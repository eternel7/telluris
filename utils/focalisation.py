"""Focalisation du personnage — 🧭 retrouver un lieu / 🎯 se focaliser sur une quête.

Le personnage se focalise sur UNE chose à la fois (champ `character["focalisation"]` :
`{"type": "lieu"|"quete", "cible": id, "posee_at": epoch}`, None/absent = aucune ;
extensible `type:"pnj"` plus tard). Deux effets selon la cible :

- guidage (type=lieu, ou quête `visite`) : à chaque déplacement le serveur calcule la
  prochaine étape (BFS sur le graphe des docs `connection`) et la direction du premier
  pas vers la case-porte (A* de combat, mêmes règles que le déplacement joueur) ;
- biais (quête `kill`/`collect`) : les tirages aléatoires favorisent l'objectif —
  poids des entrées `table_evenements` du bon type (× FOCUS_EVENEMENT_MULT, seulement
  si la cible figure dans les rencontres/ressources du lieu), et poids de la cible
  elle-même dans le tirage d'espèce / de récolte (× FOCUS_CIBLE_MULT).

Logique pure calquée sur utils/marche.py : les fonctions mutent le character sans le
sauvegarder (l'endpoint persiste) et reçoivent la DB en paramètres (find_docs_fn /
get_doc_fn) pour rester testables sans CouchDB.
"""

import time
from collections import deque

import models.character_stats as character_stats
from utils.lieux import _DIR_BIT
from utils.quetes import quete_active, objectif_atteint


# ── État ──────────────────────────────────────────────────────────────────────

def focalisation_de(character: dict) -> dict | None:
	"""Le champ `focalisation` du personnage, ou None (tolère les persos legacy)."""
	f = (character or {}).get("focalisation")
	if isinstance(f, dict) and f.get("type") and f.get("cible"):
		return f
	return None


def focalisation_effective(character: dict) -> dict | None:
	"""Normalise la focalisation en « intention » exploitable :

	- {"mode": "guidage", "lieu_cible": id, "source": "lieu"|"quete", "quete_id": ...}
	- {"mode": "kill",    "espece": "espece:x", "quete_id": ...}
	- {"mode": "collect", "item":   "item:x",   "quete_id": ...}

	Une focalisation de quête dont la quête n'est plus active est inerte (None) —
	défense en profondeur en plus des hooks d'effacement.
	"""
	f = focalisation_de(character)
	if not f:
		return None
	if f["type"] == "lieu":
		return {"mode": "guidage", "lieu_cible": f["cible"], "source": "lieu", "quete_id": None}
	if f["type"] == "quete":
		q = quete_active(character, f["cible"])
		obj = (q or {}).get("objectif") or {}
		t, cible = obj.get("type"), obj.get("cible")
		if t == "kill" and cible:
			return {"mode": "kill", "espece": cible, "quete_id": f["cible"]}
		if t == "collect" and cible:
			return {"mode": "collect", "item": cible, "quete_id": f["cible"]}
		if t == "visite" and cible:
			return {"mode": "guidage", "lieu_cible": cible, "source": "quete", "quete_id": f["cible"]}
	return None


def poser_focalisation(character: dict, type_: str, cible: str) -> dict | None:
	"""Pose la focalisation (remplace l'existante). Re-cliquer la même cible = toggle off.

	Mute le character, NE save pas. Renvoie le champ posé, ou None si toggle off.
	"""
	actuelle = focalisation_de(character)
	if actuelle and actuelle.get("type") == type_ and actuelle.get("cible") == cible:
		character["focalisation"] = None
		return None
	f = {"type": type_, "cible": cible, "posee_at": int(time.time())}
	character["focalisation"] = f
	return f


def effacer_si_quete(character: dict, quete_id: str) -> bool:
	"""Efface la focalisation si elle porte sur cette quête (terminée/abandonnée)."""
	f = focalisation_de(character)
	if f and f.get("type") == "quete" and f.get("cible") == quete_id:
		character["focalisation"] = None
		return True
	return False


def effacer_si_lieu_atteint(character: dict, lieu_id: str) -> bool:
	"""Efface la focalisation si c'est un guidage (lieu ou quête visite) vers ce lieu."""
	eff = focalisation_effective(character)
	if eff and eff.get("mode") == "guidage" and eff.get("lieu_cible") == lieu_id:
		character["focalisation"] = None
		return True
	return False


def effacer_si_objectif_atteint(character: dict) -> bool:
	"""Efface la focalisation si sa quête est active et son objectif atteint
	(hook finalize_combat pour kill, dépôt à la guilde pour collect)."""
	f = focalisation_de(character)
	if not f or f.get("type") != "quete":
		return False
	q = quete_active(character, f["cible"])
	if q and objectif_atteint(character, q):
		character["focalisation"] = None
		return True
	return False


def payload_client(character: dict, get_doc_fn) -> dict | None:
	"""{type, cible, label} pour le client (état des boutons 🧭/🎯), ou None."""
	f = focalisation_de(character)
	if not f:
		return None
	label = f["cible"]
	if f["type"] == "lieu":
		doc = get_doc_fn(f["cible"]) or {}
		label = doc.get("label") or doc.get("nom") or label
	elif f["type"] == "quete":
		q = quete_active(character, f["cible"])
		label = (q or {}).get("titre") or label
	return {"type": f["type"], "cible": f["cible"], "label": label}


# ── Graphe des lieux (macro) ──────────────────────────────────────────────────

_GRAPHE_TTL = 60.0  # secondes — évite un find_docs par pas sans invalidation manuelle
_graphe_cache: dict = {"at": 0.0, "graphe": None}


def reset_graphe_cache() -> None:
	_graphe_cache["at"] = 0.0
	_graphe_cache["graphe"] = None


def charger_graphe(find_docs_fn) -> dict:
	"""Adjacence bidirectionnelle du graphe des lieux, depuis les docs `connection` :
	{lieu_id: [{"link_id", "voisin", "porte": (x, y)}, …]} — `porte` = pos du node
	CÔTÉ lieu_id (la case du lieu où le lien est franchissable). Cache TTL court.
	"""
	now = time.time()
	if _graphe_cache["graphe"] is not None and now - _graphe_cache["at"] < _GRAPHE_TTL:
		return _graphe_cache["graphe"]
	graphe: dict = {}
	for link in (find_docs_fn({"type": "connection"}) or []):
		nodes = link.get("nodes") or []
		if len(nodes) != 2:
			continue
		for a, b in ((0, 1), (1, 0)):
			la, lb = nodes[a].get("lieu"), nodes[b].get("lieu")
			pos = nodes[a].get("pos") or [0, 0]
			if not la or not lb:
				continue
			graphe.setdefault(la, []).append({
				"link_id": link.get("_id"),
				"voisin": lb,
				"porte": (int(pos[0]), int(pos[1])),
			})
	_graphe_cache["at"] = now
	_graphe_cache["graphe"] = graphe
	return graphe


def prochaine_etape(graphe: dict, depuis: str, vers: str) -> dict | None:
	"""Premier hop du plus court chemin (en nombre de liens) `depuis` → `vers`.

	Renvoie {"suivant": lieu_id, "link_id", "porte": (x, y), "distance": n} —
	`porte` = case du lien à emprunter DANS le lieu courant. None si injoignable
	ou déjà sur place.
	"""
	if depuis == vers or depuis not in graphe:
		return None
	prev: dict = {depuis: None}  # lieu → (lieu_precedent, arete empruntée)
	file = deque([depuis])
	while file:
		cur = file.popleft()
		if cur == vers:
			break
		for arete in graphe.get(cur, []):
			v = arete["voisin"]
			if v not in prev:
				prev[v] = (cur, arete)
				file.append(v)
	if vers not in prev:
		return None
	distance = 0
	noeud = vers
	premiere = None
	while prev[noeud] is not None:
		noeud, premiere = prev[noeud][0], prev[noeud][1]
		distance += 1
	return {
		"suivant": premiere["voisin"],
		"link_id": premiere["link_id"],
		"porte": premiere["porte"],
		"distance": distance,
	}


# ── Direction dans le lieu courant (micro) ────────────────────────────────────

def direction_vers(lieu_doc: dict, position: dict, porte: tuple) -> dict | None:
	"""Premier pas du chemin A* position → case-porte, dans la grille du lieu courant.

	Mêmes règles que le déplacement joueur (cells praticables + masques nav, 8 dirs).
	Renvoie {"dx", "dy", "bit"} ou None (sur la porte, lieu sans grille, porte hors
	grille ou aucun chemin).
	"""
	cells = (lieu_doc or {}).get("cells")
	if not cells or not cells[0]:
		return None
	px = int((position or {}).get("x", 0))
	py = int((position or {}).get("y", 0))
	gx, gy = int(porte[0]), int(porte[1])
	if (px, py) == (gx, gy):
		return None
	# dims dérivées de la grille réelle (le champ `dimensions` du lieu est à borne
	# inclusive dans move_character — pas le format attendu par _find_path).
	dims = {"x": len(cells[0]), "y": len(cells)}
	if not (0 <= gx < dims["x"] and 0 <= gy < dims["y"]):
		return None
	from utils.combat import _find_path  # import paresseux : évite le cycle combat ⇄ focalisation
	path = _find_path(cells, dims, (px, py), (gx, gy), set(), (lieu_doc or {}).get("nav") or {})
	if not path or len(path) < 2:
		return None
	dx, dy = path[1][0] - px, path[1][1] - py
	return {"dx": dx, "dy": dy, "bit": _DIR_BIT.get((dx, dy), 0)}


def guidage(character: dict, lieu_doc: dict, find_docs_fn, get_doc_fn) -> dict | None:
	"""Payload de guidage servi au client (sidebar + exergue flèche/lien), ou None.

	{"cible", "cible_nom", "etape", "etape_nom", "link_id", "porte": {x, y},
	 "direction": {dx, dy, bit} | None (sur la porte → prendre le lien), "distance"}
	ou {"cible", "cible_nom", "injoignable": true} si le BFS échoue.
	"""
	eff = focalisation_effective(character)
	if not eff or eff.get("mode") != "guidage":
		return None
	cible = eff["lieu_cible"]
	lieu_courant = (character or {}).get("lieu")
	if lieu_courant == cible:
		return None  # déjà sur place (l'effacement se fait à l'arrivée ; défensif)
	cible_doc = get_doc_fn(cible) or {}
	cible_nom = cible_doc.get("label") or cible_doc.get("nom") or cible
	etape = prochaine_etape(charger_graphe(find_docs_fn), lieu_courant, cible)
	if not etape:
		return {"cible": cible, "cible_nom": cible_nom, "injoignable": True}
	suivant_doc = get_doc_fn(etape["suivant"]) or {}
	return {
		"cible": cible,
		"cible_nom": cible_nom,
		"etape": etape["suivant"],
		"etape_nom": suivant_doc.get("label") or suivant_doc.get("nom") or etape["suivant"],
		"link_id": etape["link_id"],
		"porte": {"x": etape["porte"][0], "y": etape["porte"][1]},
		"direction": direction_vers(lieu_doc, (character or {}).get("position") or {}, etape["porte"]),
		"distance": etape["distance"],
	}


# ── Biais des tirages ─────────────────────────────────────────────────────────

def _espece_de_carcasse(item_id: str) -> str:
	"""item:<sub> → espece:<sub> (règle 1-pour-1 du loot, cf. _loot_item_id)."""
	return "espece:" + item_id[len("item:"):] if item_id.startswith("item:") else ""


def boost_zone_event(character: dict, lieu_doc: dict) -> dict | None:
	"""Boost à passer à resolve_zone_event si la cible du focus est présente dans le lieu.

	{"type": "combat"|"ressource", "mult": FOCUS_EVENEMENT_MULT, "zones": {zone_def_ids}}
	— `zones` = zone-defs où la cible figure ; resolve_zone_event n'applique le boost
	que si l'une d'elles est active. Une quête collect de carcasse (aucune entrée
	`ressources` ne la produit) booste les combats contre l'espèce source à la place.
	"""
	eff = focalisation_effective(character)
	if not eff:
		return None
	if eff["mode"] == "kill":
		cibles = [("rencontres", "espece", eff["espece"], "combat")]
	elif eff["mode"] == "collect":
		# priorité à la récolte ; repli carcasse → combats contre l'espèce source
		cibles = [
			("ressources", "ressource", eff["item"], "ressource"),
			("rencontres", "espece", _espece_de_carcasse(eff["item"]), "combat"),
		]
	else:
		return None
	for champ_lieu, champ_entree, cle, type_evt in cibles:
		if not cle:
			continue
		zones: set = set()
		for e in (lieu_doc or {}).get(champ_lieu, []):
			if e.get(champ_entree) == cle:
				zones.update(e.get("zones") or [])
		if zones:
			return {"type": type_evt, "mult": character_stats.FOCUS_EVENEMENT_MULT, "zones": zones}
	return None


def espece_weights_focus(character: dict) -> dict | None:
	"""{espece_id: FOCUS_CIBLE_MULT} pour le tirage d'espèces d'un combat, ou None.

	Un focus collect de carcasse pondère l'espèce source (item:<sub> ↔ espece:<sub>) ;
	une clé absente du pool est simplement sans effet (tirage uniforme inchangé).
	"""
	eff = focalisation_effective(character)
	if not eff:
		return None
	if eff["mode"] == "kill":
		return {eff["espece"]: character_stats.FOCUS_CIBLE_MULT}
	if eff["mode"] == "collect":
		espece = _espece_de_carcasse(eff["item"])
		if espece:
			return {espece: character_stats.FOCUS_CIBLE_MULT}
	return None


def favori_recolte(character: dict) -> tuple | None:
	"""(item_id, FOCUS_CIBLE_MULT) à passer à resolve_recolte, ou None."""
	eff = focalisation_effective(character)
	if eff and eff.get("mode") == "collect":
		return (eff["item"], character_stats.FOCUS_CIBLE_MULT)
	return None

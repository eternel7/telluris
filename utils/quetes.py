# utils/quetes.py
# Moteur de quêtes : génère les offres d'une guilde à partir de son lieu PARENT
# (espèces des `rencontres` → quêtes de chasse `kill` ; `ressources` du lieu + carcasses
# des espèces → quêtes de collecte `collect`), et fournit les helpers d'état joueur
# (progression, récompenses). Le doc `quete:*` est PARTAGÉ entre quêtes générées
# (`source:"genere"`) et authorées à la main (`source:"authoree"`) ; le générateur ne
# gère/complète que les générées, les authorées s'affichent au tableau aux côtés.
#
# Comme utils/marche.py : logique pure, ne sauvegarde jamais — SAUF `remplir_tableau`,
# qui persiste les offres nouvellement générées (création des docs au tableau). Les
# helpers d'état (progression/récompenses) mutent les docs en place ; l'endpoint persiste.

import random
import time
import uuid

from db.config import get_doc, find_docs, save_doc
from models import character_stats
from utils.characters import item_ref_id, grant_xp, credit_character, cuivre_to_purse


def now_epoch() -> int:
	return int(time.time())


def _carcasse_item_id(espece_id: str) -> str | None:
	"""item:<sub_id> depuis 'espece:<sub_id>' (1-pour-1 avec les carcasses du bestiaire)."""
	if not espece_id or not espece_id.startswith("espece:"):
		return None
	return "item:" + espece_id[len("espece:"):]


# ── Lecture du lieu parent ───────────────────────────────────────────────────────

def especes_du_parent(parent_doc: dict) -> list:
	"""IDs d'espèces rencontrables dans le lieu parent (dédup, ordre stable)."""
	out = []
	for r in (parent_doc or {}).get("rencontres", []):
		eid = r.get("espece")
		if eid and eid not in out:
			out.append(eid)
	return out


def ressources_du_parent(parent_doc: dict) -> list:
	"""IDs d'items récoltables dans le lieu parent (attribut `ressources`)."""
	out = []
	for r in (parent_doc or {}).get("ressources", []):
		iid = r.get("ressource")
		if iid and iid not in out:
			out.append(iid)
	return out


def cibles_collect(parent_doc: dict) -> list:
	"""Items collectables : ressources du lieu PLUS carcasses des espèces rencontrables."""
	out = list(ressources_du_parent(parent_doc))
	for eid in especes_du_parent(parent_doc):
		iid = _carcasse_item_id(eid)
		if iid and iid not in out:
			out.append(iid)
	return out


def niveau_representatif(parent_doc: dict) -> int:
	"""Niveau de profil « moyen » du lieu, pondéré par `profil_weights` (repli 1)."""
	weights = (parent_doc or {}).get("profil_weights") or {}
	total_w = 0.0
	acc = 0.0
	for pid, w in weights.items():
		try:
			w = float(w)
		except (TypeError, ValueError):
			continue
		if w <= 0:
			continue
		prof = get_doc(pid)
		if not prof:
			continue
		acc += float(prof.get("niveau", 1)) * w
		total_w += w
	if total_w <= 0:
		return 1
	return max(1, round(acc / total_w))


# ── Noms d'affichage ─────────────────────────────────────────────────────────────

def _nom_espece(espece_id: str) -> str:
	doc = get_doc(espece_id)
	return (doc.get("nom") if doc else None) or (espece_id or "").split(":", 1)[-1]


def _nom_item(item_id: str) -> str:
	doc = get_doc(item_id)
	return (doc.get("nom") if doc else None) or (item_id or "").split(":", 1)[-1]


def _cible_nom(objectif: dict) -> str:
	t = objectif.get("type")
	cible = objectif.get("cible", "")
	if t == "kill":
		return _nom_espece(cible)
	if t == "collect":
		return _nom_item(cible)
	if t == "visite":
		doc = get_doc(cible)
		return (doc.get("label") if doc else None) or (cible or "").split(":", 1)[-1]
	return cible


# ── XP / récompenses ─────────────────────────────────────────────────────────────

def _xp_unitaire(espece_doc: dict, niveau: int) -> int:
	"""XP estimée pour tuer un individu de l'espèce au niveau donné — réutilise la formule
	du combat (`max(1, niveau*4 + somme_attrs_moyens // 10)`, cf. utils/combat.py)."""
	attrs = (espece_doc or {}).get("base_attributes", {}) or {}
	somme = 0.0
	for v in attrs.values():
		if isinstance(v, dict):
			somme += (float(v.get("min", 0) or 0) + float(v.get("max", 0) or 0)) / 2.0
	return max(1, int(niveau) * 4 + int(somme) // 10)


def _xp_unitaire_item(item_doc: dict, niveau: int) -> int:
	"""Valeur unitaire d'une cible de collecte. Carcasse (item lié à une espèce) → XP de
	chasse de l'espèce ; ressource brute → effort de récolte modéré pondéré par la rareté."""
	src = (item_doc or {}).get("source_espece")
	if src:
		esp = get_doc(src)
		if esp:
			return _xp_unitaire(esp, niveau)
	rarete = (item_doc or {}).get("rarete", "commun")
	mult = character_stats.MULT_RARETE.get(rarete, 1) or 1
	return max(1, int(niveau) * 2 + min(20, int(mult)))


_TITRES_KILL = ["Réguler les {nom}", "Chasse aux {nom}", "Éliminer les {nom}"]
_TITRES_COLLECT = ["Récolte : {nom}", "Rapporter du {nom}", "Collecte de {nom}"]


def generer_quete(guild_doc: dict, parent_doc: dict, type_obj: str, cible: str, niveau: int) -> dict:
	"""Construit un doc `quete:*` (non persisté) pour une cible donnée."""
	if type_obj == "kill":
		esp = get_doc(cible)
		xp_unit = _xp_unitaire(esp, niveau) if esp else max(1, int(niveau) * 4)
		nom = (esp.get("nom") if esp else None) or _nom_espece(cible)
		titre = random.choice(_TITRES_KILL).format(nom=nom)
		desc_tpl = "La guilde demande d'abattre {q} {nom} qui rôdent dans les environs d'Auxerre."
	else:  # collect
		item = get_doc(cible)
		xp_unit = _xp_unitaire_item(item, niveau)
		nom = (item.get("nom") if item else None) or _nom_item(cible)
		titre = random.choice(_TITRES_COLLECT).format(nom=nom)
		desc_tpl = "Rapportez {q} {nom} à la guilde."

	# Quantité tirée dans [QTE_MIN, borne_haute] : plus la cible est « chère » (xp_unit
	# élevé), plus la borne haute se rapproche du minimum (objectifs courts pour les durs).
	qmin = int(character_stats.QUETE_QTE_MIN)
	qmax = max(qmin, int(character_stats.QUETE_QTE_MAX))
	plage = qmax - qmin
	facteur_diff = min(1.0, xp_unit / 40.0)  # ~40 XP/unité = cible difficile
	borne_haute = max(qmin, int(round(qmax - plage * facteur_diff)))
	quantite = random.randint(qmin, borne_haute)

	xp = max(1, round(xp_unit * quantite * character_stats.QUETE_XP_FACTEUR))
	cuivre = max(0, round(xp * character_stats.QUETE_CUIVRE_PAR_XP))

	guild_id = guild_doc.get("_id", "")
	sub = guild_id.split(":", 1)[-1] if ":" in guild_id else guild_id
	return {
		"_id": f"quete:{sub}_{uuid.uuid4().hex[:12]}",
		"type": "quete",
		"source": "genere",
		"giver": guild_id,
		"lieu_parent": (parent_doc or {}).get("_id"),
		"titre": titre,
		"description": desc_tpl.format(q=quantite, nom=nom),
		"rang": "F",
		"objectif": {"type": type_obj, "cible": cible, "quantite": quantite},
		"recompenses": {"xp": xp, "cuivre": cuivre, "items": []},
		"statut": "offerte",
		"genere_at": now_epoch(),
	}


# ── Tableau de la guilde ─────────────────────────────────────────────────────────

def offres_du_giver(guild_id: str) -> list:
	"""Offres ouvertes (`statut:"offerte"`) d'une guilde — générées ET authorées."""
	docs = find_docs({"type": "quete"}) or []
	return [
		d for d in docs
		if d.get("giver") == guild_id and d.get("statut", "offerte") == "offerte"
	]


def remplir_tableau(guild_doc: dict) -> list:
	"""Garantit QUETE_BOARD_TAILLE offres GÉNÉRÉES au tableau (complétées à la volée),
	persiste les nouvelles, puis renvoie toutes les offres ouvertes (générées + authorées).
	Le nombre d'offres générées est borné par le nombre de cibles distinctes du parent."""
	guild_id = guild_doc.get("_id")
	parent_id = guild_doc.get("lieu_parent")
	parent_doc = get_doc(parent_id) if parent_id else None

	offres = offres_du_giver(guild_id)
	generees = [o for o in offres if o.get("source") == "genere"]
	manquantes = max(0, int(character_stats.QUETE_BOARD_TAILLE) - len(generees))

	if manquantes > 0 and parent_doc:
		niveau = niveau_representatif(parent_doc)
		existants = {
			(o["objectif"].get("type"), o["objectif"].get("cible"))
			for o in offres if o.get("objectif")
		}
		candidats = [("kill", eid) for eid in especes_du_parent(parent_doc)]
		candidats += [("collect", iid) for iid in cibles_collect(parent_doc)]
		random.shuffle(candidats)
		for type_obj, cible in candidats:
			if manquantes <= 0:
				break
			if (type_obj, cible) in existants:
				continue
			q = generer_quete(guild_doc, parent_doc, type_obj, cible, niveau)
			if save_doc(q) is None:
				continue
			offres.append(q)
			existants.add((type_obj, cible))
			manquantes -= 1
	return offres


# ── État joueur ──────────────────────────────────────────────────────────────────

def snapshot_quete(q: dict) -> dict:
	"""Copie figée d'une offre, posée dans `character["quetes_actives"]` à l'acceptation
	(la quête reste stable même si le doc `quete:*` est ensuite purgé/régénéré)."""
	return {
		"id": q.get("_id"),
		"titre": q.get("titre", "—"),
		"description": q.get("description", ""),
		"rang": q.get("rang", "F"),
		"giver": q.get("giver"),
		"objectif": dict(q.get("objectif", {})),
		"recompenses": dict(q.get("recompenses", {})),
		"progress": 0,
		"accepte_at": now_epoch(),
	}


def quete_active(character: dict, quete_id: str) -> dict | None:
	for q in character.get("quetes_actives", []):
		if q.get("id") == quete_id:
			return q
	return None


def _count_inventaire(character: dict, item_id: str) -> int:
	return sum(1 for ref in character.get("inventaire", []) if item_ref_id(ref) == item_id)


def progress_courant(character: dict, q: dict) -> int:
	"""Progression effective (entier). `collect` = comptage d'inventaire à la volée ;
	`kill`/`visite` = compteur stocké sur la quête active."""
	obj = q.get("objectif", {})
	if obj.get("type") == "collect":
		return _count_inventaire(character, obj.get("cible"))
	return int(q.get("progress", 0) or 0)


def objectif_atteint(character: dict, q: dict) -> bool:
	obj = q.get("objectif", {})
	return progress_courant(character, q) >= int(obj.get("quantite", 0) or 0)


def quete_detail(character: dict, q: dict) -> dict:
	"""Vue d'affichage d'une quête active (onglet fiche + tableau) : progression + récompenses."""
	obj = q.get("objectif", {})
	prog = progress_courant(character, q)
	qte = int(obj.get("quantite", 0) or 0)
	rec = q.get("recompenses", {}) or {}
	purse = cuivre_to_purse(rec.get("cuivre", 0))
	return {
		"id": q.get("id") or q.get("_id"),
		"titre": q.get("titre", "—"),
		"description": q.get("description", ""),
		"rang": q.get("rang", "F"),
		"objectif": obj,
		"progress": min(prog, qte) if qte else prog,
		"quantite": qte,
		"complete": prog >= qte,
		"progress_txt": f"{_cible_nom(obj)} : {min(prog, qte) if qte else prog}/{qte}",
		"recompenses": {
			"xp": rec.get("xp", 0),
			"or": purse["or"],
			"argent": purse["argent"],
			"cuivre": purse["cuivre"],
		},
	}


def fiche_details(character: dict) -> tuple:
	"""Détails affichables des quêtes du perso, TOUS donneurs confondus (onglet 📜 de la
	fiche). Renvoie (actives_detail, terminees). Partagé par /play et les endpoints quêtes
	pour que la fiche reflète accept/terminer sans rechargement."""
	actives = [quete_detail(character, q) for q in character.get("quetes_actives", [])]
	terminees = list(character.get("quetes_terminees", []))
	return actives, terminees


def retirer_items(character: dict, item_id: str, quantite: int) -> int:
	"""Retire jusqu'à `quantite` exemplaires de `item_id` de l'inventaire (mute en place).
	Renvoie le nombre réellement retiré. Utilisé au turn-in des quêtes `collect`."""
	inv = character.get("inventaire", [])
	garde = []
	retire = 0
	for ref in inv:
		if retire < quantite and item_ref_id(ref) == item_id:
			retire += 1
			continue
		garde.append(ref)
	character["inventaire"] = garde
	return retire


def appliquer_recompenses(character: dict, q: dict) -> dict:
	"""Crédite XP + cuivre (+ items éventuels) d'une quête (mute en place, NE SAUVEGARDE
	PAS — l'endpoint persiste). Renvoie un récap {xp, purse}."""
	rec = q.get("recompenses", {}) or {}
	xp_info = grant_xp(character, rec.get("xp", 0))
	purse = credit_character(character, rec.get("cuivre", 0))
	items = rec.get("items") or []
	if items:
		inv = character.get("inventaire", [])
		inv.extend(items)
		character["inventaire"] = inv
	return {"xp": xp_info, "purse": purse}


# ── Hooks de progression (appelés par combat / déplacement) ──────────────────────

def maj_progress_kills(character: dict, monstres: list) -> None:
	"""Incrémente la progression des quêtes `kill` actives selon les monstres tués
	(`not vivant`). Mute `character["quetes_actives"]` en place. À appeler dans
	finalize_combat, sous le garde exactly-once `combats_recompenses`."""
	actives = character.get("quetes_actives", [])
	if not actives:
		return
	morts = {}
	for m in monstres or []:
		if not m.get("vivant", True):
			eid = m.get("espece_id")
			if eid:
				morts[eid] = morts.get(eid, 0) + 1
	if not morts:
		return
	for q in actives:
		obj = q.get("objectif", {})
		if obj.get("type") != "kill":
			continue
		n = morts.get(obj.get("cible"), 0)
		if not n:
			continue
		qte = int(obj.get("quantite", 0) or 0)
		q["progress"] = min(qte, int(q.get("progress", 0) or 0) + n)


def maj_progress_visite(character: dict, lieu_id: str) -> None:
	"""Marque atteint tout objectif `visite` actif ciblant `lieu_id`. Mute en place."""
	for q in character.get("quetes_actives", []):
		obj = q.get("objectif", {})
		if obj.get("type") == "visite" and obj.get("cible") == lieu_id:
			q["progress"] = int(obj.get("quantite", 1) or 1)

# utils/chasse.py
# Quêtes de « chasse » : traquer et tuer UN ennemi d'une espèce donnée, marqué d'un PROFIL
# ÉLEVÉ, dans un lieu précis. Deux canaux :
# - Le TABLEAU de la guilde (`categorie:"guilde_aventurier"`) — grade visé = `max−1`.
# - Le PNJ du COMPTOIR (`categorie:"guilde_aventurier_comptoir"`) — grade visé = `max`, et
#   seulement comme CONDITION de gain de rang de guilde (rang propre à la cité = lieu_parent).
#   Une narration pré-combat annonce l'élite « couverte du sang de ses victimes ».
#
# Le grade (profil) est RÉSOLU À LA GÉNÉRATION (pas au combat) : à partir du lieu cible, d'une
# position dans une zone d'influence qui contient l'espèce, et de la distribution de grades
# résolue à cette position (`resolve_profil_weights`), FILTRÉE par `restriction_tags ⊆ tags de
# l'espèce` (un loup sans tag « magie » ne devient jamais un profil « magie »). Le `profil_id`
# est stocké dans l'objectif ; au combat, un seul monstre de l'espèce, s'il est tiré
# naturellement, se voit forcer ce profil (cf. routers/combat.py).
#
# Rang de guilde v1 = prestige/affichage seul : stocké par cité dans
# `character["rangs_guilde"] = {"lieu:auxerre": "F"}` (échelle recrutement.RANGS), sans effet
# mécanique encore. L'offre de rang est tirée à l'entrée du comptoir et persistée en champ
# transitoire `character["rang_offert"]` — même sémantique que `transport_offert`/`pnj_present`.
#
# Logique pure (DB injectée : get_doc_fn / find_docs_fn), mute sans save — l'endpoint persiste.
# Pattern de utils/transport.py. World-vars lues via le module (jamais from-import).

import random
import uuid

from models import character_stats
from utils.zones import (
	load_zone_defs_for_lieu, compute_zone_intensity, resolve_profil_weights,
)
from utils.recrutement import RANGS
from utils import quetes


# Paramètres de génération du grade : « le plus haut possible » vs « juste en dessous ».
TIER_MAX = "max"
TIER_MAX_MOINS_1 = "max_moins_1"


def est_comptoir(lieu_doc: dict) -> bool:
	"""Le lieu est-il un comptoir de guilde (donneur des quêtes de RANG) ?"""
	return (lieu_doc or {}).get("categorie") == "guilde_aventurier_comptoir"


# ── Lieux & position de chasse ───────────────────────────────────────────────────

def lieux_chasse_de(cite_id: str, get_doc_fn, find_docs_fn) -> list:
	"""Lieux où une quête de chasse de la cité peut se dérouler : la cité elle-même PLUS
	ses lieux rattachés (`lieu_parent == cité`) qui portent à la fois `rencontres` et
	`zone_influences` (sans quoi ni espèce à traquer, ni zone où résoudre le grade).
	Aujourd'hui seule la cité Auxerre remplit ça ; l'ouverture aux enfants est future-proof."""
	out = []
	cite = get_doc_fn(cite_id) if cite_id else None
	if cite is not None:
		out.append(cite)
	enfants = (find_docs_fn({"type": "lieu", "lieu_parent": cite_id}) or []) if cite_id else []
	for l in enfants:
		if l.get("_id") == cite_id:
			continue
		if l.get("rencontres") and l.get("zone_influences"):
			out.append(l)
	return out


def _zones_de_lespece(lieu_doc: dict, espece_id: str) -> set:
	"""Ids de zones d'influence (`rencontres[].zones`) où l'espèce peut apparaître."""
	return {
		z for r in (lieu_doc or {}).get("rencontres", [])
		if r.get("espece") == espece_id for z in (r.get("zones") or [])
	}


def position_de_chasse(lieu_doc: dict, espece_doc: dict) -> dict | None:
	"""Centre `{x,y}` d'un placement d'une zone qui CONTIENT l'espèce (tiré au hasard), pour
	stocker dans l'objectif et résoudre le grade. `None` si le lieu n'a pas de grille
	(`dimensions`) ou si aucune zone de l'espèce n'est placée."""
	if not lieu_doc or not lieu_doc.get("dimensions"):
		return None
	zones_cibles = _zones_de_lespece(lieu_doc, (espece_doc or {}).get("_id"))
	if not zones_cibles:
		return None
	placements = [
		p for p in lieu_doc.get("zone_influences", []) if p.get("zone") in zones_cibles
	]
	if not placements:
		return None
	p = random.choice(placements)
	return {"x": p.get("x", 0), "y": p.get("y", 0)}


def _profils_compatibles(lieu_doc: dict, espece_doc: dict, position: dict | None, get_doc_fn) -> list:
	"""Docs profil candidats au grade de l'élite : distribution résolue aux zones de l'espèce
	(placements actifs à la position si fournie, sinon tous), FILTRÉE par
	`restriction_tags ⊆ tags de l'espèce`. Liste vide si aucune distribution ou aucun compatible."""
	zones_cibles = _zones_de_lespece(lieu_doc, (espece_doc or {}).get("_id"))
	if not zones_cibles:
		return []
	placements = [
		p for p in (lieu_doc or {}).get("zone_influences", []) if p.get("zone") in zones_cibles
	]
	if position is not None:
		zone_defs = load_zone_defs_for_lieu(lieu_doc, get_doc_fn)
		px, py = position.get("x", 0), position.get("y", 0)
		actifs = [
			p for p in placements
			if compute_zone_intensity(px, py, p, zone_defs.get(p.get("zone"))) > 0.0
		]
		# Si aucun placement de la cible n'est actif au point tiré, on retombe sur tous
		# les placements de l'espèce (le point est le centre de l'un d'eux, mais un point
		# hors des autres formes ne doit pas rétrécir la distribution à vide).
		placements = actifs or placements
	pw = resolve_profil_weights(placements, lieu_doc)
	if not pw:
		return []
	tags = set((espece_doc or {}).get("tags", []))
	compat = []
	for pid in pw:
		p = get_doc_fn(pid)
		if p and set(p.get("restriction_tags") or []) <= tags:
			compat.append(p)
	return compat


def resoudre_profil_chasse(lieu_doc: dict, espece_doc: dict, tier: str,
                           position: dict | None, get_doc_fn) -> str | None:
	"""`profil_id` de l'élite à traquer, RÉSOLU À LA GÉNÉRATION. Grade le plus haut possible
	(`tier="max"`) ou juste en dessous (`"max_moins_1"`) parmi les profils compatibles avec
	l'espèce. Égalité de niveau → tirage au hasard. `None` si aucun profil compatible."""
	compat = _profils_compatibles(lieu_doc, espece_doc, position, get_doc_fn)
	if not compat:
		return None
	niveaux = sorted({int(p.get("niveau", 1)) for p in compat})
	niv_max = niveaux[-1]
	cible_niv = niv_max - 1 if tier == TIER_MAX_MOINS_1 else niv_max
	# Candidats de niveau exactement visé ; à défaut, le compatible de niveau le plus proche
	# PAR EN-DESSOUS (repli : le plus bas disponible, si la cible tombe sous le minimum).
	choix = [p for p in compat if int(p.get("niveau", 1)) == cible_niv]
	if not choix:
		en_dessous = [p for p in compat if int(p.get("niveau", 1)) <= cible_niv]
		if en_dessous:
			meilleur = max(int(p.get("niveau", 1)) for p in en_dessous)
			choix = [p for p in en_dessous if int(p.get("niveau", 1)) == meilleur]
		else:
			choix = [p for p in compat if int(p.get("niveau", 1)) == niveaux[0]]
	return random.choice(choix)["_id"]


# ── Quêtes de chasse actives ─────────────────────────────────────────────────────

def quetes_chasse_actives(character: dict, lieu_id: str) -> list:
	"""Quêtes actives de type `chasse` dont l'objectif se déroule dans `lieu_id`."""
	out = []
	for q in (character or {}).get("quetes_actives", []):
		obj = q.get("objectif", {})
		if obj.get("type") == "chasse" and obj.get("lieu") == lieu_id:
			out.append(q)
	return out


def direction_cardinale_simple(depuis_xy, vers_xy) -> str:
	"""Direction cardinale de `vers_xy` PAR RAPPORT À `depuis_xy`, règle par axe (`y` croît
	vers le BAS) : sud si `depuis.y < vers.y`, nord si `>`, rien si égal ; est si
	`depuis.x < vers.x`, ouest si `>`, rien si égal. Combinée → « sud-est », « nord »,
	« ouest »… ; chaîne vide si même case (aucun axe ne départage)."""
	dx0, dy0 = int(depuis_xy[0]), int(depuis_xy[1])
	dx1, dy1 = int(vers_xy[0]), int(vers_xy[1])
	ns = "sud" if dy0 < dy1 else ("nord" if dy0 > dy1 else "")
	ew = "est" if dx0 < dx1 else ("ouest" if dx0 > dx1 else "")
	return "-".join(p for p in (ns, ew) if p)


def dans_zone_chasse(objectif: dict, position_joueur: dict | None) -> bool:
	"""Le combat est-il déclenché dans la zone 3×3 centrée sur la position de la quête ?
	L'élite n'est marquée que là. Sans `position` (lieu sans grille) → True (contrainte de
	lieu seule, comportement historique). Position du joueur absente → False."""
	pq = (objectif or {}).get("position")
	if not pq:
		return True
	pos = position_joueur or {}
	jx, jy = pos.get("x"), pos.get("y")
	if jx is None or jy is None:
		return False
	return abs(int(jx) - int(pq.get("x", 0))) <= 1 and abs(int(jy) - int(pq.get("y", 0))) <= 1


# ── Rang de guilde (par cité) ────────────────────────────────────────────────────

def rang_de(character: dict, cite_id: str) -> str:
	"""Rang courant du perso pour cette cité (repli `F` = débutant)."""
	return (character or {}).get("rangs_guilde", {}).get(cite_id, RANGS[0])


def rang_suivant(rang: str) -> str:
	"""Rang immédiatement au-dessus (plafonné au sommet). Rang inconnu → premier de l'échelle."""
	try:
		i = RANGS.index(rang)
	except ValueError:
		return RANGS[0]
	return RANGS[min(i + 1, len(RANGS) - 1)]


def rang_max_atteint(rang: str) -> bool:
	return rang == RANGS[-1]


def promouvoir(character: dict, cite_id: str) -> str:
	"""Monte d'un cran le rang du perso pour cette cité (mute, sans save). Renvoie le nouveau rang."""
	rangs = character.setdefault("rangs_guilde", {})
	rangs[cite_id] = rang_suivant(rangs.get(cite_id, RANGS[0]))
	return rangs[cite_id]


# ── Offre de rang au comptoir (miroir simplifié du transport authoré) ─────────────

# Qualificatifs de l'élite traquée, INDEXÉS PAR NIVEAU DE PROFIL (1 → 6). Le `nom` du doc
# `profil:*` est taillé pour un aventurier (« Novice », « Seigneur mage ») : collé sur une bête,
# il sonne faux. On lui substitue ici, POUR LES QUÊTES DE CHASSE SEULEMENT, une échelle de
# bestiaire. Le doc profil n'est pas modifié (son `nom` sert partout ailleurs).
QUALIFICATIFS = ["Vicieux", "Sanguinaire", "Farouche", "Impitoyable", "Fléau", "Apocalypse"]


def qualificatif_de(profil: dict | None) -> str:
	"""Qualificatif d'élite d'un profil, d'après son `niveau` (borné aux deux extrémités : un
	profil de niveau 0 ou > 6 retombe sur le premier / le dernier de l'échelle)."""
	niv = int((profil or {}).get("niveau", 1) or 1)
	return QUALIFICATIFS[max(0, min(len(QUALIFICATIFS) - 1, niv - 1))]


def _narration_rang(nom: str, grade: str) -> str:
	"""Texte d'ambiance pré-combat quand l'élite recherchée est enfin débusquée (l'espèce
	varie → généré à la volée, pas figé dans un nœud de dialogue)."""
	return (
		f"Une odeur de charnier flotte dans l'air. La créature qui vous fait face — "
		f"{nom}, le spécimen « {grade} » que la guilde vous a chargé d'abattre — est encore "
		f"couverte du sang de ses victimes. Aucun doute : c'est elle. L'épreuve commence."
	)


def _lieu_nom(lieu_doc: dict) -> str:
	return (
		(lieu_doc or {}).get("label")
		or (lieu_doc or {}).get("nom")
		or ((lieu_doc or {}).get("_id") or "").split(":", 1)[-1]
	)


def _construire_quete_rang(comptoir_doc: dict, cite: str, lieu_doc: dict, espece_doc: dict,
                           position: dict | None, profil_id: str, rang_courant: str, get_doc_fn) -> dict:
	"""Doc `quete:*` d'une épreuve de rang (non persisté ; l'accept en fait un snapshot)."""
	profil = get_doc_fn(profil_id) or {}
	niv = int(profil.get("niveau", 1))
	grade = qualificatif_de(profil)
	nom = espece_doc.get("nom", "créature")
	lieu_nom = _lieu_nom(lieu_doc)
	rang_vise = rang_suivant(rang_courant)
	xp = max(1, round(quetes._xp_unitaire(espece_doc, niv) * character_stats.QUETE_CHASSE_XP_FACTEUR))
	cuivre = max(0, round(xp * character_stats.QUETE_CUIVRE_PAR_XP))
	objectif = {
		"type": "chasse",
		"cible": espece_doc["_id"],
		"lieu": lieu_doc["_id"],
		"profil": profil_id,
		"quantite": 1,
	}
	if position is not None:
		objectif["position"] = position
	sub = (comptoir_doc.get("_id", "") or "").split(":", 1)[-1]
	return {
		"_id": f"quete:{sub}_rang_{uuid.uuid4().hex[:12]}",
		"type": "quete",
		"source": "rang",
		"giver": comptoir_doc.get("_id"),
		"lieu_parent": cite,
		"titre": f"Épreuve de rang : traquer le {nom} « {grade} »",
		"description": (
			f"Le maître d'armes exige une preuve : traquez et abattez ce {nom} « {grade} », "
			f"l'élite qui écume {lieu_nom}, pour prétendre au rang {rang_vise}."
		),
		"rang": rang_vise,
		"objectif": objectif,
		"recompenses": {"xp": xp, "cuivre": cuivre, "items": []},
		"rang_vise": rang_vise,
		"narration": _narration_rang(nom, grade),
		"statut": "offerte",
	}


def _rang_deja_actif(character: dict, cite: str) -> bool:
	"""Une épreuve de rang de cette cité est-elle déjà en cours ? (pas d'empilement)."""
	for q in (character or {}).get("quetes_actives", []):
		if q.get("source") == "rang" and q.get("cite") == cite:
			return True
	return False


def offre_rang_pour(character: dict, comptoir_doc: dict, get_doc_fn, find_docs_fn) -> dict | None:
	"""Construit une épreuve de rang au comptoir, ou `None` si : pas de `lieu_parent`, rang
	max déjà atteint, épreuve de rang de cette cité déjà active, ou aucune cible résolvable au
	grade MAX. Ne tire PAS la probabilité (c'est `poser_rang_offert` qui la gère)."""
	cite = (comptoir_doc or {}).get("lieu_parent")
	if not cite:
		return None
	rang_courant = rang_de(character, cite)
	if rang_max_atteint(rang_courant):
		return None
	if _rang_deja_actif(character, cite):
		return None
	candidats = []
	for L in lieux_chasse_de(cite, get_doc_fn, find_docs_fn):
		for eid in quetes.especes_du_parent(L):
			espece = get_doc_fn(eid)
			if not espece:
				continue
			position = position_de_chasse(L, espece)
			if position is None:
				continue
			profil_id = resoudre_profil_chasse(L, espece, TIER_MAX, position, get_doc_fn)
			if profil_id:
				candidats.append((L, espece, position, profil_id))
	if not candidats:
		return None
	L, espece, position, profil_id = random.choice(candidats)
	return _construire_quete_rang(comptoir_doc, cite, L, espece, position, profil_id, rang_courant, get_doc_fn)


def poser_rang_offert(character: dict, comptoir_doc: dict, get_doc_fn, find_docs_fn,
                      pnj_present: bool = False) -> bool:
	"""Tire (une fois par entrée) une offre de rang au comptoir — même sémantique que
	`poser_transport_offert`. Persiste `character["rang_offert"] = {lieu, quete}` : un refresh
	ne re-tire pas, ressortir/rentrer re-tire. Aucune offre hors comptoir, sans PNJ présent, ou
	hors proba `QUETE_CHASSE_PROBA_RANG`. Renvoie True si le champ a changé."""
	lieu_id = (comptoir_doc or {}).get("_id")
	if not lieu_id or not est_comptoir(comptoir_doc):
		# Sortie d'un comptoir : purger un éventuel reliquat d'offre.
		if character.get("rang_offert") is not None:
			character.pop("rang_offert", None)
			return True
		return False
	deja = character.get("rang_offert")
	if isinstance(deja, dict) and deja.get("lieu") == lieu_id:
		return False
	quete = None
	if pnj_present and random.random() < float(character_stats.QUETE_CHASSE_PROBA_RANG):
		quete = offre_rang_pour(character, comptoir_doc, get_doc_fn, find_docs_fn)
	character["rang_offert"] = {"lieu": lieu_id, "quete": quete}
	return True


def offre_rang_courante(character: dict, comptoir_doc: dict) -> dict | None:
	"""L'offre de rang posée pour CE comptoir (sinon None). Lecture pure (pas de tirage)."""
	offert = character.get("rang_offert") or {}
	if offert.get("lieu") == (comptoir_doc or {}).get("_id"):
		return offert.get("quete")
	return None


def rang_a_rapporter(character: dict, cite: str) -> dict | None:
	"""Épreuve de rang de cette cité complétée (`progress >= quantite`) mais pas encore
	soldée — celle dont il faut « rendre compte » au comptoir. None sinon."""
	for q in (character or {}).get("quetes_actives", []):
		if q.get("source") == "rang" and q.get("cite") == cite and quetes.objectif_atteint(character, q):
			return q
	return None


def accepter_rang(character: dict) -> dict | None:
	"""Accepte l'offre de rang courante : pousse un snapshot actif (avec `source`/`rang_vise`/
	`cite`/`narration`, que le combat et le turn-in relisent) et vide l'offre. Mute sans save.
	Renvoie la quête active, ou None s'il n'y a pas d'offre à accepter."""
	offert = character.get("rang_offert") or {}
	offre = offert.get("quete")
	if not offre:
		return None
	snap = quetes.snapshot_quete(offre)
	snap["type"] = "quete"
	snap["source"] = "rang"
	snap["rang_vise"] = offre.get("rang_vise")
	snap["cite"] = offre.get("lieu_parent")
	snap["narration"] = offre.get("narration")
	character.setdefault("quetes_actives", []).append(snap)
	character["rang_offert"] = {"lieu": offert.get("lieu"), "quete": None}
	return snap


def solder_rang(character: dict, quete_id: str) -> dict | None:
	"""Rend compte au comptoir d'une épreuve de rang complétée : PROMEUT le perso pour la cité,
	applique XP/prime, archive la quête (mute sans save). Renvoie `{promu, recompenses}` ou
	None si la quête est introuvable / pas encore complétée."""
	actives = character.get("quetes_actives", [])
	q = next(
		(x for x in actives
		 if (x.get("id") or x.get("_id")) == quete_id and x.get("source") == "rang"),
		None,
	)
	if q is None or not quetes.objectif_atteint(character, q):
		return None
	cite = q.get("cite")
	nouveau = promouvoir(character, cite) if cite else rang_de(character, cite)
	recap = quetes.appliquer_recompenses(character, q)
	character["quetes_actives"] = [x for x in actives if x is not q]
	character.setdefault("quetes_terminees", []).append({
		"id": q.get("id") or q.get("_id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", nouveau),
		"termine_at": quetes.now_epoch(),
	})
	return {"promu": nouveau, "recompenses": recap}

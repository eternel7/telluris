# utils/xp_monstre.py
# XP d'un monstre et PRIX de sa dépouille, tous deux tirés de sa DANGEROSITÉ.
#
# DANGEROSITÉ = `potentiel.potentiel_menace(espèce, grade)` — la mesure du rang de /admin/table
# et du plancher des épreuves de rang : potentiel de combat (équipement espéré compris) × fuite
# interdite. Mesurée sur le SPÉCIMEN (son grade tiré), pas sur l'espèce au grade de référence :
# un loup « seigneur » est un monstre de rang D, un loup novice de la vermine.
#
# XP — courbe en PALIERS (Auteur, 13/11) : au plancher du rang R (`QUETE_RANG_POTENTIEL_MIN`), la
# bête rapporte `XP_MONSTRE_PART_NIVEAU` du coût du niveau d'entrée de R (`QUETE_RANG_NIVEAU_ENTREE`,
# même convention de coût que `chasse.xp_promotion`) ; interpolation linéaire entre deux planchers,
# pente du dernier segment prolongée au-delà. ⚠️ Aucune table recopiée : modifier un plancher ou un
# niveau d'entrée déplace la courbe.
#
# PRIX — une dépouille est tout item porteur de `source_espece` (carcasse, portion débitée,
# ossements, résidu spectral, débris animé) sans `valeur` écrite à la main :
#     prix_de_xp(xp du spécimen) × poids de l'instance / poids moyen de la carcasse source.
# Le grade voyage sur la RÉFÉRENCE (`ref["profil"]`, posé au butin, recopié sur chaque portion) ;
# référence sans grade (butin antérieur, rayon d'une boutique) ⇒ grade de référence du rang
# (`potentiel.RANG_PROFIL_REFERENCE`). La part du poids rapporte au poids moyen de la carcasse
# ENTIÈRE, si bien que débiter conserve la valeur (les portions somment au poids source).
#
# Rien n'est stocké (CLAUDE.md « Derived stats are never stored ») : seul le potentiel, coûteux
# (une simulation de belligérant), est mémoïsé par process, clé = révisions des docs espèce et
# profil. Une world-var de combat changée (MONSTRE_EQUIPEMENT_PROBA…) ne vide pas ce mémo ; les
# world-vars de CETTE courbe sont relues à chaque appel.
#
# Sens des imports : `potentiel → simulateur → combat` ; ce module importe `potentiel`
# PARESSEUSEMENT, car `combat` et `characters` l'appellent.

from models import character_stats
from utils.recrutement import RANGS

# Niveau d'entrée du PREMIER rang (F), absent de `QUETE_RANG_NIVEAU_ENTREE` : on y entre dès le
# niveau 1, au potentiel 0.
NIVEAU_ENTREE_PREMIER_RANG = 1

_memo_potentiel: dict = {}


def _cout_niveau(niveau: int) -> int:
	"""Coût du niveau d'entrée — même convention que `chasse.xp_promotion`."""
	return character_stats.xp_seuil_niveau(niveau + 1) - character_stats.xp_seuil_niveau(niveau)


def ancres() -> list:
	"""`[(potentiel, xp)]` triés : un point par rang de l'échelle qui a un plancher ET un niveau
	d'entrée, plus le premier rang au potentiel 0. Relues à chaque appel (world-vars)."""
	part = float(character_stats.XP_MONSTRE_PART_NIVEAU)
	planchers = character_stats.QUETE_RANG_POTENTIEL_MIN or {}
	entrees = character_stats.QUETE_RANG_NIVEAU_ENTREE or {}
	points = {0.0: _cout_niveau(NIVEAU_ENTREE_PREMIER_RANG) * part}
	for rang in RANGS:
		if rang in planchers and rang in entrees:
			points[float(planchers[rang])] = _cout_niveau(int(entrees[rang])) * part
	return sorted(points.items())


def xp_de_potentiel(potentiel) -> int:
	"""XP d'un monstre de cette dangerosité (≥ 1)."""
	pts = ancres()
	p = max(0.0, float(potentiel or 0))
	if len(pts) == 1:
		return max(1, round(pts[0][1]))
	for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
		if p <= x1:
			break
	xp = y0 + (y1 - y0) * (p - x0) / (x1 - x0)
	return max(1, round(xp))


def prix_de_xp(xp) -> int:
	"""Prix (cuivre) d'une carcasse de poids moyen dont la bête valait `xp` (≥ 1)."""
	ref = float(character_stats.CARCASSE_PRIX_REF_XP)
	rapport = max(0.0, float(xp or 0)) / ref
	return max(1, round(float(character_stats.CARCASSE_PRIX_REF_CUIVRE)
						* rapport ** float(character_stats.CARCASSE_PRIX_EXPOSANT)))


def potentiel_specimen(espece_id: str, profil_id: str | None, get_doc_fn) -> float | None:
	"""`potentiel_menace` du spécimen, mémoïsé par process. None si l'espèce est introuvable ou
	ne se construit pas en belligérant."""
	espece = get_doc_fn(espece_id) if espece_id else None
	if not espece:
		return None
	profil = get_doc_fn(profil_id) if profil_id else None
	cle = (espece_id, espece.get("_rev"), profil_id if profil else None, (profil or {}).get("_rev"))
	if cle in _memo_potentiel:
		return _memo_potentiel[cle]
	from utils import potentiel   # paresseux : potentiel → simulateur → combat
	try:
		v = float(potentiel.potentiel_menace(espece_id, profil_id if profil else None, get_doc_fn)[0])
	except Exception:
		v = None
	_memo_potentiel[cle] = v
	return v


def xp_specimen(espece_id: str, profil_id: str | None, get_doc_fn) -> int:
	"""XP d'un spécimen. Potentiel illisible ⇒ le bas de la courbe (potentiel 0)."""
	return xp_de_potentiel(potentiel_specimen(espece_id, profil_id, get_doc_fn) or 0)


def xp_attendue(espece_id: str, profil_weights: dict | None, get_doc_fn) -> int:
	"""XP ESPÉRÉE d'une rencontre avec l'espèce sous ces poids de grades (`profil_weights` d'un
	lieu) ; aucun poids exploitable ⇒ grade de référence du rang."""
	acc, total = 0.0, 0.0
	for pid, w in (profil_weights or {}).items():
		try:
			w = float(w)
		except (TypeError, ValueError):
			continue
		if w <= 0 or not get_doc_fn(pid):
			continue
		acc += xp_specimen(espece_id, pid, get_doc_fn) * w
		total += w
	if total <= 0:
		return xp_specimen(espece_id, _profil_reference(), get_doc_fn)
	return max(1, round(acc / total))


def _profil_reference() -> str:
	from utils import potentiel
	return potentiel.RANG_PROFIL_REFERENCE


def _poids_moyen(item_doc: dict) -> float:
	p = (item_doc or {}).get("poids", 0)
	try:
		if isinstance(p, (list, tuple)) and p:
			return (float(p[0] or 0) + float(p[-1] or 0)) / 2
		return float(p or 0)
	except (TypeError, ValueError):
		return 0.0


def est_depouille(item_doc: dict | None) -> bool:
	"""Item tiré d'une bête et sans prix écrit à la main."""
	return bool((item_doc or {}).get("source_espece")) and (item_doc or {}).get("valeur") is None


def prix_depouille(item_doc: dict, poids_instance, profil_id: str | None, get_doc_fn) -> int | None:
	"""Prix (cuivre) d'une dépouille, ou None si l'item n'en est pas une. `poids_instance` None
	⇒ poids moyen (rapport 1) ; `profil_id` None ⇒ grade de référence."""
	if not est_depouille(item_doc):
		return None
	source = item_doc
	if item_doc.get("portion_de"):
		source = get_doc_fn(item_doc["portion_de"]) or item_doc
	base = prix_de_xp(xp_specimen(item_doc["source_espece"], profil_id or _profil_reference(), get_doc_fn))
	moyen = _poids_moyen(source)
	try:
		poids = float(poids_instance) if poids_instance is not None else moyen
	except (TypeError, ValueError):
		poids = moyen
	rapport = poids / moyen if moyen > 0 else 1.0
	return max(1, round(base * rapport))

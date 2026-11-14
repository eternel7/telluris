# utils/ia_monstre.py
# Types d'IA des monstres (pur) : tags d'espèce `ia_<type>[_<nombre>][_<profil>]`.
#
# Trois axes, cumulables, un type par axe après résolution :
#   déplacement : brute (défaut) · hit_and_run · artilleur · meute · embuscade[_<rayon>] · protecteur
#   cible       : proche (défaut) · predateur · berserker
#   fuite       : aucune (défaut) · fuyard[_<pct de PV>]
# Un tag suffixé d'un profil (`ia_berserker_champion`) l'emporte, POUR SON AXE, sur le tag
# générique. Sans tag : comportement d'avant, à la lettre. `berserker` annule tout recul
# (fuite, retrait du hit-and-run et de l'artilleur). La provocation reste prioritaire
# (`combat._cible_joueur`) et réveille un embusqué.
#
# Le moteur (`combat._run_monster_turn`) aiguille sur ces axes ; ce module ne fait que lire
# les tags et trancher les choix qui ne demandent pas la carte.

DEPLACEMENTS = ("hit_and_run", "artilleur", "meute", "embuscade", "protecteur")
CIBLES = ("predateur", "berserker")
FUITES = ("fuyard",)
AXE = {**{t: "deplacement" for t in DEPLACEMENTS}, **{t: "cible" for t in CIBLES},
	   **{t: "fuite" for t in FUITES}}
# Préfixe le plus long d'abord : `hit_and_run` contient des `_`.
_TYPES = sorted(AXE, key=len, reverse=True)

DEFAUT = {"deplacement": "brute", "cible": "proche", "fuite": 0, "rayon": 0}
# Seuil de fuite d'un `ia_fuyard` sans nombre, en % des PV max.
FUITE_DEFAUT = 30
# Rayon d'éveil d'un `ia_embuscade` sans nombre, en cases.
RAYON_EMBUSCADE_DEFAUT = 3
# Un embusqué éveillé ne s'éloigne pas de son poste au-delà de rayon + cette marge.
LAISSE_MARGE = 2
# Un protecteur reste à au plus cette distance de l'allié qu'il couvre.
DISTANCE_PROTECTEUR = 2


def _lire_tag(tag) -> tuple | None:
	"""`ia_<type>[_<nombre>][_<profil>]` → (type, nombre | None, profil | ""), ou None."""
	tag = str(tag or "")
	if not tag.startswith("ia_"):
		return None
	reste = tag[3:]
	for t in _TYPES:
		if reste == t:
			return t, None, ""
		if reste.startswith(t + "_"):
			suite = reste[len(t) + 1:].split("_")
			nombre = None
			if suite and suite[0].isdigit():
				nombre = int(suite.pop(0))
			return t, nombre, "_".join(suite)
	return None


def ia_de_tags(tags, profil_id=None) -> dict:
	"""IA résolue pour ce profil : {deplacement, cible, fuite (seuil %, 0 = jamais), rayon}.

	Par axe, un tag au profil de `profil_id` l'emporte sur un tag générique ; un tag d'un
	AUTRE profil est ignoré, comme un tag mal formé."""
	profil = str(profil_id or "").split(":", 1)[-1]
	generiques: dict = {}
	propres: dict = {}
	for tag in tags or []:
		lu = _lire_tag(tag)
		if not lu:
			continue
		t, nombre, pour = lu
		if pour and pour != profil:
			continue
		cible = propres if pour else generiques
		cible.setdefault(AXE[t], (t, nombre))
	ia = dict(DEFAUT)
	for axe, (t, nombre) in {**generiques, **propres}.items():
		if axe == "fuite":
			ia["fuite"] = nombre if nombre is not None else FUITE_DEFAUT
		else:
			ia[axe] = t
			if t == "embuscade":
				ia["rayon"] = nombre if nombre is not None else RAYON_EMBUSCADE_DEFAUT
	return ia


def ia_du_snapshot(tags, profil_id=None) -> dict | None:
	"""L'IA à figer sur le snapshot, ou None si elle est celle d'avant (clé absente)."""
	ia = ia_de_tags(tags, profil_id)
	return None if ia == DEFAUT else ia


def ia_de(monstre: dict) -> dict:
	"""IA d'un snapshot (combat déjà en base sans clé ⇒ défaut)."""
	return {**DEFAUT, **((monstre or {}).get("ia") or {})}


def berserker(ia: dict) -> bool:
	return (ia or {}).get("cible") == "berserker"


def doit_fuir(ia: dict, monstre: dict) -> bool:
	"""Sous son seuil de fuite (en % des PV max), et jamais pour un berserker."""
	seuil = int((ia or {}).get("fuite") or 0)
	if seuil <= 0 or berserker(ia):
		return False
	pv_max = max(1, int(monstre.get("pv_max") or 1))
	return int(monstre.get("currentPV") or 0) * 100 < seuil * pv_max


def _ratio_pv(acteur: dict) -> float:
	return int(acteur.get("currentPV") or 0) / max(1, int(acteur.get("pv_max") or 1))


def choisir_cible(ia: dict, monstre: dict, candidats: list, distance_fn, atteignable_fn) -> dict | None:
	"""Cible selon l'axe `cible` parmi les joueurs visibles (provocation tranchée en amont) :
	  · proche     : le plus proche ;
	  · predateur  : le plus blessé (PV en proportion) parmi ceux qu'il atteint CE tour,
	                 le plus proche à défaut ;
	  · berserker  : son dernier agresseur s'il est parmi eux, le plus proche à défaut.
	Ex æquo : le plus proche, puis l'ordre des candidats (le principal en tête)."""
	if not candidats:
		return None
	proche = min(candidats, key=distance_fn)
	mode = (ia or {}).get("cible")
	if mode == "predateur":
		atteints = [j for j in candidats if atteignable_fn(j)]
		if atteints:
			return min(atteints, key=lambda j: (_ratio_pv(j), distance_fn(j)))
	elif mode == "berserker":
		agresseur = monstre.get("dernier_agresseur")
		for j in candidats:
			if agresseur and j.get("id") == agresseur:
				return j
	return proche


def score_case_meute(position_relative: int, deja_visee: bool) -> int:
	"""Score d'une case d'approche autour de la cible : dos (2) > flanc (1) > face (0),
	moins 2 si un congénère la vise déjà. `position_relative` : signe du produit scalaire
	entre l'axe de la cible et le vecteur cible → case (< 0 = dans son dos)."""
	base = 2 if position_relative < 0 else (1 if position_relative == 0 else 0)
	return base - (2 if deja_visee else 0)


def le_plus_blesse(allies: list) -> dict | None:
	"""Allié vivant au plus bas ratio de PV, s'il est blessé (sinon None)."""
	blesses = [a for a in allies or [] if a.get("vivant", True) and _ratio_pv(a) < 1]
	return min(blesses, key=_ratio_pv) if blesses else None

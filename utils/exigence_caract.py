# utils/exigence_caract.py
# EXIGENCE DE CARACTÉRISTIQUE d'une compétence (pur). Champ `exigences` du doc `competence:*` :
#
#     "exigences": {"Ag": 38, "F": 29}
#
# Posé SEULEMENT sur les compétences hors norme (dev/gen_equilibrage_competences.py) ; absent ⇒
# aucune condition. Lu sur la caract BRUTE (`caracteristiques_current`, convention 3 : un buff
# n'ouvre jamais un accès) :
#   - refus d'APPRENDRE tant que non remplie ;
#   - compétence déjà connue : INACTIVE tant que non remplie (active non lançable, passive sans
#     effet), vérifiée à la LECTURE — aucune migration.
#
# Barème du générateur : seuil = base + 3 × niv (base 20 en F/R/Ag/Ch, 30 en Vol/Int/Cha),
# secondaire = base + 1,5 × niv, niveau plafonné à 10.

BASE_PHYSIQUE = 20
BASE_MENTALE = 30
PAS_PAR_NIVEAU = 3
NIVEAU_MAX = 10
MENTALES = ("Vol", "Int", "Cha")
STATS = ("F", "R", "Ag", "Ch", "Vol", "Int", "Cha", "V")


def seuil(stat: str, niveau: int, secondaire: bool = False) -> int:
	"""Seuil d'exigence d'une carac pour un niveau (effectif) de compétence."""
	niv = max(0, min(NIVEAU_MAX, int(niveau or 0)))
	base = BASE_MENTALE if stat in MENTALES else BASE_PHYSIQUE
	pas = PAS_PAR_NIVEAU / 2 if secondaire else PAS_PAR_NIVEAU
	return int(base + pas * niv)


def normaliser(exigences) -> dict:
	"""{stat: seuil entier > 0} ; clés inconnues et valeurs invalides ignorées."""
	out = {}
	for k, v in (exigences or {}).items() if isinstance(exigences, dict) else ():
		if str(k) not in STATS:
			continue
		try:
			n = int(v)
		except (TypeError, ValueError):
			continue
		if n > 0:
			out[str(k)] = n
	return out


def manquantes(comp: dict, caracts_brutes: dict) -> dict:
	"""Exigences NON remplies : {stat: seuil}. Vide ⇒ accès ouvert."""
	caracts_brutes = caracts_brutes or {}
	return {k: v for k, v in ((comp or {}).get("exigences") or {}).items()
			if int(caracts_brutes.get(k, 0) or 0) < v}


def satisfaite(comp: dict, caracts_brutes: dict) -> bool:
	return not manquantes(comp, caracts_brutes)


def libelle(exigences: dict) -> str:
	"""« Ag 38 · F 29 » — vide sans exigence. Texte servi tel quel au client."""
	return " · ".join(f"{k} {v}" for k, v in (exigences or {}).items())


def brutes(character: dict) -> dict:
	"""Caracts BRUTES d'un porteur (doc personnage, compagnon, ou snapshot qui les a figées)."""
	return (character or {}).get("caracteristiques_current") or {}

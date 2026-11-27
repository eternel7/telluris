# utils/palier_vocation.py
# Palier de vocation (pur) : pour monter du niveau n au niveau n+1, le personnage doit
# MAÎTRISER (avoir appris) au moins `VOC_TALENTS_MIN` talents du niveau n de sa vocation
# COURANTE. Un talent = une compétence de la vocation, ou un sort de son école NATIVE.
#
# - Appris = maîtrisé : une compétence connue mais INACTIVE (exigence de caractéristique
#   non remplie) compte quand même.
# - Exigence plafonnée au contenu : min(VOC_TALENTS_MIN, talents du niveau n que la vocation
#   peut apprendre ou connaît déjà). Un palier vide ne bloque jamais la montée.
# - Écoles achetées (lettré, `magies_apprises`) : hors palier — elles ont leur propre niveau.
#
# Gardé par `spend_xp_vocation`, publié par `fiche.bloc_fiche` (`voc_palier`) pour griser
# le bouton « Monter ».

from models import character_stats
from utils import sorts as sorts_util


def _as_int(v) -> int:
	try:
		return int(v or 0)
	except (TypeError, ValueError):
		return 0


def etat_palier(character: dict, find_docs, rules_vocations) -> dict:
	"""{niveau, requis, maitrises, manque, ok} du palier courant de la vocation."""
	character = character or {}
	voc = character.get("voc") or ""
	n = _as_int((character.get("vocations_niveaux") or {}).get(voc, 0))
	connus = set(character.get("competences_connues") or []) | set(character.get("sorts_connus") or [])

	talents = set()  # talents du niveau n que la vocation peut apprendre, ou déjà connus
	for doc in find_docs({"type": "competence"}) or []:
		doc = doc or {}
		if doc.get("vocation") != voc or _as_int(doc.get("niveau")) != n:
			continue
		if doc.get("_id") in connus or not sorts_util.apprentissage_exclu(doc, voc, rules_vocations):
			talents.add(doc.get("_id"))
	ecole = sorts_util.ecole_native(voc, rules_vocations)
	if ecole:
		for doc in find_docs({"type": "sort"}) or []:
			doc = doc or {}
			if _as_int(doc.get("niveau")) != n or sorts_util.magie_de_sort(doc, rules_vocations) != ecole:
				continue
			if doc.get("_id") in connus or not sorts_util.apprentissage_exclu(doc, voc, rules_vocations):
				talents.add(doc.get("_id"))
	talents.discard(None)

	requis = min(max(0, character_stats.VOC_TALENTS_MIN), len(talents))
	maitrises = len(talents & connus)
	manque = max(0, requis - maitrises)
	return {"niveau": n, "requis": requis, "maitrises": maitrises, "manque": manque, "ok": manque == 0}


def motif_refus(etat: dict) -> str | None:
	"""Message du refus de montée, ou None si le palier est maîtrisé."""
	if etat.get("ok"):
		return None
	m = etat["manque"]
	return (f"Maîtrisez encore {m} talent{'s' if m > 1 else ''} de niveau {etat['niveau']} "
			f"de votre vocation ({etat['maitrises']}/{etat['requis']}) avant de monter")

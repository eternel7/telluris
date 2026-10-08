"""Accord grammatical des espèces dans les titres générés (`utils/accord_espece.py`)."""

import pytest

from utils import accord_espece as ae


def _e(nom, **kw):
	return {"_id": "espece:x", "nom": nom, **kw}


LOUP = _e("Loup", genre="m")
HARPIE = _e("Harpie", genre="f", h_aspire=True)
HYDRE = _e("Hydre", genre="f")
OURS = _e("Ours", genre="m")
ANE = _e("Âne", genre="m")
FAUVES = _e("Fauves", genre="m", pluriel=True)
APEP = _e("Apep", genre="m", nom_propre=True)
CUPIDON = _e("Cupidon", genre="m", nom_propre=True)
SIRENE = _e("Sirene", genre="f")


@pytest.mark.parametrize("doc,forme,attendu", [
	(LOUP, "le", "le Loup"), (LOUP, "du", "du Loup"), (LOUP, "un", "un Loup"), (LOUP, "ce", "ce Loup"),
	(SIRENE, "le", "la Sirene"), (SIRENE, "du", "de la Sirene"),
	(SIRENE, "un", "une Sirene"), (SIRENE, "ce", "cette Sirene"),
	# Élision devant voyelle (accents ignorés) et « h » muet.
	(OURS, "le", "l'Ours"), (OURS, "du", "de l'Ours"), (OURS, "ce", "cet Ours"),
	(ANE, "le", "l'Âne"),
	(HYDRE, "le", "l'Hydre"), (HYDRE, "du", "de l'Hydre"), (HYDRE, "ce", "cette Hydre"),
	# « h » aspiré : pas d'élision.
	(HARPIE, "le", "la Harpie"), (HARPIE, "du", "de la Harpie"),
	# Nom de groupe.
	(FAUVES, "le", "les Fauves"), (FAUVES, "du", "des Fauves"),
	(FAUVES, "un", "des Fauves"), (FAUVES, "ce", "ces Fauves"),
	# Nom propre : pas d'article, la contraction s'élide.
	(APEP, "le", "Apep"), (APEP, "du", "d'Apep"), (APEP, "un", "Apep"),
	(CUPIDON, "du", "de Cupidon"),
])
def test_groupe(doc, forme, attendu):
	assert ae.groupe(doc, forme) == attendu


def test_doc_sans_genre_reste_masculin():
	"""Aucune migration : un doc d'avant la pose du genre se lit comme avant."""
	vieux = {"_id": "espece:vipere", "nom": "Vipère"}
	assert ae.groupe(vieux, "le") == "le Vipère"
	assert ae.pronom(vieux) == "le"
	assert ae.sujet(vieux) == "il"


def test_nom_absent_retombe_sur_le_slug():
	assert ae.groupe({"_id": "espece:loup"}, "le") == "le loup"


def test_pronoms():
	assert (ae.pronom(LOUP), ae.sujet(LOUP)) == ("le", "il")
	assert (ae.pronom(SIRENE), ae.sujet(SIRENE)) == ("la", "elle")
	assert (ae.pronom(FAUVES), ae.sujet(FAUVES)) == ("les", "ils")


def test_forme_inconnue_est_refusee():
	with pytest.raises(ValueError):
		ae.groupe(LOUP, "au")


def test_majuscule_ne_touche_pas_au_reste():
	assert ae.majuscule("un Loup Garou") == "Un Loup Garou"
	assert ae.majuscule("") == ""


def test_titres_de_chasse_accordes():
	"""Les gabarits de chasse n'ont pas de « le {nom} » en dur : un nom féminin ou élidé
	passe par `accord_espece.groupe`."""
	from utils import quetes
	for gabarit in quetes._TITRES_CHASSE:
		assert "{nom}" not in gabarit
		titre = gabarit.format(le=ae.groupe(HARPIE, "le"), du=ae.groupe(HARPIE, "du"), grade="Fléau")
		assert "le Harpie" not in titre and "du Harpie" not in titre
		assert "la Harpie" in titre or "de la Harpie" in titre

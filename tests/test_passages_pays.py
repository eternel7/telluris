# tests/test_passages_pays.py
# Calque d'une CARTE DE PAYS en exploration (/play) : `lieux.voile_hors_pays` (cases à 0
# voilées, la mer à 1 laissée claire) et `lieux.passages_carte` (un marqueur par connexion,
# libellé de la DESTINATION, filtré comme la liste des sous-lieux).

from utils.lieux import passages_carte, voile_hors_pays

DOCS = {
	"lieu:espagne": {"label": "Espagne"},
	"lieu:chartres": {"label": "Chartres"},
	"lieu:france": {"label": "France"},
}
get_doc = DOCS.get
JAMAIS_FERMEE = lambda conn: False


def conn(_id, a, b, type_="chemin"):
	return {"_id": _id, "nodes": [a, b], "metadata": {"type": type_}}


def test_voile_ne_couvre_que_les_cases_a_zero():
	assert voile_hors_pays([[0, 1, 3], [5, 0, 1]]) == ["100", "010"]
	assert voile_hors_pays(None) == []


def test_un_marqueur_par_noeud_de_la_carte_avec_le_libelle_de_la_destination():
	c = conn("link:a", {"lieu": "lieu:france", "pos": [26, 38], "label": "Hendaye côté France"},
		{"lieu": "lieu:espagne", "pos": [52, 7], "label": "Plage d'Hendaye"})
	assert passages_carte([c], "lieu:france", JAMAIS_FERMEE, get_doc) == [
		{"x": 26, "y": 38, "link_id": "link:a", "type": "chemin", "label": "Plage d'Hendaye"}]


def test_sans_libelle_de_noeud_on_prend_celui_du_lieu_destination():
	c = conn("link:b", {"lieu": "lieu:chartres", "pos": [77, 4]},
		{"lieu": "lieu:france", "pos": [41, 14]}, "ville")
	assert passages_carte([c], "lieu:france", JAMAIS_FERMEE, get_doc)[0]["label"] == "Chartres"


def test_connexion_interne_un_marqueur_par_extremite():
	c = conn("link:i", {"lieu": "lieu:france", "pos": [1, 1], "label": "Haut"},
		{"lieu": "lieu:france", "pos": [5, 5], "label": "Bas"})
	assert [(p["x"], p["label"]) for p in passages_carte([c], "lieu:france", JAMAIS_FERMEE, get_doc)] \
		== [(1, "Bas"), (5, "Haut")]


def test_connexion_fermee_ou_noeud_sans_pos_ignores():
	c = conn("link:a", {"lieu": "lieu:france", "pos": [2, 2]}, {"lieu": "lieu:espagne", "pos": [0, 0]})
	assert passages_carte([c], "lieu:france", lambda _c: True, get_doc) == []
	sans_pos = conn("link:b", {"lieu": "lieu:france"}, {"lieu": "lieu:espagne", "pos": [0, 0]})
	assert passages_carte([sans_pos], "lieu:france", JAMAIS_FERMEE, get_doc) == []


def test_plusieurs_liens_vers_la_meme_destination_depuis_une_case_dedoublonnes():
	"""Chartres a neuf liens arrivant tous en (41,14) de la France : un seul marqueur."""
	liens = [conn(f"link:c{i}", {"lieu": "lieu:chartres", "pos": [i, 0]},
		{"lieu": "lieu:france", "pos": [41, 14]}, "pays") for i in range(3)]
	assert len(passages_carte(liens, "lieu:france", JAMAIS_FERMEE, get_doc)) == 1

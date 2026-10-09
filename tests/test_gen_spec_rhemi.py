"""Peuplement de Rhemi : fonctions pures de `dev/gen_spec_rhemi.py`."""

import importlib.util
import os
import random

import pytest

_CHEMIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev", "gen_spec_rhemi.py")
_spec = importlib.util.spec_from_file_location("gen_spec_rhemi", _CHEMIN)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

# Carré de portes (2,2)-(12,2)-(12,12)-(2,12) sur une grille 15x15 toute en terrain 1.
PORTES = [(2, 2), (12, 2), (12, 12), (2, 12)]


def _grille(n=15, valeur=1):
	return [[valeur] * n for _ in range(n)]


def test_polygone_contient_le_centre_pas_le_dehors():
	poly = g.polygone_des_portes(PORTES)
	assert g.dans_polygone(7, 7, poly)
	assert not g.dans_polygone(0, 7, poly)
	assert not g.dans_polygone(14, 14, poly)


def test_cases_interieures_restent_dans_les_portes_avec_marge():
	cases = g.cases_interieures(_grille(), PORTES, marge=1.0)
	assert cases
	for x, y in cases:
		assert 3 <= x <= 11 and 3 <= y <= 11       # marge d'une case au bord du carré
		assert (x, y) not in PORTES


def test_case_injoignable_a_pied_est_ecartee():
	"""Un îlot de terrain 1 cerné de 0 n'est pas joignable depuis une porte."""
	cells = _grille()
	for x in range(4, 11):
		for y in range(4, 11):
			cells[y][x] = 0
	cells[7][7] = 1
	assert (7, 7) not in g.cases_interieures(cells, PORTES)


def test_terrain_non_marchable_ecarte():
	cells = _grille()
	cells[6][6] = 5
	assert (6, 6) not in g.cases_interieures(cells, PORTES)


def test_etaler_rend_des_cases_distinctes_et_deterministes():
	cases = g.cases_interieures(_grille(), PORTES)
	a = g.etaler(cases, 10)
	assert len(set(a)) == 10
	assert a == g.etaler(cases, 10)
	with pytest.raises(ValueError):
		g.etaler(cases, len(cases) + 1)


@pytest.mark.parametrize("fichier,attendu", [
	("marchand_elfe_f_apothicairerie.png", ("elfe", "F", "apothicairerie")),
	("marchand_humaine_f_negoce.jpg", ("humain", "F", "negociant")),
	("marchand_hobbit_m_archerie02.png", ("hobbit", "M", "fletcher")),
	("marchand_elfe_f_tanerie.png", ("elfe", "F", "tannerie")),
	("marchand_nain_m_cirier.png", ("nain", "M", "atelier_de_cirier")),
	("marchand_ogre_m_jardinerie.png", ("ogre", "M", "jardinier")),
	("marchand_nain_f_tisserie.png", ("nain", "F", "tissage")),
])
def test_decoder_portrait_generique(fichier, attendu):
	assert g.decoder_portrait(fichier) == attendu


@pytest.mark.parametrize("fichier", [
	"marchand_george_dubois_armurerie.png",       # nominatif : appartient à un PNJ précis
	"marchand_3_fées_cuisine.png",
	"cartographe_Milo_hobbit_m.jpg",
])
def test_portrait_nominatif_ou_hors_motif_exclu(fichier):
	assert g.decoder_portrait(fichier) is None


REPERTOIRE = {
	"PRENOMS": {"humain": {"M": ["Jean"], "F": ["Jeanne"]}, "nain": {"M": ["Gimli"], "F": ["Dis"]},
				"defaut": {"M": ["X"], "F": ["Y"]}},
	"NOMS": {"humain": ["Martin"], "nain": ["Barbeforge"], "defaut": ["Z"]},
	"PRENOM_RACE_MUTUALISEE": "humain",
	"PRENOM_MUTUALISE_PROBA": 0.0,
}


def test_nom_tire_dans_le_pool_de_la_race_et_du_sexe():
	pris = set()
	assert g.tirer_nom("nain", "F", random.Random(1), REPERTOIRE, pris) == "Dis Barbeforge"
	assert g.tirer_nom("humain", "M", random.Random(1), REPERTOIRE, pris) == "Jean Martin"


def test_nom_jamais_redonne():
	pris = {"Dis Barbeforge"}
	with pytest.raises(SystemExit):
		g.tirer_nom("nain", "F", random.Random(1), REPERTOIRE, pris)


def test_enceinte_sans_portes_garde_la_plus_grande_composante_en_diagonale():
	"""Chartres : pas de portes. Une rue en escalier (liée par des diagonales) compte comme un
	seul réseau ; un îlot isolé est écarté ; le dehors du polygone aussi."""
	cells = _grille(valeur=0)
	for k in range(3, 12):
		cells[k][k] = 1                       # diagonale : 8-connexe, pas 4-connexe
	cells[3][10] = 1                          # îlot isolé
	cells[0][0] = 1                           # hors enceinte
	enceinte = [(2, 2), (12, 2), (12, 12), (2, 12)]
	cases = g.cases_dans_enceinte(cells, enceinte, marge=0.5)
	assert (7, 7) in cases and (4, 4) in cases
	assert (10, 3) not in cases
	assert (0, 0) not in cases


def test_chaque_cite_a_ses_reglages():
	for cite, r in g.VILLES.items():
		assert r["auberges"], cite
		assert r["enceinte"] is None or len(r["enceinte"]) >= 3, cite
	assert g.sortie_de("lieu:chartres").endswith("chartres_magasins_spec.json")


def test_prenom_mutualise_garde_le_nom_de_la_race():
	rep = dict(REPERTOIRE, PRENOM_MUTUALISE_PROBA=1.0)
	assert g.tirer_nom("nain", "M", random.Random(1), rep, set()) == "Jean Barbeforge"

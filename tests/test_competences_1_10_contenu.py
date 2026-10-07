# tests/test_competences_1_10_contenu.py
#
# Contenu `jsons/competences_vocations_1_10_a_importer.json` (dev/gen_competences_1_10.py) :
#   · le générateur passe toutes ses gardes (invariants de check_competences_doc compris) ;
#   · à chaque niveau 1 → 10, existantes comprises : 4 compétences pour une vocation à
#     magie, 2 passives + 5 actives sinon — cibles RELUES dans le module, jamais retapées ;
#   · aucune passive neuve pour une vocation à magie ;
#   · chaque active a son animation SONORE (nappe sonore pour un cône), aucune passive n'en a ;
#   · le fichier committé est conforme au générateur ; un lot déjà importé n'est ni une
#     collision ni réémis (régénération idempotente).

import copy
import importlib.util
import json
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(RACINE, "dev")


@pytest.fixture(scope="module")
def gen():
	if not any(f.startswith("telluris-dump-") for f in os.listdir(os.path.join(RACINE, "jsons"))):
		pytest.skip("aucun dump committé")
	if DEV not in sys.path:
		sys.path.insert(0, DEV)
	spec = importlib.util.spec_from_file_location("gen_competences_1_10",
												  os.path.join(DEV, "gen_competences_1_10.py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


@pytest.fixture(scope="module")
def construit(gen):
	ref = gen.charger_referentiel()
	lot, a_emettre, erreurs, compte = gen.construire(ref)
	return {"ref": ref, "lot": lot, "a_emettre": a_emettre, "erreurs": erreurs, "compte": compte}


def test_le_generateur_passe_toutes_ses_gardes(construit):
	assert construit["erreurs"] == []


def test_chaque_vocation_a_le_meme_nombre_par_niveau(gen, construit):
	assert set(construit["compte"]) == set(gen.PROFILS)
	for voc, c in construit["compte"].items():
		for niv in gen.NIVEAUX:
			ex_p, ex_a, nv_p, nv_a = c["niveaux"][niv]
			if c["magique"]:
				assert ex_p + ex_a + nv_a == gen.TOTAL_MAGIE, (voc, niv)
				assert nv_p == 0, (voc, niv)
			else:
				assert ex_p + nv_p == gen.PASSIVES_SANS_MAGIE, (voc, niv)
				assert ex_a + nv_a == gen.ACTIVES_SANS_MAGIE, (voc, niv)
			assert nv_p <= gen.PASSIVES_SANS_MAGIE, (voc, niv)


def test_les_vocations_a_magie_n_ont_que_des_actives_neuves(construit):
	magiques = {v for v, c in construit["compte"].items() if c["magique"]}
	assert magiques, "rules:vocations ne déclare aucune vocation à magie"
	assert all(d["mode"] == "active" for d in construit["lot"] if d["vocation"] in magiques)


def test_chaque_active_a_une_animation_sonore(gen, construit):
	themes = construit["ref"]["themes"]
	for d in construit["lot"]:
		if d["mode"] == "passive":
			assert "animation" not in d and "animation_zone" not in d, d["_id"]
			continue
		assert d["animation"].startswith(gen.PREFIXE_ANIM), d["_id"]
		sonore = d.get("animation_zone") or d["animation"]
		theme = themes[sonore[len(gen.PREFIXE_ANIM):]]
		assert theme.get("son"), d["_id"]
		est_cone = (d.get("zone") or {}).get("forme") == "cone"
		assert est_cone == ("animation_zone" in d), d["_id"]
		if est_cone:
			nappe = d["animation_zone"][len(gen.PREFIXE_ANIM):]
			assert d["zone"]["longueur"] == gen.LONGUEUR_CONE[nappe], d["_id"]


def test_les_actives_martiales_ignorent_la_charge(gen, construit):
	for d in construit["lot"]:
		if d["mode"] == "active" and gen.PROFILS[d["vocation"]]["martial"]:
			assert d.get("sensibilite_charge") == 0, d["_id"]


def test_fichier_committe_conforme_au_generateur(gen, construit):
	fichier = json.load(open(gen.SORTIE, encoding="utf-8"))
	par_id = {d["_id"]: d for d in construit["lot"]}
	# Sous-ensemble et non égalité : une fois le lot importé dans un dump plus récent, le
	# générateur ne réémet plus rien, mais le fichier committé reste valable.
	for doc in fichier:
		assert doc == par_id.get(doc["_id"]), doc["_id"]


def test_un_lot_deja_importe_n_est_ni_une_collision_ni_reemis(gen, construit):
	ref = copy.deepcopy(construit["ref"])
	for d in construit["lot"]:
		ref["competences"][d["_id"]] = dict(d, _rev="1-test")
	lot, a_emettre, erreurs, _ = gen.construire(ref)
	assert erreurs == []
	assert len(lot) == len(construit["lot"])
	assert a_emettre == []

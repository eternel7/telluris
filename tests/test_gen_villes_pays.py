"""dev/gen_villes_pays.py — chaque cité posée sur la carte de son pays, Atlantis et Mu créées
sans connexion ; rejeu idempotent sur le dump."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_villes_pays as gvp  # noqa: E402
from dev.gen_plaine_europeenne import zone_de  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402


def _taille(_nom):
	return (1408, 768)


def _proposer(doc):
	dim = doc["dimensions"]
	return {"cells": [[1] * dim["x"] for _ in range(dim["y"])], "nav": {}, "rapport": {}}


@pytest.fixture(scope="module")
def dump():
	docs = ggi.charger_dump()
	ids = {d.get("_id") for d in docs}
	if not (set(gvp.CITES) | set(gvp.ANCRES_PAYS)) <= ids:
		pytest.skip("aucun dump committé avec ces cités et ces pays")
	return docs


@pytest.fixture(scope="module")
def construit(dump):
	return gvp.construire(dump, _taille, _proposer)


def test_aucun_refus(construit):
	assert construit[2] == []


def test_un_lien_par_sortie_chaque_bout_dans_sa_zone(dump, construit):
	par_id = {d["_id"]: d for d in dump}
	liens = construit[1]
	assert len(liens) == sum(len(c["sorties"]) for c in gvp.CITES.values())
	assert len({l["_id"] for l in liens}) == len(liens)
	for cite_id, spec in gvp.CITES.items():
		pays = par_id[spec["pays"]]
		zone_pays = zone_de(pays["cells"], pays.get("nav") or {}, gvp.ANCRES_PAYS[spec["pays"]])
		cite = par_id[cite_id]
		for nom, (_, ancre) in spec["sorties"].items():
			lien = next(l for l in liens if l["_id"] == f"link:{gvp.slug(spec['pays'])}_to_{gvp.slug(cite_id)}_{nom}")
			(n_pays, n_cite) = lien["nodes"]
			assert n_pays["lieu"] == spec["pays"] and tuple(n_pays["pos"]) in zone_pays
			assert n_cite["lieu"] == cite_id
			assert tuple(n_cite["pos"]) in zone_de(cite["cells"], cite.get("nav") or {}, ancre)
			assert n_cite["label"].startswith(f"{cite.get('label')} — par ")


def test_cases_du_pays_distinctes_par_cite(construit):
	for cite_id in gvp.CITES:
		poses = [tuple(l["nodes"][0]["pos"]) for l in construit[1] if l["nodes"][1]["lieu"] == cite_id]
		assert len(poses) == len(set(poses))


def test_atlantis_et_mu_creees_sans_connexion(construit):
	lieux, liens = construit[0], construit[1]
	neufs = {d["_id"]: d for d in lieux if d["_id"] in ("lieu:atlantis", "lieu:mu")}
	assert set(neufs) == {"lieu:atlantis", "lieu:mu"}
	assert {d["image"] for d in neufs.values()} == set(gvp.IMAGES_NOUVELLES)
	assert all(d["categorie"] == "ville" and d["cells"] for d in neufs.values())
	assert not any(n["lieu"] in neufs for l in liens for n in l["nodes"])


def test_parent_pose_s_il_manque_jamais_reecrit():
	assert gvp.rattachee({"_id": "lieu:x", "_rev": "1-a"}, "lieu:p") == {"_id": "lieu:x", "lieu_parent": "lieu:p"}
	assert gvp.rattachee({"_id": "lieu:x", "lieu_parent": "lieu:q"}, "lieu:p")["lieu_parent"] == "lieu:q"


def test_rejeu_sur_dump_a_jour_n_emet_rien(dump, construit):
	lieux, liens = construit[0], construit[1]
	emis, refus = a_emettre(dump, lieux + liens)
	assert refus == [] and emis
	par_id = {d["_id"]: d for d in dump}
	par_id.update({d["_id"]: d for d in emis})
	rejeu = list(par_id.values())

	def interdit(*_):
		raise AssertionError("Atlantis et Mu sont en base : aucune grille à proposer")

	l2, d2, r2, _ = gvp.construire(rejeu, _taille, interdit)
	assert r2 == [] and a_emettre(rejeu, l2 + d2) == ([], [])


def test_pays_absent_refuse(dump):
	sans = [d for d in dump if d.get("_id") != "lieu:egypte"]
	_, _, refus, _ = gvp.construire(sans, _taille, _proposer)
	assert refus == ["absent(s) du dump ou sans grille : lieu:egypte"]

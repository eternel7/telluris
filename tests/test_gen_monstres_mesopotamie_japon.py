# tests/test_gen_monstres_mesopotamie_japon.py
#
# Générateur `dev/gen_monstres_mesopotamie_japon.py` (19/11/2026) : branché sur le moteur de
# gen_monstres_legendes le temps du test (monkeypatch), tables sources complètes, boss hors zone,
# DELTA seul et rejeu vide. Rang injecté (`rangs_fn`) : aucun hasard. Dump le plus récent par glob.

import glob
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "dev"))
sys.path.insert(0, RACINE)
import gen_monstres_mesopotamie_japon as lot  # noqa: E402

DEJA_EN_BASE = {"mushhushshu", "kappa", "tengu"}  # sur les planches, déjà au bestiaire : non touchés


@pytest.fixture
def gen(monkeypatch):
	lot.installer(monkeypatch.setattr)
	return lot.moteur


def _dernier_dump(gen):
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	return {d["_id"]: d for d in gen.armure.charger(dumps[-1]) if isinstance(d, dict) and d.get("_id")}


def _rang_fixe(rang):
	return lambda docs: {d["_id"]: rang for d in docs if d.get("type") == "espece"}


def test_aucune_espece_deja_existante_n_est_recreee():
	assert not (set(lot.NOUVELLES) & DEJA_EN_BASE)


def test_tables_sources_couvrent_chaque_espece(gen):
	for slug, spec in lot.NOUVELLES.items():
		assert slug in gen.JETONS, slug
		if "humanoide" in spec["tags"]:
			assert gen.KITS.get(slug), slug
		for c in gen.capacites.ATTRIBUTION.get(slug, []):
			assert c in gen.capacites.COMPETENCES, (slug, c)


def test_boss_hors_des_zones_les_autres_places():
	boss = {s for s, spec in lot.NOUVELLES.items() if "boss" in spec["tags"]}
	assert not (set(lot.ZONES) & boss)
	assert set(lot.ZONES) | boss == set(lot.NOUVELLES)


def test_kitsune_et_tanuki_fuient(gen):
	for slug in ("kitsune", "tanuki"):
		assert any(t.startswith("ia_fuyard") for t in gen.capacites.IA[slug]), slug


def test_controle_puis_delta_et_rejeu_vide(gen):
	base = _dernier_dump(gen)
	assert gen.controler(base) == []
	if any(("espece:" + s) in base for s in lot.NOUVELLES):
		pytest.skip("espèces déjà importées dans ce dump")
	docs, deja = gen.docs_monstres(base, _rang_fixe("C"))
	ids = [d["_id"] for d in docs]
	assert len(ids) == len(set(ids))
	assert {i for i in ids if i.startswith("espece:")} == {"espece:" + s for s in lot.NOUVELLES}
	assert "rules:regions" in deja  # asie existe déjà : non réécrite
	for zid in (i for i in ids if i.startswith("zone:")):
		avant = [e["espece"] for e in base[zid].get("defauts_rencontres") or []]
		apres = [e["espece"] for d in docs if d["_id"] == zid for e in d["defauts_rencontres"]]
		assert apres[:len(avant)] == avant, zid  # ajout seul
	base2 = {**base, **{d["_id"]: d for d in docs}}
	assert gen.docs_monstres(base2, _rang_fixe("C"))[0] == []

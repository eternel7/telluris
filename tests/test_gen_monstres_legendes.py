# tests/test_gen_monstres_legendes.py
#
# Générateur `dev/gen_monstres_legendes.py` (bestiaire des légendes du monde, 17/11/2026) : tables
# sources complètes, prompts conformes au gabarit, DELTA seul et rejeu vide. Le rang est injecté
# (`rangs_fn`) : aucun moteur, aucun hasard. Le contrôle sur données réelles lit le dump le plus
# récent par glob (CLAUDE.md §20 : jamais de `*_a_importer.json`).

import glob
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "dev"))
sys.path.insert(0, RACINE)
import gen_monstres_legendes as gen  # noqa: E402

BOSS = {"nuckelavee", "inkanyamba", "gashadokuro", "mngwa", "mokele_mbembe", "roc"}
DONJON_SEUL = {"slime", "mere_gelee", "lapin_cornu"}  # créatures de donjon (Auteur, 17/11)


def _dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	return {d["_id"]: d for d in gen.armure.charger(dumps[-1]) if isinstance(d, dict) and d.get("_id")}


def _rang_fixe(rang):
	return lambda docs: {d["_id"]: rang for d in docs if d.get("type") == "espece"}


def test_tables_sources_couvrent_chaque_espece():
	for slug, spec in gen.NOUVELLES.items():
		assert slug in gen.JETONS, slug
		if "humanoide" in spec["tags"]:
			assert gen.KITS.get(slug), slug
		for c in gen.capacites.ATTRIBUTION.get(slug, []):
			assert c in gen.capacites.COMPETENCES, (slug, c)


def test_boss_et_creatures_de_donjon_hors_des_zones():
	assert not (set(gen.ZONES) & (BOSS | DONJON_SEUL))
	for slug in BOSS:
		assert "boss" in gen.NOUVELLES[slug]["tags"], slug
	assert set(gen.ZONES) | BOSS | DONJON_SEUL == set(gen.NOUVELLES)


def test_qilin_et_baku_fuient():
	for slug in ("qilin", "baku"):
		assert any(t.startswith("ia_fuyard") for t in gen.capacites.IA[slug]), slug


def test_prompt_conforme_au_gabarit():
	for slug in gen.NOUVELLES:
		p = gen.prompt_de(slug)
		assert p.startswith("Réalise l'image d"), slug
		assert p.endswith(gen.STYLE), slug  # bloc 0.1 EN ENTIER (Auteur, 13/10)
		assert "80 %" in p and "pur, sans dégradé" in p, slug


def test_controle_sur_le_dernier_dump():
	base = _dernier_dump()
	assert gen.controler(base) == []


def test_delta_puis_rejeu_vide():
	base = _dernier_dump()
	if any(("espece:" + s) in base for s in gen.NOUVELLES):
		pytest.skip("espèces déjà importées dans ce dump")
	docs, _ = gen.docs_monstres(base, _rang_fixe("C"))
	ids = [d["_id"] for d in docs]
	assert len(ids) == len(set(ids))
	especes = {d["_id"]: d for d in docs if d.get("type") == "espece"}
	assert set(especes) == {"espece:" + s for s in gen.NOUVELLES}
	for slug in gen.NOUVELLES:
		assert ("item:" + slug) in ids, slug  # un butin par défaut par espèce
	# Rejeu sur la base augmentée de la sortie : plus rien à importer.
	base2 = {**base, **{d["_id"]: d for d in docs}}
	assert gen.docs_monstres(base2, _rang_fixe("C"))[0] == []


def test_zones_et_donjons_ajout_seul():
	base = _dernier_dump()
	if any(("espece:" + s) in base for s in gen.NOUVELLES):
		pytest.skip("espèces déjà importées dans ce dump")
	docs, _ = gen.docs_monstres(base, _rang_fixe("C"))
	par_id = {d["_id"]: d for d in docs}
	for zid, zone in par_id.items():
		if not zid.startswith("zone:"):
			continue
		avant = [e["espece"] for e in base[zid].get("defauts_rencontres") or []]
		apres = [e["espece"] for e in zone["defauts_rencontres"]]
		assert apres[:len(avant)] == avant, zid  # rien de retiré ni de réordonné
		assert {k: v for k, v in zone.items() if k != "defauts_rencontres"} == \
			{k: v for k, v in base[zid].items() if k not in ("_rev", "defauts_rencontres")}, zid
	for did in gen.DONJONS:
		for bm in par_id[did]["battle_maps"]:
			assert bm["especes"].count("espece:lapin_cornu") == 1, did
	regions = par_id["rules:regions"]["regions"]
	assert regions["asie"]["lieux"] == [] and regions["ameriques"]["lieux"] == []
	for rid, r in base["rules:regions"]["regions"].items():
		assert regions[rid] == r, rid

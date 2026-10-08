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
	"""Une passive du lot chez une vocation à magie ne peut être qu'un REMPLACEMENT d'une
	passive déjà en base (même `_id`, niveau et mode) : une place réécrite, jamais ajoutée."""
	magiques = {v for v, c in construit["compte"].items() if c["magique"]}
	assert magiques, "rules:vocations ne déclare aucune vocation à magie"
	base = construit["ref"]["competences"]
	for d in construit["lot"]:
		if d["vocation"] in magiques and d["mode"] == "passive":
			ancien = base.get(d["_id"])
			assert ancien is not None and ancien.get("mode") == "passive" \
				and ancien.get("niveau") == d["niveau"], d["_id"]


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


# ── Entrées LIBRES (competences_1_10.L) : remplacements et zones persistantes ─────────

def _entrees_libres(gen):
	return [(voc, e) for voc in sorted(gen.PROFILS) for e in gen.charger_entrees(voc)
			if e["archetype"] == "libre"]


def test_un_remplacement_garde_l_id_d_une_competence_existante(gen, construit):
	"""`remplace` reprend l'`_id` d'une compétence EN BASE (les personnages qui la
	connaissaient reçoivent la nouvelle), au même niveau et dans le même mode."""
	base = construit["ref"]["competences"]
	for voc, e in _entrees_libres(gen):
		if not e["options"].get("remplace"):
			continue
		cid = "competence:" + e["options"]["id"]
		assert cid in base, cid
		assert gen._meme_competence(base[cid], gen.construire_doc(e, voc)), cid


def test_un_remplacement_est_reemis_tant_que_la_base_differe(gen, construit):
	base = construit["ref"]["competences"]
	emis = {d["_id"] for d in construit["a_emettre"]}
	for voc, e in _entrees_libres(gen):
		doc = gen.construire_doc(e, voc)
		if e["options"].get("remplace") and gen._sans_rev(base.get(doc["_id"], {})) != doc:
			assert doc["_id"] in emis, doc["_id"]


def test_zone_persistante_seulement_si_declaree(gen, construit):
	"""Une active `ennemi` à `zone` + `maintien` laisse un MUR à tir ami : elle n'existe dans le
	lot que si sa donnée la déclare (`zone_persistante=True`) — et sans la déclaration, le
	générateur la refuse."""
	declarees = {gen.construire_doc(e, voc)["_id"] for voc, e in _entrees_libres(gen)
				 if e["options"].get("zone_persistante")}
	murs = {d["_id"] for d in construit["lot"]
			if d.get("cible") == "ennemi" and d.get("zone") and d.get("maintien")}
	assert murs == declarees and murs

	import check_competences_doc as check
	mur = next(d for d in construit["lot"] if d["_id"] in murs)
	assert any("ZONE PERSISTANTE" in m for m in check.verifier_competence(mur, "x"))
	assert not any("ZONE PERSISTANTE" in m
				   for m in check.verifier_competence(mur, "x", zone_persistante=True))


# ── Mécaniques du moteur étendu : le lot les EMPLOIE vraiment ──────────────────────

def test_le_lot_emploie_les_mecaniques_du_moteur_etendu(construit):
	"""Provocation, temps formulé (entretien, incantation), saut et lien de vie formulés,
	passives à formule : chacun au moins une fois — sinon le moteur n'est éprouvé par rien."""
	from utils.sorts import est_formule
	lot = construit["lot"]
	assert any((d["effets"].get("provocation")) for d in lot)
	assert any(est_formule(d.get("maintien")) for d in lot)
	assert any(est_formule(d.get("incantation")) for d in lot)
	assert any(est_formule(d["effets"].get("saut")) for d in lot)
	assert any(est_formule((d["effets"].get("lien_vie") or {}).get("part")) for d in lot)
	passives = [d for d in lot if d["mode"] == "passive"]
	assert any(est_formule(v) for d in passives
			   for v in list((d["effets"].get("buffs") or {}).values()) + [d["effets"].get("esquive")])


def test_une_provocation_du_lot_provoque_vraiment(construit, monkeypatch):
	"""Bout en bout : le doc GÉNÉRÉ, normalisé comme en jeu, lancé par le moteur."""
	from utils import combat as combat_mod
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)   # touche, sans critique
	sys.path.insert(0, os.path.join(RACINE, "tests"))
	from _fixtures_magie import combat, joueur, monstre
	from utils.combat import _cible_joueur, resolve_action
	from utils.competences import normaliser_competence
	defi = next(d for d in construit["lot"] if d["effets"].get("provocation") and not d.get("zone"))
	garde = joueur(0, x=5, y=5, nom="Garde")
	mage = joueur(1, x=7, y=5, nom="Mage")
	loup = monstre(x=6, y=6)
	doc = combat([garde, mage], [loup])
	garde["cc"] = 200
	res = resolve_action(doc, "competence", cible_id=loup["id"], competence=normaliser_competence(defi))
	assert "error" not in res, res
	assert _cible_joueur(doc, loup) is garde

# tests/test_direction_textes_lieux.py
# La question d'ouverture et le refus par type du service `direction` parlent de tout lieu de
# la ville, plus seulement des boutiques (dev/gen_direction_textes_lieux.py, rejoué contre le
# DERNIER dump).

import glob
import json
import os

import pytest

from dev import gen_direction_textes_lieux as g
from utils.lint_dialogues import analyser


@pytest.fixture(scope="module")
def dump():
	dumps = sorted(glob.glob(os.path.join(g.RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	with open(dumps[-1], encoding="utf-8") as f:
		return json.load(f)["docs"]


def test_les_textes_ne_se_limitent_plus_aux_boutiques():
	refus = g.TEXTES[g.NOEUD_REFUS]
	assert "magasin" not in refus and "{prenom}" in refus
	demande = g.TEXTES[g.NOEUD_DEMANDE]
	assert "genre de boutique" not in demande
	for mot in ("temple", "auberge", "boutique", "{prenom}"):
		assert mot in demande


def test_seuls_les_deux_textes_changent(dump):
	# Raisonne sur `appliquer` de CHAQUE PNJ à `direction`, et non sur `modifies` : vaut avant
	# comme après import du delta (dump à jour ⇒ `modifies` vide, rien à vérifier).
	portes = [d for d in dump if g.a_direction(d)]
	assert portes
	for d in portes:
		doc = g.appliquer(d)
		vises = g.noeuds_vises(doc)
		assert set(vises) == {g.NOEUD_DEMANDE, doc["services"]["direction"]["noeuds"]["type_inconnu"]}
		for nid, texte in vises.items():
			assert doc["dialogue"]["noeuds"][nid]["texte"] == texte
			doc["dialogue"]["noeuds"][nid]["texte"] = d["dialogue"]["noeuds"][nid]["texte"]
		assert doc == d          # rien d'autre n'a bougé


def test_regeneration_idempotente_et_lint(dump):
	apres = [g.appliquer(d) for d in dump]
	assert g.modifies(apres) == []
	portes = [d for d in apres if g.a_direction(d)]
	assert portes and analyser(portes)["erreurs"] == 0

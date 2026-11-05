# tests/test_direction_type_inconnu.py
# Le refus de la demande PAR TYPE (`type_inconnu`) parle de tout lieu de la ville, plus d'un
# « magasin » (dev/gen_direction_type_inconnu.py, rejoué contre le DERNIER dump).

import glob
import json
import os

import pytest

from dev import gen_direction_type_inconnu as g
from utils.lint_dialogues import analyser


@pytest.fixture(scope="module")
def dump():
	dumps = sorted(glob.glob(os.path.join(g.RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	with open(dumps[-1], encoding="utf-8") as f:
		return json.load(f)["docs"]


def test_le_texte_ne_parle_plus_de_magasin():
	assert "magasin" not in g.TEXTE and "{prenom}" in g.TEXTE


def test_seul_le_texte_du_refus_change(dump):
	avant = {d["_id"]: d for d in dump}
	for doc in g.modifies(dump):
		ref = dict(avant[doc["_id"]])
		ref.pop("_rev", None)
		nid = g.noeud_type_inconnu(doc)
		assert doc["dialogue"]["noeuds"][nid]["texte"] == g.TEXTE
		doc["dialogue"]["noeuds"][nid]["texte"] = ref["dialogue"]["noeuds"][nid]["texte"]
		assert doc == ref


def test_regeneration_idempotente_et_lint(dump):
	apres = [g.appliquer(d) for d in dump]
	assert g.modifies(apres) == []
	portes = [d for d in apres if g.noeud_type_inconnu(d)]
	assert portes and analyser(portes)["erreurs"] == 0

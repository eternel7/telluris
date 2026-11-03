# tests/test_direction_dun_les_places.py
# Milo, Borin et le révérend Malakor indiquent Dun-les-Places (dev/gen_direction_dun_les_places.py),
# rejoué contre le DERNIER dump : réplique de géographie, visible avant / pendant / après l'enquête
# du Morvan — sauf chez Borin pendant sa quête d'apport, où son rappel la dit déjà.

import copy
import glob
import json
import os
import re

import pytest

from dev import gen_direction_dun_les_places as g
from utils import pnj
from utils.lint_dialogues import analyser

MORVAN = "quete:la_bete_de_dun_les_places"


def _dump():
	dumps = sorted(glob.glob(os.path.join(g.RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}


@pytest.fixture(scope="module")
def docs():
	base = _dump()
	return {pid: g.appliquer(copy.deepcopy(base[pid])) for pid in g.DIRECTIONS}


def _visibles(doc, actives=(), reussies=(), flags=None):
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {}}
	return {c["id"] for c in pnj._choix_visibles(doc, doc["dialogue"]["noeud_depart"], contexte)}


def test_passe_le_linter(docs):
	rapport = analyser(list(docs.values()))
	assert rapport["erreurs"] == 0, rapport["trouvailles"]


def test_regeneration_idempotente(docs):
	assert g.modifies(docs) == []


@pytest.mark.parametrize("pid", ["pnj:milo_cartographe", "pnj:reverend_malakor"])
def test_visible_avant_pendant_apres(docs, pid):
	assert g.CHOIX_ID in _visibles(docs[pid])
	assert g.CHOIX_ID in _visibles(docs[pid], actives=[MORVAN])
	assert g.CHOIX_ID in _visibles(docs[pid], reussies=[MORVAN])


def test_borin_le_tait_pendant_son_apport(docs):
	borin = docs["pnj:borin_barbe_de_jais"]
	assert g.CHOIX_ID in _visibles(borin, flags={"apport_en_cours": False})
	assert g.CHOIX_ID not in _visibles(borin, flags={"apport_en_cours": True})
	assert g.CHOIX_ID in _visibles(borin, reussies=[MORVAN], flags={"apport_en_cours": False})


def test_geographie_sans_l_enquete(docs):
	for doc in docs.values():
		texte = doc["dialogue"]["noeuds"][g.NOEUD]["texte"]
		for mot in ("sud-est", "Yonne", "source", "lisière"):
			assert mot in texte, (doc["_id"], mot)
		for mot in ("bête", "loup", "Jacotte"):
			assert mot not in texte, (doc["_id"], mot)


def test_borin_tutoie_et_raconte_au_vous(docs):
	texte = docs["pnj:borin_barbe_de_jais"]["dialogue"]["noeuds"][g.NOEUD]["texte"]
	for replique in re.findall(r"«([^»]*)»", texte):
		assert not re.search(r"\b(vous|votre|vos)\b", replique, re.I)

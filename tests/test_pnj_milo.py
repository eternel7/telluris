# tests/test_pnj_milo.py
# Contenu : Milo à l'auberge de la Tour de l'Horloge. « Passer près de sa table » au PREMIER
# passage seulement ; « la forêt » à partir du DEUXIÈME, et seulement une fois la première
# mission de Borin réussie (condition `passages` en conjonction avec `quete_reussie`).

import json
import os

import pytest

from utils import lint_dialogues, pnj

AUBERGE = "lieu:auberge_de_la_tour_de_l_horloge"
MILO = "pnj:milo_cartographe"
BORIN = "quete:transport_borin_premiere_mission"
CONTENU = os.path.join(os.path.dirname(__file__), "..", "jsons", "pnj_milo_cartographe_a_importer.json")


def _contenu():
	with open(CONTENU, encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)}


def _scenes(passages, quetes_reussies=()):
	"""Les scènes de rencontre (s1, s2) proposées à l'accueil."""
	doc = _contenu()[MILO]
	c = {"passages": {AUBERGE: passages}}
	ctx = pnj.contexte_dialogue(c, doc, lambda _l: 0, quetes_reussies=set(quetes_reussies))
	vue = pnj.noeud_client(doc, "accueil", ctx)
	return [ch["id"] for ch in vue["choix"] if ch["id"] in ("s1", "s2")]


@pytest.mark.parametrize("passages, quetes, attendu", [
	(1, (), ["s1"]),
	(1, (BORIN,), ["s1"]),          # la quête seule n'ouvre pas la forêt dès la 1re visite
	(2, (), []),                    # 2e visite sans la quête : rien
	(2, (BORIN,), ["s2"]),
	(5, (BORIN,), ["s2"]),
])
def test_scene_selon_le_passage(passages, quetes, attendu):
	assert _scenes(passages, quetes) == attendu


def test_libelles_sans_titre():
	choix = {c["id"]: c["label"] for c in _contenu()[MILO]["dialogue"]["noeuds"]["accueil"]["choix"]}
	assert choix["s1"] == "— Passer près de sa table."
	assert choix["s2"] == "— Lui parler de la forêt au-delà de la porte nord."


def test_aucun_relais_dans_le_contenu():
	"""Le jeu n'a pas (encore) de relais : Milo n'en parle pas."""
	with open(CONTENU, encoding="utf-8") as f:
		assert "relais" not in f.read().lower()


def test_le_contenu_passe_le_linter():
	with open(CONTENU, encoding="utf-8") as f:
		rapport = lint_dialogues.analyser(json.load(f))
	assert rapport["erreurs"] == 0, rapport["trouvailles"]

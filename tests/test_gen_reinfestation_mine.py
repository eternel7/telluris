# tests/test_gen_reinfestation_mine.py — dev/gen_reinfestation_mine.py : injection ciblée,
# idempotente, et dialogue qui passe le linter.

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_reinfestation_mine as gen  # noqa: E402
from utils import lint_dialogues  # noqa: E402

ARMAND = {
	"_id": gen.ARMAND_ID, "type": "pnj", "nom": "Armand",
	"dialogue": {"noeud_depart": "accueil", "noeuds": {
		"accueil": {"texte": "« Les papiers. »", "choix": [
			{"id": "mineurs", "label": gen.LABEL_MINEURS, "condition": {"acces_menace": True},
			 "next": "mineurs"},
			{"id": "mineurs_libres", "label": gen.LABEL_MINEURS,
			 "condition": {"acces_libere": True}, "next": "mineurs_libres"},
			{"id": "pourquoi", "label": gen.LABEL_POURQUOI, "condition": {"acces_refuse": True},
			 "next": "acces_refus"},
			{"id": "rien", "label": "Rien.", "next": "fin"},
		]},
		"acces_refus": {"texte": "…", "choix": [{"id": "r", "label": "Revenir.", "next": "accueil"}]},
		"mineurs": {"texte": "…", "choix": [{"id": "r", "label": "Revenir.", "next": "accueil"}]},
		"mineurs_libres": {"texte": "…", "choix": [{"id": "r", "label": "Revenir.", "next": "accueil"}]},
	}},
}


def test_armand_premiere_infestation_et_jumeau_reinfeste():
	doc = gen.maj_armand(ARMAND)
	choix = {c["id"]: c for c in doc["dialogue"]["noeuds"]["accueil"]["choix"]}
	assert choix["mineurs"]["condition"] == {"acces_menace": True, "acces_reinfeste": False}
	assert choix["mineurs_remontes"]["condition"] == {"acces_reinfeste": True}
	ids = [c["id"] for c in doc["dialogue"]["noeuds"]["accueil"]["choix"]]
	assert ids.index("mineurs_remontes") == ids.index("mineurs") + 1
	assert "mineurs_remontes" in doc["dialogue"]["noeuds"]
	assert ARMAND["dialogue"]["noeuds"]["accueil"]["choix"][0]["condition"] == {"acces_menace": True}


def test_refus_dedouble_selon_l_etat_de_la_mine():
	doc = gen.maj_armand(ARMAND)
	choix = {c["id"]: c for c in doc["dialogue"]["noeuds"]["accueil"]["choix"]}
	assert choix["pourquoi"]["condition"] == {"acces_refuse": True, "acces_libere": False}
	assert choix["pourquoi_libre"]["condition"] == {"acces_refuse": True, "acces_libere": True}
	assert choix["pourquoi_libre"]["next"] == "acces_refus_libre"
	assert "acces_refus_libre" in doc["dialogue"]["noeuds"]


def test_regeneration_idempotente():
	une = gen.maj_armand(ARMAND)
	assert gen.maj_armand(une) == une
	mine = gen.maj_mine({"_id": gen.MINE_ID})
	assert gen.maj_mine(mine) == mine == {"_id": gen.MINE_ID, "reinfestation": True}


def test_l_ajout_n_introduit_aucune_faute_de_lint():
	# La fixture est un arbre réduit (le linter y trouve ses propres manques) : on vérifie que
	# le générateur n'en AJOUTE aucune — flag inconnu, nœud orphelin, `next` cassé.
	avant = lint_dialogues.analyser_doc(ARMAND)
	assert lint_dialogues.analyser_doc(gen.maj_armand(ARMAND)) == avant

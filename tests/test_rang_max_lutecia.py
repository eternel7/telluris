# tests/test_rang_max_lutecia.py
# Le Grand Relais (Lutecia) délivre toute l'échelle : son comptoir porte le sommet de RANGS, et
# Éléonore ne renvoie plus vers « la guilde d'une autre cité » (dev/gen_rang_max_lutecia.py).

import json
import os

from utils import chasse
from utils.recrutement import RANGS

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPORT = os.path.join(RACINE, "jsons", "rang_max_lutecia_a_importer.json")
SOURCES = ["maelys_maitresse_de_guilde_a_importer.json", "correctifs_dialogues_a_importer.json"]


def _docs(chemin):
	with open(chemin, encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)}


def test_le_comptoir_de_lutecia_delivre_toute_l_echelle():
	comptoir = _docs(IMPORT)["lieu:le_grand_relais_des_frontieres_comptoir"]
	assert chasse.rang_max_de(comptoir) == RANGS[-1]
	for rang in RANGS[:-1]:
		assert not chasse.rang_plafond_atteint(rang, comptoir)
	assert chasse.rang_plafond_atteint(RANGS[-1], comptoir)


def test_eleonore_ne_renvoie_plus_vers_une_autre_cite():
	textes = [_docs(IMPORT)["pnj:eleonore_de_vaugirard"]["dialogue"]["noeuds"]["rang_sommet"]["texte"]]
	textes += [_docs(os.path.join(RACINE, "jsons", s))["pnj:eleonore_de_vaugirard"]
			   ["dialogue"]["noeuds"]["rang_sommet"]["texte"] for s in SOURCES]
	assert len(set(textes)) == 1
	assert "autre cité" not in textes[0]

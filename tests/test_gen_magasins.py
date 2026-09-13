"""dev/gen_magasins.py — le lot de magasins décrit par une spec JSON (outil de /admin/lieux).

Verrouille ce qu'un import PUT COMPLET rendrait silencieux : un `_id` réémis écrase, un
tenancier inexistant laisse une référence morte, une case infranchissable pose une boutique
que personne n'atteint.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_magasins import construire, slug_lieu

# Une cité 4×3 : colonne 0 = mur, [1,1] = terrain difficile, le reste libre.
CITE = {
	"_id": "lieu:ville", "type": "lieu", "label": "Ville",
	"cells": [
		[0, 1, 1, 1],
		[0, 2, 1, 1],
		[0, 1, 1, 1],
	],
}
FORGE = {"_id": "lieu:la_forge", "type": "lieu", "categorie": "armurerie", "lieu_parent": "lieu:ville"}
LIEN_FORGE = {
	"_id": "link:armurerie03_to_ville", "type": "connection",
	"nodes": [{"lieu": "lieu:ville", "pos": [2, 2]}, {"lieu": "lieu:la_forge", "pos": [0, 0]}],
	"metadata": {"type": "armurerie", "status": "ouvert"},
}
TENANCIER = {"_id": "pnj:marchand_armurerie", "type": "pnj"}
DOCS = [CITE, FORGE, LIEN_FORGE, TENANCIER]


def spec(*magasins):
	return {"cite": "lieu:ville", "magasins": list(magasins)}


def test_slug_suit_la_regle_de_l_editeur():
	assert slug_lieu("Au Cheval Blanc d'Été") == "au_cheval_blanc_d_ete"


def test_auberge_sans_tenancier_ni_reference_morte():
	res = construire(DOCS, spec({"categorie": "auberge", "label": "Au Cheval Blanc",
								 "image": "auberge_europe01.png", "pos": [3, 0]}),
					 {"auberge_europe01.png"})
	assert res["erreurs"] == []
	lieu, lien = res["docs"]
	assert lieu == {
		"_id": "lieu:au_cheval_blanc", "type": "lieu", "label": "Au Cheval Blanc",
		"image": "auberge_europe01.png", "categorie": "auberge", "lieu_parent": "lieu:ville",
		"stock_matieres": {}, "stock_vente": [],
	}
	assert lien == {
		"_id": "link:auberge01_to_ville", "type": "connection",
		"nodes": [{"lieu": "lieu:ville", "pos": [3, 0]}, {"lieu": "lieu:au_cheval_blanc", "pos": [0, 0]}],
		"metadata": {"type": "auberge", "status": "ouvert"},
	}


def test_tenancier_generique_pose_s_il_existe_et_numero_suit_l_existant():
	res = construire(DOCS, spec(
		{"categorie": "armurerie", "label": "L'Enclume", "image": "x.png", "pos": [3, 1], "nom": "Gus"},
		{"categorie": "armurerie", "label": "Le Marteau", "image": "x.png", "pos": [3, 2]},
	), set())
	assert res["erreurs"] == []
	ids = [d["_id"] for d in res["docs"]]
	assert ids == ["lieu:l_enclume", "link:armurerie04_to_ville", "lieu:le_marteau", "link:armurerie05_to_ville"]
	assert res["docs"][0]["pnj"] == [{"character": "pnj:marchand_armurerie", "nom": "Gus"}]
	assert res["images_manquantes"] == ["x.png", "x.png"]


def test_un_seul_refus_annule_tout_le_lot():
	res = construire(DOCS, spec(
		{"categorie": "auberge", "label": "Bonne", "image": "a.png", "pos": [3, 0]},
		{"categorie": "auberge", "label": "Sur le mur", "image": "a.png", "pos": [0, 0]},
	), set())
	assert res["docs"] == []
	assert len(res["erreurs"]) == 1 and "terrain 0" in res["erreurs"][0]


def test_terrain_difficile_refuse_car_hors_des_fleches():
	res = construire(DOCS, spec({"categorie": "auberge", "label": "A", "image": "a.png", "pos": [1, 1]}), set())
	assert "terrain 2" in res["erreurs"][0]


def test_refus_collision_d_id_et_doublon_dans_la_spec():
	res = construire(DOCS, spec({"categorie": "auberge", "label": "La Forge", "image": "a.png", "pos": [3, 0]}), set())
	assert "lieu:la_forge existe déjà" in res["erreurs"][0]
	res = construire(DOCS, spec(
		{"categorie": "auberge", "label": "Deux", "image": "a.png", "pos": [3, 0]},
		{"categorie": "tannerie", "label": "Deux", "image": "a.png", "pos": [3, 1]},
	), set())
	assert res["docs"] == [] and "lieu:deux existe déjà" in res["erreurs"][0]


def test_refus_meme_metier_sur_la_meme_case_mais_pas_un_autre():
	res = construire(DOCS, spec({"categorie": "armurerie", "label": "B", "image": "a.png", "pos": [2, 2]}), set())
	assert "porte déjà un magasin « armurerie »" in res["erreurs"][0]
	res = construire(DOCS, spec({"categorie": "auberge", "label": "B", "image": "a.png", "pos": [2, 2]}), set())
	assert res["erreurs"] == []


def test_refus_pos_absente_hors_grille_et_cite_inconnue():
	assert "`pos`" in construire(DOCS, spec({"categorie": "a", "label": "A", "image": "a"}), set())["erreurs"][0]
	assert "hors de la grille" in construire(
		DOCS, spec({"categorie": "a", "label": "A", "image": "a", "pos": [9, 0]}), set())["erreurs"][0]
	assert "Cité introuvable" in construire(DOCS, {"cite": "lieu:nulle", "magasins": [{}]}, set())["erreurs"][0]


def test_tags_et_nuit_messages_optionnels():
	res = construire(DOCS, spec({"categorie": "halte", "label": "H", "image": "a.png", "pos": [3, 0],
								 "tags": ["taverne"], "nuit_messages": ["La salle se vide."]}), set())
	lieu = res["docs"][0]
	assert lieu["tags"] == ["taverne"] and lieu["nuit_messages"] == ["La salle se vide."]
	assert "pnj" not in lieu

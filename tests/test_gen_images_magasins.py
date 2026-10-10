"""dev/gen_images_magasins.py — portraits des tenanciers, façades de boutique et d'auberge
(Gemini, repli ComfyUI).

Partie pure seulement. Verrouille ce qui ferait passer le lot à vide ou le rendrait faux en
silence : une catégorie ou un toponyme sans traduction (KeyError au milieu du lot, ou rue
générique), un nom propre dans le prompt (peint en enseigne), une base d'image qui écraserait
une image générique partagée, une façade soumise avant le portrait qu'elle joint.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_images_magasins import (AGES, ALLURES, CHEVEUX, CORPS, LIGNEES, LIGNEES_EN, METIERS,
	METIERS_EN, QUARTIERS_AUBERGES, QUARTIERS_EN, RATIO, TRAITS_EN, base_image, entrees_de_cite,
	image_de_reponse, image_degeneree, prompt_auberge, prompt_magasin, prompt_tenancier, quartier_de,
	requete_gemini, requetes_faisables, tirage_tenancier, traits_en)
from utils.enseignes import TOPONYMES_PAR_LIEU


def test_chaque_metier_du_portrait_a_sa_boutique():
	assert set(METIERS_EN) == set(METIERS)


def test_chaque_lignee_du_portrait_a_sa_traduction():
	assert set(LIGNEES_EN) == set(LIGNEES)


def test_chaque_toponyme_de_reims_a_son_decor():
	# Relu dans enseignes : un toponyme ajouté sans décor casserait ce test, pas le lot.
	for cite in ("lieu:rhemi", "lieu:chartres"):
		assert set(QUARTIERS_EN[cite]) == set(TOPONYMES_PAR_LIEU[cite]), cite


def test_chaque_trait_tire_a_sa_traduction():
	for liste in (AGES, CORPS, CHEVEUX, ALLURES):
		for gabarit in liste:
			assert gabarit in TRAITS_EN, gabarit


def test_portrait_au_style_et_aux_regles_des_facades():
	# Consignes de l'auteur (09/10) : style d'Auxerre, foule variée, ogres jamais verts, pas de nom.
	prompt = prompt_tenancier("ogre", "M", "boulangerie", "Reims", tirage_tenancier(random.Random(0)))
	assert "pas une photographie" in prompt
	assert "photoréaliste" not in prompt
	assert "Telluris" not in prompt
	assert "jamais verts" in prompt  # la foule
	assert "jamais verte" in prompt  # le tenancier ogre
	assert "Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation" in prompt


def test_portrait_accorde_au_sexe():
	tirage = ["âgé{e}", "bedonnant{e}", "aux cheveux gris", "l'air rusé"]
	assert "Une naine âgée, bedonnante, aux cheveux gris, l'air rusé" in prompt_tenancier("nain", "F", "etable", "Chartres", tirage)
	assert "Un nain âgé, bedonnant, aux cheveux gris, l'air rusé" in prompt_tenancier("nain", "M", "etable", "Chartres", tirage)


def test_traits_inconnus_ignores():
	assert traits_en(["jeune", "trait inventé"]) == ["young"]
	assert traits_en(None) == []


def test_aucun_nom_propre_dans_le_prompt():
	label = "L'Arc Vert des Coteaux"
	prompt = prompt_magasin("fletcher", "hobbit", "M", ["young"], "lieu:rhemi", "Reims", label)
	assert "Arc Vert" not in prompt
	assert "Fastolf" not in prompt
	assert "Telluris" not in prompt  # peint en enseigne à l'essai du 08/10
	assert "vineyard" in prompt
	assert "barefoot" in prompt
	# Pas de prompt négatif avec Z-Image Turbo : l'interdiction du texte est dans le prompt.
	assert "No text" in prompt
	# Le portrait vend face à nous ; la boutique le montre au travail (consigne du 09/10).
	assert "NOT the same pose" in prompt
	assert "not looking at the camera" in prompt


def test_quartier_par_suffixe_du_label():
	assert quartier_de("Le Livre des Morts de la Vesle", "lieu:rhemi") == "de la Vesle"
	assert quartier_de("L'Enclume de la Porte de Mars", "lieu:rhemi") == "de la Porte de Mars"
	assert quartier_de("La Coupe aux Herbes du Vieux Cloître", "lieu:rhemi") == "du Vieux Cloître"
	assert quartier_de("Boutique sans quartier", "lieu:rhemi") is None
	prompt = prompt_magasin("cuisine", "elfe", "F", [], "lieu:rhemi", "Reims", "Boutique sans quartier")
	assert "walled city of Reims" in prompt


def test_image_ratee_par_le_gpu_rejetee():
	# Mesures relevées le 08/10 sur de vraies images (cf. étalonnage dans le module).
	assert image_degeneree(4.5, 0.0) == "uniforme"
	assert image_degeneree(59.5, 45.7) == "bruit"
	assert image_degeneree(67.2, 6.1) is None
	assert image_degeneree(50.4, 10.0) is None  # cuisine_europe01.jpg, déjà en jeu


def test_base_image_propre_a_la_cite():
	assert base_image("archerie_europe01.png", "lieu:rhemi") == "archerie_europe_rhemi"
	assert base_image("negoce_europe01.jpg", "lieu:rhemi") == "negoce_europe_rhemi"
	assert base_image("armurerie_europe05.png", "lieu:rhemi") == "armurerie_europe_rhemi"
	assert base_image("cabinet_alchimie_europe02.png", "lieu:rhemi") == "cabinet_alchimie_europe_rhemi"


def test_requete_gemini_portrait_avant_le_texte():
	# Le prompt désigne le tenancier comme « image 1 » : l'image doit précéder le texte.
	r = requete_gemini("prompt", "QUJD")
	parts = r["contents"][0]["parts"]
	assert parts[0] == {"inlineData": {"mimeType": "image/jpeg", "data": "QUJD"}}
	assert parts[1] == {"text": "prompt"}
	assert r["generationConfig"]["responseModalities"] == ["IMAGE"]
	assert r["generationConfig"]["imageConfig"]["aspectRatio"] == RATIO


def test_requete_gemini_sans_image_pour_une_auberge():
	assert requete_gemini("prompt")["contents"][0]["parts"] == [{"text": "prompt"}]


def test_auberge_sans_nom_propre_et_dans_son_quartier():
	prompt = prompt_auberge("lieu:rhemi", "Reims", QUARTIERS_AUBERGES["lieu:la_crayere"])
	assert "Crayère" not in prompt
	assert "Telluris" not in prompt
	assert QUARTIERS_EN["lieu:rhemi"]["des Crayères"] in prompt
	assert "No text" in prompt
	assert "walled city of Reims" in prompt_auberge("lieu:rhemi", "Reims", None)


def test_quartiers_d_auberge_connus():
	toponymes = {t for q in QUARTIERS_EN.values() for t in q}
	for q in QUARTIERS_AUBERGES.values():
		assert q in toponymes, q
	assert quartier_de("Auberge du Sacre", "lieu:rhemi") == "du Sacre"


def test_image_lue_dans_une_reponse_gemini():
	part = {"inlineData": {"mimeType": "image/jpeg", "data": "QUJD"}}
	rep = {"candidates": [{"content": {"parts": [{"text": "voici"}, part]}}]}
	assert image_de_reponse(rep) is part
	assert image_de_reponse({"candidates": [{"finishReason": "SAFETY"}]}) is None
	assert image_de_reponse(None) is None


def _lieux():
	return {
		"lieu:la_lame_du_tertre": {"lieu_parent": "lieu:chartres", "categorie": "armurerie",
			"label": "La Lame du Tertre", "image": "armurerie_europe01.jpg",
			"pnj": [{"nom": "Gorm", "portrait": "marchand_humain_m_armurerie.png"}]},
		"lieu:aux_deux_fleches": {"lieu_parent": "lieu:chartres", "categorie": "auberge",
			"label": "Aux Deux Flèches", "image": "auberge_europe01.png"},
		"lieu:portrait_fait_main": {"lieu_parent": "lieu:chartres", "categorie": "armurerie",
			"label": "X", "image": "a.png", "pnj": [{"portrait": "Elise.jpg"}]},
		"lieu:ailleurs": {"lieu_parent": "lieu:rhemi", "categorie": "auberge", "image": "a.png"},
	}


def test_entrees_portrait_et_facade_de_la_meme_personne():
	entrees, ignores = entrees_de_cite(_lieux(), "lieu:chartres", "Chartres")
	assert [e["key"] for e in entrees] == ["lieu:aux_deux_fleches", "lieu:la_lame_du_tertre"]
	assert len(ignores) == 1 and "portrait_fait_main" in ignores[0]
	auberge, boutique = entrees
	assert auberge["portrait"] is None
	assert auberge["image"]["base"] == "auberge_europe_chartres"
	assert QUARTIERS_EN["lieu:chartres"]["du Cloître"] in auberge["image"]["prompt"]
	assert boutique["portrait"]["base"] == "marchand_humain_m_armurerie"
	assert boutique["image"]["base"] == "armurerie_europe_chartres"
	# Les traits tirés pour le portrait sont ceux que la façade redit.
	assert ", ".join(boutique["tirage"]).replace("{e}", "").replace("{he}", "") in boutique["portrait"]["prompt"]
	assert ", ".join(traits_en(boutique["tirage"])) in boutique["image"]["prompt"]
	assert "Gorm" not in boutique["portrait"]["prompt"] + boutique["image"]["prompt"]
	# Graine propre au lieu : re-préparer, même avec une cité autrement peuplée, redonne le même tirage.
	seul = {"lieu:la_lame_du_tertre": _lieux()["lieu:la_lame_du_tertre"]}
	assert entrees_de_cite(seul, "lieu:chartres", "Chartres")[0][0]["tirage"] == boutique["tirage"]


def test_facade_d_une_boutique_attend_son_portrait():
	entrees, _ = entrees_de_cite(_lieux(), "lieu:chartres", "Chartres")
	man = {"entrees": entrees, "portraits": {}, "images": {}}
	assert [c for c, _, _ in requetes_faisables(man)] == [
		"image|lieu:aux_deux_fleches", "portrait|lieu:la_lame_du_tertre"]
	man["images"]["lieu:aux_deux_fleches"] = "auberge_europe_chartres01.jpg"
	man["portraits"]["lieu:la_lame_du_tertre"] = "marchand_humain_m_armurerie01.jpg"
	assert [c for c, _, _ in requetes_faisables(man)] == ["image|lieu:la_lame_du_tertre"]
	man["images"]["lieu:la_lame_du_tertre"] = "armurerie_europe_chartres01.jpg"
	assert requetes_faisables(man) == []

"""dev/gen_images_magasins.py — façades de boutique générées par ComfyUI.

Partie pure seulement. Verrouille ce qui ferait passer le lot à vide ou le rendrait faux en
silence : une catégorie ou un toponyme sans traduction (KeyError au milieu du lot, ou rue
générique), un nom propre dans le prompt (peint en enseigne), une base d'image qui écraserait
une image générique partagée.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_images_magasins import (LIGNEES_EN, METIERS_EN, QUARTIERS_EN, TRAITS_EN, base_image,
	image_degeneree, prompt_magasin, quartier_de, traits_du_portrait)
from dev.gen_portraits_batch import AGES, ALLURES, CHEVEUX, CORPS, LIGNEES, METIERS, prompt_tenancier
from utils.enseignes import TOPONYMES_PAR_LIEU


def test_chaque_metier_du_portrait_a_sa_boutique():
	assert set(METIERS_EN) == set(METIERS)


def test_chaque_lignee_du_portrait_a_sa_traduction():
	assert set(LIGNEES_EN) == set(LIGNEES)


def test_chaque_toponyme_de_reims_a_son_decor():
	# Relu dans enseignes : un toponyme ajouté sans décor casserait ce test, pas le lot.
	assert set(QUARTIERS_EN["lieu:rhemi"]) == set(TOPONYMES_PAR_LIEU["lieu:rhemi"])


def test_chaque_trait_tire_a_sa_traduction():
	for liste in (AGES, CORPS, CHEVEUX, ALLURES):
		for gabarit in liste:
			assert gabarit in TRAITS_EN, gabarit


def test_traits_relus_dans_un_vrai_prompt_de_portrait():
	for race in LIGNEES:
		for sexe in ("M", "F"):
			for graine in range(20):
				rng = random.Random(graine)
				prompt = prompt_tenancier(race, sexe, "fletcher", "Reims", random.Random(graine))
				# Même tirage, même ordre que prompt_tenancier : âge, corps, cheveux, allure.
				attendus = [TRAITS_EN[rng.choice(AGES)], TRAITS_EN[rng.choice(CORPS)],
							TRAITS_EN[rng.choice(CHEVEUX)], TRAITS_EN[rng.choice(ALLURES)]]
				assert traits_du_portrait(prompt) == attendus, (race, sexe, prompt)


def test_prompt_meconnaissable_sans_traits():
	assert traits_du_portrait(None) == []
	assert traits_du_portrait("Portrait fait à la main") == []


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

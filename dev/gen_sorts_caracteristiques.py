#!/usr/bin/env python
"""Sorts à FORMULES DE CARACTÉRISTIQUES : leur puissance lit le lanceur (`1D{Int/5}`).

    python dev/gen_sorts_caracteristiques.py [--dump jsons/telluris-dump-*.json] [--sortie …]

Sortie : jsons/sorts_caracteristiques_a_importer.json (carte d'import de /admin), dans cet
ordre : les `sort:*` neufs, une animation DÉDIÉE `animation:sc_<sort>` par sort (sprite +
son), puis le grimoire UNIQUE et la recette de scriptorium de chacun
(`utils/grimoires.grimoires_manquants` — sans grimoire, un sort ne s'apprend pas).

POURQUOI. Le moteur résout désormais les jetons `{Car}` / `{Car/n}` au lancement
(`utils/sorts.resoudre_effets`) : dés, soin (`soin`), buffs, durée, régén, coût en PV,
partage de soin et portée peuvent dépendre de la caractéristique EFFECTIVE du lanceur.
Ces sorts couvrent les niveaux 0 à 10 des sept écoles. Règles : compétence telluris-magie
§ Formules à caractéristiques.

ANIMATIONS. Chaque `animation:sc_<sort>` RECOPIE la découpe (feuille, grille, plage
d'images, sens) d'une animation de base DÉJÀ ACTIVE du dump — les feuilles sont trop
hétérogènes pour être retapées — et y pose son son, son volume et sa trajectoire. Aucune
animation existante n'est modifiée. ⚠️ Les feuilles ont été choisies sur leur NOM : chacune
se vérifie à l'aperçu de /admin/animations après import.

GARDES — une violation arrête tout, rien n'est écrit :
  · l'école de chaque sort est la `magie` d'une vocation de `rules:vocations` ;
  · chaque composant est un `item:*` du dump ; chaque sort a un consommé ET un catalyseur ;
  · l'animation de base existe et est active ; le son existe dans templates/resources/sounds ;
  · un `_id` déjà pris par un doc DIFFÉRENT fait tout refuser ; déjà importé (champs produits identiques, base éventuellement enrichie : ) ⇒ sauté.
"""

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
DOSSIER_SONS = os.path.join(RACINE, "templates", "resources", "sounds")
SORTIE = os.path.join(DOSSIER_JSONS, "sorts_caracteristiques_a_importer.json")

from utils import grimoires  # noqa: E402

# Champs d'une animation de base RECOPIÉS tels quels : la découpe de la feuille.
CLES_DECOUPE = ("fichier", "largeur", "hauteur", "colonnes", "lignes", "sens_lignes",
				"sens_colonnes", "debut", "fin", "duree_ms", "echelle", "decalage_x",
				"decalage_y", "ancrage", "rotation")


def _c(item, consomme, bonus):
	return {"item": "item:" + item, "consomme": consomme, "bonus": bonus}


def _anim(base, son, volume, fin_ms=0, **trajet):
	return {"base": "animation:" + base, "son": son, "son_volume": volume,
			"son_fin_ms": fin_ms, "trajet": trajet}


# Trajectoire d'un projectile : part de l'acteur, s'oriente vers la cible.
PROJECTILE = {"depart_ancrage": "acteur", "rotation_auto": True}

# ⚠️ Le CATALYSEUR précède le consommé dans chaque liste (règle de contenu : le lien de vie
# serait écrasé par le dernier composant engagé — on garde l'habitude partout).
SORTS = [
	# ── Niveaux 0 à 2 — sorts d'entrée ─────────────────────────────────────────
	{"slug": "dard_de_l_esprit", "nom": "Dard de l'esprit", "icon": "🗡️",
	 "magie": "Bataille", "niveau": 0, "cout_pm": 7, "cible": "ennemi", "portee": "3+{Int/20}",
	 "effets": {"degats": "1D{Int/5}"},
	 "description": "Une aiguille de pensée pure, aussi acérée que l'esprit qui la forge. "
					"Plus le mage est savant, plus le dard est long — et plus il porte loin.",
	 "composants": [_c("Cristal_canalisation", False, {"degats": "1"}),
					_c("poudre_alchimique", True, {"degats": "1D4"})],
	 "anim": _anim("spritesheet_512px_by197px_per_frame_cyan_a", "swish_3.wav", 0.7,
				   duree_trajet_ms=300, **PROJECTILE)},
	{"slug": "imposition_des_mains", "nom": "Imposition des mains", "icon": "🙌",
	 "magie": "Sainte", "niveau": 0, "cout_pm": 9, "cible": "allie", "portee": 1,
	 "effets": {"soin": "1D6+{Vol/10}", "partage_soin": 25},
	 "description": "Les paumes posées sur la plaie, le prêtre prie. La grâce qui referme la "
					"chair de l'autre lui revient un peu, comme une chaleur dans les mains.",
	 "composants": [_c("encens", False, {"soin": "2"}),
					_c("Bougie_de_veille", False, {"partage_soin": 10}),
					_c("Eau_benite", True, {"soin": "1D6"})],
	 "anim": _anim("light_glow_effect_a", "power_up_sound_v0.ogg", 0.7)},
	{"slug": "peau_de_pierre", "nom": "Peau de pierre", "icon": "🪨",
	 "magie": "Élémentaire", "niveau": 0, "cout_pm": 9, "cible": "soi", "portee": 0,
	 "effets": {"buffs": {"R": "{Vol/5}"}, "duree": "1+{Vol/20}"},
	 "description": "La peau grisonne et se fendille comme une roche au soleil. Une volonté "
					"ferme fait une pierre dure, et qui tient longtemps.",
	 "composants": [_c("Cristal_canalisation", False, {"buffs": {"R": 5}}),
					_c("Sel_gemme", True, {"duree": 2})],
	 "anim": _anim("shards01_a", "power_up_sound_v2.ogg", 0.6)},
	{"slug": "lance_de_foudre", "nom": "Lance de foudre", "icon": "⚡",
	 "magie": "Élémentaire", "niveau": 1, "cout_pm": 11, "cible": "ennemi", "portee": 7,
	 "effets": {"degats": "2D{Int/6}"},
	 "description": "Un trait d'éclair jeté comme une javeline. Le savoir du mage fixe la "
					"tension de l'orage qu'il emprunte.",
	 "composants": [_c("Cristal_canalisation", False, {"degats": "1"}),
					_c("poudre_alchimique", True, {"degats": "1D6"})],
	 "anim": _anim("shock_a", "17.mp3", 0.8, duree_trajet_ms=250, **PROJECTILE)},
	{"slug": "chatiment_du_juste", "nom": "Châtiment du juste", "icon": "☀️",
	 "magie": "Sainte", "niveau": 1, "cout_pm": 10, "cible": "ennemi", "portee": 4,
	 "effets": {"degats": "1D8+{Vol/10}"},
	 "description": "Une lumière tombe du ciel sur l'impie. Elle frappe d'autant plus fort que "
					"la foi qui l'appelle est inébranlable.",
	 "composants": [_c("encens", False, {"degats": "1"}),
					_c("Eau_benite", True, {"degats": "1D4"})],
	 "anim": _anim("16_sunburn_spritesheet_a", "power_up_sound_v3.ogg", 0.8)},
	{"slug": "seve_vive", "nom": "Sève vive", "icon": "🌿",
	 "magie": "Nature", "niveau": 1, "cout_pm": 10, "cible": "allie", "portee": 3,
	 "effets": {"soin": "2D4+{Vol/10}", "regen_pv": "{Vol/20}", "duree": 3,
				"partage_soin": "{Vol/4}"},
	 "description": "La sève monte dans le corps du blessé et circule entre lui et le druide : "
					"ce qui guérit l'un nourrit un peu l'autre.",
	 "composants": [_c("Seve_de_chene", False, {"soin": "2"}),
					_c("Herbes_medicinales", True, {"soin": "1D6"})],
	 "anim": _anim("green_effect_a", "swamp.ogg", 0.6, fin_ms=1200)},
	{"slug": "ponction_d_ame", "nom": "Ponction d'âme", "icon": "🌑",
	 "magie": "Nécromancie", "niveau": 1, "cout_pm": 11, "cible": "ennemi", "portee": 5,
	 "effets": {"degats": "1D{Vol/5}", "drain_pv": 50},
	 "description": "Un fil d'ombre arrache à la victime un peu de ce qui la fait vivre, et le "
					"nécromant s'en abreuve.",
	 "composants": [_c("os", False, {"degats": "1"}),
					_c("Fiole_de_sang_fige", True, {"degats": "1D4"})],
	 "anim": _anim("18_midnight_spritesheet_a", "swish_2.wav", 0.7)},
	{"slug": "migraine", "nom": "Migraine", "icon": "🌀",
	 "magie": "Illusoire", "niveau": 1, "cout_pm": 9, "cible": "ennemi", "portee": 6,
	 "effets": {"degats": "1D4", "degats_pm": "1D{Int/5}"},
	 "description": "Une douleur sourde derrière les yeux, une pensée qui se dérobe. Contre un "
					"sorcier, c'est sa magie qui s'écoule.",
	 "composants": [_c("Plume_d_oie", False, {"degats_pm": "1"}),
					_c("Poudre_de_miroir", True, {"degats_pm": "1D4"})],
	 "anim": _anim("13_vortex_spritesheet_a", "17.mp3", 0.5)},
	{"slug": "fouet_de_domination", "nom": "Fouet de domination", "icon": "🔗",
	 "magie": "Démonologie", "niveau": 1, "cout_pm": 10, "cible": "ennemi", "portee": 3,
	 "effets": {"degats": "1D{Vol/5}+{Cha/10}", "buffs": {"Vol": "-{Cha/5}"}, "duree": 2},
	 "description": "Une lanière de feu noir claque, et avec elle la voix du démoniste : la "
					"victime saigne et plie.",
	 "composants": [_c("Sel_noir", False, {"degats": "1"}),
					_c("Sang_demon_seche", True, {"degats": "1D4"})],
	 "anim": _anim("17_felspell_spritesheet_a", "swish_4.wav", 0.8)},
	{"slug": "lame_de_l_escrimeur_mage", "nom": "Lame de l'escrimeur-mage", "icon": "🤺",
	 "magie": "Bataille", "niveau": 1, "cout_pm": 9, "cible": "ennemi", "portee": 1,
	 "effets": {"degats": "1D6+{Ag/10}"},
	 "description": "Une lame de force se forme au bout des doigts. Elle ne vaut que ce que "
					"vaut le poignet qui la conduit.",
	 "composants": [_c("Pierre_a_aiguiser", False, {"degats": "1"}),
					_c("poudre_alchimique", True, {"degats": "1D4"})],
	 "anim": _anim("spritesheet_512px_by197px_per_frame_pink_a", "sword sound.wav", 0.8)},
	{"slug": "boule_de_feu_savante", "nom": "Boule de feu savante", "icon": "🔥",
	 "magie": "Élémentaire", "niveau": 2, "cout_pm": 16, "cible": "ennemi", "portee": 6,
	 "zone": {"forme": "cercle", "origine": "cible", "rayon": 1},
	 "effets": {"degats": "1D{Int/4}+{Int/10}"},
	 "description": "Une sphère de flammes calculée au pouce près : l'érudit sait exactement "
					"où elle éclatera, et combien elle brûlera.",
	 "composants": [_c("Cristal_canalisation", False, {"degats": "2"}),
					_c("Soufre", True, {"degats": "1D6"})],
	 "anim": _anim("9_brightfire_spritesheet_a", "foom_0.wav", 0.9,
				   duree_trajet_ms=400, arc=1, **PROJECTILE)},
	{"slug": "priere_de_communion", "nom": "Prière de communion", "icon": "🕯️",
	 "magie": "Sainte", "niveau": 2, "cout_pm": 15, "cible": "soi", "portee": 0,
	 "zone": {"forme": "cercle", "origine": "lanceur", "rayon": 2},
	 "effets": {"soin": "1D6+{Vol/15}", "partage_soin": 20},
	 "description": "Le prêtre prie à voix haute et tous ceux qui l'entourent sont relevés ; "
					"leur gratitude lui revient en force.",
	 "composants": [_c("Bougie", False, {"soin": "1"}),
					_c("Eau_benite", True, {"soin": "1D4"})],
	 "anim": _anim("aura38_a", "power_up_sound_v1.ogg", 0.7)},
	{"slug": "sang_pour_sang", "nom": "Sang pour sang", "icon": "🩸",
	 "magie": "Nécromancie", "niveau": 2, "cout_pm": 14, "cible": "soi", "portee": 0,
	 "effets": {"soin": "1D{Vol/5}+{R/10}"},
	 "description": "Le nécromant force son propre corps à se refermer. La volonté tire, la "
					"carcasse obéit — d'autant mieux qu'elle est robuste.",
	 "composants": [_c("Poudre_os", False, {"soin": "2"}),
					_c("sang", True, {"soin": "1D6"})],
	 "anim": _anim("blood_hit_03_a", "swish_2.wav", 0.6)},
	{"slug": "transfusion", "nom": "Transfusion", "icon": "💉",
	 "magie": "Sainte", "niveau": 2, "cout_pm": 12, "cible": "allie", "portee": 2,
	 "effets": {"soin": "2D{Vol/10}+{Vol/10}", "cout_pv": "{Vol/10}"},
	 "description": "Le prêtre donne de son propre sang pour sauver un compagnon. Plus sa foi "
					"est grande, plus il donne — et plus il guérit.",
	 "composants": [_c("Bougie_de_veille", False, {"soin": "2"}),
					_c("relique", True, {"soin": "1D6"})],
	 "anim": _anim("17_implode002red_a", "power_up_sound_v0.ogg", 0.7)},

	# ── Niveaux 3 à 6 — sorts de spécialiste ───────────────────────────────────
	{"slug": "chaine_d_eclairs", "nom": "Chaîne d'éclairs", "icon": "🌩️",
	 "magie": "Élémentaire", "niveau": 3, "cout_pm": 38, "cible": "ennemi", "portee": 6,
	 "zone": {"forme": "rectangle", "origine": "lanceur", "orientation": "cible",
			  "longueur": 5, "largeur": 1, "decalage": 1},
	 "effets": {"degats": "3D{Int/5}"},
	 "description": "L'éclair saute de corps en corps sur toute une ligne. Le mage choisit la "
					"direction ; sa science fixe la violence du courant.",
	 "composants": [_c("Cristal_canalisation", False, {"degats": "2"}),
					_c("poudre_alchimique", True, {"degats": "1D8"})],
	 "anim": _anim("2_magic8_spritesheet_a", "17.mp3", 0.9, **PROJECTILE)},
	{"slug": "bourgeonnement", "nom": "Bourgeonnement", "icon": "🌱",
	 "magie": "Nature", "niveau": 3, "cout_pm": 36, "cible": "soi", "portee": 0,
	 "zone": {"forme": "cercle", "origine": "lanceur", "rayon": 2},
	 "effets": {"soin": "1D8+{Vol/10}", "regen_pv": "{Vol/15}", "duree": 3, "partage_soin": 15},
	 "description": "Autour du druide, l'herbe pousse sur les plaies. Tout le cercle reprend "
					"vie, et lui avec.",
	 "composants": [_c("Branche_de_Chene", False, {"regen_pv": 1}),
					_c("Racine_de_mandragore", True, {"regen_pv": 2})],
	 "anim": _anim("20_magicbubbles_spritesheet_a", "swamp.ogg", 0.6, fin_ms=1500)},
	{"slug": "fletrissure", "nom": "Flétrissure", "icon": "🥀",
	 "magie": "Nécromancie", "niveau": 3, "cout_pm": 38, "cible": "ennemi", "portee": 5,
	 "effets": {"degats": "2D{Int/6}", "regen_pv": "-{Vol/10}", "duree": "1+{Vol/25}"},
	 "description": "La chair se dessèche et continue de se dessécher. La volonté du nécromant "
					"décide combien de temps le mal ronge.",
	 "composants": [_c("Focus_ossuaire", False, {"regen_pv": -1}),
					_c("Sel_des_sepultures", True, {"duree": 1})],
	 "anim": _anim("smoke30frames_a", "17.mp3", 0.6)},
	{"slug": "egide_du_stratege", "nom": "Égide du stratège", "icon": "🛡️",
	 "magie": "Bataille", "niveau": 4, "cout_pm": 44, "cible": "allie", "portee": 4,
	 "effets": {"buffs": {"R": "{Int/4}"}, "esquive": 10, "duree": "2+{Int/20}"},
	 "description": "Un bouclier calculé pour encaisser les coups qu'il prévoit. Plus le "
					"stratège est fin, plus la parade est solide et durable.",
	 "composants": [_c("Cristal_canalisation", False, {"buffs": {"R": 5}}),
					_c("encens", True, {"duree": 2})],
	 "anim": _anim("preset_ring_blueish_a", "power_up_sound_v2.ogg", 0.8)},
	{"slug": "effondrement_mental", "nom": "Effondrement mental", "icon": "🧠",
	 "magie": "Illusoire", "niveau": 4, "cout_pm": 46, "cible": "ennemi", "portee": 6,
	 "effets": {"degats_pm": "2D{Int/5}", "buffs": {"Int": "-{Int/4}", "Vol": "-{Int/4}"},
				"duree": 2},
	 "description": "L'illusionniste fait s'écrouler les certitudes de sa cible. Sa magie fuit, "
					"son esprit vacille.",
	 "composants": [_c("Miroir_de_poche", False, {"degats_pm": "2"}),
					_c("Poudre_de_miroir", True, {"degats_pm": "1D8"})],
	 "anim": _anim("12_nebula_spritesheet_a", "17.mp3", 0.8)},
	{"slug": "lumiere_salvatrice", "nom": "Lumière salvatrice", "icon": "🌟",
	 "magie": "Sainte", "niveau": 5, "cout_pm": 56, "cible": "soi", "portee": 0,
	 "incantation": 2,
	 "zone": {"forme": "cercle", "origine": "lanceur", "rayon": 3},
	 "effets": {"soin": "2D8+{Vol/5}", "partage_soin": 10},
	 "description": "Deux souffles de prière, puis la lumière inonde le champ de bataille. "
					"Tous les fidèles à portée se relèvent.",
	 "composants": [_c("encens", False, {"soin": "3"}),
					_c("relique", True, {"soin": "2D6"})],
	 "anim": _anim("light_glow_effect_b", "power_up_sound_v3.ogg", 1.0)},
	{"slug": "pacte_de_puissance", "nom": "Pacte de puissance", "icon": "😈",
	 "magie": "Démonologie", "niveau": 5, "cout_pm": 54, "cible": "allie", "portee": 3,
	 "effets": {"buffs": {"F": "{Cha/4}", "Vol": "{Cha/4}"}, "cout_pv": "{Cha/5}", "duree": 3},
	 "description": "Le démoniste négocie pour un allié une force qui n'est pas la sienne. Le "
					"prix se paie en sang, à la hauteur de son éloquence.",
	 "composants": [_c("Bougie_noire", False, {"buffs": {"F": 5, "Vol": 5}}),
					_c("coeur", True, {"duree": 2})],
	 "anim": _anim("17_implode002red_b", "forging_flames.mp3", 0.7, fin_ms=1500)},
	{"slug": "tempete_de_feu", "nom": "Tempête de feu", "icon": "🌋",
	 "magie": "Élémentaire", "niveau": 6, "cout_pm": 66, "cible": "ennemi", "portee": 6,
	 "incantation": 3,
	 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
	 "effets": {"degats": "4D{Int/5}+{Int/5}"},
	 "description": "Trois respirations pour réunir le feu, puis un tourbillon dévore tout ce "
					"qui se tient là. La science de l'élémentaliste en fixe la fureur.",
	 "composants": [_c("Cristal_canalisation", False, {"degats": "3"}),
					_c("Soufre", True, {"degats": "2D6"})],
	 "anim": _anim("7_firespin_spritesheet_a", "foom_0.wav", 1.0)},

	# ── Niveaux 7 à 10 — sorts de maître ───────────────────────────────────────
	{"slug": "moisson_des_ames", "nom": "Moisson des âmes", "icon": "💀",
	 "magie": "Nécromancie", "niveau": 7, "cout_pm": 76, "cible": "ennemi", "portee": 5,
	 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
	 "effets": {"degats": "3D{Vol/4}", "drain_pv": 40, "drain_max": "{Vol/2}"},
	 "description": "Une faux d'ombre passe sur un groupe entier. Le nécromant boit ce qu'elle "
					"fauche, dans la mesure de sa volonté.",
	 "composants": [_c("os", False, {"degats": "3"}),
					_c("Sel_des_sepultures", True, {"degats": "2D6"})],
	 "anim": _anim("14_phantom_spritesheet_a", "17.mp3", 0.9)},
	{"slug": "sanctuaire_sylvestre", "nom": "Sanctuaire sylvestre", "icon": "🌳",
	 "magie": "Nature", "niveau": 7, "cout_pm": 76, "cible": "soi", "portee": 0,
	 "maintien": 4,
	 "zone": {"forme": "cercle", "origine": "lanceur", "rayon": 3},
	 "effets": {"regen_pv": "{Vol/8}"},
	 "description": "Une clairière se lève autour du druide et y reste tant qu'il la porte. "
					"Ceux qui s'y tiennent guérissent à chaque souffle.",
	 "composants": [_c("Seve_de_chene", False, {"maintien_reduction": 1}),
					_c("Fiole_sang_bete", True, {"maintien_reduction": 2})],
	 "anim": _anim("green_effect_b", "swamp.ogg", 0.7, fin_ms=2000)},
	{"slug": "rempart_arcanique", "nom": "Rempart arcanique", "icon": "🏰",
	 "magie": "Bataille", "niveau": 8, "cout_pm": 86, "cible": "soi", "portee": 0,
	 "maintien": 4,
	 "zone": {"forme": "cercle", "origine": "lanceur", "rayon": 2},
	 "effets": {"buffs": {"R": "{Int/3}"}, "esquive": "{Int/10}"},
	 "description": "Un dôme de force se dresse autour du mage de bataille et de ses proches, "
					"et tient tant qu'il le nourrit.",
	 "composants": [_c("Cristal_canalisation", False, {"buffs": {"R": 5}}),
					_c("poudre_alchimique", True, {"maintien_reduction": 2})],
	 "anim": _anim("preset_shockwave_blueish_a", "power_up_sound_v2.ogg", 1.0)},
	{"slug": "meteore_savant", "nom": "Météore savant", "icon": "☄️",
	 "magie": "Élémentaire", "niveau": 8, "cout_pm": 88, "cible": "ennemi",
	 "portee": "6+{Int/10}", "incantation": 5,
	 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
	 "effets": {"degats": "6D{Int/5}+{Int/4}"},
	 "description": "Cinq respirations pour calculer la trajectoire, puis le ciel tombe. Plus "
					"le mage est savant, plus il le fait tomber loin et fort.",
	 "composants": [_c("Cristal_canalisation", False, {"degats": "4"}),
					_c("Soufre", True, {"degats": "2D8"})],
	 "anim": _anim("explosion_fire_smoke_a", "foom_0.wav", 1.0, depart_ancrage="cible",
				   depart_decalage_y=-4, duree_trajet_ms=600)},
	{"slug": "folie_partagee", "nom": "Folie partagée", "icon": "🎭",
	 "magie": "Illusoire", "niveau": 9, "cout_pm": 98, "cible": "ennemi", "portee": 5,
	 "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible",
			  "longueur": 4, "decalage": 1},
	 "effets": {"degats": "2D{Int/5}", "buffs": {"Int": "-{Int/3}", "Ag": "-{Int/5}"},
				"duree": "1+{Int/30}"},
	 "description": "Un souffle de visions fait perdre la raison à tout ce qui se trouve devant "
					"l'illusionniste. La durée du délire dépend de son génie.",
	 "composants": [_c("Plume_d_oie", False, {"buffs": {"Int": -5}}),
					_c("Poudre_de_miroir", True, {"duree": 1})],
	 "anim": _anim("31_000j_instaroutarea4infinity_a", "17.mp3", 1.0)},
	{"slug": "resurgence", "nom": "Résurgence", "icon": "🕊️",
	 "magie": "Sainte", "niveau": 10, "cout_pm": 118, "cible": "soi", "portee": 0,
	 "incantation": 4,
	 "zone": {"forme": "cercle", "origine": "lanceur", "rayon": 4},
	 "effets": {"soin": "4D10+{Vol/2}", "regen_pv": "{Vol/10}", "duree": 3,
				"partage_soin": "{Vol/10}"},
	 "description": "Quatre souffles d'une prière que peu de saints connaissent, et des ailes "
					"de lumière s'ouvrent sur le champ de bataille.",
	 "composants": [_c("encens", False, {"soin": "5"}),
					_c("relique", True, {"soin": "2D10"})],
	 "anim": _anim("wing_part_1_a", "power_up_sound_v3.ogg", 1.0)},
]


def charger_dump(chemin=None) -> dict:
	if chemin:
		print("source : %s" % chemin)
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(f for f in os.listdir(DOSSIER_JSONS)
				   if f.startswith("telluris-dump-") and f.endswith(".json"))
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
	print("source : jsons/%s" % dumps[-1])
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def sort_doc(spec: dict) -> dict:
	doc = {
		"_id": "sort:" + spec["slug"],
		"type": "sort",
		"nom": spec["nom"],
		"icon": spec["icon"],
		"description": spec["description"],
		"magie": spec["magie"],
		"niveau": spec["niveau"],
		"cout_pm": spec["cout_pm"],
		"cible": spec["cible"],
		"jet": "magique",
		"portee": spec["portee"],
		"effets": spec["effets"],
		"composants": spec["composants"],
		"animation": "animation:sc_" + spec["slug"],
	}
	for cle in ("incantation", "maintien", "zone"):
		if spec.get(cle):
			doc[cle] = spec[cle]
	return doc


def animation_doc(spec: dict, base_anim: dict) -> dict:
	a = spec["anim"]
	doc = {"_id": "animation:sc_" + spec["slug"], "type": "animation",
		   "nom": "%s (%s)" % (spec["nom"], a["base"][len("animation:"):])}
	for cle in CLES_DECOUPE:
		if cle in base_anim:
			doc[cle] = base_anim[cle]
	doc.update(a["trajet"])
	doc.update({"son": a["son"], "son_debut_ms": 0, "son_fin_ms": a["son_fin_ms"],
				"son_volume": a["son_volume"], "actif": True})
	return doc


def deja_importe(genere: dict, existant: dict) -> bool:
	"""Le doc `existant` (base ou autre import) est-il CE doc, déjà importé ? Vrai si chaque
	champ que le générateur produit s'y retrouve à l'identique.

	⚠️ Pas l'égalité stricte : la base ENRICHIT un doc importé de champs que le générateur
	n'écrit pas (`animation`, `animation_zone` liées depuis /admin/animations). Ce n'est pas
	une collision — et le réémettre (PUT complet) effacerait la liaison. Un champ produit
	qui DIFFÈRE reste une collision : un autre doc a pris l'`_id`, ou la base l'a retouché."""
	existant = existant or {}
	return all(existant.get(k) == v for k, v in (genere or {}).items())


def generer(base: dict) -> tuple:
	"""`(docs, erreurs)` — docs à importer (neufs ou différents de la base), erreurs de garde."""
	erreurs = []
	ecoles = {str(v.get("magie") or "") for v in (base.get("rules:vocations") or {}).get("value") or []
			  if isinstance(v, dict) and v.get("magie")}
	sons = set(os.listdir(DOSSIER_SONS)) if os.path.isdir(DOSSIER_SONS) else set()

	sorts, animations = [], []
	for spec in SORTS:
		sid = "sort:" + spec["slug"]
		if spec["magie"] not in ecoles:
			erreurs.append("%s : école inconnue %r" % (sid, spec["magie"]))
		compos = spec["composants"]
		if not any(c["consomme"] for c in compos) or not any(not c["consomme"] for c in compos):
			erreurs.append("%s : il faut un composant consommé ET un catalyseur" % sid)
		for c in compos:
			if c["item"] not in base:
				erreurs.append("%s : composant absent du dump %s" % (sid, c["item"]))
		base_anim = base.get(spec["anim"]["base"])
		if not base_anim or not base_anim.get("actif") or not base_anim.get("fichier"):
			erreurs.append("%s : animation de base absente ou inactive %s" % (sid, spec["anim"]["base"]))
			continue
		if spec["anim"]["son"] not in sons:
			erreurs.append("%s : son introuvable %s" % (sid, spec["anim"]["son"]))
		sorts.append(sort_doc(spec))
		animations.append(animation_doc(spec, base_anim))

	docs = []
	for doc in sorts + animations:
		existant = base.get(doc["_id"])
		if existant is None:
			docs.append(doc)
			continue
		if not deja_importe(doc, existant):
			erreurs.append("%s existe déjà et diffère — l'import (PUT complet) l'écraserait" % doc["_id"])

	# Grimoires : seulement ceux de NOS sorts (la base est réduite à ses grimoires et à ses
	# recettes, pour que `grimoires_manquants` ignore les sorts déjà en base).
	reduite = {k: d for k, d in base.items()
			   if d.get("type") == "recette" or grimoires.est_grimoire(d)}
	g_docs, _lignes, g_erreurs = grimoires.grimoires_manquants(reduite, sorts_en_plus=sorts)
	erreurs.extend(g_erreurs)
	docs.extend(g_docs)
	return docs, erreurs


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	parser = argparse.ArgumentParser(description="Sorts à formules de caractéristiques")
	parser.add_argument("--dump", help="dump à relire (défaut : le plus récent de jsons/)")
	parser.add_argument("--sortie", default=SORTIE, help="fichier écrit")
	args = parser.parse_args()

	dump = charger_dump(args.dump)
	base = {d["_id"]: d for d in dump["docs"] if isinstance(d, dict) and d.get("_id")}
	docs, erreurs = generer(base)
	if erreurs:
		print("\n⚠️ %d erreur(s) — RIEN n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("   " + e)
		sys.exit(1)
	if not docs:
		print("Tout est déjà en base. Aucun fichier écrit.")
		return
	with open(args.sortie, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	compte = lambda t: sum(1 for d in docs if d["type"] == t)  # noqa: E731
	print("écrit %s : %d sort(s), %d animation(s), %d grimoire(s), %d recette(s)" % (
		os.path.relpath(args.sortie, RACINE), compte("sort"), compte("animation"),
		compte("item"), compte("recette")))


if __name__ == "__main__":
	main()

#!/usr/bin/env python
"""Formes enseignées des sept écoles — 22 sorts transmis par un maître, chacun au bout d'une épreuve."""
# dev/gen_maitres_ecoles.py
#
# Même contrat que la Lance de lumière (dev/gen_lumiere_paladine.py) : une forme ENSEIGNÉE
# (`enseignement`, aucun grimoire, refusée par /api/apprendre_sort) AMÉLIORE une forme simple
# (`ameliore` : prérequis, et la remplace au même rang). Seul son maître la transmet (service
# PNJ `enseignement`), après une épreuve (service `apport` : rapporter des trophées).
#
#   • La forme enseignée a le NIVEAU de sa forme simple (comme Rayon → Lance).
#   • Un couple de NIVEAU 10 par école (Sainte : Rayon → Lance, déjà en base). Quatre écoles
#     n'avaient pas de forme simple de niveau 10 qui convienne : elle est créée ici, avec son
#     grimoire unique et sa recette de scriptorium (`BASES`).
#   • Trois formes ABATTENT les volants (`effets.abattre`, combat `_can_fly`) : Harpon arcanique,
#     Cisaille des vents, Liane d'abattage — le pendant, dans trois écoles, de la Lance.
#   • Un maître par forme ; d'autres pourront suivre. Il se tient dans un lieu EXISTANT : quand
#     sa cité n'a pas de lieu en base (Gênes, Constantinople, Ossory, Novgorod, Babylone,
#     Jérusalem), son texte dit d'où il vient.
#   • Portraits : `templates/resources/pnj/maitre_<slug>01.jpg`, à générer (prompts donnés à
#     l'Auteur avec la livraison).
#
# IDEMPOTENT : un doc déjà en base à l'identique n'est pas réémis ; un `_id` pris par un doc
# différent fait REFUSER tout le lot (l'import est un PUT complet) — sauf un MAÎTRE déjà importé
# (il enseigne SA forme), réémis FUSIONNÉ. Les docs de LIEU sont relus dans le dump et ne
# gagnent / ne réécrivent que l'entrée `pnj` de leurs maîtres.
#
# Usage : python dev/gen_maitres_ecoles.py [--dump chemin] [--sortie chemin]
# Sortie : jsons/maitres_ecoles_a_importer.json (📥 Importer depuis /admin)

import argparse
import copy
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "maitres_ecoles_a_importer.json")

from utils import grimoires  # noqa: E402
from gen_lumiere_paladine import _sans_rev, deja_importe, dernier_dump  # noqa: E402


def _cat(item, bonus):
	"""Catalyseur (porté, non consommé) — toujours AVANT le consommé, et plus faible."""
	return {"item": item, "consomme": False, "bonus": bonus}


def _cons(item, bonus):
	return {"item": item, "consomme": True, "bonus": bonus}


# ── Formes simples de niveau 10 créées ici (grimoire + recette) ─────────────────────

BASES = [
	{
		"_id": "sort:egide_de_la_porte",
		"type": "sort",
		"nom": "Égide de la porte",
		"icon": "🛡️",
		"description": "Le bouclier que les Templiers posent sur celui qui tient la porte d'un "
					   "temple quand le portail déborde. Un seul corps, mais un corps qui ne recule "
					   "plus. Les livres l'enseignent ; la garde de Rome en connaît une autre forme.",
		"magie": "Bataille",
		"niveau": 10,
		"cout_pm": 70,
		"cible": "allie",
		"jet": "magique",
		"portee": 4,
		"effets": {"buffs": {"R": "{Int/3}"}, "esquive": 15, "duree": "3+{Int/20}"},
		"composants": [_cat("item:Cristal_canalisation", {"buffs": {"R": 5}}),
					   _cons("item:encens", {"duree": 2})],
		"animation": "animation:sc_egide_du_stratege",
	},
	{
		"_id": "sort:proie_fantome",
		"type": "sort",
		"nom": "Proie fantôme",
		"icon": "🕊️",
		"description": "Une proie qui n'existe pas, blessée, à portée de griffe : la bête la voit, "
					   "s'acharne dessus et ne voit plus que vous. Les fauconniers de Montmartre en "
					   "ont fait autre chose, qu'ils n'écrivent pas.",
		"magie": "Illusoire",
		"niveau": 10,
		"cout_pm": 60,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 8,
		"effets": {"degats": "2D6+{Int/10}", "provocation": 1, "buffs": {"Vol": "-{Int/5}"},
				   "duree": 2},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "2"}),
					   _cons("item:Poudre_de_miroir", {"degats": "1D8"})],
		"animation": "animation:capa_spectre",
	},
	{
		"_id": "sort:lianes_de_la_canopee",
		"type": "sort",
		"nom": "Lianes de la canopée",
		"icon": "🌿",
		"description": "Des lianes épaisses comme des bras descendent d'un arbre qui n'est pas là "
					   "et serrent tout ce qui se tient dessous. Elles retiennent ce qui marche ; "
					   "pour ce qui vole, les gardiens-aigles de Teotihuacan les tressent autrement.",
		"magie": "Nature",
		"niveau": 10,
		"cout_pm": 55,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 6,
		"effets": {"degats": "3D8+{Vol/10}", "buffs": {"Ag": "-{Vol/5}"}, "duree": 2},
		"composants": [_cat("item:Seve_de_chene", {"degats": "2"}),
					   _cons("item:Herbes_a_bruler", {"degats": "1D8"})],
		"animation": "animation:capa_nature_buff",
		"zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
	},
	{
		"_id": "sort:momie_royale",
		"type": "sort",
		"nom": "Momie royale",
		"icon": "⚱️",
		"description": "Les bandelettes d'un roi oublié se déroulent, et un corps qui a régné se "
					   "redresse dans son or terni. Il garde les gestes de celui qui commandait. Au "
					   "sud de l'Égypte, une cour entière sait le faire tenir plus longtemps.",
		"magie": "Nécromancie",
		"famille": "invocation",
		"niveau": 10,
		"cout_pm": 95,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:momie", "nombre": 1, "duree": 6,
					   "profil": "profil:seigneur"},
		"composants": [_cons("item:Sel_des_sepultures", {"invocation_duree": 2}),
					   _cat("item:os", {"invocation_duree": 1})],
		"animation": "animation:capa_levee_morts",
	},
]


# ── Les 22 formes enseignées ─────────────────────────────────────────────────────────
# Chaque entrée : la forme enseignée (sans `enseignement`/`ameliore`, posés par `sort_enseigne`)
# et l'`_id` de la forme simple qu'elle améliore.

ENSEIGNES = [
	# ── Sainte ──
	("sort:priere_de_communion", {
		"_id": "sort:veille_du_calvaire",
		"nom": "Veille du Calvaire",
		"icon": "🕯️",
		"description": "La prière des sœurs du Calvaire, qui ne quittent pas un blessé tant qu'il "
					   "respire. La lumière soigne d'abord, puis reste sur les corps pendant que "
					   "la sœur veille.",
		"magie": "Sainte",
		"niveau": 2,
		"cout_pm": 20,
		"cible": "soi",
		"jet": "magique",
		"portee": 0,
		"effets": {"soin": "1D6+{Vol/15}", "partage_soin": 20, "regen_pv": "{Vol/20}",
				   "duree": 3},
		"composants": [_cat("item:Bougie", {"soin": "1"}),
					   _cons("item:Eau_benite", {"soin": "1D4"})],
		"animation": "animation:sc_priere_de_communion",
		"zone": {"forme": "cercle", "origine": "lanceur", "rayon": 2},
	}),
	# ── Bataille ──
	("sort:bombardement", {
		"_id": "sort:feu_des_chaires",
		"nom": "Feu des chaires",
		"icon": "☄️",
		"description": "Tiré des chaires qui surplombent le portail d'un temple, quand le donjon "
					   "déborde et que la cour se remplit. Le feu tombe large et loin, et il ne "
					   "trie pas : le Templier resté en bas doit savoir où se mettre.",
		"magie": "Bataille",
		"niveau": 8,
		"cout_pm": 50,
		# 4 PA sous Int 30, 2 à Int 60, 1 à Int 90 : la maîtrise raccourcit le tir.
		"incantation": "4-{Int/30}",
		"cible": "ennemi",
		"jet": "magique",
		"portee": 10,
		"effets": {"degats": "3D8+{Int/12}"},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "3"}),
					   _cons("item:poudre_alchimique", {"degats": "2D6"})],
		"animation": "animation:capa_meteore",
		"zone": {"forme": "cercle", "origine": "cible", "rayon": 3, "tir_ami": True},
	}),
	("sort:lance_arcanique", {
		"_id": "sort:harpon_arcanique",
		"nom": "Harpon arcanique",
		"icon": "🪝",
		"description": "Une lance arcanique qui garde un fil. Elle se plante dans l'aile, et le fil "
					   "tire vers le sol ce qui croyait s'enfuir par le ciel. Les Génois l'ont "
					   "inventée pour les dragons des mers ; elle sert aussi contre ceux de l'air.",
		"magie": "Bataille",
		"niveau": 7,
		"cout_pm": 40,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 8,
		"effets": {"degats": "3D10+{Int/8}", "abattre": 1, "duree": "1+{Int/30}"},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "2"}),
					   _cons("item:poudre_alchimique", {"degats": "2D6"})],
		"animation": "animation:capa_arcane",
	}),
	("sort:egide_de_la_porte", {
		"_id": "sort:egide_de_la_garde_interieure",
		"nom": "Égide de la garde intérieure",
		"icon": "🏛️",
		"description": "La garde intérieure ne protège pas un homme, elle protège un seuil. Tant "
					   "que le Templier tient, tous ceux qui se tiennent autour de lui tiennent "
					   "aussi. On la transmet à Rome, à la porte que gardaient Rémus et les Luperques.",
		"magie": "Bataille",
		"niveau": 10,
		"cout_pm": 90,
		"maintien": 6,
		"cible": "soi",
		"jet": "magique",
		"portee": 0,
		"effets": {"buffs": {"R": "{Int/3}"}, "esquive": "{Int/6}"},
		"composants": [_cat("item:Cristal_canalisation", {"maintien_reduction": 1}),
					   _cons("item:encens", {"maintien_reduction": 2})],
		"animation": "animation:sc_egide_du_stratege",
		"zone": {"forme": "carre", "origine": "lanceur", "rayon": 2},
	}),
	# ── Élémentaire ──
	("sort:boule_de_feu", {
		"_id": "sort:feu_gregeois",
		"nom": "Feu grégeois",
		"icon": "🔥",
		"description": "Le secret de Constantinople : un feu qui colle, que l'eau n'éteint pas et "
					   "qui brûle encore quand le mage a fini. Il coûte peu de mana, et beaucoup "
					   "de poix.",
		"magie": "Élémentaire",
		"niveau": 2,
		"cout_pm": 14,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 8,
		"effets": {"degats": "3D6", "regen_pv": -3, "duree": 3},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "1"}),
					   _cons("item:poix", {"degats": "1D6", "duree": 1})],
		"animation": "animation:capa_explosion_feu",
		"zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
	}),
	("sort:meteore", {
		"_id": "sort:pluie_de_surtr",
		"nom": "Pluie de Surtr",
		"icon": "🌋",
		"description": "Les Islandais disent que le géant de feu attend sous la lave, dans la grotte "
					   "qui porte son nom. Ce qui tombe du ciel avec ce sort a la couleur de son "
					   "épée, et la lave reste là où elle est tombée.",
		"magie": "Élémentaire",
		"niveau": 8,
		"cout_pm": 55,
		# 6 PA sous Int 40, 5 à Int 40, 4 à Int 80 : comme la Lance, la maîtrise raccourcit.
		"incantation": "6-{Int/40}",
		"cible": "ennemi",
		"jet": "magique",
		"portee": 10,
		"effets": {"degats": "4D6+30", "regen_pv": -4, "duree": 2},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "1D6"}),
					   _cons("item:gemmes", {"degats": "2D6"})],
		"animation": "animation:capa_meteore",
		"zone": {"forme": "cercle", "origine": "cible", "rayon": 3},
	}),
	("sort:fureur_elementaire", {
		"_id": "sort:colere_de_l_hekla",
		"nom": "Colère de l'Hekla",
		"icon": "🌋",
		"description": "Les quatre éléments frappent ensemble, comme dans la Fureur, mais ils "
					   "viennent d'en dessous : de la bouche de l'Hekla, que les gens d'Akureyri "
					   "appellent la porte de l'Enfer. Ce qui est touché brûle encore longtemps.",
		"magie": "Élémentaire",
		"niveau": 10,
		"cout_pm": 80,
		"incantation": 3,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 6,
		"effets": {"degats": "6D10+{Int/6}", "regen_pv": "-{Int/10}", "duree": 3},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "3"}),
					   _cons("item:Soufre", {"degats": "2D6"})],
		"animation": "animation:capa_explosion_feu",
		"zone": {"forme": "cercle", "origine": "cible", "rayon": 1},
	}),
	("sort:lame_de_vent", {
		"_id": "sort:cisaille_des_vents",
		"nom": "Cisaille des vents",
		"icon": "🌪️",
		"description": "Deux lames de vent qui se croisent sur une aile. Celui qui vole ne tombe "
					   "pas toujours, mais il ne remonte pas avant d'avoir repris son souffle. On "
					   "l'enseigne au pied du Granusturm, aux élémentalistes qui épaulent la Lance.",
		"magie": "Élémentaire",
		"niveau": 0,
		"cout_pm": 12,
		"cible": "ennemi",
		"portee": 10,
		"effets": {"degats": "2D6", "abattre": 1, "duree": 1},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "2"}),
					   _cons("item:plumes", {"degats": "1D6"})],
		"animation": "animation:capa_vent",
	}),
	# ── Illusoire ──
	("sort:proie_fantome", {
		"_id": "sort:leurre_du_fauconnier",
		"nom": "Leurre du fauconnier",
		"icon": "🦅",
		"description": "Le fauconnier fait tourner le leurre, et l'oiseau plonge. À Montmartre, on "
					   "fait plonger les griffons : tout ce qui vole autour de la proie fantôme "
					   "fond sur l'illusionniste, droit dans la ligne des paladins.",
		"magie": "Illusoire",
		"niveau": 10,
		"cout_pm": 85,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 10,
		"effets": {"degats": "2D6+{Int/10}", "provocation": 1,
				   "buffs": {"Ag": "-{Int/5}", "Vol": "-{Int/5}"}, "duree": "2+{Int/30}"},
		"composants": [_cat("item:Cristal_canalisation", {"degats": "2"}),
					   _cons("item:Poudre_de_miroir", {"degats": "1D8"})],
		"animation": "animation:capa_spectre",
		"zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
	}),
	("sort:formule_de_clairvoyance", {
		"_id": "sort:sur_des_epaules_de_geants",
		"nom": "Sur des épaules de géants",
		"icon": "📜",
		"description": "« Nous sommes des nains juchés sur des épaules de géants. » À l'école de "
					   "Chartres, on le dit à la lettre, et la formule voit plus loin quand on la "
					   "partage : tous ceux qui l'entendent pensent un peu plus clair.",
		"magie": "Illusoire",
		"niveau": 0,
		"cout_pm": 14,
		"cible": "soi",
		"portee": 0,
		"effets": {"buffs": {"Int": 10, "Vol": 5}, "duree": 5},
		"composants": [_cat("item:Plume_d_oie", {"buffs": {"Int": 5}}),
					   _cons("item:encens", {"duree": 2})],
		"animation": "animation:capa_meditation",
		"zone": {"forme": "cercle", "origine": "lanceur", "rayon": 2},
	}),
	("sort:eventail_de_folie", {
		"_id": "sort:chant_des_sirenes",
		"nom": "Chant des sirènes",
		"icon": "🧜",
		"description": "Le chant qui faisait sauter les marins par-dessus bord, appris d'un homme "
					   "qui a sauté et qui en est revenu. Ceux qui l'entendent oublient de se "
					   "défendre, et s'avancent vers celui qui chante.",
		"magie": "Illusoire",
		"niveau": 6,
		"cout_pm": 38,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 6,
		"effets": {"degats": "2D6+{Int/10}", "provocation": 1, "buffs": {"Vol": "-{Int/6}"},
				   "duree": 2},
		"composants": [_cat("item:Plume_d_oie", {"degats": "2"}),
					   _cons("item:Poudre_de_miroir", {"degats": "1D8"})],
		"animation": "animation:capa_impact_etincelles",
		"animation_zone": "animation:capa_cone_folie",
		"zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "decalage": 1,
				 "longueur": 5, "angle": 90},
	}),
	# ── Nature ──
	("sort:lianes_de_la_canopee", {
		"_id": "sort:liane_d_abattage",
		"nom": "Liane d'abattage",
		"icon": "🪢",
		"description": "Une seule liane, mais elle monte : elle s'enroule autour de ce qui vole, "
					   "le ramène au sol et l'y tient. Les gardiens-aigles de Teotihuacan la "
					   "tressent pour le ciel comme les gardiens-jaguars la tressent pour la forêt.",
		"magie": "Nature",
		"niveau": 10,
		"cout_pm": 75,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 8,
		"effets": {"degats": "5D10+{Vol/6}", "abattre": 1, "buffs": {"Ag": "-{Vol/4}"},
				   "duree": "2+{Vol/30}"},
		"composants": [_cat("item:Seve_de_chene", {"degats": "3"}),
					   _cons("item:Herbes_a_bruler", {"degats": "2D6"})],
		"animation": "animation:capa_nature_buff",
	}),
	("sort:serres_de_l_aigle_geant", {
		"_id": "sort:gardien_aigle",
		"nom": "Gardien-aigle",
		"icon": "🦅",
		"description": "L'aigle qui répond n'est plus un aigle sauvage : c'est l'un de ceux que les "
					   "gardiens-aigles élèvent au-dessus de Teotihuacan. Il chasse dans le ciel ce "
					   "qui croit y être seul.",
		"magie": "Nature",
		"famille": "invocation",
		"niveau": 7,
		"cout_pm": 80,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:aigle_geant", "nombre": 1, "duree": 6,
					   "profil": "profil:champion"},
		"composants": [_cons("item:Racine_de_mandragore", {"invocation_duree": 2}),
					   _cat("item:Branche_de_Chene", {"invocation_duree": 1})],
		"animation": "animation:capa_appel_sauvage",
	}),
	("sort:hurlement_du_loup", {
		"_id": "sort:meute_des_ulfhednar",
		"nom": "Meute des Ulfheðnar",
		"icon": "🐺",
		"description": "Les chasseurs en peau de loup de Reykjavik et d'Akureyri ne chassent "
					   "jamais seuls. Le hurlement appris d'eux en fait venir deux, qui chassent "
					   "ensemble et ne lâchent plus la proie.",
		"magie": "Nature",
		"famille": "invocation",
		"niveau": 2,
		"cout_pm": 32,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:loup", "nombre": 2, "duree": 6},
		"composants": [_cons("item:Fiole_sang_bete", {"invocation_duree": 2}),
					   _cat("item:Os_de_totem", {"invocation_duree": 1})],
		"animation": "animation:capa_appel_sauvage",
	}),
	("sort:guerison_des_animaux", {
		"_id": "sort:garde_du_faoladh",
		"nom": "Garde du faoladh",
		"icon": "🐺",
		"description": "En Irlande, le faoladh veille sur les blessés et les égarés jusqu'à ce que "
					   "quelqu'un vienne. Le soin appris de ses gardiens ne s'arrête pas à la "
					   "plaie : il reste sur le blessé et le tient debout.",
		"magie": "Nature",
		"niveau": 0,
		"cout_pm": 12,
		"cible": "allie",
		"portee": 3,
		"effets": {"pv": 16, "regen_pv": 3, "buffs": {"R": 5}, "duree": 3},
		"composants": [_cons("item:Herbes_medicinales", {"pv": 10}),
					   _cat("item:Seve_de_chene", {"pv": 4})],
		"animation": "animation:capa_soin_nature",
	}),
	# ── Nécromancie ──
	("sort:volee_funebre", {
		"_id": "sort:ciel_de_charogne",
		"nom": "Ciel de charogne",
		"icon": "🐦‍⬛",
		"description": "Trois corneilles mortes au lieu de deux, et qui ne se lassent pas. Les "
					   "paladins n'aiment pas ceux qui l'enseignent, mais ils les laissent faire : "
					   "les morts qui volent ne fuient pas les dragons.",
		"magie": "Nécromancie",
		"famille": "invocation",
		"niveau": 8,
		"cout_pm": 55,
		"maintien": 8,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:corneille_noire", "nombre": 3, "duree": 3,
					   "profil": "profil:champion"},
		"composants": [_cons("item:Sel_des_sepultures", {"maintien_reduction": 2}),
					   _cat("item:os", {"maintien_reduction": 1})],
		"animation": "animation:capa_levee_morts",
	}),
	("sort:momie_royale", {
		"_id": "sort:gardien_d_abou_simbel",
		"nom": "Gardien d'Abou Simbel",
		"icon": "🏺",
		"description": "Le rituel des bâtisseurs de tombeaux de la cour de Néfertiti : deux rois "
					   "momifiés se lèvent et prennent place de part et d'autre de celui qui les "
					   "appelle, comme les colosses de la façade.",
		"magie": "Nécromancie",
		"famille": "invocation",
		"niveau": 10,
		"cout_pm": 110,
		"incantation": 3,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:momie", "nombre": 2, "duree": 7,
					   "profil": "profil:seigneur"},
		"composants": [_cons("item:Sel_des_sepultures", {"invocation_duree": 2}),
					   _cat("item:os", {"invocation_duree": 1})],
		"animation": "animation:capa_levee_morts",
	}),
	("sort:levee_des_ossements", {
		"_id": "sort:ossuaire_des_catacombes",
		"nom": "Ossuaire des catacombes",
		"icon": "💀",
		"description": "Sous Lutecia, les os sont rangés en murs. Celui qui a appris à les lire en "
					   "fait lever trois d'un coup, qui connaissent le chemin mieux que les vivants.",
		"magie": "Nécromancie",
		"famille": "invocation",
		"niveau": 1,
		"cout_pm": 30,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:squelette", "nombre": 3, "duree": 5},
		"composants": [_cons("item:Sel_des_sepultures", {"invocation_nombre": 1}),
					   _cat("item:os", {"invocation_duree": 1})],
		"animation": "animation:capa_levee_morts",
	}),
	("sort:baiser_du_vampire", {
		"_id": "sort:baiser_de_la_lamie",
		"nom": "Baiser de la lamie",
		"icon": "💋",
		"description": "Le baiser tel que le donnent les lamies : il boit davantage, et celui qui "
					   "le reçoit perd l'envie de se défendre. On ne sait pas pourquoi une lamie "
					   "l'apprend à un vivant. Elle ne le dit pas.",
		"magie": "Nécromancie",
		"niveau": 1,
		"cout_pm": 14,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 4,
		"effets": {"degats": "3D6", "drain_pv": 60, "buffs": {"Cha": -10, "Vol": -10},
				   "duree": 2},
		"composants": [_cat("item:Poudre_os", {"drain_pv": 10}),
					   _cons("item:sang", {"drain_pv": 20})],
		"animation": "animation:capa_drain",
	}),
	# ── Démonologie ──
	("sort:fleau_des_demons", {
		"_id": "sort:flamme_de_maqlu",
		"nom": "Flamme de Maqlû",
		"icon": "🔥",
		"description": "Maqlû, « la Brûlure » : le grand rituel des exorcistes de Babylone, qui "
					   "brûlaient l'image du démon pour brûler le démon. La flamme qui l'a gardé "
					   "ne consume pas seulement la chair, elle vide aussi la magie.",
		"magie": "Démonologie",
		"niveau": 10,
		"cout_pm": 75,
		# 4 PA sous Vol 40, 3 à Vol 40, 2 à Vol 80 : la volonté raccourcit le rituel.
		"incantation": "4-{Vol/40}",
		"cible": "ennemi",
		"jet": "magique",
		"portee": 6,
		"effets": {"degats": "5D10+{Vol/6}", "degats_pm": "2D{Vol/10}"},
		"composants": [_cat("item:Sel_noir", {"degats": "3"}),
					   _cons("item:Sang_demon_seche", {"degats": "2D6"})],
		"animation": "animation:capa_projectile_infernal",
	}),
	("sort:ailes_de_pazuzu", {
		"_id": "sort:ailes_du_roi_des_vents",
		"nom": "Ailes du roi des vents",
		"icon": "🦇",
		"description": "Pazuzu est le roi des démons du vent, et on l'invoquait à Babylone contre "
					   "pire que lui. Ses quatre ailes se prêtent plus longtemps à qui sait lui "
					   "parler, et elles portent plus vite.",
		"magie": "Démonologie",
		"niveau": 6,
		"cout_pm": 30,
		"cible": "soi",
		"jet": "magique",
		"portee": 0,
		"effets": {"vol": 1, "duree": "4+{Int/15}", "cout_pv": 5,
				   "buffs": {"V": 2, "Ag": "{Int/6}"}, "esquive": 5},
		"composants": [_cat("item:Sel_noir", {"duree": 1}),
					   _cons("item:Sang_demon_seche", {"duree": 2})],
		"animation": "animation:capa_arcane",
	}),
	("sort:fouet_de_domination", {
		"_id": "sort:anneau_de_salomon",
		"nom": "Anneau de Salomon",
		"icon": "💍",
		"description": "On dit que Salomon liait les démons avec un sceau gravé sur son anneau. Le "
					   "fouet devient un lien : la créature saigne, perd sa magie et ne voit plus "
					   "que celui qui la tient.",
		"magie": "Démonologie",
		"niveau": 1,
		"cout_pm": 14,
		"cible": "ennemi",
		"jet": "magique",
		"portee": 3,
		"effets": {"degats": "1D{Vol/5}+{Cha/10}", "degats_pm": "1D{Cha/10}",
				   "buffs": {"Vol": "-{Cha/4}"}, "provocation": 1, "duree": 2},
		"composants": [_cat("item:Sel_noir", {"degats": "1"}),
					   _cons("item:Sang_demon_seche", {"degats": "1D4"})],
		"animation": "animation:sc_fouet_de_domination",
	}),
]


def sort_enseigne(base_id: str, doc: dict) -> dict:
	return {"type": "sort", **doc, "enseignement": True, "ameliore": base_id}


SORTS_ENSEIGNES = [sort_enseigne(b, d) for b, d in ENSEIGNES]
FORME_SIMPLE = {d["_id"]: b for b, d in ENSEIGNES}


# ── Les maîtres ───────────────────────────────────────────────────────────────────
# Un par forme enseignée. `ecole_texte` complète « votre magie … n'est pas encore assez
# sûre ». Les noms sont ceux de figures réelles ou de légendes terrestres, portés sur Telluris
# par quelqu'un qui ne confirme jamais s'il est CELUI de la légende (cf. Turpin, Geneviève).

MAITRES = [
	{
		"slug": "hadewijch_du_beguinage", "sort": "sort:veille_du_calvaire",
		"lieu": "lieu:bruges", "nom": "Sœur Hadewijch", "race": "humain", "vocation": "pretre",
		"ecole_texte": "sainte",
		"presence": "Une sœur du Calvaire en manteau gris, assise au chevet d'un blessé dans "
					"la cour du Béguinage. Elle écrit entre deux soins.",
		"description": "Sœur du Calvaire du Béguinage de Bruges. Elle écrit des poèmes que les "
					   "autres sœurs recopient sans les comprendre tout à fait.",
		"epreuve": {"titre": "Les cocatrix du Zwin", "item": "item:cockatrice_tete", "quantite": 2,
					"description": "Des cocatrix nichent dans les marais du Zwin et changent en "
								   "pierre les tisserands qui y coupent les joncs. Sœur Hadewijch "
								   "veut deux têtes de cocatrix avant de vous apprendre la Veille."},
		"accueil": "Sœur Hadewijch remonte la couverture sur le blessé avant de se tourner vers "
				   "vous. « Parlez bas. Il dort. »",
		"q_sort": "« On parle d'une Veille du Calvaire. »",
		"sort_texte": "« La prière de communion soigne, et puis elle s'en va. La Veille reste. "
					  "Elle tient le blessé pendant que vous tenez la prière. »",
		"q_suite": "« Pourquoi ne pas l'écrire dans un livre ? »",
		"sort_suite": "« Je l'ai écrite. Personne n'y arrive avec le livre. Il faut avoir passé "
					  "une nuit au chevet de quelqu'un, et savoir ce que ça coûte. »",
		"propose": "« Les cocatrix du Zwin ont pétrifié deux tisserands ce mois-ci. Rapportez-moi "
				   "deux de leurs têtes. »",
		"remis": "« Vous revenez d'un endroit dont on ne revient pas toujours. Bien. Si la prière de "
				 "communion vous obéit déjà, je vous apprends la Veille. »",
		"appris": "La leçon se fait au chevet d'un blessé, jusqu'à l'aube. {pnj} ne vous laisse "
				  "partir qu'au moment où il ouvre les yeux.",
		"deja": "« Vous l'avez. Restez jusqu'au bout, même quand la fatigue vient. »",
	},
	{
		"slug": "fulbert_de_la_crypte", "sort": "sort:feu_des_chaires",
		"lieu": "lieu:crypte_de_chartres", "nom": "Frère Fulbert", "race": "nain",
		"vocation": "templier", "ecole_texte": "de bataille",
		"presence": "Un Templier nain aux mains couvertes de cire, qui descend des chaires de la "
					"crypte avec un registre sous le bras.",
		"description": "Templier de la crypte de Chartres, chargé des chaires qui surplombent le "
					   "puits. On lui prête le nom de celui qui aurait relevé la cathédrale après "
					   "un incendie ; il dit que c'était un autre Fulbert.",
		"epreuve": {"titre": "Ce qui remonte du puits", "item": "item:minotaure_tete",
					"quantite": 1,
					"description": "Le Minotaure du labyrinthe sous le puits de Chartres remonte "
								   "parfois jusqu'aux marches de la crypte. Frère Fulbert veut sa "
								   "tête avant de vous ouvrir les chaires."},
		"accueil": "Frère Fulbert pose son registre sur une marche. « Si vous venez prier, c'est "
				   "plus haut. Ici, on surveille le puits. »",
		"q_sort": "« On parle d'un Feu des chaires. »",
		"sort_texte": "« Quand le puits déborde, on ne descend pas. On monte aux chaires, et on "
					  "tire sur tout ce qui sort. Large, et loin. »",
		"q_suite": "« Et les Templiers restés en bas ? »",
		"sort_suite": "« Ils savent où se mettre. Le feu ne trie pas. C'est pour ça qu'on ne le "
					  "donne qu'à ceux qui regardent avant de tirer. »",
		"propose": "« Rapportez-moi la tête de ce qui garde le labyrinthe. Après, on parlera "
				   "des chaires. »",
		"remis": "« Le Minotaure. Vous avez fait la descente. Si le Bombardement vous obéit déjà, je "
				 "vous montre les chaires. »",
		"appris": "{pnj} vous fait monter aux chaires et viser la cour vide jusqu'au soir. « Le "
				  "jour où elle sera pleine, vous saurez déjà. »",
		"deja": "« Vous l'avez. Regardez où sont les vôtres avant de tirer. »",
	},
	{
		"slug": "caffaro_le_genois", "sort": "sort:harpon_arcanique",
		"lieu": "lieu:calais", "nom": "Maître Caffaro", "race": "humain", "vocation": "mage",
		"ecole_texte": "de bataille",
		"presence": "Un magicien de combat génois aux bras tatoués de cordages, qui surveille le "
					"détroit depuis la jetée.",
		"description": "Magicien de combat de Gênes, venu chasser les wyvernes de mer sur la "
					   "Manche. Il tient la chronique de chaque bête abattue, et corrige celles "
					   "des autres.",
		"epreuve": {"titre": "Les wyvernes du détroit", "item": "item:wyvern_aile", "quantite": 3,
					"description": "Des wyvernes suivent les navires qui traversent le détroit "
								   "jusqu'à Douvres. Maître Caffaro veut trois ailes de wyverne : "
								   "c'est l'aile qu'on vise."},
		"accueil": "Maître Caffaro ne quitte pas des yeux la ligne de la mer. « À Gênes, on a "
				   "sorti Marco Polo de la gueule d'un dragon. Ici, ce sont des wyvernes. »",
		"q_sort": "« On parle d'un Harpon arcanique. »",
		"sort_texte": "« Une lance qui garde un fil. Elle entre dans l'aile, et le fil ramène la "
					  "bête en bas. Une bête au sol, ça se tue. »",
		"q_suite": "« Et contre un dragon ? »",
		"sort_suite": "« Contre un dragon, il en faut plusieurs, et des paladins derrière. Le "
					  "harpon le fait descendre. Il ne le tue pas. »",
		"propose": "« Rapportez-moi trois ailes de wyverne. Pas des têtes : des ailes. Je veux "
				   "voir où vous visez. »",
		"remis": "{pnj} écarte les ailes sur la jetée et regarde les plaies. « Bien visé. Si la "
				 "Lance arcanique vous obéit déjà, je vous donne le fil. »",
		"appris": "La leçon se fait sur la jetée, contre les mouettes. {pnj} note chaque tir "
				  "dans sa chronique, et ne vous dit pas ce qu'il écrit.",
		"deja": "« Vous l'avez. Visez l'aile, pas le cœur. »",
	},
	{
		"slug": "faustulus_de_la_porte", "sort": "sort:egide_de_la_garde_interieure",
		"lieu": "lieu:rome", "nom": "Frère Faustulus", "race": "ogre", "vocation": "templier",
		"ecole_texte": "de bataille",
		"presence": "Un Templier ogre en manteau de peau de loup, adossé au rempart comme s'il "
					"le tenait debout.",
		"description": "Templier de la garde de la porte, à Rome. Il porte le nom du berger qui "
					   "aurait recueilli Romulus et Rémus. Il répond que tous les gardiens de la "
					   "porte s'appellent ainsi, depuis toujours.",
		"epreuve": {"titre": "La manticore des sept collines", "item": "item:manticore_tete",
					"quantite": 1,
					"description": "Une manticore rôde sur les collines autour de Rome et "
								   "attaque les gardes de nuit. Frère Faustulus veut sa tête avant "
								   "de vous enseigner la garde intérieure."},
		"accueil": "Frère Faustulus ne bouge pas du rempart. « La porte d'abord. Vous, "
				   "ensuite. »",
		"q_sort": "« On parle d'une Égide de la garde intérieure. »",
		"sort_texte": "« L'Égide de la porte protège un homme. La garde intérieure protège tous "
					  "ceux qui se tiennent autour de lui, tant qu'il tient. »",
		"q_suite": "« Et s'il tombe ? »",
		"sort_suite": "« Il ne tombe pas. C'est tout ce qu'on lui demande. Rémus le savait. »",
		"propose": "« La manticore des collines a tué deux gardes de nuit. Rapportez-moi sa "
				   "tête. »",
		"remis": "« Vous avez tenu contre elle. Si l'Égide de la porte vous obéit déjà, je vous "
				 "apprends à la tenir pour les autres. »",
		"appris": "{pnj} vous fait tenir la porte une nuit entière, sans bouger. À l'aube, il "
				  "hoche la tête. « Maintenant, vous savez combien de temps c'est. »",
		"deja": "« Vous l'avez. Ne lâchez pas avant les autres. »",
	},
	{
		"slug": "callinicos_de_constantinople", "sort": "sort:feu_gregeois",
		"lieu": "lieu:rome", "nom": "Maître Callinicos", "race": "elfe",
		"vocation": "elementaliste", "ecole_texte": "élémentaire",
		"presence": "Un élémentaliste elfe aux manches roussies, qui sent la poix. Il est venu de "
					"Constantinople par le portail de Sainte-Sophie.",
		"description": "Élémentaliste de Constantinople. On dit que le feu grégeois a été inventé "
					   "par un Callinicos ; il ne dément pas, et il est elfe.",
		"epreuve": {"titre": "Les tritons du Tibre", "item": "item:triton_tete", "quantite": 2,
					"description": "Des tritons remontent le Tibre et s'en prennent aux barques. "
								   "Maître Callinicos veut deux têtes de triton : le feu grégeois "
								   "est fait pour brûler sur l'eau."},
		"accueil": "Maître Callinicos essuie ses mains sur son tablier. « Ne touchez à rien. Ce "
				   "qui est noir colle. »",
		"q_sort": "« On parle d'un Feu grégeois. »",
		"sort_texte": "« Un feu qui colle, que l'eau n'éteint pas. Il coûte peu de mana. La poix, "
					  "en revanche, il faut la payer. »",
		"q_suite": "« Pourquoi Constantinople en fait-elle un secret ? »",
		"sort_suite": "« Parce que c'est la seule chose qui fait reculer ce qui sort de la mer. "
					  "On ne donne pas ça à n'importe qui. »",
		"propose": "« Les tritons remontent le Tibre. Brûlez-en deux, et rapportez-moi leurs "
				   "têtes. »",
		"remis": "« Ils ont brûlé sur l'eau ? Bien. Si la Boule de feu vous obéit déjà, je vous "
				 "apprends à la faire coller. »",
		"appris": "{pnj} vous fait brûler une barque vide au milieu du Tibre. Elle brûle encore "
				  "quand il vous laisse partir.",
		"deja": "« Vous l'avez. Gardez de la poix sur vous, et ne le dites à personne. »",
	},
	{
		"slug": "hallmundr_de_surtshellir", "sort": "sort:pluie_de_surtr",
		"lieu": "lieu:reykjavik", "nom": "Hallmundr", "race": "ogre",
		"vocation": "elementaliste", "ecole_texte": "élémentaire",
		"presence": "Un élémentaliste ogre très âgé, au manteau couvert de cendre, descendu des "
					"champs de lave à l'est de la ville.",
		"description": "Élémentaliste des champs de lave. Les Islandais donnent son nom à une "
					   "coulée et à un géant de leurs sagas ; il dit qu'il habite seulement à "
					   "côté de la grotte de Surtr.",
		"epreuve": {"titre": "Les dragonnets des champs de lave", "item": "item:petit_dragon_tete",
					"quantite": 2,
					"description": "Des dragonnets nichent dans les champs de lave et descendent "
								   "sur les fermes de Reykjavik. Hallmundr veut deux de leurs "
								   "têtes."},
		"accueil": "Hallmundr se chauffe les mains sur une pierre encore tiède. « La lave, ça ne "
				   "refroidit jamais vraiment. »",
		"q_sort": "« On parle d'une Pluie de Surtr. »",
		"sort_texte": "« Le Météore tombe, et c'est fini. La Pluie de Surtr tombe, et la lave "
					  "reste là où elle est tombée. »",
		"q_suite": "« Surtr existe-t-il vraiment ? »",
		"sort_suite": "« La grotte existe. Le reste, personne n'est allé voir assez loin. Moi "
					  "non plus. »",
		"propose": "« Les dragonnets descendent des champs de lave. Rapportez-m'en deux têtes. »",
		"remis": "« Bien. Si le Météore vous obéit déjà, je vous montre comment le faire "
				 "brûler. »",
		"appris": "La leçon se fait au bord d'une coulée. {pnj} vous fait tirer jusqu'à ce que "
				  "la neige fonde autour de vous.",
		"deja": "« Vous l'avez. Ne marchez pas là où vous l'avez fait tomber. »",
	},
	{
		"slug": "saemundr_d_akureyri", "sort": "sort:colere_de_l_hekla",
		"lieu": "lieu:akureyri", "nom": "Sæmundr", "race": "humain",
		"vocation": "elementaliste", "ecole_texte": "élémentaire",
		"presence": "Un élémentaliste maigre au regard amusé, qui revient du gouffre de l'Hekla "
					"avec de la suie jusqu'aux épaules.",
		"description": "Élémentaliste d'Akureyri, qui veille sur le gouffre de l'Hekla. Les "
					   "Islandais racontent qu'un Sæmundr le Savant a berné le diable en "
					   "personne ; il dit que c'était un démon mineur, et pas si bête.",
		"epreuve": {"titre": "Ce qui sort de l'Hekla", "item": "item:demon_majeur_de_la_destruction_tete",
					"quantite": 1,
					"description": "Un démon majeur de la destruction est remonté du gouffre de "
								   "l'Hekla. Sæmundr veut sa tête avant de vous montrer la Colère."},
		"accueil": "Sæmundr secoue la suie de ses manches. « Si vous cherchez la porte de "
				   "l'Enfer, elle est par là. Je vous déconseille d'y entrer. »",
		"q_sort": "« On parle d'une Colère de l'Hekla. »",
		"sort_texte": "« La Fureur frappe avec les quatre éléments. La Colère les prend d'en "
					  "dessous, là où ils sont chauds. Et ce qu'elle touche brûle longtemps. »",
		"q_suite": "« Et ce qui est au fond du gouffre ? »",
		"sort_suite": "« Les uns disent l'Enfer de Lucifer, les autres un monde de feu. J'ai "
					  "regardé. Je ne sais pas. Ça répond quand on l'appelle, c'est tout. »",
		"propose": "« Un démon majeur est remonté du gouffre. Rapportez-moi sa tête, et on "
				   "parlera de la Colère. »",
		"remis": "« Vous l'avez renvoyé. Si la Fureur élémentaire vous obéit déjà, je vous "
				 "apprends à la prendre par en dessous. »",
		"appris": "{pnj} vous fait descendre trois marches dans le gouffre, pas une de plus. La "
				  "leçon dure jusqu'à ce que la pierre sous vos pieds devienne trop chaude.",
		"deja": "« Vous l'avez. Ne descendez pas plus bas que je vous l'ai montré. »",
	},
	{
		"slug": "eginhard_du_granusturm", "sort": "sort:cisaille_des_vents",
		"lieu": "lieu:aix_la_chapelle", "nom": "Éginhard", "race": "hobbit",
		"vocation": "elementaliste", "ecole_texte": "élémentaire",
		"presence": "Un élémentaliste hobbit, menu, qui monte et descend les escaliers du "
					"Granusturm plus vite que les paladins.",
		"description": "Élémentaliste du Granusturm, aux côtés de Turpin. Il écrit la vie des "
					   "gens qu'il admire ; on dit qu'il a écrit celle de Charlemagne, et qu'il "
					   "était déjà petit.",
		"epreuve": {"titre": "Les ailes des gargouilles", "item": "item:gargouille_aile",
					"quantite": 2,
					"description": "Les gargouilles du double rempart d'Aix-la-Chapelle se "
								   "posent la nuit. Éginhard veut deux ailes de gargouille : celles "
								   "qu'on a coupées en vol."},
		"accueil": "Éginhard arrive essoufflé du haut de la tour. « Turpin tire, moi je les fais "
				   "descendre. C'est plus fatigant qu'on croit. »",
		"q_sort": "« On parle d'une Cisaille des vents. »",
		"sort_texte": "« Deux lames de vent qui se croisent sur une aile. La bête ne tombe pas "
					  "toujours, mais elle ne remonte pas tout de suite. »",
		"q_suite": "« C'est à la portée d'un débutant ? »",
		"sort_suite": "« C'est fait pour. Turpin a besoin de bras, pas de grands mages. »",
		"propose": "« Coupez-moi deux ailes de gargouille. En vol, si possible. »",
		"remis": "« En vol ? Bien. Si la Lame de vent vous obéit déjà, je vous apprends à en "
				 "croiser deux. »",
		"appris": "{pnj} vous fait viser les pigeons du Granusturm jusqu'au soir, sans jamais en "
				  "toucher un. « Juste l'air autour. C'est ça, la cisaille. »",
		"deja": "« Vous l'avez. Faites-les descendre ; Turpin s'occupe du reste. »",
	},
	{
		"slug": "gace_le_fauconnier", "sort": "sort:leurre_du_fauconnier",
		"lieu": "lieu:montmartre", "nom": "Maître Gace", "race": "elfe",
		"vocation": "menestrel", "ecole_texte": "illusoire",
		"presence": "Un ménestrel elfe au gant de fauconnier, qui chante à mi-voix sur la terrasse "
					"et regarde les griffons tourner au-dessus de la Butte.",
		"description": "Fauconnier et ménestrel de Montmartre. Il a écrit un long poème sur la "
					   "chasse, que les paladins citent sans l'avoir lu. Dame Geneviève lui "
					   "confie les griffons qu'on ne peut pas atteindre.",
		"epreuve": {"titre": "Faire descendre un grand dragon", "item": "item:grand_dragon_aile",
					"quantite": 1,
					"description": "Un grand dragon tourne parfois au-dessus de Lutecia sans "
								   "jamais descendre. Maître Gace veut une de ses ailes : la preuve "
								   "que vous l'avez fait plonger."},
		"accueil": "Maître Gace termine son couplet avant de vous regarder. « Les griffons "
				   "aiment la musique. Ils aiment surtout ce qu'ils croient voir en dessous. »",
		"q_sort": "« On parle d'un Leurre du fauconnier. »",
		"sort_texte": "« La Proie fantôme attire une bête. Le Leurre attire tout ce qui vole "
					  "autour, et le fait plonger sur moi, droit dans la ligne de la Lance. »",
		"q_suite": "« Et vous, au milieu ? »",
		"sort_suite": "« Moi, je chante, et je fais confiance aux paladins. C'est pour ça qu'on "
					  "ne l'apprend qu'ici. »",
		"propose": "« Faites plonger un grand dragon. Rapportez-moi une de ses ailes. »",
		"remis": "« Il a plongé. Si la Proie fantôme vous obéit déjà, je vous apprends le "
				 "Leurre. »",
		"appris": "La leçon se fait sur la terrasse, avec un faucon du Sacré-Cœur. {pnj} chante, "
				  "vous tenez le leurre, et le faucon plonge sur vous jusqu'au soir.",
		"deja": "« Vous l'avez. Ne le lancez jamais sans paladin derrière vous. »",
	},
	{
		"slug": "bernard_de_l_ecole", "sort": "sort:sur_des_epaules_de_geants",
		# Devant le scriptorium du Pont Bouju (porte de `link:scriptorium01_to_chartres` en
		# (62, 20)), sur la case praticable à sa gauche — joignable depuis les six portes de
		# rempart (`dev/tracer_chemins.js`) ; sans `cases`, il était sur toutes celles de la cité.
		"lieu": "lieu:chartres", "cases": [[61, 20]], "nom": "Maître Bernard", "race": "nain",
		"vocation": "lettre",
		"ecole_texte": "illusoire",
		"presence": "Un lettré nain assis sur l'épaule d'un ogre qui porte ses livres, dans la "
					"cour de l'école de Chartres.",
		"description": "Maître de l'école de Chartres. C'est lui, dit-on, qui a parlé le premier "
					   "des nains juchés sur des épaules de géants. Son ogre, qui s'appelle "
					   "Tierry, ne le contredit jamais.",
		"epreuve": {"titre": "De quoi écrire", "item": "item:Plume_d_oie", "quantite": 5,
					"description": "Maître Bernard ne demande pas de trophée : il veut cinq "
								   "plumes d'oie, pour que l'école continue d'écrire."},
		"accueil": "Maître Bernard vous regarde de haut, parce qu'il est assis sur un ogre. « On "
				   "voit plus loin d'ici. Vous devriez essayer. »",
		"q_sort": "« On parle de Sur des épaules de géants. »",
		"sort_texte": "« La Formule de clairvoyance éclaire celui qui la dit. Celle-ci éclaire "
					  "tous ceux qui l'entendent. Un savoir qu'on garde ne fait voir loin "
					  "personne. »",
		"q_suite": "« Pourquoi ne pas l'écrire, dans une école ? »",
		"sort_suite": "« Elle est écrite. Mais une formule partagée s'apprend à plusieurs, "
					  "à voix haute. Les livres sont très mauvais pour ça. »",
		"propose": "« Apportez-moi cinq plumes d'oie. L'école en use beaucoup. »",
		"remis": "« Cinq plumes. Si la Formule de clairvoyance vous obéit déjà, je vous "
				 "apprends à la dire pour les autres. »",
		"appris": "{pnj} réunit trois élèves dans la cour, et vous fait dire la formule jusqu'à "
				  "ce que le plus lent comprenne. Il vous remercie, eux aussi.",
		"deja": "« Vous l'avez. Dites-la toujours assez fort. »",
	},
	{
		"slug": "boutes_le_rescape", "sort": "sort:chant_des_sirenes",
		"lieu": "lieu:alexandrie", "nom": "Boutès", "race": "humain", "vocation": "menestrel",
		"ecole_texte": "illusoire",
		"presence": "Un ménestrel au teint cuivré, assis sur le quai face au Phare, qui chante "
					"en regardant la mer et s'arrête quand on s'approche.",
		"description": "Ménestrel d'Alexandrie. Il porte le nom du marin qui a sauté à la mer "
					   "en entendant les sirènes, et qu'on a repêché vivant. Il dit qu'il est "
					   "celui-là ; personne ne le croit.",
		"epreuve": {"titre": "L'énigme du sphinx", "item": "item:sphinx_tete", "quantite": 1,
					"description": "Un sphinx garde une route du désert au sud d'Alexandrie et "
								   "dévore ceux qui ne répondent pas. Boutès veut sa tête : « un "
								   "chant contre une question »."},
		"accueil": "Boutès s'arrête de chanter. « Vous avez entendu ? Non ? Tant mieux pour "
				   "vous. »",
		"q_sort": "« On parle d'un Chant des sirènes. »",
		"sort_texte": "« Je l'ai entendu, j'ai sauté, et je suis revenu. Ceux qui l'entendent "
					  "oublient de se défendre et viennent vers celui qui chante. »",
		"q_suite": "« Comment êtes-vous revenu ? »",
		"sort_suite": "« Quelqu'un m'a repêché. Je ne sais pas qui. Certains disent une déesse, "
					  "d'autres un pêcheur. Je préfère le pêcheur. »",
		"propose": "« Le sphinx du sud dévore ceux qui ne répondent pas. Rapportez-moi sa "
				   "tête. »",
		"remis": "« Vous avez répondu, ou vous avez frappé avant. Peu importe. Si l'Éventail de "
				 "folie vous obéit déjà, je vous apprends le Chant. »",
		"appris": "{pnj} vous apprend le chant les oreilles bouchées à la cire. À la fin, il "
				  "retire la cire et ne chante plus.",
		"deja": "« Vous l'avez. Ne le chantez jamais au bord de l'eau. »",
	},
	{
		"slug": "cuauhtlehuanitl_gardienne_aigle", "sort": "sort:liane_d_abattage",
		"lieu": "lieu:teotihuacan", "nom": "Cuauhtlehuanitl", "race": "elfe",
		"vocation": "druide", "ecole_texte": "de la nature",
		"presence": "Une druide elfe vêtue de plumes d'aigle, gardienne-aigle de Teotihuacan, "
					"qui tresse une liane aussi épaisse que son bras sur les marches d'une "
					"pyramide.",
		"description": "Gardienne-aigle de Teotihuacan. Son nom veut dire « l'aigle qui monte », "
					   "comme on nomme ici le soleil du matin. Elle garde le ciel comme les "
					   "gardiens-jaguars gardent la forêt.",
		"epreuve": {"titre": "Les dragons rouges des volcans", "item": "item:dragon_rouge_aile",
					"quantite": 2,
					"description": "Des dragons rouges descendent des volcans sur les champs de "
								   "Teotihuacan. Cuauhtlehuanitl veut deux de leurs ailes, "
								   "arrachées au sol."},
		"accueil": "Cuauhtlehuanitl serre un dernier nœud. « Les jaguars gardent la forêt. Nous, "
				   "le ciel. Le ciel est plus grand. »",
		"q_sort": "« On parle d'une Liane d'abattage. »",
		"sort_texte": "« Les Lianes de la canopée tiennent ce qui marche. La Liane d'abattage "
					  "monte, prend ce qui vole, et le ramène sur la terre. »",
		"q_suite": "« Vos paladins à vous ? »",
		"sort_suite": "« Les gardiens-jaguars. On leur ramène les bêtes au sol ; ils s'occupent "
					  "du reste. Peu d'entre eux sont de vrais nahuals. »",
		"propose": "« Les dragons rouges descendent des volcans. Rapportez-moi deux de leurs "
				   "ailes. »",
		"remis": "« Ils sont tombés. Si les Lianes de la canopée vous obéissent déjà, je vous "
				 "apprends à les faire monter. »",
		"appris": "{pnj} vous fait tresser une liane depuis l'aube. À midi, elle la lance au "
				  "ciel, et un aigle la rapporte. Le reste du jour, c'est à vous.",
		"deja": "« Vous l'avez. Au sol, la bête est à tout le monde. »",
	},
	{
		"slug": "itzcuauhtli_du_serpent_a_plumes", "sort": "sort:gardien_aigle",
		"lieu": "lieu:temple_du_serpent_a_plumes", "nom": "Itzcuauhtli", "race": "hobbit",
		"vocation": "chaman", "ecole_texte": "de la nature",
		"presence": "Un chaman hobbit au visage peint, perché sur une tête de serpent sculptée "
					"du temple, un aigle géant sur l'épaule.",
		"description": "Chaman des gardiens-aigles, au temple du Serpent à plumes. Son nom est "
					   "celui de l'aigle d'obsidienne des récits anciens ; ses aigles à lui sont "
					   "de chair et de plumes.",
		"epreuve": {"titre": "Les araignées de la falaise", "item": "item:araignee_geante_tete",
					"quantite": 3,
					"description": "Des araignées géantes tendent leurs toiles sur les falaises "
								   "où nichent les aigles. Itzcuauhtli veut trois de leurs têtes."},
		"accueil": "L'aigle d'Itzcuauhtli vous fixe avant lui. « Il décide d'abord. Moi, "
				   "ensuite. »",
		"q_sort": "« On parle d'un Gardien-aigle. »",
		"sort_texte": "« L'aigle sauvage vient, frappe et s'en va. Le gardien-aigle est élevé "
					  "ici : il reste, et il chasse dans le ciel ce qui s'y croit seul. »",
		"q_suite": "« Comment l'élevez-vous ? »",
		"sort_suite": "« On ne l'élève pas. On le laisse nous élever. Ça prend longtemps. »",
		"propose": "« Les araignées tendent leurs toiles là où nichent nos aigles. Trois têtes. »",
		"remis": "« Les nids sont libres. Si les Serres de l'aigle géant vous obéissent déjà, "
				 "je vous présente à eux. »",
		"appris": "{pnj} vous laisse avec un aigle, sans personne d'autre, jusqu'au soir. Il ne vous dit rien. "
				  "L'aigle, si.",
		"deja": "« Vous l'avez. Remerciez-le après chaque chasse. »",
	},
	{
		"slug": "kveldulfr_d_akureyri", "sort": "sort:meute_des_ulfhednar",
		"lieu": "lieu:akureyri", "nom": "Kveldúlfr", "race": "ogre", "vocation": "chaman",
		"ecole_texte": "de la nature",
		"presence": "Un chaman ogre en peau de loup, qui somnole le jour près des portes "
					"d'Akureyri et repart chasser au crépuscule.",
		"description": "Ulfheðinn d'Akureyri. Son nom veut dire « loup du soir » : on dit qu'il "
					   "change à la tombée de la nuit, et qu'il est de mauvaise humeur le matin.",
		"epreuve": {"titre": "Le loup géant des fjords", "item": "item:loup_geant_tete",
					"quantite": 1,
					"description": "Un loup géant chasse seul dans les fjords autour d'Akureyri "
								   "et refuse toutes les meutes. Kveldúlfr veut sa tête."},
		"accueil": "Kveldúlfr ouvre un œil. « Il fait encore jour. Revenez ce soir. » Il "
				   "soupire. « Bon. Parlez. »",
		"q_sort": "« On parle d'une Meute des Ulfheðnar. »",
		"sort_texte": "« Un loup qui chasse seul, c'est un loup qui meurt. On en appelle deux, "
					  "et ils ne lâchent plus la proie. »",
		"q_suite": "« Vous chassez pour Akureyri ? »",
		"sort_suite": "« Pour Akureyri et pour Reykjavik. Les bêtes, pas les gens. Jamais les "
					  "gens. »",
		"propose": "« Le loup géant des fjords chasse seul. Ça ne se fait pas. Rapportez-moi sa "
				   "tête. »",
		"remis": "« Il chassait seul. Si le Hurlement du loup vous obéit déjà, je vous apprends "
				 "à en appeler deux. »",
		"appris": "La leçon commence au crépuscule. {pnj} hurle, deux loups répondent, et vous "
				  "chassez avec eux jusqu'au matin.",
		"deja": "« Vous l'avez. Ne chassez jamais seul. »",
	},
	{
		"slug": "faelan_d_ossory", "sort": "sort:garde_du_faoladh",
		"lieu": "lieu:camelot", "nom": "Fáelán", "race": "humain", "vocation": "druide",
		"ecole_texte": "de la nature",
		"presence": "Un druide irlandais aux cheveux gris, venu d'Ossory, qui soigne les blessés "
					"de la Table ronde au pied des remparts de Camelot.",
		"description": "Druide d'Ossory, en Irlande. Son nom veut dire « petit loup ». Il ne dit "
					   "ni oui ni non quand on lui demande s'il est faoladh.",
		"epreuve": {"titre": "Les chiens d'Annwn", "item": "item:cwn_annwn_tete", "quantite": 1,
					"description": "Les chiens d'Annwn sortent des portails qui surgissent autour "
								   "de Camelot et chassent les égarés. Fáelán veut la tête de l'un "
								   "d'eux."},
		"accueil": "Fáelán finit un bandage avant de lever les yeux. « Vous cherchez votre chemin ? Non. "
				   "Alors vous voulez quelque chose. »",
		"q_sort": "« On parle d'une Garde du faoladh. »",
		"sort_texte": "« Le faoladh veille sur les blessés et les égarés jusqu'à ce que quelqu'un "
					  "vienne. Le soin qu'il donne reste sur le blessé, et le tient debout. »",
		"q_suite": "« Vous êtes faoladh ? »",
		"sort_suite": "« Je suis druide. Le reste, ça regarde la lune. »",
		"propose": "« Les chiens d'Annwn chassent les égarés autour de Camelot. Rapportez-moi "
				   "la tête de l'un d'eux. »",
		"remis": "« Un égaré de moins à pleurer. Si la Guérison des animaux vous obéit déjà, je "
				 "vous apprends la Garde. »",
		"appris": "{pnj} vous fait veiller un blessé de la Table ronde toute la nuit. Il ne "
				  "revient qu'au matin, et ne dit pas où il était.",
		"deja": "« Vous l'avez. Restez près des égarés. »",
	},
	{
		"slug": "corvin_de_valachie", "sort": "sort:ciel_de_charogne",
		"lieu": "lieu:bucarest", "nom": "Maître Corvin", "race": "nain",
		"vocation": "necromancien", "ecole_texte": "nécromantique",
		"presence": "Un nécromancien nain au manteau noir, entouré de corneilles mortes qui "
					"attendent sur les toits sans jamais croasser.",
		"description": "Nécromancien de Valachie. Il porte le nom du corbeau. Les paladins de la "
					   "région ne l'aiment pas, mais ils l'appellent quand un balaur sort de son "
					   "donjon.",
		"epreuve": {"titre": "Des corneilles pour l'hiver", "item": "item:corneille_noire",
					"quantite": 4,
					"description": "Maître Corvin veut quatre corneilles noires, abattues dans les "
								   "plaines de Valachie : « des neuves, pour remplacer celles que le "
								   "balaur a mangées »."},
		"accueil": "Les corneilles de Maître Corvin tournent la tête vers vous en même temps que "
				   "lui. « Elles ne mordent pas. Pas les vivants. »",
		"q_sort": "« On parle d'un Ciel de charogne. »",
		"sort_texte": "« Deux corneilles, c'est une volée. Trois, c'est un ciel. Et les morts ne "
					  "fuient pas les dragons. »",
		"q_suite": "« Les paladins vous laissent faire ? »",
		"sort_suite": "« Quand un balaur sort, ils me laissent faire. Le reste du temps, ils "
					  "font semblant de ne pas me voir. Ça me va. »",
		"propose": "« Rapportez-moi quatre corneilles noires, abattues dans les plaines. »",
		"remis": "« Quatre. Elles serviront. Si la Volée funèbre vous obéit déjà, je vous "
				 "apprends à en tenir une de plus. »",
		"appris": "{pnj} relève les quatre corneilles devant vous, puis vous fait tenir les "
				  "trois premières jusqu'à ce que vos mains tremblent.",
		"deja": "« Vous l'avez. Tenez-les, elles ne se tiennent pas seules. »",
	},
	{
		"slug": "sennedjem_d_abou_simbel", "sort": "sort:gardien_d_abou_simbel",
		"lieu": "lieu:grand_temple_d_abou_simbel", "nom": "Sennedjem", "race": "humain",
		"vocation": "necromancien", "ecole_texte": "nécromantique",
		"presence": "Un nécromancien momifié, aux bandelettes propres et aux outils de bâtisseur "
					"à la ceinture, qui mesure l'ombre des colosses de la façade.",
		"description": "Bâtisseur de tombeaux de la cour de Néfertiti, mort depuis longtemps et "
					   "bien conservé. Il se dit « serviteur dans la Place de Vérité », sans "
					   "expliquer où elle est.",
		"epreuve": {"titre": "Le ver des sables", "item": "item:vers_des_sables_tete",
					"quantite": 1,
					"description": "Un ver des sables creuse sous les tombeaux de la rive et "
								   "fait s'effondrer les chambres. Sennedjem veut sa tête."},
		"accueil": "Sennedjem achève de mesurer une ombre. « Les vivants viennent rarement "
				   "jusqu'ici. Vous avez donc une affaire pressante, ou vous cherchez votre chemin. »",
		"q_sort": "« On parle d'un Gardien d'Abou Simbel. »",
		"sort_texte": "« La Momie royale lève un roi. Le Gardien en lève deux, de part et "
					  "d'autre de vous, comme les colosses de la façade. »",
		"q_suite": "« Et la reine Néfertiti ? »",
		"sort_suite": "« La reine a trouvé une autre manière de durer. Moi, je bâtis des "
					  "tombeaux. Je ne pose pas de questions. »",
		"propose": "« Un ver des sables creuse sous mes tombeaux. Rapportez-moi sa tête. »",
		"remis": "« Les chambres tiendront. Si la Momie royale vous obéit déjà, je vous "
				 "apprends le rituel des deux gardiens. »",
		"appris": "Le rituel dure une journée entière, à l'ombre des colosses. Quand il finit, "
				  "{pnj} reprend ses mesures sans un mot.",
		"deja": "« Vous l'avez. Laissez-les retourner dormir après. »",
	},
	{
		"slug": "philibert_des_catacombes", "sort": "sort:ossuaire_des_catacombes",
		# En surface, sur la SEULE case de Lutecia qui descend aux catacombes (nœud Lutecia de
		# `link:lutecia_to_catacombes0001`) — sans `cases`, il était sur toutes celles de la cité.
		"lieu": "lieu:lutecia", "cases": [[26, 27]], "nom": "Philibert", "race": "hobbit",
		"vocation": "necromancien", "ecole_texte": "nécromantique",
		"presence": "Un nécromancien hobbit couvert de poussière de calcaire, une lanterne "
					"éteinte à la main, qui vient de remonter des catacombes.",
		"description": "Nécromancien des catacombes de Lutecia. On raconte qu'un Philibert s'y "
					   "est perdu des années ; il dit qu'il ne s'est jamais perdu, qu'il "
					   "restait.",
		"epreuve": {"titre": "Les crânes des ossuaires", "item": "item:crane", "quantite": 5,
					"description": "Des goules ont dérangé les ossuaires des catacombes. "
								   "Philibert veut cinq crânes, ramassés là où elles les ont "
								   "jetés, pour remettre les murs en ordre."},
		"accueil": "Philibert souffle sur sa lanterne, qui est déjà éteinte. « Pas besoin de "
				   "lumière, là-dessous. Les os, on les entend. »",
		"q_sort": "« On parle d'un Ossuaire des catacombes. »",
		"sort_texte": "« La Levée des ossements en lève deux, à la hâte. Celui qui sait lire les "
					  "murs d'os en lève trois, et ils connaissent le chemin. »",
		"q_suite": "« Vous vous êtes vraiment perdu, là-dessous ? »",
		"sort_suite": "« On dit ça. Je restais. Les cristaux jaunes sont tout au fond, vous "
					  "savez. Mais ça, je ne le dis pas à tout le monde. »",
		"propose": "« Les goules ont défait mes murs d'os. Rapportez-moi cinq crânes. »",
		"remis": "« Cinq. Ils retrouveront leur place. Si la Levée des ossements vous obéit "
				 "déjà, je vous apprends à lire les murs. »",
		"appris": "{pnj} vous fait descendre sans lanterne et ranger les cinq crânes à tâtons. "
				  "Quand vous remontez, il fait nuit dehors aussi.",
		"deja": "« Vous l'avez. Rangez-les en partant. »",
	},
	{
		"slug": "anna_darvulia", "sort": "sort:baiser_de_la_lamie",
		"lieu": "lieu:pannonie", "nom": "Anna Darvulia", "race": "humain",
		"vocation": "necromancien", "ecole_texte": "nécromantique",
		"presence": "Une femme très pâle en robe sombre, qui attend au bord de la route, toujours "
					"à l'ombre, et sourit sans montrer les dents.",
		"description": "Lamie de Pannonie, suivante d'une comtesse dont elle ne dit pas le nom. "
					   "Elle enseigne aux vivants, et personne ne sait ce qu'elle y gagne.",
		"epreuve": {"titre": "Trois fioles de sang", "item": "item:Fiole_de_sang_fige",
					"quantite": 3,
					"description": "Anna Darvulia veut trois fioles de sang figé. Elle ne dit pas "
								   "à quoi elles serviront."},
		"accueil": "Anna Darvulia recule d'un pas, pour rester à l'ombre. « Le soleil est encore "
				   "haut. Parlons vite. »",
		"q_sort": "« On parle d'un Baiser de la lamie. »",
		"sort_texte": "« Le baiser du vampire boit. Le nôtre boit davantage, et celui qui le "
					  "reçoit n'a plus envie de se défendre. »",
		"q_suite": "« Pourquoi l'apprendre à un vivant ? »",
		"sort_suite": "« Parce que vous me l'avez demandé. » Elle sourit. « Ce n'est pas une "
					  "réponse, je sais. »",
		"propose": "« Apportez-moi trois fioles de sang figé. Ne me demandez pas pourquoi. »",
		"remis": "Elle prend les fioles sans les regarder. « Merci. Si le Baiser du vampire "
				 "vous obéit déjà, je vous apprends le nôtre. »",
		"appris": "La leçon se fait au crépuscule. Quand elle finit, {pnj} n'est plus là, et "
				  "vous ne l'avez pas vue partir.",
		"deja": "« Vous l'avez. N'en abusez pas. Nous, nous en avons abusé. »",
	},
	{
		"slug": "kisir_assur_l_exorciste", "sort": "sort:flamme_de_maqlu",
		"lieu": "lieu:petra", "nom": "Kisir-Aššur", "race": "nain", "vocation": "repurgateur",
		"ecole_texte": "démoniaque",
		"presence": "Un répurgateur nain venu de Babylone, qui brûle de petites figurines "
					"d'argile dans une coupe de bronze, à l'abri d'un tombeau taillé dans la "
					"roche.",
		"description": "Exorciste de Babylone, réfugié à Petra avec ses tablettes. Il récite le "
					   "Maqlû, « la Brûlure », en huit tablettes, et dit qu'il en manque une.",
		"epreuve": {"titre": "La tête d'un prince", "item": "item:prince_demon_tete",
					"quantite": 1,
					"description": "Un prince démon s'est installé dans un des donjons des "
								   "tombeaux royaux de Petra. Kisir-Aššur veut sa tête avant de "
								   "vous apprendre la Flamme."},
		"accueil": "Kisir-Aššur jette une figurine dans la coupe. « On brûle l'image, et le "
				   "démon brûle. C'est simple. C'est long. »",
		"q_sort": "« On parle d'une Flamme de Maqlû. »",
		"sort_texte": "« Le Fléau des démons brûle la chair. La Flamme de Maqlû brûle aussi ce "
					  "qui la fait tenir : sa magie. »",
		"q_suite": "« Et la tablette qui manque ? »",
		"sort_suite": "« Les uns disent qu'elle est restée à Babylone. Les autres qu'elle n'a "
					  "jamais été écrite. Moi, je récite les huit, et je laisse un silence à "
					  "la place. »",
		"propose": "« Un prince démon tient un donjon des tombeaux. Rapportez-moi sa tête. »",
		"remis": "« Un prince. Si le Fléau des démons vous obéit déjà, je vous apprends la "
				 "Brûlure. »",
		"appris": "La leçon dure huit tablettes et un silence. {pnj} brûle la dernière "
				  "figurine quand vous avez fini.",
		"deja": "« Vous l'avez. Récitez-les toutes, même la manquante. »",
	},
	{
		"slug": "berose_le_chaldeen", "sort": "sort:ailes_du_roi_des_vents",
		"lieu": "lieu:alexandrie", "nom": "Bérose", "race": "elfe", "vocation": "demoniste",
		"ecole_texte": "démoniaque",
		"presence": "Un démoniste elfe venu de Babylone, entouré de tablettes d'argile dans un "
					"recoin de la grande bibliothèque d'Alexandrie.",
		"description": "Démoniste de Babylone, qui recopie en grec l'histoire de sa cité pour la "
					   "bibliothèque d'Alexandrie. On dit qu'il la recopie depuis très longtemps.",
		"epreuve": {"titre": "Les démons guerriers", "item": "item:demon_guerrier_tete",
					"quantite": 2,
					"description": "Des démons guerriers sont sortis d'un donjon du delta. Bérose "
								   "veut deux de leurs têtes : « Pazuzu ne parle qu'à ceux qui "
								   "ont déjà parlé à ses semblables »."},
		"accueil": "Bérose pose son calame. « Pazuzu, oui. On me demande toujours Pazuzu. Jamais "
				   "Lamashtu, contre qui on l'appelait. »",
		"q_sort": "« On parle des Ailes du roi des vents. »",
		"sort_texte": "« Les ailes de Pazuzu se prêtent. Si vous savez lui parler, il les prête "
					  "plus longtemps, et elles portent plus vite. »",
		"q_suite": "« Pourquoi appelait-on un démon contre un autre ? »",
		"sort_suite": "« Parce que contre Lamashtu, il fallait pire qu'elle. Babylone n'a "
					  "jamais eu peur de ce genre de calcul. »",
		"propose": "« Rapportez-moi deux têtes de démon guerrier. Pazuzu saura que vous les "
				   "connaissez. »",
		"remis": "« Il saura. Si les Ailes de Pazuzu vous obéissent déjà, je vous apprends à "
				 "lui parler. »",
		"appris": "{pnj} vous fait réciter l'invocation en akkadien jusqu'à ce que le vent se "
				  "lève dans la bibliothèque. Les copistes n'ont pas l'air surpris.",
		"deja": "« Vous l'avez. Rendez-lui ses ailes à l'heure. »",
	},
	{
		"slug": "asaf_le_vizir", "sort": "sort:anneau_de_salomon",
		"lieu": "lieu:petra", "nom": "Âsaf", "race": "hobbit", "vocation": "repurgateur",
		"ecole_texte": "démoniaque",
		"presence": "Un répurgateur hobbit aux bagues trop grandes pour ses doigts, venu de "
					"Jérusalem par la route de l'encens, qui marchande avec les caravaniers.",
		"description": "Répurgateur de Jérusalem. Il se dit héritier d'un vizir de Salomon, celui "
					   "qui fit venir un trône en un clin d'œil ; il ne fait venir que des "
					   "caravanes, et en prenant son temps.",
		"epreuve": {"titre": "Sang de démon", "item": "item:Sang_demon_seche", "quantite": 3,
					"description": "Âsaf veut trois mesures de sang de démon séché. « L'anneau ne "
								   "se grave pas à l'encre. »"},
		"accueil": "Âsaf fait tourner une bague trop grande autour de son doigt. « Celle-ci "
				   "n'est pas la bonne. La bonne, personne ne l'a. »",
		"q_sort": "« On parle d'un Anneau de Salomon. »",
		"sort_texte": "« Le Fouet de domination fait saigner. L'Anneau lie : la créature perd "
					  "sa magie et ne voit plus que celui qui la tient. »",
		"q_suite": "« L'anneau de Salomon existe-t-il ? »",
		"sort_suite": "« À Jérusalem, on dit qu'il est perdu. À Babylone, qu'il n'a jamais "
					  "existé. Moi, je dis que le sceau suffit. »",
		"propose": "« Apportez-moi trois mesures de sang de démon séché. »",
		"remis": "« Il est bien sec. Si le Fouet de domination vous obéit déjà, je vous grave "
				 "le sceau. »",
		"appris": "{pnj} trace le sceau dans le sable, encore et encore, jusqu'à ce que vous le "
				  "traciez sans regarder.",
		"deja": "« Vous l'avez. Le lien tient tant que vous tenez. »",
	},
]


def _recompenses(niveau: int) -> dict:
	"""300 XP / 2750 cuivre au niveau 10 (la Lance : 300 / 2500) — linéaire en dessous."""
	return {"xp": 40 + 26 * niveau, "cuivre": 250 * (niveau + 1)}


def _epreuve_id(m: dict) -> str:
	return "quete:epreuve_" + m["sort"].split(":", 1)[1]


def portrait(m: dict) -> str:
	return f"maitre_{m['slug']}01.jpg"


def _dialogue(m: dict, nom_sort: str, nom_base: str) -> dict:
	"""Arbre commun aux maîtres (celui de la Lance, paramétré) : l'épreuve (service `apport`),
	puis l'enseignement (service `enseignement`) réservé à qui l'a réussie. Les refus sont
	PARLÉS : le maître dit ce qui manque."""
	reussie = {"quete_reussie": {"id": _epreuve_id(m)}}
	recevoir = f"« Je viens apprendre la forme : {nom_sort}. »"
	return {
		"noeud_depart": "accueil",
		"noeuds": {
			"accueil": {
				"texte": m["accueil"],
				"choix": [
					{"id": "sort", "label": m["q_sort"], "next": "sort_01"},
					{"id": "epreuve", "label": "« Que faut-il pour l'apprendre ? »",
					 "condition": {"apport_offert": True}, "next": "epreuve_propose"},
					{"id": "remettre", "label": "(Montrer ce que vous rapportez.)",
					 "condition": {"apport_possible": True},
					 "action": {"service": "apport", "op": "remettre"}},
					# Épreuve en cours, rien à remettre dans le sac : le maître rappelle le reste.
					{"id": "rappel", "label": "« Où en est l'épreuve ? »",
					 "condition": {"apport_en_cours": True, "apport_possible": False},
					 "next": "epreuve_rappel"},
					{"id": "apprendre", "label": recevoir,
					 "condition": {**reussie, "enseignement_possible": True},
					 "action": {"service": "enseignement", "op": "apprendre"}},
					{"id": "base", "label": recevoir,
					 "condition": {**reussie, "enseignement_connu": False,
								   "enseignement_prerequis_manquant": True},
					 "next": "pas_pret_base"},
					{"id": "niveau", "label": recevoir,
					 "condition": {**reussie, "enseignement_connu": False,
								   "enseignement_prerequis_manquant": False,
								   "enseignement_niveau_insuffisant": True},
					 "next": "pas_pret_niveau"},
					{"id": "points", "label": recevoir,
					 "condition": {**reussie, "enseignement_connu": False,
								   "enseignement_prerequis_manquant": False,
								   "enseignement_niveau_insuffisant": False,
								   "enseignement_points_insuffisants": True},
					 "next": "pas_pret_points"},
					{"id": "deja", "label": f"« Une question sur la forme : {nom_sort}. »",
					 "condition": {"enseignement_connu": True}, "next": "deja"},
					{"id": "fin", "label": "(Prendre congé.)", "next": "fin"},
				],
			},
			"sort_01": {"texte": m["sort_texte"],
						"choix": [{"id": "suite", "label": m["q_suite"], "next": "sort_02"}]},
			"sort_02": {"texte": m["sort_suite"],
						"choix": [{"id": "retour", "label": "(Revenir à la conversation.)", "next": "accueil"},
								  {"id": "fin", "label": "(Prendre congé.)", "next": "fin"}]},
			"epreuve_propose": {
				"texte": m["propose"] + " (Récompense : {xp} XP, {prime}.)",
				"choix": [{"id": "accepter", "label": "« J'y vais. »",
						   "action": {"service": "apport", "op": "accepter"}},
						  {"id": "plus_tard", "label": "« Pas encore. »", "next": "fin"}],
			},
			"epreuve_accepte": {
				"texte": "« {quantite} × {objet}. Je serai là. »",
				"choix": [{"id": "fin", "label": "(Partir.)", "next": "fin"}],
			},
			"epreuve_partiel": {
				"texte": "{pnj} examine ce que vous rapportez et le pose de côté. « Il en manque "
						 "encore {reste}. »",
				"choix": [{"id": "fin", "label": "(Repartir.)", "next": "fin"}],
			},
			"epreuve_rappel": {
				"texte": "« Il m'en manque encore {reste} : {objet}. Je vous attends. »",
				"choix": [{"id": "retour", "label": "(Revenir à la conversation.)", "next": "accueil"},
						  {"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"epreuve_remis": {
				"texte": m["remis"],
				"choix": [{"id": "retour", "label": "(Revenir à la conversation.)", "next": "accueil"},
						  {"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"appris": {
				"texte": m["appris"],
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"refus": {
				"texte": "{pnj} secoue la tête. « Pas aujourd'hui. Revenez plus tard. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"pas_pret_base": {
				"texte": f"« Tout part de la forme simple : {nom_base}. Apprenez-la d'abord, dans "
						 f"un grimoire. Ensuite, revenez. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"pas_pret_niveau": {
				"texte": f"« Votre magie {m['ecole_texte']} n'est pas encore assez sûre pour ça. "
						 f"Revenez plus tard. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"pas_pret_points": {
				"texte": "« Il vous faudra {cout} points pour la retenir. Vous ne les avez "
						 "pas encore. »",
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
			"deja": {
				"texte": m["deja"],
				"choix": [{"id": "fin", "label": "(Prendre congé.)", "next": "fin"}],
			},
		},
	}


def pnj_doc(m: dict, sorts: dict) -> dict:
	e = m["epreuve"]
	sort = sorts[m["sort"]]
	base = sorts[FORME_SIMPLE[m["sort"]]]
	return {
		"_id": "pnj:" + m["slug"],
		"type": "pnj",
		"nom": m["nom"],
		"race": m["race"],
		"vocation": m["vocation"],
		"portrait": portrait(m),
		"description": m["description"],
		"services": {
			"apport": {
				"offre": {"id": _epreuve_id(m), "titre": e["titre"], "description": e["description"],
						  "item": e["item"], "quantite": e["quantite"], "unique": True,
						  "recompenses": _recompenses(sort["niveau"])},
				"noeuds": {"accepte": "epreuve_accepte", "partiel": "epreuve_partiel",
						   "remis": "epreuve_remis"},
			},
			"enseignement": {"sort": m["sort"], "noeuds": {"appris": "appris", "refus": "refus"}},
		},
		"dialogue": _dialogue(m, sort["nom"], base["nom"]),
	}


def entree_presence(m: dict) -> dict:
	"""`cases` (optionnel) : le maître ne se tient que sur ces cases du lieu (`utils/pnj`)."""
	entree = {"character": "pnj:" + m["slug"], "nom": m["nom"], "portrait": portrait(m),
			  "probabilite": 1, "description": m["presence"]}
	if m.get("cases"):
		entree["cases"] = m["cases"]
	return entree


def construire(base: dict) -> tuple:
	"""`(docs, erreurs)` : formes simples de niveau 10 + leurs grimoires, formes enseignées,
	maîtres, lieux enrichis de leur présence."""
	docs, erreurs = [], []
	sorts = {d["_id"]: d for d in base.values() if d.get("type") == "sort"}
	sorts.update({d["_id"]: d for d in BASES + SORTS_ENSEIGNES})

	def _neuf(doc):
		existant = base.get(doc["_id"])
		if existant is None:
			docs.append(doc)
		elif not deja_importe(doc, existant):
			erreurs.append(f"{doc['_id']} : `_id` déjà pris par un doc différent")

	def _maitre(doc):
		"""Un maître DÉJÀ importé se met à jour : doc relu + champs produits (fusion, CLAUDE.md
		§ 11). Seul un `pnj:*` qui enseigne SA forme est le nôtre — tout autre est une collision."""
		existant = base.get(doc["_id"])
		sort = doc["services"]["enseignement"]["sort"]
		if existant is None or deja_importe(doc, existant):
			_neuf(doc)
		elif ((existant.get("services") or {}).get("enseignement") or {}).get("sort") == sort:
			docs.append({**_sans_rev(existant), **doc})
		else:
			erreurs.append(f"{doc['_id']} : `_id` déjà pris par un doc différent")

	# Tout ce que les docs citent doit exister : formes simples, composants, trophées, espèces.
	cites = set(FORME_SIMPLE.values()) - {d["_id"] for d in BASES}
	for doc in BASES + SORTS_ENSEIGNES:
		cites |= {c["item"] for c in doc.get("composants") or []}
		if doc.get("invocation"):
			cites.add(doc["invocation"]["espece"])
			if doc["invocation"].get("profil"):
				cites.add(doc["invocation"]["profil"])
	cites |= {m["epreuve"]["item"] for m in MAITRES}
	erreurs += [f"{i} absent du dump" for i in sorted(cites) if i not in base]

	for doc in BASES:
		_neuf(doc)
	neufs = [d for d in docs if d["type"] == "sort"]
	grim_docs, _lignes, grim_erreurs = grimoires.grimoires_manquants(base, neufs)
	# Seulement les grimoires des formes SIMPLES créées ici (les formes enseignées n'en ont pas,
	# par décision) : `grimoires_manquants` rend aussi ceux de tout autre sort orphelin.
	nos = {d["_id"].split(":", 1)[1] for d in BASES}
	docs += [d for d in grim_docs
			 if d["_id"].split(":", 1)[1].removeprefix("grimoire_") in nos
			 or str(d.get("objet_final") or "").removeprefix("grimoire_") in nos]
	erreurs += [e for e in grim_erreurs if any(n in e for n in nos) or "aucune recette" in e]
	for doc in SORTS_ENSEIGNES:
		_neuf(doc)

	presences = {}
	for m in MAITRES:
		_maitre(pnj_doc(m, sorts))
		presences.setdefault(m["lieu"], []).append(entree_presence(m))
	# Un maître DÉPLACÉ quitte son ancien lieu : tout lieu du dump qui porte encore l'entrée
	# d'un maître posté ailleurs est réémis sans elle.
	poste = {"pnj:" + m["slug"]: m["lieu"] for m in MAITRES}
	for lieu_id, lieu in base.items():
		if lieu.get("type") != "lieu" or lieu_id in presences:
			continue
		if any(poste.get((p or {}).get("character"), lieu_id) != lieu_id
			   for p in lieu.get("pnj") or []):
			presences[lieu_id] = []
	for lieu_id, entrees in presences.items():
		lieu = base.get(lieu_id)
		if lieu is None:
			erreurs.append(f"{lieu_id} absent du dump")
			continue
		# Entrées de présence des maîtres : ajoutées, ou RÉÉCRITES si elles ont changé, ou
		# RETIRÉES si le maître est posté ailleurs ; les autres entrées restent telles quelles.
		presence = list(lieu.get("pnj") or [])
		change = False
		ailleurs = [p for p in presence
					if poste.get((p or {}).get("character"), lieu_id) != lieu_id]
		if ailleurs:
			presence = [p for p in presence if p not in ailleurs]
			change = True
		for entree in entrees:
			rang = next((i for i, p in enumerate(presence)
						 if (p or {}).get("character") == entree["character"]), None)
			if rang is None:
				presence.append(entree)
				change = True
			elif presence[rang] != entree:
				presence[rang] = entree
				change = True
		if change:
			lieu = copy.deepcopy(_sans_rev(lieu))
			if presence:
				lieu["pnj"] = presence
			else:
				lieu.pop("pnj", None)
			docs.append(lieu)
	return docs, erreurs


def _affiche(chemin) -> str:
	try:
		return os.path.relpath(chemin, RACINE)
	except ValueError:
		return os.path.abspath(chemin)


def main(argv=None) -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	chemin = args.dump or dernier_dump()
	base = {d["_id"]: d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")}
	docs, erreurs = construire(base)
	if erreurs:
		print(f"REFUS — {len(erreurs)} erreur(s), rien n'est écrit :")
		for e in erreurs:
			print("  · " + e)
		return 1
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	compte = {}
	for d in docs:
		compte[d["type"]] = compte.get(d["type"], 0) + 1
	print(f"{len(docs)} doc(s) écrits dans {_affiche(args.sortie)} — "
		  + ", ".join(f"{n} {t}" for t, n in sorted(compte.items())) + ".")
	return 0


if __name__ == "__main__":
	sys.exit(main())

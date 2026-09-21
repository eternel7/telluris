#!/usr/bin/env python
# dev/gen_fabrication_matieres.py
# Ce qu'une MATIÈRE apporte à une pièce fabriquée sur mesure — bloc `fabrication` sur les
# docs `item:*` de matière première.
#
# Sans ce bloc, une matière reste utilisable dans une commande (elle coûte son prix et pèse
# son poids) mais n'apporte AUCUNE propriété : `fabrication.proprietes_matiere` rend un bloc
# vide. C'est le comportement d'avant pour les 1 324 items en base — aucune migration.
#
# ⚠️ AUCUNE RECETTE N'EST TOUCHÉE, et c'est délibéré. Ajouter un intrant à une recette ouvre
# un point de vente pour lui (`appro_leaves_categorie` → `approvisionner`) et risque la
# FAUSSE FEUILLE (une matière qu'une recette produit ailleurs n'est plus jamais livrée, ce
# qui gèle en silence toutes les recettes qui la citent — cf. compétence telluris-economie).
# Ce script ne fait qu'ENRICHIR des docs item existants.
#
# ⚠️ Les matières retenues sont toutes CONSOMMÉES par au moins un métier : c'est la première
# des deux portes de `commande.matiere_acceptee` (→ `marche.besoins_lieu`). La seconde est le
# tag `fabrication_<categorie ou sous_categorie de la pièce>` posé sur le doc matière, qui
# l'ouvre à une famille d'objets sans passer par les recettes du lieu — ce script ne pose pas
# de tag, il ne fait qu'écrire le bloc `fabrication` que les DEUX portes exigent.
#
# ⚠️ RELANÇABLE À VOLONTÉ, SUR UN DUMP FRAIS. `admin_import_bulk` fait un PUT COMPLET : relire
# un dump périmé écraserait les retouches faites depuis. Sans `--dump`, le script écrit donc
# lui-même un dump frais (`utils/dump.ecrire_dump_frais` — le code des outils de /admin/dev-tools
# et de /admin/exports), ce qui exige CouchDB : à lancer dans le conteneur.
#
# ⚠️ LE FICHIER NE PORTE QUE LE DIFF. Seuls les docs dont le bloc `fabrication` CHANGE partent à
# l'import ; un doc déjà à jour est écarté, et sans rien à changer aucun fichier n'est écrit. Le
# doc est repris DU DUMP, seul `fabrication` y est écrasé : une clé ajoutée à la main survit à
# l'import (PUT complet). Relancer juste après un import rend donc un lot vide — c'est le signe
# que la base est à jour. Un item absent de la base est signalé et sauté (jamais créé).
#
# ⚠️ ORPHELINS. Une matière du dump qui porte un bloc `fabrication` de MATIÈRE (`nom` /
# `modificateurs`) absent de la table — posé à la main, ou retiré de la table depuis — est
# LISTÉE, jamais écrite ni vidée : à reporter dans la table ou à nettoyer dans /admin/table.
# Les variantes sur mesure (`fabrication.base_item`) ne sont pas des matières et sont ignorées.
#
# Usage :
#   python dev/gen_fabrication_matieres.py                       # dump frais (conteneur)
#   python dev/gen_fabrication_matieres.py --dump jsons/telluris-dump-….json
# Sortie (📥 Importer depuis /admin/dev-tools, ou /admin -> Import en masse) :
#   jsons/fabrication_matieres_a_importer.json

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import fabrication                           # noqa: E402
from utils import dump as dump_util                     # noqa: E402

SORTIE = "jsons/fabrication_matieres_a_importer.json"

# ── La table ────────────────────────────────────────────────────────────────────
# `nom`  : fragment ajouté au nom de la pièce (« Épée longue en acier au cristal de feu »).
# `modificateurs` : composés par `fabrication.appliquer_modificateurs` — additif sur les
#   `bonus_*`, fusion clé à clé sur `bonus`, multiplicatif sur `poids`/`valeur`, palier le
#   plus haut sur `rarete`. Tout champ hors de `CLES_MODIFIABLES` serait ignoré.
#
# ⚠️ Volontairement SOBRE. Ces valeurs s'ajoutent à celles de l'objet de base et se cumulent
# entre matières (× quantité) : les armes réelles de la base tiennent dans +2/+3 de dégâts et
# 17-30 de PA, une matière qui donnerait +10 déclasserait tout le contenu authoré d'un coup.
# Le levier de rareté, lui, est le PRIX (`valeur`), qui se propage au coût de la commande.
MATIERES = {
	"item:fer": {
		"nom": "en fer",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 1.05}},
	},
	"item:acier": {
		"nom": "en acier",
		"modificateurs": {"bonus_degats": 2, "bonus_pa": 2,
						  "poids": {"facteur": 1.05}, "valeur": {"facteur": 1.3}},
	},
	"item:bronze": {
		"nom": "en bronze",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 1.1},
						  "valeur": {"facteur": 0.9}},
	},
	"item:plomb": {
		# Lourde et sourde : elle frappe fort et se porte mal. Le poids EST le contrepoids.
		"nom": "plombé",
		"modificateurs": {"bonus_degats": 2, "poids": {"facteur": 1.4},
						  "valeur": {"facteur": 0.8}},
	},
	"item:argent": {
		# L'argent est le métal des canaux : `item:Epee_argent` porte déjà bonus_pm 4 et
		# bonus Int 2 — la matière prolonge cette ligne au lieu d'en ouvrir une autre.
		"nom": "aux ferrures d'argent",
		"modificateurs": {"bonus_pm": 3, "bonus": {"Int": 1},
						  "valeur": {"facteur": 1.8}, "rarete": "peu_commun"},
	},
	"item:cuir": {
		"nom": "à garniture de cuir",
		"modificateurs": {"bonus_pa": 1, "poids": {"facteur": 0.95}},
	},
	"item:tendons": {
		"nom": "à ligature de tendons",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 0.95}},
	},
	"item:os": {
		"nom": "à poignée d'os",
		"modificateurs": {"bonus_degats": 1, "poids": {"facteur": 0.9}},
	},
	"item:crocs": {
		"nom": "à garde de crocs",
		"modificateurs": {"bonus_degats": 2, "valeur": {"facteur": 1.2}},
	},
	"item:gemmes": {
		"nom": "serti d'une gemme",
		"modificateurs": {"bonus_pm": 4, "bonus": {"Vol": 1},
						  "valeur": {"facteur": 2.0}, "rarete": "rare"},
	},
	"item:metaux_precieux": {
		"nom": "à incrustations précieuses",
		"modificateurs": {"bonus": {"Cha": 2}, "valeur": {"facteur": 2.5},
						  "rarete": "rare"},
	},
	"item:perles": {
		"nom": "perlé",
		"modificateurs": {"bonus": {"Cha": 1}, "valeur": {"facteur": 1.6}},
	},

	# ── Composants et parties de créatures (lot du 21/09/2026) ──────────────────
	"item:Empennage_de_maitre": {
		"nom": "de la Maîtrise",
		"modificateurs": {"bonus_degats": 1, "bonus_cc": 2, "bonus_initiative": 1, "poids": {"facteur": 0.95}, "valeur": {"facteur": 1.3}},
	},
	"item:Encre_magique": {
		"nom": "aux Inscriptions magiques",
		"modificateurs": {"bonus_pm": 2, "bonus": {"Int": 1, "Vol": 1}, "effets": {"pm": 5, "duree": 2}, "valeur": {"facteur": 1.5}, "rarete": "rare"},
	},
	"item:Fetiche_envoutement": {
		"nom": "Envoûté",
		"modificateurs": {"bonus_pm": 2, "bonus": {"Vol": 2}, "effets": {"buffs": {"Vol": 1}, "duree": 3}, "valeur": {"facteur": 1.5}, "rarete": "peu_commun"},
	},
	"item:Fiole_de_sang_fige": {
		"nom": "du Sang Figé",
		"modificateurs": {"bonus_degats": 1, "bonus_pv": 3, "effets": {"pv": 5}, "valeur": {"facteur": 1.2}},
	},
	"item:Fiole_sang_bete": {
		"nom": "Bestial",
		"modificateurs": {"bonus_degats": 1, "bonus": {"F": 1, "V": 1}, "effets": {"buffs": {"F": 1}, "duree": 2}, "valeur": {"facteur": 1.2}},
	},
	"item:Eau_benite": {
		"nom": "Béni",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 1}, "effets": {"pv": 5}, "valeur": {"facteur": 1.4}, "rarete": "peu_commun"},
	},
	"item:Fragments_ame": {
		"nom": "Hanté",
		"modificateurs": {"bonus_pm": 3, "bonus": {"Int": 1, "Vol": 2}, "effets": {"pm": 5, "regen_pm": 1}, "valeur": {"facteur": 2}, "rarete": "rare"},
	},
	"item:Graine_sacree": {
		"nom": "Sacrée",
		"modificateurs": {"bonus_pv": 3, "bonus": {"Vol": 1}, "effets": {"pv": 5, "regen_pv": 1, "duree": 3}, "valeur": {"facteur": 1.5}, "rarete": "peu_commun"},
	},
	"item:Poison_de_base": {
		"nom": "Empoisonné",
		"modificateurs": {"bonus_degats": 2, "effets": {"pv": -5, "duree": 2}, "valeur": {"facteur": 1.3}},
	},
	"item:Poudre_amethyste": {
		"nom": "d’Améthyste",
		"modificateurs": {"bonus_pm": 2, "bonus": {"Vol": 1}, "effets": {"pm": 5}, "valeur": {"facteur": 1.5}, "rarete": "peu_commun"},
	},
	"item:Poudre_de_miroir": {
		"nom": "du Reflet",
		"modificateurs": {"bonus_cd": 2, "bonus": {"Ag": 1, "Cha": 1}, "valeur": {"facteur": 1.4}},
	},
	"item:Poudre_os": {
		"nom": "des Ossements",
		"modificateurs": {"bonus_pv": 2, "bonus": {"R": 1}, "poids": {"facteur": 0.95}, "valeur": {"facteur": 1.1}},
	},
	"item:Poupee_de_cire": {
		"nom": "de l’Imitation",
		"modificateurs": {"bonus_pm": 1, "bonus": {"Vol": 1, "Int": 1}, "effets": {"duree": 2}, "valeur": {"facteur": 1.3}},
	},
	"item:Reactif_brut": {
		"nom": "Alchimique",
		"modificateurs": {"bonus_pm": 1, "effets": {"pm": 3}, "valeur": {"facteur": 1.1}},
	},
	"item:Sang_demon_seche": {
		"nom": "Démoniaque",
		"modificateurs": {"bonus_degats": 3, "bonus": {"F": 1, "Vol": 1}, "effets": {"pv": 5}, "valeur": {"facteur": 1.7}, "rarete": "rare"},
	},
	"item:Sel_des_sepultures": {
		"nom": "des Sépultures",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 1}, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.4}, "rarete": "peu_commun"},
	},
	"item:Sel_noir": {
		"nom": "Ténébreux",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 1}, "effets": {"pm": -3}, "valeur": {"facteur": 1.3}, "rarete": "peu_commun"},
	},
	"item:acier_plisse": {
		"nom": "Damasquiné",
		"modificateurs": {"bonus_degats": 3, "bonus_cc": 1, "bonus_pa": 1, "poids": {"facteur": 1.05}, "valeur": {"facteur": 1.6}, "rarete": "rare"},
	},
	"item:ange_de_la_connaissance_aile": {
		"nom": "de la Connaissance",
		"modificateurs": {"bonus_pm": 2, "bonus": {"Int": 2}, "effets": {"pm": 5, "duree": 3}, "valeur": {"facteur": 2}, "rarete": "tres_rare"},
	},
	"item:ange_de_la_connaissance_tete": {
		"nom": "de la Clairvoyance",
		"modificateurs": {"bonus_pm": 3, "bonus": {"Int": 2, "Vol": 1}, "effets": {"regen_pm": 1, "duree": 3}, "valeur": {"facteur": 2.2}, "rarete": "tres_rare"},
	},
	"item:ange_de_la_justice_aile": {
		"nom": "de la Justice",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 2}, "effets": {"buffs": {"Vol": 1}, "duree": 3}, "valeur": {"facteur": 2}, "rarete": "tres_rare"},
	},
	"item:ange_de_la_justice_bras": {
		"nom": "du Jugement",
		"modificateurs": {"bonus_degats": 3, "bonus_pa": 2, "bonus": {"F": 2, "Vol": 1}, "valeur": {"facteur": 2}, "rarete": "tres_rare"},
	},
	"item:ange_de_la_justice_tete": {
		"nom": "de la Vérité",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 2}, "effets": {"buffs": {"Vol": 1}, "duree": 3}, "valeur": {"facteur": 2.2}, "rarete": "tres_rare"},
	},
	"item:araignee_geante_tete": {
		"nom": "Arachnéen",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Ag": 1}, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.4}, "rarete": "peu_commun"},
	},
	"item:archange_de_l_ordre_aile": {
		"nom": "de l’Ordre",
		"modificateurs": {"bonus_pm": 3, "bonus": {"Vol": 2}, "effets": {"buffs": {"Vol": 1}, "duree": 3}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:archange_de_l_ordre_bras": {
		"nom": "de l’Autorité",
		"modificateurs": {"bonus_degats": 4, "bonus_pa": 2, "bonus": {"F": 2, "R": 1}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:archange_de_l_ordre_tete": {
		"nom": "du Commandement",
		"modificateurs": {"bonus": {"Vol": 2, "R": 1}, "effets": {"buffs": {"Vol": 1}, "duree": 3}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:archange_du_savoir_aile": {
		"nom": "du Savoir",
		"modificateurs": {"bonus_pm": 4, "bonus": {"Int": 2, "Vol": 1}, "effets": {"regen_pm": 1, "duree": 3}, "valeur": {"facteur": 2.8}, "rarete": "tres_rare"},
	},
	"item:archange_du_savoir_tete": {
		"nom": "de la Sagesse",
		"modificateurs": {"bonus_pm": 4, "bonus": {"Int": 3}, "effets": {"pm": 10, "duree": 3}, "valeur": {"facteur": 3}, "rarete": "legendaire"},
	},
	"item:avatar_bras": {
		"nom": "de l’Avatar",
		"modificateurs": {"bonus_degats": 4, "bonus_pa": 2, "bonus": {"F": 3}, "poids": {"facteur": 1.15}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:avatar_tete": {
		"nom": "de la Transcendance",
		"modificateurs": {"bonus_degats": 3, "bonus": {"F": 1, "Vol": 2}, "effets": {"pv": 10, "duree": 3}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:basilic_queue": {
		"nom": "du Basilic",
		"modificateurs": {"bonus_degats": 3, "bonus_cd": 1, "effets": {"pv": -5, "duree": 2}, "valeur": {"facteur": 1.8}, "rarete": "rare"},
	},
	"item:basilic_tete": {
		"nom": "du Regard Mortel",
		"modificateurs": {"bonus_degats": 4, "bonus": {"Vol": 2}, "effets": {"pv": -5, "duree": 3}, "valeur": {"facteur": 2.2}, "rarete": "tres_rare"},
	},
	"item:basilic_tete_morceau": {
		"nom": "du Regard Venimeux",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 1}, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.5}, "rarete": "rare"},
	},
	"item:bete_de_l_apocalypse_queue": {
		"nom": "de l’Apocalypse",
		"modificateurs": {"bonus_degats": 4, "bonus_pa": 2, "bonus": {"F": 2}, "poids": {"facteur": 1.1}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:bete_de_l_apocalypse_queue_morceau": {
		"nom": "du Fléau",
		"modificateurs": {"bonus_degats": 2, "bonus": {"F": 1}, "valeur": {"facteur": 1.6}, "rarete": "rare"},
	},
	"item:bete_de_l_apocalypse_tete": {
		"nom": "de la Fin des Temps",
		"modificateurs": {"bonus_degats": 5, "bonus_pa": 2, "bonus": {"F": 2, "Vol": 2}, "effets": {"pv": 10, "duree": 3}, "valeur": {"facteur": 3}, "rarete": "legendaire"},
	},
	"item:bete_de_l_apocalypse_tete_morceau": {
		"nom": "du Désastre",
		"modificateurs": {"bonus_degats": 3, "bonus": {"F": 1, "Vol": 1}, "valeur": {"facteur": 1.8}, "rarete": "tres_rare"},
	},
	"item:bete_de_l_apocalypse_patte": {
		"nom": "de la Destruction",
		"modificateurs": {"bonus_degats": 4, "bonus_pa": 1, "bonus": {"F": 2, "Ag": 1}, "poids": {"facteur": 1.1}, "valeur": {"facteur": 2.4}, "rarete": "tres_rare"},
	},
	"item:bete_de_l_apocalypse_patte_morceau": {
		"nom": "du Ravage",
		"modificateurs": {"bonus_degats": 2, "bonus": {"F": 1}, "valeur": {"facteur": 1.5}, "rarete": "rare"},
	},
	"item:bunyip_tete": {
		"nom": "des Marais",
		"modificateurs": {"bonus_degats": 3, "bonus_pv": 5, "bonus": {"R": 2}, "effets": {"pv": 5}, "valeur": {"facteur": 2}, "rarete": "rare"},
	},
	"item:bunyip_patte": {
		"nom": "des Profondeurs",
		"modificateurs": {"bonus_degats": 2, "bonus_pm": 1, "bonus": {"R": 1, "Ag": 1}, "poids": {"facteur": 1.05}, "valeur": {"facteur": 1.7}, "rarete": "rare"},
	},
	"item:bunyip_queue": {
		"nom": "des Eaux Sombres",
		"modificateurs": {"bonus_degats": 2, "bonus": {"R": 2}, "effets": {"buffs": {"R": 1}, "duree": 2}, "valeur": {"facteur": 1.8}, "rarete": "rare"},
	},
	"item:cerbere_tete": {
		"nom": "du Gardien Infernal",
		"modificateurs": {"bonus_degats": 4, "bonus": {"F": 2, "Vol": 1}, "effets": {"pv": -5, "duree": 3}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:chimere_queue": {
		"nom": "de la Chimère",
		"modificateurs": {"bonus_degats": 3, "bonus_cd": 2, "bonus": {"Ag": 1}, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 2}, "rarete": "rare"},
	},
	"item:chimere_patte": {
		"nom": "de la Fureur",
		"modificateurs": {"bonus_degats": 3, "bonus_pa": 1, "bonus": {"F": 1, "Ag": 1}, "valeur": {"facteur": 1.8}, "rarete": "rare"},
	},
	"item:chimere_patte_morceau": {
		"nom": "de la Férocité",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Ag": 1}, "valeur": {"facteur": 1.5}, "rarete": "rare"},
	},
	"item:chimere_queue_morceau": {
		"nom": "de la Discorde",
		"modificateurs": {"bonus_degats": 2, "bonus_cd": 1, "valeur": {"facteur": 1.5}, "rarete": "rare"},
	},
	"item:chimere_tete": {
		"nom": "des Trois Visages",
		"modificateurs": {"bonus_degats": 4, "bonus": {"F": 1, "Ag": 1, "Vol": 1}, "effets": {"pv": -5, "duree": 3}, "valeur": {"facteur": 2.4}, "rarete": "tres_rare"},
	},
	"item:chimere_tete_morceau": {
		"nom": "de la Monstruosité",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 1}, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.6}, "rarete": "rare"},
	},
	"item:cockatrice_aile": {
		"nom": "Paralysant",
		"modificateurs": {"bonus_pm": 2, "bonus_cd": 1, "bonus": {"Ag": 1}, "valeur": {"facteur": 1.8}, "rarete": "rare"},
	},
	"item:cockatrice_aile_morceau": {
		"nom": "du Regard de Pierre",
		"modificateurs": {"bonus_pm": 1, "bonus": {"Ag": 1}, "valeur": {"facteur": 1.4}, "rarete": "peu_commun"},
	},
	"item:cockatrice_patte": {
		"nom": "de la Griffe Mortelle",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Ag": 1}, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.6}, "rarete": "rare"},
	},
	"item:cockatrice_queue": {
		"nom": "Venimeuse",
		"modificateurs": {"bonus_degats": 2, "bonus_cd": 1, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.7}, "rarete": "rare"},
	},
	"item:cockatrice_queue_morceau": {
		"nom": "du Venin Noir",
		"modificateurs": {"bonus_degats": 1, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.4}, "rarete": "peu_commun"},
	},
	"item:cockatrice_tete": {
		"nom": "Pétrifiant",
		"modificateurs": {"bonus_degats": 3, "bonus": {"Ag": 1, "Vol": 1}, "effets": {"pv": -5, "duree": 3}, "valeur": {"facteur": 2}, "rarete": "rare"},
	},
	"item:cockatrice_tete_morceau": {
		"nom": "de la Pétrification",
		"modificateurs": {"bonus_degats": 2, "bonus": {"Vol": 1}, "effets": {"pv": -3, "duree": 2}, "valeur": {"facteur": 1.5}, "rarete": "rare"},
	},
	"item:coeur": {
		"nom": "du Courage",
		"modificateurs": {"bonus_pv": 3, "bonus": {"V": 1}, "effets": {"pv": 5, "regen_pv": 1, "duree": 2}, "valeur": {"facteur": 1.5}},
	},
	"item:cuir_brut": {
		"nom": "de la Peau",
		"modificateurs": {"bonus_pv": 1, "bonus": {"R": 1}, "poids": {"facteur": 0.95}, "valeur": {"facteur": 1.05}},
	},
	"item:poudre_alchimique": {
		"nom": "de l’Alchimie",
		"modificateurs": {"bonus_pm": 2, "effets": {"pm": 5}, "valeur": {"facteur": 1.4}, "rarete": "peu_commun"},
	},
	"item:relique": {
		"nom": "Relique",
		"modificateurs": {"bonus_pm": 2, "bonus_pv": 3, "bonus": {"Vol": 2}, "effets": {"pv": 5, "pm": 5, "duree": 3}, "valeur": {"facteur": 2.5}, "rarete": "tres_rare"},
	},
	"item:sang": {
		"nom": "Sanglante",
		"modificateurs": {"bonus_pv": 2, "bonus": {"V": 1}, "effets": {"pv": 5}, "valeur": {"facteur": 1.2}},
	},

	# ── Blocs posés à la main dans /admin/table, repris tels quels (dump du 21/09/2026) ──
	"item:Pate_a_polir": {
		"nom": "polie",
		"modificateurs": {"bonus_cc": 1, "bonus": {"Cha": 1}, "valeur": {"facteur": 1}, "rarete": "commun"},
	},
	"item:composant_rituel": {
		"nom": "de rituel",
		"modificateurs": {"bonus_pm": 1, "valeur": {"facteur": 1.1}},
	},
	"item:debris_anime": {
		"nom": "vivante",
		"modificateurs": {"bonus_cc": 4, "bonus_cd": 4, "bonus": {"Ag": 2}, "valeur": {"facteur": 2}, "rarete": "rare"},
	},
}


def _cles_consommees(base: dict) -> set:
	"""Toutes les clés matières qu'une recette consomme, quelque part. Relu du dump plutôt
	qu'appelé sur `utils.marche` : ce script ne doit pas dépendre d'une base joignable."""
	cles = set()
	for doc in base.values():
		if doc.get("type") != "recette":
			continue
		for m in (doc.get("matieres_premieres") or []):
			cle = m.get("item") or m.get("sous_categorie")
			if cle:
				cles.add(cle)
		if doc.get("matiere_premiere_sous_categorie"):
			cles.add(doc["matiere_premiere_sous_categorie"])
	return cles


def erreurs_de_forme(matieres: dict) -> list:
	"""Un modificateur hors liste blanche serait ignoré EN SILENCE par `proprietes_matiere`.
	Mieux vaut l'apprendre ici que de chercher pourquoi une matière n'apporte rien en jeu."""
	return ["%s : `%s` n'est pas un modificateur reconnu" % (item_id, cle)
			for item_id, bloc in sorted(matieres.items())
			for cle in (bloc.get("modificateurs") or {})
			if cle not in fabrication.CLES_MODIFIABLES]


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


def a_ecrire_depuis(bloc: dict, existant: dict):
	"""Le doc à importer pour poser `bloc`, ou None s'il n'y a rien à changer en base.

	⚠️ Le doc part du doc du dump, où l'on n'écrase que `fabrication` : l'import est un PUT
	COMPLET (CLAUDE.md §11), et toute clé ajoutée à la main dans /admin/table doit survivre.
	`_rev` est retiré (l'import le réattache depuis la base)."""
	fusion = _sans_rev(existant)
	fusion["fabrication"] = bloc
	return None if fusion == _sans_rev(existant) else fusion


def _est_bloc_matiere(bloc) -> bool:
	"""Un bloc `fabrication` de MATIÈRE — pas la traçabilité d'une variante sur mesure."""
	return (isinstance(bloc, dict) and "base_item" not in bloc
			and ("nom" in bloc or "modificateurs" in bloc))


def generer(docs: list, matieres: dict | None = None) -> tuple[list, list, list, list, list]:
	"""Cœur PUR du générateur : `(sortie, absents, jamais_travaillees, orphelins, inchanges)`.

	`sortie` = les SEULS docs à mettre en base, ceux dont le bloc change (`a_ecrire_depuis`) ;
	`absents` = ids de la table introuvables dans le dump (jamais créés) ;
	`jamais_travaillees` = ids qu'aucune recette ne consomme — le bloc est posé, mais seul un tag
	`fabrication_<famille>` les ouvrira à une pièce ;
	`orphelins` = ids du dump portant un bloc de matière absent de la table ;
	`inchanges` = ids dont le bloc est déjà identique en base, donc absents de `sortie`."""
	matieres = MATIERES if matieres is None else matieres
	base = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	consommees = _cles_consommees(base)

	sortie, absents, jamais_travaillees, inchanges = [], [], [], []
	for item_id, bloc in sorted(matieres.items()):
		existant = base.get(item_id)
		if existant is None:
			absents.append(item_id)
			continue
		# Une matière que personne ne travaille ne serait proposée par aucun artisan
		# (`besoins_lieu`) : le bloc serait posé pour rien. On le signale.
		sous_cat = existant.get("sous_categorie") or existant.get("categorie")
		if item_id not in consommees and sous_cat not in consommees:
			jamais_travaillees.append(item_id)
		doc = a_ecrire_depuis(bloc, existant)
		if doc is None:
			inchanges.append(item_id)
		else:
			sortie.append(doc)

	orphelins = sorted(i for i, d in base.items()
					   if i.startswith("item:") and i not in matieres
					   and _est_bloc_matiere(d.get("fabrication")))
	return sortie, absents, jamais_travaillees, orphelins, inchanges


def main() -> None:
	# Console Windows en cp1252 : sans cela, le premier accent fait planter le script.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	parser = argparse.ArgumentParser(description="Propriétés de fabrication des matières")
	parser.add_argument("--dump", help="dump à relire (défaut : un dump FRAIS écrit maintenant "
						"depuis CouchDB, dans jsons/)")
	args = parser.parse_args()

	# Contrôle AVANT le dump : une table mal formée n'a pas à solliciter la base.
	erreurs = erreurs_de_forme(MATIERES)
	if erreurs:
		print("⚠️ %d erreur(s) — RIEN n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("   " + e)
		sys.exit(1)

	if args.dump:
		source = args.dump
	else:
		try:
			source = dump_util.ecrire_dump_frais(RACINE)
		except Exception as err:
			sys.exit(f"ERREUR : dump frais impossible ({err}). Lancer dans le conteneur, ou "
					 "passer --dump jsons/telluris-dump-….json")
		print(f"dump frais ecrit : {source}")
	chemin_source = source if os.path.isabs(source) else os.path.join(RACINE, source)
	docs = dump_util.charger_docs(chemin_source)
	print(f"source : {source} ({len(docs)} docs)")

	sortie, absents, jamais_travaillees, orphelins, inchanges = generer(docs)
	base = {d.get("_id"): d for d in docs if isinstance(d, dict)}
	a_ecrire = {d["_id"] for d in sortie}

	print("\n== Matières")
	for item_id, bloc in sorted(MATIERES.items()):
		etat = ("ABSENTE de la base" if item_id in absents
				else "à écrire" if item_id in a_ecrire else "déjà à jour")
		note = "  ⚠️ travaillée par aucun métier" if item_id in jamais_travaillees else ""
		nom = (base.get(item_id) or {}).get("nom") or "—"
		print("   %-26s %-22s %-14s %s%s" % (item_id, nom, etat, bloc["nom"], note))

	print(f"\n{len(sortie)} doc(s) a mettre en base ; {len(inchanges)} deja a jour, ecarte(s)")
	if absents:
		print("⚠️ %d matière(s) absente(s) de la base, sautée(s) : %s"
			  % (len(absents), ", ".join(absents)))
	if orphelins:
		print(f"⚠️ {len(orphelins)} matière(s) du dump portent un bloc `fabrication` absent de la "
			  "table — à reporter dans MATIERES ou à nettoyer dans /admin/table :")
		for oid in orphelins:
			print(f"   {oid}")

	if sortie:
		with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
			json.dump(sortie, f, ensure_ascii=False, indent=2)
			f.write("\n")
		print(f"ecrit {SORTIE}")
	else:
		# Aucun fichier : 📥 Importer (`sortie_fraiche`) refuse alors un fichier plus vieux que le
		# run, au lieu de réimporter un ancien lot.
		print(f"rien a mettre en base : {SORTIE} n'est PAS reecrit")


if __name__ == "__main__":
	main()

#!/usr/bin/env python
# dev/gen_fabrication_matieres.py
# Ce qu'une MATIÈRE apporte à une pièce fabriquée sur mesure — bloc `fabrication` sur les
# docs `item:*` de matière première, plus ses tags `fabrication_<famille>` et, pour les parties
# de créatures, sa `rarete`.
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
# ⚠️ DEUX PORTES font entrer une matière dans une pièce (`commande.matiere_acceptee`) : le
# métier de la maison (`marche.besoins_lieu`) OU un tag `fabrication_<categorie ou
# sous_categorie de la pièce>` sur le doc matière. Les parties de créatures ne sont achetées
# que par la boucherie (clé `carcasse`) : SANS TAG, elles n'entrent dans aucune arme ni
# armure. La table porte donc, par matière, la liste COMPLÈTE de ses tags `fabrication_*` —
# ceux qu'elle ne cite pas sont retirés, les autres tags du doc ne sont jamais touchés.
#
# ⚠️ LE GAIN SUIT LA DIFFICULTÉ D'OBTENTION. Chaque matière est rangée dans un PALIER (1 à 5,
# cf. `PALIERS`) : rareté et prix pour les matières d'échoppe, DANGEROSITÉ DE L'ESPÈCE pour les
# parties de créatures (somme des attributs de base ; un morceau vaut un palier de moins que
# sa partie). Le palier fixe un budget de points (`score_matiere`), le facteur de `valeur` et la
# `rarete` produite — contrôlés par `erreurs_de_budget` AVANT tout dump.
#
# ⚠️ `effets` NE VEUT PAS DIRE LA MÊME CHOSE SELON LA PIÈCE (`effets_mal_diriges`) :
#   - sur une ARME, il vise l'ENNEMI (`sorts.effets_d_arme`) et seule sa part durative agit :
#     un buff positif ou une régén y soignerait la cible. Une matière d'arme ne porte donc que
#     des DÉBUFFS (`{"buffs": {X: -n}, "duree": d}`) ;
#   - sur une pièce PORTÉE, seuls `regen_*`, `esquive` et `canalisation` sont lus
#     (`characters.recompute_equipment_bonus`) ;
#   - sur un CONSOMMABLE, `pv`/`pm` sont ramenés à 0 s'ils sont négatifs
#     (`consommables._as_int`) : un « venin » `pv: -5` n'y fait rien non plus.
#
# ⚠️ RELANÇABLE À VOLONTÉ, SUR UN DUMP FRAIS. `admin_import_bulk` fait un PUT COMPLET : relire
# un dump périmé écraserait les retouches faites depuis. Sans `--dump`, le script écrit donc
# lui-même un dump frais (`utils/dump.ecrire_dump_frais` — le code des outils de /admin/dev-tools
# et de /admin/exports), ce qui exige CouchDB : à lancer dans le conteneur.
#
# ⚠️ LE FICHIER NE PORTE QUE LE DIFF. Seuls les docs dont le bloc `fabrication`, les tags
# `fabrication_*` ou la rareté CHANGENT partent à l'import ; un doc déjà à jour est écarté, et
# sans rien à changer aucun fichier n'est écrit. Le doc est repris DU DUMP : une clé ajoutée à la
# main survit à l'import (PUT complet). Relancer juste après un import rend donc un lot vide —
# c'est le signe que la base est à jour. Un item absent de la base est signalé et sauté.
#
# ⚠️ UNE RETOUCHE FAITE DANS /admin/table EST ÉCRASÉE À LA RELANCE si elle n'est pas reportée
# ici : la table est la vérité. Reporter d'abord, relancer ensuite.
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
from utils.commande import TAG_FABRICATION_PREFIXE      # noqa: E402

SORTIE = "jsons/fabrication_matieres_a_importer.json"

# ── Paliers ─────────────────────────────────────────────────────────────────────
# `budget` : fourchette de `score_matiere`, bornes comprises. `valeur` : facteur de prix exigé
# (None = palier 1, où le facteur reste ≤ `VALEUR_MAX_PALIER_1`). `rarete` : celle que la
# matière donne à la pièce (None = aucune, ou `commun`) — et, pour une partie de créature, la
# `rarete` de l'item lui-même, qui fixe son prix dérivé (`poids × MULT_RARETE × 2`).
PALIERS = {
	1: {"budget": (1, 3), "valeur": None, "rarete": None},
	2: {"budget": (3, 5), "valeur": 1.3, "rarete": "peu_commun"},
	3: {"budget": (6, 8), "valeur": 1.8, "rarete": "rare"},
	4: {"budget": (9, 13), "valeur": 2.5, "rarete": "tres_rare"},
	5: {"budget": (14, 18), "valeur": 3.5, "rarete": "legendaire"},
}
VALEUR_MAX_PALIER_1 = 1.1
RARETE_ITEM_PALIER_1 = "commun"

# Plafonds d'UNE matière, quel que soit son palier : au-delà, elle déclasserait le contenu
# authoré (les meilleures armes de la base tiennent dans +2/+3 de dégâts).
PLAFOND_DEGATS = 10
PLAFOND_CARAC = 6

# Poids d'un point de modificateur dans le score. Tout ce qui n'est pas cité vaut 0.
POIDS_SCORE = {
	"bonus_degats": 1, "bonus_degats_dice": 1, "bonus_cc": 1, "bonus_cd": 1, "bonus_pa": 1,
	"bonus_initiative": 1, "portee": 1, "bonus_pm": 0.5, "bonus_pv": 0.5,
}
POIDS_REGEN = 2
POIDS_EFFET_PORTE = 1       # esquive, canalisation : joués en permanence par la pièce portée
PV_PM_PAR_POINT = 5         # soin instantané : ne compte que sur un consommable

TAG_ARME = "fabrication_arme"
TAG_ARMURE = "fabrication_armure"
TAG_CONSOMMABLE = "fabrication_consommable"
TAG_CATALYSEUR = "fabrication_catalyseur"
TAG_ARC = "fabrication_arc"
TAG_ARBALETE = "fabrication_arbalete"
# Familles où `effets` vise l'ENNEMI (`sorts.effets_d_arme`).
TAGS_ARME = frozenset({TAG_ARME, TAG_ARC, TAG_ARBALETE})

# Tags d'une partie de créature, selon la partie. Un morceau suit sa partie.
TAGS_PAR_PARTIE = {
	"tete": [TAG_ARME, TAG_ARMURE],
	"bras": [TAG_ARME], "patte": [TAG_ARME], "queue": [TAG_ARME],
	"aile": [TAG_ARMURE, TAG_CATALYSEUR],
}


def _deb(carac: str, delta: int, duree: int) -> dict:
	"""Débuff d'arme : posé sur la CIBLE à l'impact (`sorts.part_durative`)."""
	return {"buffs": {carac: -abs(delta)}, "duree": duree}


def _val(facteur: float) -> dict:
	return {"facteur": facteur}


def _partie(nom: str, palier: int, partie: str, mods: dict) -> dict:
	"""Entrée d'une partie de créature : tags par partie, `rarete` de l'item alignée sur le palier."""
	p = PALIERS[palier]
	mods = dict(mods)
	if p["valeur"]:
		mods.setdefault("valeur", _val(p["valeur"]))
	if p["rarete"]:
		mods.setdefault("rarete", p["rarete"])
	return {"nom": nom, "modificateurs": mods, "palier": palier,
			"tags": list(TAGS_PAR_PARTIE[partie]),
			"rarete_item": p["rarete"] or RARETE_ITEM_PALIER_1}


def _matiere(nom: str, palier: int, mods: dict, tags=()) -> dict:
	"""Entrée d'une matière d'échoppe : facteur de `valeur` et `rarete` produite du palier."""
	p = PALIERS[palier]
	mods = dict(mods)
	if p["valeur"]:
		mods.setdefault("valeur", _val(p["valeur"]))
	if p["rarete"]:
		mods.setdefault("rarete", p["rarete"])
	return {"nom": nom, "modificateurs": mods, "palier": palier, "tags": list(tags)}


ARME_ARMURE = [TAG_ARME, TAG_ARMURE]
ARME_ARMURE_CONSO = [TAG_ARME, TAG_ARMURE, TAG_CONSOMMABLE]

# ── La table ────────────────────────────────────────────────────────────────────
# `nom`  : fragment ajouté au nom de la pièce (« Épée longue en acier au cristal de feu »).
# `modificateurs` : composés par `fabrication.appliquer_modificateurs` — additif sur les
#   `bonus_*`, fusion clé à clé sur `bonus`/`effets`, multiplicatif sur `poids`/`valeur`, palier
#   le plus haut sur `rarete`. Tout champ hors de `CLES_MODIFIABLES` serait ignoré.
# `palier` : 1 à 5 (cf. `PALIERS`). `tags` : la liste COMPLÈTE des tags `fabrication_*`.
# `rarete_item` : `rarete` du doc matière lui-même (parties de créatures seulement).
#
# Dangerosité des espèces (somme des attributs de base, dump du 24/09/2026) : basilic ≈195,
# cockatrice ≈205, araignée géante ≈225 → palier 2 ; bunyip ≈242, chimère ≈262, cerbère ≈288
# → 3 ; anges ≈360-390, archanges ≈410-440 → 4 ; avatar ≈495, Bête de l'Apocalypse ≈600 → 5.
MATIERES = {
	# ── Palier 1 : communs ─────────────────────────────────────────────────────
	"item:fer": _matiere("en fer", 1, {"bonus_degats": 1, "poids": _val(1.05)}),
	"item:bronze": _matiere("en bronze", 1, {"bonus_degats": 1, "poids": _val(1.1), "valeur": _val(0.9)}),
	# Lourde et sourde : elle frappe fort et se porte mal. Le poids EST le contrepoids.
	"item:plomb": _matiere("plombé", 1, {"bonus_degats": 2, "poids": _val(1.4), "valeur": _val(0.8)}),
	"item:cuir": _matiere("à garniture de cuir", 1, {"bonus_pa": 1, "poids": _val(0.95)}),
	"item:tendons": _matiere("à ligature de tendons", 1, {"bonus_degats": 1, "poids": _val(0.95)}),
	"item:os": _matiere("à poignée d'os", 1, {"bonus_degats": 1, "poids": _val(0.9)}),
	"item:cuir_brut": _matiere("de la Peau", 1, {"bonus_pv": 1, "bonus": {"R": 1}, "poids": _val(0.95),
												 "valeur": _val(1.05)}, ARME_ARMURE),
	"item:sang": _matiere("Sanglante", 1, {"bonus_pv": 2, "bonus": {"V": 1}, "effets": {"pv": 5},
										   "valeur": _val(1.1)}),
	"item:Reactif_brut": _matiere("Alchimique", 1, {"bonus_pm": 2, "effets": {"pm": 3}, "valeur": _val(1.1)}),
	"item:Pate_a_polir": _matiere("polie", 1, {"bonus_cc": 1, "bonus": {"Cha": 1}, "valeur": _val(1),
											   "rarete": "commun"}, ARME_ARMURE),
	"item:Poudre_os": _matiere("des Ossements", 1, {"bonus_pv": 2, "bonus": {"R": 1}, "poids": _val(0.95),
													"valeur": _val(1.1)}, ARME_ARMURE_CONSO),
	"item:Poison_de_base": _matiere("Empoisonné", 1, {"bonus_degats": 1, "effets": _deb("R", 1, 2),
													  "valeur": _val(1.1)}, ARME_ARMURE),
	"item:Fiole_sang_bete": _matiere("Bestial", 1, {"bonus_degats": 1, "bonus": {"F": 1, "V": 1},
													"valeur": _val(1.1)}, ARME_ARMURE),
	"item:Eau_benite": _matiere("béni", 1, {"bonus_degats": 1, "bonus": {"Vol": 1}, "effets": {"pv": 5},
											"valeur": _val(1.1)}, ARME_ARMURE_CONSO),
	"item:Poudre_de_miroir": _matiere("du Reflet", 1, {"bonus_cd": 1, "bonus": {"Ag": 1, "Cha": 1},
													   "valeur": _val(1.1)}, ARME_ARMURE_CONSO),
	"item:Poupee_de_cire": _matiere("de l’Imitation", 1, {"bonus_pm": 1, "bonus": {"Vol": 1, "Int": 1},
														  "valeur": _val(1.1)}, ARME_ARMURE),
	# Lot du 24/09/2026 — matières sans usage ni source jusque-là ; leurs recettes sont dans
	# jsons/recettes_matieres_sans_source_a_importer.json (une matière sans source serait
	# proposée au sur-mesure et sa commande resterait en attente pour toujours).
	"item:Salpetre": _matiere("salpêtré", 1, {"bonus_degats": 1, "bonus_cd": 1, "valeur": _val(1.1)},
							  [TAG_ARME]),
	"item:Peintures_de_guerre": _matiere("aux peintures de guerre", 1, {
		"bonus_initiative": 1, "bonus": {"F": 1, "Cha": 1}, "valeur": _val(1.1)}, ARME_ARMURE),
	"item:Encre_noire": _matiere("aux runes noires", 1, {"bonus_pm": 2, "bonus": {"Int": 1}, "valeur": _val(1.1)},
								 [TAG_ARMURE, TAG_CATALYSEUR]),
	"item:Encens": _matiere("encensé", 1, {"bonus_pm": 2, "bonus": {"Vol": 1}, "valeur": _val(1.1)},
							[TAG_ARMURE, TAG_CATALYSEUR]),
	"item:Parchemin_blanc": _matiere("sur vélin", 1, {"bonus_pm": 2, "valeur": _val(1.1)}, [TAG_CATALYSEUR]),
	"item:Parchemin_vierge": _matiere("aux marges enluminées", 1, {"bonus_pm": 2, "bonus": {"Int": 1},
																   "valeur": _val(1.1)}, [TAG_CATALYSEUR]),

	# ── Palier 2 : peu communs ─────────────────────────────────────────────────
	"item:acier": _matiere("en acier", 2, {"bonus_degats": 2, "bonus_pa": 2, "poids": _val(1.05)}),
	"item:crocs": _matiere("à garde de crocs", 2, {"bonus_degats": 2, "bonus_cc": 1}),
	"item:composant_rituel": _matiere("de rituel", 2, {"bonus_pm": 2, "bonus": {"Vol": 1},
													   "effets": {"canalisation": 1}}, ARME_ARMURE_CONSO),
	# Régén : jamais sur une arme (elle soignerait la cible) — armure et consommable seulement.
	"item:coeur": _matiere("du Courage", 2, {"bonus_pv": 2, "bonus": {"V": 1},
											 "effets": {"pv": 5, "regen_pv": 1, "duree": 3}},
						   [TAG_ARMURE, TAG_CONSOMMABLE]),
	"item:poudre_alchimique": _matiere("empreint d'alchimie", 2, {"bonus_pm": 2, "bonus": {"Int": 1},
																  "effets": {"canalisation": 1}}, ARME_ARMURE),
	"item:Poudre_amethyste": _matiere("d’Améthyste", 2, {"bonus_pm": 4, "bonus": {"Vol": 1}}, ARME_ARMURE),
	"item:Encre_magique": _matiere("aux Inscriptions magiques", 2, {"bonus_pm": 2, "bonus": {"Int": 1, "Vol": 1},
																	"effets": {"canalisation": 1}},
								   [TAG_ARMURE, TAG_CATALYSEUR]),
	"item:Fetiche_envoutement": _matiere("Envoûté", 2, {"bonus_pm": 2, "bonus": {"Vol": 1},
														"effets": _deb("Vol", 1, 2)}, ARME_ARMURE),
	"item:Graine_sacree": _matiere("Sacrée", 2, {"bonus_pv": 2, "bonus": {"Vol": 1},
												 "effets": {"pv": 5, "regen_pv": 1, "duree": 3}},
								   [TAG_ARMURE, TAG_CONSOMMABLE]),
	"item:Sel_noir": _matiere("Ténébreux", 2, {"bonus_degats": 2, "bonus": {"Vol": 1},
											   "effets": _deb("Int", 1, 2)}, [TAG_ARME]),
	"item:metaux_precieux": _matiere("à incrustations précieuses", 2, {"bonus": {"Cha": 3}}, ARME_ARMURE),
	"item:debris_anime": _matiere("vivante", 2, {"bonus_cc": 2, "bonus_cd": 1, "bonus": {"Ag": 1}}),
	"item:Cercle_invocation": _matiere("d'invocation", 2, {"bonus_pm": 2, "bonus": {"Int": 1},
														   "effets": {"canalisation": 2}}, [TAG_ARMURE, TAG_CATALYSEUR]),
	# Composant de six sorts druidiques : l'esquive se lit sur une pièce PORTÉE, jamais sur une arme.
	"item:Os_de_totem": _matiere("totémique", 2, {"bonus_pv": 2, "bonus": {"F": 1, "V": 1},
												  "effets": {"esquive": 1}}, [TAG_ARMURE, TAG_CATALYSEUR]),

	# ── Palier 3 : rares ───────────────────────────────────────────────────────
	# L'argent est le métal des canaux : `item:Epee_argent` porte déjà bonus_pm 4 et bonus Int 2.
	# Palier 3 par son PRIX (20 ag le lingot), pas par sa rareté.
	"item:argent": _matiere("aux ferrures d'argent", 3, {"bonus_pm": 4, "bonus": {"Int": 2, "Vol": 1},
														 "effets": {"canalisation": 1}}, [TAG_CATALYSEUR]),
	"item:acier_plisse": _matiere("damasquiné", 3, {"bonus_degats": 4, "bonus_cc": 1, "bonus_pa": 2,
													"poids": _val(1.05)}),
	"item:Empennage_de_maitre": _matiere("de la Maîtrise", 3, {"bonus_degats": 2, "bonus_cc": 2,
															   "bonus_initiative": 2, "poids": _val(0.95)},
										 [TAG_ARC, TAG_ARBALETE]),
	"item:gemmes": _matiere("serti d'une gemme", 3, {"bonus_pm": 4, "bonus": {"Int": 1, "Vol": 2},
													 "effets": {"canalisation": 1}}, ARME_ARMURE + [TAG_CATALYSEUR]),
	"item:perles": _matiere("perlé", 3, {"bonus_pm": 2, "bonus": {"Cha": 3, "Vol": 2}}),
	"item:Fiole_de_sang_fige": _matiere("du Sang Figé", 3, {"bonus_degats": 2, "bonus_pv": 6, "bonus": {"R": 2}},
										ARME_ARMURE),
	"item:Fragments_ame": _matiere("Hanté", 3, {"bonus_pm": 3, "bonus": {"Int": 1, "Vol": 2},
												"effets": {"regen_pm": 1}}, [TAG_ARMURE, TAG_CATALYSEUR]),
	"item:Sang_demon_seche": _matiere("Démoniaque", 3, {"bonus_degats": 4, "bonus": {"F": 1, "Vol": 1},
														"effets": _deb("Vol", 1, 2)}, [TAG_ARME]),
	"item:Sel_des_sepultures": _matiere("des Sépultures", 3, {"bonus_degats": 3, "bonus": {"Vol": 2},
															  "effets": _deb("R", 1, 2)}, [TAG_ARME]),
	"item:relique": _matiere("Relique", 3, {"bonus_pm": 2, "bonus_pv": 2, "bonus": {"Vol": 2},
											"effets": {"regen_pm": 1, "pv": 5, "pm": 5, "duree": 3}},
							 [TAG_ARMURE, TAG_CATALYSEUR, TAG_CONSOMMABLE]),

	# ── Lingots précieux : paliers 4-5 par leur PRIX (1, 2 et 20 or) ─────────────
	# Aucune recette ne les consomme : c'est `APPRO_EXTRA` qui les fait livrer au grand arsenal
	# (réserve + comptoir), seule source du jeu — cf. models/character_stats.py.
	"item:mithril": _matiere("en mithril", 4, {"bonus_degats": 3, "bonus_pa": 3, "bonus_cc": 2,
											   "bonus": {"Ag": 2}, "poids": _val(0.6)}, ARME_ARMURE),
	"item:orichalque": _matiere("en orichalque", 4, {"bonus_degats": 3, "bonus_pm": 4,
													 "bonus": {"Int": 2, "Vol": 2},
													 "effets": {"canalisation": 1}},
								ARME_ARMURE + [TAG_CATALYSEUR]),
	"item:adamantite": _matiere("en adamantite", 5, {"bonus_degats": 6, "bonus_pa": 6, "bonus": {"R": 3},
													 "poids": _val(1.2)}, ARME_ARMURE),

	# ── Parties de créatures ───────────────────────────────────────────────────
	# Venin → R, pétrification/paralysie → V (comme les bolas), regard/malédiction → Vol.
	# Palier 1 : morceaux des espèces de palier 2.
	"item:cockatrice_aile_morceau": _partie("du Regard de Pierre", 1, "aile", {"bonus_pm": 2, "bonus": {"Ag": 1}}),
	"item:cockatrice_queue_morceau": _partie("du Venin Noir", 1, "queue", {"bonus_degats": 1,
																		   "effets": _deb("V", 1, 2)}),
	"item:cockatrice_tete_morceau": _partie("de la Pétrification", 1, "tete", {"bonus_degats": 1,
																			   "bonus": {"Vol": 1}}),
	"item:basilic_tete_morceau": _partie("du Regard Venimeux", 1, "tete", {"bonus_degats": 1, "bonus": {"Vol": 1}}),

	# Palier 2 : cockatrice, basilic, araignée géante ; morceaux de chimère.
	"item:cockatrice_aile": _partie("Paralysant", 2, "aile", {"bonus_pm": 2, "bonus": {"Ag": 1, "Vol": 1},
															  "effets": {"esquive": 1}}),
	"item:cockatrice_tete": _partie("Pétrifiant", 2, "tete", {"bonus_degats": 2, "bonus": {"Ag": 1, "Vol": 1},
															  "effets": _deb("V", 1, 2)}),
	"item:cockatrice_patte": _partie("de la Griffe Mortelle", 2, "patte", {"bonus_degats": 2, "bonus": {"Ag": 1},
																		   "effets": _deb("V", 1, 2)}),
	"item:cockatrice_queue": _partie("Venimeuse", 2, "queue", {"bonus_degats": 2, "bonus_cd": 1,
															   "effets": _deb("V", 1, 2)}),
	"item:basilic_tete": _partie("du Regard Mortel", 2, "tete", {"bonus_degats": 2, "bonus": {"Vol": 2},
																 "effets": _deb("R", 1, 2)}),
	"item:basilic_queue": _partie("du Basilic", 2, "queue", {"bonus_degats": 3, "effets": _deb("R", 1, 2)}),
	"item:araignee_geante_tete": _partie("Arachnéen", 2, "tete", {"bonus_degats": 2, "bonus": {"Ag": 1},
																  "effets": _deb("V", 1, 2)}),
	"item:chimere_tete_morceau": _partie("de la Monstruosité", 2, "tete", {"bonus_degats": 2, "bonus": {"Vol": 1},
																		   "effets": _deb("Vol", 1, 2)}),
	"item:chimere_patte_morceau": _partie("de la Férocité", 2, "patte", {"bonus_degats": 2, "bonus_cc": 1,
																		 "bonus": {"Ag": 1}}),
	"item:chimere_queue_morceau": _partie("de la Discorde", 2, "queue", {"bonus_degats": 2, "bonus_cc": 1,
																		 "bonus_cd": 1}),

	# Palier 3 : bunyip, chimère, cerbère.
	"item:bunyip_tete": _partie("des Marais", 3, "tete", {"bonus_degats": 3, "bonus_pv": 6, "bonus": {"R": 2}}),
	"item:bunyip_patte": _partie("des Profondeurs", 3, "patte", {"bonus_degats": 3, "bonus": {"R": 1, "Ag": 2},
																 "poids": _val(1.05)}),
	"item:bunyip_queue": _partie("des Eaux Sombres", 3, "queue", {"bonus_degats": 3, "bonus": {"R": 2},
																  "effets": _deb("Ag", 1, 2)}),
	"item:chimere_tete": _partie("des Trois Visages", 3, "tete", {"bonus_degats": 4,
																  "bonus": {"F": 1, "Ag": 1, "Vol": 1},
																  "effets": _deb("Vol", 1, 2)}),
	"item:chimere_patte": _partie("de la Fureur", 3, "patte", {"bonus_degats": 3, "bonus_pa": 1, "bonus_cc": 1,
															   "bonus": {"F": 1, "Ag": 1}}),
	"item:chimere_queue": _partie("de la Chimère", 3, "queue", {"bonus_degats": 3, "bonus_cd": 2, "bonus": {"Ag": 1},
																"effets": _deb("R", 1, 2)}),
	"item:cerbere_tete": _partie("du Gardien Infernal", 3, "tete", {"bonus_degats": 4, "bonus": {"F": 2, "Vol": 1},
																	"effets": _deb("Vol", 1, 2)}),

	# Palier 4 : anges (bas de fourchette), archanges (haut) ; morceaux de Bête.
	"item:ange_de_la_connaissance_aile": _partie("de la Connaissance", 4, "aile", {
		"bonus_pm": 4, "bonus": {"Int": 3, "Vol": 1}, "effets": {"regen_pm": 1, "canalisation": 1}}),
	"item:ange_de_la_connaissance_tete": _partie("de la Clairvoyance", 4, "tete", {
		"bonus_pm": 4, "bonus": {"Int": 3, "Vol": 2}, "effets": {"canalisation": 3}}),
	"item:ange_de_la_justice_aile": _partie("de la Justice", 4, "aile", {
		"bonus_pa": 3, "bonus_pv": 4, "bonus": {"Vol": 3}, "effets": {"esquive": 1}}),
	"item:ange_de_la_justice_bras": _partie("du Jugement", 4, "bras", {
		"bonus_degats": 5, "bonus_cc": 1, "bonus": {"F": 2, "Vol": 1}}),
	"item:ange_de_la_justice_tete": _partie("de la Vérité", 4, "tete", {
		"bonus_degats": 4, "bonus": {"F": 1, "Vol": 3}, "effets": _deb("Vol", 1, 3)}),
	"item:archange_de_l_ordre_aile": _partie("de l’Ordre", 4, "aile", {
		"bonus_pm": 4, "bonus_pa": 3, "bonus": {"Vol": 4, "R": 1}, "effets": {"esquive": 1, "canalisation": 1}}),
	"item:archange_de_l_ordre_bras": _partie("de l’Autorité", 4, "bras", {
		"bonus_degats": 6, "bonus_cc": 2, "bonus": {"F": 3, "R": 1}}),
	"item:archange_de_l_ordre_tete": _partie("du Commandement", 4, "tete", {
		"bonus_degats": 4, "bonus": {"Vol": 4, "R": 2}, "effets": _deb("Vol", 2, 2)}),
	"item:archange_du_savoir_aile": _partie("du Savoir", 4, "aile", {
		"bonus_pm": 4, "bonus": {"Int": 4, "Vol": 3}, "effets": {"regen_pm": 1, "canalisation": 1}}),
	"item:archange_du_savoir_tete": _partie("de la Sagesse", 4, "tete", {
		"bonus_pm": 6, "bonus": {"Int": 5, "Vol": 2}, "effets": {"canalisation": 3}}),
	"item:bete_de_l_apocalypse_tete_morceau": _partie("du Désastre", 4, "tete", {
		"bonus_degats": 5, "bonus": {"F": 2, "Vol": 2}}),
	"item:bete_de_l_apocalypse_patte_morceau": _partie("du Ravage", 4, "patte", {
		"bonus_degats": 5, "bonus": {"F": 2, "Ag": 2}}),
	"item:bete_de_l_apocalypse_queue_morceau": _partie("du Fléau", 4, "queue", {
		"bonus_degats": 5, "bonus_cd": 2, "bonus": {"F": 2}}),

	# Palier 5 : avatar (bas de fourchette), Bête de l'Apocalypse (haut).
	"item:avatar_bras": _partie("de l’Avatar", 5, "bras", {
		"bonus_degats": 8, "bonus_cc": 2, "bonus": {"F": 4}, "poids": _val(1.15)}),
	"item:avatar_tete": _partie("de la Transcendance", 5, "tete", {
		"bonus_degats": 6, "bonus_pv": 2, "bonus": {"F": 2, "Vol": 4}, "effets": _deb("Vol", 2, 2)}),
	"item:bete_de_l_apocalypse_tete": _partie("de la Fin des Temps", 5, "tete", {
		"bonus_degats": 10, "bonus": {"F": 4, "Vol": 2}, "effets": _deb("R", 2, 2)}),
	"item:bete_de_l_apocalypse_patte": _partie("de la Destruction", 5, "patte", {
		"bonus_degats": 8, "bonus_cc": 2, "bonus": {"F": 4, "Ag": 2}, "poids": _val(1.1)}),
	"item:bete_de_l_apocalypse_queue": _partie("de l’Apocalypse", 5, "queue", {
		"bonus_degats": 8, "bonus_cd": 3, "bonus": {"F": 3}, "effets": _deb("Ag", 2, 2), "poids": _val(1.1)}),
}


# ── Barème ──────────────────────────────────────────────────────────────────────

def bloc_fabrication(entree: dict) -> dict:
	"""Le bloc `fabrication` à écrire : `nom` + `modificateurs`, rien des clés de pilotage
	(`palier`, `tags`, `rarete_item`)."""
	return {"nom": entree.get("nom", ""), "modificateurs": entree.get("modificateurs") or {}}


def _num(v) -> float:
	return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def score_matiere(mods: dict, tags=()) -> float:
	"""Points qu'apporte une matière (cf. en-tête) : ce qui AGIT, pas ce qui est écrit.

	Un soin instantané (`pv`/`pm` d'`effets`) ne compte que si la matière entre dans un
	consommable — ailleurs il n'est lu par personne. Un débuff vaut |Δ| × durée / 2."""
	mods = mods or {}
	score = sum(_num(mods.get(cle)) * poids for cle, poids in POIDS_SCORE.items())
	score += sum(_num(v) for v in (mods.get("bonus") or {}).values())
	eff = mods.get("effets") or {}
	score += POIDS_REGEN * (_num(eff.get("regen_pv")) + _num(eff.get("regen_pm")))
	score += POIDS_EFFET_PORTE * (_num(eff.get("esquive")) + _num(eff.get("canalisation")))
	duree = _num(eff.get("duree"))
	for v in (eff.get("buffs") or {}).values():
		score += abs(_num(v)) * duree / 2 if _num(v) < 0 else _num(v)
	if TAG_CONSOMMABLE in set(tags or ()):
		score += (max(0.0, _num(eff.get("pv"))) + max(0.0, _num(eff.get("pm")))) / PV_PM_PAR_POINT
	return score


def erreurs_de_budget(matieres: dict) -> list:
	"""Une matière hors de son palier : score hors fourchette, plafond dépassé, facteur de
	`valeur` ou `rarete` produite qui ne sont pas ceux du palier."""
	erreurs = []
	for item_id, entree in sorted(matieres.items()):
		palier = entree.get("palier")
		if palier not in PALIERS:
			erreurs.append("%s : palier `%s` inconnu" % (item_id, palier))
			continue
		p = PALIERS[palier]
		mods = entree.get("modificateurs") or {}
		score = score_matiere(mods, entree.get("tags"))
		bas, haut = p["budget"]
		if not bas <= score <= haut:
			erreurs.append("%s : score %g hors du budget %d-%d du palier %d" % (item_id, score, bas, haut, palier))
		if _num(mods.get("bonus_degats")) > PLAFOND_DEGATS:
			erreurs.append("%s : +%g dégâts > plafond %d" % (item_id, _num(mods.get("bonus_degats")), PLAFOND_DEGATS))
		for carac, v in (mods.get("bonus") or {}).items():
			if _num(v) > PLAFOND_CARAC:
				erreurs.append("%s : %s +%g > plafond %d" % (item_id, carac, _num(v), PLAFOND_CARAC))
		facteur = _num((mods.get("valeur") or {}).get("facteur")) or 1.0
		if p["valeur"] is None:
			if facteur > VALEUR_MAX_PALIER_1:
				erreurs.append("%s : valeur ×%g > ×%g au palier 1" % (item_id, facteur, VALEUR_MAX_PALIER_1))
		elif facteur != p["valeur"]:
			erreurs.append("%s : valeur ×%g ≠ ×%g du palier %d" % (item_id, facteur, p["valeur"], palier))
		rarete = mods.get("rarete")
		attendue = p["rarete"]
		if (attendue is None and rarete not in (None, RARETE_ITEM_PALIER_1)) or \
				(attendue is not None and rarete != attendue):
			erreurs.append("%s : rareté produite `%s` ≠ `%s` du palier %d" % (item_id, rarete, attendue, palier))
		rarete_item = entree.get("rarete_item")
		if rarete_item is not None and rarete_item != (attendue or RARETE_ITEM_PALIER_1):
			erreurs.append("%s : rareté de l'item `%s` ≠ palier %d" % (item_id, rarete_item, palier))
	return erreurs


def effets_mal_diriges(matieres: dict) -> list:
	"""`effets` qui n'agiraient pas, ou agiraient à rebours (cf. en-tête)."""
	erreurs = []
	for item_id, entree in sorted(matieres.items()):
		eff = (entree.get("modificateurs") or {}).get("effets") or {}
		tags = set(entree.get("tags") or ())
		buffs = eff.get("buffs") or {}
		positifs = [k for k, v in buffs.items() if _num(v) > 0]
		negatifs = [k for k, v in buffs.items() if _num(v) < 0]
		if tags & TAGS_ARME:
			soutiens = positifs + [k for k in ("regen_pv", "regen_pm", "esquive") if _num(eff.get(k)) > 0]
			if soutiens:
				erreurs.append("%s : %s sur une matière d'arme profiterait à l'ENNEMI"
							   % (item_id, ", ".join(sorted(soutiens))))
		elif negatifs:
			erreurs.append("%s : débuff %s sans famille d'arme — il ne toucherait personne"
						   % (item_id, ", ".join(sorted(negatifs))))
		for cle in ("pv", "pm"):
			if _num(eff.get(cle)) < 0:
				erreurs.append("%s : `effets.%s` négatif est ramené à 0 — inerte" % (item_id, cle))
		if buffs and _num(eff.get("duree")) <= 0:
			erreurs.append("%s : buffs sans `duree` — inertes" % item_id)
		if _num(eff.get("duree")) > 0 and not (buffs or any(_num(eff.get(k)) for k in ("regen_pv", "regen_pm", "esquive"))):
			erreurs.append("%s : `duree` sans rien à faire durer" % item_id)
		for tag in tags:
			if not tag.startswith(TAG_FABRICATION_PREFIXE):
				erreurs.append("%s : tag `%s` hors préfixe %s" % (item_id, tag, TAG_FABRICATION_PREFIXE))
	return erreurs


# ── Écriture ────────────────────────────────────────────────────────────────────

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


def a_ecrire_depuis(entree: dict, existant: dict):
	"""Le doc à importer pour poser `entree`, ou None s'il n'y a rien à changer en base.

	⚠️ Le doc part du doc du dump, où l'on n'écrase que `fabrication`, le sous-ensemble
	`fabrication_*` des tags (si l'entrée porte `tags`) et `rarete` (si elle porte
	`rarete_item`) : l'import est un PUT COMPLET (CLAUDE.md §11), et toute clé ajoutée à la main
	dans /admin/table doit survivre. `_rev` est retiré (l'import le réattache depuis la base)."""
	fusion = _sans_rev(existant)
	fusion["fabrication"] = bloc_fabrication(entree)
	if "tags" in entree:
		autres = [t for t in (existant.get("tags") or []) if not str(t).startswith(TAG_FABRICATION_PREFIXE)]
		tags = autres + sorted(set(entree["tags"]))
		if tags != (existant.get("tags") or []):
			fusion["tags"] = tags
	if entree.get("rarete_item"):
		fusion["rarete"] = entree["rarete_item"]
	return None if fusion == _sans_rev(existant) else fusion


def _est_bloc_matiere(bloc) -> bool:
	"""Un bloc `fabrication` de MATIÈRE — pas la traçabilité d'une variante sur mesure."""
	return (isinstance(bloc, dict) and "base_item" not in bloc
			and ("nom" in bloc or "modificateurs" in bloc))


def generer(docs: list, matieres: dict | None = None) -> tuple[list, list, list, list, list]:
	"""Cœur PUR du générateur : `(sortie, absents, jamais_travaillees, orphelins, inchanges)`.

	`sortie` = les SEULS docs à mettre en base, ceux qui changent (`a_ecrire_depuis`) ;
	`absents` = ids de la table introuvables dans le dump (jamais créés) ;
	`jamais_travaillees` = ids qu'aucune recette ne consomme ET qu'aucun tag `fabrication_*`
	n'ouvre à une pièce — le bloc est posé, mais aucune pièce ne pourra le recevoir ;
	`orphelins` = ids du dump portant un bloc de matière absent de la table ;
	`inchanges` = ids déjà identiques en base, donc absents de `sortie`."""
	matieres = MATIERES if matieres is None else matieres
	base = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	consommees = _cles_consommees(base)

	sortie, absents, jamais_travaillees, inchanges = [], [], [], []
	for item_id, entree in sorted(matieres.items()):
		existant = base.get(item_id)
		if existant is None:
			absents.append(item_id)
			continue
		sous_cat = existant.get("sous_categorie") or existant.get("categorie")
		tags = entree["tags"] if "tags" in entree else [
			t for t in (existant.get("tags") or []) if str(t).startswith(TAG_FABRICATION_PREFIXE)]
		if item_id not in consommees and sous_cat not in consommees and not tags:
			jamais_travaillees.append(item_id)
		doc = a_ecrire_depuis(entree, existant)
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
	erreurs = erreurs_de_forme(MATIERES) + erreurs_de_budget(MATIERES) + effets_mal_diriges(MATIERES)
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

	print("\n== Matières (palier · score)")
	for item_id, entree in sorted(MATIERES.items(), key=lambda kv: (kv[1]["palier"], kv[0])):
		etat = ("ABSENTE de la base" if item_id in absents
				else "à écrire" if item_id in a_ecrire else "déjà à jour")
		note = "  ⚠️ n'entre dans aucune pièce" if item_id in jamais_travaillees else ""
		score = score_matiere(entree["modificateurs"], entree.get("tags"))
		print("   T%d %4g  %-40s %-14s %s%s" % (entree["palier"], score, item_id, etat, entree["nom"], note))

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

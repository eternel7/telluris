#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Armes et armures d'AD&D 2e absentes de Telluris — docs `item:*` neufs + leurs recettes.

Source : les listes des Maraudeurs de Greyhawk (maraudeursdegreyhawk.fr/arenes/armes/,
/arenes/armures/ — groupes d'armes du Manuel des combattants), complétées par le Manuel
des Joueurs AD&D 2e, le Complete Fighter's Handbook et l'Oriental Adventures.

Écrit `jsons/armes_armures_add2e_a_importer.json`.

Volontairement ÉCARTÉ (déjà en base sous un autre nom) :
	main-gauche = Dague_de_parade · hache d'armes = Hache_de_guerre · fauchard = Faucharde
	étoile du matin = Morgenstern · fléau de cavalier / de fantassin = Fleau_monte / Fleau_arme
	nunchaku = Fleau_asiatique · pique à alène = Pique · bâton (bo) = Baton_de_combat
	targe, rondache, écu, pavois, bocle · arbalètes légère/lourde/de poing · sarbacane.
Écarté sans équivalent : l'arquebuse (poudre noire, hors du monde).

Règles reprises de `dev/gen_armures.py` / `dev/gen_epaulieres.py` :

1. **Échelle calée sur l'existant** : le dé d'AD&D devient `bonus_degats_dice`, la CA
   devient `bonus_pa` sur la courbe des torses en base (cuir 5 · mailles 17 · plates 25).
2. **Chaque matière doit pouvoir ARRIVER à l'atelier** : feuille globale (auto-appro,
   recalculée depuis le dump : `inputs − outputs`) OU produite par une recette de la MÊME
   catégorie de lieu (`manche`/`hampe` à l'armurerie, `cordes_d_arc` chez le fletcher).
   ⚠️ Ni `cuir` ni `tendons` (fausses feuilles : elles gèleraient la recette en silence).
3. **Aucune collision** : un `_id` (item ou recette) ou un `nom` déjà en base fait ÉCHOUER
   la génération — l'import est un PUT complet, il écraserait le doc sans prévenir.
4. Tag `tranchant` selon le critère de `dev/gen_armes_tranchantes.py` (un vrai fil) : pas
   pour ce qui ne fait que percer (stylet, estoc, lances, pics, esponton, corsèque…).

	python dev/gen_armes_armures_add2e.py
"""
import glob
import json
import os
import sys
import unicodedata

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "armes_armures_add2e_a_importer.json")

UNE = ["main_droite"]
AMB = ["main_droite", "main_gauche"]   # ambidextre / deux mains


def arme(slug, nom, icon, rarete, poids, slots, tags, portee, des, lieux, matieres, desc,
		 deg=None, r=None, deux_mains=False, **bonus):
	"""Une arme : `des` = dé d'AD&D (bonus_degats_dice), `deg` = bonus_degats."""
	item = {
		"_id": "item:" + slug, "type": "item", "nom": nom, "description": desc,
		"icon": icon, "rarete": rarete, "categorie": "arme", "sous_categorie": "",
		"slots": slots, "poids": poids, "tags": tags, "portee": portee,
	}
	if r:
		item["restriction"] = r
	if deg:
		item["bonus_degats"] = deg
	item["bonus_degats_dice"] = des
	for cle in ("cc", "cd", "initiative", "pa", "malus_depl"):
		if bonus.get(cle):
			item["bonus_" + cle] = bonus[cle]
	if bonus.get("caracs"):
		item["bonus"] = bonus["caracs"]
	if deux_mains:
		item["deux_mains"] = True
	return item, lieux, matieres


def armure(slug, nom, icon, rarete, poids, slots, pa, lieux, matieres, desc,
		   r=None, caracs=None, sous_categorie=""):
	item = {
		"_id": "item:" + slug, "type": "item", "nom": nom, "description": desc,
		"icon": icon, "rarete": rarete, "categorie": "armure", "sous_categorie": sous_categorie,
		"slots": slots, "poids": poids, "tags": [], "bonus_pa": pa,
	}
	if r:
		item["restriction"] = r
	if caracs:
		item["bonus"] = caracs
	return item, lieux, matieres


ARM = ["armurerie"]
ARC = ["fletcher", "atelier_de_l_empenneur"]   # mêmes ateliers que l'Arc_long
CUIR = ["maroquinerie"]

PIECES = [
	# ── Lames courtes ───────────────────────────────────────────────────────────────
	arme("Stylet", "Stylet", "🗡️", "commun", 0.25, AMB, ["cac"], 1, 4, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Lame fine à section carrée, sans tranchant : elle cherche le défaut de l'armure.",
		 deg=1, cc=6, initiative=3, caracs={"Ag": 2}),
	arme("Poignard", "Poignard", "🔪", "commun", 0.4, AMB, ["cac", "tranchant"], 1, 4, ARM,
		 [("fer", 1), ("manche", 1), ("peaux", 1)],
		 "Long poignard à double tranchant, l'arme de ceinture du soldat.",
		 deg=1, cc=5, initiative=2, caracs={"Ag": 2}),
	arme("Couteau", "Couteau", "🔪", "commun", 0.2, AMB, ["cac", "tranchant"], 1, 3, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Couteau de tous les jours ; on le lance au besoin, sans grande précision.",
		 deg=1, cc=4),
	arme("Kukri", "Kukri", "🔪", "peu_commun", 0.6, AMB, ["cac", "tranchant"], 1, 4, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Lame recourbée vers l'avant, lourde du bout : elle tranche comme une hachette.",
		 deg=2, cc=3, r={"F": 10}),
	arme("Katar", "Katar", "🗡️", "peu_commun", 0.5, AMB, ["cac", "tranchant"], 1, 4, ARM,
		 [("acier", 1), ("manche", 1)],
		 "Dague à poignée transversale qui prolonge le poing ; on frappe en boxant.",
		 deg=2, cc=4, r={"F": 10}),
	arme("Drusus", "Drusus", "⚔️", "peu_commun", 1.0, AMB, ["cac", "tranchant"], 1, 6, ARM,
		 [("acier", 2), ("manche", 1), ("peaux", 1)],
		 "Épée courte d'un acier exceptionnel, à l'équilibre parfait.",
		 deg=2, cc=3, r={"F": 10, "Ag": 12}),
	arme("Faucille", "Faucille", "🌙", "commun", 0.6, AMB, ["cac", "tranchant"], 1, 4, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Outil de moisson devenu arme ; les druides la portent volontiers.",
		 deg=1, cc=2),

	# ── Lames moyennes ──────────────────────────────────────────────────────────────
	arme("Cimeterre", "Cimeterre", "🌙", "commun", 1.8, UNE, ["cac", "tranchant"], 1, 8, ARM,
		 [("fer", 2), ("manche", 1), ("peaux", 1)],
		 "Lame courbe qui taille en tirant ; l'arme des cavaliers du désert.",
		 deg=3, r={"F": 12}),
	arme("Khopesh", "Khopesh", "🪝", "peu_commun", 2.5, UNE, ["cac", "tranchant"], 1, 6, ARM,
		 [("bronze", 3), ("manche", 1)],
		 "Lame en croissant héritée des vieux royaumes : elle accroche le bouclier adverse.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}),
	arme("Sabre", "Sabre", "⚔️", "commun", 1.4, UNE, ["cac", "tranchant"], 1, 6, ARM,
		 [("acier", 1), ("fer", 1), ("manche", 1)],
		 "Lame à un tranchant, légèrement courbe, garde enveloppante.",
		 deg=3, cc=3, initiative=1, r={"F": 11}),
	arme("Coutelas", "Coutelas", "🏴‍☠️", "commun", 1.6, UNE, ["cac", "tranchant"], 1, 6, ARM,
		 [("fer", 2), ("manche", 1)],
		 "Sabre court et large des marins, fait pour les ponts encombrés.",
		 deg=3, cc=2, r={"F": 11}),
	arme("Fauchon", "Fauchon", "⚔️", "commun", 2.0, UNE, ["cac", "tranchant"], 1, 6, ARM,
		 [("fer", 2), ("manche", 1), ("peaux", 1)],
		 "Lame lourde qui s'élargit vers la pointe : un couperet d'homme d'armes.",
		 deg=4, malus_depl=-1, r={"F": 13}),
	arme("Epee_large", "Épée large", "⚔️", "commun", 2.0, UNE, ["cac", "tranchant"], 1, 8, ARM,
		 [("fer", 3), ("manche", 1)],
		 "Large lame à deux tranchants, faite pour tailler plus que pour estoquer.",
		 deg=3, malus_depl=-1, r={"F": 13}),
	arme("Estoc", "Estoc", "🤺", "peu_commun", 1.8, UNE, ["cac"], 1, 8, ARM,
		 [("acier", 2), ("manche", 1)],
		 "Longue lame rigide sans fil, pensée pour passer entre les plates.",
		 deg=2, cc=3, r={"F": 13}),

	# ── Lames longues ───────────────────────────────────────────────────────────────
	arme("Epee_batarde", "Épée bâtarde", "⚔️", "commun", 2.2, UNE, ["cac", "tranchant"], 1, 8, ARM,
		 [("acier", 2), ("fer", 1), ("manche", 1), ("peaux", 1)],
		 "Épée « à une main et demie » : longue fusée, lame plus lourde que l'épée longue.",
		 deg=4, malus_depl=-1, r={"F": 14}),
	arme("Epee_a_deux_mains", "Épée à deux mains", "🗡️", "commun", 3.5, AMB, ["cac", "tranchant"],
		 1, 10, ARM, [("acier", 3), ("fer", 1), ("manche", 1), ("peaux", 1)],
		 "Lame immense maniée à deux mains ; elle fauche les rangs de piquiers.",
		 deg=5, malus_depl=-2, r={"F": 17}, deux_mains=True),
	arme("Claymore", "Claymore", "🗡️", "peu_commun", 3.0, AMB, ["cac", "tranchant"], 1, 8, ARM,
		 [("acier", 3), ("manche", 1), ("peaux", 1)],
		 "Grande épée des Highlands, quillons inclinés vers la pointe.",
		 deg=5, malus_depl=-2, r={"F": 16}, deux_mains=True),
	arme("Grand_cimeterre", "Grand cimeterre", "🌙", "peu_commun", 3.5, AMB, ["cac", "tranchant"],
		 1, 8, ARM, [("acier", 2), ("fer", 2), ("manche", 1)],
		 "Cimeterre démesuré, manié à deux mains en larges arcs.",
		 deg=5, malus_depl=-2, r={"F": 16}, deux_mains=True),

	# ── Haches ──────────────────────────────────────────────────────────────────────
	arme("Hache_a_deux_mains", "Hache à deux mains", "🪓", "commun", 4.0, AMB, ["cac", "tranchant"],
		 1, 10, ARM, [("acier", 2), ("fer", 1), ("manche", 2)],
		 "Manche de 1,2 à 1,5 m et un fer très lourd : lente, mais rien ne lui résiste.",
		 deg=5, malus_depl=-2, r={"F": 16}, deux_mains=True),
	arme("Hachette", "Hachette", "🪓", "commun", 0.8, AMB, ["cac", "tranchant"], 1, 6, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Petite hache à une main, aussi utile au bivouac qu'en mêlée.",
		 deg=2, cc=1),
	arme("Hache_de_jet", "Hache de jet", "🪓", "commun", 1.0, AMB, ["jet", "tranchant"], 2, 6, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Hache équilibrée pour être lancée avec précision.",
		 deg=3, cd=2, r={"F": 12}),

	# ── Armes d'hast ────────────────────────────────────────────────────────────────
	arme("Bardiche", "Bardiche", "🪓", "commun", 3.5, AMB, ["cac", "hast", "tranchant"], 2, 8, ARM,
		 [("fer", 3), ("hampe", 1), ("peaux", 1)],
		 "Longue lame de hache de 60 à 80 cm montée sur une hampe de 1,5 à 2,4 m.",
		 deg=4, malus_depl=-1, r={"F": 15}, deux_mains=True),
	arme("Vouge", "Vouge", "🪓", "commun", 3.5, AMB, ["cac", "hast", "tranchant"], 2, 8, ARM,
		 [("fer", 3), ("hampe", 1)],
		 "Couperet de boucher fixé au bout d'une hampe ; l'arme des milices.",
		 deg=4, malus_depl=-1, r={"F": 14}, deux_mains=True),
	arme("Doloire", "Doloire", "🪓", "commun", 3.5, AMB, ["cac", "hast", "tranchant"], 2, 8, ARM,
		 [("fer", 3), ("hampe", 1)],
		 "Large hache de charpentier emmanchée long, détournée pour la guerre.",
		 deg=4, malus_depl=-1, r={"F": 15}, deux_mains=True),
	arme("Glaive", "Glaive", "🗡️", "commun", 3.4, AMB, ["cac", "hast", "tranchant"], 2, 6, ARM,
		 [("fer", 2), ("hampe", 1), ("peaux", 1)],
		 "Lame de couteau d'une soixantaine de centimètres au bout d'une hampe.",
		 deg=4, cc=1, malus_depl=-1, r={"F": 14}, deux_mains=True),
	arme("Glaive_guisarme", "Glaive-guisarme", "🪝", "commun", 4.0, AMB, ["cac", "hast", "tranchant"],
		 2, 8, ARM, [("fer", 3), ("hampe", 1)],
		 "Glaive muni d'un crochet arrière pour désarçonner les cavaliers.",
		 deg=4, cc=2, malus_depl=-2, r={"F": 15}, deux_mains=True),
	arme("Guisarme_vouge", "Guisarme-vouge", "🪝", "commun", 4.5, AMB, ["cac", "hast", "tranchant"],
		 2, 8, ARM, [("fer", 3), ("acier", 1), ("hampe", 1)],
		 "Vouge doté d'un crochet et d'une pointe : trois armes en une, et lourde.",
		 deg=4, cc=2, malus_depl=-2, r={"F": 16}, deux_mains=True),
	arme("Partisane", "Partisane", "🔱", "commun", 3.4, AMB, ["cac", "hast", "tranchant"], 2, 6, ARM,
		 [("fer", 2), ("hampe", 1)],
		 "Large fer de lance à deux ailerons, apprécié des gardes de palais.",
		 deg=4, cc=2, malus_depl=-1, r={"F": 14}, deux_mains=True),
	arme("Fauchard_crochet", "Fauchard-crochet", "🪝", "commun", 3.2, AMB, ["cac", "hast", "tranchant"],
		 2, 6, ARM, [("fer", 2), ("hampe", 1)],
		 "Fauchard au dos armé d'un crochet qui tire l'adversaire à terre.",
		 deg=3, cc=3, malus_depl=-1, r={"F": 12}, deux_mains=True),
	arme("Fourche_fauchard", "Fourche-fauchard", "🔱", "commun", 3.5, AMB, ["cac", "hast", "tranchant"],
		 2, 8, ARM, [("fer", 2), ("hampe", 1)],
		 "Lame de fauchard prolongée d'une longue dent de fourche.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Fourche_de_guerre", "Fourche de guerre", "🔱", "commun", 3.2, AMB, ["cac", "hast"], 2, 8, ARM,
		 [("fer", 2), ("hampe", 1)],
		 "Fourche de paysan redressée et ferrée : deux dents longues et solides.",
		 deg=3, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Esponton", "Esponton", "🔱", "commun", 3.0, AMB, ["cac", "hast"], 2, 8, ARM,
		 [("fer", 2), ("hampe", 1)],
		 "Pointe de lance flanquée de deux crocs (ranseur) : elle pique et désarme.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Corseque", "Corsèque", "🔱", "commun", 3.0, AMB, ["cac", "hast"], 2, 8, ARM,
		 [("fer", 2), ("hampe", 1)],
		 "Fer de lance à deux ailerons pointus (spetum) : il blesse en profondeur.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Marteau_de_lucerne", "Marteau de Lucerne", "🔨", "commun", 4.0, AMB, ["cac", "hast"], 2, 8, ARM,
		 [("fer", 3), ("hampe", 1)],
		 "Tête de marteau à trois becs sur longue hampe, coiffée d'une pointe.",
		 deg=4, cc=1, malus_depl=-2, r={"F": 15}, deux_mains=True),
	arme("Attrape_coquin", "Attrape-coquin", "🪤", "peu_commun", 3.0, AMB, ["cac", "hast"], 2, 2, ARM,
		 [("fer", 2), ("hampe", 1), ("peaux", 1)],
		 "Pince à ressort au bout d'une perche, garnie de pointes : on capture, on ne tue pas.",
		 cc=4, r={"F": 10}, deux_mains=True),

	# ── Armes contondantes ──────────────────────────────────────────────────────────
	arme("Gourdin", "Gourdin", "🏏", "commun", 1.2, AMB, ["cac"], 1, 6, ARM,
		 [("manche", 2)],
		 "Un bon bâton noueux, épais du bout. La plus vieille arme du monde.",
		 deg=1),
	arme("Massue", "Massue", "🏏", "commun", 3.0, AMB, ["cac"], 1, 8, ARM,
		 [("manche", 3)],
		 "Gourdin énorme qu'on manie à deux mains, souvent cerclé ou clouté.",
		 deg=3, malus_depl=-1, r={"F": 14}, deux_mains=True),
	arme("Cabillot", "Cabillot", "⚓", "commun", 0.6, AMB, ["cac"], 1, 3, ARM,
		 [("manche", 1)],
		 "Cheville de bois des gréements, toujours à portée de main sur un navire.",
		 deg=1, cc=2),
	arme("Maillet_de_guerre", "Maillet de guerre", "🔨", "commun", 5.0, AMB, ["cac"], 1, 8, ARM,
		 [("fer", 3), ("manche", 2)],
		 "Masse de fer au bout d'un long manche, maniée à deux mains.",
		 deg=5, malus_depl=-2, r={"F": 17}, deux_mains=True),
	arme("Masse_de_cavalier", "Masse de cavalier", "🔨", "commun", 2.0, UNE, ["cac"], 1, 6, ARM,
		 [("fer", 2), ("manche", 1)],
		 "Masse à ailettes, légère et courte, faite pour frapper de la selle.",
		 deg=3, r={"F": 12}),
	arme("Masse_de_fantassin", "Masse de fantassin", "🔨", "commun", 3.0, UNE, ["cac"], 1, 6, ARM,
		 [("fer", 3), ("manche", 1), ("peaux", 1)],
		 "Masse d'armes lourde du piéton : elle bosselle le heaume et la tête dessous.",
		 deg=4, malus_depl=-1, r={"F": 14}),
	arme("Marteau_de_guerre", "Marteau de guerre", "🔨", "commun", 2.0, UNE, ["cac"], 1, 4, ARM,
		 [("fer", 2), ("manche", 1)],
		 "Tête de marteau carrée, souvent prolongée d'un bec ; arme favorite des nains.",
		 deg=3, cc=2, r={"F": 12}),
	arme("Tetsubo", "Tetsubo", "🏏", "peu_commun", 3.5, AMB, ["cac"], 1, 8, ARM,
		 [("manche", 2), ("fer", 1)],
		 "Long bâton dont l'extrémité est cerclée de bandes de fer cloutées.",
		 deg=4, malus_depl=-1, r={"F": 15}, deux_mains=True),
	arme("Macuahuitl", "Macuahuitl", "🪵", "peu_commun", 2.0, UNE, ["cac", "tranchant"], 1, 8, ARM,
		 [("manche", 2), ("poix", 1)],
		 "Épée de bois aux bords sertis d'éclats de pierre tranchants, collés à la poix.",
		 deg=3, r={"F": 12}),

	# ── Fléaux, chaînes, fouets ─────────────────────────────────────────────────────
	arme("Martinet", "Martinet", "🪢", "commun", 1.0, AMB, ["cac"], 1, 4, CUIR,
		 [("peaux", 2), ("plomb", 1)],
		 "Fléau à lanières lestées de plomb (scourge) : il lacère plus qu'il n'assomme.",
		 deg=1, cc=2),
	arme("Chat_a_neuf_queues", "Chat à neuf queues", "🐈‍⬛", "commun", 0.8, AMB, ["cac"], 1, 3, CUIR,
		 [("peaux", 2), ("plomb", 1)],
		 "Neuf cordelettes de cuir à nœuds de métal ; un instrument de châtiment.",
		 deg=1, cc=3),
	arme("Fouet", "Fouet", "➰", "commun", 1.0, AMB, ["cac"], 2, 2, CUIR,
		 [("peaux", 3)],
		 "Long fouet de cuir tressé : inefficace contre l'armure, redoutable pour désarmer.",
		 cc=4, r={"Ag": 12}),
	arme("Chaine_de_combat", "Chaîne de combat", "⛓️", "peu_commun", 1.5, AMB, ["cac"], 2, 4, ARM,
		 [("fer", 2)],
		 "Chaîne lestée qu'on fait tournoyer ; elle entrave autant qu'elle frappe.",
		 deg=2, cc=2, r={"Ag": 14}, deux_mains=True),
	arme("Kusarigama", "Kusarigama", "⛓️", "peu_commun", 1.5, AMB, ["cac", "tranchant"], 2, 6, ARM,
		 [("fer", 2), ("manche", 1)],
		 "Faucille reliée à une chaîne lestée : on entrave d'une main, on tranche de l'autre.",
		 deg=2, cc=3, r={"Ag": 15}, deux_mains=True),

	# ── Armes de samouraï ───────────────────────────────────────────────────────────
	arme("Wakizashi", "Wakizashi", "🌸", "peu_commun", 0.9, AMB, ["cac", "tranchant"], 1, 8, ARM,
		 [("acier", 2), ("manche", 1), ("peaux", 1)],
		 "Sabre court qui accompagne le katana, forgé de la même manière.",
		 deg=2, cc=4, initiative=2, r={"Ag": 12}),
	arme("No_dachi", "No-dachi", "🌸", "peu_commun", 2.5, AMB, ["cac", "tranchant"], 1, 10, ARM,
		 [("acier", 3), ("manche", 1), ("peaux", 1)],
		 "Très long sabre de champ de bataille, porté dans le dos.",
		 deg=4, malus_depl=-1, r={"F": 14, "Ag": 14}, deux_mains=True),
	arme("Sai", "Sai", "🔱", "peu_commun", 0.8, AMB, ["cac"], 1, 4, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Barre de métal à grande garde fourchue : elle bloque, pare et désarme.",
		 deg=1, cc=5, pa=2, r={"Ag": 12}),
	arme("Jitte", "Jitte", "🔱", "peu_commun", 0.6, AMB, ["cac"], 1, 4, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Matraque de fer à un seul croc, l'arme des gardes qui capturent.",
		 deg=1, cc=4, pa=1),
	arme("Kama", "Kama", "🌾", "peu_commun", 0.8, AMB, ["cac", "tranchant"], 1, 6, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Faucille de riziculteur au manche de bois dur, souvent maniée par paire.",
		 deg=2, cc=3, r={"Ag": 12}),

	# ── Lances ──────────────────────────────────────────────────────────────────────
	arme("Lance", "Lance", "🔱", "commun", 2.0, AMB, ["cac", "hast"], 2, 6, ARM,
		 [("fer", 1), ("hampe", 1)],
		 "Fer de lance sur une hampe de deux mètres : l'arme de base du fantassin.",
		 deg=2, r={"F": 10}, deux_mains=True),
	arme("Lance_longue", "Lance longue", "🔱", "commun", 3.0, AMB, ["cac", "hast"], 3, 8, ARM,
		 [("fer", 1), ("hampe", 2)],
		 "Lance de plus de trois mètres, tenue en rangs serrés.",
		 deg=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Trident", "Trident", "🔱", "commun", 2.5, AMB, ["cac", "hast"], 2, 6, ARM,
		 [("fer", 2), ("hampe", 1)],
		 "Fourche à trois dents droites, l'arme du pêcheur et du gladiateur.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 12}, deux_mains=True),
	arme("Harpon", "Harpon", "🎣", "commun", 2.5, AMB, ["jet"], 3, 6, ARM,
		 [("fer", 1), ("hampe", 1)],
		 "Fer barbelé sur une courte hampe, fait pour ne plus ressortir.",
		 deg=3, cd=2, r={"F": 12}),
	arme("Javelot", "Javelot", "🎯", "commun", 1.0, AMB, ["jet"], 4, 6, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Lance courte et légère, faite pour être lancée.",
		 deg=2, cd=3, r={"F": 10}),
	arme("Javeline", "Javeline", "🎯", "commun", 0.8, AMB, ["jet"], 4, 4, ARM,
		 [("fer", 1), ("manche", 1)],
		 "Trait de jet d'1,5 m à hampe fine et fer étroit.",
		 deg=2, cd=4, r={"Ag": 12}),
	arme("Flechettes", "Fléchettes", "📌", "commun", 0.1, AMB, ["jet"], 3, 3, ARM,
		 [("fer", 1)],
		 "Une poignée de courtes fléchettes lestées, lancées d'un coup de poignet.",
		 deg=1, cd=6, initiative=2, r={"Ag": 12}),
	arme("Lance_de_cavalerie_legere", "Lance de cavalerie légère", "🐎", "commun", 2.5, AMB,
		 ["cac", "hast"], 2, 6, ARM, [("fer", 1), ("hampe", 1)],
		 "Lance d'environ 3 m pour cavaliers légers, maniable d'une main.",
		 deg=3, r={"F": 12}, deux_mains=True),
	arme("Lance_de_cavalerie_moyenne", "Lance de cavalerie moyenne", "🐎", "commun", 4.5, AMB,
		 ["cac", "hast"], 3, 8, ARM, [("fer", 2), ("hampe", 2)],
		 "Lance d'environ 3,6 m, l'arme de charge des sergents montés.",
		 deg=3, malus_depl=-2, r={"F": 14}, deux_mains=True),
	arme("Lance_de_cavalerie_lourde", "Lance de cavalerie lourde", "🐎", "peu_commun", 7.0, AMB,
		 ["cac", "hast"], 3, 8, ARM, [("acier", 1), ("fer", 1), ("hampe", 3)],
		 "Lance de chevalier d'environ 4,2 m, avec rondelle de garde.",
		 deg=4, malus_depl=-3, r={"F": 17}, deux_mains=True),
	arme("Lance_de_joute", "Lance de joute", "🏇", "commun", 9.0, AMB, ["cac", "hast"], 3, 3, ARM,
		 [("hampe", 3), ("fer", 1)],
		 "Lance creuse à pointe émoussée, faite pour se briser sur l'écu en tournoi.",
		 deg=1, malus_depl=-3, r={"F": 16}, deux_mains=True),

	# ── Pics de guerre ──────────────────────────────────────────────────────────────
	arme("Pic_de_cavalier", "Pic de cavalier", "⛏️", "commun", 2.0, UNE, ["cac"], 1, 4, ARM,
		 [("fer", 2), ("manche", 1)],
		 "Bec de fer pointu au bout d'un manche court, fait pour percer l'armure de la selle.",
		 deg=3, cc=1, r={"F": 12}),
	arme("Pic_de_fantassin", "Pic de fantassin", "⛏️", "commun", 3.0, UNE, ["cac"], 1, 6, ARM,
		 [("fer", 3), ("manche", 1)],
		 "Version plus longue et plus lourde du pic de cavalier.",
		 deg=4, malus_depl=-1, r={"F": 14}),

	# ── Arcs, frondes, propulseurs ──────────────────────────────────────────────────
	arme("Arc_long_composite", "Arc long composite", "🏹", "peu_commun", [1.4, 2.2], AMB, ["tir"], 9, 6,
		 ARC, [("manche", 2), ("cordes_d_arc", 1), ("poix", 1)],
		 "Arc long fait de bois, de corne et de nerf collés : plus puissant qu'un arc d'if.",
		 deg=3, cd=7, r={"Ag": 20, "F": 12}, deux_mains=True, caracs={"Ag": 3}),
	arme("Arc_court_composite", "Arc court composite", "🏹", "peu_commun", [0.6, 1.0], AMB, ["tir"], 7, 4,
		 ARC, [("manche", 1), ("cordes_d_arc", 1), ("poix", 1)],
		 "Arc court recourbé des peuples cavaliers, tirable de la selle.",
		 deg=2, cd=6, r={"Ag": 14}, deux_mains=True, caracs={"Ag": 2}),
	arme("Daikyu", "Daikyu", "🏹", "peu_commun", [1.5, 2.2], AMB, ["tir"], 9, 6,
		 ARC, [("manche", 2), ("cordes_d_arc", 1)],
		 "Grand arc asymétrique, saisi au tiers inférieur.",
		 deg=3, cd=7, r={"Ag": 20}, deux_mains=True, caracs={"Ag": 2}),
	arme("Fronde", "Fronde", "🪨", "commun", 0.1, AMB, ["tir"], 6, 4, CUIR,
		 [("peaux", 1)],
		 "Deux lanières et une poche de cuir ; les billes de plomb vont plus loin que les cailloux.",
		 deg=1, cd=4, r={"Ag": 10}),
	arme("Fustibale", "Fustibale", "🪨", "commun", 1.0, AMB, ["tir"], 7, 6, ["fletcher"],
		 [("manche", 1), ("peaux", 1)],
		 "Bâton de 90 cm à 1,2 m portant une fronde à son extrémité.",
		 deg=2, cd=3, r={"F": 10, "Ag": 12}, deux_mains=True),
	arme("Atlatl", "Atlatl", "🎯", "peu_commun", 0.6, AMB, ["jet"], 5, 6, ["fletcher"],
		 [("manche", 2), ("peaux", 1)],
		 "Propulseur de bois qui allonge le bras et double la portée d'un javelot.",
		 deg=3, cd=3, r={"F": 10, "Ag": 12}),

	# ── Armures de corps (CA AD&D → bonus_pa : cuir 5 · mailles 17 · plates 25) ─────
	armure("Armure_matelassee", "Armure matelassée", "🧥", "commun", [3, 5], ["torse"], 5, CUIR,
		   [("item:Chiffon", 3), ("peaux", 1)],
		   "Gambison de couches de tissu piquées ; chaud, encombrant, mais il amortit.",
		   caracs={"Ag": -2}),
	armure("Armure_de_cuir_cloutee", "Armure de cuir cloutée", "🧥", "commun", [4, 7], ["torse"], 9, ARM,
		   [("peaux", 3), ("fer", 1)],
		   "Cuir épais semé de rivets de métal (besantine).",
		   caracs={"Ag": -3}),
	armure("Armure_annelee", "Armure annelée", "⛓️", "commun", [6, 9], ["torse"], 9, ARM,
		   [("peaux", 3), ("fer", 2)],
		   "Broigne de cuir sur laquelle sont cousus des anneaux de fer.",
		   caracs={"Ag": -3}),
	armure("Armure_de_peau", "Armure de peau", "🐻", "commun", [6, 10], ["torse"], 11, CUIR,
		   [("peaux", 5)],
		   "Peaux épaisses à peine tannées, superposées : chaude et raide.",
		   caracs={"Ag": -5}),
	armure("Brigandine", "Brigandine", "🧥", "commun", [7, 10], ["torse"], 12, ARM,
		   [("peaux", 2), ("fer", 2), ("acier", 1)],
		   "Petites plaques d'acier rivées sous un pourpoint de toile ou de cuir.",
		   r={"F": 14}, caracs={"Ag": -4}),
	armure("Armure_d_ecailles", "Armure d'écailles", "🐟", "commun", [10, 14], ["torse"], 13, ARM,
		   [("fer", 4), ("peaux", 2)],
		   "Écailles de métal qui se chevauchent sur un justaucorps de cuir.",
		   r={"F": 15}, caracs={"Ag": -5}),
	armure("Clibanion", "Clibanion", "🛡️", "commun", [12, 17], ["torse"], 20, ARM,
		   [("acier", 2), ("fer", 3), ("peaux", 2)],
		   "Armure feuilletée : lamelles verticales de métal rivées sur cuir, sur mailles.",
		   r={"F": 20}, caracs={"Ag": -6}),
	armure("Armure_a_bandes", "Armure à bandes", "🛡️", "commun", [11, 15], ["torse"], 20, ARM,
		   [("fer", 4), ("acier", 1), ("peaux", 2)],
		   "Bandes horizontales de métal superposées sur mailles et cuir.",
		   r={"F": 20}, caracs={"Ag": -6}),
	armure("Armure_de_plates_en_bronze", "Armure de plates en bronze", "🟠", "commun", [14, 20], ["torse"], 19,
		   ARM, [("bronze", 5), ("peaux", 2)],
		   "Cuirasse et pièces de bronze à l'antique : solide, mais lourde.",
		   r={"F": 22}, caracs={"Ag": -7}),
	armure("Armure_de_plates", "Armure de plates", "⚜️", "commun", [12, 16], ["torse"], 25, ARM,
		   [("acier", 4), ("fer", 2), ("peaux", 2)],
		   "Cuirasse d'acier sur cotte de mailles, avec les pièces de bras et de jambes.",
		   r={"F": 26}, caracs={"Ag": -6}),
	armure("Armure_de_bataille", "Armure de bataille", "⚜️", "peu_commun", [14, 18], ["torse"], 28, ARM,
		   [("acier", 5), ("fer", 2), ("peaux", 2)],
		   "Plates articulées couvrant tout le corps, ajustées par un maître armurier.",
		   r={"F": 30}, caracs={"Ag": -7}),
	armure("Harnois_complet", "Harnois complet", "🛡️", "rare", [18, 24], ["torse"], 30, ARM,
		   [("acier", 6), ("fer", 3), ("peaux", 2)],
		   "Harnois blanc fait sur mesure, sans un jour : le sommet de l'art de l'armurier.",
		   r={"F": 34}, caracs={"Ag": -9}),

	# ── Casques ─────────────────────────────────────────────────────────────────────
	armure("Bassinet", "Bassinet", "⛑️", "commun", 2.0, ["tete"], 4, ARM,
		   [("fer", 2), ("peaux", 1)],
		   "Casque arrondi et pointu, souvent complété d'un camail."),
	armure("Grand_heaume", "Grand heaume", "⛑️", "commun", 3.0, ["tete"], 6, ARM,
		   [("acier", 2), ("fer", 1), ("peaux", 1)],
		   "Heaume fermé en forme de seau : il protège tout, mais on y voit mal.",
		   caracs={"Ag": -1}),
]


def _norm(s):
	s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
	return " ".join(s.lower().replace("-", " ").replace("'", " ").split())


def _dump_recent():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json"))
				   + glob.glob(os.path.join(RACINE, "telluris-dump-*.json")),
				   key=os.path.basename)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json : impossible de contrôler les collisions.")
	return dumps[-1]


def main() -> int:
	src = _dump_recent()
	with open(src, encoding="utf-8") as fh:
		base = json.load(fh)["docs"]
	par_id = {d["_id"]: d for d in base}
	recettes = [d for d in base if d.get("type") == "recette"]

	# Feuilles globales = intrants qu'aucune recette ne produit (marche._get_marche_map).
	produits, produits_par_cat = set(), {}
	for rc in recettes:
		o = rc.get("objet_final") or ""
		cles = {o}
		it = par_id.get("item:" + o)
		if it and it.get("sous_categorie"):
			cles.add(it["sous_categorie"])
		produits |= cles
		produits_par_cat.setdefault(rc.get("lieu_categorie"), set()).update(cles)

	noms_base = {_norm(d.get("nom")): d["_id"] for d in base
				 if d["_id"].startswith("item:") and d.get("nom")}
	docs, erreurs = [], []
	for (item, lieux, matieres) in PIECES:
		slug = item["_id"][len("item:"):]
		if item["_id"] in par_id:
			erreurs.append("%s : _id déjà en base" % item["_id"])
		if _norm(item["nom"]) in noms_base:
			erreurs.append("%s : nom %r déjà porté par %s"
						   % (item["_id"], item["nom"], noms_base[_norm(item["nom"])]))
		docs.append(item)
		for lieu in lieux:
			for (cle, _q) in matieres:
				nu = cle[len("item:"):] if cle.startswith("item:") else cle
				if cle.startswith("item:") and cle not in par_id:
					erreurs.append("%s : matière %s absente de la base" % (slug, cle))
				elif not cle.startswith("item:") and "item:" + cle not in par_id:
					erreurs.append("%s : item:%s absent (matière valorisée à vide)" % (slug, cle))
				if nu in produits and nu not in produits_par_cat.get(lieu, set()):
					erreurs.append("%s @%s : %r est une FAUSSE FEUILLE (produite ailleurs)"
								   % (slug, lieu, cle))
			rid = "recette:add2e_%s%s" % (slug.lower(), "" if lieu == lieux[0] else "_" + lieu)
			if rid in par_id:
				erreurs.append("%s : déjà en base" % rid)
			docs.append({
				"_id": rid,
				"type": "recette",
				"lieu_categorie": lieu,
				"objet_final": slug,              # ⚠️ == `_id` sans le préfixe `item:`
				"quantite_produite": 1,
				"matieres_premieres": [
					{"item": c, "quantite": q} if c.startswith("item:")
					else {"sous_categorie": c, "quantite": q}
					for (c, q) in matieres
				],
			})

	ids = [d["_id"] for d in docs]
	doublons = {i for i in ids if ids.count(i) > 1}
	if doublons:
		erreurs.append("_id en double dans le fichier : %s" % sorted(doublons))

	if erreurs:
		print("Génération refusée (dump %s) :" % os.path.basename(src), file=sys.stderr)
		for e in erreurs:
			print("  x " + e, file=sys.stderr)
		return 1

	with open(SORTIE, "w", encoding="utf-8") as fh:
		json.dump(docs, fh, ensure_ascii=False, indent=2)

	items = [d for d in docs if d["type"] == "item"]
	print("→ %s  (contrôlé contre %s)" % (os.path.relpath(SORTIE, RACINE), os.path.basename(src)))
	print("   %d armes + %d armures, %d recettes" % (
		sum(1 for d in items if d["categorie"] == "arme"),
		sum(1 for d in items if d["categorie"] == "armure"),
		len(docs) - len(items)))
	return 0


if __name__ == "__main__":
	sys.exit(main())

"""Chasses légendaires — trophées, matières nommées, matériau d'armure, panoplies, mur des
trophées et collectionneur (`docs/conception_trophees_legendaires.md`, Auteur 13/11).

    python dev/gen_trophees_legendaires.py [--dump jsons/telluris-dump-*.json]

Sortie (UN SEUL fichier, delta du dump) :
    jsons/trophees_legendaires_a_importer.json

Contenu :
  1. blocs `fabrication` des parties rare+ et de leurs morceaux — table `dev/legendaires_table.py`,
     relue aussi par dev/gen_fabrication_matieres.py (même diff que lui : `gfm.generer`) ;
  2. matières NOMMÉES (une par espèce) + leur recette à trophée : la pièce de carcasse lourde
     part à une grande maison, qui rend une matière légère (tag `commandable`) ;
  3. tag de matériau `armure_tissu` / `armure_cuir` / `armure_metal` sur les armures
     (`commande.TAGS_MATERIAU_ARMURE`) — bijoux et harnachement exclus ;
  4. trophées 🏆 nommés (armes, armures, catalyseurs, élixirs) — même contrat que
     dev/gen_trophees.py (socle + apport au budget du palier, `valeur` = variante sur mesure) ;
     les plus rares accordent un POUVOIR porté (`competences`, utils/pouvoirs_objets) ;
  5. têtes naturalisées (tag `trophee_expose`) pour le Mur des trophées ;
  6. `rules:panoplies` (utils/characters.panoplies_actives) ;
  7. aménagement `mur_trophees` dans `rules:proprietes` (réveil `requiert_trophee`) ;
  8. service `rachat` du collectionneur sur `pnj:marchand_cabinet_des_specimens`.

⚠️ Garde-fous (rien n'est écrit si l'un échoue) : collisions d'`_id` (un doc différent déjà en
base n'est réécrit QUE s'il figure parmi les docs que ce script complète), budget des paliers,
feuilles du monde inchangées, recettes hors tick et au catalogue de commande de leur maison,
dialogue du collectionneur sans faute (`lint_dialogues.analyser_doc`).
"""

import argparse
import copy
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_recettes_orphelins import brancher_moteur, dernier_dump  # noqa: E402
import legendaires_table as table  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "trophees_legendaires_a_importer.json")
RARETES = ("commun", "peu_commun", "rare", "tres_rare", "legendaire")
CHAMPS_PROPRES = {"_id", "_rev", "type", "nom", "icon", "description", "rarete", "poids",
				  "valeur", "fabrication"}

# ── Matières nommées : maison qui les prépare, intrants, poids ────────────────────
MAISON_SORTE = {
	"ecailles": ("grand_arsenal", [("fer", 1)], 4.0),
	"cuir": ("grande_manufacture_du_cuir", [("cuir", 1)], 3.0),
	"peau": ("grande_manufacture_du_cuir", [("cuir", 1)], 3.0),
	"plumes": ("grande_manufacture_textile", [("soie", 1)], 1.0),
	"soie": ("grande_manufacture_textile", [("soie", 1)], 0.5),
	"os": ("cabinet_des_specimens", [("os", 1)], 5.0),
	"cendre": ("grand_laboratoire_alchimique", [("reactif_brut", 1)], 0.5),
}
SOUS_CATEGORIE_MATIERE = "matiere_legendaire"   # consommée par AUCUNE recette : jamais livrée

# Pouvoirs : sorts et compétences EXISTANTS, restriction lue BRUTE.
def _pouvoir(cap_id, **restriction):
	return [{"id": cap_id, "restriction": restriction}]


# ── Trophées 🏆 nommés ──────────────────────────────────────────────────────────
# slug → {nom, icon, poids, description, socle, trophee, categorie, intrants, apport,
#          [tags], [competences], [panoplie]}
PIECES = {
	# ── Lames draconiques ─────────────────────────────────────────────────────
	"Epee_croc_du_dragon_rouge": {
		"nom": "Épée-croc du Dragon rouge", "icon": "🗡️", "poids": 2.5,
		"description": "Un croc de dragon rouge emmanché comme une lame, cerclé de fer à la garde. "
					   "Il reste chaud au toucher ; quand on le brandit, l'air autour se met à trembler.",
		"socle": "item:Epee_longue", "trophee": "item:dragon_rouge_tete_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 1)],
		"apport": {"bonus_degats": 7, "bonus_cc": 2, "bonus": {"F": 3},
				   "effets": {"buffs": {"R": -2}, "duree": 3}},
		"competences": _pouvoir("sort:souffle_de_feu", Vol=30), "panoplie": "dragon_rouge",
	},
	"Faux_d_os_du_dragon_blanc": {
		"nom": "Faux d'os du Dragon blanc", "icon": "❄️", "poids": 4.0,
		"description": "Une griffe de dragon blanc montée en faucharde. Le givre s'y dépose même au "
					   "soleil, et ce qu'elle entaille se raidit de froid.",
		"socle": "item:Faucharde", "trophee": "item:dragon_blanc_patte_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 1), ("hampe", 1)],
		"apport": {"bonus_degats": 6, "bonus_cc": 1, "bonus": {"R": 3, "Vol": 2},
				   "effets": {"buffs": {"Ag": -2}, "duree": 3}},
		"competences": _pouvoir("sort:regard_glacial", Vol=30),
	},
	"Glaive_ecaille_du_dragon_empereur": {
		"nom": "Glaive-écaille du Dragon Empereur", "icon": "🐉", "poids": 3.5,
		"description": "Une griffe de dragon empereur, plaquée d'écailles jusqu'au talon de la hampe. "
					   "Ceux qui la voient pour la première fois baissent les yeux sans savoir pourquoi.",
		"socle": "item:Glaive", "trophee": "item:dragon_empereur_patte_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 1), ("hampe", 1)],
		"apport": {"bonus_degats": 7, "bonus_cc": 2, "bonus": {"F": 2, "R": 2},
				   "effets": {"buffs": {"Vol": -2}, "duree": 2}},
		"panoplie": "dragon_empereur",
	},
	"Hache_machoire_du_balaur": {
		"nom": "Hache-mâchoire du Balaur", "icon": "🪓", "poids": 4.0,
		"description": "Une demi-mâchoire de balaur, dents comprises, assise sur un manche ferré. "
					   "Dans les Carpates, on dit que la bête mordait encore après avoir perdu la tête.",
		"socle": "item:Hache_de_guerre", "trophee": "item:balaur_tete_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 1)],
		"apport": {"bonus_degats": 5, "bonus_cc": 1, "bonus": {"F": 2},
				   "effets": {"buffs": {"R": -2}, "duree": 2}},
		"panoplie": "balaur",
	},
	# ── Bêtes légendaires ─────────────────────────────────────────────────────
	"Masse_dard_de_tarasque": {
		"nom": "Masse-dard de Tarasque", "icon": "🔨", "poids": 5.0,
		"description": "Le dard écailleux qui termine la queue d'une tarasque, ferré en tête de masse. "
					   "Les riverains du Rhône le reconnaissent de loin, et s'écartent.",
		"socle": "item:Masse_de_fantassin", "trophee": "item:tarasque_queue_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 1)],
		"apport": {"bonus_degats": 3, "bonus_cc": 1, "bonus": {"R": 2},
				   "effets": {"buffs": {"Ag": -1}, "duree": 2}},
		"panoplie": "tarasque",
	},
	"Lance_defense_de_twrch_trwyth": {
		"nom": "Lance-défense de Twrch Trwyth", "icon": "🐗", "poids": 3.0,
		"description": "Une défense du sanglier-roi, ligaturée au bout d'une hampe de frêne. Arthur "
					   "le poursuivit d'Irlande en Cornouailles ; la lance garde l'élan de la traque.",
		"socle": "item:Lance", "trophee": "item:twrch_trwyth_tete_morceau",
		"categorie": "grand_arsenal", "intrants": [("hampe", 1), ("tendons", 1)],
		"apport": {"bonus_degats": 4, "bonus_cc": 2, "bonus": {"F": 2, "Ag": 1},
				   "effets": {"buffs": {"Ag": -1}, "duree": 2}},
		"panoplie": "twrch_trwyth",
	},
	"Fleau_griffe_de_la_bete_du_gevaudan": {
		"nom": "Fléau-griffe de la Bête du Gévaudan", "icon": "🐺", "poids": 3.0,
		"description": "Trois griffes de la Bête, enchaînées au bout d'un fléau. Loup, loup-garou ou "
					   "autre chose : le forgeron qui l'a monté n'a jamais voulu le dire.",
		"socle": "item:Fleau_arme", "trophee": "item:bete_du_gevaudan_patte",
		"categorie": "grand_arsenal", "intrants": [("fer", 1), ("cuir", 1)],
		"apport": {"bonus_degats": 3, "bonus_cc": 1, "bonus": {"Ag": 2},
				   "effets": {"buffs": {"Vol": -1}, "duree": 2}},
	},
	"Arc_tendon_de_cath_palug": {
		"nom": "Arc-tendon de Cath Palug", "icon": "🏹", "poids": 1.5,
		"description": "Un arc long bandé des tendons de la queue du chat d'Anglesey. La corde vibre "
					   "comme un feulement, et la flèche part avant qu'on ait fini de viser.",
		"socle": "item:Arc_long", "trophee": "item:cath_palug_queue",
		"categorie": "grand_atelier_d_empennage", "intrants": [],
		"apport": {"bonus_degats": 3, "bonus_cd": 2, "bonus": {"Ag": 2}},
	},
	# ── Abysses ───────────────────────────────────────────────────────────────
	"Trident_bec_du_kraken": {
		"nom": "Trident-bec du Kraken", "icon": "🔱", "poids": 3.5,
		"description": "Le bec corné d'un kraken, fendu en trois pointes sur une hampe de chêne. Les "
					   "marins de Norvège l'avaient pris pour une île ; ce trident-là ne s'y trompe pas.",
		"socle": "item:Trident", "trophee": "item:kraken_tete_morceau",
		"categorie": "grand_arsenal", "intrants": [("hampe", 1), ("fer", 1)],
		"apport": {"bonus_degats": 4, "bonus_cc": 2, "bonus": {"R": 2},
				   "effets": {"buffs": {"Ag": -2}, "duree": 2}},
	},
	"Harpon_epine_du_leviathan": {
		"nom": "Harpon-épine du Léviathan", "icon": "🌊", "poids": 4.0,
		"description": "Une épine dorsale du Léviathan, barbelée, emmanchée comme un harpon. Le fer "
					   "n'entre pas dans sa carapace, dit le vieux texte : son épine, si.",
		"socle": "item:Harpon", "trophee": "item:leviathan_queue_morceau",
		"categorie": "grand_arsenal", "intrants": [("hampe", 1), ("fer", 1)],
		"apport": {"bonus_degats": 7, "bonus_cd": 2, "bonus": {"R": 3},
				   "effets": {"buffs": {"Ag": -2}, "duree": 3}},
		"competences": _pouvoir("competence:raz_de_maree", Vol=35), "panoplie": "leviathan",
	},
	"Fouet_tentacule_du_kraken_polaire": {
		"nom": "Fouet-tentacule du Kraken polaire", "icon": "🦑", "poids": 2.5,
		"description": "Un bras de kraken polaire, séché et tressé de cuir jusqu'aux ventouses. La "
					   "mer gelait sur le passage de la bête ; le fouet engourdit ce qu'il enlace.",
		"socle": "item:Fouet", "trophee": "item:polar_kraken_patte_morceau",
		"categorie": "grande_manufacture_du_cuir", "intrants": [("cuir", 1), ("tendons", 1)],
		"apport": {"bonus_degats": 3, "bonus_cc": 2, "bonus": {"Ag": 2},
				   "effets": {"buffs": {"Ag": -2}, "duree": 3}},
	},
	"Dague_dent_du_grootslang": {
		"nom": "Dague-dent du Grootslang", "icon": "🐍", "poids": 0.8,
		"description": "Un crochet à venin du serpent-éléphant des gouffres du Richtersveld, monté en "
					   "dague. Les chercheurs de diamants qui l'ont vu s'en écartent comme de la bête.",
		"socle": "item:Dague", "trophee": "item:grootslang_tete_morceau",
		"categorie": "grand_arsenal", "intrants": [("cuir", 1)],
		"apport": {"bonus_degats": 3, "bonus_cc": 2, "bonus": {"Ag": 2},
				   "effets": {"regen_pv": -4, "duree": 2}},
		"competences": _pouvoir("sort:main_de_venin", Ag=30),
	},
	# ── Céleste / infernal ────────────────────────────────────────────────────
	"Epee_plume_du_seraphin": {
		"nom": "Épée-plume du Séraphin", "icon": "🪽", "poids": 1.8,
		"description": "Une rémige de séraphin, durcie et affûtée, sertie dans une garde d'acier. "
					   "Elle pèse moins qu'une épée de bois et ne ternit pas.",
		"socle": "item:Epee_une_main_benie", "trophee": "item:seraphin_aile",
		"categorie": "grand_arsenal", "intrants": [("fer", 1), ("cuir", 1)],
		"apport": {"bonus_degats": 6, "bonus_cc": 2, "bonus": {"Vol": 4},
				   "effets": {"buffs": {"Vol": -2}, "duree": 3}},
		"panoplie": "seraphin",
	},
	"Sceptre_corne_du_prince_demon": {
		"nom": "Sceptre-corne du Prince Démon", "icon": "😈", "poids": 2.0,
		"description": "Une corne du Prince Démon, montée en sceptre et baguée de fer noir. Elle "
					   "sent le soufre par temps de pluie ; ceux qui la portent dorment mal.",
		"socle": "item:Sceptre_os", "trophee": "item:prince_demon_tete",
		"categorie": "grand_arsenal", "intrants": [("fer", 1)],
		"apport": {"bonus_degats": 3, "bonus_pm": 10, "bonus": {"Vol": 3, "Int": 2},
				   "effets": {"buffs": {"Vol": -2}, "duree": 2}},
		"competences": _pouvoir("sort:souffle_de_soufre", Vol=30),
	},
	"Lance_aile_de_l_archange_de_l_ordre": {
		"nom": "Lance-aile de l'Archange de l'Ordre", "icon": "🪶", "poids": 3.0,
		"description": "Une lance de cavalier dont le fer est fait d'un faisceau de plumes d'archange "
					   "liées et durcies. Ce qui vient du ciel ne dit pas d'où il vient.",
		"socle": "item:Lance_de_cavalerie_moyenne", "trophee": "item:archange_de_l_ordre_aile",
		"categorie": "grand_arsenal", "intrants": [("fer", 1), ("hampe", 1)],
		"apport": {"bonus_degats": 5, "bonus_cc": 2, "bonus": {"Vol": 2},
				   "effets": {"buffs": {"Vol": -1}, "duree": 2}},
	},
	"Massue_du_geant_du_mont_saint_michel": {
		"nom": "Massue du Géant du Mont-Saint-Michel", "icon": "🦴", "poids": 8.0,
		"description": "L'avant-bras du géant du mont, durci et cerclé de fer, à peine taillé. Les "
					   "conteurs bretons disent qu'Arthur l'affronta seul ; il faut deux bras pour le lever.",
		"socle": "item:Massue", "trophee": "item:geant_du_mont_saint_michel_bras",
		"categorie": "grand_arsenal", "intrants": [("fer", 2)],
		"apport": {"bonus_degats": 4, "bonus": {"F": 3}, "restriction": {"F": 30}},
	},
	# ── Armures de métal ──────────────────────────────────────────────────────
	"Heaume_crane_du_dragon_rouge": {
		"nom": "Heaume-crâne du Dragon rouge", "icon": "🔥", "poids": 4.5,
		"description": "Le haut du crâne d'un dragon rouge, évidé et doublé de plates, les arcades en "
					   "visière. Il ne refroidit jamais tout à fait.",
		"socle": "item:Heaume_de_plates", "trophee": "item:dragon_rouge_tete_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 1)],
		"apport": {"bonus_pa": 7, "bonus_pv": 6, "bonus": {"F": 2, "Vol": 2}, "effets": {"esquive": 1}},
		"panoplie": "dragon_rouge",
	},
	"Cuirasse_d_ecailles_du_dragon_empereur": {
		"nom": "Cuirasse d'écailles du Dragon Empereur", "icon": "🐉", "poids": 14.0,
		"description": "Des écailles de dragon empereur cousues en recouvrement sur une armure "
					   "d'écailles ordinaire, qu'elles éclipsent. Plus vieux que les Anthropes, dit-on.",
		"socle": "item:Armure_d_ecailles", "trophee": "item:dragon_empereur_corps_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 2)],
		"apport": {"bonus_pa": 8, "bonus_pv": 8, "bonus": {"R": 3}},
		"panoplie": "dragon_empereur",
	},
	"Gantelets_griffes_du_balaur": {
		"nom": "Gantelets-griffes du Balaur", "icon": "🧤", "poids": 2.5,
		"description": "Des gantelets de plates terminés par les griffes d'un balaur. Vlad, dit-on, "
					   "empalait les monstres en lisière de ses terres ; celui-là, il ne put l'empaler.",
		"socle": "item:Gantelets_de_plates", "trophee": "item:balaur_patte",
		"categorie": "grand_arsenal", "intrants": [("fer", 1), ("cuir", 1)],
		"apport": {"bonus_pa": 4, "bonus_pv": 6, "bonus": {"F": 2, "R": 1}},
		"panoplie": "balaur",
	},
	# ── Armures de cuir ───────────────────────────────────────────────────────
	"Brigandine_en_peau_du_leviathan": {
		"nom": "Brigandine en peau du Léviathan", "icon": "🌊", "poids": 10.0,
		"description": "Une brigandine dont les plates sont des écailles du Léviathan, rivées sous "
					   "un cuir épais. « Sa carapace est faite de boucliers serrés », dit le vieux texte.",
		"socle": "item:Brigandine", "trophee": "item:leviathan_corps_morceau",
		"categorie": "grande_manufacture_du_cuir", "intrants": [("cuir", 2)],
		"apport": {"bonus_pa": 7, "bonus_pv": 8, "bonus": {"R": 3}, "effets": {"esquive": 1}},
		"panoplie": "leviathan",
	},
	"Bottes_en_peau_des_vers_des_sables": {
		"nom": "Bottes en peau des Vers des Sables", "icon": "🥾", "poids": 2.0,
		"description": "Des bottes taillées dans la peau d'un ver des sables. Le désert tremble avant "
					   "qu'ils ne surgissent ; celui qui les porte sent venir la secousse.",
		"socle": "item:Bottes_cuir_epais", "trophee": "item:vers_des_sables_corps_morceau",
		"categorie": "grande_manufacture_du_cuir", "intrants": [("cuir", 1)],
		"apport": {"bonus_pa": 3, "bonus_pv": 6, "bonus": {"R": 3}, "effets": {"esquive": 1}},
	},
	"Jaque_de_twrch_trwyth": {
		"nom": "Jaque de Twrch Trwyth", "icon": "🐗", "poids": 7.0,
		"description": "Un jaque matelassé des soies du sanglier-roi, dures comme des aiguilles. "
					   "Entre ses oreilles, la bête portait un peigne et des ciseaux.",
		"socle": "item:Jaque_de_crin", "trophee": "item:twrch_trwyth_corps_morceau",
		"categorie": "grande_manufacture_du_cuir", "intrants": [("cuir", 1)],
		"apport": {"bonus_pa": 4, "bonus_pv": 6, "bonus": {"R": 2, "F": 1}},
		"panoplie": "twrch_trwyth",
	},
	"Cape_ailes_de_zmei_gorynytch": {
		"nom": "Cape-ailes de Zmeï Gorynytch", "icon": "🐉", "poids": 3.0,
		"description": "La membrane d'une aile du dragon du pont Kalinov, tendue sur des baleines "
					   "d'os. Au premier coup de vent, elle tire vers le ciel.",
		"socle": "item:Cape_de_fourrure", "trophee": "item:zmey_gorynych_aile_morceau",
		"categorie": "grande_manufacture_du_cuir", "intrants": [("cuir", 1)],
		"apport": {"bonus_pa": 3, "bonus_pv": 6, "bonus_initiative": 2, "bonus": {"Ag": 3, "Vol": 2},
				   "effets": {"esquive": 2}},
		"competences": _pouvoir("sort:envol_du_griffon", Ag=35),
	},
	# ── Armures de tissu ──────────────────────────────────────────────────────
	"Robe_de_soie_du_seraphin": {
		"nom": "Robe de soie du Séraphin", "icon": "🪽", "poids": 1.5,
		"description": "Une robe tissée du duvet d'un séraphin. Six ailes, disent les prophètes ; il "
					   "en faut une seule pour une robe, et elle tient chaud sans rien peser.",
		"socle": "item:Robe_de_savant", "trophee": "item:seraphin_corps_morceau",
		"categorie": "grande_manufacture_textile", "intrants": [("soie", 2)],
		"apport": {"bonus_pm": 10, "bonus": {"Vol": 3, "Int": 2},
				   "effets": {"regen_pv": 1, "regen_pm": 1, "canalisation": 1}},
		"competences": _pouvoir("sort:soin_regenerant", Vol=30), "panoplie": "seraphin",
	},
	"Manteau_de_plumes_du_grand_phenix": {
		"nom": "Manteau de plumes du Grand Phénix", "icon": "🔥", "poids": 2.0,
		"description": "Un manteau couvert des plumes d'un grand phénix. Elles restent tièdes, et "
					   "les blessures de qui le porte se referment plus vite.",
		"socle": "item:Manteau_de_ratine", "trophee": "item:grand_phenix_corps_morceau",
		"categorie": "grande_manufacture_textile", "intrants": [("soie", 1)],
		"apport": {"bonus_pm": 6, "bonus_pv": 4, "bonus": {"Vol": 2},
				   "effets": {"regen_pv": 1, "esquive": 1}},
	},
	"Capuche_ecaille_d_illuyanka": {
		"nom": "Capuche-écaille d'Illuyanka", "icon": "🐉", "poids": 0.8,
		"description": "Une capuche de soie doublée d'écailles du serpent d'Anatolie. Il vainquit le "
					   "dieu de l'orage avant d'être pris au piège d'un festin : méfiez-vous des banquets.",
		"socle": "item:Capuche_soie", "trophee": "item:illuyanka_tete_morceau",
		"categorie": "grande_manufacture_textile", "intrants": [("soie", 1)],
		"apport": {"bonus_pa": 2, "bonus_pm": 4, "bonus": {"Int": 2, "R": 2, "Vol": 1},
				   "effets": {"esquive": 1}},
	},
	"Etole_de_gwyn_ap_nudd": {
		"nom": "Étole de Gwyn ap Nudd", "icon": "🌫️", "poids": 0.6,
		"description": "Une étole tissée de ce que le roi de l'Annwn laisse derrière lui quand il "
					   "mène la Chasse sauvage. Elle se froisse comme de la brume.",
		"socle": "item:Etole_de_fourrure", "trophee": "item:gwyn_ap_nudd_corps",
		"categorie": "grande_manufacture_textile", "intrants": [("soie", 1)],
		"apport": {"bonus_pm": 8, "bonus": {"Int": 3, "Cha": 2},
				   "effets": {"esquive": 2, "regen_pm": 1, "canalisation": 2}},
	},
	# ── Bijoux et catalyseurs ─────────────────────────────────────────────────
	"Oeil_de_ladon_serti": {
		"nom": "Œil de Ladon serti", "icon": "👁️", "poids": 0.5,
		"description": "Un œil du gardien des Hespérides, figé dans une monture d'or. Né de Cétô ou "
					   "d'Échidna, il ne dormait jamais ; l'œil non plus.",
		"socle": "item:amulette", "trophee": "item:ladon_tete_morceau",
		"categorie": "grande_orfevrerie", "intrants": [("metaux_precieux", 1)],
		"apport": {"bonus_pm": 6, "bonus_pv": 6, "bonus": {"Vol": 2, "Int": 2}},
	},
	"Coeur_cristallise_du_dragon_rouge": {
		"nom": "Cœur cristallisé du Dragon rouge", "icon": "❤️‍🔥", "poids": 1.5,
		"description": "Un fragment de cœur de dragon rouge, réduit et cristallisé au bain d'alchimie. "
					   "Il bat encore, lentement, quand on le serre dans la main.",
		"socle": "item:focus_magique", "trophee": "item:dragon_rouge_corps_morceau",
		"categorie": "grand_laboratoire_alchimique", "intrants": [("reactif_brut", 1)],
		"apport": {"bonus_pm": 12, "bonus": {"Vol": 3, "Int": 3},
				   "effets": {"regen_pm": 1, "canalisation": 2}, "restriction": {"Vol": 30}},
		"panoplie": "dragon_rouge",
	},
	"Baton_vertebre_de_l_hydre": {
		"nom": "Bâton-vertèbre de l'Hydre", "icon": "🦴", "poids": 2.5,
		"description": "Une colonne de vertèbres d'hydre, enfilées sur une âme de fer. Coupez une "
					   "tête, deux repoussent : le bâton, lui, suinte encore son venin.",
		"socle": "item:Baton_canalisateur", "trophee": "item:hydre_queue_morceau",
		"categorie": "cabinet_des_specimens", "intrants": [("os", 1)],
		"apport": {"bonus_degats": 1, "bonus_pm": 6, "bonus": {"Int": 2},
				   "effets": {"regen_pv": -2, "duree": 2}},
	},
	"Orbe_oeil_de_l_avatar": {
		"nom": "Orbe-œil de l'Avatar", "icon": "🔮", "poids": 0.8,
		"description": "L'œil d'un dieu incarné, devenu globe de cristal sous la main des orfèvres. "
					   "Ce qu'il a vu, il ne le montre pas ; ce qu'il voit, il le laisse deviner.",
		"socle": "item:Orbe_arcanique", "trophee": "item:avatar_tete",
		"categorie": "grande_orfevrerie", "intrants": [("metaux_precieux", 1)],
		"apport": {"bonus_pm": 10, "bonus": {"Int": 4, "Vol": 3}, "effets": {"canalisation": 3},
				   "restriction": {"Int": 30}},
	},
	# ── Élixirs ───────────────────────────────────────────────────────────────
	"Elixir_de_sang_d_hydre": {
		"nom": "Élixir de sang d'hydre", "icon": "🧪", "poids": 0.3,
		"description": "Sang d'hydre réduit au bain-marie : les chairs se referment comme les têtes "
					   "de la bête repoussaient, un peu moins vite.",
		"socle": "item:elixir_revigorant", "trophee": "item:hydre_corps_morceau",
		"categorie": "grand_laboratoire_alchimique",
		"intrants": [("item:Herbes_medicinales", 1), ("reactif_brut", 1)],
		"apport": {"effets": {"pv": 10, "regen_pv": 2, "buffs": {"R": 1}, "duree": 6}},
		"tags": ["non_personnalisable"],
	},
	"Elixir_de_cendre_du_phenix": {
		"nom": "Élixir de cendre du phénix", "icon": "🔥", "poids": 0.3,
		"description": "Cendre de grand phénix délayée dans l'huile chaude. On la boit d'un trait ; "
					   "on se relève comme d'un brasier.",
		"socle": "item:elixir_revigorant", "trophee": "item:grand_phenix_corps_morceau",
		"categorie": "grand_laboratoire_alchimique",
		"intrants": [("item:Herbes_medicinales", 1), ("reactif_brut", 1)],
		"apport": {"effets": {"pv": 30, "regen_pv": 2, "duree": 5}},
		"tags": ["non_personnalisable"],
	},
	"Elixir_de_givre_du_dragon_blanc": {
		"nom": "Élixir de givre du Dragon blanc", "icon": "❄️", "poids": 0.3,
		"description": "Sang de dragon blanc, gardé au froid. Il gèle la gorge, puis la peur.",
		"socle": "item:elixir_revigorant", "trophee": "item:dragon_blanc_corps_morceau",
		"categorie": "grand_laboratoire_alchimique",
		"intrants": [("item:Herbes_medicinales", 1), ("reactif_brut", 1)],
		"apport": {"effets": {"pv": 20, "buffs": {"R": 6, "Vol": 4}, "duree": 6}},
		"tags": ["non_personnalisable"],
	},
	"Elixir_d_encre_de_kraken": {
		"nom": "Élixir d'encre de kraken", "icon": "🦑", "poids": 0.3,
		"description": "Encre de kraken coupée de réactif. Elle noircit la langue et éclaircit "
					   "l'esprit : les mages en boivent avant les longues incantations.",
		"socle": "item:elixir_revigorant", "trophee": "item:kraken_corps_morceau",
		"categorie": "grand_laboratoire_alchimique",
		"intrants": [("item:Herbes_medicinales", 1), ("reactif_brut", 1)],
		"apport": {"effets": {"pm": 20, "regen_pm": 2, "buffs": {"Int": 2}, "duree": 5}},
		"tags": ["non_personnalisable"],
	},
}

# Docs EXISTANTS que ce script complète (clé par clé, le reste du doc relu du dump).
COMPLEMENTS = {"item:Pavois_de_tarasque": {"panoplie": "tarasque"}}

PANOPLIES = {
	"dragon_rouge": {"nom": "Panoplie du Dragon rouge", "icon": "🔥", "seuils": {
		"2": {"bonus_pv": 10, "effets": {"regen_pv": 1}},
		"3": {"bonus_pv": 20, "bonus_pa": 4, "bonus": {"F": 2}, "effets": {"regen_pv": 2}}}},
	"dragon_empereur": {"nom": "Panoplie du Dragon Empereur", "icon": "🐉",
						"seuils": {"2": {"bonus_pa": 4, "bonus": {"R": 2}}}},
	"balaur": {"nom": "Panoplie du Balaur", "icon": "🐉",
			   "seuils": {"2": {"bonus_cc": 2, "bonus": {"F": 2}}}},
	"tarasque": {"nom": "Panoplie de la Tarasque", "icon": "🐢",
				 "seuils": {"2": {"bonus_pa": 4, "bonus_pv": 8}}},
	"twrch_trwyth": {"nom": "Panoplie de Twrch Trwyth", "icon": "🐗",
					 "seuils": {"2": {"bonus_initiative": 2, "bonus": {"F": 1, "R": 1}}}},
	"leviathan": {"nom": "Panoplie du Léviathan", "icon": "🌊",
				  "seuils": {"2": {"bonus_pv": 10, "bonus": {"R": 2}, "effets": {"esquive": 1}}}},
	"seraphin": {"nom": "Panoplie du Séraphin", "icon": "🪽",
				 "seuils": {"2": {"bonus_pm": 10, "bonus": {"Vol": 2}, "effets": {"regen_pm": 1}}}},
}

MUR = {
	"id": "mur_trophees", "nom": "Mur des trophées", "categorie": "vie",
	"types_autorises": ["maison", "demeure", "domaine"], "cout_cuivre": 3000, "prerequis": [],
	"capacite": {},
	"effets": {"reveil": {"duree": 25, "icon": "🏆", "nom": "Fierté du chasseur",
						  "buffs": {"Cha": 3, "Vol": 2}, "requiert_trophee": True}},
	"description": "Un panneau de chêne pour exposer une tête naturalisée. Rangée au coffre, la "
				   "pièce y est accrochée : au réveil, on passe devant.",
}

COLLECTIONNEUR = "pnj:marchand_cabinet_des_specimens"
FACTEUR_COLLECTION = 1.5     # « au prix fort » : 1,5 × le coût de marché de la pièce
NOEUDS_COLLECTION = {
	"collection_offre": {
		"texte": "« Des pièces de chasse, dites-vous ? » {pnj} repose sa loupe. « Je ne prends que "
				 "les têtes des bêtes dont on parle dans les récits — dragons, hydres, léviathans… — "
				 "et je les paie au prix fort. Mieux encore si le chasseur a laissé son nom dessus. »",
		"choix": [
			{"id": "collection_vendre", "label": "Voici ce que je rapporte.",
			 "action": {"service": "rachat", "op": "vendre"}},
			{"id": "collection_non", "label": "Je les garde, finalement.", "next": "accueil"},
		],
	},
	"collection_vendue": {
		"texte": "{pnj} examine chaque pièce longuement avant de compter l'argent. « {objet}. "
				 "{prix}, comme convenu. Elles iront en vitrine, avec le nom de qui les a rapportées. »",
		"choix": [{"id": "ok", "label": "Marché conclu.", "next": "accueil"}],
	},
	"collection_rien": {
		"texte": "« Je ne vois rien ici qui manque à mes vitrines, {prenom}. Revenez avec une tête "
				 "dont on parle dans les récits. »",
		"choix": [{"id": "ok", "label": "Une autre fois.", "next": "accueil"}],
	},
}


# ── Matériau d'armure ───────────────────────────────────────────────────────────
# Ordre de lecture : une MATIÈRE de cuir nommée l'emporte (« Jambières de cuir »), puis le métal,
# puis les pièces qui sont du cuir par défaut (« Bottes » — mais « Bottes de fer » est du métal).
MOTS_CUIR_MATIERE = ("cuir", "peau", "fourrure", "croupon", "chamois", "pelisse", "crin", "loup")
MOTS_METAL = ("plate", "fer", "acier", "maille", "harnois", "heaume", "écaille", "ecaille", "bronze",
			  "annel", "bandes", "bataille", "bassinet", "clibanion", "brigandine", "bouclier", "pavois")
MOTS_CUIR = ("bottes", "botte", "jaque", "gants", "gantelets", "casque", "souliers")
MOTS_TISSU = ("robe", "soie", "lin", "laine", "capuche", "chaperon", "manteau", "cape", "tunique",
			  "matelass", "étole", "etole", "chapeau", "plumes", "feuilles", "ratine", "feutre")
SLOTS_BIJOU = {"cou", "anneau_1", "anneau_2", "ceinture"}


def materiau_armure(doc: dict) -> str | None:
	"""`armure_metal` / `armure_cuir` / `armure_tissu` d'une armure, ou None (bijou, harnachement,
	monture). Mots du nom d'abord (cf. l'ordre ci-dessus : « Cape de fourrure » est du cuir), puis
	les PA : ≥ 9 métal, ≥ 3 cuir, sinon tissu."""
	if doc.get("categorie") != "armure":
		return None
	slots = set(doc.get("slots") or [])
	if not slots or slots <= SLOTS_BIJOU or any(str(s).startswith("monture") for s in slots) \
			or "harnachement" in (doc.get("tags") or []) or doc.get("sous_categorie") in ("bijou", "insigne"):
		return None
	nom = (doc.get("nom") or "").lower()
	for mots, tag in ((MOTS_CUIR_MATIERE, "armure_cuir"), (MOTS_METAL, "armure_metal"),
					  (MOTS_CUIR, "armure_cuir"), (MOTS_TISSU, "armure_tissu")):
		if any(m in nom for m in mots):
			return tag
	pa = doc.get("bonus_pa") or 0
	return "armure_metal" if pa >= 9 else "armure_cuir" if pa >= 3 else "armure_tissu"


# ── Construction (pur) ──────────────────────────────────────────────────────────

def appliquer_apport(socle: dict, apport: dict) -> dict:
	import gen_trophees
	return gen_trophees.appliquer_apport(socle, apport)


def item_piece(slug: str, p: dict, socle: dict, rarete_palier: str | None) -> dict:
	jeu = appliquer_apport(socle, p["apport"])
	rarete = max((socle.get("rarete") or "commun", rarete_palier or "commun"), key=RARETES.index)
	doc = {"_id": "item:" + slug, "type": "item", "nom": p["nom"], "icon": p["icon"],
		   "description": p["description"], "rarete": rarete,
		   "categorie": jeu.pop("categorie"), "sous_categorie": jeu.pop("sous_categorie", ""),
		   "slots": jeu.pop("slots"), "poids": p["poids"],
		   "tags": list(dict.fromkeys(jeu.pop("tags", []) + p.get("tags", [])))}
	jeu.pop("panoplie", None)
	jeu.pop("competences", None)
	doc.update(jeu)
	if p.get("competences"):
		doc["competences"] = copy.deepcopy(p["competences"])
	if p.get("panoplie"):
		doc["panoplie"] = p["panoplie"]
	return doc


def recette_trophee(categorie: str, slug: str, trophee: str, intrants) -> dict:
	return {
		"_id": "recette:%s_%s" % (categorie, slug.lower()),
		"type": "recette", "lieu_categorie": categorie, "objet_final": slug, "quantite_produite": 1,
		"matieres_premieres": [{"item": trophee, "quantite": 1, "trophee": True}] + [
			({"item": cle} if cle.startswith("item:") else {"sous_categorie": cle}) | {"quantite": q}
			for cle, q in intrants],
	}


def famille(doc: dict) -> list:
	import gen_fabrication_matieres as gfm
	return {"arme": [gfm.TAG_ARME], "consommable": [gfm.TAG_CONSOMMABLE],
			"catalyseur": [gfm.TAG_CATALYSEUR]}.get(doc.get("categorie"), [gfm.TAG_ARMURE])


def erreurs_budget_piece(slug: str, p: dict, socle: dict, doc: dict, palier: int) -> list:
	import gen_fabrication_matieres as gfm
	tags = famille(doc)
	gain = gfm.score_matiere(doc, tags) - gfm.score_matiere(socle, tags)
	bas, haut = gfm.PALIERS[palier]["budget"]
	erreurs = []
	if not bas <= gain <= haut:
		erreurs.append("%s : apport %g hors du budget %d-%d du palier %d" % (slug, gain, bas, haut, palier))
	if gfm._num(p["apport"].get("bonus_degats")) > gfm.PLAFOND_DEGATS:
		erreurs.append("%s : dégâts > plafond" % slug)
	for carac, v in (p["apport"].get("bonus") or {}).items():
		if gfm._num(v) > gfm.PLAFOND_CARAC:
			erreurs.append("%s : %s > plafond" % (slug, carac))
	entree = {"modificateurs": {"effets": doc.get("effets") or {}}, "tags": tags}
	erreurs += ["%s : %s" % (slug, e.split(" : ", 1)[1]) for e in gfm.effets_mal_diriges({slug: entree})]
	return erreurs


def tetes_naturalisees(index: dict) -> dict:
	"""Une tête naturalisée par espèce : trophée = morceau de tête s'il existe, sinon la tête."""
	out = {}
	for esp, (palier, _t, du, _mat, evocation) in table.ESPECES.items():
		base = esp.split(":", 1)[1]
		trophee = next((i for i in ("item:%s_tete_morceau" % base, "item:%s_tete" % base) if i in index), None)
		if not trophee:
			continue
		out["Tete_naturalisee_" + base] = {
			"nom": "Tête naturalisée %s" % du, "icon": "🏆", "poids": 6.0,
			"description": "Montée sur un écu de chêne par les taxidermistes du Cabinet. %s "
						   "Rangée au coffre d'une demeure pourvue d'un Mur des trophées, elle y est "
						   "exposée." % evocation,
			"socle": "item:Specimen_monte", "trophee": trophee, "categorie": "cabinet_des_specimens",
			"intrants": [("os", 1)], "apport": {}, "palier": palier,
			"tags": ["trophee_expose", "non_personnalisable"],
		}
	return out


def matiere_nommee(esp: str) -> tuple[dict, str, list, str]:
	"""(doc squelette, maison, intrants, trophée) d'une matière nommée — bloc posé par gfm."""
	palier, _t, du, (slug, nom, icon, sorte), evocation = table.ESPECES[esp]
	maison, intrants, poids = MAISON_SORTE[sorte]
	doc = {"_id": "item:" + slug, "type": "item", "nom": nom, "icon": icon,
		   "description": "%s, préparée par une grande maison à partir de la bête. %s" % (nom, evocation),
		   "categorie": "composant", "sous_categorie": SOUS_CATEGORIE_MATIERE, "slots": [],
		   "poids": poids, "tags": ["commandable", "legendaire"]}
	return doc, maison, intrants, slug


def trophee_matiere(esp: str, index: dict) -> str | None:
	base = esp.split(":", 1)[1]
	return next((i for i in ("item:%s_corps_morceau" % base, "item:%s_corps" % base) if i in index), None)


def pnj_collectionneur(pnj: dict, articles: list) -> dict:
	doc = copy.deepcopy({k: v for k, v in pnj.items() if k != "_rev"})
	doc.setdefault("services", {})["rachat"] = {
		"articles": articles,
		"noeuds": {"fait": "collection_vendue", "sans_objet": "collection_rien"},
	}
	noeuds = doc["dialogue"]["noeuds"]
	for nid, n in NOEUDS_COLLECTION.items():
		noeuds[nid] = copy.deepcopy(n)
	choix = noeuds["accueil"]["choix"]
	if not any(c.get("id") == "collection" for c in choix):
		pos = next((i for i, c in enumerate(choix) if c.get("id") == "direction"), len(choix))
		choix.insert(pos, {"id": "collection", "label": "J'ai rapporté des pièces de chasse.",
						   "next": "collection_offre", "condition": {"rachat_possible": True}})
	return doc


# ── Lancement ───────────────────────────────────────────────────────────────────

def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	args = ap.parse_args()
	chemin = args.dump or dernier_dump()
	print("source : %s" % os.path.relpath(chemin, RACINE))
	docs = [d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")]
	index = {d["_id"]: d for d in docs}
	marche = brancher_moteur(docs)
	import gen_fabrication_matieres as gfm
	import gen_trophees as gt
	from models import character_stats
	from utils import commande, fabrication, lint_dialogues

	erreurs, sortie = [], {}

	def poser(doc: dict, complete: bool = False):
		"""Ajoute au lot ce doc s'il change la base. `complete` : doc EXISTANT relu et complété."""
		existant = index.get(doc["_id"])
		propre = {k: v for k, v in (existant or {}).items() if k != "_rev"}
		if existant is not None and propre == doc:
			return
		if existant is not None and not complete:
			erreurs.append("%s : _id déjà pris par un autre doc" % doc["_id"])
			return
		sortie[doc["_id"]] = doc

	# 1. Matériau d'armure (avant les trophées : un socle passe son tag à la pièce).
	compte = {}
	nos_pieces = {"item:" + slug for slug in PIECES}   # leur matériau vient de leur SOCLE
	for d in docs:
		tag = materiau_armure(d)
		if not tag or (d.get("fabrication") or {}).get("base_item") or d["_id"] in nos_pieces:
			continue
		compte[tag] = compte.get(tag, 0) + 1
		tags = list(d.get("tags") or [])
		if tag not in tags:
			nouveau = {k: v for k, v in d.items() if k != "_rev"}
			nouveau["tags"] = [t for t in tags if t not in commande.TAGS_MATERIAU_ARMURE] + [tag]
			poser(nouveau, complete=True)
			index[d["_id"]] = dict(d, tags=nouveau["tags"])
	print("matériau d'armure : %s" % compte)

	# 2. Matières nommées : doc squelette + recette à trophée ; bloc posé par gfm ci-dessous.
	lot_recettes = []
	matieres = {}
	for esp in table.ESPECES:
		doc, maison, intrants, slug = matiere_nommee(esp)
		trophee = trophee_matiere(esp, index)
		if not trophee:
			erreurs.append("%s : aucun corps à préparer" % esp)
			continue
		existant = index.get(doc["_id"])
		matieres[doc["_id"]] = (dict(existant) if existant else doc, maison, intrants, trophee, slug)
	entrees = table.entrees_fabrication(gfm._partie, gfm._matiere)
	erreurs += gfm.erreurs_de_forme(entrees) + gfm.erreurs_de_budget(entrees) + gfm.effets_mal_diriges(entrees)
	for mid, (doc, maison, intrants, trophee, slug) in matieres.items():
		complet = gfm.a_ecrire_depuis(entrees[mid], doc) or {k: v for k, v in doc.items() if k != "_rev"}
		cout = marche.cout_production_cuivre(trophee) or 1
		complet.setdefault("valeur", [{"cu": int(cout * 0.8)}, {"cu": int(cout * 1.2)}])
		poser(complet, complete=mid in index)
		lot_recettes.append((complet, recette_trophee(maison, slug, trophee, intrants), maison, trophee))

	# 3. Blocs des parties existantes : même diff que gen_fabrication_matieres.
	parties = {k: v for k, v in entrees.items() if k not in matieres}
	diff, absents, _jt, _orph, _inch = gfm.generer(docs, parties)
	if absents:
		erreurs.append("parties absentes du dump : %s" % ", ".join(absents))
	for d in diff:
		poser(d, complete=True)
		index[d["_id"]] = d

	# 4. Trophées + têtes naturalisées.
	pieces = dict(PIECES)
	pieces.update(tetes_naturalisees(index))
	for slug in sorted(pieces):
		p = pieces[slug]
		socle, trophee = index.get(p["socle"]), index.get(p["trophee"])
		if not socle or not trophee or not trophee.get("source_espece"):
			erreurs.append("%s : socle ou trophée absent (%s, %s)" % (slug, p["socle"], p["trophee"]))
			continue
		palier = p.get("palier") or gt.palier_espece(index.get(trophee["source_espece"]))
		doc = item_piece(slug, p, socle, gfm.PALIERS[palier]["rarete"])
		if p["apport"]:
			erreurs += erreurs_budget_piece(slug, p, socle, doc, palier)
		connus = set(marche.besoins_categorie(p["categorie"])) | marche.produits_categorie(p["categorie"])
		mats = [(trophee, 1)]
		for cle, q in p["intrants"]:
			if cle not in connus and marche.matiere_item_id(cle) not in connus:
				erreurs.append("%s : %s ni acheté ni produit par « %s »" % (slug, cle, p["categorie"]))
			intrant = index.get(marche.matiere_item_id(cle))
			if intrant:
				mats.append((intrant, q))
		doc["valeur"] = gt.valeur_piece(marche, commande, fabrication, socle, mats,
										gfm.PALIERS[palier]["valeur"])
		poser(doc)
		lot_recettes.append((doc, recette_trophee(p["categorie"], slug, p["trophee"], p["intrants"]),
							 p["categorie"], p["trophee"]))
	for _doc, recette, _cat, _t in lot_recettes:
		poser(recette)

	# 5. Compléments de docs existants.
	for iid, champs in COMPLEMENTS.items():
		if iid in index:
			poser({k: v for k, v in index[iid].items() if k != "_rev"} | champs, complete=True)

	# 6. Panoplies, mur des trophées, collectionneur.
	poser({"_id": "rules:panoplies", "type": "rules", "panoplies": PANOPLIES},
		  complete="rules:panoplies" in index)
	rp = index.get("rules:proprietes")
	if rp:
		rp = copy.deepcopy({k: v for k, v in rp.items() if k != "_rev"})
		ams = rp["value"]["amenagements"]
		rp["value"]["amenagements"] = [a for a in ams if a.get("id") != MUR["id"]] + [MUR]
		poser(rp, complete=True)
	articles = []
	for esp in table.ESPECES:
		tete = "item:%s_tete" % esp.split(":", 1)[1]
		if tete in index:
			cout = marche.cout_production_cuivre(tete) or 0
			articles.append({"item": tete, "cout_cuivre": max(100, int(round(cout * FACTEUR_COLLECTION, -1)))})
	if COLLECTIONNEUR in index:
		pnj = pnj_collectionneur(index[COLLECTIONNEUR], articles)
		erreurs += ["%s : %s" % (COLLECTIONNEUR, e) for e in lint_dialogues.analyser_doc(pnj)]
		poser(pnj, complete=True)
	else:
		erreurs.append("%s absent du dump" % COLLECTIONNEUR)

	# Panoplies : chaque id cité par une pièce est déclaré, et chaque panoplie a ≥ 2 pièces.
	cites = {}
	for d in ({**index, **sortie}).values():          # état de la base APRÈS import
		pid = d.get("panoplie") if d.get("type") == "item" else None
		if pid:
			cites.setdefault(pid, set()).add(d["_id"])
	for pid in PANOPLIES:
		if len(cites.get(pid, ())) < 2:
			erreurs.append("panoplie %s : moins de deux pièces" % pid)
	for pid in cites:
		if pid not in PANOPLIES:
			erreurs.append("panoplie %s citée mais non déclarée" % pid)

	# ── Le lot vu par le moteur : recettes de COMMANDE seules ──
	feuilles_avant = set(marche._get_marche_map()["feuilles"])
	for d in sortie.values():
		if d["_id"] in index:
			docs[:] = [x if x.get("_id") != d["_id"] else d for x in docs]
		else:
			docs.append(d)
	marche.reset_prix_cache()
	mm = marche._get_marche_map()
	if mm["feuilles"] != feuilles_avant:
		erreurs.append("feuilles du monde modifiées : %s" % sorted(mm["feuilles"] ^ feuilles_avant))
	consommees = marche.cles_consommees()
	lieux = [d for d in docs if d["_id"].startswith("lieu:")]
	for doc, recette, cat, trophee in lot_recettes:
		if cat not in character_stats.LIEU_CATEGORIES_FUSION:
			erreurs.append("%s : « %s » n'est pas une grande maison" % (doc["_id"], cat))
		if trophee in consommees:
			erreurs.append("%s : %s consommé par une recette de production" % (doc["_id"], trophee))
		maisons = [l for l in lieux if l.get("categorie") == cat]
		if not maisons:
			erreurs.append("%s : aucun lieu « %s »" % (doc["_id"], cat))
		for l in maisons:
			if any(r["_id"] == recette["_id"] for r in marche.recettes_lieu(l)):
				erreurs.append("%s : cuit par le tick de %s" % (doc["_id"], l["_id"]))
			if doc["_id"] not in commande.catalogue_commandable(l):
				erreurs.append("%s : absent du catalogue de commande de %s" % (doc["_id"], l["_id"]))
			if (commande.recette_pour(l, doc["_id"]) or {}).get("_id") != recette["_id"]:
				erreurs.append("%s : %s ne retrouve pas la recette" % (doc["_id"], l["_id"]))

	if erreurs:
		print("\n%d ERREUR(S) — rien n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("  ✗ " + e)
		sys.exit(1)
	par_type = {}
	for d in sortie.values():
		cle = d["_id"].split(":", 1)[0]
		par_type[cle] = par_type.get(cle, 0) + 1
	print("%d doc(s) à importer : %s" % (len(sortie), par_type))
	if not sortie:
		print("Base à jour — aucun fichier écrit.")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(list(sortie.values()), f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("→ %s" % os.path.relpath(SORTIE, RACINE))


if __name__ == "__main__":
	main()

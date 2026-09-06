"""Génère l'import des MAGASINS DE NIVEAU SUPÉRIEUR (les grandes manufactures de Lutèce).

Une grande maison réunit plusieurs métiers sous un toit : sa catégorie de lieu en INCLUT
d'autres (`character_stats.LIEU_CATEGORIES_FUSION`), et `utils/marche.categories_incluses`
résout cette fusion À LA LECTURE. Elle sait donc déjà tout faire de ses métiers réunis sans
qu'une seule recette soit dupliquée en base ; ce script n'écrit QUE ce que la fusion ne peut
pas déduire :

    · les enseignes (`lieu:*`), leurs portes (`connection`) et leurs tenanciers (`pnj:*`) ;
    · les items et recettes EXCLUSIFS à chaque grande maison.

    python dev/gen_magasins_superieurs.py [chemin/vers/telluris-dump-*.json]

Sorties :
    jsons/magasins_superieurs_a_importer.json        (à coller dans la carte d'import de /admin)
    jsons/magasins_superieurs_images_manquantes.txt  (les images à dessiner)

⚠️ Les recettes exclusives sont CROISÉES : leurs intrants ne peuvent PAS être réunis par un
seul des métiers fusionnés. C'est ce qui justifie la grande maison — l'atelier de quartier
n'aura jamais la clé manquante en stock, quoi qu'il produise. Le garde-fou `_metier_unique`
le vérifie recette par recette et refuse d'écrire le fichier sinon.

⚠️ Ce script REBRANCHE `db.config` sur le dump avant d'importer `utils.marche` (même procédé
que dev/audit_economy.py) : les besoins, produits et feuilles d'appro sortent du moteur du
jeu, pas d'une réimplémentation. Une clé matière qu'aucun des métiers réunis ne consomme ou
ne produit est donc détectée ici, et pas six mois plus tard sur un rayon resté vide.

⚠️ POSITION DES PORTES : posées sur des cases de la grille de Lutèce qui portent le code des
seuils existants (toutes les portes du jeu sont sur du `1`), sans masque `nav`, libres, et
prises en anneau autour du parvis de Notre-Dame — le cœur de ville. C'est une PROPOSITION
géométrique : la grille de Lutèce est une vraie carte dessinée, une case `1` peut tomber en
lisière de forêt. À revoir dans le mode « Lieux » de l'éditeur de carte.
"""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
DOSSIER_IMAGES = os.path.join(RACINE, "templates", "resources", "towns")
SORTIE = os.path.join(DOSSIER_JSONS, "magasins_superieurs_a_importer.json")
SORTIE_TXT = os.path.join(DOSSIER_JSONS, "magasins_superieurs_images_manquantes.txt")

CITE = "lieu:lutecia"
PARVIS = (50, 29)      # la porte de Notre-Dame : le centre autour duquel on ouvre les enseignes
CODE_SEUIL = 1         # code de case des 85 portes d'Auxerre et de celle de Notre-Dame
ECART_MIN = 2          # cases entre deux seuils, pour ne pas empiler les enseignes


# ── Les enseignes ────────────────────────────────────────────────────────────────
# grande catégorie → (slug du lieu, enseigne, image). L'image est un nom de fichier VOULU :
# s'il manque, le lieu est écrit quand même (il est jouable, seule l'illustration manque) et
# listé dans le .txt — même convention que dev/gen_magasins_auxerre.py.
ENSEIGNES = {
	"grande_apothicairerie":             ("la_grande_officine_de_lutecia",   "La Grande Officine",                "apothicairerie_europe03.png"),
	"institut_medico_alchimique":        ("l_institut_des_humeurs",          "L'Institut des Humeurs",            "cabinet_alchimie_europe02.png"),
	"grand_arsenal":                     ("l_arsenal_de_lutecia",            "L'Arsenal de Lutèce",               "armurerie_europe05.png"),
	"grande_manufacture_du_cuir":        ("la_grande_megisserie",            "La Grande Mégisserie",              "tannerie_europe04.png"),
	"grande_manufacture_textile":        ("la_manufacture_des_toiles",       "La Manufacture des Toiles",         "tissage_europe03.png"),
	"grandes_halles_alimentaires":       ("les_grandes_halles",              "Les Grandes Halles",                "epicerie_europe06.png"),
	"grande_orfevrerie":                 ("l_orfevrerie_royale",             "L'Orfèvrerie Royale",               "bijouterie_europe04.png"),
	"manufacture_des_instruments":       ("la_manufacture_des_instruments",  "La Manufacture des Instruments",    "lutherie_europe02.png"),
	"grande_maison_des_arts":            ("la_maison_des_arts",              "La Maison des Arts",                "atelier_d_artisan_europe04.png"),
	"manufacture_des_savons_et_parfums": ("la_maison_des_parfums",           "La Maison des Parfums",             "savonnerie_europe01.png"),
	"grand_scriptorium":                 ("le_grand_scriptorium_de_lutecia", "Le Grand Scriptorium",              "scriptorium_europe03.png"),
	"grand_laboratoire_alchimique":      ("le_grand_athanor",                "Le Grand Athanor",                  "cabinet_alchimie_europe01.png"),
	"institut_de_thanaturgie":           ("l_institut_de_thanaturgie",       "L'Institut de Thanaturgie",         "necromancie_europe01.png"),
	"cabinet_des_specimens":             ("le_cabinet_des_specimens",        "Le Cabinet des Spécimens",          "taxidermie_europe02.png"),
	"grande_corderie":                   ("la_grande_corderie_de_lutecia",   "La Grande Corderie",                "corderie_europe02.png"),
	"grand_atelier_d_empennage":         ("le_grand_atelier_d_empennage",    "Le Grand Atelier d'Empennage",      "archerie_europe02.png"),
	"grande_boulangerie":                ("le_grand_fournil_de_lutecia",     "Le Grand Fournil",                  "boulangerie_europe03.png"),
	"maison_des_conserves":              ("la_maison_des_conserves",         "La Maison des Conserves",           "salaison_europe02.png"),
}


# ── Les items et recettes exclusifs ──────────────────────────────────────────────
# grande catégorie → liste de créations. Une création :
#   (slug, nom, icon, rareté, catégorie, sous_catégorie, poids, slots, extras, description,
#    matières, quantité_produite)
# `slug` devient `item:<slug>` ET l'`objet_final` de la recette (cf. `objet_final_item_id`).
# `matières` = [(clé, quantité)] — clé = sous-catégorie OU id d'item, comme en base.
# `extras` = les champs de jeu du doc item (bonus_pa, bonus, effets, restriction, portee…),
# recopiés tels quels : ce fichier ne connaît AUCUNE règle de combat.
CREATIONS = {

	"grande_apothicairerie": [
		("Elixir_des_simples_royaux", "Élixir des simples royaux", "🧪", "rare",
		 "consommable", "", 0.2, [], {"effets": {"pv": 40, "pm": 20}},
		 "Trois tisanes réduites ensemble sur un feu de jardin, liées au sirop de sève. "
		 "Aucune officine seule n'a jamais eu la mandragore assez fraîche pour la réussir.",
		 [("item:Tisane_concentration", 2), ("item:Racine_de_mandragore", 2),
		  ("item:sirop_de_seve", 1)], 1),
		("Baume_de_mandragore", "Baume de mandragore", "🌿", "rare",
		 "consommable", "", 0.3, [], {"effets": {"pv": 25, "duree": 6, "regen_pv": 3}},
		 "Racine pilée à même la toile du bandage, fleurie de souci. On la pose et l'on "
		 "cesse de saigner ; c'est tout ce qu'on lui demande.",
		 [("item:Bandages", 2), ("item:Racine_de_mandragore", 1), ("item:Fleur_de_souci", 2)], 1),
		("Panier_de_l_herboriste", "Panier de l'herboriste", "🧺", "peu_commun",
		 "consommable", "", 0.6, [],
		 {"effets": {"pv": 15, "pm": 15, "duree": 8, "regen_pv": 1}},
		 "Ce qu'un jardin et une officine mettent en commun pour une semaine de route : "
		 "deux tisanes, une compote et de quoi les faire durer.",
		 [("item:Tisane_du_marcheur", 1), ("item:Compote_fortifiante", 1),
		  ("item:Feves_de_carreau", 2)], 1),
	],

	"institut_medico_alchimique": [
		("Serum_de_l_institut", "Sérum de l'Institut", "⚗️", "rare",
		 "consommable", "", 0.2, [], {"effets": {"pv": 35, "pm": 35}},
		 "Un réactif magique stabilisé par deux tisanes — la seule manière connue de "
		 "rendre l'alchimie buvable sans y laisser l'estomac.",
		 [("item:reactif_magique", 1), ("item:Tisane_concentration", 2),
		  ("item:sirop_de_seve", 1)], 1),
		("Onguent_alchimique", "Onguent alchimique", "🫙", "rare",
		 "consommable", "", 0.3, [], {"effets": {"pv": 20, "duree": 8, "regen_pv": 4}},
		 "La poudre mord d'abord, puis la plaie se referme plus vite qu'elle ne devrait. "
		 "Le sel noir empêche l'onguent de tourner.",
		 [("item:Bandages", 2), ("item:poudre_alchimique", 1), ("item:Sel_noir", 1)], 1),
		("Fiole_de_sang_fige", "Fiole de sang figé", "🩸", "rare",
		 "composant", "", 0.1, [], {},
		 "Du sang de démon repris au catalyseur et tenu en suspension. Les praticiens de "
		 "l'Institut refusent d'expliquer à quoi cela sert.",
		 [("item:Sang_demon_seche", 1), ("item:Bandages", 1), ("item:catalyseur_magique", 1)], 1),
	],

	"grand_arsenal": [
		("Harnois_du_grand_arsenal", "Harnois du Grand Arsenal", "🛡️", "rare",
		 "armure", "", 12.0, ["torse"],
		 {"bonus_pa": 22, "bonus_malus_depl": -2, "restriction": {"F": 30}},
		 "Plates d'acier montées sur un harnais de bourrelier et doublées de cuir. Aucune "
		 "forge seule ne sait tailler la sanglerie ; aucun bourrelier ne sait battre l'acier.",
		 [("item:harnais", 1), ("acier", 4), ("item:armure_de_cuir", 1)], 1),
		("Baudrier_de_l_arsenal", "Baudrier de l'Arsenal", "🎽", "rare",
		 "armure", "", 1.2, ["ceinture"],
		 {"bonus_pa": 3, "bonus": {"Ag": 2}, "bonus_initiative": 2},
		 "Sanglé haut, ferré court : tout tombe sous la main sans qu'on ait à chercher.",
		 [("item:harnais", 1), ("peaux", 2), ("fer", 1)], 1),
		("Fagot_de_traits_lestes", "Fagot de traits lestés", "🎯", "peu_commun",
		 "arme", "", 1.5, ["main_droite"],
		 {"tags": ["jet"], "portee": 6, "bonus_cd": 3, "bonus_degats": 3,
		  "bonus_degats_dice": 6, "restriction": {"Ag": 22}},
		 "Des plombées liées en fagot sur une sangle d'épaule. On en tire six sans reprendre "
		 "son souffle.",
		 [("item:Plumbata", 2), ("plomb", 2), ("item:harnais", 1)], 1),
	],

	"grande_manufacture_du_cuir": [
		("Equipage_de_marche_ferre", "Équipage de marche ferré", "👢", "rare",
		 "armure", "", 1.6, ["pieds"], {"bonus_pa": 4, "bonus": {"Ag": 2}},
		 "Bottes de voyage reprises sur une sanglerie de bourrelier : la semelle tient la "
		 "route bien après que le pied a renoncé.",
		 [("item:Bottes_de_voyage", 1), ("item:harnais", 1), ("peaux", 2)], 1),
		("Ceinturon_de_maitre_sellier", "Ceinturon de maître sellier", "🧷", "rare",
		 "armure", "", 1.0, ["ceinture"], {"bonus_pa": 2, "bonus": {"F": 2}},
		 "Trois épaisseurs poissées, cousues au fil de sellier. On y pend une journée de "
		 "marche sans que la boucle bouge d'un cran.",
		 [("item:ceinture", 1), ("item:harnais", 1), ("poix", 1)], 1),
		("Gants_de_courroyeur", "Gants de courroyeur", "🧤", "peu_commun",
		 "armure", "", 0.4, ["mains"], {"bonus_pa": 2, "bonus": {"Ag": 1}},
		 "Cuir corroyé deux fois, paume renforcée d'une chute de sanglerie.",
		 [("item:gants", 1), ("item:harnais", 1), ("peaux", 1)], 1),
	],

	"grande_manufacture_textile": [
		("Manteau_de_cour_double", "Manteau de cour doublé", "🧥", "rare",
		 "armure", "", 2.5, ["torse"], {"bonus_pa": 5, "bonus": {"Cha": 3}},
		 "Feutre lourd doublé d'une parure de plumassier. On ne le porte pas pour avoir "
		 "chaud.",
		 [("item:feutre", 2), ("item:parure", 1), ("peaux", 1)], 1),
		("Chaperon_emplume", "Chaperon emplumé", "🎩", "rare",
		 "armure", "", 0.6, ["tete"], {"bonus_pa": 2, "bonus": {"Cha": 4}},
		 "La coiffe du plumassier montée sur un chaperon de feutre : deux ateliers, un "
		 "seul chapeau, et l'on vous laisse entrer.",
		 [("item:feutre", 1), ("item:Coiffe_plumes", 1)], 1),
		("Necessaire_de_toilette", "Nécessaire de toilette", "🪮", "peu_commun",
		 "outil", "", 0.8, [], {},
		 "Brosse, pinceau et étui de feutre. Rien d'héroïque, mais on vous adresse la "
		 "parole autrement.",
		 [("item:brosse", 1), ("item:pinceau", 1), ("item:feutre", 1)], 1),
	],

	"grandes_halles_alimentaires": [
		("Salaison_de_grand_festin", "Salaison de grand festin", "🍖", "rare",
		 "consommable", "", 1.2, [],
		 {"effets": {"pv": 45, "duree": 10, "buffs": {"F": 6}}},
		 "Jambon de montagne et viande fumée, resalés ensemble. Le saloir et le haloir ne "
		 "sont jamais sous le même toit — sauf ici.",
		 [("item:jambon_de_montagne", 1), ("item:viande_fumee", 2), ("item:Sel", 2)], 1),
		("Conserve_de_campagne", "Conserve de campagne", "🥫", "peu_commun",
		 "consommable", "", 0.8, [],
		 {"effets": {"pv": 25, "duree": 8, "buffs": {"R": 4}}},
		 "Un repas de cuisine noyé dans la saumure du saloir : il tient trois semaines et "
		 "n'a pas mauvais goût, ce qui est déjà beaucoup.",
		 [("item:lard_sale", 1), ("item:saumure", 1), ("item:repas_cuisine", 1)], 1),
		("Terrine_des_halles", "Terrine des Halles", "🥧", "rare",
		 "consommable", "", 0.9, [],
		 {"effets": {"pv": 30, "pm": 10, "duree": 6, "buffs": {"V": 3}}},
		 "Le foie va au billot, la terrine au fourneau : deux étals qui ne se parlent que "
		 "sous la halle.",
		 [("item:foie", 2), ("item:graisse", 1), ("item:plat_raffine", 1)], 1),
	],

	"grande_orfevrerie": [
		("Diademe_d_orfevre", "Diadème d'orfèvre", "👑", "rare",
		 "armure", "", 0.3, ["tete"],
		 {"bonus_pa": 1, "bonus": {"Cha": 6, "Int": 2}, "restriction": {"Cha": 35}},
		 "Un cercle de branchages tourné par le tabletier, repris en monture et serti de "
		 "gemmes. Séparés, les deux ateliers font deux objets ordinaires.",
		 [("item:diademe", 1), ("gemmes", 2), ("item:Couronne_branchages", 1)], 1),
		("Sceptre_d_apparat", "Sceptre d'apparat", "🔱", "rare",
		 "arme", "", 2.0, ["main_droite"],
		 {"tags": ["cac"], "portee": 1, "bonus_degats_dice": 4, "bonus": {"Cha": 5},
		  "restriction": {"Cha": 30}},
		 "Un manche de tabletterie, un talisman en tête, du métal précieux entre les deux. "
		 "On ne s'en sert pas pour frapper, mais rien n'interdit d'essayer.",
		 [("item:manche", 1), ("metaux_precieux", 2), ("item:talisman", 1)], 1),
		("Ecrin_de_tabletier", "Écrin de tabletier", "🧰", "peu_commun",
		 "outil", "", 1.0, [], {},
		 "Os plaqué sur une âme de bois tournée, charnières de perle, un bijou "
		 "d'échantillon dedans pour la montre.",
		 [("item:manche", 1), ("item:bijou", 1), ("perles", 1)], 1),
	],

	"manufacture_des_instruments": [
		("Vielle_de_maitre", "Vielle de maître", "🎻", "rare",
		 "arme", "instrument", 4.5, ["main_droite", "main_gauche"],
		 {"tags": ["cac"], "portee": 1, "bonus_degats_dice": 4, "bonus": {"Cha": 9},
		  "restriction": {"Cha": 45}, "deux_mains": True},
		 "Table d'harmonie de luthier, cordes de boyaudier. Le luthier ne file pas le "
		 "boyau, le boyaudier ne sait pas régler une table : il fallait les deux.",
		 [("item:Table_d_harmonie", 1), ("item:fil_de_boyau", 3), ("peaux", 1)], 1),
		("Tambour_de_parade", "Tambour de parade", "🥁", "rare",
		 "arme", "instrument", 3.0, ["main_droite", "main_gauche"],
		 {"tags": ["cac"], "portee": 1, "bonus_degats_dice": 3,
		  "bonus": {"Cha": 6, "Vol": 2}, "restriction": {"Cha": 35}, "deux_mains": True},
		 "Peau tendue sur baudruche, cerclée de plumes. On l'entend d'un bout à l'autre "
		 "de la colonne.",
		 [("item:Tambourin", 1), ("item:baudruche", 2), ("item:Coiffe_plumes", 1)], 1),
		("Cordes_de_concert", "Cordes de concert", "🎼", "peu_commun",
		 "composant", "", 0.2, [], {},
		 "Boyau filé fin, poissé, monté par jeu complet. Elles tiennent l'accord une "
		 "saison entière.",
		 [("item:fil_de_boyau", 2), ("item:cordes_d_instrument", 1), ("poix", 1)], 1),
	],

	"grande_maison_des_arts": [
		("Reliquaire_ouvrage", "Reliquaire ouvragé", "🏺", "rare",
		 "outil", "", 1.5, [], {},
		 "Poudre d'os liée en pâte, montée sur métal précieux et sertie. Trois ateliers "
		 "y ont mis la main.",
		 [("item:Poudre_os", 1), ("metaux_precieux", 2), ("gemmes", 1)], 1),
		("Baguette_ouvragee", "Baguette ouvragée", "🪄", "rare",
		 "arme", "", 0.8, ["main_droite"],
		 {"tags": ["cac"], "portee": 1, "bonus_degats_dice": 2, "bonus": {"Int": 5},
		  "restriction": {"Int": 35}},
		 "Houx tourné par le tabletier, virole et gemme posées par l'orfèvre.",
		 [("item:Baguette_houx", 1), ("metaux_precieux", 1), ("gemmes", 1)], 1),
		("Parure_d_atelier", "Parure d'atelier", "💍", "peu_commun",
		 "armure", "", 0.2, ["cou"], {"bonus_pv": 5, "bonus": {"Cha": 3}},
		 "Pendentif rehaussé de perles sur un fond d'os poli — la pièce que chaque "
		 "compagnon de la maison présente à sa maîtrise.",
		 [("item:pendentif", 1), ("item:Poudre_os", 1), ("perles", 1)], 1),
	],

	"manufacture_des_savons_et_parfums": [
		("Parfum_de_cour", "Parfum de cour", "🌸", "rare",
		 "consommable", "", 0.1, [], {"effets": {"duree": 12, "buffs": {"Cha": 8}}},
		 "Un solide de parfumeur fondu à la cire du cirier, repris à l'huile. Il tient "
		 "une audience entière.",
		 [("item:Parfum_solide", 1), ("item:Huile_parfumee", 1), ("item:Cierge", 1)], 1),
		("Savon_de_l_apothicaire", "Savon de l'apothicaire", "🧼", "rare",
		 "consommable", "", 0.3, [],
		 {"effets": {"pv": 15, "duree": 6, "regen_pv": 2}},
		 "Savon d'huile chargé de charpie et d'infusion : on s'en lave les mains avant de "
		 "recoudre, et la plaie s'en souvient.",
		 [("item:Savon_d_huile", 1), ("item:Bandages", 1), ("item:Tisane_concentration", 1)], 1),
		("Bougie_de_veille", "Bougie de veille", "🕯️", "peu_commun",
		 "consommable", "", 0.2, [],
		 {"effets": {"duree": 14, "regen_pv": 2, "regen_pm": 2}},
		 "Cierge repris à l'huile parfumée et aux simples. Elle brûle toute la nuit et "
		 "l'on se réveille reposé, ce qui n'est pas rien.",
		 [("item:Cierge", 1), ("item:Huile_parfumee", 1), ("item:Herbes_medicinales", 1)], 1),
	],

	"grand_scriptorium": [
		("Registre_scelle", "Registre scellé", "📜", "rare",
		 "document", "", 0.5, [], {},
		 "Cahier cousu au fil poissé du cirier, refermé sur cire à cacheter et frappé au "
		 "sceau. Ce qui est dedans ne se discute plus.",
		 [("item:Papier", 3), ("item:Fil_poisse", 2), ("item:Sceau_ordre", 1)], 1),
		("Ecritoire_de_voyage", "Écritoire de voyage", "🖋️", "rare",
		 "outil", "", 1.2, [], {},
		 "Tablette de cire pour le brouillon, papier pour la mise au net, chandelle pour "
		 "la nuit. Le copiste n'a plus d'excuse.",
		 [("item:Papier", 2), ("item:Tablette_de_cire", 1), ("item:Cierge", 1)], 1),
		("Chandelle_d_etude", "Chandelle d'étude", "🕯️", "peu_commun",
		 "consommable", "", 0.2, [],
		 {"effets": {"duree": 10, "pm": 15, "regen_pm": 2}},
		 "Mèche longue et fumée d'aromates : on lit huit heures d'affilée sans que l'œil "
		 "pleure.",
		 [("item:Cierge", 1), ("item:Papier", 1), ("item:Herbes_aromatiques", 1)], 1),
	],

	"grand_laboratoire_alchimique": [
		("Athanor_portatif", "Athanor portatif", "⚗️", "rare",
		 "outil", "", 2.0, [], {},
		 "Un cristal de canalisation monté en creuset sur armature d'orfèvre. Il faut un "
		 "alchimiste pour le charger et un bijoutier pour qu'il tienne.",
		 [("item:Cristal_canalisation", 1), ("metaux_precieux", 2),
		  ("item:catalyseur_magique", 1)], 1),
		("Anneau_de_transmutation", "Anneau de transmutation", "💍", "rare",
		 "armure", "", 0.1, ["anneau_1", "anneau_2"],
		 {"bonus_pm": 12, "bonus": {"Int": 3}, "restriction": {"Int": 30}},
		 "Le chaton retient une goutte de réactif qui ne sèche jamais. On le remplit une "
		 "fois par lune.",
		 [("item:anneau", 1), ("item:reactif_magique", 1), ("gemmes", 1)], 1),
		("Philtre_du_grand_oeuvre", "Philtre du Grand Œuvre", "🧪", "rare",
		 "consommable", "", 0.2, [], {"effets": {"pv": 30, "pm": 40}},
		 "La poudre du laboratoire rendue potable par l'officine. Les deux maisons se "
		 "renvoient la paternité de la recette depuis trente ans.",
		 [("item:poudre_alchimique", 1), ("item:Tisane_concentration", 2),
		  ("item:Sel_noir", 1)], 1),
	],

	"institut_de_thanaturgie": [
		("Reliquaire_de_thanaturge", "Reliquaire de thanaturge", "💀", "rare",
		 "armure", "", 0.4, ["cou"],
		 {"bonus_pm": 15, "bonus": {"Vol": 4}, "restriction": {"Vol": 30}},
		 "Une relique tenue au sang figé dans une monture d'os. L'Institut soutient que "
		 "le procédé est purement chimique.",
		 [("item:relique", 1), ("item:Sang_demon_seche", 1), ("ossements", 2)], 1),
		("Sel_des_sepultures", "Sel des sépultures", "🧂", "rare",
		 "composant", "", 0.2, [], {},
		 "Sel noir recuit au soufre du laboratoire sur une poudre d'ossements. On en trace "
		 "des cercles dont on ne ressort pas toujours.",
		 [("item:Sel_noir", 2), ("item:Soufre", 1), ("ossements", 2)], 1),
		("Focus_ossuaire", "Focus ossuaire", "🔮", "rare",
		 "outil", "", 0.8, [], {},
		 "Focus de nécromant remonté sur cristal de laboratoire. Le canal est plus net, "
		 "et ce qui répond l'est aussi.",
		 [("item:focus_magique", 1), ("item:Cristal_canalisation", 1), ("ossements", 2)], 1),
	],

	"cabinet_des_specimens": [
		("Specimen_monte", "Spécimen monté", "🦌", "rare",
		 "outil", "", 3.0, [], {},
		 "Trophée remonté sur armature d'os et retendu de peau. Le taxidermiste prépare, "
		 "le tabletier arme : l'un sans l'autre, la bête s'affaisse.",
		 [("item:trophee", 1), ("ossements", 2), ("peaux", 2)], 1),
		("Coiffe_de_specimen", "Coiffe de spécimen", "🪶", "rare",
		 "armure", "", 0.5, ["tete"],
		 {"bonus_pa": 1, "bonus": {"Cha": 4, "Vol": 2}},
		 "Les plumes de la bête montées sur son propre crâne évidé. On la porte peu, on "
		 "s'en souvient longtemps.",
		 [("item:Coiffe_plumes", 1), ("item:trophee", 1), ("ossements", 1)], 1),
		("Vitrine_d_etude", "Vitrine d'étude", "🪟", "peu_commun",
		 "outil", "", 2.5, [], {},
		 "Montants de tabletterie, fond de peau tendue, un spécimen dedans. Le cabinet "
		 "n'en sort jamais deux identiques.",
		 [("item:trophee", 1), ("item:manche", 2), ("peaux", 1)], 1),
	],

	"grande_corderie": [
		("Cordage_de_marine", "Cordage de marine", "🪢", "peu_commun",
		 "outil", "", 2.5, [], {},
		 "Chanvre commis avec du fil de boyau et gainé de feutre : il ne cisaille pas la "
		 "main et ne rompt pas sous la pluie.",
		 [("item:corde", 2), ("item:fil_de_boyau", 2), ("item:feutre", 1)], 1),
		("Filet_de_capture", "Filet de capture", "🕸️", "rare",
		 "outil", "", 3.0, [], {},
		 "Maille lourde, plombs cousus dans le rembourrage. Ce qu'il prend ne se débat "
		 "pas deux fois.",
		 [("item:filet", 1), ("item:corde", 2), ("item:rembourrage", 1)], 1),
		("Sangle_rembourree", "Sangle rembourrée", "🎒", "peu_commun",
		 "armure", "", 0.8, ["ceinture"], {"bonus_pa": 1, "bonus": {"F": 2}},
		 "Large, doublée, cousue au boyau. On porte le double sans y penser le lendemain.",
		 [("item:corde", 1), ("item:rembourrage", 2), ("item:fil_de_boyau", 1)], 1),
	],

	"grand_atelier_d_empennage": [
		("Empennage_de_maitre", "Empennage de maître", "🪶", "rare",
		 "composant", "", 0.1, [], {},
		 "Plumes triées à la parure, refendues et collées trois par trois. La flèche part "
		 "droite même quand la main tremble.",
		 [("item:empennage_de_fleches", 1), ("item:parure", 1), ("item:manche", 1)], 1),
		("Arc_du_grand_atelier", "Arc du Grand Atelier", "🏹", "rare",
		 "arme", "", 2.2, ["main_droite", "main_gauche"],
		 {"tags": ["distance"], "portee": 9, "bonus_cd": 5, "bonus_degats": 4,
		  "bonus_degats_dice": 8, "restriction": {"Ag": 32}, "deux_mains": True},
		 "Arc long remonté par l'empenneur, corde et parure d'atelier. Le flèchier seul "
		 "n'aurait jamais eu les plumes ; le plumassier, jamais le bois.",
		 [("item:Arc_long", 1), ("item:cordes_d_arc", 1), ("item:parure", 1)], 1),
		("Carquois_emplume", "Carquois emplumé", "🎯", "peu_commun",
		 "armure", "", 0.9, ["ceinture"],
		 {"bonus_pa": 1, "bonus": {"Ag": 2}, "bonus_initiative": 1},
		 "Cuir souple, col évasé, plumes en couronne. On y puise sans regarder.",
		 [("item:empennage_de_fleches", 2), ("peaux", 2), ("item:parure", 1)], 1),
	],

	"grande_boulangerie": [
		("Tourte_de_banquet", "Tourte de banquet", "🥧", "rare",
		 "consommable", "", 1.0, [],
		 {"effets": {"pv": 35, "duree": 8, "buffs": {"R": 5}}},
		 "Pâte du fournil, garniture du fourneau. Le four banal ne cuit pas ce qu'il n'a "
		 "pas préparé — sauf ici.",
		 [("item:farine_de_froment", 2), ("item:plat_raffine", 1),
		  ("item:motte_de_beurre", 1)], 1),
		("Pain_de_voyage_renforce", "Pain de voyage renforcé", "🥖", "peu_commun",
		 "consommable", "", 0.8, [],
		 {"effets": {"pv": 22, "duree": 10, "buffs": {"V": 3}}},
		 "Biscuit deux fois cuit, relevé au miel et à ce que la cuisine avait de reste. "
		 "Il ne moisit pas, il durcit.",
		 [("item:biscuits_voyage", 2), ("item:repas_cuisine", 1),
		  ("item:miel_de_bruyere", 1)], 1),
		("Fouace_des_maitres", "Fouace des maîtres", "🍞", "rare",
		 "consommable", "", 0.7, [],
		 {"effets": {"pv": 28, "pm": 12, "duree": 6, "buffs": {"Cha": 3}}},
		 "Fouace au miel enrichie d'un mets rare et d'œufs de ferme. On la sert entière "
		 "ou pas du tout.",
		 [("item:fouace_miel", 1), ("item:mets_rare", 1), ("item:oeufs_de_ferme", 2)], 1),
	],

	"maison_des_conserves": [
		("Panier_de_provisions", "Panier de provisions", "🧺", "rare",
		 "consommable", "", 2.0, [],
		 {"effets": {"pv": 50, "duree": 12, "buffs": {"F": 4, "R": 4}}},
		 "Jambon, pain de seigle, viande fumée : trois métiers dans une même corbeille, "
		 "et de quoi tenir une semaine de route.",
		 [("item:jambon_de_montagne", 1), ("item:pain_seigle", 2),
		  ("item:viande_fumee", 1)], 1),
		("Tourte_a_la_viande", "Tourte à la viande", "🥟", "peu_commun",
		 "consommable", "", 0.9, [],
		 {"effets": {"pv": 26, "duree": 8, "buffs": {"F": 3}}},
		 "Le billot fournit, le fournil enferme, le saloir conserve. Elle voyage mieux "
		 "que celui qui la porte.",
		 [("item:viande", 2), ("item:farine_de_seigle", 1), ("item:lard_sale", 1)], 1),
		("Baril_de_saumure", "Baril de saumure", "🛢️", "peu_commun",
		 "outil", "", 4.0, [], {},
		 "Saumure fortement salée, boyaux tendus en joint. Ce qu'on y met en sort dans "
		 "l'état où on l'y a mis.",
		 [("item:saumure", 2), ("item:Sel", 2), ("item:boyaux", 1)], 1),
	],
}


# ── Lecture du dump ──────────────────────────────────────────────────────────────

def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def chemin_dump() -> str:
	"""Le dump passé en argv, sinon le plus récent de jsons/."""
	if len(sys.argv) > 1:
		return sys.argv[1] if os.path.isabs(sys.argv[1]) else os.path.join(RACINE, sys.argv[1])
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun jsons/telluris-dump-*.json — exporter depuis /admin.")
	return dumps[-1]


def brancher_moteur(docs: list):
	"""Rebranche `db.config` sur le dump AVANT d'importer `utils.marche` (même procédé que
	dev/audit_economy.py) : les besoins/produits/feuilles sortent du moteur du jeu, pas d'une
	réimplémentation, et la fusion des catégories est celle qui tournera en jeu.

	⚠️ L'ordre est la seule chose qui compte : `utils/marche.py` fait `from db.config import
	get_doc, …`, les noms sont liés à l'import."""
	os.environ["COUCHDB_HOST"] = "127.0.0.1"
	os.environ["COUCHDB_PORT"] = "1"          # coupe court à toute connexion CouchDB
	sys.path.insert(0, RACINE)

	index = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}

	import db.config as dbc
	dbc.get_doc = lambda doc_id: dict(index[doc_id]) if doc_id in index else None
	dbc.find_docs = lambda selecteur, **kw: [
		dict(d) for d in docs
		if isinstance(d, dict) and all(d.get(k) == v for k, v in selecteur.items())
	]
	dbc.save_doc = lambda doc: doc            # génération en lecture seule
	dbc.delete_doc = lambda doc: None
	dbc.server = None
	dbc.db = None

	from models import character_stats
	from utils import marche
	character_stats.load_world_variables()    # sans DB : garde les défauts du code
	marche.reset_prix_cache()
	return character_stats, marche, index


# ── Garde-fous ───────────────────────────────────────────────────────────────────

def _metier_unique(marche, grande: str, cles: list) -> str | None:
	"""Nom d'un métier réuni capable de fournir À LUI SEUL toutes ces clés, s'il en existe
	un — auquel cas la recette n'a rien d'exclusif et n'a pas sa place ici."""
	mm = marche._get_marche_map()
	for metier in marche.categories_incluses(grande)[1:]:
		couvert = mm["besoins"].get(metier, set()) | mm["produits"].get(metier, set())
		if all(cle in couvert for cle in cles):
			return metier
	return None


def _atteignables(marche, categorie: str) -> set:
	"""Clés disponibles sur place SANS le joueur : point fixe amorcé par les seules feuilles
	d'approvisionnement, comme dev/audit_economy.py. Sert au rapport, pas au refus : plusieurs
	métiers de base (boucherie, corderie, tissage) dépendent DÉJÀ du joueur, et la fusion
	n'avait pas à changer cela.

	⚠️ On n'amorce qu'avec les feuilles **effectivement livrées** — `approvisionner` saute
	celles à débit nul (`APPRO_DEBIT["herbe"] = 0` : les simples se récoltent, ils ne se
	livrent pas). Compter toutes les feuilles rendait le rapport optimiste : trois recettes
	d'apothicairerie s'annonçaient autonomes alors qu'aucune tisane n'arrive jamais seule."""
	dispo = {cle for cle in marche.appro_leaves_categorie(categorie)
			 if marche._appro_debit_pour(cle) > 0}
	recettes = marche.lieu_recettes(categorie)
	bouge = True
	while bouge:
		bouge = False
		for r in recettes:
			entrees = [cle for (cle, _q) in marche.recette_matieres(r)]
			if not entrees or not all(c in dispo for c in entrees):
				continue
			for cle in (marche.objet_final_item_id(r.get("objet_final", "")),
						r.get("objet_final")):
				if cle and cle not in dispo:
					dispo.add(cle)
					bouge = True
	return dispo


# ── Portes ───────────────────────────────────────────────────────────────────────

def choisir_portes(cite_doc: dict, occupees: set, combien: int) -> list:
	"""`combien` cases de seuil sur la grille de la cité, prises en anneau autour du PARVIS.

	Retenues : code de case == CODE_SEUIL, aucun masque `nav` (la case doit être ouverte dans
	toutes les directions), pas déjà porteuse d'une porte, et à ECART_MIN d'une case déjà
	choisie. Tri par distance de Tchebychev au parvis → les enseignes s'ouvrent du centre
	vers l'extérieur, dans un ordre reproductible."""
	cells = cite_doc.get("cells") or []
	nav = cite_doc.get("nav") or {}
	hauteur = len(cells)
	largeur = len(cells[0]) if hauteur else 0

	candidates = []
	for y in range(hauteur):
		for x in range(largeur):
			if cells[y][x] != CODE_SEUIL or "%d,%d" % (x, y) in nav or (x, y) in occupees:
				continue
			candidates.append((max(abs(x - PARVIS[0]), abs(y - PARVIS[1])), x, y))
	candidates.sort()

	retenues = []
	for _d, x, y in candidates:
		if len(retenues) >= combien:
			break
		if all(max(abs(x - px), abs(y - py)) >= ECART_MIN for (px, py) in retenues):
			retenues.append((x, y))
	return retenues


# ── Génération ───────────────────────────────────────────────────────────────────

def main() -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	source = chemin_dump()
	docs = charger(source)
	character_stats, marche, index = brancher_moteur(docs)

	grandes = list(character_stats.LIEU_CATEGORIES_FUSION)
	erreurs = []

	# --- Garde-fou 0 : la table du code et le catalogue de ce script se répondent -----
	for grande in grandes:
		if grande not in ENSEIGNES:
			erreurs.append("%s : aucune enseigne au catalogue" % grande)
		if grande not in CREATIONS:
			erreurs.append("%s : aucune création au catalogue" % grande)
	for grande in list(ENSEIGNES) + list(CREATIONS):
		if grande not in character_stats.LIEU_CATEGORIES_FUSION:
			erreurs.append("%s : au catalogue mais absente de LIEU_CATEGORIES_FUSION" % grande)

	# --- Les items et leurs recettes -------------------------------------------------
	sortie, rapport_recettes = [], []
	slugs_crees = set()
	for grande in grandes:
		atteignables = _atteignables(marche, grande)
		for (slug, nom, icon, rarete, categorie, sous_cat, poids, slots, extras, desc,
			 matieres, quantite) in CREATIONS.get(grande, []):
			item_id = "item:" + slug
			if item_id in index:
				erreurs.append("%s : collision d'_id avec un doc du dump" % item_id)
			if slug in slugs_crees:
				erreurs.append("%s : créé deux fois par ce script" % item_id)
			slugs_crees.add(slug)

			item = {
				"_id": item_id, "type": "item", "nom": nom, "description": desc,
				"icon": icon, "rarete": rarete, "categorie": categorie,
				"sous_categorie": sous_cat, "slots": list(slots), "tags": [],
				"poids": poids,
			}
			item.update(extras)          # bonus_pa, bonus, effets, restriction, portee…
			sortie.append(item)

			recette_id = "recette:%s_%s" % (grande, slug.lower())
			if recette_id in index:
				erreurs.append("%s : collision d'_id avec un doc du dump" % recette_id)
			sortie.append({
				"_id": recette_id, "type": "recette",
				"lieu_categorie": grande,
				"objet_final": slug,
				"quantite_produite": quantite,
				"matieres_premieres": [{"item": cle, "quantite": q} if cle.startswith("item:")
									   else {"sous_categorie": cle, "quantite": q}
									   for (cle, q) in matieres],
			})

			# Garde-fou 1 : chaque clé matière est connue de la grande maison (un intrant
			# qu'elle ne consomme ni ne produit ne lui arriverait JAMAIS en stock).
			connues = set(marche.besoins_categorie(grande)) | marche.produits_categorie(grande)
			inconnues = [c for c in (cle for (cle, _q) in matieres) if c not in connues]
			if inconnues:
				erreurs.append("%s : intrant(s) hors de portée de %s → %s"
							   % (recette_id, grande, ", ".join(inconnues)))
			# Garde-fou 2 : la recette est bien CROISÉE (aucun métier réuni ne la ferait seul).
			seul = _metier_unique(marche, grande, [cle for (cle, _q) in matieres])
			if seul:
				erreurs.append("%s : « %s » fournirait tout à lui seul — recette non exclusive"
							   % (recette_id, seul))
			# Garde-fou 3 : l'objet final doit avoir un doc item (sinon ligne de rayon
			# INVISIBLE — `resolve_stock_vente` saute silencieusement).
			if marche.objet_final_item_id(slug) != item_id:
				erreurs.append("%s : objet_final « %s » ne résout pas vers %s"
							   % (recette_id, slug, item_id))

			manquantes = [c for (c, _q) in matieres if c not in atteignables]
			rapport_recettes.append((grande, slug, manquantes))

	# --- La cité : lui poser sa `categorie` ------------------------------------------
	# Doc RELU du dump, un seul champ ajouté (idiome des générateurs) : `lieu:lutecia` porte
	# `categorie: ""`, ce qui la ferait manquer le regroupement par ville de l'onglet 🤝
	# (`marche.relations_lieux_payload` : est_ville = categorie == "ville").
	cite = index.get(CITE)
	if not cite:
		erreurs.append("%s introuvable dans %s" % (CITE, os.path.basename(source)))
	else:
		cite = dict(cite)
		cite["categorie"] = "ville"
		sortie.append(cite)

	# --- Enseignes, portes et tenanciers ---------------------------------------------
	occupees = {tuple(n["pos"]) for d in docs
				if isinstance(d, dict) and d.get("type") == "connection"
				for n in d.get("nodes", [])
				if n.get("lieu") == CITE and isinstance(n.get("pos"), list)}
	portes = choisir_portes(cite or {}, occupees, len(grandes)) if cite else []
	if len(portes) < len(grandes):
		erreurs.append("seulement %d case(s) de seuil libre(s) pour %d enseignes"
					   % (len(portes), len(grandes)))

	images_presentes = set(os.listdir(DOSSIER_IMAGES)) if os.path.isdir(DOSSIER_IMAGES) else set()
	manquantes_img, rapport_lieux = [], []

	from dev.gen_marchands import METIERS, NOEUDS_ESCORTE, NOEUDS_TRANSPORT, dialogue, portrait_de

	for i, grande in enumerate(grandes):
		if grande not in ENSEIGNES or i >= len(portes):
			continue
		slug, label, image = ENSEIGNES[grande]
		lieu_id = "lieu:" + slug
		lien_id = "link:%s_to_lutecia" % slug
		for doc_id in (lieu_id, lien_id):
			if doc_id in index:
				erreurs.append("%s : collision d'_id avec un doc du dump" % doc_id)
		if image not in images_presentes:
			manquantes_img.append((image, grande, label))

		lieu = {
			"_id": lieu_id, "type": "lieu", "label": label, "image": image,
			"categorie": grande,
			"pnj": [{"character": "pnj:marchand_" + grande}],
			"lieu_parent": CITE,
			"stock_matieres": {}, "stock_vente": [],
			# Cible de rayon des pièces exclusives : sans elle, `STOCK_CIBLE_DEFAUT` (25)
			# ferait empiler 25 exemplaires d'une pièce rare avant le moindre écoulement.
			"stock_cible": {"item": {"item:" + c[0]: 3 for c in CREATIONS.get(grande, [])}},
		}
		# ⚠️ Le grand scriptorium doit rester un scriptorium au sens de
		# `utils/scriptorium.lieu_est_scriptorium` — qui teste `categorie == "scriptorium"`
		# OU le tag. Le tag est l'échappatoire prévue par ce module : aucun code à toucher.
		if "scriptorium" in marche.categories_incluses(grande)[1:]:
			lieu["tags"] = ["scriptorium"]
		sortie.append(lieu)

		x, y = portes[i]
		sortie.append({
			"_id": lien_id, "type": "connection",
			"nodes": [{"lieu": CITE, "pos": [x, y]}, {"lieu": lieu_id, "pos": [0, 0]}],
			"metadata": {"type": grande, "status": "ouvert"},
		})

		# Tenancier générique : `utils/transport.entree_marchand` dérive `pnj:marchand_<cat>`
		# de la catégorie du lieu. Doc rigoureusement identique à celui que produira
		# `dev/gen_marchands.py` une fois les recettes en base (mêmes METIERS, même portrait
		# indexé sur le nom de catégorie) — les deux générateurs restent interchangeables.
		nom, metier, ambiance = METIERS[grande]
		sortie.append({
			"_id": "pnj:marchand_" + grande, "type": "pnj",
			"nom": nom, "race": "humain", "vocation": "marchand",
			"portrait": portrait_de(grande),
			"services": {
				"transport": {"noeuds": dict(NOEUDS_TRANSPORT)},
				"escorte": {"noeuds": dict(NOEUDS_ESCORTE)},
			},
			"dialogue": dialogue(metier, ambiance),
		})
		rapport_lieux.append((grande, label, x, y, image, image in images_presentes))

	# --- Refus ------------------------------------------------------------------------
	if erreurs:
		print("ABANDON — %d problème(s), aucun fichier écrit :" % len(erreurs))
		for e in erreurs:
			print("   ✗ %s" % e)
		return 1

	# --- Écriture ---------------------------------------------------------------------
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")

	with open(SORTIE_TXT, "w", encoding="utf-8") as f:
		f.write("Images de lieu à dessiner pour l'import magasins_superieurs_a_importer.json\n")
		f.write("Dossier cible : templates/resources/towns/\n")
		f.write("=" * 78 + "\n\n")
		if not manquantes_img:
			f.write("Aucune : toutes les images référencées existent déjà.\n")
		else:
			for img, cat, label in manquantes_img:
				f.write("\t%-40s  %s (%s)\n" % (img, label, cat))
			f.write("\nEn attendant, le lieu est jouable : seule l'illustration est absente.\n")

	# --- Récapitulatif ------------------------------------------------------------------
	print("Dump lu            : %s" % os.path.basename(source))
	print("Grandes maisons    : %d" % len(grandes))
	print("Docs écrits        : %d (%d items, %d recettes, %d lieux, %d portes, %d tenanciers, 1 cité)"
		  % (len(sortie), len(slugs_crees), len(slugs_crees), len(rapport_lieux),
			 len(rapport_lieux), len(rapport_lieux)))
	print("Images manquantes  : %d" % len(manquantes_img))
	print()
	print("ENSEIGNES ET SEUILS (à revoir dans le mode « Lieux » de l'éditeur de carte)")
	for grande, label, x, y, image, ok in rapport_lieux:
		print("   %-34s %-32s [%2d,%2d]  %s%s"
			  % (grande, label, x, y, image, "" if ok else "   ← IMAGE MANQUANTE"))
	print()
	print("RECETTES EXCLUSIVES — intrants que la maison ne produit pas seule")
	print("   (une maison dont les métiers de base dépendent déjà du joueur reste dans ce cas ;")
	print("    ce n'est pas un défaut du lot, c'est l'état de la chaîne en amont.)")
	for grande, slug, manquantes in rapport_recettes:
		etat = "autonome" if not manquantes else "à ravitailler : " + ", ".join(manquantes)
		print("   %-34s %-30s %s" % (grande, slug, etat))
	print()
	print("→ %s" % SORTIE)
	print("→ %s" % SORTIE_TXT)
	return 0


if __name__ == "__main__":
	sys.exit(main())

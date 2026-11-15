"""Zones d'influence PAR BIOME (docs/zones_biomes_proposition.md, validée par l'Auteur le 16/11).

Écrit UN fichier `jsons/zones_biomes_a_importer.json` (CLAUDE.md §18), DELTA seul :

- 30 `zone:*` génériques (aucune référence à un lieu réel) : `table_evenements`, `modificateurs`,
  `intensite_max` copiés de leur MODÈLE (zone existante la plus proche), `terrain_tags` propres,
  défauts de FAUNE ORDINAIRE et de ressources, SANS `regions` (le filtre reste en réserve).
  ⚠️ Les créatures des mythes ne sont jamais des défauts : elles se posent sur un placement.
- 16 essences en chaîne COMPLÈTE (arbre, tronc, gros rondin, rondin, petit rondin, branche) : la
  découpe est celle du moteur (`utils/bois.py`, tag `essence_<slug>`), aucune recette à écrire.
- 26 ressources récoltables (`composant`).
- 15 espèces de faune ordinaire, en GROUPES (comme « Fauves ») : caractéristiques et son d'une
  espèce proche existante, SANS `image` (l'interface retombe sur l'initiale ; à compléter quand
  l'illustration existera). Leur carcasse se crée au premier butin (`combat._ensure_loot_item`) ;
  la découpe en parties : relancer `gen_carcasses_parties` après import.
- Repeinte de `lieu:afrique_du_nord` et `lieu:egypte` (table `REPEINTE`) : placements ET `zones`
  des rencontres / ressources ; doc relu du dump, rien d'autre ne change.
- `zone:lac` : le défaut `espece:crocodile` posé par `gen_defauts_zones` (réservé par région) part
  sur `fleuve_tropical`.

Base comparée = dernier dump, SURCHARGÉ par les imports antérieurs non encore dans le dump
(`--apres`, défaut : `jsons/defauts_zones_a_importer.json` s'il existe). Refuse tout le lot sur un
`_id` neuf déjà pris par un doc différent ; un doc identique n'est pas réémis ; rien ⇒ aucun fichier.

    python dev/gen_zones_biomes.py [--dump …] [--apres f1.json,f2.json] [--sortie …]
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

from gen_genres_especes import accord_de  # noqa: E402
from gen_jetons_especes import TABLE as JETONS  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "zones_biomes_a_importer.json")
APRES_DEFAUT = [os.path.join(RACINE, "jsons", "defauts_zones_a_importer.json")]

# ── Zones ────────────────────────────────────────────────────────────────────────
# slug → (nom, modèle, terrain_tags, espèces (slugs), ressources (ids sans « item: »))
ZONES = {
	# Climats secs
	"maquis": ("Maquis", "garrigue", ["broussaille", "colline", "pierre", "aride"],
			   ["sanglier", "serpent", "renard", "lievre", "rapaces"],
			   ["Arbousier", "Baies_d_arbousier", "Herbes_a_bruler", "Herbes_medicinales"]),
	"pinede_seche": ("Pinède sèche", "foret_coniferes", ["foret", "conifere", "aride", "pierre"],
					 ["loup", "sanglier", "serpent", "araignee"],
					 ["Pin", "Resine_de_pin", "graines"]),
	"foret_chenes_lieges": ("Forêt de chênes-lièges", "foret_feuillus", ["foret", "bois", "clariere", "aride"],
							["cerf", "sanglier", "renard", "ecureuil"],
							["Chene_liege", "Liege", "Herbes_medicinales"]),
	"cedraie_altitude": ("Cédraie d'altitude", "contreforts", ["foret", "montagne", "conifere", "pente"],
						 ["singes", "fauves", "ours", "rapaces"],
						 ["Cedre", "Resine_de_cedre", "Eau_de_source"]),
	"oliveraie": ("Oliveraie", "verger", ["verger", "culture", "rural", "colline"],
				  ["petits_animaux_divers", "serpent", "renard"],
				  ["Olivier", "Olives", "Herbes_a_bruler"]),
	"palmeraie": ("Palmeraie", "oasis", ["oasis", "eau", "vegetation", "desert"],
				  ["serpent", "scorpion_geant", "nuee_de_scarabees"],
				  ["Palmier", "Dattes", "Eau_de_source"]),
	"steppe_aride": ("Steppe aride", "steppe", ["steppe", "plaine", "herbe", "aride"],
					 ["antilopes", "loup", "rapaces", "lievre"],
					 ["Alfa", "Feuilles_d_absinthe", "graines"]),
	"contreforts_arides": ("Contreforts arides", "contreforts", ["montagne", "colline", "roche", "pente", "aride"],
						   ["scorpion_geant", "serpent", "fauves", "oiseaux_de_proies"],
						   ["Genevrier", "pierre", "fer", "Sel_gemme"]),
	"steppe_epineuse": ("Steppe épineuse à acacias", "savane", ["savane", "plaine", "broussaille", "aride"],
						["antilopes", "hyenes", "autruches", "fauves", "rapaces"],
						["Acacia", "Gomme_d_acacia", "graines"]),
	"desert_froid": ("Désert froid", "hamada", ["desert", "roche", "froid", "plateau"],
					 ["loup", "rapaces"],
					 ["Saxaoul", "Sel_gemme", "pierre"]),
	"desert_brumeux": ("Désert côtier brumeux", "desert", ["desert", "sable", "cote", "brume"],
					   ["antilopes", "nuee_de_scarabees", "serpent", "scorpion_geant"],
					   ["Lichen_des_brumes", "Sel_gemme"]),
	"desert_succulentes": ("Désert de succulentes", "desert", ["desert", "sable", "vegetation", "aride"],
						   ["serpent", "scorpion_geant", "araignee_geante", "rapaces"],
						   ["Seve_de_succulente", "Epines", "Herbes_medicinales"]),
	# Tropiques
	"fleuve_tropical": ("Fleuve tropical", "riviere", ["riviere", "eau", "berge", "roseau", "tropical"],
						["crocodile", "rapaces", "hippopotames"],
						["Papyrus", "Lotus", "Acacia", "Eau_de_source"]),
	"marecage_tropical": ("Marécage tropical", "marais", ["marais", "eau", "boue", "tropical"],
						  ["crocodile", "serpent_geant", "hippopotames"],
						  ["Papyrus", "Herbes_medicinales", "Racine_de_mandragore"]),
	"lac_alcalin": ("Lac alcalin", "lac", ["lac", "eau", "berge", "sel", "tropical"],
					["flamants", "rapaces", "crocodile", "hyenes"],
					["Natron", "Sel_gemme"]),
	"savane_arboree": ("Savane arborée", "savane", ["savane", "plaine", "herbe", "tropical"],
					   ["elephants", "antilopes", "buffles", "hyenes", "fauves"],
					   ["Baobab", "Fruit_du_baobab", "graines"]),
	"fourre_epineux": ("Fourré épineux", "garrigue", ["broussaille", "aride", "tropical", "pierre"],
					   ["singes", "serpent", "araignee_geante", "rapaces"],
					   ["Acacia", "Epines", "Herbes_medicinales"]),
	"foret_equatoriale": ("Forêt équatoriale", "jungle", ["jungle", "foret", "tropical"],
						  ["grands_singes", "elephants", "fauves", "serpent_geant", "araignee_geante"],
						  ["Acajou", "Ebene", "Lianes", "Herbes_medicinales"]),
	"foret_galerie": ("Forêt-galerie", "foret_temperee_humide", ["foret", "riviere", "berge", "tropical"],
					  ["singes", "crocodile", "serpent", "fauves"],
					  ["Acajou", "Figues", "Eau_de_source"]),
	"foret_tropicale_seche": ("Forêt tropicale sèche", "foret_feuillus", ["foret", "bois", "aride", "tropical"],
							  ["fauves", "serpent", "sanglier", "singes"],
							  ["Teck", "Tamarin", "Herbes_a_bruler"]),
	"prairie_altitude_tropicale": ("Prairie d'altitude tropicale", "alpage",
								   ["montagne", "herbe", "pente", "brume", "tropical"],
								   ["singes", "rapaces", "oiseaux_de_proies"],
								   ["Lobelie_geante", "Herbes_medicinales", "Eau_de_source"]),
	"riziere": ("Rizière", "terres_cultivees", ["culture", "eau", "rural", "marais"],
				["buffles", "serpent", "rat_geant", "petits_animaux_divers"],
				["Riz", "Eau_de_source"]),
	# Froid et tempéré
	"foret_mixte_montagne": ("Forêt mixte de montagne", "contreforts",
							 ["foret", "montagne", "conifere", "bois", "pente"],
							 ["ours", "loup", "cerf", "ecureuil", "rapaces"],
							 ["Sapin", "Hetre", "Erable", "Seve_de_chene"]),
	"lande_arctique": ("Lande arctique", "toundra", ["toundra", "neige", "froid", "lande"],
					   ["rennes", "boeufs_musques", "loup", "ours_polaire"],
					   ["Lichen", "Bouleau", "plumes"]),
	"prairie_hautes_herbes": ("Prairie à hautes herbes", "plaine_ouverte", ["plaine", "herbe", "champ", "steppe"],
							  ["bisons", "loup", "cheval", "rapaces", "lievre"],
							  ["graines", "Herbes_medicinales", "Fleur_de_souci"]),
	"haut_plateau_froid": ("Haut plateau froid", "plateau", ["plateau", "herbe", "roche", "froid", "neige"],
						   ["yacks", "loup", "rapaces", "oiseaux_de_proies", "mammouth"],
						   ["Sel_gemme", "pierre", "Lichen"]),
	# Mers et côtes
	"recif_corallien": ("Récif corallien", "recif", ["mer", "recif", "eau", "cote", "tropical"],
						["poissons_mammiferes_marins", "serpent_geant"],
						["Corail", "Nacre"]),
	"mer_froide": ("Mer froide", "mer_cotiere", ["mer", "eau", "froid", "glace"],
				   ["phoques_et_morses", "poissons_mammiferes_marins", "ours_polaire"],
				   ["Huile_de_phoque", "Sel_gemme"]),
	"cote_tropicale": ("Côte tropicale", "littoral", ["cote", "mer", "plage", "sable", "tropical"],
					   ["crocodile", "rapaces", "tortues_marines"],
					   ["Cocotier", "Noix_de_coco", "Nacre"]),
	"foret_claire_seche": ("Forêt claire sèche", "foret_feuillus", ["foret", "clariere", "aride", "herbe"],
						   ["fauves", "serpent", "araignee", "antilopes"],
						   ["Eucalyptus", "Huile_d_eucalyptus", "Herbes_medicinales"]),
}

# ── Essences ─────────────────────────────────────────────────────────────────────
# slug (tag essence_<slug>, base d'_id) → (nom, rareté, poids arbre [min, max],
#   gros rondin, rondin, petit rondin, branche, caractère du bois)
# Tronc = [min arbre, max arbre / 2], comme les 14 essences existantes.
ESSENCES = {
	"Arbousier": ("arbousier", "commun", [80, 2500], [40, 90], [15, 35], [6, 14], [0.3, 1.5],
				  "Petit arbre tortueux au bois rougeâtre et serré, qui fleurit quand ses fruits de l'an passé mûrissent."),
	"Pin": ("pin", "commun", [150, 9000], [55, 120], [20, 45], [8, 18], [0.5, 2],
			"Bois tendre et résineux, droit et long : mâts, charpentes légères et torches qui brûlent longtemps."),
	"Chene_liege": ("chêne-liège", "commun", [150, 10000], [70, 140], [25, 55], [10, 22], [0.7, 2.5],
					"Sous l'épaisse écorce qu'on lève sans tuer l'arbre, un bois dur et lourd qui se travaille mal."),
	"Cedre": ("cèdre", "commun", [200, 16000], [80, 160], [30, 65], [12, 26], [0.8, 2.8],
			  "Bois odorant et imputrescible, que les vers fuient : coffres, plafonds et portes qu'on veut voir durer."),
	"Olivier": ("olivier", "commun", [150, 6000], [70, 140], [25, 55], [10, 22], [0.7, 2.5],
				"Bois dense et veiné, lent à pousser, que les tourneurs recherchent pour les bols et les manches."),
	"Palmier": ("palmier", "commun", [150, 5000], [50, 110], [18, 40], [7, 16], [0.5, 2],
				"Un stipe fibreux plus qu'un bois : il se refend mal, mais ses palmes couvrent les toits et se tressent en nattes."),
	"Genevrier": ("genévrier", "commun", [80, 3000], [45, 100], [15, 35], [6, 14], [0.4, 1.8],
				  "Bois noueux et parfumé, à peine plus haut qu'un anthrope, qui fume longtemps et chasse les insectes."),
	"Acacia": ("acacia", "commun", [100, 5000], [65, 130], [22, 50], [9, 20], [0.6, 2.3],
			   "Bois très dur sous une écorce hérissée d'épines ; il résiste à l'eau et ne pourrit guère."),
	"Saxaoul": ("saxaoul", "commun", [80, 2000], [60, 120], [20, 45], [8, 18], [0.6, 2.2],
				"Arbuste des sables au bois si lourd qu'il coule ; il brûle presque sans fumée."),
	"Baobab": ("baobab", "commun", [500, 30000], [60, 130], [22, 50], [9, 20], [0.5, 2],
			   "Tronc énorme et gorgé d'eau, au bois spongieux et léger, qu'on recherche pour l'écorce et les fibres."),
	"Acajou": ("acajou", "peu_commun", [200, 14000], [70, 150], [25, 55], [10, 22], [0.7, 2.5],
			   "Bois rouge, fin et stable, prisé des ébénistes et des constructeurs de coques."),
	"Ebene": ("ébène", "peu_commun", [150, 8000], [100, 190], [40, 85], [16, 32], [1, 3.5],
			  "Bois noir, si dense qu'il coule ; on en tire des pièces petites et précieuses."),
	"Teck": ("teck", "peu_commun", [200, 12000], [75, 150], [28, 60], [11, 24], [0.7, 2.6],
			 "Bois huileux et doré qui ne craint ni l'eau ni les vers : ponts de navires et pieux de quai."),
	"Sapin": ("sapin", "commun", [150, 12000], [55, 120], [20, 45], [8, 18], [0.5, 2],
			  "Bois blanc, léger et droit, le plus facile à fendre : planches, bardeaux et charpentes."),
	"Cocotier": ("cocotier", "commun", [100, 4000], [50, 110], [18, 40], [7, 16], [0.5, 2],
				 "Stipe souple qui plie sous le vent sans rompre ; ses fibres font les cordes des marins."),
	"Eucalyptus": ("eucalyptus", "commun", [150, 14000], [70, 140], [25, 55], [10, 22], [0.7, 2.5],
				   "Bois dur et lourd, à l'écorce qui pèle en lanières, dont les feuilles sentent fort la résine."),
}
ICONES_ARBRE = {"Palmier": "🌴", "Cocotier": "🌴"}

# ── Ressources ───────────────────────────────────────────────────────────────────
# id → (nom, icône, sous_categorie, tags, poids, rareté, valeur cu, description)
RESSOURCES = {
	"Baies_d_arbousier": ("Baies d'arbousier", "🍓", "fruit", ["plante"], 0.1, "commun", 4,
						  "Baies rouges et grenues, fades crues, meilleures en confiture ou en eau-de-vie."),
	"Resine_de_pin": ("Résine de pin", "🟠", "resine", [], 0.2, "commun", 5,
					  "Résine collante recueillie à l'entaille : elle calfate, colle et entretient les torches."),
	"Liege": ("Liège", "🟫", "ecorce", [], 0.5, "commun", 6,
			  "Plaque d'écorce levée sur un chêne-liège vivant : légère, souple, elle flotte et bouche les jarres."),
	"Resine_de_cedre": ("Résine de cèdre", "🟠", "resine", [], 0.2, "peu_commun", 15,
						"Résine odorante qui protège le bois et les étoffes des vers et de la pourriture."),
	"Olives": ("Olives", "🫒", "fruit", ["plante"], 0.3, "commun", 3,
			   "Olives amères cueillies à la main, à saumurer ou à presser."),
	"Dattes": ("Dattes", "🌴", "fruit", ["plante"], 0.3, "commun", 4,
			   "Grappe de dattes sucrées qui se gardent longtemps : la ration des longues marches."),
	"Alfa": ("Alfa", "🌾", "fibre", ["plante"], 0.3, "commun", 2,
			 "Herbe dure des steppes sèches, qu'on tresse en cordes, en paniers et en nattes."),
	"Gomme_d_acacia": ("Gomme d'acacia", "🟡", "resine", [], 0.1, "peu_commun", 12,
					   "Larmes de gomme durcie qui suintent de l'écorce : elles lient les encres et les remèdes."),
	"Lichen_des_brumes": ("Lichen des brumes", "🍃", "lichen", ["plante"], 0.05, "peu_commun", 10,
						  "Lichen qui ne vit que de l'humidité des brumes : il donne une teinture orangée."),
	"Seve_de_succulente": ("Sève de succulente", "💧", "seve", ["plante"], 0.2, "commun", 5,
						   "Sève épaisse et amère tirée d'une plante grasse, qui apaise les brûlures."),
	"Epines": ("Épines", "🌵", "epine", ["plante"], 0.05, "commun", 1,
			   "Longues épines dures, bonnes pour des aiguilles grossières ou des pièges."),
	"Papyrus": ("Papyrus", "🌿", "fibre", ["plante"], 0.3, "commun", 3,
				"Tiges de papyrus coupées dans l'eau : nattes, cordes, barques légères et feuilles d'écriture."),
	"Lotus": ("Fleur de lotus", "🪷", "fleur", ["plante"], 0.05, "peu_commun", 15,
			  "Fleur qui s'ouvre au soleil et se referme le soir ; on lui prête des vertus apaisantes."),
	"Natron": ("Natron", "🧂", "sel", [], 0.5, "commun", 4,
			   "Croûte de sel blanc des rives alcalines : elle lave, assèche et conserve."),
	"Fruit_du_baobab": ("Fruit du baobab", "🥥", "fruit", ["plante"], 0.5, "commun", 3,
						"Gousse veloutée à la pulpe sèche et acidulée, qui désaltère."),
	"Lianes": ("Lianes", "🌿", "fibre", ["plante"], 0.5, "commun", 2,
			   "Lianes souples coupées dans le sous-bois, solides comme une corde une fois tressées."),
	"Figues": ("Figues", "🍈", "fruit", ["plante"], 0.2, "commun", 3,
			   "Figues mûres, sucrées et fragiles, qui se sèchent au soleil."),
	"Tamarin": ("Tamarin", "🫘", "fruit", ["plante"], 0.2, "commun", 4,
				"Gousses brunes à la pulpe aigre-douce, qui relèvent les plats et soulagent le ventre."),
	"Lobelie_geante": ("Feuille de lobélie géante", "🌿", "herbe", ["plante"], 0.1, "peu_commun", 12,
					   "Feuille charnue d'une plante haute comme un anthrope, qui ne pousse qu'en altitude."),
	"Riz": ("Riz", "🍚", "grain", [], 0.5, "commun", 2,
			"Riz en paille, à battre et à décortiquer avant de le cuire."),
	"Lichen": ("Lichen", "🍃", "lichen", ["plante"], 0.05, "commun", 2,
			   "Lichen ras gratté sur la roche et le sol gelé : la pâture des bêtes du froid."),
	"Corail": ("Corail", "🪸", "corail", [], 0.3, "peu_commun", 20,
			   "Branche de corail arrachée au récif, rouge ou blanche, que les bijoutiers polissent."),
	"Nacre": ("Nacre", "🐚", "nacre", [], 0.2, "peu_commun", 18,
			  "Coquille irisée dont l'intérieur se taille en boutons, en incrustations et en parures."),
	"Huile_de_phoque": ("Huile de phoque", "🛢️", "huile", [], 0.5, "commun", 6,
						"Graisse fondue d'une bête échouée sur la glace : elle éclaire et graisse les cuirs."),
	"Noix_de_coco": ("Noix de coco", "🥥", "fruit", ["plante"], 0.8, "commun", 3,
					 "Noix lourde à coque fibreuse : son eau désaltère, sa chair nourrit, ses fibres se tressent."),
	"Huile_d_eucalyptus": ("Huile d'eucalyptus", "🧴", "huile", ["plante"], 0.1, "peu_commun", 10,
						   "Huile tirée des feuilles, à l'odeur forte, qui dégage la poitrine et chasse les insectes."),
}

# ── Espèces (faune ordinaire, en groupes) ────────────────────────────────────────
# slug → (nom, genre, h_aspire, référence (stats + son), jeton (taille, forme) | None, tags, description)
ESPECES = {
	"singes": ("Singes", "loup", ["animal", "ia_meute", "ia_hit_and_run"],
			   "Bandes bruyantes et agiles, qui harcèlent de haut et volent tout ce qui brille."),
	"grands_singes": ("Grands singes", "ours", ["animal", "ia_berserker"],
					  "Colosses du sous-bois, paisibles tant qu'on ne menace pas leur troupe."),
	"antilopes": ("Antilopes", "cerf", ["animal", "proie", "ia_fuyard_50"],
				  "Hardes rapides des plaines sèches, qui détalent au premier bruit."),
	"hyenes": ("Hyènes", "loup", ["animal", "predateur", "ia_meute", "ia_predateur"],
			   "Meutes ricanantes aux mâchoires capables de broyer les os."),
	"autruches": ("Autruches", "cerf", ["animal", "proie", "ia_fuyard_50"],
				  "Grands oiseaux coureurs, incapables de voler, dont le coup de patte éventre."),
	"hippopotames": ("Hippopotames", "ours", ["animal", "aquatique", "ia_berserker"],
					 "Masses grises des eaux lentes, plus redoutées que les crocodiles par les bateliers."),
	"flamants": ("Flamants", "petits_animaux_divers", ["animal", "vol", "proie", "ia_fuyard_50"],
				 "Nuées roses qui filtrent l'eau salée des rives, sur une patte."),
	"elephants": ("Éléphants", "mammouth", ["animal", "grande_taille", "ia_berserker"],
				  "Géants gris menés par une vieille femelle ; leur charge rase tout sur son passage."),
	"buffles": ("Buffles", "taureau", ["animal", "ia_berserker"],
				"Troupeaux massifs aux cornes recourbées, qui font front ensemble contre un fauve."),
	"rennes": ("Rennes", "cerf", ["animal", "proie", "froid", "ia_fuyard_50"],
			   "Cervidés du froid aux larges sabots, qui grattent la neige pour trouver le lichen."),
	"boeufs_musques": ("Bœufs musqués", "taureau", ["animal", "froid", "ia_berserker"],
					   "Bêtes laineuses qui se serrent en cercle, cornes dehors, face aux loups."),
	"bisons": ("Bisons", "taureau", ["animal", "ia_berserker"],
			   "Troupeaux bossus des herbes hautes ; leur galop fait trembler le sol."),
	"yacks": ("Yacks", "taureau", ["animal", "froid", "ia_berserker"],
			  "Bovins à longue toison des hauteurs froides, robustes et ombrageux."),
	"phoques_et_morses": ("Phoques et morses", "sanglier",
						  ["animal", "aquatique", "froid", "ia_berserker"],
						  "Colonies échouées sur la glace ; les mâles défendent leur rivage à coups de défenses."),
	"tortues_marines": ("Tortues marines", "sanglier", ["animal", "aquatique", "proie"],
						"Lourdes nageuses qui viennent pondre sur les plages, la nuit."),
}

# ── Repeinte des cartes déjà peintes ─────────────────────────────────────────────
REPEINTE = {
	"lieu:afrique_du_nord": {"zone:lac": "zone:fleuve_tropical", "zone:jungle": "zone:steppe_epineuse",
							 "zone:contreforts": "zone:contreforts_arides"},
	"lieu:egypte": {"zone:lac": "zone:fleuve_tropical", "zone:montagne": "zone:contreforts_arides"},
}
# Défaut retiré d'une zone tempérée : il vivait sur ce que la repeinte appelle désormais autrement.
RETRAITS_DEFAUTS = {"zone:lac": {"defauts_rencontres": ["espece:crocodile"]}}

PALIERS = (("arbre", "", "🌳"), ("tronc", "Tronc_", "🌳"), ("gros_rondin", "Gros_rondin_de_", "🪵"),
		   ("rondin", "Rondin_de_", "🪵"), ("petit_rondin", "Petit_rondin_de_", "🪵"), ("branche", "Branche_de_", "🌳"))


def _de(nom: str) -> str:
	"""« de chêne » / « d'acacia » (élision devant voyelle ou h muet)."""
	return ("d'" if nom[0].lower() in "aeiouéèêh" else "de ") + nom


def docs_essence(slug: str) -> list:
	nom, rarete, arbre, gros, rondin, petit, branche, caractere = ESSENCES[slug]
	cap = nom[0].upper() + nom[1:]
	de = _de(nom)
	de_cap = _de(cap)
	poids = {"arbre": arbre, "tronc": [arbre[0], arbre[1] / 2], "gros_rondin": gros, "rondin": rondin,
			 "petit_rondin": petit, "branche": branche}
	noms = {"arbre": cap, "tronc": f"Tronc {de_cap}", "gros_rondin": f"Gros rondin {de_cap}",
			"rondin": f"Rondin {de_cap}", "petit_rondin": f"Petit rondin {de_cap}", "branche": f"Branche {de_cap}"}
	phrases = {
		"arbre": f"Un arbre {de} sur pied : il faut l'abattre avant d'en tirer quoi que ce soit.",
		"tronc": f"Tronc {de} abattu et ébranché, trop lourd pour aller loin : il reste à le débiter.",
		"gros_rondin": f"Gros rondin {de} scié dans le fût, à refendre avant de servir.",
		"rondin": f"Rondin {de}, la mesure courante du bûcheron et du charpentier.",
		"petit_rondin": f"Petit rondin {de}, de quoi tourner un manche ou nourrir un feu.",
		"branche": f"Branche {de} élaguée, bonne à fagoter ou à tailler.",
	}
	tag = "essence_" + slug.lower()
	out = []
	for palier, prefixe, icone in PALIERS:
		if palier == "arbre":
			icone = ICONES_ARBRE.get(slug, icone)
		p = poids[palier]
		p = [int(v) if float(v).is_integer() else v for v in p]
		tags = ["bois", "a_couper", tag] if palier != "branche" else ["bois", tag]
		out.append({"_id": f"item:{prefixe}{slug}", "type": "item", "nom": noms[palier], "sous_categorie": palier,
					"icon": icone, "description": f"{phrases[palier]} {caractere}", "rarete": rarete,
					"categorie": "composant", "slots": [], "tags": tags, "poids": p})
	return out


def doc_ressource(rid: str) -> dict:
	nom, icone, sc, tags, poids, rarete, cu, desc = RESSOURCES[rid]
	return {"_id": f"item:{rid}", "type": "item", "nom": nom, "icon": icone, "description": desc,
			"rarete": rarete, "categorie": "composant", "sous_categorie": sc, "slots": [], "tags": list(tags),
			"poids": poids, "valeur": [{"cu": cu}]}


def doc_espece(slug: str, base: dict) -> dict:
	nom, ref, tags, desc = ESPECES[slug]
	r = base[f"espece:{ref}"]
	doc = {"_id": f"espece:{slug}", "type": "espece", "nom": nom, **accord_de(slug),
		   "description": desc, "base_attributes": json.loads(json.dumps(r["base_attributes"])),
		   "tags": list(tags), "proprietes": {}}
	jeton = JETONS[slug]
	if jeton:
		doc["jeton"] = {"taille": jeton[0], "forme": jeton[1]}
	if r.get("animation"):
		doc["animation"] = r["animation"]
	return doc


def doc_zone(slug: str, base: dict) -> dict:
	nom, modele, terrain, especes, ressources = ZONES[slug]
	m = base[f"zone:{modele}"]
	return {"_id": f"zone:{slug}", "type": "zone_influence", "nom": nom,
			"intensite_max": m.get("intensite_max", 0.5), "terrain_tags": list(terrain),
			"modificateurs": json.loads(json.dumps(m.get("modificateurs") or {})),
			"table_evenements": json.loads(json.dumps(m.get("table_evenements") or [])),
			"defauts_rencontres": [{"espece": f"espece:{e}"} for e in especes],
			"defauts_ressources": [{"ressource": f"item:{r}"} for r in ressources]}


def repeindre(lieu: dict, table: dict) -> dict:
	"""Copie du lieu, placements et `zones` des rencontres / ressources renommés par `table`."""
	neuf = {k: v for k, v in lieu.items() if k != "_rev"}
	neuf["zone_influences"] = [dict(p, zone=table.get(p.get("zone"), p.get("zone")))
							   for p in lieu.get("zone_influences") or []]
	for champ in ("rencontres", "ressources", "exclusions"):
		if champ in lieu:
			neuf[champ] = []
			for e in lieu.get(champ) or []:
				e = dict(e)
				if "zones" in e:
					e["zones"] = list(dict.fromkeys(table.get(z, z) for z in e.get("zones") or []))
				neuf[champ].append(e)
	return neuf


def construire(base: dict) -> list:
	"""Tous les docs voulus (neufs et modifiés), avant le filtre du delta."""
	docs = []
	for slug in ESSENCES:
		docs += docs_essence(slug)
	docs += [doc_ressource(r) for r in RESSOURCES]
	docs += [doc_espece(s, base) for s in ESPECES]
	docs += [doc_zone(s, base) for s in ZONES]
	for lid, table in REPEINTE.items():
		docs.append(repeindre(base[lid], table))
	for zid, retraits in RETRAITS_DEFAUTS.items():
		zone = base.get(zid)
		if not zone:
			continue
		neuve = {k: v for k, v in zone.items() if k != "_rev"}
		for champ, ids in retraits.items():
			cle = "espece" if champ == "defauts_rencontres" else "ressource"
			if champ in neuve:
				neuve[champ] = [d for d in neuve[champ] if d.get(cle) not in ids]
		docs.append(neuve)
	return docs


def verifier(docs: list, base: dict) -> list:
	"""Erreurs bloquantes : référence absente (espèce, item, modèle), `_id` dupliqué."""
	erreurs = []
	ids = [d["_id"] for d in docs]
	if len(ids) != len(set(ids)):
		erreurs.append("collision d'_id dans la sortie")
	connus = set(base) | set(ids)
	for slug, (_, modele, _, especes, ressources) in ZONES.items():
		if f"zone:{modele}" not in base:
			erreurs.append(f"{slug} : modèle zone:{modele} absent")
		erreurs += [f"{slug} : espece:{e} inconnue" for e in especes if f"espece:{e}" not in connus]
		erreurs += [f"{slug} : item:{r} inconnu" for r in ressources if f"item:{r}" not in connus]
	for slug, v in ESPECES.items():
		if f"espece:{v[1]}" not in base:
			erreurs.append(f"espèce {slug} : référence espece:{v[1]} absente")
		if slug not in JETONS:
			erreurs.append(f"espèce {slug} : absente de gen_jetons_especes.TABLE")
		if not accord_de(slug).get("pluriel"):
			erreurs.append(f"espèce {slug} : absente des PLURIELS de gen_genres_especes")
	return erreurs


def delta(docs: list, base: dict, neufs: set) -> tuple:
	"""(à émettre, refus) : un `_id` NEUF (préfixé item/espece/zone créé ici) déjà pris par un doc
	DIFFÉRENT est refusé ; un doc identique à la base n'est pas réémis."""
	emis, refus = [], []
	for d in docs:
		avant = base.get(d["_id"])
		propre = {k: v for k, v in (avant or {}).items() if k != "_rev"}
		if avant is None:
			emis.append(d)
		elif propre == d:
			continue
		elif d["_id"] in neufs:
			refus.append(d["_id"])
		else:
			emis.append(d)
	return emis, refus


def charger_base(dump: str, apres: list) -> dict:
	with open(dump, encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f)["docs"]}
	for chemin in apres:
		if os.path.exists(chemin):
			with open(chemin, encoding="utf-8") as f:
				for d in json.load(f):
					base[d["_id"]] = d
			print(f"Surcharge : {os.path.relpath(chemin, RACINE)}")
	return base


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--dump", default=None)
	ap.add_argument("--apres", default=None, help="imports antérieurs non encore dans le dump (virgules)")
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	dump = args.dump or sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))[-1]
	print(f"Dump : {os.path.relpath(dump, RACINE)}")
	apres = [os.path.join(RACINE, p) if not os.path.isabs(p) else p
			 for p in (args.apres.split(",") if args.apres else APRES_DEFAUT) if p]
	base = charger_base(dump, apres)
	docs = construire(base)
	erreurs = verifier(docs, base)
	if erreurs:
		print("\n".join("✗ " + e for e in erreurs))
		return 1
	neufs = ({f"item:{p}{s}" for s in ESSENCES for _, p, _ in PALIERS}
			 | {f"item:{r}" for r in RESSOURCES} | {f"espece:{s}" for s in ESPECES} | {f"zone:{s}" for s in ZONES})
	emis, refus = delta(docs, base, neufs)
	if refus:
		print("✗ _id déjà pris par un doc différent : " + ", ".join(refus))
		return 1
	compte = {}
	for d in emis:
		compte[d["_id"].split(":", 1)[0]] = compte.get(d["_id"].split(":", 1)[0], 0) + 1
	print(f"À émettre : {len(emis)} docs {compte}")
	if not emis:
		print("Rien à émettre : tout est déjà à jour.")
		return 0
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(emis, f, ensure_ascii=False, indent=1)
		f.write("\n")
	print(f"→ {os.path.relpath(args.sortie, RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())

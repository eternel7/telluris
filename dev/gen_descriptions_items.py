#!/usr/bin/env python
# dev/gen_descriptions_items.py
# Donne une `description` à tous les items du dump qui n'en ont pas.
#
# Trois sources, dans cet ordre :
# - VARIANTE sur mesure (bloc `fabrication.base_item`) : la description de son modèle, comme
#   le fait déjà `fabrication.CHAMPS_HERITES` pour une variante neuve — c'est parce que le
#   modèle n'en avait pas que la variante n'en a pas.
# - BOIS (tag `essence_<x>` + sous-catégorie de découpe) : forme × essence, cf. `FORMES_BOIS`
#   et `ESSENCES` — 15 essences × 6 formes, une table à la main serait 86 variations d'une
#   même phrase.
# - Tout le reste : la table `DESCRIPTIONS`, écrite à la main (slug d'item → texte).
#
# ⚠️ EXHAUSTIF : un item sans description qu'aucune source ne couvre FAIT ÉCHOUER le script
# (un item ajouté depuis ne reçoit jamais un texte par défaut), et une entrée de la table qui
# ne sert plus (item absent ou déjà décrit en base) est signalée.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. On relit chaque item depuis
# le dump le plus récent et on n'y injecte que `description` : régénérer est idempotent, et un
# item déjà décrit en base n'est JAMAIS réécrit — relancer sur un dump FRAIS.
#
# Usage : python dev/gen_descriptions_items.py [--dump chemin]
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/descriptions_items_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/descriptions_items_a_importer.json"

# essence (suffixe du tag `essence_<x>`) → (« d'alisier », trait du bois).
ESSENCES = {
	"alisier": ("d'alisier", "Bois dense et rosé, au grain si fin que luthiers et graveurs se le disputent."),
	"aulne": ("d'aulne", "Bois tendre qui rougit à la coupe ; sous l'eau, il ne pourrit pas — on en fait les pilotis."),
	"bouleau": ("de bouleau", "Bois clair et léger sous une écorce blanche qui brûle même mouillée."),
	"charme": ("de charme", "Le plus dur des bois communs : maillets, dents d'engrenage et manches qui ne cèdent pas."),
	"chataignier": ("de châtaignier", "Gorgé de tanin, il brave la pourriture : piquets, charpentes et douelles de tonneau."),
	"chene": ("de chêne", "Lourd, dur et durable : le bois des charpentes, des coques et des portes de place forte."),
	"erable": ("d'érable", "Bois clair au grain serré, que tourneurs et faiseurs de manches travaillent volontiers."),
	"frene": ("de frêne", "Souple et nerveux, il plie sans rompre : hampes, manches d'outils et arcs."),
	"hetre": ("de hêtre", "Bois homogène et sans odeur, bon pour l'écuelle comme pour le charbon."),
	"merisier": ("de merisier", "Bois rosé au beau grain, prisé des ébénistes pour les meubles de prix."),
	"orme": ("d'orme", "Ses fibres entrecroisées refusent la fente : on en tire moyeux de roue et quilles."),
	"peuplier": ("de peuplier", "Léger, tendre et vite poussé : caisses, sabots et planches à bon marché."),
	"saule": ("de saule", "Souple et léger, l'ami des vanniers et des faiseurs de paniers."),
	"tilleul": ("de tilleul", "Tendre et presque sans nœuds : le bois que préfèrent les sculpteurs."),
	"tremble": ("de tremble", "Bois blanc et léger qui ne se fend guère : bardeaux, écuelles et boîtes."),
}

# sous-catégorie de découpe → gabarit (« {de} » = « d'alisier »…).
FORMES_BOIS = {
	"arbre": "Un arbre {de} sur pied : il faut l'abattre avant d'en tirer quoi que ce soit.",
	"tronc": "Tronc {de} abattu et ébranché, trop lourd pour aller loin : il reste à le débiter.",
	"gros_rondin": "Gros rondin {de} scié dans le fût, à refendre avant de servir.",
	"rondin": "Rondin {de}, la mesure courante du bûcheron et du charpentier.",
	"petit_rondin": "Petit rondin {de}, de quoi tourner un manche ou nourrir un feu.",
	"branche": "Branche {de} élaguée, bonne à fagoter ou à tailler.",
}

# slug d'item (sans `item:`) → description.
DESCRIPTIONS = {
	# ── Armes ──────────────────────────────────────────────────────────────────────────────
	"Angon": "Javelot franc à longue douille de fer barbelée : planté dans un bouclier, il l'alourdit jusqu'à le rendre inutile.",
	"Azagay": "Sagaie légère à pointe de fer, faite pour être lancée vite et de loin.",
	"Baguette_houx": "Baguette de houx poli. Le houx garde sa verdure en hiver ; on dit qu'il garde aussi la magie.",
	"Baton_bois_vivant": "Bâton taillé dans une branche qui n'a jamais tout à fait cessé de vivre : quelques feuilles y repoussent encore au printemps.",
	"Baton_canalisateur": "Bâton cerclé de laiton, creusé d'une rainure où l'on sent passer le flux quand on incante.",
	"Baton_cornu": "Bâton noueux couronné d'une paire de cornes. Il impressionne autant qu'il concentre la volonté de son porteur.",
	"Baton_de_combat": "Bâton de bois dur ferré aux deux bouts : l'arme du pèlerin et du moine qui ne veut pas verser le sang.",
	"Bec_de_corbin": "Arme d'hast à pointe recourbée en bec, faite pour percer heaumes et plates.",
	"Bolas": "Pierres lestées reliées par des lanières : lancées dans les jambes, elles entravent la course.",
	"Boomerang_de_chasse": "Bâton courbe de chasseur, lancé à ras de terre pour briser les pattes du gibier.",
	"Buzdygan": "Masse d'armes à ailettes des steppes de l'Est. Plus qu'une arme, c'est une marque de commandement.",
	"Canne_ferree": "Canne de voyageur à embout de fer. On s'y appuie en chemin, on s'en sert quand le chemin tourne mal.",
	"Casse_tete_polynesien": "Massue de bois dur sculptée, venue des îles du grand océan.",
	"Cestus": "Lanières de cuir cloutées enroulées autour des poings : l'arme du pugiliste.",
	"Cestus_de_jet": "Poing de cuir lesté de plomb, assez lourd pour être lancé à courte distance.",
	"Chakram": "Anneau d'acier au tranchant extérieur aiguisé, lancé à plat d'un mouvement du poignet.",
	"Couteau_de_chasse": "Lame solide à dos épais, faite pour saigner le gibier comme pour se défendre.",
	"Couteau_de_jet_africain": "Lame à plusieurs branches tranchantes : quelle que soit sa rotation, une pointe frappe.",
	"Da_dao": "Grand sabre à deux mains à la lame lourde et large, qui tranche plus qu'il ne pique.",
	"Dague": "Lame courte à double tranchant, l'arme qu'on porte toujours sur soi.",
	"Dague_de_jet": "Dague équilibrée par la pointe, faite pour voler droit plutôt que pour parer.",
	"Dague_de_parade": "Dague à large garde, tenue dans la main gauche pour détourner la lame adverse.",
	"Dague_de_scene": "Dague de saltimbanque, assez fine pour un tour d'adresse, assez vraie pour un vrai coup.",
	"Darts_de_cavalerie": "Courtes fléchettes lestées que le cavalier jette à pleine main en chargeant.",
	"Epee_argent": "Lame plaquée d'argent, réputée mordre là où l'acier glisse sur les créatures de la nuit.",
	"Epee_courte": "Épée courte et maniable, à l'aise dans les ruelles comme dans la mêlée serrée.",
	"Epee_courte_rune": "Épée courte dont la lame porte des runes gravées ; elles s'éclairent faiblement quand on incante.",
	"Epee_longue": "Lame droite à une main, longue et équilibrée : l'arme du chevalier comme de l'homme d'armes.",
	"Epee_longue_ordre": "Épée longue frappée au pommeau des armes de l'ordre qui l'a remise à son porteur.",
	"Epee_une_main_benie": "Épée bénie au pied de l'autel ; sa garde en croix porte encore la trace de l'huile sainte.",
	"Falarique": "Lourd javelot à longue tige de fer, lancé à deux mains pour transpercer bouclier et porteur.",
	"Faucharde": "Lame de faux redressée au bout d'une hampe : l'arme des paysans levés en armes.",
	"Fleau_arme": "Boule hérissée pendue à une chaîne : elle contourne le bouclier qui croyait l'arrêter.",
	"Fleau_asiatique": "Deux bâtons courts reliés par une chaîne, maniés en moulinets rapides.",
	"Fleau_monte": "Grand fléau de cavalier à long manche, qui frappe de haut avec tout l'élan de la monture.",
	"Francisque": "Hache de jet franque au fer arqué : elle rebondit de façon imprévisible et tranche ce qu'elle touche.",
	"Gladius": "Courte épée de légionnaire, faite pour frapper d'estoc derrière le bouclier.",
	"Guisarme": "Arme d'hast à crochet : on accroche, on tire, et le cavalier se retrouve à terre.",
	"Hache_apparat_amerindienne": "Hachette ornée de plumes et de perles, aussi bonne à lancer qu'à montrer.",
	"Hache_de_guerre": "Lourde hache à large fer. Elle fend les écus — et, au besoin, le bois de chauffage.",
	"Hachette_scandinave": "Petite hache du Nord, équilibrée pour le lancer.",
	"Hallebarde": "Hache, pique et crochet au bout d'une même hampe : la reine des armes d'hast.",
	"Hunga_munga": "Fer de jet aux lames recourbées en tous sens, venu des peuples des savanes.",
	"Javelot_ethiopien": "Javelot de parade à fer ouvragé, porté par les dignitaires autant que lancé.",
	"Javelot_polynesien": "Javelot léger de bois dur, à pointe durcie au feu.",
	"Ji": "Hallebarde des empires de l'Est : pointe de lance et lame en croissant sur une même hampe.",
	"Jian": "Épée droite à double tranchant, fine et vive. On la dit « gentilhomme des armes ».",
	"Kanabo": "Massue de bois cerclée de fer et hérissée de clous : il faut la force d'un ogre pour la manier.",
	"Katana": "Sabre courbe des îles du Levant à la lame repliée cent fois ; son tranchant est légendaire.",
	"Kestros": "Fléchette à empennage de bois, lancée à la fronde.",
	"Kpinga": "Couteau de jet à trois lames rayonnantes, insigne du guerrier qui le porte.",
	"Kunai": "Outil de maçon devenu arme : une pointe à tout faire, qu'on plante ou qu'on lance.",
	"Lame_courte": "Lame courte sans garde, discrète sous un manteau.",
	"Lance_rituelle": "Lance gravée de signes rituels, plus faite pour l'office que pour la guerre — mais qui sait piquer.",
	"Lancelette": "Petite lance de jet, légère et pointue.",
	"Mambele": "Fer de jet en forme de faucille à crochet, venu des forêts du sud.",
	"Masse_a_brides": "Masse d'armes à ailettes : là où elle frappe, l'armure se tord et les côtes plient.",
	"Masse_benie": "Masse d'armes bénie, l'arme de ceux à qui leur foi défend de faire couler le sang.",
	"Masse_cannelee_perse": "Masse à tête cannelée venue de Perse, aussi belle que lourde.",
	"Morgenstern": "Massue à tête hérissée de pointes, l'« étoile du matin » des milices.",
	"Naginata": "Lame courbe au bout d'une longue hampe, maniée en grands arcs.",
	"Nzappa_zap": "Hache de jet à fer ajouré, signe de rang chez qui la porte.",
	"Omukuba": "Arme d'hast à tête de bois dur, venue des hautes terres.",
	"Pata_a_hampe": "Lame droite au bout d'une hampe, tenue par une garde-gantelet.",
	"Pilum": "Javelot de légionnaire : sa tige de fer plie à l'impact, il ne peut pas être renvoyé.",
	"Pique": "Longue hampe à pointe de fer : en rang serré, un mur que nulle charge ne franchit.",
	"Plumbata": "Fléchette lestée de plomb, lancée par-dessus les boucliers.",
	"Poincon_de_jet": "Pointe d'acier sans lame, lancée pour percer les mailles.",
	"Rapiere": "Épée fine et longue, faite pour l'estoc et la botte bien placée.",
	"Rungu": "Petite massue de jet à tête ronde, le bâton du berger des savanes.",
	"Sagaris": "Hache de cavalier des steppes, au fer étroit et pointu.",
	"Sarbacane": "Tube de roseau d'où l'on souffle des fléchettes. Silencieuse, et redoutable si la pointe est enduite.",
	"Sarisse": "Pique démesurée de la phalange : elle tient l'ennemi à cinq pas de soi.",
	"Sceptre_os": "Sceptre fait d'un long os gravé, cher aux nécromanciens et aux sorciers des marais.",
	"Schiavona": "Épée à garde en panier, celle des gardes des cités marchandes de l'Adriatique.",
	"Sestiere": "Fer de jet en étoile, lancé dans les jambes pour ralentir la course.",
	"Sheitan": "Lame de jet en forme de croissant, à la pointe recourbée comme une corne.",
	"Shuriken": "Étoile de jet en acier, cachée dans une manche jusqu'au dernier instant.",
	"Talwar": "Sabre courbe à garde en disque, venu des royaumes du Levant.",
	"Tomahawk": "Hachette légère à manche droit, aussi bonne à lancer qu'à brandir.",
	"Trident_barbele": "Trident aux pointes barbelées : ce qu'il prend, il le garde.",
	"Woludo": "Arme d'hast à lame large et courbe, venue des royaumes du sud.",
	"Yari": "Lance droite des îles du Levant, à la pointe longue et fine.",
	"dague_rituelle": "Dague à lame noircie, gravée de signes ; elle sert aux offrandes plus qu'aux combats.",
	"Arbalete": "Arbalète à étrier, que l'on bande au pied. Lente à recharger, son carreau perce la maille.",
	"Arbalete_de_poing": "Arbalète minuscule, tenue d'une main. Il faut des doigts agiles pour la réarmer.",
	"Arbalete_legere": "Arbalète au bras court, armée à la main : moins de puissance, mais plus de tirs.",
	"Arbalete_lourde": "Arbalète de siège à cranequin. Elle demande des bras solides et du temps, mais rien ne lui résiste.",
	"Arc": "Arc de bois simple, l'arme du chasseur et de l'archer de village.",
	"Arc_court": "Arc court et maniable, tiré à cheval comme dans les sous-bois.",
	"Arc_long": "Grand arc d'if aussi haut qu'un homme. Il faut des années pour le bander à fond.",
	"Hache_de_bucheron": "Hache de bûcheron à long manche : l'outil qui abat les arbres, et l'arme du pauvre.",
	# ── Armures et vêtements ───────────────────────────────────────────────────────────────
	"Armure_cuir_runee": "Armure de cuir dont chaque pièce porte des runes gravées au fer : elles protègent le corps et aiguisent l'esprit.",
	"Armure_cuir_souple_N": "Armure de cuir souple teint en noir, qui ne craque ni ne brille.",
	"Armure_plates_surcoat": "Armure de plates complète sous un surcot blanc : l'équipement du chevalier en campagne.",
	"Bandages_de_poing": "Bandes de lin serrées autour des mains, pour frapper sans se briser les doigts.",
	"Bandeau_de_cuir": "Bandeau de cuir qui tient les cheveux et la sueur loin des yeux.",
	"Bandeau_meditation": "Bandeau de lin léger que les ascètes nouent avant de méditer.",
	"Bonnet_de_clerc": "Bonnet de drap sombre, signe des gens d'étude et d'écritoire.",
	"Bottes_cuir_epais": "Bottes de cuir épais, imperméables et faites pour durer.",
	"Bottes_de_chasse": "Bottes hautes et souples, pour suivre une piste dans les fourrés.",
	"Bottes_de_fer": "Bottes renforcées de lames de fer sur le cou-de-pied et le tibia.",
	"Bottes_de_plates": "Solerets articulés de plates, qui protègent le pied jusqu'aux orteils.",
	"Bottes_de_voyage": "Bottes de route aux semelles cloutées, faites pour les longues lieues.",
	"Bottes_lacees": "Bottes lacées jusqu'au mollet, bien serrées au pied.",
	"Bottes_noires": "Bottes de cuir noir, sobres et bien cirées.",
	"Bottes_silencieuses": "Bottes à semelles de feutre, qui étouffent le bruit des pas.",
	"Bottines_de_scene": "Bottines légères de comédien, à la pointe relevée.",
	"Bottines_legeres": "Bottines basses et légères, pour qui préfère la vitesse à l'abri.",
	"Bracelets_os": "Bracelets d'os taillés et enfilés sur une lanière.",
	"Braies_fourrure": "Braies doublées de fourrure, pour les marches dans le froid.",
	"Brassards_os": "Brassards faits de plaques d'os liées au cuir, qui détournent une lame.",
	"Cagoule": "Cagoule de laine sombre qui ne laisse voir que les yeux.",
	"Calotte_cuir_rune": "Calotte de cuir gravée de runes, qui garde la tête froide et l'esprit clair.",
	"Cape_soie_sombre": "Cape à capuche en soie sombre. Elle tombe bien, se froisse peu et attire les regards.",
	"Capuche_bordeaux": "Capuche de drap teint couleur de vin.",
	"Capuche_de_laine": "Capuche de laine épaisse, contre la pluie et le vent.",
	"Capuche_noire": "Capuche de drap noir, qui laisse le visage dans l'ombre.",
	"Capuche_soie": "Capuche de soie fine : un luxe qui se voit de loin.",
	"Capuchon_de_lin": "Capuchon de lin léger, pour le soleil plus que pour la pluie.",
	"Chapeau_a_plume": "Chapeau orné d'une longue plume, coiffure de troubadour ou de galant.",
	"Chapeau_large_bord": "Chapeau à large bord qui protège du soleil comme des regards.",
	"Chapeau_mou": "Chapeau de feutre mou, qu'on plie au fond d'un sac sans l'abîmer.",
	"Chausses_ajustees": "Chausses de drap ajustées à la jambe.",
	"Chausses_bicolores": "Chausses mi-parties de deux couleurs, à la mode des cours et des bateleurs.",
	"Chausses_cuir": "Chausses de cuir souple, qui résistent aux ronces.",
	"Chausses_laine": "Chausses de laine tricotée, chaudes et simples.",
	"Chaussons_cuir": "Chaussons de cuir souple, à peine plus épais qu'un gant.",
	"Chaussons_silencieux": "Chaussons à semelle de feutre, pour marcher sans bruit sur les dalles.",
	"Coiffe_plumes": "Coiffe tressée de plumes, parure des chamans et des chefs.",
	"Cotte_de_mailles": "Cotte de mailles d'acier rivées une à une : elle arrête la lame, pas toujours le choc.",
	"Cotte_mailles_benie": "Cotte de mailles bénie, un peu plus légère que l'ordinaire, que l'on dit plus sûre aussi.",
	"Couronne_branchages": "Couronne de branches tressées, que portent les druides aux fêtes de saison.",
	"Couvre_chef_office": "Couvre-chef d'office, insigne d'une charge ou d'une confrérie.",
	"Cuirasse_cuir_brut": "Cuirasse de cuir épais à peine tanné, raide et lourde, mais solide.",
	"Cuirasse_cuir_noir": "Cuirasse de cuir bouilli teint en noir.",
	"Gantelets_acier": "Gantelets d'acier articulés, qui protègent la main sans trop gêner la prise.",
	"Gantelets_cuir": "Gantelets de cuir renforcés sur le dos de la main.",
	"Gantelets_de_plates": "Gantelets de plates à doigts articulés, le complément de l'armure complète.",
	"Gants_archer": "Gants à trois doigts renforcés, pour tirer la corde sans s'entailler.",
	"Gants_cuir_epais": "Gants de cuir épais, pour les travaux rudes.",
	"Gants_fins": "Gants de peau fine, signe d'élégance plus que de protection.",
	"Gants_fins_noirs": "Gants de peau fine teints en noir : élégance et discrétion.",
	"Gants_peau_noire": "Gants de peau noire, souples et sans couture visible.",
	"Gants_prestidigi": "Gants de prestidigitateur, aux doigts amincis pour les tours de passe-passe.",
	"Gants_runiques": "Gants brodés de runes au fil d'argent.",
	"Gants_sans_doigts": "Gants coupés aux phalanges, qui laissent les doigts libres.",
	"Heaume_de_fer": "Heaume de fer forgé d'une pièce, simple et solide.",
	"Heaume_de_plates": "Grand heaume de plates à visière, qui protège tout le visage.",
	"Heaume_ouvert_grave": "Heaume ouvert au timbre gravé de motifs, qui laisse le visage libre.",
	"Jambières_cuir": "Jambières de cuir lacées sur la jambe.",
	"Jambières_cuir_renf": "Jambières de cuir renforcées de lamelles cousues.",
	"Jambières_de_plates": "Cuissards et grèves de plates, qui protègent la jambe entière.",
	"Jupe_de_chanvre": "Jupe de chanvre grossier, simple et robuste.",
	"Jupe_lanieres_cuir": "Jupe de lanières de cuir, qui laisse les jambes libres et protège un peu.",
	"Jupe_longue_lin": "Jupe longue de lin, fraîche en été.",
	"Mocassins": "Mocassins de peau souple cousus d'une pièce, pour marcher sans bruit en forêt.",
	"Pantalon_ajuste_noir": "Pantalon noir ajusté, qui ne s'accroche à rien.",
	"Pantalon_ample": "Pantalon large et léger, qui ne gêne aucun mouvement.",
	"Pantalon_cuir": "Pantalon de cuir solide, qui résiste aux ronces et aux chutes.",
	"Pantalon_toile": "Pantalon de toile, le vêtement de tous les jours.",
	"Pantalon_velours": "Pantalon de velours, doux et cossu.",
	"Pourpoint_colore": "Pourpoint aux couleurs vives, cousu pour être vu.",
	"Pourpoint_cuir_renf": "Pourpoint de cuir renforcé de plaques cousues entre deux épaisseurs.",
	"Robe_bordeaux": "Robe de drap couleur de vin, à capuche.",
	"Robe_ceremonie": "Robe de cérémonie brodée, portée pour les offices et les grandes heures.",
	"Robe_de_savant": "Robe ample de savant, aux manches tachées d'encre.",
	"Robe_laine_epaisse": "Robe de laine épaisse, pour les nuits froides et les cloîtres glacés.",
	"Robe_lin_ceinturee": "Robe de lin simple, serrée à la taille par une ceinture.",
	"Robe_noire_capuche": "Robe noire à capuche, légère, pour se fondre dans l'ombre.",
	"Sandales_de_corde": "Sandales à semelle de corde tressée.",
	"Sandales_lierre": "Sandales tressées de lierre, aussi légères qu'éphémères.",
	"Sandales_moine": "Sandales de cuir simple, telles qu'en portent les moines sur les chemins.",
	"Souliers_cuir": "Souliers de cuir bas, pour la ville.",
	"Sous_robe_lin": "Sous-robe de lin, portée sous le vêtement de dessus.",
	"Sous_robe_noire": "Sous-robe de lin teint en noir.",
	"Tunique_feuilles": "Tunique de lin où sont tressées des feuilles fraîches, renouvelées à chaque saison.",
	"Veste_cuir_souple": "Veste de cuir souple, qui protège un peu et gêne peu.",
	"Vetements_totémiques": "Vêtements de peau peints de motifs totémiques, qui placent leur porteur sous la garde des esprits du clan.",
	"amulette": "Amulette pendue au cou, porte-bonheur ou souvenir.",
	"armure_de_cuir": "Armure de cuir bouilli, durcie à la cire : la protection la plus répandue.",
	"bijou": "Anneau de métal ouvragé, porté pour le plaisir ou pour le rang.",
	"bottes": "Bottes de cuir ordinaires.",
	"ceinture": "Ceinture de cuir à boucle ouvragée, qui tient la tenue et donne de l'allure.",
	"gants": "Gants de cuir ordinaires.",
	"harnais": "Harnais de sangles de cuir, où l'on accroche armes et outils.",
	"parure": "Parure de tête ornée de perles et de fils de métal.",
	"talisman": "Talisman gravé de signes protecteurs, porté au cou.",
	"collier": "Collier de belle facture, qui attire l'œil et délie les langues.",
	# ── Boucliers ──────────────────────────────────────────────────────────────────────────
	"Bocle": "Petit bouclier rond tenu au poing, pour parer au plus près.",
	"Bouclier_cerf_volant": "Grand bouclier en amande, qui couvre le cavalier de l'épaule au genou.",
	"Bouclier_chauffe": "Bouclier en forme de fer à repasser, le plus courant des hommes d'armes.",
	"Bouclier_normand": "Long bouclier normand en amande, bordé de fer.",
	"Bouclier_ordre": "Bouclier peint aux armes de l'ordre de son porteur.",
	"Bouclier_sacre": "Bouclier frappé d'une croix sacrée : il n'obéit qu'à une volonté ferme.",
	"Ecu": "Écu de bois cerclé de fer, recouvert de cuir.",
	"Ecu_de_joute": "Écu de tournoi épais et lourd, fait pour encaisser la lance.",
	"Pavois": "Grand pavois qu'on plante en terre pour s'abriter des traits — à peine portable.",
	"Pelta": "Petit bouclier léger en croissant, celui des tirailleurs.",
	"Rondache": "Bouclier rond de taille moyenne, maniable et sûr.",
	"Targe": "Bouclier rond à umbo central, maniable en mêlée.",
	# ── Catalyseurs ────────────────────────────────────────────────────────────────────────
	"Grimoire_base": "Recueil de formules élémentaires que tout apprenti recopie et garde à portée de main.",
	"Orbe_arcanique": "Sphère de cristal où tournoie une brume lumineuse : elle focalise le flux arcanique.",
	"Symbole_sacre": "Symbole de foi en métal, que l'on brandit ou que l'on porte au cou pour prier.",
	"catalyseur_magique": "Objet chargé de magie latente, que l'enchanteur sacrifie pour lier un sort à la matière.",
	"focus_magique": "Pierre taillée montée sur un manche court, qui rassemble le flux et rend des forces au mage.",
	# ── Composants ─────────────────────────────────────────────────────────────────────────
	"Cercle_invocation": "Parchemin où est tracé un cercle d'invocation : on le coud dans une doublure ou on le lie à un catalyseur.",
	"Encens": "Grains de résine odorante. Leur fumée apaise l'esprit et prépare aux rites.",
	"Fiole_sang_bete": "Sang de bête sauvage en fiole scellée. Les forgerons en trempent l'acier pour lui donner la férocité de l'animal.",
	"Fragments_ame": "Éclats translucides, à peine pesants, qui murmurent quand on les tient trop longtemps.",
	"Graine_sacree": "Graine bénie, recueillie dans un jardin de sanctuaire ; elle porte la vie en germe.",
	"Os_de_totem": "Os gravé tiré d'un totem de clan ; il en garde un peu de l'esprit protecteur.",
	"Parchemin_blanc": "Feuille de vélin vierge, prête à recevoir l'encre.",
	"Parchemin_vierge": "Parchemin préparé pour recevoir un sort, aux marges déjà enluminées.",
	"Peintures_de_guerre": "Pâtes colorées dont les guerriers se peignent le visage, ou leurs armes, avant la bataille.",
	"Poison_de_base": "Poison simple tiré de plantes communes. Sur une lame, il affaiblit qui en est touché.",
	"Poudre_amethyste": "Améthyste broyée en poudre violette, réputée apaiser l'esprit et attirer la magie.",
	"Poudre_de_miroir": "Éclats de miroir broyés fin. Mêlée au métal ou à la teinture, elle trouble le regard.",
	"Salpetre": "Sel blanc gratté sur les murs des caves. Il active le feu et mord le métal.",
	"Sang_demon_seche": "Sang de démon réduit en croûte noire. Il brûle encore au toucher.",
	"Sel": "Sachet de sel gris, qui conserve la viande et sert à mille usages.",
	"Sel_noir": "Sel noirci aux cendres de rites obscurs. Il jette l'ombre sur ce qu'il touche.",
	"Soufre": "Soufre jaune à l'odeur d'œuf pourri, prisé des alchimistes.",
	"composant_rituel": "Assortiment de cendres, d'herbes et d'os consacrés, préparé pour un rite.",
	"engrais": "Fumier et cendres mêlés, qui nourrissent la terre.",
	"feutre": "Laine foulée en une étoffe épaisse et dense.",
	"fil_resistant": "Fil de lin ciré, solide, pour les coutures qui doivent tenir.",
	"ligatures": "Liens de cuir et de fil pour assembler, serrer et renforcer.",
	"pigment": "Poudre colorée tirée de terres et de plantes, base des encres et des teintures.",
	"poudre_alchimique": "Poudre aux reflets changeants, préparée au creuset par un alchimiste.",
	"reactif_alchimique": "Réactif d'alchimiste, qui fume légèrement quand on débouche la fiole.",
	"reactif_magique": "Fiole d'un réactif chargé de magie, aux reflets qui ne se fixent jamais.",
	"relique": "Fragment d'os ou d'étoffe ayant appartenu à un saint, enchâssé dans un petit reliquaire.",
	"rembourrage": "Bourre de laine et de crin, pour garnir gambisons, selles et coussins.",
	"boyaux": "Boyaux nettoyés et séchés, dont on tire cordes et liens.",
	"boyaux_pour_saucisses": "Boyaux lavés et salés, prêts à être embossés par le charcutier.",
	"coeur": "Cœur d'une créature, encore lourd de sa force vitale.",
	"cordes_d_instrument": "Cordes de boyau fines et tendues, pour luths et vielles.",
	"cordes_d_arc": "Cordes d'arc de lin torsadé et ciré.",
	"crane": "Crâne nettoyé, prisé des nécromanciens comme des collectionneurs.",
	"crins": "Crins de cheval, pour archets, pinceaux et tamis.",
	"Cristal_canalisation": "Cristal limpide qui vibre doucement quand le flux magique le traverse.",
	"crocs": "Crocs arrachés à une bête, assez durs pour être montés en arme.",
	"cuir": "Cuir tanné, prêt à être coupé et cousu.",
	"cuir_brut": "Peau fraîchement écorchée, qui doit encore passer chez le tanneur.",
	"Eau_benite": "Eau bénie par un prêtre, en fiole de verre scellée.",
	"Eau_de_source": "Eau claire puisée à une source vive.",
	"Encre": "Encre noire de noix de galle, pour écrire et copier.",
	"Encre_magique": "Encre où l'on a dissous des réactifs : les signes qu'elle trace gardent un peu de magie.",
	"Encre_noire": "Encre d'un noir profond, faite de suie et de gomme, qui sert à tracer les runes.",
	"foie": "Foie frais, bon à manger ou à disséquer.",
	"graisse": "Graisse animale fondue, pour la cuisine, les chandelles et l'entretien du cuir.",
	"griffes": "Griffes arrachées à une bête, prisées des artisans et des chamans.",
	"Herbes_a_bruler": "Herbes séchées qu'on brûle pour leur fumée odorante ou purifiante.",
	"Herbes_medicinales": "Herbes médicinales cueillies et séchées, base des remèdes et des cataplasmes.",
	"manche": "Manche de bois tourné, à emmancher sur un outil ou une arme.",
	"os": "Os nettoyé, matière première du tabletier et de l'artisan.",
	"plumes": "Plumes de volaille ou d'oiseau sauvage, pour l'empennage ou l'oreiller.",
	"poils": "Poils et bourre d'animal, pour le feutre et les pinceaux.",
	"Poudre_os": "Os calcinés et broyés en poudre blanche.",
	"sang": "Sang recueilli dans une fiole, encore chaud de la bête.",
	"Seve_de_chene": "Sève de chêne recueillie à l'entaille, épaisse et ambrée.",
	"tendons": "Tendons séchés, dont on tire des fils plus solides que le lin.",
	"viande": "Viande crue, à cuire, sécher ou fumer sans tarder.",
	"yeux": "Yeux d'une créature, conservés pour les alchimistes.",
	# ── Consommables ───────────────────────────────────────────────────────────────────────
	"Bandages": "Bandes de lin propres, pour panser une plaie.",
	"Huile_entretien": "Huile légère pour protéger les lames de la rouille et assouplir le cuir.",
	"Pierre_a_aiguiser": "Pierre à grain fin, pour redonner le fil à une lame émoussée.",
	"Ration_de_voyage": "Pain dur, fromage sec et fruits séchés, enveloppés pour la route.",
	"Tisane_concentration": "Infusion amère d'herbes choisies, qui éclaircit l'esprit et ranime la magie.",
	"Torche": "Bâton entouré d'étoupe imbibée de poix, qui brûle une heure.",
	"Viande_sechee": "Lanières de viande séchée, qui tiennent des semaines dans un sac.",
	"cataplasme": "Emplâtre d'herbes broyées à appliquer sur une blessure.",
	"elixir_revigorant": "Élixir doré qui rend d'un trait la vigueur du corps et l'énergie de l'esprit.",
	"encens": "Bâtonnet d'encens à faire brûler ; sa fumée calme l'esprit et ranime la magie.",
	"huile": "Huile parfumée à masser sur les muscles las, qui hâte la guérison.",
	"mets_rare": "Mets rare et nourrissant, qui donne de la force pour un long moment.",
	"onguent": "Onguent gras qui referme lentement les plaies.",
	"plat_raffine": "Plat raffiné dont on parle encore le lendemain : il met en appétit et en confiance.",
	"potion": "Fiole de potion de soin rouge, qui referme les blessures d'un trait.",
	"potion_de_vision": "Potion qui aiguise le regard et la vivacité pour quelque temps.",
	"remede": "Remède d'apothicaire, qui soigne et soutient la convalescence.",
	"repas_cuisine": "Un vrai repas chaud, qui remet sur pied.",
	"saucisses": "Saucisses fumées, de quoi tenir une journée de marche.",
	"savon": "Pain de savon parfumé : on paraît mieux propre.",
	"sirop_de_seve": "Sirop de sève épais et sucré, qui réchauffe et redonne des forces.",
	"viande_fumee": "Viande fumée longuement, qui se conserve et nourrit bien.",
	"Bougie": "Chandelle de suif, qui éclaire une veillée et s'éteint d'un souffle.",
	# ── Documents et livres ────────────────────────────────────────────────────────────────
	"Carnet_chansons": "Carnet de chansons griffonné : couplets, refrains et airs à reprendre en chœur.",
	"Carnet_de_sorts": "Carnet de notes où un mage consigne ses formules et ses observations.",
	"Carnet_illusionniste": "Carnet d'illusionniste, plein de croquis de tours et de formules de trompe-l'œil.",
	"Dico_des_langues": "Gros dictionnaire qui met en regard les mots de plusieurs langues.",
	"Lettre_de_creance": "Lettre scellée qui atteste du crédit de son porteur auprès d'un banquier ou d'un marchand.",
	"Livre_prieres": "Livre de prières relié de cuir, aux pages usées par les doigts.",
	"Manuel_creatures": "Manuel illustré décrivant les créatures connues, leurs mœurs et leurs faiblesses.",
	"Parchemin_ordre": "Parchemin aux armes de l'ordre, porteur d'une mission ou d'un ordre de route.",
	"Sceau_ordre": "Sceau gravé aux armes de l'ordre, qui authentifie ses actes.",
	"Grimoire_necromancie": "Grimoire relié de peau sombre, plein des secrets qui font se relever les morts.",
	"Grimoire_pactes": "Grimoire où sont consignés les pactes conclus avec les puissances d'en bas, et leurs clauses.",
	# ── Métaux ─────────────────────────────────────────────────────────────────────────────
	"acier": "Lingot d'acier trempé, plus dur et plus tenace que le fer.",
	"bronze": "Lingot de bronze, alliage de cuivre et d'étain : moins dur que l'acier, mais il ne rouille pas.",
	"fer": "Lingot de fer brut, prêt pour la forge.",
	"adamantite": "Lingot d'adamantite, métal presque indestructible que seuls les plus grands forgerons savent travailler.",
	"mithril": "Lingot de mithril, métal argenté plus léger qu'une plume et plus dur que l'acier.",
	"orichalque": "Lingot d'orichalque aux reflets cuivrés, métal légendaire que la magie traverse sans peine.",
	# ── Munitions ──────────────────────────────────────────────────────────────────────────
	"Carquois_20": "Carquois de cuir garni de vingt flèches.",
	"Carreaux_argentes": "Dix carreaux d'arbalète à pointe argentée, pour les créatures que le fer ne blesse pas.",
	"empennage_de_fleches": "Plumes taillées et collées pour empenner les flèches.",
	# ── Outils et menus objets ─────────────────────────────────────────────────────────────
	"Corde_10m": "Dix mètres de corde de chanvre.",
	"Corde_5m": "Cinq mètres de corde de chanvre.",
	"Cordes_rechange": "Cordes de rechange pour un instrument ou un arc.",
	"Craie": "Bâton de craie pour marquer les murs, tracer un cercle ou retrouver son chemin.",
	"Crochet_serrurier": "Crochet de serrurier, pour les serrures dont on n'a pas la clé.",
	"Crochets": "Trousse de crochets fins, pour forcer les serrures.",
	"Fard_de_scene": "Boîte de fards de comédien, pour changer de visage le temps d'une scène.",
	"Menottes": "Fers à verrou pour entraver les poignets d'un prisonnier.",
	"Miroir_de_poche": "Petit miroir de métal poli, pour se recoiffer ou regarder au coin d'un mur.",
	"Petite_bourse_vide": "Petite bourse de cuir à cordon, vide.",
	"Petite_glace": "Petite glace dans un cadre de bois, pour se mirer.",
	"Piege_a_collet": "Collet de fil de laiton, pour prendre lapins et lièvres.",
	"Pierre_de_meditation": "Galet lisse que l'on tient en méditant, pour fixer l'esprit.",
	"aiguille": "Aiguille d'acier, pour coudre ou repriser.",
	"brosse": "Brosse de crin, pour le cheval, les habits ou les bottes.",
	"corde": "Corde de chanvre solide, toujours utile en route.",
	"de": "Dé d'os aux points gravés, compagnon des tavernes et des veillées.",
	"filet": "Filet de corde, pour pêcher, chasser ou capturer.",
	"fourreau": "Fourreau de cuir pour ranger une lame.",
	"oreiller": "Oreiller garni de plumes : le luxe du voyageur.",
	"outres": "Outres de peau, pour porter l'eau ou le vin.",
	"peigne": "Peigne de corne.",
	"pinceau": "Pinceau de poils fins, pour peindre ou enluminer.",
	"sac": "Sac de toile solide, pour porter ce qu'on ne peut pas tenir à la main.",
	"trophee": "Trophée de chasse ou de victoire, que l'on expose fièrement.",
	"Plume_d_oie": "Plume d'oie taillée en bec, pour écrire à l'encre.",
}


def _essence(doc: dict):
	for tag in doc.get("tags") or []:
		if isinstance(tag, str) and tag.startswith("essence_"):
			return tag[len("essence_"):]
	return None


def _slug(item_id: str) -> str:
	return item_id.split(":", 1)[1] if ":" in item_id else item_id


def a_une_description(doc: dict) -> bool:
	return bool(str(doc.get("description") or "").strip())


def description_de(doc: dict, items: dict, neuves: dict):
	"""Texte à poser sur `doc`, ou None si aucune source ne le couvre.

	`items` = tous les items du dump (par `_id`), `neuves` = descriptions déjà décidées
	(par `_id`) — une variante dont le modèle vient d'être décrit en hérite."""
	base_id = (doc.get("fabrication") or {}).get("base_item")
	if base_id:
		base = items.get(base_id) or {}
		if a_une_description(base):
			return base["description"]
		return neuves.get(base_id) or DESCRIPTIONS.get(_slug(base_id))
	essence = _essence(doc)
	forme = FORMES_BOIS.get(doc.get("sous_categorie") or "")
	if essence in ESSENCES and forme:
		de, trait = ESSENCES[essence]
		return forme.format(de=de) + " " + trait
	return DESCRIPTIONS.get(_slug(doc["_id"]))


def avec_description(doc: dict, texte: str) -> dict:
	"""Copie du doc sans `_rev` (réattaché à l'import), `description` placée après `icon`
	(ou `nom`) comme dans les docs déjà décrits."""
	sortie = {}
	ancre = "icon" if "icon" in doc else "nom"
	for cle, val in doc.items():
		if cle in ("_rev", "description"):
			continue
		sortie[cle] = val
		if cle == ancre:
			sortie["description"] = texte
	sortie.setdefault("description", texte)
	return sortie


def generer(docs: list):
	"""→ (docs à importer, ids sans source, entrées de table inutiles)."""
	items = {d["_id"]: d for d in docs
			 if isinstance(d, dict) and d.get("type") == "item" and d.get("_id")}
	a_decrire = sorted(i for i, d in items.items() if not a_une_description(d))
	neuves, manquants = {}, []
	# Les modèles d'abord, pour qu'une variante hérite du texte neuf de son modèle.
	for item_id in sorted(a_decrire, key=lambda i: bool((items[i].get("fabrication") or {}).get("base_item"))):
		texte = description_de(items[item_id], items, neuves)
		if texte:
			neuves[item_id] = texte
		else:
			manquants.append(item_id)
	sortie = [avec_description(items[i], neuves[i]) for i in a_decrire if i in neuves]
	utilisees = {_slug(i) for i in neuves}
	utilisees |= {_slug((items[i].get("fabrication") or {}).get("base_item") or "") for i in neuves}
	inutiles = sorted(s for s in DESCRIPTIONS if s not in utilisees)
	return sortie, sorted(manquants), inutiles


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun jsons/telluris-dump-*.json")
	return dumps[-1]


def charger(chemin: str) -> list:
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data.get("docs", []) if isinstance(data, dict) else data


def main() -> None:
	args = sys.argv[1:]
	source = args[args.index("--dump") + 1] if "--dump" in args else _dump_le_plus_recent()
	sortie, manquants, inutiles = generer(charger(source))
	print(f"relu {os.path.relpath(source, RACINE)}")
	if inutiles:
		print("Entrées de la table SANS EMPLOI (item absent ou déjà décrit) :\n   " + ", ".join(inutiles))
	if manquants:
		print("Items sans description qu'aucune source ne couvre (à écrire) :\n   " + ", ".join(manquants))
		sys.exit(1)
	if not sortie:
		print("Tous les items ont déjà une description : aucun fichier écrit.")
		return
	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	variantes = sum(1 for d in sortie if (d.get("fabrication") or {}).get("base_item"))
	bois = sum(1 for d in sortie if _essence(d) and d.get("sous_categorie") in FORMES_BOIS)
	print(f"écrit {SORTIE} : {len(sortie)} item(s) décrit(s)")
	print(f"   {len(sortie) - variantes - bois} par la table, {bois} bois (essence × forme), "
		  f"{variantes} variante(s) héritant de leur modèle")


if __name__ == "__main__":
	main()

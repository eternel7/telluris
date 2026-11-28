#!/usr/bin/env python
# dev/gen_images_hekla.py
# Images de l'arc de l'Hekla (docs/plan_hekla.md § 12, docs/hekla_neuf_cercles.md) : UN lot Gemini pour
# quatre genres — monstres (1:1, fond uni → détourage → monsters/<base>_transparent.webp), cartes de combat
# (16:9 → battle_maps/), lieux (16:9 → towns/), portraits (16:9 → pnj/). Règles : docs/prompts_images.md.
#
#   python dev/gen_images_hekla.py preparer   → écrit dev/batch/hekla/prompts.json + prompts.md (gratuit)
#   python dev/gen_images_hekla.py compter    → nombre d'images restantes et coût estimé
#   python dev/gen_images_hekla.py avancer    → soumet le lot / suit / récupère (PAYANT), à rejouer jusqu'à « terminé »
#   python dev/gen_images_hekla.py refaire minos,lion  → remet ces clés au prochain lot (l'ancien fichier reste)
#
# État : dev/batch/hekla/manifeste.json. Jamais d'écrasement (nom libre suivant), jamais de suppression :
# une image rejetée (uniforme, bruit, détourage impossible) est GARDÉE dans dev/batch/hekla/echecs/ et notée
# dans `echecs` du manifeste ; sa clé repart au lot suivant. Image brute des monstres : dev/batch/hekla/brutes/.

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_images_magasins as magasins  # noqa: E402
from detourer_image import detourer  # noqa: E402

RACINE = magasins.RACINE
DOSSIER = os.path.join(RACINE, "dev", "batch", "hekla")
PROMPTS = os.path.join(DOSSIER, "prompts.json")
PROMPTS_MD = os.path.join(DOSSIER, "prompts.md")
MANIFESTE = os.path.join(DOSSIER, "manifeste.json")
REQUETES = os.path.join(DOSSIER, "requetes.jsonl")
BRUTES = os.path.join(DOSSIER, "brutes")
ECHECS = os.path.join(DOSSIER, "echecs")
RES = os.path.join(RACINE, "templates", "resources")
CIBLES = {"monstre": os.path.join(RES, "monsters"), "battlemap": os.path.join(RES, "battle_maps"),
		  "lieu": os.path.join(RES, "towns"), "portrait": os.path.join(RES, "pnj")}
RATIOS = {"monstre": "1:1", "battlemap": "16:9", "lieu": "16:9", "portrait": "16:9"}  # prompts_images § 0.3

# ── Blocs communs (docs/prompts_images.md § 0.1, 0.1 bis, 0.2, 0.5 quater), écrits EN ENTIER ──
STYLE = ("Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : "
		 "peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. "
		 "Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, "
		 "aucun filigrane.")
STYLE_PORTRAIT = ("Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : "
				  "peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches "
				  "de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue "
				  "d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune "
				  "enseigne lisible.")
FOULE = ("Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en "
		 "proportions égales : les humains ne sont pas plus nombreux que les autres ; les ogres ne sont ni des orcs "
		 "ni des trolls : leur peau a un teint humain, rosé, hâlé, brun ou cuivré, jamais verte, jamais grise. "
		 "Pas de texte visible.")
BATTLEMAP = "La vue est aérienne. C'est une battlemap."
# Templiers de Telluris : ordre sans lien avec une foi (CLAUDE lore : aucune référence au christianisme).
SANS_CROIX = "Leurs tabards et bannières portent un emblème de tour et de flamme, sans aucune croix ni symbole religieux."
ENFER = "dans un monde souterrain d'un autre monde, sous une voûte de roche immense, sans ciel ni volcan visible"
# Lot 1 : « sous un volcan » dessinait un cône de volcan DANS la grotte et poussait les cartes en panorama.


def _monstre(sujet, fond="magenta"):
	return (f"Réalise l'image {sujet} La créature occupe environ 80 % de l'image, entière, sans membre coupé par "
			f"le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, {fond} pur, sans dégradé, sans décor, "
			f"sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette "
			f"couleur. {STYLE}")


def _carte(sujet):
	return (f"Réalise l'image {sujet} Vue strictement verticale, prise de dessus comme un plan de table de jeu : "
			f"aucun horizon, aucun ciel, aucune montagne, aucune paroi du fond vue en perspective ; tout le cadre est "
			f"occupé par le sol de la scène. Sol lisible, murs et obstacles nettement marqués, zones infranchissables bien "
			f"distinctes du sol praticable, sans personnage ni créature. {STYLE} {BATTLEMAP}")


def _lieu(sujet):
	return f"Réalise l'image {sujet} {STYLE}"


def _portrait(sujet):
	return f"Réalise l'image du portrait illustré {sujet} {STYLE_PORTRAIT}"


# clé : (genre, base de fichier, titre, prompt)
ENTREES = [
	# ── Monstres : gardiens (êtres uniques) ──
	("charon", "monstre", "charon", "Charon, maître du passage (I · Limbes)", _monstre(
		"de Charon, le nocher des morts (une seule créature, isolée) : un vieillard immense et décharné, à la longue "
		"barbe blanche et aux cheveux hirsutes, aux yeux cerclés de braise rougeoyante, vêtu de haillons gris, debout "
		"et menaçant, brandissant à deux mains une lourde rame de bois noir comme une arme, prêt à frapper.")),
	("minos", "monstre", "minos", "Minos, juge et répartiteur (II · Luxure)", _monstre(
		"de Minos, le juge des arrivants (une seule créature, isolée) : un démon colossal à l'allure de vieux roi, "
		"couronne de fer noir, barbe tressée, visage sévère et grondant, peau sombre, longue robe de juge en lambeaux ; "
		"une très longue queue de démon s'enroule plusieurs fois autour de son corps, comme pour compter ; une main "
		"levée pour prononcer une sentence.")),
	("ciacco", "monstre", "ciacco", "Ciacco, détenu maître du cercle (III · Gourmandise)", _monstre(
		"de Ciacco, détenu devenu maître de son cercle (une seule créature, isolée) : un homme énorme et bouffi, la "
		"peau blême ruisselante de pluie froide et couverte de fange, les yeux louches et rusés, un sourire de travers, "
		"une couronne grossière faite de couverts tordus sur la tête, un manteau de festin sale et trempé, une lourde "
		"louche de fer à la main comme un sceptre.")),
	("plutus", "monstre", "plutus", "Plutus, gardien des biens confisqués (IV · Avarice)", _monstre(
		"de Plutus, gardien des richesses confisquées (une seule créature, isolée) : un démon-loup bouffi, dressé sur "
		"ses pattes arrière, au pelage rêche et sombre, la gueule grande ouverte sur un hurlement furieux, la panse "
		"lourde, des chaînes chargées de clés et de cadenas pendues à son cou et à ses bras, une bourse crevée à la "
		"ceinture d'où ne tombe rien.")),
	("phlegyas", "monstre", "phlegyas", "Phlégyas, passeur du Styx (V · Colère)", _monstre(
		"de Phlégyas, le passeur des eaux noires (une seule créature, isolée) : un ancien roi géant, musculeux et "
		"furieux, la mâchoire serrée, les veines saillantes, une barbe noire en désordre, une couronne de bronze "
		"cabossée, un manteau de roi trempé de boue noire, tenant une longue perche de batelier ferrée comme une lance.")),
	("furie_alecto", "monstre", "furie_alecto", "Furie — Alecto, la colère qui dure (VI · Dité)", _monstre(
		"d'Alecto, l'une des trois Furies (une seule créature, isolée) : une femme ailée aux grandes ailes noires de "
		"chauve-souris, la peau grise tachée de sang sombre, une chevelure de serpents noirs et bronze qui sifflent, "
		"la bouche ouverte sur un cri de rage, tenant une torche de fer allumée, une tunique noire déchirée serrée à la "
		"taille par un serpent.", fond="vert vif")),
	("furie_megere", "monstre", "furie_megere", "Furie — Mégère, la malédiction de rancune (VI · Dité)", _monstre(
		"de Mégère, l'une des trois Furies (une seule créature, isolée) : une femme ailée aux grandes ailes noires de "
		"chauve-souris, la peau grise tachée de sang sombre, une chevelure de serpents noirs et bronze, le regard "
		"plein de haine et de jalousie, un doigt griffu pointé en avant pour maudire, l'autre main serrée sur un "
		"serpent, une tunique noire déchirée.", fond="vert vif")),
	("furie_tisiphone", "monstre", "furie_tisiphone", "Furie — Tisiphone, le fouet de garde (VI · Dité)", _monstre(
		"de Tisiphone, l'une des trois Furies (une seule créature, isolée) : une femme ailée aux grandes ailes noires "
		"de chauve-souris, la peau grise tachée de sang sombre, une chevelure de serpents noirs et bronze, l'air froid "
		"d'une gardienne de porte, un long fouet de serpents tressés déroulé à la main, un trousseau de clés de fer à "
		"la ceinture, une tunique noire déchirée.", fond="vert vif")),
	("geryon", "monstre", "geryon", "Géryon (VII · Violence)", _monstre(
		"de Géryon, le monstre de la fraude (une seule créature, isolée) : une créature colossale au visage d'homme "
		"juste, bienveillant et serein, aux deux pattes avant velues de fauve griffues jusqu'aux aisselles, au long "
		"corps de serpent couvert d'écailles peintes de nœuds et de cercles colorés, terminé par une queue de "
		"scorpion fourchue et venimeuse dressée au-dessus de lui.")),
	("malacoda", "monstre", "malacoda", "Malacoda, chef des Malebranche (VIII · Malebolge)", _monstre(
		"de Malacoda, chef des démons de la poix (une seule créature, isolée) : un démon noir et ailé, plus grand et "
		"plus massif que les autres, aux ailes pointues de chauve-souris, aux crocs saillants, une longue queue "
		"crochue, un sourire moqueur et faussement aimable, une main tendue comme pour indiquer un chemin, l'autre "
		"tenant un long harpon à crochet de fer.")),
	("antee", "monstre", "antee", "Antée, au dernier accès (IX · Cocyte)", _monstre(
		"d'Antée, le géant non enchaîné (une seule créature, isolée) : un géant immense et musculeux, torse nu, la "
		"peau tannée couverte de givre, une barbe épaisse prise de glace, une peau de lion jetée sur l'épaule, les "
		"pieds nus solidement plantés comme s'il puisait sa force dans la terre, les poings serrés, prêt à saisir.")),
	# ── Monstres : combats secondaires ──
	("malebranche", "monstre", "malebranche", "Malebranche (VIII et épreuve de chasse)", _monstre(
		"d'un Malebranche, démon subalterne de la fosse de poix (une seule créature, isolée) : un démon noir, maigre "
		"et nerveux, aux ailes pointues de chauve-souris, aux pieds légers et griffus, aux crocs acérés, au regard "
		"intelligent et sournois, accroupi en alerte, tenant un harpon à crochet de fer, une corde et un petit piège "
		"à mâchoires pendus à la ceinture.")),
	("ange_dechu", "monstre", "ange_dechu", "Ange déchu (VI · geôlier des portes)", _monstre(
		"d'un ange déchu, geôlier des portes d'une cité de fer (une seule créature, isolée) : un être grand et beau, "
		"au visage dur et fermé, aux grandes ailes aux plumes noircies et roussies comme par le feu, vêtu d'une "
		"armure de fer rouge sombre, une lance à la main et un bouclier rond sans emblème ; aucun halo, aucun symbole "
		"religieux.")),
	("lonza", "monstre", "lonza", "Lonza (II · corniches)", _monstre(
		"d'une lonza (une seule bête, isolée) : un félin léger et très agile, entre l'once et le lynx, au pelage "
		"clair couvert de taches sombres, au corps souple et élancé, en plein bond, la queue fouettant l'air, le "
		"regard aguicheur et cruel.")),
	("lion", "monstre", "lion_des_enfers", "Lion (VII · orée du désert de feu)", _monstre(
		"d'un lion des Enfers (une seule bête, isolée) : un lion énorme, la tête haute et orgueilleuse, la crinière "
		"sombre et hérissée, les flancs creusés par une faim enragée, la gueule entrouverte, s'avançant d'un pas lent "
		"et menaçant, le regard brûlant.")),  # lot 1 : « l'air tremble » → halo magenta dessiné
	("louve_maigre", "monstre", "louve_maigre", "Louve maigre (IV · entrepôt)", _monstre(
		"d'une louve maigre (une seule bête, isolée) : une louve d'une maigreur effrayante, chaque côte visible sous "
		"un pelage gris terne et clairsemé, les babines retroussées, les yeux brillants d'une envie insatiable, "
		"tête basse, rôdant.")),
	("chienne_noire", "monstre", "chienne_noire", "Chienne noire (VII · forêt des suicidés)", _monstre(
		"d'une chienne noire des Enfers (une seule bête, isolée) : une grande chienne de chasse au pelage noir de "
		"jais, efflanquée, affamée et rapide, lancée au galop, les crocs découverts, les yeux luisants comme des "
		"braises.", fond="vert vif")),

	# ── Cartes de combat ──
	("bm_cavite_du_malebranche", "battlemap", "cavite_du_malebranche", "Cavité du Malebranche (épreuve de chasse)", _carte(
		"d'une cavité volcanique sur les pentes d'un volcan d'Islande, en format paysage large 16:9, vue de dessus. "
		"Un sol de basalte noir et de cendre, fendu de fissures où rougeoie la lave refroidissante ; des corniches de "
		"roche surélevées sur les côtés, d'où l'on peut tirer ; des restes d'animaux déchiquetés, des griffures sur la "
		"roche, des résidus sombres et huileux ; deux pièges à mâchoires et une corde tendue dissimulés dans la "
		"cendre ; une entrée large en bas de la carte et un boyau étroit qui s'enfuit vers le haut.")),
	("bm_rive_de_l_acheron", "battlemap", "rive_de_l_acheron", "Rive de l'Achéron (I · Limbes, Charon)", _carte(
		f"de la rive d'un fleuve noir {ENFER}, en format paysage large 16:9, vue de dessus. Une plaine grise de sable "
		"et de dalles usées, sous une lumière blafarde sans source ; un large fleuve d'eau noire et profonde traverse "
		"toute la carte ; un ponton de bois vermoulu s'avance dans l'eau, avec une longue barque noire amarrée ; sur "
		"l'autre rive, le début d'une descente de pierre.")),
	("bm_corniches_du_vent", "battlemap", "corniches_du_vent", "Corniches du vent (II · Luxure, Lonza et Minos)", _carte(
		f"de corniches étroites accrochées à une falaise {ENFER}, en format paysage large 16:9, vue de dessus. Des "
		"vires de roche sombre, étroites et sinueuses, reliées par des passages, au-dessus d'un vide immense où "
		"tourbillonne une tempête de poussière et de vent ; une plateforme plus large au centre, où se tient un trône "
		"de pierre de juge ; un escalier taillé dans la falaise en haut de la carte.")),
	("bm_fange_de_la_gourmandise", "battlemap", "fange_de_la_gourmandise", "Fange de la gourmandise (III, goules)", _carte(
		f"d'une étendue de fange {ENFER}, en format paysage large 16:9, vue de dessus. Une boue épaisse, brune et "
		"noire, battue par une pluie froide, de la grêle et de la neige sale ; quelques îlots de terre sèche et de "
		"pierre plate répartis sur la carte ; des flaques plus profondes ; des restes de vaisselle brisée enfoncés "
		"dans la boue.")),
	("bm_salle_du_festin", "battlemap", "salle_du_festin", "Salle du festin (III, Ciacco)", _carte(
		f"d'une grande salle de festin {ENFER}, en format paysage large 16:9, vue de dessus. Un sol de dalles "
		"sales et humides ; de longues tables de bois aux plats et aux coupes vides, des bancs renversés ; au fond, "
		"une table haute sur une estrade ; une grande porte fermée dans le mur du fond ; l'eau de pluie qui goutte "
		"du plafond forme des flaques.")),
	("bm_arene_de_l_avarice", "battlemap", "arene_de_l_avarice", "Arène de l'avarice (IV, Louve maigre et Plutus)", _carte(
		f"d'une arène circulaire {ENFER}, en format paysage large 16:9, vue de dessus. Un sol de pierre grise "
		"partagé en deux par une large ligne tracée au sol ; d'énormes poids de pierre ronds, à demi roulés, laissant "
		"des sillons ; sur un côté, un entrepôt ouvert de biens confisqués : coffres fermés, sacs, piles d'objets "
		"précieux poussiéreux, étagères ; une pente qui descend en bas de la carte.")),
	("bm_passerelles_du_styx", "battlemap", "passerelles_du_styx", "Passerelles du Styx (V, démons guerriers et Phlégyas)", _carte(
		f"d'un marais noir {ENFER}, en format paysage large 16:9, vue de dessus. Une boue noire et profonde qui "
		"bouillonne par endroits ; des passerelles de planches et des rebords de pierre étroits qui se croisent "
		"au-dessus du marais ; un petit embarcadère ; dans un coin, le pied d'une tour de pierre où brûle un feu de "
		"signal.")),
	("bm_portes_de_dite", "battlemap", "portes_de_dite", "Portes de Dité (VI, anges déchus)", _carte(
		f"des portes d'une cité de fer rouge {ENFER}, en format paysage large 16:9, vue de dessus. Une grande "
		"muraille de fer rouge sombre traverse la carte, percée d'une porte massive à deux battants ; des escaliers "
		"montent au chemin de ronde ; devant la porte, une esplanade de pierre noire, des braseros ; derrière, le "
		"début des rues de la cité.")),
	("bm_tour_des_furies", "battlemap", "tour_des_furies", "Sommet de la tour des Furies (VI)", _carte(
		f"du sommet d'une tour ronde de fer rouge {ENFER}, en format paysage large 16:9, vue de dessus. Une large "
		"plateforme circulaire bordée de créneaux, un sol de dalles de fer rivetées et noircies, trois perchoirs de "
		"fer tordus, des chaînes et des fouets pendus, l'ouverture d'un escalier en colimaçon ; au-delà des "
		"créneaux, le vide et les toits rouges de la cité.")),
	("bm_champ_des_tombeaux", "battlemap", "champ_des_tombeaux", "Champ des tombeaux (VI)", _carte(
		f"d'un champ de tombeaux {ENFER}, en format paysage large 16:9, vue de dessus. Des rangées de grands "
		"tombeaux de pierre aux couvercles soulevés, d'où sortent des flammes ; des allées de terre brûlée entre "
		"eux ; une lueur orange partout ; au fond, une porte de fer dans un mur.")),
	("bm_rive_du_phlegethon", "battlemap", "rive_du_phlegethon", "Rive du Phlégéthon (VII, centaures)", _carte(
		f"de la rive d'un fleuve de sang bouillant {ENFER}, en format paysage large 16:9, vue de dessus. Un fleuve "
		"rouge sombre et fumant qui coule en arc de cercle, infranchissable ; une berge de roche brune avec des "
		"rochers épars et quelques arbres morts ; un gué de pierres plates à un endroit ; des traces de sabots dans "
		"la poussière.")),
	("bm_foret_des_suicides", "battlemap", "foret_des_suicides", "Forêt des suicidés (VII, harpies et chiennes noires)", _carte(
		f"d'une forêt de buissons noirs {ENFER}, en format paysage large 16:9, vue de dessus. Des arbres noirs, "
		"noueux et tordus, sans feuilles, couverts d'épines, aux branches brisées qui suintent un liquide sombre ; "
		"des fourrés épais et infranchissables ; des sentiers étroits de terre grise ; quelques nids de branches dans "
		"les arbres.")),
	("bm_desert_de_feu", "battlemap", "desert_de_feu", "Désert de feu et gouffre (VII, Lion et Géryon)", _carte(
		f"d'un désert de sable brûlant {ENFER}, en format paysage large 16:9, vue de dessus. Un sable ocre et "
		"rougeoyant sur lequel tombent lentement de larges flocons de feu ; quelques rochers noirs ; sur un bord de "
		"la carte, une falaise abrupte qui plonge dans un gouffre sombre et sans fond ; un ruisseau rouge qui se jette "
		"dans le gouffre.")),
	("bm_fosse_de_poix", "battlemap", "fosse_de_poix", "Fosse de poix (VIII, Malebranche et Malacoda)", _carte(
		f"d'une fosse de poix bouillante {ENFER}, en format paysage large 16:9, vue de dessus. Une fosse emplie de "
		"poix noire et brillante qui bouillonne ; des rives de pierre grise de part et d'autre ; un pont de pierre en "
		"arche qui la franchit ; un second pont effondré dont il ne reste que les piles ; des harpons et des crochets "
		"abandonnés sur les rives.")),
	("bm_fosse_des_serpents", "battlemap", "fosse_des_serpents", "Fosse des serpents (VIII, serpents géants)", _carte(
		f"d'une fosse grouillante de serpents {ENFER}, en format paysage large 16:9, vue de dessus. Le fond "
		"d'une fosse de pierre grise où grouillent d'innombrables serpents de toutes tailles, infranchissable ; des "
		"rives de pierre et des rochers ; un pont de pierre étroit qui traverse la fosse ; des recoins d'ombre.")),
	("bm_ponts_des_flammes", "battlemap", "ponts_des_flammes", "Ponts des flammes (VIII, conseillers fourbes)", _carte(
		f"de ponts de pierre au-dessus d'une fosse de flammes {ENFER}, en format paysage large 16:9, vue de dessus. "
		"Une fosse profonde où flottent des dizaines de flammes isolées qui se déplacent lentement ; deux ponts de "
		"pierre grise étroits qui se rejoignent sur une plateforme centrale ; des rives de pierre aux deux bouts ; "
		"une lueur orange qui monte du fond.")),
	("bm_bord_du_puits", "battlemap", "bord_du_puits_d_antee", "Bord du puits des Géants (IX, Antée)", _carte(
		f"du bord d'un puits immense dans un monde de glace {ENFER}, en format paysage large 16:9, vue de dessus. "
		"Une margelle de roche couverte de givre et de glace glissante, assez vaste pour un géant ; au centre de la "
		"carte, l'ouverture béante et noire du puits ; autour, d'énormes anneaux de fer scellés dans la roche, d'où "
		"pendent des chaînes brisées ; des congères et des blocs de glace épars.")),

	# ── Lieux ──
	("lieu_commanderie", "lieu", "commanderie_de_reykjavik", "Commanderie des Templiers de Reykjavik", _lieu(
		"de la commanderie d'un ordre de chevaliers gardiens, dans une cité portuaire d'Islande, vue de l'intérieur, "
		"en format paysage large 16:9. Une grande salle de pierre sombre et de bois, des poutres noircies, une "
		"cheminée où brûle un feu de tourbe, des cartes de l'île épinglées aux murs, des étagères d'archives et de "
		"registres scellés, des caisses de ravitaillement marquées d'un sceau ; par les fenêtres étroites, des "
		f"fumées de sources chaudes montent au-dessus des toits. Des officiers et des scribes au travail : {FOULE} "
		f"{SANS_CROIX}")),
	("lieu_forteresse", "lieu", "forteresse_de_l_hekla", "Forteresse templière de l'Hekla (vue extérieure)", _lieu(
		"d'une forteresse de pierre noire bâtie sur les pentes d'un volcan, au sud de l'Islande, vue de l'extérieur, "
		"en format paysage large 16:9. De hauts murs épais de basalte, des tours rondes trapues, une seule porte "
		"bardée de fer, une route de cendre qui y monte à travers des champs de lave couverts de mousse et de neige ; "
		"derrière, le cône du volcan fume sous un ciel bas et gris ; des panaches de vapeur sortent du sol. La "
		"forteresse semble faite pour garder quelque chose à l'intérieur plutôt que pour se défendre du dehors. "
		"Aucun personnage.")),
	("lieu_cour", "lieu", "cour_de_la_forteresse_de_l_hekla", "Cour de la forteresse", _lieu(
		"de la cour intérieure d'une forteresse de basalte noir sur les pentes d'un volcan d'Islande, en format "
		"paysage large 16:9. Des pavés de pierre sombre saupoudrés de cendre, un puits, des râteliers d'armes, des "
		"chariots de ravitaillement, une forge fumante sous un appentis ; au fond, une grande porte de fer renforcée "
		"qui mène vers l'intérieur de la montagne ; ciel bas et fumée du volcan. Des gardes s'entraînent ou "
		f"montent la garde : {FOULE} {SANS_CROIX}")),
	("lieu_cellules", "lieu", "cellules_de_la_forteresse_de_l_hekla", "Cellules de la forteresse (le démon captif)", _lieu(
		"d'un couloir de cellules creusé dans la roche volcanique, sous une forteresse, en format paysage large 16:9. "
		"Des grilles de fer épaisses gravées de motifs de protection géométriques, des torches, un poste de garde "
		"avec une table, un registre fermé et une lanterne ; dans la dernière cellule, derrière la grille, une "
		"silhouette accroupie dans l'ombre dont on ne voit que deux yeux de braise ; la roche est tiède et suinte. "
		"Aucun autre personnage.")),
	("lieu_seuil", "lieu", "seuil_de_l_hekla", "Le seuil de l'Hekla", _lieu(
		"d'un gouffre au fond d'une immense grotte volcanique, sous une forteresse, en format paysage large 16:9. "
		"Une muraille circulaire de basalte encercle l'ouverture du gouffre, d'où monte une lueur rouge et une "
		"chaleur qui fait trembler l'air ; au-dessus, accrochées à la paroi, des chaires de pierre où des magiciens "
		"peuvent se tenir en cas de déversement ; une seule porte de fer dans la muraille ; des instruments de "
		"mesure de cuivre et une table d'étude posés à l'écart. Aucun personnage.")),
	("lieu_haut_enfer", "lieu", "entree_du_haut_enfer", "Entrée du Haut-Enfer (donjon 1)", _lieu(
		f"d'un escalier de pierre immense qui descend {ENFER}, en format paysage large 16:9. Les marches usées "
		"descendent vers une plaine grise baignée d'une lumière blafarde sans source ; au loin, un fleuve noir et un "
		"château à sept murs que personne n'habite ; des ombres immobiles assises qui ne lèvent pas les yeux. "
		"Aucun personnage vivant.")),
	("lieu_porte_du_festin", "lieu", "porte_du_festin", "Porte du festin (seuil du donjon 2)", _lieu(
		f"d'une porte ancienne au fond d'une salle de festin abandonnée {ENFER}, en format paysage large 16:9. La "
		"porte de pierre est ouverte sur une pente qui descend vers des eaux noires ; autour de l'encadrement, des "
		"pierres très anciennes gravées de motifs géométriques luisent faiblement, comme une structure faite pour "
		"tenir le voyageur debout ; derrière, les tables vides du festin sous la pluie. Aucun personnage.")),
	("lieu_porte_des_tombeaux", "lieu", "porte_des_tombeaux", "Porte des tombeaux (seuil du donjon 3)", _lieu(
		f"d'une porte de fer au fond d'un champ de tombeaux enflammés {ENFER}, en format paysage large 16:9. La "
		"porte est ouverte dans un mur de fer rouge ; autour, des pierres très anciennes gravées de motifs "
		"géométriques luisent faiblement ; derrière elle, un chemin descend vers une lueur rouge et la rumeur d'un "
		"fleuve bouillant ; au premier plan, des tombeaux ouverts d'où sortent des flammes. Aucun personnage.")),
	("lieu_puits_des_geants", "lieu", "puits_des_geants", "Puits des Géants (seuil du donjon 4)", _lieu(
		f"d'un puits immense entouré de géants enchaînés {ENFER}, en format paysage large 16:9. Autour d'un trou "
		"noir et sans fond, d'immenses figures de géants se dressent comme des tours dans la brume, enchaînées à la "
		"roche, l'une avec une multitude de bras ; un vent glacé monte du puits ; du givre couvre la margelle ; "
		"autour de l'accès, des pierres très anciennes gravées de motifs géométriques luisent faiblement. Aucun "
		"autre personnage.")),
	("lieu_cocyte", "lieu", "coeur_du_cocyte", "Le cœur du Cocyte (Lucifer)", _lieu(
		f"d'un lac gelé immense {ENFER}, en format paysage large 16:9. Une étendue de glace bleutée et lisse, sous "
		"une obscurité froide ; dans la glace, des silhouettes prises jusqu'au cou, de plus en plus profondément à "
		"mesure qu'on avance ; au centre, très loin, une figure colossale prisonnière de la glace jusqu'à la "
		"poitrine, aux immenses ailes immobiles et givrées, d'où vient un vent glacé ; des chaînes énormes la "
		"retiennent. Scène calme, presque immobile.")),

	# ── Portraits ──
	("pnj_gizurr", "portrait", "commandeur_elfe_m_forteresse_de_l_hekla", "Gizurr Þórvaldsson, commandeur", _portrait(
		"d'un personnage de fantasy médiévale, format paysage large 16:9. Un elfe aux oreilles longues et pointues, "
		"d'âge mûr, grand et sec, les cheveux d'un blond cendré tirés en arrière, une cicatrice pâle sur la "
		"mâchoire, le regard froid et pragmatique, commandeur d'une forteresse de chevaliers gardiens. Il se tient "
		"légèrement décalé du centre, les mains posées sur le pommeau d'une épée plantée devant lui, et regarde "
		"droit vers le spectateur, sans hostilité ni chaleur. Tenue : armure de plaques sombre, manteau de laine "
		"grise doublé de fourrure, tabard à l'emblème de tour et de flamme, sans aucune croix ni symbole religieux. "
		"Décor : un mur de basalte noir, une meurtrière par laquelle on voit fumer un volcan.")),
	("pnj_demon_captif", "portrait", "demon_captif_forteresse_de_l_hekla", "Le démon captif", _portrait(
		"d'une créature de fantasy médiévale, format paysage large 16:9. Un démon mineur de taille d'homme, maigre, "
		"à la peau rouge sombre et craquelée comme de la lave refroidie, aux petites cornes recourbées, aux yeux de "
		"braise, au sourire trop large et trop aimable, les poignets pris dans des fers gravés de motifs de "
		"protection. Il est assis derrière les barreaux d'une cellule, légèrement décalé du centre, penché en avant "
		"comme pour confier un secret, et regarde le spectateur d'un air entendu. Décor : une cellule creusée dans "
		"la roche volcanique, une torche, une grille de fer épaisse.")),
	("pnj_lucifer", "portrait", "lucifer_cocyte", "Lucifer, captif du Cocyte", _portrait(
		# Lot 1 : « beauté abîmée », « visage las » → un vieil homme fatigué (Auteur, 28/11 : il lui faut de la
		# dignité ; prisonnier presque par sa propre volonté, sans qu'on comprenne pourquoi). Même être que dans
		# towns/coeur_du_cocyte02.jpg, JOINT en référence (REFERENCES) : l'Auteur veut les deux images liées.
		"d'une figure mythique de fantasy médiévale, format paysage large 16:9. C'est le même être que la figure "
		"colossale enchaînée au centre de l'image jointe, vu de plus près : mêmes cornes recourbées, même armure "
		"sombre, mêmes immenses ailes membraneuses prises de glace et de stalactites, mêmes chaînes rouillées tendues "
		"autour de lui, même lac gelé dans la même grotte bleutée ; on ne reprend que lui, pas les détenus ni le "
		"voyageur. L'ancien ange de lumière, d'une dignité souveraine : un visage sans âge, ni jeune ni vieux, sans "
		"aucune ride, aux traits nobles et réguliers, bien éclairé et lisible, des yeux pâles et lumineux qui semblent "
		"tout savoir. Il est pris dans la glace jusqu'aux hanches, les bras croisés, le dos droit, la tête haute, le "
		"port d'un roi sur son trône ; les chaînes pèsent sur lui sans le faire plier, comme s'il aurait pu les "
		"rompre et avait choisi de ne pas le faire. Il regarde droit vers le spectateur avec une sérénité grave, une "
		"ombre de sourire, sans menace ni supplication. Aucun halo, aucun symbole religieux.")),
	("pnj_vieillard_des_limbes", "portrait", "vieillard_des_limbes", "Le vieillard des Limbes", _portrait(
		"d'un personnage de fantasy médiévale, format paysage large 16:9. Un vieillard d'une maigreur extrême, sans "
		"âge, dont on ne saurait dire de quelle lignée il est, la peau grise comme de la cendre, une longue barbe "
		"blanche emmêlée, le regard perdu de quelqu'un qui a oublié depuis quand il attend. Il est assis sur une "
		"pierre, légèrement décalé du centre, les mains jointes sur un bâton, et lève les yeux vers le spectateur "
		"avec une curiosité lente. Tenue : une robe grise usée jusqu'à la trame. Décor : une plaine grise sous une "
		"lumière sans source, des ombres assises au loin.")),
	("pnj_femme_du_tombeau", "portrait", "femme_du_tombeau_dite", "La femme du tombeau", _portrait(
		"d'un personnage de fantasy médiévale, format paysage large 16:9. Une femme d'âge incertain, couverte de "
		"cendres de la tête aux pieds, les cheveux gris de poussière, le visage digne et absent, dont on ne saurait "
		"dire de quelle lignée elle est. Elle est assise sur le bord d'un tombeau de pierre ouvert d'où montent des "
		"flammes basses, légèrement décalée du centre, et regarde le spectateur comme si elle cherchait à se "
		"souvenir de lui. Tenue : une longue robe autrefois riche, brûlée par endroits. Décor : un champ de "
		"tombeaux ouverts et enflammés, une lueur orange.")),
	("pnj_prisonnier_cornu", "portrait", "prisonnier_cornu_malebolge", "Le prisonnier cornu", _portrait(
		"d'un personnage de fantasy médiévale, format paysage large 16:9. Un prisonnier aux deux cornes de bélier "
		"brisées, le corps sec et marqué de vieilles cicatrices, un collier de fer au cou relié à une chaîne, le "
		"regard ironique et lucide. Il est adossé à une paroi de pierre grise, légèrement décalé du centre, et "
		"regarde le spectateur avec un demi-sourire, comme s'il en savait plus qu'il ne le dit. Tenue : un pagne de "
		"toile sale. Décor : la rive d'une fosse de pierre grise, un pont en arche au loin, une lueur orange.")),
	("pnj_gardien_enchaine", "portrait", "gardien_enchaine_malebolge", "Le gardien enchaîné", _portrait(
		"d'un personnage de fantasy médiévale, format paysage large 16:9. Un ancien gardien en armure ternie et "
		"cabossée, d'une haute stature, aux grandes ailes de plumes brisées et pendantes, enchaîné aux poignets et "
		"aux chevilles, le visage fier et fermé, les yeux baissés puis relevés vers le spectateur avec défi. Il est "
		"agenouillé, légèrement décalé du centre. Aucun halo, aucun symbole religieux. Décor : une paroi de pierre "
		"grise où sont scellés des anneaux de fer, une fosse sombre derrière lui.")),
]


# Image jointe à la requête (prompts_images § 0.5 : pour REPRODUIRE ce sujet, jamais pour un style), chemin
# relatif à templates/resources/.
REFERENCES = {"pnj_lucifer": "towns/coeur_du_cocyte02.jpg"}


def entrees():
	return {cle: {"genre": g, "base": b, "titre": t, "prompt": p,
				  **({"reference": REFERENCES[cle]} if cle in REFERENCES else {})}
			for cle, g, b, t, p in ENTREES}


def preparer():
	os.makedirs(DOSSIER, exist_ok=True)
	e = entrees()
	assert len(e) == len(ENTREES), "clé en double"
	assert all(v["prompt"].startswith("Réalise l'image") for v in e.values())
	assert all(v["prompt"].endswith(BATTLEMAP) for v in e.values() if v["genre"] == "battlemap")
	with open(PROMPTS, "w", encoding="utf-8") as f:
		json.dump(e, f, ensure_ascii=False, indent="\t")
	lignes = [f"# Images de l'arc de l'Hekla — {len(e)} prompts (Gemini)", "",
			  "Généré par `dev/gen_images_hekla.py preparer`. Règles : `docs/prompts_images.md`.", ""]
	for genre, titre in (("monstre", "Monstres (1:1, fond uni à détourer)"), ("battlemap", "Cartes de combat (16:9)"),
						 ("lieu", "Lieux (16:9)"), ("portrait", "Portraits (16:9)")):
		lignes += [f"## {titre}", ""]
		for cle, v in e.items():
			if v["genre"] == genre:
				lignes += [f"**`{v['base']}` — {v['titre']}** (clé `{cle}`)", "```", v["prompt"], "```", ""]
	with open(PROMPTS_MD, "w", encoding="utf-8") as f:
		f.write("\n".join(lignes))
	print(f"{len(e)} prompts → {os.path.relpath(PROMPTS, RACINE)} (+ prompts.md)")


def _prompts():
	if not os.path.exists(PROMPTS):
		raise SystemExit("ERREUR : lancer d'abord `preparer`.")
	with open(PROMPTS, encoding="utf-8") as f:
		return json.load(f)


def _manifeste(nouveau=None):
	os.makedirs(DOSSIER, exist_ok=True)
	if nouveau is not None:
		with open(MANIFESTE, "w", encoding="utf-8") as f:
			json.dump(nouveau, f, ensure_ascii=False, indent="\t")
		return nouveau
	if os.path.exists(MANIFESTE):
		with open(MANIFESTE, encoding="utf-8") as f:
			return json.load(f)
	return _manifeste({"modele": magasins.MODELE_GEMINI, "batch": None, "lots": [], "images": {}, "echecs": []})


def nom_transparent(base):
	"""`<base>_transparent.webp`, sinon la première variante numérotée libre (`.png` compte comme pris)."""
	dossier = CIBLES["monstre"]

	def pris(nom):
		return any(os.path.exists(os.path.join(dossier, nom + ext)) for ext in (".webp", ".png", ".gif"))
	nom, n = f"{base}_transparent", 0
	while pris(nom):
		n += 1
		nom = f"{base}_transparent{n:02d}"
	return nom + ".webp"


def requete(v):
	ref = v.get("reference")
	r = magasins.requete_gemini(v["prompt"], magasins._portrait_b64(os.path.join(RES, ref)) if ref else None)
	r["generationConfig"]["imageConfig"]["aspectRatio"] = RATIOS[v["genre"]]
	return r


def _restantes(man, prompts):
	return {c: v for c, v in prompts.items() if c not in man["images"]}


def compter():
	man, prompts = _manifeste(), _prompts()
	rest = _restantes(man, prompts)
	unit = magasins.EUR_PAR_IMAGE_INTERACTIF * magasins.REMISE_BATCH
	par_genre = {}
	for v in rest.values():
		par_genre[v["genre"]] = par_genre.get(v["genre"], 0) + 1
	print(f"{len(rest)}/{len(prompts)} image(s) à générer {par_genre} ; en lot ≈ {len(rest) * unit:.2f} €"
		  f" ({unit:.3f} €/image)")


def _garder_echec(cle, octets, ext, motif, man):
	os.makedirs(ECHECS, exist_ok=True)
	n = sum(1 for e in man["echecs"] if e["cle"] == cle) + 1
	nom = f"{cle}_echec{n:02d}{ext}"
	with open(os.path.join(ECHECS, nom), "wb") as f:
		f.write(octets)
	man["echecs"].append({"cle": cle, "fichier": f"dev/batch/hekla/echecs/{nom}", "motif": motif, "lot": man["batch"]})


def _recuperer(man):
	prompts = _prompts()
	os.makedirs(BRUTES, exist_ok=True)
	ecrites, erreurs = 0, []
	for cle, part, r in magasins.reponses_lot(man["batch"]):
		if cle not in prompts or cle in man["images"]:
			continue
		v = prompts[cle]
		if not part:
			motif = json.dumps(r.get("error") or r, ensure_ascii=False)[:300]
			man["echecs"].append({"cle": cle, "fichier": None, "motif": motif, "lot": man["batch"]})
			erreurs.append(f"{cle} : {motif}")
			continue
		octets = base64.b64decode(part["inlineData"]["data"])
		ext = ".jpg" if "jpeg" in part["inlineData"].get("mimeType", "") else ".png"
		rejet = magasins.image_degeneree(*magasins._mesures(octets))
		if rejet:
			_garder_echec(cle, octets, ext, f"image {rejet}", man)
			erreurs.append(f"{cle} : image {rejet} (gardée dans echecs/)")
			continue
		if v["genre"] == "monstre":
			brute = os.path.join(BRUTES, cle + ext)
			with open(brute, "wb") as f:
				f.write(octets)
			nom = nom_transparent(v["base"])
			try:
				fond, taille, part_fond = detourer(brute, os.path.join(CIBLES["monstre"], nom))
			except Exception as exc:  # noqa: BLE001 — l'image brute reste, la clé repart
				_garder_echec(cle, octets, ext, f"détourage : {exc}", man)
				erreurs.append(f"{cle} : détourage impossible ({exc})")
				continue
			print(f"  ✓ {nom} : fond {tuple(round(c) for c in fond)}, {taille[0]}x{taille[1]}, {part_fond:.0%} retiré")
		else:
			dossier = CIBLES[v["genre"]]
			nom = magasins.nom_libre(dossier, v["base"], ext)
			with open(os.path.join(dossier, nom), "wb") as f:
				f.write(octets)
			print(f"  ✓ {v['genre']} → {nom}")
		man["images"][cle] = nom
		ecrites += 1
	man["lots"].append(man["batch"])
	man["batch"] = None
	_manifeste(man)
	print(f"{ecrites} image(s) écrite(s), {len(erreurs)} échec(s), {len(man['images'])}/{len(prompts)} au total")
	for err in erreurs:
		print("  ✗", err)


def avancer():
	man = _manifeste()
	if man.get("batch"):
		statut = magasins.statut_lot(man["batch"])
		meta = statut.get("metadata") or statut
		etat = meta.get("state")
		print(man["batch"], "→", etat, "|", meta.get("batchStats"))
		if etat in magasins.ETATS_ECHOUES:
			print("⚠ Lot en échec : ses requêtes repartiront au prochain `avancer`.")
			man["lots"].append(man["batch"])
			man["batch"] = None
			_manifeste(man)
			return
		if etat not in magasins.ETATS_REUSSIS and not statut.get("done"):
			print("En cours : rejouer `avancer` plus tard.")
			return
		_recuperer(man)
		return  # bilan d'abord : le lot suivant (échecs) part au prochain `avancer`
	restantes = _restantes(man, _prompts())
	if not restantes:
		print("Terminé : toutes les images sont générées.")
		return
	with open(REQUETES, "w", encoding="utf-8") as f:
		for cle, v in restantes.items():
			f.write(json.dumps({"key": cle, "request": requete(v)}, ensure_ascii=False) + "\n")
	man["batch"] = magasins.soumettre_lot(REQUETES, man["modele"], f"images-hekla-{len(man['lots']) + 1}")
	_manifeste(man)
	print(f"Lot soumis ({len(restantes)} requête(s)) :", man["batch"])


def refaire(cles):
	man, prompts = _manifeste(), _prompts()
	inconnues = [c for c in cles if c not in prompts]
	if inconnues:
		raise SystemExit(f"ERREUR : clé(s) inconnue(s) : {', '.join(inconnues)}")
	if man.get("batch"):
		raise SystemExit("ERREUR : un lot est en cours ; le terminer d'abord (`avancer`).")
	for c in cles:
		ancien = man["images"].pop(c, None)
		if ancien:
			man.setdefault("remplacees", []).append({"cle": c, "fichier": ancien})
	_manifeste(man)
	print(f"{len(cles)} clé(s) à refaire : {', '.join(cles)}")


def main():
	sys.stdout.reconfigure(encoding="utf-8")
	if len(sys.argv) == 3 and sys.argv[1] == "refaire":
		return refaire([c.strip() for c in sys.argv[2].split(",") if c.strip()])
	actions = {"preparer": preparer, "compter": compter, "avancer": avancer}
	if len(sys.argv) != 2 or sys.argv[1] not in actions:
		raise SystemExit("Usage : gen_images_hekla.py preparer|compter|avancer|refaire <clé,clé…>")
	actions[sys.argv[1]]()


if __name__ == "__main__":
	main()

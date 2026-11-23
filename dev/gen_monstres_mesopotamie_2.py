#!/usr/bin/env python
# dev/gen_monstres_mesopotamie_2.py
# Bestiaire de Mésopotamie, second lot (demande du 23/11/2026) : les créatures des mythes
# mésopotamiens absentes après le lot du 19/11 (gen_monstres_mesopotamie_japon.py).
#   - 16 espèces placées en zone (région `afrique_du_nord`, Levant compris, faute de région
#     Mésopotamie — même parti que le premier lot) :
#       les onze de Tiamat qui manquaient : kusarikku, bashmu, ushumgallu, lahmu, uridimmu, kulullu,
#       umu_dabrutu ; anzu, urmahlullu ; esprits et démons : lilu, lilitu (et l'ardat-lilî), gallu,
#       utukku, etemmu, rabisu, alu ; les Sebitti ;
#   - 5 êtres uniques, boss au bestiaire seul (même règle que Kyūbi, Ladon, Orochi) : humbaba,
#     taureau_celeste (Gugalanna), asag, labbu, mushmahhu.
# Choix de l'utilisateur (questionnaire du 23/11) : uniques en boss non placés ; Anzû espèce,
# Mušmaḫḫu boss ; Sebitti en espèce, Namtar exclu (puissance divine, comme Tiamat et Kingu) ;
# rencontres en afrique_du_nord. Aucun tag `demon` sur les esprits placés (interdit en zone,
# gen_defauts_zones_biomes.TAGS_INTERDITS), comme Lamashtu. Les guerriers de pierre d'Asag ne sont
# pas une espèce : le golem de pierre existe déjà, la description d'Asag les cite.
#
# MÊME MOTEUR que dev/gen_monstres_legendes.py (globales remplacées par `installer()`), lignes
# ajoutées aux tables exhaustives (`gen_jetons_especes`, `gen_genres_especes`,
# `gen_equipement_humanoides`, `gen_capacites_monstres`) : elles échouent tant que l'import n'est
# pas fait et qu'un dump FRAIS ne l'a pas relu.
#
# Usage : python dev/gen_monstres_mesopotamie_2.py [--dump jsons/telluris-dump-….json] [--prompts]
# Sortie : jsons/monstres_mesopotamie_2_a_importer.json

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_monstres_legendes as moteur  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

SORTIE = os.path.join(moteur.RACINE, "jsons", "monstres_mesopotamie_2_a_importer.json")

# Même forme que gen_monstres_legendes.NOUVELLES ; _attrs = V, F, R, Ag, Vol, Int, Cha, Ch.
NOUVELLES = {
	# ── Les onze de Tiamat ──
	"kusarikku": {
		"nom": "Kusarikku",
		"description": "Homme jusqu'à la ceinture, taureau en dessous : torse et visage d'homme barbu, "
					   "cornes et oreilles de bison, jambes terminées en sabots fendus. Les sceaux et les "
					   "bas-reliefs le montrent par paires aux portes, tenant une hampe ou un montant. Les "
					   "récits en font l'un des onze que Tiamat enfanta, que Marduk vainquit puis rangea "
					   "parmi les gardiens ; ceux qui veillent encore sur des seuils oubliés ne demandent "
					   "pas qui l'on est.",
		"base_attributes": _attrs((5, 5), (55, 75), (55, 75), (25, 40), (45, 60), (20, 35), (5, 20), (15, 30)),
		"tags": ["monstre", "hybride", "gardien", "guerrier", "humanoide"],
		"butin": ("carcasse", [180, 260], "peu_commun"),
		"son": "bete",
		"visuel": "homme-taureau debout, torse humain musclé et visage d'homme barbu aux boucles "
				  "régulières, cornes et oreilles de bison, bas du corps de taureau au pelage brun sur "
				  "jambes terminées en sabots fendus, longue queue à touffe, pagne bleu et rouge, une "
				  "longue lance dressée à la main ; posture de garde frontale",
		"fond": "bleu vif",
	},
	"bashmu": {
		"nom": "Bašmu",
		"description": "Serpent venimeux à cornes, long comme deux hommes, dressé sur deux pattes avant "
					   "griffues. Il compte parmi les onze de Tiamat : « le serpent venimeux », disent les "
					   "tablettes, dont le venin court plus vite que le sang. On le croise près des puits et "
					   "des oasis qu'il garde comme s'ils lui appartenaient ; nul ne sait de qui il tient "
					   "ce droit.",
		"base_attributes": _attrs((6, 6), (40, 60), (40, 55), (35, 50), (35, 50), (10, 20), (0, 0), (20, 35)),
		"tags": ["monstre", "reptile", "venin", "predateur"],
		"butin": ("carcasse", [150, 250], "peu_commun"),
		"son": "bete",
		"visuel": "grand serpent aux écailles ocre et noires, deux cornes recourbées sur la tête, deux "
				  "pattes avant griffues qui le dressent à demi, gueule ouverte sur des crocs dégoulinant "
				  "de venin, collerette d'écailles hérissées",
		"fond": "bleu vif",
	},
	"ushumgallu": {
		"nom": "Ušumgallu",
		"description": "« Le grand dragon » : serpent colossal à tête et à pattes de lion, la gueule "
					   "pleine d'un venin qui brûle comme de la poix. Les rois se faisaient appeler de son "
					   "nom pour dire qu'aucun ennemi ne leur tenait tête. Tiamat en enfanta plusieurs, "
					   "disent les récits ; on ignore combien survécurent à Marduk, et ceux qui hantent les "
					   "ruines ne se laissent pas compter.",
		"base_attributes": _attrs((7, 9), (60, 90), (60, 85), (30, 50), (55, 80), (25, 40), (0, 0), (30, 50)),
		"tags": ["monstre", "draconique", "predateur", "terreur", "venin"],
		"butin": ("carcasse", [800, 1200], "rare"),
		"son": "dragon",
		"visuel": "dragon-serpent colossal sans ailes, long corps couvert d'écailles brun doré, tête de "
				  "lion massive à crinière d'écailles et crocs énormes, quatre pattes de lion griffues, "
				  "bave verdâtre fumante aux lèvres, queue de serpent enroulée",
		"fond": "magenta",
	},
	"lahmu": {
		"nom": "Laḫmu",
		"description": "« Le Chevelu » : homme nu et trapu, ceint d'une écharpe rouge, la chevelure "
					   "partagée en six boucles qui tombent jusqu'aux épaules. Il fut l'un des onze de "
					   "Tiamat, puis servit Enki aux portes de l'Apsû, l'océan d'eau douce sous la terre. "
					   "Ses figurines, enterrées sous le seuil des maisons, en éloignaient le mal ; ceux "
					   "qu'on rencontre aux sources ne disent jamais ce qu'ils y gardent.",
		"base_attributes": _attrs((5, 5), (40, 55), (45, 60), (30, 45), (45, 60), (30, 45), (15, 30), (20, 35)),
		"tags": ["monstre", "gardien", "humanoide", "magique"],
		"butin": ("carcasse", [70, 100], "peu_commun"),
		"son": "ogre",
		"visuel": "homme trapu et musclé, nu à l'exception d'une écharpe rouge nouée en ceinture, "
				  "barbe longue et chevelure partagée en six grosses boucles symétriques, yeux grands "
				  "ouverts, un bâton de bois tenu à deux mains comme un montant de porte",
		"fond": "bleu vif",
	},
	"uridimmu": {
		"nom": "Uridimmu",
		"description": "« Le chien enragé » : torse d'homme, tête et pattes de lion ou de chien, il se "
					   "tient debout et brandit un bâton surmonté d'un croissant. Tiamat l'enfanta pour sa "
					   "guerre contre les dieux ; Marduk en fit ensuite un gardien. Ceux qui rôdent encore "
					   "n'en ont gardé que la rage, et chargent dès qu'on les regarde.",
		"base_attributes": _attrs((6, 6), (45, 65), (40, 55), (40, 55), (40, 55), (15, 30), (0, 10), (15, 30)),
		"tags": ["monstre", "hybride", "gardien", "guerrier", "humanoide"],
		"butin": ("carcasse", [90, 140], "peu_commun"),
		"son": "loup",
		"visuel": "guerrier hybride debout, corps humain musclé, tête de molosse à crinière de lion, "
				  "babines retroussées sur des crocs, jambes de fauve griffues, pagne frangé, une masse "
				  "surmontée d'un croissant de métal levée à la main ; posture de charge",
		"fond": "bleu vif",
	},
	"kulullu": {
		"nom": "Kulullû",
		"description": "Homme-poisson : buste et tête d'homme barbu, le reste du corps en poisson couvert "
					   "d'écailles. Il compte parmi les onze de Tiamat, et sert depuis le dieu des eaux "
					   "douces ; sa compagne, la kuliltu, lui ressemble. Il remonte les fleuves et les "
					   "canaux, et s'en prend à qui trouble l'eau qu'il garde ; certains le confondent "
					   "avec les Sages venus des eaux, d'autres jurent qu'il n'en est que l'ombre.",
		"base_attributes": _attrs((5, 5), (35, 50), (40, 55), (35, 50), (40, 55), (25, 40), (10, 25), (20, 35)),
		"tags": ["monstre", "hybride", "aquatique", "gardien", "humanoide"],
		"butin": ("carcasse", [80, 120], "peu_commun"),
		"son": "visqueux",
		"visuel": "homme-poisson, torse et bras d'homme barbu aux boucles tressées, coiffe cylindrique, "
				  "bas du corps en longue queue de poisson aux écailles argent et vert, nageoire caudale "
				  "large, un trident tenu dans une main ; corps ruisselant d'eau",
		"fond": "magenta",
	},
	"umu_dabrutu": {
		"nom": "Ūmū dabrūtu",
		"description": "« Les tempêtes féroces » : des vents qui ont un visage, nés de Tiamat pour sa "
					   "guerre. Ils arrivent en hurlant, déracinent les palmiers, arrachent les toits et "
					   "aveuglent de sable ceux qui ne se sont pas abrités. Marduk les aurait liés à son "
					   "char ; ceux qui soufflent encore sur le désert semblent n'obéir à personne.",
		"base_attributes": _attrs((8, 8), (35, 50), (25, 40), (45, 65), (45, 65), (15, 30), (0, 0), (20, 35)),
		"tags": ["esprit", "incorporel", "vol", "magique", "terreur"],
		"butin": ("residu", 2.0, "peu_commun"),
		"son": "spectre",
		"visuel": "tourbillon de sable et de vent brun doré à forme vaguement humaine, visage furieux "
				  "à la bouche hurlante esquissé dans la poussière, bras de vent étirés en lanières, "
				  "éclairs fins crépitant à l'intérieur, débris de feuilles de palmier emportés",
		"fond": "bleu vif",
	},
	# ── Monstres des récits ──
	"anzu": {
		"nom": "Anzû",
		"description": "Aigle immense à tête de lion, dont les battements d'ailes lèvent les tempêtes et "
					   "dont le cri fait trembler les montagnes. Le récit dit qu'il vola les Tablettes des "
					   "Destinées au dieu Enlil et que Ninurta l'abattit au fond des monts ; d'autres "
					   "tablettes en font un oiseau sacré. Il en reste, perchés dans les cèdres des "
					   "hauteurs, et personne ne sait ce qu'ils gardent sous leurs serres.",
		"base_attributes": _attrs((14, 16), (55, 80), (50, 70), (40, 60), (50, 70), (25, 40), (0, 0), (25, 40)),
		"tags": ["monstre", "hybride", "vol", "predateur", "terreur"],
		"butin": ("carcasse", [400, 600], "rare"),
		"son": "bete",
		"visuel": "aigle gigantesque à tête de lion rugissant, crinière fauve, grandes ailes déployées "
				  "aux plumes brun sombre et or, serres énormes, queue d'aigle en éventail, éclairs et "
				  "nuées sous les ailes ; il est en vol",
		"fond": "magenta",
	},
	"urmahlullu": {
		"nom": "Urmaḫlullû",
		"description": "« L'homme-lion » : torse d'homme sur un corps de lion, comme un centaure de fauve. "
					   "On sculptait sa figure à l'entrée des pièces que le mal guette le plus, la salle "
					   "d'eau et les latrines comprises. Ceux qui se sont éveillés gardent encore leur "
					   "porte, et un seuil sans maison ne les en détourne pas.",
		"base_attributes": _attrs((6, 6), (45, 65), (45, 60), (35, 50), (40, 55), (20, 35), (5, 20), (15, 30)),
		"tags": ["monstre", "hybride", "gardien"],
		"butin": ("carcasse", [150, 220], "peu_commun"),
		"son": "bete",
		"visuel": "homme-lion à la manière d'un centaure, torse humain barbu musclé aux cheveux bouclés "
				  "et coiffe cylindrique, soudé au corps d'un lion au pelage fauve, quatre pattes "
				  "griffues, queue à touffe, une main levée en geste de garde",
		"fond": "bleu vif",
	},
	# ── Esprits et démons ──
	"lilu": {
		"nom": "Lilû",
		"description": "Démon-vent de la nuit, qui entre par les fenêtres avec la brise et visite les "
					   "dormeuses. Les tablettes de conjuration le nomment avec ses sœurs, la lilītu et "
					   "l'ardat-lilî, et le disent né d'un homme mort sans avoir pris femme. Il charme, "
					   "trouble les rêves, puis s'en va comme il est venu ; qu'il cherche quelque chose, "
					   "nul ne l'a jamais compris.",
		"base_attributes": _attrs((7, 7), (20, 35), (20, 35), (40, 55), (45, 65), (30, 45), (35, 55), (25, 40)),
		"tags": ["esprit", "vol", "nocturne", "seduction", "magique"],
		"butin": ("residu", 2.0, "peu_commun"),
		"son": "spectre",
		"visuel": "silhouette masculine translucide et élancée, beauté troublante, peau pâle bleutée, "
				  "longs cheveux noirs flottant dans un vent invisible, ailes de brume, pieds griffus "
				  "d'oiseau, voiles sombres emportés par la brise",
		"fond": "magenta",
	},
	"lilitu": {
		"nom": "Lilītu",
		"description": "Démone-vent aux pieds de chouette et aux ailes de nuit, qui hante les ruines et les "
					   "toits des maisons. Avec l'ardat-lilî, la jeune fille morte sans avoir été épousée, "
					   "elle cherche les hommes qu'elle n'a pas eus et les jeunes mères qu'elle envie. Les "
					   "conjurations la chassent vers le désert ; elle revient, et les récits ne s'accordent "
					   "ni sur ce qu'elle veut, ni sur le nombre de ses sœurs.",
		"base_attributes": _attrs((7, 7), (20, 35), (20, 35), (40, 55), (50, 70), (30, 45), (40, 60), (25, 40)),
		"tags": ["esprit", "vol", "nocturne", "seduction", "magique"],
		"butin": ("residu", 2.0, "peu_commun"),
		"son": "spectre",
		"visuel": "femme ailée d'une beauté froide, longues ailes sombres de chouette, pieds terminés "
				  "en serres de rapace, longue chevelure noire, tiare à cornes, peau pâle, yeux d'or "
				  "luisants, voiles déchirés ; elle plane",
		"fond": "bleu vif",
	},
	"gallu": {
		"nom": "Gallû",
		"description": "Démon des Enfers, envoyé sur la terre pour y ramener ceux que la Reine du Grand "
					   "Dessous réclame. Les récits disent qu'ils ne mangent ni ne boivent, ne connaissent "
					   "ni présent ni prière, et qu'ils traînèrent jusqu'en bas le berger Dumuzi. Ils vont "
					   "par bandes, et ceux qu'ils pourchassent ne savent jamais pourquoi leur nom a été dit.",
		"base_attributes": _attrs((6, 6), (50, 70), (45, 65), (35, 50), (50, 70), (15, 30), (0, 0), (20, 35)),
		"tags": ["esprit", "predateur", "terreur"],
		"butin": ("residu", 3.0, "peu_commun"),
		"son": "spectre",
		"visuel": "silhouette humanoïde décharnée à la peau grise comme la cendre, visage sans "
				  "expression aux orbites noires, longs bras aux doigts crochus, pagne sombre, chaînes "
				  "brisées aux poignets, brume noire qui monte du sol à ses pieds",
		"fond": "bleu vif",
	},
	"utukku": {
		"nom": "Utukku",
		"description": "Esprit errant que les conjurations comptent par sept : les utukkū mauvais, qui se "
					   "glissent par les fentes des portes comme le vent et rongent la force de qui ils "
					   "touchent. Les mêmes tablettes parlent d'utukkū bienveillants, gardiens d'une "
					   "maison ; aucun voyageur n'a jamais su lequel il croisait avant qu'il soit trop tard.",
		"base_attributes": _attrs((5, 5), (15, 25), (15, 25), (35, 55), (50, 75), (25, 40), (0, 0), (30, 50)),
		"tags": ["esprit", "incorporel", "nocturne"],
		"butin": ("residu", 2.0, "peu_commun"),
		"son": "spectre",
		"visuel": "esprit translucide verdâtre à forme humaine vague, visage étiré et grimaçant, corps "
				  "qui s'effiloche en fumée vers le bas, longues mains griffues tendues, yeux luisants",
		"fond": "magenta",
	},
	"etemmu": {
		"nom": "Eṭemmu",
		"description": "Fantôme d'un mort que personne n'a enterré, ou à qui l'on ne verse plus l'eau et la "
					   "farine des offrandes. Il revient tourmenter les siens, puis les passants, en "
					   "gémissant sa soif. Les uns disent qu'une tombe et une libation l'apaisent ; d'autres "
					   "que celui qui a erré trop longtemps a oublié jusqu'à son nom.",
		"base_attributes": _attrs((4, 6), (10, 20), (15, 25), (30, 50), (50, 75), (20, 35), (0, 0), (30, 50)),
		"tags": ["undead", "non_mort", "esprit", "incorporel"],
		"butin": ("residu", 2.0, "peu_commun"),
		"son": "spectre",
		"visuel": "fantôme pâle et émacié d'un homme, longue robe à franges en lambeaux, barbe et cheveux "
				  "défaits, lèvres desséchées, une coupe vide tendue dans une main, corps translucide qui "
				  "se perd en brume",
		"fond": "bleu vif",
	},
	"rabisu": {
		"nom": "Rabiṣu",
		"description": "« Celui qui guette » : un démon tapi derrière les portes, au coin des murs et sur les "
					   "toits, qui bondit sur qui passe à sa portée. Les récits le disent invisible "
					   "jusqu'au dernier instant et lui prêtent l'odeur des lieux qu'on ne visite plus. "
					   "Personne ne sait s'il attend quelqu'un en particulier.",
		"base_attributes": _attrs((6, 6), (30, 45), (25, 40), (45, 60), (45, 60), (25, 40), (0, 0), (25, 40)),
		"tags": ["esprit", "furtif", "nocturne", "terreur"],
		"butin": ("residu", 2.0, "peu_commun"),
		"son": "spectre",
		"visuel": "créature maigre et voûtée tapie dans l'ombre, peau sombre presque noire, longs membres "
				  "repliés, grands yeux jaunes sans paupières, oreilles pointues, doigts griffus agrippés "
				  "à l'arête d'un mur ; posture d'affût",
		"fond": "bleu vif",
	},
	"alu": {
		"nom": "Alû",
		"description": "Démon sans forme, sans bouche ni membres, qui vient la nuit s'asseoir sur la "
					   "poitrine des dormeurs et les étouffer. Ceux qui en ont réchappé parlent d'un poids, "
					   "d'une ombre et d'un froid ; aucun ne l'a vu. On murmure qu'il naît d'un ciel sans "
					   "étoiles ; d'autres, qu'il n'est que la peur des hommes devenue lourde.",
		"base_attributes": _attrs((5, 5), (40, 55), (30, 45), (20, 35), (50, 70), (10, 20), (0, 0), (25, 40)),
		"tags": ["esprit", "incorporel", "nocturne", "terreur"],
		"butin": ("residu", 3.0, "peu_commun"),
		"son": "spectre",
		"visuel": "masse d'ombre informe et dense, sans tête ni membres distincts, contours qui ondulent "
				  "comme une fumée lourde, quelques reflets froids bleutés à la surface, impression de "
				  "poids écrasant",
		"fond": "magenta",
	},
	"sebitti": {
		"nom": "Sebitti",
		"description": "« Les Sept » : guerriers démoniaques qui marchent devant Erra, le dieu des "
					   "fléaux, et brûlent d'aller ravager les terres. Le récit raconte qu'Erra lui-même "
					   "dut les retenir ; on ignore si ceux qui rôdent sont les Sept, leurs ombres ou des "
					   "imitateurs. Ils frappent ensemble, sans un mot, et ne fuient jamais.",
		"base_attributes": _attrs((5, 5), (55, 75), (50, 70), (35, 50), (50, 65), (20, 35), (0, 10), (20, 35)),
		"tags": ["esprit", "guerrier", "humanoide", "terreur"],
		"butin": ("residu", 3.0, "peu_commun"),
		"son": "ogre",
		"visuel": "guerrier démoniaque à la peau noire comme le basalte veinée de braises, casque à "
				  "cornes, barbe tressée, yeux rougeoyants, pagne de cuir et bracelets d'os, une masse "
				  "cannelée et une hache courte à la main ; posture de marche résolue",
		"fond": "bleu vif",
	},
	# ── Êtres uniques : boss au bestiaire seul ──
	"humbaba": {
		"nom": "Humbaba",
		"description": "Le gardien de la Forêt des Cèdres, posté là par Enlil : un géant au visage de lion "
					   "ridé comme des entrailles, dont la voix est le déluge, la bouche le feu et le "
					   "souffle la mort. Il entend une branche craquer à soixante lieues et s'enveloppe "
					   "de sept auras de terreur. Le récit veut que Gilgamesh et Enkidu l'aient abattu ; "
					   "la forêt, elle, dit qu'il garde toujours ses arbres.",
		"base_attributes": _attrs((6, 8), (100, 135), (90, 125), (25, 40), (80, 110), (30, 50), (0, 0), (45, 70)),
		"tags": ["monstre", "geant", "gardien", "terreur", "legendaire", "boss"],
		"butin": ("carcasse", [600, 900], "rare"),
		"son": "geant",
		"visuel": "géant colossal à face de lion aux traits creusés de rides profondes en volutes, "
				  "crinière sauvage, crocs, corps massif couvert d'écailles et de fourrure, griffes de "
				  "lion aux mains et aux pieds, flammes qui s'échappent de sa bouche, cèdres immenses "
				  "suggérés par quelques branches au premier plan",
		"fond": "magenta",
	},
	"taureau_celeste": {
		"nom": "Taureau céleste",
		"description": "Le taureau que la déesse Ishtar, éconduite, arracha à son père Anu pour le lâcher "
					   "sur Uruk. Chaque souffle ouvrait dans le sol une fosse où tombaient cent hommes, "
					   "et le fleuve baissait quand il buvait. Gilgamesh et Enkidu l'abattirent, dit le "
					   "récit, et lui arrachèrent une épaule ; on raconte pourtant qu'il paît encore "
					   "quelque part, entre la terre et le ciel.",
		"base_attributes": _attrs((7, 9), (110, 145), (100, 135), (20, 35), (70, 95), (10, 20), (0, 0), (40, 65)),
		"tags": ["monstre", "celeste", "legendaire", "boss"],
		"butin": ("carcasse", [1500, 2200], "rare"),
		"son": "bete",
		"visuel": "taureau colossal au pelage d'un bleu nuit constellé de points lumineux comme un ciel "
				  "étoilé, cornes immenses dorées en croissant, sabots fendus qui fissurent le sol, "
				  "naseaux fumants, muscles énormes ; il charge tête baissée",
		"fond": "magenta",
	},
	"asag": {
		"nom": "Asag",
		"description": "Le démon des montagnes, né de l'union du Ciel et de la Terre : là où il passe, les "
					   "poissons bouillent dans les rivières et les plantes sèchent sur pied. Les pierres "
					   "elles-mêmes se lèvent pour combattre à ses côtés. Le récit dit que Ninurta le "
					   "terrassa et fit de sa dépouille les montagnes qui retiennent les eaux ; les "
					   "mineurs, eux, jurent qu'il remue encore sous la roche.",
		"base_attributes": _attrs((6, 8), (95, 130), (110, 145), (15, 30), (85, 115), (30, 50), (0, 0), (40, 65)),
		"tags": ["monstre", "geant", "maladie", "terreur", "legendaire", "boss"],
		"butin": ("carcasse", [1200, 1800], "rare"),
		"son": "geant",
		"visuel": "être monstrueux massif fait de roche sombre et de chair calcinée, silhouette difforme "
				  "sans cou, tête hérissée de pointes de pierre, bouche béante rougeoyante, bras énormes "
				  "aux poings de basalte, vapeur brûlante qui monte de son corps, éclats de pierre en "
				  "lévitation autour de lui",
		"fond": "bleu vif",
	},
	"labbu": {
		"nom": "Labbu",
		"description": "Serpent de mer né de l'écume, si long qu'on le mesure en lieues : le récit lui "
					   "donne cinquante lieues de corps et une gueule de six coudées. Il ravagea les "
					   "terres jusqu'à ce que Tišpak le tue, et son sang coula trois ans, trois mois, un "
					   "jour et une nuit. Les marins des côtes du Levant disent qu'il en reste un, ou que "
					   "c'est le même.",
		"base_attributes": _attrs((6, 8), (110, 150), (100, 140), (10, 25), (80, 110), (15, 30), (0, 0), (55, 85)),
		"tags": ["monstre", "reptile", "aquatique", "legendaire", "boss"],
		"butin": ("carcasse", [4000, 6000], "rare"),
		"son": "dragon",
		"visuel": "serpent de mer colossal aux écailles vert sombre et bronze, corps interminable formant "
				  "des anneaux qui émergent de l'eau, tête de dragon aux mâchoires immenses ouvertes, "
				  "crête dorsale déchiquetée, écume blanche qui ruisselle de ses flancs",
		"fond": "magenta",
	},
	"mushmahhu": {
		"nom": "Mušmaḫḫu",
		"description": "« Le serpent exalté », à sept têtes : l'un des onze de Tiamat, et l'un des monstres "
					   "que Ninurta compte parmi ses victoires. Chaque tête a sa volonté, et toutes crachent "
					   "un venin qui ronge la pierre. Le récit ne dit pas où il tomba ; on cite des ruines "
					   "où l'on n'ose plus descendre.",
		"base_attributes": _attrs((6, 6), (85, 120), (80, 115), (20, 35), (80, 110), (30, 50), (0, 0), (45, 75)),
		"tags": ["monstre", "reptile", "venin", "legendaire", "boss"],
		"butin": ("carcasse", [2500, 3500], "rare"),
		"son": "dragon",
		"visuel": "serpent colossal à sept têtes cornues sur sept longs cous qui ondulent chacun dans "
				  "une direction, écailles brun-rouge et noires, gueules ouvertes sur des crochets "
				  "dégoulinant de venin vert, corps massif enroulé",
		"fond": "bleu vif",
	},
}

# « zone@CODES » (codes de gen_monstres_legendes.REG). Les boss n'y figurent pas.
ZONES = {
	"kusarikku": ["ruines_maudites@AN", "steppe_aride@AN", "oasis@AN"],
	"bashmu": ["desert@AN", "oasis@AN", "canyon@AN"],
	"ushumgallu": ["ruines_maudites@AN", "desert@AN", "montagne@AN"],
	"lahmu": ["oasis@AN", "palmeraie@AN", "ruines_maudites@AN"],
	"uridimmu": ["ruines_maudites@AN", "steppe_aride@AN", "contreforts_arides@AN"],
	"kulullu": ["riviere@AN", "delta@AN", "lac@AN"],
	"umu_dabrutu": ["desert@AN", "erg@AN", "hamada@AN"],
	"anzu": ["montagne@AN", "haute_montagne@AN", "cedraie_altitude@AN"],
	"urmahlullu": ["ruines_maudites@AN", "oasis@AN", "steppe_aride@AN"],
	"lilu": ["ruines_maudites@AN", "desert@AN", "palmeraie@AN"],
	"lilitu": ["ruines_maudites@AN", "palmeraie@AN", "terres_cultivees@AN"],
	"gallu": ["ruines_maudites@AN", "gouffre@AN", "grotte@AN"],
	"utukku": ["ruines_maudites@AN", "desert@AN", "steppe_aride@AN"],
	"etemmu": ["ruines_maudites@AN", "desert@AN", "hamada@AN"],
	"rabisu": ["ruines_maudites@AN", "canyon@AN", "grotte@AN"],
	"alu": ["ruines_maudites@AN", "terres_cultivees@AN", "palmeraie@AN"],
	"sebitti": ["steppe_aride@AN", "desert@AN", "contreforts_arides@AN"],
}


def installer(setattr_fn=setattr) -> None:
	"""Branche ce lot sur le moteur de gen_monstres_legendes (globales lues par ses fonctions).
	Les tests passent `monkeypatch.setattr` pour que le branchement soit défait après eux."""
	setattr_fn(moteur, "NOUVELLES", NOUVELLES)
	setattr_fn(moteur, "ZONES", ZONES)
	setattr_fn(moteur, "DONJONS", {})
	setattr_fn(moteur, "REGIONS_NEUVES", {})  # afrique_du_nord existe déjà en base
	setattr_fn(moteur, "SORTIE", SORTIE)


if __name__ == "__main__":
	installer()
	moteur.main()

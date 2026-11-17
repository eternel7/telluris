#!/usr/bin/env python
# dev/gen_monstres_legendes.py
# Bestiaire des légendes du monde (liste docs/monstres_a_creer.md, décisions de l'Auteur du 17/11/2026) :
#   - 29 espèces `espece:*` : 7 d'Europe (dont le slime, la Mère-gelée et le lapin cornu, créatures
#     de DONJON seulement), 5 du Moyen-Orient et d'Afrique, 6 d'Asie, 5 des Amériques, 5 « autres » ;
#   - un butin par défaut par espèce (`item:<slug>` : carcasse, ossements ou résidu spectral), et la
#     découpe des grosses carcasses par `gen_carcasses_parties.generer`, DANS LE MÊME FICHIER ;
#   - deux régions DORMANTES `asie` et `ameriques` dans `rules:regions` (aucun lieu : leurs défauts de
#     zone s'éveillent le jour où une carte de pays y est rattachée) ;
#   - les défauts de rencontre des zones par biome (`ZONES`, filtrés par région ; ajout seul) ;
#   - le lapin cornu dans la Forêt de Saint-Loup et la Clairière du charbonnier (`DONJONS`) ;
#   - les 6 boss (Nuckelavee, Inkanyamba, Gashadokuro, Mngwa, Mokele-Mbembe, Roc) restent au bestiaire
#     seul, comme Ladon et Yamata no Orochi (Auteur) ; le slime et la Mère-gelée seront placés plus tard.
#
# SOURCES UNIQUES relues ici (jamais recopiées) : jeton (`gen_jetons_especes.TABLE`), accord
# (`gen_genres_especes.accord_de`), compétences / magie / IA (`gen_capacites_monstres`), kit d'un
# humanoïde (`gen_equipement_humanoides.TABLE`), effectif (`gen_effectifs_especes.fourchette_pour`) et
# armure naturelle (`gen_armure_naturelle.bonus_armure`) sur le rang MESURÉ par le moteur.
# ⚠️ Ces tables EXHAUSTIVES citent déjà les espèces neuves : `gen_jetons_especes`,
# `gen_genres_especes`, `gen_equipement_humanoides` et `gen_capacites_monstres` échouent tant que
# l'import n'est pas fait et qu'un dump FRAIS ne l'a pas relu.
#
# Images : `--prompts` ajoute les prompts (gabarit docs/prompts_images.md § 3) à
# dev/batch/monstres/prompts.json, puis `python dev/gen_images_monstres.py avancer` (PAYANT). Le champ
# `image` lit le manifeste du lot ; sans image encore, `<slug>_transparent.webp`.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. Zones, donjons et `rules:regions`
# sont RELUS du dump le plus récent et seul le champ visé change ; un doc neuf dont l'`_id` est déjà en
# base n'est jamais réécrit (« déjà en base »). Le fichier ne porte que le DELTA (CLAUDE.md §18).
#
# Usage : python dev/gen_monstres_legendes.py [--dump jsons/telluris-dump-….json] [--prompts]
# Sortie : jsons/monstres_legendes_a_importer.json

import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_armure_naturelle as armure  # noqa: E402
import gen_capacites_monstres as capacites  # noqa: E402
import gen_carcasses_parties as carcasses  # noqa: E402
import gen_effectifs_especes as effectifs  # noqa: E402
import gen_sons as sons  # noqa: E402
from gen_equipement_humanoides import TABLE as KITS, erreurs_kit  # noqa: E402
from gen_genres_especes import accord_de  # noqa: E402
from gen_jetons_especes import TABLE as JETONS  # noqa: E402
from gen_vampires import _attrs, _sans_rev  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "monstres_legendes_a_importer.json")
PROMPTS = os.path.join(RACINE, "dev", "batch", "monstres", "prompts.json")
MANIFESTE = os.path.join(RACINE, "dev", "batch", "monstres", "manifeste.json")

# ── Espèces ────────────────────────────────────────────────────────────────────
# `butin` = (forme, poids, rareté) ; forme ∈ carcasse (poids [min, max], découpée au-delà du seuil) ·
# gelee (slimes, jamais découpée) · ossements · residu (résidu spectral). `son` = famille de cri imposée (sinon `gen_sons.famille_de`). `visuel` / `fond` : prompt.

NOUVELLES = {
	# ── 1. Europe et folklore médiéval ──
	"kelpie": {
		"nom": "Kelpie",
		"description": "Esprit des lacs et des rivières d'Écosse qui prend l'apparence d'un magnifique "
					   "cheval noir, la crinière ruisselante d'herbes d'eau. Il se laisse approcher par "
					   "les voyageurs fatigués ; qui le monte reste collé à sa peau, et la bête plonge. "
					   "On dit qu'une bride passée à son cou le rend docile, mais nul ne s'accorde sur "
					   "la manière de la lui passer.",
		"base_attributes": _attrs((7, 7), (45, 65), (45, 60), (35, 50), (40, 60), (20, 35), (0, 0), (15, 30)),
		"tags": ["monstre", "aquatique", "metamorphe", "predateur"],
		"butin": ("carcasse", [300, 500], "peu_commun"),
		"visuel": "cheval noir d'une beauté inquiétante, robe luisante d'eau, crinière et queue faites "
				  "d'herbes aquatiques ruisselantes, sabots retournés, yeux trop sombres",
		"fond": "bleu vif",
	},
	"each_uisge": {
		"nom": "Each-Uisge",
		"description": "Cheval des eaux profondes des lacs d'Écosse, plus redoutable encore que le "
					   "kelpie : il prend la forme d'un beau cheval ou d'un homme séduisant. Qui le monte "
					   "est emporté au fond, dévoré, et l'on ne retrouve souvent que son foie sur la "
					   "rive. Les uns disent qu'il ne quitte jamais l'eau salée, les autres qu'il remonte "
					   "les rivières jusqu'aux lochs.",
		"base_attributes": _attrs((6, 6), (50, 70), (45, 65), (40, 55), (45, 60), (25, 40), (0, 0), (20, 35)),
		"tags": ["monstre", "aquatique", "metamorphe", "predateur"],
		"butin": ("carcasse", [400, 650], "rare"),
		"visuel": "grand cheval gris-vert à la robe mouillée comme une algue, crinière d'écume, gueule "
				  "garnie de crocs de carnassier, regard affamé",
		"fond": "bleu vif",
	},
	"dullahan": {
		"nom": "Dullahan",
		"description": "Cavalier sans tête des routes d'Irlande, qui chevauche la nuit un cheval noir en "
					   "portant sa propre tête sous le bras ; ses yeux voient à travers les ténèbres. Là "
					   "où il s'arrête, quelqu'un meurt bientôt, et il le nomme à voix haute. On raconte "
					   "que l'or le fait reculer ; personne n'a dit combien.",
		"base_attributes": _attrs((7, 7), (50, 70), (50, 70), (35, 50), (55, 75), (30, 45), (0, 0), (10, 25)),
		"tags": ["undead", "non_mort", "nocturne", "terreur", "insensible_furtivite"],
		"butin": ("ossements", 12.0, "peu_commun"),
		"visuel": "cavalier sans tête en armure sombre et cape déchirée, monté sur un cheval noir aux "
				  "yeux ardents, tenant sous le bras sa tête blafarde au sourire figé, un fouet fait "
				  "d'une échine humaine à la main ; chair desséchée, lueur froide dans les orbites de la tête",
		"fond": "magenta",
	},
	"barghest": {
		"nom": "Barghest",
		"description": "Immense chien noir aux yeux flamboyants qui rôde sur les chemins isolés du nord "
					   "de l'Angleterre, près des cimetières et aux carrefours. Le voir annonce un décès "
					   "ou un malheur ; certains récits le disent capable de se rendre invisible, "
					   "d'autres qu'il ne franchit pas l'eau courante.",
		"base_attributes": _attrs((6, 6), (35, 50), (30, 45), (40, 55), (35, 50), (20, 30), (0, 0), (15, 30)),
		"tags": ["monstre", "nocturne", "terreur", "furtif", "predateur", "insensible_furtivite"],
		"butin": ("carcasse", [60, 100], "peu_commun"),
		"son": "loup",
		"visuel": "immense chien noir de la taille d'un veau, pelage hirsute couleur de suie, yeux "
				  "flamboyants comme des braises, crocs découverts ; attitude de chasse, regard fixé sur sa proie",
		"fond": "magenta",
	},
	"nuckelavee": {
		"nom": "Nuckelavee",
		"description": "Démon des côtes et des landes des Orcades, cheval et cavalier fondus en un seul "
					   "corps, sans peau : muscles et veines noires y sont à nu. Son souffle flétrit les "
					   "récoltes, tue le bétail et répand la maladie. Il craint l'eau douce et ne passe pas "
					   "un ruisseau ; on ignore s'il en meurt ou s'il s'en détourne seulement.",
		"base_attributes": _attrs((7, 7), (75, 105), (70, 100), (30, 45), (70, 95), (30, 45), (0, 0), (30, 50)),
		"tags": ["monstre", "terreur", "maladie", "legendaire", "boss", "insensible_furtivite"],
		"butin": ("carcasse", [800, 1500], "rare"),
		"visuel": "monstre cheval et cavalier fusionnés, entièrement dépourvu de peau, muscles rouge "
				  "sombre et veines noires à nu, un seul œil enflammé au milieu de la tête du cheval, "
				  "torse humain soudé au garrot aux bras trop longs touchant le sol, tête du cavalier "
				  "énorme et ballante",
		"fond": "vert vif",
	},
	"slime": {
		"nom": "Slime",
		"description": "Masse gélatineuse qui rampe dans les galeries et les recoins humides des "
					   "donjons. Lente, presque inoffensive seule, elle se divise quand on la tranche et "
					   "s'agglutine à ses semblables. Personne ne sait de quoi elle se nourrit entre deux "
					   "aventuriers.",
		"base_attributes": _attrs((3, 3), (10, 20), (20, 30), (5, 15), (5, 15), (0, 3), (0, 0), (5, 10)),
		"tags": ["monstre", "souterrain", "lent", "nuee"],
		"butin": ("gelee", [1, 3], "commun"),
		"son": "visqueux",
		"visuel": "petite masse gélatineuse translucide vert pâle en forme de goutte affaissée, "
				  "surface luisante, quelques bulles et petits débris prisonniers dans sa gelée",
		"fond": "bleu vif",
	},
	"mere_gelee": {
		"nom": "Mère-gelée",
		"description": "Slime colossal qui emplit à elle seule une salle de donjon : les petits slimes se "
					   "détachent de ses flancs comme des gouttes. Elle engloutit ce qu'elle touche et "
					   "referme ses plaies aussitôt ouvertes. Ce qu'on trouve dans sa gelée après sa mort "
					   "raconte les aventuriers qui l'ont précédé.",
		"base_attributes": _attrs((3, 3), (50, 70), (80, 110), (5, 10), (30, 45), (0, 5), (0, 0), (10, 20)),
		"tags": ["monstre", "souterrain", "lent", "regeneration", "boss"],
		"butin": ("gelee", [150, 300], "peu_commun"),
		"son": "visqueux",
		"visuel": "énorme masse gélatineuse translucide vert pâle, haute comme deux hommes, d'où se "
				  "détachent de petites gouttes de gelée ; ossements, une épée rouillée, un casque et "
				  "quelques pièces flottent prisonniers dans sa masse",
		"fond": "bleu vif",
	},
	"lapin_cornu": {
		"nom": "Lapin cornu",
		"description": "Lapin des prairies portant au front une corne unique et torse, écho de l'almiraj "
					   "des conteurs arabes et des lièvres à bois des veillées. Craintif à découvert, il "
					   "charge pourtant d'un bond qui perce le cuir. On le rencontre surtout dans les "
					   "donjons qui sont des champs et des forêts ; sa corne se garde en trophée.",
		"base_attributes": _attrs((5, 5), (8, 15), (6, 12), (30, 45), (10, 20), (5, 10), (0, 0), (10, 20)),
		"tags": ["animal", "petite_taille", "rapide"],
		"butin": ("carcasse", [2, 4], "commun"),
		"visuel": "lapin de garenne brun au pelage dru, une corne unique, torsadée et pointue au milieu "
				  "du front, oreilles dressées, prêt à bondir ; attitude aux aguets",
		"fond": "magenta",
	},
	# ── 2. Moyen-Orient et Afrique ──
	"roc": {
		"nom": "Roc",
		"description": "Oiseau colossal des montagnes isolées et des îles lointaines, dont l'ombre couvre "
					   "un campement entier ; les marins jurent qu'il emporte un éléphant dans ses serres. "
					   "Ses œufs, gros comme des coupoles, valent une fortune pour qui les rapporte. Nul "
					   "ne sait où il niche vraiment, et ceux qui l'ont trouvé n'ont pas tous su redescendre.",
		"base_attributes": _attrs((15, 15), (90, 120), (80, 105), (35, 50), (65, 85), (20, 35), (0, 0), (40, 60)),
		"tags": ["monstre", "vol", "legendaire", "boss", "predateur"],
		"butin": ("carcasse", [3000, 8000], "rare"),
		"visuel": "oiseau gigantesque au plumage brun et or, envergure immense, bec crochu massif, serres "
				  "énormes ; elle est en vol, ailes déployées",
		"fond": "magenta",
	},
	"teryel": {
		"nom": "Teryel",
		"description": "Dévoreuse des contes kabyles, femme monstrueuse des montagnes sauvages ; rien à "
					   "voir avec la Lignée des ogres, quoi qu'en disent les mauvaises langues. Elle prend "
					   "l'apparence d'une femme ordinaire, attire les voyageurs dans son domaine et dévore "
					   "ceux qu'elle attrape. Les contes la disent aussi dupe que cruelle : on lui échappe "
					   "par la ruse, rarement par la force.",
		"base_attributes": _attrs((5, 5), (55, 75), (50, 70), (30, 45), (45, 60), (35, 50), (40, 60), (15, 30)),
		"tags": ["monstre", "metamorphe", "seduction", "predateur"],
		"butin": ("carcasse", [120, 200], "peu_commun"),
		"visuel": "femme monstrueuse très grande aux cheveux noirs immenses et emmêlés, longs ongles "
				  "crochus, dents de carnassier, robe kabyle déchirée aux broderies fanées, sourire "
				  "trompeusement accueillant",
		"fond": "magenta",
	},
	"impundulu": {
		"nom": "Impundulu",
		"description": "Oiseau de la foudre des orages d'Afrique australe, aux ailes noires et blanches "
					   "qui claquent comme le tonnerre. On le dit au service des sorcières, buveur de sang, "
					   "capable de prendre forme humaine et de filer à la vitesse de l'éclair. Là où frappe "
					   "la foudre, les anciens cherchent son œuf.",
		"base_attributes": _attrs((15, 15), (30, 45), (25, 40), (50, 65), (50, 70), (30, 45), (0, 0), (20, 35)),
		"tags": ["monstre", "vol", "magique", "predateur"],
		"butin": ("carcasse", [8, 15], "peu_commun"),
		"visuel": "grand oiseau au plumage noir et blanc éclatant, bec acéré, serres crochues, petits "
				  "éclairs bleutés crépitant entre ses plumes ; elle est en vol, ailes déployées",
		"fond": "magenta",
	},
	"tokoloshe": {
		"nom": "Tokoloshe",
		"description": "Petit esprit malveillant et difforme des terres d'Afrique australe, invisible "
					   "aux yeux ordinaires. Il entre la nuit dans les maisons, souffle des cauchemars, "
					   "vole des objets et tourmente les dormeurs ; on surélève son lit sur des briques "
					   "pour lui échapper. Les uns le disent né d'une sorcellerie, les autres plus vieux "
					   "qu'elle.",
		"base_attributes": _attrs((5, 5), (15, 25), (15, 25), (45, 60), (40, 55), (30, 45), (0, 0), (30, 45)),
		"tags": ["esprit", "petite_taille", "furtif", "malediction", "nocturne"],
		"butin": ("residu", 2.0, "peu_commun"),
		"visuel": "petit être difforme haut comme un enfant, peau sombre et ridée, longs bras grêles, "
				  "yeux brillants et malicieux, sourire de travers, corps à demi effacé comme une ombre",
		"fond": "magenta",
	},
	"inkanyamba": {
		"nom": "Inkanyamba",
		"description": "Immense serpent des cascades et des lacs d'Afrique australe, à la tête de cheval "
					   "et à la crinière de nageoires. Sa colère soulève les tempêtes, les tourbillons et "
					   "les crues ; on dit qu'à la saison chaude il quitte sa cascade pour chercher une "
					   "compagne dans le ciel. Nul n'a vu où il dort.",
		"base_attributes": _attrs((6, 6), (100, 130), (95, 125), (25, 40), (85, 110), (35, 50), (0, 0), (40, 60)),
		"tags": ["monstre", "aquatique", "reptile", "legendaire", "boss"],
		"butin": ("carcasse", [4000, 10000], "rare"),
		"visuel": "serpent aquatique colossal au corps interminable couleur d'ardoise aux reflets bleus, "
				  "tête allongée rappelant celle d'un cheval, crinière de nageoires, gueule ouverte, "
				  "corps luisant, comme sortant de l'eau",
		"fond": "magenta",
	},
	# ── 3. Asie ──
	"kappa": {
		"nom": "Kappa",
		"description": "Petit amphibien humanoïde des rivières du Japon, au bec de tortue et à la "
					   "carapace sur le dos ; le sommet de son crâne creux garde une eau qui fait sa force. "
					   "Il attire les voyageurs dans l'eau, les noie et boit leur souffle de vie. Un salut "
					   "poli, dit-on, lui fait courber la tête et renverser son eau.",
		"base_attributes": _attrs((5, 5), (30, 45), (30, 45), (40, 55), (35, 50), (30, 40), (0, 0), (20, 35)),
		"tags": ["monstre", "aquatique", "predateur"],
		"butin": ("carcasse", [25, 45], "peu_commun"),
		"visuel": "petit amphibien humanoïde à peau verte écailleuse, bec de tortue, carapace sur le "
				  "dos, mains palmées, sommet du crâne creusé en coupelle pleine d'eau entourée de "
				  "cheveux raides ; peau humide et luisante, debout sur rien, sans flaque ni eau au sol",
		"fond": "magenta",
	},
	"tengu": {
		"nom": "Tengu",
		"description": "Esprit ailé des montagnes du Japon, au long nez et au visage rouge, souvent vêtu "
					   "comme un ermite des cimes. Certains sont des maîtres du sabre qui enseignent, "
					   "dit-on, à de rares élus ; d'autres égarent les voyageurs et déchaînent la tempête "
					   "contre qui manque de respect à la montagne.",
		"base_attributes": _attrs((8, 8), (35, 50), (30, 45), (45, 60), (45, 60), (40, 55), (20, 35), (25, 40)),
		"tags": ["esprit", "vol", "guerrier", "magique", "humanoide"],
		"butin": ("carcasse", [40, 70], "peu_commun"),
		"visuel": "guerrier ailé au visage rouge et au très long nez, sourcils broussailleux, vêtu de la "
				  "robe d'un ermite des montagnes, grandes ailes de rapace brunes, katana au poing ; "
				  "elle est en vol, ailes déployées",
		"fond": "vert vif",
	},
	"gashadokuro": {
		"nom": "Gashadokuro",
		"description": "Squelette géant fait des os de tous ceux qui sont morts de faim ou de violence sans "
					   "sépulture. Il erre la nuit, silencieux malgré sa taille, saisit les voyageurs isolés "
					   "et leur arrache la tête. Un tintement d'os, comme des grelots, précède parfois son "
					   "passage ; parfois rien.",
		"base_attributes": _attrs((6, 6), (135, 170), (130, 160), (15, 30), (80, 100), (10, 20), (0, 0), (25, 40)),
		"tags": ["undead", "non_mort", "geant", "terreur", "legendaire", "boss"],
		"butin": ("ossements", [800, 2000], "rare"),
		"visuel": "squelette géant, quinze fois la taille d'un homme, fait de centaines d'ossements "
				  "humains soudés, crâne immense penché en avant, longues mains osseuses tendues ; os "
				  "apparents, lueur froide dans les orbites",
		"fond": "magenta",
	},
	"qilin": {
		"nom": "Qilin",
		"description": "Créature sacrée au corps de cerf couvert d'écailles dorées, à une ou deux cornes, "
					   "dont la venue annonce la naissance d'un grand sage. Il ne piétine aucun être vivant "
					   "et marche sur l'eau sans la troubler ; menacé, il fuit plutôt que de frapper. Ce "
					   "qu'il annonce en croisant un aventurier, nul ne s'accorde à le dire.",
		"base_attributes": _attrs((8, 8), (35, 50), (40, 55), (50, 65), (65, 85), (50, 65), (40, 60), (40, 60)),
		"tags": ["monstre", "magique", "pure", "rapide"],
		"butin": ("carcasse", [200, 350], "rare"),
		"visuel": "créature au corps de cerf gracieux couvert d'écailles dorées, une corne unique, "
				  "crinière et queue flamboyantes rouge et or, sabots fendus effleurant à peine le sol, "
				  "regard paisible",
		"fond": "vert vif",
	},
	"baku": {
		"nom": "Baku",
		"description": "Chimère au corps d'ours, à la trompe d'éléphant et aux pattes de tigre, qui dévore "
					   "les mauvais rêves et veille sur les dormeurs. Affamé, il dévore aussi les rêves "
					   "heureux et laisse ses victimes sans espoir. Il fuit plus volontiers qu'il ne se bat.",
		"base_attributes": _attrs((5, 5), (65, 80), (65, 80), (25, 40), (80, 100), (45, 60), (0, 0), (30, 45)),
		"tags": ["monstre", "hybride", "magique", "nocturne"],
		"butin": ("carcasse", [300, 500], "rare"),
		"visuel": "chimère trapue au corps d'ours au pelage sombre, trompe d'éléphant, défenses courtes, "
				  "pattes rayées de tigre, petits yeux doux et somnolents",
		"fond": "magenta",
	},
	"jorogumo": {
		"nom": "Jorōgumo",
		"description": "Araignée des forêts et des cascades du Japon qui prend l'apparence d'une femme "
					   "séduisante. Elle attire les voyageurs dans son repaire, les enivre de musique ou "
					   "de mots doux, puis les ligote dans ses fils pour les dévorer. On dit qu'elle compte "
					   "les années par centaines avant de savoir changer de forme.",
		"base_attributes": _attrs((5, 5), (45, 60), (45, 60), (55, 70), (55, 70), (45, 60), (50, 70), (20, 35)),
		"tags": ["monstre", "venin", "metamorphe", "seduction", "predateur"],
		"butin": ("carcasse", [60, 120], "peu_commun"),
		"son": "insecte",
		"visuel": "araignée géante au corps noir et jaune, dont le buste se change en une femme "
				  "séduisante en kimono sombre, longs cheveux noirs, un biwa entre les mains, fils de "
				  "soie tendus entre ses pattes ; attitude de chasse, regard fixé sur sa proie",
		"fond": "vert vif",
	},
	# ── 4. Amériques ──
	"wendigo": {
		"nom": "Wendigo",
		"description": "Esprit de l'hiver, de la famine et de la chair humaine dans les forêts glacées du "
					   "Nord-Ouest : un humanoïde décharné aux lèvres rongées, dont la faim grandit à mesure "
					   "qu'il mange. Il chasse les voyageurs perdus dans la neige. Les uns disent qu'on le "
					   "devient en cédant à la faim, les autres qu'il est né du froid lui-même.",
		"base_attributes": _attrs((7, 7), (60, 85), (55, 75), (45, 60), (50, 70), (25, 40), (0, 0), (20, 35)),
		"tags": ["monstre", "froid", "terreur", "predateur", "nocturne"],
		"butin": ("carcasse", [80, 150], "peu_commun"),
		"visuel": "humanoïde décharné et très grand, peau grise tendue sur les os, côtes saillantes, "
				  "lèvres rongées sur des crocs, longs doigts griffus, givre sur les épaules, yeux "
				  "enfoncés et affamés ; attitude de chasse, regard fixé sur sa proie",
		"fond": "magenta",
	},
	"oiseau_tonnerre": {
		"nom": "Oiseau-tonnerre",
		"description": "Oiseau colossal des hautes montagnes du Nord-Ouest : ses ailes font le tonnerre, "
					   "ses yeux lancent les éclairs. Il règne sur le ciel et combat les grands serpents des "
					   "eaux ; sa venue annonce une tempête comme on n'en voit qu'une par génération.",
		"base_attributes": _attrs((14, 14), (65, 85), (55, 75), (45, 60), (70, 95), (35, 50), (0, 0), (35, 55)),
		"tags": ["monstre", "vol", "elementaire", "magique"],
		"butin": ("carcasse", [600, 1200], "rare"),
		"visuel": "oiseau colossal au plumage noir et bleu nuit, bec crochu, serres puissantes, éclairs "
				  "jaillissant de ses yeux et crépitant au bout de ses rémiges ; elle est en vol, ailes déployées",
		"fond": "magenta",
	},
	"mapinguari": {
		"nom": "Mapinguari",
		"description": "Monstre géant des forêts d'Amazonie, couvert d'une fourrure épaisse et précédé "
					   "d'une odeur pestilentielle ; certains lui donnent une bouche au milieu du ventre. "
					   "Presque invulnérable, il fait fuir les chasseurs de son seul cri. Les uns le disent "
					   "vieux comme la forêt, les autres né d'un chasseur maudit.",
		"base_attributes": _attrs((5, 5), (95, 125), (100, 130), (20, 35), (65, 85), (15, 25), (0, 0), (25, 40)),
		"tags": ["monstre", "geant", "foret", "predateur"],
		"butin": ("carcasse", [600, 1200], "rare"),
		"visuel": "monstre massif dressé sur ses pattes arrière, haut comme deux hommes, fourrure "
				  "brun sombre hirsute, longues griffes recourbées, un seul œil, une large bouche "
				  "dentue au milieu du ventre",
		"fond": "magenta",
	},
	"ahuizotl": {
		"nom": "Ahuizotl",
		"description": "Bête des lacs et des rivières des Mexicas, semblable à un petit chien au pelage "
					   "luisant, avec une main d'Anthrope au bout de la queue. Il attire les imprudents "
					   "au bord de l'eau, les saisit et les entraîne au fond ; on retrouve les corps "
					   "intacts, privés des yeux, des ongles et des dents.",
		"base_attributes": _attrs((6, 6), (30, 45), (25, 40), (45, 60), (30, 45), (20, 30), (0, 0), (15, 30)),
		"tags": ["monstre", "aquatique", "predateur"],
		"butin": ("carcasse", [15, 30], "peu_commun"),
		"visuel": "petit animal semblable à un chien au pelage noir lisse et luisant, oreilles pointues, "
				  "pattes de raton, une main humaine griffue au bout de sa longue queue ; corps luisant, "
				  "comme sortant de l'eau",
		"fond": "magenta",
	},
	"camazotz": {
		"nom": "Camazotz",
		"description": "Chauve-souris humanoïde géante des cavernes et des ruines mayas, celle que les "
					   "récits placent dans la Maison des Chauves-souris : elle tranche les têtes d'un "
					   "coup de son nez acéré. La nuit lui appartient ; ce qu'elle fait des têtes, les "
					   "récits ne le disent pas.",
		"base_attributes": _attrs((10, 10), (35, 50), (30, 45), (45, 60), (40, 55), (25, 40), (0, 0), (20, 35)),
		"tags": ["monstre", "vol", "nocturne", "souterrain", "predateur"],
		"butin": ("carcasse", [40, 80], "peu_commun"),
		"visuel": "chauve-souris humanoïde géante, ailes membraneuses immenses, nez en forme de lame, "
				  "crocs, griffes au bout des ailes, fourrure noire ; elle est en vol, ailes déployées",
		"fond": "magenta",
	},
	# ── 5. Autres créatures retenues ──
	"mngwa": {
		"nom": "Mngwa",
		"description": "Félin plus grand qu'un lion, à la fourrure grise tachetée, qui chasse les "
					   "Anthropes jusque dans les villages isolés de la côte d'Afrique de l'Est. Il tue un "
					   "homme adulte en quelques instants et ne laisse que des touffes de poils gris. Les "
					   "chasseurs ne s'accordent ni sur sa robe ni sur le nombre de ses semblables.",
		"base_attributes": _attrs((8, 8), (65, 85), (55, 75), (60, 75), (55, 75), (25, 40), (0, 0), (35, 55)),
		"tags": ["monstre", "predateur", "rapide", "legendaire", "boss"],
		"butin": ("carcasse", [250, 400], "rare"),
		"visuel": "félin colossal plus grand qu'un lion, fourrure gris cendré tachetée de noir, "
				  "épaules massives, crocs énormes ; attitude de chasse, griffes et crocs visibles, "
				  "regard fixé sur sa proie",
		"fond": "magenta",
	},
	"adze": {
		"nom": "Adze",
		"description": "Esprit buveur de sang des pays ewe, qui prend la forme d'une luciole pour entrer "
					   "dans les maisons et boire le sang des dormeurs ; sous forme humaine, il passe "
					   "inaperçu. Les uns le rattachent aux lignées de vampires du nord, les autres jurent "
					   "qu'il ne doit rien à personne. Le jour, dit-on, il se terre.",
		"base_attributes": _attrs((12, 12), (10, 20), (10, 20), (55, 70), (45, 60), (35, 50), (0, 0), (25, 40)),
		"tags": ["esprit", "petite_taille", "furtif", "nocturne", "vol"],
		"butin": ("residu", 1.0, "peu_commun"),
		"visuel": "luciole surnaturelle grosse comme un poing, à la lueur rouge ambré, dont la lumière "
				  "dessine un visage malveillant aux crocs fins, ailes translucides ; elle est en vol",
		"fond": "magenta",
	},
	"mokele_mbembe": {
		"nom": "Mokele-Mbembe",
		"description": "Grand animal territorial des marais et des rivières profondes du bassin du Congo, "
					   "au long cou et à la queue massive, qui barre le cours de l'eau. Il renverse les "
					   "pirogues et tue sans dévorer. Les riverains disent qu'il arrête les rivières ; nul "
					   "ne sait combien il en reste.",
		"base_attributes": _attrs((5, 5), (140, 175), (135, 165), (15, 25), (75, 95), (20, 30), (0, 0), (35, 55)),
		"tags": ["monstre", "aquatique", "reptile", "legendaire", "boss"],
		"butin": ("carcasse", [6000, 15000], "rare"),
		"visuel": "animal colossal au long cou et à la petite tête, corps massif gris-brun aux "
				  "épaules d'éléphant, queue énorme et puissante, une corne sur le museau ; corps "
				  "luisant, comme sortant de l'eau",
		"fond": "magenta",
	},
	"pontianak": {
		"nom": "Pontianak",
		"description": "Esprit d'une femme morte enceinte, des jungles et des bananeraies de Malaisie : "
					   "belle femme aux longs cheveux noirs, en robe blanche, qui révèle sa nature "
					   "monstrueuse en attaquant. Un cri d'enfant ou un parfum de fleur annoncent sa "
					   "venue ; un clou planté dans sa nuque, dit-on, la rendrait à la vie ordinaire.",
		"base_attributes": _attrs((6, 6), (35, 50), (30, 45), (55, 70), (65, 85), (35, 50), (50, 70), (0, 0)),
		"tags": ["undead", "non_mort", "esprit", "seduction", "terreur", "nocturne"],
		"butin": ("residu", 2.5, "peu_commun"),
		"son": "spectre",
		"visuel": "femme spectrale très pâle aux immenses cheveux noirs tombant jusqu'au sol, robe "
				  "blanche longue et souillée, ongles longs et crochus, visage beau mais yeux rouges et "
				  "bouche aux crocs fins, pieds flottant au-dessus du vide",
		"fond": "vert vif",
	},
	"kongamato": {
		"nom": "Kongamato",
		"description": "Grand reptile ailé sans plumes des fleuves d'Afrique centrale, au bec garni de "
					   "dents : « celui qui renverse les barques ». Il fond sur les pirogues et les "
					   "voyageurs près de l'eau ; les pêcheurs le chassent à grands cris, et l'on dit que "
					   "le voir en face porte malheur.",
		"base_attributes": _attrs((10, 10), (35, 50), (30, 45), (45, 60), (30, 45), (15, 25), (0, 0), (15, 30)),
		"tags": ["monstre", "reptile", "vol", "predateur"],
		"butin": ("carcasse", [40, 80], "peu_commun"),
		"visuel": "grand reptile volant sans plumes, ailes membraneuses brun rouge, long bec garni de "
				  "dents pointues, crête osseuse, queue fine ; elle est en vol, ailes déployées",
		"fond": "magenta",
	},
}

ACCORD = ("nom_propre", "pluriel", "h_aspire")

# ── Régions dormantes (Auteur, 17/11) ──────────────────────────────────────────
REGIONS_NEUVES = {
	"asie": {"nom": "Asie", "lieux": []},
	"ameriques": {"nom": "Amériques", "lieux": []},
}

# ── Défauts de rencontre des zones par biome ───────────────────────────────────
# « zone@CODES » ; codes : E europe · N grand_nord · AN afrique_du_nord · A afrique · AS asie ·
# AM ameriques. Les boss, le slime, la Mère-gelée et le lapin cornu n'y figurent pas (Auteur).
REG = {"E": "europe", "N": "grand_nord", "AN": "afrique_du_nord", "A": "afrique", "AS": "asie",
	   "AM": "ameriques"}

ZONES = {
	"kelpie": ["lac@E", "riviere@E"],
	"each_uisge": ["lac@E", "fjord@E,N"],
	"dullahan": ["lande@E", "plaine_ouverte@E", "ruines_maudites@E"],
	"barghest": ["lande@E", "ruines_maudites@E", "bocage@E"],
	"teryel": ["montagne@AN", "contreforts_arides@AN", "foret_chenes_lieges@AN"],
	"impundulu": ["savane@A", "prairie_altitude_tropicale@A", "plateau@A"],
	"tokoloshe": ["savane_arboree@A", "foret_claire_seche@A", "terres_cultivees@A"],
	"kappa": ["riviere@AS", "riziere@AS", "lac@AS"],
	"tengu": ["montagne@AS", "haute_montagne@AS", "foret_mixte_montagne@AS"],
	# Rares et non agressifs (Auteur) : deux zones chacun, IA fuyarde.
	"qilin": ["plaine_ouverte@AS", "foret_bambou@AS"],
	"baku": ["foret_bambou@AS", "foret_persistante@AS"],
	"jorogumo": ["foret_mixte_montagne@AS", "foret_bambou@AS", "cascade@AS"],
	"wendigo": ["taiga@AM", "toundra@AM", "foret_coniferes@AM"],
	"oiseau_tonnerre": ["haute_montagne@AM", "montagne@AM"],
	"mapinguari": ["jungle@AM", "foret_equatoriale@AM"],
	"ahuizotl": ["lac@AM", "riviere@AM"],
	"camazotz": ["grotte@AM", "gouffre@AM", "ruines_maudites@AM"],
	"adze": ["foret_equatoriale@A", "savane_arboree@A", "terres_cultivees@A"],
	"pontianak": ["jungle@AS", "foret_equatoriale@AS", "cote_tropicale@AS"],
	"kongamato": ["fleuve_tropical@A", "marecage_tropical@A", "foret_galerie@A"],
}

# ── Donjons (Auteur, 17/11) : espèces ajoutées à chaque carte de combat du donjon ──
DONJONS = {
	"donjon:orleans_saint_loup": ["lapin_cornu"],
	"donjon:clairiere_du_charbonnier": ["lapin_cornu"],
}

# ── Prompts d'image (docs/prompts_images.md § 3, bloc 0.1 en entier) ───────────
STYLE = ("Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de "
		 "gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions "
		 "crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, "
		 "aucune signature, aucun filigrane.")


def prompt_de(slug: str) -> str:
	spec = NOUVELLES[slug]
	art = "d'une" if accord_de(slug)["genre"] == "f" else "d'un"
	return (f"Réalise l'image {art} {spec['nom']} (une seule créature, isolée) : {spec['visuel']}. "
			"La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue "
			f"de trois-quarts. Fond parfaitement uni et plat, {spec['fond']} pur, sans dégradé, sans décor, "
			"sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche "
			f"de cette couleur. {STYLE}")


def ecrire_prompts() -> int:
	"""Ajoute les prompts absents de dev/batch/monstres/prompts.json (un prompt présent n'est jamais
	réécrit : le lot l'a peut-être déjà généré). Renvoie le nombre d'ajouts."""
	with open(PROMPTS, encoding="utf-8") as f:
		prompts = json.load(f)
	ajouts = 0
	for slug in NOUVELLES:
		if slug in prompts:
			continue
		prompts[slug] = {"espece": "espece:" + slug, "champ_image": None, "prompt": prompt_de(slug)}
		ajouts += 1
	if ajouts:
		with open(PROMPTS, "w", encoding="utf-8") as f:
			json.dump(prompts, f, ensure_ascii=False, indent="\t")
			f.write("\n")
	return ajouts


def image_de(slug: str) -> str:
	"""Fichier détouré du lot s'il existe (manifeste), sinon le nom que le lot lui donnera."""
	try:
		with open(MANIFESTE, encoding="utf-8") as f:
			images = json.load(f).get("images") or {}
	except OSError:
		images = {}
	return images.get(slug) or f"{slug}_transparent.webp"


# ── Construction ───────────────────────────────────────────────────────────────

def _de(nom: str) -> str:
	"""« de Kelpie », « d'Impundulu » (élision devant voyelle ou h muet)."""
	return ("d'" if nom[:1].upper() in "AEIOUÉÈH" else "de ") + nom


def _butin(eid: str, spec: dict) -> dict:
	forme, poids, rarete = spec["butin"]
	nom = spec["nom"]
	if forme == "carcasse":
		titre, sc, icon = "Carcasse", "carcasse", "🥩"
		desc = f"Dépouille {_de(nom)} récupérée à l'issue du combat."
	elif forme == "gelee":
		# Pas une carcasse : ni boucherie, ni découpe (gen_carcasses_parties.est_source).
		titre, sc, icon = "Gelée", "gelee", "🫧"
		desc = f"Gelée {_de(nom)}, encore tiède, recueillie après le combat."
	elif forme == "ossements":
		titre, sc, icon = "Ossements", "ossements", "🦴"
		desc = f"Ossements et reliquats récupérés sur {nom} après sa destruction."
	else:
		titre, sc, icon = "Résidu spectral", "residu_spectral", "👻"
		desc = f"Ce qui reste {_de(nom)} une fois dissipé."
	return {
		"_id": "item:" + eid.split(":", 1)[1], "type": "item", "nom": f"{titre} {_de(nom)}",
		"sous_categorie": sc, "icon": icon, "rarete": rarete, "categorie": "composant", "slots": [],
		"poids": list(poids) if isinstance(poids, list) else poids,
		"description": desc, "source_espece": eid, "loot_defaut": True,
	}


def _espece_brute(slug: str, spec: dict) -> dict:
	"""Doc sans les champs mesurés (effectif, armure, son)."""
	accord = accord_de(slug)
	doc = {"_id": "espece:" + slug, "type": "espece", "nom": spec["nom"], "genre": accord["genre"],
		   **{k: True for k in ACCORD if accord.get(k)}}
	jeton = JETONS[slug]
	if jeton:
		doc["jeton"] = {"taille": jeton[0], "forme": jeton[1]}
	tags = list(spec["tags"]) + [t for t in capacites.MAGIE.get(slug, []) + capacites.IA.get(slug, [])
								 if t not in spec["tags"]]
	doc.update({
		"image": image_de(slug),
		"description": spec["description"],
		"base_attributes": copy.deepcopy(spec["base_attributes"]),
		"tags": tags,
	})
	if slug in KITS and KITS[slug]:
		doc["items"] = ["item:" + i for i in KITS[slug]]
	doc["proprietes"] = {}
	comps = [f"competence:monstre_{c}" for c in capacites.ATTRIBUTION.get(slug, [])]
	if comps:
		doc["competences"] = comps
	return doc


def _son(doc: dict, spec: dict, base: dict) -> str | None:
	"""Cri déjà en base pour la famille de l'espèce (rotation stable sur le slug)."""
	famille = spec.get("son") or sons.famille_de(doc)
	if not famille:
		return None
	choix = sorted(i for i in base if i.startswith(f"{sons.PREFIXE}{famille}_"))
	if not choix:
		return None
	return choix[sum(map(ord, doc["_id"])) % len(choix)]


def controler(base: dict) -> list:
	"""Erreurs fail-closed : tables sources incomplètes, zone ou donjon absent, espèce interdite en zone,
	kit invalide, région inconnue."""
	err = []
	for slug in NOUVELLES:
		if slug not in JETONS:
			err.append(f"espece:{slug} absente de gen_jetons_especes.TABLE")
		if "humanoide" in NOUVELLES[slug]["tags"] and slug not in KITS:
			err.append(f"espece:{slug} humanoïde absente de gen_equipement_humanoides.TABLE")
		for c in capacites.ATTRIBUTION.get(slug, []):
			if c not in capacites.COMPETENCES:
				err.append(f"espece:{slug} : compétence inconnue {c}")
	for slug, entrees in ZONES.items():
		if slug not in NOUVELLES:
			err.append(f"ZONES : {slug} n'est pas une espèce neuve")
			continue
		tags = set(NOUVELLES[slug]["tags"])
		import gen_defauts_zones_biomes as biomes
		if tags & biomes.TAGS_INTERDITS:
			err.append(f"ZONES : {slug} porte un tag interdit en zone ({sorted(tags & biomes.TAGS_INTERDITS)})")
		for brut in entrees:
			z, _, codes = brut.partition("@")
			if "zone:" + z not in base:
				err.append(f"ZONES : zone:{z} absente du dump")
			for c in filter(None, codes.split(",")):
				if c not in REG:
					err.append(f"ZONES : code de région inconnu {c}")
	for did, slugs in DONJONS.items():
		if did not in base:
			err.append(f"{did} absent du dump")
		for s in slugs:
			if s not in NOUVELLES:
				err.append(f"{did} : {s} n'est pas une espèce neuve")
	regions = set(((base.get("rules:regions") or {}).get("regions") or {})) | set(REGIONS_NEUVES)
	for code, rid in REG.items():
		if rid not in regions:
			err.append(f"région {rid} ({code}) inconnue")
	return err


def docs_monstres(base: dict, rangs_fn=None) -> tuple[list, list]:
	"""(docs à importer, ids déjà en base) d'après les docs du dump `base` ({_id: doc}).
	`rangs_fn(docs) → {_id: rang}` mesure les rangs (défaut : le moteur, via gen_armure_naturelle)."""
	erreurs = controler(base)
	if erreurs:
		sys.exit("ERREUR :\n   " + "\n   ".join(erreurs))
	items = {i: d for i, d in base.items() if i.startswith("item:")}
	docs, deja, neufs = [], [], []

	especes = {}
	for slug, spec in NOUVELLES.items():
		doc = _espece_brute(slug, spec)
		if "items" in doc:
			e = erreurs_kit(slug, doc, KITS[slug], items)
			if e:
				sys.exit(f"ERREUR : espece:{slug} : " + " ; ".join(e))
		especes[doc["_id"]] = doc

	# Rang mesuré par le moteur sur la base AUGMENTÉE des espèces neuves (sans armure ni effectif).
	vue = {**base, **especes}
	rangs = (rangs_fn or _rangs_moteur)(list(vue.values()))
	for eid, doc in especes.items():
		spec = NOUVELLES[eid.split(":", 1)[1]]
		rang = rangs.get(eid)
		fourchette = effectifs.fourchette_pour(doc["tags"], rang)
		if fourchette is not None:
			doc["effectif"] = fourchette
		pa = armure.bonus_armure(rang, doc["tags"]) if rang else 0
		if pa:
			doc["armure_naturelle"] = pa
		son = _son(doc, spec, base)
		if son:
			doc["animation"] = son

	for eid, doc in especes.items():
		spec = NOUVELLES[eid.split(":", 1)[1]]
		butin = _butin(eid, spec)
		neufs += [doc, butin]
		for d in (doc, butin):
			(deja if d["_id"] in base else docs).append(d["_id"] if d["_id"] in base else d)

	# Compétences de monstre neuves (foudre, dévoreur de rêves…) : celles qui manquent ou diffèrent.
	for suffixe in sorted({c for s in NOUVELLES for c in capacites.ATTRIBUTION.get(s, [])}):
		comp = capacites.doc_competence(suffixe)
		if comp["_id"] in base and _sans_rev(base[comp["_id"]]) == comp:
			continue
		if comp["_id"] in base:
			deja.append(comp["_id"])  # déjà en base, mais retouchée : gen_capacites_monstres la tranchera
			continue
		docs.append(comp)

	# Découpe des grosses carcasses : même cœur que gen_carcasses_parties, restreint aux neuves.
	carcasses.controler_profils()
	vue = {**base, **{d["_id"]: d for d in neufs}}
	grosses = [s for s, spec in NOUVELLES.items() if spec["butin"][0] == "carcasse"
			   and spec["butin"][1][1] > carcasses.seuil()]
	if grosses:
		sortie, _resume, _ign, _orph, inchanges = carcasses.generer(list(vue.values()), grosses)
		par_id = {d["_id"]: i for i, d in enumerate(docs)}
		for d in sortie:
			if d["_id"] in par_id:
				docs[par_id[d["_id"]]] = d
			elif d["_id"] not in base:
				docs.append(d)
		deja += [i for i in inchanges if i in base and i not in deja]

	# Régions dormantes.
	reg = _sans_rev(base["rules:regions"])
	regions = dict(reg.get("regions") or {})
	manque = {k: v for k, v in REGIONS_NEUVES.items() if k not in regions}
	if manque:
		regions.update(copy.deepcopy(manque))
		reg["regions"] = regions
		docs.append(reg)
	else:
		deja.append("rules:regions")

	# Zones : défauts de rencontre ajoutés (rien n'est retiré ni retouché).
	from utils import zones as moteur_zones
	champ = moteur_zones.CHAMPS_CONTENU[0][2]
	par_zone = {}
	for slug, entrees in ZONES.items():
		for brut in entrees:
			z, _, codes = brut.partition("@")
			e = {"espece": "espece:" + slug}
			if codes:
				e["regions"] = [REG[c] for c in codes.split(",")]
			par_zone.setdefault("zone:" + z, []).append(e)
	for zid in sorted(par_zone):
		zone = _sans_rev(base[zid])
		defauts = [dict(d) for d in zone.get(champ) or []]
		presents = {d.get("espece") for d in defauts}
		ajouts = [e for e in par_zone[zid] if e["espece"] not in presents]
		if not ajouts:
			deja.append(zid)
			continue
		zone[champ] = moteur_zones.normaliser_defauts(defauts + ajouts, "espece")
		docs.append(zone)

	# Donjons : espèce ajoutée à chaque carte de combat qui ne l'a pas.
	for did, slugs in DONJONS.items():
		donjon = _sans_rev(base[did])
		change = False
		for bm in donjon.get("battle_maps") or []:
			lst = list(bm.get("especes") or [])
			for s in slugs:
				if "espece:" + s not in lst:
					lst.append("espece:" + s)
					change = True
			bm["especes"] = lst
		(docs.append(donjon) if change else deja.append(did))

	return docs, deja


def _rangs_moteur(docs: list) -> dict:
	rangs, erreurs = armure.rangs_du_dump(docs)
	for e in erreurs:
		if any(e.startswith("espece:" + s + " ") for s in NOUVELLES):
			sys.exit(f"ERREUR : rang illisible — {e}")
	return rangs


def _dump_le_plus_recent() -> str:
	return armure._dump_le_plus_recent()


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	parser = argparse.ArgumentParser()
	parser.add_argument("--dump", default="")
	parser.add_argument("--prompts", action="store_true", help="ajoute les prompts d'image au lot Gemini")
	args = parser.parse_args()
	if args.prompts:
		print(f"{ecrire_prompts()} prompt(s) ajouté(s) → {os.path.relpath(PROMPTS, RACINE)}")
	source = args.dump or _dump_le_plus_recent()
	base = {d["_id"]: d for d in armure.charger(source) if isinstance(d, dict) and d.get("_id")}
	docs, deja = docs_monstres(base)
	print(f"relu {os.path.relpath(source, RACINE)}")
	for d in docs:
		extra = ""
		if d.get("type") == "espece":
			extra = f"  effectif {d.get('effectif')} · armure {d.get('armure_naturelle', 0)} · {d.get('animation', '—')}"
		print(f"   à importer {d['_id']}{extra}")
	for i in deja:
		print(f"   déjà en base {i}")
	if not docs:
		print("rien à importer — la base est à jour")
		return
	ids = [d["_id"] for d in docs]
	if len(ids) != len(set(ids)):
		sys.exit("ERREUR : _id en double dans la sortie")
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} doc(s) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()

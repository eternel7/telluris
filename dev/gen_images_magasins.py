#!/usr/bin/env python
# dev/gen_images_magasins.py
# Images d'une cité, d'un seul tenant : PORTRAIT de chaque tenancier (§2), FAÇADE de chaque
# boutique (§1 bis) et de chaque auberge. Gabarits : docs/prompts_images.md. API BATCH de Gemini
# (−50 % du prix interactif, résultat sous 24 h).
#
#   python dev/gen_images_magasins.py preparer  --cite lieu:chartres [--sauf lieu:x,lieu:y]
#   python dev/gen_images_magasins.py avancer   --cite …  → l'étape suivante, quelle qu'elle soit (PAYANT)
#   python dev/gen_images_magasins.py essai     --cite … [--seulement …] [--limite N]  → interactif, essais/
#   python dev/gen_images_magasins.py soumettre | etat | recuperer --cite …
#   python dev/gen_images_magasins.py appliquer --cite … → jsons/images_magasins_<cite>_a_importer.json
#
# DEUX lots, enchaînés : la façade joint le portrait de SON tenancier, avant le prompt (« image 1 »),
# il faut donc que ce portrait existe. Chaque soumission envoie tout ce qui est faisable À CE
# MOMENT (`requetes_faisables`) : lot 1 = portraits + auberges (sans tenancier) ; `recuperer`
# réécrit alors requetes.jsonl avec le lot 2 = façades des boutiques. `avancer`, rejoué jusqu'à
# « terminé », soumet / suit / récupère / resoumet sans qu'on ait à savoir où on en est.
# Une requête échouée ou une image rejetée repart dans le lot suivant.
#
# Repli local gratuit : `generer [--essai]` (ComfyUI + FLUX.2 Klein, façades seulement, une fois
# les portraits récupérés). `generer` exige le serveur ComfyUI lancé par
# C:\ComfyUI_windows_portable\run_telluris.bat : `--bf16-text-enc` (l'encodeur Qwen3 déborde en
# fp16 → NaN, image de bruit), `--fp32-vae`, `--disable-smart-memory` (tout déchargé après chaque image).
# Tout l'état vit dans dev/batch/<cite>/images/manifeste.json, sauvé après CHAQUE image : une
# interruption ne perd rien, le rejeu reprend où il s'était arrêté. (Rhemi a été fait avant la
# fusion : dev/batch/rhemi/manifeste.json + magasins/, archives d'un autre format.)
#
# ⚠️ Aucun NOM dans un prompt, ni boutique ni tenancier, ni « Telluris » : le modèle le peint en
# enseigne ou en signature.
# ⚠️ Le portrait montre le tenancier face à nous, qui vend ; la façade le montre AU TRAVAIL
# (consigne de l'auteur, 09/10). Les traits tirés pour le portrait sont REDITS dans la façade.
# ⚠️ Aucune image existante n'est écrasée : prochain `…NN` libre (`nom_libre`). Format natif du
# modèle (Flash Lite → .jpg).
# ⚠️ `appliquer` relit le dump le plus récent et ne change QUE `pnj[0].portrait` et `image`
# (import = PUT complet, CLAUDE.md §11).
# La clé GEMINI_API_KEY est lue dans l'environnement (ou le registre Windows), jamais affichée.

import argparse
import base64
import glob
import io
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_PNJ = os.path.join(RACINE, "templates", "resources", "pnj")
DOSSIER_TOWNS = os.path.join(RACINE, "templates", "resources", "towns")
API = "https://generativelanguage.googleapis.com"
MODELE_GEMINI = "gemini-3.1-flash-lite-image"
RATIO = "16:9"

# Coût réellement observé le 08/10/2026 : 0,16 € pour 4 portraits interactifs → ~0,04 €
# l'image ; le batch en coûte la moitié.
EUR_PAR_IMAGE_INTERACTIF = 0.04
REMISE_BATCH = 0.5

PORTRAIT_GENERIQUE = re.compile(r"^marchand_(elfe|hobbit|humaine?|nain|ogre)_([mf])_")

# Cités dont le doc `lieu:*` n'a pas de label.
NOMS_CITES = {"lieu:rhemi": "Reims"}


# ══ Portrait du tenancier (§2, en français) ═══════════════════════════════════════

# Lignée : repère reconnaissable, jamais une règle de corps (docs/prompts_images.md §2).
LIGNEES = {
	"nain": ("Une naine", "Un nain",
			 "nettement plus petit{e} qu'un humain — un humain se tient au même plan, et {il} lui arrive à peine à la taille —, tête et mains grandes pour sa taille{imberbe}"),
	"hobbit": ("Une hobbit", "Un hobbit",
			   "de toute petite taille d'adulte, pieds nus — un humain au même plan le{a} dépasse de deux têtes"),
	"elfe": ("Une elfe", "Un elfe", "aux oreilles longues et pointues"),
	# Jamais vert (consigne de l'auteur, 09/10).
	"ogre": ("Une ogresse", "Un ogre",
			 "bien plus grand{e} et massi{ve} qu'un humain, peau épaisse au teint humain, jamais verte — un humain au même plan lui arrive à la poitrine"),
	"humain": ("Une humaine", "Un humain", ""),
}
AGES = ["jeune", "dans la force de l'âge", "d'âge mûr", "âgé{e}", "très âgé{e}"]
CORPS = ["maigre", "sec{he}", "de corpulence ordinaire", "solide", "fort{e}", "bedonnant{e}", "voûté{e}"]
ALLURES = ["le regard vif", "l'air bourru", "le sourire facile", "l'œil méfiant", "l'air las mais aimable",
		   "le regard franc", "l'air rusé"]
CHEVEUX = ["aux cheveux noirs", "aux cheveux châtains", "aux cheveux roux", "aux cheveux blonds",
		   "aux cheveux gris", "aux cheveux blancs", "au crâne rasé", "aux cheveux tressés"]

# Métier : (qui il est, objet présenté, tenue, décor). Une ligne par catégorie de base.
METIERS = {
	"apothicairerie": ("tient une apothicairerie", "un petit flacon de remède ambré", "longue blouse tachée d'herbes, sacoche de simples", "étagères de bocaux, bouquets d'herbes séchées, mortier et pilon"),
	"armurerie": ("tient une armurerie", "une épée fraîchement forgée", "tablier de cuir roussi, avant-bras nus couverts de suie", "enclume, forge rougeoyante, râteliers d'armes et de cottes de mailles"),
	"atelier_d_artisan": ("tient un atelier d'artisan", "un coffret de bois sculpté", "tablier de travail plein de copeaux", "établi, outils de menuisier, objets ouvragés en exposition"),
	"atelier_de_cirier": ("tient un atelier de cirier", "un grand cierge de cire blonde", "tablier constellé de gouttes de cire", "cuves de cire, grappes de chandelles suspendues, rayons de miel"),
	"atelier_de_l_empenneur": ("tient un atelier d'empenneur", "une flèche finement empennée", "tablier, plumes piquées au col", "faisceaux de flèches, bottes de plumes, fûts de bois droits"),
	"bijouterie": ("tient une bijouterie", "une bague sertie d'une pierre", "vêtements fins, loupe de bijoutier au cou", "comptoir garni d'écrins, balance de précision, petits bijoux"),
	"boucherie": ("tient une boucherie", "un beau quartier de viande", "tablier taché, couperet à la ceinture", "crochets de viandes suspendues, billot de bois, étal"),
	"boulangerie": ("tient une boulangerie", "une miche de pain doré", "tablier enfariné, manches retroussées", "four à pain, corbeilles de pains et de brioches"),
	"grande_boulangerie": ("tient une grande boulangerie", "une couronne de pain festonnée", "tablier enfariné de maître boulanger, toque de toile", "plusieurs fours à pain, mitrons au travail, paniers de pains et de pâtisseries"),
	"bourrellerie": ("tient une bourrellerie", "un collier de cheval en cuir", "tablier de cuir, alêne à la ceinture", "harnais, selles et sangles pendus aux murs"),
	"boyauderie": ("tient une boyauderie", "un écheveau de corde de boyau", "tablier de cuir humide", "bacs de trempage, cordes de boyau qui sèchent sur des perches"),
	"brosserie": ("tient une brosserie", "une brosse à poils de sanglier", "tablier de toile", "brosses, balais et pinceaux de toutes tailles"),
	"corderie": ("tient une corderie", "un rouleau de corde de chanvre", "vêtements de toile, mains calleuses", "rouet de cordier, rouleaux de cordages"),
	"cordonnerie": ("tient une cordonnerie", "une paire de bottes neuves", "tablier de cuir, marteau de cordonnier", "formes à chaussures, établi, bottes alignées"),
	"cuisine": ("tient une cuisine", "un bol de ragoût fumant", "tablier noué, torchon sur l'épaule", "marmites sur le feu, broche, tables de voyageurs"),
	"etable": ("tient une étable", "un licol de cuir neuf aux boucles de laiton", "tablier de cuir, manches retroussées, brins de paille", "stalles de bois, bottes de foin, une mule et un poney"),
	"fletcher": ("tient une archerie", "un arc long de bois d'if", "brassard de cuir, carquois à l'épaule", "arcs suspendus, flèches en faisceaux, cibles de paille"),
	"fumoir": ("tient un fumoir", "un jambon fumé", "tablier noirci par la fumée", "viandes et poissons pendus dans la fumée, foyer couvant"),
	"jardinier": ("tient une jardinerie", "un panier de légumes frais", "chapeau de paille, tablier de toile terreux", "pots de plantes, semis, outils de jardin"),
	"laboratoire_d_alchimie": ("tient un laboratoire d'alchimie", "une fiole au liquide luminescent", "robe tachée, lunettes de protection relevées sur le front", "alambics, cornues, grimoires ouverts"),
	"lutherie": ("tient une lutherie", "un luth au bois verni", "tablier de luthier, copeaux fins", "instruments suspendus, gabarits, pots de vernis"),
	"maroquinerie": ("tient une maroquinerie", "une sacoche de cuir ouvragé", "tablier de cuir, aiguilles à la ceinture", "bourses, ceintures, sacoches en exposition"),
	"necromancie": ("tient une boutique de nécromancie", "un crâne gravé de runes", "robe sombre, amulettes d'os", "ossements, bougies noires, bocaux troubles, grimoires"),
	"negociant": ("tient une maison de négoce", "une bourse pleine et une balance", "vêtements de marchand aisé, chaîne au cou", "coffres, ballots de marchandises, registres de comptes"),
	"plumasserie": ("tient une plumasserie", "un éventail de plumes chatoyantes", "vêtements soignés, plume au chapeau", "plumes multicolores en bouquets, chapeaux ornés"),
	"salaison": ("tient une salaison", "un saucisson sec", "tablier, mains rougies par le sel", "tonneaux de sel, jambons et saucissons pendus"),
	"savonnerie": ("tient une savonnerie", "un pain de savon parfumé", "tablier clair, manches retroussées", "pains de savon empilés, chaudron, fioles de parfum"),
	"scriptorium": ("tient un scriptorium", "un livre relié de cuir", "robe de scribe, doigts tachés d'encre", "pupitres, encriers, parchemins, piles de livres"),
	"tabletterie": ("tient une tabletterie", "un jeu d'échecs en os et ivoire", "tablier fin, loupe", "petits objets d'os et d'ivoire, peignes, dés, boîtes"),
	"tannerie": ("tient une tannerie", "une peau tannée souple", "tablier de cuir épais, bottes hautes", "peaux tendues sur des cadres, cuves de tan"),
	"taxidermie": ("tient un cabinet de taxidermie", "un renard naturalisé", "blouse de travail, outils fins", "animaux naturalisés, têtes de cerfs, bocaux de spécimens"),
	"tissage": ("tient un atelier de tissage", "une étoffe richement tissée", "vêtements de toile fine", "métier à tisser, rouleaux d'étoffes colorées"),
}

# Style d'Auxerre (§0.1), préféré par l'auteur au photoréaliste du lot de Rhemi (09/10) : même
# rendu que les façades, où ce portrait part en référence.
STYLE_FR = ("Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de "
			"gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse "
			"relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image "
			"entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun "
			"monogramme, aucun filigrane, aucune enseigne lisible.")
# §0.2 (phrase de l'auteur, telle quelle) + la variété de la foule d'Auxerre : sans elle, des
# figurants identiques (lot de Rhemi, 09/10). Ogres jamais verts.
FOULE_FR = ("Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, "
			"chacun différent par l'âge, la carrure, les cheveux et la tenue : elfes bruns, roux, noirs, "
			"argentés ou blonds, en robe, cape de voyage ou cuir ; nains barbus, naines imberbes aux cheveux tressés, en armure, "
			"tablier ou habit de marchand ; hobbits ronds ou fluets, jeunes ou ridés, en gilets colorés ; "
			"ogres aux teints humains, burinés, rougeauds ou hâlés, jamais verts ; humains de toutes "
			"origines, aventuriers, gardes, marchands, pèlerins.")


def _accord(texte, f):
	return (texte.replace("{e}", "e" if f else "").replace("{he}", "he" if f else "")
			.replace("{ve}", "ve" if f else "f").replace("{il}", "elle" if f else "il")
			.replace("{a}", "a" if f else "")
			# Les naines n'ont JAMAIS de barbe (consigne de l'auteur, 10/10).
			.replace("{imberbe}", ", visage parfaitement imberbe, sans aucune barbe" if f else ""))


def tirage_tenancier(rng):
	"""PURE. Traits d'un tenancier, gabarits français NON accordés : [âge, corps, cheveux, allure].
	Servent au portrait ET, traduits (`traits_en`), à la façade — c'est la même personne."""
	return [rng.choice(AGES), rng.choice(CORPS), rng.choice(CHEVEUX), rng.choice(ALLURES)]


def prompt_tenancier(race, sexe, categorie, cite_nom, tirage):
	"""PURE. Prompt du gabarit §2 pour un tenancier (aucun nom propre)."""
	f = sexe == "F"
	une_f, un_m, marqueur = LIGNEES.get(race, LIGNEES["humain"])
	qui, objet, tenue, decor = METIERS[categorie]
	corps = ", ".join(_accord(t, f) for t in tirage)
	il = "Elle" if f else "Il"
	sujet = (une_f if f else un_m) + (f" {corps}" if corps else "") + (f", {_accord(marqueur, f)}" if marqueur else "")
	return (f"Portrait illustré d'un personnage de fantasy médiévale, format paysage large. "
			# Pas de « Telluris » : le mot finissait peint en enseigne (essai des façades, 08/10).
			f"{sujet}. {il} {qui} à {cite_nom}, dans un monde médiéval fantastique. "
			# Lot de Lutecia (10/10) : des tenanciers peints au milieu de la rue (consigne de l'auteur).
			f"La scène se passe À L'INTÉRIEUR de sa boutique, jamais dans la rue : {il.lower()} se tient "
			f"derrière son comptoir, légèrement décalé{'e' if f else ''} du centre, et regarde droit vers le "
			f"spectateur avec l'assurance d'un{'e' if f else ''} commerçant{'e' if f else ''} ; "
			f"{il.lower()} lui présente {objet}. "
			f"Tenue de travail usée et crédible : {tenue}. Tout autour, l'intérieur de la boutique : {decor}. "
			f"La rue n'apparaît qu'au fond, petite, à travers la porte ou la vitrine. "
			f"{FOULE_FR} {STYLE_FR}")


# ══ Façade de boutique ou d'auberge (§1 bis, en anglais) ═══════════════════════════

# Métier : (boutique, marchandises exposées). Mêmes catégories que `METIERS` (verrouillé par test).
METIERS_EN = {
	"apothicairerie": ("apothecary shop", "shelves of jars and vials, bunches of dried herbs, mortar and pestle"),
	"armurerie": ("armorer's forge and shop", "racks of swords and spears, chainmail shirts, helmets, glowing forge"),
	"atelier_d_artisan": ("woodcarver's workshop", "carved wooden boxes, bowls and chairs, workbench with tools"),
	"atelier_de_cirier": ("chandler's workshop", "bunches of hanging candles, large wax tapers, vats of wax, honeycombs"),
	"atelier_de_l_empenneur": ("fletcher's workshop", "bundles of arrows, sheaves of feathers, straight wooden shafts"),
	"bijouterie": ("jeweler's shop", "counter with open jewel cases, rings, necklaces, small precision scale"),
	"boucherie": ("butcher's shop", "meat hanging from hooks, wooden chopping block, cuts of meat on the counter"),
	"boulangerie": ("bakery", "baskets of golden loaves and brioches, bread oven glowing inside"),
	"grande_boulangerie": ("large master bakery", "several glowing bread ovens, bakers' boys at work, piles of loaves, pastries and festive bread crowns"),
	"bourrellerie": ("saddler's and harness maker's shop", "saddles, harnesses, horse collars and straps hanging on the walls"),
	"boyauderie": ("gut-string maker's workshop", "gut strings drying on poles, soaking tubs"),
	"brosserie": ("brush maker's shop", "brushes, brooms and paintbrushes of every size"),
	"corderie": ("rope maker's workshop", "coils of hemp rope, rope-making wheel"),
	"cordonnerie": ("cobbler's shop", "rows of leather boots and shoes, shoe lasts, workbench"),
	"cuisine": ("cookshop", "pots on the fire, roasting spit, steaming stew bowls, tables for travelers"),
	"etable": ("stable", "wooden stalls, hay bales, a mule and a pony, harnesses"),
	"fletcher": ("bowyer and fletcher shop", "longbows hanging, bundles of arrows, quivers, straw targets"),
	"fumoir": ("smokehouse", "hams, sausages and fish hanging in the smoke, smoldering hearth"),
	"jardinier": ("gardener's shop", "potted plants, seedlings, baskets of vegetables, garden tools"),
	"laboratoire_d_alchimie": ("alchemist's laboratory", "alembics, retorts, glowing vials, open grimoires"),
	"lutherie": ("luthier's workshop", "lutes, fiddles and harps hanging, varnish pots"),
	"maroquinerie": ("leather goods shop", "leather bags, purses, belts and satchels on display"),
	"necromancie": ("necromancer's shop", "skulls, bones, black candles, murky jars, dark grimoires"),
	"negociant": ("merchant trading house", "chests, bales of goods, barrels, ledgers and a balance scale"),
	"plumasserie": ("plumassier's shop", "bouquets of colorful feathers, plumed hats, feather fans"),
	# « barrels of salt » → des sacs marqués « SALT » (lot du 09/10).
	"salaison": ("salting house", "open barrels heaped with coarse white salt, hanging hams and dry sausages"),
	"savonnerie": ("soap maker's shop", "stacked bars of soap, cauldron, perfume flasks"),
	"scriptorium": ("scriptorium and bookshop", "writing desks, inkwells, parchments, stacks of leather-bound books"),
	"tabletterie": ("bone and ivory carver's shop", "carved combs, dice, chess sets, small bone boxes"),
	"tannerie": ("tannery", "hides stretched on frames, tanning vats"),
	"taxidermie": ("taxidermist's cabinet", "stuffed animals, deer heads, specimen jars"),
	"tissage": ("weaver's workshop", "loom, rolls of colorful fabric"),
}

# Toponymes d'enseigne → décor de la rue (`{precision_lieu}` + `{repere_cite}` du §1). Clés =
# `TOPONYMES_PAR_LIEU[cite]` (verrouillé par test). Repères réels, aucun symbole religieux.
QUARTIERS_EN = {
	"lieu:rhemi": {
		"du Sacre": "on the square in front of the great gothic cathedral of Reims, its towers rising behind",
		"de la Vesle": "on a quay along the river Vesle, water and a stone bridge nearby",
		"des Coteaux": "on a sloping street of Reims, vineyard hills visible in the distance beyond the ramparts",
		"de la Porte de Mars": ("beside the Porte de Mars, an ancient Roman triumphal arch: three round "
								"classical arches with carved columns, Roman and not gothic"),
		"du Chapitre": "in a narrow lane of old canons' houses at the foot of the gothic cathedral of Reims",
		"des Crayères": "near the entrances of chalk cellars dug into white chalk",
		"du Vieux Cloître": "beside the arcades of an old romanesque cloister",
	},
	"lieu:lutecia": {
		"de la Seine": "on a quay along the river Seine, barges moored at the bank and a stone bridge nearby",
		"du Parvis": ("on the wide square in front of the great gothic cathedral of Notre-Dame on its island, "
					  "its two square towers rising behind"),
		"des Halles": "beside the great covered market halls, crowded with stalls, carts and porters",
		"de la Cité": "in a narrow lane of the island in the middle of the Seine, tall timber-framed houses packed close",
		"du Petit-Pont": "at the foot of a short stone bridge lined with houses, crossing an arm of the Seine",
		"des Écoles": "in a steep street of the schools quarter on the left bank, scholars in long robes carrying books",
		"de la Grève": "on a sloping riverside square of sand and gravel, boats unloading wood and grain on the bank",
		"du Palais": "beside the royal palace on the island, its round towers with pointed roofs rising behind",
		"des Faubourgs": "in a street just outside the city ramparts, gardens and orchards between the houses",
		"de la Montagne": "on a steep hill street climbing above the left bank, old stone walls at the top",
	},
	"lieu:chartres": {
		"de la Porte Guillaume": ("beside the Porte Guillaume, a fortified city gate flanked by two round "
								  "towers, its bridge crossing the river Eure"),
		"de l'Eure": "on a quay along the river Eure, wash-houses and small wooden footbridges over the water",
		"de la Basse-Ville": ("in a steep lane of the lower town, stone stairways climbing toward the "
							  "great cathedral of Chartres on its hill"),
		"du Cloître": ("in the close at the foot of the great gothic cathedral of Chartres, its two "
					   "mismatched spires, one plain and one ornate, rising behind"),
		"du Tertre": "on a steep stepped street running down the hillside, roofs of the lower town below",
		"de Saint-André": "beside a large old romanesque church on the bank of the river Eure",
		"du Pont Bouju": "beside an old stone bridge with low arches over the river Eure",
		"des Épars": "on a wide market square at the edge of the town, near the ramparts",
	},
}

# Lignée : (homme, femme, repère d'échelle) — repère reconnaissable, jamais une règle de corps.
LIGNEES_EN = {
	# Échelle VISIBLE : en photoréaliste, « plus petit » seul ne suffit pas (essai du 09/10 : un
	# nain rendu en humain trapu) — on le compare aux humains qui passent.
	"nain": ("a dwarf man", "a dwarf woman", "so short that the head only reaches the waist of the humans walking past, large head and hands for the size"),
	"hobbit": ("a halfling man", "a halfling woman", "a grown adult with an adult face, barely reaching the hips of the humans around, barefoot with large hairy feet"),
	"elfe": ("an elf man", "an elf woman", "ears only slightly elongated to a subtle point"),
	"ogre": ("an ogre man", "an ogress woman", "towering head and shoulders above the humans around, massive, thick human-toned skin never green, dressed in work clothes"),
	"humain": ("a human man", "a human woman", ""),
}

# Traduction des gabarits de `tirage_tenancier` (NON accordés : la façade est en anglais).
TRAITS_EN = {
	"jeune": "young",
	"dans la force de l'âge": "in the prime of life",
	"d'âge mûr": "middle-aged",
	"âgé{e}": "old",
	"très âgé{e}": "very old",
	"maigre": "skinny",
	"sec{he}": "wiry",
	"de corpulence ordinaire": "of average build",
	"solide": "sturdy",
	"fort{e}": "strong",
	"bedonnant{e}": "pot-bellied",
	"voûté{e}": "stooped",
	"aux cheveux noirs": "black hair",
	"aux cheveux châtains": "brown hair",
	"aux cheveux roux": "red hair",
	"aux cheveux blonds": "blond hair",
	"aux cheveux gris": "grey hair",
	"aux cheveux blancs": "white hair",
	"au crâne rasé": "shaved head",
	"aux cheveux tressés": "braided hair",
	"le regard vif": "sharp eyes",
	"l'air bourru": "gruff look",
	"le sourire facile": "easy smile",
	"l'œil méfiant": "wary eyes",
	"l'air las mais aimable": "tired but kindly look",
	"le regard franc": "frank gaze",
	"l'air rusé": "cunning look",
}

# §0.2 et §0.1 traduits ; la consigne « aucun texte » DOIT être ici (pas de prompt négatif).
# Chaque lignée avec un trait VISIBLE : la phrase nue ne donnait que des humains.
# Essai du 09/10 : « long pointed ears » → des oreilles en cornes ; « tiny halflings » → un bambin.
# Lot de Rhemi (09/10) : « as in the Lord of the Rings films » → costumes de film en série (hobbits
# tous en gilet vert, elfes tous blonds, ogres tous chauves torse nu). L'auteur préfère la foule
# d'Auxerre : chaque passant DIFFÉRENT — d'où les variations explicites par lignée.
FOULE = ("A lively, varied crowd of ogres, dwarves, halflings, elves and humans goes about its business in "
		 "the street, every passer-by different in age, build, hair and outfit, never the same costume "
		 "twice: elves with fine faces and slightly pointed ears, with dark, auburn, black, silver or fair "
		 "hair, in rich robes, travel cloaks or elegant leather armor; dwarves only waist-high to the "
		 "humans, the men with red, black, grey or white beards, the women always beardless with braided hair, in plate armor, smith's aprons or "
		 "merchant clothes; halflings the height of a human child but grown adults with adult faces, "
		 "plump or slim, young or wrinkled, barefoot with curly hair, in colorful waistcoats and skirts; "
		 # Jamais verts (consigne de l'auteur, 09/10) : les teints restent humains, en plus rude.
		 "huge ogres with human skin tones, weathered, ruddy, tanned or ashen, "
		 "never green, in "
		 "tunics, furs or armor, towering over the crowd; humans of every origin: adventurers, guards, "
		 "merchants, pilgrims, peasants. Everyone wears medieval clothing; nothing modern.")
# Style d'Auxerre (§0.1), préféré par l'auteur au photoréaliste du lot de Rhemi (09/10).
STYLE = ("Detailed semi-realistic medieval fantasy illustration in the style of a high-end narrative 2D "
		 "RPG: rich digital painting, warm natural light, warm earthy palette with touches of vivid color "
		 "in clothes, awnings and banners, believable proportions, lots of lively detail. Not a photograph. "
		 "Every building is medieval, stone and timber-framed; nothing modern. "
		 "No text anywhere in the image: no letters, no inscription, no readable sign, no lettering on "
		 "banners or awnings, no logo, no signature, no watermark.")

# Auberges dont l'enseigne ne finit pas par un toponyme (`quartier_de` lit les autres).
QUARTIERS_AUBERGES = {
	"lieu:au_bon_vigneron": "des Coteaux",
	"lieu:la_crayere": "des Crayères",
	"lieu:aux_deux_fleches": "du Cloître",
	"lieu:le_relais_de_l_eure": "de l'Eure",
	"lieu:au_grenier_de_beauce": "de la Porte Guillaume",
	"lieu:la_halte_des_pelerins": "de la Basse-Ville",
}


def traits_en(tirage):
	"""PURE. Les traits du portrait, en anglais, pour la façade (inconnus ignorés)."""
	return [TRAITS_EN[t] for t in tirage or [] if t in TRAITS_EN]


def quartier_de(label, cite):
	"""PURE. Le toponyme d'enseigne qui termine `label` (le plus long gagne), ou None."""
	for t in sorted(QUARTIERS_EN.get(cite, {}), key=len, reverse=True):
		if (label or "").endswith(" " + t):
			return t
	return None


def prompt_magasin(categorie, race, sexe, traits, cite, cite_nom, label):
	"""PURE. Prompt du gabarit §1 bis, en phrases. Ni le nom de la boutique ni celui du tenancier.
	Le tenancier EST la personne de l'image 1 (son portrait, joint en référence) ; lignée et traits
	— ceux qui ont servi à générer ce portrait — ne font que la confirmer."""
	boutique, marchandises = METIERS_EN[categorie]
	t = quartier_de(label, cite)
	lieu = QUARTIERS_EN[cite][t] if t else f"in a street of the walled city of {cite_nom}"
	# `race` None : tenancier d'un portrait EXISTANT dont on ignore la lignée (mode doublons) — la
	# référence seule le décrit, toute précision risquerait de la contredire.
	if race:
		homme, femme, repere = LIGNEES_EN.get(race, LIGNEES_EN["humain"])
		desc = [homme if sexe == "M" else femme] + list(traits) + ([repere] if repere else [])
		if race == "nain" and sexe == "F":   # jamais de barbe (consigne de l'auteur, 10/10)
			desc.append("completely beardless smooth face, no beard at all")
	else:
		desc = list(traits)
	tenancier = f" ({', '.join(desc)})" if desc else ""
	# Petites lignées : sans humain à côté, le modèle les grandissait à l'intérieur de la boutique
	# (hobbit de « La Besogne des Halles », 10/10) — l'échelle doit tenir AUSSI derrière le comptoir.
	echelle = ""
	if race in ("hobbit", "nain"):
		echelle = (" Keep the shopkeeper's small size inside the shop too: the counter reaches the "
				   "shopkeeper's chest, the furniture and tools are made for humans and look large "
				   "next to the shopkeeper, and any human customer at the window is twice as tall.")
	# Le portrait le montre face à nous, souriant, qui vend ; la boutique le montre AU TRAVAIL :
	# lot du 09/10, la pose du portrait était recopiée (consigne de l'auteur).
	return (f"The person shown in image 1 is the shopkeeper: keep exactly the same face, hair, facial hair, "
			f"body, skin and clothes as in image 1{tenancier}, but NOT the same pose or expression. "
			f"Do not reuse the background of image 1. Show this shopkeeper at work in the ground-floor "
			f"shop of a medieval fantasy {boutique} in the city of {cite_nom}, {lieu}, "
			f"busy with the trade, absorbed in the task, not looking at the camera, not posing, not "
			# « open front and market stall » donnait de toutes petites échoppes (lot de Chartres, 10/10).
			f"presenting anything to the viewer. The shop is a solid, permanent town house of two or "
			f"three storeys, built of stone and timber framing, with its own walls, roof and upper "
			f"floors — never a market stall, booth, tent, cart or makeshift lean-to. It fills about 80% "
			f"of the image, seen from the street in a three-quarter view. "
			# Lot de Lutecia (10/10) : boutiques ouvertes sur deux pans de mur (consigne de l'auteur).
			f"Its street wall stays a real wall of stone and timber with a door and ONE shop window "
			f"whose wooden shutter is folded down to serve as the sales counter; the shopkeeper works "
			f"behind that window or just inside the open door. Never two open walls, never a corner "
			f"shop open on two sides, never a front entirely open onto the street. "
			# Lot de Lutecia (10/10) : un faux nom peint sur l'écriteau de « L'Herbier de la Grève ».
			f"No hanging shop sign, no signboard, no name board or plaque above the door or window. "
			f"The goods are displayed on shelves, racks and counters seen through the window and the "
			f"door, and on the shutter counter, and are immediately recognizable: {marchandises}."
			f"{echelle} {FOULE} {STYLE}")


def prompt_auberge(cite, cite_nom, quartier):
	"""PURE. Façade d'auberge (§1 bis sans tenancier : aucun PNJ n'y est posté). Aucun nom propre."""
	lieu = QUARTIERS_EN.get(cite, {}).get(quartier) or f"in a street of the walled city of {cite_nom}"
	return (f"The front of a large medieval fantasy inn and tavern in the city of {cite_nom}, {lieu}. The inn "
			# Pas d'enseigne : « a hanging sign showing only a painted emblem » → faux texte peint ; sans
			# enseigne, il l'a écrit sur un bandeau de façade (essais du 09/10).
			f"fills about 80% of the image, seen from the street in a three-quarter view: a tall stone and "
			f"timber-framed building with bare facade beams — no hanging sign, no signboard, no name board "
			f"or plaque above the door —, wide open door and "
			f"windows revealing a warm firelit common room with long tables, travelers eating and drinking, "
			f"barrels and benches outside the door, a stable yard to one side. {FOULE} {STYLE}")


# ══ Lot ═══════════════════════════════════════════════════════════════════════════

def requete_gemini(prompt, image_b64=None, mime="image/jpeg"):
	"""PURE. Corps `generateContent` : l'image jointe AVANT le texte (c'est l'« image 1 » du prompt)."""
	parts = ([{"inlineData": {"mimeType": mime, "data": image_b64}}] if image_b64 else []) + [{"text": prompt}]
	return {"contents": [{"parts": parts}],
			"generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": RATIO}}}


def entrees_de_cite(lieux, cite, cite_nom, sauf=()):
	"""PURE. (entrées du manifeste, lieux ignorés) pour les boutiques et auberges de `cite`.
	Lignée et sexe lus sur le portrait générique actuel ; traits tirés par une graine propre au
	lieu (re-préparer redonne les mêmes, quel que soit le contenu de la cité)."""
	entrees, ignores = [], []
	for lid, lieu in sorted(lieux.items()):
		if lieu.get("lieu_parent") != cite or lid in sauf:
			continue
		cat, label = lieu.get("categorie"), lieu.get("label")
		if cat == "auberge" and lieu.get("image"):
			q = QUARTIERS_AUBERGES.get(lid) or quartier_de(label, cite)
			entrees.append({"key": lid, "categorie": cat, "quartier": q, "portrait": None,
							"image": {"base": base_image(lieu["image"], cite), "prompt": prompt_auberge(cite, cite_nom, q)}})
			continue
		pnj = (lieu.get("pnj") or [{}])[0]
		m = PORTRAIT_GENERIQUE.match(str(pnj.get("portrait") or ""))
		if not m or cat not in METIERS or not lieu.get("image"):
			ignores.append(f"{lid} ({cat}, portrait {pnj.get('portrait') or '—'}, image {lieu.get('image') or '—'})")
			continue
		race = "humain" if m.group(1) == "humaine" else m.group(1)
		sexe = m.group(2).upper()
		tirage = tirage_tenancier(random.Random(zlib.crc32(lid.encode())))
		entrees.append({
			"key": lid, "categorie": cat, "race": race, "sexe": sexe, "tenancier": pnj.get("nom"),
			"quartier": quartier_de(label, cite), "tirage": tirage,
			"portrait": {"base": f"marchand_{race}_{sexe.lower()}_{cat}",
						 "prompt": prompt_tenancier(race, sexe, cat, cite_nom, tirage)},
			"image": {"base": base_image(lieu["image"], cite),
					  "prompt": prompt_magasin(cat, race, sexe, traits_en(tirage), cite, cite_nom, label)},
		})
	return entrees, ignores


# Lignée d'un tenancier nouveau : chances ÉGALES (consigne de l'auteur, 10/10).
LIGNEES_TIRAGE = ["humain", "elfe", "nain", "hobbit", "ogre"]


def _entree_refaite(lid, lieu, cite, cite_nom, refaire_por, refaire_img, conserves):
	"""PURE. Entrée du manifeste pour UNE boutique dont on refait le portrait et/ou la façade ; la
	partie gardée est inscrite dans `conserves` (fichier actuel, jamais régénéré). Lignée et sexe :
	ceux du portrait générique s'il l'était, sinon tirés par une graine propre au lieu — à chances
	ÉGALES (consigne de l'auteur, 10/10) — quand le portrait est refait, inconnus sinon."""
	pnj = (lieu.get("pnj") or [{}])[0]
	cat, label, por = lieu.get("categorie"), lieu.get("label"), pnj.get("portrait") or ""
	rng = random.Random(zlib.crc32(lid.encode()))
	tirage = tirage_tenancier(rng)
	m = PORTRAIT_GENERIQUE.match(por)
	race = ("humain" if m.group(1) == "humaine" else m.group(1)) if m else None
	sexe = m.group(2).upper() if m else None
	if refaire_por and not m:
		race, sexe = rng.choice(LIGNEES_TIRAGE), rng.choice("MF")
	if not refaire_por:
		conserves["portraits"][lid] = por
	if not refaire_img:
		conserves["images"][lid] = lieu.get("image")
	return {"key": lid, "categorie": cat, "race": race, "sexe": sexe, "tenancier": pnj.get("nom"),
			"quartier": quartier_de(label, cite), "tirage": tirage if refaire_por else None,
			"doublon": [x for x, oui in (("portrait", refaire_por), ("image", refaire_img)) if oui],
			"portrait": {"base": f"marchand_{race or 'humain'}_{(sexe or 'm').lower()}_{cat}",
						 "prompt": prompt_tenancier(race, sexe, cat, cite_nom, tirage) if refaire_por else None},
			"image": {"base": base_image(lieu.get("image"), cite),
					  "prompt": prompt_magasin(cat, race, sexe, traits_en(tirage) if refaire_por else [],
											   cite, cite_nom, label)}}


def entrees_a_refaire(lieux, cite, cite_nom, cles):
	"""PURE. (entrées, conservés, ignorés) pour des boutiques DÉSIGNÉES (revue de l'auteur) : la
	façade est toujours refaite ; le portrait aussi s'il n'est pas un portrait de marchand
	(`marchand_*`) — un guerrier ou un clerc pris dans le fonds des personnages."""
	entrees, ignores = [], []
	conserves = {"portraits": {}, "images": {}}
	for lid in sorted(cles):
		lieu = lieux.get(lid)
		if not lieu or lieu.get("lieu_parent") != cite:
			ignores.append(f"{lid} (absent de {cite})")
			continue
		if lieu.get("categorie") not in METIERS:
			ignores.append(f"{lid} ({lieu.get('categorie')} : métier sans gabarit)")
			continue
		por = str(((lieu.get("pnj") or [{}])[0]).get("portrait") or "")
		entrees.append(_entree_refaite(lid, lieu, cite, cite_nom, not por.startswith("marchand_"), True, conserves))
	return entrees, conserves, ignores


def entrees_doublons(lieux, cite, cite_nom):
	"""PURE. (entrées, conservés, ignorés) pour les boutiques de `cite` dont la FAÇADE ou le
	PORTRAIT est un doublon — fichier aussi posé sur un autre lieu, n'importe où.

	Le PROPRIÉTAIRE d'un fichier partagé le garde : un lieu hors de `cite` d'abord (Auxerre a
	précédé Lutecia : c'est la copie qu'on remplace), sinon le premier de `cite` par id. Tous les
	autres porteurs de `cite` sont refaits — seulement la partie en doublon :
	  · portrait refait → façade refaite aussi seulement si elle est elle-même en doublon ;
	  · façade seule → elle joint le portrait EXISTANT (`conserves["portraits"]`), sans redire
	    des traits qu'on ignore ;
	  · portrait seul → la façade existante est gardée (`conserves["images"]`).
	Seuls les marchands (`pnj:marchand_*`) : un portrait de PNJ nommé n'est pas un doublon à
	refaire. Lignée et sexe d'un portrait refait : ceux du portrait générique s'il l'était,
	sinon tirés par une graine propre au lieu (c'est un nouveau tenancier)."""
	usage_img, usage_por = {}, {}
	for lid, lieu in lieux.items():
		if lieu.get("image"):
			usage_img.setdefault(lieu["image"], []).append(lid)
		for p in lieu.get("pnj") or []:
			if p.get("portrait"):
				usage_por.setdefault(p["portrait"], []).append(lid)

	def proprietaire(porteurs):
		hors = sorted(p for p in porteurs if (lieux.get(p) or {}).get("lieu_parent") != cite)
		return hors[0] if hors else sorted(porteurs)[0]

	def doublon(usage, fichier, lid):
		porteurs = usage.get(fichier) or []
		return len(porteurs) > 1 and proprietaire(porteurs) != lid

	entrees, ignores = [], []
	conserves = {"portraits": {}, "images": {}}
	for lid, lieu in sorted(lieux.items()):
		if lieu.get("lieu_parent") != cite:
			continue
		pnj = (lieu.get("pnj") or [{}])[0]
		if not str(pnj.get("character") or "").startswith("pnj:marchand_"):
			continue
		cat, label, por = lieu.get("categorie"), lieu.get("label"), pnj.get("portrait") or ""
		refaire_img = doublon(usage_img, lieu.get("image"), lid)
		refaire_por = bool(por) and doublon(usage_por, por, lid)
		if not (refaire_img or refaire_por):
			continue
		if cat not in METIERS:
			ignores.append(f"{lid} ({cat} : métier sans gabarit)")
			continue
		entrees.append(_entree_refaite(lid, lieu, cite, cite_nom, refaire_por, refaire_img, conserves))
	return entrees, conserves, ignores


def prompt_tenancier_depuis_facade(race, sexe, categorie, cite_nom):
	"""PURE. Portrait (§2) du tenancier VISIBLE sur une façade déjà générée, jointe en image 1 :
	la façade est gardée pour un lieu ultérieur (consigne de l'auteur, 10/10), il lui faut son
	marchand. Mêmes règles que `prompt_tenancier` ; les traits sont ceux de l'image, pas tirés."""
	f = sexe == "F"
	return (f"La personne au travail dans la boutique de l'image 1 est le sujet de ce portrait : garde "
			f"exactement son visage, ses cheveux, sa carrure, sa peau et sa tenue, mais PAS sa pose, et ne "
			f"reprends pas le décor de l'image 1. " + prompt_tenancier(race, sexe, categorie, cite_nom, []))


def requetes_faisables(man):
	"""PURE. [(clé du lot, entrée, genre)] de ce qui peut partir MAINTENANT : un portrait
	manquant ; une façade manquante dont le portrait existe (ou qui n'en a pas : auberge)."""
	sortie = []
	for e in man["entrees"]:
		k = e["key"]
		if e.get("portrait") and k not in man["portraits"]:
			sortie.append((f"portrait|{k}", e, "portrait"))
		if k not in man["images"] and (not e.get("portrait") or k in man["portraits"]):
			sortie.append((f"image|{k}", e, "image"))
	return sortie


def image_de_reponse(reponse):
	"""PURE. La première partie `inlineData` d'une réponse `generateContent`, ou None."""
	return next((p for c in (reponse or {}).get("candidates", [])
				 for p in (c.get("content") or {}).get("parts", []) if "inlineData" in p), None)


# Image ratée par le GPU (NaN dans le sampler) : gris uniforme ou bruit pur. Étalonné le 08/10 :
# bonnes images (générées ou de `towns/`) écart-type 50-78, écart entre voisins 5-10 ; gris
# uniforme écart-type 4,5 ; bruit écart entre voisins ~45.
SEUIL_ECART_TYPE, SEUIL_VOISINS = 15, 25


def image_degeneree(ecart_type, ecart_voisins):
	"""PURE. Motif du rejet d'une image (écart-type et écart moyen entre pixels voisins, en
	niveaux de gris 0-255), ou None si elle est plausible."""
	if ecart_type < SEUIL_ECART_TYPE:
		return "uniforme"
	if ecart_voisins > SEUIL_VOISINS:
		return "bruit"
	return None


def base_image(image, cite):
	"""PURE. `archerie_europe01.png` → `archerie_europe_rhemi` (cf. `auberge_europe_lutecia*`)."""
	tige = re.sub(r"\d*$", "", os.path.splitext(image or "")[0]).rstrip("_")
	suffixe = f"_{cite.split(':', 1)[-1]}"
	# Image déjà générée pour la cité (`…_lutecia01.jpg`) : sans ce garde, `…_lutecia_lutecia`.
	return tige if tige.endswith(suffixe) else tige + suffixe


def nom_libre(dossier, base, ext, pris=()):
	"""Prochain `base01.ext`, `base02.ext`… dont le NOM SANS EXTENSION est absent du disque ET
	de `pris` : `…01.png` existant interdit aussi `…01.jpg` (jamais d'écrasement, jamais deux
	fichiers au même nom)."""
	tiges = {os.path.splitext(f)[0] for f in os.listdir(dossier)} | {os.path.splitext(p)[0] for p in pris}
	n = 1
	while f"{base}{n:02d}" in tiges:
		n += 1
	return f"{base}{n:02d}{ext}"


# ── E/S ─────────────────────────────────────────────────────────────────────────

def _slug(cite):
	return cite.split(":", 1)[-1]


def _dump_le_plus_recent():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json.")
	return dumps[-1]


def _docs(chemin):
	with open(chemin, encoding="utf-8") as f:
		d = json.load(f)
	return d["docs"] if isinstance(d, dict) and "docs" in d else d


def _cle():
	k = os.environ.get("GEMINI_API_KEY")
	if not k and sys.platform == "win32":
		import winreg
		with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
			k = winreg.QueryValueEx(h, "GEMINI_API_KEY")[0]
	if not k:
		raise SystemExit("ERREUR : GEMINI_API_KEY absente.")
	return k


def _http(url, corps=None, entetes=None, methode=None, brut=False):
	donnees = corps if isinstance(corps, (bytes, type(None))) else json.dumps(corps).encode()
	h = {"x-goog-api-key": _cle(), **({"Content-Type": "application/json"} if donnees and not brut else {}),
		 **(entetes or {})}
	req = urllib.request.Request(url, data=donnees, headers=h, method=methode or ("POST" if donnees else "GET"))
	try:
		with urllib.request.urlopen(req, timeout=300) as r:
			return r.headers, r.read()
	except urllib.error.HTTPError as e:
		raise SystemExit(f"HTTP {e.code} : {e.read().decode('utf-8', 'replace')[:800]}")


def _dossier(cite):
	d = os.path.join(RACINE, "dev", "batch", _slug(cite), "images")
	os.makedirs(d, exist_ok=True)
	return d


def _chemin_manifeste(cite):
	return os.path.join(_dossier(cite), "manifeste.json")


def _chemin_requetes(cite):
	return os.path.join(_dossier(cite), "requetes.jsonl")


def _manifeste(cite, nouveau=None):
	chemin = _chemin_manifeste(cite)
	if nouveau is not None:
		with open(chemin, "w", encoding="utf-8") as f:
			json.dump(nouveau, f, ensure_ascii=False, indent="\t")
		return nouveau
	if not os.path.exists(chemin):
		raise SystemExit("ERREUR : lancer d'abord `preparer`.")
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def _portrait_b64(chemin):
	"""Portrait du tenancier ramené à ~1 Mpx en JPEG puis base64 : bruts, les 62 portraits
	(~1,2 Mo chacun) gonflaient le JSONL du lot sans rien apporter à la référence."""
	from PIL import Image
	im = Image.open(chemin).convert("RGB")
	r = (1_000_000 / (im.width * im.height)) ** 0.5
	if r < 1:
		im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
	tampon = io.BytesIO()
	im.save(tampon, "JPEG", quality=90)
	return base64.b64encode(tampon.getvalue()).decode("ascii")


def _requete(e, genre, chemin_portrait=None):
	"""Corps de la requête : le portrait seul, ou la façade qui joint `chemin_portrait` (auberge : rien)."""
	if genre == "portrait":
		return requete_gemini(e["portrait"]["prompt"])
	return requete_gemini(e["image"]["prompt"], _portrait_b64(chemin_portrait) if chemin_portrait else None)


def _ecrire_requetes(cite, man):
	"""Réécrit requetes.jsonl avec ce qui peut partir maintenant ; rend le nombre de requêtes."""
	faisables = requetes_faisables(man)
	with open(_chemin_requetes(cite), "w", encoding="utf-8") as f:
		for cle, e, genre in faisables:
			nom = man["portraits"].get(e["key"]) if genre == "image" else None
			requete = _requete(e, genre, os.path.join(DOSSIER_PNJ, nom) if nom else None)
			f.write(json.dumps({"key": cle, "request": requete}, ensure_ascii=False) + "\n")
	return len(faisables)


def _resume_lot(cite, man):
	faisables = requetes_faisables(man)
	n_p = sum(1 for _, _, g in faisables if g == "portrait")
	n_i = len(faisables) - n_p
	attente = sum(1 for e in man["entrees"] if e.get("portrait") and e["key"] not in man["portraits"]
				  and e["key"] not in man["images"])
	unit = EUR_PAR_IMAGE_INTERACTIF * REMISE_BATCH
	print(f"Prochain lot : {n_p} portrait(s) + {n_i} façade(s) → {os.path.relpath(_chemin_requetes(cite), RACINE)}"
		  f" ; ≈ {len(faisables) * unit:.2f} €")
	if attente:
		print(f"  puis {attente} façade(s) de boutique, au lot suivant (≈ {attente * unit:.2f} €) :"
			  " elles joignent le portrait de leur tenancier.")


def _mesures(octets):
	"""(écart-type, écart moyen entre voisins horizontaux) de l'image en niveaux de gris."""
	from PIL import Image, ImageChops, ImageStat
	g = Image.open(io.BytesIO(octets)).convert("L")
	w, h = g.size
	voisins = ImageChops.difference(g.crop((0, 0, w - 1, h)), g.crop((1, 0, w, h)))
	return ImageStat.Stat(g).stddev[0], ImageStat.Stat(voisins).mean[0]


def _ecrire_image(dossier, base, part, pris):
	"""Écrit l'image d'une réponse Gemini sous le prochain nom libre ; (nom, None) ou (None, motif)."""
	octets = base64.b64decode(part["inlineData"]["data"])
	rejet = image_degeneree(*_mesures(octets))
	if rejet:
		return None, f"image {rejet}"
	ext = ".jpg" if "jpeg" in part["inlineData"].get("mimeType", "") else ".png"
	nom = nom_libre(dossier, base, ext, pris)
	with open(os.path.join(dossier, nom), "wb") as f:
		f.write(octets)
	return nom, None


def soumettre_lot(chemin_jsonl, modele, nom_affiche):
	"""Envoie un fichier de requêtes JSONL à l'API batch (PAYANT) ; rend le nom du lot."""
	octets = open(chemin_jsonl, "rb").read()
	h, _ = _http(f"{API}/upload/v1beta/files", {"file": {"display_name": nom_affiche}}, {
		"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
		"X-Goog-Upload-Header-Content-Length": str(len(octets)),
		"X-Goog-Upload-Header-Content-Type": "application/jsonl"})
	_, rep = _http(h["x-goog-upload-url"], octets, {"X-Goog-Upload-Offset": "0",
												   "X-Goog-Upload-Command": "upload, finalize"}, brut=True)
	fichier = json.loads(rep)["file"]["name"]
	_, rep = _http(f"{API}/v1beta/models/{modele}:batchGenerateContent",
				   {"batch": {"display_name": nom_affiche, "input_config": {"file_name": fichier}}})
	return json.loads(rep)["name"]


def statut_lot(lot):
	_, rep = _http(f"{API}/v1beta/{lot}")
	return json.loads(rep)


# L'API répond `BATCH_STATE_*` (constaté le 08/10/2026) ; la doc écrit `JOB_STATE_*`.
ETATS_REUSSIS = ("BATCH_STATE_SUCCEEDED", "JOB_STATE_SUCCEEDED")
ETATS_ECHOUES = ("BATCH_STATE_FAILED", "BATCH_STATE_CANCELLED", "BATCH_STATE_EXPIRED",
				 "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED")


def reponses_lot(lot):
	"""[(clé, partie inlineData | None, ligne brute)] d'un lot terminé ; SystemExit sinon."""
	s = statut_lot(lot)
	meta = s.get("metadata") or {}
	if meta.get("state") not in ETATS_REUSSIS and not s.get("done"):
		raise SystemExit(f"Lot pas terminé : {meta.get('state')}")
	rep = (s.get("response") or {}).get("responsesFile") or ((meta.get("output") or {}).get("responsesFile"))
	if not rep:
		raise SystemExit("Aucun fichier de réponses : " + json.dumps(s)[:600])
	_, brut = _http(f"{API}/download/v1beta/{rep}:download?alt=media")
	sortie = []
	for ligne in brut.decode("utf-8").splitlines():
		if ligne.strip():
			r = json.loads(ligne)
			sortie.append((r.get("key"), image_de_reponse(r.get("response")), r))
	return sortie


# ── ComfyUI (repli local, façades seulement) ────────────────────────────────────

COMFY = "http://127.0.0.1:8188"
# FLUX.2 Klein 4B distillé, graphe du modèle officiel ComfyUI `image_flux2_klein_image_edit_4b_
# distilled` : le PORTRAIT du tenancier part en image de référence (`ReferenceLatent`), pour que
# ce soit bien LE marchand de la boutique. Écartés : DreamShaper XL (08/10, lignées ignorées,
# foule absente) et Z-Image Turbo (09/10, bon rendu mais sans image de référence possible).
# Poids fp8 (~4 Go) : l'iGPU plafonne à 14,4 Go et annonce 0 Go libre dès qu'on en tient ~10
# (`torch.cuda.mem_get_info`, mesuré le 08/10).
MODELE_COMFY = "flux-2-klein-4b-fp8.safetensors"
ENCODEUR = "qwen_3_4b_fp8_mixed.safetensors"
VAE = "flux2-vae.safetensors"
# 16:9, la taille des images de `towns/`.
LARGEUR, HAUTEUR = 1408, 768
PAS, CFG, SAMPLER = 4, 1.0, "euler"


def _comfy(chemin, corps=None):
	req = urllib.request.Request(COMFY + chemin, data=json.dumps(corps).encode() if corps is not None else None,
								 headers={"Content-Type": "application/json"} if corps is not None else {})
	with urllib.request.urlopen(req, timeout=30) as r:
		return r.read()


def _liberer():
	"""Décharge modèles et mémoire de ComfyUI. ⚠️ Sur la Radeon 890M (mémoire partagée), la
	mémoire n'est pas rendue entre deux images : la suivante sortait en bruit ou en gris (NaN),
	ou échouait en « Not enough memory … Have: 0.0GB free ». Constaté le 08/10."""
	_comfy("/free", {"unload_models": True, "free_memory": True})


def _envoyer_portrait(nom):
	"""Dépose le portrait du tenancier dans le dossier `input/` de ComfyUI ; rend son nom là-bas."""
	with open(os.path.join(DOSSIER_PNJ, nom), "rb") as f:
		octets = f.read()
	borne = "----telluris" + zlib.crc32(octets).__format__("x")
	corps = (f"--{borne}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
			 f"--{borne}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{nom}\"\r\n"
			 f"Content-Type: application/octet-stream\r\n\r\n").encode() + octets + f"\r\n--{borne}--\r\n".encode()
	req = urllib.request.Request(COMFY + "/upload/image", data=corps,
								 headers={"Content-Type": f"multipart/form-data; boundary={borne}"})
	with urllib.request.urlopen(req, timeout=60) as r:
		return json.loads(r.read())["name"]


def _workflow(prompt, graine, portrait):
	return {
		"1": {"class_type": "UNETLoader", "inputs": {"unet_name": MODELE_COMFY, "weight_dtype": "default"}},
		"2": {"class_type": "CLIPLoader", "inputs": {"clip_name": ENCODEUR, "type": "flux2", "device": "default"}},
		"3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
		"4": {"class_type": "LoadImage", "inputs": {"image": portrait}},
		"5": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["4", 0], "upscale_method": "nearest-exact",
			"megapixels": 1.0, "resolution_steps": 1}},
		"6": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
		"7": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
		"8": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["7", 0]}},
		"9": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["7", 0], "latent": ["6", 0]}},
		"10": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["8", 0], "latent": ["6", 0]}},
		"11": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["9", 0], "negative": ["10", 0], "cfg": CFG}},
		"12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": SAMPLER}},
		"13": {"class_type": "Flux2Scheduler", "inputs": {"steps": PAS, "width": LARGEUR, "height": HAUTEUR}},
		"14": {"class_type": "RandomNoise", "inputs": {"noise_seed": graine}},
		"15": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": LARGEUR, "height": HAUTEUR, "batch_size": 1}},
		"16": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["14", 0], "guider": ["11", 0],
			"sampler": ["12", 0], "sigmas": ["13", 0], "latent_image": ["15", 0]}},
		"17": {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["3", 0]}},
		"18": {"class_type": "SaveImage", "inputs": {"images": ["17", 0], "filename_prefix": "telluris_magasin"}},
	}


# ── Étapes ──────────────────────────────────────────────────────────────────────

def _lieux(source=None):
	"""Lieux du dump le plus récent, ÉCRASÉS par ceux de `source` (export `/admin/exports` plus
	frais) : l'import est un PUT complet, il doit repartir de l'état réellement en base."""
	lieux = {d["_id"]: d for d in _docs(_dump_le_plus_recent()) if d.get("type") == "lieu"}
	if source:
		lieux.update({d["_id"]: d for d in _docs(source) if d.get("type") == "lieu"})
	return lieux


def lignee_du_tenancier(lieu, entree=None):
	"""PURE. (race, sexe) du tenancier : celle de l'entrée du manifeste si son portrait est
	refait, sinon lue sur le portrait générique ; None si inconnue."""
	if entree and "portrait" in (entree.get("doublon") or ["portrait"]) and entree.get("race"):
		return entree["race"], entree["sexe"]
	m = PORTRAIT_GENERIQUE.match(str(((lieu.get("pnj") or [{}])[0]).get("portrait") or ""))
	if not m:
		return None
	return ("humain" if m.group(1) == "humaine" else m.group(1)), m.group(2).upper()


def noms_manquants(lieux, cite, entrees, repertoire, tirer_nom):
	"""PURE (`tirer_nom` injecté). {lieu: nom} pour chaque marchand de `cite` sans `nom` :
	prénom + nom du répertoire du recrutement selon sa lignée, graine propre au lieu, jamais un
	nom déjà porté par un PNJ d'un lieu. Les tenanciers de lignée inconnue sont rendus à part."""
	par_cle = {e["key"]: e for e in entrees}
	pris = {p.get("nom") for l in lieux.values() for p in (l.get("pnj") or []) if p.get("nom")}
	noms, inconnus = {}, []
	for lid, lieu in sorted(lieux.items()):
		pnj = (lieu.get("pnj") or [{}])[0]
		if (lieu.get("lieu_parent") != cite or pnj.get("nom")
				or not str(pnj.get("character") or "").startswith("pnj:marchand_")):
			continue
		lignee = lignee_du_tenancier(lieu, par_cle.get(lid))
		if not lignee:
			inconnus.append(lid)
			continue
		noms[lid] = tirer_nom(lignee[0], lignee[1], random.Random(zlib.crc32(("nom|" + lid).encode())),
							  repertoire, pris)
	return noms, inconnus


def preparer(cite, sauf, doublons=False, refaire=(), source=None):
	lieux = _lieux(source)
	# Boutiques pas encore importées : complétées depuis l'import du peuplement (le dump prime).
	imp = os.path.join(RACINE, "jsons", f"{_slug(cite)}_magasins_a_importer.json")
	if os.path.exists(imp):
		for d in _docs(imp):
			if d.get("type") == "lieu":
				lieux.setdefault(d["_id"], d)
	cite_nom = (lieux.get(cite) or {}).get("label") or NOMS_CITES.get(cite) or _slug(cite).capitalize()
	conserves = {"portraits": {}, "images": {}}
	if doublons or refaire:
		entrees, conserves, ignores = (entrees_doublons(lieux, cite, cite_nom) if doublons
									   else ([], {"portraits": {}, "images": {}}, []))
		# `--refaire` l'emporte : l'entrée désignée REMPLACE celle des doublons.
		e_r, c_r, i_r = entrees_a_refaire(lieux, cite, cite_nom, refaire)
		entrees = [e for e in entrees if e["key"] not in refaire] + e_r
		for genre in conserves:
			conserves[genre] = {k: v for k, v in conserves[genre].items() if k not in refaire} | c_r[genre]
		ignores += i_r
		entrees = [e for e in entrees if e["key"] not in sauf]
	else:
		entrees, ignores = entrees_de_cite(lieux, cite, cite_nom, sauf)
	ancien = {}
	if os.path.exists(_chemin_manifeste(cite)):
		ancien = _manifeste(cite)
		if ancien.get("batch"):
			raise SystemExit(f"Lot en cours : {ancien['batch']} — `recuperer` avant de re-préparer.")
	cles = {e["key"] for e in entrees}
	# Une boutique à REFAIRE perd ce qu'un lot précédent lui avait généré : la partie refaite
	# repart, la partie gardée revient au fichier actuel (`conserves`).
	for genre in ("portraits", "images"):
		for k in refaire:
			(ancien.get(genre) or {}).pop(k, None)
	# Images déjà générées conservées : seules les manquantes repartent. Mode doublons : la partie
	# qui n'est PAS en doublon compte comme acquise (fichier actuel), donc jamais régénérée.
	man = {"cite": cite, "modele": MODELE_GEMINI, "entrees": entrees, "batch": None, "source": source,
		   "portraits": {**{k: v for k, v in conserves["portraits"].items() if k in cles},
						 **{k: v for k, v in (ancien.get("portraits") or {}).items() if k in cles}},
		   "images": {**{k: v for k, v in conserves["images"].items() if k in cles},
					  **{k: v for k, v in (ancien.get("images") or {}).items() if k in cles}},
		   "lots": ancien.get("lots") or []}
	_ecrire_requetes(cite, man)
	_manifeste(cite, man)
	n_aub = sum(1 for e in entrees if not e.get("portrait"))
	print(f"{len(entrees)} lieux préparés ({len(entrees) - n_aub} boutique(s), {n_aub} auberge(s))"
		  f" → {os.path.relpath(_chemin_manifeste(cite), RACINE)}"
		  f" ({len(man['portraits'])} portrait(s), {len(man['images'])} façade(s) déjà générés)")
	_resume_lot(cite, man)
	for i in ignores:
		print("  ignoré :", i)


def soumettre(cite):
	man = _manifeste(cite)
	if man.get("batch"):
		raise SystemExit(f"Déjà soumis : {man['batch']} — `etat` pour suivre.")
	n = _ecrire_requetes(cite, man)
	if not n:
		raise SystemExit("Rien à soumettre : toutes les images sont générées — `appliquer`.")
	man["batch"] = soumettre_lot(_chemin_requetes(cite), man["modele"], f"images-{cite}-{len(man['lots']) + 1}")
	_manifeste(cite, man)
	print(f"Lot soumis ({n} requête(s)) :", man["batch"])


def etat(cite):
	man = _manifeste(cite)
	if not man.get("batch"):
		raise SystemExit("Aucun lot en cours.")
	s = statut_lot(man["batch"])
	meta = s.get("metadata") or s
	print(man["batch"], "→", meta.get("state"), "| stats :", meta.get("batchStats"))
	return meta.get("state"), s.get("done")


def recuperer(cite):
	"""Écrit portraits (pnj/) et façades (towns/) du lot, CLÔT le lot (`lots`) et réécrit
	requetes.jsonl avec la suite : les façades dont le portrait vient d'arriver, et les échecs."""
	man = _manifeste(cite)
	if not man.get("batch"):
		raise SystemExit("Aucun lot en cours.")
	par_cle = {e["key"]: e for e in man["entrees"]}
	ecrites, erreurs = 0, []
	for cle, part, r in reponses_lot(man["batch"]):
		genre, _, lid = (cle or "").partition("|")
		e = par_cle.get(lid)
		cible = {"portrait": man["portraits"], "image": man["images"]}.get(genre)
		if e is None or cible is None or lid in cible:
			continue
		if not part:
			erreurs.append(f"{cle} : {json.dumps(r.get('error') or r)[:200]}")
			continue
		dossier = DOSSIER_PNJ if genre == "portrait" else DOSSIER_TOWNS
		nom, motif = _ecrire_image(dossier, e[genre]["base"], part, set(cible.values()))
		if not nom:
			erreurs.append(f"{cle} : {motif}")
			continue
		cible[lid] = nom
		ecrites += 1
	man["lots"].append(man["batch"])
	man["batch"] = None
	_ecrire_requetes(cite, man)
	_manifeste(cite, man)
	print(f"{ecrites} image(s) écrite(s) ; {len(erreurs)} échec(s) — "
		  f"{len(man['portraits'])} portrait(s), {len(man['images'])}/{len(man['entrees'])} façade(s)")
	for e in erreurs:
		print("  ✗", e)
	_resume_lot(cite, man)


def avancer(cite):
	"""L'étape suivante, quelle qu'elle soit : soumettre (PAYANT), suivre, récupérer puis
	resoumettre la suite. À rejouer jusqu'à « terminé »."""
	man = _manifeste(cite)
	if man.get("batch"):
		state, done = etat(cite)
		if state in ETATS_ECHOUES:
			print("⚠ Lot en échec : retiré, ses requêtes repartiront au prochain `avancer`.")
			man["lots"].append(man["batch"])
			man["batch"] = None
			_manifeste(cite, man)
			return
		if state not in ETATS_REUSSIS and not done:
			print("En cours — rejouer `avancer` plus tard.")
			return
		recuperer(cite)
		man = _manifeste(cite)
	if requetes_faisables(man):
		soumettre(cite)
	else:
		print("Terminé : toutes les images sont générées — `appliquer`.")


def essai(cite, seulement, limite):
	"""Gemini INTERACTIF (~0,04 €/image) dans dev/batch/<cite>/images/essais/ : ni pnj/, ni towns/,
	ni le manifeste ne bougent — pour juger les gabarits avant de payer le lot. Une boutique coûte
	deux images : son portrait, puis sa façade qui le joint."""
	man = _manifeste(cite)
	dossier = os.path.join(_dossier(cite), "essais")
	os.makedirs(dossier, exist_ok=True)
	a_faire = [e for e in man["entrees"] if not seulement or e["key"] in seulement]
	if limite:
		a_faire = a_faire[:limite]
	def _refait_portrait(e):
		return bool(e.get("portrait")) and "portrait" in (e.get("doublon") or ["portrait"])

	n = sum(2 if _refait_portrait(e) else 1 for e in a_faire)
	print(f"{n} essai(s), ≈ {n * EUR_PAR_IMAGE_INTERACTIF:.2f} €")

	def _un(requete, base):
		t0 = time.time()
		_, rep = _http(f"{API}/v1beta/models/{man['modele']}:generateContent", requete)
		part = image_de_reponse(json.loads(rep))
		if not part:
			print(f"  ✗ {base} : {rep.decode('utf-8', 'replace')[:300]}", flush=True)
			return None
		nom, motif = _ecrire_image(dossier, base, part, ())
		print(f"  {nom or '✗ ' + motif} ({time.time() - t0:.0f} s)", flush=True)
		return nom

	for e in a_faire:
		print(e["key"])
		chemin = None
		if _refait_portrait(e):
			portrait = _un(_requete(e, "portrait"), e["portrait"]["base"])
			if not portrait:
				continue
			chemin = os.path.join(dossier, portrait)
		elif man["portraits"].get(e["key"]):   # portrait conservé : c'est lui que la façade joint
			chemin = os.path.join(DOSSIER_PNJ, man["portraits"][e["key"]])
		_un(_requete(e, "image", chemin), e["image"]["base"])


def generer(cite, seulement, limite, essai=False):
	"""Façades par ComfyUI, pour les boutiques dont le portrait est récupéré. `essai` : écrit dans
	dev/batch/<cite>/images/essais/, sans toucher au manifeste ni à `towns/`."""
	man = _manifeste(cite)
	if man.get("batch"):
		raise SystemExit(f"Lot en cours : {man['batch']} — `recuperer` d'abord.")
	try:
		_comfy("/system_stats")
	except (urllib.error.URLError, OSError):
		raise SystemExit(f"ERREUR : ComfyUI injoignable sur {COMFY} — lancer "
						 "C:\\ComfyUI_windows_portable\\run_telluris.bat.")
	_liberer()
	dossier = DOSSIER_TOWNS
	if essai:
		dossier = os.path.join(_dossier(cite), "essais")
		os.makedirs(dossier, exist_ok=True)
	a_faire = [e for e in man["entrees"] if e["key"] in man["portraits"]
			   and (essai or e["key"] not in man["images"]) and (not seulement or e["key"] in seulement)]
	if limite:
		a_faire = a_faire[:limite]
	print(f"{len(a_faire)} image(s) à générer")
	for i, e in enumerate(a_faire, 1):
		t0 = time.time()
		wf = _workflow(e["image"]["prompt"], zlib.crc32(e["key"].encode()), _envoyer_portrait(man["portraits"][e["key"]]))
		pid = json.loads(_comfy("/prompt", {"prompt": wf}))["prompt_id"]
		while True:
			h = json.loads(_comfy(f"/history/{pid}")).get(pid)
			if h:
				break
			time.sleep(2)
		_liberer()
		if (h.get("status") or {}).get("status_str") != "success":
			print(f"  ✗ {e['key']} : {json.dumps((h.get('status') or {}).get('messages', [])[-1:])[:400]}")
			continue
		im = next(im for o in h["outputs"].values() for im in o.get("images", []))
		png = _comfy("/view?" + urllib.parse.urlencode(
			{"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")}))
		rejet = image_degeneree(*_mesures(png))
		if rejet:
			print(f"  ✗ {e['key']} : image {rejet} (GPU), non écrite — relancer `generer`", flush=True)
			continue
		nom = nom_libre(dossier, e["image"]["base"], ".png", () if essai else set(man["images"].values()))
		with open(os.path.join(dossier, nom), "wb") as f:
			f.write(png)
		if not essai:
			man["images"][e["key"]] = nom
			_ecrire_requetes(cite, man)
			_manifeste(cite, man)
		print(f"  [{i}/{len(a_faire)}] {nom} ← {e['key']} ({time.time() - t0:.0f} s)", flush=True)


def _repertoire_noms():
	"""Répertoire du recrutement et tirage de dev/gen_spec_rhemi.py (même règle que Rhemi et
	Chartres : prénom mutualisé compris), relus du SOURCE sans importer `utils` (base)."""
	sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
	from gen_spec_rhemi import constantes_source, tirer_nom
	rep = constantes_source(os.path.join(RACINE, "utils", "recrutement.py"),
							{"PRENOMS", "NOMS", "PRENOM_RACE_MUTUALISEE", "PRENOM_MUTUALISE_PROBA"})
	return rep, tirer_nom


def portrait_facade(cite, facade, race, sexe, categorie):
	"""Gemini INTERACTIF (~0,04 €) : portrait du tenancier d'une façade de `towns/` GARDÉE pour un
	lieu ultérieur. Écrit dans `pnj/` (prochain nom libre) et inscrit la paire dans
	dev/batch/<cite>/images/reserve.json — aucun lieu n'y est rattaché, aucun import."""
	chemin = os.path.join(DOSSIER_TOWNS, facade)
	if not os.path.exists(chemin):
		raise SystemExit(f"ERREUR : {facade} absente de towns/.")
	cite_nom = (_lieux().get(cite) or {}).get("label") or NOMS_CITES.get(cite) or _slug(cite).capitalize()
	requete = requete_gemini(prompt_tenancier_depuis_facade(race, sexe.upper(), categorie, cite_nom),
							 _portrait_b64(chemin))
	_, rep = _http(f"{API}/v1beta/models/{MODELE_GEMINI}:generateContent", requete)
	part = image_de_reponse(json.loads(rep))
	if not part:
		raise SystemExit(f"✗ {rep.decode('utf-8', 'replace')[:300]}")
	nom, motif = _ecrire_image(DOSSIER_PNJ, f"marchand_{race}_{sexe.lower()}_{categorie}", part, ())
	if not nom:
		raise SystemExit(f"✗ {motif}")
	fichier = os.path.join(_dossier(cite), "reserve.json")
	reserve = json.load(open(fichier, encoding="utf-8")) if os.path.exists(fichier) else []
	reserve.append({"facade": facade, "portrait": nom, "race": race, "sexe": sexe.upper(),
					"categorie": categorie, "cite": cite})
	with open(fichier, "w", encoding="utf-8") as f:
		json.dump(reserve, f, ensure_ascii=False, indent="\t")
	print(f"{nom} ← {facade} (réserve : {os.path.relpath(fichier, RACINE)})")


def appliquer(cite, source=None):
	"""Un seul import : `pnj[0].portrait`, `image` et — marchand de la cité qui n'en a pas —
	`pnj[0].nom`, sur des lieux relus de `source` (export frais) sinon du dump le plus récent.
	⚠️ PUT complet : un doc relu trop vieux écraserait les stocks d'entre-temps."""
	man = _manifeste(cite)
	source = source or man.get("source")
	lieux = _lieux(source)
	cite_lieux = {k: v for k, v in lieux.items() if v.get("lieu_parent") == cite}
	# Portraits et façades du manifeste posés AVANT de nommer : la lignée se lit sur le portrait.
	maj = {}
	for cle in sorted(set(man["portraits"]) | set(man["images"])):
		if cle not in lieux:
			continue
		doc = json.loads(json.dumps(lieux[cle]))
		if cle in man["portraits"]:
			doc["pnj"][0]["portrait"] = man["portraits"][cle]
		if cle in man["images"]:
			doc["image"] = man["images"][cle]
		maj[cle] = doc
	repertoire, tirer = _repertoire_noms()
	noms, inconnus = noms_manquants({**lieux, **maj}, cite, man["entrees"], repertoire, tirer)
	for lid, nom in noms.items():
		doc = maj.get(lid) or json.loads(json.dumps(lieux[lid]))
		doc["pnj"][0]["nom"] = nom
		maj[lid] = doc
	absents = sorted((set(man["portraits"]) | set(man["images"])) - set(lieux))
	sortie = [maj[k] for k in sorted(maj)]
	print(f"source : {os.path.relpath(source, RACINE) if source else 'dump le plus récent'} "
		  f"({len(cite_lieux)} lieux de la cité) ; {len(noms)} nom(s) de tenancier ajouté(s)")
	for lid in inconnus:
		print(f"  ⚠ {lid} : lignée du tenancier inconnue, pas de nom")
	chemin = os.path.join(RACINE, "jsons", f"images_magasins_{_slug(cite)}_a_importer.json")
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"{len(sortie)} lieu(x) → {os.path.relpath(chemin, RACINE)}")
	if absents:
		print(f"⚠ {len(absents)} lieu(x) absents du dump : exporter un dump puis relancer.")


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	p = argparse.ArgumentParser()
	p.add_argument("etape", choices=["preparer", "avancer", "essai", "soumettre", "etat", "recuperer",
									 "generer", "appliquer", "portrait_facade"])
	p.add_argument("--cite", required=True, help="ex. lieu:chartres")
	p.add_argument("--sauf", default="", help="lieux à exclure, séparés par des virgules")
	p.add_argument("--seulement", default="", help="ne générer que ces lieux, séparés par des virgules")
	p.add_argument("--limite", type=int, default=0, help="nombre maximal de lieux à générer")
	p.add_argument("--essai", action="store_true", help="générer dans dev/batch/<cite>/images/essais/")
	p.add_argument("--facade", default="", help="portrait_facade : image de towns/ dont on tire le tenancier")
	p.add_argument("--race", default="", help="portrait_facade : lignée du tenancier (humain, elfe, nain, hobbit, ogre)")
	p.add_argument("--sexe", default="", help="portrait_facade : M ou F")
	p.add_argument("--categorie", default="", help="portrait_facade : métier (clé de METIERS)")
	p.add_argument("--source", default="",
				   help="preparer/appliquer : export de lieux plus frais que le dump (il le remplace pour ces lieux)")
	p.add_argument("--refaire", default="",
				   help="preparer : boutiques à refaire (façade ; portrait aussi s'il n'est pas marchand_*), séparées par des virgules")
	p.add_argument("--doublons", action="store_true",
				   help="preparer : seulement les façades/portraits de marchands partagés avec un autre lieu")
	a = p.parse_args()
	if a.etape == "preparer":
		preparer(a.cite, {s for s in a.sauf.split(",") if s}, a.doublons,
				 {s for s in a.refaire.split(",") if s}, a.source or None)
	elif a.etape == "essai":
		essai(a.cite, {s for s in a.seulement.split(",") if s}, a.limite)
	elif a.etape == "portrait_facade":
		if a.race not in LIGNEES or a.sexe.upper() not in ("M", "F") or a.categorie not in METIERS:
			raise SystemExit("ERREUR : --race, --sexe (M/F) et --categorie (clé de METIERS) requis.")
		portrait_facade(a.cite, a.facade, a.race, a.sexe, a.categorie)
	elif a.etape == "generer":
		generer(a.cite, {s for s in a.seulement.split(",") if s}, a.limite, a.essai)
	else:
		if a.etape == "appliquer":
			appliquer(a.cite, a.source or None)
		else:
			{"avancer": avancer, "soumettre": soumettre, "etat": etat, "recuperer": recuperer}[a.etape](a.cite)


if __name__ == "__main__":
	main()

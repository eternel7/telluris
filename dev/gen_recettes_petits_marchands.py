"""Recettes et items des marchands qui en avaient moins de six (dump du 16/10).

Fumoir (1 recette), tannerie (1), taxidermie (2), cabinet des spécimens (3), atelier
d'artisan (5) et caves de Chartres (3 sous la portée `lieu:chartres`). Le lot leur donne des
vivres à effet, des matières de sur-mesure (bloc `fabrication`), des demi-produits consommés
par d'AUTRES métiers (une recette par débouché), de l'équipement et les outils de
crochetage (`bonus_desamorcage`, lu par `utils.pieges` au désamorçage).

    python dev/gen_recettes_petits_marchands.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/recettes_petits_marchands_a_importer.json   (carte d'import de /admin)

Garde-fous : ceux de dev/gen_bourrellerie.py (`main`) — collision d'`_id`, intrant sans doc,
FAUSSE FEUILLE contrôlée cité par cité (portée comprise), grande maison non croisée.

⚠️ Matières brutes NEUVES (copeaux de hêtre, écorce de chêne, alun) : feuilles livrées, donc
ACHETABLES au comptoir du fumoir et de la tannerie. Le `fer` le devient aussi à la tannerie et
à l'atelier d'artisan, l'`Eau_de_source` à l'atelier d'artisan.

⚠️ Les blocs `fabrication` des matières de ce lot sont posés ICI, et lus dans la table de
dev/gen_fabrication_matieres.py (la vérité) : relancé après l'import, ce dernier ne rend
aucun diff pour elles.

⚠️ `poudre_d_os` n'est PAS un doc manquant : `marche._OBJET_FINAL_ITEM_ID` le résout en
`item:Poudre_os`.
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import gen_bourrellerie as socle                                  # noqa: E402
from gen_bourrellerie import _composant, _piece                   # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "recettes_petits_marchands_a_importer.json")
CHARTRES = "lieu:chartres"
LUTECIA = "lieu:lutecia"


def _brute(nom, icon, poids, cu, description):
	"""Matière première NEUVE : sous-catégorie = slug (posée par `_brutes`), `valeur` explicite
	— c'est le prix de la feuille, base du coût de tout ce qu'elle nourrit."""
	return _composant(nom, icon, poids, description) | {"valeur": [{"cu": cu}]}


def _conso(nom, icon, poids, description, effets, rarete="commun", sous_categorie=""):
	return {"nom": nom, "icon": icon, "rarete": rarete, "categorie": "consommable",
			"sous_categorie": sous_categorie, "slots": [], "poids": poids,
			"description": description, "effets": effets}


def _outil(nom, icon, poids, description, rarete="commun", **champs):
	return {"nom": nom, "icon": icon, "rarete": rarete, "categorie": "outil",
			"slots": [], "poids": poids, "description": description} | champs


def _arme(nom, icon, poids, description, rarete, **champs):
	return {"nom": nom, "icon": icon, "rarete": rarete, "categorie": "arme",
			"slots": ["main_droite", "main_gauche"], "poids": poids,
			"description": description} | champs


def _catalyseur(nom, icon, slot, poids, description, rarete, **champs):
	return {"nom": nom, "icon": icon, "rarete": rarete, "categorie": "catalyseur",
			"slots": [slot], "poids": poids, "description": description} | champs


# ── Les items ─────────────────────────────────────────────────────────────────
# Valeurs calées sur l'existant (dump 16/10) : vivres entre `viande_fumee` (pv 8, regen 1,
# 3 t) et `jambon_de_montagne` (pv 18, regen 2, 10 t) ; colifichets de cou/ceinture à +1 carac
# comme `talisman`/`pendentif` ; cape entre la cape de plumes et le cuir clouté.
ITEMS = {
	# ── Matières brutes neuves ────────────────────────────────────────────────
	"copeaux_de_hetre": _brute(
		"Copeaux de hêtre", "🪵", 0.3, 3,
		"Copeaux et sciure de hêtre sec, que le fumeur jette sur la braise : la fumée doit "
		"rester froide et blanche, jamais la flamme."),
	"ecorce_de_chene": _brute(
		"Écorce de chêne", "🌳", 0.5, 4,
		"Écorce pilée de jeunes chênes, levée au printemps. Moulue et mise à tremper, elle "
		"donne le tan, qui fait d'une peau un cuir."),
	"alun": _brute(
		"Alun", "🧂", 0.2, 10,
		"Pierre blanche qu'on dissout dans l'eau chaude pour passer les peaux en blanc : un "
		"cuir souple et pâle, qui prend l'encre."),
	# ── Fumoir ────────────────────────────────────────────────────────────────
	"Viande_sechee_de_route": _conso(
		"Viande séchée de route", "🥩", 0.1,
		"Lanières de viande salées puis séchées à la fumée jusqu'à durcir comme du cuir. Ça ne "
		"pèse rien, ça ne pourrit pas, et ça se mâche longtemps.", {"pv": 6}),
	"Saucisson_fume": _conso(
		"Saucisson fumé", "🌭", 0.25,
		"Viande hachée au sel, poussée en boyau et pendue des semaines dans la fumée. On le "
		"tranche à la halte, on le finit au rempart suivant.",
		{"pv": 10, "regen_pv": 1, "duree": 8}),
	"Lard_fume": _conso(
		"Lard fumé", "🥓", 0.3,
		"Poitrine de lard frottée de sel puis fumée au hêtre. Le gras tient au corps plus "
		"qu'aucun pain.", {"pv": 6, "regen_pv": 1, "duree": 5}),
	"Coeur_fume_du_chasseur": _conso(
		"Cœur fumé du chasseur", "🫀", 0.2,
		"Les chasseurs le mangent à la veille d'une traque : un cœur de bête fumé entier, "
		"dur et noir. On dit qu'il donne le courage de ce qu'on a tué.",
		{"pv": 4, "buffs": {"Vol": 3}, "duree": 6}, rarete="peu_commun"),
	"Foie_fume_au_genevrier": _conso(
		"Foie fumé au genévrier", "🍖", 0.2,
		"Foie fumé sur des rameaux de genévrier, qui lui laissent un goût de résine. Les "
		"magiciens de passage en achètent plus que les soldats.",
		{"pm": 3, "regen_pm": 1, "duree": 6}),
	"Cuir_fume": _composant(
		"Cuir fumé", "🟫", 0.5,
		"Un cuir pendu dans la fumée jusqu'à prendre la couleur du tabac. L'eau perle dessus, "
		"et il garde une souplesse de gant."),
	# ── Tannerie ──────────────────────────────────────────────────────────────
	"Cuir_tanne_au_chene": _composant(
		"Cuir tanné au chêne", "🟫", 0.6,
		"Des mois dans les fosses à tan, couche de peau, couche d'écorce : le cuir en ressort "
		"ferme, brun et presque imputrescible."),
	"Peau_chamoisee": _composant(
		"Peau chamoisée", "🟨", 0.3,
		"Peau foulée à la graisse jusqu'à devenir douce comme une étoffe. Elle se plie, se "
		"lave et ne craque jamais."),
	"Croupon_epais": _composant(
		"Croupon épais", "🟫", 1.0,
		"Le dos de la peau, la partie la plus épaisse, tannée lentement au chêne. Le tanneur "
		"la garde pour qui veut un cuir qui encaisse."),
	"Tablier_de_tanneur": _piece(
		"Tablier de tanneur", "🦺", "torse", 1.2,
		"Un tablier de cuir de chêne qui descend aux genoux, bouclé dans le dos. Ce qui coupe "
		"et ce qui ronge s'y arrête.", bonus_pa=3, bonus={"R": 1}),
	"Gants_d_echarneur": _piece(
		"Gants d'écharneur", "🧤", "mains", 0.3,
		"Gants épais cousus à l'aiguille d'os, paume doublée de tendon. L'écharneur y tient "
		"son couteau des heures sans glisser.", bonus_pa=1, bonus={"Ag": 1}),
	"Couteau_a_echarner": _outil(
		"Couteau à écharner", "🔪", 0.4,
		"Une longue lame courbe à deux poignées, émoussée exprès : elle racle la chair et la "
		"graisse sans jamais trouer la peau."),
	# ── Taxidermie ────────────────────────────────────────────────────────────
	"Collier_de_crocs": _piece(
		"Collier de crocs", "🦷", "cou", 0.15,
		"Des crocs percés, enfilés sur un tendon. On ne les porte pas pour la beauté : chacun "
		"est une bête qui n'a pas gagné.", bonus={"F": 1}, bonus_initiative=1),
	"Patte_de_chasseur": _piece(
		"Patte de chasseur", "🐾", "ceinture", 0.1,
		"Une patte griffue séchée, pendue à la ceinture par une ligature. Les forestiers y "
		"voient de la chance ; les taxidermistes, un client.", bonus={"Ag": 1}),
	"Plume_totem": _piece(
		"Plume-totem", "🪶", "cou", 0.05,
		"Trois plumes de rapace liées en éventail. On la serre dans le poing avant de "
		"traverser une lande.", bonus={"Vol": 1}),
	"Cape_de_fourrure": _piece(
		"Cape de fourrure", "🧥", "epaules", 1.5,
		"Une peau entière, poil dehors, assouplie à la graisse et cousue d'une bordure. Le "
		"vent des routes ne passe pas.", rarete="peu_commun", bonus_pa=2, bonus={"R": 1}),
	"Griffe_montee": _composant(
		"Griffe montée", "🦅", 0.1,
		"Une griffe vidée, durcie au feu et ligaturée sur un talon de tendon, prête à être "
		"fixée à une garde ou à un poing."),
	"Oeil_de_bete_conserve": _composant(
		"Œil de bête conservé", "👁️", 0.05,
		"Un œil gardé dans le sel jusqu'à durcir comme une perle. Les catalyseurs qui en "
		"portent un, dit-on, voient le mana venir."),
	"Appeau_de_chasse": _outil(
		"Appeau de chasse", "🎶", 0.05,
		"Un sifflet d'os garni d'une plume, qui imite le cri d'une proie blessée. Il attire "
		"le gibier — et parfois ce qui chasse le gibier."),
	# ── Cabinet des spécimens ─────────────────────────────────────────────────
	"Bocal_d_yeux_en_saumure": _composant(
		"Bocal d'yeux en saumure", "🫙", 0.6,
		"Des yeux de bêtes rangés dans une saumure trouble, le col scellé à la cire et "
		"étiqueté de la main du conservateur. Les alchimistes en achètent sans poser de question."),
	"Squelette_articule": _outil(
		"Squelette articulé", "🦴", 4.0,
		"Une ossature remontée pièce à pièce, chaque jointure tenue par une boucle de fer. "
		"Les étudiants du cabinet y apprennent où frapper.", rarete="rare"),
	"Coeur_reliquaire": _piece(
		"Cœur reliquaire", "🫀", "cou", 0.3,
		"Un cœur séché au sel, enchâssé dans un petit coffret d'os qu'on porte au cou. Il "
		"bat encore, prétendent ceux qui le vendent.",
		rarete="rare", bonus_pv=2, bonus={"Vol": 2}),
	"Main_de_gloire": _catalyseur(
		"Main de gloire", "🖐️", "main_gauche", 0.4,
		"La main d'un pendu, salée, séchée, les doigts garnis de suif et de mèches. Allumée, "
		"disent les vieux récits, elle tient endormis ceux de la maison où l'on entre.",
		"rare", bonus_pm=3, effets={"canalisation": 1}, restriction={"Vol": 25}),
	"Planche_anatomique": {
		"nom": "Planche anatomique", "icon": "📜", "rarete": "peu_commun",
		"categorie": "document", "slots": [], "poids": 0.1,
		"description": "Un parchemin couvert de coupes de bêtes, tracées à l'encre de sang "
		"d'après des pièces du cabinet. Les chirurgiens en tapissent leurs murs."},
	# ── Atelier d'artisan ─────────────────────────────────────────────────────
	"Crochets_d_os": _outil(
		"Crochets d'os", "🔓", 0.05,
		"Deux tiges d'os limées en crochet et en tension. Elles cassent plus vite que le fer, "
		"mais ne sonnent pas dans la serrure.", bonus_desamorcage=5),
	"Trousse_de_crochetage_fine": _outil(
		"Trousse de crochetage fine", "🧰", 0.2,
		"Un rouleau de cuir où dorment crochets, tensions et aiguilles, chacun dans sa "
		"couture. L'outil des mains qui savent déjà.", rarete="peu_commun", bonus_desamorcage=15),
	"Passe_partout": _outil(
		"Passe-partout", "🗝️", 0.1,
		"Une clef de fer limée sur un crochet de serrurier : sans dents, elle trouve d'elle-"
		"même les gorges d'un mécanisme.", bonus_desamorcage=10),
	"Colle_d_os": _composant(
		"Colle d'os", "🍯", 0.2,
		"Os concassés bouillis des heures, puis la gelée coulée en plaques. On la refond au "
		"bain-marie : luthiers, archers et tabletiers n'assemblent rien sans elle."),
	"Aiguille_d_os": _composant(
		"Aiguilles d'os", "🪡", 0.01,
		"Aiguilles taillées dans des éclats d'os, chas percé au foret. Elles passent là où "
		"l'acier déchirerait la peau."),
	# ── Caves de Chartres ─────────────────────────────────────────────────────
	"Biere_de_Beauce": _conso(
		"Bière de Beauce", "🍺", 1.0,
		"La bière du grenier : orge de la plaine, eau de puits, une nuit de levain. Elle "
		"désaltère les moissonneurs et les caravanes.", {"pv": 8, "buffs": {"R": 1}, "duree": 6},
		sous_categorie="boisson"),
	"Vinaigre_de_miel": {
		"nom": "Vinaigre de miel", "icon": "🫙", "rarete": "commun",
		"categorie": "composant", "sous_categorie": "condiment", "slots": [], "poids": 0.8,
		"description": "Un hydromel oublié en fût jusqu'à tourner : doux d'abord, aigre "
		"ensuite. Les cuisiniers de Chartres en déglacent leurs volailles."},
	"Genievre_de_Beauce": _conso(
		"Genièvre de Beauce", "🥃", 0.6,
		"Eau-de-vie de grain passée sur des baies de genévrier. Elle réchauffe le cœur et "
		"embrume les mains.", {"pv": 4, "buffs": {"Vol": 2, "Ag": -1}, "duree": 5},
		sous_categorie="boisson"),
	"Hydromel_du_pelerin": _conso(
		"Hydromel du pèlerin", "🍯", 1.0,
		"Hydromel chauffé aux épices douces, qu'on sert à ceux qui viennent parcourir le "
		"labyrinthe de Chartres. On le boit avant d'entrer, pour garder la tête claire.",
		{"pm": 10, "regen_pm": 1, "buffs": {"Vol": 2}, "duree": 6}, rarete="peu_commun",
		sous_categorie="boisson"),
	# ── Débouchés chez d'autres métiers ───────────────────────────────────────
	"Bottes_de_cuir_fume": _piece(
		"Bottes de cuir fumé", "🥾", "pieds", 0.9,
		"Des bottes de cuir fumé, coutures enduites : on traverse un gué sans y laisser ses "
		"pieds.", bonus_pa=1, bonus={"Ag": 1}),
	"Besace_de_cuir_fume": _piece(
		"Besace de cuir fumé", "👝", "ceinture", 0.5,
		"Une sacoche plate à rabat, en cuir fumé qui ne boit pas la pluie. Les messagers la "
		"portent sur la hanche.", bonus_initiative=2),
	"Ceinturon_tanne_au_chene": _piece(
		"Ceinturon tanné au chêne", "🎗️", "ceinture", 0.4,
		"Une large ceinture de cuir de chêne, épaisse comme deux doigts, qui tient les reins "
		"au port d'une charge.", bonus_pa=1, bonus={"R": 1}),
	"Gants_de_chamois": _piece(
		"Gants de chamois", "🧤", "mains", 0.1,
		"Des gants fins comme une seconde peau. Ils protègent peu, mais la main garde tout "
		"son toucher.", bonus={"Ag": 1, "Cha": 1}),
	"Bouclier_de_croupon": _piece(
		"Bouclier de croupon", "🛡️", "main_gauche", [1.5, 2.5],
		"Deux épaisseurs de croupon tendues sur un cerclage de fer. Plus léger qu'un "
		"bouclier de bois, et il ne se fend pas.", bonus_pa=4, restriction={"F": 12}),
	"Tourte_au_lard_fume": _conso(
		"Tourte au lard fumé", "🥧", 0.6,
		"Pâte au beurre, lard fumé en dés, cuite au four du boulanger. Un repas entier qui "
		"voyage dans un linge.", {"pv": 18, "regen_pv": 2, "duree": 6}, sous_categorie="boulangerie"),
	"Volaille_au_vinaigre_de_miel": _conso(
		"Volaille au vinaigre de miel", "🍗", 0.8,
		"Volaille rôtie, déglacée au vinaigre de miel et aux herbes du fournil. Le plat des "
		"jours de marché à Chartres.", {"pv": 22, "regen_pv": 2, "duree": 6},
		rarete="peu_commun", sous_categorie="cuisine"),
	"Arc_recurve_de_corne": _arme(
		"Arc recurve de corne", "🏹", [0.8, 1.2],
		"Un arc court à branches retournées : âme de bois, ventre de corne, dos de tendon, "
		"le tout collé à la colle d'os. Il tire comme un arc long.", "peu_commun",
		sous_categorie="arc", tags=["tir"], portee=8, restriction={"Ag": 21},
		bonus_degats=3, bonus_degats_dice=4, bonus_cd=6, bonus={"Ag": 2}, deux_mains=True),
	"Guiterne": _arme(
		"Guiterne", "🪕", 1.2,
		"Petit luth au dos taillé dans la masse, table collée à l'os. Sa voix aigre porte "
		"au-dessus d'une salle de taverne.", "commun",
		sous_categorie="instrument", tags=["cac"], portee=1, deux_mains=True,
		bonus_degats_dice=2, bonus={"Cha": 4}, restriction={"Cha": 25}),
	"Coffret_marquete": _outil(
		"Coffret marqueté", "🧰", 0.8,
		"Un coffret de bois couvert de losanges d'os et de bois sombre, collés un à un. On y "
		"range ce qu'on ne montre pas.", rarete="peu_commun"),
	"Elixir_de_clairvoyance": _conso(
		"Élixir de clairvoyance", "🧪", 0.1,
		"Une tisane de concentration où l'on a laissé infuser un œil de bête. Le regard "
		"porte plus loin, le goût aussi.", {"pm": 10, "buffs": {"Int": 4}, "duree": 6},
		rarete="rare"),
	"Ossuaire_articule": _catalyseur(
		"Ossuaire articulé", "💀", "main_gauche", 1.5,
		"Une main de squelette articulé montée sur un manche, frottée de sel noir. Les "
		"thanaturges la tendent vers les morts qu'ils appellent.",
		"rare", bonus_pm=4, effets={"canalisation": 1}, bonus={"Vol": 1}, restriction={"Vol": 30}),
}

# ── Les recettes ──────────────────────────────────────────────────────────────
# slug produit → (catégorie, [(clé, quantité)], quantité produite[, portée]). Clé = sous-
# catégorie (butin de boucherie : `viande`, `os`…, venu par le flux de cité) ou `item:<id>`.
RECETTES = {
	# Fumoir
	"Viande_sechee_de_route":  ("fumoir", [("viande", 1), ("item:Sel", 1)], 3),
	"Saucisson_fume":          ("fumoir", [("item:boyaux_pour_saucisses", 1), ("viande", 2), ("item:Sel", 1), ("copeaux_de_hetre", 1)], 3),
	"Lard_fume":               ("fumoir", [("graisse", 1), ("viande", 1), ("copeaux_de_hetre", 1)], 2),
	"Coeur_fume_du_chasseur":  ("fumoir", [("coeur", 1), ("copeaux_de_hetre", 1)], 1),
	"Foie_fume_au_genevrier":  ("fumoir", [("foie", 1), ("copeaux_de_hetre", 1)], 1),
	"Cuir_fume":               ("fumoir", [("cuir", 1), ("copeaux_de_hetre", 2)], 1),
	# Tannerie
	"Cuir_tanne_au_chene":     ("tannerie", [("cuir_brut", 2), ("ecorce_de_chene", 2)], 1),
	"Peau_chamoisee":          ("tannerie", [("peaux", 1), ("graisse", 1)], 1),
	"Croupon_epais":           ("tannerie", [("cuir_brut", 3), ("ecorce_de_chene", 3)], 1),
	"Parchemin_vierge":        ("tannerie", [("peaux", 1), ("alun", 1)], 3),
	"Tablier_de_tanneur":      ("tannerie", [("item:Cuir_tanne_au_chene", 2), ("item:Boucle_de_fer", 1)], 1),
	"Gants_d_echarneur":       ("tannerie", [("cuir", 1), ("tendons", 1), ("item:Aiguille_d_os", 1)], 1),
	"Couteau_a_echarner":      ("tannerie", [("fer", 1), ("manche", 2)], 1),
	# Taxidermie
	"Collier_de_crocs":        ("taxidermie", [("crocs", 3), ("tendons", 1)], 1),
	"Patte_de_chasseur":       ("taxidermie", [("griffes", 1), ("tendons", 1)], 1),
	"Plume_totem":             ("taxidermie", [("plumes", 3), ("tendons", 1)], 1),
	"Cape_de_fourrure":        ("taxidermie", [("peaux", 2), ("poils", 2), ("graisse", 1), ("item:Aiguille_d_os", 1)], 1),
	"Griffe_montee":           ("taxidermie", [("griffes", 2), ("tendons", 1)], 1),
	"Oeil_de_bete_conserve":   ("taxidermie", [("yeux", 2), ("item:Sel", 1)], 1),
	"Appeau_de_chasse":        ("taxidermie", [("os", 1), ("plumes", 1)], 2),
	# Cabinet des spécimens (Lutecia seule) — GRANDE MAISON (taxidermie + plumasserie +
	# tabletterie) : chaque recette tire un intrant qu'aucun de ces métiers ne fournit seul.
	"Bocal_d_yeux_en_saumure": ("cabinet_des_specimens", [("yeux", 3), ("item:Sel", 2), ("item:Cire_d_abeille", 1)], 1),
	"Squelette_articule":      ("cabinet_des_specimens", [("ossements", 4), ("item:Boucle_de_fer", 2)], 1),
	"Coeur_reliquaire":        ("cabinet_des_specimens", [("coeur", 1), ("item:Sel", 1), ("ossements", 1)], 1),
	"Main_de_gloire":          ("cabinet_des_specimens", [("ossements", 1), ("graisse", 1), ("item:Sel", 1), ("item:Meche", 2)], 1),
	"Planche_anatomique":      ("cabinet_des_specimens", [("item:Parchemin_vierge", 1), ("sang", 1), ("yeux", 1)], 1),
	# Atelier d'artisan
	"Crochets_d_os":           ("atelier_d_artisan", [("os", 1)], 2),
	"Trousse_de_crochetage_fine": ("atelier_d_artisan", [("item:Crochets", 1), ("item:aiguille", 2), ("cuir", 1)], 1),
	"Passe_partout":           ("atelier_d_artisan", [("fer", 1), ("item:Crochet_serrurier", 1)], 1),
	"Colle_d_os":              ("atelier_d_artisan", [("os", 2), ("item:Eau_de_source", 1)], 2),
	"Pierre_a_aiguiser":       ("atelier_d_artisan", [("pierre", 1)], 2),
	"Aiguille_d_os":           ("atelier_d_artisan", [("os", 1)], 4),
	# Caves de Chartres
	"Biere_de_Beauce":         ("cave", [("item:grain_d_orge", 3), ("item:Eau_de_source", 1)], 3, CHARTRES),
	"Vinaigre_de_miel":        ("cave", [("item:Hydromel_de_Beauce", 1)], 3, CHARTRES),
	"Genievre_de_Beauce":      ("cave", [("item:grain_d_orge", 2), ("item:Eau_de_vie", 1)], 2, CHARTRES),
	"Hydromel_du_pelerin":     ("cave", [("item:Hydromel_de_Beauce", 1), ("item:epices_douces", 1)], 1, CHARTRES),
	# Débouchés chez d'autres métiers
	"Bottes_de_cuir_fume":     ("cordonnerie", [("item:Cuir_fume", 2), ("tendons", 1)], 1),
	"Besace_de_cuir_fume":     ("maroquinerie", [("item:Cuir_fume", 2), ("item:Boucle_de_fer", 1)], 1),
	"Ceinturon_tanne_au_chene": ("maroquinerie", [("item:Cuir_tanne_au_chene", 1), ("item:Boucle_de_fer", 1)], 1),
	"Gants_de_chamois":        ("maroquinerie", [("item:Peau_chamoisee", 1)], 1),
	"Bouclier_de_croupon":     ("armurerie", [("item:Croupon_epais", 2), ("fer", 1)], 1),
	"Tourte_au_lard_fume":     ("boulangerie", [("item:farine_de_froment", 2), ("item:Lard_fume", 2), ("item:motte_de_beurre", 1)], 1),
	"Volaille_au_vinaigre_de_miel": ("cuisine", [("item:Volaille", 1), ("item:Vinaigre_de_miel", 1), ("item:herbes_de_fournil", 1)], 1, CHARTRES),
	"Arc_recurve_de_corne":    ("atelier_de_l_empenneur", [("manche", 1), ("cordes_d_arc", 1), ("tendons", 1), ("item:Colle_d_os", 2)], 1),
	"Guiterne":                ("lutherie", [("item:Table_d_harmonie", 1), ("item:cordes_d_instrument", 4), ("item:Colle_d_os", 1)], 1),
	"Coffret_marquete":        ("tabletterie", [("branche", 1), ("os", 2), ("item:Colle_d_os", 1)], 1),
	"Elixir_de_clairvoyance":  ("grand_laboratoire_alchimique", [("item:Bocal_d_yeux_en_saumure", 1), ("item:Tisane_concentration", 1)], 1),
	"Ossuaire_articule":       ("institut_de_thanaturgie", [("item:Squelette_articule", 1), ("item:Sel_noir", 1)], 1),
}

# Matières brutes neuves : leur sous-catégorie est leur slug (clé de recette).
BRUTES = ("copeaux_de_hetre", "ecorce_de_chene", "alun")

# `valeur` explicite des intermédiaires : sans elle, chaque étape multiplie par MARGE_TRANSFO
# (×5) et le cuir fumé (cuir 25 cu) sortait à 155 cu, ses bottes à 1 575 — deux fois les
# guêtres de route. Calée à hauteur du cuir bouilli (102 cu) et de ses voisins de rayon.
VALEURS = {
	"Cuir_fume": [{"cu": 35}, {"cu": 70}],
	"Peau_chamoisee": [{"cu": 30}, {"cu": 60}],
	"Cuir_tanne_au_chene": [{"cu": 40}, {"cu": 80}],
	"Croupon_epais": [{"cu": 60}, {"cu": 110}],
	"Planche_anatomique": [{"cu": 120}, {"cu": 240}],
	"Hydromel_du_pelerin": [{"cu": 40}, {"cu": 90}],
}

# Docs déjà en base complétés par ce lot.
MODIFS = {
	"item:Crochet_serrurier": {"bonus_desamorcage": 5},
	"item:Crochets": {"bonus_desamorcage": 10},
	# Existait sans effet (produite par l'armurerie) : elle gagne l'entretien de lame.
	"item:Pierre_a_aiguiser": {"effets": {"buffs": {"F": 2}, "duree": 3}},
}


def table_items() -> dict:
	"""ITEMS, avec la sous-catégorie des matières brutes et le bloc `fabrication` + tags des
	matières que la table de dev/gen_fabrication_matieres.py décrit (même ordre de tags qu'elle
	écrit : `a_ecrire_depuis` ne rendra aucun diff après l'import).

	⚠️ Import DIFFÉRÉ : la table tire `utils.*`, qui fige `db.config.get_doc` à l'import — elle
	ne se charge qu'une fois le moteur branché sur le dump (`socle.main`)."""
	from gen_fabrication_matieres import MATIERES as FAB, bloc_fabrication
	out = {}
	for slug, d in ITEMS.items():
		d = dict(d)
		if slug in BRUTES:
			d["sous_categorie"] = slug
		if slug in VALEURS:
			d["valeur"] = VALEURS[slug]
		entree = FAB.get("item:" + slug)
		if entree:
			d["fabrication"] = bloc_fabrication(entree)
			d["tags"] = sorted(set(entree.get("tags") or []))
		out[slug] = d
	return out


if __name__ == "__main__":
	socle.main(table_items, RECETTES, SORTIE, MODIFS)

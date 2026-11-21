#!/usr/bin/env python
# dev/gen_boulangeries.py
# Ouvre DEUX boulangeries à Auxerre, et la chaîne d'items/recettes qui les fait vivre.
#
# Sortie (à coller dans /admin → Import en masse) : jsons/boulangeries_a_importer.json
#
# ⚠️ POURQUOI UN GÉNÉRATEUR ET PAS UN JSON ÉCRIT À LA MAIN (cf. CLAUDE.md §11) :
#   1. « Au même emplacement que les cuisines » est une donnée de la BASE, pas une constante :
#      les deux cases sont RELUES depuis les docs `connection` des `lieu:*` de catégorie
#      `cuisine` du parent. Déplacer une cuisine dans l'éditeur et relancer ce script suffit.
#   2. Le tenancier `pnj:marchand_boulangerie` est produit par le MÊME `dialogue()` que les 29
#      autres (`dev/gen_marchands.py`, importé ici) : un seul endroit décrit ce que dit un
#      tenancier générique, sinon les deux générateurs divergeraient en silence.
#   3. `admin_import_bulk` fait un PUT COMPLET : relancer est idempotent parce que tout ce qui
#      est écrit ici est reconstruit, jamais fusionné à moitié.
#
# ── LES QUATRE DÉCISIONS QUI COMMANDENT LE RESTE ─────────────────────────────────
#
# ⚠️ 1. UNE MATIÈRE CONSOMMÉE PAR LA CATÉGORIE DEVIENT UNE FEUILLE AUTO-APPROVISIONNÉE, DONC
#    VENDUE AU COMPTOIR (`marche.appro_leaves_categorie` → `approvisionner`). Écrire une
#    recette, c'est ouvrir un point de vente pour chacun de ses intrants BRUTS. C'est voulu
#    ici — grains, levain, miel, œufs, beurre, noix, raisins, épices, herbes et sel sont
#    exactement ce qu'une boulangerie-épicerie médiévale tient en rayon —, mais c'est aussi
#    pourquoi l'EAU a été retirée des recettes : un comptoir qui vend de l'eau de source
#    n'apporte rien et ajoute une ligne de bruit à chaque rayon.
#
# ⚠️ 2. LES FARINES SONT DES INTERMÉDIAIRES PRODUITS SUR PLACE (grain ×3 → 1 farine), pas des
#    feuilles : elles ne sont donc PAS approvisionnées, elles sont moulues. Le « pool unifié »
#    de `_executer_production_batch` les rend à la fois EN VENTE et réutilisables comme
#    matière — mais seulement AU-DESSUS du `stock_cible`. D'où les cibles BASSES posées sur
#    les trois farines (3-4) : à 25 (le `STOCK_CIBLE_DEFAUT`), il aurait fallu accumuler 25
#    sacs de farine sur l'étal avant qu'un seul pain ne sorte du four.
#
# ⚠️ 3. LES DEUX FRUITS NE SONT PAS DES FEUILLES, ET C'EST DÉLIBÉRÉ. `item:Pomme_de_verger`
#    est déjà produit par le jardinier ; on lui donne ici son pendant `item:Poire_de_verger`
#    (mêmes recettes, même famille) plutôt que d'inventer un fruit de boulangerie. Les deux
#    tourtes dépendent donc d'un APPROVISIONNEMENT RÉEL — étal du jardinier, sac du joueur,
#    ou course de transport — exactement comme la cuisine dépend depuis toujours de la viande
#    et du foie de la boucherie. Symétrie assumée : mettre un seul des deux fruits en feuille
#    aurait donné deux tourtes qui ne se comportent pas pareil, sans que rien ne le dise. Les
#    deux boutiques sont donc SEMÉES en pommes et en poires pour que les tourtes soient en
#    rayon dès l'import.
#    ⚠️ Corollaire : le statut de feuille est GLOBAL. Écrire un jour une recette (n'importe
#    où) qui PRODUIT un intrant du fournil — du miel chez l'apiculteur, par exemple — le
#    ferait cesser d'être une feuille, donc cesser d'être livré ici, et la ligne de produits
#    qui en dépend s'éteindrait en silence.
#
# ⚠️ 4. LES PRIX SONT ÉPINGLÉS PAR UN `valeur` EXPLICITE ([min, max]), pas dérivés. Sans lui,
#    `cout_production_cuivre` propage `MARGE_TRANSFO` (×5) À CHAQUE ÉTAPE : grain → farine →
#    pain, c'est ×25, et la miche de froment se vendait plus cher qu'une nuit d'auberge. Un
#    `valeur` explicite est AUTORITAIRE et coupe la propagation (`item_sale_price_cuivre`
#    prend `valeur[0]` = le min ; `prix_range_cuivre` prend min/max des bornes).
#
# Usage : python dev/gen_boulangeries.py

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from dev.gen_marchands import (  # noqa: E402  (après l'ajustement de sys.path)
	METIERS, NOEUDS_ESCORTE, NOEUDS_TRANSPORT, PORTRAITS, dialogue,
)

# SOURCE UNIQUE : le dump complet. ⚠️ Figé explicitement (et non « le glob le plus récent »)
# pour que régénérer donne toujours le même résultat ; à mettre à jour à la main.
SRC_DUMP = "jsons/telluris-dump-20260905-123809.json"
SORTIE = "jsons/boulangeries_a_importer.json"

CITE = "lieu:auxerre"
CATEGORIE = "boulangerie"
# On se pose là où sont les cuisines : même métier de bouche, même quartier.
CATEGORIE_MODELE = "cuisine"

# Les deux boutiques, dans l'ordre où les cases des cuisines sont trouvées (tri par id de
# lien → `link:cuisine01…` d'abord, comme les magasins existants).
BOUTIQUES = [
	{
		"_id": "lieu:le_four_banal_de_saint_germain",
		"label": "Le Four Banal de Saint-Germain",
		"image": "boulangerie_europe01.png",
		"tenancier": "Aubry Chaufour",
	},
	{
		"_id": "lieu:le_fournil_de_l_yonne",
		"label": "Le Fournil de l'Yonne",
		"image": "boulangerie_europe03.png",
		"tenancier": "Perrette Bienfarine",
	},
]


# ── Matières premières : les FEUILLES (auto-approvisionnées, donc vendues au comptoir) ──
# `item:Sel` existe déjà (feuille de la salaison) : on le RÉUTILISE, on ne le redéclare pas.
# (clé, nom, icon, sous_categorie, poids, prix_min, prix_max, description)
MATIERES = [
	("grain_de_froment",  "Grain de froment",  "🌾", "grain",     0.5,  2,   5,
	 "Froment battu et vanné, prêt pour la meule. Le grain des pains blancs."),
	("grain_de_seigle",   "Grain de seigle",   "🌾", "grain",     0.5,  2,   4,
	 "Seigle des terres pauvres, qui donne un pain noir et qui tient au corps."),
	("grain_d_orge",      "Grain d'orge",      "🌾", "grain",     0.5,  1,   3,
	 "Orge commune, celle du pain des pauvres et de la bière des soldats."),
	("levain_de_chef",    "Levain de chef",    "🫙", "levain",    0.2,  6,   15,
	 "Une pâte aigre entretenue de fournée en fournée ; certains la disent plus vieille que la ville."),
	("miel_de_bruyere",   "Miel de bruyère",   "🍯", "miel",      0.4,  25,  60,
	 "Miel sombre et fort des ruchers de lande, gardé en pot de grès."),
	("oeufs_de_ferme",    "Œufs de ferme",     "🥚", "oeuf",      0.3,  8,   20,
	 "Une douzaine d'œufs couchés dans la paille, à manier avec précaution."),
	("motte_de_beurre",   "Motte de beurre",   "🧈", "beurre",    0.5,  18,  45,
	 "Beurre baratté du matin, moulé et marqué au sceau de la ferme."),
	("cerneaux_de_noix",  "Cerneaux de noix",  "🌰", "fruit_sec", 0.2,  12,  30,
	 "Noix décortiquées à la main, qu'on garde tout l'hiver dans un linge sec."),
	("raisins_secs",      "Raisins secs",      "🍇", "fruit_sec", 0.15, 10,  25,
	 "Grappes séchées au grenier ; elles sucrent les pâtes quand le miel manque."),
	("epices_douces",     "Épices douces",     "🧂", "epice",     0.1,  40,  110,
	 "Cannelle et gingembre pilés ensemble, venus de si loin qu'on les compte au grain."),
	("herbes_de_fournil", "Herbes de fournil", "🌿", "aromate",   0.05, 5,   14,
	 "Thym, sauge et romarin liés en bouquet, séchés à la chaleur du four."),
]
# ⚠️ `herbes_de_fournil` n'est PAS de sous-catégorie `herbe` : `APPRO_DEBIT["herbe"] = 0`
# (les herbes sont une récolte JOUEUR, volontairement hors auto-appro) et `_appro_debit_pour`
# retombe sur la sous-catégorie d'un intrant désigné par son id. La boulangerie n'aurait donc
# jamais été livrée en herbes, et le pain aux herbes serait resté introuvable, en silence.

# ── Les farines : intermédiaires PRODUITS sur place (cf. décision 2) ─────────────
# (clé, nom, icon, grain d'origine, prix_min, prix_max, description)
FARINES = [
	("farine_de_froment", "Farine de froment", "🌾", "grain_de_froment", 12, 30,
	 "Fleur de froment blutée fin, blanche comme il se doit pour les pains de bourgeois."),
	("farine_de_seigle",  "Farine de seigle",  "🌾", "grain_de_seigle",  10, 26,
	 "Farine grise à l'odeur forte, qui donne au pain sa mie serrée."),
	("farine_d_orge",     "Farine d'orge",     "🌾", "grain_d_orge",      8, 20,
	 "Mouture rustique, un peu grossière, dont on fait galettes et pains de ménage."),
]

# ── Les 15 produits ─────────────────────────────────────────────────────────────
# ⚠️ Une matière est TOUJOURS désignée par un item précis (`{"item": "item:xxx"}`) et jamais
# par une sous-catégorie : `matiere_item_id("fruit_sec")` rendrait `item:fruit_sec`, un doc
# qui n'existe pas — la matière serait alors valorisée à 1 cu EN SILENCE (cf. l'avertissement
# de `_OBJET_FINAL_ITEM_ID` dans utils/marche.py) et jamais mise en vitrine.
PRODUITS = [
	dict(id="pain_froment", nom="Pain de froment", icon="🍞", poids=0.7, rarete="commun",
		 prix=(12, 28), qp=2,
		 description="Pain blanc courant fabriqué avec de la farine de blé.",
		 effets={"pv": 9},
		 matieres=[("item:farine_de_froment", 2), ("item:levain_de_chef", 1), ("item:Sel", 1)]),
	dict(id="pain_seigle", nom="Pain de seigle", icon="🍞", poids=0.8, rarete="commun",
		 prix=(9, 20), qp=2,
		 description="Pain sombre et dense, nourrissant et apprécié dans les régions froides.",
		 effets={"pv": 8, "duree": 4, "regen_pv": 1},
		 matieres=[("item:farine_de_seigle", 2), ("item:levain_de_chef", 1), ("item:Sel", 1)]),
	dict(id="pain_orge", nom="Pain d'orge", icon="🍞", poids=0.7, rarete="commun",
		 prix=(6, 14), qp=3,
		 description="Pain rustique, nourrissant et peu coûteux.",
		 effets={"pv": 6},
		 matieres=[("item:farine_d_orge", 2), ("item:levain_de_chef", 1), ("item:Sel", 1)]),
	dict(id="pain_meteil", nom="Pain de méteil", icon="🍞", poids=0.75, rarete="commun",
		 prix=(10, 24), qp=2,
		 description="Pain fabriqué avec un mélange de farine de blé et de seigle.",
		 effets={"pv": 8, "duree": 3, "regen_pv": 1},
		 matieres=[("item:farine_de_froment", 1), ("item:farine_de_seigle", 1),
				   ("item:levain_de_chef", 1), ("item:Sel", 1)]),
	dict(id="pain_noix", nom="Pain aux noix", icon="🥖", poids=0.7, rarete="commun",
		 prix=(20, 48), qp=2,
		 description="Pain rustique contenant des noix concassées.",
		 effets={"pv": 12, "duree": 6, "buffs": {"F": 5}},
		 matieres=[("item:farine_de_froment", 1), ("item:farine_de_seigle", 1),
				   ("item:cerneaux_de_noix", 2), ("item:levain_de_chef", 1), ("item:Sel", 1)]),
	dict(id="pain_herbes", nom="Pain aux herbes", icon="🥖", poids=0.3, rarete="commun",
		 prix=(14, 32), qp=3,
		 description="Petit pain parfumé avec des herbes locales comme le thym, la sauge ou le romarin.",
		 effets={"pv": 7, "duree": 6, "buffs": {"Vol": 5}},
		 matieres=[("item:farine_de_froment", 1), ("item:herbes_de_fournil", 2),
				   ("item:levain_de_chef", 1), ("item:Sel", 1)]),
	dict(id="petit_pain", nom="Petit pain", icon="🥖", poids=0.15, rarete="commun",
		 prix=(5, 12), qp=4,
		 description="Portion individuelle de pain blanc, pratique pour les voyageurs et les soldats.",
		 effets={"pv": 4},
		 matieres=[("item:farine_de_froment", 1), ("item:levain_de_chef", 1), ("item:Sel", 1)]),
	dict(id="galette_cereales", nom="Galette de céréales", icon="🫓", poids=0.3, rarete="commun",
		 prix=(7, 16), qp=4,
		 description="Galette plate préparée avec des céréales et cuite sur une plaque ou une pierre chaude.",
		 effets={"pv": 6, "duree": 3, "regen_pv": 1},
		 # Sans levain : c'est une pâte non levée, cuite à même la pierre.
		 matieres=[("item:farine_d_orge", 1), ("item:farine_de_seigle", 1), ("item:Sel", 1)]),
	dict(id="fouace_miel", nom="Fouace au miel", icon="🍥", poids=0.5, rarete="commun",
		 prix=(26, 60), qp=2,
		 description="Pain moelleux légèrement sucré au miel, souvent préparé pour les jours de fête.",
		 effets={"pv": 14, "duree": 6, "regen_pv": 2},
		 matieres=[("item:farine_de_froment", 2), ("item:miel_de_bruyere", 1),
				   ("item:motte_de_beurre", 1), ("item:levain_de_chef", 1)]),
	dict(id="brioche_miel", nom="Brioche au miel", icon="🍮", poids=0.6, rarete="peu_commun",
		 prix=(45, 105), qp=2,
		 description="Pâte riche en œufs et en beurre, légèrement sucrée au miel.",
		 effets={"pv": 18, "pm": 6, "duree": 8, "buffs": {"Cha": 10}},
		 matieres=[("item:farine_de_froment", 2), ("item:oeufs_de_ferme", 2),
				   ("item:motte_de_beurre", 2), ("item:miel_de_bruyere", 1),
				   ("item:levain_de_chef", 1)]),
	dict(id="tourte_pommes", nom="Tourte aux pommes", icon="🥧", poids=1.0, rarete="commun",
		 prix=(34, 80), qp=1,
		 description="Pâte garnie de pommes coupées et légèrement sucrées.",
		 effets={"pv": 16, "duree": 6, "buffs": {"Cha": 5}},
		 matieres=[("item:farine_de_froment", 2), ("item:Pomme_de_verger", 3),
				   ("item:motte_de_beurre", 1), ("item:miel_de_bruyere", 1)]),
	dict(id="tourte_poires", nom="Tourte aux poires", icon="🥧", poids=1.0, rarete="commun",
		 prix=(36, 85), qp=1,
		 description="Tourte garnie de poires et parfois parfumée avec des épices.",
		 effets={"pv": 16, "duree": 6, "buffs": {"Ch": 5}},
		 matieres=[("item:farine_de_froment", 2), ("item:Poire_de_verger", 3),
				   ("item:motte_de_beurre", 1), ("item:epices_douces", 1)]),
	dict(id="galette_fruits_secs", nom="Galette aux fruits secs", icon="🍪", poids=0.35,
		 rarete="commun", prix=(30, 70), qp=2,
		 description="Galette garnie de noix, noisettes, raisins secs ou autres fruits séchés.",
		 effets={"pv": 12, "duree": 8, "regen_pv": 2},
		 matieres=[("item:farine_de_froment", 1), ("item:cerneaux_de_noix", 1),
				   ("item:raisins_secs", 2), ("item:miel_de_bruyere", 1)]),
	dict(id="biscuits_voyage", nom="Biscuits de voyage", icon="🍘", poids=0.4, rarete="commun",
		 prix=(16, 38), qp=5,
		 description="Biscuits très secs et résistants conçus pour être conservés plusieurs semaines.",
		 effets={"pv": 6, "duree": 12, "regen_pv": 1},
		 # Ni levain ni beurre : c'est précisément ce qui les fait tenir des semaines.
		 matieres=[("item:farine_de_froment", 2), ("item:farine_d_orge", 1), ("item:Sel", 1)]),
	dict(id="pain_epices_miel", nom="Pain d'épices au miel", icon="🍯", poids=0.5,
		 rarete="peu_commun", prix=(55, 130), qp=2,
		 description="Pain dense et parfumé au miel, à la cannelle et au gingembre.",
		 effets={"pv": 15, "pm": 10, "duree": 10, "buffs": {"Vol": 10}},
		 matieres=[("item:farine_de_seigle", 2), ("item:miel_de_bruyere", 3),
				   ("item:epices_douces", 2), ("item:oeufs_de_ferme", 1)]),
]

# ⚠️ `sous_categorie` des 15 produits : « boulangerie », la catégorie de métier demandée.
# Leur `categorie` de doc, elle, DOIT rester `consommable` — c'est ce champ que lisent
# `consommables.est_consommable`, la fiche d'objet et l'action 🍽️. Confondre les deux ferait
# des pains des objets inertes, qu'on ne pourrait ni manger ni poser dans un slot d'action.
SOUS_CATEGORIE_PRODUIT = "boulangerie"

# Cibles de rayon. ⚠️ Les farines sont BASSES à dessein (cf. décision 2 en tête de fichier).
STOCK_CIBLE = {
	"item": {
		"item:farine_de_froment": 4,
		"item:farine_de_seigle": 3,
		"item:farine_d_orge": 3,
		"item:levain_de_chef": 4,
		"item:miel_de_bruyere": 6,
		"item:motte_de_beurre": 6,
		"item:oeufs_de_ferme": 8,
		"item:epices_douces": 4,
		# ⚠️ `item:Sel` a une `sous_categorie` VIDE : `item_sous_categorie` retombe sur sa
		# `categorie` (`composant`), qui n'est dans aucune table — sans cette ligne il héritait du
		# `STOCK_CIBLE_DEFAUT` (25) et le fournil tenait 25 sachets de sel en vitrine.
		"item:Sel": 6,
	},
	"sous_categorie": {
		"grain": 12,
		"fruit_sec": 6,
		"aromate": 6,
		SOUS_CATEGORIE_PRODUIT: 6,
	},
}

# Semis d'ouverture : de quoi que les deux tourtes soient en rayon dès l'import, et que le
# four ne parte pas de rien. ⚠️ Les fruits ne sont PAS approvisionnés (cf. décision 3) — ce
# stock-là s'épuise, et c'est le commerce qui doit le reconstituer.
STOCK_MATIERES_DEPART = {
	"item:grain_de_froment": 24,
	"item:grain_de_seigle": 18,
	"item:grain_d_orge": 15,
	"item:levain_de_chef": 8,
	"item:Sel": 8,
	"item:miel_de_bruyere": 6,
	"item:motte_de_beurre": 6,
	"item:oeufs_de_ferme": 6,
	"item:cerneaux_de_noix": 6,
	"item:raisins_secs": 6,
	"item:epices_douces": 4,
	"item:herbes_de_fournil": 6,
	"item:Pomme_de_verger": 12,
	"item:Poire_de_verger": 12,
}


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def cases_des_cuisines(docs: list) -> list:
	"""Cases de la grille de la CITÉ où s'ouvrent les cuisines, dans l'ordre de leurs liens.

	⚠️ C'est le nœud portant `CITE` qu'on lit, jamais l'autre : la `pos` du nœud boutique est
	`[0, 0]` (une boutique n'a pas de grille) et `get_lieu_links` scope l'affichage du lien à
	la case du lieu COURANT."""
	cuisines = {
		d["_id"] for d in docs
		if d.get("type") == "lieu" and d.get("categorie") == CATEGORIE_MODELE
		and d.get("lieu_parent") == CITE
	}
	trouvees = []
	for d in sorted(docs, key=lambda x: x.get("_id", "")):
		if d.get("type") != "connection":
			continue
		noeuds = d.get("nodes") or []
		if not any(n.get("lieu") in cuisines for n in noeuds):
			continue
		pos = next((n.get("pos") for n in noeuds if n.get("lieu") == CITE), None)
		if pos:
			trouvees.append([int(pos[0]), int(pos[1])])
	return trouvees


def prochain_indice_lien(docs: list) -> int:
	"""1 + le plus grand NN présent dans `link:<categorie>NN_to_<cité>` (convention de
	l'éditeur de lieux). 1 si la catégorie n'a encore aucune porte."""
	prefixe = "link:" + CATEGORIE
	suffixe = "_to_" + CITE.split(":", 1)[1]
	maxi = 0
	for d in docs:
		i = d.get("_id", "")
		if d.get("type") == "connection" and i.startswith(prefixe) and i.endswith(suffixe):
			nn = i[len(prefixe):-len(suffixe)]
			if nn.isdigit():
				maxi = max(maxi, int(nn))
	return maxi + 1


def item_matiere(cle, nom, icon, sous_cat, poids, pmin, pmax, description) -> dict:
	return {
		"_id": "item:" + cle,
		"type": "item",
		"nom": nom,
		"icon": icon,
		"description": description,
		"rarete": "commun",
		"categorie": "composant",
		"sous_categorie": sous_cat,
		"slots": [],
		"tags": [],
		"poids": poids,
		"valeur": [{"cu": pmin}, {"cu": pmax}],
	}


def doc_boutique(spec: dict, pos: list) -> list:
	"""Le doc lieu + sa porte dans la grille de la cité."""
	lieu = {
		"_id": spec["_id"],
		"type": "lieu",
		"label": spec["label"],
		"image": spec["image"],
		"categorie": CATEGORIE,
		"lieu_parent": CITE,
		# ⚠️ `portrait` volontairement ABSENT de l'entrée : aucune image
		# `marchand_*_boulangerie.png` n'existe encore, et un champ vide fait justement
		# retomber `pnj_payload` sur le portrait du doc générique — ce qu'on veut — là où un
		# nom de fichier inventé donnerait une image cassée. Seul le NOM est posé : chaque
		# fournil a son tenancier, et aucun texte de dialogue ne le cite en dur.
		"pnj": [{"character": "pnj:marchand_" + CATEGORIE, "nom": spec["tenancier"]}],
		"stock_matieres": dict(STOCK_MATIERES_DEPART),
		"stock_vente": [],
		"stock_cible": json.loads(json.dumps(STOCK_CIBLE)),
	}
	lien = {
		"_id": spec["link_id"],
		"type": "connection",
		"nodes": [
			{"lieu": CITE, "pos": pos},
			{"lieu": spec["_id"], "pos": [0, 0]},
		],
		"metadata": {"type": CATEGORIE, "status": "ouvert"},
	}
	return [lieu, lien]


def main() -> None:
	docs_base = charger(SRC_DUMP)
	cases = cases_des_cuisines(docs_base)
	if len(cases) < len(BOUTIQUES):
		raise SystemExit(
			f"{len(cases)} cuisine(s) trouvée(s) sous {CITE}, il en faut {len(BOUTIQUES)} — "
			f"les boulangeries se posent sur leurs cases."
		)
	depart = prochain_indice_lien(docs_base)

	out: list = []

	# 1. Le tenancier générique, bâti par le MÊME gabarit que les 29 autres.
	nom, metier, ambiance = METIERS[CATEGORIE]
	out.append({
		"_id": "pnj:marchand_" + CATEGORIE,
		"type": "pnj",
		"nom": nom,
		"race": "humain",
		"vocation": "marchand",
		# Portrait de la rotation générique de gen_marchands, à remplacer par un portrait de
		# métier le jour où il en existera un.
		"portrait": PORTRAITS[0],
		"services": {
			"transport": {"noeuds": dict(NOEUDS_TRANSPORT)},
			"escorte": {"noeuds": dict(NOEUDS_ESCORTE)},
		},
		"dialogue": dialogue(metier, ambiance),
	})

	# 2. Les matières premières (feuilles) et les trois farines (intermédiaires).
	for (cle, nom_i, icon, sous_cat, poids, pmin, pmax, desc) in MATIERES:
		out.append(item_matiere(cle, nom_i, icon, sous_cat, poids, pmin, pmax, desc))
	for (cle, nom_i, icon, _grain, pmin, pmax, desc) in FARINES:
		out.append(item_matiere(cle, nom_i, icon, "farine", 0.4, pmin, pmax, desc))

	# 3. La poire, pendant exact de la pomme du jardinier (cf. décision 3).
	out.append({
		"_id": "item:Poire_de_verger",
		"type": "item",
		"nom": "Poire de verger",
		"icon": "🍐",
		"description": "Poire de plein vent, ferme et granuleuse, qu'on cueille avant qu'elle ne blettisse.",
		"rarete": "commun",
		"categorie": "consommable",
		"sous_categorie": "fruit",
		"slots": [],
		"tags": ["plante"],
		"poids": 0.25,
		"effets": {"pv": 5},
	})
	# ⚠️ Deux recettes, calquées sur celles de `Pomme_de_verger` (1 graine → 3, 2 → 7) : sans
	# elles la poire serait une FEUILLE, donc livrée d'office au fournil — et les deux tourtes
	# ne se comporteraient pas pareil.
	for suffixe, qg, qp in (("", 1, 3), ("_lot", 2, 7)):
		out.append({
			"_id": "recette:jardinier_poire_de_verger" + suffixe,
			"type": "recette",
			"lieu_categorie": "jardinier",
			"objet_final": "Poire_de_verger",
			"quantite_produite": qp,
			"matieres_premieres": [{"sous_categorie": "graines", "quantite": qg}],
		})

	# 4. Les recettes de mouture : grain ×3 → 1 farine.
	for (cle, _nom_i, _icon, grain, _pmin, _pmax, _desc) in FARINES:
		out.append({
			"_id": "recette:boulangerie_" + cle,
			"type": "recette",
			"lieu_categorie": CATEGORIE,
			"objet_final": cle,
			"quantite_produite": 1,
			"matieres_premieres": [{"item": "item:" + grain, "quantite": 3}],
		})

	# 5. Les 15 produits + leurs recettes.
	for p in PRODUITS:
		out.append({
			"_id": "item:" + p["id"],
			"type": "item",
			"nom": p["nom"],
			"icon": p["icon"],
			"description": p["description"],
			"rarete": p["rarete"],
			"categorie": "consommable",
			"sous_categorie": SOUS_CATEGORIE_PRODUIT,
			"slots": [],
			"tags": [],
			"poids": p["poids"],
			"valeur": [{"cu": p["prix"][0]}, {"cu": p["prix"][1]}],
			"effets": p["effets"],
		})
		out.append({
			"_id": "recette:boulangerie_" + p["id"],
			"type": "recette",
			"lieu_categorie": CATEGORIE,
			"objet_final": p["id"],
			"quantite_produite": p["qp"],
			"matieres_premieres": [
				{"item": item_id, "quantite": q} for (item_id, q) in p["matieres"]
			],
		})

	# 6. Les deux boutiques, sur les cases des cuisines.
	for i, spec in enumerate(BOUTIQUES):
		spec = dict(spec)
		spec["link_id"] = f"link:{CATEGORIE}{depart + i:02d}_to_{CITE.split(':', 1)[1]}"
		out.extend(doc_boutique(spec, cases[i]))

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(out, f, ensure_ascii=False, indent=2)
	print(f"{len(out)} docs écrits dans {SORTIE}")
	for i, spec in enumerate(BOUTIQUES):
		print(f"  {spec['label']} → case {cases[i]} de {CITE}")


if __name__ == "__main__":
	main()

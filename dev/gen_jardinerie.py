"""Ouvre la filière végétale : le jardinier cultive, l'apothicaire et l'alchimiste transforment.

    python dev/gen_jardinerie.py [chemin/vers/telluris-dump-*.json]

Sortie :
    jsons/jardinerie_a_importer.json   (à coller dans la carte d'import de /admin)

Trois métiers, une chaîne :

    graines (feuille, vendue au jardinier)
        └─ 10 plantes cultivées      (jardinier, 20 recettes : 2 conduites par plante)
             ├─ 6 fruits & légumes   → consommables modestes, et matière de l'apothicaire
             └─ 4 simples            → matière de l'apothicaire ET de l'alchimiste
                  └─ remèdes, tisanes, philtres  (apothicairerie + laboratoire_d_alchimie)

DEUX CONDUITES PAR PLANTE, et c'est là tout l'intérêt mécanique : « semis » ne
consomme que des graines, « fumée » y ajoute de l'ENGRAIS et rend bien davantage.
Or l'engrais est déjà produit sur place (`recette:…` poudre d'os → engrais) et
n'était jusqu'ici consommé par personne : le pool unifié du tick atelier
(stock_matieres PUIS surplus du rayon) le fait donc chaîner tout seul, sans
duplication. Cf. CLAUDE.md § Marché, « pool unifié ».

⚠️ Toute matière consommée devient une FEUILLE auto-approvisionnée, donc vendue
sur place (CLAUDE.md § Armement & matières premières). Ici c'est voulu et c'est
la seule feuille neuve : `graines` — un jardinier vend des semences. Tout le
reste des intrants est soit déjà en base (graisse, sang, réactif brut, herbes),
soit produit sur place.

⚠️ Une clé matière **sous-catégorie** est résolue en `item:<sous_categorie>` :
d'où le doc `item:graines` (11ᵉ item du jardin), sans lequel la matière serait
valorisée à vide. Partout ailleurs les nouvelles plantes sont référencées par
**item-ref** (`{"item": "item:…"}`) : deux simples de sous-catégorie `herbe` ne
doivent pas se confondre dans les recettes, exactement comme les deux herbes
déjà en base.

Le script lit le dump committé (source unique, cf. CLAUDE.md §11) et n'émet que
les docs ABSENTS de la base : relancé après import, il ne produit rien.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")

# ── Le jardin ────────────────────────────────────────────────────────────────
# (slug, nom, icon, categorie, sous_categorie, poids, rarete, effets, description,
#  rendement du semis, conduite 2 : (graines, engrais, rendement))
#
# `slug` EST l'`objet_final` des recettes : `objet_final_item_id` en dérive
# `item:<slug>`, donc l'id du doc item doit lui correspondre au caractère près.
#
# ⚠️ POURQUOI l'engrais ne va QU'AUX SIMPLES. `cout_production_cuivre` prend le
# **MAX** sur les recettes qui produisent un item, pas le min : la conduite la plus
# CHÈRE fixe le prix. Or l'engrais coûte déjà 45 cu (poudre d'os ×3 × marge), donc
# le mettre sur un chou le ferait valoir 58 cu — plus cher qu'un remède. Les fruits
# et légumes doublent donc leur conduite en semis serré (graines ×2, meilleur
# rendement) et restent à quelques cuivres, tandis que les quatre simples portent
# la conduite fumée : eux DOIVENT être chers, c'est là que se fait la valeur.
PLANTES = [
	("Chou_pomme", "Chou pommé", "🥬", "consommable", "legume", 1.0, "commun",
	 {"pv": 6},
	 "Un chou dense et serré, qui tient tout l'hiver en cave.", 2, (2, 0, 5)),
	("Panais_de_sillon", "Panais de sillon", "🥕", "consommable", "legume", 0.4, "commun",
	 {"pv": 5},
	 "Racine sucrée des sillons de bord de champ, meilleure après les gelées.", 3, (2, 0, 7)),
	("Feves_de_carreau", "Fèves de carreau", "🫘", "consommable", "legume", 0.3, "commun",
	 {"pv": 4, "duree": 3, "regen_pv": 1},
	 "Fèves plates semées au carreau ; nourrissent longtemps le marcheur.", 3, (2, 0, 8)),
	("Ail_des_moines", "Ail des moines", "🧄", "consommable", "legume", 0.1, "commun",
	 {"pv": 3},
	 "Ail de cloître, si piquant qu'on le dit capable d'assainir une plaie.", 2, (2, 0, 6)),
	("Pomme_de_verger", "Pomme de verger", "🍎", "consommable", "fruit", 0.2, "commun",
	 {"pv": 5},
	 "Pomme de plein vent, dure et acide, qui se garde jusqu'au carême.", 3, (2, 0, 7)),
	("Prunelles_de_haie", "Prunelles de haie", "🫐", "consommable", "fruit", 0.1, "commun",
	 {"pv": 3, "pm": 3},
	 "Petites prunes noires de haie vive, âpres tant qu'elles n'ont pas gelé.", 2, (2, 0, 6)),
	("Racine_de_mandragore", "Racine de mandragore", "🌱", "composant", "racine", 0.3, "peu_commun",
	 None,
	 "Racine fourchue arrachée de nuit, réputée crier. Base de bien des philtres.", 1, (1, 2, 2)),
	("Fleur_de_souci", "Fleur de souci", "🌼", "composant", "fleur", 0.05, "commun",
	 None,
	 "Fleur orange du potager, séchée en corolles pour les tisanes et les baumes.", 2, (1, 1, 6)),
	("Capsules_de_pavot", "Capsules de pavot", "🥀", "composant", "herbe", 0.05, "commun",
	 None,
	 "Têtes de pavot cueillies vertes ; leur lait endort la douleur.", 2, (1, 1, 5)),
	("Feuilles_d_absinthe", "Feuilles d'absinthe", "🍃", "composant", "herbe", 0.05, "commun",
	 None,
	 "Feuilles argentées d'une amertume tenace, chères aux distillateurs.", 2, (1, 1, 6)),
]

# ⚠️ PRIX TENU À LA MAIN pour les quatre simples. Sans cela leur valeur serait celle
# de la conduite fumée (`cout_production_cuivre` prend le MAX sur les recettes, pas le
# min) : l'engrais à 45 cu ferait valoir une fleur de souci 38 cu, soit près de quatre
# fois un remède (18 cu) — et tout ce qu'on en tire exploserait à son tour, la marge de
# transformation étant multiplicative (×5 par étape). Le champ `valeur` est AUTORITAIRE
# (cf. `item_sale_price_cuivre`) : c'est le levier prévu pour cadrer une matière dont on
# ne veut pas subir la chaîne. Repère : `item:Herbes_medicinales` (feuille) vaut 1 cu ;
# une plante cultivée vaut quelques cuivres, la mandragore beaucoup plus.
VALEURS_CU = {
	"Racine_de_mandragore": 60,
	"Fleur_de_souci": 6,
	"Capsules_de_pavot": 8,
	"Feuilles_d_absinthe": 6,
}

# La seule matière neuve à acheter : le jardinier vend ses semences.
GRAINES = {
	"_id": "item:graines",
	"type": "item",
	"nom": "Graines",
	"icon": "🌾",
	"description": "Sachet de semences potagères et de simples, trié par le jardinier.",
	"rarete": "commun",
	"categorie": "composant",
	"sous_categorie": "graines",
	"slots": [],
	"tags": ["plante"],
	"poids": 0.05,
}

# ── Ce que l'apothicaire et l'alchimiste en font ─────────────────────────────
# Items NEUFS produits par ces deux métiers (mêmes champs que le jardin).
PRODUITS = [
	("Tisane_de_souci", "Tisane de souci", "🍵", "consommable", "", 0.1, "commun",
	 {"pv": 8, "duree": 4, "regen_pv": 2},
	 "Infusion de fleurs de souci : referme les petites plaies et calme la fièvre."),
	("Sirop_de_pavot", "Sirop de pavot", "🍯", "consommable", "", 0.2, "peu_commun",
	 {"pv": 10, "duree": 6, "regen_pv": 4},
	 "Sirop épais au lait de pavot. Endort la douleur ; à doser d'une main sûre."),
	("Emplatre_d_ail", "Emplâtre d'ail", "🧄", "consommable", "", 0.2, "commun",
	 {"pv": 14},
	 "Cataplasme d'ail pilé dans la graisse, appliqué brûlant sur la blessure."),
	("Compote_fortifiante", "Compote fortifiante", "🥣", "consommable", "", 0.4, "peu_commun",
	 {"pv": 20, "duree": 8, "buffs": {"R": 5}},
	 "Fruits du verger longuement cuits : un repas de convalescent qui tient au corps."),
	("Tisane_du_marcheur", "Tisane du marcheur", "🫖", "consommable", "", 0.1, "commun",
	 {"duree": 6, "buffs": {"V": 1}},
	 "Amère et brûlante, elle délie les jambes pour une bonne partie du chemin."),
	("Extrait_de_mandragore", "Extrait de mandragore", "⚗️", "composant", "", 0.1, "peu_commun",
	 None,
	 "Suc de racine réduit à froid, matière première des philtres du sommeil."),
	("Philtre_de_songe", "Philtre de songe", "🌙", "consommable", "", 0.2, "peu_commun",
	 {"duree": 8, "buffs": {"Vol": 10}},
	 "Le buveur dort les yeux ouverts et rien ne semble plus pouvoir l'atteindre."),
	("Absinthe_verte", "Absinthe verte", "🍸", "consommable", "", 0.2, "peu_commun",
	 {"pm": 25, "duree": 4, "regen_pm": 3},
	 "Distillat vert pâle, amer à faire pleurer, qui rouvre les canaux de la magie."),
	("Vinaigre_des_quatre_voleurs", "Vinaigre des quatre voleurs", "🫙", "consommable", "", 0.3, "peu_commun",
	 {"pv": 12, "duree": 6, "regen_pv": 2},
	 "Macération d'ail et d'absinthe dont on se frotte avant d'entrer chez les pestiférés."),
	("Eau_de_prunelle", "Eau de prunelle", "🥃", "consommable", "", 0.2, "commun",
	 {"pm": 15, "duree": 5, "regen_pm": 2},
	 "Eau-de-vie de prunelles, tirée au bain-marie sous l'œil de l'alchimiste."),
]

# Recettes de transformation. (id, lieu_categorie, objet_final, quantite_produite, matières)
# Une matière = {"item": …} (référence précise) ou {"sous_categorie": …}.
# ⚠️ Les plantes passent TOUJOURS par item-ref : deux simples partagent la
# sous-catégorie `herbe`, les confondre changerait la recette en silence.
TRANSFORMATIONS = [
	# --- Apothicairerie ---------------------------------------------------
	("recette:apothicaire_tisane_de_souci", "apothicairerie", "Tisane_de_souci", 2, [
		{"item": "item:Fleur_de_souci", "quantite": 2},
		{"item": "item:Herbes_medicinales", "quantite": 1},
	]),
	("recette:apothicaire_sirop_de_pavot", "apothicairerie", "Sirop_de_pavot", 2, [
		{"item": "item:Capsules_de_pavot", "quantite": 2},
		# Produit sur place (recette:apothicaire_sirop_de_seve) → pool unifié.
		{"item": "item:sirop_de_seve", "quantite": 1},
	]),
	("recette:apothicaire_emplatre_d_ail", "apothicairerie", "Emplatre_d_ail", 2, [
		{"item": "item:Ail_des_moines", "quantite": 2},
		{"sous_categorie": "graisse", "quantite": 1},
	]),
	("recette:apothicaire_compote_fortifiante", "apothicairerie", "Compote_fortifiante", 2, [
		{"item": "item:Pomme_de_verger", "quantite": 2},
		{"item": "item:Prunelles_de_haie", "quantite": 2},
	]),
	("recette:apothicaire_tisane_du_marcheur", "apothicairerie", "Tisane_du_marcheur", 2, [
		{"item": "item:Feuilles_d_absinthe", "quantite": 1},
		{"item": "item:Fleur_de_souci", "quantite": 1},
		{"item": "item:Herbes_medicinales", "quantite": 1},
	]),
	# --- Laboratoire d'alchimie -------------------------------------------
	# Deux fioles par racine : sans ce rendement, l'extrait puis le philtre
	# encaisseraient deux fois la marge de transformation (×5) et le philtre
	# vaudrait plus cher qu'un cheval. Cf. `cout_production_cuivre`.
	("recette:alchimie_extrait_de_mandragore", "laboratoire_d_alchimie", "Extrait_de_mandragore", 2, [
		{"item": "item:Racine_de_mandragore", "quantite": 1},
	]),
	("recette:alchimie_philtre_de_songe", "laboratoire_d_alchimie", "Philtre_de_songe", 1, [
		{"item": "item:Capsules_de_pavot", "quantite": 2},
		# Intermédiaire produit sur place, réutilisé dans le même tick.
		{"item": "item:Extrait_de_mandragore", "quantite": 1},
	]),
	("recette:alchimie_absinthe_verte", "laboratoire_d_alchimie", "Absinthe_verte", 1, [
		{"item": "item:Feuilles_d_absinthe", "quantite": 3},
		# ⚠️ Item-ref et NON la sous-catégorie `reactif_brut` : le doc générique
		# `item:reactif_brut` n'existe pas (il s'appelle `item:Reactif_brut`), la
		# matière serait valorisée à vide — c'est le cas prévu par CLAUDE.md
		# § Armement & matières premières. Les 5 recettes d'alchimie déjà en base
		# qui passent par la sous-catégorie ont ce défaut, à corriger à part.
		{"item": "item:Reactif_brut", "quantite": 1},
	]),
	("recette:alchimie_vinaigre_quatre_voleurs", "laboratoire_d_alchimie", "Vinaigre_des_quatre_voleurs", 2, [
		{"item": "item:Ail_des_moines", "quantite": 3},
		{"item": "item:Feuilles_d_absinthe", "quantite": 1},
	]),
	("recette:alchimie_eau_de_prunelle", "laboratoire_d_alchimie", "Eau_de_prunelle", 2, [
		{"item": "item:Prunelles_de_haie", "quantite": 4},
		{"item": "item:Reactif_brut", "quantite": 1},
	]),
]

# ⚠️ AUCUNE de ces recettes ne vise un `objet_final` DÉJÀ produit en base, et ce
# n'est pas un oubli : `cout_production_cuivre` prend le MAX sur les recettes qui
# produisent un item. Ajouter une voie « à base de plantes » au remède, à la potion
# ou au composant rituel aurait donc RENCHÉRI ces produits pour tout le monde — de
# 18 à 285 cu pour le remède, de 25 à 1140 pour le composant rituel — sans rien
# retirer à l'ancienne voie. Une filière neuve se branche par des produits neufs.


def charger_dump(chemin=None):
	if chemin:
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez le chemin en argument.")
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def doc_item(slug, nom, icon, categorie, sous_categorie, poids, rarete, effets, description):
	"""Doc `item:*` au format exact de ceux déjà en base (cf. item:Herbes_medicinales)."""
	doc = {
		"_id": "item:" + slug,
		"type": "item",
		"nom": nom,
		"icon": icon,
		"description": description,
		"rarete": rarete,
		"categorie": categorie,
		"sous_categorie": sous_categorie,
		"slots": [],
		"tags": ["plante"] if sous_categorie in ("legume", "fruit", "racine", "fleur", "herbe") else [],
		"poids": poids,
	}
	if effets:
		doc["effets"] = effets
	if slug in VALEURS_CU:
		doc["valeur"] = [{"cu": VALEURS_CU[slug]}]
	return doc


def main():
	dump = charger_dump(sys.argv[1] if len(sys.argv) > 1 else None)
	ids_pris = {d["_id"] for d in dump["docs"]}

	sortie = []
	ignores = []

	def ajouter(doc):
		if doc["_id"] in ids_pris:
			ignores.append(doc["_id"])   # déjà en base — un PUT l'écraserait
			return
		ids_pris.add(doc["_id"])
		sortie.append(doc)

	# 1. La semence, puis les 10 plantes.
	ajouter(GRAINES)
	for (slug, nom, icon, cat, sous_cat, poids, rarete, effets, desc, _semis, _c2) in PLANTES:
		ajouter(doc_item(slug, nom, icon, cat, sous_cat, poids, rarete, effets, desc))

	# 2. Deux conduites de culture par plante = 20 recettes de jardinier.
	for (slug, _nom, _ic, _cat, _sc, _p, _r, _ef, _d, semis, conduite2) in PLANTES:
		graines2, engrais2, rendement2 = conduite2
		ajouter({
			"_id": "recette:jardin_%s_semis" % slug.lower(),
			"type": "recette",
			"lieu_categorie": "jardinier",
			"objet_final": slug,
			"quantite_produite": semis,
			"matieres_premieres": [{"sous_categorie": "graines", "quantite": 1}],
		})
		matieres2 = [{"sous_categorie": "graines", "quantite": graines2}]
		if engrais2:
			# Produit sur place (poudre d'os → engrais) et jusqu'ici consommé par
			# personne : le pool unifié du tick atelier le fait chaîner tout seul.
			matieres2.append({"item": "item:engrais", "quantite": engrais2})
		ajouter({
			"_id": "recette:jardin_%s_%s" % (slug.lower(), "fumee" if engrais2 else "serree"),
			"type": "recette",
			"lieu_categorie": "jardinier",
			"objet_final": slug,
			"quantite_produite": rendement2,
			"matieres_premieres": matieres2,
		})

	# 3. Les produits transformés, puis les recettes qui les font.
	for (slug, nom, icon, cat, sous_cat, poids, rarete, effets, desc) in PRODUITS:
		ajouter(doc_item(slug, nom, icon, cat, sous_cat, poids, rarete, effets, desc))
	for (rid, lieu_cat, objet, quantite, matieres) in TRANSFORMATIONS:
		ajouter({
			"_id": rid,
			"type": "recette",
			"lieu_categorie": lieu_cat,
			"objet_final": objet,
			"quantite_produite": quantite,
			"matieres_premieres": matieres,
		})

	# 4. Contrôle : toute matière référencée doit exister (sinon valorisée à vide).
	manquants = []
	for d in sortie:
		if d.get("type") != "recette":
			continue
		for m in d["matieres_premieres"]:
			cle = m.get("item") or m.get("sous_categorie")
			item_id = cle if str(cle).startswith("item:") else "item:" + str(cle)
			if item_id not in ids_pris:
				manquants.append((d["_id"], cle, item_id))

	chemin = os.path.join(DOSSIER_JSONS, "jardinerie_a_importer.json")
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")

	# La console Windows est en cp1252 : sans cela, un accent fait planter le script
	# APRÈS l'écriture du fichier — panne trompeuse.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	items = [d for d in sortie if d["type"] == "item"]
	recettes = [d for d in sortie if d["type"] == "recette"]
	print("Items   : %d" % len(items))
	print("Recettes: %d  (jardinier %d, apothicairerie %d, laboratoire_d_alchimie %d)" % (
		len(recettes),
		sum(1 for r in recettes if r["lieu_categorie"] == "jardinier"),
		sum(1 for r in recettes if r["lieu_categorie"] == "apothicairerie"),
		sum(1 for r in recettes if r["lieu_categorie"] == "laboratoire_d_alchimie"),
	))
	if ignores:
		print("Déjà en base, non ré-émis : %s" % ", ".join(ignores))
	if manquants:
		print()
		print("⚠ Matières sans doc item (valorisées à vide) :")
		for rid, cle, item_id in manquants:
			print("   %-52s %-24s -> %s" % (rid, cle, item_id))
	print()
	print("→ %s" % chemin)


if __name__ == "__main__":
	main()

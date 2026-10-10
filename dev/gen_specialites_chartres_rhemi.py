"""Spécialités de terroir de CHARTRES et de RHEMI, et le métier neuf de la CAVE.

Recettes PORTÉES (`lieu_portee`, cf. dev/gen_specialites_france.py) : cuisinables seulement
par les boutiques dont la chaîne `lieu_parent` remonte jusqu'à `lieu:chartres` ou
`lieu:rhemi`. Les boissons et les condiments relèvent d'un métier qui n'existait pas, la
`cave` : ses recettes et son tenancier générique (`pnj:marchand_cave`) sont dans ce lot, ses
BOUTIQUES se posent ensuite à l'éditeur (lot de lieux, mode Lieux) — la catégorie y apparaît
d'elle-même dès que ses recettes sont en base.

    python dev/gen_specialites_chartres_rhemi.py [chemin/vers/telluris-dump-*.json]

Sortie : jsons/specialites_chartres_rhemi_a_importer.json (carte d'import de /admin)

Matières : on RÉUTILISE ce qui existe (`item:Miel`, farines, beurre, œufs, Vin de pays…) ;
les neuves sont génériques (`item:Raisin`, pas « Raisin de Champagne ») — le terroir vit dans
la recette et le nom du produit, pas dans ses intrants.

⚠️ Garde-fous, rien n'est écrit si l'un échoue :
  · `_id` déjà pris par un doc DIFFÉRENT ⇒ refus ; doc identique en base ⇒ sauté (idempotent) ;
  · tout intrant a son doc (en base ou dans ce lot) ;
  · une matière neuve n'est produite par aucune recette (sinon ce ne serait pas une feuille) ;
  · un intermédiaire du lot (Eau-de-vie, Champagne, Vinaigre) est produit par le MÊME métier
    que sa consommatrice, sous une portée qui couvre la sienne — sinon fausse feuille ;
  · la recette n'est servie qu'aux boutiques de sa portée, et au moins une existe — SAUF pour
    la cave, métier neuf : simple avertissement tant que ses boutiques ne sont pas posées.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_specialites_france import _atteignables, brancher_moteur, charger, chemin_dump  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "specialites_chartres_rhemi_a_importer.json")

CHARTRES = "lieu:chartres"
RHEMI = "lieu:rhemi"
PAYS = "lieu:france"
CAVE = "cave"
# Métiers neufs : leurs boutiques n'existent pas encore, l'absence d'atelier n'est qu'un avis.
METIERS_NEUFS = {CAVE}


# ── Matières neuves (feuilles) ───────────────────────────────────────────────────
# (slug, nom, icon, sous_categorie, rareté, poids, valeur_min, valeur_max, description)
MATIERES = [
	("Sucre", "Sucre", "🧂", "sucre", "commun", 0.5, 20, 50,
	 "Pain de sucre roux, cassé au marteau et vendu au poids. Il vient de loin, et cela se "
	 "sent au prix."),
	("Raisin", "Raisin", "🍇", "raisin", "commun", 1.0, 8, 20,
	 "Grappes cueillies du matin, à presser avant le soir : passé un jour, le jus tourne."),
	("Graines_de_moutarde", "Graines de moutarde", "🌱", "moutarde", "commun", 0.2, 6, 16,
	 "Petites graines brunes qui piquent le nez dès qu'on les écrase."),
	("Truffe", "Truffe", "🍄", "truffe", "rare", 0.1, 60, 160,
	 "Tubercule noir déterré au pied des chênes. Son parfum traverse le papier qui l'enveloppe "
	 "et la moitié de la boutique."),
]


# ── Produits et recettes ─────────────────────────────────────────────────────────
# slug → (nom, icon, rareté, catégorie, sous_catégorie, poids, effets, métier, portée,
#         intrants [(item_id, qté)], quantité produite, description)
PRODUITS = {
	# — Chartres —
	"Pate_de_Chartres": (
		"Pâté de Chartres", "🥧", "rare", "consommable", "cuisine", 0.9,
		{"pv": 36, "pm": 8, "duree": 10, "buffs": {"F": 4}}, "cuisine", CHARTRES,
		[("item:viande", 3), ("item:foie", 1), ("item:farine_de_froment", 2),
		 ("item:motte_de_beurre", 1), ("item:oeufs_de_ferme", 1), ("item:Truffe", 1)], 2,
		"Pâté en croûte garni de gibier — faisan, perdreau ou lièvre selon la chasse — et relevé "
		"de truffe. Les cuisiniers de Chartres le dorent à l'œuf et ne le coupent que froid."),
	"Mentchikoff": (
		"Mentchikoff", "🍬", "peu_commun", "consommable", "boulangerie", 0.05,
		{"pm": 12, "duree": 6, "buffs": {"Cha": 3}}, "boulangerie", CHARTRES,
		[("item:Amandes", 2), ("item:Sucre", 3), ("item:oeufs_de_ferme", 1)], 6,
		"Bonbon au cœur de praliné, enrobé d'une fine coque blanche qui imite la meringue. On "
		"l'offre par cornets entiers, et on en garde un pour soi."),
	"Sable_de_Beauce": (
		"Sablé de Beauce", "🍪", "commun", "consommable", "boulangerie", 0.1,
		{"pv": 12, "duree": 6, "buffs": {"R": 2}}, "boulangerie", CHARTRES,
		[("item:farine_de_froment", 2), ("item:motte_de_beurre", 2), ("item:Sucre", 1)], 6,
		"Biscuit sec et croustillant de farine de Beauce et de beurre frais. Il voyage bien et "
		"s'émiette dans la poche."),
	"Hydromel_de_Beauce": (
		"Hydromel de Beauce", "🍯", "peu_commun", "consommable", "boisson", 1.0,
		{"pm": 15, "duree": 6, "buffs": {"Vol": 3}}, CAVE, CHARTRES,
		[("item:Miel", 3)], 2,
		"Miel de Beauce laissé à fermenter des mois en tonneau. Doux à la première gorgée, "
		"traître à la troisième."),
	"Eure_et_Liqueur": (
		"Eure-et-Liqueur", "🥃", "rare", "consommable", "boisson", 0.7,
		{"pm": 20, "duree": 8, "buffs": {"Vol": 4}}, CAVE, CHARTRES,
		[("item:Miel", 2), ("item:Eau_de_vie", 1), ("item:epices_douces", 1)], 2,
		"Liqueur au miel de Beauce, montée à l'eau-de-vie et aux épices. Le nom fait sourire "
		"les Chartrains ; la boisson, beaucoup moins après le deuxième verre."),

	# — Rhemi —
	"Biscuit_rose_de_Reims": (
		"Biscuit rose de Reims", "🌸", "peu_commun", "consommable", "boulangerie", 0.05,
		{"pv": 10, "pm": 8, "duree": 6, "buffs": {"Cha": 3}}, "boulangerie", RHEMI,
		[("item:farine_de_froment", 1), ("item:oeufs_de_ferme", 3), ("item:Sucre", 2)], 6,
		"Biscuit cuillère léger comme l'air, teinté de rose et poudré de sucre. On le trempe "
		"dans le champagne ou le ratafia, et il ne s'en remet pas."),
	"Jambon_de_Reims": (
		"Jambon de Reims", "🍖", "peu_commun", "consommable", "salaison", 1.2,
		{"pv": 28, "duree": 8, "buffs": {"R": 4}}, "salaison", RHEMI,
		[("item:viande", 3), ("item:Vin_de_pays", 1), ("item:herbes_de_fournil", 1),
		 ("item:Sel", 1)], 2,
		"Jambon cuit et désossé, mariné au bouillon et au vin blanc, puis moulé au persil dans "
		"une gelée parfumée. Il se tranche fin et se garde au frais."),
	"Pieds_de_cochon_a_la_Sainte_Menehould": (
		"Pieds de cochon à la Sainte-Menehould", "🐖", "peu_commun", "consommable", "cuisine", 0.8,
		{"pv": 26, "duree": 8, "buffs": {"F": 3}}, "cuisine", RHEMI,
		[("item:viande", 2), ("item:farine_de_froment", 1), ("item:motte_de_beurre", 1),
		 ("item:oeufs_de_ferme", 1), ("item:Sel", 1)], 2,
		"Pieds de porc bouillis si longtemps que l'os se mange, puis panés et grillés jusqu'à "
		"craquer sous la dent."),
	"Champagne": (
		"Champagne", "🍾", "rare", "consommable", "boisson", 1.5,
		{"pm": 20, "duree": 8, "buffs": {"Cha": 5}}, CAVE, RHEMI,
		[("item:Raisin", 4), ("item:Sucre", 1)], 2,
		"Vin blanc effervescent des coteaux de Rhemi, repris en bouteille pour y faire sa "
		"mousse. Le bouchon part tout seul, et parfois avec un doigt."),
	"Ratafia_de_Champagne": (
		"Ratafia de Champagne", "🍷", "peu_commun", "consommable", "boisson", 0.8,
		{"pm": 15, "duree": 6, "buffs": {"Ch": 3}}, CAVE, RHEMI,
		[("item:Raisin", 3), ("item:Eau_de_vie", 1)], 2,
		"Jus de raisin arrêté net dans sa fermentation par une rasade d'eau-de-vie. Sucré, fort, "
		"et servi en petits verres."),
	"Vinaigre_de_Reims": (
		"Vinaigre de Reims", "🫙", "commun", "composant", "condiment", 0.8,
		None, CAVE, RHEMI,
		[("item:Champagne", 1)], 3,
		"Vinaigre tiré du vin de Champagne, piquant et clair. Les caves de Rhemi en font avec "
		"ce qui n'a pas pris sa mousse."),
	"Moutarde_de_Reims": (
		"Moutarde de Reims", "🟡", "commun", "composant", "condiment", 0.4,
		None, CAVE, RHEMI,
		[("item:Graines_de_moutarde", 3), ("item:Vinaigre_de_Reims", 1), ("item:Sel", 1)], 3,
		"Graines broyées au vinaigre de Reims. Elle monte au nez avant d'arriver à la langue."),

	# — Intermédiaire de toutes les caves —
	"Eau_de_vie": (
		"Eau-de-vie", "⚗️", "commun", "composant", "alcool", 0.6,
		None, CAVE, PAYS,
		[("item:Vin_de_pays", 3)], 1,
		"Vin passé à l'alambic jusqu'à n'en garder que le feu. Les caves la gardent pour monter "
		"leurs liqueurs, rarement pour la boire pure."),
}


# `valeur` EXPLICITE (autoritative, coupe la propagation de `cout_production_cuivre`) sur les
# intermédiaires et condiments : chaque étape multiplie le coût par `MARGE_TRANSFO`, et la
# chaîne vin → eau-de-vie → liqueur sortait l'Eure-et-Liqueur à 630 cu, un vinaigre plus cher
# que le champagne dont il est tiré. Plafonnés ici, leurs consommatrices retombent dans
# l'échelle des spécialités existantes (Coq au vin 162, Galette des Rois 302).
VALEURS = {
	"Eau_de_vie": (45, 110),
	"Vinaigre_de_Reims": (12, 30),
	"Moutarde_de_Reims": (18, 45),
}


def matiere_doc(slug, nom, icon, sous_cat, rarete, poids, vmin, vmax, desc) -> dict:
	return {
		"_id": "item:" + slug, "type": "item", "nom": nom, "description": desc, "icon": icon,
		"rarete": rarete, "categorie": "composant", "sous_categorie": sous_cat,
		"slots": [], "tags": [], "poids": poids,
		"valeur": [{"cu": vmin}, {"cu": vmax}],
	}


def produit_docs(slug: str) -> tuple:
	"""(item, recette) d'un produit de PRODUITS."""
	(nom, icon, rarete, categorie, sous_cat, poids, effets, metier, portee,
	 intrants, quantite, desc) = PRODUITS[slug]
	item = {
		"_id": "item:" + slug, "type": "item", "nom": nom, "description": desc, "icon": icon,
		"rarete": rarete, "categorie": categorie, "sous_categorie": sous_cat,
		"slots": [], "tags": [], "poids": poids,
	}
	if effets:
		item["effets"] = effets
	if slug in VALEURS:
		vmin, vmax = VALEURS[slug]
		item["valeur"] = [{"cu": vmin}, {"cu": vmax}]
	recette = {
		"_id": "recette:specialite_%s" % slug.lower(), "type": "recette",
		"lieu_categorie": metier,
		"lieu_portee": portee,
		"objet_final": slug,
		"quantite_produite": quantite,
		"matieres_premieres": [{"item": cle, "quantite": q} for (cle, q) in intrants],
	}
	return item, recette


def tenancier_cave() -> dict:
	"""`pnj:marchand_cave`, bâti EXACTEMENT comme ses confrères : dialogue et services de
	`gen_marchands`, fragment de direction de `gen_direction_marchands`. Ne PAS relancer
	`gen_marchands` pour l'obtenir : il réécrit tous les tenanciers en PUT complet."""
	import gen_direction_marchands as gd
	import gen_marchands as gm
	nom, metier, ambiance = gm.METIERS[CAVE]
	doc = {
		"_id": "pnj:marchand_" + CAVE, "type": "pnj", "nom": nom, "race": "humain",
		"vocation": "marchand", "portrait": gm.portrait_de(CAVE),
		"services": {
			"transport": {"noeuds": dict(gm.NOEUDS_TRANSPORT)},
			"escorte": {"noeuds": dict(gm.NOEUDS_ESCORTE)},
		},
		"dialogue": gm.dialogue(metier, ambiance),
	}
	return gd.injecter(doc)


def construire_lot() -> list:
	"""Tous les docs du lot, dans un ordre stable (matières, produits, tenancier)."""
	lot = [matiere_doc(*m) for m in MATIERES]
	for slug in PRODUITS:
		lot.extend(produit_docs(slug))
	lot.append(tenancier_cave())
	return lot


def _portee_couvre(marche, portee_large: str, portee: str, index: dict) -> bool:
	"""`portee_large` est-elle `portee` ou l'un de ses ancêtres ?"""
	lieu = index.get(portee)
	return bool(lieu) and portee_large in marche.portees_lieu(lieu)


def main() -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	source = chemin_dump()
	docs = charger(source)
	index = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	_cs, marche = brancher_moteur(docs, index)

	erreurs, avis, nouveaux, deja = [], [], [], 0
	lot = construire_lot()
	ids_lot = {d["_id"] for d in lot}

	# --- 1. Collisions et idempotence -------------------------------------------------
	for doc in lot:
		existant = index.get(doc["_id"])
		if existant is None:
			nouveaux.append(doc)
		elif {k: v for k, v in existant.items() if k != "_rev"} == doc:
			deja += 1
		else:
			erreurs.append("%s : _id déjà pris par un autre doc" % doc["_id"])

	# --- 2. Intrants et feuilles, AVANT ajout ----------------------------------------
	produits_monde = {marche.objet_final_item_id(r.get("objet_final", ""))
					  for r in docs if isinstance(r, dict) and r.get("type") == "recette"}
	for (slug, *_r) in MATIERES:
		if "item:" + slug in produits_monde:
			erreurs.append("item:%s : déjà produit par une recette — pas une feuille" % slug)
	for slug, spec in PRODUITS.items():
		for cle, _q in spec[9]:
			if cle not in index and cle not in ids_lot:
				erreurs.append("%s : intrant %s sans doc" % (slug, cle))
		# Intermédiaire du lot : même métier, portée qui couvre celle de la consommatrice.
		for cle, _q in spec[9]:
			amont = PRODUITS.get(cle[len("item:"):])
			if amont is None:
				continue
			if amont[7] != spec[7]:
				erreurs.append("%s : %s vient du métier « %s », pas « %s » — fausse feuille"
							   % (slug, cle, amont[7], spec[7]))
			elif not _portee_couvre(marche, amont[8], spec[8], index):
				erreurs.append("%s : %s n'est produit que sous %s — fausse feuille"
							   % (slug, cle, amont[8]))

	# --- 3. Ajout du lot à la vue du moteur, puis service des recettes ----------------
	for doc in nouveaux:
		index[doc["_id"]] = doc
		docs.append(doc)
	marche.reset_prix_cache()

	lieux = [d for d in docs if isinstance(d, dict) and d.get("type") == "lieu"]
	rapport = []
	for slug, spec in PRODUITS.items():
		metier, portee = spec[7], spec[8]
		recette_id = "recette:specialite_%s" % slug.lower()
		if portee not in index or index[portee].get("type") != "lieu":
			erreurs.append("%s : `lieu_portee` %s n'est pas un lieu" % (recette_id, portee))
			continue
		ateliers = [L for L in lieux
					if metier in marche.categories_incluses(L.get("categorie") or "")
					and portee in marche.portees_lieu(L)]
		servie = sorted(L["_id"] for L in lieux
						if recette_id in {r.get("_id") for r in marche.recettes_lieu(L)})
		if servie != sorted(L["_id"] for L in ateliers):
			erreurs.append("%s : servie à %s, attendu %s"
						   % (recette_id, servie, sorted(L["_id"] for L in ateliers)))
			continue
		if marche.objet_final_item_id(slug) != "item:" + slug:
			erreurs.append("%s : objet_final « %s » ne résout pas" % (recette_id, slug))
		if not ateliers:
			msg = "%s : aucune boutique « %s » sous %s" % (recette_id, metier, portee)
			if metier in METIERS_NEUFS:
				avis.append(msg + " — à poser à l'éditeur")
			else:
				erreurs.append(msg + " — recette morte-née")
			continue
		manquantes = sorted({c for (c, _q) in spec[9]} - _atteignables(marche, ateliers[0]))
		rapport.append((spec[0], metier, portee, len(ateliers), manquantes))

	if erreurs:
		print("ABANDON — %d problème(s), aucun fichier écrit :" % len(erreurs))
		for e in erreurs:
			print("   ✗ %s" % e)
		return 1

	print("Dump lu : %s" % os.path.basename(source))
	if not nouveaux:
		print("base à jour : aucun fichier écrit")
		return 0
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(nouveaux, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print("Docs écrits : %d (%d déjà en base, sautés)" % (len(nouveaux), deja))
	print()
	print("%-38s %-12s %-14s %-9s %s" % ("produit", "métier", "portée", "ateliers", "intrants à ravitailler"))
	print("-" * 110)
	for nom, metier, portee, nb, manquantes in rapport:
		print("%-38s %-12s %-14s %-9d %s"
			  % (nom, metier, portee.replace("lieu:", ""), nb,
				 ", ".join(m.replace("item:", "") for m in manquantes) or "— autonome"))
	for a in avis:
		print("   ⚠ %s" % a)
	print()
	print("→ %s" % os.path.relpath(SORTIE, RACINE))
	return 0


if __name__ == "__main__":
	sys.exit(main())

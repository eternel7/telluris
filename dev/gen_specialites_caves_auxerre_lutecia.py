"""Spécialités de CAVE d'AUXERRE et de LUTÈCE — les boissons de terroir des caves posées par
dev/gen_spec_caves_negoces.py (sans elles, ces caves n'auraient que l'Eau-de-vie à produire).

Lot DISTINCT de dev/gen_specialites_chartres_rhemi.py, déjà en base : le métier `cave`, son
tenancier `pnj:marchand_cave` et l'intermédiaire `item:Eau_de_vie` (portée France) sont RELUS du
dump, jamais réémis. Mêmes formes de docs (`matiere_doc`, et la même construction de produit) et
mêmes garde-fous.

    python dev/gen_specialites_caves_auxerre_lutecia.py [chemin/vers/telluris-dump-*.json]

Sortie : jsons/specialites_caves_auxerre_lutecia_a_importer.json (carte d'import de /admin)

Matières : on RÉUTILISE (`item:Raisin`, `Vin_de_pays`, `Miel`, `epices_douces`, `grain_d_orge`,
`Eau_de_source`, `Sucre`) ; la seule neuve est générique (`item:Cassis`).

⚠️ Garde-fous, rien n'est écrit si l'un échoue :
  · `_id` déjà pris par un doc DIFFÉRENT ⇒ refus ; doc identique en base ⇒ sauté (idempotent) ;
  · tout intrant a son doc (en base ou dans ce lot) ;
  · une matière neuve n'est produite par aucune recette ;
  · un intermédiaire produit par une recette de la base vient du MÊME métier sous une portée qui
    couvre celle de sa consommatrice (l'Eau-de-vie des caves, portée France) ;
  · la recette n'est servie qu'aux boutiques de sa portée ; caves pas encore posées ⇒ avis.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_specialites_france import _atteignables, brancher_moteur, charger, chemin_dump  # noqa: E402
from gen_specialites_chartres_rhemi import CAVE, _portee_couvre, matiere_doc  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "specialites_caves_auxerre_lutecia_a_importer.json")

AUXERRE = "lieu:auxerre"
LUTECIA = "lieu:lutecia"


# ── Matières neuves (feuilles) ───────────────────────────────────────────────────
# (slug, nom, icon, sous_categorie, rareté, poids, valeur_min, valeur_max, description)
MATIERES = [
	("Cassis", "Cassis", "🫐", "baie", "commun", 0.5, 8, 22,
	 "Petites baies noires et luisantes, cueillies en grappes au bord des vignes. Crues, elles "
	 "font grimacer ; il faut du sucre et de la patience pour en tirer quelque chose."),
]


# ── Produits et recettes ─────────────────────────────────────────────────────────
# slug → (nom, icon, rareté, catégorie, sous_catégorie, poids, effets, métier, portée,
#         intrants [(item_id, qté)], quantité produite, description)
PRODUITS = {
	# — Auxerre —
	"Vin_de_Chablis": (
		"Vin de Chablis", "🥂", "peu_commun", "consommable", "boisson", 1.0,
		{"pm": 14, "duree": 6, "buffs": {"Int": 3}}, CAVE, AUXERRE,
		[("item:Raisin", 4)], 2,
		"Vin blanc sec et vif des coteaux de l'Yonne, qui sent la pierre à fusil. Les gens "
		"d'Auxerre le boivent frais, et jurent qu'il éclaircit les idées."),
	"Vin_d_Irancy": (
		"Vin d'Irancy", "🍷", "peu_commun", "consommable", "boisson", 1.0,
		{"pv": 10, "duree": 6, "buffs": {"F": 3}}, CAVE, AUXERRE,
		[("item:Raisin", 4)], 2,
		"Rouge léger d'un village de vignerons blotti dans un creux de l'Yonne, entre les "
		"cerisiers. Il se boit jeune, avant que les monstres n'aient le temps de le voler."),
	"Marc_de_Bourgogne": (
		"Marc de Bourgogne", "🥃", "rare", "consommable", "boisson", 0.7,
		{"pm": 18, "duree": 8, "buffs": {"Vol": 4}}, CAVE, AUXERRE,
		[("item:Raisin", 3), ("item:Eau_de_vie", 1)], 2,
		"Ce qui reste au fond du pressoir, peaux et pépins, repassé au feu de l'alambic. Les "
		"convoyeurs de cristaux en emportent une flasque pour la route de Lutecia."),
	"Creme_de_cassis": (
		"Crème de cassis", "🫐", "peu_commun", "consommable", "boisson", 0.6,
		{"pm": 12, "duree": 6, "buffs": {"Cha": 3}}, CAVE, AUXERRE,
		[("item:Cassis", 3), ("item:Eau_de_vie", 1), ("item:Sucre", 1)], 2,
		"Liqueur épaisse et pourpre, de baies de cassis macérées dans l'eau-de-vie et sucrées "
		"sans compter. Une cuillerée dans un verre de blanc, et la conversation se délie."),

	# — Lutèce —
	"Hypocras": (
		"Hypocras", "🍷", "peu_commun", "consommable", "boisson", 1.0,
		{"pm": 14, "duree": 6, "buffs": {"Cha": 3}}, CAVE, LUTECIA,
		[("item:Vin_de_pays", 2), ("item:Miel", 1), ("item:epices_douces", 1)], 2,
		"Vin miellé et épicé, filtré à travers une chausse de drap. On le sert aux banquets de "
		"la capitale, où personne ne s'accorde sur le savant qui lui aurait donné son nom."),
	"Vin_de_Montmartre": (
		"Vin de Montmartre", "🍇", "commun", "consommable", "boisson", 1.0,
		{"pv": 8, "duree": 6, "buffs": {"Vol": 2}}, CAVE, LUTECIA,
		[("item:Raisin", 4)], 2,
		"Petit vin des vignes qui grimpent la butte jusqu'aux casernes des paladins. Il est "
		"aigrelet, mais les paladins le bénissent, dit-on, avant chaque garde."),
	"Cervoise": (
		"Cervoise", "🍺", "commun", "consommable", "boisson", 1.0,
		{"pv": 10, "duree": 6, "buffs": {"R": 2}}, CAVE, LUTECIA,
		[("item:grain_d_orge", 3), ("item:Eau_de_source", 1)], 3,
		"Bière d'orge trouble et sans houblon, brassée dans les caves des Halles. Elle nourrit "
		"presque autant qu'elle désaltère, et les porteurs n'en boivent pas d'autre."),
	"Vinaigre_de_Lutece": (
		"Vinaigre de Lutèce", "🫙", "commun", "composant", "condiment", 0.8,
		None, CAVE, LUTECIA,
		[("item:Vin_de_pays", 2)], 3,
		"Vinaigre des vinaigriers de la capitale, qui crient leur marchandise au petit matin en "
		"poussant leur tonneau sur une brouette. Piquant, clair, il relève tout."),
}


# `valeur` EXPLICITE sur le condiment (même raison que dans le lot Chartres/Rhemi : un vinaigre
# ne doit pas coûter plus cher que le vin dont il est tiré).
VALEURS = {
	"Vinaigre_de_Lutece": (12, 30),
}


def produit_docs(slug: str) -> tuple:
	"""(item, recette) d'un produit de PRODUITS — même forme que le lot Chartres/Rhemi."""
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


def construire_lot() -> list:
	"""Tous les docs du lot, dans un ordre stable (matières, produits)."""
	lot = [matiere_doc(*m) for m in MATIERES]
	for slug in PRODUITS:
		lot.extend(produit_docs(slug))
	return lot


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

	if "pnj:marchand_" + CAVE not in index:
		erreurs.append("pnj:marchand_%s absent du dump — importer d'abord le lot Chartres/Rhemi" % CAVE)

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
	recettes_monde = [r for r in docs if isinstance(r, dict) and r.get("type") == "recette"]
	producteurs = {}
	for r in recettes_monde:
		producteurs.setdefault(marche.objet_final_item_id(r.get("objet_final", "")), []).append(r)
	for (slug, *_r) in MATIERES:
		if "item:" + slug in producteurs:
			erreurs.append("item:%s : déjà produit par une recette — pas une feuille" % slug)
	for slug, spec in PRODUITS.items():
		for cle, _q in spec[9]:
			if cle not in index and cle not in ids_lot:
				erreurs.append("%s : intrant %s sans doc" % (slug, cle))
			# Intermédiaire produit en base : même métier, portée qui couvre la consommatrice.
			amont = [r for r in producteurs.get(cle, []) if r.get("lieu_categorie") == spec[7]]
			if producteurs.get(cle) and not any(
					_portee_couvre(marche, r.get("lieu_portee"), spec[8], index) for r in amont):
				erreurs.append("%s : %s n'est produit par aucune %s couvrant %s — fausse feuille"
							   % (slug, cle, spec[7], spec[8]))

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
			avis.append("%s : aucune cave sous %s — à poser (dev/gen_spec_caves_negoces.py)"
						% (recette_id, portee))
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

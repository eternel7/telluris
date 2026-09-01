#!/usr/bin/env python
# dev/gen_stock_cible_ateliers.py
# Pose un `stock_cible` BAS sur les INTERMÉDIAIRES que chaque atelier fabrique pour lui-même.
#
# CE QU'IL CORRIGE. Un atelier peut chaîner ses recettes : produire un `manche`, puis le
# consommer pour monter une épée (« pool unifié » de `marche._executer_production_batch`).
# Mais un produit fini part TOUJOURS au rayon (`stock_vente`), jamais dans `stock_matieres`, et
# le rayon n'est utilisable comme matière qu'AU-DESSUS de son `stock_cible`. Aucun des 90 docs
# `lieu:*` n'en déclare : c'est donc `STOCK_CIBLE_DEFAUT` qui gouvernait tout.
#
# ⚠️ Ce défaut valait **100** et a été ramené à **25** (cf. le commentaire de
# `models/character_stats.STOCK_CIBLE_DEFAUT`, qui porte la mesure) — l'essentiel du mal est
# donc déjà traité à la source. La base garde la trace de l'ancien régime : `item:manche` à
# 101/102/103/104 chez quatre armuriers, `item:Papier` à 208, `item:pigment` à 186, et surtout
# `item:Table_d_harmonie` **à 99** — ce luthier-là était à UNE unité de pouvoir monter un luth.
#
# CE QUE CE SCRIPT AJOUTE ENCORE. `stock_cible` est défini PAR LIEU
# (`{item|sous_categorie|categorie: cible}`) — le levier existe depuis toujours, personne ne
# s'en était servi. On descend les SEULS intermédiaires maison **sous** le défaut : un
# intermédiaire est un EN-COURS, pas de la marchandise, et l'atelier n'a aucune raison d'en
# exposer autant qu'un produit fini. Mesuré à défaut 25, sur 120 visites simulées :
#
#   atelier → pièce chaînée      défaut 100    défaut 25 seul   défaut 25 + ce fichier
#   boyauderie → outre           visite 35     visite 10        visite 6
#   salaison  → jambon           visite 34     visite  9        visite 5
#   lutherie  → Luth             visite  9     visite  3        visite 2
#   armurerie → total chaîné      1 068 pièces  1 111 pièces     1 135 pièces
#
# Le gain est donc réel mais SECOND : ce fichier est un raffinement, plus un correctif. Rien
# d'autre n'est touché — produits finis et matières gardent la cible par défaut.
#
# ⚠️ Effets de bord ASSUMÉS, tous voulus — `stock_cible` gouverne trois choses à la fois :
#   1. le chaînage (`_vente_surplus_entries`) — l'objet de ce script ;
#   2. le PRIX (`facteur_stock`) : un intermédiaire au-dessus de sa cible devient moins cher,
#      jusqu'à −`PRIX_AMPLITUDE_STOCK`. C'est correct : un atelier qui déborde de manches les
#      brade. L'effet est PETIT — sur un panier fixe des 512 lignes du dump, passer la cible
#      de 100 à 25 ne bouge le prix total que de −3 % ;
#   3. l'écoulement PNJ (`ecouler_produits_pnj`), qui n'achète lui aussi que le surplus : les
#      manches en trop commencent enfin à se vendre tout seuls.
#
# ⚠️ La cible doit rester AU-DESSUS de la plus grosse quantité exigée par une recette chaînée
# (la Harpe demande 8 `cordes_d_instrument`) — sinon l'atelier oscillerait autour de la cible
# sans jamais réunir de quoi produire. `CIBLE` est vérifiée contre le graphe et le script
# SORT EN ERREUR si elle est trop basse.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc. On RELIT donc les
# docs depuis le dump et on n'y injecte que `stock_cible` : régénérer est idempotent, et une
# retouche faite à la main en base survit à la régénération.
#
# ⚠️ Les docs `lieu:*` de BOUTIQUE n'ont pas de `cells` (seules les cités en portent) : les
# réémettre en entier reste bon marché. Le script REFUSE tout lieu porteur de `cells`, pour ne
# jamais réémettre une carte de ~30 Ko par mégarde.
#
# Usage :
#   python dev/gen_stock_cible_ateliers.py            # tous les ateliers concernés
#   python dev/gen_stock_cible_ateliers.py boyauderie salaison   # seulement ces catégories
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/stock_cible_ateliers_a_importer.json

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.marche import recette_matieres, objet_final_item_id   # noqa: E402

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260831-122931.json"

# Recettes pas encore importées, à prendre en compte comme si elles l'étaient : sans elles, un
# atelier dont le chaînage arrive avec un fichier d'import ne serait pas vu par ce script.
SRC_EXTRA = ["jsons/boyauderie_salaison_a_importer.json"]

# Exemplaires gardés en vitrine pour un intermédiaire maison. Au-dessus, l'atelier travaille
# avec. ⚠️ À tenir SOUS `STOCK_CIBLE_DEFAUT` (25), sinon ce fichier n'ajoute rien à la règle
# générale. Doit dépasser la plus grosse quantité exigée par une recette chaînée — la Harpe
# demande 8 `cordes_d_instrument` — sinon l'atelier oscillerait autour de la cible sans jamais
# réunir de quoi produire (contrôlé plus bas, le script sort en erreur).
CIBLE = 12

# Surcharge PAR CATÉGORIE de lieu, quand la cible générale est encore trop haute pour que
# l'atelier chaîne. ⚠️ La BOYAUDERIE est le seul métier du jeu SANS aucune feuille d'appro
# (`marche.appro_leaves_categorie("boyauderie")` → `[]`) : rien ne lui est livré, tout vient
# du sac du joueur. Ses en-cours arrivent donc à l'unité, pas par charrettes — à 12 en
# vitrine, ses 7 boyaux pour saucisses n'ouvraient aucun surplus et la recette d'andouille
# restait inapplicable alors que la matière était là, sous les yeux du joueur. À 2, deux
# passes suffisent à amorcer la chaîne. Le contrôle « la cible couvre la plus grosse quantité
# exigée » (plus bas) s'applique catégorie par catégorie : ici l'outre demande 2 baudruches,
# donc 2 est exactement le plancher admissible.
CIBLE_PAR_CATEGORIE: dict[str, int] = {
	"boyauderie": 2,
}

SORTIE = "jsons/stock_cible_ateliers_a_importer.json"


def cible_de(categorie: str) -> int:
	"""Cible de vitrine des intermédiaires de cette catégorie de lieu. SOURCE UNIQUE — lue par
	le contrôle de plancher ET par l'écriture, un écart entre les deux laisserait passer une
	cible trop basse pour la recette qu'elle doit servir."""
	return int(CIBLE_PAR_CATEGORIE.get(categorie, CIBLE))


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def intermediaires_par_categorie(docs: list) -> dict:
	"""{lieu_categorie: {item_id d'un produit que SES PROPRES recettes reconsomment}}.

	Entièrement DÉRIVÉ du graphe de recettes : rien n'est listé à la main, une recette chaînée
	ajoutée demain sera prise en compte sans toucher à ce script. On indexe par **item_id** —
	la seule forme commune aux deux façons de désigner une matière (sous-catégorie ou item-ref)
	et la seule clé que `stock_cible.item` sait lire."""
	par_id = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	recettes = [d for d in docs if isinstance(d, dict) and d.get("type") == "recette"]

	produits: dict = {}
	for r in recettes:
		cat = r.get("lieu_categorie")
		if cat:
			produits.setdefault(cat, set()).add(objet_final_item_id(r.get("objet_final", "")))

	besoins: dict = {}
	for r in recettes:
		cat = r.get("lieu_categorie")
		if not cat:
			continue
		for cle, qte in recette_matieres(r):
			if not cle:
				continue
			iid = cle if str(cle).startswith("item:") else objet_final_item_id(cle)
			if iid in produits.get(cat, set()):
				besoins.setdefault(cat, {})
				# On garde la plus grosse quantité exigée : c'est elle que la cible doit couvrir.
				besoins[cat][iid] = max(besoins[cat].get(iid, 0), int(qte))

	# Contrôle de la cible AVANT d'écrire quoi que ce soit, CATÉGORIE PAR CATÉGORIE (une
	# surcharge de CIBLE_PAR_CATEGORIE doit être vérifiée comme la cible générale).
	trop = [(cat, iid, q) for cat, m in besoins.items() for iid, q in m.items()
			if q > cible_de(cat)]
	if trop:
		lignes = "\n".join(f"   {cat} : {iid} exige {q} > cible {cible_de(cat)}"
						   for cat, iid, q in trop)
		sys.exit(f"ERREUR : cible sous la quantite exigee par une recette :\n{lignes}")

	# Un intermédiaire dont le doc item n'existe pas serait une cible posée sur du vide.
	inconnus = [iid for m in besoins.values() for iid in m if iid not in par_id]
	if inconnus:
		sys.exit(f"ERREUR : intermediaires sans doc item : {sorted(set(inconnus))}")

	return {cat: set(m) for cat, m in besoins.items()}


def main() -> None:
	filtres = set(sys.argv[1:])
	docs = charger(SRC_DUMP)
	for extra in SRC_EXTRA:
		chemin = os.path.join(RACINE, extra)
		if os.path.exists(chemin):
			docs = docs + charger(extra)

	interm = intermediaires_par_categorie(docs)
	if filtres:
		inconnues = filtres - set(interm)
		if inconnues:
			sys.exit(f"ERREUR : aucune recette chainee pour {sorted(inconnues)}")
		interm = {c: v for c, v in interm.items() if c in filtres}

	sortie, inchanges = [], 0
	for doc in docs:
		if not isinstance(doc, dict) or doc.get("type") != "lieu":
			continue
		cibles = interm.get(doc.get("categorie"))
		if not cibles:
			continue
		if doc.get("cells"):
			print(f"   ignore (porte une grille) : {doc['_id']}")
			continue
		# Fusion, jamais écrasement : un `stock_cible` déjà posé à la main est conservé, et
		# seules les clés d'intermédiaires sont ajoutées ou mises à jour.
		bloc = dict(doc.get("stock_cible") or {})
		par_item = dict(bloc.get("item") or {})
		avant = dict(par_item)
		cible = cible_de(doc.get("categorie"))
		for iid in sorted(cibles):
			par_item[iid] = cible
		if par_item == avant:
			inchanges += 1
		bloc["item"] = par_item
		doc["stock_cible"] = bloc
		sortie.append(doc)

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")

	print(f"ecrit {SORTIE}")
	print(f"   {len(sortie)} lieu(x), cible par defaut {CIBLE} "
		  f"({inchanges} deja a jour - reimport sans effet)")
	for cat in sorted(interm):
		n = sum(1 for d in sortie if d.get("categorie") == cat)
		noms = ", ".join(sorted(i.split(":", 1)[1] for i in interm[cat]))
		marque = " *" if cat in CIBLE_PAR_CATEGORIE else "  "
		print(f"   {cat:24} {n:>2} lieu(x)   cible {cible_de(cat):>2}{marque} {noms}")
	if CIBLE_PAR_CATEGORIE:
		print("   * cible surchargee (CIBLE_PAR_CATEGORIE)")


if __name__ == "__main__":
	main()

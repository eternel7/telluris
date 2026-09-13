"""Donne au scriptorium une encre qu'il sait fabriquer seul : pigment → encre.

Les livres de contenu (sort, recette, carte — utils/scriptorium.py) coûtent papier + encre
et ne puisent que dans le SURPLUS du rayon (au-dessus du stock cible). Or la seule recette
d'encre du scriptorium consomme du `sang`, qu'aucun approvisionnement ne livre (la boucherie
le produit, ce n'est donc pas une « feuille ») : l'encre ne dépassait jamais sa cible et
aucun livre ne sortait. Le pigment, lui, naît du `residu_spectral` auto-approvisionné.

    python dev/gen_encre_scriptorium.py [chemin/vers/telluris-dump-*.json]

Sortie :
    jsons/encre_scriptorium_a_importer.json   (carte d'import de /admin)

Lit le dump committé (source unique, cf. CLAUDE.md §11) et n'émet la recette que si le
scriptorium ne sait pas déjà faire de l'encre à partir du pigment (même id, ou même produit
à partir des mêmes matières sous un autre id). Relancer après l'import ne produit rien.

⚠️ Conséquence côté marché, à assumer avant d'importer : le coût de revient d'un produit est
le MAX sur ses recettes (`marche.cout_production_cuivre`) — l'encre passe de 12-36 cu à
30-90 cu. Le dosage 1 pigment → 2 encres est le moins cher des dosages essayés, et reprend
celui des recettes voisines (sang → encre ×2, résidu spectral → pigment ×2).
⚠️ `item:pigment` a une sous_categorie VIDE : l'intrant est donc référencé par son id
(`item`), comme dans les recettes de grimoires, jamais par sous-catégorie.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")

RECETTE = {
	"_id": "recette:scriptorium_encre_pigment",
	"type": "recette",
	"lieu_categorie": "scriptorium",
	"objet_final": "encre",
	"quantite_produite": 2,
	"matieres_premieres": [{"item": "item:pigment", "quantite": 1}],
}

# Même table que `marche._OBJET_FINAL_ITEM_ID` pour les deux produits en jeu : `encre` et
# `Encre` désignent le même item, une recette déjà écrite sous l'autre graphie compte.
_OBJET_FINAL_ITEM_ID = {"encre": "item:Encre"}


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


def recette_matieres(r):
	"""Réplique de `marche.recette_matieres` (repli mono-entrée compris) : script sans dépendance."""
	mp = r.get("matieres_premieres")
	if isinstance(mp, list) and mp:
		out = [
			(e.get("item") or e.get("sous_categorie"), max(1, int(e.get("quantite", 1) or 1)))
			for e in mp if isinstance(e, dict) and (e.get("item") or e.get("sous_categorie"))
		]
		if out:
			return out
	sc = r.get("matiere_premiere_sous_categorie")
	return [(sc, max(1, int(r.get("quantite_matiere", 1) or 1)))] if sc else []


def signature(r):
	"""Métier + produit + clés matières (sans les quantités : un autre dosage du même geste
	est déjà « savoir faire de l'encre au pigment », on ne l'empile pas)."""
	slug = str(r.get("objet_final") or "")
	return (
		r.get("lieu_categorie"),
		_OBJET_FINAL_ITEM_ID.get(slug, "item:" + slug),
		tuple(sorted(c for c, _q in recette_matieres(r))),
	)


def main():
	dump = charger_dump(sys.argv[1] if len(sys.argv) > 1 else None)
	docs = dump["docs"]
	ids = {d["_id"] for d in docs}
	deja = {signature(d) for d in docs if d.get("type") == "recette"}

	manquants = [d for d in ("item:pigment", "item:Encre") if d not in ids]
	if manquants:
		raise SystemExit("Items absents du dump : %s — rien n'est écrit." % ", ".join(manquants))

	sortie = []
	if RECETTE["_id"] in ids:
		etat = "déjà en base (même id) — rien à importer"
	elif signature(RECETTE) in deja:
		etat = "le scriptorium sait déjà faire de l'encre au pigment — rien à importer"
	else:
		sortie.append(RECETTE)
		etat = "à importer"

	chemin = os.path.join(DOSSIER_JSONS, "encre_scriptorium_a_importer.json")
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")

	# Console Windows en cp1252 : sans cela, un accent fait planter le script APRÈS l'écriture.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	print("%s : pigment x1 -> encre x2 (scriptorium) — %s" % (RECETTE["_id"], etat))
	print("→ %s" % chemin)


if __name__ == "__main__":
	main()

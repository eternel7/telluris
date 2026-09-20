"""Retire la plume d'oie des recettes de grimoire : c'est elle qui bloquait le rayon.

`item:Plume_d_oie` n'est PAS une feuille d'approvisionnement — une recette de scriptorium
la produit (`objet_final: plume_a_ecrire`, que `marche._OBJET_FINAL_ITEM_ID` mappe sur
`item:Plume_d_oie`) —, donc `approvisionner` ne la livre jamais. Sa seule source est la clé
`plumes` du boucher, qui n'est pas une feuille non plus : elle ne circule que par le pool de
flux de la cité, où l'armurerie, la plumasserie, le fletcher et l'empenneur puisent avant.
Au dump du 20/09 les deux scriptoriums d'Auxerre avaient 0 plume en réserve et 1 et 3 au
rayon pour une cible de 12 (donc 0 surplus consommable) : AUCUNE recette de grimoire n'était
applicable, pendant que l'amont auto-approvisionné (chiffon, résidu spectral) empilait 794
encres, 403 pigments et 395 papiers. Cinq grimoires produits dans le monde en six jours.

Les livres de contenu (traité, recueil, carte — `scriptorium._recette_virtuelle`) ne coûtent
que papier + encre : c'est pour cela qu'eux sortaient. Les grimoires s'alignent dessus.

    python dev/gen_grimoires_sans_plume.py [chemin/vers/telluris-dump-*.json]

Sortie :
    jsons/grimoires_sans_plume_a_importer.json   (carte d'import de /admin)

Lit le dump committé (source unique, cf. CLAUDE.md §11) et ne réémet QUE les recettes qui
portent encore la plume, doc complet sans `_rev` (l'import est un PUT complet, `_rev` est
réattaché depuis la base). Relancer après l'import n'écrit aucun doc.

⚠️ `utils/grimoires.matieres_grimoire` relit la signature majoritaire EN BASE : une fois ce
lot importé, `dev/gen_grimoires.py` écrit les recettes des sorts suivants sans plume, sans
qu'une ligne de code change.
⚠️ Conséquences à assumer avant d'importer :
  · `item:Plume_d_oie` sort des `besoins_categorie("scriptorium")` — le scriptorium ne
    l'achète plus comme MATIÈRE. Il continue de la racheter et de la vendre : il la produit
    (`lieu_produit`), et c'est cette branche-là qui décide du rachat.
  · Le coût de revient d'un grimoire perd une plume ; il ne sert qu'à borner la bande de
    rachat (`params_vente_lieu`), la fourchette de vente restant celle du champ `valeur`.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "grimoires_sans_plume_a_importer.json")

PLUME = "item:Plume_d_oie"


def charger_dump(chemin=None):
	if chemin:
		print("source : %s" % chemin)
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez le chemin en argument.")
	print("source : jsons/%s" % dumps[-1])
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def est_recette_de_grimoire(d):
	"""Même prédicat que `grimoires.matieres_grimoire` : le produit, jamais l'`_id`."""
	return d.get("type") == "recette" and str(d.get("objet_final") or "").startswith("grimoire_")


def main():
	# Console Windows en cp1252 : sans cela, le premier accent fait planter le script.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	dump = charger_dump(sys.argv[1] if len(sys.argv) > 1 else None)
	recettes = [d for d in dump["docs"]
				if isinstance(d, dict) and d.get("_id") and est_recette_de_grimoire(d)]
	print("%d recette(s) de grimoire en base" % len(recettes))

	docs, erreurs, deja = [], [], 0
	for r in recettes:
		mp = r.get("matieres_premieres")
		if not isinstance(mp, list) or not mp:
			# Repli mono-entrée (`matiere_premiere_sous_categorie`) : aucune recette de
			# grimoire ne l'utilise, et une plume ne s'y référence pas par sous-catégorie.
			# On le SIGNALE au lieu de deviner.
			erreurs.append("%s n'a pas de `matieres_premieres` en liste — laissée telle quelle"
						   % r["_id"])
			continue
		garde = [e for e in mp if not (isinstance(e, dict) and e.get("item") == PLUME)]
		if len(garde) == len(mp):
			deja += 1
			continue
		if not garde:
			# Une recette sans matière n'entre pas dans `_executer_production_batch` : le
			# grimoire ne sortirait JAMAIS plus. On refuse plutôt que de le stériliser.
			erreurs.append("%s n'aurait plus aucune matière — non réémise" % r["_id"])
			continue
		docs.append({k: v for k, v in r.items() if k != "_rev"} | {"matieres_premieres": garde})

	if deja:
		print("   %d recette(s) déjà sans plume — non réémises (idempotent)" % deja)
	if erreurs:
		print("\n⚠️ %d recette(s) laissée(s) de côté :" % len(erreurs))
		for e in erreurs:
			print("   " + e)

	if not docs:
		print("\nrien à corriger : aucune recette de grimoire ne porte la plume. Aucun fichier écrit.")
		return

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("\nécrit jsons/%s : %d recette(s) allégée(s) de la plume d'oie"
		  % (os.path.basename(SORTIE), len(docs)))
	print("→ %s" % SORTIE)


if __name__ == "__main__":
	main()

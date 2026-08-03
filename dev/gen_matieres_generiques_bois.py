"""Donne un doc générique aux quatre calibres de bois consommés par les recettes.

    python dev/gen_matieres_generiques_bois.py [chemin/vers/telluris-dump-*.json]

Sortie :
    jsons/matieres_generiques_bois_a_importer.json

⚠️ POURQUOI. Une clé matière **sous-catégorie** est valorisée via
`marche.matiere_item_id` → `item:<sous_categorie>`. Or `branche`, `petit_rondin`,
`rondin` et `gros_rondin` n'existent qu'en 11 à 15 exemplaires PAR ESSENCE
(`item:Branche_de_Chene`…) : le doc générique manque, `get_doc` rend `None`, et
`item_sale_price_cuivre` retombe sur le plancher de **1 cu**. Sans aucune erreur ni
aucun symptôme visible — juste un prix faux, propagé à tout ce qui en dérive
(manche, hampe, et par elles la moitié de l'armurerie) par la marge de
transformation. Les deux autres trous de la même famille, `chiffon` et
`reactif_brut`, ont bien un doc générique sous un id capitalisé : ils se corrigent
par une entrée dans `marche._OBJET_FINAL_ITEM_ID`, pas par un doc de plus.

Ces docs sont des **unités de compte marchandes**, pas du butin : le poids retenu
est la MÉDIANE des poids minimaux des essences (c'est le minimum que lit
`item_ref_weight` sur une référence nue). ⚠️ Aucun tag `essence_*` et aucun tag
`a_couper` : `bois._trouver_item` filtre sur l'essence, donc ces docs restent
**invisibles** pour la découpe, pour `cible_coupe` et pour `pieces_legeres` — ils ne
peuvent ni être coupés, ni devenir la cible d'une coupe, ni entrer dans une quête de
collecte. Ils ne servent qu'à donner un prix à la matière que le marchand
auto-approvisionne.

Idempotent : lit le dump committé et n'émet que ce qui manque.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")

# sous_categorie → (nom, icon, description)
CALIBRES = [
	("branche", "Branche", "🌿",
	 "Branche de bois tout-venant, essence indifférente : la mesure du marchand."),
	("petit_rondin", "Petit rondin", "🪵",
	 "Petit rondin de bois tout-venant, essence indifférente : la mesure du marchand."),
	("rondin", "Rondin", "🪵",
	 "Rondin de bois tout-venant, essence indifférente : la mesure du marchand."),
	("gros_rondin", "Gros rondin", "🪵",
	 "Gros rondin de bois tout-venant, essence indifférente : la mesure du marchand."),
]


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


def poids_min(item):
	"""Le poids que lit `item_ref_weight` sur une référence nue : le minimum d'un
	`[min, max]`, le nombre lui-même sinon."""
	p = item.get("poids")
	if isinstance(p, (list, tuple)) and p:
		return float(p[0])
	return float(p or 0)


def mediane(valeurs):
	v = sorted(valeurs)
	n = len(v)
	if not n:
		return 0.0
	return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def main():
	dump = charger_dump(sys.argv[1] if len(sys.argv) > 1 else None)
	docs = dump["docs"]
	ids_pris = {d["_id"] for d in docs}

	sortie, rapport, ignores = [], [], []
	for sous_cat, nom, icon, description in CALIBRES:
		item_id = "item:" + sous_cat
		essences = [
			d for d in docs
			if d.get("type") == "item" and d.get("sous_categorie") == sous_cat
			and d.get("_id") != item_id
		]
		if not essences:
			raise SystemExit("Aucune essence en base pour « %s » — dump inattendu." % sous_cat)
		poids = mediane([poids_min(d) for d in essences])
		poids = round(poids, 2) if poids < 10 else round(poids)

		if item_id in ids_pris:
			ignores.append(item_id)
			continue
		ids_pris.add(item_id)
		sortie.append({
			"_id": item_id,
			"type": "item",
			"nom": nom,
			"icon": icon,
			"description": description,
			"rarete": "commun",
			"categorie": "composant",
			"sous_categorie": sous_cat,
			"slots": [],
			# ⚠️ Ni `essence_*` ni `a_couper` : ce doc doit rester hors du système de découpe.
			"tags": ["bois"],
			"poids": poids,
		})
		rapport.append("  %-14s %-16s poids %-7s (médiane des minima de %d essences)"
					   % (sous_cat, nom, poids, len(essences)))

	chemin = os.path.join(DOSSIER_JSONS, "matieres_generiques_bois_a_importer.json")
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")

	# La console Windows est en cp1252 : sans cela, un accent fait planter le script
	# APRÈS l'écriture du fichier — panne trompeuse.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	print("Docs génériques créés : %d" % len(sortie))
	print()
	for ligne in rapport:
		print(ligne)
	if ignores:
		print("Déjà en base, non ré-émis : %s" % ", ".join(ignores))
	print()
	print("→ %s" % chemin)
	print()
	print("Rappel : `chiffon` et `reactif_brut` sont corrigés dans le CODE")
	print("         (marche._OBJET_FINAL_ITEM_ID), pas par un doc.")


if __name__ == "__main__":
	main()

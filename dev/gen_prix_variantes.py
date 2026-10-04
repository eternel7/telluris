"""Recalcule la `valeur` des variantes sur mesure déjà en base, et aligne la rareté des
matières qui confèrent plus d'un palier au-dessus de la leur — UN SEUL fichier à importer.

Pourquoi : `fabrication.assurer_variante` ne retouche JAMAIS une variante existante, et les
variantes créées avant le correctif portent une `valeur` figée sur le DEVIS de leur premier
client (relation, stock du jour, matières apportées comptées 0, facteur de matière appliqué
aussi à la matière). Résultat au dump du 02/10 : 30 variantes sur 35 se revendaient plus
cher qu'elles ne coûtent à commander (jusqu'à ×18), deux à −96 %. Cf. dev/audit_economy.py §7.

Deux corrections, dans cet ordre (la seconde lit la première) :
  1. **rareté des matières** — `fabrication.rarete_minimale_matiere` : une matière ne confère
     qu'un palier de plus que sa propre rareté (`RARETE_ECART_MAX`). Seul le champ `rarete`
     change ; sans `valeur` explicite, le coût d'une matière en dépend, d'où l'ordre ;
  2. **valeur des variantes** — la règle même des commandes neuves :
     `commande.prix_variante` (coûts de revient + plafond = plancher de commande) passé à
     `fabrication.valeur_variante` avec le facteur des matières. Seul `valeur` change.

    python dev/gen_prix_variantes.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/prix_variantes_a_importer.json   (carte d'import de /admin)

Le fichier ne porte que le DIFF : chaque doc est repris ENTIER du dump (l'import est un PUT
complet, CLAUDE.md §11) avec le seul champ corrigé ; `_rev` est retiré (l'import le réattache).
Base à jour ⇒ fichier vide. Le moteur est celui du jeu, branché sur le dump comme
dev/audit_economy.py.
"""

import argparse
import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "prix_variantes_a_importer.json")

sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


def est_variante(doc: dict) -> bool:
	bloc = doc.get("fabrication")
	return doc.get("type") == "item" and isinstance(bloc, dict) and bool(bloc.get("base_item"))


def corriger_raretes(docs: list) -> list:
	"""Docs matière corrigés (copies, `_rev` retiré). Mute les docs EN PLACE — ce sont les
	objets que sert le moteur branché — pour que le calcul des variantes qui suit lise la
	rareté corrigée (l'appelant vide ensuite les caches de prix)."""
	from utils import fabrication
	sortie = []
	for doc in docs:
		if doc.get("type") != "item" or est_variante(doc):
			continue
		cible = fabrication.rarete_minimale_matiere(doc)
		if cible is None:
			continue
		print("  rareté  %-32s %s → %s" % (doc["_id"], doc.get("rarete"), cible))
		doc["rarete"] = cible
		sortie.append(_sans_rev(doc))
	return sortie


def recalculer_variantes(docs: list) -> tuple[list, list]:
	"""`(docs corrigés, erreurs)`. À appeler APRÈS `audit_economy.brancher_moteur`."""
	from utils import commande, fabrication
	index = {d["_id"]: d for d in docs}
	sortie, erreurs = [], []
	for doc in sorted((d for d in docs if est_variante(d)), key=lambda d: d["_id"]):
		bloc = doc["fabrication"]
		base = index.get(bloc["base_item"])
		if base is None:
			erreurs.append("%s : objet de base %s absent" % (doc["_id"], bloc["base_item"]))
			continue
		matieres = []
		for m in bloc.get("matieres") or []:
			mdoc = index.get(m.get("item"))
			if mdoc is None:
				erreurs.append("%s : matière %s absente" % (doc["_id"], m.get("item")))
				break
			matieres.append((mdoc, m.get("quantite", 1)))
		else:
			facteurs = fabrication.appliquer_modificateurs(base, matieres)["_facteurs"]
			valeur = fabrication.valeur_variante(
				facteur_valeur=facteurs.get("valeur", 1.0),
				**commande.prix_variante(base, matieres))
			if valeur != doc.get("valeur"):
				print("  valeur  %-44s %s → %s" % (doc["_id"], _cu(doc.get("valeur")), _cu(valeur)))
				sortie.append(dict(_sans_rev(doc), valeur=valeur))
	return sortie, erreurs


def _cu(valeur) -> str:
	if not isinstance(valeur, list):
		return str(valeur)
	return "[" + ", ".join(str(v.get("cu", v)) if isinstance(v, dict) else str(v) for v in valeur) + "]"


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	args = ap.parse_args()
	chemin = args.dump or dernier_dump()
	print("source : %s" % os.path.relpath(chemin, RACINE))

	import audit_economy
	docs, _meta = audit_economy.charger_dump(chemin)
	docs = [copy.deepcopy(d) for d in docs if isinstance(d, dict) and d.get("_id")]

	# Moteur d'abord : `rarete_minimale_matiere` lit le MULT_RARETE du dump (variable de monde).
	_cs, _characters, marche = audit_economy.brancher_moteur(docs)
	raretes = corriger_raretes(docs)
	marche.reset_prix_cache()                    # le coût d'une matière peut dépendre de sa rareté
	variantes, erreurs = recalculer_variantes(docs)

	if erreurs:
		print("\n⚠ RIEN N'EST ÉCRIT :")
		for e in erreurs:
			print("  · " + e)
		return 1
	lot = raretes + variantes
	ids = [d["_id"] for d in lot]
	assert len(ids) == len(set(ids)), "un _id en double dans le lot"
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(lot, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("\n%d matière(s), %d variante(s) → %s" % (len(raretes), len(variantes),
												   os.path.relpath(SORTIE, RACINE)))
	return 0


if __name__ == "__main__":
	sys.exit(main())

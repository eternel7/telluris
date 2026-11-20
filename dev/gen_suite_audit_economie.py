"""Suite de l'audit économique du 20/11 — UN SEUL fichier à importer, trois corrections :

  1. **Appro de base des morceaux de bête** (§2/§5 : la filière animale bloquait 335 recettes
     sans aventurier). Les morceaux (cuir brut, os, tendons…) sont produits par les tables de
     dépeçage, donc ne sont PAS des « feuilles » : `APPRO_DEBIT` seul n'y peut rien. On les
     DÉCLARE dans `APPRO_EXTRA` pour chaque catégorie d'atelier dont une recette les consomme
     (index `besoins` du moteur, relu au lancement), à un débit FAIBLE (`DEBIT_MORCEAUX`) : le
     monde tourne au ralenti, l'aventurier qui vend ses dépouilles accélère.
     ⚠️ Jamais à la boucherie elle-même : une matière déclarée y devient un besoin du lieu, et
     `_deverser_surplus_flux` cesserait de verser au flux de cité les morceaux qu'un joueur y
     vend.
  2. **Appro par item des trois herbes indispensables** (§5) : `APPRO_DEBIT` posé SOUS L'ID
     (`item:Herbes_medicinales`…), `herbe`/`seve` restent à 0 pour toutes les autres plantes.
  3. **Bois sans source** (§6) : essences ajoutées aux `defauts_ressources` des zones de
     biome qui leur conviennent (`ESSENCES_PAR_ZONE`) ; tronc, rondins et branches suivent
     par la coupe. Les palmes (branche d'un palmier, chaîne réduite) se ramassent directement.
  4. **Prix du sur-mesure** (§7) : `dev/gen_prix_variantes.py` (raretés puis valeurs).

    python dev/gen_suite_audit_economie.py [--dump jsons/telluris-dump-*.json]

Sortie : jsons/suite_audit_economie_a_importer.json

Docs repris ENTIERS du dump (PUT complet, CLAUDE.md §11), seul le champ visé change, `_rev`
retiré. Idempotent : base à jour ⇒ doc non émis.
"""

import argparse
import copy
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import gen_prix_variantes as gpv  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "suite_audit_economie_a_importer.json")

# Morceaux de bête (racines du §5 de l'audit) — clés de recette, courtes ou item-ref.
MORCEAUX = ["cuir_brut", "crins", "tendons", "boyaux", "graisse", "poils", "os", "plumes",
			"sang", "coeur", "crocs", "yeux", "crane", "griffes", "viande", "foie",
			"item:viande", "item:foie", "item:boyaux", "item:graisse"]
# Une unité par tick d'atelier : le fer est à 5, l'acier à 3 — la bête reste l'affaire du chasseur.
DEBIT_MORCEAUX = 1
# Catégories qui reçoivent les dépouilles du joueur : jamais livrées (cf. docstring, point 1).
CATEGORIES_EXCLUES = {"boucherie"}

# Herbes indispensables du §5 (« doit » > 0) : deux unités par tick, sous leur id.
HERBES = {"item:Herbes_medicinales": 2, "item:Seve_de_chene": 2, "item:Herbes_a_bruler": 2}

# Zone de biome → ressources ajoutées. Arbres sur pied (la coupe donne le reste), palmes à part.
ESSENCES_PAR_ZONE = {
	"zone:maquis": ["item:Cypres", "item:Caroubier"],
	"zone:garrigue": ["item:Cypres", "item:Caroubier"],
	"zone:pinede_seche": ["item:Cypres"],
	"zone:steppe_aride": ["item:Arganier"],
	"zone:contreforts_arides": ["item:Arganier"],
	"zone:oasis": ["item:Doum", "item:Branche_de_Doum", "item:Branche_de_Palmier_dattier"],
	"zone:palmeraie": ["item:Doum", "item:Branche_de_Doum", "item:Branche_de_Palmier_dattier"],
}


def appro(docs: list, marche) -> dict | None:
	"""`rules:world_variables` corrigé, ou None s'il est déjà à jour."""
	wv = next(d for d in docs if d["_id"] == "rules:world_variables")
	val = copy.deepcopy(wv["value"])
	debit = val.setdefault("APPRO_DEBIT", {})
	extra = val.setdefault("APPRO_EXTRA", {})
	besoins = marche._get_marche_map()["besoins"]
	for cle in MORCEAUX:
		debit.setdefault(cle, DEBIT_MORCEAUX)
		for cat in sorted(c for c, b in besoins.items() if cle in b and c not in CATEGORIES_EXCLUES):
			liste = extra.setdefault(cat, [])
			if cle not in liste:
				liste.append(cle)
	for cle, q in HERBES.items():
		debit.setdefault(cle, q)
	if val == wv["value"]:
		return None
	return dict(gpv._sans_rev(wv), value=val)


def zones(docs: list) -> tuple[list, list]:
	"""(zones corrigées, erreurs)."""
	index = {d["_id"]: d for d in docs}
	sortie, erreurs = [], []
	for zid, res in ESSENCES_PAR_ZONE.items():
		z = index.get(zid)
		if z is None:
			erreurs.append("%s absente" % zid)
			continue
		manquants = [r for r in res if r not in index]
		if manquants:
			erreurs.append("%s : items absents %s" % (zid, manquants))
			continue
		liste = copy.deepcopy(z.get("defauts_ressources") or [])
		deja = {e.get("ressource") for e in liste}
		ajout = [r for r in res if r not in deja]
		if ajout:
			liste += [{"ressource": r} for r in ajout]
			sortie.append(dict(gpv._sans_rev(z), defauts_ressources=liste))
			print("  zone    %-28s + %s" % (zid, ", ".join(ajout)))
	return sortie, erreurs


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args()
	chemin = args.dump or gpv.dernier_dump()
	print("source : %s" % os.path.relpath(chemin, RACINE))

	import audit_economy
	docs, _meta = audit_economy.charger_dump(chemin)
	docs = [copy.deepcopy(d) for d in docs if isinstance(d, dict) and d.get("_id")]
	_cs, _ch, marche = audit_economy.brancher_moteur(docs)

	wv = appro(docs, marche)
	zs, erreurs = zones(docs)
	raretes = gpv.corriger_raretes(docs)
	marche.reset_prix_cache()
	variantes, err_v = gpv.recalculer_variantes(docs)
	erreurs += err_v
	if erreurs:
		print("\n⚠ RIEN N'EST ÉCRIT :")
		for e in erreurs:
			print("  · " + e)
		return 1

	lot = ([wv] if wv else []) + zs + raretes + variantes
	ids = [d["_id"] for d in lot]
	assert len(ids) == len(set(ids)), "un _id en double dans le lot"
	with open(args.sortie, "w", encoding="utf-8") as f:
		json.dump(lot, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("\nvariables de monde %d · zones %d · matières %d · variantes %d → %s"
		  % (1 if wv else 0, len(zs), len(raretes), len(variantes), os.path.relpath(args.sortie, RACINE)))
	return 0


if __name__ == "__main__":
	sys.exit(main())

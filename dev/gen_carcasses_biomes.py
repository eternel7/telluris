"""Carcasses à poids RÉALISTE des 15 espèces de faune des zones par biome (`gen_zones_biomes.py`),
puis leur découpe par `gen_carcasses_parties.generer` — UN fichier (CLAUDE.md §18) :
`jsons/carcasses_biomes_a_importer.json`.

Sans carcasse en base, `combat._ensure_loot_item` en crée une au premier butin avec un poids de
REPLI (Force moyenne / 5, plafonné à 25 kg : un éléphant pèserait 25 kg). Ici chaque carcasse
est calibrée comme celles du bestiaire (cerf 100-250, taureau 440-1500, mammouth 5000-12000),
pour UN animal du groupe ; au-delà du seuil de découpe (`CARCASSE_DECOUPE_POIDS_MIN`), la
carcasse est débitée en portions puis en morceaux, comme toutes les autres.

Le lot porte AUSSI le reste du delta de `gen_carcasses_parties` sur le même dump (ex. les tags de
comportement en combat retirés des portions existantes, 15/11) : un seul import pour une passe.
Delta seul ; une carcasse déjà en base n'est jamais recréée (son poids édité est gardé).

    python dev/gen_carcasses_biomes.py [--dump jsons/telluris-dump-….json] [--sortie …]
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import gen_carcasses_parties as parties  # noqa: E402
from gen_genres_especes import accord_de  # noqa: E402
from gen_zones_biomes import ESPECES  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "carcasses_biomes_a_importer.json")

# slug → poids [min, max] en kg, pour UN animal du groupe.
CARCASSES = {
	"singes": [10, 40],
	"grands_singes": [80, 200],
	"antilopes": [20, 120],
	"hyenes": [40, 80],
	"autruches": [60, 140],
	"hippopotames": [1000, 3000],
	"flamants": [2, 4],
	"elephants": [2500, 6000],
	"buffles": [400, 900],
	"rennes": [70, 180],
	"boeufs_musques": [180, 400],
	"bisons": [400, 1000],
	"yacks": [300, 800],
	"phoques_et_morses": [80, 1200],
	"tortues_marines": [70, 200],
}


def _de(slug: str, nom: str) -> str:
	"""« de Hyènes » (h aspiré, lu dans `gen_genres_especes`) / « d'Antilopes » / « de Singes »."""
	return "de " if accord_de(slug).get("h_aspire") else parties.de_ou_d(nom)


def carcasse_doc(slug: str) -> dict:
	nom = ESPECES[slug][0]
	de = _de(slug, nom)
	return {"_id": f"item:{slug}", "type": "item", "nom": f"Carcasse {de}{nom}", "sous_categorie": "carcasse",
			"icon": "🥩", "rarete": "commun", "categorie": "composant", "slots": [],
			"poids": list(CARCASSES[slug]), "description": f"Dépouille {de}{nom} récupérée à l'issue du combat.",
			"source_espece": f"espece:{slug}", "loot_defaut": True}


def construire(dump_docs: list) -> tuple[list, list]:
	"""(docs à importer, avertissements). Carcasses neuves ajoutées au dump, puis découpe de TOUT
	ce que `generer` juge à écrire ; une carcasse légère (sous le seuil) part telle quelle."""
	par_id = {d["_id"]: d for d in dump_docs if isinstance(d, dict) and d.get("_id")}
	avert = [f"espece:{s} absente du dump (importer zones_biomes d'abord)"
			 for s in CARCASSES if f"espece:{s}" not in par_id]
	neuves = [carcasse_doc(s) for s in CARCASSES if f"item:{s}" not in par_id and f"espece:{s}" in par_id]
	sortie, _, ignorees, orphelins, _ = parties.generer(dump_docs + neuves)
	avert += [f"ignorée : {i}" for i in ignorees if any(i.startswith(c["_id"]) for c in neuves)]
	avert += [f"orphelin : {o}" for o in orphelins]
	ids = {d["_id"] for d in sortie}
	sortie += [c for c in neuves if c["_id"] not in ids]
	return sortie, avert


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	if set(CARCASSES) != set(ESPECES):
		print("✗ CARCASSES et gen_zones_biomes.ESPECES divergent :", sorted(set(CARCASSES) ^ set(ESPECES)))
		return 1
	parties.controler_profils()
	dump = args.dump or sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))[-1]
	print(f"Dump : {os.path.relpath(dump, RACINE)}")
	with open(dump, encoding="utf-8") as f:
		docs = json.load(f)["docs"]
	sortie, avert = construire(docs)
	for a in avert:
		print("⚠ " + a)
	if any(a.startswith("espece:") for a in avert):
		return 1
	par_id = {d["_id"]: d for d in docs}
	nouveaux = [d["_id"] for d in sortie if d["_id"] not in par_id]
	print(f"À émettre : {len(sortie)} docs ({len(nouveaux)} nouveaux, {len(sortie) - len(nouveaux)} modifiés)")
	if not sortie:
		print("Rien à émettre.")
		return 0
	ids = [d["_id"] for d in sortie]
	assert len(ids) == len(set(ids)), "collision d'_id"
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=1)
		f.write("\n")
	print(f"→ {os.path.relpath(args.sortie, RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())

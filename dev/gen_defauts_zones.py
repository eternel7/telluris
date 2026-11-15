"""Amorçage du CONTENU PAR DÉFAUT des zones d'influence (cf. `utils/zones.py`, `peupler_lieu`).

Écrit UN fichier `jsons/defauts_zones_a_importer.json` (CLAUDE.md §18), DELTA seul contre le dump :

- `rules:regions` : chaque pays dans sa région (table `REGIONS` ci-dessous, autorée). Une cité,
  un sous-lieu héritent de la région de leur `lieu_parent` à la lecture : seuls les pays y figurent.
- `zone:*` : `defauts_rencontres` / `defauts_ressources` DÉDUITS de l'existant — une espèce ou une
  ressource que AU MOINS `SEUIL_LIEUX` lieux rattachent déjà à cette zone devient un défaut,
  SANS `regions` (Auteur, 16/11 : une zone par BIOME, `dev/gen_zones_biomes.py` ; le filtre reste
  en réserve pour un endémique isolé, posé à la main dans /admin/zones). Les lieux ne sont PAS
  modifiés : la fusion étant une union, leurs entrées existantes deviennent de simples doublons.

Idempotent : un défaut déjà présent sur la zone est gardé tel quel (régions comprises — une
retouche faite dans /admin/zones n'est jamais écrasée) ; une zone ou des règles déjà à jour ne
sont pas réémises ; rien à émettre ⇒ aucun fichier.

    python dev/gen_defauts_zones.py [--dump jsons/telluris-dump-….json] [--sortie …]
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import zones  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "defauts_zones_a_importer.json")
SEUIL_LIEUX = 2

# Régions de FAUNE et de FLORE (pas de frontières politiques) : un défaut régional y vaut.
REGIONS = {
	"europe": ("Europe", [
		"lieu:france", "lieu:europe", "lieu:plaine_europeenne", "lieu:angleterre", "lieu:espagne",
		"lieu:italie", "lieu:pannonie", "lieu:roumanie", "lieu:balkans", "lieu:pologne_ruthenie",
		"lieu:baltique_orientale", "lieu:scandinavie_meridionale", "lieu:moscovie",
	]),
	"grand_nord": ("Grand Nord", ["lieu:grand_nord", "lieu:islande", "lieu:laponie"]),
	"steppes": ("Steppes et Caucase", [
		"lieu:steppe_pontique", "lieu:basse_volga", "lieu:volga_oural", "lieu:caucase",
	]),
	"afrique_du_nord": ("Afrique du Nord et Orient", [
		"lieu:afrique_du_nord", "lieu:maroc", "lieu:ifriqiya", "lieu:egypte", "lieu:nubie", "lieu:levant",
	]),
	"afrique": ("Afrique subsaharienne", [
		"lieu:afrique", "lieu:abyssinie", "lieu:senegambie", "lieu:cote_de_guinee", "lieu:bassin_du_congo",
		"lieu:grands_lacs", "lieu:lac_tchad", "lieu:angola", "lieu:zambeze", "lieu:namib_kalahari",
		"lieu:le_cap", "lieu:madagascar",
	]),
	"oceanie": ("Océanie", ["lieu:australie"]),
}


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def regles_regions(existant: dict | None) -> dict:
	"""`rules:regions` : les régions de la table, en GARDANT ce qu'une édition y a ajouté (lieux
	et régions en plus). Les régions de la table passent d'abord, dans son ordre."""
	doc = {k: v for k, v in (existant or {}).items() if k not in ("_rev",)}
	doc.setdefault("_id", zones.REGLES_REGIONS)
	doc.setdefault("type", "rules")
	regions = dict(doc.get("regions") or {})
	fusion = {}
	for rid, (nom, lieux) in REGIONS.items():
		reg = dict(regions.pop(rid, {}) or {})
		reg.setdefault("nom", nom)
		vus = list(reg.get("lieux") or [])
		reg["lieux"] = vus + [l for l in lieux if l not in vus]
		fusion[rid] = reg
	fusion.update(regions)
	doc["regions"] = fusion
	return doc


def deduire(lieux: list, regles: dict) -> dict:
	"""`{zone_id: {"rencontres": {id: [regions]}, "ressources": {id: [regions]}}}` : ce que
	`SEUIL_LIEUX` lieux au moins rattachent à la zone. Régions toujours VIDES : l'amorçage n'en écrit
	plus (Auteur, 16/11 — une zone par biome) ; la forme `{id: [regions]}` reste celle que lit
	`zones_a_emettre`."""
	par_id = {l["_id"]: l for l in lieux}
	compte: dict = {}
	for lieu in lieux:
		region = zones.region_de(lieu, regles, par_id.get)
		for champ, cle, _ in zones.CHAMPS_CONTENU:
			for e in lieu.get(champ) or []:
				ident = e.get(cle)
				for z in (e.get("zones") or []) if ident else []:
					if zones.SEP_PLACEMENT in z:
						continue
					fiche = compte.setdefault(z, {}).setdefault(champ, {}).setdefault(ident, {})
					fiche.setdefault(lieu["_id"], region)
	out: dict = {}
	for z, champs in compte.items():
		for champ, ids in champs.items():
			for ident, lieux_regions in ids.items():
				if len(lieux_regions) < SEUIL_LIEUX:
					continue
				out.setdefault(z, {}).setdefault(champ, {})[ident] = []
	return out


def zones_a_emettre(docs: dict, deduits: dict) -> list:
	"""Zones RELUES du dump, complétées des défauts déduits absents ; seules celles qui changent."""
	out = []
	for z in sorted(deduits):
		zone = docs.get(z)
		if not zone:
			print(f"⚠ {z} : rattachée par des lieux mais absente du dump, ignorée")
			continue
		neuve = {k: v for k, v in zone.items() if k != "_rev"}
		change = False
		for champ, cle, champ_defaut in zones.CHAMPS_CONTENU:
			defauts = [dict(d) for d in neuve.get(champ_defaut) or []]
			presents = {d.get(cle) for d in defauts}
			for ident, regions in deduits[z].get(champ, {}).items():
				if ident in presents:
					continue
				entree = {cle: ident}
				if regions:
					entree["regions"] = regions
				defauts.append(entree)
				change = True
			if defauts or champ_defaut in neuve:
				neuve[champ_defaut] = defauts
		if change:
			out.append(neuve)
	return out


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	chemin = args.dump or dernier_dump()
	print(f"Dump : {os.path.relpath(chemin, RACINE)}")
	with open(chemin, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}

	inconnus = [l for _, ls in REGIONS.values() for l in ls if l not in docs]
	if inconnus:
		sys.exit(f"Pays absents du dump : {inconnus}")
	lieux = [d for i, d in docs.items() if i.startswith("lieu:")]
	pays = {i for i, d in docs.items() if i.startswith("lieu:") and d.get("categorie") == "pays"}
	classes = {l for _, ls in REGIONS.values() for l in ls}
	hors = sorted(pays - classes - {"lieu:world"})
	if hors:
		print(f"⚠ pays sans région : {hors}")

	existant = docs.get(zones.REGLES_REGIONS)
	regles = regles_regions(existant)
	emis = []
	if {k: v for k, v in (existant or {}).items() if k != "_rev"} != regles:
		emis.append(regles)
	deduits = deduire(lieux, regles)
	zones_neuves = zones_a_emettre(docs, deduits)
	emis += zones_neuves

	n_renc = sum(len(v.get("rencontres", {})) for v in deduits.values())
	n_ress = sum(len(v.get("ressources", {})) for v in deduits.values())
	print(f"Défauts déduits (≥ {SEUIL_LIEUX} lieux) : {n_renc} rencontres, {n_ress} ressources, "
		  f"sur {len(deduits)} zones ; {len(zones_neuves)} zone(s) à réémettre")
	for z in zones_neuves:
		for champ, cle, champ_defaut in zones.CHAMPS_CONTENU:
			for d in z.get(champ_defaut) or []:
				print(f"  {z['_id']:<26} {cle:<9} {d[cle]:<34} {','.join(d.get('regions') or []) or 'partout'}")
	if not emis:
		print("Rien à émettre : tout est déjà à jour.")
		return 0
	ids = [d["_id"] for d in emis]
	assert len(ids) == len(set(ids)), "collision d'_id dans la sortie"
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(emis, f, ensure_ascii=False, indent=1)
		f.write("\n")
	print(f"→ {os.path.relpath(args.sortie, RACINE)} ({len(emis)} docs)")
	return 0


if __name__ == "__main__":
	sys.exit(main())

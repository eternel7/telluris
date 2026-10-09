#!/usr/bin/env python
"""Sorts de VOL (`effets.vol`, utils/vol.py) — un par école hors Élémentaire, + leurs grimoires."""
# dev/gen_sorts_vol.py
#
# Le vol est né dans l'école Illusoire (Voile d'Icare, niveau 3) ; les autres écoles l'obtiennent
# PLUS HAUT (4 → 6), chacune avec sa nuance. Élémentaire n'a pas de sort de vol (décision de
# l'Auteur). Ailes de Dédale = la version MAINTENUE (combat seulement : le moteur refuse un sort
# maintenu hors combat, faute de round où prélever l'entretien).
#
# Tout sort de vol ACCÉLÈRE (décision de l'Auteur) : buff de V, à SON échelle (1-10 — −2 V ≈
# un tiers du déplacement d'un humain, cf. `sorts._bonus_dict`) : +1 jusqu'au niveau 4, +2
# au-delà. Constante, jamais une formule (garde-fou de contenu : pas de V par formule).
#
# Règle de contenu (telluris-magie) : un composant consommé ET un catalyseur, le catalyseur
# plus faible sur la même clé. Composants = ceux que l'école emploie déjà en base.
#
# Chaque sort sort avec son GRIMOIRE UNIQUE et sa RECETTE de scriptorium (`utils/grimoires.py`,
# matières relues dans le dump) — sinon il ne s'apprend pas. Seuls les grimoires de CES sorts
# sont émis, pas ceux d'autres sorts orphelins (c'est le travail de dev/gen_grimoires.py).
#
# IDEMPOTENT : un doc déjà en base à l'identique n'est pas réémis ; un `_id` pris par un doc
# différent fait REFUSER tout le lot (l'import est un PUT complet).
#
# Usage : python dev/gen_sorts_vol.py [--dump chemin] [--sortie chemin]
# Sortie : jsons/sort_vol_a_importer.json (📥 Importer depuis /admin)

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "sort_vol_a_importer.json")

from utils import grimoires  # noqa: E402

# Buff de vitesse par niveau (cf. en-tête).
V_JUSQU_AU_NIVEAU_4 = 1
V_AU_DELA = 2
NIVEAU_PALIER_V = 4


def vitesse(niveau: int) -> int:
	return V_JUSQU_AU_NIVEAU_4 if niveau <= NIVEAU_PALIER_V else V_AU_DELA


def _sort(slug, nom, icon, animation, magie, niveau, cout_pm, effets, consomme, catalyseur,
		  description, **champs) -> dict:
	"""Doc `sort:*` de vol. `consomme` / `catalyseur` = (item, bonus) ; le catalyseur est
	placé AVANT le consommé (ordre de la base)."""
	effets = {"vol": 1, **effets}
	effets["buffs"] = {**(effets.get("buffs") or {}), "V": vitesse(niveau)}
	return {
		"_id": "sort:" + slug,
		"type": "sort",
		"nom": nom,
		"icon": icon,
		"animation": animation,
		"description": description,
		"magie": magie,
		"niveau": niveau,
		"cout_pm": cout_pm,
		"cible": "soi",
		"portee": 0,
		**champs,
		"effets": effets,
		"composants": [
			{"item": catalyseur[0], "consomme": False, "bonus": catalyseur[1]},
			{"item": consomme[0], "consomme": True, "bonus": consomme[1]},
		],
	}


DUREE_CONSO = {"duree": 2}
DUREE_CATA = {"duree": 1}

SORTS = [
	_sort("voile_d_icare", "Voile d'Icare", "🪽", "animation:capa_illusion", "Illusoire", 3, 20,
		  {"duree": "2+{Int/20}"},
		  ("item:Poudre_de_miroir", DUREE_CONSO), ("item:Plume_d_oie", DUREE_CATA),
		  "Un mirage tissé autour du corps le porte au-dessus du sol : on foule l'air des "
		  "rivières et des à-pics tant que l'illusion tient. Qu'elle se dissipe au-dessus du "
		  "vide, et la chute, elle, est bien réelle."),
	_sort("ailes_de_dedale", "Ailes de Dédale", "🪶", "animation:capa_illusion", "Illusoire", 6, 30,
		  {},
		  ("item:Poudre_de_miroir", {"maintien_reduction": 2}),
		  ("item:Plume_d_oie", {"maintien_reduction": 1}),
		  "Dédale, dit-on, sut voler sans se brûler parce qu'il ne lâcha jamais son ouvrage des "
		  "yeux. Ces ailes d'illusion tiennent tant que la volonté du mage les tient — qu'elle "
		  "vacille sous un coup, et le ciel se dérobe.",
		  maintien=4),
	_sort("talonnieres_de_persee", "Talonnières de Persée", "👟", "animation:capa_arcane", "Bataille",
		  4, 28, {"duree": "2+{Int/20}", "esquive": 5},
		  ("item:poudre_alchimique", DUREE_CONSO), ("item:Cristal_canalisation", DUREE_CATA),
		  "Des ailes de force pure poussent aux chevilles, comme aux sandales que Persée reçut "
		  "pour aller trancher la Gorgone. Le combattant bondit d'un à-pic à l'autre, plus vif "
		  "et plus difficile à toucher."),
	_sort("manteau_de_freyja", "Manteau de Freyja", "🦅", "animation:capa_meditation", "Nature",
		  5, 32, {"duree": "3+{Vol/20}", "buffs": {"Ag": 5}},
		  ("item:Fiole_sang_bete", DUREE_CONSO), ("item:Os_de_totem", DUREE_CATA),
		  "Les skaldes chantent la cape de plumes de faucon qu'une déesse prêtait à qui devait "
		  "franchir les mondes. Le druide en revêt l'esprit : il prend l'air, et l'aisance du "
		  "rapace avec."),
	_sort("plume_de_maat", "Plume de Maât", "🪶", "animation:capa_meditation", "Sainte",
		  5, 32, {"duree": "2+{Vol/20}", "regen_pv": 2},
		  ("item:Eau_benite", DUREE_CONSO), ("item:encens", DUREE_CATA),
		  "Sur les rives du Nil, on pesait les cœurs contre une plume : le juste était plus "
		  "léger qu'elle. La prière rend au fidèle cette légèreté — il s'élève, et ses plaies "
		  "se referment tant qu'il demeure en l'air."),
	_sort("ailes_de_pazuzu", "Ailes de Pazuzu", "🦇", "animation:capa_arcane", "Démonologie",
		  6, 24, {"duree": "3+{Int/20}", "cout_pv": 8},
		  ("item:Sang_demon_seche", DUREE_CONSO), ("item:Sel_noir", DUREE_CATA),
		  "Les vieilles tablettes de Babylone montrent un démon des vents à quatre ailes. Ses "
		  "ailes se prêtent, elles ne se donnent pas : le démoniste les paie de son propre sang."),
	_sort("envol_du_ba", "Envol du Ba", "🕊️", "animation:capa_spectre", "Nécromancie",
		  6, 36, {"duree": "4+{Int/30}"},
		  ("item:Sel_des_sepultures", DUREE_CONSO), ("item:os", DUREE_CATA),
		  "Les embaumeurs d'Égypte disaient que l'âme quitte la tombe sous la forme d'un oiseau "
		  "à tête humaine. Le nécromancien détache un peu de la sienne : le corps suit, longtemps, "
		  "comme s'il ne pesait déjà plus rien."),
]


def slugs() -> set:
	return {s["_id"][len("sort:"):] for s in SORTS}


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
	return dumps[-1]


def deja_importe(genere: dict, existant: dict) -> bool:
	"""Chaque champ produit se retrouve à l'identique (la base peut ENRICHIR un doc importé)."""
	return all((existant or {}).get(k) == v for k, v in (genere or {}).items())


def construire(base: dict) -> tuple:
	"""`(docs, erreurs)` : sorts neufs puis leurs grimoires + recettes. Un `_id` déjà en base
	à l'identique est sauté ; pris par un doc différent, c'est une erreur."""
	neufs, erreurs = [], []
	for doc in SORTS:
		existant = base.get(doc["_id"])
		if existant is None:
			neufs.append(doc)
		elif not deja_importe(doc, existant):
			erreurs.append(f"{doc['_id']} : `_id` déjà pris par un doc différent")
	grim_docs, _lignes, grim_erreurs = grimoires.grimoires_manquants(base, neufs)
	nos_slugs = slugs()
	# Seulement les grimoires de NOS sorts : `grimoires_manquants` rend aussi ceux de tout
	# autre sort orphelin de la base.
	grim_docs = [d for d in grim_docs if d["_id"].split(":", 1)[1][len("grimoire_"):] in nos_slugs]
	erreurs += [e for e in grim_erreurs if any(f"grimoire_{s}" in e for s in nos_slugs)
				or "aucune recette" in e]
	return neufs + grim_docs, erreurs


def _affiche(chemin) -> str:
	"""Chemin relatif au dépôt pour l'affichage. ⚠️ Sous Windows, `relpath` LÈVE si le chemin
	est sur un autre lecteur que le dépôt (sortie dans un dossier temporaire sur C:, dépôt
	sur Z:) : on montre alors le chemin absolu plutôt que d'échouer après avoir écrit."""
	try:
		return os.path.relpath(chemin, RACINE)
	except ValueError:
		return os.path.abspath(chemin)


def main(argv=None) -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	chemin = args.dump or dernier_dump()
	base = {d["_id"]: d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")}
	docs, erreurs = construire(base)
	if erreurs:
		print(f"REFUS — {len(erreurs)} erreur(s), rien n'est écrit :")
		for e in erreurs:
			print("  · " + e)
		return 1
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} doc(s) écrits dans {_affiche(args.sortie)} — "
		  f"{sum(1 for d in docs if d['type'] == 'sort')} sort(s), "
		  f"{sum(1 for d in docs if d['type'] == 'item')} grimoire(s), "
		  f"{sum(1 for d in docs if d['type'] == 'recette')} recette(s).")
	return 0


if __name__ == "__main__":
	sys.exit(main())

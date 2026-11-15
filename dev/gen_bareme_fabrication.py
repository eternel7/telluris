#!/usr/bin/env python
# dev/gen_bareme_fabrication.py
# Barème de fabrication (Auteur, 15/11) — la DONNÉE qu'il exige, et les variantes déjà en base.
#
# Le moteur (`utils/fabrication.py`) fait désormais :
#   - dégâts et PA d'une matière au barème de sa RARETÉ (`BAREME_DEGATS`, `BAREME_PA`), lus à la
#     lecture : les matières elles-mêmes ne sont PAS réécrites ;
#   - dés des matières AJOUTÉS à ceux de la pièce (« 1D8+1D6 ») ;
#   - une matière par FAMILLE et une partie par CRÉATURE (`conflits_combinaison`).
#
# Ce script pose ce que le moteur lit et que la donnée n'a pas encore :
#   1. tags de famille `cuir` / `gemme` sur les matières d'échoppe (`FAMILLES_ECHOPPE`), `cuir` /
#      `tissu` sur les matières nommées légendaires (selon leur sorte,
#      `gen_trophees_legendaires.FAMILLE_SORTE`) — les autres tags ne sont jamais touchés ;
#   2. `source_espece` sur les matières nommées légendaires (`legendaires_table.ESPECES`), pour
#      qu'« une partie par créature » les rapproche des carcasses de la même bête ;
#   3. les VARIANTES sur mesure déjà en base (`fabrication.base_item`) : `bonus_degats`,
#      `bonus_degats_dice` et `bonus_pa` recalculés depuis leur objet de base et leurs matières
#      (`assurer_variante` ne retouche jamais un doc existant). Poids, valeur, nom et autres
#      bonus ne bougent pas. Une variante qui enfreint les nouvelles règles de combinaison est
#      SIGNALÉE (elle existe, on ne la défait pas) et reçoit quand même le barème.
#
# Les exemplaires portés ne sont que des RÉFÉRENCES vers le doc `item:*` : corriger le doc corrige
# tous les exemplaires, au prochain recalcul de l'équipement.
#
# Relit le dump le plus récent (ou `--dump`), n'écrit que les docs qui CHANGENT (CLAUDE.md §11,
# §18) → jsons/bareme_fabrication_a_importer.json. Base à jour ⇒ aucun fichier.
#
# Usage : python dev/gen_bareme_fabrication.py [--dump jsons/telluris-dump-….json]

import argparse
import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import fabrication  # noqa: E402
import legendaires_table as table  # noqa: E402
from gen_trophees_legendaires import FAMILLE_SORTE  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "bareme_fabrication_a_importer.json")

# Famille des matières d'échoppe (Auteur, 15/11). Aucune matière de tissu n'est vendue en échoppe :
# le tissu ne vient que des matières nommées (plumes, soies).
FAMILLES_ECHOPPE = {
	"item:cuir": "cuir",
	"item:cuir_brut": "cuir",
	"item:Cuir_bouilli": "cuir",
	"item:Cuir_fume": "cuir",
	"item:Cuir_tanne_au_chene": "cuir",
	"item:Croupon_epais": "cuir",
	"item:Peau_chamoisee": "cuir",
	"item:gemmes": "gemme",
	"item:perles": "gemme",
	"item:Poudre_amethyste": "gemme",
}

CLES_VARIANTE = ("bonus_degats", fabrication.CLE_DES, "bonus_pa")


def charger(chemin=None):
	if not chemin:
		dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
		if not dumps:
			sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
		chemin = dumps[-1]
	with open(chemin, encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(chemin)


def complements_matieres() -> dict:
	"""`{item_id: {"tag": str|None, "source_espece": str|None}}` voulus sur les matières."""
	voulu = {iid: {"tag": fam, "source_espece": None} for iid, fam in FAMILLES_ECHOPPE.items()}
	for esp, (_palier, _t, _du, (slug, _nom, _icon, sorte), _evoc) in table.ESPECES.items():
		voulu["item:" + slug] = {"tag": FAMILLE_SORTE.get(sorte), "source_espece": esp}
	return voulu


def matieres_a_ecrire(docs: dict, erreurs: list) -> dict:
	"""Docs matière complétés (relus du dump, `_rev` retiré), seulement ceux qui changent."""
	sortie = {}
	for iid, voulu in sorted(complements_matieres().items()):
		doc = docs.get(iid)
		if doc is None:
			erreurs.append(f"{iid} : absent du dump — ignoré")
			continue
		nouveau = copy.deepcopy({k: v for k, v in doc.items() if k != "_rev"})
		tags = list(nouveau.get("tags") or [])
		if voulu["tag"] and voulu["tag"] not in tags:
			nouveau["tags"] = tags + [voulu["tag"]]
		if voulu["source_espece"]:
			nouveau["source_espece"] = voulu["source_espece"]
		if nouveau != {k: v for k, v in doc.items() if k != "_rev"}:
			sortie[iid] = nouveau
	return sortie


def variantes_a_ecrire(docs: dict, erreurs: list, signalees: list) -> dict:
	"""Variantes recalculées (barème, dés ajoutés), seulement celles qui changent.
	`docs` doit déjà porter les matières complétées (familles, créature)."""
	sortie = {}
	for iid, doc in sorted(docs.items()):
		fab = doc.get("fabrication") if iid.startswith("item:") else None
		base_id = fab.get("base_item") if isinstance(fab, dict) else None
		if not base_id:
			continue
		base = docs.get(base_id)
		mats = [(docs.get(m.get("item")), m.get("quantite", 1)) for m in (fab.get("matieres") or [])]
		if base is None or any(d is None for d, _q in mats):
			erreurs.append(f"{iid} : objet de base ou matière absent du dump — ignorée")
			continue
		conflits = fabrication.conflits_combinaison(mats)
		if conflits:
			signalees.append((iid, conflits))
		mods = fabrication.appliquer_modificateurs(base, mats)
		nouveau = copy.deepcopy({k: v for k, v in doc.items() if k != "_rev"})
		for cle in CLES_VARIANTE:
			if mods.get(cle) is None:
				nouveau.pop(cle, None)
			else:
				nouveau[cle] = mods[cle]
		if nouveau != {k: v for k, v in doc.items() if k != "_rev"}:
			sortie[iid] = nouveau
	return sortie


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--dump")
	args = parser.parse_args()
	docs, nom = charger(args.dump)
	print(f"Dump : {nom}")
	erreurs, signalees = [], []

	matieres = matieres_a_ecrire(docs, erreurs)
	index = dict(docs)
	index.update(matieres)
	variantes = variantes_a_ecrire(index, erreurs, signalees)

	for iid, doc in matieres.items():
		print(f"  matière {iid} : tags {doc.get('tags')}, espèce {doc.get('source_espece') or '—'}")
	for iid, doc in variantes.items():
		avant = docs[iid]
		detail = ", ".join(f"{k} {avant.get(k)} → {doc.get(k) if doc.get(k) is not None else '∅'}"
						   for k in CLES_VARIANTE if avant.get(k) != doc.get(k))
		print(f"  variante {iid} : {detail}")
	for iid, conflits in signalees:
		motifs = "; ".join(f"{c['motif']} {c['cle']} ({', '.join(d.get('_id', '?') for d in c['docs'])})"
						   for c in conflits)
		print(f"  ⚠ {iid} enfreint les règles de combinaison : {motifs}")
	for e in erreurs:
		print(f"  ⚠ {e}")

	lot = list(matieres.values()) + list(variantes.values())
	ids = [d["_id"] for d in lot]
	if len(ids) != len(set(ids)):
		sys.exit("ERREUR : _id en double dans le lot")
	if not lot:
		print("Base à jour : aucun fichier écrit.")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(lot, f, ensure_ascii=False, indent=2)
	print(f"{len(matieres)} matière(s) + {len(variantes)} variante(s) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()

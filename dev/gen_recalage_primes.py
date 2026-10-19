#!/usr/bin/env python
# dev/gen_recalage_primes.py
# Recalage des primes en cuivre des quêtes ÉCRITES sur un barème par rang (revue du dump du
# 18/10/2026) : les quêtes générées paient `QUETE_CUIVRE_PAR_XP` = 3 cu/XP (27 à 384 cu au
# tableau), les quêtes écrites 83 à 250 cu/XP — le convoi de Chartres, sans rang, rapportait
# le prix d'une Chambre (5 000 cu) et une escorte de rang D celui d'un Logement et demi.
#
# Barème (cuivre) : sans rang ≈ 150–300 · E ≈ 500 · D ≈ 1 500 · C ≈ 3 000. Un apport sans
# `rang_min` se range au rang que son XP désigne (70 XP : entre E et D).
# Seul `recompenses.cuivre` change ; XP, items, `rang_guilde` et dialogues ({prime}) intacts.
#
# Relit le dump le plus récent et n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/recalage_primes_a_importer.json. Rejouable : une prime déjà recalée est reconnue et
# sautée ; une prime ni ancienne ni nouvelle est une ERREUR (le doc a bougé : arbitrer).
#
# ⚠️ Les anciens fichiers d'import et générateurs qui écrivent ces PNJ (gen_convoi_lutecia,
# gen_enquete_escolives, gen_enquete_morvan, gen_escorte_guilde, gen_mission_bucherons,
# gen_quete_rang_c_jumieges, pnj_bouchard_de_clignancourt_a_importer.json…) portent encore
# l'ancienne prime : les réimporter effacerait ce recalage.
#
# Usage : python dev/gen_recalage_primes.py

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "recalage_primes_a_importer.json")

# (pnj, service, bloc) → (ancienne prime, nouvelle prime). Le rang en commentaire est celui
# de l'offre (`rang_min`, sinon `rang_guilde`, sinon l'XP).
PRIMES = {
	("pnj:borin_barbe_de_jais", "escorte", "recherche"): (500, 250),                      # sans rang, 30 XP
	("pnj:bouchard_de_clignancourt", "escorte", "offre"): (5000, 300),                    # sans rang, 30 XP
	("pnj:reverend_malakor", "escorte", "offre"): (10000, 500),                           # E, 40 XP
	("pnj:bouchard_de_clignancourt_reims", "escorte", "offre"): (15000, 600),             # E, 60 XP
	("pnj:borin_barbe_de_jais", "apport", "offre"): (8000, 800),                          # E/D, 70 XP
	("pnj:aelis_de_montfaucon_cour_des_arches", "escorte", "offre"): (10000, 1500),       # D, 120 XP
	("pnj:bouchard_de_clignancourt_route_silencieuse", "escorte", "offre"): (30000, 1500),  # D, 120 XP
	("pnj:dame_eleonore_de_rochefort", "escorte", "offre"): (30000, 1500),                # D, 120 XP
	("pnj:frere_martin_de_clairvaux", "escorte", "offre"): (30000, 1500),                 # D, 120 XP
	("pnj:gautier_de_valcroix", "escorte", "offre"): (30000, 1500),                       # D, 120 XP
	("pnj:gautier_de_valcroix", "apport", "offre"): (30000, 1500),                        # D, 120 XP
	("pnj:eleonore_de_vaugirard", "rang", "apport"): (1200, 3000),                        # C, 150 XP
	("pnj:maelys", "transport", "offre"): (20000, 3000),                                  # C, 150 XP
}


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(dumps[-1])


def recaler(base: dict) -> list:
	"""Docs recalés qui DIFFÈRENT de `base` (ids du dump), dans un ordre stable."""
	docs = {}
	for (did, service, bloc), (ancienne, nouvelle) in sorted(PRIMES.items()):
		if did not in base:
			sys.exit(f"ERREUR : {did} absent du dump")
		doc = docs.get(did)
		if doc is None:
			doc = copy.deepcopy(base[did])
			doc.pop("_rev", None)
			docs[did] = doc
		try:
			rec = doc["services"][service][bloc]["recompenses"]
		except KeyError:
			sys.exit(f"ERREUR : services.{service}.{bloc}.recompenses absent de {did}")
		if rec.get("cuivre") not in (ancienne, nouvelle):
			sys.exit(f"ERREUR : {did} services.{service}.{bloc} paie {rec.get('cuivre')!r} cu, "
					 f"ni {ancienne} ni {nouvelle} attendus")
		rec["cuivre"] = nouvelle
	sortie = []
	for did, doc in sorted(docs.items()):
		avant = {k: v for k, v in base[did].items() if k != "_rev"}
		if doc != avant:
			sortie.append(doc)
	return sortie


def main():
	base, nom = dernier_dump()
	docs = recaler(base)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} docs ({nom}) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()

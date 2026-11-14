#!/usr/bin/env python
# dev/gen_renseignement_guilde.py
# 🔎 Salle commune de guilde (Auteur, 14/11/2026 ; compétence telluris-renseignement) :
#  - `rules:renseignement` à jour (méthodes `recrues` et `receptionniste`, source : gen_renseignement) ;
#  - chaque PNJ posté au COMPTOIR d'une guilde (`guilde_aventurier_comptoir`) reçoit
#    `services.renseignement` + le choix « Que sait-on de… ? » au nœud de départ + le nœud
#    `renseignement_ouvre`. Doc RELU dans le dump et fusionné (PUT complet à l'import : rien
#    d'autre ne bouge) ; un PNJ qui porte déjà le service n'est pas réécrit.
#
# ⚠️ Un seul fichier, le delta de CETTE demande seulement (convention 18) : l'item
# `item:note_renseignement` d'une demande antérieure n'y figure pas. Chaque PNJ passe le lint
# des dialogues (aucune erreur tolérée).
#
# Usage : python dev/gen_renseignement_guilde.py
# Sortie (/admin → Import en masse) : jsons/renseignement_guilde_a_importer.json

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import gen_renseignement  # noqa: E402
from utils import lint_dialogues  # noqa: E402
from utils import renseignement  # noqa: E402

SORTIE = "jsons/renseignement_guilde_a_importer.json"
CATEGORIE_COMPTOIR = "guilde_aventurier_comptoir"
NOEUD = "renseignement_ouvre"
CHOIX = {"id": "renseignement", "label": "« Que sait-on, à la Guilde, de ce que je cherche ? »",
		 "action": {"service": "renseignement"}}
TEXTE = ("Les registres de la Guilde s'ouvrent sur le comptoir, page après page de signalements "
		 "griffonnés. « Voyons ce qui a été consigné. Dites-moi ce que vous cherchez. »")


def avec_service(pnj: dict) -> dict | None:
	"""Copie du PNJ dotée du service, ou None s'il le porte déjà (idempotent)."""
	if (pnj.get("services") or {}).get("renseignement"):
		return None
	doc = copy.deepcopy(pnj)
	doc.pop("_rev", None)
	dialogue = doc.get("dialogue") or {}
	noeuds = dialogue.get("noeuds") or {}
	depart = dialogue.get("noeud_depart")
	if depart not in noeuds:
		raise SystemExit(f"ERREUR : {pnj['_id']} n'a pas de nœud de départ lisible")
	doc.setdefault("services", {})["renseignement"] = {"noeuds": {"ouvre": NOEUD}}
	choix = noeuds[depart].setdefault("choix", [])
	if not any(c.get("id") == CHOIX["id"] for c in choix):
		choix.append(dict(CHOIX, action=dict(CHOIX["action"])))
	noeuds[NOEUD] = {"texte": TEXTE, "choix": [{"id": "retour", "label": "« Merci. »", "next": depart}]}
	return doc


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def main() -> None:
	for m in gen_renseignement.METHODES:
		renseignement.normaliser_methode(m)
	chemin = _dump_le_plus_recent()
	with open(chemin, encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f).get("docs", []) if d.get("_id")}
	regles = gen_renseignement.docs()[0]
	sortie = []
	if {k: v for k, v in (base.get(regles["_id"]) or {}).items() if k != "_rev"} != regles:
		sortie.append(regles)
	pnj_ids = sorted({e.get("character") for d in base.values()
					  if d.get("type") == "lieu" and d.get("categorie") == CATEGORIE_COMPTOIR
					  for e in d.get("pnj") or [] if isinstance(e, dict) and e.get("character")})
	manquants = [p for p in pnj_ids if p not in base]
	if manquants:
		raise SystemExit(f"ERREUR : PNJ de comptoir absents du dump : {manquants}")
	pnjs = [doc for doc in (avec_service(base[p]) for p in pnj_ids) if doc]
	bilan = lint_dialogues.analyser(pnjs)
	erreurs = [t for t in bilan["trouvailles"] if t["niveau"] == "erreur"]
	if erreurs:
		raise SystemExit("ERREUR de lint :\n" + "\n".join(f"{t['doc_id']} {t['noeud']} : {t['message']}" for t in erreurs))
	sortie += pnjs
	ids = [d["_id"] for d in sortie]
	if len(ids) != len(set(ids)):
		raise SystemExit("ERREUR : _id en double")
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
	print(f"{len(sortie)} doc(s) → {SORTIE} (dont {len(pnjs)} PNJ de comptoir ; "
		  f"{bilan['avertissements']} avertissement(s) de lint ; dump : {os.path.basename(chemin)})")


if __name__ == "__main__":
	main()

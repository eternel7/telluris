#!/usr/bin/env python
# dev/gen_escorte_marchands.py
# Ouvre l'escorte de PROGÉNITURE chez les tenanciers génériques `pnj:marchand_*`.
#
# Le moteur sait déjà tout faire (cf. `utils/escorte.py`, section PROGÉNITURE) ; ce qui
# manque à chaque tenancier, ce sont les MOTS : les nœuds de dialogue par lesquels il parle
# de son enfant, et les choix conditionnés qui les rendent atteignables. Ce fichier n'ajoute
# QUE cela — la machinerie, identique pour tous.
#
# ⚠️ AUCUN ENFANT N'EST ÉCRIT ICI. Un doc `pnj:marchand_<categorie>` est GÉNÉRIQUE : deux
# boutiques d'un même métier le partagent, elles ne peuvent donc pas avoir la même famille.
# La `progeniture` vit sur l'entrée `pnj` du doc LIEU → `dev/gen_progeniture.py`. Tant qu'on
# n'en a posé aucune, ces nœuds restent inatteignables et rien ne change en jeu.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS `dev/gen_marchands.py` : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge. Régénérer les marchands DEPUIS ZÉRO écraserait ce que la base a
# de particulier — les deux nœuds de lore de `pnj:marchand_etable` (conseils de monture), et
# `pnj:marchand_etable` lui-même, que `gen_marchands.py` ne produit plus (la catégorie
# `etable` n'a aucune recette). On RELIT donc les docs depuis le dump et on n'y injecte que
# le fragment d'escorte : régénérer est idempotent, et une retouche faite à la main survit.
#
# La SOURCE des textes reste `dev/gen_marchands.py` (importé ici) : un seul endroit décrit ce
# que dit un tenancier générique, sinon les deux générateurs divergeraient en silence.
#
# Usage : python dev/gen_escorte_marchands.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/marchands_escorte_a_importer.json

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from dev.gen_marchands import (  # noqa: E402  (après l'ajustement de sys.path)
	CHOIX_ACCUEIL_ESCORTE, NOEUDS_DIALOGUE_ESCORTE, NOEUDS_ESCORTE,
)

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260808-073319.json"

PREFIXE = "pnj:marchand_"
SORTIE = "jsons/marchands_escorte_a_importer.json"


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def injecter(doc: dict) -> dict:
	"""Pose le fragment d'escorte sur un doc marchand relu en base. IDEMPOTENT : les nœuds
	sont écrasés par leur version de référence et les choix sont remplacés PAR LEUR ID —
	relancer ce script deux fois ne duplique rien."""
	doc = json.loads(json.dumps(doc))          # copie profonde : on ne mute pas le dump

	services = doc.setdefault("services", {})
	# `setdefault` puis mise à jour du seul sous-champ `noeuds` : un bloc `escorte` déjà
	# présent (une `offre` écrite, une `recherche`) doit survivre intact.
	services.setdefault("escorte", {})["noeuds"] = dict(NOEUDS_ESCORTE)

	dialogue = doc.setdefault("dialogue", {})
	noeuds = dialogue.setdefault("noeuds", {})
	for nid, contenu in NOEUDS_DIALOGUE_ESCORTE.items():
		noeuds[nid] = json.loads(json.dumps(contenu))

	accueil = noeuds.get(dialogue.get("noeud_depart") or "accueil")
	if accueil is None:
		raise SystemExit(f"{doc['_id']} : pas de nœud d'accueil, fragment non posable.")
	nouveaux = {c["id"] for c in CHOIX_ACCUEIL_ESCORTE}
	# On repart des choix existants MOINS les nôtres (idempotence), puis on réinsère le bloc
	# d'escorte JUSTE AVANT le choix de sortie : « Je ne faisais que passer » doit rester la
	# dernière ligne de la liste, c'est la porte de sortie du joueur.
	restants = [c for c in accueil.get("choix") or [] if c.get("id") not in nouveaux]
	sorties = [c for c in restants if (c.get("next") == "fin" and not c.get("condition"))]
	avant = [c for c in restants if c not in sorties]
	accueil["choix"] = avant + [json.loads(json.dumps(c)) for c in CHOIX_ACCUEIL_ESCORTE] + sorties
	return doc


def main() -> None:
	base = charger(SRC_DUMP)
	marchands = [d for d in base
				 if isinstance(d, dict) and str(d.get("_id", "")).startswith(PREFIXE)]
	if not marchands:
		raise SystemExit(f"Aucun doc `{PREFIXE}*` dans {SRC_DUMP} — dump périmé ?")
	docs = [injecter(d) for d in sorted(marchands, key=lambda d: d["_id"])]
	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
	print(f"{len(docs)} tenanciers ouverts à l'escorte -> {SORTIE}")
	print("Rappel : sans `progeniture` sur l'entrée `pnj` d'un lieu (dev/gen_progeniture.py), "
		  "ces nœuds restent inatteignables et rien ne change en jeu.")


if __name__ == "__main__":
	main()

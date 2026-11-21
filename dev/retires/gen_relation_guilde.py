#!/usr/bin/env python
# dev/gen_relation_guilde.py
# Fait porter par le COMPTOIR la réputation des quatre lieux de la guilde d'Auxerre.
#
# La guilde du Bastion de l'Yonne est éclatée en quatre docs `lieu:*` — façade, réception,
# comptoir, bureau du maître —, et chacun portait jusqu'ici SA propre relation. Selon le canal
# emprunté, le `giver` d'une quête change de lieu : le tableau donne la réception, l'épreuve de
# rang donne le comptoir, la commission de donjon donne le bureau. Le joueur voyait donc quatre
# cotes distinctes pour une seule maison, et rendre un service à l'une ne comptait pas chez les
# autres.
#
# Le champ **`relation_lieu`** (lu par `marche.lieu_de_relation`) délègue la relation d'un lieu
# à un autre : on le pose sur la façade, la réception et le bureau, tous trois pointant vers le
# comptoir. ⚠️ UN SEUL SAUT est suivi — le comptoir, lui, ne porte rien (il EST le porteur).
#
# ⚠️ NE TOUCHE NI `categorie` NI `sous_categorie` :
#   · la `categorie` du bureau doit rester `bureau_maitre_guilde` — `lieu:la_mine_aux_cristaux`
#     et `lieu:temple_portail_de_saint_austrelin_interieur` la vérifient dans leur bloc `acces`
#     (`quete_active.giver_categorie`). La changer fermerait DÉFINITIVEMENT deux portes gardées.
#   · ajouter une `sous_categorie` au bureau serait redondant : `relation_lieu` suffit à le faire
#     encaisser sur le comptoir, gain COMME sanction.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc. On RELIT donc les
# docs depuis le dump et on n'y injecte que `relation_lieu` : régénérer est idempotent, et une
# retouche faite à la main en base (un `pnj`, un bloc `acces`) survit à la régénération.
#
# Usage : python dev/gen_relation_guilde.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/relation_guilde_a_importer.json   (3 docs : façade, réception, bureau)

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260807-165213.json"

COMPTOIR_ID = "lieu:le_bastion_de_l_yonne_comptoir"
# Les trois lieux qui délèguent leur réputation au comptoir.
DELEGANTS = [
	"lieu:le_bastion_de_l_yonne",                    # façade (guilde_aventurier_exterieur)
	"lieu:le_bastion_de_l_yonne_interieur",          # réception : tableau de quêtes + recrues
	"lieu:bureau_du_maitre_de_guilde_d_auxerre",     # Gautier : commissions de donjon
]

SORTIE = "jsons/relation_guilde_a_importer.json"


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


_BASE = None


def extraire(doc_id: str) -> dict:
	"""Le doc tel qu'il est EN BASE, jamais retapé. Sortie en erreur s'il manque : mieux vaut
	ne rien générer qu'un fichier d'import qui écraserait un doc par une version inventée."""
	global _BASE
	if _BASE is None:
		_BASE = {d["_id"]: d for d in charger(SRC_DUMP)
				 if isinstance(d, dict) and d.get("_id")}
	if doc_id not in _BASE:
		sys.exit(f"ERREUR : {doc_id} introuvable dans {SRC_DUMP}")
	return _BASE[doc_id]


def main() -> None:
	# Le porteur doit exister : déléguer vers un lieu absent rendrait la relation illisible.
	extraire(COMPTOIR_ID)

	docs = []
	for lieu_id in DELEGANTS:
		doc = extraire(lieu_id)
		if doc.get("relation_lieu") == COMPTOIR_ID:
			print(f"   {lieu_id} : déjà consolidé (réimport sans effet)")
		doc["relation_lieu"] = COMPTOIR_ID
		docs.append(doc)

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	ids = ", ".join(d["_id"] for d in docs)
	print(f"écrit {SORTIE}\n   {len(docs)} doc(s) : relation_lieu = {COMPTOIR_ID}\n   {ids}")


if __name__ == "__main__":
	main()

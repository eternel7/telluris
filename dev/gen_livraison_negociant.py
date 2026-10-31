#!/usr/bin/env python
# dev/gen_livraison_negociant.py
# Le NÉGOCIANT prend livraison des courses, comme tout magasin.
#
# Le moteur le fait déjà destinataire (`transport.tient_boutique` → `magasins_candidats` :
# il achète tout) ; il manque à son tenancier générique `pnj:marchand_negociant` les MOTS :
# le choix d'accueil « Je vous apporte une livraison. » et les trois réponses du router
# (`livre`, `livre_retour` pour une course à retour, `incomplet`). Il ne DONNE aucune course
# (pas de recette → `est_magasin` faux) : ni `propose`, ni `accepte`, ni `mefiance`.
#
# ⚠️ Relit le DUMP et n'injecte que ce fragment (PUT complet à l'import : cf. CLAUDE.md §11).
# Le fragment de direction (`gen_direction_marchands.injecter`, idempotent) est posé AVANT :
# le dump figé ne l'a pas encore, et l'import de ce fichier ne doit pas l'effacer.
#
# Usage : python dev/gen_livraison_negociant.py
# Sortie : jsons/livraison_negociant_a_importer.json

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_direction_marchands as direction   # noqa: E402

SRC_DUMP = direction.SRC_DUMP
DOC_ID = "pnj:marchand_negociant"
SORTIE = "jsons/livraison_negociant_a_importer.json"

NOEUDS_TRANSPORT = {
	"livre": "transport_livre",
	"livre_retour": "transport_livre_retour",
	"incomplet": "transport_incomplet",
}

# Même choix que les autres tenanciers (`transport_a_livrer` : posé par le router).
CHOIX_LIVRAISON = {
	"id": "livraison", "label": "Je vous apporte une livraison.",
	"action": {"service": "transport", "op": "livrer"},
	"condition": {"transport_a_livrer": True},
}

_FIN = [{"id": "ok", "label": "Ce fut un plaisir.", "next": "fin"}]

NOEUDS_DIALOGUE = {
	"transport_livre": {
		"texte": "La balance s'incline sous le premier colis, puis sous le suivant. "
				 "« {colis} colis, pesés et comptés : le compte y est, {prenom}. » Les pièces "
				 "glissent sur le comptoir. « {prime} pièces de cuivre, comptant, comme toujours. "
				 "{expediteur} saura que sa marchandise est arrivée à bon port. »",
		"choix": _FIN,
	},
	"transport_livre_retour": {
		"texte": "« {colis} colis, pesés et comptés. » Un reçu est porté au registre, signé, "
				 "scellé à la cire. « Je ne vous dois rien : c'est {donneur} qui paie les siens. "
				 "Rapportez-lui ce reçu, il fait foi. »",
		"choix": [{"id": "ok", "label": "J'y retourne de ce pas.", "next": "fin"}],
	},
	"transport_incomplet": {
		"texte": "Un doigt suit le registre, puis compte vos colis, et la tête se secoue. "
				 "« Le compte n'y est pas, {prenom}. Je paie ce qu'on me livre, pas ce qu'on me "
				 "promet — et le temps court toujours. »",
		"choix": [{"id": "ok", "label": "Je vais arranger ça.", "next": "fin"}],
	},
}


def injecter(doc: dict) -> dict:
	"""Pose direction PUIS livraison sur le doc relu. IDEMPOTENT (nœuds écrasés par leur
	référence, choix d'accueil remplacé par son id)."""
	doc = direction.injecter(doc)
	services = doc["services"] = doc.get("services") or {}
	transport = services.setdefault("transport", {})
	transport["noeuds"] = {**(transport.get("noeuds") or {}), **NOEUDS_TRANSPORT}
	noeuds = doc["dialogue"]["noeuds"]
	for nid, contenu in NOEUDS_DIALOGUE.items():
		noeuds[nid] = json.loads(json.dumps(contenu))
	accueil = noeuds[doc["dialogue"].get("noeud_depart") or "accueil"]
	# En tête, comme chez les autres tenanciers : c'est ce qu'on vient faire.
	accueil["choix"] = [json.loads(json.dumps(CHOIX_LIVRAISON))] + [
		c for c in accueil.get("choix") or [] if c.get("id") != CHOIX_LIVRAISON["id"]]
	return doc


def main() -> None:
	doc = next((d for d in direction.charger(SRC_DUMP) if d.get("_id") == DOC_ID), None)
	if not doc:
		raise SystemExit(f"{DOC_ID} absent de {SRC_DUMP} — dump périmé ?")
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump([injecter(doc)], f, ensure_ascii=False, indent=2)
	print(f"{DOC_ID} prend livraison -> {SORTIE}")


if __name__ == "__main__":
	main()

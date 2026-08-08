#!/usr/bin/env python
# dev/gen_escorte_guilde.py
# Ouvre le REGISTRE DES DISPARITIONS au comptoir du Bastion de l'Yonne.
#
# La guilde ne remplace pas les parents : elle les CENTRALISE. Le bloc
# `services.escorte.recherche` dit au moteur de balayer la cité, d'y chercher les maisons qui
# attendent encore un enfant (`escorte.familles_de_la_cite`) et d'en confier une. Le donneur
# est alors le comptoir, la DESTINATION reste la boutique — d'où le +1 de réputation des deux
# côtés (`recompenses.relation_lieux`, dédupliqué par `quetes.recompenser_lieux`).
#
# ⚠️ Le comptoir ne propose QUE les familles écrites (`dev/gen_progeniture.py`) : sans elles,
# `familles_de_la_cite` rend une liste vide et Borin n'a rien à dire. C'est exactement la
# règle voulue — la guilde ne connaît que les disparitions qu'on lui a déclarées.
#
# ⚠️ Pas de `rang_min` : le registre est le canal d'entrée, ouvert à tout inscrit. En poser un
# suffirait à le réserver (fail-closed, comme partout), et le refus serait alors PARLÉ par le
# flag `escorte_rang_insuffisant` — auquel il faudrait ajouter son nœud.
#
# ⚠️ La prime de la guilde est plus généreuse que celle d'un parent (`recompenses` ci-dessous,
# utilisée en défaut quand la famille n'en écrit aucune) : la Guilde a un trésor, l'artisan
# n'a que sa reconnaissance. C'est ce qui donne une raison de passer au comptoir.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON À LA MAIN : `admin_import_bulk` fait un PUT COMPLET.
# Borin porte déjà trois services et dix-sept nœuds (première mission, épreuves de rang, accès
# au bureau du maître) ; retaper son doc, c'est prendre le risque d'en perdre un morceau. On
# le RELIT depuis le dump et on n'y injecte que l'escorte.
#
# Usage : python dev/gen_escorte_guilde.py
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/borin_recherche_escorte_a_importer.json

import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC_DUMP = "jsons/telluris-dump-20260808-073319.json"
SORTIE = "jsons/borin_recherche_escorte_a_importer.json"

PNJ_ID = "pnj:borin_barbe_de_jais"
CITE = "lieu:auxerre"

SERVICE = {
	"recherche": {
		"cite": CITE,
		# Le comptoir recense TOUTES les disparitions de la cité : il en a bien plus souvent
		# une à confier qu'un tenancier isolé (world-var ESCORTE_GUILDE_PROBA = 0.25).
		"proba": 0.25,
		# Défaut appliqué aux familles qui n'écrivent pas leurs propres récompenses.
		"recompenses": {"xp": 30, "cuivre": 500},
	},
	"noeuds": {"accepte": "escorte_acceptee"},
}

# ⚠️ `{protege}`, `{destination}`, `{destinataire}` et `{direction}` ne sont posés que
# lorsqu'une escorte est offerte, en cours, ou à déposer ici : ces quatre nœuds sont tous dans
# ce cas. Un nœud « merci » (hors offre) devrait s'en passer — il n'y en a pas ici, la guilde
# n'a pas à se féliciter d'un enfant qui n'est pas le sien.
NOEUDS = {
	"escorte_propose": {
		"texte": (
			"Borin fait glisser un registre plus mince que les autres et l'ouvre à une page "
			"cornée. « Celui-là, je n'aime pas le tenir. » Il tourne le livre vers vous. "
			"« {protege}. Une famille d'Auxerre, un enfant qui n'est pas rentré. On l'a vu du "
			"côté de {lieu_rencontre}. La Guilde paie ceux qui les ramènent — et elle se "
			"souvient de ceux qui les ramènent vivants. »"
		),
		"choix": [
			{"id": "escorte_details", "label": "Où, exactement ?", "next": "escorte_details"},
			{"id": "escorte_refuser", "label": "Ce n'est pas pour moi.", "next": "accueil"},
		],
	},
	"escorte_details": {
		"texte": (
			"« {direction}. » Le doigt épais s'arrête et ne bouge plus. « Vous rendrez l'enfant "
			"à sa famille, pas à moi : {destinataire}, à : {destination}. Moi, je me contente "
			"d'inscrire que c'est fait — {xp} points d'expérience et {prime} pièces de cuivre "
			"ce jour-là. »"
		),
		"choix": [
			{"id": "escorte_accepter", "label": "Je m'en charge.",
			 "action": {"service": "escorte", "op": "accepter"}},
			{"id": "escorte_refuser", "label": "Laissez-moi y réfléchir.", "next": "accueil"},
		],
	},
	"escorte_acceptee": {
		"texte": (
			"Le nain trace une croix dans la marge et souffle sur l'encre. « C'est noté à votre "
			"nom. » Le sourire revient, un peu plus grave que d'habitude. « Une chose, "
			"{prenom} : {protege} ne se battra pas et ne pourra pas s'enfuir. Ce n'est pas un "
			"colis — ramenez l'enfant, pas son panier. »"
		),
		"choix": [
			{"id": "partir", "label": "J'y vais de ce pas.", "next": "fin"},
			{"id": "retour", "label": "Encore une chose, Borin…", "next": "accueil"},
		],
	},
	"escorte_relance": {
		"texte": (
			"« Toujours en chemin ? » Le registre reste ouvert à la page cornée. « Cherchez "
			"{direction}. Et souvenez-vous : c'est à : {destination} qu'on attend, pas ici. "
			"Une croix dans mon livre ne vaut rien tant que la porte ne s'est pas rouverte. »"
		),
		"choix": [
			{"id": "retour", "label": "J'y retourne.", "next": "accueil"},
			{"id": "fin", "label": "Je m'en occupe.", "next": "fin"},
		],
	},
}

CHOIX_ACCUEIL = [
	{"id": "escorte_offre", "label": "Un avis de recherche, peut-être ?",
	 "next": "escorte_propose", "condition": {"escorte_offerte": True}},
	{"id": "escorte_relance", "label": "Au sujet de {protege}…",
	 "next": "escorte_relance", "condition": {"escorte_en_cours": True}},
]


def charger(chemin: str) -> list:
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def main() -> None:
	base = {d["_id"]: d for d in charger(SRC_DUMP)
			if isinstance(d, dict) and d.get("_id")}
	doc = base.get(PNJ_ID)
	if doc is None:
		raise SystemExit(f"{PNJ_ID} absent de {SRC_DUMP} — dump périmé ?")
	doc = json.loads(json.dumps(doc))            # copie profonde : on ne mute pas le dump

	services = doc.setdefault("services", {})
	services["escorte"] = json.loads(json.dumps(SERVICE))

	dialogue = doc.setdefault("dialogue", {})
	noeuds = dialogue.setdefault("noeuds", {})
	for nid, contenu in NOEUDS.items():
		noeuds[nid] = json.loads(json.dumps(contenu))

	accueil = noeuds.get(dialogue.get("noeud_depart") or "accueil")
	if accueil is None:
		raise SystemExit(f"{PNJ_ID} : pas de nœud d'accueil.")
	# IDEMPOTENT : nos choix sont retirés puis réinsérés JUSTE AVANT la porte de sortie.
	nouveaux = {c["id"] for c in CHOIX_ACCUEIL}
	restants = [c for c in accueil.get("choix") or [] if c.get("id") not in nouveaux]
	sorties = [c for c in restants if c.get("next") == "fin" and not c.get("condition")]
	avant = [c for c in restants if c not in sorties]
	accueil["choix"] = avant + json.loads(json.dumps(CHOIX_ACCUEIL)) + sorties

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump([doc], f, ensure_ascii=False, indent=2)
	print(f"{PNJ_ID} : registre des disparitions ouvert -> {SORTIE}")


if __name__ == "__main__":
	main()

#!/usr/bin/env python
# dev/gen_inscription_capitale.py
# Inscription chez les réceptionnistes des cités qui ont une CAPITALE SŒUR (même `lieu_parent`,
# `sous_categorie: capitale`) : depuis le 11/11 (Auteur), la carte de cette capitale portée au sac
# fait remettre la carte de la ville AU MOINS au rang de la capitale (`chasse.inscrire`). Le texte
# « ici, on commence au premier échelon » devenait faux : il nomme désormais la capitale.
#
# - `inscription_propose` : la phrase du registre local est remplacée ;
# - `inscription_faite`   : « Si vous portez un rang de <capitale>, il est recopié. » (formule des
#   cités lointaines, `gen_guildes_pnj.py`), et l'élision fautive « frappée d'deux fleuves »
#   corrigée au passage (« frappée de deux fleuves », « carte d'Orléans ») dans ce même nœud.
#
# Cités visées : DÉRIVÉES du dump (le PNJ qui porte le don `item:carte_aventurier`, son lieu, la
# ville au-dessus, une capitale de même parent), jamais listées en dur. Une capitale sans parent
# ne compte pas (même règle que `recrutement.carte_valable_dans`).
#
# Relit le dump le plus récent, n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/inscription_capitale_a_importer.json. Rejouable : un nœud déjà corrigé est reconnu et
# sauté ; un PNJ visé dont le texte attendu est introuvable est une ERREUR, jamais un saut muet.
#
# Usage : python dev/gen_inscription_capitale.py [--dump jsons/telluris-dump-….json]

import argparse
import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "inscription_capitale_a_importer.json")

CARTE = "item:carte_aventurier"
ANCIEN_REGISTRE = "Chaque maison tient son registre : ici, on commence au premier échelon."
VOYELLES = "aeiouyhâàéèêëîïôûAEIOUYHÂÀÉÈÊËÎÏÔÛ"


def nom_court(cite_doc: dict) -> str:
	"""« La capitale Lutecia » → « Lutecia » : le libellé de carte dit déjà que c'est une capitale."""
	label = cite_doc.get("label") or cite_doc["_id"].split(":", 1)[1]
	prefixe = "La capitale "
	return label[len(prefixe):] if label.startswith(prefixe) else label


def nouveau_registre(capitale: str) -> str:
	return (f"Chaque maison tient son registre, mais celui de la Guilde de {capitale} fait foi dans tout "
			f"le pays : si vous portez sa carte, montrez-la-moi, et la vôtre portera au moins le même rang. "
			f"Sans elle, on commence ici au premier échelon.")


def recopie(capitale: str) -> str:
	return f"Si vous portez un rang de {capitale}, il est recopié. "


def ville_de(lieu_id, docs):
	"""Ville (catégorie `ville`) qui contient ce lieu, en remontant les `lieu_parent`."""
	vus = set()
	while lieu_id and lieu_id not in vus:
		vus.add(lieu_id)
		doc = docs.get(lieu_id) or {}
		if doc.get("categorie") == "ville":
			return lieu_id
		lieu_id = doc.get("lieu_parent")
	return None


def capitale_soeur(cite_id, docs):
	"""Capitale de même `lieu_parent` que la cité (elle-même exclue), None sinon. Plusieurs :
	ERREUR (le texte n'en nomme qu'une ; aucun cas dans le monde au 11/11)."""
	parent = (docs.get(cite_id) or {}).get("lieu_parent")
	if not parent:
		return None
	soeurs = sorted(d["_id"] for d in docs.values()
					if d.get("type") == "lieu" and d.get("sous_categorie") == "capitale"
					and d.get("lieu_parent") == parent and d["_id"] != cite_id)
	if len(soeurs) > 1:
		raise SystemExit(f"{cite_id} : plusieurs capitales sœurs {soeurs}, le texte n'en nomme qu'une")
	return soeurs[0] if soeurs else None


def lieu_du_pnj(pnj_id, docs):
	for d in docs.values():
		if d.get("type") == "lieu" and any(
				(p.get("character") if isinstance(p, dict) else p) == pnj_id for p in d.get("pnj") or []):
			return d["_id"]
	return None


def corriger_elision(texte: str) -> str:
	"""« frappée d'deux » → « frappée de deux » (« d'un », « d'une » restent) ; « carte de
	Orléans » → « carte d'Orléans »."""
	cle = "frappée d'"
	i = texte.find(cle)
	if i >= 0:
		suite = texte[i + len(cle):]
		if suite[:1] and suite[0] not in VOYELLES:
			texte = texte[:i] + "frappée de " + suite
	cle = "carte de "
	i = texte.find(cle)
	if i >= 0:
		suite = texte[i + len(cle):]
		if suite[:1] and suite[0] in VOYELLES:
			texte = texte[:i] + "carte d'" + suite
	return texte


def corriger(pnj: dict, capitale: str) -> bool:
	"""Mute le doc ; True s'il a changé. ERREUR si un nœud attendu est introuvable."""
	noeuds = (pnj.get("dialogue") or {}).get("noeuds") or {}
	propose, faite = noeuds.get("inscription_propose"), noeuds.get("inscription_faite")
	if not propose or not faite:
		raise SystemExit(f"{pnj['_id']} : nœuds d'inscription introuvables")
	change = False
	neuf = nouveau_registre(capitale)
	if neuf not in propose["texte"]:
		if ANCIEN_REGISTRE not in propose["texte"]:
			raise SystemExit(f"{pnj['_id']} : phrase du registre introuvable dans inscription_propose")
		propose["texte"] = propose["texte"].replace(ANCIEN_REGISTRE, neuf)
		change = True
	texte = corriger_elision(faite["texte"])
	if recopie(capitale) not in texte:
		ancre = "{prenom}. "
		if ancre not in texte:
			raise SystemExit(f"{pnj['_id']} : « {ancre} » introuvable dans inscription_faite")
		texte = texte.replace(ancre, ancre + recopie(capitale), 1)
	if texte != faite["texte"]:
		faite["texte"] = texte
		change = True
	return change


def construire(docs: dict) -> list:
	"""PURE. Docs `pnj:*` réceptionnistes modifiés, `_rev` retiré (réattaché à l'import)."""
	sortie = []
	for d in sorted(docs.values(), key=lambda x: x["_id"]):
		don = ((d.get("services") or {}).get("don") or {}) if d.get("type") == "pnj" else {}
		if don.get("item") != CARTE:
			continue
		cite = ville_de(lieu_du_pnj(d["_id"], docs), docs)
		cap = capitale_soeur(cite, docs) if cite else None
		noeuds = (d.get("dialogue") or {}).get("noeuds") or {}
		if not cap or "inscription_propose" not in noeuds:
			continue   # pas de capitale sœur, ou inscription par mission (Borin)
		if ANCIEN_REGISTRE not in noeuds["inscription_propose"].get("texte", "") \
				and "fait foi dans tout le pays" not in noeuds["inscription_propose"].get("texte", ""):
			continue   # cité lointaine : elle nomme déjà Lutecia (`rang_reconnu`)
		doc = copy.deepcopy(d)
		if corriger(doc, nom_court(docs[cap])):
			doc.pop("_rev", None)
			sortie.append(doc)
	return sortie


def main():
	sys.stdout.reconfigure(encoding="utf-8")
	p = argparse.ArgumentParser(description=__doc__)
	p.add_argument("--dump", default=sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))[-1])
	a = p.parse_args()
	with open(a.dump, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	sortie = construire(docs)
	# Rejeu sur la sortie : idempotent (rien ne doit plus changer).
	rejoue = {**docs, **{d["_id"]: d for d in sortie}}
	if construire(rejoue):
		raise SystemExit("Correctif non idempotent")
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump({"docs": sortie}, f, ensure_ascii=False, indent="\t")
	print(f"{len(sortie)} réceptionniste(s) : {', '.join(d['_id'] for d in sortie)} → {SORTIE}")


if __name__ == "__main__":
	main()

#!/usr/bin/env python
# dev/gen_carcasses_parties.py
# Débite les GROSSES carcasses en portions anatomiques : tête, corps, pattes, queue, ailes —
# puis les portions encore trop lourdes en MORCEAUX.
#
# CE QU'IL CORRIGE. `charge_max = F×5`, soit 250 à 500 kg pour un personnage abouti. Vingt
# carcasses du bestiaire dépassent 100 kg, jusqu'aux 12 tonnes du mammouth : le ramassage en
# combat les REFUSE (« Trop lourd : vous ne pouvez pas porter cette carcasse »), et le plus
# gros gibier du jeu ne rapportait donc RIEN. La découpe rend ce butin divisible.
#
# CE QU'IL ÉCRIT. Trois familles de docs dans UN fichier d'import :
#   1. les carcasses sources, enrichies du champ **`decoupe`** = [{item, quantite, fraction}]
#      — c'est LUI, et lui seul, qui rend un item découpable en jeu
#      (`utils/carcasse.item_est_decoupable`) ;
#   2. un doc `item:<espece>_<partie>` par portion, portant sa propre table **`depecage`** ;
#   3. pour toute portion dont le poids max dépasse le seuil, un doc
#      `item:<espece>_<partie>_morceau`, et sur la portion un `decoupe` vers n morceaux
#      identiques, n choisi pour que CHAQUE morceau pèse moins que le seuil même à poids max.
#
# ⚠️ UNE DÉCOUPE N'EST JAMAIS ANATOMIQUE DEUX FOIS. Une portion et un morceau sont eux aussi
# `sous_categorie: carcasse` (c'est ce qui les fait racheter par la boucherie) : sans garde,
# une relance sur un dump qui contient déjà les portions les re-débitait en « tête d'un
# corps » (`item:aigle_geant_corps_tete`). Tout doc qui porte `portion_de` est donc EXCLU des
# sources ; une portion trop lourde se débite en morceaux, et un morceau ne porte aucun
# `decoupe` (terminal — pas de récursion, cf. le garde-fou de `carcasse.item_est_decoupable`).
#
# ⚠️ LE DÉPEÇAGE D'UNE PORTION EST BAKÉ, PAS DÉRIVÉ À CHAUD. `depecage_carcasse` sait déjà
# lire un champ `depecage` posé sur le doc : on s'en sert pour chaque portion, en y écrivant
# l'intersection « ce que CETTE espèce rend » ∩ « ce que CETTE partie contient ». Un morceau
# reprend la table de sa portion telle quelle — le moteur la remet à l'échelle du poids
# d'instance (`× poids / DEPECAGE_POIDS_REF`). Le prix : **changer `DEPECAGE_TAGS` ne se
# propage pas tout seul** — il faut relancer ce script.
#
# ⚠️ LA TABLE LUE EST LE DÉFAUT DE CODE (`models/character_stats.DEPECAGE_TAGS`), pas celle
# du dump : c'est là que l'auteur édite, et `dev/gen_depecage_tags.py` la pousse vers
# `rules:world_variables`. Lancer les deux dans la foulée garde les trois d'accord.
#
# ⚠️ CONSERVATION DE LA MASSE. Les `fraction` d'un profil somment à 1.0 — vérifié ici, et le
# script SORT EN ERREUR sinon. Une partie qui ne rendrait AUCUNE matière est retirée et sa
# fraction redistribuée. Le `decoupe` d'une portion vers ses morceaux vaut `fraction: 1.0`.
#
# ⚠️ RELANÇABLE À VOLONTÉ, SUR UN DUMP FRAIS. `admin_import_bulk` fait un PUT COMPLET : relire
# un dump périmé écraserait les retouches faites depuis. Sans `--dump`, le script écrit donc
# lui-même un dump frais (`utils/dump.ecrire_dump_frais` — le code des outils de /admin/dev-tools
# et de /admin/exports), ce qui exige CouchDB : à lancer dans le conteneur.
#
# ⚠️ LE FICHIER NE PORTE QUE LE DIFF. Seuls les docs NOUVEAUX ou MODIFIÉS par rapport au dump
# partent à l'import ; un doc déjà à jour est écarté, et sans rien à changer aucun fichier n'est
# écrit. Un doc déjà en base est repris DU DUMP, seuls les champs générés y sont écrasés : une
# clé ajoutée à la main survit à l'import (PUT complet). Relancer juste après un import rend donc
# un lot vide — c'est le signe que la base est à jour.
#
# ⚠️ ORPHELINS. Un doc du dump rattaché (`portion_de`) à une source traitée mais que ce run ne
# produit pas — typiquement les `item:*_corps_tete` d'une ancienne génération — est LISTÉ,
# jamais écrit ni supprimé : à effacer à la main dans /admin/table.
#
# Usage :
#   python dev/gen_carcasses_parties.py                          # dump frais, toutes les carcasses
#   python dev/gen_carcasses_parties.py --dump jsons/telluris-dump-….json
#   python dev/gen_carcasses_parties.py cerf mammouth            # seulement ces espèces (slug)
# Sortie (📥 Importer depuis /admin/dev-tools, ou /admin -> Import en masse) :
#   jsons/carcasses_parties_a_importer.json

import argparse
import json
import math
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from models import character_stats                      # noqa: E402
from utils.marche import depecage_carcasse              # noqa: E402
from utils.commande import TAG_FABRICATION_PREFIXE      # noqa: E402
from utils import dump as dump_util                     # noqa: E402

SORTIE = "jsons/carcasses_parties_a_importer.json"

SUFFIXE_MORCEAU = "_morceau"

# ── Anatomie : ce que CHAQUE partie peut contenir ────────────────────────────────
# Filtre appliqué aux matières que l'espèce rend déjà. Une matière absente de TOUTES les
# parties d'un profil serait PERDUE à la découpe : le script le vérifie et sort en erreur.
# ⚠️ Une matière peut figurer dans plusieurs parties (le cuir vient de partout) — c'est
# voulu, et sans effet de duplication : chaque portion n'en rend qu'au prorata de SON poids.
PARTIES: dict[str, dict] = {
	# Le poison (tag d'espèce `venin`) vient des glandes de la tête et du dard de la queue.
	"tete":   {"libelle": "Tête",  "icon": "💀", "genre": "f",
			   "matieres": ["crane", "yeux", "crocs", "cuir_brut", "os", "item:Poison_de_base"]},
	"corps":  {"libelle": "Corps", "icon": "🥩", "genre": "m",
			   "matieres": ["viande", "os", "sang", "graisse", "boyaux", "foie", "coeur",
							"cuir_brut", "poils", "crins", "plumes", "item:Sang_demon_seche"]},
	"patte":  {"libelle": "Patte", "icon": "🦴", "genre": "f",
			   "matieres": ["viande", "os", "tendons", "griffes", "cuir_brut", "poils"]},
	"bras":   {"libelle": "Bras",  "icon": "🦴", "genre": "m",
			   "matieres": ["viande", "os", "tendons", "griffes", "cuir_brut"]},
	"jambe":  {"libelle": "Jambe", "icon": "🦴", "genre": "f",
			   "matieres": ["viande", "os", "tendons", "griffes", "cuir_brut", "poils"]},
	"aile":   {"libelle": "Aile",  "icon": "🪶", "genre": "f",
			   "matieres": ["plumes", "cuir_brut", "os", "tendons"]},
	"queue":  {"libelle": "Queue", "icon": "🦴", "genre": "f",
			   "matieres": ["cuir_brut", "poils", "crins", "os", "tendons", "item:Poison_de_base"]},
}

# ── Profils anatomiques : (partie, quantité, fraction du poids total) ────────────
# ⚠️ Les fractions d'un profil somment à 1.0 (contrôlé). La fraction est celle de TOUTES les
# pièces de la partie réunies : `pattes ×4 à 0.28` = 7 % du poids par patte.
PROFILS: dict[str, list] = {
	"quadrupede":     [("tete", 1, 0.12), ("corps", 1, 0.52), ("patte", 4, 0.28),
					   ("queue", 1, 0.08)],
	"aile":           [("tete", 1, 0.10), ("corps", 1, 0.45), ("aile", 2, 0.20),
					   ("patte", 2, 0.14), ("queue", 1, 0.11)],
	"humanoide":      [("tete", 1, 0.08), ("corps", 1, 0.50), ("bras", 2, 0.12),
					   ("jambe", 2, 0.30)],
	"humanoide_aile": [("tete", 1, 0.08), ("corps", 1, 0.42), ("aile", 2, 0.16),
					   ("bras", 2, 0.11), ("jambe", 2, 0.23)],
	"arachnide":      [("tete", 1, 0.15), ("corps", 1, 0.45), ("patte", 8, 0.40)],
}

# Profil forcé pour les espèces que les tags décrivent mal. ⚠️ Les tags sont une taxonomie de
# COMBAT (`vol`, `predateur`, `legendaire`), pas d'anatomie : ils ne savent pas qu'une
# araignée a huit pattes ni qu'un homme-arbre n'a pas de queue.
PROFIL_PAR_ESPECE: dict[str, str] = {
	"araignee_geante": "arachnide",
	"homme_arbre":     "humanoide",
}


def seuil() -> float:
	"""Seuil de découpe, relu à chaque appel (variable de monde réglable) : au-delà, un item
	mérite d'être débité, et un morceau pèse toujours MOINS."""
	return float(character_stats.CARCASSE_DECOUPE_POIDS_MIN)


def poids_bornes(poids) -> tuple[float, float]:
	"""(min, max) d'un champ `poids` scalaire ou [min, max]."""
	if isinstance(poids, (list, tuple)) and poids:
		vals = [float(v) for v in poids]
		return min(vals), max(vals)
	try:
		v = float(poids or 0)
	except (TypeError, ValueError):
		v = 0.0
	return v, v


def profil_de(espece: dict) -> str:
	"""Profil anatomique d'une espèce : override explicite, sinon dérivé des tags."""
	slug = (espece.get("_id") or "")[len("espece:"):]
	if slug in PROFIL_PAR_ESPECE:
		return PROFIL_PAR_ESPECE[slug]
	tags = set(espece.get("tags") or [])
	if "humanoide" in tags:
		return "humanoide_aile" if "vol" in tags else "humanoide"
	return "aile" if "vol" in tags else "quadrupede"


def de_ou_d(nom: str) -> str:
	"""« de Cerf » mais « d'Archange » — le libellé d'une portion se lit à voix haute."""
	return "d'" if nom and nom[0].lower() in "aeiouyàâäéèêëîïôöûüh" else "de "


def controler_profils() -> None:
	"""Les fractions somment à 1.0, et aucune matière connue n'est perdue par un profil.

	⚠️ Le second contrôle est le plus important : une matière absente de toutes les parties
	disparaîtrait à la découpe SANS AUCUN SYMPTÔME — le joueur vendrait ses portions et
	constaterait, beaucoup plus tard, qu'il n'obtient plus jamais de cœur."""
	for nom, parties in PROFILS.items():
		total = round(sum(f for (_p, _q, f) in parties), 6)
		if total != 1.0:
			sys.exit(f"ERREUR : profil {nom} : les fractions somment a {total}, pas 1.0")
		couvertes = {m for (p, _q, _f) in parties for m in PARTIES[p]["matieres"]}
		connues = {m for liste in character_stats.DEPECAGE_TAGS.values() for m in liste}
		perdues = sorted(connues - couvertes)
		if perdues:
			sys.exit(f"ERREUR : profil {nom} : matieres perdues a la decoupe : {perdues}")


def est_source(doc: dict) -> bool:
	"""Une carcasse à débiter : `carcasse`, plus lourde que le seuil, et **pas un doc généré**.
	⚠️ `portion_de` exclut portions ET morceaux : c'est la garde qui empêche la « tête d'un
	corps » sur une relance."""
	return (isinstance(doc, dict) and doc.get("type") == "item"
			and doc.get("sous_categorie") == "carcasse"
			and not doc.get("portion_de")
			and poids_bornes(doc.get("poids"))[1] > seuil())


def nb_morceaux(pmax: float) -> int:
	"""Le plus petit n tel que chaque morceau pèse STRICTEMENT moins que le seuil, poids max et
	arrondi au centième compris (99.996 s'arrondirait à 100.0)."""
	s = seuil()
	n = max(1, int(math.floor(pmax / s)) + 1)
	while round(pmax / n, 2) >= s:
		n += 1
	return n


def portions_de(espece: dict) -> list[dict]:
	"""[{partie, quantite, fraction, depecage}] pour une espèce — parties vides retirées et
	fractions RENORMALISÉES, pour que la masse reste conservée."""
	# Quantités de base : au poids de référence, le facteur d'échelle vaut exactement 1.
	base = dict(depecage_carcasse(espece, poids=character_stats.DEPECAGE_POIDS_REF))
	if not base:
		return []
	retenues = []
	for (partie, quantite, fraction) in PROFILS[profil_de(espece)]:
		matieres = [[m, q] for (m, q) in base.items() if m in PARTIES[partie]["matieres"]]
		if not matieres:
			continue
		retenues.append({"partie": partie, "quantite": quantite,
						 "fraction": fraction, "depecage": sorted(matieres)})
	if not retenues:
		return []
	# Renormalisation : une partie retirée ne doit pas faire disparaître sa part de masse.
	total = sum(p["fraction"] for p in retenues)
	for p in retenues:
		p["fraction"] = round(p["fraction"] / total, 4)
	# Le reliquat d'arrondi va sur la plus grosse part (le corps, en pratique).
	plus_grosse = max(retenues, key=lambda p: p["fraction"])
	plus_grosse["fraction"] = round(
		plus_grosse["fraction"] + (1.0 - sum(p["fraction"] for p in retenues)), 4)
	return retenues


def _poids(pi: float, pa: float):
	return [pi, pa] if pa > pi else pi


def morceau_doc(portion: dict, n: int) -> dict:
	"""Le doc morceau d'une portion trop lourde. Même dépeçage, poids / n, AUCUN `decoupe`."""
	pmin, pmax = poids_bornes(portion.get("poids"))
	pi = max(0.01, round(pmin / n, 2))
	pa = max(pi, round(pmax / n, 2))
	libelle = PARTIES[portion["partie"]]["libelle"].lower()
	nom_esp = portion["_nom_espece"]
	liaison = de_ou_d(nom_esp)
	return {
		"_id": portion["_id"] + SUFFIXE_MORCEAU,
		"type": "item",
		"nom": f"Morceau de {libelle} {liaison}{nom_esp}",
		"icon": "🥩",
		"categorie": portion["categorie"],
		"sous_categorie": portion["sous_categorie"],
		"rarete": portion["rarete"],
		"slots": [],
		"poids": _poids(pi, pa),
		"description": f"Morceau de {libelle} {liaison}{nom_esp}, taillé pour être emporté.",
		"tags": sorted(set(portion["tags"]) | {"morceau"}),
		"source_espece": portion["source_espece"],
		"portion_de": portion["_id"],
		"partie": portion["partie"],
		"depecage": [list(e) for e in portion["depecage"]],
	}


def generer(docs: list, filtres=()) -> tuple[list, list, list, list, list]:
	"""Cœur PUR du générateur : `(sortie, resume, ignorees, orphelins, inchanges)`.

	`sortie` = les SEULS docs à mettre en base : nouveaux, ou modifiés par rapport au dump
	(`a_ecrire_depuis`) ;
	`resume` = [(carcasse_id, profil, nb_parties, nb_pieces, nb_morceaux_docs)] — la découpe
	complète, qu'elle soit déjà en base ou non ;
	`orphelins` = ids du dump rattachés à une source traitée que ce run ne produit pas ;
	`inchanges` = ids générés déjà identiques en base, donc absents de `sortie`."""
	par_id = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	carcasses = [d for d in docs if est_source(d)]
	filtres = set(filtres or ())
	if filtres:
		carcasses = [c for c in carcasses if c["_id"][len("item:"):] in filtres]

	s = seuil()
	sortie, resume, ignorees = [], [], []
	sources_traitees: set[str] = set()
	for carc in sorted(carcasses, key=lambda c: c["_id"]):
		slug = carc["_id"][len("item:"):]
		espece = par_id.get(carc.get("source_espece") or ("espece:" + slug))
		if not espece:
			ignorees.append(f"{carc['_id']} : espece introuvable")
			continue
		portions = portions_de(espece)
		if not portions:
			# Esprit, construct : `depecage_carcasse` ne rend rien, il n'y a rien à débiter.
			ignorees.append(f"{carc['_id']} : ne se depece pas")
			continue
		sources_traitees.add(carc["_id"])

		nom_esp = espece.get("nom") or slug
		liaison = de_ou_d(nom_esp)
		pmin, pmax = poids_bornes(carc.get("poids"))
		entrees, nb_morceaux_docs = [], 0
		for p in portions:
			pid = f"item:{slug}_{p['partie']}"
			part = PARTIES[p["partie"]]
			unite = p["fraction"] / p["quantite"]
			pi = max(0.01, round(pmin * unite, 2))
			pa = max(pi, round(pmax * unite, 2))
			portion = {
				"_id": pid,
				"type": "item",
				"nom": f"{part['libelle']} {liaison}{nom_esp}",
				"icon": part["icon"],
				"categorie": "composant",
				# ⚠️ `carcasse` et pas une sous-catégorie neuve : c'est elle qui fait acheter
				# la portion par la boucherie (`besoins_categorie`) ET qui aiguille
				# `_matieres_entrantes` vers le dépeçage.
				"sous_categorie": "carcasse",
				"rarete": carc.get("rarete", "commun"),
				"slots": [],
				"poids": _poids(pi, pa),
				# Accord en genre porté par la table (`genre`) : « Corps … débité »,
				# « Patte … débitée ».
				"description": f"{part['libelle']} {liaison}{nom_esp}, "
							   f"débité{'e' if part['genre'] == 'f' else ''} sur place.",
				# Les tags de l'ESPÈCE suivent la portion (une aile de dragon reste
				# draconique), plus un tag de partie pour filtrer et écrire des recettes.
				"tags": sorted(set(espece.get("tags") or []) | {"partie_" + p["partie"]}),
				"source_espece": espece["_id"],
				"portion_de": carc["_id"],
				"partie": p["partie"],
				"depecage": p["depecage"],
			}
			morceau = None
			if pa > s:
				# Portion encore intransportable : n morceaux identiques, chacun < seuil.
				n = nb_morceaux(pa)
				portion["_nom_espece"] = nom_esp
				morceau = morceau_doc(portion, n)
				del portion["_nom_espece"]
				portion["decoupe"] = [{"item": morceau["_id"], "quantite": n, "fraction": 1.0}]
				portion["decoupe_poids_min"] = s
			sortie.append(portion)
			if morceau:
				sortie.append(morceau)
				nb_morceaux_docs += 1
			entrees.append({"item": pid, "quantite": p["quantite"],
							"fraction": p["fraction"]})

		doc = dict(carc)
		doc["decoupe"] = entrees
		# Seuil BAKÉ sur le doc : le serveur refuse en dessous, le client grise en lisant le
		# même champ, et l'auteur peut le relever espèce par espèce sans toucher au monde.
		doc["decoupe_poids_min"] = s
		sortie.append(doc)
		resume.append((carc["_id"], profil_de(espece), len(entrees),
					   sum(e["quantite"] for e in entrees), nb_morceaux_docs))

	produits = {d["_id"] for d in sortie}
	portions_produites = {d["_id"] for d in sortie if d.get("portion_de") in sources_traitees}
	rattaches = sources_traitees | portions_produites
	orphelins = sorted(d["_id"] for d in par_id.values()
					   if d.get("portion_de") in rattaches and d["_id"] not in produits)

	# Seul ce qui CHANGE la base part à l'import : un doc absent du dump, ou dont un champ
	# généré diffère. Un doc déjà à jour est écarté (`inchanges`).
	a_ecrire, inchanges = [], []
	for genere in sortie:
		existant = par_id.get(genere["_id"])
		doc = a_ecrire_depuis(genere, existant)
		if doc is None:
			inchanges.append(genere["_id"])
		else:
			a_ecrire.append(doc)
	return a_ecrire, resume, ignorees, orphelins, inchanges


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


def a_ecrire_depuis(genere: dict, existant: dict | None):
	"""Le doc à importer pour `genere`, ou None s'il n'y a rien à changer en base.

	⚠️ Un doc DÉJÀ en base part du doc du dump, où l'on n'écrase que les champs générés :
	l'import est un PUT COMPLET (CLAUDE.md §11), et reconstruire le doc à neuf ferait disparaître
	toute clé ajoutée depuis à la main dans /admin/table. `_rev` est ignoré dans la comparaison
	(l'import le réattache depuis la base).

	⚠️ Deux champs générés appartiennent AUSSI à `dev/gen_fabrication_matieres.py`, qui les pose
	sur les parties après coup : les tags `fabrication_*` (qui ouvrent une partie aux armes et
	armures) et une `rarete` relevée selon la dangerosité de l'espèce. On les garde, sinon chaque
	relance de ce script défait l'autre en silence."""
	if not existant:
		return genere
	fusion = dict(existant)
	fusion.update(genere)
	if "tags" in genere:
		fab = [t for t in (existant.get("tags") or []) if str(t).startswith(TAG_FABRICATION_PREFIXE)]
		if fab:
			fusion["tags"] = [t for t in genere["tags"] if t not in fab] + sorted(set(fab))
	if "rarete" in genere and (character_stats.MULT_RARETE.get(existant.get("rarete"), 0)
							   > character_stats.MULT_RARETE.get(genere["rarete"], 0)):
		fusion["rarete"] = existant["rarete"]
	return None if _sans_rev(fusion) == _sans_rev(existant) else fusion


def main() -> None:
	parser = argparse.ArgumentParser(description="Débite les grosses carcasses en portions, "
									 "puis en morceaux de moins de "
									 f"{seuil():g} kg.")
	parser.add_argument("--dump", help="dump à relire (défaut : un dump FRAIS écrit maintenant "
						"depuis CouchDB, dans jsons/)")
	parser.add_argument("especes", nargs="*", help="slugs de carcasse à traiter (défaut : toutes)")
	args = parser.parse_args()

	controler_profils()
	if args.dump:
		source = args.dump
	else:
		try:
			source = dump_util.ecrire_dump_frais(RACINE)
		except Exception as err:
			sys.exit(f"ERREUR : dump frais impossible ({err}). Lancer dans le conteneur, ou "
					 "passer --dump jsons/telluris-dump-….json")
		print(f"dump frais ecrit : {source}")
	chemin_source = source if os.path.isabs(source) else os.path.join(RACINE, source)
	docs = dump_util.charger_docs(chemin_source)
	print(f"source : {source} ({len(docs)} docs)")

	sortie, resume, ignorees, orphelins, inchanges = generer(docs, args.especes)
	if args.especes and not resume:
		sys.exit(f"ERREUR : aucune carcasse > {seuil():g} kg pour {sorted(args.especes)}")

	par_id = {d.get("_id"): d for d in docs if isinstance(d, dict)}
	nouveaux = [d["_id"] for d in sortie if d["_id"] not in par_id]
	modifies = [d["_id"] for d in sortie if d["_id"] in par_id]
	print(f"{len(sortie)} doc(s) a mettre en base : {len(nouveaux)} nouveau(x), "
		  f"{len(modifies)} modifie(s) ; {len(inchanges)} deja a jour, ecarte(s)")
	for oid in modifies:
		print(f"   modifie : {oid}")
	if sortie:
		with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
			json.dump(sortie, f, ensure_ascii=False, indent=2)
			f.write("\n")
		print(f"ecrit {SORTIE}")
	else:
		# Aucun fichier : 📥 Importer (`sortie_fraiche`) refuse alors un fichier plus vieux que le
		# run, au lieu de réimporter un ancien lot.
		print(f"rien a mettre en base : {SORTIE} n'est PAS reecrit")

	print("\ndecoupe complete (en base ou a importer) :")
	for (cid, profil, nb_parties, nb_pieces, nb_m) in resume:
		print(f"   {cid:30} {profil:16} {nb_parties} partie(s), {nb_pieces} piece(s), "
			  f"{nb_m} portion(s) en morceaux")
	for ligne in ignorees:
		print(f"   ignoree : {ligne}")
	if orphelins:
		print(f"\n⚠️ {len(orphelins)} doc(s) du dump rattaché(s) à ces carcasses mais plus produit(s) "
			  "— à supprimer à la main dans /admin/table :")
		for oid in orphelins:
			print(f"   {oid}")


if __name__ == "__main__":
	main()

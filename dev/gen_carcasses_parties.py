#!/usr/bin/env python
# dev/gen_carcasses_parties.py
# Débite les GROSSES carcasses en portions anatomiques : tête, corps, pattes, queue, ailes.
#
# CE QU'IL CORRIGE. `charge_max = F×5`, soit 250 à 500 kg pour un personnage abouti. Vingt
# carcasses du bestiaire dépassent 100 kg, jusqu'aux 12 tonnes du mammouth : le ramassage en
# combat les REFUSE (« Trop lourd : vous ne pouvez pas porter cette carcasse »), et le plus
# gros gibier du jeu ne rapportait donc RIEN. La découpe rend ce butin divisible — on emporte
# la tête et les pattes, on abandonne le corps.
#
# CE QU'IL ÉCRIT. Deux familles de docs dans UN fichier d'import :
#   1. les carcasses sources, enrichies du champ **`decoupe`** = [{item, quantite, fraction}]
#      — c'est LUI, et lui seul, qui rend une carcasse découpable en jeu
#      (`utils/carcasse.item_est_decoupable`) ;
#   2. un doc `item:<espece>_<partie>` par portion, portant sa propre table **`depecage`**.
#
# ⚠️ LE DÉPEÇAGE D'UNE PORTION EST BAKÉ, PAS DÉRIVÉ À CHAUD. `depecage_carcasse` sait déjà
# lire un champ `depecage` posé sur le doc (il servait aux espèces à dépeçage manuel) : on
# s'en sert pour chaque portion, en y écrivant l'intersection « ce que CETTE espèce rend »
# ∩ « ce que CETTE partie contient ». Deux bénéfices : aucun paramètre neuf dans le moteur,
# et un contenu éditable pièce par pièce dans /admin/table. Le prix : **changer
# `DEPECAGE_TAGS` ne se propage pas tout seul aux portions** — il faut relancer ce script.
# C'est le même marché que tous les `dev/gen_*.py`, qui figent des valeurs relues du dump.
#
# ⚠️ LA TABLE LUE EST LE DÉFAUT DE CODE (`models/character_stats.DEPECAGE_TAGS`), pas celle
# du dump : c'est là que l'auteur édite, et `dev/gen_depecage_tags.py` la pousse vers
# `rules:world_variables`. Lancer les deux dans la foulée garde les trois d'accord (code,
# base, portions).
#
# ⚠️ CONSERVATION DE LA MASSE. Les `fraction` d'un profil somment à 1.0 — vérifié ici, et le
# script SORT EN ERREUR sinon. Une partie qui ne rendrait AUCUNE matière est retirée et sa
# fraction redistribuée sur le corps, plutôt que laissée comme un poids mort invendable.
#
# ⚠️ LIMITE ASSUMÉE : une portion reste proportionnelle à sa source. Le corps d'un mammouth
# (0.52 × 5 000 à 12 000 kg) reste intransportable — on prend sa tête et ses pattes, le reste
# pourrit sur place. C'est le comportement voulu ; pour le changer il faudrait une seconde
# découpe (portion → quartiers), qui n'existe pas.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc. On RELIT donc
# les carcasses depuis le dump et on n'y injecte que `decoupe` : régénérer est idempotent.
#
# Usage :
#   python dev/gen_carcasses_parties.py                # toutes les carcasses > seuil
#   python dev/gen_carcasses_parties.py cerf mammouth  # seulement ces espèces (slug)
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/carcasses_parties_a_importer.json

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from models import character_stats                      # noqa: E402
from utils.marche import depecage_carcasse              # noqa: E402

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260831-122931.json"

SORTIE = "jsons/carcasses_parties_a_importer.json"

# ── Anatomie : ce que CHAQUE partie peut contenir ────────────────────────────────
# Filtre appliqué aux matières que l'espèce rend déjà. Une matière absente de TOUTES les
# parties d'un profil serait PERDUE à la découpe : le script le vérifie et sort en erreur.
# ⚠️ Une matière peut figurer dans plusieurs parties (le cuir vient de partout) — c'est
# voulu, et sans effet de duplication : chaque portion n'en rend qu'au prorata de SON poids.
PARTIES: dict[str, dict] = {
	"tete":   {"libelle": "Tête",  "icon": "💀", "genre": "f",
			   "matieres": ["crane", "yeux", "crocs", "cuir_brut", "os"]},
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
			   "matieres": ["cuir_brut", "poils", "crins", "os", "tendons"]},
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

# Seuil : au-delà, la carcasse mérite d'être débitée. Lu dans les variables de monde pour
# qu'il n'y ait qu'UNE valeur à changer (le client s'en sert pour son libellé).
SEUIL = float(character_stats.CARCASSE_DECOUPE_POIDS_MIN)


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


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


def portions_de(espece: dict, carcasse: dict) -> list[dict]:
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


def main() -> None:
	controler_profils()
	filtres = set(sys.argv[1:])
	docs = charger(SRC_DUMP)
	par_id = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}

	carcasses = [
		d for d in docs
		if isinstance(d, dict) and d.get("type") == "item"
		and d.get("sous_categorie") == "carcasse"
		and poids_bornes(d.get("poids"))[1] > SEUIL
	]
	if filtres:
		carcasses = [c for c in carcasses if c["_id"][len("item:"):] in filtres]
		if not carcasses:
			sys.exit(f"ERREUR : aucune carcasse > {SEUIL} kg pour {sorted(filtres)}")

	sortie, resume, ignorees = [], [], []
	for carc in sorted(carcasses, key=lambda c: c["_id"]):
		slug = carc["_id"][len("item:"):]
		espece = par_id.get(carc.get("source_espece") or ("espece:" + slug))
		if not espece:
			ignorees.append(f"{carc['_id']} : espece introuvable")
			continue
		portions = portions_de(espece, carc)
		if not portions:
			# Esprit, construct : `depecage_carcasse` ne rend rien, il n'y a rien à débiter.
			ignorees.append(f"{carc['_id']} : ne se depece pas")
			continue

		nom_esp = espece.get("nom") or slug
		liaison = de_ou_d(nom_esp)
		pmin, pmax = poids_bornes(carc.get("poids"))
		entrees = []
		for p in portions:
			pid = f"item:{slug}_{p['partie']}"
			part = PARTIES[p["partie"]]
			unite = p["fraction"] / p["quantite"]
			pi = max(0.01, round(pmin * unite, 2))
			pa = max(pi, round(pmax * unite, 2))
			sortie.append({
				"_id": pid,
				"type": "item",
				"nom": f"{part['libelle']} {liaison}{nom_esp}",
				"icon": part["icon"],
				"categorie": "composant",
				# ⚠️ `carcasse` et pas une sous-catégorie neuve : c'est elle qui fait acheter
				# la portion par la boucherie (`besoins_categorie`) ET qui aiguille
				# `_matieres_entrantes` vers le dépeçage. Une clé neuve demanderait une
				# recette et un intrant de plus par métier.
				"sous_categorie": "carcasse",
				"rarete": carc.get("rarete", "commun"),
				"slots": [],
				"poids": [pi, pa] if pa > pi else pi,
				# Accord en genre porté par la table (`genre`) : « Corps … débité »,
				# « Patte … débitée ». Un libellé faux se voit à chaque ligne d'inventaire.
				"description": f"{part['libelle']} {liaison}{nom_esp}, "
							   f"débité{'e' if part['genre'] == 'f' else ''} sur place.",
				# Les tags de l'ESPÈCE suivent la portion (une aile de dragon reste
				# draconique), plus un tag de partie pour filtrer et écrire des recettes.
				"tags": sorted(set(espece.get("tags") or []) | {"partie_" + p["partie"]}),
				"source_espece": espece["_id"],
				"portion_de": carc["_id"],
				"partie": p["partie"],
				"depecage": p["depecage"],
			})
			entrees.append({"item": pid, "quantite": p["quantite"],
							"fraction": p["fraction"]})

		doc = dict(carc)
		doc["decoupe"] = entrees
		# Seuil BAKÉ sur le doc : le serveur refuse en dessous, le client grise en lisant le
		# même champ, et l'auteur peut le relever espèce par espèce sans toucher au monde.
		doc["decoupe_poids_min"] = SEUIL
		sortie.append(doc)
		resume.append((carc["_id"], profil_de(espece), len(entrees),
					   sum(e["quantite"] for e in entrees)))

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")

	print(f"ecrit {SORTIE}")
	print(f"   {len(sortie)} doc(s) : {len(resume)} carcasse(s) + "
		  f"{len(sortie) - len(resume)} portion(s)")
	for (cid, profil, nb_parties, nb_pieces) in resume:
		print(f"   {cid:30} {profil:16} {nb_parties} partie(s), {nb_pieces} piece(s)")
	for ligne in ignorees:
		print(f"   ignoree : {ligne}")


if __name__ == "__main__":
	main()

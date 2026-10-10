#!/usr/bin/env python
# dev/gen_spec_caves_negoces.py
# Ajout de CAVES (Rhemi 4, Auxerre 3, Chartres 2, Lutecia 6) et de NÉGOCES (Lutecia 3) à des cités
# déjà peuplées : écrit la spec de chaque cité, la valide par `dev/gen_magasins.construire` et
# produit UN import pour les quatre cités.
#
#   python dev/gen_spec_caves_negoces.py
#     → jsons/specs/<cité>_caves_negoces_spec.json   (rejouables sur /admin/lieux)
#     → jsons/caves_negoces_a_importer.json          (lieux + connexions, carte d'import de /admin)
#   puis, pour les images : python dev/gen_images_magasins.py preparer --cite <cité> --lot jsons/caves_negoces_a_importer.json
#
# ⚠️ CASES : celles de `dev/gen_spec_rhemi.py` — dedans des portes intérieures (Rhemi, Lutecia),
# enceinte relevée (Chartres) —, hors de tout seuil déjà posé, étalées LOIN des seuils existants.
# Auxerre n'a qu'une porte intérieure (non bornable) : ses caves prennent des cases qui portent
# DÉJÀ un seuil de magasin (précédent `dev/gen_magasins_auxerre.py`), jamais celui d'une cave.
#
# ⚠️ TENANCIER : lignée tirée à chances ÉGALES entre les cinq Lignées (consigne de l'auteur), nom du
# répertoire du recrutement, `portrait` = `marchand_<race>_<m|f>_<métier>01.jpg` — un nom VOULU que
# `gen_images_magasins` lit pour la lignée et que son `appliquer` remplace par le portrait généré.
# Façade provisoire : `cave_europe01.jpg` (pas encore dessinée) / `negoce_europe01.jpg`.
#
# ⚠️ REFUS GLOBAL (code 1, aucun fichier) si une cité échoue, ou si `pnj:marchand_cave` manque au
# dump (lot dev/gen_specialites_chartres_rhemi.py pas encore importé : pas de tenancier).
# Tirages seedés : relancer sur le même dump redonne les mêmes fichiers.

import json
import os
import random
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
	sys.path.insert(0, RACINE)

import gen_magasins  # noqa: E402
import gen_spec_rhemi as spec_rhemi  # noqa: E402
from utils import enseignes  # noqa: E402

SORTIE = os.path.join("jsons", "caves_negoces_a_importer.json")
DOSSIER_SPECS = os.path.join("jsons", "specs")
GRAINE = 20261010

LOT = {
	"lieu:rhemi": {"cave": 4},
	"lieu:auxerre": {"cave": 3},
	"lieu:chartres": {"cave": 2},
	"lieu:lutecia": {"cave": 6, "negociant": 3},
}
# Cités sans enceinte bornable : on pose sur les seuils de magasins existants.
SUR_SEUILS = {"lieu:auxerre"}

LIGNEES = ["humain", "elfe", "nain", "hobbit", "ogre"]
IMAGE_PROVISOIRE = {"cave": "cave_europe01.jpg", "negociant": "negoce_europe01.jpg"}


def _est_boutique(lieu: dict) -> bool:
	"""Un lieu tenu par un marchand (ni porte, ni grotte, ni pays)."""
	return any(str((e or {}).get("character") or "").startswith("pnj:marchand_")
			   for e in (lieu.get("pnj") or []) if isinstance(e, dict))


def seuils_de(docs: list, cite_id: str, par_id: dict, boutiques: bool = False) -> dict:
	"""{(x, y): {catégories}} des connexions de la cité (portes comprises, catégorie None) ;
	`boutiques` : seulement les seuils de magasins tenus par un marchand."""
	out = {}
	for c in docs:
		if not isinstance(c, dict) or c.get("type") != "connection":
			continue
		nodes = c.get("nodes") or []
		ici = next((n for n in nodes if n.get("lieu") == cite_id), None)
		la = next((n for n in nodes if n.get("lieu") != cite_id), None)
		if ici and la and boutiques and not _est_boutique(par_id.get(la.get("lieu")) or {}):
			continue
		if ici and la and isinstance(ici.get("pos"), list) and len(ici["pos"]) == 2:
			out.setdefault(tuple(ici["pos"]), set()).add((par_id.get(la.get("lieu")) or {}).get("categorie"))
	return out


def candidats_de(docs: list, cite_id: str, par_id: dict, metiers: set, enceinte=None) -> tuple:
	"""PURE. (cases candidates, seuils existants à fuir) pour `cite_id`."""
	cite = par_id[cite_id]
	cells = cite.get("cells") or []
	seuils = seuils_de(docs, cite_id, par_id)
	if cite_id in SUR_SEUILS:
		boutiques = seuils_de(docs, cite_id, par_id, boutiques=True)
		cases = [p for p, cats in boutiques.items()
				 if not (seuils.get(p, set()) & metiers)
				 and p[1] < len(cells) and p[0] < len(cells[p[1]]) and cells[p[1]][p[0]] == 1]
		if not cases:
			return [], None
		# Moitié la plus centrale : `etaler` pousse sinon les boutiques aux seuils les plus excentrés.
		cx = sum(c[0] for c in cases) / len(cases)
		cy = sum(c[1] for c in cases) / len(cases)
		cases.sort(key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0]))
		return sorted(cases[:max(1, len(cases) // 2)], key=lambda c: (c[1], c[0])), None
	if enceinte:
		interieur = spec_rhemi.cases_dans_enceinte(cells, enceinte)
	else:
		portes = _portes_interieures(docs, cite_id)
		interieur = spec_rhemi.cases_interieures(cells, portes)
	return [c for c in interieur if c not in seuils], sorted(seuils)


def _portes_interieures(docs: list, cite_id: str) -> list:
	portes = []
	for c in docs:
		if not isinstance(c, dict) or c.get("type") != "connection":
			continue
		nodes = c.get("nodes") or []
		ici = next((n for n in nodes if n.get("lieu") == cite_id), None)
		la = next((n for n in nodes if n.get("lieu") != cite_id), None)
		if ici and la and str(la.get("lieu", "")).endswith("_interieur"):
			portes.append(tuple(ici["pos"]))
	return portes


def labels_varies(metier: str, n: int, cite_id: str, exclus: set, pris_lot: set, rng) -> list:
	"""PURE (`rng` injecté). `n` enseignes de `enseignes.tirer_labels`, en évitant de redire dans
	le lot une tournure ou un toponyme déjà servis (`pris_lot`, mis à jour) — quatre « … du
	Palais » d'affilée sinon. Repli sur le tirage brut quand la variété s'épuise."""
	toponymes = sorted(enseignes.toponymes_de(cite_id), key=len, reverse=True)
	tous = enseignes.tirer_labels(metier, 10 ** 4, cite_id, exclus=exclus, rand_fn=rng.shuffle)
	tous = [l for l in tous if any(l.endswith(" " + t) for t in toponymes)] or tous

	def morceaux(label):
		t = next((t for t in toponymes if label.endswith(" " + t)), "")
		return {"T:" + label[:len(label) - len(t)].strip(), "P:" + t}

	choisis = []
	for label in tous:
		if len(choisis) == n:
			break
		if not (morceaux(label) & pris_lot):
			choisis.append(label)
			pris_lot |= morceaux(label)
	for label in tous:
		if len(choisis) == n:
			break
		if label not in choisis:
			choisis.append(label)
	return choisis


def construire_spec(docs: list, cite_id: str, metiers: dict, repertoire: dict, enceinte=None,
					graine: int = GRAINE) -> tuple:
	"""PURE. (spec, rapport) des boutiques `metiers` ({catégorie: nombre}) à ajouter à `cite_id`."""
	par_id = {d.get("_id"): d for d in docs if isinstance(d, dict) and d.get("_id")}
	if cite_id not in par_id or not par_id[cite_id].get("cells"):
		raise SystemExit(f"ERREUR : {cite_id} absent du dump ou sans grille.")
	candidats, deja = candidats_de(docs, cite_id, par_id, set(metiers), enceinte)
	total = sum(metiers.values())
	cases = spec_rhemi.etaler(candidats, total, deja)
	rng = random.Random(f"{graine}|{cite_id}")
	rng.shuffle(cases)

	labels_pris = {d.get("label") for d in docs if isinstance(d, dict) and d.get("type") == "lieu"}
	noms_pris = {e.get("nom") for d in docs if isinstance(d, dict) and isinstance(d.get("pnj"), list)
				 for e in d["pnj"] if isinstance(e, dict) and e.get("nom")}
	magasins, rapport = [], []
	pris_lot = set()
	for metier in sorted(metiers):
		for label in labels_varies(metier, metiers[metier], cite_id, labels_pris, pris_lot, rng):
			labels_pris.add(label)
			race, sexe = rng.choice(LIGNEES), rng.choice("MF")
			nom = spec_rhemi.tirer_nom(race, sexe, rng, repertoire, noms_pris)
			x, y = cases.pop()
			portrait = f"marchand_{race}_{sexe.lower()}_{metier}01.jpg"
			magasins.append({"categorie": metier, "label": label, "image": IMAGE_PROVISOIRE[metier],
							 "pos": [x, y], "nom": nom, "portrait": portrait})
			rapport.append(f"  {metier:10} {label:40} [{x:2},{y:2}]  {nom} ({race} {sexe})")
	borne = "seuils de magasins existants" if cite_id in SUR_SEUILS else (
		"enceinte relevée" if enceinte else "portes intérieures")
	rapport.insert(0, f"{cite_id} — {borne}, {len(candidats)} cases candidates, {len(magasins)} boutiques")
	return {"cite": cite_id, "magasins": magasins}, rapport


def main() -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = spec_rhemi._dump_le_plus_recent()
	docs = spec_rhemi.charger(source)
	if not any(isinstance(d, dict) and d.get("_id") == "pnj:marchand_cave" for d in docs):
		print("✗ pnj:marchand_cave absent du dump — importer jsons/specialites_chartres_rhemi_a_importer.json "
			  "puis exporter un dump. AUCUN fichier écrit.")
		return 1
	# Idempotence : le lot exclut les labels et cases déjà en base — relancé APRÈS import, il
	# tirerait 18 boutiques DE PLUS et écraserait l'import (pris le 10/10). Lot en base ⇒ rien.
	chemin_import = os.path.join(RACINE, SORTIE)
	if os.path.exists(chemin_import):
		ids = {d.get("_id") for d in docs if isinstance(d, dict)}
		with open(chemin_import, encoding="utf-8") as f:
			lieux_lot = [d["_id"] for d in json.load(f) if d.get("type") == "lieu"]
		if lieux_lot and all(i in ids for i in lieux_lot):
			print(f"relu {os.path.relpath(source, RACINE)} : les {len(lieux_lot)} boutiques de {SORTIE} "
				  "sont déjà en base — AUCUN fichier écrit.")
			return 0
	repertoire = spec_rhemi.constantes_source(
		os.path.join(RACINE, "utils", "recrutement.py"),
		{"PRENOMS", "NOMS", "PRENOM_RACE_MUTUALISEE", "PRENOM_MUTUALISE_PROBA"})
	images = set(os.listdir(gen_magasins.DOSSIER_IMAGES))

	specs, sortie, erreurs, rapports = {}, [], [], []
	for cite_id, metiers in LOT.items():
		enceinte = (spec_rhemi.VILLES.get(cite_id) or {}).get("enceinte")
		spec, rapport = construire_spec(docs, cite_id, metiers, repertoire, enceinte)
		res = gen_magasins.construire(docs, spec, images)
		erreurs += [f"{cite_id} : {e}" for e in res["erreurs"]]
		erreurs += [f"{cite_id} : {a}" for a in res["avertissements"]]
		sans_pnj = [d["_id"] for d in res["docs"] if d.get("type") == "lieu" and "pnj" not in d]
		erreurs += [f"{cite_id} : {i} sans tenancier" for i in sans_pnj]
		specs[cite_id] = spec
		sortie += res["docs"]
		rapports.append(rapport)

	print(f"relu {os.path.relpath(source, RACINE)}")
	if erreurs:
		print(f"✗ {len(erreurs)} refus — AUCUN fichier écrit :")
		for e in erreurs:
			print("  · " + e)
		return 1
	os.makedirs(os.path.join(RACINE, DOSSIER_SPECS), exist_ok=True)
	for cite_id, spec in specs.items():
		chemin = os.path.join(RACINE, DOSSIER_SPECS, f"{cite_id.split(':', 1)[-1]}_caves_negoces_spec.json")
		with open(chemin, "w", encoding="utf-8") as f:
			json.dump(spec, f, ensure_ascii=False, indent="\t")
			f.write("\n")
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	for rapport in rapports:
		for ligne in rapport:
			print(ligne)
	print(f"{len(sortie) // 2} boutiques ({len(sortie)} docs avec les connexions) → {SORTIE.replace(os.sep, '/')}")
	return 0


if __name__ == "__main__":
	sys.exit(main())

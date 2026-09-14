"""Contrôle la proposition `docs/competences_vocations_3_6_10.md`.

    python dev/check_competences_doc.py [chemin/vers/le/document.md]

Sortie : un rapport, et le code 1 au premier invariant violé.

⚠️ POURQUOI un vérificateur plutôt qu'une relecture. `_bonus_dict` (utils/sorts.py) est une
LISTE BLANCHE : une clé d'effet inventée (`crit`, `actions`, `resistance_feu`…) ne lève aucune
erreur, elle DISPARAÎT à la normalisation. Un document de 120 compétences relu à l'œil laisse
passer ce genre de clé sans le moindre symptôme — jusqu'à l'import, où la compétence est en
base et ne fait rien. Le seul contrôle qui vaille est donc de faire normaliser chaque bloc par
le moteur RÉEL, puis de comparer ce qui entre et ce qui sort.

Les huit invariants contrôlés sont énoncés dans le document lui-même (§ « Invariants contrôlés
par dev/check_competences_doc.py ») — ce fichier en est l'exécution, pas la source.

Ce script ne lit ni n'écrit la base : il ne fait que relire un fichier markdown committé.
"""

import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.competences import (  # noqa: E402
	competence_utilisable_combat,
	competence_utilisable_exploration,
	est_active,
	est_passive,
	normaliser_competence,
)
from utils.sorts import _bonus_dict  # noqa: E402

DOC_DEFAUT = os.path.join(RACINE, "docs", "competences_vocations_3_6_10.md")
DOSSIER_JSONS = os.path.join(RACINE, "jsons")

NIVEAUX_ATTENDUS = (3, 6, 10)
# Champs qui n'ont aucun effet sur une passive : les y laisser est trompeur à la relecture
# (on croit lire une active) sans que le moteur ne s'en plaigne jamais.
CHAMPS_ACTIFS_SEULEMENT = ("cout_pm", "cible", "jet", "portee")
# Clés de PREMIER NIVEAU que `normaliser_competence` sait lire. Même piège que les clés
# d'effet : un `magie` ou un `composants` recopié depuis un doc de sort ne lève rien et
# disparaît — la compétence part en base amputée de ce que son auteur croyait y mettre.
CHAMPS_DOC = ("_id", "_rev", "type", "nom", "icon", "description", "vocation", "niveau",
			  "mode", "cout_pm", "cible", "jet", "portee", "effets", "condition", "animation")

BLOC_JSON = re.compile(r"^```json\n(.*?)\n```", re.MULTILINE | re.DOTALL)


def charger_blocs(chemin):
	"""Chaque bloc ```json``` du document, avec son numéro de ligne de départ."""
	texte = open(chemin, encoding="utf-8").read()
	blocs = []
	for m in BLOC_JSON.finditer(texte):
		ligne = texte.count("\n", 0, m.start()) + 1
		blocs.append((ligne, m.group(1)))
	return blocs


def vocations_du_dump():
	"""Les ids de `rules:vocations` et les `_id` des competence:* du dump le plus récent.

	Le dump sert de RÉFÉRENTIEL, pas de source : il dit quelles vocations existent et quels
	`_id` sont déjà pris. Absent, le contrôle correspondant est sauté (annoncé), pas fatal —
	ce script doit tourner sur un poste sans dump comme sur un poste à jour.
	"""
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	) if os.path.isdir(DOSSIER_JSONS) else []
	if not dumps:
		return None, None, None
	chemin = os.path.join(DOSSIER_JSONS, dumps[-1])
	docs = json.load(open(chemin, encoding="utf-8")).get("docs") or []
	vocations = set()
	existantes = set()
	for d in docs:
		if d.get("_id") == "rules:vocations":
			vocations = {str(v.get("id")) for v in (d.get("value") or [])}
		elif str(d.get("_id", "")).startswith("competence:"):
			existantes.add(d["_id"])
	return dumps[-1], vocations, existantes


def main():
	chemin = sys.argv[1] if len(sys.argv) > 1 else DOC_DEFAUT
	if not os.path.exists(chemin):
		raise SystemExit(f"ERREUR : document introuvable — {chemin}")

	erreurs = []
	blocs = charger_blocs(chemin)
	if not blocs:
		raise SystemExit(f"ERREUR : aucun bloc ```json``` dans {chemin}")

	dump, vocations_connues, ids_existants = vocations_du_dump()

	docs = []
	for ligne, brut in blocs:
		try:
			doc = json.loads(brut)
		except json.JSONDecodeError as exc:
			erreurs.append(f"ligne {ligne} : JSON invalide — {exc}")
			continue
		docs.append((ligne, doc))

	vus = {}
	par_vocation = {}

	for ligne, doc in docs:
		cid = doc.get("_id", "<sans _id>")
		prefixe = f"ligne {ligne} ({cid})"

		# (1) le moteur accepte-t-il le doc, et sans perdre de clé ?
		comp = normaliser_competence(doc)
		if comp is None:
			erreurs.append(f"{prefixe} : rejeté par normaliser_competence "
						   f"(type ≠ 'competence' ou vocation absente)")
			continue

		for cle in doc:
			if cle not in CHAMPS_DOC:
				erreurs.append(f"{prefixe} : champ `{cle}` INCONNU de normaliser_competence — "
							   f"il disparaîtrait silencieusement à la lecture")

		effets_ecrits = doc.get("effets") or {}
		effets_lus = _bonus_dict(effets_ecrits)
		for cle in effets_ecrits:
			if cle not in effets_lus:
				erreurs.append(f"{prefixe} : clé d'effet `{cle}` INCONNUE du moteur — "
							   f"elle disparaîtrait silencieusement à l'import")
		for cle, valeur in (effets_ecrits.get("buffs") or {}).items():
			if cle not in ("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"):
				erreurs.append(f"{prefixe} : buff sur `{cle}` — caractéristique inconnue")
			elif cle == "V" and abs(int(valeur)) > 5:
				erreurs.append(f"{prefixe} : buff V de {valeur} — V est à l'échelle 1-10, "
							   f"|delta| > 5 immobilise ou catapulte la cible")

		# (2) unicité, et pas de collision avec ce qui est déjà en base
		if cid in vus:
			erreurs.append(f"{prefixe} : `_id` en double (déjà ligne {vus[cid]})")
		vus[cid] = ligne
		if ids_existants is not None and cid in ids_existants:
			erreurs.append(f"{prefixe} : `_id` DÉJÀ EN BASE — l'import l'écraserait "
						   f"(admin_import_bulk fait un PUT complet)")

		# (4) référentiel
		if vocations_connues and comp["vocation"] not in vocations_connues:
			erreurs.append(f"{prefixe} : vocation `{comp['vocation']}` absente de rules:vocations")
		if comp["niveau"] not in NIVEAUX_ATTENDUS:
			erreurs.append(f"{prefixe} : niveau {comp['niveau']} hors de {NIVEAUX_ATTENDUS}")
		par_vocation.setdefault(comp["vocation"], []).append(comp)

		if est_passive(comp):
			# (5) une passive conditionnée n'est lue QUE pour sa furtivite
			if comp["condition"]:
				autres = {k: v for k, v in effets_lus.items()
						  if k != "furtivite" and v not in ("", 0, {}, None)}
				if autres:
					erreurs.append(f"{prefixe} : passive avec `condition` portant "
								   f"{sorted(autres)} — seule `furtivite` serait lue "
								   f"(bonus_passifs exclut les passives conditionnées)")
				if not effets_lus.get("furtivite"):
					erreurs.append(f"{prefixe} : passive avec `condition` sans `furtivite` "
								   f"— elle n'aurait aucun effet")
			# (8) champs d'active sur une passive
			for champ in CHAMPS_ACTIFS_SEULEMENT:
				if champ in doc:
					erreurs.append(f"{prefixe} : passive portant `{champ}` — sans effet, "
								   f"et trompeur à la relecture")
		elif est_active(comp):
			combat = competence_utilisable_combat(comp)
			exploration = competence_utilisable_exploration(comp)
			# (7) utilisable quelque part
			if not combat and not exploration:
				erreurs.append(f"{prefixe} : active inutilisable en combat ET en exploration")
			# (6) une offensive doit porter des dégâts ou une part durative
			if comp["cible"] == "ennemi" and not combat:
				erreurs.append(f"{prefixe} : active `ennemi` sans `degats` ni part durative "
							   f"— resolve_action la refuserait")

	# (3) six entrées par vocation : une passive + une active par palier
	for voc, comps in sorted(par_vocation.items()):
		if len(comps) != 6:
			erreurs.append(f"vocation `{voc}` : {len(comps)} entrées au lieu de 6")
		for niveau in NIVEAUX_ATTENDUS:
			palier = [c for c in comps if c["niveau"] == niveau]
			passives = [c for c in palier if est_passive(c)]
			actives = [c for c in palier if est_active(c)]
			if len(passives) != 1 or len(actives) != 1:
				erreurs.append(f"vocation `{voc}` niveau {niveau} : "
							   f"{len(passives)} passive(s) et {len(actives)} active(s), "
							   f"attendu 1 et 1")
	if vocations_connues:
		manquantes = sorted(vocations_connues - set(par_vocation))
		if manquantes:
			erreurs.append(f"vocations sans aucune entrée : {', '.join(manquantes)}")

	# ── Rapport ──────────────────────────────────────────────────────────────────
	print(f"Document  : {os.path.relpath(chemin, RACINE)}")
	print(f"Référentiel : {dump or 'AUCUN DUMP — contrôles de vocation et de collision sautés'}")
	print(f"Blocs lus : {len(docs)} · vocations couvertes : {len(par_vocation)}")
	passives = sum(1 for _, d in docs if (d.get("mode") == "passive"))
	print(f"Répartition : {passives} passives / {len(docs) - passives} actives")

	if erreurs:
		print(f"\n{len(erreurs)} PROBLÈME(S) :")
		for e in erreurs:
			print(f"  - {e}")
		return 1
	print("\nOK — les huit invariants tiennent.")
	return 0


if __name__ == "__main__":
	sys.exit(main())

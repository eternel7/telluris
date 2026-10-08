"""Contrôle la proposition `docs/competences_vocations_3_6_10.md`.

    python dev/check_competences_doc.py [chemin/vers/le/document.md]

Sortie : un rapport, et le code 1 au premier invariant violé.

⚠️ POURQUOI un vérificateur plutôt qu'une relecture. `_bonus_dict` (utils/sorts.py) est une
LISTE BLANCHE : une clé d'effet inventée (`crit`, `actions`, `resistance_feu`…) ne lève aucune
erreur, elle DISPARAÎT à la normalisation. Un document de 120 compétences relu à l'œil laisse
passer ce genre de clé sans le moindre symptôme — jusqu'à l'import, où la compétence est en
base et ne fait rien. Le seul contrôle qui vaille est donc de faire normaliser chaque bloc par
le moteur RÉEL, puis de comparer ce qui entre et ce qui sort.

Les treize invariants contrôlés sont énoncés dans le document lui-même (§ « Invariants contrôlés
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
	action_piege as competence_action_piege,
	competence_utilisable_combat,
	est_aura,
	competence_utilisable_exploration,
	est_active,
	est_passive,
	normaliser_competence,
)
from utils.sorts import (  # noqa: E402
	CARACTS_FORMULE, INCANTATION_PA_MAX, MAINTIEN_PM_MAX, _bonus_dict,
	capacite_utilisable_combat, effets_agissent_sur_cible, est_formule, evaluer_formule,
)
from utils.zones_effet import normaliser_zone  # noqa: E402

DOC_DEFAUT = os.path.join(RACINE, "docs", "competences_vocations_3_6_10.md")
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
# L'import que `dev/gen_competences_3_6_10.py` tire de CE document : il n'est pas un
# référentiel — le relire ferait de chaque bloc une collision avec lui-même.
IMPORT_DU_DOC = "competences_vocations_3_6_10_a_importer.json"

NIVEAUX_ATTENDUS = (3, 6, 10)
# Champs qui n'ont aucun effet sur une passive : les y laisser est trompeur à la relecture
# (on croit lire une active) sans que le moteur ne s'en plaigne jamais.
CHAMPS_ACTIFS_SEULEMENT = ("cout_pm", "cible", "jet", "portee")
# Clés de PREMIER NIVEAU que `normaliser_competence` sait lire. Même piège que les clés
# d'effet : un `magie` ou un `composants` recopié depuis un doc de sort ne lève rien et
# disparaît — la compétence part en base amputée de ce que son auteur croyait y mettre.
CHAMPS_DOC = ("_id", "_rev", "type", "nom", "icon", "description", "vocation", "famille",
			  "niveau", "mode", "cout_pm", "maintien", "incantation", "sensibilite_charge",
			  "cible", "jet", "portee", "zone", "effets", "condition", "animation",
			  "animation_zone", "pose_piege")
# Clés que le moteur lit sur un SORT mais jamais sur une compétence. `_bonus_dict` les
# normalise (elles ne « disparaissent » donc pas : le contrôle n°1 ne les verrait pas), et
# `competence_utilisable_combat` en accepte même deux — mais AUCUNE branche de
# `resolve_action` ne les résout côté compétence. Une compétence qui en porte une part en
# base, s'utilise sans erreur, et ne fait rien. Vérifié en exécutant le moteur.
# ⚠️ `cout_pv`, `saut` et `lien_vie` ONT ÉTÉ OUVERTS aux compétences (chokepoint de
# lancement partagé `combat._lancer_capacite`), ainsi qu'`incantation` : ils ne figurent
# donc plus ici. Ne restent inertes que les bonus de COMPOSANT — une compétence n'en a pas,
# et `sorts.doc_effectif` ne les lira jamais sur elle.
EFFETS_INERTES_SUR_COMPETENCE = {
	# ⚠️ `canalisation` est déclarée par `_bonus_dict` mais recopiée par AUCUN des deux
	# `empiler_effet_*` (ni sort, ni compétence) et pas agrégée par `bonus_passifs` :
	# elle n'atteint jamais `canalisation_bonus`. C'est une clé d'OBJET et de CONSOMMABLE
	# (`consommables.effets_de` la lit, elle), pas de capacité. Mesuré, pas déduit.
	"canalisation": "inerte sur une capacité — clé d'objet/consommable (ni empiler_effet_* "
					"ni bonus_passifs ne la relaient)",
	"invocation_duree":  "bonus de composant — une compétence n'a pas de composants",
	"invocation_nombre": "bonus de composant — une compétence n'a pas de composants",
	"maintien_reduction": "bonus de composant — une compétence n'a pas de composants",
}
# Champs de premier niveau encore réservés aux sorts.
CHAMPS_INERTES_SUR_COMPETENCE = {
	"invocation":  "réservé aux docs `sort:*` (normaliser_competence ne le lit pas)",
}
MAINTIEN_MAX = MAINTIEN_PM_MAX   # borne du moteur, jamais recopiée à la main
# Clés qui font d'une compétence une compétence de PIÈGE (`competences.action_piege`) : une
# case de barre posée d'office à l'apprentissage (`slots_actions.placer_si_libre`) et le DROIT
# d'agir (seuil `> 0`) sans la compétence dédiée. L'échelle de pièges vit dans
# `dev/gen_pieges.py` ; ce document n'en porte aucune (invariant n°13).
CLES_PIEGE_EFFETS = ("detection_pieges", "desamorcage")
CLE_PIEGE_DOC = "pose_piege"
# Clés du bloc `zone` que `normaliser_zone` sait lire. Même liste blanche, même piège : une
# `rayon_max` ou une `hauteur` inventée ne lève rien et ne dessine rien.
CHAMPS_ZONE = ("forme", "origine", "orientation", "rayon", "longueur", "largeur",
			   "decalage", "angle")

BLOC_JSON = re.compile(r"^```json\n(.*?)\n```", re.MULTILINE | re.DOTALL)


def charger_blocs(chemin):
	"""Chaque bloc ```json``` du document, avec son numéro de ligne de départ."""
	texte = open(chemin, encoding="utf-8").read()
	blocs = []
	for m in BLOC_JSON.finditer(texte):
		ligne = texte.count("\n", 0, m.start()) + 1
		blocs.append((ligne, m.group(1)))
	return blocs


def competences_des_imports() -> dict:
	"""Docs `competence:*` des `jsons/*_a_importer.json` committés, par `_id`.

	⚠️ Ils sont TENUS POUR IMPORTÉS (révision 6) : le dump committé retarde sur le contenu
	livré — celui du 2 octobre n'a aucune des 18 compétences de pièges de la PR #66. Même
	lecture que `ids_des_imports`, mais les docs entiers : le rapport en tire l'échelle de
	pièges du forestier et du voleur.
	"""
	out = {}
	if not os.path.isdir(DOSSIER_JSONS):
		return out
	for nom in sorted(os.listdir(DOSSIER_JSONS)):
		if not nom.endswith("_a_importer.json") or nom == IMPORT_DU_DOC:
			continue
		try:
			contenu = json.load(open(os.path.join(DOSSIER_JSONS, nom), encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			continue
		for doc in (contenu if isinstance(contenu, list) else [contenu]):
			if isinstance(doc, dict) and str(doc.get("_id", "")).startswith("competence:"):
				out[doc["_id"]] = doc
	return out


def ids_des_imports() -> set:
	"""`_id` de compétences présents dans les `jsons/*_a_importer.json` committés.

	⚠️ NÉCESSAIRE, et pas par excès de zèle : le dump committé retarde toujours sur le
	contenu livré. Les compétences arrivées avec les zones d'effet (`competence:balayage`,
	`competence:tourbillon_de_lames`, `competence:cri_de_ralliement`) vivent dans un import
	et dans AUCUN dump — un `_id` réutilisé les écraserait en silence, `admin_import_bulk`
	faisant un PUT complet. On lit donc les deux référentiels.
	"""
	out = set()
	if not os.path.isdir(DOSSIER_JSONS):
		return out
	for nom in os.listdir(DOSSIER_JSONS):
		if not nom.endswith("_a_importer.json") or nom == IMPORT_DU_DOC:
			continue
		try:
			contenu = json.load(open(os.path.join(DOSSIER_JSONS, nom), encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			continue   # un import illisible n'est pas le sujet de ce script
		for doc in (contenu if isinstance(contenu, list) else [contenu]):
			if isinstance(doc, dict) and str(doc.get("_id", "")).startswith("competence:"):
				out.add(doc["_id"])
	return out


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


def verifier_competence(doc, prefixe, ids_existants=None, vocations_connues=None,
						niveaux=NIVEAUX_ATTENDUS, zone_persistante=False) -> list:
	"""Invariants d'UN doc (n° 1, 2, 4 et 7 à 13 du document) — liste d'erreurs, vide si OK.

	Partagée par ce vérificateur et par `dev/gen_competences_1_10.py` : un lot généré passe
	par les mêmes gardes qu'un bloc écrit à la main. `ids_existants` / `vocations_connues`
	à None sautent le contrôle correspondant ; `niveaux` à None accepte tout niveau.
	`zone_persistante=True` = la zone persistante est VOULUE (déclarée par la donnée) : la
	garde (12), qui ne vise que le mur involontaire, est levée pour ce doc.
	"""
	erreurs = []
	cid = doc.get("_id", "<sans _id>")
	# (1) le moteur accepte-t-il le doc, et sans perdre de clé ?
	comp = normaliser_competence(doc)
	if comp is None:
		erreurs.append(f"{prefixe} : rejeté par normaliser_competence "
					   f"(type ≠ 'competence' ou vocation absente)")
		return erreurs

	for cle in doc:
		if cle not in CHAMPS_DOC:
			erreurs.append(f"{prefixe} : champ `{cle}` INCONNU de normaliser_competence — "
						   f"il disparaîtrait silencieusement à la lecture")

	# (2) Clés INERTES sur une compétence. Elles ne disparaissent pas à la
	# normalisation — c'est bien pire : la compétence part en base, s'utilise sans la
	# moindre erreur, et ne fait rien. Deux d'entre elles (`saut`, `lien_vie`) sont même
	# ACCEPTÉES par `competence_utilisable_combat`.
	for cle, pourquoi in CHAMPS_INERTES_SUR_COMPETENCE.items():
		if cle in doc:
			erreurs.append(f"{prefixe} : champ `{cle}` sur une COMPÉTENCE — {pourquoi}")
	for cle, pourquoi in EFFETS_INERTES_SUR_COMPETENCE.items():
		if (doc.get("effets") or {}).get(cle):
			erreurs.append(f"{prefixe} : effet `{cle}` sur une COMPÉTENCE — {pourquoi}")

	# (3) L'ACCORD entre le prédicat du router et le moteur. Ce contrôle remplace
	# l'ancienne règle « `degats_pm` jamais seul », devenue sans objet : les deux
	# gardes divergeaient (celle des compétences omettait la clé), elles appellent
	# désormais la même fonction. Plutôt que de retirer le contrôle, on le remonte
	# d'un cran — on ne teste plus UNE clé, on teste que les deux prédicats du moteur
	# s'accordent sur cette entrée, quelle que soit la clé en cause.
	eff_norm = _bonus_dict(doc.get("effets") or {})
	if est_active(comp) and comp["cible"] == "ennemi":
		if capacite_utilisable_combat(comp) and not effets_agissent_sur_cible(eff_norm):
			erreurs.append(f"{prefixe} : active `ennemi` lançable en combat mais SANS "
						   f"effet sur une cible — le router la listerait, le moteur "
						   f"la refuserait au moment de frapper")

	# (4) maintien : borne du moteur, actives seulement, et pas de `duree` trompeuse.
	# Une FORMULE (`"5-{Vol/25}"`) est jugée sur ce qu'elle donne entre une caract à 0 et à
	# 100 : `sorts.resoudre_temps` la bornerait en silence, l'auteur doit le savoir.
	if "maintien" in doc:
		maintien = doc.get("maintien") or 0
		if est_formule(maintien):
			extremes = [evaluer_formule(maintien, {c: v for c in CARACTS_FORMULE}) for v in (0, 100)]
			if min(extremes) < 1 or max(extremes) > MAINTIEN_MAX:
				erreurs.append(f"{prefixe} : `maintien` {maintien!r} sort de [1, {MAINTIEN_MAX}] "
							   f"entre une caract à 0 et à 100 ({extremes})")
		elif not isinstance(maintien, int) or maintien < 0 or maintien > MAINTIEN_MAX:
			erreurs.append(f"{prefixe} : `maintien` {maintien!r} hors de [0, "
						   f"{MAINTIEN_MAX}] (MAINTIEN_PM_MAX)")
		if maintien and est_passive(comp):
			erreurs.append(f"{prefixe} : PASSIVE portant `maintien` — une passive n'est "
						   f"jamais lancée, rien ne prélèverait l'entretien")
		if maintien and (doc.get("effets") or {}).get("duree"):
			erreurs.append(f"{prefixe} : entrée MAINTENUE portant `duree` — l'entrée "
						   f"d'effets_actifs ne se décrémente pas, la durée annoncée "
						   f"est une échéance qui n'existe pas")

	# (4 bis) incantation FORMULÉE : mêmes bornes que le moteur, entre une caract à 0 et à 100.
	if est_formule(doc.get("incantation")):
		extremes = [evaluer_formule(doc["incantation"], {c: v for c in CARACTS_FORMULE})
					for v in (0, 100)]
		if min(extremes) < 1 or max(extremes) > INCANTATION_PA_MAX:
			erreurs.append(f"{prefixe} : `incantation` {doc['incantation']!r} sort de [1, "
						   f"{INCANTATION_PA_MAX}] entre une caract à 0 et à 100 ({extremes})")

	# (4 ter) PROVOCATION : elle ne vaut que posée sur un MONSTRE touché, pour une durée.
	if eff_norm.get("provocation"):
		if not (est_active(comp) and comp["cible"] == "ennemi"):
			erreurs.append(f"{prefixe} : `provocation` hors d'une active `ennemi` — rien ne "
						   f"la poserait sur un monstre")
		if not (eff_norm.get("duree") or (eff_norm.get("formules") or {}).get("duree")):
			erreurs.append(f"{prefixe} : `provocation` sans `duree` — l'effet ne serait "
						   f"jamais posé (part à durée)")

	# (4 quinquies) ÉCHANGE DE PLACE : il permute le lanceur et la cible DÉSIGNÉE (allié ou
	# ennemi) — sur soi ou sur une passive, il n'y aurait personne avec qui permuter.
	if eff_norm.get("echange") and not (est_active(comp) and comp["cible"] in ("allie", "ennemi")):
		erreurs.append(f"{prefixe} : `echange` hors d'une active `allie` ou `ennemi` — il "
					   f"n'y aurait personne avec qui permuter")

	# (4 quater) AURA à formule : `entree_aura` ne résout rien, la formule serait perdue.
	if est_passive(comp) and doc.get("zone") and eff_norm.get("formules"):
		erreurs.append(f"{prefixe} : AURA à formule — `competences.entree_aura` ne résout "
					   f"aucune formule, l'aura ne donnerait que sa part constante")

	# (11) SIGNE de la régén selon la cible. Depuis la PR #66 `regen_pv`/`regen_pm` sont
	# SIGNÉES (négatif = poison). Le moteur ne refuse AUCUN des mauvais emplois :
	# `effets_agissent_sur_cible` accepte une régén positive sur un ennemi (elle le
	# soignerait), une aura négative empoisonnerait tout le groupe. Mesuré, pas déduit.
	regens = {k: eff_norm.get(k, 0) for k in ("regen_pv", "regen_pm")}
	negatives = sorted(k for k, v in regens.items() if v < 0)
	positives = sorted(k for k, v in regens.items() if v > 0)
	if negatives:
		if est_passive(comp) and doc.get("zone"):
			erreurs.append(f"{prefixe} : AURA à régén NÉGATIVE {negatives} — elle "
						   f"empoisonnerait tout le groupe, montures comprises")
		if est_active(comp) and comp["cible"] == "allie":
			erreurs.append(f"{prefixe} : active `allie` à régén NÉGATIVE {negatives} — "
						   f"elle empoisonnerait un compagnon")
	if positives and est_active(comp) and comp["cible"] == "ennemi":
		erreurs.append(f"{prefixe} : active `ennemi` à régén POSITIVE {positives} — "
					   f"elle soignerait la cible (le moteur l'accepte)")
	if (est_active(comp) and (negatives or positives)
			and not eff_norm.get("duree") and not doc.get("maintien")):
		erreurs.append(f"{prefixe} : active à régén sans `duree` ni `maintien` — rien "
					   f"ne serait empilé (part_durative)")

	# (12) MUR involontaire (PR #33) : la règle est DÉRIVÉE, sans clé — toute capacité
	# offensive à zone ET maintenue laisse une zone persistante qui brûle QUICONQUE s'y
	# tient, alliés et lanceur compris. Le moteur la gère : la garde ne refuse que celle
	# qu'on n'a pas DÉCLARÉE (`zone_persistante`), qu'un auteur aurait obtenue en voulant
	# seulement « une frappe de zone maintenue ».
	if (est_active(comp) and comp["cible"] == "ennemi" and doc.get("zone")
			and doc.get("maintien") and not zone_persistante):
		erreurs.append(f"{prefixe} : active `ennemi` à `zone` ET `maintien` — c'est une "
					   f"ZONE PERSISTANTE à tir ami (Mur de feu), pas une frappe")

	# (13) aucune clé de piège : `action_piege` en ferait une compétence de piège
	for cle in CLES_PIEGE_EFFETS:
		if eff_norm.get(cle):
			erreurs.append(f"{prefixe} : effet `{cle}` — l'entrée deviendrait une "
						   f"compétence de PIÈGE (case de barre d'office, droit d'agir "
						   f"sans la compétence dédiée)")
	if CLE_PIEGE_DOC in doc:
		erreurs.append(f"{prefixe} : bloc `{CLE_PIEGE_DOC}` — l'échelle des poses vit "
					   f"dans dev/gen_pieges.py, pas dans ce document")

	# (1 bis) la zone est une seconde liste blanche, avec ses propres pièges
	zone_ecrite = doc.get("zone")
	if zone_ecrite is not None:
		for cle in zone_ecrite if isinstance(zone_ecrite, dict) else ():
			if cle not in CHAMPS_ZONE:
				erreurs.append(f"{prefixe} : clé de zone `{cle}` INCONNUE du moteur")
		zone_lue = normaliser_zone(zone_ecrite)
		if zone_lue is None:
			erreurs.append(f"{prefixe} : bloc `zone` rejeté par normaliser_zone "
						   f"(`forme` absente ou non reconnue) — la capacité "
						   f"retomberait sur la seule case de sa cible")
		else:
			# (6) Une passive + zone n'est plus une erreur : c'est une AURA
			# (`competences.est_aura`), ancrée sur le porteur, servie au groupe en
			# exploration et positionnellement en combat. Restent deux gardes.
			if est_passive(comp):
				if not est_aura(comp):
					erreurs.append(f"{prefixe} : passive à `zone` que `est_aura` ne "
								   f"reconnaît pas")
				# ⚠️ `aura + condition` est HORS PÉRIMÈTRE du moteur : une passive
				# conditionnée sort déjà du repli permanent, et rien ne relit sa zone.
				if comp["condition"]:
					erreurs.append(f"{prefixe} : AURA portant une `condition` — hors "
								   f"périmètre du moteur, elle ne serait jamais posée")
				# Une aura qui n'offre rien est une chip vide sur ses alliés.
				eff_a = comp["effets"]
				if not (eff_a.get("buffs") or eff_a.get("regen_pv")
						or eff_a.get("regen_pm") or eff_a.get("esquive")):
					erreurs.append(f"{prefixe} : AURA sans buff, régén ni esquive — "
								   f"elle ne donnerait rien à personne")
			# (9) convention de `decalage`, pour les seules formes orientées
			if zone_lue["forme"] in ("rectangle", "cone"):
				if zone_lue["origine"] == "lanceur" and zone_lue["decalage"] < 1:
					erreurs.append(f"{prefixe} : forme orientée ancrée sur le LANCEUR "
								   f"avec decalage {zone_lue['decalage']} — son premier "
								   f"cran serait la case du lanceur (attendu ≥ 1)")
				if zone_lue["origine"] == "cible" and zone_lue["decalage"] != 0:
					erreurs.append(f"{prefixe} : forme orientée ancrée sur la CIBLE "
								   f"avec decalage {zone_lue['decalage']} — la cible "
								   f"désignée serait la seule épargnée (attendu 0)")

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

	# (2) pas de collision avec ce qui est déjà en base
	if ids_existants is not None and cid in ids_existants:
		erreurs.append(f"{prefixe} : `_id` DÉJÀ EN BASE — l'import l'écraserait "
					   f"(admin_import_bulk fait un PUT complet)")

	# (4) référentiel
	if vocations_connues and comp["vocation"] not in vocations_connues:
		erreurs.append(f"{prefixe} : vocation `{comp['vocation']}` absente de rules:vocations")
	if niveaux is not None and comp["niveau"] not in niveaux:
		erreurs.append(f"{prefixe} : niveau {comp['niveau']} hors de {tuple(niveaux)}")

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
	return erreurs


def main():
	chemin = sys.argv[1] if len(sys.argv) > 1 else DOC_DEFAUT
	if not os.path.exists(chemin):
		raise SystemExit(f"ERREUR : document introuvable — {chemin}")

	erreurs = []
	blocs = charger_blocs(chemin)
	if not blocs:
		raise SystemExit(f"ERREUR : aucun bloc ```json``` dans {chemin}")

	dump, vocations_connues, ids_existants = vocations_du_dump()
	ids_imports = ids_des_imports()
	if ids_existants is not None:
		ids_existants = ids_existants | ids_imports

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

		erreurs.extend(verifier_competence(doc, prefixe, ids_existants, vocations_connues))
		comp = normaliser_competence(doc)
		if comp is None:
			continue
		# (2) unicité, et pas de collision avec ce qui est déjà en base
		if cid in vus:
			erreurs.append(f"{prefixe} : `_id` en double (déjà ligne {vus[cid]})")
		vus[cid] = ligne
		par_vocation.setdefault(comp["vocation"], []).append(comp)

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
	print(f"Référentiel : {dump or 'AUCUN DUMP — contrôles de vocation et de collision sautés'}"
		  f" + {len(ids_imports)} competence:* dans jsons/*_a_importer.json")
	print(f"Blocs lus : {len(docs)} · vocations couvertes : {len(par_vocation)}")
	passives = sum(1 for _, d in docs if (d.get("mode") == "passive"))
	print(f"Répartition : {passives} passives / {len(docs) - passives} actives")
	docs_bruts = [d for _, d in docs]
	zones = [d for d in docs_bruts if d.get("zone")]
	formes = {}
	for d in zones:
		formes[d["zone"].get("forme")] = formes.get(d["zone"].get("forme"), 0) + 1
	auras = [d for d in zones if d.get("mode") == "passive"]
	hostiles = sum(1 for d in zones if d.get("cible") == "ennemi" and d.get("mode") != "passive")
	print(f"Zones : {len(zones)} — {len(zones) - len(auras)} capacités "
		  f"({hostiles} hostiles / {len(zones) - len(auras) - hostiles} bénéfiques) "
		  f"+ {len(auras)} aura(s) · "
		  + " · ".join(f"{f} ×{n}" for f, n in sorted(formes.items())))
	sensibles = [d for d in docs_bruts if d.get("sensibilite_charge") is not None]
	if sensibles:
		print(f"Charge magique : {len(sensibles)} entrée(s) à `sensibilite_charge` explicite")
	poisons = [d["_id"].split(":", 1)[1] for d in docs_bruts
			   if any(_bonus_dict(d.get("effets") or {}).get(k, 0) < 0
					  for k in ("regen_pv", "regen_pm"))]
	print(f"Régén négative : {len(poisons)} entrée(s) — {', '.join(poisons) or 'aucune'}")
	# Échelle de pièges déjà livrée (imports tenus pour en base) : ce que les entrées du
	# document côtoient au même palier, pour les vocations qui en ont une.
	pieges = {}
	for cdoc in competences_des_imports().values():
		comp = normaliser_competence(cdoc)
		if comp and competence_action_piege(comp):
			pieges.setdefault(comp["vocation"], []).append(comp["niveau"])
	for voc, niveaux in sorted(pieges.items()):
		communs = sorted(set(niveaux) & set(NIVEAUX_ATTENDUS))
		print(f"Pièges en base — {voc} : {len(niveaux)} compétence(s), niveaux "
			  f"{min(niveaux)}→{max(niveaux)} · paliers partagés avec ce document : "
			  f"{', '.join(map(str, communs)) or 'aucun'}")

	if erreurs:
		print(f"\n{len(erreurs)} PROBLÈME(S) :")
		for e in erreurs:
			print(f"  - {e}")
		return 1
	print("\nOK — les treize invariants tiennent.")
	return 0


if __name__ == "__main__":
	sys.exit(main())

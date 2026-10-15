# utils/potentiel.py
# Potentiels de COMBAT et de SUPPORT d'un belligérant — les règles d'évaluation de
# l'écran /admin/simulateur, regroupées ICI pour être ÉDITÉES facilement : toutes les
# pondérations vivent dans REGLES_POTENTIEL en tête de fichier, rien n'est enfoui dans
# les formules. Modifier un poids ne demande de toucher à rien d'autre.
#
# Les deux fonctions sont PURES et travaillent sur ce que produit utils/simulateur :
# un `snapshot` de référence (déterministe — point médian pour une espèce, snapshot de
# pleine forme pour un character) et un `arsenal` (sorts/compétences/consommables de la
# barre d'action). Les seuils de toucher passent par les helpers du moteur — les mêmes
# que le duel — et les espérances de dés par simulateur.moyenne_de_des.
#
# Sens des imports : potentiel → simulateur → combat, jamais l'inverse.

import copy
import math

from models import character_stats
from utils import combat, simulateur
from utils.simulateur import moyenne_de_des, options_offensives_statiques

# ── LES RÈGLES — tout se règle ici ───────────────────────────────────────────────────
REGLES_POTENTIEL = {
	# Cible étalon contre qui l'offense est évaluée (un adversaire « moyen ») :
	"defense_reference": 40,      # Ag + esquive de l'adversaire type (jets physiques)
	"pm_def_reference": 30,       # défense magique de l'adversaire type (jets magiques)
	"pa_reference": 2,            # armure soustraite aux dégâts physiques

	# Potentiel de COMBAT = sqrt(offense × survie) :
	"poids_offense": 1.0,         # espérance de dégâts/round de la meilleure option
	"poids_survie": 1.0,          # PV effectifs (pv_max × mitigation)
	"facteur_pa": 0.04,           # +4 % de PV effectifs par point d'armure — PA en ESPÉRANCE
	                              # sur la localisation (`combat.pa_de_zone`) : un casque ne
	                              # pèse que la part des coups qui frappent la tête
	"facteur_esquive": 0.01,      # +1 % de PV effectifs par point d'Ag + esquive
	"bonus_portee": 0.10,         # +10 % d'offense par case de portée au-delà de 1
	"tours_reference": 5,         # horizon d'un combat : la régén de PV (équipement…) compte
	                              # pour regen_pv × tours en PV effectifs

	# Potentiel d'une ESPÈCE (`potentiel_espece`) :
	"bonus_humanoide": 0.10,      # +10 % pour un humanoïde qui a des objets à porter
	                              # (maniement, tactique), en plus du gain espéré des objets

	# Potentiel de SUPPORT = Σ des soutiens de la barre, pondérés par la castabilité :
	"poids_soin": 1.0,            # par PV rendu instantanément
	"poids_pm_rendus": 0.5,       # par PM rendu (instantané ou régénéré × durée)
	"poids_regen": 2.0,           # par PV régénéré × durée
	"poids_buff": 0.8,            # par tranche de 10 points de caract buffés × durée
	"poids_esquive_octroyee": 0.6,  # par point d'esquive × durée
	"poids_furtivite": 15.0,      # forfait si le soutien confère la furtivité
}


def _regles(surcharge: dict | None) -> dict:
	"""REGLES_POTENTIEL surchargées clé à clé (tests, expérimentations) — les clés
	absentes gardent leur valeur de référence."""
	return {**REGLES_POTENTIEL, **(surcharge or {})}


def potentiel_combat(snapshot: dict, arsenal: dict, regles: dict | None = None) -> dict:
	"""Score offensif ET défensif d'un belligérant contre l'adversaire étalon.

	offense = meilleure option offensive : proba de toucher (seuils du moteur contre la
	défense de référence) × dégâts moyens après armure de référence × actions par tour,
	majorée par la portée, plafonnée par la castabilité pour un sort (les PM ne financent
	pas un cast par action indéfiniment).
	survie  = (pv_max + régén × tours_reference) gonflés par l'armure — en espérance sur la
	          localisation des coups — et l'esquive (PV effectifs).
	total   = sqrt(offense × survie) — forme Lanchester : doubler l'un ou l'autre pèse
	pareil, l'échelle reste douce."""
	r = _regles(regles)
	actions_max = max(1, int(snapshot.get("actions_max", 1) or 1))
	pm_max = int(snapshot.get("pm_max", 0) or 0)

	# Adversaire ÉTALON, sous la forme d'un dict de défenseur : c'est lui que reçoit
	# `combat.calculer_degats`. ⚠️ Si la formule se met un jour à lire les caracts brutes
	# de la cible (`caracts_base`), c'est ICI qu'il faudra les lui donner.
	etalon = {"pa": r["pa_reference"], "ag": r["defense_reference"],
			  "pm_def": r["pm_def_reference"], "caracts_base": {}}

	meilleure, option_retenue = 0.0, ""
	for opt in options_offensives_statiques(snapshot, arsenal):
		if opt["jet"] == "magique":
			seuil = combat._magic_hit_threshold(
				snapshot.get("toucher_magique", 0), r["pm_def_reference"])
		else:
			skill = snapshot.get("cd", 0) if opt["jet"] == "cd" else snapshot.get("cc", 0)
			seuil = combat._hit_threshold(skill, r["defense_reference"])
		# Dégâts par la formule PARTAGÉE (espérance des dés au lieu du tirage) : changer
		# la règle du jeu met ce score à jour tout seul.
		par_coup = (seuil / 100.0) * combat.calculer_degats(
			snapshot, etalon, opt["notation"], 1, opt["jet"], des_fn=moyenne_de_des)
		par_round = par_coup * actions_max * (1 + r["bonus_portee"] * (opt["portee"] - 1))
		if opt["cout_pm"] > 0:
			castabilite = min(1.0, pm_max / (opt["cout_pm"] * actions_max)) if pm_max else 0.0
			par_round *= castabilite
		if par_round > meilleure:
			meilleure, option_retenue = par_round, opt["label"]

	offense = meilleure * r["poids_offense"]
	pv_effectifs = max(1, int(snapshot.get("pv_max", 1) or 1)) + (
		max(0, int(snapshot.get("regen_pv_base", 0) or 0)) * r["tours_reference"])
	survie = pv_effectifs * (
		1 + r["facteur_pa"] * combat.pa_de_zone(snapshot)
		+ r["facteur_esquive"] * (int(snapshot.get("ag", 0) or 0)
								  + int(snapshot.get("esquive", 0) or 0))
	) * r["poids_survie"]
	total = math.sqrt(max(0.0, offense) * max(0.0, survie))
	return {"total": round(total, 1), "offense": round(offense, 1),
			"survie": round(survie, 1), "option_retenue": option_retenue}


def potentiel_support(snapshot: dict, arsenal: dict, regles: dict | None = None) -> dict:
	"""Score de soutien : ce que la barre sait RENDRE et OCTROYER (soins, PM, régén,
	buffs de caract, esquive, furtivité), chaque soutien pondéré par sa castabilité —
	`min(1, pm_max/cout_pm)` pour un sort/une compétence, `min(1, stock)` pour un
	consommable. Une espèce n'a pas de soutien → total 0."""
	r = _regles(regles)
	pm_max = int(snapshot.get("pm_max", 0) or 0)
	total, detail = 0.0, []
	for s in arsenal.get("soutiens") or []:
		eff = s.get("effets") or {}
		duree = int(eff.get("duree", 0) or 0)
		buffs_abs = sum(abs(int(v or 0)) for v in (eff.get("buffs") or {}).values())
		points = (
			int(eff.get("pv", 0) or 0) * r["poids_soin"]
			+ int(eff.get("pm", 0) or 0) * r["poids_pm_rendus"]
			+ int(eff.get("regen_pv", 0) or 0) * duree * r["poids_regen"]
			+ int(eff.get("regen_pm", 0) or 0) * duree * r["poids_pm_rendus"]
			+ (buffs_abs / 10.0) * duree * r["poids_buff"]
			+ int(eff.get("esquive", 0) or 0) * duree * r["poids_esquive_octroyee"]
			+ (r["poids_furtivite"] if int(eff.get("furtivite", 0) or 0) > 0 else 0.0)
		)
		if s.get("kind") == "consommable":
			castabilite = min(1.0, float(s.get("stock") or 0))
		elif int(s.get("cout_pm", 0) or 0) > 0:
			castabilite = min(1.0, pm_max / s["cout_pm"]) if pm_max else 0.0
		else:
			castabilite = 1.0
		points *= castabilite
		if points > 0:
			total += points
			detail.append({"label": s.get("label", "?"), "points": round(points, 1)})
	detail.sort(key=lambda d: -d["points"])
	return {"total": round(total, 1), "detail": detail}


def _esperance_min(capacite: int, n: int, p: float) -> float:
	"""E[min(capacite, X)], X ~ Binomiale(n, p) : nombre espéré d'emplacements d'un groupe
	effectivement garnis quand chacun de ses `n` objets est tiré avec la proba `p`."""
	return sum(min(capacite, k) * math.comb(n, k) * p ** k * (1 - p) ** (n - k)
			   for k in range(n + 1))


def potentiel_espece(espece_id: str, profil_id: str | None, get_doc_fn,
					 regles: dict | None = None) -> dict:
	"""Potentiel de COMBAT d'une espèce (± profil), ÉQUIPEMENT COMPRIS — la valeur que lisent
	le plancher des épreuves de rang et la colonne espèce de /admin/table.

	En jeu, un humanoïde tire chacun de ses objets (`combat.items_equipables_monstre`) avec la
	proba `MONSTRE_EQUIPEMENT_PROBA` : on en prend l'ESPÉRANCE, déterministe.
	  · nu         = potentiel du snapshot de référence (humanoïde nu, cf. `_snapshot_median`) ;
	  · gain d'un objet = potentiel avec CET objet seul dans son premier slot − nu, mesuré par
		les formules du moteur (`simulateur._equiper_snapshot`) : arme → modes et dés,
		armure → PA de sa zone, bonus de caract, esquive, régén — rien n'est recopié ici ;
	  · objets qui se disputent les MÊMES slots = un groupe : gain moyen × nombre espéré de
		slots garnis (`_esperance_min`), loi exacte du tirage pour une pièce à un slot ;
	  · equipement = somme des groupes. ⚠️ Approximation assumée : les pièces sont supposées
		additives (pas d'interaction entre elles) et une arme à deux mains bloque son groupe
		seul, pas le bouclier d'un autre groupe ;
	  · total = (nu + equipement) × (1 + bonus_humanoide) si l'espèce est humanoïde ET a au
		moins un objet à porter, sinon nu.
	Lève comme `construire_belligerant` (ValueError / LookupError)."""
	r = _regles(regles)
	spec = {"type": "espece", "id": espece_id}
	if profil_id:
		spec["profil"] = profil_id
	bel = simulateur.construire_belligerant(spec, get_doc_fn)
	nu_snap, arsenal = bel["snapshot_reference"], bel["arsenal"]
	nu = potentiel_combat(nu_snap, arsenal, r)["total"]
	espece = get_doc_fn(espece_id) or {}

	items = combat.items_equipables_monstre(espece) if simulateur.espece_equipable(espece) else []
	groupes: dict = {}
	detail = []
	for item_id, item in items:
		slots = [s for s in (item.get("slots") or []) if s in simulateur.SLOTS_EQUIPABLES]
		if not slots:
			continue
		snap = simulateur._equiper_snapshot(copy.deepcopy(nu_snap), {slots[0]: item_id})
		gain = max(0.0, potentiel_combat(snap, arsenal, r)["total"] - nu)
		detail.append({"item": item_id, "slot": slots[0], "gain": round(gain, 1)})
		cle = frozenset(slots)
		groupe = groupes.setdefault(cle, {"gains": [], "deux_mains": False})
		groupe["gains"].append(gain)
		groupe["deux_mains"] |= bool(item.get("deux_mains"))

	p = max(0.0, min(1.0, float(character_stats.MONSTRE_EQUIPEMENT_PROBA)))
	equipement = 0.0
	for cle, groupe in groupes.items():
		gains = groupe["gains"]
		capacite = 1 if groupe["deux_mains"] else len(cle)
		equipement += (sum(gains) / len(gains)) * _esperance_min(capacite, len(gains), p)

	bonus = r["bonus_humanoide"] if detail else 0.0
	total = (nu + equipement) * (1 + bonus)
	detail.sort(key=lambda d: -d["gain"])
	return {"total": round(total, 1), "nu": nu, "equipement": round(equipement, 1),
			"bonus_humanoide": bonus, "detail": detail}

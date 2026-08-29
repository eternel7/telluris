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

import math

from utils import combat
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
	"facteur_pa": 0.04,           # +4 % de PV effectifs par point d'armure
	"facteur_esquive": 0.01,      # +1 % de PV effectifs par point d'Ag + esquive
	"bonus_portee": 0.10,         # +10 % d'offense par case de portée au-delà de 1

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
	survie  = pv_max gonflés par l'armure et l'esquive (PV effectifs).
	total   = sqrt(offense × survie) — forme Lanchester : doubler l'un ou l'autre pèse
	pareil, l'échelle reste douce."""
	r = _regles(regles)
	actions_max = max(1, int(snapshot.get("actions_max", 1) or 1))
	pm_max = int(snapshot.get("pm_max", 0) or 0)

	meilleure, option_retenue = 0.0, ""
	for opt in options_offensives_statiques(snapshot, arsenal):
		if opt["jet"] == "magique":
			seuil = combat._magic_hit_threshold(
				snapshot.get("toucher_magique", 0), r["pm_def_reference"])
			pa = 0
		else:
			skill = snapshot.get("cd", 0) if opt["jet"] == "cd" else snapshot.get("cc", 0)
			seuil = combat._hit_threshold(skill, r["defense_reference"])
			pa = r["pa_reference"]
		par_coup = (seuil / 100.0) * max(1.0, moyenne_de_des(opt["notation"]) - pa)
		par_round = par_coup * actions_max * (1 + r["bonus_portee"] * (opt["portee"] - 1))
		if opt["cout_pm"] > 0:
			castabilite = min(1.0, pm_max / (opt["cout_pm"] * actions_max)) if pm_max else 0.0
			par_round *= castabilite
		if par_round > meilleure:
			meilleure, option_retenue = par_round, opt["label"]

	offense = meilleure * r["poids_offense"]
	survie = max(1, int(snapshot.get("pv_max", 1) or 1)) * (
		1 + r["facteur_pa"] * int(snapshot.get("pa", 0) or 0)
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

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
from utils import capacites_monstre, combat, simulateur
from utils.sorts import est_maintenu, resoudre_effets, resoudre_temps, sorts_eligibles_espece
from utils.simulateur import esperance_option, options_offensives_statiques
from utils.recrutement import RANGS

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

	# RANG d'une espèce (`rang_espece`) — la VITESSE qui interdit la fuite :
	"initiative_reference": 40,   # initiative du fuyard étalon = humain de départ (V 5, Ag 20 :
	                              # (Ag + 20 V) // 3), contre qui se joue `combat._flee_threshold`
	"poids_inescapable": 1.0,     # potentiel × (1 + poids × piège) ; piège = 0 tant que la fuite
	                              # vaut celle d'initiative égale, 1 quand elle tombe à 0 % —
	                              # au plancher de 5 % du moteur : × 1,9

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
		# Dégâts par la formule PARTAGÉE (espérance des dés au lieu du tirage) : changer
		# la règle du jeu met ce score à jour tout seul. Deux armes ⇒ deux coups par action.
		par_coup = _par_coup_etalon(snapshot, opt, r)
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


# ── CAPACITÉS d'une espèce : sorts tirés et capacités innées, UNE par tour ───────────────
# Un monstre lance AU PLUS UNE capacité par tour (`combat._tenter_capacite_monstre`), sort tiré
# ou compétence innée (souffle, étreinte…), celle-ci soumise à sa RECHARGE. Son round avec la
# capacité `c` vaut donc la frappe de `c` + ses actions RESTANTES à l'arme — jamais moins que
# l'arme seule. L'offense d'une espèce est la moyenne de ses rounds sur l'horizon
# `tours_reference` :
#   · SORTS : il en tire `k` (niveau de son profil, borné au pool des sorts que son IA sait
#     lancer — `combat.roll_monster_sorts`) et joue son meilleur ; espérance du meilleur des
#     `k` tirés, loi exacte P(le i-ᵉ meilleur du pool est le meilleur tiré) = C(n−i, k−1) /
#     C(n, k) — déterministe, comme l'équipement en espérance ;
#   · INNÉES : chacune n'occupe que la part des rounds que permettent sa recharge
#     (`ceil(horizon / recharge)` lancers) et ses PM ; la plus forte d'abord, tant qu'elle
#     bat le meilleur sort ; les rounds restants prennent le meilleur sort (ou l'arme).
# Toute frappe de capacité reçoit le même bonus de portée que les armes (`bonus_portee`).


def _offense_creature(invocation: dict, get_doc_fn, regles: dict) -> float:
	"""Offense par round d'UNE créature invoquée : son arme et ses capacités INNÉES, une par
	tour, sans sa propre magie (pas de récursion)."""
	espece = get_doc_fn(str(invocation.get("espece") or ""))
	if not espece or espece.get("type") != "espece":
		return 0.0
	spec = {"type": "espece", "id": espece["_id"]}
	profil = None
	if invocation.get("profil"):
		spec["profil"] = invocation["profil"]
		profil = get_doc_fn(invocation["profil"])
	try:
		bel = simulateur.construire_belligerant(spec, get_doc_fn)
	except (ValueError, LookupError):
		return 0.0
	snap, arsenal = bel["snapshot_reference"], bel["arsenal"]
	arme = potentiel_combat(snap, _arsenal_arme(arsenal), regles)["offense"]
	return offense_capacites(snap, arme, espece, profil, arsenal, get_doc_fn, regles,
							 sorts=False)["offense"]


def _arsenal_arme(arsenal: dict) -> dict:
	"""L'arsenal réduit à l'arme : ni sort ni compétence (comptés une par tour, à part)."""
	return {**(arsenal or {}), "sorts": [], "competences": []}


def _bonus_portee(portee: int, r: dict) -> float:
	return 1 + r["bonus_portee"] * (max(1, int(portee or 1)) - 1)


def valeur_sort_monstre(snapshot: dict, sort: dict, get_doc_fn, regles: dict | None = None) -> tuple:
	"""`(valeur par round, actions qu'il consomme)` d'un sort tiré, contre l'adversaire étalon.

	  · lançable `lances = min(tours_reference, pm_max // cout_pm)` fois sur l'horizon : sa
		valeur est pondérée par `lances / tours_reference` ;
	  · instantané (ou maintenu) offensif : espérance de toucher × dégâts × bonus de portée,
		cible unique ;
	  · incantation longue : un seul départ pour `ceil(incantation / actions_max)` rounds ;
	  · invocation : offense de la créature × leur nombre × la part de l'horizon où elles
		restent (toute s'il est maintenu, sinon sa `duree`) ;
	  · soutien (soin, buff) : 0 — l'offense ne le voit pas."""
	r = _regles(regles)
	caracts = combat.caracts_effectives(snapshot)
	effets = resoudre_effets(sort["effets"], caracts)
	sort = resoudre_temps(sort, caracts, effets)
	actions = max(1, int(snapshot.get("actions_max", 1) or 1))
	horizon = max(1, int(r["tours_reference"]))
	cout = max(0, int(sort.get("cout_pm", 0) or 0))
	pm_max = int(snapshot.get("pm_max", 0) or 0)
	lances = min(horizon, pm_max // cout) if cout else horizon
	if lances <= 0:
		return 0.0, 1
	part = lances / horizon
	invocation = sort.get("invocation")
	if invocation:
		tenue = horizon if est_maintenu(sort) else min(horizon, max(1, int(invocation.get("duree", 1) or 1)))
		nombre = max(1, int(invocation.get("nombre", 1) or 1))
		return _offense_creature(invocation, get_doc_fn, r) * nombre * tenue / horizon, 1
	if sort.get("cible") != "ennemi" or not effets.get("degats"):
		return 0.0, 1
	portee = max(1, int(sort.get("portee", 1) or 1))
	option = {"kind": "sort", "label": sort.get("nom", ""), "jet": sort.get("jet") or "magique",
			  "portee": portee, "ranged": True, "notation": effets["degats"], "cout_pm": cout}
	valeur = _par_coup_etalon(snapshot, option, r) * _bonus_portee(portee, r) * part
	incantation = max(1, int(sort.get("incantation", 1) or 1))
	if incantation > actions:
		return valeur / math.ceil(incantation / actions), actions
	return valeur, incantation


def valeur_innee(snapshot: dict, comp: dict, regles: dict | None = None) -> tuple:
	"""`(frappe par lancer, part des rounds)` d'une compétence INNÉE offensive (souffle…) : sa
	frappe contre l'étalon × bonus de portée, et la part de l'horizon où elle est disponible —
	`ceil(horizon / recharge)` lancers (tous sans recharge), bornés par ses PM."""
	r = _regles(regles)
	options = options_offensives_statiques({**snapshot, "attaque_profils": []},
										   {"competences": [comp]})
	if not options:
		return 0.0, 0.0
	opt = options[0]
	frappe = _par_coup_etalon(snapshot, opt, r) * _bonus_portee(opt["portee"], r)
	horizon = max(1, int(r["tours_reference"]))
	recharge = max(0, int(comp.get("recharge", 0) or 0))
	lances = math.ceil(horizon / recharge) if recharge else horizon
	cout = max(0, int(comp.get("cout_pm", 0) or 0))
	if cout:
		lances = min(lances, int(snapshot.get("pm_max", 0) or 0) // cout)
	return frappe, max(0.0, min(1.0, lances / horizon))


def offense_capacites(snapshot: dict, offense_arme: float, espece: dict, profil: dict | None,
					  arsenal: dict | None, get_doc_fn, regles: dict | None = None,
					  sorts: bool = True) -> dict:
	"""`{offense, pool, tires, innees}` : offense moyenne par round d'un spécimen, ses capacités
	jouées UNE par tour (cf. le bloc d'en-tête). Sans capacité : l'offense à l'arme.
	`sorts=False` ne compte que les innées (créature invoquée)."""
	actions = max(1, int(snapshot.get("actions_max", 1) or 1))
	par_action = offense_arme / actions

	# 1. Le meilleur round de SORT, en espérance sur le tirage (l'arme seule à défaut).
	meilleur_sort, n, k = offense_arme, 0, 0
	if sorts:
		profil_id = (profil or {}).get("_id") if str((profil or {}).get("_id") or "").startswith("profil:") else None
		pool = [s for s in sorts_eligibles_espece(espece, get_doc_fn, combat.find_docs, profil_id)
				if capacites_monstre.sort_lancable_par_ia(s)]
		niveau = int((profil or {}).get("niveau", 1) or 0) if profil else 1
		n, k = len(pool), max(0, min(niveau, len(pool)))
		if k:
			rounds = []
			for sort in pool:
				valeur, prises = valeur_sort_monstre(snapshot, sort, get_doc_fn, regles)
				rounds.append(max(offense_arme, valeur + par_action * max(0, actions - prises)))
			rounds.sort(reverse=True)
			meilleur_sort = sum(v * math.comb(n - 1 - i, k - 1) / math.comb(n, k)
								for i, v in enumerate(rounds))

	# 2. Les INNÉES, sur la part des rounds que leur recharge permet, la plus forte d'abord.
	innees = []
	for comp in (arsenal or {}).get("competences") or []:
		frappe, part = valeur_innee(snapshot, comp, regles)
		if frappe > 0 and part > 0:
			innees.append({"label": comp.get("nom", ""), "round": frappe + par_action * (actions - 1),
						   "part": part, "frappe": round(frappe, 1)})
	innees.sort(key=lambda c: -c["round"])
	reste, offense = 1.0, 0.0
	for c in innees:
		if c["round"] <= meilleur_sort or reste <= 0:
			break
		prise = min(c["part"], reste)
		offense += prise * c["round"]
		reste -= prise
	offense += reste * meilleur_sort
	return {"offense": offense, "pool": n, "tires": k,
			"innees": [{"label": c["label"], "frappe": c["frappe"], "part": round(c["part"], 2)}
					   for c in innees]}


def _etalon(r: dict) -> dict:
	"""L'adversaire ÉTALON, sous la forme d'un dict de défenseur (cf. `potentiel_combat`)."""
	return {"pa": r["pa_reference"], "ag": r["defense_reference"],
			"pm_def": r["pm_def_reference"], "caracts_base": {}}


def _par_coup_etalon(snapshot: dict, opt: dict, r: dict) -> float:
	"""Espérance de dégâts d'UNE action `opt` contre l'étalon — seuils du moteur."""
	def seuil_de(coup):
		if opt["jet"] == "magique":
			return combat._magic_hit_threshold(snapshot.get("toucher_magique", 0), r["pm_def_reference"])
		# Précision résolue par le moteur (typologie, deux armes, compétence martiale).
		skill = coup.get("skill")
		if skill is None:
			skill = snapshot.get("cd", 0) if opt["jet"] == "cd" else snapshot.get("cc", 0)
		return combat._hit_threshold(skill, r["defense_reference"])
	return esperance_option(snapshot, _etalon(r), opt, seuil_de)


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
	  · nu = sqrt(offense × survie) du spécimen de référence : offense à l'ARME, puis ses
		capacités jouées une par tour — sorts tirés en espérance, innées selon leur recharge
		(`offense_capacites`) ; équipement mesuré à l'arme seule (pièces additives) ;
	  · total = (nu + equipement) × (1 + bonus_humanoide) si l'espèce est humanoïde ET a au
		moins un objet à porter, sinon nu.
	Lève comme `construire_belligerant` (ValueError / LookupError)."""
	r = _regles(regles)
	spec = {"type": "espece", "id": espece_id}
	if profil_id:
		spec["profil"] = profil_id
	bel = simulateur.construire_belligerant(spec, get_doc_fn)
	nu_snap, arsenal = bel["snapshot_reference"], bel["arsenal"]
	# Arme SEULE : sorts et compétences innées sont comptés à part, une capacité par tour.
	arme = _arsenal_arme(arsenal)
	pc = potentiel_combat(nu_snap, arme, r)
	espece = get_doc_fn(espece_id) or {}
	profil = get_doc_fn(profil_id) if profil_id else None
	capacites = offense_capacites(nu_snap, pc["offense"], espece, profil, arsenal, get_doc_fn, r)
	nu = round(math.sqrt(max(0.0, capacites["offense"]) * max(0.0, pc["survie"])), 1)

	items = combat.items_equipables_monstre(espece) if simulateur.espece_equipable(espece) else []
	groupes: dict = {}
	detail = []
	for item_id, item in items:
		slots = [s for s in (item.get("slots") or []) if s in simulateur.SLOTS_EQUIPABLES]
		if not slots:
			continue
		snap = simulateur._equiper_snapshot(copy.deepcopy(nu_snap), {slots[0]: item_id})
		# ⚠️ Gain mesuré contre le nu SANS magie (`pc`) : le potentiel équipé l'est aussi.
		gain = max(0.0, potentiel_combat(snap, arme, r)["total"] - pc["total"])
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
			"bonus_humanoide": bonus, "detail": detail,
			"capacites": {"offense_arme": pc["offense"], "offense": round(capacites["offense"], 1),
						  "pool": capacites["pool"], "tires": capacites["tires"],
						  "innees": capacites["innees"]},
			"initiative": int(nu_snap.get("initiative", 0) or 0)}


# ── RANG de dangerosité d'une espèce ─────────────────────────────────────────────────
# Colonnes calculées `rang` / `rang_libelle` de /admin/table (jamais stockées). Même échelle
# que le PLANCHER des épreuves de rang (`QUETE_RANG_POTENTIEL_MIN`, world-var relue à chaque
# appel) : l'espèce prend le plus haut rang dont elle atteint le seuil, sinon le plancher F.
# La VITESSE y pèse deux fois : dans les actions par tour (déjà dans l'offense de
# `potentiel_combat`) et, propre au rang, par la FUITE qu'elle interdit (`facteur_inescapable`) :
# une bête plus vive que le fuyard étalon ne se fuit plus, ce qui rend chaque combat mortel.
# Mesurée sous un grade de RÉFÉRENCE fixe — `combattant`, celui sur lequel les seuils ont été
# calibrés (cf. le commentaire de QUETE_RANG_POTENTIEL_MIN) — et pas sous le grade tiré en
# jeu, qui dépend de la zone : le rang dit ce qu'EST l'espèce, pas un spécimen donné.
RANG_PROFIL_REFERENCE = "profil:combattant"
# Libellé de dangerosité par rang (proposition du 04/11) — destiné aux traces de monstres.
RANG_LIBELLES = {
	"F": "Vermine",
	"E": "Bête dangereuse",
	"D": "Monstre",
	"C": "Fléau",
	"B": "Calamité",
	"A": "Cataclysme",
	"S": "Légende vivante",
	"S+": "Apocalypse",
}


def rang_de_potentiel(valeur: float) -> str:
	"""Rang de dangerosité d'un potentiel : le seuil le plus HAUT atteint parmi
	`QUETE_RANG_POTENTIEL_MIN`, sinon le premier rang de l'échelle (aucun plancher)."""
	rang, meilleur = RANGS[0], float("-inf")
	for r, seuil in (character_stats.QUETE_RANG_POTENTIEL_MIN or {}).items():
		if valeur >= seuil > meilleur:
			rang, meilleur = r, seuil
	return rang


def facteur_inescapable(initiative: int, regles: dict | None = None) -> tuple[float, float]:
	"""`(fuite, facteur)` face à un ennemi de cette initiative. `fuite` = chance de fuir du
	fuyard étalon, par la règle du MOTEUR (`combat._flee_threshold`) ; `facteur` multiplie le
	potentiel : 1 tant que la fuite vaut au moins celle d'une initiative égale, jusqu'à
	1 + `poids_inescapable` quand elle tombe à 0. Une bête LENTE n'est pas rabaissée : la
	lenteur ne retire rien à ce qu'elle frappe."""
	r = _regles(regles)
	ref = int(r["initiative_reference"])
	fuite = combat._flee_threshold(ref, int(initiative or 0)) / 100.0
	egale = combat._flee_threshold(ref, ref) / 100.0
	piege = max(0.0, 1.0 - fuite / egale) if egale > 0 else 0.0
	return fuite, 1.0 + r["poids_inescapable"] * piege


def potentiel_menace(espece_id: str, profil_id: str | None, get_doc_fn,
					 regles: dict | None = None) -> tuple[float, float]:
	"""`(potentiel, fuite)` d'une espèce sous ce profil : `potentiel_espece` (équipement espéré
	compris) × `facteur_inescapable`. SOURCE UNIQUE de la mesure de dangerosité partagée par le
	rang (`rang_espece`) et le PLANCHER des épreuves de rang (`chasse.potentiel_cible`).
	Lève comme `potentiel_espece`."""
	pe = potentiel_espece(espece_id, profil_id, get_doc_fn, regles)
	fuite, facteur = facteur_inescapable(pe["initiative"], regles)
	return round(pe["total"] * facteur, 1), fuite


def rang_espece(espece_id: str, get_doc_fn, regles: dict | None = None) -> dict:
	"""`{potentiel_rang, fuite_pct, rang, rang_libelle}` d'une espèce : `potentiel_menace` sous
	le grade de référence (`RANG_PROFIL_REFERENCE`), et son rang. Lève comme `potentiel_espece`."""
	v, fuite = potentiel_menace(espece_id, RANG_PROFIL_REFERENCE, get_doc_fn, regles)
	rang = rang_de_potentiel(v)
	return {"potentiel_rang": v, "fuite_pct": round(fuite * 100), "rang": rang,
			"rang_libelle": RANG_LIBELLES.get(rang, "")}

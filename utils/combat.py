import re
import math
import random
import uuid
from db.config import get_doc, save_doc, find_docs
from models import character_stats
from models.character_stats import (
	BaseStats, EquipmentBonus, compute_derived_stats
)
from utils.lieux import nav_allows, MOVE_OFFSETS
from utils.characters import (
	grant_xp, sync_equipment_bonus, carried_weight, poids_bounds, item_ref_id, item_ref_weight,
)
from utils.consommables import (
	caracts_avec_buffs, est_consommable, effet_instantane, effets_de, esquive_bonus,
	cumul_effets, identite_source, poser_effet, _as_int as _eff_int,
)
from utils.sorts import part_durative, effets_d_arme, concat_degats
from utils.quetes import maj_progress_kills, maj_progress_chasse
from utils.focalisation import effacer_si_objectif_atteint
from utils import recrutement
from utils import montures as montures_util
from utils import escorte as escorte_util
from utils import animations as animations_util

BATTLE_MAPS = [
	"map0001.jpg", "map0002.jpg", "map0003.jpg", "map0004.jpg",
	"map0005.jpg", "map0006.jpg", "map0007.jpg", "abandonned_church01.webp",
]

# Tag qui retire une battle map du tirage de décor ordinaire (`select_battle_map`) :
# une salle de donjon ne s'atteint que par son gardien. Filtre de DONNÉE — préféré à
# `donjon.donjon_de_lieu`, qui coûterait un find_docs à chaque entrée en combat.
TAG_BATTLE_MAP_EXCLU = "donjon"


def _compute_actions_max(ag: int, v: int) -> int:
	"""Nombre d'actions par tour dérivé des stats : max(1, ceil(Ag/40 + V/2))."""
	return max(1, math.ceil(ag / 40 + v / 2))


def _charge_penalized_deplacement(deplacement_base: int, charge: float, charge_max: float) -> int:
	"""Déplacement de combat après malus de charge.

	Au-delà de la moitié de la charge max, le déplacement est divisé par deux
	(arrondi à l'inférieur, minimum 1). En-dessous, valeur de base inchangée.
	"""
	if charge_max > 0 and charge > charge_max / 2:
		return max(1, deplacement_base // 2)
	return max(1, deplacement_base)


def _recompute_player_deplacement(joueur: dict) -> None:
	"""Réapplique le malus de charge au déplacement du joueur (après un ramassage)."""
	joueur["deplacement"] = _charge_penalized_deplacement(
		joueur.get("deplacement_base", joueur.get("deplacement", 1)),
		joueur.get("charge", 0), joueur.get("charge_max", 0),
	)


# ── Effets à durée EN COMBAT ─────────────────────────────────────────────────
# Un snapshot de joueur porte une liste `effets_actifs` VIVANTE (même forme d'entrée que
# character["effets_actifs"] : {nom, icon, buffs, regen_pv, regen_pm, esquive, restants}),
# alimentée à l'entrée par les effets déjà en cours et par tout sort/compétence/consommable
# à durée lancé pendant le combat. Elle est décrémentée au tour de son porteur
# (_tick_effets_combat) et reversée sur le personnage à la fin (_finalize_membre).
#
# Pour que ces effets pèsent réellement sur les dérivées, le snapshot conserve de quoi les
# RECALCULER : `caracts_base` (caracts + buffs PERMANENTS d'équipement et de passives),
# `equipment_bonus` et `voc_niveau`. Un snapshot d'avant cette feature n'a pas ces champs :
# _refresh_snapshot_stats sort alors sans rien toucher → un combat déjà en base tourne à
# l'identique, sans migration.


def _buffs_des_effets(acteur: dict) -> dict:
	"""Buffs de caract portés par les effets vivants du snapshot — NON CUMULATIFS (meilleur
	bonus + pire malus par caract, cf. utils/consommables.cumul_effets). Les permanents
	(équipement, passives) sont déjà figés dans `caracts_base` : rien à scinder ici."""
	return cumul_effets(acteur.get("effets_actifs") or [])["buffs"]


def _refresh_snapshot_stats(acteur: dict) -> None:
	"""Recompose les dérivées d'un snapshot depuis `caracts_base` + Σ buffs de ses effets
	vivants. Chokepoint unique : tout ce qui ajoute ou retire un effet en combat finit ici.

	⚠️ Deux valeurs restent FIGÉES à l'entrée en combat et ne sont JAMAIS recalculées :
	  • `actions_max` — _refresh_actions recalcule actions_restantes = actions_max − Σ
		compteurs. Un actions_max qui bouge en plein tour offrirait des actions gratuites
		au moment du cast, puis un budget incohérent à l'expiration du buff.
	  • `charge_max` — même exclusion anti-exploit qu'en exploration (charge_max_of ignore
		les buffs) : un buff de F qui expire rendrait rétroactivement surchargé.
	"""
	base_caracts = acteur.get("caracts_base")
	if not base_caracts:
		return  # snapshot d'avant la feature : rien à recalculer
	stats = dict(base_caracts)
	for code, delta in _buffs_des_effets(acteur).items():
		if code in stats:
			stats[code] = max(0, int(stats[code] or 0) + delta)

	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	equipment = _equipment_bonus_de(acteur)
	derived = compute_derived_stats(base, niveau=acteur.get("voc_niveau", 0), equipment=equipment)

	acteur["cc"] = derived.cc
	acteur["cd"] = derived.cd
	acteur["ag"] = base.ag
	acteur["ch"] = base.ch
	acteur["pa"] = derived.pa
	# Localisation : seule la VENTILATION est portée par le snapshot ; la part globale
	# s'en déduit (`pa` − Σ zones), donc un debuff de R la fait bouger toute seule.
	acteur["pa_zones"] = dict(derived.pa_zones)
	acteur["pm_def"] = derived.pm_def
	acteur["toucher_magique"] = derived.toucher_magique
	acteur["degats_cc"] = derived.degats_cc
	acteur["degats_cd"] = derived.degats_cd
	acteur["initiative"] = derived.initiative
	# Plancher à 1 : un debuff de R assez violent amènerait pv_max à 0, donc currentPV à 0
	# au re-clamp — un acteur « mort » sans que personne ne l'ait frappé, et sans que
	# `vivant` soit mis à jour (le combat resterait bloqué sur un cadavre debout).
	acteur["pv_max"] = max(1, derived.pv_max)
	acteur["pm_max"] = max(0, derived.pm_max)
	acteur["deplacement_base"] = derived.deplacement
	# Esquive = passives permanentes (figées à l'entrée) + la MEILLEURE des effets vivants
	# (non-cumul : deux dissimulations ne s'additionnent pas).
	acteur["esquive"] = acteur.get("esquive_base", 0) + cumul_effets(
		acteur.get("effets_actifs") or [])["esquive"]

	# `attaque_profils` reste FIGÉ lui aussi : les recalculer relirait les docs d'items en
	# base (_weapon_attacks fait un get_doc par slot) à chaque tour, dans ce qui doit rester
	# du calcul pur. Le seul effet perdu est la portée d'une arme de jet (F // FACTEUR_DEGATS_ARMURE, soit +1
	# case pour 20 de Force et FACTEUR_DEGATS_ARMURE = 20) — négligeable au regard du coût.

	# Un buff de R/Vol qui expire abaisse les max : on re-clampe plutôt que de laisser
	# des PV au-dessus du plafond (l'inverse — un buff qui monte le max — ne soigne pas).
	acteur["currentPV"] = min(int(acteur.get("currentPV", acteur["pv_max"]) or 0), acteur["pv_max"])
	acteur["currentPM"] = min(int(acteur.get("currentPM", acteur["pm_max"]) or 0), acteur["pm_max"])
	# ⚠️ Une monture est immobilisée à l'entrée (`deplacement: 0`, hors ordre d'initiative) :
	# recalculer son déplacement depuis V la remettrait en marche. Elle est dans `joueurs`,
	# donc CIBLABLE — un debuff qui la touche ne doit pas la « réveiller ». Même raison, même
	# traitement, pour une personne ESCORTÉE.
	if acteur.get("est_monture") or acteur.get("est_protege"):
		acteur["deplacement"] = 0
	else:
		_recompute_player_deplacement(acteur)


def _equipment_bonus_de(acteur: dict) -> EquipmentBonus:
	"""EquipmentBonus du snapshot (stocké en dict pour rester sérialisable en base)."""
	brut = acteur.get("equipment_bonus")
	if isinstance(brut, EquipmentBonus):
		return brut
	try:
		return EquipmentBonus(**(brut or {}))
	except Exception:
		return EquipmentBonus()


def _empiler_effet_combat(acteur: dict, source: dict, effets: dict, tour: int) -> dict | None:
	"""Empile la part à durée de `effets` sur les effets vivants du snapshot (mute en
	place). Renvoie l'entrée créée, None si rien à empiler.

	L'entrée a EXACTEMENT la forme de celles de character["effets_actifs"] (plus un
	`pose_tour` retiré à la sortie du combat) : c'est ce qui permet à _finalize_membre de
	la reverser telle quelle sur le personnage, où le tick d'exploration la reprendra.

	⚠️ Non-cumul : `poser_effet` remplace toute entrée de MÊME SOURCE (`source_id`, timbré
	ici faute de clé de famille à ce niveau — le snapshot ne sait pas s'il pose un sort, une
	compétence ou une potion). Vaut aussi pour les debuffs posés sur une cible : relancer le
	même sort sur le même monstre le rafraîchit au lieu de l'empiler.
	"""
	eff = effets or {}
	if not part_durative(eff):
		return None
	entry = {
		"source_id": identite_source(source),
		"nom": (source or {}).get("nom", "Effet"),
		"icon": (source or {}).get("icon", "✨"),
		"buffs": dict(eff.get("buffs") or {}),
		"regen_pv": _eff_int(eff.get("regen_pv")),
		"regen_pm": _eff_int(eff.get("regen_pm")),
		"esquive": _eff_int(eff.get("esquive")),
		"restants": _eff_int(eff.get("duree")),
		# Tour de la pose : le tick du même tour la saute, sinon un effet lancé pendant
		# son propre tour perdrait un point avant d'avoir servi.
		"pose_tour": int(tour or 0),
	}
	poser_effet(acteur, entry)
	_refresh_snapshot_stats(acteur)
	return entry


def _avec_vfx(entree: dict, canal: str, cible_id: str, source_anim=None, acteur_id=None) -> dict:
	"""Ajoute la charge d'animation à une entrée de journal — et RIEN si rien n'est résolu.

	Le journal ne porte AUCUN id (`{tour, acteur (un NOM), kind, texte}`) : le client ne
	peut donc pas déduire qui a été touché par quoi, et les tours de monstres sont
	entièrement résolus côté serveur avant la réponse HTTP. C'est ce qui fait de l'entrée
	de journal le SEUL canal possible pour transporter une animation.

	Clé ABSENTE quand aucune animation n'est configurée : les combats déjà en base et tout
	contenu non lié continuent de tourner à l'identique, sans migration."""
	charge = animations_util.vfx(canal, cible_id, source_anim, acteur_id)
	if charge:
		entree["vfx"] = charge
	return entree


# Champs d'un snapshot que le CLIENT PEINT, et qui doivent donc attendre la ligne de
# journal qui les explique : vitalité, mort, position. Tout le reste (compteurs d'action,
# effets, détection, charge) suit l'état autoritatif immédiatement.
CHAMPS_ETAT = ("currentPV", "currentPM", "vivant", "morte", "pos", "facing")


# Profondeur des DEUX gardes d'idempotence indexées par id de combat : `combats_recompenses`
# (finalisation : XP/PV/butin ramassé, un par doc de membre) et `butin_collectes` (butin de
# victoire encaissé par /collect, sur le principal seul).
#
# ⚠️ C'est une FENÊTRE anti-doublon, jamais un journal : un doc `combat:*` terminé est
# finalisé PUIS SUPPRIMÉ au passage suivant à /play (main.py), donc un id sorti de la fenêtre
# ne peut plus jamais revenir se faire payer. Les dimensionner ensemble est délibéré — elles
# reposent sur ce même fait ; `butin_collectes` n'était pas borné du tout et grossissait
# d'une clé par combat pillé (70 sur un personnage de la base de référence).
#
# ⚠️ Aucune migration : un doc déjà en base dépasse la borne jusqu'à sa prochaine écriture,
# qui le retaille toute seule.
MEMOIRE_COMBATS_MAX = 10


def _avec_etat(entree: dict, *acteurs: dict) -> dict:
	"""Ajoute à une entrée de journal l'état des acteurs QU'ELLE VIENT DE CHANGER.

	Même canal et même motif que `_avec_vfx`, pour la même raison : le journal ne porte
	aucun id, et un tour de monstre est entièrement résolu avant la réponse HTTP. Sans
	cette charge, le client ne peut pas savoir quelle ligne explique quelle perte de PV —
	il n'a d'autre choix que de tout appliquer d'un bloc, donc AVANT les animations, et le
	joueur voit le résultat avant le coup.

	⚠️ À appeler APRÈS la mutation : on photographie l'acteur tel qu'il est, pas un delta.
	⚠️ `pos` est COPIÉ — le snapshot garde son dict d'un pas à l'autre.
	⚠️ Un acteur qu'AUCUNE entrée ne nomme n'est jamais gelé côté client : il suit l'état
	final tout de suite. Une couverture partielle dégrade donc vers « immédiat », jamais
	vers « faux ». Clé absente si aucun acteur (un combat déjà en base tourne à l'identique).
	"""
	etat: dict = {}
	for acteur in acteurs:
		aid = str((acteur or {}).get("id") or "")
		if not acteur or not aid:
			continue
		vue = {k: acteur[k] for k in CHAMPS_ETAT if k in acteur}
		if isinstance(vue.get("pos"), dict):
			vue["pos"] = dict(vue["pos"])
		etat[aid] = vue
	if etat:
		entree["etat"] = etat
	return entree


def _appliquer_effet_sur_cible(combat_doc: dict, cible: dict, source: dict,
							   effets: dict, tour: int, hostile: bool = True) -> dict | None:
	"""Empile la part à durée d'un sort/compétence OFFENSIF sur la CIBLE touchée.

	Miroir exact de la pose « sur soi » (même entrée, même chokepoint de recalcul), à trois
	différences près :
	  • elle n'est posée qu'en cas de TOUCHE — un sort qui se dissipe ne débuffe personne ;
	  • une cible MORTE du même coup n'est pas affectée (rien à ralentir dans un cadavre) ;
	  • elle ne remonte sur aucun doc : `_finalize_membre` ne reverse que les effets des
		membres du groupe, et un monstre ne survit pas au combat.

	Le tick est déjà générique : `_reset_turn_budget` appelle `_tick_effets_combat` pour les
	monstres comme pour les joueurs → la durée compte en TOURS DE LA CIBLE, ce qui est la
	lecture attendue (« -10 Ag pendant 2 tours » = les 2 prochains tours de l'ennemi).
	"""
	if not cible or not cible.get("vivant", True):
		return None
	entry = _empiler_effet_combat(cible, source, effets, tour)
	if not entry:
		return None
	# `cible` en état : poser l'effet est passé par _refresh_snapshot_stats, qui re-clampe
	# ses PV/PM (un debuff de R abaisse pv_max).
	combat_doc.setdefault("log", []).append(_avec_etat(_avec_vfx({
		"tour": int(tour or 0),
		"acteur": cible.get("nom", "?"),
		"kind": "sys",
		"texte": f"{entry.get('icon', '✨')} {cible.get('nom', '?')} "
				 f"{'subit' if hostile else 'bénéficie de'} "
				 f"{entry.get('nom', 'un effet')} ({entry['restants']} tour(s)).",
	}, "debuff" if hostile else "buff", cible.get("id", "")), cible))
	return entry


def _appliquer_effet_arme(combat_doc: dict, attaquant: dict, cible: dict,
						  profil: dict) -> dict | None:
	"""Empile la part à durée portée par l'ARME à l'impact — bolas qui entravent, lame
	qui affaiblit, hampe qui étourdit.

	N'appelle que des chokepoints existants : un effet d'arme se pose exactement comme un
	effet de sort, sur le même bloc `effets`, avec la même durée en tours de celui qui le
	subit. À n'appeler qu'après une TOUCHE (le seuil de toucher est le seul jet ; il n'y a
	pas de résistance propre à l'effet) et après la mise à jour de `vivant` : le
	chokepoint refuse une cible morte, on ne ralentit pas un cadavre.

	`effets_cible` décide de QUI subit — `ennemi` (le défaut) ou `soi`, une arme qui
	nourrit celui qui la manie. `_empiler_effet_combat` timbre l'identité de la source, si
	bien qu'une arme frappant deux fois **relance** son effet au lieu de l'empiler
	(non-cumul : une source = une entrée)."""
	effets = profil.get("effets")
	if not effets:
		return None
	source = {"nom": profil.get("label", "Arme"), "icon": "⚔️",
			  "id": profil.get("effets_source_id") or ""}
	if profil.get("effets_cible") == "soi":
		return _empiler_effet_combat(attaquant, source, effets, combat_doc["tour"])
	return _appliquer_effet_sur_cible(combat_doc, cible, source, effets, combat_doc["tour"])


def _lancer_sur_allie(combat_doc: dict, lanceur: dict, cible: dict, source: dict,
					  effets: dict, portee: int, grid: dict) -> dict:
	"""Applique un sort/une compétence bénéfique à un ALLIÉ (compagnon ou monture).

	Chokepoint partagé par les deux branches `cible == "allie"` de `resolve_action` : la
	seule différence entre un sort et une compétence à cet endroit serait le libellé, ce
	qui ne justifie pas deux copies de la même logique.

	⚠️ **Aucun jet de toucher.** Un allié ne se défend pas : on ne rate pas une main
	tendue. C'est ce qui rend `jet` (cc/cd/magique) sans objet ici — il ne concerne que
	les cibles hostiles.

	⚠️ **Pas d'interdiction « engagé au corps à corps ».** Elle existe pour les effets
	OFFENSIFS à distance (on n'incante pas tranquillement une bombe avec une épée sous la
	gorge) ; l'appliquer aux soins les rendrait impossibles exactement au moment où ils
	servent. La ligne de vue, elle, reste exigée au-delà du contact : on ne soigne pas à
	travers un mur.
	"""
	if not cible:
		return {"error": "Allié invalide."}
	# Seul un allié DEBOUT est visable : soigner un membre à 0 PV le remettrait en jeu,
	# donc changerait la condition de défaite et l'ordre du tour. Relever un compagnon à
	# terre mérite sa propre mécanique, pas un effet de bord d'un sort de soin.
	if cible.get("currentPV", 0) <= 0:
		return {"error": f"{cible.get('nom', 'Cet allié')} est à terre."}
	portee = max(1, int(portee or 1))
	if _cheby(lanceur, cible) > portee:
		return {"error": "Allié hors de portée."}
	if portee > 1 and not _line_of_sight(grid["cells"], lanceur["pos"]["x"], lanceur["pos"]["y"],
										  cible["pos"]["x"], cible["pos"]["y"]):
		return {"error": "Ligne de vue obstruée."}

	avant_pv, avant_pm = cible.get("currentPV", 0), cible.get("currentPM", 0)
	cible["currentPV"] = min(cible.get("pv_max", avant_pv), avant_pv + int(effets.get("pv", 0) or 0))
	cible["currentPM"] = min(cible.get("pm_max", avant_pm), avant_pm + int(effets.get("pm", 0) or 0))
	pv_rendu = cible["currentPV"] - avant_pv
	pm_rendu = cible["currentPM"] - avant_pm
	effet_pose = _appliquer_effet_sur_cible(
		combat_doc, cible, source, effets, combat_doc["tour"], hostile=False)
	# Une dissimulation lancée sur un allié le dissimule LUI (et remet la détection des
	# monstres à zéro) : _activer_furtivite prend déjà son porteur en paramètre.
	if int(effets.get("furtivite", 0) or 0) > 0:
		_activer_furtivite(combat_doc, cible, int(effets["furtivite"]))

	gains = " / ".join(s for s in (
		f"+{pv_rendu} PV" if pv_rendu else "",
		f"+{pm_rendu} PM" if pm_rendu else "",
		f"effet {effet_pose['restants']} tour(s)" if effet_pose else "",
	) if s) or "aucun effet"
	# ⚠️ Le LANCEUR n'est pas en état : ses PM sont débités par l'appelant APRÈS ce retour
	# (branche `sort`/`competence` de resolve_action). Le nommer ici gèlerait son affichage
	# sur une valeur d'avant le débit ; ne pas le nommer le laisse suivre l'état final.
	combat_doc.setdefault("log", []).append(_avec_etat(_avec_vfx({
		"tour": combat_doc["tour"],
		"acteur": lanceur["nom"],
		"kind": "sys",
		"texte": f"{lanceur['nom']} lance {source.get('nom', 'un effet')} "
				 f"sur {cible['nom']} ({gains}).",
	}, "soin", cible.get("id", ""), (source or {}).get("animation"), lanceur.get("id", "")), cible))
	return {
		"cible": cible["nom"], "cible_id": cible.get("id"),
		"cible_pv": cible["currentPV"], "cible_pv_max": cible.get("pv_max"),
		"cible_pm": cible["currentPM"], "cible_pm_max": cible.get("pm_max"),
		"pv_rendu": pv_rendu, "pm_rendu": pm_rendu,
		"effet_cible": dict(effet_pose) if effet_pose else None,
	}


def _tick_effets_combat(combat_doc: dict, acteur: dict) -> None:
	"""Début de tour d'un acteur : régén des effets, décrément, purge, recalcul.

	La `duree` compte donc en TOURS DU PORTEUR — même nombre qu'en exploration (où elle
	compte les déplacements), et indépendante du nombre de combattants.
	"""
	actifs = acteur.get("effets_actifs") or []
	if not actifs:
		return
	tour = int(combat_doc.get("tour", 0) or 0)

	# 1. Régénération (avant le décrément : un effet à 1 restant soigne une dernière fois).
	# Non-cumul : seule la MEILLEURE régén compte, pas la somme des effets en cours.
	cumul = cumul_effets(actifs)
	pv, pm = cumul["regen_pv"], cumul["regen_pm"]
	if pv or pm:
		avant_pv, avant_pm = acteur.get("currentPV", 0), acteur.get("currentPM", 0)
		acteur["currentPV"] = min(acteur.get("pv_max", avant_pv), avant_pv + pv)
		acteur["currentPM"] = min(acteur.get("pm_max", avant_pm), avant_pm + pm)
		gains = " / ".join(s for s in (
			f"+{acteur['currentPV'] - avant_pv} PV" if acteur["currentPV"] != avant_pv else "",
			f"+{acteur['currentPM'] - avant_pm} PM" if acteur["currentPM"] != avant_pm else "",
		) if s)
		if gains:
			combat_doc.setdefault("log", []).append(_avec_etat({
				"tour": tour, "acteur": acteur.get("nom", "?"), "kind": "sys",
				"texte": f"{acteur.get('nom', '?')} régénère ({gains}).",
			}, acteur))

	# 2. Décrément + purge. Une entrée posée CE tour-ci est épargnée.
	restants, expires = [], []
	for eff in actifs:
		if int(eff.get("pose_tour", -1)) == tour:
			restants.append(eff)
			continue
		eff["restants"] = _eff_int(eff.get("restants")) - 1
		(restants if eff["restants"] > 0 else expires).append(eff)
	acteur["effets_actifs"] = restants

	# 3. Les dérivées suivent (un buff expiré doit cesser de compter immédiatement).
	# ⚠️ AVANT les lignes de dissipation : elles portent l'état de l'acteur, qui n'est
	# arrêté qu'une fois les max recalculés et les PV/PM re-clampés.
	if expires:
		_refresh_snapshot_stats(acteur)

	for eff in expires:
		combat_doc.setdefault("log", []).append(_avec_etat(_avec_vfx({
			"tour": tour, "acteur": acteur.get("nom", "?"), "kind": "sys",
			"texte": f"{eff.get('icon', '✨')} {eff.get('nom', 'Effet')} se dissipe "
					 f"({acteur.get('nom', '?')}).",
		}, "dissipation", acteur.get("id", "")), acteur))


# ── Grille de combat ─────────────────────────────────────────────────────────
# Terrain cells[y][x] : -1 inaccessible, 0 inaccessible sauf vol, 1 accessible,
# 3 = falaise (infranchissable au sol, mais transparente à la vision : on tire/lance
# un sort par-dessus), n>1 accessible sous condition. Deux prédicats distincts :
# `_walkable` (déplacement, exclut les falaises sauf vol) et `_passable` (vision, seuil
# >= 1, donc une falaise ne bloque pas la ligne de vue).
DEFAULT_GRID_W = 13
DEFAULT_GRID_H = 11
TERRAIN_FALAISE = 3


def _can_fly(actor: dict) -> bool:
	"""L'acteur peut-il franchir les falaises ? Hook `volant` (inerte tant que non peuplé)."""
	return bool(actor.get("volant"))


def _open_grid(w: int = DEFAULT_GRID_W, h: int = DEFAULT_GRID_H) -> dict:
	"""Grille entièrement praticable (terrain ouvert, fallback sans battle map)."""
	return {"dims": {"x": w, "y": h}, "cells": [[1] * w for _ in range(h)]}


def _passable(cells: list, x: int, y: int) -> bool:
	"""Case transparente à la vision (`>= 1`) : une falaise (3) n'arrête pas un projectile,
	seul un mur (`< 1`) le fait. Prédicat de LIGNE DE VUE uniquement — pour le déplacement
	voir `_walkable`."""
	if not cells or y < 0 or y >= len(cells):
		return False
	row = cells[y]
	if x < 0 or x >= len(row):
		return False
	return row[x] >= 1


def _walkable(cells: list, x: int, y: int, flying: bool = False) -> bool:
	"""Case franchissable au DÉPLACEMENT : praticable (`>= 1`) et, sauf vol, pas une falaise."""
	if not cells or y < 0 or y >= len(cells):
		return False
	row = cells[y]
	if x < 0 or x >= len(row):
		return False
	val = row[x]
	return val >= 1 and (flying or val != TERRAIN_FALAISE)


def _cheby(a: dict, b: dict) -> int:
	return max(abs(a["pos"]["x"] - b["pos"]["x"]), abs(a["pos"]["y"] - b["pos"]["y"]))


def _line_of_sight(cells: list, x0: int, y0: int, x1: int, y1: int) -> bool:
	"""Ligne de vue libre entre deux cases (tracé de Bresenham).

	Bloquée si une case INTERMÉDIAIRE (hors extrémités) n'est pas praticable
	(`cells < 1`) — un mur arrête le projectile. `nav` n'est pas consulté : le tir
	survole les coins nav-bloqués, seul le terrain (murs) bloque la trajectoire.
	"""
	dx = abs(x1 - x0)
	dy = abs(y1 - y0)
	sx = 1 if x0 < x1 else -1
	sy = 1 if y0 < y1 else -1
	err = dx - dy
	x, y = x0, y0
	while True:
		if (x, y) != (x0, y0) and (x, y) != (x1, y1) and not _passable(cells, x, y):
			return False
		if x == x1 and y == y1:
			return True
		e2 = 2 * err
		if e2 > -dy:
			err -= dy
			x += sx
		if e2 < dx:
			err += dx
			y += sy


def _occupied_set(combat_doc: dict, exclude: dict | None = None) -> set:
	"""Ensemble des (x,y) occupés par des acteurs vivants (hors `exclude`)."""
	occ = set()
	for j in combat_doc["joueurs"]:
		if j is not exclude and j.get("currentPV", 1) > 0:
			occ.add((j["pos"]["x"], j["pos"]["y"]))
	for m in combat_doc["monstres"]:
		if m is not exclude and m["vivant"]:
			occ.add((m["pos"]["x"], m["pos"]["y"]))
	return occ


def _occupied_at(combat_doc: dict, x: int, y: int) -> bool:
	return (x, y) in _occupied_set(combat_doc)


def _move_ap_used_for(actor: dict, cells_moved: int) -> int:
	"""AP consommés pour `cells_moved` cases : ceil(cells * actions_max / deplacement)."""
	dep = max(1, actor.get("deplacement", 1))
	return math.ceil(cells_moved * actor["actions_max"] / dep)


def _refresh_actions(actor: dict) -> None:
	"""Recalcule actions_restantes = actions_max - attaques - ramassages - consommations
	- sorts - compétences - éditions de barre - pénalités - AP_déplacement.

	`penalites` = actions perdues sur échec critique (cf. _appliquer_fumble). Comme
	actions_restantes est TOUJOURS recalculé ici, une pénalité doit être un compteur :
	poser actions_restantes = 0 à la main serait écrasé au prochain appel."""
	used = (actor.get("attaques", 0) + actor.get("ramasses", 0)
			+ actor.get("consommes", 0) + actor.get("sorts", 0)
			+ actor.get("competences", 0) + actor.get("editions", 0)
			+ actor.get("penalites", 0)
			+ _move_ap_used_for(actor, actor.get("cells_moved", 0)))
	actor["actions_restantes"] = max(0, actor["actions_max"] - used)


def _reset_turn_budget(actor: dict, combat_doc: dict | None = None) -> None:
	"""Réinitialise le budget d'un acteur en début de tour.

	Seul hook « début de tour d'acteur » du moteur : c'est donc ici que les effets à durée
	régénèrent, se décrémentent et expirent (`combat_doc` fourni). Sans `combat_doc` —
	appels de test, monstres — le budget seul est réinitialisé.
	"""
	if combat_doc is not None:
		_tick_effets_combat(combat_doc, actor)
	actor["cells_moved"] = 0
	actor["attaques"] = 0
	actor["ramasses"] = 0
	actor["consommes"] = 0
	actor["sorts"] = 0
	actor["competences"] = 0
	# ⚠️ Compté dans _refresh_actions ET remis à zéro ICI : sans cette ligne, réorganiser
	# sa barre serait gratuit dès le deuxième tour.
	actor["editions"] = 0
	# Une dette d'action (échec critique commis alors qu'il ne restait rien à perdre)
	# se paie MAINTENANT : elle devient la pénalité du nouveau tour, puis s'efface.
	actor["penalites"] = actor.get("dette_actions", 0)
	actor["dette_actions"] = 0
	actor["actions_restantes"] = actor["actions_max"]
	_refresh_actions(actor)


def _find_path(cells: list, dims: dict, start: tuple, goal: tuple, blocked: set,
			   nav: dict | None = None, flying: bool = False) -> list | None:
	"""A* 8-directions (heuristique Chebyshev). Porté du prototype client.

	Mêmes règles que le déplacement du joueur : un pas est valide s'il vise une case
	dans la grille, praticable (`cells >= 1`), non `blocked` (sauf la case d'arrivée,
	occupable par la cible) et autorisé par `nav` (masques de la carte, diagonales
	incluses). Les diagonales coûtant 1 case, l'heuristique est la distance de
	Chebyshev (admissible) plutôt que Manhattan.
	Retourne la liste [(x,y), ...] de start à goal inclus, ou None.
	"""
	nav = nav or {}
	w, h = dims["x"], dims["y"]
	sx, sy = start
	gx, gy = goal
	start_node = {"x": sx, "y": sy, "g": 0, "h": max(abs(gx - sx), abs(gy - sy)), "parent": None}
	start_node["f"] = start_node["h"]
	open_list = [start_node]
	closed = set()

	while open_list:
		open_list.sort(key=lambda n: n["f"])
		cur = open_list.pop(0)
		if cur["x"] == gx and cur["y"] == gy:
			path = []
			node = cur
			while node:
				path.append((node["x"], node["y"]))
				node = node["parent"]
			return path[::-1]
		closed.add((cur["x"], cur["y"]))
		for dx, dy in MOVE_OFFSETS:
			nx, ny = cur["x"] + dx, cur["y"] + dy
			if nx < 0 or nx >= w or ny < 0 or ny >= h:
				continue
			if not _walkable(cells, nx, ny, flying):
				continue
			if not nav_allows(nav, cur["x"], cur["y"], dx, dy):
				continue
			if (nx, ny) in closed:
				continue
			is_goal = (nx == gx and ny == gy)
			if (nx, ny) in blocked and not is_goal:
				continue
			g = cur["g"] + 1
			existing = next((n for n in open_list if n["x"] == nx and n["y"] == ny), None)
			if existing is None:
				node = {"x": nx, "y": ny, "g": g, "h": max(abs(gx - nx), abs(gy - ny)), "parent": cur}
				node["f"] = node["g"] + node["h"]
				open_list.append(node)
			elif g < existing["g"]:
				existing["g"] = g
				existing["f"] = g + existing["h"]
				existing["parent"] = cur
	return None


def _nearest_passable(cells: list, dims: dict, tx: int, ty: int, occupied: set,
					  flying: bool = False) -> tuple:
	"""Case praticable et libre la plus proche de (tx, ty) par recherche en spirale."""
	w, h = dims["x"], dims["y"]
	tx = max(0, min(w - 1, tx))
	ty = max(0, min(h - 1, ty))
	for radius in range(0, max(w, h) + 1):
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				if max(abs(dx), abs(dy)) != radius:
					continue
				x, y = tx + dx, ty + dy
				if _walkable(cells, x, y, flying) and (x, y) not in occupied:
					return (x, y)
	return (tx, ty)


# ── Placement initial des acteurs ─────────────────────────────────────────────
# Central placé aléatoirement sur un sol type 1 : 50 % à ~5 cases du centre, 50 % à
# ~5 cases des bords (distance élargie « ou plus » si nécessaire pour pouvoir loger
# et rejoindre les monstres). Les monstres sont ensuite dispersés aléatoirement sur
# des cases atteignables depuis lui — la région joignable est calculée une fois par
# flood fill, donc toute case tirée garantit un chemin (équivaut à « tirer au hasard
# puis tester un chemin, sinon reboucler », sans le coût de la boucle).
PLAYER_CENTER_DIST: int = 5   # mode « centre »  : distance cible depuis le centre
PLAYER_BORDER_INSET: int = 5  # mode « bordure » : distance cible depuis les bords


def _iter_cells(dims: dict):
	for y in range(dims["y"]):
		for x in range(dims["x"]):
			yield x, y


def _is_type1(cells: list, x: int, y: int) -> bool:
	"""Sol « normal » praticable (type exactement 1)."""
	return 0 <= y < len(cells) and 0 <= x < len(cells[y]) and cells[y][x] == 1


def _reachable_region(cells: list, dims: dict, nav: dict, start: tuple,
					  flying: bool = False) -> set:
	"""Toutes les cases franchissables atteignables depuis `start`.

	Flood fill 8-directions respectant `nav` — mêmes règles que l'A* de
	déplacement (`_walkable`), donc cette région == l'ensemble des cases que l'A* sait joindre.
	"""
	sx, sy = start
	if not _walkable(cells, sx, sy, flying):
		return set()
	w, h = dims["x"], dims["y"]
	seen = {(sx, sy)}
	stack = [(sx, sy)]
	while stack:
		x, y = stack.pop()
		for dx, dy in MOVE_OFFSETS:
			nx, ny = x + dx, y + dy
			if (nx, ny) in seen or nx < 0 or nx >= w or ny < 0 or ny >= h:
				continue
			if not _walkable(cells, nx, ny, flying) or not nav_allows(nav, x, y, dx, dy):
				continue
			seen.add((nx, ny))
			stack.append((nx, ny))
	return seen


def _player_cell_candidates(cells: list, dims: dict, occupied: set, mode: str) -> list:
	"""Cases type 1 libres, ordonnées selon le mode de placement du central.

	Préférence aux cases à >= distance cible (5) du centre (mode 'centre') ou des
	bords (mode 'bordure'), la plus proche de la cible d'abord puis de plus en plus
	loin (« ou plus »). Ordre aléatoire à l'intérieur d'un même palier de distance.
	"""
	w, h = dims["x"], dims["y"]
	cx, cy = w // 2, h // 2
	target = PLAYER_CENTER_DIST if mode == "centre" else PLAYER_BORDER_INSET
	tiers: dict = {}
	for x, y in _iter_cells(dims):
		if not _is_type1(cells, x, y) or (x, y) in occupied:
			continue
		if mode == "centre":
			d = max(abs(x - cx), abs(y - cy))
		else:
			d = min(x, y, w - 1 - x, h - 1 - y)
		# « d cases ou plus » : d >= cible prioritaire (excédent minimal d'abord),
		# cases plus proches que la cible reléguées en dernier recours.
		key = (0, d - target) if d >= target else (1, target - d)
		tiers.setdefault(key, []).append((x, y))
	ordered = []
	for key in sorted(tiers):
		bucket = tiers[key]
		random.shuffle(bucket)
		ordered.extend(bucket)
	return ordered


def _nearest_of(pool, ref: tuple) -> tuple | None:
	"""Case de `pool` la plus proche de `ref` (distance Chebyshev), ou None si vide."""
	best, best_d = None, None
	for c in pool:
		d = max(abs(c[0] - ref[0]), abs(c[1] - ref[1]))
		if best_d is None or d < best_d:
			best, best_d = c, d
	return best


def _first_passable_cells(cells: list, dims: dict, count: int, flying: bool = False) -> list:
	"""Les `count` premières cases franchissables en balayant depuis (0,0)."""
	out = []
	for x, y in _iter_cells(dims):
		if _walkable(cells, x, y, flying):
			out.append((x, y))
			if len(out) >= count:
				return out
	return out


def _place_actors(combat_doc: dict, grid: dict) -> None:
	"""Place le groupe joueur puis disperse les monstres aléatoirement, en garantissant
	qu'ils peuvent rejoindre le personnage central.

	1. Tirage 50/50 du mode du central : ~5 cases du centre, ou ~5 cases des bords.
	2. Central + groupe potentiel sur des cases type 1 libres ; la distance s'élargit
	   (« ou plus ») jusqu'à une case dont la région atteignable peut tout loger.
	3. Vérification que tous les joueurs se rejoignent (sols >= 1) ; sinon repli sur
	   les premiers sols > 0 trouvés depuis (0,0).
	4. Monstres placés aléatoirement sur des cases de la région du central — donc
	   toujours joignables (remplace « tirer au hasard puis reboucler si non joint »).
	"""
	cells, dims = grid["cells"], grid["dims"]
	nav = grid.get("nav", {})
	joueurs = combat_doc["joueurs"]
	monstres = combat_doc["monstres"]
	occupied: set = set()

	need = len(joueurs) + len(monstres)  # cases distinctes à loger dans la région

	# 1-2. Mode + recherche d'une case type 1 pour le central dont la région
	#      atteignable est assez grande pour le groupe ET les monstres.
	mode = "centre" if random.random() < 0.5 else "bordure"
	main = joueurs[0]
	main_cell, region = None, set()
	for cand in _player_cell_candidates(cells, dims, occupied, mode):
		reg = _reachable_region(cells, dims, nav, cand)
		if len(reg) >= need:
			main_cell, region = cand, reg
			break

	placed_ok = False
	if main_cell is not None:
		main["pos"] = {"x": main_cell[0], "y": main_cell[1]}
		occupied.add(main_cell)
		# Groupe potentiel : cases type 1 libres de la région, au plus près du central.
		ok = True
		for j in joueurs[1:]:
			free = [c for c in region if c not in occupied]
			pick = _nearest_of([c for c in free if _is_type1(cells, c[0], c[1])] or free, main_cell)
			if pick is None:
				ok = False
				break
			j["pos"] = {"x": pick[0], "y": pick[1]}
			occupied.add(pick)
		# 3. Tous les joueurs doivent partager la région du central.
		placed_ok = ok and all((j["pos"]["x"], j["pos"]["y"]) in region for j in joueurs)

	# 3. (repli) Aucun placement valide : premiers sols > 0 depuis (0,0).
	if not placed_ok:
		fallback = _first_passable_cells(cells, dims, len(joueurs))
		occupied = set()
		for i, j in enumerate(joueurs):
			pos = fallback[i] if i < len(fallback) else (0, 0)
			j["pos"] = {"x": pos[0], "y": pos[1]}
			occupied.add(pos)
		region = _reachable_region(cells, dims, nav, (main["pos"]["x"], main["pos"]["y"]))

	# 4. Monstres : cases aléatoires de la région du central (toutes joignables).
	base = (main["pos"]["x"], main["pos"]["y"])
	for m in monstres:
		pool = [c for c in region if c not in occupied]
		if pool:
			pos = random.choice(pool)
		else:  # région saturée (carte minuscule) : repli sur la case libre la plus proche.
			pos = _nearest_passable(cells, dims, base[0], base[1], occupied)
		m["pos"] = {"x": pos[0], "y": pos[1]}
		occupied.add(pos)


def select_battle_map(terrain_tags: list, depart_lieu: dict | None) -> dict | None:
	"""Sélection pondérée d'un lieu battle map selon le recoupement de tags de TERRAIN.

	`terrain_tags` = décor des zones actives (`zones.terrain_tags_actifs`), PAS les
	`tags` de l'événement tiré : ceux-là nomment des créatures pour un événement
	`combat` (loup, brigand…) et ne recoupent jamais un tag de carte — le tirage était
	donc uniforme, et la mine sortait en pleine forêt une fois sur quatre.

	Trois règles :
	  1. une salle de donjon (tag `donjon`) n'est JAMAIS tirée comme décor ordinaire —
	     on n'y descend que par son gardien (cf. § Donjons) ;
	  2. au moins UN tag commun est exigé, et le poids est le nombre de tags communs ;
	  3. repli si rien ne matche : tirage uniforme sur tout le pool hors donjon. Une
	     zone dont le terrain n'a pas encore de carte (urbaine, marais…) garde ainsi le
	     comportement historique au lieu de tomber sur la grille ouverte, et l'import
	     d'une carte au bon tag l'active sans toucher au code.

	Retourne le lieu, ou None si aucune carte exploitable (l'appelant retombe alors sur
	la grille ouverte de `get_combat_grid`).
	"""
	candidates = [
		b for b in (find_docs({"type": "lieu", "categorie": "battle_map"}) or [])
		if b.get("cells") and TAG_BATTLE_MAP_EXCLU not in (b.get("tags") or [])
	]
	if not candidates:
		return None
	# Les tags du lieu de départ restent dans le pool : ils permettent à un auteur de
	# taguer un lieu d'exploration pour surcharger le décor de ses combats.
	pool_tags = set(terrain_tags or []) | set((depart_lieu or {}).get("tags", []))
	communs = [len(set(b.get("tags", [])) & pool_tags) for b in candidates]
	matching = [(b, n) for b, n in zip(candidates, communs) if n > 0]
	if not matching:
		return random.choice(candidates)
	return random.choices([b for b, _ in matching], weights=[n for _, n in matching], k=1)[0]


def get_combat_grid(combat_doc: dict) -> dict:
	"""Résout la grille {dims, cells, nav} du combat.

	`cells`/`nav` ne sont PAS dupliqués dans le doc combat : on référence le lieu
	battle map (`battle_map_id`) et on lit sa grille à la demande. `nav` = masque des
	directions interdites par case (cf. utils.lieux.get_final_mask), comme play_town.
	Repli sur une grille ouverte (taille `grid_dims`) si aucun lieu. Tolère un ancien
	doc avec `grid` en ligne.
	"""
	bm_id = combat_doc.get("battle_map_id")
	if bm_id:
		lieu = get_doc(bm_id)
		if lieu and lieu.get("cells"):
			return {
				"dims": lieu["dimensions"],
				"cells": lieu["cells"],
				"nav": lieu.get("nav", {}),
			}
	if combat_doc.get("grid", {}).get("cells"):  # rétro-compat docs existants
		grid = combat_doc["grid"]
		grid.setdefault("nav", {})
		return grid
	dims = combat_doc.get("grid_dims") or {"x": DEFAULT_GRID_W, "y": DEFAULT_GRID_H}
	grid = _open_grid(dims["x"], dims["y"])
	grid["nav"] = {}  # grille ouverte = aucune direction interdite
	return grid


def roll_dice(notation: str) -> int:
	"""Évalue une notation de dégâts et retourne au moins 1.

	Gère les termes simples ('1D6+3', '2D8', 'D4-1') comme les expressions
	composites issues des armes ('1D6+1D4+2', '1D8+1D6-1') : chaque terme 'nDm'
	est lancé (signe pris en compte), puis les entiers isolés sont additionnés.
	"""
	notation = notation.upper().replace(" ", "")
	total = 0
	for sign, n, sides in re.findall(r"([+-]?)(\d*)D(\d+)", notation):
		rolled = sum(random.randint(1, int(sides)) for _ in range(int(n or "1")))
		total += -rolled if sign == "-" else rolled
	# Modificateurs plats : entiers signés restants une fois les dés retirés.
	for mod in re.findall(r"[+-]?\d+", re.sub(r"[+-]?\d*D\d+", "", notation)):
		total += int(mod)
	return max(1, total)


# ── Localisation des touches ─────────────────────────────────────────────────
# Un d100 décide OÙ le coup porte ; seuls les PA de la pièce couvrant cette zone
# s'appliquent, plus ceux qui protègent partout (armure naturelle, bouclier).

# Libellés de journal — c'est par là que la mécanique devient visible en jeu.
ZONE_LIBELLE = {
	"tete": "à la tête", "epaules": "à l'épaule", "torse": "au torse",
	"bras": "au bras", "jambes": "à la jambe", "pieds": "au pied",
}


def _table_localisation() -> list:
	"""Bornes hautes triées, lues à chaud (`character_stats.LOCALISATION_TOUCHES`).
	Bornes ≤ 0 écartées : elles ne pourraient jamais gagner et fausseraient les parts."""
	table = [(int(b), str(z)) for z, b in
			 (character_stats.LOCALISATION_TOUCHES or {}).items() if int(b) > 0]
	return sorted(table)


def tirer_localisation(rand_fn=None) -> str | None:
	"""Zone frappée par ce coup — d100 contre la table des bornes hautes.

	`None` = pas de localisation (table vide ou illisible) : l'appelant retombe alors
	sur les PA agrégés, c'est-à-dire le comportement d'avant la feature.
	⚠️ `rand_fn` résolue À L'APPEL (même piège que `des_fn` de `calculer_degats`) : une
	valeur par défaut figerait la référence et les tests qui monkeypatchent `random`
	ne l'atteindraient plus."""
	table = _table_localisation()
	if not table:
		return None
	roll = (rand_fn or random.randint)(1, 100)
	for borne, zone in table:
		if roll <= borne:
			return zone
	return table[-1][1]   # jet au-delà de la dernière borne : la table ne monte pas à 100


def _parts_de_zone() -> dict:
	"""Part de chaque zone dans le d100 (largeur de sa tranche / 100). Sert à l'ESPÉRANCE
	des PA, celle que consomment les estimations du simulateur et des potentiels."""
	table = _table_localisation()
	if not table:
		return {}
	parts, precedent = {}, 0
	for borne, zone in table:
		parts[zone] = max(0, borne - precedent) / 100.0
		precedent = borne
	return parts


def pa_de_zone(defenseur: dict, zone: str | None = None):
	"""Points d'armure à opposer à un coup, selon l'endroit frappé.

	⚠️ La part GLOBALE (armure naturelle + bouclier, cou, ceinture) est DÉRIVÉE de
	`pa − Σ pa_zones`, jamais stockée à côté. Deux champs indépendants divergeraient dès
	que `pa` est surchargé — ce que font les stats forcées du simulateur et nombre de
	tests, qui posent un `pa` à la main sur un snapshot. Ici, forcer `pa` déplace le
	global et la ventilation reste vraie.

	Trois régimes :
	  • `pa_zones` absent ou vide (monstre, combat déjà en base, étalon des potentiels)
		⇒ tout est global : le `pa` agrégé s'applique, exactement comme avant la
		feature — aucune migration, et l'armure NATURELLE d'un monstre est bien
		uniforme ;
	  • `zone is None` ⇒ ESPÉRANCE : global + Σ (part de la tranche × PA de la zone).
		C'est ce qu'il faut aux estimations, qui doivent rester déterministes ;
	  • sinon ⇒ global + PA de la pièce couvrant cette zone (0 si elle est nue).
	"""
	total = int(defenseur.get("pa", 0) or 0)
	zones = {z: int(v or 0) for z, v in (defenseur.get("pa_zones") or {}).items()}
	global_ = total - sum(zones.values())
	if not zones:
		return total
	if zone is None:
		return global_ + sum(part * zones.get(z, 0) for z, part in _parts_de_zone().items())
	return global_ + zones.get(zone, 0)


def calculer_degats(attaquant: dict, defenseur: dict, notation: str,
					mult_degats: int = 1, jet: str = "cc", des_fn=None,
					zone: str | None = None):
	"""SOURCE UNIQUE des dégâts d'un coup qui TOUCHE — le seul endroit à modifier pour
	changer la façon dont une frappe blesse.

	Traversée par les cinq sites qui portent un coup (attaque de monstre, arme du joueur,
	sort, compétence, duel du simulateur) ET par les deux qui l'ESTIMENT (choix d'option
	du simulateur, offense des potentiels). Une formule recopiée ailleurs ferait diverger
	le jeu de son propre banc d'essai — c'est exactement ce que ce chokepoint supprime.

	Règle actuelle : dés × multiplicateur de critique, PUIS soustraction des PA, plancher
	à 1. Le critique double le COUP, pas la pénétration d'armure ; la magie ignore les PA
	(la défense magique a déjà joué dans le seuil de toucher).

	`des_fn` évalue la notation : `roll_dice` pour jouer un coup (défaut, rend un `int`),
	`simulateur.moyenne_de_des` pour l'espérer (rend un `float`). Même injection que les
	`get_doc_fn`/`rand_fn` du projet — c'est ce qui garde scores et coups sur UNE formule.
	⚠️ Le défaut est résolu DANS LE CORPS et non en valeur par défaut du paramètre : une
	valeur par défaut est évaluée à la DÉFINITION du module, donc elle figerait la
	référence et les nombreux tests qui monkeypatchent `roll_dice` ne l'atteindraient
	plus — ils verraient les vrais dés tomber sans rien pouvoir y faire.

	⚠️ CINQ POINTS À CONNAÎTRE AVANT DE TOUCHER À LA FORMULE :

	1. `attaquant` est passé bien qu'inutilisé par la règle d'aujourd'hui. C'est
	   délibéré : ajouter demain la Force au coup ne changera ni cette signature ni les
	   sept sites d'appel. Ne pas le retirer comme paramètre mort.
	2. Les caractéristiques BRUTES ne sont pas au premier niveau d'un snapshot : ni `F`
	   ni `R` n'y existent. Elles vivent dans `attaquant["caracts_base"]["F"]` et
	   `defenseur["caracts_base"]["R"]` (avec `.get`, un snapshot d'avant la feature des
	   effets à durée n'en porte pas).
	3. L'arithmétique se fait sur le RÉSULTAT du tirage, jamais dans la notation :
	   `des_fn` attend une chaîne (`"1D6+2"`), pas un nombre.
	4. F et R sont DÉJÀ comptées une fois — la Force dans la taille du dé
	   (`_caract_to_dice_`) plus `F // FACTEUR_DEGATS_ARMURE` de bonus plat, la Résistance dans les PA
	   (`R // FACTEUR_DEGATS_ARMURE`). Les rajouter brutes les compterait deux fois, et à
	   l'échelle ×10 des caracts ce serait un terme de ±50 sur un dé qui rend 5 : le dé ne
	   pèserait plus rien. Passer par les world-vars ou par `jet` (ne pas donner la Force
	   à un sort) plutôt que par une addition brute.
	5. Les PA opposés dépendent de la ZONE frappée : passer par `pa_de_zone`, jamais
	   par `defenseur["pa"]`, qui reste le total toutes pièces confondues.
	"""
	bruts = (des_fn or roll_dice)(notation) * mult_degats
	# `zone` = l'endroit frappé (cf. `tirer_localisation`). Absente ⇒ espérance des PA,
	# ce qu'attendent les estimations ; la magie, elle, n'oppose aucune armure.
	pa = 0 if jet == "magique" else pa_de_zone(defenseur, zone)
	return max(1, bruts - pa)


def roll_monster_stats(espece: dict, profil: dict) -> BaseStats:
	base = espece.get("base_attributes", {})
	mods = profil.get("attributs_modifier", {})

	def roll(key):
		bmin = base.get(key, {}).get("min", 1)
		bmax = base.get(key, {}).get("max", 5)
		mod = mods.get(key, {})
		delta = random.randint(mod.get("min", 0), mod.get("max", 0)) if mod else 0
		return max(bmin, min(bmax, bmin + delta))

	return BaseStats(
		v=roll("V"), f=roll("F"), r=roll("R"), ag=roll("Ag"),
		vol=roll("Vol"), int_=roll("Int"), cha=roll("Cha"), ch=roll("Ch"),
	)


def _espece_midpoint(espece: dict) -> BaseStats:
	base = espece.get("base_attributes", {})
	def mid(key):
		bmin = base.get(key, {}).get("min", 1)
		bmax = base.get(key, {}).get("max", 5)
		return (bmin + bmax) // 2
	return BaseStats(
		v=mid("V"), f=mid("F"), r=mid("R"), ag=mid("Ag"),
		vol=mid("Vol"), int_=mid("Int"), cha=mid("Cha"), ch=mid("Ch"),
	)


def _weapon_attacks(character: dict, base: BaseStats) -> list:
	"""Profils d'attaque disponibles selon les armes équipées.

	Une entrée par mode (cac/jet/tir) : la meilleure portée si plusieurs armes du même
	mode. Le mode vient d'un tag de l'item (`tir`/`jet`, défaut `cac`) ; les armes d'hast
	sont du `cac` à `portee >= 2` (pas de mode dédié). Une attaque de mêlée (poings,
	portée 1) est TOUJOURS disponible. Chaque profil porte les clés à lire dans le
	snapshot joueur : `toucher` (cc|cd) et `degats` (degats_cc|degats_cd).

	- cac : toucher cc, dégâts degats_cc (basé F), portée = item.portee (>=1).
	- jet : toucher cd, dégâts degats_cc (basé F), portée = item.portee + F//JET_PORTEE_F_DIV.
	- tir : toucher cd, dégâts degats_cd (basé Ag), portée = item.portee.

	Un profil emporte aussi la part DURATIVE du bloc `effets` de l'arme qui l'a gagné
	(`effets`/`effets_cible`), appliquée à l'impact par `_appliquer_effet_arme`. C'est le
	seul moment où les docs d'items sont relus : `attaque_profils` reste ensuite FIGÉ dans
	le snapshot (cf. `_refresh_snapshot_stats`), donc l'effet d'une arme est arrêté à
	l'entrée en combat comme sa portée et ses dégâts. Un profil sans `effets` (arme
	ordinaire, ou combat déjà en base) ne déclenche rien : aucune migration.
	"""
	jet_div = max(1, character_stats.JET_PORTEE_F_DIV)
	best: dict = {}

	def consider(mode, portee, ranged, toucher, degats, item):
		cur = best.get(mode)
		if cur is not None and portee <= cur["portee"]:
			return
		profil = {"mode": mode, "portee": max(1, int(portee)), "ranged": ranged,
				  "toucher": toucher, "degats": degats, "label": item.get("nom", "Arme"),
				  # Animation d'impact de CETTE arme (vide = repli sur le défaut du mode).
				  # Posée ici parce que c'est le SEUL moment où les docs d'items sont relus :
				  # aucune lecture DB ne doit avoir lieu pendant la résolution d'un coup.
				  "animation": str(item.get("animation") or ""),
				  # L'id de l'arme n'était posé (`effets_source_id`) que si elle portait un
				  # effet duratif : une arme ordinaire était anonyme dans le snapshot.
				  "item_id": str(item.get("_id") or "")}
		# La part durative SEULE : les dégâts d'une arme passent par ses `bonus_degats*`,
		# pas par ce bloc. Rien à empiler ⇒ pas de clé, donc pas de test à l'impact.
		effets, cible = effets_d_arme(item)
		if part_durative(effets):
			profil["effets"] = effets
			profil["effets_cible"] = cible
			# Identité de non-cumul ancrée sur l'ID de l'arme, pas sur son nom : deux docs
			# peuvent partager un `nom`, jamais un `_id` (cf. cle_source).
			profil["effets_source_id"] = item.get("_id", "")
		best[mode] = profil

	for ref in (character.get("slots") or {}).values():
		item_id = item_ref_id(ref)
		if not item_id:
			continue
		item = get_doc(item_id)
		if not item or item.get("categorie") != "arme":
			continue
		tags = set(item.get("tags", []))
		base_portee = int(item.get("portee", 1) or 1)
		if "tir" in tags:
			consider("tir", base_portee, True, "cd", "degats_cd", item)
		elif "jet" in tags:
			consider("jet", base_portee + base.f // jet_div, True, "cd", "degats_cc", item)
		else:  # cac par défaut (inclut les armes d'hast, portee >= 2)
			consider("cac", base_portee, False, "cc", "degats_cc", item)

	best.setdefault("cac", {"mode": "cac", "portee": 1, "ranged": False,
							"toucher": "cc", "degats": "degats_cc", "label": "Mains nues"})
	return [best[m] for m in ("cac", "jet", "tir") if m in best]


def build_joueur_snapshot(character: dict, joueur_index: int = 0) -> dict:
	# Buffs de consommables inclus : un combat démarré pendant un buff en profite
	# intégralement (pv_max, cc, dégâts, initiative, actions, déplacement — et donc
	# charge_max, bonus de portage en combat seulement). Ces effets sont désormais VIVANTS
	# dans le snapshot : décrémentés au tour de leur porteur (_tick_effets_combat) puis
	# reversés sur le personnage (_finalize_membre). Une potion bue juste avant d'entrer
	# ne dure donc plus tout le combat.
	# Bonus recalculé depuis les items équipés (slots = IDs) plutôt que depuis le champ
	# stocké equipment_bonus, périmé si un item a été modifié en base sans ré-équiper. Posé
	# AVANT caracts_avec_buffs, qui y lit les buffs de caract portés par les objets.
	equipment = sync_equipment_bonus(character)
	stats = caracts_avec_buffs(character)
	# Base PERMANENTE (équipement + passives, SANS les effets temporaires) : c'est depuis
	# elle que _refresh_snapshot_stats recompose les dérivées à chaque changement d'effet.
	# `stats` ci-dessus = caracts_base + Σ buffs des effets entrants → le snapshot construit
	# ici et un refresh immédiat donnent exactement les mêmes valeurs.
	caracts_base = caracts_avec_buffs(character, origines=("equipement", "competence"))
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
	derived = compute_derived_stats(base, niveau=voc_niveau, equipment=equipment)

	# Charge portée à l'entrée en combat → malus de déplacement si > charge_max/2.
	charge = round(carried_weight(character), 2)
	deplacement = _charge_penalized_deplacement(derived.deplacement, charge, derived.charge_max)

	# Profils d'attaque selon les armes équipées (mêlée/jet/tir) + portée de mêlée (legacy).
	attaques = _weapon_attacks(character, base)
	portee_cac = next((a["portee"] for a in attaques if a["mode"] == "cac"), 1)

	return {
		"id": f"joueur_{joueur_index}",
		"character_id": character["_id"],
		"nom": character.get("nom", "Aventurier"),
		"voc": character.get("voc", ""),
		"race": character.get("race", ""),
		"image": character.get("image", ""),
		"currentPV": character.get("currentPV", derived.pv_max),
		"pv_max": derived.pv_max,
		"currentPM": character.get("currentPM", derived.pm_max),
		"pm_max": derived.pm_max,
		"actions_restantes": _compute_actions_max(base.ag, base.v),
		"actions_max": _compute_actions_max(base.ag, base.v),
		"cc": derived.cc,
		"cd": derived.cd,
		"ag": base.ag,
		# Ch : écart de Chance attaquant/cible = glissement des fenêtres de critique
		# (_seuils_critiques). Valeur AVEC buffs, comme le reste du snapshot.
		"ch": base.ch,
		"pa": derived.pa,
		# Localisation des touches : ce que chaque pièce couvre. `pa` reste le TOTAL —
		# ce qui protège partout s'en déduit (cf. `pa_de_zone`), pour qu'un `pa`
		# surchargé (stats forcées du simulateur) reste cohérent.
		"pa_zones": dict(derived.pa_zones),
		"pm_def": derived.pm_def,
		"toucher_magique": derived.toucher_magique,
		"degats_cc": derived.degats_cc,
		"degats_cd": derived.degats_cd,
		"initiative": derived.initiative,
		"deplacement": deplacement,            # après malus de charge
		"deplacement_base": derived.deplacement,  # sans malus (pour recalcul au ramassage)
		"charge": charge,
		"charge_max": derived.charge_max,
		"portee": portee_cac,
		"attaque_profils": attaques,   # profils d'attaque (cac/jet/tir) ; ≠ "attaques" (compteur)
		"pos": {"x": 0, "y": 0},
		"facing": 0,
		"cells_moved": 0,
		"attaques": 0,
		"ramasses": 0,
		"consommes": 0,
		"sorts": 0,
		"competences": 0,
		# Actions perdues sur échec critique : `penalites` compte dans le budget du tour
		# courant, `dette_actions` reporte au suivant ce qui n'a pas pu être payé.
		"penalites": 0,
		"dette_actions": 0,
		# Esquive = malus au seuil de toucher PHYSIQUE des attaques subies (cc/cd,
		# jamais la magie). Somme des passives (competences_bonus) + effets actifs.
		"esquive": esquive_bonus(character),
		# Part PERMANENTE seule : _refresh_snapshot_stats y rajoute celle des effets
		# vivants, qui varie au fil du combat.
		"esquive_base": esquive_bonus(character, origines=("equipement", "competence")),
		# ── De quoi RECALCULER les dérivées quand un effet est posé ou expire ──
		"caracts_base": caracts_base,
		"equipment_bonus": equipment.model_dump() if hasattr(equipment, "model_dump") else dict(equipment or {}),
		"voc_niveau": voc_niveau,
		# Effets à durée VIVANTS : copies (jamais les entrées du doc perso, qui seraient
		# alors mutées par le combat avant même sa conclusion).
		"effets_actifs": [dict(eff) for eff in (character.get("effets_actifs") or [])],
		# Furtivité : tant que furtif, un monstre non-détecté ne vient pas au joueur.
		# Posée à l'entrée en combat (passives conditionnées au terrain) ou par une
		# active/un sort ; brisée par toute action offensive du joueur.
		"furtif": False,
		"furtivite_bonus": 0,
		"butin_ramasse": [],   # références {item, poids} des carcasses ramassées en combat
	}


def _pick_profil(profils: list, profil_weights: dict | None):
	"""Tire un profil parmi `profils` (déjà filtrés, p.ex. cap ville).

	Si `profil_weights` est fourni, tirage pondéré restreint aux profils présents
	dans `profils` (les ids inconnus / hors cap / poids ≤ 0 sont ignorés). Repli sur
	un tirage uniforme si aucun candidat pondéré ne subsiste.
	"""
	if not profils:
		return None
	if profil_weights:
		by_id = {p["_id"]: p for p in profils}
		candidates, poids = [], []
		for pid, w in profil_weights.items():
			p = by_id.get(pid)
			if p is not None and isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0:
				candidates.append(p)
				poids.append(w)
		if candidates:
			return random.choices(candidates, weights=poids, k=1)[0]
	return random.choice(profils)


def instantiate_monsters(
	especes: list, profils: list, nb: int, zone_tags: list,
	profil_weights: dict | None = None,
	espece_weights: dict | None = None,
) -> list:
	matching = [e for e in especes if set(e.get("tags", [])) & set(zone_tags)]
	pool = matching if matching else especes
	if not pool:
		return []

	# Focalisation : tirage d'espèce pondéré (défaut 1.0 par espèce — une cible absente
	# du pool est sans effet). Repli uniforme si les poids sont tous nuls.
	poids_especes = None
	if espece_weights:
		poids_especes = [max(0.0, espece_weights.get(e.get("_id"), 1.0)) for e in pool]
		if sum(poids_especes) <= 0:
			poids_especes = None

	monstres = []
	for i in range(nb):
		espece = (
			random.choices(pool, weights=poids_especes, k=1)[0]
			if poids_especes else random.choice(pool)
		)
		profil = _pick_profil(profils, profil_weights)
		monstres.append(build_monster_snapshot(espece, profil, i))

	return monstres


def build_monster_snapshot(espece: dict, profil: dict | None, idx: int) -> dict:
	"""Snapshot d'UN monstre (stats dérivées + XP) pour un profil donné. `profil is None`
	→ repli sur le point médian de l'espèce (niveau 1). Extrait de la boucle
	d'`instantiate_monsters` pour pouvoir reconstruire un monstre à profil FORCÉ (quête de
	chasse : l'élite recherchée) sans dupliquer la dérivation des stats."""
	if profil:
		base_stats = roll_monster_stats(espece, profil)
		niveau = profil.get("niveau", 1)
		profil_id = profil["_id"]
	else:
		base_stats = _espece_midpoint(espece)
		niveau = 1
		profil_id = None

	derived = compute_derived_stats(base_stats, niveau=niveau)
	# XP dérivée de la difficulté : niveau du profil + somme des stats du monstre.
	sum_stats = (
		base_stats.v + base_stats.f + base_stats.r + base_stats.ag
		+ base_stats.vol + base_stats.int_ + base_stats.cha + base_stats.ch
	)
	xp_reward = max(1, niveau * 4 + sum_stats // 10)

	return {
		"id": f"monstre_{idx}",
		"nom": espece.get("nom", "Monstre"),
		"espece_id": espece["_id"],
		# Un monstre porte les MÊMES champs de recalcul qu'un joueur (`caracts_base`,
		# `voc_niveau`, `esquive_base`, `effets_actifs`) : c'est ce qui rend
		# _refresh_snapshot_stats opérant sur lui, donc ce qui donne une prise à un
		# debuff. Il n'a ni équipement ni passive → `caracts_base` = ses stats brutes.
		"caracts_base": {
			"V": base_stats.v, "F": base_stats.f, "R": base_stats.r, "Ag": base_stats.ag,
			"Vol": base_stats.vol, "Int": base_stats.int_, "Cha": base_stats.cha,
			"Ch": base_stats.ch,
		},
		"voc_niveau": niveau,
		"esquive_base": 0,
		"effets_actifs": [],
		"profil_id": profil_id,
		"image": espece.get("image", ""),
		# Animation d'impact des attaques de CETTE espèce (vide = repli sur le canal
		# `monstre`). Copiée au snapshot : le doc `espece:*` n'est plus relu ensuite.
		"animation": str(espece.get("animation") or ""),
		"currentPV": max(1, derived.pv_max),
		"pv_max": max(1, derived.pv_max),
		"actions_restantes": _compute_actions_max(base_stats.ag, base_stats.v),
		"actions_max": _compute_actions_max(base_stats.ag, base_stats.v),
		"cc": derived.cc,
		"ag": base_stats.ag,
		# Vol/Int alimentent le jet de DÉTECTION contre un joueur furtif (repli
		# Int−10 puis Ag−30 pour les créatures sans volonté/intelligence).
		"vol": base_stats.vol,
		"int": base_stats.int_,
		# Ch : glissement des fenêtres de critique (_seuils_critiques). Beaucoup
		# d'espèces ont encore Ch = 0 en base → delta large en faveur du joueur.
		"ch": base_stats.ch,
		"pa": derived.pa,
		# Un monstre n'a pas d'équipement : son armure est NATURELLE, donc uniforme.
		# `pa_zones` vide ⇒ tout est global, la localisation ne change rien pour lui.
		"pa_zones": {},
		"pm_def": derived.pm_def,
		"degats_cc": derived.degats_cc,
		"initiative": derived.initiative,
		"deplacement": derived.deplacement,
		"portee": 1,
		"pos": {"x": 0, "y": 0},
		"cells_moved": 0,
		"attaques": 0,
		# Actions perdues sur échec critique (cf. _appliquer_fumble) — les monstres
		# fumblent comme les joueurs.
		"penalites": 0,
		"dette_actions": 0,
		"vivant": True,
		# Tags d'espèce embarqués : predateur/proie pilotent la chasse entre
		# monstres quand le joueur est furtif et non détecté.
		"tags": list(espece.get("tags", [])),
		"detecte": False,
		"xp_reward": xp_reward,
		"niveau": niveau,   # niveau du profil → pondère le tirage du poids de carcasse
	}


def create_combat_doc(
	character: dict, monstres: list, zone_tags: list, map_image: str,
	battle_map: dict | None = None,
	furtivite_initiale: int = 0,
	compagnons: list | None = None,
	montures: list | None = None,
	proteges: list | None = None,
) -> dict:
	joueur = build_joueur_snapshot(character, joueur_index=0)
	# Furtivité passive à l'entrée (conditions de terrain déjà évaluées par l'appelant
	# via competences.furtivite_passive) : posée AVANT resolve_first_turns pour que les
	# monstres à meilleure initiative testent leur détection dès le tour 1. Sur le
	# joueur principal SEUL (v1) : les compagnons entrent à découvert.
	if furtivite_initiale > 0:
		joueur["furtif"] = True
		joueur["furtivite_bonus"] = int(furtivite_initiale)
	# Compagnons recrutés (docs `aventurier:*`, miroirs du character) : mêmes snapshots
	# que le joueur — _place_actors et l'initiative gèrent déjà N joueurs.
	joueurs = [joueur] + [
		build_joueur_snapshot(c, joueur_index=i + 1)
		for i, c in enumerate(compagnons or [])
	]
	# Montures : elles SUIVENT le groupe sur la carte (elles portent la charge, on ne les
	# laisse pas à la porte) mais ne combattent pas. Snapshot standard — c'est ce qui les
	# rend ciblables par les monstres — puis on les marque `jouable: False` et on les
	# immobilise. Elles vivent dans `joueurs` : tout ce qui parcourt cette liste (ciblage,
	# placement, jetons alliés) les voit sans code neuf.
	montures_snaps = []
	for i, m in enumerate(montures or []):
		snap = build_joueur_snapshot(m, joueur_index=len(joueurs) + i)
		snap["jouable"] = False
		snap["est_monture"] = True
		snap["deplacement"] = 0
		snap["deplacement_base"] = 0
		# `derived.charge_max` vaut F×5 : sur une monture il faut le multiplicateur
		# d'espèce, sinon la répartition du butin de fin lui refuserait des carcasses
		# qu'elle peut parfaitement porter (/collect borne sur CETTE valeur).
		snap["charge_max"] = montures_util.charge_max_porteur(m)
		montures_snaps.append(snap)
	joueurs += montures_snaps

	# Personnes ESCORTÉES : même traitement qu'une monture — elles suivent le groupe, sont
	# sur la carte donc CIBLABLES, mais ne jouent pas. C'est tout l'enjeu de la quête : elles
	# n'ont aucun moyen de se défendre, et le joueur doit s'interposer.
	# ⚠️ Pas de `charge_max` recalculé, contrairement aux montures : un protégé ne porte pas
	# pour le groupe (il est absent de `porteurs_effectifs`), la dérivée standard suffit.
	proteges_snaps = []
	for i, p in enumerate(proteges or []):
		snap = build_joueur_snapshot(p, joueur_index=len(joueurs) + i)
		snap["jouable"] = False
		snap["est_protege"] = True
		snap["deplacement"] = 0
		snap["deplacement_base"] = 0
		proteges_snaps.append(snap)
	joueurs += proteges_snaps

	# ⚠️ `ordre_initiative` n'accueille QUE les jouables : une monture qui y figurerait
	# obtiendrait un tour que personne ne peut jouer (_resolve_until_player rendrait la
	# main au client sur un acteur qui n'a pas d'actions) — le combat s'arrêterait là.
	all_actors = [(j["id"], j["initiative"]) for j in joueurs if j.get("jouable", True)]
	all_actors += [(m["id"], m["initiative"]) for m in monstres]
	all_actors.sort(key=lambda x: x[1], reverse=True)
	ordre = [a[0] for a in all_actors]

	combat_id = f"combat:{uuid.uuid4().hex}"
	combat_doc = {
		"_id": combat_id,
		"type": "combat",
		"user_id": character["user_id"],
		"character_id": character["_id"],
		"status": "active",
		"tour": 1,
		"ordre_initiative": ordre,
		"acteur_courant_index": 0,
		"map_image": map_image,
		"zone_tags": zone_tags,
		"joueurs": joueurs,
		"monstres": monstres,
		"log": [{"tour": 1, "acteur": "Système", "kind": "sys", "texte": "Le combat commence !"}],
		"xp_gagnee": 0,
	}
	# On référence le lieu battle map (grille statique non dupliquée). `cells` est
	# résolu à la demande via get_combat_grid(). Repli = grille ouverte.
	# `nav` DOIT être inclus : le placement (_reachable_region) suit les mêmes règles que
	# le déplacement (_find_path, qui charge nav via get_combat_grid). Sans lui, une carte
	# scindée par des masques nav (ex. chemin2) ferait spawn un monstre dans une région
	# nav-séparée du joueur → injoignable malgré la garantie de _place_actors.
	if battle_map:
		combat_doc["battle_map_id"] = battle_map["_id"]
		grid = {"dims": battle_map["dimensions"], "cells": battle_map["cells"],
				"nav": battle_map.get("nav", {})}
	else:
		grid = _open_grid()
		combat_doc["grid_dims"] = grid["dims"]
	_place_actors(combat_doc, grid)
	return combat_doc


# ── Helpers internes ────────────────────────────────────────────────────────

def _get_joueur(combat_doc: dict, actor_id: str) -> dict | None:
	for j in combat_doc["joueurs"]:
		if j["id"] == actor_id:
			return j
	return None


def _get_monstre(combat_doc: dict, actor_id: str) -> dict | None:
	for m in combat_doc["monstres"]:
		if m["id"] == actor_id:
			return m
	return None


def _hit_threshold(attaquant_cc: int, defenseur_ag: int) -> int:
	"""Seuil de réussite sur un d100 (jet <= seuil = touché).

	Jet sous CC, difficulté = Ag du défenseur : seuil = 50 + CC - Ag.
	Donc CC == Ag → 50 %. Clampé à [5, 95] pour garder toujours une marge.
	"""
	return max(5, min(95, 50 + attaquant_cc - defenseur_ag))


def _defense_physique(defenseur: dict) -> int:
	"""Difficulté défensive contre un jet PHYSIQUE (cc/cd) : Ag + esquive.

	SOURCE UNIQUE des trois sites qui résolvent un jet martial — attaque d'arme
	(`_do_attack_on`), compétence à `jet` cc/cd, et sort de contact à `jet` cc/cd. Les
	compétences ne lisaient que l'Ag : un buff d'esquive sur la cible y était ignoré,
	alors qu'il comptait face à une arme. La magie, elle, ne passe jamais par ici — elle
	se résout sur la pm_def, où l'esquive n'a rien à faire.
	"""
	return int(defenseur.get("ag", 0) or 0) + int(defenseur.get("esquive", 0) or 0)


def _degats_competence(joueur: dict, competence: dict, effets: dict) -> str:
	"""Notation de dégâts d'une compétence — SOURCE UNIQUE.

	Une frappe de CORPS À CORPS (`jet: "cc"`) est un coup PORTÉ AVEC l'arme, pas un effet à
	côté : elle AJOUTE les dégâts d'arme du porteur (`degats_cc` du snapshot = dé de Force +
	dés et bonus de l'arme équipée) à ses propres dés. Sans quoi une active coûtant 1 action
	ET des PM frappait moins fort qu'une attaque ordinaire gratuite.

	⚠️ `cd` et `magique` en sont EXCLUS : un tir emprunte déjà l'arc par son jet, et une
	frappe magique ne se négocie pas au poids de la hache.
	⚠️ Une compétence SANS dés (pur debuff : entrave, cri de guerre) reste sans dés — sinon
	une prise qui ne blesse pas deviendrait une attaque.
	⚠️ Snapshot sans `degats_cc` (combat déjà en base) ⇒ la compétence garde ses seuls dés :
	aucune migration.
	"""
	base = (effets or {}).get("degats", "")
	if not base or (competence or {}).get("jet", "cc") != "cc":
		return base
	return concat_degats(joueur.get("degats_cc", ""), base)


def _magic_hit_threshold(toucher_magique: int, cible_pm_def: int) -> int:
	"""Seuil de réussite d'un sort offensif sur d100 (miroir de _hit_threshold) :
	50 + toucher magique − défense magique de la cible, clampé [5, 95]. La défense
	magique remplace l'esquive (Ag) ET l'armure : les dégâts d'un sort qui touche ne
	sont PAS réduits par les PA (l'armure physique n'arrête pas la magie)."""
	return max(5, min(95, 50 + toucher_magique - cible_pm_def))


def _seuils_critiques(attaquant: dict, defenseur: dict) -> tuple:
	"""Fenêtres de critique d'un jet d100 offensif, glissées par l'écart de Chance.

	delta = Ch attaquant − Ch cible, divisé par CRIT_CHANCE_DIVISEUR : la chance élargit
	la réussite critique ET repousse l'échec critique, symétriquement. Les deux world-vars
	génériques restent des garde-fous — un jet ≤ CRIT_REUSSITE_MAX est TOUJOURS une réussite
	critique, un jet ≥ CRIT_ECHEC_MIN toujours un échec —, donc le glissement ne peut que
	jouer en faveur du plus chanceux. Renvoie (seuil_reussite, seuil_echec).

	Snapshot sans `ch` (combat créé avant la feature) → delta 0 = fenêtres de base.
	"""
	base_ok = int(character_stats.CRIT_REUSSITE_MAX)
	base_ko = int(character_stats.CRIT_ECHEC_MIN)
	div = int(character_stats.CRIT_CHANCE_DIVISEUR)
	if div <= 0:
		return base_ok, base_ko          # mécanique désactivée
	glissement = (attaquant.get("ch", 0) - defenseur.get("ch", 0)) // div
	return max(base_ok, base_ok + glissement), min(base_ko, base_ko + glissement)


def _resoudre_jet(attaquant: dict, defenseur: dict, seuil: int) -> dict:
	"""Un jet d100 offensif : {roll, seuil, touche, critique, fumble, mult_degats}.

	Le critique PRIME sur le seuil de toucher : une réussite critique touche même si le
	seuil était raté, un échec critique rate même si le seuil passait. Si un réglage
	extrême faisait se croiser les deux fenêtres, la réussite l'emporte (ordre des tests).
	"""
	crit_ok, crit_ko = _seuils_critiques(attaquant, defenseur)
	roll = random.randint(1, 100)
	if roll <= crit_ok:
		return {"roll": roll, "seuil": seuil, "touche": True,
				"critique": True, "fumble": False, "mult_degats": 2}
	if roll >= crit_ko:
		return {"roll": roll, "seuil": seuil, "touche": False,
				"critique": False, "fumble": True, "mult_degats": 1}
	return {"roll": roll, "seuil": seuil, "touche": roll <= seuil,
			"critique": False, "fumble": False, "mult_degats": 1}


def _appliquer_fumble(combat_doc: dict, acteur: dict) -> None:
	"""Échec critique : coûte une action de plus que celle déjà dépensée.

	S'il n'en reste aucune (le fumble était la dernière action du tour), la pénalité est
	REPORTÉE au tour suivant via `dette_actions` — sans ce report, le clamp `max(0, …)`
	de _refresh_actions l'avalerait silencieusement. À appeler APRÈS l'incrément du
	compteur d'action et son _refresh_actions, sinon actions_restantes est périmé.
	"""
	if acteur.get("actions_restantes", 0) > 0:
		acteur["penalites"] = acteur.get("penalites", 0) + 1
		_refresh_actions(acteur)
		texte = f"{acteur['nom']} perd pied : une action de perdue !"
	else:
		acteur["dette_actions"] = acteur.get("dette_actions", 0) + 1
		texte = f"{acteur['nom']} perd pied : il entamera son prochain tour avec une action de moins !"
	combat_doc["log"].append({
		"tour": combat_doc["tour"],
		"acteur": acteur["nom"],
		"kind": "sys",
		"texte": texte,
	})


def _flee_threshold(joueur_init: int, monstre_init_max: int) -> int:
	"""Seuil de fuite sur d100 : 50 + init joueur - meilleure init ennemie, clampé [5, 95]."""
	return max(5, min(95, 50 + joueur_init - monstre_init_max))


def _check_victory(combat_doc: dict) -> None:
	if all(not m["vivant"] for m in combat_doc["monstres"]):
		xp = sum(m["xp_reward"] for m in combat_doc["monstres"])
		combat_doc["xp_gagnee"] = xp
		combat_doc["status"] = "victoire"
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": "Système",
			"kind": "sys",
			"texte": f"Victoire ! {xp} XP gagnés.",
		})


def _do_attack_on(combat_doc: dict, attaquant: dict, defenseur: dict) -> None:
	"""Attaque physique d'un monstre sur un défenseur — le joueur (cas normal) OU un
	autre monstre (chasse prédateur/proie pendant la furtivité du joueur). L'`esquive`
	du défenseur gonfle sa difficulté défensive (l'Ag), jamais sur la magie.

	Décompte l'action de l'attaquant lui-même : un échec critique en coûte une SECONDE
	(ou l'endette pour le tour suivant), ce qui exige que le budget soit déjà à jour."""
	est_joueur = str(defenseur.get("id", "")).startswith("joueur_")
	seuil = _hit_threshold(attaquant["cc"],
						   _defense_physique(defenseur))
	jet = _resoudre_jet(attaquant, defenseur, seuil)
	roll = jet["roll"]
	attaquant["attaques"] = attaquant.get("attaques", 0) + 1
	_refresh_actions(attaquant)
	if jet["touche"]:
		# Formule partagée avec le joueur, les sorts, les compétences et le simulateur.
		# La zone frappée décide des PA opposés (pièce couvrante + protections globales).
		zone = tirer_localisation()
		ou = f" {ZONE_LIBELLE[zone]}" if zone in ZONE_LIBELLE else ""
		dmg = calculer_degats(attaquant, defenseur, attaquant["degats_cc"],
							  jet["mult_degats"], "cc", zone=zone)
		defenseur["currentPV"] = max(0, defenseur["currentPV"] - dmg)
		# Un tour de monstre est entièrement résolu côté serveur : sans cette charge sur
		# l'entrée de journal, un coup encaissé par le joueur ne pourrait jamais s'animer.
		# ⚠️ L'ATTAQUANT est en état lui aussi, alors que ses PV ne bougent pas : c'est sa
		# POSITION qui compte. Un prédateur qui fond sur sa proie (_chasse_ou_erre) n'écrit
		# aucune ligne de déplacement — sans lui ici, il n'aurait aucune ligne où arriver.
		combat_doc["log"].append(_avec_etat(_avec_vfx({
			"tour": combat_doc["tour"],
			"acteur": attaquant["nom"],
			"kind": "crit" if jet["critique"] else "hit",
			"texte": (
				f"{attaquant['nom']} porte un COUP CRITIQUE à {defenseur['nom']}{ou} : {dmg} dégâts ! "
				f"(PV : {defenseur['currentPV']}/{defenseur['pv_max']})"
				if jet["critique"] else
				f"{attaquant['nom']} touche {defenseur['nom']}{ou} pour {dmg} dégâts ! "
				f"(PV : {defenseur['currentPV']}/{defenseur['pv_max']})"
			),
		}, "monstre", defenseur.get("id", ""), attaquant.get("animation"), attaquant.get("id", "")),
			attaquant, defenseur))
		if defenseur["currentPV"] <= 0:
			if est_joueur:
				# KO d'un membre du groupe : le combat continue tant qu'il reste un
				# joueur debout — la défaite n'arrive que TOUS à terre.
				est_monture = defenseur.get("est_monture")
				est_protege = defenseur.get("est_protege")
				# La cargaison vit sur le DOC de la monture, pas sur son snapshot : on se
				# contente de la marquer ici, `finalize_combat` déversera son sac dans le
				# butin disponible (là où le doc est chargé, et sauvé). Une personne ESCORTÉE
				# porte le même marqueur `morte` — c'est `_finalize_protege` qui en tirera la
				# mort et l'échec de la quête, au même endroit et pour la même raison.
				# ⚠️ Marqué AVANT la ligne, qui porte l'état du défenseur (`morte`).
				if est_monture or est_protege:
					defenseur["morte"] = True
				if est_monture:
					texte_ko = f"{defenseur['nom']} s'effondre — sa charge se répand au sol !"
				elif est_protege:
					# ⚠️ Tournure NEUTRE en genre : le snapshot ne porte pas le sexe, et une
					# escorte peut viser n'importe qui — un accord fautif se verrait à chaque
					# partie. (Même précaution que la règle « aucun pronom genré » des dialogues.)
					texte_ko = f"{defenseur['nom']} s'effondre… La promesse n'aura pas tenu."
				else:
					texte_ko = f"{defenseur['nom']} est à terre !"
				combat_doc["log"].append(_avec_etat({
					"tour": combat_doc["tour"],
					"acteur": "Système",
					"kind": "sys",
					"texte": texte_ko,
				}, defenseur))
				# ⚠️ `_combattants_vivants` et non la liste brute : une monture debout ne
				# doit pas empêcher la défaite d'être déclarée (plus personne ne joue).
				if not _combattants_vivants(combat_doc):
					combat_doc["status"] = "defaite"
					combat_doc["log"].append({
						"tour": combat_doc["tour"],
						"acteur": "Système",
						"kind": "sys",
						"texte": "Tout le groupe est à terre… Défaite.",
					})
			else:
				# Proie tuée par un monstre : le joueur n'en tire pas l'XP (kill qu'il
				# n'a pas fait) mais la carcasse reste dépeçable (butin conservé).
				defenseur["vivant"] = False
				defenseur["tue_par_monstre"] = True
				defenseur["xp_reward"] = 0
				combat_doc["log"].append(_avec_etat({
					"tour": combat_doc["tour"],
					"acteur": attaquant["nom"],
					"kind": "kill",
					"texte": f"{attaquant['nom']} abat {defenseur['nom']} !",
				}, defenseur))
				_check_victory(combat_doc)
	else:
		# Rien n'a changé chez le défenseur, mais l'attaquant vient peut-être d'arriver
		# (chasse d'une proie, sans ligne de déplacement) : sa position doit se poser ici.
		combat_doc["log"].append(_avec_etat(_avec_vfx({
			"tour": combat_doc["tour"],
			"acteur": attaquant["nom"],
			"kind": "fumble" if jet["fumble"] else "miss",
			"texte": (
				f"{attaquant['nom']} rate LAMENTABLEMENT son attaque ! (jet {roll} / seuil {seuil})"
				if jet["fumble"] else
				f"{attaquant['nom']} rate son attaque ! (jet {roll} / seuil {seuil})"
			),
		}, "fumble" if jet["fumble"] else "miss", defenseur.get("id", ""),
			acteur_id=attaquant.get("id", "")), attaquant))
		if jet["fumble"]:
			_appliquer_fumble(combat_doc, attaquant)


def _joueurs_vivants(combat_doc: dict) -> list:
	"""Tous les acteurs du camp du joueur encore debout, MONTURES COMPRISES : c'est la
	liste du CIBLAGE (un monstre peut s'en prendre à une bête de somme). Pour savoir si
	le combat est perdu, voir `_combattants_vivants` — les deux ne se confondent pas."""
	return [j for j in combat_doc["joueurs"] if j.get("currentPV", 0) > 0]


def _combattants_vivants(combat_doc: dict) -> list:
	"""Les acteurs encore debout qui peuvent AGIR. ⚠️ Distinct de `_joueurs_vivants` :
	une monture ne joue pas. Si on comptait sur elle pour décider de la défaite, un groupe
	entièrement à terre avec une monture indemne ne perdrait jamais — et plus personne ne
	pouvant jouer, le combat resterait bloqué indéfiniment."""
	return [j for j in _joueurs_vivants(combat_doc) if j.get("jouable", True)]


def _cible_joueur(combat_doc: dict, monstre: dict) -> dict | None:
	"""Cible de l'IA d'un monstre : le joueur VIVANT le plus proche (Chebyshev), en
	excluant un joueur furtif non détecté (il ne le voit pas). None si aucun joueur
	visible — tous furtifs non détectés (le monstre tentera une détection) ou tous KO."""
	visibles = [
		j for j in _joueurs_vivants(combat_doc)
		if not (j.get("furtif") and not monstre.get("detecte"))
	]
	if not visibles:
		return None
	return min(visibles, key=lambda j: _cheby(monstre, j))


def _do_monster_attack(combat_doc: dict, monstre: dict, joueur: dict) -> None:
	_do_attack_on(combat_doc, monstre, joueur)


def _monster_step_toward(combat_doc: dict, monstre: dict, joueur: dict, grid: dict) -> bool:
	"""Avance le monstre d'une case vers le joueur via A*. Retourne True si déplacé."""
	blocked = _occupied_set(combat_doc, exclude=monstre)
	path = _find_path(
		grid["cells"], grid["dims"],
		(monstre["pos"]["x"], monstre["pos"]["y"]),
		(joueur["pos"]["x"], joueur["pos"]["y"]),
		blocked,
		grid.get("nav", {}),
		flying=_can_fly(monstre),
	)
	if not path or len(path) < 2:
		return False
	nxt = path[1]
	# Ne pas entrer sur la case du joueur (cible) ni une case occupée.
	if nxt == (joueur["pos"]["x"], joueur["pos"]["y"]) or nxt in blocked:
		return False
	# Vérifier qu'il reste assez d'AP pour ce pas (coût proportionnel).
	projected = (monstre["attaques"] + monstre.get("penalites", 0)
				 + _move_ap_used_for(monstre, monstre["cells_moved"] + 1))
	if projected > monstre["actions_max"]:
		return False
	monstre["pos"] = {"x": nxt[0], "y": nxt[1]}
	monstre["cells_moved"] += 1
	_refresh_actions(monstre)
	return True


def _detection_threshold(monstre: dict, joueur: dict) -> int:
	"""Seuil du jet de détection d'un joueur furtif (d100, jet ≤ seuil = repéré).
	Compétence de détection = Vol du monstre, repli Int−10 (créature sans volonté),
	repli Ag−30 (créature sans intelligence). Difficulté = Ag du joueur + son bonus de
	furtivité + la DISTANCE qui les sépare, à raison de DETECTION_DISTANCE_FACTEUR points
	par case (plus on est loin, plus on est dur à repérer — variable de monde, lue via le
	module pour rester réglable à chaud). Même idiome que _hit_threshold : 50 + skill −
	difficulté, [5, 95]."""
	vol = int(monstre.get("vol", 0) or 0)
	intel = int(monstre.get("int", 0) or 0)
	if vol > 0:
		skill = vol
	elif intel > 0:
		skill = intel - 10
	else:
		skill = int(monstre.get("ag", 0) or 0) - 30
	cases = _cheby(monstre, joueur) if monstre.get("pos") and joueur.get("pos") else 0
	difficulte = (int(joueur.get("ag", 0) or 0)
				  + int(joueur.get("furtivite_bonus", 0) or 0)
				  + cases * max(0, character_stats.DETECTION_DISTANCE_FACTEUR))
	return max(5, min(95, 50 + skill - difficulte))


def _tenter_detection(combat_doc: dict, monstre: dict, joueur: dict,
					  echec_texte: str | None = None) -> bool:
	"""Jet de détection d100 (≤ seuil = repéré). Une réussite est DÉFINITIVE pour le
	combat. Tiré en début de tour du monstre, ou par la cible d'une attaque à distance."""
	seuil = _detection_threshold(monstre, joueur)
	roll = random.randint(1, 100)
	if roll <= seuil:
		monstre["detecte"] = True
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "sys",
			"texte": f"{monstre['nom']} vous repère ! (jet {roll} / seuil {seuil})",
		})
		return True
	if echec_texte:
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "sys",
			"texte": f"{echec_texte} (jet {roll} / seuil {seuil})",
		})
	return False


def _briser_furtivite(combat_doc: dict, joueur: dict) -> None:
	"""Toute action OFFENSIVE du joueur (attaque, sort ou compétence sur un ennemi)
	révèle sa position — se déplacer/consommer/ramasser ne brise pas la furtivité."""
	if not joueur.get("furtif"):
		return
	joueur["furtif"] = False
	joueur["furtivite_bonus"] = 0
	combat_doc["log"].append({
		"tour": combat_doc["tour"],
		"acteur": joueur["nom"],
		"kind": "sys",
		"texte": f"{joueur['nom']} sort de l'ombre : tous les ennemis l'ont repéré !",
	})


def _activer_furtivite(combat_doc: dict, joueur: dict, bonus: int) -> None:
	"""Pose l'état furtif (compétence active ou sort, `effets.furtivite > 0`) et efface
	la détection de TOUS les monstres : chacun devra réussir un nouveau jet."""
	joueur["furtif"] = True
	joueur["furtivite_bonus"] = max(int(joueur.get("furtivite_bonus", 0) or 0), int(bonus))
	for m in combat_doc["monstres"]:
		m["detecte"] = False
	combat_doc["log"].append({
		"tour": combat_doc["tour"],
		"acteur": joueur["nom"],
		"kind": "sys",
		"texte": f"{joueur['nom']} se fond dans les ombres…",
	})


def _furtivite_apres_offensive(combat_doc: dict, joueur: dict, cible: dict | None,
							   distant: bool) -> None:
	"""Sort du joueur furtif après une action offensive. Corps à corps = révélation
	totale ; à distance = seule la CIBLE tente un jet de détection (tuée d'un trait ou
	déjà alertée : aucun jet — l'embuscade tient toujours pour les autres)."""
	if not joueur.get("furtif"):
		return
	if not distant:
		_briser_furtivite(combat_doc, joueur)
		return
	if not cible or not cible.get("vivant") or cible.get("detecte"):
		return
	_tenter_detection(
		combat_doc, cible, joueur,
		echec_texte=f"{cible['nom']} cherche d'où vient le coup sans repérer {joueur['nom']} !",
	)


def _proie_la_plus_proche(combat_doc: dict, predateur: dict) -> dict | None:
	"""Le plus proche monstre vivant taggé `proie` (≠ lui-même), pour la chasse d'un
	prédateur pendant que le joueur est furtif. None si aucune proie sur la carte."""
	proies = [m for m in combat_doc["monstres"]
			  if m["vivant"] and m["id"] != predateur["id"]
			  and "proie" in (m.get("tags") or [])]
	if not proies:
		return None
	return min(proies, key=lambda m: _cheby(predateur, m))


def _wander_step(combat_doc: dict, monstre: dict, grid: dict) -> bool:
	"""Un pas d'errance : case voisine aléatoire praticable (mêmes règles que le
	déplacement — nav bitmask, terrain, cases occupées). Retourne True si déplacé."""
	blocked = _occupied_set(combat_doc, exclude=monstre)
	x, y = monstre["pos"]["x"], monstre["pos"]["y"]
	cells, dims, nav = grid["cells"], grid["dims"], grid.get("nav", {})
	flying = _can_fly(monstre)
	options = []
	for dx, dy in MOVE_OFFSETS:
		nx, ny = x + dx, y + dy
		if not (0 <= nx < dims["x"] and 0 <= ny < dims["y"]):
			continue
		if (nx, ny) in blocked or not nav_allows(nav, x, y, dx, dy):
			continue
		if not _walkable(cells, nx, ny, flying):
			continue
		options.append((nx, ny))
	if not options:
		return False
	projected = (monstre["attaques"] + monstre.get("penalites", 0)
				 + _move_ap_used_for(monstre, monstre["cells_moved"] + 1))
	if projected > monstre["actions_max"]:
		return False
	nx, ny = random.choice(options)
	monstre["pos"] = {"x": nx, "y": ny}
	monstre["cells_moved"] += 1
	_refresh_actions(monstre)
	return True


def _chasse_ou_erre(combat_doc: dict, monstre: dict, grid: dict) -> None:
	"""Tour alternatif d'un monstre qui n'a PAS détecté le joueur furtif : un prédateur
	chasse la proie la plus proche (mêmes règles d'attaque, la victime ne rapporte pas
	d'XP mais reste au butin) ; sinon il erre au hasard."""
	proie = None
	if "predateur" in (monstre.get("tags") or []):
		proie = _proie_la_plus_proche(combat_doc, monstre)
	if proie is not None:
		portee = monstre.get("portee", 1)
		safety = 0
		while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
			   and proie["vivant"] and _cheby(monstre, proie) > portee
			   and monstre["cells_moved"] < monstre.get("deplacement", 1)
			   and safety < 100):
			safety += 1
			if not _monster_step_toward(combat_doc, monstre, proie, grid):
				break
		while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
			   and proie["vivant"] and _cheby(monstre, proie) <= portee):
			_do_attack_on(combat_doc, monstre, proie)   # décompte l'action lui-même
		return
	# Errance : quelques pas au hasard, sans jamais fondre sur le joueur.
	steps = 0
	safety = 0
	while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
		   and monstre["cells_moved"] < monstre.get("deplacement", 1)
		   and safety < 100):
		safety += 1
		if not _wander_step(combat_doc, monstre, grid):
			break
		steps += 1
	if steps > 0:
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "move",
			"texte": f"{monstre['nom']} erre en cherchant du regard ({steps} case(s)).",
		}, monstre))


def _run_monster_turn(combat_doc: dict, monstre: dict, grid: dict) -> None:
	"""Tour d'un monstre : se rapprocher du joueur (A*) puis attaquer si à portée.
	Joueur FURTIF : le monstre doit d'abord le détecter (jet en début de tour, réussite
	définitive pour le combat) ; tant qu'il ne l'a pas repéré, il ne vient pas vers lui
	— un prédateur chasse une proie, les autres errent."""
	_reset_turn_budget(monstre, combat_doc)
	portee = monstre.get("portee", 1)

	# Cible résolue en début de tour : le joueur vivant le plus proche. Aucun joueur
	# visible = tous furtifs non détectés → jet de détection sur le plus proche, puis
	# chasse/errance en cas d'échec (comportement furtivité inchangé).
	joueur = _cible_joueur(combat_doc, monstre)
	if joueur is None:
		furtifs = [j for j in _joueurs_vivants(combat_doc) if j.get("furtif")]
		cible_furtive = min(furtifs, key=lambda j: _cheby(monstre, j)) if furtifs else None
		if cible_furtive is None or not _tenter_detection(combat_doc, monstre, cible_furtive):
			_chasse_ou_erre(combat_doc, monstre, grid)
			idx = combat_doc["acteur_courant_index"] + 1
			if idx >= len(combat_doc["ordre_initiative"]):
				idx = 0
				combat_doc["tour"] += 1
			combat_doc["acteur_courant_index"] = idx
			return
		joueur = cible_furtive

	# Phase déplacement : avancer vers le joueur tant qu'éloigné et budget dispo.
	steps = 0
	safety = 0
	while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
		   and _cheby(monstre, joueur) > portee
		   and monstre["cells_moved"] < monstre.get("deplacement", 1)
		   and safety < 100):
		safety += 1
		if not _monster_step_toward(combat_doc, monstre, joueur, grid):
			break
		steps += 1
	if steps > 0:
		# Le jeton ne saute plus à sa case d'arrivée dès la réponse : il y glisse quand
		# cette ligne est révélée, puis frappe. Le chemin case par case n'est pas rejoué
		# (un seul log `move` agrégé par tour) — c'est un glissement, pas une marche.
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "move",
			"texte": f"{monstre['nom']} avance vers {joueur['nom']} ({steps} case(s)).",
		}, monstre))

	# Phase attaque : frapper tant qu'à portée et qu'il reste des actions. Si la cible
	# tombe (KO) en cours de tour, le monstre se rabat sur le joueur visible suivant.
	while combat_doc["status"] == "active" and monstre["actions_restantes"] > 0:
		if joueur is None or joueur.get("currentPV", 0) <= 0:
			joueur = _cible_joueur(combat_doc, monstre)
		if joueur is None or _cheby(monstre, joueur) > portee:
			break
		_do_monster_attack(combat_doc, monstre, joueur)   # décompte l'action lui-même

	idx = combat_doc["acteur_courant_index"] + 1
	if idx >= len(combat_doc["ordre_initiative"]):
		idx = 0
		combat_doc["tour"] += 1
	combat_doc["acteur_courant_index"] = idx


def _resolve_until_player(combat_doc: dict, grid: dict, start_at_current: bool = False) -> None:
	"""Run monster turns until it's a player's turn.

	start_at_current=True  : process the actor at acteur_courant_index first (combat init).
	start_at_current=False : advance past the current actor first (after player action).
	"""
	ordre = combat_doc["ordre_initiative"]
	max_iter = len(ordre) * 20

	if not start_at_current:
		# Move past current actor before entering the loop
		idx = combat_doc["acteur_courant_index"] + 1
		if idx >= len(ordre):
			idx = 0
			combat_doc["tour"] += 1
		combat_doc["acteur_courant_index"] = idx

	for _ in range(max_iter):
		if combat_doc["status"] != "active":
			break
		actor_id = ordre[combat_doc["acteur_courant_index"]]
		if actor_id.startswith("joueur_"):
			joueur = _get_joueur(combat_doc, actor_id)
			if joueur and joueur.get("currentPV", 0) > 0:
				_reset_turn_budget(joueur, combat_doc)
				break
			# Joueur KO (à terre) : son tour est sauté, comme un monstre mort.
			idx = combat_doc["acteur_courant_index"] + 1
			if idx >= len(ordre):
				idx = 0
				combat_doc["tour"] += 1
			combat_doc["acteur_courant_index"] = idx
			continue
		monstre = _get_monstre(combat_doc, actor_id)
		if not monstre or not monstre["vivant"]:
			# Dead monster — skip
			idx = combat_doc["acteur_courant_index"] + 1
			if idx >= len(ordre):
				idx = 0
				combat_doc["tour"] += 1
			combat_doc["acteur_courant_index"] = idx
			continue
		_run_monster_turn(combat_doc, monstre, grid)


def _advance_and_resolve(combat_doc: dict, grid: dict) -> None:
	"""After a player action: advance past the player and resolve all monster turns."""
	_resolve_until_player(combat_doc, grid, start_at_current=False)


def resolve_first_turns(combat_doc: dict) -> None:
	"""Called after combat creation: if monsters go first, resolve their turns."""
	_resolve_until_player(combat_doc, get_combat_grid(combat_doc), start_at_current=True)


# ── API publique ────────────────────────────────────────────────────────────

def resolve_action(
	combat_doc: dict, action_type: str, cible_id: str | None = None,
	dx: int | None = None, dy: int | None = None, sens: int | None = None,
	mode: str | None = None, item: dict | None = None, sort: dict | None = None,
	competence: dict | None = None,
) -> dict:
	ordre = combat_doc["ordre_initiative"]
	actor_id = ordre[combat_doc["acteur_courant_index"]]

	if not actor_id.startswith("joueur_"):
		return {"error": "Ce n'est pas le tour du joueur."}

	joueur = _get_joueur(combat_doc, actor_id)
	if not joueur:
		return {"error": "Joueur introuvable."}
	if joueur.get("currentPV", 0) <= 0:
		# Garde défensive : un joueur à terre ne devrait jamais avoir la main
		# (_resolve_until_player le saute), mais un doc en vol ne doit pas agir.
		return {"error": f"{joueur['nom']} est à terre."}
	if joueur["actions_restantes"] <= 0:
		return {"error": "Plus d'actions disponibles."}

	portee = joueur.get("portee", 1)
	grid = get_combat_grid(combat_doc)
	result: dict = {}

	if action_type == "deplacer":
		if dx is None or dy is None:
			return {"error": "Direction manquante."}
		dx = max(-1, min(1, int(dx)))
		dy = max(-1, min(1, int(dy)))
		if dx == 0 and dy == 0:
			return {"error": "Direction nulle."}

		dims, cells = grid["dims"], grid["cells"]
		nx, ny = joueur["pos"]["x"] + dx, joueur["pos"]["y"] + dy
		if nx < 0 or nx >= dims["x"] or ny < 0 or ny >= dims["y"]:
			return {"error": "Hors de la zone."}
		if not _walkable(cells, nx, ny, _can_fly(joueur)):
			return {"error": "Terrain infranchissable."}
		if not nav_allows(grid.get("nav", {}), joueur["pos"]["x"], joueur["pos"]["y"], dx, dy):
			return {"error": "Direction bloquée."}
		if _occupied_at(combat_doc, nx, ny):
			return {"error": "Case occupée."}
		if joueur["cells_moved"] >= joueur.get("deplacement", 1):
			return {"error": "Budget de déplacement épuisé."}
		projected = (joueur["attaques"] + joueur.get("penalites", 0)
					 + _move_ap_used_for(joueur, joueur["cells_moved"] + 1))
		if projected > joueur["actions_max"]:
			return {"error": "Plus d'actions pour se déplacer."}

		joueur["pos"] = {"x": nx, "y": ny}
		joueur["cells_moved"] += 1
		_refresh_actions(joueur)
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "move",
			"texte": f"{joueur['nom']} se déplace en [{nx},{ny}].",
		}, joueur))
		result = {"moved": True, "pos": joueur["pos"]}

	elif action_type == "tourner":
		# Rotation ±90° (caméra). Coûte une case du budget de déplacement.
		if sens not in (-1, 1):
			return {"error": "Sens de rotation invalide."}
		if joueur["cells_moved"] >= joueur.get("deplacement", 1):
			return {"error": "Budget de déplacement épuisé."}
		projected = (joueur["attaques"] + joueur.get("penalites", 0)
					 + _move_ap_used_for(joueur, joueur["cells_moved"] + 1))
		if projected > joueur["actions_max"]:
			return {"error": "Plus d'actions pour pivoter."}

		joueur["facing"] = (joueur.get("facing", 0) + sens * 90) % 360
		joueur["cells_moved"] += 1
		_refresh_actions(joueur)
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "move",
			"texte": f"{joueur['nom']} pivote ({'droite' if sens > 0 else 'gauche'}).",
		}, joueur))
		result = {"turned": True, "facing": joueur["facing"]}

	elif action_type == "attaquer":
		alive = [m for m in combat_doc["monstres"] if m["vivant"]]
		if not alive:
			return {"error": "Aucune cible disponible."}

		# Profil d'attaque selon le mode demandé (arme), repli sur la mêlée (cac).
		attaques = joueur.get("attaque_profils") or []
		profil = next((a for a in attaques if a["mode"] == mode), None) if mode else None
		if profil is None:
			profil = next((a for a in attaques if a["mode"] == "cac"), None)
		if profil is None:
			profil = {"mode": "cac", "portee": joueur.get("portee", 1), "ranged": False,
					  "toucher": "cc", "degats": "degats_cc"}
		atk_portee = max(1, int(profil.get("portee", 1)))
		is_ranged = bool(profil.get("ranged"))
		skill = joueur.get("cd" if profil.get("toucher") == "cd" else "cc", 0)
		notation = joueur.get(profil.get("degats", "degats_cc")) or joueur.get("degats_cc", "1D4")

		if cible_id:
			monstre = _get_monstre(combat_doc, cible_id)
			if not monstre or not monstre["vivant"]:
				return {"error": "Cible invalide."}
		else:
			candidats = [m for m in alive if _cheby(joueur, m) <= atk_portee]
			if not candidats:
				return {"error": "Aucune cible à portée. Rapprochez-vous."}
			monstre = candidats[0]

		# Règles de combat à distance (jet/tir) : pas d'engagement au corps à corps + ligne de vue.
		if is_ranged:
			if any(m["vivant"] and _cheby(joueur, m) <= 1 for m in combat_doc["monstres"]):
				return {"error": "Un ennemi vous menace au corps à corps : impossible de tirer."}
			if not _line_of_sight(grid["cells"], joueur["pos"]["x"], joueur["pos"]["y"],
								   monstre["pos"]["x"], monstre["pos"]["y"]):
				return {"error": "Ligne de vue obstruée."}
		if _cheby(joueur, monstre) > atk_portee:
			return {"error": "Cible hors de portée."}

		seuil = _hit_threshold(skill, _defense_physique(monstre))
		jet = _resoudre_jet(joueur, monstre, seuil)
		roll = jet["roll"]
		if jet["touche"]:
			zone = tirer_localisation()
			ou = f" {ZONE_LIBELLE[zone]}" if zone in ZONE_LIBELLE else ""
			dmg = calculer_degats(joueur, monstre, notation, jet["mult_degats"],
								  profil.get("toucher", "cc"), zone=zone)
			monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
			# L'animation suit le MODE de l'arme (cac/jet/tir), avec celle de l'arme elle-même
			# en priorité : le profil la porte depuis le snapshot, aucun doc n'est relu ici.
			anim_arme = profil.get("animation")
			if monstre["currentPV"] <= 0:
				monstre["vivant"] = False
				combat_doc["log"].append(_avec_etat(_avec_vfx({
					"tour": combat_doc["tour"],
					"acteur": joueur["nom"],
					"kind": "kill",
					"texte": (
						f"{joueur['nom']} porte un COUP CRITIQUE et élimine {monstre['nom']} !"
						if jet["critique"] else
						f"{joueur['nom']} élimine {monstre['nom']} !"
					),
				}, profil.get("mode", "cac"), monstre.get("id", ""), anim_arme, joueur.get("id", "")),
					monstre))
			else:
				combat_doc["log"].append(_avec_etat(_avec_vfx({
					"tour": combat_doc["tour"],
					"acteur": joueur["nom"],
					"kind": "crit" if jet["critique"] else "hit",
					"texte": (
						f"{joueur['nom']} porte un COUP CRITIQUE à {monstre['nom']}{ou} : {dmg} dégâts ! "
						f"(jet {roll} — PV : {monstre['currentPV']}/{monstre['pv_max']})"
						if jet["critique"] else
						f"{joueur['nom']} touche {monstre['nom']}{ou} pour {dmg} dégâts ! "
						f"(PV : {monstre['currentPV']}/{monstre['pv_max']})"
					),
				}, profil.get("mode", "cac"), monstre.get("id", ""), anim_arme, joueur.get("id", "")),
					monstre))
			# Après la mise à jour de `vivant` : le chokepoint refuse une cible morte.
			effet_arme = _appliquer_effet_arme(combat_doc, joueur, monstre, profil)
			result = {"hit": True, "dmg": dmg, "critique": jet["critique"],
					  "cible": monstre["nom"], "cible_pv": monstre["currentPV"]}
			if effet_arme:
				result["effet_arme"] = {"nom": effet_arme.get("nom"),
										"restants": effet_arme.get("restants")}
		else:
			combat_doc["log"].append(_avec_vfx({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "fumble" if jet["fumble"] else "miss",
				"texte": (
					f"{joueur['nom']} rate LAMENTABLEMENT son attaque sur {monstre['nom']} ! "
					f"(jet {roll} / seuil {seuil})"
					if jet["fumble"] else
					f"{joueur['nom']} rate son attaque sur {monstre['nom']} ! (jet {roll} / seuil {seuil})"
				),
			}, "fumble" if jet["fumble"] else "miss", monstre.get("id", ""),
				acteur_id=joueur.get("id", "")))
			result = {"hit": False, "fumble": jet["fumble"], "roll": roll, "seuil": seuil}

		_furtivite_apres_offensive(combat_doc, joueur, monstre, is_ranged)
		joueur["attaques"] += 1
		_refresh_actions(joueur)
		# Après le décompte de l'attaque : un fumble coûte une action de PLUS.
		if jet["fumble"]:
			_appliquer_fumble(combat_doc, joueur)
		_check_victory(combat_doc)

	elif action_type == "passer":
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "sys",
			"texte": f"{joueur['nom']} passe son tour.",
		})
		joueur["actions_restantes"] = 0
		result = {"passed": True}

	elif action_type == "fuir":
		init_max = max(
			(m["initiative"] for m in combat_doc["monstres"] if m["vivant"]),
			default=0,
		)
		seuil = _flee_threshold(joueur["initiative"], init_max)
		flee_roll = random.randint(1, 100)
		if flee_roll <= seuil:
			combat_doc["status"] = "fuite"
			combat_doc["log"].append({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "flee",
				"texte": f"{joueur['nom']} prend la fuite !",
			})
			result = {"fled": True}
		else:
			combat_doc["log"].append({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "flee",
				"texte": f"{joueur['nom']} tente de fuir mais échoue ! (jet {flee_roll}/{seuil})",
			})
			joueur["actions_restantes"] = 0
			result = {"fled": False, "roll": flee_roll, "seuil": seuil}

	elif action_type == "ramasser":
		# Ramasser la carcasse d'un ennemi mort adjacent, coûte 1 action. Interdit si
		# un ennemi VIVANT est au corps à corps (adjacent) → il faut d'abord se dégager.
		if any(m["vivant"] and _cheby(joueur, m) <= 1 for m in combat_doc["monstres"]):
			return {"error": "Un ennemi vous menace au corps à corps."}
		morts_adj = [
			m for m in combat_doc["monstres"]
			if not m["vivant"] and not m.get("loote") and _cheby(joueur, m) <= 1
		]
		if not morts_adj:
			return {"error": "Aucune carcasse à portée."}
		if cible_id:
			monstre = next((m for m in morts_adj if m["id"] == cible_id), None)
			if monstre is None:
				return {"error": "Carcasse invalide."}
		else:
			monstre = morts_adj[0]

		item = _ensure_loot_item(monstre.get("espece_id", ""), monstre.get("nom", ""))
		if item is None:
			return {"error": "Cette créature ne laisse aucun reste."}
		poids = _roll_carcasse_weight(item, monstre.get("niveau", 1))
		if joueur.get("charge", 0) + poids > joueur.get("charge_max", 0):
			return {"error": "Trop lourd : vous ne pouvez pas porter cette carcasse."}

		monstre["loote"] = True
		# Référence {item, poids} : le poids d'instance tiré est conservé dans l'inventaire.
		joueur.setdefault("butin_ramasse", []).append({"item": item["_id"], "poids": poids})
		joueur["charge"] = round(joueur.get("charge", 0) + poids, 2)
		_recompute_player_deplacement(joueur)  # malus de charge éventuel
		joueur["ramasses"] = joueur.get("ramasses", 0) + 1
		_refresh_actions(joueur)
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "sys",
			"texte": f"{joueur['nom']} récupère {item.get('nom', 'une carcasse')}.",
		})
		result = {"looted": True, "item": item.get("nom"), "charge": joueur["charge"]}

	elif action_type == "consommer":
		# Consommer un item du sac (doc résolu injecté par le router, qui l'a déjà retiré
		# de l'inventaire du personnage), coûte 1 action. Part INSTANTANÉE (pv/pm) ET part
		# à DURÉE (buffs/régén/esquive) s'appliquent — une potion d'armure vaut en combat
		# autant que le sort équivalent.
		if not item or not est_consommable(item) or not effet_instantane(item):
			return {"error": "Cet objet ne peut pas être consommé en combat."}
		eff = effets_de(item)
		# Empilé AVANT la part instantanée : un buff de R relève pv_max, dans lequel le
		# soin de la même potion peut alors se loger (miroir d'appliquer_instantane).
		effet_pose = _empiler_effet_combat(joueur, item, eff, combat_doc["tour"])
		avant_pv, avant_pm = joueur["currentPV"], joueur["currentPM"]
		joueur["currentPV"] = min(joueur["pv_max"], avant_pv + eff["pv"])
		joueur["currentPM"] = min(joueur["pm_max"], avant_pm + eff["pm"])
		# L'item quitte le sac → la charge portée baisse (miroir inverse du ramassage).
		joueur["charge"] = round(max(0.0, joueur.get("charge", 0) - float(item.get("poids", 0) or 0)), 2)
		_recompute_player_deplacement(joueur)
		joueur["consommes"] = joueur.get("consommes", 0) + 1
		_refresh_actions(joueur)
		pv_rendu = joueur["currentPV"] - avant_pv
		pm_rendu = joueur["currentPM"] - avant_pm
		gains = " / ".join(s for s in (
			f"+{pv_rendu} PV" if pv_rendu else "",
			f"+{pm_rendu} PM" if pm_rendu else "",
			f"effet {effet_pose['restants']} tour(s)" if effet_pose else "",
		) if s) or "aucun effet"
		combat_doc["log"].append(_avec_etat(_avec_vfx({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "sys",
			"texte": f"{joueur['nom']} consomme {item.get('nom', 'un objet')} ({gains}).",
		}, "consommable", joueur.get("id", ""), item.get("animation")), joueur))
		result = {"consomme": True, "item": item.get("nom"),
				  "pv_rendu": pv_rendu, "pm_rendu": pm_rendu, "charge": joueur["charge"],
				  "effets_actifs": [dict(e) for e in joueur.get("effets_actifs") or []]}

	elif action_type == "editer_barre":
		# Réorganiser sa barre d'action sous le feu coûte 1 action : improviser un plan
		# a un prix. C'est l'ENTRÉE en mode édition qui est facturée, pas chaque case —
		# une fois le temps pris, on réarrange autant qu'on veut.
		#
		# Aucune mutation du personnage ici : le CONTENU des cases vit sur le doc
		# `character:*`/`aventurier:*` et reste écrit par /api/slot_action, qui n'a pas
		# à connaître le combat. Le moteur ne débite que le temps passé.
		joueur["editions"] = joueur.get("editions", 0) + 1
		_refresh_actions(joueur)
		combat_doc["log"].append({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "sys",
			"texte": f"{joueur['nom']} réorganise sa barre d'action.",
		})
		result = {"edition_barre": True}

	elif action_type == "sort":
		# Lancer un sort connu, coûte 1 action + cout_pm PM. Le router injecte
		# `sort = {doc (normalisé), effets (fusionnés avec les bonus des composants
		# engagés), composants_engages, poids_consommes}` — les composants consommés
		# ont déjà été retirés du sac du personnage en mémoire. S'appliquent la part
		# INSTANTANÉE (degats/pv/pm, ou furtivité = état posé instantanément) ET la part
		# à DURÉE (buffs/régén/esquive), empilée sur les effets vivants du snapshot.
		if not sort or not sort.get("doc"):
			return {"error": "Sort invalide."}
		sdoc = sort["doc"]
		effets = sort.get("effets") or {}
		cout_pm = max(0, int(sdoc.get("cout_pm", 0) or 0))
		if not (effets.get("degats") or effets.get("pv") or effets.get("pm")
				or int(effets.get("furtivite", 0) or 0) > 0 or part_durative(effets)):
			return {"error": "Ce sort n'a aucun effet utilisable en combat."}
		if joueur["currentPM"] < cout_pm:
			return {"error": "PM insuffisants."}

		jet = None   # renseigné seulement par la branche offensive (jet de toucher)
		if sdoc.get("cible") == "allie":
			# Sort d'entraide : compagnon OU monture, désigné par son id de snapshot.
			# Aucun jet, aucun compteur d'attaque — seulement l'action et les PM.
			allie = _get_joueur(combat_doc, cible_id) if cible_id else None
			res_allie = _lancer_sur_allie(combat_doc, joueur, allie, sdoc, effets,
										  sdoc.get("portee", 1), grid)
			if "error" in res_allie:
				return res_allie   # PM NON débités : le sort n'est jamais parti
			joueur["currentPM"] -= cout_pm
			result = {"sort": sdoc.get("nom"), **res_allie}
		elif sdoc.get("cible") == "ennemi":
			# Dégâts OU part à durée : un sort offensif peut n'être qu'un debuff
			# (« −10 Ag pendant 2 tours »), il lui suffit d'avoir quelque chose à faire.
			if not effets.get("degats") and not part_durative(effets):
				return {"error": "Ce sort n'a aucun effet sur une cible."}
			monstre = _get_monstre(combat_doc, cible_id) if cible_id else None
			if not monstre or not monstre["vivant"]:
				return {"error": "Cible invalide."}
			sort_portee = max(1, int(sdoc.get("portee", 1) or 1))
			# Règles à distance identiques au jet/tir : un sort de portée > 1 est
			# interdit si engagé au corps à corps et exige une ligne de vue ; un sort
			# de contact (portée 1) reste lançable en mêlée.
			if sort_portee > 1:
				if any(m["vivant"] and _cheby(joueur, m) <= 1 for m in combat_doc["monstres"]):
					return {"error": "Un ennemi vous menace au corps à corps : impossible d'incanter."}
				if not _line_of_sight(grid["cells"], joueur["pos"]["x"], joueur["pos"]["y"],
									   monstre["pos"]["x"], monstre["pos"]["y"]):
					return {"error": "Ligne de vue obstruée."}
			if _cheby(joueur, monstre) > sort_portee:
				return {"error": "Cible hors de portée."}

			# Le sort part : PM débités AVANT le jet (raté = PM quand même dépensés).
			joueur["currentPM"] -= cout_pm
			# Jet porté par la DONNÉE, exactement comme pour les compétences :
			# `magique` (défaut des sorts) se résout sous toucher_magique contre la
			# pm_def ; un sort de CONTACT marqué `cc`/`cd` (« au toucher ») exige
			# d'abord de poser la main — jet martial contre la défense physique.
			mode_jet = sdoc.get("jet") or "magique"
			if mode_jet == "magique":
				seuil = _magic_hit_threshold(joueur.get("toucher_magique", 0),
											 monstre.get("pm_def", 0))
			else:
				skill = joueur["cd"] if mode_jet == "cd" else joueur["cc"]
				seuil = _hit_threshold(skill, _defense_physique(monstre))
			jet = _resoudre_jet(joueur, monstre, seuil)
			roll = jet["roll"]
			if jet["touche"]:
				# `mode_jet` porte tout : la magie ignore les PA (la pm_def a déjà joué
				# dans le seuil), un sort à jet MARTIAL les subit — sinon `jet: "cc"`
				# serait un pur gain, contourner la pm_def sans rien payer en retour.
				ou = ""
				if effets.get("degats"):
					zone = tirer_localisation()
					ou = f" {ZONE_LIBELLE[zone]}" if zone in ZONE_LIBELLE else ""
					dmg = calculer_degats(joueur, monstre, effets["degats"],
										  jet["mult_degats"], mode_jet, zone=zone)
				else:
					dmg = 0
				monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
				anim_sort = sdoc.get("animation")
				if dmg and monstre["currentPV"] <= 0:
					monstre["vivant"] = False
					combat_doc["log"].append(_avec_etat(_avec_vfx({
						"tour": combat_doc["tour"],
						"acteur": joueur["nom"],
						"kind": "kill",
						"texte": (
							f"{joueur['nom']} lance {sdoc.get('nom', 'un sort')} d'une puissance CRITIQUE "
							f"et pulvérise {monstre['nom']} !"
							if jet["critique"] else
							f"{joueur['nom']} lance {sdoc.get('nom', 'un sort')} et élimine {monstre['nom']} !"
						),
					}, "sort", monstre.get("id", ""), anim_sort, joueur.get("id", "")), joueur, monstre))
				elif dmg:
					combat_doc["log"].append(_avec_etat(_avec_vfx({
						"tour": combat_doc["tour"],
						"acteur": joueur["nom"],
						"kind": "crit" if jet["critique"] else "hit",
						"texte": (
							f"{joueur['nom']} lance {sdoc.get('nom', 'un sort')} d'une puissance CRITIQUE : "
							f"{monstre['nom']} encaisse{ou} {dmg} dégâts ! "
							f"(jet {roll} — PV : {monstre['currentPV']}/{monstre['pv_max']})"
							if jet["critique"] else
							f"{joueur['nom']} lance {sdoc.get('nom', 'un sort')} : {monstre['nom']} "
							f"encaisse{ou} {dmg} dégâts ! (PV : {monstre['currentPV']}/{monstre['pv_max']})"
						),
					}, "sort", monstre.get("id", ""), anim_sort, joueur.get("id", "")), joueur, monstre))
				else:
					# Sort de pur debuff : il touche sans blesser. La ligne posée juste
					# après par _appliquer_effet_sur_cible dit ce que la cible encaisse.
					combat_doc["log"].append(_avec_etat(_avec_vfx({
						"tour": combat_doc["tour"],
						"acteur": joueur["nom"],
						"kind": "hit",
						"texte": f"{joueur['nom']} lance {sdoc.get('nom', 'un sort')} "
								 f"sur {monstre['nom']} : le sort prend.",
					}, "sort", monstre.get("id", ""), anim_sort, joueur.get("id", "")), joueur))
				# Part à DURÉE sur la CIBLE : posée seulement si le sort a TOUCHÉ, et jamais
				# sur une cible que le même coup vient d'abattre.
				effet_cible = _appliquer_effet_sur_cible(
					combat_doc, monstre, sdoc, effets, combat_doc["tour"])
				result = {"sort": sdoc.get("nom"), "hit": True, "dmg": dmg,
						  "critique": jet["critique"],
						  "cible": monstre["nom"], "cible_pv": monstre["currentPV"],
						  "effet_cible": dict(effet_cible) if effet_cible else None}
			else:
				# Le lanceur en état : les PM sont débités AVANT le jet (raté = dépensés),
				# la ligne qui annonce l'échec est donc celle qui doit les faire baisser.
				combat_doc["log"].append(_avec_etat(_avec_vfx({
					"tour": combat_doc["tour"],
					"acteur": joueur["nom"],
					"kind": "fumble" if jet["fumble"] else "miss",
					"texte": (
						f"{joueur['nom']} bafouille son incantation : {sdoc.get('nom', 'le sort')} "
						f"lui explose au visage ! (jet {roll} / seuil {seuil})"
						if jet["fumble"] else
						f"{joueur['nom']} lance {sdoc.get('nom', 'un sort')} sur {monstre['nom']}"
						f" mais le sort se dissipe ! (jet {roll} / seuil {seuil})"
					),
				}, "fumble" if jet["fumble"] else "miss", monstre.get("id", ""),
					acteur_id=joueur.get("id", "")), joueur))
				result = {"sort": sdoc.get("nom"), "hit": False, "fumble": jet["fumble"],
						  "roll": roll, "seuil": seuil}

			# Incanter au contact révèle le lanceur (touché ou raté) ; à distance, seule la
			# cible tente de le repérer — foudroyée sur place, elle n'en a même pas le temps.
			_furtivite_apres_offensive(combat_doc, joueur, monstre, sort_portee > 1)
		else:
			# Sort sur soi : toujours lançable ; débit PM puis part instantanée clampée.
			joueur["currentPM"] -= cout_pm
			avant_pv, avant_pm = joueur["currentPV"], joueur["currentPM"]
			joueur["currentPV"] = min(joueur["pv_max"], avant_pv + int(effets.get("pv", 0) or 0))
			joueur["currentPM"] = min(joueur["pm_max"], avant_pm + int(effets.get("pm", 0) or 0))
			pv_rendu = joueur["currentPV"] - avant_pv
			pm_rendu = joueur["currentPM"] - avant_pm
			# Part à DURÉE : empilée sur les effets vivants du snapshot (buffs de caract,
			# régén, esquive), qui recalcule aussitôt les dérivées du lanceur.
			effet_pose = _empiler_effet_combat(joueur, sdoc, effets, combat_doc["tour"])
			gains = " / ".join(s for s in (
				f"+{pv_rendu} PV" if pv_rendu else "",
				f"+{pm_rendu} PM" if pm_rendu else "",
				f"effet {effet_pose['restants']} tour(s)" if effet_pose else "",
			) if s) or "aucun effet"
			combat_doc["log"].append(_avec_etat({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "sys",
				"texte": f"{joueur['nom']} lance {sdoc.get('nom', 'un sort')} ({gains}).",
			}, joueur))
			# Sort de dissimulation (effets.furtivite > 0) : pose l'état furtif et
			# remet la détection de tous les monstres à zéro.
			if int(effets.get("furtivite", 0) or 0) > 0:
				_activer_furtivite(combat_doc, joueur, int(effets["furtivite"]))
			result = {"sort": sdoc.get("nom"), "pv_rendu": pv_rendu, "pm_rendu": pm_rendu,
					  "furtif": bool(joueur.get("furtif")),
					  "effets_actifs": [dict(e) for e in joueur.get("effets_actifs") or []]}

		# Les composants consommés quittent le sac → la charge portée baisse.
		poids_consommes = float(sort.get("poids_consommes", 0) or 0)
		if poids_consommes:
			joueur["charge"] = round(max(0.0, joueur.get("charge", 0) - poids_consommes), 2)
			_recompute_player_deplacement(joueur)
			result["charge"] = joueur["charge"]
		result["currentPM"] = joueur["currentPM"]
		joueur["sorts"] = joueur.get("sorts", 0) + 1
		_refresh_actions(joueur)
		# Après le décompte du sort : une incantation ratée sur un échec critique coûte
		# une action de PLUS (les PM, eux, sont déjà partis avant le jet).
		if jet and jet["fumble"]:
			_appliquer_fumble(combat_doc, joueur)
		_check_victory(combat_doc)

	elif action_type == "competence":
		# Utiliser une compétence ACTIVE connue, coûte 1 action + cout_pm PM (souvent 0 :
		# une compétence martiale ne consomme pas de magie). Le router injecte la compétence
		# normalisée. Comme pour les sorts et les consommables, part INSTANTANÉE
		# (degats/pv/pm) ET part à DURÉE s'appliquent. Les compétences PASSIVES n'arrivent
		# jamais ici — leur bonus est déjà intégré au snapshot (competences_bonus →
		# caracts_avec_buffs, replié dans `caracts_base`).
		if not competence:
			return {"error": "Compétence invalide."}
		effets = competence.get("effets") or {}
		cout_pm = max(0, int(competence.get("cout_pm", 0) or 0))
		if not (effets.get("degats") or effets.get("pv") or effets.get("pm")
				or int(effets.get("furtivite", 0) or 0) > 0 or part_durative(effets)):
			return {"error": "Cette compétence n'a aucun effet utilisable en combat."}
		if joueur["currentPM"] < cout_pm:
			return {"error": "PM insuffisants."}

		nom = competence.get("nom", "une compétence")
		resultat_jet = None   # renseigné seulement par la branche offensive (jet de toucher)
		if competence.get("cible") == "allie":
			# Miroir exact de la branche alliée du sort (même chokepoint).
			allie = _get_joueur(combat_doc, cible_id) if cible_id else None
			res_allie = _lancer_sur_allie(combat_doc, joueur, allie, competence, effets,
										  competence.get("portee", 1), grid)
			if "error" in res_allie:
				return res_allie
			joueur["currentPM"] -= cout_pm
			result = {"competence": nom, **res_allie}
		elif competence.get("cible") == "ennemi":
			# Dégâts OU part à durée : une compétence offensive peut n'être qu'un debuff
			# (cri de guerre qui affaiblit, entrave qui ralentit…).
			if not effets.get("degats") and not part_durative(effets):
				return {"error": "Cette compétence n'a aucun effet sur une cible."}
			monstre = _get_monstre(combat_doc, cible_id) if cible_id else None
			if not monstre or not monstre["vivant"]:
				return {"error": "Cible invalide."}
			comp_portee = max(1, int(competence.get("portee", 1) or 1))
			# Portée > 1 = règles à distance (jet/tir/sort) : interdit si engagé au corps à
			# corps, et exige une ligne de vue.
			if comp_portee > 1:
				if any(m["vivant"] and _cheby(joueur, m) <= 1 for m in combat_doc["monstres"]):
					return {"error": "Un ennemi vous menace au corps à corps : impossible."}
				if not _line_of_sight(grid["cells"], joueur["pos"]["x"], joueur["pos"]["y"],
									   monstre["pos"]["x"], monstre["pos"]["y"]):
					return {"error": "Ligne de vue obstruée."}
			if _cheby(joueur, monstre) > comp_portee:
				return {"error": "Cible hors de portée."}

			# La compétence part : PM débités AVANT le jet (raté = PM quand même dépensés).
			joueur["currentPM"] -= cout_pm
			# Le jet est porté par la DONNÉE : une frappe martiale se résout sous cc/cd contre
			# l'Ag de la cible (PA soustraits comme une attaque d'arme) ; une compétence
			# magique se résout sous toucher_magique contre la pm_def (sans soustraction de PA,
			# l'armure physique n'arrête pas la magie).
			# Le jet est aussi ce qui décide si les dégâts d'ARME s'ajoutent (cf.
			# _degats_competence) : une frappe `cc` est portée avec l'arme en main.
			jet = competence.get("jet", "cc")
			if jet == "magique":
				seuil = _magic_hit_threshold(joueur.get("toucher_magique", 0), monstre.get("pm_def", 0))
			else:
				skill = joueur["cd"] if jet == "cd" else joueur["cc"]
				seuil = _hit_threshold(skill, _defense_physique(monstre))
			resultat_jet = _resoudre_jet(joueur, monstre, seuil)
			roll = resultat_jet["roll"]
			if resultat_jet["touche"]:
				ou = ""
				if effets.get("degats"):
					# Notation = dés de la compétence, PLUS les dégâts d'arme si c'est une
					# frappe de contact. Le reste (critique avant les PA, magie sans PA)
					# est la formule commune.
					notation = _degats_competence(joueur, competence, effets)
					zone = tirer_localisation()
					ou = f" {ZONE_LIBELLE[zone]}" if zone in ZONE_LIBELLE else ""
					dmg = calculer_degats(joueur, monstre, notation,
										  resultat_jet["mult_degats"], jet, zone=zone)
				else:
					dmg = 0   # compétence de pur debuff : elle touche sans blesser
				monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
				anim_comp = competence.get("animation")
				if dmg and monstre["currentPV"] <= 0:
					monstre["vivant"] = False
					combat_doc["log"].append(_avec_etat(_avec_vfx({
						"tour": combat_doc["tour"],
						"acteur": joueur["nom"],
						"kind": "kill",
						"texte": (
							f"{joueur['nom']} utilise {nom} — coup CRITIQUE — et élimine {monstre['nom']} !"
							if resultat_jet["critique"] else
							f"{joueur['nom']} utilise {nom} et élimine {monstre['nom']} !"
						),
					}, "competence", monstre.get("id", ""), anim_comp, joueur.get("id", "")),
						joueur, monstre))
				elif dmg:
					combat_doc["log"].append(_avec_etat(_avec_vfx({
						"tour": combat_doc["tour"],
						"acteur": joueur["nom"],
						"kind": "crit" if resultat_jet["critique"] else "hit",
						"texte": (
							f"{joueur['nom']} utilise {nom} — coup CRITIQUE : {monstre['nom']} encaisse{ou} "
							f"{dmg} dégâts ! (jet {roll} — PV : {monstre['currentPV']}/{monstre['pv_max']})"
							if resultat_jet["critique"] else
							f"{joueur['nom']} utilise {nom} : {monstre['nom']} encaisse{ou} {dmg} dégâts ! "
							f"(PV : {monstre['currentPV']}/{monstre['pv_max']})"
						),
					}, "competence", monstre.get("id", ""), anim_comp, joueur.get("id", "")),
						joueur, monstre))
				else:
					# Compétence de pur debuff : elle touche sans blesser. La ligne posée
					# juste après par _appliquer_effet_sur_cible dit ce que la cible encaisse.
					combat_doc["log"].append(_avec_etat(_avec_vfx({
						"tour": combat_doc["tour"],
						"acteur": joueur["nom"],
						"kind": "hit",
						"texte": f"{joueur['nom']} utilise {nom} sur {monstre['nom']} : la prise porte.",
					}, "competence", monstre.get("id", ""), anim_comp, joueur.get("id", "")), joueur))
				# Part à DURÉE sur la CIBLE : posée seulement si la compétence a TOUCHÉ, et
				# jamais sur une cible que le même coup vient d'abattre.
				effet_cible = _appliquer_effet_sur_cible(
					combat_doc, monstre, competence, effets, combat_doc["tour"])
				result = {"competence": nom, "hit": True, "dmg": dmg,
						  "critique": resultat_jet["critique"],
						  "cible": monstre["nom"], "cible_pv": monstre["currentPV"],
						  "effet_cible": dict(effet_cible) if effet_cible else None}
			else:
				combat_doc["log"].append(_avec_etat(_avec_vfx({
					"tour": combat_doc["tour"],
					"acteur": joueur["nom"],
					"kind": "fumble" if resultat_jet["fumble"] else "miss",
					"texte": (
						f"{joueur['nom']} rate complètement {nom} sur {monstre['nom']} "
						f"et se découvre ! (jet {roll} / seuil {seuil})"
						if resultat_jet["fumble"] else
						f"{joueur['nom']} utilise {nom} sur {monstre['nom']}"
						f" mais manque son coup ! (jet {roll} / seuil {seuil})"
					),
				}, "fumble" if resultat_jet["fumble"] else "miss", monstre.get("id", ""),
					acteur_id=joueur.get("id", "")), joueur))
				result = {"competence": nom, "hit": False, "fumble": resultat_jet["fumble"],
						  "roll": roll, "seuil": seuil}

			# Frapper au contact révèle le joueur (touché ou raté) ; à distance, seule la
			# cible tente de le repérer — et une cible abattue ne repère plus rien.
			_furtivite_apres_offensive(combat_doc, joueur, monstre, comp_portee > 1)
		else:
			# Compétence sur soi : toujours utilisable ; débit PM puis part instantanée clampée.
			joueur["currentPM"] -= cout_pm
			avant_pv, avant_pm = joueur["currentPV"], joueur["currentPM"]
			joueur["currentPV"] = min(joueur["pv_max"], avant_pv + int(effets.get("pv", 0) or 0))
			joueur["currentPM"] = min(joueur["pm_max"], avant_pm + int(effets.get("pm", 0) or 0))
			pv_rendu = joueur["currentPV"] - avant_pv
			pm_rendu = joueur["currentPM"] - avant_pm
			# Part à DURÉE : même traitement que pour un sort (cf. branche "sort").
			effet_pose = _empiler_effet_combat(joueur, competence, effets, combat_doc["tour"])
			gains = " / ".join(s for s in (
				f"+{pv_rendu} PV" if pv_rendu else "",
				f"+{pm_rendu} PM" if pm_rendu else "",
				f"effet {effet_pose['restants']} tour(s)" if effet_pose else "",
			) if s) or "aucun effet"
			combat_doc["log"].append(_avec_etat({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "sys",
				"texte": f"{joueur['nom']} utilise {nom} ({gains}).",
			}, joueur))
			# Compétence de dissimulation (ex. Furtivité de l'assassin) : pose l'état
			# furtif et remet la détection de tous les monstres à zéro.
			if int(effets.get("furtivite", 0) or 0) > 0:
				_activer_furtivite(combat_doc, joueur, int(effets["furtivite"]))
			result = {"competence": nom, "pv_rendu": pv_rendu, "pm_rendu": pm_rendu,
					  "furtif": bool(joueur.get("furtif")),
					  "effets_actifs": [dict(e) for e in joueur.get("effets_actifs") or []]}

		result["currentPM"] = joueur["currentPM"]
		joueur["competences"] = joueur.get("competences", 0) + 1
		_refresh_actions(joueur)
		# Après le décompte de la compétence : un échec critique coûte une action de PLUS.
		if resultat_jet and resultat_jet["fumble"]:
			_appliquer_fumble(combat_doc, joueur)
		_check_victory(combat_doc)

	else:
		return {"error": f"Action inconnue : {action_type}"}

	if combat_doc["status"] == "active" and joueur["actions_restantes"] <= 0:
		_advance_and_resolve(combat_doc, grid)

	return result


# ── Butin (loot) ──────────────────────────────────────────────────────────────
# Loot 1-pour-1 avec le bestiaire : un monstre tué laisse une « carcasse » dont
# l'_id suit la règle item:<sub_id>, où sub_id = la partie de l'espece_id après
# "espece:". Les 133 carcasses sont pré-générées (item.json importé) ; on en crée
# une à la volée pour toute espèce ajoutée ensuite au bestiaire sans item associé.
# Ces carcasses sont des composants destinés à être transformés par les PNJ
# (boucher, alchimiste, magicien, forgeron…).

def _loot_item_id(espece_id: str) -> str | None:
	"""item:<sub_id> à partir d'un espece_id ('espece:<sub_id>'), ou None si malformé."""
	if not espece_id or not espece_id.startswith("espece:"):
		return None
	return "item:" + espece_id[len("espece:"):]


def _build_loot_item(item_id: str, espece_id: str, nom_fallback: str) -> dict:
	"""Doc item « Restes de … » créé à la volée pour une espèce sans carcasse pré-générée.

	Lit le doc espèce (si présent) pour le nom et un poids dérivé de la Force moyenne
	(échelle ×10 : F_moy/5, ×0.5 si petite_taille, ×2 si géant, borné 0.5–25 kg).
	"""
	espece = get_doc(espece_id) or {}
	nom = espece.get("nom") or nom_fallback or item_id[len("item:"):]
	base_f = espece.get("base_attributes", {}).get("F", {})
	f_avg = (base_f.get("min", 10) + base_f.get("max", 10)) / 2
	poids = f_avg / 5
	tags = set(espece.get("tags", []))
	if "petite_taille" in tags:
		poids *= 0.5
	if "geant" in tags:
		poids *= 2
	poids = round(max(0.5, min(25.0, poids)), 1)
	return {
		"_id": item_id,
		"type": "item",
		"nom": f"Restes de {nom}",
		"icon": "🦴",
		"rarete": "commun",
		"categorie": "composant",
		"slots": [],
		"poids": poids,
		"description": f"Dépouille de {nom} récupérée à l'issue du combat.",
		"source_espece": espece_id,
		"loot_defaut": True,
	}


def _ensure_loot_item(espece_id: str, nom_fallback: str = "") -> dict | None:
	"""Retourne le doc item carcasse d'une espèce, en le créant en base si absent.

	None si l'espece_id est malformé ou si la création échoue. Partagé par le
	ramassage en combat et par la construction du butin disponible à la victoire.
	"""
	item_id = _loot_item_id(espece_id)
	if not item_id:
		return None
	item = get_doc(item_id)
	if item is not None:
		return item
	item = _build_loot_item(item_id, espece_id, nom_fallback)
	if save_doc(item) is None:
		return None
	return item


def _roll_carcasse_weight(item: dict, niveau: int) -> float:
	"""Poids tiré pour une instance de carcasse.

	Si l'item a un poids fixe → ce poids. S'il a un poids [min, max] → on tire min OU
	max via random.choices, pondéré par le niveau du profil de l'ennemi :
	weights = [max(1, 7-niveau), max(1, 1+niveau)] → bas niveau ⇒ plutôt le min (léger),
	haut niveau ⇒ plutôt le max (lourd).
	"""
	pmin, pmax = poids_bounds(item)
	if pmin == pmax:
		return pmin
	w_min = max(1, 7 - niveau)
	w_max = max(1, 1 + niveau)
	return random.choices([pmin, pmax], weights=[w_min, w_max])[0]


def _carcasse_payload(monstre: dict) -> dict | None:
	"""Descripteur {monstre_id, item_id, nom, poids} de la carcasse d'un monstre, le
	poids étant tiré selon le niveau du profil (cf. _roll_carcasse_weight).

	None si la créature ne laisse pas de reste (espece_id malformé) ou si la
	création de l'item échoue.
	"""
	item = _ensure_loot_item(monstre.get("espece_id", ""), monstre.get("nom", ""))
	if item is None:
		return None
	return {
		"monstre_id": monstre["id"],
		"item_id": item["_id"],
		"nom": item.get("nom", item["_id"]),
		"poids": _roll_carcasse_weight(item, monstre.get("niveau", 1)),
	}


def _finalize_membre(combat_doc: dict, joueur: dict, doc: dict, status: str) -> bool:
	"""Applique l'issue du combat au doc d'UN membre du groupe (principal ou compagnon,
	les docs `aventurier:*` étant des miroirs du character) : PV (KO → relevé à 1),
	PM, XP pleine (v1) et butin ramassé par CE membre → SON sac. Garde d'idempotence
	PAR DOC (`combats_recompenses`, même document que l'XP). Sauvegarde ; True si la
	récompense vient d'être appliquée."""
	combat_id = combat_doc.get("_id")
	rewarded = doc.get("combats_recompenses", [])
	if combat_id in rewarded:
		return False

	if status == "victoire":
		# Un membre KO à la victoire est relevé à 1 PV (jamais de mort définitive).
		doc["currentPV"] = max(1, joueur.get("currentPV", 0))
		# XP + montée de niveau : règle partagée avec la découverte de lieux. XP
		# pleine pour chaque membre (v1, pas de partage).
		grant_xp(doc, combat_doc.get("xp_gagnee", 0))
	elif status == "defaite":
		doc["currentPV"] = 1
	elif status == "fuite":
		doc["currentPV"] = max(1, joueur.get("currentPV", 0))
	# PM réappliqués pour TOUTES les issues (le PM n'est pas la ressource de KO ; une
	# potion de PM bue en combat doit persister).
	doc["currentPM"] = max(0, joueur.get("currentPM", doc.get("currentPM", 0)))

	# Effets à durée encore vivants : reversés sur le personnage, où le tick d'exploration
	# (_apply_world_turn_regen) les reprend. Un buff est un buff — qu'il ait été lancé
	# avant le combat ou pendant, il ne meurt pas avec lui. `pose_tour` n'a de sens qu'en
	# combat et ne suit pas.
	restants = [
		{k: v for k, v in eff.items() if k != "pose_tour"}
		for eff in joueur.get("effets_actifs") or []
		if _eff_int(eff.get("restants")) > 0
	]
	# Écrasement (pas d'extend) : ces entrées SONT celles du personnage, copiées à l'entrée
	# en combat puis décrémentées — les rajouter les dupliquerait.
	if restants or joueur.get("effets_actifs") is not None:
		doc["effets_actifs"] = restants

	# Butin ramassé en plein combat (action « ramasser ») : conservé quelle que soit
	# l'issue, dans le sac du membre qui l'a saisi. Ajouté dans le MÊME doc que l'XP
	# → couvert par l'idempotence atomique (pas de double).
	ramasse = [i for i in joueur.get("butin_ramasse", []) if i]
	if ramasse:
		inventaire = doc.get("inventaire", [])
		inventaire.extend(ramasse)
		doc["inventaire"] = inventaire

	# Idempotence atomique : le combat est enregistré dans le doc du membre,
	# sauvegardé avec l'XP. Borné pour éviter une croissance illimitée.
	rewarded.append(combat_id)
	doc["combats_recompenses"] = rewarded[-MEMOIRE_COMBATS_MAX:]
	return save_doc(doc) is not None


def _finalize_monture(combat_doc: dict, snap: dict, doc: dict, status: str,
					  character: dict) -> bool:
	"""Applique l'issue du combat au doc d'UNE monture. Elle ne gagne pas d'XP (elle porte,
	elle ne se bat pas) et n'a pas d'affinité — seuls ses PV comptent, et sa survie.

	Tombée à 0 PV, elle est PERDUE (world-var MONTURE_MORT_DEFINITIVE) : elle quitte le
	troupeau et sa cargaison rejoint le butin disponible, pour que le joueur puisse la
	récupérer dans l'overlay de fin plutôt que de la voir disparaître avec la bête.
	⚠️ Cela suppose une victoire — `butin_disponible` n'est proposé que dans ce cas ; une
	défaite emporte donc la cargaison, ce qui est le prix assumé du risque.

	Même garde d'idempotence PAR DOC que `_finalize_membre` : une re-finalisation ne peut
	ni ressusciter la bête ni dupliquer sa cargaison."""
	combat_id = combat_doc.get("_id")
	rewarded = doc.get("combats_recompenses", [])
	if combat_id in rewarded:
		return False

	if snap.get("morte") and character_stats.MONTURE_MORT_DEFINITIVE:
		cargaison = montures_util.tuer(character, doc)
		dispo = combat_doc.setdefault("butin_disponible", [])
		for n, ref in enumerate(cargaison):
			item = get_doc(item_ref_id(ref))
			if not item:
				continue
			dispo.append({
				# Id synthétique : /collect indexe le butin par `monstre_id` sans exiger
				# qu'un monstre porte ce nom (la boucle de marquage ne trouvera rien, ce
				# qui est sans effet).
				"monstre_id": f"cargo_{snap['id']}_{n}",
				"item_id": item["_id"],
				"nom": item.get("nom", item["_id"]),
				"poids": item_ref_weight(ref),
			})
	else:
		# Survivante (ou mort désactivée) : relevée comme un membre du groupe.
		doc["currentPV"] = max(1, snap.get("currentPV", 0))
		doc["currentPM"] = max(0, snap.get("currentPM", doc.get("currentPM", 0)))
		# Effets à durée encore vivants (un buff lancé sur la bête par un allié) :
		# reversés comme pour un membre du groupe. Un doc `monture:*` étant un miroir
		# du character, le tick d'exploration les reprend sans code supplémentaire.
		restants = [
			{k: v for k, v in eff.items() if k != "pose_tour"}
			for eff in snap.get("effets_actifs") or []
			if _eff_int(eff.get("restants")) > 0
		]
		if restants or snap.get("effets_actifs") is not None:
			doc["effets_actifs"] = restants

	rewarded.append(combat_id)
	doc["combats_recompenses"] = rewarded[-MEMOIRE_COMBATS_MAX:]
	return save_doc(doc) is not None


def _finalize_protege(combat_doc: dict, snap: dict, doc: dict, status: str,
					  character: dict) -> bool:
	"""Applique l'issue du combat au doc d'UNE personne escortée. Passe DÉDIÉE, hors de la
	boucle des compagnons — sinon elle toucherait de l'XP, une affinité, et serait relevée à
	1 PV alors que tout l'enjeu de la quête est qu'elle puisse mourir.

	Tombée à 0 PV, elle MEURT (world-var ESCORTE_MORT_DEFINITIVE) : elle quitte le groupe et
	l'escorte est archivée EN ÉCHEC, avec la sanction de réputation chez le donneur ET toute
	sa maison (`escorte.echouer` → `quetes.sanctionner_renoncement`). Rien ne tombe au sol :
	son sac part avec elle — ce ne serait pas un butin, ce serait un dépouillement.

	⚠️ Le personnage est muté ICI mais sauvé par `_finalize_membre` juste après (même save
	que l'XP), exactement comme `_finalize_monture` — c'est ce qui rend l'archivage de la
	quête atomique avec le reste de la finalisation.

	Même garde d'idempotence PAR DOC que `_finalize_membre` : une re-finalisation ne peut ni
	ressusciter la personne ni sanctionner deux fois."""
	combat_id = combat_doc.get("_id")
	rewarded = doc.get("combats_recompenses", [])
	if combat_id in rewarded:
		return False

	if snap.get("morte") and character_stats.ESCORTE_MORT_DEFINITIVE:
		escorte_util.tuer(character, doc)
		q = next(
			(x for x in escorte_util.escortes_actives(character)
			 if (x.get("id") or x.get("_id")) == doc.get("quete")),
			None,
		)
		if q is not None:
			escorte_util.echouer(character, q, get_doc, save_doc, find_docs)
	else:
		# Survivante (ou mort désactivée) : relevée comme un membre du groupe.
		doc["currentPV"] = max(1, snap.get("currentPV", 0))
		doc["currentPM"] = max(0, snap.get("currentPM", doc.get("currentPM", 0)))
		# Effets à durée encore vivants (un soin lancé sur elle par un allié) : reversés,
		# comme pour un membre du groupe — son doc est un miroir du character.
		restants = [
			{k: v for k, v in eff.items() if k != "pose_tour"}
			for eff in snap.get("effets_actifs") or []
			if _eff_int(eff.get("restants")) > 0
		]
		if restants or snap.get("effets_actifs") is not None:
			doc["effets_actifs"] = restants

	rewarded.append(combat_id)
	doc["combats_recompenses"] = rewarded[-MEMOIRE_COMBATS_MAX:]
	return save_doc(doc) is not None


def finalize_combat(combat_doc: dict) -> bool:
	"""Applique l'issue du combat (XP/PV/butin) à TOUS les membres du groupe en base —
	compagnons (docs `aventurier:*`) d'abord, personnage principal en dernier.

	Idempotent ET atomique PAR DOC : l'id du combat est enregistré dans le
	`combats_recompenses` de chaque membre, c.-à-d. DANS LE MÊME document que son XP.
	La récompense ne peut donc être appliquée qu'une seule fois par membre, même si
	une sauvegarde échoue par ailleurs, et reste rattrapable (par /play) si
	`combat_action` n'a pas pu la finaliser.

	Sur le principal SEUL : progression des quêtes de chasse, focalisation, et deltas
	d'affinité envers les compagnons (+VICTOIRE / +KO, dans le même save que l'XP).

	Retourne True si la récompense du PRINCIPAL vient d'être appliquée et sauvegardée.
	"""
	status = combat_doc.get("status")
	if status not in ("victoire", "defaite", "fuite"):
		return False  # combat encore actif → rien à appliquer

	principal_id = combat_doc["character_id"]
	character = get_doc(principal_id)
	if not character:
		return False

	# Compagnons d'abord (best-effort chacun), principal en dernier : si le save du
	# principal échoue, /play re-finalisera — les compagnons déjà servis sont protégés
	# par leur propre garde d'idempotence.
	compagnons_traites = []
	montures_traitees = []
	proteges_traites = []
	joueur_principal = None
	for j in combat_doc["joueurs"]:
		cid = j.get("character_id")
		if cid == principal_id:
			joueur_principal = j
			continue
		doc = get_doc(cid) if cid else None
		if not doc:
			continue
		# ⚠️ Une monture n'est PAS un compagnon : elle ne gagne pas d'XP, n'a pas
		# d'affinité, et à 0 PV elle meurt au lieu d'être relevée. `_finalize_membre` lui
		# appliquerait les trois — elle a sa propre passe, plus bas.
		if j.get("est_monture"):
			montures_traitees.append((j, doc))
			continue
		# ⚠️ Ni une personne ESCORTÉE : elle ne gagne pas d'XP, n'a pas d'affinité, et à 0 PV
		# elle meurt (et fait échouer sa quête) au lieu d'être relevée. Passe dédiée, plus bas.
		if j.get("est_protege"):
			proteges_traites.append((j, doc))
			continue
		_finalize_membre(combat_doc, j, doc, status)
		compagnons_traites.append((j, doc))
	if joueur_principal is None:
		joueur_principal = combat_doc["joueurs"][0]

	combat_id = combat_doc.get("_id")
	if combat_id in character.get("combats_recompenses", []):
		combat_doc["recompense_appliquee"] = True  # déjà appliqué au principal
		return False

	# Carcasses laissées au sol (monstres tués non ramassés) : proposées dans l'overlay
	# de fin UNIQUEMENT en cas de victoire. Le joueur choisit lesquelles emporter via
	# POST /api/combat/{id}/collect (borné par charge_max) — pas d'ajout automatique.
	if status == "victoire":
		dispo = []
		for m in combat_doc["monstres"]:
			if m.get("loote"):
				continue  # déjà ramassée pendant le combat
			payload = _carcasse_payload(m)
			if payload:
				dispo.append(payload)
		combat_doc["butin_disponible"] = dispo

	# Montures — APRÈS l'affectation de `butin_disponible` ci-dessus, qui l'écraserait :
	# la cargaison d'une bête tombée s'y ajoute (mute `character["montures"]`, sauvé avec
	# le principal juste en dessous).
	for j, doc in montures_traitees:
		_finalize_monture(combat_doc, j, doc, status, character)

	# Personnes escortées — même place, même motif que les montures : le personnage est muté
	# ici (retrait du groupe, archivage de la quête en échec) et sauvé par `_finalize_membre`
	# juste en dessous, dans le même save que l'XP.
	for j, doc in proteges_traites:
		_finalize_protege(combat_doc, j, doc, status, character)

	# Progression des quêtes de chasse : compte les monstres tués (toute issue), sous le
	# même garde exactly-once que l'XP → pas de double comptage si /play re-finalise.
	maj_progress_kills(character, combat_doc.get("monstres", []))
	# Quêtes de « chasse » (élite marquée) : complétées si le monstre porteur du quete_chasse
	# est tombé. Même fenêtre d'idempotence que les kills ci-dessus.
	maj_progress_chasse(character, combat_doc.get("monstres", []))
	# Focalisation : objectif de la quête focalisée atteint → effacée (même save).
	effacer_si_objectif_atteint(character)

	# Affinités (même doc que l'XP → idempotent) : une victoire ensemble resserre les
	# liens ; laisser un compagnon se faire mettre à terre les abîme.
	for j, doc in compagnons_traites:
		delta = character_stats.AFFINITE_DELTA_VICTOIRE if status == "victoire" else 0
		if j.get("currentPV", 0) <= 0:
			delta += character_stats.AFFINITE_DELTA_KO
		if delta:
			recrutement.ajuster_affinite(character, doc["_id"], delta)

	if not _finalize_membre(combat_doc, joueur_principal, character, status):
		return False  # échec de sauvegarde → ne pas marquer, on réessaiera

	combat_doc["recompense_appliquee"] = True
	return True

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
	grant_xp, sync_equipment_bonus, carried_weight, poids_bounds, tirer_poids, item_ref_id,
	lieu_label, noter_victoire, resolve_item_ref, recompute_equipment_bonus, autre_main,
)
from utils.consommables import (
	caracts_avec_buffs, canalisation_bonus, est_consommable, effet_instantane, effets_de,
	esquive_bonus, regen_bonus,
	cumul_effets, identite_source, poser_effet, _as_int as _eff_int,
)
from utils import charge_magie
from utils.sorts import (
	part_durative, effets_d_arme, concat_degats, INCANTATION_PA_MAX,
	capacite_utilisable_combat, effets_agissent_sur_cible,
	est_incantation_longue, est_maintenu, pm_par_pa, seuil_concentration,
	sorts_eligibles_espece,
)
from utils.zones_effet import cases_effet
from utils.quetes import maj_progress_kills, maj_progress_chasse
# `utils/zones.py` est une FEUILLE (math/random seulement) : aucun cycle possible.
from utils.zones import profils_compatibles
from utils.focalisation import effacer_si_objectif_atteint
from utils import recrutement
from utils import montures as montures_util
from utils import escorte as escorte_util
from utils import animations as animations_util
from utils import jetons
from utils import journal

BATTLE_MAPS = [
	"map0001.jpg", "map0002.jpg", "map0003.jpg", "map0004.jpg",
	"map0005.jpg", "map0006.jpg", "map0007.jpg", "abandonned_church01.webp",
]

# Tag qui retire une battle map du tirage de décor ordinaire (`select_battle_map`) :
# une salle de donjon ne s'atteint que par son gardien. Filtre de DONNÉE — préféré à
# `donjon.donjon_de_lieu`, qui coûterait un find_docs à chaque entrée en combat.
TAG_BATTLE_MAP_EXCLU = "donjon"

# Donjon à étages : distance de Chebyshev minimale entre le point d'apparition FIXE du groupe
# et les monstres tirés sur l'étage. Sans elle, un monstre pourrait naître au contact du
# groupe et l'entrée furtive ne vaudrait rien. Repli sans contrainte sur un étage trop petit.
DISTANCE_MIN_APPARITION = 5


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


def _ajuster_charge_magique(joueur: dict, delta_poids: float, coef: float = 1.0) -> None:
	"""Suit la charge MAGIQUE au rythme de la charge physique, en combat.

	Le snapshot fige `charge_magique` à l'entrée (la résolution d'un coup ne lit pas la
	base) : chaque site qui bouge `charge` doit donc bouger celle-ci du même mouvement,
	sans quoi ramasser une carcasse alourdirait le sac sans alourdir la magie. `coef` est
	le `charge_magique` de l'objet quand on l'a sous la main ; à défaut 1.0, c'est-à-dire
	le poids physique — le repli déjà retenu partout ailleurs.

	⚠️ Repli sur `charge` quand la clé manque : un combat ouvert AVANT cette mécanique n'a
	pas de `charge_magique` sur ses snapshots, et doit continuer de tourner (CLAUDE.md §4).
	"""
	actuelle = joueur.get("charge_magique")
	if actuelle is None:
		actuelle = joueur.get("charge", 0)
	joueur["charge_magique"] = max(0.0, round(float(actuelle) + delta_poids * coef, 2))


def etat_charge_snapshot(joueur: dict) -> tuple:
	"""`(ratio, canalisation)` d'un SNAPSHOT de combat, à passer aux `liste_*_payload`.

	Hors combat ces listes mesurent la charge sur le doc personnage ; en combat c'est faux
	dès le premier ramassage — le butin vit sur le snapshot (`butin_ramasse`) et n'entre
	dans l'inventaire du doc qu'à la fin. Sans cette passerelle, l'étiquette d'une case
	resterait au tarif d'avant le ramassage pendant que le moteur, lui, facture le vrai.
	"""
	charge = joueur.get("charge_magique")
	if charge is None:
		charge = joueur.get("charge", 0)
	return (charge_magie.ratio_charge(charge, joueur.get("charge_max", 0)),
			joueur.get("canalisation", 0))


def bloc_charge_snapshot(joueur: dict) -> dict:
	"""Bloc `charge_magie` d'un SNAPSHOT, pour le payload de combat — même forme que celui
	que `fiche.bloc_fiche` publie en ville, pour que le client n'ait qu'un seul format."""
	charge = joueur.get("charge_magique")
	if charge is None:
		charge = joueur.get("charge", 0)
	return charge_magie.bloc_charge(charge, joueur.get("charge_max", 0),
									joueur.get("canalisation", 0))


def _penalite_charge_acteur(joueur: dict, capacite: dict | None) -> float:
	"""Pénalité de charge appliquée à CETTE capacité pour CET acteur, ici et maintenant.

	Lit le seul snapshot — aucune base, aucun doc personnage : c'est la règle absolue de
	la résolution d'un coup. Un acteur sans `charge_max` (monstre, invocation, fixture)
	donne un ratio de 0, donc aucune pénalité : la mécanique est celle des porteurs.
	"""
	ratio, canalisation = etat_charge_snapshot(joueur)
	return charge_magie.penalite_finale(ratio, capacite, canalisation)


def _maintien_du(joueur: dict, entree: dict) -> int:
	"""PM d'entretien réellement dus ce tour-ci pour ce sort maintenu, charge comprise.

	Écrit `maintien_effectif` sur l'entrée de concentration ET sur la chip correspondante
	(`effets_actifs`, retrouvée par `source_id`) : le client annonce `🔄 N PM/round` depuis
	la chip, et afficher la base pendant qu'on prélève le tarif chargé serait un mensonge
	à l'écran. **Source unique** du montant, partagée par le prélèvement de début de tour
	et par la pénalité d'un test de concentration réussi."""
	du = charge_magie.maintien_effectif(
		entree.get("maintien"), _penalite_charge_acteur(joueur, entree))
	entree["maintien_effectif"] = du
	sort_id = str(entree.get("sort_id") or "")
	for chip in joueur.get("effets_actifs") or []:
		if str(chip.get("source_id") or "") == sort_id:
			chip["maintien"] = du
			break
	return du


def _cout_pm_charge(joueur: dict, capacite: dict | None) -> int:
	"""PM de lancement d'une capacité sous la charge du porteur. **Source unique** : la
	garde « PM insuffisants » et le débit doivent lire exactement la même valeur, sinon un
	sort serait proposé puis refusé (ou pire, débité d'un autre montant)."""
	return charge_magie.cout_pm_effectif(
		(capacite or {}).get("cout_pm"), _penalite_charge_acteur(joueur, capacite))


# Origines de buffs lues à l'ENTRÉE en combat : tout sauf « aura » — l'aura de groupe
# d'exploration (`auras_recues`) y devient positionnelle (cf. `_recalculer_auras`).
_ORIGINES_SNAPSHOT: tuple = ("effet", "equipement", "competence")


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
	# Volant SOUS COUVERT (`_appliquer_couvert`) : V // 3, après les buffs — c'est la vitesse
	# effective qui est entravée, et l'entrave survit à l'expiration d'un buff.
	if acteur.get("sous_couvert"):
		stats["V"] = int(stats.get("V", 0) or 0) // COUVERT_DIVISEUR

	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	equipment = _equipment_bonus_de(acteur)
	# ⚠️ `des_cc_base` DOIT être repassé : sans lui, le premier effet posé ou expiré
	# recomposerait `degats_cc` à 1 dé et retirerait au monstre son attaque naturelle, en
	# silence et pour le reste du combat. Absent ⇒ 1, donc un combat déjà en base garde
	# rigoureusement le comportement d'avant (aucune migration).
	derived = compute_derived_stats(base, niveau=acteur.get("voc_niveau", 0), equipment=equipment,
									des_cc=int(acteur.get("des_cc_base", 1) or 1))

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

	⚠️ Un sort MAINTENU pose son entrée même sans part durative : un Mur de feu ou un Lien
	de vie n'a aucun buff propre — son effet vit ailleurs (une nappe, un autre corps) — mais
	il doit se voir dans les chips ✨ avec son entretien, faute de quoi le joueur paierait
	chaque round pour quelque chose d'invisible.
	"""
	eff = effets or {}
	maintien = _eff_int((source or {}).get("maintien"))
	if not part_durative(eff) and not maintien:
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
	if maintien:
		# ⚠️ `maintenu` fait SAUTER le décrément (cf. _tick_effets_combat) : « tant qu'il
		# peut payer, le sort reste actif ». `duree` ne veut donc plus rien dire pour lui —
		# c'est la concentration qui le tient, et le défaut de PM qui le fait tomber.
		entry["maintenu"] = True
		entry["maintien"] = maintien
		entry["restants"] = max(1, entry["restants"])
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
# `cap` : l'orientation d'un grand jeton (utils/jetons.py) — un pivot doit se révéler avec
# le glissement qu'il accompagne, pas avant.
CHAMPS_ETAT = ("currentPV", "currentPM", "vivant", "morte", "pos", "facing", "cap")


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
	if portee > 1 and not _vue_acteurs(grid["cells"], lanceur, cible):
		return {"error": "Ligne de vue obstruée."}
	return _appliquer_soutien(combat_doc, lanceur, cible, source, effets)


def _appliquer_soutien(combat_doc: dict, lanceur: dict, cible: dict, source: dict,
					   effets: dict) -> dict:
	"""Pose un effet BÉNÉFIQUE sur un allié — l'application seule, SANS aucune garde.

	Séparé de `_lancer_sur_allie` (qui garde portée, ligne de vue et « à terre ») parce
	qu'une ZONE de soutien sert des alliés que ces gardes refuseraient : la forme couvre
	sa propre distance, et elle a déjà été filtrée par le terrain et la ligne de vue
	depuis son ancre. L'appelant reste responsable d'écarter un allié à terre.
	"""
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


# ── Capacités offensives (sorts & compétences) : un coup, une zone ───────────────
# Les deux branches de `resolve_action` posaient le MÊME mécanisme (seuil, jet, dégâts,
# localisation, journal, part à durée) dans deux copies qui ne différaient que par la
# plume. La zone d'effet ayant besoin de le rejouer une fois PAR CIBLE, il devient un
# chokepoint unique, les libellés restant portés par la branche appelante.
#
# Champs disponibles dans chaque gabarit : {acteur} {cible} {nom} {nom_fumble} {ou}
# {dmg} {pv} {pv_max} {roll} {seuil}. ⚠️ `nom_fumble` existe parce que le repli du nom
# d'un sort diffère entre ses lignes (« un sort » / « le sort ») ; pour une compétence
# les deux valent la même chose.
TEXTES_SORT = {
	"kill_crit": "{acteur} lance {nom} d'une puissance CRITIQUE et pulvérise {cible} !",
	"kill": "{acteur} lance {nom} et élimine {cible} !",
	"crit": "{acteur} lance {nom} d'une puissance CRITIQUE : {cible} encaisse{ou} {dmg} "
			"dégâts ! (jet {roll} — PV : {pv}/{pv_max})",
	"hit": "{acteur} lance {nom} : {cible} encaisse{ou} {dmg} dégâts ! "
		   "(PV : {pv}/{pv_max})",
	"prend": "{acteur} lance {nom} sur {cible} : le sort prend.",
	"fumble": "{acteur} bafouille son incantation : {nom_fumble} lui explose au visage ! "
			  "(jet {roll} / seuil {seuil})",
	"miss": "{acteur} lance {nom} sur {cible} mais le sort se dissipe ! "
			"(jet {roll} / seuil {seuil})",
}
TEXTES_COMPETENCE = {
	"kill_crit": "{acteur} utilise {nom} — coup CRITIQUE — et élimine {cible} !",
	"kill": "{acteur} utilise {nom} et élimine {cible} !",
	"crit": "{acteur} utilise {nom} — coup CRITIQUE : {cible} encaisse{ou} {dmg} dégâts ! "
			"(jet {roll} — PV : {pv}/{pv_max})",
	"hit": "{acteur} utilise {nom} : {cible} encaisse{ou} {dmg} dégâts ! "
		   "(PV : {pv}/{pv_max})",
	"prend": "{acteur} utilise {nom} sur {cible} : la prise porte.",
	"fumble": "{acteur} rate complètement {nom} sur {cible} et se découvre ! "
			  "(jet {roll} / seuil {seuil})",
	"miss": "{acteur} utilise {nom} sur {cible} mais manque son coup ! "
			"(jet {roll} / seuil {seuil})",
}

# ── Profil d'une CAPACITÉ — la seule chose qui distingue un sort d'une compétence ──
# Sorts et compétences suivent le MÊME chemin de lancement (`_lancer_capacite`) : mêmes
# `effets`, mêmes cibles, mêmes mécaniques de round et de grille. Ce qui les sépare tient
# en cinq lignes, rassemblées ici plutôt que dispersées dans deux branches jumelles.
#
# ⚠️ Deux différences ne sont PAS cosmétiques :
#   - `notation` : une frappe de compétence en `cc` emprunte les dés de l'arme équipée
#     (`_degats_competence`) ; un sort n'emprunte rien ;
#   - `portee` : une compétence emprunte aussi l'ALLONGE de l'arme et en dérive son
#     drapeau `ranged` (une hallebarde frappe à 2 cases EN mêlée), là où un sort tient
#     simplement `portee > 1` pour « à distance ».
# Les trois autres (clé de résultat, textes de journal, verbe) sont de l'habillage.
PROFIL_SORT = {
	"cle": "sort",
	"textes": TEXTES_SORT,
	"verbe": "lance",
	"nom_defaut": "un sort",
	"icon_defaut": "🔮",
	"sans_effet": "Ce sort n'a aucun effet sur une cible.",
	"engage": "Un ennemi vous menace au corps à corps : impossible d'incanter.",
}
PROFIL_COMPETENCE = {
	"cle": "competence",
	"textes": TEXTES_COMPETENCE,
	"verbe": "utilise",
	"nom_defaut": "une compétence",
	"icon_defaut": "⚡",
	"sans_effet": "Cette compétence n'a aucun effet sur une cible.",
	"engage": "Un ennemi vous menace au corps à corps : impossible.",
}
PROFILS = {"sort": PROFIL_SORT, "competence": PROFIL_COMPETENCE}


def _profil_de(kind) -> dict:
	"""Profil d'une capacité par son type. Défaut `sort` — c'est le chemin historique, et
	un `kind` absent vient forcément d'un doc de combat écrit avant le partage."""
	return PROFILS.get(str(kind or "sort"), PROFIL_SORT)


def _notation_capacite(joueur: dict, doc: dict, effets: dict, profil: dict) -> str:
	"""Notation de dégâts d'une capacité qui part. Une COMPÉTENCE de contact ajoute les dés
	de l'arme en main (chokepoint `_degats_competence`) ; un sort garde les siens."""
	if not effets.get("degats"):
		return ""
	if profil["cle"] == "competence":
		return _degats_competence(joueur, doc, effets)
	return effets.get("degats", "")


def _portee_capacite(joueur: dict, doc: dict, profil: dict) -> tuple:
	"""`(portée effective, à distance ?)`. Une COMPÉTENCE emprunte l'allonge de son arme et
	en dérive `ranged` ; un sort est « à distance » dès que sa portée dépasse 1."""
	if profil["cle"] == "competence":
		return _portee_competence(joueur, doc)
	portee = max(1, int((doc or {}).get("portee", 1) or 1))
	return portee, portee > 1


def cibles_de_zone(combat_doc: dict, joueur: dict, monstre: dict, zone: dict,
				   grid: dict) -> list:
	"""Monstres vivants touchés par la ZONE d'une capacité offensive, cible désignée EN TÊTE.

	`zone` est la vue normalisée d'`utils/zones_effet` (None ⇒ la seule cible désignée).
	La géométrie est filtrée par le terrain et la ligne de vue DEPUIS L'ANCRE : une
	explosion ne brûle pas l'intérieur d'un mur et ne contourne pas l'angle d'un couloir.

	⚠️ **La cible DÉSIGNÉE est toujours de la liste**, même si la forme ne la couvre pas
	(zone ancrée sur le lanceur et poussée trop loin par son `decalage`, par exemple).
	C'est contre elle que la portée, la ligne de vue et l'engagement au corps à corps ont
	été validés, et c'est elle que le joueur a payé pour frapper : l'écarter rendrait un
	sort visiblement sans effet sur l'ennemi qu'on vient de désigner.

	⚠️ **Aucun tir ami.** Une zone hostile ne touche QUE des monstres : ni le lanceur, ni
	ses compagnons, ni ses montures, ni ses invocations. C'est une limite assumée du
	périmètre (le jeu n'a de tir ami nulle part), pas un oubli.
	"""
	if not zone:
		return [monstre]
	jx, jy = joueur["pos"]["x"], joueur["pos"]["y"]
	# Grand jeton : la forme se pose sur la case de son emprise la plus proche du lanceur, et
	# une victime est prise dès qu'UNE de ses cases est dans la forme (utils/jetons.py).
	cases = set(cases_effet(
		zone,
		(jx, jy),
		jetons.case_proche(monstre, jx, jy),
		joueur.get("facing", 0),
		praticable=lambda x, y: _passable(grid["cells"], x, y),
		vue=lambda x0, y0, x1, y1: _line_of_sight(grid["cells"], x0, y0, x1, y1),
	))
	autres = [m for m in combat_doc["monstres"]
			  if m["vivant"] and m is not monstre and m.get("pos")
			  and any(c in cases for c in jetons.cases_emprise(m))]
	return [monstre] + autres


def beneficiaires_de_zone(combat_doc: dict, lanceur: dict, principal: dict, zone: dict,
						  grid: dict) -> list:
	"""Alliés DEBOUT servis par la zone d'une capacité bénéfique, `principal` EN TÊTE.

	Jumeau de `cibles_de_zone` pour l'autre camp. `principal` est l'allié DÉSIGNÉ pour une
	capacité `cible: "allie"`, et le LANCEUR lui-même pour une capacité `cible: "soi"` —
	qui n'en désigne aucun, et dont la forme se pose donc toujours sur lui.

	⚠️ **Le lanceur profite d'une zone dans laquelle il se tient**, alors qu'il ne peut
	jamais être *désigné* comme allié (`allyTargets` l'exclut côté client). Les deux ne
	disent pas la même chose : une vague de soin centrée sur un compagnon blessé qui
	épargnerait le soigneur debout au milieu serait une surprise, pas une règle.

	⚠️ **Un allié à TERRE est écarté** — même raison que dans `_lancer_sur_allie` : le
	remettre en jeu changerait la condition de défaite et l'ordre du tour. Relever un
	compagnon mérite sa propre mécanique.

	⚠️ **Montures, personnes escortées et invocations sont de la partie** : elles sont sur
	la grille et déjà visables une par une, rien ne justifie qu'une nappe les traverse
	sans les toucher. Aucun MONSTRE n'en profite, symétrique exact du « pas de tir ami ».
	"""
	if not zone:
		return [principal]
	lx, ly = lanceur["pos"]["x"], lanceur["pos"]["y"]
	cases = set(cases_effet(
		zone,
		(lx, ly),
		jetons.case_proche(principal, lx, ly),
		lanceur.get("facing", 0),
		praticable=lambda x, y: _passable(grid["cells"], x, y),
		vue=lambda x0, y0, x1, y1: _line_of_sight(grid["cells"], x0, y0, x1, y1),
	))
	autres = [p for p in combat_doc.get("joueurs", [])
			  if p is not principal and p.get("pos") and p.get("currentPV", 0) > 0
			  and any(c in cases for c in jetons.cases_emprise(p))]
	return [principal] + autres


def _servir_zone_soutien(combat_doc: dict, lanceur: dict, principal: dict, source: dict,
						 effets: dict, zone: dict, grid: dict) -> list:
	"""Sert les alliés que la zone ajoute au bénéficiaire déjà traité. Rend leurs résultats.

	⚠️ À n'appeler qu'APRÈS que `principal` a reçu son dû (par `_lancer_sur_allie` pour une
	capacité `allie`, par la branche `soi` pour le lanceur) : il est en tête de la liste et
	volontairement sauté ici, sinon il encaisserait deux fois le même soin.
	"""
	return [_appliquer_soutien(combat_doc, lanceur, p, source, effets)
			for p in beneficiaires_de_zone(combat_doc, lanceur, principal, zone, grid)[1:]]


# ── Auras : passives à zone, POSITIONNELLES en combat ────────────────────────────
# Une aura (competences.est_aura) est portée par le snapshot de son émetteur (`auras`) et
# posée, sur chaque allié que sa zone couvre, comme une entrée VIVANTE d'`effets_actifs`
# marquée `aura: True` : régén, buffs et esquive passent alors par les chokepoints existants
# (`_tick_effets_combat`, `_refresh_snapshot_stats`, `cumul_effets` — donc NON cumulatives :
# deux prêtres qui se chevauchent ne soignent qu'une fois). L'entrée ne se décrémente pas et
# ne survit pas au combat (`_effets_a_reverser`).

def _entree_aura(aura: dict, emetteur: dict) -> dict:
	"""Entrée d'`effets_actifs` qu'une aura pose sur un allié couvert. `source_id` distingue
	les porteurs (deux prêtres = deux chips), le non-cumul tenant à `cumul_effets`."""
	return {
		"source_id": f"aura:{aura.get('id', '')}:{emetteur.get('id', '')}",
		"aura": True,
		"nom": aura.get("nom", "Aura"),
		"icon": aura.get("icon", "✨"),
		"buffs": dict(aura.get("buffs") or {}),
		"regen_pv": _eff_int(aura.get("regen_pv")),
		"regen_pm": _eff_int(aura.get("regen_pm")),
		"esquive": _eff_int(aura.get("esquive")),
		"restants": 0,
	}


def _entrees_aura_attendues(combat_doc: dict, grid: dict) -> dict:
	"""{id du snapshot: [entrées aura]} selon les positions du moment. Émetteur debout et
	placé seulement ; bénéficiaires = `beneficiaires_de_zone` ancrée sur l'émetteur (terrain,
	ligne de vue, alliés à terre écartés, jamais un monstre)."""
	attendues: dict = {}
	for emetteur in combat_doc.get("joueurs", []):
		auras = emetteur.get("auras") or []
		if not auras or not emetteur.get("pos") or emetteur.get("currentPV", 0) <= 0:
			continue
		for aura in auras:
			for p in beneficiaires_de_zone(combat_doc, emetteur, emetteur, aura.get("zone"), grid):
				attendues.setdefault(p.get("id"), []).append(_entree_aura(aura, emetteur))
	return attendues


def _poser_entrees_aura(acteur: dict, voulues: list) -> bool:
	"""Remplace les entrées `aura` d'un acteur ; recalcule ses dérivées SEULEMENT si elles
	changent. Rend True s'il y a eu changement."""
	actifs = acteur.get("effets_actifs") or []
	if [e for e in actifs if e.get("aura")] == voulues:
		return False
	acteur["effets_actifs"] = [e for e in actifs if not e.get("aura")] + voulues
	_refresh_snapshot_stats(acteur)
	return True


def poser_auras_propres(snap: dict) -> None:
	"""Pose sur un snapshot SES PROPRES auras, sans grille : le porteur est toujours dans sa
	zone (ancrée sur lui). Sert le simulateur, dont le duel 1D n'a ni grille ni allié — sans
	quoi le banc d'essai ignorerait une aura que le jeu applique."""
	_poser_entrees_aura(snap, [_entree_aura(a, snap) for a in (snap.get("auras") or [])])


def _recalculer_auras(combat_doc: dict, grid: dict | None = None) -> None:
	"""Chokepoint unique des auras : remet les entrées `aura` de chaque allié en accord avec
	les positions et les vivants. Appelé au placement, en tête de tour, en fin d'action et
	à chaque KO. ⚠️ IDEMPOTENT : aucun allié n'est touché si ses entrées n'ont pas changé
	(CLAUDE.md §17) — sinon chaque appel relancerait `_refresh_snapshot_stats` pour rien."""
	joueurs = combat_doc.get("joueurs") or []
	porteurs = [j for j in joueurs if j.get("auras")]
	if not porteurs and not any(e.get("aura") for j in joueurs
								for e in (j.get("effets_actifs") or [])):
		return
	if grid is None:
		grid = get_combat_grid(combat_doc)
	attendues = _entrees_aura_attendues(combat_doc, grid)
	for j in joueurs:
		_poser_entrees_aura(j, attendues.get(j.get("id"), []))


def _resoudre_coup_capacite(combat_doc: dict, joueur: dict, monstre: dict, source: dict,
							effets: dict, notation: str, mode_jet: str, canal: str,
							textes: dict, noms: dict) -> tuple:
	"""UN coup de capacité offensive sur UNE cible : jet, dégâts, journal, part à durée.

	Chokepoint partagé par les branches `sort` et `competence` de `resolve_action`, et
	rejoué une fois par cible d'une zone d'effet. Ne touche NI les PM, NI le compteur
	d'actions, NI la furtivité, NI la victoire : tout cela est propre au lancement, pas
	au coup, et se paie une seule fois même quand la zone frappe cinq ennemis.

	⚠️ `notation` est calculée par l'appelant (une compétence de contact y ajoute les dés
	de l'arme) : elle ne dépend pas de la cible, la recalculer par victime serait faux
	pour rien. En revanche la LOCALISATION et le jet de toucher sont retirés pour chacune
	— une boule de feu peut griller l'un et manquer l'autre.

	Rend `(resultat, jet)`.
	"""
	if mode_jet == "magique":
		seuil = _magic_hit_threshold(joueur.get("toucher_magique", 0), monstre.get("pm_def", 0))
	else:
		skill = joueur["cd"] if mode_jet == "cd" else joueur["cc"]
		seuil = _hit_threshold(skill, _defense_physique(monstre))
	jet = _resoudre_jet(joueur, monstre, seuil)
	ctx = {"acteur": joueur["nom"], "cible": monstre["nom"], "roll": jet["roll"],
		   "seuil": seuil, "ou": "", "dmg": 0,
		   "pv": monstre["currentPV"], "pv_max": monstre["pv_max"], **noms}
	anim = (source or {}).get("animation")

	if not jet["touche"]:
		cle = "fumble" if jet["fumble"] else "miss"
		combat_doc["log"].append(_avec_etat(_avec_vfx({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": cle,
			"texte": textes[cle].format(**ctx),
		}, cle, monstre.get("id", ""), acteur_id=joueur.get("id", "")), joueur))
		return {"hit": False, "fumble": jet["fumble"], "roll": jet["roll"], "seuil": seuil,
				"cible": monstre["nom"], "cible_id": monstre.get("id")}, jet

	if notation:
		touchee = tirer_localisation()
		ctx["ou"] = f" {ZONE_LIBELLE[touchee]}" if touchee in ZONE_LIBELLE else ""
		dmg = calculer_degats(joueur, monstre, notation, jet["mult_degats"], mode_jet,
							  zone=touchee)
	else:
		dmg = 0   # capacité de pur debuff : elle touche sans blesser
	avant_pv = monstre["currentPV"]
	monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
	ctx["dmg"] = dmg
	ctx["pv"] = monstre["currentPV"]

	# ── DÉGÂTS AUX PM ────────────────────────────────────────────────────────────
	# « Ils ne réduisent pas directement les PV. » Un sort peut porter les deux à la fois
	# (Éclair siphonnant : 10 aux PV et 5 aux PM).
	# ⚠️ AUCUNE soustraction des PA : une armure n'arrête pas une siphonie. C'est pour cela
	# que le jet passe par `roll_dice` en direct et non par `calculer_degats`.
	dmg_pm = 0
	notation_pm = (effets or {}).get("degats_pm") or ""
	if notation_pm:
		dmg_pm = roll_dice(notation_pm) * jet["mult_degats"]
		avant_pm = _eff_int(monstre.get("currentPM"))
		monstre["currentPM"] = max(0, avant_pm - dmg_pm)
		dmg_pm = avant_pm - monstre["currentPM"]

	# ── DRAIN ────────────────────────────────────────────────────────────────────
	# « Le drain ne récupère que sur les dégâts EFFECTIVEMENT infligés, et non sur les
	# dégâts théoriques du sort. » D'où l'écart réel de PV (`avant_pv − currentPV`) et non
	# `dmg` : le `max(0, …)` ci-dessus fait qu'un coup mortel de 40 sur une cible à 5 PV ne
	# nourrit le lanceur que de 5.
	# ⚠️ Rendu par la fonction, jamais crédité ici : le contrat de ce chokepoint est de ne
	# toucher ni les PM du lanceur, ni son action, ni sa furtivité, ni la victoire — et le
	# plafond `drain_max` vaut UNE FOIS PAR LANCEMENT, pas une fois par victime d'une zone.
	inflige = avant_pv - monstre["currentPV"]
	drain_pv = (inflige * _eff_int((effets or {}).get("drain_pv"))) // 100
	drain_pm = (inflige * _eff_int((effets or {}).get("drain_pm"))) // 100

	if dmg and monstre["currentPV"] <= 0:
		monstre["vivant"] = False
		cle, kind, geles = ("kill_crit" if jet["critique"] else "kill"), "kill", (joueur, monstre)
	elif dmg:
		cle = "crit" if jet["critique"] else "hit"
		kind, geles = cle, (joueur, monstre)
	else:
		# La ligne posée juste après par `_appliquer_effet_sur_cible` dira ce que la
		# cible encaisse ; celle-ci ne gèle donc PAS la cible (elle ne la change pas).
		cle, kind, geles = "prend", "hit", (joueur,)
	combat_doc["log"].append(_avec_etat(_avec_vfx({
		"tour": combat_doc["tour"],
		"acteur": joueur["nom"],
		"kind": kind,
		"texte": textes[cle].format(**ctx),
	}, canal, monstre.get("id", ""), anim, joueur.get("id", "")), *geles))

	# Ligne PROPRE aux dégâts de PM : `currentPM` est dans `CHAMPS_ETAT`, donc l'anneau de
	# mana de la cible ne bougera qu'à la révélation de cette ligne-ci. La fondre dans la
	# ligne de dégâts ferait chuter les deux jauges d'un coup, sans dire pourquoi.
	if dmg_pm:
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "hit",
			"texte": f"{monstre['nom']} voit sa magie se vider : −{dmg_pm} PM "
					 f"({monstre['currentPM']}/{monstre.get('pm_max', 0)}).",
		}, monstre))

	# Part à DURÉE sur la CIBLE : posée seulement si la capacité a TOUCHÉ, et jamais sur
	# une cible que le même coup vient d'abattre.
	effet_cible = _appliquer_effet_sur_cible(combat_doc, monstre, source, effets,
											 combat_doc["tour"])
	return {"hit": True, "dmg": dmg, "critique": jet["critique"],
			"cible": monstre["nom"], "cible_id": monstre.get("id"),
			"cible_pv": monstre["currentPV"],
			# Remontés au LANCEMENT, qui seul sait plafonner et créditer une fois.
			"dmg_pm": dmg_pm, "cible_pm": _eff_int(monstre.get("currentPM")),
			"drain_pv": drain_pv, "drain_pm": drain_pm,
			"effet_cible": dict(effet_cible) if effet_cible else None}, jet


def _resoudre_capacite_offensive(combat_doc: dict, joueur: dict, cibles: list,
								 source: dict, effets: dict, notation: str,
								 mode_jet: str, canal: str, textes: dict,
								 noms: dict) -> tuple:
	"""Le coup ci-dessus, joué sur CHAQUE cible de la zone. Rend `(resultat, jet_principal)`.

	Le résultat est celui de la cible DÉSIGNÉE (premier élément), enrichi de `cibles` —
	la liste complète — dès qu'il y en a plus d'une. Le client garde donc exactement le
	payload qu'il lisait avant pour une capacité mono-cible.

	⚠️ **Seul le jet de la cible désignée peut faire échouer critiquement le lanceur.**
	Chaque victime a bien son propre jet (elles n'ont ni la même défense ni la même
	chance), mais faire du fumble une loterie à N tirages punirait les zones larges
	exactement parce qu'elles sont larges — un cône de cinq cases deviendrait le geste le
	plus dangereux du jeu pour celui qui le lance.
	"""
	resultats = []
	jet_principal = None
	for cible in cibles:
		res, jet = _resoudre_coup_capacite(combat_doc, joueur, cible, source, effets,
										   notation, mode_jet, canal, textes, noms)
		if jet_principal is None:
			jet_principal = jet
		resultats.append(res)
	principal = dict(resultats[0])
	if len(resultats) > 1:
		principal["cibles"] = resultats
	# DRAIN : sommé sur toutes les victimes, plafonné UNE FOIS PAR LANCEMENT, puis crédité
	# au lanceur. ⚠️ C'est ici et pas dans `_resoudre_coup_capacite` : `drain_max` est le
	# plafond du SORT, pas celui de chaque victime — sinon une zone de cinq ennemis
	# rendrait cinq fois le plafond, et le sort le plus large serait aussi le plus
	# nourrissant.
	total_pv = sum(_eff_int(r.get("drain_pv")) for r in resultats)
	total_pm = sum(_eff_int(r.get("drain_pm")) for r in resultats)
	plafond = _eff_int((effets or {}).get("drain_max"))
	if plafond:
		total_pv = min(total_pv, plafond)
		total_pm = min(total_pm, plafond)
	if total_pv or total_pm:
		avant_pv, avant_pm = joueur["currentPV"], _eff_int(joueur.get("currentPM"))
		# Clampés aux max du lanceur : un drain ne fait pas déborder une jauge.
		joueur["currentPV"] = min(joueur.get("pv_max", avant_pv), avant_pv + total_pv)
		joueur["currentPM"] = min(joueur.get("pm_max", avant_pm), avant_pm + total_pm)
		gains = " / ".join(s for s in (
			f"+{joueur['currentPV'] - avant_pv} PV" if joueur["currentPV"] != avant_pv else "",
			f"+{joueur['currentPM'] - avant_pm} PM" if joueur["currentPM"] != avant_pm else "",
		) if s)
		if gains:
			combat_doc["log"].append(_avec_etat({
				"tour": combat_doc["tour"],
				"acteur": joueur["nom"],
				"kind": "sys",
				"texte": f"{joueur['nom']} draine la vie de ses victimes ({gains}).",
			}, joueur))
		principal["drain"] = {"pv": joueur["currentPV"] - avant_pv,
							  "pm": joueur["currentPM"] - avant_pm}
	return principal, jet_principal


def _tick_effets_combat(combat_doc: dict, acteur: dict) -> None:
	"""Début de tour d'un acteur : régén des effets, décrément, purge, recalcul.

	La `duree` compte donc en TOURS DU PORTEUR — même nombre qu'en exploration (où elle
	compte les déplacements), et indépendante du nombre de combattants.
	"""
	actifs = acteur.get("effets_actifs") or []
	# Régén PERMANENTE portée par le snapshot (objet équipé, passives) : elle joue à CHAQUE
	# tour, y compris sans le moindre effet à durée en cours — sortir en tête sur `not actifs`
	# la ferait disparaître dès qu'un focus magique est la seule source du porteur.
	# ⚠️ `.get(..., 0)` : un combat déjà en base n'a pas ces champs (aucune migration).
	base_pv = _eff_int(acteur.get("regen_pv_base"))
	base_pm = _eff_int(acteur.get("regen_pm_base"))
	if not actifs and not (base_pv or base_pm):
		return
	tour = int(combat_doc.get("tour", 0) or 0)

	# 1. Régénération (avant le décrément : un effet à 1 restant soigne une dernière fois).
	# ⚠️ Même arithmétique que `consommables.regen_bonus`, dont ceci est le pendant en
	# combat : les sources PERMANENTES s'ADDITIONNENT, le non-cumul (meilleure régén seule)
	# ne joue qu'ENTRE effets à durée. Les faire cumuler autrement ferait diverger la régén
	# d'un tour de combat de celle d'un tour de monde, pour un même porteur.
	cumul = cumul_effets(actifs)
	pv = base_pv + cumul["regen_pv"]
	pm = base_pm + cumul["regen_pm"]
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

	# 2. Décrément + purge. Une entrée posée CE tour-ci est épargnée — une entrée MAINTENUE
	# aussi, et pour toujours : sa durée n'est pas un compte à rebours mais la capacité de
	# son lanceur à payer l'entretien (cf. `_payer_maintiens`, qui la retire quand il ne le
	# peut plus). La décrémenter ferait tomber le sort au bout de `duree` tours alors même
	# que le mage paie, ce qui est exactement ce que « sort maintenu » exclut. Une AURA non
	# plus : elle dure tant que sa zone couvre le porteur (`_recalculer_auras`).
	restants, expires = [], []
	for eff in actifs:
		if eff.get("maintenu") or eff.get("aura") or int(eff.get("pose_tour", -1)) == tour:
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
	"""L'acteur peut-il franchir les falaises ? `volant`, posé par `_appliquer_couvert`."""
	return bool(actor.get("volant"))


# ── Vol et couvert ───────────────────────────────────────────────────────────
# Une espèce taguée `vol` (dragon, griffon, pégase…) VOLE : aucun terrain praticable (`>= 1`)
# ne la bloque, falaise comprise. Mais dans un lieu COUVERT (tag `couvert` : grotte,
# catacombes…) elle ne peut pas déployer ses ailes : elle marche, et lourdement — V // 3 et
# actions // 3. Un dragon ne vole pas dans une grotte.
#   • `vol_espece` est posé sur le snapshot à sa CONSTRUCTION (monstre, invocation) ou à
#     l'entrée (monture, depuis son espèce) ; clé ABSENTE sinon : un snapshot ordinaire reste
#     celui d'avant, à la lettre.
#   • `combat_doc["couvert"]` se décide à l'entrée et à chaque changement d'étage, depuis les
#     tags du LIEU du combat (battle map ∪ tags de zone). Absent (combat d'avant) ⇒ découvert.
#   • ⚠️ V // 3 est appliqué dans `_refresh_snapshot_stats`, APRÈS les buffs : c'est lui qui
#     recompose déplacement et initiative, et un buff de V qui expire ne doit pas effacer
#     l'entrave. `actions_max`, lui, est FIGÉ au snapshot (cf. `_refresh_snapshot_stats`) :
#     sa valeur d'origine est gardée dans `actions_max_libre`, pour la rendre à un étage
#     découvert.
TAG_ESPECE_VOL = "vol"
TAG_LIEU_COUVERT = "couvert"
COUVERT_DIVISEUR = 3


def espece_vole(espece: dict | None) -> bool:
	"""L'espèce vole-t-elle ? Tag `vol` sur le doc `espece:*`."""
	return TAG_ESPECE_VOL in ((espece or {}).get("tags") or [])


def lieu_couvert(*listes_tags) -> bool:
	"""Le lieu du combat est-il COUVERT ? Vrai si l'une des listes de tags porte `couvert`
	(battle map, zone d'exploration, étage)."""
	return any(TAG_LIEU_COUVERT in (tags or []) for tags in listes_tags)


def _appliquer_couvert(acteur: dict, couvert: bool) -> None:
	"""Pose l'état de vol d'un acteur selon le lieu. Sans `vol_espece`, ne touche à RIEN.
	Réversible : appelé à chaque changement d'étage, il rend ailes et actions à un étage
	découvert. Mute sans sauvegarder."""
	if not acteur.get("vol_espece"):
		return
	acteur["volant"] = not couvert
	if couvert:
		acteur["sous_couvert"] = True
	else:
		acteur.pop("sous_couvert", None)
	libre = int(acteur.setdefault("actions_max_libre", acteur.get("actions_max", 1)) or 1)
	acteur["actions_max"] = max(1, libre // COUVERT_DIVISEUR) if couvert else libre
	# Dérivées (V // 3 : déplacement, initiative…) puis budget du tour sur le nouveau max.
	_refresh_snapshot_stats(acteur)
	_refresh_actions(acteur)


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
	"""Distance de Chebyshev entre deux ACTEURS — entre leurs EMPRISES (utils/jetons.py).
	Chokepoint unique de toutes les portées et adjacences du moteur : deux 1x1 donnent
	exactement l'écart case à case d'avant, un grand jeton se touche par n'importe quel bord."""
	return jetons.distance(a, b)


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


def _vue_acteurs(cells: list, a: dict, b: dict) -> bool:
	"""Ligne de vue entre deux ACTEURS : vraie si AU MOINS UNE paire (case de a, case de b)
	se voit. Deux 1x1 ⇒ exactement `_line_of_sight` d'une case à l'autre ; un grand jeton
	dépasse d'un mur tant qu'une de ses cases reste à découvert."""
	cases_a = jetons.cases_emprise(a)
	cases_b = jetons.cases_emprise(b)
	return any(_line_of_sight(cells, x0, y0, x1, y1)
			   for (x0, y0) in cases_a for (x1, y1) in cases_b)


def _traversable_par(occupant: dict, traversant: dict | None) -> bool:
	"""`traversant` peut-il passer sur les cases d'`occupant` ? Seul un joueur JOUABLE, et
	seulement sur un grand allié NON JOUABLE (monture, personne escortée, invocation de plus
	d'une case) : l'échange de places qui débloque un 1x1 est géométriquement impossible avec
	un 2x2, qui enfermerait sinon le groupe. Les monstres, eux, n'y passent jamais."""
	return (traversant is not None and traversant.get("jouable", True) is not False
			and occupant.get("jouable") is False and jetons.est_grand(occupant))


def _occupied_set(combat_doc: dict, exclude: dict | None = None,
				  traversant: dict | None = None) -> set:
	"""Ensemble des (x,y) occupés par des acteurs vivants (hors `exclude`) — TOUTES les cases
	de chaque emprise. `traversant` (un joueur qui se déplace) ignore les grands alliés non
	jouables, qu'il a le droit de traverser (`_traversable_par`)."""
	occ = set()
	for j in combat_doc["joueurs"]:
		if j is not exclude and j.get("currentPV", 1) > 0 and not _traversable_par(j, traversant):
			occ.update(jetons.cases_emprise(j))
	for m in combat_doc["monstres"]:
		if m is not exclude and m["vivant"]:
			occ.update(jetons.cases_emprise(m))
	return occ


def _occupied_at(combat_doc: dict, x: int, y: int, traversant: dict | None = None) -> bool:
	return (x, y) in _occupied_set(combat_doc, traversant=traversant)


def _allie_echangeable(combat_doc: dict, x: int, y: int) -> dict | None:
	"""L'acteur NON JOUABLE (monture, personne escortée) vivant sur (x,y), ou None.

	⚠️ `jouable is False` STRICTEMENT : un joueur ordinaire n'a pas la clé, et un
	`.get("jouable")` falsy rendrait tout le groupe échangeable. Un compagnon jouable
	garde sa case — il a son propre tour pour s'en aller — et un monstre encore plus.
	⚠️ 1x1 SEULEMENT : un grand allié ne s'échange pas, il se traverse (`_traversable_par`)."""
	for j in combat_doc["joueurs"]:
		if (j.get("jouable") is False and j.get("currentPV", 1) > 0
				and not jetons.est_grand(j) and jetons.couvre(j, x, y)):
			return j
	return None


def _echange_possible(cells: list, a: dict, b: dict) -> bool:
	"""Deux acteurs peuvent-ils PERMUTER leurs cases ? Chacun doit pouvoir TENIR sur celle
	de l'autre — `_walkable` avec le vol de CELUI QUI ARRIVE, dans les deux sens. Un joueur
	volant posé sur une falaise n'échange donc pas avec une monture qui l'y suivrait mal."""
	return (_walkable(cells, b["pos"]["x"], b["pos"]["y"], _can_fly(a))
			and _walkable(cells, a["pos"]["x"], a["pos"]["y"], _can_fly(b)))


def _move_ap_used_for(actor: dict, cells_moved: int) -> int:
	"""AP consommés pour `cells_moved` cases : ceil(cells * actions_max / deplacement)."""
	dep = max(1, actor.get("deplacement", 1))
	return math.ceil(cells_moved * actor["actions_max"] / dep)


def _refresh_actions(actor: dict) -> None:
	"""Recalcule actions_restantes = actions_max - attaques - ramassages - consommations
	- sorts - compétences - éditions de barre - canalisation - pénalités - AP_déplacement.

	`penalites` = actions perdues sur échec critique (cf. _appliquer_fumble). Comme
	actions_restantes est TOUJOURS recalculé ici, une pénalité doit être un compteur :
	poser actions_restantes = 0 à la main serait écrasé au prochain appel.

	`canalisation` = PA versés CE TOUR dans une incantation longue (cf.
	_avancer_incantation). Même raison d'être un compteur, et même piège : une incantation
	qui poserait directement actions_restantes = 0 se ferait rendre son budget au premier
	déplacement du joueur."""
	used = (actor.get("attaques", 0) + actor.get("ramasses", 0)
			+ actor.get("consommes", 0) + actor.get("sorts", 0)
			+ actor.get("competences", 0) + actor.get("editions", 0)
			+ actor.get("canalisation", 0) + actor.get("penalites", 0)
			+ _move_ap_used_for(actor, actor.get("cells_moved", 0)))
	actor["actions_restantes"] = max(0, actor["actions_max"] - used)


def _reset_turn_budget(actor: dict, combat_doc: dict | None = None) -> None:
	"""Réinitialise le budget d'un acteur en début de tour.

	Seul hook « début de tour d'acteur » du moteur : c'est donc ici que les effets à durée
	régénèrent, se décrémentent et expirent, que l'entretien des sorts maintenus est prélevé
	et qu'une incantation longue avance (`combat_doc` fourni). Sans `combat_doc` — appels de
	test, monstres — le budget seul est réinitialisé.

	⚠️ ORDRE : entretien et incantation viennent APRÈS la remise à `actions_max`, parce que
	l'incantation DÉPENSE ce budget. Les inverser lui donnerait un tour d'avance, puis un
	budget plein pour agir malgré la canalisation.
	"""
	if combat_doc is not None:
		# Auras remises à jour AVANT la régén du tour : elle lit la couverture du moment.
		_recalculer_auras(combat_doc)
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
	# ⚠️ Remis à zéro ICI comme `editions`, et AVANT `_avancer_incantation` qui le remplit :
	# les PA versés dans l'incantation sont mémorisés par `pa_investis`, pas par ce compteur,
	# qui ne mesure que la dépense DU TOUR (cf. _refresh_actions).
	actor["canalisation"] = 0
	actor["actions_restantes"] = actor["actions_max"]
	_refresh_actions(actor)
	# ⚠️ `combat_doc` peut être le PSEUDO-DOC du simulateur (`{"tour", "log"}` seuls, cf.
	# utils/simulateur) : les deux helpers ci-dessous ne lisent que `tour`, `log` et
	# `joueurs` via `.get(...)`, et sortent en tête sur un acteur qui n'entretient ni ne
	# canalise rien — c'est-à-dire toujours, au banc d'essai.
	if combat_doc is not None:
		_payer_maintiens(combat_doc, actor)
		_avancer_incantation(combat_doc, actor)


def _avancer_tour(combat_doc: dict) -> None:
	"""Passe la main à l'acteur suivant d'`ordre_initiative` ; débordement ⇒ tour suivant.

	SOURCE UNIQUE de l'avancement — sept copies verbatim de ces quatre lignes vivaient dans
	les fins de tours serveur (monstre, défenseur, invocation) et dans `_resolve_until_player`.
	Le compteur `tour` n'avance QUE sur le débordement : c'est lui qui définit un « round »,
	et donc la cadence des effets à durée comme celle de l'entretien des sorts maintenus.

	⚠️ **N'est PAS le chemin de `_purger_invocations`**, qui RÉPARE l'index après un retrait
	(aucun `+1`, et un clamp à 0 en plus). Y router la purge ferait sauter un acteur à chaque
	invocation dissipée.
	"""
	idx = combat_doc["acteur_courant_index"] + 1
	if idx >= len(combat_doc["ordre_initiative"]):
		idx = 0
		combat_doc["tour"] += 1
	combat_doc["acteur_courant_index"] = idx


# ── Concentration : sorts MAINTENUS et incantations LONGUES ──────────────────────
# Deux états de snapshot, tous deux propres au COMBAT (jamais reversés sur un doc
# personnage, cf. `_finalize_membre`) :
#
#   acteur["concentrations"] = [{sort_id, nom, icon, maintien, cible_id}]
#       Ce que le lanceur ENTRETIENT. Prélevé en PM au début de CHACUN de ses tours
#       (`_payer_maintiens`), sans coûter le moindre PA. Ce qu'il ne peut plus payer tombe.
#
#   acteur["incantation"] = {sort_id, …, pa_total, pa_investis, pm_total, pm_verses, …}
#       Ce qu'il est en train de LANCER. Absorbe ses PA tour après tour
#       (`_avancer_incantation`) jusqu'à ce que le sort parte.
#
# Les deux sont FRAGILES : un coup encaissé déclenche un test de concentration par objet
# tenu (cf. `_tester_concentration`). C'est ce qui fait du mage un artilleur à protéger.
# ⚠️ Clés ABSENTES sur un combat déjà en base, et sur tout acteur qui n'a rien lancé : tout
# ce qui les lit sort en tête sur une liste vide (CLAUDE.md §4).


def _concentrations(acteur: dict) -> list:
	"""Liste (vivante) des sorts entretenus par l'acteur — vide s'il n'entretient rien."""
	return (acteur or {}).get("concentrations") or []


def _rompre_concentration(combat_doc: dict, acteur: dict, entree: dict, texte: str) -> None:
	"""Un sort maintenu s'arrête : entretien, effet, invocations et lien de vie disparaissent.

	CHOKEPOINT UNIQUE de l'arrêt — appelé par le défaut de paiement (`_payer_maintiens`),
	par l'échec d'un test de concentration et par la fin de combat. Trois choses à défaire,
	et les oublier laisserait des états orphelins que plus rien ne nettoierait :
	  1. l'entrée d'`effets_actifs` de même source (puis recalcul des dérivées) ;
	  2. les créatures que ce sort tenait sur la grille ;
	  3. le lien de vie posé sur le protégé — sinon il continuerait d'encaisser pour un
		 protecteur qui ne paie plus.

	⚠️ Mute sans sauver, comme tout `utils/*`. ⚠️ Tolère un `combat_doc` réduit (le
	pseudo-doc du simulateur n'a ni `joueurs` ni `monstres`).
	"""
	sort_id = str(entree.get("sort_id") or "")
	acteur["concentrations"] = [c for c in _concentrations(acteur)
								if str(c.get("sort_id") or "") != sort_id]

	# 1. L'effet qu'il portait — et celui qu'il avait posé AILLEURS.
	# ⚠️ Balaie TOUS les acteurs, monstres compris : un sort maintenu OFFENSIF (Mur de feu)
	# pose sa part durative sur ses VICTIMES, pas sur son lanceur. Ne nettoyer que ce
	# dernier laisserait le débuff en place pour toujours — et `maintenu` l'exempte
	# justement du décrément, donc plus rien ne l'aurait jamais retiré.
	porteurs = ([acteur] + list(combat_doc.get("joueurs") or [])
				+ list(combat_doc.get("monstres") or []))
	vus = set()
	for porteur in porteurs:
		if id(porteur) in vus:
			continue
		vus.add(id(porteur))
		avant = porteur.get("effets_actifs") or []
		restants = [e for e in avant if str(e.get("source_id") or "") != sort_id]
		if len(restants) != len(avant):
			porteur["effets_actifs"] = restants
			_refresh_snapshot_stats(porteur)

	# 2. Les créatures qu'il tenait. ⚠️ `_dissiper_invocation` et jamais un marquage à la
	# main : elle pose aussi `currentPV = 0`, que lisent `_joueurs_vivants` et `_occupied_set`.
	for invoc in list(combat_doc.get("joueurs") or []):
		if invoc.get("est_invocation") and str(invoc.get("sort_maintenu") or "") == sort_id:
			_dissiper_invocation(combat_doc, invoc,
								 f"{invoc['nom']} se dissipe : l'appel n'est plus tenu.")

	# 3. Le lien de vie qu'il tissait.
	cible_id = str(entree.get("cible_id") or "")
	for protege in list(combat_doc.get("joueurs") or []):
		lien = protege.get("lien_vie") or {}
		if lien and str(lien.get("source_id") or "") == sort_id and (
				not cible_id or protege.get("id") == cible_id):
			protege.pop("lien_vie", None)

	combat_doc.setdefault("log", []).append(_avec_etat(_avec_vfx({
		"tour": int(combat_doc.get("tour", 0) or 0),
		"acteur": acteur.get("nom", "?"),
		"kind": "sys",
		"texte": texte,
	}, "dissipation", acteur.get("id", "")), acteur))


def _payer_maintiens(combat_doc: dict, acteur: dict) -> None:
	"""Début de tour : l'acteur verse les PM d'entretien de chacun de ses sorts maintenus.

	« À chaque round, le jeteur doit dépenser le coût de maintien en PM. Tant qu'il peut
	payer ce coût, le sort reste actif. » Le maintien ne consomme AUCUN PA et n'empêche pas
	de lancer autre chose — c'est pour cela qu'il est prélevé ici et non par un compteur
	d'action.

	⚠️ Paiement dans l'ORDRE DE POSE, et chacun est tenté : celui qui n'est pas payable
	tombe, les suivants — moins chers — peuvent encore tenir. Faire tomber toute la file au
	premier impayé punirait le mage prévoyant qui garde un petit sort en réserve.
	⚠️ La `duree` compte en tours du PORTEUR partout dans le moteur (cf.
	`_tick_effets_combat`) : prélever au début du tour du lanceur met l'entretien à la même
	cadence, et le rend indépendant du nombre de combattants.
	"""
	for entree in list(_concentrations(acteur)):
		# ⚠️ L'entretien se REFACTURE à chaque tour au tarif de la charge COURANTE — c'est
		# l'inverse de l'incantation, qui fige le sien. Un mage qui ramasse un butin au
		# tour 3 doit sentir son mur de feu peser plus lourd au tour 4 ; il peut aussi
		# lâcher son sac pour le retenir. La base reste intacte sur l'entrée : seule
		# `maintien_effectif` bouge, sinon la pénalité se composerait avec elle-même.
		du = _maintien_du(acteur, entree)
		if du <= 0:
			continue
		if _eff_int(acteur.get("currentPM")) < du:
			_rompre_concentration(
				combat_doc, acteur, entree,
				f"{entree.get('icon', '✨')} {entree.get('nom', 'Le sort')} s'effondre : "
				f"{acteur.get('nom', '?')} n'a plus les {du} PM du maintien.")
			continue
		acteur["currentPM"] = _eff_int(acteur.get("currentPM")) - du


def _effets_a_reverser(snap: dict) -> list:
	"""Effets à durée d'un snapshot qui survivent à la SORTIE du combat.

	SOURCE UNIQUE des trois sites de `finalize_combat` (membre du groupe, monture, personne
	escortée) : un buff est un buff, qu'il ait été lancé avant le combat ou pendant, et il
	ne meurt pas avec lui. `pose_tour` n'a de sens qu'en combat et ne suit pas.

	⚠️ Un effet MAINTENU ne suit pas non plus, et c'est l'essentiel : il n'existe que tant
	que quelqu'un paie son entretien chaque round, et il n'y a pas de round en exploration.
	Le reverser tel quel poserait sur le personnage un buff que plus rien ne prélève et que
	plus rien ne fait tomber — permanent et gratuit, donc un exploit. Même raison pour une
	AURA : elle n'existe que tant que son porteur est à côté.
	"""
	return [
		{k: v for k, v in eff.items() if k not in ("pose_tour", "maintenu", "maintien")}
		for eff in (snap or {}).get("effets_actifs") or []
		if _eff_int(eff.get("restants")) > 0 and not eff.get("maintenu") and not eff.get("aura")
	]


def _payer_cout_pv(combat_doc: dict, joueur: dict, source: dict, cout_pv: int) -> None:
	"""Le lanceur paie une partie du prix en SANG (`effets.cout_pv`).

	« Certains effets peuvent remplacer tout ou partie de leur coût en PM par une dépense
	directe de PV, faisant de la vie du jeteur une ressource magique utilisable. »

	⚠️ Ces PV ne sont PAS des dégâts subis : ils ne déclenchent aucun test de concentration,
	ne passent par aucun lien de vie et ne rompent pas la furtivité. La dépense est
	volontaire — c'est le prix demandé, pas un coup reçu.
	⚠️ L'appelant a déjà garanti `currentPV > cout_pv` : le plancher est ici une ceinture.
	"""
	if cout_pv <= 0:
		return
	joueur["currentPV"] = max(1, _eff_int(joueur.get("currentPV")) - cout_pv)
	combat_doc.setdefault("log", []).append(_avec_etat({
		"tour": int(combat_doc.get("tour", 0) or 0),
		"acteur": joueur.get("nom", "?"),
		"kind": "sys",
		"texte": f"{joueur.get('nom', '?')} paie {(source or {}).get('nom', 'le sort')} "
				 f"de son sang : −{cout_pv} PV.",
	}, joueur))


def _armer_incantation(combat_doc: dict, joueur: dict, sdoc: dict, effets: dict,
					   cible_id: str | None, dx, dy, kind: str = "sort") -> dict:
	"""Arme une incantation LONGUE, puis y verse déjà les PA du tour en cours.

	Le sort ne part pas : il devient un état du snapshot que `_avancer_incantation` fera
	progresser à chaque tour du lanceur. La cible visée est mémorisée telle quelle et
	re-validée à la résolution.

	⚠️ `doc` et `effets` sont STOCKÉS dans le combat, pas relus plus tard : la résolution a
	lieu depuis `_reset_turn_budget`, qui n'a aucun accès à la base (tout `utils/combat` est
	du calcul pur). Ce sont des dicts normalisés, donc sérialisables tels quels.
	"""
	profil = _profil_de(kind)
	joueur["incantation"] = {
		"sort_id": sdoc.get("id", ""),
		# ⚠️ Le TYPE est mémorisé avec le reste : la résolution a lieu des tours plus tard,
		# depuis `_reset_turn_budget`, qui n'a aucun moyen de redeviner si ce qui s'arme est
		# un sort ou une compétence. Absent (bloc armé avant le partage) ⇒ `sort`.
		"kind": profil["cle"],
		"nom": sdoc.get("nom", profil["nom_defaut"]),
		"icon": sdoc.get("icon", profil["icon_defaut"]),
		"doc": dict(sdoc),
		"effets": dict(effets or {}),
		"cible_id": cible_id,
		"dx": dx,
		"dy": dy,
		"pa_total": max(1, int(sdoc.get("incantation", 1) or 1)),
		"pa_investis": 0,
		# ⚠️ **Le seul tarif de charge FIGÉ du jeu**, et c'est voulu : une incantation
		# absorbe tout le budget du lanceur et NE S'ABANDONNE PAS. Facturer au tarif du
		# moment où l'on s'engage est cohérent avec cet engagement — et recalculer à
		# chaque tranche ferait varier le prix d'un round à l'autre sous un ramassage.
		"pm_total": _cout_pm_charge(joueur, sdoc),
		"pm_verses": 0,
	}
	combat_doc.setdefault("log", []).append(_avec_etat({
		"tour": int(combat_doc.get("tour", 0) or 0),
		"acteur": joueur.get("nom", "?"),
		"kind": "sys",
		"texte": f"{joueur.get('nom', '?')} entame l'incantation de "
				 f"{sdoc.get('nom', profil['nom_defaut'])} "
				 f"({joueur['incantation']['pa_total']} PA).",
	}, joueur))
	_avancer_incantation(combat_doc, joueur)
	# ⚠️ Relu APRÈS l'avancement : le tour a pu la mener à terme (le sort est parti) ou la
	# rompre (plus de PM). Renvoyer le bloc capturé avant afficherait une barre de progression
	# pour une incantation qui n'existe plus.
	return {profil["cle"]: sdoc.get("nom"), "incantation": _incantation_payload(joueur)}


def _incantation_payload(joueur: dict) -> dict | None:
	"""Vue CLIENT de l'incantation en cours — None s'il n'y en a pas.

	⚠️ `doc` et `effets` en sont retirés : le client n'a rien à en faire, et le sort complet
	pèse plus lourd que tout le reste du payload d'action."""
	inc = (joueur or {}).get("incantation")
	if not inc:
		return None
	return {k: v for k, v in inc.items() if k not in ("doc", "effets")}


def _rompre_incantation(combat_doc: dict, joueur: dict, texte: str) -> None:
	"""L'incantation en cours s'arrête sans que le sort parte. Les PM déjà versés sont PERDUS.

	« Une interruption peut donc faire perdre les PM déjà dépensés » : c'est tout le risque
	du mage artilleur, et la raison pour laquelle ses alliés doivent le couvrir. Les
	composants consommés, eux, sont partis dès le démarrage — eux aussi sont perdus.
	"""
	inc = joueur.get("incantation")
	if not inc:
		return
	# ⚠️ Posé à None plutôt que retiré : `incantation` est dans `CHAMPS_ETAT`, et
	# `_avec_etat` ne photographie que les clés PRÉSENTES. Retirée, la fin de l'incantation
	# ne serait jamais gelée et la barre de progression du client resterait pleine jusqu'au
	# prochain rafraîchissement complet.
	joueur["incantation"] = None
	perdus = _eff_int(inc.get("pm_verses"))
	combat_doc.setdefault("log", []).append(_avec_etat(_avec_vfx({
		"tour": int(combat_doc.get("tour", 0) or 0),
		"acteur": joueur.get("nom", "?"),
		"kind": "sys",
		"texte": texte + (f" ({perdus} PM perdus)" if perdus else ""),
	}, "dissipation", joueur.get("id", "")), joueur))


def _avancer_incantation(combat_doc: dict, joueur: dict) -> None:
	"""Verse dans l'incantation en cours TOUS les PA dont le lanceur dispose ce tour.

	« Le jeteur dépense ses PA disponibles pour faire progresser l'incantation. Les PA
	investis sont conservés d'un round à l'autre. Le sort n'est lancé qu'une fois la
	totalité des PA nécessaires dépensée. »

	Arithmétique des PM, verrouillée par `tests/test_combat_incantation.py` sur l'exemple du
	livre de règles : la tranche vaut `ceil(cout_pm / incantation)` et la réserve baisse au
	fur et à mesure, donc **les derniers PA peuvent être gratuits** — un Météore de 15 PM en
	6 PA verse 3 PM par PA, les 15 PM sont couverts au 5ᵉ, et le 6ᵉ ne coûte rien.

	⚠️ Le sort part ICI, des tours après le clic, par le même chokepoint que le lancement
	direct (`_lancer_capacite`). Sa cible est RE-VALIDÉE à ce moment : morte ou hors de portée,
	le sort se perd — c'est le prix du temps d'incantation.
	⚠️ `joueur["canalisation"]` est un COMPTEUR (cf. `_refresh_actions`) : poser
	`actions_restantes = 0` serait écrasé au premier recalcul.
	⚠️ Tolère le pseudo-doc du simulateur : sortie en tête sur un acteur sans `incantation`,
	et `get_combat_grid` n'est appelé qu'au moment de résoudre.
	"""
	inc = joueur.get("incantation")
	if not inc:
		return
	pa_total = max(1, _eff_int(inc.get("pa_total")))
	pm_total = _eff_int(inc.get("pm_total"))
	tranche = -(-pm_total // pa_total)

	while _eff_int(inc.get("pa_investis")) < pa_total and joueur.get("actions_restantes", 0) > 0:
		du = min(tranche, pm_total - _eff_int(inc.get("pm_verses")))
		if du > 0 and _eff_int(joueur.get("currentPM")) < du:
			_rompre_incantation(
				combat_doc, joueur,
				f"{joueur.get('nom', '?')} n'a plus les {du} PM qu'exige la suite de "
				f"l'incantation : le sort se défait.")
			return
		if du > 0:
			joueur["currentPM"] = _eff_int(joueur.get("currentPM")) - du
			inc["pm_verses"] = _eff_int(inc.get("pm_verses")) + du
		inc["pa_investis"] = _eff_int(inc.get("pa_investis")) + 1
		joueur["canalisation"] = _eff_int(joueur.get("canalisation")) + 1
		_refresh_actions(joueur)

	if _eff_int(inc.get("pa_investis")) < pa_total:
		# Encore du chemin : une ligne par tour, pour que le joueur voie où il en est.
		combat_doc.setdefault("log", []).append(_avec_etat({
			"tour": int(combat_doc.get("tour", 0) or 0),
			"acteur": joueur.get("nom", "?"),
			"kind": "sys",
			"texte": f"{joueur.get('nom', '?')} poursuit son incantation de "
					 f"{inc.get('nom', 'un sort')} ({inc['pa_investis']}/{pa_total} PA).",
		}, joueur))
		return

	# L'incantation aboutit : le sort part MAINTENANT.
	# ⚠️ None et non un retrait — même raison que dans `_rompre_incantation` : la clé doit
	# rester présente pour que `_avec_etat` gèle sa disparition.
	joueur["incantation"] = None
	sdoc = dict(inc.get("doc") or {})
	# ⚠️ Les PM ont été versés par tranches : les redébiter ferait payer le sort deux fois.
	sdoc["cout_pm"] = 0
	grid = get_combat_grid(combat_doc)
	result, jet = _lancer_capacite(combat_doc, joueur, sdoc, inc.get("effets") or {},
								   inc.get("cible_id"), inc.get("dx"), inc.get("dy"), grid,
								   inc.get("kind", "sort"))
	if "error" in result:
		# Cible morte, hors de portée, plus de place pour l'invocation… Le sort est perdu,
		# et les PM avec lui : rien à rembourser, ils ont été dépensés round après round.
		combat_doc.setdefault("log", []).append(_avec_etat({
			"tour": int(combat_doc.get("tour", 0) or 0),
			"acteur": joueur.get("nom", "?"),
			"kind": "sys",
			"texte": f"{joueur.get('nom', '?')} achève son incantation dans le vide : "
					 f"{result['error']}",
		}, joueur))
		return
	if jet and jet["fumble"]:
		_appliquer_fumble(combat_doc, joueur)
	_check_victory(combat_doc)


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


def _place_actors(combat_doc: dict, grid: dict, point_apparition: dict | None = None) -> None:
	"""Place le groupe joueur puis disperse les monstres aléatoirement, en garantissant
	qu'ils peuvent rejoindre le personnage central.

	`point_apparition` ({x, y}, donjon à étages) : le central y est posé tel quel au lieu du
	tirage centre/bordure, et les monstres naissent à `DISTANCE_MIN_APPARITION` au moins.

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

	# Cases distinctes à loger dans la région — un grand jeton en compte plusieurs.
	need = sum(l * p for l, p in (jetons.dims_jeton(a) for a in joueurs + monstres))

	# 1-2. Mode + recherche d'une case type 1 pour le central dont la région
	#      atteignable est assez grande pour le groupe ET les monstres.
	main = joueurs[0]
	main_cell, region = None, set()
	spawn = None
	if point_apparition is not None:
		spawn = (int(point_apparition.get("x", -1)), int(point_apparition.get("y", -1)))
		if _walkable(cells, spawn[0], spawn[1]):
			main_cell, region = spawn, _reachable_region(cells, dims, nav, spawn)
		else:
			spawn = None   # point hors carte ou dans un mur : placement ordinaire
	if main_cell is None:
		mode = "centre" if random.random() < 0.5 else "bordure"
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
			if jetons.est_grand(j):
				# Grande monture : l'ancre la plus proche du central où toute l'emprise tient.
				ancres = sorted(free, key=lambda c: (max(abs(c[0] - main_cell[0]),
														 abs(c[1] - main_cell[1])), c[1], c[0]))
				if _poser_emprise(j, ancres, region, occupied, main):
					continue
				j.pop("jeton", None)   # nulle part où la loger : posée en 1x1 pour ce combat
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
			if jetons.est_grand(j):
				j.pop("jeton", None)   # le repli pose une case par acteur
			pos = fallback[i] if i < len(fallback) else (0, 0)
			j["pos"] = {"x": pos[0], "y": pos[1]}
			occupied.add(pos)
		region = _reachable_region(cells, dims, nav, (main["pos"]["x"], main["pos"]["y"]))

	# 4. Monstres : cases aléatoires de la région du central (toutes joignables).
	base = (main["pos"]["x"], main["pos"]["y"])
	for m in monstres:
		pool = [c for c in region if c not in occupied]
		if spawn is not None:
			loin = [c for c in pool
					if max(abs(c[0] - spawn[0]), abs(c[1] - spawn[1])) >= DISTANCE_MIN_APPARITION]
			pool = loin or pool
		if jetons.est_grand(m):
			# Grand jeton : ancres de la région dans un ordre aléatoire, tourné vers le groupe.
			ancres = sorted(pool)
			random.shuffle(ancres)
			if _poser_emprise(m, ancres, region, occupied, main):
				continue
			m.pop("jeton", None)   # carte trop petite : posé en 1x1 (fail-soft)
		if pool:
			pos = random.choice(pool)
		else:  # région saturée (carte minuscule) : repli sur la case libre la plus proche.
			pos = _nearest_passable(cells, dims, base[0], base[1], occupied)
		m["pos"] = {"x": pos[0], "y": pos[1]}
		occupied.add(pos)


def _caps_face_a(sonde: dict, repere: dict) -> list:
	"""Les deux caps à essayer pour poser un grand jeton : celui qui fait face à `repere`,
	puis celui de l'autre axe (toujours vers lui) — un couloir peut refuser le premier."""
	premier = jetons.cap_vers(sonde, repere)
	(sx, sy), (rx, ry) = jetons.centre(sonde), jetons.centre(repere)
	if premier in ("gauche", "droite"):
		second = "bas" if ry >= sy else "haut"
	else:
		second = "droite" if rx >= sx else "gauche"
	return [premier, second]


def _poser_emprise(acteur: dict, ancres, region: set, occupied: set, repere: dict) -> bool:
	"""Pose `acteur` (grand jeton) sur la première ancre de `ancres` où TOUTE son emprise tient
	dans `region` sans chevaucher `occupied`, en essayant les deux caps de `_caps_face_a`.
	Mute `pos`, `cap` et `occupied` ; rend False si rien ne tient (l'appelant décide du repli)."""
	for (x, y) in ancres:
		sonde = {"pos": {"x": x, "y": y}, "jeton": acteur.get("jeton")}
		for cap in _caps_face_a(sonde, repere):
			sonde["cap"] = cap
			cases = jetons.cases_emprise(sonde)
			if all(c in region and c not in occupied for c in cases):
				acteur["pos"] = {"x": x, "y": y}
				acteur["cap"] = cap
				occupied.update(cases)
				return True
	return False


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
		# Nom propre de l'exemplaire (`characters.renommer_ref`) → libellé du profil. COPIE :
		# le doc sort du cache de requête. Le non-cumul reste ancré sur l'`_id`, jamais le nom.
		if isinstance(ref, dict) and ref.get("nom_perso"):
			item = dict(item, nom=ref["nom_perso"])
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


def _profil_attaque(joueur: dict, mode: str | None = None) -> dict:
	"""Profil d'attaque du snapshot pour un MODE — sélecteur unique, pendant serveur du
	`attackProfile(mode)` du client. Deux replis, dans cet ordre : le mode demandé, puis la
	mêlée, puis les mains nues — `_weapon_attacks` posant toujours un `cac`, le dernier ne
	sert qu'aux snapshots d'avant `attaque_profils` (combat déjà en base : aucune migration).
	"""
	attaques = joueur.get("attaque_profils") or []
	profil = next((a for a in attaques if a.get("mode") == mode), None) if mode else None
	if profil is None:
		profil = next((a for a in attaques if a.get("mode") == "cac"), None)
	if profil is None:
		profil = {"mode": "cac", "portee": joueur.get("portee", 1), "ranged": False,
				  "toucher": "cc", "degats": "degats_cc"}
	return profil


def _profil_arme_monstre(monstre: dict) -> dict:
	"""Profil d'attaque PRINCIPAL d'un monstre : le meilleur mode À DISTANCE (tir puis
	jet) s'il en a un, sinon le corps à corps — c'est lui qui pilote à la fois le
	kiting (`_deplacement_ia`) et le coup porté. Repli mains nues par défaut : monstre
	sans `attaque_profils` (non-humanoïde, ou combat déjà en base — aucune migration)."""
	attaques = monstre.get("attaque_profils") or []
	for mode in ("tir", "jet", "cac"):
		profil = next((a for a in attaques if a.get("mode") == mode), None)
		if profil:
			return profil
	return {"mode": "cac", "portee": monstre.get("portee", 1), "ranged": False,
			"toucher": "cc", "degats": "degats_cc"}


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
	# ⚠️ Sans l'origine « aura » : l'aura de GROUPE d'exploration (`auras_recues`) n'entre pas
	# en combat, où une aura devient positionnelle (`_recalculer_auras`).
	stats = caracts_avec_buffs(character, origines=_ORIGINES_SNAPSHOT)
	# Base PERMANENTE (équipement + passives, SANS les effets temporaires) : c'est depuis
	# elle que _refresh_snapshot_stats recompose les dérivées à chaque changement d'effet.
	# `stats` ci-dessus = caracts_base + Σ buffs des effets entrants → le snapshot construit
	# ici et un refresh immédiat donnent exactement les mêmes valeurs.
	caracts_base = caracts_avec_buffs(character, origines=("equipement", "competence"))
	_regen_permanente = regen_bonus(character, origines=("equipement", "competence"))
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
	# Charge MAGIQUE (poids × coefficient `charge_magique` des items) et aide à la
	# canalisation : figées sur le snapshot parce que la résolution d'un coup n'a PAS le
	# droit de lire la base. Recalculées aux mêmes deux sites que `charge` (ramassage,
	# consommation), donc jamais périmées — cf. `_recompute_charge_magique`.
	charge_mag = round(charge_magie.charge_magique_portee(character, resolve_item_ref), 2)
	canalisation = canalisation_bonus(character, origines=_ORIGINES_SNAPSHOT)

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
		"charge_magique": charge_mag,
		"canalisation": canalisation,
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
		"esquive": esquive_bonus(character, origines=_ORIGINES_SNAPSHOT),
		# Part PERMANENTE seule : _refresh_snapshot_stats y rajoute celle des effets
		# vivants, qui varie au fil du combat.
		"esquive_base": esquive_bonus(character, origines=("equipement", "competence")),
		# Régén PERMANENTE (objet porté + passives), appliquée à chaque tour du porteur par
		# _tick_effets_combat. Part permanente SEULE, comme `esquive_base` : celle des effets
		# à durée vit dans `effets_actifs` et varie au fil du combat.
		# ⚠️ Elle N'INCLUT PAS la régén naturelle (ceil(R/20) PV, ceil(Vol/20) PM) du tour de
		# monde : on ne se soigne pas de soi-même sous le feu, seul un objet ou une passive
		# le fait. Ne pas la rajouter ici en croyant aligner les deux tours.
		"regen_pv_base": _regen_permanente[0],
		"regen_pm_base": _regen_permanente[1],
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
		# AURAS que CE combattant émet (passives à zone, dénormalisées par
		# competences.recompute_competences_bonus) : appliquées selon les positions par
		# `_recalculer_auras`. Absent (combat d'avant) ⇒ aucune aura.
		"auras": [dict(a) for a in ((character.get("competences_bonus") or {}).get("auras") or [])],
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

	# ⚠️ Le filtre `restriction_tags` est appliqué APRÈS le tirage de l'espèce, et pas une
	# fois pour toute la fournée : un pool peut mêler des espèces aux tags différents (le
	# donjon-mine oppose gobelins, rats, chauves-souris et araignées dans la même salle), et
	# un profil `distance` légitime sur le gobelin ne l'est pas sur le rat. Filtrer en amont
	# reviendrait à appliquer à tout le monde la contrainte de la plus pauvre en tags.
	# Mémoïsé par espèce : `nb` peut valoir une dizaine de monstres pour un pool de deux.
	compat: dict = {}
	monstres = []
	for i in range(nb):
		espece = (
			random.choices(pool, weights=poids_especes, k=1)[0]
			if poids_especes else random.choice(pool)
		)
		eid = espece.get("_id")
		if eid not in compat:
			compat[eid] = profils_compatibles(profils, espece)
		# Aucun compatible ⇒ `None`, donc le point médian de l'espèce (cf.
		# `build_monster_snapshot`) — exactement ce que produisait déjà un `profils` vide.
		# ⚠️ Ne JAMAIS replier ici sur la liste non filtrée : ce serait rouvrir le défaut.
		profil = _pick_profil(compat[eid], profil_weights)
		monstres.append(build_monster_snapshot(espece, profil, i))

	return monstres


def des_cc_espece(espece: dict) -> int:
	"""Nombre de dés de Force au corps à corps pour l'attaque NATURELLE de cette espèce.

	SEUL point de décision : une espèce sans le tag `humanoide` frappe avec ce qu'elle a
	sur elle (crocs, griffes, cornes) et gagne un dé de base supplémentaire — un humanoïde,
	lui, tire ses dégâts de l'arme qu'il équipe. La valeur est ensuite RECOPIÉE dans le
	snapshot (`des_cc_base`), parce que `_refresh_snapshot_stats` recompose `degats_cc` à
	chaque effet posé ou expiré : sans elle en mémoire, le premier debuff venu retirerait
	le dé en silence et il faudrait relire le doc espèce à chaque tour."""
	if character_stats.TAG_HUMANOIDE in ((espece or {}).get("tags") or []):
		return 1
	return max(1, int(character_stats.MONSTRE_DES_CC_NATURELS or 1))


def roll_monster_equipment(espece: dict) -> dict:
	"""Tire l'équipement d'un monstre HUMANOÏDE parmi `espece['items']` : un jet
	INDÉPENDANT par item éligible (world-var `MONSTRE_EQUIPEMENT_PROBA`), affecté à un
	slot libre parmi ceux que l'item couvre (`item['slots']`, même confiance que
	`_weapon_attacks`/`recompute_equipment_bonus`, qui ne valident pas davantage). Une
	arme `deux_mains` bloque l'AUTRE main SANS y rien écrire, comme l'équipement joueur
	(`liberer_pour_deux_mains`). Renvoie `{slot: item_id}` (chaîne, jamais {item, poids}
	: pas d'exemplaire personnalisé pour un monstre). Vide ⇒ armure naturelle + mains
	nues, à la lettre — c'est le repli de `build_monster_snapshot`."""
	items = [str(i) for i in (espece or {}).get("items") or [] if i]
	if not items:
		return {}
	pool = list(items)
	random.shuffle(pool)
	proba = character_stats.MONSTRE_EQUIPEMENT_PROBA
	slots: dict[str, str] = {}
	occupied: set[str] = set()
	for item_id in pool:
		item = get_doc(item_id)
		if not item or item.get("categorie") not in ("arme", "armure"):
			continue
		if random.random() >= proba:
			continue
		candidats = [s for s in (item.get("slots") or []) if s not in occupied]
		if not candidats:
			continue
		slot = random.choice(candidats)
		deux_mains = bool(item.get("deux_mains")) and slot in ("main_droite", "main_gauche")
		if deux_mains and autre_main(slot) in occupied:
			continue
		slots[slot] = item_id
		occupied.add(slot)
		if deux_mains:
			occupied.add(autre_main(slot))
	return slots


def roll_monster_sorts(espece: dict, niveau: int) -> list[str]:
	"""Sorts ATTRIBUÉS à un monstre humanoïde à sa création : X = niveau du profil,
	borné au nombre de sorts éligibles (`sorts.sorts_eligibles_espece`), tirés SANS
	REMISE. Stockés tels quels (`sorts_connus`, même champ/forme que
	`character['sorts_connus']`), jamais lancés par l'IA cette passe."""
	pool = sorts_eligibles_espece(espece, get_doc, find_docs)
	if not pool:
		return []
	x = max(0, min(int(niveau or 0), len(pool)))
	if x == 0:
		return []
	return [s["id"] for s in random.sample(pool, x)]


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

	des_cc = des_cc_espece(espece)
	is_humanoide = character_stats.TAG_HUMANOIDE in (espece.get("tags") or [])
	slots_monstre: dict = {}
	equipment = EquipmentBonus()
	attaque_profils = None
	if is_humanoide:
		slots_monstre = roll_monster_equipment(espece)
		if slots_monstre:
			equipment = recompute_equipment_bonus(slots_monstre)
		attaque_profils = _weapon_attacks({"slots": slots_monstre}, base_stats)
	derived = compute_derived_stats(base_stats, niveau=niveau, equipment=equipment, des_cc=des_cc)
	portee = max(1, int(_profil_arme_monstre({"attaque_profils": attaque_profils or []}).get("portee", 1)))
	# XP dérivée de la difficulté : niveau du profil + somme des stats du monstre.
	sum_stats = (
		base_stats.v + base_stats.f + base_stats.r + base_stats.ag
		+ base_stats.vol + base_stats.int_ + base_stats.cha + base_stats.ch
	)
	xp_reward = max(1, niveau * 4 + sum_stats // 10)

	snap = {
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
		# Dés de Force de son attaque naturelle (2 hors `humanoide`). FIGÉ à l'entrée comme
		# les autres `*_base`, et relu par `_refresh_snapshot_stats` : c'est ce qui fait
		# survivre le dé supplémentaire à un buff ou à un debuff de Force.
		"des_cc_base": des_cc,
		"esquive_base": 0,
		"regen_pv_base": 0,
		"regen_pm_base": 0,
		"effets_actifs": [],
		"profil_id": profil_id,
		"image": espece.get("image", ""),
		# Animation d'impact des attaques de CETTE espèce (vide = repli sur le canal
		# `monstre`). Copiée au snapshot : le doc `espece:*` n'est plus relu ensuite.
		"animation": str(espece.get("animation") or ""),
		"currentPV": max(1, derived.pv_max),
		"pv_max": max(1, derived.pv_max),
		# RÉSERVE DE MANA d'un monstre. Il ne lance rien — c'est une réserve à VIDER, pas à
		# dépenser : sans elle, un sort à `degats_pm` serait inerte sur la seule cible qu'il
		# puisse viser, et toute la mécanique anti-lanceur n'existerait que sur le papier.
		# ⚠️ Même formule que les joueurs (`compute_derived_stats` : Vol×2 + Int×2), donc
		# une bête sans volonté ni intelligence n'a rien à siphonner — ce qui est juste.
		# ⚠️ Un combat déjà en base n'a pas ces clés : tout ce qui les lit passe par
		# `.get(..., 0)` (CLAUDE.md §4). `_refresh_snapshot_stats` les recompose et les
		# re-clampe ensuite comme celles d'un joueur, sans une ligne de plus.
		"currentPM": max(0, derived.pm_max),
		"pm_max": max(0, derived.pm_max),
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
		# Un monstre SANS équipement n'a que son armure NATURELLE, uniforme : `pa_zones`
		# vide ⇒ tout est global, la localisation ne change rien pour lui. Un humanoïde
		# ARMÉ (armure tirée, cf. `roll_monster_equipment`) a un `derived.pa_zones` non
		# vide, exactement comme un joueur équipé — même formule, aucun cas particulier.
		"pa_zones": dict(derived.pa_zones),
		"pm_def": derived.pm_def,
		"degats_cc": derived.degats_cc,
		"initiative": derived.initiative,
		"deplacement": derived.deplacement,
		"portee": portee,
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
	# Grand jeton (utils/jetons.py) : clé ABSENTE pour une espèce 1x1 sans forme, dont le
	# snapshot reste celui d'avant, à la lettre. `cap` est posé au placement.
	jeton = jetons.jeton_espece(espece)
	if jeton:
		snap["jeton"] = jeton
	# Espèce VOLANTE : l'état de vol (ou l'entrave sous couvert) est posé à l'entrée dans le
	# lieu du combat (`_appliquer_couvert`). Clé absente sinon, même parti pris que `jeton`.
	if espece_vole(espece):
		snap["vol_espece"] = True
	# Équipement et sorts d'un humanoïde : clés ABSENTES sinon (non-humanoïde, ou
	# humanoïde sans rien tiré) — même parti pris que `jeton`/`vol_espece` ci-dessus,
	# et même comportement d'avant pour un humanoïde nu (`_profil_arme_monstre` retombe
	# alors sur son repli mains nues, identique à ce qu'`attaque_profils` porterait).
	if is_humanoide and slots_monstre:
		snap["slots"] = slots_monstre
		snap["equipment_bonus"] = equipment.model_dump()
		snap["attaque_profils"] = attaque_profils
		# `cd`/`degats_cd` manquent à TOUT snapshot monstre (`_refresh_snapshot_stats` les
		# recompose seulement au premier effet posé, cf. `_equiper_snapshot` côté
		# simulateur) : sans eux ICI, un humanoïde à l'arc toucherait avec un `cd` de 0
		# et ses dégâts retomberaient sur `degats_cc` (mêlée) tant qu'aucun buff/debuff
		# n'avait forcé le recalcul. Posés seulement s'il a un profil À DISTANCE qui les
		# lit — un humanoïde mêlée n'en a pas plus besoin qu'une bête.
		if attaque_profils and any(p.get("mode") in ("tir", "jet") for p in attaque_profils):
			snap["cd"] = derived.cd
			snap["degats_cd"] = derived.degats_cd
	if is_humanoide:
		sorts_connus = roll_monster_sorts(espece, niveau)
		if sorts_connus:
			snap["sorts_connus"] = sorts_connus
	return snap


# ── Invocations ──────────────────────────────────────────────────────────────
# Une INVOCATION est une créature ALLIÉE apparue en plein combat par un sort (bloc
# `invocation` du doc, normalisé par `utils.sorts.invocation_de`). Elle vit dans
# `combat_doc["joueurs"]`, comme une monture ou une personne escortée : tout ce qui parcourt
# cette liste — ciblage des monstres, jetons alliés, cases occupées, badges — la voit sans
# code neuf.
#
# Ce qui la distingue des deux autres acteurs `jouable: False` :
#   · elle a un TOUR, joué par le SERVEUR (`_run_invocation_turn`) : elle se DÉPLACE puis
#     frappe, là où la personne escortée qui se défend ne fait jamais un pas. Elle figure
#     donc dans `ordre_initiative` (comme une escortée qui se défend, jamais comme une
#     monture) — d'où l'exclusion explicite de la liste « hors tour » du bandeau ;
#   · elle est TEMPORAIRE : `invocation_restants` tours d'action, puis elle se dissipe ;
#   · elle n'a AUCUN doc en base (pas de `character_id`), ce qui suffit à la faire sauter
#     par `finalize_combat` (`doc = get_doc(cid) if cid else None`) et par les bénéficiaires
#     de `/collect` : ni XP, ni butin, ni affinité, ni sauvegarde. Rien d'elle ne survit au
#     combat, et c'est voulu.
#
# ⚠️ Elle reste `jouable: False` : `_combattants_vivants` ne la compte pas, donc un groupe
# entièrement à terre perd même si son invocation tient encore debout. Sans cela, un joueur
# KO derrière une créature invoquée bloquerait le combat sans que personne puisse jouer.


def build_invocation_snapshot(espece: dict, profil: dict | None, joueur_index: int,
							  duree: int, invocateur: dict | None = None) -> dict:
	"""Snapshot d'UNE créature invoquée, côté JOUEUR — `build_monster_snapshot` re-keyé.

	Mêmes stats dérivées qu'un monstre de la même espèce (c'est le même bestiaire), donc le
	même travail de dérivation, mais un id `joueur_*` : c'est lui que lisent `_get_joueur`,
	`_resolve_until_player` et la branche `est_joueur` de `_do_attack_on`.

	`profil is None` → point médian de l'espèce au niveau 1 : DÉTERMINISTE (le tirage d'un
	`profil:*` passe par `roll_monster_stats`, donc par `random`). C'est le défaut des sorts
	qui ne nomment pas de profil.
	"""
	snap = build_monster_snapshot(espece, profil, joueur_index)
	snap["id"] = f"joueur_{joueur_index}"
	# Clés qui n'ont de sens que sur un ENNEMI : une invocation ne se loote pas, ne rapporte
	# aucune XP et n'a personne à détecter. `vivant` en particulier doit disparaître — du
	# côté joueur, c'est `currentPV > 0` qui fait foi (cf. `_joueurs_vivants`), et un
	# `vivant: True` figé dans les entrées de journal (`CHAMPS_ETAT`) mentirait au client.
	for cle in ("vivant", "detecte", "xp_reward"):
		snap.pop(cle, None)
	snap["jouable"] = False
	snap["est_invocation"] = True
	snap["invocation_restants"] = max(1, int(duree or 1))
	snap["invocateur_id"] = str((invocateur or {}).get("id") or "")
	snap["invocateur_nom"] = str((invocateur or {}).get("nom") or "")
	# Pas de magie : une créature invoquée ne lance rien. Posés explicitement parce que
	# `_tick_effets_combat` et les anneaux de badge les lisent.
	snap["currentPM"] = 0
	snap["pm_max"] = 0
	# Esquive : un monstre n'en porte pas de clé, mais `_defense_physique` la lit sur la
	# CIBLE — un debuff d'esquive posé sur l'invocation doit avoir où atterrir.
	snap["esquive"] = 0
	# Profil d'attaque explicite (et non le repli « mains nues » de `_profil_attaque`) :
	# c'est lui qui porte l'animation d'impact de l'espèce, sans quoi les coups de la
	# créature seraient muets là où ceux du même monstre en face s'animent.
	# ⚠️ Une invocation HUMANOÏDE garde le sien (posé par `build_monster_snapshot` :
	# arme tirée, portée réelle) au lieu d'être écrasée en mêlée forcée — c'est ce qui
	# lui permet de kiter comme n'importe quel monstre archer (`_run_invocation_turn`).
	if character_stats.TAG_HUMANOIDE not in (espece.get("tags") or []):
		snap["attaque_profils"] = [{
			"mode": "cac", "portee": snap.get("portee", 1), "ranged": False,
			"toucher": "cc", "degats": "degats_cc",
			"label": espece.get("nom", "Griffes"),
			"animation": str(espece.get("animation") or ""),
		}]
	return snap


def _prochain_index_joueur(combat_doc: dict) -> int:
	"""Prochain indice de snapshot `joueur_*` JAMAIS attribué dans ce combat, et le réserve.

	⚠️ SURTOUT PAS `len(joueurs)` : une invocation purgée libère son indice, qui serait
	réattribué à la suivante. Or les entrées de journal déjà écrites portent l'état des
	acteurs PAR ID (`_avec_etat`, `_avec_vfx`) — une ligne de la créature d'avant irait
	alors s'appliquer à celle d'après, et le client la verrait mourir en naissant.

	Le compteur vit sur le doc (donc il survit au retrait ET au tour suivant). Absent
	— combat déjà en base, ou premier appel — il repart du plus grand indice présent + 1,
	ce qui est exact : aucune invocation n'a pu être purgée avant le premier appel.
	"""
	suivant = combat_doc.get("prochain_joueur_index")
	if not isinstance(suivant, int):
		suivant = 0
		for j in combat_doc.get("joueurs") or []:
			suffixe = str(j.get("id", "")).rsplit("_", 1)[-1]
			if suffixe.isdigit():
				suivant = max(suivant, int(suffixe) + 1)
	combat_doc["prochain_joueur_index"] = suivant + 1
	return suivant


def _cases_invocation(combat_doc: dict, grid: dict, origine: dict, nombre: int,
					  jeton: dict | None = None) -> list:
	"""Jusqu'à `nombre` places libres où faire apparaître des créatures autour d'`origine`,
	les plus proches d'abord. Chaque place : `{"pos", "cap", "reduit"}`.

	Bornées à la RÉGION ATTEIGNABLE depuis l'invocateur (`_reachable_region`, mêmes règles
	de terrain et de `nav` que l'A* de déplacement) : une créature ne doit jamais surgir
	derrière un mur, d'où elle ne pourrait ni rejoindre l'ennemi ni être rejointe. Renvoie
	moins de places que demandé s'il n'y a pas la place — et une liste vide si l'invocateur
	est totalement encerclé, ce que l'appelant traite comme un échec du sort.

	Grand `jeton` : toute l'emprise doit tenir ; sinon la créature est posée en 1x1
	(`reduit: True`), comme au placement initial.
	"""
	ox, oy = origine["pos"]["x"], origine["pos"]["y"]
	occupees = _occupied_set(combat_doc)
	region = _reachable_region(grid["cells"], grid["dims"], grid.get("nav", {}), (ox, oy))
	libres = [c for c in region if c not in occupees]
	libres.sort(key=lambda c: (max(abs(c[0] - ox), abs(c[1] - oy)), c[1], c[0]))
	places = []
	for _ in range(max(0, int(nombre))):
		sonde = {"jeton": jeton}
		if jetons.est_grand(sonde) and _poser_emprise(sonde, libres, region, occupees, origine):
			places.append({"pos": sonde["pos"], "cap": sonde["cap"], "reduit": False})
			continue
		case = next((c for c in libres if c not in occupees), None)
		if case is None:
			break
		occupees.add(case)
		places.append({"pos": {"x": case[0], "y": case[1]}, "cap": None,
					   "reduit": jetons.est_grand(sonde)})
	return places


def invoquer(combat_doc: dict, lanceur: dict, sort: dict, grid: dict) -> list:
	"""Fait apparaître les créatures du bloc `invocation` de `sort` (vue normalisée) autour
	de `lanceur`, et les inscrit dans le combat. Renvoie les snapshots créés (vide = aucune
	case libre : le sort n'a rien pu appeler).

	⚠️ Elles sont insérées dans `ordre_initiative` JUSTE APRÈS l'acteur courant, et non à
	leur rang d'initiative : tout ce qui précède l'index courant garderait sinon un rang
	décalé d'un cran, et `acteur_courant_index` désignerait brusquement quelqu'un d'autre en
	plein tour. Elles jouent donc dès le tour où on les appelle — ce que dit déjà la fiction
	(« il surgit ») — puis suivent l'ordre comme tout le monde.
	"""
	invocation = sort.get("invocation") or {}
	espece = get_doc(invocation.get("espece"))
	if not espece or espece.get("type") != "espece":
		return []
	profil = get_doc(invocation["profil"]) if invocation.get("profil") else None
	if profil is not None and profil.get("type") != "profil":
		profil = None

	places = _cases_invocation(combat_doc, grid, lanceur, invocation.get("nombre", 1),
							   jetons.jeton_espece(espece))
	crees = []
	for place in places:
		snap = build_invocation_snapshot(
			espece, profil, _prochain_index_joueur(combat_doc),
			invocation.get("duree", 1), lanceur)
		# Sort d'origine : c'est par lui que `_enregistrer_concentration` reconnaît les
		# créatures que CE lancement vient d'appeler. Sans lui, un second sort d'invocation
		# maintenu adopterait les créatures du premier.
		snap["sort_id"] = sort.get("id", "")
		# Créature volante appelée sous couvert : entravée comme les autres.
		_appliquer_couvert(snap, bool(combat_doc.get("couvert")))
		snap["pos"] = place["pos"]
		if place["cap"]:
			snap["cap"] = place["cap"]
		if place["reduit"]:
			snap.pop("jeton", None)
		combat_doc["joueurs"].append(snap)
		crees.append(snap)

	ordre = combat_doc["ordre_initiative"]
	insert_at = combat_doc["acteur_courant_index"] + 1
	for i, snap in enumerate(crees):
		ordre.insert(insert_at + i, snap["id"])
	return crees


def _dissiper_invocation(combat_doc: dict, invoc: dict, texte: str) -> None:
	"""Marque une invocation comme dissipée (elle quittera le combat à la prochaine purge).

	⚠️ `currentPV = 0` EN PLUS du drapeau : c'est ce que lisent `_joueurs_vivants` (ciblage
	des monstres) et `_occupied_set` (sa case redevient libre) — le drapeau seul la laisserait
	encaisser des coups et bloquer un passage jusqu'à la purge."""
	invoc["dissipe"] = True
	invoc["currentPV"] = 0
	combat_doc["log"].append(_avec_etat(_avec_vfx({
		"tour": combat_doc["tour"],
		"acteur": "Système",
		"kind": "sys",
		"texte": texte,
	}, "dissipation", invoc.get("id", "")), invoc))


def _purger_invocations(combat_doc: dict) -> None:
	"""Retire du combat les invocations dissipées ou abattues — CHOKEPOINT UNIQUE, appelé en
	tête de chaque itération de `_resolve_until_player`.

	Les retirer (plutôt que les laisser à 0 PV comme un compagnon à terre) est ce qui fait
	disparaître leur jeton côté client, qui reconstruit ses tokens depuis `joueurs` et purge
	ceux qu'il n'y voit plus. Mais cela DÉCALE `ordre_initiative` : l'index courant est donc
	recalculé sur l'acteur qu'il désignait, par comptage des entrées supprimées avant lui —
	jamais par recherche de son id, qui peut être justement celui qu'on retire.
	"""
	morts = {j["id"] for j in combat_doc["joueurs"]
			 if j.get("est_invocation") and (j.get("dissipe") or j.get("currentPV", 0) <= 0)}
	if not morts:
		return
	combat_doc["joueurs"] = [j for j in combat_doc["joueurs"] if j["id"] not in morts]
	ordre = combat_doc["ordre_initiative"]
	idx = combat_doc["acteur_courant_index"]
	retires_avant = sum(1 for i, aid in enumerate(ordre) if i < idx and aid in morts)
	combat_doc["ordre_initiative"] = [aid for aid in ordre if aid not in morts]
	idx -= retires_avant
	# L'acteur courant lui-même a pu partir : l'index garde alors sa valeur et désigne
	# celui qui a pris sa place. Débordement ⇒ tour suivant, comme partout ailleurs.
	if idx >= len(combat_doc["ordre_initiative"]):
		idx = 0
		combat_doc["tour"] += 1
	combat_doc["acteur_courant_index"] = max(0, idx)


def create_combat_doc(
	character: dict, monstres: list, zone_tags: list, map_image: str,
	battle_map: dict | None = None,
	furtivite_initiale: int = 0,
	compagnons: list | None = None,
	montures: list | None = None,
	proteges: list | None = None,
	point_apparition: dict | None = None,
	etages: dict | None = None,
	furtivite_groupe: dict | None = None,
) -> dict:
	"""`etages` (donjon à étages) : état de la descente, posé tel quel sur le doc — il retire
	la fin par victoire et la fuite, et ouvre l'action `emprunter`. Le groupe entier y entre
	furtif (`furtivite_groupe` = {character_id: bonus passif}), au `point_apparition` fixe."""
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
		# Gabarit relu sur l'ESPÈCE, jamais recopié sur le doc monture : une retouche du
		# bestiaire vaut tout de suite pour les bêtes déjà achetées (aucune migration).
		espece_monture = get_doc(m["espece"]) if m.get("espece") else None
		jeton = jetons.jeton_espece(espece_monture) if espece_monture else None
		if jeton:
			snap["jeton"] = jeton
		# Pégase, grand faucon… : même règle de vol qu'un monstre (relue sur l'espèce).
		if espece_vole(espece_monture):
			snap["vol_espece"] = True
		montures_snaps.append(snap)
	joueurs += montures_snaps

	# Personnes ESCORTÉES : même traitement qu'une monture — elles suivent le groupe, sont
	# sur la carte donc CIBLABLES, mais ne jouent pas. C'est tout l'enjeu de la quête : le
	# joueur doit s'interposer.
	# Exception : une personne qui SAIT SE DÉFENDRE (`se_defend`, posé par la spec de l'offre)
	# reçoit un tour, joué par le SERVEUR (`_run_defenseur_turn`) — jamais un pas, un coup sur
	# l'ennemi au contact. Elle reste `jouable: False` : défaite, échange de places et
	# finalisation (mort ⇒ échec de l'escorte) ne changent pas.
	# ⚠️ Pas de `charge_max` recalculé, contrairement aux montures : un protégé ne porte pas
	# pour le groupe (il est absent de `porteurs_effectifs`), la dérivée standard suffit.
	proteges_snaps = []
	for i, p in enumerate(proteges or []):
		snap = build_joueur_snapshot(p, joueur_index=len(joueurs) + i)
		snap["jouable"] = False
		snap["est_protege"] = True
		snap["deplacement"] = 0
		snap["deplacement_base"] = 0
		if p.get("se_defend"):
			snap["se_defend"] = True
		proteges_snaps.append(snap)
	joueurs += proteges_snaps

	# Vol ou entrave sous COUVERT (tags de la battle map ∪ tags de zone), AVANT l'ordre
	# d'initiative : V // 3 abaisse aussi l'initiative d'un volant entravé.
	couvert = lieu_couvert(zone_tags, (battle_map or {}).get("tags"))
	for acteur in joueurs + list(monstres):
		_appliquer_couvert(acteur, couvert)

	# ⚠️ `ordre_initiative` n'accueille QUE les acteurs qui ont un tour : une monture qui y
	# figurerait obtiendrait un tour que personne ne peut jouer (_resolve_until_player rendrait
	# la main au client sur un acteur qui n'a pas d'actions) — le combat s'arrêterait là.
	# La personne escortée qui se défend y entre, elle : son tour est joué par
	# `_resolve_until_player`, qui ne rend jamais la main sur elle.
	ordre = _ordre_par_initiative(
		[j for j in joueurs if j.get("jouable", True) or j.get("se_defend")] + list(monstres))

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
		# Lieu couvert : relu par les invocations (`invoquer`) ; recalculé à chaque étage.
		"couvert": couvert,
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
	_place_actors(combat_doc, grid, point_apparition)
	if etages is not None:
		combat_doc["etages"] = etages
		_entrer_en_furtivite(combat_doc, furtivite_groupe)
	# Auras posées dès le placement : les alliés côte à côte en profitent dès le tour 1.
	_recalculer_auras(combat_doc, grid)
	return combat_doc


def _ordre_par_initiative(acteurs: list) -> list:
	"""Ids des acteurs, meilleure initiative en tête (tri stable : à égalité, l'ordre de la
	liste — donc le camp du joueur, listé d'abord — l'emporte)."""
	return [a["id"] for a in sorted(acteurs, key=lambda a: a.get("initiative", 0), reverse=True)]


def _entrer_en_furtivite(combat_doc: dict, bonus_par_perso: dict | None = None) -> None:
	"""Donjon à étages : TOUT le groupe entre dans l'étage furtif — montures et personnes
	escortées comprises (visibles, elles attireraient tous les monstres sur le groupe). Le
	bonus passif de chaque membre (`competences.furtivite_passive`, calculé par l'appelant)
	est indexé par `character_id`. Les monstres de l'étage n'ont encore repéré personne."""
	bonus_par_perso = bonus_par_perso or {}
	for j in combat_doc["joueurs"]:
		j["furtif"] = True
		j["furtivite_bonus"] = int(bonus_par_perso.get(j.get("character_id"), 0) or 0)
	for m in combat_doc["monstres"]:
		m["detecte"] = False


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


def _portee_competence(joueur: dict, competence: dict) -> tuple:
	"""Portée EFFECTIVE d'une compétence et son caractère « à distance » — SOURCE UNIQUE.

	Même porte que `_degats_competence`, juste au-dessus, et pour la même raison : une frappe
	de CORPS À CORPS (`jet: "cc"` avec des dés) est un coup PORTÉ AVEC l'arme. Elle en emprunte
	les dés — et donc aussi l'ALLONGE : une arme d'hast frappe à 2 cases par `attaquer`, la
	compétence portée par cette même hallebarde doit frapper à 2 cases elle aussi.

	⚠️ `max` et NON un remplacement : une portée écrite par l'auteur n'est jamais rabaissée par
	l'arme en main.
	⚠️ Tout ce qui n'est pas une frappe `cc` à dés garde une allonge de 1 : un pur debuff de
	contact (entrave, cri), un soin `cible: "allie"` — `normaliser_competence` met `jet: "cc"`
	PAR DÉFAUT, on ne soigne pas au bout d'une hallebarde —, une compétence `cd` ou `magique`.
	⚠️ **Le second membre est le vrai piège.** La branche `competence` déduisait « à distance »
	de `portee > 1`, là où la branche `attaquer` lit le drapeau `ranged` du profil : hériter des
	2 cases d'une hast aurait rendu la compétence INTERDITE en mêlée et soumise à la ligne de
	vue, l'inverse même de ce qu'est une hast. `ranged` se mesure donc à l'allonge — on est « à
	distance » quand on frappe AU-DELÀ de ce que l'arme atteint. À allonge 1 la formule se réduit
	exactement à `portee > 1` : comportement d'avant à la lettre pour tout le reste.
	⚠️ Snapshot sans `attaque_profils` (combat déjà en base) ⇒ `_profil_attaque` retombe sur les
	mains nues, donc allonge 1 : aucune migration.
	"""
	comp = competence or {}
	portee = max(1, int(comp.get("portee", 1) or 1))
	effets = comp.get("effets") or {}
	if comp.get("jet", "cc") == "cc" and effets.get("degats"):
		allonge = max(1, int(_profil_attaque(joueur, "cac").get("portee", 1) or 1))
	else:
		allonge = 1
	portee = max(portee, allonge)
	return portee, portee > allonge


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


def passage_franchissable(combat_doc: dict, passage: dict) -> bool:
	"""Le groupe peut-il emprunter ce passage ? Le personnage PRINCIPAL doit être SUR sa
	case, et tous les combattants debout former avec lui une FILE continue : chacun adjacent
	(Chebyshev ≤ 1, entre emprises) à un autre, de proche en proche depuis le principal —
	un groupe de 7 peut s'étirer sur 7 cases, diagonale comprise. Montures, personnes
	escortées, invocations et membres à terre suivent sans condition ; le principal à terre
	aussi, la file part alors de n'importe quel combattant debout sur la case.

	⚠️ Surtout pas « tous à une case du passage » : au fond d'un couloir d'une case de large,
	le passage n'a qu'UNE voisine praticable, et un groupe de trois y restait enfermé pour
	toujours (on ne fuit pas un donjon) — cf. `test_un_couloir_en_cul_de_sac_se_franchit_en_file`."""
	pos = passage.get("pos") or {}
	x, y = pos.get("x"), pos.get("y")
	if x is None or y is None:
		return False
	combattants = _combattants_vivants(combat_doc)
	principal = next((j for j in combattants
					  if j.get("character_id") == combat_doc.get("character_id")), None)
	candidats = [principal] if principal else combattants
	tete = next((j for j in candidats if jetons.couvre(j, x, y)), None)
	if tete is None:
		return False
	relies, frontiere = [tete], [tete]
	restants = [j for j in combattants if j is not tete]
	while frontiere and restants:
		courant = frontiere.pop()
		voisins = [j for j in restants if _cheby(courant, j) <= 1]
		restants = [j for j in restants if _cheby(courant, j) > 1]
		relies.extend(voisins)
		frontiere.extend(voisins)
	return not restants


def annoter_passages(combat_doc: dict) -> dict:
	"""Pose `franchissable` sur chaque passage d'un donjon à étages, pour le client (qui ne
	recalcule jamais la règle). Recalculé à chaque réponse, jamais lu par le serveur."""
	for p in (combat_doc.get("etages") or {}).get("passages") or []:
		p["franchissable"] = passage_franchissable(combat_doc, p)
	return combat_doc


def _monstres_de_l_expedition(combat_doc: dict) -> list:
	"""Tous les monstres affrontés : ceux des étages quittés (archivés) puis ceux de l'étage
	courant. C'est la liste des kills, de l'XP et du bestiaire d'un donjon à étages."""
	archives = list((combat_doc.get("etages") or {}).get("archives") or [])
	return archives + list(combat_doc.get("monstres") or [])


def _etage_nettoye(combat_doc: dict) -> bool:
	"""Plus aucun ennemi vivant à l'étage courant."""
	return all(not m.get("vivant", True) for m in combat_doc.get("monstres") or [])


def butin_d_etage(combat_doc: dict) -> list:
	"""Butin de l'étage courant à répartir en le quittant : `[{monstre_id, cle, item_id, nom,
	poids}]` — carcasses (celles déjà ramassées en combat exclues) et objets équipés des
	humanoïdes, une ligne chacun (cf. `_butin_du_monstre`).

	⚠️ Poids tirés UNE fois et mémorisés sur `etages.butin_etage` (clé = l'étage) : l'overlay
	peut être fermé puis rouvert, un nouveau tirage à chaque ouverture laisserait le joueur
	relancer le dé jusqu'à obtenir la carcasse légère."""
	etages = combat_doc["etages"]
	memo = etages.get("butin_etage") or {}
	if memo.get("etage") != etages.get("etage"):
		dispo = []
		for m in combat_doc.get("monstres") or []:
			if m.get("vivant", True):
				continue
			dispo.extend(_butin_du_monstre(m))
		memo = {"etage": etages.get("etage"), "dispo": dispo}
		etages["butin_etage"] = memo
	# `loote` (ramassage en combat) ne retire que la CARCASSE ; les objets restent proposés.
	loote = {m["id"] for m in combat_doc.get("monstres") or [] if m.get("loote")}
	return [d for d in memo.get("dispo") or []
			if d.get("slot") or d.get("monstre_id") not in loote]


def _repartir_butin_d_etage(combat_doc: dict, dispo: list, attributions: list) -> str | None:
	"""Met les carcasses attribuées dans le `butin_ramasse` de leur bénéficiaire — celui que
	`_finalize_membre` verse au sac quelle que soit l'issue. Ce que personne n'emporte reste à
	l'étage. Refus GLOBAL (rien n'est pris) si un bénéficiaire est hors du groupe ou
	surchargé : miroir de `/collect`, charge lue sur le SNAPSHOT. Renvoie l'erreur ou None."""
	par_cle = {cle_butin(d): d for d in dispo}
	# Mêmes bénéficiaires que `/collect` : ni monture morte, ni personne escortée.
	membres = {j["character_id"]: j for j in combat_doc["joueurs"]
			   if j.get("character_id") and not j.get("morte") and not j.get("est_protege")}
	par_benef: dict = {}
	for a in attributions or []:
		cle, cid = a.get("cle") or a.get("monstre_id"), a.get("beneficiaire_id")
		if cle not in par_cle:
			continue
		if cid not in membres:
			return "Bénéficiaire hors du groupe de combat."
		par_benef.setdefault(cid, []).append(cle)
	for cid, cles in par_benef.items():
		j = membres[cid]
		if j.get("charge", 0) + sum(par_cle[c]["poids"] for c in cles) > j.get("charge_max", 0) + 1e-6:
			return f"Charge maximale dépassée pour {j.get('nom', 'ce personnage')}."
	monstres = {m["id"]: m for m in combat_doc.get("monstres") or []}
	for cid, cles in par_benef.items():
		j = membres[cid]
		for cle in cles:
			d = par_cle[cle]
			monstre = monstres.get(d.get("monstre_id")) or {}
			if d.get("slot"):
				# Objet équipé : pas de `loote`, qui ne marque que la carcasse.
				item = get_doc(d["item_id"])
			else:
				item = _ensure_loot_item(monstre.get("espece_id", ""), monstre.get("nom", ""))
				monstre["loote"] = True
			j.setdefault("butin_ramasse", []).append({"item": d["item_id"], "poids": d["poids"]})
			j["charge"] = round(j.get("charge", 0) + d["poids"], 2)
			_ajuster_charge_magique(j, d["poids"], charge_magie.coefficient_item(item or {}))
			combat_doc["log"].append({
				"tour": combat_doc["tour"],
				"acteur": j.get("nom", ""),
				"kind": "sys",
				"texte": f"{j.get('nom', '')} emporte {d.get('nom', 'une carcasse')}.",
			})
		_recompute_player_deplacement(j)
	combat_doc["etages"].pop("butin_etage", None)
	return None


def _sortir_du_donjon(combat_doc: dict, passage: dict) -> None:
	"""Remontée à la surface : la SEULE victoire d'un donjon à étages. L'XP est celle de
	toute la descente ; `sortie` est appliquée au personnage par `finalize_combat`, dans la
	même sauvegarde que l'XP (même garde d'idempotence)."""
	xp = sum(int(m.get("xp_reward", 0) or 0)
			 for m in _monstres_de_l_expedition(combat_doc) if not m.get("vivant", True))
	combat_doc["xp_gagnee"] = xp
	combat_doc["status"] = "victoire"
	combat_doc["sortie"] = {"lieu": passage.get("vers_lieu"),
							"pos": dict(passage.get("vers_pos") or {})}
	combat_doc["log"].append({
		"tour": combat_doc["tour"],
		"acteur": "Système",
		"kind": "sys",
		"texte": f"Le groupe remonte à l'air libre. {xp} XP gagnés.",
	})


def changer_d_etage(combat_doc: dict, lieu_doc: dict, point_apparition: dict,
					monstres: list, passages: list, bonus_par_perso: dict | None = None) -> None:
	"""Le même combat passe à l'étage `lieu_doc`. Mute sans sauvegarder.

	Conservé : les joueurs (PV, PM, effets, sorts maintenus, butin ramassé), le compteur de
	tours, le journal. Remplacé : la carte, les monstres (ceux de l'étage quitté sont
	archivés pour l'XP et les quêtes ; leurs carcasses restent en bas), les passages.
	Le groupe réapparaît au point fixe, furtif, et un ordre d'initiative neuf commence."""
	etages = combat_doc["etages"]
	etages.setdefault("archives", []).extend(combat_doc.get("monstres") or [])
	# Ids renumérotés à la suite de TOUS les monstres déjà vus : le journal garde les lignes
	# des étages passés, et deux `monstre_0` y désigneraient deux bêtes différentes.
	depart = len(etages["archives"])
	for i, m in enumerate(monstres):
		m["id"] = f"monstre_{depart + i}"
	combat_doc["monstres"] = monstres
	combat_doc["battle_map_id"] = lieu_doc["_id"]
	combat_doc.pop("grid_dims", None)
	combat_doc["map_image"] = lieu_doc.get("image", "")
	combat_doc["zone_tags"] = list(lieu_doc.get("tags") or [])
	# Couvert ou non, étage par étage : un griffon entravé dans les catacombes retrouve ses
	# ailes en débouchant sur une salle à ciel ouvert (`_appliquer_couvert` est réversible).
	# AVANT l'ordre d'initiative ci-dessous, qui lit l'initiative recomposée.
	couvert = lieu_couvert(combat_doc["zone_tags"])
	combat_doc["couvert"] = couvert
	for acteur in list(combat_doc["joueurs"]) + monstres:
		_appliquer_couvert(acteur, couvert)
	etages["etage"] = lieu_doc["_id"]
	etages["passages"] = list(passages)
	grid = {"dims": lieu_doc["dimensions"], "cells": lieu_doc["cells"],
			"nav": lieu_doc.get("nav", {})}
	_place_actors(combat_doc, grid, point_apparition)
	_entrer_en_furtivite(combat_doc, bonus_par_perso)
	joueurs_en_jeu = set(combat_doc["ordre_initiative"])
	combat_doc["ordre_initiative"] = _ordre_par_initiative(
		[j for j in combat_doc["joueurs"] if j["id"] in joueurs_en_jeu] + monstres)
	combat_doc["acteur_courant_index"] = 0
	combat_doc["log"].append({
		"tour": combat_doc["tour"],
		"acteur": "Système",
		"kind": "sys",
		"texte": f"Le groupe atteint {lieu_label(lieu_doc, lieu_doc['_id'])}.",
	})
	_recalculer_auras(combat_doc, grid)
	_resolve_until_player(combat_doc, grid, start_at_current=True)


def _flee_threshold(joueur_init: int, monstre_init_max: int) -> int:
	"""Seuil de fuite sur d100 : 50 + init joueur - meilleure init ennemie, clampé [5, 95]."""
	return max(5, min(95, 50 + joueur_init - monstre_init_max))


def _check_victory(combat_doc: dict) -> None:
	# Donjon à étages : un étage vidé n'est PAS une fin — on n'en sort que par un passage
	# vers la surface (`_sortir_du_donjon`) ou par la défaite.
	if combat_doc.get("etages"):
		return
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


def _poser_lien_vie(combat_doc: dict, lanceur: dict, protege: dict, sdoc: dict,
					effets: dict) -> None:
	"""Tisse un lien de vie entre le lanceur (PROTECTEUR) et l'allié désigné (PROTÉGÉ).

	Le bloc vit sur le PROTÉGÉ — c'est lui qui encaisse, donc lui que `_rediriger_lien_vie`
	interroge à chaque coup. Le lanceur, lui, porte la concentration qui le finance
	(cf. `_enregistrer_concentration`), et c'est par `source_id` que les deux se retrouvent
	quand le sort tombe.

	⚠️ Un lanceur ne se lie pas à lui-même : il encaisserait ce qu'il encaisse déjà, pour
	un entretien en PM. Le bloc est alors simplement ignoré.
	"""
	lien = (effets or {}).get("lien_vie")
	if not lien or not protege or protege is lanceur:
		return
	protege["lien_vie"] = {
		"protecteur_id": lanceur.get("id", ""),
		"protecteur_nom": lanceur.get("nom", "?"),
		"source_id": sdoc.get("id", ""),
		"part": int(lien.get("part", 0) or 0),
		"reduction": int(lien.get("reduction", 0) or 0),
	}
	combat_doc.setdefault("log", []).append(_avec_etat({
		"tour": int(combat_doc.get("tour", 0) or 0),
		"acteur": lanceur.get("nom", "?"),
		"kind": "sys",
		"texte": f"{lanceur.get('nom', '?')} tisse un lien de vie avec "
				 f"{protege.get('nom', '?')} : {lien.get('part', 0)} % des coups reçus "
				 f"lui reviendront.",
	}, lanceur))


def _verifier_saut(combat_doc: dict, sauteur: dict, effets: dict, dx, dy,
				   grid: dict) -> dict:
	"""Une destination de saut est-elle recevable ? `{}` si oui (ou si ce n'est pas un saut).

	SÉPARÉE de `_sauter` parce qu'elle est appelée DEUX fois : une première en tête de
	`_lancer_capacite`, AVANT le moindre débit de PM, et une seconde par `_sauter` lui-même.
	Sans la première, une case invalide coûtait le sort sans rien téléporter — alors que la
	règle du moteur est constante : un sort qui ne part pas ne se paie pas (cf.
	`_lancer_sur_allie`, « PM NON débités : le sort n'est jamais parti »).

	Ce qui n'est PAS vérifié fait tout l'intérêt du sort : ni `nav`, ni chemin praticable,
	ni ligne de vue. On franchit le mur, on ne le contourne pas.
	"""
	portee = max(0, int((effets or {}).get("saut", 0) or 0))
	if portee <= 0:
		return {}
	if not sauteur:
		return {"error": "Personne à téléporter."}
	if dx is None or dy is None:
		return {"error": "Aucune case de destination désignée."}
	nx, ny = int(dx), int(dy)
	dims, cells = grid["dims"], grid["cells"]
	if nx < 0 or nx >= dims["x"] or ny < 0 or ny >= dims["y"]:
		return {"error": "Hors de la zone."}
	# Portée mesurée d'EMPRISE à case, comme toutes les portées du moteur (`_cheby`) : une
	# grande créature saute depuis son bord le plus proche.
	if jetons.distance(sauteur, {"pos": {"x": nx, "y": ny}}) > portee:
		return {"error": "Destination hors de portée du saut."}

	# Emprise d'ARRIVÉE : une seule case pour un jeton ordinaire, le rectangle complet pour
	# une grande créature (cap courant — un saut ne fait pas pivoter la bête). Toutes doivent
	# être praticables ET libres. ⚠️ `exclude=sauteur` : il quitte ses propres cases, elles
	# ne doivent pas se bloquer elles-mêmes sur un saut court qui les recouvre.
	occupees = _occupied_set(combat_doc, exclude=sauteur)
	largeur, profondeur = jetons.dims_jeton(sauteur)
	w, h = jetons.dims_orientees(largeur, profondeur, jetons.cap_de(sauteur))
	for cx, cy in jetons.cases_rect(nx, ny, w, h):
		if cx < 0 or cx >= dims["x"] or cy < 0 or cy >= dims["y"]:
			return {"error": "Hors de la zone."}
		if not _walkable(cells, cx, cy, _can_fly(sauteur)):
			return {"error": "Terrain infranchissable à l'arrivée."}
		if (cx, cy) in occupees:
			return {"error": "Case occupée."}
	return {}


def _sauter(combat_doc: dict, lanceur: dict, sauteur: dict, effets: dict,
			dx, dy, grid: dict) -> dict:
	"""Téléporte `sauteur` sur la case (dx, dy) — coordonnées ABSOLUES. `{}` si pas un saut.

	« Le déplacement est instantané : les cases situées entre le départ et l'arrivée ne sont
	pas parcourues. » D'où ce qui n'est PAS vérifié, et qui fait tout l'intérêt du sort :
	ni `nav`, ni chemin praticable, ni ligne de vue. On franchit le mur, on ne le contourne
	pas. Restent la portée (Chebyshev depuis le sauteur), le terrain d'ARRIVÉE et la place.

	⚠️ `dx`/`dy` sont ici des coordonnées ABSOLUES, alors que la branche `deplacer` de
	`resolve_action` les clampe à [-1, 1] comme des deltas. Deux sémantiques sur un même
	champ, donc : c'est pourquoi seul `_sauter` les lit tels quels, et jamais l'inverse.
	⚠️ Journal : UNE seule entrée `move`, avec tout l'écart de `pos`. Le jeton glisse alors
	d'un trait sans parcourir les cases — la téléportation s'anime toute seule, sans une
	ligne de client (cf. `telluris-combat` § Révélation différée).
	⚠️ Un GRAND jeton doit tenir tout entier à l'arrivée, `cap` courant compris.
	"""
	if not (effets or {}).get("saut"):
		return {}
	erreur = _verifier_saut(combat_doc, sauteur, effets, dx, dy, grid)
	if erreur:
		return erreur

	nx, ny = int(dx), int(dy)
	ancienne = {"x": sauteur["pos"]["x"], "y": sauteur["pos"]["y"]}
	sauteur["pos"] = {"x": nx, "y": ny}
	combat_doc.setdefault("log", []).append(_avec_etat(_avec_vfx({
		"tour": int(combat_doc.get("tour", 0) or 0),
		"acteur": lanceur.get("nom", "?"),
		"kind": "move",
		"texte": f"{sauteur.get('nom', '?')} disparaît et reparaît en [{nx},{ny}].",
	}, "sort", sauteur.get("id", "")), sauteur))
	return {"saut": {"acteur_id": sauteur.get("id"), "de": ancienne,
					 "vers": {"x": nx, "y": ny}}}


def _rediriger_lien_vie(combat_doc: dict, defenseur: dict, dmg: int) -> tuple:
	"""Répartit un coup entre le protégé et son protecteur. N'APPLIQUE rien.

	Rend `(dégâts pour le défenseur, dégâts pour le protecteur, protecteur ou None)` ;
	l'appelant écrit les deux PV, de façon que la ligne de coup affiche déjà le bon total.

	« Le transfert ne crée pas de nouveaux dégâts : il déplace la perte de PV d'une cible
	vers une autre. » `reduction` est absorbée d'abord, `part` du reste part au protecteur —
	l'exemple du livre de règles (20 dégâts, part 50 %) donne bien 10 et 10.

	⚠️ Lien SANS protecteur valide (mort, à terre, ou disparu du combat) ⇒ comportement
	d'avant, à la lettre : le protégé encaisse tout. Un lien qui absorberait encore alors
	que son porteur est au sol protégerait gratuitement.
	⚠️ **Ce chokepoint n'est atteint que depuis `_do_attack_on`**, seul endroit où un acteur
	du camp du joueur perd des PV sous un coup. `_resoudre_coup_capacite` et
	`_frapper_monstre` ne frappent QUE des monstres, par construction — le jour où un
	monstre lancera un sort offensif par le premier, le lien de vie cessera de fonctionner
	en silence. Même angle mort au banc d'essai : `utils/simulateur` applique ses dégâts en
	parallèle, un duel 1 contre 1 n'ayant personne à protéger.
	"""
	lien = (defenseur or {}).get("lien_vie") or {}
	if not lien or dmg <= 0:
		return dmg, 0, None
	protecteur = next(
		(p for p in combat_doc.get("joueurs") or []
		 if p.get("id") == lien.get("protecteur_id") and p.get("currentPV", 0) > 0),
		None)
	if protecteur is None or protecteur is defenseur:
		return dmg, 0, None
	reduction = max(0, min(100, int(lien.get("reduction", 0) or 0)))
	part = max(0, min(100, int(lien.get("part", 0) or 0)))
	reduit = dmg - (dmg * reduction) // 100
	transfere = (reduit * part) // 100
	return reduit - transfere, transfere, (protecteur if transfere > 0 else None)


def _tester_concentration(combat_doc: dict, acteur: dict, attaquant: dict,
						  degats_subis: int) -> None:
	"""Un coup encaissé menace ce que l'acteur TIENT : son incantation et ses sorts maintenus.

	« Lorsqu'un lanceur subit une attaque pendant une incantation, il effectue un test de
	concentration. » Quatre issues, par objet tenu :
	  • réussite critique → rien ne bouge ;
	  • réussite         → ça tient, au prix d'une TRANCHE de PM (cf. sorts.pm_par_pa) ;
	  • échec            → l'incantation est perdue, ou le sort maintenu tombe ;
	  • échec critique   → idem, PLUS une action perdue (`_appliquer_fumble`).

	⚠️ **Un jet PAR objet tenu** — c'est le choix de conception retenu, à l'inverse de la
	règle des zones d'effet (un seul fumble possible, quel que soit le nombre de cibles).
	Ici la multiplication du risque est la contrepartie assumée d'entretenir plusieurs
	sorts à la fois : un mage qui en tient trois est trois fois plus exposé.
	⚠️ `_resoudre_jet` et non un `random` local : c'est lui qui fait que la CHANCE pilote
	les fenêtres de critique, celle du lanceur comme celle de qui le frappe.
	⚠️ Des PV dépensés volontairement (`effets.cout_pv`) n'atteignent JAMAIS ce test : ce
	sont un prix payé, pas un coup reçu.
	"""
	if not acteur.get("incantation") and not _concentrations(acteur):
		return
	seuil = seuil_concentration(acteur.get("vol", acteur.get("caracts_base", {}).get("Vol", 0)),
								degats_subis)

	def _issue():
		jet = _resoudre_jet(acteur, attaquant, seuil)
		if jet["critique"]:
			return "critique", jet
		if jet["fumble"]:
			return "fumble", jet
		return ("reussite" if jet["touche"] else "echec"), jet

	# 1. L'incantation en cours.
	inc = acteur.get("incantation")
	if inc:
		issue, _ = _issue()
		if issue == "reussite":
			penalite = min(_eff_int(acteur.get("currentPM")), pm_par_pa(inc.get("doc") or {}))
			acteur["currentPM"] = _eff_int(acteur.get("currentPM")) - penalite
			combat_doc.setdefault("log", []).append(_avec_etat({
				"tour": int(combat_doc.get("tour", 0) or 0),
				"acteur": acteur.get("nom", "?"),
				"kind": "sys",
				"texte": f"{acteur.get('nom', '?')} vacille mais tient son incantation "
						 f"(−{penalite} PM).",
			}, acteur))
		elif issue in ("echec", "fumble"):
			_rompre_incantation(combat_doc, acteur,
								f"{acteur.get('nom', '?')} perd le fil de son incantation !")
			if issue == "fumble":
				_appliquer_fumble(combat_doc, acteur)

	# 2. Chacun des sorts maintenus.
	for entree in list(_concentrations(acteur)):
		issue, _ = _issue()
		if issue == "critique":
			continue
		if issue == "reussite":
			# Tenir sous le coup coûte une fois l'entretien — au tarif de la CHARGE, comme
			# le prélèvement de début de tour : les deux sont le même geste (payer pour ne
			# pas lâcher), et les facturer différemment serait incompréhensible.
			penalite = min(_eff_int(acteur.get("currentPM")), _maintien_du(acteur, entree))
			acteur["currentPM"] = _eff_int(acteur.get("currentPM")) - penalite
			continue
		_rompre_concentration(
			combat_doc, acteur, entree,
			f"{entree.get('icon', '✨')} {entree.get('nom', 'Le sort')} se rompt sous le coup "
			f"({acteur.get('nom', '?')}).")
		if issue == "fumble":
			_appliquer_fumble(combat_doc, acteur)


def _traiter_ko(combat_doc: dict, defenseur: dict, attaquant: dict) -> None:
	"""Un corps vient de tomber à 0 PV : marqueurs, ligne de journal, défaite ou victoire.

	Extrait de `_do_attack_on`, qui ne pouvait abattre qu'UN acteur par coup. Le LIEN DE
	VIE en fait tomber potentiellement DEUX — le protégé et son protecteur — et les deux
	doivent suivre exactement la même cascade.

	⚠️ `est_joueur` est RECALCULÉ ici depuis la victime, jamais hérité du défenseur : un
	protecteur du camp du joueur passerait sinon par la branche « proie », qui le
	déclarerait mort-depçable et lui retirerait son XP.
	⚠️ Les marqueurs (`morte`, `dissipe`) sont posés AVANT la ligne, qui photographie
	l'état de la victime (`_avec_etat`) : après, `morte: False` serait figé dans le journal
	et la cargaison d'une monture ne se déverserait jamais à l'écran.
	"""
	est_joueur = str(defenseur.get("id", "")).startswith("joueur_")
	if est_joueur:
		# KO d'un membre du groupe : le combat continue tant qu'il reste un
		# joueur debout — la défaite n'arrive que TOUS à terre.
		est_monture = defenseur.get("est_monture")
		est_protege = defenseur.get("est_protege")
		# La cargaison vit sur le DOC de la monture, pas sur son snapshot : on se
		# contente de la marquer ici, `finalize_combat` déversera son sac AU SOL (là
		# où le doc est chargé, et sauvé) — la ligne ci-dessous le dit déjà, il aura
		# fallu le mécanisme du sol pour qu'elle cesse de mentir. Une personne ESCORTÉE
		# porte le même marqueur `morte` — c'est `_finalize_protege` qui en tirera la
		# mort et l'échec de la quête, au même endroit et pour la même raison.
		# ⚠️ Marqué AVANT la ligne, qui porte l'état du défenseur (`morte`).
		if est_monture or est_protege:
			defenseur["morte"] = True
		if defenseur.get("est_invocation"):
			# Une créature invoquée n'est pas « à terre » : elle cesse d'être là.
			# ⚠️ Marquée `dissipe` ICI, sinon elle traînerait à 0 PV jusqu'à son
			# propre tour — que `_resolve_until_player` saute justement parce
			# qu'elle est à 0 PV. Personne ne la retirerait jamais du combat.
			defenseur["dissipe"] = True
			texte_ko = f"{defenseur['nom']} est mis en pièces et se dissipe en fumée."
		elif est_monture:
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
		# Un porteur d'aura à terre n'émet plus ; un allié à terre ne reçoit plus.
		_recalculer_auras(combat_doc)
		# ⚠️ `_combattants_vivants` et non la liste brute : une monture debout ne
		# doit pas empêcher la défaite d'être déclarée (plus personne ne joue).
		# ⚠️ Garde `status` : depuis le lien de vie, un même coup peut faire tomber DEUX
		# corps, donc appeler cette cascade deux fois. Sans elle, la seconde réécrirait
		# « Tout le groupe est à terre… Défaite. » une deuxième fois dans le journal.
		if not _combattants_vivants(combat_doc) and combat_doc["status"] == "active":
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


def _do_attack_on(combat_doc: dict, attaquant: dict, defenseur: dict,
				   profil: dict | None = None) -> None:
	"""Attaque physique d'un monstre sur un défenseur — le joueur (cas normal) OU un
	autre monstre (chasse prédateur/proie pendant la furtivité du joueur). L'`esquive`
	du défenseur gonfle sa difficulté défensive (l'Ag), jamais sur la magie.

	`profil` (cf. `_profil_arme_monstre`) : mode/toucher/dégâts de l'ATTAQUE — mêlée
	mains nues par défaut (repli si absent, combat déjà en base : aucune migration),
	sinon celui de l'arme tirée d'un humanoïde armé (cac/jet/tir), même idiome que
	`_frapper_monstre` côté joueur-attaque-monstre.

	Décompte l'action de l'attaquant lui-même : un échec critique en coûte une SECONDE
	(ou l'endette pour le tour suivant), ce qui exige que le budget soit déjà à jour."""
	profil = profil or {"mode": "cac", "toucher": "cc", "degats": "degats_cc",
						 "portee": attaquant.get("portee", 1)}
	skill = attaquant.get("cd" if profil.get("toucher") == "cd" else "cc", 0)
	notation = attaquant.get(profil.get("degats", "degats_cc")) or attaquant.get("degats_cc", "1D4")
	est_joueur = str(defenseur.get("id", "")).startswith("joueur_")
	seuil = _hit_threshold(skill, _defense_physique(defenseur))
	jet = _resoudre_jet(attaquant, defenseur, seuil)
	roll = jet["roll"]
	attaquant["attaques"] = attaquant.get("attaques", 0) + 1
	_refresh_actions(attaquant)
	if jet["touche"]:
		# Formule partagée avec le joueur, les sorts, les compétences et le simulateur.
		# La zone frappée décide des PA opposés (pièce couvrante + protections globales).
		zone = tirer_localisation()
		ou = f" {ZONE_LIBELLE[zone]}" if zone in ZONE_LIBELLE else ""
		dmg = calculer_degats(attaquant, defenseur, notation,
							  jet["mult_degats"], profil.get("toucher", "cc"), zone=zone)
		# LIEN DE VIE : une partie du coup peut être absorbée puis reportée sur un
		# protecteur. ⚠️ Les DEUX déductions de PV avant le moindre `_traiter_ko` : la
		# première cascade interroge `_combattants_vivants`, qui répondrait sur un état
		# incomplet si le protecteur n'avait pas encore encaissé sa part.
		dmg_def, dmg_prot, protecteur = _rediriger_lien_vie(combat_doc, defenseur, dmg)
		defenseur["currentPV"] = max(0, defenseur["currentPV"] - dmg_def)
		if protecteur is not None:
			protecteur["currentPV"] = max(0, protecteur["currentPV"] - dmg_prot)
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
		# Canal "monstre" TOUJOURS, quel que soit le mode : c'est le défaut réservé aux
		# attaques de monstre (distinct des canaux cac/tir/jet du joueur), seule
		# l'animation SOURCE change — celle de l'arme d'abord, l'espèce à défaut.
		}, "monstre", defenseur.get("id", ""),
			profil.get("animation") or attaquant.get("animation"), attaquant.get("id", "")),
			attaquant, defenseur))
		if protecteur is not None:
			# ⚠️ Ligne SÉPARÉE, et non un troisième acteur gelé sur la ligne ci-dessus :
			# `_gelerActeurs` (client) ne rembobine que les acteurs qu'une entrée NOMME, et
			# `_avec_vfx` ne porte qu'UNE cible. Sans sa propre ligne, la barre du protecteur
			# chuterait dès l'arrivée de la réponse, avant que le coup ne s'anime — le défaut
			# même que toute la révélation différée existe pour empêcher.
			combat_doc["log"].append(_avec_etat(_avec_vfx({
				"tour": combat_doc["tour"],
				"acteur": protecteur["nom"],
				"kind": "hit",
				"texte": f"Le lien de vie détourne {dmg_prot} dégâts vers "
						 f"{protecteur['nom']} ! "
						 f"(PV : {protecteur['currentPV']}/{protecteur['pv_max']})",
			}, "monstre", protecteur.get("id", "")), protecteur))
		# CONCENTRATION : chaque corps qui a réellement perdu des PV risque ce qu'il tenait.
		# ⚠️ Avant les cascades de KO : un mort n'a plus rien à concentrer, et la ligne se
		# lirait absurdement après son « est à terre ».
		if dmg_def > 0:
			_tester_concentration(combat_doc, defenseur, attaquant, dmg_def)
		if protecteur is not None and dmg_prot > 0:
			_tester_concentration(combat_doc, protecteur, attaquant, dmg_prot)
		if defenseur["currentPV"] <= 0:
			_traiter_ko(combat_doc, defenseur, attaquant)
		if protecteur is not None and protecteur["currentPV"] <= 0:
			# Le protecteur peut tomber sous le coup qu'il absorbe — même cascade, et le
			# même `attaquant` en est la cause, même s'il ne l'a jamais visé.
			_traiter_ko(combat_doc, protecteur, attaquant)
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


def _do_monster_attack(combat_doc: dict, monstre: dict, joueur: dict,
						profil: dict | None = None) -> None:
	_do_attack_on(combat_doc, monstre, joueur, profil)


def _predicats_jeton(grid: dict, acteur: dict) -> tuple:
	"""(praticable, nav_ok) injectés dans `utils/jetons.py` — mêmes règles que `_find_path`."""
	cells, dims, nav = grid["cells"], grid["dims"], grid.get("nav", {})
	flying = _can_fly(acteur)
	return ((lambda x, y: 0 <= x < dims["x"] and 0 <= y < dims["y"] and _walkable(cells, x, y, flying)),
			(lambda x, y, dx, dy: nav_allows(nav, x, y, dx, dy)))


def _pas_budget_ok(acteur: dict) -> bool:
	"""Reste-t-il assez d'AP pour UN pas de plus (coût proportionnel) ?"""
	projected = (acteur["attaques"] + acteur.get("penalites", 0)
				 + _move_ap_used_for(acteur, acteur["cells_moved"] + 1))
	return projected <= acteur["actions_max"]


def _grand_pas_vers(combat_doc: dict, acteur: dict, cible: dict, grid: dict, blocked: set) -> bool:
	"""Un pas d'un GRAND jeton vers `cible` : A* sur les états (ancre, cap) jusqu'à ce que son
	emprise soit à portée, puis le premier pas — pivot compris (utils/jetons.py)."""
	portee = max(1, int(acteur.get("portee", 1) or 1))
	praticable, nav_ok = _predicats_jeton(grid, acteur)
	chemin = jetons.chemin_jeton(
		acteur,
		but=lambda vue: jetons.distance(vue, cible) <= portee,
		heuristique=lambda vue: max(0, jetons.distance(vue, cible) - portee),
		bloque=blocked, praticable=praticable, nav_ok=nav_ok,
	)
	if not chemin or len(chemin) < 2 or not _pas_budget_ok(acteur):
		return False
	x, y, cap = chemin[1]
	acteur["pos"] = {"x": x, "y": y}
	acteur["cap"] = cap
	acteur["cells_moved"] += 1
	_refresh_actions(acteur)
	return True


def _monster_step_toward(combat_doc: dict, monstre: dict, joueur: dict, grid: dict) -> bool:
	"""Avance le monstre d'une case vers le joueur via A*. Retourne True si déplacé."""
	blocked = _occupied_set(combat_doc, exclude=monstre)
	if jetons.est_grand(monstre):
		return _grand_pas_vers(combat_doc, monstre, joueur, grid, blocked)
	mx, my = monstre["pos"]["x"], monstre["pos"]["y"]
	# Cible à grand jeton : on vise la case de son emprise la plus proche (la sienne pour un 1x1).
	but = jetons.case_proche(joueur, mx, my)
	path = _find_path(
		grid["cells"], grid["dims"],
		(mx, my),
		but,
		blocked,
		grid.get("nav", {}),
		flying=_can_fly(monstre),
	)
	if not path or len(path) < 2:
		return False
	nxt = path[1]
	# Ne pas entrer sur la case du joueur (cible) ni une case occupée.
	if jetons.couvre(joueur, nxt[0], nxt[1]) or nxt in blocked:
		return False
	# Vérifier qu'il reste assez d'AP pour ce pas (coût proportionnel).
	if not _pas_budget_ok(monstre):
		return False
	if monstre.get("jeton"):   # 1x1 à forme : le dessin s'oriente dans le sens de la marche
		monstre["cap"] = jetons.cap_vers(monstre, {"pos": {"x": nxt[0], "y": nxt[1]}})
	monstre["pos"] = {"x": nxt[0], "y": nxt[1]}
	monstre["cells_moved"] += 1
	_refresh_actions(monstre)
	return True


def _monster_step_away(combat_doc: dict, monstre: dict, cible: dict, grid: dict,
						portee: int) -> bool:
	"""Un pas de RECUL loin de `cible` (kiting d'un monstre armé à distance trop
	approché) : pas de nouveau pathfinder, extension minimale des step-functions
	existantes. Retourne True si déplacé.

	Monstre 1x1 : scan glouton des 8 voisins (mêmes filtres que `_wander_step` —
	nav bitmask, terrain, cases occupées), choisit celui qui MAXIMISE la distance à
	`cible` ; aucun candidat ne l'améliore ⇒ pas de pas (même idiome de repli que les
	autres step-functions). Grand jeton : réutilise `jetons.chemin_jeton` (déjà l'A*
	générique de `_grand_pas_vers`) avec un but INVERSÉ : s'éloigner jusqu'à `portee`
	(heuristique admissible, même raisonnement que `_grand_pas_vers`)."""
	blocked = _occupied_set(combat_doc, exclude=monstre)
	if jetons.est_grand(monstre):
		praticable, nav_ok = _predicats_jeton(grid, monstre)
		chemin = jetons.chemin_jeton(
			monstre,
			but=lambda vue: jetons.distance(vue, cible) >= portee,
			heuristique=lambda vue: max(0, portee - jetons.distance(vue, cible)),
			bloque=blocked, praticable=praticable, nav_ok=nav_ok,
		)
		if not chemin or len(chemin) < 2 or not _pas_budget_ok(monstre):
			return False
		x, y, cap = chemin[1]
		monstre["pos"] = {"x": x, "y": y}
		monstre["cap"] = cap
		monstre["cells_moved"] += 1
		_refresh_actions(monstre)
		return True
	x, y = monstre["pos"]["x"], monstre["pos"]["y"]
	cells, dims, nav = grid["cells"], grid["dims"], grid.get("nav", {})
	flying = _can_fly(monstre)
	dist_actuelle = jetons.distance(monstre, cible)
	best = None
	best_dist = dist_actuelle
	for dx, dy in MOVE_OFFSETS:
		nx, ny = x + dx, y + dy
		if not (0 <= nx < dims["x"] and 0 <= ny < dims["y"]):
			continue
		if (nx, ny) in blocked or not nav_allows(nav, x, y, dx, dy):
			continue
		if not _walkable(cells, nx, ny, flying):
			continue
		d = jetons.distance({"pos": {"x": nx, "y": ny}}, cible)
		if d > best_dist:
			best_dist = d
			best = (nx, ny)
	if best is None or not _pas_budget_ok(monstre):
		return False
	if monstre.get("jeton"):   # même parti pris que `_monster_step_toward` : le dessin s'oriente
		monstre["cap"] = jetons.cap_vers(monstre, {"pos": {"x": best[0], "y": best[1]}})
	monstre["pos"] = {"x": best[0], "y": best[1]}
	monstre["cells_moved"] += 1
	_refresh_actions(monstre)
	return True


def _deplacement_ia(combat_doc: dict, monstre: dict, cible: dict, grid: dict,
					 profil: dict) -> tuple:
	"""Déplacement d'IA d'un monstre (ou d'une invocation) vers/loin de `cible`, selon
	son profil d'attaque actif (`_profil_arme_monstre`) : se rapproche si hors de
	portée, s'écarte si trop près et armé à distance, ne bouge pas s'il est déjà à
	portée idéale. Renvoie `(steps, verbe)` — `verbe` distingue le texte de log entre
	un monstre qui avance et un monstre qui recule prudemment."""
	portee = max(1, int(profil.get("portee", monstre.get("portee", 1))))
	ranged = bool(profil.get("ranged"))
	steps = 0
	safety = 0
	if ranged and _cheby(monstre, cible) < portee:
		while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
			   and _cheby(monstre, cible) < portee
			   and monstre["cells_moved"] < monstre.get("deplacement", 1)
			   and safety < 100):
			safety += 1
			if not _monster_step_away(combat_doc, monstre, cible, grid, portee):
				break
			steps += 1
		return steps, "recule prudemment devant"
	while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
		   and _cheby(monstre, cible) > portee
		   and monstre["cells_moved"] < monstre.get("deplacement", 1)
		   and safety < 100):
		safety += 1
		if not _monster_step_toward(combat_doc, monstre, cible, grid):
			break
		steps += 1
	return steps, "avance vers"


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
	if jetons.est_grand(monstre):
		# Grand jeton : les pas qui tiennent (pivot compris), tirés au hasard.
		praticable, nav_ok = _predicats_jeton(grid, monstre)
		etats = [e for e in (jetons.pas_jeton(monstre, dx, dy, blocked, praticable, nav_ok)
							 for dx, dy in MOVE_OFFSETS) if e]
		if not etats or not _pas_budget_ok(monstre):
			return False
		pos, cap = random.choice(etats)
		monstre["pos"] = pos
		monstre["cap"] = cap
		monstre["cells_moved"] += 1
		_refresh_actions(monstre)
		return True
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
	if monstre.get("jeton"):   # 1x1 à forme : le dessin s'oriente dans le sens de la marche
		monstre["cap"] = jetons.cap_vers(monstre, {"pos": {"x": nx, "y": ny}})
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
		profil = _profil_arme_monstre(monstre)
		portee = max(1, int(profil.get("portee", monstre.get("portee", 1))))
		if proie["vivant"]:
			_deplacement_ia(combat_doc, monstre, proie, grid, profil)
		while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
			   and proie["vivant"] and _cheby(monstre, proie) <= portee):
			_do_attack_on(combat_doc, monstre, proie, profil)   # décompte l'action lui-même
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
	profil = _profil_arme_monstre(monstre)
	portee = max(1, int(profil.get("portee", monstre.get("portee", 1))))

	# Cible résolue en début de tour : le joueur vivant le plus proche. Aucun joueur
	# visible = tous furtifs non détectés → jet de détection sur le plus proche, puis
	# chasse/errance en cas d'échec (comportement furtivité inchangé).
	joueur = _cible_joueur(combat_doc, monstre)
	if joueur is None:
		furtifs = [j for j in _joueurs_vivants(combat_doc) if j.get("furtif")]
		cible_furtive = min(furtifs, key=lambda j: _cheby(monstre, j)) if furtifs else None
		if cible_furtive is None or not _tenter_detection(combat_doc, monstre, cible_furtive):
			_chasse_ou_erre(combat_doc, monstre, grid)
			_avancer_tour(combat_doc)
			return
		joueur = cible_furtive

	# Phase déplacement : se rapprocher du joueur, ou s'en écarter s'il est armé à
	# distance et déjà trop proche (`_deplacement_ia`, cf. `_profil_arme_monstre`).
	steps, verbe = _deplacement_ia(combat_doc, monstre, joueur, grid, profil)
	if steps > 0:
		# Le jeton ne saute plus à sa case d'arrivée dès la réponse : il y glisse quand
		# cette ligne est révélée, puis frappe. Le chemin case par case n'est pas rejoué
		# (un seul log `move` agrégé par tour) — c'est un glissement, pas une marche.
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": monstre["nom"],
			"kind": "move",
			"texte": f"{monstre['nom']} {verbe} {joueur['nom']} ({steps} case(s)).",
		}, monstre))

	# Phase attaque : frapper tant qu'à portée et qu'il reste des actions. Si la cible
	# tombe (KO) en cours de tour, le monstre se rabat sur le joueur visible suivant.
	while combat_doc["status"] == "active" and monstre["actions_restantes"] > 0:
		if joueur is None or joueur.get("currentPV", 0) <= 0:
			joueur = _cible_joueur(combat_doc, monstre)
		if joueur is None or _cheby(monstre, joueur) > portee:
			break
		_do_monster_attack(combat_doc, monstre, joueur, profil)   # décompte l'action lui-même

	_avancer_tour(combat_doc)


def _frapper_monstre(combat_doc: dict, attaquant: dict, monstre: dict, profil: dict) -> tuple:
	"""Résout UN coup d'un acteur du camp du joueur sur un monstre, selon un profil d'attaque :
	jet, localisation, dégâts, ligne de journal (kill/hit/miss) et effet d'arme. Renvoie
	`(result, jet)`.

	Partagé par l'action `attaquer` du joueur et le tour de la personne escortée qui se défend
	(`_run_defenseur_turn`) : même jet, même formule, même journal — aucun coup gratuit.
	⚠️ Le DÉCOMPTE reste à l'appelant (furtivité, `attaques`, fumble, victoire) : la personne
	escortée n'est jamais furtive, et l'ordre des lignes de journal du joueur ne doit pas bouger.
	Ni portée ni ligne de vue ne sont contrôlées ici."""
	skill = attaquant.get("cd" if profil.get("toucher") == "cd" else "cc", 0)
	notation = attaquant.get(profil.get("degats", "degats_cc")) or attaquant.get("degats_cc", "1D4")
	seuil = _hit_threshold(skill, _defense_physique(monstre))
	jet = _resoudre_jet(attaquant, monstre, seuil)
	roll = jet["roll"]
	if not jet["touche"]:
		combat_doc["log"].append(_avec_vfx({
			"tour": combat_doc["tour"],
			"acteur": attaquant["nom"],
			"kind": "fumble" if jet["fumble"] else "miss",
			"texte": (
				f"{attaquant['nom']} rate LAMENTABLEMENT son attaque sur {monstre['nom']} ! "
				f"(jet {roll} / seuil {seuil})"
				if jet["fumble"] else
				f"{attaquant['nom']} rate son attaque sur {monstre['nom']} ! (jet {roll} / seuil {seuil})"
			),
		}, "fumble" if jet["fumble"] else "miss", monstre.get("id", ""),
			acteur_id=attaquant.get("id", "")))
		return {"hit": False, "fumble": jet["fumble"], "roll": roll, "seuil": seuil}, jet

	zone = tirer_localisation()
	ou = f" {ZONE_LIBELLE[zone]}" if zone in ZONE_LIBELLE else ""
	dmg = calculer_degats(attaquant, monstre, notation, jet["mult_degats"],
						  profil.get("toucher", "cc"), zone=zone)
	monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
	# L'animation suit le MODE de l'arme (cac/jet/tir), avec celle de l'arme elle-même en
	# priorité : le profil la porte depuis le snapshot, aucun doc n'est relu ici.
	anim_arme = profil.get("animation")
	if monstre["currentPV"] <= 0:
		monstre["vivant"] = False
		texte = (f"{attaquant['nom']} porte un COUP CRITIQUE et élimine {monstre['nom']} !"
				 if jet["critique"] else
				 f"{attaquant['nom']} élimine {monstre['nom']} !")
		kind = "kill"
	else:
		texte = (
			f"{attaquant['nom']} porte un COUP CRITIQUE à {monstre['nom']}{ou} : {dmg} dégâts ! "
			f"(jet {roll} — PV : {monstre['currentPV']}/{monstre['pv_max']})"
			if jet["critique"] else
			f"{attaquant['nom']} touche {monstre['nom']}{ou} pour {dmg} dégâts ! "
			f"(PV : {monstre['currentPV']}/{monstre['pv_max']})"
		)
		kind = "crit" if jet["critique"] else "hit"
	combat_doc["log"].append(_avec_etat(_avec_vfx({
		"tour": combat_doc["tour"],
		"acteur": attaquant["nom"],
		"kind": kind,
		"texte": texte,
	}, profil.get("mode", "cac"), monstre.get("id", ""), anim_arme, attaquant.get("id", "")),
		monstre))
	# Après la mise à jour de `vivant` : le chokepoint refuse une cible morte.
	effet_arme = _appliquer_effet_arme(combat_doc, attaquant, monstre, profil)
	result = {"hit": True, "dmg": dmg, "critique": jet["critique"],
			  "cible": monstre["nom"], "cible_pv": monstre["currentPV"]}
	if effet_arme:
		result["effet_arme"] = {"nom": effet_arme.get("nom"),
								"restants": effet_arme.get("restants")}
	return result, jet


def _run_defenseur_turn(combat_doc: dict, joueur: dict) -> None:
	"""Tour d'une personne escortée qui SAIT SE DÉFENDRE (`se_defend`) — joué par le serveur,
	comme celui d'un monstre, et ne rend donc jamais la main au client.

	Elle ne fait JAMAIS un pas : la couvrir reste l'affaire du joueur. Elle frappe, à l'allonge
	de son arme de mêlée, l'ennemi au contact le plus entamé (le premier en cas d'égalité),
	tant qu'il lui reste des actions. Personne à portée ⇒ elle passe, sans ligne de journal
	(sinon une ligne par tour pour ne rien dire).

	Budget, jet, fumble et victoire sont ceux du joueur (`_frapper_monstre`) : aucun coup
	gratuit. ⚠️ Elle reste `jouable: False` — sa survie n'empêche pas la défaite
	(`_combattants_vivants`) : elle ne bouge pas, un groupe à terre ne gagnerait jamais."""
	_reset_turn_budget(joueur, combat_doc)
	profil = _profil_attaque(joueur, "cac")
	portee = max(1, int(profil.get("portee", 1)))
	safety = 0
	while (combat_doc["status"] == "active" and joueur.get("currentPV", 0) > 0
		   and joueur["actions_restantes"] > 0 and safety < 100):
		safety += 1
		cibles = [m for m in combat_doc["monstres"]
				  if m["vivant"] and _cheby(joueur, m) <= portee]
		if not cibles:
			break
		monstre = min(cibles, key=lambda m: m["currentPV"])
		_, jet = _frapper_monstre(combat_doc, joueur, monstre, profil)
		joueur["attaques"] = joueur.get("attaques", 0) + 1
		_refresh_actions(joueur)
		# Après le décompte de l'attaque : un fumble coûte une action de PLUS.
		if jet["fumble"]:
			_appliquer_fumble(combat_doc, joueur)
		_check_victory(combat_doc)

	_avancer_tour(combat_doc)


def _run_invocation_turn(combat_doc: dict, invoc: dict, grid: dict) -> None:
	"""Tour d'une créature INVOQUÉE — joué par le serveur, comme celui d'un monstre : elle
	fonce sur l'ennemi vivant le plus proche (A*, mêmes règles de terrain et de `nav`) puis
	frappe tant qu'il lui reste des actions.

	Miroir exact de `_run_monster_turn`, camp inversé et sans furtivité (une créature
	appelée à grand bruit ne surprend personne, et aucun monstre ne se cache d'elle). Budget,
	jet, fumble et victoire passent par les chokepoints du joueur (`_frapper_monstre`) :
	aucun coup gratuit.

	DURÉE : décomptée à la FIN de son tour, de sorte qu'une créature appelée pour `duree`
	tours agisse exactement `duree` fois — celui de son apparition compris."""
	_reset_turn_budget(invoc, combat_doc)
	# `_profil_arme_monstre` : une invocation HUMANOÏDE garde son arme (cf.
	# `build_invocation_snapshot`), les autres retombent sur le `cac` mains nues posé
	# à sa création — même sélecteur que `_run_monster_turn`, camp inversé.
	profil = _profil_arme_monstre(invoc)
	portee = max(1, int(profil.get("portee", 1)))

	cibles = [m for m in combat_doc["monstres"] if m["vivant"]]
	cible = min(cibles, key=lambda m: _cheby(invoc, m)) if cibles else None

	steps, verbe = (0, "bondit vers")
	if cible is not None:
		steps, verbe = _deplacement_ia(combat_doc, invoc, cible, grid, profil)
		if verbe == "avance vers":
			verbe = "bondit vers"   # même flair qu'avant pour l'approche
	if steps > 0:
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": invoc["nom"],
			"kind": "move",
			"texte": f"{invoc['nom']} {verbe} {cible['nom']} ({steps} case(s)).",
		}, invoc))

	safety = 0
	while (combat_doc["status"] == "active" and invoc["actions_restantes"] > 0 and safety < 100):
		safety += 1
		if cible is None or not cible["vivant"]:
			vivants = [m for m in combat_doc["monstres"] if m["vivant"]]
			cible = min(vivants, key=lambda m: _cheby(invoc, m)) if vivants else None
		if cible is None or _cheby(invoc, cible) > portee:
			break
		_, jet = _frapper_monstre(combat_doc, invoc, cible, profil)
		invoc["attaques"] = invoc.get("attaques", 0) + 1
		_refresh_actions(invoc)
		if jet["fumble"]:
			_appliquer_fumble(combat_doc, invoc)
		_check_victory(combat_doc)

	# ⚠️ Une créature TENUE par un sort maintenu ne compte plus ses tours : c'est l'entretien
	# en PM qui la garde là (cf. `_payer_maintiens`), et c'est le défaut de paiement qui la
	# renvoie. Continuer le compte à rebours la ferait disparaître alors que son invocateur
	# paie toujours — deux horloges pour une seule créature, dont la plus courte gagnerait.
	if not invoc.get("sort_maintenu"):
		invoc["invocation_restants"] = int(invoc.get("invocation_restants", 1)) - 1
		if invoc["invocation_restants"] <= 0:
			_dissiper_invocation(combat_doc, invoc,
								 f"{invoc['nom']} retourne d'où il vient — l'appel est épuisé.")

	_avancer_tour(combat_doc)


def _resolve_until_player(combat_doc: dict, grid: dict, start_at_current: bool = False) -> None:
	"""Run monster turns until it's a player's turn.

	start_at_current=True  : process the actor at acteur_courant_index first (combat init).
	start_at_current=False : advance past the current actor first (after player action).

	Les personnes escortées qui se défendent et les créatures INVOQUÉES (`joueur_*` à
	`jouable: False`) sont jouées ICI, comme des monstres : la main ne s'arrête jamais sur
	elles. C'est aussi ici que les invocations expirées quittent le combat.
	"""
	ordre = combat_doc["ordre_initiative"]
	# Garde-fou de boucle. Une itération est consommée par : un tour de monstre, de défenseur
	# ou d'invocation, un joueur à terre ou un monstre mort qu'on saute — et désormais un
	# tour de CANALISATION, sauté parce que l'incantation a mangé tout le budget. Ce dernier
	# poste dépend du CONTENU (un sort peut demander jusqu'à INCANTATION_PA_MAX PA, soit
	# autant de tours sautés pour un lanceur), d'où la marge explicite : sans elle, un groupe
	# de mages sur un sort très long épuiserait le compteur et sortirait, en silence, sur un
	# combat figé.
	max_iter = len(ordre) * (20 + INCANTATION_PA_MAX)

	if not start_at_current:
		# Move past current actor before entering the loop
		_avancer_tour(combat_doc)

	for _ in range(max_iter):
		if combat_doc["status"] != "active":
			break
		# Invocations dissipées ou abattues : elles quittent le combat ICI, seul endroit qui
		# puisse remettre `acteur_courant_index` d'aplomb après un retrait. ⚠️ `ordre` est
		# relu juste après — la purge remplace la liste, elle ne la mute pas en place.
		_purger_invocations(combat_doc)
		ordre = combat_doc["ordre_initiative"]
		if not ordre:
			break
		if combat_doc["acteur_courant_index"] >= len(ordre):
			combat_doc["acteur_courant_index"] = 0
		actor_id = ordre[combat_doc["acteur_courant_index"]]
		if actor_id.startswith("joueur_"):
			joueur = _get_joueur(combat_doc, actor_id)
			if joueur and joueur.get("currentPV", 0) > 0:
				# ⚠️ `is False` STRICTEMENT : un joueur ordinaire ne porte pas la clé.
				if joueur.get("est_invocation"):
					_run_invocation_turn(combat_doc, joueur, grid)
					continue
				if joueur.get("jouable") is False:
					_run_defenseur_turn(combat_doc, joueur)
					continue
				# ⚠️ C'est `_reset_turn_budget` qui prélève l'entretien des sorts maintenus
				# ET fait avancer une incantation longue : le budget qu'il rend peut donc
				# être déjà entièrement mangé quand il revient.
				_reset_turn_budget(joueur, combat_doc)
				if joueur["actions_restantes"] <= 0:
					# CANALISATION : la main ne va PAS au client. Il n'aurait aucune action
					# à jouer et `resolve_action` lui refuserait tout, `passer` compris —
					# le joueur resterait devant une interface morte.
					# ⚠️ On teste le BUDGET, jamais un drapeau « canalise » : un lanceur dont
					# l'entretien vient d'échouer (plus de PM, incantation rompue) a retrouvé
					# son budget et doit rejouer normalement. Un drapeau le sauterait à vie.
					# ⚠️ `_avancer_tour` AVANT `continue` : sans lui on tourne sur le même
					# index, `max_iter` s'épuise en silence et le combat ressort avec la main
					# plantée sur le lanceur — tous les boutons éteints, partie bloquée.
					_avancer_tour(combat_doc)
					continue
				break
			# Joueur KO (à terre) : son tour est sauté, comme un monstre mort.
			_avancer_tour(combat_doc)
			continue
		monstre = _get_monstre(combat_doc, actor_id)
		if not monstre or not monstre["vivant"]:
			# Dead monster — skip
			_avancer_tour(combat_doc)
			continue
		_run_monster_turn(combat_doc, monstre, grid)


def _advance_and_resolve(combat_doc: dict, grid: dict) -> None:
	"""After a player action: advance past the player and resolve all monster turns."""
	_resolve_until_player(combat_doc, grid, start_at_current=False)


def resolve_first_turns(combat_doc: dict) -> None:
	"""Called after combat creation: if monsters go first, resolve their turns."""
	_resolve_until_player(combat_doc, get_combat_grid(combat_doc), start_at_current=True)


# ── API publique ────────────────────────────────────────────────────────────

def _lancer_capacite(combat_doc: dict, joueur: dict, sdoc: dict, effets: dict,
					 cible_id: str | None, dx, dy, grid: dict, kind: str = "sort") -> tuple:
	"""Résout une CAPACITÉ qui PART — sort ou compétence : les quatre familles de
	lancement, et rien d'autre.

	CHOKEPOINT PARTAGÉ par les QUATRE chemins qui font partir une capacité : le lancement
	direct d'un sort, celui d'une compétence, et la fin d'une INCANTATION LONGUE de l'un ou
	de l'autre, qui se résout des tours plus tard depuis `_avancer_incantation`. Tous
	doivent aboutir au même état : des copies divergeraient au premier effet ajouté — c'est
	exactement ce qui était arrivé aux gardes d'éligibilité.

	`kind` ne sert qu'à choisir le PROFIL (cf. `PROFIL_SORT` / `PROFIL_COMPETENCE`) : les
	dés et l'allonge empruntés à l'arme, les textes de journal et la clé de résultat. Toute
	la mécanique — saut, lien de vie, zones, furtivité, entretien — est commune.

	⚠️ Ne touche NI le compteur d'actions, NI la charge (composants), NI le fumble, NI la
	victoire : tout cela appartient au LANCEMENT et se paie une seule fois, alors qu'une
	incantation longue traverse plusieurs tours. L'appelant s'en charge.
	⚠️ Les PM de lancement sont débités ICI pour un sort instantané ; une incantation
	longue les a déjà versés par tranches (`pm_verses`) et passe `cout_pm` à 0.

	Rend `(resultat, jet)` — `jet` renseigné par la seule branche offensive.
	"""
	profil = _profil_de(kind)
	cle = profil["cle"]
	nom_capacite = sdoc.get("nom", profil["nom_defaut"])
	# PM sous la CHARGE du lanceur (utils/charge_magie) : un porteur bardé canalise moins
	# bien. Même fonction que la garde de `resolve_action`, sinon un sort serait proposé
	# à un prix et débité à un autre. ⚠️ Une incantation longue arrive ici avec `cout_pm`
	# déjà à 0 (ses PM sont partis par tranches) : la pénalité ne s'applique pas deux fois.
	cout_pm = _cout_pm_charge(joueur, sdoc)
	# Une compétence ne porte jamais de bloc `invocation` (`normaliser_competence` ne le
	# lit pas) : le `.get` suffit, aucune garde par type n'est nécessaire.
	invocation = sdoc.get("invocation") or None
	jet = None   # renseigné seulement par la branche offensive (jet de toucher)
	# ⚠️ Le SAUT se valide AVANT le moindre débit : sa destination est désignée par le
	# joueur, donc refusable, et la règle du moteur est constante — un sort qui ne part pas
	# ne se paie pas. La branche qui l'exécute revalidera, c'est le même chokepoint.
	if effets.get("saut"):
		sauteur = (_get_joueur(combat_doc, cible_id) if sdoc.get("cible") == "allie"
				   else joueur)
		if sauteur is not None:
			erreur = _verifier_saut(combat_doc, sauteur, effets, dx, dy, grid)
			if erreur:
				return erreur, None
	if invocation:
		# INVOCATION : le sort ne vise personne, il ajoute des combattants. Testée AVANT
		# `cible`, qui ne décrit pas ce qu'elle fait (une invocation est `soi` par défaut,
		# mais elle ne se pose rien sur soi).
		# ⚠️ Aucune case libre autour du lanceur ⇒ le sort NE PART PAS : ni PM, ni action.
		# Le contraire ferait payer plein tarif une incantation dont il ne sort rien, et
		# c'est le seul échec ici qui ne doit rien à un jet de dés.
		# ⚠️ EXCLUSIF des trois autres branches : un sort qui invoque n'applique aucun de
		# ses `effets`. Ce qu'il produit est la créature, pas un buff — et lui laisser les
		# deux ferait d'une invocation le meilleur sort de soi du jeu, pour le même coût.
		crees = invoquer(combat_doc, joueur, sdoc, grid)
		if not crees:
			return {"error": "Aucune place autour de vous pour faire apparaître la créature."}, None
		joueur["currentPM"] -= cout_pm
		noms = ", ".join(c["nom"] for c in crees)
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "sys",
			"texte": f"{joueur['nom']} {profil['verbe']} {nom_capacite} : {noms} "
					 f"répond à l'appel ({crees[0]['invocation_restants']} tour(s)).",
		}, joueur))
		result = {cle: nom_capacite,
				  "invoques": [{"id": c["id"], "nom": c["nom"],
								"restants": c["invocation_restants"]} for c in crees]}
	elif sdoc.get("cible") == "allie":
		# Sort d'entraide : compagnon OU monture, désigné par son id de snapshot.
		# Aucun jet, aucun compteur d'attaque — seulement l'action et les PM.
		allie = _get_joueur(combat_doc, cible_id) if cible_id else None
		res_allie = _lancer_sur_allie(combat_doc, joueur, allie, sdoc, effets,
									  _portee_capacite(joueur, sdoc, profil)[0], grid)
		if "error" in res_allie:
			return res_allie, None   # PM NON débités : la capacité n'est jamais partie
		joueur["currentPM"] -= cout_pm
		result = {cle: nom_capacite, **res_allie}
		# ZONE DE SOUTIEN : les alliés que la forme ajoute au désigné, lui déjà servi.
		# ⚠️ Les gardes de `_lancer_sur_allie` (portée, ligne de vue, « à terre ») ne
		# valent que pour le DÉSIGNÉ : c'est contre lui que le sort a été autorisé.
		autres = _servir_zone_soutien(combat_doc, joueur, allie, sdoc, effets,
									  sdoc.get("zone"), grid)
		if autres:
			result["beneficiaires"] = autres
		# LIEN DE VIE : le sort ne pose rien sur le désigné, il TISSE entre lui et le
		# lanceur. Posé après le soutien, pour que la zone serve d'abord normalement.
		_poser_lien_vie(combat_doc, joueur, allie, sdoc, effets)
		# SAUT sur un allié : la case d'arrivée est celle que le joueur a désignée.
		saut = _sauter(combat_doc, joueur, allie, effets, dx, dy, grid)
		if "error" in saut:
			return saut, None
		result.update(saut)
	elif sdoc.get("cible") == "ennemi":
		# Dégâts, dégâts de PM OU part à durée : un sort offensif peut n'être qu'un debuff
		# (« −10 Ag pendant 2 tours »), il lui suffit d'avoir quelque chose à faire.
		# ⚠️ Garde partagée avec la sous-branche `ennemi` des compétences
		# (`sorts.effets_agissent_sur_cible`) : une siphonie pure (`degats_pm` seul, sans
		# le moindre dégât de PV) doit passer des deux côtés. Elle est le cœur de la
		# famille anti-lanceur.
		if not effets_agissent_sur_cible(effets):
			return {"error": profil["sans_effet"]}, None
		monstre = _get_monstre(combat_doc, cible_id) if cible_id else None
		if not monstre or not monstre["vivant"]:
			return {"error": "Cible invalide."}, None
		# Portée EFFECTIVE : une compétence de contact emprunte l'ALLONGE de l'arme en
		# main, comme elle en emprunte les dés (chokepoint `_portee_capacite`).
		sort_portee, est_a_distance = _portee_capacite(joueur, sdoc, profil)
		# Règles à distance identiques au jet/tir : interdit si engagé au corps à corps,
		# et exige une ligne de vue. ⚠️ Piloté par le drapeau `ranged` et non par
		# `portee > 1` : une hallebarde frappe à 2 cases EN MÊLÉE.
		if est_a_distance:
			if any(m["vivant"] and _cheby(joueur, m) <= 1 for m in combat_doc["monstres"]):
				return {"error": profil["engage"]}, None
			if not _vue_acteurs(grid["cells"], joueur, monstre):
				return {"error": "Ligne de vue obstruée."}, None
		if _cheby(joueur, monstre) > sort_portee:
			return {"error": "Cible hors de portée."}, None

		# La capacité part : PM débités AVANT le jet (raté = PM quand même dépensés).
		joueur["currentPM"] -= cout_pm
		# Jet porté par la DONNÉE, exactement comme pour les compétences :
		# `magique` (défaut des sorts) se résout sous toucher_magique contre la
		# pm_def ; un sort de CONTACT marqué `cc`/`cd` (« au toucher ») exige
		# d'abord de poser la main — jet martial contre la défense physique.
		mode_jet = sdoc.get("jet") or ("cc" if cle == "competence" else "magique")
		# ZONE D'EFFET : la cible désignée d'abord, puis tout monstre pris dans la
		# forme (cf. utils/zones_effet.py). `zone` absente ⇒ liste d'un seul élément,
		# donc exactement le comportement d'avant.
		cibles_sort = cibles_de_zone(combat_doc, joueur, monstre, sdoc.get("zone"), grid)
		result, jet = _resoudre_capacite_offensive(
			combat_doc, joueur, cibles_sort, sdoc, effets,
			_notation_capacite(joueur, sdoc, effets, profil),
			mode_jet, cle, profil["textes"],
			{"nom": nom_capacite, "nom_fumble": nom_capacite})
		result[cle] = nom_capacite

		# Incanter au contact révèle le lanceur (touché ou raté) ; à distance, seule la
		# cible tente de le repérer — foudroyée sur place, elle n'en a même pas le temps.
		_furtivite_apres_offensive(combat_doc, joueur, monstre, est_a_distance)
	else:
		# Capacité sur soi : toujours lançable ; débit PM puis part instantanée clampée.
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
			"texte": f"{joueur['nom']} {profil['verbe']} {nom_capacite} ({gains}).",
		}, joueur))
		# Sort de dissimulation (effets.furtivite > 0) : pose l'état furtif et
		# remet la détection de tous les monstres à zéro.
		if int(effets.get("furtivite", 0) or 0) > 0:
			_activer_furtivite(combat_doc, joueur, int(effets["furtivite"]))
		result = {cle: nom_capacite, "pv_rendu": pv_rendu, "pm_rendu": pm_rendu,
				  "furtif": bool(joueur.get("furtif")),
				  "effets_actifs": [dict(e) for e in joueur.get("effets_actifs") or []]}
		# ZONE DE SOUTIEN autour de soi (cri de ralliement, nappe de soin) : le
		# lanceur vient d'être servi ci-dessus, la forme est ancrée sur lui et, faute
		# de cible désignée, orientée par son `facing`.
		autres = _servir_zone_soutien(combat_doc, joueur, joueur, sdoc, effets,
									  sdoc.get("zone"), grid)
		if autres:
			result["beneficiaires"] = autres
		# SAUT sur soi : le cas courant de la téléportation tactique.
		saut = _sauter(combat_doc, joueur, joueur, effets, dx, dy, grid)
		if "error" in saut:
			return saut, None
		result.update(saut)

	# ⚠️ ICI et pas plus haut : on n'entretient que ce qui est réellement parti. Toutes les
	# sorties en erreur ci-dessus ont déjà rendu la main, donc aucune concentration
	# fantôme ne survit à un sort refusé.
	entree = _enregistrer_concentration(combat_doc, joueur, sdoc, cible_id)
	if entree:
		result["concentrations"] = [dict(c) for c in _concentrations(joueur)]
	return result, jet


def _enregistrer_concentration(combat_doc: dict, joueur: dict, sdoc: dict,
							   cible_id: str | None) -> dict | None:
	"""Inscrit un sort MAINTENU dans les concentrations du lanceur — None s'il n'en est pas un.

	L'entrée est ce que `_payer_maintiens` prélèvera à chaque tour, et ce que
	`_rompre_concentration` défera. Elle rattache aussi les objets que le sort TIENT :
	  • les créatures qu'il vient d'appeler (marquées `sort_maintenu`), pour qu'elles se
		dissipent avec lui plutôt qu'à l'épuisement de leur propre compteur ;
	  • le lien de vie qu'il pose sur le protégé.
	"""
	if not est_maintenu(sdoc):
		return None
	sort_id = sdoc.get("id", "")
	entree = {
		"sort_id": sort_id,
		"nom": sdoc.get("nom", "un sort"),
		"icon": sdoc.get("icon", "🔮"),
		"maintien": max(0, int(sdoc.get("maintien", 0) or 0)),
		# Sensibilité du sort à la CHARGE, recopiée depuis le doc : `_payer_maintiens`
		# recalcule l'entretien à CHAQUE tour et n'a plus le doc sous la main. Sans elle,
		# l'entretien retomberait sur la sensibilité par défaut du monde au 2ᵉ round.
		"sensibilite_charge": sdoc.get("sensibilite_charge"),
		"cible_id": cible_id or "",
	}
	concentrations = [c for c in _concentrations(joueur)
					  if str(c.get("sort_id") or "") != sort_id]
	concentrations.append(entree)
	joueur["concentrations"] = concentrations

	# Chip de suivi sur le LANCEUR. ⚠️ Indispensable pour un sort maintenu OFFENSIF (Mur de
	# feu) ou un LIEN DE VIE : leur part durative vit sur la victime ou sur le protégé, donc
	# le lanceur n'a rien dans ses propres `effets_actifs` — il paierait chaque round pour
	# quelque chose d'invisible, sans même pouvoir le relâcher (la chip EST le bouton).
	if not any(str(e.get("source_id") or "") == sort_id
			   for e in joueur.get("effets_actifs") or []):
		poser_effet(joueur, {
			"source_id": sort_id, "nom": entree["nom"], "icon": entree["icon"],
			"buffs": {}, "regen_pv": 0, "regen_pm": 0, "esquive": 0,
			"restants": 1, "pose_tour": int(combat_doc.get("tour", 0) or 0),
			"maintenu": True, "maintien": entree["maintien"],
		})

	# Les créatures que CE sort vient d'appeler cessent de compter leurs tours : c'est
	# l'entretien qui les tient désormais (cf. `_run_invocation_turn`).
	for invoc in combat_doc.get("joueurs") or []:
		if (invoc.get("est_invocation") and not invoc.get("sort_maintenu")
				and invoc.get("invocateur_id") == joueur.get("id")
				and invoc.get("sort_id") == sort_id):
			invoc["sort_maintenu"] = sort_id
	return entree


def resolve_action(
	combat_doc: dict, action_type: str, cible_id: str | None = None,
	dx: int | None = None, dy: int | None = None, sens: int | None = None,
	mode: str | None = None, item: dict | None = None, sort: dict | None = None,
	competence: dict | None = None, attributions: list | None = None,
) -> dict:
	"""Résout une action du joueur (cf. `_resoudre_action_joueur`), puis remet les AURAS en
	accord avec les positions : un pas, un saut ou une invocation peut faire entrer ou
	sortir un allié de la zone d'un porteur. Une action refusée n'a rien bougé.
	`attributions` : répartition du butin d'étage (`emprunter`, donjon à étages)."""
	result = _resoudre_action_joueur(combat_doc, action_type, cible_id, dx, dy, sens, mode,
									 item, sort, competence, attributions)
	if not (result or {}).get("error"):
		_recalculer_auras(combat_doc)
	return result


def _resoudre_action_joueur(
	combat_doc: dict, action_type: str, cible_id: str | None = None,
	dx: int | None = None, dy: int | None = None, sens: int | None = None,
	mode: str | None = None, item: dict | None = None, sort: dict | None = None,
	competence: dict | None = None, attributions: list | None = None,
) -> dict:
	ordre = combat_doc["ordre_initiative"]
	actor_id = ordre[combat_doc["acteur_courant_index"]]

	if not actor_id.startswith("joueur_"):
		return {"error": "Ce n'est pas le tour du joueur."}

	joueur = _get_joueur(combat_doc, actor_id)
	if not joueur:
		return {"error": "Joueur introuvable."}
	if joueur.get("jouable") is False:
		# Garde défensive : une personne escortée qui se défend joue un tour SERVEUR
		# (`_run_defenseur_turn`) — la main ne s'arrête jamais sur elle, un doc en vol non plus.
		return {"error": "Ce n'est pas le tour du joueur."}
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
		# Case occupée par un acteur NON JOUABLE (monture, personne escortée) : il n'a ni tour
		# ni budget de déplacement, il enfermerait donc le joueur pour tout le combat. On
		# ÉCHANGE les deux places, au prix d'un pas ordinaire. La règle : chacun doit pouvoir
		# tenir sur la case de l'autre (la jambe ALLER est la garde de terrain ci-dessus).
		# ⚠️ Aucun second contrôle `nav` pour la direction retour : `get_final_mask` est
		# bidirectionnel (il vérifie la source ET la cible), l'appel ci-dessus la couvre déjà.
		# ⚠️ Une case couverte par un GRAND allié non jouable n'est pas « occupée » pour le
		# joueur : il la traverse (`_traversable_par`) — l'échange de places est impossible avec
		# une emprise de plusieurs cases, qui l'enfermerait pour tout le combat.
		echange = None
		if _occupied_at(combat_doc, nx, ny, traversant=joueur):
			echange = _allie_echangeable(combat_doc, nx, ny)
			if echange is None:
				return {"error": "Case occupée."}
			if not _echange_possible(cells, joueur, echange):
				return {"error": f"{echange['nom']} ne peut pas tenir sur votre case."}
			# L'échangé atterrit sur l'ancienne case du joueur : si celui-ci traversait un grand
			# allié, les deux bêtes se superposeraient.
			ox, oy = joueur["pos"]["x"], joueur["pos"]["y"]
			if any(p is not joueur and p is not echange and p.get("currentPV", 1) > 0
				   and jetons.couvre(p, ox, oy) for p in combat_doc["joueurs"]):
				return {"error": f"{echange['nom']} ne peut pas tenir sur votre case."}
		if joueur["cells_moved"] >= joueur.get("deplacement", 1):
			return {"error": "Budget de déplacement épuisé."}
		projected = (joueur["attaques"] + joueur.get("penalites", 0)
					 + _move_ap_used_for(joueur, joueur["cells_moved"] + 1))
		if projected > joueur["actions_max"]:
			return {"error": "Plus d'actions pour se déplacer."}

		# ⚠️ Dicts NEUFS des deux côtés : le journal copie l'état par acteur, une référence
		# partagée ferait dériver une ligne déjà écrite.
		ancienne = {"x": joueur["pos"]["x"], "y": joueur["pos"]["y"]}
		joueur["pos"] = {"x": nx, "y": ny}
		if echange is not None:
			echange["pos"] = ancienne
		joueur["cells_moved"] += 1
		_refresh_actions(joueur)
		combat_doc["log"].append(_avec_etat({
			"tour": combat_doc["tour"],
			"acteur": joueur["nom"],
			"kind": "move",
			"texte": (f"{joueur['nom']} échange sa place avec {echange['nom']}."
					  if echange is not None
					  else f"{joueur['nom']} se déplace en [{nx},{ny}]."),
		# ⚠️ L'échangé est passé LUI AUSSI : il vient de bouger. Absent de `etat`, son jeton
		# suivrait l'état final tout de suite pendant que celui du joueur attend la révélation
		# du journal — les deux corps ne glisseraient pas ensemble. (`None` est ignoré.)
		}, joueur, echange))
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

		# Profil d'attaque selon le mode demandé (arme), repli sur la mêlée (cac) —
		# sélecteur partagé avec _portee_competence, qui y lit l'allonge de l'arme.
		profil = _profil_attaque(joueur, mode)
		atk_portee = max(1, int(profil.get("portee", 1)))
		is_ranged = bool(profil.get("ranged"))

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
			if not _vue_acteurs(grid["cells"], joueur, monstre):
				return {"error": "Ligne de vue obstruée."}
		if _cheby(joueur, monstre) > atk_portee:
			return {"error": "Cible hors de portée."}

		result, jet = _frapper_monstre(combat_doc, joueur, monstre, profil)

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

	elif action_type == "interrompre":
		# Cesser d'entretenir un sort MAINTENU dont on ne veut plus payer le prix. GRATUIT —
		# relâcher un effort n'est pas un geste, et faire payer la sortie enfermerait un mage
		# dans son propre sort jusqu'à ce que ses PM s'épuisent.
		# ⚠️ Ne vise QUE les sorts maintenus, et c'est délibéré : une INCANTATION ne
		# s'abandonne pas. Elle absorbe tout le budget du tour (`_avancer_incantation`), donc
		# la main ne revient jamais au joueur tant qu'elle dure — commencer un Météore, c'est
		# s'y engager. Seuls un coup encaissé (test de concentration) ou le manque de PM
		# peuvent encore l'arrêter, et c'est précisément ce qui fait du mage un artilleur que
		# ses alliés doivent protéger.
		entree = next((c for c in _concentrations(joueur)
					   if str(c.get("sort_id") or "") == str(cible_id or "")), None)
		if not entree:
			return {"error": "Vous n'entretenez pas ce sort."}
		_rompre_concentration(
			combat_doc, joueur, entree,
			f"{joueur['nom']} cesse d'entretenir {entree.get('nom', 'son sort')}.")
		result = {"interrompu": True,
				  "concentrations": [dict(c) for c in _concentrations(joueur)],
				  "currentPM": joueur["currentPM"]}

	elif action_type == "fuir":
		if combat_doc.get("etages"):
			return {"error": "On ne fuit pas un donjon : trouvez un passage vers la surface."}
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

	elif action_type == "emprunter":
		# Donjon à étages : franchir une connexion. Aucune action n'est décomptée — la sortie
		# clôt le combat, et un changement d'étage (orchestré par le router, qui charge
		# l'étage suivant) repart d'un ordre d'initiative neuf.
		etages = combat_doc.get("etages")
		if not etages:
			return {"error": "Aucun passage à emprunter ici."}
		passage = next((p for p in etages.get("passages") or [] if p.get("id") == cible_id), None)
		if passage is None:
			return {"error": "Passage inconnu."}
		if not passage_franchissable(combat_doc, passage):
			return {"error": "Tout le groupe doit se tenir au passage, en file derrière celui qui l'occupe."}
		# Étage vidé qu'on quitte pour un AUTRE étage : son butin se répartit avant de partir
		# (la sortie vers la surface a déjà le sien, `butin_disponible` à la victoire).
		# `attributions` None = pas encore décidé → on renvoie les carcasses sans bouger ;
		# une liste (même vide) = la répartition choisie, appliquée avant le changement.
		if not passage.get("surface") and _etage_nettoye(combat_doc):
			dispo = butin_d_etage(combat_doc)
			if dispo and attributions is None:
				return {"butin_etage": dispo, "passage_id": passage.get("id")}
			if dispo:
				erreur = _repartir_butin_d_etage(combat_doc, dispo, attributions)
				if erreur:
					return {"error": erreur}
		if passage.get("surface"):
			_sortir_du_donjon(combat_doc, passage)
			result = {"sortie": True}
		else:
			result = {"passage": dict(passage)}

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
		_ajuster_charge_magique(joueur, poids, charge_magie.coefficient_item(item))
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
		_poids_consomme = float(item.get("poids", 0) or 0)
		joueur["charge"] = round(max(0.0, joueur.get("charge", 0) - _poids_consomme), 2)
		_ajuster_charge_magique(joueur, -_poids_consomme, charge_magie.coefficient_item(item))
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
		cout_pm = _cout_pm_charge(joueur, sdoc)
		# ⚠️ MÊME FONCTION que `sorts.sort_utilisable_combat`, celle qui a filtré ce sort
		# côté router : les deux ne peuvent plus diverger. `effets` est passé à part —
		# ce sont les effets FUSIONNÉS avec le bonus des composants engagés, et c'est sur
		# eux qu'il faut juger, pas sur ceux du doc nu.
		if not capacite_utilisable_combat(sdoc, effets):
			return {"error": "Ce sort n'a aucun effet utilisable en combat."}
		cout_pv = max(0, int(effets.get("cout_pv", 0) or 0))
		# ⚠️ `>` STRICT : à 0 PV le lanceur est « à terre ». Un sort capable d'assommer son
		# auteur par sa seule facture ouvrirait une condition de défaite absurde.
		if cout_pv and joueur["currentPV"] <= cout_pv:
			return {"error": "Pas assez de PV pour payer ce sort."}

		if est_incantation_longue(sdoc):
			# INCANTATION LONGUE : le sort ne part pas maintenant. Il s'arme, puis absorbe
			# les PA du lanceur tour après tour (`_avancer_incantation`), et se résout de
			# lui-même quand la totalité des PA a été versée.
			# ⚠️ Testée AVANT le débit des PM : ils partent par TRANCHES, une par PA.
			if joueur.get("incantation"):
				return {"error": "Une incantation est déjà en cours."}
			result = _armer_incantation(combat_doc, joueur, sdoc, effets, cible_id, dx, dy)
			jet = None
			_payer_cout_pv(combat_doc, joueur, sdoc, cout_pv)
		else:
			if joueur["currentPM"] < cout_pm:
				return {"error": "PM insuffisants."}
			result, jet = _lancer_capacite(combat_doc, joueur, sdoc, effets,
										   cible_id, dx, dy, grid, "sort")
			if "error" in result:
				return result   # rien n'a été payé : le sort n'est jamais parti
			_payer_cout_pv(combat_doc, joueur, sdoc, cout_pv)

		# Les composants consommés quittent le sac → la charge portée baisse.
		poids_consommes = float(sort.get("poids_consommes", 0) or 0)
		if poids_consommes:
			joueur["charge"] = round(max(0.0, joueur.get("charge", 0) - poids_consommes), 2)
			# Coefficient inconnu ici : le router agrège PLUSIEURS composants en un seul
			# poids. Repli à 1.0, soit le poids physique — le défaut partout ailleurs.
			_ajuster_charge_magique(joueur, -poids_consommes)
			_recompute_player_deplacement(joueur)
			result["charge"] = joueur["charge"]
		result["currentPM"] = joueur["currentPM"]
		# ⚠️ Une incantation LONGUE ne passe pas par ce compteur : ses PA sont déjà décomptés
		# un par un par `canalisation` (cf. `_avancer_incantation`). L'ajouter ferait payer
		# une action de plus le tour où le mage se contente de commencer à incanter.
		if not est_incantation_longue(sdoc):
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
		# normalisée. Les compétences PASSIVES n'arrivent jamais ici — leur bonus est déjà
		# intégré au snapshot (competences_bonus → caracts_avec_buffs).
		#
		# ⚠️ MIROIR EXACT de la branche `sort` ci-dessus, et ce n'est plus une promesse
		# tenue à la main : les deux appellent `_lancer_capacite`, qui porte toute la
		# mécanique (saut, lien de vie, zones, furtivité, entretien). Ne restent ici que
		# le compteur d'actions, le fumble et la victoire — ce qui appartient au LANCEMENT
		# et se paie une seule fois, alors qu'une incantation longue traverse des tours.
		if not competence:
			return {"error": "Compétence invalide."}
		effets = competence.get("effets") or {}
		cout_pm = _cout_pm_charge(joueur, competence)
		# ⚠️ MÊME FONCTION que `competences.competence_utilisable_combat`, celle qui a
		# filtré cette compétence côté router : les deux ne peuvent plus diverger.
		if not capacite_utilisable_combat(competence, effets):
			return {"error": "Cette compétence n'a aucun effet utilisable en combat."}
		cout_pv = max(0, int(effets.get("cout_pv", 0) or 0))
		# ⚠️ `>` STRICT : à 0 PV le porteur est « à terre ». Une capacité capable d'assommer
		# son auteur par sa seule facture ouvrirait une condition de défaite absurde.
		if cout_pv and joueur["currentPV"] <= cout_pv:
			return {"error": "Pas assez de PV pour payer cette compétence."}

		if est_incantation_longue(competence):
			# INCANTATION LONGUE : la compétence ne part pas maintenant. Elle s'arme, puis
			# absorbe les PA du porteur tour après tour, et se résout d'elle-même quand la
			# totalité des PA a été versée — par le même chemin que les sorts.
			# ⚠️ Testée AVANT le débit des PM : ils partent par TRANCHES, une par PA.
			if joueur.get("incantation"):
				return {"error": "Une incantation est déjà en cours."}
			result = _armer_incantation(combat_doc, joueur, competence, effets,
										cible_id, dx, dy, "competence")
			resultat_jet = None
			_payer_cout_pv(combat_doc, joueur, competence, cout_pv)
		else:
			if joueur["currentPM"] < cout_pm:
				return {"error": "PM insuffisants."}
			result, resultat_jet = _lancer_capacite(combat_doc, joueur, competence, effets,
													cible_id, dx, dy, grid, "competence")
			if "error" in result:
				return result   # rien n'a été payé : la compétence n'est jamais partie
			_payer_cout_pv(combat_doc, joueur, competence, cout_pv)

		result["currentPM"] = joueur["currentPM"]
		# ⚠️ Une incantation LONGUE ne passe pas par ce compteur : ses PA sont déjà décomptés
		# un par un par `canalisation` (cf. `_avancer_incantation`). L'ajouter ferait payer
		# une action de plus le tour où le porteur se contente de commencer.
		if not est_incantation_longue(competence):
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
		"cle": monstre["id"],
		"item_id": item["_id"],
		"nom": item.get("nom", item["_id"]),
		"poids": _roll_carcasse_weight(item, monstre.get("niveau", 1)),
	}


def cle_butin(d: dict) -> str:
	"""Clé UNIQUE d'une ligne de butin. Carcasse : le `monstre_id` (forme d'avant — combats et
	gardes `butin_collectes` déjà en base restent valides) ; objet équipé : `<monstre_id>|<slot>`.
	Une entrée sans `cle` (combat antérieur) est une carcasse."""
	return d.get("cle") or d["monstre_id"]


def _objets_payload(monstre: dict) -> list[dict]:
	"""Une ligne de butin par objet ÉQUIPÉ d'un humanoïde (`slots` tiré par
	`roll_monster_equipment`) : `{monstre_id, cle, slot, item_id, nom, poids}`, poids d'instance
	tiré dans les bornes du doc (`tirer_poids`). Sans `slots` (bête, humanoïde nu)
	⇒ []. Un item absent de la base est sauté."""
	lignes = []
	for slot, item_id in (monstre.get("slots") or {}).items():
		item = get_doc(item_id) if item_id else None
		if not item:
			continue
		lignes.append({
			"monstre_id": monstre["id"],
			"cle": f"{monstre['id']}|{slot}",
			"slot": slot,
			"item_id": item_id,
			"nom": item.get("nom", item_id),
			"poids": tirer_poids(item),
		})
	return lignes


def _butin_du_monstre(monstre: dict) -> list[dict]:
	"""Butin d'un monstre MORT : sa carcasse (sauf déjà ramassée en combat, `loote` — qui ne
	concerne QUE la carcasse) puis, pour un humanoïde, chacun de ses objets équipés."""
	lignes = []
	if not monstre.get("loote"):
		payload = _carcasse_payload(monstre)
		if payload:
			lignes.append(payload)
	return lignes + _objets_payload(monstre)


def verser_butin_au_sol(character: dict, combat_doc: dict, deja=None) -> list[dict]:
	"""Verse au SOL du principal les éléments de `butin_disponible` (carcasses, objets
	équipés des humanoïdes) que personne n'a emportés, et les inscrit par CLÉ de ligne
	(`cle_butin`) dans la MÊME garde que l'encaissement. Mute `character`
	(`objets_au_sol` + `butin_collectes`) et `combat_doc` (`butin_disponible` vidé) ;
	ne sauvegarde RIEN — l'appelant persiste. Renvoie `[{nom, poids}]` de ce qui est tombé.

	POURQUOI. Une carcasse est INDIVISIBLE tant qu'elle est dans le butin : l'overlay de fin
	l'attribue entière à un membre, ou à personne. Un cerf de 180 kg qu'aucun membre ne peut
	porter n'avait donc qu'une issue, disparaître — exactement le butin que `utils/carcasse.py`
	existe pour rendre accessible (« on emporte la tête et les pattes, on abandonne le corps »).
	Au sol, il redevient débitable (`POST /api/couper`, `source:"sol"`) puis emportable morceau
	par morceau. Plus aucun geste ne détruit du butin : abandonner, c'est laisser par terre et
	faire un pas.

	⚠️ Le sol appartient au PERSONNAGE et non au lieu (champ transitoire, vidé au premier pas
	par les DEUX branches de `move_character`) : il n'y a aucun cas particulier à écrire pour
	une salle de donjon, où le joueur n'a de toute façon jamais bougé — ni `routers/combat.py`
	ni `_declencher_combat_donjon` n'écrivent `lieu`/`position`, la salle n'est qu'un décor de
	battle map. La pile l'attend là où il se tient, c.-à-d. au seuil.

	⚠️ MÊME garde que l'encaissement (`butin_collectes[combat_id]`) : « déjà sorti du butin »
	vaut pour un sac COMME pour le sol. Sans cela, un second /collect — ou le filet de /play
	après un `save_doc(combat_doc)` best-effort échoué — reverserait la carcasse une seconde
	fois. `deja` = ce que l'appelant vient d'encaisser, pas encore écrit dans la garde.

	⚠️ Aucune lecture de doc : `butin_disponible` porte déjà `item_id`, `nom` et `poids`. Le
	poids versé est celui de l'INSTANCE (tiré au butin), comme à l'encaissement — c'est lui que
	`carcasse.item_est_decoupable(doc, poids)` compare au seuil de découpe.

	⚠️ VICTOIRE SEULEMENT. `butin_disponible` n'a de sens qu'à la victoire — c'est là, et là
	seulement, que `finalize_combat` le remplit —, et le garde interdit qu'une écriture
	future y verse quoi que ce soit qui se retrouverait au sol sans qu'on l'ait décidé.
	Précédent : la cargaison d'une monture tombée y transitait POUR TOUTES LES ISSUES, si
	bien qu'un filet non gardé aurait rendu sur une défaite un butin délibérément perdu.
	(Elle va désormais au sol directement, cf. `_finalize_monture`.)
	"""
	if combat_doc.get("status") != "victoire":
		return []
	combat_id = combat_doc.get("_id")
	guard = character.get("butin_collectes", {})
	if not isinstance(guard, dict):
		guard = {}
	traites = set(guard.get(combat_id, [])) | set(deja or ())

	au_sol = character.get("objets_au_sol", [])
	verses = []
	for d in (combat_doc.get("butin_disponible") or []):
		if not d.get("monstre_id"):
			continue
		cle = cle_butin(d)
		if cle in traites:
			continue
		au_sol.append({"item": d["item_id"], "poids": d["poids"]})
		verses.append({"nom": d.get("nom", d["item_id"]), "poids": d["poids"]})
		traites.add(cle)
	character["objets_au_sol"] = au_sol

	# ⚠️ `pop` AVANT l'écriture : réassigner une clé existante ne la déplace pas en fin de
	# dict, et l'ordre d'insertion EST l'ordre de récence qui décide de l'éviction.
	guard.pop(combat_id, None)
	guard[combat_id] = sorted(traites)
	character["butin_collectes"] = dict(list(guard.items())[-MEMOIRE_COMBATS_MAX:])
	combat_doc["butin_disponible"] = []
	return verses


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
	restants = _effets_a_reverser(joueur)
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
	troupeau et sa cargaison se DÉVERSE AU SOL du principal (champ transitoire, perdu au
	premier pas), d'où le joueur emporte ce qu'il peut porter et débite le reste.

	⚠️ QUELLE QUE SOIT L'ISSUE, et c'est un changement délibéré : la cargaison passait par
	`butin_disponible`, qui n'est proposé QU'À LA VICTOIRE — une défaite l'emportait donc
	(« prix assumé du risque »). Le sol n'a pas cette contrainte : la bête tombe là où elle
	tombe, sa charge s'y répand (le log du KO le dit déjà), et le groupe relevé à 1 PV la
	retrouve sur place.

	⚠️ C'est aussi le seul chemin qui préserve les RÉFÉRENCES telles quelles : le détour par
	le butin les reconstruisait en `{item, poids}`, perdant `lieu_parent` (donc le libellé
	« Carte d'aventurier (Auxerre) ») et aplatissant les réfs legacy en chaîne nue. Il
	économise au passage une lecture de doc item par objet porté.

	⚠️ La cargaison est versée sur le doc du PRINCIPAL, sauvé par `_finalize_membre` juste
	après — donc sous SON garde exactly-once, là où le reste de cette fonction est sous
	celui de la bête. Rien de neuf (`montures_util.tuer` mute déjà `character["montures"]`)
	et rien à craindre : `finalize_combat` sort AVANT cette boucle quand le principal a
	déjà été récompensé.

	Même garde d'idempotence PAR DOC que `_finalize_membre` : une re-finalisation ne peut
	ni ressusciter la bête ni dupliquer sa cargaison."""
	combat_id = combat_doc.get("_id")
	rewarded = doc.get("combats_recompenses", [])
	if combat_id in rewarded:
		return False

	# Carcasses chargées sur la bête au changement d'étage d'un donjon (`butin_ramasse`) :
	# dans son sac AVANT l'aiguillage, donc déversées au sol avec le reste si elle est morte.
	ramasse = [i for i in snap.get("butin_ramasse", []) if i]
	if ramasse:
		doc["inventaire"] = list(doc.get("inventaire") or []) + ramasse

	if snap.get("morte") and character_stats.MONTURE_MORT_DEFINITIVE:
		cargaison = montures_util.tuer(character, doc)
		if cargaison:
			au_sol = character.get("objets_au_sol", [])
			au_sol.extend(cargaison)
			character["objets_au_sol"] = au_sol
	else:
		# Survivante (ou mort désactivée) : relevée comme un membre du groupe.
		doc["currentPV"] = max(1, snap.get("currentPV", 0))
		doc["currentPM"] = max(0, snap.get("currentPM", doc.get("currentPM", 0)))
		# Effets à durée encore vivants (un buff lancé sur la bête par un allié) :
		# reversés comme pour un membre du groupe. Un doc `monture:*` étant un miroir
		# du character, le tick d'exploration les reprend sans code supplémentaire.
		restants = _effets_a_reverser(snap)
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
		restants = _effets_a_reverser(snap)
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

	# Butin des monstres tués (carcasse non ramassée + objets équipés d'un humanoïde, une
	# ligne chacun) : proposé dans l'overlay de fin UNIQUEMENT en cas de victoire. Le joueur
	# choisit quoi emporter via POST /api/combat/{id}/collect (borné par charge_max) — pas
	# d'ajout automatique.
	if status == "victoire":
		dispo = []
		for m in combat_doc["monstres"]:
			# Un vivant ne laisse rien : une sortie de donjon à étages est une
			# victoire même quand des monstres rôdent encore à l'étage.
			if m.get("vivant", False):
				continue
			dispo.extend(_butin_du_monstre(m))
		combat_doc["butin_disponible"] = dispo

	# Montures : une bête tombée quitte le troupeau et déverse sa cargaison au SOL du
	# principal (elle ne passe plus par `butin_disponible`, qui n'est proposé qu'à la
	# victoire — cf. `_finalize_monture`). Mute `character`, sauvé juste en dessous.
	for j, doc in montures_traitees:
		_finalize_monture(combat_doc, j, doc, status, character)

	# Personnes escortées — même place, même motif que les montures : le personnage est muté
	# ici (retrait du groupe, archivage de la quête en échec) et sauvé par `_finalize_membre`
	# juste en dessous, dans le même save que l'XP.
	for j, doc in proteges_traites:
		_finalize_protege(combat_doc, j, doc, status, character)

	# Progression des quêtes de chasse : compte les monstres tués (toute issue), sous le
	# même garde exactly-once que l'XP → pas de double comptage si /play re-finalise.
	# Donjon à étages : les monstres des étages quittés comptent aussi (archivés).
	tous_monstres = _monstres_de_l_expedition(combat_doc)
	maj_progress_kills(character, tous_monstres)
	# Quêtes de « chasse » (élite marquée) : complétées si le monstre porteur du quete_chasse
	# est tombé. Même fenêtre d'idempotence que les kills ci-dessus.
	maj_progress_chasse(character, tous_monstres)
	# Bestiaire du carnet (onglet 📖) : TOUTES les espèces de ce combat, tuées OU NON — c'est
	# un carnet d'observation, une bête qu'on a fuie a bien été rencontrée. D'où un hook à
	# part de `maj_progress_kills`, qui ne retient que les morts.
	# ⚠️ Ici et pas dans `start_combat` : celui-ci ne sauve JAMAIS le doc personnage, alors
	# que cette zone-ci est déjà sous le garde exactly-once `combats_recompenses` et sera
	# persistée par le `_finalize_membre` du principal, plus bas — donc coût zéro. Et rien
	# n'échappe au hook : /play interdit d'abandonner un combat actif et re-finalise les
	# combats terminés.
	# ⚠️ Le doc `lieu:*` (le plus gros du jeu, hors cache de requête) n'est relu QUE si une
	# espèce de ce combat n'a pas encore ce lieu à son actif : un combat répété au même
	# endroit ne coûte aucune lecture.
	lieu_id = character.get("lieu", "")
	monstres = tous_monstres
	label = ""
	if journal.lieux_a_nommer(character, monstres, lieu_id):
		label = lieu_label(get_doc(lieu_id), lieu_id)
	journal.noter_rencontres(character, monstres, lieu_id, label)
	# Salle gardée nettoyée : la porte par laquelle on est entré ne se rouvrira plus, et une
	# barrière peut s'ouvrir derrière (la clairière dégagée devant la grotte aux loups).
	# ⚠️ `salle_gardee` et JAMAIS `battle_map_id` : cf. `characters.noter_victoire` — la même
	# carte sert de décor aux combats de zone, qui ne franchissent aucune porte.
	# ⚠️ Même place et même motif que le bestiaire ci-dessus : déjà sous le garde
	# exactly-once `combats_recompenses`, persisté par le `_finalize_membre` du principal —
	# donc aucun `save_doc` ajouté.
	if status == "victoire" and combat_doc.get("salle_gardee"):
		noter_victoire(character, combat_doc["salle_gardee"])
	# Donjon à étages : remontée par un passage vers la surface — le groupe réapparaît à
	# l'arrivée de la connexion (une défaite le laisse au lieu d'où il est descendu).
	# Même save que l'XP, donc même garde exactly-once. Le sol est transitoire (§6).
	sortie = combat_doc.get("sortie") or {}
	if status == "victoire" and sortie.get("lieu"):
		character["lieu"] = sortie["lieu"]
		character["position"] = {"x": int(sortie.get("pos", {}).get("x", 0)),
								 "y": int(sortie.get("pos", {}).get("y", 0))}
		character["objets_au_sol"] = []
		character["ressource_recoltable"] = None
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

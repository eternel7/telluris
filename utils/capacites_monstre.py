# utils/capacites_monstre.py
# Magie et capacités PROPRES des monstres (pur, DB injectée, ne sauve rien).
#
# Deux sources, deux règles :
# - SORTS : tirés par TAG d'espèce `magie_<école>_<niveau>[_<profil>]`. Sans suffixe, le tag
#   vaut pour tout profil ; avec, pour ce seul profil (`magie_elementaire_2_apprenti`). Le
#   nombre de sorts tirés reste le niveau du profil (`combat.roll_monster_sorts`).
# - COMPÉTENCES INNÉES : champ `competences: [ids]` de l'espèce, docs `competence:*` de
#   vocation `monstre` (même schéma d'effets que les joueurs, jamais apprenables : aucun
#   personnage n'a cette vocation). Présentes quel que soit le grade.
#     · passive `cible: soi`    → bonus permanents du spécimen (régénération, buffs) ;
#     · passive `cible: ennemi` → part à durée posée À L'IMPACT de son attaque naturelle
#       (venin) — même chemin que l'effet d'une arme empoisonnée (`combat._appliquer_effet_arme`).

#
# IA : à son tour, un monstre peut lancer AU PLUS UNE capacité active (`choisir_capacite`),
# payée en PM et suivie d'une RECHARGE en tours (`recharges` du snapshot, décrémenté au début
# de chacun de ses tours). Le moteur (`combat._options_capacite_monstre`) construit les
# options — cibles, victimes de la zone, bénéficiaires — ; ce module ne fait que les noter.

import re
import unicodedata

from utils.competences import competence_utilisable_combat, est_active, est_passive, normaliser_competence
from utils.consommables import _as_int, _as_signed_int
from utils.sorts import (est_incantation_longue, est_maintenu, normaliser_sort, part_durative,
						 resoudre_effets, sort_utilisable_combat)

VOCATION_MONSTRE = "monstre"

# Valeur d'un effet à durée NEUF dans le score d'une option, en points de dégâts : à peu près
# l'espérance d'un 2D6 — un debuff vaut un coup moyen, pas plus. Un effet que la victime porte
# déjà (même source) ne vaut rien : le relancer ne ferait que le rafraîchir.
BONUS_EFFET = 7.0
# Un soin ne vaut que sous ce ratio de PV (bénéficiaire blessé).
SEUIL_SOIN = 0.5

_TAG_MAGIE = re.compile(r"^magie_([a-z]+)_(\d+)(?:_([a-z0-9_]+))?$")


def slug_ecole(nom) -> str:
	"""Clé d'école comparable à un tag : minuscules, sans accent ni espace
	(`Élémentaire` → `elementaire`). Les écoles ne sont recopiées nulle part : un tag se
	compare au slug de l'école PORTÉE par le sort."""
	texte = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode()
	return re.sub(r"[^a-z0-9]", "", texte.lower())


def _suffixe_profil(profil_id) -> str:
	return str(profil_id or "").split(":", 1)[-1]


def magies_de_tags(tags, profil_id=None) -> dict:
	"""{slug d'école: niveau max} que les tags `magie_*` ouvrent au profil `profil_id`.

	Un tag sans profil vaut pour tous ; un tag suffixé ne vaut que pour le sien. Plusieurs
	tags d'une même école ⇒ le plafond le plus HAUT parmi ceux qui s'appliquent. Tag mal
	formé ⇒ ignoré."""
	profil = _suffixe_profil(profil_id)
	out: dict = {}
	for tag in tags or []:
		m = _TAG_MAGIE.match(str(tag))
		if not m:
			continue
		ecole, niveau, pour = m.group(1), int(m.group(2)), m.group(3)
		if pour and pour != profil:
			continue
		out[ecole] = max(out.get(ecole, 0), niveau)
	return out


def competences_espece(espece: dict, get_doc) -> list:
	"""Compétences innées de l'espèce, normalisées (ids morts ou invalides ignorés)."""
	out = []
	for cid in (espece or {}).get("competences") or []:
		comp = normaliser_competence(get_doc(str(cid))) if cid else None
		if comp:
			out.append(comp)
	return out


def passives_permanentes(competences: list, caracts: dict) -> dict:
	"""Somme des passives `cible: soi` d'un spécimen, formules résolues sur ses caracts
	BRUTES : {buffs, regen_pv, regen_pm, esquive}. Une passive à condition de terrain ou à
	zone (aura) n'y entre pas — comme pour les joueurs (`competences.bonus_passifs`)."""
	buffs: dict = {}
	regen_pv = regen_pm = esquive = 0
	for comp in competences or []:
		if not est_passive(comp) or comp.get("cible") != "soi" or comp.get("condition") or comp.get("zone"):
			continue
		eff = resoudre_effets(comp.get("effets") or {}, caracts)
		for k, delta in (eff.get("buffs") or {}).items():
			buffs[str(k)] = buffs.get(str(k), 0) + _as_signed_int(delta)
		regen_pv += _as_signed_int(eff.get("regen_pv"))
		regen_pm += _as_signed_int(eff.get("regen_pm"))
		esquive += _as_int(eff.get("esquive"))
	return {"buffs": buffs, "regen_pv": regen_pv, "regen_pm": regen_pm, "esquive": esquive}


def effets_a_l_impact(competences: list, caracts: dict) -> dict | None:
	"""Part à durée que l'attaque naturelle pose à l'impact (venin) : la PREMIÈRE passive
	`cible: ennemi` à part durative, formules résolues sur les caracts du spécimen.
	{effets, source_id, nom, icon} ou None."""
	for comp in competences or []:
		if not est_passive(comp) or comp.get("cible") != "ennemi":
			continue
		eff = resoudre_effets(comp.get("effets") or {}, caracts)
		if part_durative(eff):
			return {"effets": eff, "source_id": comp["id"], "nom": comp.get("nom", ""),
					"icon": comp.get("icon", "")}
	return None


# Clés d'effet qu'un sort de MONSTRE ne sait pas encore jouer (elles visent une case, un
# allié ou un état propre au joueur) : un sort qui en porte n'est pas lancé par l'IA.
EFFETS_HORS_IA = ("saut", "echange", "vol", "lien_vie", "partage_soin", "provocation")


def sort_lancable_par_ia(sort: dict | None) -> bool:
	"""Un sort tiré est-il jouable par l'IA ? Instantané (1 PA), ni maintenu, ni invocation,
	sans effet visant une case ou un allié du joueur (`EFFETS_HORS_IA`)."""
	if not sort or not sort_utilisable_combat(sort):
		return False
	if est_incantation_longue(sort) or est_maintenu(sort) or sort.get("invocation"):
		return False
	eff = sort.get("effets") or {}
	return not any(eff.get(k) for k in EFFETS_HORS_IA)


def actives_du_monstre(monstre: dict, get_doc) -> list:
	"""Capacités ACTIVES que l'IA peut lancer : compétences innées (`competences_monstre`)
	puis sorts tirés (`sorts_connus`) jouables par l'IA (`sort_lancable_par_ia`)."""
	out = []
	for cid in (monstre or {}).get("competences_monstre") or []:
		comp = normaliser_competence(get_doc(str(cid)))
		if comp and est_active(comp) and competence_utilisable_combat(comp) and not comp.get("pose_piege"):
			out.append(comp)
	for sid in (monstre or {}).get("sorts_connus") or []:
		sort = normaliser_sort(get_doc(str(sid)))
		if sort_lancable_par_ia(sort):
			out.append(sort)
	return out


def _porte_effet(acteur: dict, source_id: str) -> bool:
	return any(e.get("source_id") == source_id for e in (acteur or {}).get("effets_actifs") or [])


def score_option(option: dict, moyenne_fn) -> float:
	"""Valeur d'une option en points de dégâts (0 = inutile).

	Hostile : pour chaque victime de la zone, l'espérance des dégâts (`moyenne_fn`), la moitié
	de celle des dégâts aux PM, et `BONUS_EFFET` si la part à durée est neuve pour elle.
	Soutien : un soin compte pour ce qu'il rend à un bénéficiaire BLESSÉ (sous `SEUIL_SOIN`),
	une part à durée neuve pour `BONUS_EFFET`."""
	eff = option.get("effets") or {}
	sid = option.get("source_id", "")
	duratif = part_durative(eff)
	score = 0.0
	if option.get("hostile"):
		for v in option.get("victimes") or []:
			if eff.get("degats"):
				score += moyenne_fn(eff["degats"])
			if eff.get("degats_pm") and _as_int(v.get("pm_max")) > 0:
				score += moyenne_fn(eff["degats_pm"]) / 2
			if duratif and not _porte_effet(v, sid):
				score += BONUS_EFFET
		return score
	for b in option.get("beneficiaires") or []:
		pv_max = max(1, _as_int(b.get("pv_max")))
		manque = pv_max - _as_int(b.get("currentPV"))
		if _as_int(eff.get("pv")) and _as_int(b.get("currentPV")) < pv_max * SEUIL_SOIN:
			score += min(_as_int(eff["pv"]), manque)
		if duratif and not _porte_effet(b, sid):
			score += BONUS_EFFET
	return score


def choisir_capacite(options: list, moyenne_fn, rand_fn=None) -> dict | None:
	"""L'option au meilleur score (> 0), ex æquo départagés par `rand_fn` (choix dans une
	liste, `random.choice` par défaut) ; None si aucune ne sert à rien."""
	notees = [(score_option(o, moyenne_fn), o) for o in options or []]
	notees = [(s, o) for s, o in notees if s > 0]
	if not notees:
		return None
	meilleur = max(s for s, _ in notees)
	ex_aequo = [o for s, o in notees if s == meilleur]
	if len(ex_aequo) == 1:
		return ex_aequo[0]
	if rand_fn is None:
		import random
		rand_fn = random.choice
	return rand_fn(ex_aequo)


def decrementer_recharges(acteur: dict) -> None:
	"""Début de tour : chaque recharge en cours perd un tour (plancher 0, entrée retirée)."""
	recharges = (acteur or {}).get("recharges")
	if not recharges:
		return
	for cid in list(recharges):
		reste = _as_int(recharges[cid]) - 1
		if reste > 0:
			recharges[cid] = reste
		else:
			del recharges[cid]

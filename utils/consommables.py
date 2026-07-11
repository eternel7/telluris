# utils/consommables.py
# Consommables à effet de gameplay : un item `categorie:"consommable"` porte un champ
# `effets` {pv, pm, regen_pv, regen_pm, buffs:{caract:+delta}, duree} (tous optionnels).
# pv/pm = instantanés (seuls utilisables en combat) ; buffs/regen_* = effet actif empilé
# sur character["effets_actifs"], décrémenté à chaque tour monde (move_character), jamais
# pendant un combat (le snapshot d'entrée fige le bénéfice).
#
# Logique pure (resolve_ref injecté), ne sauvegarde jamais — l'endpoint persiste.
# Les buffs sont volontairement EXCLUS de charge_max_of, des plafonds/coûts d'XP et de
# restriction_satisfaite (équipement) : un buff expiré ne doit ni bloquer un déplacement
# (surcharge), ni permettre d'équiper/monter ce qu'on ne pourrait pas sans lui.

from utils.characters import item_ref_id


def _as_int(x) -> int:
	try:
		return max(0, int(x or 0))
	except (TypeError, ValueError):
		return 0


def effets_de(item_doc) -> dict:
	"""Champ `effets` de l'item, normalisé : pv/pm/regen_pv/regen_pm entiers ≥ 0,
	buffs dict {caract: int}, duree entier ≥ 0. Dict aux clés toujours présentes."""
	raw = (item_doc or {}).get("effets") or {}
	buffs = {}
	for k, v in (raw.get("buffs") or {}).items():
		try:
			buffs[str(k)] = int(v)
		except (TypeError, ValueError):
			continue
	return {
		"pv": _as_int(raw.get("pv")),
		"pm": _as_int(raw.get("pm")),
		"regen_pv": _as_int(raw.get("regen_pv")),
		"regen_pm": _as_int(raw.get("regen_pm")),
		"buffs": buffs,
		"duree": _as_int(raw.get("duree")),
	}


def est_consommable(item_doc) -> bool:
	"""Consommable actif = catégorie `consommable` ET au moins un effet. Les consommables
	sans `effets` (Torche, Bougie…) restent inertes — rétro-compat volontaire."""
	if not item_doc or item_doc.get("categorie") != "consommable":
		return False
	eff = effets_de(item_doc)
	return bool(eff["pv"] or eff["pm"] or eff["regen_pv"] or eff["regen_pm"] or eff["buffs"])


def effet_instantane(item_doc) -> bool:
	"""Éligibilité combat : seul un effet instantané (pv ou pm) est applicable en combat
	(pas d'empilement d'effet actif pendant un combat — la part buffs/régén est perdue)."""
	eff = effets_de(item_doc)
	return eff["pv"] > 0 or eff["pm"] > 0


def _sources_de_buffs(character: dict) -> list:
	"""Toutes les sources de buffs/régén d'un personnage, au même format {buffs, regen_*} :
	les effets actifs TEMPORAIRES (consommables, sorts — décrémentés au tour monde) et le
	bonus PERMANENT des compétences passives (`competences_bonus`, dénormalisé par
	utils/competences.recompute_competences_bonus). Chokepoint unique : tout ce qui buffe
	un personnage passe ici, donc par caracts_avec_buffs/regen_bonus."""
	character = character or {}
	sources = list(character.get("effets_actifs") or [])
	passif = character.get("competences_bonus")
	if passif:
		sources.append(passif)
	return sources


def caracts_avec_buffs(character: dict) -> dict:
	"""COPIE de caracteristiques_current + somme des buffs (clamp ≥ 0). N'applique que les
	caracts déjà présentes, et jamais V (échelle 1-10, incompatible avec des deltas ×10)."""
	caracts = dict((character or {}).get("caracteristiques_current") or {})
	for eff in _sources_de_buffs(character):
		for k, delta in (eff.get("buffs") or {}).items():
			if k == "V" or k not in caracts:
				continue
			try:
				caracts[k] = max(0, int(caracts[k] or 0) + int(delta))
			except (TypeError, ValueError):
				continue
	return caracts


def regen_bonus(character: dict) -> tuple[int, int]:
	"""(Σ regen_pv, Σ regen_pm) des effets actifs et des passives — s'ajoute à la régén
	naturelle."""
	pv = pm = 0
	for eff in _sources_de_buffs(character):
		pv += _as_int(eff.get("regen_pv"))
		pm += _as_int(eff.get("regen_pm"))
	return pv, pm


def empiler_effet(character: dict, item_doc: dict) -> dict | None:
	"""Empile l'effet à durée (buffs/régén) de l'item sur character["effets_actifs"]
	(mute en place, NE SAUVEGARDE PAS). Renvoie l'entrée créée, None si l'item n'a pas
	d'effet à durée. Empilement autorisé (2 potions = 2 entrées)."""
	eff = effets_de(item_doc)
	if eff["duree"] <= 0 or not (eff["buffs"] or eff["regen_pv"] or eff["regen_pm"]):
		return None
	entry = {
		"item_id": item_doc.get("item") or item_doc.get("_id"),
		"nom": item_doc.get("nom", "Effet"),
		"icon": item_doc.get("icon", "✨"),
		"buffs": eff["buffs"],
		"regen_pv": eff["regen_pv"],
		"regen_pm": eff["regen_pm"],
		"restants": eff["duree"],
	}
	character.setdefault("effets_actifs", []).append(entry)
	return entry


def appliquer_instantane(character: dict, item_doc: dict, pv_max: int, pm_max: int) -> dict:
	"""Applique la part instantanée (pv/pm) au personnage, clampée aux max passés (mute
	en place, NE SAUVEGARDE PAS). pv_max/pm_max sont fournis par l'appelant, calculés
	APRÈS l'empilement du buff : une potion mixte soigne dans le max bufffé."""
	eff = effets_de(item_doc)
	avant_pv = int(character.get("currentPV", pv_max) or 0)
	avant_pm = int(character.get("currentPM", pm_max) or 0)
	character["currentPV"] = min(int(pv_max), avant_pv + eff["pv"])
	character["currentPM"] = min(int(pm_max), avant_pm + eff["pm"])
	return {
		"pv_rendu": character["currentPV"] - avant_pv,
		"pm_rendu": character["currentPM"] - avant_pm,
	}


def tick_effets(character: dict) -> list:
	"""Décrémente `restants` de chaque effet actif, purge ceux à 0 (mute en place).
	Renvoie les entrées expirées (l'appelant re-clampe PV/PM si un buff R/Vol tombe)."""
	actifs = (character or {}).get("effets_actifs") or []
	if not actifs:
		return []
	restants, expires = [], []
	for eff in actifs:
		eff["restants"] = _as_int(eff.get("restants")) - 1
		(restants if eff["restants"] > 0 else expires).append(eff)
	character["effets_actifs"] = restants
	return expires


def effets_actifs_payload(character: dict) -> list:
	"""Effets actifs pour l'UI (chips ✨ de la fiche) — copies, jamais les entrées vives."""
	return [dict(eff) for eff in (character or {}).get("effets_actifs") or []]


def liste_consommables_combat(character: dict, resolve_ref_fn) -> list:
	"""Consommables du sac utilisables en combat (effet instantané seulement), avec leur
	index D'ORIGINE dans l'inventaire (adressage serveur par index vérifié item_id)."""
	out = []
	for idx, ref in enumerate((character or {}).get("inventaire") or []):
		doc = resolve_ref_fn(ref)
		if not doc or not est_consommable(doc) or not effet_instantane(doc):
			continue
		eff = effets_de(doc)
		out.append({
			"index": idx,
			"item_id": item_ref_id(ref),
			"nom": doc.get("nom", "?"),
			"icon": doc.get("icon", "🧪"),
			"pv": eff["pv"],
			"pm": eff["pm"],
			"poids": doc.get("poids", 0),
		})
	return out

# utils/competences.py
# Compétences de vocation : un doc CouchDB `competence:*` porte une vocation, un niveau,
# un mode (`passive` / `active`) et des `effets` au format des sorts/consommables
# ({degats, pv, pm, regen_pv, regen_pm, buffs, duree}). Miroir de `utils/sorts.py`, à deux
# différences près : `cout_pm` peut valoir 0 (un sort exige > 0) et il n'y a pas de composants.
#
# PASSIVE = permanente. Ses buffs/régén sont dénormalisés dans character["competences_bonus"]
# (pattern d'equipment_bonus), recalculé à la création et à chaque apprentissage, puis replié
# par utils/consommables.caracts_avec_buffs / regen_bonus — le seul chokepoint des buffs, donc
# une passive est effective partout (fiche, exploration, snapshot de combat) sans autre code.
#
# ACTIVE = coûte 1 action (+ cout_pm PM). En COMBAT, seule la part instantanée s'applique
# (degats/pv/pm) : comme pour les consommables et les sorts, la part buffs/durée d'un effet
# mixte est perdue (pas de tick en combat). En EXPLORATION, une active `cible:"soi"` applique
# sa part instantanée et empile ses buffs/régén sur character["effets_actifs"].
# Une active `cible:"ennemi"` porte son jet dans la donnée (`jet`: cc / cd / magique).
#
# Apprentissage : character["competences_connues"] (liste d'ids). Coût en points de
# caractéristique = (niveau + 1) × COMPETENCE_COUT_COEFF, dès que vocations_niveaux[vocation]
# ≥ niveau. Pas de grimoire (l'équivalent viendra avec l'arbre de compétences).
#
# À la CRÉATION, les vocations HORS SORT_VOCATIONS_DEPART choisissent une compétence de
# niveau 0 (complément exact du choix de sort — on choisit l'un ou l'autre, jamais les deux).
#
# Logique pure (get_doc/find_docs injectés), ne sauvegarde jamais — les endpoints persistent.

from models import character_stats
from utils.consommables import _as_int
from utils.sorts import _bonus_dict

MODES = ("passive", "active")
JETS = ("cc", "cd", "magique")


def normaliser_competence(doc) -> dict | None:
	"""Vue normalisée d'un doc `competence:*`, ou None si ce n'est pas une compétence
	valide (type ≠ "competence", vocation absente). Contrairement aux sorts, un coût en
	PM nul est légitime : une compétence martiale ne consomme pas de magie."""
	doc = doc or {}
	if doc.get("type") != "competence" or not doc.get("vocation"):
		return None
	mode = str(doc.get("mode") or "passive")
	if mode not in MODES:
		mode = "passive"
	jet = str(doc.get("jet") or "cc")
	if jet not in JETS:
		jet = "cc"
	return {
		"id": doc.get("_id", ""),
		"nom": doc.get("nom", "Compétence"),
		"icon": doc.get("icon", "⚡"),
		"description": doc.get("description", ""),
		"vocation": doc.get("vocation"),
		"niveau": _as_int(doc.get("niveau")),
		"mode": mode,
		"cout_pm": _as_int(doc.get("cout_pm")),
		"cible": doc.get("cible") or "soi",
		"jet": jet,
		"portee": max(1, _as_int(doc.get("portee")) or 1),
		"effets": _bonus_dict(doc.get("effets")),
	}


def est_passive(comp: dict) -> bool:
	return (comp or {}).get("mode") == "passive"


def est_active(comp: dict) -> bool:
	return (comp or {}).get("mode") == "active"


def competence_utilisable_combat(comp: dict) -> bool:
	"""Éligibilité combat : active ET part instantanée (dégâts, PV ou PM). La part
	buffs/durée d'une compétence mixte est perdue en combat (règle consommables)."""
	if not est_active(comp):
		return False
	eff = (comp or {}).get("effets") or {}
	return bool(eff.get("degats")) or _as_int(eff.get("pv")) > 0 or _as_int(eff.get("pm")) > 0


def competence_utilisable_exploration(comp: dict) -> bool:
	"""Éligibilité exploration : active, ciblée sur soi, et au moins un effet applicable
	hors combat (soin/PM instantanés, ou buffs/régén à durée)."""
	if not est_active(comp) or (comp or {}).get("cible", "soi") != "soi":
		return False
	eff = (comp or {}).get("effets") or {}
	instant = _as_int(eff.get("pv")) > 0 or _as_int(eff.get("pm")) > 0
	duratif = _as_int(eff.get("duree")) > 0 and bool(
		eff.get("buffs") or _as_int(eff.get("regen_pv")) or _as_int(eff.get("regen_pm")))
	return instant or duratif


def empiler_effet_competence(character: dict, comp: dict) -> dict | None:
	"""Empile la part à durée (buffs/régén) d'une compétence active sur
	character["effets_actifs"] (mute en place, NE SAUVEGARDE PAS). Même forme d'entrée que
	les consommables/sorts → tick_effets/caracts_avec_buffs/regen_bonus/chips inchangés."""
	eff = (comp or {}).get("effets") or {}
	if _as_int(eff.get("duree")) <= 0 or not (
			eff.get("buffs") or _as_int(eff.get("regen_pv")) or _as_int(eff.get("regen_pm"))):
		return None
	entry = {
		"competence_id": (comp or {}).get("id", ""),
		"nom": (comp or {}).get("nom", "Compétence"),
		"icon": (comp or {}).get("icon", "⚡"),
		"buffs": dict(eff.get("buffs") or {}),
		"regen_pv": _as_int(eff.get("regen_pv")),
		"regen_pm": _as_int(eff.get("regen_pm")),
		"restants": _as_int(eff.get("duree")),
	}
	character.setdefault("effets_actifs", []).append(entry)
	return entry


# ── Passives : bonus permanent dénormalisé ───────────────────────────────────────

def competences_connues_docs(character: dict, get_doc) -> list:
	"""Docs normalisés des compétences connues du personnage (ids morts ignorés)."""
	out = []
	for cid in (character or {}).get("competences_connues") or []:
		comp = normaliser_competence(get_doc(cid))
		if comp:
			out.append(comp)
	return out


def bonus_passifs(character: dict, get_doc) -> dict:
	"""Somme des buffs/régén des compétences PASSIVES connues : {buffs, regen_pv, regen_pm}.
	Les actives n'y contribuent jamais (leur effet passe par effets_actifs à l'usage)."""
	buffs: dict = {}
	regen_pv = regen_pm = 0
	for comp in competences_connues_docs(character, get_doc):
		if not est_passive(comp):
			continue
		eff = comp["effets"]
		for k, delta in (eff.get("buffs") or {}).items():
			buffs[str(k)] = int(buffs.get(str(k), 0)) + int(delta)
		regen_pv += _as_int(eff.get("regen_pv"))
		regen_pm += _as_int(eff.get("regen_pm"))
	return {"buffs": buffs, "regen_pv": regen_pv, "regen_pm": regen_pm}


def recompute_competences_bonus(character: dict, get_doc) -> dict:
	"""Recalcule character["competences_bonus"] depuis la source de vérité (les docs des
	compétences connues) — miroir de recompute_equipment_bonus. Mute, NE SAUVEGARDE PAS."""
	bonus = bonus_passifs(character, get_doc)
	character["competences_bonus"] = bonus
	return bonus


# ── Apprentissage ────────────────────────────────────────────────────────────────

def cout_apprentissage(comp: dict) -> int:
	"""Coût en points de caractéristique : (niveau + 1) × COMPETENCE_COUT_COEFF
	(lecture via le module — la world-var est réassignée à chaud)."""
	return (_as_int((comp or {}).get("niveau")) + 1) * character_stats.COMPETENCE_COUT_COEFF


def vocation_choisit_competence(voc) -> bool:
	"""Vrai si la vocation choisit une COMPÉTENCE de départ à la création — c'est-à-dire
	toute vocation qui ne choisit pas un SORT. Source unique de la règle (le client la
	re-dérive de la même liste)."""
	return bool(voc) and voc not in character_stats.SORT_VOCATIONS_DEPART


def competences_apprenables(character: dict, find_docs) -> list:
	"""Compétences achetables par le personnage : celles de sa vocation, de niveau atteint,
	pas déjà connues. Chaque entrée est enrichie de `cout_points`."""
	character = character or {}
	voc = character.get("voc")
	niveau_voc = _as_int((character.get("vocations_niveaux") or {}).get(voc, 0))
	connues = set(character.get("competences_connues") or [])
	out = []
	for doc in find_docs({"type": "competence"}) or []:
		comp = normaliser_competence(doc)
		if not comp or comp["id"] in connues or comp["vocation"] != voc:
			continue
		if niveau_voc < comp["niveau"]:
			continue
		comp["cout_points"] = cout_apprentissage(comp)
		out.append(comp)
	out.sort(key=lambda c: (c["niveau"], c["nom"]))
	return out


def competences_depart_par_vocation(find_docs) -> dict:
	"""Compétences niveau 0 groupées par vocation — choix de la compétence de départ à la
	création : {vocation: [{id, nom, icon, description, mode}]}."""
	out: dict = {}
	for doc in find_docs({"type": "competence"}) or []:
		comp = normaliser_competence(doc)
		if not comp or comp["niveau"] != 0:
			continue
		out.setdefault(comp["vocation"], []).append({
			"id": comp["id"], "nom": comp["nom"], "icon": comp["icon"],
			"description": comp["description"], "mode": comp["mode"],
		})
	for lst in out.values():
		lst.sort(key=lambda c: (c["mode"], c["nom"]))
	return out


# ── Payload UI ───────────────────────────────────────────────────────────────────

def liste_competences_payload(character: dict, get_doc, contexte: str) -> list:
	"""Compétences connues pour l'UI (rendu initial ET resync après action). Contexte
	"combat" : seules les actives à part instantanée (sélecteur ⚡). Contexte "exploration" :
	TOUTES les compétences connues (l'onglet ⚡ est un catalogue), drapeau `utilisable` pour
	les seules actives lançables hors combat — une passive n'est jamais « utilisable »."""
	out = []
	for comp in competences_connues_docs(character, get_doc):
		if contexte == "combat" and not competence_utilisable_combat(comp):
			continue
		out.append({
			"utilisable": True if contexte == "combat" else competence_utilisable_exploration(comp),
			"competence_id": comp["id"],
			"nom": comp["nom"],
			"icon": comp["icon"],
			"description": comp["description"],
			"niveau": comp["niveau"],
			"mode": comp["mode"],
			"cout_pm": comp["cout_pm"],
			"cible": comp["cible"],
			"jet": comp["jet"],
			"portee": comp["portee"],
			"effets": comp["effets"],
		})
	return out

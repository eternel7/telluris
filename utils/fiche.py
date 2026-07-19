# utils/fiche.py
# Source UNIQUE du contenu de la fiche de personnage (onglets Stats / Inventaire /
# Compétences). Le même bloc sert deux consommateurs :
#   - la page /play, pour le personnage principal (contexte Jinja) ;
#   - GET /api/groupe/compagnon/{id}, pour un compagnon — un doc `aventurier:*` est un
#     miroir du character, tous ces helpers s'y appliquent tels quels.
# Sans ce module, la fiche d'un compagnon serait une copie des ~10 appels de /play,
# vouée à diverger au premier onglet ajouté.
#
# Logique pure (DB injectée), ne sauvegarde jamais.

from models import character_stats
from models.character_stats import (
	BaseStats, compute_derived_stats, compute_stat_cap, compute_character_level,
	xp_seuil_niveau,
)
from utils.characters import sync_equipment_bonus, charge_max_of, resolve_item_ref
from utils import consommables
from utils import sorts as sorts_util
from utils import competences as competences_util
from utils import slots_actions


CARACTS = ["V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"]


def race_de(character: dict, get_doc_fn) -> dict:
	"""Doc de race du personnage ({} si introuvable)."""
	races = get_doc_fn("rules:races") or {}
	return next(
		(r for r in (races.get("value") or []) if r.get("id") == character.get("race")),
		None,
	) or {}


def stat_caps(character: dict, race: dict) -> dict:
	"""Plafonds par caractéristique. Calculés sur les caracts BRUTES (un buff ne doit
	jamais ouvrir de plafond — anti-exploit, cf. spend_xp)."""
	stats_cur = character.get("caracteristiques_current", {})
	return {
		code: compute_stat_cap(
			stat_key=code,
			stats_max=race.get("stats_max", {}),
			nb_max_accessibles=race.get("nb_max_accessibles", 3),
			current_stats=stats_cur,
			max_bonus=race.get("max_bonus"),
			max_bonus_used=character.get("max_bonus_used"),
		)
		for code in CARACTS
	}


def derived_de(character: dict) -> dict:
	"""Dérivées avec TOUS les buffs (équipement, passives, effets actifs), sauf la charge
	max — elle reste brute, c'est la limite réellement appliquée par la garde de surcharge
	(`charge_max_of`), donc celle qu'affichent la jauge et la ligne « Charge max »."""
	eq = sync_equipment_bonus(character)
	buffs = consommables.caracts_avec_buffs(character)
	base = BaseStats(
		v=buffs.get("V", 0), f=buffs.get("F", 0), r=buffs.get("R", 0), ag=buffs.get("Ag", 0),
		vol=buffs.get("Vol", 0), int_=buffs.get("Int", 0), cha=buffs.get("Cha", 0), ch=buffs.get("Ch", 0),
	)
	voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
	derived = compute_derived_stats(base=base, niveau=voc_niveau, equipment=eq)
	out = derived.model_dump()
	out["charge_max"] = charge_max_of(character)
	return out


def bloc_fiche(character: dict, get_doc_fn, find_docs_fn, race: dict | None = None) -> dict:
	"""Le contenu commun des onglets Stats et ⚡ (sorts + écoles + compétences), sous les
	MÊMES clés que le contexte de /play — le client les lit sans savoir de qui il s'agit."""
	race = race if race is not None else race_de(character, get_doc_fn)
	vocations = get_doc_fn("rules:vocations")
	niveau = compute_character_level(character.get("xp_total", 0))
	return {
		"stat_caps": stat_caps(character, race),
		"xp_coeff": character_stats.XP_COEFF,
		"xp_voc_coeff": character_stats.XP_VOC_COEFF,
		"xp_niv_prev": xp_seuil_niveau(niveau),
		"xp_niv_next": xp_seuil_niveau(niveau + 1),
		"effets_actifs": consommables.effets_actifs_payload(character),
		"caracts_detail": consommables.caracts_detail(character),
		"sorts": sorts_util.liste_sorts_payload(character, get_doc_fn, "exploration"),
		"sorts_apprenables": sorts_util.sorts_apprenables(
			character, find_docs_fn, resolve_item_ref, vocations
		),
		"sorts_magies": sorts_util.apprentissage_magies_payload(character, vocations),
		"competences": competences_util.liste_competences_payload(character, get_doc_fn, "exploration"),
		"competences_apprenables": competences_util.competences_apprenables(character, find_docs_fn),
		# Barre de combat : une seule liste ordonnée remplace les deux listes d'épinglés.
		# ⚠️ Clé `barre_slots` et non `slots` : ce bloc est fusionné dans le payload d'un
		# compagnon (`routers/recrutement._recrue_view`), où `slots` désigne déjà son
		# ÉQUIPEMENT — l'écraser viderait son paperdoll.
		"barre_slots": slots_actions.slots_payload(character, get_doc_fn),
		"barre_slots_max": slots_actions.slots_max(),
		"consommables": consommables.liste_consommables_combat(character, resolve_item_ref),
	}

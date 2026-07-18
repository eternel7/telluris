# utils/montures.py
# Montures de transport : une étable (`categorie:"etable"` ou tag "montures") vend des
# montures — docs `monture:*` MIROIRS du character, exactement comme `aventurier:*`
# (mêmes champs que consomment compute_derived_stats, carried_weight,
# build_joueur_snapshot, _apply_world_turn_regen) → tout le moteur marche dessus tel
# quel, sans code spécifique.
#
# Ce qu'une monture N'EST PAS : un compagnon. Elle n'a pas de tour en combat, ne s'y
# déplace pas, ne gagne pas d'XP, n'a ni affinité ni part de butin. Son seul rôle est
# de PORTER : capacité = charge_max_of (F*5) × `espece.proprietes.charge_mult`, ce qui
# en fait le premier moyen d'augmenter durablement l'emport d'une expédition. Elle
# reste néanmoins une cible valide pour les monstres (elle est sur la carte).
#
# Plafond SÉPARÉ de celui des compagnons (`character["montures"]` vs
# `character["groupe"]`) : mettre porteur et épée en concurrence forcerait un arbitrage
# absurde. L'appartenance se prouve comme pour un `aventurier:*` — un doc `monture:*`
# n'a pas de `user_id`, seul `acquise_par` + statut fait foi (cf. montures_effectives).
#
# Comme utils/recrutement.py : logique pure, ne sauvegarde JAMAIS (les helpers mutent
# les docs en place, l'endpoint persiste). World-vars lues via le module (jamais
# from-import) — elles sont réglables à chaud depuis /admin.

import random
import time
import uuid

from db.config import get_doc
from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats
from utils.characters import (
	carried_weight, charge_max_of, item_ref_weight, money_to_cuivre, sync_equipment_bonus,
)
from utils.consommables import caracts_avec_buffs

# Les 8 caractéristiques, dans l'ordre de `espece.base_attributes`.
CARACTS = ["V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"]


def now_epoch() -> int:
	return int(time.time())


# ── Le lieu vendeur ──────────────────────────────────────────────────────────────

def lieu_vend_montures(lieu_doc: dict) -> bool:
	"""Une étable. Miroir exact de `recrutement.lieu_recrute` : le OU sur le tag évite
	une migration de données le jour où un autre type de lieu vendra des montures."""
	if not lieu_doc:
		return False
	return (lieu_doc.get("categorie") == "etable"
			or "montures" in (lieu_doc.get("tags") or []))


def especes_offertes(lieu_doc: dict) -> list:
	"""Ids d'espèces vendues ici, dans l'ordre, sans doublon : union des listes
	`montures` portées par les entrées `pnj` du lieu (c'est le tenancier qui tient
	l'écurie, pas le bâtiment — deux PNJ pourraient offrir des lots différents)."""
	vues, out = set(), []
	for entree in (lieu_doc or {}).get("pnj", []) or []:
		for espece_id in entree.get("montures", []) or []:
			if espece_id and espece_id not in vues:
				vues.add(espece_id)
				out.append(espece_id)
	return out


# ── Propriétés d'espèce ──────────────────────────────────────────────────────────

def charge_mult(espece_doc: dict) -> float:
	"""Multiplicateur de capacité de l'espèce. Plancher à 1.0 : une monture ne peut pas
	porter MOINS qu'un humain de même Force."""
	brut = (espece_doc or {}).get("proprietes", {}).get("charge_mult")
	if brut is None:
		return float(character_stats.MONTURE_CHARGE_MULT_DEFAUT)
	try:
		return max(1.0, float(brut))
	except (TypeError, ValueError):
		return float(character_stats.MONTURE_CHARGE_MULT_DEFAUT)


def prix_de(espece_doc: dict) -> int:
	"""Prix d'achat en cuivre."""
	brut = (espece_doc or {}).get("proprietes", {}).get("prix_cuivre")
	if brut is None:
		return int(character_stats.MONTURE_PRIX_DEFAUT)
	try:
		return max(0, int(brut))
	except (TypeError, ValueError):
		return int(character_stats.MONTURE_PRIX_DEFAUT)


def charge_max_monture(monture: dict, get_doc_fn=None) -> int:
	"""Capacité d'emport d'une monture — SOURCE UNIQUE, à utiliser partout où l'on
	comparerait sinon à `charge_max_of`. Le multiplicateur est relu sur le doc espèce
	à chaque appel (jamais dénormalisé sur la monture) : régler `charge_mult` en base
	prend effet immédiatement, comme pour toute donnée d'équilibrage."""
	lire = get_doc_fn or get_doc
	espece = lire(monture.get("espece", "")) if monture.get("espece") else None
	return int(charge_max_of(monture) * charge_mult(espece))


# ── Création ─────────────────────────────────────────────────────────────────────

def _derives_de(monture: dict):
	"""Stats dérivées (miroir de `recrutement._derives_de`, sans vocation : une monture
	n'en a pas, le niveau est donc toujours 0)."""
	equipment = sync_equipment_bonus(monture)
	stats = caracts_avec_buffs(monture)
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	return compute_derived_stats(base, niveau=0, equipment=equipment)


def vitaux_de(monture: dict) -> dict:
	"""État vital pour les payloads (miroir de `recrutement.vitaux_de`)."""
	derived = _derives_de(monture)
	return {
		"currentPV": monture.get("currentPV", derived.pv_max),
		"pv_max": derived.pv_max,
		"currentPM": monture.get("currentPM", derived.pm_max),
		"pm_max": derived.pm_max,
	}


def creer_monture(espece_doc: dict, lieu_doc: dict, acheteur: dict) -> dict | None:
	"""Doc `monture:*` neuf, stats tirées uniformément dans les fourchettes de l'espèce
	(deux chevaux ne se valent pas). None si l'espèce est introuvable.

	Le doc porte le SOUS-ENSEMBLE des champs d'un character qui rend opérants
	compute_derived_stats / carried_weight / build_joueur_snapshot /
	_apply_world_turn_regen. `slots` reste vide : une monture n'équipe rien (mais le
	champ doit exister — `carried_weight` le somme).

	⚠️ Les `tags` de l'espèce ne sont PAS recopiés : plusieurs montures portent `proie`
	ou `predateur`, qui pilotent l'IA de prédation en furtivité. Celle-ci ne scanne que
	les monstres, mais recopier ces tags sur un acteur rangé dans `joueurs` créerait une
	interaction qu'aucun code n'attend."""
	if not espece_doc:
		return None

	attrs = espece_doc.get("base_attributes", {}) or {}
	caract = {}
	for code in CARACTS:
		borne = attrs.get(code) or {}
		lo = int(borne.get("min", 0) or 0)
		hi = int(borne.get("max", lo) or lo)
		caract[code] = random.randint(min(lo, hi), max(lo, hi))

	espece_id = espece_doc.get("_id", "")
	sub = espece_id.split(":", 1)[-1] if ":" in espece_id else espece_id
	monture = {
		"_id": f"monture:{sub}_{uuid.uuid4().hex[:12]}",
		"type": "monture",
		"espece": espece_id,
		"statut": "acquise",
		"acquise_par": acheteur.get("_id"),
		"acquise_at": now_epoch(),
		"giver": (lieu_doc or {}).get("_id"),
		"lieu_parent": (lieu_doc or {}).get("lieu_parent"),
		"nom": espece_doc.get("nom", "Monture"),
		"image": espece_doc.get("image", ""),
		"caracteristiques_current": caract,
		"currentPV": 0,   # posés au max dérivé ci-dessous
		"currentPM": 0,
		"inventaire": [],
		"slots": {},
		"equipment_bonus": {},
		"competences_bonus": {},
		"effets_actifs": [],
		"combats_recompenses": [],   # requis par la finalisation de combat
		"jouable": False,            # ← lu par le combat : ni tour, ni déplacement
	}
	derived = _derives_de(monture)
	monture["currentPV"] = derived.pv_max
	monture["currentPM"] = derived.pm_max
	return monture


# ── Le troupeau du joueur ────────────────────────────────────────────────────────

def plafond_montures() -> int:
	return int(character_stats.MONTURE_GROUPE_MAX)


def montures_effectives(character: dict, get_doc_fn=None) -> list:
	"""Docs des montures ACTIVES du joueur : ids de `character["montures"]` résolus,
	filtrés sur statut `acquise` + acquises PAR CE personnage. Miroir exact de
	`recrutement.groupe_effectif` — un doc `monture:*` n'ayant pas de `user_id`, c'est
	la SEULE preuve d'appartenance. Un id périmé (monture morte) est ignoré."""
	lire = get_doc_fn or get_doc
	out = []
	for mid in character.get("montures", []) or []:
		m = lire(mid)
		if m and m.get("statut") == "acquise" and m.get("acquise_par") == character.get("_id"):
			out.append(m)
	return out


def peut_acquerir(character: dict, espece_doc: dict, get_doc_fn=None) -> tuple[bool, str]:
	"""(ok, raison) : plafond du troupeau, puis fonds. L'ordre compte — annoncer
	« bourse insuffisante » à quelqu'un qui a déjà son quota serait trompeur."""
	if len(montures_effectives(character, get_doc_fn)) >= plafond_montures():
		return False, "Vous ne pouvez pas mener davantage de montures."
	if money_to_cuivre(character) < prix_de(espece_doc):
		return False, "Vous n'avez pas de quoi payer cette monture."
	return True, ""


def acquerir(character: dict, monture: dict) -> tuple[bool, str]:
	"""Attache la monture au personnage. Mute les DEUX docs, sans sauvegarder — l'état
	vit sur le doc de la monture (`acquise_par`), la liste du character n'en est que
	l'index. Le débit de la bourse est fait par l'appelant (marche.debit_character)."""
	if monture.get("statut") == "morte":
		return False, "Cette monture est morte."
	monture["statut"] = "acquise"
	monture["acquise_par"] = character.get("_id")
	monture.setdefault("acquise_at", now_epoch())
	troupeau = character.setdefault("montures", [])
	if monture["_id"] not in troupeau:
		troupeau.append(monture["_id"])
	return True, ""


def relacher(character: dict, monture: dict) -> tuple[bool, str]:
	"""Rend sa liberté à une monture (miroir de `recrutement.congedier`, autorisé
	partout). REFUSE tant qu'elle porte quelque chose : la relâcher chargée ferait
	disparaître le butin sans que rien ne le signale. Mute les deux docs, sans save."""
	if monture.get("inventaire"):
		return False, "Videz son sac avant de la relâcher."
	monture["statut"] = "relachee"
	monture.pop("acquise_par", None)
	character["montures"] = [
		mid for mid in character.get("montures", []) or [] if mid != monture.get("_id")
	]
	return True, ""


def tuer(character: dict, monture: dict) -> list:
	"""Mort définitive : la monture quitte le troupeau et rend sa cargaison, qui sera
	déversée au sol par l'appelant (elle ne doit pas disparaître avec elle). Mute les
	deux docs, sans save. Renvoie les références d'items qu'elle portait."""
	cargaison = list(monture.get("inventaire") or [])
	monture["inventaire"] = []
	monture["statut"] = "morte"
	monture["currentPV"] = 0
	monture.pop("acquise_par", None)
	character["montures"] = [
		mid for mid in character.get("montures", []) or [] if mid != monture.get("_id")
	]
	return cargaison


# ── Portage ──────────────────────────────────────────────────────────────────────

def est_monture(porteur: dict) -> bool:
	return (porteur or {}).get("type") == "monture"


def charge_max_porteur(porteur: dict, get_doc_fn=None) -> int:
	"""Plafond de charge de N'IMPORTE QUEL porteur du groupe — chokepoint qui aiguille
	entre la dérivée standard et la capacité démultipliée d'une monture. À utiliser
	partout où le porteur peut être l'un ou l'autre (transferts, payloads)."""
	if est_monture(porteur):
		return charge_max_monture(porteur, get_doc_fn)
	return charge_max_of(porteur)

# Le test « cette référence rentre-t-elle ? » reste `recrutement.peut_porter`, qui
# délègue ici pour le plafond : un seul endroit décide de la capacité, un seul autre
# décide de l'admission.

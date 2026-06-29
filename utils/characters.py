from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from db.config import get_doc, save_doc, find_docs
from models import character_stats
from models.character_stats import compute_character_level, EquipmentBonus, BaseStats, compute_derived_stats

def get_user_characters(current_user: dict = Body(...)):
	if not current_user:
		return None
	
	db_user = get_doc(current_user["_id"])
	if not db_user:
		return None
	
	# characters :
	selector = {
		"type": "character",
		"user_id": current_user["_id"]
	}
	characters = find_docs(selector)
	for c in characters:
		c["niveau"] = compute_character_level(c.get("xp_total", 0))
	return characters
	
def get_selected_character(current_user: dict = Body(...)):
	if not current_user:
		return None
	user_id = current_user["_id"]
	db_user = get_doc(user_id)
	if not db_user:
		return None
	
	#selected character for current user
	character_id = db_user["selected_character"]
	character = get_doc(character_id)
	
	if not character or not character["user_id"] == user_id:
		return None

	return character

# ── Références d'items (inventaire / sol / slots / butin) ──────────────────────
# Une référence d'item stockée est SOIT une chaîne "item:xxx" (legacy → poids = min
# de l'item), SOIT un objet {"item": "item:xxx", "poids": <nombre>} portant le poids
# propre à l'instance (tiré au loot). Le champ `poids` d'un doc item peut lui-même être
# un nombre fixe OU un tableau [min, max].

def item_ref_id(ref) -> str | None:
	"""ID de l'item depuis une référence (chaîne legacy ou objet {item, poids})."""
	if isinstance(ref, dict):
		return ref.get("item")
	return ref


def poids_bounds(item: dict) -> tuple[float, float]:
	"""(min, max) du poids d'un doc item ; `poids` peut être [min, max] ou un nombre."""
	p = (item or {}).get("poids", 0)
	if isinstance(p, (list, tuple)) and len(p) >= 2:
		return float(p[0] or 0), float(p[1] or 0)
	val = float(p or 0)
	return val, val


def item_ref_weight(ref) -> float:
	"""Poids effectif d'une référence : poids stocké si {item, poids}, sinon min de l'item."""
	if isinstance(ref, dict) and ref.get("poids") is not None:
		return float(ref.get("poids") or 0)
	item = get_doc(item_ref_id(ref)) if item_ref_id(ref) else None
	return poids_bounds(item)[0]


def resolve_item_ref(ref):
	"""Référence → doc item complet, avec `poids` écrasé par le poids effectif de
	l'instance (nombre) et `_id`/`item` conservés. None si l'item n'existe plus."""
	item_id = item_ref_id(ref)
	if not item_id:
		return None
	doc = get_doc(item_id)
	if not doc:
		return None
	doc = dict(doc)
	doc["poids"] = item_ref_weight(ref)
	doc["item"] = item_id
	return doc


def recompute_equipment_bonus(slots: dict) -> EquipmentBonus:
	"""Cumule les bonus des items équipés en relisant chaque doc depuis CouchDB.

	`slots` = dict {slot_name: ref|None} où ref est une chaîne id OU un objet
	{item, poids}. Les valeurs sont relues à chaque appel (`get_doc`) pour que toute
	modif d'un item en base soit reflétée sans ré-équiper. Partagé par /play (fiche),
	le snapshot de combat et equip/unequip — jamais servi depuis un cache.
	"""
	bonus = EquipmentBonus()
	for ref in slots.values():
		item_id = item_ref_id(ref)
		if not item_id:
			continue
		item = get_doc(item_id)
		if not item:
			continue
		bonus.pa           += item.get("bonus_pa", 0)
		bonus.pv           += item.get("bonus_pv", 0)
		bonus.pm           += item.get("bonus_pm", 0)
		bonus.malus_depl   += item.get("bonus_malus_depl", 0)
		bonus.cc_bonus     += item.get("bonus_cc", 0)
		bonus.cd_bonus     += item.get("bonus_cd", 0)
		bonus.degats_bonus += item.get("bonus_degats", 0)
		dice = item.get("bonus_degats_dice", "")
		if dice:
			bonus.degats_dice = f"{bonus.degats_dice}+{dice}" if bonus.degats_dice else dice
		bonus.initiative   += item.get("bonus_initiative", 0)
	return bonus


def carried_weight(character: dict) -> float:
	"""Poids total porté = somme des poids effectifs des références de l'inventaire ET
	des items équipés (slots). Une référence chaîne (legacy) vaut le min de l'item ;
	une référence {item, poids} vaut son poids d'instance.

	Sert à la contrainte de charge (charge_max) et au malus de déplacement en combat.
	"""
	refs = list(character.get("inventaire", []))
	refs += [v for v in (character.get("slots") or {}).values() if v]
	return sum(item_ref_weight(r) for r in refs)


def charge_max_of(character: dict) -> int:
	"""Charge maximale portable du personnage (kg).

	Dérivée autoritative `F*5` via `compute_derived_stats` (indépendante du niveau et
	de l'équipement). Sert à la contrainte de charge en exploration comme en combat.
	"""
	stats = character.get("caracteristiques_current", {})
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	return compute_derived_stats(base, niveau=0).charge_max


def restriction_satisfaite(restriction: dict | None, caracs: dict) -> tuple[bool, dict]:
	"""Vérifie les minimums de caractéristiques d'une arme (champ item `restriction`).

	`restriction` = {caract: min, …} (ex. {"F": 30, "Ag": 25}). Sémantique **ET** :
	toutes les caract listées doivent atteindre leur minimum. `caracs` = dict des
	caractéristiques courantes du personnage (`caracteristiques_current`).

	Retourne (ok, manque) où `manque` = {caract: min} des entrées non satisfaites
	(vide si ok). Une restriction absente/vide est toujours satisfaite. Helper pur
	(sans DB) → partagé par l'équipement et testable.
	"""
	if not restriction or not isinstance(restriction, dict):
		return True, {}
	manque = {}
	for caract, mini in restriction.items():
		try:
			seuil = int(mini)
		except (TypeError, ValueError):
			continue
		if int((caracs or {}).get(caract, 0) or 0) < seuil:
			manque[caract] = seuil
	return (not manque), manque


def grant_xp(character: dict, amount: int) -> dict:
	"""Ajoute `amount` XP au personnage et attribue les points de montée de niveau.

	Mute `character` en place (`xp_total`, `attribute_points`) mais NE SAUVEGARDE PAS :
	l'appelant persiste le personnage avec ses autres modifications (régén, position,
	PV de sortie de combat…). Règle : +N points par niveau gagné (passage au niveau N
	→ +N points), partagée entre la découverte de lieux et les récompenses de combat.

	Retourne un récap : {xp_gain, niveau_avant, niveau_apres, niveau_up, points_gagnes}.
	"""
	amount = max(0, int(amount or 0))
	xp_before = character.get("xp_total", 0)
	niveau_avant = compute_character_level(xp_before)
	character["xp_total"] = xp_before + amount
	niveau_apres = compute_character_level(character["xp_total"])
	points_gagnes = sum(range(niveau_avant + 1, niveau_apres + 1))
	if points_gagnes:
		character["attribute_points"] = character.get("attribute_points", 0) + points_gagnes
	return {
		"xp_gain": amount,
		"niveau_avant": niveau_avant,
		"niveau_apres": niveau_apres,
		"niveau_up": niveau_apres > niveau_avant,
		"points_gagnes": points_gagnes,
	}


# ── Monnaie (Or / Argent / Cuivre) ─────────────────────────────────────────────
# Trois paliers ; le cuivre est la base. 1 or = 100 argent = 10 000 cuivre.
# Le personnage stocke or/argent/cuivre comme entiers (absents = 0).

CUIVRE_PAR_ARGENT = 100
ARGENT_PAR_OR     = 100
CUIVRE_PAR_OR     = CUIVRE_PAR_ARGENT * ARGENT_PAR_OR   # 10 000


def money_to_cuivre(character: dict) -> int:
	"""Bourse du personnage convertie en cuivre (base)."""
	return (
		int(character.get("or", 0) or 0) * CUIVRE_PAR_OR
		+ int(character.get("argent", 0) or 0) * CUIVRE_PAR_ARGENT
		+ int(character.get("cuivre", 0) or 0)
	)


def cuivre_to_purse(total_cuivre: int) -> dict:
	"""Total en cuivre → bourse normalisée {or, argent, cuivre}."""
	total = max(0, int(total_cuivre or 0))
	o, reste = divmod(total, CUIVRE_PAR_OR)
	a, c = divmod(reste, CUIVRE_PAR_ARGENT)
	return {"or": o, "argent": a, "cuivre": c}


def credit_character(character: dict, cuivre: int) -> dict:
	"""Ajoute `cuivre` à la bourse du personnage et la mute en place (or/argent/cuivre
	normalisés). NE SAUVEGARDE PAS (l'appelant persiste, comme `grant_xp`). Retourne
	la bourse mise à jour."""
	purse = cuivre_to_purse(money_to_cuivre(character) + max(0, int(cuivre or 0)))
	character["or"]     = purse["or"]
	character["argent"] = purse["argent"]
	character["cuivre"] = purse["cuivre"]
	return purse


def valeur_entry_to_cuivre(entry) -> int:
	"""Une entrée de prix {or, ag, cu} → cuivre. Robuste aux clés absentes."""
	if not isinstance(entry, dict):
		return 0
	return (
		int(entry.get("or", 0) or 0) * CUIVRE_PAR_OR
		+ int(entry.get("ag", 0) or 0) * CUIVRE_PAR_ARGENT
		+ int(entry.get("cu", 0) or 0)
	)


# ── Éligibilité & prix de vente marchand ───────────────────────────────────────

def item_sous_categorie(item_doc: dict) -> str | None:
	"""Sous-catégorie marchande d'un item. Explicite via `sous_categorie` (ex.
	« carcasse » sur les dépouilles), sinon repli sur la `categorie` de l'item.
	None si l'item n'existe pas. Un `sous_categorie` vide ("") est ignoré (repli)."""
	if not item_doc:
		return None
	return item_doc.get("sous_categorie") or item_doc.get("categorie")


def lieu_buys(lieu_doc: dict, item_doc: dict) -> bool:
	"""True si le marchand du lieu achète cet item (sous-catégorie ∈ liste des règles
	du monde pour la catégorie du lieu)."""
	sc = item_sous_categorie(item_doc)
	if not sc:
		return False
	achetees = character_stats.ACHAT_SOUS_CAT_PAR_LIEU.get((lieu_doc or {}).get("categorie"), [])
	return sc in achetees


def item_sale_price_cuivre(item_doc: dict, ref) -> int:
	"""Prix de vente proposé (en cuivre). Si l'item porte un champ `valeur`, on propose
	le MIN (laisse la place au marchandage futur vers le max) ; sinon prix dérivé
	`poids × MULT_RARETE × PRIX_DERIVE_BASE`, minimum 1."""
	valeur = (item_doc or {}).get("valeur")
	if valeur is not None:
		entry = valeur[0] if isinstance(valeur, (list, tuple)) and valeur else valeur
		prix = valeur_entry_to_cuivre(entry)
		if prix > 0:
			return prix
	mult = character_stats.MULT_RARETE.get((item_doc or {}).get("rarete"), 1)
	poids = item_ref_weight(ref)
	return max(1, round(poids * mult * character_stats.PRIX_DERIVE_BASE))
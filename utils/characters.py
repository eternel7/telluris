from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from db.config import get_doc, save_doc, find_docs
from models import character_stats
from models.character_stats import compute_character_level, EquipmentBonus, BaseStats, compute_derived_stats, normalize_dice

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

	# Réparation paresseuse de l'agrégat des passives : import tardif, le module competences
	# dépend (via consommables) de celui-ci. Ne coûte des lectures que pour un perso périmé,
	# et une seule fois — on persiste la réparation en best-effort.
	from utils.competences import competences_bonus_perime, recompute_competences_bonus
	if competences_bonus_perime(character):
		recompute_competences_bonus(character, get_doc)
		save_doc(character)

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


def item_ref_lieu(ref) -> str | None:
	"""Lieu d'ÉMISSION de l'instance : `lieu_parent` porté par la RÉFÉRENCE, jamais par le doc.
	Une carte de guilde est un objet GÉNÉRIQUE (`item:carte_aventurier`, un seul doc pour tout
	le monde) — c'est l'exemplaire remis qui sait de quelle guilde il vient."""
	if isinstance(ref, dict):
		return ref.get("lieu_parent")
	return None


def item_label(nom: str, lieu_doc: dict | None) -> str:
	"""« Carte d'aventurier (Auxerre) » — le nom du doc, suffixé du lieu de l'instance."""
	label = (lieu_doc or {}).get("label") or (lieu_doc or {}).get("nom")
	return f"{nom} ({label})" if label else nom


def resolve_item_ref(ref):
	"""Référence → doc item complet, avec `poids` écrasé par le poids effectif de
	l'instance (nombre) et `_id`/`item` conservés. None si l'item n'existe plus.

	Chokepoint d'affichage : tout ce que voit le client (sac, sol, paperdoll, fiche objet,
	marché, combat, butin) passe par ici et n'affiche que `nom` — c'est donc le seul endroit
	où le lieu d'émission d'une instance devient visible."""
	item_id = item_ref_id(ref)
	if not item_id:
		return None
	doc = get_doc(item_id)
	if not doc:
		return None
	doc = dict(doc)
	doc["poids"] = item_ref_weight(ref)
	doc["item"] = item_id
	# Un grimoire n'a pas d'école propre : elle vit sur les sorts qu'il enseigne. Résolue
	# ICI et pas côté client, qui ne connaît que les sorts qu'il peut apprendre — soit
	# précisément PAS ceux d'une école qui lui est fermée, là où l'information est la plus
	# utile. Import tardif : utils.sorts dépend de ce module. Ne coûte des lectures qu'aux
	# grimoires, les autres items ne paient que le test de sous-catégorie.
	from utils.sorts import est_grimoire, ecoles_de_grimoire
	if est_grimoire(doc):
		doc["magies"] = ecoles_de_grimoire(doc, get_doc, get_doc("rules:vocations"))
	if (lieu_id := item_ref_lieu(ref)):
		doc["lieu_parent"] = lieu_id
		doc["nom"] = item_label(doc.get("nom") or item_id, get_doc(lieu_id))
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
		# `bonus_degats_dice` porte le NOMBRE DE FACES en base (6 = 1D6) — normalisé ici,
		# sinon il serait concaténé en "+6", c.-à-d. lu comme un modificateur plat.
		dice = normalize_dice(item.get("bonus_degats_dice"))
		if dice:
			bonus.degats_dice = f"{bonus.degats_dice}+{dice}" if bonus.degats_dice else dice
		bonus.initiative   += item.get("bonus_initiative", 0)

		# Buffs de caractéristiques portés par l'objet : le champ `bonus` = {caract: delta},
		# PLUS `bonus_malus_depl`, qui est lui aussi un delta sur V (données : -1, -2 pour les
		# armures lourdes) et se cumule donc naturellement avec un éventuel `bonus.V`.
		buffs = {}
		for caract, delta in (item.get("bonus") or {}).items():
			try:
				delta = int(delta)
			except (TypeError, ValueError):
				continue
			if delta:
				buffs[str(caract)] = buffs.get(str(caract), 0) + delta
		try:
			malus_v = int(item.get("bonus_malus_depl", 0) or 0)
		except (TypeError, ValueError):
			malus_v = 0
		if malus_v:
			buffs["V"] = buffs.get("V", 0) + malus_v
		if buffs:
			for caract, delta in buffs.items():
				bonus.buffs[caract] = bonus.buffs.get(caract, 0) + delta
			bonus.buffs_sources.append({
				"nom":   item.get("nom", item_id),
				"icon":  item.get("icon", "⚔"),
				"buffs": buffs,
			})
	return bonus


def sync_equipment_bonus(character: dict) -> EquipmentBonus:
	"""Recalcule le bonus d'équipement depuis les slots ET le dénormalise dans
	character["equipment_bonus"] (mute en place, NE SAUVEGARDE PAS).

	À appeler AVANT tout caracts_avec_buffs / compute_derived_stats : c'est ce champ
	dénormalisé que lit utils/consommables._sources_de_buffs pour replier les buffs de
	caractéristiques de l'équipement. Miroir de competences.recompute_competences_bonus.
	"""
	bonus = recompute_equipment_bonus(character.get("slots", {}))
	character["equipment_bonus"] = bonus.model_dump()
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


_MAINS = ("main_droite", "main_gauche")


def autre_main(slot: str) -> str:
	"""L'autre emplacement de main, pour un slot qui EST une main (appelant garde)."""
	return "main_gauche" if slot == "main_droite" else "main_droite"


def main_occupee_par_deux_mains(slots: dict, resolve_item_fn, slot: str) -> dict | None:
	"""Doc de l'arme à deux mains qui bloque `slot` (portée par l'AUTRE main), ou None
	si `slot` n'est pas une main, l'autre main est vide, ou son occupant n'est pas
	`deux_mains`. `resolve_item_fn(ref) -> dict|None` résout une référence en doc item
	(DB injectée par l'appelant : `lambda ref: get_doc(item_ref_id(ref))`). Helper pur
	(sans DB) → partagé par l'équipement et testable, même précédent que
	`restriction_satisfaite`."""
	if slot not in _MAINS:
		return None
	autre_ref = slots.get(autre_main(slot))
	if not autre_ref:
		return None
	item = resolve_item_fn(autre_ref)
	return item if item and item.get("deux_mains") else None


def liberer_pour_deux_mains(slots: dict, item: dict, slot: str) -> str | None:
	"""Si `item` est une arme à deux mains posée dans `slot`, l'AUTRE main à libérer en
	plus (son éventuel occupant retourne au sac) ; None sinon."""
	if slot not in _MAINS or not (item or {}).get("deux_mains"):
		return None
	return autre_main(slot)


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
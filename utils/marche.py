# utils/marche.py
# Logique pure du marché : marchandage (Cha vs Cha), fourchette de prix, dépeçage des
# carcasses par espèce, et conversion de ce qu'un lieu achète en stock vendable via les
# recettes (`recette:*`). Les endpoints (routers/user.py) persistent ; ces helpers ne
# sauvegardent jamais (ils mutent les docs en place, comme grant_xp/credit_character).

import os
import random
import time
from collections import Counter

from db.config import get_doc, find_docs
from models import character_stats
from utils.characters import (
	resolve_item_ref,
	money_to_cuivre, cuivre_to_purse,
	item_sous_categorie, item_sale_price_cuivre, valeur_entry_to_cuivre,
)


def _clamp(x, lo, hi):
	return max(lo, min(hi, x))


# Champs du doc item utiles à la fiche/comparaison côté client (mêmes clés que la fiche
# de l'inventaire perso). Attachés aux lignes vente/achat du marchand pour qu'un clic
# affiche la même fiche (`nom`/`icon`/`poids` sont déjà portés par la ligne, poids =
# instance pour la vente → on ne les réécrase pas ici).
_FICHE_ITEM_KEYS = (
	"categorie", "sous_categorie", "rarete", "tags", "portee", "restriction", "slots", "effets",
	"bonus",
	"bonus_pa", "bonus_pv", "bonus_pm", "bonus_cc", "bonus_cd",
	"bonus_degats", "bonus_degats_dice", "bonus_initiative", "bonus_malus_depl",
)


def fiche_item_fields(item: dict) -> dict:
	"""Sous-ensemble des champs d'un doc item nécessaires à la fiche/comparaison client."""
	return {k: item[k] for k in _FICHE_ITEM_KEYS if k in (item or {})}


# ── Monnaie ─────────────────────────────────────────────────────────────────────

def debit_character(character: dict, cuivre: int) -> dict | None:
	"""Retire `cuivre` de la bourse du personnage (mute en place, NE SAUVEGARDE PAS).
	Renvoie la bourse mise à jour, ou None si les fonds sont insuffisants."""
	cout = max(0, int(cuivre or 0))
	total = money_to_cuivre(character)
	if cout > total:
		return None
	purse = cuivre_to_purse(total - cout)
	character["or"]     = purse["or"]
	character["argent"] = purse["argent"]
	character["cuivre"] = purse["cuivre"]
	return purse


# ── Marchandage ─────────────────────────────────────────────────────────────────

def merchant_cha(lieu_doc: dict) -> int:
	"""Cha du marchand : champ `cha` du lieu s'il est posé, sinon le défaut par
	catégorie de lieu (`CHA_MARCHAND_PAR_CATEGORIE`), sinon le global `CHA_MARCHAND`."""
	lieu_doc = lieu_doc or {}
	if lieu_doc.get("cha") is not None:
		return int(lieu_doc.get("cha") or 0)
	cat = lieu_doc.get("categorie")
	return int(character_stats.CHA_MARCHAND_PAR_CATEGORIE.get(cat, character_stats.CHA_MARCHAND))


def prix_range_cuivre(item_doc: dict, ref=None) -> tuple[int, int]:
	"""(min, max) en cuivre. Si `valeur` porte ≥2 bornes → min/max de ces bornes ;
	sinon min = **coût de revient** (`cout_production_cuivre` : dérivé poids/rareté pour les
	matières brutes, propagé via les recettes × MARGE_TRANSFO pour les produits transformés)
	et max = min × PRIX_MAX_FACTEUR."""
	valeur = (item_doc or {}).get("valeur")
	if isinstance(valeur, (list, tuple)) and len(valeur) >= 2:
		bornes = [valeur_entry_to_cuivre(e) for e in valeur]
		bornes = [b for b in bornes if b > 0]
		if len(bornes) >= 2:
			return min(bornes), max(bornes)
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	pmin = cout_production_cuivre(item_id, item_doc, ref)
	pmax = max(pmin, round(pmin * character_stats.PRIX_MAX_FACTEUR))
	return pmin, pmax


# ── Coût de revient propagé (chaînes de transformation) ───────────────────────────
# Le prix d'un produit reflète le coût de ses ingrédients (récursif via les recettes)
# × MARGE_TRANSFO par étape → les objets issus de transformations successives sont bien
# plus chers que les matières brutes. Caches process-lifetime, vidés par reset_prix_cache().
_recipe_map: dict | None = None   # objet_final_item_id → [recettes le produisant]
_cout_memo: dict[str, int] = {}
_marche_map: dict | None = None   # {"besoins": {cat: set}, "feuilles": set} dérivé des recettes


def reset_prix_cache() -> None:
	"""Vide les caches de coût de revient (à appeler quand recettes/items/MARGE changent)."""
	global _recipe_map, _marche_map
	_recipe_map = None
	_marche_map = None
	_cout_memo.clear()


def _get_recipe_map() -> dict:
	"""Construit (une fois) la table objet_final_item_id → liste de recettes le produisant."""
	global _recipe_map
	if _recipe_map is None:
		m: dict[str, list] = {}
		for r in (find_docs({"type": "recette"}) or []):
			oid = objet_final_item_id(r.get("objet_final", ""))
			if oid:
				m.setdefault(oid, []).append(r)
		_recipe_map = m
	return _recipe_map


# ── Besoins marchands & feuilles d'appro (dérivés des recettes) ───────────────────
# Les recettes (`recette:*`, champ `lieu_categorie` + matières d'entrée) sont la source
# unique de vérité : ce qu'un métier achète au joueur = ce que ses recettes consomment ;
# les matières « feuilles » à auto-approvisionner = les entrées qu'aucune recette ne
# produit (hors `carcasse`, qui est du loot joueur). Remplace les ex-world-vars
# ACHAT_SOUS_CAT_PAR_LIEU et APPRO_MATIERES_PAR_LIEU. Cache vidé par reset_prix_cache().

def _get_marche_map() -> dict:
	"""Construit (une fois) depuis toutes les recettes :
	{"besoins": {lieu_categorie: set(clés matières consommées — sous_cat ou item id)},
	 "produits": {lieu_categorie: set(item_id produits)},
	 "feuilles": set(clés matières sans recette productrice, hors carcasse)}."""
	global _marche_map
	if _marche_map is None:
		besoins: dict[str, set] = {}
		produits: dict[str, set] = {}
		outputs: set = set()
		inputs_all: set = set()
		for r in (find_docs({"type": "recette"}) or []):
			cat = r.get("lieu_categorie")
			outputs.add(r.get("objet_final"))
			if cat:
				produits.setdefault(cat, set()).add(objet_final_item_id(r.get("objet_final", "")))
			for (cle, _qm) in recette_matieres(r):
				if not cle:
					continue
				inputs_all.add(cle)
				if cat:
					besoins.setdefault(cat, set()).add(cle)
		# Une clé item-ref est « produite » si une recette a cet item pour objet_final.
		outputs_ids = {objet_final_item_id(o) for o in outputs if o}
		feuilles = {k for k in inputs_all
					if k not in outputs and k not in outputs_ids} - {"carcasse"}
		_marche_map = {"besoins": besoins, "produits": produits, "feuilles": feuilles}
	return _marche_map


def besoins_categorie(categorie: str) -> list[str]:
	"""Clés matières consommées par les recettes de cette catégorie de lieu (sous-catégories
	et/ou ids d'items référencés directement — ce que le marchand achète au joueur). Liste
	triée, vide si aucune recette."""
	if not categorie:
		return []
	return sorted(_get_marche_map()["besoins"].get(categorie, set()))


def appro_leaves_categorie(categorie: str) -> list[str]:
	"""Matières « feuilles » (sans recette productrice, hors carcasse) consommées par les
	recettes de cette catégorie → à auto-approvisionner (ex. métaux pour l'armurerie)."""
	if not categorie:
		return []
	mm = _get_marche_map()
	return sorted(mm["besoins"].get(categorie, set()) & mm["feuilles"])


def produits_categorie(categorie: str) -> set:
	"""Item_ids des biens produits par les recettes de cette catégorie de lieu."""
	if not categorie:
		return set()
	return _get_marche_map()["produits"].get(categorie, set())


def lieu_produit(lieu_doc: dict, item_doc: dict) -> bool:
	"""True si l'item est un bien que ce lieu **produit** (donc rachetable au joueur)."""
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	if not item_id:
		return False
	return item_id in produits_categorie((lieu_doc or {}).get("categorie"))


def lieu_buys(lieu_doc: dict, item_doc: dict) -> bool:
	"""True si le marchand du lieu achète cet item : son id OU sa sous-catégorie ∈ besoins
	(intrants des recettes, item-refs compris) **OU** c'est un bien que le lieu produit
	(rachat à moindre coût)."""
	if lieu_produit(lieu_doc, item_doc):
		return True
	besoins = besoins_categorie((lieu_doc or {}).get("categorie"))
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	if item_id and item_id in besoins:
		return True
	sc = item_sous_categorie(item_doc)
	return bool(sc) and sc in besoins


def cle_matiere_lieu(categorie: str, item_doc: dict) -> str:
	"""Clé sous laquelle cet item entre dans le `stock_matieres` du lieu : son **id** si une
	recette de la catégorie le référence directement (le plus précis gagne, comme
	`stock_cible_pour`), sinon sa sous-catégorie. Limitation assumée : si un même lieu a une
	recette item-ref ET une recette générique sur la même sous-catégorie, l'item référencé
	alimente le bucket spécifique (pas le générique)."""
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	if item_id and item_id in besoins_categorie(categorie):
		return item_id
	return item_sous_categorie(item_doc)


def params_vente_lieu(lieu_doc: dict, item_doc: dict, item_id: str, ref=None) -> tuple[int, int, int]:
	"""Paramètres du côté **vente** (joueur→lieu) : `(pmin, pmax, stock)` à passer à
	`prix_marche(..., "vente", stock, cible)`. Source unique pour `_marchand_vendables`,
	`sell_item` et `marchander` (sens vente) → prix affiché/appliqué/marchandé cohérents.
	- **Rachat** d'un bien produit par le lieu (`lieu_produit`) : bande plafonnée au coût de
	  revient → `(round(pmin × RACHAT_FACTEUR), pmin)`, stock = qty en rayon (`stock_vente`).
	  Garantit rachat ≤ pmin ≤ prix de vente (le prix d'achat joueur est toujours ≥ pmin).
	- **Intrant brut** (sinon) : fourchette normale `(pmin, pmax)`, stock = `stock_matieres[clé]`
	  (clé = item id si une recette du lieu référence cet item, sinon sous-catégorie)."""
	pmin, pmax = prix_range_cuivre(item_doc, ref if ref is not None else item_id)
	if lieu_produit(lieu_doc, item_doc):
		pmin_r = max(1, int(round(pmin * float(character_stats.RACHAT_FACTEUR))))
		stock = next((int(e.get("qty", 0)) for e in (lieu_doc or {}).get("stock_vente", [])
					  if e.get("item_id") == item_id), 0)
		return pmin_r, pmin, stock
	cle = cle_matiere_lieu((lieu_doc or {}).get("categorie"), item_doc)
	stock = int(((lieu_doc or {}).get("stock_matieres", {}) or {}).get(cle, 0))
	return pmin, pmax, stock


def cout_production_cuivre(item_id: str, item_doc: dict | None = None, ref=None, _seen=None) -> int:
	"""Coût de revient d'un objet (cuivre). Un `valeur` explicite est autoritaire (pas de
	propagation). Sinon : pour un objet produit par une/des recette(s), coût des ingrédients
	(récursif) × quantite_matiere / quantite_produite × MARGE_TRANSFO (max sur les recettes),
	borné au minimum par le coût intrinsèque (poids/rareté). Feuilles (matières brutes / sans
	recette) = `item_sale_price_cuivre`."""
	if not item_id:
		return item_sale_price_cuivre(item_doc or {}, ref)
	if item_id in _cout_memo:
		return _cout_memo[item_id]
	doc = item_doc if (item_doc is not None and (item_doc.get("_id") == item_id or item_doc.get("item") == item_id)) else (get_doc(item_id) or {})
	# `valeur` explicite → prix maîtrisé à la main, pas de propagation.
	if doc.get("valeur") is not None:
		v = item_sale_price_cuivre(doc, ref if ref is not None else item_id)
		_cout_memo[item_id] = v
		return v
	base = item_sale_price_cuivre(doc, ref if ref is not None else item_id)
	recs = _get_recipe_map().get(item_id)
	if not recs or (_seen and item_id in _seen):
		# Pas de recette (matière brute) : NE PAS mémoïser — le prix peut dépendre du poids
		# d'instance (items à poids [min,max] comme les carcasses).
		return base
	seen = (_seen or set()) | {item_id}
	best = base
	for r in recs:
		# Coût de revient = somme des ingrédients (multi-entrées) × quantité, / quantité produite.
		ci = 0
		for (cle, qm) in recette_matieres(r):
			ci += cout_production_cuivre(matiere_item_id(cle), None, None, seen) * qm
		qp = max(1, int(r.get("quantite_produite", 1) or 1))
		best = max(best, int(round(ci / qp * character_stats.MARGE_TRANSFO)))
	best = max(1, best)
	_cout_memo[item_id] = best
	return best


def marchander(pmin: int, pmax: int, cha_joueur: int, cha_marchand: int, sens: str,
			   seuil_bonus: int = 0) -> dict:
	"""Jet opposé Cha joueur vs Cha marchand, prix interpolé entre pmin et pmax.

	seuil = clamp(50 + Cha_j − Cha_m + seuil_bonus, 5, 95) ; roll d100 ; marge = seuil − roll ;
	t = clamp(0.5 + marge/100, 0, 1) (t haut = favorable au joueur). `seuil_bonus` porte le poids
	de la relation au lieu ((relation−50)·RELATION_SEUIL_COEFF).
	- sens "vente" (le joueur vend, veut le max) : prix = pmin + (pmax−pmin)·t
	- sens "achat" (le joueur achète, veut le min) : prix = pmin + (pmax−pmin)·(1−t)
	"""
	pmin, pmax = int(pmin), int(max(pmin, pmax))
	seuil = _clamp(50 + int(cha_joueur or 0) - int(cha_marchand or 0) + int(seuil_bonus or 0), 5, 95)
	roll = random.randint(1, 100)
	t = _clamp(0.5 + (seuil - roll) / 100.0, 0.0, 1.0)
	frac = t if sens == "vente" else (1.0 - t)
	prix = int(round(pmin + (pmax - pmin) * frac))
	return {
		"prix": max(1, prix),
		"frac": frac,   # position dans la fourchette → rejouée contre le poids de chaque instance
		"roll": roll,
		"seuil": seuil,
		"succes": roll <= seuil,
		"min": pmin,
		"max": pmax,
	}


# ── Relation marchand (prix de base pondéré + persistance) ───────────────────────
# La relation perso×lieu (0–100, neutre 50) pondère le prix de base SANS aléa, et le
# seuil du marchandage. Un seul coeff (RELATION_SEUIL_COEFF) règle les deux : écart au
# neutre d = relation−50 ; le prix de base utilise frac = clamp(0.5 + d·coeff/100, 0, 1)
# (50 → médian), le marchandage ajoute d·coeff au seuil.

def _relation_seuil_bonus(relation: int) -> int:
	"""Bonus de seuil de marchandage apporté par la relation ((relation−50)·coeff)."""
	d = int(relation or 0) - 50
	return int(round(d * character_stats.RELATION_SEUIL_COEFF))


def prix_base_cuivre(pmin: int, pmax: int, relation: int, sens: str) -> int:
	"""Prix de base (sans marchander) pondéré par la relation, sans aléa. À relation 50
	le prix est médian ; au-dessus il tend vers le favorable au joueur, en dessous vers
	le défavorable. `sens` ∈ "vente" (le joueur veut le max) / "achat" (veut le min)."""
	pmin, pmax = int(pmin), int(max(pmin, pmax))
	d = int(relation or 0) - 50
	frac = _clamp(0.5 + d * character_stats.RELATION_SEUIL_COEFF / 100.0, 0.0, 1.0)
	if sens == "vente":
		prix = pmin + (pmax - pmin) * frac
	else:  # achat
		prix = pmax - (pmax - pmin) * frac
	return max(1, int(round(prix)))


def prix_negocie(relation_doc: dict, item_id: str, sens: str, pmin: int, pmax: int):
	"""Prix négocié persistant pour (item, sens) résolu en cuivre contre la fourchette de
	CETTE instance, sinon None.

	Le marchandage persiste une **fraction** de la fourchette (`{"frac": t}`) et non un
	montant fixe : le prix est recalculé `pmin + (pmax−pmin)·frac` contre `pmin`/`pmax`,
	qui dépendent du poids de l'objet → deux exemplaires de même item_id mais de poids
	différents gardent des prix distincts après marchandage (le facteur poids reste
	appliqué). Rétro-compat : un montant scalaire stocké (ancien format) est renvoyé tel
	quel (montant absolu)."""
	pn = (relation_doc or {}).get("prix_negocies") or {}
	val = (pn.get(item_id) or {}).get(sens)
	if isinstance(val, dict):
		frac = val.get("frac")
		if isinstance(frac, (int, float)) and not isinstance(frac, bool):
			pmin, pmax = int(pmin), int(max(pmin, pmax))
			return max(1, int(round(pmin + (pmax - pmin) * float(frac))))
		return None
	if isinstance(val, (int, float)) and not isinstance(val, bool):
		return max(1, int(val))  # legacy : montant absolu persisté avant le passage en fraction
	return None


def prix_courant(relation_doc: dict, item_id: str, pmin: int, pmax: int, sens: str) -> int:
	"""Prix appliqué à une transaction : prix négocié stocké s'il existe, sinon prix de
	base pondéré relation. Source unique de vérité du prix (listes + vente/achat)."""
	neg = prix_negocie(relation_doc, item_id, sens, pmin, pmax)
	if neg is not None:
		return max(1, neg)
	return prix_base_cuivre(pmin, pmax, relation_value(relation_doc), sens)


# ── Prix offre/demande (stock cible) ──────────────────────────────────────────────

def stock_cible_pour(lieu_doc: dict, item: dict) -> int:
	"""Stock cible d'un bien chez ce lieu, par spécificité décroissante :
	`stock_cible.item[item_id]` → `stock_cible.sous_categorie[sous_cat]` →
	`stock_cible.categorie[cat]` → world-var `STOCK_CIBLE_DEFAUT`. `item` = doc résolu."""
	cibles = (lieu_doc or {}).get("stock_cible") or {}
	item = item or {}
	item_id = item.get("item") or item.get("_id")
	niveaux = (
		("item", item_id),
		("sous_categorie", item_sous_categorie(item)),
		("categorie", item.get("categorie")),
	)
	for niveau, cle in niveaux:
		table = cibles.get(niveau) or {}
		if cle and cle in table:
			try:
				return max(1, int(table[cle]))
			except (TypeError, ValueError):
				pass
	return max(1, int(character_stats.STOCK_CIBLE_DEFAUT))


def facteur_stock(stock: int, cible: int) -> float:
	"""Facteur prix selon l'écart stock/cible, borné ±PRIX_AMPLITUDE_STOCK.
	Stock élevé → < 1 (moins cher / moins bien payé) ; stock bas → > 1. Même sens pour
	l'achat (le marchand brade son surplus) et la vente (il paie moins une matière dont il déborde)."""
	cible = max(1, int(cible or 0))
	ampl = float(character_stats.PRIX_AMPLITUDE_STOCK)
	return _clamp(1.0 - ampl * (int(stock or 0) - cible) / cible, 1.0 - ampl, 1.0 + ampl)


def prix_marche(relation_doc: dict, item_id: str, pmin: int, pmax: int, sens: str,
				stock: int, cible: int) -> int:
	"""Prix « marché » : `prix_courant` (relation + marchandage) modulé par le facteur de
	stock, re-clampé dans `[pmin, pmax]` (planchers/plafonds conservés). Source unique du
	prix appliqué (listes + transactions)."""
	base = prix_courant(relation_doc, item_id, pmin, pmax, sens)
	pmin_i, pmax_i = int(pmin), int(max(pmin, pmax))
	val = int(round(base * facteur_stock(stock, cible)))
	return max(pmin_i, min(pmax_i, max(1, val)))


# ── Doc relation (réputation perso × lieu) ───────────────────────────────────────

def now_epoch() -> int:
	"""Epoch UTC en secondes (isolé pour les tests / le monkeypatch)."""
	return int(time.time())


def relation_doc_id(character: dict, lieu_doc: dict) -> str:
	char_id = (character or {}).get("_id") or ""
	lieu_id = (lieu_doc or {}).get("_id") or ""
	return "relation:" + char_id + "::" + lieu_id


def get_relation(character: dict, lieu_doc: dict) -> dict:
	"""Doc relation perso×lieu : l'existant en base, sinon un dict frais neutre (non
	sauvegardé — l'endpoint persiste, comme credit_character/grant_xp)."""
	doc_id = relation_doc_id(character, lieu_doc)
	existing = get_doc(doc_id)
	if existing:
		return existing
	return {
		"_id": doc_id,
		"type": "relation",
		"character_id": (character or {}).get("_id"),
		"lieu_id": (lieu_doc or {}).get("_id"),
		"value": int(character_stats.RELATION_INITIALE),
		"prix_negocies": {},
		"marchandage_bloque_jusqu": 0,
	}


def relation_value(relation_doc: dict) -> int:
	"""Valeur de relation bornée 0–100."""
	return int(_clamp(int((relation_doc or {}).get("value", 0) or 0), 0, 100))


def marchandage_bloque(relation_doc: dict, now: int) -> bool:
	"""Le marchand refuse-t-il de négocier (blocage après crit échec encore actif) ?"""
	return now < int((relation_doc or {}).get("marchandage_bloque_jusqu", 0) or 0)


def appliquer_marchandage(relation_doc: dict, item_id: str, sens: str, deal: dict,
						  now: int) -> dict:
	"""Applique l'issue d'un marchandage au doc relation (mute en place, NE SAUVEGARDE
	PAS). Crit réussite (roll ≤ MAX) → +1 relation ; crit échec (roll ≥ MIN) → −1 relation
	et blocage du marchandage ; réussite simple → persiste le prix négocié. Renvoie un
	résumé {crit, relation, prix_negocie, bloque_jusqu}."""
	roll = int(deal.get("roll", 50))
	val = relation_value(relation_doc)
	crit = None
	if roll <= int(character_stats.CRIT_REUSSITE_MAX):
		val = min(100, val + 1)
		crit = "reussite"
	elif roll >= int(character_stats.CRIT_ECHEC_MIN):
		val = max(0, val - 1)
		relation_doc["marchandage_bloque_jusqu"] = now + int(character_stats.MARCHANDAGE_BLOCAGE_SECONDES)
		crit = "echec"
	relation_doc["value"] = val

	neg = None
	if deal.get("succes"):
		pn = relation_doc.setdefault("prix_negocies", {})
		# On persiste la FRACTION de la fourchette (rejouée contre le poids de chaque
		# instance), pas le montant fixe — sinon deux exemplaires de poids différents
		# auraient le même prix. Repli sur l'absolu si un deal n'expose pas de frac.
		frac = deal.get("frac")
		if isinstance(frac, (int, float)) and not isinstance(frac, bool):
			pn.setdefault(item_id, {})[sens] = {"frac": float(frac)}
		else:
			pn.setdefault(item_id, {})[sens] = int(deal["prix"])
		neg = int(deal["prix"])

	return {
		"crit": crit,
		"relation": val,
		"prix_negocie": neg,
		"bloque_jusqu": int(relation_doc.get("marchandage_bloque_jusqu", 0) or 0),
	}


# Répertoires des images de lieu, dans l'ordre de résolution (mêmes chemins que les
# mounts statiques de main.py — garder synchro).
_IMAGE_ROUTES = (
	("towns", "templates/resources/towns"),
	("maps", "templates/resources/maps"),
	("battle_maps", "templates/resources/battle_maps"),
)


def _lieu_image_route(lieu_doc: dict) -> tuple[str | None, str | None]:
	"""(image, route) servable pour un doc lieu : première route dont le fichier existe
	sur disque (towns → maps → battle_maps), sinon (None, None)."""
	img = (lieu_doc or {}).get("image")
	if img:
		for route, path in _IMAGE_ROUTES:
			if os.path.exists(os.path.join(path, img)):
				return img, route
	return None, None


def relations_lieux_payload(character: dict) -> list[dict]:
	"""Tous les lieux CONNUS du personnage (`lieux_visites`, complété des lieux ayant déjà
	un doc relation) pour l'onglet 🤝 de la fiche, sous forme de liste à plat. Le client
	regroupe par ville (`lieu_parent` → lieu `categorie:"ville"`) en accordéon. Sert au
	rendu initial de /play ET au resync client après marchandage (champ `relations_lieux`
	de quotes/marchander → renderFicheRelations).

	Chaque entrée porte de quoi construire l'en-tête de ville côté client, y compris quand
	la ville elle-même n'a pas été visitée (`parent_*`). Un lieu sans relation apparaît en
	valeur neutre (RELATION_INITIALE)."""
	character = character or {}
	now = now_epoch()

	# Docs relation indexés par lieu_id en une seule passe.
	rels_by_lieu: dict[str, dict] = {}
	for rel in (find_docs({"type": "relation", "character_id": character.get("_id")}) or []):
		lid = rel.get("lieu_id")
		if lid:
			rels_by_lieu[lid] = rel

	# Ensemble connu = lieux visités + lieux avec relation (dédup, ordre conservé).
	lieu_ids: list[str] = []
	seen: set[str] = set()
	for lid in list(character.get("lieux_visites") or []) + list(rels_by_lieu.keys()):
		if lid and lid not in seen:
			seen.add(lid)
			lieu_ids.append(lid)

	parent_cache: dict[str, dict | None] = {}
	relations = []
	for lieu_id in lieu_ids:
		lieu_doc = get_doc(lieu_id)
		if not lieu_doc:
			continue
		rel = rels_by_lieu.get(lieu_id)
		img, img_route = _lieu_image_route(lieu_doc)
		parent_id = lieu_doc.get("lieu_parent")
		parent_nom = parent_img = parent_route = None
		if parent_id:
			if parent_id not in parent_cache:
				parent_cache[parent_id] = get_doc(parent_id)
			pdoc = parent_cache[parent_id]
			if pdoc:
				parent_nom = pdoc.get("label", parent_id)
				parent_img, parent_route = _lieu_image_route(pdoc)
		relations.append({
			"lieu_id": lieu_id,
			"nom": lieu_doc.get("label", lieu_id),
			"categorie": lieu_doc.get("categorie", "") or "",
			"est_ville": lieu_doc.get("categorie") == "ville",
			"image": img,
			"image_route": img_route,
			"value": relation_value(rel) if rel else int(character_stats.RELATION_INITIALE),
			"bloque": marchandage_bloque(rel, now) if rel else False,
			"lieu_parent": parent_id,
			"parent_nom": parent_nom,
			"parent_image": parent_img,
			"parent_image_route": parent_route,
		})
	relations.sort(key=lambda r: r["value"], reverse=True)
	return relations


# ── Résolution objet_final → item ───────────────────────────────────────────────
# Quelques produits de recette réutilisent un item legacy (cf. add_item.json) ; les
# autres résolvent vers `item:<objet_final>`.
_OBJET_FINAL_ITEM_ID: dict[str, str] = {
	"bougie": "item:Bougie",
	"encre": "item:Encre",
	"poudre_d_os": "item:Poudre_os",
	"viande_sechee": "item:Viande_sechee",
	"plume_a_ecrire": "item:Plume_d_oie",
}


def objet_final_item_id(slug: str) -> str:
	"""ID d'item produit pour un `objet_final` de recette (override legacy ou item:<slug>)."""
	return _OBJET_FINAL_ITEM_ID.get(slug, "item:" + slug)


def matiere_item_id(cle: str) -> str:
	"""ID d'item correspondant à une clé matière : une clé item-ref est déjà un id, une
	sous-catégorie passe par `objet_final_item_id` (évite `item:item:…`)."""
	return cle if str(cle).startswith("item:") else objet_final_item_id(cle)


def recette_matieres(r: dict) -> list:
	"""Matières premières d'une recette → liste de (cle, quantite). La **clé matière** est
	soit une sous-catégorie, soit un id d'item (préfixe `item:`) : une entrée de
	`matieres_premieres:[{sous_categorie|item, quantite}, …]` peut référencer un item
	précis (`item` prioritaire) — deux items de même sous-catégorie (ex. les herbes)
	peuvent ainsi avoir des recettes distinctes. Les clés item-ref circulent telles
	quelles dans `stock_matieres`/besoins/feuilles. Repli rétro-compatible sur le champ
	mono-entrée `matiere_premiere_sous_categorie`/`quantite_matiere`."""
	mp = r.get("matieres_premieres")
	if isinstance(mp, list) and mp:
		out = [
			(e.get("item") or e.get("sous_categorie"), max(1, int(e.get("quantite", 1) or 1)))
			for e in mp if isinstance(e, dict) and (e.get("item") or e.get("sous_categorie"))
		]
		if out:
			return out
	sc = r.get("matiere_premiere_sous_categorie")
	return [(sc, max(1, int(r.get("quantite_matiere", 1) or 1)))] if sc else []


# ── Dépeçage des carcasses (boucherie) ──────────────────────────────────────────

_INTANGIBLE = {"esprit", "incorporel"}
_CONSTRUCT = {"construct", "elementaire"}
_UNDEAD = {"undead", "non_mort"}


def _facteur_poids(poids) -> float:
	"""Facteur d'échelle du dépeçage = poids / DEPECAGE_POIDS_REF (1.0 si poids absent/invalide).

	Pilote la conservation de la masse : une carcasse plus lourde rend proportionnellement
	plus de matières (cf. depecage_carcasse)."""
	ref = character_stats.DEPECAGE_POIDS_REF
	if not isinstance(poids, (int, float)) or isinstance(poids, bool) or poids <= 0 or ref <= 0:
		return 1.0
	return float(poids) / float(ref)


def depecage_carcasse(espece_doc: dict, qmap: dict | None = None,
					  poids=None) -> list[tuple[str, int]]:
	"""Matières premières tirées d'une carcasse (modèle hybride espèce × recettes).

	La **membership** (quelles sous-catégories) est dérivée des `tags` de l'espèce ; la
	**quantité de base** de chaque sous-cat vient de `qmap` (table des recettes de
	boucherie `carcasse → <matiere>`) si fournie, sinon de la quantité dérivée des tags.
	Override : si l'espèce porte un champ `depecage` (liste de [sous_cat, qty]), on
	l'utilise tel quel. Règle par tags (table tunable `DEPECAGE_TAGS`) : esprit/construct
	→ rien ; mort-vivant → os ; sinon base charnue + apports par tag. On prend le MAX par
	sous-cat entre sources (pas la somme). **Conservation de la masse** : toute quantité de
	base est mise à l'échelle du poids de l'instance (`× poids / DEPECAGE_POIDS_REF`, min 1)
	— plus la carcasse est lourde, plus elle rend de matières (plus de bucket petite/geant).
	"""
	espece_doc = espece_doc or {}
	facteur = _facteur_poids(poids)
	override = espece_doc.get("depecage")
	if isinstance(override, list) and override:
		out = []
		for entry in override:
			if isinstance(entry, (list, tuple)) and len(entry) >= 2:
				out.append((str(entry[0]), max(1, int(round(int(entry[1]) * facteur)))))
			elif isinstance(entry, dict) and entry.get("sous_categorie"):
				out.append((entry["sous_categorie"], max(1, int(round(int(entry.get("quantite", 1)) * facteur)))))
		return out

	tags = set(espece_doc.get("tags") or [])
	table = character_stats.DEPECAGE_TAGS
	if tags & _INTANGIBLE or tags & _CONSTRUCT:
		return []

	sources: list[list[str]] = []
	if tags & _UNDEAD:
		sources = [table[t] for t in (tags & _UNDEAD) if t in table]
	else:
		if "_charnu_base" in table:
			sources.append(table["_charnu_base"])
		sources += [table[t] for t in tags if t in table and not t.startswith("_")]

	draconique = "draconique" in tags
	counts: dict[str, int] = {}
	for src in sources:
		local = Counter(src)
		if draconique:
			local.pop("plumes", None)
		for sc, q in local.items():
			counts[sc] = max(counts.get(sc, 0), q)

	qmap = qmap or {}
	out = []
	for sc, q in counts.items():
		if q <= 0:
			continue
		base = qmap.get(sc, q)  # quantité de recette si dispo, sinon dérivée des tags
		out.append((sc, max(1, int(round(base * facteur)))))  # facteur = échelle au poids
	return out


# ── Conversion : ce que le lieu achète → stock vendable ─────────────────────────

_CONVERSION_CAP = 100  # bornes le nombre de cuissons de recette par vente (anti-runaway)


def lieu_recettes(lieu_categorie: str) -> list:
	"""Recettes de transformation associées à une catégorie de lieu (atelier)."""
	if not lieu_categorie:
		return []
	return find_docs({"type": "recette", "lieu_categorie": lieu_categorie})


def _stock_vente_add(stock_vente: list, item_id: str, qty: int) -> None:
	"""Ajoute `qty` exemplaires de `item_id` au stock de vente (fusion par item_id)."""
	for entry in stock_vente:
		if entry.get("item_id") == item_id:
			entry["qty"] = int(entry.get("qty", 0)) + qty
			return
	stock_vente.append({"item_id": item_id, "qty": qty})


def _matieres_entrantes(item_doc: dict, qmap: dict | None = None,
						categorie: str | None = None) -> list[tuple[str, int]]:
	"""Matières apportées au lieu par l'objet acheté. Une carcasse est décomposée par
	espèce (quantités issues de `qmap`, table des recettes de boucherie) ; tout autre
	objet apporte 1 unité sous sa clé matière pour ce lieu (`cle_matiere_lieu` : id
	d'item si une recette de la catégorie le référence directement, sinon sous-catégorie)."""
	if item_sous_categorie(item_doc) == "carcasse":
		item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id") or ""
		sub = item_id[len("item:"):] if item_id.startswith("item:") else ""
		espece = get_doc("espece:" + sub) if sub else None
		return depecage_carcasse(espece, qmap, (item_doc or {}).get("poids")) if espece else []
	cle = cle_matiere_lieu(categorie, item_doc)
	if cle:
		return [(cle, 1)]
	return []


def _executer_production_batch(lieu_doc: dict, recettes: list | None = None) -> list[dict]:
	"""Passe de production : **draine le stock** du lieu en cuisant des recettes tant qu'il
	reste de la matière, en tirant chaque recette au hasard **pondéré par `quantite_matiere`**
	(les plus gourmandes favorisées), jusqu'au cap anti-runaway. Les matières qu'aucune recette
	du lieu ne consomme (produits finis de la boucherie : carcasse décomposée par espèce+poids
	en viande/os/…) sont **mises en rayon** (`stock_vente`). La matière transformable **sous le
	seuil** reste en stock pour le prochain batch. Mute `lieu_doc` en place ; renvoie [{item_id,qty}]."""
	stock_mat = lieu_doc.setdefault("stock_matieres", {})
	stock_vente = lieu_doc.setdefault("stock_vente", [])
	recettes = recettes if recettes is not None else lieu_recettes(lieu_doc.get("categorie"))
	consommables = {sc for r in recettes for (sc, _q) in recette_matieres(r)}

	prepared = [
		{
			"inputs": recette_matieres(r),                        # [(sous_cat, qm), …]
			"poids": sum(qm for (_sc, qm) in recette_matieres(r)),  # pour la pondération du tirage
			"qp": max(1, int(r.get("quantite_produite", 1) or 1)),
			"item_id": objet_final_item_id(r.get("objet_final", "")),
		}
		for r in recettes
		if recette_matieres(r)
	]
	produits: dict[str, int] = {}
	fired = 0
	while fired < _CONVERSION_CAP:
		# Une recette est applicable seulement si TOUTES ses matières sont en stock suffisant.
		applicable = [p for p in prepared if all(int(stock_mat.get(sc, 0)) >= qm for (sc, qm) in p["inputs"])]
		if not applicable:
			break
		chosen = random.choices(applicable, weights=[max(1, p["poids"]) for p in applicable])[0]
		for (sc, qm) in chosen["inputs"]:
			stock_mat[sc] -= qm
		_stock_vente_add(stock_vente, chosen["item_id"], chosen["qp"])
		produits[chosen["item_id"]] = produits.get(chosen["item_id"], 0) + chosen["qp"]
		fired += 1

	# Produits finis : matières qu'aucune recette du lieu ne consomme (ex. viande/os
	# décomposés à la boucherie) → mises en rayon lors de la passe.
	for sc in list(stock_mat):
		q = int(stock_mat.get(sc, 0))
		if q > 0 and sc not in consommables:
			item_id = matiere_item_id(sc)
			_stock_vente_add(stock_vente, item_id, q)
			produits[item_id] = produits.get(item_id, 0) + q
			stock_mat[sc] = 0

	# Nettoyage des matières épuisées
	for sc in [k for k, v in stock_mat.items() if v <= 0]:
		del stock_mat[sc]

	return [{"item_id": k, "qty": v} for k, v in produits.items()]


def tenter_production(lieu_doc: dict, recettes: list | None = None) -> list[dict]:
	"""Avec une probabilité `ATELIER_TRANSFO_PROBA`, lance une passe de production (batch) ;
	sinon ne fait rien (la matière reste stockée). Déclenché à chaque vente ET à chaque
	visite du lieu. Mute `lieu_doc` en place ; renvoie les produits ajoutés (vide si pas de
	déclenchement ou rien à produire)."""
	proba = max(0.0, min(1.0, character_stats.ATELIER_TRANSFO_PROBA))
	if random.random() >= proba:
		return []
	return _executer_production_batch(lieu_doc, recettes)


def ecouler_produits_pnj(lieu_doc: dict) -> list[dict]:
	"""Vente PNJ en parallèle : **objet par objet**, chaque produit en rayon (`stock_vente`)
	tire indépendamment sa demande avec proba `VENTE_PNJ_PROBA` — au même tick, certains
	produits s'écoulent, d'autres non (plus réaliste qu'une vente en bloc). Quand un produit
	est demandé, on écoule une fraction `VENTE_PNJ_FRACTION` de son **excédent** (au-dessus du
	stock cible). Les PNJ n'achètent que le surplus : `qty` ne descend jamais sous la cible
	(le joueur garde le stock de base). Mute `lieu_doc` ; renvoie [{item_id, qty}] écoulés
	(vide si rien de demandé/écoulé)."""
	proba = max(0.0, min(1.0, character_stats.VENTE_PNJ_PROBA))
	frac = max(0.0, min(1.0, character_stats.VENTE_PNJ_FRACTION))
	if proba <= 0 or frac <= 0:
		return []
	ecoules = []
	for entry in (lieu_doc or {}).get("stock_vente", []):
		# Chaque produit tire sa propre demande PNJ ce tick (indépendant des autres).
		if random.random() >= proba:
			continue
		item_id = entry.get("item_id")
		qty = int(entry.get("qty", 0))
		if not item_id or qty <= 0:
			continue
		item = resolve_item_ref(item_id)
		if not item:
			continue
		cible = stock_cible_pour(lieu_doc, item)
		excedent = qty - cible
		if excedent <= 0:
			continue
		vendu = int(round(excedent * frac))
		if vendu > 0:
			entry["qty"] = qty - vendu
			ecoules.append({"item_id": item_id, "qty": vendu})
	return ecoules


def _appro_debit_pour(cle: str) -> int:
	"""Débit d'appro d'une clé matière : `APPRO_DEBIT[cle]` si posé ; pour une clé item-ref
	sans entrée dédiée, repli sur la sous-catégorie du doc item (ex. les deux herbes héritent
	de `APPRO_DEBIT["herbe"]` = 0 → pas d'auto-appro, récolte joueur) ; sinon le défaut."""
	debit = character_stats.APPRO_DEBIT
	if cle in debit:
		return int(debit[cle] or 0)
	if str(cle).startswith("item:"):
		sc = item_sous_categorie(get_doc(cle) or {})
		if sc in debit:
			return int(debit[sc] or 0)
	return int(character_stats.APPRO_DEBIT_DEFAUT or 0)


def approvisionner(lieu_doc: dict) -> bool:
	"""Approvisionnement automatique du lieu : injecte dans `stock_matieres` les matières
	« feuilles » dérivées de ses recettes (`appro_leaves_categorie`, typiquement les métaux
	pour l'armurerie), au débit `_appro_debit_pour(cle)` (`APPRO_DEBIT`, repli item→sous-cat,
	sinon `APPRO_DEBIT_DEFAUT`). Mute `lieu_doc` ; True si quelque chose a été ajouté."""
	feuilles = appro_leaves_categorie((lieu_doc or {}).get("categorie"))
	if not feuilles:
		return False
	stock = lieu_doc.setdefault("stock_matieres", {})
	changed = False
	for cle in feuilles:
		q = _appro_debit_pour(cle)
		if q > 0:
			stock[cle] = int(stock.get(cle, 0)) + q
			changed = True
	return changed


def tick_atelier(lieu_doc: dict, recettes: list | None = None) -> bool:
	"""Tick marché à appeler à chaque vente/visite : approvisionne le lieu selon sa catégorie,
	tente une passe de production puis un écoulement PNJ des produits finis. Renvoie True si le
	doc a changé (→ l'appelant save)."""
	approvisionne = approvisionner(lieu_doc)
	produits = tenter_production(lieu_doc, recettes)
	ecoules = ecouler_produits_pnj(lieu_doc)
	return bool(approvisionne or produits or ecoules)


def convertir_apres_achat(lieu_doc: dict, item_doc: dict) -> bool:
	"""Absorbe l'objet acheté en matières (`stock_matieres`) puis lance un `tick_atelier`
	(production + écoulement PNJ, probabilistes). Mute `lieu_doc` en place (l'appelant
	persiste). Renvoie True si quelque chose a changé."""
	recettes = lieu_recettes(lieu_doc.get("categorie"))

	# Rachat d'un bien que le lieu produit : il repart en rayon (re-vendable), pas en matières.
	if lieu_produit(lieu_doc, item_doc):
		item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
		if item_id:
			_stock_vente_add(lieu_doc.setdefault("stock_vente", []), item_id, 1)
		return tick_atelier(lieu_doc, recettes)

	stock_mat = lieu_doc.setdefault("stock_matieres", {})
	# Table de quantités du dépeçage : recettes `carcasse → <matiere>` du lieu (boucherie).
	qmap = {
		r.get("objet_final"): int(r.get("quantite_produite", 1) or 1)
		for r in recettes if r.get("matiere_premiere_sous_categorie") == "carcasse"
	}
	for cle, qty in _matieres_entrantes(item_doc, qmap, lieu_doc.get("categorie")):
		stock_mat[cle] = int(stock_mat.get(cle, 0)) + qty

	return tick_atelier(lieu_doc, recettes)


def resolve_stock_vente(lieu_doc: dict, relation_doc: dict | None = None) -> list[dict]:
	"""Stock de vente du lieu résolu en lignes affichables : item résolu + qty + prix
	courant à l'achat (négocié ou base pondéré relation) + fourchette min–max."""
	out = []
	for entry in (lieu_doc or {}).get("stock_vente", []):
		item_id = entry.get("item_id")
		qty = int(entry.get("qty", 0))
		if not item_id or qty <= 0:
			continue
		item = resolve_item_ref(item_id)
		if not item:
			continue
		pmin, pmax = prix_range_cuivre(item, item_id)
		cible = stock_cible_pour(lieu_doc, item)
		prix_cuivre = prix_marche(relation_doc, item_id, pmin, pmax, "achat", qty, cible)
		negocie = (relation_doc or {}).get("prix_negocies", {}).get(item_id, {}).get("achat") is not None
		out.append({
			"item_id": item_id,
			"nom": item.get("nom"),
			"icon": item.get("icon"),
			"poids": round(float(item.get("poids", 0) or 0), 2),
			"qty": qty,
			"prix_cuivre": prix_cuivre,
			"prix": cuivre_to_purse(prix_cuivre),
			"prix_min": pmin,
			"prix_max": pmax,
			"prix_min_purse": cuivre_to_purse(pmin),
			"prix_max_purse": cuivre_to_purse(pmax),
			"negocie": negocie,
			**fiche_item_fields(item),
		})
	return out

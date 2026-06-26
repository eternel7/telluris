# utils/marche.py
# Logique pure du marché : marchandage (Cha vs Cha), fourchette de prix, dépeçage des
# carcasses par espèce, et conversion de ce qu'un lieu achète en stock vendable via les
# recettes (`recette:*`). Les endpoints (routers/user.py) persistent ; ces helpers ne
# sauvegardent jamais (ils mutent les docs en place, comme grant_xp/credit_character).

import random
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
	sinon min = prix proposé (`item_sale_price_cuivre`) et max = min × PRIX_MAX_FACTEUR."""
	valeur = (item_doc or {}).get("valeur")
	if isinstance(valeur, (list, tuple)) and len(valeur) >= 2:
		bornes = [valeur_entry_to_cuivre(e) for e in valeur]
		bornes = [b for b in bornes if b > 0]
		if len(bornes) >= 2:
			return min(bornes), max(bornes)
	pmin = item_sale_price_cuivre(item_doc, ref)
	pmax = max(pmin, round(pmin * character_stats.PRIX_MAX_FACTEUR))
	return pmin, pmax


def marchander(pmin: int, pmax: int, cha_joueur: int, cha_marchand: int, sens: str) -> dict:
	"""Jet opposé Cha joueur vs Cha marchand, prix interpolé entre pmin et pmax.

	seuil = clamp(50 + Cha_j − Cha_m, 5, 95) ; roll d100 ; marge = seuil − roll ;
	t = clamp(0.5 + marge/100, 0, 1) (t haut = favorable au joueur).
	- sens "vente" (le joueur vend, veut le max) : prix = pmin + (pmax−pmin)·t
	- sens "achat" (le joueur achète, veut le min) : prix = pmin + (pmax−pmin)·(1−t)
	"""
	pmin, pmax = int(pmin), int(max(pmin, pmax))
	seuil = _clamp(50 + int(cha_joueur or 0) - int(cha_marchand or 0), 5, 95)
	roll = random.randint(1, 100)
	t = _clamp(0.5 + (seuil - roll) / 100.0, 0.0, 1.0)
	frac = t if sens == "vente" else (1.0 - t)
	prix = int(round(pmin + (pmax - pmin) * frac))
	return {
		"prix": max(1, prix),
		"roll": roll,
		"seuil": seuil,
		"succes": roll <= seuil,
		"min": pmin,
		"max": pmax,
	}


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


# ── Dépeçage des carcasses (boucherie) ──────────────────────────────────────────

_INTANGIBLE = {"esprit", "incorporel"}
_CONSTRUCT = {"construct", "elementaire"}
_UNDEAD = {"undead", "non_mort"}


def depecage_carcasse(espece_doc: dict, qmap: dict | None = None) -> list[tuple[str, int]]:
	"""Matières premières tirées d'une carcasse (modèle hybride espèce × recettes).

	La **membership** (quelles sous-catégories) est dérivée des `tags` de l'espèce ; la
	**quantité de base** de chaque sous-cat vient de `qmap` (table des recettes de
	boucherie `carcasse → <matiere>`) si fournie, sinon de la quantité dérivée des tags.
	Override : si l'espèce porte un champ `depecage` (liste de [sous_cat, qty]), on
	l'utilise tel quel. Règle par tags (table tunable `DEPECAGE_TAGS`) : esprit/construct
	→ rien ; mort-vivant → os ; sinon base charnue + apports par tag. On prend le MAX par
	sous-cat entre sources (pas la somme). Échelle : ×0.5 `petite_taille`, ×2 `geant` (min 1).
	"""
	espece_doc = espece_doc or {}
	override = espece_doc.get("depecage")
	if isinstance(override, list) and override:
		out = []
		for entry in override:
			if isinstance(entry, (list, tuple)) and len(entry) >= 2:
				out.append((str(entry[0]), int(entry[1])))
			elif isinstance(entry, dict) and entry.get("sous_categorie"):
				out.append((entry["sous_categorie"], int(entry.get("quantite", 1))))
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

	facteur = 0.5 if "petite_taille" in tags else (2.0 if "geant" in tags else 1.0)
	qmap = qmap or {}
	out = []
	for sc, q in counts.items():
		if q <= 0:
			continue
		base = qmap.get(sc, q)  # quantité de recette si dispo, sinon dérivée des tags
		out.append((sc, max(1, int(round(base * facteur)))))
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


def _matieres_entrantes(item_doc: dict, qmap: dict | None = None) -> list[tuple[str, int]]:
	"""Matières apportées au lieu par l'objet acheté. Une carcasse est décomposée par
	espèce (quantités issues de `qmap`, table des recettes de boucherie) ; tout autre
	objet apporte 1 unité de sa propre sous-catégorie."""
	sous_cat = item_sous_categorie(item_doc)
	if sous_cat == "carcasse":
		item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id") or ""
		sub = item_id[len("item:"):] if item_id.startswith("item:") else ""
		espece = get_doc("espece:" + sub) if sub else None
		return depecage_carcasse(espece, qmap) if espece else []
	if sous_cat:
		return [(sous_cat, 1)]
	return []


def convertir_apres_achat(lieu_doc: dict, item_doc: dict) -> list[dict]:
	"""Le lieu absorbe l'objet acheté en matières (`stock_matieres`), cuit ses recettes
	pour remplir `stock_vente`, et **revend brute** toute matière qu'aucune de ses
	recettes ne consomme (cas boucherie : la carcasse décomposée → viande/os/cuir… sont
	directement vendables ; une matière transformable sous le seuil reste en réserve).
	Mute `lieu_doc` en place (l'appelant persiste). Renvoie [{item_id, qty}] ajoutés."""
	stock_mat = lieu_doc.setdefault("stock_matieres", {})
	stock_vente = lieu_doc.setdefault("stock_vente", [])

	recettes = lieu_recettes(lieu_doc.get("categorie"))
	consommables = {r.get("matiere_premiere_sous_categorie") for r in recettes}

	# Table de quantités du dépeçage : recettes `carcasse → <matiere>` du lieu (boucherie).
	qmap = {
		r.get("objet_final"): int(r.get("quantite_produite", 1) or 1)
		for r in recettes if r.get("matiere_premiere_sous_categorie") == "carcasse"
	}
	for sous_cat, qty in _matieres_entrantes(item_doc, qmap):
		stock_mat[sous_cat] = int(stock_mat.get(sous_cat, 0)) + qty

	produits: dict[str, int] = {}
	fired = 0
	for recette in recettes:
		matiere = recette.get("matiere_premiere_sous_categorie")
		qm = int(recette.get("quantite_matiere", 1) or 1)
		qp = int(recette.get("quantite_produite", 1) or 1)
		item_id = objet_final_item_id(recette.get("objet_final", ""))
		while int(stock_mat.get(matiere, 0)) >= qm and fired < _CONVERSION_CAP:
			stock_mat[matiere] -= qm
			_stock_vente_add(stock_vente, item_id, qp)
			produits[item_id] = produits.get(item_id, 0) + qp
			fired += 1

	# Matières qu'aucune recette du lieu ne transforme → revendues brutes.
	for sc in list(stock_mat):
		q = int(stock_mat.get(sc, 0))
		if q > 0 and sc not in consommables:
			item_id = objet_final_item_id(sc)
			_stock_vente_add(stock_vente, item_id, q)
			produits[item_id] = produits.get(item_id, 0) + q
			stock_mat[sc] = 0

	# Nettoyage des matières épuisées
	for sc in [k for k, v in stock_mat.items() if v <= 0]:
		del stock_mat[sc]

	return [{"item_id": k, "qty": v} for k, v in produits.items()]


def resolve_stock_vente(lieu_doc: dict) -> list[dict]:
	"""Stock de vente du lieu résolu en lignes affichables : item résolu + qty + prix."""
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
		out.append({
			"item_id": item_id,
			"nom": item.get("nom"),
			"icon": item.get("icon"),
			"poids": round(float(item.get("poids", 0) or 0), 2),
			"qty": qty,
			"prix_min": pmin,
			"prix_max": pmax,
			"prix_min_purse": cuivre_to_purse(pmin),
			"prix_max_purse": cuivre_to_purse(pmax),
		})
	return out

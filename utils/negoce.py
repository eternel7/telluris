"""Négociant — le « marchand pur » (pur : mute sans sauver, l'appelant persiste).

Il n'a AUCUNE recette : il achète tout, ne garde en rayon que ce qui vaut cher, et fait
circuler le reste. Deux formes, même règle :
- boutique de ville (`categorie` ∈ `CATEGORIES_NEGOCE`, posée à l'éditeur) ;
- employé d'une propriété au poste `bureau_marchand` (atelier, cf. utils/proprietes.py).

Valeur de référence `V` = `pmin` de `marche.prix_range_cuivre` : le PLANCHER de vente de
toute boutique (`prix_marche` re-clampe à pmin). D'où l'invariant anti-arbitrage — le
négociant paie toujours < V, donc acheter ailleurs pour lui revendre ne rapporte jamais.

Destin d'un objet racheté (`absorber`) :
1. `V ≥ NEGOCE_SEUIL_REVENTE_CUIVRE` → rayon (`stock_vente`), revendu au prix de rayon normal ;
2. sinon, clé utile au flux et pool sous son plafond → flux (de la cité, ou du bien) ;
3. sinon → conversion en cuivre : `RACHAT_FACTEUR × V × (1 + NEGOCE_BONUS_CONVERSION)`, le
   « prix normal » étant le rachat d'une boutique (0,6 V). En propriété il va à la caisse,
   en ville il disparaît (vente aux PNJ).
⚠️ La carcasse ne circule jamais (aucun doc `item:carcasse`, la boucherie la décompose À LA
VENTE) : toujours convertie."""

from models import character_stats
from utils import marche
from utils.characters import item_sous_categorie


def valeur_reference(item_doc: dict, ref=None) -> int:
	"""V = pmin de la fourchette marché (≥ 1)."""
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	pmin, _ = marche.prix_range_cuivre(item_doc, ref if ref is not None else item_id)
	return max(1, int(pmin))


def commission(relation_doc: dict | None) -> float:
	"""Commission LINÉAIRE en relation : `NEGOCE_COMMISSION_MAX` à 0, `_MIN` à 100."""
	cmin = float(character_stats.NEGOCE_COMMISSION_MIN)
	cmax = float(character_stats.NEGOCE_COMMISSION_MAX)
	r = marche.relation_value(relation_doc)
	return cmax - (cmax - cmin) * r / 100.0


def bornes_rachat(item_doc: dict, ref=None) -> tuple[int, int]:
	"""Fourchette affichée : du pire (relation 0) au meilleur (relation 100) rachat."""
	v = valeur_reference(item_doc, ref)
	return (max(1, int(round(v * (1 - float(character_stats.NEGOCE_COMMISSION_MAX))))),
			max(1, int(round(v * (1 - float(character_stats.NEGOCE_COMMISSION_MIN))))))


def prix_rachat(item_doc: dict, relation_doc: dict | None, ref=None) -> int:
	"""Ce que le négociant paie au vendeur : `V × (1 − commission)`. Ni stock ni marchandage."""
	v = valeur_reference(item_doc, ref)
	return max(1, int(round(v * (1 - commission(relation_doc)))))


def prix_conversion(item_doc: dict, ref=None) -> int:
	"""Cuivre tiré d'un objet que ni le rayon ni le flux ne prennent."""
	v = valeur_reference(item_doc, ref)
	f = float(character_stats.RACHAT_FACTEUR) * (1 + float(character_stats.NEGOCE_BONUS_CONVERSION))
	return max(0, int(round(v * f)))


def destination(item_doc: dict, flux: dict | None, cles_utiles, ref=None) -> str:
	"""`"rayon"`, `"flux"` ou `"conversion"` — sans rien muter."""
	if valeur_reference(item_doc, ref) >= int(character_stats.NEGOCE_SEUIL_REVENTE_CUIVRE):
		return "rayon"
	sc = item_sous_categorie(item_doc)
	if not flux or sc == "carcasse":
		return "conversion"
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	cles = cles_utiles or ()
	if item_id not in cles and sc not in cles:
		return "conversion"
	plafond = max(1, int(character_stats.STOCK_CIBLE_DEFAUT))
	if int((flux.get("pool") or {}).get(item_id, 0)) >= plafond:
		return "conversion"
	return "flux"


def absorber(neg_doc: dict, item_doc: dict, flux: dict | None, cles_utiles, ref=None) -> tuple[str, int]:
	"""Fait entrer l'objet racheté chez le négociant (mute `neg_doc` et le contexte de flux).
	Renvoie `(destination, cuivre_converti)` — l'appelant crédite la caisse en propriété."""
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	dest = destination(item_doc, flux, cles_utiles, ref)
	if dest == "rayon":
		marche._stock_vente_add(neg_doc.setdefault("stock_vente", []), item_id, 1)
		return dest, 0
	if dest == "flux":
		pool = flux.setdefault("pool", {})
		pool[item_id] = int(pool.get(item_id, 0)) + 1
		flux["change"] = True
		return dest, 0
	return dest, prix_conversion(item_doc, ref)

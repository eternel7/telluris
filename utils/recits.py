"""Récits historiques (pur) : plafond de titres en rayon par magasin (Auteur, 22/11/2026).

Un récit = un item tagué `ouvrage_historique` (`dev/gen_ouvrages_historiques.py`). Un magasin
n'en expose qu'un nombre limité de TITRES DISTINCTS, UN exemplaire de chacun :
`character_stats.RECITS_PLAFOND[categorie]` (scriptorium 1, bibliothèque 5, grande 10…),
remplacé par `RECITS_PLAFOND_CAPITALE[categorie]` quand la cité du lieu est une capitale.

Le plafond tient à la FABRICATION (`marche._executer_production_batch`) et à la vente d'un
atelier de propriété aux boutiques de sa cité (`echanges_cite.prix_vente_boutique`). Un récit
que le joueur vend est toujours accepté : le rayon peut alors dépasser jusqu'à la vente.

Catégorie absente des tables ⇒ `None` ⇒ aucun plafond (comportement d'avant)."""

from models import character_stats

TAG_RECIT = "ouvrage_historique"


def est_recit(item_doc: dict | None) -> bool:
	return TAG_RECIT in ((item_doc or {}).get("tags") or ())


def plafond(lieu_doc: dict | None, cite_doc: dict | None) -> int | None:
	"""Nombre maximal de titres de récits en rayon pour ce lieu ; None = sans plafond."""
	cat = (lieu_doc or {}).get("categorie")
	if not cat:
		return None
	if (cite_doc or {}).get("sous_categorie") == "capitale" and cat in character_stats.RECITS_PLAFOND_CAPITALE:
		return int(character_stats.RECITS_PLAFOND_CAPITALE[cat])
	if cat in character_stats.RECITS_PLAFOND:
		return int(character_stats.RECITS_PLAFOND[cat])
	return None


def titres_en_rayon(lieu_doc: dict | None, resolve_fn) -> set:
	"""Ids des récits présents (qty > 0) dans le rayon du lieu."""
	out = set()
	for e in (lieu_doc or {}).get("stock_vente") or ():
		item_id = e.get("item_id")
		if item_id and int(e.get("qty", 0) or 0) > 0 and est_recit(resolve_fn(item_id)):
			out.add(item_id)
	return out


def admis(item_id: str, titres: set, plafond_lieu: int | None) -> bool:
	"""Ce récit peut-il entrer en rayon ? Pas s'il y est déjà (un exemplaire par titre), ni si
	le plafond de titres est atteint. Sans plafond, toujours."""
	if plafond_lieu is None:
		return True
	return item_id not in titres and len(titres) < plafond_lieu

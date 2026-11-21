"""Sacs du groupe pour un panneau de rangement à deux colonnes (pur, DB injectée).

Partagé par le coffre d'une propriété (`routers/proprietes`) et les rangements d'une
implantation (`routers/colonisation`) : à gauche le sac du personnage, d'un de ses PORTEURS
(compagnons puis montures, `recrutement.porteurs_effectifs`) ou d'un CONTENANT de ces sacs.
"""

from utils import contenants
from utils import montures
from utils import recrutement
from utils.characters import carried_weight


def porteurs_payload(character: dict, get_doc_fn, resolve_fn) -> list:
	"""Porteurs du groupe au format d'un sac de gauche. ⚠️ `charge_max_porteur` et non
	`charge_max_of` : une monture porte bien davantage, et le client recopie ce plafond
	pour griser ses flèches."""
	return [
		{"id": p["_id"], "prenom": p.get("prenom", ""), "nom": p.get("nom", ""),
		 "monture": montures.est_monture(p),
		 "charge": round(carried_weight(p), 2), "charge_max": montures.charge_max_porteur(p),
		 "inventaire": [d for r in p.get("inventaire") or [] if (d := resolve_fn(r))]}
		for p in recrutement.porteurs_effectifs(character, get_doc_fn)
	]


def sacs_contenants(character: dict, get_doc_fn, resolve_fn, now: int) -> list:
	"""Chaque contenant porté (vous, compagnons, montures), vide ou plein, au format d'un sac :
	`cle` (`porteur#index`, sélecteur), `porteur_id` (= `compagnon_id` des transferts, vous
	compris), `index`/`item_id` (adresse), `charge`/`charge_max` (rangé / capacité) et contenu
	indexé par sa position réelle. Hors marée : rien de visible, `accessible` faux."""
	porteurs = [character] + recrutement.porteurs_effectifs(character, get_doc_fn)
	par_id = {p.get("_id"): p for p in porteurs}
	out = []
	for c in contenants.destinations(porteurs, get_doc_fn, now):
		ref_c = (par_id[c["porteur_id"]].get("inventaire") or [])[c["index"]]
		vue = contenants.vue(ref_c, get_doc_fn(c["item_id"]), now, resolve_fn)
		out.append(dict(c, charge=c["charge_kg"] if c["accessible"] else 0,
						charge_max=c["capacite_kg"], inventaire=vue.get("contenu") or []))
	return out


def porteur_vise(character: dict, compagnon_id, get_doc_fn) -> dict | None:
	"""Le sac visé : le personnage, ou l'un de ses porteurs (compagnon OU monture) ; None si
	l'id n'en est pas un (→ 403 chez l'appelant). Un doc `aventurier:*`/`monture:*` n'a pas de
	`user_id` : `porteurs_effectifs` (statut + lien vers CE personnage) est la seule preuve
	d'appartenance — miroir de `routers/user._acteur`."""
	if not compagnon_id or compagnon_id == character.get("_id"):
		return character
	return next((x for x in recrutement.porteurs_effectifs(character, get_doc_fn)
				 if x.get("_id") == compagnon_id), None)


def contenant_vise(porteur: dict, body: dict, get_doc_fn) -> tuple[int | None, dict | None, bool]:
	"""(position, doc, introuvable) du contenant DESTINATAIRE adressé par
	`index_contenant`/`item_id_contenant` dans ce sac ; (None, None, False) sans adresse ;
	`introuvable` vrai si l'adresse ne désigne plus un contenant (→ 404 chez l'appelant)."""
	idx_c, iid_c = body.get("index_contenant"), body.get("item_id_contenant")
	if idx_c is None and not iid_c:
		return None, None, False
	pos_c, doc_c = contenants.contenant_de(porteur, idx_c, iid_c, get_doc_fn)
	return pos_c, doc_c, pos_c is None

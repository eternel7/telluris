# routers/contenants.py — ouvrir, ranger, sortir (utils/contenants.py ; docs/conception_contenants.md).
#
# Le contenant peut être dans le sac du personnage, d'un compagnon ou d'une monture : tout
# passe par `_acteur` (CLAUDE.md, convention 1) et l'action porte le `compagnon_id` de
# l'acteur courant. Hors combat seulement (Auteur, 02/11) : l'interface vit dans /play, qui
# redirige déjà vers un combat actif — la garde serveur vise la requête forgée.

import time
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from db.config import get_doc, find_docs
from utils.auth import get_current_user
from utils.characters import item_ref_id, resolve_item_ref
from utils import contenants
from utils import recrutement
from routers.user import _acteur, _save_acteur, _inventory_payload, _fiche_payload

contenants_router = APIRouter()


def _refuser_en_combat(current_user: dict, principal: dict) -> None:
	"""Même test que l'anti-doublon de `routers/combat.py`."""
	for c in find_docs({"type": "combat", "user_id": current_user["_id"]}) or []:
		if c.get("character_id") == principal.get("_id") and c.get("status") == "active":
			raise HTTPException(status_code=409, detail="On ne fouille pas un contenant en plein combat.")


def _contenant(porteur: dict, idx, item_id) -> tuple[int, dict]:
	inv = porteur.get("inventaire") or []
	pos = contenants.localiser(inv, idx, item_id)
	doc = get_doc(item_ref_id(inv[pos])) if pos is not None else None
	if pos is None or not contenants.est_contenant(doc):
		raise HTTPException(status_code=404, detail="Contenant introuvable dans ce sac.")
	return pos, doc


def _reponse(porteur: dict, principal: dict, pos_c: int, doc_c: dict, now: int, extra: dict | None = None) -> dict:
	"""Resync complet (convention 10) : sac, charge et bloc du contenant ; `fiche` car sortir
	ou ranger un grimoire ouvre ou ferme « 📖 Apprendre »."""
	ref_c = (porteur.get("inventaire") or [])[pos_c]
	payload = _inventory_payload(porteur, principal)
	payload["contenant"] = dict(contenants.vue(ref_c, doc_c, now, resolve_item_ref),
								index=pos_c, item_id=item_ref_id(ref_c), nom=(resolve_item_ref(ref_c) or {}).get("nom"))
	payload["fiche"] = _fiche_payload(porteur)
	if extra:
		payload.update(extra)
	return payload


@contenants_router.get("/contenant")
def contenant_ouvrir(current_user: Annotated[dict, Depends(get_current_user)],
					 index: int | None = None, item_id: str | None = None, compagnon_id: str | None = None):
	porteur, principal = _acteur(current_user, {"compagnon_id": compagnon_id})
	pos_c, doc_c = _contenant(porteur, index, item_id)
	return _reponse(porteur, principal, pos_c, doc_c, int(time.time()))


@contenants_router.post("/contenant/ranger")
async def contenant_ranger(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Sac → contenant. Toujours possible, marée basse comprise (on dépose à tout moment)."""
	porteur, principal = _acteur(current_user, body)
	_refuser_en_combat(current_user, principal)
	pos_c, doc_c = _contenant(porteur, body.get("index_contenant"), body.get("item_id_contenant"))
	inv = porteur.get("inventaire") or []
	pos = contenants.localiser(inv, body.get("index"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Objet absent de ce sac.")
	if pos == pos_c:
		raise HTTPException(status_code=422, detail="Un contenant ne se range pas en lui-même.")
	ok, raison = contenants.peut_ranger(inv[pos_c], doc_c, inv[pos], get_doc(item_ref_id(inv[pos])))
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	ref = contenants.ranger(porteur, pos_c, pos)
	if pos < pos_c:
		pos_c -= 1   # le sac a perdu un objet AVANT le contenant
	_save_acteur(porteur, principal)
	return _reponse(porteur, principal, pos_c, doc_c, int(time.time()),
					{"range": (resolve_item_ref(ref) or {}).get("nom")})


@contenants_router.post("/contenant/sortir")
async def contenant_sortir(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Contenant → sac du même porteur. Refus hors marée (Sac de Manannán) ou si le porteur
	ne peut pas porter l'objet."""
	porteur, principal = _acteur(current_user, body)
	_refuser_en_combat(current_user, principal)
	now = int(time.time())
	pos_c, doc_c = _contenant(porteur, body.get("index_contenant"), body.get("item_id_contenant"))
	if not contenants.accessible(doc_c, now):
		raise HTTPException(status_code=409, detail="La mer s'est retirée : le sac semble vide jusqu'à la prochaine marée haute.")
	ref_c = (porteur.get("inventaire") or [])[pos_c]
	dedans = contenants.contenu(ref_c)
	j = contenants.localiser(dedans, body.get("index_contenu"), body.get("item_id"))
	if j is None:
		raise HTTPException(status_code=404, detail="Cet objet n'est plus dans le contenant.")
	if not recrutement.peut_porter(porteur, dedans[j]):
		raise HTTPException(status_code=409, detail="Vous ne pouvez pas porter davantage."
							if porteur is principal else "Ce porteur ne peut pas porter davantage.")
	ref = contenants.sortir(porteur, pos_c, j)
	_save_acteur(porteur, principal)
	return _reponse(porteur, principal, pos_c, doc_c, now,
					{"sorti": (resolve_item_ref(ref) or {}).get("nom")})


@contenants_router.post("/contenant/poser")
async def contenant_poser(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Contenant → sol du PRINCIPAL (un compagnon n'a ni lieu ni position, cf. drop_item), sans
	passer par le sac : aucun contrôle de charge, un contenant porte plus que son porteur.
	Transitoire comme tout objet au sol : perdu au prochain déplacement, repris par le
	ramassage ordinaire (sac ou contenant). Refus hors marée, comme « sortir »."""
	porteur, principal = _acteur(current_user, body)
	_refuser_en_combat(current_user, principal)
	now = int(time.time())
	pos_c, doc_c = _contenant(porteur, body.get("index_contenant"), body.get("item_id_contenant"))
	if not contenants.accessible(doc_c, now):
		raise HTTPException(status_code=409, detail="La mer s'est retirée : le sac semble vide jusqu'à la prochaine marée haute.")
	dedans = contenants.contenu((porteur.get("inventaire") or [])[pos_c])
	j = contenants.localiser(dedans, body.get("index_contenu"), body.get("item_id"))
	if j is None:
		raise HTTPException(status_code=404, detail="Cet objet n'est plus dans le contenant.")
	au_sol = principal.get("objets_au_sol") or []
	ref = contenants.poser(porteur, pos_c, j, au_sol)
	principal["objets_au_sol"] = au_sol
	_save_acteur(porteur, principal)
	return _reponse(porteur, principal, pos_c, doc_c, now,
					{"pose": (resolve_item_ref(ref) or {}).get("nom")})

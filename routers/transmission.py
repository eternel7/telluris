# routers/transmission.py — POST /api/transmettre (utils/transmission.py).
#
# Le menu « Transmettre » de /play : un objet que le groupe a en main (sac d'un porteur,
# contenant porté, sol du lieu) passe à n'importe quel autre emplacement du groupe.
#
# Corps :
#   compagnon_id   — l'ACTEUR de la fiche ouverte (`_actionBody`, CLAUDE.md §1) : la réponse
#                    est SON inventaire (sac + sol du principal), jamais celui d'un autre ;
#   source, cible  — {"sol": true} | {"porteur_id": id}
#                    | {"porteur_id": id, "contenant_index": i, "contenant_item_id": iid} ;
#   index, item_id — l'objet dans la source (position vérifiée par l'item_id).

import time
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from db.config import get_doc, save_doc
from utils.auth import get_current_user
from utils.characters import item_ref_id, item_ref_weight, resolve_item_ref
from utils import transmission
from routers.user import _acteur, _membre_du_groupe, _inventory_payload, _fiche_payload
from routers.contenants import _refuser_en_combat

transmission_router = APIRouter()


def _emplacement(desc, principal: dict, acteur: dict, resolus: dict) -> dict:
	"""Résout une adresse du corps. Un même `porteur_id` donne TOUJOURS le même dict (`resolus`) :
	deux dicts d'un même doc feraient deux `save_doc` sur un `_rev` identique."""
	if not isinstance(desc, dict):
		raise HTTPException(status_code=422, detail="Emplacement invalide")
	if desc.get("sol"):
		return transmission.emplacement_sol()
	pid = desc.get("porteur_id")
	if not pid:
		raise HTTPException(status_code=422, detail="Emplacement invalide")
	if pid not in resolus:
		p = _membre_du_groupe(principal, acteur, pid)
		if p is None:
			raise HTTPException(status_code=403, detail="Ce porteur ne fait pas partie de votre groupe")
		resolus[pid] = p
	porteur = resolus[pid]
	if desc.get("contenant_index") is not None or desc.get("contenant_item_id"):
		return transmission.emplacement_contenant(porteur, desc.get("contenant_index"), desc.get("contenant_item_id"))
	return transmission.emplacement_sac(porteur)


@transmission_router.post("/transmettre")
def transmettre(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	acteur, principal = _acteur(current_user, body)
	resolus = {acteur["_id"]: acteur, principal["_id"]: principal}
	source = _emplacement(body.get("source"), principal, acteur, resolus)
	cible = _emplacement(body.get("cible"), principal, acteur, resolus)
	# Même garde que la fenêtre 👜 : on ne fouille pas un contenant en plein combat.
	if "contenant" in (source["genre"], cible["genre"]):
		_refuser_en_combat(current_user, principal)

	au_sol = principal.get("objets_au_sol") or []
	ok, code, raison, ref = transmission.transmettre(
		source, cible, au_sol, body.get("index"), body.get("item_id"), get_doc, int(time.time()))
	if not ok:
		raise HTTPException(status_code=code, detail=raison)
	principal["objets_au_sol"] = au_sol

	# Docs touchés, CIBLE d'abord et autoritative (409 : rien n'est persisté) ; les autres en
	# best-effort — même séquence que le ramassage pour un autre porteur. Identité (`is`).
	touches = []
	for e in (cible, source):
		doc = principal if e["genre"] == "sol" else e["porteur"]
		if not any(doc is d for d in touches):
			touches.append(doc)
	if save_doc(touches[0]) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	for doc in touches[1:]:
		if save_doc(doc) is None:
			print(f"transmettre : échec de sauvegarde de {doc.get('_id')}")

	payload = _inventory_payload(acteur, principal)
	# « 📖 Apprendre » de chaque SAC qui a bougé (un grimoire rangé ou posé est inerte) ;
	# le client n'applique un bloc qu'à la fiche de son `id` (`_appliquerFiche`).
	payload["fiches"] = [f for e in (source, cible) if e["genre"] == "sac"
						 if (f := _fiche_payload(e["porteur"]))]
	doc = resolve_item_ref(ref) or {}
	payload["transmis"] = {"nom": doc.get("nom") or item_ref_id(ref), "icon": doc.get("icon", ""),
						   "poids": round(item_ref_weight(ref), 2)}
	return payload

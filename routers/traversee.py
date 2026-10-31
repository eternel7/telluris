# routers/traversee.py
# Traversée maritime en cours : le navire avance d'UNE case par appel (`/api/traversee/avancer`),
# appelé en boucle par le mode voyage de /play. Le passage se paie au capitaine, service PNJ
# `traversee` (routers/pnj.py) ; la logique est pure dans utils/traversee.py.
#
# Pattern de routers/user.py : get_selected_character → muter → save_doc is None ⇒ 409. Le
# DÉBARQUEMENT passe par `_effets_arrivee`, la branche « lien » de `move_character` : arriver
# au port par la mer, c'est arriver comme par la porte (quêtes de visite, XP de découverte,
# escortes, tour de monde…).

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException

from db.config import get_doc, save_doc
from models import character_stats
from utils.auth import get_current_user
from utils.characters import get_selected_character, lieu_label, marquer_joue
from utils import consommables
from utils import quetes
from utils import transport
from utils import traversee
from routers.user import (
	_effets_arrivee, _apply_world_turn_regen, _apply_world_turn_groupe, _auras_du_groupe,
	_vitals_payload, _zone_event_payload, _echecs_payload,
)

traversee_router = APIRouter()


def nom_port(route: dict) -> str:
	"""Le nom du port d'arrivée tel qu'on le dit : la CITÉ des quais d'arrivée (« Douvres »),
	repli sur le label des quais eux-mêmes."""
	arrivee = get_doc((route.get("arrivee") or {}).get("lieu", "")) or {}
	parent = get_doc(arrivee.get("lieu_parent", "")) if arrivee.get("lieu_parent") else None
	return lieu_label(parent or arrivee, (route.get("arrivee") or {}).get("lieu", ""))


@traversee_router.post("/traversee/avancer")
async def traversee_avancer(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Une case de plus. En mer : rencontre éventuelle (combat seul, comme un pas à terre).
	Sur la dernière case : débarquement sur les quais d'arrivée, `arrive: true`."""
	if not current_user:
		raise HTTPException(status_code=401, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")
	if not traversee.en_mer(character):
		raise HTTPException(status_code=409, detail="Vous n'êtes pas en mer.")
	route = get_doc(character["traversee"].get("route", ""))
	if not traversee.est_route(route):
		raise HTTPException(status_code=409, detail="Route maritime introuvable.")

	if traversee.avancer(character, route) == "arrivee":
		destination = route["arrivee"]["lieu"]
		lieu_doc = get_doc(destination)
		if not lieu_doc:
			raise HTTPException(status_code=409, detail="Port d'arrivée introuvable.")
		pos = traversee.debarquer(character, route)
		payload = _effets_arrivee(character, destination, pos, lieu_doc)
		payload["arrive"] = True
		payload["port"] = nom_port(route)
		return payload

	etat = character["traversee"]
	zone_defs = {z: get_doc(z) for z in traversee.zones_de_route(route)}
	zone_event = traversee.evenement_etape(route, etat["etape"], {k: v for k, v in zone_defs.items() if v})
	# Courses de transport échues (expiration paresseuse : pas de tick de fond).
	transports_echoues = transport.traiter_expirations(
		character, quetes.now_epoch(), get_doc, save_doc)
	compagnons, montures_groupe = _auras_du_groupe(character)
	_apply_world_turn_regen(character)
	marquer_joue(character)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	_apply_world_turn_groupe(character, 0, compagnons, montures_groupe)
	return {
		"arrive": False,
		"position": character["position"],
		"etape": etat["etape"],
		"total": traversee.total_etapes(route),
		"zone_event": _zone_event_payload(zone_event),
		"vitals": _vitals_payload(character),
		"effets_actifs": consommables.effets_actifs_payload(character),
		"transports_echoues": _echecs_payload(transports_echoues),
	}


def payload_play(character: dict) -> dict | None:
	"""Bloc `TRAVERSEE` injecté par /play (None à terre)."""
	if not traversee.en_mer(character):
		return None
	route = get_doc(character["traversee"].get("route", ""))
	if not traversee.est_route(route):
		return None
	return traversee.payload_client(character, route, nom_port(route),
									character_stats.TRAVERSEE_PAS_MS)

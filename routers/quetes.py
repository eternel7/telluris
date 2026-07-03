# routers/quetes.py
# Endpoints du tableau de quêtes d'une guilde (`categorie:"guilde_aventurier"`).
# Le moteur (utils/quetes.py) génère/complète les offres à partir du lieu PARENT ;
# ici on gère l'interaction joueur : consulter le tableau, accepter, terminer, abandonner.
# Pattern calqué sur routers/user.py : get_selected_character → muter → save_doc is None ⇒ 409.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre,
	resolve_item_ref, charge_max_of,
)
from utils import quetes
from utils import focalisation

quetes_router = APIRouter()

GUILDE_CATEGORIE = "guilde_aventurier"


def _guild_lieu(character: dict) -> dict:
	"""Doc du lieu courant si c'est une guilde d'aventuriers ; 403 sinon."""
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or lieu_doc.get("categorie") != GUILDE_CATEGORIE:
		raise HTTPException(status_code=403, detail="Vous n'êtes pas dans une guilde d'aventuriers.")
	return lieu_doc


def _offre_view(o: dict) -> dict:
	"""Vue d'une offre du tableau pour le client (prix éclaté en bourse + nom de cible)."""
	obj = o.get("objectif", {})
	rec = o.get("recompenses", {}) or {}
	purse = cuivre_to_purse(rec.get("cuivre", 0))
	return {
		"id": o.get("_id"),
		"source": o.get("source", "genere"),
		"titre": o.get("titre", "—"),
		"description": o.get("description", ""),
		"rang": o.get("rang", "F"),
		"objectif": obj,
		"cible_nom": quetes._cible_nom(obj),
		"recompenses": {
			"xp": rec.get("xp", 0),
			"or": purse["or"],
			"argent": purse["argent"],
			"cuivre": purse["cuivre"],
		},
	}


def _board_payload(character: dict, lieu_doc: dict) -> dict:
	"""Offres du tableau + quêtes actives (détaillées) de ce donneur + bourse."""
	offres = quetes.remplir_tableau(lieu_doc)
	giver = lieu_doc.get("_id")
	actives = [
		quetes.quete_detail(character, q)
		for q in character.get("quetes_actives", [])
		if q.get("giver") == giver
	]
	# Détails complets (tous donneurs) pour rafraîchir l'onglet 📜 de la fiche côté client.
	fiche_actives, fiche_terminees = quetes.fiche_details(character)
	return {
		"offres": [_offre_view(o) for o in offres],
		"actives": actives,
		"fiche_actives": fiche_actives,
		"fiche_terminees": fiche_terminees,
		"lieu_parent": lieu_doc.get("lieu_parent"),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		# État de la focalisation pour resynchroniser les boutons 🎯 côté client.
		"focalisation": focalisation.payload_client(character, get_doc),
	}


@quetes_router.get("/quetes/board")
async def quetes_board(current_user: Annotated[dict, Depends(get_current_user)]):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)
	return _board_payload(character, lieu_doc)


@quetes_router.post("/quetes/accepter")
async def quetes_accepter(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)

	quete_id = body.get("quete_id")
	quete_doc = get_doc(quete_id) if quete_id else None
	if not quete_doc or quete_doc.get("type") != "quete":
		raise HTTPException(status_code=404, detail="Quête introuvable")
	if quete_doc.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Cette quête n'est pas proposée ici.")
	if quete_doc.get("statut", "offerte") != "offerte":
		raise HTTPException(status_code=409, detail="Quête déjà prise.")
	if quetes.quete_active(character, quete_id):
		raise HTTPException(status_code=409, detail="Quête déjà acceptée.")

	actives = character.get("quetes_actives", [])
	actives.append(quetes.snapshot_quete(quete_doc))
	character["quetes_actives"] = actives
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	# L'offre quitte le tableau (best-effort : un échec ici n'annule pas l'acceptation,
	# le filtre `quete_active` empêche un double-accept côté joueur).
	quete_doc["statut"] = "acceptee"
	quete_doc["accepte_par"] = character["_id"]
	save_doc(quete_doc)

	payload = _board_payload(character, lieu_doc)
	payload["accepte"] = {"titre": quete_doc.get("titre", "—")}
	return payload


@quetes_router.post("/quetes/terminer")
async def quetes_terminer(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)

	quete_id = body.get("quete_id")
	q = quetes.quete_active(character, quete_id)
	if not q:
		raise HTTPException(status_code=404, detail="Quête non active")
	if q.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Rendez-vous à la guilde qui a confié la quête.")
	if not quetes.objectif_atteint(character, q):
		raise HTTPException(status_code=422, detail="Objectif non rempli.")

	# Les collectes ont déjà été consommées au fil des dépôts (`/api/quetes/deposer`) ; le
	# turn-in ne fait que valider la progression et donner la récompense.
	recap = quetes.appliquer_recompenses(character, q)

	# Quête focalisée terminée → la focalisation tombe (même save).
	focalisation.effacer_si_quete(character, quete_id)

	# Retrait des actives + archivage (idempotence : plus dans actives → plus de turn-in).
	character["quetes_actives"] = [
		a for a in character.get("quetes_actives", []) if a.get("id") != quete_id
	]
	termine = character.get("quetes_terminees", [])
	termine.append({
		"id": q.get("id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", "F"),
		"recompenses": q.get("recompenses", {}),
		"termine_at": quetes.now_epoch(),
	})
	character["quetes_terminees"] = termine

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	payload = _board_payload(character, lieu_doc)
	payload["termine"] = {
		"titre": q.get("titre", "—"),
		"xp": recap["xp"].get("xp_gain", 0),
		"niveau_up": recap["xp"].get("niveau_up", False),
		"recompenses": q.get("recompenses", {}),
	}
	return payload


@quetes_router.post("/quetes/deposer")
async def quetes_deposer(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Dépose à la guilde les pièces de collecte portées (jusqu'au reste à faire) : les retire de
	l'inventaire et fait progresser la quête. Permet de remplir une collecte en plusieurs voyages
	sans devoir tout porter d'un coup (utile pour le bois lourd)."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)

	quete_id = body.get("quete_id")
	q = quetes.quete_active(character, quete_id)
	if not q:
		raise HTTPException(status_code=404, detail="Quête non active")
	if q.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Rendez-vous à la guilde qui a confié la quête.")
	if q.get("objectif", {}).get("type") != "collect":
		raise HTTPException(status_code=422, detail="Cette quête ne se dépose pas.")

	n = quetes.deposer_collect(character, q)
	if n <= 0:
		raise HTTPException(status_code=422, detail="Rien à déposer (aucune pièce portée ou objectif déjà atteint).")
	# Collecte complétée par ce dépôt → la focalisation tombe (même save).
	focalisation.effacer_si_objectif_atteint(character)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	payload = _board_payload(character, lieu_doc)
	payload["depose"] = {"n": n, "titre": q.get("titre", "—"), "complete": quetes.objectif_atteint(character, q)}
	# Le dépôt a retiré des pièces du sac → rafraîchir l'inventaire côté client.
	payload["slots"] = {s: resolve_item_ref(v) if v else None for s, v in character.get("slots", {}).items()}
	payload["inventaire"] = [d for r in character.get("inventaire", []) if (d := resolve_item_ref(r))]
	payload["objets_au_sol"] = [d for r in character.get("objets_au_sol", []) if (d := resolve_item_ref(r))]
	payload["charge_max"] = charge_max_of(character)
	return payload


@quetes_router.post("/quetes/abandonner")
async def quetes_abandonner(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)

	quete_id = body.get("quete_id")
	if not quetes.quete_active(character, quete_id):
		raise HTTPException(status_code=404, detail="Quête non active")
	# Quête focalisée abandonnée → la focalisation tombe (même save).
	focalisation.effacer_si_quete(character, quete_id)
	character["quetes_actives"] = [
		a for a in character.get("quetes_actives", []) if a.get("id") != quete_id
	]
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	return _board_payload(character, lieu_doc)

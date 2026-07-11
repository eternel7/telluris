# routers/pnj.py
# Endpoints des PNJ de lieu (dialogues à choix + services) et de l'intro narrative.
# La logique est pure dans utils/pnj.py (et utils/intro.py) ; ici on gère l'interaction :
# résoudre le PNJ présent, naviguer l'arbre, exécuter le service de soin (débit + PV),
# choisir la raison de la fuite. Pattern calqué sur routers/user.py :
# get_selected_character → muter → save_doc is None ⇒ 409.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, sync_equipment_bonus,
	money_to_cuivre, cuivre_to_purse,
	poids_bounds, carried_weight, charge_max_of,
)
from utils.marche import debit_character, get_relation, relation_value
from utils import pnj
from utils import intro
from routers.user import _derived_from_character, _vitals_payload, _inventory_payload

pnj_router = APIRouter()


def _pnj_du_lieu(character: dict) -> tuple[dict, dict, dict]:
	"""(entrée pnj du lieu, doc PNJ, doc lieu) du PNJ présent au lieu courant ; 404 sinon."""
	lieu_doc = get_doc(character.get("lieu", ""))
	entree = pnj.entree_pnj_active(character, lieu_doc or {})
	pnj_doc = get_doc(entree["character"]) if entree else None
	if not entree or not pnj_doc:
		raise HTTPException(status_code=404, detail="Personne à qui parler ici.")
	return entree, pnj_doc, lieu_doc


def _contexte(character: dict, pnj_doc: dict) -> dict:
	"""Contexte de dialogue avec la résolution de relation fermée sur la DB (le lieu peut
	ne pas exister → relation neutre sur doc minimal, get_relation ne sauvegarde pas)."""
	def _rel(lieu_id: str) -> int:
		lieu = get_doc(lieu_id) or {"_id": lieu_id}
		return relation_value(get_relation(character, lieu))
	return pnj.contexte_dialogue(character, pnj_doc, _rel)


@pnj_router.get("/pnj/dialogue")
async def pnj_dialogue(current_user: Annotated[dict, Depends(get_current_user)]):
	"""État initial du panneau de dialogue : PNJ présent + nœud de départ (choix filtrés)."""
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")

	entree, pnj_doc, _ = _pnj_du_lieu(character)
	contexte = _contexte(character, pnj_doc)
	depart = (pnj_doc.get("dialogue") or {}).get("noeud_depart", "accueil")
	return {
		"pnj": pnj.pnj_payload(entree, pnj_doc),
		"noeud": pnj.noeud_client(pnj_doc, depart, contexte, pnj.soin_effectif(pnj_doc, contexte)),
	}


@pnj_router.post("/pnj/dialogue/choix")
async def pnj_dialogue_choix(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...)):
	"""Résout un choix de dialogue (stateless, revalidé serveur). Body {"noeud", "choix_id"}.
	Un choix à action `{"service":"soin"}` débite et soigne ; `{"service":"don"}` remet un
	objet (contrôle de charge + débit, séquence modèle buy_item) ; un choix simple renvoie
	le nœud suivant, `noeud: null` = fin (le client ferme)."""
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")

	entree, pnj_doc, _ = _pnj_du_lieu(character)
	contexte = _contexte(character, pnj_doc)
	noeud_id = body.get("noeud")
	choix = pnj.choix_valide(pnj_doc, noeud_id, body.get("choix_id"), contexte)
	if not choix:
		raise HTTPException(status_code=422, detail="Choix de dialogue invalide.")

	soin = pnj.soin_effectif(pnj_doc, contexte)
	reponse: dict = {}

	action = choix.get("action") or {}
	if action.get("service") == "soin":
		if not soin:
			raise HTTPException(status_code=422, detail="Ce personnage ne soigne pas.")
		noeuds_soin = (pnj_doc.get("services", {}).get("soin", {}).get("noeuds", {}))
		eq = sync_equipment_bonus(character)
		derived = _derived_from_character(character, eq)
		if int(character.get("currentPV", derived.pv_max)) >= derived.pv_max:
			# PV pleins : rien débité, le PNJ le fait remarquer.
			suivant = noeuds_soin.get("inutile")
		elif soin["cout_cuivre"] > 0 and debit_character(character, soin["cout_cuivre"]) is None:
			# Bourse vide : rien débité (debit_character n'a pas mutés les fonds), rien sauvé.
			suivant = noeuds_soin.get("sans_fonds")
		else:
			pv_rendu = pnj.appliquer_soin(character, derived.pv_max, soin["fraction_pv"])
			if save_doc(character) is None:
				raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
			suivant = noeuds_soin.get("fait")
			reponse["soin"] = {
				"pv_rendu": pv_rendu,
				"gratuit": soin["gratuit"],
				"cout": soin["cout_cuivre"],
			}
		reponse["vitals"] = _vitals_payload(character)
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
	elif action.get("service") == "don":
		don = pnj.don_effectif(pnj_doc, contexte)
		if not don:
			raise HTTPException(status_code=422, detail="Ce personnage n'a rien à donner.")
		item_doc = get_doc(don["item"])
		if not item_doc:
			raise HTTPException(status_code=422, detail="Objet du don introuvable.")
		noeuds_don = (pnj_doc.get("services", {}).get("don", {}).get("noeuds", {}))
		poids_unitaire = poids_bounds(item_doc)[0]
		poids_total = poids_unitaire * don["quantite"]
		if carried_weight(character) + poids_total > charge_max_of(character):
			# Surcharge : rien donné, rien débité, le PNJ le fait remarquer.
			suivant = noeuds_don.get("trop_charge")
		elif don["cout_cuivre"] > 0 and debit_character(character, don["cout_cuivre"]) is None:
			# Bourse vide : rien débité (fonds non mutés), rien donné.
			suivant = noeuds_don.get("sans_fonds")
		else:
			pnj.appliquer_don(character, don["item"], poids_unitaire, don["quantite"])
			if save_doc(character) is None:
				raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
			suivant = noeuds_don.get("fait")
			reponse["don"] = {
				"item": don["item"],
				"nom": item_doc.get("nom"),
				"icon": item_doc.get("icon"),
				"quantite": don["quantite"],
				"gratuit": don["gratuit"],
				"cout": don["cout_cuivre"],
			}
			reponse["inventaire_payload"] = _inventory_payload(character)
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
	else:
		suivant = choix.get("next")

	if not suivant or suivant == "fin":
		reponse["noeud"] = None
	else:
		reponse["noeud"] = pnj.noeud_client(pnj_doc, suivant, contexte, soin)
	return reponse


@pnj_router.post("/intro/raison")
async def intro_raison(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...)):
	"""Persiste la raison de la fuite choisie dans l'overlay d'intro. Body {"raison": id}.
	Renvoie le texte de suite propre à la raison (affiché avant « Prendre la route »)."""
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")

	if not intro.intro_en_cours(character):
		raise HTTPException(status_code=409, detail="Aucune introduction en cours.")
	lieu_doc = get_doc(character.get("cite", "")) or {}
	raison = intro.raison_valide(lieu_doc, body.get("raison"))
	if not raison:
		raise HTTPException(status_code=422, detail="Raison inconnue.")

	character["intro"]["raison"] = raison["id"]
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	return {"raison": raison["id"], "texte_suite": raison.get("texte_suite", "")}

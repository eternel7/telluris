# routers/enigmes.py — panneau d'énigme de /play (utils/enigmes.py ; docs/conception_enigmes.md).
#
# Le SERVEUR tranche : la solution ne quitte jamais `utils/enigmes`, le client n'envoie que des
# essais et ne reçoit que `enigmes.vue_client`. L'ouverture se revérifie à CHAQUE requête
# (lieu, prérequis, conditions) : un choix de dialogue `"enigme": "enigme:…"` ne fait que
# demander au client d'ouvrir le panneau, il n'accorde rien.
#
# Les énigmes se jouent sur le personnage PRINCIPAL (aucun `compagnon_id`) : l'état vit sur
# son doc, et les compagnons ne font que commenter.

import time
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from db.config import get_doc, save_doc
from utils.auth import get_current_user
from utils.characters import get_selected_character
from utils.lieux import get_lieu_links
from utils import acces
from utils import enigmes
from utils import escorte
from utils import journal
from utils import recrutement

enigmes_router = APIRouter()


def _personnage(current_user: dict) -> dict:
	if not current_user:
		raise HTTPException(status_code=401, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")
	return character


def _enigme_ouverte(character: dict, enigme_id) -> dict:
	"""Doc de l'énigme, ouvrable ICI par ce personnage — sinon 404/403."""
	doc = get_doc(enigme_id) if isinstance(enigme_id, str) and enigme_id.startswith("enigme:") else None
	if not doc or doc.get("type") != "enigme":
		raise HTTPException(status_code=404, detail="Énigme introuvable.")
	ok, motif = enigmes.ouvrable(doc, character,
								 lambda conds: acces.clauses_remplies(character, conds, get_doc))
	if not ok:
		raise HTTPException(status_code=403, detail=motif)
	return doc


def _voix(character: dict) -> list:
	"""Qui peut commenter : les escortés (par prénom), puis les compagnons (par vocation)."""
	voix = [{"prenom": p.get("prenom", ""), "protege": True}
			for p in escorte.proteges_effectifs(character, get_doc)]
	voix += [{"prenom": c.get("prenom", ""), "vocation": c.get("voc")}
			 for c in recrutement.groupe_effectif(character, get_doc)]
	return voix


@enigmes_router.get("/enigme")
def enigme_ouvrir(current_user: Annotated[dict, Depends(get_current_user)], id: str = ""):
	character = _personnage(current_user)
	doc = _enigme_ouverte(character, id)
	return {"enigme": enigmes.vue_client(doc, character),
			"commentaires": enigmes.commentaires(doc, ["ouverture"], _voix(character))}


@enigmes_router.post("/enigme/action")
def enigme_action(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Body {"id", "action", …} — champs propres à l'action (`cle`, `positions`, `gauche`/`droite`,
	`placement`, `actives`/`ancrees`). Un essai FAUX n'est pas une erreur : 200 + remarque."""
	character = _personnage(current_user)
	doc = _enigme_ouverte(character, body.get("id"))
	deja = enigmes.est_resolue(character, doc["_id"])
	try:
		resultat = enigmes.agir(doc, character, str(body.get("action") or ""), body, int(time.time()))
	except enigmes.EssaiInvalide as exc:
		raise HTTPException(status_code=422, detail=str(exc))
	if not deja and save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	reponse = {
		"enigme": enigmes.vue_client(doc, character),
		"resultat": resultat,
		"commentaires": enigmes.commentaires(doc, resultat["evenements"], _voix(character)),
		# Onglet 📖 resynchronisé : ses notes 🧩 viennent de bouger (convention 10).
		"journal": journal.journal_payload(character, get_doc),
	}
	if resultat["resolue"] and not deja:
		# Une porte peut dépendre de `enigme_resolue` : resync des sous-lieux (convention 10).
		reponse["links"] = get_lieu_links(current_user)
	return reponse

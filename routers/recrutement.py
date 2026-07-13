# routers/recrutement.py
# Endpoints du tableau de recrutement d'un lieu recruteur (tag "recrutement" ou guilde
# d'aventuriers). Le moteur (utils/recrutement.py) génère/complète les recrues ; ici on
# gère l'interaction joueur : consulter le tableau (carte d'aventurier de la cité
# requise), embaucher (gratuit), congédier (autorisé partout, miroir de l'abandon de
# quête). Pattern calqué sur routers/quetes.py : muter → save_doc is None ⇒ 409.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc
from utils.auth import get_current_user
from utils.characters import get_selected_character, cuivre_to_purse, money_to_cuivre
from utils import recrutement
from models.character_stats import compute_character_level

recrutement_router = APIRouter()


def _lieu_recruteur(character: dict) -> dict:
	"""Doc du lieu courant s'il recrute ; 403 sinon (miroir de _guild_lieu)."""
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or not recrutement.lieu_recrute(lieu_doc):
		raise HTTPException(status_code=403, detail="Aucun tableau de recrutement ici.")
	return lieu_doc


def _recrue_view(character: dict, av: dict) -> dict:
	"""Vue d'une recrue pour le client : identité + conditions EFFECTIVES (affinité
	déduite) + mémoire du lien (`affinite` brute — None si jamais rencontrée)."""
	affinite_brute = (character.get("affinites", {}) or {}).get(av["_id"])
	return {
		"id": av["_id"],
		"prenom": av.get("prenom", ""),
		"nom": av.get("nom", ""),
		"race": av.get("race", ""),
		"voc": av.get("voc", ""),
		"sex": av.get("sex", ""),
		"rang": av.get("rang", "F"),
		"niveau": compute_character_level(av.get("xp_total", 0)),
		"specialite": av.get("specialite", ""),
		"image": av.get("image", ""),
		"exigences_effectives": recrutement.conditions_effectives(
			av, recrutement.affinite_de(character, av["_id"])),
		"affinite": affinite_brute,
		"deja_connu": av["_id"] in (character.get("compagnons_connus", {}) or {}),
	}


def _groupe_view(character: dict) -> list:
	"""Le groupe actif, avec l'état vital du compagnon (son doc est la source)."""
	out = []
	for av in recrutement.groupe_effectif(character, get_doc):
		vue = _recrue_view(character, av)
		vue["currentPV"] = av.get("currentPV", 0)
		vue["currentPM"] = av.get("currentPM", 0)
		out.append(vue)
	return out


def _appliquer_departs(character: dict) -> list:
	"""Check paresseux des départs volontaires (affinité < seuil) : persiste les docs
	mutés (compagnons puis personnage) et renvoie les noms partis pour le toast."""
	partis = recrutement.departs_volontaires(character, get_doc)
	if partis:
		for av in partis:
			save_doc(av)
		save_doc(character)
	return [f"{av.get('prenom', '')} {av.get('nom', '')}".strip() for av in partis]


def _payload(character: dict, recrues: list | None = None) -> dict:
	payload = {
		"groupe": _groupe_view(character),
		"plafond": recrutement.taille_max_groupe(),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"affinites_detail": recrutement.affinites_detail_payload(character, get_doc),
	}
	if recrues is not None:
		payload["recrues"] = [_recrue_view(character, av) for av in recrues]
	return payload


@recrutement_router.get("/recrutement/board")
async def recrutement_board(current_user: Annotated[dict, Depends(get_current_user)]):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _lieu_recruteur(character)
	ok, raison = recrutement.acces_autorise(character, lieu_doc)
	if not ok:
		raise HTTPException(status_code=403, detail=raison)

	departs = _appliquer_departs(character)
	recrues = recrutement.remplir_tableau_recrues(lieu_doc, character)
	payload = _payload(character, recrues)
	if departs:
		payload["departs"] = departs
	return payload


@recrutement_router.post("/recrutement/embaucher")
async def recrutement_embaucher(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _lieu_recruteur(character)
	ok, raison = recrutement.acces_autorise(character, lieu_doc)
	if not ok:
		raise HTTPException(status_code=403, detail=raison)

	av_id = body.get("aventurier_id")
	av = get_doc(av_id) if av_id else None
	if not av or av.get("type") != "aventurier":
		raise HTTPException(status_code=404, detail="Recrue introuvable")
	if av.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Cette recrue n'est pas proposée ici.")

	ok, raison = recrutement.embaucher(character, av)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	# La recrue quitte le tableau (best-effort : un échec ici n'annule pas l'embauche,
	# groupe_effectif filtre par embauche_par — pattern acceptation de quête).
	save_doc(av)

	recrues = recrutement.remplir_tableau_recrues(lieu_doc, character)
	payload = _payload(character, recrues)
	payload["embauche"] = {"nom": f"{av.get('prenom', '')} {av.get('nom', '')}".strip()}
	return payload


@recrutement_router.post("/recrutement/congedier")
async def recrutement_congedier(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Congédier est autorisé PARTOUT (miroir de l'abandon de quête) : l'onglet 🤝 est
	atteignable n'importe où. Le doc du compagnon est CONSERVÉ (mémoire du lien)."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	av_id = body.get("aventurier_id")
	av = get_doc(av_id) if av_id else None
	if not av or av.get("type") != "aventurier":
		raise HTTPException(status_code=404, detail="Compagnon introuvable")

	ok, raison = recrutement.congedier(character, av)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	save_doc(av)  # best-effort, comme l'embauche

	# À un lieu recruteur → tableau à jour ; ailleurs → payload léger (groupe + 👥).
	lieu_doc = get_doc(character.get("lieu", ""))
	recrues = None
	if lieu_doc and recrutement.lieu_recrute(lieu_doc) and recrutement.acces_autorise(character, lieu_doc)[0]:
		recrues = recrutement.remplir_tableau_recrues(lieu_doc, character)
	payload = _payload(character, recrues)
	payload["congedie"] = {"nom": f"{av.get('prenom', '')} {av.get('nom', '')}".strip()}
	return payload

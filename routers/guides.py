# routers/guides.py
# Guides locaux : engager et congédier À L'AUBERGE, interroger et renouveler PARTOUT.
# Le moteur est dans utils/guides.py. Pattern de routers/montures.py : gardes, débit APRÈS les
# gardes, `save_doc is None` ⇒ 409, le bloc recalculé dans chaque réponse (Convention §10).

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, delete_doc, find_docs
from utils.auth import get_current_user
from utils.characters import get_selected_character, cuivre_to_purse, money_to_cuivre, lieu_label
from utils.marche import debit_character
from utils import auberge, escorte, focalisation, guides, montures, quetes, recrutement, transport
from routers.montures import _monture_view

guides_router = APIRouter()


def _perso(current_user: dict) -> dict:
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	return character


def _a_l_auberge(character: dict) -> dict:
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or not auberge.lieu_est_taverne(lieu_doc):
		raise HTTPException(status_code=403, detail="Un guide s'engage et se congédie dans une auberge.")
	return lieu_doc


def _guide(character: dict) -> dict:
	guide = guides.guide_de(character, get_doc)
	if guide is None:
		raise HTTPException(status_code=404, detail="Aucun guide ne vous accompagne.")
	return guide


def _offre_view(g: dict, regles: dict, index: dict) -> dict:
	contrat = guides.vue_contrat(g, regles)
	return {
		"id": g["_id"], "prenom": g.get("prenom", ""), "nom": g.get("nom", ""),
		"race": g.get("race", ""), "sex": g.get("sex", ""), "image": g.get("image", ""),
		"image_base": escorte.image_protege(g.get("image", ""))[0],
		"presentation": guides.replique(g, regles, "presentation"),
		"zone_nom": lieu_label(index.get((g.get("guide") or {}).get("zone")) or {}, ""),
		**montures.vitaux_de(g),
		**contrat,
	}


def _resync(character: dict) -> dict:
	"""Ce que tout écran doit relire après un geste : bourse, cap, guide."""
	lieu_doc = get_doc(character.get("lieu", "")) or {}
	guide = guides.guide_de(character, get_doc)
	return {
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"focalisation": focalisation.payload_client(character, get_doc),
		"guidage": focalisation.guidage(character, lieu_doc, find_docs, get_doc),
		"guide": _monture_view(guide) if guide else None,
	}


def _tableau(character: dict, lieu_doc: dict) -> dict:
	regles = guides.regles_de(get_doc)
	index = guides.index_lieux(find_docs)
	races = (get_doc("rules:races") or {}).get("value") or []
	offres = guides.remplir_tableau(lieu_doc, index, regles, races, recrutement.portraits_disponibles(),
									find_docs, save_doc, delete_doc, get_doc_fn=get_doc,
									portraits_guide=guides.portraits_guide_disponibles())
	return {"offres": [_offre_view(o, regles, index) for o in offres], **_resync(character)}


@guides_router.get("/guides/tableau")
async def tableau(current_user: Annotated[dict, Depends(get_current_user)]):
	character = _perso(current_user)
	return _tableau(character, _a_l_auberge(character))


@guides_router.post("/guides/engager")
async def engager(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character = _perso(current_user)
	lieu_doc = _a_l_auberge(character)
	if guides.guide_de(character, get_doc):
		raise HTTPException(status_code=409, detail="Un guide vous accompagne déjà.")
	guide = get_doc(body.get("guide_id") or "")
	# ⚠️ L'offre appartient à CETTE auberge : un id forgé ne doit pas engager un guide d'ailleurs.
	if not guide or not montures.est_guide(guide) or guide.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Ce guide n'est pas proposé ici.")
	regles = guides.regles_de(get_doc)
	cout, _ = guides.forfait(guides.metier_de(guide, regles))
	if money_to_cuivre(character) < cout:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer son forfait.")
	ok, raison = guides.engager(character, guide, regles)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if debit_character(character, cout) is None:
		raise HTTPException(status_code=409, detail="Fonds insuffisants.")
	if save_doc(guide) is None or save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	return _tableau(character, lieu_doc)


@guides_router.post("/guides/congedier")
async def congedier(current_user: Annotated[dict, Depends(get_current_user)]):
	character = _perso(current_user)
	lieu_doc = _a_l_auberge(character)
	guide = _guide(character)
	ok, raison = guides.congedier(character, guide)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	save_doc(guide)
	return _tableau(character, lieu_doc)


@guides_router.post("/guides/renouveler")
async def renouveler(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Un nouveau forfait, PARTOUT : le guide n'abandonne personne en route."""
	character = _perso(current_user)
	guide = _guide(character)
	regles = guides.regles_de(get_doc)
	cout, _ = guides.forfait(guides.metier_de(guide, regles))
	if debit_character(character, cout) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer son forfait.")
	guides.ajouter_forfait(guide, regles)
	if save_doc(character) is None or save_doc(guide) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	return {"replique": guides.replique(guide, regles, "renouvele"), **_resync(character)}


@guides_router.get("/guides/dialogue")
async def dialogue(current_user: Annotated[dict, Depends(get_current_user)]):
	character = _perso(current_user)
	guide = _guide(character)
	regles = guides.regles_de(get_doc)
	if not guides.actif(guide):
		return {"replique": guides.replique(guide, regles, "epuise"), "sujets": [], **_resync(character)}
	sujets = guides.sujets(character, guide, guides.index_lieux(find_docs),
						   focalisation.charger_graphe(find_docs), regles)
	return {"replique": guides.replique(guide, regles, "accueil"), "sujets": sujets, **_resync(character)}


def _cap_quete(character: dict, guide: dict, regles: dict, quete_id: str, index: dict, graphe: dict) -> tuple[str, list]:
	"""Réponse à « peux-tu m'aider pour cette quête ? ». Renvoie (réplique, suggestions)."""
	q = quetes.quete_active(character, quete_id)
	if not q:
		raise HTTPException(status_code=404, detail="Quête introuvable dans vos quêtes actives")
	piste = guides.piste_quete(q, guide, character.get("lieu"), index, graphe, regles)
	if not piste:
		return guides.replique(guide, regles, "inconnu", quete=q.get("titre", "")), []
	nom = lieu_label(index.get(piste["lieu"]) or {}, piste["lieu"])
	if piste["distance"] == 0:
		# Déjà sur le terrain : le 🎯 de la quête, s'il a un effet, tient lieu de cap.
		if focalisation.quete_focalisable(q):
			character["focalisation"] = {"type": "quete", "cible": quete_id,
										 "posee_at": quetes.now_epoch()}
		return guides.replique(guide, regles, "ici", lieu=nom, quete=q.get("titre", "")), []
	guides.poser_cap(character, guide, piste["lieu"], quete_id)
	return guides.replique(guide, regles, "accepte", lieu=nom, quete=q.get("titre", "")), []


def _cap_saisie(character: dict, guide: dict, regles: dict, saisie, index: dict, graphe: dict) -> tuple[str, list]:
	"""Réponse à « connais-tu tel lieu ? ». Texte borné ici, écrit en `textContent` côté client."""
	nom = transport.nettoyer_recherche_lieu(saisie)
	trouve = transport.chercher_parmi(nom, guides.lieux_connus(guide, index, regles))
	if trouve.get("exact"):
		lieu_id, label = trouve["exact"]
		if lieu_id == character.get("lieu"):
			return guides.replique(guide, regles, "ici", lieu=label), []
		if lieu_id not in focalisation.distances_depuis(graphe, character.get("lieu")):
			return guides.replique(guide, regles, "sans_chemin", lieu=label), []
		guides.poser_cap(character, guide, lieu_id)
		return guides.replique(guide, regles, "accepte", lieu=label), []
	if trouve.get("suggestions"):
		return guides.replique(guide, regles, "proche", recherche=nom), trouve["suggestions"]
	return guides.replique(guide, regles, "inconnu", quete=nom), []


@guides_router.post("/guides/demander")
async def demander(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Body {quete_id} ou {saisie}. Pose le cap et renvoie la réponse du guide."""
	character = _perso(current_user)
	guide = _guide(character)
	regles = guides.regles_de(get_doc)
	if not guides.actif(guide):
		raise HTTPException(status_code=409, detail="Son forfait est épuisé : il ne vous indique plus rien.")
	index = guides.index_lieux(find_docs)
	graphe = focalisation.charger_graphe(find_docs)
	if body.get("quete_id"):
		texte, suggestions = _cap_quete(character, guide, regles, body["quete_id"], index, graphe)
	else:
		texte, suggestions = _cap_saisie(character, guide, regles, body.get("saisie"), index, graphe)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit d'écriture, réessayez")
	return {"replique": texte, "suggestions": suggestions, **_resync(character)}

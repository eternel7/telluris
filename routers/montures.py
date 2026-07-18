# routers/montures.py
# Endpoints de l'étable : consulter les montures en vente, en acheter une, en relâcher
# une. Le moteur (utils/montures.py) tire les stats et calcule les capacités ; ici on
# gère l'interaction joueur et l'argent. Pattern calqué sur routers/recrutement.py :
# muter → save_doc is None ⇒ 409, doc principal AUTORITATIF sauvé en premier.
#
# Il n'y a PAS d'endpoint d'inventaire ici : le sac d'une monture se sert par
# `GET /api/groupe` et `POST /api/groupe/transferer` (routers/recrutement.py), qui sont
# porteur-agnostiques — une monture n'y est qu'un porteur de plus.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre, carried_weight,
)
from utils.marche import debit_character
from utils import montures

montures_router = APIRouter()


def _acces_etable(current_user: dict) -> tuple[dict, dict]:
	"""(personnage, lieu) pour toute opération sur l'étable : personnage sélectionné (404),
	lieu vendeur (403). Prélude commun au board et à l'achat — miroir de `_acces_tableau`,
	sans contrôle de carte : acheter une bête ne demande pas d'être membre d'une guilde."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or not montures.lieu_vend_montures(lieu_doc):
		raise HTTPException(status_code=403, detail="Aucune monture à vendre ici.")
	return character, lieu_doc


def _offre_view(espece_doc: dict) -> dict:
	"""Vue d'une monture EN VENTE. `charge_estimee` est une fourchette : les stats sont
	tirées à l'achat, on ne peut donc pas promettre une capacité exacte — mais le joueur
	doit pouvoir comparer deux espèces avant de payer."""
	attrs = espece_doc.get("base_attributes", {}) or {}
	f_borne = attrs.get("F") or {}
	mult = montures.charge_mult(espece_doc)
	f_min = int(f_borne.get("min", 0) or 0)
	f_max = int(f_borne.get("max", f_min) or f_min)
	return {
		"espece": espece_doc.get("_id", ""),
		"nom": espece_doc.get("nom", ""),
		"image": espece_doc.get("image", ""),
		"description": espece_doc.get("description", ""),
		"prix": montures.prix_de(espece_doc),
		"charge_mult": mult,
		"charge_min": int(f_min * 5 * mult),
		"charge_max": int(f_max * 5 * mult),
	}


def _monture_view(m: dict) -> dict:
	"""Vue d'une monture POSSÉDÉE. Mêmes clés que `_recrue_view` là où le client les
	partage (`id`/`nom`/`image`/vitaux) : les deux alimentent la même carte de personnage.
	`est_monture` permet au client de la ranger dans son propre groupe et de lui offrir
	« Relâcher » plutôt que « Congédier »."""
	return {
		"id": m["_id"],
		"nom": m.get("nom", "Monture"),
		"prenom": "",           # la carte affiche « prenom nom » : une bête n'a qu'un nom
		"espece": m.get("espece", ""),
		"image": m.get("image", ""),
		# Une monture est illustrée par l'image de son ESPÈCE, servie par le mount
		# /monsters — pas par /characters comme un portrait de personnage.
		"image_base": "/monsters",
		"est_monture": True,
		"charge": round(carried_weight(m), 2),
		"charge_max": montures.charge_max_porteur(m),
		**montures.vitaux_de(m),
	}


def _payload(character: dict, lieu_doc: dict | None = None) -> dict:
	payload = {
		"montures": [_monture_view(m) for m in montures.montures_effectives(character, get_doc)],
		"plafond": montures.plafond_montures(),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}
	if lieu_doc is not None:
		offres = []
		for espece_id in montures.especes_offertes(lieu_doc):
			espece_doc = get_doc(espece_id)
			if espece_doc:          # référence morte ignorée, comme add_character
				offres.append(_offre_view(espece_doc))
		payload["offres"] = offres
	return payload


@montures_router.get("/montures/etable")
async def etable_board(current_user: Annotated[dict, Depends(get_current_user)]):
	character, lieu_doc = _acces_etable(current_user)
	return _payload(character, lieu_doc)


@montures_router.post("/montures/acheter")
async def acheter_monture(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Achète une monture proposée par CE lieu. La bête est créée à l'achat (ses stats
	sont tirées à ce moment) : deux chevaux du même relais ne se valent pas."""
	character, lieu_doc = _acces_etable(current_user)

	espece_id = body.get("espece")
	if not espece_id or espece_id not in montures.especes_offertes(lieu_doc):
		raise HTTPException(status_code=403, detail="Cette monture n'est pas proposée ici.")
	espece_doc = get_doc(espece_id)
	if not espece_doc:
		raise HTTPException(status_code=404, detail="Espèce introuvable")

	ok, raison = montures.peut_acquerir(character, espece_doc, get_doc)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)

	monture = montures.creer_monture(espece_doc, lieu_doc, character)
	if monture is None:
		raise HTTPException(status_code=422, detail="Cette monture ne peut pas être créée.")
	# Débit APRÈS toutes les gardes : on ne prend l'argent que si la bête part avec vous.
	if debit_character(character, montures.prix_de(espece_doc)) is None:
		raise HTTPException(status_code=409, detail="Fonds insuffisants.")
	montures.acquerir(character, monture)

	# La monture d'abord : si la sauvegarde du principal échoue ensuite, on laisse un doc
	# orphelin (invisible, `montures_effectives` filtre sur l'index du character) plutôt
	# qu'un index pointant dans le vide.
	if save_doc(monture) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	payload = _payload(character, lieu_doc)
	payload["achetee"] = _monture_view(monture)
	return payload


@montures_router.post("/montures/relacher")
async def relacher_monture(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Rend sa liberté à une monture — autorisé PARTOUT (miroir du congédiement). Refusé
	tant qu'elle porte quelque chose : la relâcher chargée ferait disparaître le butin."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	monture_id = body.get("monture_id") or ""
	m = next(
		(x for x in montures.montures_effectives(character, get_doc) if x.get("_id") == monture_id),
		None,
	)
	if m is None:
		raise HTTPException(status_code=403, detail="Cette monture n'est pas la vôtre.")

	ok, raison = montures.relacher(character, m)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	save_doc(m)   # best-effort, comme le congédiement

	payload = _payload(character)
	payload["relachee"] = m.get("nom", "Monture")
	return payload

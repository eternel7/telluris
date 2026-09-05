# routers/scriptorium.py
# Endpoint du scriptorium : l'écrit personnel (papier+encre+plume → livre TRANSPORTABLE).
#
# ⚠️ La production automatique de livres (sort/recette/carte) N'A PAS D'ENDPOINT ICI : elle
# est injectée dans le tick d'atelier existant (utils.marche.tick_atelier, via
# utils.scriptorium.recettes_effectives), aux mêmes 4 sites que tout autre lieu marchand —
# main.py (visite), routers/user.py (achat), routers/auberge.py (nuit),
# utils/marche.py::convertir_apres_achat (vente/rachat). Ces livres s'achètent comme un
# grimoire, par le flux marchand déjà existant (buy_item).
#
# Pattern calqué sur routers/auberge.py::poser_annonce : MÊME règle d'écriture (papier+encre
# consommés, plume outil — Convention « une seule règle d'écriture dans tout le jeu ») et
# même mécanique d'écrivain (`ecrivain_id`, PAS `compagnon_id` — Convention §1).

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc
from models import character_stats
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, carried_weight, charge_max_of, item_ref_weight, resolve_item_ref,
)
from utils import auberge
from utils import scriptorium
# ⚠️ Sens d'import : `routers/scriptorium` → `routers/user`, jamais l'inverse (précédent :
# `routers/auberge` → `routers/user`). `routers/user` n'importe pas ce module.
from routers.user import _inventory_payload

scriptorium_router = APIRouter()


def _acces_scriptorium(current_user: dict) -> tuple[dict, dict]:
	"""(personnage, lieu) pour toute opération de scriptorium : personnage sélectionné (404),
	lieu qui EST un scriptorium (403). Miroir exact de `routers/auberge.py::_acces_auberge`."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or not scriptorium.lieu_est_scriptorium(lieu_doc):
		raise HTTPException(status_code=403, detail="Il n'y a pas de scriptorium ici.")
	return character, lieu_doc


def _ecrivain(character: dict, body: dict) -> tuple[dict, list]:
	"""Qui tient la plume — MIROIR EXACT de `routers/auberge.py::_ecrivain` : `ecrivain_id`
	et non `compagnon_id` (Convention §1), preuve via `auberge.ecrivains`
	(→ `expedition.membres`, jamais une monture)."""
	ecrivain_id = (body or {}).get("ecrivain_id") or ""
	if not ecrivain_id or ecrivain_id == character.get("_id"):
		return character, None
	membres = auberge.ecrivains(character, get_doc)
	membre = next((m for m in membres if m.get("_id") == ecrivain_id), None)
	if membre is None:
		raise HTTPException(status_code=403, detail="Ce compagnon n'écrit pas pour vous.")
	return membre, membres


@scriptorium_router.get("/scriptorium")
async def salle_scriptorium(current_user: Annotated[dict, Depends(get_current_user)]):
	"""État du panneau d'écriture : qui peut écrire, et avec quoi."""
	character, _ = _acces_scriptorium(current_user)
	membres = auberge.ecrivains(character, get_doc)
	return {
		"ecrivains": [auberge.ecrivain_view(get_doc, m, character) for m in membres],
		"longueur_max": int(character_stats.SCRIPTORIUM_LIVRE_LONGUEUR_MAX),
	}


@scriptorium_router.post("/scriptorium/ecrire")
async def ecrire_scriptorium(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Écrit un manuscrit personnel. Exige papier, encre ET plume d'oie (même règle que
	l'annonce d'auberge), DÉPENSE le papier et l'encre, et produit un item TRANSPORTABLE —
	contrairement au tableau d'auberge, qui produit un message public.

	⚠️ Un COMPAGNON qui a ses propres fournitures peut écrire à sa place (`ecrivain_id`), et
	le manuscrit porte alors SA signature (`auteur_nom`, dénormalisé comme pour un message).
	Chacun écrit avec SON sac : contrôle ET dépense portent sur le seul écrivain."""
	character, lieu_doc = _acces_scriptorium(current_user)
	ecrivain, membres = _ecrivain(character, body)
	soi = ecrivain is character

	manquantes = auberge.fournitures_manquantes(get_doc, [ecrivain])
	if manquantes:
		libelles = {"papier": "du papier", "encre": "de l'encre",
					"plume_a_ecrire": "une plume à écrire"}
		sujet = ("Il vous manque " if soi
				 else f"Il manque à {auberge.nom_affichable(ecrivain)} ")
		raise HTTPException(
			status_code=422,
			detail=sujet + ", ".join(libelles.get(m, m) for m in manquantes) + ".")

	texte = auberge.nettoyer_texte(body.get("texte"),
								   int(character_stats.SCRIPTORIUM_LIVRE_LONGUEUR_MAX))
	if not texte:
		raise HTTPException(status_code=422, detail="Un manuscrit vide ne s'écrit pas.")

	poids_livre = item_ref_weight(scriptorium.ITEM_LIVRE_ECRIT_ID)
	if carried_weight(ecrivain) + poids_livre > charge_max_of(ecrivain):
		raise HTTPException(status_code=409, detail="Trop chargé pour emporter un livre de plus.")

	# ⚠️ MÊME SÉQUENCE que `consommer`/`poser_annonce` : retrait en MÉMOIRE, PUIS sauvegarde.
	# Un échec de save laisse donc le sac intact en base.
	retire, _ = auberge.retirer_fournitures(get_doc, ecrivain)
	if not retire:
		raise HTTPException(status_code=409, detail="Les fournitures viennent de manquer.")

	ref = scriptorium.nouveau_livre(ecrivain, texte)
	ecrivain.setdefault("inventaire", []).append(ref)

	if save_doc(ecrivain) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	payload = {
		"livre": resolve_item_ref(ref),
		"consomme": list(auberge.FOURNITURES_CONSOMMEES),
		"ecrivain": auberge.nom_affichable(ecrivain),
		"ecrivain_compagnon": not soi,
	}
	# ⚠️ Le SAC vient de changer (Convention §10), publié SEULEMENT quand c'est le principal
	# qui a écrit — sinon `_applyInventoryPayload` mélangerait durablement les deux sacs
	# (Convention §1). Le sac du principal, lui, n'a pas bougé.
	if soi:
		payload["inventaire_payload"] = _inventory_payload(character)
	return payload

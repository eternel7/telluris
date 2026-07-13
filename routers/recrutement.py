# routers/recrutement.py
# Endpoints du tableau de recrutement d'un lieu recruteur (tag "recrutement" ou guilde
# d'aventuriers). Le moteur (utils/recrutement.py) génère/complète les recrues ; ici on
# gère l'interaction joueur : consulter le tableau (carte d'aventurier de la cité
# requise), embaucher (gratuit), congédier (autorisé partout, miroir de l'abandon de
# quête). Pattern calqué sur routers/quetes.py : muter → save_doc is None ⇒ 409.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, find_docs
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre,
	carried_weight, charge_max_of, resolve_item_ref, item_ref_weight,
)
from utils import recrutement
from utils import fiche as fiche_util
# Le sac d'un compagnon se sert exactement comme celui du joueur (mêmes refs, mêmes docs
# résolus) : on réutilise le payload d'inventaire de routers/user.py plutôt que de le
# recopier — précédent : routers/combat.py importe déjà `_take_ref` du même module.
from routers.user import _inventory_payload
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
		vue.update(recrutement.vitaux_de(av))
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


# ── Gestion du groupe hors combat (panneau 👥) ────────────────────────────────────
#
# Un doc `aventurier:*` n'a PAS de `user_id` : sa seule preuve d'appartenance est
# `groupe_effectif` (statut « embauche » + `embauche_par`). C'est le garde de tous les
# endpoints ci-dessous — miroir de `_acteur` (routers/user.py), qui protège de la même
# façon les actions de fiche menées pour le compte d'un compagnon.

def _compagnon(character: dict, av_id: str) -> dict:
	av = next(
		(a for a in recrutement.groupe_effectif(character, get_doc) if a.get("_id") == av_id),
		None,
	)
	if av is None:
		raise HTTPException(status_code=403, detail="Ce compagnon ne fait pas partie de votre groupe")
	return av


def _charge_view(porteur: dict) -> dict:
	return {"charge": round(carried_weight(porteur), 2), "charge_max": charge_max_of(porteur)}


@recrutement_router.get("/groupe")
async def groupe_etat(current_user: Annotated[dict, Depends(get_current_user)]):
	"""État du groupe pour le panneau 👥, disponible PARTOUT (contrairement au board de
	recrutement, qui exige un lieu recruteur et la carte d'aventurier)."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	departs = _appliquer_departs(character)
	payload = _payload(character)
	payload["principal"] = {
		"id": character["_id"],
		"prenom": character.get("prenom", ""),
		"nom": character.get("nom", ""),
		"image": character.get("image", ""),
		**_charge_view(character),
		"inventaire": [d for r in character.get("inventaire", []) if (d := resolve_item_ref(r))],
	}
	# Sacs des compagnons : le panneau affiche deux inventaires côte à côte et doit pouvoir
	# griser une flèche de transfert AVANT l'appel serveur (même arithmétique que peut_porter).
	payload["sacs"] = {
		av["_id"]: {
			**_charge_view(av),
			"inventaire": [d for r in av.get("inventaire", []) if (d := resolve_item_ref(r))],
		}
		for av in recrutement.groupe_effectif(character, get_doc)
	}
	if departs:
		payload["departs"] = departs
	return payload


@recrutement_router.get("/groupe/compagnon/{av_id:path}")
async def groupe_compagnon(
	current_user: Annotated[dict, Depends(get_current_user)],
	av_id: str,
):
	"""Fiche complète d'un compagnon : de quoi rebasculer le panneau de fiche du client sur
	lui (mêmes clés que le contexte de /play, cf. utils/fiche.bloc_fiche). Le SOL affiché
	reste celui du personnage principal — un compagnon n'a ni lieu ni position."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	av = _compagnon(character, av_id)

	race = fiche_util.race_de(av, get_doc)
	payload = {
		"id": av["_id"],
		"prenom": av.get("prenom", ""),
		"nom": av.get("nom", ""),
		"sex": av.get("sex", ""),
		"race": av.get("race", ""),
		"race_nom": race.get("nom", av.get("race", "")),
		"voc": av.get("voc", ""),
		"rang": av.get("rang", "F"),
		"specialite": av.get("specialite", ""),
		"image": av.get("image", ""),
		"niveau": compute_character_level(av.get("xp_total", 0)),
		"xp_total": av.get("xp_total", 0),
		"attribute_points": av.get("attribute_points", 0),
		"caracteristiques_current": dict(av.get("caracteristiques_current", {})),
		"race_min": dict(race.get("stats", {})),
		"race_max": dict(race.get("stats_max", {})),
		"vocations_niveaux": dict(av.get("vocations_niveaux", {})),
		"voc_niveau": av.get("vocations_niveaux", {}).get(av.get("voc", ""), 0),
		"derived_stats": fiche_util.derived_de(av),
		"vitals": recrutement.vitaux_de(av),
		"equipment_bonus": av.get("equipment_bonus", {}),
		"exigences_effectives": recrutement.conditions_effectives(
			av, recrutement.affinite_de(character, av["_id"])),
		"affinite": recrutement.affinite_de(character, av["_id"]),
	}
	payload.update(_inventory_payload(av, character))
	payload.update(fiche_util.bloc_fiche(av, get_doc, find_docs, race))
	return payload


@recrutement_router.post("/groupe/transferer")
async def groupe_transferer(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Passe un objet entre le sac du joueur et celui d'un compagnon. Refus DUR (409) si le
	destinataire dépasse sa charge max : rien ne tombe au sol, rien n'est perdu — le client
	grise d'ailleurs la flèche à l'avance. Un bout du transfert est TOUJOURS le principal."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	av = _compagnon(character, body.get("compagnon_id") or "")
	sens = body.get("sens")
	if sens not in ("vers_compagnon", "vers_principal"):
		raise HTTPException(status_code=422, detail="Sens de transfert invalide")

	source, cible = (character, av) if sens == "vers_compagnon" else (av, character)
	ok, raison, ref = recrutement.transferer_ref(source, cible, body.get("index"), body.get("item_id"))
	if not ok:
		# « Objet absent » = requête incohérente (422) ; refus de charge = 409, comme les
		# autres gardes de surcharge du jeu (move_character, /recolter).
		code = 422 if ref is None and raison.startswith("Objet") else 409
		raise HTTPException(status_code=code, detail=raison)

	# Principal autoritatif (409 si conflit), compagnon en best-effort — même séquence
	# bi-doc que l'embauche et le congédiement.
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	save_doc(av)

	doc = resolve_item_ref(ref)
	return {
		"principal": _inventory_payload(character),
		"compagnon": _inventory_payload(av, character),
		"compagnon_id": av["_id"],
		"transfere": {
			"nom": (doc or {}).get("nom", "?"),
			"icon": (doc or {}).get("icon", "📦"),
			"poids": item_ref_weight(ref),
			"vers": "compagnon" if sens == "vers_compagnon" else "principal",
		},
	}

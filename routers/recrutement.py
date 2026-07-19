# routers/recrutement.py
# Endpoints du tableau de recrutement d'un lieu recruteur (tag "recrutement" ou guilde
# d'aventuriers). Le moteur (utils/recrutement.py) génère/complète les recrues ; ici on
# gère l'interaction joueur : consulter le tableau (carte d'aventurier de la cité
# requise), embaucher (gratuit — c'est l'ACCEPTATION des clauses de conduite), refuser
# ces clauses (la recrue quitte le tableau), congédier (autorisé partout, miroir de
# l'abandon de quête). Pattern calqué sur routers/quetes.py : muter → save_doc is None ⇒ 409.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, find_docs
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre,
	carried_weight, charge_max_of, resolve_item_ref, item_ref_weight,
)
from utils import recrutement
from utils import montures
from utils import fiche as fiche_util
# Une monture est un porteur du groupe : le panneau 👥 la rend avec la même carte que les
# compagnons. On réutilise sa vue plutôt que de la recopier — même précédent que
# `_inventory_payload` importé de routers/user.py juste en dessous.
from routers.montures import _monture_view
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


def _acces_tableau(current_user: dict) -> tuple[dict, dict]:
	"""(personnage, lieu) pour toute opération sur le tableau : personnage sélectionné (404),
	lieu recruteur (403), carte d'aventurier de la cité (403). Prélude commun au board, à
	l'embauche et au refus."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _lieu_recruteur(character)
	ok, raison = recrutement.acces_autorise(character, lieu_doc)
	if not ok:
		raise HTTPException(status_code=403, detail=raison)
	return character, lieu_doc


def _recrue_du_tableau(lieu_doc: dict, body: dict) -> dict:
	"""Doc de la recrue visée par le corps de requête, vérifié comme proposée PAR CE LIEU.
	Le statut (`offert` ?) est laissé aux gardes métier, qui remontent en 409."""
	av_id = body.get("aventurier_id")
	av = get_doc(av_id) if av_id else None
	if not av or av.get("type") != "aventurier":
		raise HTTPException(status_code=404, detail="Recrue introuvable")
	if av.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Cette recrue n'est pas proposée ici.")
	return av


def _nom_de(av: dict) -> str:
	return f"{av.get('prenom', '')} {av.get('nom', '')}".strip()


def _recrue_view(character: dict, av: dict) -> dict:
	"""Vue d'une recrue pour le client : identité + conditions EFFECTIVES (affinité
	déduite) + mémoire du lien (`affinite` brute — None si jamais rencontrée).

	Source unique des recrues ET du groupe (`_groupe_view` n'y ajoute que les vitaux) : le
	client en fait des CARTES de personnage (part-character-card.html), d'où le niveau de
	vocation et le cadrage du portrait — sans eux, la carte ne saurait ni afficher la ligne
	d'identité complète ni recadrer l'image comme son porteur l'a réglée."""
	affinite_brute = (character.get("affinites", {}) or {}).get(av["_id"])
	return {
		"id": av["_id"],
		"prenom": av.get("prenom", ""),
		"nom": av.get("nom", ""),
		"race": av.get("race", ""),
		"voc": av.get("voc", ""),
		"voc_niveau": (av.get("vocations_niveaux") or {}).get(av.get("voc", ""), 0),
		"sex": av.get("sex", ""),
		"rang": av.get("rang", "F"),
		"niveau": compute_character_level(av.get("xp_total", 0)),
		"specialite": av.get("specialite", ""),
		"image": av.get("image", ""),
		"portrait_zoom": av.get("portrait_zoom"),
		"portrait_translate": av.get("portrait_translate"),
		"exigences_effectives": recrutement.conditions_effectives(
			av, recrutement.affinite_de(character, av["_id"])),
		"affinite": affinite_brute,
		"deja_connu": av["_id"] in (character.get("compagnons_connus", {}) or {}),
		# Vitaux : la carte les affiche (barres + ligne PV/PM) pour un compagnon comme pour une
		# recrue — son doc est la source, ses max se recalculent comme ceux du joueur.
		**recrutement.vitaux_de(av),
	}


def _groupe_view(character: dict) -> list:
	"""Le groupe actif (même vue que les recrues : `_recrue_view` porte déjà les vitaux)."""
	return [_recrue_view(character, av) for av in recrutement.groupe_effectif(character, get_doc)]


def _appliquer_departs(character: dict) -> list:
	"""Check paresseux des départs volontaires (affinité < seuil) : persiste les docs
	mutés (compagnons puis personnage) et renvoie les noms partis pour le toast."""
	partis = recrutement.departs_volontaires(character, get_doc)
	if partis:
		for av in partis:
			save_doc(av)
		save_doc(character)
	return [_nom_de(av) for av in partis]


def _payload(character: dict, recrues: list | None = None) -> dict:
	payload = {
		"groupe": _groupe_view(character),
		"plafond": recrutement.taille_max_groupe(),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"affinites_detail": recrutement.affinites_detail_payload(character, get_doc),
		# Les montures voyagent avec le groupe mais n'en sont pas membres (ni affinité, ni
		# part de butin, ni plafond commun) : liste et plafond SÉPARÉS, que le client rend
		# dans son propre regroupement en fin de panneau.
		"montures": [_monture_view(m)
					 for m in montures.montures_effectives(character, get_doc)],
		"montures_plafond": montures.plafond_montures(),
	}
	if recrues is not None:
		payload["recrues"] = [_recrue_view(character, av) for av in recrues]
	return payload


@recrutement_router.get("/recrutement/board")
async def recrutement_board(current_user: Annotated[dict, Depends(get_current_user)]):
	character, lieu_doc = _acces_tableau(current_user)
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
	"""Embauche = ACCEPTATION des conditions de la recrue (part de butin + clauses de
	conduite) : le client ne l'appelle qu'après validation du dialogue de clauses."""
	character, lieu_doc = _acces_tableau(current_user)
	av = _recrue_du_tableau(lieu_doc, body)

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
	payload["embauche"] = {"nom": _nom_de(av)}
	return payload


@recrutement_router.post("/recrutement/refuser")
async def recrutement_refuser(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Refus des conditions : la recrue se vexe et QUITTE le tableau (`retirer_du_tableau`
	tranche entre suppression et retour au statut `parti` pour un ancien compagnon). Le
	refus ne coûte AUCUNE affinité — éconduire un inconnu n'a pas de coût social — donc le
	personnage n'est pas muté : pas de save_doc(character), pas de branche de conflit."""
	character, lieu_doc = _acces_tableau(current_user)
	av = _recrue_du_tableau(lieu_doc, body)

	ok, raison = recrutement.peut_refuser(av)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	recrutement.retirer_du_tableau(av)  # persiste ou supprime lui-même

	# La place libérée est aussitôt repeuplée (remplir_tableau_recrues complète jusqu'à
	# offre.nb) : le tableau ne rétrécit pas, la recrue refusée est simplement remplacée.
	recrues = recrutement.remplir_tableau_recrues(lieu_doc, character)
	payload = _payload(character, recrues)
	payload["refus"] = {"nom": _nom_de(av)}
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
	payload["congedie"] = {"nom": _nom_de(av)}
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


def _porteurs_du_groupe(character: dict) -> list:
	"""Tous ceux qui peuvent porter un objet pour le joueur : compagnons PUIS montures."""
	return recrutement.porteurs_effectifs(character, get_doc)


def _porteur_du_groupe(character: dict, porteur_id: str) -> dict:
	"""Doc du porteur visé, compagnon OU monture, avec la même preuve d'appartenance dans
	les deux cas (statut + lien vers CE personnage). Garde des transferts."""
	p = next((x for x in _porteurs_du_groupe(character) if x.get("_id") == porteur_id), None)
	if p is None:
		raise HTTPException(status_code=403, detail="Ce porteur ne fait pas partie de votre groupe")
	return p


def _charge_view(porteur: dict) -> dict:
	"""⚠️ `charge_max_porteur` et non `charge_max_of` : une monture porte bien davantage,
	et c'est ce plafond que le client recopie pour griser ses flèches de transfert."""
	return {"charge": round(carried_weight(porteur), 2),
			"charge_max": montures.charge_max_porteur(porteur)}


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
	# Sacs des porteurs (compagnons ET montures) : le panneau affiche deux inventaires côte
	# à côte et doit pouvoir griser une flèche de transfert AVANT l'appel serveur (même
	# arithmétique que peut_porter).
	payload["sacs"] = {
		p["_id"]: {
			**_charge_view(p),
			"inventaire": [d for r in p.get("inventaire", []) if (d := resolve_item_ref(r))],
		}
		for p in _porteurs_du_groupe(character)
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
		# Cadrage du portrait : le client mesure l'image, mais il ne peut pas DEVINER le
		# recadrage déjà enregistré sur ce compagnon (absent d'une recrue neuve → défaut :
		# zoom 100, centré). Mêmes champs que ceux relus par les jetons alliés en combat.
		"portrait_zoom": av.get("portrait_zoom"),
		"portrait_translate": av.get("portrait_translate"),
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
	"""Passe un objet entre le sac du joueur et celui d'un porteur du groupe — compagnon ou
	MONTURE, indifféremment (`_porteur_du_groupe` prouve l'appartenance dans les deux cas,
	`peut_porter` applique le bon plafond). Refus DUR (409) si le destinataire dépasse sa
	charge max : rien ne tombe au sol, rien n'est perdu — le client grise d'ailleurs la
	flèche à l'avance. Un bout du transfert est TOUJOURS le principal."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	av = _porteur_du_groupe(character, body.get("compagnon_id") or "")
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

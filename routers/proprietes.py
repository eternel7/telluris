# routers/proprietes.py
# Endpoints des propriétés résidentielles : acheter (zone habitable d'une ville), louer une
# chambre (auberge), puis, DEDANS, occuper/quitter, vendre/abandonner, aménager, engager du
# personnel, héberger des compagnons, déposer/retirer au coffre. Le moteur est
# utils/proprietes.py ; ici l'accès, l'argent et la persistance.
#
# Pattern routers/montures.py : prélude d'accès, `_payload` qui RECALCULE tout le bloc
# (Convention §10), `save_doc(...) is None ⇒ 409`, débit APRÈS toutes les gardes. Docs
# annexes neufs (propriété, lien, employé) sauvés AVANT le personnage : un échec ensuite
# laisse un orphelin invisible plutôt qu'un index pointant dans le vide.
#
# ⚠️ Aucune route ne change `type_propriete` : il n'existe pas de conversion de type.

import unicodedata
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, delete_doc
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre, resolve_item_ref,
	credit_character, tirer_poids, poids_bounds, carried_weight, charge_max_of,
)
from utils.marche import debit_character
from utils import auberge
from utils import recrutement
from utils import proprietes
from utils import escorte
from utils import commande as commande_util
# Sens d'import : `routers/proprietes` → `routers/user`, jamais l'inverse (précédent :
# routers/auberge).
from routers.user import _inventory_payload

proprietes_router = APIRouter()


# ── Vues ─────────────────────────────────────────────────────────────────────────

def _type_view(cat: dict, tdef: dict) -> dict:
	return {
		"id": tdef.get("id", ""),
		"label": tdef.get("label", ""),
		"rang": tdef.get("rang", 0),
		"description": tdef.get("description", ""),
		"prix": int(tdef.get("prix_cuivre") or 0),
		"capacites": {
			"occupants_max": int(tdef.get("occupants_max") or 0),
			"personnel_max": int(tdef.get("personnel_max") or 0),
			"stockage_kg": int(tdef.get("stockage_kg") or 0),
		},
		"amenagements": [a.get("nom", a.get("id")) for a in proprietes.amenagements_du_type(cat, tdef.get("id"))],
	}


def _resume(p: dict, cat: dict, character: dict) -> dict:
	tdef = proprietes.type_def(cat, p.get("type_propriete")) or {}
	return {
		"id": p["_id"],
		"label": p.get("label", ""),
		"type": tdef.get("label", p.get("type_propriete", "")),
		"mode": p.get("mode"),
		"statut": p.get("statut"),
		"expire_at": p.get("expire_at"),
		"residence": character.get("residence") == p["_id"],
		"cite": p.get("lieu_parent"),
	}


def _mes_proprietes(character: dict, cat: dict) -> list:
	return [_resume(p, cat, character) for p in proprietes.proprietes_de(character, get_doc)]


def _payload_offre(character: dict, lieu_doc: dict, cat: dict) -> dict:
	"""Ce qui s'acquiert ICI : types des zones habitables couvrant la case, et/ou une
	chambre à louer si le lieu est une auberge."""
	types = []
	for tid in proprietes.types_achetables_ici(lieu_doc, character.get("position"), get_doc):
		tdef = proprietes.type_def(cat, tid)
		if tdef:                                   # zone pointant un type absent : ignorée
			types.append(_type_view(cat, tdef))
	location = None
	if auberge.lieu_est_taverne(lieu_doc):
		tdef = _type_location(cat)
		if tdef:
			loc = proprietes.location_de(tdef)
			ch = proprietes.chambre_louee_ici(character, lieu_doc.get("_id"), get_doc)
			if ch:
				proprietes.traiter_expiration_location(ch)
			location = {
				"type": _type_view(cat, tdef),
				"prix": loc["prix_cuivre"],
				"duree_s": loc["duree_s"],
				"chambre": _resume(ch, cat, character) if ch else None,
			}
	return {
		"types": types,
		"location": location,
		"mes_proprietes": _mes_proprietes(character, cat),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}


def _type_location(cat: dict) -> dict | None:
	"""Le type qui se loue (la Chambre) — le premier du catalogue porteur de `location`."""
	return next((t for t in cat.get("types") or [] if proprietes.location_de(t)), None)


def _payload_ici(character: dict, prop: dict, cat: dict, role: str, extra: dict | None = None) -> dict:
	tdef = proprietes.type_def(cat, prop.get("type_propriete")) or {}
	employes = proprietes.employes_effectifs(prop, get_doc)
	caps = proprietes.capacites(prop, cat)
	gardien = proprietes.gardien_present(prop, cat, employes)
	resident = character.get("residence") == prop["_id"] if role == proprietes.PROPRIETAIRE else False
	gere = role == proprietes.PROPRIETAIRE
	heberges = proprietes.heberges_effectifs(character, prop, get_doc) if gere else []

	def am_view(am_id):
		a = proprietes.amenagement_def(cat, am_id) or {"id": am_id, "nom": am_id}
		return {"id": a.get("id"), "nom": a.get("nom", am_id), "categorie": a.get("categorie", ""),
				"cout": int(a.get("cout_cuivre") or 0), "description": a.get("description", "")}

	revente_ok, revente_raison = proprietes.revente_autorisee(
		tdef, get_doc(prop.get("lieu_parent")) if prop.get("lieu_parent") else None)
	payload = {
		"role": role,
		"propriete": {
			"id": prop["_id"], "label": prop.get("label", ""), "mode": prop.get("mode"),
			"statut": prop.get("statut"), "expire_at": prop.get("expire_at"),
			"proprietaire_nom": prop.get("proprietaire_nom", ""), "residence": resident,
		},
		"type": {"id": tdef.get("id", ""), "label": tdef.get("label", ""), "rang": tdef.get("rang", 0),
				 "description": tdef.get("description", "")},
		"capacites": {
			**caps,
			"occupants": proprietes.occupants(resident, prop),
			"personnel": len(employes),
			"stockage_utilise": proprietes.poids_coffre(prop),
		},
		"installes": [am_view(a) for a in prop.get("amenagements") or []],
		"disponibles": [am_view(a["id"]) for a in proprietes.amenagements_disponibles(prop, cat)] if gere else [],
		"heberges": [{"id": a["_id"], "nom": proprietes.nom_personnage(a), "image": a.get("image", "")}
					 for a in heberges],
		"hebergeables": [{"id": a["_id"], "nom": proprietes.nom_personnage(a)}
						 for a in recrutement.groupe_effectif(character, get_doc)] if gere else [],
		"employes": [_employe_view(cat, e) for e in employes],
		"activites": [dict(a, metier_label=(proprietes.metier_def(cat, a["metier"]) or {}).get("label", a["metier"]))
					  for a in proprietes.activites(prop, cat, employes)],
		"gardien": gardien,
		"revente": {"autorisee": gere and revente_ok and prop.get("mode") == proprietes.MODE_ACHAT,
					"raison": revente_raison, "prix": proprietes.prix_revente(tdef)},
		"mes_proprietes": _mes_proprietes(character, cat),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}
	if extra:
		payload.update(extra)
	return payload


def _employe_view(cat: dict, e: dict) -> dict:
	"""Vue d'un employé — mêmes clés que la carte de personnage là où elles se recoupent
	(`prenom`/`nom`/`image`/`image_base`) : il s'affiche comme un PNJ, portrait `/pnj` d'abord."""
	route, _ = escorte.image_protege(e.get("portrait", ""))
	return {
		"id": e["_id"], "nom": proprietes.nom_personnage(e),
		"prenom": e.get("prenom", ""), "nom_famille": e.get("nom", ""),
		"image": e.get("portrait", ""), "image_base": route,
		"metier": e.get("metier"),
		"metier_label": (proprietes.metier_def(cat, e.get("metier")) or {}).get("label", e.get("metier")),
		"poste_nom": (proprietes.amenagement_def(cat, e.get("poste")) or {}).get("nom", ""),
		"categorie": e.get("categorie", ""),
		"categorie_label": categorie_label(e.get("categorie", "")) if e.get("categorie") else "",
		"marchand": proprietes.est_atelier(e),
		"grande": proprietes.grande_maison(e),
	}


def categorie_label(categorie: str) -> str:
	"""« grand_laboratoire_alchimique » → « Grand laboratoire alchimique » : les catégories de
	boutique n'ont pas de libellé en base, c'est leur identifiant qui fait foi."""
	return (categorie or "").replace("_", " ").capitalize()


# ── Préludes d'accès ─────────────────────────────────────────────────────────────

def _personnage(current_user: dict) -> dict:
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	return character


def _ici(current_user: dict) -> tuple[dict, dict, dict, str]:
	"""(personnage, propriété, catalogue, rôle) : il faut être DANS la propriété. La
	location est périmée au passage (paresseux)."""
	character = _personnage(current_user)
	prop = get_doc(character.get("lieu", ""))
	if not prop or not proprietes.est_propriete(prop):
		raise HTTPException(status_code=403, detail="Vous n'êtes dans aucune propriété.")
	if proprietes.traiter_expiration_location(prop):
		save_doc(prop)
	role = proprietes.role_de(character, prop)
	if not role:
		raise HTTPException(status_code=403, detail=proprietes.acces_propriete(character, prop)[1])
	return character, prop, proprietes.catalogue(get_doc), role


def _exiger(role: str, *attendus) -> None:
	if role not in attendus:
		raise HTTPException(status_code=403, detail="Seul le propriétaire peut faire cela.")


def _sauver(*docs) -> None:
	"""Sauve dans l'ordre donné ; le DERNIER est l'autoritatif (409 sur conflit). Les
	précédents aussi : un échec avant le principal n'a encore rien engagé."""
	for d in docs:
		if save_doc(d) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")


# ── Acquisition ──────────────────────────────────────────────────────────────────

@proprietes_router.get("/proprietes/offre")
async def offre(current_user: Annotated[dict, Depends(get_current_user)]):
	character = _personnage(current_user)
	lieu_doc = get_doc(character.get("lieu", "")) or {}
	payload = _payload_offre(character, lieu_doc, proprietes.catalogue(get_doc))
	if not payload["types"] and not payload["location"]:
		raise HTTPException(status_code=403, detail="Aucune propriété à acquérir ici.")
	return payload


@proprietes_router.post("/proprietes/acheter")
async def acheter(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Achète une propriété du type proposé par la zone habitable de CETTE case. La
	propriété naît à l'achat, avec sa connexion depuis cette case (visible de tous)."""
	character = _personnage(current_user)
	lieu_doc = get_doc(character.get("lieu", "")) or {}
	cat = proprietes.catalogue(get_doc)
	type_id = body.get("type")
	if not type_id or type_id not in proprietes.types_achetables_ici(
			lieu_doc, character.get("position"), get_doc):
		raise HTTPException(status_code=403, detail="Ce type de propriété ne s'acquiert pas ici.")
	tdef = proprietes.type_def(cat, type_id)
	if not tdef:
		raise HTTPException(status_code=404, detail="Type de propriété inconnu.")
	prix = int(tdef.get("prix_cuivre") or 0)
	if money_to_cuivre(character) < prix:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer ce bien.")

	pos = character.get("position") or {}
	prop = proprietes.creer_propriete(
		tdef, lieu_doc.get("_id"),
		{"lieu": lieu_doc.get("_id"), "pos": [pos.get("x", 0), pos.get("y", 0)]},
		character, proprietes.MODE_ACHAT)
	lien = proprietes.creer_lien(prop)
	if debit_character(character, prix) is None:
		raise HTTPException(status_code=409, detail="Fonds insuffisants.")
	proprietes.acquerir(character, prop, prix)
	_sauver(prop, lien, character)

	payload = _payload_offre(character, lieu_doc, cat)
	payload["achetee"] = _resume(prop, cat, character)
	return payload


@proprietes_router.post("/proprietes/louer")
async def louer(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Loue (ou prolonge) une chambre dans CETTE auberge. Relouer réactive la même
	chambre : ses affaires y sont restées, rien n'est recréé."""
	character = _personnage(current_user)
	lieu_doc = get_doc(character.get("lieu", "")) or {}
	if not auberge.lieu_est_taverne(lieu_doc):
		raise HTTPException(status_code=403, detail="On ne loue de chambre qu'à l'auberge.")
	cat = proprietes.catalogue(get_doc)
	tdef = _type_location(cat)
	if not tdef:
		raise HTTPException(status_code=404, detail="Aucune chambre à louer.")
	loc = proprietes.location_de(tdef)
	if money_to_cuivre(character) < loc["prix_cuivre"]:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer la chambre.")

	prop = proprietes.chambre_louee_ici(character, lieu_doc.get("_id"), get_doc)
	nouveaux = []
	if prop is None:
		pos = character.get("position") or {}
		prop = proprietes.creer_propriete(
			tdef, lieu_doc.get("lieu_parent"),
			{"lieu": lieu_doc.get("_id"), "pos": [pos.get("x", 0), pos.get("y", 0)]},
			character, proprietes.MODE_LOCATION)
		prop["expire_at"] = 0
		nouveaux.append(proprietes.creer_lien(prop))
		proprietes.acquerir(character, prop, loc["prix_cuivre"])
	proprietes.prolonger_location(prop, loc["duree_s"])
	if debit_character(character, loc["prix_cuivre"]) is None:
		raise HTTPException(status_code=409, detail="Fonds insuffisants.")
	_sauver(prop, *nouveaux, character)

	payload = _payload_offre(character, lieu_doc, cat)
	payload["louee"] = _resume(prop, cat, character)
	return payload


# ── Dans la propriété ────────────────────────────────────────────────────────────

@proprietes_router.get("/proprietes/ici")
async def ici(current_user: Annotated[dict, Depends(get_current_user)]):
	character, prop, cat, role = _ici(current_user)
	return _payload_ici(character, prop, cat, role)


@proprietes_router.post("/proprietes/occuper")
async def occuper(current_user: Annotated[dict, Depends(get_current_user)]):
	character, prop, cat, role = _ici(current_user)
	ok, raison = proprietes.occuper(character, prop)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(character)
	return _payload_ici(character, prop, cat, role)


@proprietes_router.post("/proprietes/quitter")
async def quitter(current_user: Annotated[dict, Depends(get_current_user)]):
	character, prop, cat, role = _ici(current_user)
	ok, raison = proprietes.quitter(character, prop)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(character)
	return _payload_ici(character, prop, cat, role)


def _ceder(current_user: dict, statut: str) -> dict:
	"""Vente ou abandon : le bien quitte le joueur AVEC ses aménagements, son lien est
	supprimé, et le personnage ressort sur la case d'origine (il ne peut pas rester dans
	un lieu qui n'a plus de porte)."""
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	employes = proprietes.employes_effectifs(prop, get_doc)
	ok, raison = proprietes.peut_ceder(prop, employes)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	tdef = proprietes.type_def(cat, prop.get("type_propriete")) or {}
	gain = 0
	if statut == proprietes.VENDUE:
		ok, raison = proprietes.revente_autorisee(
			tdef, get_doc(prop.get("lieu_parent")) if prop.get("lieu_parent") else None)
		if not ok:
			raise HTTPException(status_code=409, detail=raison)
		gain = proprietes.prix_revente(tdef)
		credit_character(character, gain)
	proprietes.ceder(character, prop, statut, employes)
	origine = prop.get("origine") or {}
	opos = origine.get("pos") or [0, 0]
	character["lieu"] = origine.get("lieu") or character.get("cite")
	character["position"] = {"x": opos[0], "y": opos[1]}
	_sauver(prop, character)
	for e in employes:
		save_doc(e)                                # best-effort, comme un congédiement
	lien = get_doc(prop.get("lien", "")) if prop.get("lien") else None
	if lien:
		delete_doc(lien)
	return {"sortie": True, "gain": gain, "statut": statut, "label": prop.get("label", ""),
			"purse": cuivre_to_purse(money_to_cuivre(character))}


@proprietes_router.post("/proprietes/vendre")
async def vendre(current_user: Annotated[dict, Depends(get_current_user)]):
	return _ceder(current_user, proprietes.VENDUE)


@proprietes_router.post("/proprietes/abandonner")
async def abandonner(current_user: Annotated[dict, Depends(get_current_user)]):
	return _ceder(current_user, proprietes.ABANDONNEE)


@proprietes_router.post("/proprietes/installer")
async def installer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	am_id = body.get("amenagement")
	ok, raison = proprietes.peut_installer(prop, cat, am_id)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	cout = int((proprietes.amenagement_def(cat, am_id) or {}).get("cout_cuivre") or 0)
	if debit_character(character, cout) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer cet aménagement.")
	proprietes.installer(prop, am_id)
	_sauver(prop, character)
	return _payload_ici(character, prop, cat, role)


@proprietes_router.get("/proprietes/embauche")
async def embauche(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Tableau d'embauche (propriétaire) : un candidat par poste libre, renouvelé
	paresseusement comme un tableau de recrues."""
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	employes = proprietes.employes_effectifs(prop, get_doc)
	if proprietes.rafraichir_candidats(prop, cat, employes, get_doc, recrutement.portraits_disponibles()):
		save_doc(prop)
	return _payload_embauche(character, prop, cat, employes)


def _payload_embauche(character: dict, prop: dict, cat: dict, employes: list, extra=None) -> dict:
	caps = proprietes.capacites(prop, cat)
	complet = len(employes) >= caps["personnel_max"]

	def carte(c):
		route, _ = escorte.image_protege(c.get("portrait", ""))
		mdef = proprietes.metier_def(cat, c.get("metier")) or {}
		return {
			"id": c["id"], "prenom": c.get("prenom", ""), "nom": c.get("nom", ""),
			"race": c.get("race", ""), "sex": c.get("sex", ""),
			"image": c.get("portrait", ""), "image_base": route,
			"metier_label": mdef.get("label", c.get("metier", "")),
			"poste_nom": (proprietes.amenagement_def(cat, c.get("amenagement")) or {}).get("nom", ""),
			"categorie_label": categorie_label(c.get("categorie", "")) if c.get("categorie") else "",
			"grande": c.get("categorie") in (proprietes.character_stats.LIEU_CATEGORIES_FUSION or {}),
			"cout": int(c.get("cout") or 0),
		}
	payload = {
		"candidats": [carte(c) for c in prop.get("candidats") or []],
		"employes": [_employe_view(cat, e) for e in employes],
		"personnel": len(employes), "personnel_max": caps["personnel_max"], "complet": complet,
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}
	if extra:
		payload.update(extra)
	return payload


@proprietes_router.post("/proprietes/engager")
async def engager(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Embauche un candidat du tableau : il devient un `employe:*` de CETTE propriété."""
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	candidat = proprietes.candidat_par_id(prop, body.get("candidat_id"))
	if candidat is None:
		raise HTTPException(status_code=404, detail="Ce candidat n'est plus disponible.")
	employes = proprietes.employes_effectifs(prop, get_doc)
	ok, raison = proprietes.peut_engager(prop, cat, employes, candidat.get("metier"), candidat.get("amenagement"))
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if debit_character(character, int(candidat.get("cout") or 0)) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi engager ce personnel.")
	employe = proprietes.creer_employe(prop, candidat, character)
	proprietes.engager(prop, employe)
	proprietes.retirer_candidat(prop, candidat["id"])
	employes.append(employe)
	proprietes.rafraichir_candidats(prop, cat, employes, get_doc)   # poste pourvu : candidats rivaux retirés
	_sauver(employe, prop, character)
	mdef = proprietes.metier_def(cat, employe["metier"]) or {}
	return _payload_embauche(character, prop, cat, employes,
							 {"engage": f"{proprietes.nom_personnage(employe)} ({mdef.get('label', employe['metier'])})"})


@proprietes_router.post("/proprietes/renvoyer")
async def renvoyer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	employe = next((e for e in proprietes.employes_effectifs(prop, get_doc)
					if e.get("_id") == body.get("employe_id")), None)
	if employe is None:
		raise HTTPException(status_code=404, detail="Cet employé ne travaille pas ici.")
	if int(employe.get("caisse_cuivre") or 0):
		raise HTTPException(status_code=409, detail="Relevez d'abord sa caisse.")
	proprietes.renvoyer(prop, employe)
	_sauver(prop)
	save_doc(employe)
	return _payload_ici(character, prop, cat, role)


def _compagnon(aventurier_id) -> dict:
	av = get_doc(aventurier_id) if aventurier_id else None
	if not av or av.get("type") != "aventurier":
		raise HTTPException(status_code=404, detail="Compagnon introuvable.")
	return av


@proprietes_router.post("/proprietes/heberger")
async def heberger(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	av = _compagnon(body.get("aventurier_id"))
	ok, raison = proprietes.heberger(character, prop, cat, av)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(prop, character)
	save_doc(av)
	return _payload_ici(character, prop, cat, role)


@proprietes_router.post("/proprietes/reprendre")
async def reprendre(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	av = _compagnon(body.get("aventurier_id"))
	ok, raison = proprietes.reprendre(character, prop, av, get_doc)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(prop, character)
	save_doc(av)
	return _payload_ici(character, prop, cat, role)


# ── Coffre et ateliers : l'inventaire du lieu, présenté comme celui du groupe ─────

def _payload_coffre(character: dict, prop: dict, cat: dict, role: str, employes: list | None = None,
					extra: dict | None = None) -> dict:
	"""Deux colonnes, comme `GET /api/groupe` : le sac du personnage (`principal`) et, à
	droite, le COFFRE puis chaque atelier (matières confiées, rayon, caisse)."""
	if employes is None:
		employes = proprietes.employes_effectifs(prop, get_doc)
	gardien = proprietes.gardien_present(prop, cat, employes)
	coffre_visible = (role in (proprietes.PROPRIETAIRE, proprietes.LOCATAIRE, proprietes.ANCIEN_LOCATAIRE)
					  or proprietes.peut_retirer(role, prop, gardien)[0])
	gere = role == proprietes.PROPRIETAIRE
	ateliers = []
	for e in employes:
		if not proprietes.est_atelier(e):
			continue
		ateliers.append(dict(_employe_view(cat, e),
			matieres=[{"cle": k, "qty": int(q)} for k, q in sorted((e.get("stock_matieres") or {}).items()) if int(q) > 0] if gere else [],
			produits=[{"item_id": r["item_id"], "nom": (resolve_item_ref(r["item_id"]) or {}).get("nom", r["item_id"]),
					   "qty": int(r.get("qty") or 0)} for r in e.get("stock_vente") or []] if gere else [],
			caisse=int(e.get("caisse_cuivre") or 0) if (gere or not gardien) else None))
	payload = {
		"role": role,
		"gardien": gardien,
		"principal": _inventory_payload(character),
		"coffre": {
			"visible": coffre_visible,
			"depot": role in (proprietes.PROPRIETAIRE, proprietes.LOCATAIRE),
			"charge": proprietes.poids_coffre(prop),
			"charge_max": proprietes.capacites(prop, cat)["stockage_kg"],
			# Ordre alphabétique (sans accents ni casse) ; `idx` garde la position réelle dans le coffre.
			"inventaire": sorted(
				(dict(d, idx=i) for i, r in enumerate(prop.get("coffre") or [])
				 if (d := resolve_item_ref(r))),
				key=lambda d: unicodedata.normalize("NFD", str(d.get("nom") or "")).encode("ascii", "ignore").decode().lower(),
			) if coffre_visible else [],
		},
		"ateliers": ateliers,
		"caisse_totale": sum(int(e.get("caisse_cuivre") or 0) for e in employes),
		"caisse_accessible": gere or (role == proprietes.VISITEUR and not gardien
									  and prop.get("mode") == proprietes.MODE_ACHAT),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}
	if extra:
		payload.update(extra)
	return payload


@proprietes_router.get("/proprietes/coffre")
async def coffre(current_user: Annotated[dict, Depends(get_current_user)]):
	character, prop, cat, role = _ici(current_user)
	return _payload_coffre(character, prop, cat, role)


@proprietes_router.post("/proprietes/coffre/transferer")
async def coffre_transferer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Sac ↔ coffre. `vers_coffre` : propriétaire ou locataire, borné par le stockage dérivé.
	`vers_principal` : ses affaires, ou un VISITEUR chez un propriétaire sans gardien — le vol
	(`vol: true`)."""
	character, prop, cat, role = _ici(current_user)
	sens = body.get("sens")
	if sens == "vers_coffre":
		refs = character.get("inventaire") or []
		pos = proprietes.localiser(refs, body.get("index"), body.get("item_id"))
		if pos is None:
			raise HTTPException(status_code=404, detail="Objet absent de l'inventaire.")
		ok, raison = proprietes.peut_deposer(role, prop, cat, refs[pos])
		if not ok:
			raise HTTPException(status_code=409, detail=raison)
		proprietes.deposer(character, prop, pos)
		_sauver(prop, character)
		return _payload_coffre(character, prop, cat, role)
	if sens != "vers_principal":
		raise HTTPException(status_code=422, detail="Sens de transfert inconnu.")
	employes = proprietes.employes_effectifs(prop, get_doc)
	ok, raison = proprietes.peut_retirer(role, prop, proprietes.gardien_present(prop, cat, employes))
	if not ok:
		raise HTTPException(status_code=403, detail=raison)
	refs = prop.get("coffre") or []
	pos = proprietes.localiser(refs, body.get("index"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Cet objet n'est plus dans le coffre.")
	if not recrutement.peut_porter(character, refs[pos]):
		raise HTTPException(status_code=409, detail="Vous ne pouvez pas porter davantage.")
	proprietes.retirer(character, prop, pos)
	_sauver(prop, character)
	return _payload_coffre(character, prop, cat, role, employes, {"vol": role == proprietes.VISITEUR})


def _atelier_de(prop: dict, employe_id) -> dict:
	e = next((x for x in proprietes.employes_effectifs(prop, get_doc)
			  if x.get("_id") == employe_id and proprietes.est_atelier(x)), None)
	if e is None:
		raise HTTPException(status_code=404, detail="Ce marchand ne travaille pas ici.")
	return e


@proprietes_router.post("/proprietes/atelier/donner")
async def atelier_donner(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Le propriétaire CONFIE un objet de son sac à un marchand (sans retour : il devient
	matière d'atelier, ou marchandise du rayon s'il est de ceux qu'il produit)."""
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	atelier = _atelier_de(prop, body.get("employe_id"))
	refs = character.get("inventaire") or []
	pos = proprietes.localiser(refs, body.get("index"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Objet absent de l'inventaire.")
	item = resolve_item_ref(refs[pos])
	ok, raison = proprietes.donner(atelier, item or {})
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	refs.pop(pos)
	character["inventaire"] = refs
	_sauver(atelier, character)
	return _payload_coffre(character, prop, cat, role)


@proprietes_router.post("/proprietes/atelier/reprendre")
async def atelier_reprendre(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Le propriétaire reprend un exemplaire du rayon de son marchand (gratuit)."""
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	atelier = _atelier_de(prop, body.get("employe_id"))
	item_id = body.get("item_id")
	item = resolve_item_ref(item_id) if item_id else None
	if not item:
		raise HTTPException(status_code=404, detail="Objet introuvable.")
	poids = tirer_poids(item)
	if carried_weight(character) + poids > charge_max_of(character):
		raise HTTPException(status_code=409, detail="Vous ne pouvez pas porter davantage.")
	if not proprietes.reprendre_produit(atelier, item_id):
		raise HTTPException(status_code=404, detail="Ce produit n'est plus en rayon.")
	pmin, pmax = poids_bounds(item)
	character.setdefault("inventaire", []).append({"item": item_id, "poids": poids} if pmax > pmin else item_id)
	_sauver(atelier, character)
	return _payload_coffre(character, prop, cat, role)


@proprietes_router.post("/proprietes/atelier/choisir")
async def atelier_choisir(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Tout visiteur s'adresse à un marchand : `atelier_courant` (TRANSITOIRE, vidé au premier
	déplacement) désigne le « lieu » que le marché et les commandes traiteront."""
	character, prop, cat, role = _ici(current_user)
	atelier = _atelier_de(prop, body.get("employe_id"))
	character["atelier_courant"] = atelier["_id"]
	_sauver(character)
	return {
		**_employe_view(cat, atelier),
		"commande": commande_util.lieu_prend_commandes(atelier, get_doc),
		"sur_mesure": commande_util.lieu_fabrique_sur_mesure(atelier),
	}


@proprietes_router.post("/proprietes/caisse/relever")
async def caisse_relever(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Le propriétaire relève la caisse de ses marchands. Un VISITEUR la vide aussi quand
	aucun gardien ne veille : c'est un vol (`vol: true`)."""
	character, prop, cat, role = _ici(current_user)
	employes = proprietes.employes_effectifs(prop, get_doc)
	gardien = proprietes.gardien_present(prop, cat, employes)
	if role != proprietes.PROPRIETAIRE and not proprietes.peut_retirer(role, prop, gardien)[0]:
		raise HTTPException(status_code=403, detail="Cette caisse ne vous est pas accessible.")
	ateliers = [e for e in employes if proprietes.est_atelier(e)]
	total = proprietes.relever_caisse(ateliers)
	if not total:
		raise HTTPException(status_code=409, detail="La caisse est vide.")
	credit_character(character, total)
	# Les caisses d'abord : un échec ensuite perd le relevé plutôt que de le DOUBLER (une
	# caisse restée pleine se relèverait une seconde fois).
	_sauver(*ateliers, character)
	return _payload_coffre(character, prop, cat, role, employes,
						   {"releve": total, "vol": role == proprietes.VISITEUR})

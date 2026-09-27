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

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, delete_doc
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre, resolve_item_ref,
	item_ref_weight, credit_character,
)
from utils.marche import debit_character
from utils import auberge
from utils import recrutement
from utils import proprietes
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

	coffre_visible = (role in (proprietes.PROPRIETAIRE, proprietes.LOCATAIRE, proprietes.ANCIEN_LOCATAIRE)
					  or proprietes.peut_retirer(role, prop, gardien)[0])
	coffre = []
	if coffre_visible:
		for i, r in enumerate(prop.get("coffre") or []):
			d = resolve_item_ref(r)
			if d:
				coffre.append(dict(d, idx=i))

	embauches = []
	if gere and len(employes) < caps["personnel_max"]:
		for p in proprietes.postes_libres(prop, cat, employes):
			mdef = proprietes.metier_def(cat, p["metier"])
			if mdef:
				embauches.append({
					"metier": p["metier"], "metier_label": mdef.get("label", p["metier"]),
					"amenagement": p["amenagement"],
					"amenagement_nom": (proprietes.amenagement_def(cat, p["amenagement"]) or {}).get("nom", ""),
					"cout": int(mdef.get("cout_embauche_cuivre") or 0), "libres": p["libres"],
				})

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
		"employes": [{
			"id": e["_id"], "nom": proprietes.nom_personnage(e), "metier": e.get("metier"),
			"metier_label": (proprietes.metier_def(cat, e.get("metier")) or {}).get("label", e.get("metier")),
			"poste_nom": (proprietes.amenagement_def(cat, e.get("poste")) or {}).get("nom", ""),
		} for e in employes],
		"embauches": embauches,
		"activites": [dict(a, metier_label=(proprietes.metier_def(cat, a["metier"]) or {}).get("label", a["metier"]))
					  for a in proprietes.activites(prop, cat, employes)],
		"gardien": gardien,
		"coffre": coffre,
		"coffre_visible": coffre_visible,
		"revente": {"autorisee": gere and revente_ok and prop.get("mode") == proprietes.MODE_ACHAT,
					"raison": revente_raison, "prix": proprietes.prix_revente(tdef)},
		"mes_proprietes": _mes_proprietes(character, cat),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}
	if extra:
		payload.update(extra)
	return payload


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
	ok, raison = proprietes.peut_ceder(prop)
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
	employes = proprietes.employes_effectifs(prop, get_doc)
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


@proprietes_router.post("/proprietes/engager")
async def engager(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	metier_id, am_id = body.get("metier"), body.get("amenagement")
	employes = proprietes.employes_effectifs(prop, get_doc)
	ok, raison = proprietes.peut_engager(prop, cat, employes, metier_id, am_id)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	mdef = proprietes.metier_def(cat, metier_id)
	if debit_character(character, int(mdef.get("cout_embauche_cuivre") or 0)) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi engager ce personnel.")
	employe = proprietes.creer_employe(prop, mdef, am_id, character)
	proprietes.engager(prop, employe)
	_sauver(employe, prop, character)
	return _payload_ici(character, prop, cat, role,
						{"engage": f"{proprietes.nom_personnage(employe)} ({mdef.get('label', metier_id)})"})


@proprietes_router.post("/proprietes/renvoyer")
async def renvoyer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, prop, cat, role = _ici(current_user)
	_exiger(role, proprietes.PROPRIETAIRE)
	employe = next((e for e in proprietes.employes_effectifs(prop, get_doc)
					if e.get("_id") == body.get("employe_id")), None)
	if employe is None:
		raise HTTPException(status_code=404, detail="Cet employé ne travaille pas ici.")
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


@proprietes_router.post("/proprietes/deposer")
async def deposer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, prop, cat, role = _ici(current_user)
	refs = character.get("inventaire") or []
	pos = proprietes.localiser(refs, body.get("idx"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Objet absent de l'inventaire.")
	ok, raison = proprietes.peut_deposer(role, prop, cat, refs[pos])
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	proprietes.deposer(character, prop, pos)
	_sauver(prop, character)
	return _payload_ici(character, prop, cat, role,
						{"inventaire_payload": _inventory_payload(character)})


@proprietes_router.post("/proprietes/retirer")
async def retirer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Reprendre un objet du coffre. Un VISITEUR chez un propriétaire sans gardien le peut
	aussi : c'est le vol (`vol: true` dans la réponse)."""
	character, prop, cat, role = _ici(current_user)
	gardien = proprietes.gardien_present(prop, cat, proprietes.employes_effectifs(prop, get_doc))
	ok, raison = proprietes.peut_retirer(role, prop, gardien)
	if not ok:
		raise HTTPException(status_code=403, detail=raison)
	refs = prop.get("coffre") or []
	pos = proprietes.localiser(refs, body.get("idx"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Cet objet n'est plus dans le coffre.")
	if not recrutement.peut_porter(character, refs[pos]):
		raise HTTPException(status_code=409, detail="Vous ne pouvez pas porter davantage.")
	poids = item_ref_weight(refs[pos])
	proprietes.retirer(character, prop, pos)
	_sauver(prop, character)
	return _payload_ici(character, prop, cat, role, {
		"inventaire_payload": _inventory_payload(character),
		"vol": role == proprietes.VISITEUR, "poids": poids,
	})

# routers/renseignement.py
# 🔎 Se renseigner — le moteur est dans utils/renseignement.py (compétence telluris-renseignement).
# Pattern de routers/guides.py : gardes, débit APRÈS les gardes, `save_doc is None` ⇒ 409, blocs
# recalculés dans chaque réponse (Convention §10). Le carnet et le bestiaire sont ceux du
# PRINCIPAL ; l'ACTEUR (celui qui se renseigne) paie PV/PM et gagne l'XP.

import random
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from db.config import find_docs, get_doc, save_doc
from models import character_stats
from utils import donjon as donjon_util
from utils import expedition, fiche, focalisation, journal, marche, pouvoirs_objets, quetes, recrutement
from utils import renseignement as rens
from utils.auth import get_current_user
from utils.characters import (
	carried_weight, charge_max_of, credit_character, cuivre_to_purse, get_selected_character,
	grant_xp, item_ref_weight, lieu_label, money_to_cuivre,
)
from utils.marche import debit_character
from routers.user import _inventory_payload

renseignement_router = APIRouter()

CHAMPS_LIEU = ["_id", "label", "nom", "lieu_parent", "categorie", "sous_categorie", "tags",
			   "rencontres", "ressources", "stock_vente"]
SUGGESTIONS_MAX = 12

_RANGS: dict = {}


def _hasard():
	"""Le hasard d'une recherche — point unique, remplacé par les tests (jets contrôlés)."""
	return random.Random()


def _rang(espece_id: str) -> str | None:
	"""Rang d'une espèce (`potentiel.rang_espece`), mémoïsé par process sur la révision."""
	doc = get_doc(espece_id)
	if not doc:
		return None
	cle = (espece_id, doc.get("_rev"))
	if cle not in _RANGS:
		try:
			from utils import potentiel
			_RANGS[cle] = potentiel.rang_espece(espece_id, get_doc)["rang"]
		except Exception:
			_RANGS[cle] = None
	return _RANGS[cle]


def _perso(current_user: dict) -> dict:
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	return character


def _index_chaine(lieu_doc: dict) -> dict:
	"""Le lieu et ses ancêtres seuls : assez pour les prédicats (zone sauvage = hors cité),
	sans relire les 700 lieux du monde à chaque rendu de /play."""
	index, doc, vus = {}, lieu_doc, set()
	while doc and doc.get("_id") and doc["_id"] not in vus:
		vus.add(doc["_id"])
		index[doc["_id"]] = doc
		doc = get_doc(doc.get("lieu_parent")) if doc.get("lieu_parent") else None
	return index


def _index_complet() -> dict:
	return {d["_id"]: d for d in (find_docs({"type": "lieu"}, fields=CHAMPS_LIEU) or []) if d.get("_id")}


def _interlocuteurs(character: dict, lieu_doc: dict) -> dict:
	"""PNJ de guilde qui renseignent ICI : les recrues encore offertes au tableau d'une réception,
	et les PNJ présents (`pnj_present`, tirage d'entrée) qui portent `services.renseignement`."""
	sortie = {"recrue": [], "receptionniste": []}
	lieu_id = lieu_doc.get("_id")
	if not lieu_id:
		return sortie
	if lieu_doc.get("categorie") == "guilde_aventurier":
		maintenant = rens.now_epoch()
		sortie["recrue"] = [r for r in recrutement.recrues_du_giver(lieu_id)
							if int(r.get("expire_at") or maintenant + 1) > maintenant]
	present = character.get("pnj_present") or {}
	if present.get("lieu") == lieu_id:
		for pid in present.get("characters") or []:
			doc = get_doc(pid)
			if doc and (doc.get("services") or {}).get("renseignement"):
				sortie["receptionniste"].append(doc)
	return sortie


def _contexte(character: dict, complet=True) -> dict:
	"""Tout ce que lit une recherche : lieu, index, membres, méthodes exerçables ici.
	`complet=False` : index réduit à la chaîne du lieu (bouton 🔎 de /play) ; `"auto"` : complet
	seulement si un interlocuteur de guilde est là (ses sujets « du coin » balaient le pays)."""
	lieu_doc = get_doc(character.get("lieu", "")) or {}
	regles = rens.regles_de(get_doc)
	_, erreurs = rens.methodes_de(regles)
	for e in erreurs:
		print(f"[renseignement] méthode écartée : {e}")
	index = _index_complet() if complet is True else _index_chaine(lieu_doc)
	membres = expedition.membres(character, get_doc)
	relation = marche.relation_value(marche.get_relation(character, lieu_doc)) if lieu_doc else None
	apps = rens.applicables(lieu_doc, index, membres, regles,
							lambda m, cid: pouvoirs_objets.connait(m, cid, get_doc), relation,
							rens.informateur_ici(character, lieu_doc.get("_id", "")),
							_interlocuteurs(character, lieu_doc))
	if complet == "auto" and any(a["interlocuteur"] for a in apps):
		index = _index_complet()
	return {"lieu": lieu_doc, "regles": regles, "index": index, "membres": membres, "apps": apps}


def _coin(character: dict, ctx: dict) -> dict:
	"""Pays de la cité, rang retenu du joueur (cette guilde ou la capitale du pays)."""
	index, lieu_id = ctx["index"], ctx["lieu"].get("_id", "")
	cite = rens.cite_de(lieu_id, index) or {}
	pays = rens.pays_de(lieu_id, index) or {}
	capitale = rens.capitale_du_pays(pays.get("_id"), index) or {}
	return {"cite": cite.get("_id"), "pays": pays.get("_id"),
			"rang_joueur": rens.rang_joueur_guilde(character, cite.get("_id"), capitale.get("_id"))}


def _nom(m: dict) -> str:
	return (m or {}).get("prenom") or (m or {}).get("nom") or "Votre compagnon"


def _doc_cible(cible_id: str) -> dict | None:
	return get_doc(cible_id) if cible_id and cible_id.startswith(("espece:", "item:")) else None


def _ecole(app: dict) -> set:
	if not app["methode"]["cibles"]["ecole_vocation"]:
		return set()
	return rens.items_d_ecole(app["acteur"].get("voc"), get_doc("rules:vocations"), find_docs)


def _cibles(character: dict, app: dict) -> dict:
	"""Cibles proposées pour une méthode : quêtes, bestiaire, récits cédables."""
	m = app["methode"]
	ecole = _ecole(app)
	quetes_l, bestiaire_l = [], []
	if "quete" in m["modes"]:
		for q in character.get("quetes_actives") or []:
			cid = rens.cible_quete(q)
			if not cid or quetes.objectif_atteint(character, q):
				continue
			elite = (q.get("objectif") or {}).get("type") == "chasse" and m["cibles"]["elites"]
			if elite or rens.cible_ok(m, cid, _doc_cible(cid), _rang, ecole):
				quetes_l.append({"id": q.get("id"), "titre": q.get("titre", ""), "elite": elite})
	if "bestiaire" in m["modes"]:
		for eid in sorted((character.get("bestiaire") or {}).keys()):
			doc = _doc_cible(eid)
			if doc and rens.cible_ok(m, eid, doc, _rang, ecole):
				bestiaire_l.append({"id": eid, "nom": doc.get("nom") or eid})
	recits = []
	if "recit" in m["modes"]:
		recits = [{"cle": f"{r['espece']}|{r['lieu']}",
				   "texte": f"{(_doc_cible(r['espece']) or {}).get('nom') or r['espece']} — {r['label']}"}
				  for r in rens.recits_cedables(character, character.get("lieu", ""))]
	return {"quetes": quetes_l, "bestiaire": bestiaire_l, "recits": recits}


def _rang_pnj(app: dict) -> str | None:
	"""Rang qui borne l'interlocuteur : celui d'une recrue (dérivé de son niveau) ; aucun pour
	le réceptionniste, qui lit les archives de la Guilde."""
	if app["interlocuteur"] and app["methode"]["interlocuteur"] == "recrue":
		return rens.rang_de_niveau(rens.niveau_de(app["acteur"]))
	return None


def _monde(ctx: dict) -> dict:
	"""Donjons, zones, boutiques, distances depuis le lieu — lu une fois par requête."""
	donjons, zones_noms, zones_terrains, boutiques = _sources_monde(ctx)
	distances = focalisation.distances_depuis(focalisation.charger_graphe(find_docs), ctx["lieu"].get("_id", ""))
	return {"donjons": donjons, "zones_noms": zones_noms, "zones_terrains": zones_terrains,
			"boutiques": boutiques, "distances": distances}


def _sujets_coin(ctx: dict, coin: dict, monde: dict) -> dict:
	"""Ids des sujets « du coin », bornés au PAYS de la cité : espèces et matières des lieux du
	pays (et de leurs zones), donjons dont le portail est dans le pays."""
	pays, index = coin["pays"], ctx["index"]
	dans = {lid for lid in index if pays and any(d.get("_id") == pays for d in rens.chaine(lid, index))}
	dangers, ressources = set(), set()
	for lid in dans:
		dangers.update(e.get("espece") for e in index[lid].get("rencontres") or [] if e.get("espece"))
		ressources.update(e.get("ressource") for e in index[lid].get("ressources") or [] if e.get("ressource"))
	donjons = [d["_id"] for d in monde["donjons"] if d.get("portail") in dans]
	return {"dangers": sorted(dangers), "donjons": sorted(donjons), "ressources": sorted(ressources)}


def _nom_sujet(cid: str, monde: dict, index: dict) -> str:
	if cid.startswith("donjon:"):
		return next((d.get("nom") for d in monde["donjons"] if d.get("_id") == cid), None) or cid
	if cid.startswith("lieu:"):
		return lieu_label(index.get(cid) or {}, cid)
	return (_doc_cible(cid) or {}).get("nom") or cid.split(":", 1)[-1]


def _cible_de_quete(q: dict, index: dict) -> str | None:
	"""Cible d'une quête pour la Guilde : bête, matière, élite — ou le LIEU d'une visite, d'une
	escorte (rendez-vous, sinon destination), d'un transport (destination)."""
	obj = (q or {}).get("objectif") or {}
	if obj.get("type") in ("kill", "collect", "chasse"):
		return obj.get("cible")
	if obj.get("type") == "transport":
		return obj.get("cible")
	if obj.get("type") in rens.OBJECTIFS_LIEU:
		from utils import guides
		lieux = guides.lieux_de_cible(obj, index, q)
		return lieux[0] if lieux else None
	return None


def _cibles_guilde(character: dict, ctx: dict, app: dict, coin: dict, monde: dict) -> dict:
	"""Sujets d'un interlocuteur de guilde, chacun avec `bloque` (raison) si une borne de rang
	l'interdit : visible mais grisé, rien ne se paie."""
	rang_pnj = _rang_pnj(app)

	def entree(cid, titre, cle):
		grade = rens.grade_sujet(cid, monde["donjons"], _rang)
		return {"id": cle, "nom": titre, "bloque": rens.borne_rang(grade, rang_pnj, coin["rang_joueur"])}

	quetes_l = []
	for q in character.get("quetes_actives") or []:
		cid = _cible_de_quete(q, ctx["index"])
		if cid and not quetes.objectif_atteint(character, q):
			e = entree(cid, q.get("titre", ""), q.get("id"))
			quetes_l.append({**e, "titre": e["nom"]})
	sujets = _sujets_coin(ctx, coin, monde)
	return {"quetes": quetes_l, "bestiaire": [], "recits": [],
			**{mode: [entree(cid, _nom_sujet(cid, monde, ctx["index"]), cid) for cid in sujets[mode]]
			   for mode in rens.MODES_COIN if mode in app["methode"]["modes"]}}


def _cout_app(app: dict, niveau: str) -> int:
	if app["interlocuteur"] and app["methode"]["interlocuteur"] == "recrue":
		return rens.cout_recrue(niveau, rens.niveau_de(app["acteur"]))
	return rens.cout_cuivre(app["methode"], niveau)


def _vue_app(character: dict, app: dict, ctx: dict, extra: dict | None = None) -> dict:
	m = app["methode"]
	lieu_id = ctx["lieu"].get("_id", "")
	vue = {
		"id": m["id"], "cle": app["cle"], "nom": m["nom"], "icon": m["icon"], "informateur": m["informateur"],
		"acteur_id": app["acteur"].get("_id"), "acteur_nom": _nom(app["acteur"]),
		"interlocuteur": m["interlocuteur"], "interlocuteur_id": (app["interlocuteur"] or {}).get("_id"),
		"seuil": app["seuil"], "sans_jet": bool(m["niveau_fixe"]),
		"cout_max": rens.cout_max(m), "cout_base": rens.cout_cuivre(m, "rumeur"),
		"cout_pv": m["cout_pv"], "cout_pm": rens.cout_pm(m, get_doc),
		"modes": m["modes"], "disponible_dans": rens.disponible_dans(character, lieu_id, app["cle"]),
		"description": m["repliques"].get("description", ""),
	}
	if app["interlocuteur"]:
		vue["cout_base"], vue["cout_max"] = _cout_app(app, "rumeur"), _cout_app(app, "exact")
		vue["cout_pv"], vue["cout_pm"] = None, 0
		if m["interlocuteur"] == "recrue":
			voc = next((v.get("label") for v in (get_doc("rules:vocations") or {}).get("value") or []
						if v.get("id") == app["acteur"].get("voc")), "") or app["acteur"].get("voc", "")
			vue["nom"] = f"{_nom(app['acteur'])} — {voc}, rang {_rang_pnj(app)}"
		else:
			vue["nom"] = f"{_nom(app['acteur'])} — {m['nom']}"
		vue["cibles"] = _cibles_guilde(character, ctx, app, extra["coin"], extra["monde"])
	else:
		vue["cibles"] = _cibles(character, app)
	return vue


def _offre(character: dict, ctx: dict) -> dict:
	lieu_id = ctx["lieu"].get("_id", "")
	extra = None
	if any(a["interlocuteur"] for a in ctx["apps"]):
		extra = {"coin": _coin(character, ctx), "monde": _monde(ctx)}
	return {
		"lieu": lieu_label(ctx["lieu"], lieu_id),
		"methodes": [_vue_app(character, a, ctx, extra) for a in ctx["apps"]],
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}


def disponible(character: dict) -> bool:
	"""Le bouton 🔎 s'affiche-t-il ? (contexte de /play). Une méthode `via_pnj` (le réceptionniste)
	s'ouvre par le dialogue de son PNJ, pas par ce bouton."""
	try:
		return any(not a["methode"]["via_pnj"] for a in _contexte(character, complet=False)["apps"])
	except Exception as e:
		print(f"[renseignement] disponibilité illisible : {e}")
		return False


@renseignement_router.get("/renseignement/offre")
def offre(current_user: Annotated[dict, Depends(get_current_user)]):
	character = _perso(current_user)
	return _offre(character, _contexte(character, complet="auto"))


def _app(ctx: dict, methode_id: str, interlocuteur_id: str = "") -> dict:
	cle = f"{methode_id}|{interlocuteur_id}" if interlocuteur_id else methode_id
	app = next((a for a in ctx["apps"] if a["cle"] == cle), None)
	if not app:
		raise HTTPException(status_code=403, detail="Personne ici ne peut se renseigner ainsi.")
	return app


@renseignement_router.get("/renseignement/catalogue")
def catalogue(current_user: Annotated[dict, Depends(get_current_user)], methode: str = "", q: str = ""):
	"""Recherche libre : espèces et matières du catalogue qu'accepte la méthode, par nom."""
	character = _perso(current_user)
	ctx = _contexte(character, complet=False)
	app = _app(ctx, methode)
	m = app["methode"]
	texte = (q or "").strip().lower()[:40]
	if len(texte) < 2:
		return {"suggestions": []}
	ecole = _ecole(app)
	docs = []
	if m["cibles"]["especes"]:
		docs += find_docs({"type": "espece"}, fields=["_id", "nom", "tags"]) or []
	if m["cibles"]["ressources"]:
		docs += find_docs({"type": "item"}, fields=["_id", "nom", "categorie", "sous_categorie"]) or []
	sortie = []
	for d in docs:
		nom = str(d.get("nom") or "")
		if texte not in nom.lower():
			continue
		# ⚠️ Le grade minimum (simulation coûteuse) n'est vérifié qu'à la recherche elle-même.
		if rens.cible_ok(m, d["_id"], d, None, ecole):
			sortie.append({"id": d["_id"], "nom": nom})
	sortie.sort(key=lambda s: (not s["nom"].lower().startswith(texte), s["nom"]))
	return {"suggestions": sortie[:SUGGESTIONS_MAX]}


def _sources_monde(ctx: dict) -> tuple:
	donjons = find_docs({"type": "donjon"}) or []
	zones = find_docs({"type": "zone_influence"}, fields=["_id", "nom", "terrain_tags"]) or []
	boutiques = [d for d in ctx["index"].values() if d.get("stock_vente")]
	return (donjons, {z["_id"]: z.get("nom", "") for z in zones},
			{z["_id"]: z.get("terrain_tags") or [] for z in zones}, boutiques)


def _pistes_pour(cibles: list, m: dict, ctx: dict, donjons: list, boutiques: list, distances: dict,
				 exclure: set | None = None) -> list:
	toutes = []
	for cid in cibles:
		for p in rens.pistes_de(cid, m["sources"], ctx["index"], donjons, boutiques):
			if exclure and (p["cible"], p["lieu"]) in exclure:
				continue
			toutes.append(p)
	return rens.a_portee(toutes, distances, portee_max=m["portee_max"])


def _vitaux(membre: dict) -> dict:
	d = fiche.derived_de(membre)
	return {"currentPV": membre.get("currentPV", d["pv_max"]), "pv_max": d["pv_max"],
			"currentPM": membre.get("currentPM", d["pm_max"]), "pm_max": d["pm_max"]}


@renseignement_router.post("/renseignement/chercher")
def chercher(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Body {methode, mode: quete|bestiaire|libre|hasard|recit, cible?, quete_id?, recit?}."""
	character = _perso(current_user)
	ctx = _contexte(character)
	app = _app(ctx, str(body.get("methode") or ""), str(body.get("interlocuteur") or ""))
	if app["interlocuteur"]:
		return _chercher_guilde(character, ctx, app, body)
	m, acteur = app["methode"], app["acteur"]
	lieu_doc, lieu_id = ctx["lieu"], ctx["lieu"].get("_id", "")
	soi = acteur is character
	mode = str(body.get("mode") or "")
	if mode not in m["modes"]:
		raise HTTPException(status_code=422, detail="Cette méthode ne cherche pas ainsi.")
	attente = rens.disponible_dans(character, lieu_id, app["cle"])
	if attente:
		raise HTTPException(status_code=409, detail=f"On vous a déjà tout dit ici — revenez dans {max(1, attente // 60)} min.")

	# ── Cible ────────────────────────────────────────────────────────────────────
	ecole = _ecole(app)
	cible_id, elite, recit = None, None, None
	if mode == "quete":
		q = quetes.quete_active(character, str(body.get("quete_id") or ""))
		cible_id = rens.cible_quete(q)
		if not cible_id:
			raise HTTPException(status_code=404, detail="Quête introuvable dans vos quêtes actives.")
		if (q.get("objectif") or {}).get("type") == "chasse" and m["cibles"]["elites"]:
			elite = q["objectif"]
	elif mode == "bestiaire":
		cible_id = str(body.get("cible") or "")
		if cible_id not in (character.get("bestiaire") or {}):
			raise HTTPException(status_code=404, detail="Cette espèce n'est pas dans votre bestiaire.")
	elif mode == "libre":
		cible_id = str(body.get("cible") or "")
	elif mode == "recit":
		cle = str(body.get("recit") or "")
		recit = next((r for r in rens.recits_cedables(character, lieu_id)
					  if f"{r['espece']}|{r['lieu']}" == cle), None)
		if not recit:
			raise HTTPException(status_code=404, detail="Vous n'avez pas ce récit à offrir ici.")
	doc_cible = _doc_cible(cible_id) if cible_id else None
	if cible_id and not elite:
		if not doc_cible:
			raise HTTPException(status_code=404, detail="Cible inconnue.")
		if not rens.cible_ok(m, cible_id, doc_cible, _rang, ecole):
			raise HTTPException(status_code=422, detail="Ce n'est pas le genre de chose qu'on apprend ainsi.")

	# ── Coûts possibles (vérifiés AVANT le jet) ──────────────────────────────────
	if money_to_cuivre(character) < rens.cout_max(m):
		raise HTTPException(status_code=409, detail=f"Il faut pouvoir payer jusqu'à {rens.cout_max(m)} cuivres.")
	pm = rens.cout_pm(m, get_doc)
	if pm and int(_vitaux(acteur)["currentPM"]) < pm:
		raise HTTPException(status_code=409, detail=f"{_nom(acteur)} n'a pas assez de PM ({pm}).")

	# ── Pistes et jet ────────────────────────────────────────────────────────────
	rand = _hasard()
	donjons, zones_noms, zones_terrains, boutiques = _sources_monde(ctx)
	distances = focalisation.distances_depuis(focalisation.charger_graphe(find_docs), lieu_id)
	donjons_noms = {d["_id"]: d.get("nom", "") for d in donjons}
	connus = rens.cles_bestiaire(character)
	monde = [c for c in rens.toutes_cibles(m["sources"], ctx["index"], donjons, boutiques)
			 if rens.cible_ok(m, c, _doc_cible(c), None, ecole)]
	if elite:
		porteur = elite.get("lieu")
		pistes = [{"type": "lieu", "porteur": porteur, "lieu": porteur, "cible": elite.get("cible"),
				   "distance": distances.get(porteur, 0)}] if porteur else []
		res = rens.resoudre(m, app["seuil"], pistes, rand=rand, sans_jet=True)
		cible_id = elite.get("cible")
		doc_cible = _doc_cible(cible_id)
	else:
		if mode in ("hasard", "recit"):
			plafond = rens.rang_index(_rang(recit["espece"])) if recit else None
			cibles = [c for c in monde if not recit or (c.startswith("espece:") and rens.rang_index(_rang(c)) <= plafond)]
			if m["cibles"]["grade_min"]:
				cibles = [c for c in cibles if rens.cible_ok(m, c, _doc_cible(c), _rang, ecole)]
			pistes = _pistes_pour(cibles, m, ctx, donjons, boutiques, distances, exclure=connus)
		else:
			pistes = _pistes_pour([cible_id], m, ctx, donjons, boutiques, distances)
		fausses = [p for p in _pistes_pour(monde, m, ctx, donjons, boutiques, distances)
				   if p["cible"] != cible_id]
		res = rens.resoudre(m, app["seuil"], pistes, rand=rand, ponderer=mode in ("hasard", "recit"),
							fausses=fausses)
		if res["piste"] and mode in ("hasard", "recit"):
			cible_id = res["piste"]["cible"]
			# Rumeur FAUSSE sans cible choisie : on nomme une vraie cible des environs, mais au
			# terrain d'une AUTRE (sinon la « fausse » piste dirait vrai sur sa propre cible).
			if res["fausse"]:
				autres = sorted(set(monde) - {cible_id})
				if autres:
					cible_id = rand.choice(autres)
			doc_cible = _doc_cible(cible_id)
	niveau = res["niveau"]

	# ── Texte ────────────────────────────────────────────────────────────────────
	cible_txt = rens.nom_cible(cible_id, doc_cible) if cible_id else "quoi que ce soit"
	rang = (rens.rang_piste(res["piste"], ctx["index"], donjons, _rang)
			if niveau == "exact" and res["piste"] and not elite else None)
	intro = m["repliques"].get("intro", "")
	txt = rens.texte_resultat(res, cible_txt, _nom(acteur), ctx["index"], zones_noms, zones_terrains,
							  donjons_noms, rang, intro, cible_id or "")
	if elite and res["piste"]:
		pos = elite.get("position") or {}
		grade = (get_doc(elite.get("profil") or "") or {}).get("nom") or ""
		ou = lieu_label(ctx["index"].get(elite.get("lieu")) or {}, elite.get("lieu", ""))
		txt["texte"] = ((intro.strip() + " ") if intro else "") + (
			f"{_nom(acteur)} apprend où se terre {cible_txt}" + (f" « {grade} »" if grade else "")
			+ f" : {ou}" + (f", vers la case {pos.get('x')}, {pos.get('y')}" if pos else "") + ".")
		txt["lieu_id"], txt["lieu_label"] = elite.get("lieu"), ou

	# ── Paiement ─────────────────────────────────────────────────────────────────
	cuivre = rens.cout_cuivre(m, niveau if niveau in rens.NIVEAUX else "rumeur")
	if cuivre and debit_character(character, cuivre) is None:
		raise HTTPException(status_code=409, detail="Fonds insuffisants.")
	pv_perdus = 0
	if m["cout_pv"]:
		pv_perdus = rens.lancer(m["cout_pv"] if m["cout_pv"] != "monde" else character_stats.RENS_BRAS_DE_FER_PV, rand)
		v = _vitaux(acteur)
		acteur["currentPV"] = max(1, int(v["currentPV"]) - pv_perdus)
	if pm:
		acteur["currentPM"] = max(0, int(_vitaux(acteur)["currentPM"]) - pm)
	belle = niveau == "exact" and res["jet"] is not None
	pourboire = 0
	if m["pourboire"] and belle:
		pourboire = round(m["cout"] * float(character_stats.RENS_POURBOIRE_FACTEUR)) + rens.lancer(
			character_stats.RENS_POURBOIRE_DES, rand)
		credit_character(character, pourboire)
	xp = None
	if belle and int(character_stats.RENS_XP_BELLE) > 0:
		xp = grant_xp(acteur, int(character_stats.RENS_XP_BELLE))

	# ── Ce que le joueur apprend ─────────────────────────────────────────────────
	piste_info = {"texte": txt["texte"], "cible": cible_id or "", "cible_nom": cible_txt,
				  "niveau": niveau if not res["fausse"] else "rumeur",
				  "lieu_id": txt["lieu_id"], "lieu_label": txt["lieu_label"], "rang": rang}
	rens.apprendre(character, piste_info, lieu_label(lieu_doc, lieu_id))
	note = False
	if m["note"] and niveau in ("region", "exact") and not res["fausse"]:
		ref = rens.nouvelle_note(_nom(acteur), piste_info)
		if carried_weight(acteur) + item_ref_weight(ref) <= charge_max_of(acteur):
			acteur.setdefault("inventaire", []).append(ref)
			note = True
	if recit:
		cedes = dict(character.get("recits_cedes") or {})
		cedes[lieu_id] = list(cedes.get(lieu_id) or []) + [f"{recit['espece']}|{recit['lieu']}"]
		character["recits_cedes"] = cedes
	rens.marquer_delai(character, lieu_id, app["cle"])

	# ── Persistance : le principal (bourse, carnet) d'abord, puis l'acteur compagnon. ──
	relation = None
	if cuivre and lieu_doc:
		relation = marche.get_relation(character, lieu_doc)
		if not marche.compter_transaction(relation)["modifie"]:
			relation = None
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	if not soi:
		save_doc(acteur)
	if relation:
		save_doc(relation)

	out = {
		"resultat": {
			"texte": txt["texte"], "niveau": niveau, "niveau_label": rens.LIBELLE_NIVEAU.get(niveau, ""),
			"cout": cuivre, "pv_perdus": pv_perdus, "pm": pm, "pourboire": pourboire,
			"xp": (xp or {}).get("xp_gain", 0), "note": note, "acteur": _nom(acteur),
		},
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"journal": journal.journal_payload(character, get_doc),
		"vitaux": {"id": acteur.get("_id"), **_vitaux(acteur)},
		**_offre(character, _contexte(character, complet="auto")),
	}
	if note and soi:
		out["inventaire_payload"] = _inventory_payload(character)
	if xp and soi:
		out["fiche"] = fiche.fiche_resync(character, get_doc, find_docs)
	return out


def _chercher_guilde(character: dict, ctx: dict, app: dict, body: dict) -> dict:
	"""Recrue du tableau ou réceptionniste. Body {methode, interlocuteur, mode: quete|dangers|
	donjons|ressources, quete_id? | cible?}. Bornes de rang AVANT tout paiement ; le délai court
	par interlocuteur ; une recrue répond avec son MEILLEUR savoir (affronté > origine > métier)."""
	m, pnj = app["methode"], app["acteur"]
	recrue = m["interlocuteur"] == "recrue"
	lieu_doc, lieu_id, index = ctx["lieu"], ctx["lieu"].get("_id", ""), ctx["index"]
	mode = str(body.get("mode") or "")
	if mode not in m["modes"]:
		raise HTTPException(status_code=422, detail="On ne vous renseigne pas là-dessus ici.")
	attente = rens.disponible_dans(character, lieu_id, app["cle"])
	if attente:
		raise HTTPException(status_code=409, detail=f"{_nom(pnj)} vous a déjà tout dit — revenez dans {max(1, attente // 60)} min.")
	coin, monde = _coin(character, ctx), _monde(ctx)
	donjons, distances = monde["donjons"], monde["distances"]
	sujets = _sujets_coin(ctx, coin, monde)

	# ── Sujet ────────────────────────────────────────────────────────────────────
	if mode == "quete":
		q = quetes.quete_active(character, str(body.get("quete_id") or ""))
		cible_id = _cible_de_quete(q, index) if q else None
		if not cible_id:
			raise HTTPException(status_code=404, detail="Quête introuvable dans vos quêtes actives.")
	else:
		cible_id = str(body.get("cible") or "")
		if cible_id not in sujets.get(mode, []):
			raise HTTPException(status_code=404, detail="Personne ici n'en a entendu parler.")
	grade = rens.grade_sujet(cible_id, donjons, _rang)
	raison = rens.borne_rang(grade, _rang_pnj(app), coin["rang_joueur"])
	if raison:
		raise HTTPException(status_code=403, detail=raison)
	if money_to_cuivre(character) < _cout_app(app, "exact"):
		raise HTTPException(status_code=409, detail=f"Il faut pouvoir donner jusqu'à {_cout_app(app, 'exact')} cuivres.")

	# ── Pistes ───────────────────────────────────────────────────────────────────
	speciales = rens.pistes_speciales(cible_id, index, donjons)
	brutes = speciales if speciales is not None else rens.pistes_de(
		cible_id, list(rens.SOURCES), index, donjons, monde["boutiques"])
	tout = rens.a_portee(brutes, distances, portee_lieux=len(index) + 1)
	pistes_pays = [p for p in tout if rens.dans_pays(p, coin["pays"], index)]
	coin_seul = mode in rens.MODES_COIN
	seuil_v, sans_jet = app["seuil"], False
	if recrue:
		pistes_dangers = [p for cid in sujets["dangers"]
						  for p in rens.a_portee(rens.pistes_de(cid, ["lieu", "zone"], index, donjons, []),
												 distances, portee_lieux=len(index) + 1)
						  if rens.dans_pays(p, coin["pays"], index)]
		vus = rens.affrontes(pnj.get("_id"), pistes_dangers, _rang_pnj(app), _rang)
		metier = rens.methode_de_vocation(pnj.get("voc"), rens.methodes_de(ctx["regles"])[0])
		pistes_metier = []
		if metier and speciales is None and rens.cible_ok(metier, cible_id, _doc_cible(cible_id), _rang):
			pistes_metier = rens.a_portee(rens.pistes_de(cible_id, metier["sources"], index, donjons, monde["boutiques"]),
										  distances, portee_max=metier["portee_max"])
			if coin_seul:
				pistes_metier = [p for p in pistes_metier if rens.dans_pays(p, coin["pays"], index)]
		source, pistes, sans_jet = rens.savoir_recrue(cible_id, vus, pistes_pays, pistes_metier)
		if source == "origine":
			seuil_v = max(rens.SEUIL_MIN, min(rens.SEUIL_MAX, seuil_v + int(character_stats.RENS_RECRUE_ORIGINE_BONUS)))
	else:
		pistes = pistes_pays if coin_seul else rens.a_portee(brutes, distances)
	fausses = []
	if speciales is None:
		fausses = [p for cid in sujets["dangers"] + sujets["ressources"] if cid != cible_id
				   for p in rens.a_portee(rens.pistes_de(cid, ["lieu", "zone"], index, donjons, []), distances)]
	rand = _hasard()
	res = rens.resoudre(m, seuil_v, pistes, rand=rand, fausses=fausses, sans_jet=sans_jet)
	niveau = res["niveau"]

	# ── Texte ────────────────────────────────────────────────────────────────────
	intro = m["repliques"].get("intro", "")
	nom_pnj = _nom(pnj)
	oui_dire = []
	if cible_id.startswith("donjon:"):
		donjon = next(d for d in donjons if d.get("_id") == cible_id)
		especes = rens.especes_du_donjon(donjon)
		noms = [rens.nom_cible(e, _doc_cible(e)) for e in especes]
		etat = rens.etat_donjon(donjon, lambda s: donjon_util.donjon_purge(character, s, get_doc(s)),
								lambda s: donjon_util.donjon_reinfeste(character, get_doc(s)))
		txt = {**rens.texte_donjon(res, donjon, noms, etat, nom_pnj, grade, intro), "lieu_id": None, "lieu_label": ""}
		cible_txt = f"« {donjon.get('nom') or cible_id} »"
		if niveau == "exact":
			salle = (res["piste"] or {}).get("lieu")
			oui_dire = [(e, salle, donjon.get("nom") or "") for e in especes]
	elif cible_id.startswith("lieu:"):
		cible_txt = _nom_sujet(cible_id, monde, index)
		txt = rens.texte_lieu(res, cible_txt, nom_pnj, index, intro)
	else:
		doc_cible = _doc_cible(cible_id)
		# Rumeur fausse : la cible reste celle demandée, seul le lieu ment.
		cible_txt = rens.nom_cible(cible_id, doc_cible)
		rang = rens.rang_piste(res["piste"], index, donjons, _rang) if niveau == "exact" and res["piste"] else None
		txt = rens.texte_resultat(res, cible_txt, nom_pnj, index, monde["zones_noms"], monde["zones_terrains"],
								  {d["_id"]: d.get("nom", "") for d in donjons}, rang, intro, cible_id)
		if sans_jet and res["piste"]:
			txt["texte"] = txt["texte"].replace(" apprend qu'on trouve ", " en a affronté de ses mains : on trouve ", 1)

	# ── Paiement, liens ──────────────────────────────────────────────────────────
	cuivre = _cout_app(app, niveau if niveau in rens.NIVEAUX else "rumeur")
	if cuivre and debit_character(character, cuivre) is None:
		raise HTTPException(status_code=409, detail="Fonds insuffisants.")
	if recrue and int(character_stats.RENS_RECRUE_AFFINITE):
		recrutement.ajuster_affinite(character, pnj["_id"], int(character_stats.RENS_RECRUE_AFFINITE))
	xp = None
	# XP au JOUEUR sur belle réussite au jet du réceptionniste (c'est son Cha qui joue) ; le jet
	# d'une recrue est le sien : rien à gagner pour le joueur.
	if not recrue and niveau == "exact" and res["jet"] is not None and int(character_stats.RENS_XP_BELLE) > 0:
		xp = grant_xp(character, int(character_stats.RENS_XP_BELLE))
	piste_info = {"texte": txt["texte"], "cible": cible_id if not cible_id.startswith(("lieu:", "donjon:")) else "",
				  "cible_nom": cible_txt, "niveau": "rumeur" if res["fausse"] else niveau,
				  "lieu_id": txt.get("lieu_id"), "lieu_label": txt.get("lieu_label", ""), "rang": grade}
	rens.apprendre(character, piste_info, lieu_label(lieu_doc, lieu_id))
	for eid, salle, label in oui_dire:
		if salle:
			journal.noter_oui_dire(character, eid, salle, label)
	rens.marquer_delai(character, lieu_id, app["cle"])
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	out = {
		"resultat": {
			"texte": txt["texte"], "niveau": niveau, "niveau_label": rens.LIBELLE_NIVEAU.get(niveau, ""),
			"cout": cuivre, "pv_perdus": 0, "pm": 0, "pourboire": 0,
			"xp": (xp or {}).get("xp_gain", 0), "note": False, "acteur": nom_pnj,
			"affinite": int(character_stats.RENS_RECRUE_AFFINITE) if recrue else 0,
		},
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"journal": journal.journal_payload(character, get_doc),
		**_offre(character, _contexte(character, complet="auto")),
	}
	if xp:
		out["fiche"] = fiche.fiche_resync(character, get_doc, find_docs)
	return out


@renseignement_router.post("/renseignement/lire")
def lire(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Lire une note de renseignement du sac du PRINCIPAL (body {index}) : la piste s'inscrit à
	son bestiaire 👂 et à son carnet — même achetée ou reçue."""
	character = _perso(current_user)
	try:
		ref = (character.get("inventaire") or [])[int(body.get("index"))]
	except (TypeError, ValueError, IndexError):
		raise HTTPException(status_code=404, detail="Objet introuvable dans votre sac.")
	if not rens.est_note(ref):
		raise HTTPException(status_code=422, detail="Ce n'est pas une note de renseignement.")
	lieu_doc = get_doc(character.get("lieu", "")) or {}
	change = rens.apprendre(character, ref["piste"], lieu_label(lieu_doc, character.get("lieu", "")))
	if change and save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	return {"texte": ref["piste"].get("texte", ""), "appris": change,
			"journal": journal.journal_payload(character, get_doc)}

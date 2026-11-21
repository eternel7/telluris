# routers/colonisation.py
# Endpoints de la voie de colonisation : lire un site et FONDER (sur la carte d'un pays), puis,
# DANS l'implantation, le panneau (site, population, bâtiments, défense), les dons, les
# bâtiments, les chantiers, le personnel nommé et l'association. Le moteur est
# utils/colonisation.py ; ici l'accès, l'argent et la persistance.
#
# Pattern routers/proprietes.py : prélude d'accès, payload qui RECALCULE tout le bloc
# (Convention §10), `save_doc(...) is None ⇒ 409`, débit APRÈS toutes les gardes, docs annexes
# neufs sauvés AVANT le personnage.
#
# ⚠️ Seul le personnage PRINCIPAL a un statut (§ 10) : le rôle n'est jamais lu sur un compagnon ;
# `compagnon_id` ne désigne qu'un SAC (dons, rangements).

import os
import unicodedata
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, find_docs, suivre_modele
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre, resolve_item_ref, item_ref_id, credit_character,
	item_ref_weight,
)
from utils.marche import debit_character
from utils import colonisation
from utils import echanges_cite
from utils import filtres_boutique
from utils import proprietes
from utils import recrutement
from utils import contenants
from utils import sacs_groupe
from utils import montures
from utils import escorte
from utils import traces
from utils.zones import load_zone_defs_for_lieu, peupler_lieu
from utils.lieux import connexions_du_lieu, get_lieu_links, ORIGINES_IMAGE_LIEU, TOWNS_IMAGES_PATH
# Sens d'import : `routers/colonisation` → `routers/user`, jamais l'inverse.
from routers.user import _inventory_payload

colonisation_router = APIRouter()

CONFLIT = "Conflit de sauvegarde — réessayez."


# ── Accès ────────────────────────────────────────────────────────────────────────────

def _personnage(current_user: dict) -> dict:
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	return character


def _sauver(*docs) -> None:
	"""Sauve dans l'ordre donné ; un échec lève 409 avant que la suite ne s'engage."""
	for d in docs:
		if save_doc(d) is None:
			raise HTTPException(status_code=409, detail=CONFLIT)


def lire_site(pays_doc: dict, position, reg: dict) -> dict:
	"""Tout ce qui se lit sur la carte du pays autour d'une case : `{relies, zone_defs, fiche,
	tags}`. Partagé avec `/play` (rattrapage). Lu sur le contenu EFFECTIF du pays
	(`zones.peupler_lieu` : défauts des zones compris), copie jamais sauvée."""
	pays_doc = peupler_lieu(pays_doc, get_doc) or {}
	relies = colonisation.lieux_relies(connexions_du_lieu(pays_doc.get("_id")), pays_doc.get("_id"), get_doc)
	zone_defs = load_zone_defs_for_lieu(pays_doc, get_doc)
	ids = {r.get("ressource") for r in pays_doc.get("ressources") or [] if r.get("ressource")}
	items = {i: d for i, d in ((i, get_doc(i)) for i in ids) if d}
	# Danger : rang de la pire rencontre possible ici — la mesure même des traces de monstres.
	x, y = colonisation._xy(position)
	menace = traces.menace_lieu(pays_doc, {"x": x, "y": y}, get_doc,
								find_docs({"type": "profil"}) or [], ville=False) if pays_doc.get("rencontres") else None
	return {"relies": relies, "zone_defs": zone_defs,
			"fiche": colonisation.fiche_site(pays_doc, position, zone_defs, relies, reg, items=items, menace=menace),
			"tags": colonisation.tags_site(pays_doc, position, zone_defs)}


def site_de(imp: dict, reg: dict) -> dict:
	"""Fiche de site d'une implantation, relue sur son pays (jamais stockée)."""
	origine = imp.get("origine") or {}
	pays = get_doc(origine.get("lieu") or "") or {}
	return lire_site(pays, origine.get("pos") or [0, 0], reg)["fiche"]


def tous_les_modeles() -> list:
	return find_docs({"type": "lieu", "tags": {"$elemMatch": {"$eq": colonisation.TAG_MODELE}}}) or []


def _vignettes(propositions: list) -> list:
	"""Vignettes de choix d'un modèle (§ 12.2) ; un modèle injouable (sans grille, sans entrée
	ou sans image sur le disque) n'est pas proposé."""
	out = []
	for p in propositions:
		m = p["modele"]
		route = next((r for r, chemin in ORIGINES_IMAGE_LIEU
					  if m.get("image") and os.path.exists(os.path.join(chemin, m["image"]))), None)
		if not colonisation.modele_valide(m) or not route:
			continue
		out.append({"id": m["_id"], "label": m.get("label", ""), "image": m["image"], "route": route,
					"dimensions": m.get("dimensions"), "partages": p["partages"], "generique": p["generique"]})
	return out


def _implantations_du_pays(pays_id) -> list:
	return find_docs({"type": colonisation.TYPE_DOC, "lieu_parent": pays_id}) or []


def _lien_et_portes(imp: dict) -> tuple[dict | None, dict]:
	"""La connexion vers le pays et les portes des sous-lieux ({id du bâtiment: lien})."""
	portes = {b["id"]: p for b in imp.get("batiments") or []
			  if b.get("lien") and (p := get_doc(b["lien"]))}
	return get_doc(imp.get("lien") or ""), portes


def suivre_modele_ici(imp: dict, reg: dict) -> None:
	"""`/play` dans une implantation : sortie, bâtiments et portes suivent la grille ACTUELLE du
	lieu modèle (`colonisation.suivre_entrees`) ; best-effort, rejoué au passage suivant."""
	lien, portes = _lien_et_portes(imp)
	imp_change, lien_change, changees = colonisation.suivre_entrees(imp, reg, lien, portes)
	for d in changees + ([lien] if lien_change and lien else []) + ([imp] if imp_change else []):
		save_doc(d)


def _ici(current_user: dict) -> tuple[dict, dict, dict, str]:
	"""(personnage, implantation, règles, rôle) : il faut être DANS l'implantation."""
	character = _personnage(current_user)
	imp = get_doc(character.get("lieu", ""))
	if not imp or not colonisation.est_implantation(imp):
		raise HTTPException(status_code=403, detail="Vous n'êtes dans aucune implantation.")
	if colonisation.synchroniser_association(character, get_doc):
		save_doc(character)
	return character, imp, colonisation.regles(get_doc), colonisation.role_de(character, imp)


def _exiger(role: str, *attendus) -> None:
	if role not in attendus:
		raise HTTPException(status_code=403, detail="Seul le fondateur peut faire cela."
							if attendus == (colonisation.FONDATEUR,) else "Il faut être fondateur ou associé.")


def rattraper_ici(character: dict, imp: dict, reg: dict, role: str, site: dict, employes: list) -> list:
	"""Rattrapage PARESSEUX du temps écoulé, déclenché par la présence du fondateur ou d'un
	associé (§ 10). Sauve les PNJ touchés puis le lieu ; renvoie les événements (toasts)."""
	if not colonisation.vaut_presence(role):
		return []
	avant = imp.get("fondateur_rang")
	if role == colonisation.FONDATEUR:
		colonisation.noter_rang(imp, character)
	bilan = colonisation.rattraper(imp, reg, site, employes)
	evenements = list(bilan["evenements"])
	if bilan["passes"] or bilan.get("evenements_attente") or imp.get("fondateur_rang") != avant:
		# La production vend son surplus aux boutiques du lieu (2 jours au plus, § 8).
		boutiques = echanges_cite.boutiques_cite(imp["_id"], find_docs)
		vente = colonisation.echanger(imp, reg, employes, boutiques,
									  get_doc, resolve_item_ref, bilan["passes"], site=site, find_docs_fn=find_docs)
		if vente["gain"]:
			evenements.append(f"La production s'est vendue : {vente['gain']} cu en caisse.")
		# L'intendant comble les stocks bas mis en consigne (boutiques, convoi, troc).
		appro = colonisation.approvisionner(
			imp, reg, employes, boutiques, get_doc, resolve_item_ref,
			lambda item: colonisation.stock_de_item(item, filtres_boutique.filtres_item(item), reg),
			bilan["passes"], cite=_cite_du_convoi(imp, reg))
		evenements.extend(appro["evenements"])
		vues = {d.get("_id") for d in vente["touchees"]}
		for d in (bilan["employes_touches"] + vente["touchees"] + [b for b in appro["touchees"] if b.get("_id") not in vues]
				  + colonisation.synchroniser_tenanciers(imp, reg, employes, get_doc)):
			save_doc(d)
		negociant = colonisation.negociant_de(imp, reg, employes)
		if negociant and vente["gain"]:
			save_doc(negociant)
		save_doc(imp)        # best-effort : un conflit sera rejoué au prochain passage
	return evenements


def _cite_du_convoi(imp: dict, reg: dict) -> dict | None:
	"""`{"label", "distance"}` de la cité la plus proche, où part le charretier ; None si aucun
	convoi ne peut partir (aucune consigne d'achat, aucune cité reliée au pays). Lu seulement
	quand une consigne est active : les connexions du pays ne se relisent pas à chaque passage."""
	if not any(colonisation.consigne(imp, reg, s)["acheter"] for s in reg.get("stocks") or []):
		return None
	pays = imp.get("lieu_parent")
	pos = (imp.get("origine") or {}).get("pos")
	if not pays or not pos:
		return None
	proches = colonisation.cites_de_la_charte(colonisation.lieux_relies(connexions_du_lieu(pays), pays, get_doc), pos)
	if not proches:
		return None
	return {"label": proches[0].get("label") or "", "distance": colonisation.distance(proches[0]["pos"], pos)}


def _images_des_villes() -> dict:
	"""{categorie: image} des boutiques de cité existantes (la première par `_id`) : une boutique
	de colonie prend l'intérieur d'une boutique de ville du même métier."""
	out = {}
	for d in sorted(find_docs({"type": "lieu"}, ["_id", "categorie", "image"]) or [], key=lambda d: str(d.get("_id"))):
		if d.get("categorie") and d.get("image") and os.path.exists(os.path.join(TOWNS_IMAGES_PATH, d["image"])):
			out.setdefault(d["categorie"], d["image"])
	return out


def image_sous_lieu(categorie: str, prefixe: str | None = None, images_villes: dict | None = None) -> str:
	"""Image d'intérieur : la première `<prefixe ou categorie>_europe*` du dossier des villes, sinon
	celle d'une boutique de cité du même métier."""
	debut = prefixe or f"{categorie}_europe"
	try:
		fichiers = sorted(f for f in os.listdir(TOWNS_IMAGES_PATH) if f.startswith(debut))
	except OSError:
		fichiers = []
	if fichiers:
		return fichiers[0]
	if prefixe:
		return ""
	return (images_villes if images_villes is not None else _images_des_villes()).get(categorie, "")


def fichiers_towns() -> list:
	"""Noms du dossier des images de lieux (icônes de carte comprises)."""
	try:
		return os.listdir(TOWNS_IMAGES_PATH)
	except OSError:
		return []


def regions_du_monde() -> dict:
	return (get_doc("rules:regions") or {}).get("regions") or {}


def categories_disponibles() -> list:
	"""Métiers achetables comme en ville : le marchand générique `pnj:marchand_<cat>` existe (il
	tient la boutique) et une image d'intérieur aussi. L'auberge s'y ajoute (sans tenancier)."""
	prefixe = "pnj:marchand_"
	images = _images_des_villes()
	cats = [d["_id"][len(prefixe):] for d in (find_docs({"type": "pnj"}, ["_id"]) or [])
			if str(d.get("_id", "")).startswith(prefixe)]
	return sorted(c for c in set(cats) if image_sous_lieu(c, images_villes=images))


def _payload(character: dict, imp: dict, reg: dict, role: str, site: dict | None = None,
			 employes: list | None = None, extra: dict | None = None) -> dict:
	site = site if site is not None else site_de(imp, reg)
	employes = employes if employes is not None else colonisation.employes_effectifs(imp, get_doc)
	cat = proprietes.catalogue(get_doc)
	payload = colonisation.vue(imp, reg, role, site, employes, cat,
							   disponibles=categories_disponibles() if role == colonisation.FONDATEUR else ())
	payload["purse"] = cuivre_to_purse(money_to_cuivre(character))
	payload["demande_en_attente"] = any(d.get("id") == character.get("_id") for d in imp.get("demandes") or [])
	payload["peut_demander"] = colonisation.peut_demander(character, imp, reg)[0]
	payload["position"] = character.get("position")
	payload["dons_possibles"] = _dons_possibles(character, reg)
	payload["reperes"] = colonisation.reperes_carte(imp, reg)
	payload["guilde"] = _vue_guilde(character, imp, reg, employes)
	if role in (colonisation.FONDATEUR, colonisation.ASSOCIE):
		payload["plan"] = _plan(imp)
	if role == colonisation.FONDATEUR:
		# Sélecteur 🏷️ de l'icône montrée sur la carte du pays.
		payload["icone_carte"] = colonisation.vue_icone(imp, reg, fichiers_towns(), regions_du_monde())
	if role == colonisation.FONDATEUR and colonisation.chantier_pret(imp) \
			and imp["chantier"]["genre"] == colonisation.CHANTIER_STATUT:
		# § 12.5 : le choix du modèle est reproposé — celui qui partage le plus de tags avec
		# le modèle ACTUEL en tête, présélectionné.
		actuel = get_doc(imp.get("modele") or "") or {}
		payload["modeles"] = _vignettes(colonisation.modeles_proposes(
			tous_les_modeles(), imp["chantier"]["objet"], actuel.get("tags") or [],
			(imp.get("origine") or {}).get("lieu"), reg))
	if extra:
		payload.update(extra)
	return payload


def _plan(imp: dict) -> dict | None:
	"""Mini-plan de l'onglet Bâtiments : image et grille du lieu modèle (lien pur, posées par
	`get_doc`) et ses entrées ; None sans grille ou sans image sur le disque."""
	dims, image = imp.get("dimensions") or {}, imp.get("image")
	route = next((r for r, chemin in ORIGINES_IMAGE_LIEU
				  if image and os.path.exists(os.path.join(chemin, image))), None)
	if not dims.get("x") or not dims.get("y") or not route:
		return None
	return {"image": f"/{route}/{image}", "dimensions": {"x": dims["x"], "y": dims["y"]},
			"entrees": imp.get("entrees") or []}


def _sacs_dons(character: dict) -> list:
	"""Les sacs où l'on puise un don : le principal EN TÊTE, ses porteurs (compagnons puis
	montures, `recrutement.porteurs_effectifs`), puis les contenants ouverts de tous ces sacs
	(sacs virtuels, `contenants.avec_contenants`). ⚠️ Source UNIQUE de la liste des dons et
	de `donner` : les deux doivent voir les mêmes sacs, adressés par `_id`."""
	return contenants.avec_contenants([character] + recrutement.porteurs_effectifs(character, get_doc),
									  get_doc, colonisation.now_epoch())


def _nom_sac(sac: dict, character: dict) -> str:
	"""Qui porte l'objet : vide pour le principal, le nom du compagnon / de la monture, ou
	celui du contenant (« Sac de Manannán ») pour un sac virtuel."""
	if sac is character:
		return ""
	if contenants.est_virtuel(sac):
		return sac.get("nom") or ""
	return proprietes.nom_personnage(sac) if sac.get("prenom") else (sac.get("nom") or "")


def _dons_possibles(character: dict, reg: dict, sacs: list | None = None) -> list:
	"""Objets du GROUPE qu'un stock accepte :
	`[{sac, porteur, index, item_id, nom, icon, stock, stock_label, unites}]`."""
	labels = reg.get("stocks_labels") or {}
	out = []
	for sac in sacs if sacs is not None else _sacs_dons(character):
		porteur = _nom_sac(sac, character)
		for i, ref in enumerate(sac.get("inventaire") or []):
			item = resolve_item_ref(ref)
			if not item:
				continue
			regle = colonisation.stock_de_item(item, filtres_boutique.filtres_item(item), reg)
			if regle:
				out.append({"sac": sac.get("_id"), "porteur": porteur,
							"index": i, "item_id": item_ref_id(ref), "nom": item.get("nom", ""),
							"icon": item.get("icon", ""), "stock": regle["stock"],
							"stock_label": labels.get(regle["stock"], regle["stock"]),
							"unites": colonisation.unites_de_item(item, regle)})
	return out


# ── Fonder (§ 2, § 3, § 12.2) ────────────────────────────────────────────────────────

def _payload_site(character: dict, pays_doc: dict, reg: dict) -> dict:
	position = character.get("position") or {}
	lu = lire_site(pays_doc, position, reg)
	implantations = _implantations_du_pays(pays_doc.get("_id"))
	ok, raison = colonisation.peut_fonder(character, pays_doc, position, lu["relies"], implantations, reg)
	premier = (colonisation.paliers(reg) or [{}])[0]
	return {
		"site": lu["fiche"], "tags": lu["tags"],
		"peut_fonder": ok, "refus": raison,
		"charte": colonisation.charte_de(character),
		"cites": [{"id": c["id"], "label": c["label"]} for c in colonisation.cites_de_la_charte(lu["relies"], position)],
		"palier": {"id": premier.get("id"), "label": premier.get("label")},
		"modeles": _vignettes(colonisation.modeles_proposes(
			tous_les_modeles(), premier.get("id"), lu["tags"], pays_doc.get("_id"), reg)),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"mes_implantations": [{"id": i["_id"], "label": i.get("label", ""),
							   "palier": (colonisation.palier_def(reg, i.get("palier")) or {}).get("label", "")}
							  for i in (get_doc(x) for x in colonisation.implantations_de(character)) if i],
	}


@colonisation_router.get("/colonisation/site")
async def site(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Fiche de site de la case où l'on se tient (carte d'un pays) et conditions de la charte."""
	character = _personnage(current_user)
	pays_doc = get_doc(character.get("lieu", "")) or {}
	if pays_doc.get("categorie") != colonisation.CATEGORIE_PAYS:
		raise HTTPException(status_code=403, detail="Une implantation se fonde sur la carte d'un pays.")
	return _payload_site(character, pays_doc, colonisation.regles(get_doc))


@colonisation_router.post("/colonisation/fonder")
async def fonder(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Fonde une implantation sur CETTE case : la charte est remise, lieu et connexion créés."""
	character = _personnage(current_user)
	pays_doc = get_doc(character.get("lieu", "")) or {}
	reg = colonisation.regles(get_doc)
	position = character.get("position") or {}
	lu = lire_site(pays_doc, position, reg)
	ok, raison = colonisation.peut_fonder(character, pays_doc, position, lu["relies"],
										  _implantations_du_pays(pays_doc.get("_id")), reg)
	if not ok:
		raise HTTPException(status_code=403, detail=raison)
	premier = colonisation.paliers(reg)[0]
	proposes = {v["id"] for v in _vignettes(colonisation.modeles_proposes(
		tous_les_modeles(), premier.get("id"), lu["tags"], pays_doc.get("_id"), reg))}
	if body.get("modele") not in proposes:
		raise HTTPException(status_code=409, detail="Ce modèle n'est pas proposé pour ce site.")
	modele = get_doc(body["modele"])
	especes = colonisation.especes_du_site(peupler_lieu(pays_doc, get_doc), position)
	imp = colonisation.creer_implantation(
		character, pays_doc, position, modele, reg, nom=body.get("nom"),
		espece=colonisation.random.choice(especes) if especes else None)
	lien = colonisation.creer_lien(imp, colonisation.entrees_de(modele)[0])
	colonisation.consommer_charte(character)
	colonisation.inscrire(character, imp)
	_sauver(imp, lien, character)
	payload = _payload_site(character, pays_doc, reg)
	payload["fondee"] = {"id": imp["_id"], "label": imp["label"]}
	payload["links"] = get_lieu_links(current_user)     # la connexion vient de naître sur cette case
	return payload


# ── La charte, au bureau d'un maître de guilde (§ 2) ─────────────────────────────────

def _bureau(character: dict) -> tuple[dict, dict]:
	bureau = get_doc(character.get("lieu", "")) or {}
	if not colonisation.est_bureau_de_guilde(bureau):
		raise HTTPException(status_code=403, detail="La charte s'achète au bureau d'un maître de guilde.")
	return bureau, get_doc(bureau.get("lieu_parent") or "") or {}


def _payload_charte(character: dict, bureau: dict, cite: dict, reg: dict, extra=None) -> dict:
	ok, raison = colonisation.peut_acheter_charte(character, bureau, reg)
	payload = {"prix": int((reg.get("reglages") or {}).get("charte_cuivre") or 0),
			   "cite": cite.get("label", ""), "maitre": ((bureau.get("pnj") or [{}])[0]).get("nom", ""),
			   "peut_acheter": ok, "refus": raison, "charte": colonisation.charte_de(character),
			   "reglages": {k: (reg.get("reglages") or {}).get(k) for k in
							("rang_min", "distance_cite_min", "distance_implantation_min", "implantations_par_pays")},
			   "purse": cuivre_to_purse(money_to_cuivre(character))}
	if extra:
		payload.update(extra)
	return payload


@colonisation_router.get("/colonisation/charte")
async def charte(current_user: Annotated[dict, Depends(get_current_user)]):
	character = _personnage(current_user)
	bureau, cite = _bureau(character)
	return _payload_charte(character, bureau, cite, colonisation.regles(get_doc))


@colonisation_router.post("/colonisation/charte/acheter")
async def charte_acheter(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Le maître de guilde signe la charte de SA cité : elle ne vaudra que sur une case dont
	cette cité est la plus proche."""
	character = _personnage(current_user)
	bureau, cite = _bureau(character)
	reg = colonisation.regles(get_doc)
	ok, raison = colonisation.peut_acheter_charte(character, bureau, reg)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	prix = int((reg.get("reglages") or {}).get("charte_cuivre") or 0)
	if debit_character(character, prix) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer la charte.")
	colonisation.delivrer_charte(character, cite, prix)
	_sauver(character)
	return _payload_charte(character, bureau, cite, reg, {"achetee": True})


# ── Dans l'implantation ──────────────────────────────────────────────────────────────

@colonisation_router.get("/colonisation/ici")
async def ici(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, role = _ici(current_user)
	site_ = site_de(imp, reg)
	employes = colonisation.employes_effectifs(imp, get_doc)
	evenements = rattraper_ici(character, imp, reg, role, site_, employes)
	return _payload(character, imp, reg, role, site_, employes, {"evenements": evenements})


@colonisation_router.post("/colonisation/donner")
async def donner(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Don LIBRE d'un objet du sac à l'un des quatre stocks (tout visiteur, § 10) ; c'est
	aussi l'approvisionnement de l'associé et le dépôt du fondateur."""
	character, imp, reg, role = _ici(current_user)
	# L'objet peut venir de TOUT le groupe : un compagnon, une monture, un contenant (sac
	# virtuel) — `sac` = son `_id` dans `_sacs_dons`, le principal à défaut.
	vise = body.get("sac") or character.get("_id")
	sacs = _sacs_dons(character)
	sac = next((s for s in sacs if s.get("_id") == vise), None)
	if sac is None:
		raise HTTPException(status_code=404, detail="Ce sac n'est pas celui de votre groupe.")
	refs = sac.setdefault("inventaire", [])
	pos = proprietes.localiser(refs, body.get("index"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Objet absent de l'inventaire.")
	item = resolve_item_ref(refs[pos]) or {}
	regle = colonisation.stock_de_item(item, filtres_boutique.filtres_item(item), reg)
	if not regle:
		raise HTTPException(status_code=409, detail="Le lieu n'a pas l'usage de cet objet.")
	stock = regle["stock"]
	if float((imp.get("stocks") or {}).get(stock) or 0) >= colonisation.stockage(imp, reg):
		raise HTTPException(status_code=409, detail="Cette réserve est pleine.")
	# `tout` : chaque exemplaire du même objet dans CE sac, du dernier au premier (les positions
	# restent valables), tant que la réserve a de la place.
	iid = item_ref_id(refs[pos])
	positions = [i for i in range(len(refs) - 1, -1, -1) if item_ref_id(refs[i]) == iid] if body.get("tout") else [pos]
	entre, nombre = 0.0, 0
	for i in positions:
		if float(imp["stocks"].get(stock) or 0) >= colonisation.stockage(imp, reg):
			break
		entre += colonisation.deposer(imp, reg, character, stock,
									  colonisation.unites_de_item(resolve_item_ref(refs[i]) or item, regle),
									  item.get("nom", ""))
		refs.pop(i)
		nombre += 1
	entre = round(entre, 1)
	contenants.reporter([sac])                          # sac virtuel → référence du contenant
	porteur = contenants.porteurs_reels([sac])[0]
	_sauver(imp, porteur)
	role = colonisation.role_de(character, imp)        # un premier don fait un soutien
	extra = {"don": {"stock": stock, "unites": entre, "nom": item.get("nom", ""), "nombre": nombre},
			 "inventaire_payload": _inventory_payload(character)}
	if porteur is not character:
		# Sac d'un compagnon / d'une monture allégé : son payload voyage à part (Convention §10),
		# jamais à la place de celui du principal — sac du porteur, sol du joueur.
		extra["compagnon_id"] = porteur.get("_id")
		extra["compagnon"] = _inventory_payload(porteur, character)
	return _payload(character, imp, reg, role, extra=extra)


@colonisation_router.post("/colonisation/feu")
async def feu(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	if colonisation.regler_feu(imp, reg, body.get("reglage")):
		_sauver(imp)
	return _payload(character, imp, reg, role)


@colonisation_router.post("/colonisation/consigne")
async def consigne(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Le fondateur règle l'achat automatique d'une réserve par l'intendant : interrupteur et
	plafond de dépense par jour, sur la caisse du lieu."""
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	ok, motif = colonisation.regler_consigne(imp, reg, body.get("stock"), body.get("acheter"), body.get("plafond_jour"))
	if not ok:
		raise HTTPException(status_code=400, detail=motif)
	_sauver(imp)
	return _payload(character, imp, reg, role)


@colonisation_router.post("/colonisation/icone")
async def icone(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Le fondateur choisit l'icône de l'implantation sur la carte du pays, ou n'en met aucune
	(`fichier` vide) tant qu'elle n'est pas imposée."""
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	ok, raison = colonisation.choisir_icone(imp, reg, fichiers_towns(), body.get("fichier"), regions_du_monde())
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(imp)
	return _payload(character, imp, reg, role)


@colonisation_router.post("/colonisation/construire")
async def construire(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Déclenche un bâtiment (fondateur seul, § 12.8) : stocks et argent payés, le bâtiment
	attend d'être posé."""
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	bdef = colonisation.batiment_def(reg, body.get("type")) or {}
	choix = bool(bdef.get("familles") or bdef.get("toutes_categories"))
	categorie = body.get("categorie") if choix else None
	if choix and not categorie:
		raise HTTPException(status_code=409, detail="Choisissez le métier de la boutique.")
	ok, raison = colonisation.peut_construire(imp, reg, body.get("type"), categorie, categories_disponibles())
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if bdef.get("nature") == colonisation.SOUS_LIEU and not image_sous_lieu(bdef.get("categorie") or categorie):
		raise HTTPException(status_code=409, detail="Aucune image d'intérieur pour ce métier.")
	prix = colonisation.prix_batiment(bdef, categorie)
	if debit_character(character, prix) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer ce bâtiment.")
	b = colonisation.construire(imp, reg, body["type"], categorie=categorie)
	_sauver(imp, character)
	return _payload(character, imp, reg, role, extra={"construit": b["id"]})


@colonisation_router.post("/colonisation/poser")
async def poser(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""« Poser ici » (§ 12.4) : le bâtiment se pose — ou se déplace — sous les pieds du
	personnage. Fondateur, ou associé une fois l'aménagement déclenché."""
	character, imp, reg, role = _ici(current_user)
	if not colonisation.peut_agir_sur_carte(role):
		raise HTTPException(status_code=403, detail="Il faut être fondateur ou associé.")
	ok, raison = colonisation.peut_poser(imp, body.get("batiment"), character.get("position") or {})
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	colonisation.poser(imp, body["batiment"], character["position"])
	b = colonisation.batiment(imp, body["batiment"])
	bdef = colonisation.batiment_def(reg, b.get("type")) or {}
	annexes = []
	if bdef.get("nature") == colonisation.SOUS_LIEU:
		if not b.get("lieu"):
			# Première pose : le sous-lieu naît, avec sa porte sur cette case (vue de tous).
			lieu, lien = colonisation.creer_sous_lieu(imp, b, reg, image_sous_lieu(b.get("categorie"), bdef.get("image_prefixe")))
			if bdef.get("comme_en_ville"):
				# Comme en ville : le marchand générique du métier tient la boutique, tout de suite.
				lieu["pnj"] = colonisation.pnj_comme_en_ville(lieu, get_doc(f"pnj:marchand_{lieu['categorie']}"), reg)
			else:
				employes = colonisation.employes_effectifs(imp, get_doc)
				lieu["pnj"] = colonisation.pnj_du_sous_lieu(lieu, colonisation.tenancier(imp, reg, employes, b["id"]), reg)
			annexes = [lieu, lien]
		else:
			lien = get_doc(b.get("lien") or "")
			if lien and colonisation.deplacer_sous_lieu(lien, imp["_id"], b["pos"]):
				annexes = [lien]
	_sauver(*annexes, imp)
	return _payload(character, imp, reg, role, extra={"pose": body["batiment"], "links": get_lieu_links(current_user)})


@colonisation_router.post("/colonisation/reparer")
async def reparer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	ok, raison = colonisation.reparer(imp, reg, body.get("batiment"))
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(imp)
	return _payload(character, imp, reg, role)


# ── Chantiers et palier (§ 4, § 12.5) ────────────────────────────────────────────────

@colonisation_router.post("/colonisation/chantier/ouvrir")
async def chantier_ouvrir(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	employes = colonisation.employes_effectifs(imp, get_doc)
	if body.get("genre") == colonisation.CHANTIER_GUILDE:
		ok, raison, chantier = colonisation.peut_ouvrir_echelon(imp, reg)
		if chantier and not colonisation.guilde_de(imp):
			chantier["nom"] = colonisation.nettoyer_nom(body.get("nom"))      # nom de la guilde, au premier échelon
	else:
		ok, raison, chantier = colonisation.peut_ouvrir_chantier(imp, reg, employes, body.get("genre"), body.get("objet"))
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	colonisation.ouvrir_chantier(imp, reg, chantier)
	_sauver(imp)
	return _payload(character, imp, reg, role, employes=employes)


@colonisation_router.post("/colonisation/chantier/financer")
async def chantier_financer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Verse au chantier ouvert (fondateur ou associé, § 10). Une fortification entièrement
	financée est aussitôt en place ; un statut attend le choix du modèle (`/palier`)."""
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR, colonisation.ASSOCIE)
	if not imp.get("chantier"):
		raise HTTPException(status_code=409, detail="Aucun chantier n'est ouvert.")
	try:
		montant = int(body.get("montant") or 0)
	except (TypeError, ValueError):
		montant = 0
	montant = max(0, min(montant, money_to_cuivre(character), colonisation.reste_chantier(imp)))
	if montant <= 0:
		raise HTTPException(status_code=409, detail="Rien à verser.")
	if debit_character(character, montant) is None:
		raise HTTPException(status_code=409, detail="Fonds insuffisants.")
	colonisation.financer(imp, character, montant)
	nom_guilde = (imp.get("chantier") or {}).get("nom")
	acheve = colonisation.achever_fortification(imp) or colonisation.achever_guilde(imp, reg, nom_guilde)
	_sauver(imp, character)
	return _payload(character, imp, reg, role, extra={"verse": montant, "acheve": acheve})


@colonisation_router.post("/colonisation/palier")
async def palier(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Le chantier de statut est payé : le fondateur choisit le modèle du nouveau palier.
	Nouvelle image, nouvelle grille, bâtiments replacés ; on se retrouve à la première entrée."""
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	chantier = imp.get("chantier") or {}
	if chantier.get("genre") != colonisation.CHANTIER_STATUT or not colonisation.chantier_pret(imp):
		raise HTTPException(status_code=409, detail="Le chantier de statut n'est pas achevé.")
	actuel = get_doc(imp.get("modele") or "") or {}
	proposes = {v["id"] for v in _vignettes(colonisation.modeles_proposes(
		tous_les_modeles(), chantier["objet"], actuel.get("tags") or [], (imp.get("origine") or {}).get("lieu"), reg))}
	if body.get("modele") not in proposes:
		raise HTTPException(status_code=409, detail="Ce modèle n'est pas proposé pour ce palier.")
	modele = get_doc(body["modele"])
	colonisation.changer_palier(imp, reg, modele, imp.get("dimensions") or actuel.get("dimensions") or {})
	# La grille du NOUVEAU modèle sur l'exemplaire (lien pur) : sortie, bâtiments et portes la suivent.
	suivre_modele(imp, {modele["_id"]: modele}.get)
	entree = colonisation.entrees_de(modele)[0]
	lien, portes = _lien_et_portes(imp)
	_imp_change, _lien_change, portes = colonisation.suivre_entrees(imp, reg, lien, portes)
	character["position"] = {"x": entree[0], "y": entree[1]}
	_sauver(*portes, imp, *([lien] if lien else []), character)
	# La carte a changé sous les pieds du joueur : le client recharge la page.
	return {"palier": (colonisation.palier_def(reg, imp["palier"]) or {}).get("label", ""), "recharger": True}


# ── Personnel nommé (§ 8) ────────────────────────────────────────────────────────────

def _payload_embauche(character: dict, imp: dict, reg: dict, employes: list, extra=None) -> dict:
	cat = proprietes.catalogue(get_doc)

	def carte(c):
		route, _ = escorte.image_protege(c.get("portrait", ""))
		b = colonisation.batiment(imp, c.get("amenagement")) or {}
		return {
			"id": c["id"], "prenom": c.get("prenom", ""), "nom": c.get("nom", ""),
			"race": c.get("race", ""), "sex": c.get("sex", ""),
			"image": c.get("portrait", ""), "image_base": route,
			"metier_label": (colonisation.metier_def(reg, cat, c.get("metier")) or {}).get("label", c.get("metier", "")),
			"poste_nom": (colonisation.batiment_def(reg, b.get("type")) or {}).get("label", ""),
			"cout": int(c.get("cout") or 0),
		}
	payload = {
		"candidats": [carte(c) for c in imp.get("candidats") or []],
		"employes": [{"id": e["_id"], "nom": proprietes.nom_personnage(e),
					  "metier_label": (colonisation.metier_def(reg, cat, e.get("metier")) or {}).get("label", e.get("metier", ""))}
					 for e in employes],
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}
	if extra:
		payload.update(extra)
	return payload


def _rafraichir(imp: dict, reg: dict, employes: list) -> bool:
	return colonisation.rafraichir_candidats(
		imp, reg, proprietes.catalogue(get_doc), employes, get_doc, recrutement.portraits_disponibles(),
		proprietes.portraits_personnel_disponibles())


@colonisation_router.get("/colonisation/embauche")
async def embauche(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	employes = colonisation.employes_effectifs(imp, get_doc)
	if _rafraichir(imp, reg, employes):
		save_doc(imp)
	return _payload_embauche(character, imp, reg, employes)


@colonisation_router.post("/colonisation/engager")
async def engager(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	candidat = proprietes.candidat_par_id(imp, body.get("candidat_id"))
	if candidat is None:
		raise HTTPException(status_code=404, detail="Ce candidat n'est plus disponible.")
	employes = colonisation.employes_effectifs(imp, get_doc)
	ok, raison = colonisation.peut_engager(imp, reg, employes, candidat)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if debit_character(character, int(candidat.get("cout") or 0)) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi engager ce personnel.")
	employe = colonisation.engager(imp, candidat, character)
	employes.append(employe)
	_rafraichir(imp, reg, employes)
	_sauver(employe, *colonisation.synchroniser_tenanciers(imp, reg, employes, get_doc), imp, character)
	return _payload_embauche(character, imp, reg, employes, {"engage": proprietes.nom_personnage(employe)})


@colonisation_router.post("/colonisation/renvoyer")
async def renvoyer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	employe = next((e for e in colonisation.employes_effectifs(imp, get_doc)
					if e.get("_id") == body.get("employe_id")), None)
	if employe is None:
		raise HTTPException(status_code=404, detail="Ce PNJ ne travaille pas ici.")
	colonisation.renvoyer(imp, employe)
	restants = colonisation.employes_effectifs(imp, get_doc)
	restants = [e for e in restants if e.get("_id") != employe.get("_id")]
	_sauver(*colonisation.synchroniser_tenanciers(imp, reg, restants, get_doc), imp)
	save_doc(employe)
	return _payload(character, imp, reg, role)


# ── Combats joués : défense du lieu et tanière (§ 6) ─────────────────────────────────

def _route_image(image: str) -> str | None:
	return next((r for r, chemin in ORIGINES_IMAGE_LIEU if image and os.path.exists(os.path.join(chemin, image))), None)


def _ouvrir_combat(character: dict, imp: dict, reg: dict, genre: str, battle_map: dict, image: str,
				   route: str, gardes: list) -> dict:
	"""Combat de la voie de colonisation : l'espèce de la menace, le groupe du personnage (et,
	en défense, les gardes au poste), `colonie` posé pour `combat._finalize_colonie`."""
	from utils.combat import create_combat_doc, instantiate_monsters, resolve_first_turns, finalize_combat
	existant = [c for c in find_docs({"type": "combat", "user_id": character.get("user_id")}) or []
				if c.get("character_id") == character["_id"] and c.get("status") == "active"]
	if existant:
		return {"combat_id": existant[0]["_id"]}
	espece = get_doc((imp.get("menace") or {}).get("espece") or "")
	if not espece:
		raise HTTPException(status_code=409, detail="Aucune bête ne menace le lieu.")
	monstres = instantiate_monsters([espece], find_docs({"type": "profil"}) or [],
									colonisation.nb_adversaires(imp, reg, genre), [])
	if not monstres:
		raise HTTPException(status_code=409, detail="Aucun adversaire à affronter.")
	pos = character.get("position") or {}
	combat_doc = create_combat_doc(
		character, monstres, ["colonie"], image, battle_map=battle_map,
		compagnons=recrutement.groupe_effectif(character, get_doc),
		montures=montures.montures_effectives(character, get_doc),
		proteges=escorte.proteges_effectifs(character, get_doc),
		point_apparition={"x": pos.get("x", 0), "y": pos.get("y", 0)} if genre == colonisation.DEFENSE else None,
		gardes=gardes)
	combat_doc["colonie"] = {"implantation": imp["_id"], "genre": genre}
	combat_doc["map_route"] = route
	if genre == colonisation.DEFENSE:
		colonisation.placer_assaillants(combat_doc, battle_map)
	resolve_first_turns(combat_doc)
	if combat_doc["status"] != "active":
		finalize_combat(combat_doc)
	if save_doc(combat_doc) is None:
		raise HTTPException(status_code=409, detail=CONFLIT)
	return {"combat_id": combat_doc["_id"]}


@colonisation_router.post("/colonisation/defendre")
async def defendre(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Le lieu est attaqué pendant la visite du fondateur ou d'un associé : un combat joué sur
	la carte du lieu, les assaillants aux entrées, les gardes au poste à ses côtés (§ 6)."""
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR, colonisation.ASSOCIE)
	if not imp.get("attaque_en_cours"):
		raise HTTPException(status_code=409, detail="Le lieu n'est pas attaqué.")
	employes = colonisation.employes_effectifs(imp, get_doc)
	gardes = [colonisation.garde_combattant(e, reg) for e in colonisation.gardes_au_poste(imp, reg, employes)]
	return _ouvrir_combat(character, imp, reg, colonisation.DEFENSE, imp, imp.get("image", ""),
						  _route_image(imp.get("image", "")) or "battle_maps", gardes)


@colonisation_router.post("/colonisation/taniere")
async def taniere(current_user: Annotated[dict, Depends(get_current_user)]):
	"""« Pacifier » : la tanière localisée se vide en combat, sur une carte du terrain du site."""
	from utils.combat import select_battle_map
	character, imp, reg, role = _ici(current_user)
	ok, raison = colonisation.peut_vider_taniere(imp, role)
	if not ok:
		raise HTTPException(status_code=409 if role in (colonisation.FONDATEUR, colonisation.ASSOCIE) else 403,
							detail=raison)
	origine = imp.get("origine") or {}
	pays = get_doc(origine.get("lieu") or "") or {}
	terrain = lire_site(pays, origine.get("pos") or [0, 0], reg)["tags"]
	carte = select_battle_map(terrain, pays)
	if not carte:
		raise HTTPException(status_code=409, detail="Aucune carte de combat pour ce terrain.")
	return _ouvrir_combat(character, imp, reg, colonisation.TANIERE, carte, carte.get("image", ""),
						  "battle_maps", [])


# ── Négoce : caisse, option par PNJ, progression du négociant (§ 8) ─────────────────

@colonisation_router.post("/colonisation/caisse/relever")
async def caisse_relever(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	montant = colonisation.relever_caisse(imp, character)
	if not montant:
		raise HTTPException(status_code=409, detail="La caisse est vide.")
	credit_character(character, montant)
	_sauver(imp, character)
	return _payload(character, imp, reg, role, extra={"releve": montant})


@colonisation_router.post("/colonisation/employe/vente")
async def employe_vente(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Le fondateur décide si la production de CE PNJ se vend ; interdite, elle reste au lieu."""
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	employe = next((e for e in colonisation.employes_effectifs(imp, get_doc)
					if e.get("_id") == body.get("employe_id")), None)
	if employe is None:
		raise HTTPException(status_code=404, detail="Ce PNJ ne travaille pas ici.")
	employe["vente_cite"] = bool(body.get("vente"))
	_sauver(employe)
	return _payload(character, imp, reg, role)


def _seance_negociant(current_user: dict, fn) -> dict:
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	employes = colonisation.employes_effectifs(imp, get_doc)
	negociant = colonisation.negociant_de(imp, reg, employes)
	if not negociant:
		raise HTTPException(status_code=409, detail="Aucun négociant au comptoir.")
	return character, imp, reg, role, employes, negociant


@colonisation_router.post("/colonisation/negociant/former")
async def negociant_former(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Formation payée (mêmes règles que le négociant d'un bien urbain)."""
	character, imp, reg, role, employes, negociant = _seance_negociant(current_user, None)
	regln = echanges_cite.reglages_negociant(proprietes.catalogue(get_doc))
	cout = echanges_cite.cout_formation(negociant, regln)
	if money_to_cuivre(character) < cout:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer la formation.")
	ok, raison, gain = echanges_cite.former(negociant, regln)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	debit_character(character, cout)
	_sauver(negociant, character)
	return _payload(character, imp, reg, role, employes=employes, extra={"formation": gain})


@colonisation_router.post("/colonisation/negociant/livres")
async def negociant_livres(current_user: Annotated[dict, Depends(get_current_user)]):
	"""« Tenir les livres » : séance offerte par un fondateur LETTRÉ."""
	character, imp, reg, role, employes, negociant = _seance_negociant(current_user, None)
	regln = echanges_cite.reglages_negociant(proprietes.catalogue(get_doc))
	ok, raison, gain = echanges_cite.tenir_les_livres(character, negociant, regln)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(negociant)
	return _payload(character, imp, reg, role, employes=employes, extra={"livres": gain})


# ── La guilde du joueur (§ 9) ────────────────────────────────────────────────────────

def _compagnons_envoyables(character: dict) -> list:
	from utils import mercenaires
	return [c for c in recrutement.groupe_effectif(character, get_doc) if not mercenaires.est_clone(c)]


def _vue_guilde(character: dict, imp: dict, reg: dict, employes: list) -> dict:
	vue = colonisation.vue_guilde(character, imp, reg, employes, _compagnons_envoyables(character))
	if vue.get("coffre") is not None:
		vue["sac"] = [{"index": i, "item_id": item_ref_id(r), "nom": (resolve_item_ref(r) or {}).get("nom", ""),
					   "icon": (resolve_item_ref(r) or {}).get("icon", "")}
					  for i, r in enumerate(character.get("inventaire") or [])]
	return vue


def _ici_guilde(current_user: dict) -> tuple[dict, dict, dict, str]:
	"""Dans l'implantation OU dans sa maison de guilde (un sous-lieu de la colonie)."""
	character = _personnage(current_user)
	lieu = get_doc(character.get("lieu", "")) or {}
	if colonisation.est_sous_lieu(lieu):
		imp = get_doc(lieu["colonie"])
		if not imp:
			raise HTTPException(status_code=404, detail="Implantation introuvable.")
		return character, imp, colonisation.regles(get_doc), colonisation.role_de(character, imp)
	return _ici(current_user)


def _payload_guilde(character: dict, imp: dict, reg: dict, extra: dict | None = None) -> dict:
	payload = {"guilde": _vue_guilde(character, imp, reg, colonisation.employes_effectifs(imp, get_doc)),
			   "purse": cuivre_to_purse(money_to_cuivre(character))}
	if extra:
		payload.update(extra)
	return payload


def _guilde_ou_409(imp: dict) -> dict:
	g = colonisation.guilde_de(imp)
	if not g:
		raise HTTPException(status_code=409, detail="Ce lieu n'a pas encore de guilde.")
	return g


@colonisation_router.get("/colonisation/guilde")
async def guilde(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, _role = _ici_guilde(current_user)
	return _payload_guilde(character, imp, reg)


@colonisation_router.post("/colonisation/guilde/rejoindre")
async def guilde_rejoindre(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, _role = _ici_guilde(current_user)
	ok, raison = colonisation.rejoindre(character, imp)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(imp)
	return _payload_guilde(character, imp, reg)


@colonisation_router.post("/colonisation/guilde/quitter")
async def guilde_quitter(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, _role = _ici_guilde(current_user)
	ok, raison = colonisation.quitter_guilde(character, imp)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(imp)
	return _payload_guilde(character, imp, reg)


@colonisation_router.post("/colonisation/guilde/envoyer")
async def guilde_envoyer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Un membre envoie des compagnons de SON groupe en mission (résolue à leur retour)."""
	character, imp, reg, _role = _ici_guilde(current_user)
	_guilde_ou_409(imp)
	par_id = {c["_id"]: c for c in _compagnons_envoyables(character)}
	choisis = [par_id[i] for i in (body.get("compagnons") or []) if i in par_id]
	if len(choisis) != len(body.get("compagnons") or []):
		raise HTTPException(status_code=409, detail="Ce compagnon n'est pas dans votre groupe.")
	mission = colonisation.mission_def(reg, body.get("mission"))
	ok, raison = colonisation.peut_envoyer(character, imp, reg, mission, choisis)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	exp = colonisation.envoyer(character, imp, reg, colonisation.employes_effectifs(imp, get_doc), mission, choisis)
	_sauver(*choisis, imp, character)
	return _payload_guilde(character, imp, reg, {"envoyee": exp["id"]})


@colonisation_router.post("/colonisation/guilde/accueillir")
async def guilde_accueillir(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Le groupe revenu rejoint son membre : récompense moins la commission de la guilde."""
	character, imp, reg, _role = _ici_guilde(current_user)
	g = _guilde_ou_409(imp)
	exp = next((e for e in g.get("expeditions") or [] if e.get("id") == body.get("expedition")), None)
	if not exp:
		raise HTTPException(status_code=404, detail="Cette expédition n'existe plus.")
	compagnons = [c for c in (get_doc(i) for i in exp.get("compagnons") or [])
				  if c and (c.get("en_mission") or {}).get("expedition") == exp["id"]]
	libres = recrutement.taille_max_groupe() - recrutement.places_occupees(character, get_doc)
	ok, raison, issue = colonisation.accueillir(character, imp, reg, colonisation.employes_effectifs(imp, get_doc),
												exp["id"], compagnons, places_libres=libres)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	if issue["gain"]:
		credit_character(character, issue["gain"])
	_sauver(*compagnons, imp, character)
	return _payload_guilde(character, imp, reg, {"issue": issue})


@colonisation_router.post("/colonisation/guilde/coffre/deposer")
async def guilde_coffre_deposer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, _role = _ici_guilde(current_user)
	g = _guilde_ou_409(imp)
	if "coffre" not in colonisation.fonctions(imp, reg) or not colonisation.titre_de(character, imp):
		raise HTTPException(status_code=403, detail="Le matériel commun est aux membres, dès la Demeure des aventuriers.")
	refs = character.get("inventaire") or []
	pos = proprietes.localiser(refs, body.get("index"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Objet absent de l'inventaire.")
	poids = sum(item_ref_weight(r) for r in g.get("coffre") or []) + item_ref_weight(refs[pos])
	if poids > colonisation.coffre_guilde_kg(imp, reg):
		raise HTTPException(status_code=409, detail="Le coffre de la guilde est plein.")
	g.setdefault("coffre", []).append(refs.pop(pos))
	_sauver(imp, character)
	return _payload_guilde(character, imp, reg, {"inventaire_payload": _inventory_payload(character)})


@colonisation_router.post("/colonisation/guilde/coffre/retirer")
async def guilde_coffre_retirer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, _role = _ici_guilde(current_user)
	g = _guilde_ou_409(imp)
	if not colonisation.peut_retirer_coffre_guilde(character, imp):
		raise HTTPException(status_code=403, detail="Seuls le maître et les membres fondateurs en retirent.")
	refs = g.get("coffre") or []
	try:
		pos = int(body.get("index"))
	except (TypeError, ValueError):
		pos = -1
	if not 0 <= pos < len(refs):
		raise HTTPException(status_code=404, detail="Cet objet n'est plus au coffre.")
	if not recrutement.peut_porter(character, refs[pos]):
		raise HTTPException(status_code=409, detail="Vous ne pouvez pas porter davantage.")
	character.setdefault("inventaire", []).append(refs.pop(pos))
	_sauver(imp, character)
	return _payload_guilde(character, imp, reg, {"inventaire_payload": _inventory_payload(character)})


# ── Ce que l'associé y gagne : entrepôt commun, coffre personnel, colons (§ 10) ───────

def _poids(refs: list) -> float:
	return round(sum(item_ref_weight(r) for r in refs or []), 2)


def _rangement(refs: list, kg_max: float, depot: bool, retrait: bool, note: str) -> dict:
	"""Un rangement au format du coffre d'une propriété (colonne de droite du panneau
	partagé) : contenu trié par nom, `idx` = position réelle dans la liste."""
	return {
		"visible": True, "depot": depot and kg_max > 0, "retrait": retrait,
		"charge": _poids(refs), "charge_max": kg_max, "note": note,
		"inventaire": sorted(
			(dict(d, idx=i) for i, r in enumerate(refs or []) if (d := resolve_item_ref(r))),
			key=lambda d: unicodedata.normalize("NFD", str(d.get("nom") or "")).encode("ascii", "ignore").decode().lower()),
	}


def _reserves_acceptees(character: dict, reg: dict) -> dict:
	"""`{item_id: libellé du stock}` pour chaque objet des sacs du groupe (contenants ouverts
	compris) que l'un des quatre stocks accepte — mêmes sacs et même règle que les dons."""
	labels = reg.get("stocks_labels") or {}
	out = {}
	for sac in _sacs_dons(character):
		for ref in sac.get("inventaire") or []:
			iid = item_ref_id(ref)
			if iid in out:
				continue
			item = resolve_item_ref(ref)
			regle = colonisation.stock_de_item(item, filtres_boutique.filtres_item(item), reg) if item else None
			if regle:
				out[iid] = labels.get(regle["stock"], regle["stock"])
	return out


def _payload_rangements(character: dict, imp: dict, reg: dict, extra=None) -> dict:
	"""Même panneau que le coffre d'une propriété (`routers/proprietes._payload_coffre`) : à
	gauche le sac du personnage, d'un porteur ou d'un contenant ; à droite l'entrepôt commun
	puis, pour un associé, son petit coffre."""
	role = colonisation.role_de(character, imp)
	gere = role in (colonisation.FONDATEUR, colonisation.ASSOCIE)
	kg_e = colonisation.entrepot_kg(imp, reg)
	peut = colonisation.peut_retirer_entrepot(character, imp)
	rangements = {"entrepot": dict(_rangement(imp.get("entrepot"), kg_e, gere, peut,
		("" if peut else "Dépôt seulement : le fondateur autorise le retrait.") if kg_e
		else "Il faut un entrepôt debout."), label="📦 Entrepôt commun")}
	if role == colonisation.ASSOCIE:
		kg_c = colonisation.coffre_associe_kg(imp, reg)
		rangements["coffre"] = dict(_rangement((imp.get("coffres") or {}).get(character.get("_id")) or [],
			kg_c, True, True, "" if kg_c else "Il faut une habitation debout."), label="🔒 Votre petit coffre")
	payload = {
		"colonie": True, "role": role,
		"rangements": rangements,
		"associes": ([{"id": a.get("id"), "nom": a.get("nom"), "retrait": bool(a.get("retrait"))}
					  for a in imp.get("associes") or []] if role == colonisation.FONDATEUR else None),
		# Journal des mouvements de l'entrepôt (fondateur) : les lignes `entrepot` du carnet.
		"mouvements": ([j for j in reversed(imp.get("journal") or []) if j.get("genre") == "entrepot"][:30]
					   if role == colonisation.FONDATEUR else None),
		# Objets du groupe que les RÉSERVES acceptent (flèche « verser aux réserves ») : stock par item.
		"reserves": _reserves_acceptees(character, reg),
		"principal": _inventory_payload(character),
		"porteurs": sacs_groupe.porteurs_payload(character, get_doc, resolve_item_ref),
		"sacs_contenants": sacs_groupe.sacs_contenants(character, get_doc, resolve_item_ref, colonisation.now_epoch()),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}
	if extra:
		payload.update(extra)
	return payload


def _refs_cible(character: dict, imp: dict, reg: dict, cible: str) -> tuple[list, float]:
	if cible == "coffre":
		if colonisation.role_de(character, imp) != colonisation.ASSOCIE:
			raise HTTPException(status_code=403, detail="Le petit coffre est celui d'un associé.")
		return imp.setdefault("coffres", {}).setdefault(character["_id"], []), colonisation.coffre_associe_kg(imp, reg)
	if colonisation.role_de(character, imp) not in (colonisation.FONDATEUR, colonisation.ASSOCIE):
		raise HTTPException(status_code=403, detail="L'entrepôt commun est au fondateur et aux associés.")
	return imp.setdefault("entrepot", []), colonisation.entrepot_kg(imp, reg)


def _porteur_rangement(character: dict, body: dict) -> dict:
	"""Le sac de gauche : le personnage, ou un porteur de son groupe (`compagnon_id`) — 403 sinon."""
	p = sacs_groupe.porteur_vise(character, body.get("compagnon_id"), get_doc)
	if p is None:
		raise HTTPException(status_code=403, detail="Ce porteur ne fait pas partie de votre groupe.")
	return p


@colonisation_router.get("/colonisation/rangements")
async def rangements(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, _role = _ici(current_user)
	return _payload_rangements(character, imp, reg)


@colonisation_router.post("/colonisation/rangements/deposer")
async def rangements_deposer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Sac → rangement. Le sac est celui du personnage, d'un porteur (`compagnon_id`) ou un
	CONTENANT de ce sac (`index_contenant`/`item_id_contenant`, marée haute) ; le RÔLE reste
	celui du personnage."""
	character, imp, reg, _role = _ici(current_user)
	refs, kg_max = _refs_cible(character, imp, reg, body.get("cible"))
	porteur = _porteur_rangement(character, body)
	sac, ref_c, refus = contenants.sac_vise(porteur, body.get("index_contenant"),
											body.get("item_id_contenant"), get_doc, colonisation.now_epoch())
	if refus:
		raise HTTPException(status_code=refus[0], detail=refus[1])
	pos = proprietes.localiser(sac, body.get("index"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Objet absent de l'inventaire.")
	if _poids(refs) + item_ref_weight(sac[pos]) > kg_max:
		raise HTTPException(status_code=409, detail="Il n'y a plus de place.")
	if body.get("cible") != "coffre":
		colonisation.noter(imp, f"{proprietes.nom_personnage(character)} dépose "
						   f"{(resolve_item_ref(sac[pos]) or {}).get('nom', '')} à l'entrepôt.", genre="entrepot")
	refs.append(sac.pop(pos))
	contenants.nettoyer(ref_c)
	_sauver(imp, porteur)
	return _payload_rangements(character, imp, reg)


@colonisation_router.post("/colonisation/rangements/retirer")
async def rangements_retirer(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""Rangement → sac du personnage, d'un porteur (`compagnon_id`) ou CONTENANT de ce sac
	(`index_contenant`/`item_id_contenant` : borné par sa capacité, jamais un contenant dedans)."""
	character, imp, reg, _role = _ici(current_user)
	refs, _kg = _refs_cible(character, imp, reg, body.get("cible"))
	if body.get("cible") != "coffre" and not colonisation.peut_retirer_entrepot(character, imp):
		raise HTTPException(status_code=403, detail="Le fondateur ne vous a pas autorisé à retirer.")
	pos = proprietes.localiser(refs, body.get("index"), body.get("item_id"))
	if pos is None:
		raise HTTPException(status_code=404, detail="Cet objet n'y est plus.")
	porteur = _porteur_rangement(character, body)
	nom_objet = (resolve_item_ref(refs[pos]) or {}).get("nom", "")
	pos_c, doc_c, introuvable = sacs_groupe.contenant_vise(porteur, body, get_doc)
	if introuvable:
		raise HTTPException(status_code=404, detail="Contenant introuvable dans ce sac.")
	if pos_c is not None:
		ok, raison = contenants.peut_ranger(porteur["inventaire"][pos_c], doc_c, refs[pos],
											resolve_item_ref(refs[pos]) or {})
		if not ok:
			raise HTTPException(status_code=409, detail=raison)
		contenants.deposer(porteur, pos_c, item_ref_id(porteur["inventaire"][pos_c]), refs.pop(pos), get_doc,
						   controler=False)
	else:
		if not recrutement.peut_porter(porteur, refs[pos]):
			raise HTTPException(status_code=409, detail="Vous ne pouvez pas porter davantage."
								if porteur is character else "Ce porteur ne peut pas porter davantage.")
		porteur.setdefault("inventaire", []).append(refs.pop(pos))
	if body.get("cible") != "coffre":
		colonisation.noter(imp, f"{proprietes.nom_personnage(character)} prend {nom_objet} à l'entrepôt.", genre="entrepot")
	_sauver(imp, porteur)
	return _payload_rangements(character, imp, reg)


@colonisation_router.post("/colonisation/rangements/autoriser")
async def rangements_autoriser(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	if not colonisation.autoriser_retrait(imp, body.get("id"), bool(body.get("retrait"))):
		raise HTTPException(status_code=404, detail="Cet associé n'est plus là.")
	_sauver(imp)
	return _payload_rangements(character, imp, reg)


def _implantations_gerees(character: dict) -> list:
	ids = list(colonisation.implantations_de(character)) + ([character["association"]] if character.get("association") else [])
	return [i for i in (get_doc(x) for x in ids) if i and colonisation.role_de(character, i) in
			(colonisation.FONDATEUR, colonisation.ASSOCIE)]


def _payload_colons(character: dict, cite: dict, reg: dict, extra=None) -> dict:
	offres = []
	for imp in _implantations_gerees(character):
		pays = (imp.get("origine") or {}).get("lieu")
		relies = colonisation.lieux_relies(connexions_du_lieu(pays), pays, get_doc) if pays else []
		ok, raison, n = colonisation.peut_recruter_colons(character, imp, cite.get("_id"), relies, reg,
														   colonisation.employes_effectifs(imp, get_doc))
		offres.append({"id": imp["_id"], "label": imp.get("label", ""), "nombre": n, "refus": raison})
	payload = {"cite": cite.get("label", ""), "offres": offres, "convoi": character.get("colons")}
	if extra:
		payload.update(extra)
	return payload


def _taverne_de_cite(character: dict) -> dict:
	from utils import auberge as auberge_util
	from utils import marche as marche_util
	lieu = get_doc(character.get("lieu", "")) or {}
	cite = get_doc(lieu.get("lieu_parent") or "") or {}
	if not auberge_util.lieu_est_taverne(lieu) or not marche_util.est_cite(cite) or colonisation.est_implantation(cite):
		raise HTTPException(status_code=403, detail="Les colons se trouvent à l'auberge d'une cité.")
	return cite


@colonisation_router.get("/colonisation/colons")
async def colons(current_user: Annotated[dict, Depends(get_current_user)]):
	character = _personnage(current_user)
	return _payload_colons(character, _taverne_de_cite(character), colonisation.regles(get_doc))


@colonisation_router.post("/colonisation/colons/recruter")
async def colons_recruter(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	"""« Amener des colons » : à l'auberge d'une cité proche, des habitants prêts à partir ;
	ils s'installent quand on arrive au lieu, se dispersent sur une défaite ou au bout du délai."""
	character = _personnage(current_user)
	cite = _taverne_de_cite(character)
	reg = colonisation.regles(get_doc)
	imp = next((i for i in _implantations_gerees(character) if i["_id"] == body.get("implantation")), None)
	if not imp:
		raise HTTPException(status_code=403, detail="Il faut être fondateur ou associé du lieu.")
	pays = (imp.get("origine") or {}).get("lieu")
	relies = colonisation.lieux_relies(connexions_du_lieu(pays), pays, get_doc) if pays else []
	ok, raison, n = colonisation.peut_recruter_colons(character, imp, cite.get("_id"), relies, reg,
													   colonisation.employes_effectifs(imp, get_doc))
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	convoi = colonisation.recruter_colons(character, imp, cite, n, reg)
	_sauver(character)
	return _payload_colons(character, cite, reg, {"recrutes": convoi["nombre"]})


# ── Association (§ 10) ───────────────────────────────────────────────────────────────

@colonisation_router.post("/colonisation/association/demander")
async def association_demander(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	ok, raison = colonisation.peut_demander(character, imp, reg)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	colonisation.demander(character, imp, body.get("texte"))
	_sauver(imp, character)
	return _payload(character, imp, reg, role)


@colonisation_router.post("/colonisation/association/repondre")
async def association_repondre(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	ok, raison, _ = colonisation.repondre(imp, reg, body.get("id"), bool(body.get("accepter")))
	if not ok:
		raise HTTPException(status_code=409, detail=raison)
	_sauver(imp)
	return _payload(character, imp, reg, role)


@colonisation_router.post("/colonisation/association/exclure")
async def association_exclure(current_user: Annotated[dict, Depends(get_current_user)], body: dict = Body(...)):
	character, imp, reg, role = _ici(current_user)
	_exiger(role, colonisation.FONDATEUR)
	if not colonisation.retirer_associe(imp, body.get("id"), exclu=True):
		raise HTTPException(status_code=404, detail="Cet associé n'est plus là.")
	_sauver(imp)
	return _payload(character, imp, reg, role)


@colonisation_router.post("/colonisation/association/quitter")
async def association_quitter(current_user: Annotated[dict, Depends(get_current_user)]):
	character, imp, reg, role = _ici(current_user)
	if not colonisation.retirer_associe(imp, character.get("_id"), exclu=False):
		raise HTTPException(status_code=409, detail="Vous n'êtes pas associé à ce lieu.")
	character.pop("association", None)
	_sauver(imp, character)
	return _payload(character, imp, reg, colonisation.role_de(character, imp))

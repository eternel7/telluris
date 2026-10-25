# utils/offres.py
# PLUSIEURS offres écrites par service : `services.transport` / `services.escorte` /
# `services.apport` acceptent `offres: [{offre: {...}, noeuds: {...}}, ...]` à côté de la
# forme d'avant (`offre` + `noeuds`), relue telle quelle (aucune migration). C'est ainsi que
# Maëlys propose plusieurs épreuves pour une même montée de rang.
#
# Tout le moteur en aval (`*.offre_spec`, flags, `_resoudre_*`, linter) ne connaît qu'UNE
# offre par service : `vue_pnj` rend une COPIE du doc PNJ où chaque service listé est réduit
# au bloc RETENU — rien d'autre n'a à changer. Choix du bloc, dans cet ordre :
#   1. l'entrée dont la quête est ACTIVE (en cours, à livrer, à rapporter) ;
#   2. sinon l'entrée TIRÉE à l'entrée du lieu (`poser_offres_tirees`, champ transitoire
#      `character["offres_tirees"] = {lieu, tirages: {pnj_id: {service: quete_id}}}` — même
#      sémantique que `pnj_present` : un refresh ne re-tire pas, ressortir/rentrer re-tire),
#      si elle est toujours ÉLIGIBLE ;
#   3. sinon aucune offre.
#
# Éligible = pas une offre `unique` déjà réussie ; une offre qui récompense un RANG de guilde
# n'est ouverte qu'au cran JUSTE EN DESSOUS dans la cité (le cran se lit dans la récompense,
# aucun champ neuf — même règle que l'épreuve d'apport de rang) ; et une seule épreuve de rang
# à la fois chez ce donneur (miroir de `chasse._rang_deja_actif`).
#
# ⚠️ La récompense `rang_guilde: "B"` (chaîne) est RÉSOLUE ici en `{cite, rang}` : l'apport
# recopie ses récompenses telles quelles, et `chasse.crediter_rang` refuse une chaîne en
# silence (fail-closed).
#
# La condition de dialogue `offre: "quete:x"` (utils/pnj.py) lit `_offres_retenues`, posé
# sur la vue : c'est elle qui départage deux choix d'accueil conditionnés sur le même flag.
#
# Logique pure, mute sans save — l'appelant persiste.

import copy
import random

from utils import quetes
from utils.recrutement import RANGS

SERVICES_LISTABLES = ("transport", "escorte", "apport")

# Clé posée sur la VUE (jamais en base) : ids des offres retenues, lue par `pnj.condition_ok`.
CLE_RETENUES = "_offres_retenues"


def entrees(pnj_doc: dict, service: str) -> list:
	"""Les entrées `{offre, noeuds}` de `services.<service>.offres` dont l'offre porte un id
	`quete:` — une entrée sans id ne peut être ni retenue, ni tirée, ni testée."""
	conf = (((pnj_doc or {}).get("services") or {}).get(service) or {})
	out = []
	for e in conf.get("offres") or []:
		offre = (e or {}).get("offre") if isinstance(e, dict) else None
		qid = (offre or {}).get("id")
		if isinstance(qid, str) and qid.startswith("quete:"):
			out.append(e)
	return out


def cite_du_donneur(lieu_doc: dict | None) -> str | None:
	"""Cité dont relève le rang d'une épreuve : le `lieu_parent` du lieu du donneur, sinon le
	lieu lui-même (même résolution que `transport.rang_guilde_recompense`)."""
	return (lieu_doc or {}).get("lieu_parent") or (lieu_doc or {}).get("_id")


def rang_vise(offre: dict, lieu_doc: dict | None) -> dict | None:
	"""`{cite, rang}` de la récompense de rang de l'offre, ou None. Rang hors échelle ⇒ None."""
	spec = ((offre or {}).get("recompenses") or {}).get("rang_guilde")
	if not spec:
		return None
	if isinstance(spec, dict):
		cite, rang = spec.get("cite"), spec.get("rang")
	else:
		cite, rang = cite_du_donneur(lieu_doc), spec
	if not cite or rang not in RANGS:
		return None
	return {"cite": cite, "rang": rang}


def _au_cran_du_dessous(character: dict, vise: dict) -> bool:
	courant = ((character or {}).get("rangs_guilde") or {}).get(vise["cite"], RANGS[0])
	if courant not in RANGS:
		return False
	return RANGS.index(courant) == RANGS.index(vise["rang"]) - 1


def _ids_de_rang(pnj_doc: dict, lieu_doc: dict | None) -> set:
	return {
		e["offre"]["id"]
		for service in SERVICES_LISTABLES for e in entrees(pnj_doc, service)
		if rang_vise(e["offre"], lieu_doc)
	}


def epreuve_active(character: dict, pnj_doc: dict, lieu_doc: dict | None) -> str | None:
	"""Id de l'épreuve de rang de CE donneur que le personnage mène déjà, sinon None."""
	actives = quetes.quetes_actives_ids(character)
	return next(iter(sorted(_ids_de_rang(pnj_doc, lieu_doc) & actives)), None)


def eligible(character: dict, offre: dict, pnj_doc: dict, lieu_doc: dict | None) -> bool:
	"""Cette offre peut-elle être PROPOSÉE (pas déjà en cours) maintenant ?"""
	qid = (offre or {}).get("id")
	if not qid or quetes.quete_active(character, qid):
		return False
	if offre.get("unique", True) is not False and quetes.quete_reussie(character, qid):
		return False
	vise = rang_vise(offre, lieu_doc)
	if vise:
		if not _au_cran_du_dessous(character, vise):
			return False
		if epreuve_active(character, pnj_doc, lieu_doc):
			return False
	return True


def tirer(character: dict, pnj_doc: dict, lieu_doc: dict | None,
		  rand_fn=random.random) -> dict:
	"""`{service: quete_id}` tiré parmi les entrées éligibles de chaque service listé.
	Un service sans entrée éligible est absent. `rand_fn` injecté (tests sans hasard)."""
	out = {}
	for service in SERVICES_LISTABLES:
		elig = [e["offre"]["id"] for e in entrees(pnj_doc, service)
				if eligible(character, e["offre"], pnj_doc, lieu_doc)]
		if elig:
			out[service] = elig[min(len(elig) - 1, int(rand_fn() * len(elig)))]
	return out


def poser_offres_tirees(character: dict, lieu_doc: dict, pnj_docs: list,
						rand_fn=random.random) -> bool:
	"""Tire, à l'ENTRÉE du lieu, l'offre proposée par service pour chaque PNJ présent qui
	porte des `offres`. No-op si le tirage est déjà fait pour ce lieu (refresh stable).
	Renvoie True si le champ a changé (l'appelant sauvegarde)."""
	lieu_id = (lieu_doc or {}).get("_id")
	deja = character.get("offres_tirees")
	if not lieu_id:
		return False
	if isinstance(deja, dict) and deja.get("lieu") == lieu_id:
		return False
	tirages = {}
	for doc in pnj_docs or []:
		pid = (doc or {}).get("_id")
		if pid and any(entrees(doc, s) for s in SERVICES_LISTABLES):
			tirages[pid] = tirer(character, doc, lieu_doc, rand_fn)
	if not tirages and deja is None:
		return False
	character["offres_tirees"] = {"lieu": lieu_id, "tirages": tirages}
	return True


def _tire(character: dict, pnj_id: str, lieu_id: str | None, service: str) -> str | None:
	t = character.get("offres_tirees") or {}
	if not lieu_id or t.get("lieu") != lieu_id:
		return None
	return ((t.get("tirages") or {}).get(pnj_id) or {}).get(service)


def entree_retenue(character: dict, pnj_doc: dict, lieu_doc: dict | None,
				   service: str) -> dict | None:
	"""Le bloc `{offre, noeuds}` que ce PNJ tient MAINTENANT pour ce service, ou None."""
	liste = entrees(pnj_doc, service)
	if not liste:
		return None
	actives = quetes.quetes_actives_ids(character)
	for e in liste:
		if e["offre"]["id"] in actives:
			return e
	tire = _tire(character, (pnj_doc or {}).get("_id"), (lieu_doc or {}).get("_id"), service)
	for e in liste:
		if e["offre"]["id"] == tire and eligible(character, e["offre"], pnj_doc, lieu_doc):
			return e
	return None


def _offre_resolue(offre: dict, lieu_doc: dict | None) -> dict:
	"""Copie de l'offre dont la récompense de rang est résolue en `{cite, rang}`."""
	out = copy.deepcopy(offre)
	vise = rang_vise(out, lieu_doc)
	if vise:
		out.setdefault("recompenses", {})["rang_guilde"] = vise
	return out


def vue_pnj(pnj_doc: dict | None, character: dict, lieu_doc: dict | None) -> dict | None:
	"""Le doc PNJ tel que le voit CE personnage ici : chaque service à `offres` réduit au bloc
	retenu (`offre` + `noeuds`, sans `offres`), et `_offres_retenues` = ids des offres tenues
	(listées ou écrites à l'ancienne). Doc sans `offres` ⇒ copie identique (plus la clé)."""
	if not pnj_doc:
		return pnj_doc
	vue = dict(pnj_doc)
	services = dict(vue.get("services") or {})
	retenues = []
	for service in SERVICES_LISTABLES:
		conf = services.get(service)
		if not isinstance(conf, dict):
			continue
		if "offres" in conf:
			conf = {k: v for k, v in conf.items() if k not in ("offres", "offre", "noeuds")}
			e = entree_retenue(character, pnj_doc, lieu_doc, service)
			if e:
				conf["offre"] = _offre_resolue(e["offre"], lieu_doc)
				conf["noeuds"] = dict(e.get("noeuds") or {})
			services[service] = conf
		qid = ((conf or {}).get("offre") or {}).get("id")
		if isinstance(qid, str):
			retenues.append(qid)
	if services:
		vue["services"] = services
	vue[CLE_RETENUES] = retenues
	return vue

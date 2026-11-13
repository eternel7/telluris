# utils/secours.py
# Quêtes de SECOURS : le comptoir de la guilde confie le sauvetage de 2 à 3 aventuriers en
# péril, quelque part autour de la cité — une forêt dangereuse à un saut de ses portes, ou une
# salle (un étage) d'un donjon proche, comme les catacombes de Lutécia. On les retrouve
# blessés, ils se défendent, et il faut les ramener VIVANTS au comptoir dans le délai.
#
# ⚠️ C'est une 4ᵉ SOURCE de la famille escorte, pas un système : on SYNTHÉTISE une spec à la
# forme exacte de `services.escorte.offre` et on la passe à `escorte.generer_escorte_authoree`.
# Acceptation, incarnation, combat, dépose, solde et échec à la première mort ne savent pas
# d'où vient l'offre. Ce que la spec ajoute :
#   · `type_secours: True`     — distingue l'offre au dialogue (flag `secours_offert`) ;
#   · `expire_h`               — délai, posé en `expire_at` à l'acceptation ;
#   · `rencontre.donjon`       — rendez-vous DANS un combat de donjon (`escorte.rencontres_en_combat`),
#                                que le chokepoint de déplacement ignore ;
#   · `proteges[].pv_depart`   — on les retrouve blessés (`escorte.creer_protege`).
#
# Le PÉRIMÈTRE est DÉRIVÉ de la carte (opt-out, aucune donnée à écrire par lieu) :
#   · la cité et les lieux à UN saut de connexion, pour chaque zone placée à `danger > 0` —
#     filtre STRICT, sans le repli « toutes les zones » de `escorte.zones_dangereuses` : un
#     cœur de ville n'est pas un lieu de péril ;
#   · les salles des `donjon:*` joints à ce voisinage — un étage dont la connexion part de la
#     cité ou d'un voisin (donjon à étages), ou dont le `portail` (donjon classique) y est ;
#   · moins tout ce qui porte le tag `sans_secours` (lieu, salle ou doc donjon), les salles
#     `proteges_restent_dehors`, les lieux qu'une escorte ÉCRITE vise déjà comme rendez-vous,
#     et ceux qu'une barrière d'accès garde par autre chose qu'un rang (`_porte_ouverte` : la
#     mine sous mandat, la grotte des bûcherons n'accueillent pas d'inconnus). La carte du
#     pays n'est pas un voisin (elle jouxte toutes ses cités).
#
# Logique pure (DB injectée), mute sans sauver — l'appelant persiste. World-vars lues via le
# module (jamais from-import) : réglables à chaud depuis /admin.

import random
import unicodedata

from models import character_stats
from utils import acces, donjon, quetes


TAG_SANS_SECOURS = "sans_secours"

# Carte d'un PAYS (`lieu:france`) : voisine de toutes ses cités par leurs portes, elle ferait de
# tout le pays « les abords » de chacune — et joindrait chaque donjon dont le portail s'y trouve.
# Elle est donc retirée du voisinage (miroir de `colonisation.CATEGORIE_PAYS`).
CATEGORIE_PAYS = "pays"

# Rang de guilde exigé selon le NIVEAU du lieu de péril (`niveau_min` d'une salle de donjon,
# `danger` de la zone d'un lieu explorable). Voulu : même pente que les donjons écrits —
# grades 3-4 des catacombes ⇒ rang D. Surchargeable par `bloc.rangs` ({"3": "D", …}).
RANGS_PAR_NIVEAU = {1: "F", 2: "E", 3: "D", 4: "C", 5: "B", 6: "A"}
NIVEAU_MAX = max(RANGS_PAR_NIVEAU)


# ---------------------------------------------------------------------------
# Le bloc de donnée
# ---------------------------------------------------------------------------

def secours_spec(pnj_doc: dict | None) -> dict | None:
	"""Le bloc `services.escorte.secours` du comptoir, ou None. Frère de `recherche` : un
	bloc VIDE (`{}`) suffit — la cité est alors celle du comptoir."""
	bloc = (((pnj_doc or {}).get("services") or {}).get("escorte") or {}).get("secours")
	return bloc if isinstance(bloc, dict) else None


def est_secours(q: dict | None) -> bool:
	"""Cette offre / quête active est-elle un secours ?"""
	return bool((q or {}).get("type_secours"))


# ---------------------------------------------------------------------------
# Le périmètre
# ---------------------------------------------------------------------------

def _tags(doc: dict | None) -> list:
	return list((doc or {}).get("tags") or [])


def _exclu(doc: dict | None) -> bool:
	return TAG_SANS_SECOURS in _tags(doc)


def _porte_ouverte(doc: dict | None) -> bool:
	"""Le lieu n'est-il gardé, au plus, que par un RANG ? Toute autre condition d'accès
	(mandat, quête active, combat gagné…) est un lieu SCÉNARISÉ — la mine sous commission, la
	grotte des bûcherons : un secours généré y serait injouable, ou piétinerait l'histoire."""
	gate = acces.gate_de(doc)
	if not gate:
		return True
	return all(isinstance(c, dict) and set(c) == {"rang_min"} for c in gate.get("conditions") or [])


def _rang_des_portes(*docs) -> str | None:
	"""Le rang exigé par la plus stricte des barrières `rang_min` de ces lieux, ou None."""
	return acces.rang_le_plus_eleve(*(acces.rang_min_du_lieu(d) for d in docs if d))


def _danger(zone_doc: dict | None) -> float:
	try:
		return float(((zone_doc or {}).get("modificateurs") or {}).get("danger", 0) or 0)
	except (TypeError, ValueError):
		return 0.0


def _borner_niveau(n) -> int:
	try:
		n = int(n)
	except (TypeError, ValueError):
		n = 1
	return max(1, min(NIVEAU_MAX, n))


def voisinage(cite_id: str, connexions_fn) -> list:
	"""La cité puis les lieux à UN saut de connexion, sans doublon, dans l'ordre."""
	ids = [cite_id] if cite_id else []
	for conn in (connexions_fn(cite_id) if cite_id else []) or []:
		for n in conn.get("nodes") or []:
			lid = (n or {}).get("lieu") if isinstance(n, dict) else None
			if lid and lid not in ids:
				ids.append(lid)
	return ids


def _lieux_vises_par_ecrit(find_docs_fn) -> set:
	"""Rendez-vous des escortes ÉCRITES : un secours généré n'y est jamais posé."""
	vises = set()
	for p in find_docs_fn({"type": "pnj"}) or []:
		offre = (((p.get("services") or {}).get("escorte") or {}).get("offre") or {})
		lid = (offre.get("rencontre") or {}).get("lieu")
		if lid:
			vises.add(lid)
	return vises


def _projeter(find_docs_fn, selector: dict, champs: list) -> list:
	try:
		return find_docs_fn(selector, fields=champs) or []
	except TypeError:
		# Finder injecté sans projection (tests purs) : le comportement reste correct.
		return find_docs_fn(selector) or []


def candidats(cite_id: str, get_doc_fn, find_docs_fn, connexions_fn) -> list:
	"""Les lieux de péril possibles autour de `cite_id` :
	`[{"lieu", "zones"?: [zone], "donjon"?: id, "etage"?: n, "niveau": int}]`.

	⚠️ Les docs `lieu` du voisinage (cités : les plus gros du jeu, hors cache de requête) ne
	sont lus qu'une fois chacun ; les salles de donjon par une requête PROJETÉE."""
	if not cite_id:
		return []
	vises = _lieux_vises_par_ecrit(find_docs_fn)
	sortie = []
	voisins, docs_voisins = [], {}
	for lid in voisinage(cite_id, connexions_fn):
		doc = get_doc_fn(lid) or {}
		if lid != cite_id and doc.get("categorie") == CATEGORIE_PAYS:
			continue
		voisins.append(lid)
		docs_voisins[lid] = doc

	# (a) Lieux explorables : une entrée par ZONE dangereuse placée (le niveau suit sa zone).
	zones_cache: dict = {}
	for lid in voisins:
		if lid in vises:
			continue
		doc = docs_voisins[lid]
		if (_exclu(doc) or doc.get("categorie") == "battle_map" or not doc.get("dimensions")
				or not _porte_ouverte(doc)):
			continue
		rang_porte = _rang_des_portes(doc)
		vus = []
		for p in doc.get("zone_influences") or []:
			zid = p.get("zone")
			if not zid or zid in vus:
				continue
			vus.append(zid)
			if zid not in zones_cache:
				zones_cache[zid] = get_doc_fn(zid) or {}
			danger = _danger(zones_cache[zid])
			if danger > 0:
				sortie.append({"lieu": lid, "zones": [zid], "niveau": _borner_niveau(round(danger)),
							   "rang_porte": rang_porte})

	# (b) Salles de donjon jointes au voisinage.
	donjons = find_docs_fn({"type": "donjon"}) or []
	portails = [d.get("portail") for d in donjons if d.get("portail")]
	portails_docs = {}
	if portails:
		for p in _projeter(find_docs_fn, {"type": "lieu", "_id": {"$in": portails}},
						   ["_id", "lieu_parent", "acces"]):
			portails_docs[p.get("_id")] = p
	joints = []
	for d in donjons:
		if _exclu(d):
			continue
		salles = [e for e in donjon.battle_maps_de(d) if e.get("lieu")]
		portail = d.get("portail")
		portail_doc = portails_docs.get(portail) or {}
		relie = (portail in voisins or portail_doc.get("lieu_parent") in voisins
				 or any(e["lieu"] in voisins for e in salles))
		if relie and _porte_ouverte(portail_doc):
			joints.append((d, salles, portail_doc))
	ids_salles = [e["lieu"] for _, salles, _p in joints for e in salles]
	salles_docs = {}
	if ids_salles:
		for s in _projeter(find_docs_fn, {"type": "lieu", "_id": {"$in": ids_salles}},
						   ["_id", "tags", "proteges_restent_dehors", "acces"]):
			salles_docs[s.get("_id")] = s
	for d, salles, portail_doc in joints:
		for i, e in enumerate(salles):
			sid = e["lieu"]
			sdoc = salles_docs.get(sid) or {}
			if (sid in vises or _exclu(sdoc) or not donjon.proteges_admis(sdoc)
					or not _porte_ouverte(sdoc)):
				continue
			niveau = (e.get("niveau_min") or d.get("niveau_min")
					  or e.get("niveau_max") or d.get("niveau_max") or 1)
			sortie.append({"lieu": sid, "donjon": d["_id"], "etage": i + 1,
						   "niveau": _borner_niveau(niveau),
						   "rang_porte": _rang_des_portes(portail_doc, sdoc)})
	return sortie


# ---------------------------------------------------------------------------
# Rang, protégés, spec
# ---------------------------------------------------------------------------

def rang_du_niveau(niveau: int, bloc: dict | None = None) -> str:
	table = dict(RANGS_PAR_NIVEAU)
	for k, v in ((bloc or {}).get("rangs") or {}).items():
		try:
			table[int(k)] = v
		except (TypeError, ValueError):
			continue
	return table.get(_borner_niveau(niveau), "F")


def rang_du_candidat(c: dict, bloc: dict | None, dest_doc: dict | None) -> str:
	"""Le rang qui commande la mission : le plus élevé du rang du niveau, des barrières
	`rang_min` du lieu de péril (`rang_porte`, relu par `candidats`) et du comptoir — même
	règle « porte la plus stricte » qu'une commission."""
	return acces.rang_le_plus_eleve(
		rang_du_niveau(c.get("niveau", 1), bloc),
		c.get("rang_porte"),
		acces.rang_min_du_lieu(dest_doc),
	) or "F"


def _generer_aventurier_defaut(niveau_max: int) -> dict | None:
	# Import PARESSEUX : `recrutement` tire la base (db.config) et une grappe de modules.
	from utils import recrutement
	return recrutement.generer_aventurier({"_id": "secours"}, None, niveau_max)


def protege_de_aventurier(av: dict) -> dict:
	"""Spec de protégé tirée d'un doc `aventurier:*` généré : identité, caractéristiques
	(budget de création compris — ce sont des aventuriers, pas des civils) et équipement
	PORTÉ. Ils savent se défendre, et on les retrouve blessés."""
	equipement = {s: ref for s, ref in (av.get("slots") or {}).items() if ref}
	spec = {
		"prenom": av.get("prenom", ""),
		"nom": av.get("nom", ""),
		"race": av.get("race", ""),
		"sex": av.get("sex", ""),
		"image": av.get("image", ""),
		"caracteristiques": dict(av.get("caracteristiques_current") or {}),
		"se_defend": True,
		"pv_depart": float(character_stats.SECOURS_PV_DEPART),
	}
	if equipement:
		spec["equipement"] = equipement
	return spec


def proteges_de(niveau: int, generer_fn=None, rand_fn=random.random) -> list:
	"""2 à 3 (SECOURS_NB_MIN/MAX) aventuriers en péril, de grade au plus `niveau`."""
	generer_fn = generer_fn or _generer_aventurier_defaut
	nmin = max(1, int(character_stats.SECOURS_NB_MIN))
	nmax = max(nmin, int(character_stats.SECOURS_NB_MAX))
	n = nmin + int(rand_fn() * (nmax - nmin + 1))
	n = min(nmax, n)
	out = []
	for _ in range(n):
		av = generer_fn(niveau)
		if av:
			out.append(protege_de_aventurier(av))
	return out


def _slug(txt: str) -> str:
	base = unicodedata.normalize("NFKD", str(txt or ""))
	base = "".join(c for c in base if not unicodedata.combining(c))
	brut = "".join(c if c.isalnum() else "_" for c in base.lower())
	return "_".join(x for x in brut.split("_") if x)


def id_secours(lieu_id: str, now: int) -> str:
	"""Identifiant stable sur la FENÊTRE : un même lieu ne porte qu'un secours par tranche."""
	tranche = int(now) // (max(1, int(character_stats.SECOURS_FENETRE_H)) * 3600)
	return f"quete:secours_{_slug(str(lieu_id or '').split(':', 1)[-1])}_{tranche}"


def deja_tire(character: dict, quete_id: str) -> bool:
	"""Ce secours a-t-il déjà été pris (en cours, réussi OU échoué) ?"""
	for q in (character or {}).get("quetes_actives") or []:
		if q.get("id") == quete_id:
			return True
	for q in (character or {}).get("quetes_terminees") or []:
		if q.get("id") == quete_id:
			return True
	return False


def nom_du_lieu(c: dict, get_doc_fn) -> str:
	"""Nom affiché du lieu de péril. Une salle de donjon porte souvent une description
	(« Un vaste réseau souterrain… ») : on nomme alors le DONJON et l'étage."""
	if c.get("donjon"):
		d = get_doc_fn(c["donjon"]) or {}
		nom = (d.get("nom") or "").strip() or "un donjon"
		if donjon.est_a_etages(d):
			etage = c.get("etage") or next(
				(i + 1 for i, e in enumerate(donjon.battle_maps_de(d)) if e.get("lieu") == c.get("lieu")), 1)
			return f"{nom}, étage {int(etage)}"
		return nom
	from utils.characters import lieu_label
	return lieu_label(get_doc_fn(c["lieu"]), c["lieu"])


def spec_secours(character: dict, comptoir_doc: dict, bloc: dict, c: dict, get_doc_fn,
				 rang: str, now: int, generer_fn=None, rand_fn=random.random) -> dict | None:
	"""Spec à la forme de `services.escorte.offre` pour le candidat `c`. None si personne
	n'a pu être généré (règles absentes)."""
	proteges = proteges_de(c.get("niveau", 1), generer_fn, rand_fn)
	if not proteges:
		return None
	cite = bloc.get("cite") or (comptoir_doc or {}).get("lieu_parent")
	from utils.escorte import noms_proteges
	qui = noms_proteges(proteges)
	ou = nom_du_lieu(c, get_doc_fn)
	enseigne = ((comptoir_doc or {}).get("label") or (comptoir_doc or {}).get("nom") or "").strip()
	rec = dict(bloc.get("recompenses") or {})
	xp = int(rec.get("xp", int(character_stats.SECOURS_XP) * int(c.get("niveau", 1) or 1)))
	rec["xp"] = xp
	rec["cuivre"] = int(rec.get("cuivre", max(0, round(xp * float(character_stats.QUETE_CUIVRE_PAR_XP)))))
	rencontre = {"lieu": c["lieu"]}
	if c.get("zones"):
		rencontre["zones"] = list(c["zones"])
	if c.get("donjon"):
		rencontre["donjon"] = c["donjon"]
	spec = {
		"id": id_secours(c["lieu"], now),
		"destination": comptoir_doc.get("_id"),
		"rencontre": rencontre,
		"proteges": proteges,
		"type_secours": True,
		"expire_h": int(character_stats.SECOURS_DELAI_H),
		# ⚠️ Enseignes et lieux portent leur article : deux-points, jamais de préposition.
		"titre": f"Secours : {qui}",
		"description": (
			f"Des aventuriers ne sont pas revenus : {qui}. Dernier signe de vie : {ou}. "
			f"Ils sont blessés mais savent encore se battre. Retrouvez-les et ramenez-les "
			f"vivants au comptoir de la Guilde : {enseigne}."
		),
		"recompenses": rec,
	}
	if cite and rang and rang != acces.RANGS[0]:
		spec["rang_min"] = {"cite": cite, "rang": rang}
	return spec


# ---------------------------------------------------------------------------
# L'offre du comptoir (4ᵉ branche de `escorte.poser_escorte_offerte`)
# ---------------------------------------------------------------------------

def offre_secours(character: dict, comptoir_doc: dict, bloc: dict, find_docs_fn, get_doc_fn,
				  connexions_fn=None, rand_fn=random.random, choix_fn=random.choice,
				  generer_fn=None, now: int | None = None) -> dict | None:
	"""L'offre de secours que ce comptoir peut confier, ou None. Gardes, dans l'ordre :
	membre de la guilde de la cité, tirage (`proba` du bloc ou SECOURS_PROBA), puis un
	candidat dont le rang est à la portée du joueur et dont la tranche n'a pas déjà été prise.
	⚠️ Le candidat se choisit APRÈS le filtre de rang : un rang F trouve la forêt voisine
	plutôt que rien, au lieu de tirer les catacombes puis de se taire."""
	from utils import chasse, escorte
	cite = bloc.get("cite") or (comptoir_doc or {}).get("lieu_parent")
	if not cite or not chasse.membre_de_la_guilde(character, cite, get_doc_fn):
		return None
	if rand_fn() >= float(bloc.get("proba", character_stats.SECOURS_PROBA)):
		return None
	if connexions_fn is None:
		from utils.lieux import connexions_du_lieu as connexions_fn
	get_doc_fn = quetes._cached_getter(get_doc_fn)
	now = int(quetes.now_epoch() if now is None else now)
	possibles = []
	for c in candidats(cite, get_doc_fn, find_docs_fn, connexions_fn):
		if deja_tire(character, id_secours(c["lieu"], now)):
			continue
		rang = rang_du_candidat(c, bloc, comptoir_doc)
		if not acces.rang_min_satisfait(character, {"cite": cite, "rang": rang}):
			continue
		possibles.append((c, rang))
	if not possibles:
		return None
	c, rang = choix_fn(possibles)
	spec = spec_secours(character, comptoir_doc, bloc, c, get_doc_fn, rang, now,
						generer_fn, rand_fn)
	if not spec:
		return None
	return escorte.generer_escorte_authoree(spec, comptoir_doc, find_docs_fn, get_doc_fn)


# ---------------------------------------------------------------------------
# Le délai (paresseux)
# ---------------------------------------------------------------------------

def expirer(character: dict, now: int, get_doc_fn) -> tuple[list, list]:
	"""Secours dont le délai est passé : archivés EN ÉCHEC, protégés libérés — SANS
	sanction de réputation (le joueur n'a pas renoncé, il est arrivé trop tard). Mute sans
	save. Renvoie `(quêtes échues, docs protege:* mutés à persister)`."""
	from utils import escorte
	echues, docs = [], []
	for q in list(escorte.escortes_actives(character)):
		if not est_secours(q):
			continue
		limite = int(q.get("expire_at", 0) or 0)
		if not limite or int(now) < limite:
			continue
		docs.extend(escorte.liberer_proteges(character, q, get_doc_fn, statut="libere"))
		escorte.archiver(character, q, echec=True, now=int(now))
		echues.append(q)
	return echues, docs

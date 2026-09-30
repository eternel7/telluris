# utils/proprietes.py
# Propriétés résidentielles du joueur (pur) — Chambre → Logement → Maison → Demeure → Domaine.
#
# Une propriété est une ENTITÉ INDÉPENDANTE, doc `propriete:<type>_<hex12>`, au type FIGÉ à
# la création : aucune fonction de ce module n'écrit `type_propriete` ailleurs que dans
# `creer_propriete`. Monter en gamme = céder (vendre/abandonner) PUIS acquérir une autre
# propriété ; les aménagements restent attachés au doc cédé, rien n'est transféré.
#
# La propriété SE COMPORTE COMME UN LIEU : elle porte `label`, `image`, `categorie`,
# `lieu_parent`, et une connexion `link:*` la relie à la case où elle a été acquise — `/play`
# et `move_character` la traitent comme n'importe quel sous-lieu sans grille (une boutique).
# ⚠️ Son `type` est `"propriete"`, PAS `"lieu"` : les balayages `find_docs({"type":"lieu"})`
# (éditeur, tick d'ateliers, escortes) n'ont pas à voir des centaines de logis de joueurs.
#
# Tout est piloté par la DONNÉE `rules:proprietes` (préfixe `rules:`, déjà caché) :
#   types        : capacités de base, prix, revente, location (chambre)
#   amenagements : `types_autorises` (LA contrainte de type), coût, prérequis, capacité
#                  ajoutée (occupants / stockage_kg / postes {metier: n}), activité, effets
#   metiers      : personnel engageable (coût d'embauche)
# Les capacités d'une propriété ne sont JAMAIS stockées : dérivées à la lecture (type +
# aménagements installés), comme les stats dérivées d'un personnage.
#
# Où l'on achète : sur une case d'une VILLE couverte par une zone d'influence peinte dont le
# doc porte `type_propriete` (`zone:habitable_<type>`, une par type). Où l'on loue : dans une
# auberge (`auberge.lieu_est_taverne`), une Chambre seulement (`types[].location`).
#
# Vol : chez un PROPRIÉTAIRE (mode achat), un visiteur peut se servir dans le coffre tant
# qu'aucun gardien n'est présent (employé `gardien` affecté à un aménagement `effets.garde`).
# Une chambre LOUÉE est inviolable : seul son locataire y entre.
#
# Pattern utils/montures.py : logique PURE, DB injectée, mute sans jamais sauvegarder.

import random
import time
import uuid

from db.config import get_doc
from models import character_stats
from utils.characters import item_ref_weight, resolve_item_ref
from utils import marche
from utils import zones as zones_util
from utils import recrutement

CATALOGUE_ID = "rules:proprietes"
TYPE_DOC = "propriete"
TYPE_EMPLOYE = "employe"
CATEGORIE = "propriete"

MODE_ACHAT = "achat"
MODE_LOCATION = "location"

POSSEDEE = "possedee"
LOUEE = "louee"
EXPIREE = "expiree"
VENDUE = "vendue"
ABANDONNEE = "abandonnee"

EMPLOYE_ACTIF = "employe"
EMPLOYE_RENVOYE = "renvoye"

# Rôles du personnage vis-à-vis d'une propriété (cf. `role_de`).
PROPRIETAIRE = "proprietaire"
LOCATAIRE = "locataire"
ANCIEN_LOCATAIRE = "ancien_locataire"
VISITEUR = "visiteur"

# Race dont on tire le nom du personnel : on recrute en cité humaine (même pool que
# `recrutement.PRENOM_RACE_MUTUALISEE`, relu et non recopié).
RACE_PERSONNEL = recrutement.PRENOM_RACE_MUTUALISEE


def now_epoch() -> int:
	return int(time.time())


# ── Catalogue ────────────────────────────────────────────────────────────────────

def catalogue(get_doc_fn=None) -> dict:
	"""`{types, amenagements, metiers}` de `rules:proprietes`. Doc absent ⇒ catalogue vide :
	aucune propriété n'est alors achetable, rien ne casse."""
	lire = get_doc_fn or get_doc
	valeur = ((lire(CATALOGUE_ID) or {}).get("value")) or {}
	return {
		"types": list(valeur.get("types") or []),
		"amenagements": list(valeur.get("amenagements") or []),
		"metiers": list(valeur.get("metiers") or []),
		"reglages": dict(valeur.get("reglages") or {}),
	}


def _par_id(liste: list, ident) -> dict | None:
	return next((x for x in liste or [] if x.get("id") == ident), None)


def type_def(cat: dict, type_id) -> dict | None:
	return _par_id(cat.get("types"), type_id)


def amenagement_def(cat: dict, am_id) -> dict | None:
	return _par_id(cat.get("amenagements"), am_id)


def metier_def(cat: dict, metier_id) -> dict | None:
	return _par_id(cat.get("metiers"), metier_id)


def est_propriete(doc: dict) -> bool:
	return (doc or {}).get("type") == TYPE_DOC


def _int(v, defaut=0) -> int:
	try:
		return int(v)
	except (TypeError, ValueError):
		return defaut


# ── Capacités DÉRIVÉES ───────────────────────────────────────────────────────────

def capacites(prop: dict, cat: dict) -> dict:
	"""Capacités de CETTE propriété = base du type + Σ capacité des aménagements installés.
	`postes` : {metier: places} tous aménagements confondus (vue d'ensemble) ;
	le détail par aménagement est dans `postes_par_amenagement`."""
	tdef = type_def(cat, prop.get("type_propriete")) or {}
	cap = {
		"occupants_max": _int(tdef.get("occupants_max")),
		"personnel_max": _int(tdef.get("personnel_max")),
		"stockage_kg": _int(tdef.get("stockage_kg")),
		"postes": {},
	}
	for am_id in prop.get("amenagements") or []:
		adef = amenagement_def(cat, am_id) or {}
		c = adef.get("capacite") or {}
		cap["occupants_max"] += _int(c.get("occupants"))
		cap["stockage_kg"] += _int(c.get("stockage_kg"))
		for metier, n in (c.get("postes") or {}).items():
			cap["postes"][metier] = cap["postes"].get(metier, 0) + _int(n)
	return cap


def postes_par_amenagement(prop: dict, cat: dict) -> list:
	"""[(amenagement_id, metier, places)] des aménagements INSTALLÉS."""
	out = []
	for am_id in prop.get("amenagements") or []:
		adef = amenagement_def(cat, am_id) or {}
		for metier, n in ((adef.get("capacite") or {}).get("postes") or {}).items():
			if _int(n) > 0:
				out.append((am_id, metier, _int(n)))
	return out


def poids_coffre(prop: dict) -> float:
	return round(sum(item_ref_weight(r) for r in prop.get("coffre") or []), 2)


# ── Aménagements ─────────────────────────────────────────────────────────────────

def peut_installer(prop: dict, cat: dict, am_id) -> tuple[bool, str]:
	"""La contrainte de TYPE est ici : un aménagement n'entre que dans les types qui le
	listent. Puis doublon, puis prérequis. Une chambre louée n'est pas aménageable."""
	if prop.get("mode") != MODE_ACHAT:
		return False, "On n'aménage pas une chambre louée."
	adef = amenagement_def(cat, am_id)
	if not adef:
		return False, "Aménagement inconnu."
	tdef = type_def(cat, prop.get("type_propriete")) or {}
	if prop.get("type_propriete") not in (adef.get("types_autorises") or []):
		return False, f"{adef.get('nom', am_id)} : impossible dans un(e) {tdef.get('label', 'propriété')}."
	if am_id in (prop.get("amenagements") or []):
		return False, f"{adef.get('nom', am_id)} est déjà installé(e)."
	manquants = [p for p in adef.get("prerequis") or [] if p not in (prop.get("amenagements") or [])]
	if manquants:
		noms = ", ".join((amenagement_def(cat, p) or {}).get("nom", p) for p in manquants)
		return False, f"Il faut d'abord : {noms}."
	return True, ""


def amenagements_disponibles(prop: dict, cat: dict) -> list:
	"""Défs installables MAINTENANT (type, doublon, prérequis) — ce qu'affiche le panneau."""
	return [a for a in cat.get("amenagements") or [] if peut_installer(prop, cat, a.get("id"))[0]]


def amenagements_du_type(cat: dict, type_id) -> list:
	"""Tous les aménagements AUTORISÉS pour un type (catalogue d'une offre d'achat)."""
	return [a for a in cat.get("amenagements") or [] if type_id in (a.get("types_autorises") or [])]


def installer(prop: dict, am_id) -> None:
	"""Ajoute l'aménagement (l'appelant a vérifié `peut_installer` et débité)."""
	prop.setdefault("amenagements", []).append(am_id)


# ── Zones habitables (achat) ─────────────────────────────────────────────────────

def lieu_est_ville(lieu_doc: dict) -> bool:
	"""Une ville ou une capitale (`categorie:"ville"`, sous-catégorie ville|capitale)."""
	return (lieu_doc or {}).get("categorie") == "ville"


def types_achetables_ici(lieu_doc: dict, position: dict, get_doc_fn=None) -> list:
	"""Types de propriété achetables sur CETTE case : zones peintes de la ville dont le doc
	porte `type_propriete` et qui couvrent (x, y). Ordre de la carte, sans doublon."""
	if not lieu_est_ville(lieu_doc):
		return []
	lire = get_doc_fn or get_doc
	x = (position or {}).get("x")
	y = (position or {}).get("y")
	if x is None or y is None:
		return []
	placements = lieu_doc.get("zone_influences") or []
	vus, out = set(), []
	for p in placements:
		zone_id = p.get("zone")
		if not zone_id or zone_id in vus:
			continue
		vus.add(zone_id)
		zdoc = lire(zone_id) or {}
		type_id = zdoc.get("type_propriete")
		if type_id and type_id not in out and zones_util.est_dans_zone(x, y, zone_id, placements):
			out.append(type_id)
	return out


def offre_ici(lieu_doc: dict, position: dict, est_auberge: bool, cat: dict, get_doc_fn=None) -> bool:
	"""Le bouton « 🏠 Propriétés » de la sidebar : un type achetable sur CETTE case, ou une
	chambre à louer dans une auberge. Partagé par `/play` et le pas de `move_character` (un pas
	ne recharge pas la page : sans ce recalcul, le bouton resterait celui de la case d'avant)."""
	if [t for t in types_achetables_ici(lieu_doc, position, get_doc_fn) if type_def(cat, t)]:
		return True
	return bool(est_auberge and any(location_de(t) for t in cat["types"]))


# ── Prix d'achat : voisinage + occupation de la case ─────────────────────────────
# prix = prix_cuivre × (1 + min(plafond, Σ bonus(genre) × (R+1−d)/(R+1))) × multiplicateur ** n
#   d : distance de Chebyshev entre la case d'achat et l'entrée d'un lieu voisin (≤ R) ;
#   n : propriétés ACHETÉES (possédées) déjà reliées à CETTE case.
# Surchargeable par `rules:proprietes.reglages.prix_achat` (clé absente ⇒ défaut ci-dessous).
# La location d'une chambre d'auberge n'est pas concernée.
PRIX_ACHAT_DEFAUT = {
	"rayon": 4,
	"bonus": {"marchand": 0.05, "grand_marchand": 0.20, "guilde": 0.20},
	"plafond_voisinage": 1.5,
	"multiplicateur_occupation": 2,
}

MARCHAND = "marchand"
GRAND_MARCHAND = "grand_marchand"
GUILDE = "guilde"


def reglages_prix(cat: dict) -> dict:
	"""Défauts du module ← `reglages.prix_achat` (champ à champ, `bonus` genre à genre)."""
	surcharge = (reglages(cat) or {}).get("prix_achat") or {}
	out = {**PRIX_ACHAT_DEFAUT, "bonus": dict(PRIX_ACHAT_DEFAUT["bonus"])}
	for k, v in surcharge.items():
		if k == "bonus" and isinstance(v, dict):
			out["bonus"].update(v)
		elif k in out and k != "bonus":
			out[k] = v
	return out


def genre_voisin(lieu_doc: dict) -> str | None:
	"""Ce que ce lieu apporte au quartier ; le genre le plus fort gagne. Prédicats existants :
	`recrutement.lieu_de_guilde`, table `LIEU_CATEGORIES_FUSION` (lue comme `grande_maison`),
	et `marche.besoins_lieu` non vide — c'est `transport.est_magasin`, non importé ici
	(transport → focalisation → lieux → proprietes : cycle)."""
	if not lieu_doc or est_propriete(lieu_doc):
		return None
	if recrutement.lieu_de_guilde(lieu_doc):
		return GUILDE
	if grande_maison(lieu_doc):
		return GRAND_MARCHAND
	if marche.besoins_lieu(lieu_doc):
		return MARCHAND
	return None


def voisinage(connexions: list, cite_id, x: int, y: int, rayon: int, get_doc_fn=None) -> dict:
	"""{"voisins": [(genre, d)], "proprietes_case": n} autour de (x, y) dans `cite_id`.
	`connexions` = docs bruts touchant la cité (`lieux.connexions_du_lieu`). Chaque destination
	compte UNE fois, à sa plus courte distance ; seules celles du rayon sont relues."""
	lire = get_doc_fn or get_doc
	distances = {}
	for conn in connexions or []:
		nodes = [n for n in conn.get("nodes") or [] if isinstance(n, dict)]
		ici = next((n for n in nodes if n.get("lieu") == cite_id), None)
		autre = next((n for n in nodes if n.get("lieu") != cite_id), None)
		if ici is None or autre is None or not autre.get("lieu"):
			continue
		pos = list(ici.get("pos") or [])[:2]
		if len(pos) < 2:
			continue
		d = max(abs(_int(pos[0]) - x), abs(_int(pos[1]) - y))
		if d <= rayon and d < distances.get(autre["lieu"], rayon + 1):
			distances[autre["lieu"]] = d
	voisins, n = [], 0
	for lieu_id, d in distances.items():
		doc = lire(lieu_id) or {}
		if est_propriete(doc):
			if d == 0 and doc.get("mode") == MODE_ACHAT and doc.get("statut") == POSSEDEE:
				n += 1
			continue
		genre = genre_voisin(doc)
		if genre:
			voisins.append((genre, d))
	return {"voisins": voisins, "proprietes_case": n}


def prix_achat(tdef: dict, cat: dict, vois: dict) -> dict:
	"""Prix majoré d'un type sur une case dont `vois` est le `voisinage`."""
	regl = reglages_prix(cat)
	rayon = max(0, _int(regl.get("rayon")))
	bonus = regl.get("bonus") or {}
	somme = sum(float(bonus.get(g) or 0) * (rayon + 1 - d) / (rayon + 1)
				for g, d in (vois or {}).get("voisins") or [])
	voisinage_facteur = 1 + min(float(regl.get("plafond_voisinage") or 0), somme)
	n = _int((vois or {}).get("proprietes_case"))
	occupation_facteur = float(regl.get("multiplicateur_occupation") or 1) ** n
	base = _int((tdef or {}).get("prix_cuivre"))
	return {
		"prix": int(round(base * voisinage_facteur * occupation_facteur)),
		"base": base,
		"voisinage_pct": int(round((voisinage_facteur - 1) * 100)),
		"occupation_facteur": occupation_facteur,
		"proprietes_case": n,
	}


# ── Création, lien, rôles ────────────────────────────────────────────────────────

def nom_personnage(character: dict) -> str:
	return f"{character.get('prenom', '')} {character.get('nom', '')}".strip() or "Inconnu"


def creer_propriete(tdef: dict, cite_id, origine: dict, acheteur: dict, mode: str,
					now: int | None = None) -> dict:
	"""Doc `propriete:*` neuf. `origine` = {"lieu", "pos": [x, y]} : la case d'où part la
	connexion. Le nom du propriétaire est DÉNORMALISÉ (un visiteur n'a pas le droit de relire
	le `character:*` d'autrui — même règle que les messages de taverne)."""
	now = now_epoch() if now is None else now
	type_id = tdef.get("id", "")
	qui = nom_personnage(acheteur)
	prop = {
		"_id": f"propriete:{type_id}_{uuid.uuid4().hex[:12]}",
		"type": TYPE_DOC,
		"type_propriete": type_id,
		"mode": mode,
		"categorie": CATEGORIE,
		"label": f"{tdef.get('label', 'Propriété')} de {qui}",
		"image": tdef.get("image", ""),
		"lieu_parent": cite_id,
		"statut": LOUEE if mode == MODE_LOCATION else POSSEDEE,
		"proprietaire": acheteur.get("_id"),
		"proprietaire_nom": qui,
		"acquise_at": now,
		"prix_paye": 0,
		"origine": {"lieu": (origine or {}).get("lieu"), "pos": list((origine or {}).get("pos") or [0, 0])},
		"amenagements": [],
		"coffre": [],
		"heberges": [],
		"employes": [],
	}
	prop["lien"] = f"link:{prop['_id'].split(':', 1)[1]}"
	return prop


def creer_lien(prop: dict) -> dict:
	"""Connexion case d'origine ↔ propriété (nœud de la propriété en [0,0], comme une
	boutique). Même forme que les liens des générateurs `dev/gen_magasins*.py`."""
	origine = prop.get("origine") or {}
	return {
		"_id": prop["lien"],
		"type": "connection",
		"nodes": [
			{"lieu": origine.get("lieu"), "pos": list(origine.get("pos") or [0, 0])},
			{"lieu": prop["_id"], "pos": [0, 0]},
		],
		"metadata": {"type": CATEGORIE, "status": "ouvert"},
	}


def traiter_expiration_location(prop: dict, now: int | None = None) -> bool:
	"""Péremption PARESSEUSE d'une location (aucun tick de fond). True si le doc a changé.
	La chambre expirée reste celle du locataire : il peut y reprendre ses affaires, et
	relouer dans la même auberge la réactive (`louer`)."""
	now = now_epoch() if now is None else now
	if (prop.get("mode") == MODE_LOCATION and prop.get("statut") == LOUEE
			and _int(prop.get("expire_at")) <= now):
		prop["statut"] = EXPIREE
		return True
	return False


def role_de(character: dict, prop: dict, now: int | None = None) -> str | None:
	"""Rôle du personnage — None = il n'a rien à y faire (refus d'entrée)."""
	cid = (character or {}).get("_id")
	statut = prop.get("statut")
	a_lui = prop.get("proprietaire") == cid
	if prop.get("mode") == MODE_LOCATION:
		if not a_lui:
			return None
		now = now_epoch() if now is None else now
		if statut == LOUEE and _int(prop.get("expire_at")) > now:
			return LOCATAIRE
		if statut in (LOUEE, EXPIREE):
			return ANCIEN_LOCATAIRE
		return None
	if statut != POSSEDEE:
		return None
	return PROPRIETAIRE if a_lui else VISITEUR


def acces_propriete(character: dict, prop: dict, now: int | None = None) -> tuple[bool, str]:
	"""Entrer dans une propriété. Achat : ouverte à tous (visible par tout joueur). Location :
	INVIOLABLE, son locataire seul. Cédée : plus personne."""
	if role_de(character, prop, now):
		return True, ""
	if prop.get("mode") == MODE_LOCATION:
		return False, "Cette chambre est louée à quelqu'un d'autre."
	return False, "Cette propriété n'est plus accessible."


def peut_dormir(character: dict, prop: dict, now: int | None = None) -> bool:
	"""Nuit gratuite : chez soi (propriétaire) ou dans sa chambre louée non expirée."""
	return role_de(character, prop, now) in (PROPRIETAIRE, LOCATAIRE)


# ── Possession ───────────────────────────────────────────────────────────────────

def acquerir(character: dict, prop: dict, prix: int) -> None:
	"""Attache la propriété au personnage (index `character.proprietes`). Sans save."""
	prop["prix_paye"] = int(prix)
	liste = character.setdefault("proprietes", [])
	if prop["_id"] not in liste:
		liste.append(prop["_id"])


def proprietes_de(character: dict, get_doc_fn=None) -> list:
	"""Docs des propriétés ACTIVES (possédées ou louées, expirées comprises) du personnage.
	Même preuve d'appartenance qu'une monture : l'index du character ET `proprietaire`."""
	lire = get_doc_fn or get_doc
	out = []
	for pid in character.get("proprietes") or []:
		p = lire(pid)
		if (p and p.get("proprietaire") == character.get("_id")
				and p.get("statut") in (POSSEDEE, LOUEE, EXPIREE)):
			out.append(p)
	return out


def occuper(character: dict, prop: dict) -> tuple[bool, str]:
	"""Fait de CETTE propriété la résidence (une seule à la fois). Propriétaire seulement."""
	if role_de(character, prop) != PROPRIETAIRE:
		return False, "Vous ne pouvez occuper qu'une propriété qui vous appartient."
	character["residence"] = prop["_id"]
	return True, ""


def quitter(character: dict, prop: dict) -> tuple[bool, str]:
	if character.get("residence") != prop.get("_id"):
		return False, "Vous ne résidez pas ici."
	character["residence"] = None
	return True, ""


def peut_ceder(prop: dict, employes: list | None = None) -> tuple[bool, str]:
	"""Vendre ou abandonner laisse la propriété derrière soi : rien ne doit y disparaître —
	ni le coffre, ni les compagnons hébergés, ni la caisse des ateliers (le rayon et les
	matières confiées, eux, partent avec les marchands renvoyés : c'est leur fonds)."""
	if any(_int(e.get("caisse_cuivre")) for e in employes or []):
		return False, "Relevez d'abord la caisse de vos marchands."
	if prop.get("coffre"):
		return False, "Videz le coffre avant de céder la propriété."
	if prop.get("heberges"):
		return False, "Reprenez d'abord les compagnons hébergés ici."
	return True, ""


def revente_autorisee(tdef: dict, cite_doc: dict | None) -> tuple[bool, str]:
	"""Règles économiques : le TYPE fixe un facteur de revente (0 ⇒ invendable) et la CITÉ
	peut fermer le marché immobilier (`proprietes.revente: false` sur son doc)."""
	if float(tdef.get("revente_facteur") or 0) <= 0:
		return False, "Ce type de propriété ne se revend pas."
	if ((cite_doc or {}).get("proprietes") or {}).get("revente") is False:
		return False, "La cité n'autorise pas la revente de biens."
	return True, ""


def prix_revente(tdef: dict, prop: dict) -> int:
	"""Prix PAYÉ × facteur du type : un bien acheté cher (quartier marchand, case déjà
	occupée — cf. `prix_achat`) se revend en proportion. `prix_paye` absent ou nul (bien
	d'avant la majoration) ⇒ prix du type. Les aménagements ne sont pas remboursés : ils
	restent attachés au bien cédé."""
	base = _int((prop or {}).get("prix_paye")) or _int(tdef.get("prix_cuivre"))
	return int(round(base * float(tdef.get("revente_facteur") or 0)))


def ceder(character: dict, prop: dict, statut: str, employes: list) -> None:
	"""Vente ou abandon : la propriété quitte le personnage, garde ses aménagements, son
	personnel est renvoyé. Mute les docs, sans save (le lien est supprimé par l'appelant)."""
	prop["statut"] = statut
	prop["ancien_proprietaire"] = prop.get("proprietaire")
	prop["proprietaire"] = None
	prop["cedee_at"] = now_epoch()
	for e in employes:
		renvoyer(prop, e)
	if character.get("residence") == prop.get("_id"):
		character["residence"] = None
	character["proprietes"] = [p for p in character.get("proprietes") or [] if p != prop.get("_id")]


# ── Location (chambre d'auberge) ─────────────────────────────────────────────────

def location_de(tdef: dict) -> dict | None:
	"""{prix_cuivre, duree_s} si ce type se loue, sinon None."""
	loc = (tdef or {}).get("location") or None
	if not loc or _int(loc.get("duree_s")) <= 0:
		return None
	return {"prix_cuivre": _int(loc.get("prix_cuivre")), "duree_s": _int(loc.get("duree_s"))}


def chambre_louee_ici(character: dict, auberge_id, get_doc_fn=None) -> dict | None:
	"""La chambre (louée ou expirée) de ce personnage dans CETTE auberge, s'il en a une."""
	for p in proprietes_de(character, get_doc_fn):
		if p.get("mode") == MODE_LOCATION and (p.get("origine") or {}).get("lieu") == auberge_id:
			return p
	return None


def prolonger_location(prop: dict, duree_s: int, now: int | None = None) -> None:
	"""Relouer : on repart de maintenant, ou de l'échéance si elle n'est pas passée
	(payer d'avance ne fait jamais perdre de temps)."""
	now = now_epoch() if now is None else now
	depart = max(now, _int(prop.get("expire_at")))
	prop["expire_at"] = depart + int(duree_s)
	prop["statut"] = LOUEE


# ── Coffre ───────────────────────────────────────────────────────────────────────

def peut_deposer(role: str, prop: dict, cat: dict, ref) -> tuple[bool, str]:
	if role not in (PROPRIETAIRE, LOCATAIRE):
		return False, "Vous ne pouvez rien déposer ici."
	plafond = capacites(prop, cat)["stockage_kg"]
	if poids_coffre(prop) + item_ref_weight(ref) > plafond:
		return False, f"Le coffre est plein ({plafond} kg)."
	return True, ""


def peut_retirer(role: str, prop: dict, gardien: bool) -> tuple[bool, str]:
	"""Le propriétaire, le locataire (même expiré : ce sont ses affaires), ou un VISITEUR
	chez un propriétaire sans gardien — c'est le vol. Une chambre louée est inviolable."""
	if role in (PROPRIETAIRE, LOCATAIRE, ANCIEN_LOCATAIRE):
		return True, ""
	if role == VISITEUR and prop.get("mode") == MODE_ACHAT:
		if gardien:
			return False, "Un gardien veille : impossible de se servir ici."
		return True, ""
	return False, "Ce coffre ne vous est pas accessible."


def deposer(character: dict, prop: dict, pos: int) -> object:
	refs = character.get("inventaire") or []
	ref = refs.pop(pos)
	character["inventaire"] = refs
	prop.setdefault("coffre", []).append(ref)
	return ref


def retirer(character: dict, prop: dict, pos: int) -> object:
	refs = prop.get("coffre") or []
	ref = refs.pop(pos)
	prop["coffre"] = refs
	character.setdefault("inventaire", []).append(ref)
	return ref


def localiser(refs: list, idx, item_id) -> int | None:
	"""Position d'une référence — délégué au chokepoint des transferts du groupe."""
	return recrutement._localiser_ref(refs or [], idx, item_id)


# ── Personnel (employés) ─────────────────────────────────────────────────────────

def employes_effectifs(prop: dict, get_doc_fn=None) -> list:
	"""Docs des employés ACTIFS : index `prop.employes` résolu, statut + `propriete` vérifiés
	(un doc `employe:*` n'a pas de `user_id` : comme un compagnon, le lien fait foi)."""
	lire = get_doc_fn or get_doc
	out = []
	for eid in prop.get("employes") or []:
		e = lire(eid)
		if e and e.get("statut") == EMPLOYE_ACTIF and e.get("propriete") == prop.get("_id"):
			out.append(e)
	return out


def postes_libres(prop: dict, cat: dict, employes: list) -> list:
	"""[{amenagement, metier, libres}] : places non pourvues par aménagement installé."""
	out = []
	for am_id, metier, places in postes_par_amenagement(prop, cat):
		pris = sum(1 for e in employes if e.get("poste") == am_id and e.get("metier") == metier)
		if places - pris > 0:
			out.append({"amenagement": am_id, "metier": metier, "libres": places - pris})
	return out


def peut_engager(prop: dict, cat: dict, employes: list, metier_id, am_id) -> tuple[bool, str]:
	"""Un employé occupe un POSTE : un aménagement installé qui l'ouvre, non pourvu, sous le
	plafond de personnel du type. L'espace ne crée jamais le PNJ — c'est ce geste qui le fait."""
	if prop.get("mode") != MODE_ACHAT:
		return False, "On n'engage pas de personnel dans une chambre louée."
	if not metier_def(cat, metier_id):
		return False, "Métier inconnu."
	if not any(p["amenagement"] == am_id and p["metier"] == metier_id
			   for p in postes_libres(prop, cat, employes)):
		return False, "Aucun poste libre pour ce métier dans cet aménagement."
	if len(employes) >= capacites(prop, cat)["personnel_max"]:
		return False, "Cette propriété ne peut pas loger davantage de personnel."
	return True, ""


def creer_employe(prop: dict, candidat: dict, employeur: dict) -> dict:
	"""Doc `employe:*` attaché à CETTE propriété (jamais transféré à une autre), né d'un
	candidat du tableau d'embauche. Un employé PRODUCTIF (`categorie`) a la forme d'un lieu
	marchand (`categorie`, `stock_*`, `lieu_parent`) : `utils/marche.py` et `utils/commande.py`
	le prennent tel quel là où ils attendent une boutique."""
	metier_id = candidat.get("metier", "")
	employe = {
		"_id": f"employe:{metier_id}_{uuid.uuid4().hex[:12]}",
		"type": TYPE_EMPLOYE,
		"metier": metier_id,
		"prenom": candidat.get("prenom", ""),
		"nom": candidat.get("nom", ""),
		"sex": candidat.get("sex", ""),
		"race": candidat.get("race", RACE_PERSONNEL),
		"portrait": candidat.get("portrait", ""),
		"propriete": prop.get("_id"),
		"poste": candidat.get("amenagement"),
		"employe_par": employeur.get("_id"),
		"statut": EMPLOYE_ACTIF,
		"embauche_at": now_epoch(),
	}
	if candidat.get("categorie"):
		employe.update({
			"categorie": candidat["categorie"],
			"modele": candidat.get("modele", ""),
			"lieu_parent": prop.get("lieu_parent"),
			"label": f"{nom_personnage(employe)}",
			"stock_matieres": {},
			"stock_vente": [],
			"caisse_cuivre": 0,
		})
	return employe


def engager(prop: dict, employe: dict) -> None:
	liste = prop.setdefault("employes", [])
	if employe["_id"] not in liste:
		liste.append(employe["_id"])


def renvoyer(prop: dict, employe: dict) -> None:
	employe["statut"] = EMPLOYE_RENVOYE
	prop["employes"] = [e for e in prop.get("employes") or [] if e != employe.get("_id")]


def gardien_present(prop: dict, cat: dict, employes: list) -> bool:
	"""Un employé au poste d'un aménagement `effets.garde` INSTALLÉ, du métier que ce poste
	ouvre. La loge vide ne garde rien : sans le PNJ, l'espace n'est qu'un espace."""
	installes = set(prop.get("amenagements") or [])
	for e in employes:
		adef = amenagement_def(cat, e.get("poste")) or {}
		postes = (adef.get("capacite") or {}).get("postes") or {}
		if (e.get("poste") in installes and (adef.get("effets") or {}).get("garde")
				and e.get("metier") in postes):
			return True
	return False


def activites(prop: dict, cat: dict, employes: list) -> list:
	"""Activités des aménagements installés : exercée ssi un employé du bon métier y est
	affecté. La production elle-même est celle des ATELIERS (`produire`)."""
	out = []
	for am_id in prop.get("amenagements") or []:
		adef = amenagement_def(cat, am_id) or {}
		act = adef.get("activite")
		if not act:
			continue
		qui = next((e for e in employes
					if e.get("poste") == am_id and e.get("metier") == act.get("metier")), None)
		out.append({
			"amenagement": am_id,
			"nom": adef.get("nom", am_id),
			"label": act.get("label", ""),
			"metier": act.get("metier", ""),
			"exercee": qui is not None,
			"employe": nom_personnage(qui) if qui else "",
		})
	return out


# ── Ateliers : PNJ marchands employés ────────────────────────────────────────────
# Un employé dont le poste ouvre des `activite.categories` exerce une catégorie de BOUTIQUE :
# il produit à partir de ce qu'on lui confie et du flux de SA propriété (jamais celui de la
# ville), ses ventes remplissent une caisse que relève le propriétaire, et tout visiteur peut
# lui acheter ou lui commander — simple pour tous, sur mesure pour une grande maison seule
# (`commande.lieu_fabrique_sur_mesure` appliqué à l'employé, rien à ajouter).

MODELE_PREFIXE = "pnj:marchand_"


def reglages(cat: dict) -> dict:
	"""`rules:proprietes.reglages` : durée du tableau d'embauche, vente automatique."""
	return cat.get("reglages") or {}


def est_atelier(doc: dict) -> bool:
	doc = doc or {}
	return (doc.get("type") == TYPE_EMPLOYE and bool(doc.get("categorie"))
			and doc.get("statut") == EMPLOYE_ACTIF)


def grande_maison(employe: dict) -> bool:
	"""Relu à chaque appel dans la variable de monde (jamais stocké sur l'employé)."""
	return (employe or {}).get("categorie") in (character_stats.LIEU_CATEGORIES_FUSION or {})


def atelier_actif(character: dict, lieu_doc: dict, get_doc_fn=None) -> dict | None:
	"""L'atelier désigné par le champ TRANSITOIRE `atelier_courant`, s'il travaille dans CETTE
	propriété. C'est lui que le marché et les commandes traitent comme « le lieu »."""
	if not est_propriete(lieu_doc):
		return None
	eid = (character or {}).get("atelier_courant")
	if not eid or eid not in (lieu_doc.get("employes") or []):
		return None
	e = (get_doc_fn or get_doc)(eid)
	if e and est_atelier(e) and e.get("propriete") == lieu_doc.get("_id"):
		return e
	return None


def categories_du_poste(adef: dict, metier_id) -> list:
	act = (adef or {}).get("activite") or {}
	return list(act.get("categories") or []) if act.get("metier") == metier_id else []


# ── Tableau d'embauche ───────────────────────────────────────────────────────────

def _candidat(am_id, mdef: dict, race: str, portrait: str, rand, categorie=None, modele=None) -> dict:
	sex = rand.choice(["M", "F"])
	prenoms = recrutement.prenoms_possibles(race, sex)
	noms = recrutement.NOMS.get(race) or recrutement.NOMS["defaut"]
	c = {
		"id": f"cand_{uuid.uuid4().hex[:10]}",
		"amenagement": am_id,
		"metier": mdef.get("id", ""),
		"prenom": rand.choice(prenoms),
		"nom": rand.choice(noms),
		"sex": sex,
		"race": race,
		"portrait": portrait,
		"cout": _int(mdef.get("cout_embauche_cuivre")),
	}
	if categorie:
		c["categorie"] = categorie
		c["modele"] = modele
	return c


def generer_candidats(prop: dict, cat: dict, employes: list, get_doc_fn=None,
					  portraits=None, rand=random) -> list:
	"""Un candidat par poste libre — et, pour un poste marchand, un par catégorie ouverte dont
	le marchand générique `pnj:marchand_<cat>` existe : le candidat en reprend le portrait et
	la race, mais porte un nom TIRÉ (deux joueurs n'embauchent pas le même Maître Fromond)."""
	return _candidats_pour(postes_libres(prop, cat, employes), cat, get_doc_fn, portraits, rand)


def _candidats_pour(postes: list, cat: dict, get_doc_fn, portraits, rand) -> list:
	lire = get_doc_fn or get_doc
	out = []
	for p in postes:
		mdef = metier_def(cat, p["metier"])
		if not mdef:
			continue
		adef = amenagement_def(cat, p["amenagement"]) or {}
		cats = categories_du_poste(adef, p["metier"])
		if cats:
			for c in cats:
				modele = lire(MODELE_PREFIXE + c)
				if modele:
					out.append(_candidat(p["amenagement"], mdef, modele.get("race") or RACE_PERSONNEL,
										 modele.get("portrait", ""), rand, c, modele["_id"]))
		else:
			portrait = rand.choice(portraits) if portraits else ""
			out.append(_candidat(p["amenagement"], mdef, RACE_PERSONNEL, portrait, rand))
	return out


def rafraichir_candidats(prop: dict, cat: dict, employes: list, get_doc_fn=None, portraits=None,
						 now: int | None = None, rand=random, force: bool = False) -> bool:
	"""Péremption PARESSEUSE du tableau. Tableau valide : on retire les candidats dont le
	poste a été pourvu entre-temps, et on complète — sans re-tirer les autres — les postes
	libres qui n'ont plus (poste pourvu en partie) ou pas encore (aménagement installé
	après le tirage) de candidat. True si le doc a changé."""
	now = now_epoch() if now is None else now
	if not force and prop.get("candidats") is not None and _int(prop.get("candidats_expire_at")) > now:
		postes = postes_libres(prop, cat, employes)
		libres = {(p["amenagement"], p["metier"]) for p in postes}
		gardes = [c for c in prop["candidats"] if (c.get("amenagement"), c.get("metier")) in libres]
		couverts = {(c.get("amenagement"), c.get("metier")) for c in gardes}
		gardes += _candidats_pour([p for p in postes if (p["amenagement"], p["metier"]) not in couverts],
								  cat, get_doc_fn, portraits, rand)
		if gardes == prop["candidats"]:
			return False
		prop["candidats"] = gardes
		return True
	prop["candidats"] = generer_candidats(prop, cat, employes, get_doc_fn, portraits, rand)
	prop["candidats_expire_at"] = now + _int(reglages(cat).get("candidats_duree_s"), 86400)
	return True


def candidat_par_id(prop: dict, cid) -> dict | None:
	return next((c for c in prop.get("candidats") or [] if c.get("id") == cid), None)


def retirer_candidat(prop: dict, cid) -> None:
	prop["candidats"] = [c for c in prop.get("candidats") or [] if c.get("id") != cid]


# ── Matières confiées, produits, caisse ──────────────────────────────────────────

def donner(employe: dict, item_doc: dict) -> tuple[bool, str]:
	"""Le joueur CONFIE un objet à son marchand. Un bien que l'atelier produit va au rayon
	(il le revendra) ; une matière de ses recettes entre dans `stock_matieres` sous la clé de
	`marche.cle_matiere_lieu` — exactement comme une vente à une boutique, sans paiement."""
	if not est_atelier(employe):
		return False, "Ce PNJ ne tient pas d'atelier."
	if not marche.lieu_buys(employe, item_doc):
		return False, "Il n'a pas l'usage de cet objet."
	item_id = (item_doc or {}).get("item") or (item_doc or {}).get("_id")
	if marche.lieu_produit(employe, item_doc):
		marche._stock_vente_add(employe.setdefault("stock_vente", []), item_id, 1)
	else:
		cle = marche.cle_matiere_lieu(employe.get("categorie"), item_doc, employe)
		stock = employe.setdefault("stock_matieres", {})
		stock[cle] = _int(stock.get(cle)) + 1
	return True, ""


def racheter(employe: dict, item_doc: dict) -> tuple[bool, str]:
	"""Un VISITEUR vend un objet au marchand : l'atelier l'absorbe exactement comme un objet
	confié (`donner`) — jamais `marche.convertir_apres_achat`, dont le tick approvisionne et
	suit le flux de la cité. Le paiement (argent créé, comme en boutique) reste à l'appelant."""
	return donner(employe, item_doc)


def vend_au_proprietaire(character: dict, employe: dict, get_doc_fn=None) -> bool:
	"""L'atelier travaille-t-il pour CE personnage ? Son maître ne lui vend ni ne lui achète
	rien : il confie et reprend au 📦 Coffre."""
	if not est_atelier(employe):
		return False
	prop = (get_doc_fn or get_doc)(employe.get("propriete", "")) or {}
	return bool(prop.get("proprietaire")) and prop.get("proprietaire") == (character or {}).get("_id")


def reprendre_produit(employe: dict, item_id) -> bool:
	"""Le propriétaire reprend UN exemplaire du rayon (gratuit : c'est sa production)."""
	rayon = employe.get("stock_vente") or []
	entree = next((e for e in rayon if e.get("item_id") == item_id and _int(e.get("qty")) > 0), None)
	if entree is None:
		return False
	entree["qty"] = _int(entree.get("qty")) - 1
	employe["stock_vente"] = [e for e in rayon if _int(e.get("qty")) > 0]
	return True


def prix_vente_auto(item_id) -> int:
	"""Prix d'une vente automatique : le prix médian du marché (relation neutre, sans stock)."""
	doc = resolve_item_ref(item_id) or {}
	pmin, pmax = marche.prix_range_cuivre(doc, item_id)
	return marche.prix_base_cuivre(pmin, pmax, 50, "achat")


def ecouler_employe(employe: dict, regl: dict, rand=random) -> list:
	"""Vente automatique du rayon d'un marchand à domicile : chaque produit tire sa demande
	(`vente_auto.proba`) et en écoule une fraction (`fraction`, au moins 1), en gardant
	`reserve` exemplaires pour les visiteurs. ⚠️ Pas `ecouler_produits_pnj` : celle-ci
	n'écoule que l'excédent au-dessus d'une cible de boutique (25) — ici, rien ne partirait."""
	va = regl.get("vente_auto") or {}
	proba = float(va.get("proba", 0.5))
	frac = float(va.get("fraction", 0.34))
	reserve = _int(va.get("reserve"), 1)
	ecoules = []
	for entree in employe.get("stock_vente") or []:
		qty = _int(entree.get("qty"))
		if qty <= reserve or rand.random() >= proba:
			continue
		vendu = max(1, int(round((qty - reserve) * frac)))
		entree["qty"] = qty - vendu
		ecoules.append({"item_id": entree.get("item_id"), "qty": vendu})
	employe["stock_vente"] = [e for e in employe.get("stock_vente") or [] if _int(e.get("qty")) > 0]
	return ecoules


def flux_propriete(prop: dict) -> dict:
	"""Le flux PROPRE du bien — même mécanique que celui d'une ville (`flux_marchand`), clos par
	`marche.persister_flux`. Il prend son sens avec plusieurs marchands : ce que l'un écoule
	nourrit l'atelier de l'autre."""
	return marche.ouvrir_flux(prop)


def produire(employe: dict, flux: dict | None, passes: int, cat: dict,
			 prix_fn=prix_vente_auto, rand=random) -> tuple[bool, int]:
	"""`passes` ticks d'atelier SANS approvisionnement gratuit ; les ventes automatiques vont
	dans la caisse. Renvoie (changé, gain en cuivre). Mute l'employé et le flux, sans save."""
	if not est_atelier(employe):
		return False, 0
	recettes = marche.recettes_lieu(employe)
	regl = reglages(cat)
	change, gain = False, 0
	for _ in range(max(0, int(passes))):
		ch, ecoules = marche.tick_detaille(employe, recettes, flux, appro=False,
										   ecouler=lambda d: ecouler_employe(d, regl, rand))
		change = change or ch
		gain += sum(_int(e.get("qty")) * prix_fn(e.get("item_id")) for e in ecoules)
	if gain:
		encaisser(employe, gain)
	return change or bool(gain), gain


def encaisser(employe: dict, cuivre: int) -> None:
	employe["caisse_cuivre"] = _int(employe.get("caisse_cuivre")) + int(cuivre)


def relever_caisse(employes: list) -> int:
	"""Vide la caisse de chaque atelier ; renvoie le total. L'appelant crédite qui relève."""
	total = 0
	for e in employes:
		total += _int(e.get("caisse_cuivre"))
		if e.get("caisse_cuivre"):
			e["caisse_cuivre"] = 0
	return total


# ── Compagnons hébergés ──────────────────────────────────────────────────────────

def occupants(character_residence: bool, prop: dict) -> int:
	"""Occupants = le résident (s'il réside ici) + les compagnons hébergés."""
	return (1 if character_residence else 0) + len(prop.get("heberges") or [])


def heberger(character: dict, prop: dict, cat: dict, av: dict) -> tuple[bool, str]:
	"""Le compagnon quitte le groupe et reste au logis (`loge_a`) — il n'est plus dans
	`character.groupe`, donc `groupe_effectif` l'ignore sans une ligne de plus. Son statut
	`embauche` et son affinité restent : on le reprend tel quel."""
	if prop.get("mode") != MODE_ACHAT:
		return False, "On n'héberge personne dans une chambre louée."
	if av.get("statut") != "embauche" or av.get("embauche_par") != character.get("_id"):
		return False, "Ce compagnon n'est pas le vôtre."
	if av.get("_id") not in (character.get("groupe") or []):
		return False, "Ce compagnon n'est pas dans votre groupe."
	resident = character.get("residence") == prop.get("_id")
	if occupants(resident, prop) >= capacites(prop, cat)["occupants_max"]:
		return False, "Il n'y a plus de place pour loger quelqu'un ici."
	character["groupe"] = [g for g in character.get("groupe") or [] if g != av["_id"]]
	av["loge_a"] = prop["_id"]
	av.pop("auras_recues", None)   # hors du groupe, plus d'aura
	prop.setdefault("heberges", []).append(av["_id"])
	return True, ""


def heberges_effectifs(character: dict, prop: dict, get_doc_fn=None) -> list:
	lire = get_doc_fn or get_doc
	out = []
	for aid in prop.get("heberges") or []:
		av = lire(aid)
		if (av and av.get("loge_a") == prop.get("_id") and av.get("statut") == "embauche"
				and av.get("embauche_par") == character.get("_id")):
			out.append(av)
	return out


def reprendre(character: dict, prop: dict, av: dict, get_doc_fn=None) -> tuple[bool, str]:
	"""Le compagnon rejoint le groupe — sous le plafond du groupe s'il n'est pas de la
	compagnie (même règle que l'embauche : `places_occupees`)."""
	if av.get("_id") not in (prop.get("heberges") or []) or av.get("loge_a") != prop.get("_id"):
		return False, "Ce compagnon ne loge pas ici."
	if (not av.get("permanent")
			and recrutement.places_occupees(character, get_doc_fn) >= recrutement.taille_max_groupe()):
		return False, "Votre groupe est complet."
	prop["heberges"] = [h for h in prop.get("heberges") or [] if h != av["_id"]]
	av.pop("loge_a", None)
	groupe = character.setdefault("groupe", [])
	if av["_id"] not in groupe:
		groupe.append(av["_id"])
	return True, ""

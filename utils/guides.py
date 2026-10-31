# utils/guides.py
# Guides locaux : des personnages qui connaissent la région, engagés et congédiés à l'auberge.
#
# Un guide est un doc `monture:*` portant le bloc `guide` (`montures.est_guide`) : en combat il
# a le statut d'une monture (immobile, ciblable, mort définitive, cargaison au sol) mais se défend
# au contact comme un paladin d'escorte (`se_defend`) ; au tour de monde il régénère et il porte.
# Ses seules différences passent par `est_guide`.
#
# Le service est PAYÉ D'AVANCE au forfait (X cuivres pour N tours ; un tour = un pas ou une
# attente). Forfait épuisé : il reste mais n'aide plus, son cap tombe ; aucune dette.
#
# LOCALISATION. `rules:guides` décrit chaque métier : où il s'offre (`offre`) et ce qu'il sait
# en plus de son pays (`savoir`). Tout est lu à l'exécution : le doc absent = aucun guide.
#
# Logique pure : DB injectée, mute sans sauver (l'appelant persiste). `random` passe par `rand`.

import os
import random
import re
import time
import uuid

from utils import focalisation
from utils import montures
from utils import quetes
from utils import recrutement
from utils import transport
from utils.characters import lieu_label, tirer_poids

REGLES_ID = "rules:guides"

# Champs utiles d'un lieu : les docs `lieu:*` complets (grilles) sont les plus gros du jeu.
CHAMPS_LIEU = ["_id", "label", "nom", "lieu_parent", "categorie", "sous_categorie",
			   "tags", "rencontres", "ressources"]

CATEGORIES_TEMPLE = ("temple", "temple_portail", "temple_templier")

OBJECTIFS_GUIDABLES = ("chasse", "visite", "escorte", "kill", "collect")


def regles_de(get_doc_fn) -> dict:
	return get_doc_fn(REGLES_ID) or {}


def metier_de(guide: dict, regles: dict) -> dict:
	return ((regles or {}).get("metiers") or {}).get(((guide or {}).get("guide") or {}).get("metier")) or {}


# ── Géographie ───────────────────────────────────────────────────────────────────

def index_lieux(find_docs_fn) -> dict:
	"""{lieu_id: doc réduit à CHAMPS_LIEU}. Lu à l'ouverture d'un panneau, jamais à chaque pas."""
	docs = find_docs_fn({"type": "lieu"}, fields=CHAMPS_LIEU) or []
	return {d["_id"]: d for d in docs if d.get("_id")}


def chaine(lieu_id: str, index: dict) -> list:
	"""Le lieu puis ses ancêtres (borné contre un cycle de données)."""
	sortie, vus = [], set()
	while lieu_id and lieu_id not in vus and lieu_id in index:
		vus.add(lieu_id)
		sortie.append(index[lieu_id])
		lieu_id = index[lieu_id].get("lieu_parent")
	return sortie


def cite_de(lieu_id: str, index: dict) -> dict | None:
	return next((d for d in chaine(lieu_id, index) if d.get("categorie") == "ville"), None)


def zone_de(lieu_id: str, index: dict) -> str:
	"""Ce que le guide connaît d'office : son pays, à défaut sa cité (cités sans pays en base)."""
	docs = chaine(lieu_id, index)
	pays = next((d for d in docs if d.get("categorie") == "pays"), None)
	cite = next((d for d in docs if d.get("categorie") == "ville"), None)
	return (pays or cite or {}).get("_id") or lieu_id


def traits_cite(lieu_id: str, index: dict) -> set:
	"""Traits DÉRIVÉS à la lecture : `port` (un quai ou le tag), `donjon` (un temple dans la
	cité), et tout tag du lieu ou de ses ancêtres (`montagne`, `contrebande`…).

	⚠️ `donjon` passe par le TEMPLE : les lieux de donjon en base n'ont pas de `lieu_parent` (14
	sur 14 au dump du 31/10), et un temple est par définition la forteresse bâtie autour d'un
	portail de donjon. Lutecia, Auxerre, Chartres l'ont ; Rhemi, sans portail, non."""
	traits = set()
	for d in chaine(lieu_id, index):
		traits.update(d.get("tags") or [])
	cite = cite_de(lieu_id, index)
	if cite:
		for d in index.values():
			if d.get("lieu_parent") != cite["_id"]:
				continue
			if d.get("categorie") == "quai":
				traits.add("port")
			if d.get("categorie") in CATEGORIES_TEMPLE or "donjon" in (d.get("tags") or []):
				traits.add("donjon")
	return traits


def metier_disponible(metier: dict, lieu_id: str, index: dict) -> bool:
	offre = (metier or {}).get("offre") or {}
	if offre.get("partout"):
		return True
	if set(offre.get("pays") or []) & {d["_id"] for d in chaine(lieu_id, index)}:
		return True
	if set(offre.get("traits") or []) & traits_cite(lieu_id, index):
		return True
	cite = cite_de(lieu_id, index) or {}
	return cite.get("sous_categorie") in (offre.get("sous_categories") or [])


def metiers_offerts(lieu_id: str, index: dict, regles: dict) -> list:
	"""Ids des métiers qu'une auberge peut proposer ici, dans l'ordre du catalogue."""
	return [mid for mid, m in ((regles or {}).get("metiers") or {}).items()
			if metier_disponible(m, lieu_id, index)]


def connait(guide: dict, lieu_id: str, index: dict, regles: dict) -> bool:
	"""Le lieu est-il dans son pays, ou dans ce que son métier lui apprend ?"""
	doc = index.get(lieu_id)
	if not doc:
		return False
	zone = (guide.get("guide") or {}).get("zone")
	if zone and any(d.get("_id") == zone for d in chaine(lieu_id, index)):
		return True
	savoir = metier_de(guide, regles).get("savoir") or {}
	return (doc.get("categorie") in (savoir.get("categories") or [])
			or bool(set(savoir.get("tags") or []) & set(doc.get("tags") or [])))


# ── Génération et tableau ────────────────────────────────────────────────────────

def equipement_de(metier: dict, get_doc_fn, rand=random) -> dict:
	"""Slots portés par un guide de ce métier (`metier.equipement` = {slot: item_id}), poids
	d'instance tiré. Un objet disparu du catalogue laisse le slot vide, sans bloquer l'offre."""
	slots = {}
	for slot, item_id in ((metier or {}).get("equipement") or {}).items():
		doc = get_doc_fn(item_id) if get_doc_fn else None
		if doc:
			slots[slot] = {"item": item_id, "poids": tirer_poids(doc, rand.random)}
	return slots


PORTRAIT_GUIDE = re.compile(r"^guide_(.+)_([mf])_([a-z]+?)\d*\.(?:jpe?g|png|webp)$")


def portraits_guide_disponibles() -> list:
	"""Portraits propres aux guides : `pnj/guide_<type>_<sexe>_<lignée>NN.ext`."""
	dossier = os.path.join(os.path.dirname(__file__), "..", "templates", "resources", "pnj")
	try:
		return [f for f in os.listdir(dossier) if f.lower().startswith("guide_")]
	except OSError:
		return []


def choisir_portrait_guide(metier_id: str, metier: dict, sex: str, race: str, portraits: list,
						   rand=random) -> str:
	"""Portrait du type de ce guide, sexe et Lignée stricts ; le type du fichier est
	`metier.portrait`, à défaut l'id du métier. Chaîne vide si aucun ne convient."""
	cible = ((metier or {}).get("portrait") or metier_id, (sex or "M").lower(), (race or "").lower())
	pool = [p for p in portraits or []
			if (m := PORTRAIT_GUIDE.match(p.lower())) and m.groups() == cible]
	return rand.choice(pool) if pool else ""


def generer_guide(metier_id: str, lieu_doc: dict, index: dict, regles: dict, races: list,
				  portraits: list, rand=random, get_doc_fn=None, portraits_guide=()) -> dict | None:
	"""Doc d'une offre. Portrait propre au type (`portraits_guide`), sinon la règle des recrues
	(visage juste ou rien) ; équipement selon le métier (⚠️ PORTÉ pour se défendre : il ne le
	cède pas au joueur)."""
	metier = ((regles or {}).get("metiers") or {}).get(metier_id)
	if not metier or not races:
		return None
	race = rand.choice(races)
	sex = rand.choice(["M", "F"])
	caract = dict(race.get("stats", {}))
	recrutement._repartir_points(caract, race.get("stats_max", {}), 10)
	race_id = race.get("id", "")
	now = int(time.time())
	lieu_id = (lieu_doc or {}).get("_id", "")
	guide = {
		"_id": f"monture:guide_{uuid.uuid4().hex[:12]}",
		"type": "monture",
		"statut": "offert",
		"giver": lieu_id,
		"lieu_parent": (lieu_doc or {}).get("lieu_parent"),
		"espece": "",
		"prenom": rand.choice(recrutement.prenoms_possibles(race_id, sex)),
		"nom": rand.choice(recrutement.NOMS.get(race_id, recrutement.NOMS["defaut"])),
		"race": race_id,
		"sex": sex,
		"image": (choisir_portrait_guide(metier_id, metier, sex, race_id, portraits_guide, rand)
				  or recrutement.choisir_portrait(metier.get("portrait_voc", ""), sex, race_id, portraits)),
		"caracteristiques_current": caract,
		"currentPV": 0,
		"currentPM": 0,
		"inventaire": [],
		"slots": equipement_de(metier, get_doc_fn, rand),
		"equipment_bonus": {},
		"competences_bonus": {},
		"effets_actifs": [],
		"combats_recompenses": [],
		"jouable": False,
		"genere_at": now,
		"expire_at": now + int((regles or {}).get("duree_offre_secondes", 0) or 0),
		"guide": {"metier": metier_id, "zone": zone_de(lieu_id, index), "tours_restants": 0},
	}
	derives = montures._derives_de(guide)
	guide["currentPV"] = derives.pv_max
	guide["currentPM"] = derives.pm_max
	return guide


def remplir_tableau(lieu_doc: dict, index: dict, regles: dict, races: list, portraits: list,
					find_docs_fn, save_doc_fn, delete_doc_fn, now: int | None = None, rand=random,
					get_doc_fn=None, portraits_guide=()) -> list:
	"""Purge les offres périmées puis complète jusqu'à `tableau_nb`, en variant les métiers.
	Une offre est partagée entre joueurs, comme une recrue au tableau de la guilde."""
	now = int(time.time()) if now is None else now
	lieu_id = (lieu_doc or {}).get("_id")
	offres = []
	for d in find_docs_fn({"type": "monture", "giver": lieu_id, "statut": "offert"}) or []:
		if now >= int(d.get("expire_at") or 0):
			delete_doc_fn(d)
		else:
			offres.append(d)
	metiers = metiers_offerts(lieu_id, index, regles)
	manque = int((regles or {}).get("tableau_nb", 0) or 0) - len(offres)
	if not metiers or manque <= 0:
		return offres
	presents = {(o.get("guide") or {}).get("metier") for o in offres}
	sac = [m for m in metiers if m not in presents] or list(metiers)
	rand.shuffle(sac)
	for i in range(manque):
		guide = generer_guide(sac[i % len(sac)], lieu_doc, index, regles, races, portraits, rand, get_doc_fn,
							  portraits_guide)
		if guide and save_doc_fn(guide) is not None:
			offres.append(guide)
	return offres


# ── Contrat ──────────────────────────────────────────────────────────────────────

def guide_de(character: dict, get_doc_fn) -> dict | None:
	return next((m for m in montures.montures_effectives(character, get_doc_fn)
				 if montures.est_guide(m)), None)


def tours_restants(guide: dict) -> int:
	return max(0, int(((guide or {}).get("guide") or {}).get("tours_restants", 0) or 0))


def actif(guide: dict) -> bool:
	"""Seule source de l'état « épuisé » : dérivé, jamais stocké."""
	return tours_restants(guide) > 0


def forfait(metier: dict) -> tuple[int, int]:
	"""(cuivres, tours) du forfait d'un métier."""
	return (max(0, int((metier or {}).get("forfait_cuivre", 0) or 0)),
			max(0, int((metier or {}).get("forfait_tours", 0) or 0)))


def vue_contrat(guide: dict, regles: dict) -> dict:
	metier = metier_de(guide, regles)
	cout, tours = forfait(metier)
	return {"metier_label": metier.get("label", ""), "forfait_cuivre": cout, "forfait_tours": tours,
			"tours_restants": tours_restants(guide), "epuise": not actif(guide)}


def ajouter_forfait(guide: dict, regles: dict) -> int:
	"""Crédite les tours d'un forfait (renouveler avant la fin cumule). Le débit reste à
	l'appelant, après ses gardes. Renvoie les tours restants."""
	_, tours = forfait(metier_de(guide, regles))
	guide["guide"]["tours_restants"] = tours_restants(guide) + tours
	return tours_restants(guide)


def engager(character: dict, guide: dict, regles: dict) -> tuple[bool, str]:
	if guide.get("statut") != "offert" or not montures.est_guide(guide):
		return False, "Ce guide n'est plus disponible."
	ok, raison = montures.acquerir(character, guide)
	if not ok:
		return False, raison
	guide.pop("expire_at", None)
	ajouter_forfait(guide, regles)
	return True, ""


def congedier(character: dict, guide: dict) -> tuple[bool, str]:
	"""Rend sa liberté au guide. La garde « dans une auberge » est au router. Aucun remboursement."""
	if guide.get("inventaire"):
		return False, "Videz son sac avant de le congédier."
	focalisation.effacer_si_guide(character, guide.get("_id"))
	guide["statut"] = "parti"
	guide.pop("acquise_par", None)
	guide.pop("auras_recues", None)
	character["montures"] = [m for m in character.get("montures") or [] if m != guide.get("_id")]
	return True, ""


def decompter_tour(character: dict, compagnons_montures: list, regles_fn) -> dict | None:
	"""Un tour de monde : retire un tour au guide qui accompagne le personnage. Mute le guide
	(sauvé par `_apply_world_turn_groupe`) et le character (cap retiré à l'épuisement, sauvé par
	l'appelant). Renvoie {"tours_restants", "alerte": "epuise"|"bientot"|None}, ou None sans guide.
	`regles_fn` est paresseux : un joueur sans guide ne lit rien de plus."""
	guide = next((m for m in compagnons_montures or [] if montures.est_guide(m)), None)
	if guide is None:
		return None
	avant = tours_restants(guide)
	apres = max(0, avant - 1)
	guide["guide"]["tours_restants"] = apres
	alerte = None
	if avant and not apres:
		focalisation.effacer_si_guide(character, guide.get("_id"))
		alerte = "epuise"
	elif apres and apres == int((regles_fn() or {}).get("seuil_alerte_tours", 0) or 0):
		alerte = "bientot"
	return {"tours_restants": apres, "alerte": alerte}


# ── Ce que le guide sait ─────────────────────────────────────────────────────────

def lieux_de_cible(obj: dict, index: dict, q: dict | None = None) -> list:
	"""Lieux où une quête se joue. Chasse, visite, escorte le disent ; pour kill et collect on
	cherche la cible dans les `rencontres`/`ressources`, mêmes champs que `boost_zone_event`,
	repli carcasse → espèce compris."""
	t, cible = obj.get("type"), obj.get("cible")
	if t == "chasse":
		return [obj["lieu"]] if obj.get("lieu") else []
	if t == "visite":
		return [cible] if cible else []
	if t == "escorte":
		rdv = (obj.get("rencontre") or {}).get("lieu")
		if rdv and not (q or {}).get("rencontre_at"):
			return [rdv]
		return [cible] if cible else []
	if t == "kill":
		return [i for i, d in index.items()
				if any(e.get("espece") == cible for e in d.get("rencontres") or [])]
	if t == "collect":
		recolte = [i for i, d in index.items()
				   if any(e.get("ressource") == cible for e in d.get("ressources") or [])]
		if recolte:
			return recolte
		espece = focalisation._espece_de_carcasse(cible or "")
		return [i for i, d in index.items()
				if espece and any(e.get("espece") == espece for e in d.get("rencontres") or [])]
	return []


def piste_quete(q: dict, guide: dict, depuis: str, index: dict, graphe: dict, regles: dict) -> dict | None:
	"""{lieu, distance} : le lieu le plus proche, connu de ce guide, joignable, où cette quête
	se joue. Ex æquo : l'ordre d'id, pour que deux questions de suite donnent la même réponse."""
	obj = (q or {}).get("objectif") or {}
	if obj.get("type") not in OBJECTIFS_GUIDABLES:
		return None
	distances = focalisation.distances_depuis(graphe, depuis)
	candidats = [(distances[lid], lid) for lid in lieux_de_cible(obj, index, q)
				 if lid in distances and connait(guide, lid, index, regles)]
	if not candidats:
		return None
	distance, lieu = min(candidats)
	return {"lieu": lieu, "distance": distance}


def sujets(character: dict, guide: dict, index: dict, graphe: dict, regles: dict) -> list:
	"""Les quêtes actives sur lesquelles on peut l'interroger, avec ou sans piste : il doit
	pouvoir répondre « ça, je ne connais pas » plutôt que de faire disparaître la quête."""
	sortie = []
	for q in character.get("quetes_actives") or []:
		if (q.get("objectif") or {}).get("type") not in OBJECTIFS_GUIDABLES:
			continue
		if quetes.objectif_atteint(character, q):
			continue
		piste = piste_quete(q, guide, character.get("lieu"), index, graphe, regles)
		sortie.append({
			"quete_id": q.get("id"),
			"titre": q.get("titre", ""),
			"connu": bool(piste),
			"ici": bool(piste) and piste["distance"] == 0,
		})
	return sortie


def lieux_connus(guide: dict, index: dict, regles: dict) -> list:
	"""[(lieu_id, libellé)] des lieux qu'il sait nommer, pour la question libre."""
	return [(i, lieu_label(d, i)) for i, d in index.items() if connait(guide, i, index, regles)]


def poser_cap(character: dict, guide: dict, lieu_id: str, quete_id: str | None = None) -> None:
	"""Le cap du guide : le `type:"lieu"` de toujours, signé. Remplace toute focalisation."""
	f = {"type": "lieu", "cible": lieu_id, "posee_at": int(time.time()), "guide": guide["_id"]}
	if quete_id:
		f["puis_quete"] = quete_id
	character["focalisation"] = f


def replique(guide: dict, regles: dict, cle: str, **valeurs) -> str:
	"""Réplique du métier, sinon commune. Placeholders tolérés absents (donnée éditable)."""
	metier = metier_de(guide, regles)
	gabarit = (metier.get("repliques") or {}).get(cle) or ((regles or {}).get("repliques") or {}).get(cle) or ""
	for k, v in valeurs.items():
		gabarit = gabarit.replace("{" + k + "}", str(v))
	return gabarit

# utils/renseignement.py
# 🔎 SE RENSEIGNER (pur) : un membre du groupe dont la vocation a une MÉTHODE dans ce lieu
# apprend OÙ trouver une espèce ou une ressource. Compétence `telluris-renseignement`.
#
# Aucune piste n'est écrite à la main : la réponse se DÉRIVE à la lecture des sources du monde
# (`rencontres` / `ressources` des lieux et leurs zones, salles de donjon, rayons des boutiques).
# Le doc `rules:renseignement` ne dit que QUI demande, OÙ, à quel PRIX et sur quelles CIBLES.
#
# Logique pure (Convention §2) : DB injectée, mute sans sauver (l'appelant persiste), hasard par
# `rand` (objet `random.Random`-like : `random()`, `randint`, `choices`). World-vars lues VIA le
# module `character_stats`, jamais en `from … import`.

import random
import re
import time

from models import character_stats
from utils.characters import lieu_label

REGLES_ID = "rules:renseignement"
ITEM_NOTE_ID = "item:note_renseignement"
SOUS_CATEGORIE_NOTE = "note_renseignement"

# Clés de caractéristique d'une méthode → clé de `caracteristiques_current`. ⚠️ Une clé hors de
# cette table REFUSE la méthode à la lecture (`normaliser_methode`) : jamais un 0 silencieux.
CLES_CARACS = {"v": "V", "f": "F", "r": "R", "ag": "Ag", "vol": "Vol", "int": "Int", "cha": "Cha", "ch": "Ch"}
NIVEAUX = ("rumeur", "region", "exact")
SOURCES = ("lieu", "zone", "donjon", "boutique")
PREDICATS = ("taverne", "scriptorium", "salle_d_armes", "sauvage", "pays")
# Modes « du coin » (salle commune de guilde) : bornés au PAYS de la cité de la guilde.
MODES_COIN = ("dangers", "donjons", "ressources")
MODES_CIBLE = ("quete", "bestiaire", "libre", "hasard", "recit") + MODES_COIN
# Interlocuteurs de guilde : l'acteur n'est pas un membre du groupe mais un PNJ du lieu —
# chaque recrue du tableau (réception), le réceptionniste (comptoir, ouvert par son dialogue).
INTERLOCUTEURS = ("recrue", "receptionniste")
# Types de quête dont la cible est un LIEU (rendez-vous, destination) : piste `lieu`.
OBJECTIFS_LIEU = ("visite", "escorte", "transport")

# Une salle d'armes : catégories d'armurerie OU tag `salle_d_armes`. ⚠️ Recopié dans
# `utils/capacites.py` (verrouillé par tests/test_capacites.py) : modifier l'un, c'est modifier l'autre.
CATEGORIES_SALLE_D_ARMES = ("armurerie", "grand_arsenal")
TAG_SALLE_D_ARMES = "salle_d_armes"

SEUIL_MIN, SEUIL_MAX = 5, 95          # idiome des jets d100 du jeu (pieges.seuil_detection)
LIBELLE_NIVEAU = {"rumeur": "rumeur", "region": "région", "exact": "lieu exact"}

# Terrain d'une rumeur : premier tag reconnu du lieu ou de la zone → tournure.
TERRAINS = {
	"foret": "du côté des forêts", "bois": "du côté des bois", "foret_dense": "au cœur des forêts",
	"montagne": "vers les montagnes", "gorge": "au fond des gorges", "lande": "sur les landes",
	"desert": "dans les sables", "erg": "dans les sables", "marais": "dans les marais",
	"humide": "dans les terres humides", "eau": "au bord de l'eau", "lac": "au bord d'un lac",
	"fleuve": "le long du fleuve", "delta": "dans le delta", "mer": "du côté de la mer",
	"cote": "sur la côte", "ruines": "parmi des ruines", "souterrain": "sous terre",
	"sous-terrain": "sous terre", "grotte": "dans des grottes", "catacombe": "dans les catacombes",
	"crypte": "dans une crypte", "ville": "en ville", "urbain": "en ville", "champ": "dans les champs",
	"plaine": "dans les plaines", "colline": "dans les collines", "clairiere": "dans une clairière",
	"donjon": "au fond d'un donjon",
}


def now_epoch() -> int:
	return int(time.time())


def lancer(notation, rand=random) -> int:
	"""« 1D6 », « 2D6+1 », « 3 » → entier ≥ 0. Local : `combat.roll_dice` tirerait tout le moteur."""
	texte = str(notation or "0").replace(" ", "").upper()
	m = re.fullmatch(r"(\d*)D(\d+)([+-]\d+)?", texte)
	if not m:
		try:
			return max(0, int(texte))
		except ValueError:
			return 0
	n, faces, bonus = int(m.group(1) or 1), int(m.group(2)), int(m.group(3) or 0)
	return max(0, sum(rand.randint(1, faces) for _ in range(n)) + bonus) if faces > 0 else max(0, bonus)


# ── Règles ───────────────────────────────────────────────────────────────────────

def regles_de(get_doc_fn) -> dict:
	return get_doc_fn(REGLES_ID) or {}


def normaliser_methode(raw: dict) -> dict:
	"""Vue normalisée d'une méthode. ⚠️ LÈVE `ValueError` sur une clé de caractéristique, un
	prédicat, une source ou un niveau inconnus : une coquille ne doit jamais valoir 0."""
	m = dict(raw or {})
	if not m.get("id"):
		raise ValueError("méthode sans id")
	test = [str(c).strip().lower() for c in (m.get("test") or [])]
	inconnues = [c for c in test if c not in CLES_CARACS]
	if inconnues:
		raise ValueError(f"{m['id']} : caractéristique(s) inconnue(s) {inconnues} — clés admises {sorted(CLES_CARACS)}")
	lieu = dict(m.get("lieu") or {})
	preds = [str(p) for p in (lieu.get("predicats") or [])]
	if [p for p in preds if p not in PREDICATS]:
		raise ValueError(f"{m['id']} : prédicat de lieu inconnu {preds}")
	sources = [str(s) for s in (m.get("sources") or SOURCES)]
	if [s for s in sources if s not in SOURCES]:
		raise ValueError(f"{m['id']} : source inconnue {sources}")
	niveau_fixe = m.get("niveau_fixe") or None
	if niveau_fixe and niveau_fixe not in NIVEAUX:
		raise ValueError(f"{m['id']} : niveau_fixe inconnu {niveau_fixe}")
	niveau_max = m.get("niveau_max") or "exact"
	if niveau_max not in NIVEAUX:
		raise ValueError(f"{m['id']} : niveau_max inconnu {niveau_max}")
	modes = [str(x) for x in (m.get("modes") or ("quete", "bestiaire", "libre", "hasard"))]
	if [x for x in modes if x not in MODES_CIBLE]:
		raise ValueError(f"{m['id']} : mode de cible inconnu {modes}")
	cibles = dict(m.get("cibles") or {})
	interlocuteur = m.get("interlocuteur") or None
	if interlocuteur and interlocuteur not in INTERLOCUTEURS:
		raise ValueError(f"{m['id']} : interlocuteur inconnu {interlocuteur}")
	return {
		"interlocuteur": interlocuteur,
		"via_pnj": bool(m.get("via_pnj")),
		"id": str(m["id"]),
		"nom": str(m.get("nom") or m["id"]),
		"icon": str(m.get("icon") or "🔎"),
		"vocations": [str(v) for v in (m.get("vocations") or [])],
		"informateur": bool(m.get("informateur")),
		"lieu": {"predicats": preds,
				 "categories": [str(c) for c in (lieu.get("categories") or [])],
				 "tags": [str(t) for t in (lieu.get("tags") or [])]},
		"test": test,
		"cout": max(0, int(m.get("cout") or 0)),
		"cout_pv": m.get("cout_pv") or None,
		"cout_pm": max(0, int(m.get("cout_pm") or 0)),
		"connait": m.get("connait") or None,
		"sources": sources,
		"portee_max": None if m.get("portee_max") is None else max(0, int(m["portee_max"])),
		"cibles": {
			"especes": bool(cibles.get("especes", True)),
			"ressources": bool(cibles.get("ressources", True)),
			"tags_espece": [str(t) for t in (cibles.get("tags_espece") or [])],
			"sous_categories": [str(s) for s in (cibles.get("sous_categories") or [])],
			"ecole_vocation": bool(cibles.get("ecole_vocation")),
			"grade_min": cibles.get("grade_min") or None,
			"elites": bool(cibles.get("elites")),
		},
		"modes": modes,
		"niveau_fixe": niveau_fixe,
		"niveau_max": niveau_max,
		"note": bool(m.get("note")),
		"pourboire": bool(m.get("pourboire")),
		"repliques": dict(m.get("repliques") or {}),
	}


def methodes_de(regles: dict) -> tuple[list, list]:
	"""(méthodes valides, erreurs). Une méthode invalide est ÉCARTÉE et nommée dans `erreurs`."""
	valides, erreurs = [], []
	for raw in (regles or {}).get("methodes") or []:
		try:
			valides.append(normaliser_methode(raw))
		except (ValueError, TypeError) as e:
			erreurs.append(str(e))
	return valides, erreurs


def tags_nature(regles: dict) -> set:
	return set((regles or {}).get("tags_nature") or [])


# ── Lieux ────────────────────────────────────────────────────────────────────────

def chaine(lieu_id: str, index: dict) -> list:
	sortie, vus = [], set()
	while lieu_id and lieu_id not in vus and lieu_id in index:
		vus.add(lieu_id)
		sortie.append(index[lieu_id])
		lieu_id = index[lieu_id].get("lieu_parent")
	return sortie


def cite_de(lieu_id: str, index: dict) -> dict | None:
	return next((d for d in chaine(lieu_id, index) if d.get("categorie") == "ville"), None)


def region_de(lieu_id: str, index: dict) -> dict | None:
	"""Premier ancêtre NOTABLE (lui compris) : la cité, sinon la carte de pays, sinon le lieu."""
	docs = chaine(lieu_id, index)
	return (next((d for d in docs if d.get("categorie") == "ville"), None)
			or next((d for d in docs if d.get("categorie") == "pays"), None)
			or (docs[0] if docs else None))


def lieu_salle_d_armes(lieu_doc: dict | None) -> bool:
	if not lieu_doc:
		return False
	return (lieu_doc.get("categorie") in CATEGORIES_SALLE_D_ARMES
			or TAG_SALLE_D_ARMES in (lieu_doc.get("tags") or []))


def est_sauvage(lieu_doc: dict | None, index: dict, nature: set) -> bool:
	"""Zone sauvage = carte de pays OU tag nature OU lieu à rencontres/ressources OU hors cité."""
	if not lieu_doc:
		return False
	return (lieu_doc.get("categorie") == "pays"
			or bool(set(lieu_doc.get("tags") or []) & nature)
			or bool(lieu_doc.get("rencontres") or lieu_doc.get("ressources"))
			or cite_de(lieu_doc.get("_id", ""), index) is None)


def predicat_ok(nom: str, lieu_doc: dict, index: dict, nature: set) -> bool:
	if nom == "taverne":
		from utils import auberge
		return auberge.lieu_est_taverne(lieu_doc)
	if nom == "scriptorium":
		# Prédicat recopié de `scriptorium.lieu_est_scriptorium` sans en tirer les imports
		# (`marche`) : un OU catégorie/tag, verrouillé par test_renseignement.
		return lieu_doc.get("categorie") == "scriptorium" or "scriptorium" in (lieu_doc.get("tags") or [])
	if nom == "salle_d_armes":
		return lieu_salle_d_armes(lieu_doc)
	if nom == "sauvage":
		return est_sauvage(lieu_doc, index, nature)
	if nom == "pays":
		return lieu_doc.get("categorie") == "pays"
	return False


def lieu_ok(methode: dict, lieu_doc: dict | None, index: dict, nature: set) -> bool:
	"""La méthode s'exerce-t-elle ici ? OU entre prédicats, catégories et tags."""
	if not lieu_doc:
		return False
	l = methode["lieu"]
	return (any(predicat_ok(p, lieu_doc, index, nature) for p in l["predicats"])
			or lieu_doc.get("categorie") in l["categories"]
			or bool(set(l["tags"]) & set(lieu_doc.get("tags") or [])))


# ── Acteur et seuil ──────────────────────────────────────────────────────────────

def caracts_de(membre: dict) -> dict:
	from utils.consommables import caracts_avec_buffs
	return caracts_avec_buffs(membre)


def bonus_relation(relation_value: int | None) -> int:
	if relation_value is None:
		return 0
	borne = int(character_stats.RENS_RELATION_MAX)
	brut = round((int(relation_value) - int(character_stats.RELATION_INITIALE))
				 * float(character_stats.RENS_RELATION_POIDS))
	return max(-borne, min(borne, brut))


def seuil(methode: dict, membre: dict, relation_value: int | None = None) -> int:
	"""50 + moyenne des caractéristiques testées + bonus de relation, borné à [5, 95]."""
	caracts = caracts_de(membre)
	vals = [int(caracts.get(CLES_CARACS[c], 0) or 0) for c in methode["test"]]
	moyenne = round(sum(vals) / len(vals)) if vals else 0
	return max(SEUIL_MIN, min(SEUIL_MAX, 50 + moyenne + bonus_relation(relation_value)))


def membre_eligible(methode: dict, membre: dict, connait_fn) -> bool:
	if (membre or {}).get("voc") not in methode["vocations"]:
		return False
	if methode["connait"] and not connait_fn(membre, methode["connait"]):
		return False
	return True


def methode_de_vocation(voc: str, methodes: list) -> dict | None:
	"""La première méthode de cette vocation (ordre du doc) — le métier d'une recrue."""
	return next((m for m in methodes if voc in m["vocations"] and not m["interlocuteur"]), None)


def applicables(lieu_doc: dict | None, index: dict, membres: list, regles: dict, connait_fn,
				relation_value: int | None = None, informateur_present: bool = False,
				interlocuteurs: dict | None = None) -> list:
	"""[{methode, acteur, seuil, cle, interlocuteur}] des méthodes exerçables ici, dans l'ordre
	du doc. Acteur = le membre éligible au plus haut seuil ; ex æquo : le premier (principal EN
	TÊTE). Méthode à `interlocuteur` : une entrée PAR PNJ de `interlocuteurs[type]` (recrue :
	seuil de SA vocation sur SES caracs ; réceptionniste : Cha du JOUEUR). Sans aucune méthode
	de vocation, l'informateur de taverne (s'il est là) prend le relais. `cle` = identité de
	l'entrée (méthode, ou méthode|PNJ) : c'est elle qui porte le délai."""
	methodes, _ = methodes_de(regles)
	nature = tags_nature(regles)
	sortie = []
	for m in methodes:
		if m["informateur"] or not lieu_ok(m, lieu_doc, index, nature):
			continue
		if m["interlocuteur"]:
			for pnj in (interlocuteurs or {}).get(m["interlocuteur"]) or []:
				if m["interlocuteur"] == "recrue":
					metier = methode_de_vocation(pnj.get("voc"), methodes) or m
					s = seuil(metier, pnj)
				else:
					s = seuil(m, membres[0], relation_value) if membres else SEUIL_MIN
				sortie.append({"methode": m, "acteur": pnj, "seuil": s, "interlocuteur": pnj,
							   "cle": f"{m['id']}|{pnj.get('_id')}"})
			continue
		meilleur = None
		for membre in membres or []:
			if not membre_eligible(m, membre, connait_fn):
				continue
			s = seuil(m, membre, relation_value)
			if meilleur is None or s > meilleur["seuil"]:
				meilleur = {"methode": m, "acteur": membre, "seuil": s, "interlocuteur": None, "cle": m["id"]}
		if meilleur:
			sortie.append(meilleur)
	if not any(not a["interlocuteur"] for a in sortie) and informateur_present:
		for m in methodes:
			if m["informateur"] and lieu_ok(m, lieu_doc, index, nature) and membres:
				sortie.append({"methode": m, "acteur": membres[0], "interlocuteur": None, "cle": m["id"],
							   "seuil": seuil(m, membres[0], relation_value)})
				break
	return sortie


def poser_informateur(character: dict, lieu_doc: dict | None, regles: dict, index: dict,
					  rand=random) -> bool:
	"""Champ transitoire `informateur_present` tiré à l'ENTRÉE d'un lieu où une méthode
	d'informateur s'exerce (sémantique de `pnj.poser_pnj_present` : no-op tant qu'on reste dans
	le même lieu, re-tiré en revenant). Renvoie True si le champ a changé."""
	lieu_id = (lieu_doc or {}).get("_id")
	if not lieu_id:
		return False
	actuel = character.get("informateur_present") or {}
	if actuel.get("lieu") == lieu_id:
		return False
	methodes, _ = methodes_de(regles)
	nature = tags_nature(regles)
	possible = any(m["informateur"] and lieu_ok(m, lieu_doc, index, nature) for m in methodes)
	if not possible:
		if actuel:
			character.pop("informateur_present", None)
			return True
		return False
	character["informateur_present"] = {
		"lieu": lieu_id,
		"present": rand.random() < float(character_stats.RENS_INFORMATEUR_PROBA),
	}
	return True


def informateur_ici(character: dict, lieu_id: str) -> bool:
	actuel = (character or {}).get("informateur_present") or {}
	return actuel.get("lieu") == lieu_id and bool(actuel.get("present"))


# ── Délai ────────────────────────────────────────────────────────────────────────

def _cle_delai(lieu_id: str, methode_id: str) -> str:
	return f"{lieu_id}|{methode_id}"


def disponible_dans(character: dict, lieu_id: str, methode_id: str, now: int | None = None) -> int:
	"""Secondes avant la prochaine recherche (0 = maintenant)."""
	instant = now_epoch() if now is None else int(now)
	at = ((character or {}).get("renseignements_at") or {}).get(_cle_delai(lieu_id, methode_id))
	if not at:
		return 0
	return max(0, int(at) + int(character_stats.RENS_DELAI_MINUTES) * 60 - instant)


def marquer_delai(character: dict, lieu_id: str, methode_id: str, now: int | None = None) -> None:
	"""Horodate la recherche ; les entrées échues sont purgées au passage (Convention §5)."""
	instant = now_epoch() if now is None else int(now)
	duree = int(character_stats.RENS_DELAI_MINUTES) * 60
	ats = {k: v for k, v in ((character.get("renseignements_at") or {}).items())
		   if int(v or 0) + duree > instant}
	ats[_cle_delai(lieu_id, methode_id)] = instant
	character["renseignements_at"] = ats


# ── Coûts ────────────────────────────────────────────────────────────────────────

def cout_cuivre(methode: dict, niveau: str) -> int:
	base = methode["cout"] * (float(character_stats.RENS_INFORMATEUR_MULT) if methode["informateur"] else 1.0)
	mult = float((character_stats.RENS_COUT_MULT or {}).get(niveau, 1.0))
	return max(0, round(base * mult))


def cout_max(methode: dict) -> int:
	"""Ce qu'une recherche peut coûter au pire : la bourse doit le couvrir AVANT le jet."""
	niveaux = [n for n in NIVEAUX if NIVEAUX.index(n) <= NIVEAUX.index(methode["niveau_max"])]
	if methode["niveau_fixe"]:
		niveaux = [methode["niveau_fixe"], "rumeur"]
	return max(cout_cuivre(methode, n) for n in niveaux)


def cout_pm(methode: dict, get_doc_fn) -> int:
	"""PM fixés par la méthode, sinon ceux de la compétence exigée (`connait`)."""
	if methode["cout_pm"]:
		return methode["cout_pm"]
	if methode["connait"]:
		return max(0, int((get_doc_fn(methode["connait"]) or {}).get("cout_pm") or 0))
	return 0


# ── Cibles ───────────────────────────────────────────────────────────────────────

RANGS = ["F", "E", "D", "C", "B", "A", "S", "S+"]   # = recrutement.RANGS (importer tirerait marche)


def rang_index(rang: str | None) -> int:
	return RANGS.index(rang) if rang in RANGS else -1


def items_d_ecole(voc: str, rules_vocations, find_docs_fn) -> set:
	"""Composants des sorts de l'école de cette vocation — DÉRIVÉS, jamais recopiés."""
	from utils import sorts
	ecole = sorts.ecole_native(voc, rules_vocations)
	if not ecole:
		return set()
	sortie = set()
	for s in find_docs_fn({"type": "sort"}) or []:
		if sorts.magie_de_sort(s, rules_vocations) == ecole:
			sortie.update(c.get("item") for c in (s.get("composants") or []) if c.get("item"))
	return sortie


def cible_ok(methode: dict, cible_id: str, doc: dict | None, rang_fn=None, ecole_items: set | None = None) -> bool:
	"""Le filtre de cibles de la méthode accepte-t-il cette espèce / cette matière ?"""
	c = methode["cibles"]
	if doc is None:
		return False
	if cible_id.startswith("espece:"):
		if not c["especes"]:
			return False
		if c["tags_espece"] and not (set(c["tags_espece"]) & set(doc.get("tags") or [])):
			return False
		if c["grade_min"] and rang_fn is not None and rang_index(rang_fn(cible_id)) < rang_index(c["grade_min"]):
			return False
		return True
	if cible_id.startswith("item:"):
		if not c["ressources"]:
			return False
		filtres = bool(c["sous_categories"]) or c["ecole_vocation"]
		if not filtres:
			return True
		sc = doc.get("sous_categorie") or doc.get("categorie")
		return (sc in c["sous_categories"]) or (c["ecole_vocation"] and cible_id in (ecole_items or set()))
	return False


def cible_quete(q: dict) -> str | None:
	obj = (q or {}).get("objectif") or {}
	if obj.get("type") in ("kill", "collect", "chasse"):
		return obj.get("cible")
	return None


def cles_bestiaire(character: dict) -> set:
	"""{(espèce, lieu)} déjà au bestiaire (vu OU ouï-dire)."""
	sortie = set()
	for eid, fiche in ((character or {}).get("bestiaire") or {}).items():
		for l in (fiche or {}).get("lieux") or []:
			if l.get("id"):
				sortie.add((eid, l["id"]))
	return sortie


def recits_cedables(character: dict, taverne_id: str) -> list:
	"""Paires (espèce, lieu) VUES au bestiaire et pas encore cédées dans cette taverne."""
	cedes = set(((character or {}).get("recits_cedes") or {}).get(taverne_id) or [])
	sortie = []
	for eid, fiche in ((character or {}).get("bestiaire") or {}).items():
		for l in (fiche or {}).get("lieux") or []:
			if l.get("id") and not l.get("oui_dire") and f"{eid}|{l['id']}" not in cedes:
				sortie.append({"espece": eid, "lieu": l["id"], "label": l.get("label") or ""})
	return sortie


# ── Sources ──────────────────────────────────────────────────────────────────────

def _entrees(lieu: dict, champ: str, cle: str, cible: str) -> list:
	return [e for e in (lieu.get(champ) or []) if e.get(cle) == cible]


def _carcasse_vers_espece(item_id: str) -> str:
	return "espece:" + item_id[len("item:"):] if item_id.startswith("item:") else ""


def pistes_de(cible_id: str, sources: list, index: dict, donjons: list, boutiques: list) -> list:
	"""Toutes les pistes du monde pour cette cible, sans portée.
	Une piste = {type, porteur (lieu mesuré), lieu, zone?, donjon?, cible}. `boutiques` = docs lieu
	réduits portant `stock_vente`. Une matière sans récolte retombe sur l'espèce source (carcasse),
	comme `guides.lieux_de_cible`."""
	pistes = []
	especes, items = [], []
	if cible_id.startswith("espece:"):
		especes = [cible_id]
	elif cible_id.startswith("item:"):
		items = [cible_id]
	for lid, lieu in index.items():
		entrees = [e for i in items for e in _entrees(lieu, "ressources", "ressource", i)]
		entrees += [e for eid in especes for e in _entrees(lieu, "rencontres", "espece", eid)]
		if items and not entrees:
			espece = _carcasse_vers_espece(items[0])
			entrees = _entrees(lieu, "rencontres", "espece", espece) if espece else []
		for e in entrees:
			zones = e.get("zones") or []
			if zones and "zone" in sources:
				for z in zones:
					pistes.append({"type": "zone", "porteur": lid, "lieu": lid, "zone": z, "cible": cible_id})
			elif not zones and "lieu" in sources:
				pistes.append({"type": "lieu", "porteur": lid, "lieu": lid, "cible": cible_id})
	if "donjon" in sources:
		cherche = set(especes) | {_carcasse_vers_espece(i) for i in items}
		for d in donjons or []:
			portail = d.get("portail")
			for salle in d.get("battle_maps") or []:
				if cherche & set(salle.get("especes") or []) and portail:
					pistes.append({"type": "donjon", "porteur": portail, "lieu": salle.get("lieu"),
								   "donjon": d.get("_id"), "cible": cible_id})
					break
	if "boutique" in sources and items:
		for b in boutiques or []:
			if any(s.get("item_id") == items[0] and int(s.get("qty") or 0) > 0 for s in (b.get("stock_vente") or [])):
				pistes.append({"type": "boutique", "porteur": b["_id"], "lieu": b["_id"], "cible": cible_id})
	# Une même zone peut venir de deux entrées : on dédoublonne.
	vues, uniques = set(), []
	for p in pistes:
		cle = (p["type"], p["porteur"], p.get("zone"), p.get("donjon"))
		if cle not in vues:
			vues.add(cle)
			uniques.append(p)
	return uniques


def toutes_cibles(sources: list, index: dict, donjons: list, boutiques: list) -> set:
	"""Toutes les cibles qu'un renseignement peut viser par ces sources (pour le hasard)."""
	cibles = set()
	for lieu in index.values():
		if "lieu" in sources or "zone" in sources:
			cibles.update(e.get("espece") for e in (lieu.get("rencontres") or []) if e.get("espece"))
			cibles.update(e.get("ressource") for e in (lieu.get("ressources") or []) if e.get("ressource"))
	if "donjon" in sources:
		for d in donjons or []:
			for salle in d.get("battle_maps") or []:
				cibles.update(salle.get("especes") or [])
	if "boutique" in sources:
		for b in boutiques or []:
			cibles.update(s.get("item_id") for s in (b.get("stock_vente") or []) if int(s.get("qty") or 0) > 0)
	return {c for c in cibles if c}


def a_portee(pistes: list, distances: dict, portee_lieux: int | None = None, portee_max: int | None = None) -> list:
	"""Pistes JOIGNABLES, des plus proches aux plus lointaines (ex æquo : ordre d'id), limitées aux
	`portee_lieux` lieux porteurs les plus proches et à `portee_max` liens si la méthode en fixe."""
	n = int(character_stats.RENS_PORTEE_LIEUX) if portee_lieux is None else int(portee_lieux)
	tri = sorted((p for p in pistes if p["porteur"] in distances),
				 key=lambda p: (distances[p["porteur"]], p["porteur"], p.get("zone") or "", p.get("donjon") or ""))
	if portee_max is not None:
		tri = [p for p in tri if distances[p["porteur"]] <= portee_max]
	porteurs, sortie = [], []
	for p in tri:
		if p["porteur"] not in porteurs:
			if len(porteurs) >= n:
				break
			porteurs.append(p["porteur"])
		p = dict(p)
		p["distance"] = distances[p["porteur"]]
		sortie.append(p)
	return sortie


# ── Jet ──────────────────────────────────────────────────────────────────────────

def niveau_du_jet(jet: int, seuil_v: int) -> str:
	if jet <= seuil_v * float(character_stats.RENS_EXACT_FACTEUR):
		return "exact"
	if jet <= seuil_v:
		return "region"
	return "rumeur"


def plafonner(niveau: str, niveau_max: str) -> str:
	return niveau if NIVEAUX.index(niveau) <= NIVEAUX.index(niveau_max) else niveau_max


# ── Libellés ─────────────────────────────────────────────────────────────────────

def nom_cible(cible_id: str, doc: dict | None) -> str:
	"""« un loup » (accord de l'espèce) ; une matière entre guillemets, sans article inventé."""
	if cible_id.startswith("espece:"):
		from utils import accord_espece
		return accord_espece.groupe(doc, "un") if doc else cible_id.split(":", 1)[-1]
	return "« " + ((doc or {}).get("nom") or cible_id.split(":", 1)[-1].replace("_", " ")) + " »"


VOYELLES = tuple("AEIOUYÂÀÉÈÊÎÏÔÛÜaeiouyâàéèêîïôûüHh")


def de(label: str) -> str:
	"""« de France », « d'Auxerre », « du Puy » (Le → du, Les → des, La → de la)."""
	label = str(label or "")
	for article, contraction in (("Le ", "du "), ("Les ", "des "), ("La ", "de la "), ("L'", "de l'")):
		if label.startswith(article):
			return contraction + label[len(article):]
	return ("d'" if label.startswith(VOYELLES) else "de ") + label


def _label(index: dict, lieu_id: str) -> str:
	return lieu_label(index.get(lieu_id) or {}, lieu_id)


def ou_exact(p: dict, index: dict, zones_noms: dict, donjons_noms: dict) -> tuple[str, str]:
	"""(phrase « où », libellé court du lieu) au niveau exact."""
	if p["type"] == "zone":
		z = zones_noms.get(p["zone"]) or p["zone"].split(":")[-1].replace("_", " ")
		lbl = f"{z} ({_label(index, p['porteur'])})"
		return f"dans la zone « {z} » {de(_label(index, p['porteur']))}", lbl
	if p["type"] == "donjon":
		nom = donjons_noms.get(p.get("donjon")) or _label(index, p["porteur"])
		return f"dans le donjon « {nom} »", nom
	if p["type"] == "boutique":
		cite = cite_de(p["porteur"], index)
		suffixe = f" ({lieu_label(cite)})" if cite else ""
		return f"chez {_label(index, p['porteur'])}{suffixe}", _label(index, p["porteur"])
	return f"à {_label(index, p['porteur'])}", _label(index, p["porteur"])


def distance_txt(d: int) -> str:
	if d <= 2:
		return "tout près d'ici"
	if d <= 5:
		return "à quelque distance"
	return "loin d'ici"


def terrain_txt(p: dict, index: dict, zones_terrains: dict) -> str:
	tags = list(zones_terrains.get(p.get("zone")) or []) if p.get("zone") else []
	for d in chaine(p["porteur"], index):
		tags += list(d.get("tags") or []) + [d.get("categorie") or ""]
	if p["type"] == "donjon":
		tags = ["donjon"] + tags
	return next((TERRAINS[t] for t in tags if t in TERRAINS), "quelque part")


# ── Grade ────────────────────────────────────────────────────────────────────────

def rang_piste(p: dict, index: dict, donjons: list, rang_fn) -> str | None:
	"""Grade d'une piste : l'espèce visée, sinon la pire espèce qui partage l'endroit."""
	if p["cible"].startswith("espece:"):
		return rang_fn(p["cible"])
	especes = set()
	if p["type"] in ("lieu", "zone"):
		for e in (index.get(p["porteur"]) or {}).get("rencontres") or []:
			if p["type"] == "lieu" or p.get("zone") in (e.get("zones") or []):
				especes.add(e.get("espece"))
	elif p["type"] == "donjon":
		for d in donjons or []:
			if d.get("_id") == p.get("donjon"):
				for salle in d.get("battle_maps") or []:
					especes.update(salle.get("especes") or [])
	rangs = [r for r in (rang_fn(e) for e in especes if e) if r]
	return max(rangs, key=rang_index) if rangs else None


def rang_txt(rang: str | None) -> str:
	if not rang:
		return ""
	from utils.potentiel import RANG_LIBELLES
	return f"{RANG_LIBELLES.get(rang, '')} (rang {rang})".strip()


# ── Recherche ────────────────────────────────────────────────────────────────────

def choisir_piste(pistes: list, rand=random, ponderer: bool = False) -> dict | None:
	"""La plus proche (déterministe), ou tirée avec un poids 1/(1+d) (« ce qui traîne »)."""
	if not pistes:
		return None
	if not ponderer:
		return pistes[0]
	return rand.choices(pistes, weights=[1.0 / (1 + p["distance"]) for p in pistes], k=1)[0]


def resoudre(methode: dict, seuil_v: int, pistes: list, *, rand=random, ponderer: bool = False,
			 fausses: list | None = None, sans_jet: bool = False) -> dict:
	"""{niveau, piste, jet, fausse}. `pistes` = à portée et triées ; `fausses` = pistes d'AUTRES
	cibles, où une rumeur fausse ira pointer. Sans piste : niveau `rien` (sauf rumeur fausse)."""
	jet = None
	if sans_jet:
		niveau = "exact"
	elif methode["niveau_fixe"]:
		niveau = methode["niveau_fixe"]
	else:
		jet = rand.randint(1, 100)
		niveau = plafonner(niveau_du_jet(jet, seuil_v), methode["niveau_max"])
	piste = choisir_piste(pistes, rand, ponderer)
	fausse = False
	if niveau == "rumeur" and fausses and (not piste or rand.randint(1, 100) <= int(character_stats.RENS_FAUSSE_PCT)):
		piste, fausse = rand.choice(fausses), True
	if piste is None:
		niveau = "rien"
	return {"niveau": niveau, "piste": piste, "jet": jet, "fausse": fausse}


def texte_resultat(res: dict, cible_txt: str, acteur_nom: str, index: dict, zones_noms: dict,
				   zones_terrains: dict, donjons_noms: dict, rang: str | None, intro: str = "",
				   cible_id: str = "") -> dict:
	"""{texte, lieu_id, lieu_label} — le lieu inscrit au bestiaire (None pour une rumeur).
	`cible_id` = la cible NOMMÉE (≠ celle de la piste pour une rumeur fausse)."""
	p, niveau = res["piste"], res["niveau"]
	debut = (intro.strip() + " ") if intro else ""
	if niveau == "rien":
		return {"texte": f"{debut}Personne n'a entendu parler de {cible_txt} dans les environs.",
				"lieu_id": None, "lieu_label": ""}
	if niveau == "rumeur":
		# Une bête se VOIT, une matière se TROUVE (la cible de la piste dit laquelle).
		verbe = "aurait vu" if (cible_id or p.get("cible") or "").startswith("espece:") else "trouverait"
		return {"texte": (f"{debut}{acteur_nom} entend dire qu'on {verbe} {cible_txt} "
						  f"{terrain_txt(p, index, zones_terrains)}, {distance_txt(p.get('distance', 99))}."),
				"lieu_id": None, "lieu_label": ""}
	if niveau == "region":
		reg = region_de(p["porteur"], index) or {}
		lbl = lieu_label(reg, p["porteur"])
		return {"texte": f"{debut}{acteur_nom} apprend qu'on trouve {cible_txt} du côté {de(lbl)}.",
				"lieu_id": reg.get("_id") or p["porteur"], "lieu_label": lbl}
	ou, lbl = ou_exact(p, index, zones_noms, donjons_noms)
	grade = rang_txt(rang)
	return {"texte": (f"{debut}{acteur_nom} apprend qu'on trouve {cible_txt} {ou}"
					  + (f" — {grade}" if grade else "") + "."),
			"lieu_id": p["lieu"] if p["type"] != "zone" else p["porteur"], "lieu_label": lbl}


# ── Salle commune de guilde ──────────────────────────────────────────────────────
# Recrues du tableau (réception) et réceptionniste (comptoir). Bornes de rang : le rang de
# l'interlocuteur ≥ grade du sujet (recrue seule ; le réceptionniste lit les archives) ET le
# rang du joueur ≥ grade − 1. Un sujet bloqué se dit, ne se paie pas, ne lance aucun délai.

def rang_de_niveau(niveau: int) -> str:
	"""Rang d'un PNJ de ce niveau : le plus haut dont le niveau d'entrée
	(`QUETE_RANG_NIVEAU_ENTREE`) est atteint, sinon le premier. Relu, jamais stocké."""
	rang = RANGS[0]
	for r, n in sorted((character_stats.QUETE_RANG_NIVEAU_ENTREE or {}).items(), key=lambda x: x[1]):
		if int(niveau or 0) >= int(n):
			rang = r
	return rang


def niveau_de(pnj: dict) -> int:
	return character_stats.compute_character_level(int((pnj or {}).get("xp_total", 0) or 0))


def pays_de(lieu_id: str, index: dict) -> dict | None:
	return next((d for d in chaine(lieu_id, index) if d.get("categorie") == "pays"), None)


def capitale_du_pays(pays_id: str, index: dict) -> dict | None:
	"""La cité `sous_categorie: capitale` rattachée à ce pays (ordre d'id si plusieurs)."""
	if not pays_id:
		return None
	return next((d for _, d in sorted(index.items())
				 if d.get("categorie") == "ville" and d.get("sous_categorie") == "capitale"
				 and any(a.get("_id") == pays_id for a in chaine(d["_id"], index))), None)


def rang_joueur_guilde(character: dict, cite_id: str, capitale_id: str | None) -> str:
	"""Meilleur rang entre celui de CETTE guilde et celui de la capitale du pays (F sans rang)."""
	rangs = (character or {}).get("rangs_guilde") or {}
	candidats = [rangs.get(cite_id), rangs.get(capitale_id) if capitale_id else None]
	return max((r for r in candidats if r in RANGS), key=rang_index, default=RANGS[0])


def borne_rang(grade: str | None, rang_pnj: str | None, rang_joueur: str) -> str | None:
	"""Raison du refus, ou None. `rang_pnj` None = pas de borne pour l'interlocuteur."""
	if not grade or grade not in RANGS:
		return None
	if rang_pnj is not None and rang_index(rang_pnj) < rang_index(grade):
		return f"Ça me dépasse : une menace de rang {grade}, je n'en ai jamais approché."
	if rang_index(rang_joueur) < rang_index(grade) - 1:
		return f"Pas pour votre rang : la Guilde n'en parle qu'à partir du rang {RANGS[rang_index(grade) - 1]}."
	return None


def dans_pays(p: dict, pays_id: str | None, index: dict) -> bool:
	"""La piste se rattache-t-elle à ce pays (porteur ou un de ses ancêtres) ?"""
	return bool(pays_id) and any(d.get("_id") == pays_id for d in chaine(p["porteur"], index))


def pistes_speciales(cible_id: str, index: dict, donjons: list) -> list | None:
	"""Cibles qui ne sont ni espèce ni matière : un LIEU (quête de visite, d'escorte, de
	transport) ou un DONJON (sujet « donjons du coin »). None pour les autres."""
	if cible_id.startswith("lieu:"):
		return [{"type": "lieu", "porteur": cible_id, "lieu": cible_id, "cible": cible_id}] if cible_id in index else []
	if cible_id.startswith("donjon:"):
		d = next((x for x in donjons or [] if x.get("_id") == cible_id), None)
		salles = [s.get("lieu") for s in (d or {}).get("battle_maps") or [] if s.get("lieu")]
		if not d or not d.get("portail") or not salles:
			return []
		return [{"type": "donjon", "porteur": d["portail"], "lieu": salles[0], "donjon": cible_id, "cible": cible_id}]
	return None


def especes_du_donjon(donjon: dict | None) -> list:
	vues = []
	for s in (donjon or {}).get("battle_maps") or []:
		for e in s.get("especes") or []:
			if e not in vues:
				vues.append(e)
	return vues


def grade_sujet(cible_id: str, donjons: list, rang_fn) -> str | None:
	"""Grade qui borne un sujet : l'espèce, ou la pire espèce d'un donjon ; rien sinon."""
	if cible_id.startswith("espece:"):
		return rang_fn(cible_id)
	if cible_id.startswith("donjon:"):
		d = next((x for x in donjons or [] if x.get("_id") == cible_id), None)
		rangs = [r for r in (rang_fn(e) for e in especes_du_donjon(d)) if r]
		return max(rangs, key=rang_index) if rangs else None
	return None


def affrontes(recrue_id: str, pistes_especes: list, rang_recrue: str, rang_fn) -> list:
	"""Ce qu'une recrue a AFFRONTÉ : 2 à 3 pistes d'espèces de grade ≤ le sien, tirées avec son
	id pour graine — déterministe, rien de stocké, valable pour une recrue déjà en base."""
	tri = sorted((p for p in pistes_especes if p["cible"].startswith("espece:")
				  and rang_index(rang_fn(p["cible"])) <= rang_index(rang_recrue)),
				 key=lambda p: (p["cible"], p["porteur"], p.get("zone") or "", p.get("donjon") or ""))
	if not tri:
		return []
	graine = random.Random(str(recrue_id))
	return graine.sample(tri, min(len(tri), 2 + graine.randint(0, 1)))


def savoir_recrue(cible_id: str, deja_affrontes: list, pistes_pays: list, pistes_metier: list) -> tuple:
	"""Le MEILLEUR savoir de la recrue sur cette cible : (source, pistes, sans_jet).
	affronté ⇒ lieu exact sans jet ; sinon sa région d'origine (pays de la guilde) ⇒ jet avec
	bonus ; sinon la méthode de sa vocation ⇒ jet ; sinon rien."""
	vus = [p for p in deja_affrontes if p["cible"] == cible_id]
	if vus:
		return "affronte", vus, True
	if pistes_pays:
		return "origine", pistes_pays, False
	if pistes_metier:
		return "metier", pistes_metier, False
	return None, [], False


def cout_recrue(niveau: str, niveau_recrue: int) -> int:
	"""Pourboire : RENS_RECRUE_POURBOIRE × RENS_COUT_MULT[niveau] × (1 + niveau de la recrue / 10)."""
	mult = float((character_stats.RENS_COUT_MULT or {}).get(niveau, 1.0))
	return max(0, round(int(character_stats.RENS_RECRUE_POURBOIRE) * mult * (1 + int(niveau_recrue or 0) / 10)))


def texte_lieu(res: dict, label: str, acteur_nom: str, index: dict, intro: str = "") -> dict:
	"""Une quête dont la cible est un LIEU : où il se trouve (carnet seul)."""
	debut = (intro.strip() + " ") if intro else ""
	p, niveau = res["piste"], res["niveau"]
	if niveau == "rien" or not p:
		return {"texte": f"{debut}Personne ne sait où se trouve « {label} ».", "lieu_id": None, "lieu_label": ""}
	if niveau == "rumeur":
		return {"texte": f"{debut}{acteur_nom} croit savoir que « {label} » est {distance_txt(p.get('distance', 99))}.",
				"lieu_id": None, "lieu_label": ""}
	reg = region_de(p["porteur"], index) or {}
	if niveau == "region" or reg.get("_id") == p["porteur"]:
		return {"texte": f"{debut}{acteur_nom} situe « {label} » du côté {de(lieu_label(reg, p['porteur']))}.",
				"lieu_id": None, "lieu_label": ""}
	return {"texte": (f"{debut}{acteur_nom} situe « {label} » dans {lieu_label(reg, '')}, "
					  f"à {p.get('distance', '?')} passage(s) d'ici."), "lieu_id": None, "lieu_label": ""}


def etat_donjon(donjon: dict | None, purge_fn, reinfeste_fn) -> str:
	"""« nettoyé par vous », « de nouveau infesté », ou « jamais nettoyé par vous »."""
	salles = [s.get("lieu") for s in (donjon or {}).get("battle_maps") or [] if s.get("lieu")]
	if any(reinfeste_fn(s) for s in salles):
		return "de nouveau infesté"
	if salles and all(purge_fn(s) for s in salles):
		return "nettoyé par vous"
	return "jamais nettoyé par vous"


def texte_donjon(res: dict, donjon: dict, noms_especes: list, etat: str, acteur_nom: str,
				 rang: str | None, intro: str = "") -> dict:
	"""Sujet « donjon du coin » : rumeur = danger vague ; région = qui le peuple ; exact = qui
	le peuple, fourchette de niveaux, grade et état pour vous."""
	debut = (intro.strip() + " ") if intro else ""
	nom = donjon.get("nom") or donjon.get("_id", "")
	niveau = res["niveau"]
	if niveau in ("rien", "rumeur"):
		return {"texte": f"{debut}{acteur_nom} a seulement entendu dire que « {nom} » n'est pas un endroit pour les novices."}
	peuple = ", ".join(noms_especes) or "des créatures sans nom"
	if niveau == "region":
		return {"texte": f"{debut}{acteur_nom} sait que « {nom} » abrite {peuple}."}
	nmin, nmax = donjon.get("niveau_min"), donjon.get("niveau_max")
	niveaux = f" (niveaux {nmin} à {nmax})" if nmin is not None and nmax is not None else ""
	grade = rang_txt(rang)
	return {"texte": (f"{debut}{acteur_nom} sait que « {nom} » abrite {peuple}{niveaux}"
					  + (f" — {grade}" if grade else "") + f" ; {etat}.")}


# ── Note de renseignement ────────────────────────────────────────────────────────

def nouvelle_note(auteur_nom: str, resultat: dict, now: int | None = None) -> dict:
	"""Référence d'inventaire : la piste vit sur la RÉFÉRENCE (patron de l'écrit personnel)."""
	return {
		"item": ITEM_NOTE_ID,
		"piste": {k: resultat.get(k) for k in ("texte", "cible", "cible_nom", "niveau", "lieu_id", "lieu_label", "rang")},
		"auteur_nom": auteur_nom,
		"cree_at": now_epoch() if now is None else int(now),
	}


def est_note(ref) -> bool:
	return isinstance(ref, dict) and ref.get("item") == ITEM_NOTE_ID and isinstance(ref.get("piste"), dict)


def titre_note(nom_generique: str, ref) -> str:
	cible = ((ref or {}).get("piste") or {}).get("cible_nom")
	return f"{nom_generique} : {cible}" if cible else nom_generique


def prix_note(ref) -> int:
	"""Prix d'une note : celui d'une dépouille dont la bête vaudrait l'XP du plancher de son rang
	(paliers de `xp_monstre`) ; sans grade, le premier rang."""
	from utils import xp_monstre
	rang = ((ref or {}).get("piste") or {}).get("rang")
	plancher = float((character_stats.QUETE_RANG_POTENTIEL_MIN or {}).get(rang, 0) or 0)
	return xp_monstre.prix_de_xp(xp_monstre.xp_de_potentiel(plancher))


def apprendre(character: dict, piste: dict, lieu_courant_label: str = "", now: int | None = None) -> bool:
	"""Inscrit une piste réussie chez CE personnage : bestiaire 👂 (espèce) + carnet (une fois).
	Renvoie True si quelque chose a changé."""
	from utils import journal
	change = False
	cible, lieu_id = piste.get("cible") or "", piste.get("lieu_id")
	if cible.startswith("espece:") and lieu_id and piste.get("niveau") in ("region", "exact"):
		change |= journal.noter_oui_dire(character, cible, lieu_id, piste.get("lieu_label") or "", now=now)
	texte = piste.get("texte") or ""
	if texte and not any(e.get("texte") == texte for e in journal.entrees_de(character)):
		journal.nouvelle_entree(character, texte, lieu_courant_label, now=now)
		change = True
	return change

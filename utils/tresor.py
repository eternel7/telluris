# utils/tresor.py
# Trésor d'un étage de donjon à étages — la règle, et rien d'autre.
#
# MARQUEUR : bloc `tresor` sur l'ENTRÉE de la salle dans `battle_maps` du doc `donjon:*`
# (absent ⇒ aucun coffre, comme avant). L'auteur choisit l'étage, en général le dernier.
#
#   "tresor": {
#     "nom": "Coffre de l'ossuaire", "icon": "🧰",          # optionnels
#     "pos": [x, y],                                         # optionnel (sinon tiré loin du départ)
#     "garanti": [{"item": "item:x", "quantite": 1}],       # donné à CHAQUE expédition
#     "bourse": [min, max],                                  # cuivre, tiré à chaque expédition
#     "tirage": {"nb": 2, "table": [{"item": "item:y", "poids": 3, "quantite": 1}]},
#     "piege": {"chance": 40, "danger": 3,                   # chance en % (100 = toujours)
#               "effets": ["degats", "alarme", "mimique"],   # UN effet tiré parmi eux
#               "alarme": 3,                                 # renforts (défaut : effectif de la salle)
#               "mimique": "espece:x"}                       # espèce qui jaillit du coffre
#   }
#
# CYCLE (un seul combat par expédition, `combat.installer_tresor`) : contenu et piège tirés à
# la PREMIÈRE entrée dans l'étage, mémorisés sur `etages.tresors[<lieu>]` — revenir à l'étage
# ne relance rien. Une nouvelle expédition (nouveau combat) retire tout : le trésor revient à
# chaque descente, part garantie comprise (demande de l'Auteur, 18/10).
#
# PIÈGE : un piège `camp:"monde"` ORDINAIRE (utils/pieges.py) posé sur la case du coffre,
# marqué `declencheur:"ouverture"` — détecté à l'approche ou par la fouille, désamorcé au
# contact comme les autres, mais ce n'est pas le pas qui le déclenche : c'est d'ouvrir.
#   • degats  : `<danger>D6` à l'ouvreur (cascade d'un piège de salle) ;
#   • alarme  : des monstres de l'étage accourent, loin du coffre, et savent où est le groupe ;
#   • mimique : le coffre s'anime (monstre de l'espèce écrite) — il ne s'ouvre qu'une fois
#     abattu.
#
# Module PUR : DB injectée (`get_doc_fn`, `instantiate_fn`), hasard par `rand_fn`.

import random

from utils import donjon
from utils import pieges as pieges_util
from utils.characters import tirer_poids

NOM_DEFAUT = "Coffre"
ICON_DEFAUT = "🧰"

EFFET_DEGATS = "degats"
EFFET_ALARME = "alarme"
EFFET_MIMIQUE = "mimique"
EFFETS = (EFFET_DEGATS, EFFET_ALARME, EFFET_MIMIQUE)

DECLENCHEUR_OUVERTURE = "ouverture"

# États du coffre.
ETAT_FERME = "ferme"     # jamais ouvert
ETAT_ANIME = "anime"     # mimique vivante : le coffre est le monstre
ETAT_OUVERT = "ouvert"   # ouvert, il reste des objets que l'ouvreur n'a pas pu porter
ETAT_VIDE = "vide"
ETATS_OUVRABLES = (ETAT_FERME, ETAT_OUVERT)

# Bornes de sûreté contre une faute de frappe (`"nb": 200`), pas des réglages de jeu.
TIRAGE_NB_MAX = 10
QUANTITE_MAX = 20

# Portée (Chebyshev) à laquelle on ouvre un coffre : au contact, comme on ramasse.
PORTEE_OUVERTURE = 1


def _as_int(valeur, defaut: int = 0) -> int:
	try:
		return int(valeur)
	except (TypeError, ValueError):
		return defaut


def _borne(valeur: int, mini: int, maxi: int) -> int:
	return max(mini, min(maxi, valeur))


def _lignes(raw, avec_poids: bool) -> list:
	out = []
	for ligne in raw or []:
		if not isinstance(ligne, dict):
			continue
		item = str(ligne.get("item") or "").strip()
		if not item:
			continue
		entree = {"item": item,
				  "quantite": _borne(_as_int(ligne.get("quantite"), 1) or 1, 1, QUANTITE_MAX)}
		if avec_poids:
			poids = _as_int(ligne.get("poids"), 1)
			if poids <= 0:
				continue
			entree["poids"] = poids
		out.append(entree)
	return out


def normaliser_tresor(raw) -> dict | None:
	"""Bloc `tresor` normalisé, ou None (absent / inexploitable : rien à trouver)."""
	if not isinstance(raw, dict):
		return None
	garanti = _lignes(raw.get("garanti"), avec_poids=False)
	bourse = raw.get("bourse")
	if isinstance(bourse, (list, tuple)) and len(bourse) >= 2:
		bmin, bmax = max(0, _as_int(bourse[0])), max(0, _as_int(bourse[1]))
	else:
		bmin = bmax = max(0, _as_int(bourse))
	bourse = [min(bmin, bmax), max(bmin, bmax)]
	brut_tirage = raw.get("tirage") if isinstance(raw.get("tirage"), dict) else {}
	table = _lignes(brut_tirage.get("table"), avec_poids=True)
	tirage = {"nb": _borne(_as_int(brut_tirage.get("nb"), 1), 0, TIRAGE_NB_MAX) if table else 0,
			  "table": table}
	if not garanti and not tirage["nb"] and not bourse[1]:
		return None
	pos = raw.get("pos")
	if isinstance(pos, dict):
		pos = [pos.get("x"), pos.get("y")]
	pos = ([_as_int(pos[0], -1), _as_int(pos[1], -1)]
		   if isinstance(pos, (list, tuple)) and len(pos) >= 2 else None)
	return {
		"nom": str(raw.get("nom") or "").strip() or NOM_DEFAUT,
		"icon": str(raw.get("icon") or "").strip() or ICON_DEFAUT,
		"pos": pos,
		"garanti": garanti,
		"bourse": bourse,
		"tirage": tirage,
		"piege": _normaliser_piege(raw.get("piege")),
	}


def _normaliser_piege(raw) -> dict | None:
	if not isinstance(raw, dict):
		return None
	chance = _borne(_as_int(raw.get("chance"), 100), 0, 100)
	if chance <= 0:
		return None
	effets = [e for e in (raw.get("effets") or [EFFET_DEGATS]) if e in EFFETS]
	mimique = str(raw.get("mimique") or "").strip()
	if not mimique:
		effets = [e for e in effets if e != EFFET_MIMIQUE]
	alarme = raw.get("alarme")
	return {
		"chance": chance,
		"danger": _borne(_as_int(raw.get("danger"), 1), pieges_util.DANGER_MIN,
						 pieges_util.DANGER_MAX),
		"effets": effets or [EFFET_DEGATS],
		"alarme": (None if alarme is None
				   else _borne(_as_int(alarme, 1), 1, donjon.NB_MONSTRES_MAX)),
		"mimique": mimique or None,
	}


def tresor_de_salle(donjon_doc: dict | None, lieu_id: str) -> dict | None:
	"""Bloc `tresor` normalisé de cette salle du donjon, ou None."""
	entree = donjon.battle_map_entry(donjon_doc or {}, lieu_id) or {}
	return normaliser_tresor(entree.get("tresor"))


# ── Tirages ──────────────────────────────────────────────────────────────────

def _choisir(table: list, rand_fn) -> dict:
	total = sum(l["poids"] for l in table)
	seuil = rand_fn() * total
	for ligne in table:
		seuil -= ligne["poids"]
		if seuil < 0:
			return ligne
	return table[-1]


def tirer_contenu(tresor: dict, get_doc_fn, rand_fn=None) -> dict:
	"""Contenu d'UNE expédition : `{objets: [{item, nom, icon, poids}], cuivre}` — un objet
	par exemplaire (chacun a son poids d'instance), garanti d'abord puis tirage. Un item
	absent de la base est écarté."""
	rand_fn = rand_fn or random.random
	lignes = list(tresor.get("garanti") or [])
	table = (tresor.get("tirage") or {}).get("table") or []
	for _ in range((tresor.get("tirage") or {}).get("nb", 0) if table else 0):
		lignes.append(_choisir(table, rand_fn))
	objets = []
	for ligne in lignes:
		doc = get_doc_fn(ligne["item"])
		if not doc:
			continue
		for _ in range(ligne.get("quantite", 1)):
			objets.append({"item": doc["_id"], "nom": doc.get("nom", doc["_id"]),
						   "icon": doc.get("icon", ""), "poids": tirer_poids(doc, rand_fn)})
	bmin, bmax = (tresor.get("bourse") or [0, 0])[:2]
	cuivre = bmin + int(rand_fn() * (bmax - bmin + 1)) if bmax > bmin else bmin
	return {"objets": objets, "cuivre": min(cuivre, bmax)}


def tirer_piege(tresor: dict, rand_fn=None) -> dict | None:
	"""Le coffre est-il piégé cette fois ? `{danger, effet}` ou None."""
	rand_fn = rand_fn or random.random
	piege = tresor.get("piege")
	if not piege or rand_fn() * 100 >= piege["chance"]:
		return None
	effets = piege["effets"]
	effet = effets[min(int(rand_fn() * len(effets)), len(effets) - 1)]
	return {"danger": piege["danger"], "effet": effet}


def preparer_tresor(donjon_doc: dict, lieu_id: str, profils: list, nb_compagnons: int,
					get_doc_fn, instantiate_fn, rand_fn=None) -> dict | None:
	"""Tout ce que l'étage `lieu_id` réserve, tiré pour cette expédition, ou None (pas de
	trésor) : nom, icône, case écrite, contenu, piège ; plus les monstres que le piège
	ferait paraître — instanciés ICI, le moteur de combat ne lit pas les espèces.
	Grade : la fourchette de la salle (`donjon.monstres_de_salle`)."""
	tresor = tresor_de_salle(donjon_doc, lieu_id)
	if tresor is None:
		return None
	prepare = {"lieu": lieu_id, "nom": tresor["nom"], "icon": tresor["icon"],
			   "pos": tresor["pos"], **tirer_contenu(tresor, get_doc_fn, rand_fn)}
	piege = tirer_piege(tresor, rand_fn)
	if piege and piege["effet"] == EFFET_MIMIQUE:
		espece = get_doc_fn(tresor["piege"]["mimique"])
		mimique = donjon.monstres_de_salle(
			donjon_doc, lieu_id, profils, 0, get_doc_fn, instantiate_fn, nb=1,
			especes=[espece]) if espece else []
		if mimique:
			prepare["mimique"] = mimique[0]
		else:
			piege["effet"] = EFFET_DEGATS   # espèce introuvable : le piège reste un piège
	if piege and piege["effet"] == EFFET_ALARME:
		prepare["renforts"] = donjon.monstres_de_salle(
			donjon_doc, lieu_id, profils, nb_compagnons, get_doc_fn, instantiate_fn,
			nb=tresor["piege"]["alarme"])
	prepare["piege"] = piege
	return prepare


# ── Placement ────────────────────────────────────────────────────────────────

def case_du_tresor(cells: list, dims: dict, pos_ecrite, depart, interdites,
				   rand_fn=None) -> tuple | None:
	"""Case du coffre : la case ÉCRITE si elle est au sol, sinon une case au sol tirée hors
	`interdites`, à au moins `pieges.PIEGES_DISTANCE_DEPART` du départ (même éloignement que
	les pièges de salle). None : carte sans case possible."""
	if pos_ecrite and pieges_util.case_au_sol(cells, pos_ecrite[0], pos_ecrite[1]):
		return int(pos_ecrite[0]), int(pos_ecrite[1])
	places = pieges_util.placer_pieges(cells, dims, [depart] if depart else [],
									   interdites, 1, 1, rand_fn=rand_fn)
	return (places[0]["x"], places[0]["y"]) if places else None


def nouveau_piege_du_coffre(pid: str, x: int, y: int, piege: dict, nom: str) -> dict:
	"""Le piège tiré (`tirer_piege`), sous la forme UNIQUE des pièges (caché)."""
	p = pieges_util.nouveau_piege(pid, pieges_util.CAMP_MONDE, x, y, piege["danger"],
								  nom=f"Piège — {nom}")
	p["declencheur"] = DECLENCHEUR_OUVERTURE
	p["effet"] = piege["effet"]
	return p


def piege_d_ouverture(piege: dict) -> bool:
	"""Ce piège se déclenche-t-il à l'OUVERTURE d'un coffre (et non sous le pas) ?"""
	return (piege or {}).get("declencheur") == DECLENCHEUR_OUVERTURE


# ── Lectures ─────────────────────────────────────────────────────────────────

def a_portee(etat: dict, emprise) -> bool:
	"""L'emprise d'un acteur touche-t-elle le coffre ?"""
	if not etat or etat.get("x") is None:
		return False
	return any(max(abs(cx - etat["x"]), abs(cy - etat["y"])) <= PORTEE_OUVERTURE
			   for cx, cy in emprise or [])


def prendre(objets: list, charge: float, charge_max: float) -> tuple:
	"""Ce que l'ouvreur emporte, dans l'ordre du coffre, tant que sa charge le permet ;
	le reste demeure dans le coffre. Renvoie `(pris, restes)`."""
	pris, restes = [], []
	for o in objets or []:
		if charge + o["poids"] <= charge_max + 1e-6:
			pris.append(o)
			charge += o["poids"]
		else:
			restes.append(o)
	return pris, restes


def vue_publique(etat: dict | None) -> dict | None:
	"""Ce que le CLIENT voit du coffre : jamais le contenu d'un coffre fermé, jamais le
	piège (il ne paraît, comme tout piège, que détecté), jamais les monstres réservés.
	Coffre animé : rien — c'est le monstre qu'on voit."""
	if not etat or etat.get("x") is None or etat.get("etat") == ETAT_ANIME:
		return None
	vue = {k: etat.get(k) for k in ("x", "y", "nom", "icon", "etat")}
	if etat.get("etat") == ETAT_OUVERT:
		vue["contenu"] = [{"nom": o["nom"], "icon": o.get("icon", ""), "poids": o["poids"]}
						  for o in etat.get("objets") or []]
	return vue

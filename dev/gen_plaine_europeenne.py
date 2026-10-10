"""La Plaine européenne, Bruges et Aix-la-Chapelle — et les outils de FRONTIÈRE partagés.

Bibliothèque de `dev/gen_voisins_france.py` (qui écrit le fichier à importer unique) ; pas de
point d'entrée propre.

TROIS LIEUX : les deux cités sont POSÉES sur la plaine (`lieu_parent` + connexions) et la
plaine est rattachée à `lieu:france`. Docs minimaux par `cartes_a_creer` / `villes_a_creer`,
grilles par `gen_grille_image.proposer_pour_image` (profil `pays` : côte murée en nav ; profil
ville : `cells` + `nav`). Déjà en base ⇒ le doc RELU du dump sert de base (retouches gardées).

RÈGLE DES FRONTIÈRES — on ne passe d'une carte à l'autre QUE par une connexion :
  · le territoire du VOISIN que montre une carte est mis à 0 (`FRONTIERE_*`, bandes lues sur
    l'image) : il ne se traverse plus, le joueur doit prendre la connexion ;
  · les connexions se posent SUR la frontière, du côté accessible — avant la limite des murs
    nav quand la carte montre plus loin que la frontière ;
  · entre deux PAYS, UNE CASE SUR DEUX de la frontière porte un passage (`ligne_frontiere`,
    `liens_frontiere`) : la ligne est relue sur la grille, les noms comptés pour son côté le
    plus long — l'autre, plus court, porte parfois deux passages sur une case ;
  · chaque passage est NOMMÉ (col, gué, route…) : un nœud porte « <passage> — <son lieu> ».
    Le bouton du jeu affiche le libellé du nœud de DESTINATION (`buildLocationslist`) : le
    joueur lit le passage ET le pays où il mène. Côté cité, le nœud de la cité porte
    « <cité> — par l'ouest » : sur la carte du pays, ses liens sont sur des cases voisines.
  · cité ↔ plaine : sur la plaine, la case de la cité et ses voisines (une case par lien, le
    schéma de Reims ↔ France) ; dans la cité, une sortie par route qui quitte la carte.
  Chaque case visée est ramenée à la case libre la plus proche DANS LA ZONE de la terre de sa
  carte (`zone_de`, ancrée sur un point de terre : sur une carte de pays la mer est une zone à
  part, parfois plus grande que la terre) ; aucune case ⇒ lot refusé.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_cartes_pays import cartes_a_creer  # noqa: E402
from dev.gen_villes_images import poser_grille, villes_a_creer  # noqa: E402
from utils import grille_image  # noqa: E402

IMAGE_PLAINE = "plaine_europeenne.jpg"
PLAINE = "lieu:plaine_europeenne"
FRANCE = "lieu:france"
IMAGES_CITES = ("bruges_city.jpg", "aix_la_chapelle_city.jpg")

# Un point de TERRE par carte de pays : la zone qui le contient est celle où l'on marche.
ANCRE_PLAINE = (41, 29)    # Aix-la-Chapelle
ANCRE_FRANCE = (45, 25)    # Massif central

# Place des cités sur la plaine (lue sur l'image, 88×48 cases de 16 px) :
#   Bruges — le château dessiné sur le delta de l'Escaut, au débouché du Zwin ;
#   Aix-la-Chapelle — entre Meuse et Rhin, au nord des forêts de l'Ardenne et de l'Eifel.
POSITIONS_PLAINE = {
	"lieu:bruges": (28, 25),
	"lieu:aix_la_chapelle": (41, 29),
}

# Sorties des cités : nom → point visé (une route qui quitte la carte, hors du cadre).
# Bruges n'a pas de sortie au nord : c'est le Zwin et la mer.
SORTIES_CITES = {
	"lieu:bruges": {"ouest": (1, 30), "sud": (40, 46), "est": (86, 30)},
	"lieu:aix_la_chapelle": {"nord": (53, 1), "ouest": (4, 22), "est": (83, 20), "sud": (55, 43)},
}

# Le NORD DE LA FRANCE sur la plaine, mis à 0 : (x_min, x_max, y) ⇒ cases y ≥ `y` à 0.
# Côte picarde, puis la frontière au sud de l'Ardenne, la Lorraine et l'Alsace jusqu'au Rhin ;
# au-delà (x ≥ 56) le bas de la carte est l'Empire, pas la France.
FRONTIERE_PLAINE = ((0, 12, 38), (13, 20, 39), (21, 34, 41), (35, 44, 43), (45, 55, 45))

# France ↔ plaine, une case sur deux de la frontière (`liens_frontiere`). Sur la France, la
# rangée 1 peinte (nord fermé par nav) EST la frontière, et la côte picarde en (45, 2) : ses
# cases touchent l'au-delà `NORD_FRANCE` (x_min, x_max, y_min, y_max — les cases hors de la
# terre). Sur la plaine, la case juste au nord de la bande mise à 0. Lignes lues d'OUEST en
# EST depuis `DEPART_*`.
NORD_FRANCE = (45, 87, 0, 1)
DEPART_FRANCE_NORD = (45, 2)
DEPART_PLAINE = (0, 37)

# Noms, d'ouest en est (Manche → Flandre → Hainaut → Ardenne → Lorraine → Rhin) : un par
# poste de la plaine (55 cases ⇒ 28 ; la France, 42 cases, en porte deux sur certaines).
# ⚠️ Rang = suffixe d'`_id` (`_01`…) : réordonner fait désigner un autre passage aux `_id`
# en base ; la grille bouge ⇒ `liens_frontiere` avertit que le compte ne tombe plus juste.
PASSAGES_PLAINE = (
	"Chemin de la côte picarde", "Grève de Malo", "Route de Furnes", "Gué de l'Yser",
	"Route des Flandres", "Gué de la Lys", "Route de Lille à Courtrai", "Pont de Tournai",
	"Route de Valenciennes à Mons", "Gué de la Sambre", "Bois de Chimay", "Route de Rocroi",
	"Vallée de la Meuse", "Gué de la Semois", "Route de Bouillon", "Route de Montmédy",
	"Gué de la Chiers", "Route du Luxembourg", "Gué de la Moselle", "Route de Thionville",
	"Route de la Sarre", "Pont de Sarrebruck", "Passage de Bitche", "Route de Wissembourg",
	"Gué de la Lauter", "Pont du Rhin", "Bac de Seltz", "Pont de Kehl",
)

# Libellé d'une sortie de cité, d'après sa clé dans `SORTIES_*`.
SORTIES_LIBELLES = {"nord": "par le nord", "sud": "par le sud", "est": "par l'est",
	"ouest": "par l'ouest", "nord_est": "par le nord-est"}

METADATA = {"type": "chemin", "status": "ouvert"}

# Grille de toutes les cartes de pays (88 × 48 cases de 16 px).
DIMS = {"x": 88, "y": 48}

# Voisines d'une case, dans l'ordre où les liens les prennent (la case elle-même d'abord).
VOISINES = ((0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1))


# ── Outils de frontière (partagés avec gen_france_espagne_italie) ────────────────────────────
def zone_de(cells, nav, ancre=None):
	"""Cases `(x, y)` de la zone de `ancre` sous la règle de marche, ou de la plus grande zone
	sans ancre. Ancre hors de toute zone ⇒ ensemble vide."""
	zone, tailles = grille_image.zones(cells, nav)
	if not tailles:
		return set()
	if ancre is not None:
		x, y = ancre
		z = zone[y][x] if grille_image._dans(cells, x, y) else -1
		if z == -1:
			return set()
	else:
		z = max(range(len(tailles)), key=tailles.__getitem__)
	return {(x, y) for y, ligne in enumerate(zone) for x, v in enumerate(ligne) if v == z}


def case_proche(principale, cible):
	"""La case de `principale` la plus proche de `cible` (euclidienne, puis y, puis x) ou None."""
	if not principale:
		return None
	cx, cy = cible
	return min(principale, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0]))


def cases_autour(principale, centre, n):
	"""`n` cases distinctes de `principale` autour de `centre` (lui d'abord), ou None."""
	cases = [(centre[0] + dx, centre[1] + dy) for dx, dy in VOISINES]
	cases = [c for c in cases if c in principale]
	return cases[:n] if len(cases) >= n else None


def cases_frontiere(bandes, sens, cols, rows):
	"""Cases mises à 0 par `bandes`.

	'sud' / 'nord' : bandes de COLONNES ((x_min, x_max, y), …) ⇒ y ≥ `y` / y ≤ `y`.
	'est' / 'ouest' : bandes de RANGÉES ((y_min, y_max, x), …) ⇒ x ≥ `x` / x ≤ `x`."""
	cases = set()
	for a_min, a_max, borne in bandes:
		if sens in ("sud", "nord"):
			for x in range(max(0, a_min), min(cols - 1, a_max) + 1):
				ys = range(borne, rows) if sens == "sud" else range(0, min(rows - 1, borne) + 1)
				cases.update((x, y) for y in ys)
		else:
			for y in range(max(0, a_min), min(rows - 1, a_max) + 1):
				xs = range(borne, cols) if sens == "est" else range(0, min(cols - 1, borne) + 1)
				cases.update((x, y) for x in xs)
	return cases


def fermer(cells, cases) -> int:
	"""Met `cases` à 0 dans `cells` (muté) ; rend le nombre de cases changées."""
	n = 0
	for x, y in cases:
		if grille_image._dans(cells, x, y) and cells[y][x] != 0:
			cells[y][x] = 0
			n += 1
	return n


def connexion(_id, lieu_a, pos_a, lieu_b, pos_b):
	return {"_id": _id, "type": "connection",
		"nodes": [{"lieu": lieu_a, "pos": list(pos_a)}, {"lieu": lieu_b, "pos": list(pos_b)}],
		"metadata": dict(METADATA)}


def lien_vise(_id, lieu_a, zone_a, cible_a, lieu_b, zone_b, cible_b):
	"""(doc, refus) : chaque bout ramené à la case de sa zone la plus proche du point visé."""
	pos_a, pos_b = case_proche(zone_a, cible_a), case_proche(zone_b, cible_b)
	if pos_a is None or pos_b is None:
		manque = lieu_a if pos_a is None else lieu_b
		return None, f"{_id} : aucune case accessible sur {manque}"
	return connexion(_id, lieu_a, pos_a, lieu_b, pos_b), None


def bande(bandes, sens, dims):
	"""`cases_frontiere` sur les dimensions d'un doc."""
	return cases_frontiere(bandes, sens, dims["x"], dims["y"])


def ligne_frontiere(zone, au_dela, depart, cadre=None):
	"""Cases de `zone` qui touchent (orthogonalement) une case d'`au_dela`, en CHAÎNE : depuis
	la plus proche de `depart`, chaque pas va à la plus proche non encore prise (Chebyshev,
	puis Manhattan, puis y, puis x) — l'escalier d'une bande se suit marche par marche.
	`cadre` (x_min, x_max, y_min, y_max) : seules ces cases (une bande qui borde aussi la mer
	n'est une frontière que sur sa partie terrestre)."""
	x_min, x_max, y_min, y_max = cadre or (0, 10 ** 9, 0, 10 ** 9)
	restantes = {(x, y) for x, y in zone if x_min <= x <= x_max and y_min <= y <= y_max
		and any((x + dx, y + dy) in au_dela for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
	if not restantes:
		return []

	def pres(c, d):
		ex, ey = abs(c[0] - d[0]), abs(c[1] - d[1])
		return (max(ex, ey), ex + ey, c[1], c[0])

	ligne = [min(restantes, key=lambda c: pres(c, depart))]
	restantes.discard(ligne[0])
	while restantes:
		suivante = min(restantes, key=lambda c: pres(c, ligne[-1]))
		restantes.discard(suivante)
		ligne.append(suivante)
	return ligne


def postes(ligne, n):
	"""`n` cases de `ligne`, prises parmi une case sur deux (`ligne[0::2]`), réparties d'un bout
	à l'autre : exactement `ligne[0::2]` quand il y en a `n` ; moins ⇒ une case porte deux
	liens ; plus ⇒ des postes sautés."""
	pairs = ligne[0::2]
	if not pairs or n <= 0:
		return []
	if n == 1:
		return [pairs[0]]
	return [pairs[round(i * (len(pairs) - 1) / (n - 1))] for i in range(n)]


def liens_frontiere(prefixe, lieu_a, ligne_a, lieu_b, ligne_b, noms, libelles):
	"""(docs, refus, avertissements) : un lien `<prefixe>_NN` par nom de `noms` (ordonnés comme
	les deux lignes), posés UNE CASE SUR DEUX le long de la frontière (`postes`), chaque nœud
	libellé « <nom> — <libellé de son lieu> ».

	Les noms sont comptés pour le côté le PLUS LONG (`ceil(len / 2)`) : l'autre côté, plus
	court, porte parfois deux liens sur une case. Compte qui ne tombe pas juste ⇒ avertissement
	(la grille a bougé : la liste de noms est à revoir), le lot reste posable."""
	if not ligne_a or not ligne_b:
		manque = lieu_a if not ligne_a else lieu_b
		return [], [f"{prefixe} : aucune case de frontière sur {manque}"], []
	n = len(noms)
	attendu = max((len(ligne_a) + 1) // 2, (len(ligne_b) + 1) // 2)
	avert = [] if n == attendu else [f"{prefixe} : {n} nom(s) pour {attendu} poste(s) — "
		f"frontière de {len(ligne_a)} case(s) sur {lieu_a}, {len(ligne_b)} sur {lieu_b}"]
	docs = []
	for i, (nom, pos_a, pos_b) in enumerate(zip(noms, postes(ligne_a, n), postes(ligne_b, n)), start=1):
		doc = connexion(f"{prefixe}_{i:02d}", lieu_a, pos_a, lieu_b, pos_b)
		for noeud in doc["nodes"]:
			noeud["label"] = f"{nom} — {libelles.get(noeud['lieu'], noeud['lieu'])}"
		docs.append(doc)
	return docs, [], avert


def libelle_sortie(cite_label, nom):
	return f"{cite_label} — {SORTIES_LIBELLES.get(nom, nom)}"


def libelles_de(*listes):
	"""_id → label des docs donnés (les derniers gagnent)."""
	return {d["_id"]: d.get("label") or d["_id"] for liste in listes for d in liste if d.get("_id")}


def sans_rev(doc):
	return {k: v for k, v in doc.items() if k != "_rev"}


# ── La plaine et ses cités ───────────────────────────────────────────────────────────────
def lieux_a_creer(docs, taille_fn):
	"""(plaine, [cités], refus) — docs SANS grille des lieux ABSENTS du dump."""
	ids = {d.get("_id") for d in docs}
	plaines, cites, refus = [], [], []
	if PLAINE not in ids:
		plaines, refus = cartes_a_creer([IMAGE_PLAINE], docs, taille_fn)
		if not plaines and not refus:
			refus.append(f"{IMAGE_PLAINE} : déjà citée par un autre lieu, ou absente de CARTES")
	manquantes = [nom for nom in IMAGES_CITES
		if f"lieu:{os.path.splitext(nom)[0].rsplit('_city', 1)[0]}" not in ids]
	if manquantes:
		cites, refus_c = villes_a_creer(manquantes, docs, taille_fn)
		refus += refus_c
	for cite in cites:
		cite["lieu_parent"] = PLAINE
	return (plaines[0] if plaines else None), sorted(cites, key=lambda c: c["_id"]), refus


def connexions_cite(cite_id, zone_cite, zone_plaine, cite_label=None):
	"""(docs, refus) des liens plaine ↔ cité ; le nœud de la cité libellé par sa sortie."""
	slug = cite_id.split(":", 1)[1]
	sorties = SORTIES_CITES[cite_id]
	centre = POSITIONS_PLAINE[cite_id]
	if centre not in zone_plaine:
		return [], [f"{cite_id} : la case {list(centre)} de la plaine n'est pas dans sa zone de terre"]
	cases_plaine = cases_autour(zone_plaine, centre, len(sorties))
	if not cases_plaine:
		return [], [f"{cite_id} : pas {len(sorties)} cases libres autour de {list(centre)} sur la plaine"]
	docs, refus = [], []
	for (nom, cible), pos_plaine in zip(sorties.items(), cases_plaine):
		pos_cite = case_proche(zone_cite, cible)
		if pos_cite is None:
			refus.append(f"{cite_id} : aucune case de sa zone principale pour la sortie {nom}")
			continue
		doc = connexion(f"link:plaine_europeenne_to_{slug}_{nom}", PLAINE, pos_plaine, cite_id, pos_cite)
		doc["nodes"][1]["label"] = libelle_sortie(cite_label or cite_id, nom)
		docs.append(doc)
	return docs, refus


def connexions_france_plaine(zone_france, zone_plaine, libelles):
	"""(docs, refus, avertissements) des liens France ↔ plaine (`PASSAGES_PLAINE`)."""
	x_min, x_max, y_min, y_max = NORD_FRANCE
	au_dela = {(x, y) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)} - zone_france
	return liens_frontiere("link:france_to_plaine_europeenne",
		FRANCE, ligne_frontiere(zone_france, au_dela, DEPART_FRANCE_NORD),
		PLAINE, ligne_frontiere(zone_plaine, bande(FRONTIERE_PLAINE, "sud", DIMS), DEPART_PLAINE),
		PASSAGES_PLAINE, libelles)


def construire(docs, taille_fn, proposer_fn, france):
	"""(lieux, liens, refus, propositions, avertissements) de la plaine, de ses cités et des liens France ↔ plaine.

	`proposer_fn(doc, profil) -> {cells, nav, rapport}` : grille d'un lieu NEUF (Pillow côté
	CLI). Lieu déjà en base : son doc relu, seule la frontière y est appliquée.
	`lieux` = docs complets (`_rev` retiré), émis par l'appelant s'ils diffèrent du dump.
	`france` : le doc de la France TEL QU'IL SERA ÉCRIT (frontière espagnole posée par
	`gen_france_espagne_italie`) — lu ici, jamais modifié."""
	par_id = {d.get("_id"): d for d in docs}
	plaine_neuve, cites_neuves, refus = lieux_a_creer(docs, taille_fn)
	if refus:
		return [], [], refus, {}, []
	propositions = {}
	lieux = []
	neufs = ([plaine_neuve] if plaine_neuve else []) + cites_neuves
	for doc in neufs:
		prop = proposer_fn(doc, "pays" if doc["_id"] == PLAINE else "")
		propositions[doc["_id"]] = prop
		lieux.append(poser_grille(doc, prop))
	ids_neufs = {d["_id"] for d in lieux}
	for _id in [PLAINE] + sorted(POSITIONS_PLAINE):
		if _id not in ids_neufs:
			lieux.append(sans_rev(copy.deepcopy(par_id[_id])))
	par_lieu = {d["_id"]: d for d in lieux}

	plaine = par_lieu[PLAINE]
	dims = plaine["dimensions"]
	fermer(plaine["cells"], cases_frontiere(FRONTIERE_PLAINE, "sud", dims["x"], dims["y"]))
	zone_plaine = zone_de(plaine["cells"], plaine.get("nav") or {}, ANCRE_PLAINE)
	zone_france = zone_de(france.get("cells") or [], france.get("nav") or {}, ANCRE_FRANCE)

	libelles = libelles_de(docs, lieux, [france])
	liens, refus, avert = connexions_france_plaine(zone_france, zone_plaine, libelles)
	for cite_id in sorted(POSITIONS_PLAINE):
		cite = par_lieu[cite_id]
		d, r = connexions_cite(cite_id, zone_de(cite["cells"], cite.get("nav") or {}), zone_plaine,
			libelles[cite_id])
		liens += d
		refus += r
	return lieux, liens, refus, propositions, avert

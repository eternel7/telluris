# utils/chasse.py
# Quêtes de « chasse » : traquer et tuer UN ennemi d'une espèce donnée, marqué d'un PROFIL
# ÉLEVÉ, dans un lieu précis. Deux canaux :
# - Le TABLEAU de la guilde (`categorie:"guilde_aventurier"`) — grade visé = `max−1`.
# - Le PNJ du COMPTOIR (`categorie:"guilde_aventurier_comptoir"`) — grade visé = `max`, et
#   seulement comme CONDITION de gain de rang de guilde (rang propre à la cité = lieu_parent).
#   Une narration pré-combat annonce l'élite « couverte du sang de ses victimes ».
#
# Le grade (profil) est RÉSOLU À LA GÉNÉRATION (pas au combat) : à partir du lieu cible, d'une
# position dans une zone d'influence qui contient l'espèce, et de la distribution de grades
# résolue à cette position (`resolve_profil_weights`), FILTRÉE par `restriction_tags ⊆ tags de
# l'espèce` (un loup sans tag « magie » ne devient jamais un profil « magie »). Le `profil_id`
# est stocké dans l'objectif ; au combat, un seul monstre de l'espèce, s'il est tiré
# naturellement, se voit forcer ce profil (cf. routers/combat.py).
#
# Rang de guilde v1 = prestige/affichage seul : stocké par cité dans
# `character["rangs_guilde"] = {"lieu:auxerre": "F"}` (échelle recrutement.RANGS), sans effet
# mécanique encore. L'offre de rang est tirée à l'entrée du comptoir et persistée en champ
# transitoire `character["rang_offert"]` — même sémantique que `transport_offert`/`pnj_present`.
#
# ⚠️ Chaque guilde a son PLAFOND (`rang_max` sur le doc du comptoir, défaut world-var
# `RANG_GUILDE_MAX_DEFAUT = "D"`) : elle ne promeut pas au-delà de ce que son bestiaire justifie.
# Sans lui, le comptoir d'Auxerre proposait de passer D → C pour des loups et des sangliers.
# Aller plus haut demande la guilde d'une AUTRE cité — c'est le plafond, et non le sommet de
# l'échelle, qui coupe les offres (`rang_plafond_atteint`) et arme le flag de dialogue `rang_max`.
#
# Logique pure (DB injectée : get_doc_fn / find_docs_fn), mute sans save — l'endpoint persiste.
# Pattern de utils/transport.py. World-vars lues via le module (jamais from-import).

import random
import uuid

from models import character_stats
from utils.zones import (
	load_zone_defs_for_lieu, compute_zone_intensity, resolve_profil_weights,
	profils_compatibles,
)
from utils.characters import lieu_label
from utils.recrutement import RANGS
from utils import quetes


# Paramètres de génération du grade : « le plus haut possible » vs « juste en dessous ».
TIER_MAX = "max"
TIER_MAX_MOINS_1 = "max_moins_1"

# Marge de sécurité, en cases, entre la position d'une chasse et le bord de la carte : le joueur
# doit pouvoir tourner autour de la case cible (zone 3×3 de `dans_zone_chasse`) sans buter sur le
# vide, et l'overlay 🗺️ recadre une fenêtre CENTRÉE dessus — collée au bord, elle serait à moitié
# hors image.
MARGE_BORDS = 2


def est_comptoir(lieu_doc: dict) -> bool:
	"""Le lieu est-il un comptoir de guilde (donneur des quêtes de RANG) ?"""
	return (lieu_doc or {}).get("categorie") == "guilde_aventurier_comptoir"


# ── Lieux & position de chasse ───────────────────────────────────────────────────

def lieux_chasse_de(cite_id: str, get_doc_fn, find_docs_fn) -> list:
	"""Lieux où une quête de chasse de la cité peut se dérouler : la cité elle-même PLUS
	ses lieux rattachés (`lieu_parent == cité`) qui portent à la fois `rencontres` et
	`zone_influences` (sans quoi ni espèce à traquer, ni zone où résoudre le grade).
	Aujourd'hui seule la cité Auxerre remplit ça ; l'ouverture aux enfants est future-proof.

	⚠️ Requête PROJETÉE sur les seuls champs consommés en aval — sans quoi elle rapatrie les
	`cells` de chaque enfant de la cité (44 docs, ~30 Ko à Auxerre) pour n'en garder que des
	`_id`. Les champs listés sont exactement ceux que lisent `especes_du_parent`,
	`position_de_chasse`, `_profils_compatibles` et `_construire_quete_rang` (`label`)."""
	out = []
	cite = get_doc_fn(cite_id) if cite_id else None
	if cite is not None:
		out.append(cite)
	enfants = (find_docs_fn(
		{"type": "lieu", "lieu_parent": cite_id},
		["_id", "type", "label", "nom", "rencontres", "zone_influences", "profil_weights", "dimensions"],
	) or []) if cite_id else []
	for l in enfants:
		if l.get("_id") == cite_id:
			continue
		if l.get("rencontres") and l.get("zone_influences"):
			out.append(l)
	return out


def _zones_de_lespece(lieu_doc: dict, espece_id: str) -> set:
	"""Ids de zones d'influence (`rencontres[].zones`) où l'espèce peut apparaître."""
	return {
		z for r in (lieu_doc or {}).get("rencontres", [])
		if r.get("espece") == espece_id for z in (r.get("zones") or [])
	}


def _borner_axe(v: int, taille: int, marge: int) -> int:
	"""Coordonnée ramenée dans `[marge, taille−1−marge]`. ⚠️ Sur une carte trop étroite pour la
	marge (intervalle vide), on retombe sur le MILIEU de l'axe plutôt que de croiser les bornes :
	mieux vaut une case centrale qu'une case hors grille."""
	hi = taille - 1 - marge
	if hi < marge:
		return max(0, (taille - 1) // 2)
	return max(marge, min(hi, v))


def borner_position(pos: dict | None, dimensions: dict | None, marge: int = MARGE_BORDS) -> dict | None:
	"""Position `{x,y}` ramenée DANS la grille du lieu, à `marge` cases des bords.
	`dimensions` = comptes de cases (`{"x":86,"y":48}` ⇒ indices valides 0..85 / 0..47) — convention
	de `combat._iter_cells` et du client, pas la borne inclusive de `move_character`.
	`pos` à None (objectif sans position) ou `dimensions` absentes/nulles ⇒ renvoyé tel quel."""
	if not pos or not dimensions:
		return pos
	w, h = int(dimensions.get("x", 0) or 0), int(dimensions.get("y", 0) or 0)
	if w <= 0 or h <= 0:
		return pos
	return {
		"x": _borner_axe(int(pos.get("x", 0)), w, marge),
		"y": _borner_axe(int(pos.get("y", 0)), h, marge),
	}


def _anneau(x0: int, y0: int, r: int):
	"""Cases à distance de Chebyshev EXACTEMENT `r` de (x0, y0), sans doublon (`r=0` → le centre).
	Ne parcourt que le PÉRIMÈTRE de l'anneau : la recherche en spirale reste en O(rayon²) au total
	au lieu de l'O(rayon³) d'un balayage carré par rayon."""
	if r <= 0:
		yield (x0, y0)
		return
	for dx in range(-r, r + 1):
		yield (x0 + dx, y0 - r)
		yield (x0 + dx, y0 + r)
	for dy in range(-r + 1, r):
		yield (x0 - r, y0 + dy)
		yield (x0 + r, y0 + dy)


def case_praticable_proche(pos: dict | None, lieu_doc: dict, marge: int = MARGE_BORDS) -> dict | None:
	"""Case PRATICABLE la plus proche de `pos` (spirale de Chebyshev), sans jamais sortir de la
	fenêtre `[marge, dim−1−marge]` — un point borné ne doit pas être repoussé contre le bord par
	la recherche.

	Praticabilité déléguée à `combat._walkable` (`>= 1` et pas une falaise), **source unique** du
	terrain franchissable : c'est déjà le prédicat du déplacement joueur en exploration, via l'A*
	de `focalisation.direction_vers`. Import PARESSEUX, comme là-bas — `utils.combat` importe
	`utils.quetes`, dont dépend ce module, et `chasse` tient à ne pas tirer le moteur de combat.

	⚠️ Repli sur `pos` INCHANGÉE si le lieu n'a pas de `cells` ou si la fenêtre n'offre aucune case
	praticable : la position reste bornée (comportement d'avant), on ne supprime jamais la quête
	pour autant. Une carte dont les `cells` manquent ou sont toutes bloquées est un problème
	d'authoring — le prix à payer ne doit pas être la disparition silencieuse des chasses.
	⚠️ La case rendue est praticable, pas forcément DANS la forme de la zone ni CONNECTÉE à la
	région du joueur (`nav` et enclaves ignorés) — cf. la limitation documentée dans CLAUDE.md."""
	cells = (lieu_doc or {}).get("cells")
	if not pos or not cells or not cells[0]:
		return pos
	from utils.combat import _walkable  # import paresseux (cf. focalisation.direction_vers)
	# Fenêtre autorisée dérivée de la grille RÉELLE, la seule que `_walkable` sait indexer.
	w, h = len(cells[0]), len(cells)
	lo_x, hi_x = _borner_axe(0, w, marge), _borner_axe(w - 1, w, marge)
	lo_y, hi_y = _borner_axe(0, h, marge), _borner_axe(h - 1, h, marge)
	x0, y0 = int(pos.get("x", 0)), int(pos.get("y", 0))
	# Rayon max = distance de Chebyshev au coin le plus éloigné de la fenêtre → celle-ci est
	# balayée ENTIÈREMENT avant de renoncer, même si `dimensions` et `cells` se contredisent
	# (le point de départ est alors hors de la grille réelle).
	rmax = max(abs(x0 - lo_x), abs(x0 - hi_x), abs(y0 - lo_y), abs(y0 - hi_y))
	for r in range(0, rmax + 1):
		for x, y in _anneau(x0, y0, r):
			if lo_x <= x <= hi_x and lo_y <= y <= hi_y and _walkable(cells, x, y):
				return {"x": x, "y": y}
	return pos


def position_de_chasse(lieu_doc: dict, espece_doc: dict) -> dict | None:
	"""Centre `{x,y}` d'un placement d'une zone qui CONTIENT l'espèce (tiré au hasard), BORNÉ à la
	grille du lieu à `MARGE_BORDS` cases des bords puis ramené sur une case PRATICABLE, pour
	stocker dans l'objectif et résoudre le grade. `None` si le lieu n'a pas de grille
	(`dimensions`) ou si aucune zone de l'espèce n'est placée."""
	if not lieu_doc or not lieu_doc.get("dimensions"):
		return None
	zones_cibles = _zones_de_lespece(lieu_doc, (espece_doc or {}).get("_id"))
	if not zones_cibles:
		return None
	placements = [
		p for p in lieu_doc.get("zone_influences", []) if p.get("zone") in zones_cibles
	]
	if not placements:
		return None
	p = random.choice(placements)
	# ⚠️ Le centre d'un placement n'est PAS garanti dans la grille : une zone d'influence peut
	# légitimement déborder du bord (bbox négatives fréquentes), et rien ne valide les bornes ni
	# dans l'éditeur ni dans `PUT /lieu/{id}/zone_influences`. `lieu:auxerre` porte ainsi un
	# placement centré en x=86 sur une carte de 86 cases : la chasse envoyait le joueur sur une
	# case fantôme, hors image.
	pos = borner_position({"x": p.get("x", 0), "y": p.get("y", 0)}, lieu_doc.get("dimensions"))
	# ⚠️ Borner ne suffit pas : une case DANS la carte peut être un mur ou une falaise, et le
	# joueur ne pourrait alors jamais entrer dans le 3×3 de `dans_zone_chasse`. On repart donc
	# sur la case praticable la plus proche.
	return case_praticable_proche(pos, lieu_doc)


def _profils_compatibles(lieu_doc: dict, espece_doc: dict, position: dict | None, get_doc_fn) -> list:
	"""Docs profil candidats au grade de l'élite : distribution résolue aux zones de l'espèce
	(placements actifs à la position si fournie, sinon tous), FILTRÉE par
	`restriction_tags ⊆ tags de l'espèce`. Liste vide si aucune distribution ou aucun compatible."""
	zones_cibles = _zones_de_lespece(lieu_doc, (espece_doc or {}).get("_id"))
	if not zones_cibles:
		return []
	placements = [
		p for p in (lieu_doc or {}).get("zone_influences", []) if p.get("zone") in zones_cibles
	]
	if position is not None:
		zone_defs = load_zone_defs_for_lieu(lieu_doc, get_doc_fn)
		px, py = position.get("x", 0), position.get("y", 0)
		actifs = [
			p for p in placements
			if compute_zone_intensity(px, py, p, zone_defs.get(p.get("zone"))) > 0.0
		]
		# Si aucun placement de la cible n'est actif au point tiré, on retombe sur tous
		# les placements de l'espèce (le point est le centre de l'un d'eux, mais un point
		# hors des autres formes ne doit pas rétrécir la distribution à vide). C'est aussi
		# ce repli qui absorbe le BORNAGE de `position_de_chasse` : un centre ramené dans la
		# grille peut sortir de sa propre forme (zone débordant du bord de carte), et le grade
		# doit rester celui des placements de l'espèce.
		placements = actifs or placements
	pw = resolve_profil_weights(placements, lieu_doc)
	if not pw:
		return []
	# Prédicat PARTAGÉ (`zones.profil_compatible`) — surtout pas une copie locale : la même
	# règle décide du grade d'une élite ici, de l'accompagnement dans `instantiate_monsters`
	# et de la cible d'une commission dans `utils/donjon.py`.
	return profils_compatibles([p for p in (get_doc_fn(pid) for pid in pw) if p], espece_doc)


def resoudre_profil_chasse(lieu_doc: dict, espece_doc: dict, tier: str,
                           position: dict | None, get_doc_fn) -> str | None:
	"""`profil_id` de l'élite à traquer, RÉSOLU À LA GÉNÉRATION. Grade le plus haut possible
	(`tier="max"`) ou juste en dessous (`"max_moins_1"`) parmi les profils compatibles avec
	l'espèce. Égalité de niveau → tirage au hasard. `None` si aucun profil compatible."""
	compat = _profils_compatibles(lieu_doc, espece_doc, position, get_doc_fn)
	if not compat:
		return None
	niveaux = sorted({int(p.get("niveau", 1)) for p in compat})
	niv_max = niveaux[-1]
	cible_niv = niv_max - 1 if tier == TIER_MAX_MOINS_1 else niv_max
	# Candidats de niveau exactement visé ; à défaut, le compatible de niveau le plus proche
	# PAR EN-DESSOUS (repli : le plus bas disponible, si la cible tombe sous le minimum).
	choix = [p for p in compat if int(p.get("niveau", 1)) == cible_niv]
	if not choix:
		en_dessous = [p for p in compat if int(p.get("niveau", 1)) <= cible_niv]
		if en_dessous:
			meilleur = max(int(p.get("niveau", 1)) for p in en_dessous)
			choix = [p for p in en_dessous if int(p.get("niveau", 1)) == meilleur]
		else:
			choix = [p for p in compat if int(p.get("niveau", 1)) == niveaux[0]]
	return random.choice(choix)["_id"]


# ── Quêtes de chasse actives ─────────────────────────────────────────────────────

def quetes_chasse_actives(character: dict, lieu_id: str) -> list:
	"""Quêtes actives de type `chasse` dont l'objectif se déroule dans `lieu_id`."""
	out = []
	for q in (character or {}).get("quetes_actives", []):
		obj = q.get("objectif", {})
		if obj.get("type") == "chasse" and obj.get("lieu") == lieu_id:
			out.append(q)
	return out


def direction_cardinale_simple(depuis_xy, vers_xy) -> str:
	"""Direction cardinale de `vers_xy` PAR RAPPORT À `depuis_xy`, règle par axe (`y` croît
	vers le BAS) : sud si `depuis.y < vers.y`, nord si `>`, rien si égal ; est si
	`depuis.x < vers.x`, ouest si `>`, rien si égal. Combinée → « sud-est », « nord »,
	« ouest »… ; chaîne vide si même case (aucun axe ne départage)."""
	dx0, dy0 = int(depuis_xy[0]), int(depuis_xy[1])
	dx1, dy1 = int(vers_xy[0]), int(vers_xy[1])
	ns = "sud" if dy0 < dy1 else ("nord" if dy0 > dy1 else "")
	ew = "est" if dx0 < dx1 else ("ouest" if dx0 > dx1 else "")
	return "-".join(p for p in (ns, ew) if p)


def dans_zone_chasse(objectif: dict, position_joueur: dict | None) -> bool:
	"""Le combat est-il déclenché dans la zone 3×3 centrée sur la position de la quête ?
	L'élite n'est marquée que là. Sans `position` (lieu sans grille) → True (contrainte de
	lieu seule, comportement historique). Position du joueur absente → False."""
	pq = (objectif or {}).get("position")
	if not pq:
		return True
	pos = position_joueur or {}
	jx, jy = pos.get("x"), pos.get("y")
	if jx is None or jy is None:
		return False
	return abs(int(jx) - int(pq.get("x", 0))) <= 1 and abs(int(jy) - int(pq.get("y", 0))) <= 1


def chasse_accomplie(q: dict) -> bool:
	"""L'élite de cette chasse est-elle déjà tombée ? Une quête accomplie RESTE dans
	`quetes_actives` jusqu'à ce que le joueur la rende à son donneur — il faut donc pouvoir la
	distinguer de celle qui est encore à faire.

	⚠️ `quantite` par défaut **1** et non 0 (contrairement à `quetes.objectif_atteint`, générique) :
	une chasse vise toujours une cible, et `0 >= 0` ferait passer pour accomplie une quête dont
	l'objectif ne porte pas le champ."""
	obj = (q or {}).get("objectif") or {}
	return int((q or {}).get("progress", 0) or 0) >= int(obj.get("quantite", 1) or 1)


def marquer_elites(character: dict, monstres: list, lieu_id: str, pool_especes: list,
                   get_doc_fn, snapshot_fn) -> str | None:
	"""Promeut en élite un monstre par chasse EN COURS dans ce lieu, dont la zone 3×3 contient
	le joueur : le grade a été résolu à la génération, on l'applique tel quel (`snapshot_fn` =
	`combat.build_monster_snapshot`, injecté pour garder ce module pur). Mute `monstres` en
	place ; renvoie la narration pré-combat de la variante « rang », s'il y en a une. On ne
	force JAMAIS l'apparition de l'espèce : si elle n'est pas au pool, rien n'est marqué.

	⚠️ Une chasse ACCOMPLIE mais pas encore rendue reste dans `quetes_actives` : sans le filtre
	`chasse_accomplie`, elle réclamerait encore son élite et la VOLERAIT au contrat encore à
	faire visant la même espèce (le premier de la liste gagne, et `promus` interdit de servir
	deux fois le même monstre). Le joueur abattait bien la bête, mais le crédit retombait sur le
	contrat déjà rempli : deux chasses au même gibier devenaient inachevables l'une après
	l'autre — chaque kill semblait annuler le résultat de la précédente.

	⚠️ **UNE BÊTE, UN CONTRAT** : `promus` interdit de servir deux fois le même spécimen. Si le
	combat n'en offre pas un par contrat, le contrat non servi n'a simplement pas de cible ICI —
	il attend le combat suivant. Un monstre ne porte donc jamais qu'un seul `quete_chasse`."""
	especes = {e["_id"]: e for e in (pool_especes or []) if e.get("_id")}
	narration = None
	promus = set()          # ids des monstres déjà promus dans cette passe
	for q in quetes_chasse_actives(character, lieu_id):
		if chasse_accomplie(q):
			continue
		obj = q.get("objectif", {})
		espece_id, profil_id = obj.get("cible"), obj.get("profil")
		qid = q.get("id") or q.get("_id")
		if not espece_id or not profil_id or not qid:
			continue
		# L'élite ne surgit que si le combat se déclenche dans la zone 3×3 autour de la
		# position de la quête (la carte 🗺️ y mène le joueur). Sans position → lieu seul.
		if not dans_zone_chasse(obj, character.get("position")):
			continue
		idx = next(
			(i for i, m in enumerate(monstres)
			 if m.get("espece_id") == espece_id and m["id"] not in promus),
			None,
		)
		if idx is None:
			continue
		espece_doc = especes.get(espece_id)
		profil_doc = get_doc_fn(profil_id)
		if not espece_doc or not profil_doc:
			continue
		ancien = monstres[idx]
		elite = snapshot_fn(espece_doc, profil_doc, idx)
		elite["id"] = ancien["id"]
		elite["pos"] = ancien.get("pos", elite["pos"])
		elite["quete_chasse"] = qid
		monstres[idx] = elite
		promus.add(elite["id"])
		if q.get("source") == "rang" and q.get("narration"):
			narration = q["narration"]
	return narration


# ── Rang de guilde (par cité) ────────────────────────────────────────────────────

def rang_de(character: dict, cite_id: str) -> str:
	"""Rang courant du perso pour cette cité (repli `F` = débutant)."""
	return (character or {}).get("rangs_guilde", {}).get(cite_id, RANGS[0])


def meilleur_rang(rangs_guilde: dict) -> str:
	"""Le rang le plus élevé obtenu par le personnage, toutes cités confondues (RANGS =
	échelle croissante F→S+). 'aucun' si le personnage n'a encore aucun rang."""
	if not rangs_guilde:
		return "aucun"
	return max(rangs_guilde.values(), key=lambda r: RANGS.index(r) if r in RANGS else -1)


def rangs_guilde_title(rangs_guilde: dict, get_doc_fn) -> str:
	"""Détail par ville du rang affiché (infobulle du `meilleur_rang`) : une ligne
	'Ville : Rang' par cité, triées par id de lieu. `get_doc_fn` résout le nom de chaque
	cité (DB injectée, comme le reste du module)."""
	return "\n".join(
		f"{(get_doc_fn(lid) or {}).get('nom', lid)} : {r}"
		for lid, r in sorted((rangs_guilde or {}).items())
	)


def rang_suivant(rang: str) -> str:
	"""Rang immédiatement au-dessus (plafonné au sommet). Rang inconnu → premier de l'échelle."""
	try:
		i = RANGS.index(rang)
	except ValueError:
		return RANGS[0]
	return RANGS[min(i + 1, len(RANGS) - 1)]


def rang_max_atteint(rang: str) -> bool:
	"""Le SOMMET DU MONDE (`RANGS[-1]`) est-il atteint ? Repère de l'échelle, PAS le garde de
	production : ce qui décide si une guilde a encore quelque chose à offrir est
	`rang_plafond_atteint`, borné par le comptoir et non par l'échelle entière."""
	return rang == RANGS[-1]


def _index_rang(rang: str) -> int:
	"""Position d'un rang sur l'échelle ; rang inconnu → 0 (miroir de `rang_suivant`, qui retombe
	sur `RANGS[0]`) : un rang illisible n'est pas un rang élevé."""
	try:
		return RANGS.index(rang)
	except ValueError:
		return 0


def rang_max_de(comptoir_doc: dict) -> str:
	"""Rang le plus élevé que CE comptoir peut délivrer : champ `rang_max` de son doc lieu, repli
	sur la world-var `RANG_GUILDE_MAX_DEFAUT`. Une guilde ne promeut pas au-delà de ce que son
	bestiaire justifie — monter plus haut demande la guilde d'une autre cité.

	⚠️ Valeur hors échelle (côté donnée comme côté world-var) → `RANGS[0]`, donc plus aucune offre
	ici : un plafond qu'on ne sait pas lire ne doit pas devenir PERMISSIF. Le symptôme est bruyant
	(le comptoir ne propose plus rien), là où un repli sur le sommet passerait inaperçu."""
	brut = (comptoir_doc or {}).get("rang_max")
	if brut in RANGS:
		return brut
	defaut = character_stats.RANG_GUILDE_MAX_DEFAUT
	return defaut if defaut in RANGS else RANGS[0]


def rang_plafond_atteint(rang_courant: str, comptoir_doc: dict) -> bool:
	"""Ce comptoir n'a-t-il plus rien à offrir au personnage ? (rang courant ≥ son plafond).
	C'est ce prédicat — et non `rang_max_atteint` — qui coupe les offres d'épreuve et qui arme le
	flag de dialogue `rang_max` (« au sommet de ce que CETTE guilde peut t'offrir »)."""
	return _index_rang(rang_courant) >= _index_rang(rang_max_de(comptoir_doc))


def promouvoir(character: dict, cite_id: str) -> str:
	"""Monte d'un cran le rang du perso pour cette cité (mute, sans save). Renvoie le nouveau rang."""
	rangs = character.setdefault("rangs_guilde", {})
	rangs[cite_id] = rang_suivant(rangs.get(cite_id, RANGS[0]))
	return rangs[cite_id]


def crediter_rang(character: dict, spec) -> str | None:
	"""INSCRIT le personnage à un rang de guilde porté par la récompense d'une quête (mute,
	sans save). `spec` = `{"cite": "lieu:x", "rang": "F"}`, déjà RÉSOLU à la génération de
	l'offre — le module ne relit aucun doc.

	C'est le pendant de `promouvoir` pour l'ENTRÉE dans la guilde : l'épreuve de rang monte
	d'un cran, une première mission inscrit à un cran donné. Sans elle, un personnage qui
	vient de recevoir sa carte d'aventurier restait à `rangs_guilde == {}`, donc « aucun » à
	l'affichage — alors que tout le moteur le traitait déjà comme `RANGS[0]` (`rang_de`,
	`acces.rang_min_satisfait`) et que le comptoir lui proposait déjà l'épreuve suivante.

	⚠️ Ne RÉTROGRADE JAMAIS : on garde le plus élevé des deux crans. Une mission d'inscription
	rejouée (ou copiée dans une guilde où l'on est déjà mieux classé) ne peut rien retirer.
	⚠️ FAIL-CLOSED : cité manquante ou rang hors `RANGS` ⇒ rien n'est écrit (même refus qu'un
	seuil illisible dans `acces`) — on n'invente pas un cran sur une donnée qu'on ne sait pas
	lire. Renvoie le rang effectif si le doc a CHANGÉ, None sinon (rien à faire, ou déjà
	mieux classé : c'est ce qui rend la récompense inoffensive une seconde fois)."""
	if not isinstance(spec, dict):
		return None
	cite = spec.get("cite")
	rang = spec.get("rang")
	if not cite or rang not in RANGS:
		return None
	rangs = character.setdefault("rangs_guilde", {})
	courant = rangs.get(cite)
	if courant in RANGS and _index_rang(courant) >= _index_rang(rang):
		return None
	rangs[cite] = rang
	return rang


# ── Offre de rang au comptoir (miroir simplifié du transport authoré) ─────────────

# Qualificatifs de l'élite traquée, INDEXÉS PAR NIVEAU DE PROFIL (1 → 6). Le `nom` du doc
# `profil:*` est taillé pour un aventurier (« Novice », « Seigneur mage ») : collé sur une bête,
# il sonne faux. On lui substitue ici, POUR LES QUÊTES DE CHASSE SEULEMENT, une échelle de
# bestiaire. Le doc profil n'est pas modifié (son `nom` sert partout ailleurs).
QUALIFICATIFS = ["Vicieux", "Sanguinaire", "Farouche", "Impitoyable", "Fléau", "Apocalypse"]


def qualificatif_de(profil: dict | None) -> str:
	"""Qualificatif d'élite d'un profil, d'après son `niveau` (borné aux deux extrémités : un
	profil de niveau 0 ou > 6 retombe sur le premier / le dernier de l'échelle)."""
	niv = int((profil or {}).get("niveau", 1) or 1)
	return QUALIFICATIFS[max(0, min(len(QUALIFICATIFS) - 1, niv - 1))]


def _narration_rang(nom: str, grade: str) -> str:
	"""Texte d'ambiance pré-combat quand l'élite recherchée est enfin débusquée (l'espèce
	varie → généré à la volée, pas figé dans un nœud de dialogue)."""
	return (
		f"Une odeur de charnier flotte dans l'air. La créature qui vous fait face — "
		f"{nom}, le spécimen « {grade} » que la guilde vous a chargé d'abattre — est encore "
		f"couverte du sang de ses victimes. Aucun doute : c'est elle. L'épreuve commence."
	)


def _lieu_nom(lieu_doc: dict) -> str:
	"""Délègue au chokepoint de nommage (`characters.lieu_label`) : la formule ne doit vivre
	qu'à un seul endroit — c'est de l'avoir recopiée qu'un type de quête a fini par afficher
	un `_id` au joueur."""
	return lieu_label(lieu_doc)


def _construire_quete_rang(comptoir_doc: dict, cite: str, lieu_doc: dict, espece_doc: dict,
                           position: dict | None, profil_id: str, rang_courant: str, get_doc_fn) -> dict:
	"""Doc `quete:*` d'une épreuve de rang (non persisté ; l'accept en fait un snapshot)."""
	profil = get_doc_fn(profil_id) or {}
	niv = int(profil.get("niveau", 1))
	grade = qualificatif_de(profil)
	nom = espece_doc.get("nom", "créature")
	lieu_nom = _lieu_nom(lieu_doc)
	rang_vise = rang_suivant(rang_courant)
	xp = max(1, round(quetes._xp_unitaire(espece_doc, niv) * character_stats.QUETE_CHASSE_XP_FACTEUR))
	cuivre = max(0, round(xp * character_stats.QUETE_CUIVRE_PAR_XP))
	objectif = {
		"type": "chasse",
		"cible": espece_doc["_id"],
		"lieu": lieu_doc["_id"],
		"profil": profil_id,
		"quantite": 1,
	}
	if position is not None:
		objectif["position"] = position
	sub = (comptoir_doc.get("_id", "") or "").split(":", 1)[-1]
	return {
		"_id": f"quete:{sub}_rang_{uuid.uuid4().hex[:12]}",
		"type": "quete",
		"source": "rang",
		"giver": comptoir_doc.get("_id"),
		"lieu_parent": cite,
		"titre": f"Épreuve de rang : traquer le {nom} « {grade} »",
		"description": (
			f"Le maître d'armes exige une preuve : traquez et abattez ce {nom} « {grade} », "
			f"l'élite qui écume {lieu_nom}, pour prétendre au rang {rang_vise}."
		),
		"rang": rang_vise,
		"objectif": objectif,
		"recompenses": {"xp": xp, "cuivre": cuivre, "items": []},
		"rang_vise": rang_vise,
		"narration": _narration_rang(nom, grade),
		"statut": "offerte",
	}


def _rang_deja_actif(character: dict, cite: str) -> bool:
	"""Une épreuve de rang de cette cité est-elle déjà en cours ? (pas d'empilement)."""
	for q in (character or {}).get("quetes_actives", []):
		if q.get("source") == "rang" and q.get("cite") == cite:
			return True
	return False


def offre_rang_pour(character: dict, comptoir_doc: dict, get_doc_fn, find_docs_fn) -> dict | None:
	"""Construit une épreuve de rang au comptoir, ou `None` si : pas de `lieu_parent`, PLAFOND DE
	CE COMPTOIR déjà atteint (`rang_max_de`, défaut `D` — pas le sommet du monde), épreuve de rang
	de cette cité déjà active, ou aucune cible résolvable au grade MAX. Ne tire PAS la probabilité
	(c'est `poser_rang_offert` qui la gère)."""
	cite = (comptoir_doc or {}).get("lieu_parent")
	if not cite:
		return None
	rang_courant = rang_de(character, cite)
	if rang_plafond_atteint(rang_courant, comptoir_doc):
		return None
	if _rang_deja_actif(character, cite):
		return None
	candidats = []
	for L in lieux_chasse_de(cite, get_doc_fn, find_docs_fn):
		for eid in quetes.especes_du_parent(L):
			espece = get_doc_fn(eid)
			if not espece:
				continue
			position = position_de_chasse(L, espece)
			if position is None:
				continue
			profil_id = resoudre_profil_chasse(L, espece, TIER_MAX, position, get_doc_fn)
			if profil_id:
				candidats.append((L, espece, position, profil_id))
	if not candidats:
		return None
	L, espece, position, profil_id = random.choice(candidats)
	return _construire_quete_rang(comptoir_doc, cite, L, espece, position, profil_id, rang_courant, get_doc_fn)


def poser_rang_offert(character: dict, comptoir_doc: dict, get_doc_fn, find_docs_fn,
                      pnj_present: bool = False) -> bool:
	"""Tire (une fois par entrée) une offre de rang au comptoir — même sémantique que
	`poser_transport_offert`. Persiste `character["rang_offert"] = {lieu, quete}` : un refresh
	ne re-tire pas, ressortir/rentrer re-tire. Aucune offre hors comptoir, sans PNJ présent, ou
	hors proba `QUETE_CHASSE_PROBA_RANG`. Renvoie True si le champ a changé."""
	lieu_id = (comptoir_doc or {}).get("_id")
	if not lieu_id or not est_comptoir(comptoir_doc):
		# Sortie d'un comptoir : purger un éventuel reliquat d'offre.
		if character.get("rang_offert") is not None:
			character.pop("rang_offert", None)
			return True
		return False
	deja = character.get("rang_offert")
	if isinstance(deja, dict) and deja.get("lieu") == lieu_id:
		return False
	quete = None
	if pnj_present and random.random() < float(character_stats.QUETE_CHASSE_PROBA_RANG):
		quete = offre_rang_pour(character, comptoir_doc, get_doc_fn, find_docs_fn)
	character["rang_offert"] = {"lieu": lieu_id, "quete": quete}
	return True


def offre_rang_courante(character: dict, comptoir_doc: dict) -> dict | None:
	"""L'offre de rang posée pour CE comptoir (sinon None). Lecture pure (pas de tirage)."""
	offert = character.get("rang_offert") or {}
	if offert.get("lieu") == (comptoir_doc or {}).get("_id"):
		return offert.get("quete")
	return None


def rang_a_rapporter(character: dict, cite: str) -> dict | None:
	"""Épreuve de rang de cette cité complétée (`progress >= quantite`) mais pas encore
	soldée — celle dont il faut « rendre compte » au comptoir. None sinon."""
	for q in (character or {}).get("quetes_actives", []):
		if q.get("source") == "rang" and q.get("cite") == cite and quetes.objectif_atteint(character, q):
			return q
	return None


def accepter_rang(character: dict) -> dict | None:
	"""Accepte l'offre de rang courante : pousse un snapshot actif (avec `source`/`rang_vise`/
	`cite`/`narration`, que le combat et le turn-in relisent) et vide l'offre. Mute sans save.
	Renvoie la quête active, ou None s'il n'y a pas d'offre à accepter."""
	offert = character.get("rang_offert") or {}
	offre = offert.get("quete")
	if not offre:
		return None
	snap = quetes.snapshot_quete(offre)
	snap["type"] = "quete"
	snap["source"] = "rang"
	snap["rang_vise"] = offre.get("rang_vise")
	snap["cite"] = offre.get("lieu_parent")
	snap["narration"] = offre.get("narration")
	character.setdefault("quetes_actives", []).append(snap)
	character["rang_offert"] = {"lieu": offert.get("lieu"), "quete": None}
	return snap


def solder_rang(character: dict, quete_id: str) -> dict | None:
	"""Rend compte au comptoir d'une épreuve de rang complétée : PROMEUT le perso pour la cité,
	applique XP/prime, archive la quête (mute sans save). Renvoie `{promu, recompenses}` ou
	None si la quête est introuvable / pas encore complétée."""
	actives = character.get("quetes_actives", [])
	q = next(
		(x for x in actives
		 if (x.get("id") or x.get("_id")) == quete_id and x.get("source") == "rang"),
		None,
	)
	if q is None or not quetes.objectif_atteint(character, q):
		return None
	cite = q.get("cite")
	nouveau = promouvoir(character, cite) if cite else rang_de(character, cite)
	recap = quetes.appliquer_recompenses(character, q)
	character["quetes_actives"] = [x for x in actives if x is not q]
	character.setdefault("quetes_terminees", []).append({
		"id": q.get("id") or q.get("_id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", nouveau),
		"termine_at": quetes.now_epoch(),
	})
	return {"promu": nouveau, "recompenses": recap}

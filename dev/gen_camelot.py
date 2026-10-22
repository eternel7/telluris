"""Camelot en jeu, et Londres recalée sur sa forteresse : UN fichier à importer.

Lore : docs/lore/cites/20261021_camelot_winchester.md (cité fondée par Arthur, Winchester
bourg voisin au sud, accès tôt par Douvres). Image : towns/camelot_capital.jpg.

Camelot — grille (règle de l'Auteur, 22/10/2026 : d'abord les cases 0 / 1 / 5, ensuite les
nav, seulement là où un passage non voulu reste ouvert)
- Doc de `gen_villes_images.villes_a_creer` (forme de `lieu:rhemi`). `sous_categorie`
  « ville » : Londres reste la capitale de l'île (champ sans effet en jeu).
- Grille : `utils/grille_matieres.proposer_cite` sur la base de `gen_grille_image.base_cite`
  (tracé des rues, cadre, lecture par MATIÈRES de l'image). Seules données déclarées :
  `ENCEINTE`, le polygone de la crête du rempart (la fermeture du bâti avalait le bourg), et
  `MONUMENTS`, le fort de la Table ronde et la cathédrale d'Excalibur : des LIEUX où l'on
  entrera par une connexion, pas des toits où marcher ; la pente du fort (un relief se lit
  à la couleur comme une place, mi-herbe mi-ombre) ; `CHEMINS`, la rampe qui y monte.
  Le DEDANS est ensuite remplacé par `DEDANS_TRACE`, relevé à la main sur l'image.
- Deux zones : le DEDANS (polygone) et le DEHORS (campagne + bourg), reliées par les seules
  portes de rempart. Le script refuse d'écrire sinon.
- Portes (forme de l'éditeur, `_ptDocs`, cinq docs par porte) : chaque case au plus près du
  centre de son arche, côté dehors et côté dedans. Images réutilisées : toutes les
  `porte_de_ville_*` servent déjà (Calais et Bucarest en partagent avec Auxerre).
- Sur la carte d'Angleterre, Camelot est là où est Winchester : coordonnées réelles recalées
  sur Londres et Glastonbury, puis remontées dans les terres. Ses trois entrées arrivent
  DEHORS, au plus près de leur repère.

Londres (demande de l'Auteur, 22/10/2026)
- Ses connexions descendent sur le corps de la forteresse dessinée (`LONDRES_COTES`) et la
  COUVRENT : une connexion par case de ses deux rangées hautes, 12 en tout.
  Les quatre liens existants gardent leur `_id` (relus du dump, seul leur nœud Angleterre
  bouge) ; les autres sont neufs. Chaque connexion a sa PROPRE case d'arrivée dans Londres :
  partagée, cette case porterait plusieurs boutons « Angleterre » menant ailleurs.

Usage : python dev/gen_camelot.py [--dump jsons/telluris-dump-….json] [--sans-apercu]
Sortie : jsons/camelot_a_importer.json (+ jsons/camelot_grille_apercu.png)
"""

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_villes_images as gvi  # noqa: E402
from utils import grille_matieres  # noqa: E402
from utils.lieux import nav_allows  # noqa: E402

IMAGE = "camelot_capital.jpg"
CITE = "lieu:camelot"
PAYS = "lieu:angleterre"
LONDRES = "lieu:london"
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "camelot_a_importer.json")

# Crête du rempart, sens horaire depuis le fort : mur nord, tour nord-est, mur est, porte de
# Winchester, mur sud, porte ouest (entre ses deux tours), tour ouest.
ENCEINTE = ((15, 9), (30, 9), (33, 12), (40, 12), (46, 12), (50, 12), (57, 12), (63, 14),
	(69, 15), (70, 21), (69, 27), (61, 30), (57, 32), (53, 32), (46, 32), (41, 33), (32, 31), (26, 29),
	(19, 28), (16, 25), (14, 21), (14, 17))
MONUMENTS = {
	"fort de la Table ronde": ((14, 8), (31, 8), (31, 17), (26, 20), (17, 21), (14, 19)),
	"cathédrale": ((41, 14), (50, 9), (55, 10), (58, 15), (58, 20), (47, 23), (41, 23)),
	# Relief : la pente sous le fort, entre son pied et les premières maisons.
	"pente du fort": ((14, 19), (17, 21), (26, 20), (31, 17), (33, 20), (30, 23), (22, 23), (16, 23)),
}
# La rampe qui monte de la ville à la porte du fort (seul passage par la pente).
CHEMINS = (((31, 22), (29, 20), (28, 18)),)
# Repères : la campagne (DEHORS) et le parvis de la cathédrale (DEDANS).
CAMPAGNE = (10, 40)
PARVIS = (45, 25)
# DEDANS TRACÉ À LA MAIN (Auteur, 22/10/2026) : aucun algorithme ne lit les rues du cœur sans
# passer sur un toit, la falaise ou le long de la cathédrale ; les cases praticables du dedans
# sont relevées à l'œil sur l'image, ligne y → colonnes x. Remplace le cœur calculé ; le
# rempart, le dehors et les portes restent ceux de `proposer_cite`.
DEDANS_TRACE = {
	18: (28,), 19: (28,), 20: (29, 30),                    # rampe du fort, escalier
	21: (31, 32, 33, 34),                                  # pied de l'escalier, entre les maisons
	22: (35, 40, 41, 52, 53, 54, 55),
	23: (34, 35, 36, 37, 38, 39, 40, 41, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55),
	24: (33, 34, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 54, 55),       # parvis
	25: (32, 33, 40, 42, 43, 44, 45, 46, 47, 48, 49, 54, 55),
	26: (29, 30, 31, 32, 40, 49, *range(55, 68)),                       # place du marché
	27: (27, 28, 29, 40, 49, *range(56, 64)),
	28: (25, 26, 27, 39, 50, 51, 52, 56, 57, 61, 62, 63),               # (25, 28) : porte ouest
	29: (39, 52),
	30: (52,),
	31: (52,),                                                          # porte de Winchester
}

# (nom, slug, arche, image extérieure, image intérieure, (case dehors, case dedans) IMPOSÉES)
# arche = centre (x, y), ou (x, y, dx, dy) pour imposer la direction vers le dedans.
# Cases VALIDÉES par l'Auteur (22/10/2026), « gravées dans le marbre » : la porte ouest telle
# que calculée ; la porte de Winchester dehors sous l'arche, dedans dans la rue au pied de la
# tour gauche.
PORTES = (
	("Porte ouest", "ouest", (21.5, 30),
	 "porte_de_ville_pont_exterieur04.png", "porte_de_ville_pont_interieur04.png",
	 ((21, 31), (25, 28))),
	("Porte de Winchester", "de_winchester", (56.5, 32, 0, -1),
	 "porte_de_ville_exterieure08.jpg", "porte_de_ville_interieur16.png",
	 ((57, 34), (52, 31))),
)
PORTE_TYPE = "poste de garde"
PORTE_LABEL_DEHORS = "au-delà des remparts"

# (suffixe d'_id, libellé, case sur la carte d'Angleterre, repère dans Camelot — DEHORS)
ENTREES = (
	("ouest", "Camelot — par le pont de l'ouest", (63, 38), (16, 34)),
	("sud", "Camelot — par le bourg de Winchester", (64, 39), (50, 42)),
	("est", "Camelot — par l'est", (65, 38), (78, 27)),
)

# Londres : le corps de la forteresse sur la carte d'Angleterre, ses deux rangées hautes
# (la rangée du bas, y = 37, retirée à la demande de l'Auteur : 12 connexions), groupé par
# côté.
# le long de sa case d'origine : cases voisines, une par connexion.
#   côté : (libellé, cases Angleterre, case d'arrivée de référence dans Londres, pas)
LONDRES_COTES = {
	"ouest": ("Londres — par l'ouest", ((68, 35), (68, 36), (69, 35)), (5, 22), (0, 1)),
	"fleuve": ("Londres — par le fleuve", ((69, 36),), (38, 34), (1, 0)),
	"nord": ("Londres — par le nord", ((70, 35), (71, 35), (72, 35), (73, 35)), (30, 5), (1, 0)),
	"sud": ("Londres — par le sud", ((70, 36), (71, 36)), (14, 43), (1, 0)),
	"pont": ("Londres — par le pont", ((72, 36),), (52, 30), (1, 0)),
	"est": ("Londres — par l'est", ((73, 36),), (79, 24), (0, 1)),
}
# Les quatre liens existants : leur `_id` et leur nœud Londres restent, la case Angleterre
# devient celle-ci.
LONDRES_EXISTANTS = {
	"link:angleterre_to_london_ouest": (68, 36),
	"link:angleterre_to_london_nord": (71, 35),
	"link:angleterre_to_london_sud": (70, 36),
	"link:angleterre_to_london_est": (73, 36),
}


def zone_de(cells, nav, depart) -> set:
	"""Cases praticables (valeur 1, murs nav respectés) jointes à `depart`."""
	hauteur, largeur = len(cells), len(cells[0])
	x0, y0 = depart
	if cells[y0][x0] != 1:
		return set()
	vues, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				nx, ny = x + dx, y + dy
				if ((dx or dy) and 0 <= nx < largeur and 0 <= ny < hauteur
						and (nx, ny) not in vues and cells[ny][nx] == 1
						and nav_allows(nav, x, y, dx, dy)):
					vues.add((nx, ny))
					pile.append((nx, ny))
	return vues


def plus_proche(zone: set, repere) -> tuple:
	"""Case de `zone` la plus proche d'un repère (distance euclidienne, puis (y, x))."""
	return min(zone, key=lambda c: ((c[0] - repere[0]) ** 2 + (c[1] - repere[1]) ** 2, c[1], c[0]))


def plus_proche_case(cells, repere) -> tuple:
	"""Case praticable (1) la plus proche d'un repère."""
	return min(((x, y) for y, ligne in enumerate(cells) for x, v in enumerate(ligne) if v == 1),
		key=lambda c: ((c[0] - repere[0]) ** 2 + (c[1] - repere[1]) ** 2, c[1], c[0]))


def portes(cite: str, portes_cases) -> list:
	"""Les cinq docs de chaque porte, forme de `_ptDocs` (admin_map_editor.html)."""
	base_cite = cite.split(":", 1)[1]
	sortie = []
	for nom, slug, (dehors, dedans), img_ext, img_int in portes_cases:
		base = f"{base_cite}_porte_{slug}"
		ext, int_ = f"lieu:{base}_exterieur", f"lieu:{base}_interieur"
		meta = {"type": PORTE_TYPE, "status": "ouvert"}
		sortie += [
			{"_id": ext, "type": "lieu", "label": f"{nom} — extérieur", "image": img_ext,
			 "categorie": "Porte de rempart", "lieu_parent": cite},
			{"_id": int_, "type": "lieu", "label": f"{nom} — intérieur", "image": img_int,
			 "categorie": "Porte de rempart", "lieu_parent": cite},
			{"_id": f"link:{base}_carte_exterieur", "type": "connection",
			 "nodes": [{"lieu": cite, "pos": list(dehors), "label": PORTE_LABEL_DEHORS},
					   {"lieu": ext, "pos": [0, 0]}], "metadata": dict(meta)},
			{"_id": f"link:{base}_carte_interieur", "type": "connection",
			 "nodes": [{"lieu": cite, "pos": list(dedans)}, {"lieu": int_, "pos": [0, 0]}],
			 "metadata": dict(meta)},
			{"_id": f"link:{base}_passage", "type": "connection",
			 "nodes": [{"lieu": ext, "pos": [0, 0]}, {"lieu": int_, "pos": [0, 0]}],
			 "metadata": dict(meta)},
		]
	return sortie


def connexion_camelot(suffixe: str, label: str, case_pays, case_ville) -> dict:
	return {
		"_id": f"link:angleterre_to_camelot_{suffixe}",
		"type": "connection",
		"nodes": [
			{"lieu": PAYS, "pos": list(case_pays)},
			{"lieu": CITE, "pos": list(case_ville), "label": label},
		],
		"metadata": {"type": "chemin", "status": "ouvert"},
	}


def _arrivee(zone: set, depart, pas, prises: set):
	"""Première case de `zone` libre, en partant de `depart` dans la direction `pas`, puis
	dans l'autre sens."""
	for k in range(0, 40):
		for signe in (1, -1):
			case = (depart[0] + signe * k * pas[0], depart[1] + signe * k * pas[1])
			if case in zone and case not in prises:
				return case
	return None


def connexions_londres(par_id: dict, erreurs: list) -> list:
	londres = par_id[LONDRES]
	zone = zone_de(londres["cells"], londres.get("nav") or {}, (5, 22))
	existants = {}
	for lid, case_pays in LONDRES_EXISTANTS.items():
		doc = copy.deepcopy(par_id[lid])
		doc.pop("_rev", None)
		noeud = next(n for n in doc["nodes"] if n["lieu"] == PAYS)
		noeud["pos"] = list(case_pays)
		existants[tuple(case_pays)] = doc
	prises = {tuple(next(n["pos"] for n in d["nodes"] if n["lieu"] == LONDRES))
		for d in existants.values()}
	sortie = list(existants.values())
	for cote, (label, cases, depart, pas) in LONDRES_COTES.items():
		neuves = [c for c in cases if tuple(c) not in existants]
		for i, case_pays in enumerate(neuves, 1):
			arrivee = _arrivee(zone, depart, pas, prises)
			if arrivee is None:
				erreurs.append(f"Londres {cote} : aucune case d'arrivée libre")
				continue
			prises.add(arrivee)
			sortie.append({
				"_id": f"link:angleterre_to_london_{cote}_{i:02d}",
				"type": "connection",
				"nodes": [
					{"lieu": PAYS, "pos": list(case_pays)},
					{"lieu": LONDRES, "pos": list(arrivee), "label": label},
				],
				"metadata": {"type": "chemin", "status": "ouvert"},
			})
	return sortie


def poser_dedans_trace(cells):
	"""Le dedans (centre dans `ENCEINTE`, hors ligne du rempart) prend `DEDANS_TRACE` : 1 sur
	les cases relevées, 0 ailleurs. Mute `cells`."""
	rows, cols = len(cells), len(cells[0])
	dedans = grille_matieres.dedans_polygone(ENCEINTE, cols, rows)
	anneau = grille_matieres.polygone_cases(ENCEINTE)
	for y in range(rows):
		for x in range(cols):
			if dedans[y][x] and (x, y) not in anneau:
				cells[y][x] = 1 if x in DEDANS_TRACE.get(y, ()) else 0


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = args[args.index("--dump") + 1] if "--dump" in args else None
	docs = ggi.charger_dump(chemin_dump)
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (PAYS, LONDRES, *LONDRES_EXISTANTS) if i not in par_id]
	if manquants:
		print("✗ absents du dump : " + ", ".join(manquants))
		return 1

	a_creer, refus = gvi.villes_a_creer([IMAGE], docs, gvi._taille_image)
	if refus or not a_creer:
		print("✗ " + ("; ".join(refus) or f"{IMAGE} est déjà citée par un lieu : rien à créer."))
		return 1
	doc = a_creer[0]
	doc.update({"label": "Camelot", "sous_categorie": "ville", "lieu_parent": PAYS})
	cols, rows = doc["dimensions"]["x"], doc["dimensions"]["y"]
	chemin = ggi.trouver_image(IMAGE)
	base = ggi.base_cite(chemin, cols, rows, ENCEINTE)
	cite = grille_matieres.proposer_cite(base["cells"], base["rues"], base["lecture"], ENCEINTE,
		MONUMENTS.values(), base["cadre"], chemins=CHEMINS, grille_sc=base["sous_cases"],
		portes=[p[2] for p in PORTES], masques=base["masques"],
		ancres_dehors=[e[3] for e in ENTREES], portes_imposees=[p[5] for p in PORTES])
	doc = gvi.poser_grille(doc, cite)
	poser_dedans_trace(doc["cells"])
	cells, nav = doc["cells"], doc["nav"]

	dedans, dehors = zone_de(cells, nav, plus_proche_case(cells, PARVIS)), zone_de(cells, nav, CAMPAGNE)
	erreurs = []
	if dedans & dehors:
		erreurs.append("le dedans et le dehors communiquent sans porte")
	poly = cite["dedans"]
	hors_zone = [(x, y) for y in range(rows) for x in range(cols) if cells[y][x] == 1
		and (x, y) not in dedans and (x, y) not in dehors]
	portes_cases = [(nom, slug, cases_, ie, ii)
		for (nom, slug, _centre, ie, ii, _imp), cases_ in zip(PORTES, cite["portes"])]
	for nom, _s, (c_dehors, c_dedans), _ie, _ii in portes_cases:
		if c_dehors not in dehors or c_dedans not in dedans:
			erreurs.append(f"{nom} : case dehors {c_dehors} ou dedans {c_dedans} du mauvais côté")
	reliees = grille_matieres.portes_reliees(cells, nav, [c for _n, _s, c, _e, _i in portes_cases])
	erreurs += [f"portes non reliées au {cote} : {portes_cases[i][0]} ↔ {portes_cases[j][0]}"
		for cote, i, j in reliees["manques"]]   # Camelot : dedans ET dehors (aucun fleuve ne coupe)
	entrees = [(s_, l_, p_, plus_proche(dehors, c_)) for s_, l_, p_, c_ in ENTREES]

	pays = par_id[PAYS]
	zone_pays = zone_de(pays["cells"], pays.get("nav") or {}, (78, 38))  # depuis Douvres
	for s, _l, p, _c in entrees:
		if tuple(p) not in zone_pays:
			erreurs.append(f"entrée {s} : case {p} injoignable depuis Douvres")
	for _label, cases, _d, _p in LONDRES_COTES.values():
		erreurs += [f"Londres : case {c} injoignable depuis Douvres"
			for c in cases if tuple(c) not in zone_pays]
	tous = [c for _l, cases, _d, _p in LONDRES_COTES.values() for c in cases]
	if sorted(LONDRES_EXISTANTS.values()) != sorted(c for c in tous if c in LONDRES_EXISTANTS.values()):
		erreurs.append("un lien existant de Londres n'a pas de case dans LONDRES_COTES")

	neufs = [doc] + portes(CITE, portes_cases) + [connexion_camelot(*e) for e in entrees]
	erreurs += [f"{d['_id']} déjà en base" for d in neufs if d["_id"] in par_id]
	londres = connexions_londres(par_id, erreurs)
	erreurs += [f"{d['_id']} déjà en base" for d in londres
		if d["_id"] in par_id and d["_id"] not in LONDRES_EXISTANTS]
	if erreurs:
		print("✗ " + "\n✗ ".join(erreurs))
		return 1

	sortie = neufs + londres
	if "--sans-apercu" not in args:
		ggi.ecrire_apercu(chemin, cells, os.path.join(ggi.DOSSIER_JSONS, "camelot_grille_apercu.png"),
			nav)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"rapport : {json.dumps(cite['rapport'], ensure_ascii=False, default=list)}")
	print(f"poches hors des deux zones : {len(hors_zone)} case(s)")
	for nom, _s, (c_dehors, c_dedans), _ie, _ii in portes_cases:
		print(f"   {nom} : dehors {c_dehors}, dedans {c_dedans}")
	for s_, _l, _p, c_ in entrees:
		print(f"   entrée {s_} : {c_}")
	print(f"{CITE} {cols}×{rows} · dedans {len(dedans)} cases · dehors {len(dehors)} cases · "
		f"{len(PORTES)} porte(s) · Londres {len(londres)} connexion(s) · "
		f"{len(sortie)} doc(s) → {os.path.relpath(SORTIE, ggi.RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())

"""Petra en jeu : le Levant, la cité, sa guilde, ses quatre temples-donjons et leur bestiaire —
UN fichier à importer (CLAUDE.md §18).

Lore : docs/lore/cites/20261024_histoire_de_petra.md (arbitrage de l'Auteur, 24/10/2026).
- Pays : `lieu:levant` sur `maps/levant.jpg`, grille au profil `pays` (`gen_cartes_pays`) :
  cases toutes à 1, côte murée.
- Cité : `lieu:petra` sur `towns/petra_city.jpg`. Grille relevée À LA MAIN (vue cavalière,
  falaises partout : la lecture par matières ne lit rien — même précédent que le cœur de
  Camelot). `DEDANS` / `DEHORS` = polygones praticables, `EAU` = canaux et bassins (5), tout le
  reste à 0. Le dedans et le dehors ne se rejoignent que par les deux portes (Siq, sud).
- Guilde : Le Caravansérail des Seuils, dans les coursives du grand bâtiment à cour ;
  Zaydu (comptoir) inscrit en RECONNAISSANT le rang de Lutecia (`services.don.rang_reconnu`),
  Shaqilath (bureau) mandate les QUATRE donjons (`services.commission.donjons`).
- Donjons : un temple-forteresse par tombeau royal, un Templier à chaque porte. Rangs exigés
  (Auteur, 24/10) : crue A, djinns A, trésor S, cités anéanties S+ — posés en `rang_min` sur
  la salle (ou l'étage d'entrée), lus par la porte ET par le bureau.
- Portails transversaux : Khazneh → Alexandrie, ad-Deir → Bucarest (rang A de Lutecia, celui
  qui ouvre Notre-Dame) ; le Qasr al-Bint attend Muziris (aucune connexion).
- Cartes de combat : quadrillage DESSINÉ de ~46 px (30 × 17 ; 30 × 16 pour les djinns, 60 × 33
  pour Iram), cases relevées en polygones comme la cité.

REJOUABLE : un `_id` déjà au dump est signalé et n'est pas réécrit (PUT complet, §11).

Usage : python dev/gen_petra.py [--dump jsons/telluris-dump-….json] [--apercu]
Sortie : jsons/petra_a_importer.json (+ aperçus des grilles dans jsons/ avec --apercu)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_bestiaire_arthurien import docs_bestiaire_arthurien  # noqa: E402
from dev.gen_vampires import _attrs  # noqa: E402
from utils.lieux import nav_allows  # noqa: E402

SORTIE = os.path.join(ggi.DOSSIER_JSONS, "petra_a_importer.json")
PAYS, CITE = "lieu:levant", "lieu:petra"
LUTECIA, ALEXANDRIE, BUCAREST = "lieu:lutecia", "lieu:alexandrie", "lieu:bucarest"
COLS, ROWS = 86, 48          # 1376 × 768 en cases de 16 px (côté des villes et pays du dump)

# ── Grille de la cité (coordonnées en CASES ; une case compte si son centre est dedans) ──
DEDANS = {
	"place ouest": ((21.5, 32.5), (28, 32.5), (28, 39.5), (21.5, 39.5)),
	"rue à colonnades": ((26, 33.8), (34, 33.5), (36, 32), (40, 31.3), (43, 29), (46, 26.5),
		(49, 25), (57.5, 25), (57.5, 27.5), (53, 28.5), (49, 29.8), (45, 31.5), (41, 33.5),
		(36, 35), (34, 36.8), (28, 37.5), (26, 37.5)),
	"terrasse des tombeaux": ((57.5, 25.5), (60, 25.5), (61.5, 28), (66, 30), (70, 30.3),
		(76, 31.3), (78, 31), (74, 33.5), (64, 33.5), (60, 32), (57, 31), (55.5, 29.5)),
	"quartier sud": ((27, 39), (31, 38.5), (36, 37), (40, 35), (44, 32.8), (48, 31.3), (51, 30.5),
		(51, 32), (47, 33.5), (43, 36), (42, 38), (42, 41), (39, 41), (39, 39), (34, 39.6),
		(30, 40.5), (27, 40.5)),
	"jardins": ((14.5, 22.5), (20, 21), (26, 20), (30.5, 19), (33, 21), (33, 24.5), (29, 25),
		(26, 25.5), (24, 27), (20, 28), (16, 27.3), (14.5, 26)),
	"rampe des jardins": ((22.8, 26), (25.2, 26), (25.2, 33), (22.8, 33)),
	"escalier d'ad-Deir": ((27, 20.5), (29.3, 20.5), (26.3, 13.8), (24.3, 13.8)),
	"parvis d'ad-Deir": ((20.5, 13), (26, 13), (26, 15.5), (20.5, 15.5)),
}
DEHORS = {
	"Siq": ((58.6, 3), (62.2, 3), (62.2, 21.8), (58.6, 21.8)),
	"désert nord-est": ((62, 3), (81.5, 3), (81.5, 19.5), (76, 17.3), (70, 14.3), (64.5, 10.8), (62, 10)),
	"désert sud-est": ((67, 35.8), (78, 33.2), (81.5, 32.4), (81.5, 45.6), (61.5, 45.6), (61.5, 40), (65, 37.5)),
	"bande sud": ((24, 44.7), (63, 44.7), (63, 45.6), (24, 45.6)),
}
# Canaux : polylignes d'une case de large ; bassins : polygones. Valeur 5 (eau, très difficile).
CANAUX = (
	((58.5, 25.5), (57, 27), (54, 28.3), (51, 29.4), (48, 30.8), (45, 32.3), (42, 34), (39, 35.8),
	 (36, 37.3), (33, 38.3), (30, 39.3), (27, 40.3)),
	((34, 15.5), (32, 18), (31, 20), (30.5, 22.5)),
)
BASSINS = (((57.5, 28), (61, 28), (61, 30), (57.5, 30)),)
# Cases bouchées au milieu du praticable : fontaines, caravansérail du désert.
OBSTACLES = (((23.5, 33.5), (25, 33.5), (25, 35), (23.5, 35)), ((23.5, 36.5), (25, 36.5), (25, 38), (23.5, 38)),
	((73.5, 5.5), (80.5, 5.5), (80.5, 10.5), (73.5, 10.5)))

# Portes de rempart : (nom, slug, case DEHORS, case DEDANS, image extérieure, image intérieure).
PORTES = (
	("Porte du Siq", "du_siq", (60, 21), (56, 26),
	 "porte_de_ville_petra_siq_exterieur01.jpg", "porte_de_ville_petra_siq_interieur01.jpg"),
	("Porte du sud", "du_sud", (40, 45), (40, 40),
	 "porte_de_ville_petra_sud_exterieur01.jpg", "porte_de_ville_petra_sud_interieur01.jpg"),
)
PORTE_TYPE = "poste de garde"
PORTE_LABEL_DEHORS = "au-delà des remparts"

# Entrées depuis le Levant : (suffixe, libellé, repère sur la carte du Levant, case DEHORS).
ENTREES = (
	("siq", "Petra — par le Siq", (48, 31), (60, 4)),
	("desert", "Petra — par le désert", (50, 34), (72, 40)),
)

# Monuments reliés à la cité : (slug, repère — la connexion part de la case du dedans la plus proche).
REPERES = {
	"guilde": (44, 26), "khazneh": (52, 25), "ad_deir": (23, 14), "qasr_al_bint": (22, 34),
	"urne": (64, 27), "soie": (70, 30), "corinthien": (75, 31), "palais": (72, 33),
}
# Arrivées des portails transversaux : (cité, case de départ d'une zone connue, repère visé).
ARRIVEES = {
	ALEXANDRIE: ((24, 37), (28, 33)),   # dedans, depuis la porte sud-ouest ; le Sérapéum, au sud-ouest
	BUCAREST: ((49, 20), (50, 16)),     # dedans, depuis la porte du palais ; le nord, vers Bran
}


def dans_polygone(x: float, y: float, poly) -> bool:
	dedans = False
	n = len(poly)
	for i in range(n):
		(x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
		if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
			dedans = not dedans
	return dedans


def peindre(cells, polys, valeur):
	for y, ligne in enumerate(cells):
		for x in range(len(ligne)):
			if any(dans_polygone(x + 0.5, y + 0.5, p) for p in polys):
				ligne[x] = valeur


def peindre_polyligne(cells, points, valeur, demi=0.5):
	"""Les cases dont le centre est à moins de `demi` case du tracé."""
	for y, ligne in enumerate(cells):
		for x in range(len(ligne)):
			cx, cy = x + 0.5, y + 0.5
			for (x1, y1), (x2, y2) in zip(points, points[1:]):
				dx, dy = x2 - x1, y2 - y1
				t = max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / ((dx * dx + dy * dy) or 1)))
				if (cx - x1 - t * dx) ** 2 + (cy - y1 - t * dy) ** 2 <= demi * demi:
					ligne[x] = valeur
					break


def grille_cite() -> list:
	cells = [[0] * COLS for _ in range(ROWS)]
	peindre(cells, list(DEDANS.values()) + list(DEHORS.values()), 1)
	for canal in CANAUX:
		peindre_polyligne(cells, canal, 5)
	peindre(cells, BASSINS, 5)
	peindre(cells, OBSTACLES, 0)
	return cells


def zone_de(cells, depart, nav=None) -> set:
	"""Cases praticables (1 ou 5) jointes à `depart` (8-voisinage, murs nav respectés)."""
	hauteur, largeur = len(cells), len(cells[0])
	if cells[depart[1]][depart[0]] not in (1, 5):
		return set()
	vues, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				nx, ny = x + dx, y + dy
				if ((dx or dy) and 0 <= nx < largeur and 0 <= ny < hauteur and (nx, ny) not in vues
						and cells[ny][nx] in (1, 5) and nav_allows(nav or {}, x, y, dx, dy)):
					vues.add((nx, ny))
					pile.append((nx, ny))
	return vues


def plus_proche(zone, repere, prises=()) -> tuple:
	libres = [c for c in zone if c not in prises] or list(zone)
	return min(libres, key=lambda c: ((c[0] - repere[0]) ** 2 + (c[1] - repere[1]) ** 2, c[1], c[0]))


# ── Cartes de combat (même relevé en polygones, cases de la carte DESSINÉE) ───────────────
SALLES = {
	"crue": {"dim": (30, 17), "base": 1,
		"murs": (((6, 0), (13, 0), (12.5, 3.5), (11, 4.6), (8.5, 4.5), (7, 2)),
			((18, 0), (30, 0), (30, 10.5), (29, 12.5), (28, 9), (26.5, 4), (22, 3.5), (20, 3), (18.5, 1.5)),
			((0, 4), (3, 4.5), (4.5, 6), (3.5, 9), (4, 11.5), (6, 13), (8, 14.5), (11, 15), (15, 14.8),
			 (18, 14.2), (19.5, 15.5), (20, 17), (0, 17))),
		"eau": (((0, 0), (6, 0), (7, 2), (8.5, 4.5), (3, 4.5), (0, 4)),
			((13, 0), (18, 0), (18.5, 1.5), (17, 4), (12, 4.5)),
			((4.5, 5), (8, 6.5), (10, 8.5), (12, 9.5), (15, 11), (17, 13), (18.5, 15), (19.5, 17),
			 (30, 17), (30, 13.5), (26, 12.5), (23, 11.5), (20, 10), (18, 8.5), (16, 7), (15, 5.5),
			 (13, 4.5), (11, 4.6)),
			((23, 6.3), (26.5, 6.3), (26.5, 9.6), (23, 9.6))),
		"obstacles": (((10, 9.3), (13, 9.3), (13, 11.5), (10, 11.5)), ((15, 11), (17.5, 11), (17.5, 13.5), (15, 13.5)),
			((19.5, 9), (22, 9), (22, 11), (19.5, 11)), ((12, 3), (14, 3), (14, 4.6), (12, 4.6)),
			((15, 4), (19.5, 4), (19.5, 5.8), (15, 5.8)), ((15, 6), (16.8, 6), (16.8, 7.6), (15, 7.6)),
			((22, 6), (27.3, 6), (27.3, 6.3), (22, 6.3)), ((22, 9.6), (27.3, 9.6), (27.3, 10.6), (22, 10.6))),
	},
	"djinns": {"dim": (30, 16), "base": 1,
		"murs": (((2, 5), (3.8, 5), (3.8, 10.5), (2, 10.5)), ((8.5, 2), (10, 2), (10, 8), (8.5, 8)),
			((16.3, 0), (18, 0), (18, 4), (16.3, 4)), ((16.3, 9.5), (18, 9.5), (18, 15.5), (16.3, 15.5)),
			((24.5, 4.5), (26.3, 4.5), (26.3, 9.5), (24.5, 9.5)), ((5, 0), (7, 0), (7, 1), (5, 1))),
		"eau": (((9.6, 4), (14.3, 4), (14.3, 6.6), (9.6, 6.6)), ((18.4, 10), (23.6, 10), (23.6, 13.6), (18.4, 13.6))),
		"obstacles": (((7, 7.5), (8.4, 7.5), (8.4, 8.8), (7, 8.8)), ((15, 3), (16.3, 3), (16.3, 4.8), (15, 4.8)),
			((13, 12.5), (15, 12.5), (15, 14), (13, 14)), ((26.5, 4.5), (28, 4.5), (28, 5.8), (26.5, 5.8))),
	},
	"tresor_1": {"dim": (30, 17), "ascii": (
		"##############..##############",
		"##############..##############",
		"##.....x.#..........#.......##",
		"##xxxx...#..........#..xxxx.##",
		"##.......#.########.#.....xx##",
		"##xx.....#.#......#.#.....xx##",
		"##xx.....#.#xx.xxx#.#.......##",
		"####.#####.#......#.#####...##",
		"####.0000#..........#0000.####",
		"##...####..#......#..####...##",
		"##xx....#..#xx...x#..#....xxx#",
		"##xx....#..#xx....#..#....xx##",
		"##xx....#..###..###..#....xx##",
		"##xx....#....#..#....#.....x##",
		"##xxxx..#.xxx#..#....#......##",
		"##xxxxxx#.xxx#..#....#..xxx.##",
		"##############################",
	)},
	"tresor_2": {"dim": (30, 17), "base": 1,
		"murs": (((0, 0), (30, 0), (30, 2.5), (0, 2.5)), ((0, 0), (2.8, 0), (2.8, 17), (0, 17)),
			((27.2, 0), (30, 0), (30, 17), (27.2, 17)), ((0, 13.8), (13.3, 13.8), (13.3, 17), (0, 17)),
			((16.7, 13.8), (30, 13.8), (30, 17), (16.7, 17)),
			((4, 2.5), (5.4, 2.5), (5.4, 4.3), (4, 4.3)), ((8, 2.5), (9.4, 2.5), (9.4, 4.3), (8, 4.3)),
			((12, 2.5), (13.4, 2.5), (13.4, 4.3), (12, 4.3)), ((17, 2.5), (18.4, 2.5), (18.4, 4.3), (17, 4.3)),
			((21, 2.5), (22.4, 2.5), (22.4, 4.3), (21, 4.3)), ((25, 2.5), (26.4, 2.5), (26.4, 4.3), (25, 4.3))),
		"ouvertures": (((14, 0), (16, 0), (16, 2.5), (14, 2.5)),),
		"obstacles": (((13, 6), (17, 6), (17, 9), (13, 9)), ((3, 8), (4.6, 8), (4.6, 9), (3, 9)),
			((25.4, 8), (27, 8), (27, 9), (25.4, 9)), ((2.8, 12.6), (4.4, 12.6), (4.4, 13.6), (2.8, 13.6)),
			((9.8, 12.6), (11.4, 12.6), (11.4, 13.6), (9.8, 13.6)), ((18.6, 12.6), (20.2, 12.6), (20.2, 13.6), (18.6, 13.6)),
			((25.6, 12.6), (27.2, 12.6), (27.2, 13.6), (25.6, 13.6)),
			((5, 4.6), (7.6, 4.6), (7.6, 5.8), (5, 5.8)), ((10, 4), (11.4, 4), (11.4, 5.2), (10, 5.2)),
			((22.6, 3.8), (24.2, 3.8), (24.2, 5.2), (22.6, 5.2)), ((20, 5.6), (22.6, 5.6), (22.6, 6.8), (20, 6.8)),
			((4, 9.6), (5.8, 9.6), (5.8, 10.8), (4, 10.8)), ((8.6, 10.6), (10.4, 10.6), (10.4, 12), (8.6, 12)),
			((4.6, 11), (6.2, 11), (6.2, 12.2), (4.6, 12.2)), ((21.6, 11.2), (23.2, 11.2), (23.2, 12.6), (21.6, 12.6)),
			((24, 9.6), (25.6, 9.6), (25.6, 10.8), (24, 10.8)), ((24, 11.2), (25.6, 11.2), (25.6, 12.4), (24, 12.4))),
	},
	"iram": {"dim": (60, 33), "base": 1, "echelle": 2,
		"murs": (((19.5, 0), (23.5, 0), (23.5, 5.6), (20.5, 5.6)), ((22.8, 3.8), (26.8, 6), (25.6, 9.8), (22.6, 8.4)),
			((22.8, 8.2), (27, 7.4), (28.6, 10.4), (27, 12), (24.6, 11.4))),
		"obstacles": (((2, 4), (3.6, 4), (6.6, 8), (5, 8.6)), ((10.4, 0.2), (12.2, 0.2), (12.4, 6.4), (11, 6.4)),
			((15, 2.4), (16.2, 2.4), (16.2, 5), (15, 5)), ((7.2, 5.4), (9.2, 5.4), (9.2, 7.2), (7.2, 7.2)),
			((9.6, 5.6), (12, 5.6), (12, 7.6), (9.6, 7.6)), ((13.2, 4.2), (15, 4.2), (15, 5.6), (13.2, 5.6)),
			((5, 8.4), (10.4, 8.4), (10.4, 14.6), (5, 14.6)),
			((17.2, 10.6), (20, 10.6), (20, 13.8), (17.2, 13.8)), ((9.8, 14.4), (12.2, 14.4), (12.2, 16.6), (9.8, 16.6)),
			((12.4, 13.6), (13.8, 13.6), (13.8, 15), (12.4, 15)), ((14.2, 13), (15.8, 13), (15.8, 15.6), (14.2, 15.6)),
			((20.4, 11.2), (22.4, 11.2), (22.4, 12.6), (20.4, 12.6))),
	},
	"hegra": {"dim": (30, 17), "base": 1,
		"murs": (((0, 0), (7, 0), (7.2, 4.5), (5, 6.4), (2, 6.6), (0, 6)), ((9.4, 0), (14.2, 0), (14, 2.8), (9.6, 2.8)),
			((19.2, 0), (25.4, 0), (25.4, 3.6), (19.6, 3.6)), ((25.2, 3.2), (30, 3.2), (30, 9.6), (25.2, 9.4)),
			((0, 8.6), (5.6, 8.6), (5.6, 15.4), (0, 15.4)), ((25, 9.6), (30, 9.6), (30, 17), (25, 17)),
			((5.6, 13.6), (12.2, 13.6), (12.2, 17), (5.6, 17)), ((11.6, 4), (19, 4), (19, 9.6), (11.6, 9.6))),
		"failles": (((4.6, 7.4), (8.2, 6.4), (9.6, 8.6), (9.4, 11), (10.6, 13), (12, 15.2), (16, 15.6), (19, 14.6),
				(21.2, 13), (22.2, 10.2), (22.4, 7), (21.6, 4.4), (19, 3), (16, 2), (14.2, 3), (11, 3.6), (9.4, 5.4)),),
		"obstacles": (((13.4, 10), (15.6, 10), (15.6, 11.2), (13.4, 11.2)), ((16, 9.6), (18.2, 9.6), (18.2, 10.8), (16, 10.8))),
	},
}
CODES_ASCII = {"#": 0, "0": 0, ".": 1, "x": 3, "~": 5}


def grille_salle(spec: dict) -> list:
	cols, rows = spec["dim"]
	if "ascii" in spec:
		assert len(spec["ascii"]) == rows and all(len(l) == cols for l in spec["ascii"]), "relevé ASCII"
		return [[CODES_ASCII[c] for c in ligne] for ligne in spec["ascii"]]
	k = spec.get("echelle", 1)
	cells = [[spec["base"]] * cols for _ in range(rows)]

	def mise(polys):
		return [tuple((x * k, y * k) for x, y in p) for p in polys]
	peindre(cells, mise(spec.get("eau", ())), 5)
	peindre(cells, mise(spec.get("murs", ())), 0)
	peindre(cells, mise(spec.get("ouvertures", ())), 1)
	for faille in spec.get("failles", ()):
		trace = [(x * k, y * k) for x, y in faille]
		peindre_polyligne(cells, trace + trace[:1], 0, demi=0.6)
	peindre(cells, mise(spec.get("obstacles", ())), 3)
	return cells


# ── Rangs, donjons, salles ────────────────────────────────────────────────────────────────
RANGS_DONJONS = {"crue": "A", "djinns": "A", "tresor": "S", "cites": "S+"}   # Auteur, 24/10
GIVER = "bureau_maitre_guilde"
BUREAU = "lieu:le_caravanserail_des_seuils_bureau_du_maitre"
COMPTOIR = "lieu:le_caravanserail_des_seuils_comptoir"
INTERIEUR = "lieu:le_caravanserail_des_seuils_interieur"


def salle_id(nom: str) -> str:
	return f"lieu:petra_donjon_{nom}"


def rang_min(rang: str) -> dict:
	return {"rang_min": {"cite": CITE, "rang": rang}}


def mandat(*salles) -> dict:
	"""La commission de Shaqilath, ENCORE À FAIRE, visant l'une de ces salles."""
	clauses = [{"quete_active": {"lieu": salle_id(s), "types": ["chasse"], "giver_categorie": GIVER,
		"objectif_atteint": False}} for s in salles]
	return clauses[0] if len(clauses) == 1 else {"ou": clauses}


# (slug du temple, tombeau, donjon, salles, Templier)
TEMPLES = {
	"urne": {"tombeau": "le tombeau de l'Urne", "donjon": "crue", "salles": ("crue",),
		"templier": "natiru"},
	"soie": {"tombeau": "le tombeau de la Soie", "donjon": "djinns", "salles": ("djinns",),
		"templier": "abd_obodas"},
	"corinthien": {"tombeau": "le tombeau Corinthien", "donjon": "tresor",
		"salles": ("tresor_1", "tresor_2"), "templier": "wailu"},
	"palais": {"tombeau": "le tombeau du Palais", "donjon": "cites", "salles": ("iram", "hegra"),
		"templier": "aslah"},
}
DONJONS = {
	"crue": {"nom": "La crue du tombeau de l'Urne", "niveau_min": 4, "niveau_max": 5,
		"description": "Derrière la porte du tombeau de l'Urne, une gorge de grès où la crue ne retombe "
			"jamais tout à fait. Chaque fois que l'eau monte, elle ramène ce qui vit dans les oueds — "
			"et les marids qui la mènent.",
		"salles": [{"lieu": salle_id("crue"), "especes": ["espece:marid", "espece:crocodile",
			"espece:serpent_geant"], "nb_monstres": 4}]},
	"djinns": {"nom": "Le refuge des djinns", "niveau_min": 5, "niveau_max": 6,
		"description": "Depuis la Vague, le portail du tombeau de la Soie ouvre sur un palais de fumée "
			"où les djinns se rassemblent. Sur Telluris ou ailleurs : personne ne le sait, et les "
			"dalles cachent plus de pièges que de réponses.",
		"salles": [{"lieu": salle_id("djinns"), "especes": ["espece:ifrit", "espece:marid",
			"espece:silat", "espece:jann", "espece:nasnas"], "nb_monstres": 5}]},
	"tresor": {"nom": "Le trésor du Pharaon", "niveau_min": 5, "niveau_max": 6, "mode": "etages",
		"description": "Sous le tombeau Corinthien, des chambres funéraires gardées par les scarabées, "
			"puis la salle du trésor que les voyageurs croient caché dans la Khazneh. Le sphinx qui la "
			"garde ne dit pas à qui appartient l'or.",
		"salles": [{"lieu": salle_id("tresor_1"), "especes": ["espece:nuee_de_scarabees",
				"espece:scorpion_geant", "espece:mimique"], "nb_monstres": 5},
			{"lieu": salle_id("tresor_2"), "especes": ["espece:sphinx"], "nb_monstres": 1}]},
	"cites": {"nom": "Les cités anéanties", "niveau_min": 6, "niveau_max": 6, "mode": "etages",
		"description": "Derrière le tombeau du Palais, Iram aux colonnes, ensevelie par le vent, puis "
			"Hégra des Thamûd, fendue par le séisme. Châtiments, tempêtes ou coïncidences : les "
			"vieilles familles de Petra ne s'accordent pas sur ce qui a frappé ces deux cités.",
		"salles": [{"lieu": salle_id("iram"), "especes": ["espece:geant_de_ad",
				"espece:ghul_des_sables", "espece:jann"], "nb_monstres": 5},
			{"lieu": salle_id("hegra"), "especes": ["espece:qudar"], "nb_monstres": 1}]},
}
SALLES_LIEUX = {
	"crue": {"label": "La gorge de la crue", "tags": ["donjon", "gorge", "eau"]},
	"djinns": {"label": "Le palais de fumée", "tags": ["donjon", "palais", "couvert", "pieges_12_4"]},
	"tresor_1": {"label": "Les chambres funéraires du tombeau Corinthien",
		"tags": ["donjon", "tombeau", "sous-terrain", "couvert"]},
	"tresor_2": {"label": "La salle du trésor", "tags": ["donjon", "tombeau", "sous-terrain", "couvert"]},
	"iram": {"label": "Iram aux colonnes", "tags": ["donjon", "desert", "ruines"]},
	"hegra": {"label": "Hégra, la cité fendue", "tags": ["donjon", "desert", "ruines"]},
}
# Trésor de la salle du sphinx (Auteur, 24/10 : encens et myrrhe, or et bourse, cristal de mana).
TRESOR = {"nom": "Le trésor du Pharaon", "icon": "🧰", "pos": [14, 10],
	"garanti": [{"item": "item:cristal_de_mana_violet", "quantite": 1}, {"item": "item:myrrhe", "quantite": 2}],
	"bourse": [300, 900],
	"tirage": {"nb": 3, "table": [{"item": "item:Encens", "poids": 3}, {"item": "item:myrrhe", "poids": 3},
		{"item": "item:gemmes", "poids": 2}, {"item": "item:anneau", "poids": 2}, {"item": "item:bague", "poids": 2}]},
	"piege": {"chance": 50, "danger": 4, "effets": ["degats", "alarme", "mimique"], "alarme": 3,
		"mimique": "espece:mimique"}}
# Passages des donjons à étages : (salle, case, libellé) ↔ (salle ou temple, case, libellé).
ETAGES = {
	"tresor": {"entree": (14, 1), "descente": ((14, 15), (14, 15)), "sortie": (15, 1)},
	"cites": {"entree": (3, 30), "descente": ((57, 28), (1, 7)), "sortie": (13, 12)},
}


# ── PNJ ───────────────────────────────────────────────────────────────────────────────────
def choix(i, label, nxt=None, condition=None, action=None, deplacer=None) -> dict:
	c = {"id": i, "label": label}
	if condition:
		c["condition"] = condition
	if action:
		c["action"] = action
	else:
		c["next"] = nxt or "fin"
	if deplacer:
		c["deplacer"] = deplacer
	return c


def noeud(texte, *choix_) -> dict:
	return {"texte": texte, "choix": list(choix_)}


def pnj_doc(slug, nom, race, vocation, portrait, description, noeuds, services=None) -> dict:
	doc = {"_id": f"pnj:{slug}", "type": "pnj", "nom": nom, "race": race, "vocation": vocation,
		"portrait": portrait, "description": description}
	if services:
		doc["services"] = services
	doc["dialogue"] = {"noeud_depart": "accueil", "noeuds": noeuds}
	return doc


RETOUR = choix("retour", "Une autre question…", "accueil")


def zaydu() -> dict:
	return pnj_doc("zaydu_caravanserail_des_seuils", "Zaydu", "hobbit", "receptionniste",
		"guilde_hobbit_m_petra01.jpg",
		"Réceptionniste du Caravansérail des Seuils, la maison de la Guilde des Aventuriers de Petra. "
		"Un jeune hobbit au sourire franc, fils d'un gardien des sources, qui sert de l'eau à tout arrivant "
		"avant même de lui demander son nom. À sa ceinture pend la clé de bronze d'une citerne : une seule, "
		"il le précise toujours.",
		{
			"accueil": noeud(
				"Avant même de vous saluer, {pnj} vous tend un gobelet d'eau fraîche par-dessus le comptoir de "
				"pierre, qui lui arrive à la poitrine. « Buvez d'abord, on parlera après. C'est la première règle "
				"de Nebaioth, et à Petra personne ne l'a oubliée. » Il essuie ses mains sur son gilet rayé. "
				"« Bienvenue au Caravansérail des Seuils, {prenom}. »",
				choix("inscription", "« Je voudrais m'inscrire à la Guilde de Petra. »", "inscription_propose",
					{"don_recu": False}),
				choix("bureau", "« Je voudrais voir la maîtresse de la Guilde. »", condition={"acces_ouvrable": True},
					action={"service": "acces", "op": "passer"}),
				choix("bureau_deja", "« Je monte voir la maîtresse. »", "acces_deja", {"acces_ouvert": True}),
				choix("bureau_refus", "« Qui dirige la Guilde, ici ? »", "acces_refus", {"acces_refuse": True}),
				choix("eau", "« Pourquoi cette eau, d'abord ? »", "eau"),
				choix("seuils", "« Pourquoi « des Seuils » ? »", "seuils"),
				choix("rien", "« Rien. Je me rafraîchissais. »")),
			"inscription_propose": noeud(
				"{pnj} ouvre un registre presque aussi large que lui. « Votre nom, votre lignée, ce que vous savez "
				"faire. Et si vous portez la carte de la Guilde de Lutecia, montrez-la-moi : la maîtresse veut qu'on "
				"y reconnaisse le rang inscrit. Les routes jusqu'ici sont trop longues pour qu'on vous fasse tout "
				"recommencer. »",
				choix("inscrire", "« Inscrivez-moi. »", action={"service": "don"}),
				choix("attendre", "« Pas encore. »", "accueil")),
			"inscription_faite": noeud(
				"Quelques lignes d'une écriture ronde, un coup de buvard, et il fait glisser vers vous une plaque de "
				"cuir frappée d'une porte ouverte sur une source. « Votre carte de Petra. Si vous arrivez de "
				"Lutecia avec un rang, il est recopié — je l'ai lu de mes yeux. Sinon, vous partez du premier "
				"échelon, comme tout le monde. » Il remplit votre gobelet. « Bienvenue parmi nous, {prenom}. »",
				choix("merci", "« Merci, Zaydu. »"), RETOUR),
			"inscription_sans_fonds": noeud(
				"« L'inscription ne coûte rien, {prenom}. Si le registre vous réclame une pièce, quelqu'un a "
				"changé les règles sans prévenir les gardiens — et ça, à Petra, ça n'arrive pas. »",
				choix("ok", "« Je reviendrai. »")),
			"inscription_trop_charge": noeud(
				"« Pas même la place d'une carte dans votre sac ? » Il rit doucement. « Allégez-vous, {prenom}. "
				"Le registre vous attendra, et l'eau aussi. »",
				choix("ok", "« Je reviens le sac plus léger. »")),
			"acces_ouvre": noeud(
				"{pnj} retrouve votre nom dans le registre et désigne la coursive d'angle. « La maîtresse vous "
				"recevra. C'est là-haut : {portail}. Elle a mené des caravanes pendant trente ans ; dites-lui d'où "
				"vous venez, elle saura combien vous valez. »",
				choix("monter", "Monter par la coursive.", deplacer=BUREAU)),
			"acces_deja": noeud(
				"« Vous connaissez la coursive. » Un geste vers l'escalier d'angle, sans lâcher sa jarre. "
				"« Montez, {prenom}. »",
				choix("monter", "Monter par la coursive.", deplacer=BUREAU)),
			"acces_refus": noeud(
				"« Shaqilath. La maîtresse de la Guilde. » Il le dit avec une fierté tranquille. « Elle ne reçoit "
				"que les aventuriers de rang A de Petra : les quatre tombeaux qu'elle mandate ne pardonnent rien en "
				"dessous. Inscrivez-vous ici — votre rang de Lutecia sera reconnu — ou gagnez-le. »",
				choix("ok", "« J'y travaille. »"), RETOUR),
			"eau": noeud(
				"« L'eau ? » Il remplit un second gobelet, pour lui cette fois. « Mon père est gardien des sources. "
				"Quand la Vague est passée et que la terre a tremblé, ce sont eux qui ont recousu les canaux, en "
				"quelques saisons. Depuis, à Petra, c'est leur voix qui compte quand il s'agit de l'eau — même au "
				"conseil. » Il fait tinter la petite clé de bronze à sa ceinture. « Celle-ci ouvre une citerne. "
				"Une seule. Il faut des années pour qu'on vous en confie une deuxième. »",
				RETOUR, choix("fin", "« Merci pour l'eau. »")),
			"seuils": noeud(
				"« Parce qu'ici, tout le monde passe un seuil un jour. » Il compte sur ses doigts. « Trois portes "
				"tiennent encore, comme avant la Vague : la Khazneh vers Alexandrie, ad-Deir vers Bucarest, le Qasr "
				"al-Bint vers Muziris, en Inde. Quatre autres ont changé de couleur, dans les tombeaux royaux, et "
				"les Templiers les gardent. » Il hausse les épaules. « Les gardiens disent que la montagne a bu la "
				"Vague. Les Architectes disent autre chose. Moi, je sers de l'eau. »",
				RETOUR, choix("fin", "« Je comprends. »")),
		},
		{
			"don": {"item": "item:carte_aventurier", "quantite": 1, "cout_cuivre": 0, "lieu_parent": "auto",
				"rang_guilde": "F", "rang_reconnu": LUTECIA, "unique": True,
				"noeuds": {"fait": "inscription_faite", "sans_fonds": "inscription_sans_fonds",
					"trop_charge": "inscription_trop_charge"}},
			"acces": {"lieu": BUREAU, "noeuds": {"ouvre": "acces_ouvre", "refus": "acces_refus", "deja": "acces_deja"}},
		})


def shaqilath() -> dict:
	return pnj_doc("shaqilath", "Shaqilath", "ogre", "maitre_de_guilde", "guilde_ogre_f_petra01.jpg",
		"Maîtresse de la Guilde des Aventuriers de Petra, au Caravansérail des Seuils. Une ogresse d'âge mûr, "
		"la peau hâlée par trente ans de pistes, les cheveux noirs striés de gris tressés sous un foulard "
		"indigo. Ancienne cheffe d'escorte de caravanes, on l'appelle « la Caravanière » ; elle porte le nom "
		"des reines d'autrefois sans en avoir le sang, et s'en amuse. C'est elle qui mandate les compagnies "
		"pour les quatre tombeaux royaux.",
		{
			"accueil": noeud(
				"Le bureau sent le cuir et la poussière de piste. Penchée sur une carte des routes du désert, {pnj} "
				"se redresse — et il faut lever les yeux, puis les lever encore. Elle vous tend un gobelet d'eau "
				"avant de dire un mot. « Buvez. Ensuite, dites-moi d'où vous venez. » Puis, avec un demi-sourire : "
				"« Et non, je n'ai rien de royal. On me le demande chaque semaine. »",
				choix("commission", "« Vous avez un mandat pour moi ? »", "commission_propose",
					{"commission_offerte": True}),
				choix("commission_rapport", "« C'est fait. Ce qui commandait là-dessous est tombé. »",
					condition={"commission_a_rapporter": True}, action={"service": "commission", "op": "rapporter"}),
				choix("commission_relance", "« Où en est mon mandat ? »", "commission_relance",
					{"commission_en_cours": True}),
				choix("aucun", "« Vous avez un mandat pour moi ? »", "aucun_mandat",
					{"commission_offerte": False, "commission_en_cours": False, "commission_a_rapporter": False}),
				choix("tombeaux", "« Que s'est-il passé dans les tombeaux royaux ? »", "tombeaux"),
				choix("caravanes", "« Pourquoi « la Caravanière » ? »", "caravanes"),
				choix("rien", "« Rien. Je voulais vous voir. »")),
			"commission_propose": noeud(
				"Elle déroule un mandat déjà scellé. « Une commission d'éradication. Les Templiers me signalent "
				"{lieu}. Ce qui m'inquiète, c'est ce qui y commande : un {espece} hors du commun. » Elle pose un "
				"doigt épais sur la carte. « Abattez-le, et revenez me le dire vous-même. {xp} points d'expérience "
				"et {prime} pièces de cuivre. Le Templier de la porte lira ce sceau, pas votre nom. »",
				choix("details", "« Qui garde les portes ? »", "commission_details"),
				choix("accepter", "« Donnez-moi ce mandat. »", action={"service": "commission", "op": "accepter"}),
				choix("refuser", "« Pas celui-là. »", "accueil")),
			"commission_details": noeud(
				"« Chaque tombeau a sa porte, et chaque porte son Templier : Natiru tient l'Urne, Abd-Obodas la "
				"Soie, Wa'ilu le Corinthien, Aslah le Palais. Ils ne laissent passer qu'avec un mandat — et qu'au "
				"rang que le tombeau exige : A pour l'Urne et la Soie, S pour le Corinthien, S+ pour le Palais. » "
				"Elle hausse une épaule. « Je ne vous propose que ce que vous pouvez franchir. »",
				choix("accepter", "« Donnez-moi ce mandat. »", action={"service": "commission", "op": "accepter"}),
				choix("refuser", "« Je réfléchis. »", "accueil")),
			"commission_accepte": noeud(
				"Elle presse le sceau de la Guilde dans la cire et vous tend le mandat. « {espece}, dans {lieu}. "
				"Prenez de l'eau en partant : là-dessous, personne ne vous en offrira. »",
				choix("ok", "« Ce sera fait. »")),
			"commission_relance": noeud(
				"Elle suit une ligne de son registre du bout d'un ongle. « {espece}, dans {lieu}. Le mandat court "
				"toujours, {prenom}, et le Templier compte les jours. »",
				choix("ok", "« J'y retourne. »")),
			"commission_rapporte": noeud(
				"Elle vous écoute jusqu'au bout sans un mot, puis pousse vers vous {prime} pièces de cuivre ; {xp} "
				"points sont portés à votre nom. « Une caravane qui revient entière, c'est la seule chose qui m'ait "
				"jamais rendue fière. Vous venez d'en ramener une. » Elle remplit deux gobelets. « Les tombeaux ne "
				"vont nulle part. Revenez quand vous voudrez. »",
				choix("ok", "« Merci, maîtresse. »")),
			"aucun_mandat": noeud(
				"« Rien pour vous aujourd'hui. » Elle ne détourne pas les yeux. « Je ne mandate que pour les "
				"tombeaux qu'on peut franchir : l'Urne et la Soie au rang A, le Corinthien au rang S, le Palais au "
				"rang S+. Faites reconnaître votre rang au comptoir, ou gagnez-le. Les tombeaux, eux, ne vont "
				"nulle part. »",
				choix("ok", "« Je reviendrai. »"), choix("retour", "Une autre question…", "accueil")),
			"tombeaux": noeud(
				"« Quand la Vague est passée, la terre a tremblé en même temps. » Elle tourne son gobelet entre ses "
				"doigts. « Trois portes ont tenu. Quatre autres, dans les tombeaux royaux, ont changé de couleur, et "
				"plus personne ne sait ce qu'il y a derrière avant d'y être allé. Une gorge où la crue ne retombe "
				"jamais. Un palais de fumée plein de djinns. Le trésor que les voyageurs cherchent dans la Khazneh. "
				"Et deux cités mortes, l'une sous le sable, l'autre fendue. » Un silence. « Les vieilles familles "
				"disent que ce sont des châtiments. Les Architectes, que ce sont des portes mal tenues. Moi, je dis "
				"que ce sont des contrats. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Je vois. »")),
			"caravanes": noeud(
				"« Trente ans d'escortes, d'Arabie jusqu'aux pistes du Levant. » Elle montre la selle de chameau "
				"usée accrochée au mur. « Je n'ai jamais perdu une caravane qui m'avait demandé protection. C'est la "
				"deuxième règle de Nebaioth, et c'est la seule dont je me vante. » Elle sourit. « Quand la Guilde a "
				"eu besoin de quelqu'un qui sache ramener les gens vivants, on est venu me chercher. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Merci. »")),
		},
		{"commission": {"donjons": [f"donjon:petra_{d}" for d in DONJONS],
			"noeuds": {"accepte": "commission_accepte", "rapporte": "commission_rapporte"}}})


# Templiers : (nom, Lignée, portrait réemployé, présentation, texte de la porte, lore du tombeau).
TEMPLIERS = {
	"natiru": ("Natiru", "nain", "templier_nain_m_garde_temple01.png",
		"Templier nain de la garde du tombeau de l'Urne. Il compte les crues comme d'autres comptent les "
		"jours, et ne laisse descendre dans la gorge que les compagnies mandatées par la Guilde.",
		"Devant le tombeau de l'Urne, une muraille neuve ferme la façade ; derrière elle, on entend l'eau "
		"gronder sans répit. {pnj}, un nain en haubert ruisselant, garde la poterne, une main sur un registre "
		"détrempé. « Halte. Derrière cette porte, la crue ne retombe jamais. »",
		"« Avant la Vague, on y menait les caravanes vers une cité de l'autre côté du désert. » Il essuie son "
		"registre du revers de la manche. « Maintenant, la porte ouvre sur une gorge en crue. Chaque fois que "
		"l'eau monte, elle ramène les bêtes des oueds, et les marids qui la mènent. Les gardiens des sources "
		"disent que c'est l'eau de Petra qui cherche à rentrer. Moi, je n'en sais rien : je compte ceux qui "
		"remontent. »"),
	"abd_obodas": ("Abd-Obodas", "humain", "templier_humain_m_garde_temple01.png",
		"Templier de la garde du tombeau de la Soie. Il porte le nom d'un ancien roi, comme bien des fils des "
		"vieilles familles, et connaît par cœur les dalles qu'il ne faut pas fouler derrière sa porte.",
		"La façade du tombeau de la Soie ondule de veines rouges, jaunes et violettes, et une fumée fine "
		"s'échappe sous la porte murée. {pnj} se tient devant, un tissu humide noué sur le visage. « On ne "
		"respire pas ça longtemps. Que voulez-vous ? »",
		"« Les djinns étaient sur Telluris bien avant nous, bien avant les rois. » Il regarde la fumée sous "
		"la porte. « Depuis la Vague, ce seuil ouvre sur l'endroit où ils se retrouvent : un palais de fumée. "
		"Sur Telluris ou ailleurs, personne n'a pu le dire. Ce que je sais, c'est que les dalles y mentent : "
		"une sur trois cache un piège, et les ifrits ne les déclenchent jamais. »"),
	"wailu": ("Wa'ilu", "ogre", "templier_ogre_m_garde_temple01.jpg",
		"Templier ogre de la garde du tombeau Corinthien. Il a vu descendre plus de chercheurs de trésor qu'il "
		"n'en a vu remonter, et ne s'en étonne plus.",
		"Devant le tombeau Corinthien, des colonnes taillées dans la roche encadrent une porte basse cerclée de "
		"bronze. {pnj}, un ogre aux bras croisés, la bouche de toute sa carrure. « Encore quelqu'un pour le "
		"trésor du Pharaon. »",
		"« Les voyageurs le cherchent dans la Khazneh depuis toujours. » Il hausse ses énormes épaules. « Il "
		"est là-dessous, derrière cette porte : des chambres pleines de scarabées, puis une salle d'or gardée "
		"par un sphinx. À qui il appartient, ce trésor ? Le sphinx ne l'a jamais dit, et ceux qui lui ont posé "
		"la question ne sont pas remontés me répondre. » Il désigne la porte. « Il vous faut un mandat de "
		"Shaqilath et le rang S. Le seuil fait le reste. »"),
	"aslah": ("Aslah", "ogre", "templier_ogre_m_garde_temple02.jpg",
		"Templier ogre de la garde du tombeau du Palais, le plus haut des tombeaux royaux. Il parle peu, et "
		"jamais de ce qu'il a vu derrière sa porte.",
		"Le tombeau du Palais domine la terrasse de ses étages de colonnes. Du sable fin coule sous sa porte, "
		"alors qu'aucun vent ne souffle. {pnj} le balaie du pied, lentement. « Le sable revient tous les "
		"matins. »",
		"« Derrière, il y a deux cités. » Il cesse de balayer. « D'abord Iram aux colonnes, ensevelie par le "
		"vent, où marchent encore des géants. Puis Hégra, fendue par la terre comme Petra a tremblé à la "
		"Vague. On dit qu'un homme y tua la chamelle sortie du rocher et que tout trembla. D'autres disent que "
		"la terre a tremblé, voilà tout. » Il reprend son balai. « Mandat de Shaqilath, rang S+. Sinon, "
		"rien. »"),
}


def templier(slug: str, temple: dict) -> dict:
	nom, race, portrait, description, porte, lore = TEMPLIERS[slug]
	classique = len(temple["salles"]) == 1
	lieu = salle_id(temple["salles"][0])
	consigne = ("« Un mandat de la Guilde, et le rang {r}. Shaqilath délivre l'un, le comptoir inscrit "
		"l'autre. » ").replace("{r}", RANGS_DONJONS[temple["donjon"]])
	noeuds = {"lore": noeud(lore, choix("retour", "Revenir.", "accueil"))}
	if classique:
		accueil = [
			choix("passer", "« J'ai un mandat de la Guilde. »", condition={"acces_ouvrable": True},
				action={"service": "acces", "op": "passer"}),
			choix("accompli", "« C'est fait. Ce qui commandait est tombé. »", "acces_accompli",
				{"acces_accompli": True}),
			choix("pourquoi", "« Pourquoi cette porte est-elle fermée ? »", "acces_refus",
				{"acces_refuse": True, "acces_libere": False}),
			choix("pourquoi_libre", "« Pourquoi cette porte est-elle fermée ? »", "acces_refus_libre",
				{"acces_refuse": True, "acces_libere": True}),
		]
		noeuds.update({
			"acces_ouvre": noeud(
				"{pnj} compare le sceau de la Guilde à son registre, hoche la tête une fois et trace un trait à "
				"côté de votre nom. « Mandat enregistré. » La poterne s'ouvre sur {portail}. « Personne ne viendra "
				"vous chercher. Revenez par où vous êtes entré, ou ne revenez pas. »",
				choix("fin", "Franchir le seuil.")),
			"acces_refus": noeud(
				"« Pas de mandat, pas de passage. » " + consigne + "« {portail} n'est pas un lieu où l'on va voir. »",
				choix("fin", "S'écarter.")),
			"acces_refus_libre": noeud(
				"« Ce qui commandait là-dessous est tombé, et la porte reste close jusqu'au prochain mandat. » "
				+ consigne,
				choix("fin", "S'écarter.")),
			"acces_accompli": noeud(
				"Pour la première fois, {pnj} referme son registre. « On l'a entendu, d'ici. Puis plus rien — et "
				"c'est à ce silence qu'on reconnaît le travail fait. » Il désigne la terrasse. « Portez votre "
				"rapport à Shaqilath. C'est elle qui paie. »",
				{"id": "fin", "label": "« J'y vais. »", "next": "fin"}),
		})
		noeuds["acces_accompli"] = {**noeuds["acces_accompli"], "relation": {"delta": 1}}
		if temple["donjon"] == "crue":
			accueil.append(choix("remonte", "« L'eau est remontée ? »", "remonte", {"acces_reinfeste": True}))
			noeuds["remonte"] = noeud(
				"« Elle remonte toujours. » {pnj} montre la marque de la dernière crue sur la muraille. « Un mandat "
				"a été donné, et les bêtes sont revenues avec l'eau. C'est la loi de cette porte : on la vide, elle "
				"se remplit. »",
				choix("retour", "Revenir.", "accueil"))
		services = {"acces": {"lieu": lieu, "noeuds": {"ouvre": "acces_ouvre", "refus": "acces_refus"}}}
	else:
		accueil = [choix("consignes", "« Que faut-il pour descendre ? »", "consignes")]
		noeuds["consignes"] = noeud(
			consigne + "« Avec les deux, passez le seuil : il s'ouvrira seul. Sans, il ne s'ouvrira pas, et je "
			"n'y pourrai rien. Là-dessous, on ne remonte qu'en trouvant la sortie, tout au fond. »",
			choix("retour", "Revenir.", "accueil"))
		services = None
	accueil += [choix("lore", "« Qu'y a-t-il derrière ? »", "lore"), choix("rien", "« Rien. Je passais. »")]
	noeuds["accueil"] = noeud(porte, *accueil)
	return pnj_doc(f"templier_{slug}_petra", nom, race, "garde", portrait, description, noeuds, services)


# ── Bestiaire et objets ───────────────────────────────────────────────────────────────────
ESPECES = {
	"nasnas": {"nom": "Nasnas",
		"description": "Demi-créature des déserts : la moitié d'un corps, un œil, un bras, une jambe, qui avance "
			"par bonds plus vite qu'un chameau au trot. Les caravaniers de Petra disent qu'un djinn fendit un homme "
			"en deux ; d'autres, qu'elle cherche son autre moitié dans chaque voyageur qu'elle déchire. Aucun "
			"gardien des sources n'en a jamais vu deux ensemble.",
		"base_attributes": _attrs((7, 9), (35, 55), (30, 45), (50, 75), (30, 45), (15, 30), (0, 0), (30, 45)),
		"tags": ["monstre", "desert", "rapide", "predateur"], "carcasse": ([25, 45], "rare")},
	"geant_de_ad": {"nom": "Géant de ʿĀd",
		"description": "Bâtisseur d'Iram aux colonnes, mort sous le sable que le vent jeta sur sa cité. Les ʿĀd "
			"étaient si grands, dit-on, qu'ils taillaient leurs colonnes à leur mesure ; ceux qui se relèvent "
			"derrière le tombeau du Palais ruissellent encore de ce sable. Châtiment d'un orgueil, colère du ciel "
			"ou simple tempête : les vieilles familles de Petra ne s'accordent pas.",
		"base_attributes": _attrs((5, 7), (85, 110), (80, 100), (15, 25), (40, 60), (20, 35), (0, 0), (30, 45)),
		"tags": ["humanoide", "geant", "mort_vivant", "desert"], "carcasse": ([600, 1100], "rare")},
	"qudar": {"nom": "Qudar",
		"description": "Celui qui tua la chamelle de Sâlih sortie du rocher, et dont le crime, dit-on, fit trembler "
			"la terre jusqu'à fendre Hégra. Il hante encore sa cité morte, les mains tachées d'un sang qu'aucune "
			"eau n'a lavé. Le séisme punissait-il, ou fut-il seulement ? Les gardiens des sources, qui ont vu "
			"Petra trembler à la Vague, préfèrent ne pas répondre.",
		"base_attributes": _attrs((6, 8), (70, 95), (65, 85), (40, 60), (55, 80), (35, 50), (20, 35), (40, 60)),
		"tags": ["humanoide", "mort_vivant", "legendaire", "boss"], "carcasse": ([60, 90], "tres_rare")},
	"nuee_de_scarabees": {"nom": "Nuée de scarabées",
		"description": "Des centaines de scarabées noirs aux reflets de bronze qui roulent ensemble comme une seule "
			"bête dans les chambres du tombeau Corinthien. Les chercheurs de trésor jurent qu'ils gardent l'or "
			"du Pharaon ; les Templiers, qu'ils dévorent simplement tout ce qui entre.",
		"base_attributes": _attrs((4, 6), (25, 40), (50, 70), (30, 50), (10, 20), (1, 5), (0, 0), (20, 35)),
		"tags": ["monstre", "insecte", "essaim", "souterrain"], "carcasse": ([5, 15], "peu_commun")},
	"scorpion_geant": {"nom": "Scorpion géant",
		"description": "Scorpion du désert grand comme un cheval, dont le dard perle d'un venin vert pâle. Il gîte "
			"dans les chambres basses du tombeau Corinthien comme dans les sables qui bordent les pistes "
			"caravanières de Petra.",
		"base_attributes": _attrs((6, 8), (55, 75), (60, 80), (35, 55), (20, 35), (3, 8), (0, 0), (25, 40)),
		"tags": ["monstre", "venin", "desert", "predateur"], "carcasse": ([200, 400], "peu_commun")},
}
ITEMS = [
	{"_id": "item:myrrhe", "type": "item", "nom": "Myrrhe", "sous_categorie": "", "icon": "🟤",
	 "description": "Larmes de résine rouge et amère, récoltées sur des arbres d'Arabie et pesées à Petra au "
		"poids de l'eau. Les caravanes la vendent pour les onguents, les rites et les morts.",
	 "rarete": "rare", "categorie": "composant", "slots": [], "poids": 0.05, "valeur": [{"cu": 40}]},
	{"_id": "item:cristal_de_mana_violet", "type": "item", "nom": "Cristal de mana violet", "icon": "💜",
	 "description": "Éclat de mana violet, qui bourdonne doucement au creux de la main. Les Architectes y voient "
		"de la puissance pure, de quoi nourrir un portail ; d'où vient celui-ci, au fond d'un trésor de Petra, "
		"aucun ne s'accorde.",
	 "categorie": "composant", "sous_categorie": "cristal", "rarete": "tres_rare", "slots": [], "poids": 0.1},
]


# ── Lieux et connexions ───────────────────────────────────────────────────────────────────
def connexion(_id, a, pos_a, b, pos_b, type_, label_a=None, label_b=None) -> dict:
	"""`label_a` = le bouton qui MÈNE à `a` (affiché depuis `b`), et réciproquement."""
	na, nb = {"lieu": a, "pos": list(pos_a)}, {"lieu": b, "pos": list(pos_b)}
	if label_a:
		na["label"] = label_a
	if label_b:
		nb["label"] = label_b
	return {"_id": _id, "type": "connection", "nodes": [na, nb], "metadata": {"type": type_, "status": "ouvert"}}


def portes_docs(portes_cases) -> list:
	"""Les cinq docs de chaque porte, forme de `_ptDocs` (admin_map_editor.html)."""
	sortie = []
	for nom, slug, dehors, dedans, img_ext, img_int in portes_cases:
		base = f"petra_porte_{slug}"
		ext, int_ = f"lieu:{base}_exterieur", f"lieu:{base}_interieur"
		sortie += [
			{"_id": ext, "type": "lieu", "label": f"{nom} — extérieur", "image": img_ext,
			 "categorie": "Porte de rempart", "lieu_parent": CITE},
			{"_id": int_, "type": "lieu", "label": f"{nom} — intérieur", "image": img_int,
			 "categorie": "Porte de rempart", "lieu_parent": CITE},
			connexion(f"link:{base}_carte_exterieur", CITE, dehors, ext, (0, 0), PORTE_TYPE, PORTE_LABEL_DEHORS),
			connexion(f"link:{base}_carte_interieur", CITE, dedans, int_, (0, 0), PORTE_TYPE),
			connexion(f"link:{base}_passage", ext, (0, 0), int_, (0, 0), PORTE_TYPE),
		]
	return sortie


# Bouton affiché dans la cité d'arrivée pour gagner le portail de Petra.
ARRIVEE_LABELS = {"khazneh": "Petra — par le seuil de la Khazneh", "ad_deir": "Petra — par le seuil d'ad-Deir"}
TEXTES = {
	"khazneh": "La façade de la Khazneh monte d'un seul jet dans la falaise rose, colonnes, fronton et rotonde "
		"taillés dans la roche. Derrière la porte, au fond de la salle, un seuil de pierre ancien tourne sans "
		"bruit : celui que les voyageurs prennent pour le trésor du Pharaon. Des Architectes en tiennent "
		"l'ancrage ; il mène au Sérapéum d'Alexandrie.",
	"ad_deir": "Au sommet de l'escalier taillé, la grande façade d'ad-Deir domine les canyons. Dans sa salle "
		"unique, un seuil tenu par les Architectes de Petra s'ouvre vers Bucarest, de l'autre côté du monde "
		"connu.",
	"qasr_al_bint": "Massif et carré, le Qasr al-Bint ferme la rue à colonnades. Au fond du sanctuaire, un seuil "
		"ancien regarde vers Muziris, en Inde, la cité du poivre.",
}


def docs_petra(par_id: dict, levant: dict, erreurs: list) -> list:
	cells = grille_cite()
	# Le dehors a DEUX pans (le Siq et le désert du nord-est ; le désert du sud-est et sa bande),
	# chacun relié au Levant par sa propre entrée et à la cité par sa propre porte.
	dedans = zone_de(cells, PORTES[0][3])
	dehors = set().union(*(zone_de(cells, p[2]) for p in PORTES))
	if dedans & dehors:
		erreurs.append("le dedans et le dehors de Petra communiquent sans porte")
	for nom, _s, c_dehors, c_dedans, _e, _i in PORTES:
		if c_dehors not in dehors or c_dedans not in dedans:
			erreurs.append(f"{nom} : case dehors {c_dehors} ou dedans {c_dedans} du mauvais côté")
	docs = [{"_id": CITE, "type": "lieu", "label": "Petra", "image": "petra_city.jpg", "categorie": "ville",
		"sous_categorie": "capitale", "dimensions": {"x": COLS, "y": ROWS}, "cells": cells, "nav": {},
		"tags": [], "lieu_parent": PAYS}]
	docs += portes_docs(PORTES)

	# Entrées depuis le Levant.
	zone_levant = zone_de(levant["cells"], plus_proche(
		{(x, y) for y, l in enumerate(levant["cells"]) for x, v in enumerate(l) if v == 1}, ENTREES[0][2]),
		levant.get("nav"))
	for suffixe, label, repere_pays, repere_cite in ENTREES:
		docs.append(connexion(f"link:levant_to_petra_{suffixe}", PAYS, plus_proche(zone_levant, repere_pays),
			CITE, plus_proche(dehors, repere_cite), "chemin", label_b=label))

	prises = set()

	def case(slug):
		c = plus_proche(dedans, REPERES[slug], prises)
		prises.add(c)
		return c

	# Guilde.
	docs += [
		{"_id": INTERIEUR, "type": "lieu", "label": "Le Caravansérail des Seuils - coursives",
		 "image": "guilde_petra_coursives.jpg", "categorie": "guilde_aventurier", "lieu_parent": CITE,
		 "sous_categorie": "guilde_aventurier", "tags": ["recrutement"], "relation_lieu": COMPTOIR},
		{"_id": COMPTOIR, "type": "lieu", "label": "Le Caravansérail des Seuils - comptoir",
		 "image": "guilde_petra_coursives.jpg", "categorie": "guilde_aventurier_comptoir", "lieu_parent": CITE,
		 "sous_categorie": "guilde_aventurier", "rang_max": "S+",
		 "pnj": [{"character": "pnj:zaydu_caravanserail_des_seuils", "nom": "Zaydu",
			"portrait": "guilde_hobbit_m_petra01.jpg", "probabilite": 1,
			"description": "Derrière le long comptoir de pierre, un jeune hobbit verse de l'eau à chaque arrivant."}]},
		{"_id": BUREAU, "type": "lieu", "label": "Le Caravansérail des Seuils - bureau de la maîtresse",
		 "image": "guilde_petra_bureau.jpg", "categorie": "bureau_maitre_guilde", "lieu_parent": CITE,
		 "relation_lieu": COMPTOIR,
		 "acces": {"gardien": "pnj:zaydu_caravanserail_des_seuils",
			"refus": "Zaydu barre la coursive d'angle d'un sourire désolé : la maîtresse ne reçoit que les "
				"aventuriers de rang A de Petra.", "cycle": 1, "conditions": [rang_min("A")]},
		 "pnj": [{"character": "pnj:shaqilath", "nom": "Shaqilath", "portrait": "guilde_ogre_f_petra01.jpg",
			"probabilite": 1, "description": "Une ogresse au foulard indigo, penchée sur une carte des pistes."}]},
		connexion("link:petra_to_le_caravanserail_des_seuils_interieur", CITE, case("guilde"), INTERIEUR, (0, 0),
			"guilde_aventurier", "sortir dans la rue", "entrer dans le caravansérail"),
		connexion("link:le_caravanserail_des_seuils_interieur_to_comptoir", INTERIEUR, (0, 0), COMPTOIR, (0, 0),
			"guilde_aventurier", "s'éloigner du comptoir", "s'approcher du comptoir"),
		connexion("link:le_caravanserail_des_seuils_comptoir_to_bureau_du_maitre", COMPTOIR, (0, 0), BUREAU, (0, 0),
			"guilde_aventurier", "redescendre au comptoir", "monter par la coursive d'angle"),
	]
	docs += [zaydu(), shaqilath()]

	# Portails transversaux (rang A de Lutecia : celui qui ouvre le voyage par Notre-Dame).
	porte_monde = {"refus": "Un Architecte vous arrête au bord du seuil : on ne le franchit qu'avec le rang A "
		"de la Guilde de Lutecia.", "cycle": 1, "conditions": [{"rang_min": {"cite": LUTECIA, "rang": "A"}}]}
	for slug, label, image, vers in (
			("khazneh", "La Khazneh", "petra_khazneh_portail.jpg", ALEXANDRIE),
			("ad_deir", "Ad-Deir", "petra_ad_deir_portail.jpg", BUCAREST),
			("qasr_al_bint", "Le Qasr al-Bint", "petra_qasr_al_bint_portail.jpg", None)):
		lid = f"lieu:petra_{slug}"
		doc = {"_id": lid, "type": "lieu", "label": label, "image": image, "categorie": "portail",
			"sous_categorie": "temple", "lieu_parent": CITE, "texte": TEXTES[slug]}
		if vers:
			doc["acces"] = dict(porte_monde)
		docs.append(doc)
		docs.append(connexion(f"link:petra_to_{slug}", CITE, case(slug), lid, (0, 0), "temple",
			"ressortir dans la cité", f"entrer dans {label[0].lower() + label[1:]}"))
		if vers:
			cite_doc = par_id[vers]
			depart, repere = ARRIVEES[vers]
			zone = zone_de(cite_doc["cells"], depart, cite_doc.get("nav"))
			if not zone:
				erreurs.append(f"{vers} : case de départ {depart} non praticable")
				continue
			docs.append(connexion(f"link:petra_{slug}_to_{vers.split(':', 1)[1]}", lid, (0, 0), vers,
				plus_proche(zone, repere), "portail", ARRIVEE_LABELS[slug],
				f"franchir le seuil vers {cite_doc.get('label')}"))

	# Temples, salles, donjons.
	for slug, temple in TEMPLES.items():
		tid = f"lieu:petra_temple_{slug}"
		tpl = templier(temple["templier"], temple)
		docs.append({"_id": tid, "type": "lieu", "label": f"Le temple de {temple['tombeau'].replace('le ', '', 1)}",
			"image": f"temple_petra_{slug}.jpg", "categorie": "temple_portail", "sous_categorie": "temple",
			"lieu_parent": CITE,
			"pnj": [{"character": tpl["_id"], "nom": tpl["nom"], "portrait": tpl["portrait"], "probabilite": 1,
				"description": tpl["description"].split(".")[0] + "."}]})
		docs.append(tpl)
		docs.append(connexion(f"link:petra_to_temple_{slug}", CITE, case(slug), tid, (0, 0), "temple_portail",
			"redescendre sur la terrasse", "entrer dans le temple"))
		d = temple["donjon"]
		spec = DONJONS[d]
		rang = RANGS_DONJONS[d]
		donjon = {"_id": f"donjon:petra_{d}", "type": "donjon", "nom": spec["nom"], "description": spec["description"],
			"portail": tid, "niveau_min": spec["niveau_min"], "niveau_max": spec["niveau_max"],
			"battle_maps": [dict(e) for e in spec["salles"]]}
		if spec.get("mode"):
			donjon["mode"] = spec["mode"]
		if d == "tresor":
			donjon["battle_maps"][1]["tresor"] = TRESOR
		docs.append(donjon)
		for i, nom_salle in enumerate(temple["salles"]):
			cells = grille_salle(SALLES[nom_salle])
			lieu = {"_id": salle_id(nom_salle), "type": "lieu", "label": SALLES_LIEUX[nom_salle]["label"],
				"image": f"petra_donjon_{nom_salle}.jpg", "categorie": "battle_map",
				"dimensions": {"x": len(cells[0]), "y": len(cells)}, "cells": cells, "nav": {},
				"tags": list(SALLES_LIEUX[nom_salle]["tags"])}
			if i == 0:
				lieu["acces"] = {"gardien": tpl["_id"],
					"refus": f"{tpl['nom']} barre le seuil : il faut un mandat de la Guilde de Petra et le rang {rang}.",
					"cycle": 1, "conditions": [mandat(*temple["salles"]), rang_min(rang)]}
			if d == "crue":
				lieu["reinfestation"] = True
			docs.append(lieu)
		if spec.get("mode") == "etages":
			e = ETAGES[d]
			s1, s2 = (salle_id(n) for n in temple["salles"])
			for salle, c in ((s1, e["entree"]), (s1, e["descente"][0]), (s2, e["descente"][1]), (s2, e["sortie"])):
				g = next(x for x in docs if x["_id"] == salle)["cells"]
				if g[c[1]][c[0]] not in (1, 5):
					erreurs.append(f"{salle} : passage {c} sur une case non praticable")
			docs += [
				connexion(f"link:petra_temple_{slug}_to_{s1.split(':')[1]}", tid, (0, 0), s1, e["entree"], "descente",
					"remonter au temple", "franchir le seuil"),
				connexion(f"link:{s1.split(':')[1]}_to_{s2.split(':')[1]}", s1, e["descente"][0], s2, e["descente"][1],
					"descente", "remonter", "descendre plus profond"),
				connexion(f"link:{s2.split(':')[1]}_to_petra_temple_{slug}", s2, e["sortie"], tid, (0, 0), "passage",
					None, "remonter à la surface"),
			]
	return docs


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = args[args.index("--dump") + 1] if "--dump" in args else None
	docs_base = ggi.charger_dump(chemin_dump)
	par_id = {d.get("_id"): d for d in docs_base}
	manquants = [i for i in (LUTECIA, ALEXANDRIE, BUCAREST) if i not in par_id]
	if manquants:
		print("✗ absents du dump : " + ", ".join(manquants))
		return 1
	erreurs = []

	chemin_levant = ggi.trouver_image("levant.jpg")
	levant = {"_id": PAYS, "type": "lieu", "label": "Levant", "image": "levant.jpg", "categorie": "pays",
		"sous_categorie": "region", "dimensions": {"x": COLS, "y": ROWS}, "tags": []}
	prop = ggi.proposer_pour_image(chemin_levant, COLS, ROWS, levant, profil="pays")
	levant = {**levant, "cells": prop["cells"], "nav": prop["nav"]}
	levant = {k: levant[k] for k in ("_id", "type", "label", "image", "categorie", "sous_categorie",
		"dimensions", "cells", "nav", "tags")}

	sortie = [levant] + docs_petra(par_id, levant, erreurs) + ITEMS
	bestiaire, _deja = docs_bestiaire_arthurien(par_id, ESPECES)
	sortie += bestiaire
	ids = [d["_id"] for d in sortie]
	erreurs += [f"_id en double : {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
	deja = [i for i in ids if i in par_id]
	if deja:
		erreurs.append("déjà en base : " + ", ".join(deja))
	if erreurs:
		print("✗ " + "\n✗ ".join(erreurs))
		return 1
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	if "--apercu" in args:
		ggi.ecrire_apercu(ggi.trouver_image("petra_city.jpg"), sortie[1]["cells"] if sortie[1]["_id"] == CITE else
			next(d for d in sortie if d["_id"] == CITE)["cells"], os.path.join(ggi.DOSSIER_JSONS, "petra_grille_apercu.png"))
		ggi.ecrire_apercu(chemin_levant, levant["cells"], os.path.join(ggi.DOSSIER_JSONS, "levant_grille_apercu.png"),
			levant["nav"])
	compte = {}
	for d in sortie:
		t = d["_id"].split(":", 1)[0]
		compte[t] = compte.get(t, 0) + 1
	print(" · ".join(f"{n} {t}" for t, n in sorted(compte.items())) + f" → {os.path.relpath(SORTIE, ggi.RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())

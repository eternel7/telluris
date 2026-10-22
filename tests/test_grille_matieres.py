"""Grille d'une cité lue par matières (`utils/grille_matieres.py`) — sans image : les sous-cases
et les lectures sont fabriquées, les seuils RELUS dans `REGLES_MATIERES`."""

from utils import grille_matieres as gm
from utils.lieux import nav_allows

R = gm.REGLES_MATIERES


def _sc(matiere):
	"""Une sous-case (L, a, b, texture) qui se classe dans `matiere`."""
	return {
		gm.VEGETATION: (60.0, R["veg_a_max"] - 5, R["veg_b_min"] + 15, 2.0),
		gm.EAU: (R["eau_l_min"] + 20, 0.0, R["eau_b_max"] - 5, 1.0),
		gm.SOMBRE: (R["sombre_l_max"] - 10, 2.0, 15.0, 2.0),
		gm.TERRE: (R["terre_l_min"] + 10, R["terre_a_min"] + 4, R["terre_b_min"] + 6, R["texture_min"] - 2),
		gm.ROCHE: (R["terre_l_min"] + 10, R["terre_a_min"] + 4, R["terre_b_min"] + 6, R["texture_min"] + 3),
		gm.PIERRE: (R["pierre_l_min"] + 8, 1.0, R["terre_b_min"] - 6, R["texture_min"] + 3),
	}[matiere]


def _lect(matiere, ecart=10.0, b=20.0):
	return {"parts": {matiere: 1.0}, "ecart": ecart, "b": b}


def test_classer_chaque_matiere():
	for m in (gm.VEGETATION, gm.EAU, gm.SOMBRE, gm.TERRE, gm.ROCHE, gm.PIERRE):
		assert gm.classer(_sc(m)) == m, m


def test_lab_blanc_et_noir():
	assert round(gm.lab((255, 255, 255))[0]) == 100
	assert round(gm.lab((0, 0, 0))[0]) == 0


def test_eau_gardee_si_bordee_de_vegetation_rejetee_si_bordee_de_pierre():
	n = 6
	taille = max(3, R["eau_taille_min"])

	def grille(bord):
		g = [[_sc(bord)] * (taille + 2) for _ in range(n)]
		for y in range(1, n - 1):
			g[y] = [_sc(bord)] + [_sc(gm.EAU)] * taille + [_sc(bord)]
		return g
	assert gm.matieres(grille(gm.VEGETATION))[2][2] == gm.EAU
	# L'ombre bleutée d'une tour : même couleur, mais bordée de pierre.
	assert gm.matieres(grille(gm.PIERRE))[2][2] == gm.SOMBRE


def test_parts_par_case_reparties():
	mat = [[gm.VEGETATION, gm.EAU], [gm.EAU, gm.EAU]]
	parts = gm.parts_par_case(mat, 1, 1)
	assert parts[0][0] == {gm.VEGETATION: 0.25, gm.EAU: 0.75}


def test_dedans_et_contour_du_polygone():
	carre = ((2, 2), (6, 2), (6, 6), (2, 6))
	dedans = gm.dedans_polygone(carre, 9, 9)
	assert dedans[4][4] and not dedans[0][0] and not dedans[8][8]
	contour = gm.polygone_cases(carre)
	assert {(2, 2), (6, 2), (6, 6), (2, 6), (4, 2), (2, 4)} <= contour
	assert (4, 4) not in contour


def test_riviere_recousue_si_la_teinte_du_trou_reste_proche():
	cells = [[1] * 12 for _ in range(3)]
	for x in (0, 1, 2, 3, 7, 8, 9, 10, 11):
		cells[1][x] = 5
	proche = [[0.0] * 12 for _ in range(3)]
	recousues = gm.recoudre_rivieres(cells, proche)
	assert sorted(recousues) == [(4, 1), (5, 1), (6, 1)]
	assert all(v == 5 for v in cells[1])


def test_riviere_pas_recousue_si_la_teinte_change():
	cells = [[1] * 12 for _ in range(3)]
	for x in (0, 1, 2, 3, 7, 8, 9, 10, 11):
		cells[1][x] = 5
	b = [[0.0] * 12 for _ in range(3)]
	for x in (4, 5, 6):
		b[1][x] = R["riviere_ecart_b"] * 3
	assert gm.recoudre_rivieres(cells, b) == []
	assert cells[1][5] == 1


def test_riviere_pas_recousue_au_dela_du_trou_max():
	trou = R["riviere_trou_max"] + 2
	largeur = 4 + trou + 4
	cells = [[5] * 4 + [1] * trou + [5] * 4]
	assert gm.recoudre_rivieres(cells, [[0.0] * largeur]) == []


def test_pont_rouvert_entre_deux_eaux():
	cells = [[1, 1, 1], [5, 0, 5], [1, 1, 1]]
	parts = [[{gm.SOMBRE: 1.0}] * 3 for _ in range(3)]
	assert gm.poser_ponts(cells, parts) == [(1, 1)]
	assert cells[1][1] == 1


def test_pas_de_pont_dans_la_pierre():
	cells = [[1, 1, 1], [5, 0, 5], [1, 1, 1]]
	parts = [[{gm.PIERRE: 1.0}] * 3 for _ in range(3)]
	assert gm.poser_ponts(cells, parts) == []


def test_corriger_pierre_toit_foule_eau():
	cells = [[1, 1, 1, 5]]
	lect = [[
		_lect(gm.PIERRE),
		_lect(gm.SOMBRE, ecart=R["toit_ecart_max"] - 1),   # toit : sombre et uni
		_lect(gm.SOMBRE, ecart=R["toit_ecart_max"] + 3),   # place noire de monde : bigarrée
		_lect(gm.VEGETATION),                               # un 5 sans eau
	]]
	comptes = gm.corriger(cells, lect)
	assert cells == [[0, 0, 1, 1]]
	assert comptes["pierre"] == 1 and comptes["toit"] == 1


def test_corriger_ne_rouvre_jamais_pres_de_l_enceinte():
	cells = [[0, 0, 0, 0]]
	lect = [[_lect(gm.TERRE)] * 4]
	masque = [[True, False, False, False]]
	gm.corriger(cells, lect, masque)
	assert cells == [[0, 0, 1, 1]]


def _cite(n=14):
	"""Une cité carrée dans un pré, tout praticable, rues bigarrées partout."""
	cells = [[1] * n for _ in range(n)]
	lect = [[_lect(gm.TERRE, ecart=R["dedans_uni_ecart"] + 5) for _ in range(n)] for _ in range(n)]
	return cells, lect


def _zone(cells, nav, depart):
	h, w = len(cells), len(cells[0])
	vues, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				nx, ny = x + dx, y + dy
				if ((dx or dy) and 0 <= nx < w and 0 <= ny < h and (nx, ny) not in vues
						and cells[ny][nx] == 1 and nav_allows(nav, x, y, dx, dy)):
					vues.add((nx, ny))
					pile.append((nx, ny))
	return vues


def test_cite_dedans_et_dehors_separes_par_le_rempart():
	cells, lect = _cite()
	enceinte = ((3, 3), (10, 3), (10, 10), (3, 10))
	res = gm.proposer_cite(cells, [], lect, enceinte)
	c, nav = res["cells"], res["nav"]
	dedans, dehors = _zone(c, nav, (6, 6)), _zone(c, nav, (0, 0))
	assert dedans and dehors and not dedans & dehors
	# Rempart et chemin de ronde fermés, sans un seul mur nav sur un rempart droit.
	assert c[3][6] == 0 and c[4][6] == 0
	assert nav == {}
	assert res["cells"] is not cells and cells[3][6] == 1   # entrée non mutée


def test_cite_nav_seulement_sur_un_rempart_en_diagonale():
	cells, lect = _cite(16)
	losange = ((8, 1), (14, 7), (8, 13), (2, 7))
	res = gm.proposer_cite(cells, [], lect, losange)
	c, nav, dedans = res["cells"], res["nav"], res["dedans"]
	assert not _zone(c, nav, (8, 7)) & _zone(c, nav, (0, 0))
	# Chaque bit est posé côté dedans, sur un pas qui sort de l'enceinte.
	for cle, masque in nav.items():
		x, y = map(int, cle.split(","))
		assert dedans[y][x]


def test_cite_monument_ferme_et_chemin_rouvert():
	cells, lect = _cite()
	enceinte = ((1, 1), (12, 1), (12, 12), (1, 12))
	monument = ((5, 5), (9, 5), (9, 9), (5, 9))
	res = gm.proposer_cite(cells, [], lect, enceinte, [monument], chemins=[((7, 9), (7, 7))])
	c = res["cells"]
	assert c[6][6] == 0 and c[8][8] == 0
	assert c[7][7] == 1 and c[8][7] == 1 and c[9][7] == 1
	assert res["rapport"]["chemins"] == 3


def test_cite_talus_uni_ferme_au_dedans_sauf_rue_tracee():
	cells, lect = _cite()
	for y in range(5, 8):
		for x in range(5, 8):
			lect[y][x] = _lect(gm.VEGETATION, ecart=R["dedans_uni_ecart"] - 2)
	enceinte = ((1, 1), (12, 1), (12, 12), (1, 12))
	# Une rue tracée traverse le talus de part en part (une rue d'une case serait une poche).
	res = gm.proposer_cite(cells, [(6, 5), (6, 6), (6, 7)], lect, enceinte)
	c = res["cells"]
	assert c[5][5] == 0 and c[7][7] == 0
	assert c[5][6] == c[6][6] == c[7][6] == 1   # la rue tracée reste
	assert res["rapport"]["talus"] == 6


def test_cite_cadre_ferme():
	cells, lect = _cite()
	cadre = [[x == 0 for x in range(14)] for _ in range(14)]
	res = gm.proposer_cite(cells, [], lect, ((3, 3), (10, 3), (10, 10), (3, 10)), cadre=cadre)
	assert all(ligne[0] == 0 for ligne in res["cells"])


# ── Strate du cœur, percées, portes ──────────────────────────────────────────────

PAVE = (R["sol_l_haut"] + 5, 2.0, R["sol_b_min"] + 10, 3.0)       # sol plein
TOIT = (R["sol_l_bas"] - 5, R["sol_a_max"] + 6, 20.0, 3.0)        # ni clair ni ocre


def _sc_grille(cols, rows, k, motif):
	"""Sous-cases k×k par case, motif(x, y) → sous-case de la case."""
	return [[motif(sx // k, sy // k) for sx in range(cols * k)] for sy in range(rows * k)]


def test_sol_pave_et_toit():
	assert gm.sol(PAVE) == 1.0
	assert gm.sol(TOIT) == 0.0
	assert gm.sol((R["sol_l_haut"], R["sol_a_max"] + 5, 30.0, 0.0)) == R["sol_hors_teinte"]


def test_creuser_suit_le_pave_plutot_que_le_toit():
	# Deux ancres aux deux bouts ; une rue de pavé fait un détour par la rangée 0, la ligne
	# droite (rangée 2) passe sur les toits.
	cols, rows = 7, 3

	def motif(x, y):
		return PAVE if y == 0 or x in (0, cols - 1) else TOIT
	g = _sc_grille(cols, rows, 2, motif)
	dedans = [[True] * cols for _ in range(rows)]
	interdites = [[False] * cols for _ in range(rows)]
	res = gm.creuser_coeur(g, cols, rows, dedans, interdites, [(0, 2), (cols - 1, 2)])
	assert (3, 0) in res["cases"]          # la rue de pavé
	assert (3, 2) not in res["cases"]      # pas la ligne droite sur les toits
	assert res["isolees"] == []


def test_creuser_ne_traverse_jamais_une_interdite():
	cols, rows = 5, 3
	g = _sc_grille(cols, rows, 2, lambda x, y: PAVE)
	dedans = [[True] * cols for _ in range(rows)]
	interdites = [[x == 2 for x in range(cols)] for _ in range(rows)]
	res = gm.creuser_coeur(g, cols, rows, dedans, interdites, [(0, 1), (4, 1)])
	assert not any(x == 2 for x, _y in res["cases"])
	assert (4, 1) in res["isolees"]        # l'ancre de l'autre côté reste signalée isolée


def test_places_ouvertes_et_reliees():
	cols, rows = 9, 5

	def motif(x, y):
		return PAVE if (x >= 6 and y <= 2) or y == 4 else TOIT
	g = _sc_grille(cols, rows, 2, motif)
	dedans = [[True] * cols for _ in range(rows)]
	interdites = [[False] * cols for _ in range(rows)]
	res = gm.creuser_coeur(g, cols, rows, dedans, interdites, [(0, 4)])
	assert {(7, 1), (8, 0)} <= res["places"] <= res["cases"]


def _cite_coeur():
	n = 16
	cells, lect = _cite(n)
	enceinte = ((3, 3), (12, 3), (12, 12), (3, 12))
	# Le cœur : toits partout, sauf une rue de pavé de la porte ouest à la porte est.
	g = _sc_grille(n, n, 2, lambda x, y: PAVE if y == 8 else TOIT)
	return cells, lect, enceinte, g


def test_cite_strate_du_coeur_et_percees():
	cells, lect, enceinte, g = _cite_coeur()
	portes = [(2.5, 8.5), (13.5, 8.5)]
	res = gm.proposer_cite(cells, [], lect, enceinte, grille_sc=g, portes=portes)
	c = res["cells"]
	# Le cœur repart de 0 : seule la rue de pavé est ouverte (le reste était « praticable »).
	assert c[8][7] == 1 and c[6][7] == 0
	# Percées : le chemin de ronde s'ouvre derrière chaque arche, la ligne du mur non.
	assert c[8][3] == 0 and c[8][4] == 1 and c[8][11] == 1
	(dehors_o, dedans_o), (dehors_e, dedans_e) = res["portes"]
	assert dehors_o[0] < 3 and dedans_o[0] > 3 and dedans_e[0] < 12 < dehors_e[0]
	assert res["rapport"]["portes_reliees"] == {"ok": True, "manques": []}


def test_cite_direction_de_percee_imposee():
	cells, lect, enceinte, g = _cite_coeur()
	# Arche au sud, percée imposée vers le nord : elle ouvre la colonne de l'arche.
	res = gm.proposer_cite(cells, [], lect, enceinte, grille_sc=g, portes=[(7.5, 12.5, 0, -1)])
	assert [c[0] for c in res["rapport"]["percees"][0]] == [7] * len(res["rapport"]["percees"][0])


def test_portes_reliees_signale_le_cote():
	cells = [[1, 1, 0, 1, 1]]
	portes = [((0, 0), (1, 0)), ((4, 0), (3, 0))]
	res = gm.portes_reliees(cells, {}, portes)
	assert not res["ok"] and set(res["manques"]) == {("dehors", 0, 1), ("dedans", 0, 1)}
	assert gm.portes_reliees([[1] * 5], {}, portes)["ok"]


def test_portes_de_cite_apparie_par_id_y_compris_numerotees():
	docs = [
		{"_id": "lieu:ville_porte_nord_exterieur", "type": "lieu", "categorie": "Porte de rempart"},
		{"_id": "lieu:ville_porte_nord_interieur", "type": "lieu", "categorie": "Porte de rempart"},
		{"_id": "lieu:ville_porte_douve_exterieur01", "type": "lieu", "categorie": "Porte de rempart"},
		{"_id": "lieu:ville_porte_douve_interieur01", "type": "lieu", "categorie": "Porte de rempart"},
		{"_id": "lieu:ville_forge", "type": "lieu", "categorie": "forge"},
	]

	def lien(lieu, pos):
		return {"type": "connection", "nodes": [{"lieu": "lieu:ville", "pos": pos}, {"lieu": lieu, "pos": [0, 0]}]}
	docs += [lien("lieu:ville_porte_nord_exterieur", [1, 1]), lien("lieu:ville_porte_nord_interieur", [1, 3]),
		lien("lieu:ville_porte_douve_exterieur01", [9, 9]), lien("lieu:ville_porte_douve_interieur01", [7, 7]),
		lien("lieu:ville_forge", [5, 5])]
	assert gm.portes_de_cite(docs, "lieu:ville") == {
		"lieu:ville_porte_nord": [(1, 1), (1, 3)],
		"lieu:ville_porte_douve#01": [(9, 9), (7, 7)],
	}


# ── Traits (cel shading), dehors, portes imposées ───────────────────────────────────

NOIR, HERBE_PX, TUILE_PX = (0, 0, 0), (110, 160, 60), (190, 80, 50)


def _image(cols, rows, k, motif):
	"""Pixels plats d'une image cols·k × rows·k ; motif(px, py) → (r, g, b)."""
	w, h = cols * k, rows * k
	return [motif(px, py) for py in range(h) for px in range(w)], w, h


def test_masques_pixels_encre_sol_toit():
	m = gm.masques_pixels([NOIR, HERBE_PX, TUILE_PX], 3, 1)
	assert list(m["encre"]) == [1, 0, 0]
	assert list(m["sol"]) == [0, 1, 0]
	assert list(m["toit"]) == [0, 0, 1]


def test_trait_noir_separe_deux_cases():
	k = 8
	# Deux cases d'herbe ; un trait vertical à la frontière dans le second cas.
	sans, w, h = _image(2, 1, k, lambda px, py: HERBE_PX)
	avec, _, _ = _image(2, 1, k, lambda px, py: NOIR if px == k else HERBE_PX)
	assert gm.relies_sans_trait(gm.masques_pixels(sans, w, h), 2, 1, (0, 0), (1, 0))
	assert not gm.relies_sans_trait(gm.masques_pixels(avec, w, h), 2, 1, (0, 0), (1, 0))


def test_elaguer_retire_le_morceau_isole_par_un_trait_sans_ancre():
	k, cols = 6, 6
	# Un trait vertical entre la colonne 3 et la colonne 4 : à droite, deux colonnes isolées.
	pixels, w, h = _image(cols, 2, k, lambda px, py: NOIR if px == 4 * k else HERBE_PX)
	m = gm.masques_pixels(pixels, w, h)
	cells = [[1] * cols for _ in range(2)]
	cases = [(x, y) for y in range(2) for x in range(cols)]
	res = gm.elaguer(cells, cases, m, [(0, 0)], garder_min=10)
	assert cells == [[1, 1, 1, 1, 0, 0], [1, 1, 1, 1, 0, 0]]
	assert res["composantes"] == 2
	# Avec une ancre de l'autre côté, le morceau reste.
	cells = [[1] * cols for _ in range(2)]
	gm.elaguer(cells, cases, m, [(0, 0), (5, 1)], garder_min=10)
	assert all(v == 1 for ligne in cells for v in ligne)


def test_lire_dehors_sol_toit_eau():
	cells = [[0, 0, 0]]
	pixels_case = [[{"sol": 0.9, "toit": 0.0, "encre": 0.1}, {"sol": 0.2, "toit": 0.7, "encre": 0.1},
		{"sol": 0.9, "toit": 0.0, "encre": 0.0}]]
	lect = [[_lect(gm.VEGETATION), _lect(gm.SOMBRE), _lect(gm.EAU)]]
	gm.lire_dehors(cells, [(0, 0), (1, 0), (2, 0)], pixels_case, lect)
	assert cells == [[1, 0, 5]]


def test_cite_portes_imposees_posees_et_raccordees():
	cells, lect, enceinte, g = _cite_coeur()
	portes = [(2.5, 8.5), (13.5, 8.5)]
	# Case dedans imposée dans le chemin de ronde, case dehors imposée dans un coin à 0.
	cells[8][1] = 0
	res = gm.proposer_cite(cells, [], lect, enceinte, grille_sc=g, portes=portes,
		portes_imposees=[((1, 8), (4, 9)), (None, None)])
	assert res["portes"][0] == ((1, 8), (4, 9))
	assert res["cells"][9][4] == 1 and res["cells"][8][1] == 1
	assert res["rapport"]["percees"][0] == [(4, 9)]
	assert res["rapport"]["portes_reliees"]["ok"]


def test_cite_routes_de_porte_a_porte():
	n = 18
	cells, lect = _cite(n)
	enceinte = ((2, 2), (15, 2), (15, 15), (2, 15))
	# Deux rues parallèles de pavé entre les portes ouest et est : deux routes.
	g = _sc_grille(n, n, 2, lambda x, y: PAVE if y in (6, 11) or x in (4, 13) else TOIT)
	res = gm.proposer_cite(cells, [], lect, enceinte, grille_sc=g,
		portes=[(1.5, 8.5, 1, 0), (16.5, 8.5, -1, 0)])
	assert res["rapport"]["coeur"]["routes"] == [(0, 1, 2)]
	assert res["cells"][6][8] == 1 and res["cells"][11][8] == 1

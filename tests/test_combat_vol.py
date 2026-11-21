# tests/test_combat_vol.py
#
# Espèces VOLANTES (tag `vol`) et lieux COUVERTS (tag `couvert`).
#
# À découvert, un volant n'est bloqué par aucun terrain praticable (falaise comprise). Sous
# couvert — grotte, catacombes — il ne déploie pas ses ailes : il marche, V // 3 et
# actions // 3. Un dragon ne vole pas dans une grotte.
#
# Les points sensibles ne sont pas les divisions, ce sont leurs SURVIES : l'entrave doit
# tenir à l'expiration d'un buff de V (`_refresh_snapshot_stats` recompose tout), et se
# lever quand le groupe débouche sur un étage découvert (`actions_max` est figé au snapshot).

from utils import combat as combat_util

from tests.test_combat_groupe import character, combat_doc, db  # noqa: F401 (fixture)


def espece(tags=("monstre", "vol")):
	"""Fourchettes DÉGÉNÉRÉES : V 6, Ag 40 ⇒ actions ceil(40/40 + 6/2) = 4, déplacement 6,
	initiative (40 + 6×20) // 3 = 53. Sous couvert : V 2 ⇒ déplacement 2, initiative
	(40 + 40) // 3 = 26, actions 4 // 3 = 1."""
	return {
		"_id": "espece:griffon_test", "nom": "Griffon", "tags": list(tags),
		"base_attributes": {
			"V": {"min": 6, "max": 6}, "F": {"min": 30, "max": 30},
			"R": {"min": 30, "max": 30}, "Ag": {"min": 40, "max": 40},
			"Vol": {"min": 10, "max": 10}, "Int": {"min": 10, "max": 10},
			"Cha": {"min": 0, "max": 0}, "Ch": {"min": 10, "max": 10},
		},
	}


def griffon(idx=0, tags=("monstre", "vol")):
	return combat_util.build_monster_snapshot(espece(tags), None, idx)


def carte(tags, w=8, h=8):
	return {"_id": "lieu:carte_test", "type": "lieu", "categorie": "battle_map", "tags": list(tags),
			"image": "carte.png", "dimensions": {"x": w, "y": h},
			"cells": [[1] * w for _ in range(h)], "nav": {}}


# ── Les prédicats ────────────────────────────────────────────────────────────────

def test_une_espece_vole_par_son_tag():
	assert combat_util.espece_vole(espece())
	assert not combat_util.espece_vole(espece(("monstre",)))
	assert not combat_util.espece_vole(None)


def test_un_lieu_est_couvert_si_une_des_listes_de_tags_le_dit():
	assert combat_util.lieu_couvert(["foret"], ["grotte", "couvert"])
	assert combat_util.lieu_couvert(["couvert"], None)
	assert not combat_util.lieu_couvert(["grotte", "catacombe"], [])


def test_seule_une_espece_volante_porte_la_marque_au_snapshot():
	assert griffon()["vol_espece"] is True
	# Clé ABSENTE sinon : un snapshot ordinaire reste celui d'avant, à la lettre.
	assert "vol_espece" not in griffon(tags=("monstre",))


def test_un_volant_franchit_la_falaise_pas_le_mur():
	cells = [[1, combat_util.TERRAIN_FALAISE, 0]]
	assert combat_util._walkable(cells, 1, 0, flying=True)
	assert not combat_util._walkable(cells, 1, 0, flying=False)
	assert not combat_util._walkable(cells, 2, 0, flying=True)


# ── L'entrave ────────────────────────────────────────────────────────────────────

def test_a_decouvert_il_vole_sans_rien_perdre():
	g = griffon()
	combat_util._appliquer_couvert(g, couvert=False)
	assert g["volant"] is True and "sous_couvert" not in g
	assert (g["actions_max"], g["actions_restantes"], g["deplacement"], g["initiative"]) == (4, 4, 6, 53)


def test_sous_couvert_il_marche_v_et_actions_divises_par_3():
	g = griffon()
	combat_util._appliquer_couvert(g, couvert=True)
	assert g["volant"] is False and g["sous_couvert"] is True
	assert g["actions_max"] == 4 // combat_util.COUVERT_DIVISEUR
	assert g["actions_restantes"] == g["actions_max"]
	assert g["deplacement"] == 6 // combat_util.COUVERT_DIVISEUR
	assert g["initiative"] == (40 + (6 // combat_util.COUVERT_DIVISEUR) * 20) // 3


def test_l_entrave_est_reversible():
	"""Un étage couvert puis un étage à ciel ouvert : ailes, actions et vitesse reviennent."""
	g = griffon()
	combat_util._appliquer_couvert(g, couvert=True)
	combat_util._appliquer_couvert(g, couvert=False)
	assert g["volant"] is True and "sous_couvert" not in g
	assert (g["actions_max"], g["deplacement"], g["initiative"]) == (4, 6, 53)
	# Deux étages couverts d'affilée ne divisent pas deux fois.
	combat_util._appliquer_couvert(g, couvert=True)
	combat_util._appliquer_couvert(g, couvert=True)
	assert (g["actions_max"], g["deplacement"]) == (1, 2)


def test_l_entrave_survit_a_un_buff_de_vitesse():
	g = griffon()
	combat_util._appliquer_couvert(g, couvert=True)
	g["effets_actifs"] = [{"source_id": "potion:celerite", "buffs": {"V": 3}, "restants": 2}]
	combat_util._refresh_snapshot_stats(g)
	assert g["deplacement"] == (6 + 3) // combat_util.COUVERT_DIVISEUR
	g["effets_actifs"] = []
	combat_util._refresh_snapshot_stats(g)
	assert g["deplacement"] == 6 // combat_util.COUVERT_DIVISEUR


def test_une_espece_non_volante_n_est_jamais_touchee():
	rat = griffon(tags=("monstre",))
	avant = dict(rat)
	combat_util._appliquer_couvert(rat, couvert=True)
	assert rat == avant


# ── Les points d'entrée ─────────────────────────────────────────────────────────

def test_le_combat_decide_du_couvert_par_la_battle_map_ou_la_zone(db):
	doc = combat_util.create_combat_doc(character(), [griffon()], [], "carte.png",
										battle_map=carte(["grotte", "couvert"]))
	assert doc["couvert"] is True
	g = doc["monstres"][0]
	assert g["volant"] is False and g["actions_max"] == 1 and g["deplacement"] == 2

	doc = combat_util.create_combat_doc(character(), [griffon()], ["couvert"], "carte.png",
										battle_map=carte(["foret"]))
	assert doc["couvert"] is True and doc["monstres"][0]["volant"] is False

	doc = combat_util.create_combat_doc(character(), [griffon()], ["foret"], "carte.png",
										battle_map=carte(["clariere"]))
	assert doc["couvert"] is False
	assert doc["monstres"][0]["volant"] is True and doc["monstres"][0]["actions_max"] == 4


def test_changer_d_etage_rend_ses_ailes_a_un_volant(db):
	"""Le groupe débouche d'un étage couvert sur une salle à ciel ouvert : le griffon qu'il
	a invoqué (dans `joueurs`) et les monstres neufs volent de nouveau."""
	allie = griffon(idx=9)
	allie["id"] = "joueur_1"
	combat_util._appliquer_couvert(allie, couvert=True)
	doc = combat_doc([allie], [], couvert=True,
					 etages={"donjon": "donjon:x", "etage": "lieu:e1", "passages": [], "archives": []})
	ouvert = carte(["donjon"])
	ouvert["_id"] = "lieu:e2"
	combat_util.changer_d_etage(doc, ouvert, {"x": 1, "y": 1}, [griffon()], [])
	assert doc["couvert"] is False
	assert allie["volant"] is True and allie["actions_max"] == 4
	assert doc["monstres"][0]["volant"] is True


# ── Se faufiler entre les piliers (ailes déployées) ─────────────────────────────
# Un volant à découvert n'est arrêté que par une LIGNE de 0 : un pilier isolé passe sous
# ses ailes. Sous couvert, abattu, ailes brisées ou vol magique seul : rien ne change.

def test_un_pilier_isole_se_survole_une_ligne_non():
	cells = [[1, 1, 1, 1, 1],
			 [1, 0, 1, 0, 1],
			 [1, 1, 1, 0, 1],
			 [1, 1, 1, 1, 1]]
	assert combat_util._pilier_isole(cells, 1, 1)
	assert not combat_util._pilier_isole(cells, 3, 1)   # (3,1)-(3,2) : une ligne
	assert combat_util._walkable(cells, 1, 1, flying=True, ailes=True)
	assert not combat_util._walkable(cells, 1, 1, flying=True)
	assert not combat_util._walkable(cells, 3, 1, flying=True, ailes=True)
	# Deux 0 en DIAGONALE font aussi une ligne.
	diag = [[0, 1], [1, 0]]
	assert not combat_util._pilier_isole(diag, 0, 0)


def test_seules_des_ailes_deployees_se_faufilent():
	g = griffon()
	combat_util._appliquer_couvert(g, couvert=False)
	assert combat_util._ailes_deployees(g)
	combat_util._appliquer_couvert(g, couvert=True)
	assert not combat_util._ailes_deployees(g)
	g = griffon()
	combat_util._appliquer_couvert(g, couvert=False)
	g["ailes_brisees"] = True
	assert not combat_util._ailes_deployees(g)
	# Le vol MAGIQUE seul ne se faufile pas (la marche du joueur reste deplacement.js).
	assert not combat_util._ailes_deployees({"vol_magique": True})


def test_les_coins_du_nav_cedent_aux_ailes_pas_les_murs_fins_ni_les_lignes():
	cells = [[1, 1], [1, 1]]
	nav = {"0,0": 8 | 4}     # coin bas-droite ET mur fin à droite interdits depuis (0,0)
	assert not combat_util._pas_nav_ok(nav, cells, 0, 0, 1, 1)
	assert combat_util._pas_nav_ok(nav, cells, 0, 0, 1, 1, ailes=True)
	assert not combat_util._pas_nav_ok(nav, cells, 0, 0, 1, 0, ailes=True)
	# Coin interdit ENTRE deux 0 : franchir une ligne, même en vol.
	ligne = [[1, 0], [0, 1]]
	assert not combat_util._pas_nav_ok(nav, ligne, 0, 0, 1, 1, ailes=True)
	# Jamais plus strict que la marche : sans nav, la diagonale reste permise.
	assert combat_util._pas_nav_ok({}, ligne, 0, 0, 1, 1, ailes=True)


def _foret_a_piliers(w=12, h=9):
	"""Clairière plantée d'un arbre isolé toutes les deux cases (colonnes et lignes paires) :
	aucun rectangle 3x2 libre n'y bouge d'une case sans heurter un tronc."""
	return [[0 if (x % 2 == 0 and y % 2 == 0) else 1 for x in range(w)] for y in range(h)]


def test_un_grand_volant_se_faufile_entre_les_arbres():
	cells = _foret_a_piliers()
	grid = {"cells": cells, "dims": {"x": len(cells[0]), "y": len(cells)}, "nav": {}}
	dragon = {"pos": {"x": 1, "y": 1}, "cap": "bas", "jeton": {"largeur": 3, "profondeur": 2,
			  "forme": "triangle"}}
	a_pied = dict(dragon)
	vole = dict(dragon, volant=True)
	for acteur, attendu in ((a_pied, False), (vole, True)):
		praticable, nav_ok = combat_util._predicats_jeton(grid, acteur)
		bouge = any(combat_util.jetons.pas_jeton(acteur, dx, dy, set(), praticable, nav_ok)
					for dx, dy in combat_util.MOVE_OFFSETS)
		assert bouge is attendu


def test_l_invocation_evite_la_poche_d_ou_elle_ne_sort_pas():
	"""Le lanceur se tient dans une poche 4x2 murée en LIGNE continue (aucune aile n'y passe),
	ouverte d'une seule case : le 3x2 y tient, à une case de lui — c'était la place retenue —,
	mais n'en sortirait jamais. L'invocation surgit dehors, de l'autre côté de l'ouverture."""
	w, h = 12, 8
	cells = [[1] * w for _ in range(h)]
	for x in range(0, 6):
		cells[0][x] = 0
		cells[3][x] = 0
	for y in range(0, 4):
		cells[y][0] = 0
		cells[y][5] = 0
	cells[3][1] = 1          # l'ouverture, une case, sous le lanceur
	grid = {"cells": cells, "dims": {"x": w, "y": h}, "nav": {}}
	jeton = {"largeur": 3, "profondeur": 2, "forme": "triangle"}
	poche = {(x, y) for x in range(1, 5) for y in range(1, 3)}
	doc = {"joueurs": [{"id": "joueur_0", "pos": {"x": 1, "y": 1}, "currentPV": 10}], "monstres": []}

	# Sans la condition de sortie, la pose la plus proche est bien dans la poche…
	sonde = {"jeton": jeton}
	region = combat_util._reachable_region(cells, grid["dims"], {}, (1, 1), True, True)
	libres = sorted((c for c in region if c != (1, 1)),
					key=lambda c: (max(abs(c[0] - 1), abs(c[1] - 1)), c[1], c[0]))
	assert combat_util._poser_emprise(sonde, libres, region, {(1, 1)}, doc["joueurs"][0])
	assert set(combat_util.jetons.cases_emprise(sonde)) <= poche
	assert not combat_util._emprise_se_degage(sonde, grid, ailes=True)

	# … l'invocation, elle, choisit une place d'où elle peut sortir.
	place = combat_util._cases_invocation(doc, grid, doc["joueurs"][0], 1, jeton, ailes=True)[0]
	posee = {"pos": place["pos"], "cap": place["cap"], "jeton": jeton}
	assert not place["reduit"]
	assert set(combat_util.jetons.cases_emprise(posee)).isdisjoint(poche)
	assert combat_util._emprise_se_degage(posee, grid, ailes=True)

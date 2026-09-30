"""Proposition de grille de terrain depuis l'image d'une carte (`utils/grille_image.py`).

Ces tests n'ouvrent aucune image : le module ne dépend de RIEN (surtout pas de Pillow, absent
de l'environnement de collecte locale — cf. CLAUDE.md § Running tests), il reçoit des
échantillons déjà réduits. C'est précisément ce découpage qui rend la classification testable ;
`dev/gen_grille_image.py` et l'endpoint `grille_proposee` sont les seuls à toucher un fichier.

Ce que ces tests verrouillent, dans l'ordre d'importance :
  1. la règle qui porte tout l'outil — à couleur ÉGALE, c'est la densité de traits qui sépare
     un pâté de maisons d'un champ ;
  2. le fait que rien ne soit seuillé en ABSOLU : la même scène plus sombre ou plus chaude doit
     donner la même grille, sans quoi l'outil ne servirait que sur la carte qui l'a réglé ;
  3. la forme de la matrice, que `dimensions_coherentes` refuse en 422 si elle dérape ;
  4. le lissage, qui ne doit PAS murer une ruelle de deux cases ;
  5. la notation, qui doit dénoncer un classifieur tout-`1` au lieu de le féliciter.
"""

from utils import grille_image as gi

# Trois teintes du parchemin des cartes de cité, mesurées sur `auxerre_start_city.png` sous les
# cases que l'auteur a peintes 0, 1 et 5.
BATI = (140, 118, 92)      # terracotta des toits — le rouge domine
CHAMP = (118, 130, 85)     # campagne — le vert domine
EAU = (99, 156, 180)       # la rivière — le rouge est le canal le plus faible


def _echantillons(cases):
	"""(couleurs, contours) à plat depuis une liste de lignes de (rgb, contours)."""
	couleurs, contours = [], []
	for ligne in cases:
		for rgb, bord in ligne:
			couleurs.append(rgb)
			contours.append(bord)
	return couleurs, contours


def _scene(taille=6, foret=False, place=False):
	"""Une scène minimale : une colonne d'eau, un bloc bâti dense, le reste en campagne.
	`foret` ajoute un bosquet aussi dessiné que la ville (2×2, en bas à droite) ; `place`, une
	rangée de cases couleur de toit mais LISSES (une place pavée) sous le bloc bâti."""
	cases = []
	for y in range(taille):
		ligne = []
		for x in range(taille):
			if x == 0:
				ligne.append((EAU, 10))
			elif 2 <= x <= 4 and 1 <= y <= 4:
				ligne.append((BATI, 200))
			elif place and 2 <= x <= 4 and y == 5:
				ligne.append((BATI, 20))
			elif foret and taille - 3 <= x <= taille - 2 and taille - 3 <= y <= taille - 2:
				ligne.append((CHAMP, 250))
			else:
				ligne.append((CHAMP, 20))
		cases.append(ligne)
	return cases


# ── 1. La règle qui porte l'outil ────────────────────────────────────────────────────────
def test_a_couleur_egale_la_densite_de_traits_separe_le_bati_du_champ():
	"""L'invariant central : à teinte ÉGALE, c'est la densité de traits (toits, murs,
	ombres) qui fait le bâti — une place pavée couleur de toit reste libre. Le poids des
	contours du profil ville est positif ; si ce test tombe, il a été annulé."""
	assert gi.PROFILS_GRILLE["ville"]["obstacle"]["contours"] > 0
	cells = gi.grille_depuis_echantillons(*_echantillons(_scene(8, place=True)), 8, 8)
	assert cells[2][3] == gi.TERRAIN_INACCESSIBLE      # toits denses
	assert cells[5][3] == gi.TERRAIN_LIBRE             # même teinte, lisse


def test_la_foret_dense_reste_libre_malgre_ses_traits():
	"""La forêt qui entoure Auxerre est aussi dessinée qu'une ville ; c'est sa COULEUR qui la
	trahit (verte, pas rouge). En comptant les traits seuls, la moitié de la campagne passait
	pour des maisons."""
	cells = gi.grille_depuis_echantillons(*_echantillons(_scene(8, foret=True)), 8, 8)
	assert cells[6][6] == gi.TERRAIN_LIBRE
	assert cells[2][3] == gi.TERRAIN_INACCESSIBLE


def test_l_eau_l_emporte_sur_le_bati():
	"""Un pont ou une berge très dessinée reste de l'eau : l'ordre des deux règles n'est pas
	commutatif."""
	couleurs, contours = _echantillons(_scene())
	repere = gi.calibrer(couleurs, contours)
	assert gi.classer_case(EAU, 255, repere) == gi.TERRAIN_EAU


# ── 2. Rien n'est seuillé en absolu ──────────────────────────────────────────────────────
def test_la_meme_scene_plus_sombre_donne_la_meme_grille():
	"""⚠️ LA raison d'être de `calibrer`. Les deux seules cartes peintes à la main n'ont pas
	le même étalonnage : l'eau d'Auxerre est bleue (99,156,180), celle de Lutèce un turquoise
	désaturé (146,169,151). Une palette absolue calée sur l'une classe l'eau de l'autre en
	terre ferme."""
	claire = _scene()
	sombre = [[(tuple(max(0, c - 40) for c in rgb), bord) for rgb, bord in ligne]
		for ligne in claire]
	attendue = gi.grille_depuis_echantillons(*_echantillons(claire), 6, 6)
	obtenue = gi.grille_depuis_echantillons(*_echantillons(sombre), 6, 6)
	assert obtenue == attendue


def test_une_carte_sans_eau_ne_produit_aucune_case_d_eau():
	"""⚠️ Le garde-fou `eau_froideur_minimale`. Sans lui, la médiane est celle de la terre
	ferme et les cases les plus froides du simple bruit franchissent le seuil RELATIF à elles
	seules : un delta de bruit promu en fleuve, sur une carte qui n'a pas de rivière."""
	cases = [[((120 + x, 118, 90 + y), 30) for x in range(8)] for y in range(8)]
	cells = gi.grille_depuis_echantillons(*_echantillons(cases), 8, 8)
	assert gi.TERRAIN_EAU not in gi.comptes(cells)


# ── 3. La forme de la matrice ────────────────────────────────────────────────────────────
def test_la_matrice_est_indexee_y_puis_x_et_toutes_ses_lignes_sont_pleines():
	"""La contrainte exacte que `utils.lieux.dimensions_coherentes` refuse en 422 : autant de
	lignes que `dimensions.y`, et `dimensions.x` entrées sur CHACUNE."""
	couleurs, contours = _echantillons([[(CHAMP, 20)] * 7 for _ in range(4)])
	cells = gi.grille_depuis_echantillons(couleurs, contours, 7, 4)
	assert len(cells) == 4
	assert all(len(ligne) == 7 for ligne in cells)


def test_un_echantillon_manquant_donne_une_case_libre_sans_decaler_la_grille():
	"""Fail-soft : tronquer la suite décalerait toutes les cases d'après, ce qui ne se verrait
	qu'en jeu."""
	cells = gi.grille_depuis_echantillons([CHAMP] * 5, [20] * 5, 4, 3)
	assert len(cells) == 3 and all(len(ligne) == 4 for ligne in cells)
	assert cells[2] == [gi.TERRAIN_LIBRE] * 4


def test_aucune_valeur_hors_du_vocabulaire_0_1_5():
	"""Le pinceau propose 0/1/2/3/5/9 ; l'outil s'en tient aux trois des cartes de cité."""
	cells = gi.grille_depuis_echantillons(*_echantillons(_scene()), 6, 6)
	assert set(gi.comptes(cells)) <= {gi.TERRAIN_INACCESSIBLE, gi.TERRAIN_LIBRE, gi.TERRAIN_EAU}


# ── 4. Le lissage ────────────────────────────────────────────────────────────────────────
def test_le_lissage_absorbe_une_case_isolee():
	cells = [[1] * 5 for _ in range(5)]
	cells[2][2] = 0
	assert gi.lisser_majorite(cells)[2][2] == 1


def test_le_lissage_ne_mure_pas_une_ruelle_de_deux_cases():
	"""⚠️ La raison du seuil à 5 et pas à 4. Chaque case d'un couloir de deux cases de large a
	exactement 4 voisines hors couloir sur ses flancs : à 4, la ruelle se referme. Une ruelle
	murée par le lissage est une régression parfaitement silencieuse — elle ne se voit qu'en
	jeu, en butant dessus."""
	cells = [[0] * 6 for _ in range(6)]
	for y in range(6):
		cells[y][2] = cells[y][3] = 1
	lisse = gi.lisser_majorite(cells)
	assert [lisse[y][2] for y in range(6)] == [1] * 6
	assert [lisse[y][3] for y in range(6)] == [1] * 6


def test_le_lissage_ne_mute_pas_la_grille_recue():
	cells = [[1] * 5 for _ in range(5)]
	cells[2][2] = 0
	gi.lisser_majorite(cells, passes=3)
	assert cells[2][2] == 0


# ── 5. La connexité, sur demande seulement ───────────────────────────────────────────────
def test_la_composante_principale_efface_l_ilot_detache():
	cells = [[0] * 7 for _ in range(7)]
	for y in (0, 1):
		for x in (0, 1, 2):
			cells[y][x] = 1
	cells[5][5] = 1                      # îlot d'une seule case, sans contact
	nettoye = gi.garder_composante_principale(cells)
	assert nettoye[0][0] == 1 and nettoye[1][2] == 1
	assert nettoye[5][5] == gi.TERRAIN_INACCESSIBLE


def test_la_composante_principale_relie_en_DIAGONALE():
	"""Connexité à 8, la même que celle des déplacements (`nav.VALID_MOVES`) : deux cases qui
	ne se touchent que par un coin communiquent bel et bien en jeu."""
	cells = [[0] * 4 for _ in range(4)]
	cells[0][0] = cells[1][1] = cells[2][2] = 1
	assert gi.garder_composante_principale(cells)[2][2] == 1


def test_l_eau_compte_comme_praticable_pour_la_connexite():
	"""Le seuil est `>= 1`, celui de `_caseAccessible` (le voile rouge de l'éditeur) : une
	rivière franchissable relie ses deux rives, elle ne les sépare pas."""
	cells = [[0] * 5 for _ in range(5)]
	for y in range(5):
		cells[y][2] = gi.TERRAIN_EAU
	cells[2][1] = cells[2][3] = 1
	nettoye = gi.garder_composante_principale(cells)
	assert nettoye[2][1] == 1 and nettoye[2][3] == 1


# ── 6. La notation ───────────────────────────────────────────────────────────────────────
def test_deux_grilles_identiques_donnent_un_rappel_parfait():
	cells = [[0, 1, 5], [1, 1, 0]]
	rapport = gi.concordance(cells, cells)
	assert rapport["global"] == 1.0
	assert all(m["rappel"] == 1.0 and m["precision"] == 1.0
		for m in rapport["par_valeur"].values())
	assert rapport["ecarts"] == []


def test_un_classifieur_tout_libre_est_denonce_par_le_rappel_pas_par_le_global():
	"""⚠️ LE test qui interdit de se féliciter d'un taux global. Sur une carte à 65 % de cases
	libres — la proportion réelle d'Auxerre — répondre « libre » partout affiche 65 % de
	réussite sans rien savoir faire. Seul le rappel par valeur le dit."""
	reference = [[1] * 13 + [0] * 5 + [5] * 2 for _ in range(10)]
	tout_libre = [[1] * 20 for _ in range(10)]
	rapport = gi.concordance(tout_libre, reference)
	assert rapport["global"] == 0.65
	assert rapport["par_valeur"][1]["rappel"] == 1.0
	assert rapport["par_valeur"][0]["rappel"] == 0.0
	assert rapport["par_valeur"][5]["rappel"] == 0.0


def test_la_concordance_distingue_rappel_et_precision():
	"""Sur-déclarer une valeur ne coûte rien au rappel mais écroule la précision — c'est ce
	couple qui dit à l'auteur combien de retouches l'attendent."""
	reference = [[0, 1, 1, 1]]
	proposee = [[0, 0, 0, 1]]
	m = gi.concordance(proposee, reference)["par_valeur"]
	assert m[0]["rappel"] == 1.0
	assert m[0]["precision"] == 1 / 3


# ── Robustesse ───────────────────────────────────────────────────────────────────────────
def test_une_image_unie_ne_fait_pas_lever_otsu():
	"""Aucune coupure n'a de sens sur une série constante ; l'outil doit rendre une grille,
	pas une exception."""
	cells = gi.grille_depuis_echantillons([CHAMP] * 9, [42] * 9, 3, 3)
	assert len(cells) == 3 and all(len(ligne) == 3 for ligne in cells)


def test_une_couleur_rgba_est_acceptee():
	"""Les cartes du dépôt sont toutes en RGBA ; l'alpha ne dit rien du terrain."""
	assert gi.rougeur((140, 118, 92, 255)) == gi.rougeur((140, 118, 92))


def test_les_grilles_vides_ne_font_rien_lever():
	assert gi.lisser_majorite([]) == []
	assert gi.garder_composante_principale([]) == []
	assert gi.comptes([]) == {}
	assert gi.concordance([], [])["global"] == 0.0


# ═════════════════════════════════════════════════════════════════════════════════════════
# Profils, nav et topologie (passages, coins, enceinte)
# ═════════════════════════════════════════════════════════════════════════════════════════
import copy  # noqa: E402

L, B, E = gi.TERRAIN_LIBRE, gi.TERRAIN_INACCESSIBLE, gi.TERRAIN_EAU


def _regles(profil="ville", **surcharges):
	regles = copy.deepcopy(gi.PROFILS_GRILLE[profil])
	regles.update(surcharges)
	return regles


def _grille(texte):
	"""'.' libre, '#' bâti, '~' eau, '^' falaise — une ligne par rangée."""
	table = {".": L, "#": B, "~": E, "^": gi.TERRAIN_FALAISE}
	return [[table[c] for c in ligne] for ligne in texte.strip().split("\n")]


def _nb_zones(cells, nav):
	return len(gi.zones(cells, nav)[1])


# ── Profils ──────────────────────────────────────────────────────────────────────────────
def test_trois_profils_et_un_repli_sur_la_ville():
	assert set(gi.PROFILS_GRILLE) == {"ville", "foret", "catacombes"}
	assert gi.regles_de("inconnu") is gi.PROFILS_GRILLE[gi.PROFIL_DEFAUT]
	assert gi.REGLES_GRILLE is gi.PROFILS_GRILLE["ville"]


def test_le_profil_se_lit_sur_les_tags_souterrain_avant_foret():
	assert gi.profil_de({"categorie": "ville", "tags": []}) == "ville"
	assert gi.profil_de({"tags": ["chemin", "foret", "bois"]}) == "foret"
	assert gi.profil_de({"tags": ["sous-terrain", "catacombe", "donjon"]}) == "catacombes"
	assert gi.profil_de({"tags": ["mine", "cristaux"]}) == "catacombes"
	# ⚠️ Un tag de souterrain l'emporte sur la forêt qui l'entoure.
	assert gi.profil_de({"tags": ["foret", "sous-terrain"]}) == "catacombes"
	assert gi.profil_de(None) == gi.PROFIL_DEFAUT


def test_chaque_profil_ne_produit_que_son_vocabulaire():
	"""La valeur « froide » est l'eau en surface, la falaise sous terre (cristaux)."""
	permis = {
		"ville": {B, L, E},
		"foret": {B, L, gi.TERRAIN_FALAISE, E},
		"catacombes": {B, L, gi.TERRAIN_FALAISE},
	}
	couleurs, contours = _echantillons(_scene(8, foret=True, place=True))
	for profil, valeurs in permis.items():
		cells = gi.grille_depuis_echantillons(couleurs, contours, 8, 8, profil=profil)
		assert set(gi.comptes(cells)) <= valeurs, profil
	assert gi.PROFILS_GRILLE["catacombes"]["valeur_froide"] == gi.TERRAIN_FALAISE


def test_la_luminance_seule_separe_sol_et_paroi_des_catacombes():
	"""Sous terre, la paroi est SOMBRE (le vide noir, la roche) et le sol éclairé. Teintes
	médianes mesurées sur `catacombes0001` sous les cases peintes 1 et 0."""
	sol, paroi = (64, 56, 50), (32, 31, 29)
	cases = [[(paroi if x in (0, 1, 6, 7) else sol, 30) for x in range(8)] for _ in range(6)]
	cells = gi.grille_depuis_echantillons(*_echantillons(cases), 8, 6, profil="catacombes")
	assert cells[3][0] == B and cells[3][4] == L


# ── nav ──────────────────────────────────────────────────────────────────────────────────
def test_la_recopie_de_valid_moves_suit_utils_lieux():
	"""Recopie assumée (importer `utils.lieux` tirerait FastAPI) : verrouillée ici."""
	from utils import lieux
	assert gi.VALID_MOVES == lieux.VALID_MOVES
	nav = {"2,2": 1 | 8, "2,1": 16, "3,3": 128, "1,2": 4}
	for x in range(1, 4):
		for y in range(1, 4):
			masque = lieux.get_final_mask(nav, x, y)
			for bit, dx, dy, _op in gi.VALID_MOVES:
				assert gi.nav_autorise(nav, x, y, dx, dy) == bool(masque & bit)


def test_interdire_pose_le_bit_des_deux_cotes_et_ne_retire_rien():
	nav = {"1,1": 64}
	assert gi.interdire(nav, 1, 1, 1, 0) == 2
	assert nav == {"1,1": 64 | 4, "2,1": 64}
	assert gi.interdire(nav, 1, 1, 1, 0) == 0
	assert not gi.nav_autorise(nav, 2, 1, -1, 0)


# ── Coins ────────────────────────────────────────────────────────────────────────────────
def test_la_diagonale_qui_rase_l_angle_d_une_maison_est_fermee():
	cells = _grille("""
...
.#.
...
""")
	nav = {}
	gi.fermer_coins(cells, nav)
	assert not gi.nav_autorise(nav, 1, 0, 1, 1)       # (1,0)→(2,1) : angle (1,1)
	assert not gi.nav_autorise(nav, 2, 1, -1, 1)      # (2,1)→(1,2) : angle (1,1)
	assert gi.nav_autorise(nav, 0, 0, 1, 0)           # l'orthogonale reste ouverte
	assert gi.pas_praticable(cells, nav, 0, 0, 1, 0)


def test_les_coins_gardent_le_nav_existant_et_ne_posent_que_des_diagonales():
	cells = _grille("""
....
.#..
....
""")
	nav = {"3,0": 16}
	gi.fermer_coins(cells, nav)
	assert nav["3,0"] & 16
	orthogonaux = 1 | 4 | 16 | 64
	assert all((v & orthogonaux) == 0 for k, v in nav.items() if k != "3,0")


def test_deux_cases_d_eau_ferment_la_diagonale_mais_une_berge_non():
	cells = _grille("""
.~
~.
""")
	nav = {}
	gi.fermer_coins(cells, nav)
	assert not gi.nav_autorise(nav, 0, 0, 1, 1)
	cells = _grille("""
.~
..
""")
	nav = {}
	gi.fermer_coins(cells, nav)
	assert gi.nav_autorise(nav, 0, 0, 1, 1)


# ── Passages ─────────────────────────────────────────────────────────────────────────────
def test_une_riviere_se_franchit_par_un_pont_orthogonal_au_plus_pres_de_l_image():
	"""Deux rives, un seul pont : il passe par la case d'eau de MOINDRE marge (l'arche de
	pierre dessinée sur l'eau), jamais en diagonale."""
	cells = _grille("""
...~~...
...~~...
...~~...
...~~...
...~~...
""")
	marges = [[0.0] * 8 for _ in range(5)]
	for y in range(5):
		marges[y][3] = marges[y][4] = 5.0
	marges[3][3] = marges[3][4] = 0.1          # le pont dessiné
	sortie, nav, rapport = gi.relier_zones(cells, {}, marges, regles=_regles())
	assert _nb_zones(sortie, nav) == 1
	assert len(rapport["passages"]) == 1
	passage = rapport["passages"][0]
	assert passage["cases"] == [[3, 3], [4, 3]]
	assert passage["traverse"] == ["eau"]
	assert sortie[3][3] == sortie[3][4] == L


def test_deux_quartiers_sont_relies_par_la_rangee_de_toits_la_moins_marquee():
	cells = _grille("""
..#..
..#..
..#..
""")
	marges = [[0.0] * 5 for _ in range(3)]
	marges[0][2], marges[1][2], marges[2][2] = 3.0, 0.2, 3.0
	sortie, _, rapport = gi.relier_zones(cells, {}, marges, regles=_regles())
	assert rapport["passages"][0]["cases"] == [[2, 1]]
	assert rapport["passages"][0]["traverse"] == ["bati"]


def test_le_bati_se_perce_avant_l_eau_a_longueur_egale():
	"""`cout_creuser` : une rue manquée par la grille est plus probable qu'un pont."""
	regles = _regles()
	assert regles["cout_creuser"][B] < regles["cout_creuser"][E]
	# Deux quartiers séparés par une colonne faite de toits et d'une case d'eau : un seul
	# passage d'une case suffit, et c'est un toit qui cède.
	cells = _grille("""
..~..
..#..
..#..
""")
	sortie, nav, rapport = gi.relier_zones(cells, {}, None, regles=_regles(poche_min=0))
	assert _nb_zones(sortie, nav) == 1
	assert [p["traverse"] for p in rapport["passages"]] == [["bati"]]


def test_un_passage_trop_long_n_est_pas_creuse_et_la_zone_est_signalee():
	cells = _grille("""
........
########
########
########
........
""")
	regles = _regles(passage_longueur_max=2, poche_isolee_max=0)
	sortie, nav, rapport = gi.relier_zones(cells, {}, None, regles=regles)
	assert rapport["passages"] == []
	assert len(rapport["zones_isolees"]) == 1
	assert rapport["zones_isolees"][0]["taille"] == 8
	assert sortie == cells


def test_une_petite_zone_injoignable_est_effacee_plutot_que_laissee_isolee():
	cells = _grille("""
......
######
######
######
...###
""")
	regles = _regles(passage_longueur_max=2, poche_isolee_max=3)
	sortie, nav, rapport = gi.relier_zones(cells, {}, None, regles=regles)
	assert sortie[4][:3] == [B, B, B]
	assert rapport["zones_isolees"] == []
	assert rapport["poches_effacees"] == 3


def test_une_poche_minuscule_est_effacee_avant_tout():
	cells = _grille("""
.....
.....
###.#
#####
.####
""")
	sortie, _, rapport = gi.relier_zones(cells, {}, None, regles=_regles(poche_min=2))
	assert sortie[4][0] == B
	assert rapport["passages"] == []


def test_un_mur_nav_peint_a_la_main_n_est_jamais_perce():
	"""Un mur nav de l'auteur est une intention : le passage le contourne ou renonce."""
	cells = _grille("""
..#..
..#..
""")
	nav = {"1,0": 4, "1,1": 4}          # interdit de sortir vers la droite depuis x = 1
	sortie, nav_sortie, rapport = gi.relier_zones(cells, nav, None,
		regles=_regles(poche_isolee_max=0))
	assert rapport["passages"] == []
	assert nav_sortie["1,0"] & 4 and nav_sortie["1,1"] & 4


def test_relier_ne_mute_rien_et_est_idempotent_et_deterministe():
	cells = _grille("""
...~~...
...~~...
..#~~#..
""")
	nav = {"0,0": 2}
	copie_cells, copie_nav = copy.deepcopy(cells), dict(nav)
	a = gi.relier_zones(cells, nav, None, regles=_regles())
	b = gi.relier_zones(cells, nav, None, regles=_regles())
	assert cells == copie_cells and nav == copie_nav
	assert a == b
	c = gi.relier_zones(a[0], a[1], None, regles=_regles())
	assert c[0] == a[0] and c[1] == a[1] and c[2]["passages"] == []


# ── Enceinte ─────────────────────────────────────────────────────────────────────────────
def _ville_fortifiee(porte=True):
	"""Une ville de 7×7 au centre d'une carte 13×11 : un anneau de bâti, une porte dessinée
	(une case libre dans l'anneau) si `porte`, des rues intérieures, une cour."""
	lignes = [
		".............",
		".............",
		"...#######...",
		"...#.....#...",
		"...#.###.#...",
		"...#.#.#.#...",
		"...#.###.#...",
		"...#.....#...",
		"...###.###...",
		".............",
		".............",
	]
	if not porte:
		lignes[8] = "...#######..."
	return _grille("\n".join(lignes))


def test_l_enceinte_est_la_masse_batie_comblee():
	cells = _ville_fortifiee()
	masque = gi.detecter_enceinte(cells, _regles(enceinte_rayon=1, enceinte_part_min=0.1))
	assert masque and masque[5][6] and masque[3][4]      # la cour et une rue sont dedans
	assert not masque[0][0] and not masque[10][12]


def test_une_petite_masse_n_est_pas_une_enceinte():
	cells = _ville_fortifiee()
	assert gi.detecter_enceinte(cells, _regles(enceinte_rayon=1, enceinte_part_min=0.9)) == []


def test_la_porte_dessinee_est_fermee_par_nav_et_jamais_creusee():
	"""L'auteur posera ses portes de rempart : dedans et dehors restent deux zones, la case de
	porte reste LIBRE (désignable), aucun passage ne traverse le mur."""
	cells = _ville_fortifiee()
	masque = gi.detecter_enceinte(cells, _regles(enceinte_rayon=1, enceinte_part_min=0.1))
	nav = {}
	gi.fermer_enceinte(cells, nav, masque)
	cotes = gi.cotes_de(masque)
	sortie, nav, rapport = gi.relier_zones(cells, nav, None, cotes,
		regles=_regles(poche_min=0, poche_isolee_max=0))
	zone, _ = gi.zones(sortie, nav)
	assert sortie[8][6] == L
	assert zone[9][6] != zone[7][6]
	for passage in rapport["passages"]:
		assert len({cotes[y][x] for x, y in passage["cases"]}) == 1


def test_la_cour_interieure_est_reliee_aux_rues_et_pas_au_dehors():
	cells = _ville_fortifiee()
	masque = gi.detecter_enceinte(cells, _regles(enceinte_rayon=1, enceinte_part_min=0.1))
	nav = {}
	gi.fermer_enceinte(cells, nav, masque)
	sortie, nav, rapport = gi.relier_zones(cells, nav, None, gi.cotes_de(masque),
		regles=_regles(poche_min=0))
	zone, _ = gi.zones(sortie, nav)
	assert zone[5][6] == zone[3][4]                  # cour ↔ rues
	assert zone[5][6] != zone[0][0]                  # jamais le dehors
	assert len(rapport["passages"]) == 1


def test_une_ville_au_bord_coupe_le_dehors_en_plusieurs_cotes():
	"""Lutèce touche le bord : ses rives nord et sud ne se rejoignent que par les portes."""
	masque = [[x in (2, 3) for x in range(6)] for _ in range(3)]
	cotes = gi.cotes_de(masque)
	assert cotes[1][2] == cotes[1][3] == 0
	assert cotes[1][0] != cotes[1][5] and 0 not in (cotes[1][0], cotes[1][5])


def test_une_case_creusee_contre_le_rempart_ne_l_ouvre_pas():
	"""Le scellement ne couvre que les paires foulables : une case CREUSÉE contre le mur doit
	être rescellée, sinon elle ouvre une brèche vers l'autre côté."""
	cells = _grille("""
.#.
.#.
.#.
""")
	cotes = [[1, 1, 0], [1, 1, 0], [1, 1, 0]]
	nav = {}
	sortie, nav, _ = gi.relier_zones(cells, nav, None, cotes, regles=_regles(poche_min=0))
	# À gauche, la case bâtie (1, y) est du même côté que la colonne 0 : on peut la creuser,
	# mais jamais passer à la colonne 2.
	zone, _ = gi.zones(sortie, nav)
	assert all(zone[y][0] != zone[y][2] for y in range(3))


# ── Point d'entrée ───────────────────────────────────────────────────────────────────────
def test_proposer_sans_passages_rend_l_ancien_comportement():
	couleurs, contours = _echantillons(_scene(8))
	res = gi.proposer(couleurs, contours, 8, 8, nav={"1,1": 2}, passages=False)
	attendu = gi.lisser_majorite(gi.grille_depuis_echantillons(couleurs, contours, 8, 8))
	assert res["cells"] == attendu
	assert res["nav"] == {"1,1": 2}
	assert res["profil"] == "ville"


def test_proposer_garde_le_nav_existant_et_rend_une_zone():
	"""`enceinte=False` : sur 8×8, le bloc bâti de la scène couvre assez de carte pour passer
	pour une ville fortifiée — ce n'est pas ce qu'on teste ici."""
	couleurs, contours = _echantillons(_scene(8, foret=True))
	res = gi.proposer(couleurs, contours, 8, 8, nav={"7,7": 1}, enceinte=False)
	assert res["nav"]["7,7"] & 1
	assert res["rapport"]["zones"] == 1
	assert not res["rapport"]["enceinte"]
	assert res["rapport"]["nav_ajoutes"] == gi._bits(res["nav"]) - 1


# ── Notation ─────────────────────────────────────────────────────────────────────────────
def test_le_f1_moyen_resume_rappel_et_precision_par_valeur():
	reference = [[0, 1, 1, 1]]
	proposee = [[0, 0, 0, 1]]
	rapport = gi.concordance(proposee, reference)
	f1_zero = 2 * 1.0 * (1 / 3) / (1.0 + 1 / 3)
	f1_un = 2 * (1 / 3) * 1.0 / (1 / 3 + 1.0)
	assert abs(rapport["f1_moyen"] - (f1_zero + f1_un) / 2) < 1e-9


def test_un_mur_nav_retrouve_a_une_case_pres_compte():
	rapport = gi.concordance_nav({"3,3": 4}, {"2,3": 1, "9,9": 2})
	assert rapport == {"peintes": 2, "proposees": 1, "retrouvees": 1, "rappel": 0.5}

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
def test_quatre_profils_et_un_repli_sur_la_ville():
	assert set(gi.PROFILS_GRILLE) == {"ville", "foret", "catacombes", "pays"}
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
	# Un PAYS se reconnaît à sa catégorie (`lieu:france` n'a aucun tag).
	assert gi.profil_de({"categorie": gi.CATEGORIE_PAYS, "tags": []}) == "pays"


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


# ── Rues ─────────────────────────────────────────────────────────────────────────────────
TOIT = (120, 70, 50)       # terracotta sombre et vif
PAVE = (200, 190, 170)     # pavé clair et terne


def _fins(cols, rows, k, claires):
	"""Échantillons fins à plat : toit partout, PAVÉ sur les sous-cases de `claires`
	(ensemble de (sx, sy) en coordonnées de sous-case)."""
	return [PAVE if (sx, sy) in claires else TOIT
		for sy in range(rows * k) for sx in range(cols * k)]


def _quartier(cols=10, rows=7):
	"""Bloc bâti, bordé d'une colonne libre à gauche et à droite (la ville autour)."""
	return [[L if x in (0, cols - 1) else B for x in range(cols)] for _ in range(rows)]


def test_une_rue_plus_fine_que_la_case_est_ouverte():
	"""Une ligne de sous-cases claires traverse le bloc : la rangée devient praticable, le
	reste du bloc reste bâti."""
	k = gi.SOUS_CASES
	cells = _quartier()
	rue = {(sx, 3 * k + 1) for sx in range(k, 9 * k)}
	sortie, ouvertes = gi.tracer_rues(cells, _fins(10, 7, k, rue), k, _regles())
	assert [sortie[3][x] for x in range(10)] == [L] * 10
	assert all(sortie[y][x] == B for y in (1, 5) for x in range(1, 9))
	assert ouvertes == [[x, 3] for x in range(1, 9)]
	assert cells[3][4] == B                       # la source n'est pas mutée


def test_une_cour_claire_isolee_n_est_pas_une_rue():
	"""Une seule case claire au cœur du bloc, sans case libre autour : moins de
	`longueur_min` cases, rien n'est ouvert."""
	k = gi.SOUS_CASES
	assert gi.PROFILS_GRILLE["ville"]["rues"]["longueur_min"] > 1
	cells = _quartier()
	cour = {(5 * k + 1, 3 * k + 1)}
	sortie, ouvertes = gi.tracer_rues(cells, _fins(10, 7, k, cour), k, _regles())
	assert ouvertes == [] and sortie == cells


def test_le_cadre_clair_d_une_carte_sur_parchemin_n_est_pas_une_rue():
	"""Reims : une bande claire le long du bord de la carte, collée à une case libre."""
	k = gi.SOUS_CASES
	cells = _quartier()
	cadre = {(sx, 1) for sx in range(10 * k)}
	sortie, ouvertes = gi.tracer_rues(cells, _fins(10, 7, k, cadre), k, _regles())
	assert ouvertes == []


def test_sans_reglage_de_rues_ou_sans_echantillons_fins_rien_ne_change():
	k = gi.SOUS_CASES
	cells = _quartier()
	rue = {(sx, 3 * k + 1) for sx in range(k, 9 * k)}
	for profil in ("foret", "catacombes"):
		assert gi.PROFILS_GRILLE[profil]["rues"] is None
		assert gi.tracer_rues(cells, _fins(10, 7, k, rue), k, _regles(profil))[1] == []
	assert gi.tracer_rues(cells, None, k, _regles())[1] == []
	couleurs, contours = _echantillons(_scene(8))
	sans = gi.proposer(couleurs, contours, 8, 8, enceinte=False)
	avec_off = gi.proposer(couleurs, contours, 8, 8, enceinte=False,
		fins=_fins(8, 8, k, set()), rues=False)
	assert sans["cells"] == avec_off["cells"] and avec_off["rapport"]["rues"] == []


def _masque(texte):
	"""'#' plein, '.' vide — une ligne par rangée."""
	return [[c == "#" for c in ligne] for ligne in texte.strip().split("\n")]


def test_le_squelette_d_une_bande_epaisse_est_une_ligne_d_un_pixel_d_un_seul_tenant():
	bande = _masque("""
..............
.############.
.############.
.############.
..............
""")
	sq = gi.squelettiser(bande)
	pleins = [(x, y) for y, l in enumerate(sq) for x, v in enumerate(l) if v]
	assert pleins and {y for _, y in pleins} == {2}          # une seule rangée : la médiane
	assert len(gi._composantes(sq)) == 1
	assert all(bande[y][x] for x, y in pleins)               # jamais hors de la tache
	assert bande[2][1] and sum(bande[2]) == 12                # la source n'est pas mutée


def test_le_squelette_garde_la_connexite_d_un_carrefour():
	croix = _masque("""
.....###.....
.....###.....
.....###.....
#############
#############
#############
.....###.....
.....###.....
.....###.....
""")
	sq = gi.squelettiser(croix)
	assert len(gi._composantes(sq)) == 1
	# Quatre bras : Zhang-Suen rogne chaque bout d'environ la demi-largeur de la tache.
	assert any(sq[y][6] for y in (0, 1, 2)) and any(sq[y][6] for y in (6, 7, 8))
	assert any(sq[4][x] for x in (0, 1, 2)) and any(sq[4][x] for x in (10, 11, 12))


def test_l_ebarbage_coupe_une_epine_courte_et_garde_les_vraies_branches():
	# Une rue horizontale, une épine de 2 px vers le haut, une branche de 6 px vers le bas.
	sq = _masque("""
......#..........
......#..........
#################
.........#.......
.........#.......
.........#.......
.........#.......
.........#.......
.........#.......
""")
	sortie = gi.ebarber(sq, 4)
	assert not sortie[0][6] and not sortie[1][6]
	assert all(sortie[y][9] for y in range(3, 9))
	assert all(sortie[2])                                     # la rue elle-même, entière
	assert sq[0][6]                                          # la source n'est pas mutée
	# Une ligne sans carrefour n'a pas d'épine : gardée entière, le filtre de groupe tranche.
	seule = _masque("""
.......
.#####.
.......
""")
	assert gi.ebarber(seule, 10) == seule


def test_une_rue_diagonale_ouvre_des_cases_4_connexes():
	"""Un pas diagonal de case à case ne tiendrait que par un coin, que `fermer_coins` ferme
	entre deux toits : l'orthogonale intermédiaire est ouverte avec."""
	k = gi.SOUS_CASES
	cells = _quartier(12, 12)
	rue = set()
	for s in range(k, 11 * k):
		rue |= {(s, s), (s + 1, s), (s, s + 1)}            # bande diagonale de 2-3 px
	sortie, ouvertes = gi.tracer_rues(cells, _fins(12, 12, k, rue), k, _regles())
	assert ouvertes
	zone, _ = gi.zones(sortie, {})
	assert zone[1][0] == zone[10][11] != -1
	ouv = {tuple(c) for c in ouvertes}
	for x, y in ouv:
		assert any((x + dx, y + dy) in ouv or sortie[y + dy][x + dx] == L
			for dx, dy in gi.ORTHOGONAUX if gi._dans(sortie, x + dx, y + dy))
	nav = {}
	gi.fermer_coins(sortie, nav)
	zone, _ = gi.zones(sortie, nav)
	assert zone[1][0] == zone[10][11]


def test_une_rue_coudee_sort_continue_sans_case_isolee():
	"""Le défaut de l'ancienne lecture case par case : des cases éparses le long d'une rue.
	Le squelette la suit d'un bout à l'autre, coude compris."""
	k = gi.SOUS_CASES
	cells = _quartier(14, 10)
	# Depuis la colonne libre de gauche, rangée 2, jusqu'à la colonne 9, puis vers le bas.
	rue = {(sx, 2 * k + d) for sx in range(k, 9 * k + 2) for d in (1, 2)}
	rue |= {(9 * k + d, sy) for sy in range(2 * k, 9 * k) for d in (1, 2)}
	sortie, ouvertes = gi.tracer_rues(cells, _fins(14, 10, k, rue), k, _regles())
	assert all([x, 2] in ouvertes for x in range(1, 9))
	assert all([9, y] in ouvertes for y in range(3, 8))
	# Un seul tenant 4-connexe, rattaché à la colonne libre de gauche.
	ouv = {tuple(c) for c in ouvertes}
	groupes = gi._composantes([[(x, y) in ouv for x in range(14)] for y in range(10)],
		gi.ORTHOGONAUX)
	assert len(groupes) == 1 and (1, 2) in groupes[0]


# ── Murs nav optionnels ──────────────────────────────────────────────────────────────────
def test_sans_murs_nav_le_nav_rendu_est_celui_recu():
	couleurs, contours = _echantillons(_scene(8, foret=True))
	res = gi.proposer(couleurs, contours, 8, 8, nav={"7,7": 1}, murs_nav=False)
	assert res["nav"] == {"7,7": 1}
	assert res["rapport"]["nav_ajoutes"] == 0 and res["rapport"]["coins"] == 0
	assert res["rapport"]["murs_nav"] is False


def test_sans_murs_nav_l_enceinte_est_fermee_par_le_terrain():
	"""Choix de l'auteur : la porte dessinée passe à 0 (il la rouvre au pinceau), dedans et
	dehors restent deux zones, et aucun passage ne rouvre le pourtour."""
	cells = _ville_fortifiee()
	masque = gi.detecter_enceinte(cells, _regles(enceinte_rayon=1, enceinte_part_min=0.1))
	fermees = gi.fermer_enceinte_terrain(cells, masque)
	assert fermees == [[6, 8]] and cells[8][6] == B   # la case de porte, dans le mur
	cotes = gi.cotes_de(masque)
	sortie, nav, rapport = gi.relier_zones(cells, {}, None, cotes,
		regles=_regles(poche_min=0, poche_isolee_max=0), murs_nav=False)
	assert nav == {}
	zone, _ = gi.zones(sortie, nav)
	assert zone[5][6] != -1 and zone[0][0] != -1
	assert zone[5][6] != zone[0][0]
	for passage in rapport["passages"]:
		for x, y in passage["cases"]:
			assert not any(gi._dans(sortie, x + dx, y + dy) and sortie[y + dy][x + dx] == L
				and cotes[y + dy][x + dx] != cotes[y][x] for dx, dy in gi.VOISINS)


# ── Cadre de carte et rues hors les murs ─────────────────────────────────────────────────
def _encadree():
	"""La ville fortifiée, dans un cadre bâti d'une case tout autour (Reims)."""
	cells = _ville_fortifiee()
	H, W = len(cells), len(cells[0])
	for y in range(H):
		for x in range(W):
			if x in (0, W - 1) or y in (0, H - 1):
				cells[y][x] = B
	return cells


def test_un_cadre_de_parchemin_ne_fait_pas_de_la_carte_une_enceinte():
	"""Reims : le cadre bâti se soudait à la ville, toute la carte devenait intra-muros et
	ses villages n'avaient plus de dehors."""
	cells = _encadree()
	regles = _regles(enceinte_rayon=1, enceinte_part_min=0.1)
	cadre = gi.masque_cadre(cells, regles)
	assert cadre and cadre[0][0] and not cadre[5][6]
	masque = gi.detecter_enceinte(cells, regles)
	assert masque and masque[5][6] and not masque[1][1] and not masque[0][0]


def test_un_anneau_exterieur_surtout_libre_n_est_pas_un_cadre():
	assert gi.masque_cadre(_ville_fortifiee(), _regles()) == []


def _cite_et_village(cols=20, rows=10):
	"""À gauche la cité (toits terracotta, rue de pavé clair rangée 3) ; à droite un village
	plus sombre (toits bruns, chemin de terre rangée 6, plus terne que le pavé de la cité)."""
	k = gi.SOUS_CASES
	cite = lambda sx: sx < (cols // 2) * k
	# Choisies pour que le chemin du village soit à peine plus clair que les TOITS de la
	# cité : au seuil commun il se confond avec eux.
	toit_village, terre = (70, 50, 40), (95, 85, 75)
	fins = []
	for sy in range(rows * k):
		for sx in range(cols * k):
			if cite(sx):
				fins.append(PAVE if sy == 3 * k + 1 else TOIT)
			else:
				fins.append(terre if sy == 6 * k + 1 else toit_village)
	cells = [[L if x in (0, cols - 1) else B for x in range(cols)] for _ in range(rows)]
	masque = [[x < cols // 2 for x in range(cols)] for _ in range(rows)]
	return cells, fins, masque


def test_le_chemin_d_un_village_hors_les_murs_a_son_propre_seuil():
	"""Au seuil commun, la lumière de la cité écrase le chemin de terre du village ; réglé à
	part hors les murs, il est ouvert."""
	k = gi.SOUS_CASES
	cells, fins, masque = _cite_et_village()
	regles = _regles()
	dehors = sum(1 for y, l in enumerate(cells) for x, v in enumerate(l) if v == B and not masque[y][x])
	assert dehors >= regles["rues"]["cases_min"]
	_, commun = gi.tracer_rues(cells, fins, k, regles)
	_, par_cote = gi.tracer_rues(cells, fins, k, regles, masque)
	village = [[x, 6] for x in range(10, 19)]
	assert not any(c in commun for c in village)
	assert all(c in par_cote for c in village)
	assert all([x, 3] in par_cote for x in range(1, 10))          # la cité garde ses rues


def test_un_cote_trop_petit_emprunte_le_seuil_commun():
	k = gi.SOUS_CASES
	cells, fins, masque = _cite_et_village()
	regles = _regles()
	regles["rues"] = dict(regles["rues"], cases_min=10 ** 6, decalage_dehors=regles["rues"]["decalage"])
	assert gi.tracer_rues(cells, fins, k, regles, masque) == gi.tracer_rues(cells, fins, k, regles)


# ── Profil pays : murs nav seuls ─────────────────────────────────────────────────────────
# Teintes mesurées sur `france.png` : la terre du parchemin, la mer, l'eau d'un fleuve (froide
# ET sombre, plus fine qu'une case).
TERRE = (216, 202, 155)
MER = (40, 90, 110)
FLEUVE = (60, 70, 68)
# Sous-cases des échantillons fins des tests : de quoi dessiner un fleuve plus fin qu'une case.
K_PAYS = 4


def _carte(texte):
	"""'.' terre, '~' mer, '|' fleuve — une ligne par rangée. Rend (couleurs, fins, cols,
	rows) : la couleur MOYENNE de chaque case (le fleuve, plus fin qu'une case, n'y paraît
	pas) et ses `K_PAYS²` pixels (le fleuve y est plein)."""
	lignes = texte.strip().split("\n")
	rows, cols, k = len(lignes), len(lignes[0]), K_PAYS
	couleurs = [MER if c == "~" else TERRE for ligne in lignes for c in ligne]
	fins = [None] * (cols * k * rows * k)
	for y, ligne in enumerate(lignes):
		for x, c in enumerate(ligne):
			couleur = {"~": MER, "|": FLEUVE}.get(c, TERRE)
			for j in range(k):
				for i in range(k):
					fins[(y * k + j) * cols * k + x * k + i] = couleur
	return couleurs, fins, cols, rows


def _pays(texte, nav=None, **options):
	couleurs, fins, cols, rows = _carte(texte)
	return gi.proposer(couleurs, [0] * len(couleurs), cols, rows, nav=nav, profil="pays",
		fins=fins, k=K_PAYS, **options)


# Mer en haut et en bas, un fleuve qui les relie.
FLEUVE_TRAVERSANT = """
~~~~~~~~~~~~
~~~~~~~~~~~~
......|.....
......|.....
......|.....
......|.....
~~~~~~~~~~~~
~~~~~~~~~~~~
"""


def test_profil_pays_cells_toutes_libres():
	"""Seuls les nav bloquent : la mer, le fleuve, tout reste à 1 (forme de `lieu:france`)."""
	cells = _pays(FLEUVE_TRAVERSANT)["cells"]
	assert gi.comptes(cells) == {L: 12 * 8}


def test_la_cote_est_muree_dans_les_deux_sens():
	prop = _pays(FLEUVE_TRAVERSANT)
	nav = prop["nav"]
	for x in range(12):
		for dx in (-1, 0, 1):
			if 0 <= x + dx < 12:
				assert not gi.nav_autorise(nav, x, 2, dx, -1)   # terre → mer
				assert not gi.nav_autorise(nav, x + dx, 1, -dx, 1)   # mer → terre
	assert prop["rapport"]["cote"] and all(y in (2, 5) for _, y in prop["rapport"]["cote"])


def test_un_fleuve_n_est_pas_mure_seule_la_cote_l_est():
	"""Choix de l'auteur : le profil pays ne mure QUE le bord de mer. Le fleuve, même bien
	visible au pixel, se traverse : la terre reste d'un seul tenant, aucun gué à poser."""
	prop = _pays(FLEUVE_TRAVERSANT)
	rapport, nav = prop["rapport"], prop["nav"]
	assert "fleuves" not in rapport and rapport["passages"] == []
	assert rapport["zones_isolees"] == [] and rapport["zones"] == 1
	for y in (3, 4):                                  # rangées sans voisine de mer
		for x in range(12):
			assert int(nav.get(f"{x},{y}", 0)) == 0
	assert gi.nav_autorise(nav, 5, 3, 1, 0) and gi.nav_autorise(nav, 6, 3, 1, 0)


def test_un_bras_de_mer_en_diagonale_ne_s_enjambe_pas_par_son_coin():
	"""Deux cases de mer en diagonale : le pas diagonal entre les deux cases de terre qui
	les flanquent passerait au-dessus de l'eau."""
	mer = [[False] * 3 for _ in range(3)]
	mer[0][0] = mer[1][1] = True
	nav = {}
	gi.murer_barrieres(nav, mer, lambda x, y: not mer[y][x])
	assert not gi.nav_autorise(nav, 1, 0, -1, 1)    # (1,0) → (0,1)
	assert gi.nav_autorise(nav, 2, 0, 0, 1)         # loin de la mer, rien


def test_le_nav_d_origine_n_est_jamais_retire():
	"""Un mur peint à la main est une intention d'auteur, même là où l'image n'en voit pas."""
	nav = {"6,4": 4, "0,3": 4}
	sortie = _pays(FLEUVE_TRAVERSANT, nav=nav)["nav"]
	assert sortie["6,4"] & 4 and sortie["0,3"] & 4
	assert nav == {"6,4": 4, "0,3": 4}   # l'entrée n'est pas mutée


def test_sans_murs_nav_le_nav_rendu_est_celui_recu_profil_pays():
	nav = {"0,3": 4}
	assert _pays(FLEUVE_TRAVERSANT, nav=nav, murs_nav=False)["nav"] == nav


def test_une_ile_reste_isolee_et_un_navire_redevient_mer():
	"""On ne trace jamais de chemin sur la mer : l'île est SIGNALÉE. Une terre plus petite que
	`ile_min` cernée d'eau est un navire dessiné : rendue à la mer, sans mur autour."""
	ile_min = gi.PROFILS_GRILLE["pays"]["ile_min"]
	assert ile_min > 1
	carte = """
............
............
~~~~~~~~~~~~
~~~...~~~~~~
~~~...~~~.~~
~~~...~~~~~~
~~~~~~~~~~~~
~~~~~~~~~~~~
"""
	rapport = _pays(carte)["rapport"]
	assert [z["taille"] for z in rapport["zones_isolees"]] == [9]
	assert [9, 4] not in rapport["cote"]


def test_le_cadre_du_parchemin_ne_relie_pas_les_cotes():
	"""Une bande de terre d'une case le long du bord, mer derrière : c'est le cadre, pas une
	côte — sur la France, il reliait la Corse au continent en faisant le tour de la carte."""
	# Un continent (x 1-4) et une île (x 8-10), reliés seulement par la bande du bord (rangée 0
	# et colonne 11).
	carte = """
............
~....~~~~~~.
~....~~~~~~.
~....~~~....
~....~~~....
~....~~~....
~~~~~~~~~~~.
~~~~~~~~~~~.
"""
	prop = _pays(carte)
	zone, _ = gi.zones(prop["cells"], prop["nav"])
	assert zone[3][2] != zone[4][9]
	# Sans la règle du cadre, les deux terres n'en feraient qu'une.
	sans_cadre = _regles("pays", cadre_profondeur=0)
	couleurs, fins, cols, rows = _carte(carte)
	prop = gi.proposer(couleurs, [0] * len(couleurs), cols, rows, regles=sans_cadre,
		profil="pays", fins=fins, k=K_PAYS)
	zone, _ = gi.zones(prop["cells"], prop["nav"])
	assert zone[3][2] == zone[4][9]


# ── Cadre décoratif d'une carte de pays → cases à 0 ─────────────────────────────────────
REGLES_PAYS = gi.PROFILS_GRILLE["pays"]
PX = 16.0   # pixels par case des profils de test (les cartes de `maps/` à 88×48)


def _profil(traits=(), longueur=None, fond=30):
	"""Profil de contours d'un côté : `fond` partout, un trait FORT aux lignes `traits`. Le bord
	de l'image (ligne 0) est toujours contrasté — il ne doit jamais compter."""
	longueur = longueur or int((REGLES_PAYS["cadre_max_cases"] + 1) * PX)
	fort = REGLES_PAYS["cadre_trait_min"] + 50
	profil = [float(fond)] * longueur
	profil[0] = 250.0
	for d in traits:
		profil[d] = float(fort)
	return profil


def test_epaisseur_le_trait_le_plus_profond_arrondi_a_la_case():
	assert gi.epaisseur_cadre(_profil([10, 47]), [0.0], PX, REGLES_PAYS) == 3    # 48 px → 3
	assert gi.epaisseur_cadre(_profil([18]), [0.0], PX, REGLES_PAYS) == 1        # 19 px → 1


def test_epaisseur_sans_trait_ni_blanc_le_bord_seul_ne_fait_pas_de_cadre():
	assert gi.epaisseur_cadre(_profil(), [0.0], PX, REGLES_PAYS) == 0


def test_epaisseur_un_trait_au_dela_du_maximum_est_de_la_carte():
	"""Une côte rectiligne ou un cartouche plus loin que `cadre_max_cases` : pas un cadre."""
	loin = int(REGLES_PAYS["cadre_max_cases"] * PX) + 2
	assert gi.epaisseur_cadre(_profil([loin]), [0.0], PX, REGLES_PAYS) == 0


def test_epaisseur_seuil_relatif_a_la_mediane():
	"""Un côté chargé (montagnes jusqu'au bord) : un « trait » à peine au-dessus du fond n'en est
	pas un — le seuil suit `cadre_trait_facteur` × la médiane du profil."""
	fond = REGLES_PAYS["cadre_trait_min"]   # médiane assez haute pour que le facteur l'emporte
	profil = _profil(fond=fond)
	profil[20] = fond * REGLES_PAYS["cadre_trait_facteur"] - 1
	assert gi.epaisseur_cadre(profil, [0.0], PX, REGLES_PAYS) == 0


def test_epaisseur_un_bord_blanc_vaut_une_case():
	"""Le papier blanc déchiqueté de la France : pas de trait, mais il jure avec le parchemin."""
	part = REGLES_PAYS["cadre_blanc_part"]
	assert gi.epaisseur_cadre(_profil(), [part, 0.1], PX, REGLES_PAYS) == 1
	assert gi.epaisseur_cadre(_profil(), [part - 0.01], PX, REGLES_PAYS) == 0


def test_masque_bordure_par_cote():
	m = gi.masque_bordure(5, 4, {"haut": 1, "gauche": 2})
	assert [[int(v) for v in ligne] for ligne in m] == [
		[1, 1, 1, 1, 1],
		[1, 1, 0, 0, 0],
		[1, 1, 0, 0, 0],
		[1, 1, 0, 0, 0],
	]


def _bords(**cases):
	"""Profils de bord dont chaque côté a un trait à `cases[cote]` cases (absent = aucun)."""
	return {c: {"contours": _profil([int(cases[c] * PX) - 1] if cases.get(c) else []),
		"blanc": [0.0], "px_case": PX} for c in gi.COTES_CADRE}


def test_pays_le_cadre_passe_a_0_le_reste_a_1():
	couleurs, fins, cols, rows = _carte(FLEUVE_TRAVERSANT)
	prop = gi.proposer(couleurs, [0] * len(couleurs), cols, rows, profil="pays", fins=fins,
		k=K_PAYS, bords=_bords(gauche=2, haut=1))
	cells = prop["cells"]
	for y in range(rows):
		for x in range(cols):
			assert cells[y][x] == (B if (x < 2 or y < 1) else L)
	assert prop["rapport"]["cadre"] == {"haut": 1, "bas": 0, "gauche": 2, "droite": 0}
	assert prop["rapport"]["cadre_cases"] == sum(1 for l in cells for v in l if v == B)


def test_pays_aucun_mur_vers_le_cadre_et_pas_de_cote_dedans():
	"""Le cadre bloque par le terrain : la terre qui le borde n'est pas une côte, aucun mur."""
	couleurs, fins, cols, rows = _carte(FLEUVE_TRAVERSANT)
	prop = gi.proposer(couleurs, [0] * len(couleurs), cols, rows, profil="pays", fins=fins,
		k=K_PAYS, bords=_bords(gauche=2))
	nav = prop["nav"]
	for y in (3, 4):                     # rangées loin de la mer, au contact du cadre
		assert gi.nav_autorise(nav, 2, y, -1, 0)
		assert int(nav.get(f"2,{y}", 0)) == 0
	assert all(x >= 2 for x, _ in prop["rapport"]["cote"])


def test_pays_sans_bords_rien_ne_change():
	"""Sans profils de bord (CLI d'avant, image illisible) : la proposition d'avant, `cells` à 1."""
	assert gi.comptes(_pays(FLEUVE_TRAVERSANT)["cells"]) == {L: 12 * 8}
	assert _pays(FLEUVE_TRAVERSANT)["rapport"]["cadre_cases"] == 0


def test_pays_sans_murs_nav_le_cadre_passe_quand_meme_a_0():
	couleurs, fins, cols, rows = _carte(FLEUVE_TRAVERSANT)
	prop = gi.proposer(couleurs, [0] * len(couleurs), cols, rows, profil="pays", fins=fins,
		k=K_PAYS, bords=_bords(droite=1), murs_nav=False)
	assert all(ligne[-1] == B for ligne in prop["cells"]) and prop["nav"] == {}


def test_sous_cases_du_profil():
	# Aucun profil n'en déclare aujourd'hui : repli sur `SOUS_CASES`, lu par les rues.
	for profil, regles in gi.PROFILS_GRILLE.items():
		assert gi.sous_cases_de(profil) == regles.get("sous_cases", gi.SOUS_CASES)
	assert gi.sous_cases_de("ville") == gi.SOUS_CASES


def test_le_catalogue_des_profils_suit_PROFILS_GRILLE_dans_son_ordre():
	# Source de la liste « Réglage » de l'éditeur : aucun profil recopié dans le template.
	cat = gi.catalogue_profils()
	assert list(cat) == list(gi.PROFILS_GRILLE)
	assert all(cat[k] == v.get("libelle", k) for k, v in gi.PROFILS_GRILLE.items())

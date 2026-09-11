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


def _scene():
	"""Une scène minimale : une colonne d'eau, un bloc bâti dense, le reste en campagne.

	Les valeurs de contours sont choisies de part et d'autre de la coupure qu'Otsu trouvera.
	"""
	cases = []
	for y in range(6):
		ligne = []
		for x in range(6):
			if x == 0:
				ligne.append((EAU, 10))
			elif 2 <= x <= 4 and 1 <= y <= 4:
				ligne.append((BATI, 200))
			else:
				ligne.append((CHAMP, 20))
		cases.append(ligne)
	return cases


# ── 1. La règle qui porte l'outil ────────────────────────────────────────────────────────
def test_a_couleur_egale_la_densite_de_traits_separe_le_bati_du_champ():
	"""L'invariant central : un pâté de maisons et un champ ont la même teinte beige, seule
	la densité de traits (toits, murs, ombres) les distingue. Si ce test tombe, l'outil ne
	sait plus rien faire d'autre que poser l'eau."""
	couleurs, contours = _echantillons(_scene())
	repere = gi.calibrer(couleurs, contours)
	assert gi.classer_case(BATI, 200, repere) == gi.TERRAIN_INACCESSIBLE
	assert gi.classer_case(BATI, 20, repere) == gi.TERRAIN_LIBRE


def test_la_foret_dense_reste_libre_malgre_ses_traits():
	"""⚠️ La raison du ET plutôt que du OU. La forêt qui entoure Auxerre est aussi dessinée
	qu'une ville ; c'est sa COULEUR qui la trahit. En OU, la précision sur le bâti tombait
	de 0,55 à 0,39 — la moitié de la campagne passait pour des maisons."""
	couleurs, contours = _echantillons(_scene())
	repere = gi.calibrer(couleurs, contours)
	assert gi.classer_case(CHAMP, 250, repere) == gi.TERRAIN_LIBRE


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

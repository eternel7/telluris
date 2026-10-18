"""`dev/gen_calais_remparts.py` — ce que le générateur garantit sans relire d'image.

1. **Le tracé du rempart est 4-connexe** : aucun pas diagonal ne le franchit.
2. **Une poche est reliée au réseau** par la case la moins chère, une **impasse** prolongée
   vers une case éloignée ; jamais à travers le rempart ni hors de l'enceinte.
3. **Une ouverture qui joindrait dedans et dehors est annulée.**
4. **Les cinq docs d'une porte** ont la forme de l'éditeur (`dev/test_portes_client.js`),
   ses deux portes de part et d'autre du châtelet (`PORTE_ECART_MAX`).
"""

from dev import gen_calais_remparts as g


def _cout_plat(x, y):
	return 1


def test_le_trace_est_4_connexe():
	cases = g.trace((0, 0), (5, 3))
	assert cases[0] == (0, 0) and cases[-1] == (5, 3)
	for a, b in zip(cases, cases[1:]):
		assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def test_le_rempart_ferme_separe_dedans_et_dehors():
	# Diagonale murée en travers d'un champ libre : sans l'orthogonale, on passerait en biais.
	cells = [[1] * 6 for _ in range(6)]
	murs = set(g.trace((0, 5), (5, 0)))
	assert g.fermer_rempart(cells, murs) == len(murs)
	assert not g.atteint(cells, {}, (0, 0)) & g.atteint(cells, {}, (5, 5))


def test_une_poche_est_reliee_par_la_case_la_moins_chere():
	# Rue (y = 0) et poche (y = 2, x = 0..2) séparées par une rangée murée ; la case (1, 1)
	# est claire (coût 1), les autres sombres.
	cells = [[1, 1, 1, 1], [0, 0, 0, 0], [1, 1, 1, 0]]
	enceinte = ((0, 0), (4, 0), (4, 3), (0, 3))
	cout = lambda x, y: 1 if (x, y) == (1, 1) else 5  # noqa: E731
	ouvertures = g.relier_rues(cells, {}, set(), enceinte, cout, dedans=(0, 0), dehors=(99, 99))
	assert ouvertures[0] == ("poche", [(1, 1)])
	assert (2, 2) in g.atteint(cells, {}, (0, 0))


def test_jamais_a_travers_le_rempart_ni_hors_enceinte():
	cells = [[1, 1, 1], [0, 0, 0], [1, 1, 1]]
	murs = {(0, 1), (1, 1), (2, 1)}
	assert g.relier_rues(cells, {}, murs, ((0, 0), (3, 0), (3, 3), (0, 3)), _cout_plat,
						 (0, 0), (99, 99)) == []
	# Hors de l'enceinte (y >= 1) : rien n'est ouvrable non plus.
	assert g.relier_rues(cells, {}, set(), ((0, 0), (3, 0), (3, 1), (0, 1)), _cout_plat,
						 (0, 0), (99, 99)) == []
	assert cells[1] == [0, 0, 0]


def test_une_ouverture_qui_joindrait_le_dehors_est_annulee():
	# La « poche » touche le dehors : la relier ouvrirait le rempart.
	cells = [[1, 1, 1], [0, 0, 0], [1, 1, 1]]
	enceinte = ((0, 0), (3, 0), (3, 3), (0, 3))
	g.relier_rues(cells, {}, set(), enceinte, _cout_plat, dedans=(0, 0), dehors=(2, 2))
	assert cells[1] == [0, 0, 0]


def test_une_impasse_est_prolongee_vers_une_case_eloignee():
	# Rue repliée en U : ses deux bouts (1, 1) et (1, 3), à 8 pas l'un de l'autre, ne sont
	# séparés que par la case murée (1, 2).
	cells = [
		[0, 0, 0, 0, 0, 0, 0],
		[0, 1, 1, 1, 1, 1, 0],
		[0, 0, 0, 0, 0, 1, 0],
		[0, 1, 1, 1, 1, 1, 0],
		[0, 0, 0, 0, 0, 0, 0],
	]
	enceinte = ((0, 0), (7, 0), (7, 5), (0, 5))
	ouvertures = g.relier_rues(cells, {}, set(), enceinte, _cout_plat, dedans=(1, 1),
							   dehors=(99, 99))
	assert ouvertures == [("impasse", [(1, 2)])]


def test_chaque_porte_est_sur_son_pont_levis():
	# La porte extérieure est la dernière case du pont, voisine (8) de la précédente : le pont
	# se parcourt d'un bout à l'autre.
	for p in g.PORTES:
		for a, b in zip(p["pont"], p["pont"][1:]):
			assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1, p["slug"]
	assert len({p["slug"] for p in g.PORTES}) == len(g.PORTES)


def test_les_deux_portes_d_une_paire_encadrent_le_chatelet():
	# Débouché lu sur l'image, jamais recalé « à la rue la plus proche » : la porte sud-ouest
	# était partie en (39, 28), une autre rue, loin du châtelet.
	for p in g.PORTES:
		assert g.ecart_porte(p) <= g.PORTE_ECART_MAX, p["slug"]
	assert g.ecart_porte({"pont": ((0, 0),), "dedans": (3, 10)}) == 10


def test_les_cinq_docs_d_une_porte():
	porte = dict(g.PORTES[0])
	docs = g.docs_porte("lieu:calais", porte, (35, 40), (37, 32))
	ext, inte, carte_ext, carte_int, passage = docs
	assert ext["_id"] == "lieu:calais_porte_sud_ouest_exterieur"
	assert inte["_id"] == "lieu:calais_porte_sud_ouest_interieur"
	assert {ext["categorie"], inte["categorie"]} == {g.PORTE_CATEGORIE}
	assert {ext["lieu_parent"], inte["lieu_parent"]} == {"lieu:calais"}
	for lien in (carte_ext, carte_int, passage):
		assert lien["metadata"] == g.PORTE_META
	assert carte_ext["nodes"][0] == {"lieu": "lieu:calais", "pos": [35, 40],
									 "label": g.PORTE_LABEL_EXT}
	assert carte_int["nodes"][0] == {"lieu": "lieu:calais", "pos": [37, 32]}
	assert [n["lieu"] for n in passage["nodes"]] == [ext["_id"], inte["_id"]]
	assert all(n["pos"] == [0, 0] and "label" not in n for n in passage["nodes"])

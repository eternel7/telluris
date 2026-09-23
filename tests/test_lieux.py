"""utils/lieux — images d'un lieu proposées par le formulaire de l'éditeur (`images_lieu` de
`GET /api/lieux/creation_options`, toutes les origines que le jeu sait servir, dans SON ordre)
et nœud de destination d'une connexion (`noeud_destination`, branche « lien » de
`move_character`), connexions INTERNES à une carte comprises."""

from utils import lieux, marche


def test_origines_image_lieu_recopient_la_resolution_du_jeu():
	"""`ORIGINES_IMAGE_LIEU` est une RECOPIE de `marche._IMAGE_ROUTES` : un ordre divergent
	ferait afficher par l'éditeur une autre image que celle servie au joueur."""
	assert lieux.ORIGINES_IMAGE_LIEU == marche._IMAGE_ROUTES


def test_images_de_lieu_couvre_toutes_les_origines_premier_dossier_gagnant(tmp_path, monkeypatch):
	dossiers = {}
	for route in ("towns", "maps", "battle_maps"):
		d = tmp_path / route
		d.mkdir()
		dossiers[route] = d
	(dossiers["towns"] / "forge01.png").write_bytes(b"")
	(dossiers["towns"] / "commun.png").write_bytes(b"")
	(dossiers["maps"] / "region.jpg").write_bytes(b"")
	(dossiers["battle_maps"] / "donjon_salle1.png").write_bytes(b"")
	(dossiers["battle_maps"] / "commun.png").write_bytes(b"")   # masqué par towns
	(dossiers["battle_maps"] / "notes.md").write_bytes(b"")     # pas une image
	monkeypatch.setattr(lieux, "ORIGINES_IMAGE_LIEU",
		tuple((route, str(dossiers[route])) for route, _ in lieux.ORIGINES_IMAGE_LIEU))

	assert lieux.images_de_lieu() == {
		"commun.png": "towns",
		"forge01.png": "towns",
		"region.jpg": "maps",
		"donjon_salle1.png": "battle_maps",
	}


# ── noeud_destination ─────────────────────────────────────────────────────────────

def _conn(*nodes):
	return {"_id": "link:x", "nodes": [{"lieu": l, "pos": p} for l, p in nodes]}


def test_connexion_ordinaire_mene_a_l_autre_lieu():
	conn = _conn(("lieu:auxerre", [4, 5]), ("lieu:forge", [0, 0]))
	node, interne = lieux.noeud_destination(conn, "lieu:auxerre", {"x": 4, "y": 5})
	assert node["lieu"] == "lieu:forge" and interne is False
	# Vu depuis l'autre côté : même règle, l'autre lieu.
	node, interne = lieux.noeud_destination(conn, "lieu:forge", {"x": 0, "y": 0})
	assert node["lieu"] == "lieu:auxerre" and interne is False


def test_connexion_interne_mene_a_l_autre_case_dans_les_deux_sens():
	conn = _conn(("lieu:tour", [2, 3]), ("lieu:tour", [9, 1]))
	node, interne = lieux.noeud_destination(conn, "lieu:tour", {"x": 2, "y": 3})
	assert node["pos"] == [9, 1] and interne is True
	node, interne = lieux.noeud_destination(conn, "lieu:tour", {"x": 9, "y": 1})
	assert node["pos"] == [2, 3] and interne is True


def test_connexion_interne_sur_une_seule_case_ne_mene_nulle_part():
	conn = _conn(("lieu:tour", [2, 3]), ("lieu:tour", [2, 3]))
	assert lieux.noeud_destination(conn, "lieu:tour", {"x": 2, "y": 3}) == (None, True)

# tests/test_livres_images.py
#
# Images des livres (Auteur, 22/11/2026) : une image à la racine de `resources/livres` = une
# planche achetable dans la famille du scriptorium, sans import ; un sous-dossier nommé comme un
# item = les illustrations de ce livre, relues à la lecture (`resolve_item_ref`).

import pytest

from utils import livres_images, marche, scriptorium


@pytest.fixture(autouse=True)
def _cache_vide():
	livres_images.reset_cache()
	yield
	livres_images.reset_cache()


def _deposer(dossier, *noms):
	dossier.mkdir(parents=True, exist_ok=True)
	for nom in noms:
		(dossier / nom).write_bytes(b"x")


# ── Planches ─────────────────────────────────────────────────────────────────────

def test_seules_les_images_de_la_racine_sont_des_planches(tmp_path):
	_deposer(tmp_path, "b_vue.png", "carte_de_la_Beauce.jpg", "LISEZMOI.md", ".cache.jpg")
	_deposer(tmp_path / "ouvrage_critias", "01.jpg")
	assert livres_images.planches(str(tmp_path)) == ["b_vue.png", "carte_de_la_Beauce.jpg"]


def test_dossier_absent_rend_rien(tmp_path):
	assert livres_images.planches(str(tmp_path / "absent")) == []


def test_nom_genre_et_id_viennent_du_fichier():
	f = "carte_de_la_Beauce.jpg"
	assert livres_images.nom_planche(f) == "Carte de la Beauce"
	assert livres_images.genre_planche(f) == "carte"
	assert livres_images.genre_planche("vue-de-Lutecia.png") == "oeuvre"
	assert livres_images.nom_planche("vue-de-Lutecia.png") == "Vue de Lutecia"
	assert livres_images.nom_planche("vision_d_Atlantis.jpg") == "Vision d'Atlantis"
	assert livres_images.nom_planche("le_puits_qu_on_tait.jpg") == "Le puits qu'on tait"
	assert livres_images.nom_planche("l_arche.jpg") == "L'arche"
	assert livres_images.item_id_planche("Église_é.jpg") == "item:planche_eglise_e"


def test_doc_planche():
	doc = livres_images.doc_planche("carte_de_la_Beauce.jpg")
	assert doc["categorie"] == "livre"
	assert doc["sous_categorie"] == livres_images.SOUS_CATEGORIE_PLANCHE
	assert doc["planche"] == {"fichier": "carte_de_la_Beauce.jpg", "genre": "carte"}
	assert doc["icon"] == "🗺️"
	assert not scriptorium.contenu_scelle(doc)        # une planche se voit en vitrine


# ── Illustrations d'un livre ─────────────────────────────────────────────────────

def test_images_d_un_livre_planche_puis_illustrations(tmp_path):
	_deposer(tmp_path, "carte_x.jpg")
	_deposer(tmp_path / "planche_carte_x", "02.jpg", "01.jpg")
	doc = {"_id": "item:planche_carte_x", "categorie": "livre", "planche": {"fichier": "carte_x.jpg"}}
	assert livres_images.images_de(doc, str(tmp_path)) == [
		{"url": "/livres/carte_x.jpg"},
		{"url": "/livres/planche_carte_x/01.jpg"},
		{"url": "/livres/planche_carte_x/02.jpg"},
	]


def test_image_reconvertie_garde_sa_planche(tmp_path):
	_deposer(tmp_path, "carte_x.webp")
	doc = {"_id": "item:planche_carte_x", "categorie": "livre", "planche": {"fichier": "carte_x.jpg"}}
	assert livres_images.images_de(doc, str(tmp_path)) == [{"url": "/livres/carte_x.webp"}]


def test_fichier_retire_l_image_disparait(tmp_path):
	doc = {"_id": "item:planche_y", "categorie": "livre", "planche": {"fichier": "y.jpg"}}
	assert livres_images.images_de(doc, str(tmp_path)) == []


def test_pas_d_images_hors_des_livres(tmp_path):
	_deposer(tmp_path / "Epee", "01.jpg")
	assert livres_images.images_de({"_id": "item:Epee", "categorie": "arme"}, str(tmp_path)) == []


def test_url_encodee():
	assert livres_images.url("ouvrage_x", "vue de Lutèce.jpg") == "/livres/ouvrage_x/vue%20de%20Lut%C3%A8ce.jpg"


@pytest.mark.parametrize("nom", ["..", "../etc", "a/b", "a\\b", "", "x y"])
def test_sous_dossier_non_admis(tmp_path, nom):
	assert livres_images.illustrations(nom, str(tmp_path)) == []


# ── Tirage dans la famille du scriptorium ────────────────────────────────────────

def test_recettes_planches_cree_le_doc_une_fois(tmp_path, monkeypatch):
	_deposer(tmp_path, "carte_de_la_Beauce.jpg", "vue.png")
	monkeypatch.setattr(scriptorium.random, "choice", lambda seq: seq[0])
	base, sauves = {}, []

	def save(doc):
		sauves.append(doc["_id"])
		base[doc["_id"]] = doc

	(r,) = scriptorium.recettes_planches(base.get, save, racine=str(tmp_path))
	assert r["objet_final"] == "planche_carte_de_la_beauce"
	assert r["max_par_passe"] == 1
	scriptorium.recettes_planches(base.get, save, racine=str(tmp_path))
	assert sauves == ["item:planche_carte_de_la_beauce"]      # jamais retouché ensuite


def test_aucune_image_aucune_recette(tmp_path):
	assert scriptorium.recettes_planches(lambda i: None, lambda d: None, racine=str(tmp_path)) == []


def test_famille_scriptorium():
	assert scriptorium.famille_scriptorium({"categorie": "scriptorium"})
	assert scriptorium.famille_scriptorium({"categorie": "grand_scriptorium"})
	assert scriptorium.famille_scriptorium({"categorie": "bibliotheque"})
	assert scriptorium.famille_scriptorium({"categorie": "grande_bibliotheque"})
	assert scriptorium.famille_scriptorium({"categorie": "boulangerie", "tags": ["scriptorium"]})
	assert not scriptorium.famille_scriptorium({"categorie": "boulangerie"})


def test_bibliotheque_tire_une_planche_sans_livres_de_contenu(monkeypatch):
	monkeypatch.setattr(marche, "recettes_lieu", lambda lieu: [])
	monkeypatch.setattr(scriptorium, "recettes_planches", lambda g, s, racine=None: [{"objet_final": "planche_z"}])
	monkeypatch.setattr(scriptorium, "recettes_virtuelles", lambda *a: pytest.fail("pas de livre de contenu"))
	r = scriptorium.recettes_effectives({"categorie": "bibliotheque", "lieu_parent": "lieu:c"}, None, None, None)
	assert r == [{"objet_final": "planche_z"}]


# ── Toujours une planche en rayon ────────────────────────────────────────────────

def _base():
	base = {}
	return base, base.get, lambda doc: base.__setitem__(doc["_id"], doc)


def test_garnir_pose_une_planche_si_aucune(tmp_path, monkeypatch):
	_deposer(tmp_path, "carte_x.jpg", "vue.png")
	monkeypatch.setattr(scriptorium.random, "choice", lambda seq: seq[-1])
	base, get, save = _base()
	lieu = {"categorie": "scriptorium", "stock_vente": [{"item_id": "item:Papier", "qty": 4}]}
	assert scriptorium.garnir_planche(lieu, get, save, racine=str(tmp_path)) is True
	assert lieu["stock_vente"][-1] == {"item_id": "item:planche_vue", "qty": 1}
	assert "item:planche_vue" in base                            # doc créé au premier tirage
	# Une planche déjà là : rien de plus.
	assert scriptorium.garnir_planche(lieu, get, save, racine=str(tmp_path)) is False
	assert len(lieu["stock_vente"]) == 2


def test_garnir_ignore_une_ligne_videe(tmp_path):
	_deposer(tmp_path, "vue.png")
	_base_, get, save = _base()
	lieu = {"categorie": "bibliotheque", "stock_vente": [{"item_id": "item:planche_vue", "qty": 0}]}
	assert scriptorium.garnir_planche(lieu, get, save, racine=str(tmp_path)) is True


def test_garnir_hors_famille_ou_sans_image(tmp_path):
	_base_, get, save = _base()
	assert scriptorium.garnir_planche({"categorie": "boulangerie"}, get, save, racine=str(tmp_path)) is False
	lieu = {"categorie": "scriptorium"}
	assert scriptorium.garnir_planche(lieu, get, save, racine=str(tmp_path / "vide")) is False
	assert "stock_vente" not in lieu


def test_tick_garnit_la_boutique_mais_pas_le_marchand_d_une_propriete(monkeypatch):
	poses = []
	monkeypatch.setattr(scriptorium, "garnir_planche", lambda lieu, g, s: poses.append(lieu) or True)
	monkeypatch.setattr(marche, "tenter_production", lambda lieu, r: [])
	monkeypatch.setattr(marche, "ecouler_produits_pnj", lambda lieu: [])
	lieu = {"categorie": "scriptorium", "stock_vente": [], "stock_matieres": {}}
	change, _ = marche.tick_detaille(lieu, [], None)
	assert change is True and poses == [lieu]               # la pose suffit à faire sauver le lieu
	marche.tick_detaille(lieu, [], None, appro=False, ecouler=lambda l: [])
	assert poses == [lieu]                                  # appro=False : jamais


def test_hors_famille_comportement_d_avant(monkeypatch):
	monkeypatch.setattr(marche, "recettes_lieu", lambda lieu: ["base"])
	monkeypatch.setattr(scriptorium, "recettes_planches", lambda *a, **k: pytest.fail("pas de planche"))
	assert scriptorium.recettes_effectives({"categorie": "boulangerie"}, None, None, None) == ["base"]

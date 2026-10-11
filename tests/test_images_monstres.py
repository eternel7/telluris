"""Variantes d'image d'un monstre en combat (utils/images_monstres)."""
from utils.images_monstres import choisir_image, jetons_armes, variantes

ARC = {"_id": "item:Arc_long", "categorie": "arme", "sous_categorie": "arc", "tags": ["tir"]}
PIQUE = {"_id": "item:Pique", "categorie": "arme", "sous_categorie": "", "tags": ["hast"]}


def _candidats():
	vus = []
	def choix(liste):
		vus.append(list(liste))
		return liste[0]
	return vus, choix


def test_variante_evidente_choisie_avec_l_arme():
	fichiers = ["centaure_transparent.png", "centaure_transparent_arc.png"]
	assert choisir_image("centaure_transparent.png", fichiers, [ARC]) == "centaure_transparent_arc.png"


def test_sans_l_arme_tirage_parmi_les_generiques_a_poids_egaux():
	fichiers = ["loup_transparent.png", "loup_transparent01.png", "loup_transparent_arc.png"]
	vus, choix = _candidats()
	choisir_image("loup_transparent.png", fichiers, [PIQUE], choix_fn=choix)
	assert vus == [["loup_transparent.png", "loup_transparent01.png"]]


def test_plusieurs_evidentes_tirees_a_egalite():
	fichiers = ["x_transparent.png", "x_transparent_arc.png", "x_transparent_arc01.png"]
	vus, choix = _candidats()
	choisir_image("x_transparent.png", fichiers, [ARC], choix_fn=choix)
	assert vus == [["x_transparent_arc.png", "x_transparent_arc01.png"]]


def test_variante_a_mot_inconnu_jamais_tiree():
	fichiers = ["loup_geant_transparent.png", "loup_geant_transparent_monture.png"]
	assert choisir_image("loup_geant_transparent.png", fichiers, [ARC]) == "loup_geant_transparent.png"


def test_pas_de_capture_d_une_autre_espece_au_meme_prefixe():
	fichiers = ["loup_transparent.png", "loup_geant_transparent.png"]
	assert [f for f, _ in variantes("loup_transparent.png", fichiers)] == ["loup_transparent.png"]


def test_base_lue_sur_une_image_numerotee():
	fichiers = ["renard_transparent01.png", "renard_transparent02.png"]
	vus, choix = _candidats()
	choisir_image("renard_transparent01.png", fichiers, [], choix_fn=choix)
	assert vus == [fichiers]


def test_image_hors_convention_ou_sans_fichier_inchangee():
	assert choisir_image("dragon.png", ["dragon_transparent01.png"], []) == "dragon.png"
	assert choisir_image("loup_transparent.png", [], []) == "loup_transparent.png"
	assert choisir_image("", [], []) == ""


def test_jetons_d_arme_tires_de_l_id_des_tags_et_de_la_sous_categorie():
	assert {"arc", "long", "tir"} <= jetons_armes([ARC])
	assert {"hache", "guerre"} <= jetons_armes([{"_id": "item:Hache_de_guerre"}])
	assert jetons_armes([None, {}]) == set()

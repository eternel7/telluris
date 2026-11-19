# tests/test_images_lieu.py — image d'un lieu tirée au sort parmi ses variantes (utils/images_lieu.py).

from utils import images_lieu

PRESENTS = {"a01.jpg", "a02.jpg", "a03.jpg"}
existe = PRESENTS.__contains__
LIEU = {"_id": "lieu:a", "image": "a01.jpg", "images": ["a01.jpg", "a02.jpg"]}


def _dernier(liste):
	return liste[-1]


def test_sans_liste_rien_ne_change():
	perso = {}
	assert not images_lieu.poser_image_tiree(perso, {"_id": "lieu:b", "image": "b.jpg"}, existe, True)
	assert perso == {}
	assert images_lieu.image_effective(perso, {"_id": "lieu:b", "image": "b.jpg"}, existe) == "b.jpg"


def test_tirage_a_l_entree_stable_au_rafraichissement():
	perso = {}
	assert images_lieu.poser_image_tiree(perso, LIEU, existe, True, _dernier)
	assert images_lieu.image_effective(perso, LIEU, existe) == "a02.jpg"
	# Rafraîchissement : pas de nouvelle entrée, le tirage reste.
	assert not images_lieu.poser_image_tiree(perso, LIEU, existe, False, lambda l: l[0])
	assert images_lieu.image_effective(perso, LIEU, existe) == "a02.jpg"
	# Nouvelle entrée : retiré.
	assert images_lieu.poser_image_tiree(perso, LIEU, existe, True, lambda l: l[0])
	assert images_lieu.image_effective(perso, LIEU, existe) == "a01.jpg"


def test_fichier_manquant_ecarte_et_tirage_d_un_autre_lieu_ignore():
	lieu = dict(LIEU, images=["a01.jpg", "absent.jpg", "a03.jpg", "a03.jpg"])
	assert images_lieu.variantes(lieu, existe) == ["a01.jpg", "a03.jpg"]
	perso = {"image_tiree": {"lieu": "lieu:autre", "image": "a03.jpg"}}
	assert images_lieu.image_effective(perso, lieu, existe) == "a01.jpg"
	# Tirage gardé devenu invalide (fichier retiré de la liste) ⇒ retiré même sans entrée.
	perso = {"image_tiree": {"lieu": "lieu:a", "image": "absent.jpg"}}
	assert images_lieu.poser_image_tiree(perso, lieu, existe, False, _dernier)
	assert perso["image_tiree"]["image"] == "a03.jpg"


def test_une_seule_variante_servable_vaut_l_image_du_lieu():
	perso = {"image_tiree": {"lieu": "lieu:a", "image": "a02.jpg"}}
	lieu = dict(LIEU, images=["a01.jpg", "absent.jpg"])
	assert images_lieu.poser_image_tiree(perso, lieu, existe, True)
	assert "image_tiree" not in perso
	assert images_lieu.image_effective(perso, lieu, existe) == "a01.jpg"

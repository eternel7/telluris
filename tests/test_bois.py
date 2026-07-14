# tests/test_bois.py
#
# Tests purs de la découpe du bois. Ici : `a_outil_coupe` et le partage d'outil en
# exploration — il suffit qu'UN membre du groupe porte l'outil de coupe (compétences /
# équipements partagés par l'expédition).

from utils import bois
from models import character_stats


TAG = character_stats.OUTIL_COUPE_BOIS_TAG  # "outil_coupe_bois"

_DB = {
    "item:hache":    {"_id": "item:hache", "nom": "Hache", "tags": [TAG]},
    "item:cailloux": {"_id": "item:cailloux", "nom": "Cailloux", "tags": []},
}


def _get_doc(item_id):
    return _DB.get(item_id)


def test_outil_dans_le_sac_du_personnage():
    perso = {"inventaire": ["item:hache"], "slots": {}}
    assert bois.a_outil_coupe(perso, _get_doc) is True


def test_outil_equipe_par_le_personnage():
    perso = {"inventaire": [], "slots": {"main": "item:hache"}}
    assert bois.a_outil_coupe(perso, _get_doc) is True


def test_aucun_outil_nulle_part():
    perso = {"inventaire": ["item:cailloux"], "slots": {}}
    assert bois.a_outil_coupe(perso, _get_doc) is False


def test_outil_seulement_chez_un_compagnon_sac():
    perso = {"inventaire": ["item:cailloux"], "slots": {}}
    compagnon = {"inventaire": ["item:hache"], "slots": {}}
    assert bois.a_outil_coupe(perso, _get_doc, [compagnon]) is True


def test_outil_seulement_chez_un_compagnon_equipe():
    perso = {"inventaire": [], "slots": {}}
    compagnon = {"inventaire": [], "slots": {"main": "item:hache"}}
    assert bois.a_outil_coupe(perso, _get_doc, [compagnon]) is True


def test_compagnons_non_transmis_ignore_leur_outil():
    # Rétro-compat : sans l'argument compagnons, seul le personnage est scanné.
    perso = {"inventaire": [], "slots": {}}
    compagnon = {"inventaire": ["item:hache"], "slots": {}}
    assert bois.a_outil_coupe(perso, _get_doc) is False
    assert bois.a_outil_coupe(perso, _get_doc, []) is False
    assert bois.a_outil_coupe(perso, _get_doc, [compagnon]) is True


def test_reference_objet_dict_dans_le_sac():
    # Une réf d'inventaire peut être un objet {item, poids} (pas seulement une string).
    perso = {"inventaire": [{"item": "item:hache", "poids": 3}], "slots": {}}
    assert bois.a_outil_coupe(perso, _get_doc) is True

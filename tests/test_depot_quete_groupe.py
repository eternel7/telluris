# tests/test_depot_quete_groupe.py
# Objets de quête portés par le GROUPE : les pièces d'une collecte (dépôt à la guilde) sont
# prises dans le sac du principal PUIS dans ceux de ses porteurs (compagnons, montures),
# comme à la vente chez un marchand. Le principal se vide en premier (Convention §7).

from utils import chasse, quetes

CARCASSE = "item:carcasse_de_loup"


def _q(quantite, progress=0):
	return {"id": "quete:x", "objectif": {"type": "collect", "cible": CARCASSE, "quantite": quantite},
			"progress": progress}


def _sac(_id, n, autre=0):
	return {"_id": _id, "inventaire": [CARCASSE] * n + ["item:pain"] * autre}


def test_depot_puise_dans_les_sacs_du_groupe_principal_en_tete():
	c, bob, mule = _sac("character:c", 1, autre=1), _sac("aventurier:bob", 2), _sac("monture:mule", 3)
	q = _q(4)
	n, touches = quetes.deposer_collect(c, q, [bob, mule])
	assert n == 4 and q["progress"] == 4
	assert c["inventaire"] == ["item:pain"], "le principal se vide d'abord, le reste lui reste"
	assert bob["inventaire"] == [] and mule["inventaire"] == [CARCASSE] * 2
	assert touches == [bob, mule]


def test_depot_sans_porteur_ne_touche_que_le_principal():
	c = _sac("character:c", 2)
	n, touches = quetes.deposer_collect(c, _q(5))
	assert (n, touches) == (2, []) and c["inventaire"] == []


def test_seul_un_compagnon_porte_la_piece():
	c, bob = _sac("character:c", 0), _sac("aventurier:bob", 1)
	n, touches = quetes.deposer_collect(c, _q(1), [bob])
	assert (n, touches) == (1, [bob]) and bob["inventaire"] == []


def test_objectif_deja_atteint_ne_retire_rien():
	bob = _sac("aventurier:bob", 2)
	assert quetes.deposer_collect({}, _q(2, progress=2), [bob]) == (0, [])
	assert len(bob["inventaire"]) == 2


def test_apport_de_rang_trouve_l_objet_sur_un_compagnon():
	spec = {"items": [CARCASSE]}
	sacs = [_sac("character:c", 0), _sac("aventurier:antoine", 1)]
	assert chasse.sac_avec_apport(sacs, spec) == 1
	assert chasse.retirer_objet_apport(sacs[1], spec) == CARCASSE
	assert sacs[1]["inventaire"] == []

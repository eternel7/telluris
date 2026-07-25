"""Capacités mises en commun par l'expédition (utils/expedition.py) — logique pure.

Trois questions distinctes : QUI compose l'expédition (`membres` — surtout pas les
montures), QUI porte l'outil (`porteur_avec_tag`, sac ET équipement), et QUI parle au
marchand (`meilleur_negociateur`, au Cha BUFFÉ, sous condition de confiance).
`recrutement.groupe_effectif` relit les docs en base → on monkeypatche le `get_doc` du
module recrutement, comme le fait tests/test_recrutement.py.
"""

import pytest

from models import character_stats
from utils import expedition
from utils import recrutement


TAG = "outil_coupe_bois"

HACHE = {"_id": "item:hache", "type": "item", "nom": "Hache", "tags": [TAG]}
CAILLOU = {"_id": "item:caillou", "type": "item", "nom": "Caillou", "tags": []}

_ITEMS = {d["_id"]: d for d in (HACHE, CAILLOU)}


def _get_item(item_id):
	return _ITEMS.get(item_id)


def _compagnon(av_id, **extra):
	av = {"_id": av_id, "type": "aventurier", "statut": "embauche",
		  "embauche_par": "character:joueur", "inventaire": [], "slots": {}}
	av.update(extra)
	return av


def _monture(m_id, **extra):
	m = {"_id": m_id, "type": "monture", "statut": "acquise",
		 "acquise_par": "character:joueur", "inventaire": [], "slots": {}}
	m.update(extra)
	return m


def _joueur(**extra):
	perso = {"_id": "character:joueur", "inventaire": [], "slots": {},
			 "caracteristiques_current": {"Cha": 50}}
	perso.update(extra)
	return perso


@pytest.fixture
def db(monkeypatch):
	"""Base minimale : `groupe_effectif` / `montures_effectives` lisent par id."""
	docs = {}

	def get_doc(doc_id):
		return docs.get(doc_id)

	monkeypatch.setattr(recrutement, "get_doc", get_doc)
	monkeypatch.setattr(recrutement.montures, "get_doc", get_doc)
	return docs


# ── membres : l'expédition, ce sont des PERSONNES ────────────────────────────────

def test_membres_principal_en_tete_puis_compagnons(db):
	av = _compagnon("aventurier:1")
	db[av["_id"]] = av
	perso = _joueur(groupe=[av["_id"]])
	assert expedition.membres(perso) == [perso, av]


def test_membres_exclut_les_montures(db):
	"""Une monture porte, mais elle ne négocie pas et ne manie pas une hache."""
	av = _compagnon("aventurier:1")
	mon = _monture("monture:1")
	db.update({av["_id"]: av, mon["_id"]: mon})
	perso = _joueur(groupe=[av["_id"]], montures=[mon["_id"]])
	assert expedition.membres(perso) == [perso, av]
	# … alors que « qui porte pour moi ? » répond autre chose.
	assert mon in recrutement.porteurs_effectifs(perso)


def test_membres_exclut_un_compagnon_parti(db):
	av = _compagnon("aventurier:1", statut="parti")
	db[av["_id"]] = av
	perso = _joueur(groupe=[av["_id"]])
	assert expedition.membres(perso) == [perso]


# ── porteur_avec_tag : sac ET équipement, chez n'importe quel membre ─────────────

def test_tag_dans_le_sac_du_principal():
	perso = _joueur(inventaire=["item:hache"])
	assert expedition.porteur_avec_tag(_get_item, [perso], TAG) is True


def test_tag_equipe_par_un_compagnon_seul():
	perso = _joueur(inventaire=["item:caillou"])
	av = _compagnon("aventurier:1", slots={"main_droite": "item:hache"})
	assert expedition.porteur_avec_tag(_get_item, [perso, av], TAG) is True


def test_tag_absent_partout():
	perso = _joueur(inventaire=["item:caillou"])
	av = _compagnon("aventurier:1", inventaire=["item:caillou"])
	assert expedition.porteur_avec_tag(_get_item, [perso, av], TAG) is False


def test_tag_reference_objet_avec_poids_d_instance():
	"""Une entrée d'inventaire peut être un objet {item, poids} — item_ref_id tranche."""
	perso = _joueur(inventaire=[{"item": "item:hache", "poids": 3.0}])
	assert expedition.porteur_avec_tag(_get_item, [perso], TAG) is True


# ── meilleur_negociateur : le Cha BUFFÉ, sous condition de confiance ─────────────

def test_negociateur_compagnon_au_cha_buffe_bat_le_principal():
	"""30 de Cha + une passive +25 battent un principal à 50 : c'est tout l'objet du
	correctif — le Cha brut aurait laissé parler le joueur."""
	perso = _joueur()
	av = _compagnon("aventurier:1", caracteristiques_current={"Cha": 30},
					competences_bonus={"nom": "Aura sympathique", "buffs": {"Cha": 25}})
	perso["affinites"] = {av["_id"]: 80}
	doc, cha, est_compagnon = expedition.meilleur_negociateur(perso, [av], seuil_min=50)
	assert (doc, cha, est_compagnon) == (av, 55, True)


def test_negociateur_compagnon_sous_seuil_de_confiance_ignore():
	perso = _joueur()
	av = _compagnon("aventurier:1", caracteristiques_current={"Cha": 90})
	perso["affinites"] = {av["_id"]: 20}
	doc, cha, est_compagnon = expedition.meilleur_negociateur(perso, [av], seuil_min=50)
	assert (doc, cha, est_compagnon) == (perso, 50, False)


def test_negociateur_egalite_le_principal_garde_la_parole():
	perso = _joueur()
	av = _compagnon("aventurier:1", caracteristiques_current={"Cha": 50})
	perso["affinites"] = {av["_id"]: 100}
	doc, _cha, est_compagnon = expedition.meilleur_negociateur(perso, [av], seuil_min=50)
	assert (doc, est_compagnon) == (perso, False)


def test_negociateur_seuil_zero_rend_tous_les_compagnons_eligibles():
	"""⚠️ 0 = « tous les compagnons », PAS « principal seul » : le principal n'a pas
	d'affinité envers lui-même, le seuil ne filtre que les autres."""
	perso = _joueur()
	av = _compagnon("aventurier:1", caracteristiques_current={"Cha": 60})
	perso["affinites"] = {av["_id"]: 0}
	doc, cha, est_compagnon = expedition.meilleur_negociateur(perso, [av], seuil_min=0)
	assert (doc, cha, est_compagnon) == (av, 60, True)


def test_negociateur_affinite_inconnue_vaut_le_neutre():
	"""Un compagnon jamais noté part au neutre (AFFINITE_INITIALE = 50) : au seuil par
	défaut, il a droit à la parole."""
	perso = _joueur()
	av = _compagnon("aventurier:1", caracteristiques_current={"Cha": 70})
	doc, _cha, est_compagnon = expedition.meilleur_negociateur(perso, [av])
	assert (doc, est_compagnon) == (av, True)


def test_negociateur_sans_compagnon_rend_le_principal():
	perso = _joueur()
	assert expedition.meilleur_negociateur(perso, []) == (perso, 50, False)


def test_negociateur_retient_les_trois_sources_de_buffs():
	"""Équipement + passive + effet à durée : les 3 origines de `_sources_de_buffs`."""
	perso = _joueur()
	av = _compagnon(
		"aventurier:1", caracteristiques_current={"Cha": 20},
		equipment_bonus={"nom": "Broche", "buffs": {"Cha": 10}},
		competences_bonus={"nom": "Aura", "buffs": {"Cha": 5}},
		effets_actifs=[{"nom": "Philtre", "item_id": "item:philtre",
						"buffs": {"Cha": 30}, "restants": 3}],
	)
	perso["affinites"] = {av["_id"]: 100}
	_doc, cha, _est = expedition.meilleur_negociateur(perso, [av], seuil_min=50)
	assert cha == 65


def test_seuil_par_defaut_lu_via_le_module(monkeypatch):
	"""World-var réglable à chaud : la relire via le module, jamais par from-import."""
	perso = _joueur()
	av = _compagnon("aventurier:1", caracteristiques_current={"Cha": 99})
	perso["affinites"] = {av["_id"]: 60}
	monkeypatch.setattr(character_stats, "MARCHANDAGE_COMPAGNON_AFFINITE_MIN", 90)
	_doc, _cha, est_compagnon = expedition.meilleur_negociateur(perso, [av])
	assert est_compagnon is False

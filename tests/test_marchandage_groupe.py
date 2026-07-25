"""Marchandage mené par le groupe — le jet passe par le plus haut Cha BUFFÉ.

Deux régressions figées ici :
  1. le Cha jeté doit intégrer les TROIS sources de `consommables._sources_de_buffs`
	 (équipement, passives, effets à durée). Le lire brut était le bug historique :
	 `competence:aura_sympathique` (+5 Cha) ne pesait rien sur le marchandage ;
  2. une MONTURE, si charismatique soit-elle, ne négocie jamais — `expedition.membres`
	 n'est pas `recrutement.porteurs_effectifs`.

Logique pure : on teste le chokepoint `expedition.meilleur_negociateur` et la composition
de l'expédition, pas l'endpoint (qui n'ajoute que `sync_equipment_bonus` + l'appel à
`marche.marchander`).
"""

import pytest

from utils import expedition
from utils import recrutement


PRINCIPAL = "character:joueur"


def _joueur(cha=50, **extra):
	perso = {"_id": PRINCIPAL, "inventaire": [], "slots": {},
			 "caracteristiques_current": {"Cha": cha}}
	perso.update(extra)
	return perso


def _compagnon(av_id, cha, **extra):
	av = {"_id": av_id, "type": "aventurier", "statut": "embauche",
		  "embauche_par": PRINCIPAL, "prenom": "Lyra", "nom": "Vent-d'Ambre",
		  "inventaire": [], "slots": {}, "caracteristiques_current": {"Cha": cha}}
	av.update(extra)
	return av


@pytest.fixture
def db(monkeypatch):
	docs = {}

	def get_doc(doc_id):
		return docs.get(doc_id)

	monkeypatch.setattr(recrutement, "get_doc", get_doc)
	monkeypatch.setattr(recrutement.montures, "get_doc", get_doc)
	return docs


# ── (1) le Cha jeté est le Cha BUFFÉ ─────────────────────────────────────────────

@pytest.mark.parametrize("origine, champ", [
	("equipement", "equipment_bonus"),
	("passive", "competences_bonus"),
])
def test_cha_du_negociateur_integre_les_bonus_permanents(origine, champ):
	"""Équipement et passives sont des agrégats DÉNORMALISÉS sur le doc — c'est ce que
	`caracts_avec_buffs` replie, et ce que le jet brut ignorait."""
	perso = _joueur(cha=40)
	av = _compagnon("aventurier:1", 30, **{champ: {"nom": origine, "buffs": {"Cha": 25}}})
	perso["affinites"] = {av["_id"]: 90}
	doc, cha, est_compagnon = expedition.meilleur_negociateur(perso, [av], seuil_min=50)
	assert (doc["_id"], cha, est_compagnon) == (av["_id"], 55, True)


def test_cha_du_negociateur_integre_un_effet_a_duree():
	perso = _joueur(cha=40)
	av = _compagnon("aventurier:1", 30, effets_actifs=[
		{"nom": "Philtre d'éloquence", "item_id": "item:philtre",
		 "buffs": {"Cha": 20}, "restants": 2}])
	perso["affinites"] = {av["_id"]: 90}
	_doc, cha, est_compagnon = expedition.meilleur_negociateur(perso, [av], seuil_min=50)
	assert (cha, est_compagnon) == (50, True)


def test_les_buffs_du_principal_comptent_aussi():
	"""Le correctif profite d'abord au joueur : un ménestrel PRINCIPAL doit voir sa passive
	peser, même sans compagnon."""
	perso = _joueur(cha=40, competences_bonus={"nom": "Aura", "buffs": {"Cha": 15}})
	doc, cha, est_compagnon = expedition.meilleur_negociateur(perso, [])
	assert (doc["_id"], cha, est_compagnon) == (PRINCIPAL, 55, False)


def test_le_plus_charismatique_des_compagnons_l_emporte():
	perso = _joueur(cha=20)
	beau_parleur = _compagnon("aventurier:1", 70)
	bourru = _compagnon("aventurier:2", 25)
	perso["affinites"] = {"aventurier:1": 80, "aventurier:2": 80}
	doc, cha, _est = expedition.meilleur_negociateur(perso, [bourru, beau_parleur], seuil_min=50)
	assert (doc["_id"], cha) == ("aventurier:1", 70)


# ── (2) une monture ne négocie pas ───────────────────────────────────────────────

def test_une_monture_au_cha_ecrasant_n_est_jamais_negociatrice(db):
	"""Elle vit dans `porteurs_effectifs` (elle porte le butin) mais pas dans
	l'expédition : `membres` est la barrière, et c'est elle que l'endpoint appelle."""
	av = _compagnon("aventurier:1", 30)
	mon = {"_id": "monture:1", "type": "monture", "statut": "acquise",
		   "acquise_par": PRINCIPAL, "nom": "Bourrin",
		   "caracteristiques_current": {"Cha": 99}}
	db.update({av["_id"]: av, mon["_id"]: mon})
	perso = _joueur(cha=45, groupe=[av["_id"]], montures=[mon["_id"]],
					affinites={av["_id"]: 90})

	membres = expedition.membres(perso, db.get)
	assert mon not in membres
	doc, cha, est_compagnon = expedition.meilleur_negociateur(perso, membres[1:])
	assert (doc["_id"], cha, est_compagnon) == (PRINCIPAL, 45, False)

# tests/test_mercenaires_endpoints.py
#
# Endpoints des compagnons-JOUEURS (`routers/auberge.py` : /auberge/services*) : inscription,
# retrait, engagement par un autre compte, refus du même compte, recruteur unique (409), et
# le verrou d'équipement de `routers/user._refuser_clone`. Base en mémoire de
# tests/test_auberge_endpoints.py.

import pytest
from fastapi import HTTPException

from utils import mercenaires

from tests.test_auberge_endpoints import monde, _appel, _perso  # noqa: F401 (fixture)


def _offreur():
	return _perso(_id="character:o_1", user_id="user:o", prenom="Ysolde", nom="Brune",
				  xp_total=200, vocations_niveaux={}, voc="guerrier",
				  slots={"main_droite": {"item": "item:epee", "poids": 2}})


def _recruteur(cid="character:u_1", user="user:u"):
	return _perso(_id=cid, user_id=user, affinites={})


def _inscrire(monde, offreur, **body):
	return _appel(monde, offreur, monde["ra"].proposer_services,
				  None, {"part_butin_pct": 12, "clauses": "Pas d'égouts.", **body})


def test_inscription_puis_affichage_aux_autres_seulement(monde):
	offreur = _offreur()
	data = _inscrire(monde, offreur)
	assert data["mon_offre"]["exigences"] == {"part_butin_pct": 12, "clauses": ["Pas d'égouts."]}
	assert data["mon_offre"]["ici"] is True
	assert data["services"] == []                     # on ne se voit pas soi-même
	vue = _appel(monde, _recruteur(), monde["ra"].salle, None)
	assert [s["prenom"] for s in vue["services"]] == ["Ysolde"]
	assert vue["services"][0]["exigences_effectives"]["part_butin_pct"] == 12
	# Rien du personnage d'autrui en clair dans l'id servi.
	assert "o_1" not in vue["services"][0]["id"]


def test_engager_cree_un_clone_au_sac_vide(monde):
	offreur = _offreur()
	_inscrire(monde, offreur)
	recruteur = _recruteur()
	offre_id = mercenaires.id_offre(offreur["_id"])
	data = _appel(monde, recruteur, monde["ra"].engager_services, None, {"offre_id": offre_id})
	assert data["engage"]["nom"] == "Ysolde Brune"
	assert data["services"] == []                     # l'offre est prise
	clone = monde["docs"][recruteur["groupe"][0]]
	assert mercenaires.est_clone(clone) and clone["statut"] == "embauche"
	assert clone["inventaire"] == []
	assert clone["slots"]["main_droite"] == {"item": "item:epee", "poids": 2}
	assert monde["docs"][offre_id]["clone_id"] == clone["_id"]
	# Un second recruteur bute : un seul à la fois.
	with pytest.raises(HTTPException) as e:
		_appel(monde, _recruteur("character:z_1", "user:z"), monde["ra"].engager_services,
			   None, {"offre_id": offre_id})
	assert e.value.status_code == 409
	# Et l'offreur ne change pas ses termes en cours de contrat.
	with pytest.raises(HTTPException) as e:
		_inscrire(monde, offreur)
	assert e.value.status_code == 409
	vue = _appel(monde, offreur, monde["ra"].salle, None)
	assert vue["mon_offre"]["engage_par"] == "Greta Hazgard"


def test_meme_compte_refuse(monde):
	offreur = _offreur()
	_inscrire(monde, offreur)
	with pytest.raises(HTTPException) as e:
		_appel(monde, _recruteur("character:o_2", "user:o"), monde["ra"].engager_services,
			   None, {"offre_id": mercenaires.id_offre(offreur["_id"])})
	assert e.value.status_code == 403


def test_offre_d_une_autre_auberge_introuvable(monde):
	offreur = _offreur()
	_inscrire(monde, offreur)
	monde["docs"][mercenaires.id_offre(offreur["_id"])]["lieu"] = "lieu:ailleurs"
	with pytest.raises(HTTPException) as e:
		_appel(monde, _recruteur(), monde["ra"].engager_services,
			   None, {"offre_id": mercenaires.id_offre(offreur["_id"])})
	assert e.value.status_code == 404


def test_retirer_ses_services(monde):
	offreur = _offreur()
	_inscrire(monde, offreur)
	data = _appel(monde, offreur, monde["ra"].retirer_services, None)
	assert data["mon_offre"] is None
	assert monde["docs"][mercenaires.id_offre(offreur["_id"])]["statut"] == "retire"
	with pytest.raises(HTTPException) as e:
		_appel(monde, offreur, monde["ra"].retirer_services, None)
	assert e.value.status_code == 404


def test_equipement_d_un_clone_verrouille():
	from routers import user as ru
	with pytest.raises(HTTPException) as e:
		ru._refuser_clone({"source_character": "character:o_1"})
	assert e.value.status_code == 403
	ru._refuser_clone({"_id": "aventurier:guilde_x"})   # un compagnon ordinaire passe

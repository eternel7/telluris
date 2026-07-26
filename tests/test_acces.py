# tests/test_acces.py
# Barrière d'accès à un lieu, gardée par un PNJ (utils/acces.py). Logique pure : DB
# injectée par un faux `get_doc`, aucun accès réseau. Pattern tests/test_transport.py.

import pytest

from models import character_stats
from utils import acces


DOCS = {
	"lieu:guilde": {"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier"},
	"lieu:auberge": {"_id": "lieu:auberge", "type": "lieu", "categorie": "auberge"},
}


def get_doc(doc_id):
	return DOCS.get(doc_id)


def _character(**extra):
	return {"_id": "character:1", "inventaire": [], "quetes_actives": [], **extra}


def _quete(type_="chasse", lieu="lieu:portail", cible="espece:loup", giver="lieu:guilde"):
	return {"id": "quete:1", "giver": giver, "objectif": {"type": type_, "lieu": lieu, "cible": cible}}


def _lieu_garde(conditions, cycle=1, refus="Refusé."):
	return {
		"_id": "lieu:portail",
		"type": "lieu",
		"acces": {
			"gardien": "pnj:garde",
			"refus": refus,
			"cycle": cycle,
			"conditions": conditions,
		},
	}


@pytest.fixture(autouse=True)
def defauts(monkeypatch):
	"""Remet la world-var à son défaut avant chaque test (certains la font varier)."""
	monkeypatch.setattr(character_stats, "ACCES_GARDIEN_ACTIF", True)


# ---------------------------------------------------------------------------
# gate_de / cycle_de — lieu sans barrière
# ---------------------------------------------------------------------------

def test_lieu_sans_acces_est_libre():
	lieu = {"_id": "lieu:place", "type": "lieu"}
	assert acces.gate_de(lieu) is None
	ok, raison = acces.conditions_remplies(_character(), lieu, get_doc)
	assert ok and raison == ""
	ok, _ = acces.acces_autorise(_character(), lieu, get_doc)
	assert ok


def test_character_sans_laissez_passer_ne_leve_aucune_erreur():
	# Champ absent ⇒ aucune migration nécessaire.
	character = _character()
	assert "laissez_passer" not in character
	assert acces.laissez_passer_valide(character, _lieu_garde([])) is False


# ---------------------------------------------------------------------------
# quete_active
# ---------------------------------------------------------------------------

def test_quete_active_aucune_quete_refuse():
	lieu = _lieu_garde([{"quete_active": {"giver_categorie": "guilde_aventurier"}}])
	ok, raison = acces.conditions_remplies(_character(), lieu, get_doc)
	assert not ok and raison == "Refusé."


def test_quete_active_filtre_lieu_isole():
	lieu = _lieu_garde([{"quete_active": {"lieu": "lieu:portail"}}])
	character = _character(quetes_actives=[_quete(lieu="lieu:portail")])
	assert acces.conditions_remplies(character, lieu, get_doc)[0]
	character_autre = _character(quetes_actives=[_quete(lieu="lieu:ailleurs")])
	assert not acces.conditions_remplies(character_autre, lieu, get_doc)[0]


def test_quete_active_filtre_cible_isole():
	lieu = _lieu_garde([{"quete_active": {"cible": "espece:loup"}}])
	character = _character(quetes_actives=[_quete(cible="espece:loup")])
	assert acces.conditions_remplies(character, lieu, get_doc)[0]
	character_autre = _character(quetes_actives=[_quete(cible="espece:ours")])
	assert not acces.conditions_remplies(character_autre, lieu, get_doc)[0]


def test_quete_active_filtre_types_isole():
	lieu = _lieu_garde([{"quete_active": {"types": ["eradication", "chasse"]}}])
	character = _character(quetes_actives=[_quete(type_="chasse")])
	assert acces.conditions_remplies(character, lieu, get_doc)[0]
	character_autre = _character(quetes_actives=[_quete(type_="collect")])
	assert not acces.conditions_remplies(character_autre, lieu, get_doc)[0]


def test_quete_active_giver_categorie_resolue_par_get_doc():
	lieu = _lieu_garde([{"quete_active": {"giver_categorie": "guilde_aventurier"}}])
	character = _character(quetes_actives=[_quete(giver="lieu:guilde")])
	assert acces.conditions_remplies(character, lieu, get_doc)[0]
	character_autre = _character(quetes_actives=[_quete(giver="lieu:auberge")])
	assert not acces.conditions_remplies(character_autre, lieu, get_doc)[0]


def test_quete_active_filtres_combines():
	lieu = _lieu_garde([{"quete_active": {
		"lieu": "lieu:portail", "types": ["chasse"], "giver_categorie": "guilde_aventurier",
	}}])
	# Une seule quête satisfait TOUS les filtres à la fois → autorisé.
	character = _character(quetes_actives=[
		_quete(type_="collect", lieu="lieu:portail", giver="lieu:guilde"),
		_quete(type_="chasse", lieu="lieu:portail", giver="lieu:guilde"),
	])
	assert acces.conditions_remplies(character, lieu, get_doc)[0]


def test_quete_active_objectif_atteint_ferme_la_boucle():
	"""LE test anti-boucle : une quête ACCOMPLIE mais pas encore rapportée reste dans
	`quetes_actives` — sans ce filtre elle continue d'ouvrir la porte du donjon, et le joueur
	rejoue le combat en boucle tant qu'il ne va pas rendre compte (constaté en jeu)."""
	lieu = _lieu_garde([{"quete_active": {"lieu": "lieu:portail", "objectif_atteint": False}}])
	q = _quete()
	q["objectif"]["quantite"] = 1
	# En cours (progress 0/1) → la porte s'ouvre.
	q["progress"] = 0
	assert acces.conditions_remplies(_character(quetes_actives=[q]), lieu, get_doc)[0]
	# Accomplie (1/1), pas encore rapportée → la porte se referme.
	q["progress"] = 1
	assert not acces.conditions_remplies(_character(quetes_actives=[q]), lieu, get_doc)[0]


def test_quete_active_objectif_atteint_vrai_exige_l_inverse():
	# Symétrique : une porte peut n'ouvrir qu'APRÈS l'accomplissement (salle du trésor…).
	lieu = _lieu_garde([{"quete_active": {"objectif_atteint": True}}])
	q = _quete()
	q["objectif"]["quantite"] = 1
	q["progress"] = 0
	assert not acces.conditions_remplies(_character(quetes_actives=[q]), lieu, get_doc)[0]
	q["progress"] = 1
	assert acces.conditions_remplies(_character(quetes_actives=[q]), lieu, get_doc)[0]


def test_quete_active_objectif_atteint_absent_ne_filtre_rien():
	# Rétro-compatibilité : les barrières déjà écrites ne changent pas de comportement.
	lieu = _lieu_garde([{"quete_active": {"lieu": "lieu:portail"}}])
	q = _quete()
	q["objectif"]["quantite"] = 1
	for progress in (0, 1):
		q["progress"] = progress
		assert acces.conditions_remplies(_character(quetes_actives=[q]), lieu, get_doc)[0]


def test_quete_active_filtre_absent_est_permissif():
	# `quete_active: {}` = n'importe quelle quête active suffit.
	lieu = _lieu_garde([{"quete_active": {}}])
	character = _character(quetes_actives=[_quete()])
	assert acces.conditions_remplies(character, lieu, get_doc)[0]


# ---------------------------------------------------------------------------
# item
# ---------------------------------------------------------------------------

def test_item_sans_lieu_parent():
	lieu = _lieu_garde([{"item": {"item": "item:cle"}}])
	character = _character(inventaire=["item:cle"])
	assert acces.conditions_remplies(character, lieu, get_doc)[0]
	assert not acces.conditions_remplies(_character(), lieu, get_doc)[0]


def test_item_avec_lieu_parent():
	lieu = _lieu_garde([{"item": {"item": "item:carte_aventurier", "lieu_parent": "lieu:auxerre"}}])
	bonne = _character(inventaire=[{"item": "item:carte_aventurier", "lieu_parent": "lieu:auxerre"}])
	assert acces.conditions_remplies(bonne, lieu, get_doc)[0]
	mauvaise = _character(inventaire=[{"item": "item:carte_aventurier", "lieu_parent": "lieu:rhemi"}])
	assert not acces.conditions_remplies(mauvaise, lieu, get_doc)[0]


# ---------------------------------------------------------------------------
# rang_min — porte de prestige (rang de guilde, par cité)
# ---------------------------------------------------------------------------

def _lieu_rang(rang="D", cite="lieu:auxerre"):
	return _lieu_garde([{"rang_min": {"cite": cite, "rang": rang}}])


def test_rang_min_sans_rang_refuse():
	# `rangs_guilde` absent ⇒ repli sur le PREMIER de l'échelle (miroir de chasse.rang_de).
	character = _character()
	assert "rangs_guilde" not in character
	assert not acces.conditions_remplies(character, _lieu_rang("D"), get_doc)[0]


def test_rang_min_seuil_au_premier_cran_toujours_atteint():
	# Un seuil posé sur le rang de départ n'exclut personne (garde-fou : une porte ouverte
	# ne doit pas se refermer sur un repli).
	seuil = acces.RANGS[0]
	assert acces.conditions_remplies(_character(), _lieu_rang(seuil), get_doc)[0]


def test_rang_min_rang_exact_autorise():
	character = _character(rangs_guilde={"lieu:auxerre": "D"})
	assert acces.conditions_remplies(character, _lieu_rang("D"), get_doc)[0]


def test_rang_min_rang_superieur_autorise():
	character = _character(rangs_guilde={"lieu:auxerre": "B"})
	assert acces.conditions_remplies(character, _lieu_rang("D"), get_doc)[0]


def test_rang_min_rang_juste_en_dessous_refuse():
	character = _character(rangs_guilde={"lieu:auxerre": "E"})
	ok, raison = acces.conditions_remplies(character, _lieu_rang("D"), get_doc)
	assert not ok and raison == "Refusé."


def test_rang_min_est_propre_a_la_cite():
	# Monter à Rhemi n'ouvre pas les portes d'Auxerre.
	character = _character(rangs_guilde={"lieu:rhemi": "A"})
	assert not acces.conditions_remplies(character, _lieu_rang("D", "lieu:auxerre"), get_doc)[0]


def test_rang_min_sommet_de_l_echelle():
	# Ne jamais coder en dur la VALEUR du dernier rang : l'échelle est passée de 7 à 8 crans.
	sommet = acces.RANGS[-1]
	character = _character(rangs_guilde={"lieu:auxerre": sommet})
	assert acces.conditions_remplies(character, _lieu_rang(sommet), get_doc)[0]


def test_rang_min_filtre_incomplet_refuse():
	# Fail-closed : sans `cite` ou sans `rang`, il n'y a pas de comparaison possible.
	for filtre in ({}, {"cite": "lieu:auxerre"}, {"rang": "D"}):
		lieu = _lieu_garde([{"rang_min": filtre}])
		character = _character(rangs_guilde={"lieu:auxerre": "S"})
		assert not acces.conditions_remplies(character, lieu, get_doc)[0], filtre


def test_rang_min_rang_hors_echelle_refuse():
	# Un rang inventé, côté DONNÉE comme côté PERSO, ne doit pas ouvrir la porte.
	character = _character(rangs_guilde={"lieu:auxerre": "Z"})
	assert not acces.conditions_remplies(character, _lieu_rang("D"), get_doc)[0]
	bonne = _character(rangs_guilde={"lieu:auxerre": "S"})
	assert not acces.conditions_remplies(bonne, _lieu_rang("Z"), get_doc)[0]


# ---------------------------------------------------------------------------
# Fail-closed
# ---------------------------------------------------------------------------

def test_cle_condition_inconnue_refuse():
	lieu = _lieu_garde([{"relation_min": {"lieux": ["lieu:guilde"], "seuil": 50}}])
	assert not acces.conditions_remplies(_character(), lieu, get_doc)[0]


def test_conditions_invalides_remonte_les_cles_inconnues():
	# `rang_min` est désormais CÂBLÉ (cf. section plus bas) : seul `relation_min` reste
	# un point d'extension documenté mais non implémenté.
	lieu = _lieu_garde([{"relation_min": {"seuil": 50}}, {"rang_min": {"rang": "C"}}])
	assert set(acces.conditions_invalides(lieu)) == {"relation_min"}


def test_conditions_invalides_vide_pour_vocabulaire_connu():
	lieu = _lieu_garde([{"quete_active": {}}, {"item": {"item": "item:cle"}},
					   {"rang_min": {"cite": "lieu:auxerre", "rang": "D"}}])
	assert acces.conditions_invalides(lieu) == []


def test_conditions_invalides_vide_sans_barriere():
	assert acces.conditions_invalides({"_id": "lieu:place", "type": "lieu"}) == []


def test_conditions_invalides_remonte_les_SOUS_filtres_inconnus():
	"""Un sous-filtre fautif est bien plus dangereux qu'une clé fautive : le moteur l'IGNORE
	(donc barrière plus permissive, en silence) au lieu de refuser. `objectifatteint` sans
	underscore rouvrirait la boucle du donjon sans que rien ne le signale."""
	lieu = _lieu_garde([{"quete_active": {"lieu": "lieu:portail", "objectifatteint": False}}])
	assert acces.conditions_invalides(lieu) == ["quete_active.objectifatteint"]
	# Le moteur, lui, laisse effectivement passer — d'où l'utilité du linter.
	q = _quete()
	q["objectif"]["quantite"] = 1
	q["progress"] = 1
	assert acces.conditions_remplies(_character(quetes_actives=[q]), lieu, get_doc)[0]


def test_conditions_invalides_sous_filtres_des_autres_cles():
	lieu = _lieu_garde([{"item": {"item": "item:cle", "lieu_parnt": "x"}},
					   {"rang_min": {"cite": "lieu:auxerre", "rangs": "D"}}])
	assert set(acces.conditions_invalides(lieu)) == {"item.lieu_parnt", "rang_min.rangs"}


def test_conditions_invalides_tous_les_sous_filtres_connus_passent():
	lieu = _lieu_garde([
		{"quete_active": {"lieu": "l", "types": [], "giver_categorie": "g", "cible": "c",
						  "objectif_atteint": False}},
		{"item": {"item": "i", "lieu_parent": "p"}},
		{"rang_min": {"cite": "c", "rang": "D"}},
	])
	assert acces.conditions_invalides(lieu) == []


# ---------------------------------------------------------------------------
# Laissez-passer
# ---------------------------------------------------------------------------

def test_laissez_passer_pose_autorise():
	lieu = _lieu_garde([{"quete_active": {}}])
	character = _character()
	assert not acces.conditions_remplies(character, lieu, get_doc)[0]
	acces.poser_laissez_passer(character, lieu, "pnj:garde")
	assert acces.laissez_passer_valide(character, lieu)
	ok, _ = acces.acces_autorise(character, lieu, get_doc)
	assert ok


def test_laissez_passer_perime_si_le_cycle_bouge():
	lieu = _lieu_garde([{"quete_active": {}}], cycle=1)
	character = _character()
	acces.poser_laissez_passer(character, lieu, "pnj:garde")
	assert acces.laissez_passer_valide(character, lieu)
	lieu["acces"]["cycle"] = 2
	assert not acces.laissez_passer_valide(character, lieu)
	ok, _ = acces.acces_autorise(character, lieu, get_doc)
	assert not ok


def test_revoquer_retire_le_laissez_passer():
	lieu = _lieu_garde([{"quete_active": {}}])
	character = _character()
	acces.poser_laissez_passer(character, lieu, "pnj:garde")
	assert acces.revoquer(character, "lieu:portail") is True
	assert not acces.laissez_passer_valide(character, lieu)
	# Rien à retirer une deuxième fois.
	assert acces.revoquer(character, "lieu:portail") is False


# ---------------------------------------------------------------------------
# Kill-switch
# ---------------------------------------------------------------------------

def test_kill_switch_desactive_toutes_les_barrieres(monkeypatch):
	monkeypatch.setattr(character_stats, "ACCES_GARDIEN_ACTIF", False)
	lieu = _lieu_garde([{"quete_active": {}}])
	ok, raison = acces.acces_autorise(_character(), lieu, get_doc)
	assert ok and raison == ""

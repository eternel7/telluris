"""Endpoints HORS de la boucle d'événements.

L'accès CouchDB est synchrone : un endpoint `async def` gèle la boucle d'uvicorn — donc tous
les joueurs — pendant ses allers-retours base. Les endpoints qui ne touchent que les docs du
joueur sont donc des `def` (threadpool de FastAPI) ; ceux à état partagé restent en file.
Contrepartie : un `def` n'est plus seul à tourner, une écriture refusée par CouchDB (`_rev`)
doit se dire au lieu de passer pour un succès."""

import inspect

import pytest
from fastapi import HTTPException


# Périmètre VOULU (constante, pas un compte dérivé) : ce qui n'écrit que les docs du joueur —
# ou ne fait que lire — n'a pas à attendre les autres joueurs.
HORS_BOUCLE = {
	"main": ["get_playground", "get_embleme", "get_combat_page"],
	"routers.traversee": ["traversee_avancer"],
	"routers.user": [
		"move_character", "renommer_personnage", "renommer_objet", "focaliser", "consommer_item",
		"ecrire_journal", "slot_action", "slot_deplacer", "drop_item", "pickup_item",
		"couper_item", "lancer_sort", "utiliser_competence", "apprendre_sort",
		"apprendre_magie", "monter_magie", "vocation_options", "spend_xp",
		"spend_xp_vocation", "equip_item", "unequip_item", "changer_vocation",
		"recolter_ressource", "apprendre_competence", "select_character",
		"update_character_portrait"],
	"routers.contenants": ["contenant_ranger", "contenant_sortir", "contenant_poser"],
	"routers.recrutement": ["groupe_renommer_compagnie", "groupe_transferer",
							"groupe_compagnon", "groupe_etat"],
	"routers.scriptorium": ["ecrire_scriptorium", "salle_scriptorium"],
	"routers.guides": ["demander", "dialogue"],
	"routers.pnj": ["intro_raison", "pnj_portail_seuils"],
	"routers.commande": ["retirer_commande", "annuler_commande"],
	"routers.combat": ["get_combat", "combat_acteur", "start_combat", "combat_action",
					   "collect_loot"],
	"routers.montures": ["etable_board"],
	"routers.zones": ["list_zones", "get_zone", "list_items"],
}

# ⚠️ État PARTAGÉ entre joueurs (stock d'une boutique, tableaux, tables d'auberge, biens) :
# chaque action y influence la suivante. Ces endpoints restent des coroutines — sérialisés
# par la boucle. En sortir un, c'est d'abord traiter ses écritures concurrentes.
EN_FILE = {
	"routers.user": ["buy_item", "sell_item", "marchander_item"],
	"routers.commande": ["passer_commande", "relancer_commande"],
	"routers.quetes": ["quetes_board", "quetes_accepter", "quetes_terminer"],
	"routers.recrutement": ["recrutement_board", "recrutement_embaucher"],
	"routers.pnj": ["pnj_dialogue", "pnj_dialogue_choix"],
	"routers.montures": ["acheter_monture"],
}


def _endpoints(table):
	import importlib
	for module, noms in table.items():
		mod = importlib.import_module(module)
		for nom in noms:
			yield f"{module}.{nom}", getattr(mod, nom)


def test_les_endpoints_personnels_ne_sont_pas_des_coroutines():
	for nom, endpoint in _endpoints(HORS_BOUCLE):
		assert not inspect.iscoroutinefunction(endpoint), nom


def test_les_endpoints_a_etat_partage_restent_en_file():
	for nom, endpoint in _endpoints(EN_FILE):
		assert inspect.iscoroutinefunction(endpoint), nom


def test_pas_refuse_en_409_si_le_personnage_n_est_pas_sauve(monkeypatch):
	"""Écriture du personnage refusée ⇒ 409 (le client remet la carte en place), et les docs
	du groupe ne sont pas écrits : ils sont ANNEXES, persistés après lui."""
	from routers import user as ru
	char = {"_id": "character:u_1", "type": "character", "user_id": "u",
			"lieu": "lieu:pre", "position": {"x": 1, "y": 1},
			"caracteristiques_current": {}, "inventaire": [], "groupe": [], "montures": []}
	lieu = {"_id": "lieu:pre", "type": "lieu", "dimensions": {"x": 5, "y": 5}}
	lots = []
	monkeypatch.setattr(ru, "get_selected_character", lambda _u: char)
	monkeypatch.setattr(ru, "get_doc", lambda doc_id: lieu if doc_id == "lieu:pre" else None)
	monkeypatch.setattr(ru, "find_docs", lambda *a, **k: [])
	monkeypatch.setattr(ru, "get_lieu_directions", lambda *a, **k: {})
	monkeypatch.setattr(ru, "save_doc", lambda doc: None)
	monkeypatch.setattr(ru, "save_docs", lambda ds: lots.append(ds) or [])

	with pytest.raises(HTTPException) as e:
		ru.move_character(None, {"_id": "u"}, {"x": 1, "y": 0})

	assert e.value.status_code == 409
	assert lots == []

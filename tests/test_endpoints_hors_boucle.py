"""Endpoints de déplacement HORS de la boucle d'événements.

L'accès CouchDB est synchrone : un endpoint `async def` gèle la boucle d'uvicorn — donc tous
les joueurs — pendant ses allers-retours base. Le pas, la case de traversée et `/play` sont
donc des `def` (threadpool de FastAPI). Contrepartie : un pas n'est plus seul à tourner, une
écriture refusée par CouchDB (`_rev`) doit se dire au lieu de passer pour un succès."""

import inspect

import pytest
from fastapi import HTTPException


def test_le_pas_la_traversee_et_play_ne_sont_pas_des_coroutines():
	import main
	from routers import user as ru, traversee as rt
	for endpoint in (ru.move_character, rt.traversee_avancer, main.get_playground):
		assert not inspect.iscoroutinefunction(endpoint), endpoint.__name__


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

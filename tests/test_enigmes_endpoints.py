# tests/test_enigmes_endpoints.py — réponse de `routers/enigmes` à la résolution : /play n'est
# pas rechargé, tout ce qu'il a rendu et qui dépend de `enigme_resolue` revient dans la réponse
# (convention 10) — portes, marques de lieux, énigmes à bouton, lignes 🗣. Base en mémoire.

import copy

import pytest

LIEU = "lieu:atelier_test"
LIEU_DOC = {"_id": LIEU, "type": "lieu", "categorie": "maison",
			"pnj": [{"character": "pnj:puca", "label": "Le Púca"},
					{"character": "pnj:enfant", "label": "L'enfant",
					 "conditions": [{"enigme_resolue": {"id": "enigme:crans", "attendu": False}}]}]}
CRANS = {"_id": "enigme:crans", "type": "enigme", "nom": "Les tiroirs", "famille": "crans",
		 "lieux": [LIEU], "bouton": True,
		 "elements": {"pieces": [{"id": "a", "label": "Tiroir A", "crans": 4, "depart": 0}]},
		 "solution": {"positions": {"a": 3}}, "reussite": "Ouvert.", "echec": "Rien."}
# Ouvrable seulement une fois `enigme:crans` résolue : la résolution le fait apparaître.
SUITE = {"_id": "enigme:suite", "type": "enigme", "nom": "La plaque", "famille": "crans",
		 "lieux": [LIEU], "bouton": True, "prerequis": ["enigme:crans"],
		 "elements": {"pieces": [{"id": "a", "label": "Plaque", "crans": 2, "depart": 0}]},
		 "solution": {"positions": {"a": 1}}, "reussite": "Ouvert.", "echec": "Rien."}
PNJS = [{"_id": "pnj:puca", "type": "pnj", "nom": "Le Púca"},
		{"_id": "pnj:enfant", "type": "pnj", "nom": "L'enfant"}]


@pytest.fixture
def monde(monkeypatch):
	from routers import enigmes as re
	from routers import pnj as rp

	perso = {"_id": "character:u_1", "type": "character", "lieu": LIEU, "position": {"x": 1, "y": 1},
			 "pnj_present": {"lieu": LIEU, "characters": ["pnj:puca", "pnj:enfant"]}}
	docs = {d["_id"]: copy.deepcopy(d) for d in [LIEU_DOC, CRANS, SUITE, perso] + PNJS}

	def find_docs_fn(selector, fields=None):
		return [d for d in docs.values() if all(d.get(k) == v for k, v in selector.items())]

	for mod in (re, rp):
		monkeypatch.setattr(mod, "get_doc", lambda i: docs.get(i))
	monkeypatch.setattr(re, "save_doc", lambda d: docs.__setitem__(d["_id"], d) or d)
	monkeypatch.setattr(re, "find_docs", find_docs_fn)
	monkeypatch.setattr(re, "get_selected_character", lambda u: docs["character:u_1"])
	monkeypatch.setattr(re, "get_lieu_links", lambda u: [{"nodes": []}])
	monkeypatch.setattr(re.journal, "journal_payload", lambda c, g: {})
	# Le contexte de dialogue complet n'est pas l'objet du test : la marque est un témoin.
	monkeypatch.setattr(rp, "marque_pnj", lambda c, d, l=None, e=None: "!" if d["_id"] == "pnj:puca" else None)
	return re, docs


def _essayer(re, a):
	return re.enigme_action({"id": "u_1"}, {"id": "enigme:crans", "action": "essayer", "positions": {"a": a}})


def test_un_essai_faux_ne_resynchronise_pas_le_lieu(monde):
	re, _ = monde
	rep = _essayer(re, 1)
	assert not rep["resultat"]["resolue"]
	for cle in ("links", "lieux_marques", "enigmes_ici", "pnjs_ici", "pnj_marques"):
		assert cle not in rep


def test_la_resolution_resynchronise_portes_enigmes_et_pnj(monde):
	re, _ = monde
	rep = _essayer(re, 3)
	assert rep["resultat"]["resolue"]
	assert rep["links"] == [{"nodes": []}] and "lieux_marques" in rep
	# ✓ devant l'énigme résolue, et la suivante (prérequis) apparaît.
	assert rep["enigmes_ici"] == [{"id": "enigme:crans", "nom": "Les tiroirs", "resolue": True},
								  {"id": "enigme:suite", "nom": "La plaque", "resolue": False}]
	# L'enfant (condition `attendu: false`) s'efface ; le Púca reste, avec sa marque.
	assert rep["pnjs_ici"] == ["pnj:puca"]
	assert rep["pnj_marques"] == {"pnj:puca": "!"}


def test_rejouer_une_enigme_deja_resolue_ne_resynchronise_rien(monde):
	re, _ = monde
	_essayer(re, 3)
	assert "enigmes_ici" not in _essayer(re, 3)

# tests/test_lieux_acces.py
# get_lieu_links (utils/lieux.py) filtre les connexions dont le lieu de DESTINATION est
# verrouillé par une barrière d'accès (utils/acces.py). `db`/`get_doc`/
# `get_selected_character` sont monkeypatchés au niveau du module : get_lieu_links
# n'accepte pas de DB injectée (il n'est pas "pur" comme utils/quetes.py), donc le test
# isole la vraie CouchDB en substituant ces trois noms dans l'espace du module.

import pytest

from utils import lieux as lieux_module

CURRENT_USER = {"_id": "user:test"}
CHARACTER = {"position": {"x": 1, "y": 1}, "lieu": "lieu:ville",
			 "quetes_actives": [], "inventaire": []}

# `lieu:ville` (le lieu COURANT) porte volontairement une barrière qu'il échouerait
# lui-même — ça vérifie qu'elle n'est jamais évaluée pour le nœud courant.
DOCS = {
	"lieu:ville": {"_id": "lieu:ville", "type": "lieu",
				   "acces": {"gardien": "pnj:x", "refus": "Fermé.", "cycle": 1,
							 "conditions": [{"quete_active": {}}]}},
	"lieu:portail": {"_id": "lieu:portail", "type": "lieu",
					 "acces": {"gardien": "pnj:x", "refus": "Fermé.", "cycle": 1,
							   "conditions": [{"quete_active": {}}]}},
	"lieu:place": {"_id": "lieu:place", "type": "lieu"},
}

CONN_FERMEE = {"_id": "link:ville_portail", "type": "connection",
			   "nodes": [{"lieu": "lieu:ville", "pos": [1, 1]},
						 {"lieu": "lieu:portail", "pos": [2, 2]}]}
CONN_OUVERTE = {"_id": "link:ville_place", "type": "connection",
				"nodes": [{"lieu": "lieu:ville", "pos": [1, 1]},
						  {"lieu": "lieu:place", "pos": [3, 3]}]}


class _Row:
	def __init__(self, value):
		self.value = value


class _FakeDB:
	def __init__(self, connections):
		self._connections = connections

	def view(self, design, view_name, key=None, startkey=None, endkey=None):
		return [_Row(c) for c in self._connections]


def _get_doc(doc_id):
	doc = DOCS.get(doc_id)
	return dict(doc) if doc else None


def _get_selected_character(current_user):
	return dict(CHARACTER)


@pytest.fixture(autouse=True)
def isole(monkeypatch):
	monkeypatch.setattr(lieux_module, "db", _FakeDB([CONN_FERMEE, CONN_OUVERTE]))
	monkeypatch.setattr(lieux_module, "get_doc", _get_doc)
	monkeypatch.setattr(lieux_module, "get_selected_character", _get_selected_character)


def test_connexion_fermee_est_retiree():
	links = lieux_module.get_lieu_links(CURRENT_USER)
	ids = {c["_id"] for c in links}
	assert ids == {"link:ville_place"}


def test_lieu_courant_jamais_filtre():
	# lieu:ville porte lui-même une barrière qu'il échouerait — mais il n'est jamais le
	# nœud DESTINATION évalué : seule la connexion dont l'AUTRE bout échoue disparaît.
	links = lieux_module.get_lieu_links(CURRENT_USER)
	# La connexion vers lieu:place (ouverte) survit malgré la barrière portée par
	# lieu:ville lui-même.
	assert any(c["_id"] == "link:ville_place" for c in links)


def test_filtrer_acces_false_rend_tout():
	links = lieux_module.get_lieu_links(CURRENT_USER, filtrer_acces=False)
	ids = {c["_id"] for c in links}
	assert ids == {"link:ville_portail", "link:ville_place"}

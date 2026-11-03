"""Passe-muraille (utils/passe_muraille.py) : lecture d'une paire de porte de rempart."""
import glob
import json
import os

import pytest

from utils import passe_muraille as pm


CITE = "lieu:auxerre"
EXT = "lieu:auxerre_porte_pont_exterieur"
INT = "lieu:auxerre_porte_pont_interieur"


def _porte(_id):
	return {"_id": _id, "type": "lieu", "categorie": pm.CATEGORIE_PORTE, "lieu_parent": CITE}


def _monde(connexions, docs=None):
	"""(connexions_fn, get_doc_fn) sur une liste de connexions et des docs de lieu."""
	docs = dict(docs or {})
	docs.setdefault(CITE, {"_id": CITE, "type": "lieu", "categorie": "ville"})
	docs.setdefault(EXT, _porte(EXT))
	docs.setdefault(INT, _porte(INT))

	def connexions_fn(lieu_id):
		return [c for c in connexions if any(n.get("lieu") == lieu_id for n in c["nodes"])]
	return connexions_fn, docs.get


# Forme exacte d'une paire en base (Auxerre, porte du pont) : cinq docs, nœuds porte en [0,0].
PAIRE = [
	{"_id": "link:ext", "nodes": [{"lieu": CITE, "pos": [64, 26], "label": "au-delà des remparts"},
								  {"lieu": EXT, "pos": [0, 0]}]},
	{"_id": "link:passage", "nodes": [{"lieu": EXT, "pos": [0, 0]}, {"lieu": INT, "pos": [0, 0]}]},
	{"_id": "link:int", "nodes": [{"lieu": CITE, "pos": [62, 26]}, {"lieu": INT, "pos": [0, 0]}]},
]


def test_de_l_exterieur_on_arrive_sur_la_case_interieure():
	jumelle, sortie = pm.traversee(EXT, *_monde(PAIRE))
	assert jumelle == INT
	assert (sortie["lieu"], sortie["pos"]) == (CITE, [62, 26])


def test_et_inversement():
	jumelle, sortie = pm.traversee(INT, *_monde(PAIRE))
	assert jumelle == EXT
	assert (sortie["lieu"], sortie["pos"]) == (CITE, [64, 26])


def test_est_porte_lit_la_categorie():
	assert pm.est_porte(_porte(EXT))
	assert not pm.est_porte({"categorie": "ville"})
	assert not pm.est_porte(None)


def test_porte_sans_jumelle_rien_ne_saute():
	assert pm.traversee(EXT, *_monde([PAIRE[0]])) is None


def test_deux_jumelles_indecidable():
	autre = "lieu:auxerre_porte_douve_interieur01"
	conns = PAIRE + [{"_id": "link:x", "nodes": [{"lieu": EXT, "pos": [0, 0]}, {"lieu": autre, "pos": [0, 0]}]}]
	assert pm.traversee(EXT, *_monde(conns, {autre: _porte(autre)})) is None


def test_deux_sorties_indecidable():
	conns = PAIRE + [{"_id": "link:int2", "nodes": [{"lieu": CITE, "pos": [10, 10]}, {"lieu": INT, "pos": [0, 0]}]}]
	assert pm.traversee(EXT, *_monde(conns)) is None


def test_sortie_bouton_false_ignoree():
	"""Un nœud `bouton: false` ne s'emprunte pas (verrou de `lieux.depart_interdit`)."""
	conns = [PAIRE[0], PAIRE[1], {"_id": "link:int", "nodes": [
		{"lieu": CITE, "pos": [62, 26]}, {"lieu": INT, "pos": [0, 0], "bouton": False}]}]
	assert pm.traversee(EXT, *_monde(conns)) is None


def test_connexion_dupliquee_comptee_une_fois():
	assert pm.traversee(EXT, *_monde(PAIRE + [PAIRE[2]]))[1]["pos"] == [62, 26]


def test_sortie_sans_position_rien_ne_saute():
	conns = [PAIRE[0], PAIRE[1], {"_id": "link:int", "nodes": [{"lieu": CITE}, {"lieu": INT, "pos": [0, 0]}]}]
	assert pm.traversee(EXT, *_monde(conns)) is None


def _dernier_dump():
	dumps = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "jsons", "telluris-dump-*.json")))
	return dumps[-1] if dumps else None


@pytest.mark.skipif(_dernier_dump() is None, reason="aucun dump committé")
def test_paires_du_dump_se_traversent_vers_la_cite_parente():
	"""Toute porte du dump dont la paire se lit mène à une case de SA cité parente, et la
	jumelle ramène à l'autre case."""
	docs = {d["_id"]: d for d in json.load(open(_dernier_dump(), encoding="utf-8"))["docs"]}
	conns = [d for d in docs.values() if isinstance(d.get("nodes"), list)]
	par_lieu = {}
	for c in conns:
		for n in c["nodes"]:
			par_lieu.setdefault(n.get("lieu"), []).append(c)
	portes = [d for d in docs.values() if pm.est_porte(d)]
	lues = 0
	for porte in portes:
		saut = pm.traversee(porte["_id"], lambda i: par_lieu.get(i, []), docs.get)
		if saut is None:
			continue
		lues += 1
		jumelle, sortie = saut
		assert sortie["lieu"] == porte.get("lieu_parent"), porte["_id"]
		retour = pm.traversee(jumelle, lambda i: par_lieu.get(i, []), docs.get)
		assert retour and retour[0] == porte["_id"]
		assert retour[1]["pos"] != sortie["pos"], porte["_id"]
	assert lues  # au moins une paire lue : le test ne passe pas à vide


# ── Branchement dans move_character (routers/user.py) ────────────────────────────

def _deplacer(monkeypatch, move, docs_porte=None):
	"""Joue `move_character` depuis la case extérieure de la paire ; rend (lieu, pos) passés à
	`_effets_arrivee`."""
	import asyncio
	from routers import user as ru
	connexions_fn, get_doc_fn = _monde(PAIRE, docs_porte)
	char = {"_id": "character:u_1", "lieu": CITE, "position": {"x": 64, "y": 26}}
	arrivee = {}
	monkeypatch.setattr(ru, "get_selected_character", lambda _u: char)
	monkeypatch.setattr(ru, "get_lieu_links", lambda _u, filtrer_acces=True: [PAIRE[0]])
	monkeypatch.setattr(ru, "get_doc", lambda i: dict(get_doc_fn(i) or {}) or None)
	monkeypatch.setattr(ru, "connexions_du_lieu", connexions_fn)
	monkeypatch.setattr(ru, "carried_weight", lambda _c: 0)
	monkeypatch.setattr(ru, "charge_max_of", lambda _c: 1)
	monkeypatch.setattr(ru, "_guide_au_franchissement", lambda *a, **k: (None, None))
	monkeypatch.setattr(ru.donjon, "donjon_a_etages_de", lambda *a, **k: None)
	monkeypatch.setattr(ru.acces, "acces_autorise",
		lambda _c, doc, _g: (not (doc or {}).get("ferme"), "Le garde vous arrête."))
	monkeypatch.setattr(ru, "_effets_arrivee",
		lambda _c, dest, pos, _doc: arrivee.update(lieu=dest, pos=pos) or {"moved": 1})
	asyncio.run(ru.move_character(None, {"_id": "u"}, move))
	return arrivee["lieu"], arrivee["pos"]


def test_sans_reglage_on_entre_dans_la_porte(monkeypatch):
	assert _deplacer(monkeypatch, {"link": "link:ext"}) == (EXT, {"x": 0, "y": 0})


def test_passe_muraille_depose_de_l_autre_cote_du_mur(monkeypatch):
	assert _deplacer(monkeypatch, {"link": "link:ext", "passe_muraille": True}) == (CITE, {"x": 62, "y": 26})


def test_passe_muraille_n_ouvre_pas_une_porte_gardee(monkeypatch):
	from fastapi import HTTPException
	ferme = dict(_porte(INT), ferme=True)
	with pytest.raises(HTTPException) as e:
		_deplacer(monkeypatch, {"link": "link:ext", "passe_muraille": True}, {INT: ferme})
	assert e.value.status_code == 403

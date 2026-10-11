"""Tests de la chronologie du lore (`utils/chronologie.py`) : grammaire des bornes, temps
normalisé, validation, payload — et fumée sur la vraie source `docs/lore/chronologie.json`."""

import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import chronologie as chrono, lore  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ères de test (indépendantes du contenu réel) : ordinale, deux passées contiguës, jeu, futur.
ERES = [
	{"id": "anc", "libelle": "Ancien", "type": "ordinal", "rangs": [{"id": "r0", "libelle": "Âge 0"}, {"id": "r1", "libelle": "Âge 1"}]},
	{"id": "p1", "libelle": "Passé 1", "type": "passe", "debut": 1000, "fin": 500},
	{"id": "p2", "libelle": "Passé 2", "type": "passe", "debut": 500, "fin": 0},
	{"id": "jeu", "libelle": "Jeu", "type": "ordinal", "rangs": [{"id": "D", "libelle": "D"}, {"id": "C", "libelle": "C"}]},
	{"id": "fut", "libelle": "Futur", "type": "futur", "debut": 0, "fin": 200},
]
E = chrono._Eres(ERES)


def _source(*evenements):
	return {"eres": copy.deepcopy(ERES), "origines": {"monde": "Monde", "italie": "Italie"},
			"vocabulaire": {"lieux": {"rome": "Rome"}}, "evenements": list(evenements)}


def _ev(eid="a", quand=None, **extra):
	ev = {"id": eid, "titre": eid.upper(), "resume": "r", "quand": quand or {"moment": {"ere": "p2", "ans": 100}},
		  "couche": "histoire", "categorie": "evenement", "autorite": "auteur", "visibilite": "public",
		  "origine": ["monde"], "sources": [{"fichier": "README.md"}]}
	ev.update(extra)
	return ev


def _valide(data):
	return chrono.valider(data, chemin_de=lambda f: f if f == "README.md" else None)


# ── Temps normalisé ────────────────────────────────────────────────────────────

def test_temps_continu_entre_eres_passees_et_monotone():
	fin_p1 = chrono.intervalle({"ere": "p1", "ans": 500}, E)[0]
	debut_p2 = chrono.intervalle({"ere": "p2", "ans": 500}, E)[0]
	assert fin_p1 == debut_p2 == 2.0
	ts = [chrono.intervalle({"ere": "p1" if a > 500 else "p2", "ans": a}, E)[0] for a in (1000, 800, 501, 499, 1, 0)]
	assert ts == sorted(ts) and ts[0] == 1.0 and ts[-1] == 3.0


def test_genres_de_borne():
	assert chrono.intervalle({"ere": "p2", "ans": 250}, E) == (2.5, 2.5, "exact")
	lo, hi, g = chrono.intervalle({"ere": "p2", "entre": [600, 400]}, E)  # déborde sur p1 : permis
	assert g == "incertain" and lo < 2.0 < hi
	assert chrono.intervalle({"ere": "anc", "rang": "r1"}, E) == (0.5, 1.0, "rang")
	assert chrono.intervalle({"ere": "jeu", "entre_rangs": ["D", "C"]}, E) == (3.0, 4.0, "rang")
	assert chrono.intervalle({"ere": "anc", "inconnu": True}, E) == (0.0, 1.0, "inconnu")
	assert chrono.intervalle({"ere": "p2", "ouvert": True}, E, "a") == (3.0, 3.0, "ouvert")
	assert chrono.intervalle({"ere": "anc", "ouvert": True}, E, "de") == (0.0, 0.0, "ouvert")


def test_futur_dans_n_ans():
	assert chrono.intervalle({"ere": "fut", "dans": 50}, E) == (4.25, 4.25, "exact")
	assert chrono.intervalle({"ere": "fut", "entre_dans": [20, 100]}, E)[:2] == (4.1, 4.5)
	assert chrono.texte_borne({"ere": "fut", "entre_dans": [20, 100]}, E) == "? dans 20 à 100 ans"


def test_bornes_refusees():
	cas = [
		({"ere": "p2", "entre": [100, 400]}, "inversé"),
		({"ere": "fut", "entre_dans": [100, 20]}, "inversé"),
		({"ere": "p2", "ans": 100, "rang": "r0"}, "exactement une"),
		({"ere": "p2", "rang": "r0"}, "impossible"),
		({"ere": "fut", "ans": 10}, "impossible"),
		({"ere": "anc", "rang": "r9"}, "absent"),
		({"ere": "p2", "ans": 900}, "hors de l'ère déclarée"),
		({"ere": "p2", "ans": 5000}, "hors de toute ère"),
		({"ere": "zz", "ans": 1}, "ère inconnue"),
		({"ere": "p2", "inconnu": 1}, "true"),
	]
	for borne, attendu in cas:
		try:
			chrono.intervalle(borne, E)
		except ValueError as e:
			assert attendu in str(e), (borne, str(e))
		else:
			raise AssertionError(f"borne acceptée à tort : {borne}")
	try:
		chrono.intervalle({"ere": "p2", "ouvert": True}, E)  # `ouvert` hors d'une période
	except ValueError:
		pass
	else:
		raise AssertionError("`ouvert` accepté pour un instant")


def test_notation():
	n = chrono.notation
	assert n({"moment": {"ere": "p2", "ans": 100}}, E) == "il y a 100 ans"
	assert n({"moment": {"ere": "p1", "entre": [1000, 900]}}, E) == "? entre 1 000 et 900 ans avant l'ère actuelle"
	assert n({"moment": {"ere": "jeu", "rang": "D"}}, E) == "rang D"
	assert n({"de": {"ere": "anc", "rang": "r0"}, "a": {"ere": "p2", "ouvert": True}}, E) == "de Âge 0 à jusqu'à aujourd'hui"
	assert n({"moment": {"ere": "anc", "inconnu": True}}, E).startswith("? à un moment inconnu")


# ── Validation ─────────────────────────────────────────────────────────────────

def test_source_saine():
	assert _valide(_source(_ev("a"), _ev("b", apres=["a"], liens=["a"], tags={"lieux": ["rome"]}))) == []


def test_erreurs_detectees():
	periode_inversee = {"de": {"ere": "p2", "ans": 10}, "a": {"ere": "p1", "ans": 900}}
	data = _source(
		_ev("a"),
		_ev("a"),                                                      # doublon
		_ev("b", quand=periode_inversee),
		_ev("c", tags={"lieux": ["mars"]}, sources=[{"fichier": "../secret"}]),
		_ev("d", liens=["fantome"], couche="ailleurs"),
		_ev("e", quand={"moment": {"ere": "p1", "ans": 900}}, apres=["a"]),  # 900 ans < « après » 100 ans
		_ev("f", quand={"moment": {"ere": "p2", "ans": 1}, "de": {"ere": "p2", "ans": 1}}),
		_ev("g", origine=["atlantide"]),
		_ev("h", origine=[]),
	)
	msgs = "\n".join(_valide(data))
	for attendu in ("a : id en double", "b : date : `de` postérieur à `a`", "c : tag lieux:'mars'",
					"c : source hors du lore", "d : `liens` vers un id inconnu", "d : `couche` 'ailleurs'",
					"e : déclaré après 'a' mais daté avant lui", "f : date : `quand` = moment OU de/a",
					"g : origine 'atlantide' absente", "h : `origine` manquante"):
		assert attendu in msgs, (attendu, msgs)


def test_apres_tolere_le_chevauchement_des_incertitudes():
	a = _ev("a", quand={"moment": {"ere": "p1", "entre": [900, 600]}})
	b = _ev("b", quand={"moment": {"ere": "p1", "entre": [900, 550]}}, apres=["a"])
	assert _valide(_source(a, b)) == []


# ── Payload ────────────────────────────────────────────────────────────────────

def test_payload_brut_intact_et_calculs():
	ev = _ev("a", quand={"de": {"ere": "anc", "rang": "r1"}, "a": {"ere": "p2", "ouvert": True}},
			 jalons=[{"libelle": "avènement", "borne": {"ere": "p1", "ans": 800}}], tags={"lieux": ["rome"]})
	data = _source(ev)
	p = chrono.payload(data, chemin_de=lambda f: f)
	(e,) = p["evenements"]
	assert e["brut"] == ev and list(e["brut"]) == list(ev)          # ordre des clés de la source
	assert e["calc"]["forme"] == "periode" and e["calc"]["fin"]["genre"] == "ouvert"
	assert e["eres"] == ["anc", "p1", "p2"]
	assert e["calc"]["jalons"][0]["notation"] == "il y a 800 ans"
	assert e["sources"][0]["url"] == lore.URL_LORE + "README.md"
	rome = next(v for v in p["facettes"]["lieux"] if v["id"] == "rome")
	assert rome["n"] == 1
	assert e["origine"] == ["monde"]
	assert {v["id"]: v["n"] for v in p["facettes"]["origine"]} == {"monde": 1, "italie": 0}
	assert "evenements" not in p["entete"] and p["entete"]["eres"] == data["eres"]


def test_payload_garde_les_erreurs_par_element():
	data = _source(_ev("a", tags={"lieux": ["mars"]}))
	(e,) = chrono.payload(data, chemin_de=lambda f: f)["evenements"]
	assert any("mars" in m for m in e["erreurs"])


# ── Vraie source ───────────────────────────────────────────────────────────────

def test_vraie_source_valide():
	assert chrono.valider(chrono.charger()) == []


def test_citations_presentes_dans_leur_source():
	"""Chaque citation se retrouve dans le fichier cité (espaces et emphases ignorés)."""
	norm = lambda s: re.sub(r"\s+", " ", s.replace("*", "")).strip().lower()  # noqa: E731
	for ev in chrono.charger()["evenements"]:
		for s in ev["sources"]:
			if not s.get("citation"):
				continue
			chemin = lore.chemin_de(s["fichier"])
			with open(os.path.join(RACINE, "docs", chemin), encoding="utf-8") as f:
				assert norm(s["citation"]) in norm(f.read()), (ev["id"], s["fichier"], s["citation"])


def test_vraie_source_payload_complet():
	data = chrono.charger()
	p = chrono.payload(data)
	assert len(p["evenements"]) == len(data["evenements"])
	for e in p["evenements"]:
		assert e["calc"]["debut"]["t"][0] <= e["calc"]["fin"]["t"][1]


def test_json_hors_de_l_index_du_lore():
	assert all(not e["chemin"].endswith(".json") for e in lore.lister())


def test_route_declaree_avant_le_fourre_tout():
	with open(os.path.join(RACINE, "main.py"), encoding="utf-8") as f:
		src = f.read()
	assert src.index('"/admin/lore/chronologie"') < src.index('"/admin/lore/{cle:path}"')

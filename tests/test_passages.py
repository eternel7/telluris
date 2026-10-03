# tests/test_passages.py
# Condition `passages` : nombre d'ENTRÉES dans un lieu, compté au tirage de présence
# (`pnj.poser_pnj_present`), lu par les DEUX vocabulaires — présence d'un PNJ / barrière de
# lieu (`acces.clauses_remplies`) et choix de dialogue (`pnj.condition_ok`) — via UN
# prédicat partagé (`pnj.passages_ok`). Contenu : Élise au Coq de Lutèce.

import json
import os

import pytest

from utils import acces, lint_dialogues, pnj

COQ = "lieu:le_coq_de_lutece"
CONTENU = os.path.join(os.path.dirname(__file__), "..", "jsons", "pnj_elise_herboriste_a_importer.json")


def _lieu(_id=COQ, entrees=None):
	return {"_id": _id, "type": "lieu", "pnj": entrees or []}


def _jamais(*_):
	return 0.0  # tout PNJ de probabilité > 0 passe le jet


# ── Le compteur ─────────────────────────────────────────────────────────────

def test_une_entree_compte_un_passage_et_un_refresh_ne_compte_rien():
	c = {}
	assert pnj.poser_pnj_present(c, _lieu(), rand_fn=_jamais)
	assert c["passages"] == {COQ: 1}
	assert not pnj.poser_pnj_present(c, _lieu(), rand_fn=_jamais)   # refresh
	assert c["passages"] == {COQ: 1}


def test_ressortir_puis_rentrer_compte_un_passage_de_plus():
	c = {}
	pnj.poser_pnj_present(c, _lieu(), rand_fn=_jamais)
	pnj.poser_pnj_present(c, _lieu("lieu:lutecia"), rand_fn=_jamais)
	pnj.poser_pnj_present(c, _lieu(), rand_fn=_jamais)
	assert c["passages"] == {COQ: 2, "lieu:lutecia": 1}


def test_le_passage_est_compte_AVANT_le_tirage():
	"""Les conditions de présence voient le passage EN COURS : 1 dès la première entrée."""
	entree = {"character": "pnj:x", "probabilite": 1,
			  "conditions": [{"passages": {"lieu": COQ, "min": 1, "max": 1}}]}
	c = {}
	cond = lambda conds: acces.clauses_remplies(c, conds, lambda _id: None)
	pnj.poser_pnj_present(c, _lieu(entrees=[entree]), rand_fn=_jamais, condition_fn=cond)
	assert c["pnj_present"]["characters"] == ["pnj:x"]


def test_champ_absent_ou_illisible_vaut_zero():
	assert pnj.passages_ok(None, {"lieu": COQ, "max": 0})
	assert pnj.passages_ok({COQ: "3"}, {"lieu": COQ, "max": 0})
	c = {"passages": {COQ: True}}
	assert pnj.compter_passage(c, COQ) == 1


# ── Le prédicat ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n, filtre, attendu", [
	(1, {"lieu": COQ, "max": 1}, True),
	(2, {"lieu": COQ, "max": 1}, False),
	(2, {"lieu": COQ, "min": 2, "max": 2}, True),
	(3, {"lieu": COQ, "min": 2, "max": 2}, False),
	(9, {"lieu": COQ, "min": 6}, True),
	(5, {"lieu": COQ, "min": 6}, False),
])
def test_bornes_incluses(n, filtre, attendu):
	assert pnj.passages_ok({COQ: n}, filtre) is attendu


@pytest.mark.parametrize("filtre", [
	None, [], {"lieu": COQ}, {"max": 3}, {"lieu": COQ, "max": "3"}, {"lieu": COQ, "max": True},
	{"lieu": COQ, "max": 3, "maxi": 4}, {"lieu": 3, "max": 3},
])
def test_FAIL_CLOSED_sur_un_filtre_fautif(filtre):
	assert pnj.passages_ok({COQ: 1}, filtre) is False


def test_meme_reponse_dans_les_deux_vocabulaires():
	for n in range(0, 8):
		c = {"passages": {COQ: n}}
		ctx = pnj.contexte_dialogue(c, {}, lambda _l: 0)
		for f in ({"lieu": COQ, "max": 4}, {"lieu": COQ, "min": 5}, {"lieu": COQ, "min": 3, "max": 3}):
			assert pnj.condition_ok({"passages": f}, ctx) \
				== acces.clauses_remplies(c, [{"passages": f}], lambda _id: None) \
				== pnj.passages_ok(c["passages"], f)


def test_vocabulaire_servi_aux_editeurs():
	voc = acces.vocabulaire_conditions()
	assert "passages" in voc["cles"]
	assert set(voc["sous_filtres"]["passages"]) == set(pnj.PASSAGES_CLES)
	assert acces.conditions_pnj_invalides(
		_lieu(entrees=[{"character": "pnj:x", "conditions": [{"passages": {"lieu": COQ, "maxi": 1}}]}])
	) == ["pnj[0].conditions.passages.maxi"]


def test_linter_signale_un_filtre_toujours_faux():
	assert lint_dialogues.fautes_passages({"lieu": COQ, "max": 2}) == []
	assert lint_dialogues.fautes_passages({"lieu": COQ})
	assert lint_dialogues.fautes_passages({"lieu": COQ, "min": 3, "max": 2})
	assert lint_dialogues.fautes_passages({"lieu": "coq", "max": 2})
	assert lint_dialogues.fautes_passages({"lieu": COQ, "max": "2"})


# ── Contenu : Élise, puis l'aubergiste ──────────────────────────────────────

def _contenu():
	with open(CONTENU, encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)}


def _presents_au_passage(n):
	"""Qui est là, et quelle scène s'offre, au n-ième passage au Coq."""
	docs = _contenu()
	c = {"passages": {COQ: n - 1}}
	cond = lambda conds: acces.clauses_remplies(c, conds, lambda _id: None)
	pnj.poser_pnj_present(c, docs[COQ], rand_fn=_jamais, condition_fn=cond)
	assert c["passages"][COQ] == n
	scenes = {}
	for pid in c["pnj_present"]["characters"]:
		ctx = pnj.contexte_dialogue(c, docs[pid], lambda _l: 0)
		vue = pnj.noeud_client(docs[pid], "accueil", ctx)
		scenes[pid] = [ch["id"] for ch in vue["choix"] if ch["id"] not in ("fin", "soin")]
	return scenes


@pytest.mark.parametrize("n, attendu", [
	(1, {"pnj:elise_herboriste": ["s1"]}),
	# À partir du 2ᵉ passage, les scènes passées restent ouvertes (une scène manquée se
	# rattrape), la plus récente EN TÊTE ; la première rencontre, elle, ne se rejoue pas.
	(2, {"pnj:elise_herboriste": ["s2"]}),
	(3, {"pnj:elise_herboriste": ["s3", "s2"]}),
	(4, {"pnj:elise_herboriste": ["s4", "s3", "s2"]}),
	(5, {"pnj:aubergiste_du_coq_de_lutece": ["absente"]}),
	(6, {"pnj:aubergiste_du_coq_de_lutece": ["retrouvee"]}),
	(12, {"pnj:aubergiste_du_coq_de_lutece": ["retrouvee"]}),
])
def test_une_scene_par_passage(n, attendu):
	assert _presents_au_passage(n) == attendu


def test_scenes_ouvertes_ensemble_ont_des_libelles_distincts():
	"""Deux libellés identiques côte à côte rendraient le menu illisible."""
	accueil = _contenu()["pnj:elise_herboriste"]["dialogue"]["noeuds"]["accueil"]
	labels = [c["label"] for c in accueil["choix"]]
	assert len(labels) == len(set(labels))


def test_le_contenu_passe_le_linter():
	with open(CONTENU, encoding="utf-8") as f:
		rapport = lint_dialogues.analyser(json.load(f))
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]

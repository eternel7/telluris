# tests/test_pistage_contenu.py
#
# Contenu de dev/gen_pistage.py : la passive « Lecture des traces » (forestier, niveau 0)
# passe les gardes des compétences, pose `pistage` dans l'agrégat des passives, et c'est
# CETTE clé — non plus la vocation — qui fait un pisteur (utils/traces.pisteur).

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_pistage as gen  # noqa: E402
import check_competences_doc as check  # noqa: E402
from utils import competences as competences_util, traces  # noqa: E402
from utils.competences import normaliser_competence  # noqa: E402

DOCS = gen.docs_pistage()
DOC = DOCS[0]


def test_passive_de_forestier_des_le_niveau_0():
	# Décision de l'Auteur (11/11) : obtenable dès le niveau 0 — constante voulue.
	assert (DOC["vocation"], DOC["niveau"], DOC["mode"]) == ("forestier", 0, "passive")


def test_gardes_des_competences():
	assert check.verifier_competence(DOC, DOC["_id"], niveaux=None) == []
	assert normaliser_competence(DOC)["effets"]["pistage"] == 1


def test_le_delta_ne_reprend_pas_un_doc_deja_identique_en_base():
	base = {DOC["_id"]: dict(DOC, _rev="1-x"),
			"competence:autre": {"type": "competence", "vocation": "forestier", "nom": "Autre"}}
	assert gen.delta(base) == []
	base.pop(DOC["_id"])
	assert [d["_id"] for d in gen.delta(base)] == [DOC["_id"]]


def test_la_passive_apprise_fait_un_pisteur_quelle_que_soit_la_vocation():
	docs = {d["_id"]: d for d in DOCS}
	perso = {"voc": "templier", "nom": "Ex", "competences_connues": [DOC["_id"]]}
	competences_util.recompute_competences_bonus(perso, docs.get)
	assert perso["competences_bonus"]["pistage"] == 1
	assert traces.pisteur([perso]) is perso


def test_sans_la_passive_aucune_cle_posee():
	# Clé posée seulement si acquise : sinon tout agrégat en base différerait de son recalcul.
	assert "pistage" not in competences_util.bonus_passifs({"competences_connues": []}, {}.get)

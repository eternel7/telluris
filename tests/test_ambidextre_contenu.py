# tests/test_ambidextre_contenu.py
#
# Contenu de dev/gen_ambidextre.py : une passive « Ambidextre » par vocation retenue,
# niveaux de l'Auteur, gardes de check_competences_doc, et effet réel en combat (la passive
# lève le malus de seconde arme, `combat.coups_du_profil`).

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_ambidextre as gen  # noqa: E402
import check_competences_doc as check  # noqa: E402
from utils import competences as competences_util  # noqa: E402
from utils.competences import normaliser_competence  # noqa: E402

DOCS = gen.docs_ambidextre()


def test_niveaux_retenus_par_l_auteur():
	# Décision de l'Auteur (11/11) — constante voulue.
	assert {d["vocation"]: d["niveau"] for d in DOCS} == {
		"assassin": 2, "duelliste": 3, "voleur": 6, "barbare": 6, "guerrier": 8}


def test_un_doc_par_vocation_ids_uniques():
	ids = [d["_id"] for d in DOCS]
	assert len(ids) == len(set(ids)) == len(gen.AMBIDEXTRES)
	assert all(d["nom"] == gen.NOM and d["mode"] == "passive" for d in DOCS)


@pytest.mark.parametrize("doc", DOCS, ids=lambda d: d["_id"])
def test_gardes_des_competences(doc):
	assert check.verifier_competence(doc, doc["_id"], niveaux=None) == []
	assert normaliser_competence(doc)["effets"]["ambidextre"] == 1


def test_le_delta_ne_reprend_pas_un_doc_deja_identique_en_base():
	base = {d["_id"]: dict(d, _rev="1-x") for d in DOCS}
	for voc in gen.AMBIDEXTRES:   # vocations connues du « dump »
		base[f"competence:autre_{voc}"] = {"type": "competence", "vocation": voc}
	assert gen.delta(base) == []
	base.pop(DOCS[0]["_id"])
	assert [d["_id"] for d in gen.delta(base)] == [DOCS[0]["_id"]]


def test_hors_de_la_regle_2_plus_5_du_generateur_1_10():
	"""Option (a) de l'Auteur : en SUS du compte par niveau — déclarées hors compte."""
	import gen_competences_1_10
	assert gen_competences_1_10.HORS_COMPTE == {d["_id"] for d in DOCS}


def test_la_passive_apprise_pose_l_ambidextrie():
	perso = {"competences_connues": [d["_id"] for d in DOCS[:1]]}
	docs = {d["_id"]: d for d in DOCS}
	assert competences_util.bonus_passifs(perso, docs.get)["ambidextre"] == 1

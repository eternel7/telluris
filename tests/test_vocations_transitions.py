# tests/test_vocations_transitions.py
#
# Contenu de dev/gen_vocations_transitions.py (`rules:vocations_transitions`, repris de la page
# d'accueil) : ids cohérents, pas de boucle, et le contrôle attrape une vocation inconnue.

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_vocations_transitions as gen  # noqa: E402
from utils import vocations  # noqa: E402

IDS = set(gen.TRANSITIONS)


def test_graphe_coherent_avec_lui_meme():
	assert gen.erreurs(IDS) == []
	assert all(c in IDS for cibles in gen.TRANSITIONS.values() for c in cibles)


def test_le_controle_attrape_une_vocation_inconnue_ou_sans_entree():
	assert any("absente" in e for e in gen.erreurs(IDS - {"mage"}))
	assert any("sans entrée" in e for e in gen.erreurs(IDS | {"inconnue"}))


def test_doc_lu_par_le_moteur():
	doc = gen.doc_transitions()
	assert doc["_id"] == vocations.TRANSITIONS_DOC_ID
	assert vocations.transitions_de("guerrier", doc) == gen.TRANSITIONS["guerrier"]


def test_delta_vide_quand_le_doc_est_deja_en_base():
	base = {"rules:vocations": {"value": [{"id": i} for i in IDS]},
			vocations.TRANSITIONS_DOC_ID: dict(gen.doc_transitions(), _rev="1-x")}
	assert gen.delta(base) == []
	base.pop(vocations.TRANSITIONS_DOC_ID)
	assert [d["_id"] for d in gen.delta(base)] == [vocations.TRANSITIONS_DOC_ID]

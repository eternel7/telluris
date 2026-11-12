"""`dev/gen_echanges_cite.py` — n'AJOUTE à `rules:proprietes` que ce qui manque.

Verrouille : l'ajout des métiers et aménagements, les `effets_poste` complétés clé à clé, les
réglages relus dans le MOTEUR (jamais recopiés), le retrait de `vente_auto`, l'idempotence, et
que chaque nouvel aménagement a un texte d'effet. Doc en mémoire (aucun fichier de `jsons/`)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_echanges_cite as gen  # noqa: E402

from utils import echanges_cite  # noqa: E402
from utils import proprietes  # noqa: E402


def _dump():
	ams = [{"id": i, "nom": i, "types_autorises": ["maison"], "capacite": {"postes": {"marchand": 1}},
			"effets_poste": {"deja": 1} if i == "jardin" else {}}
		   for i in gen.EFFETS_POSTE]
	return [{"_id": gen.DOC_ID, "_rev": "1-x", "type": "rules", "value": {
		"types": [], "amenagements": ams,
		"metiers": [{"id": "marchand", "label": "Marchand"}],
		"reglages": {"candidats_duree_s": 10, "vente_auto": {"proba": 0.5}}}}]


def test_ajoute_ce_qui_manque_et_relit_les_reglages_du_moteur():
	doc, changes = gen.generer(_dump())
	val = doc["value"]
	assert "_rev" not in doc and changes
	assert {m["id"] for m in gen.METIERS} <= {m["id"] for m in val["metiers"]}
	assert {a["id"] for a in gen.AMENAGEMENTS} <= {a["id"] for a in val["amenagements"]}
	jardin = next(a for a in val["amenagements"] if a["id"] == "jardin")
	assert jardin["effets_poste"] == {"deja": 1, "autoproduction": True}      # complété, rien retiré
	assert val["reglages"]["echanges"] == echanges_cite.ECHANGES_DEFAUT
	assert val["reglages"]["negociant"] == echanges_cite.NEGOCIANT_DEFAUT
	assert "vente_auto" not in val["reglages"] and val["reglages"]["candidats_duree_s"] == 10


def test_idempotent():
	doc, _ = gen.generer(_dump())
	doc["_rev"] = "2-y"
	_doc2, changes = gen.generer([json.loads(json.dumps(doc))])
	assert changes == []


def test_chaque_nouvel_amenagement_dit_son_effet():
	doc, _ = gen.generer(_dump())
	cat = doc["value"]
	for a in gen.AMENAGEMENTS:
		textes = proprietes.textes_effets(a, cat)
		assert any("avec un(e)" in t for t in textes), a["id"]

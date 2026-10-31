# tests/test_guildes_pnj.py
# Réceptionnistes et maîtres des maisons de guilde (dev/gen_guildes_pnj.py), contre un dump minimal.

from dev import gen_guildes_pnj as gen
from utils import lint_dialogues


def _dump():
	docs = {}
	for m in gen.MAISONS:
		cite, guilde = m[0], m[1]
		docs[f"lieu:{cite}"] = {"_id": f"lieu:{cite}", "label": cite,
								"sous_categorie": "capitale" if cite == "rome" else None}
		docs[f"lieu:{guilde}_comptoir"] = {"_id": f"lieu:{guilde}_comptoir", "type": "lieu", "_rev": "1-a"}
		docs[f"lieu:{guilde}_bureau_du_maitre"] = {
			"_id": f"lieu:{guilde}_bureau_du_maitre", "type": "lieu", "_rev": "1-a", "label": "X - bureau du maître",
			"acces": {"cycle": 1, "conditions": [{"rang_min": {"cite": f"lieu:{cite}", "rang": "D"}}]}}
	return docs


def test_chaque_maison_recoit_ses_deux_pnj_et_seule_une_capitale_monte_a_s_plus():
	sortie = {d["_id"]: d for d in gen.construire(_dump(), {})}
	for m in gen.MAISONS:
		comptoir = sortie[f"lieu:{m[1]}_comptoir"]
		bureau = sortie[f"lieu:{m[1]}_bureau_du_maitre"]
		assert "_rev" not in comptoir
		assert comptoir["pnj"][0]["character"] == f"pnj:{m[5][0]}"
		assert bureau["pnj"][0]["character"] == f"pnj:{m[6][0]}"
		assert bureau["acces"]["gardien"] == f"pnj:{m[5][0]}"
		assert bureau["acces"]["conditions"] == [{"rang_min": {"cite": f"lieu:{m[0]}", "rang": "D"}}]
		assert comptoir.get("rang_max") == ("S+" if m[0] == "rome" else None)


def test_les_ids_de_pnj_sont_uniques_et_les_dialogues_passent_le_linter():
	sortie = gen.construire(_dump(), {})
	pnj = [d for d in sortie if d["type"] == "pnj"]
	assert len({d["_id"] for d in pnj}) == 2 * len(gen.MAISONS)
	assert lint_dialogues.analyser(pnj)["erreurs"] == 0


def test_une_femme_et_un_homme_par_maison_jamais_deux_fois_la_meme_lignee():
	for m in gen.MAISONS:
		assert m[5][2] != m[6][2], m[0]
		assert m[5][3] != m[6][3], m[0]

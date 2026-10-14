"""Condition de dialogue `rang_min` : `{cite, rang}`, le MÊME comparateur fail-closed que la
barrière de lieu (`acces.rang_min_satisfait`) — et le contrôle du linter qui l'accompagne."""

from utils import lint_dialogues, pnj

COND = {"rang_min": {"cite": "lieu:auxerre", "rang": "E"}}


def _ctx(rangs=None, flags=None):
	return {"rangs_guilde": rangs or {}, "flags": flags or {}}


def test_rang_atteint_ou_depasse():
	assert pnj.condition_ok(COND, _ctx({"lieu:auxerre": "E"}))
	assert pnj.condition_ok(COND, _ctx({"lieu:auxerre": "A"}))


def test_rang_inferieur_ou_absent():
	assert not pnj.condition_ok(COND, _ctx({"lieu:auxerre": "F"}))
	# Rang absent ⇒ premier de l'échelle (F) : refusé.
	assert not pnj.condition_ok(COND, _ctx({}))


def test_le_rang_se_lit_par_cite():
	assert not pnj.condition_ok(COND, _ctx({"lieu:lutecia": "S"}))


def test_filtre_illisible_fail_closed():
	for filtre in ({"cite": "lieu:auxerre", "rang": "Z"}, {"rang": "E"}, {"cite": "lieu:auxerre"}, "E"):
		assert not pnj.condition_ok({"rang_min": filtre}, _ctx({"lieu:auxerre": "S"})), filtre


def test_se_combine_aux_flags():
	cond = dict(COND, apport_offert=True)
	assert not pnj.condition_ok(cond, _ctx({"lieu:auxerre": "E"}))
	assert pnj.condition_ok(cond, _ctx({"lieu:auxerre": "E"}, {"apport_offert": True}))


def test_contexte_dialogue_porte_les_rangs():
	ctx = pnj.contexte_dialogue({"rangs_guilde": {"lieu:auxerre": "D"}}, {}, lambda _l: 0)
	assert ctx["rangs_guilde"] == {"lieu:auxerre": "D"}


def test_condition_structuree_des_deux_cotes():
	assert "rang_min" in pnj.CONDITIONS_STRUCTUREES
	assert "rang_min" in lint_dialogues.CONDITIONS_STRUCTUREES


def _doc(filtre):
	return {"_id": "pnj:test", "type": "pnj", "dialogue": {"noeud_depart": "a", "noeuds": {
		"a": {"texte": "…", "choix": [
			{"id": "x", "label": "x", "condition": {"rang_min": filtre}, "next": "fin"},
			{"id": "fin", "label": "fin", "next": "fin"},
		]}}}}


def test_linter_accepte_un_filtre_bien_forme():
	rapport = lint_dialogues.analyser([_doc({"cite": "lieu:auxerre", "rang": "E"})])
	assert rapport["erreurs"] == 0, rapport["trouvailles"]


def test_linter_signale_un_filtre_fautif():
	for filtre in ({"cite": "auxerre", "rang": "E"}, {"cite": "lieu:auxerre", "rang": "Z"},
				   {"cite": "lieu:auxerre", "rang": "E", "rangs": "E"}, "E"):
		rapport = lint_dialogues.analyser([_doc(filtre)])
		assert rapport["erreurs"] >= 1, filtre

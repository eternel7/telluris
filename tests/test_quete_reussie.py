# tests/test_quete_reussie.py
# La condition de dialogue `quete_reussie` — tester une quête NOMMÉE depuis n'importe quel PNJ.
#
# ⚠️ Ce qu'elle apporte, et que rien ne savait faire : les flags existants
# (`escorte_accomplie`, `transport_accompli`) sont dérivés de l'offre portée par le PNJ à qui
# l'on PARLE (`escorte.offre_spec(pnj_doc)`), donc toujours faux chez un tiers. Deux paladins
# ne pouvaient pas réagir à une escorte confiée par le maître de guilde.

import pytest

from utils import pnj, quetes, escorte, transport
from utils import lint_dialogues


QID = "quete:escorte_bucherons_d_auxerre"


def _perso(terminees=None):
	return {"_id": "character:t", "prenom": "Test", "quetes_terminees": list(terminees or [])}


REUSSIE = _perso([{"id": QID, "titre": "Les bûcherons disparus"}])
ECHOUEE = _perso([{"id": QID, "titre": "Les bûcherons disparus", "echec": True}])
VIERGE = _perso()


# ── Le prédicat, source unique (utils/quetes.py) ────────────────────────────────

def test_quete_reussie_ne_compte_que_les_succes():
	assert quetes.quete_reussie(REUSSIE, QID) is True
	# ⚠️ Un ÉCHEC ne compte pas : le donneur repropose (c'est ce qui rend une offre `unique`
	# rejouable après un revers). Le dialogue doit donc rester dans son état « avant ».
	assert quetes.quete_reussie(ECHOUEE, QID) is False
	assert quetes.quete_reussie(VIERGE, QID) is False
	assert quetes.quete_reussie(REUSSIE, "quete:autre") is False
	assert quetes.quete_reussie(REUSSIE, "") is False
	assert quetes.quete_reussie(None, QID) is False


def test_quetes_reussies_rend_l_ensemble_des_ids():
	c = _perso([
		{"id": "quete:a"},
		{"id": "quete:b", "echec": True},
		{"id": "quete:c", "echec": False},
		{"titre": "archive sans id"},
	])
	assert quetes.quetes_reussies(c) == {"quete:a", "quete:c"}
	assert quetes.quetes_reussies(_perso()) == set()
	assert quetes.quetes_reussies(None) == set()


def test_les_deux_gates_de_unique_delegent_a_la_source_unique():
	"""`escorte.deja_reussie` et `transport.deja_reussie` étaient deux copies du même corps.
	Après délégation, leur comportement doit rester rigoureusement identique."""
	for character in (REUSSIE, ECHOUEE, VIERGE):
		attendu = quetes.quete_reussie(character, QID)
		assert escorte.deja_reussie(character, QID) is attendu
		assert transport.deja_reussie(character, QID) is attendu


# ── La condition de dialogue (utils/pnj.py) ─────────────────────────────────────

def _ctx(character):
	return pnj.contexte_dialogue(character, {}, lambda _l: 50,
								 quetes_reussies=quetes.quetes_reussies(character))


def test_la_condition_joue_dans_les_DEUX_sens():
	positive = {"quete_reussie": {"id": QID}}
	negative = {"quete_reussie": {"id": QID, "attendu": False}}

	assert pnj.condition_ok(positive, _ctx(REUSSIE)) is True
	assert pnj.condition_ok(negative, _ctx(REUSSIE)) is False

	assert pnj.condition_ok(positive, _ctx(VIERGE)) is False
	assert pnj.condition_ok(negative, _ctx(VIERGE)) is True

	# ⚠️ Une quête ÉCHOUÉE laisse le dialogue dans son état « avant » — le paladin ne parle
	# toujours pas de quelqu'un qu'on n'a pas ramené.
	assert pnj.condition_ok(positive, _ctx(ECHOUEE)) is False
	assert pnj.condition_ok(negative, _ctx(ECHOUEE)) is True


def test_attendu_absent_vaut_true():
	assert pnj.condition_ok({"quete_reussie": {"id": QID}}, _ctx(REUSSIE)) is True
	assert pnj.condition_ok({"quete_reussie": {"id": QID, "attendu": True}},
							_ctx(REUSSIE)) is True


def test_filtre_mal_forme_est_FAIL_CLOSED():
	"""Le choix est MASQUÉ, jamais affiché à tort : un choix qui apparaît trop tôt révèle
	l'intrigue, un choix masqué se voit. Le garde-fou est le linter, pas le moteur."""
	for filtre in ({}, {"attendu": False}, {"id": ""}, {"id": None}, {"id": 42},
				   "quete:x", None, []):
		assert pnj.condition_ok({"quete_reussie": filtre}, _ctx(REUSSIE)) is False
		assert pnj.condition_ok({"quete_reussie": filtre}, _ctx(VIERGE)) is False


def test_la_condition_se_combine_avec_les_autres_formes():
	"""`condition_ok` doit continuer d'appliquer les flags ET les autres formes structurées :
	`quete_reussie` ne doit pas court-circuiter la boucle."""
	ctx = pnj.contexte_dialogue(REUSSIE, {}, lambda _l: 50, flags={"acces_ouvert": True},
								quetes_reussies=quetes.quetes_reussies(REUSSIE))
	assert pnj.condition_ok({"quete_reussie": {"id": QID}, "acces_ouvert": True}, ctx) is True
	assert pnj.condition_ok({"quete_reussie": {"id": QID}, "acces_ouvert": False}, ctx) is False
	assert pnj.condition_ok({"quete_reussie": {"id": QID}, "flag_absent": True}, ctx) is False


def test_contexte_sans_quetes_reussies_reste_utilisable():
	"""Paramètre en dernier AVEC défaut : les appels positionnels existants (7 sites dans
	tests/test_transport.py) ne doivent pas casser, et l'absence vaut « rien de réussi »."""
	ctx = pnj.contexte_dialogue(REUSSIE, {}, lambda _l: 50)
	assert ctx["quetes_reussies"] == set()
	assert pnj.condition_ok({"quete_reussie": {"id": QID}}, ctx) is False


# ── Le linter (utils/lint_dialogues.py) ─────────────────────────────────────────

def test_les_deux_listes_de_conditions_structurees_sont_le_MEME_ensemble():
	"""⚠️ Une clé structurée oubliée côté linter serait signalée comme flag inconnu sur du
	contenu correct ; une clé de trop y laisserait passer une vraie faute."""
	assert set(pnj.CONDITIONS_STRUCTUREES) == set(lint_dialogues.CONDITIONS_STRUCTUREES)


def _doc_avec_condition(condition):
	return {
		"_id": "pnj:test", "type": "pnj", "nom": "Test",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Bonjour.",
					"choix": [
						{"id": "c", "label": "Un choix.", "next": "fin",
						 "condition": condition},
						{"id": "fin", "label": "Partir.", "next": "fin"},
					],
				},
			},
		},
	}


def _erreurs(condition):
	res = lint_dialogues.analyser([_doc_avec_condition(condition)])
	return [t["message"] for t in res["trouvailles"] if t["niveau"] == "erreur"]


def test_le_linter_accepte_une_condition_bien_formee():
	assert _erreurs({"quete_reussie": {"id": QID}}) == []
	assert _erreurs({"quete_reussie": {"id": QID, "attendu": False}}) == []


def test_le_linter_refuse_un_id_sans_prefixe_quete():
	"""C'est LA faute invisible en jeu : le choix reste caché pour toujours (ou s'affiche
	toujours, dans la forme `attendu: false`)."""
	assert _erreurs({"quete_reussie": {"id": "escorte_bucherons"}})
	assert _erreurs({"quete_reussie": {"id": ""}})
	assert _erreurs({"quete_reussie": "quete:x"})


def test_le_linter_refuse_une_SOUS_cle_inconnue():
	"""⚠️ Le contrôle qui compte : une sous-clé fautive est IGNORÉE par le moteur, donc la
	condition redevient positive et le choix s'affiche à tort — sans aucun symptôme."""
	assert _erreurs({"quete_reussie": {"id": QID, "attendus": False}})
	assert _erreurs({"quete_reussie": {"id": QID, "attendu": "false"}})

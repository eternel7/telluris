# tests/test_quete_active.py
# La condition de dialogue `quete_active` — jumelle de `quete_reussie`, pour l'état EN COURS.
#
# ⚠️ Ce qu'elle apporte, et que rien ne savait faire : `quete_reussie` ne bascule qu'au
# turn-in, si bien qu'un PNJ qui ANNONCE une mission continuait de l'annoncer pendant toute
# sa durée — Borin répétait « le maître de la guilde vous cherche » alors que le joueur avait
# déjà le contrat en poche. Les flags existants (`escorte_en_cours`, `transport_en_cours`)
# n'y pouvaient rien : ils sont dérivés de l'offre portée par le PNJ à qui l'on PARLE, donc
# toujours faux chez un tiers — et ici c'est Gautier qui confie, pas Borin.
#
# ⚠️ Les deux conditions sont COMPLÉMENTAIRES, jamais contraires : une quête jamais acceptée
# est absente des DEUX ensembles. C'est leur CONJONCTION en `attendu: false` qui exprime
# « tant qu'on ne m'a pas encore confié ceci ».

from utils import pnj, quetes
from utils import lint_dialogues


QID = "quete:escorte_bucherons_d_auxerre"


def _perso(actives=None, terminees=None):
	return {
		"_id": "character:t", "prenom": "Test",
		"quetes_actives": list(actives or []),
		"quetes_terminees": list(terminees or []),
	}


VIERGE = _perso()
ACCEPTEE = _perso(actives=[{"id": QID, "titre": "Les bûcherons disparus"}])
# ⚠️ Objectif atteint mais pas encore rapporté : la quête est TOUJOURS dans `quetes_actives`
# (elle n'en sort qu'au turn-in — c'est exactement ce que suppose `objectif_atteint: false`
# côté barrières d'accès). Le PNJ qui annonce doit donc rester muet ici aussi.
REMPLIE = _perso(actives=[{"id": QID, "progress": 4, "objectif": {"quantite": 4}}])
RENDUE = _perso(terminees=[{"id": QID}])
ECHOUEE = _perso(terminees=[{"id": QID, "echec": True}])


# ── Le prédicat, source unique (utils/quetes.py) ────────────────────────────────

def test_quetes_actives_ids_rend_l_ensemble_des_ids():
	c = _perso(actives=[{"id": "quete:a"}, {"id": "quete:b"}, {"titre": "sans id"}])
	assert quetes.quetes_actives_ids(c) == {"quete:a", "quete:b"}
	assert quetes.quetes_actives_ids(VIERGE) == set()
	assert quetes.quetes_actives_ids(None) == set()


def test_une_quete_REMPLIE_mais_non_rendue_reste_active():
	"""⚠️ Le point qui fait toute l'utilité de la condition : une quête accomplie ne quitte
	`quetes_actives` qu'au turn-in. Un PNJ qui annonce se tait dès l'ACCEPTATION."""
	assert quetes.quetes_actives_ids(REMPLIE) == {QID}
	assert quetes.quetes_reussies(REMPLIE) == set()


def test_une_quete_rendue_quitte_les_actives_et_entre_dans_les_reussies():
	assert quetes.quetes_actives_ids(RENDUE) == set()
	assert quetes.quetes_reussies(RENDUE) == {QID}


# ── La condition dans le moteur de dialogue ────────────────────────────────────

def _ctx(character, **flags):
	return pnj.contexte_dialogue(
		character, {}, lambda _l: 50, flags=flags,
		quetes_reussies=quetes.quetes_reussies(character),
		quetes_actives=quetes.quetes_actives_ids(character))


def test_la_condition_suit_l_etat_de_la_quete():
	assert pnj.condition_ok({"quete_active": {"id": QID}}, _ctx(ACCEPTEE)) is True
	assert pnj.condition_ok({"quete_active": {"id": QID}}, _ctx(REMPLIE)) is True
	assert pnj.condition_ok({"quete_active": {"id": QID}}, _ctx(VIERGE)) is False
	assert pnj.condition_ok({"quete_active": {"id": QID}}, _ctx(RENDUE)) is False


def test_attendu_false_est_la_seule_negation_disponible():
	f = {"id": QID, "attendu": False}
	assert pnj.condition_ok({"quete_active": f}, _ctx(VIERGE)) is True
	assert pnj.condition_ok({"quete_active": f}, _ctx(ACCEPTEE)) is False


def test_LA_CONJONCTION_dit_tant_qu_on_ne_m_a_pas_confie_ceci():
	"""Le cas d'usage qui a fait naître la condition (Borin, Bastion de l'Yonne) : le choix
	« le maître de la guilde vous cherche » ne doit s'afficher qu'AVANT l'acceptation.

	⚠️ Aucune des deux conditions ne suffit seule — c'est le cœur du sujet :
	  • `quete_reussie: false` seul laisserait le choix visible pendant TOUTE la mission ;
	  • `quete_active: false` seul le laisserait REVENIR une fois la mission rendue."""
	cond = {"quete_active": {"id": QID, "attendu": False},
			"quete_reussie": {"id": QID, "attendu": False}}
	assert pnj.condition_ok(cond, _ctx(VIERGE)) is True       # rien de confié : Borin parle
	assert pnj.condition_ok(cond, _ctx(ACCEPTEE)) is False    # contrat en poche : il se tait
	assert pnj.condition_ok(cond, _ctx(REMPLIE)) is False     # bûcherons retrouvés : muet
	assert pnj.condition_ok(cond, _ctx(RENDUE)) is False      # mission rendue : muet
	# ⚠️ Un ÉCHEC rouvre le sujet, et c'est cohérent : `deja_reussie` ignore les archives en
	# échec, donc le donneur repropose l'offre `unique` — Borin doit pouvoir y renvoyer.
	assert pnj.condition_ok(cond, _ctx(ECHOUEE)) is True


def test_les_deux_conditions_ne_se_court_circuitent_pas():
	ctx = _ctx(ACCEPTEE, acces_ouvert=True)
	assert pnj.condition_ok(
		{"quete_active": {"id": QID}, "quete_reussie": {"id": QID}}, ctx) is False
	assert pnj.condition_ok({"quete_active": {"id": QID}, "acces_ouvert": True}, ctx) is True
	assert pnj.condition_ok({"quete_active": {"id": QID}, "acces_ouvert": False}, ctx) is False
	assert pnj.condition_ok({"quete_active": {"id": QID}, "flag_absent": True}, ctx) is False


def test_la_condition_est_FAIL_CLOSED():
	"""Même arbitrage que `quete_reussie` : un filtre mal formé MASQUE le choix. Un choix qui
	s'afficherait à tort révélerait l'intrigue ; un choix masqué se voit."""
	for filtre in (None, "quete:x", 42, [], {}, {"attendu": True}, {"id": ""}, {"id": 7}):
		assert pnj.condition_ok({"quete_active": filtre}, _ctx(ACCEPTEE)) is False
		assert pnj.condition_ok({"quete_active": filtre}, _ctx(VIERGE)) is False


def test_contexte_sans_quetes_actives_reste_utilisable():
	"""Paramètre en DERNIER avec défaut : les appels positionnels existants ne cassent pas,
	et l'absence vaut « rien en cours »."""
	ctx = pnj.contexte_dialogue(ACCEPTEE, {}, lambda _l: 50)
	assert ctx["quetes_actives"] == set()
	assert pnj.condition_ok({"quete_active": {"id": QID}}, ctx) is False


# ── Le linter (utils/lint_dialogues.py) ─────────────────────────────────────────

def test_les_deux_listes_de_conditions_de_quete_sont_le_MEME_ensemble():
	"""⚠️ Miroir exact, comme `CONDITIONS_STRUCTUREES` : une condition oubliée côté linter
	échapperait au contrôle des sous-clés, le seul qui attrape la faute invisible."""
	assert set(pnj.CONDITIONS_QUETE) == set(lint_dialogues.CONDITIONS_QUETE)
	assert set(lint_dialogues.CONDITIONS_QUETE) <= set(lint_dialogues.CONDITIONS_STRUCTUREES)


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
	assert _erreurs({"quete_active": {"id": QID}}) == []
	assert _erreurs({"quete_active": {"id": QID, "attendu": False}}) == []
	# Les deux ensemble : la forme réellement utilisée par Borin.
	assert _erreurs({"quete_active": {"id": QID, "attendu": False},
					 "quete_reussie": {"id": QID, "attendu": False}}) == []


def test_le_linter_refuse_un_id_sans_prefixe_quete():
	assert _erreurs({"quete_active": {"id": "escorte_bucherons"}})
	assert _erreurs({"quete_active": {"id": ""}})
	assert _erreurs({"quete_active": "quete:x"})


def test_le_linter_refuse_une_SOUS_cle_inconnue():
	"""⚠️ Le contrôle qui compte : une sous-clé fautive est IGNORÉE par le moteur, donc la
	condition redevient positive et le choix s'affiche à tort — sans aucun symptôme."""
	assert _erreurs({"quete_active": {"id": QID, "attendus": False}})
	assert _erreurs({"quete_active": {"id": QID, "attendu": "false"}})


def test_le_linter_signale_les_DEUX_conditions_d_un_meme_choix():
	"""Une seule des deux mal écrite doit suffire à lever une erreur : le contrôle boucle sur
	l'ensemble, il ne s'arrête pas à la première trouvée."""
	msgs = _erreurs({"quete_active": {"id": QID, "attendus": False},
					 "quete_reussie": {"id": "pas_un_id"}})
	assert any("quete_active" in m for m in msgs)
	assert any("quete_reussie" in m for m in msgs)

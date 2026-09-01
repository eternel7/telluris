# tests/test_indicateurs.py
#
# Marques « ! » / « ? » (utils/indicateurs.py + utils/pnj.py). Tests PURS : `marques_lieux`
# ne doit toucher AUCUN document — c'est ce qui autorise à la republier partout sans le
# moindre arbitrage de coût (contrairement à `relations_lieux`, cf. Conventions §10).
#
# Le fil rouge de ce fichier est l'EXCLUSIVITÉ : une course est « à livrer » OU « à
# rapporter », une escorte est « à retrouver » OU « à déposer » — jamais les deux, sinon le
# joueur irait déposer quelqu'un qu'il n'a pas encore rencontré.

import pytest

from models import character_stats
from utils import indicateurs, lint_dialogues
from utils import pnj as pnj_util


# ── Fabriques ────────────────────────────────────────────────────────────────────

def personnage(*quetes):
	return {"_id": "character:test", "quetes_actives": list(quetes)}


def course(giver="lieu:forge", cible="lieu:saloir", livree=False, id_="q1"):
	q = {
		"id": id_, "giver": giver,
		"objectif": {"type": "transport", "cible": cible},
	}
	if livree:
		q["livree_at"] = 1000
	return q


def escorte_q(giver="lieu:temple", cible="lieu:athanor", rdv="lieu:auxerre",
			  rencontree=False, id_="e1"):
	obj = {"type": "escorte", "cible": cible}
	if rdv:
		obj["rencontre"] = {"lieu": rdv, "position": {"x": 10, "y": 12}}
	q = {"id": id_, "giver": giver, "objectif": obj}
	if rencontree:
		q["rencontre_at"] = 2000
	return q


# ── AUCUNE lecture de document ───────────────────────────────────────────────────

def test_marques_lieux_ne_lit_aucun_document(monkeypatch):
	"""Le module ne doit faire aucun accès DB. Un `get_doc`/`find_docs` qui se glisserait
	dans un prédicat ferait exploser ce test AVANT la revue de code : la map est republiée
	par le déplacement, le dialogue et les quatre endpoints de quêtes."""
	def interdit(*a, **k):  # pragma: no cover - doit ne jamais être appelé
		raise AssertionError("marques_lieux a touché la base")

	import db.config as dbc
	monkeypatch.setattr(dbc, "get_doc", interdit, raising=False)
	monkeypatch.setattr(dbc, "find_docs", interdit, raising=False)
	monkeypatch.setattr(dbc, "save_doc", interdit, raising=False)

	c = personnage(course(), escorte_q(), {"id": "k", "giver": "lieu:guilde",
										   "objectif": {"type": "kill", "quantite": 3},
										   "progress": 3})
	assert indicateurs.marques_lieux(c)  # non vide : le calcul a bien tourné
	# Garde plus forte que le monkeypatch (qui ne verrait pas un `from db.config import …`) :
	# le module ne doit tout simplement PAS avoir de nom d'accès DB dans son espace.
	for nom in ("get_doc", "find_docs", "save_doc", "delete_doc", "db"):
		assert not hasattr(indicateurs, nom), f"utils/indicateurs.py expose `{nom}`"


def test_personnage_sans_quete():
	assert indicateurs.marques_lieux(personnage()) == {}
	assert indicateurs.marques_lieux({}) == {}


# ── Transport : la marque SE DÉPLACE de la destination au donneur ─────────────────

def test_transport_aller_marque_le_destinataire():
	c = personnage(course(giver="lieu:forge", cible="lieu:saloir"))
	assert indicateurs.marques_lieux(c) == {"lieu:saloir": "?"}


def test_transport_livre_marque_le_donneur_et_plus_le_destinataire():
	"""Une course `retour` reste active après la livraison — le temps d'aller en rendre
	compte. La marque doit SUIVRE le geste attendu, pas rester où elle était."""
	c = personnage(course(giver="lieu:forge", cible="lieu:saloir", livree=True))
	assert indicateurs.marques_lieux(c) == {"lieu:forge": "?"}


# ── Escorte : EXACTEMENT une des deux étapes ─────────────────────────────────────

def test_escorte_avant_rencontre_marque_le_rendez_vous_seul():
	c = personnage(escorte_q(cible="lieu:athanor", rdv="lieu:auxerre"))
	assert indicateurs.marques_lieux(c) == {"lieu:auxerre": "?"}


def test_escorte_apres_rencontre_marque_la_destination_seule():
	c = personnage(escorte_q(cible="lieu:athanor", rdv="lieu:auxerre", rencontree=True))
	assert indicateurs.marques_lieux(c) == {"lieu:athanor": "?"}


def test_escorte_sans_rendez_vous_marque_la_destination():
	"""Sans bloc `rencontre`, la personne rejoint le groupe à l'acceptation : `incarner`
	pose `rencontre_at` sur-le-champ, il n'y a donc qu'une étape."""
	c = personnage(escorte_q(cible="lieu:athanor", rdv=None, rencontree=True))
	assert indicateurs.marques_lieux(c) == {"lieu:athanor": "?"}


def test_escorte_rendez_vous_et_depose_au_meme_lieu_ne_marque_qu_une_fois():
	"""Le cas qui casserait une garde mal posée : `escorte_vers` ne teste PAS
	`rencontre_at`, c'est l'aiguillage d'`indicateurs` qui rend les deux étapes exclusives."""
	avant = personnage(escorte_q(cible="lieu:auxerre", rdv="lieu:auxerre"))
	apres = personnage(escorte_q(cible="lieu:auxerre", rdv="lieu:auxerre", rencontree=True))
	assert indicateurs.marques_lieux(avant) == {"lieu:auxerre": "?"}
	assert indicateurs.marques_lieux(apres) == {"lieu:auxerre": "?"}


# ── Chasse : le piège du `quantite` par défaut ───────────────────────────────────

def test_chasse_sans_champ_quantite_n_est_PAS_accomplie():
	"""⚠️ LE piège du module : `chasse.chasse_accomplie` a `quantite` par défaut **1**,
	`quetes.objectif_atteint` par défaut **0**. Aiguiller autrement que sur le TYPE
	d'objectif marquerait « à rendre » une chasse à peine acceptée."""
	q = {"id": "c1", "giver": "lieu:comptoir", "progress": 0,
		 "objectif": {"type": "chasse", "cible": "espece:loup", "lieu": "lieu:auxerre"}}
	assert indicateurs.marques_lieux(personnage(q)) == {}


def test_chasse_accomplie_marque_le_donneur():
	q = {"id": "c1", "giver": "lieu:comptoir", "progress": 1,
		 "objectif": {"type": "chasse", "cible": "espece:loup", "lieu": "lieu:auxerre"}}
	assert indicateurs.marques_lieux(personnage(q)) == {"lieu:comptoir": "?"}


def test_epreuve_de_rang_et_commission_passent_par_le_meme_chemin():
	"""Rang et commission sont des quêtes `chasse` ordinaires : seule leur `source` diffère,
	et `indicateurs` n'a justement pas à la connaître."""
	rang = {"id": "r1", "source": "rang", "giver": "lieu:comptoir", "progress": 1,
			"objectif": {"type": "chasse", "cible": "espece:ours", "quantite": 1}}
	com = {"id": "d1", "source": "commission", "giver": "lieu:bureau", "progress": 1,
		   "objectif": {"type": "chasse", "cible": "espece:rat", "quantite": 1}}
	assert indicateurs.marques_lieux(personnage(rang, com)) == {
		"lieu:comptoir": "?", "lieu:bureau": "?"}


# ── kill / collect / visite ──────────────────────────────────────────────────────

@pytest.mark.parametrize("type_", ["kill", "collect", "visite"])
def test_objectif_generique_atteint_ou_non(type_):
	fait = {"id": "g", "giver": "lieu:guilde", "progress": 5,
			"objectif": {"type": type_, "quantite": 5}}
	pas_fait = {"id": "g", "giver": "lieu:guilde", "progress": 2,
				"objectif": {"type": type_, "quantite": 5}}
	assert indicateurs.marques_lieux(personnage(fait)) == {"lieu:guilde": "?"}
	assert indicateurs.marques_lieux(personnage(pas_fait)) == {}


def test_plusieurs_quetes_au_meme_donneur_ne_produisent_qu_une_entree():
	a = {"id": "a", "giver": "lieu:guilde", "progress": 1,
		 "objectif": {"type": "kill", "quantite": 1}}
	b = {"id": "b", "giver": "lieu:guilde", "progress": 2,
		 "objectif": {"type": "collect", "quantite": 2}}
	assert indicateurs.marques_lieux(personnage(a, b)) == {"lieu:guilde": "?"}


def test_giver_absent_ou_illisible_ne_pose_rien():
	"""Fail-soft : une quête sans donneur ne doit pas produire une clé `None` que le client
	rattacherait à n'importe quoi."""
	q = {"id": "x", "progress": 1, "objectif": {"type": "kill", "quantite": 1}}
	assert indicateurs.marques_lieux(personnage(q)) == {}


# ── Kill-switch ─────────────────────────────────────────────────────────────────

def test_kill_switch_coupe_tout(monkeypatch):
	monkeypatch.setattr(character_stats, "INDICATEURS_ACTIFS", False)
	c = personnage(course(), escorte_q(rencontree=True))
	assert indicateurs.marques_lieux(c) == {}


# ── Marque d'un CHOIX de dialogue (utils/pnj.py) ─────────────────────────────────

def test_marque_de_condition_offre_et_rapport():
	assert pnj_util.marque_de_condition({"transport_offert": True}) == "!"
	assert pnj_util.marque_de_condition({"escorte_offerte": True}) == "!"
	assert pnj_util.marque_de_condition({"transport_a_livrer": True}) == "?"
	assert pnj_util.marque_de_condition({"commission_a_rapporter": True}) == "?"


def test_marque_de_condition_offre_prime_sur_rapport():
	cond = {"transport_a_livrer": True, "transport_offert": True}
	assert pnj_util.marque_de_condition(cond) == "!"


def test_un_flag_ATTENDU_FAUX_est_un_verrou_pas_une_offre():
	"""⚠️ `condition_ok` compare `bool(flags.get(cle)) is not bool(attendu)` : une condition
	peut exiger l'ABSENCE du flag. Sans cette garde, le nœud « rien à te proposer
	aujourd'hui » porterait un « ! »."""
	assert pnj_util.marque_de_condition({"transport_offert": False}) is None
	assert pnj_util.marque_de_condition({"commission_a_rapporter": False}) is None


def test_conditions_sans_rapport_avec_les_marques():
	assert pnj_util.marque_de_condition(None) is None
	assert pnj_util.marque_de_condition({}) is None
	assert pnj_util.marque_de_condition({"relation_min": {"lieux": ["lieu:x"], "seuil": 70}}) is None
	assert pnj_util.marque_de_condition({"intro_raison": "dette"}) is None
	assert pnj_util.marque_de_condition({"dialogue_en_attente": True}) is None


def test_les_deux_frozensets_sont_des_sous_ensembles_de_FLAGS_CONNUS():
	"""Garde-fou contre un flag mal orthographié : il vaudrait False en silence et la marque
	ne s'afficherait JAMAIS, sans le moindre symptôme."""
	assert pnj_util.FLAGS_OFFRE <= lint_dialogues.FLAGS_CONNUS
	assert pnj_util.FLAGS_RAPPORT <= lint_dialogues.FLAGS_CONNUS
	assert not (pnj_util.FLAGS_OFFRE & pnj_util.FLAGS_RAPPORT)


# ── Marque d'un NŒUD (donc du bouton 🗣) ─────────────────────────────────────────

def _pnj(*choix):
	return {"_id": "pnj:test",
			"dialogue": {"noeud_depart": "accueil",
						 "noeuds": {"accueil": {"texte": "…", "choix": list(choix)}}}}


def _ctx(**flags):
	return {"relations": {}, "intro_raison": None, "prenom": "Greta",
			"flags": dict(flags), "placeholders": {}}


def test_marque_noeud_prend_la_plus_forte_des_choix_visibles():
	doc = _pnj(
		{"id": "a", "label": "Bonjour"},
		{"id": "b", "label": "Une livraison", "condition": {"transport_a_livrer": True}},
		{"id": "c", "label": "Une course ?", "condition": {"transport_offert": True}},
	)
	ctx = _ctx(transport_a_livrer=True, transport_offert=True)
	assert pnj_util.marque_noeud(doc, "accueil", ctx) == "!"


def test_marque_noeud_ignore_un_choix_MASQUE_par_sa_condition():
	"""Toute la promesse du badge : « badge ! ⇒ en entrant, je trouve un choix ! ». Dériver
	des flags bruts promettrait un « ! » à un PNJ qui n'a aucune branche pour l'exploiter."""
	doc = _pnj({"id": "c", "label": "Une course ?", "condition": {"transport_offert": True}})
	assert pnj_util.marque_noeud(doc, "accueil", _ctx(transport_offert=False)) is None
	assert pnj_util.marque_noeud(doc, "accueil", _ctx(transport_offert=True)) == "!"


def test_marque_noeud_sur_un_noeud_inexistant():
	assert pnj_util.marque_noeud(_pnj(), "attente", _ctx()) is None


def test_noeud_attente_ne_porte_aucun_badge():
	"""Bénéfice gratuit du calcul sur le nœud de DÉPART EFFECTIF : sous `delai_min`, c'est
	`noeud_attente` qui est servi, et ses choix ne portent pas de condition d'offre."""
	doc = {"_id": "pnj:gautier",
		   "dialogue": {"noeud_depart": "accueil", "noeud_attente": "patiente",
						"noeuds": {
							"accueil": {"choix": [{"id": "c", "label": "?",
												   "condition": {"commission_offerte": True}}]},
							"patiente": {"choix": [{"id": "p", "label": "Revenir plus tard"}]},
						}}}
	ctx = _ctx(commission_offerte=True)
	depart_libre = pnj_util.noeud_depart_effectif(doc, 0)
	depart_bloque = pnj_util.noeud_depart_effectif(doc, 900)
	assert pnj_util.marque_noeud(doc, depart_libre, ctx) == "!"
	assert pnj_util.marque_noeud(doc, depart_bloque, ctx) is None


def test_noeud_client_publie_la_marque_et_jamais_la_condition():
	doc = _pnj(
		{"id": "c", "label": "Une course ?", "condition": {"transport_offert": True}},
		{"id": "a", "label": "Bonjour"},
	)
	vue = pnj_util.noeud_client(doc, "accueil", _ctx(transport_offert=True))
	assert [c["id"] for c in vue["choix"]] == ["c", "a"]
	assert vue["choix"][0]["marque"] == "!"
	assert vue["choix"][1]["marque"] is None
	assert all("condition" not in c for c in vue["choix"])


def test_noeud_client_et_marque_noeud_partagent_le_MEME_filtre():
	"""Deux boucles de filtrage divergeraient un jour, et le badge cesserait de correspondre
	au contenu du panneau."""
	doc = _pnj(
		{"id": "c", "label": "Une course ?", "condition": {"transport_offert": True}},
		{"id": "l", "label": "Livraison", "condition": {"transport_a_livrer": True}},
	)
	ctx = _ctx(transport_offert=False, transport_a_livrer=True)
	vue = pnj_util.noeud_client(doc, "accueil", ctx)
	assert [c["id"] for c in vue["choix"]] == ["l"]
	assert pnj_util.marque_noeud(doc, "accueil", ctx) == "?"

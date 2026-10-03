# tests/test_quete_reussie_cite.py
# La clause d'accès `quete_reussie_cite` : « au moins une quête DONNÉE DANS CETTE CITÉ a été
# menée à bien », et le `giver` / la `cite` que les archives de quête portent pour elle.
#
# ⚠️ Le test qui compte est `test_une_archive_d_avant_ne_compte_pas` : les archives déjà en
# base n'ont ni `giver` ni `cite`. Elles ne doivent rien ouvrir ni rien refermer.

from utils import acces, chasse, escorte, transport


CITE = "lieu:lutecia"
LIEUX = {
	"lieu:lutecia": {"_id": "lieu:lutecia", "lieu_parent": "lieu:france"},
	"lieu:france": {"_id": "lieu:france"},
	"lieu:comptoir": {"_id": "lieu:comptoir", "lieu_parent": "lieu:lutecia"},
	"lieu:arriere_salle": {"_id": "lieu:arriere_salle", "lieu_parent": "lieu:comptoir"},
	"lieu:auxerre": {"_id": "lieu:auxerre", "lieu_parent": "lieu:france"},
	"lieu:cathedrale": {"_id": "lieu:cathedrale", "lieu_parent": "lieu:auxerre"},
	# Chaîne cyclique : la remontée doit s'arrêter, pas boucler.
	"lieu:a": {"_id": "lieu:a", "lieu_parent": "lieu:b"},
	"lieu:b": {"_id": "lieu:b", "lieu_parent": "lieu:a"},
}


def _get(doc_id):
	return LIEUX.get(doc_id)


def _perso(*archives):
	return {"_id": "character:t", "quetes_actives": [], "quetes_terminees": list(archives)}


def _lieu(condition):
	return {"_id": "lieu:porte", "acces": {"cycle": 1, "refus": "Non.",
										   "conditions": [condition]}}


def _ok(character, condition):
	return acces.acces_autorise(character, _lieu(condition), _get)[0]


POSITIF = {"quete_reussie_cite": {"cite": CITE}}
NEGATIF = {"quete_reussie_cite": {"cite": CITE, "attendu": False}}


def test_dans_les_deux_sens():
	vierge = _perso()
	fait = _perso({"id": "quete:x", "giver": "lieu:comptoir"})
	assert _ok(vierge, POSITIF) is False
	assert _ok(fait, POSITIF) is True
	# La forme qui compte : visible tant qu'aucune quête de la cité n'est rendue.
	assert _ok(vierge, NEGATIF) is True
	assert _ok(fait, NEGATIF) is False


def test_le_donneur_remonte_toute_la_chaine_lieu_parent():
	assert _ok(_perso({"id": "q", "giver": "lieu:arriere_salle"}), POSITIF) is True
	# Le donneur peut être la cité elle-même.
	assert _ok(_perso({"id": "q", "giver": CITE}), POSITIF) is True


def test_une_quete_d_une_autre_cite_ne_compte_pas():
	"""Le convoi de Lutecia est donné à Auxerre : y arriver n'est pas une quête de Lutecia."""
	c = _perso({"id": "quete:escorte_convoi_de_lutecia", "giver": "lieu:cathedrale"})
	assert _ok(c, POSITIF) is False
	assert _ok(c, NEGATIF) is True


def test_un_echec_ne_compte_pas():
	c = _perso({"id": "q", "giver": "lieu:comptoir", "echec": True})
	assert _ok(c, POSITIF) is False


def test_la_cite_archivee_telle_quelle_compte():
	"""Épreuve d'apport : aucune quête active, donc aucun `giver` — la cité est archivée."""
	assert _ok(_perso({"id": "quete:apport_lutecia_C", "cite": CITE}), POSITIF) is True


def test_une_archive_d_avant_ne_compte_pas():
	"""Aucune migration : une archive sans `giver` ni `cite` est muette."""
	c = _perso({"id": "quete:x", "titre": "Ancienne", "rang": "F"})
	assert _ok(c, POSITIF) is False
	assert _ok(c, NEGATIF) is True


def test_une_chaine_cyclique_ne_boucle_pas():
	assert _ok(_perso({"id": "q", "giver": "lieu:a"}), POSITIF) is False


def test_un_donneur_disparu_ne_compte_pas():
	assert _ok(_perso({"id": "q", "giver": "lieu:supprime"}), POSITIF) is False


def test_fail_closed_y_compris_sous_la_negation():
	c = _perso()
	for filtre in ({}, {"cite": ""}, {"cite": None}, {"cite": 12}):
		assert _ok(c, {"quete_reussie_cite": filtre}) is False
		assert _ok(c, {"quete_reussie_cite": {**filtre, "attendu": False}}) is False
	assert _ok(c, {"quete_reussie_cite": {"cite": CITE, "attendu": "non"}}) is False


def test_declaree_au_vocabulaire():
	assert "quete_reussie_cite" in acces.CONDITIONS_CONNUES
	assert acces.SOUS_FILTRES_CONNUS["quete_reussie_cite"] == {"cite", "attendu"}
	assert acces.conditions_invalides(
		_lieu({"quete_reussie_cite": {"cite": CITE, "id": "q"}})) == ["quete_reussie_cite.id"]
	assert "quete_reussie_cite" in acces.vocabulaire_conditions()["cles"]


# ── Les archives portent ce que la clause lit ───────────────────────────────────

def test_transport_et_escorte_archivent_le_donneur():
	for module in (transport, escorte):
		c = {"quetes_actives": [{"id": "q", "giver": "lieu:comptoir"}]}
		module.archiver(c, c["quetes_actives"][0], echec=False, now=1)
		assert c["quetes_terminees"][-1]["giver"] == "lieu:comptoir"


def test_l_epreuve_d_apport_archive_la_cite():
	perso = {"rangs_guilde": {CITE: "D"}, "inventaire": [], "quetes_actives": [],
			 "quetes_terminees": [], "xp_total": 0, "vocations_niveaux": {"guerrier": 0},
			 "voc": "guerrier", "or": 0, "argent": 0, "cuivre": 0, "attribute_points": 0}
	apport = {"rang_vise": "C", "items": ["item:x"], "recompenses": {"xp": 10}}
	assert chasse.solder_apport(perso, CITE, apport) is not None
	assert perso["quetes_terminees"][-1]["cite"] == CITE
	assert _ok(perso, NEGATIF) is False

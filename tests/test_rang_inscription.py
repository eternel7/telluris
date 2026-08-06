# tests/test_rang_inscription.py
# Inscription à un rang de guilde portée par la RÉCOMPENSE d'une quête
# (`recompenses.rang_guilde`) — c'est ainsi que la première mission de Borin fait entrer le
# joueur dans la guilde, là où l'épreuve du comptoir le fait MONTER (`chasse.promouvoir`).
#
# Trois maillons, testés séparément puis bout en bout :
#   spec écrite  →  transport.rang_guilde_recompense  (résolution de la cité, À LA GÉNÉRATION)
#                →  quetes.appliquer_recompenses      (chokepoint unique des 4 turn-in)
#                →  chasse.crediter_rang              (écriture, jamais de rétrogradation)

from utils import chasse, quetes, transport
from utils.characters import money_to_cuivre
from utils.recrutement import RANGS

GUILDE = {"_id": "lieu:le_bastion_de_l_yonne_comptoir", "lieu_parent": "lieu:auxerre"}


def perso(**champs):
	base = {
		"_id": "character:u_1", "type": "character",
		"xp_total": 0, "attribute_points": 0, "vocations_niveaux": {"barbare": 0},
		"inventaire": [], "or": 0, "argent": 0, "cuivre": 0, "groupe": [],
	}
	base.update(champs)
	return base


# ── Résolution de la cité (miroir d'`items_recompense`) ──────────────────────────

def test_la_cite_est_DERIVEE_du_donneur():
	"""Une spec écrit `"F"` tout court : la cité vient du `lieu_parent` du donneur, donc la
	même mission copiée dans une autre guilde inscrit à SA cité."""
	assert transport.rang_guilde_recompense("F", GUILDE) == {
		"rang_guilde": {"cite": "lieu:auxerre", "rang": "F"}
	}


def test_un_donneur_sans_parent_retombe_sur_lui_meme():
	assert transport.rang_guilde_recompense("F", {"_id": "lieu:x"}) == {
		"rang_guilde": {"cite": "lieu:x", "rang": "F"}
	}


def test_une_cite_explicite_est_recopiee_telle_quelle():
	spec = {"cite": "lieu:rhemi", "rang": "E"}
	assert transport.rang_guilde_recompense(spec, GUILDE) == {"rang_guilde": spec}


def test_sans_spec_la_cle_est_ABSENTE_du_bloc_recompenses():
	"""`{}` et non `{"rang_guilde": None}` : le bloc est fusionné par `**`, une clé nulle
	traînerait dans toutes les courses ordinaires."""
	assert transport.rang_guilde_recompense(None, GUILDE) == {}
	assert transport.rang_guilde_recompense("", GUILDE) == {}


# ── Écriture (chasse.crediter_rang) ──────────────────────────────────────────────

def test_inscription_d_un_personnage_sans_aucun_rang():
	c = perso(rangs_guilde={})
	assert chasse.crediter_rang(c, {"cite": "lieu:auxerre", "rang": "F"}) == "F"
	assert c["rangs_guilde"] == {"lieu:auxerre": "F"}


def test_le_champ_absent_ne_demande_aucune_migration():
	c = perso()
	assert "rangs_guilde" not in c
	assert chasse.crediter_rang(c, {"cite": "lieu:auxerre", "rang": "F"}) == "F"
	assert c["rangs_guilde"] == {"lieu:auxerre": "F"}


def test_ne_RETROGRADE_jamais():
	"""Le cœur de la garde : rejouer une inscription F chez qui est déjà D ne retire rien."""
	c = perso(rangs_guilde={"lieu:auxerre": "D"})
	assert chasse.crediter_rang(c, {"cite": "lieu:auxerre", "rang": "F"}) is None
	assert c["rangs_guilde"]["lieu:auxerre"] == "D"


def test_une_seconde_fois_ne_change_rien():
	c = perso(rangs_guilde={"lieu:auxerre": "F"})
	assert chasse.crediter_rang(c, {"cite": "lieu:auxerre", "rang": "F"}) is None


def test_une_autre_cite_est_independante():
	c = perso(rangs_guilde={"lieu:auxerre": "D"})
	assert chasse.crediter_rang(c, {"cite": "lieu:rhemi", "rang": "F"}) == "F"
	assert c["rangs_guilde"] == {"lieu:auxerre": "D", "lieu:rhemi": "F"}


def test_fail_closed_sur_une_donnee_illisible():
	"""Cité manquante ou rang hors échelle ⇒ rien n'est écrit : on n'invente pas un cran sur
	une donnée qu'on ne sait pas lire (même refus qu'un seuil illisible dans `acces`)."""
	c = perso(rangs_guilde={})
	for spec in ({"rang": "F"}, {"cite": "lieu:auxerre"},
				 {"cite": "lieu:auxerre", "rang": "Z"},
				 {"cite": "lieu:auxerre", "rang": None}, "F", None, []):
		assert chasse.crediter_rang(c, spec) is None
	assert c["rangs_guilde"] == {}


def test_promouvoir_reste_intact_a_cote():
	"""L'épreuve de rang monte d'UN cran ; l'inscription pose un cran donné. Les deux
	coexistent sur le même champ."""
	c = perso(rangs_guilde={})
	chasse.crediter_rang(c, {"cite": "lieu:auxerre", "rang": "F"})
	assert chasse.promouvoir(c, "lieu:auxerre") == RANGS[1]


# ── Bout en bout : la première mission de Borin ──────────────────────────────────

def test_la_premiere_mission_de_borin_inscrit_au_rang_F():
	"""Ce que le joueur vit : la course est écrite `rang_guilde: "F"`, générée chez Borin,
	puis soldée — et `rangs_guilde` porte enfin ce que le moteur supposait déjà."""
	rec = {"xp": 30, "cuivre": 200,
		   "items": [{"item": "item:carte_aventurier", "poids": 0.05}],
		   **transport.rang_guilde_recompense("F", GUILDE)}
	q = {"id": "quete:transport_borin_premiere_mission", "recompenses": rec}

	c = perso(rangs_guilde={})
	assert chasse.meilleur_rang(c["rangs_guilde"]) == "aucun"   # avant : rien à afficher

	recap = quetes.appliquer_recompenses(c, q)

	assert recap["rang"] == "F"
	assert c["rangs_guilde"] == {"lieu:auxerre": "F"}
	assert chasse.meilleur_rang(c["rangs_guilde"]) == "F"
	# Les autres récompenses passent inchangées (la prime est convertie en bourse par
	# `credit_character` : 200 cuivre = 2 argent, d'où la relecture par `money_to_cuivre`).
	assert c["xp_total"] == 30 and money_to_cuivre(c) == 200
	assert len(c["inventaire"]) == 1


def test_le_recap_du_solde_PROPAGE_le_rang_jusqu_a_l_endpoint():
	"""⚠️ Le piège : `transport._solder` recopiait le récap clé par clé, donc `rang` était
	jeté en silence. Le personnage portait bien son rang neuf, mais l'endpoint ne l'apprenait
	jamais — pas de payload, affichage figé jusqu'au rechargement de /play."""
	rec = {"xp": 30, "cuivre": 200, **transport.rang_guilde_recompense("F", GUILDE)}
	q = {"id": "quete:transport_borin_premiere_mission", "giver": GUILDE["_id"],
		 "recompenses": rec, "objectif": {"type": "transport", "cible": "lieu:fumoir"}}
	c = perso(rangs_guilde={}, quetes_actives=[q])

	recap = transport.rapporter_transport(c, q, lambda _id: None, lambda d: d)

	assert recap["rang"] == "F"
	assert c["rangs_guilde"] == {"lieu:auxerre": "F"}
	# Les clés historiques du récap restent en place (aucune régression du turn-in).
	for cle in ("xp", "purse", "relation", "compagnie"):
		assert cle in recap, cle


def test_une_course_ordinaire_ne_touche_a_aucun_rang():
	"""Aucune régression sur les courses générées : sans `rang_guilde`, `recap["rang"]` est
	None et le champ du personnage n'est même pas créé."""
	c = perso()
	recap = quetes.appliquer_recompenses(c, {"recompenses": {"xp": 10, "cuivre": 30}})
	assert recap["rang"] is None
	assert "rangs_guilde" not in c

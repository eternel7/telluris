"""Donjons et commissions d'éradication (utils/donjon.py) — logique pure, sans DB.

Les dépendances DB sont injectées (get_doc_fn / find_docs_fn). Le monde de test : un donjon
d'une salle (`lieu:mine`, une battle map avec `cells`) peuplé de deux espèces, et quatre
profils de grades croissants dont un réservé aux créatures « magie » — c'est lui qui doit
être écarté quand on résout le grade de l'élite d'un gobelin (filtre `restriction_tags ⊆
tags de l'espèce`, comme pour les quêtes de chasse).

Le point que ces tests verrouillent : une commission est une quête `chasse` ORDINAIRE
(`objectif.type == "chasse"`, progressée par `quetes.maj_progress_chasse`), distinguée d'une
épreuve de rang par son seul `source == "commission"`.
"""

import pytest

from models import character_stats
from utils import donjon, quetes


# ── Monde de test ────────────────────────────────────────────────────────────────

def _espece(eid, nom, tags):
	return {"_id": eid, "type": "espece", "nom": nom, "tags": list(tags),
			"base_attributes": {k: {"min": 4, "max": 8} for k in
								("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch")}}


GOBELIN = _espece("espece:gobelin", "Gobelin", ["humanoide", "petite_taille"])
ARAIGNEE = _espece("espece:araignee_geante", "Araignee Geante", ["monstre", "venin"])
SORCIER = _espece("espece:sorcier", "Sorcier", ["humanoide", "magie"])


def _profil(pid, niveau, restr=None):
	return {"_id": pid, "type": "profil", "nom": pid.split(":")[-1].title(),
			"niveau": niveau, "restriction_tags": restr or []}


NOVICE = _profil("profil:novice", 1)
COMBATTANT = _profil("profil:combattant", 2)
SEIGNEUR = _profil("profil:seigneur", 6)
# Niveau 6 comme le seigneur, mais réservé à « magie » : jamais l'élite d'un gobelin.
SEIGNEUR_MAGE = _profil("profil:seigneur_mage", 6, ["magie"])
PROFILS = [NOVICE, COMBATTANT, SEIGNEUR, SEIGNEUR_MAGE]

MINE = {"_id": "lieu:mine", "type": "lieu", "label": "La mine aux cristaux",
		"categorie": "battle_map", "image": "map0021.png",
		"dimensions": {"x": 4, "y": 4}, "cells": [[1] * 4 for _ in range(4)]}
# Une salle SANS grille : elle ne doit jamais être tirée (le décor du donjon serait perdu).
SALLE_SANS_GRILLE = {"_id": "lieu:salle_vide", "type": "lieu", "categorie": "battle_map"}

BUREAU = {"_id": "lieu:bureau", "type": "lieu", "label": "Bureau du maître de guilde",
		  "categorie": "bureau_maitre_guilde", "lieu_parent": "lieu:auxerre"}

DONJON = {
	"_id": "donjon:mine", "type": "donjon", "nom": "Le donjon-mine",
	"portail": "lieu:portail",
	"battle_maps": [{"lieu": "lieu:mine",
					 "especes": ["espece:gobelin", "espece:araignee_geante"]}],
}

DOCS = {d["_id"]: d for d in
		(GOBELIN, ARAIGNEE, SORCIER, MINE, SALLE_SANS_GRILLE, BUREAU, DONJON, *PROFILS)}


def get_doc(doc_id):
	return DOCS.get(doc_id)


def find_docs(selector):
	t = (selector or {}).get("type")
	return [d for d in DOCS.values() if d.get("type") == t]


def _character(**extra):
	# ⚠️ La bourse vit en champs de PREMIER NIVEAU (`or`/`argent`/`cuivre`), pas dans un
	# sous-dict `money` : c'est ce que mutent `credit_character`/`money_to_cuivre`.
	return {"_id": "character:1", "user_id": "user:1", "inventaire": [],
			"quetes_actives": [], "quetes_terminees": [],
			"attribute_points": 0, "xp": 0, "niveau": 1,
			"or": 0, "argent": 0, "cuivre": 0, **extra}


@pytest.fixture(autouse=True)
def graine(monkeypatch):
	"""Tirages déterministes : `tirer_cible` et `_profil_max_compatible` font des choix."""
	import random
	monkeypatch.setattr(random, "choice", lambda seq: list(seq)[0])


# ---------------------------------------------------------------------------
# Lecture du doc donjon
# ---------------------------------------------------------------------------

def test_battle_map_entry_trouve_la_salle():
	assert donjon.battle_map_entry(DONJON, "lieu:mine")["lieu"] == "lieu:mine"
	assert donjon.battle_map_entry(DONJON, "lieu:ailleurs") is None


def test_battle_maps_de_ignore_les_entrees_mal_formees():
	doc = {"battle_maps": [{"especes": ["espece:gobelin"]}, "pas un dict",
						   {"lieu": "lieu:mine"}]}
	assert [e["lieu"] for e in donjon.battle_maps_de(doc)] == ["lieu:mine"]
	assert donjon.battle_maps_de({}) == []
	assert donjon.battle_maps_de(None) == []


def test_donjon_de_lieu_est_le_seul_lien_salle_vers_donjon():
	assert donjon.donjon_de_lieu("lieu:mine", find_docs)["_id"] == "donjon:mine"
	# Une battle map ordinaire (décor de combat tiré au hasard) n'appartient à aucun donjon.
	assert donjon.donjon_de_lieu("lieu:salle_vide", find_docs) is None
	assert donjon.donjon_de_lieu(None, find_docs) is None


def test_especes_de_salle_ne_renvoie_que_les_docs_existants():
	doc = {"battle_maps": [{"lieu": "lieu:mine",
							"especes": ["espece:gobelin", "espece:fantome"]}]}
	assert [e["_id"] for e in donjon.especes_de_salle(doc, "lieu:mine", get_doc)] \
		== ["espece:gobelin"]


# ---------------------------------------------------------------------------
# Grade de l'élite
# ---------------------------------------------------------------------------

def test_profil_max_compatible_prend_le_plus_haut_niveau():
	assert donjon._profil_max_compatible(GOBELIN, PROFILS)["_id"] == "profil:seigneur"


def test_profil_max_compatible_ecarte_les_profils_restreints():
	# `profil:seigneur_mage` est de même niveau que `profil:seigneur`, mais réservé à « magie ».
	for _ in range(10):
		assert donjon._profil_max_compatible(GOBELIN, PROFILS)["_id"] != "profil:seigneur_mage"
	# Une créature qui PORTE le tag y a droit (et il n'est alors pas écarté du pool).
	compat = [p["_id"] for p in PROFILS
			  if set(p["restriction_tags"]) <= set(SORCIER["tags"])]
	assert "profil:seigneur_mage" in compat


def test_profil_max_compatible_sans_profil_du_tout():
	assert donjon._profil_max_compatible(GOBELIN, []) is None
	assert donjon._profil_max_compatible(GOBELIN, None) is None


# ---------------------------------------------------------------------------
# niveau_max — le bouton de difficulté (un donjon n'a pas de zones pour le borner)
# ---------------------------------------------------------------------------

def test_niveau_max_de_salle_prime_sur_donjon():
	d = {"niveau_max": 2, "battle_maps": [{"lieu": "lieu:a", "niveau_max": 5},
										  {"lieu": "lieu:b"}]}
	assert donjon.niveau_max_de(d, "lieu:a") == 5   # la salle prime
	assert donjon.niveau_max_de(d, "lieu:b") == 2   # repli sur le donjon
	assert donjon.niveau_max_de(d) == 2


def test_niveau_max_de_absent_est_sans_borne():
	assert donjon.niveau_max_de(DONJON, "lieu:mine") is None
	assert donjon.niveau_max_de({}, "lieu:mine") is None


def test_niveau_max_de_valeur_illisible_passe_a_la_source_suivante():
	# On ne DEVINE pas un plafond : ni 0 (qui bloquerait tout), ni « sans borne » (qui
	# rendrait le donjon imbattable en silence).
	d = {"niveau_max": 3, "battle_maps": [{"lieu": "lieu:a", "niveau_max": "beaucoup"}]}
	assert donjon.niveau_max_de(d, "lieu:a") == 3


def test_profils_sous_plafond():
	assert {p["_id"] for p in donjon._profils_sous_plafond(PROFILS, 2)} \
		== {"profil:novice", "profil:combattant"}
	# Sans plafond, tout passe.
	assert len(donjon._profils_sous_plafond(PROFILS, None)) == len(PROFILS)


def test_profils_sous_plafond_trop_bas_retombe_sur_le_plancher():
	# Mieux vaut un donjon trop facile qu'un donjon sans monstres : sans profil,
	# instantiate_monsters retomberait sur le point médian de l'espèce, tous grades confondus.
	assert [p["_id"] for p in donjon._profils_sous_plafond(PROFILS, 0)] == ["profil:novice"]
	assert donjon._profils_sous_plafond([], 3) == []


def test_tirer_cible_respecte_le_plafond_de_grade():
	"""LE test d'équilibrage : sans plafond, l'élite prend le niveau 6 de la base — un mur
	imbattable pour un joueur qui vient de décrocher son rang D."""
	sans = dict(DONJON)
	assert donjon.tirer_cible(sans, get_doc, find_docs)["profil"]["niveau"] == 6
	avec = dict(DONJON, niveau_max=2)
	assert donjon.tirer_cible(avec, get_doc, find_docs)["profil"]["niveau"] == 2


def test_tirer_cible_plafond_par_salle():
	d = {"niveau_max": 6, "battle_maps": [
		{"lieu": "lieu:mine", "especes": ["espece:gobelin"], "niveau_max": 1}]}
	assert donjon.tirer_cible(d, get_doc, find_docs)["profil"]["niveau"] == 1


def test_tirer_cible_ne_requete_les_profils_qu_une_fois():
	"""`_contexte` (routers/pnj.py) appelle `tirer_cible` à CHAQUE rendu de nœud : une
	requête de profils par espèce du donjon serait gratuite."""
	appels = []

	def find_docs_compte(selector):
		appels.append((selector or {}).get("type"))
		return find_docs(selector)

	donjon.tirer_cible(DONJON, get_doc, find_docs_compte)
	assert appels.count("profil") == 1


# ---------------------------------------------------------------------------
# tirer_cible
# ---------------------------------------------------------------------------

def test_tirer_cible_nominal():
	cible = donjon.tirer_cible(DONJON, get_doc, find_docs)
	assert cible["lieu"] == "lieu:mine"
	assert cible["espece"]["_id"] in ("espece:gobelin", "espece:araignee_geante")
	assert cible["profil"]["_id"] == "profil:seigneur"
	assert cible["lieu_doc"]["_id"] == "lieu:mine"


def test_tirer_cible_donjon_vide():
	assert donjon.tirer_cible({"battle_maps": []}, get_doc, find_docs) is None
	assert donjon.tirer_cible(None, get_doc, find_docs) is None


def test_tirer_cible_ignore_une_salle_sans_grille():
	# Sans `cells`, create_combat_doc retomberait sur une grille ouverte → décor perdu.
	d = {"battle_maps": [{"lieu": "lieu:salle_vide", "especes": ["espece:gobelin"]}]}
	assert donjon.tirer_cible(d, get_doc, find_docs) is None


def test_tirer_cible_ignore_un_lieu_inexistant():
	d = {"battle_maps": [{"lieu": "lieu:nulle_part", "especes": ["espece:gobelin"]}]}
	assert donjon.tirer_cible(d, get_doc, find_docs) is None


def test_tirer_cible_sans_espece_compatible():
	assert donjon.tirer_cible(DONJON, get_doc, lambda s: []) is None


# ---------------------------------------------------------------------------
# construire_commission
# ---------------------------------------------------------------------------

def _offre(character=None):
	cible = donjon.tirer_cible(DONJON, get_doc, find_docs)
	return donjon.construire_commission(BUREAU, cible)


def test_construire_commission_forme_de_l_objectif():
	q = _offre()
	obj = q["objectif"]
	# C'est une quête de CHASSE ordinaire : c'est ce qui la rend progressable sans code neuf.
	assert obj["type"] == "chasse"
	assert obj["lieu"] == "lieu:mine"
	assert obj["cible"] == q["objectif"]["cible"]
	assert obj["profil"] == "profil:seigneur"
	assert obj["quantite"] == 1
	# ⚠️ PAS de `position` : on entre dans un donjon par son gardien, pas en marchant sur
	# une case. `dans_zone_chasse` lit alors la seule contrainte de lieu.
	assert "position" not in obj


def test_construire_commission_source_et_giver():
	q = _offre()
	assert q["source"] == "commission"
	assert q["giver"] == "lieu:bureau"
	assert q["type"] == "quete"
	assert q["_id"].startswith("quete:bureau_commission_")


def test_construire_commission_recompenses_positives():
	q = _offre()
	assert q["recompenses"]["xp"] > 0
	assert q["recompenses"]["cuivre"] > 0


def test_construire_commission_nomme_le_grade_et_le_lieu():
	q = _offre()
	from utils import chasse
	grade = chasse.qualificatif_de(SEIGNEUR)
	assert grade in q["titre"]
	assert grade in q["description"]
	assert "La mine aux cristaux" in q["description"]
	# La narration pré-combat est générée (l'espèce varie) : elle nomme la bête et le lieu.
	assert grade in q["narration"] and "La mine aux cristaux" in q["narration"]


def test_construire_commission_cible_incomplete():
	assert donjon.construire_commission(BUREAU, None) is None
	assert donjon.construire_commission(BUREAU, {"lieu": "lieu:mine"}) is None


# ---------------------------------------------------------------------------
# offre / acceptation
# ---------------------------------------------------------------------------

def test_offre_commission_pour_nominal():
	assert donjon.offre_commission_pour(
		_character(), BUREAU, DONJON, get_doc, find_docs) is not None


def test_offre_commission_bloquee_si_une_est_deja_active():
	character = _character()
	donjon.accepter_commission(character, _offre())
	assert donjon.offre_commission_pour(
		character, BUREAU, DONJON, get_doc, find_docs) is None


def test_offre_commission_reoffrable_apres_soldement():
	# Pas de `unique` : une commission est un contrat de travail répétable.
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	q["progress"] = 1
	assert donjon.solder_commission(character, q["id"]) is not None
	assert donjon.offre_commission_pour(
		character, BUREAU, DONJON, get_doc, find_docs) is not None


def test_offre_commission_sans_cible_jouable():
	assert donjon.offre_commission_pour(
		_character(), BUREAU, {"battle_maps": []}, get_doc, find_docs) is None


def test_accepter_commission_pousse_le_snapshot():
	character = _character()
	offre = _offre()
	q = donjon.accepter_commission(character, offre)
	assert character["quetes_actives"] == [q]
	assert q["id"] == offre["_id"]
	assert q["source"] == "commission"
	assert q["narration"] == offre["narration"]
	assert q["progress"] == 0
	assert q["objectif"] == offre["objectif"]


def test_accepter_commission_offre_vide():
	character = _character()
	assert donjon.accepter_commission(character, None) is None
	assert character["quetes_actives"] == []


# ---------------------------------------------------------------------------
# Progression & soldement
# ---------------------------------------------------------------------------

def test_commission_active_et_pour_lieu():
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	assert donjon.commission_active(character) is q
	assert donjon.commission_active_pour_lieu(character, "lieu:mine") is q
	assert donjon.commission_active_pour_lieu(character, "lieu:ailleurs") is None


def test_commission_active_ignore_une_epreuve_de_rang():
	# Les deux familles sont des quêtes `chasse` : seul `source` les sépare.
	character = _character(quetes_actives=[
		{"id": "quete:r1", "source": "rang", "objectif": {"type": "chasse", "quantite": 1},
		 "progress": 1},
	])
	assert donjon.commission_active(character) is None
	assert donjon.commission_a_rapporter(character) is None


def test_commission_a_rapporter_suit_maj_progress_chasse():
	"""La progression n'est PAS spécifique aux commissions : c'est le hook générique de
	`utils/quetes.py` (appelé par finalize_combat) qui la fait avancer."""
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	assert donjon.commission_a_rapporter(character) is None
	# Un monstre de la bonne espèce mais NON MARQUÉ ne compte pas.
	quetes.maj_progress_chasse(character, [
		{"vivant": False, "espece_id": q["objectif"]["cible"]}])
	assert donjon.commission_a_rapporter(character) is None
	# L'élite marquée, elle, complète la commission.
	quetes.maj_progress_chasse(character, [
		{"vivant": False, "espece_id": q["objectif"]["cible"], "quete_chasse": q["id"]}])
	assert donjon.commission_a_rapporter(character) is q


def test_solder_commission_archive_et_paie():
	from utils.characters import money_to_cuivre
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	q["progress"] = 1
	resultat = donjon.solder_commission(character, q["id"])
	assert resultat is not None
	assert resultat["recompenses"]["xp"]["xp_gain"] == q["recompenses"]["xp"]
	# La prime atterrit bien dans la bourse (champs de 1er niveau, pas un sous-dict `money`).
	assert money_to_cuivre(character) == q["recompenses"]["cuivre"]
	assert character["quetes_actives"] == []
	assert [t["id"] for t in character["quetes_terminees"]] == [q["id"]]
	assert character["quetes_terminees"][0]["titre"] == q["titre"]


def test_solder_commission_refuse_si_non_accomplie():
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	assert donjon.solder_commission(character, q["id"]) is None
	assert character["quetes_actives"] == [q]


def test_solder_commission_archive_le_lieu_et_la_source():
	"""Sans `lieu`/`source` dans l'archive, plus rien ne dit QUEL donjon a été purgé — et le
	gardien reparlerait d'une mine infestée après le rapport (cf. `donjon_purge`)."""
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	q["progress"] = 1
	donjon.solder_commission(character, q["id"])
	archive = character["quetes_terminees"][0]
	assert archive["source"] == "commission"
	assert archive["lieu"] == "lieu:mine"


# ---------------------------------------------------------------------------
# donjon_purge — l'état du LIEU, qui survit au rapport
# ---------------------------------------------------------------------------

def test_donjon_purge_faux_avant_et_pendant():
	character = _character()
	assert not donjon.donjon_purge(character, "lieu:mine")
	q = donjon.accepter_commission(character, _offre())
	# Commission prise mais élite encore debout.
	assert not donjon.donjon_purge(character, "lieu:mine")


def test_donjon_purge_vrai_des_l_objectif_atteint():
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	q["progress"] = 1
	assert donjon.donjon_purge(character, "lieu:mine")


def test_donjon_purge_SURVIT_au_rapport():
	"""C'est toute la raison d'être de la fonction : `commission_a_rapporter` devient faux au
	turn-in, mais la mine reste purgée — le monde a changé pour de bon."""
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	q["progress"] = 1
	donjon.solder_commission(character, q["id"])
	assert donjon.commission_a_rapporter(character) is None
	assert donjon.donjon_purge(character, "lieu:mine")


def test_donjon_purge_est_propre_au_lieu():
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	q["progress"] = 1
	donjon.solder_commission(character, q["id"])
	assert not donjon.donjon_purge(character, "lieu:autre_mine")


def test_donjon_purge_ignore_une_archive_d_un_autre_type():
	# Une épreuve de rang archivée ne purge aucun donjon.
	character = _character(quetes_terminees=[
		{"id": "quete:r1", "titre": "Épreuve", "rang": "E", "lieu": "lieu:mine"},
	])
	assert not donjon.donjon_purge(character, "lieu:mine")


def test_donjon_purge_archive_ancienne_sans_lieu():
	# Dégradation gracieuse : une commission soldée avant l'ajout de `lieu` n'est pas
	# détectable — le gardien reparle d'une mine infestée, sans planter.
	character = _character(quetes_terminees=[
		{"id": "quete:c1", "titre": "Commission", "rang": "D", "source": "commission"},
	])
	assert not donjon.donjon_purge(character, "lieu:mine")


def test_solder_commission_quete_introuvable():
	assert donjon.solder_commission(_character(), "quete:inexistante") is None


def test_solder_commission_ne_touche_pas_une_epreuve_de_rang():
	# Même id, mais `source: "rang"` → ce n'est pas à ce module de la solder (pas de
	# promotion de rang ici, ce serait une promotion silencieusement perdue).
	character = _character(quetes_actives=[
		{"id": "quete:r1", "source": "rang", "objectif": {"type": "chasse", "quantite": 1},
		 "progress": 1, "recompenses": {"xp": 5, "cuivre": 5}},
	])
	assert donjon.solder_commission(character, "quete:r1") is None
	assert len(character["quetes_actives"]) == 1


# ---------------------------------------------------------------------------
# Intégration avec la fiche (rendu de quête)
# ---------------------------------------------------------------------------

def test_quete_detail_ne_propose_pas_de_carte_sans_position(monkeypatch):
	"""Une commission ne porte pas de case cible : le bouton 🗺️ doit rester masqué, sinon
	l'overlay recadrerait sur (0,0) et enverrait le joueur au mauvais endroit."""
	monkeypatch.setattr(quetes, "get_doc", get_doc)
	character = _character()
	q = donjon.accepter_commission(character, _offre())
	detail = quetes.quete_detail(character, q)
	assert "carte" not in detail
	assert detail["objectif"]["type"] == "chasse"

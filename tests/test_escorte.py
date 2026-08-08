# tests/test_escorte.py
#
# Quêtes d'ESCORTE (utils/escorte.py) : retrouver quelqu'un, le faire voyager avec le
# groupe, le ramener VIVANT. Tests PURS — aucune DB : tout passe par les fonctions
# injectées (get_doc_fn / save_doc_fn / find_docs_fn), comme le module lui-même.
#
# La partie COMBAT (snapshot non jouable, hors initiative, défaite) est en fin de fichier
# et réutilise les fabriques de test_combat_groupe, comme test_combat_montures.

import pytest

from models import character_stats
from utils import escorte as escorte_util
from utils import recrutement as recrutement_util
from utils import expedition as expedition_util
from utils import combat as combat_util
from utils import characters as characters_util

from tests.test_combat_groupe import (
	character as combat_character, joueur_snap, monstre_snap, combat_doc,
)


# ── Monde de test ────────────────────────────────────────────────────────────────

RACES = {
	"_id": "rules:races",
	"value": [{"id": "humain", "stats": {"V": 5, "F": 20, "R": 20, "Ag": 20,
										 "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20}}],
}

HERBES = {"_id": "item:Herbes_medicinales", "type": "item", "nom": "Herbes médicinales",
		  "categorie": "composant", "sous_categorie": "herbe", "poids": 0.1}

TEMPLE = {"_id": "lieu:temple", "type": "lieu", "label": "Temple de Saint-Eusèbe",
		  "categorie": "temple", "lieu_parent": "lieu:auxerre"}

ATHANOR = {"_id": "lieu:athanor", "type": "lieu", "label": "L'Athanor",
		   "categorie": "laboratoire_d_alchimie", "lieu_parent": "lieu:auxerre"}

# Cité de 10×10 : tout est praticable SAUF la colonne x=5 (mur) — de quoi vérifier que la
# case du rendez-vous est bien ramenée sur du terrain franchissable.
def _cells(mur_x=None):
	return [[0 if x == mur_x else 1 for x in range(10)] for _ in range(10)]


CITE = {
	"_id": "lieu:auxerre", "type": "lieu", "label": "Auxerre", "categorie": "ville",
	"dimensions": {"x": 10, "y": 10},
	"cells": _cells(),
	"zone_influences": [{"zone": "zone:foret", "x": 6, "y": 4, "rayon": 3}],
}

SPEC = {
	"id": "quete:escorte_aline",
	"destination": "lieu:athanor",
	"rencontre": {"lieu": "lieu:auxerre", "zones": ["zone:foret"]},
	"proteges": [{"prenom": "Aline", "nom": "Varnepierre", "race": "humain", "sex": "F",
				  "image": "druide_f_humain03.jpg",
				  "inventaire": [{"item": "item:Herbes_medicinales"}]}],
	"unique": True,
	"recompenses": {"xp": 40, "cuivre": 10000},
}


def pnj(spec=SPEC):
	return {"_id": "pnj:malakor", "type": "pnj", "nom": "Malakor",
			"services": {"escorte": {"offre": dict(spec) if spec else None,
									 "noeuds": {"accepte": "escorte_acceptee"}}}}


def character(cid="character:u_1", **champs):
	base = {
		"_id": cid, "type": "character", "user_id": "user:u",
		"prenom": "Test", "nom": "Héros", "race": "humain", "voc": "guerrier",
		"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 30,
									 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
		"currentPV": 50, "currentPM": 20, "xp_total": 0, "attribute_points": 0,
		"vocations_niveaux": {"guerrier": 0},
		"inventaire": [], "slots": {}, "equipment_bonus": {}, "competences_bonus": {},
		"effets_actifs": [], "or": 0, "argent": 0, "cuivre": 0,
		"quetes_actives": [], "quetes_terminees": [], "combats_recompenses": [],
		"position": {"x": 0, "y": 0}, "lieu": "lieu:auxerre", "groupe": [], "montures": [],
	}
	base.update(champs)
	return base


@pytest.fixture
def db():
	"""Base en mémoire + les trois fonctions injectées attendues par le module."""
	docs = {d["_id"]: dict(d) for d in (RACES, HERBES, TEMPLE, ATHANOR, CITE)}

	def get_doc_fn(doc_id):
		d = docs.get(doc_id)
		return dict(d) if d else None

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def find_docs_fn(selector, fields=None):
		return [d for d in docs.values()
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	return {"docs": docs, "get": get_doc_fn, "save": save_doc_fn, "find": find_docs_fn}


def _offre(db, spec=SPEC, giver=TEMPLE):
	return escorte_util.generer_escorte_authoree(spec, giver, db["find"], db["get"])


# ── Le rendez-vous : trois formes, une seule résolution ──────────────────────────

def test_rencontre_absente_personne_chez_le_donneur(db):
	"""Sans bloc `rencontre`, l'objectif n'en porte pas : elle rejoint le groupe à
	l'acceptation."""
	spec = dict(SPEC)
	spec.pop("rencontre")
	offre = _offre(db, spec)
	assert "rencontre" not in offre["objectif"]


def test_rencontre_lieu_seul_sans_position(db):
	"""`{lieu}` sans zones : contrainte de LIEU seule — on la trouve n'importe où là-bas."""
	spec = dict(SPEC, rencontre={"lieu": "lieu:auxerre"})
	offre = _offre(db, spec)
	assert offre["objectif"]["rencontre"] == {"lieu": "lieu:auxerre"}


def test_rencontre_zones_tire_une_case(db):
	"""`{lieu, zones}` : la case du placement est figée dans l'objectif."""
	offre = _offre(db)
	rdv = offre["objectif"]["rencontre"]
	assert rdv["lieu"] == "lieu:auxerre"
	assert rdv["position"] == {"x": 6, "y": 4}


def test_position_bornee_aux_marges(db):
	"""Une zone qui déborde du bord de carte ne doit pas envoyer le joueur hors image :
	la case est ramenée à MARGE_BORDS cases du bord (régression `lieu:auxerre`, x=86 sur
	une carte de 86 cases)."""
	lieu = dict(CITE, zone_influences=[{"zone": "zone:foret", "x": 42, "y": -7}])
	pos = escorte_util.position_de_rencontre(lieu, ["zone:foret"])
	assert pos == {"x": 7, "y": 2}          # 10 cases, marge 2 → [2, 7]


def test_position_ramenee_sur_case_praticable(db):
	"""Bornée ne suffit pas : une case peut être un mur. La spirale de Chebyshev de
	`chasse.case_praticable_proche` la décale d'une case."""
	lieu = dict(CITE, cells=_cells(mur_x=6),
				zone_influences=[{"zone": "zone:foret", "x": 6, "y": 4}])
	pos = escorte_util.position_de_rencontre(lieu, ["zone:foret"])
	assert pos != {"x": 6, "y": 4}
	assert lieu["cells"][pos["y"]][pos["x"]] >= 1


def test_position_none_sans_grille_ni_zone(db):
	assert escorte_util.position_de_rencontre(TEMPLE, ["zone:foret"]) is None
	assert escorte_util.position_de_rencontre(CITE, []) is None
	assert escorte_util.position_de_rencontre(CITE, ["zone:inconnue"]) is None


# ── Offre & unicité ──────────────────────────────────────────────────────────────

def test_offre_spec_exige_destination_et_proteges():
	assert escorte_util.offre_spec(pnj())["id"] == "quete:escorte_aline"
	assert escorte_util.offre_spec(pnj(spec={"destination": "lieu:x"})) is None
	assert escorte_util.offre_spec({"_id": "pnj:x"}) is None


def test_deja_reussie_ignore_les_echecs():
	c = character(quetes_terminees=[{"id": "quete:escorte_aline", "echec": True}])
	assert escorte_util.deja_reussie(c, "quete:escorte_aline") is False
	c["quetes_terminees"].append({"id": "quete:escorte_aline"})
	assert escorte_util.deja_reussie(c, "quete:escorte_aline") is True


def test_offre_unique_ne_repasse_pas(db):
	"""Gate `unique` : le donneur ne repropose pas une escorte menée à bien."""
	c = character(quetes_terminees=[{"id": "quete:escorte_aline"}])
	assert escorte_util.poser_escorte_offerte(c, TEMPLE, db["find"], db["get"],
											  rand_fn=lambda: 0.0, pnj_doc=pnj()) is True
	assert escorte_util.offre_courante(c, TEMPLE) is None


def test_offre_posee_une_fois_par_entree(db):
	c = character()
	assert escorte_util.poser_escorte_offerte(c, TEMPLE, db["find"], db["get"],
											  rand_fn=lambda: 0.0, pnj_doc=pnj()) is True
	assert escorte_util.offre_courante(c, TEMPLE)["id"] == "quete:escorte_aline"
	# Un refresh ne re-tire pas.
	assert escorte_util.poser_escorte_offerte(c, TEMPLE, db["find"], db["get"],
											  rand_fn=lambda: 0.0, pnj_doc=pnj()) is False


def test_pas_d_empilement_d_escortes(db):
	c = character()
	offre = _offre(db)
	escorte_util.accepter_escorte(c, offre, db["get"])
	c["escorte_offerte"] = None
	escorte_util.poser_escorte_offerte(c, TEMPLE, db["find"], db["get"],
									   rand_fn=lambda: 0.0, pnj_doc=pnj())
	assert escorte_util.offre_courante(c, TEMPLE) is None


def test_lieu_sans_donneur_nettoie_l_offre(db):
	c = character()
	escorte_util.poser_escorte_offerte(c, TEMPLE, db["find"], db["get"],
									   rand_fn=lambda: 0.0, pnj_doc=pnj())
	assert escorte_util.poser_escorte_offerte(c, ATHANOR, db["find"], db["get"],
											  pnj_doc=None) is True
	assert c["escorte_offerte"] is None


# ── Rang de guilde exigé par l'offre ─────────────────────────────────────────────

RANG_D = {"cite": "lieu:auxerre", "rang": "D"}


def test_sans_rang_min_l_offre_reste_ouverte_a_tous(db):
	"""Rétro-compat : une spec sans `rang_min` se comporte exactement comme avant."""
	assert escorte_util.rang_requis(SPEC) is None
	assert escorte_util.rang_suffisant(character(), SPEC) is True


def test_rang_insuffisant_bloque_l_offre(db):
	"""Rang F face à un seuil D : rien n'est posé — donc rien à accepter, même en forgeant
	la requête (`offre_courante` rend None et le service refuse en 422)."""
	spec = dict(SPEC, rang_min=RANG_D)
	c = character(rangs_guilde={"lieu:auxerre": "F"})
	escorte_util.poser_escorte_offerte(c, TEMPLE, db["find"], db["get"],
									   rand_fn=lambda: 0.0, pnj_doc=pnj(spec))
	assert escorte_util.offre_courante(c, TEMPLE) is None


def test_rang_absent_vaut_le_premier_de_l_echelle(db):
	"""Un personnage neuf n'a pas de `rangs_guilde` : il ne passe pas."""
	spec = dict(SPEC, rang_min=RANG_D)
	assert escorte_util.rang_suffisant(character(), spec) is False


def test_rang_atteint_ouvre_l_offre(db):
	spec = dict(SPEC, rang_min=RANG_D)
	c = character(rangs_guilde={"lieu:auxerre": "D"})
	escorte_util.poser_escorte_offerte(c, TEMPLE, db["find"], db["get"],
									   rand_fn=lambda: 0.0, pnj_doc=pnj(spec))
	assert escorte_util.offre_courante(c, TEMPLE)["id"] == "quete:escorte_aline"


def test_rang_superieur_ouvre_aussi(db):
	"""Le seuil est un MINIMUM : un rang plus élevé passe (comparaison sur l'échelle)."""
	spec = dict(SPEC, rang_min=RANG_D)
	assert escorte_util.rang_suffisant(character(rangs_guilde={"lieu:auxerre": "C"}), spec)


def test_rang_d_une_autre_cite_ne_compte_pas(db):
	"""Le rang est propre à la CITÉ : celui de Rhemi n'ouvre pas la mission d'Auxerre."""
	spec = dict(SPEC, rang_min=RANG_D)
	assert escorte_util.rang_suffisant(character(rangs_guilde={"lieu:rhemi": "B"}), spec) is False


def test_seuil_illisible_est_fail_closed(db):
	"""Un `rang` hors échelle ou un `cite` manquant REFUSE : un seuil qu'on ne sait pas lire
	ne doit pas rendre l'offre permissive (même esprit que les barrières de lieu)."""
	c = character(rangs_guilde={"lieu:auxerre": "A"})
	assert escorte_util.rang_suffisant(c, dict(SPEC, rang_min={"cite": "lieu:auxerre",
															   "rang": "Z"})) is False
	assert escorte_util.rang_suffisant(c, dict(SPEC, rang_min={"rang": "D"})) is False


def test_refus_parle_seulement_quand_il_y_a_de_quoi_refuser(db):
	"""Le flag du nœud de refus : vrai pour un joueur trop peu gradé, faux dès qu'il n'y a
	plus rien à refuser (rang atteint, escorte en cours, mission déjà accomplie)."""
	spec = dict(SPEC, rang_min=RANG_D)
	assert escorte_util.rang_insuffisant(character(), pnj(spec)) is True
	assert escorte_util.rang_insuffisant(
		character(rangs_guilde={"lieu:auxerre": "D"}), pnj(spec)) is False
	# Sans seuil, jamais de refus à prononcer.
	assert escorte_util.rang_insuffisant(character(), pnj()) is False
	# Mission déjà menée à bien.
	fini = character(quetes_terminees=[{"id": "quete:escorte_aline"}])
	assert escorte_util.rang_insuffisant(fini, pnj(spec)) is False


def test_le_rang_de_la_quete_suit_son_seuil_d_acces(db):
	"""Une mission réservée au rang E EST une mission de rang E : le badge de la fiche ne
	doit pas annoncer « F » au joueur qui vient d'atteindre le palier."""
	offre = _offre(db, dict(SPEC, rang_min={"cite": "lieu:auxerre", "rang": "E"}))
	assert offre["rang"] == "E"


def test_rang_explicite_prime_sur_le_seuil(db):
	"""L'auteur garde le dernier mot : un `rang` écrit l'emporte sur le seuil d'accès."""
	offre = _offre(db, dict(SPEC, rang="C", rang_min={"cite": "lieu:auxerre", "rang": "E"}))
	assert offre["rang"] == "C"


def test_sans_seuil_le_rang_reste_au_premier_cran(db):
	"""Rétro-compat : sans `rang_min` ni `rang`, l'offre reste au premier cran."""
	assert _offre(db)["rang"] == "F"


def test_seuil_illisible_ne_devient_pas_un_rang_invente(db):
	"""Même bornage que le comparateur : un `rang` hors échelle retombe sur le défaut plutôt
	que de peindre un cran qui n'existe pas."""
	offre = _offre(db, dict(SPEC, rang_min={"cite": "lieu:auxerre", "rang": "Z"}))
	assert offre["rang"] == "F"


def test_rang_explicite_illisible_retombe_aussi(db):
	"""⚠️ Le bornage vaut AUSSI pour le `rang` écrit à la main : SANS EXCEPTION, c'est tout
	l'objet de la source unique `acces.rang_de_quete`."""
	assert _offre(db, dict(SPEC, rang="Z"))["rang"] == "F"
	assert _offre(db, dict(SPEC, rang="Z", rang_min={"cite": "lieu:auxerre",
													 "rang": "E"}))["rang"] == "E"


def _garder(db, lieu_id, rang):
	"""Pose une barrière `rang_min` sur un lieu de la base de test."""
	db["docs"][lieu_id]["acces"] = {
		"gardien": "pnj:x", "cycle": 1,
		"conditions": [{"rang_min": {"cite": "lieu:auxerre", "rang": rang}}],
	}


def test_la_barriere_du_lieu_de_depose_compte(db):
	"""Une mission qu'on ne peut pas RENDRE sans un rang ne doit pas s'annoncer plus facile
	qu'elle n'est : la porte de l'Athanor est une porte de la quête."""
	_garder(db, "lieu:athanor", "D")
	assert _offre(db)["rang"] == "D"


def test_le_plus_eleve_des_deux_seuils_gagne(db):
	"""Spec et lieu de dépose sont deux portes : c'est la plus stricte qui fait le prix."""
	_garder(db, "lieu:athanor", "D")
	assert _offre(db, dict(SPEC, rang_min={"cite": "lieu:auxerre", "rang": "E"}))["rang"] == "D"
	_garder(db, "lieu:athanor", "E")
	assert _offre(db, dict(SPEC, rang_min={"cite": "lieu:auxerre", "rang": "C"}))["rang"] == "C"


def test_barriere_sans_rang_min_ne_change_rien(db):
	"""Un lieu gardé par un MANDAT (et non par un rang) laisse la quête à son défaut."""
	db["docs"]["lieu:athanor"]["acces"] = {
		"gardien": "pnj:x", "cycle": 1,
		"conditions": [{"quete_active": {"types": ["escorte"]}}],
	}
	assert _offre(db)["rang"] == "F"


def test_la_regle_est_LA_MEME_que_celle_des_commissions(db):
	"""SANS EXCEPTION : escorte et commission de donjon passent par `acces.rang_de_quete`,
	donc rendent le même rang pour les mêmes seuils. Si l'une des deux dérivait un jour,
	c'est ce test qui tomberait."""
	from utils import acces as acces_util, donjon as donjon_util
	_garder(db, "lieu:athanor", "D")
	rang_escorte = _offre(db, dict(SPEC, rang_min={"cite": "lieu:auxerre", "rang": "E"}))["rang"]
	# Mêmes deux seuils, soumis par l'autre appelant.
	bureau = {"_id": "lieu:b", "acces": {"conditions": [
		{"rang_min": {"cite": "lieu:auxerre", "rang": "E"}}]}}
	salle = {"_id": "lieu:s", "acces": {"conditions": [
		{"rang_min": {"cite": "lieu:auxerre", "rang": "D"}}]}}
	assert rang_escorte == donjon_util.rang_commission(bureau, salle) == "D"
	# Et la source unique elle-même, appelée nue, dit la même chose.
	assert acces_util.rang_de_quete(None, "E", "D", defaut="F") == "D"


def test_le_rang_survit_a_l_acceptation_et_a_l_archivage(db):
	"""Le snapshot et l'archive recopient le rang : il doit rester E de bout en bout."""
	c = character(rangs_guilde={"lieu:auxerre": "E"})
	spec = dict(SPEC, rang_min={"cite": "lieu:auxerre", "rang": "E"})
	q, _docs = escorte_util.accepter_escorte(c, _offre(db, spec), db["get"])
	assert q["rang"] == "E"
	escorte_util.traiter_deplacement(c, CITE, {"x": 6, "y": 4},
									 db["get"], db["save"], db["find"])
	escorte_util.traiter_deplacement(c, ATHANOR, None,
									 db["get"], db["save"], db["find"])
	assert c["quetes_terminees"][0]["rang"] == "E"


def test_refus_parle_muet_pendant_une_escorte_en_cours(db):
	spec = dict(SPEC, rang_min=RANG_D)
	c = character()
	escorte_util.accepter_escorte(c, _offre(db), db["get"])
	assert escorte_util.rang_insuffisant(c, pnj(spec)) is False


# ── Acceptation ──────────────────────────────────────────────────────────────────

def test_accepter_pose_la_quete_sans_incarner(db):
	"""Avec un rendez-vous, personne ne naît encore : les docs attendent la rencontre."""
	c = character()
	c["escorte_offerte"] = {"lieu": "lieu:temple", "quete": _offre(db)}
	q, docs = escorte_util.accepter_escorte(c, _offre(db), db["get"])
	assert docs == []
	assert c["escorte_offerte"] is None
	assert q["objectif"]["type"] == "escorte"
	assert len(c["quetes_actives"]) == 1
	assert c.get("proteges") in (None, [])


def test_accepter_sans_rendez_vous_incarne_sur_le_champ(db):
	"""Sans bloc `rencontre`, elle est là, chez le donneur."""
	c = character()
	spec = dict(SPEC)
	spec.pop("rencontre")
	q, docs = escorte_util.accepter_escorte(c, _offre(db, spec), db["get"])
	assert len(docs) == 1
	assert q["rencontre_at"]
	assert c["proteges"] == [docs[0]["_id"]]
	assert docs[0]["statut"] == "escorte"
	assert docs[0]["escorte_par"] == c["_id"]


def test_protege_a_les_stats_de_base_de_sa_race(db):
	"""Une civile n'est pas une aventurière : aucun point dépensé."""
	c = character()
	doc = escorte_util.creer_protege(SPEC["proteges"][0], c, "quete:x", db["get"])
	assert doc["caracteristiques_current"] == RACES["value"][0]["stats"]
	# PV/PM au max dérivé, et un doc opérant pour le moteur.
	assert doc["currentPV"] > 0
	assert doc["slots"] == {} and doc["combats_recompenses"] == []
	# L'inventaire de la spec arrive AVEC elle, poids résolu depuis le doc item.
	assert doc["inventaire"] == [{"item": "item:Herbes_medicinales", "poids": 0.1}]


def test_protege_race_inconnue_ne_nait_pas_mort(db):
	"""Repli documenté : sans race résolue, les stats par défaut évitent un pv_max de 0."""
	doc = escorte_util.creer_protege({"prenom": "X", "race": "dragon"}, character(),
									 "quete:x", db["get"])
	assert doc["caracteristiques_current"] == escorte_util.STATS_DEFAUT
	assert doc["currentPV"] > 0


# ── Rencontre ────────────────────────────────────────────────────────────────────

def _accepte(db, c, spec=SPEC):
	q, _docs = escorte_util.accepter_escorte(c, _offre(db, spec), db["get"])
	return q


def test_rencontre_hors_zone_ne_fait_rien(db):
	c = character()
	_accepte(db, c)
	res = escorte_util.traiter_deplacement(c, CITE, {"x": 0, "y": 0},
										   db["get"], db["save"], db["find"])
	assert res["rencontres"] == []
	assert c.get("proteges") in (None, [])


def test_rencontre_dans_le_3x3_incarne_une_seule_fois(db):
	c = character()
	q = _accepte(db, c)
	res = escorte_util.traiter_deplacement(c, CITE, {"x": 5, "y": 5},
										   db["get"], db["save"], db["find"])
	assert len(res["rencontres"]) == 1
	assert len(c["proteges"]) == 1
	assert q["rencontre_at"]
	pid = c["proteges"][0]
	assert db["docs"][pid]["statut"] == "escorte"     # persisté par le chokepoint
	# Rejouer le même pas ne doit rien dupliquer (il est appelé à CHAQUE déplacement).
	res2 = escorte_util.traiter_deplacement(c, CITE, {"x": 5, "y": 5},
											db["get"], db["save"], db["find"])
	assert res2["rencontres"] == []
	assert c["proteges"] == [pid]


def test_rencontre_mauvais_lieu_ne_fait_rien(db):
	c = character()
	_accepte(db, c)
	res = escorte_util.traiter_deplacement(c, ATHANOR, {"x": 6, "y": 4},
										   db["get"], db["save"], db["find"])
	assert res["rencontres"] == []


def test_rencontre_sans_position_au_premier_pas_dans_le_lieu(db):
	"""Forme `{lieu}` seul : la contrainte de lieu suffit."""
	c = character()
	_accepte(db, c, dict(SPEC, rencontre={"lieu": "lieu:auxerre"}))
	res = escorte_util.traiter_deplacement(c, CITE, {"x": 0, "y": 0},
										   db["get"], db["save"], db["find"])
	assert len(res["rencontres"]) == 1


# ── Dépose ───────────────────────────────────────────────────────────────────────

def test_depose_mauvais_lieu_ne_solde_rien(db):
	c = character()
	_accepte(db, c)
	escorte_util.traiter_deplacement(c, CITE, {"x": 6, "y": 4},
									 db["get"], db["save"], db["find"])
	res = escorte_util.traiter_deplacement(c, CITE, {"x": 6, "y": 4},
										   db["get"], db["save"], db["find"])
	assert res["depose"] is None
	assert len(c["quetes_actives"]) == 1


def test_depose_solde_archive_et_detache(db):
	c = character()
	_accepte(db, c)
	escorte_util.traiter_deplacement(c, CITE, {"x": 6, "y": 4},
									 db["get"], db["save"], db["find"])
	pid = c["proteges"][0]

	res = escorte_util.traiter_deplacement(c, ATHANOR, None,
										   db["get"], db["save"], db["find"])

	assert res["depose"]["xp"] == 40
	assert c["xp_total"] == 40
	assert c["or"] == 1                       # 10 000 cuivre = 1 or
	assert c["quetes_actives"] == []
	assert c["quetes_terminees"][0]["id"] == "quete:escorte_aline"
	assert c["quetes_terminees"][0]["echec"] is False
	assert c["proteges"] == []
	assert db["docs"][pid]["statut"] == "arrivee"
	# +1 de relation chez le DONNEUR (le temple), jamais chez le destinataire.
	rel = [d for d in db["docs"].values()
		   if d.get("type") == "relation" and d.get("lieu_id") == "lieu:temple"]
	assert rel and rel[0]["value"] == int(character_stats.RELATION_INITIALE) + 1


def test_depose_refusee_si_quelqu_un_est_a_terre(db):
	c = character()
	_accepte(db, c)
	escorte_util.traiter_deplacement(c, CITE, {"x": 6, "y": 4},
									 db["get"], db["save"], db["find"])
	db["docs"][c["proteges"][0]]["currentPV"] = 0

	res = escorte_util.traiter_deplacement(c, ATHANOR, None,
										   db["get"], db["save"], db["find"])
	assert res["depose"] is None
	assert len(c["quetes_actives"]) == 1


def test_depose_impossible_avant_la_rencontre(db):
	"""Passer chez le père sans avoir trouvé sa fille ne solde rien."""
	c = character()
	_accepte(db, c)
	res = escorte_util.traiter_deplacement(c, ATHANOR, None,
										   db["get"], db["save"], db["find"])
	assert res["depose"] is None


# ── Échec ────────────────────────────────────────────────────────────────────────

def test_echouer_archive_en_echec_et_sanctionne(db):
	c = character()
	q = _accepte(db, c)
	escorte_util.traiter_deplacement(c, CITE, {"x": 6, "y": 4},
									 db["get"], db["save"], db["find"])
	pid = c["proteges"][0]

	docs = escorte_util.echouer(c, q, db["get"], db["save"], db["find"])

	assert c["quetes_actives"] == []
	assert c["quetes_terminees"][0]["echec"] is True
	assert c["quetes_terminees"][0]["recompenses"] == {}
	assert c["proteges"] == []
	assert [d["_id"] for d in docs] == [pid]
	rel = [d for d in db["docs"].values()
		   if d.get("type") == "relation" and d.get("lieu_id") == "lieu:temple"]
	assert rel and rel[0]["value"] == int(character_stats.RELATION_INITIALE) - 1


def test_echec_laisse_l_offre_reproposable(db):
	"""Un échec ne consomme pas le `unique` : le donneur repropose."""
	c = character()
	q = _accepte(db, c)
	escorte_util.echouer(c, q, db["get"], db["save"], db["find"])
	assert escorte_util.deja_reussie(c, "quete:escorte_aline") is False


def test_liberer_proteges_a_l_abandon(db):
	c = character()
	q = _accepte(db, c)
	escorte_util.traiter_deplacement(c, CITE, {"x": 6, "y": 4},
									 db["get"], db["save"], db["find"])
	docs = escorte_util.liberer_proteges(c, q, db["get"])
	assert c["proteges"] == []
	assert docs[0]["statut"] == "libere"


# ── Un protégé n'est ni un porteur ni un membre ──────────────────────────────────

def test_protege_hors_porteurs_et_hors_membres(db):
	"""RÉGRESSION : on ne lui transfère rien, il ne vend rien, il ne manie pas de hache."""
	c = character()
	spec = dict(SPEC)
	spec.pop("rencontre")
	_q, docs = escorte_util.accepter_escorte(c, _offre(db, spec), db["get"])
	pid = docs[0]["_id"]
	db["docs"][pid] = docs[0]

	assert [d["_id"] for d in escorte_util.proteges_effectifs(c, db["get"])] == [pid]
	assert recrutement_util.porteurs_effectifs(c, db["get"]) == []
	assert [m["_id"] for m in expedition_util.membres(c, db["get"])] == [c["_id"]]


def test_proteges_effectifs_ignore_un_lien_rompu(db):
	c = character(proteges=["protege:zombie"])
	db["docs"]["protege:zombie"] = {"_id": "protege:zombie", "type": "protege",
									"statut": "libere"}
	assert escorte_util.proteges_effectifs(c, db["get"]) == []


# ── PROGÉNITURE : les enfants des tenanciers ────────────────────────────────────
#
# La seule source d'escorte GÉNÉRÉE. Deux canaux, un seul moteur : le parent se saisit
# lui-même du cas de son enfant (sous condition de CONFIANCE), ou le comptoir de la guilde
# recense la disparition. Dans les deux cas, la spec synthétisée repasse par
# `generer_escorte_authoree` — c'est ce que ces tests épinglent en premier.

from utils import marche as marche_util          # noqa: E402
from utils import quetes as quetes_util          # noqa: E402


ZONE_FORET = {"_id": "zone:foret", "type": "zone_influence", "nom": "Forêt",
			  "modificateurs": {"danger": 1, "visibilite": 0}}
ZONE_VILLE = {"_id": "zone::coeur", "type": "zone_influence", "nom": "Cœur de ville",
			  "modificateurs": {"danger": -3, "visibilite": 1}}

# Cité avec DEUX zones placées : une dangereuse, une sûre. Le rendez-vous dérivé ne doit
# jamais tomber au milieu des étals.
CITE_ZONES = dict(CITE, zone_influences=[
	{"zone": "zone:foret", "x": 6, "y": 4},
	{"zone": "zone::coeur", "x": 2, "y": 2},
])

FAMILLE = {
	"nom": "Varnepierre",
	"race": "humain",
	"enfants": [
		{"prenom": "Girard", "sex": "M", "image": "druide_m_humain01.jpg",
		 "inventaire": [{"item": "item:Herbes_medicinales"}]},
		{"prenom": "Perrote", "sex": "F"},
	],
}

MARCHAND_PNJ = {"_id": "pnj:marchand_laboratoire_d_alchimie", "type": "pnj",
				"nom": "Le tenancier", "race": "humain",
				"services": {"escorte": {"noeuds": {"accepte": "escorte_acceptee"}}}}

MAGASIN = dict(ATHANOR, pnj=[{"character": "pnj:marchand_laboratoire_d_alchimie",
							  "nom": "Clément Varnepierre",
							  "progeniture": FAMILLE}])

COMPTOIR = {"_id": "lieu:comptoir", "type": "lieu", "label": "Le Bastion",
			"categorie": "guilde_aventurier_comptoir", "lieu_parent": "lieu:auxerre",
			"pnj": [{"character": "pnj:borin"}]}

BORIN = {"_id": "pnj:borin", "type": "pnj", "nom": "Borin",
		 "services": {"escorte": {"recherche": {"cite": "lieu:auxerre", "proba": 1.0},
								  "noeuds": {"accepte": "escorte_acceptee"}}}}


@pytest.fixture
def dbp(db):
	"""Le monde de `db`, plus une boutique dotée d'une famille et le comptoir de la guilde."""
	for d in (ZONE_FORET, ZONE_VILLE, MARCHAND_PNJ, MAGASIN, COMPTOIR, BORIN):
		db["docs"][d["_id"]] = dict(d)
	db["docs"]["lieu:auxerre"] = dict(CITE_ZONES)
	return db


def _relation(db, character, lieu_doc, valeur):
	"""Pose une cote en base pour ce couple perso × lieu (le doc n'existe pas par défaut :
	`get_relation` en fabrique un neutre à 50, sous le seuil de confiance)."""
	doc_id = marche_util.relation_doc_id(character, lieu_doc)
	db["docs"][doc_id] = {"_id": doc_id, "type": "relation",
						  "character_id": character["_id"],
						  "lieu_id": marche_util.lieu_de_relation(lieu_doc),
						  "value": valeur, "prix_negocies": {},
						  "marchandage_bloque_jusqu": 0}
	return db["docs"][doc_id]


def _toujours(valeur):
	return lambda *a, **k: valeur


def _premier(seq):
	return list(seq)[0]


# ── Où vit l'information de nommage ──────────────────────────────────────────────

def test_progeniture_lue_sur_l_entree_du_lieu_en_priorite():
	# Le doc PNJ est GÉNÉRIQUE : deux boutiques d'un même métier le partagent, donc c'est
	# l'entrée du lieu qui doit gagner — sinon elles auraient le même enfant.
	doc = {"services": {"escorte": {"progeniture": {"nom": "Doc", "enfants": [{"prenom": "A"}]}}}}
	entree = {"progeniture": {"nom": "Entree", "enfants": [{"prenom": "B"}]}}
	assert escorte_util.progeniture_de(entree, doc)["nom"] == "Entree"
	assert escorte_util.progeniture_de({}, doc)["nom"] == "Doc"
	assert escorte_util.progeniture_de(None, None) is None


def test_progeniture_sans_enfant_nomme_n_ouvre_rien():
	# Une famille vide, ou dont aucun enfant n'a de prénom, ne doit pas produire d'offre.
	assert escorte_util.progeniture_de({"progeniture": {"nom": "X", "enfants": []}}, None) is None
	assert escorte_util.progeniture_de({"progeniture": {"enfants": [{"sex": "F"}]}}, None) is None


def test_id_enfant_est_le_meme_quel_que_soit_le_canal():
	# ⚠️ L'id est bâti sur le MAGASIN, jamais sur le donneur : sinon le comptoir et le père
	# proposeraient deux quêtes distinctes pour le même enfant.
	# (le lieu de test est `lieu:athanor`)
	attendu = "quete:escorte_progeniture_athanor_girard"
	assert escorte_util.id_enfant("lieu:athanor", {"prenom": "Girard"}) == attendu
	# Accents et ponctuation ne changent pas l'id d'une régénération à l'autre.
	assert (escorte_util.id_enfant("lieu:l_athanor", {"prenom": "Élo\u00efse-Marie"})
			== "quete:escorte_progeniture_l_athanor_eloise_marie")


def test_un_enfant_ramene_ne_se_repropose_plus(dbp):
	perso = character()
	assert len(escorte_util.enfants_a_retrouver(perso, "lieu:athanor", FAMILLE)) == 2
	assert not escorte_util.progeniture_accomplie(perso, "lieu:athanor", FAMILLE)
	perso["quetes_terminees"] = [
		{"id": escorte_util.id_enfant("lieu:athanor", FAMILLE["enfants"][0]), "echec": False}]
	restants = escorte_util.enfants_a_retrouver(perso, "lieu:athanor", FAMILLE)
	assert [e["prenom"] for e in restants] == ["Perrote"]
	assert escorte_util.progeniture_accomplie(perso, "lieu:athanor", FAMILLE)


def test_un_echec_ne_consomme_pas_l_enfant(dbp):
	perso = character(quetes_terminees=[
		{"id": escorte_util.id_enfant("lieu:athanor", FAMILLE["enfants"][0]), "echec": True}])
	assert len(escorte_util.enfants_a_retrouver(perso, "lieu:athanor", FAMILLE)) == 2


# ── Le rendez-vous dérivé des zones dangereuses ──────────────────────────────────

def test_zones_dangereuses_ne_retient_que_le_danger_positif(dbp):
	zones = escorte_util.zones_dangereuses(dbp["docs"]["lieu:auxerre"], dbp["get"])
	assert zones == ["zone:foret"]


def test_zones_dangereuses_repli_sur_toutes_les_zones(dbp):
	# Carte sans aucune zone dangereuse : plutôt que de faire disparaître le contenu, on
	# retombe sur les zones placées — une carte muette est un défaut d'authoring.
	sans = dict(CITE_ZONES, zone_influences=[{"zone": "zone::coeur", "x": 2, "y": 2}])
	assert escorte_util.zones_dangereuses(sans, dbp["get"]) == ["zone::coeur"]
	# Aucune zone du tout : liste vide, l'appelant retombe sur la contrainte de lieu seule.
	assert escorte_util.zones_dangereuses(dict(CITE_ZONES, zone_influences=[]), dbp["get"]) == []


def test_rendez_vous_derive_tombe_dans_la_zone_dangereuse(dbp):
	spec = escorte_util.spec_progeniture(character(), dbp["docs"]["lieu:athanor"],
										 FAMILLE, dbp["get"], choix_fn=_premier)
	assert spec["rencontre"]["lieu"] == "lieu:auxerre"
	assert spec["rencontre"]["zones"] == ["zone:foret"]
	assert spec["destination"] == "lieu:athanor"


def test_rendez_vous_ecrit_prime_sur_le_derive(dbp):
	famille = dict(FAMILLE, rencontre={"lieu": "lieu:auxerre", "zones": ["zone::coeur"]})
	spec = escorte_util.spec_progeniture(character(), dbp["docs"]["lieu:athanor"],
										 famille, dbp["get"], choix_fn=_premier)
	assert spec["rencontre"]["zones"] == ["zone::coeur"]


# ── La spec synthétisée repasse par le générateur d'offre ÉCRITE ─────────────────

def test_offre_de_progeniture_a_la_forme_d_une_offre_ecrite(dbp):
	q = escorte_util.generer_escorte_progeniture(
		character(), dbp["docs"]["lieu:athanor"], FAMILLE, dbp["docs"]["lieu:athanor"],
		dbp["find"], dbp["get"], MARCHAND_PNJ, choix_fn=_premier)
	assert q["objectif"] == {"type": "escorte", "cible": "lieu:athanor", "quantite": 1,
							 "rencontre": q["objectif"]["rencontre"]}
	assert q["objectif"]["rencontre"]["position"] is not None
	assert q["giver"] == "lieu:athanor"
	# L'enfant hérite du nom de famille et de la race de la fratrie.
	assert q["proteges"][0]["nom"] == "Varnepierre"
	assert q["proteges"][0]["race"] == "humain"
	# Le magasin est REMERCIÉ en plus du donneur (ici le même : `recompenser_lieux` dédupe).
	assert q["recompenses"]["relation_lieux"] == ["lieu:athanor"]
	assert q["recompenses"]["xp"] == character_stats.ESCORTE_PROGENITURE_XP


# ── La confiance du tenancier ────────────────────────────────────────────────────

def test_le_tenancier_ne_parle_pas_de_sa_famille_a_un_inconnu(dbp):
	perso = character()                       # relation absente ⇒ neutre (50) < 60
	escorte_util.poser_escorte_offerte(
		perso, dbp["docs"]["lieu:athanor"], dbp["find"], dbp["get"],
		rand_fn=_toujours(0.0), pnj_doc=MARCHAND_PNJ,
		entree=MAGASIN["pnj"][0], choix_fn=_premier)
	# Le champ est bien posé (le tirage a eu lieu pour ce lieu), mais SANS quête.
	assert perso["escorte_offerte"] == {"lieu": "lieu:athanor", "quete": None}
	# …et il le DIT : sans refus parlé, le joueur croirait n'avoir pas eu de chance.
	assert escorte_util.mefiance(perso, dbp["docs"]["lieu:athanor"], MAGASIN["pnj"][0],
								 MARCHAND_PNJ, dbp["get"], now=0)


def test_au_dessus_du_seuil_la_course_est_offerte(dbp):
	perso = character()
	_relation(dbp, perso, dbp["docs"]["lieu:athanor"],
			  character_stats.ESCORTE_PROGENITURE_RELATION_MIN)
	assert escorte_util.poser_escorte_offerte(
		perso, dbp["docs"]["lieu:athanor"], dbp["find"], dbp["get"],
		rand_fn=_toujours(0.0), pnj_doc=MARCHAND_PNJ,
		entree=MAGASIN["pnj"][0], choix_fn=_premier)
	q = perso["escorte_offerte"]["quete"]
	assert q and q["proteges"][0]["prenom"] == "Girard"
	# Plus rien à refuser : le tenancier a parlé.
	assert not escorte_util.mefiance(perso, dbp["docs"]["lieu:athanor"], MAGASIN["pnj"][0],
									 MARCHAND_PNJ, dbp["get"], now=0)


def test_une_brouille_ferme_la_porte_meme_a_bonne_cote(dbp):
	perso = character()
	rel = _relation(dbp, perso, dbp["docs"]["lieu:athanor"], 90)
	rel["marchandage_bloque_jusqu"] = 10_000
	assert not escorte_util.confiance_suffisante(perso, dbp["docs"]["lieu:athanor"],
												 dbp["get"], now=1)
	assert escorte_util.mefiance(perso, dbp["docs"]["lieu:athanor"], MAGASIN["pnj"][0],
								 MARCHAND_PNJ, dbp["get"], now=1)


def test_seuil_a_zero_desactive_le_garde_fou(dbp, monkeypatch):
	monkeypatch.setattr(character_stats, "ESCORTE_PROGENITURE_RELATION_MIN", 0)
	assert escorte_util.confiance_suffisante(character(), dbp["docs"]["lieu:athanor"],
											 dbp["get"], now=0)


def test_mefiance_muette_quand_tous_les_enfants_sont_rentres(dbp):
	perso = character(quetes_terminees=[
		{"id": escorte_util.id_enfant("lieu:athanor", e), "echec": False}
		for e in FAMILLE["enfants"]])
	assert not escorte_util.mefiance(perso, dbp["docs"]["lieu:athanor"], MAGASIN["pnj"][0],
									 MARCHAND_PNJ, dbp["get"], now=0)


# ── Le registre de la guilde ─────────────────────────────────────────────────────

def test_la_guilde_ne_recense_que_les_familles_ecrites(dbp):
	perso = character()
	familles = escorte_util.familles_de_la_cite(perso, "lieu:auxerre", dbp["find"], dbp["get"])
	assert [lieu["_id"] for lieu, _e, _b in familles] == ["lieu:athanor"]
	# Une fois les deux enfants rentrés, la maison sort du registre.
	perso["quetes_terminees"] = [{"id": escorte_util.id_enfant("lieu:athanor", e), "echec": False}
								 for e in FAMILLE["enfants"]]
	assert escorte_util.familles_de_la_cite(perso, "lieu:auxerre", dbp["find"], dbp["get"]) == []


def test_le_comptoir_confie_la_recherche_sans_condition_de_relation(dbp):
	# Aucune relation posée : la guilde n'exige pas la confiance du marchand, seulement
	# d'être inscrit chez elle.
	perso = character()
	assert escorte_util.poser_escorte_offerte(
		perso, COMPTOIR, dbp["find"], dbp["get"], rand_fn=_toujours(0.0),
		pnj_doc=BORIN, choix_fn=_premier)
	q = perso["escorte_offerte"]["quete"]
	assert q["giver"] == "lieu:comptoir"                 # le donneur est le comptoir…
	assert q["objectif"]["cible"] == "lieu:athanor"      # …mais on dépose chez le parent
	assert q["recompenses"]["relation_lieux"] == ["lieu:athanor"]


def test_l_offre_ecrite_prime_sur_les_deux_sources_generees(dbp):
	# Un PNJ qui porte les trois blocs ne doit servir que le plus spécifique : l'écrit.
	pnj_doc = dict(BORIN)
	pnj_doc["services"] = {"escorte": dict(BORIN["services"]["escorte"],
										   offre=dict(SPEC, id="quete:ecrite"))}
	perso = character()
	escorte_util.poser_escorte_offerte(perso, COMPTOIR, dbp["find"], dbp["get"],
									   rand_fn=_toujours(0.0), pnj_doc=pnj_doc,
									   choix_fn=_premier)
	assert perso["escorte_offerte"]["quete"]["id"] == "quete:ecrite"


# ── Le solde : +1 chez le donneur ET chez le magasin ─────────────────────────────

def test_recompenser_lieux_dedouble_par_doc_relation(dbp):
	# ⚠️ LE PIÈGE : donneur et destination sont le MÊME lieu quand le parent confie
	# lui-même la mission — sans dédup il encaisserait +2 d'un seul coup.
	perso = character()
	magasin = dbp["docs"]["lieu:athanor"]
	valeurs = quetes_util.recompenser_lieux(perso, [magasin, magasin], dbp["get"], dbp["save"])
	assert valeurs["lieu:athanor"] == character_stats.RELATION_INITIALE + 1


def test_deux_lieux_qui_delegue_leur_relation_ne_comptent_qu_une_fois(dbp):
	# Même mécanisme via `relation_lieu` : la réception délègue au comptoir.
	perso = character()
	reception = {"_id": "lieu:reception", "type": "lieu",
				 "relation_lieu": "lieu:comptoir", "lieu_parent": "lieu:auxerre"}
	valeurs = quetes_util.recompenser_lieux(perso, [COMPTOIR, reception], dbp["get"], dbp["save"])
	assert valeurs["lieu:comptoir"] == valeurs["lieu:reception"] == \
		character_stats.RELATION_INITIALE + 1


def _mener_a_bien(dbp, perso, q):
	"""Incarne les protégés puis dépose la quête à destination — le chemin complet."""
	for doc in escorte_util.incarner(perso, q, dbp["get"]):
		dbp["save"](doc)
	cible = dbp["docs"][q["objectif"]["cible"]]
	return escorte_util.traiter_deplacement(perso, cible, None, dbp["get"], dbp["save"],
											dbp["find"], now=1000)


def test_une_escorte_de_guilde_monte_les_DEUX_reputations(dbp):
	perso = character()
	escorte_util.poser_escorte_offerte(perso, COMPTOIR, dbp["find"], dbp["get"],
									   rand_fn=_toujours(0.0), pnj_doc=BORIN,
									   choix_fn=_premier)
	q, _docs = escorte_util.accepter_escorte(perso, perso["escorte_offerte"]["quete"],
											 dbp["get"], now=1)
	maj = _mener_a_bien(dbp, perso, q)
	assert maj["depose"] is not None
	base = character_stats.RELATION_INITIALE
	comptoir = dbp["docs"]["relation:" + perso["_id"] + "::lieu:comptoir"]
	magasin = dbp["docs"]["relation:" + perso["_id"] + "::lieu:athanor"]
	assert comptoir["value"] == base + 1     # la guilde qui a confié
	assert magasin["value"] == base + 1      # la famille à qui l'on rend l'enfant


def test_une_escorte_confiee_par_le_parent_ne_paie_qu_une_fois(dbp):
	perso = character()
	_relation(dbp, perso, dbp["docs"]["lieu:athanor"],
			  character_stats.ESCORTE_PROGENITURE_RELATION_MIN)
	escorte_util.poser_escorte_offerte(perso, dbp["docs"]["lieu:athanor"], dbp["find"],
									   dbp["get"], rand_fn=_toujours(0.0),
									   pnj_doc=MARCHAND_PNJ, entree=MAGASIN["pnj"][0],
									   choix_fn=_premier)
	q, _docs = escorte_util.accepter_escorte(perso, perso["escorte_offerte"]["quete"],
											 dbp["get"], now=1)
	_mener_a_bien(dbp, perso, q)
	rel = dbp["docs"]["relation:" + perso["_id"] + "::lieu:athanor"]
	assert rel["value"] == character_stats.ESCORTE_PROGENITURE_RELATION_MIN + 1


def test_l_enfant_ramene_disparait_des_deux_canaux(dbp):
	perso = character()
	escorte_util.poser_escorte_offerte(perso, COMPTOIR, dbp["find"], dbp["get"],
									   rand_fn=_toujours(0.0), pnj_doc=BORIN,
									   choix_fn=_premier)
	q, _docs = escorte_util.accepter_escorte(perso, perso["escorte_offerte"]["quete"],
											 dbp["get"], now=1)
	prenom = q["proteges"][0]["prenom"]
	_mener_a_bien(dbp, perso, q)
	restants = escorte_util.enfants_a_retrouver(perso, "lieu:athanor", FAMILLE)
	assert prenom not in [e["prenom"] for e in restants]
	# Le père ne le redemande pas non plus : l'id est le même des deux côtés.
	assert escorte_util.deja_reussie(perso, escorte_util.id_enfant("lieu:athanor",
																   {"prenom": prenom}))


def test_une_escorte_en_cours_empeche_toute_autre_offre(dbp):
	perso = character()
	escorte_util.poser_escorte_offerte(perso, COMPTOIR, dbp["find"], dbp["get"],
									   rand_fn=_toujours(0.0), pnj_doc=BORIN,
									   choix_fn=_premier)
	escorte_util.accepter_escorte(perso, perso["escorte_offerte"]["quete"], dbp["get"], now=1)
	_relation(dbp, perso, dbp["docs"]["lieu:athanor"], 90)
	escorte_util.poser_escorte_offerte(perso, dbp["docs"]["lieu:athanor"], dbp["find"],
									   dbp["get"], rand_fn=_toujours(0.0),
									   pnj_doc=MARCHAND_PNJ, entree=MAGASIN["pnj"][0],
									   choix_fn=_premier)
	assert perso["escorte_offerte"]["quete"] is None


def test_escorte_vers_retrouve_la_quete_a_deposer_ici(dbp):
	perso = character()
	escorte_util.poser_escorte_offerte(perso, COMPTOIR, dbp["find"], dbp["get"],
									   rand_fn=_toujours(0.0), pnj_doc=BORIN,
									   choix_fn=_premier)
	q, _docs = escorte_util.accepter_escorte(perso, perso["escorte_offerte"]["quete"],
											 dbp["get"], now=1)
	# Chez le parent : c'est `escorte_vers` qui lui donne un mot, pas `escorte_du_donneur`
	# (le donneur, ici, c'est la guilde).
	assert escorte_util.escorte_vers(perso, "lieu:athanor")["id"] == q["id"]
	assert escorte_util.escorte_du_donneur(perso, "lieu:athanor") is None
	assert escorte_util.escorte_du_donneur(perso, "lieu:comptoir")["id"] == q["id"]


# ── Combat ───────────────────────────────────────────────────────────────────────

def protege_doc(pid="protege:aline", **champs):
	base = {
		"_id": pid, "type": "protege", "statut": "escorte",
		"escorte_par": "character:u_1", "quete": "quete:escorte_aline",
		"prenom": "Aline", "nom": "Varnepierre", "race": "humain", "sex": "F",
		"image": "druide_f_humain03.jpg",
		"caracteristiques_current": {"V": 5, "F": 20, "R": 20, "Ag": 20,
									 "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20},
		"currentPV": 80, "currentPM": 30,
		"inventaire": [], "slots": {}, "equipment_bonus": {}, "competences_bonus": {},
		"effets_actifs": [], "combats_recompenses": [], "jouable": False,
	}
	base.update(champs)
	return base


def protege_snap(jid="joueur_1", cid="protege:aline", x=1, y=1, pv=80, **champs):
	snap = joueur_snap(jid, cid, x=x, y=y, pv=pv, nom="Aline Varnepierre")
	snap.update({"jouable": False, "est_protege": True,
				 "deplacement": 0, "deplacement_base": 0})
	snap.update(champs)
	return snap


@pytest.fixture
def dbc(monkeypatch):
	"""DB en mémoire branchée sur combat + characters + escorte (finalisation)."""
	docs = {}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def find_docs_fn(selector, fields=None):
		return [d for d in docs.values()
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	monkeypatch.setattr(combat_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(combat_util, "save_doc", save_doc_fn)
	monkeypatch.setattr(combat_util, "find_docs", find_docs_fn)
	monkeypatch.setattr(characters_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(character_stats, "ESCORTE_MORT_DEFINITIVE", True)
	return docs


def test_protege_snapshote_mais_hors_initiative(dbc):
	doc = combat_util.create_combat_doc(combat_character(), [monstre_snap()], [], "",
										proteges=[protege_doc()])
	assert [j["id"] for j in doc["joueurs"]] == ["joueur_0", "joueur_1"]
	assert doc["joueurs"][1]["character_id"] == "protege:aline"
	assert doc["joueurs"][1]["jouable"] is False
	assert doc["joueurs"][1]["est_protege"] is True
	assert doc["joueurs"][1]["deplacement"] == 0
	assert set(doc["ordre_initiative"]) == {"joueur_0", "monstre_0"}


def test_sans_protege_le_combat_est_inchange(dbc):
	doc = combat_util.create_combat_doc(combat_character(), [monstre_snap()], [], "")
	assert [j["id"] for j in doc["joueurs"]] == ["joueur_0"]
	assert doc["joueurs"][0].get("est_protege") is None


def test_protege_est_une_cible_valide(dbc):
	"""Tout l'enjeu : les monstres peuvent s'en prendre à elle."""
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0)
	prot = protege_snap(x=6, y=6)
	m = monstre_snap(x=7, y=7)
	doc = combat_doc([j0, prot], [m])
	assert combat_util._cible_joueur(doc, m)["id"] == "joueur_1"


def test_escortee_debout_n_empeche_pas_la_defaite(dbc):
	"""RÉGRESSION CRITIQUE (miroir des montures) : si elle comptait comme un survivant,
	la défaite ne serait jamais déclarée et le combat resterait bloqué."""
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=1)
	prot = protege_snap(x=1, y=1, pv=80)
	m = monstre_snap(x=0, y=1, cc=100, degats_cc="100D6")
	doc = combat_doc([j0, prot], [m])

	combat_util._do_attack_on(doc, m, j0)

	assert j0["currentPV"] == 0
	assert prot["currentPV"] == 80
	assert doc["status"] == "defaite"
	assert combat_util._combattants_vivants(doc) == []


def test_protege_abattu_marque_morte_et_ne_perd_pas_le_combat(dbc):
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=50)
	prot = protege_snap(x=1, y=1, pv=1)
	m = monstre_snap(x=1, y=2, cc=100, degats_cc="100D6")
	doc = combat_doc([j0, prot], [m])

	combat_util._do_attack_on(doc, m, prot)

	assert prot["currentPV"] == 0 and prot["morte"] is True
	assert doc["status"] == "active"
	assert any("La promesse n'aura pas tenu" in e["texte"] for e in doc["log"])


def test_finalize_protege_mort_archive_la_quete_en_echec(dbc):
	"""La mort fait ÉCHOUER l'escorte : quête archivée, personne hors du groupe,
	réputation en baisse chez le donneur."""
	q = {"id": "quete:escorte_aline", "titre": "Escorte : Aline", "rang": "F",
		 "giver": "lieu:temple", "objectif": {"type": "escorte", "cible": "lieu:athanor",
											  "quantite": 1},
		 "recompenses": {"xp": 40, "cuivre": 10000}, "rencontre_at": 1, "progress": 0}
	perso = combat_character(proteges=["protege:aline"], quetes_actives=[q],
							 quetes_terminees=[])
	prot = protege_doc()
	dbc[perso["_id"]] = perso
	dbc[prot["_id"]] = prot
	dbc["lieu:temple"] = dict(TEMPLE)
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	doc = combat_doc([j0, protege_snap(pv=0, morte=True)],
					 [monstre_snap(vivant=False)], status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)

	assert prot["statut"] == "morte"
	assert perso["proteges"] == []
	assert perso["quetes_actives"] == []
	assert perso["quetes_terminees"][0]["echec"] is True
	assert prot.get("xp_total", 0) == 0        # elle ne se bat pas : pas d'XP
	assert perso.get("affinites", {}) == {}    # ni affinité


def test_finalize_protege_survivante_garde_ses_pv(dbc):
	q = {"id": "quete:escorte_aline", "titre": "Escorte", "giver": "lieu:temple",
		 "objectif": {"type": "escorte", "cible": "lieu:athanor", "quantite": 1},
		 "recompenses": {}, "rencontre_at": 1}
	perso = combat_character(proteges=["protege:aline"], quetes_actives=[q])
	prot = protege_doc()
	dbc[perso["_id"]] = perso
	dbc[prot["_id"]] = prot
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	doc = combat_doc([j0, protege_snap(pv=42)], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)

	assert prot["currentPV"] == 42
	assert prot["statut"] == "escorte"
	assert perso["proteges"] == ["protege:aline"]
	assert len(perso["quetes_actives"]) == 1


def test_finalize_protege_idempotent(dbc):
	"""Une re-finalisation ne peut pas sanctionner deux fois."""
	q = {"id": "quete:escorte_aline", "titre": "Escorte", "giver": "lieu:temple",
		 "objectif": {"type": "escorte", "cible": "lieu:athanor", "quantite": 1},
		 "recompenses": {}, "rencontre_at": 1}
	perso = combat_character(proteges=["protege:aline"], quetes_actives=[q],
							 quetes_terminees=[])
	prot = protege_doc()
	dbc[perso["_id"]] = perso
	dbc[prot["_id"]] = prot
	dbc["lieu:temple"] = dict(TEMPLE)
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	doc = combat_doc([j0, protege_snap(pv=0, morte=True)],
					 [monstre_snap(vivant=False)], status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)
	combat_util.finalize_combat(doc)

	assert len(perso["quetes_terminees"]) == 1

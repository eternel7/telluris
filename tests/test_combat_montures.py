# tests/test_combat_montures.py
#
# Montures en combat (utils/combat.py) : elles suivent le groupe sur la carte, sont
# CIBLABLES, mais n'ont pas de tour et ne comptent pas dans la défaite. À 0 PV elles
# meurent et rendent leur cargaison au butin disponible. Mêmes conventions que
# test_combat_groupe.py : docs à la main, monkeypatch DB sur les modules.

import pytest

from models import character_stats
from utils import combat as combat_util
from utils import characters as characters_util
from utils import montures as montures_util

from tests.test_combat_groupe import (
	character, aventurier, joueur_snap, monstre_snap, combat_doc,
)


ANE = {
	"_id": "espece:ane", "type": "espece", "nom": "Âne", "image": "ane_transparent.png",
	"base_attributes": {
		"V": {"min": 4, "max": 4}, "F": {"min": 20, "max": 20}, "R": {"min": 30, "max": 30},
		"Ag": {"min": 15, "max": 15}, "Vol": {"min": 20, "max": 20}, "Int": {"min": 5, "max": 5},
		"Cha": {"min": 0, "max": 0}, "Ch": {"min": 0, "max": 0},
	},
	"tags": ["monture", "proie"],
	"proprietes": {"charge_mult": 4.0, "prix_cuivre": 80000},
}
SAC = {"_id": "item:sac", "type": "item", "nom": "Sac", "categorie": "contenant", "poids": 3}
ENCLUME = {"_id": "item:enclume", "type": "item", "nom": "Enclume", "categorie": "outil",
		   "poids": 90}


def monture(mid="monture:ane_1", **champs):
	"""Doc `monture:*` : miroir du character, sans vocation ni race."""
	base = {
		"_id": mid, "type": "monture", "espece": "espece:ane", "statut": "acquise",
		"acquise_par": "character:u_1", "nom": "Âne", "image": "ane_transparent.png",
		"caracteristiques_current": {"V": 4, "F": 20, "R": 30, "Ag": 15,
									 "Vol": 20, "Int": 5, "Cha": 0, "Ch": 0},
		"currentPV": 40, "currentPM": 5,
		"inventaire": [], "slots": {}, "equipment_bonus": {}, "competences_bonus": {},
		"effets_actifs": [], "combats_recompenses": [], "jouable": False,
	}
	base.update(champs)
	return base


def monture_snap(mid="joueur_2", cid="monture:ane_1", x=1, y=1, pv=40, **champs):
	snap = joueur_snap(mid, cid, x=x, y=y, pv=pv, nom="Âne")
	snap.update({"jouable": False, "est_monture": True, "deplacement": 0,
				 "deplacement_base": 0, "charge_max": 400})
	snap.update(champs)
	return snap


@pytest.fixture
def db(monkeypatch):
	docs = {d["_id"]: dict(d) for d in (ANE, SAC, ENCLUME)}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	monkeypatch.setattr(combat_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(combat_util, "save_doc", save_doc_fn)
	monkeypatch.setattr(characters_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(montures_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(character_stats, "MONTURE_MORT_DEFINITIVE", True)
	return docs


# ── Entrée en combat ─────────────────────────────────────────────────────────────

def test_monture_snapshotee_mais_hors_initiative(db):
	"""Elle est sur la carte (donc ciblable) mais n'obtient JAMAIS de tour."""
	doc = combat_util.create_combat_doc(character(), [monstre_snap()], [], "",
										compagnons=[aventurier()],
										montures=[monture()])
	assert [j["id"] for j in doc["joueurs"]] == ["joueur_0", "joueur_1", "joueur_2"]
	assert doc["joueurs"][2]["character_id"] == "monture:ane_1"
	assert doc["joueurs"][2]["jouable"] is False
	assert doc["joueurs"][2]["est_monture"] is True
	# L'ordre d'initiative ne contient QUE les jouables + les monstres.
	assert set(doc["ordre_initiative"]) == {"joueur_0", "joueur_1", "monstre_0"}


def test_monture_immobile(db):
	doc = combat_util.create_combat_doc(character(), [monstre_snap()], [], "",
										montures=[monture()])
	assert doc["joueurs"][1]["deplacement"] == 0
	assert doc["joueurs"][1]["deplacement_base"] == 0


def test_monture_porte_sa_charge_demultipliee(db):
	"""F=20 → charge_max_of 100, ×4 pour l'âne : c'est CETTE valeur que /collect borne."""
	doc = combat_util.create_combat_doc(character(), [monstre_snap()], [], "",
										montures=[monture()])
	assert doc["joueurs"][1]["charge_max"] == 400


def test_sans_monture_le_combat_est_inchange(db):
	"""Rétro-compat : l'argument est optionnel, rien ne bouge sans lui."""
	doc = combat_util.create_combat_doc(character(), [monstre_snap()], [], "")
	assert [j["id"] for j in doc["joueurs"]] == ["joueur_0"]
	assert doc["joueurs"][0].get("est_monture") is None


# ── Ciblage ──────────────────────────────────────────────────────────────────────

def test_monture_est_une_cible_valide(db):
	"""Un monstre s'en prend à elle si elle est la plus proche — c'est voulu."""
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0)
	mont = monture_snap(x=6, y=6)
	m = monstre_snap(x=7, y=7)
	doc = combat_doc([j0, mont], [m])
	assert combat_util._cible_joueur(doc, m)["id"] == "joueur_2"


# ── Défaite : LE piège ───────────────────────────────────────────────────────────

def _coup_qui_porte(monkeypatch):
	"""Force le jet à toucher, sans critique ni fumble.

	⚠️ `_hit_threshold` est clampé à 95 : même à cc 100 contre une cible immobile, un
	coup rate 5 % du temps. Les tests ci-dessous vérifient ce qui se passe APRÈS un
	coup porté (monture à terre, cargaison répandue, statut du combat) — laisser le
	hasard décider les rendrait intermittents, et le prochain appel à `random` ajouté
	ailleurs dans le moteur suffirait à les faire tomber."""
	monkeypatch.setattr(combat_util, "_resoudre_jet", lambda a, d, seuil: {
		"roll": 1, "seuil": seuil, "touche": True, "critique": False,
		"fumble": False, "mult_degats": 1})


def test_monture_debout_n_empeche_pas_la_defaite(db, monkeypatch):
	"""RÉGRESSION CRITIQUE : si la monture comptait comme un survivant, la défaite ne
	serait jamais déclarée et, plus personne ne pouvant jouer, le combat resterait
	bloqué pour toujours."""
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=1)
	mont = monture_snap(x=1, y=1, pv=40)
	m = monstre_snap(x=0, y=1, cc=100, degats_cc="100D6")
	doc = combat_doc([j0, mont], [m])

	_coup_qui_porte(monkeypatch)
	combat_util._do_attack_on(doc, m, j0)

	assert j0["currentPV"] == 0
	assert mont["currentPV"] == 40          # elle est indemne…
	assert doc["status"] == "defaite"       # …et pourtant c'est perdu


def test_combattants_vivants_exclut_la_monture(db):
	j0 = joueur_snap("joueur_0", "character:u_1", pv=0)
	mont = monture_snap(pv=40)
	doc = combat_doc([j0, mont], [monstre_snap()])
	# Ciblage : elle est vivante. Défaite : elle ne compte pas.
	assert [j["id"] for j in combat_util._joueurs_vivants(doc)] == ["joueur_2"]
	assert combat_util._combattants_vivants(doc) == []


def test_monture_morte_ne_termine_pas_le_combat(db, monkeypatch):
	"""Symétrique : abattre la bête ne fait pas perdre tant qu'il reste un combattant."""
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=50)
	mont = monture_snap(x=1, y=1, pv=1)
	m = monstre_snap(x=1, y=2, cc=100, degats_cc="100D6")
	doc = combat_doc([j0, mont], [m])

	_coup_qui_porte(monkeypatch)
	combat_util._do_attack_on(doc, m, mont)

	assert mont["currentPV"] == 0 and mont["morte"] is True
	assert doc["status"] == "active"
	assert any("charge se répand" in e["texte"] for e in doc["log"])


# ── Finalisation ─────────────────────────────────────────────────────────────────

def test_finalize_monture_morte_perdue_et_cargaison_au_sol(db):
	"""La cargaison ne disparaît pas avec la bête : elle se déverse au SOL du principal."""
	perso = character(montures=["monture:ane_1"])
	mont_doc = monture(inventaire=[{"item": "item:sac", "poids": 3},
								   {"item": "item:enclume", "poids": 90}])
	db[perso["_id"]] = perso
	db[mont_doc["_id"]] = mont_doc
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	snap = monture_snap(pv=0, morte=True)
	doc = combat_doc([j0, snap], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)

	assert mont_doc["statut"] == "morte"
	assert perso["montures"] == []          # retirée du troupeau
	assert mont_doc["inventaire"] == []
	# Les RÉFÉRENCES telles quelles : le détour par `butin_disponible` les reconstruisait en
	# `{item, poids}` et perdait au passage un éventuel `lieu_parent`.
	assert perso["objets_au_sol"] == [{"item": "item:sac", "poids": 3},
									  {"item": "item:enclume", "poids": 90}]
	# Et surtout PLUS dans le butin de victoire, qui n'aurait rien rendu sur une défaite.
	# (Celui-ci ne porte que la carcasse du monstre abattu, ce qui est sa raison d'être.)
	assert [d["item_id"] for d in doc["butin_disponible"]] == ["item:rat"]


def test_finalize_monture_morte_verse_au_sol_MEME_en_defaite(db):
	"""Le cas qui a motivé le changement : `butin_disponible` n'est proposé qu'à la victoire,
	si bien qu'une défaite emportait la cargaison. La bête tombe là où elle tombe."""
	perso = character(montures=["monture:ane_1"])
	mont_doc = monture(inventaire=[{"item": "item:enclume", "poids": 90}])
	db[perso["_id"]] = perso
	db[mont_doc["_id"]] = mont_doc
	j0 = joueur_snap("joueur_0", perso["_id"], pv=0)
	doc = combat_doc([j0, monture_snap(pv=0, morte=True)], [monstre_snap()],
					 status="defaite", xp_gagnee=0)

	combat_util.finalize_combat(doc)

	assert perso["objets_au_sol"] == [{"item": "item:enclume", "poids": 90}]


def test_finalize_monture_le_sol_deja_occupe_est_complete(db):
	"""Le sol appartient au lieu où l'on se tient : ce qu'on y avait posé reste dessous."""
	perso = character(montures=["monture:ane_1"])
	perso["objets_au_sol"] = [{"item": "item:corde", "poids": 2}]
	mont_doc = monture(inventaire=["item:sac"])   # réf legacy en chaîne nue : conservée telle quelle
	db[perso["_id"]] = perso
	db[mont_doc["_id"]] = mont_doc
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	doc = combat_doc([j0, monture_snap(pv=0, morte=True)], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)

	assert perso["objets_au_sol"] == [{"item": "item:corde", "poids": 2}, "item:sac"]


def test_finalize_monture_ne_gagne_pas_d_xp(db):
	"""Elle porte, elle ne se bat pas."""
	perso = character(montures=["monture:ane_1"])
	mont_doc = monture()
	db[perso["_id"]] = perso
	db[mont_doc["_id"]] = mont_doc
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	doc = combat_doc([j0, monture_snap(pv=25)], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)

	assert perso["xp_total"] == 10
	assert mont_doc.get("xp_total", 0) == 0
	assert mont_doc["currentPV"] == 25      # PV du combat reportés
	assert perso["montures"] == ["monture:ane_1"]


def test_finalize_monture_survivante_relevee_a_1(db):
	"""Tombée à 0 sans que la mort définitive soit active : simple KO."""
	perso = character(montures=["monture:ane_1"])
	mont_doc = monture()
	db[perso["_id"]] = perso
	db[mont_doc["_id"]] = mont_doc
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	# `morte` non posé (mort désactivée au moment du KO) → branche survivante.
	doc = combat_doc([j0, monture_snap(pv=0)], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)

	assert mont_doc["currentPV"] == 1
	assert perso["montures"] == ["monture:ane_1"]


def test_finalize_monture_idempotent(db):
	"""Une re-finalisation ne ressuscite pas la bête ni ne duplique sa cargaison."""
	perso = character(montures=["monture:ane_1"])
	mont_doc = monture(inventaire=[{"item": "item:sac", "poids": 3}])
	db[perso["_id"]] = perso
	db[mont_doc["_id"]] = mont_doc
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	doc = combat_doc([j0, monture_snap(pv=0, morte=True)],
					 [monstre_snap(vivant=False)], status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)
	nb_cargo = len(perso["objets_au_sol"])
	combat_util.finalize_combat(doc)

	assert nb_cargo == 1
	assert len(perso["objets_au_sol"]) == 1


def test_finalize_monture_pas_d_affinite(db):
	"""Une monture n'a pas d'affinité : le doc du joueur ne doit pas en créer une."""
	perso = character(montures=["monture:ane_1"])
	mont_doc = monture()
	db[perso["_id"]] = perso
	db[mont_doc["_id"]] = mont_doc
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	doc = combat_doc([j0, monture_snap(pv=40)], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)

	combat_util.finalize_combat(doc)

	assert perso["affinites"] == {}

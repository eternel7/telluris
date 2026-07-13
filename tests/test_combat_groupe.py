# tests/test_combat_groupe.py
#
# Combat de groupe (utils/combat.py) : snapshots multiples, ciblage IA du joueur le
# plus proche, défaite seulement TOUS à terre, tours des KO sautés, finalize multi-docs
# idempotent (compagnons `aventurier:*` d'abord, principal en dernier). Docs à la main,
# monkeypatch DB sur les modules (pattern test_recrutement / test_quetes_board).

import pytest

from models import character_stats
from utils import combat as combat_util
from utils import characters as characters_util


# ── Monde de test ────────────────────────────────────────────────────────────────

def character(cid="character:u_1", **champs):
	base = {
		"_id": cid, "type": "character", "user_id": "user:u",
		"prenom": "Test", "nom": "Héros", "voc": "guerrier", "race": "humain",
		"image": "guerrier_m_humain01.jpg",
		"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 30,
									 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
		"currentPV": 50, "currentPM": 20,
		"vocations_niveaux": {"guerrier": 0}, "xp_total": 0, "attribute_points": 0,
		"inventaire": [], "slots": {}, "equipment_bonus": {},
		"sorts_connus": [], "competences_connues": [], "competences_bonus": {},
		"effets_actifs": [], "or": 0, "argent": 0, "cuivre": 0,
		"combats_recompenses": [], "quetes_actives": [], "affinites": {},
	}
	base.update(champs)
	return base


def aventurier(aid="aventurier:guilde_ami", **champs):
	av = character(aid, type="aventurier", prenom="Aldric", nom="Ferrant",
				   statut="embauche", embauche_par="character:u_1", giver="lieu:guilde")
	av.update(champs)
	return av


def joueur_snap(jid, cid, x=0, y=0, pv=50, **champs):
	base = {
		"id": jid, "character_id": cid, "nom": jid, "currentPV": pv, "pv_max": 50,
		"currentPM": 20, "pm_max": 20, "ag": 30, "esquive": 0, "pa": 1,
		"initiative": 40, "actions_restantes": 2, "actions_max": 2,
		"deplacement": 5, "deplacement_base": 5, "cells_moved": 0,
		"attaques": 0, "ramasses": 0, "consommes": 0, "sorts": 0, "competences": 0,
		"charge": 0, "charge_max": 150, "furtif": False, "furtivite_bonus": 0,
		"butin_ramasse": [], "pos": {"x": x, "y": y}, "facing": 0,
	}
	base.update(champs)
	return base


def monstre_snap(mid="monstre_0", x=5, y=5, **champs):
	base = {
		"id": mid, "nom": mid, "espece_id": "espece:rat", "profil_id": None,
		"currentPV": 10, "pv_max": 10, "cc": 40, "ag": 20, "vol": 20, "int": 10,
		"pa": 0, "pm_def": 5, "degats_cc": "1D4", "initiative": 20,
		"deplacement": 3, "portee": 1, "actions_restantes": 2, "actions_max": 2,
		"cells_moved": 0, "attaques": 0, "vivant": True, "tags": [],
		"detecte": False, "xp_reward": 10, "niveau": 1, "pos": {"x": x, "y": y},
	}
	base.update(champs)
	return base


def combat_doc(joueurs, monstres, **champs):
	ordre = [j["id"] for j in joueurs] + [m["id"] for m in monstres]
	base = {
		"_id": "combat:test", "type": "combat", "user_id": "user:u",
		"character_id": "character:u_1", "status": "active", "tour": 1,
		"ordre_initiative": ordre, "acteur_courant_index": 0,
		"zone_tags": [], "map_image": "", "joueurs": joueurs, "monstres": monstres,
		"log": [], "xp_gagnee": 0,
		"grid_dims": {"x": 13, "y": 11},
	}
	base.update(champs)
	return base


@pytest.fixture
def db(monkeypatch):
	"""Base en mémoire branchée sur combat + characters (snapshots, finalize)."""
	docs = {}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	monkeypatch.setattr(combat_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(combat_util, "save_doc", save_doc_fn)
	monkeypatch.setattr(characters_util, "get_doc", get_doc_fn)
	return docs


# ── create_combat_doc avec compagnons ────────────────────────────────────────────

def test_create_combat_doc_snapshots_du_groupe(db):
	perso = character()
	comp = aventurier()
	doc = combat_util.create_combat_doc(perso, [monstre_snap()], [], "",
										compagnons=[comp])
	assert [j["id"] for j in doc["joueurs"]] == ["joueur_0", "joueur_1"]
	assert doc["joueurs"][0]["character_id"] == "character:u_1"
	assert doc["joueurs"][1]["character_id"] == "aventurier:guilde_ami"
	assert set(doc["ordre_initiative"]) == {"joueur_0", "joueur_1", "monstre_0"}
	# Tous placés sur des cases distinctes.
	positions = {(j["pos"]["x"], j["pos"]["y"]) for j in doc["joueurs"]}
	assert len(positions) == 2


def test_furtivite_initiale_sur_le_principal_seul(db):
	doc = combat_util.create_combat_doc(character(), [monstre_snap()], [], "",
										furtivite_initiale=10,
										compagnons=[aventurier()])
	assert doc["joueurs"][0]["furtif"] is True
	assert doc["joueurs"][1]["furtif"] is False


# ── Ciblage IA ───────────────────────────────────────────────────────────────────

def test_cible_joueur_le_plus_proche(db):
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", x=4, y=4)
	m = monstre_snap(x=5, y=5)
	doc = combat_doc([j0, j1], [m])
	assert combat_util._cible_joueur(doc, m)["id"] == "joueur_1"


def test_cible_joueur_ignore_les_ko(db):
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", x=4, y=4, pv=0)
	m = monstre_snap(x=5, y=5)
	doc = combat_doc([j0, j1], [m])
	assert combat_util._cible_joueur(doc, m)["id"] == "joueur_0"


def test_cible_joueur_exclut_le_furtif_non_detecte(db):
	j0 = joueur_snap("joueur_0", "character:u_1", x=4, y=4, furtif=True)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", x=0, y=0)
	m = monstre_snap(x=5, y=5)
	doc = combat_doc([j0, j1], [m])
	# Le furtif est pourtant plus proche : le monstre vise le compagnon visible.
	assert combat_util._cible_joueur(doc, m)["id"] == "joueur_1"
	# Détecté, il redevient la cible la plus proche.
	m["detecte"] = True
	assert combat_util._cible_joueur(doc, m)["id"] == "joueur_0"


def test_cible_joueur_none_si_tous_furtifs_ou_ko(db):
	j0 = joueur_snap("joueur_0", "character:u_1", furtif=True)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", pv=0)
	m = monstre_snap()
	doc = combat_doc([j0, j1], [m])
	assert combat_util._cible_joueur(doc, m) is None


# ── Défaite = TOUS à terre ───────────────────────────────────────────────────────

def _force_hits(monkeypatch):
	"""Jets d100 toujours à 1 (touché garanti) et dés de dégâts au maximum."""
	monkeypatch.setattr(combat_util.random, "randint", lambda a, b: 1 if b == 100 else b)


def test_ko_dun_membre_ne_defait_pas_le_groupe(db, monkeypatch):
	_force_hits(monkeypatch)
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=1)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", x=9, y=9)
	m = monstre_snap(x=1, y=1, degats_cc="1D100")
	doc = combat_doc([j0, j1], [m])
	combat_util._do_attack_on(doc, m, j0)
	assert j0["currentPV"] == 0
	assert doc["status"] == "active"
	assert any("à terre" in l["texte"] for l in doc["log"])


def test_defaite_quand_le_dernier_tombe(db, monkeypatch):
	_force_hits(monkeypatch)
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=0)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", x=1, y=0, pv=1)
	m = monstre_snap(x=1, y=1, degats_cc="1D100")
	doc = combat_doc([j0, j1], [m])
	combat_util._do_attack_on(doc, m, j1)
	assert doc["status"] == "defaite"


def test_monstre_se_rabat_sur_le_suivant_apres_un_ko(db, monkeypatch):
	"""La cible tombe en cours de tour : le monstre re-résout et frappe le voisin."""
	_force_hits(monkeypatch)
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=1)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", x=2, y=0, pv=50)
	m = monstre_snap(x=1, y=0, degats_cc="1D10", actions_restantes=3, actions_max=3)
	doc = combat_doc([j0, j1], [m], acteur_courant_index=2)
	grid = combat_util.get_combat_grid(doc)
	combat_util._run_monster_turn(doc, m, grid)
	assert j0["currentPV"] == 0
	assert j1["currentPV"] < 50  # le second coup est parti sur le compagnon


# ── Tours des KO sautés ──────────────────────────────────────────────────────────

def test_resolve_until_player_saute_les_joueurs_ko(db):
	j0 = joueur_snap("joueur_0", "character:u_1", x=0, y=0, pv=0)
	j1 = joueur_snap("joueur_1", "aventurier:guilde_ami", x=1, y=0)
	doc = combat_doc([j0, j1], [], acteur_courant_index=0)
	grid = combat_util.get_combat_grid(doc)
	combat_util._resolve_until_player(doc, grid, start_at_current=True)
	assert doc["ordre_initiative"][doc["acteur_courant_index"]] == "joueur_1"


def test_resolve_action_refuse_un_joueur_a_terre(db):
	j0 = joueur_snap("joueur_0", "character:u_1", pv=0)
	doc = combat_doc([j0], [monstre_snap()])
	res = combat_util.resolve_action(doc, "passer")
	assert "à terre" in res["error"]


# ── finalize_combat multi-docs ───────────────────────────────────────────────────

def test_finalize_applique_a_tous_les_docs(db, monkeypatch):
	monkeypatch.setattr(character_stats, "AFFINITE_DELTA_VICTOIRE", 1)
	monkeypatch.setattr(character_stats, "AFFINITE_DELTA_KO", -5)
	perso = character()
	comp = aventurier()
	db[perso["_id"]] = perso
	db[comp["_id"]] = comp
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30,
					 butin_ramasse=[{"item": "item:rat", "poids": 2}])
	j1 = joueur_snap("joueur_1", comp["_id"], pv=0)  # compagnon KO
	doc = combat_doc([j0, j1], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)
	assert combat_util.finalize_combat(doc) is True
	assert perso["currentPV"] == 30 and perso["xp_total"] == 10
	assert {"item": "item:rat", "poids": 2} in perso["inventaire"]
	assert comp["currentPV"] == 1 and comp["xp_total"] == 10  # KO relevé, XP pleine
	assert doc["_id"] in perso["combats_recompenses"]
	assert doc["_id"] in comp["combats_recompenses"]
	# Affinité : +1 (victoire) −5 (KO) = −4 sous le neutre.
	assert perso["affinites"][comp["_id"]] == 50 + 1 - 5


def test_finalize_idempotent_par_doc(db):
	perso = character()
	comp = aventurier()
	db[perso["_id"]] = perso
	db[comp["_id"]] = comp
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	j1 = joueur_snap("joueur_1", comp["_id"], pv=30)
	doc = combat_doc([j0, j1], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)
	assert combat_util.finalize_combat(doc) is True
	assert combat_util.finalize_combat(doc) is False
	assert perso["xp_total"] == 10 and comp["xp_total"] == 10  # pas de double


def test_finalize_compagnon_rattrape_si_deja_servi(db):
	"""Le compagnon a déjà touché sa récompense (finalize partiel) : un second passage
	ne le double pas mais sert le principal."""
	perso = character()
	comp = aventurier(combats_recompenses=["combat:test"], xp_total=10)
	db[perso["_id"]] = perso
	db[comp["_id"]] = comp
	j0 = joueur_snap("joueur_0", perso["_id"], pv=30)
	j1 = joueur_snap("joueur_1", comp["_id"], pv=30)
	doc = combat_doc([j0, j1], [monstre_snap(vivant=False)],
					 status="victoire", xp_gagnee=10)
	assert combat_util.finalize_combat(doc) is True
	assert comp["xp_total"] == 10  # inchangé
	assert perso["xp_total"] == 10


def test_finalize_defaite_releve_tout_le_monde_a_1(db):
	perso = character()
	comp = aventurier()
	db[perso["_id"]] = perso
	db[comp["_id"]] = comp
	j0 = joueur_snap("joueur_0", perso["_id"], pv=0)
	j1 = joueur_snap("joueur_1", comp["_id"], pv=0)
	doc = combat_doc([j0, j1], [monstre_snap()], status="defaite")
	combat_util.finalize_combat(doc)
	assert perso["currentPV"] == 1 and comp["currentPV"] == 1

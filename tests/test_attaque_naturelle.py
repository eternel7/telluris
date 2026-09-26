# tests/test_attaque_naturelle.py
#
# Attaque NATURELLE des créatures non humanoïdes : un dé de Force supplémentaire au corps
# à corps (`MONSTRE_DES_CC_NATURELS`). Une bête n'a pas d'arme à équiper — ses crocs SONT
# son armement —, là où un humanoïde tire ses dégâts de ce qu'il tient.
#
# Le point sensible n'est pas le calcul, c'est sa SURVIE : `_refresh_snapshot_stats`
# recompose `degats_cc` à chaque effet posé ou expiré. Sans `des_cc_base` sur le snapshot,
# le premier debuff venu retirerait le dé en silence, pour le reste du combat.

import pytest

from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats
from utils import combat as combat_mod
from utils import characters as characters_mod


# ── Fabriques ────────────────────────────────────────────────────────────────────

def espece(tags=(), f=24):
	"""Espèce à fourchettes DÉGÉNÉRÉES (min == max) : `_espece_midpoint` en tire une valeur
	déterministe, donc la notation de dégâts est reproductible."""
	return {
		"_id": "espece:test", "nom": "Cobaye", "tags": list(tags),
		"base_attributes": {
			"V": {"min": 5, "max": 5}, "F": {"min": f, "max": f},
			"R": {"min": 20, "max": 20}, "Ag": {"min": 20, "max": 20},
			"Vol": {"min": 10, "max": 10}, "Int": {"min": 10, "max": 10},
			"Cha": {"min": 10, "max": 10}, "Ch": {"min": 10, "max": 10},
		},
	}


def base(f=24):
	return BaseStats(v=5, f=f, r=20, ag=20, vol=10, int_=10, cha=10, ch=10)


# ── Le prédicat : SEUL point de décision ─────────────────────────────────────────

def test_une_espece_sans_tag_humanoide_gagne_un_de():
	assert combat_mod.des_cc_espece(espece(["predateur"])) == 2
	assert combat_mod.des_cc_espece(espece([])) == 2
	assert combat_mod.des_cc_espece({}) == 2


def test_une_espece_humanoide_garde_UN_seul_de():
	"""Un bandit frappe avec son arme : lui donner le dé naturel en plus le ferait cogner
	deux fois plus fort que le joueur qu'il singe."""
	assert combat_mod.des_cc_espece(espece(["humanoide", "predateur"])) == 1


def test_le_tag_a_UNE_seule_source():
	"""Le paperdoll du simulateur et l'attaque naturelle décident sur le MÊME tag. Deux
	chaînes en dur finiraient par diverger, et le banc habillerait une bête qui garderait
	quand même ses crocs."""
	from utils import simulateur
	assert simulateur.TAG_EQUIPABLE == character_stats.TAG_HUMANOIDE


# ── La notation produite ─────────────────────────────────────────────────────────

def test_compute_derived_stats_defaut_inchange():
	"""⚠️ `des_cc` par défaut à 1 : aucun des appelants existants (joueur, compagnon,
	monture, fiche) ne change de comportement."""
	assert compute_derived_stats(base(), niveau=1).degats_cc == "1D5+1"


def test_le_de_supplementaire_est_de_la_MEME_taille():
	"""« un dé correspondant à `_caract_to_dice_(base.f)` » : on double le dé de Force, on
	n'en ajoute pas un d'une autre taille."""
	assert compute_derived_stats(base(f=24), niveau=1, des_cc=2).degats_cc == "2D5+1"
	# F=15 → dé D4 et bonus plat 15//20 = 0, que `_format_damage` n'écrit pas.
	assert compute_derived_stats(base(f=15), niveau=1, des_cc=2).degats_cc == "2D4"
	assert compute_derived_stats(base(f=95), niveau=1, des_cc=2).degats_cc == "2D25+4"


def test_le_TIR_n_est_jamais_concerne():
	"""Les monstres n'attaquent qu'au contact (cf. CLAUDE.md § Attaques par mode) : le dé
	naturel ne doit pas fuir dans `degats_cd`, qui suit l'Ag."""
	d = compute_derived_stats(base(), niveau=1, des_cc=2)
	assert d.degats_cd == compute_derived_stats(base(), niveau=1).degats_cd


def test_zero_de_est_planche_a_un():
	"""Une attaque sans le moindre dé ne serait plus une attaque."""
	assert compute_derived_stats(base(), niveau=1, des_cc=0).degats_cc == "1D5+1"


# ── Le snapshot ──────────────────────────────────────────────────────────────────

def test_snapshot_de_bete_porte_deux_des_et_le_champ_de_recalcul():
	snap = combat_mod.build_monster_snapshot(espece(["predateur"]), None, 0)
	assert snap["degats_cc"] == "2D5+1"
	assert snap["des_cc_base"] == 2


def test_snapshot_dhumanoide_inchange():
	snap = combat_mod.build_monster_snapshot(espece(["humanoide"]), None, 0)
	assert snap["degats_cc"] == "1D5+1"
	assert snap["des_cc_base"] == 1


# ── LE point sensible : survivre au recalcul ─────────────────────────────────────

def test_le_de_naturel_SURVIT_a_un_buff_puis_a_son_expiration():
	"""`_refresh_snapshot_stats` recompose `degats_cc` depuis `caracts_base`. Sans
	`des_cc_base` repassé, le monstre perdrait son dé au premier effet — et ne le
	retrouverait jamais."""
	snap = combat_mod.build_monster_snapshot(espece(["predateur"]), None, 0)
	snap["effets_actifs"] = [{"nom": "Rage", "buffs": {"F": 20}, "restants": 2}]
	combat_mod._refresh_snapshot_stats(snap)
	assert snap["degats_cc"] == "2D8+2"   # F 24→44 : le dé grandit (D5→D8), ils restent DEUX
	snap["effets_actifs"] = []
	combat_mod._refresh_snapshot_stats(snap)
	assert snap["degats_cc"] == "2D5+1"


def test_un_DEBUFF_ne_retire_pas_le_de_naturel():
	snap = combat_mod.build_monster_snapshot(espece(["predateur"]), None, 0)
	snap["effets_actifs"] = [{"nom": "Faiblesse", "buffs": {"F": -10}, "restants": 3}]
	combat_mod._refresh_snapshot_stats(snap)
	assert snap["degats_cc"].startswith("2D")


def test_un_snapshot_SANS_le_champ_garde_le_comportement_davant():
	"""Aucune migration : un combat déjà en base n'a pas `des_cc_base` → 1 dé, exactement
	ce qu'il affichait avant la feature."""
	snap = combat_mod.build_monster_snapshot(espece(["predateur"]), None, 0)
	del snap["des_cc_base"]
	combat_mod._refresh_snapshot_stats(snap)
	assert snap["degats_cc"] == "1D5+1"


def test_un_joueur_ne_gagne_jamais_le_de_naturel():
	"""`build_joueur_snapshot` ne pose pas `des_cc_base` → le recalcul retombe sur 1."""
	from tests.test_combat_groupe import character as combat_character
	snap = combat_mod.build_joueur_snapshot(combat_character(), 0)
	avant = snap["degats_cc"]
	combat_mod._refresh_snapshot_stats(snap)
	assert snap["degats_cc"] == avant
	assert snap["degats_cc"].startswith("1D")


# ── Kill-switch ─────────────────────────────────────────────────────────────────

def test_la_world_var_a_UN_restaure_le_comportement_davant(monkeypatch):
	monkeypatch.setattr(character_stats, "MONSTRE_DES_CC_NATURELS", 1)
	snap = combat_mod.build_monster_snapshot(espece(["predateur"]), None, 0)
	assert snap["des_cc_base"] == 1
	assert snap["degats_cc"] == "1D5+1"


def test_la_world_var_est_lue_A_CHAUD(monkeypatch):
	"""⚠️ Lue par `character_stats.MONSTRE_DES_CC_NATURELS` et jamais par un `from … import`,
	sinon le réglage depuis /admin n'aurait aucun effet."""
	monkeypatch.setattr(character_stats, "MONSTRE_DES_CC_NATURELS", 3)
	assert combat_mod.des_cc_espece(espece(["predateur"])) == 3
	assert combat_mod.build_monster_snapshot(espece(["predateur"]), None, 0)["degats_cc"] == "3D5+1"


# ── Équipement d'un humanoïde (roll_monster_equipment câblé dans le snapshot) ────

ARC_COURT = {
	"_id": "item:Arc_court", "type": "item", "nom": "Arc court", "categorie": "arme",
	"slots": ["main_droite"], "tags": ["tir"], "portee": 4, "deux_mains": True,
	"bonus_degats": 0, "bonus_cd": 0,
}
CUIRASSE_CUIR = {
	"_id": "item:Cuir_bouilli", "type": "item", "nom": "Cuir bouilli", "categorie": "armure",
	"slots": ["torse"], "bonus_pa": 5,
}


def _toujours_equiper(monkeypatch, catalogue):
	monkeypatch.setattr(combat_mod.random, "random", lambda: 0.0)
	monkeypatch.setattr(combat_mod.random, "shuffle", lambda l: None)
	monkeypatch.setattr(combat_mod.random, "choice", lambda opts: opts[0])
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: catalogue.get(i))
	monkeypatch.setattr(characters_mod, "get_doc", lambda i: catalogue.get(i))


def test_humanoide_sans_items_conserve_le_comportement_dactuel():
	snap = combat_mod.build_monster_snapshot(espece(["humanoide"]), None, 0)
	assert snap["portee"] == 1
	assert snap["degats_cc"] == "1D5+1"
	assert "slots" not in snap
	assert "attaque_profils" not in snap
	assert "sorts_connus" not in snap


def test_humanoide_avec_arc_devient_a_distance(monkeypatch):
	catalogue = {ARC_COURT["_id"]: ARC_COURT}
	_toujours_equiper(monkeypatch, catalogue)
	e = espece(["humanoide"])
	e["items"] = [ARC_COURT["_id"]]
	snap = combat_mod.build_monster_snapshot(e, None, 0)
	assert snap["slots"] == {"main_droite": ARC_COURT["_id"]}
	tir = next(a for a in snap["attaque_profils"] if a["mode"] == "tir")
	assert tir["ranged"] is True
	assert tir["portee"] == 4
	assert snap["portee"] == 4


def test_espece_non_humanoide_ignore_items(monkeypatch):
	catalogue = {ARC_COURT["_id"]: ARC_COURT}
	_toujours_equiper(monkeypatch, catalogue)
	e = espece(["predateur"])
	e["items"] = [ARC_COURT["_id"]]
	snap = combat_mod.build_monster_snapshot(e, None, 0)
	assert snap["portee"] == 1
	assert "slots" not in snap
	assert "attaque_profils" not in snap


def test_armure_roulee_peuple_pa_zones(monkeypatch):
	catalogue = {CUIRASSE_CUIR["_id"]: CUIRASSE_CUIR}
	_toujours_equiper(monkeypatch, catalogue)
	e = espece(["humanoide"])
	e["items"] = [CUIRASSE_CUIR["_id"]]
	sans_armure = combat_mod.build_monster_snapshot(espece(["humanoide"]), None, 0)
	avec_armure = combat_mod.build_monster_snapshot(e, None, 0)
	assert avec_armure["pa_zones"]
	assert avec_armure["pa"] > sans_armure["pa"]


# ── Sorts attribués à la création (roll_monster_sorts) ───────────────────────────

SORT_FLAMME = {
	"_id": "sort:jet_flammes", "type": "sort", "nom": "Jet de flammes", "magie": "feu",
	"niveau": 1, "cout_pm": 3,
}
SORT_METEORE = {
	"_id": "sort:meteore", "type": "sort", "nom": "Météore", "magie": "feu",
	"niveau": 5, "cout_pm": 20,
}


def test_roll_monster_sorts_borne_au_pool(monkeypatch):
	pool = [SORT_FLAMME, SORT_METEORE]
	monkeypatch.setattr(combat_mod, "find_docs", lambda q: pool)
	monkeypatch.setattr(combat_mod.random, "sample", lambda pop, k: pop[:k])
	e = {"_id": "espece:test", "tags": ["humanoide"], "magies": {"feu": 5}}
	assert combat_mod.roll_monster_sorts(e, niveau=5) == [SORT_FLAMME["_id"], SORT_METEORE["_id"]]
	assert len(combat_mod.roll_monster_sorts(e, niveau=1)) == 1


def test_roll_monster_sorts_niveau_zero():
	e = {"_id": "espece:test", "tags": ["humanoide"], "magies": {"feu": 5}}
	assert combat_mod.roll_monster_sorts(e, niveau=0) == []


def test_build_monster_snapshot_stocke_sorts_connus_sans_les_lancer(monkeypatch):
	monkeypatch.setattr(combat_mod, "find_docs", lambda q: [SORT_FLAMME])
	monkeypatch.setattr(combat_mod.random, "sample", lambda pop, k: pop[:k])
	e = espece(["humanoide"])
	e["magies"] = {"feu": 5}
	snap = combat_mod.build_monster_snapshot(e, {"_id": "profil:test", "niveau": 1}, 0)
	assert snap["sorts_connus"] == [SORT_FLAMME["_id"]]
	assert snap["currentPM"] == snap["pm_max"]

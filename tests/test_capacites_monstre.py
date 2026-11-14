# tests/test_capacites_monstre.py
#
# Magie et capacités PROPRES des monstres (utils/capacites_monstre.py) :
# - sorts tirés par TAG d'espèce `magie_<école>_<niveau>[_<profil>]`, toute espèce ;
# - compétences innées (`espece.competences`, docs `competence:*` de vocation `monstre`) :
#   passives permanentes (régénération) et venin posé à l'impact de l'attaque naturelle.

import pytest

from utils import capacites_monstre as cm
from utils import combat as combat_mod
from utils.sorts import sorts_eligibles_espece


# ── Tags `magie_*` ────────────────────────────────────────────────────────────────

def test_slug_ecole_retire_accents_et_casse():
	assert cm.slug_ecole("Élémentaire") == "elementaire"
	assert cm.slug_ecole("Démonologie") == "demonologie"
	assert cm.slug_ecole(None) == ""


def test_tag_sans_profil_vaut_pour_tous():
	assert cm.magies_de_tags(["magie_nature_2"], "profil:mage") == {"nature": 2}
	assert cm.magies_de_tags(["magie_nature_2"], None) == {"nature": 2}


def test_tag_suffixe_ne_vaut_que_pour_son_profil():
	tags = ["magie_elementaire_2_apprenti", "magie_elementaire_8_heros_mage"]
	assert cm.magies_de_tags(tags, "profil:apprenti") == {"elementaire": 2}
	# Le profil contient lui-même un `_` : c'est tout le reste du tag.
	assert cm.magies_de_tags(tags, "profil:heros_mage") == {"elementaire": 8}
	assert cm.magies_de_tags(tags, "profil:mage") == {}


def test_plafond_le_plus_haut_par_ecole():
	tags = ["magie_necromancie_3", "magie_necromancie_6_mage", "magie_sainte_1"]
	assert cm.magies_de_tags(tags, "profil:mage") == {"necromancie": 6, "sainte": 1}
	assert cm.magies_de_tags(tags, "profil:novice") == {"necromancie": 3, "sainte": 1}


def test_tag_mal_forme_ignore():
	tags = ["magie_", "magie_nature", "magie_nature_x", "Magie_Nature_2", "magique", "vol"]
	assert cm.magies_de_tags(tags, "profil:mage") == {}


SORTS = [
	{"_id": "sort:flammerole", "type": "sort", "nom": "Flammerole", "magie": "Élémentaire",
	 "niveau": 1, "cout_pm": 3},
	{"_id": "sort:meteore", "type": "sort", "nom": "Météore", "magie": "Élémentaire",
	 "niveau": 7, "cout_pm": 30},
	{"_id": "sort:ronces", "type": "sort", "nom": "Ronces", "magie": "Nature",
	 "niveau": 1, "cout_pm": 3},
]


def _ids(pool):
	return sorted(s["id"] for s in pool)


def test_pool_par_profil_depuis_les_tags():
	espece = {"tags": ["magie_elementaire_2_apprenti", "magie_elementaire_8_mage"]}
	find = lambda sel: SORTS
	assert _ids(sorts_eligibles_espece(espece, lambda i: None, find, "profil:apprenti")) == ["sort:flammerole"]
	assert _ids(sorts_eligibles_espece(espece, lambda i: None, find, "profil:mage")) == ["sort:flammerole", "sort:meteore"]
	assert sorts_eligibles_espece(espece, lambda i: None, find, "profil:novice") == []


def test_carte_magies_et_tags_fusionnees():
	"""`magies` (libellé accentué) et tags (slug) désignent la même école."""
	espece = {"magies": {"Élémentaire": 1}, "tags": ["magie_nature_1"]}
	pool = sorts_eligibles_espece(espece, lambda i: None, lambda sel: SORTS, None)
	assert _ids(pool) == ["sort:flammerole", "sort:ronces"]


def test_un_non_humanoide_tire_ses_sorts(monkeypatch):
	monkeypatch.setattr(combat_mod, "find_docs", lambda q: SORTS)
	monkeypatch.setattr(combat_mod.random, "sample", lambda pop, k: pop[:k])
	e = _espece(tags=["magique", "magie_elementaire_1"])
	snap = combat_mod.build_monster_snapshot(e, {"_id": "profil:apprenti", "niveau": 2}, 0)
	assert snap["sorts_connus"] == ["sort:flammerole"]


# ── Compétences innées ────────────────────────────────────────────────────────────

REGEN = {"_id": "competence:monstre_regeneration", "type": "competence", "vocation": "monstre",
		 "nom": "Régénération", "mode": "passive", "cible": "soi",
		 "effets": {"regen_pv": "{R/10}"}}
CARAPACE = {"_id": "competence:monstre_carapace", "type": "competence", "vocation": "monstre",
			"nom": "Carapace", "mode": "passive", "cible": "soi", "effets": {"buffs": {"R": 10}}}
VENIN = {"_id": "competence:monstre_venin", "type": "competence", "vocation": "monstre",
		 "nom": "Venin", "icon": "☠", "mode": "passive", "cible": "ennemi",
		 "effets": {"regen_pv": -4, "buffs": {"F": -5}, "duree": 3}}
SOUFFLE = {"_id": "competence:monstre_souffle", "type": "competence", "vocation": "monstre",
		   "nom": "Souffle", "mode": "active", "cible": "ennemi", "cout_pm": 5,
		   "effets": {"degats": "4D6"}}
CATALOGUE = {d["_id"]: d for d in (REGEN, CARAPACE, VENIN, SOUFFLE)}


def _espece(tags=(), competences=()):
	return {
		"_id": "espece:cobaye", "nom": "Cobaye", "tags": list(tags),
		"competences": list(competences),
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 5), ("F", 30), ("R", 40), ("Ag", 30),
							 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}


@pytest.fixture
def catalogue(monkeypatch):
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(combat_mod, "find_docs", lambda q: [])


def test_competences_espece_ignore_les_ids_morts():
	e = _espece(competences=["competence:monstre_venin", "competence:absente", ""])
	assert [c["id"] for c in cm.competences_espece(e, CATALOGUE.get)] == ["competence:monstre_venin"]


def test_passive_de_regeneration_resolue_sur_le_specimen(catalogue):
	snap = combat_mod.build_monster_snapshot(_espece(competences=[REGEN["_id"]]), None, 0)
	assert snap["regen_pv_base"] == 4      # R 40 / 10


def test_passive_de_buff_entre_dans_les_caracts_avant_derivation(catalogue):
	sans = combat_mod.build_monster_snapshot(_espece(), None, 0)
	avec = combat_mod.build_monster_snapshot(_espece(competences=[CARAPACE["_id"]]), None, 0)
	assert avec["caracts_base"]["R"] == sans["caracts_base"]["R"] + 10
	assert avec["pv_max"] > sans["pv_max"]


def test_sans_competence_le_snapshot_est_celui_d_avant(catalogue):
	snap = combat_mod.build_monster_snapshot(_espece(), None, 0)
	assert snap["regen_pv_base"] == 0
	assert "competences_monstre" not in snap
	assert "effets_impact" not in snap


def test_actives_listees_passives_absentes(catalogue):
	e = _espece(competences=[SOUFFLE["_id"], REGEN["_id"], VENIN["_id"]])
	snap = combat_mod.build_monster_snapshot(e, None, 0)
	assert snap["competences_monstre"] == [SOUFFLE["_id"]]
	assert snap["effets_impact"]["source_id"] == VENIN["_id"]


# ── Venin à l'impact de l'attaque naturelle ──────────────────────────────────────

def _joueur():
	return {"id": "joueur_0", "nom": "Frida", "vivant": True, "currentPV": 200, "pv_max": 200,
			"currentPM": 10, "pm_max": 10, "pa": 0, "pa_zones": {}, "ag": 0, "pm_def": 0,
			"pos": {"x": 3, "y": 4}, "effets_actifs": [],
			"caracts_base": {"V": 5, "F": 30, "R": 30, "Ag": 0, "Vol": 20, "Int": 20, "Cha": 10, "Ch": 10}}


def _doc(joueur, monstre):
	return {"_id": "combat:test", "status": "active", "tour": 1, "log": [],
			"joueurs": [joueur], "monstres": [monstre],
			"ordre_initiative": ["joueur_0", monstre["id"]], "acteur_courant_index": 1,
			"grid": {"dims": {"x": 7, "y": 7}, "cells": [[1] * 7 for _ in range(7)], "nav": {}}}


def test_le_venin_est_porte_par_le_profil_naturel(catalogue):
	snap = combat_mod.build_monster_snapshot(_espece(competences=[VENIN["_id"]]), None, 0)
	profil = combat_mod._profil_arme_monstre(snap)
	assert profil["effets"]["regen_pv"] == -4
	assert profil["effets_source_id"] == VENIN["_id"]


def test_le_venin_se_pose_quand_le_coup_porte(catalogue, monkeypatch):
	monstre = combat_mod.build_monster_snapshot(_espece(competences=[VENIN["_id"]]), None, 0)
	monstre["pos"] = {"x": 3, "y": 3}
	monstre["cc"] = 200
	joueur = _joueur()
	doc = _doc(joueur, monstre)
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	combat_mod._do_attack_on(doc, monstre, joueur, combat_mod._profil_arme_monstre(monstre))
	poison = [e for e in joueur["effets_actifs"] if e.get("source_id") == VENIN["_id"]]
	assert poison and poison[0]["regen_pv"] == -4


def test_un_coup_manque_n_empoisonne_pas(catalogue, monkeypatch):
	monstre = combat_mod.build_monster_snapshot(_espece(competences=[VENIN["_id"]]), None, 0)
	monstre["pos"] = {"x": 3, "y": 3}
	joueur = _joueur()
	joueur["ag"] = 500
	doc = _doc(joueur, monstre)
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 90)
	combat_mod._do_attack_on(doc, monstre, joueur, combat_mod._profil_arme_monstre(monstre))
	assert joueur["effets_actifs"] == []


# ── Choix d'une capacité (pur) ───────────────────────────────────────────────────

MOYENNE = lambda notation: {"4D6": 14.0, "2D6": 7.0}.get(notation, 1.0)


def test_score_hostile_compte_chaque_victime():
	opt = {"hostile": True, "effets": {"degats": "4D6"}, "victimes": [{}, {}]}
	assert cm.score_option(opt, MOYENNE) == 28.0


def test_un_debuff_deja_porte_ne_vaut_rien():
	eff = {"buffs": {"V": -5}, "duree": 2}
	neuf = {"hostile": True, "effets": eff, "source_id": "c:x", "victimes": [{"effets_actifs": []}]}
	porte = {"hostile": True, "effets": eff, "source_id": "c:x",
			 "victimes": [{"effets_actifs": [{"source_id": "c:x"}]}]}
	assert cm.score_option(neuf, MOYENNE) == cm.BONUS_EFFET
	assert cm.score_option(porte, MOYENNE) == 0
	assert cm.choisir_capacite([porte], MOYENNE) is None


def test_un_soin_ne_vaut_que_sur_un_blesse():
	eff = {"pv": 20}
	sain = {"hostile": False, "effets": eff, "beneficiaires": [{"currentPV": 90, "pv_max": 100}]}
	blesse = {"hostile": False, "effets": eff, "beneficiaires": [{"currentPV": 10, "pv_max": 100}]}
	assert cm.score_option(sain, MOYENNE) == 0
	assert cm.score_option(blesse, MOYENNE) == 20


def test_ex_aequo_departages_par_rand_fn():
	a = {"hostile": True, "effets": {"degats": "2D6"}, "victimes": [{}]}
	b = {"hostile": True, "effets": {"degats": "2D6"}, "victimes": [{}]}
	assert cm.choisir_capacite([a, b], MOYENNE, rand_fn=lambda l: l[-1]) is b


def test_recharges_decrementees_puis_retirees():
	acteur = {"recharges": {"c:a": 2, "c:b": 1}}
	cm.decrementer_recharges(acteur)
	assert acteur["recharges"] == {"c:a": 1}
	cm.decrementer_recharges(acteur)
	assert acteur["recharges"] == {}


# ── Lancer en combat ──────────────────────────────────────────────────────────────

CONE = {"_id": "competence:monstre_cone", "type": "competence", "vocation": "monstre",
		"nom": "Souffle de feu", "icon": "🔥", "mode": "active", "cible": "ennemi",
		"jet": "magique", "cout_pm": 5, "portee": 5, "recharge": 3,
		"zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible",
				 "decalage": 1, "longueur": 4, "angle": 90},
		"effets": {"degats": "4D6", "regen_pv": -3, "duree": 2}}
MEUTE = {"_id": "competence:monstre_meute", "type": "competence", "vocation": "monstre",
		 "nom": "Hurlement de meute", "mode": "active", "cible": "soi", "cout_pm": 0,
		 "recharge": 5, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 2},
		 "effets": {"buffs": {"F": 8}, "duree": 3}}
CATALOGUE.update({CONE["_id"]: CONE, MEUTE["_id"]: MEUTE})


def _joueur_en(i, x, y):
	j = _joueur()
	j.update(id=f"joueur_{i}", nom=f"J{i}", pos={"x": x, "y": y})
	return j


def _arene(monstres, joueurs):
	return {"_id": "combat:test", "status": "active", "tour": 1, "log": [],
			"joueurs": joueurs, "monstres": monstres,
			"ordre_initiative": [j["id"] for j in joueurs] + [m["id"] for m in monstres],
			"acteur_courant_index": len(joueurs),
			"grid": {"dims": {"x": 9, "y": 9}, "cells": [[1] * 9 for _ in range(9)], "nav": {}}}


def _dragon(x=4, y=1, comps=(CONE["_id"],), idx=0):
	m = combat_mod.build_monster_snapshot(_espece(competences=list(comps)), None, idx)
	m["pos"] = {"x": x, "y": y}
	m["toucher_magique"] = 200
	return m


def _jet_moyen_des_minimaux(monkeypatch):
	"""d100 à 50 (touche, hors critique), chaque dé de dégâts à 1 : la cible survit."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50 if b == 100 else a)


def test_le_souffle_touche_tout_le_cone_et_seulement_lui(catalogue, monkeypatch):
	_jet_moyen_des_minimaux(monkeypatch)
	dragon = _dragon()
	j0, j1, loin = _joueur_en(0, 4, 3), _joueur_en(1, 4, 4), _joueur_en(2, 0, 8)
	doc = _arene([dragon], [j0, j1, loin])
	pm = dragon["currentPM"]
	assert combat_mod._tenter_capacite_monstre(doc, dragon, doc["grid"]) is True
	assert j0["currentPV"] < 200 and j1["currentPV"] < 200
	assert loin["currentPV"] == 200
	assert any(e["source_id"] == CONE["_id"] for e in j0["effets_actifs"])
	assert dragon["currentPM"] == pm - 5
	assert dragon["recharges"] == {CONE["_id"]: 3}
	assert dragon["attaques"] == 1


def test_les_degats_passent_par_la_cascade_du_camp_du_joueur(catalogue, monkeypatch):
	"""Lien de vie, concentration et KO : `_blesser_allie`, la cascade d'un coup reçu."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	appels = []
	vrai = combat_mod._blesser_allie
	monkeypatch.setattr(combat_mod, "_blesser_allie",
						lambda doc, att, vic, dmg, ligne, intro: appels.append(vic["id"]) or vrai(doc, att, vic, dmg, ligne, intro))
	dragon = _dragon()
	doc = _arene([dragon], [_joueur_en(0, 4, 3)])
	combat_mod._tenter_capacite_monstre(doc, dragon, doc["grid"])
	assert appels == ["joueur_0"]


def test_une_seule_capacite_par_tour_puis_recharge(catalogue, monkeypatch):
	_jet_moyen_des_minimaux(monkeypatch)
	dragon = _dragon()
	doc = _arene([dragon], [_joueur_en(0, 4, 3)])
	assert combat_mod._tenter_capacite_monstre(doc, dragon, doc["grid"])
	assert not combat_mod._tenter_capacite_monstre(doc, dragon, doc["grid"]), "déjà lancée ce tour"
	for _ in range(2):
		combat_mod._reset_turn_budget(dragon)
		assert not combat_mod._tenter_capacite_monstre(doc, dragon, doc["grid"]), "en recharge"
	combat_mod._reset_turn_budget(dragon)
	assert combat_mod._tenter_capacite_monstre(doc, dragon, doc["grid"])


def test_hors_de_portee_ou_sans_pm_aucune_option(catalogue):
	dragon = _dragon()
	doc = _arene([dragon], [_joueur_en(0, 4, 8)])        # 7 cases > portée 5
	assert combat_mod._options_capacite_monstre(doc, dragon, doc["grid"]) == []
	doc["joueurs"][0]["pos"] = {"x": 4, "y": 3}
	dragon["currentPM"] = 4
	assert combat_mod._options_capacite_monstre(doc, dragon, doc["grid"]) == []


def test_un_mur_coupe_la_vue(catalogue):
	dragon = _dragon()
	doc = _arene([dragon], [_joueur_en(0, 4, 4)])
	doc["grid"]["cells"][2] = [0] * 9                   # rangée de murs entre eux
	assert combat_mod._options_capacite_monstre(doc, dragon, doc["grid"]) == []


def test_un_furtif_non_detecte_n_est_pas_vise(catalogue):
	dragon = _dragon()
	dragon["detecte"] = False
	j = _joueur_en(0, 4, 3)
	j["furtif"] = True
	doc = _arene([dragon], [j])
	assert combat_mod._options_capacite_monstre(doc, dragon, doc["grid"]) == []


def test_soutien_de_zone_buffe_la_meute_une_fois(catalogue):
	chef = _dragon(4, 4, comps=(MEUTE["_id"],), idx=0)
	loup = _dragon(5, 5, comps=(), idx=1)
	loin = _dragon(0, 0, comps=(), idx=2)
	doc = _arene([chef, loup, loin], [_joueur_en(0, 8, 8)])
	assert combat_mod._tenter_capacite_monstre(doc, chef, doc["grid"])
	assert any(e["source_id"] == MEUTE["_id"] for e in loup["effets_actifs"])
	assert any(e["source_id"] == MEUTE["_id"] for e in chef["effets_actifs"])
	assert not loin["effets_actifs"]


def test_tour_de_monstre_souffle_avant_de_marcher(catalogue, monkeypatch):
	_jet_moyen_des_minimaux(monkeypatch)
	dragon = _dragon()
	doc = _arene([dragon], [_joueur_en(0, 4, 4)])
	combat_mod._run_monster_turn(doc, dragon, doc["grid"])
	textes = [l["texte"] for l in doc["log"]]
	assert any("utilise Souffle de feu" in t for t in textes)
	assert doc["joueurs"][0]["currentPV"] < 200


def test_monstre_sans_capacite_tour_inchange(catalogue):
	m = _dragon(comps=())
	doc = _arene([m], [_joueur_en(0, 4, 4)])
	assert combat_mod._options_capacite_monstre(doc, m, doc["grid"]) == []
	assert combat_mod._tenter_capacite_monstre(doc, m, doc["grid"]) is False


# ── Banc d'essai : l'espèce engage ses capacités ─────────────────────────────────

def test_arsenal_d_espece_porte_ses_actives():
	from utils import simulateur
	e = _espece(competences=[CONE["_id"], MEUTE["_id"], REGEN["_id"]])
	arsenal = simulateur._arsenal_d_espece(e, CATALOGUE.get, (), {"Vol": 20})
	assert [c["id"] for c in arsenal["competences"]] == [CONE["_id"]]
	assert arsenal["competences"][0]["recharge"] == 3
	assert [s["id"] for s in arsenal["soutiens"]] == [MEUTE["_id"]]


# ── Phase 4 : l'IA lance ses sorts tirés ─────────────────────────────────────────

TRAIT = {"_id": "sort:trait", "type": "sort", "nom": "Trait de feu", "magie": "Élémentaire",
		 "niveau": 1, "cout_pm": 4, "cible": "ennemi", "portee": 6, "effets": {"degats": "2D6"}}
INVOC = {"_id": "sort:invoc", "type": "sort", "nom": "Levée", "magie": "Nécromancie",
		 "niveau": 1, "cout_pm": 4, "cible": "soi", "effets": {},
		 "invocation": {"espece": "espece:squelette", "nombre": 1, "duree": 3}}
LONG = {"_id": "sort:long", "type": "sort", "nom": "Météore", "magie": "Élémentaire",
		"niveau": 1, "cout_pm": 4, "cible": "ennemi", "portee": 6, "incantation": 3,
		"effets": {"degats": "6D6"}}
SOIN = {"_id": "sort:soin", "type": "sort", "nom": "Soin", "magie": "Sainte",
		"niveau": 1, "cout_pm": 4, "cible": "allie", "portee": 4, "effets": {"pv": 30}}
CATALOGUE.update({d["_id"]: d for d in (TRAIT, INVOC, LONG, SOIN)})


def test_sorts_jouables_par_l_ia():
	from utils.sorts import normaliser_sort
	assert cm.sort_lancable_par_ia(normaliser_sort(TRAIT))
	assert not cm.sort_lancable_par_ia(normaliser_sort(INVOC))
	assert not cm.sort_lancable_par_ia(normaliser_sort(LONG))
	m = {"sorts_connus": [TRAIT["_id"], INVOC["_id"], LONG["_id"], "sort:absent"]}
	assert [c["id"] for c in cm.actives_du_monstre(m, CATALOGUE.get)] == [TRAIT["_id"]]


def test_un_mage_monstre_lance_son_sort(catalogue, monkeypatch):
	_jet_moyen_des_minimaux(monkeypatch)
	mage = _dragon(comps=())
	mage["sorts_connus"] = [TRAIT["_id"]]
	j = _joueur_en(0, 4, 6)
	doc = _arene([mage], [j])
	pm = mage["currentPM"]
	assert combat_mod._tenter_capacite_monstre(doc, mage, doc["grid"])
	assert j["currentPV"] < 200
	assert mage["currentPM"] == pm - 4
	assert "recharges" not in mage or not mage["recharges"]


def test_un_mage_monstre_soigne_un_allie_blesse(catalogue):
	pretre = _dragon(4, 4, comps=(), idx=0)
	pretre["sorts_connus"] = [SOIN["_id"]]
	blesse = _dragon(5, 5, comps=(), idx=1)
	blesse["currentPV"] = 5
	doc = _arene([pretre, blesse], [_joueur_en(0, 8, 8)])
	assert combat_mod._tenter_capacite_monstre(doc, pretre, doc["grid"])
	assert blesse["currentPV"] == min(blesse["pv_max"], 35)

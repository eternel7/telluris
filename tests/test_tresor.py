# tests/test_tresor.py
#
# Trésor d'un étage de donjon à étages (bloc `tresor` sur l'entrée de salle, utils/tresor.py) :
# contenu garanti + bourse + tirage pondéré, piège probable (dégâts / alarme / mimique) qui se
# déclenche à l'OUVERTURE et non sous le pas, coffre qu'on ouvre même en plein combat.
#
# ⚠️ Les tests qui comptent : `test_la_vue_client_ne_livre_ni_contenu_ni_piege_cache` (le doc
# de combat part tel quel au navigateur — sans le filtre, la console dirait ce que contient un
# coffre fermé et s'il est piégé) et `test_revenir_a_l_etage_ne_retire_pas_le_tresor` (sinon
# monter puis redescendre rejouerait le trésor à l'infini dans la même expédition).

import pytest

from utils import combat as combat_util
from utils import donjon
from utils import pieges as pieges_util
from utils import tresor as tresor_util

from tests.test_combat_groupe import character, joueur_snap, monstre_snap, combat_doc, db


ITEMS = {
	"item:cristal": {"_id": "item:cristal", "nom": "Cristal", "icon": "💎", "poids": 1},
	"item:coupe": {"_id": "item:coupe", "nom": "Coupe", "icon": "🏆", "poids": [2, 4]},
	"item:lingot": {"_id": "item:lingot", "nom": "Lingot", "icon": "🧱", "poids": 100},
	"espece:rat": {"_id": "espece:rat"},
	"espece:mimique": {"_id": "espece:mimique"},
}

BLOC = {
	"nom": "Coffre de l'ossuaire",
	"garanti": [{"item": "item:cristal", "quantite": 2}],
	"bourse": [10, 20],
	"tirage": {"nb": 1, "table": [{"item": "item:coupe", "poids": 1}]},
}


def _donjon(bloc=None):
	return {"_id": "donjon:catacombes", "type": "donjon", "mode": "etages",
			"battle_maps": [
				{"lieu": "lieu:etage_1", "especes": ["espece:rat"], "nb_monstres": 2},
				{"lieu": "lieu:etage_2", "especes": ["espece:rat"], "nb_monstres": 3,
				 "tresor": BLOC if bloc is None else bloc},
			]}


def _sequence(*valeurs):
	vals = list(valeurs)

	def rand():
		return vals.pop(0) if vals else 0.0
	return rand


def _instancier(especes, profils, nb, tags):
	return [monstre_snap(f"monstre_{i}", espece_id=especes[0]["_id"]) for i in range(nb)]


def _grille(w=15, h=15):
	return {"dims": {"x": w, "y": h}, "cells": [[1] * w for _ in range(h)], "nav": {}}


# ── Bloc ─────────────────────────────────────────────────────────────────────────

def test_sans_bloc_aucun_tresor():
	assert tresor_util.normaliser_tresor(None) is None
	assert tresor_util.normaliser_tresor({"nom": "Coffre vide"}) is None
	assert tresor_util.tresor_de_salle(_donjon(), "lieu:etage_1") is None
	assert tresor_util.tresor_de_salle(_donjon(), "lieu:etage_2")["nom"] == "Coffre de l'ossuaire"


def test_normalisation_bornes_et_defauts():
	t = tresor_util.normaliser_tresor({
		"bourse": [30, 5], "pos": {"x": 4, "y": 6},
		"tirage": {"nb": 999, "table": [{"item": "item:coupe", "poids": 0},
										{"item": "item:cristal", "quantite": 999}]},
		"piege": {"chance": 40, "danger": 9, "effets": ["mimique", "alarme", "inconnu"],
				  "alarme": 99},
	})
	assert t["nom"] == tresor_util.NOM_DEFAUT and t["icon"] == tresor_util.ICON_DEFAUT
	assert t["bourse"] == [5, 30] and t["pos"] == [4, 6]
	assert t["tirage"]["nb"] == tresor_util.TIRAGE_NB_MAX
	# Poids nul écarté ; quantité bornée.
	assert t["tirage"]["table"] == [{"item": "item:cristal", "quantite": tresor_util.QUANTITE_MAX,
									 "poids": 1}]
	# Mimique sans espèce écrite : retirée des effets possibles.
	assert t["piege"]["effets"] == ["alarme"]
	assert t["piege"]["danger"] == pieges_util.DANGER_MAX
	assert t["piege"]["alarme"] == donjon.NB_MONSTRES_MAX
	assert tresor_util.normaliser_tresor(dict(BLOC, piege={"chance": 0}))["piege"] is None
	assert tresor_util.normaliser_tresor(dict(BLOC, piege={}))["piege"]["effets"] == ["degats"]


# ── Tirages ──────────────────────────────────────────────────────────────────────

def test_contenu_garanti_tirage_et_bourse():
	t = tresor_util.normaliser_tresor(BLOC)
	# rand : tirage de la table (1 ligne), poids de la coupe (0.5 → 3), bourse (0.5 → 15).
	c = tresor_util.tirer_contenu(t, ITEMS.get, _sequence(0.0, 0.5, 0.5))
	assert [o["item"] for o in c["objets"]] == ["item:cristal", "item:cristal", "item:coupe"]
	assert c["objets"][2]["poids"] == 3.0
	assert c["cuivre"] == 15


def test_un_item_absent_de_la_base_est_ecarte():
	t = tresor_util.normaliser_tresor({"garanti": [{"item": "item:fantome"},
												   {"item": "item:cristal"}]})
	assert [o["item"] for o in tresor_util.tirer_contenu(t, ITEMS.get)["objets"]] == ["item:cristal"]


def test_piege_probable():
	t = tresor_util.normaliser_tresor(dict(BLOC, piege={
		"chance": 40, "danger": 2, "effets": ["degats", "alarme"]}))
	assert tresor_util.tirer_piege(t, _sequence(0.5)) is None          # 50 ≥ 40 : pas piégé
	assert tresor_util.tirer_piege(t, _sequence(0.39, 0.9)) == {"danger": 2, "effet": "alarme"}
	assert tresor_util.tirer_piege(t, _sequence(0.1, 0.0)) == {"danger": 2, "effet": "degats"}


def test_preparer_tresor_reserve_les_monstres_du_piege():
	mimique = dict(BLOC, piege={"chance": 100, "effets": ["mimique"], "mimique": "espece:mimique"})
	p = tresor_util.preparer_tresor(_donjon(mimique), "lieu:etage_2", [], 0, ITEMS.get,
									_instancier, _sequence())
	assert p["piege"]["effet"] == "mimique" and p["mimique"]["espece_id"] == "espece:mimique"
	alarme = dict(BLOC, piege={"chance": 100, "effets": ["alarme"]})
	p = tresor_util.preparer_tresor(_donjon(alarme), "lieu:etage_2", [], 0, ITEMS.get,
									_instancier, _sequence())
	assert len(p["renforts"]) == 3   # sans `alarme` écrit : l'effectif de la salle
	alarme["piege"]["alarme"] = 1
	p = tresor_util.preparer_tresor(_donjon(alarme), "lieu:etage_2", [], 0, ITEMS.get,
									_instancier, _sequence())
	assert len(p["renforts"]) == 1
	# Espèce de mimique introuvable : le piège reste un piège à dégâts.
	perdue = dict(BLOC, piege={"chance": 100, "effets": ["mimique"], "mimique": "espece:x"})
	p = tresor_util.preparer_tresor(_donjon(perdue), "lieu:etage_2", [], 0, ITEMS.get,
									_instancier, _sequence())
	assert p["piege"]["effet"] == "degats" and "mimique" not in p
	assert tresor_util.preparer_tresor(_donjon(), "lieu:etage_1", [], 0, ITEMS.get,
									   _instancier) is None


# ── Installation à l'entrée de l'étage ───────────────────────────────────────────

def _prepare(piege=None, pos=None, **extra):
	p = {"lieu": "lieu:etage_2", "nom": "Coffre", "icon": "🧰", "pos": pos,
		 "objets": [{"item": "item:cristal", "nom": "Cristal", "icon": "💎", "poids": 1}],
		 "cuivre": 12, "piege": piege}
	p.update(extra)
	return p


def _etages(tresors=None):
	e = {"donjon": "donjon:catacombes", "etage": "lieu:etage_2", "passages": [],
		 "archives": []}
	if tresors is not None:
		e["tresors"] = tresors
	return e


def test_case_ecrite_ou_tiree_loin_du_depart(db):
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1", x=1, y=1)], [],
					 etages=_etages())
	combat_util.installer_tresor(doc, _prepare(pos=[9, 7]), _grille(), {"x": 1, "y": 1})
	etat = doc["etages"]["tresors"]["lieu:etage_2"]
	assert (etat["x"], etat["y"]) == (9, 7) and etat["etat"] == "ferme"
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1", x=1, y=1)], [],
					 etages=_etages())
	combat_util.installer_tresor(doc, _prepare(pos=[50, 50]), _grille(), {"x": 1, "y": 1})
	etat = doc["etages"]["tresors"]["lieu:etage_2"]
	assert max(abs(etat["x"] - 1), abs(etat["y"] - 1)) >= pieges_util.PIEGES_DISTANCE_DEPART


def test_le_piege_du_coffre_est_un_piege_cache_qui_remplace_celui_de_la_salle(db):
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1", x=1, y=1)], [],
					 etages=_etages())
	doc["pieges"] = [pieges_util.nouveau_piege("piege_0_0", "monde", 9, 7, 1)]
	combat_util.installer_tresor(doc, _prepare(piege={"danger": 2, "effet": "degats"},
											   pos=[9, 7]), _grille(), {"x": 1, "y": 1})
	assert len(doc["pieges"]) == 1
	p = doc["pieges"][0]
	assert p["etat"] == "cache" and p["declencheur"] == "ouverture" and p["effet"] == "degats"
	assert (p["x"], p["y"]) == (9, 7)


def test_marcher_sur_le_coffre_ne_declenche_pas_son_piege(db):
	j = joueur_snap("joueur_0", "character:u_1", x=9, y=7)
	doc = combat_doc([j], [], etages=_etages())
	doc["pieges"] = [tresor_util.nouveau_piege_du_coffre(
		"piege_tresor_0", 9, 7, {"danger": 3, "effet": "degats"}, "Coffre")]
	combat_util._pieges_au_pas(doc, j)
	assert j["currentPV"] == 50 and doc["pieges"][0]["etat"] == "cache"


def test_revenir_a_l_etage_ne_retire_pas_le_tresor(db):
	j = joueur_snap("joueur_0", "character:u_1", x=8, y=7)
	doc = combat_doc([j], [], etages=_etages())
	combat_util.installer_tresor(doc, _prepare(piege={"danger": 1, "effet": "degats"},
											   pos=[9, 7]), _grille(), None)
	doc["pieges"][0]["etat"] = "desamorce"
	combat_util._ranger_tresor(doc)
	doc["pieges"] = []
	doc["etages"]["tresors"]["lieu:etage_2"]["etat"] = "vide"
	# Une préparation neuve est IGNORÉE : le coffre de l'expédition est déjà là.
	combat_util.installer_tresor(doc, _prepare(pos=[2, 2]), _grille(), None)
	etat = doc["etages"]["tresors"]["lieu:etage_2"]
	assert (etat["x"], etat["y"], etat["etat"]) == (9, 7, "vide")
	assert [p["etat"] for p in doc["pieges"]] == ["desamorce"]


def test_changer_d_etage_range_et_rend_le_coffre(db):
	j = joueur_snap("joueur_0", "character:u_1", x=8, y=7)
	doc = combat_doc([j], [], etages=_etages(), battle_map_id=None)
	combat_util.installer_tresor(doc, _prepare(piege={"danger": 1, "effet": "degats"},
											   pos=[9, 7]), _grille(), None)
	doc["pieges"][0]["etat"] = "detecte"
	haut = {"_id": "lieu:etage_1", "dimensions": {"x": 15, "y": 15},
			"cells": [[1] * 15 for _ in range(15)], "nav": {}, "tags": []}
	combat_util.changer_d_etage(doc, haut, {"x": 1, "y": 1}, [], [])
	assert doc["pieges"] == []
	assert doc["etages"]["tresors"]["lieu:etage_2"]["piege"]["etat"] == "detecte"
	bas = dict(haut, _id="lieu:etage_2")
	combat_util.changer_d_etage(doc, bas, {"x": 1, "y": 1}, [], [], tresor=_prepare(pos=[2, 2]))
	assert [(p["x"], p["y"], p["etat"]) for p in doc["pieges"]] == [(9, 7, "detecte")]


# ── Ouvrir ───────────────────────────────────────────────────────────────────────

def _doc_coffre(joueurs, monstres=(), piege=None, **etat):
	tresor = {"x": 9, "y": 7, "nom": "Coffre", "icon": "🧰", "etat": "ferme",
			  "objets": [{"item": "item:cristal", "nom": "Cristal", "icon": "💎", "poids": 1},
						 {"item": "item:lingot", "nom": "Lingot", "icon": "🧱", "poids": 100}],
			  "cuivre": 12}
	tresor.update(etat)
	doc = combat_doc(list(joueurs), list(monstres),
					 etages=_etages({"lieu:etage_2": tresor}))
	if piege:
		p = tresor_util.nouveau_piege_du_coffre("piege_tresor_0", 9, 7, piege, "Coffre")
		tresor["piege_id"] = p["id"]
		doc["pieges"] = [p]
	return doc


def test_ouvrir_au_contact_seulement(db):
	db.update(ITEMS)
	doc = _doc_coffre([joueur_snap("joueur_0", "character:u_1", x=5, y=5)])
	assert "error" in combat_util.resolve_action(doc, "ouvrir_tresor")
	assert combat_util.vue_client(doc)["peut_ouvrir_tresor"] is False


def test_pas_avec_un_ennemi_au_corps_a_corps(db):
	db.update(ITEMS)
	doc = _doc_coffre([joueur_snap("joueur_0", "character:u_1", x=8, y=7)],
					  [monstre_snap(x=7, y=7)])
	assert combat_util.resolve_action(doc, "ouvrir_tresor")["error"].startswith("Un ennemi")


def test_ouvrir_en_plein_combat_emporte_ce_qui_se_porte(db):
	db.update(ITEMS)
	ouvreur = joueur_snap("joueur_0", "character:u_1", x=8, y=7, charge_max=50)
	autre = joueur_snap("joueur_1", "aventurier:fort", x=10, y=7, charge_max=500)
	doc = _doc_coffre([ouvreur, autre], [monstre_snap(x=0, y=0)])
	assert combat_util.vue_client(doc)["peut_ouvrir_tresor"] is True
	res = combat_util.resolve_action(doc, "ouvrir_tresor")
	assert res["tresor"] == "ouvert" and res["pris"] == ["Cristal"] and res["restes"] == 1
	assert ouvreur["butin_ramasse"] == [{"item": "item:cristal", "poids": 1}]
	assert ouvreur["cuivre_ramasse"] == 12 and ouvreur["charge"] == 1
	vue = combat_util.vue_client(doc)["etages"]["tresor"]
	assert vue["etat"] == "ouvert" and [o["nom"] for o in vue["contenu"]] == ["Lingot"]
	# Un autre membre vide le reste ; la bourse, elle, est déjà partie.
	doc["acteur_courant_index"] = 1
	res = combat_util.resolve_action(doc, "ouvrir_tresor")
	assert res["tresor"] == "vide" and res["cuivre"] == 0
	assert autre["butin_ramasse"] == [{"item": "item:lingot", "poids": 100}]
	assert "error" in combat_util.resolve_action(doc, "ouvrir_tresor")


def test_piege_a_degats(db):
	db.update(ITEMS)
	j = joueur_snap("joueur_0", "character:u_1", x=8, y=7, charge_max=500)
	doc = _doc_coffre([j], piege={"danger": 1, "effet": "degats"})
	res = combat_util.resolve_action(doc, "ouvrir_tresor")
	assert j["currentPV"] < 50 and doc["pieges"][0]["etat"] == "declenche"
	assert res["tresor"] == "vide" and len(j["butin_ramasse"]) == 2


def test_un_piege_desamorce_ne_fait_rien(db):
	db.update(ITEMS)
	j = joueur_snap("joueur_0", "character:u_1", x=8, y=7, charge_max=500)
	doc = _doc_coffre([j], piege={"danger": 5, "effet": "degats"})
	doc["pieges"][0]["etat"] = "desamorce"
	combat_util.resolve_action(doc, "ouvrir_tresor")
	assert j["currentPV"] == 50


def test_alarme_les_renforts_accourent_et_savent_ou_est_le_groupe(db):
	db.update(ITEMS)
	j = joueur_snap("joueur_0", "character:u_1", x=8, y=7, charge_max=500)
	archive = monstre_snap("monstre_0", vivant=False)
	doc = _doc_coffre([j], [monstre_snap("monstre_1", x=0, y=0)],
					  piege={"danger": 1, "effet": "alarme"},
					  renforts=[monstre_snap("monstre_0"), monstre_snap("monstre_1")])
	doc["etages"]["archives"] = [archive]
	doc["grid_dims"] = {"x": 20, "y": 20}
	combat_util.resolve_action(doc, "ouvrir_tresor")
	arrives = doc["monstres"][1:]
	assert [m["id"] for m in arrives] == ["monstre_2", "monstre_3"]
	assert all(m["detecte"] for m in arrives)
	assert all(max(abs(m["pos"]["x"] - 8), abs(m["pos"]["y"] - 7))
			   >= combat_util.DISTANCE_MIN_APPARITION for m in arrives)
	assert doc["ordre_initiative"][-2:] == ["monstre_2", "monstre_3"]
	assert j["currentPV"] == 50 and len(j["butin_ramasse"]) == 2
	assert "renforts" not in doc["etages"]["tresors"]["lieu:etage_2"]


def test_mimique_le_coffre_ne_s_ouvre_qu_abattue(db):
	db.update(ITEMS)
	j = joueur_snap("joueur_0", "character:u_1", x=8, y=7, charge_max=500)
	doc = _doc_coffre([j], piege={"danger": 1, "effet": "mimique"},
					  mimique=monstre_snap("monstre_0", nom="Mimique"))
	res = combat_util.resolve_action(doc, "ouvrir_tresor")
	assert res["tresor"] == "mimique" and j["butin_ramasse"] == []
	m = doc["monstres"][-1]
	assert m["id"] == res["monstre_id"] and m["detecte"] is True
	assert doc["ordre_initiative"][1] == m["id"]
	vue = combat_util.vue_client(doc)
	assert "tresor" not in vue["etages"] and vue["peut_ouvrir_tresor"] is False
	m["vivant"] = False
	assert combat_util.vue_client(doc)["etages"]["tresor"]["etat"] == "ferme"
	j["attaques"] = 0
	res = combat_util.resolve_action(doc, "ouvrir_tresor")
	assert res["tresor"] == "vide" and len(j["butin_ramasse"]) == 2


def test_la_vue_client_ne_livre_ni_contenu_ni_piege_cache(db):
	doc = _doc_coffre([joueur_snap("joueur_0", "character:u_1", x=8, y=7)],
					  piege={"danger": 1, "effet": "alarme"},
					  renforts=[monstre_snap("monstre_9")])
	vue = combat_util.vue_client(doc)
	assert "tresors" not in vue["etages"]
	assert vue["etages"]["tresor"] == {"x": 9, "y": 7, "nom": "Coffre", "icon": "🧰",
									   "etat": "ferme"}
	assert vue["pieges"] == []
	assert "tresors" in doc["etages"]   # le doc lui-même n'est pas touché


def test_la_bourse_et_les_objets_vont_au_membre_a_la_fin(db):
	perso = character()
	db[perso["_id"]] = perso
	j = joueur_snap("joueur_0", perso["_id"], butin_ramasse=[{"item": "item:cristal", "poids": 1}],
					cuivre_ramasse=10250)
	doc = combat_doc([j], [], status="defaite")
	combat_util._finalize_membre(doc, j, perso, "defaite")
	assert perso["inventaire"] == [{"item": "item:cristal", "poids": 1}]
	assert (perso["or"], perso["argent"], perso["cuivre"]) == (1, 2, 50)

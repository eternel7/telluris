# tests/test_donjon_etages.py
#
# Donjon à étages (`"mode": "etages"` sur un doc donjon) : on y descend (ou on y monte) par des
# connexions ordinaires, et toute l'expédition est UN combat qui change de carte d'étage en
# étage. Le groupe entre furtif au point d'apparition fixe ; vider un étage ne termine rien ; on
# ne fuit pas — on sort par un passage vers la surface, ou par la défaite.
#
# ⚠️ Les tests qui comptent : `test_un_etage_vide_n_est_pas_une_victoire` (sans lui, le premier
# étage nettoyé renverrait le groupe à la carte) et `test_la_sortie_compte_les_kills_des_etages_quittes`
# (sans l'archive, un kill fait au premier étage disparaîtrait des quêtes au changement d'étage).

import pytest

from utils import combat as combat_util
from utils import donjon

from tests.test_combat_groupe import (
	character, aventurier, joueur_snap, monstre_snap, combat_doc, db,
)


DONJON = {
	"_id": "donjon:catacombes", "type": "donjon", "nom": "Catacombes", "mode": "etages",
	"battle_maps": [
		{"lieu": "lieu:etage_1", "especes": ["espece:rat"], "nb_monstres": 2},
		{"lieu": "lieu:etage_2", "especes": ["espece:rat", "espece:absente"]},
	],
}
CLASSIQUE = {"_id": "donjon:mine", "type": "donjon",
			 "battle_maps": [{"lieu": "lieu:mine", "especes": ["espece:rat"]}]}


def _etage(lid, w=15, h=15):
	return {"_id": lid, "type": "lieu", "categorie": "battle_map", "tags": ["donjon"],
			"label": lid.split(":")[1], "image": f"{lid}.png",
			"dimensions": {"x": w, "y": h}, "cells": [[1] * w for _ in range(h)], "nav": {}}


def _passage(pid, x, y, vers="lieu:etage_2", surface=False, vx=1, vy=1):
	return {"id": pid, "pos": {"x": x, "y": y}, "vers_lieu": vers,
			"vers_pos": {"x": vx, "y": vy}, "surface": surface, "label": vers}


def _etages(passages=None, archives=None):
	return {"donjon": DONJON["_id"], "etage": "lieu:etage_1",
			"passages": passages or [], "archives": archives or []}


# ── Lecture du doc donjon ────────────────────────────────────────────────────────

def test_mode_absent_est_un_donjon_classique():
	assert donjon.est_a_etages(CLASSIQUE) is False
	assert donjon.est_a_etages(None) is False
	assert donjon.est_a_etages(DONJON) is True


def test_donjon_a_etages_de_ne_requete_que_pour_une_salle_de_donjon():
	appels = []

	def find_docs(sel):
		appels.append(sel)
		return [DONJON, CLASSIQUE]

	assert donjon.donjon_a_etages_de({"_id": "lieu:porte", "categorie": "cite"}, find_docs) is None
	assert donjon.donjon_a_etages_de(
		{"_id": "lieu:etage_1", "categorie": "battle_map", "tags": []}, find_docs) is None
	assert appels == []
	assert donjon.donjon_a_etages_de(_etage("lieu:etage_1"), find_docs) is DONJON
	# Une salle d'un donjon CLASSIQUE n'est pas un étage : son gardien ouvre toujours le combat.
	assert donjon.donjon_a_etages_de(_etage("lieu:mine"), find_docs) is None


def _instancier(appels):
	def instantiate(especes, profils, nb, tags):
		appels.append({"especes": [e["_id"] for e in especes], "profils": profils,
					   "nb": nb, "tags": tags})
		return [monstre_snap(f"monstre_{i}") for i in range(nb)]
	return instantiate


def test_monstres_de_salle_effectif_ecrit_ou_regle_du_moteur():
	docs = {"espece:rat": {"_id": "espece:rat"}}
	appels = []
	m1 = donjon.monstres_de_salle(DONJON, "lieu:etage_1", [], 4, docs.get, _instancier(appels))
	assert len(m1) == 2 and appels[-1]["nb"] == 2   # écrit : le bonus de compagnons ne s'ajoute pas
	m2 = donjon.monstres_de_salle(DONJON, "lieu:etage_2", [], 4, docs.get, _instancier(appels))
	assert len(m2) == 3 + 4 // 2
	assert appels[-1]["especes"] == ["espece:rat"]   # espèce absente de la base ignorée
	assert appels[-1]["tags"] == []


def test_monstres_de_salle_respecte_la_fourchette_de_grade():
	docs = {"espece:rat": {"_id": "espece:rat"}}
	d = dict(DONJON, niveau_max=2)
	profils = [{"_id": "profil:a", "niveau": 1}, {"_id": "profil:b", "niveau": 4}]
	appels = []
	donjon.monstres_de_salle(d, "lieu:etage_1", profils, 0, docs.get, _instancier(appels))
	assert [p["_id"] for p in appels[-1]["profils"]] == ["profil:a"]


def test_monstres_de_salle_sans_espece():
	assert donjon.monstres_de_salle(DONJON, "lieu:inconnu", [], 0, {}.get,
									_instancier([])) == []


def test_passages_de_l_etage():
	connexions = [
		{"_id": "connection:descente", "nodes": [
			{"lieu": "lieu:etage_1", "pos": [3, 4]}, {"lieu": "lieu:etage_2", "pos": [7, 8]}]},
		{"_id": "connection:sortie", "nodes": [
			{"lieu": "lieu:lutecia", "pos": [10, 11], "label": "Parvis"},
			{"lieu": "lieu:etage_1", "pos": [0, 0]}]},
		{"_id": "connection:cassee", "nodes": [{"lieu": "lieu:etage_1", "pos": [1]}]},
	]
	passages = donjon.passages_de_l_etage(connexions, "lieu:etage_1", DONJON,
										  lambda lid: "nom de " + lid)
	assert passages == [
		{"id": "connection:descente", "pos": {"x": 3, "y": 4}, "vers_lieu": "lieu:etage_2",
		 "vers_pos": {"x": 7, "y": 8}, "surface": False, "label": "nom de lieu:etage_2"},
		{"id": "connection:sortie", "pos": {"x": 0, "y": 0}, "vers_lieu": "lieu:lutecia",
		 "vers_pos": {"x": 10, "y": 11}, "surface": True, "label": "Parvis"},
	]


def test_bonus_furtivite_groupe():
	vus = []

	def furtivite(doc, get_doc, tags):
		vus.append(tags)
		return 15 if doc["_id"] == "character:u_1" else 0

	bonus = donjon.bonus_furtivite_groupe(
		[character(), aventurier(), None], ["souterrain"], furtivite, {}.get)
	assert bonus == {"character:u_1": 15, "aventurier:guilde_ami": 0}
	assert vus[0] == {"souterrain"}


# ── Entrée : point d'apparition fixe, tout le groupe furtif ─────────────────────

def test_entree_au_point_d_apparition_et_furtive(db):
	etage = _etage("lieu:etage_1")
	monstres = [monstre_snap(f"monstre_{i}") for i in range(4)]
	doc = combat_util.create_combat_doc(
		character(), monstres, [], etage["image"], battle_map=etage,
		compagnons=[aventurier()], point_apparition={"x": 2, "y": 2},
		etages=_etages(), furtivite_groupe={"character:u_1": 12})
	principal, compagnon = doc["joueurs"]
	assert principal["pos"] == {"x": 2, "y": 2}
	assert max(abs(compagnon["pos"]["x"] - 2), abs(compagnon["pos"]["y"] - 2)) == 1
	assert all(j["furtif"] for j in doc["joueurs"])
	assert principal["furtivite_bonus"] == 12 and compagnon["furtivite_bonus"] == 0
	for m in doc["monstres"]:
		assert max(abs(m["pos"]["x"] - 2), abs(m["pos"]["y"] - 2)) >= combat_util.DISTANCE_MIN_APPARITION
		assert m["detecte"] is False
	assert doc["etages"]["etage"] == "lieu:etage_1"


def test_point_d_apparition_dans_un_mur_retombe_sur_le_placement_ordinaire(db):
	etage = _etage("lieu:etage_1")
	etage["cells"][2][2] = 0
	doc = combat_util.create_combat_doc(
		character(), [monstre_snap()], [], "", battle_map=etage,
		point_apparition={"x": 2, "y": 2}, etages=_etages())
	assert doc["joueurs"][0]["pos"] != {"x": 2, "y": 2}


def test_sans_etages_le_combat_ordinaire_ne_change_pas(db):
	doc = combat_util.create_combat_doc(character(), [monstre_snap()], [], "",
										compagnons=[aventurier()])
	assert "etages" not in doc
	assert not any(j["furtif"] for j in doc["joueurs"])


# ── Pas de condition de sortie ───────────────────────────────────────────────────

def test_un_etage_vide_n_est_pas_une_victoire(db):
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1")],
					 [monstre_snap(vivant=False)], etages=_etages())
	combat_util._check_victory(doc)
	assert doc["status"] == "active"
	del doc["etages"]
	combat_util._check_victory(doc)
	assert doc["status"] == "victoire"


def test_on_ne_fuit_pas_un_donjon_a_etages(db):
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1")], [monstre_snap()],
					 etages=_etages())
	res = combat_util.resolve_action(doc, "fuir")
	assert "error" in res and doc["status"] == "active"


# ── Emprunter un passage ─────────────────────────────────────────────────────────

def _groupe(x0, y0, x1, y1):
	return [joueur_snap("joueur_0", "character:u_1", x=x0, y=y0),
			joueur_snap("joueur_1", "aventurier:guilde_ami", x=x1, y=y1)]


def test_tout_le_groupe_doit_etre_au_passage(db):
	p = _passage("connection:descente", 5, 5)
	loin = combat_doc(_groupe(5, 5, 8, 8), [monstre_snap(x=0, y=0)], etages=_etages([p]))
	assert combat_util.passage_franchissable(loin, p) is False
	assert "error" in combat_util.resolve_action(loin, "emprunter", "connection:descente")
	personne_dessus = combat_doc(_groupe(4, 5, 6, 5), [], etages=_etages([p]))
	assert combat_util.passage_franchissable(personne_dessus, p) is False
	regroupe = combat_doc(_groupe(5, 5, 6, 6), [], etages=_etages([p]))
	assert combat_util.passage_franchissable(regroupe, p) is True


def _trio(*positions):
	return [joueur_snap(f"joueur_{i}", "character:u_1" if i == 0 else f"aventurier:a{i}",
						x=x, y=y) for i, (x, y) in enumerate(positions)]


def test_un_couloir_en_cul_de_sac_se_franchit_en_file(db):
	"""Cas réel (combat:84de35e8…, 24/09/2026) : sortie au fond d'un couloir d'une case de
	large, UNE seule voisine praticable — trois combattants ne pouvaient jamais être tous
	à une case du passage, et le groupe restait enfermé dans le donjon."""
	p = _passage("connection:surface", 17, 10)
	en_file = combat_doc(_trio((17, 10), (17, 9), (17, 8)), [], etages=_etages([p]))
	assert combat_util.passage_franchissable(en_file, p) is True


def test_une_file_rompue_ne_franchit_pas(db):
	p = _passage("connection:surface", 17, 10)
	trou = combat_doc(_trio((17, 10), (17, 9), (17, 7)), [], etages=_etages([p]))
	assert combat_util.passage_franchissable(trou, p) is False
	# Adjacents entre eux mais détachés du passage : la file doit partir de la tête.
	detaches = combat_doc(_trio((17, 10), (10, 9), (10, 8)), [], etages=_etages([p]))
	assert combat_util.passage_franchissable(detaches, p) is False


def test_un_groupe_de_sept_en_diagonale_franchit(db):
	"""Chaque membre est adjacent au précédent : la file s'étire sur 7 cases depuis le
	principal, en diagonale comme en ligne droite."""
	p = _passage("connection:surface", 5, 5)
	diagonale = combat_doc(_trio(*[(5 + i, 5 + i) for i in range(7)]), [],
						   etages=_etages([p]))
	assert combat_util.passage_franchissable(diagonale, p) is True


def test_la_file_part_du_principal(db):
	"""Un compagnon sur le passage ne suffit pas : c'est le principal qui l'emprunte."""
	p = _passage("connection:surface", 17, 10)
	compagnon_dessus = combat_doc(_trio((17, 9), (17, 10), (17, 8)), [], etages=_etages([p]))
	assert combat_util.passage_franchissable(compagnon_dessus, p) is False


def test_principal_a_terre_la_file_part_d_un_combattant_debout(db):
	"""Le principal à terre suit comme tout membre à terre, sinon le groupe restait
	enfermé : la file part alors de qui se tient sur le passage."""
	p = _passage("connection:surface", 17, 10)
	groupe = _trio((1, 1), (17, 10), (17, 9))
	groupe[0]["currentPV"] = 0
	doc = combat_doc(groupe, [], etages=_etages([p]))
	assert combat_util.passage_franchissable(doc, p) is True


def test_une_monture_ou_un_membre_a_terre_suit_sans_condition(db):
	p = _passage("connection:descente", 5, 5)
	groupe = _groupe(5, 5, 12, 12)
	groupe[1]["currentPV"] = 0
	groupe.append(joueur_snap("joueur_2", "monture:ane", x=0, y=0, jouable=False,
							  est_monture=True))
	doc = combat_doc(groupe, [], etages=_etages([p]))
	assert combat_util.passage_franchissable(doc, p) is True


def test_emprunter_vers_un_etage_rend_le_passage_au_router(db):
	p = _passage("connection:descente", 5, 5)
	doc = combat_doc(_groupe(5, 5, 5, 6), [monstre_snap(x=0, y=0)], etages=_etages([p]))
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente")
	assert res == {"passage": p}
	assert doc["status"] == "active"
	assert "error" in combat_util.resolve_action(doc, "emprunter", "connection:inconnue")


def test_changer_d_etage_conserve_le_groupe_et_remplace_les_monstres(db):
	p = _passage("connection:descente", 5, 5, vx=3, vy=3)
	groupe = _groupe(5, 5, 5, 6)
	groupe[0]["currentPV"] = 17
	groupe[0]["effets_actifs"] = [{"source": "potion", "restants": 3}]
	mort = monstre_snap("monstre_0", x=0, y=0, vivant=False)
	vif = monstre_snap("monstre_1", x=9, y=9)
	doc = combat_doc(groupe, [mort, vif], etages=_etages([p]))
	suivant = _etage("lieu:etage_2")
	neufs = [monstre_snap("monstre_0"), monstre_snap("monstre_1")]
	combat_util.changer_d_etage(doc, suivant, {"x": 3, "y": 3}, neufs, [],
								{"character:u_1": 5})
	assert doc["battle_map_id"] == "lieu:etage_2" and "grid_dims" not in doc
	assert doc["map_image"] == "lieu:etage_2.png"
	assert doc["etages"]["etage"] == "lieu:etage_2"
	assert doc["etages"]["archives"] == [mort, vif]
	# Renumérotés à la suite : le journal des étages passés garde ses `monstre_0`/`monstre_1`.
	assert [m["id"] for m in doc["monstres"]] == ["monstre_2", "monstre_3"]
	assert set(doc["ordre_initiative"]) == {"joueur_0", "joueur_1", "monstre_2", "monstre_3"}
	principal = doc["joueurs"][0]
	assert principal["pos"] == {"x": 3, "y": 3}
	assert principal["currentPV"] == 17
	assert principal["furtif"] and principal["furtivite_bonus"] == 5
	assert all(j["furtif"] for j in doc["joueurs"])
	assert doc["status"] == "active"
	assert doc["ordre_initiative"][doc["acteur_courant_index"]].startswith("joueur_")


def test_la_sortie_compte_les_kills_des_etages_quittes(db):
	perso = character(quetes_actives=[
		{"id": "q:rats", "objectif": {"type": "kill", "cible": "espece:rat", "quantite": 5},
		 "progress": 0}])
	db[perso["_id"]] = perso
	archives = [monstre_snap("monstre_0", vivant=False, xp_reward=10),
				monstre_snap("monstre_1", vivant=True, xp_reward=10)]
	sortie = _passage("connection:sortie", 5, 5, vers="lieu:lutecia", surface=True,
					  vx=10, vy=11)
	doc = combat_doc([joueur_snap("joueur_0", perso["_id"], x=5, y=5)],
					 [monstre_snap("monstre_2", vivant=False, xp_reward=7)],
					 etages=_etages([sortie], archives))
	res = combat_util.resolve_action(doc, "emprunter", "connection:sortie")
	assert res == {"sortie": True}
	assert doc["status"] == "victoire"
	assert doc["xp_gagnee"] == 17
	assert doc["sortie"] == {"lieu": "lieu:lutecia", "pos": {"x": 10, "y": 11}}
	assert combat_util.finalize_combat(doc) is True
	assert perso["lieu"] == "lieu:lutecia" and perso["position"] == {"x": 10, "y": 11}
	assert perso["xp_total"] == 17
	assert perso["quetes_actives"][0]["progress"] == 2


def test_une_defaite_laisse_le_personnage_la_ou_il_est_descendu(db):
	perso = character(lieu="lieu:lutecia", position={"x": 4, "y": 4})
	db[perso["_id"]] = perso
	doc = combat_doc([joueur_snap("joueur_0", perso["_id"], pv=0)], [monstre_snap()],
					 status="defaite", etages=_etages())
	combat_util.finalize_combat(doc)
	assert perso["lieu"] == "lieu:lutecia" and perso["position"] == {"x": 4, "y": 4}
	assert perso["xp_total"] == 0


# ── Butin d'un étage vidé ────────────────────────────────────────────────────────

def _carcasse_rat(db, poids=4):
	item_id = combat_util._loot_item_id("espece:rat")
	db[item_id] = {"_id": item_id, "type": "item", "nom": "Carcasse de rat", "poids": poids}
	return item_id


def _etage_vide(db, poids=4):
	"""Groupe au passage de descente, deux rats morts sur l'étage."""
	item_id = _carcasse_rat(db, poids)
	p = _passage("connection:descente", 5, 5)
	morts = [monstre_snap("monstre_0", x=0, y=0, vivant=False),
			 monstre_snap("monstre_1", x=1, y=0, vivant=False)]
	return combat_doc(_groupe(5, 5, 5, 6), morts, etages=_etages([p])), p, item_id


def test_quitter_un_etage_vide_propose_d_abord_son_butin(db):
	doc, _, item_id = _etage_vide(db)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente")
	assert res["passage_id"] == "connection:descente"
	assert [d["monstre_id"] for d in res["butin_etage"]] == ["monstre_0", "monstre_1"]
	assert all(d["item_id"] == item_id for d in res["butin_etage"])
	# Rien n'a bougé, et la liste est la MÊME à la réouverture (poids non retirés).
	assert doc["etages"]["etage"] == "lieu:etage_1" and doc["status"] == "active"
	assert combat_util.resolve_action(doc, "emprunter", "connection:descente") == res


def test_la_repartition_va_au_butin_ramasse_puis_le_groupe_passe(db):
	doc, p, item_id = _etage_vide(db)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente", attributions=[
		{"monstre_id": "monstre_0", "beneficiaire_id": "aventurier:guilde_ami"}])
	assert res == {"passage": p}
	principal, compagnon = doc["joueurs"]
	assert compagnon["butin_ramasse"] == [{"item": item_id, "poids": 4}]
	assert compagnon["charge"] == 4 and principal["butin_ramasse"] == []
	# Ce que personne n'emporte reste à l'étage.
	assert [m.get("loote", False) for m in doc["monstres"]] == [True, False]
	assert "butin_etage" not in doc["etages"]


def test_une_repartition_vide_laisse_tout_a_l_etage(db):
	doc, p, _ = _etage_vide(db)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente", attributions=[])
	assert res == {"passage": p}
	assert not any(m.get("loote") for m in doc["monstres"])


def test_une_surcharge_refuse_toute_la_repartition(db):
	doc, _, _ = _etage_vide(db, poids=100)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente", attributions=[
		{"monstre_id": "monstre_0", "beneficiaire_id": "character:u_1"},
		{"monstre_id": "monstre_1", "beneficiaire_id": "character:u_1"}])
	assert "error" in res
	assert doc["joueurs"][0]["butin_ramasse"] == [] and doc["joueurs"][0]["charge"] == 0
	assert not any(m.get("loote") for m in doc["monstres"])


def test_une_personne_escortee_ne_recoit_pas_de_butin_d_etage(db):
	doc, _, _ = _etage_vide(db)
	doc["joueurs"].append(joueur_snap("joueur_2", "protege:enfant", x=6, y=6,
									  jouable=False, est_protege=True))
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente", attributions=[
		{"monstre_id": "monstre_0", "beneficiaire_id": "protege:enfant"}])
	assert "error" in res


def test_un_etage_ou_rodent_des_monstres_ne_propose_rien(db):
	doc, p, _ = _etage_vide(db)
	doc["monstres"].append(monstre_snap("monstre_2", x=12, y=12))
	assert combat_util.resolve_action(doc, "emprunter", "connection:descente") == {"passage": p}


def test_la_sortie_ne_propose_pas_la_carcasse_d_un_vivant(db):
	_carcasse_rat(db)
	db["character:u_1"] = character()
	sortie = _passage("connection:sortie", 5, 5, vers="lieu:lutecia", surface=True)
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1", x=5, y=5)],
					 [monstre_snap("monstre_0", vivant=False), monstre_snap("monstre_1")],
					 etages=_etages([sortie]))
	combat_util.resolve_action(doc, "emprunter", "connection:sortie")
	combat_util.finalize_combat(doc)
	assert [d["monstre_id"] for d in doc["butin_disponible"]] == ["monstre_0"]


def test_une_monture_garde_le_butin_charge_sur_elle(db):
	perso = character()
	bete = {"_id": "monture:ane", "type": "monture", "inventaire": [{"item": "item:sel"}],
			"currentPV": 30, "combats_recompenses": []}
	snap = joueur_snap("joueur_1", "monture:ane", est_monture=True,
					   butin_ramasse=[{"item": "item:carcasse_rat", "poids": 4}])
	doc = combat_doc([joueur_snap("joueur_0", perso["_id"]), snap], [], status="victoire")
	combat_util._finalize_monture(doc, snap, bete, "victoire", perso)
	assert bete["inventaire"] == [{"item": "item:sel"}, {"item": "item:carcasse_rat", "poids": 4}]


def test_annoter_passages(db):
	p1 = _passage("connection:a", 5, 5)
	p2 = _passage("connection:b", 0, 0)
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1", x=5, y=5)], [],
					 etages=_etages([p1, p2]))
	combat_util.annoter_passages(doc)
	assert [p["franchissable"] for p in doc["etages"]["passages"]] == [True, False]

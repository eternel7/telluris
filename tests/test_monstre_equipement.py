# tests/test_monstre_equipement.py
#
# Tirage d'équipement d'un monstre HUMANOÏDE (`utils.combat.roll_monster_equipment`) :
# un jet indépendant par item éligible de `espece["items"]`, affecté à un slot libre.
# Pur (get_doc/random injectés via monkeypatch), aucune dépendance DB.

from utils import combat as combat_mod


ARC = {
	"_id": "item:Arc_court", "type": "item", "nom": "Arc court", "categorie": "arme",
	"slots": ["main_droite"], "tags": ["tir"], "portee": 4, "deux_mains": True,
}
CUIRASSE = {
	"_id": "item:Cuir_bouilli", "type": "item", "nom": "Cuir bouilli", "categorie": "armure",
	"slots": ["torse"], "bonus_pa": 5,
}
EPEE = {
	"_id": "item:Epee_courte", "type": "item", "nom": "Épée courte", "categorie": "arme",
	"slots": ["main_droite", "main_gauche"], "tags": [], "portee": 1,
}
CATALOGUE = {d["_id"]: d for d in (ARC, CUIRASSE, EPEE)}


def _espece(items):
	return {"_id": "espece:test", "nom": "Cobaye", "tags": ["humanoide"], "items": items}


def _toujours_equiper(monkeypatch):
	"""Neutralise le hasard : probabilité toujours franchie, ordre stable, premier
	candidat retenu — assignation entièrement déterministe."""
	monkeypatch.setattr(combat_mod.random, "random", lambda: 0.0)
	monkeypatch.setattr(combat_mod.random, "shuffle", lambda l: None)
	monkeypatch.setattr(combat_mod.random, "choice", lambda opts: opts[0])
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: CATALOGUE.get(i))


def test_liste_vide_ne_tire_rien():
	assert combat_mod.roll_monster_equipment(_espece([])) == {}
	assert combat_mod.roll_monster_equipment({}) == {}


def test_assignation_deterministe(monkeypatch):
	_toujours_equiper(monkeypatch)
	slots = combat_mod.roll_monster_equipment(_espece([ARC["_id"]]))
	assert slots == {"main_droite": ARC["_id"]}


def test_arme_deux_mains_bloque_lautre_main_sans_cle(monkeypatch):
	_toujours_equiper(monkeypatch)
	slots = combat_mod.roll_monster_equipment(_espece([ARC["_id"]]))
	assert "main_gauche" not in slots
	assert slots.get("main_droite") == ARC["_id"]


def test_probabilite_a_zero_nequipe_jamais(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "random", lambda: 1.0)
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: CATALOGUE.get(i))
	assert combat_mod.roll_monster_equipment(_espece([ARC["_id"], CUIRASSE["_id"]])) == {}


def test_item_sans_slot_libre_est_ignore_sans_lever(monkeypatch):
	"""Deux armes concurrentes pour LA SEULE main droite libre : la seconde n'a aucun
	candidat et doit être ignorée proprement, jamais lever."""
	monkeypatch.setattr(combat_mod.random, "random", lambda: 0.0)
	monkeypatch.setattr(combat_mod.random, "shuffle", lambda l: None)
	monkeypatch.setattr(combat_mod.random, "choice", lambda opts: opts[0])
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: CATALOGUE.get(i))
	slots = combat_mod.roll_monster_equipment(_espece([ARC["_id"], ARC["_id"]]))
	assert slots == {"main_droite": ARC["_id"]}


def test_item_de_categorie_non_equipable_est_ignore(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "random", lambda: 0.0)
	monkeypatch.setattr(combat_mod.random, "shuffle", lambda l: None)
	monkeypatch.setattr(combat_mod.random, "choice", lambda opts: opts[0])
	compo = {"_id": "item:Restes", "categorie": "composant", "slots": ["torse"]}
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: {compo["_id"]: compo}.get(i))
	assert combat_mod.roll_monster_equipment(_espece([compo["_id"]])) == {}


def test_id_mort_est_ignore(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "random", lambda: 0.0)
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: None)
	assert combat_mod.roll_monster_equipment(_espece(["item:fantome"])) == {}


def test_armure_et_arme_occupent_des_slots_distincts(monkeypatch):
	_toujours_equiper(monkeypatch)
	slots = combat_mod.roll_monster_equipment(_espece([ARC["_id"], CUIRASSE["_id"]]))
	assert slots == {"main_droite": ARC["_id"], "torse": CUIRASSE["_id"]}

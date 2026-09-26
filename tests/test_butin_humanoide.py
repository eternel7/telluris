# tests/test_butin_humanoide.py
# Butin d'un humanoïde : sa carcasse PLUS chacun de ses objets équipés (`slots` tiré par
# `roll_monster_equipment`), une LIGNE par élément, chacune avec sa clé (`cle_butin`) —
# attribuable séparément à la fin du combat comme au butin d'un étage de donjon.
#
# Ce que ces tests ferment : l'équipement d'un humanoïde disparaissait avec lui, et un
# monstre ne pouvait donner qu'une ligne (le butin était indexé par `monstre_id`).

from utils import combat as combat_util

from tests.test_combat_groupe import (
	character, joueur_snap, monstre_snap, combat_doc, db,
)
from tests.test_donjon_etages import _passage, _etages, _groupe


EPEE = {"_id": "item:epee", "type": "item", "nom": "Épée courte", "categorie": "arme",
		"poids": 2.5}
CUIRASSE = {"_id": "item:cuirasse", "type": "item", "nom": "Cuirasse", "categorie": "armure",
			"poids": [8, 12]}


def _peupler(db, poids_carcasse=40):
	carcasse = combat_util._loot_item_id("espece:rat")
	db[carcasse] = {"_id": carcasse, "type": "item", "nom": "Carcasse", "poids": poids_carcasse}
	db[EPEE["_id"]] = dict(EPEE)
	db[CUIRASSE["_id"]] = dict(CUIRASSE)
	return carcasse


def _humanoide(mid="monstre_0", **champs):
	return monstre_snap(mid, vivant=False,
						slots={"main_droite": "item:epee", "torse": "item:cuirasse"}, **champs)


# ── Construction des lignes ───────────────────────────────────────────────────────

def test_un_humanoide_donne_sa_carcasse_puis_chacun_de_ses_objets(db):
	carcasse = _peupler(db)
	lignes = combat_util._butin_du_monstre(_humanoide())
	assert [(d["item_id"], d["cle"]) for d in lignes] == [
		(carcasse, "monstre_0"),
		("item:epee", "monstre_0|main_droite"),
		("item:cuirasse", "monstre_0|torse"),
	]
	assert len({combat_util.cle_butin(d) for d in lignes}) == len(lignes)
	# Poids du doc ; [min, max] ⇒ le min (même repli que `item_ref_weight`).
	assert [d["poids"] for d in lignes[1:]] == [2.5, 8.0]
	assert all(d["monstre_id"] == "monstre_0" for d in lignes)


def test_une_bete_ne_donne_que_sa_carcasse(db):
	carcasse = _peupler(db)
	lignes = combat_util._butin_du_monstre(monstre_snap(vivant=False))
	assert [d["item_id"] for d in lignes] == [carcasse]


def test_un_objet_absent_de_la_base_est_saute(db):
	_peupler(db)
	del db["item:cuirasse"]
	lignes = combat_util._butin_du_monstre(_humanoide())
	assert [d.get("slot") for d in lignes] == [None, "main_droite"]


def test_une_carcasse_ramassee_en_combat_laisse_les_objets(db):
	_peupler(db)
	lignes = combat_util._butin_du_monstre(_humanoide(loote=True))
	assert [d["slot"] for d in lignes] == ["main_droite", "torse"]


def test_une_entree_sans_cle_est_une_carcasse():
	"""Combat déjà en base (CLAUDE.md §4) : la clé retombe sur le `monstre_id`."""
	assert combat_util.cle_butin({"monstre_id": "monstre_3"}) == "monstre_3"


# ── Fin de combat ─────────────────────────────────────────────────────────────────

def test_la_victoire_propose_une_ligne_par_element(db):
	_peupler(db)
	db["character:u_1"] = character()
	doc = combat_doc([joueur_snap("joueur_0", "character:u_1")],
					 [_humanoide(), monstre_snap("monstre_1", vivant=False)], status="victoire")
	combat_util.finalize_combat(doc)
	assert [d["cle"] for d in doc["butin_disponible"]] == [
		"monstre_0", "monstre_0|main_droite", "monstre_0|torse", "monstre_1"]


def test_au_sol_la_garde_est_par_ligne():
	perso = {"_id": "character:a", "inventaire": [],
			 "butin_collectes": {"combat:1": ["monstre_0|main_droite"]}}
	combat = {"_id": "combat:1", "status": "victoire", "butin_disponible": [
		{"monstre_id": "monstre_0", "cle": "monstre_0", "item_id": "item:carcasse", "poids": 40},
		{"monstre_id": "monstre_0", "cle": "monstre_0|main_droite", "slot": "main_droite",
		 "item_id": "item:epee", "poids": 2.5},
	]}
	combat_util.verser_butin_au_sol(perso, combat)
	# L'épée déjà encaissée n'est pas reversée ; la carcasse du MÊME monstre, si.
	assert perso["objets_au_sol"] == [{"item": "item:carcasse", "poids": 40}]
	assert sorted(perso["butin_collectes"]["combat:1"]) == ["monstre_0", "monstre_0|main_droite"]


# ── Étage de donjon ───────────────────────────────────────────────────────────────

def _etage_humanoide(db, poids_carcasse=40):
	_peupler(db, poids_carcasse)
	p = _passage("connection:descente", 5, 5)
	return combat_doc(_groupe(5, 5, 5, 6), [_humanoide(x=0, y=0)], etages=_etages([p])), p


def test_l_etage_propose_chaque_element(db):
	doc, _ = _etage_humanoide(db)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente")
	assert [d["cle"] for d in res["butin_etage"]] == [
		"monstre_0", "monstre_0|main_droite", "monstre_0|torse"]


def test_un_objet_d_etage_va_a_son_beneficiaire_sans_marquer_la_carcasse(db):
	doc, p = _etage_humanoide(db)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente", attributions=[
		{"monstre_id": "monstre_0", "cle": "monstre_0|main_droite",
		 "beneficiaire_id": "aventurier:guilde_ami"},
		{"monstre_id": "monstre_0", "cle": "monstre_0|torse", "beneficiaire_id": "character:u_1"}])
	assert res == {"passage": p}
	principal, compagnon = doc["joueurs"]
	assert compagnon["butin_ramasse"] == [{"item": "item:epee", "poids": 2.5}]
	assert principal["butin_ramasse"] == [{"item": "item:cuirasse", "poids": 8.0}]
	assert not doc["monstres"][0].get("loote")


def test_une_attribution_sans_cle_vise_la_carcasse(db):
	"""Ancien client : `monstre_id` seul ⇒ la carcasse, comme avant."""
	doc, p = _etage_humanoide(db)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente", attributions=[
		{"monstre_id": "monstre_0", "beneficiaire_id": "character:u_1"}])
	assert res == {"passage": p}
	assert doc["joueurs"][0]["butin_ramasse"] == [{"item": "item:rat", "poids": 40}]
	assert doc["monstres"][0]["loote"] is True


def test_une_surcharge_d_etage_refuse_tout(db):
	doc, _ = _etage_humanoide(db, poids_carcasse=145)
	res = combat_util.resolve_action(doc, "emprunter", "connection:descente", attributions=[
		{"monstre_id": "monstre_0", "beneficiaire_id": "character:u_1"},
		{"monstre_id": "monstre_0", "cle": "monstre_0|torse", "beneficiaire_id": "character:u_1"}])
	assert "error" in res
	assert doc["joueurs"][0]["butin_ramasse"] == []
	assert not doc["monstres"][0].get("loote")

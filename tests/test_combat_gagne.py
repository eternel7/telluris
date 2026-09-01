# tests/test_combat_gagne.py
# Le marqueur « cette salle gardée a été nettoyée » et la condition d'accès qui le lit.
#
# ⚠️ Le test qui compte est `test_un_combat_de_ZONE_sur_la_meme_carte_ne_marque_RIEN` : une
# salle de donjon reste un lieu `battle_map` ordinaire, donc TIRABLE COMME DÉCOR par
# `combat.select_battle_map`. Marquer d'après `battle_map_id` ferait « gagner » un combat de
# donjon qui n'a jamais eu lieu — la porte se fermerait et les barrières conditionnées
# dessus s'ouvriraient, après une simple escarmouche en forêt.

import pytest

from utils import acces, donjon
from utils.characters import noter_victoire, victoire_acquise


SALLE = "lieu:grotte_en_foret"
AUTRE = "lieu:la_mine_aux_cristaux"


def _perso(gagnees=None):
	c = {"_id": "character:t", "quetes_actives": [], "quetes_terminees": []}
	if gagnees is not None:
		c["battle_maps_gagnees"] = list(gagnees)
	return c


# ── Le champ et ses accesseurs ──────────────────────────────────────────────────

def test_champ_absent_vaut_aucune_victoire():
	"""Comportement d'avant à la lettre — aucune migration."""
	assert victoire_acquise(_perso(), SALLE) is False
	assert victoire_acquise({}, SALLE) is False
	assert victoire_acquise(None, SALLE) is False


def test_noter_puis_lire():
	c = _perso()
	assert noter_victoire(c, SALLE) is True
	assert c["battle_maps_gagnees"] == [SALLE]
	assert victoire_acquise(c, SALLE) is True
	assert victoire_acquise(c, AUTRE) is False


def test_noter_est_idempotent_et_dedoublonne():
	"""`finalize_combat` peut être rejouée par /play : la liste ne doit pas s'allonger."""
	c = _perso()
	noter_victoire(c, SALLE)
	assert noter_victoire(c, SALLE) is False
	noter_victoire(c, AUTRE)
	assert c["battle_maps_gagnees"] == [SALLE, AUTRE]


def test_noter_refuse_un_lieu_vide():
	c = _perso()
	assert noter_victoire(c, "") is False
	assert noter_victoire(c, None) is False
	assert "battle_maps_gagnees" not in c or c["battle_maps_gagnees"] == []


# ── La condition d'accès `combat_gagne` ─────────────────────────────────────────

def _lieu(condition):
	return {"_id": "lieu:porte", "acces": {"cycle": 1, "refus": "Non.",
										   "conditions": [condition]}}


def _ok(character, condition):
	return acces.acces_autorise(character, _lieu(condition), lambda _i: None)[0]


def test_combat_gagne_dans_les_deux_sens():
	avant, apres = _perso(), _perso([SALLE])
	positif = {"combat_gagne": {"lieu": SALLE}}
	negatif = {"combat_gagne": {"lieu": SALLE, "attendu": False}}

	# La clairière dégagée : fermée tant que les loups tiennent, ouverte après.
	assert _ok(avant, positif) is False
	assert _ok(apres, positif) is True
	# La porte du combat : ouverte une fois, et une seule.
	assert _ok(avant, negatif) is True
	assert _ok(apres, negatif) is False


def test_combat_gagne_vise_bien_LE_lieu_nomme():
	c = _perso([AUTRE])
	assert _ok(c, {"combat_gagne": {"lieu": SALLE}}) is False
	assert _ok(c, {"combat_gagne": {"lieu": AUTRE}}) is True


def test_combat_gagne_est_FAIL_CLOSED():
	"""`lieu` est obligatoire : pas de défaut implicite « la salle qui porte la barrière »,
	qui serait juste pour la porte du combat et faux pour toute barrière conditionnée sur le
	combat d'un AUTRE lieu."""
	c = _perso([SALLE])
	for filtre in ({}, {"lieu": ""}, {"lieu": None}, {"lieu": 42},
				   {"lieu": SALLE, "attendu": "non"}):
		assert _ok(c, {"combat_gagne": filtre}) is False


# ── La négation de `quete_active` ───────────────────────────────────────────────

QUETE = {"id": "quete:x", "objectif": {"type": "escorte", "cible": "lieu:bureau"}}


def _avec_quete():
	c = _perso()
	c["quetes_actives"] = [dict(QUETE)]
	return c


def test_quete_active_attendu_false_est_la_negation():
	"""C'est ce qui masque la grotte VIDE le temps de la mission."""
	filtre = {"types": ["escorte"], "cible": "lieu:bureau"}
	positif = {"quete_active": dict(filtre)}
	negatif = {"quete_active": dict(filtre, attendu=False)}

	assert _ok(_avec_quete(), positif) is True
	assert _ok(_avec_quete(), negatif) is False
	assert _ok(_perso(), positif) is False
	assert _ok(_perso(), negatif) is True


def test_attendu_absent_garde_le_comportement_d_avant():
	filtre = {"types": ["escorte"], "cible": "lieu:bureau"}
	assert _ok(_avec_quete(), {"quete_active": dict(filtre)}) is True
	assert _ok(_avec_quete(), {"quete_active": dict(filtre, attendu=True)}) is True


def test_attendu_illisible_est_fail_closed():
	filtre = {"types": ["escorte"], "cible": "lieu:bureau", "attendu": "false"}
	assert _ok(_avec_quete(), {"quete_active": filtre}) is False


def test_les_deux_cles_sont_declarees_au_vocabulaire():
	"""⚠️ Un SOUS-filtre inconnu est ignoré par le moteur — donc plus PERMISSIF, donc
	invisible. C'est `conditions_invalides` (le linter) qui l'attrape."""
	assert "combat_gagne" in acces.CONDITIONS_CONNUES
	assert "attendu" in acces.SOUS_FILTRES_CONNUS["quete_active"]
	assert acces.SOUS_FILTRES_CONNUS["combat_gagne"] == {"lieu", "attendu"}
	assert acces.conditions_invalides(_lieu({"combat_gagne": {"lieu": SALLE}})) == []
	assert acces.conditions_invalides(
		_lieu({"combat_gagne": {"lieu": SALLE, "attendus": False}})) == ["combat_gagne.attendus"]
	assert acces.conditions_invalides(
		_lieu({"quete_active": {"attendus": False}})) == ["quete_active.attendus"]


# ── `lieu_visite` : le passage à usage unique ───────────────────────────────────

def test_lieu_visite_dans_les_deux_sens():
	vierge = _perso()
	vu = _perso(); vu["lieux_visites"] = ["lieu:clairiere"]
	positif = {"lieu_visite": {"lieu": "lieu:clairiere"}}
	negatif = {"lieu_visite": {"lieu": "lieu:clairiere", "attendu": False}}

	assert _ok(vierge, positif) is False
	assert _ok(vu, positif) is True
	# La forme qui compte : ouvert tant qu'on n'y est pas allé, refermé ensuite.
	assert _ok(vierge, negatif) is True
	assert _ok(vu, negatif) is False


def test_lieu_visite_champ_absent_vaut_jamais_visite():
	"""Comportement d'avant à la lettre — aucune migration."""
	assert _ok(_perso(), {"lieu_visite": {"lieu": "lieu:x", "attendu": False}}) is True


def test_lieu_visite_est_fail_closed():
	c = _perso(); c["lieux_visites"] = ["lieu:clairiere"]
	for filtre in ({}, {"lieu": ""}, {"lieu": None}, {"lieu": 12},
				   {"lieu": "lieu:clairiere", "attendu": "non"}):
		assert _ok(c, {"lieu_visite": filtre}) is False


def test_lieu_visite_est_declare_au_vocabulaire():
	assert "lieu_visite" in acces.CONDITIONS_CONNUES
	assert acces.SOUS_FILTRES_CONNUS["lieu_visite"] == {"lieu", "attendu"}
	assert acces.conditions_invalides(
		_lieu({"lieu_visite": {"lieu": "lieu:x", "attendus": True}})) == ["lieu_visite.attendus"]


def test_un_lieu_referme_reste_QUITTABLE():
	"""⚠️ L'invariante qui rend le passage unique jouable : la barrière porte sur la
	DESTINATION. Un joueur qui vient d'entrer, et dont l'arrivée a refermé la porte derrière
	lui, doit pouvoir ressortir — les lieux de sortie n'ont pas de barrière, et
	`get_lieu_links` ne filtre jamais le lieu courant."""
	c = _perso(); c["lieux_visites"] = ["lieu:clairiere"]
	# La clairière elle-même est désormais fermée…
	assert _ok(c, {"lieu_visite": {"lieu": "lieu:clairiere", "attendu": False}}) is False
	# …mais rien n'empêche d'aller vers un lieu sans barrière.
	assert acces.acces_autorise(c, {"_id": "lieu:auxerre"}, lambda _i: None)[0] is True


# ── donjon_purge : la menace est éliminée, commission ou non ────────────────────

def test_donjon_purge_reconnait_une_victoire_sans_commission():
	"""Sans cela, `acces_libere`/`acces_menace` resteraient réservés aux donjons mandatés et
	Armand réciterait son refus générique à un joueur qui vient d'abattre les loups."""
	assert donjon.donjon_purge(_perso(), SALLE) is False
	assert donjon.donjon_purge(_perso([SALLE]), SALLE) is True
	assert donjon.donjon_purge(_perso([AUTRE]), SALLE) is False


# ── Le hook de finalisation, sur la VRAIE `finalize_combat` ────────────────────
# ⚠️ On appelle le moteur, pas une reformulation de sa ligne : le seul intérêt de ces trois
# tests est de figer QUEL champ est lu. Rejouer la règle à la main les rendrait aveugles
# précisément au changement qu'ils doivent interdire (`salle_gardee` → `battle_map_id`).
# Harnais repris de tests/test_combat_groupe.py.

from utils import combat as combat_util
from utils import characters as characters_util


@pytest.fixture
def db(monkeypatch):
	docs = {}
	monkeypatch.setattr(combat_util, "get_doc", lambda i: docs.get(i))
	monkeypatch.setattr(combat_util, "save_doc", lambda d: docs.setdefault(d["_id"], d) or d)
	monkeypatch.setattr(characters_util, "get_doc", lambda i: docs.get(i))
	return docs


def _joueur():
	return {
		"_id": "character:u_1", "type": "character", "user_id": "user:u",
		"prenom": "Test", "nom": "Héros", "voc": "guerrier", "race": "humain",
		"currentPV": 50, "currentPM": 20, "xp_total": 0, "niveau": 1,
		"attribute_points": 0, "vocations_niveaux": {"guerrier": 1}, "inventaire": [],
		"slots": {}, "quetes_actives": [], "quetes_terminees": [], "combats_recompenses": [],
		"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 30, "Vol": 20,
									 "Int": 20, "Cha": 20, "Ch": 20},
		"lieu": "lieu:auxerre", "effets_actifs": [], "bestiaire": {},
	}


def _snap_joueur(cid):
	return {"id": "joueur_0", "character_id": cid, "nom": "Héros", "currentPV": 40,
			"pv_max": 50, "currentPM": 20, "pm_max": 20, "vivant": True, "pos": {"x": 0, "y": 0},
			"butin_ramasse": [], "effets_actifs": []}


def _combat(cid, status="victoire", salle=None):
	doc = {
		"_id": "combat:test", "type": "combat", "user_id": "user:u", "character_id": cid,
		"status": status, "xp_gagnee": 5, "battle_map_id": SALLE,
		"joueurs": [_snap_joueur(cid)],
		"monstres": [{"id": "monstre_0", "nom": "Loup", "espece_id": "espece:loup_geant",
					  "currentPV": 0, "vivant": False, "pos": {"x": 5, "y": 5}}],
		"ordre_initiative": ["joueur_0", "monstre_0"], "journal": [], "tour": 1,
	}
	if salle:
		doc["salle_gardee"] = salle
	return doc


def test_une_victoire_par_une_porte_gardee_marque_la_salle(db):
	perso = _joueur()
	db[perso["_id"]] = perso
	assert combat_util.finalize_combat(_combat(perso["_id"], salle=SALLE)) is True
	assert victoire_acquise(perso, SALLE) is True


def test_un_combat_de_ZONE_sur_la_meme_carte_ne_marque_RIEN(db):
	"""⚠️ LE test de ce fichier. `lieu:grotte_en_foret` porte les tags `chemin/foret/bois` :
	la moindre escarmouche autour d'Auxerre peut s'y dérouler comme DÉCOR. Le combat porte
	alors `battle_map_id` mais AUCUN `salle_gardee` — rien ne doit être marqué, sinon la
	porte du donjon se fermerait et la clairière s'ouvrirait sans qu'on ait vu un loup."""
	perso = _joueur()
	db[perso["_id"]] = perso
	combat = _combat(perso["_id"])          # battle_map_id présent, salle_gardee absent
	assert combat["battle_map_id"] == SALLE
	assert combat_util.finalize_combat(combat) is True
	assert victoire_acquise(perso, SALLE) is False


@pytest.mark.parametrize("status", ["defaite", "fuite"])
def test_ni_la_defaite_ni_la_fuite_ne_marquent(db, status):
	perso = _joueur()
	db[perso["_id"]] = perso
	combat_util.finalize_combat(_combat(perso["_id"], status=status, salle=SALLE))
	assert victoire_acquise(perso, SALLE) is False

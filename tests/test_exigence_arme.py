# tests/test_exigence_arme.py
#
# Exigence d'ARME d'une compétence (utils/exigence_arme.py) : normalisation du champ `arme`,
# lecture de ce qui est porté, règle de satisfaction, libellé, profil emprunté — et ses
# branchements : passives (`bonus_passifs`), payload ⚡ (`liste_competences_payload`),
# garde de combat (`resolve_action`), emprunt (`combat._profil_emprunte`), simulateur.

from utils import combat as combat_mod
from utils import exigence_arme as ea
from utils import simulateur
from utils.competences import bonus_passifs, liste_competences_payload, normaliser_competence
from utils.combat import resolve_action

ITEMS = {
	"item:Arc": {"_id": "item:Arc", "categorie": "arme", "sous_categorie": "arc", "tags": ["tir"]},
	"item:Arbalete": {"_id": "item:Arbalete", "categorie": "arme", "sous_categorie": "arbalete",
					  "tags": ["tir"]},
	"item:Couteau_jet": {"_id": "item:Couteau_jet", "categorie": "arme", "sous_categorie": "",
						 "tags": ["jet", "tranchant", "legere"]},
	"item:Dague": {"_id": "item:Dague", "categorie": "arme", "sous_categorie": "",
				   "tags": ["cac", "tranchant", "legere"]},
	"item:Hache": {"_id": "item:Hache", "categorie": "arme", "sous_categorie": "",
				   "tags": ["cac", "tranchant", "lourde"]},
	"item:Ecu": {"_id": "item:Ecu", "categorie": "armure", "sous_categorie": "bouclier",
				 "tags": ["armure_cuir"]},
	"item:Bocle": {"_id": "item:Bocle", "categorie": "armure", "sous_categorie": "",
				   "tags": ["armure_cuir"]},
	"item:Casque": {"_id": "item:Casque", "categorie": "armure", "sous_categorie": "casque",
					"tags": []},
}


def _portees(**slots):
	return ea.armes_portees({"slots": slots}, ITEMS.get)


# ── Normalisation ────────────────────────────────────────────────────────────────

def test_normaliser_arme_absente_ou_invalide_ne_pose_aucune_exigence():
	assert ea.normaliser_arme(None) is None
	assert ea.normaliser_arme({}) is None
	assert ea.normaliser_arme({"mode": "lance-pierre"}) is None   # mode inconnu
	assert ea.normaliser_arme("tir") is None                      # pas un bloc


def test_normaliser_arme_mode_seul_ou_liste_et_tags():
	assert ea.normaliser_arme({"mode": "tir"}) == {"modes": ["tir"], "tags": []}
	assert ea.normaliser_arme({"mode": ["tir", "jet", "tir", "x"], "tags": ["arc", "", "arc"]}) \
		== {"modes": ["tir", "jet"], "tags": ["arc"]}


def test_normaliser_competence_porte_l_exigence():
	doc = {"_id": "competence:t", "type": "competence", "vocation": "forestier",
		   "mode": "active", "arme": {"mode": "tir"}}
	assert normaliser_competence(doc)["arme"] == {"modes": ["tir"], "tags": []}
	assert normaliser_competence(dict(doc, arme=None))["arme"] is None


# ── Ce qui est porté ─────────────────────────────────────────────────────────────

def test_armes_portees_lit_armes_et_boucliers_main_droite_d_abord():
	armes = _portees(main_gauche="item:Ecu", main_droite="item:Hache", tete="item:Casque")
	assert [(a["mode"], a["slot"]) for a in armes] == [("cac", "main_droite"),
													   ("bouclier", "main_gauche")]
	# La sous-catégorie compte comme un tag : « arc » sans tag neuf sur l'item.
	assert "arc" in _portees(main_droite="item:Arc")[0]["tags"]
	# Un bouclier sans sous-catégorie n'est pas reconnu (le contenu doit la poser).
	assert _portees(main_gauche="item:Bocle") == []
	# Référence d'inventaire en dict (exemplaire nommé) : même lecture.
	assert _portees(main_droite={"item": "item:Dague", "nom_perso": "Piqûre"})[0]["mode"] == "cac"


# ── Satisfaction ─────────────────────────────────────────────────────────────────

def _ok(arme, **slots):
	return ea.satisfaite(ea.normaliser_arme(arme), _portees(**slots))


def test_mode_simple():
	assert _ok({"mode": "tir"}, main_droite="item:Arc")
	assert not _ok({"mode": "tir"}, main_droite="item:Hache")
	assert not _ok({"mode": "tir"})
	assert _ok({"mode": "jet"}, main_droite="item:Couteau_jet")
	assert _ok({"mode": "bouclier"}, main_gauche="item:Ecu")
	assert not _ok({"mode": "bouclier"}, main_droite="item:Hache")


def test_un_des_modes_suffit():
	assert _ok({"mode": ["tir", "jet"]}, main_droite="item:Couteau_jet")
	assert _ok({"mode": ["tir", "jet"]}, main_droite="item:Arc")
	assert not _ok({"mode": ["tir", "jet"]}, main_droite="item:Dague")


def test_tags_un_des_tags_suffit_sur_l_objet_qui_remplit_le_mode():
	assert _ok({"mode": "tir", "tags": ["arbalete"]}, main_droite="item:Arbalete")
	assert not _ok({"mode": "tir", "tags": ["arbalete"]}, main_droite="item:Arc")
	assert _ok({"mode": "cac", "tags": ["legere"]}, main_droite="item:Dague")
	assert not _ok({"mode": "cac", "tags": ["legere"]}, main_droite="item:Hache")
	# Le tag doit être porté par l'arme du MODE, pas par une autre en main.
	assert not _ok({"mode": "cac", "tags": ["legere"]}, main_droite="item:Hache",
				   main_gauche="item:Couteau_jet")


def test_mains_nues_admet_un_bouclier_mais_aucune_arme():
	assert _ok({"mode": "mains_nues"})
	assert _ok({"mode": "mains_nues"}, main_gauche="item:Ecu")
	assert not _ok({"mode": "mains_nues"}, main_droite="item:Dague")
	assert not _ok({"mode": "mains_nues"}, main_droite="item:Arc")


def test_deux_armes_exige_deux_armes_de_melee_qui_portent_chacune_le_tag():
	assert _ok({"mode": "deux_armes"}, main_droite="item:Dague", main_gauche="item:Hache")
	assert not _ok({"mode": "deux_armes"}, main_droite="item:Dague", main_gauche="item:Ecu")
	assert not _ok({"mode": "deux_armes", "tags": ["legere"]},
				   main_droite="item:Dague", main_gauche="item:Hache")


def test_sans_exigence_ou_porte_inconnu_rien_n_est_refuse():
	assert ea.satisfaite(None, [])
	# Snapshot d'avant (pas de clé `armes_portees`) : aucune vérification.
	assert ea.satisfaite({"modes": ["tir"], "tags": []}, None)


def test_libelle():
	assert ea.libelle(None) == ""
	assert ea.libelle(ea.normaliser_arme({"mode": "tir", "tags": ["arc"]})) == "une arme de tir (arc)"
	assert ea.libelle(ea.normaliser_arme({"mode": ["jet", "tir"]})) == "une arme de jet ou une arme de tir"
	assert ea.libelle(ea.normaliser_arme({"mode": "mains_nues", "tags": ["x"]})) == "les mains nues"


def test_mode_emprunte_suit_le_premier_mode_rempli():
	arme = ea.normaliser_arme({"mode": ["jet", "tir"]})
	assert ea.mode_emprunte(arme, _portees(main_droite="item:Arc", main_gauche="item:Couteau_jet")) == "jet"
	assert ea.mode_emprunte(arme, _portees(main_droite="item:Arc")) == "tir"
	assert ea.mode_emprunte(ea.normaliser_arme({"mode": "deux_armes"}),
							_portees(main_droite="item:Dague", main_gauche="item:Hache")) == "cac"
	# Bouclier / mains nues ne désignent aucun profil ; rien de connu ⇒ règle d'avant.
	assert ea.mode_emprunte(ea.normaliser_arme({"mode": "bouclier"}), _portees(main_gauche="item:Ecu")) is None
	assert ea.mode_emprunte(arme, None) is None


# ── Passives ─────────────────────────────────────────────────────────────────────

_MAITRISE_ARC = {"_id": "competence:maitrise_arc", "type": "competence", "nom": "Maîtrise de l'arc",
				 "vocation": "forestier", "niveau": 9, "mode": "passive",
				 "arme": {"mode": "tir", "tags": ["arc"]}, "effets": {"buffs": {"Ag": 5}}}
_DOCS = {**ITEMS, _MAITRISE_ARC["_id"]: _MAITRISE_ARC}


def _perso(**slots):
	return {"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 40, "Vol": 30,
										 "Int": 20, "Cha": 20, "Ch": 20},
			"currentPV": 50, "currentPM": 20, "voc": "forestier", "inventaire": [],
			"slots": slots, "competences_connues": [_MAITRISE_ARC["_id"]], "effets_actifs": []}


def test_passive_a_exigence_ne_compte_que_l_arme_en_main():
	assert bonus_passifs(_perso(main_droite="item:Arc"), _DOCS.get)["buffs"] == {"Ag": 5}
	assert bonus_passifs(_perso(main_droite="item:Arbalete"), _DOCS.get)["buffs"] == {}
	assert bonus_passifs(_perso(), _DOCS.get)["buffs"] == {}


# ── Payload ⚡ ────────────────────────────────────────────────────────────────────

_TIR = {"_id": "competence:tir", "type": "competence", "nom": "Tir précis", "vocation": "forestier",
		"niveau": 0, "mode": "active", "cible": "ennemi", "jet": "cd", "portee": 8,
		"arme": {"mode": "tir"}, "effets": {"degats": "1D8"}}
_POSTURE = {"_id": "competence:posture", "type": "competence", "nom": "Garde", "vocation": "templier",
			"niveau": 0, "mode": "active", "cible": "soi", "arme": {"mode": "bouclier"},
			"effets": {"esquive": 5, "duree": 2}}
_DOCS_P = {**_DOCS, _TIR["_id"]: _TIR, _POSTURE["_id"]: _POSTURE}


def _perso_p(**slots):
	return dict(_perso(**slots), competences_connues=[_TIR["_id"], _POSTURE["_id"], _MAITRISE_ARC["_id"]])


def test_payload_porte_libelle_etat_et_profil_emprunte():
	par_id = {c["competence_id"]: c for c in liste_competences_payload(
		_perso_p(main_droite="item:Arc"), _DOCS_P.get, "exploration", etat_charge=(0, 0))}
	assert par_id["competence:tir"]["arme_requise"] == "une arme de tir"
	assert par_id["competence:tir"]["arme_ok"] is True
	assert par_id["competence:tir"]["arme_profil"] == "tir"
	assert par_id["competence:maitrise_arc"]["arme_ok"] is True
	# Sans bouclier : la posture n'est pas « utilisable » hors combat, et le dit.
	assert par_id["competence:posture"]["arme_ok"] is False
	assert par_id["competence:posture"]["utilisable"] is False


def test_payload_combat_garde_la_competence_grisee():
	(tir,) = [c for c in liste_competences_payload(_perso_p(main_droite="item:Hache"), _DOCS_P.get,
												   "combat", etat_charge=(0, 0))
			  if c["competence_id"] == "competence:tir"]
	assert tir["arme_ok"] is False and tir["arme_profil"] is None


def test_payload_sans_exigence_reste_neutre():
	doc = dict(_TIR, _id="competence:libre", arme=None)
	(c,) = liste_competences_payload(dict(_perso(), competences_connues=["competence:libre"]),
									 {"competence:libre": doc}.get, "exploration", etat_charge=(0, 0))
	assert c["arme_requise"] == "" and c["arme_ok"] is True and c["arme_profil"] is None


# ── Combat : garde et emprunt ────────────────────────────────────────────────────

_PROFIL_ARC = {"mode": "tir", "portee": 10, "ranged": True, "toucher": "cd", "degats": "degats_cd"}
_PROFIL_LANCER = {"mode": "jet", "portee": 4, "ranged": True, "toucher": "cc", "degats": "degats_cc"}


def _combat(armes, profils):
	joueur = {
		"id": "joueur_0", "nom": "Frida", "vivant": True,
		"currentPV": 60, "pv_max": 80, "currentPM": 20, "pm_max": 30,
		"actions_restantes": 3, "actions_max": 3,
		"cells_moved": 0, "attaques": 0, "ramasses": 0, "consommes": 0, "sorts": 0,
		"competences": 0, "pos": {"x": 3, "y": 5}, "portee": 1,
		"charge": 10.0, "charge_max": 100.0, "deplacement": 4, "deplacement_base": 4,
		"cc": 50, "cd": 40, "ag": 30, "pa": 5, "pm_def": 20, "toucher_magique": 50,
		"initiative": 30, "attaque_profils": profils, "degats_cc": "1D4", "degats_cd": "1D6",
	}
	if armes is not None:
		joueur["armes_portees"] = armes
	monstre = {"id": "monstre_0", "nom": "Loup", "vivant": True, "pos": {"x": 3, "y": 3},
			   "currentPV": 20, "pv_max": 20, "pa": 5, "ag": 30, "pm_def": 30,
			   "initiative": 20, "deplacement": 3, "xp_reward": 5}
	return {"type": "combat", "status": "active", "tour": 1, "log": [],
			"ordre_initiative": ["joueur_0", "monstre_0"], "acteur_courant_index": 0,
			"joueurs": [joueur], "monstres": [monstre],
			"grid": {"dims": {"x": 7, "y": 7}, "cells": [[1] * 7 for _ in range(7)], "nav": {}}}


def test_combat_refuse_sans_l_arme_et_ne_debite_rien():
	combat = _combat(_portees(main_droite="item:Hache"), [])
	res = resolve_action(combat, "competence", cible_id="monstre_0",
						 competence=normaliser_competence(_TIR))
	assert res == {"error": "Cette compétence exige une arme de tir."}
	assert combat["joueurs"][0]["competences"] == 0
	assert combat["joueurs"][0]["actions_restantes"] == 3


def test_combat_accepte_avec_l_arme(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)
	combat = _combat(_portees(main_droite="item:Arc"), [_PROFIL_ARC])
	res = resolve_action(combat, "competence", cible_id="monstre_0",
						 competence=normaliser_competence(_TIR))
	assert "error" not in res, res


def test_combat_snapshot_d_avant_sans_armes_portees_ne_verifie_rien(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)
	combat = _combat(None, [])
	res = resolve_action(combat, "competence", cible_id="monstre_0",
						 competence=normaliser_competence(_TIR))
	assert "error" not in res, res


def test_emprunt_aligne_sur_l_exigence():
	couteaux = normaliser_competence(dict(_TIR, _id="competence:couteaux", arme={"mode": "jet"}))
	joueur = {"attaque_profils": [_PROFIL_LANCER, _PROFIL_ARC],
			  "armes_portees": _portees(main_droite="item:Arc", main_gauche="item:Couteau_jet")}
	# Sans exigence, un `cd` prend l'arc d'abord ; avec `jet` exigé, le couteau.
	assert combat_mod._profil_emprunte(joueur, dict(couteaux, arme=None))["mode"] == "tir"
	assert combat_mod._profil_emprunte(joueur, couteaux)["mode"] == "jet"
	assert combat_mod._portee_competence(joueur, couteaux) == (8, True)   # max(4, 8 écrite)


# ── Simulateur ───────────────────────────────────────────────────────────────────

def test_simulateur_ecarte_la_competence_dont_l_arme_manque():
	docs = {**_DOCS_P}
	perso = dict(_perso_p(main_droite="item:Hache"),
				 slots_actions=[{"type": "competence", "ref": "competence:tir"}])
	assert simulateur._arsenal_de_barre(perso, docs.get)["competences"] == []
	perso["slots"] = {"main_droite": "item:Arc"}
	assert [c["id"] for c in simulateur._arsenal_de_barre(perso, docs.get)["competences"]] \
		== ["competence:tir"]

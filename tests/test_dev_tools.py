"""utils/dev_tools.py — la liste blanche des outils de dev/ et ses outils PARAMÉTRÉS (/admin/lieux).

Verrouille la frontière de sécurité de ces écrans : le client n'envoie qu'un id et des valeurs
TYPÉES, jamais un chemin ni un morceau d'argv ; les fichiers relus sont écrits par le serveur ;
et 📥 Importer ne peut pas envoyer le fichier d'un run précédent (import = PUT complet).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import dev_tools as dt

VILLES = ["lieu:lutecia", "lieu:auxerre"]
OUTILS_LIEUX = ["lieux_magasins_json", "lieux_progeniture", "lieux_audit_economy"]


def _outil(outil_id):
	return dt._PAR_ID[outil_id]


# ── Catalogue ────────────────────────────────────────────────────────────────

def test_payload_sans_argv_ni_fonction():
	for portee in (None, "lieux"):
		for o in dt.catalogue_payload(portee):
			assert "argv" not in o and "argv_fn" not in o


def test_dev_tools_ne_liste_que_les_outils_sans_parametre():
	ids = {o["id"] for o in dt.catalogue_payload()}
	assert {"audit_economy", "pytest"} <= ids
	assert not ids & set(OUTILS_LIEUX)


def test_page_lieux_liste_ses_outils():
	assert [o["id"] for o in dt.catalogue_payload("lieux")] == OUTILS_LIEUX


def test_forme_des_entrees():
	for o in dt.CATALOGUE:
		if o.get("params"):
			assert callable(o.get("argv_fn")) and o.get("dump_frais"), o["id"]
			assert all(p["type"] in dt._TYPES_PARAM for p in o["params"]), o["id"]
		else:
			assert isinstance(o.get("argv"), list), o["id"]


# ── Validation des paramètres ────────────────────────────────────────────────

@pytest.mark.parametrize("ville", [
	"../etc/passwd", "lieu:Lutecia", "lieu:lutecia;rm -rf", "lieu:", "lutecia", 42, None,
	"lieu:lutecia --dernier", ["lieu:lutecia"],
])
def test_ville_mal_formee_refusee(ville):
	valeurs, refus = dt.valider_params(_outil("lieux_audit_economy"), {"ville": ville}, VILLES)
	assert valeurs is None and refus


def test_ville_bien_formee_mais_inconnue_refusee():
	valeurs, refus = dt.valider_params(_outil("lieux_audit_economy"), {"ville": "lieu:rhemi"}, VILLES)
	assert valeurs is None and "pas une ville connue" in refus


def test_parametre_inconnu_refuse():
	valeurs, refus = dt.valider_params(_outil("lieux_audit_economy"),
									   {"ville": "lieu:lutecia", "argv": ["sh"]}, VILLES)
	assert valeurs is None and "inconnu" in refus


def test_outil_sans_parametre_refuse_des_parametres():
	assert dt.valider_params(_outil("pytest"), None) == ({}, None)
	assert dt.valider_params(_outil("pytest"), {"x": 1})[1]


def test_lieux_dedoublonnes_et_bornes():
	o = _outil("lieux_progeniture")
	assert dt.valider_params(o, {"lieux": ["lieu:a", "lieu:b", "lieu:a"]}) == ({"lieux": ["lieu:a", "lieu:b"]}, None)
	assert dt.valider_params(o, {"lieux": []})[1]
	assert dt.valider_params(o, {"lieux": ["lieu:a", "../x"]})[1]
	assert dt.valider_params(o, {"lieux": "lieu:a"})[1]
	assert dt.valider_params(o, {"lieux": [f"lieu:l{i}" for i in range(dt.LIEUX_MAX + 1)]})[1]


def test_json_doit_etre_un_objet_borne():
	o = _outil("lieux_magasins_json")
	assert dt.valider_params(o, {"ville": "lieu:lutecia", "spec": [1]}, VILLES)[1]
	gros = {"x": "a" * (dt.JSON_OCTETS_MAX + 1)}
	assert dt.valider_params(o, {"ville": "lieu:lutecia", "spec": gros}, VILLES)[1]


def test_argv_est_une_liste_des_seules_valeurs_validees():
	o = _outil("lieux_audit_economy")
	valeurs, _ = dt.valider_params(o, {"ville": "lieu:lutecia"}, VILLES)
	argv = o["argv_fn"](valeurs, {"dump": "jsons/telluris-dump-1.json"})
	assert argv[-4:] == [os.path.join("dev", "audit_economy.py"), "jsons/telluris-dump-1.json",
						 "--ville", "lieu:lutecia"]
	o = _outil("lieux_progeniture")
	valeurs, _ = dt.valider_params(o, {"lieux": ["lieu:a", "lieu:b"]})
	assert o["argv_fn"](valeurs, {"dump": "d.json"})[-4:] == ["--dump", "d.json", "--lieux", "lieu:a,lieu:b"]


def test_spec_ecrite_force_la_ville_affichee():
	o = _outil("lieux_magasins_json")
	valeurs, _ = dt.valider_params(o, {"ville": "lieu:lutecia",
									   "spec": {"cite": "lieu:auxerre", "magasins": []}}, VILLES)
	assert dt.spec_a_ecrire(o, valeurs) == {"cite": "lieu:lutecia", "magasins": []}
	assert dt.spec_a_ecrire(_outil("lieux_audit_economy"), {"ville": "lieu:lutecia"}) is None


def test_est_ville_lit_aussi_la_sous_categorie():
	assert dt.est_ville({"categorie": "", "sous_categorie": "capitale"})   # Lutèce
	assert dt.est_ville({"categorie": "ville"})
	assert not dt.est_ville({"categorie": "pays"})


# ── Lancement ────────────────────────────────────────────────────────────────

def test_lancer_refuse_avant_toute_preparation(monkeypatch):
	monkeypatch.setattr(dt, "_RUN", None)
	appels = []
	run, erreur = dt.lancer("lieux_audit_economy", {"ville": "../x"},
							preparer=lambda o, v: appels.append(1), villes_connues=VILLES)
	assert run is None and erreur[0] == 422 and appels == []
	run, erreur = dt.lancer("lieux_audit_economy", {"ville": "lieu:lutecia"}, villes_connues=VILLES)
	assert run is None and erreur[0] == 500


def test_pas_de_dump_ecrit_si_un_run_tourne(monkeypatch):
	monkeypatch.setattr(dt, "_RUN", {"fini": False, "label": "autre"})
	appels = []
	run, erreur = dt.lancer("lieux_audit_economy", {"ville": "lieu:lutecia"},
							preparer=lambda o, v: appels.append(1), villes_connues=VILLES)
	assert erreur[0] == 409 and appels == []


def test_lancer_prepare_puis_lance_l_argv_construit(monkeypatch):
	monkeypatch.setattr(dt, "_RUN", None)
	vu = {}

	def faux_popen(argv, **kw):
		vu["argv"], vu["shell"] = argv, kw.get("shell")
		raise FileNotFoundError

	monkeypatch.setattr(dt.subprocess, "Popen", faux_popen)
	run, erreur = dt.lancer("lieux_audit_economy", {"ville": "lieu:lutecia"},
							preparer=lambda o, v: {"dump": "jsons/d.json"}, villes_connues=VILLES)
	assert erreur is None and run["code"] == 127
	assert isinstance(vu["argv"], list) and not vu["shell"]
	assert vu["argv"][-3:] == ["jsons/d.json", "--ville", "lieu:lutecia"]
	assert "# dump écrit par le serveur : jsons/d.json" in run["lignes"]


# ── 📥 Importer : jamais le fichier d'un autre run ───────────────────────────

def test_sortie_fraiche(monkeypatch):
	o = "lieux_magasins_json"
	monkeypatch.setattr(dt, "_RUN", None)
	assert dt.sortie_fraiche(o)[1][0] == 409
	monkeypatch.setattr(dt, "_RUN", {"outil": o, "fini": True, "code": 1, "debut": 100.0})
	assert dt.sortie_fraiche(o, mtime_fn=lambda p: 150.0)[1][0] == 409          # run en échec
	monkeypatch.setattr(dt, "_RUN", {"outil": o, "fini": True, "code": 0, "debut": 100.0})
	assert dt.sortie_fraiche(o, mtime_fn=lambda p: 50.0)[1][0] == 409           # fichier antérieur
	assert dt.sortie_fraiche(o, mtime_fn=lambda p: 150.0) == ("jsons/magasins_a_importer.json", None)
	assert dt.sortie_fraiche("lieux_audit_economy")[1][0] == 404               # aucune sortie
	monkeypatch.setattr(dt, "_RUN", {"outil": "lieux_progeniture", "fini": True, "code": 0, "debut": 100.0})
	assert dt.sortie_fraiche(o, mtime_fn=lambda p: 150.0)[1][0] == 409          # autre outil

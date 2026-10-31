"""Portraits propres aux guides : choix, service par /characters, catalogue et gabarits d'images."""

import importlib.util
import os
import random
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils import guides
from utils.statiques import PortraitsStatic

DEV = os.path.join(os.path.dirname(__file__), "..", "dev")


def _charger(nom):
	sys.path.insert(0, DEV)
	spec = importlib.util.spec_from_file_location(nom, os.path.join(DEV, f"{nom}.py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


PORTRAITS = ["guide_routes_f_nain01.jpg", "guide_routes_m_nain01.jpg", "guide_routes_f_elfe01.jpg",
			 "guide_peau_de_loup_f_nain02.jpg", "guide_routes_f_nain.txt", "autre.jpg"]


def test_le_type_le_sexe_et_la_lignee_sont_stricts():
	choix = guides.choisir_portrait_guide("guide_des_routes", {"portrait": "routes"}, "F", "nain",
										  PORTRAITS, random.Random(1))
	assert choix == "guide_routes_f_nain01.jpg"


def test_un_type_a_underscores_se_lit_entier():
	assert (guides.choisir_portrait_guide("peau_de_loup", {}, "F", "nain", PORTRAITS, random.Random(1))
			== "guide_peau_de_loup_f_nain02.jpg")


def test_aucun_portrait_du_type_rend_vide():
	assert guides.choisir_portrait_guide("marin", {}, "F", "nain", PORTRAITS) == ""


INDEX = {d["_id"]: d for d in [
	{"_id": "lieu:italie", "categorie": "pays"},
	{"_id": "lieu:france", "categorie": "pays"},
	{"_id": "lieu:rome", "categorie": "ville", "lieu_parent": "lieu:italie"},
	{"_id": "lieu:auberge", "categorie": "auberge", "lieu_parent": "lieu:rome"},
	{"_id": "lieu:bourg", "categorie": "ville", "lieu_parent": "lieu:france"},
	{"_id": "lieu:auberge_fr", "categorie": "auberge", "lieu_parent": "lieu:bourg"},
]}


def test_un_type_de_pays_ne_s_offre_que_dans_ce_pays():
	metier = {"offre": {"pays": ["lieu:italie"]}}
	assert guides.metier_disponible(metier, "lieu:auberge", INDEX)
	assert not guides.metier_disponible(metier, "lieu:auberge_fr", INDEX)


STATS = {"V": 10, "F": 10, "R": 10, "Ag": 10, "Vol": 10, "Int": 10, "Cha": 10, "Ch": 10}
RACES = [{"id": "nain", "stats": STATS, "stats_max": {k: 40 for k in STATS}}]


def _regles():
	return {"duree_offre_secondes": 10, "metiers": {
		"routes": {"label": "Routes", "offre": {"partout": True}, "savoir": {}, "portrait_voc": "forestier"}}}


def test_generer_prefere_le_portrait_du_type_et_garde_le_repli():
	lieu = INDEX["lieu:auberge"]
	sexes = {"F": "f", "M": "m"}
	propres = [f"guide_routes_{s}_nain01.jpg" for s in sexes.values()]
	avec = guides.generer_guide("routes", lieu, INDEX, _regles(), RACES, ["forestier_f_nain01.jpg", "forestier_m_nain01.jpg"],
								random.Random(1), None, propres)
	assert avec["image"] == f"guide_routes_{sexes[avec['sex']]}_nain01.jpg"
	sans = guides.generer_guide("routes", lieu, INDEX, _regles(), RACES, ["forestier_f_nain01.jpg", "forestier_m_nain01.jpg"],
								random.Random(1))
	assert sans["image"] == f"forestier_{sexes[sans['sex']]}_nain01.jpg"


def test_characters_sert_un_portrait_de_guide_depuis_pnj(tmp_path):
	chars, pnj = tmp_path / "characters", tmp_path / "pnj"
	chars.mkdir()
	pnj.mkdir()
	(chars / "guerrier_m_nain01.jpg").write_bytes(b"perso")
	(pnj / "guide_routes_f_nain01.jpg").write_bytes(b"guide")
	(pnj / "tenancier.jpg").write_bytes(b"secret")
	app = FastAPI()
	app.mount("/characters", PortraitsStatic(directory=str(chars), dossier_guides=str(pnj)))
	client = TestClient(app)
	assert client.get("/characters/guerrier_m_nain01.jpg").content == b"perso"
	assert client.get("/characters/guide_routes_f_nain01.jpg").content == b"guide"
	assert client.get("/characters/tenancier.jpg").status_code == 404
	assert client.get("/characters/guide_inconnu.jpg").status_code == 404


def test_le_catalogue_a_un_gabarit_d_image_par_type():
	metiers = _charger("gen_guides").DOC["metiers"]
	gabarits = _charger("gabarits_guides").GUIDES
	assert {m.get("portrait") or mid for mid, m in metiers.items()} == set(gabarits)
	for qui, variantes in gabarits.values():
		assert qui and len(variantes) == 10


def test_les_types_de_pays_gardent_le_service_de_leur_modele():
	gen = _charger("gen_guides")
	for type_id, modele, pays, *_ in gen.TYPES_PAR_PAYS:
		m, base = gen.DOC["metiers"][type_id], gen.DOC["metiers"][modele]
		assert m["offre"] == {"pays": [pays]}
		for champ in ("arrhes_cuivre", "question_cuivre", "savoir", "equipement"):
			assert m[champ] == base[champ]


def test_les_presentations_n_imposent_aucun_genre():
	for mid, m in _charger("gen_guides").DOC["metiers"].items():
		mots = m["repliques"]["presentation"].lower().replace(",", " ").split()
		assert not {"il", "lui", "elle"} & set(mots), mid


def test_vingt_images_par_type_et_cles_uniques():
	images = _charger("gen_images_guides")
	entrees = images.entrees()
	attendu = len(images.GUIDES) * len(images.LIGNEES) * len(images.SEXES) * images.PAR_SEXE
	assert len(entrees) == attendu
	assert len({e["key"] for e in entrees}) == attendu
	assert all(e["base"].startswith("guide_") for e in entrees)


def test_prompt_respecte_les_consignes():
	images = _charger("gen_images_guides")
	par_cle = {e["key"]: e for e in images.entrees()}
	naine = images.prompt_guide(par_cle["guide_routes_f_nain#1"])
	assert naine.startswith("Réalise l'image d'une naine")
	assert "imberbe" in naine and "Pas de texte visible" in naine
	assert "jamais verte" in images.prompt_guide(par_cle["guide_routes_f_ogre#1"])


def test_aucun_prompt_ne_fait_poser_un_autre_personnage():
	images = _charger("gen_images_guides")
	for e in images.entrees():
		prompt = images.prompt_guide(e)
		assert "au même plan" not in prompt and "{" not in prompt, e["key"]
		assert "aucun autre personnage" in prompt, e["key"]

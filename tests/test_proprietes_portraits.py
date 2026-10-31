# tests/test_proprietes_portraits.py
# Portraits du personnel : groupe du métier, Lignée et sexe du fichier repris par le candidat.

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dev"))

from gabarits_personnel import GROUPES
from utils import escorte, proprietes

PORTRAITS = ["personnel_soin_f_nain01.jpg", "personnel_soin_m_elfe02.jpg",
			 "personnel_garde_f_ogre01.jpg", "autre.jpg", "personnel_soin_f_nain.txt"]
CAT = {"metiers": [{"id": "medecin", "label": "Médecin", "cout_embauche_cuivre": 1},
				   {"id": "meunier", "label": "Meunier", "cout_embauche_cuivre": 1}]}


def test_table_des_groupes_identique_aux_gabarits():
	depuis_gabarits = {m: g for g, (metiers, _, _) in GROUPES.items() for m in metiers}
	assert proprietes.GROUPE_PORTRAIT == depuis_gabarits


def test_visage_du_groupe_du_metier_seulement():
	for graine in range(30):
		race, sexe, portrait = proprietes._visage("medecin", PORTRAITS, random.Random(graine))
		assert (race, sexe, portrait) in {("nain", "F", "personnel_soin_f_nain01.jpg"),
										  ("elfe", "M", "personnel_soin_m_elfe02.jpg")}


def test_lignees_a_chances_egales_malgre_un_nombre_d_images_inegal():
	pool = [f"personnel_soin_f_nain{n:02}.jpg" for n in range(1, 10)] + ["personnel_soin_f_elfe01.jpg"]
	rand = random.Random(1)
	elfes = sum(proprietes._visage("medecin", pool, rand)[0] == "elfe" for _ in range(1000))
	assert 400 < elfes < 600


def test_sans_image_du_groupe_pas_de_visage():
	assert proprietes._visage("boucher", PORTRAITS, random.Random(1)) is None
	assert proprietes._visage("meunier", PORTRAITS, random.Random(1)) is None


def test_candidat_coherent_avec_son_portrait_sinon_regle_d_avant():
	postes = [{"amenagement": "a", "metier": "medecin"}, {"amenagement": "b", "metier": "meunier"}]
	cat = {**CAT, "amenagements": []}
	medecin, meunier = proprietes._candidats_pour(postes, cat, lambda _: None, ["p.jpg"], random.Random(3),
												  portraits_personnel=PORTRAITS)
	assert medecin["portrait"].startswith("personnel_soin_")
	assert medecin["sex"].lower() == medecin["portrait"].split("_")[2]
	assert medecin["race"] in medecin["portrait"]
	assert meunier["portrait"] == "p.jpg" and meunier["race"] == proprietes.RACE_PERSONNEL


METIERS_SOIN = [m for m, g in proprietes.GROUPE_PORTRAIT.items() if g == "soin"]
IMAGES_SOIN = [f"personnel_soin_{s}_{r}01.jpg" for s in "fm" for r in ("nain", "elfe")]


def _postes(metiers):
	return [{"amenagement": f"a{i}", "metier": m} for i, m in enumerate(metiers)]


def test_metiers_d_un_meme_groupe_jamais_la_meme_image_dans_un_tirage():
	metiers = METIERS_SOIN[:len(IMAGES_SOIN)]
	assert len(metiers) >= 2      # sinon le test passerait à vide
	cat = {**CAT, "metiers": [{"id": m} for m in metiers], "amenagements": []}
	for graine in range(50):
		cands = proprietes._candidats_pour(_postes(metiers), cat, lambda _: None, [], random.Random(graine),
										   portraits_personnel=IMAGES_SOIN)
		portraits = [c["portrait"] for c in cands]
		assert len(portraits) == len(metiers) == len(set(portraits))


def test_completer_le_tableau_evite_les_images_des_candidats_gardes():
	metier = METIERS_SOIN[0]
	cat = {**CAT, "metiers": [{"id": metier}], "amenagements": []}
	for graine in range(30):
		[c] = proprietes._candidats_pour(_postes([metier]), cat, lambda _: None, [], random.Random(graine),
										 portraits_personnel=IMAGES_SOIN, deja_pris=set(IMAGES_SOIN[:-1]))
		assert c["portrait"] == IMAGES_SOIN[-1]


def _monde_sans_tenue(monkeypatch):
	metier = METIERS_SOIN[0]
	monkeypatch.setattr(proprietes, "postes_libres", lambda *_: _postes([metier]))
	monkeypatch.setattr(proprietes, "candidats_par_poste", lambda *_: 1)
	return {**CAT, "metiers": [{"id": metier}], "amenagements": []}


def test_nouveau_tableau_evite_les_portraits_des_employes(monkeypatch):
	cat = _monde_sans_tenue(monkeypatch)
	employes = [{"portrait": p} for p in IMAGES_SOIN[:-1]]
	for graine in range(30):
		[c] = proprietes.generer_candidats({}, cat, employes, lambda _: None, [], random.Random(graine),
										   portraits_personnel=IMAGES_SOIN)
		assert c["portrait"] == IMAGES_SOIN[-1]


def test_tableau_complete_evite_aussi_les_portraits_des_employes(monkeypatch):
	cat = _monde_sans_tenue(monkeypatch)
	employes = [{"portrait": p} for p in IMAGES_SOIN[:-1]]
	prop = {"candidats": [], "candidats_expire_at": 100}
	assert proprietes.rafraichir_candidats(prop, cat, employes, lambda _: None, [], now=0, rand=random.Random(1),
										   portraits_personnel=IMAGES_SOIN)
	assert [c["portrait"] for c in prop["candidats"]] == IMAGES_SOIN[-1:]


def test_groupe_epuise_reutilise_une_image_du_groupe():
	metiers = METIERS_SOIN[:2]
	cat = {**CAT, "metiers": [{"id": m} for m in metiers], "amenagements": []}
	cands = proprietes._candidats_pour(_postes(metiers), cat, lambda _: None, [], random.Random(1),
									   portraits_personnel=IMAGES_SOIN[:1])
	assert [c["portrait"] for c in cands] == IMAGES_SOIN[:1] * 2


def test_tout_metier_a_ses_portraits_servis_depuis_pnj():
	reels = proprietes.portraits_personnel_disponibles()
	rand = random.Random(1)
	for metier in proprietes.GROUPE_PORTRAIT:
		race, _, portrait = proprietes._visage(metier, reels, rand)
		assert race in {"humain", "elfe", "nain", "ogre", "hobbit"}
		assert escorte.image_protege(portrait)[0] == "/pnj"
	assert not any(p.startswith("full_") for p in reels)

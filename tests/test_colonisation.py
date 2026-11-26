"""Voie de colonisation — logique pure (`utils/colonisation.py`) et son générateur.

Décisions verrouillées : docs/lore/systemes/20261112_voie_de_colonisation.md. Règles en
mémoire, bâties par le générateur (`gen.generer` sur un dump vide) : aucun fichier de `jsons/`."""

import copy
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_colonisation as gen  # noqa: E402

from db import config as db_config  # noqa: E402
from utils import colonisation as col  # noqa: E402
from utils import enseignes_icones  # noqa: E402
from utils.recrutement import RANGS  # noqa: E402

DOCS = gen.generer({})
REGLES_DOC = next(d for d in DOCS if d["_id"] == col.REGLES_ID)
MODELES = [d for d in DOCS if d["_id"] != col.REGLES_ID]


def _reg():
	return col.regles({col.REGLES_ID: copy.deepcopy(REGLES_DOC)}.get)


W, H = 30, 20
ZONE_FORET = {"_id": "zone:foret", "terrain_tags": ["foret", "riviere", "colline"], "modificateurs": {"danger": 2}}
ZONE_DEFS = {"zone:foret": ZONE_FORET}


def _pays():
	cells = [[1] * W for _ in range(H)]
	cells[10][21] = 5                       # une case d'eau près du site
	cells[0][0] = 0                         # hors pays
	return {"_id": "lieu:pays", "type": "lieu", "categorie": "pays", "label": "Pays", "tags": ["tempere"],
			"dimensions": {"x": W, "y": H}, "cells": cells,
			"zone_influences": [{"x": 20, "y": 10, "w": 8, "h": 8, "rot": 0, "forme": "rectangle", "zone": "zone:foret"}],
			"rencontres": [{"espece": "espece:loup", "zones": ["zone:foret"]}],
			"ressources": [{"ressource": "item:Baies", "zones": ["zone:foret"]}]}


RELIES = [{"id": "lieu:cite", "label": "Cité", "categorie": "ville", "pos": [5, 5]},
		  {"id": "lieu:autre", "label": "Autre", "categorie": "ville", "pos": [29, 19]},
		  {"id": "lieu:grotte", "label": "Grotte", "categorie": "grotte", "pos": [22, 12]}]
SITE_POS = {"x": 20, "y": 10}


def _perso(rang="C", charte="lieu:autre", **champs):
	"""Par défaut, une charte de la cité la plus proche de SITE_POS (`lieu:autre`)."""
	base = {"_id": "character:a", "prenom": "Greta", "nom": "Hazgard", "rangs_guilde": {"lieu:cite": rang}}
	if charte:
		base[col.CHAMP_CHARTE] = {"cite": charte, "label": charte}
	base.update(champs)
	return base


def _modele(palier="campement"):
	return copy.deepcopy(next(m for m in MODELES if palier in m["tags"]))


def _imp(reg=None, palier="campement", **champs):
	"""Implantation fondée, grille de son modèle posée comme le fait `db.config.get_doc`."""
	reg = reg or _reg()
	m = _modele("campement")
	imp = col.creer_implantation(_perso(), _pays(), SITE_POS, m, reg, espece="espece:loup", now=1000)
	if palier != "campement":
		m = _modele(palier)
		imp["palier"], imp["modele"] = palier, m["_id"]
	imp.update(champs)
	return db_config.suivre_modele(imp, {m["_id"]: m}.get)


ITEMS = {"item:Baies": {"_id": "item:Baies", "nom": "Baies", "categorie": "composant", "sous_categorie": "fleur"}}
MENACE_C = {"rang": "C"}      # pire rencontre possible au site (les loups) : un rang médian


def _site(reg, menace=MENACE_C):
	return col.fiche_site(_pays(), SITE_POS, ZONE_DEFS, RELIES, reg, items=ITEMS, menace=menace)


def _employe(imp, metier, poste, n=0):
	e = {"_id": f"employe:{metier}_{n}", "type": "employe", "metier": metier, "poste": poste,
		 "prenom": "Aldo", "nom": f"N{n}", "statut": "employe", "propriete": imp["_id"]}
	imp.setdefault("employes", []).append(e["_id"])
	return e


class Hasard:
	"""`rand` injecté : `random()` rend une valeur fixe, les tirages bornés leur minimum."""

	def __init__(self, valeur=0.99):
		self.valeur = valeur

	def random(self):
		return self.valeur

	def randint(self, a, b):
		return a

	def uniform(self, a, b):
		return a

	def choice(self, seq):
		return seq[0]

	def randrange(self, n):
		return 0


# ── Lien pur au modèle (§ 12.3) : le point unique de `db/config.py` ──────────────────

def test_la_grille_est_lue_sur_le_modele_et_jamais_ecrite():
	m = _modele()
	imp = {"_id": "implantation:x", "type": "implantation", "modele": m["_id"], "label": "X"}
	lu = db_config.suivre_modele(dict(imp), {m["_id"]: m}.get)
	assert all(lu[c] == m[c] for c in db_config.CHAMPS_MODELE)
	ecrit = db_config.sans_modele(lu)
	assert not set(db_config.CHAMPS_MODELE) & set(ecrit) and ecrit["modele"] == m["_id"]
	assert lu["cells"] is m["cells"] or lu["cells"] == m["cells"]      # l'exemplaire lu garde sa grille


def test_corriger_le_modele_corrige_l_implantation_et_un_lieu_ordinaire_n_est_pas_touche():
	m = _modele()
	imp = {"_id": "implantation:x", "modele": m["_id"], "cells": [[0]], "image": "vieille.png"}
	m["image"] = "neuve.png"
	assert db_config.suivre_modele(imp, {m["_id"]: m}.get)["image"] == "neuve.png"
	# modèle introuvable : aucune grille périmée ne survit
	assert "cells" not in db_config.suivre_modele({"_id": "implantation:y", "modele": "lieu:absent", "cells": [[1]]}, {}.get)
	lieu = {"_id": "lieu:ville", "modele": m["_id"], "cells": [[1]]}
	assert db_config.suivre_modele(lieu, {m["_id"]: m}.get)["cells"] == [[1]]
	assert db_config.sans_modele(lieu) is lieu


# ── Fonder (§ 2) ─────────────────────────────────────────────────────────────────────

def test_fonder_exige_le_rang_de_la_charte():
	reg = _reg()
	minimum = reg["reglages"]["rang_min"]
	dessous = RANGS[RANGS.index(minimum) - 1]
	assert col.peut_fonder(_perso(minimum), _pays(), SITE_POS, RELIES, [], reg) == (True, "")
	assert not col.peut_fonder(_perso(dessous), _pays(), SITE_POS, RELIES, [], reg)[0]
	assert not col.peut_fonder(_perso(rangs_guilde={}), _pays(), SITE_POS, RELIES, [], reg)[0]
	# le MEILLEUR rang compte, toutes cités confondues
	assert col.rang_suffisant({"rangs_guilde": {"a": RANGS[0], "b": RANGS[-1]}}, reg)


def test_fonder_respecte_les_distances_et_la_case():
	reg = _reg()
	d_imp = reg["reglages"]["distance_implantation_min"]
	cite = RELIES[0]["pos"]
	# Auteur, 15/11 : une case par défaut — seule la case de connexion est refusée, la voisine se fonde
	assert reg["reglages"]["distance_cite_min"] == 1
	assert "point de connexion" in col.peut_fonder(_perso(charte="lieu:cite"), _pays(), {"x": cite[0], "y": cite[1]}, RELIES, [], reg)[1]
	assert col.peut_fonder(_perso(charte="lieu:cite"), _pays(), {"x": cite[0] + 1, "y": cite[1] + 1}, RELIES, [], reg)[0]
	# un réglage relevé s'applique toujours, à toute ville
	reg["reglages"]["distance_cite_min"] = d_cite = 3
	assert "Cité-État" in col.peut_fonder(_perso(), _pays(), {"x": cite[0] + d_cite - 1, "y": cite[1]}, RELIES, [], reg)[1]
	assert col.peut_fonder(_perso(charte="lieu:cite"), _pays(), {"x": cite[0] + d_cite, "y": cite[1]}, RELIES, [], reg)[0]
	voisine = {"fondateur": "character:b", "origine": {"pos": [SITE_POS["x"] + d_imp - 1, SITE_POS["y"]]}}
	assert "autre implantation" in col.peut_fonder(_perso(), _pays(), SITE_POS, RELIES, [voisine], reg)[1]
	voisine["origine"]["pos"][0] += 1
	assert col.peut_fonder(_perso(), _pays(), SITE_POS, RELIES, [voisine], reg)[0]
	# une seule par pays et par personnage, où qu'elle soit
	mienne = {"fondateur": "character:a", "origine": {"pos": [0, 19]}}
	assert "déjà une implantation" in col.peut_fonder(_perso(), _pays(), SITE_POS, RELIES, [mienne], reg)[1]
	# case non marchable, point de connexion de tout genre (ici une grotte), hors d'un pays
	assert not col.peut_fonder(_perso(), _pays(), {"x": 0, "y": 0}, RELIES, [], reg)[0]
	assert "point de connexion" in col.peut_fonder(_perso(), _pays(), {"x": 22, "y": 12}, RELIES, [], reg)[1]
	assert not col.peut_fonder(_perso(), {**_pays(), "categorie": "ville"}, SITE_POS, RELIES, [], reg)[0]


def test_le_bouton_fonder_ne_s_offre_que_sur_une_case_fondable():
	"""`offre_fonder` (rendu de /play + réponse de chaque pas) = le jugement de `peut_fonder` :
	jamais sur un point de connexion, jamais sans charte ni hors d'un pays."""
	pays = _pays()
	docs = {col.REGLES_ID: copy.deepcopy(REGLES_DOC),
			**{r["id"]: {"_id": r["id"], "label": r["label"], "categorie": r["categorie"]} for r in RELIES}}
	connexions = [{"nodes": [{"lieu": pays["_id"], "pos": r["pos"]}, {"lieu": r["id"]}]} for r in RELIES]
	lus = []

	def find(q):
		lus.append(q)
		return []

	def offre(perso, lieu, pos):
		return col.offre_fonder(perso, lieu, pos, docs.get, find, lambda _id: connexions)

	assert offre(_perso(), pays, SITE_POS)
	for r in RELIES:                                      # cité, grotte : points de connexion
		assert not offre(_perso(charte=r["id"]), pays, {"x": r["pos"][0], "y": r["pos"][1]})
	assert not offre(_perso(charte="lieu:cite"), pays, SITE_POS)   # charte d'une cité trop lointaine
	lus.clear()
	assert not offre(_perso(charte=None), pays, SITE_POS)
	assert not offre(_perso(), {**pays, "categorie": "ville"}, SITE_POS)
	assert lus == []                                      # sans charte ou hors pays : aucune lecture


def test_la_charte_va_aux_cites_les_plus_proches_a_egalite_toutes():
	assert [c["id"] for c in col.cites_de_la_charte(RELIES, SITE_POS)] == ["lieu:autre"]
	egal = [{"id": "a", "label": "A", "categorie": "ville", "pos": [0, 0]},
			{"id": "b", "label": "B", "categorie": "ville", "pos": [10, 0]},
			{"id": "g", "label": "G", "categorie": "grotte", "pos": [5, 0]}]
	assert {c["id"] for c in col.cites_de_la_charte(egal, {"x": 5, "y": 0})} == {"a", "b"}


def test_creer_implantation_part_au_premier_palier_sans_grille_propre():
	reg = _reg()
	m = _modele()
	imp = col.creer_implantation(_perso(), _pays(), SITE_POS, m, reg, nom="  Val   <b>Clair</b>  ", espece="espece:loup", now=5)
	assert imp["_id"].startswith(db_config.PREFIXE_MODELE) and imp["type"] == col.TYPE_DOC
	assert imp["palier"] == col.paliers(reg)[0]["id"] and imp["modele"] == m["_id"]
	assert not set(db_config.CHAMPS_MODELE) & set(imp)          # lien PUR : rien de recopié
	assert imp["label"] == "Val <b>Clair</b>"                    # borné, pas échappé (le rendu échappe)
	assert imp["stocks"] == {s: reg["stocks_depart"][s] for s in reg["stocks"]}
	assert imp["menace"] == {"espece": "espece:loup", "etape": 1} and imp["rattrape_at"] == 5
	lien = col.creer_lien(imp, col.entrees_de(m)[0])
	assert lien["nodes"][0] == {"lieu": "lieu:pays", "pos": [20, 10]}
	assert lien["nodes"][1] == {"lieu": imp["_id"], "pos": col.entrees_de(m)[0]}


def test_la_charte_s_achete_au_bureau_et_ne_vaut_que_pres_de_sa_cite():
	reg = _reg()
	bureau = {"_id": "lieu:bureau", "categorie": col.CATEGORIE_BUREAU, "lieu_parent": "lieu:autre"}
	sans = _perso(charte=None)
	assert col.peut_acheter_charte(sans, bureau, reg) == (True, "")
	assert not col.peut_acheter_charte(sans, {**bureau, "categorie": "guilde_aventurier"}, reg)[0]
	dessous = RANGS[RANGS.index(reg["reglages"]["rang_min"]) - 1]
	assert "rang" in col.peut_acheter_charte(_perso(dessous, charte=None), bureau, reg)[1]
	assert "Autre" in col.peut_fonder(sans, _pays(), SITE_POS, RELIES, [], reg)[1]      # nomme où l'acheter
	charte = col.delivrer_charte(sans, {"_id": "lieu:autre", "label": "Autre"}, 40000, now=7)
	assert charte == {"cite": "lieu:autre", "label": "Autre", "prix": 40000, "at": 7}
	assert "déjà" in col.peut_acheter_charte(sans, bureau, reg)[1]                     # une à la fois
	assert col.peut_fonder(sans, _pays(), SITE_POS, RELIES, [], reg) == (True, "")
	# signée ailleurs : elle ne vaut pas ici
	ailleurs = _perso(charte="lieu:cite")
	assert "signée par le maître de guilde de Autre" in col.peut_fonder(ailleurs, _pays(), SITE_POS, RELIES, [], reg)[1]
	assert col.consommer_charte(sans) == charte and col.charte_de(sans) is None


# ── Fiche de site (§ 3) et tags (§ 12.2) ─────────────────────────────────────────────

def test_fiche_de_site_six_axes_lus_sur_la_carte():
	reg = _reg()
	fiche = _site(reg)
	assert set(fiche) == set(reg["axes_site"])
	assert all(0 <= b["note"] <= b["max"] and b["mots"] for b in fiche.values())
	assert fiche["eau"]["note"] >= 2 and "eau à portée" in fiche["eau"]["details"]   # rivière + case d'eau
	# rang C + (donjon proche, zone dangereuse) : UN seul cran de plus
	assert fiche["danger"]["note"] == reg["site"]["danger_par_rang"]["C"] + 1
	assert "un donjon proche" in fiche["danger"]["details"] and fiche["danger"]["max"] == col.danger_max(reg)
	# hors de toute zone, loin de l'eau : un site nu
	nu = col.fiche_site(_pays(), {"x": 2, "y": 17}, ZONE_DEFS, RELIES, reg, items=ITEMS, menace=None)
	assert nu["eau"]["note"] == 0 and nu["materiaux"]["note"] == 0 and nu["danger"]["note"] == 0


def test_danger_lu_sur_le_rang_de_la_pire_rencontre():
	reg = _reg()
	par_rang = reg["site"]["danger_par_rang"]
	# aucune rencontre possible : 0, même avec un donjon proche et une zone dangereuse
	assert _site(reg, menace=None)["danger"]["note"] == 0
	# l'échelle suit les rangs, un cran par rang (F → 1 … S+ → max)
	assert [par_rang[r] for r in RANGS] == list(range(1, len(RANGS) + 1))
	assert col.danger_max(reg) == len(RANGS)
	# S+ : au maximum, le bonus ne le dépasse pas
	assert _site(reg, menace={"rang": RANGS[-1]})["danger"]["note"] == col.danger_max(reg)
	# sans donjon ni zone dangereuse : le rang seul
	calme = {"zone:foret": {**ZONE_FORET, "modificateurs": {}}}
	f = col.fiche_site(_pays(), SITE_POS, calme, RELIES[:2], reg, items=ITEMS, menace={"rang": "D"})
	assert f["danger"]["note"] == par_rang["D"] and "rang D" in f["danger"]["details"][0]
	assert f["danger"]["mots"] == reg["site"]["mots_danger"][par_rang["D"]]


def test_danger_relatif_rend_l_echelle_des_formules():
	reg = _reg()
	site = lambda n: {"danger": {"note": n}}
	assert col.danger_relatif(site(0), reg) == 0
	assert col.danger_relatif(site(col.danger_max(reg)), reg) == 3      # l'ancien maximum des formules
	assert col.danger_relatif({}, reg) == 0


def _pays_ressources(*ids):
	p = _pays()
	p["ressources"] = [{"ressource": i, "zones": ["zone:foret"]} for i in ids] \
		+ [{"ressource": ids[0], "zones": ["zone:foret"]}]        # doublon : compté une fois
	return p


RESSOURCES = {
	"item:Chene": {"_id": "item:Chene", "nom": "Chêne", "categorie": "composant", "sous_categorie": "arbre",
				   "tags": ["bois", "a_couper", "essence_chene"]},
	"item:Bouleau": {"_id": "item:Bouleau", "nom": "Bouleau", "categorie": "composant", "sous_categorie": "arbre",
					 "tags": ["bois", "a_couper", "essence_bouleau"]},
	"item:fer": {"_id": "item:fer", "nom": "Fer", "categorie": "metal", "sous_categorie": "fer"},
	"item:Herbes": {"_id": "item:Herbes", "nom": "Herbes", "categorie": "composant", "sous_categorie": "herbe"},
	"item:Bibelot": {"_id": "item:Bibelot", "nom": "Bibelot", "categorie": "divers", "sous_categorie": "bibelot"},
}


def test_chaque_ressource_releve_l_axe_de_sa_nature():
	reg = _reg()
	nu = {"zone:foret": {"_id": "zone:foret", "terrain_tags": []}}      # aucun mot-clé : seules les ressources
	f = col.fiche_site(_pays_ressources("item:Chene", "item:fer", "item:Herbes", "item:Bibelot"),
					   SITE_POS, nu, [], reg, items=RESSOURCES, menace=None)
	assert f["materiaux"]["note"] == 2 and f["materiaux"]["ressources"] == ["item:Chene", "item:fer"]
	assert f["nourriture"]["note"] == 1 and f["nourriture"]["details"] == ["Herbes"]
	assert "ressources" not in f["eau"] and "Bibelot" not in str(f)            # nature inconnue : sans effet
	# plafond 3
	beaucoup = col.fiche_site(_pays_ressources("item:Chene", "item:Bouleau", "item:fer", "item:x"),
							  SITE_POS, nu, [], reg,
							  items={**RESSOURCES, "item:x": {"categorie": "metal"}}, menace=None)
	assert beaucoup["materiaux"]["note"] == 3


def test_tags_du_site_zone_puis_pays_puis_tag_de_pays():
	assert col.tags_site(_pays(), SITE_POS, ZONE_DEFS) == ["foret", "riviere", "colline", "tempere", "pays_pays"]
	assert col.tags_site(_pays(), {"x": 2, "y": 17}, ZONE_DEFS) == ["tempere", "pays_pays"]


# ── Lieux modèles (§ 12.1, § 12.2) ───────────────────────────────────────────────────

def _m(ident, *tags):
	return {"_id": ident, "tags": [col.TAG_MODELE, "campement", *tags]}


def test_modeles_meilleur_recouvrement_en_tete_generique_en_dernier():
	reg = _reg()
	modeles = [_m("lieu:gen"), _m("lieu:desert", "desert", "sable"), _m("lieu:foret", "foret", "riviere"),
			   _m("lieu:bois", "foret"), {"_id": "lieu:hameau", "tags": [col.TAG_MODELE, "hameau"]}]
	ordre = col.modeles_proposes(modeles, "campement", ["foret", "riviere"], "lieu:pays", reg)
	assert [p["modele"]["_id"] for p in ordre] == ["lieu:foret", "lieu:bois", "lieu:desert", "lieu:gen"]
	assert ordre[0]["partages"] == ["foret", "riviere"] and ordre[-1]["generique"]


def test_modeles_propres_au_pays_seuls_proposes_le_generique_en_plus():
	reg = _reg()
	modeles = [_m("lieu:gen"), _m("lieu:foret", "foret"), _m("lieu:ici", "pays_pays"), _m("lieu:ailleurs", "pays_autre")]
	ids = lambda pays: [p["modele"]["_id"] for p in col.modeles_proposes(modeles, "campement", ["foret"], pays, reg)]
	assert ids("lieu:pays") == ["lieu:ici", "lieu:gen"]
	# sans modèle propre : ceux des AUTRES pays ne se proposent pas
	assert ids("lieu:tiers") == ["lieu:foret", "lieu:gen"]


def test_le_generateur_livre_un_modele_generique_valide_par_palier():
	reg = _reg()
	for p in col.paliers(reg):
		[m] = [x for x in MODELES if p["id"] in x["tags"]]
		assert col.modele_generique(m, reg) and col.modele_valide(m)
		assert 1 <= len(col.entrees_de(m)) <= 4
	aires = [m["dimensions"]["x"] * m["dimensions"]["y"] for m in MODELES]
	assert aires == sorted(aires) and len(set(aires)) == len(aires)      # le lieu grandit à chaque palier


def test_normaliser_entrees_refuse_ce_qui_ecarterait_le_modele():
	# Grille 3×2 : seule la valeur 1 est marchable (`case_marchable`), comme `modele_valide`.
	m = {"cells": [[1, 0, 1], [3, 1, 5]], "dimensions": {"x": 3, "y": 2}}
	assert col.normaliser_entrees(m, [[0, 0], [1, 1]]) == ([[0, 0], [1, 1]], "")
	assert col.normaliser_entrees(m, []) == ([], "")
	for brut in ([[1, 0]], [[0, 1]], [[2, 1]], [[3, 0]], [[0, -1]],    # 0, 3, 5, hors grille
				 [[0, 0], [0, 0]], [[0, 0]] * 5, [["0", 0]], [[True, 0]], [[0]], None):
		entrees, erreur = col.normaliser_entrees(m, brut)
		assert entrees == [] and erreur, brut
	# ce qui passe la normalisation passe `modele_valide`
	m["entrees"] = col.normaliser_entrees(m, [[2, 0]])[0]
	assert col.modele_valide(m)


def test_icones_du_palier_generique_en_tete_un_format_par_nom():
	fichiers = ["hameau_icon.png", "hameau_icon.webp", "hameau_icon_europe02.png", "hameau_icon_feu.jpg",
				"hameau_europe01.jpg", "campement_icon_generique.webp", "hameau_icon.gif"]
	regions = {"europe": {"nom": "Europe"}}
	assert col.icones_du_palier("hameau", fichiers, regions) == [
		{"fichier": "hameau_icon.webp", "label": "Générique", "generique": True},   # webp avant png
		{"fichier": "hameau_icon_europe02.png", "label": "Europe 2", "generique": False},
		{"fichier": "hameau_icon_feu.jpg", "label": "Feu", "generique": False}]
	assert [c["fichier"] for c in col.icones_du_palier("campement", fichiers)] == ["campement_icon_generique.webp"]
	assert col.icones_du_palier("village", fichiers) == []


# ── Abandon et ruine (cahier des règles du monde, Auteur 26/11/2026) ──────────────────

def _abandonnee(reg, part, **champs):
	"""Implantation fondée à t=1000 (`vu_at`), relue après `part` du délai de ruine."""
	imp = _imp(reg, **champs)
	return imp, 1000 + int(reg["ruine"]["apres_s"] * part)


def test_le_delai_de_ruine_est_de_soixante_jours_et_delaissee_a_mi_chemin():
	reg = _reg()
	assert reg["ruine"]["apres_s"] == 60 * col.JOUR_S        # décision de l'Auteur
	imp, t = _abandonnee(reg, 0.25)
	assert col.etat_abandon(imp, reg, t) == ""
	imp, t = _abandonnee(reg, reg["ruine"]["delaissee_part"])
	assert col.etat_abandon(imp, reg, t) == col.ABANDON_DELAISSEE and not col.en_ruine(imp, reg, t)
	imp, t = _abandonnee(reg, 1)
	assert col.en_ruine(imp, reg, t)
	assert col.implantation_ouverte(imp, reg, t)[0] is False
	# sans date de présence (doc ancien sans `vu_at` ni `rattrape_at`) : jamais en ruine
	assert col.etat_abandon({"type": "implantation"}, reg, t) == ""
	# doc ancien sans `vu_at` : la dernière présence se relit dans `rattrape_at`
	ancien = {"type": "implantation", "rattrape_at": 1000}
	assert col.en_ruine(ancien, reg, t)


def test_fondateur_associe_et_soutien_tiennent_le_lieu_le_visiteur_non():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	for role in (col.FONDATEUR, col.ASSOCIE, col.SOUTIEN):
		imp, t = _abandonnee(reg, 0.9)
		assert col.marquer_presence(imp, role, reg, t) and imp["vu_at"] == t
		assert not col.marquer_presence(imp, role, reg, t + pas - 1)     # une écriture par passe au plus
		assert col.etat_abandon(imp, reg, t + 1) == ""
	imp, t = _abandonnee(reg, 0.9)
	assert not col.marquer_presence(imp, col.VISITEUR, reg, t) and imp["vu_at"] == 1000
	# une ruine ne se relève pas
	imp, t = _abandonnee(reg, 1)
	assert not col.marquer_presence(imp, col.FONDATEUR, reg, t) and col.en_ruine(imp, reg, t + 1)


def test_la_ruine_libere_le_site_pour_tous_et_pour_son_fondateur():
	reg = _reg()
	d_imp = reg["reglages"]["distance_implantation_min"]
	ruine, t = _abandonnee(reg, 1)
	ruine["origine"]["pos"] = [SITE_POS["x"] + d_imp - 1, SITE_POS["y"]]
	relies = RELIES + [{"id": ruine["_id"], "label": "Ruine", "categorie": col.TYPE_DOC, "pos": list(ruine["origine"]["pos"])}]
	vivante = copy.deepcopy(ruine)
	vivante["vu_at"] = t
	autre = _perso(_id="character:b")
	assert "autre implantation" in col.peut_fonder(autre, _pays(), SITE_POS, relies, [vivante], reg, now=t)[1]
	assert col.peut_fonder(autre, _pays(), SITE_POS, relies, [ruine], reg, now=t) == (True, "")
	# sa case n'est plus un point de connexion, et son fondateur peut refonder dans le pays
	case = {"x": ruine["origine"]["pos"][0], "y": ruine["origine"]["pos"][1]}
	assert "point de connexion" in col.peut_fonder(autre, _pays(), case, relies, [vivante], reg, now=t)[1]
	assert "point de connexion" not in col.peut_fonder(autre, _pays(), case, relies, [ruine], reg, now=t)[1]
	assert "déjà une implantation" in col.peut_fonder(_perso(), _pays(), SITE_POS, relies, [vivante], reg, now=t)[1]
	assert col.peut_fonder(_perso(), _pays(), SITE_POS, relies, [ruine], reg, now=t) == (True, "")
	# plus d'icône sur la carte du pays
	for imp in (ruine, vivante):
		imp["icone_carte"] = "campement_icon.webp"
	fichiers = ["campement_icon.webp"]
	assert col.icones_carte([ruine], reg, fichiers, now=t) == []
	assert len(col.icones_carte([vivante], reg, fichiers, now=t)) == 1


def test_le_visiteur_voit_le_lieu_delaisse():
	reg = _reg()
	imp, t = _abandonnee(reg, reg["ruine"]["delaissee_part"])
	assert col.vue(imp, reg, col.VISITEUR, _site(reg), [], now=t)["abandon"] is True
	assert col.vue(imp, reg, col.VISITEUR, _site(reg), [], now=1001)["abandon"] is False


def test_icone_facultative_avant_le_bourg_imposee_ensuite():
	reg = _reg()
	ids = [p["id"] for p in col.paliers(reg)]
	seuil = reg["icones"]["obligatoire_des"]
	avant, apres = ids[ids.index(seuil) - 1], seuil
	fichiers = [f"{avant}_icon.webp", f"{avant}_icon_feu.webp", f"{apres}_icon_generique.webp"]
	imp = {"palier": avant}
	assert not col.icone_obligatoire(imp, reg) and col.icone_affichee(imp, reg, fichiers) is None   # jamais choisie
	assert col.choisir_icone(imp, reg, fichiers, f"{avant}_icon_feu.webp") == (True, "")
	assert col.icone_affichee(imp, reg, fichiers) == f"{avant}_icon_feu.webp"
	assert col.choisir_icone(imp, reg, fichiers, f"{apres}_icon_generique.webp")[0] is False        # autre palier
	assert col.choisir_icone(imp, reg, fichiers, None) == (True, "") and imp["icone_carte"] == ""
	assert col.icone_affichee(imp, reg, fichiers) is None
	# Monté au palier imposé : le générique s'affiche, « aucune » est refusée
	imp["palier"] = apres
	assert col.icone_obligatoire(imp, reg) and col.icone_affichee(imp, reg, fichiers) == f"{apres}_icon_generique.webp"
	assert col.choisir_icone(imp, reg, fichiers, "")[0] is False
	# une icône voulue à un palier précédent : le générique du nouveau la remplace
	imp2 = {"palier": avant, "icone_carte": f"{avant}_icon_feu.webp"}
	imp2["palier"] = ids[0] if ids[0] != avant else ids[1]
	fichiers2 = fichiers + [f"{imp2['palier']}_icon.webp"]
	assert col.icone_affichee(imp2, reg, fichiers2) == f"{imp2['palier']}_icon.webp"
	# imposée mais aucune icône pour ce palier : rien
	assert col.icone_affichee({"palier": ids[-1]}, reg, fichiers) is None
	carte = col.icones_carte([{"palier": apres, "label": "Ici", "origine": {"pos": [4, 5]}},
							  {"palier": avant, "origine": {"pos": [1, 1]}}], reg, fichiers)
	assert carte == [{"x": 4, "y": 5, "fichier": f"{apres}_icon_generique.webp", "label": "Ici"}]


def test_le_generateur_n_ajoute_que_ce_qui_manque():
	dump = {d["_id"]: copy.deepcopy(d) for d in DOCS}
	assert gen.generer(dump) == []                                        # idempotent
	# un bloc retouché par l'Auteur n'est jamais réécrit ; un bloc absent revient seul
	dump[col.REGLES_ID]["value"]["stockage_base"] = 999
	del dump[col.REGLES_ID]["value"]["sante"]
	dump[col.REGLES_ID]["_rev"] = "3-x"
	[doc] = gen.generer(dump)
	assert doc["value"]["stockage_base"] == 999 and doc["value"]["sante"] == col.DEFAUTS["sante"]
	assert "_rev" not in doc
	gen.controler(DOCS, {})


# ── Bâtiments (§ 8, § 12.4) ──────────────────────────────────────────────────────────

def _construit(imp, reg, type_id, pos=None):
	imp["stocks"].update({"bois": 500, "materiaux": 500})
	b = col.construire(imp, reg, type_id, now=1)
	if pos:
		col.poser(imp, b["id"], pos)
	return b


def test_construire_paie_les_stocks_et_respecte_le_palier():
	reg = _reg()
	imp = _imp(reg)
	entrepot = col.batiment_def(reg, "entrepot")
	imp["stocks"].update({"bois": entrepot["bois"], "materiaux": entrepot["materiaux"] - 1})
	assert "manque" in col.peut_construire(imp, reg, "entrepot")[1]
	imp["stocks"]["materiaux"] = entrepot["materiaux"]
	assert col.peut_construire(imp, reg, "entrepot") == (True, "")
	b = col.construire(imp, reg, "entrepot", now=1)
	assert imp["stocks"]["bois"] == 0 and imp["stocks"]["materiaux"] == 0 and b["pos"] is None
	imp["stocks"].update({"bois": 500, "materiaux": 500})
	assert "palier" in col.peut_construire(imp, reg, "ferme")[1]          # la ferme s'ouvre au Hameau
	assert col.peut_construire(_imp(reg, "hameau", stocks={"bois": 500, "materiaux": 500}), reg, "ferme")[0]
	# un sous-lieu (où l'on entre) se construit dès son palier
	ville = _imp(reg, "ville", stocks={"bois": 9999, "materiaux": 9999})
	assert all(col.peut_construire(ville, reg, d["id"])[0] for d in reg["batiments_def"]
			   if d["nature"] == col.SOUS_LIEU and d.get("catalogue", True))
	assert not col.peut_construire(ville, reg, "maison_guilde")[0]          # elle naît avec la guilde


def test_pose_libre_hors_entrees_un_batiment_par_case():
	reg = _reg()
	imp = _imp(reg)
	a, b = _construit(imp, reg, "habitation"), _construit(imp, reg, "entrepot")
	entree = col.entrees_de(imp)[0]
	assert "entrée" in col.peut_poser(imp, a["id"], entree)[1]
	assert not col.peut_poser(imp, a["id"], {"x": -1, "y": 0})[0]
	assert col.peut_poser(imp, a["id"], {"x": 3, "y": 3}) == (True, "")
	col.poser(imp, a["id"], {"x": 3, "y": 3})
	assert "prise" in col.peut_poser(imp, b["id"], [3, 3])[1]
	assert col.peut_poser(imp, a["id"], [3, 3])[0]                         # se reposer sur sa propre case
	col.poser(imp, a["id"], [4, 4])                                        # déplacer : même geste
	assert col.batiment(imp, a["id"])["pos"] == [4, 4]
	assert col.peut_agir_sur_carte(col.FONDATEUR) and col.peut_agir_sur_carte(col.ASSOCIE)
	assert not col.peut_agir_sur_carte(col.SOUTIEN) and not col.peut_agir_sur_carte(col.VISITEUR)


def test_reperes_sur_la_carte_halo_d_une_famille_a_part():
	reg = _reg()
	imp = _imp(reg)
	a = _construit(imp, reg, "habitation", [3, 3])
	_construit(imp, reg, "entrepot")                                       # non posé : pas de marqueur
	[m] = col.reperes_carte(imp, reg)
	assert (m["x"], m["y"], m["icone"], m["batiment"]) == (3, 3, col.batiment_def(reg, "habitation")["icone"], a["id"])
	assert m["link_id"] is None and m["metier"] is None                    # on n'y entre pas
	assert col.RGB_REPERE not in enseignes_icones.FAMILLES.values()        # une couleur qu'aucun métier ne porte


def test_changer_de_palier_replace_chaque_batiment_au_plus_pres():
	reg = _reg()
	imp = _imp(reg)
	anciennes = dict(imp["dimensions"])
	coin = [anciennes["x"] - 1, anciennes["y"] - 1]
	a = _construit(imp, reg, "habitation", coin)
	b = _construit(imp, reg, "entrepot", [0, 0])
	c = _construit(imp, reg, "poste_de_garde")
	nouveau = _modele("hameau")
	nw, nh = nouveau["dimensions"]["x"], nouveau["dimensions"]["y"]
	col.replacer_batiments(imp, anciennes, nouveau)
	assert col.batiment(imp, a["id"])["pos"] == [nw - 1, nh - 1]           # même position relative
	assert col.batiment(imp, b["id"])["pos"] == [0, 0] and col.batiment(imp, c["id"])["pos"] is None
	# la case visée est une entrée ou un mur : la case libre la plus proche
	e = col.entrees_de(nouveau)[0]
	assert col.case_libre_proche(nouveau, e, set()) != e
	assert col.case_libre_proche(nouveau, [5, 5], {(5, 5)}) == [4, 4]


# ── Paliers et chantiers (§ 4, § 10 « Financer ») ────────────────────────────────────

def _pret_pour_hameau(reg):
	imp = _imp(reg)
	suivant = col.palier_suivant(reg, imp["palier"])
	imp["population"] = suivant["population_min"]
	imp["fortifications"] = [col.fortification_requise(reg, suivant["id"])["id"]]
	employes = [_employe(imp, "garde", "b_x", n) for n in range(suivant["postes_min"])]
	return imp, employes, suivant


def test_le_palier_suivant_exige_population_postes_et_fortification():
	reg = _reg()
	imp, employes, suivant = _pret_pour_hameau(reg)
	c = col.conditions_palier(imp, reg, employes)
	assert c["pret"] and c["prix"] == suivant["prix_statut_cuivre"] and len(c["conditions"]) == 3
	for casse in ({"population": suivant["population_min"] - 1}, {"fortifications": []}):
		assert not col.conditions_palier({**imp, **casse}, reg, employes)["pret"]
	assert not col.conditions_palier(imp, reg, employes[:-1])["pret"]
	assert col.conditions_palier(_imp(reg, col.paliers(reg)[-1]["id"]), reg, []) is None


def test_chantier_de_statut_finance_a_plusieurs_puis_changement_de_palier():
	reg = _reg()
	imp, employes, suivant = _pret_pour_hameau(reg)
	a = _construit(imp, reg, "habitation", [2, 2])
	ok, _, chantier = col.peut_ouvrir_chantier(imp, reg, employes, col.CHANTIER_STATUT)
	assert ok and chantier["cout"] == suivant["prix_statut_cuivre"]
	col.ouvrir_chantier(imp, reg, chantier, now=1)
	assert not col.peut_ouvrir_chantier(imp, reg, employes, col.CHANTIER_STATUT)[0]      # un seul à la fois
	associe = {"_id": "character:b", "prenom": "Milo", "nom": ""}
	imp["associes"] = [{"id": "character:b", "nom": "Milo", "apports": {}}]
	moitie = chantier["cout"] // 2
	assert col.financer(imp, associe, moitie, now=2) == moitie
	assert imp["associes"][0]["apports"] == {"cuivre": moitie}                           # compté, sans part de caisse
	assert not col.changer_palier(imp, reg, _modele("hameau"), imp["dimensions"], now=3)  # pas encore payé
	assert col.financer(imp, _perso(), 10 ** 9, now=4) == chantier["cout"] - moitie      # jamais plus que le reste
	assert col.chantier_pret(imp) and not col.achever_fortification(imp)
	nouveau = _modele("hameau")
	assert col.changer_palier(imp, reg, nouveau, imp["dimensions"], now=5)
	assert imp["palier"] == suivant["id"] and imp["modele"] == nouveau["_id"] and "chantier" not in imp
	assert col.batiment(imp, a["id"])["pos"] is not None
	assert col.places_associes(imp, reg) == reg["autres_joueurs"]["associes_max"][suivant["id"]]


def test_chantier_de_fortification_les_stocks_partent_a_l_ouverture():
	reg = _reg()
	imp = _imp(reg)
	f = col.fortification_requise(reg, "hameau")
	assert "manque" in col.peut_ouvrir_chantier(imp, reg, [], col.CHANTIER_FORTIFICATION, f["id"])[1]
	imp["stocks"].update({"bois": f["bois"] + 1, "materiaux": f["materiaux"]})
	ok, _, chantier = col.peut_ouvrir_chantier(imp, reg, [], col.CHANTIER_FORTIFICATION, f["id"])
	assert ok
	col.ouvrir_chantier(imp, reg, chantier, now=1)
	assert imp["stocks"]["bois"] == 1 and imp["stocks"]["materiaux"] == 0
	col.financer(imp, _perso(), f["prix_cuivre"], now=2)
	assert col.achever_fortification(imp, now=3) and imp["fortifications"] == [f["id"]]
	assert "déjà" in col.peut_ouvrir_chantier(imp, reg, [], col.CHANTIER_FORTIFICATION, f["id"])[1]
	# une défense d'un palier plus haut n'est pas à portée
	loin = next(x for x in reg["fortifications"] if x["palier_min"] == "petite_ville")
	imp["stocks"].update({"bois": 99999, "materiaux": 99999})
	assert not col.peut_ouvrir_chantier(imp, reg, [], col.CHANTIER_FORTIFICATION, loin["id"])[0]


def test_chaque_palier_a_sa_fortification_minimale_ou_la_repete():
	reg = _reg()
	requises = [col.fortification_requise(reg, p["id"]) for p in col.paliers(reg)[1:]]
	# seule la Petite ville répète celle du Bourg (« murailles » aux deux lignes du tableau)
	assert [bool(f) for f in requises] == [p["id"] != "petite_ville" for p in col.paliers(reg)[1:]]


# ── Personnel nommé (§ 8) ────────────────────────────────────────────────────────────

# Métiers de `rules:proprietes` que les bâtiments de la colonisation emploient (le dump les porte).
CAT_PROP = {"metiers": [{"id": m, "label": m.capitalize(), "cout_embauche_cuivre": 500}
						for m in ("garde", "medecin", "intendant", "palefrenier", "artisan", "marchand",
								  "commis", "charretier", "teneur_livres", "crieur")]}


def test_metiers_ceux_des_proprietes_plus_ceux_de_la_colonisation():
	reg = _reg()
	ids = [m["id"] for m in col.metiers(reg, CAT_PROP)]
	assert len(ids) == len(set(ids)) and {"garde", "medecin", "agriculteur", "bucheron"} <= set(ids)
	# tout poste d'un bâtiment constructible a son métier
	manquants = {m for d in reg["batiments_def"] if d["nature"] in col.NATURES_OUVERTES
				 for m in d.get("postes") or {}} - set(ids)
	assert not manquants


def test_un_candidat_par_poste_libre_et_l_embauche_cree_le_pnj_nomme():
	reg = _reg()
	imp = _imp(reg)
	b = _construit(imp, reg, "poste_de_garde", [2, 2])
	places = sum(col.batiment_def(reg, "poste_de_garde")["postes"].values())
	rand = random.Random(1)
	assert col.rafraichir_candidats(imp, reg, CAT_PROP, [], {}.get, ["p.jpg"], now=10, rand=rand)
	assert len(imp["candidats"]) == len(col.batiment_def(reg, "poste_de_garde")["postes"])
	assert not col.rafraichir_candidats(imp, reg, CAT_PROP, [], {}.get, ["p.jpg"], now=11, rand=rand)   # encore valide
	candidat = next(c for c in imp["candidats"] if c["metier"] == "garde")
	assert col.peut_engager(imp, reg, [], candidat) == (True, "")
	employe = col.engager(imp, candidat, _perso(), now=12)
	assert employe["propriete"] == imp["_id"] and employe["poste"] == b["id"] and employe["_id"] in imp["employes"]
	assert candidat not in imp["candidats"]
	libres = sum(p["libres"] for p in col.postes_libres(imp, reg, [employe]))
	assert libres == places - 1
	col.renvoyer(imp, employe, now=13)
	assert imp["employes"] == [] and employe["statut"] == "renvoye"


def test_un_batiment_endommage_arrete_ses_pnj_jusqu_a_reparation():
	reg = _reg()
	imp = _imp(reg)
	b = _construit(imp, reg, "poste_de_garde", [2, 2])
	garde = _employe(imp, "garde", b["id"])
	assert col.au_poste(imp, reg, [garde]) == [garde]
	b["endommage"] = True
	assert col.au_poste(imp, reg, [garde]) == [] and col.postes(imp, reg) == []
	imp["stocks"]["materiaux"] = reg["reparation_materiaux"] - 1
	assert not col.reparer(imp, reg, b["id"], now=1)[0]
	imp["stocks"]["materiaux"] = reg["reparation_materiaux"]
	assert col.reparer(imp, reg, b["id"], now=1) == (True, "") and imp["stocks"]["materiaux"] == 0
	assert col.au_poste(imp, reg, [garde]) == [garde]


# ── Stocks, dons, besoins (§ 7, § 10) ────────────────────────────────────────────────

def test_un_objet_donne_rejoint_le_stock_que_sa_regle_reconnait():
	reg = _reg()
	pain = {"nom": "Pain", "sous_categorie": "boulangerie", "poids": 2}
	assert col.stock_de_item(pain, [], reg)["stock"] == "nourriture"
	assert col.stock_de_item({"sous_categorie": "herbe"}, [], reg)["stock"] == "medicaments"
	assert col.stock_de_item({}, ["matiere.bois"], reg)["stock"] == "bois"
	assert col.stock_de_item({}, ["matiere.metal"], reg)["stock"] == "materiaux"
	assert col.stock_de_item({"sous_categorie": "grimoire"}, ["magie.grimoire"], reg) is None
	# Pierres de construction (marbre, granit, argile…) : sous-catégorie « pierre » ; les cordes
	# d'instrument ne bâtissent rien (Auteur, 16/11).
	assert col.stock_de_item({"sous_categorie": "pierre"}, ["matiere.autre"], reg)["stock"] == "materiaux"
	assert col.stock_de_item({"sous_categorie": "corde"}, ["matiere.autre"], reg) is None
	# Objets ouvrés (cordes, poix, toiles…) : par le tag, catégorie inchangée.
	corde = {"categorie": "outil", "sous_categorie": "", "tags": ["materiau_construction"], "poids": 1.0}
	assert col.stock_de_item(corde, [], reg)["stock"] == "materiaux"
	assert col.stock_de_item({"categorie": "outil", "tags": None}, [], reg) is None
	regle = col.stock_de_item(pain, [], reg)
	assert col.unites_de_item(pain, regle) == 2 * regle["unites_par_kg"]
	assert col.unites_de_item({"poids": [1, 3]}, regle) == 2 * regle["unites_par_kg"]      # poids en fourchette
	assert {r["stock"] for r in reg["depots"]} == set(reg["stocks"])                       # les quatre stocks s'alimentent


def test_le_don_est_borne_par_la_reserve_note_au_carnet_et_fait_un_soutien():
	reg = _reg()
	imp = _imp(reg)
	capacite = col.stockage(imp, reg)
	visiteur = {"_id": "character:v", "prenom": "Milo", "nom": ""}
	assert col.role_de(visiteur, imp) == col.VISITEUR
	imp["stocks"]["bois"] = capacite - 3
	assert col.deposer(imp, reg, visiteur, "bois", 5, "Rondin", now=1) == 3            # la réserve est pleine au-delà
	assert imp["stocks"]["bois"] == capacite
	assert col.role_de(visiteur, imp) == col.SOUTIEN and imp["soutiens"]["character:v"]["dons"] == {"bois": 3}
	assert "Milo donne Rondin" in imp["journal"][-1]["texte"]
	# le fondateur verse sans se compter ni s'écrire à lui-même
	n = len(imp["journal"])
	col.deposer(imp, reg, _perso(), "nourriture", 1, now=2)
	assert len(imp["journal"]) == n and "character:a" not in imp["soutiens"]
	# l'associé : ses dépôts sont des APPORTS
	imp["associes"] = [{"id": "character:b", "nom": "Bo", "apports": {}}]
	col.deposer(imp, reg, {"_id": "character:b", "prenom": "Bo", "nom": ""}, "nourriture", 2, now=3)
	assert imp["associes"][0]["apports"] == {"nourriture": 2} and "character:b" not in imp["soutiens"]


def test_l_entrepot_agrandit_les_reserves_et_davantage_a_chaque_palier():
	reg = _reg()
	imp = _imp(reg)
	base = col.stockage(imp, reg)
	assert base == reg["stockage_base"]
	_construit(imp, reg, "entrepot")
	gain = col.stockage(imp, reg) - base
	assert gain == col.batiment_def(reg, "entrepot")["stockage"]
	imp["palier"] = "hameau"
	assert col.stockage(imp, reg) - base == 2 * gain


def test_le_tableau_des_besoins_est_derive_des_stocks_bas():
	reg = _reg()
	imp = _imp(reg, stocks={"nourriture": 0, "bois": 999, "materiaux": 999, "medicaments": 999})
	assert [b["stock"] for b in col.besoins(imp, reg, [])] == ["nourriture"]
	imp["stocks"]["nourriture"] = 999
	assert col.besoins(imp, reg, []) == []
	# plus de bouches, plus de besoin
	seuil = col.seuils_stocks(imp, reg, [])["nourriture"]
	imp["population"] = 10
	assert col.seuils_stocks(imp, reg, [])["nourriture"] > seuil


# ── Sécurité et moral (§ 5) ──────────────────────────────────────────────────────────

def test_la_securite_a_cinq_familles_et_n_atteint_jamais_le_maximum():
	reg = _reg()
	imp = _imp(reg, stocks={s: 9999 for s in reg["stocks"]})
	imp["fortifications"] = [f["id"] for f in reg["fortifications"]]
	imp["menace"] = {"espece": None, "etape": 0}
	b = _construit(imp, reg, "poste_de_garde")
	site = {a: {"note": 3 if a == "defense" else 0} for a in reg["axes_site"]}
	s = col.securite(imp, reg, site, [_employe(imp, "garde", b["id"], n) for n in range(5)])
	assert [f["id"] for f in s["facteurs"]] == reg["facteurs_securite"]
	assert all(f["valeur"] == f["max"] for f in s["facteurs"])                # tout est au plus haut…
	assert s["valeur"] == reg["securite"]["plafond"] < 100                    # …et pourtant jamais le maximum
	assert s["mot"] == reg["securite"]["mots"][-1][1]


def test_gardes_fortifications_et_feu_relevent_la_securite():
	reg = _reg()
	imp = _imp(reg)
	site = _site(reg)
	nue = col.securite(imp, reg, site, [])["valeur"]
	b = _construit(imp, reg, "poste_de_garde")
	garde = _employe(imp, "garde", b["id"])
	gardee = col.securite(imp, reg, site, [garde])["valeur"]
	assert gardee > col.securite(imp, reg, site, [])["valeur"]
	imp["fortifications"] = ["palissade"]
	fortifiee = col.securite(imp, reg, site, [garde])["valeur"]
	assert fortifiee > gardee
	imp["feu"] = "reduit"
	assert col.securite(imp, reg, site, [garde])["valeur"] < fortifiee
	assert nue < fortifiee
	# la tanière localisée : le territoire est connu
	imp["menace"]["etape"] = 4
	connue = next(f for f in col.securite(imp, reg, site, [garde])["facteurs"] if f["id"] == "connaissance_territoire")
	assert connue["valeur"] == connue["max"]


def test_le_moral_suit_nourriture_morts_attaques_et_feu():
	reg = _reg()
	imp = _imp(reg, stocks={s: 9999 for s in reg["stocks"]})
	site = _site(reg)
	now = 100 * col.JOUR_S
	m = lambda: col.moral(imp, reg, site, [], now)["valeur"]
	serein = m()
	imp["stocks"]["nourriture"] = 0
	assert m() < serein
	imp["stocks"]["nourriture"] = 9999
	imp["morts"] = [now - 10]
	endeuille = m()
	assert endeuille < serein
	imp["morts"] = [now - reg["moral"]["fenetre_s"] - 10]                     # hors de la fenêtre : oublié
	assert m() == serein
	imp["attaques"] = [{"at": now - 10, "repoussee": False}]
	assert m() < serein
	imp["attaques"] = [{"at": now - 10, "repoussee": True}]                   # repoussée : le moral tient
	assert m() == serein
	imp["feu"] = "reduit"
	assert m() < serein
	assert col.moral(imp, reg, site, [], now)["mot"]


# ── Le temps : rattrapage paresseux (§ 1, § 6, § 7) ──────────────────────────────────

def test_le_rattrapage_est_plafonne_et_garde_le_reliquat():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	plafond = reg["reglages"]["rattrapage_max_s"]
	imp = _imp(reg, rattrape_at=1000)
	assert col.passes_dues(imp, reg, 1000 + pas - 1) == 0
	assert col.passes_dues(imp, reg, 1000 + 2 * pas + 5) == 2
	assert col.passes_dues(imp, reg, 1000 + 100 * plafond) == plafond // pas
	site = _site(reg)
	bilan = col.rattraper(imp, reg, site, [], now=1000 + 2 * pas + 5, rand=Hasard())
	assert bilan["passes"] == 2 and imp["rattrape_at"] == 1000 + 2 * pas       # 5 s restent dues
	assert col.rattraper(imp, reg, site, [], now=1000 + 2 * pas + 6, rand=Hasard())["passes"] == 0
	# absence longue : seules les dernières passes sont rejouées, l'horloge repart de maintenant
	loin = 1000 + 50 * plafond
	assert col.rattraper(imp, reg, site, [], now=loin, rand=Hasard())["passes"] == plafond // pas
	assert imp["rattrape_at"] == loin


def test_une_passe_produit_et_consomme_selon_le_site():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	site = _site(reg)
	imp = _imp(reg, stocks={"nourriture": 50.0, "bois": 50.0, "materiaux": 0.0, "medicaments": 0.0}, rattrape_at=0)
	imp["stocks"].update({"bois": 500, "materiaux": 500})
	b = col.construire(imp, reg, "entrepot", now=0)
	imp["stocks"] = {"nourriture": 50.0, "bois": 50.0, "materiaux": 0.0, "medicaments": 0.0}
	bucheron = _employe(imp, "bucheron", b["id"])
	jour = col.JOUR_S // pas
	col.rattraper(imp, reg, site, [bucheron], now=jour * pas, rand=Hasard())
	c = reg["consommation"]
	produit = next(m for m in reg["metiers_def"] if m["id"] == "bucheron")["produit"]
	attendu_bois = 50 + produit["par_jour"] * col.facteur_axe(site, produit["axe"], reg) - c["bois_feu_jour"]["grand"]
	assert abs(imp["stocks"]["bois"] - attendu_bois) < 0.05
	attendu_nourriture = 50 - 2 * c["nourriture_par_habitant_jour"]            # le bûcheron et le fondateur
	assert abs(imp["stocks"]["nourriture"] - attendu_nourriture) < 0.05
	assert imp["stocks"]["materiaux"] == 0


def test_le_bilan_par_jour_est_celui_qu_une_journee_de_passes_produit():
	"""`bilan_jour` (jauges des réserves) et la passe lisent les mêmes formules : sans plafond ni
	plancher atteint, une journée de passes déplace chaque stock de son solde."""
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	site = _site(reg)
	imp = _imp(reg, rattrape_at=0)
	imp["stocks"].update({"bois": 500, "materiaux": 500})
	b = col.construire(imp, reg, "entrepot", now=0)
	imp["stocks"] = {"nourriture": 50.0, "bois": 50.0, "materiaux": 0.0, "medicaments": 0.0}
	bucheron = _employe(imp, "bucheron", b["id"])
	solde = col.bilan_jour(imp, reg, site, [bucheron])
	assert set(solde) == set(reg["stocks"])
	avant = dict(imp["stocks"])
	col.rattraper(imp, reg, site, [bucheron], now=(col.JOUR_S // pas) * pas, rand=Hasard())
	for s in ("nourriture", "bois"):
		assert abs(imp["stocks"][s] - (avant[s] + solde[s])) < 0.05, s
	assert solde["nourriture"] < 0
	assert col.autonomie_jours(10, -4) == 2.5
	assert col.autonomie_jours(10, 0) is None and col.autonomie_jours(10, 1) is None
	assert col.autonomie_jours(-1, -4) == 0.0
	# la vue des gérants porte le solde et l'autonomie de chaque stock ; le visiteur, rien
	v = col.vue(imp, reg, col.FONDATEUR, site, [bucheron])
	nourr = next(x for x in v["stocks"] if x["stock"] == "nourriture")
	assert nourr["par_jour"] == round(solde["nourriture"], 1)
	assert nourr["jours"] == col.autonomie_jours(imp["stocks"]["nourriture"], solde["nourriture"])
	assert "stocks" not in col.vue(imp, reg, col.VISITEUR, site, [bucheron])
	# l'approvisionnement montre la production des métiers (même formule que le solde)
	metiers = col.production_metiers_jour(imp, reg, site, [bucheron])
	assert metiers.get("bois", 0) > 0
	assert v["approvisionnement"]["metiers"] == {s: round(x, 1) for s, x in metiers.items()}


def test_sans_place_sur_la_grille_retouchee_le_batiment_redevient_a_poser():
	reg = _reg()
	imp = _imp(reg, batiments=[{"id": "b1", "type": "habitation", "pos": [2, 2]}])
	imp["cells"] = [[0] * len(imp["cells"][0]) for _ in imp["cells"]]   # plus une case marchable
	imp_change, lien_change, portes = col.suivre_entrees(imp, reg, None, {})
	assert imp_change and not lien_change and portes == []
	assert col.batiment(imp, "b1")["pos"] is None
	assert imp["journal"][-1]["genre"] == "batiment" and "à reposer" in imp["journal"][-1]["texte"]
	# un lieu sans grille lue (modèle introuvable) ne déplace rien
	sans = _imp(reg, batiments=[{"id": "b1", "type": "habitation", "pos": [2, 2]}])
	sans.pop("cells")
	assert col.suivre_entrees(sans, reg, None, {})[0] is False


def test_chaque_ligne_du_carnet_porte_un_genre_connu():
	reg = _reg()
	imp = _imp(reg)
	col.regler_feu(imp, reg, "reduit")
	col.noter(imp, "sans genre")
	assert imp["journal"][-2]["genre"] == "feu" and "genre" not in imp["journal"][-1]
	# chaque genre posé par le moteur est l'un de ceux que le carnet sait filtrer
	import re
	source = open(col.__file__, encoding="utf-8").read()
	assert set(re.findall(r'genre="([a-z_]+)"', source)) <= set(col.GENRES_JOURNAL)
	for _ in range(col.JOURNAL_MAX + 5):
		col.noter(imp, "x", genre="don")
	assert len(imp["journal"]) == col.JOURNAL_MAX


def test_sans_bois_le_grand_feu_tombe_et_un_pecheur_sans_eau_ne_peche_rien():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	site = _site(reg)
	imp = _imp(reg, stocks={"nourriture": 0.0, "bois": 0.0, "materiaux": 0.0, "medicaments": 0.0}, rattrape_at=0)
	b = {"id": "b_ferme", "type": "ferme", "pos": None}
	imp["batiments"] = [b]
	pecheur = _employe(imp, "pecheur", "b_ferme")
	sec = {**site, "eau": {"note": 0}}
	bilan = col.rattraper(imp, reg, sec, [pecheur], now=pas, rand=Hasard())
	assert imp["feu"] == "reduit" and any("feu" in e for e in bilan["evenements"])
	assert imp["stocks"]["nourriture"] == 0
	col.rattraper(imp, reg, site, [pecheur], now=2 * pas, rand=Hasard())
	assert imp["stocks"]["nourriture"] > 0 or site["eau"]["note"] == 0


def test_la_population_arrive_d_elle_meme_si_le_lieu_est_sur_et_loge():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	imp = _imp(reg, stocks={s: 9999 for s in reg["stocks"]}, rattrape_at=0)
	imp["fortifications"] = [f["id"] for f in reg["fortifications"]]
	imp["menace"] = {"espece": None, "etape": 0}
	site = {a: {"note": 3 if a == "defense" else 0} for a in reg["axes_site"]}
	libres = col.logements(imp, reg)
	col.rattraper(imp, reg, site, [], now=20 * pas, rand=Hasard(0.0001))      # tous les tirages réussissent
	assert imp["population"] == libres                                          # jamais plus que de logements
	# un moral à terre fait partir : la famine, sans feu ni réserve
	imp["stocks"] = {s: 0.0 for s in reg["stocks"]}
	imp["fortifications"], imp["morts"] = [], [20 * pas] * 5
	avant = imp["population"]
	bilan = col.rattraper(imp, reg, {a: {"note": col.danger_max(reg) if a == "danger" else 0} for a in reg["axes_site"]}, [],
						  now=30 * pas, rand=Hasard(0.0001))
	assert imp["population"] < avant and any("quitté" in e for e in bilan["evenements"])


def test_la_menace_avance_par_etapes_jusqu_a_la_taniere_localisee():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	imp = _imp(reg, stocks={s: 9999 for s in reg["stocks"]}, rattrape_at=0)
	site = _site(reg)
	assert imp["menace"]["etape"] == 1
	textes = []
	for i in range(1, 4):
		textes += col.rattraper(imp, reg, site, [], now=i * pas, rand=Hasard(0.0))["evenements"]
		assert imp["menace"]["etape"] == i + 1
	assert len(reg["etapes_menace"]) == imp["menace"]["etape"] == 4
	assert any("remarqué" in t for t in textes) and any("tanière" in t for t in textes)
	# sans espèce, aucune menace ne naît
	calme = _imp(reg, rattrape_at=0, menace={"espece": None, "etape": 0})
	col.rattraper(calme, reg, site, [], now=50 * pas, rand=Hasard(0.0))
	assert calme["menace"]["etape"] == 0 and calme["attaques"] == []


def test_une_attaque_en_l_absence_coute_mais_jamais_le_lieu():
	reg = _reg()
	imp = _imp(reg, stocks={"nourriture": 100.0, "bois": 100.0, "materiaux": 0.0, "medicaments": 0.0}, population=3)
	b = {"id": "b_g", "type": "poste_de_garde", "pos": [1, 1]}
	imp["batiments"] = [b]
	nomme = _employe(imp, "garde", "b_g")
	employes = [nomme]
	bilan = {"evenements": [], "employes_touches": []}
	col._attaque(imp, reg, employes, 500, Hasard(0.0), bilan, {"valeur": 0})    # la sécurité ne retient rien
	assert imp["attaques"] == [{"at": 500, "repoussee": False}]
	assert imp["souffrants"] >= 1 and imp["stocks"]["nourriture"] < 100 and b.get("endommage")
	assert any("attaqué" in e for e in bilan["evenements"])
	assert imp["_id"] and imp["palier"] == "campement"                          # jamais la perte du lieu
	# repoussée : aucune perte de réserve
	imp2 = _imp(reg, stocks={"nourriture": 100.0, "bois": 100.0, "materiaux": 0.0, "medicaments": 0.0})
	col._attaque(imp2, reg, [], 500, Hasard(0.5), {"evenements": [], "employes_touches": []}, {"valeur": 90})
	assert imp2["attaques"][0]["repoussee"] and imp2["stocks"]["nourriture"] == 100


def test_la_mort_d_un_pnj_nomme_est_definitive_et_les_comptes_partent_d_abord():
	reg = _reg()
	imp = _imp(reg, population=1)
	nomme = _employe(imp, "garde", "b_x")
	employes = [nomme]
	bilan = {"evenements": [], "employes_touches": []}
	col._mort(imp, employes, Hasard(), 10, bilan, "de maladie")
	assert imp["population"] == 0 and employes == [nomme] and bilan["employes_touches"] == []
	col._mort(imp, employes, Hasard(), 11, bilan, "de maladie")
	assert employes == [] and imp["employes"] == [] and nomme["statut"] == col.EMPLOYE_MORT
	assert bilan["employes_touches"] == [nomme] and "Aldo" in bilan["evenements"][-1]
	assert imp["morts"] == [10, 11]


# ── Les autres joueurs (§ 10) ────────────────────────────────────────────────────────

def test_association_demande_ecrite_acceptee_places_par_palier():
	reg = _reg()
	imp = _imp(reg)
	places = col.places_associes(imp, reg)
	assert places == reg["autres_joueurs"]["associes_max"]["campement"] == 1
	b = {"_id": "character:b", "prenom": "Bo", "nom": ""}
	c = {"_id": "character:c", "prenom": "Cy", "nom": ""}
	assert not col.peut_demander(_perso(), imp, reg)[0]                         # le fondateur
	assert col.peut_demander(b, imp, reg) == (True, "")
	col.demander(b, imp, "  Je  porte du bois.  ", now=1)
	assert imp["demandes"][0]["texte"] == "Je porte du bois." and b["demande_association"] == imp["_id"]
	assert not col.peut_demander(b, imp, reg)[0]
	col.demander(c, imp, "Moi aussi", now=2)
	assert col.repondre(imp, reg, "character:b", True, now=3)[0]
	assert col.role_de(b, imp) == col.ASSOCIE and col.vaut_presence(col.ASSOCIE)
	ok, raison, _ = col.repondre(imp, reg, "character:c", True, now=4)
	assert not ok and "places" in raison                                        # une seule place au Campement
	assert col.repondre(imp, reg, "character:c", False, now=5)[0] and imp["demandes"] == []
	# le personnage suit le doc du lieu, paresseusement
	lire = {imp["_id"]: imp}.get
	assert col.synchroniser_association(b, lire) and b == {**b, "association": imp["_id"]} and "demande_association" not in b
	assert col.synchroniser_association(c, lire) and "demande_association" not in c and "association" not in c
	# une seule association active
	autre = _imp(reg)
	assert "déjà associé" in col.peut_demander(b, autre, reg)[1]
	# exclusion : les apports restent au lieu, l'association tombe au passage suivant
	imp["stocks"]["bois"] = 0
	col.deposer(imp, reg, b, "bois", 4, now=6)
	assert col.retirer_associe(imp, "character:b", exclu=True, now=7)
	assert imp["stocks"]["bois"] == 4 and col.role_de(b, imp) == col.VISITEUR
	assert col.synchroniser_association(b, lire) and "association" not in b


def test_le_visiteur_lit_en_mots_le_fondateur_a_les_chiffres():
	reg = _reg()
	imp = _imp(reg)
	site = _site(reg)
	col.noter(imp, "secret du carnet", 1)
	visiteur = col.vue(imp, reg, col.VISITEUR, site, [], CAT_PROP, now=10)
	assert visiteur["securite"] == {"mot": col.securite(imp, reg, site, [])["mot"]}
	assert set(visiteur["moral"]) == {"mot"} and all(set(b) == {"mots"} for b in visiteur["site"].values())
	assert not {"stocks", "journal", "batiments", "demandes", "population", "chantier"} & set(visiteur)
	assert visiteur["fondateur_nom"] == "Greta Hazgard" and visiteur["palier"]["label"] == "Campement"
	assert "besoins" in visiteur and len(visiteur["stocks_ouverts"]) == len(reg["stocks"])
	fondateur = col.vue(imp, reg, col.FONDATEUR, site, [], CAT_PROP, now=10)
	assert "valeur" in fondateur["securite"] and "facteurs" in fondateur["moral"]
	assert fondateur["journal"][0]["texte"] == "secret du carnet" and len(fondateur["stocks"]) == len(reg["stocks"])
	associe = col.vue(imp, reg, col.ASSOCIE, site, [], CAT_PROP, now=10)
	assert "stocks" in associe and "journal" not in associe and "demandes" not in associe
	# le catalogue ne montre que ce qui se construit AU PALIER COURANT, les sept paliers ont leur libellé de menace
	# sans métier disponible, une boutique « toutes catégories » n'a aucune ligne d'achat
	assert {c["id"] for c in fondateur["catalogue"]} == {d["id"] for d in reg["batiments_def"]
														  if d["nature"] in col.NATURES_OUVERTES and d.get("catalogue", True)
														  and not d.get("toutes_categories")
														  and col.palier_atteint(reg, imp["palier"], d.get("palier_min"))}
	assert not any(c["id"] == "ferme" for c in fondateur["catalogue"])        # la ferme attend le Hameau
	# les fortifications aussi : seules celles du palier courant, plus celles déjà en place
	assert {f["id"] for f in fondateur["fortifications"]} == {
		f["id"] for f in reg["fortifications"] if col.palier_atteint(reg, imp["palier"], f.get("palier_min"))}
	assert len(fondateur["fortifications"]) < len(reg["fortifications"])     # le campement n'ouvre pas tout
	loin = next(f for f in reg["fortifications"] if not col.palier_atteint(reg, imp["palier"], f.get("palier_min")))
	imp["fortifications"] = [loin["id"]]
	assert loin["id"] in {f["id"] for f in col.vue(imp, reg, col.FONDATEUR, site, [], CAT_PROP, now=10)["fortifications"]}
	assert set(reg["menace"]["attaque_proba"]) == {p["id"] for p in col.paliers(reg)}


def test_regles_absentes_rien_ne_se_fonde_et_les_blocs_manquants_retombent_sur_les_defauts():
	vide = col.regles({}.get)
	assert col.paliers(vide) == [] and not col.peut_fonder(_perso(), _pays(), SITE_POS, RELIES, [], vide)[0]
	partiel = col.regles({col.REGLES_ID: {"value": {"securite": {"plafond": 80}}}}.get)
	assert partiel["securite"]["plafond"] == 80 and partiel["securite"]["mots"] == col.DEFAUTS["securite"]["mots"]
	assert partiel["sante"] == col.DEFAUTS["sante"]


def test_la_liste_des_lieux_ne_montre_d_une_implantation_que_le_public():
	reg = _reg()
	imp = _imp(reg)
	col.noter(imp, "secret", 1)
	public = col.details_publics(dict(imp))
	assert set(public) <= set(col.CHAMPS_PUBLICS) and public["label"] == imp["label"]
	assert not {"journal", "stocks", "demandes", "cells", "nav", "fondateur"} & set(public)
	ville = {"type": "lieu", "categorie": "ville", "flux_marchand": {}}
	assert col.details_publics(ville) is ville


# ── Sous-lieux et vente de la production (§ 8, § 12.4) ───────────────────────────────

DISPONIBLES = ["boulangerie", "armurerie", "grande_boulangerie", "negociant", "etable", "auberge", "inconnue"]


def test_chaque_boutique_de_cite_s_achete_une_par_une():
	reg = _reg()
	boutique = col.batiment_def(reg, "boutique")
	assert col.categories_possibles(reg, "boutique", DISPONIBLES) == sorted(
		c for c in DISPONIBLES if c not in ("auberge", "etable"))              # grandes maisons et négociant compris
	assert col.categories_possibles(reg, "auberge", []) == ["auberge"]
	imp = _imp(reg, "bourgade", stocks={"bois": 0, "materiaux": 0})
	lignes = col.catalogue_achats(imp, reg, DISPONIBLES)
	par_cat = {l["categorie"]: l for l in lignes if l["id"] == "boutique"}
	# la grande maison n'est pas présentée avant son palier
	assert set(par_cat) == {c for c in col.categories_possibles(reg, "boutique", DISPONIBLES) if not col.est_grande_maison(c)}
	assert par_cat["boulangerie"]["prix"] == boutique["prix_cuivre"] and par_cat["boulangerie"]["refus"] == ""
	assert par_cat["boulangerie"]["bois"] == par_cat["boulangerie"]["materiaux"] == 0   # acheté, sans stock
	assert "palier" in col.peut_construire(imp, reg, "boutique", "grande_boulangerie", DISPONIBLES)[1]
	bourg = _imp(reg, boutique["palier_grande_maison"])
	grande = {l["categorie"]: l for l in col.catalogue_achats(bourg, reg, DISPONIBLES) if l["id"] == "boutique"}["grande_boulangerie"]
	assert grande["grande"] and grande["prix"] == boutique["prix_grande_maison"]
	assert not any(l["id"] == "boutique" for l in col.catalogue_achats(_imp(reg), reg, DISPONIBLES))  # campement : aucune boutique
	assert col.peut_construire(_imp(reg, boutique["palier_grande_maison"]), reg, "boutique", "grande_boulangerie", DISPONIBLES)[0]
	assert "métier" in col.peut_construire(imp, reg, "boutique", "etable", DISPONIBLES)[1]
	assert "métier" in col.peut_construire(imp, reg, "boutique", "absente", DISPONIBLES)[1]
	b = col.construire(imp, reg, "boutique", now=1, categorie="boulangerie")
	assert b["categorie"] == "boulangerie" and "Boulangerie" in imp["journal"][-1]["texte"]
	assert col.construire(imp, reg, "auberge", now=1)["categorie"] == "auberge"
	assert "categorie" not in col.construire(imp, reg, "habitation", now=1)
	assert col.libelle_metier("boulangerie") == "Boulangerie"
	assert not any(l["id"] == "atelier" for l in lignes)                     # fondu dans la boutique


def test_premiere_pose_d_un_sous_lieu_cree_le_lieu_et_sa_porte():
	reg = _reg()
	imp = _imp(reg, "bourgade", stocks={"bois": 999, "materiaux": 999})
	b = col.construire(imp, reg, "boutique", now=1, categorie="boulangerie")
	col.poser(imp, b["id"], [4, 4])
	lieu, lien = col.creer_sous_lieu(imp, b, reg, "boulangerie_europe01.jpg")
	assert lieu["_id"].startswith(col.PREFIXE_SOUS_LIEU) and lieu["type"] == "lieu"
	assert lieu["categorie"] == "boulangerie" and lieu["lieu_parent"] == imp["_id"] and col.est_sous_lieu(lieu)
	assert lieu["label"] == f"Boulangerie de {imp['label']}"
	assert lien["nodes"] == [{"lieu": imp["_id"], "pos": [4, 4]}, {"lieu": lieu["_id"], "pos": [0, 0]}]
	assert (b["lieu"], b["lien"]) == (lieu["_id"], lien["_id"])
	col.poser(imp, b["id"], [5, 6])
	assert col.deplacer_sous_lieu(lien, imp["_id"], b["pos"]) and lien["nodes"][0]["pos"] == [5, 6]
	assert not col.deplacer_sous_lieu(lien, imp["_id"], None)             # sans case, la porte reste
	from utils import marche
	assert marche.est_cite(imp) and not marche.est_cite(lieu)             # l'implantation EST sa cité


def test_une_boutique_fonctionne_comme_en_ville_sans_pnj_a_engager():
	reg = _reg()
	imp = _imp(reg, "bourgade", stocks={"bois": 999, "materiaux": 999})
	b = col.construire(imp, reg, "etable", now=1)
	col.poser(imp, b["id"], [4, 4])
	lieu, _ = col.creer_sous_lieu(imp, b, reg, "etable_europe01.png")
	docs = {imp["_id"]: imp, lieu["_id"]: lieu}
	assert col.sous_lieu_ouvert(lieu, docs.get) == (True, "")                # ouverte tout de suite
	assert col.postes(imp, reg) == []                                       # aucun poste à pourvoir
	modele = {"_id": "pnj:marchand_etable", "nom": "Throlgar", "portrait": "t.png"}
	assert col.pnj_comme_en_ville(lieu, modele, reg) == [{"character": "pnj:marchand_etable", "nom": "Throlgar",
														   "portrait": "t.png", "montures": reg["montures_etable"]}]
	assert col.pnj_comme_en_ville({"categorie": "auberge"}, modele, reg) == []
	lieu["pnj"] = col.pnj_comme_en_ville(lieu, modele, reg)
	assert col.synchroniser_tenanciers(imp, reg, [], docs.get) == []         # son marchand reste
	b["endommage"] = True
	assert "endommagé" in col.sous_lieu_ouvert(lieu, docs.get)[1]
	assert col.sous_lieu_ouvert({"_id": "lieu:auxerre", "categorie": "ville"}, docs.get) == (True, "")


def _vente(reg, stock=200.0, **extra):
	imp = _imp(reg, "bourgade", stocks={"nourriture": stock, "bois": 0, "materiaux": 0, "medicaments": 999})
	imp["batiments"] = [{"id": "b_f", "type": "ferme", "pos": [1, 1]}]
	agri = _employe(imp, "agriculteur", "b_f")
	agri.update(extra)
	return imp, agri


class _Boutique(dict):
	pass


def test_le_surplus_de_production_se_vend_aux_boutiques_du_lieu(monkeypatch):
	from utils import echanges_cite, marche
	reg = _reg()
	imp, agri = _vente(reg)
	boulangerie = {"_id": "lieu:colonie_b", "categorie": "boulangerie", "stock_matieres": {}, "stock_vente": []}
	monkeypatch.setattr(echanges_cite, "prix_vente_boutique", lambda ctx, b, doc: 7)
	recus = []
	monkeypatch.setattr(marche, "absorber_achat", lambda b, doc, *a, **k: recus.append((b["_id"], doc["_id"])))
	items = {i: {"_id": i, "nom": i, "poids": 0.5} for i in col.DEFAUTS["metiers_def"][0]["produit"]["items"]}
	plancher = reg["echanges"]["surplus_facteur"] * col.seuils_stocks(imp, reg, [agri])["nourriture"]
	bilan = col.echanger(imp, reg, [agri], [boulangerie], {}.get, items.get, 1, rand=random.Random(0), now=5)
	assert bilan["gain"] == 7 * len(recus) and imp["caisse_cuivre"] == bilan["gain"] and recus
	assert imp["stocks"]["nourriture"] >= plancher                          # jamais sous le surplus
	# le portage d'une passe borne ce qui part (20 kg ⇒ 40 objets de 0,5 kg)
	assert len(recus) == int(reg["echanges"]["portage_kg"] / 0.5)
	assert imp["echanges_journal"] and bilan["touchees"] == [boulangerie]
	# interdite par le fondateur : la production reste au lieu
	imp2, agri2 = _vente(reg, vente_cite=False)
	assert col.echanger(imp2, reg, [agri2], [boulangerie], {}.get, items.get, 5, rand=random.Random(0))["gain"] == 0
	# aucune boutique preneuse, pas de crieur : rien ne part
	monkeypatch.setattr(echanges_cite, "prix_vente_boutique", lambda ctx, b, doc: None)
	imp3, agri3 = _vente(reg)
	assert col.echanger(imp3, reg, [agri3], [boulangerie], {}.get, items.get, 5, rand=random.Random(0))["gain"] == 0


# ── Autonomie des approvisionnements ─────────────────────────────────────────────────

def test_les_comptes_glanent_et_les_soignants_font_des_simples():
	reg = _reg()
	appro = reg["approvisionnement"]
	site = {"nourriture": {"note": 2}, "materiaux": {"note": 0}}
	imp = _imp(reg, population=4)
	auto = col.production_autonome(imp, reg, site, [])
	assert auto["nourriture"] == 4 * appro["glanage"]["nourriture"] * col.facteur_axe(site, "nourriture", reg)
	assert auto["bois"] == 4 * appro["glanage"]["bois"] * col.facteur_axe(site, "materiaux", reg)
	assert "medicaments" not in auto
	# le glanage couvre une part des bouches des comptés, jamais toutes (sinon plus de besoin)
	assert auto["nourriture"] < 4 * reg["consommation"]["nourriture_par_habitant_jour"]
	# personne de compté : aucun glanage ; un soignant au poste : des simples
	vide = _imp(reg)
	vide["batiments"] = [{"id": "b_h", "type": "habitation", "pos": [1, 1]}]
	medecin = _employe(vide, "medecin", "b_h")
	auto = col.production_autonome(vide, reg, site, [medecin])
	assert set(auto) == {"medicaments"}
	assert auto["medicaments"] == appro["soignant"]["par_jour"] * col.facteur_axe(site, appro["soignant"]["axe"], reg)
	# poste endommagé : plus de simples
	vide["batiments"][0]["endommage"] = True
	assert col.production_autonome(vide, reg, site, [medecin]) == {}


def test_une_passe_ajoute_le_glanage_dans_la_capacite():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	site = {"nourriture": {"note": 3}, "materiaux": {"note": 3}}
	imp = _imp(reg, population=2, rattrape_at=0, feu="reduit",
			   stocks={"nourriture": 20.0, "bois": 20.0, "materiaux": 0.0, "medicaments": 99.0})
	sans = copy.deepcopy(imp)
	sans["population"] = 0
	col.rattraper(imp, reg, site, [], now=pas, rand=Hasard())
	col.rattraper(sans, reg, site, [], now=pas, rand=Hasard())
	# même consommation de bois ; la nourriture diffère du glanage MOINS les bouches des comptés
	gl = col.production_autonome(imp, reg, site, [])
	part = pas / col.JOUR_S
	assert round(imp["stocks"]["bois"] - sans["stocks"]["bois"], 3) == round(gl["bois"] * part, 3)
	attendu = (gl["nourriture"] - 2 * reg["consommation"]["nourriture_par_habitant_jour"]) * part
	assert round(imp["stocks"]["nourriture"] - sans["stocks"]["nourriture"], 3) == round(attendu, 3)


def test_la_consigne_est_eteinte_par_defaut_et_bornee():
	reg = _reg()
	imp = _imp(reg)
	defaut = reg["approvisionnement"]["plafond_jour_defaut"]
	assert col.consigne(imp, reg, "nourriture") == {"acheter": False, "plafond_jour": defaut}
	assert col.regler_consigne(imp, reg, "nourriture", True, 300) == (True, "")
	assert col.consigne(imp, reg, "nourriture") == {"acheter": True, "plafond_jour": 300}
	assert not col.regler_consigne(imp, reg, "or_pur", True, 10)[0]
	assert not col.regler_consigne(imp, reg, "bois", True, -1)[0]
	assert not col.regler_consigne(imp, reg, "bois", True, col.PLAFOND_JOUR_MAX + 1)[0]
	assert not col.regler_consigne(imp, reg, "bois", True, "beaucoup")[0]


def _appro(reg, caisse=10000, charretier=False, **stocks):
	imp = _imp(reg, "bourgade", caisse_cuivre=caisse,
			   stocks={"nourriture": 0.0, "bois": 0.0, "materiaux": 0.0, "medicaments": 0.0, **stocks})
	imp["batiments"] = [{"id": "b_e", "type": "entrepot", "pos": [1, 1]}, {"id": "b_c", "type": "comptoir", "pos": [2, 2]}]
	employes = [_employe(imp, "intendant", "b_e")]
	if charretier:
		employes.append(_employe(imp, "charretier", "b_c", 1))
	return imp, employes


NOURRITURE = {"stock": "nourriture", "unites_par_kg": 1}
PAIN = {"_id": "item:pain", "nom": "Pain", "poids": 1}


def _stock_de(doc):
	return NOURRITURE if doc.get("_id") == "item:pain" else None


def test_l_intendant_n_achete_que_ce_que_le_fondateur_a_mis_en_consigne(monkeypatch):
	from utils import echanges_cite
	reg = _reg()
	monkeypatch.setattr(echanges_cite, "prix_achat_boutique", lambda ctx, b, doc: 10)
	boutique = {"_id": "lieu:colonie_b", "stock_vente": [{"item_id": "item:pain", "qty": 50}]}
	imp, employes = _appro(reg)
	# sans consigne : rien
	bilan = col.approvisionner(imp, reg, employes, [boutique], {}.get, {"item:pain": PAIN}.get, _stock_de, 24, now=5)
	assert bilan["depense"] == 0 and imp["stocks"]["nourriture"] == 0
	# consigne, mais sans intendant au poste : rien
	col.regler_consigne(imp, reg, "nourriture", True, 1000)
	assert col.approvisionner(imp, reg, [], [boutique], {}.get, {"item:pain": PAIN}.get, _stock_de, 24, now=5)["depense"] == 0
	# l'intendant achète jusqu'au seuil bas, sur la caisse, et le rayon de la boutique baisse
	seuil = col.seuils_stocks(imp, reg, employes)["nourriture"]
	bilan = col.approvisionner(imp, reg, employes, [boutique], {}.get, {"item:pain": PAIN}.get, _stock_de, 24, now=5)
	assert imp["stocks"]["nourriture"] >= seuil and imp["stocks"]["nourriture"] - seuil < 1
	n = imp["stocks"]["nourriture"]
	assert bilan["depense"] == 10 * n and imp["caisse_cuivre"] == 10000 - bilan["depense"]
	assert boutique["stock_vente"][0]["qty"] == 50 - n and bilan["touchees"] == [boutique]
	assert imp["echanges_journal"][0]["sens"] == "achat"
	# le plafond du jour borne la dépense (× le temps écoulé : une passe = 1/24 de jour)
	imp2, employes2 = _appro(reg)
	col.regler_consigne(imp2, reg, "nourriture", True, 240)
	bilan = col.approvisionner(imp2, reg, employes2, [boutique], {}.get, {"item:pain": PAIN}.get, _stock_de, 1, now=5)
	assert bilan["depense"] == 10 and imp2["stocks"]["nourriture"] == 1
	# caisse vide : rien
	imp3, employes3 = _appro(reg, caisse=0)
	col.regler_consigne(imp3, reg, "nourriture", True, 1000)
	assert col.approvisionner(imp3, reg, employes3, [boutique], {}.get, {"item:pain": PAIN}.get, _stock_de, 24, now=5)["depense"] == 0


def test_le_charretier_part_en_cite_et_le_convoi_arrive_au_rattrapage():
	reg = _reg()
	appro = reg["approvisionnement"]
	imp, employes = _appro(reg, charretier=True)
	col.regler_consigne(imp, reg, "nourriture", True, 100000)
	cite = {"label": "Cité", "distance": 10}
	seuil = col.seuils_stocks(imp, reg, employes)["nourriture"]
	bilan = col.approvisionner(imp, reg, employes, [], {}.get, {}.get, _stock_de, 24, cite=cite, now=1000)
	[l] = imp["livraisons"]
	prix_u = appro["prix_unite_cite"]["nourriture"] * (1 + appro["majoration_par_case"] * 10)
	assert l["unites"] == int(seuil) and l["cout"] == int(math.ceil(l["unites"] * prix_u))
	assert l["arrivee"] == 1000 + 10 * appro["duree_par_case_s"] and imp["caisse_cuivre"] == 10000 - l["cout"]
	assert imp["stocks"]["nourriture"] == 0 and bilan["evenements"]
	# un convoi en route compte : pas de second départ
	col.approvisionner(imp, reg, employes, [], {}.get, {}.get, _stock_de, 24, cite=cite, now=1001)
	assert len(imp["livraisons"]) == 1
	# arrivée : versé au stock au premier instant qui passe l'échéance
	evenements = {"evenements": []}
	col.livrer(imp, reg, l["arrivee"] - 1, evenements)
	assert imp["livraisons"] and imp["stocks"]["nourriture"] == 0
	col.livrer(imp, reg, l["arrivee"], evenements)
	assert imp["livraisons"] == [] and imp["stocks"]["nourriture"] == l["unites"] and evenements["evenements"]
	# sans charretier, aucune cité : pas de convoi
	imp2, employes2 = _appro(reg)
	col.regler_consigne(imp2, reg, "nourriture", True, 100000)
	col.approvisionner(imp2, reg, employes2, [], {}.get, {}.get, _stock_de, 24, cite=cite, now=1000)
	assert not imp2.get("livraisons")


def test_l_intendant_troque_un_surplus_a_perte_moindre_avec_un_negociant():
	reg = _reg()
	appro = reg["approvisionnement"]
	imp, employes = _appro(reg, caisse=0, bois=60.0)
	col.regler_consigne(imp, reg, "nourriture", True, 1000)
	seuils = col.seuils_stocks(imp, reg, employes)
	surplus = 60.0 - reg["echanges"]["surplus_facteur"] * seuils["bois"]
	assert surplus > 0
	col.approvisionner(imp, reg, employes, [], {}.get, {}.get, _stock_de, 24, now=5)
	recu = imp["stocks"]["nourriture"]
	assert recu == round(min(seuils["nourriture"], surplus / appro["troc_taux"]), 1) and recu > 0
	assert round(imp["stocks"]["bois"], 3) == round(60.0 - recu * appro["troc_taux"], 3)
	assert imp["stocks"]["bois"] >= reg["echanges"]["surplus_facteur"] * seuils["bois"] - 0.1   # jamais sous le surplus
	assert imp["echanges_journal"][0]["sens"] == "troc"
	assert appro["troc_taux_negociant"] < appro["troc_taux"]


def _metier(reg, ident):
	return next(m for m in reg["metiers_def"] if m["id"] == ident)


def test_le_bucheron_vend_l_essence_du_site_et_le_carrier_ses_minerais():
	reg = _reg()
	rondins = [{"_id": f"item:Rondin_de_{e}", "type": "item", "sous_categorie": "rondin", "tags": [f"essence_{e.lower()}"]}
			   for e in ("Chene", "Bouleau")]
	find = lambda q: [d for d in rondins if d["sous_categorie"] == q.get("sous_categorie")]
	resolve = {**RESSOURCES, **{d["_id"]: d for d in rondins}}.get
	bucheron, carrier = _metier(reg, "bucheron")["produit"], _metier(reg, "carrier")["produit"]
	site = {"materiaux": {"note": 2, "ressources": ["item:Bouleau", "item:fer"]}}
	# le bouleau du site, pas le chêne de la liste habituelle
	assert col.objets_du_metier("bucheron", bucheron, site, reg, resolve, find) == ["item:Rondin_de_Bouleau"]
	# la pierre habituelle PLUS le fer du site
	assert col.objets_du_metier("carrier", carrier, site, reg, resolve, find) == carrier["items"] + ["item:fer"]
	# une pierre de construction du site (sous-catégorie « pierre ») se vend aussi, avec la pierre brute
	marbre = {"_id": "item:marbre", "type": "item", "categorie": "composant", "sous_categorie": "pierre"}
	resolve_m = {**RESSOURCES, marbre["_id"]: marbre}.get
	site_m = {"materiaux": {"note": 1, "ressources": ["item:marbre"]}}
	assert col.objets_du_metier("carrier", carrier, site_m, reg, resolve_m, find) == carrier["items"] + ["item:marbre"]
	# sans ressource adaptée : la liste habituelle
	for metier, produit in (("bucheron", bucheron), ("carrier", carrier)):
		assert col.objets_du_metier(metier, produit, {}, reg, resolve, find) == produit["items"]
	# un métier hors `ventes_du_site` ne bouge pas
	agri = _metier(reg, "agriculteur")["produit"]
	assert col.objets_du_metier("agriculteur", agri, site, reg, resolve, find) == agri["items"]


def test_le_personnel_du_comptoir_releve_portage_caisse_et_crieur():
	reg = _reg()
	imp = _imp(reg, "bourgade")
	imp["batiments"] = [{"id": "b_c", "type": "comptoir", "pos": [1, 1]}]
	base = col.caisse_max(imp, reg, [])
	assert base == reg["echanges"]["caisse_max_par_rang"] * (col.rang_palier(reg, "bourgade") + 1)
	staff = [_employe(imp, m, "b_c", n) for n, m in enumerate(("charretier", "teneur_livres", "crieur", "commis"))]
	eff = col.effets_negoce(imp, reg, staff)
	defs = col.batiment_def(reg, "comptoir")["effets_metier"]
	assert eff == {k: v for bloc in defs.values() for k, v in bloc.items()}
	assert col.caisse_max(imp, reg, staff) == base * defs["teneur_livres"]["caisse_facteur"]
	assert col.relever_caisse({**imp, "caisse_cuivre": 30}, _perso(), now=1) == 30


def test_le_generateur_complete_les_entrees_sans_reecrire_ce_qui_existe():
	ancien = copy.deepcopy(REGLES_DOC)
	b = next(x for x in ancien["value"]["batiments_def"] if x["id"] == "auberge")
	del b["categorie"]
	b["prix_cuivre"] = 1                                                     # retouché par l'Auteur
	ancien["value"]["batiments_def"] = [x for x in ancien["value"]["batiments_def"] if x["id"] != "comptoir"]
	dump = {d["_id"]: copy.deepcopy(d) for d in DOCS if d["_id"] != col.REGLES_ID}
	dump[col.REGLES_ID] = ancien
	[doc] = gen.generer(dump)
	auberge = next(x for x in doc["value"]["batiments_def"] if x["id"] == "auberge")
	assert auberge["categorie"] == "auberge" and auberge["prix_cuivre"] == 1
	assert any(x["id"] == "comptoir" for x in doc["value"]["batiments_def"])


# ── Combats joués : défense, tanière (§ 6) ; repos au feu ────────────────────────────

def test_present_le_fondateur_peut_etre_pris_dans_une_attaque_au_plus_une_fois_par_passe():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	site = _site(reg)
	imp = _imp(reg, menace={"espece": "espece:loup", "etape": 1})
	assert not col.attaque_presente(imp, reg, site, [], now=10 * pas, rand=Hasard(0.0))   # pas encore remarqué
	imp["menace"]["etape"] = 2
	assert col.attaque_presente(imp, reg, site, [], now=10 * pas, rand=Hasard(0.0))
	assert imp["attaque_en_cours"] == {"at": 10 * pas, "espece": "espece:loup"}
	assert not col.attaque_presente(imp, reg, site, [], now=20 * pas, rand=Hasard(0.0))   # une à la fois
	imp.pop("attaque_en_cours")
	assert not col.attaque_presente(imp, reg, site, [], now=10 * pas + 5, rand=Hasard(0.0))  # même passe
	assert not col.attaque_presente(imp, reg, site, [], now=12 * pas, rand=Hasard(0.999))


def test_une_attaque_laissee_sans_reponse_se_resout_seule():
	reg = _reg()
	delai = reg["menace"]["delai_defense_s"]
	imp = _imp(reg, rattrape_at=1000, stocks={"nourriture": 100.0, "bois": 100.0, "materiaux": 0.0, "medicaments": 0.0})
	imp["attaque_en_cours"] = {"at": 1000, "espece": "espece:loup"}
	col.rattraper(imp, reg, _site(reg), [], now=1000 + delai - 1, rand=Hasard(0.99))
	assert imp.get("attaque_en_cours")                                      # encore le temps de répondre
	bilan = col.rattraper(imp, reg, _site(reg), [], now=1000 + delai, rand=Hasard(0.99))
	assert "attaque_en_cours" not in imp and bilan.get("evenements_attente")
	assert imp["attaques"][-1]["at"] == 1000 and imp["journal"]


def test_issue_d_une_defense_gardes_tombes_et_idempotence():
	reg = _reg()
	imp = _imp(reg, stocks={"nourriture": 100.0, "bois": 100.0, "materiaux": 0.0, "medicaments": 0.0})
	imp["batiments"] = [{"id": "b_g", "type": "poste_de_garde", "pos": [1, 1]}]
	g1, g2 = _employe(imp, "garde", "b_g", 1), _employe(imp, "garde", "b_g", 2)
	employes = [g1, g2]
	imp["attaque_en_cours"] = {"at": 1, "espece": "espece:loup"}
	info = {"implantation": imp["_id"], "genre": col.DEFENSE}
	touches = col.issue_combat(imp, reg, info, "victoire", [g1["_id"]], employes, "combat:1", now=50, rand=Hasard())
	assert touches == [g1] and g1["statut"] == col.EMPLOYE_MORT and imp["employes"] == [g2["_id"]]
	assert imp["attaques"][-1] == {"at": 50, "repoussee": True} and "attaque_en_cours" not in imp
	assert col.issue_combat(imp, reg, info, "victoire", [g1["_id"]], employes, "combat:1") is None   # déjà appliqué
	# perdue : les pertes d'une attaque subie, sans que la sécurité ne retienne rien
	col.issue_combat(imp, reg, info, "defaite", [], employes, "combat:2", now=60, rand=Hasard(0.0))
	assert imp["attaques"][-1] == {"at": 60, "repoussee": False} and imp["stocks"]["nourriture"] < 100


def test_la_taniere_videe_fait_taire_la_menace_puis_une_autre_bete_s_installe():
	reg = _reg()
	pas = reg["temps"]["passe_s"]
	imp = _imp(reg, menace={"espece": "espece:loup", "etape": 3}, stocks={s: 9999 for s in reg["stocks"]})
	assert "localisée" in col.peut_vider_taniere(imp, col.FONDATEUR)[1]
	imp["menace"]["etape"] = 4
	assert col.peut_vider_taniere(imp, col.ASSOCIE) == (True, "")
	assert not col.peut_vider_taniere(imp, col.VISITEUR)[0]
	info = {"implantation": imp["_id"], "genre": col.TANIERE}
	assert col.issue_combat(imp, reg, info, "fuite", [], [], "combat:t0", now=100) == []
	assert imp["menace"]["etape"] == 4                                      # fuir ne vide rien
	col.issue_combat(imp, reg, info, "victoire", [], [], "combat:t1", now=100)
	assert imp["menace"] == {"espece": "espece:loup", "etape": 0, "nettoyee_at": 100}
	assert imp["expeditions_reussies"] == 1
	imp["rattrape_at"] = 100
	repousse = reg["menace"]["repousse_s"]
	col.rattraper(imp, reg, _site(reg), [], now=100 + repousse - pas, rand=Hasard(0.99))
	assert imp["menace"]["etape"] == 0
	bilan = col.rattraper(imp, reg, _site(reg), [], now=100 + repousse + pas, rand=Hasard(0.99))
	assert imp["menace"]["etape"] == 1 and any("autre bête" in e for e in bilan["evenements"])


def test_les_assaillants_partent_des_entrees_et_la_meute_grossit_avec_le_palier():
	reg = _reg()
	imp = _imp(reg, "village")
	entrees = col.entrees_de(imp)
	combat = {"joueurs": [{"pos": {"x": 10, "y": 10}}],
			  "monstres": [{"pos": {"x": 11, "y": 11}} for _ in range(len(entrees) + 1)] + [{"pos": {"x": 1, "y": 1}, "jeton": {"largeur": 2, "profondeur": 2}}]}
	col.placer_assaillants(combat, imp)
	cases = [(m["pos"]["x"], m["pos"]["y"]) for m in combat["monstres"]]
	assert len(set(cases)) == len(cases)
	assert all(col.distance(list(c), e) <= 1 for c, e in zip(cases, entrees))           # une par entrée
	assert cases[-1] == (1, 1)                                               # un grand jeton garde sa case
	assert col.nb_adversaires(_imp(reg, "ville"), reg, col.DEFENSE) > col.nb_adversaires(imp, reg, col.DEFENSE)


def test_un_garde_se_bat_sous_son_nom_avec_l_equipement_standard():
	reg = _reg()
	e = {"_id": "employe:g", "prenom": "Aldo", "nom": "Brun", "race": "nain", "sex": "M", "portrait": "p.jpg"}
	g = col.garde_combattant(e, reg)
	conf = reg["garde_combattant"]
	assert (g["_id"], g["prenom"], g["race"], g["image"]) == ("employe:g", "Aldo", "nain", "p.jpg")
	assert g["caracteristiques_current"] == conf["caracts"] and g["slots"] == conf["slots"]
	assert g["vocations_niveaux"] == {conf["voc"]: conf["niveau"]}


def test_la_nuit_d_une_implantation_se_raconte_au_feu():
	reg = _reg()
	imp = _imp(reg)
	lu = col.lieu_de_nuit(imp, {col.REGLES_ID: REGLES_DOC}.get)
	assert lu["nuit_messages"] == reg["nuit_feu"] and "nuit_messages" not in imp
	ville = {"type": "lieu", "categorie": "ville"}
	assert col.lieu_de_nuit(ville, {}.get) is ville


# ── La guilde du joueur (§ 9) ────────────────────────────────────────────────────────

def _guilde(reg, palier="village", associes=()):
	imp = _imp(reg, palier)
	imp["associes"] = [{"id": a, "nom": a, "apports": {}} for a in associes]
	ok, _r, chantier = col.peut_ouvrir_echelon(imp, reg)
	assert ok
	col.ouvrir_chantier(imp, reg, chantier, now=1)
	col.financer(imp, _perso(), chantier["cout"], now=2)
	assert col.achever_guilde(imp, reg, "  Les  Loups  ", now=3)
	return imp


def test_la_guilde_s_ouvre_au_village_et_les_associes_d_alors_sont_fondateurs():
	reg = _reg()
	premier = col.echelons(reg)[0]
	assert col.palier_def(reg, premier["palier"])
	assert "palier" in col.peut_ouvrir_echelon(_imp(reg, "bourgade"), reg)[1]
	imp = _guilde(reg, associes=["character:b"])
	g = col.guilde_de(imp)
	assert g["nom"] == "Les Loups" and g["echelon"] == premier["id"]
	assert g["membres"]["character:a"]["titre"] == col.MAITRE
	assert g["membres"]["character:b"]["titre"] == col.MEMBRE_FONDATEUR
	assert col.fonctions(imp, reg) == set(premier["fonctions"])
	[maison] = [b for b in imp["batiments"] if b["type"] == "maison_guilde"]
	assert maison["pos"] is None                                             # elle attend sa pose
	# rejoindre plus tard : simple membre
	c = {"_id": "character:c", "prenom": "Cy", "nom": ""}
	assert col.rejoindre(c, imp) == (True, "") and col.titre_de(c, imp) == col.MEMBRE
	assert not col.rejoindre(c, imp)[0]
	assert not col.quitter_guilde(_perso(), imp)[0]                          # le maître reste
	assert col.quitter_guilde(c, imp) == (True, "") and col.titre_de(c, imp) is None


def test_les_fonctions_des_echelons_sont_cumulatives_et_suivent_le_palier():
	reg = _reg()
	imp = _guilde(reg)
	suivant = col.echelon_suivant(imp, reg)
	assert "palier" in col.peut_ouvrir_echelon(imp, reg)[1]                  # la Maison attend le Bourg
	imp["palier"] = suivant["palier"]
	ok, _r, chantier = col.peut_ouvrir_echelon(imp, reg)
	col.ouvrir_chantier(imp, reg, chantier, now=4)
	col.financer(imp, _perso(), chantier["cout"], now=5)
	assert col.achever_guilde(imp, reg, now=6)
	attendu = set(col.echelons(reg)[0]["fonctions"]) | set(suivant["fonctions"])
	assert col.fonctions(imp, reg) == attendu
	assert len([b for b in imp["batiments"] if b["type"] == "maison_guilde"]) == 1   # une seule maison


def test_la_vue_ne_presente_que_l_echelon_que_le_palier_ouvre():
	reg = _reg()
	assert col.vue_guilde(_perso(), _imp(reg), reg, [], [], now=1)["suivant"] is None     # campement : rien
	premier = col.echelons(reg)[0]
	assert col.vue_guilde(_perso(), _imp(reg, premier["palier"]), reg, [], [], now=1)["suivant"]["id"] == premier["id"]
	imp = _guilde(reg)
	suivant = col.echelon_suivant(imp, reg)
	assert not col.palier_atteint(reg, imp["palier"], suivant["palier"])
	assert col.vue_guilde(_perso(), imp, reg, [], [], now=1)["suivant"] is None
	imp["palier"] = suivant["palier"]
	assert col.vue_guilde(_perso(), imp, reg, [], [], now=1)["suivant"]["id"] == suivant["id"]


def test_les_postes_de_specialistes_n_ouvrent_qu_avec_leur_fonction():
	reg = _reg()
	imp = _guilde(reg)
	assert "specialistes" not in col.fonctions(imp, reg)
	libres = {p["metier"] for p in col.postes_libres(imp, reg, [])}
	assert not libres & set(col.METIERS_SPECIALISTES)
	ouvre = next(e for e in col.echelons(reg) if "specialistes" in (e.get("fonctions") or []))
	imp["guilde"]["echelon"] = ouvre["id"]
	libres = {p["metier"] for p in col.postes_libres(imp, reg, [])}
	assert set(col.METIERS_SPECIALISTES) <= libres


def test_defense_et_attraction_de_la_guilde():
	reg = _reg()
	imp = _guilde(reg)
	site = _site(reg)
	sans = col.securite(imp, reg, site, [])
	g = col.guilde_de(imp)
	g["echelon"] = next(e["id"] for e in col.echelons(reg) if "defense" in e["fonctions"])
	avec = col.securite(imp, reg, site, [])
	h = lambda s: next(f["valeur"] for f in s["facteurs"] if f["id"] == "defense_humaine")
	assert h(avec) == min(20, h(sans) + reg["guilde_reglages"]["defense"])
	assert col.facteur_attraction(imp, reg) == 1.0
	g["echelon"] = col.echelons(reg)[-1]["id"]
	assert col.facteur_attraction(imp, reg) == reg["guilde_reglages"]["attraction"]


def _compagnon(n, xp=0, **extra):
	c = {"_id": f"aventurier:{n}", "statut": "embauche", "embauche_par": "character:a", "xp_total": xp,
		 "prenom": f"C{n}", "nom": "", "caracteristiques_current": {"V": 5, "F": 30, "R": 30}, "currentPV": 20}
	c.update(extra)
	return c


def test_une_expedition_part_revient_et_paie_son_membre_moins_la_commission():
	reg = _reg()
	imp = _guilde(reg)
	membre = _perso(groupe=["aventurier:1", "aventurier:2"])
	c1, c2 = _compagnon(1), _compagnon(2)
	mission = col.missions_ouvertes(imp, reg)[0]
	assert not col.peut_envoyer({"_id": "character:z"}, imp, reg, mission, [c1])[0]      # pas membre
	assert not col.peut_envoyer(membre, imp, reg, None, [c1])[0]
	assert not col.peut_envoyer(membre, imp, reg, mission, [])[0]
	assert not col.peut_envoyer(membre, imp, reg, mission, [_compagnon(3)])[0]          # hors du groupe
	assert col.peut_envoyer(membre, imp, reg, mission, [c1, c2]) == (True, "")
	fermee = next(m for m in reg["missions"] if m not in col.missions_ouvertes(imp, reg))
	assert not col.peut_envoyer(membre, imp, reg, fermee, [c1])[0]                       # échelon trop bas
	exp = col.envoyer(membre, imp, reg, [], mission, [c1, c2], now=100)
	assert membre["groupe"] == [] and c1["en_mission"]["expedition"] == exp["id"]
	assert exp["retour"] == 100 + mission["duree_s"] and 0.1 <= exp["chance"] <= 0.95
	assert not col.accueillir(membre, imp, reg, [], exp["id"], [c1, c2], now=exp["retour"] - 1)[0]
	assert "complet" in col.accueillir(membre, imp, reg, [], exp["id"], [c1, c2], now=exp["retour"], places_libres=1)[1]
	ok, _r, issue = col.accueillir(membre, imp, reg, [], exp["id"], [c1, c2], now=exp["retour"], rand=Hasard(0.0))
	assert ok and issue["reussie"]
	assert issue["commission"] == int(mission["recompense_cuivre"] * reg["guilde_reglages"]["commission"])
	assert issue["gain"] + issue["commission"] == mission["recompense_cuivre"]
	assert imp["caisse_cuivre"] == issue["commission"] and imp["expeditions_reussies"] == 1
	assert membre["groupe"] == ["aventurier:1", "aventurier:2"] and "en_mission" not in c1
	assert c1["xp_total"] == mission["xp"] and col.guilde_de(imp)["expeditions"] == []


def test_une_expedition_manquee_ramene_ses_compagnons_blesses():
	reg = _reg()
	imp = _guilde(reg)
	membre = _perso(groupe=["aventurier:1"])
	c1 = _compagnon(1)
	exp = col.envoyer(membre, imp, reg, [], col.missions_ouvertes(imp, reg)[0], [c1], now=0)
	ok, _r, issue = col.accueillir(membre, imp, reg, [], exp["id"], [c1], now=exp["retour"], rand=Hasard(0.999))
	assert ok and not issue["reussie"] and issue["gain"] == 0 and c1["currentPV"] == 1
	assert not col.accueillir(membre, imp, reg, [], exp["id"], [c1], now=exp["retour"])[0]   # déjà accueilli


def test_la_chance_suit_la_puissance_du_groupe_et_le_maitre_d_armes():
	reg = _reg()
	imp = _guilde(reg)
	mission = col.missions_ouvertes(imp, reg)[0]
	faible = col.chance_reussite(imp, reg, [], mission, [_compagnon(1)])
	fort = col.chance_reussite(imp, reg, [], mission, [_compagnon(1, xp=10 ** 6), _compagnon(2, xp=10 ** 6)])
	assert faible < fort <= 0.95
	maison = next(b for b in imp["batiments"] if b["type"] == "maison_guilde")
	maitre = _employe(imp, "maitre_d_armes", maison["id"])
	assert col.chance_reussite(imp, reg, [maitre], mission, [_compagnon(1)]) == faible      # spécialistes pas encore
	col.guilde_de(imp)["echelon"] = next(e["id"] for e in col.echelons(reg) if "specialistes" in e["fonctions"])
	assert col.chance_reussite(imp, reg, [maitre], mission, [_compagnon(1)]) > faible


def test_le_tableau_de_la_maison_de_guilde_est_aux_membres():
	reg = _reg()
	imp = _guilde(reg)
	maison = next(b for b in imp["batiments"] if b["type"] == "maison_guilde")
	col.poser(imp, maison["id"], [4, 4])
	lieu, _lien = col.creer_sous_lieu(imp, maison, reg, "guilde.png")
	assert lieu["tags"] == ["recrutement"] and "stock_vente" not in lieu
	docs = {imp["_id"]: imp, col.REGLES_ID: REGLES_DOC}
	assert col.sous_lieu_ouvert(lieu, docs.get) == (True, "")                # tenue par le fondateur
	assert col.acces_tableau_guilde(_perso(), lieu, docs.get) == (True, "")
	assert "membres" in col.acces_tableau_guilde({"_id": "character:z"}, lieu, docs.get)[1]
	from utils import recrutement
	assert recrutement.lieu_recrute(lieu)
	assert recrutement.acces_autorise({"_id": "character:z"}, lieu, docs.get)[0] is False
	# le coffre : chacun dépose, le maître et les fondateurs retirent
	c = {"_id": "character:c", "prenom": "Cy", "nom": ""}
	col.rejoindre(c, imp)
	assert col.peut_retirer_coffre_guilde(_perso(), imp) and not col.peut_retirer_coffre_guilde(c, imp)


# ── Ce que l'associé y gagne (§ 10) ──────────────────────────────────────────────────

def test_prix_de_faveur_pour_le_fondateur_et_les_associes_seulement():
	from utils import marche
	reg = _reg()
	imp = _imp(reg)
	imp["associes"] = [{"id": "character:b", "nom": "Bo", "apports": {}}]
	boutique = {"_id": "lieu:colonie_x", "categorie": "boulangerie", "colonie": imp["_id"]}
	docs = {imp["_id"]: imp, col.REGLES_ID: REGLES_DOC}
	faveur = reg["associes_reglages"]["faveur_relation"]
	assert col.faveur(_perso(), boutique, docs.get) == faveur
	assert col.faveur({"_id": "character:b"}, boutique, docs.get) == faveur
	assert col.faveur({"_id": "character:z"}, boutique, docs.get) == 0
	rel = marche.get_relation(_perso(), boutique, docs.get)
	assert rel["faveur"] == faveur and rel["value"] < faveur                 # la relation elle-même ne bouge pas
	neutre = marche.get_relation({"_id": "character:z"}, boutique, docs.get)
	assert "faveur" not in neutre
	assert marche.prix_courant(rel, "item:x", 10, 100, "achat") < marche.prix_courant(neutre, "item:x", 10, 100, "achat")
	assert marche.prix_courant(rel, "item:x", 10, 100, "vente") > marche.prix_courant(neutre, "item:x", 10, 100, "vente")
	# une ancienne faveur restée en base ne vaut rien après une exclusion
	imp["associes"] = []
	stale = {"_id": "relation:character:b::lieu:colonie_x", "value": 10, "faveur": faveur}
	docs[stale["_id"]] = stale
	assert "faveur" not in marche.get_relation({"_id": "character:b"}, boutique, docs.get)
	assert col.remise_auberge(_perso(), boutique, docs.get) == reg["associes_reglages"]["remise_auberge"]


def test_entrepot_commun_depot_libre_retrait_autorise_associe_par_associe():
	reg = _reg()
	imp = _imp(reg)
	assert col.entrepot_kg(imp, reg) == 0
	imp["batiments"] = [{"id": "b_e", "type": "entrepot", "pos": [1, 1]}, {"id": "b_e2", "type": "entrepot", "pos": [2, 2]}]
	assert col.entrepot_kg(imp, reg) == 2 * reg["associes_reglages"]["entrepot_kg_par_entrepot"]
	imp["associes"] = [{"id": "character:b", "nom": "Bo", "apports": {}}]
	b = {"_id": "character:b"}
	assert col.peut_retirer_entrepot(_perso(), imp) and not col.peut_retirer_entrepot(b, imp)
	assert col.autoriser_retrait(imp, "character:b", True) and col.peut_retirer_entrepot(b, imp)
	assert not col.autoriser_retrait(imp, "character:z", True)
	assert col.coffre_associe_kg(imp, reg) == 0                              # il faut une habitation
	imp["batiments"].append({"id": "b_h", "type": "habitation", "pos": [3, 3]})
	assert col.coffre_associe_kg(imp, reg) == reg["associes_reglages"]["coffre_associe_kg"]


def test_des_colons_escortes_depuis_une_cite_proche_s_installent_a_l_arrivee():
	reg = _reg()
	imp = _imp(reg)
	imp["associes"] = [{"id": "character:b", "nom": "Bo", "apports": {}}]
	b = {"_id": "character:b", "prenom": "Bo", "nom": ""}
	dmax = reg["associes_reglages"]["colons_distance_max"]
	loin = {"id": "lieu:loin", "label": "Loin", "categorie": "ville", "pos": [SITE_POS["x"] + dmax + 1, SITE_POS["y"]]}
	relies = RELIES + [loin]
	assert "loin" in col.peut_recruter_colons(b, imp, "lieu:loin", relies, reg, [])[1]
	assert not col.peut_recruter_colons({"_id": "character:z"}, imp, "lieu:autre", relies, reg, [])[0]
	ok, _r, n = col.peut_recruter_colons(b, imp, "lieu:autre", relies, reg, [])
	libres = col.logements(imp, reg) - col.habitants(imp, [])
	assert ok and n == min(reg["associes_reglages"]["colons_max"], libres)
	convoi = col.recruter_colons(b, imp, {"_id": "lieu:autre"}, n, reg, now=10)
	assert not col.peut_recruter_colons(b, imp, "lieu:autre", relies, reg, [], now=11)[0]   # un convoi à la fois
	ailleurs = {**_imp(reg), "_id": "implantation:autre"}
	assert col.deposer_colons(b, ailleurs, reg, [], now=12) == 0 and b.get("colons")       # pas ici
	assert col.deposer_colons(b, imp, reg, [], now=12) == n
	assert imp["population"] == n and imp["associes"][0]["apports"] == {"colons": n} and "colons" not in b
	# un convoi périmé s'est dispersé
	col.recruter_colons(b, imp, {"_id": "lieu:autre"}, 1, reg, now=20)
	assert col.deposer_colons(b, imp, reg, [], now=convoi["expire_at"] + 20) == 0 and "colons" not in b


def test_l_image_definitive_d_un_modele_remplace_la_provisoire(monkeypatch):
	# Le dump porte les images PROVISOIRES (les définitives sont peut-être déjà sur le disque).
	dump = {d["_id"]: copy.deepcopy(d) for d in DOCS}
	for palier_id, provisoire, _w, _h in gen.MODELES:
		dump[f"lieu:{col.TAG_MODELE}_{palier_id}"]["image"] = provisoire
	monkeypatch.setattr(gen, "image_definitive", lambda p: "colonie_hameau_generique01.jpg" if p == "hameau" else None)
	[maj] = gen.generer(dump)
	assert maj["_id"] == "lieu:modele_colonie_hameau" and maj["image"] == "colonie_hameau_generique01.jpg"
	assert maj["cells"] == dump[maj["_id"]]["cells"]                         # seul le champ `image` change
	dump[maj["_id"]]["image"] = "retouchee.jpg"                              # posée à la main : on n'y touche pas
	assert gen.generer(dump) == []


def test_une_ruine_n_a_plus_ni_bouton_ni_marqueur_sauf_pour_qui_s_y_trouve():
	from utils import lieux
	reg = _reg()
	ruine, _t = _abandonnee(reg, 1)          # vu_at = 1000 : en ruine à l'heure réelle
	vivante = copy.deepcopy(ruine)
	vivante["vu_at"] = col.now_epoch()
	docs = {col.REGLES_ID: copy.deepcopy(REGLES_DOC)}
	perso = _perso()
	assert lieux.noeud_ferme(perso, "lieu:pays", ruine["_id"], ruine, docs.get) is True
	assert lieux.noeud_ferme(perso, "lieu:pays", vivante["_id"], vivante, docs.get) is False
	assert lieux.noeud_ferme(perso, ruine["_id"], ruine["_id"], ruine, docs.get) is False   # on ne s'expulse pas

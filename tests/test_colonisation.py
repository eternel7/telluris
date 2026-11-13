"""Voie de colonisation — logique pure (`utils/colonisation.py`) et son générateur.

Décisions verrouillées : docs/lore/systemes/20261112_voie_de_colonisation.md. Règles en
mémoire, bâties par le générateur (`gen.generer` sur un dump vide) : aucun fichier de `jsons/`."""

import copy
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


def _site(reg):
	return col.fiche_site(_pays(), SITE_POS, ZONE_DEFS, RELIES, reg)


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
	d_cite, d_imp = reg["reglages"]["distance_cite_min"], reg["reglages"]["distance_implantation_min"]
	cite = RELIES[0]["pos"]
	trop_pres = {"x": cite[0] + d_cite - 1, "y": cite[1]}
	juste = {"x": cite[0] + d_cite, "y": cite[1]}
	assert "Cité-État" in col.peut_fonder(_perso(), _pays(), trop_pres, RELIES, [], reg)[1]
	assert col.peut_fonder(_perso(charte="lieu:cite"), _pays(), juste, RELIES, [], reg)[0]
	voisine = {"fondateur": "character:b", "origine": {"pos": [SITE_POS["x"] + d_imp - 1, SITE_POS["y"]]}}
	assert "autre implantation" in col.peut_fonder(_perso(), _pays(), SITE_POS, RELIES, [voisine], reg)[1]
	voisine["origine"]["pos"][0] += 1
	assert col.peut_fonder(_perso(), _pays(), SITE_POS, RELIES, [voisine], reg)[0]
	# une seule par pays et par personnage, où qu'elle soit
	mienne = {"fondateur": "character:a", "origine": {"pos": [0, 19]}}
	assert "déjà une implantation" in col.peut_fonder(_perso(), _pays(), SITE_POS, RELIES, [mienne], reg)[1]
	# case non marchable, case déjà reliée, hors d'un pays
	assert not col.peut_fonder(_perso(), _pays(), {"x": 0, "y": 0}, RELIES, [], reg)[0]
	assert not col.peut_fonder(_perso(), _pays(), {"x": 22, "y": 12}, RELIES, [], reg)[0]
	assert not col.peut_fonder(_perso(), {**_pays(), "categorie": "ville"}, SITE_POS, RELIES, [], reg)[0]


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
	assert all(0 <= b["note"] <= 3 and b["mots"] for b in fiche.values())
	assert fiche["eau"]["note"] >= 2 and "eau à portée" in fiche["eau"]["details"]   # rivière + case d'eau
	assert fiche["danger"]["note"] >= 2 and "un donjon proche" in fiche["danger"]["details"]
	# hors de toute zone, loin de l'eau : un site nu
	nu = col.fiche_site(_pays(), {"x": 2, "y": 17}, ZONE_DEFS, RELIES, reg)
	assert nu["eau"]["note"] == 0 and nu["materiaux"]["note"] == 0 and nu["danger"]["note"] == 0


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
	bilan = col.rattraper(imp, reg, {a: {"note": 3 if a == "danger" else 0} for a in reg["axes_site"]}, [],
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
	# le catalogue ne montre que ce qui se construit, les sept paliers ont leur libellé de menace
	# sans métier disponible, une boutique « toutes catégories » n'a aucune ligne d'achat
	assert {c["id"] for c in fondateur["catalogue"]} == {d["id"] for d in reg["batiments_def"]
														  if d["nature"] in col.NATURES_OUVERTES and d.get("catalogue", True)
														  and not d.get("toutes_categories")}
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
	assert set(par_cat) == set(col.categories_possibles(reg, "boutique", DISPONIBLES))
	assert par_cat["boulangerie"]["prix"] == boutique["prix_cuivre"] and par_cat["boulangerie"]["refus"] == ""
	assert par_cat["boulangerie"]["bois"] == par_cat["boulangerie"]["materiaux"] == 0   # acheté, sans stock
	grande = par_cat["grande_boulangerie"]
	assert grande["grande"] and grande["prix"] == boutique["prix_grande_maison"] and "palier" in grande["refus"]
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
	dump = {d["_id"]: copy.deepcopy(d) for d in DOCS}
	monkeypatch.setattr(gen, "image_definitive", lambda p: "colonie_hameau_generique01.jpg" if p == "hameau" else None)
	[maj] = gen.generer(dump)
	assert maj["_id"] == "lieu:modele_colonie_hameau" and maj["image"] == "colonie_hameau_generique01.jpg"
	assert maj["cells"] == dump[maj["_id"]]["cells"]                         # seul le champ `image` change
	dump[maj["_id"]]["image"] = "retouchee.jpg"                              # posée à la main : on n'y touche pas
	assert gen.generer(dump) == []

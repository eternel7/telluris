#!/usr/bin/env python
# dev/gen_quetes_de_mu.py
# Les quêtes de Mu (demande du 26/11/2026) : TOUTES celles que le lore a identifiées pour le séjour
# (docs/lore/cites/20261124_de_mu_aux_mondes_divins.md), après « Partir pour Mu » (dev/gen_partir_pour_mu.py).
#
#   Gagner sa place
#     1. Les eaux troubles de Mu       apport  — Rangi Waiora (ouvrages de la périphérie) : carcasse de Naga,
#                                               conduites de la lisière (3 Naga, salle de donjon)
#     2. Un service qui ne peut attendre escorte — Moana Teriitahi (fare des Marées) : Tama, pris au sas
#                                               des jardiniers derrière deux murènes géantes ; pièce de sas
#                                               vendue par Kahu Rehua
#     3. Une confiance qui se mérite   apport  — Ana Hereheretue (Institut) : registre du souffleur de vasques
#                                               (déduction à l'atelier ; consignes : ne pas entrer, se taire)
#   La descente
#     4. La descente                   escorte — Aélis (fare des Marées) : réseau ancien (vannes, crans) →
#                                               chambre du sceau ; puis la déduction du scellement ouvre l'antre
#   Échidna (« Le serpent sous la cité »), choix DÉFINITIF par l'état du monde du joueur :
#     5a. La mère des serpents         transport — Échidna → Ana : son écaille, le passage de Cerbère
#     5b. le combat                    salle de donjon (Échidna seule, grade 5-6) ; elle fuit, Aélis reste
#     Quitter Mu : la copie partielle du relevé des seuils (don unique : Échidna sur la voie de la parole,
#     Aélis dans l'antre déserté sur celle du combat) — invendable.
#   Les sept affaires (apports, ordre libre ; les trois dernières après « Une confiance qui se mérite ») :
#     le chant sous les ruines · le marchand qui vend le passé · les enfants de la marée · les eaux sans
#     poissons · les cartographes qui ne dessinent plus · le dernier gardien de Mu · le nom effacé.
#     Une affaire = un donneur en ville, un lieu gardé par la quête, une énigme, un PNJ du lieu qui remet
#     la preuve (`don` unique, revenu s'il est perdu), la remise chez le donneur et ses issues PARLÉES
#     (trois là où le lore en donne trois, la seule fin du récit sinon : chant, enfants, cartographes).
#
#   ⚠️ Les issues à trois branches (condamner / sécuriser / signaler…) sont des répliques, pas un état :
#   aucune n'est mémorisée, comme le veut le lore (« aucune n'est mauvaise », sans suite sur la trame).
#   Seul le choix d'Échidna est un état, porté par la quête de la parole OU la victoire de la salle.
#   ⚠️ Un PNJ ne tient qu'UNE offre par service : un `offres` à plusieurs entrées tire au hasard parmi
#   les éligibles (utils/offres.py) sans voir les prérequis écrits dans le dialogue — d'où un donneur par quête.
#
#   Images : cartes de combat PROVISOIRES (grille et image recopiées d'une salle existante, CARTES_PROVISOIRES),
#   lieux et portraits À LIVRER par l'Auteur (noms ci-dessous, prompts dans la séance du lore).
#
# ⚠️ UN SEUL FICHIER À IMPORTER : jsons/quetes_de_mu_a_importer.json, DELTA seul (CLAUDE.md §18) : espèces
# (dev/gen_monstres_mu.py), PNJ et lieux de Mu RELUS du dump (choix, nœuds, services, présences ajoutés :
# régénération idempotente), docs neufs COMPLETS (PUT, CLAUDE.md §11).
#
# Usage : python dev/gen_quetes_de_mu.py [jsons/telluris-dump-….json]

import copy
import importlib.util
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))


def _charger(nom):
	spec = importlib.util.spec_from_file_location(nom, os.path.join(RACINE, "dev", nom + ".py"))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


V = _charger("gen_vestiges_premier_passage")
P = _charger("gen_partir_pour_mu")
import gen_monstres_mu as M  # noqa: E402

choix, noeud, ajouter_choix, sans_rev = V.choix, V.noeud, V.ajouter_choix, V.sans_rev
pnj_doc, entree_pnj, aelis, compagnon = V.pnj_doc, V.entree_pnj, V.aelis, V.compagnon

SORTIE = os.path.join(RACINE, "jsons", "quetes_de_mu_a_importer.json")

MU = P.MU
PARTIR = P.QUETE
AU_MU = {"quete_reussie": {"id": PARTIR}}

# ── Lieux déjà en base ──
SEUIL, AUBERGE, MARCHE = P.SEUIL, P.AUBERGE, P.MARCHE
AELIS_MU, TEMPLIER, AUBERGISTE, MARCHANDE = P.AELIS_MU, P.TEMPLIER_MU, P.AUBERGISTE, P.MARCHANDE
PORTRAIT_AELIS, PORTRAIT_AELIS_DIALOGUE = P.PORTRAIT_AELIS, P.PORTRAIT_AELIS_DIALOGUE

# ── Lieux neufs ──
OUVRAGES = "lieu:ouvrages_de_la_peripherie"
CONDUITES = "lieu:conduites_de_la_lisiere"
JARDINS = "lieu:jardins_de_la_paroi"
LISIERE = "lieu:lisiere_des_jardins"
SAS = "lieu:sas_des_jardiniers"
INSTITUT = "lieu:institut_de_mu"
ATELIER = "lieu:atelier_du_souffleur_de_vasques"
RESEAU = "lieu:reseau_ancien_de_mu"
CHAMBRE = "lieu:chambre_du_sceau"
ANTRE = "lieu:antre_d_echidna"
COMBAT_ANTRE = "lieu:combat_de_l_antre_d_echidna"
QUAI = "lieu:quai_des_pecheurs_de_mu"
SANCTUAIRE = "lieu:sanctuaire_noye_de_tangaroa"
DEPOT = "lieu:depot_de_maintenance_condamne"
CHAMBRE_HYDRAULIQUE = "lieu:chambre_hydraulique_oubliee"
STRUCTURE = "lieu:chambre_exterieure_de_la_structure"
CARTES = "lieu:salle_des_cartes_de_mu"
RELEVES = "lieu:ancienne_salle_des_releves"
PORTE_CONDAMNEE = "lieu:porte_condamnee_de_la_sentinelle"
RESERVE = "lieu:reserve_des_registres_de_mu"

# Portes sur la carte de Mu-la-Centrale (88 × 48), cases praticables relues sur la grille du dump du
# 26/11 et reliées au seuil (vérifié par `_portes_praticables`).
PORTES_MU = {
	OUVRAGES: (26, 25), JARDINS: (24, 32), INSTITUT: (44, 20), ATELIER: (50, 24), QUAI: (64, 30),
	DEPOT: (36, 22), CHAMBRE_HYDRAULIQUE: (60, 33), CARTES: (40, 30), PORTE_CONDAMNEE: (48, 37),
}

# ── Quêtes ──
Q_EAUX = "quete:eaux_troubles_de_mu"
Q_SERVICE = "quete:service_qui_ne_peut_attendre"
Q_CONFIANCE = "quete:confiance_qui_se_merite"
Q_DESCENTE = "quete:la_descente_de_mu"
Q_PAROLE = "quete:la_mere_des_serpents"
Q_CHANT = "quete:chant_sous_les_ruines"
Q_MARCHAND = "quete:marchand_qui_vend_le_passe"
Q_ENFANTS = "quete:enfants_de_la_maree"
Q_POISSONS = "quete:eaux_sans_poissons"
Q_CARTOGRAPHES = "quete:cartographes_qui_ne_dessinent_plus"
Q_GARDIEN = "quete:dernier_gardien_de_mu"
Q_NOM = "quete:nom_efface"
QUETES = (Q_EAUX, Q_SERVICE, Q_CONFIANCE, Q_DESCENTE, Q_PAROLE, Q_CHANT, Q_MARCHAND, Q_ENFANTS,
		  Q_POISSONS, Q_CARTOGRAPHES, Q_GARDIEN, Q_NOM)

# ── Objets ──
NAGA = "item:naga"                          # butin de l'espèce (gen_monstres_mu)
PIECE_SAS = "item:piece_de_sas"
REGISTRE = "item:registre_du_souffleur_de_vasques"
ECAILLE = "item:ecaille_d_echidna"
COPIE_RELEVE = "item:copie_partielle_du_releve_des_seuils"
FRAGMENTS_CHANT = "item:estampage_des_fragments_du_chant"
INVENTAIRE_DEPOT = "item:inventaire_du_depot_de_maintenance"
TABLETTE = "item:tablette_des_bassins"
RELEVE_COURANTS = "item:releve_des_courants_de_la_structure"
CARTE_INCERTAINE = "item:carte_des_zones_incertaines"
PLAQUE_ARCHIVE = "item:plaque_de_l_archive_de_la_sentinelle"
RAPPORT = "item:copie_fidele_du_dernier_rapport"

# ── PNJ neufs ──
RANGI = "pnj:rangi_waiora"
NGAIO = "pnj:ngaio_jardiniere"
TAMA = "pnj:tama_teriitahi"
ANA = "pnj:ana_hereheretue"
KORO = "pnj:koro_hapai_souffleur"
MAHINA = "pnj:mahina_rehu"
MAHINA_BASSIN = "pnj:mahina_rehu_bassin"
RAWIRI = "pnj:rawiri_tane"
RAWIRI_SANCTUAIRE = "pnj:rawiri_tane_sanctuaire"
MERE = "pnj:mere_tapuni"
HINE = "pnj:hine_matarau"
ATAAHUA = "pnj:ataahua_paora"
TANE = "pnj:tane_moerai"
PIRIPI = "pnj:piripi_ngata"
TAMATOA = "pnj:tamatoa_paepae"
NGAIRE = "pnj:ngaire_koroneho"
NGAIRE_STRUCTURE = "pnj:ngaire_koroneho_structure"
TE_RANGI = "pnj:te_rangi_huatahi"
KAURI = "pnj:kauri_tipene"
ROIMATA = "pnj:roimata_apprentie"
WIREMU = "pnj:wiremu_cartographe"
SENTINELLE = "pnj:sentinelle_de_la_porte_condamnee"
HUIA = "pnj:huia_ruawai"
ECHIDNA = "pnj:echidna"
AELIS_DESCENTE = "pnj:aelis_de_montfaucon_descente"      # sa voix pendant la descente (`voix_protege`)
AELIS_SCEAU = "pnj:aelis_de_montfaucon_sceau"
AELIS_ANTRE = "pnj:aelis_de_montfaucon_antre"

# ── Énigmes ──
E_SOUFFLEUR = "enigme:atelier_du_souffleur"
E_VANNES = "enigme:vannes_du_reseau_ancien"
E_SCELLEMENT = "enigme:scellement_de_la_porte"
E_CHANT = "enigme:fragments_du_chant"
E_DEPOT = "enigme:depot_de_maintenance"
E_BASSIN = "enigme:mots_des_enfants"
E_COURANTS = "enigme:courants_de_la_structure"
E_RELEVES = "enigme:reperes_de_la_pierre"
E_RITE = "enigme:rite_de_la_sentinelle"
E_REGISTRES = "enigme:registres_grattes"

# ── Espèces, donjons ──
E_NAGA, E_MURENE, E_ECHIDNA = "espece:naga", "espece:murene_geante", "espece:echidna"
D_CONDUITES, D_LISIERE, D_ANTRE = "donjon:conduites_de_la_lisiere", "donjon:lisiere_des_jardins", "donjon:antre_d_echidna"
# Cartes de combat PROVISOIRES : image, dimensions, cases et murs d'une salle existante, en attendant
# celles de l'Auteur (prompts dans la séance) — couloirs humides, eau courante, salle qui sent la mer.
CARTES_PROVISOIRES = {CONDUITES: "lieu:catacombes0001", LISIERE: "lieu:petra_donjon_crue",
					  COMBAT_ANTRE: "lieu:salle_de_l_arche_eteinte"}

# ── Images à livrer (Auteur) ──
IMG = {
	OUVRAGES: "ouvrages_de_la_peripherie01.jpg", JARDINS: "jardins_de_la_paroi01.jpg",
	SAS: "sas_des_jardiniers01.jpg", INSTITUT: "institut_de_mu01.jpg", ATELIER: "atelier_du_souffleur01.jpg",
	RESEAU: "reseau_ancien_de_mu01.jpg", CHAMBRE: "chambre_du_sceau01.jpg", ANTRE: "antre_d_echidna01.jpg",
	QUAI: "quai_des_pecheurs_de_mu01.jpg", SANCTUAIRE: "sanctuaire_noye_de_tangaroa01.jpg",
	DEPOT: "depot_de_maintenance01.jpg", CHAMBRE_HYDRAULIQUE: "chambre_hydraulique01.jpg",
	STRUCTURE: "chambre_exterieure_de_la_structure01.jpg", CARTES: "salle_des_cartes_de_mu01.jpg",
	RELEVES: "ancienne_salle_des_releves01.jpg", PORTE_CONDAMNEE: "porte_condamnee01.jpg",
	RESERVE: "reserve_des_registres01.jpg",
}
PORTRAITS = {
	RANGI: "technicien_nain_m_ouvrages_de_mu01.jpg", NGAIO: "jardiniere_hobbit_f_jardins_de_mu01.jpg",
	TAMA: "jardinier_nain_m_tama01.jpg", ANA: "architecte_elfe_f_institut_de_mu01.jpg",
	KORO: "souffleur_ogre_m_atelier_de_mu01.jpg", MAHINA: "linguiste_humain_f_institut_de_mu01.jpg",
	RAWIRI: "archiviste_hobbit_m_institut_de_mu01.jpg", MERE: "restauratrice_ogre_f_institut_de_mu01.jpg",
	HINE: "chanteuse_humain_f_fare_des_marees01.jpg", ATAAHUA: "soigneuse_elfe_f_fare_des_marees01.jpg",
	TANE: "marchand_nain_m_marche_du_dome01.jpg", PIRIPI: "intermediaire_humain_m_depot_de_mu01.jpg",
	TAMATOA: "pecheur_ogre_m_quai_de_mu01.jpg", NGAIRE: "naturaliste_hobbit_f_quai_de_mu01.jpg",
	TE_RANGI: "officiant_elfe_m_quai_de_mu01.jpg", KAURI: "cartographe_humain_m_salle_des_cartes01.jpg",
	ROIMATA: "apprentie_hobbit_f_salle_des_cartes01.jpg", WIREMU: "cartographe_nain_m_salle_des_releves01.jpg",
	SENTINELLE: "sentinelle_porte_condamnee01.jpg", HUIA: "descendante_elfe_f_reserve_de_mu01.jpg",
	ECHIDNA: "echidna_antre01.jpg",
}
PORTRAITS[MAHINA_BASSIN] = PORTRAITS[MAHINA]
PORTRAITS[RAWIRI_SANCTUAIRE] = PORTRAITS[RAWIRI]
PORTRAITS[NGAIRE_STRUCTURE] = PORTRAITS[NGAIRE]


# ---------------------------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------------------------

def avant(q):
	return {"quete_active": {"id": q, "attendu": False}, "quete_reussie": {"id": q, "attendu": False}}


def pendant(q):
	return {"quete_active": {"id": q}}


def apres(q):
	return {"quete_reussie": {"id": q}}


def apport_actif(item, attendu=True):
	"""Clause d'ACCÈS (le vocabulaire des barrières ne nomme pas les quêtes par id) : un apport de
	cet objet est en cours."""
	f = {"types": ["collect"], "cible": item}
	if not attendu:
		f["attendu"] = False
	return {"quete_active": f}


def escorte_active(destination, attendu=True):
	f = {"types": ["escorte"], "cible": destination}
	if not attendu:
		f["attendu"] = False
	return {"quete_active": f}


def ouvert_pour(clause_active, q):
	"""Lieu d'une affaire : ouvert pendant la quête, et après (on y revient voir ce qui a changé)."""
	return {"ou": [clause_active, {"quete_reussie": {"id": q}}]}


# ---------------------------------------------------------------------------------------------
# Constructeurs communs
# ---------------------------------------------------------------------------------------------

def lieu(id_, label, texte, categorie="chemin", parent=MU, acces=None, pnj=None, image=None):
	d = {"_id": id_, "type": "lieu", "label": label, "image": image or IMG[id_], "categorie": categorie,
		 "lieu_parent": parent, "texte": texte}
	if acces:
		d["acces"] = acces
	if pnj:
		d["pnj"] = pnj
	return d


def lien(a, pos_a, label_a, b, label_b, type_="chemin", pos_b=(0, 0)):
	slug = lambda x: x.split(":", 1)[1]  # noqa: E731
	return {"_id": f"link:{slug(b)}_to_{slug(a)}", "type": "connection",
			"nodes": [{"lieu": a, "pos": list(pos_a), "label": label_a},
					  {"lieu": b, "pos": list(pos_b), "label": label_b}],
			"metadata": {"type": type_, "status": "ouvert"}}


def present(pid, nom, description, conditions=None):
	return entree_pnj(pid, nom, PORTRAITS.get(pid, PORTRAIT_AELIS_DIALOGUE), description, conditions or [])


def item_quete(id_, nom, description, icon="📜", poids=0.2, categorie="document", sous_categorie=""):
	return {"_id": id_, "type": "item", "nom": nom, "sous_categorie": sous_categorie, "icon": icon,
			"description": description, "rarete": "rare", "categorie": categorie, "slots": [],
			"poids": poids, "tags": ["quete", "mu"]}


def offre_apport(q, titre, description, item, xp, cuivre):
	return {"id": q, "titre": titre, "description": description, "item": item, "quantite": 1,
			"unique": True, "recompenses": {"xp": xp, "cuivre": cuivre}}


def donneur(pid, nom, race, description, vocation, offre, prerequis, textes, issues, extra_accueil=(),
			extra_noeuds=None, services=None):
	"""PNJ qui CONFIE et REÇOIT un apport (modèle Borin / Morvan), dans ses trois états.
	`textes` : accueil, propose, accepte, rappel, partiel, remis, souvenir, et `offre_label`.
	`issues` : [(id, réplique, réponse)] — trois façons de conclure, PARLÉES (rien n'est mémorisé)."""
	q = offre["id"]
	noeuds = {
		"accueil": noeud(
			textes["accueil"],
			choix("offre", textes["offre_label"], "propose", condition=dict(prerequis, apport_offert=True)),
			choix("rappel", "« Où en étions-nous ? »", "rappel",
				  condition={"apport_en_cours": True, "apport_possible": False}),
			choix("remettre", textes.get("remettre_label", "Lui remettre ce que vous rapportez."),
				  condition={"apport_possible": True}, action={"service": "apport", "op": "remettre"}),
			choix("souvenir", textes.get("souvenir_label", "« Et depuis ? »"), "souvenir", condition=apres(q)),
			*extra_accueil,
			choix("fin", "(Prendre congé.)", "fin")),
		"propose": noeud(
			textes["propose"],
			choix("accepter", textes.get("accepter_label", "« Je m'en occupe. »"),
				  action={"service": "apport", "op": "accepter"}),
			choix("plus_tard", "« Pas maintenant. »", "fin")),
		"accepte": noeud(textes["accepte"], choix("route", "« J'y vais. »", "fin")),
		"rappel": noeud(textes["rappel"], choix("ok", "Revenir.", "accueil")),
		"partiel": noeud(textes.get("partiel", textes["rappel"]), choix("ok", "Revenir.", "accueil")),
		"remis": noeud(textes["remis"], *[choix(i, rep, f"issue_{i}") for i, rep, _ in issues]),
		"souvenir": noeud(textes["souvenir"], choix("ok", "Revenir.", "accueil")),
	}
	for i, _, reponse in issues:
		noeuds[f"issue_{i}"] = noeud(reponse, choix("fin", "(Prendre congé.)", "fin"))
	noeuds.update(extra_noeuds or {})
	serv = {"apport": {"offre": offre, "noeuds": {"accepte": "accepte", "partiel": "partiel", "remis": "remis"}}}
	serv.update(services or {})
	return pnj_doc(pid, nom, race, description, PORTRAITS[pid], noeuds, vocation=vocation, services=serv)


def remettant(pid, nom, race, description, vocation, q, item, enigme_id, textes, trop_lourd=None):
	"""PNJ du lieu d'une affaire qui REMET la preuve une fois l'énigme résolue (modèle Jacotte) : `don`
	unique compté sur tout le groupe, revenu si l'objet est perdu, la quête toujours en cours."""
	noeuds = {
		"accueil": noeud(
			textes["accueil"],
			choix("regarder", textes["regarder_label"], "fin", condition={"quete_active": {"id": q},
																	"enigme_resolue": {"id": enigme_id, "attendu": False}},
				  enigme=enigme_id),
			choix("prendre", textes["prendre_label"],
				  condition={"quete_active": {"id": q}, "enigme_resolue": {"id": enigme_id}, "don_recu": False},
				  action={"service": "don"}),
			choix("apres", textes.get("apres_label", "« Et maintenant ? »"), "apres", condition=apres(q)),
			choix("fin", "(Le laisser.)", "fin")),
		"donne": noeud(textes["donne"], choix("fin", "(Repartir.)", "fin")),
		"trop_lourd": noeud(trop_lourd or "« Vous ne porterez rien de plus. Allégez-vous. »",
							choix("fin", "(Repartir.)", "fin")),
		"apres": noeud(textes["apres"], choix("ok", "Revenir.", "accueil")),
	}
	return pnj_doc(pid, nom, race, description, PORTRAITS[pid], noeuds, vocation=vocation,
				   services={"don": {"item": item, "quantite": 1, "cout_cuivre": 0, "unique": True,
									 "unique_porteurs": True,
									 "noeuds": {"fait": "donne", "sans_fonds": "donne", "trop_charge": "trop_lourd"}}})


def temoin(pid, nom, race, description, vocation, accueil, repliques):
	"""PNJ sans service : `repliques` = [(id, label, condition, texte)] — un AVANT, un PENDANT et un
	APRÈS par quête qui le touche (ou une réplique libre, condition None)."""
	noeuds = {"accueil": noeud(accueil, *[choix(i, lab, i, **({"condition": c} if c else {}))
										  for i, lab, c, _ in repliques],
							   choix("fin", "(Prendre congé.)", "fin"))}
	for i, _, _, texte in repliques:
		noeuds[i] = noeud(texte, choix("ok", "Revenir.", "accueil"))
	return pnj_doc(pid, nom, race, description, PORTRAITS[pid], noeuds, vocation=vocation)


def enigme(id_, nom, famille, lieu_id, texte, elements, solution, reussite, echec, commentaires,
		   conditions, prerequis=None):
	return V.enigme(id_, nom, famille, lieu_id, texte, elements, solution, reussite, echec, commentaires,
					prerequis=prerequis, conditions=conditions)


def salle(id_, label, source, tags, acces):
	src = source
	d = {"_id": id_, "type": "lieu", "label": label, "image": src["image"], "categorie": "battle_map",
		 "dimensions": copy.deepcopy(src["dimensions"]), "cells": copy.deepcopy(src["cells"]),
		 "tags": tags, "acces": acces}
	if src.get("nav"):
		d["nav"] = copy.deepcopy(src["nav"])
	return d


def donjon(id_, nom, description, portail, salle_id, compo, nmin, nmax, musique="Ambience_Cave_00.mp3"):
	return {"_id": id_, "type": "donjon", "nom": nom, "description": description, "portail": portail,
			"niveau_min": nmin, "niveau_max": nmax, "musique": musique, "musique_volume": 0.45,
			"battle_maps": [{"lieu": salle_id, "especes": list(compo), "composition": compo,
							 "niveau_min": nmin, "niveau_max": nmax}]}


# ---------------------------------------------------------------------------------------------
# 1. Les eaux troubles de Mu — Rangi Waiora, les conduites de la lisière
# ---------------------------------------------------------------------------------------------
# Mesuré (`potentiel.potentiel_menace`, dump du 26/11) : Naga ≈ 140 vétéran, ≈ 197 champion → rang B
# chacun ; trois ensemble dépassent le plancher A (250).

def quete_eaux(par_id):
	offre = offre_apport(
		Q_EAUX, "Les eaux troubles de Mu",
		"Dans les conduites d'eau de la lisière, des grilles sont arrachées et des vannes forcées. Rangi "
		"Waiora, responsable des ouvrages de la périphérie, croit à une intrusion. Descendez dans les "
		"conduites et rapportez-lui de quoi savoir qui force ses grilles.",
		NAGA, 250, 2500)
	rangi = donneur(
		RANGI, "Rangi Waiora", "nain", "Responsable des ouvrages hydrauliques de la périphérie de Mu.", "guerrier",
		offre, AU_MU,
		{"accueil": "Un nain trapu, les avant-bras gris de vase séchée, penché sur un plan de conduites "
					"épinglé à même la pierre. Il lève les yeux, vous jauge, et ne pose pas son crayon. "
					"Autour de lui, des clés à vanne, des grilles tordues, et le bruit de l'eau partout.",
		 "offre_label": "« Des grilles tordues ? »",
		 "propose": "« Arrachées. Pas tordues : arrachées, de dehors vers dedans. » Il tapote le plan. "
					"« Trois conduites de la lisière, en trois nuits. Des vannes forcées à la main, et "
					"pas par une main d'ici. Mes gars ne descendent plus. » Il vous regarde enfin. « Les "
					"aventuriers, je ne les aime pas. Ils cassent, ils crient, ils repartent. Mais vous "
					"êtes là. Descendez, voyez qui c'est, et rapportez-moi de quoi le prouver. »",
		 "accepter_label": "« Je descends. »",
		 "accepte": "« L'entrée est derrière moi. Ça monte et ça baisse avec la marée de la bulle : ne "
					"restez pas dans les conduites basses quand l'eau chante. » Il retourne à son plan. "
					"« Et ne touchez pas à mes vannes. »",
		 "rappel": "« Les conduites de la lisière, derrière moi. Qui force mes grilles, et la preuve. »",
		 "remettre_label": "Poser devant lui la dépouille d'un Naga.",
		 "remis": "Rangi recule d'un pas devant les écailles vert d'eau. « Des Naga. Ici. » Il s'accroupit, "
				  "soulève un pan de capuchon avec le bout de sa clé. « Ils ne s'en prenaient à personne, "
				  "pas vrai ? Ils ont arraché mes grilles et forcé mes vannes, et pas un de mes gars n'a "
				  "été touché. » Il se relève. « Ils cherchaient un passage. Vers le dessous. Qu'est-ce "
				  "que vous voulez que j'en fasse, de ce passage ? »",
		 "souvenir": "« Les conduites tiennent. » Il ne lève pas les yeux de son plan. « Mes gars "
					 "redescendent. Les Naga, on n'en a pas revu. Ce qu'ils cherchaient sous la cité, "
					 "je préfère ne pas le savoir. Vous, vous avez l'air de vouloir le savoir. »"},
		[("condamner", "« Condamnez l'accès. Muré, scellé. »",
		  "« Muré, scellé. C'est ce que j'aurais fait sans vous. » Il hoche la tête. « Ça tiendra. Rien "
		  "n'entre, rien ne sort. Et si ce qu'ils cherchaient a besoin d'eux, il attendra. »"),
		 ("securiser", "« Sécurisez-le sans le fermer. »",
		  "Il fronce les sourcils, puis acquiesce. « Une grille neuve, qui s'ouvre de dedans. On saura "
		  "qui passe. » Il griffonne sur son plan. « Vous n'êtes pas si bête, pour une aventurière. Ou "
		  "un aventurier. Je ne fais pas la différence, sous la vase. »"),
		 ("signaler", "« Gardez les preuves. C'est une intrusion organisée : il faut le dire plus haut. »",
		  "« Plus haut. » Il soupire. « Les Templiers voudront murer, l'Institut voudra étudier, et "
		  "moi je voudrai dormir. » Il emballe une écaille dans un chiffon. « Je le dirai. Avec votre "
		  "nom. Ici, ça ne se fait pas pour n'importe qui. »")],
		extra_accueil=(
			choix("conduites", "Descendre dans les conduites.", condition={"acces_ouvrable": True},
				  action={"service": "acces", "op": "passer"}),
			choix("service", "« L'équipe des jardiniers n'est pas remontée. »", "service",
				  condition=pendant(Q_SERVICE)),
			choix("descente", "« L'eau ne suit plus son cours, dit Aélis. »", "descente",
				  condition=pendant(Q_DESCENTE)),
			choix("gardien", "« La sentinelle de la porte condamnée… »", "gardien", condition=pendant(Q_GARDIEN)),
		),
		extra_noeuds={
			"conduites_ouvertes": noeud(
				"L'eau vous monte aux genoux dès la première marche. Plus loin, dans le noir, quelque chose "
				"ondule contre le courant, sans bruit, et s'arrête quand vous vous arrêtez.",
				choix("arme", "Tirer votre arme.", "fin")),
			"conduites_closes": noeud("« Les conduites, c'est mon affaire. Vous n'y descendez pas sans raison. »",
									  choix("ok", "Revenir.", "accueil")),
			"service": noeud(
				"« La lisière cultivée, c'est pas à moi. » Il le dit vite, comme on le répète. « Et la "
				"pièce de leur sas, je ne la prête pas sans un ordre écrit. Kahu Rehua en vend, au marché. "
				"Moi, je n'ai rien dit. »",
				choix("ok", "Revenir.", "accueil")),
			"descente": noeud(
				"« Dans le quartier des citernes, l'eau tourne à l'envers depuis trois jours. Mes plans "
				"ne connaissent pas ce qu'il y a dessous. » Il déroule une feuille plus vieille que lui. "
				"« Ceux-là, si. Le réseau ancien, derrière mes ouvrages. Je vous l'ouvre. Pas plus. »",
				choix("ok", "Revenir.", "accueil")),
			"gardien": noeud(
				"« Elle bouffe du mana pour garder une porte que personne n'ouvre. » Il hausse les épaules. "
				"« On tarit son flux, on reprend la place, on y met une citerne. La linguiste veut lui "
				"parler. Parler à une pierre. »",
				choix("ok", "Revenir.", "accueil")),
		},
		services={"acces": {"lieu": CONDUITES, "noeuds": {"ouvre": "conduites_ouvertes", "refus": "conduites_closes"}}})
	# Boucle tant que la preuve n'est pas remise (modèle Morvan) : sans `combat_gagne`, une dépouille
	# perdue au sol ne bloque pas la quête.
	conduites = salle(CONDUITES, "Les conduites de la lisière", par_id[CARTES_PROVISOIRES[CONDUITES]],
					  ["sous-terrain", "donjon", "couvert", "humide", "eau"],
					  {"gardien": RANGI, "cycle": 1, "refus": "Une grille fermée, et l'eau derrière.",
					   "conditions": [{"quete_active": {"types": ["collect"], "cible": NAGA, "objectif_atteint": False}}]})
	d = donjon(D_CONDUITES, "Les conduites de la lisière",
			   "Les conduites d'eau de la périphérie de Mu, contre la paroi de la bulle, où des Naga forcent les grilles.",
			   OUVRAGES, CONDUITES, {E_NAGA: 3}, 3, 4)
	return [rangi, conduites, d]


# ---------------------------------------------------------------------------------------------
# 2. Un service qui ne peut attendre — Moana, Tama, la lisière des jardins
# ---------------------------------------------------------------------------------------------
# Mesuré : murène géante ≈ 176 champion, ≈ 184 héros → rang B ; deux ensemble passent le plancher A.

def offre_service():
	return {
		"id": Q_SERVICE, "titre": "Un service qui ne peut attendre",
		"description": "Une équipe de jardiniers de la lisière n'est pas remontée depuis la veille, et "
					   "personne à Mu ne s'en dit responsable. Moana Teriitahi, l'aubergiste du fare des "
					   "Marées, vous demande d'aller chercher son neveu Tama au sas des jardiniers, contre "
					   "la paroi de la bulle, et de le ramener vivant au fare.",
		"destination": AUBERGE, "rencontre": {"lieu": SAS},
		"proteges": [{"prenom": "Tama", "nom": "Teriitahi", "race": "nain", "sex": "M", "image": PORTRAITS[TAMA],
					  "description": "Jardinier de la lisière, neveu de Moana. Il rêve d'une ville sous un "
									 "soleil impossible, et ne s'en vante pas. Il ne sait pas se battre."}],
		"unique": True, "proba": 1, "recompenses": {"xp": 200, "cuivre": 2000},
	}


def moana(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	doc.setdefault("services", {})["escorte"] = {"offre": offre_service(), "noeuds": {"accepte": "service_accepte"}}
	ajouter_choix(doc, "accueil", [
		choix("service_offre", "« Vous avez l'air inquiète. »", "service_01",
			  condition=dict(avant(Q_SERVICE), escorte_offerte=True, quete_reussie={"id": Q_EAUX})),
		choix("service_relance", "« Tama ? »", "service_relance", condition=pendant(Q_SERVICE)),
		choix("service_souvenir", "« Tama va bien ? »", "service_souvenir", condition=apres(Q_SERVICE)),
		choix("confiance_secret", "« On parle de corail, au fare ? »", "confiance_secret",
			  condition=pendant(Q_CONFIANCE)),
	], en_tete=True)
	n["service_01"] = noeud(
		"Moana essuie le même verre pour la troisième fois. « L'équipe de la lisière n'est pas remontée. "
		"Depuis hier. » Elle repose le verre. « Les techniciens disent que les jardins ne sont pas à eux. "
		"Les Templiers, qu'ils sont hors de la cité. L'Institut n'a pas d'avis. Mon neveu est dedans. »",
		choix("service_02", "« Pourquoi moi ? »", "service_02"))
	n["service_02"] = noeud(
		"« Je ne vous aime pas plus que les autres. » Elle le dit sans méchanceté. « Mais vous, au moins, "
		"personne ne vous reprochera d'y être allé. Vous n'êtes à personne, ici. » Elle vous regarde "
		"enfin. « Le sas des jardiniers, au bout des jardins de la paroi. Ramenez-moi Tama. »",
		choix("service_ok", "« Je le ramène. »", action={"service": "escorte", "op": "accepter"}),
		choix("service_non", "« Pas maintenant. »", "fin"))
	n["service_accepte"] = noeud(
		"« Les jardins sont au bout du quai, à l'ouest, là où l'or du dôme tourne au vert. Ngaio y "
		"travaille : elle vous dira où frapper, et où ne pas frapper. » Elle hésite. « Il y a des bêtes, "
		"dans les failles. Elles aiment le bruit. »",
		choix("service_route", "« J'y vais. »", "fin"))
	n["service_relance"] = noeud(
		"« Au sas des jardiniers. Ramenez-le ici. » Elle ne vous sert rien d'autre.",
		choix("accueil", "Revenir.", "accueil"))
	n["service_souvenir"] = noeud(
		"« Il dort mal, mais il dort ici. » Elle pose devant vous un bol que vous n'avez pas commandé. "
		"« Le repas du soir est pour vous. Et je ne vous sers plus en dernier. N'en parlez pas aux autres "
		"invités. »",
		choix("accueil", "Revenir.", "accueil"))
	n["confiance_secret"] = noeud(
		"Moana baisse la voix. « On dit que l'Institut perd des branches. Vous travaillez pour eux, "
		"maintenant. Vous savez quelque chose ? »",
		choix("taire", "« Rien que je puisse dire. »", "confiance_tu"),
		choix("dire", "« Un apprenti, peut-être. »", "confiance_dit"))
	n["confiance_tu"] = noeud("Elle hausse les épaules, et pour la première fois, elle a l'air satisfaite de vous.",
							  choix("accueil", "Revenir.", "accueil"))
	n["confiance_dit"] = noeud(
		"« Un apprenti. » Elle le répète comme on goûte un plat. « Demain, tout le quai le saura. » Elle "
		"retourne à ses verres.",
		choix("accueil", "Revenir.", "accueil"))
	return doc


def kahu(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	vente = doc["services"]["vente"]
	vente["articles"] = [a for a in vente["articles"] if a.get("item") != PIECE_SAS] + [
		{"item": PIECE_SAS, "cout_cuivre": 400}]
	ajouter_choix(doc, "accueil", [
		choix("piece_sas", "« Une pièce de sas, pour les jardiniers ? »", "piece_sas", condition=pendant(Q_SERVICE)),
		choix("confiance_secret", "« Vous avez l'air de vouloir me demander quelque chose. »", "confiance_secret",
			  condition=pendant(Q_CONFIANCE)),
		choix("marchand", "« Le marchand d'à côté, qui vend du vieux… »", "marchand", condition=pendant(Q_MARCHAND)),
	], en_tete=True)
	n["piece_sas"] = noeud(
		"Kahu sort de sous l'étal un anneau de bronze à joint de cuir, et le fait tourner sur un doigt. "
		"« Les techniciens n'en prêtent pas sans papier. Moi, je vends. Quatre cents. »",
		choix("acheter", "Acheter la pièce de sas.", action={"service": "vente", "op": "acheter", "item": PIECE_SAS}),
		choix("accueil", "Revenir.", "accueil"))
	n["confiance_secret"] = noeud(
		"Elle se penche. « On dit que des branches du corail vivant passent par des vasques qui ne sont "
		"pas celles de l'Institut. Un mot, et je vous fais le cristal à moitié prix. »",
		choix("taire", "« Je n'ai rien à vous dire. »", "confiance_tu"),
		choix("dire", "« Un apprenti de l'Institut. »", "confiance_dit"))
	n["confiance_tu"] = noeud("« Dommage. » Elle sourit pourtant. « Les poissons d'en haut ne parlent pas tous. »",
							  choix("accueil", "Revenir.", "accueil"))
	n["confiance_dit"] = noeud(
		"« Un apprenti. » Elle note quelque chose sur une feuille d'algue. « Le rabais, c'était pour rire. »",
		choix("accueil", "Revenir.", "accueil"))
	n["marchand"] = noeud(
		"« Tane ? Il vend ce que la cité a oublié qu'elle avait. » Elle hausse les épaules. « Les gens "
		"achètent. Moi, je ne demande pas d'où vient la nacre. Lui, on devrait. »",
		choix("accueil", "Revenir.", "accueil"))
	return doc


def quete_service(par_id):
	ngaio = pnj_doc(NGAIO, "Ngaio", "hobbit", "Jardinière de la lisière, à Mu.", PORTRAITS[NGAIO], vocation="forestier",
		services={"acces": {"lieu": LISIERE, "noeuds": {"ouvre": "lisiere_ouverte", "refus": "lisiere_close"}}},
		noeuds={
		"accueil": noeud(
			"Une hobbit agenouillée entre deux rangs de fougères d'eau, les mains dans une terre noire et "
			"humide. Au-dessus d'elle, la paroi de la bulle laisse passer une lumière verte et lente.",
			choix("jardins", "« Que cultivez-vous ici ? »", "jardins"),
			choix("equipe", "« L'équipe de Tama ? »", "equipe", condition=pendant(Q_SERVICE)),
			choix("venir", "Aller vers le sas, le long de la faille.", condition={"acces_ouvrable": True},
				  action={"service": "acces", "op": "passer"}),
			choix("apres", "« Les jardins ? »", "apres", condition=apres(Q_SERVICE)),
			choix("fin", "(La laisser travailler.)", "fin")),
		"jardins": noeud(
			"« Ce qui pousse sans soleil. Les algues, les fougères d'eau, les racines blanches. » Elle "
			"essuie ses mains. « La moitié de ce qu'on mange à Mu vient d'ici. Personne ne le sait, et "
			"c'est bien comme ça. »",
			choix("ok", "Revenir.", "accueil")),
		"equipe": noeud(
			"« Ils sont au sas, au bout de la faille. Ils ont frappé toute la nuit pour qu'on les entende, "
			"et ce sont les murènes qui ont entendu. » Elle baisse la voix. « Deux. Elles gardent la faille, "
			"maintenant. Et le sas est coincé : il faudra une pièce neuve pour le rouvrir. »",
			choix("ok", "Revenir.", "accueil")),
		"lisiere_ouverte": noeud(
			"Le sol devient pierre, puis eau. Dans la faille, deux têtes marbrées se tournent vers vous "
			"ensemble, lentement.",
			choix("arme", "Tirer votre arme.", "fin")),
		"lisiere_close": noeud("« Plus rien ne bouge dans la faille. Le sas est par là. »",
							   choix("ok", "Revenir.", "accueil")),
		"apres": noeud(
			"« On travaille en silence, maintenant. Tama le premier. » Elle sourit à peine. « Il dit que "
			"vous ne regardiez pas la faille, en sortant. Vous regardiez la paroi. »",
			choix("ok", "Revenir.", "accueil")),
	})
	tama = temoin(TAMA, "Tama Teriitahi", "nain", "Jardinier de la lisière, neveu de Moana.", "forestier",
		"Un jeune nain aux mains tachées de vert, attablé seul près du bassin du fare, qui regarde l'eau "
		"plus que les gens.",
		[("merci", "« Ça va mieux ? »", apres(Q_SERVICE),
		  "« Je dors ici, maintenant. Ma tante dit que c'est pour me surveiller. » Il hausse les épaules. "
		  "« Merci. Je ne l'ai pas dit, au sas. »"),
		 ("reve", "« Vous rêvez, m'a-t-on dit ? »", None,
		  "Il rougit. « D'une ville. Sous un soleil qu'on ne peut pas regarder. » Il fredonne trois notes, "
		  "s'arrête. « La vieille Hine chante ça. Je ne l'ai jamais appris. »"),
		 ("chant", "« Le chant de Hine… »", pendant(Q_CHANT),
		  "« Je le connais en entier, ou presque. Il manque un bout, au milieu, là où ça remercie. » Il "
		  "fronce les sourcils. « Une coque d'or. Je ne sais pas ce que c'est. »"),
		 ("chant_apres", "« Vous avez chanté, au sanctuaire. »", apres(Q_CHANT),
		  "« Tout le monde a chanté. » Il sourit. « Je rêve encore. Mais maintenant je sais la fin. »")])
	lisiere = salle(LISIERE, "La lisière des jardins", par_id[CARTES_PROVISOIRES[LISIERE]],
					["donjon", "eau", "humide", "couvert"],
					{"gardien": NGAIO, "cycle": 1, "refus": "La faille est calme.",
					 "conditions": [escorte_active(AUBERGE), {"combat_gagne": {"lieu": LISIERE, "attendu": False}}]})
	jardins = lieu(JARDINS, "Les jardins de la paroi",
		"Des rangs de fougères d'eau et d'algues tendues sur des cadres de corail mort, contre la paroi "
		"dorée de la bulle. La lumière y vire au vert. On y parle bas.",
		pnj=[present(NGAIO, "Ngaio", "Une hobbit agenouillée dans les fougères d'eau, qui ne lève pas la tête au bruit.")])
	sas = lieu(SAS, "Le sas des jardiniers",
		"Une porte ronde de bronze contre la paroi, et derrière, une salle basse où une équipe de jardiniers "
		"attend, assise sur ses paniers, dans une poche d'air qui sent le sel.",
		acces={"cycle": 1, "refus": "Le sas est coincé. Il faut une pièce neuve, et la faille doit être tranquille.",
			   "conditions": [escorte_active(AUBERGE), {"combat_gagne": {"lieu": LISIERE}}, {"item": {"item": PIECE_SAS}}]})
	d = donjon(D_LISIERE, "La lisière des jardins",
			   "La faille contre la paroi de la bulle, au bout des jardins, où deux murènes géantes ont répondu aux coups.",
			   JARDINS, LISIERE, {E_MURENE: 2}, 4, 5)
	liens = [lien(JARDINS, (0, 0), "Revenir dans les jardins", SAS, "Ouvrir le sas des jardiniers")]
	return [ngaio, tama, lisiere, jardins, sas, d] + liens


# ---------------------------------------------------------------------------------------------
# 3. Une confiance qui se mérite — Ana Hereheretue, l'atelier du souffleur
# ---------------------------------------------------------------------------------------------

def quete_confiance():
	offre = offre_apport(
		Q_CONFIANCE, "Une confiance qui se mérite",
		"Dans les bassins de l'Institut, le corail de mana abyssal est sous rāhui : nul n'y récolte, et le "
		"bassin est tapu pour qui n'est pas Architecte. Des branches vivantes disparaissent pourtant. Ana "
		"Hereheretue vous demande de trouver qui, sans entrer dans le bassin et sans en parler à personne, "
		"et de lui en rapporter la preuve.",
		REGISTRE, 250, 3000)
	ana = donneur(
		ANA, "Ana Hereheretue", "elfe", "Architecte de l'Institut de Mu, sous qui travaille Aélis.", "mage",
		offre, apres(Q_SERVICE),
		{"accueil": "Une elfe aux cheveux tressés de fils de nacre, debout devant une vasque où pousse une "
					"branche de corail jaune. Elle parle à Aélis, puis se tait en vous voyant, et vous "
					"regarde comme on mesure une porte.",
		 "offre_label": "« Aélis m'a dit que vous vouliez me voir. »",
		 "propose": "« Dans nos bassins, le corail est sous rāhui. Personne n'y récolte, le temps qu'il se "
					"refasse, et le bassin est tapu pour qui n'est pas Architecte. » Elle effleure la vasque. "
					"« Des branches vivantes disparaissent. Je veux savoir qui. Deux consignes : vous "
					"n'entrez pas dans le bassin, et vous n'en parlez à personne. Pas même à Aélis. » Un "
					"temps. « Je ne vous demande pas d'être fort. Je vous demande de ne pas entrer, et de "
					"vous taire. Ici, c'est plus rare. »",
		 "accepter_label": "« Je n'entrerai pas, et je me tairai. »",
		 "accepte": "« Un corail vivant ne quitte Mu que dans une vasque d'eau des abysses. Les vasques, on "
					"les souffle à l'atelier de Koro Hapai, près du marché. Commencez par là. » Elle se "
					"retourne vers sa branche. « Et rappelez-vous les consignes. »",
		 "rappel": "« Les vasques, l'atelier de Koro Hapai. Pas le bassin. Pas un mot. »",
		 "remettre_label": "Lui tendre le registre du souffleur.",
		 "remis": "Ana feuillette le registre jusqu'à une commande passée au nom de l'Institut, d'une main "
				  "qu'elle reconnaît. Elle ferme les yeux. « Hemo. Mon apprenti. » Elle referme le registre. "
				  "« Ses acheteurs sont déjà repartis par Notre-Dame, j'imagine. Moins on parle de Mu, plus "
				  "les guildes d'en haut s'y intéressent. » Elle vous regarde. « Que feriez-vous de lui ? »",
		 "souvenir": "« Les bassins se refont. » Elle vous désigne une porte que vous n'aviez pas remarquée. "
					 "« Les salles extérieures de l'Institut vous sont ouvertes, et les techniciens "
					 "écouteront votre nom. Je vous recommanderai, le jour où l'eau cessera de suivre son "
					 "cours. Ici, c'est toujours un jour comme celui-là qui finit par venir. »"},
		[("institut", "« Jugez-le au sein de l'Institut. »",
		  "« C'est notre affaire, et nous la réglerons. » Elle range le registre dans une niche. « Il ne "
		  "soufflera plus de vasques. Il apprendra à les entretenir. C'est plus long. »"),
		 ("templiers", "« Livrez-le aux Templiers de Mu. »",
		  "Elle se raidit. « Hemi Taurua en sera ravi. Les Templiers réclameront un droit de regard sur nos "
		  "bassins, et ils l'auront. » Elle hoche la tête, lentement. « C'est juste. Ce n'est pas "
		  "agréable. »"),
		 ("reparer", "« Qu'il rende les vasques et nomme ses acheteurs. Sans procès. »",
		  "« Sans procès. » Elle y réfléchit. « La filière se tarit, et personne ne sait qu'elle a existé. "
		  "C'est peut-être le plus sage. C'est sûrement le moins juste. » Elle vous regarde autrement. "
		  "« Vous avez tenu les deux consignes. »")],
		extra_accueil=(
			choix("descente", "« Aélis m'emmène sous la cité. »", "descente", condition=pendant(Q_DESCENTE)),
			choix("ecaille", "Lui tendre l'écaille d'Échidna.", condition={"transport_a_livrer": True},
				  action={"service": "transport", "op": "livrer"}),
			choix("parole_apres", "« Cerbère… »", "parole_apres", condition=apres(Q_PAROLE)),
			choix("gardien", "« La sentinelle de la porte condamnée ? »", "gardien", condition=pendant(Q_GARDIEN)),
		),
		extra_noeuds={
			"descente": noeud(
				"« Je lui ai dit de ne pas y aller seule. Elle ne m'a pas écoutée, elle vous a pris. C'est "
				"pareil, à peu près. » Elle soupire. « Les Templiers voudront renforcer ce qu'elle "
				"trouvera, quitte à le casser. Elle ne les laissera pas faire. Je ne sais pas qui a "
				"raison. »",
				choix("ok", "Revenir.", "accueil")),
			"ecaille_livree": noeud(
				"Ana prend l'écaille à deux mains, et elle tremble. « Elle vous l'a donnée. À vous. » Elle "
				"rassemble trois Architectes en un souffle. Il faut une nuit pour tenir un passage étroit, "
				"bref, sous la cité, sans rouvrir la porte. Vous y êtes. Par l'interstice, vous voyez une "
				"prairie d'asphodèles sans une ombre, et un trône vide. Puis un grand chien noir à trois "
				"têtes passe, sans un bruit, et le passage se referme. « Il gardait une maison "
				"abandonnée », murmure Ana. « Où sont partis les dieux ? »",
				choix("fin", "(Ne rien répondre.)", "fin")),
			"ecaille_absente": noeud("« Elle vous aurait donné quelque chose. Vous ne l'avez plus ? »",
									 choix("ok", "Revenir.", "accueil")),
			"parole_apres": noeud(
				"« Il est avec elle, sous la cité. La porte est restée close. » Ana regarde sa vasque. « Ce "
				"que ce passage nous coûtera, je n'en sais rien. Ce qui suivra non plus. Aélis dit que les "
				"dieux sont partis. Moi, je dis qu'un trône vide n'est pas une réponse. »",
				choix("ok", "Revenir.", "accueil")),
			"gardien": noeud(
				"« Mahina a raison de vouloir comprendre avant d'éteindre. » Elle hésite. « Les sentinelles "
				"de ce temps-là ne gardaient pas des portes : elles gardaient des réponses. »",
				choix("ok", "Revenir.", "accueil")),
		},
		services={"transport": {"noeuds": {"livre": "ecaille_livree", "incomplet": "ecaille_absente"}}})
	koro = remettant(
		KORO, "Koro Hapai", "ogre", "Souffleur de vasques, près du marché du Dôme.", "guerrier", Q_CONFIANCE, REGISTRE,
		E_SOUFFLEUR,
		{"accueil": "Un ogre immense penché sur un four où chauffe une boule de verre d'eau, qu'il tourne au "
					"bout d'une canne avec une délicatesse d'enfant. Des vasques vides sèchent sur des "
					"étagères, et une place est vide sur l'une d'elles.",
		 "regarder_label": "« Je peux regarder votre atelier ? »",
		 "prendre_label": "« Votre registre, Koro. Je dois le montrer. »",
		 "donne": "Koro vous tend le registre sans discuter. « Montrez-le à qui doit le voir. Moi, je souffle. "
				  "Je ne demande pas où vont les vasques. J'aurais dû. » Il retourne à son four. « Et "
				  "ne dites pas que c'est moi qui vous l'ai dit. Je n'ai rien dit. »",
		 "apres": "« On me fait signer, maintenant, pour chaque vasque. » Il grogne. « C'est bien. C'est "
				  "lent. Les deux. »"})
	e = enigme(E_SOUFFLEUR, "L'atelier du souffleur", "deduction", ATELIER,
		"Des vasques sèchent sur les étagères, le four ronfle, le registre est ouvert sur l'établi. Koro "
		"souffle sans vous regarder. Quelqu'un vient ici prendre ce qui ne devrait pas sortir.",
		{"indices": [
			{"id": "etagere", "label": "L'étagère des vasques", "fait": "Trois places vides, poussière en rond : trois vasques prises la même semaine."},
			{"id": "registre", "label": "Le registre ouvert", "fait": "Une commande de trois vasques « pour l'Institut », sans le sceau de l'Institut, d'une écriture serrée."},
			{"id": "seau", "label": "Le seau sous l'établi", "fait": "Un seau d'eau des abysses, et au fond, un brin de corail jaune encore vivant."},
			{"id": "four", "label": "Le four", "fait": "Rien que du verre et des cendres. Koro souffle comme il a toujours soufflé."},
			{"id": "bassin", "label": "Le chemin du bassin de l'Institut", "fait": "Le chemin monte vers le bassin tapu. Les consignes sont claires : vous n'y entrez pas."},
		], "conclusions": [
			{"id": "koro", "label": "Koro vend lui-même le corail."},
			{"id": "voleur", "label": "Un voleur entre la nuit dans les bassins de l'Institut."},
			{"id": "institut", "label": "Quelqu'un de l'Institut fait souffler des vasques pour sortir le corail de Mu."},
		]},
		{"conclusion": "institut", "indices": ["etagere", "registre", "seau"], "seuil": 2},
		"Une commande au nom de l'Institut, sans son sceau. Trois vasques. Un brin de corail vivant dans "
		"l'eau des abysses. Celui qui coupe les branches sait les couper, et sait comment les faire sortir.",
		"Ce n'est pas ce que disent les choses que vous avez vues.",
		[compagnon("voleur", "ouverture", "Personne n'entre dans un bassin gardé quand il peut se faire livrer le butin."),
		 compagnon("lettre", "examen:registre", "Une commande sans sceau. Soit c'est un oubli, soit c'est une signature."),
		 compagnon("mage", "examen:seau", "Il vit encore. Il ne vivra pas une heure hors de cette eau."),
		 compagnon("guerrier", "examen:bassin", "On vous a dit de ne pas y aller. On n'y va pas.")],
		[apport_actif(REGISTRE)])
	atelier = lieu(ATELIER, "L'atelier du souffleur de vasques",
		"Un four rond, des cannes de souffleur, des vasques de verre d'eau qui sèchent sur des étagères, et "
		"l'odeur du sel chauffé. On y fabrique les seuls récipients où le corail vivant survit hors de Mu.",
		pnj=[present(KORO, "Koro Hapai", "Un ogre penché sur son four, qui tourne une boule de verre au bout d'une canne.")])
	return [ana, koro, e, atelier]


# ---------------------------------------------------------------------------------------------
# 4. La descente — escorte d'Aélis, réseau ancien → chambre du sceau
# ---------------------------------------------------------------------------------------------

def offre_descente():
	return {
		"id": Q_DESCENTE, "titre": "La descente",
		"description": "Dans un quartier de Mu, l'eau ne suit plus son cours. Aélis a suivi les anomalies "
					   "jusqu'à un réseau plus ancien que les plans, derrière les ouvrages de la "
					   "périphérie : des galeries, des chambres et des bassins de régulation dont on "
					   "comprend mal l'usage. Accompagnez-la jusqu'au fond et ramenez-la vivante. Elle ne "
					   "sait pas se battre.",
		"destination": CHAMBRE,
		"proteges": [{"prenom": "Aélis", "nom": "de Montfaucon", "race": "humain", "sex": "F", "image": PORTRAIT_AELIS,
					  "description": "Architecte de l'Institut, en formation à Mu. Un compas, un carnet, les "
									 "plans de Rangi Waiora. Elle ne sait pas se battre."}],
		"unique": True, "proba": 1, "recompenses": {"xp": 350, "cuivre": 4000},
	}


def aelis_mu(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	doc["services"] = {"escorte": {"offre": offre_descente(), "noeuds": {"accepte": "descente_accepte"}}}
	ajouter_choix(doc, "accueil", [
		choix("descente_offre", "« Vous ne finissez pas ce plan ? »", "descente_01",
			  condition=dict(avant(Q_DESCENTE), escorte_offerte=True, quete_reussie={"id": Q_CONFIANCE})),
		choix("confiance_secret", "« Je ne peux pas vous dire ce que je fais. »", "confiance_secret",
			  condition=pendant(Q_CONFIANCE)),
		choix("echidna_apres", "« Les dieux… »", "dieux", condition={"enigme_resolue": {"id": E_SCELLEMENT}}),
	], en_tete=True)
	n["descente_01"] = noeud(
		"« Parce qu'il ne finit pas. » Elle retourne le carnet vers vous : un quartier de Mu, des flèches "
		"bleues qui tournent en rond. « Dans le quartier des citernes, l'eau ne suit plus son cours depuis "
		"trois jours. Rangi dit que ses plans s'arrêtent là. Les siens. Il a des plans plus vieux, qu'il ne "
		"montre à personne. » Elle referme le carnet. « Il y a un réseau sous la cité, et il bouge. »",
		choix("descente_02", "« Et vous voulez descendre. »", "descente_02"))
	n["descente_02"] = noeud(
		"« Ana dit de ne pas y aller seule. » Elle sourit. « Je n'y vais pas seule. Les Templiers pèsent de "
		"loin, ici : s'ils trouvent avant nous, ils renforceront, et renforcer, chez eux, ça veut dire "
		"casser. Je veux voir avant qu'ils cassent. Vous venez ? »",
		choix("descente_ok", "« Je viens. »", action={"service": "escorte", "op": "accepter"}),
		choix("descente_non", "« Pas encore. »", "fin"))
	n["descente_accepte"] = noeud(
		"Elle range le compas, le carnet, les plans de Rangi. « Aux ouvrages de la périphérie. Rangi nous "
		"ouvre le réseau ancien, et pas plus. Après, c'est à nous de comprendre. »",
		choix("descente_route", "« Aux ouvrages. »", "fin"))
	n["confiance_secret"] = noeud(
		"Aélis lève un sourcil, puis sourit. « Ana vous a demandé de vous taire, et vous vous taisez. » Elle "
		"retourne à son plan, vexée une seconde, pas plus. « Bien. C'est comme ça qu'on gagne sa place, ici. "
		"J'essaie encore. »",
		choix("accueil", "Revenir.", "accueil"))
	n["dieux"] = noeud(
		"Aélis pose son crayon. « Des demeures vides, des maîtres partis, des portes laissées à elles-mêmes. "
		"C'est ce que je crois. » Elle hausse les épaules. « Uannedugga, au siège du confinement, dit qu'ils "
		"ont fui ce qu'ils avaient ouvert. Hemi Taurua, que le sacrifice était juste, dieux ou pas. Et Hine "
		"chante un merci à Tangaroa pour une coque d'or. » Elle sourit. « Je me trompe peut-être. Ça "
		"m'arrive. »",
		choix("accueil", "Revenir.", "accueil"))
	return doc


def lieu_auberge(doc):
	"""Fare des Marées : Aélis s'absente pendant la descente et tant qu'elle étudie le sceau ; Hine,
	Ataahua et Tama (après le sas) y sont."""
	doc = sans_rev(doc)
	absente = [escorte_active(CHAMBRE, attendu=False),
			   {"ou": [{"quete_reussie": {"id": Q_DESCENTE, "attendu": False}}, {"enigme_resolue": {"id": E_SCELLEMENT}}]}]
	for e in doc.get("pnj") or []:
		if e.get("character") == AELIS_MU:
			e["conditions"] = [c for c in e.get("conditions") or [] if c not in absente] + absente
	neufs = {HINE: present(HINE, "Hine Matarau", "Une vieille femme assise près du bassin, qui fredonne sans s'en rendre compte."),
			 ATAAHUA: present(ATAAHUA, "Ataahua Paora", "Une elfe en tablier de soigneuse, qui boit une infusion en surveillant la porte."),
			 TAMA: present(TAMA, "Tama Teriitahi", "Un jeune nain aux mains vertes, seul près du bassin.", [apres(Q_SERVICE)])}
	doc["pnj"] = [e for e in doc.get("pnj") or [] if e.get("character") not in neufs] + list(neufs.values())
	return doc


def lieu_marche(doc):
	doc = sans_rev(doc)
	doc["pnj"] = [e for e in doc.get("pnj") or [] if e.get("character") != TANE] + [
		present(TANE, "Tane Moerai", "Un nain derrière un étal tendu de toile noire, où brillent des objets plus vieux que la cité.")]
	return doc


def lien_auberge(doc):
	"""La porte du fare sur la grille repeinte (gen_partir_pour_mu.POS_AUBERGE)."""
	doc = sans_rev(doc)
	for nd in doc["nodes"]:
		if nd["lieu"] == MU:
			nd["pos"] = list(P.POS_AUBERGE)
	return doc


def hemi(doc):
	doc = sans_rev(doc)
	n = doc["dialogue"]["noeuds"]
	ajouter_choix(doc, "accueil", [
		choix("confiance_secret", "« Vous me regardez beaucoup, ces jours-ci. »", "confiance_secret",
			  condition=pendant(Q_CONFIANCE)),
		choix("descente", "« On descend sous la cité, Aélis et moi. »", "descente", condition=pendant(Q_DESCENTE)),
		choix("sacrifice", "« La porte sous la cité… »", "sacrifice", condition={"enigme_resolue": {"id": E_SCELLEMENT}}),
		choix("nom", "« Un nom gratté des registres. »", "nom", condition=pendant(Q_NOM)),
	], en_tete=True)
	n["confiance_secret"] = noeud(
		"« On vous voit souvent du côté des bassins de l'Institut. » L'ogre ne sourit pas. « Que faites-vous "
		"là-haut, l'étranger ? »",
		choix("taire", "« Je me promène. »", "confiance_tu"),
		choix("dire", "« Une affaire de corail. »", "confiance_dit"))
	n["confiance_tu"] = noeud("Il vous regarde longtemps, puis hoche la tête, une seule fois. « Promenez-vous, alors. »",
							  choix("accueil", "Revenir.", "accueil"))
	n["confiance_dit"] = noeud("« De corail. » Il le note quelque part derrière ses yeux. « Merci de me le dire. »",
							   choix("accueil", "Revenir.", "accueil"))
	n["descente"] = noeud(
		"« Le réseau ancien. » Sa main se crispe sur la roue de pierre. « S'il y a là-dessous ce que je crois, "
		"il faut le renforcer. Le sceller deux fois, et tant pis pour ce qu'on casse. L'architecte dira "
		"non. Elle a tort, et elle le sait peut-être. Ramenez-la. »",
		choix("accueil", "Revenir.", "accueil"))
	n["sacrifice"] = noeud(
		"« Les vieux disent que Mu a donné un continent pour fermer cette porte. Ce n'est qu'un dire. » Il "
		"regarde la vasque de corail. « Si c'est vrai, que les dieux y aient eu part ou non, c'était juste. "
		"Mu vit. Le monde vit. Qui pleure le continent n'a qu'à pleurer, l'étranger : moi, je garde ce qui "
		"reste. »",
		choix("accueil", "Revenir.", "accueil"))
	n["nom"] = noeud(
		"« Il y a des vérités qui auraient perdu Mu, dites au mauvais moment. » L'ogre ne détourne pas les "
		"yeux. « Je ne sais pas de quel nom vous parlez. Si je le savais, je ne vous dirais pas s'il faut "
		"le rendre. »",
		choix("accueil", "Revenir.", "accueil"))
	return doc


def aelis_descente():
	etapes = {
		"ouvrages": {"passages": {"lieu": RESEAU, "max": 0}},
		"vannes": {"passages": {"lieu": RESEAU, "min": 1}, "enigme_resolue": {"id": E_VANNES, "attendu": False}},
		"chambre": {"enigme_resolue": {"id": E_VANNES}},
	}
	doc = pnj_doc(AELIS_DESCENTE, "Aélis de Montfaucon", "humain",
		"Aélis de Montfaucon, architecte de l'Institut, qui descend avec vous sous Mu.",
		PORTRAIT_AELIS_DIALOGUE, vocation="lettre", noeuds={
		"accueil": noeud(
			"Aélis marche à votre hauteur, les plans de Rangi sous le bras, et compte les marches à mi-voix.",
			*[choix(cle, "« Où en sommes-nous ? »", cle, condition=c) for cle, c in etapes.items()],
			choix("fin", "(Reprendre la route.)", "fin")),
		"ouvrages": noeud(
			"« Aux ouvrages de la périphérie, voir Rangi. Le réseau ancien part de derrière ses plans. »",
			choix("ok", "Revenir.", "accueil")),
		"vannes": noeud(
			"« Les bassins de régulation. Trois vannes, et l'eau qui tourne à l'envers. Quelqu'un a laissé "
			"leurs marques sur la margelle. On règle, on ne force pas. »",
			choix("ok", "Revenir.", "accueil")),
		"chambre": noeud(
			"« L'eau repart. Elle descend vers la chambre du fond, celle qui n'est sur aucun plan. Allons "
			"voir ce qui la retenait. »",
			choix("ok", "Revenir.", "accueil")),
	})
	doc["voix_protege"] = {"quete": Q_DESCENTE, "prenom": "Aélis"}
	return doc


def quete_descente():
	vannes = enigme(E_VANNES, "Les vannes des bassins de régulation", "crans", RESEAU,
		"Trois bassins en gradins, reliés par des vannes de pierre à quatre crans, de « fermée » à « grande "
		"ouverte ». Sur la margelle, des marques à demi effacées : une vague au-dessus du premier bassin, "
		"deux au-dessus du deuxième, aucune au-dessus du troisième. L'eau tourne en rond.",
		{"pieces": [
			{"id": "haute", "label": "Vanne du bassin haut", "crans": 4, "depart": 3},
			{"id": "milieu", "label": "Vanne du bassin du milieu", "crans": 4, "depart": 0},
			{"id": "basse", "label": "Vanne du bassin bas", "crans": 4, "depart": 2},
		]},
		# Une vague = entrouverte, deux = mi-ouverte, aucune = fermée : l'eau descend au lieu de tourner.
		{"positions": {"haute": 1, "milieu": 2, "basse": 0}},
		"Les vannes s'enclenchent. L'eau hésite, puis repart dans le bon sens, et descend en chantant vers "
		"une ouverture au fond du dernier bassin, que la vase cachait : un escalier.",
		"L'eau bouillonne, puis reprend sa ronde.",
		[aelis("ouverture", "Les marques sur la margelle. Une vague, deux vagues, rien. Ce sont des réglages."),
		 aelis("echec", "Le bassin bas n'a pas de vague. Il ne doit rien laisser passer."),
		 aelis("reussite", "Je me suis trompée de vanne deux fois. Ne le dites pas à Rangi."),
		 compagnon("forestier", "ouverture", "L'eau tourne parce que quelque chose la retient en bas."),
		 compagnon("guerrier", "echec", "On pourrait casser la vanne. On ne la casse pas, je sais.")],
		[escorte_active(CHAMBRE)])
	scellement = enigme(E_SCELLEMENT, "Le scellement de la porte", "deduction", CHAMBRE,
		"Au fond de la chambre, une porte immense, scellée par un dispositif de pierre et de métal que "
		"personne n'a construit depuis des siècles. Autour, des fresques usées, une inscription, des traces "
		"sur le sol. La porte ne bouge pas. Pourtant, quelque chose pousse.",
		{"indices": [
			{"id": "logements", "label": "Le dispositif du sceau", "fait": "Plusieurs logements vides dans le dispositif. Les pièces n'ont pas été arrachées : on les a retirées, proprement, avec les bons outils."},
			{"id": "pression", "label": "La porte", "fait": "La pierre vibre sous la main, par vagues lentes. Quelque chose pousse de l'autre côté, et ne passe pas."},
			{"id": "empreintes", "label": "Le sol devant la porte", "fait": "Des empreintes géantes dans la vase séchée, qui ne vont nulle part."},
			{"id": "silhouettes", "label": "Ce qu'ont vu les techniciens", "fait": "Rangi a recueilli les récits : trois silhouettes, que personne ne décrit de la même façon."},
			{"id": "fresques", "label": "Les fresques", "fait": "Un héros mène, enchaîné, un chien à trois têtes. Plus loin, une femme-serpent regarde la porte."},
			{"id": "inscription", "label": "L'inscription des Tables de Pierre", "fait": "Le maître de l'autre côté y est nommé « Celui qui reçoit beaucoup ». Polydegmon, dans la langue des Hellènes : Hadès."},
		], "conclusions": [
			{"id": "use", "label": "Le sceau s'use tout seul, avec les siècles."},
			{"id": "force", "label": "Ce qui est de l'autre côté a forcé le sceau."},
			{"id": "retire", "label": "Quelqu'un d'ici a retiré des pièces du sceau, et ce qui pousse de l'autre côté ne passe pas encore."},
		]},
		{"conclusion": "retire", "indices": ["logements", "pression"], "seuil": 2},
		"Des pièces retirées, volontairement. Une porte qui tient encore. Derrière les fresques, une dalle "
		"cède sous la main, et un passage s'ouvre vers le bas, vers une odeur de sel, de vase et de "
		"quelque chose de vivant. Qui a retiré les pièces, et pourquoi, la chambre ne le dit pas.",
		"Ce n'est pas ce que disent les choses que vous avez vues.",
		[compagnon("lettre", "examen:inscription", "Celui qui reçoit beaucoup. On le disait d'un dieu qui ne rendait rien."),
		 compagnon("mage", "examen:pression", "Ce n'est pas du mana qui pousse. C'est un appétit."),
		 compagnon("voleur", "examen:logements", "Du travail propre. Celui qui a fait ça savait ce qu'il démontait."),
		 compagnon("forestier", "examen:empreintes", "Grandes, et trois tailles. Ou une bête qui change.")],
		[apres(Q_DESCENTE)])
	aelis_sceau = pnj_doc(AELIS_SCEAU, "Aélis de Montfaucon", "humain",
		"Aélis de Montfaucon, devant la porte scellée sous Mu.", PORTRAIT_AELIS_DIALOGUE, vocation="lettre", noeuds={
		"accueil": noeud(
			"Aélis est assise face à la porte, le carnet sur les genoux, et recopie les fresques trait par "
			"trait. Elle ne se retourne pas à votre entrée.",
			choix("porte", "« Qu'est-ce que c'est ? »", "porte"),
			choix("templiers", "« Les Templiers voudront renforcer le sceau. »", "templiers"),
			choix("regarder", "« Regardons le sceau ensemble. »", "fin", enigme=E_SCELLEMENT,
				  condition={"enigme_resolue": {"id": E_SCELLEMENT, "attendu": False}}),
			choix("fin", "(La laisser recopier.)", "fin")),
		"porte": noeud(
			"« La porte que Mu a fermée. Celle pour laquelle elle a payé un continent, si l'on croit les "
			"vieux. » Elle tapote la fresque du chien à trois têtes. « Et on dirait qu'elle mène chez "
			"quelqu'un. Celui qui reçoit beaucoup. Une porte vorace, ou l'appétit d'une maison. »",
			choix("ok", "Revenir.", "accueil")),
		"templiers": noeud(
			"« Ils voudront le renforcer, quitte à détruire une partie du portail. » Elle relève la tête. "
			"« Ça ne se défait pas, ce genre de geste. Je ne les laisserai pas faire. Pas avant qu'on ait "
			"compris. Et peut-être pas après. »",
			choix("ok", "Revenir.", "accueil")),
	})
	return [vannes, scellement, aelis_descente(), aelis_sceau]


# ---------------------------------------------------------------------------------------------
# 5. Échidna — la parole (transport) ou le combat ; Quitter Mu (copie partielle du relevé)
# ---------------------------------------------------------------------------------------------
# Mesuré : Échidna ≈ 424 au grade 5 (héros), ≈ 437 au grade 6 (seigneur) → rang S, seule, contre un
# groupe de rang A : « très difficile », comme le veut le lore.



def offre_parole():
	return {"id": Q_PAROLE, "titre": "La mère des serpents",
			"description": "Échidna vous a confié une de ses écailles. Portez-la à Ana Hereheretue, à "
						   "l'Institut de Mu : les Architectes peuvent tenir un passage étroit et bref sous "
						   "la cité, sans rouvrir la porte, pour que Cerbère rejoigne sa mère.",
			"destination": INSTITUT, "cargaison": [{"item": ECAILLE, "quantite": 1, "poids": 2}],
			"proba": 1, "unique": True, "recompenses": {"xp": 400, "cuivre": 0}}


def echidna():
	sans_choix = {"quete_active": {"id": Q_PAROLE, "attendu": False}, "quete_reussie": {"id": Q_PAROLE, "attendu": False}}
	return pnj_doc(ECHIDNA, "Échidna", "serpent",
		"La mère des serpents, sous Mu-la-Centrale.", PORTRAITS[ECHIDNA], vocation="mage",
		services={
			"transport": {"offre": offre_parole(),
						  "noeuds": {"accepte": "parole_accepte", "trop_charge": "parole_trop_charge"}},
			"acces": {"lieu": COMBAT_ANTRE, "noeuds": {"ouvre": "combat_ouvert", "refus": "combat_refuse"}},
			"don": {"item": COPIE_RELEVE, "quantite": 1, "cout_cuivre": 0, "unique": True, "unique_porteurs": True,
					"noeuds": {"fait": "releve_donne", "sans_fonds": "releve_donne", "trop_charge": "releve_lourd"}},
		},
		noeuds={
		"accueil": noeud(
			"Dans une grotte d'eau noire, une femme se tient à demi dressée sur des anneaux de serpent plus "
			"larges qu'une barque, écailles bleu nuit et or. Son visage est grave, presque beau. Elle vous "
			"regarde venir sans bouger, comme on regarde venir une marée qu'on connaît.",
			choix("qui", "« Qui êtes-vous ? »", "qui", condition=sans_choix),
			choix("ecouter", "« Je vous écoute. »", "ecoute", condition=dict(sans_choix, transport_offert=True)),
			choix("combattre", "« Je viens vous combattre. »", "avertit", condition=sans_choix),
			choix("parole_en_cours", "« L'écaille… »", "parole_en_cours", condition=pendant(Q_PAROLE)),
			choix("parole_apres", "« Cerbère est là ? »", "parole_apres", condition=apres(Q_PAROLE)),
			choix("releve", "« Le relevé d'Uanna. »", "releve", condition=dict(apres(Q_PAROLE), don_recu=False)),
			choix("fin", "(Reculer.)", "fin")),
		"qui": noeud(
			"« On m'appelle la mère des serpents. Vous m'appelez la mère des monstres. » Sa voix est basse, "
			"sans colère. « Mes enfants s'appelaient l'Hydre, le lion de Némée, Orthos. Un héros les a "
			"abattus l'un après l'autre, et des dieux l'envoyaient. Mon fils Cerbère, on l'a enchaîné et "
			"traîné hors des Enfers. Et moi, on m'a laissée vivre. Pour éprouver les héros. » Elle penche "
			"la tête. « Vous appelez monstres mes enfants. Et vous, qui vous envoie ? »",
			choix("ok", "Revenir.", "accueil")),
		"ecoute": noeud(
			"Elle se tait longtemps. « Alors écoutez. La porte sous cette cité menait chez Celui qui reçoit "
			"beaucoup. Elle avait faim, et elle grandissait. Les maîtres de Mu l'ont fermée. Pour la fermer, "
			"ils ont donné un continent. Ils l'ont décidé, ils l'ont organisé, et ils ont dit à leur peuple "
			"que la terre tremblait. » Ses anneaux se resserrent. « Si les dieux ont vu grandir cette porte, "
			"ils l'ont laissée faire. Mu a payé seule. »",
			choix("cerbere", "« Et Cerbère ? »", "demande")),
		"demande": noeud(
			"« Il était de l'autre côté quand ils ont fermé. Je le soignais. Il y est resté. » Elle arrache "
			"une écaille à son flanc, sans un bruit, et vous la tend. « Les Architectes savent tenir un "
			"passage étroit, bref, sans rouvrir la porte. Portez ceci à la vôtre, celle qui travaille la "
			"pierre jaune. Qu'ils le laissent revenir près de moi. C'est tout ce que je demande aux "
			"Anthropes. »",
			choix("accepter", "Prendre l'écaille.", action={"service": "transport", "op": "accepter"}),
			choix("refuser", "« Pas encore. »", "accueil")),
		"parole_accepte": noeud(
			"« Ana Hereheretue. » Elle connaît le nom. « Elle a les mains sûres. » Elle se recouche dans "
			"l'eau noire. « Je n'irai nulle part. »",
			choix("fin", "(Remonter.)", "fin")),
		"parole_trop_charge": noeud("« Vous portez trop. Une écaille de moi ne se laisse pas au fond d'un sac. »",
									choix("ok", "Revenir.", "accueil")),
		"parole_en_cours": noeud("« À l'Institut. Je n'irai nulle part. »", choix("ok", "Revenir.", "accueil")),
		"parole_apres": noeud(
			"Un grand chien noir à trois têtes dort contre ses anneaux, les trois museaux sur ses écailles. "
			"Elle ne le quitte pas des yeux. « Il gardait une maison vide. Un trône sans personne, des fleurs "
			"sans ombres. » Elle relève la tête. « Où sont partis les dieux, Anthrope ? Je ne le sais pas "
			"plus que vous. Ce que ce passage coûtera, nul ne le sait encore. »",
			choix("ok", "Revenir.", "accueil")),
		"releve": noeud(
			"« Le siège d'Uanna tient un relevé des seuils naturels. Je l'ai vu, du temps où les Sages "
			"descendaient me voir. Quelques lignes y portent un mot : demeure. La porte d'ici. Saint-Pierre. "
			"L'Hekla. Un arbre du nord. » Elle trace des signes dans la vase, d'une griffe. « Les Sages ne "
			"vous le donneront pas. Recopiez ce que je me rappelle. Ce n'est qu'une part. »",
			choix("copier", "Recopier les lignes tracées dans la vase.", action={"service": "don"}),
			choix("ok", "Revenir.", "accueil")),
		"releve_donne": noeud(
			"Vous recopiez. Le reste lui échappe. « Allez voir si les autres demeures sont vides, elles "
			"aussi. Et revenez me le dire, si vous en revenez. »",
			choix("fin", "(Remonter.)", "fin")),
		"releve_lourd": noeud("« Allégez-vous d'abord. »", choix("ok", "Revenir.", "accueil")),
		"avertit": noeud(
			"Elle se dresse, et la grotte paraît soudain trop petite. « Écoutez-moi bien. Je ne meurs pas. "
			"Je ne vous laisserai pas me prendre ce qui me reste. Si vous levez une arme, je me battrai "
			"jusqu'à ce que l'un de nous doive fuir, et ce ne sera pas sans peine pour vous. » Elle attend. "
			"« Vous pouvez encore remonter. »",
			choix("lutter", "Lever votre arme.", condition={"acces_ouvrable": True},
				  action={"service": "acces", "op": "passer"}),
			choix("non", "« Je vous écoute, alors. »", "accueil")),
		"combat_ouvert": noeud("« Vous faites leur ouvrage. Comme lui. »", choix("arme", "Frapper.", "fin")),
		"combat_refuse": noeud("Elle vous regarde sans bouger. « Ce choix-là est derrière vous. »",
							   choix("ok", "Revenir.", "accueil")),
	})


def aelis_antre():
	"""Sur la voie du COMBAT : Échidna enfuie, Aélis recopie ce qu'elle a laissé dans l'antre."""
	return pnj_doc(AELIS_ANTRE, "Aélis de Montfaucon", "humain",
		"Aélis de Montfaucon, dans l'antre déserté d'Échidna.", PORTRAIT_AELIS_DIALOGUE, vocation="lettre",
		services={"don": {"item": COPIE_RELEVE, "quantite": 1, "cout_cuivre": 0, "unique": True, "unique_porteurs": True,
						  "noeuds": {"fait": "releve_donne", "sans_fonds": "releve_donne", "trop_charge": "releve_lourd"}}},
		noeuds={
		"accueil": noeud(
			"L'antre est vide. Une mue immense luit encore dans l'eau noire. Aélis est accroupie devant une "
			"paroi couverte de signes, gravés d'une griffe, et des ossements soigneusement rangés : un crâne "
			"de lion, des têtes de serpent, une mâchoire de chien.",
			choix("reliques", "« Qu'est-ce que c'est ? »", "reliques"),
			choix("releve", "« Ces signes ? »", "releve", condition={"don_recu": False}),
			choix("fin", "(Se taire.)", "fin")),
		"reliques": noeud(
			"« Ses enfants. L'Hydre, le lion de Némée, Orthos. » Aélis ne les touche pas. « Elle les "
			"gardait. Et là, gravé, un homme avec une massue et une peau de lion. Héraclès. » Elle vous "
			"regarde. « Elle a dit que nous faisions leur ouvrage. Je ne sais pas qui sont \"ils\". Vous "
			"non plus. »",
			choix("ok", "Revenir.", "accueil")),
		"releve": noeud(
			"« Une liste. Des seuils naturels. Le mot \"demeure\" à côté de quatre : la porte d'ici, "
			"Saint-Pierre, l'Hekla, un arbre du nord. » Elle recopie, vite. « Le siège d'Uanna a l'original, "
			"j'en suis sûre. Ils ne nous le donneront jamais. Voilà une copie. Une part seulement. »",
			choix("prendre", "Prendre la copie.", action={"service": "don"}),
			choix("ok", "Revenir.", "accueil")),
		"releve_donne": noeud(
			"« Elle ne défend plus Mu, maintenant. Elle est quelque part, pas loin, et elle attend son "
			"fils. » Aélis referme le carnet. « Les grands fonds le sauront avant nous. »",
			choix("fin", "(Remonter.)", "fin")),
		"releve_lourd": noeud("« Allégez-vous d'abord. »", choix("ok", "Revenir.", "accueil")),
	})


def quete_echidna(par_id):
	antre = lieu(ANTRE, "L'antre d'Échidna",
		"Une grotte d'eau noire sous la chambre du sceau, où l'on respire un air de sel et de vase. Les "
		"parois portent des marques de griffes, et l'eau, au fond, ne reflète rien.",
		acces={"cycle": 1, "refus": "La dalle derrière les fresques ne bouge pas.",
			   "conditions": [{"enigme_resolue": {"id": E_SCELLEMENT}}]},
		pnj=[present(ECHIDNA, "Échidna", "Une femme dressée sur des anneaux de serpent, dans l'eau noire.",
					 [{"combat_gagne": {"lieu": COMBAT_ANTRE, "attendu": False}}]),
			 present(AELIS_ANTRE, "Aélis", "Aélis, accroupie devant une paroi gravée, dans l'antre déserté.",
					 [{"combat_gagne": {"lieu": COMBAT_ANTRE}}])])
	antre["pnj"][1]["portrait"] = PORTRAIT_AELIS_DIALOGUE
	combat = salle(COMBAT_ANTRE, "L'antre d'Échidna", par_id[CARTES_PROVISOIRES[COMBAT_ANTRE]],
				   ["sous-terrain", "donjon", "couvert", "humide", "eau"],
				   {"gardien": ECHIDNA, "cycle": 1, "refus": "Échidna ne se battra plus.",
					# Le combat n'est plus ouvert dès que la parole est engagée : le choix est définitif.
					"conditions": [{"combat_gagne": {"lieu": COMBAT_ANTRE, "attendu": False}},
								   {"quete_active": {"types": ["transport"], "cible": INSTITUT, "attendu": False}},
								   {"quete_reussie": {"id": Q_PAROLE, "attendu": False}}]})
	d = donjon(D_ANTRE, "L'antre d'Échidna", "Sous la chambre du sceau de Mu, la grotte d'eau noire de la mère des serpents.",
			   ANTRE, COMBAT_ANTRE, {E_ECHIDNA: 1}, 5, 6)
	return [echidna(), aelis_antre(), antre, combat, d]


# ---------------------------------------------------------------------------------------------
# Les sept affaires
# ---------------------------------------------------------------------------------------------

def affaire_chant():
	offre = offre_apport(Q_CHANT, "Le chant sous les ruines",
		"Hine Matarau chante une mélodie que des gens de tous âges connaissent sans l'avoir apprise. Elle "
		"voudrait savoir d'où elle vient. Un sanctuaire noyé de Tangaroa en garderait les fragments gravés : "
		"rapportez-lui-en l'estampage.", FRAGMENTS_CHANT, 180, 1500)
	hine = donneur(HINE, "Hine Matarau", "humain", "Vieille chanteuse, au fare des Marées.", "menestrel", offre, AU_MU,
		{"accueil": "Une vieille femme au visage plissé de rires, assise près du bassin du fare, qui fredonne "
					"sans s'en rendre compte. Quand elle se tait, deux tables plus loin, quelqu'un continue.",
		 "offre_label": "« Cet air, d'où vient-il ? »",
		 "propose": "« De ma mère, qui le tenait de la sienne. Je n'ai pas connu le temps où le continent "
					"s'est couché, moi. Le chant, si. » Elle sourit. « Les jeunes le connaissent sans que je "
					"leur aie appris. Le petit Tama, par exemple. Ils rêvent tous d'une ville sous un soleil "
					"impossible. On dit qu'un vieux sanctuaire de Tangaroa, noyé sous le quai, en garde les "
					"mots gravés. Rapportez-les-moi. »",
		 "accepte": "« Le sanctuaire est sous le quai des pêcheurs. Rawiri, l'archiviste, y descend déjà avec "
					"ses lanternes. Il ne croit à rien, celui-là. C'est reposant. »",
		 "rappel": "« Le sanctuaire noyé, sous le quai. Les mots gravés. »",
		 "remettre_label": "Lui tendre l'estampage des fragments.",
		 "remis": "Hine suit les signes du doigt, et ses lèvres bougent. « Là. C'est là que ma mère disait "
				  "autre chose. » Elle chante, doucement, la version entière. Au milieu, un merci : à "
				  "Tangaroa, père des poissons, pour la coque d'or. Elle s'arrête. « La coque d'or. C'est "
				  "la bulle. Nous remercions Tangaroa pour la bulle. » Elle se lève. « On le chantera là où il "
				  "est né. »",
		 "souvenir": "« On le chante en entier, maintenant. » Elle rit. « Rawiri en a gardé une copie, pour "
					 "que le chant ne tienne plus à ma seule mémoire. Il dit que ça ne prouve pas que "
					 "Tangaroa l'a faite, ni qu'il a entendu. Il a raison. Et d'où viennent les rêves, nul "
					 "ne le sait. »"},
		[("sanctuaire", "Descendre avec elle au sanctuaire.",
		  "Au sanctuaire noyé, Hine chante la version entière, et les rêveurs avec elle, Tama le premier, "
		  "et tous ceux qui l'ont voulu. Les murs portent les voix comme une seule. Rawiri, à l'écart, "
		  "recopie : le chant ne tiendra plus à la seule mémoire d'une vieille femme. Il dit que Mu a "
		  "remercié Tangaroa pour la bulle. Il ne dit pas que Tangaroa l'a faite, ni qu'il a entendu.")])
	rawiri_s = remettant(RAWIRI_SANCTUAIRE, "Rawiri Tane", "hobbit", "Archiviste de l'Institut, au sanctuaire noyé.",
		"lettre", Q_CHANT, FRAGMENTS_CHANT, E_CHANT,
		{"accueil": "Un hobbit trempé jusqu'aux genoux, une lanterne dans chaque main, devant des murs couverts "
					"de signes à demi effacés. L'eau monte et descend dans la salle comme une respiration.",
		 "regarder_label": "« Relevons les fragments. »",
		 "prendre_label": "« L'estampage, pour Hine. »",
		 "donne": "Rawiri vous tend l'estampage roulé. « Gardez-vous de croire que c'est la main d'un dieu. "
				  "C'est la main de ceux qui le remerciaient. Ça n'est pas pareil. » Il remonte sa lanterne. "
				  "« Moi, j'en garde une copie. »",
		 "apres": "« Ils ont chanté ici. Tous. » Il fronce les sourcils. « Les murs résonnent comme si on les "
				  "avait bâtis pour ça. On les a bâtis pour ça. Ça ne prouve rien d'autre. »"})
	e = enigme(E_CHANT, "Les fragments du chant", "association", SANCTUAIRE,
		"Gravés sur les murs du sanctuaire, des fragments du chant. Dans votre mémoire, les vers de Hine. "
		"Certains ont changé en passant de bouche en bouche : rendez chaque vers à son fragment.",
		{"gauche": [
			{"id": "pere", "texte": "« Père des poissons, garde nos morts. »"},
			{"id": "soleil", "texte": "« La ville dort sous un soleil qu'on ne regarde pas. »"},
			{"id": "coque", "texte": "« Merci pour la coque, qui brille. »"},
			{"id": "retour", "texte": "« Ceux qui partent reviendront par l'eau. »"},
		], "droite": [
			{"id": "tangaroa", "texte": "« Tangaroa, père des poissons, reçois ceux qui te sont rendus. »"},
			{"id": "astre", "texte": "« Mu sous l'astre que nul œil ne soutient. »"},
			{"id": "or", "texte": "« Gratitude à Tangaroa pour la coque d'or qui nous tient. »"},
			{"id": "maree", "texte": "« Ce que la marée prend, la marée le rend. »"},
		]},
		{"paires": {"pere": "tangaroa", "soleil": "astre", "coque": "or", "retour": "maree"}, "seuil": 3},
		"Les vers retrouvent leurs fragments. Au milieu du chant, ce que la mémoire avait poli : la coque "
		"d'or. Rawiri relève la lanterne. « La bulle », dit-il. « Ils remerciaient pour la bulle. »",
		"Rawiri secoue la tête. « Ce vers-là n'est pas né sur ce mur. »",
		[compagnon("menestrel", "ouverture", "Un chant qui passe de bouche en bouche garde l'air et perd les mots."),
		 compagnon("lettre", "echec", "Cherchez le sens, pas les mots. La mémoire change les mots."),
		 compagnon("pretre", "reussite", "Un merci n'est pas une preuve qu'on a été entendu.")],
		[apport_actif(FRAGMENTS_CHANT)])
	sanctuaire = lieu(SANCTUAIRE, "Le sanctuaire noyé de Tangaroa",
		"Une salle ronde aux murs gravés, à demi noyée sous le quai, où l'eau monte et descend avec la marée "
		"de la bulle. Les murs sont disposés pour qu'une assemblée chante d'une seule voix.",
		acces={"cycle": 1, "refus": "L'eau couvre l'escalier du sanctuaire. Rien ne vous appelle en bas.",
			   "conditions": [ouvert_pour(apport_actif(FRAGMENTS_CHANT), Q_CHANT)]},
		pnj=[present(RAWIRI_SANCTUAIRE, "Rawiri Tane", "Un hobbit trempé, une lanterne dans chaque main.",
					 [ouvert_pour(apport_actif(FRAGMENTS_CHANT), Q_CHANT)])])
	return [hine, rawiri_s, e, sanctuaire, lien(QUAI, (0, 0), "Remonter sur le quai", SANCTUAIRE, "Descendre au sanctuaire noyé")]


def affaire_marchand():
	offre = offre_apport(Q_MARCHAND, "Le marchand qui vend le passé",
		"Au marché du Dôme, Tane Moerai vend des objets marqués du sceau de Mu, authentiques, sortis d'un "
		"secteur fermé depuis des générations. Mere Tapuni, restauratrice de l'Institut, voudrait savoir "
		"d'où ils viennent : rapportez-lui l'inventaire du dépôt dont ils sortent.", INVENTAIRE_DEPOT, 180, 1500)
	mere = donneur(MERE, "Mere Tapuni", "ogre", "Restauratrice de l'Institut de Mu.", "lettre", offre, AU_MU,
		{"accueil": "Une ogresse aux mains étonnamment fines, penchée sur un tesson qu'elle recolle au "
					"pinceau, une loupe de nacre vissée à l'œil.",
		 "offre_label": "« Ce tesson vient d'où ? »",
		 "propose": "« Du marché. Je l'ai acheté à Tane Moerai, avec mon argent, pour qu'il ne parte pas en "
					"haut. » Elle pose son pinceau. « Une plaque d'accès, un outil d'Architecte, une figurine "
					"votive. Authentiques. Sortis d'un secteur fermé depuis des générations. Pour lui, les "
					"objets doivent circuler. Pour moi, ils doivent durer. Trouvez d'où ils sortent. »",
		 "accepte": "« Les plaques portent le sceau d'un ancien dépôt de maintenance, dans le secteur "
					"condamné, à l'ouest de la grande place. On n'y va plus. Quelqu'un y va. »",
		 "rappel": "« Le dépôt de maintenance condamné. L'inventaire de ce qui en sort. »",
		 "remettre_label": "Lui remettre l'inventaire du dépôt.",
		 "remis": "Mere parcourt l'inventaire, ligne à ligne, et sa loupe tombe. « Une réserve effondrée. Des "
				  "pièces déplacées le mois dernier. Et un intermédiaire qui cachait l'endroit pour être le "
				  "seul à y aller. » Elle soupire. « Que fait-on, maintenant ? »",
		 "souvenir": "« Les pièces sensibles sont inventoriées, le dépôt mis en sûreté. » Elle reprend son "
					 "pinceau. « Tane garde son étal, et il écrit ses provenances. Lui dit qu'un passé qu'on "
					 "enferme est un passé qu'on oublie. Moi, qu'un passé qu'on vend est un passé qu'on perd. "
					 "Nous avons tous les deux raison, et ça m'agace. »"},
		[("denoncer", "« Dénoncez l'intermédiaire. »",
		  "« Les Templiers s'en chargeront. » Elle range l'inventaire. « Le dépôt sera muré, et les pièces "
		  "qui y restent avec. »"),
		 ("restitution", "« Négociez une restitution avec Tane. »",
		  "« Il rendra ce qu'il a, s'il peut vendre le reste avec un papier. » Elle grimace. « C'est un "
		  "marché. Ici, tout finit en marché. »"),
		 ("conserver", "« Gardez les pièces, le temps de les étudier. »",
		  "Elle sourit pour la première fois. « Pour un temps. Je le noterai : pour un temps. Ça fera "
		  "plaisir à Tane, ce mot-là. »")])
	tane = temoin(TANE, "Tane Moerai", "nain", "Marchand d'objets anciens, au marché du Dôme.", "guerrier",
		"Un nain derrière un étal tendu de toile noire. Une plaque de bronze au sceau de Mu, un outil de "
		"pierre poli par des mains mortes depuis longtemps, une petite figurine de corail.",
		[("etal", "« D'où viennent ces objets ? »", avant(Q_MARCHAND),
		  "« De Mu. » Il sourit. « Tout vient de Mu, ici. »"),
		 ("defense", "« Ils sortent d'un secteur fermé. »", pendant(Q_MARCHAND),
		  "« Et alors ? Ils dormaient dans le noir, ils ne servaient à personne. » Il hausse les épaules. "
		  "« Un objet qui ne passe plus de main en main, c'est un objet mort. Mere veut des morts bien "
		  "rangés. Moi, je les fais vivre. Je les achète à un type qui ne dit jamais d'où. »"),
		 ("apres", "« Vous écrivez vos provenances, maintenant ? »", apres(Q_MARCHAND),
		  "« J'écris. » Il tapote un registre neuf. « Les clients aiment ça, figurez-vous. Une histoire, "
		  "ça se vend mieux qu'un objet. »")])
	piripi = remettant(PIRIPI, "Piripi Ngata", "humain", "Intermédiaire, au dépôt de maintenance condamné.", "voleur",
		Q_MARCHAND, INVENTAIRE_DEPOT, E_DEPOT,
		{"accueil": "Un homme maigre, une lanterne sourde à la main, qui se fige en vous voyant au milieu des "
					"caisses du dépôt, puis fait semblant de compter.",
		 "regarder_label": "« Regardons ce dépôt de plus près. »",
		 "prendre_label": "« Votre inventaire, Piripi. Tout. »",
		 "donne": "Il vous tend un carnet graisseux. « Tout est là. Ce que j'ai sorti, ce qui reste. La "
				  "réserve s'est effondrée toute seule, je n'ai rien cassé. » Il baisse les yeux. « Je "
				  "voulais juste être le seul à savoir. »",
		 "apres": "« On m'a pris le dépôt. » Il hausse les épaules. « C'était pas à moi. Ça faisait du bien "
				  "de faire comme si. »"})
	e = enigme(E_DEPOT, "Le dépôt de maintenance", "deduction", DEPOT,
		"Des caisses, des étagères vides, une réserve au plafond effondré, et des traces partout dans la "
		"poussière. Quelqu'un sort des objets d'ici depuis peu, et il est seul à savoir comment.",
		{"indices": [
			{"id": "eboulis", "label": "La réserve effondrée", "fait": "Le plafond s'est effondré de lui-même, il y a longtemps : la poussière sur les blocs est épaisse."},
			{"id": "trou", "label": "Le passage dans l'éboulis", "fait": "Un passage creusé récemment dans l'éboulis, juste assez large pour une personne."},
			{"id": "caisses", "label": "Les caisses", "fait": "Des caisses déplacées le mois dernier : les marques de leur ancien emplacement sont encore nettes."},
			{"id": "porte", "label": "La porte du secteur", "fait": "Le sceau de condamnation de la porte est intact. On n'entre pas par là."},
			{"id": "carnet", "label": "La lanterne de Piripi", "fait": "Sa lanterne est réglée au plus bas : celle de quelqu'un qui ne veut pas être vu."},
		], "conclusions": [
			{"id": "pillage", "label": "Une bande de pillards vide le dépôt par la grande porte."},
			{"id": "seul", "label": "Un seul homme a trouvé un chemin par la réserve effondrée et garde le secret pour lui."},
			{"id": "institut", "label": "L'Institut a vidé le dépôt et revend les pièces."},
		]},
		{"conclusion": "seul", "indices": ["trou", "porte", "caisses"], "seuil": 2},
		"Un passage dans l'éboulis, une porte jamais ouverte, des caisses déplacées une à une. Un seul homme, "
		"et un monopole. Piripi cesse de compter.",
		"Piripi sourit, rassuré. Ce n'est pas ça.",
		[compagnon("voleur", "examen:trou", "Un trou de rat. Celui qui l'a creusé ne voulait pas de compagnie."),
		 compagnon("guerrier", "examen:porte", "Personne n'a passé cette porte depuis qu'on l'a scellée."),
		 compagnon("lettre", "ouverture", "Un dépôt de maintenance a toujours un registre. Celui-ci a un menteur.")],
		[apport_actif(INVENTAIRE_DEPOT)])
	depot = lieu(DEPOT, "Le dépôt de maintenance condamné",
		"Un ancien dépôt de maintenance du secteur condamné, à l'ouest de la grande place : des caisses, des "
		"étagères de pierre, une réserve au plafond effondré, et l'odeur de la poussière qui n'a pas vu d'air.",
		acces={"cycle": 1, "refus": "Une porte au sceau de condamnation intact. Rien ne vous y appelle.",
			   "conditions": [ouvert_pour(apport_actif(INVENTAIRE_DEPOT), Q_MARCHAND)]},
		pnj=[present(PIRIPI, "Piripi Ngata", "Un homme maigre, une lanterne sourde à la main, au milieu des caisses.",
					 [ouvert_pour(apport_actif(INVENTAIRE_DEPOT), Q_MARCHAND)])])
	return [mere, tane, piripi, e, depot]


def affaire_enfants():
	offre = offre_apport(Q_ENFANTS, "Les enfants de la marée",
		"Des enfants de Mu rêvent d'une femme qui leur apprend une langue inconnue, la main posée sur l'eau. "
		"Ataahua Paora, soigneuse, s'en inquiète. Mahina Rehu, vieille linguiste, reconnaît des tournures. "
		"Retrouvez d'où viennent ces mots et rapportez à Ataahua ce que vous trouverez.", TABLETTE, 180, 1500)
	ataahua = donneur(ATAAHUA, "Ataahua Paora", "elfe", "Soigneuse des enfants du quartier des bassins.", "pretre", offre, AU_MU,
		{"accueil": "Une elfe en tablier de soigneuse, une infusion fumante entre les mains, qui surveille la "
					"porte du fare comme si un enfant allait y paraître à tout instant.",
		 "offre_label": "« Vous attendez quelqu'un ? »",
		 "propose": "« Les enfants du quartier des bassins rêvent de la même femme. Elle leur apprend une "
					"langue. Elle pose la main sur l'eau, et elle attend qu'on lui réponde d'en bas. » Elle "
					"serre sa tasse. « L'un est fasciné, un autre a peur de dormir. Mahina dit qu'elle "
					"reconnaît des tournures. Moi, je veux savoir si je dois les réveiller. »",
		 "accepte": "« Mahina les a écoutés un à un. Elle dit que les mêmes signes sont gravés sur les bornes "
					"du bassin de marée, et plus bas, dans une vieille chambre hydraulique. Elle y est déjà. "
					"Elle a soixante-dix ans. Allez-y vite. »",
		 "rappel": "« La chambre hydraulique, sous le bassin de marée. Mahina y est. »",
		 "remettre_label": "Lui montrer la tablette des bassins.",
		 "remis": "Ataahua lit la traduction de Mahina, épinglée à la tablette, à mi-voix : « Pose la main "
				  "sur l'eau. Attends. Si l'eau répond, ne descends pas. » Elle relève la tête. « Une "
				  "formule de prudence. On apprenait ça aux petits de Mu, pour les bassins. » Elle rit, "
				  "nerveusement. « Mahina voudra en faire une leçon. »",
		 "souvenir": "« Mahina en a fait une leçon. Les petits la récitent en jouant au bord des bassins. » "
					 "Elle sourit, puis plus du tout. « Certains ne rêvent plus. D'autres, si. La femme, "
					 "personne ne sait qui c'est. »"},
		[("lecon", "« Qu'elle en fasse une leçon. »",
		  "« Une leçon, comme autrefois. » Ataahua hoche la tête. « Les petits la réciteront au bord des "
		  "bassins. » Elle repose sa tasse. « Certains cesseront de rêver. D'autres, non. Et la femme, "
		  "personne ne saura qui c'est. »")])
	mahina_b = remettant(MAHINA_BASSIN, "Mahina Rehu", "humain", "Vieille linguiste de l'Institut, dans la chambre hydraulique.",
		"lettre", Q_ENFANTS, TABLETTE, E_BASSIN,
		{"accueil": "Une vieille femme assise sur une margelle, les pieds dans l'eau qui monte, un carnet sur "
					"les genoux. Devant elle, une grille, une tablette coincée derrière, et des signes gravés "
					"à hauteur d'enfant.",
		 "regarder_label": "« Lisons ces signes ensemble. »",
		 "prendre_label": "« La tablette, pour Ataahua. »",
		 "donne": "Vous dégagez la grille ensemble, et Mahina tire la tablette de l'eau juste avant qu'elle "
				  "ne la couvre. Elle épingle sa traduction dessus. « Pour Ataahua. Et pour les petits. » "
				  "Elle sort les pieds de l'eau. « La femme du rêve, je ne la reconnais pas. Je reconnais "
				  "les mots. C'est déjà beaucoup. »",
		 "apres": "« Les signes étaient à hauteur d'enfant. » Elle range son carnet. « On apprenait aux petits "
				  "les repères de sécurité, et les mots de la navigation. Mu savait que ses enfants vivraient "
				  "près de l'eau. »"})
	e = enigme(E_BASSIN, "Les mots des enfants", "association", CHAMBRE_HYDRAULIQUE,
		"Mahina a noté les mots des enfants, un par un. Sur les bornes de la chambre, des signes gravés à "
		"hauteur d'enfant. Rendez chaque mot à son signe.",
		{"gauche": [
			{"id": "main", "texte": "« Main sur l'eau » (l'enfant fasciné)."},
			{"id": "attendre", "texte": "« Attendre » (l'enfant qui a peur)."},
			{"id": "reponse", "texte": "« L'eau répond » (les jumeaux du quai)."},
			{"id": "descendre", "texte": "« Ne pas descendre » (la plus petite, en pleurant)."},
		], "droite": [
			{"id": "paume", "texte": "Une paume ouverte au-dessus d'une ligne ondulée."},
			{"id": "sablier", "texte": "Deux triangles pointe contre pointe."},
			{"id": "cercles", "texte": "Des cercles qui s'élargissent sur l'eau."},
			{"id": "marche", "texte": "Une marche barrée d'un trait."},
		]},
		{"paires": {"main": "paume", "attendre": "sablier", "reponse": "cercles", "descendre": "marche"}, "seuil": 3},
		"Les mots trouvent leurs signes, et la suite se lit : poser la main sur l'eau, attendre, et si l'eau "
		"répond, ne pas descendre. Une formule de prudence des bassins. La grille, elle, est toujours "
		"coincée, et l'eau monte.",
		"Mahina secoue la tête. « Pas celui-là. Les enfants ne disent pas ça avec ce signe. »",
		[compagnon("lettre", "ouverture", "Des signes à hauteur d'enfant. Une école, ou un avertissement."),
		 compagnon("pretre", "echec", "Écoutez comme l'enfant le disait, pas seulement ce qu'il disait."),
		 compagnon("forestier", "reussite", "Si l'eau répond, on ne descend pas. Je connais des rivières qui méritent la même règle.")],
		[apport_actif(TABLETTE)])
	chambre = lieu(CHAMBRE_HYDRAULIQUE, "La chambre hydraulique oubliée",
		"Sous le bassin de marée, une chambre de pierre aux bornes gravées, où une fermeture bloquée laisse "
		"l'eau monter lentement. Une grille, et derrière, une tablette.",
		acces={"cycle": 1, "refus": "Le bassin de marée est calme. Rien ne vous y appelle.",
			   "conditions": [ouvert_pour(apport_actif(TABLETTE), Q_ENFANTS)]},
		pnj=[present(MAHINA_BASSIN, "Mahina Rehu", "Une vieille femme assise sur une margelle, les pieds dans l'eau.",
					 [ouvert_pour(apport_actif(TABLETTE), Q_ENFANTS)])])
	return [ataahua, mahina_b, e, chambre]


def affaire_poissons():
	offre = offre_apport(Q_POISSONS, "Les eaux sans poissons",
		"Depuis le sacrifice du continent, une zone de la mer est presque vide de poissons. Tamatoa Paepae, "
		"pêcheur, porte le deuil d'une lignée et voudrait comprendre. Une structure immergée, à demi "
		"enfouie, trouble le mana : rapportez-lui le relevé de ses courants.", RELEVE_COURANTS, 180, 1500)
	tamatoa = donneur(TAMATOA, "Tamatoa Paepae", "ogre", "Pêcheur, sur le quai de Mu.", "guerrier", offre, AU_MU,
		{"accueil": "Un ogre aux mains couturées de cicatrices de ligne, qui ravaude un filet sur le quai. "
					"Sur son épaule, un tatouage de noms, serrés, nombreux.",
		 "offre_label": "« Ces noms, sur votre épaule ? »",
		 "propose": "« Les miens. Ceux qui sont morts pendant les années de disette, après le sacrifice. » "
					"Il ne lève pas les yeux. « Il y a une zone, au large de la bulle, où il n'y a plus de "
					"poissons. Les pêcheurs l'évitent. Des silhouettes immenses passent au fond, et les "
					"instruments s'affolent. Ngaire dit qu'il y a une structure, en bas. Te Rangi dit que "
					"le père des poissons s'est détourné. Moi, je veux savoir. »",
		 "accepte": "« La cloche de plongée part du bout du quai. Ngaire y descend avec ses instruments. Elle "
					"vous attendra dans la chambre extérieure de la structure. »",
		 "rappel": "« La structure, au bout de la cloche. Le relevé de Ngaire. »",
		 "remettre_label": "Lui remettre le relevé des courants.",
		 "remis": "Tamatoa étale le relevé sur son filet. Les courants y tournent autour d'un point, et les "
				  "flèches des poissons s'y arrêtent toutes, au même endroit, et font demi-tour. « Ils ne "
				  "fuient pas la mer. Ils fuient ça. » Il pose le doigt sur la structure. « Qu'est-ce qu'on "
				  "fait ? »",
		 "souvenir": "« Ça va mieux. Les poissons ne reviennent pas encore. » Il retrousse sa manche. « J'ai "
					 "commencé à apprendre les noms à mon fils. Pour qu'on ne les oublie plus. » Il hausse "
					 "les épaules. « À Mu, on dit que le père des poissons s'est détourné, ou qu'il n'a pas "
					 "entendu. Moi, je ne sais plus. »"},
		[("isoler", "« Aidez Ngaire à isoler la structure. »",
		  "« Isoler. » Il hoche la tête. « Elle a un plan. Elle a toujours un plan. Ça me va. »"),
		 ("rite", "« Suivez Te Rangi dans un rite de mémoire. »",
		  "« Un rite. Pour les morts qui ne sont jamais arrivés chez Tangaroa. » Il serre le filet. « Ceux "
		  "qui reviennent sans corps. On leur doit au moins ça. »"),
		 ("baliser", "« Faites baliser la zone pour les pêcheurs. »",
		  "« Des bouées. » Il grogne. « Pas glorieux. Personne ne se noiera plus pour rien. C'est déjà "
		  "ça. »")])
	te_rangi = temoin(TE_RANGI, "Te Rangi Huatahi", "elfe", "Officiant de Tangaroa, sur le quai de Mu.", "pretre",
		"Un elfe en manteau d'algues tressées, qui jette du sel dans l'eau à intervalles réguliers en "
		"murmurant des noms.",
		[("sel", "« Pourquoi ce sel ? »", None,
		  "« Pour les morts qu'on rend à la mer. Tangaroa est le père des poissons, et c'est à lui qu'on "
		  "confie les morts. » Il jette une pincée. « Ceux qui ne trouvent pas son royaume reviennent. "
		  "Sans corps, la tête seule. Vous en avez peut-être croisé, en haut. »"),
		 ("poissons", "« La zone sans poissons ? »", pendant(Q_POISSONS),
		  "« Le père des poissons s'est détourné de cette mer. Ou il n'a pas entendu, quand le continent "
		  "s'est couché. » Il regarde au loin. « Abandon, impuissance, ou caprice de la mer. Je prie pour "
		  "ne pas savoir. »"),
		 ("apres", "« Et maintenant ? »", apres(Q_POISSONS),
		  "« Les morts de cette zone ont des noms, maintenant. » Il sourit tristement. « Le silence de "
		  "Tangaroa reste une blessure. Elle ne se ferme pas parce qu'on la regarde. »")])
	ngaire = temoin(NGAIRE, "Ngaire Koroneho", "hobbit", "Naturaliste, sur le quai de Mu.", "forestier",
		"Une hobbit entourée d'instruments de cuivre et de verre, qui note la couleur de l'eau toutes les "
		"heures dans un carnet taché de sel.",
		[("instruments", "« Que mesurez-vous ? »", avant(Q_POISSONS),
		  "« Le sel, le mana, la température, les bancs. » Elle tapote une aiguille. « Le monde se laisse "
		  "mesurer, si on est patient. Les dieux, je les laisse à Te Rangi. »"),
		 ("poissons", "« Vous y descendez ? »", pendant(Q_POISSONS),
		  "« Par la cloche, oui. Je vous attends en bas, dans la chambre extérieure. » Elle range ses "
		  "aiguilles. « C'est une structure. Ça se touche, ça se mesure. Il y a une cause. Il y a toujours "
		  "une cause. »"),
		 ("apres", "« Les poissons reviendront ? »", apres(Q_POISSONS),
		  "« Pas tout de suite. » Elle note quelque chose. « Une mer qui a peur met longtemps à oublier. »")])
	ngaire_s = remettant(NGAIRE_STRUCTURE, "Ngaire Koroneho", "hobbit", "Naturaliste, dans la chambre extérieure de la structure.",
		"forestier", Q_POISSONS, RELEVE_COURANTS, E_COURANTS,
		{"accueil": "Dans une chambre de pierre noire qui résonne sourdement, comme une cloche frappée trop "
					"loin, Ngaire a posé ses instruments en cercle. Leurs aiguilles tremblent toutes vers le "
					"même mur.",
		 "regarder_label": "« Plaçons vos relevés. »",
		 "prendre_label": "« Le relevé, pour Tamatoa. »",
		 "donne": "Ngaire roule le relevé et vous le tend. « Cette chambre résonne avec le mana de Mu. Avec "
				  "la bulle. Je ne sais pas pourquoi. » Elle range un instrument. « Je saurai. Pas "
				  "aujourd'hui. »",
		 "apres": "« Je reviens tous les jours. » Elle tapote le mur noir. « Elle chante moins fort. Ou "
				  "j'entends moins bien. »"})
	e = enigme(E_COURANTS, "Les courants de la structure", "placement", STRUCTURE,
		"Sur une carte des courants, trois emplacements marqués par Ngaire : là où les poissons font "
		"demi-tour, là où les instruments s'affolent, là où passent les silhouettes. Placez sur chacun ce "
		"que l'on y relève.",
		{"symboles": [
			{"id": "spirale", "label": "Un courant qui tourne sur lui-même"},
			{"id": "aiguille", "label": "Une aiguille qui tremble vers la structure"},
			{"id": "ombre", "label": "Une ombre immense, au fond"},
			{"id": "banc", "label": "Un banc de poissons qui file droit"},
		], "emplacements": [
			{"id": "demi_tour", "label": "Là où les poissons font demi-tour"},
			{"id": "affolement", "label": "Là où les instruments s'affolent"},
			{"id": "passage", "label": "Là où passent les silhouettes"},
		]},
		{"placement": {"demi_tour": "spirale", "affolement": "aiguille", "passage": "ombre"}},
		"Les trois relevés tombent juste : le courant tourne autour de la structure, les aiguilles la "
		"désignent, et les ombres la contournent. Les poissons ne fuient pas la mer : ils fuient ce qui "
		"résonne ici.",
		"Ngaire efface d'un doigt. « Non. Les poissons ne filent pas droit, là. »",
		[compagnon("forestier", "ouverture", "Les bêtes savent où ne pas aller. Suivez où elles ne vont pas."),
		 compagnon("mage", "echec", "Le mana ne ment pas. Il tremble là où il y a quelque chose."),
		 compagnon("pretre", "reussite", "Une cause, dit-elle. Une cause n'empêche pas un dieu de se taire.")],
		[apport_actif(RELEVE_COURANTS)])
	quai = lieu(QUAI, "Le quai des pêcheurs",
		"Le quai de pierre au bord du bassin intérieur de Mu, où l'eau de mer filtrée vient battre la "
		"bulle. Des barques, des filets qui sèchent, des casiers, et au bout, une cloche de plongée de "
		"bronze pendue à un portique.",
		pnj=[present(TAMATOA, "Tamatoa Paepae", "Un ogre qui ravaude un filet, un tatouage de noms sur l'épaule."),
			 present(TE_RANGI, "Te Rangi Huatahi", "Un elfe en manteau d'algues tressées, qui jette du sel dans l'eau."),
			 present(NGAIRE, "Ngaire Koroneho", "Une hobbit entourée d'instruments de cuivre et de verre.",
					 [{"quete_active": {"types": ["collect"], "cible": RELEVE_COURANTS, "attendu": False}}])])
	structure = lieu(STRUCTURE, "La chambre extérieure de la structure",
		"Une chambre de pierre noire, à demi enfouie au fond de la mer, qu'on atteint par la cloche de "
		"plongée. Elle résonne sourdement, et les instruments s'y affolent.",
		acces={"cycle": 1, "refus": "La cloche de plongée est remontée. Rien ne vous appelle en bas.",
			   "conditions": [ouvert_pour(apport_actif(RELEVE_COURANTS), Q_POISSONS)]},
		pnj=[present(NGAIRE_STRUCTURE, "Ngaire Koroneho", "Une hobbit au milieu d'un cercle d'instruments tremblants.",
					 [ouvert_pour(apport_actif(RELEVE_COURANTS), Q_POISSONS)])])
	return [tamatoa, te_rangi, ngaire, ngaire_s, e, quai, structure,
			lien(QUAI, (0, 0), "Remonter par la cloche", STRUCTURE, "Descendre par la cloche de plongée")]


def affaire_cartographes():
	offre = offre_apport(Q_CARTOGRAPHES, "Les cartographes qui ne dessinent plus",
		"Kauri Tipene, cartographe, appelle à l'aide : deux relevés sûrs d'un même quartier ne concordent "
		"plus, et son collègue Wiremu a disparu pendant une vérification, dans l'ancienne salle des relevés. "
		"Retrouvez-le et rapportez à Kauri la carte qu'il en tirera.", CARTE_INCERTAINE, 180, 1500)
	kauri = donneur(KAURI, "Kauri Tipene", "humain", "Cartographe de Mu, à la salle des cartes.", "lettre", offre,
		apres(Q_CONFIANCE),
		{"accueil": "Un homme aux doigts tachés d'encre, entre deux tables couvertes de cartes de Mu qui se "
					"ressemblent presque. Il passe de l'une à l'autre en comptant à mi-voix.",
		 "offre_label": "« Ces deux cartes ne sont pas pareilles ? »",
		 "propose": "« Elles devraient. Même quartier, mêmes instruments, mêmes mains, à un mois d'écart. » "
					"Il pose les deux index. « Trois pas de différence ici. Cinq là. Wiremu est descendu "
					"vérifier dans l'ancienne salle des relevés. Il n'est pas remonté. Roimata dit que c'est "
					"un faussaire. Ce n'est pas un faussaire. Trouvez-le. »",
		 "accepte": "« L'ancienne salle des relevés, derrière cette porte. On ne s'en sert plus depuis "
					"longtemps. Wiremu, si. »",
		 "rappel": "« L'ancienne salle des relevés. Wiremu. »",
		 "remettre_label": "Lui remettre la carte de Wiremu.",
		 "remis": "Kauri déroule la carte. Les rues y sont tracées d'un trait sûr, et des zones entières "
				  "sont hachurées en gris : incertaines. Il les regarde longtemps. « Il ne promet plus une "
				  "ville fidèle. » Il soupire. « Et Roimata qui le traitait de faussaire. »",
		 "souvenir": "« Wiremu a repris son travail. » Kauri désigne une table où le nain trace, en jurant. "
					 "« Le phénomène revient, par moments. Ça ne prouve pas que les quartiers bougent. Ça "
					 "prouve que nos instruments écoutent le mana autant que la pierre. »"},
		[("temoins", "« Et les anciennes cartes ? »",
		  "« Roimata les garde. Comme témoins de ce que Mu croyait savoir. » Il sourit. « Wiremu reprend "
		  "son travail. Il marquera les zones incertaines, et il ne promettra plus une ville fidèle. »")])
	roimata = temoin(ROIMATA, "Roimata", "hobbit", "Apprentie cartographe, à la salle des cartes.", "lettre",
		"Une jeune hobbit qui recopie une carte trop vieille pour elle, la langue entre les dents.",
		[("faussaire", "« Wiremu, un faussaire ? »", pendant(Q_CARTOGRAPHES),
		  "« Ses cartes ne collent pas aux nôtres. » Elle ne lève pas les yeux. « Soit c'est lui qui se "
		  "trompe, soit c'est la ville. Les villes ne se trompent pas. »"),
		 ("cartes", "« Que recopiez-vous ? »", None,
		  "« Une carte de Mu d'avant la bulle. » Elle souffle sur l'encre. « Il y a des rues qui n'existent "
		  "plus, et des rues qui n'existaient pas. Je les recopie toutes. »"),
		 ("apres", "« Et vos anciennes cartes ? »", apres(Q_CARTOGRAPHES),
		  "« Je les garde. Ce sont des témoins. » Elle sourit. « Wiremu m'a dit pardon. Moi aussi. »")])
	wiremu = remettant(WIREMU, "Wiremu", "nain", "Cartographe, dans l'ancienne salle des relevés.", "lettre",
		Q_CARTOGRAPHES, CARTE_INCERTAINE, E_RELEVES,
		{"accueil": "Un nain hirsute penché sur une table de relevés, entouré de feuilles froissées, qui trace "
					"un trait, le gomme, le retrace, et ne vous a pas entendu entrer.",
		 "regarder_label": "« Séparons ce qui bouge de ce qui ne bouge pas. »",
		 "prendre_label": "« Votre carte, pour Kauri. »",
		 "donne": "Wiremu vous tend une carte où des zones entières sont hachurées de gris. « Les repères "
				  "de la pierre ne bougent pas. Mes instruments, si. Quand le mana tremble, ils mentent. » Il "
				  "s'essuie le front. « Dites à Kauri que je reviens. Dites à Roimata que je ne suis pas "
				  "un faussaire. »",
		 "apres": "« Je ne promets plus une ville fidèle. » Il hausse les épaules. « Je promets une ville "
				  "honnête. »"})
	e = enigme(E_RELEVES, "Les repères de la pierre", "association", RELEVES,
		"Sur les feuilles de Wiremu, des écarts entre deux relevés. Dans ses notes, ce qu'il soupçonne pour "
		"chacun. Rendez chaque écart à sa cause.",
		{"gauche": [
			{"id": "borne", "texte": "Une borne de pierre gravée, au même endroit sur les trois cartes."},
			{"id": "aiguille", "texte": "Une distance qui change selon l'heure du relevé."},
			{"id": "canal", "texte": "Un canal comblé, absent de la carte la plus récente."},
			{"id": "angle", "texte": "Un angle qui dévie d'autant plus qu'on approche du dôme."},
		], "droite": [
			{"id": "fixe", "texte": "Un repère sûr : la pierre."},
			{"id": "mana", "texte": "L'instrument réagit aux variations du mana."},
			{"id": "travaux", "texte": "Un vrai changement, fait par des mains."},
			{"id": "bulle", "texte": "Le trouble vient de la bulle elle-même."},
		]},
		{"paires": {"borne": "fixe", "aiguille": "mana", "canal": "travaux", "angle": "bulle"}, "seuil": 3},
		"Les écarts trouvent leurs causes. Les repères de pierre n'ont pas bougé. Les instruments, si, "
		"chaque fois que le mana tremble. Wiremu pose son crayon pour la première fois depuis des jours.",
		"Wiremu grogne sans lever la tête. « Non. Ça, c'est la pierre. La pierre ne ment pas. »",
		[compagnon("lettre", "ouverture", "Trois cartes de trois époques : ce qui ne change sur aucune est un point fixe."),
		 compagnon("mage", "echec", "Une aiguille qui change avec l'heure, c'est du mana. La pierre n'a pas d'heure."),
		 compagnon("forestier", "reussite", "En forêt aussi, on se fie aux rochers, pas au soleil.")],
		[apport_actif(CARTE_INCERTAINE)])
	cartes = lieu(CARTES, "La salle des cartes",
		"Une longue salle voûtée où des cartes de Mu de toutes les époques sont épinglées aux murs, posées "
		"sur des tables, roulées dans des niches. L'encre et le sel y sentent pareil.",
		categorie="institut_des_architectes",
		pnj=[present(KAURI, "Kauri Tipene", "Un homme aux doigts tachés d'encre, entre deux cartes presque pareilles."),
			 present(ROIMATA, "Roimata", "Une jeune hobbit qui recopie une très vieille carte.")])
	releves = lieu(RELEVES, "L'ancienne salle des relevés",
		"Une salle ronde, sous la salle des cartes, aux murs percés de visées de pierre vers les quatre coins "
		"de la cité. Les instruments y tremblent.",
		acces={"cycle": 1, "refus": "La porte de l'ancienne salle des relevés est fermée. On ne s'en sert plus.",
			   "conditions": [ouvert_pour(apport_actif(CARTE_INCERTAINE), Q_CARTOGRAPHES)]},
		pnj=[present(WIREMU, "Wiremu", "Un nain hirsute penché sur une table de relevés.",
					 [ouvert_pour(apport_actif(CARTE_INCERTAINE), Q_CARTOGRAPHES)])])
	return [kauri, roimata, wiremu, e, cartes, releves,
			lien(CARTES, (0, 0), "Remonter à la salle des cartes", RELEVES, "Descendre à l'ancienne salle des relevés")]


def affaire_gardien():
	offre = offre_apport(Q_GARDIEN, "Le dernier gardien de Mu",
		"Sous une porte condamnée, une vieille sentinelle répond encore à des gestes que nul ne connaît, et "
		"l'on entend parfois des coups derrière la porte. Mahina Rehu veut comprendre son rite avant qu'on "
		"ne tarisse son mana : rapportez-lui ce que la sentinelle garde.", PLAQUE_ARCHIVE, 180, 1500)
	mahina = donneur(MAHINA, "Mahina Rehu", "humain", "Vieille linguiste de l'Institut de Mu.", "lettre", offre,
		apres(Q_CONFIANCE),
		{"accueil": "Une vieille femme aux yeux vifs, entourée de plaques de pierre gravées qu'elle lit du bout "
					"des doigts, comme on lit un visage.",
		 "offre_label": "« Vous lisez la pierre ? »",
		 "propose": "« La pierre, les gestes, les enfants. Ce qui reste quand l'écriture s'en va. » Elle "
					"repose une plaque. « Sous une porte condamnée, une sentinelle de l'ancien temps "
					"attend une marque de reconnaissance qui n'existe dans aucun registre. Rangi veut "
					"tarir son mana pour reprendre la place. Moi, je veux comprendre son rite avant. "
					"Rapportez-moi ce qu'elle garde. »",
		 "accepte": "« La porte condamnée, au sud de la grande place. Elle ne vous attaquera pas. Elle "
					"attend. Elle attend depuis plus longtemps que la bulle. »",
		 "rappel": "« La porte condamnée, au sud de la place. Ce qu'elle garde. »",
		 "remettre_label": "Lui remettre la plaque de l'archive.",
		 "remis": "Mahina lit la plaque, lentement. « Des échanges. Avec une demeure, derrière le portail. » "
				  "Elle relit. « Pas un nom de dieu. Une demeure. Et quelqu'un qui répondait, quand la "
				  "sentinelle frappait. Les réponses ont cessé bien avant le sacrifice. » Elle repose la "
				  "plaque. « Que fait-on d'elle, maintenant ? »",
		 "souvenir": "« La sentinelle veille encore. » Mahina sourit. « Elle a reçu une réponse. Pas celle "
					 "qu'elle attendait. L'archive parle d'une demeure sans dire de qui. Ça me suffit. Ça "
					 "devrait vous suffire. Ça ne vous suffit pas, je le vois. »"},
		[("rite", "« Rendez-lui une part de son rite. »",
		  "« Une part. » Elle hoche la tête. « Elle continuera de frapper. Et quelqu'un, désormais, "
		  "frappera en retour. »"),
		 ("deplacer", "« Déplacez l'archive à l'Institut. »",
		  "« L'archive ici, la sentinelle là-bas. » Elle soupire. « Rangi aura sa citerne. Elle gardera "
		  "une porte vide. »"),
		 ("veiller", "« Laissez-la veiller, avec une réponse symbolique. »",
		  "« Une réponse. » Elle sourit. « C'est ce qu'elle voulait. Pas la bonne. Une. »")],
		extra_accueil=(
			choix("enfants", "« Les enfants de la marée ? »", "enfants", condition=pendant(Q_ENFANTS)),
		),
		extra_noeuds={"enfants": noeud(
			"« Je reconnais des tournures, pas la langue. » Elle pianote sur une plaque. « J'ai écouté les "
			"enfants un à un. Leurs mots font une suite, incomplète. Les mêmes signes sont sur les bornes du "
			"bassin de marée. Je descends voir la chambre du dessous. Ne dites pas mon âge à Ataahua. »",
			choix("ok", "Revenir.", "accueil"))})
	sentinelle = remettant(SENTINELLE, "La sentinelle", "sentinelle", "Une sentinelle de l'ancien temps, sous une porte condamnée.",
		"guerrier", Q_GARDIEN, PLAQUE_ARCHIVE, E_RITE,
		{"accueil": "Une haute figure de pierre et de bronze, debout devant une porte condamnée, une main levée "
					"comme pour frapper. Ses yeux de cristal s'allument faiblement quand vous approchez. "
					"Derrière la porte, un coup sourd. Puis rien.",
		 "regarder_label": "Refaire, devant elle, les gestes gravés sur les plaques.",
		 "prendre_label": "Tendre la main vers la niche qu'elle désigne.",
		 "donne": "La sentinelle abaisse la main, lentement, et ouvre une niche dans son socle. Une plaque "
				  "de pierre y repose. Elle frappe une fois à la porte, et attend. Vous frappez en retour. "
				  "Ses yeux brillent plus fort, une seconde. Ce n'est pas la réponse qu'elle attendait. "
				  "C'est une réponse.",
		 "apres": "La sentinelle frappe à la porte, une fois, à intervalles réguliers. Quand vous êtes là, "
				  "vous répondez. Elle ne devient pas une compagne. Elle reste une gardienne."})
	e = enigme(E_RITE, "Le rite de la sentinelle", "crans", PORTE_CONDAMNEE,
		"Trois plaques gravées autour du socle montrent un geste chacune, en cinq positions : la main basse, "
		"à la hanche, au cœur, à l'épaule, levée. Un trait marque, sur chacune, la position que l'on a usée "
		"à force de la faire.",
		{"pieces": [
			{"id": "salut", "label": "Premier geste : le salut", "crans": 5, "depart": 0},
			{"id": "nom", "label": "Deuxième geste : le nom", "crans": 5, "depart": 0},
			{"id": "porte", "label": "Troisième geste : la porte", "crans": 5, "depart": 0},
		]},
		{"positions": {"salut": 4, "nom": 2, "porte": 3}},
		"La sentinelle répond au dernier geste par un geste à elle : la main levée vers la porte, puis vers "
		"son socle. Une niche s'y dessine.",
		"La sentinelle ne bouge pas. Ses yeux s'éteignent un peu.",
		[compagnon("lettre", "ouverture", "Le trait le plus usé, c'est le geste qu'on a répété des siècles."),
		 compagnon("guerrier", "echec", "Un salut, ça se fait main levée. Partout, depuis toujours."),
		 compagnon("pretre", "reussite", "Elle attendait qu'on lui parle dans sa langue. On n'a dit qu'un mot.")],
		[apport_actif(PLAQUE_ARCHIVE)])
	porte = lieu(PORTE_CONDAMNEE, "La porte condamnée",
		"Une porte murée au sud de la grande place, sous une voûte où l'or du dôme ne descend plus. Devant, "
		"une sentinelle de pierre et de bronze, la main levée.",
		pnj=[present(SENTINELLE, "La sentinelle", "Une figure de pierre et de bronze, la main levée devant une porte murée.",
					 [ouvert_pour(apport_actif(PLAQUE_ARCHIVE), Q_GARDIEN)])])
	return [mahina, sentinelle, e, porte]


def affaire_nom():
	offre = offre_apport(Q_NOM, "Le nom effacé",
		"Rawiri Tane, archiviste, a remarqué une rupture dans une suite de registres : un nom a été gratté "
		"de plusieurs copies. Il veut établir les faits sans déclencher de crise : rapportez-lui la copie "
		"fidèle du dernier rapport de celui qu'on a effacé.", RAPPORT, 180, 1500)
	rawiri = donneur(RAWIRI, "Rawiri Tane", "hobbit", "Archiviste de l'Institut de Mu.", "lettre", offre, apres(Q_CONFIANCE),
		{"accueil": "Un hobbit méticuleux, des lunettes de nacre sur le nez, qui range des registres par "
					"ordre de taille puis les dérange par ordre de date, en soupirant.",
		 "offre_label": "« Un registre vous pose problème ? »",
		 "propose": "« Une rupture. » Il ouvre trois registres côte à côte. « Les pages sont intactes. Mais "
					"ici, ici et ici, un nom a été gratté. Le même, je crois. Un dignitaire, du temps du "
					"sacrifice. » Il referme. « Je veux les faits. Pas une crise. La réserve des registres "
					"est derrière moi. Sa descendante y travaille sans savoir qui il était. »",
		 "accepte": "« Huia Ruawai. Elle recopie des listes de maintenance, à la réserve. Elle porte son nom "
					"sans le savoir. Allez-y doucement. »",
		 "rappel": "« La réserve des registres. Le dernier rapport. Doucement. »",
		 "remettre_label": "Lui remettre la copie fidèle du dernier rapport.",
		 "remis": "Rawiri lit, et ses lunettes glissent. « Il demandait que les dieux rendent compte de la "
				  "porte, et du silence qui répondait aux prières. » Il relit. « Il ne dit pas que les dieux "
				  "ont fait la porte. Il demande pourquoi on continue de les prier. On l'a effacé pour "
				  "ça. » Il pose le rapport. « Ceux qui jugeaient que la survie de Mu exigeait de se taire. "
				  "Que fait-on de lui ? »",
		 "souvenir": "« Le nom est revenu, au moins dans une copie fidèle. » Il remonte ses lunettes. « Les "
					 "uns disent courage, les autres, mise en danger de la cité. Hemi Taurua ne dit rien, ce "
					 "qui est sa façon de dire beaucoup. L'affaire est close dans les archives. Pas dans les "
					 "consciences. »"},
		[("public", "« Rendez le nom public. »",
		  "« Public. » Il pâlit, puis acquiesce. « On en parlera au marché demain. On en parlera encore "
		  "dans cent ans. Rien ne s'effondrera. Rien ne sera pareil. »"),
		 ("discret", "« Rétablissez-le discrètement dans les archives. »",
		  "« Discrètement. » Il soupire de soulagement. « Une ligne réécrite. Qui cherchera, trouvera. »"),
		 ("depositaire", "« Confiez les preuves à un dépositaire indépendant. »",
		  "« Hors de l'Institut, hors des Templiers. » Il réfléchit. « Tamatoa, peut-être. Il garde déjà "
		  "des noms sur son épaule. »")])
	huia = remettant(HUIA, "Huia Ruawai", "elfe", "Copiste, à la réserve des registres de Mu.", "lettre", Q_NOM, RAPPORT, E_REGISTRES,
		{"accueil": "Une elfe aux longs doigts, penchée sur une liste de maintenance qu'elle recopie d'une "
					"écriture parfaite. Elle lève la tête, aimable, sans savoir pourquoi vous êtes là.",
		 "regarder_label": "« Puis-je voir ces registres avec vous ? »",
		 "prendre_label": "« Recopiez-moi ce rapport, Huia. Fidèlement. »",
		 "donne": "Huia recopie, et sa plume ralentit sur le nom. Le sien. « Mon aïeul. » Elle finit la "
				  "copie, la sèche, vous la tend. « On m'a toujours dit qu'il était mort avec le continent. "
				  "On ne m'a jamais dit qu'il avait posé une question. »",
		 "apres": "« Je sais ce qu'il a demandé. » Elle sourit, triste et fière. « Je ne sais pas s'il avait "
				  "raison. Je sais qu'il avait le droit de le demander. »"})
	e = enigme(E_REGISTRES, "Les registres grattés", "deduction", RESERVE,
		"Listes de responsables, actes de maintenance, copies d'un même registre. Un nom manque, ici et là. "
		"Les pages, elles, sont intactes.",
		{"indices": [
			{"id": "listes", "label": "Les listes de responsables", "fait": "Un siège de dignitaire est vide sur trois ans, au temps du sacrifice. Personne n'y a été nommé."},
			{"id": "actes", "label": "Les actes de maintenance", "fait": "Des actes de cette période sont contresignés d'un sceau sans nom : celui du siège vide."},
			{"id": "copies", "label": "Les copies recoupées", "fait": "Sur une copie oubliée au fond de la réserve, le nom n'a pas été gratté : Ruawai."},
			{"id": "encre", "label": "L'encre des grattages", "fait": "Les grattages sont tous de la même main, faits la même année."},
			{"id": "rapport", "label": "Le dernier rapport du siège", "fait": "Un rapport de ce siège, sans nom, demande que les dieux rendent compte de la porte."},
		], "conclusions": [
			{"id": "erreur", "label": "Un copiste maladroit a abîmé les registres."},
			{"id": "efface", "label": "On a effacé le dignitaire Ruawai, d'une seule main, à cause de ce qu'il demandait."},
			{"id": "traitre", "label": "Ruawai a trahi Mu, et ses crimes ont été effacés avec lui."},
		]},
		{"conclusion": "efface", "indices": ["copies", "encre", "rapport"], "seuil": 2},
		"Une seule main, une seule année, et sur une copie oubliée, le nom : Ruawai. Son siège rendu, son "
		"dernier rapport retrouvé. Huia lève la tête de sa liste.",
		"Les registres se taisent. Ce n'est pas ça.",
		[compagnon("lettre", "examen:copies", "Il reste toujours une copie qu'on a oubliée. Toujours."),
		 compagnon("voleur", "examen:encre", "Une seule main. Quelqu'un a reçu l'ordre de le faire."),
		 compagnon("pretre", "examen:rapport", "Demander des comptes aux dieux. On a brûlé des gens pour moins, ailleurs.")],
		[apport_actif(RAPPORT)])
	reserve = lieu(RESERVE, "La réserve des registres",
		"Une réserve basse aux étagères chargées de registres reliés de cuir de poisson, derrière l'Institut. "
		"Une lampe, une table de copiste, et le silence des choses qu'on garde.",
		parent=MU, acces={"cycle": 1, "refus": "La réserve des registres n'est ouverte qu'aux archivistes.",
						  "conditions": [ouvert_pour(apport_actif(RAPPORT), Q_NOM)]},
		pnj=[present(HUIA, "Huia Ruawai", "Une elfe penchée sur une liste de maintenance, d'une écriture parfaite.")])
	return [rawiri, huia, e, reserve,
			lien(INSTITUT, (0, 0), "Revenir à l'Institut", RESERVE, "Entrer dans la réserve des registres")]


# ---------------------------------------------------------------------------------------------
# Lieux de ville, liens, objets
# ---------------------------------------------------------------------------------------------

def lieux_ville():
	ouvrages = lieu(OUVRAGES, "Les ouvrages de la périphérie",
		"Un atelier de pierre contre la lisière, où des clés à vanne pendent aux murs à côté de grilles "
		"tordues. Partout, le bruit de l'eau qui court dans les conduites, et l'odeur de la vase.",
		pnj=[present(RANGI, "Rangi Waiora", "Un nain trapu penché sur un plan de conduites épinglé à la pierre.")])
	institut = lieu(INSTITUT, "L'Institut de Mu",
		"Une salle haute sous une coupole d'or pâle, où des vasques de corail vivant luisent d'un jaune très "
		"doux. Des Architectes y parlent bas, et se taisent quand un étranger entre.",
		categorie="institut_des_architectes",
		pnj=[present(ANA, "Ana Hereheretue", "Une elfe aux tresses de nacre, devant une vasque de corail jaune."),
			 present(MAHINA, "Mahina Rehu", "Une vieille femme qui lit des plaques de pierre du bout des doigts."),
			 present(RAWIRI, "Rawiri Tane", "Un hobbit à lunettes de nacre, au milieu de registres."),
			 present(MERE, "Mere Tapuni", "Une ogresse aux mains fines, qui recolle un tesson au pinceau.")])
	reseau = lieu(RESEAU, "Le réseau ancien",
		"Derrière les ouvrages, des galeries plus anciennes que les plans, des bassins de régulation en "
		"gradins reliés par des vannes de pierre, et une eau qui tourne en rond.",
		acces={"cycle": 1, "refus": "Rangi garde la porte du réseau ancien fermée.",
			   "conditions": [{"ou": [escorte_active(CHAMBRE), apres(Q_DESCENTE)]}]})
	chambre = lieu(CHAMBRE, "La chambre du sceau",
		"Une chambre absente de tous les plans, au fond du réseau ancien. Une porte immense, scellée, des "
		"fresques usées, une inscription des Tables de Pierre. La pierre vibre sous la main.",
		acces={"cycle": 1, "refus": "L'escalier sous le dernier bassin est noyé. L'eau ne descend pas.",
			   "conditions": [{"enigme_resolue": {"id": E_VANNES}}, {"ou": [escorte_active(CHAMBRE), apres(Q_DESCENTE)]}]},
		pnj=[present(AELIS_SCEAU, "Aélis", "Aélis, assise face à la porte, le carnet sur les genoux.",
					 [apres(Q_DESCENTE), {"enigme_resolue": {"id": E_SCELLEMENT, "attendu": False}}])])
	chambre["pnj"][0]["portrait"] = PORTRAIT_AELIS_DIALOGUE
	liens = [lien(MU, PORTES_MU[lid], label_mu, lid, label_lieu)
			 for lid, label_mu, label_lieu in (
				 (OUVRAGES, "Ressortir sur la lisière", "Entrer aux ouvrages de la périphérie"),
				 (JARDINS, "Quitter les jardins", "Aller aux jardins de la paroi"),
				 (INSTITUT, "Ressortir sur la place", "Entrer à l'Institut de Mu"),
				 (ATELIER, "Ressortir de l'atelier", "Entrer chez le souffleur de vasques"),
				 (QUAI, "Quitter le quai", "Aller au quai des pêcheurs"),
				 (DEPOT, "Ressortir du secteur condamné", "Entrer au dépôt de maintenance"),
				 (CHAMBRE_HYDRAULIQUE, "Remonter au bassin de marée", "Descendre sous le bassin de marée"),
				 (CARTES, "Ressortir de la salle des cartes", "Entrer à la salle des cartes"),
				 (PORTE_CONDAMNEE, "Revenir sur la place", "Aller à la porte condamnée"))]
	liens += [
		lien(OUVRAGES, (0, 0), "Remonter aux ouvrages", RESEAU, "Descendre dans le réseau ancien"),
		lien(RESEAU, (0, 0), "Remonter dans le réseau ancien", CHAMBRE, "Descendre à la chambre du sceau"),
		lien(CHAMBRE, (0, 0), "Remonter à la chambre du sceau", ANTRE, "Passer derrière les fresques"),
	]
	return [ouvrages, institut, reseau, chambre] + liens


def objets():
	return [
		item_quete(PIECE_SAS, "Pièce de sas", "Un anneau de bronze à joint de cuir, de quoi rouvrir le sas d'un "
				   "jardin de la lisière, à Mu.", icon="⚙️", poids=1.5, categorie="composant"),
		item_quete(REGISTRE, "Registre du souffleur de vasques", "Le registre de Koro Hapai : les vasques soufflées, "
				   "et pour qui. Une commande au nom de l'Institut n'y porte pas son sceau."),
		item_quete(ECAILLE, "Écaille d'Échidna", "Une écaille bleu nuit et or, large comme une main ouverte, encore "
				   "tiède. Échidna l'a arrachée à son flanc pour qu'on la porte aux Architectes de Mu.",
				   icon="🐍", poids=2, categorie="composant"),
		item_quete(COPIE_RELEVE, "Copie partielle du relevé des seuils", "Une part du relevé des seuils naturels "
				   "que tient le siège d'Uanna, à Mu. Quatre lignes y portent le mot « demeure » : la porte sous "
				   "la cité, Saint-Pierre, l'Hekla, un arbre du nord. L'original reste à Mu.",
				   sous_categorie="releve_des_seuils"),
		item_quete(FRAGMENTS_CHANT, "Estampage des fragments du chant", "Les fragments du chant de la coque d'or, "
				   "relevés sur les murs du sanctuaire noyé de Tangaroa."),
		item_quete(INVENTAIRE_DEPOT, "Inventaire du dépôt de maintenance", "Le carnet graisseux de Piripi Ngata : "
				   "ce qui est sorti du dépôt condamné, et ce qui y reste."),
		item_quete(TABLETTE, "Tablette des bassins", "Une tablette de pierre tirée de la chambre hydraulique, "
				   "et épinglée dessus, la traduction de Mahina Rehu : une formule de prudence des bassins.",
				   icon="🪨", poids=3),
		item_quete(RELEVE_COURANTS, "Relevé des courants de la structure", "Les courants autour d'une structure "
				   "immergée, au large de Mu, et l'endroit où les poissons font demi-tour."),
		item_quete(CARTE_INCERTAINE, "Carte des zones incertaines", "Une carte d'un quartier de Mu par Wiremu, "
				   "les zones où les instruments mentent hachurées de gris.", icon="🗺️"),
		item_quete(PLAQUE_ARCHIVE, "Plaque de l'archive de la sentinelle", "Une plaque de pierre gardée par la "
				   "sentinelle de la porte condamnée. Elle parle d'échanges avec une « demeure », derrière le "
				   "portail, sans nommer aucun dieu.", icon="🪨", poids=4),
		item_quete(RAPPORT, "Copie fidèle du dernier rapport", "Le dernier rapport du dignitaire Ruawai, recopié "
				   "par sa descendante : il demandait pourquoi l'on continuait à prier les dieux."),
	]


# ---------------------------------------------------------------------------------------------
# Contrôles et écriture
# ---------------------------------------------------------------------------------------------

def _portes_praticables(par_id):
	"""Chaque porte neuve sur une case praticable de Mu, reliée au seuil (BFS 4-voisins sur `cells`)."""
	cells = par_id[MU].get("cells") or []
	depart = P.POS_SEUIL
	vus, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
			if 0 <= ny < len(cells) and 0 <= nx < len(cells[ny]) and cells[ny][nx] == 1 and (nx, ny) not in vus:
				vus.add((nx, ny))
				pile.append((nx, ny))
	portes = dict(PORTES_MU, **{AUBERGE: P.POS_AUBERGE, MARCHE: P.POS_MARCHE})
	return [f"porte de {lid} {pos} injoignable depuis le seuil" for lid, pos in portes.items() if tuple(pos) not in vus]


REQUIS = (MU, SEUIL, AUBERGE, MARCHE, AELIS_MU, TEMPLIER, AUBERGISTE, MARCHANDE, "link:fare_des_marees_to_mu",
		  *CARTES_PROVISOIRES.values())


def generer(par_id, rangs_fn=None):
	"""`rangs_fn(docs) → {_id: rang}` : rang des espèces neuves (défaut : mesuré par le moteur, qui
	remplace `db.config.get_doc` dans tout le process — les tests l'injectent)."""
	for requis in REQUIS:
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	fautes = _portes_praticables(par_id)
	if fautes:
		sys.exit("ERREUR :\n  " + "\n  ".join(fautes))
	relus = [moana(par_id[AUBERGISTE]), kahu(par_id[MARCHANDE]), hemi(par_id[TEMPLIER]), aelis_mu(par_id[AELIS_MU]),
			 lieu_auberge(par_id[AUBERGE]), lieu_marche(par_id[MARCHE]), lien_auberge(par_id["link:fare_des_marees_to_mu"])]
	neufs = (lieux_ville() + objets() + quete_eaux(par_id) + quete_service(par_id) + quete_confiance()
			 + quete_descente() + quete_echidna(par_id) + affaire_chant() + affaire_marchand() + affaire_enfants()
			 + affaire_poissons() + affaire_cartographes() + affaire_gardien() + affaire_nom())
	return M.docs_monstres(par_id, rangs_fn) + relus + neufs


def main(argv):
	with open(V.dernier_dump(argv), encoding="utf-8") as f:
		dump = json.load(f)
	par_id = {d["_id"]: d for d in dump["docs"]}
	docs = generer(par_id)
	fautes = V.controler(docs, par_id)
	if fautes:
		sys.exit("ERREUR :\n  " + "\n  ".join(fautes))
	docs = [d for d in docs if d["_id"] not in par_id or sans_rev(par_id[d["_id"]]) != d]
	if not docs:
		print("Rien à importer : le dump est à jour.")
		return
	print("Neufs :", len([d for d in docs if d["_id"] not in par_id]), "· retouchés :",
		  ", ".join(d["_id"] for d in docs if d["_id"] in par_id) or "aucun")
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)

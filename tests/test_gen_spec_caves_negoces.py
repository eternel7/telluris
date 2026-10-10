"""Ajout de caves et de négoces aux cités peuplées : fonctions pures de `dev/gen_spec_caves_negoces.py`."""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_magasins  # noqa: E402
import gen_spec_caves_negoces as g  # noqa: E402

# Grille 15x15 en terrain 1, quatre portes intérieures en carré, une boutique déjà posée au centre.
CITE = "lieu:test"
PORTES = [(2, 2), (12, 2), (12, 12), (2, 12)]
SEUIL_EXISTANT = (7, 7)

REPERTOIRE = {
	"PRENOMS": {"defaut": {"M": ["Jean", "Paul", "Luc", "Marc"], "F": ["Anne", "Rose", "Lise", "Eve"]}},
	"NOMS": {"defaut": ["Martin", "Bernard", "Petit", "Durand", "Leroy", "Moreau"]},
	"PRENOM_RACE_MUTUALISEE": "humain",
	"PRENOM_MUTUALISE_PROBA": 0.0,
}


def _lien(i, cite, pos, lieu):
	return {"_id": f"link:x{i}", "type": "connection", "nodes": [{"lieu": cite, "pos": list(pos)}, {"lieu": lieu, "pos": [0, 0]}]}


def _docs(cite=CITE, grille=15):
	docs = [{"_id": cite, "type": "lieu", "label": "Test", "cells": [[1] * grille for _ in range(grille)]},
			{"_id": "pnj:marchand_cave", "type": "pnj"},
			{"_id": "pnj:marchand_boucherie", "type": "pnj"},
			{"_id": "lieu:etal", "type": "lieu", "label": "L'Étal", "categorie": "boucherie", "lieu_parent": cite,
			 "pnj": [{"character": "pnj:marchand_boucherie", "nom": "Jean Martin"}]}]
	for i, p in enumerate(PORTES):
		docs.append({"_id": f"lieu:p{i}_interieur", "type": "lieu"})
		docs.append(_lien(i, cite, p, f"lieu:p{i}_interieur"))
	docs.append(_lien(9, cite, SEUIL_EXISTANT, "lieu:etal"))
	return docs


def test_spec_pose_le_compte_demande_hors_des_seuils_et_sur_terrain_1():
	docs = _docs()
	spec, _rapport = g.construire_spec(docs, CITE, {"cave": 3, "negociant": 2}, REPERTOIRE)
	poses = [tuple(m["pos"]) for m in spec["magasins"]]
	assert sorted(m["categorie"] for m in spec["magasins"]) == ["cave"] * 3 + ["negociant"] * 2
	assert len(set(poses)) == len(poses)
	assert not set(poses) & (set(PORTES) | {SEUIL_EXISTANT})


def test_labels_distincts_hors_base_et_varies():
	docs = _docs()
	spec, _ = g.construire_spec(docs, CITE, {"cave": 4}, REPERTOIRE)
	labels = [m["label"] for m in spec["magasins"]]
	assert len(set(labels)) == len(labels)
	assert "L'Étal" not in labels


def test_labels_varies_ne_redisent_ni_tournure_ni_toponyme():
	pris = set()
	labels = g.labels_varies("cave", 4, "lieu:lutecia", set(), pris, random.Random(1))
	tournures = [l.rsplit(" d", 1)[0] for l in labels]
	assert len(labels) == 4 and len(set(tournures)) == 4
	assert len([p for p in pris if p.startswith("P:")]) == 4


def test_tenanciers_de_lignee_connue_et_portrait_generique_du_metier():
	spec, _ = g.construire_spec(_docs(), CITE, {"cave": 6}, REPERTOIRE)
	for m in spec["magasins"]:
		race, sexe, metier = m["portrait"].split("_")[1:4]
		assert race in g.LIGNEES and sexe in ("m", "f") and metier.startswith("cave")
		assert m["nom"] and m["image"] == g.IMAGE_PROVISOIRE["cave"]


def test_relancer_redonne_la_meme_spec():
	assert g.construire_spec(_docs(), CITE, {"cave": 3}, REPERTOIRE) == \
		g.construire_spec(_docs(), CITE, {"cave": 3}, REPERTOIRE)


def test_cite_sur_seuils_pose_sur_une_boutique_existante_jamais_sur_une_porte():
	cite = next(iter(g.SUR_SEUILS))
	docs = _docs(cite)
	spec, _ = g.construire_spec(docs, cite, {"cave": 1}, REPERTOIRE)
	assert [tuple(m["pos"]) for m in spec["magasins"]] == [SEUIL_EXISTANT]


def test_gen_magasins_accepte_la_spec_et_pose_le_tenancier_de_la_cave():
	docs = _docs()
	spec, _ = g.construire_spec(docs, CITE, {"cave": 2}, REPERTOIRE)
	res = gen_magasins.construire(docs, spec, set())
	assert res["erreurs"] == []
	lieux = [d for d in res["docs"] if d["type"] == "lieu"]
	assert len(lieux) == 2
	assert all(d["pnj"][0]["character"] == "pnj:marchand_cave" and d["pnj"][0]["nom"] for d in lieux)


def test_le_lot_demande():
	# Constante voulue : la demande de l'auteur (10/10/2026).
	assert g.LOT == {"lieu:rhemi": {"cave": 4}, "lieu:auxerre": {"cave": 3}, "lieu:chartres": {"cave": 2},
					 "lieu:lutecia": {"cave": 6, "negociant": 3}}

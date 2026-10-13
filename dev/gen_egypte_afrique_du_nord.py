"""Égypte ↔ Afrique du Nord — la frontière, sur le modèle de France ↔ plaine européenne.

Bibliothèque de `dev/gen_villes_pays.py` (qui écrit le fichier à importer unique) ; pas de
point d'entrée propre. Règle des frontières de `gen_plaine_europeenne` : le territoire du
voisin que montre une carte est mis à 0, la connexion se pose SUR la frontière, du côté
accessible, et chaque passage est NOMMÉ.

  · ÉGYPTE — la Libye qu'elle montre à l'ouest de la frontière dessinée (`FRONTIERE_EGYPTE`)
    et le cadre du bas (`CADRE_SUD_EGYPTE`) mis à 0 : le bas de la carte (vers 25° N) est
    lui aussi une frontière avec l'Afrique du Nord — la Haute-Égypte et la Nubie y sont.
  · AFRIQUE DU NORD — l'Égypte qu'elle montre (`FRONTIERE_AFRIQUE`) mise à 0 : à l'est du
    25e méridien, jusqu'à la latitude du bas de la carte d'Égypte (Louxor dessinée en
    y ≈ 26 sur les deux cartes à leur échelle). L'Anatolie, le Levant et l'Arabie du haut de
    la carte, au-delà du Sinaï, sont pris avec : ils ne se joignaient que par lui.
    L'ÉGYPTE FAIT FOI (carte plus détaillée) : l'Afrique du Nord est ensuite RECALÉE sur
    elle (`frontieres_calees.recaler`) — toute case qui tombe dans la terre de l'Égypte est
    mise à 0 ; `FRONTIERE_AFRIQUE` reste la bande d'origine.
  · DEUX TRONÇONS (`TRONCONS`) : l'ouest, de la Méditerranée vers le sud ; le sud, d'ouest
    en est jusqu'à la mer Rouge (le cadre de chaque ligne s'arrête à son rivage).

DENSITÉ (choix de l'Auteur, 12/10) : l'Égypte est dessinée ~2,5 fois plus grand. Une case
sur deux est comptée côté AFRIQUE DU NORD (`postes`) ; côté Égypte, chaque passage se pose
sur la case de sa ligne la plus proche de la projection du poste
(`frontieres_calees.liens_projetes`) — les deux bouts se font face.

⚠️ Une connexion déjà en base dont un nœud tombe dans le territoire mis à 0 est signalée
(avertissement) : la retirer à la main (🧾 JSON → 🗑) — c'est le cas des liens Alexandrie et
Le Caire ↔ Afrique du Nord, que remplacent leurs liens vers l'Égypte.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import frontieres_calees  # noqa: E402
from dev.gen_plaine_europeenne import bande, fermer, sans_rev, zone_de  # noqa: E402

EGYPTE = "lieu:egypte"
AFRIQUE = "lieu:afrique_du_nord"

ANCRE_EGYPTE = (40, 30)    # désert occidental
ANCRE_AFRIQUE = (40, 30)   # Hoggar

# La LIBYE sur la carte d'Égypte, mise à 0 : (y_min, y_max, x) ⇒ cases x ≤ `x`. La frontière
# dessinée descend de la côte de Sollum, s'infléchit à l'ouest de Siwa puis file droit au sud.
FRONTIERE_EGYPTE = ((0, 12, 7), (13, 18, 6), (19, 47, 7))
# Le CADRE du bas de la carte d'Égypte, mis à 0 : (x_min, x_max, y) ⇒ cases y ≥ `y`.
CADRE_SUD_EGYPTE = ((0, 87, 45),)

# L'ÉGYPTE sur la carte d'Afrique du Nord, mise à 0 : (y_min, y_max, x) ⇒ cases x ≥ `x`.
FRONTIERE_AFRIQUE = ((0, 27, 62),)

# DEUX TRONÇONS, chacun réparti à part (sinon les postes de l'ouest d'une carte tomberaient sur
# le sud de l'autre) : nom → (cadre sur l'Égypte, cadre sur l'Afrique du Nord, départs) ; un
# cadre (x_min, x_max, y_min, y_max) borne la ligne, de la côte à la mer Rouge exclue. Lignes
# de l'Afrique du Nord RECALÉE : le long du cadre ouest de la carte d'Égypte, puis de son bas.
TRONCONS = {
	"ouest": ((7, 8, 9, 43), (56, 56, 0, 28), (7, 9), (56, 17)),
	"sud": ((9, 87, 44, 44), (57, 87, 29, 29), (9, 44), (57, 29)),
}

# Noms par tronçon — l'ouest du nord au sud le long du 25e méridien, le sud d'ouest en est le
# long du bas de la carte d'Égypte (vers 25° N) : un par poste de l'Afrique du Nord.
# ⚠️ Rang = suffixe d'`_id`, numérotés à la suite (cf. gen_plaine_europeenne.PASSAGES_PLAINE).
# ABOU SIMBEL n'est PAS sur la carte d'Égypte (elle s'arrête sous Louxor) : elle est dessinée
# sur l'Afrique du Nord en (76, 32), au bord du Nil, au sud du territoire mis à 0. Le dernier
# passage du sud tombe sur le Nil de l'Égypte, qui fait foi (Égypte x 64 sous Louxor ; Afrique
# du Nord x 79, à trois cases du Nil qu'elle dessine) : il porte son nom — c'est la route qui
# y mène. Les autres suivent le désert occidental de l'Égypte, d'ouest en est.
ABOU_SIMBEL_AFRIQUE = (76, 32)
# Le Nil au bas de la carte d'Égypte (sous Louxor) : la route d'Abou Simbel y part.
NIL_EGYPTE = (64, 44)
PASSAGES = {
	"ouest": (
		"Port de Sollum", "Piste de Jaghboub", "Oasis de Siwa", "Piste de Koufra",
		"Plateau du Gilf Kébir", "Djebel Ouweinat",
	),
	"sud": (
		"Lisière sud de la Grande Mer de Sable", "Piste d'Abou Ballas", "Piste de Bir Tarfawi",
		"Oasis de Dakhla", "Oasis de Baris", "Oasis de Kharga", "Darb el-Arbaïn",
		"Piste de Sélima", "Oasis de Dounqoul", "Piste de Kourkour", "Route d'Assouan",
		"Route d'Abou Simbel",
	),
}


def preparer_egypte(egypte):
	"""Le doc de l'Égypte (copie, `_rev` retiré), la Libye et le cadre du bas à 0."""
	doc = sans_rev(copy.deepcopy(egypte))
	fermer(doc["cells"], bande(FRONTIERE_EGYPTE, "ouest", doc["dimensions"]))
	fermer(doc["cells"], bande(CADRE_SUD_EGYPTE, "sud", doc["dimensions"]))
	return doc


def preparer_afrique(afrique, egypte):
	"""Le doc de l'Afrique du Nord (copie, `_rev` retiré), l'Égypte qu'elle montre à 0, puis
	recalée sur `egypte` (préparée), qui fait foi."""
	doc = sans_rev(copy.deepcopy(afrique))
	fermer(doc["cells"], bande(FRONTIERE_AFRIQUE, "est", doc["dimensions"]))
	frontieres_calees.recaler(doc, egypte,
		zone_de(egypte["cells"], egypte.get("nav") or {}, ANCRE_EGYPTE),
		bande(FRONTIERE_AFRIQUE, "est", doc["dimensions"]),
		bande(FRONTIERE_EGYPTE, "ouest", egypte["dimensions"])
		| bande(CADRE_SUD_EGYPTE, "sud", egypte["dimensions"]))
	return doc


def lignes(egypte, afrique):
	"""{tronçon: (ligne de l'Égypte, ligne de l'Afrique du Nord)} sur les docs PRÉPARÉS."""
	zone_e = zone_de(egypte["cells"], egypte.get("nav") or {}, ANCRE_EGYPTE)
	zone_a = zone_de(afrique["cells"], afrique.get("nav") or {}, ANCRE_AFRIQUE)
	sortie = {}
	for nom, (cadre_e, cadre_a, depart_e, depart_a) in TRONCONS.items():
		ligne_a, ligne_e = frontieres_calees.lignes(afrique, zone_a, egypte, zone_e,
			depart_a, depart_e, cadre_a, cadre_e)
		sortie[nom] = (ligne_e, ligne_a)
	return sortie


def connexions(lignes_par_troncon, libelles):
	"""(docs, refus, avertissements) : un lien `link:afrique_du_nord_to_egypte_NN` par nom,
	une case sur deux côté Afrique du Nord, chacun face à sa projection côté Égypte."""
	prefixe = "link:afrique_du_nord_to_egypte"
	docs, refus, avert = [], [], []
	for troncon, (ligne_e, ligne_a) in lignes_par_troncon.items():
		d, r, a = frontieres_calees.liens_projetes(prefixe, AFRIQUE, ligne_a, EGYPTE, ligne_e,
			PASSAGES[troncon], libelles, rang0=len(docs))
		docs += d
		refus += [f"{x} ({troncon})" for x in r]
		avert += [f"{x} ({troncon})" for x in a]
	return docs, refus, avert


def connexions_coupees(docs, egypte, afrique):
	"""Avertissements : connexions en base dont un nœud tombe sur une case mise à 0 ici."""
	cells = {EGYPTE: egypte["cells"], AFRIQUE: afrique["cells"]}
	avert = []
	for d in docs:
		if d.get("type") != "connection" or str(d.get("_id", "")).startswith("link:afrique_du_nord_to_egypte_"):
			continue
		for n in d.get("nodes") or []:
			grille = cells.get(n.get("lieu"))
			x, y = (n.get("pos") or (None, None))[:2]
			if grille is not None and x is not None and 0 <= y < len(grille) \
					and 0 <= x < len(grille[y]) and grille[y][x] == 0:
				avert.append(f"{d['_id']} : nœud {n['lieu']} {n['pos']} dans le territoire mis à 0 "
					"— à retirer à la main (🧾 JSON → 🗑)")
	return avert


def construire(docs, libelles):
	"""(lieux, liens, refus, avertissements) : Égypte et Afrique du Nord frontières posées, et
	les passages. `lieux` = docs complets, émis par l'appelant s'ils diffèrent du dump."""
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (EGYPTE, AFRIQUE) if not (par_id.get(i) or {}).get("cells")]
	if manquants:
		return [], [], [f"absent(s) du dump ou sans grille : {', '.join(manquants)}"], []
	egypte = preparer_egypte(par_id[EGYPTE])
	afrique = preparer_afrique(par_id[AFRIQUE], egypte)
	liens, refus, avert = connexions(lignes(egypte, afrique), libelles)
	liens += frontieres_calees.liens_perimes(docs, "link:afrique_du_nord_to_egypte_",
		{l["_id"] for l in liens})
	return [egypte, afrique], liens, refus, avert + connexions_coupees(docs, egypte, afrique)

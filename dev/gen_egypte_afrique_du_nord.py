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
  · DEUX TRONÇONS (`TRONCONS`) : l'ouest, de la Méditerranée vers le sud ; le sud, d'ouest
    en est jusqu'à la mer Rouge (le cadre de chaque ligne s'arrête à son rivage).

DENSITÉ (choix de l'Auteur, 12/10) : l'Égypte est dessinée ~4,5 fois plus grand. Une case
sur deux est comptée côté AFRIQUE DU NORD (`ligne[0::2]`) ; côté Égypte, les mêmes passages
sont RÉPARTIS sur tout le tronçon (`postes`) — un tous les ~5 cases au lieu d'une sur deux.

⚠️ Une connexion déjà en base dont un nœud tombe dans le territoire mis à 0 est signalée
(avertissement) : la retirer à la main (🧾 JSON → 🗑) — c'est le cas des liens Alexandrie et
Le Caire ↔ Afrique du Nord, que remplacent leurs liens vers l'Égypte.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_plaine_europeenne import (  # noqa: E402
	bande, connexion, fermer, ligne_frontiere, postes, sans_rev, zone_de)

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
# cadre (x_min, x_max, y_min, y_max) borne la ligne, de la côte à la mer Rouge exclue.
TRONCONS = {
	"ouest": ((7, 8, 9, 44), (61, 61, 13, 27), (8, 9), (61, 13)),
	"sud": ((9, 76, 44, 44), (62, 78, 28, 28), (9, 44), (62, 28)),
}

# Noms par tronçon — l'ouest du nord au sud le long du 25e méridien, le sud d'ouest en est le
# long du bas de la carte d'Égypte (vers 25° N) : un par poste de l'Afrique du Nord.
# ⚠️ Rang = suffixe d'`_id`, numérotés à la suite (cf. gen_plaine_europeenne.PASSAGES_PLAINE).
# ABOU SIMBEL n'est PAS sur la carte d'Égypte (elle s'arrête sous Louxor) : elle est dessinée
# sur l'Afrique du Nord en (76, 32), au bord du Nil, au sud du territoire mis à 0. Le passage
# posé au plus près du Nil (8e du sud : Afrique du Nord x 76, Égypte x 67 sous Louxor) porte
# donc son nom — c'est la route qui y mène.
ABOU_SIMBEL_AFRIQUE = (76, 32)
PASSAGES = {
	"ouest": (
		"Port de Sollum", "Col d'Halfaya", "Piste de Jaghboub", "Oasis de Siwa",
		"Lisière nord de la Grande Mer de Sable", "Piste de Koufra", "Plateau du Gilf Kébir",
		"Djebel Ouweinat",
	),
	"sud": (
		"Lisière sud de la Grande Mer de Sable", "Piste d'Abou Ballas", "Oasis de Dakhla",
		"Oasis de Kharga", "Darb el-Arbaïn", "Piste de Kourkour", "Route d'Esna",
		"Route d'Abou Simbel", "Route de Bérénice",
	),
}


def preparer_egypte(egypte):
	"""Le doc de l'Égypte (copie, `_rev` retiré), la Libye et le cadre du bas à 0."""
	doc = sans_rev(copy.deepcopy(egypte))
	fermer(doc["cells"], bande(FRONTIERE_EGYPTE, "ouest", doc["dimensions"]))
	fermer(doc["cells"], bande(CADRE_SUD_EGYPTE, "sud", doc["dimensions"]))
	return doc


def preparer_afrique(afrique):
	"""Le doc de l'Afrique du Nord (copie, `_rev` retiré), l'Égypte qu'elle montre à 0."""
	doc = sans_rev(copy.deepcopy(afrique))
	fermer(doc["cells"], bande(FRONTIERE_AFRIQUE, "est", doc["dimensions"]))
	return doc


def lignes(egypte, afrique):
	"""{tronçon: (ligne de l'Égypte, ligne de l'Afrique du Nord)} sur les docs PRÉPARÉS."""
	dims_e, dims_a = egypte["dimensions"], afrique["dimensions"]
	au_dela_e = bande(FRONTIERE_EGYPTE, "ouest", dims_e) | bande(CADRE_SUD_EGYPTE, "sud", dims_e)
	au_dela_a = bande(FRONTIERE_AFRIQUE, "est", dims_a)
	zone_e = zone_de(egypte["cells"], egypte.get("nav") or {}, ANCRE_EGYPTE)
	zone_a = zone_de(afrique["cells"], afrique.get("nav") or {}, ANCRE_AFRIQUE)
	return {nom: (ligne_frontiere(zone_e, au_dela_e, depart_e, cadre_e),
			ligne_frontiere(zone_a, au_dela_a, depart_a, cadre_a))
		for nom, (cadre_e, cadre_a, depart_e, depart_a) in TRONCONS.items()}


def connexions(lignes_par_troncon, libelles):
	"""(docs, refus, avertissements) : un lien `link:afrique_du_nord_to_egypte_NN` par nom,
	une case sur deux côté Afrique du Nord, répartis sur tout le tronçon côté Égypte."""
	prefixe = "link:afrique_du_nord_to_egypte"
	docs, refus, avert, rang = [], [], [], 0
	for troncon, (ligne_e, ligne_a) in lignes_par_troncon.items():
		noms = PASSAGES[troncon]
		if not ligne_e or not ligne_a:
			refus.append(f"{prefixe} ({troncon}) : aucune case de frontière sur "
				f"{EGYPTE if not ligne_e else AFRIQUE}")
			continue
		attendu = (len(ligne_a) + 1) // 2
		if len(noms) != attendu:
			avert.append(f"{prefixe} ({troncon}) : {len(noms)} nom(s) pour {attendu} poste(s) — "
				f"frontière de {len(ligne_a)} case(s) sur {AFRIQUE}, {len(ligne_e)} sur {EGYPTE}")
		for nom, pos_a, pos_e in zip(noms, postes(ligne_a, len(noms)), postes(ligne_e, len(noms))):
			rang += 1
			doc = connexion(f"{prefixe}_{rang:02d}", AFRIQUE, pos_a, EGYPTE, pos_e)
			for noeud in doc["nodes"]:
				noeud["label"] = f"{nom} — {libelles.get(noeud['lieu'], noeud['lieu'])}"
			docs.append(doc)
	return docs, refus, avert


def connexions_coupees(docs, egypte, afrique):
	"""Avertissements : connexions en base dont un nœud tombe sur une case mise à 0 ici."""
	fermees = {EGYPTE: bande(FRONTIERE_EGYPTE, "ouest", egypte["dimensions"])
			| bande(CADRE_SUD_EGYPTE, "sud", egypte["dimensions"]),
		AFRIQUE: bande(FRONTIERE_AFRIQUE, "est", afrique["dimensions"])}
	avert = []
	for d in docs:
		if d.get("type") != "connection" or str(d.get("_id", "")).startswith("link:afrique_du_nord_to_egypte_"):
			continue
		for n in d.get("nodes") or []:
			if tuple(n.get("pos") or ()) in fermees.get(n.get("lieu"), ()):
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
	egypte, afrique = preparer_egypte(par_id[EGYPTE]), preparer_afrique(par_id[AFRIQUE])
	liens, refus, avert = connexions(lignes(egypte, afrique), libelles)
	return [egypte, afrique], liens, refus, avert + connexions_coupees(docs, egypte, afrique)

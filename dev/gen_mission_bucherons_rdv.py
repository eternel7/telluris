#!/usr/bin/env python
# dev/gen_mission_bucherons_rdv.py
# Déplace le RENDEZ-VOUS de l'escorte « Retrouver les bûcherons d'Auxerre » DERRIÈRE le combat
# contre les trois loups géants.
#
# LE DÉFAUT CORRIGÉ — l'offre écrite de Gautier posait `rencontre.lieu` sur
# `lieu:grotte_dans_foret_humide_interieur01`, dont la barrière `acces` ne demande que la quête
# active. Le joueur acceptait donc la mission, entrait dans la grotte AVANT d'avoir affronté la
# meute, et `escorte.traiter_deplacement` incarnait sur-le-champ les quatre `protege:*`. Or un
# protégé attaché est snapshoté dans `joueurs` à CHAQUE combat (`est_protege`, ciblable, hors
# `_combattants_vivants`) : les trois bûcherons et Aélis se retrouvaient sur la carte du combat
# des loups, où la mort de l'un fait échouer la quête (`ESCORTE_MORT_DEFINITIVE`). L'escorte
# commençait avant que la menace qui la justifie n'ait été levée.
#
# LE REMÈDE — 100 % DONNÉE, aucune ligne de moteur. Le rendez-vous passe sur
# `lieu:clairiere_de_la_grotte_liberee`, dont la barrière porte DÉJÀ
# `combat_gagne: {lieu: lieu:grotte_en_foret}` : ce lieu n'existe tout simplement pas tant que
# la meute tient le seuil. La rencontre ne peut donc plus se déclencher avant la victoire, et
# elle se déclenche là où le contenu écrit conduit déjà le joueur — le nœud `route` d'Armand
# porte `deplacer: lieu:clairiere_de_la_grotte_liberee` (« Menez, {prenom}. Nous vous suivons »).
#
# LA GROTTE SE VIDE QUAND LA MEUTE TOMBE — les deux docs d'intérieur deviennent STRICTEMENT
# COMPLÉMENTAIRES : exactement l'un des deux est ouvert, dans les quatre états du monde.
#   · `…_interieur01` (peuplé, quatre `pnj`) : `quete_active` ET `combat_gagne {attendu:false}` ;
#   · `…_interieur`   (vide)                 : `ou` [ pas de quête , combat gagné ].
# Sans cela, `interieur01` restait ouvert pendant toute l'escorte : le joueur y retrouvait les
# quatre PNJ encore assis dans le noir pendant que leurs quatre `protege:*` le suivaient sur la
# route — des doublons. Ils sont sortis avec lui : la grotte est vide, et c'est le doc vide qui
# la montre. Deux ouvertes = deux boutons « Penetrer dans la grotte » ; zéro ouverte = une
# grotte sans intérieur : l'invariante est épinglée par `tests/test_acces.py`.
#
# ⚠️ POURQUOI UNE CLAUSE `ou` A DÛ NAÎTRE POUR ÇA. `acces.conditions` est un ET, et `attendu`
# ne nie qu'UN prédicat. Or la grotte habitée demande une CONJONCTION (« quête active ET combat
# pas gagné ») : son complément est une DISJONCTION, inexprimable jusqu'ici. Les deux états sans
# quête (avant, et après la remise) se disent bien d'une seule clause — c'est la fenêtre du
# MILIEU, l'escorte en cours une fois les loups morts, qui impose le `ou`. La clause a donc été
# ajoutée au moteur (`utils/acces.py`, fail-closed et récursive) plutôt que d'accepter une
# grotte sans intérieur pendant tout le retour vers Auxerre.
#
# ⚠️ Les scènes d'après-bataille écrites À L'INTÉRIEUR (« Vous pouvez vous asseoir, maintenant »)
# ne restent atteignables que par le joueur qui a DÉCLENCHÉ le combat depuis la grotte : il y
# est encore au retour du combat, et `get_lieu_links` ne filtre jamais le lieu COURANT — un lieu
# refermé reste quittable. Celui qui a chargé depuis le seuil, lui, les retrouve dehors.
#
# ARMAND NE HÈLE QUE PENDANT LA QUÊTE — son entrée `pnj` sur le seuil porte désormais
# `conditions: [quete_active …]`, le vocabulaire des barrières de lieu appliqué à la PRÉSENCE
# d'un PNJ (`utils/pnj.entrees_pnj`, évaluateur injecté). Hors quête, son nœud d'accueil
# (« quelque chose remue là-dedans, puis une voix d'homme ») contredisait la seule branche
# qu'il offrait alors (`grotte_silencieuse` : « ce n'était pas aujourd'hui »). Un texte de
# nœud ne se conditionne pas ; sa présence, si.
#
# ⚠️ Le pré-combat de l'intérieur de la grotte est PRÉSERVÉ : `interieur01` reste ouvert dès
# l'acceptation. Tout le dialogue de siège (Étienne et son feu, Matthieu et le seuil, Aélis et
# ses onze pouces) se joue toujours AVANT la bataille — il n'est plus payé du risque de perdre
# la quête dans le combat qui suit.
#
# ⚠️ La condition `lieu_visite {attendu: false}` de la clairière est RETIRÉE. Elle en faisait un
# passage à usage unique, ce qui était sans risque pour une carte postale de victoire et en
# devient un pour un POINT DE RENDEZ-VOUS : si l'incarnation échouait sur cette unique visite
# (docs de race illisibles, par exemple), le lieu se refermait et la quête n'avait plus aucun
# moyen de commencer. La clairière se referme désormais toute seule à la fin de la quête, par
# sa condition `quete_active`. Ré-entrer après la rencontre est inerte (`incarner` est
# idempotent : `rencontre_at`).
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — toucher un champ oblige à reproduire tout le doc (celui de Gautier
# fait 20 Ko de dialogue). On RELIT donc les docs depuis le dump et on n'y injecte que le champ
# visé : régénérer est idempotent, et une retouche faite à la main en base survit.
#
# ⚠️ UNE QUÊTE DÉJÀ ACCEPTÉE NE CHANGE PAS : le bloc `rencontre` est FIGÉ dans le snapshot de
# `quetes_actives` à l'acceptation. Un personnage qui porte déjà la mission doit l'abandonner
# (ce qui coûte la sanction de maison) et la reprendre chez Gautier pour voir le nouveau
# rendez-vous.
#
# Usage : python dev/gen_mission_bucherons_rdv.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/mission_bucherons_rdv_correctif_a_importer.json
#     (5 docs : Gautier, la clairière, la grotte habitée, la grotte vide, le seuil)

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260903-183733.json"

GIVER_ID = "pnj:gautier_de_valcroix"
CLAIRIERE_ID = "lieu:clairiere_de_la_grotte_liberee"
SALLE_ID = "lieu:grotte_en_foret"
PEUPLE_ID = "lieu:grotte_dans_foret_humide_interieur01"
VIDE_ID = "lieu:grotte_dans_foret_humide_interieur"
SEUIL_ID = "lieu:grotte_dans_foret_humide"
ARMAND_ID = "pnj:armand_renaud"

# ⚠️ Le MÊME filtre des deux côtés : la grotte vide est le complément EXACT de la grotte
# habitée, deux copies finiraient par désigner deux quêtes différentes.
QUETE_FILTRE = {
	"types": ["escorte"],
	"cible": "lieu:bureau_du_maitre_de_guilde_d_auxerre",
	"giver_categorie": "bureau_maitre_guilde",
}
OFFRE_ID = "quete:escorte_bucherons_d_auxerre"

SORTIE = "jsons/mission_bucherons_rdv_correctif_a_importer.json"


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


_BASE = None


def extraire(doc_id: str) -> dict:
	"""Le doc tel qu'il est EN BASE, jamais retapé. Sortie en erreur s'il manque : mieux vaut
	ne rien générer qu'un fichier d'import qui écraserait un doc par une version inventée."""
	global _BASE
	if _BASE is None:
		_BASE = {d["_id"]: d for d in charger(SRC_DUMP)
				 if isinstance(d, dict) and d.get("_id")}
	if doc_id not in _BASE:
		sys.exit(f"ERREUR : {doc_id} introuvable dans {SRC_DUMP}")
	return _BASE[doc_id]


def rendez_vous_apres_le_combat(giver: dict) -> dict:
	"""Pose le rendez-vous sur la clairière. Fail-closed : on ne devine pas une offre absente."""
	offre = ((giver.get("services") or {}).get("escorte") or {}).get("offre")
	if not isinstance(offre, dict):
		sys.exit(f"ERREUR : {GIVER_ID} ne porte aucun services.escorte.offre")
	if offre.get("id") != OFFRE_ID:
		sys.exit(f"ERREUR : l'offre de {GIVER_ID} est {offre.get('id')!r}, attendu {OFFRE_ID!r}")
	avant = (offre.get("rencontre") or {}).get("lieu")
	if avant == CLAIRIERE_ID:
		print(f"   {GIVER_ID} : rendez-vous déjà sur la clairière (réimport sans effet)")
	# ⚠️ On écrase le bloc au lieu de le muter : un `zones` hérité tirerait une case au hasard
	# dans la clairière, qui n'a pas de grille — la contrainte de LIEU seule est ce qu'il faut.
	offre["rencontre"] = {"lieu": CLAIRIERE_ID}
	return giver


def clairiere_reutilisable(lieu: dict) -> dict:
	"""Retire le `lieu_visite {attendu: false}` — un rendez-vous ne doit pas être à usage
	unique — et vérifie que le verrou de combat, lui, est bien là : c'est LUI qui interdit
	désormais à l'escorte de commencer avant la bataille."""
	acces = lieu.get("acces") or {}
	conditions = [c for c in (acces.get("conditions") or [])
				  if not (isinstance(c, dict) and "lieu_visite" in c)]
	gagne = [c for c in conditions
			 if isinstance(c, dict) and (c.get("combat_gagne") or {}).get("lieu") == SALLE_ID]
	if not gagne:
		sys.exit(f"ERREUR : {CLAIRIERE_ID} ne porte plus combat_gagne sur {SALLE_ID} — le "
				 "rendez-vous ne serait plus gardé par le combat, ce qui est TOUT l'objet du "
				 "correctif.")
	if any((c.get("combat_gagne") or {}).get("attendu") is False for c in gagne):
		sys.exit(f"ERREUR : {CLAIRIERE_ID} exige combat_gagne attendu:false — la clairière "
				 "s'ouvrirait AVANT la victoire, exactement l'inverse du but.")
	if len(conditions) == len(acces.get("conditions") or []):
		print(f"   {CLAIRIERE_ID} : plus de lieu_visite à retirer (réimport sans effet)")
	acces["conditions"] = conditions
	lieu["acces"] = acces
	return lieu


def grotte_peuplee(lieu: dict) -> dict:
	"""Les quatre assiégés ne se montrent que TANT QUE la meute tient le seuil."""
	acces = lieu.get("acces") or {}
	acces["conditions"] = [
		{"quete_active": dict(QUETE_FILTRE)},
		{"combat_gagne": {"lieu": SALLE_ID, "attendu": False}},
	]
	lieu["acces"] = acces
	return lieu


def grotte_vide(lieu: dict) -> dict:
	"""Le COMPLÉMENT EXACT de la grotte habitée : ouverte dans les trois autres états du
	monde — avant la quête, pendant l'escorte une fois la meute tombée, et après la remise.
	Avant et après, les conditions sont les mêmes (aucune quête active) ; c'est la fenêtre
	du milieu qui impose la clause `ou`.
	
	⚠️ POURQUOI UN `ou` ET PAS DEUX CLAUSES : `acces.conditions` est un ET. La grotte
	habitée demande une CONJONCTION (« quête active ET combat pas gagné ») ; son complément
	est donc une disjonction (« pas de quête OU combat gagné »), que le ET ne sait pas dire
	et qu'aucun `attendu` ne rattrape — il nie un prédicat, pas une conjonction. D'où la
	clause `ou` ajoutée au moteur (`utils/acces.py`), fail-closed et récursive.
	
	⚠️ Le `refus` d'origine est CONSERVÉ : il ne se lit plus que dans le seul état où la
	grotte vide est fermée — pendant le siège —, et « Des voix montent du fond de la grotte »
	y est exactement juste."""
	acces = lieu.get("acces") or {}
	acces["cycle"] = int(acces.get("cycle", 1))
	acces["conditions"] = [{"ou": [
		# Les deux états où aucune escorte de bûcherons ne court : avant, et après la remise.
		{"quete_active": dict(QUETE_FILTRE, attendu=False)},
		# Et, pendant la quête, dès que la meute est tombée : ils sont sortis avec le joueur.
		{"combat_gagne": {"lieu": SALLE_ID, "attendu": True}},
	]}]
	lieu["acces"] = acces
	return lieu


def seuil_sans_armand_hors_quete(lieu: dict) -> dict:
	"""Armand ne hèle le joueur depuis la fente que TANT QUE la quête court.
	
	Son nœud d'accueil parle d'une voix qui remue au fond de la grotte ; hors quête, la
	fiction dit l'inverse (`grotte_silencieuse` : « si quelqu'un s'est abrité là, ce n'était
	pas aujourd'hui »), et le PNJ se contredisait donc lui-même à qui passait par là sans
	mission. Un texte de nœud ne se conditionne pas — c'est la PRÉSENCE qui devait l'être.
	
	⚠️ Aucun risque de blocage, contrairement à un gardien ordinaire : la salle qu'Armand
	ouvre (`lieu:grotte_en_foret`) demande DÉJÀ la même quête, et les trois assiégés de
	l'intérieur portent le même service `acces`. Sans quête, il n'y a rien à ouvrir."""
	entrees = lieu.get("pnj") or []
	vise = [e for e in entrees if isinstance(e, dict) and e.get("character") == ARMAND_ID]
	if not vise:
		sys.exit(f"ERREUR : {ARMAND_ID} n'est pas une entrée pnj de {SEUIL_ID}")
	for entree in vise:
		# ⚠️ JAMAIS de `probabilite` sur un gardien : un tirage malheureux le rendrait muet
		# et la porte, elle, resterait fermée. La condition remplace le hasard, elle ne s'y
		# ajoute pas.
		entree.pop("probabilite", None)
		entree["conditions"] = [{"quete_active": dict(QUETE_FILTRE)}]
	return lieu


def main() -> None:
	docs = [
		rendez_vous_apres_le_combat(extraire(GIVER_ID)),
		clairiere_reutilisable(extraire(CLAIRIERE_ID)),
		grotte_peuplee(extraire(PEUPLE_ID)),
		grotte_vide(extraire(VIDE_ID)),
		seuil_sans_armand_hors_quete(extraire(SEUIL_ID)),
	]
	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"écrit {SORTIE}\n"
		  f"   rendez-vous de {OFFRE_ID} : {CLAIRIERE_ID} (derrière combat_gagne {SALLE_ID})\n"
		  f"   grotte habitée / grotte vide : complémentaires sur combat_gagne {SALLE_ID}\n"
		  f"   {len(docs)} doc(s) : " + ", ".join(d["_id"] for d in docs))


if __name__ == "__main__":
	main()

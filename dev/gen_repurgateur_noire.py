#!/usr/bin/env python
# dev/gen_repurgateur_noire.py
# Bascule le RÉPURGATEUR de la magie Sainte à la magie NOIRE (école `Démonologie`), en
# l'excluant des INVOCATIONS de cette école — et dote les deux écoles noires de leurs
# premiers sorts d'invocation.
#
# CE QUE LE FICHIER D'IMPORT CONTIENT, et rien d'autre :
#   1. `rules:vocations` — doc RECOPIÉ du dump, dans lequel la seule entrée `repurgateur`
#      change : `magie` Sainte → Démonologie, `familles_exclues: ["invocation"]`, blurb.
#      ⚠️ Le doc entier est réécrit parce qu'`admin_import_bulk` fait un PUT COMPLET : une
#      `value` partielle EFFACERAIT les 19 autres vocations, en silence.
#   2. Les 3 sorts de répurgateur déjà en base, relus du dump, re-tagués `Démonologie` et
#      re-formulés en magie noire (l'eau bénite et le sel laissent la place au sel noir et
#      au soufre). `_id`, `effets`, `cout_pm`, `cible`, `jet` et `portee` sont INCHANGÉS :
#      un personnage qui connaît déjà l'un de ces sorts le garde, au même prix et au même
#      effet — seule sa couleur change.
#   3. Deux sorts d'INVOCATION NEUFS, un par école noire (`sort:pacte_du_servant` en
#      Démonologie, `sort:levee_des_ossements` en Nécromancie). Ce sont eux que la nouvelle
#      exclusion retire au répurgateur : sans contenu d'invocation en Démonologie, la règle
#      ne mordrait sur rien.
#
# POURQUOI UN GÉNÉRATEUR plutôt qu'un JSON tapé à la main : les docs 1 et 2 sont RELUS du
# dump et ne reçoivent que les champs ajoutés, donc régénérer est idempotent et ne peut pas
# perdre un champ que quelqu'un aurait posé entre-temps (cf. CLAUDE.md § Import et écriture
# de contenu). Le script sort en erreur si l'un des docs attendus manque du dump, et si un
# `_id` neuf existe déjà en base.
#
# ⚠️ LE DUMP EST UN INSTANTANÉ, figé explicitement ci-dessous. Une vocation ajoutée dans
# /admin depuis cet export serait ramenée à l'état d'alors : rafraîchir `SRC_DUMP` avant de
# régénérer. Le script imprime tout ce qu'il change, pour qu'un écart saute aux yeux AVANT
# l'import.
#
# Usage : python dev/gen_repurgateur_noire.py
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/repurgateur_magie_noire_a_importer.json   (6 docs)

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé (et non « le glob le plus récent »)
# pour que régénérer donne toujours le même résultat ; à mettre à jour à la main.
SRC_DUMP = "jsons/telluris-dump-20260913-195314.json"

SORTIE = "jsons/repurgateur_magie_noire_a_importer.json"

VOCATIONS_ID = "rules:vocations"
REPURGATEUR = "repurgateur"

# L'école que le répurgateur pratique désormais, et la famille qui lui reste fermée.
ECOLE_NOIRE = "Démonologie"
FAMILLE_INVOCATION = "invocation"

BLURB_REPURGATEUR = (
	"Chasseur de créatures maudites. Il combat le mal par le mal : sa magie est noire, "
	"mais il n'appelle jamais ce qu'il passe sa vie à abattre."
)

# ── 2. Re-formulation des 3 sorts de répurgateur ────────────────────────────────────
# Seules ces clés sont réécrites ; tout le reste du doc est celui du dump. `effets`,
# `cout_pm`, `cible`, `jet` et `portee` n'y figurent VOLONTAIREMENT pas : la bascule
# d'école ne doit rien changer à l'équilibre d'un sort déjà en jeu.
SORTS_REPURGATEUR = {
	"sort:fer_et_priere": {
		"magie": ECOLE_NOIRE,
		"nom": "Fer et malédiction",
		"description": "La main gantée s'abat en même temps que la formule. Contre l'impur, "
					   "le répurgateur emprunte à l'impur — et le contact vaut mieux que la distance.",
		"composants": [
			{"item": "item:Sel_noir", "consomme": True, "bonus": {"degats": "1D6"}},
			{"item": "item:Soufre", "consomme": False, "bonus": {"degats": "1"}},
		],
	},
	"sort:feu_purificateur": {
		"magie": ECOLE_NOIRE,
		"description": "Un feu noir qui purge les créatures maudites. Il ne descend d'aucun ciel.",
		"composants": [
			{"item": "item:Soufre", "consomme": True, "bonus": {"degats": "1D6"}},
			{"item": "item:Sel_noir", "consomme": True, "bonus": {"degats": "1D4"}},
		],
	},
	"sort:sceau_de_protection": {
		"magie": ECOLE_NOIRE,
		"description": "Un sceau tracé au sel noir : ce qui rôde le reconnaît comme un des siens "
					   "et passe son chemin.",
		"composants": [
			{"item": "item:Sel_noir", "consomme": True, "bonus": {"duree": 2}},
			{"item": "item:Bougie", "consomme": False, "bonus": {"buffs": {"Vol": 5}}},
		],
	},
}

# ── 3. Sorts d'INVOCATION neufs ─────────────────────────────────────────────────────
# NIVEAU 1, et non 0 : une invocation ajoute un combattant entier à la grille, ce qu'aucun
# sort de départ ne doit faire (le niveau 0 alimente le choix de sort à la création).
# AUCUN `composants` : les bonus de composant s'additionnent aux `effets`, qu'une invocation
# n'applique justement pas (branche exclusive de `resolve_action`) — ils seraient inertes.
SORTS_INVOCATION = [
	{
		"_id": "sort:pacte_du_servant",
		"type": "sort",
		"nom": "Pacte du servant",
		"icon": "😈",
		"description": "Un nom prononcé à voix basse, et l'un des plus bas échelons de l'Enfer "
					   "se glisse par la couture du monde. Il obéit le temps du pacte, pas une "
					   "seconde de plus.",
		"vocation": "demoniste",
		"magie": ECOLE_NOIRE,
		"famille": FAMILLE_INVOCATION,
		"niveau": 1,
		"cout_pm": 20,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:demon_servant", "nombre": 1, "duree": 4},
	},
	{
		"_id": "sort:levee_des_ossements",
		"type": "sort",
		"nom": "Levée des ossements",
		"icon": "💀",
		"description": "Ce que la terre a gardé se redresse au premier mot. Deux carcasses "
					   "montées à la hâte : elles ne frappent pas fort, mais elles ne reculent "
					   "devant rien et ne sentent rien.",
		"vocation": "necromancien",
		"magie": "Nécromancie",
		"famille": FAMILLE_INVOCATION,
		"niveau": 1,
		"cout_pm": 24,
		"cible": "soi",
		"portee": 0,
		"effets": {},
		"invocation": {"espece": "espece:squelette", "nombre": 2, "duree": 3},
	},
]


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


_BASE = None


def base() -> dict:
	global _BASE
	if _BASE is None:
		_BASE = {d["_id"]: d for d in charger(SRC_DUMP)
				 if isinstance(d, dict) and d.get("_id")}
	return _BASE


def extraire(doc_id: str) -> dict:
	"""Le doc tel qu'il est EN BASE, jamais retapé. Sortie en erreur s'il manque : mieux vaut
	ne rien générer qu'un import qui écraserait un doc par une version inventée."""
	if doc_id not in base():
		sys.exit(f"ERREUR : {doc_id} introuvable dans {SRC_DUMP}")
	return base()[doc_id]


def vocations_doc() -> dict:
	"""`rules:vocations` recopié du dump, entrée `repurgateur` rectifiée."""
	doc = extraire(VOCATIONS_ID)
	entrees = doc.get("value") or []
	cible = next((v for v in entrees if v.get("id") == REPURGATEUR), None)
	if cible is None:
		sys.exit(f"ERREUR : vocation « {REPURGATEUR} » absente de {VOCATIONS_ID}")

	avant_magie = cible.get("magie", "")
	avant_exclues = list(cible.get("familles_exclues") or [])
	cible["magie"] = ECOLE_NOIRE
	cible["familles_exclues"] = [FAMILLE_INVOCATION]
	cible["blurb"] = BLURB_REPURGATEUR
	print(f"   {VOCATIONS_ID} : {len(entrees)} vocations recopiées")
	print(f"      repurgateur.magie             {avant_magie or '(vide)'} -> {ECOLE_NOIRE}")
	print(f"      repurgateur.familles_exclues  {avant_exclues or '(absent)'} -> "
		  f"{cible['familles_exclues']}")

	# Filet : l'exclusion ne vaut que si l'école pointée existe VRAIMENT ailleurs, sinon le
	# répurgateur se retrouverait seul praticant d'une école sans le moindre sort.
	ecoles = {str(v.get("magie") or "") for v in entrees if v.get("id") != REPURGATEUR}
	if ECOLE_NOIRE not in ecoles:
		sys.exit(f"ERREUR : aucune autre vocation ne pratique « {ECOLE_NOIRE} » — "
				 "le répurgateur n'aurait aucun sort à apprendre.")
	return doc


def sorts_retagues() -> list:
	"""Les 3 sorts de répurgateur du dump, re-tagués et re-formulés en magie noire."""
	docs = []
	for sort_id, champs in SORTS_REPURGATEUR.items():
		doc = extraire(sort_id)
		if doc.get("vocation") != REPURGATEUR:
			sys.exit(f"ERREUR : {sort_id} n'est pas un sort de répurgateur "
					 f"(vocation={doc.get('vocation')!r})")
		avant = doc.get("magie", "")
		doc.update(champs)
		etat = "déjà en magie noire (réimport sans effet sur l'école)" if avant == ECOLE_NOIRE \
			else f"{avant or '(vide)'} -> {ECOLE_NOIRE}"
		print(f"   {sort_id} : {etat}")
		docs.append(doc)
	return docs


def sorts_neufs() -> list:
	"""Les sorts d'invocation, contrôlés contre le dump : aucune collision d'`_id`, espèce
	invoquée existante (un `espece:*` mort ferait un sort qui ne produit RIEN, sans erreur)."""
	for doc in SORTS_INVOCATION:
		if doc["_id"] in base():
			sys.exit(f"ERREUR : {doc['_id']} existe déjà en base — un import l'écraserait.")
		espece_id = doc["invocation"]["espece"]
		espece = base().get(espece_id)
		if not espece or espece.get("type") != "espece":
			sys.exit(f"ERREUR : {doc['_id']} invoque {espece_id}, absent du bestiaire.")
		inv = doc["invocation"]
		print(f"   {doc['_id']} : NEUF — {inv['nombre']}× {espece['nom']} "
			  f"pendant {inv['duree']} tour(s), {doc['cout_pm']} PM, niveau {doc['niveau']}")
	return [dict(d) for d in SORTS_INVOCATION]


def main() -> None:
	print(f"source : {SRC_DUMP}")
	docs = [vocations_doc()] + sorts_retagues() + sorts_neufs()

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"écrit {SORTIE}\n   {len(docs)} doc(s)")
	print("   ⚠️ Après l'import : un répurgateur ne voit plus les sorts Saints dans son "
		  "onglet ⚡, mais les sorts de Démonologie — hors invocations.")


if __name__ == "__main__":
	main()

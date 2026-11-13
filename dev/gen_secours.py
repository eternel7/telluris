#!/usr/bin/env python
# dev/gen_secours.py
# Ouvre les SECOURS (utils/secours.py) à CHAQUE comptoir de la Guilde des Aventuriers.
#
# Pour chaque PNJ posté dans un lieu `guilde_aventurier_comptoir`, le script RELIT son doc
# depuis le dump le plus récent et n'y injecte que :
#   · `services.escorte.secours = {"cite": <lieu_parent du comptoir>}` — le moteur dérive
#     tout le reste de la carte (lieux de péril, donjons proches, rang, protégés) ;
#   · `services.escorte.noeuds.secours_accepte` — le nœud de suite propre au secours (Borin,
#     à Auxerre, garde son `accepte` des enfants disparus) ;
#   · cinq nœuds `secours_*` et deux choix à l'accueil, gardés par les flags DISJOINTS
#     `secours_offert` / `secours_en_cours`.
# Les autres services, nœuds et choix du PNJ restent tels quels.
#
# ⚠️ Texte GÉNÉRIQUE, partagé par vingt-six voix : aucun nom en dur, aucun accord de genre ni
# pour le PNJ ni pour le joueur (vouvoiement neutre), aucune didascalie qui suppose une
# Lignée. Les personnes à secourir passent par {protege}, le lieu par {lieu_rencontre}.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. Le doc relu du dump est
# réécrit entier avec nos ajouts (régénération IDEMPOTENTE : nos choix sont retirés puis
# réinsérés juste avant la porte de sortie). Un nœud déjà présent sous l'un de nos ids, au
# contenu différent, ARRÊTE le script : jamais d'écrasement silencieux.
#
# Usage : python dev/gen_secours.py
# Sortie (à charger dans /admin -> Import en masse) : jsons/secours_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

SORTIE = "jsons/secours_a_importer.json"
CATEGORIE_COMPTOIR = "guilde_aventurier_comptoir"

NOEUDS = {
	"secours_propose": {
		"texte": (
			"Un registre s'ouvre sur le comptoir, à une page encore fraîche d'encre. « Des "
			"aventuriers de la Guilde ne sont pas revenus : {protege}. Leur dernier signe de "
			"vie vient de là : {lieu_rencontre}. Blessés, d'après ce qu'on sait — mais ils "
			"tiennent encore une arme. »"
		),
		"choix": [
			{"id": "secours_details", "label": "Qu'attend la Guilde ?", "next": "secours_details"},
			{"id": "secours_refuser", "label": "Ce n'est pas pour moi.", "next": "accueil"},
		],
	},
	"secours_details": {
		"texte": (
			"« Qu'on les ramène ici, vivants : {destination}. La Guilde paie {xp} points "
			"d'expérience et {prime} pièces de cuivre, et elle se souvient de qui ne laisse "
			"pas les siens dehors. » Un doigt tapote la date en marge. « Ne traînez pas : "
			"passé quelques jours, il n'y aura plus personne à ramener. »"
		),
		"choix": [
			{"id": "secours_accepter", "label": "J'y vais.",
			 "action": {"service": "escorte", "op": "accepter"}},
			{"id": "secours_refuser", "label": "Laissez-moi y réfléchir.", "next": "accueil"},
		],
	},
	"secours_acceptee": {
		"texte": (
			"La plume court dans la marge. « C'est inscrit à votre nom, {prenom}. » Le registre "
			"se referme. « Ils sauront se défendre, mais ils ne courront plus : c'est à vous "
			"de les couvrir jusqu'au retour. Et si l'un d'eux tombe en chemin, la page reste "
			"ouverte pour rien. »"
		),
		"choix": [
			{"id": "partir", "label": "Je pars sur-le-champ.", "next": "fin"},
			{"id": "retour", "label": "Encore une chose…", "next": "accueil"},
		],
	},
	"secours_relance": {
		"texte": (
			"« Des nouvelles de {protege} ? » Le registre est rouvert à la même page. "
			"« Dernier signe de vie : {lieu_rencontre}. On les attend ici, et nulle part "
			"ailleurs : {destination}. »"
		),
		"choix": [
			{"id": "retour", "label": "J'y retourne.", "next": "accueil"},
			{"id": "fin", "label": "Je m'en occupe.", "next": "fin"},
		],
	},
}

CHOIX_ACCUEIL = [
	{"id": "secours_offre", "label": "Des aventuriers à secourir ?",
	 "next": "secours_propose", "condition": {"secours_offert": True}},
	{"id": "secours_relance", "label": "Au sujet de {protege}…",
	 "next": "secours_relance", "condition": {"secours_en_cours": True}},
]


def dump_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("Aucun dump jsons/telluris-dump-*.json.")
	return dumps[-1]


def charger(chemin: str) -> list:
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def copie(x):
	return json.loads(json.dumps(x))


def ouvrir_secours(doc: dict, cite: str) -> dict:
	"""Le doc PNJ avec le secours injecté (copie profonde, le dump n'est pas muté)."""
	doc = copie(doc)
	escorte = doc.setdefault("services", {}).setdefault("escorte", {})
	escorte["secours"] = {"cite": cite}
	noeuds_service = escorte.setdefault("noeuds", {})
	noeuds_service["secours_accepte"] = "secours_acceptee"
	# Un comptoir sans autre escorte n'a pas d'`accepte` : le secours le devient (le linter
	# l'exige). Celui d'un comptoir qui en a déjà un (Borin, enfants disparus) n'est pas touché.
	noeuds_service.setdefault("accepte", "secours_acceptee")

	dialogue = doc.setdefault("dialogue", {})
	noeuds = dialogue.setdefault("noeuds", {})
	for nid, contenu in NOEUDS.items():
		if nid in noeuds and noeuds[nid] != contenu:
			raise SystemExit(f"{doc['_id']} : le nœud « {nid} » existe déjà avec un autre "
							 f"contenu — collision, rien n'est écrit.")
		noeuds[nid] = copie(contenu)
	depart = dialogue.get("noeud_depart") or "accueil"
	accueil = noeuds.get(depart)
	if accueil is None:
		raise SystemExit(f"{doc['_id']} : pas de nœud d'accueil « {depart} ».")
	nouveaux = {c["id"] for c in CHOIX_ACCUEIL}
	restants = [c for c in accueil.get("choix") or [] if c.get("id") not in nouveaux]
	sorties = [c for c in restants if c.get("next") == "fin" and not c.get("condition")]
	avant = [c for c in restants if c not in sorties]
	accueil["choix"] = avant + copie(CHOIX_ACCUEIL) + sorties
	return doc


def main() -> None:
	src = dump_recent()
	docs = charger(src)
	par_id = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	cibles = []                                   # (pnj_id, cite)
	for d in docs:
		if d.get("type") != "lieu" or d.get("categorie") != CATEGORIE_COMPTOIR:
			continue
		cite = d.get("lieu_parent")
		for entree in d.get("pnj") or []:
			pid = entree.get("character")
			if pid and cite and pid not in {p for p, _ in cibles}:
				cibles.append((pid, cite))
	sortie = []
	for pid, cite in sorted(cibles):
		doc = par_id.get(pid)
		if doc is None:
			print(f"  ⚠️ {pid} absent du dump — ignoré")
			continue
		sortie.append(ouvrir_secours(doc, cite))

	from utils import lint_dialogues
	rapport = lint_dialogues.analyser(sortie)
	for t in rapport.get("trouvailles") or []:
		if t.get("niveau") == "erreur":
			print(f"  ❌ {t.get('doc_id')} [{t.get('noeud')}] {t.get('message')}")
	if rapport.get("erreurs"):
		raise SystemExit(f"{rapport['erreurs']} erreur(s) de dialogue — rien n'est écrit.")

	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
	print(f"{len(sortie)} comptoir(s) ouverts aux secours (dump : {os.path.basename(src)}) "
		  f"-> {SORTIE} · linter : {rapport.get('avertissements', 0)} avertissement(s)")


if __name__ == "__main__":
	main()

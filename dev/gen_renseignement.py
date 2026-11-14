#!/usr/bin/env python
# dev/gen_renseignement.py
# 🔎 Se renseigner (compétence telluris-renseignement) : le doc `rules:renseignement` (méthodes
# par vocation, validées par l'Auteur les 13-14/11/2026) et l'item générique
# `item:note_renseignement` (la piste vit sur la RÉFÉRENCE, cf. utils/renseignement.py).
#
# ⚠️ `admin_import_bulk` fait un PUT COMPLET : seuls les docs absents du dump le plus récent, ou
# qui en diffèrent, sont écrits — régénération idempotente. Chaque méthode passe
# `renseignement.normaliser_methode` (une caractéristique inconnue arrête tout).
#
# Usage : python dev/gen_renseignement.py
# Sortie (/admin → Import en masse) : jsons/renseignement_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import renseignement  # noqa: E402

SORTIE = "jsons/renseignement_a_importer.json"

TAVERNE = {"predicats": ["taverne"]}
LIEUX_ESPECES = ["zone", "lieu", "donjon"]
TAGS_MAL = ["undead", "non_mort", "demon", "infernal", "monstre"]
TAGS_BETES = ["animal", "proie", "predateur"]
VEGETAUX = ["herbe", "baie", "graines", "fruit_sec", "arbre", "branche"]

METHODES = [
	{"id": "veterans", "nom": "Payer une tournée aux vétérans", "icon": "🍺", "vocations": ["guerrier"],
	 "lieu": TAVERNE, "test": ["cha", "f"], "cout": 12, "sources": LIEUX_ESPECES,
	 "cibles": {"ressources": False},
	 "repliques": {"intro": "Une tournée offerte, et les vétérans comparent leurs cicatrices.",
				   "description": "Les mercenaires de la salle commune racontent ce qu'ils ont affronté."}},
	{"id": "bras_de_fer", "nom": "Bras de fer", "icon": "💪", "vocations": ["barbare"],
	 "lieu": TAVERNE, "test": ["f"], "cout": 0, "cout_pv": "monde", "sources": LIEUX_ESPECES,
	 "cibles": {"ressources": False, "grade_min": "D"},
	 "repliques": {"intro": "Coudes sur la table : le perdant dit ce qu'il a vu de pire.",
				   "description": "Un défi de force, payé en PV. Seules les bêtes vraiment dangereuses intéressent."}},
	{"id": "tableau", "nom": "Lire le tableau des ordres", "icon": "📌", "vocations": ["paladin", "templier"],
	 "lieu": TAVERNE, "test": [], "cout": 5, "niveau_fixe": "region", "sources": LIEUX_ESPECES,
	 "cibles": {"ressources": False, "tags_espece": TAGS_MAL},
	 "repliques": {"intro": "Au tableau d'information, une menace signalée aux ordres.",
				   "description": "Sans jet : la région où une créature du Mal a été signalée."}},
	{"id": "salle_d_armes", "nom": "Écouter les escrimeurs", "icon": "🤺", "vocations": ["duelliste"],
	 "lieu": {"predicats": ["salle_d_armes"]}, "test": ["ag", "cha"], "cout": 10, "sources": LIEUX_ESPECES,
	 "cibles": {"ressources": False},
	 "repliques": {"intro": "Entre deux assauts, les escrimeurs échangent leurs ragots.",
				   "description": "Les ragots de la salle d'armes."}},
	{"id": "registres", "nom": "Compulser les registres", "icon": "📜", "vocations": ["lettre"],
	 "lieu": {"predicats": ["scriptorium"]}, "test": ["int"], "cout": 15, "note": True,
	 "repliques": {"intro": "Registres et bestiaires du scriptorium s'ouvrent sous vos doigts.",
				   "description": "Toutes les sources ; en cas de réussite, une note de renseignement."}},
	{"id": "ouvrages", "nom": "Ouvrages de son école", "icon": "📚",
	 "vocations": ["elementaliste", "mage", "illusionniste"],
	 "lieu": {"predicats": ["scriptorium"]}, "test": ["int"], "cout": 15,
	 "cibles": {"tags_espece": ["magique", "elementaire"], "sous_categories": ["cristal"], "ecole_vocation": True},
	 "repliques": {"intro": "Les traités de votre école citent leurs matières et leurs lieux.",
				   "description": "Composants des sorts de votre école, créatures magiques, cristaux."}},
	{"id": "chanson", "nom": "Chanter pour la salle", "icon": "🎶", "vocations": ["menestrel"],
	 "lieu": TAVERNE, "test": ["cha"], "cout": 8, "pourboire": True, "sources": LIEUX_ESPECES,
	 "cibles": {"ressources": False},
	 "repliques": {"intro": "Votre chanson finie, la salle répond par ses propres histoires.",
				   "description": "Une belle réussite rapporte aussi un pourboire."}},
	{"id": "recits", "nom": "Échanger des récits", "icon": "🪕", "vocations": ["menestrel"],
	 "lieu": TAVERNE, "test": ["cha"], "cout": 0, "modes": ["recit"], "sources": LIEUX_ESPECES,
	 "cibles": {"ressources": False},
	 "repliques": {"intro": "Un récit contre un récit : on vous rend la pareille.",
				   "description": "Cédez un lieu vu de votre bestiaire contre une piste neuve de grade égal ou moindre."}},
	{"id": "receleurs", "nom": "Interroger les receleurs", "icon": "🗝️", "vocations": ["voleur"],
	 "lieu": {"predicats": ["taverne"], "categories": ["negociant"]}, "test": ["ag", "cha"], "cout": 12,
	 "sources": ["boutique"], "cibles": {"especes": False},
	 "repliques": {"intro": "Un receleur baisse la voix.",
				   "description": "Quelle boutique a telle marchandise en rayon."}},
	{"id": "indicateurs", "nom": "Payer ses indicateurs", "icon": "🗡️", "vocations": ["assassin"],
	 "lieu": TAVERNE, "test": ["cha"], "cout": 40, "sources": LIEUX_ESPECES,
	 "cibles": {"ressources": False, "elites": True},
	 "repliques": {"intro": "Votre réseau a fait son travail.",
				   "description": "Cher, mais précis ; l'élite d'une chasse est trouvée sans faute."}},
	{"id": "pistes", "nom": "Suivre les pistes", "icon": "🐾", "vocations": ["forestier"],
	 "lieu": {"predicats": ["sauvage"]}, "test": ["int", "ag"], "cout": 0, "portee_max": 1,
	 "sources": ["zone", "lieu"],
	 "repliques": {"intro": "Les traces mènent plus loin que ce que l'œil voit d'ici.",
				   "description": "Espèces et ressources d'ici et des lieux contigus."}},
	{"id": "chasseurs", "nom": "Parler aux chasseurs", "icon": "🏹", "vocations": ["forestier"],
	 "lieu": {"predicats": ["taverne"], "categories": ["boucherie"]}, "test": ["cha"], "cout": 8,
	 "sources": LIEUX_ESPECES, "cibles": {"ressources": False, "tags_espece": TAGS_BETES},
	 "repliques": {"intro": "Chasseurs et trappeurs parlent volontiers de leur gibier.",
				   "description": "Où trouver bêtes et gibier."}},
	{"id": "betes_plantes", "nom": "Interroger bêtes et plantes", "icon": "🌿", "vocations": ["druide"],
	 "lieu": {"predicats": ["sauvage"]}, "test": ["int"], "cout": 0, "cout_pm": 6, "sources": ["zone", "lieu"],
	 "cibles": {"tags_espece": TAGS_BETES, "sous_categories": VEGETAUX},
	 "repliques": {"intro": "Les bêtes et les plantes vous répondent à leur manière.",
				   "description": "Bêtes et végétaux, contre quelques PM."}},
	{"id": "faucon", "nom": "L'œil du faucon", "icon": "🦅", "vocations": ["chaman"],
	 "lieu": {"predicats": ["pays"]}, "test": ["int"], "cout": 0, "connait": "competence:il_du_faucon",
	 "portee_max": 0, "sources": ["zone"], "cibles": {"ressources": False},
	 "repliques": {"intro": "L'esprit du faucon survole la carte pour vous.",
				   "description": "Les zones de cette carte et leurs espèces ; coûte les PM d'Œil du faucon."}},
	# Salle commune de guilde (Auteur, 14/11) : un interlocuteur par PNJ — chaque recrue du
	# tableau de la réception, le réceptionniste du comptoir (ouvert par son dialogue).
	{"id": "recrues", "nom": "Interroger une recrue", "icon": "🧭", "interlocuteur": "recrue",
	 "lieu": {"categories": ["guilde_aventurier"]}, "test": ["cha"], "cout": 0,
	 "modes": ["quete", "dangers", "donjons", "ressources"],
	 "repliques": {"intro": "Contre un pourboire, la recrue raconte ce qu'elle sait.",
				   "description": "Ce qu'elle a affronté, ce que dit son pays, ce que sait son métier."}},
	{"id": "receptionniste", "nom": "Les registres de la Guilde", "icon": "📒", "interlocuteur": "receptionniste",
	 "via_pnj": True, "lieu": {"categories": ["guilde_aventurier_comptoir"]}, "test": ["cha"], "cout": 0,
	 "modes": ["quete", "dangers", "donjons", "ressources"],
	 "repliques": {"intro": "Les registres de la Guilde s'ouvrent sur le comptoir.",
				   "description": "Gratuit : ce que la Guilde a consigné, selon votre rang."}},
	{"id": "informateur", "nom": "Payer l'informateur", "icon": "🕵️", "informateur": True,
	 "lieu": TAVERNE, "test": ["cha"], "cout": 10, "niveau_max": "region",
	 "repliques": {"intro": "Contre quelques pièces, l'informateur de la taverne se penche vers vous.",
				   "description": "Plus cher et jamais précis au lieu près."}},
]

TAGS_NATURE = ["foret", "bois", "clairiere", "clariere", "lande", "montagne", "gorge", "desert",
			   "eau", "humide", "falaise", "grotte", "fleuve"]

REGLES = {"_id": renseignement.REGLES_ID, "type": "rules", "tags_nature": TAGS_NATURE, "methodes": METHODES}

NOTE = {
	"_id": renseignement.ITEM_NOTE_ID, "type": "item", "nom": "Note de renseignement", "icon": "🗒️",
	"categorie": "document", "sous_categorie": renseignement.SOUS_CATEGORIE_NOTE, "rarete": "commun",
	"slots": [], "poids": 0.05,
	"description": "Une note griffonnée : où trouver ce que l'on cherche.",
}


def docs() -> list:
	return [json.loads(json.dumps(REGLES)), json.loads(json.dumps(NOTE))]


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in (doc or {}).items() if k != "_rev"}


def main() -> None:
	for m in METHODES:
		renseignement.normaliser_methode(m)          # lève sur une coquille
	ids = [m["id"] for m in METHODES]
	if len(ids) != len(set(ids)):
		raise SystemExit("ERREUR : id de méthode en double")
	chemin = _dump_le_plus_recent()
	with open(chemin, encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f).get("docs", []) if d.get("_id")}
	vocs = {v.get("id") for v in (base.get("rules:vocations") or {}).get("value") or []}
	inconnues = sorted({v for m in METHODES for v in m.get("vocations", [])} - vocs)
	if inconnues:
		raise SystemExit(f"ERREUR : vocations inconnues du dump : {inconnues}")
	for m in METHODES:
		if m.get("connait") and m["connait"] not in base:
			raise SystemExit(f"ERREUR : {m['id']} exige {m['connait']}, absent du dump")
	sortie = [d for d in docs() if _sans_rev(base.get(d["_id"])) != d]
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
	print(f"{len(sortie)} doc(s) → {SORTIE} (dump : {os.path.basename(chemin)})")


if __name__ == "__main__":
	main()

"""Échanges des ateliers d'un bien avec leur cité : métiers, aménagements et réglages.

# Décisions de l'Auteur du 12/11/2026 (compétence `telluris-proprietes` § Échanges avec la cité,
# moteur `utils/echanges_cite.py`). Ce générateur pose dans `rules:proprietes` :
#   · quatre métiers : commis, charretier, teneur de livres, crieur ;
#   · quatre aménagements qui leur donnent un poste (Salle des commis, Remise à charrette,
#     Cabinet des comptes, Étal sur rue), chacun avec ses `effets_poste` ;
#   · `effets_poste.achats_cite` sur les deux bureaux de négoce (le négociant ouvre les achats) ;
#   · `effets_poste.autoproduction` sur Jardin, Potager, Verger (la terre fournit ses semences) ;
#   · `reglages.echanges` et `reglages.negociant` (défauts relus dans le moteur) ; retire
#     `reglages.vente_auto`, que plus rien ne lit.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. On relit `rules:proprietes`
# dans le dump le plus récent et on n'y AJOUTE que ce qui précède (un aménagement ou un métier
# déjà présent n'est pas réécrit, un `effets_poste` existant est complété clé à clé) :
# régénérer sur un dump à jour ne produit aucun fichier.
#
# Usage : python dev/gen_echanges_cite.py [--dump chemin]
# Sortie : jsons/echanges_cite_a_importer.json
"""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
SORTIE = "jsons/echanges_cite_a_importer.json"
DOC_ID = "rules:proprietes"

L, M, D, Do = "logement", "maison", "demeure", "domaine"

METIERS = [
	{"id": "commis", "label": "Commis", "cout_embauche_cuivre": 600,
	 "description": "Court les boutiques de la cité, compare les prix et rapporte les meilleures offres."},
	{"id": "charretier", "label": "Charretier", "cout_embauche_cuivre": 500,
	 "description": "Mène la charrette du bien : ce qui part vers la cité ou en revient voyage par lui."},
	{"id": "teneur_livres", "label": "Teneur de livres", "cout_embauche_cuivre": 1200,
	 "description": "Tient les comptes des ateliers : il achète au plus juste et garde une caisse plus grande."},
	{"id": "crieur", "label": "Crieur", "cout_embauche_cuivre": 200,
	 "description": "Vend à la porte, aux passants, ce que nulle boutique n'a voulu prendre."},
]

AMENAGEMENTS = [
	{"id": "salle_commis", "nom": "Salle des commis", "categorie": "gestion", "types_autorises": [M, D, Do],
	 "cout_cuivre": 2500, "prerequis": [], "capacite": {"postes": {"commis": 1}},
	 "effets_poste": {"prospection": 2},
	 "description": "Un pupitre, des tablettes de cire et la liste des échoppes de la cité : le commis "
					"en part chaque matin et revient avec les prix du jour."},
	{"id": "remise_charrette", "nom": "Remise à charrette", "categorie": "exterieur", "types_autorises": [M, D, Do],
	 "cout_cuivre": 4000, "prerequis": [], "capacite": {"postes": {"charretier": 1}},
	 "effets_poste": {"portage_kg": 200},
	 "description": "Un appentis, une charrette et son harnais : les marchandises cessent de partir à dos d'homme."},
	{"id": "cabinet_comptes", "nom": "Cabinet des comptes", "categorie": "gestion", "types_autorises": [L, M, D, Do],
	 "cout_cuivre": 2000, "prerequis": [], "capacite": {"postes": {"teneur_livres": 1}},
	 "effets_poste": {"remise_achat": 0.1, "caisse_facteur": 2},
	 "description": "Une petite pièce fermée, des registres reliés et une balance à monnaie : chaque "
					"pièce de cuivre y a sa ligne."},
	{"id": "etal_rue", "nom": "Étal sur rue", "categorie": "activite", "types_autorises": [L, M, D, Do],
	 "cout_cuivre": 1500, "prerequis": [], "capacite": {"postes": {"crieur": 1}},
	 "effets_poste": {"crieur": {"unites": 2}},
	 "description": "Une planche sur deux tréteaux, contre le mur qui donne sur la rue : ce qui encombre "
					"les rayons y trouve un acheteur de passage."},
]

# Effets ajoutés à des aménagements déjà en jeu (complétés clé à clé, jamais retirés).
EFFETS_POSTE = {
	"bureau_professionnel": {"achats_cite": True},
	"bureau_marchand": {"achats_cite": True},
	"jardin": {"autoproduction": True},
	"potager": {"autoproduction": True},
	"verger": {"autoproduction": True},
}


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun jsons/telluris-dump-*.json")
	return dumps[-1]


def _reglages_moteur() -> tuple[dict, dict]:
	"""Les défauts du MOTEUR, relus (jamais recopiés) : le doc en base dit la même chose."""
	from utils import echanges_cite
	return dict(echanges_cite.ECHANGES_DEFAUT), dict(echanges_cite.NEGOCIANT_DEFAUT)


def generer(docs: list) -> tuple[dict, list]:
	"""→ (doc `rules:proprietes` à importer, [changements lisibles])."""
	doc = next((d for d in docs if d.get("_id") == DOC_ID), None)
	if doc is None:
		sys.exit(f"ERREUR : {DOC_ID} absent du dump")
	doc = json.loads(json.dumps(doc))
	doc.pop("_rev", None)
	val = doc["value"]
	ams = {a["id"]: a for a in val["amenagements"]}
	mets = {m["id"]: m for m in val["metiers"]}
	changes = []

	inconnus = sorted(set(EFFETS_POSTE) - set(ams))
	if inconnus:
		sys.exit("ERREUR : aménagements absents du dump : " + ", ".join(inconnus))
	for m in METIERS:
		if m["id"] not in mets:
			val["metiers"].append(m)
			changes.append(f"métier {m['id']}")
	for a in AMENAGEMENTS:
		if a["id"] not in ams:
			val["amenagements"].append(a)
			changes.append(f"aménagement {a['id']}")
	for am_id, effets in EFFETS_POSTE.items():
		ep = ams[am_id].setdefault("effets_poste", {})
		for k, v in effets.items():
			if ep.get(k) != v:
				ep[k] = v
				changes.append(f"{am_id}: effets_poste.{k}")

	reg = val.setdefault("reglages", {})
	echanges, negociant = _reglages_moteur()
	for cle, defaut in (("echanges", echanges), ("negociant", negociant)):
		if cle not in reg:
			reg[cle] = defaut
			changes.append(f"reglages.{cle}")
	if "vente_auto" in reg:
		del reg["vente_auto"]
		changes.append("reglages.vente_auto retiré")

	# Contrôles avant d'écrire : postes ⇒ métier connu, ids uniques.
	ids = [a["id"] for a in val["amenagements"]]
	if len(ids) != len(set(ids)):
		sys.exit("ERREUR : id d'aménagement en double")
	connus = {m["id"] for m in val["metiers"]}
	for a in val["amenagements"]:
		for metier in ((a.get("capacite") or {}).get("postes") or {}):
			if metier not in connus:
				sys.exit(f"ERREUR : {a['id']} ouvre un poste de métier inconnu : {metier}")
	return doc, changes


def main() -> None:
	args = sys.argv[1:]
	source = args[args.index("--dump") + 1] if "--dump" in args else _dump_le_plus_recent()
	with open(source, encoding="utf-8") as f:
		docs = json.load(f)["docs"]
	doc, changes = generer(docs)
	print(f"relu {os.path.relpath(source, RACINE)} — {len(changes)} changement(s)")
	for c in changes:
		print("   " + c)
	if not changes:
		print("Rien à importer : le dump est déjà à jour.")
		return
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump({"docs": [doc]}, f, ensure_ascii=False, indent=2)
	print(f"→ {SORTIE}")


if __name__ == "__main__":
	main()

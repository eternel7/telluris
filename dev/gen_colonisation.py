"""Voie de colonisation : chiffres du moteur dans `rules:colonisation` + lieux modèles génériques.

    python dev/gen_colonisation.py [--dump chemin]

Sortie : jsons/colonisation_moteur_a_importer.json   (carte d'import de /admin)

Décisions de l'Auteur : docs/lore/systemes/20261112_voie_de_colonisation.md ; moteur :
utils/colonisation.py (compétence `telluris-colonisation`).

1. `rules:colonisation` — ⚠️ l'import fait un PUT COMPLET : le doc est RELU dans le dump le
   plus récent et on n'y AJOUTE que ce qui manque de `colonisation.DEFAUTS` (`completer` : bloc,
   clé, entrée à `id`, clé d'une entrée) — une valeur déjà présente, peut-être retouchée par
   l'Auteur, n'est jamais réécrite. Sans le doc dans
   le dump, il est posé en entier (paliers, réglages et listes de la première livraison).
2. Sept lieux modèles GÉNÉRIQUES `lieu:modele_colonie_<palier>` (§ 12.1 : le seul prérequis),
   posés seulement s'ils manquent au dump. Images PROVISOIRES (une clairière, un hameau, des
   fortifications déjà sur le disque), grille ouverte sans mur : chaque modèle se remplace
   par sa vraie image et sa vraie grille dans `/admin/lieux`, sans toucher au moteur.

Régénérer sur un dump à jour n'écrit aucun doc (idempotent)."""

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import colonisation  # noqa: E402

JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "colonisation_moteur_a_importer.json")
ID = colonisation.REGLES_ID
OR = colonisation.OR

# ── Première livraison (inchangée) : le socle du doc s'il manque au dump ─────────────
# id, label, population, postes nommés tenus, prix de l'aménagement de statut (or),
# fortification minimale, menace, ce que le palier ouvre.
_PALIERS = [
	("campement", "Campement", 0, 0, 0, "feu et surveillance", "danger permanent",
	 ["logement du fondateur", "stockage", "feu"]),
	("hameau", "Hameau", 5, 4, 16, "palissade complète et porte", "attaques occasionnelles",
	 ["premiers PNJ", "cultures", "élevage"]),
	("bourgade", "Bourgade", 15, 12, 60, "fossé et tours", "attaques occasionnelles",
	 ["métiers spécialisés", "bâtiments spécialisés", "boutique", "auberge"]),
	("village", "Village", 40, 24, 200, "enceinte et portes fortifiées", "menaces contrôlables",
	 ["production locale", "auberge d'aventuriers"]),
	("bourg", "Bourg", 100, 40, 600, "murailles", "menaces exceptionnelles",
	 ["marché", "grande auberge", "administration"]),
	("petite_ville", "Petite ville", 250, 64, 2000, "murailles", "menaces exceptionnelles",
	 ["quartiers spécialisés", "nombreux services"]),
	("ville", "Ville", 600, 100, 6000, "système défensif complet", "rares mais majeures",
	 ["infrastructure complète", "guilde d'aventuriers"]),
]
PALIERS = [{"id": i, "label": l, "rang": n + 1, "population_min": pop, "postes_min": postes,
			"prix_statut_cuivre": prix * OR, "fortification_min": fortif, "menace": menace, "ouvre": ouvre}
		   for n, (i, l, pop, postes, prix, fortif, menace, ouvre) in enumerate(_PALIERS)]

SOCLE = {
	"paliers": PALIERS,
	"reglages": {"charte_cuivre": 4 * OR, "rang_min": "C", "distance_cite_min": 6,
				 "distance_implantation_min": 4, "implantations_par_pays": 1,
				 "rattrapage_max_s": 3 * 86400, "visible_des_le": "campement"},
	"stocks": ["nourriture", "bois", "materiaux", "medicaments"],
	"axes_site": ["eau", "nourriture", "materiaux", "commerce", "defense", "danger"],
	"facteurs_securite": ["defense_physique", "defense_humaine", "environnement", "logistique",
						  "connaissance_territoire"],
	"feu": ["grand", "reduit"],
	"etapes_menace": ["presente", "a_remarque_le_lieu", "attaque_troupeaux_et_reserves", "taniere_localisee"],
	"metiers": ["agriculteur", "eleveur", "intendant", "bucheron", "chasseur", "aubergiste", "garde",
				"batisseur", "carrier", "pecheur"],
	"batiments": ["habitation", "entrepot", "ferme", "etable", "auberge", "boutique", "atelier", "poste_de_garde"],
	"guilde": {"independante": True, "echelons": [
		{"id": "auberge_aventuriers", "label": "Auberge d'aventuriers", "palier": "village"},
		{"id": "maison_aventuriers", "label": "Maison d'aventuriers", "palier": "bourg"},
		{"id": "demeure_aventuriers", "label": "Demeure des aventuriers", "palier": "petite_ville"},
		{"id": "guilde_aventuriers", "label": "Guilde d'aventuriers", "palier": "ville"},
		{"id": "grande_guilde_aventuriers", "label": "Grande guilde d'aventuriers", "palier": "ville"}]},
	"autres_joueurs": {
		"statuts": ["visiteur", "soutien", "associe"], "don_libre": True, "associe_vaut_presence": True,
		"entrepot_associe": "depot",
		"roles_associe": ["approvisionner", "financer_chantier", "pacifier_territoire", "amener_colons", "loger"],
		"recompenses_associe": ["prix_de_faveur", "membre_fondateur_guilde"],
		"tableau_besoins": True, "associations_actives_max": 1, "expiration_s": None,
		"associes_max": {p["id"]: 2 ** n for n, p in enumerate(PALIERS)},
		"reserve_au_fondateur": ["engager_pnj", "renvoyer_pnj", "choisir_amenagement", "regler_feu",
								 "vendre_production", "caisse", "accepter_associe", "exclure_associe"]},
}

# ── Lieux modèles génériques : (palier, image provisoire, largeur, hauteur) ──────────
# La grille grandit avec le palier (§ 12.1) ; ses proportions suivent celles de l'image.
MODELES = [
	("campement", "clairiere_du_charbonnier.jpg", 22, 12),
	("hameau", "hameau.png", 21, 14),
	("bourgade", "hameau.png", 27, 18),
	("village", "hameau.png", 33, 22),
	("bourg", "fortifications.png", 32, 28),
	("petite_ville", "fortifications.png", 40, 35),
	("ville", "fortifications.png", 48, 42),
]


def modele(palier: dict, image: str, w: int, h: int) -> dict:
	"""Lieu modèle générique : grille ouverte (aucun mur), entrées au milieu des bords — une
	au campement, deux au hameau, quatre ensuite (§ 12.6)."""
	entrees = [[w // 2, h - 1], [w // 2, 0], [0, h // 2], [w - 1, h // 2]]
	n = 1 if palier["rang"] == 1 else 2 if palier["rang"] == 2 else 4
	return {
		"_id": f"lieu:{colonisation.TAG_MODELE}_{palier['id']}",
		"type": "lieu",
		"label": f"{palier['label']} (modèle générique)",
		"image": image,
		"categorie": "modele_colonie",
		"tags": [colonisation.TAG_MODELE, palier["id"]],
		"dimensions": {"x": w, "y": h},
		"cells": [[1] * w for _ in range(h)],
		"nav": {},
		"entrees": entrees[:n],
	}


def dernier_dump(chemin=None) -> dict:
	chemin = chemin or (sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json"))) or [None])[-1]
	if not chemin:
		return {}
	with open(chemin, encoding="utf-8") as f:
		return {d.get("_id"): d for d in json.load(f)["docs"]}


def completer(valeur: dict, attendu: dict) -> list:
	"""Ajoute à `valeur` ce qui MANQUE d'`attendu`, sans jamais réécrire l'existant : un bloc
	absent ; dans un bloc dict, une clé absente ; dans une liste d'entrées à `id`, une entrée
	absente et, dans une entrée présente, une clé absente (une valeur retouchée par l'Auteur
	reste la sienne). Rend la liste des chemins ajoutés."""
	ajouts = []
	for cle, defaut in attendu.items():
		if cle not in valeur:
			valeur[cle] = copy.deepcopy(defaut)
			ajouts.append(cle)
		elif isinstance(defaut, dict) and isinstance(valeur[cle], dict):
			for sous, v in defaut.items():
				if sous not in valeur[cle]:
					valeur[cle][sous] = copy.deepcopy(v)
					ajouts.append(f"{cle}.{sous}")
		elif isinstance(defaut, list) and isinstance(valeur[cle], list) \
				and all(isinstance(x, dict) and "id" in x for x in defaut):
			par_id = {x.get("id"): x for x in valeur[cle] if isinstance(x, dict)}
			for entree in defaut:
				present = par_id.get(entree["id"])
				if present is None:
					valeur[cle].append(copy.deepcopy(entree))
					ajouts.append(f"{cle}[{entree['id']}]")
					continue
				for sous, v in entree.items():
					if sous not in present:
						present[sous] = copy.deepcopy(v)
						ajouts.append(f"{cle}[{entree['id']}].{sous}")
	return ajouts


def generer(par_id: dict) -> list:
	docs = []
	# 1. Les règles : le doc du dump, complété des blocs absents.
	existant = par_id.get(ID)
	regles = {k: v for k, v in (existant or {"_id": ID, "type": "rules"}).items() if k != "_rev"}
	valeur = copy.deepcopy(regles.get("value") or {})
	ajouts = completer(valeur, {**colonisation.DEFAUTS, **SOCLE})
	if ajouts:
		regles["value"] = valeur
		docs.append(regles)
	# 2. Les modèles génériques qui manquent.
	paliers = {p["id"]: p for p in valeur.get("paliers") or []}
	for palier_id, image, w, h in MODELES:
		doc = modele(paliers[palier_id], image, w, h)
		if doc["_id"] not in par_id:
			docs.append(doc)
	return docs


def controler(docs: list, par_id: dict) -> None:
	"""Contrôles de livraison (ici et non en test : `jsons/` est temporaire)."""
	ids = [d["_id"] for d in docs]
	assert len(set(ids)) == len(ids), "collision d'_id dans la sortie"
	for d in docs:
		if d["_id"] == ID:
			v = d["value"]
			pids = [p["id"] for p in v["paliers"]]
			assert all(b["palier_min"] in pids for b in v["batiments_def"])
			assert all(f["palier_min"] in pids and f.get("requis_pour", pids[0]) in pids for f in v["fortifications"])
			# chaque palier au-delà du premier trouve sa fortification minimale, sauf répétition (« murailles »)
			requis = {f["requis_pour"] for f in v["fortifications"] if f.get("requis_pour")}
			assert requis <= set(pids[1:]), requis
			metiers = {m["id"] for m in v["metiers_def"]} | {m["id"] for m in (par_id.get("rules:proprietes") or {}).get("value", {}).get("metiers", [])}
			if par_id.get("rules:proprietes"):
				for b in v["batiments_def"]:
					assert set(b.get("postes") or {}) <= metiers, (b["id"], set(b.get("postes") or {}) - metiers)
			assert {r["stock"] for r in v["depots"]} <= set(v["stocks"])
		else:
			assert d["_id"] not in par_id, f"{d['_id']} existe déjà"
			assert colonisation.modele_valide(d), d["_id"]
			assert any(os.path.exists(os.path.join(RACINE, "templates", "resources", r, d["image"]))
					   for r in ("towns", "maps", "battle_maps")), d["image"]


def main(argv: list) -> None:
	par_id = dernier_dump(argv[argv.index("--dump") + 1] if "--dump" in argv else None)
	docs = generer(par_id)
	controler(docs, par_id)
	if not docs:
		print("Rien à importer : le dump porte déjà les règles et les modèles.")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump({"docs": docs}, f, ensure_ascii=False, indent=1)
		f.write("\n")
	print(f"{len(docs)} doc(s) → {os.path.relpath(SORTIE, RACINE)} :", ", ".join(d["_id"] for d in docs))


if __name__ == "__main__":
	main(sys.argv[1:])

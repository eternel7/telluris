"""Règles de la voie de colonisation : `rules:colonisation` (valeurs de départ, AUCUN moteur ne les lit encore).

    python dev/gen_colonisation.py

Sortie :
    jsons/colonisation_a_importer.json   (à coller dans la carte d'import de /admin)

Doc NEUF : le lancement refuse d'écrire si `rules:colonisation` existe déjà dans le dump le
plus récent (le PUT complet de l'import l'écraserait). Relancer régénère le fichier à
l'identique (idempotent). Décisions de l'Auteur : docs/lore/systemes/20261112_voie_de_colonisation.md."""

import glob
import json
import os

ICI = os.path.dirname(os.path.abspath(__file__))
JSONS = os.path.join(ICI, "..", "jsons")
SORTIE = os.path.join(JSONS, "colonisation_a_importer.json")
ID = "rules:colonisation"

OR = 10000  # cuivre par or (utils/characters.CUIVRE_PAR_OR)

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

paliers = [{"id": i, "label": l, "rang": n + 1, "population_min": pop, "postes_min": postes,
			"prix_statut_cuivre": prix * OR, "fortification_min": fortif, "menace": menace, "ouvre": ouvre}
		   for n, (i, l, pop, postes, prix, fortif, menace, ouvre) in enumerate(_PALIERS)]

reglages = {
	"charte_cuivre": 4 * OR,           # payée au maître de guilde de la cité la plus proche
	"rang_min": "C",                   # échelle recrutement.RANGS
	"distance_cite_min": 6,            # cases de la carte du pays
	"distance_implantation_min": 4,
	"implantations_par_pays": 1,
	"rattrapage_max_s": 3 * 86400,     # absence du fondateur : au-delà, le lieu se fige
	"visible_des_le": "campement",
}

stocks = ["nourriture", "bois", "materiaux", "medicaments"]  # l'eau est un trait du site
axes_site = ["eau", "nourriture", "materiaux", "commerce", "defense", "danger"]
facteurs_securite = ["defense_physique", "defense_humaine", "environnement", "logistique", "connaissance_territoire"]
feu = ["grand", "reduit"]
etapes_menace = ["presente", "a_remarque_le_lieu", "attaque_troupeaux_et_reserves", "taniere_localisee"]

# S'AJOUTENT aux métiers de `rules:proprietes` (jamais recopiés ici).
metiers = ["agriculteur", "eleveur", "intendant", "bucheron", "chasseur", "aubergiste", "garde",
		   "batisseur", "carrier", "pecheur"]
batiments = ["habitation", "entrepot", "ferme", "etable", "auberge", "boutique", "atelier", "poste_de_garde"]

guilde = {
	"independante": True,
	"echelons": [
		{"id": "auberge_aventuriers", "label": "Auberge d'aventuriers", "palier": "village"},
		{"id": "maison_aventuriers", "label": "Maison d'aventuriers", "palier": "bourg"},
		{"id": "demeure_aventuriers", "label": "Demeure des aventuriers", "palier": "petite_ville"},
		{"id": "guilde_aventuriers", "label": "Guilde d'aventuriers", "palier": "ville"},
		{"id": "grande_guilde_aventuriers", "label": "Grande guilde d'aventuriers", "palier": "ville"},
	],
}

# Les autres joueurs (personnage PRINCIPAL seul ; ni clone de compagnon, ni monture).
autres_joueurs = {
	"statuts": ["visiteur", "soutien", "associe"],  # soutien = a donné ; associé = accepté par le fondateur
	"don_libre": True,                    # tout visiteur donne aux stocks, sans accord
	"associe_vaut_presence": True,        # combat joué ET rattrapage déclenché par sa visite
	"entrepot_associe": "depot",          # retrait seulement si le fondateur l'autorise, associé par associé
	"roles_associe": ["approvisionner", "financer_chantier", "pacifier_territoire", "amener_colons", "loger"],
	"recompenses_associe": ["prix_de_faveur", "membre_fondateur_guilde"],  # pas de parts sur la caisse
	"tableau_besoins": True,              # dérivé des stocks bas, sans récompense
	"associations_actives_max": 1,        # par personnage, en plus de ses propres implantations
	"expiration_s": None,                 # aucune : départ volontaire ou exclusion seulement
	# 1, 2, 4… : doublement par palier (valeurs de départ)
	"associes_max": {p["id"]: 2 ** n for n, p in enumerate(paliers)},
	"reserve_au_fondateur": ["engager_pnj", "renvoyer_pnj", "choisir_amenagement", "regler_feu",
							 "vendre_production", "caisse", "accepter_associe", "exclure_associe"],
}

# ── Contrôles au lancement ─────────────────────────────────────────────────────
ids = [p["id"] for p in paliers]
assert len(set(ids)) == len(ids)
for a, b in zip(paliers, paliers[1:]):
	assert a["population_min"] < b["population_min"] and a["postes_min"] < b["postes_min"], b["id"]
	assert a["prix_statut_cuivre"] < b["prix_statut_cuivre"], b["id"]
assert all(e["palier"] in ids for e in guilde["echelons"])
assert reglages["visible_des_le"] in ids
assert list(autres_joueurs["associes_max"]) == ids

dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
if dumps:
	with open(dumps[-1], encoding="utf-8") as f:
		assert all(d.get("_id") != ID for d in json.load(f)["docs"]), f"{ID} existe déjà dans {dumps[-1]}"

doc = {"_id": ID, "type": "rules",
	   "value": {"paliers": paliers, "reglages": reglages, "stocks": stocks, "axes_site": axes_site,
				 "facteurs_securite": facteurs_securite, "feu": feu, "etapes_menace": etapes_menace,
				 "metiers": metiers, "batiments": batiments, "guilde": guilde,
				 "autres_joueurs": autres_joueurs}}
with open(SORTIE, "w", encoding="utf-8") as f:
	json.dump({"docs": [doc]}, f, ensure_ascii=False, indent=2)
	f.write("\n")
print(len(paliers), "paliers,", len(metiers), "métiers,", len(batiments), "bâtiments,", len(guilde["echelons"]), "échelons")

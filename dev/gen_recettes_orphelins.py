"""Écrit une recette pour chaque item ORPHELIN — ni produit ni utilisé par aucune recette.

« Orphelin » est la définition de /admin/recettes-graphe (mode ⊘ Orphelins) : rôle `isole`
dans le réseau de `utils.graphe_recettes.construire_graphe` — aucune arête `recette` entrante
ni sortante, une sous-catégorie `hors_recette` ne comptant pas. Le graphe est construit ici
par le MÊME module que l'écran ; seule la règle de rôle (`roleNoeud`, JS) est recopiée.

Exclus, sans recette :
  · les COMPOSANTS (`categorie == "composant"`) — à la demande ;
  · les livres de CONTENU (`scriptorium.SOUS_CATEGORIES_LIVRE_CONTENU`) : générés par le
    tick d'atelier du scriptorium (`scriptorium._recette_virtuelle`), jamais par un doc
    `recette:*` — leur en écrire une doublerait la production ;
  · `EXCLUS` : objets dont la RARETÉ est le sens (carte de guilde délivrée à l'inscription).

    python dev/gen_recettes_orphelins.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/recettes_orphelins_a_importer.json   (carte d'import de /admin)

⚠️ Garde-fous — rien n'est écrit si l'un d'eux échoue :
  · tout intrant est déjà CONSOMMÉ ou PRODUIT par les métiers réunis de la catégorie, ou une
    vraie FEUILLE du monde (`_get_marche_map()["feuilles"]`) : jamais de fausse feuille
    (cf. telluris-economie § Armement). Une feuille neuve pour la catégorie ouvre un point de
    vente — listé en sortie (ici `item:Chiffon` au tissage : la base n'a ni lin, ni laine
    tissée, ni soie ; le tissu des vêtements est le chiffon, la laine les `poils`/le feutre) ;
  · le doc de chaque intrant existe (sinon valorisé à vide) ;
  · la catégorie de lieu existe dans le monde (sinon la recette ne cuit nulle part) ;
  · une recette de GRANDE MAISON est croisée (`_metier_unique`, mêmes règles que
    dev/gen_magasins_superieurs.py), contrôlée APRÈS ajout du lot ;
  · le produit n'était pas une feuille (le produire couperait son approvisionnement) ;
  · tout orphelin non exclu a sa ligne dans `TABLE`, et toute ligne vise un orphelin.

Idempotent : une recette déjà en base à l'identique est sautée, un `_id` occupé par autre
chose fait tout refuser ; un item qui a gagné une recette depuis est sauté (signalé).
Le moteur est celui du jeu : `db.config` est rebranché sur le dump AVANT d'importer
`utils.marche` (même procédé que dev/audit_economy.py).
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "recettes_orphelins_a_importer.json")

EXCLUS = {
	"item:carte_aventurier": "délivrée par la guilde à l'inscription (`lieu_parent` localisé)",
}

CATEGORIES_EXCLUES = {"composant"}

# item → (lieu_categorie, [(clé matière, quantité)…], quantité produite).
# Clé `item:…` = item précis ; sinon sous-catégorie — même forme que les recettes en base.
TABLE = {
	# ── Tissage : laine (poils, feutre) et tissu (chiffon) ──────────────────────────
	"Bandeau_meditation":   ("tissage", [("item:Chiffon", 1)], 2),
	"Bonnet_de_clerc":      ("tissage", [("item:feutre", 1)], 1),
	"Cagoule":              ("tissage", [("poils", 2)], 1),
	"Cape_soie_sombre":     ("tissage", [("item:Chiffon", 4)], 1),
	"Capuche_bordeaux":     ("tissage", [("item:Chiffon", 1)], 1),
	"Capuche_de_laine":     ("tissage", [("poils", 2)], 1),
	"Capuche_noire":        ("tissage", [("item:Chiffon", 1)], 1),
	"Capuche_soie":         ("tissage", [("item:Chiffon", 1)], 1),
	"Capuchon_de_lin":      ("tissage", [("item:Chiffon", 1)], 1),
	"Chapeau_mou":          ("tissage", [("item:feutre", 1)], 1),
	"Chausses_ajustees":    ("tissage", [("item:Chiffon", 2)], 1),
	"Chausses_bicolores":   ("tissage", [("item:Chiffon", 2)], 1),
	"Chausses_laine":       ("tissage", [("poils", 3)], 1),
	"Couvre_chef_office":   ("tissage", [("item:feutre", 1), ("item:Chiffon", 1)], 1),
	"Jupe_de_chanvre":      ("tissage", [("item:Chiffon", 2)], 1),
	"Jupe_longue_lin":      ("tissage", [("item:Chiffon", 3)], 1),
	"Pantalon_ajuste_noir": ("tissage", [("item:Chiffon", 2)], 1),
	"Pantalon_ample":       ("tissage", [("item:Chiffon", 3)], 1),
	"Pantalon_toile":       ("tissage", [("item:Chiffon", 2)], 1),
	"Pantalon_velours":     ("tissage", [("item:Chiffon", 2), ("poils", 1)], 1),
	"Robe_bordeaux":        ("tissage", [("item:Chiffon", 4)], 1),
	"Robe_de_savant":       ("tissage", [("item:Chiffon", 4)], 1),
	"Robe_laine_epaisse":   ("tissage", [("poils", 4), ("item:feutre", 1)], 1),
	"Robe_lin_ceinturee":   ("tissage", [("item:Chiffon", 3)], 1),
	"Robe_noire_capuche":   ("tissage", [("item:Chiffon", 4)], 1),
	"Sous_robe_lin":        ("tissage", [("item:Chiffon", 2)], 1),
	"Sous_robe_noire":      ("tissage", [("item:Chiffon", 2)], 1),
	"Tunique_feuilles":     ("tissage", [("item:Chiffon", 2)], 1),
	# ── Grande manufacture textile : pièces d'apparat, croisées tissage × plumasserie ──
	"Chapeau_large_bord":   ("grande_manufacture_textile", [("item:feutre", 1), ("plumes", 1)], 1),
	"Pourpoint_colore":     ("grande_manufacture_textile", [("item:Chiffon", 2), ("item:parure", 1)], 1),
	"Robe_ceremonie":       ("grande_manufacture_textile", [("item:Chiffon", 4), ("item:parure", 1)], 1),
	# ── Cordonnerie ────────────────────────────────────────────────────────────────
	"Sandales_lierre":      ("cordonnerie", [("item:corde", 1)], 1),
	# ── Scriptorium : documents et grimoires d'équipement ───────────────────────────
	"Carnet_chansons":      ("scriptorium", [("item:Papier", 2), ("item:Encre", 1)], 1),
	"Carnet_de_sorts":      ("scriptorium", [("item:Papier", 3), ("item:Encre", 1), ("item:Encre_magique", 1)], 1),
	"Carnet_illusionniste": ("scriptorium", [("item:Papier", 2), ("item:Encre", 1), ("item:pigment", 1)], 1),
	"Dico_des_langues":     ("scriptorium", [("item:Papier", 6), ("item:Encre", 2)], 1),
	"Lettre_de_creance":    ("scriptorium", [("item:Parchemin_blanc", 1), ("item:Encre", 1), ("item:Cire_a_cacheter", 1)], 1),
	"Livre_prieres":        ("scriptorium", [("item:Papier", 3), ("item:Encre", 1)], 1),
	"Manuel_creatures":     ("scriptorium", [("item:Papier", 4), ("item:Encre", 1), ("item:pigment", 1)], 1),
	"Parchemin_ordre":      ("scriptorium", [("item:Parchemin_blanc", 1), ("item:Encre", 1)], 1),
	"Grimoire_base":        ("scriptorium", [("item:Papier", 4), ("item:Encre", 2)], 1),
	"Grimoire_necromancie": ("scriptorium", [("item:Papier", 4), ("item:Encre_magique", 1), ("residu_spectral", 1)], 1),
	"Grimoire_pactes":      ("scriptorium", [("item:Papier", 3), ("item:Parchemin_vierge", 1), ("item:Encre_magique", 2)], 1),
	# ── Bijouterie : catalyseurs, miroirs, pierres ──────────────────────────────────
	"Orbe_arcanique":       ("bijouterie", [("gemmes", 2), ("metaux_precieux", 1)], 1),
	"Symbole_sacre":        ("bijouterie", [("metaux_precieux", 1)], 1),
	"Miroir_de_poche":      ("bijouterie", [("metaux_precieux", 1)], 1),
	"Petite_glace":         ("bijouterie", [("metaux_precieux", 1)], 2),
	"Pierre_de_meditation": ("bijouterie", [("gemmes", 1)], 1),
	# ── Corderie ───────────────────────────────────────────────────────────────────
	"Corde_5m":             ("corderie", [("item:corde", 1)], 1),
	"Corde_10m":            ("corderie", [("item:corde", 2)], 1),
	"Piege_a_collet":       ("corderie", [("item:corde", 1)], 2),
	# ── Lutherie ───────────────────────────────────────────────────────────────────
	"Cordes_rechange":      ("lutherie", [("item:cordes_d_instrument", 2)], 1),
	# ── Armurerie : petite serrurerie, pierre à aiguiser (débris de golem) ──────────
	"Crochet_serrurier":    ("armurerie", [("fer", 1)], 2),
	"Crochets":             ("armurerie", [("fer", 1)], 2),
	"Menottes":             ("armurerie", [("fer", 2)], 1),
	"Pierre_a_aiguiser":    ("armurerie", [("debris_anime", 1)], 4),
	# ── Atelier d'artisan : craie d'os ──────────────────────────────────────────────
	"Craie":                ("atelier_d_artisan", [("ossements", 1)], 3),
	# ── Apothicairerie : fard (pigment + graisse) ───────────────────────────────────
	"Fard_de_scene":        ("apothicairerie", [("item:pigment", 1), ("graisse", 1)], 2),
	# ── Salaison ───────────────────────────────────────────────────────────────────
	"Ration_de_voyage":     ("salaison", [("viande", 1), ("item:Sel", 1)], 2),
	# ── Empenneur : munitions ───────────────────────────────────────────────────────
	"Carquois_20":          ("atelier_de_l_empenneur", [("item:empennage_de_fleches", 2), ("manche", 2), ("fer", 1), ("cuir", 1)], 1),
	"Carreaux_argentes":    ("atelier_de_l_empenneur", [("item:empennage_de_fleches", 1), ("manche", 1), ("argent", 1)], 1),
}


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun jsons/telluris-dump-*.json — exporter depuis /admin.")
	return dumps[-1]


def brancher_moteur(docs: list):
	"""Rebranche `db.config` sur `docs` (liste MUTABLE : l'appelant y ajoute le lot puis
	appelle `marche.reset_prix_cache()` pour revalider) AVANT d'importer `utils.marche`."""
	os.environ["COUCHDB_HOST"] = "127.0.0.1"
	os.environ["COUCHDB_PORT"] = "1"          # coupe court à toute connexion CouchDB
	if RACINE not in sys.path:
		sys.path.insert(0, RACINE)

	import db.config as dbc
	dbc.get_doc = lambda doc_id: next((dict(d) for d in docs if d.get("_id") == doc_id), None)
	dbc.find_docs = lambda selecteur, **kw: [
		dict(d) for d in docs
		if isinstance(d, dict) and all(v == {"$gt": None} or d.get(k) == v
									   for k, v in (selecteur or {}).items())
	]
	dbc.save_doc = lambda doc: doc            # génération en lecture seule
	dbc.delete_doc = lambda doc: None
	dbc.server = None
	dbc.db = None

	from models import character_stats
	from utils import marche
	character_stats.load_world_variables()
	marche.reset_prix_cache()
	return marche


def orphelins(docs: list) -> list:
	"""Items de rôle `isole` — miroir de `roleNoeud`/`estOrphelin` (admin_recettes_graphe.html)
	sur le graphe de `construire_graphe`."""
	from utils.graphe_recettes import construire_graphe
	items = [d for d in docs if str(d.get("_id", "")).startswith("item:")]
	recettes = [d for d in docs if d.get("type") == "recette"]
	g = construire_graphe(recettes, items)
	noeuds = {n["id"]: n for n in g["nodes"]}
	produit, sert = set(), set()
	for e in g["edges"]:
		if e["kind"] == "recette":
			produit.add(e["target"])
			sert.add(e["source"])
		elif e["kind"] == "membre" and not noeuds[e["target"]].get("hors_recette"):
			sert.add(e["source"])
	return sorted(i for i, n in noeuds.items()
				  if n["type"] == "item" and i not in produit and i not in sert)


def recette_doc(slug: str, ligne) -> dict:
	categorie, matieres, produite = ligne
	return {
		"_id": "recette:%s_%s" % (categorie, slug.lower()),
		"type": "recette",
		"lieu_categorie": categorie,
		"objet_final": slug,
		"quantite_produite": produite,
		"matieres_premieres": [
			({"item": cle} if cle.startswith("item:") else {"sous_categorie": cle})
			| {"quantite": q}
			for cle, q in matieres
		],
	}


def _metier_unique(marche, grande: str, cles: list) -> str | None:
	"""Métier réuni capable de fournir À LUI SEUL toutes ces clés (cf.
	dev/gen_magasins_superieurs.py) : la recette n'aurait alors rien d'exclusif."""
	mm = marche._get_marche_map()
	for metier in marche.categories_incluses(grande)[1:]:
		couvert = mm["besoins"].get(metier, set()) | mm["produits"].get(metier, set())
		if all(cle in couvert for cle in cles):
			return metier
	return None


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	args = ap.parse_args()
	chemin = args.dump or dernier_dump()
	print("source : %s" % os.path.relpath(chemin, RACINE))
	docs = [d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")]
	index = {d["_id"]: d for d in docs}

	marche = brancher_moteur(docs)
	from models import character_stats
	from utils import scriptorium

	# ── Qui est orphelin, qui est exclu ───────────────────────────────────────────
	orph = orphelins(docs)
	cibles, exclus = [], {}
	for i in orph:
		d = index[i]
		if d.get("categorie") in CATEGORIES_EXCLUES:
			exclus.setdefault("composant", []).append(i)
		elif d.get("sous_categorie") in scriptorium.SOUS_CATEGORIES_LIVRE_CONTENU:
			exclus.setdefault("livre de contenu (tick du scriptorium)", []).append(i)
		elif i in EXCLUS:
			exclus.setdefault(EXCLUS[i], []).append(i)
		else:
			cibles.append(i)
	print("%d orphelin(s) : %d à couvrir" % (len(orph), len(cibles)))
	for raison, ids in sorted(exclus.items()):
		print("  exclus — %s : %d" % (raison, len(ids)))

	erreurs, notes = [], []
	slugs = {"item:" + s for s in TABLE}
	for i in cibles:
		if i not in slugs:
			erreurs.append("%s : orphelin sans ligne dans TABLE" % i)

	# ── Contrôles AVANT ajout (état de la base) ───────────────────────────────────
	mm = marche._get_marche_map()
	lieux_cats = {d.get("categorie") for d in docs if d["_id"].startswith("lieu:")}
	nouveaux, deja, ouvertures = [], 0, []
	for slug, ligne in sorted(TABLE.items()):
		item_id = "item:" + slug
		doc = recette_doc(slug, ligne)
		existant = index.get(doc["_id"])
		if existant is not None:
			if {k: v for k, v in existant.items() if k != "_rev"} == doc:
				deja += 1
			else:
				erreurs.append("%s : _id déjà pris par un autre doc" % doc["_id"])
			continue
		if item_id not in index:
			erreurs.append("%s : aucun doc item" % item_id)
			continue
		if item_id not in orph:
			notes.append("%s : n'est plus orphelin, sauté" % item_id)
			continue
		cat = ligne[0]
		if cat not in lieux_cats:
			erreurs.append("%s : aucun lieu de catégorie « %s »" % (doc["_id"], cat))
		if item_id in mm["feuilles"] or slug in mm["feuilles"]:
			erreurs.append("%s : est une feuille — la produire couperait son appro" % item_id)
		besoins = set(marche.besoins_categorie(cat))
		produits = marche.produits_categorie(cat)
		for cle, _q in ligne[1]:
			mid = marche.matiere_item_id(cle)
			if mid not in index:
				erreurs.append("%s : intrant %s sans doc (%s)" % (doc["_id"], cle, mid))
			if cle in besoins or mid in produits:
				continue
			if cle in mm["feuilles"]:
				ouvertures.append((cat, cle))
				continue
			erreurs.append("%s : %s n'est ni consommé ni produit par « %s » ni une feuille — "
						   "FAUSSE FEUILLE" % (doc["_id"], cle, cat))
		nouveaux.append(doc)

	# ── Contrôles APRÈS ajout du lot (croisement des grandes maisons) ─────────────
	docs.extend(nouveaux)
	marche.reset_prix_cache()
	for doc in nouveaux:
		cat = doc["lieu_categorie"]
		if cat in character_stats.LIEU_CATEGORIES_FUSION:
			cles = [c for c, _q in marche.recette_matieres(doc)]
			seul = _metier_unique(marche, cat, cles)
			if seul:
				erreurs.append("%s : « %s » fournit seul tous les intrants — recette non croisée"
							   % (doc["_id"], seul))

	for n in notes:
		print("  · " + n)
	for cat, cle in sorted(set(ouvertures)):
		print("  ⚠ point de vente ouvert : %s au rayon de « %s »" % (cle, cat))
	if erreurs:
		print("\n%d ERREUR(S) — rien n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("  ✗ " + e)
		sys.exit(1)
	print("%d recette(s) déjà en base, %d à importer" % (deja, len(nouveaux)))
	if not nouveaux:
		print("Base à jour — aucun fichier écrit.")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(nouveaux, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("→ %s" % os.path.relpath(SORTIE, RACINE))


if __name__ == "__main__":
	main()

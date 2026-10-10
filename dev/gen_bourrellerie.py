"""Bourrellerie : demi-produits de sanglerie, pièces de cuir bouilli et HARNACHEMENT de monture.

Avant ce lot, la bourrellerie ne cuisait que deux recettes (outres, harnais). Ce lot lui
donne une chaîne : cinq demi-produits (sangles, boucles, cuir bouilli, bourrelet de crin,
courroie poissée) qu'elle consomme elle-même ET qu'elle fournit, par le flux de cité, à
l'armurerie, la cordonnerie, l'empenneur et la grande manufacture du cuir — plus le
harnachement des montures (`montures.SLOTS_MONTURE`, bloc `monture.charge_pct`).

    python dev/gen_bourrellerie.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/bourrellerie_a_importer.json   (carte d'import de /admin)

⚠️ Garde-fous — rien n'est écrit si l'un d'eux échoue :
  · aucun `_id` (item ou recette) déjà pris par un AUTRE doc ; un doc identique en base est
    sauté (régénération idempotente) ;
  · tout intrant a son doc (en base ou créé par ce lot) ;
  · tout produit a son doc, et n'est PAS une feuille du monde (le produire couperait son
    approvisionnement) ;
  · la catégorie de chaque recette existe dans le monde ;
  · lot ajouté, chaque intrant est, pour la catégorie qui le consomme : une feuille LIVRÉE
    sur place (`appro_leaves_categorie`, débit > 0), OU un produit de la catégorie (fusion
    comprise), OU un produit d'une catégorie présente dans CHACUNE des cités où la
    consommatrice existe (il viendra par le flux de cité) — sinon c'est une FAUSSE FEUILLE ;
  · une recette de GRANDE MAISON est croisée (`_metier_unique`) ;
  · tout slot est un emplacement connu (personnage ou monture), et un objet ne mêle jamais
    les deux familles ; seul un objet de monture porte un bloc `monture`.

Le bloc `fabrication` du Cuir bouilli (matière de sur-mesure) n'est PAS posé ici : il vit
dans la table de dev/gen_fabrication_matieres.py — relancer ce générateur APRÈS l'import.
"""

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_recettes_orphelins import _metier_unique, brancher_moteur, dernier_dump  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "bourrellerie_a_importer.json")

SLOTS_PERSONNAGE = {
	"main_droite", "main_gauche", "torse", "tete", "epaules", "jambes",
	"pieds", "mains", "anneau_1", "anneau_2", "cou", "ceinture",
}
# Miroir de `utils.montures.SLOTS_MONTURE` — relu à l'exécution dans `controler_items`.
SLOTS_MONTURE = {"monture_dos", "monture_tete", "monture_poitrail"}


def _composant(nom, icon, poids, description):
	return {"nom": nom, "icon": icon, "rarete": "commun", "categorie": "composant",
			"slots": [], "poids": poids, "description": description}


def _piece(nom, icon, slot, poids, description, rarete="commun", tags=(), **bonus):
	doc = {"nom": nom, "icon": icon, "rarete": rarete, "categorie": "armure",
		   "slots": [slot], "poids": poids, "description": description, "tags": list(tags)}
	doc.update(bonus)
	return doc


def _harnais(nom, icon, slot, poids, description, charge_pct=0, rarete="commun", **bonus):
	"""Pièce de harnachement : tag `harnachement`, bloc `monture` seulement s'il sert."""
	doc = _piece(nom, icon, slot, poids, description, rarete, ("harnachement",), **bonus)
	if charge_pct:
		doc["monture"] = {"charge_pct": charge_pct}
	return doc


# ── Les items ─────────────────────────────────────────────────────────────────
# Valeurs calées sur l'existant (dump 10/10) : cuirasse de cuir bouilli entre `armure_de_cuir`
# (PA 5) et la cuir clouté (PA 9) ; jambières un cran au-dessus de `Jambières_cuir_renf`.
# Harnachement : la charge d'une monture vaut F×5×charge_mult (1,2-1,5) ; un dos chargé
# (bât 35 %) + collier (15 %) + bride (5 %) plafonne à +55 %.
ITEMS = {
	# ── Demi-produits ─────────────────────────────────────────────────────────
	"Sangle_de_cuir": _composant(
		"Sangles de cuir", "🎗️", 0.15,
		"Bandes de peau refendues au couteau à pied et lissées à l'os : le premier ouvrage "
		"du bourrelier, et celui qui sert à tout le reste."),
	"Boucle_de_fer": _composant(
		"Boucles de fer", "🔗", 0.05,
		"Boucles à ardillon tirées d'un lingot, par poignées. Une sangle sans boucle n'est "
		"qu'une lanière."),
	"Cuir_bouilli": _composant(
		"Cuir bouilli", "🟫", 0.4,
		"Peau trempée dans la poix chaude puis mise en forme sur un moule de bois. En "
		"refroidissant, elle devient dure comme de la corne."),
	"Bourrelet_de_crin": _composant(
		"Bourrelet de crin", "🧶", 0.3,
		"Boudin de toile bourré de crin tassé, que l'on coud sous ce qui porte ou ce qui "
		"frotte. Le métier tient son nom de lui."),
	"Courroie_poissee": _composant(
		"Courroie poissée", "🪢", 0.1,
		"Deux sangles cousues l'une sur l'autre au fil poissé : la pluie n'y entre pas et la "
		"couture ne cède pas."),
	# ── Pièces de la bourrellerie ─────────────────────────────────────────────
	"Sacoche_de_ceinture": _piece(
		"Sacoche de ceinture", "👝", "ceinture", 0.5,
		"Une poche de cuir à rabat bouclé, pendue à la hanche. Ce qu'on y range se trouve "
		"sans quitter l'ennemi des yeux.", bonus_initiative=2),
	"Bricole_de_portefaix": _piece(
		"Bricole de portefaix", "🎽", "epaules", 1.2,
		"Le harnais des porteurs de halle : une courroie de poitrail rembourrée qui reporte "
		"la charge des reins sur les épaules.", rarete="peu_commun", bonus_pa=1, bonus={"F": 2}),
	"Casque_de_cuir_bouilli": _piece(
		"Casque de cuir bouilli", "⛑️", "tete", 0.8,
		"Une calotte moulée d'une seule pièce, jugulaire bouclée. Plus léger que le fer, "
		"moins bruyant aussi.", bonus_pa=2),
	"Cuirasse_de_cuir_bouilli": _piece(
		"Cuirasse de cuir bouilli", "🦺", "torse", [4, 6],
		"Plastron et dossière de cuir durci, réunis aux flancs par des sangles bouclées. On "
		"la serre comme on sangle une selle.", bonus_pa=8, bonus={"Ag": -3}),
	"Jambieres_de_cuir_bouilli": _piece(
		"Jambières de cuir bouilli", "🦵", "jambes", 1.4,
		"Cuissots et genouillères de cuir moulé, tenus par trois sangles chacun.",
		bonus_pa=3, bonus={"Ag": -1}),
	"Fourreau_de_dos": _piece(
		"Fourreau de dos", "🗡️", "epaules", 0.7,
		"Fourreau de cuir bouilli monté sur courroies croisées, la poignée au-dessus de "
		"l'épaule : la lame sort d'un seul geste.", bonus_initiative=3),
	"Gorgerin_de_cuir_bouilli": _piece(
		"Gorgerin de cuir bouilli", "🧣", "cou", 0.5,
		"Un col dur qui couvre la gorge et le haut des clavicules, là où frappent les crocs.",
		bonus_pa=1),
	# ── Pièces d'autres métiers, nourries par la bourrellerie ─────────────────
	"Targe_a_enarmes": _piece(
		"Targe à énarmes", "🛡️", "main_gauche", [1.5, 3],
		"Petit bouclier de bois ferré, doublé de cuir bouilli. Les énarmes de courroie "
		"poissée le lient à l'avant-bras : il suit le geste au lieu de le freiner.",
		bonus_pa=6, bonus={"Ag": -1}, restriction={"F": 15}),
	"Guetres_de_route": _piece(
		"Guêtres de route", "🥾", "jambes", 0.5,
		"Jambières de peau fermées par une rangée de boucles, contre la boue, les ronces "
		"et les morsures basses.", bonus_pa=1, bonus={"Ag": 1}),
	"Carquois_de_cuir_bouilli": _piece(
		"Carquois de cuir bouilli", "🏹", "ceinture", 0.8,
		"Un étui rigide qui ne s'écrase pas sous la pluie ni dans les chutes ; les traits "
		"restent droits et viennent à la main.", bonus_pa=1, bonus_initiative=2),
	"Brigandine_de_courroyeur": _piece(
		"Brigandine de courroyeur", "🦺", "torse", [5, 8],
		"Une cuirasse de cuir bouilli doublée d'une veste souple et d'un bourrelet de crin "
		"aux épaules. Elle encaisse comme du fer et se porte des jours entiers.",
		rarete="peu_commun", bonus_pa=10, bonus={"Ag": -2, "R": 1}),
	# ── Harnachement de monture ───────────────────────────────────────────────
	"Selle_de_voyage": _harnais(
		"Selle de voyage", "🐎", "monture_dos", 4.0,
		"Arçon garni de crin, quartiers de peau, sangle et contre-sangle bouclées. La bête "
		"porte son cavalier sans se blesser le garrot.", charge_pct=10, bonus_pa=1),
	"Bat_de_portage": _harnais(
		"Bât de portage", "📦", "monture_dos", 6.0,
		"Deux panneaux rembourrés reliés par des arcs, avec crochets et sangles de charge. "
		"Une selle porte un homme, un bât porte un convoi.", charge_pct=35),
	"Selle_a_sacoches": _harnais(
		"Selle à sacoches", "🐎", "monture_dos", 5.0,
		"Une selle de voyage à laquelle on a cousu deux sacs de maroquinier, bouclés sur les "
		"flancs. Elle charge presque autant qu'un bât et protège mieux.",
		charge_pct=25, rarete="peu_commun", bonus_pa=1),
	"Collier_d_attelage": _harnais(
		"Collier d'attelage", "⭕", "monture_poitrail", 3.0,
		"Le gros bourrelet rembourré passé à l'encolure : la bête tire de l'épaule et non "
		"plus de la gorge, et sa charge ne l'étouffe plus.", charge_pct=15),
	"Barde_de_cuir_bouilli": _harnais(
		"Barde de cuir bouilli", "🛡️", "monture_poitrail", 8.0,
		"Un poitrail de cuir durci sur courroies poissées, qui couvre le cou et la poitrine "
		"de la bête contre griffes et crocs.",
		rarete="peu_commun", bonus_pa=6, bonus_pv=5, restriction={"F": 35}),
	"Chanfrein_de_cuir_bouilli": _harnais(
		"Chanfrein de cuir bouilli", "🐴", "monture_tete", 1.5,
		"Une plaque moulée qui couvre le front et le nez de la monture, sanglée sous la "
		"ganache.", bonus_pa=2),
	"Bride_de_route": _harnais(
		"Bride de route", "🐴", "monture_tete", 0.6,
		"Têtière, frontal et rênes de courroie poissée, mors doux. Une bête qu'on ne "
		"tiraille pas accepte une charge de plus.", charge_pct=5),
}

# ── Les recettes ──────────────────────────────────────────────────────────────
# slug produit → (catégorie de lieu, [(clé, quantité)], quantité produite). Clé = sous-
# catégorie (`peaux`, `poix`, `fer`, `lin`, `crins` — mêmes clés que les recettes en base)
# ou `item:<id>` pour un item sans sous-catégorie.
RECETTES = {
	# Demi-produits
	"Sangle_de_cuir":            ("bourrellerie", [("peaux", 1)], 3),
	"Boucle_de_fer":             ("bourrellerie", [("fer", 1)], 8),
	"Cuir_bouilli":              ("bourrellerie", [("peaux", 2), ("poix", 1)], 2),
	"Bourrelet_de_crin":         ("bourrellerie", [("crins", 2), ("lin", 1)], 1),
	"Courroie_poissee":          ("bourrellerie", [("item:Sangle_de_cuir", 2), ("item:Fil_poisse", 1)], 2),
	# Pièces de la bourrellerie
	"Sacoche_de_ceinture":       ("bourrellerie", [("item:Sangle_de_cuir", 1), ("peaux", 1), ("item:Boucle_de_fer", 1)], 1),
	"Bricole_de_portefaix":      ("bourrellerie", [("item:Courroie_poissee", 2), ("item:Bourrelet_de_crin", 1), ("item:Boucle_de_fer", 2)], 1),
	"Casque_de_cuir_bouilli":    ("bourrellerie", [("item:Cuir_bouilli", 1), ("item:Sangle_de_cuir", 1), ("item:Boucle_de_fer", 1)], 1),
	"Cuirasse_de_cuir_bouilli":  ("bourrellerie", [("item:Cuir_bouilli", 4), ("item:Sangle_de_cuir", 2), ("item:Boucle_de_fer", 4)], 1),
	"Jambieres_de_cuir_bouilli": ("bourrellerie", [("item:Cuir_bouilli", 2), ("item:Sangle_de_cuir", 2), ("item:Boucle_de_fer", 2)], 1),
	"Fourreau_de_dos":           ("bourrellerie", [("item:Cuir_bouilli", 1), ("item:Courroie_poissee", 2), ("item:Boucle_de_fer", 1)], 1),
	"Gorgerin_de_cuir_bouilli":  ("bourrellerie", [("item:Cuir_bouilli", 1), ("item:Boucle_de_fer", 1)], 1),
	# Autres métiers (demi-produits par le flux de cité)
	"Targe_a_enarmes":           ("armurerie", [("fer", 1), ("item:Cuir_bouilli", 2), ("item:Courroie_poissee", 2)], 1),
	"Guetres_de_route":          ("cordonnerie", [("peaux", 1), ("item:Sangle_de_cuir", 1), ("item:Boucle_de_fer", 3)], 1),
	"Carquois_de_cuir_bouilli":  ("atelier_de_l_empenneur", [("item:Cuir_bouilli", 1), ("item:Courroie_poissee", 1), ("item:Boucle_de_fer", 1)], 1),
	"Brigandine_de_courroyeur":  ("grande_manufacture_du_cuir", [("item:Cuirasse_de_cuir_bouilli", 1), ("item:Veste_cuir_souple", 1), ("item:Bourrelet_de_crin", 2)], 1),
	# Harnachement
	"Selle_de_voyage":           ("bourrellerie", [("peaux", 3), ("item:Bourrelet_de_crin", 1), ("item:Sangle_de_cuir", 2), ("item:Boucle_de_fer", 2)], 1),
	"Bat_de_portage":            ("bourrellerie", [("peaux", 2), ("item:Bourrelet_de_crin", 2), ("item:Sangle_de_cuir", 3), ("item:Boucle_de_fer", 4)], 1),
	"Collier_d_attelage":        ("bourrellerie", [("item:Bourrelet_de_crin", 2), ("item:Cuir_bouilli", 1), ("item:Sangle_de_cuir", 2), ("item:Boucle_de_fer", 2)], 1),
	"Barde_de_cuir_bouilli":     ("bourrellerie", [("item:Cuir_bouilli", 6), ("item:Courroie_poissee", 3), ("item:Boucle_de_fer", 6)], 1),
	"Chanfrein_de_cuir_bouilli": ("bourrellerie", [("item:Cuir_bouilli", 2), ("item:Sangle_de_cuir", 1), ("item:Boucle_de_fer", 2)], 1),
	"Bride_de_route":            ("bourrellerie", [("item:Courroie_poissee", 2), ("item:Boucle_de_fer", 3)], 1),
	"Selle_a_sacoches":          ("grande_manufacture_du_cuir", [("item:Selle_de_voyage", 1), ("item:sac", 2)], 1),
}


def item_doc(slug: str, table: dict = None) -> dict:
	d = dict((table or ITEMS)[slug])
	doc = {"_id": "item:" + slug, "type": "item", "nom": d.pop("nom"), "icon": d.pop("icon"),
		   "description": d.pop("description"), "rarete": d.pop("rarete"),
		   "categorie": d.pop("categorie"), "sous_categorie": "", "slots": d.pop("slots"),
		   "tags": d.pop("tags", []), "poids": d.pop("poids")}
	doc.update(d)
	return doc


def recette_doc(slug: str, table: dict = None) -> dict:
	categorie, matieres, produite = (table or RECETTES)[slug]
	return {
		"_id": "recette:%s_%s" % (categorie, slug.lower()),
		"type": "recette",
		"lieu_categorie": categorie,
		"objet_final": slug,
		"quantite_produite": produite,
		"matieres_premieres": [
			({"item": cle} if cle.startswith("item:") else {"sous_categorie": cle}) | {"quantite": q}
			for cle, q in matieres
		],
	}


def controler_items(docs_items: list, slots_monture=None) -> list:
	"""Erreurs de forme des items du lot (pur) : slots connus, familles jamais mêlées, bloc
	`monture` réservé au harnachement."""
	slots_monture = set(slots_monture or SLOTS_MONTURE)
	erreurs = []
	for doc in docs_items:
		slots = set(doc.get("slots") or [])
		inconnus = slots - SLOTS_PERSONNAGE - slots_monture
		if inconnus:
			erreurs.append("%s : emplacement(s) inconnu(s) %s" % (doc["_id"], sorted(inconnus)))
		monture = bool(slots & slots_monture)
		if monture and slots & SLOTS_PERSONNAGE:
			erreurs.append("%s : mêle emplacements de personnage et de monture" % doc["_id"])
		if doc.get("monture") and not monture:
			erreurs.append("%s : bloc `monture` sur un objet qui ne se pose pas sur une bête" % doc["_id"])
	return erreurs


def villes_par_categorie(docs: list) -> dict:
	"""{catégorie de lieu: {cité}} — la cité est le premier ancêtre `categorie == "ville"`."""
	index = {d["_id"]: d for d in docs if str(d.get("_id", "")).startswith("lieu:")}
	out = {}
	for lieu in index.values():
		courant, n = lieu, 0
		while courant and courant.get("categorie") != "ville" and n < 12:
			courant, n = index.get(courant.get("lieu_parent")), n + 1
		if courant and lieu.get("categorie") and lieu.get("categorie") != "ville":
			out.setdefault(lieu["categorie"], set()).add(courant["_id"])
	return out


def main(items: dict = None, recettes: dict = None, sortie: str = None):
	"""Contrôle puis écrit un lot items + recettes. Paramétré pour être rejoué par les
	générateurs frères (dev/gen_brosserie.py) : mêmes garde-fous, autre table."""
	items, recettes, sortie = items or ITEMS, recettes or RECETTES, sortie or SORTIE
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
	from utils import montures

	erreurs, nouveaux, deja = [], [], 0
	lot_items = [item_doc(s, items) for s in sorted(items)]
	lot_recettes = [recette_doc(s, recettes) for s in sorted(recettes)]
	erreurs += controler_items(lot_items, montures.SLOTS_MONTURE)

	# ── Contrôles AVANT ajout (état de la base) ──────────────────────────────
	mm = marche._get_marche_map()
	lieux_cats = {d.get("categorie") for d in docs if d["_id"].startswith("lieu:")}
	for doc in lot_items + lot_recettes:
		existant = index.get(doc["_id"])
		if existant is None:
			nouveaux.append(doc)
		elif {k: v for k, v in existant.items() if k != "_rev"} == doc:
			deja += 1
		else:
			erreurs.append("%s : _id déjà pris par un autre doc" % doc["_id"])
	ids_lot = {d["_id"] for d in lot_items}
	for slug, (cat, matieres, _q) in sorted(recettes.items()):
		if "item:" + slug not in ids_lot and "item:" + slug not in index:
			erreurs.append("item:%s : produit sans doc" % slug)
		if cat not in lieux_cats:
			erreurs.append("%s : aucun lieu de catégorie « %s »" % (slug, cat))
		if "item:" + slug in mm["feuilles"] or slug in mm["feuilles"]:
			erreurs.append("item:%s : est une feuille — la produire couperait son appro" % slug)
		for cle, _n in matieres:
			mid = marche.matiere_item_id(cle)
			if mid not in index and mid not in ids_lot:
				erreurs.append("%s : intrant %s sans doc (%s)" % (slug, cle, mid))

	# ── Contrôles APRÈS ajout du lot ─────────────────────────────────────────
	docs.extend(nouveaux)
	marche.reset_prix_cache()
	villes = villes_par_categorie(docs)
	ventes, flux = set(), set()
	for slug, (cat, matieres, _q) in sorted(recettes.items()):
		feuilles_livrees = set(marche.appro_leaves_categorie(cat))
		produits = marche.produits_categorie(cat)
		for cle, _n in matieres:
			mid = marche.matiere_item_id(cle)
			if cle in feuilles_livrees and marche._appro_debit_pour(cle) > 0:
				ventes.add((cat, cle))
				continue
			if mid in produits:
				continue
			producteurs = {c for c in villes if mid in marche.produits_categorie(c)}
			couvertes = set().union(*(villes[c] for c in producteurs)) if producteurs else set()
			manque = villes.get(cat, set()) - couvertes
			if producteurs and not manque:
				flux.add((cat, cle, ", ".join(sorted(producteurs))))
				continue
			erreurs.append("%s (%s) : %s n'arrive ni par l'appro, ni par l'atelier, ni par le flux "
						   "de %s — FAUSSE FEUILLE" % (slug, cat, cle, ", ".join(sorted(manque)) or "aucune cité"))
		if cat in character_stats.LIEU_CATEGORIES_FUSION:
			seul = _metier_unique(marche, cat, [c for c, _n in marche.recette_matieres(recette_doc(slug, recettes))])
			if seul:
				erreurs.append("%s : « %s » fournit seul tous les intrants — recette non croisée" % (slug, seul))

	for cat, cle in sorted(ventes):
		print("  ✓ %s acheté sur place par « %s » (point de vente au comptoir)" % (cle, cat))
	for cat, cle, prod in sorted(flux):
		print("  ↻ %s → « %s » par le flux de cité (produit par %s)" % (cle, cat, prod))
	if erreurs:
		print("\n%d ERREUR(S) — rien n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("  ✗ " + e)
		sys.exit(1)
	print("%d doc(s) déjà en base ; %d à importer (%d items, %d recettes)" % (
		deja, len(nouveaux), sum(1 for d in nouveaux if d["type"] == "item"),
		sum(1 for d in nouveaux if d["type"] == "recette")))
	if not nouveaux:
		print("Base à jour — aucun fichier écrit.")
		return
	with open(sortie, "w", encoding="utf-8") as f:
		json.dump(nouveaux, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("→ %s" % os.path.relpath(sortie, RACINE))


if __name__ == "__main__":
	main()

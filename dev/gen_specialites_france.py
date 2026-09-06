"""Génère l'import des SPÉCIALITÉS DE TERROIR : des recettes qui n'existent qu'à un endroit.

Une `recette:*` peut porter `lieu_portee`, un id de lieu : elle n'est alors cuisinable que par
les boutiques dont la chaîne d'ancêtres `lieu_parent` remonte jusqu'à lui
(`utils/marche.portees_lieu`). Champ ABSENT ⇒ portée mondiale, comportement d'avant.

    python dev/gen_specialites_france.py [chemin/vers/telluris-dump-*.json]

Sortie : jsons/specialites_france_a_importer.json (à coller dans la carte d'import de /admin)

⚠️ PRÉREQUIS DE DONNÉES, écrit par ce script : les cités n'avaient AUCUN `lieu_parent` — la
remontée s'arrêtait à la ville et `lieu:france` n'était atteignable par aucune chaîne. Les
trois cités sont donc réémises rattachées au pays (doc relu du dump, un seul champ ajouté).

⚠️ Ce script REBRANCHE `db.config` sur le dump AVANT d'importer `utils.marche`, puis injecte
ses propres docs dans la vue : les garde-fous s'exécutent donc sur l'état POST-IMPORT, avec le
moteur du jeu et non une réimplémentation. Une recette portée par un lieu sans boutique du
métier serait morte-née — c'est ce qui disqualifie Reims, qui n'a aucun commerce.

⚠️ La portée dit OÙ L'ON FABRIQUE, jamais COMBIEN ÇA VAUT : le coût de revient reste global
(`marche._get_recipe_map`), sans quoi on achèterait un plat là où il est produit pour le
revendre plus cher là où il ne l'est pas.
"""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "specialites_france_a_importer.json")

PAYS = "lieu:france"
CITES = ("lieu:auxerre", "lieu:lutecia", "lieu:rhemi")


# ── Matières premières neuves ────────────────────────────────────────────────────
# FEUILLES : aucune recette ne les produit, donc `appro_leaves_lieu` les livre — et
# seulement aux boutiques DANS LA PORTÉE, ce qui est la démonstration même du mécanisme :
# deux cuisines du même métier, une seule reçoit du vin.
# (slug, nom, icon, sous_categorie, poids, valeur_min, valeur_max, description)
MATIERES = [
	("Vin_de_pays", "Vin de pays", "🍷", "vin", 1.2, 14, 36,
	 "Un vin de l'année, tiré au tonneau et transvasé en cruche. On en boit, on en cuisine, "
	 "et le second usage vaut souvent mieux que le premier."),
	("Volaille", "Volaille", "🐔", "volaille", 1.6, 16, 40,
	 "Bête plumée et vidée, prête pour la broche ou la cocotte. Le cou et les abattis sont "
	 "laissés dedans, c'est ce qui fait le fond."),
	("Creme", "Crème", "🥛", "creme", 0.4, 10, 26,
	 "Crème levée sur le lait de la veille, épaisse à tenir la cuiller. Elle tourne en deux "
	 "jours, ce qui explique qu'on ne la trouve pas partout."),
	("Amandes", "Amandes", "🌰", "fruit_sec", 0.2, 15, 38,
	 "Amandes mondées et séchées. Venues du sud à dos de mulet, elles coûtent ce que coûte "
	 "la route."),
]


# ── Les dix spécialités ──────────────────────────────────────────────────────────
# (slug, nom, icon, rareté, poids, lieu_categorie, lieu_portee, effets, description,
#  matières, quantité_produite)
PLATS = [
	("Croissant", "Croissant", "🥐", "peu_commun", 0.15, "boulangerie", PAYS,
	 {"pv": 14, "duree": 4, "buffs": {"V": 3}},
	 "Pâte feuilletée au beurre, roulée et pliée six fois avant le four. Elle sort dorée, "
	 "creuse, et ne survit jamais jusqu'au soir.",
	 [("item:farine_de_froment", 2), ("item:motte_de_beurre", 3), ("item:levain_de_chef", 1)], 4),

	("Pain_de_campagne", "Pain de campagne", "🍞", "commun", 1.1, "boulangerie", PAYS,
	 {"pv": 20, "duree": 8, "buffs": {"R": 3}},
	 "Grosse miche à croûte épaisse, moitié froment moitié seigle. Elle se garde la semaine "
	 "et se coupe contre la poitrine.",
	 [("item:farine_de_froment", 1), ("item:farine_de_seigle", 2),
	  ("item:levain_de_chef", 1), ("item:Sel", 1)], 2),

	("Pain_d_epices", "Pain d'épices", "🍯", "peu_commun", 0.6, "boulangerie", PAYS,
	 {"pv": 18, "pm": 10, "duree": 6, "buffs": {"Vol": 3}},
	 "Pain de seigle chargé de miel et d'épices, cuit lentement. Il colle aux doigts et "
	 "réchauffe longtemps après qu'on l'a mangé.",
	 [("item:farine_de_seigle", 2), ("item:miel_de_bruyere", 4), ("item:epices_douces", 3)], 3),

	("Galette_des_Rois", "Galette des Rois", "👑", "rare", 0.9, "boulangerie", PAYS,
	 {"pv": 30, "pm": 15, "duree": 10, "buffs": {"Ch": 5}},
	 "Deux abaisses feuilletées scellées sur une crème d'amandes, et une fève cachée dedans. "
	 "Celui qui la trouve est roi jusqu'au soir — la chance, dit-on, lui reste plus longtemps.",
	 [("item:farine_de_froment", 2), ("item:motte_de_beurre", 2),
	  ("item:oeufs_de_ferme", 2), ("item:Amandes", 3)], 2),

	("Brioche_parisienne", "Brioche parisienne", "🥮", "peu_commun", 0.5,
	 "boulangerie", "lieu:lutecia",
	 {"pv": 22, "pm": 8, "duree": 6, "buffs": {"Cha": 3}},
	 "Autant d'œufs et de beurre que de farine, une nuit de pousse au frais, une tête bien "
	 "ronde. On ne la réussit qu'avec le lait de la capitale, prétendent les fourniers d'ici.",
	 [("item:farine_de_froment", 3), ("item:oeufs_de_ferme", 3),
	  ("item:motte_de_beurre", 3), ("item:levain_de_chef", 1)], 3),

	("Quiche_lorraine", "Quiche lorraine", "🥧", "peu_commun", 0.8,
	 "boulangerie", "lieu:auxerre",
	 {"pv": 26, "duree": 8, "buffs": {"R": 4}},
	 "Tarte salée d'œufs battus à la crème, semée de lardons fumés. Elle se mange tiède et "
	 "se transporte mal, ce qui la garde dans sa ville.",
	 [("item:farine_de_froment", 2), ("item:oeufs_de_ferme", 3),
	  ("item:Creme", 2), ("item:lard_sale", 2)], 2),

	("Pate_de_campagne", "Pâté de campagne", "🥩", "peu_commun", 0.7, "cuisine", PAYS,
	 {"pv": 24, "duree": 8, "buffs": {"R": 3}},
	 "Viande et foie hachés gros, tassés en terrine et cuits au bain. On le laisse rassir "
	 "trois jours avant d'y toucher ; c'est là qu'il est bon.",
	 [("item:foie", 2), ("item:viande", 2), ("item:graisse", 1), ("item:Sel", 1)], 2),

	("Pot_au_feu", "Pot-au-feu", "🍲", "peu_commun", 1.5, "cuisine", PAYS,
	 {"pv": 32, "duree": 10, "buffs": {"R": 5}},
	 "Viande et racines abandonnées une demi-journée dans le bouillon. Le plat tient au "
	 "corps, et le bouillon qui reste fait le repas du lendemain.",
	 [("item:viande", 3), ("item:Panais_de_sillon", 2), ("item:Chou_pomme", 2),
	  ("item:Sel", 1)], 3),

	("Coq_au_vin", "Coq au vin", "🍗", "rare", 1.2, "cuisine", PAYS,
	 {"pv": 34, "pm": 10, "duree": 10, "buffs": {"F": 4}},
	 "Volaille mise à mijoter dans son vin jusqu'à ce que la chair quitte l'os. La sauce, "
	 "réduite de moitié, vaut le plat.",
	 [("item:Volaille", 2), ("item:Vin_de_pays", 2), ("item:herbes_de_fournil", 1)], 2),

	("Boeuf_bourguignon", "Bœuf bourguignon", "🍷", "rare", 1.4, "cuisine", PAYS,
	 {"pv": 38, "duree": 10, "buffs": {"F": 5}},
	 "Morceaux de bœuf longuement cuits au vin rouge avec leurs racines. Trois heures de "
	 "feu doux, et l'on coupe la viande à la cuiller.",
	 [("item:viande", 3), ("item:Vin_de_pays", 2), ("item:Panais_de_sillon", 2)], 2),
]


# ── Lecture du dump et branchement du moteur ─────────────────────────────────────

def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def chemin_dump() -> str:
	"""Le dump passé en argv, sinon le plus récent de jsons/."""
	if len(sys.argv) > 1:
		return sys.argv[1] if os.path.isabs(sys.argv[1]) else os.path.join(RACINE, sys.argv[1])
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun jsons/telluris-dump-*.json — exporter depuis /admin.")
	return dumps[-1]


def brancher_moteur(docs: list, index: dict):
	"""Rebranche `db.config` sur la vue MUTABLE `index`/`docs` avant d'importer `utils.marche`.
	Les deux structures sont capturées par référence : y injecter les docs générés fait voir
	au moteur l'état POST-IMPORT, ce qui est exactement ce que les garde-fous doivent juger.

	⚠️ L'ordre est la seule chose qui compte : `utils/marche.py` fait `from db.config import
	get_doc, …`, les noms sont liés à l'import."""
	os.environ["COUCHDB_HOST"] = "127.0.0.1"
	os.environ["COUCHDB_PORT"] = "1"
	sys.path.insert(0, RACINE)

	import db.config as dbc
	dbc.get_doc = lambda doc_id: dict(index[doc_id]) if doc_id in index else None
	dbc.find_docs = lambda selecteur, *a, **kw: [
		dict(d) for d in docs
		if isinstance(d, dict) and all(d.get(k) == v for k, v in selecteur.items())
	]
	dbc.save_doc = lambda doc: doc
	dbc.delete_doc = lambda doc: None
	dbc.server = None
	dbc.db = None

	from models import character_stats
	from utils import marche
	character_stats.load_world_variables()   # sans DB : garde les défauts du code
	marche.reset_prix_cache()
	return character_stats, marche


def _atteignables(marche, lieu_doc: dict) -> set:
	"""Clés disponibles dans CE lieu sans le joueur : point fixe amorcé par les seules feuilles
	EFFECTIVEMENT LIVRÉES (`approvisionner` saute les débits nuls — les simples se récoltent,
	ils ne se livrent pas). Sert au rapport, pas au refus : plusieurs métiers dépendent déjà du
	joueur, et la portée n'avait pas à changer cela."""
	dispo = {cle for cle in marche.appro_leaves_lieu(lieu_doc)
			 if marche._appro_debit_pour(cle) > 0}
	recettes = marche.recettes_lieu(lieu_doc)
	bouge = True
	while bouge:
		bouge = False
		for r in recettes:
			entrees = [cle for (cle, _q) in marche.recette_matieres(r)]
			if not entrees or not all(c in dispo for c in entrees):
				continue
			for cle in (marche.objet_final_item_id(r.get("objet_final", "")),
						r.get("objet_final")):
				if cle and cle not in dispo:
					dispo.add(cle)
					bouge = True
	return dispo


# ── Génération ───────────────────────────────────────────────────────────────────

def main() -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	source = chemin_dump()
	docs = charger(source)
	index = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	character_stats, marche = brancher_moteur(docs, index)

	sortie, erreurs = [], []

	def emettre(doc: dict) -> None:
		"""Ajoute le doc à la sortie ET à la vue du moteur : les garde-fous jugent l'état
		post-import, pas l'état du dump."""
		sortie.append(doc)
		index[doc["_id"]] = doc
		docs.append(doc)

	# --- 1. Les cités pendent au pays -------------------------------------------------
	if PAYS not in index:
		erreurs.append("%s introuvable dans %s" % (PAYS, os.path.basename(source)))
	for cite_id in CITES:
		cite = index.get(cite_id)
		if not cite:
			erreurs.append("%s introuvable dans le dump" % cite_id)
			continue
		if cite.get("lieu_parent") not in (None, PAYS):
			erreurs.append("%s a déjà un autre parent (%s) — arbitrage à faire à la main"
						   % (cite_id, cite.get("lieu_parent")))
			continue
		emettre(dict(cite, lieu_parent=PAYS))

	# --- 2. Les matières feuilles ------------------------------------------------------
	for (slug, nom, icon, sous_cat, poids, vmin, vmax, desc) in MATIERES:
		item_id = "item:" + slug
		if item_id in index:
			erreurs.append("%s : collision d'_id avec un doc du dump" % item_id)
		emettre({
			"_id": item_id, "type": "item", "nom": nom, "description": desc, "icon": icon,
			"rarete": "commun", "categorie": "composant", "sous_categorie": sous_cat,
			"slots": [], "tags": [], "poids": poids,
			"valeur": [{"cu": vmin}, {"cu": vmax}],
		})

	# --- 3. Les plats et leurs recettes portées ----------------------------------------
	for (slug, nom, icon, rarete, poids, categorie, portee, effets, desc,
		 matieres, quantite) in PLATS:
		item_id = "item:" + slug
		recette_id = "recette:specialite_%s" % slug.lower()
		for doc_id in (item_id, recette_id):
			if doc_id in index:
				erreurs.append("%s : collision d'_id avec un doc du dump" % doc_id)
		emettre({
			"_id": item_id, "type": "item", "nom": nom, "description": desc, "icon": icon,
			"rarete": rarete, "categorie": "consommable", "sous_categorie": categorie,
			"slots": [], "tags": [], "poids": poids, "effets": effets,
		})
		emettre({
			"_id": recette_id, "type": "recette",
			"lieu_categorie": categorie,
			"lieu_portee": portee,
			"objet_final": slug,
			"quantite_produite": quantite,
			"matieres_premieres": [{"item": cle, "quantite": q} if cle.startswith("item:")
								   else {"sous_categorie": cle, "quantite": q}
								   for (cle, q) in matieres],
		})

	marche.reset_prix_cache()   # les index doivent voir les recettes qu'on vient d'émettre

	# --- 4. Garde-fous -----------------------------------------------------------------
	lieux = [d for d in docs if isinstance(d, dict) and d.get("type") == "lieu"]
	rapport = []
	for (slug, nom, _icon, _rarete, _poids, categorie, portee, _effets, _desc,
		 matieres, _quantite) in PLATS:
		recette_id = "recette:specialite_%s" % slug.lower()

		# (a) La portée doit désigner un lieu qui existe.
		if portee not in index or index[portee].get("type") != "lieu":
			erreurs.append("%s : `lieu_portee` %s n'est pas un lieu du dump" % (recette_id, portee))
			continue

		# (b) Au moins une boutique du métier doit se trouver SOUS cette portée, sinon la
		# recette est morte-née — personne ne peut la cuire, et rien ne le signalerait.
		ateliers = [L for L in lieux
					if categorie in marche.categories_incluses(L.get("categorie") or "")
					and portee in marche.portees_lieu(L)]
		if not ateliers:
			erreurs.append("%s : aucune boutique « %s » sous %s — recette morte-née"
						   % (recette_id, categorie, portee))
			continue

		# (c) La recette doit effectivement être servie à ces ateliers, et à eux seuls.
		servie = [L["_id"] for L in lieux
				  if recette_id in {r.get("_id") for r in marche.recettes_lieu(L)}]
		attendu = sorted(L["_id"] for L in ateliers)
		if sorted(servie) != attendu:
			erreurs.append("%s : servie à %s, attendu %s" % (recette_id, sorted(servie), attendu))
			continue

		# (d) L'objet final doit résoudre vers l'item produit (sinon ligne de rayon INVISIBLE).
		if marche.objet_final_item_id(slug) != "item:" + slug:
			erreurs.append("%s : objet_final « %s » ne résout pas vers item:%s"
						   % (recette_id, slug, slug))

		manquantes = sorted({c for (c, _q) in matieres} - _atteignables(marche, ateliers[0]))
		rapport.append((nom, categorie, portee, len(ateliers), manquantes))

	if erreurs:
		print("ABANDON — %d problème(s), aucun fichier écrit :" % len(erreurs))
		for e in erreurs:
			print("   ✗ %s" % e)
		return 1

	# --- 5. Écriture --------------------------------------------------------------------
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")

	print("Dump lu       : %s" % os.path.basename(source))
	print("Docs écrits   : %d (%d cités rattachées, %d matières, %d plats, %d recettes portées)"
		  % (len(sortie), len(CITES), len(MATIERES), len(PLATS), len(PLATS)))
	print()
	print("%-24s %-13s %-16s %-9s %s" % ("plat", "métier", "portée", "ateliers", "intrants à ravitailler"))
	print("-" * 108)
	for nom, categorie, portee, nb, manquantes in rapport:
		print("%-24s %-13s %-16s %-9d %s"
			  % (nom, categorie, portee.replace("lieu:", ""), nb,
				 ", ".join(m.replace("item:", "") for m in manquantes) or "— autonome"))
	print()
	print("→ %s" % SORTIE)
	return 0


if __name__ == "__main__":
	sys.exit(main())

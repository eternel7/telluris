#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Armes de [WOIN] *Archaic Equipment* absentes de Telluris — docs `item:*` neufs + leurs recettes.

Entrée : `jsons/armes_manquantes_woin.json` (liste de travail : 36 noms + un type, rien d'autre).
Source des noms : enworld.org, « Do you know your glaive-guisarme from your bohemian
earspoon » — armes à poudre exclues. Les statistiques ci-dessous sont **de l'équilibrage
maison**, calées sur les armes déjà en base de la même famille (aucun chiffre du livre).

Écrit `jsons/armes_woin_a_importer.json` : 32 armes + 32 recettes.

Volontairement ÉCARTÉ (déjà en base sous un autre nom — décision déjà prise par
`dev/gen_armes_armures_add2e.py`, qui l'écrivait en tête de son en-tête) :
	Hache d'armes = Hache_de_guerre · Spetum = Corsèque · Nunchaku = Fleau_asiatique
	Bō = Baton_de_combat
Ces quatre noms sont dans `ALIAS` ; le script vérifie que la cible existe toujours dans le dump.

Règles reprises de `dev/gen_armes_armures_add2e.py` :

1. **Table EXHAUSTIVE** : tout nom de la liste de travail est soit dans `PIECES`, soit dans
   `ALIAS` ; l'inverse (un nom de `PIECES` hors liste) est aussi refusé. Une liste qui bouge
   fait échouer le script plutôt que d'être ignorée.
2. **Chaque matière doit pouvoir ARRIVER à l'atelier** : feuille globale (auto-appro) OU
   produite par une recette de la MÊME catégorie de lieu (`manche` / `hampe` à l'armurerie).
   ⚠️ Ni `cuir` ni `tendons` (fausses feuilles : elles gèleraient la recette en silence).
3. **Aucune collision** : un `_id` pris par un doc DIFFÉRENT, ou un `nom` déjà porté par un
   autre `_id`, fait ÉCHOUER tout le lot (l'import est un PUT complet). Un doc IDENTIQUE à
   celui du dump est sauté : relancer après l'import ne produit rien (idempotent).
4. Tag `tranchant` seulement pour un vrai fil (cf. `dev/gen_armes_tranchantes.py`) ; tag
   `hast` pour les armes d'hast (le Jō, simple bâton à hampe, reste `cac` comme Baton_de_combat).
5. `objet_final` == l'`_id` sans le préfixe `item:` (`marche.objet_final_item_id`).

	python dev/gen_armes_woin.py [--dump jsons/telluris-dump-….json] [--sortie fichier.json]
"""
import argparse
import glob
import json
import os
import sys
import unicodedata

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTE = os.path.join(RACINE, "jsons", "armes_manquantes_woin.json")
SORTIE = os.path.join(RACINE, "jsons", "armes_woin_a_importer.json")

UNE = ["main_droite"]
AMB = ["main_droite", "main_gauche"]   # ambidextre / deux mains


def arme(slug, nom, icon, rarete, poids, slots, tags, portee, des, matieres, desc,
		 deg=None, r=None, deux_mains=False, **bonus):
	"""Une arme d'armurerie : `des` = dé de dégâts (bonus_degats_dice), `deg` = bonus_degats."""
	item = {
		"_id": "item:" + slug, "type": "item", "nom": nom, "description": desc,
		"icon": icon, "rarete": rarete, "categorie": "arme", "sous_categorie": "",
		"slots": slots, "poids": poids, "tags": tags, "portee": portee,
	}
	if r:
		item["restriction"] = r
	if deg:
		item["bonus_degats"] = deg
	item["bonus_degats_dice"] = des
	for cle in ("cc", "cd", "initiative", "pa", "malus_depl"):
		if bonus.get(cle):
			item["bonus_" + cle] = bonus[cle]
	if bonus.get("caracs"):
		item["bonus"] = bonus["caracs"]
	if deux_mains:
		item["deux_mains"] = True
	return item, "armurerie", matieres


# nom de la liste de travail → _id de l'item qui le couvre déjà
ALIAS = {
	"Hache d'armes": "item:Hache_de_guerre",
	"Spetum": "item:Corseque",
	"Nunchaku": "item:Fleau_asiatique",
	"Bō": "item:Baton_de_combat",
}

PIECES = [
	# ── Épées ───────────────────────────────────────────────────────────────────────
	arme("Flamberge", "Flamberge", "🗡️", "peu_commun", 3.8, AMB, ["cac", "tranchant"], 1, 10,
		 [("acier", 3), ("fer", 1), ("manche", 1), ("peaux", 1)],
		 "Grande épée à deux mains dont la lame ondule en flammes : elle mord plus profond qu'une lame droite.",
		 deg=5, cc=2, malus_depl=-2, r={"F": 17}, deux_mains=True),
	arme("Epee_double", "Épée double", "⚔️", "peu_commun", 3.0, AMB, ["cac", "tranchant"], 1, 8,
		 [("acier", 2), ("fer", 2), ("manche", 1)],
		 "Une poignée centrale, une lame à chaque bout : on frappe des deux côtés sans changer de prise.",
		 deg=3, cc=3, malus_depl=-1, r={"F": 13, "Ag": 14}, deux_mains=True),
	arme("Machette", "Machette", "🔪", "commun", 0.9, AMB, ["cac", "tranchant"], 1, 6,
		 [("fer", 2), ("manche", 1)],
		 "Lame large et lourde du bout : elle ouvre un sentier dans les broussailles, et un homme au besoin.",
		 deg=2, r={"F": 10}),
	arme("Epee_de_cour", "Épée de cour", "🤺", "peu_commun", 0.9, AMB, ["cac"], 1, 6,
		 [("acier", 1), ("manche", 1)],
		 "Lame fine d'apparat sans tranchant utile : elle se porte au côté et se tire d'un geste vif.",
		 deg=1, cc=4, initiative=2, r={"Ag": 13}),

	# ── Armes contondantes ──────────────────────────────────────────────────────────
	arme("Matraque", "Matraque", "🏏", "commun", 0.5, AMB, ["cac"], 1, 4,
		 [("manche", 1), ("peaux", 1)],
		 "Court bâton gainé de cuir, l'arme des guets qui veulent assommer sans tuer.",
		 deg=1, cc=2),
	arme("Assommoir", "Assommoir", "🏏", "commun", 1.0, AMB, ["cac"], 1, 6,
		 [("manche", 1), ("plomb", 1)],
		 "Manche court coiffé d'une masse de plomb : le coup ne laisse pas de trace, seulement un homme à terre.",
		 deg=2, cc=1, r={"F": 10}),

	# ── Divers ──────────────────────────────────────────────────────────────────────
	arme("Pieu", "Pieu", "📍", "commun", 1.5, AMB, ["cac"], 1, 6,
		 [("manche", 2)],
		 "Un long bout de bois taillé en pointe et durci au feu. Sommaire, mais il perce.",
		 deg=1, r={"F": 10}),
	arme("Faux", "Faux", "🌾", "commun", 2.5, AMB, ["cac", "hast", "tranchant"], 2, 6,
		 [("fer", 2), ("hampe", 1)],
		 "Grande lame courbe sur un long manche : un outil de moisson qu'une main désespérée sait retourner.",
		 deg=3, malus_depl=-1, r={"F": 12}, deux_mains=True),

	# ── Armes d'hast ────────────────────────────────────────────────────────────────
	arme("Brandistock", "Brandistock", "🔱", "peu_commun", 3.0, AMB, ["cac", "hast"], 2, 8,
		 [("fer", 2), ("acier", 1), ("hampe", 1)],
		 "Bâton creux d'où jaillissent trois lames sous l'effet d'un ressort ; on le range court, on l'emploie long.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Epieu_de_chasse", "Épieu de chasse", "🔱", "commun", 2.2, AMB, ["cac", "hast"], 2, 6,
		 [("fer", 1), ("hampe", 1)],
		 "Fer large muni d'une traverse qui arrête le sanglier avant qu'il ne remonte la hampe.",
		 deg=3, cc=1, r={"F": 11}, deux_mains=True),
	arme("Hache_dague", "Hache-dague", "🪓", "commun", 2.8, AMB, ["cac", "hast", "tranchant"], 2, 8,
		 [("fer", 2), ("hampe", 1)],
		 "Lame de dague ouverte d'un croc perpendiculaire, montée sur hampe : elle pique, tranche et accroche.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Guan_dao", "Guan dao", "🌙", "peu_commun", 4.0, AMB, ["cac", "hast", "tranchant"], 2, 8,
		 [("acier", 1), ("fer", 2), ("hampe", 1)],
		 "Large lame courbe d'un seul tranchant sur une hampe lestée : un coup de taille qui fend le rang.",
		 deg=4, cc=1, malus_depl=-1, r={"F": 15}, deux_mains=True),
	arme("Oreille_de_boheme", "Oreille de Bohême", "🔱", "commun", 3.0, AMB, ["cac", "hast"], 2, 6,
		 [("fer", 2), ("hampe", 1)],
		 "Fer de lance flanqué de deux ailerons recourbés, comme une cuiller à oreille : il blesse en entrant.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 12}, deux_mains=True),
	arme("Svardstav", "Svärdstav", "⚔️", "peu_commun", 2.8, AMB, ["cac", "hast", "tranchant"], 2, 8,
		 [("acier", 1), ("fer", 1), ("hampe", 1)],
		 "« Bâton-épée » des soldats suédois : une longue lame d'épée plantée au bout d'une hampe.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Nagamaki", "Nagamaki", "🌸", "peu_commun", 2.4, AMB, ["cac", "hast", "tranchant"], 2, 8,
		 [("acier", 2), ("hampe", 1), ("peaux", 1)],
		 "Lame de sabre montée sur une fusée presque aussi longue qu'elle : le fantassin garde la portée et la vivacité.",
		 deg=3, cc=4, r={"F": 12, "Ag": 14}, deux_mains=True),
	arme("Sovnya", "Sovnya", "🌙", "commun", 3.0, AMB, ["cac", "hast", "tranchant"], 2, 8,
		 [("fer", 2), ("hampe", 1)],
		 "Lame courbe à un seul tranchant sur une hampe : l'arme des fantassins des steppes.",
		 deg=3, cc=2, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Faux_de_guerre", "Faux de guerre", "🌾", "commun", 2.8, AMB, ["cac", "hast", "tranchant"], 2, 8,
		 [("fer", 2), ("hampe", 1)],
		 "Lame de faux redressée dans l'axe de la hampe et renforcée : l'arme des paysans levés en masse.",
		 deg=3, cc=1, malus_depl=-1, r={"F": 13}, deux_mains=True),

	# ── Armes d'Orient ──────────────────────────────────────────────────────────────
	arme("Hanbo", "Hanbō", "🥢", "commun", 0.6, AMB, ["cac"], 1, 3,
		 [("manche", 1)],
		 "Bâton court d'un peu moins d'un mètre, assez bref pour se manier en espace clos.",
		 deg=1, cc=3, initiative=1, r={"Ag": 11}),
	arme("Jo", "Jō", "🥢", "commun", 1.2, AMB, ["cac"], 2, 4,
		 [("hampe", 1)],
		 "Bâton droit d'un mètre vingt, tenu à deux mains : on frappe du bout, on pare du milieu.",
		 deg=1, cc=3, r={"Ag": 12}, deux_mains=True),
	arme("Niuweidao", "Niuweidao", "🌙", "commun", 2.2, UNE, ["cac", "tranchant"], 1, 8,
		 [("acier", 1), ("fer", 2), ("manche", 1)],
		 "« Sabre en queue de bœuf » : lame large qui s'évase vers la pointe, faite pour trancher à cheval.",
		 deg=4, cc=1, malus_depl=-1, r={"F": 14}),
	arme("Sibat", "Sibat", "🔱", "commun", 1.6, AMB, ["cac", "hast"], 2, 6,
		 [("fer", 1), ("hampe", 1)],
		 "Lance légère des îles, d'une seule pièce : elle se manie d'une main comme à deux.",
		 deg=2, cc=2, r={"F": 10, "Ag": 11}, deux_mains=True),
	arme("Hu_cha", "Hu cha", "🔱", "peu_commun", 2.8, AMB, ["cac", "hast"], 2, 8,
		 [("fer", 2), ("hampe", 1)],
		 "« Fourche du tigre » : trois pointes sur une hampe, pour arrêter la charge d'une bête ou d'un homme.",
		 deg=3, cc=3, malus_depl=-1, r={"F": 13}, deux_mains=True),
	arme("Tekko_kagi", "Tekko-kagi", "🐾", "peu_commun", 0.5, AMB, ["cac", "tranchant"], 1, 4,
		 [("fer", 1), ("peaux", 1)],
		 "Quatre griffes de fer au dos d'une sangle de cuir : on lacère à mains nues, ou presque.",
		 deg=1, cc=4, r={"Ag": 12}),
	arme("Kyoketsu_shoge", "Kyoketsu-shoge", "⛓️", "peu_commun", 1.0, AMB, ["cac", "tranchant"], 2, 4,
		 [("fer", 1), ("peaux", 2)],
		 "Lame à crochet reliée à une longue corde terminée par un anneau : on entrave, on accroche, on tire.",
		 deg=1, cc=3, r={"Ag": 15}),
	arme("Urumi", "Urumi", "〰️", "peu_commun", 1.2, UNE, ["cac", "tranchant"], 2, 6,
		 [("acier", 2), ("manche", 1)],
		 "Plusieurs lames d'acier souple fixées à une même garde ; une fois lancée, elle fouette tout autour.",
		 deg=3, cc=3, r={"Ag": 16}),
	arme("Epee_papillon", "Épée papillon", "🦋", "peu_commun", 1.0, AMB, ["cac", "tranchant"], 1, 6,
		 [("acier", 1), ("fer", 1), ("manche", 1)],
		 "Paire de courts sabres à garde ronde, portée dans le même fourreau : on les manie ensemble.",
		 deg=2, cc=4, initiative=2, r={"Ag": 13}),
	arme("Fouet_a_neuf_sections", "Fouet à neuf sections", "⛓️", "peu_commun", 1.6, AMB, ["cac"], 2, 6,
		 [("fer", 3)],
		 "Neuf tronçons de fer articulés, terminés d'une pointe : un fouet qui se déroule en chaîne rigide.",
		 deg=2, cc=3, r={"Ag": 15}),
	arme("Tonfa", "Tonfa", "🥢", "commun", 0.6, AMB, ["cac"], 1, 4,
		 [("manche", 2)],
		 "Bâton court à poignée latérale : on frappe en le faisant pivoter, on pare sur l'avant-bras.",
		 deg=1, cc=4, pa=1, r={"Ag": 12}),
	arme("Setsukon", "Setsukon", "⛓️", "peu_commun", 1.4, AMB, ["cac"], 2, 6,
		 [("manche", 2), ("fer", 1)],
		 "Trois bâtons de bois reliés par des chaînes : replié il se cache, déployé il atteint loin.",
		 deg=2, cc=4, r={"Ag": 15}, deux_mains=True),
	arme("Shang_gao", "Shang gao", "🔱", "peu_commun", 2.4, AMB, ["cac", "hast"], 2, 6,
		 [("fer", 2), ("hampe", 1)],
		 "Arme d'hast d'Orient à fer long, courte pour une lance et équilibrée pour la parade.",
		 deg=2, cc=3, r={"F": 11, "Ag": 12}, deux_mains=True),
	arme("Eventail_de_guerre", "Éventail de guerre", "🪭", "peu_commun", 0.5, AMB, ["cac"], 1, 3,
		 [("fer", 2)],
		 "Éventail dont les lames sont de fer : il passe pour un accessoire, pare une lame et frappe au visage.",
		 deg=1, cc=3, pa=2, r={"Ag": 12}),

	# ── Tir ─────────────────────────────────────────────────────────────────────────
	arme("Arbalete_a_repetition", "Arbalète à répétition", "🏹", "peu_commun", 3.0, UNE, ["tir"], 6, 4,
		 [("fer", 2), ("manche", 2), ("bronze", 1)],
		 "Arbalète surmontée d'un magasin de traits, armée d'un seul levier : peu de force, mais une volée serrée.",
		 deg=2, cd=4, r={"Ag": 14}, deux_mains=True),
]


def _norm(s):
	s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
	return " ".join(s.lower().replace("-", " ").replace("'", " ").split())


def _dump_recent():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json"))
				   + glob.glob(os.path.join(RACINE, "telluris-dump-*.json")),
				   key=os.path.basename)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json : impossible de contrôler les collisions.")
	return dumps[-1]


def _sans_rev(doc):
	return {k: v for k, v in doc.items() if k != "_rev"}


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
	ap.add_argument("--dump", help="dump à relire (défaut : le plus récent de jsons/)")
	ap.add_argument("--sortie", default=SORTIE, help="fichier écrit (défaut : %(default)s)")
	args = ap.parse_args(argv)

	src = args.dump or _dump_recent()
	with open(src, encoding="utf-8") as fh:
		base = json.load(fh)["docs"]
	par_id = {d["_id"]: d for d in base}
	recettes = [d for d in base if d.get("type") == "recette"]
	erreurs = []

	# ── 1. Table exhaustive vs liste de travail ─────────────────────────────────────
	with open(LISTE, encoding="utf-8-sig") as fh:
		listees = [a["nom"] for a in json.load(fh)["armes"]]
	couverts = {_norm(it["nom"]) for (it, _l, _m) in PIECES} | {_norm(n) for n in ALIAS}
	for nom in listees:
		if _norm(nom) not in couverts:
			erreurs.append("%r figure dans la liste de travail mais ni dans PIECES ni dans ALIAS" % nom)
	attendus = {_norm(n) for n in listees}
	for (it, _l, _m) in PIECES:
		if _norm(it["nom"]) not in attendus:
			erreurs.append("%s : %r absent de la liste de travail" % (it["_id"], it["nom"]))
	for nom, cible in ALIAS.items():
		if cible not in par_id:
			erreurs.append("ALIAS %r → %s : la cible n'existe plus dans le dump" % (nom, cible))

	# Feuilles globales = intrants qu'aucune recette ne produit (marche._get_marche_map).
	produits, produits_par_cat = set(), {}
	for rc in recettes:
		o = rc.get("objet_final") or ""
		cles = {o}
		it = par_id.get("item:" + o)
		if it and it.get("sous_categorie"):
			cles.add(it["sous_categorie"])
		produits |= cles
		produits_par_cat.setdefault(rc.get("lieu_categorie"), set()).update(cles)

	noms_base = {_norm(d.get("nom")): d["_id"] for d in base
				 if d["_id"].startswith("item:") and d.get("nom")}

	# ── 2. Construction et contrôles ────────────────────────────────────────────────
	neufs, deja = [], 0
	for (item, lieu, matieres) in PIECES:
		slug = item["_id"][len("item:"):]
		rid = "recette:woin_%s" % slug.lower()
		recette = {
			"_id": rid,
			"type": "recette",
			"lieu_categorie": lieu,
			"objet_final": slug,              # ⚠️ == `_id` sans le préfixe `item:`
			"quantite_produite": 1,
			"matieres_premieres": [{"sous_categorie": c, "quantite": q} for (c, q) in matieres],
		}
		for (cle, _q) in matieres:
			if "item:" + cle not in par_id:
				erreurs.append("%s : item:%s absent (matière valorisée à vide)" % (slug, cle))
			if cle in produits and cle not in produits_par_cat.get(lieu, set()):
				erreurs.append("%s @%s : %r est une FAUSSE FEUILLE (produite ailleurs)"
							   % (slug, lieu, cle))
		for doc in (item, recette):
			en_base = par_id.get(doc["_id"])
			if en_base is None:
				neufs.append(doc)
			elif _sans_rev(en_base) == doc:
				deja += 1
			else:
				erreurs.append("%s : _id déjà en base avec un contenu DIFFÉRENT (PUT complet = écrasement)"
							   % doc["_id"])
		autre = noms_base.get(_norm(item["nom"]))
		if autre and autre != item["_id"]:
			erreurs.append("%s : nom %r déjà porté par %s" % (item["_id"], item["nom"], autre))

	ids = [d["_id"] for (it, _l, _m) in PIECES for d in (it,)]
	doublons = {i for i in ids if ids.count(i) > 1}
	if doublons:
		erreurs.append("_id en double dans PIECES : %s" % sorted(doublons))

	if erreurs:
		print("Génération refusée (dump %s) :" % os.path.basename(src), file=sys.stderr)
		for e in erreurs:
			print("  x " + e, file=sys.stderr)
		return 1

	for nom, cible in ALIAS.items():
		print("   écarté : %-14s déjà couvert par %s" % (nom, cible))
	if not neufs:
		print("Rien à créer (%d docs déjà identiques dans %s) : aucun fichier écrit."
			  % (deja, os.path.basename(src)))
		return 0

	with open(args.sortie, "w", encoding="utf-8") as fh:
		json.dump(neufs, fh, ensure_ascii=False, indent=2)

	nb_items = sum(1 for d in neufs if d["type"] == "item")
	print("→ %s  (contrôlé contre %s)" % (os.path.relpath(args.sortie, RACINE), os.path.basename(src)))
	print("   %d armes + %d recettes, %d docs déjà en base (sautés)"
		  % (nb_items, len(neufs) - nb_items, deja))
	return 0


if __name__ == "__main__":
	sys.exit(main())

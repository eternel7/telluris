"""Génère l'import qui porte Auxerre à DEUX magasins de chaque type possible.

Lit le dump committé (source unique, cf. CLAUDE.md §11 « Import de contenu ») et
n'écrit que ce qui manque : un doc `lieu:*` + son doc `connection` par magasin à
créer. Un type déjà servi deux fois n'est pas touché — relancer le script sur un
dump plus récent est donc idempotent.

    python dev/gen_magasins_auxerre.py [chemin/vers/telluris-dump-*.json]

Sorties :
    jsons/magasins_auxerre_a_importer.json        (à coller dans la carte d'import de /admin)
    jsons/magasins_auxerre_images_manquantes.txt  (les images à dessiner)

⚠️ « Type de magasin possible » = une catégorie qui a un tenancier générique
`pnj:marchand_*` (cf. dev/gen_marchands.py) — c'est-à-dire toute catégorie citée
par une recette (`recette.lieu_categorie`), plus l'étable. Une catégorie sans
tenancier n'aurait personne derrière le comptoir.

⚠️ POSITION : chaque nouveau magasin est posé sur une case de la grille d'Auxerre
qui porte DÉJÀ la porte d'un magasin, en excluant celles d'un magasin de MÊME
type (deux boutiques du même métier ne partagent pas leur seuil). Plusieurs lieux
sur une même case est un cas déjà présent en base (les deux temples de Malakor).
"""

import json
import os
import re
import sys
import unicodedata

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
DOSSIER_IMAGES = os.path.join(RACINE, "templates", "resources", "towns")

CITE = "lieu:auxerre"
PAR_TYPE = 2  # ce que la ville doit compter de magasins de chaque type

# --- Catalogue des enseignes à ouvrir -------------------------------------
# Une entrée par magasin POSSIBLE, dans l'ordre où on les proposera. Le script
# n'en retient que ce qu'il faut pour atteindre PAR_TYPE ; les surnuméraires
# restent en réserve pour un futur passage (ou une autre cité).
#
# `image` : nom de fichier VOULU. S'il n'existe pas dans templates/resources/towns,
# il est écrit quand même (le lieu est jouable, seule l'illustration manque) et
# listé dans le .txt — cf. la demande explicite d'un placeholder `<type>_europeXX.png`.
ENSEIGNES = [
	# categorie,                  label,                              image
	("apothicairerie",            "L'Herbier du Guet",                "apothicairerie_europe01.png"),
	("armurerie",                 "La Forge du Rempart",              "armurerie_europe01.png"),
	("atelier_d_artisan",         "L'Etabli du Faubourg",             "atelier_d_artisan_europe01.png"),
	("atelier_d_artisan",         "Le Copeau d'Autessiodurum",        "atelier_d_artisan_europe03.png"),
	("atelier_de_cirier",         "La Meche de Sainte-Colombe",       "atelier_de_cirier_europe01.png"),
	("atelier_de_cirier",         "Le Cierge d'Auxerre",              "atelier_de_cirier_europe02.png"),
	("atelier_de_l_empenneur",    "La Plume et l'Encoche",            "atelier_de_l_empenneur_europe01.png"),
	("atelier_de_l_empenneur",    "L'Empennage du Rempart",           "atelier_de_l_empenneur_europe02.png"),
	("bijouterie",                "L'Ecrin de l'Yonne",               "bijouterie_europe02.png"),
	("boucherie",                 "Le Billot de Saint-Germain",       "boucherie_europe01.png"),
	("bourrellerie",              "Le Harnais de l'Yonne",            "bourrellerie_europe01.png"),
	("bourrellerie",              "La Bricole et le Collier",         "bourrellerie_europe02.png"),
	("boyauderie",                "La Corde de Boyau",                "boyauderie_europe01.png"),
	("boyauderie",                "Le Fil du Tripier",                "boyauderie_europe02.png"),
	("brosserie",                 "La Soie et le Crin",               "brosserie_europe01.png"),
	("brosserie",                 "Le Balai de Saint-Germain",        "brosserie_europe02.png"),
	("corderie",                  "Le Chanvre Tresse",                "corderie_europe01.png"),
	("corderie",                  "Les Cables de l'Yonne",            "corderie_europe02.png"),
	("cordonnerie",              "Le Soulier de Saint-Crepin",        "cordonnerie_europe01.png"),
	("cordonnerie",              "La Semelle du Pelerin",             "cordonnerie_europe02.png"),
	("cuisine",                   "La Marmite du Guet",               "epicerie_europe01.png"),
	("cuisine",                   "Le Pot-au-Feu des Halles",         "epicerie_europe02.png"),
	("etable",                    "Le Pre aux Betes",                 "etable_europe04.png"),
	("fletcher",                  "L'Arc et la Corde",                "archerie_europe01.png"),
	("fumoir",                    "Le Haloir des Remparts",           "fumoir_europe02.png"),
	("fumoir",                    "La Cheminee Noire",                "fumoir_europe03.png"),
	("jardinier",                 "Le Clos des Simples",              "jardinier_europe01.png"),
	("jardinier",                 "Le Jardin de Saint-Germain",       "jardinier_europe02.png"),
	("laboratoire_d_alchimie",    "Le Creuset d'Autessiodurum",       "cabinet_alchimie_europe03.png"),
	("lutherie",                  "La Vielle et le Luth",             "lutherie_europe01.png"),
	("lutherie",                  "Les Cordes d'Autessiodurum",       "lutherie_europe02.png"),
	("maroquinerie",              "La Gibeciere d'Auxerre",           "maroquinerie_europe01.png"),
	("maroquinerie",              "Le Cuir Repousse",                 "maroquinerie_europe02.png"),
	("necromancie",               "Le Suaire de Cendres",             "necromancie_europe01.png"),
	("necromancie",               "L'Ossuaire Muet",                  "necromancie_europe02.png"),
	("plumasserie",               "Le Duvet d'Oie",                   "plumasserie_europe01.png"),
	("plumasserie",               "Le Panache de l'Yonne",            "plumasserie_europe02.png"),
	("salaison",                  "Le Saloir du Pont",                "salaison_europe01.png"),
	("salaison",                  "La Bourrique en Saumure",          "salaison_europe03.png"),
	("savonnerie",                "La Cuve de Cendre",                "savonnerie_europe01.png"),
	("savonnerie",                "Le Savon de Saint-Etienne",        "savonnerie_europe02.png"),
	("scriptorium",               "La Lettrine d'Or",                 "scriptorium_europe02.png"),
	("tabletterie",               "L'Ivoire et le Buis",              "tabletterie_europe02.png"),
	("tabletterie",               "Le Peigne de Corne",               "tabletterie_europe03.png"),
	("tannerie",                  "Le Tan de l'Yonne",                "tannerie_europe01.png"),
	("tannerie",                  "La Fosse aux Peaux",               "tannerie_europe02.png"),
	("taxidermie",                "Le Trophee de Chasse",             "taxidermie_europe01.png"),
	("taxidermie",                "Les Yeux de Verre",                "taxidermie_europe02.png"),
	("tissage",                   "La Navette d'Auxerre",             "tissage_europe01.png"),
	("tissage",                   "Le Metier de Haute Lisse",         "tissage_europe02.png"),
]

# Les labels du catalogue sont écrits SANS accent pour que ce fichier reste lisible
# quel que soit l'encodage de la console ; on les réaccentue à l'écriture du doc.
ACCENTS = {
	"L'Etabli du Faubourg": "L'Établi du Faubourg",
	"La Meche de Sainte-Colombe": "La Mèche de Sainte-Colombe",
	"L'Ecrin de l'Yonne": "L'Écrin de l'Yonne",
	"Le Chanvre Tresse": "Le Chanvre Tressé",
	"Les Cables de l'Yonne": "Les Câbles de l'Yonne",
	"Le Soulier de Saint-Crepin": "Le Soulier de Saint-Crépin",
	"La Semelle du Pelerin": "La Semelle du Pèlerin",
	"Le Pre aux Betes": "Le Pré aux Bêtes",
	"Le Haloir des Remparts": "Le Hâloir des Remparts",
	"La Cheminee Noire": "La Cheminée Noire",
	"La Gibeciere d'Auxerre": "La Gibecière d'Auxerre",
	"Le Cuir Repousse": "Le Cuir Repoussé",
	"Le Savon de Saint-Etienne": "Le Savon de Saint-Étienne",
	"Le Trophee de Chasse": "Le Trophée de Chasse",
	"Le Metier de Haute Lisse": "Le Métier de Haute Lisse",
}

DIACRITIQUES = re.compile(r"[̀-ͯ]")


def slug_lieu(label):
	"""« Le Chaudron des Brumes » → « le_chaudron_des_brumes ».

	Réplique exacte de `_slugLieu` (templates/admin_map_editor.html) : les ids
	créés à la main et ceux créés par l'éditeur doivent suivre la même règle."""
	s = unicodedata.normalize("NFD", str(label or ""))
	s = DIACRITIQUES.sub("", s).lower()
	s = re.sub(r"[^a-z0-9]+", "_", s)
	return re.sub(r"_+", "_", s).strip("_")


def charger_dump(chemin=None):
	if chemin:
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez le chemin en argument.")
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def types_possibles(docs):
	"""Catégories ayant un tenancier générique `pnj:marchand_<categorie>`."""
	return {
		d["_id"][len("pnj:marchand_"):]
		for d in docs
		if d.get("type") == "pnj" and str(d.get("_id", "")).startswith("pnj:marchand_")
	}


def main():
	dump = charger_dump(sys.argv[1] if len(sys.argv) > 1 else None)
	docs = dump["docs"]
	par_id = {d["_id"]: d for d in docs}

	possibles = types_possibles(docs)

	# --- Ce qu'Auxerre possède déjà -------------------------------------
	# Une catégorie n'est « servie » que par un lieu enfant de la cité.
	deja = {}
	for d in docs:
		if d.get("type") == "lieu" and d.get("lieu_parent") == CITE:
			cat = d.get("categorie")
			if cat in possibles:
				deja.setdefault(cat, []).append(d["_id"])

	# --- Les cases de la grille d'Auxerre qui portent déjà une boutique --
	# `pool` garde l'ordre de lecture (déterminisme) ; `cats_de_case` dit quels
	# métiers y ont pignon sur rue, pour ne jamais y reposer le même.
	pool = []
	cats_de_case = {}
	numeros = {}  # categorie -> plus grand NN de link:<cat>NN_to_auxerre
	for c in docs:
		if c.get("type") != "connection":
			continue
		nodes = c.get("nodes") or []
		if len(nodes) != 2:
			continue
		cote_ville = next((n for n in nodes if n.get("lieu") == CITE), None)
		cote_lieu = next((n for n in nodes if n.get("lieu") != CITE), None)
		if not cote_ville or not cote_lieu:
			continue
		cible = par_id.get(cote_lieu.get("lieu")) or {}
		cat = cible.get("categorie")
		if cat not in possibles:
			continue
		m = re.match(r"^link:" + re.escape(cat) + r"(\d+)_to_auxerre$", c.get("_id", ""))
		if m:
			numeros[cat] = max(numeros.get(cat, 0), int(m.group(1)))
		case = tuple(cote_ville.get("pos") or [0, 0])
		if case not in cats_de_case:
			pool.append(case)
			cats_de_case[case] = set()
		cats_de_case[case].add(cat)

	if not pool:
		raise SystemExit("Aucune porte de magasin trouvée dans la grille d'Auxerre.")

	images_presentes = set(os.listdir(DOSSIER_IMAGES)) if os.path.isdir(DOSSIER_IMAGES) else set()
	ids_pris = {d["_id"] for d in docs}

	sortie = []
	manquantes = []       # (image, categorie, label)
	rapport = []          # lignes du récapitulatif console
	curseur = 0           # tourne sur `pool` pour étaler les nouvelles portes

	compte = {cat: len(deja.get(cat, [])) for cat in possibles}

	for cat, label_brut, image in ENSEIGNES:
		if cat not in possibles:
			continue
		if compte.get(cat, 0) >= PAR_TYPE:
			continue

		label = ACCENTS.get(label_brut, label_brut)
		lieu_id = "lieu:" + slug_lieu(label)
		if lieu_id in ids_pris:
			raise SystemExit(f"Collision d'id : {lieu_id} existe déjà — changez le label.")
		ids_pris.add(lieu_id)

		# Case libre pour CE métier : on avance dans le pool jusqu'à en trouver une.
		case = None
		for pas in range(len(pool)):
			candidate = pool[(curseur + pas) % len(pool)]
			if cat not in cats_de_case[candidate]:
				case = candidate
				curseur = (curseur + pas + 1) % len(pool)
				break
		if case is None:
			raise SystemExit(f"Aucune case sans magasin de type « {cat} » — pool trop étroit.")
		cats_de_case[case].add(cat)

		numeros[cat] = numeros.get(cat, 0) + 1
		link_id = "link:%s%02d_to_auxerre" % (cat, numeros[cat])

		sortie.append({
			"_id": lieu_id,
			"type": "lieu",
			"label": label,
			"image": image,
			"categorie": cat,
			# `nom`/`portrait` volontairement absents : pnj_payload retombe alors
			# sur le doc `pnj:marchand_<cat>` (cf. CLAUDE.md, mode « Lieux »).
			"pnj": [{"character": "pnj:marchand_" + cat}],
			"lieu_parent": CITE,
			# Le tick atelier approvisionne et produit tout seul à la 1re visite.
			"stock_matieres": {},
			"stock_vente": [],
		})
		sortie.append({
			"_id": link_id,
			"type": "connection",
			"nodes": [
				{"lieu": CITE, "pos": [case[0], case[1]]},
				{"lieu": lieu_id, "pos": [0, 0]},
			],
			"metadata": {"type": cat, "status": "ouvert"},
		})

		if image not in images_presentes:
			manquantes.append((image, cat, label))
		compte[cat] = compte.get(cat, 0) + 1
		rapport.append("  %-24s %-34s [%2d,%2d]  %s%s" % (
			cat, label, case[0], case[1], image,
			"" if image in images_presentes else "   ← IMAGE MANQUANTE",
		))

	# --- Écriture --------------------------------------------------------
	chemin_json = os.path.join(DOSSIER_JSONS, "magasins_auxerre_a_importer.json")
	with open(chemin_json, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")

	chemin_txt = os.path.join(DOSSIER_JSONS, "magasins_auxerre_images_manquantes.txt")
	with open(chemin_txt, "w", encoding="utf-8") as f:
		f.write("Images de lieu à dessiner pour l'import magasins_auxerre_a_importer.json\n")
		f.write("Dossier cible : templates/resources/towns/\n")
		f.write("=" * 78 + "\n\n")
		if not manquantes:
			f.write("Aucune : toutes les images référencées existent déjà.\n")
		else:
			par_cat = {}
			for img, cat, label in manquantes:
				par_cat.setdefault(cat, []).append((img, label))
			for cat in sorted(par_cat):
				f.write("%s\n" % cat)
				for img, label in par_cat[cat]:
					f.write("\t%-40s  (%s)\n" % (img, label))
				f.write("\n")
			f.write("=" * 78 + "\n")
			f.write("Total : %d image(s) manquante(s) sur %d magasin(s) créé(s).\n"
					% (len(manquantes), len(sortie) // 2))
			f.write("\nEn attendant, le lieu est jouable : seule l'illustration est absente.\n")

	# --- Récapitulatif console ------------------------------------------
	# La console Windows est en cp1252 : sans cela, une flèche ou un accent fait
	# planter le script APRÈS avoir écrit les fichiers — panne trompeuse.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	print("Types de magasin possibles : %d" % len(possibles))
	non_servis = sorted(c for c in possibles if compte.get(c, 0) < PAR_TYPE)
	print("Magasins créés : %d (%d docs avec les connexions)" % (len(sortie) // 2, len(sortie)))
	print("Images manquantes : %d" % len(manquantes))
	print()
	for ligne in rapport:
		print(ligne)
	if non_servis:
		print()
		print("⚠ Toujours sous %d après import (pas assez d'enseignes au catalogue) : %s"
			  % (PAR_TYPE, ", ".join(non_servis)))
	print()
	print("→ %s" % chemin_json)
	print("→ %s" % chemin_txt)


if __name__ == "__main__":
	main()

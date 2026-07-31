"""Génère les fichiers d'import de la passe « armures » :

	jsons/armures_recettes_a_importer.json   — item:peaux + recettes de fabrication
	jsons/armures_bonus_pa_a_importer.json   — docs `item:*` complets, `bonus_pa` renseigné

Contexte (cf. l'analyse du dump) : sur 108 items `categorie:"armure"`, seuls 19 étaient
l'`objet_final` d'une recette, et les 11 recettes d'armurerie exigeaient toutes du `cuir` —
matière que la tannerie produit, donc **jamais une « feuille »**, donc **jamais
auto-approvisionnée**. Aucune armure ne pouvait sortir d'un atelier.

Deux leviers, tous les deux en DONNÉES :

1. **`item:peaux`** — nouvelle matière, consommée par les métiers du cuir et produite par
   AUCUNE recette : c'est donc une feuille au sens de `marche.appro_leaves_categorie`, et
   elle est auto-approvisionnée à chaque tick. Le `cuir` (tanné) reste le matériau noble,
   fourni par la tannerie et par le dépeçage du joueur — les deux grades coexistent, et le
   débouché du butin n'est pas dévalué.

   ⚠️ On n'a PAS écrit de recette `peaux → cuir` dans ces ateliers, bien que ce fût l'idée
   de départ. Deux effets de bord l'interdisent :
	 - `lieu_produit(armurerie, item:cuir)` deviendrait vrai → le cuir vendu par le joueur
	   partirait en `stock_vente` (bande de RACHAT, plafonnée au coût de revient) au lieu de
	   `stock_matieres` : le joueur serait payé MOINS pour son cuir qu'aujourd'hui ;
	 - un produit d'atelier n'est réutilisable comme matière qu'au-dessus de son `stock_cible`
	   (100 par défaut), là où une feuille atterrit directement dans `stock_matieres` et sert
	   au tick suivant.

2. **`bonus_pa`** — 92 des 108 armures n'en portaient aucun (la Cotte de mailles : 8 kg pour
   0 point d'armure). Barème `poids × facteur de matière`, calé sur les 16 valeurs déjà en
   base : il retombe exactement sur `Armure_plates_surcoat` (12 kg × 2.1 = 25) et sur
   `armure_de_cuir` (3 × 1.8 = 5). Les valeurs déjà posées ne sont JAMAIS écrasées.

Périmètre assumé : **aucune armure de tissu** (robes, capuches, chausses, pantalons,
chapeaux) ne reçoit de recette — il n'existe aucune matière textile dans le jeu (ni lin, ni
laine, ni toile, ni soie ; `tissage` ne produit que `feutre` et `rembourrage` à partir de
`poils`). Ces 32 pièces gardent leur `bonus_pa` calculé mais restent hors production, en
attente d'une filière textile dédiée.

Les recettes sont relues depuis le **dump** (source unique) : régénérer est idempotent.

	python dev/gen_armures.py
"""

import glob
import json
import os
import unicodedata

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE_RECETTES = os.path.join(DOSSIER_JSONS, "armures_recettes_a_importer.json")
SORTIE_BONUS_PA = os.path.join(DOSSIER_JSONS, "armures_bonus_pa_a_importer.json")


# ── La matière qui débloque toute la filière ────────────────────────────────────
# Feuille : aucune recette ne la produit → `appro_leaves_categorie` l'injecte dans le
# `stock_matieres` de tout métier dont une recette la consomme, à `APPRO_DEBIT_DEFAUT`/tick.
# ⚠️ `valeur` EXPLICITE : sans elle, une feuille est valorisée `poids × MULT_RARETE ×
# PRIX_DERIVE_BASE` = 2 cuivre, et toutes les armures de cuir s'effondreraient à un
# douzième du prix de `item:armure_de_cuir`. 20 cu la cale juste sous le `cuir` tanné
# (25 cu), qui reste le matériau supérieur.
ITEM_PEAUX = {
	"_id": "item:peaux",
	"type": "item",
	"nom": "Peaux brutes",
	"description": (
		"Lot de peaux achetées en gros aux éleveurs et aux chasseurs. Un atelier les "
		"apprête lui-même, sommairement : bon pour des sangles, des doublures et de la "
		"grosse pièce, jamais pour l'ouvrage fin du tanneur."
	),
	"icon": "🟤",
	"rarete": "commun",
	"categorie": "composant",
	"sous_categorie": "peaux",
	"slots": [],
	"tags": [],
	"poids": 1.0,
	"valeur": [{"cu": 20}],
}


# ── Barème d'armure ──────────────────────────────────────────────────────────────
# bonus_pa = round(poids × FACTEUR[classe]), planché à 1 dès que la matière protège
# vraiment (facteur ≥ 1.0). Calé sur les 16 valeurs déjà en base :
#   Armure_plates_surcoat 12.0 × 2.1 = 25.2 → 25   (valeur en base : 25)
#   armure_de_cuir         3.0 × 1.8 =  5.4 →  5   (valeur en base :  5)
#   Pavois                 6.0 × 2.3 = 13.8 → 14   (valeur en base : 14)
#   Bocle                  0.6 × 2.3 =  1.4 →  1 → planché… (valeur en base : 3, non écrasée)
FACTEUR_PA = {
	"plates": 2.1,
	"mailles": 2.1,
	"metal": 2.1,
	"bouclier": 2.3,
	"cuir_renforce": 1.8,
	"cuir_souple": 1.4,
	"os": 1.5,
	"fourrure": 1.0,
	"tissu": 0.8,
	"apparat": 0.0,   # bijoux, plumes d'apparat, curiosités : aucune protection
}


# ── Table de fabrication ─────────────────────────────────────────────────────────
# slug d'item → (classe de matière, catégorie de lieu | None, [(clé matière, quantité)])
# `None` en catégorie = pièce non fabricable (textile) : elle reçoit un `bonus_pa` mais
# aucune recette.
#
# ⚠️ Trois matières sont volontairement ÉVITÉES dans les recettes neuves, parce qu'elles
# sont produites par une recette (donc jamais auto-approvisionnées) et gèleraient la
# recette exactement comme le `cuir` gelait les 11 recettes d'armure d'origine :
#   `cuir` (tannerie) · `ligatures` (armurerie ← tendons) · `tendons`/`os`/`plumes` (boucherie).
# Les seules exceptions assumées sont les pièces dont l'os ou la plume EST le sujet
# (Bracelets_os, Coiffe_plumes…) : elles restent alimentées par le joueur, exactement comme
# `collier`, `talisman` et `parure` le sont déjà aujourd'hui.
ARMURES = {
	# ── Armurerie : métal, boucliers, cuir renforcé ───────────────────────────────
	"Cotte_de_mailles":      ("mailles",       "armurerie", [("fer", 4), ("peaux", 1)]),
	"Cotte_mailles_benie":   ("mailles",       "armurerie", [("fer", 4), ("argent", 1), ("peaux", 1)]),
	"Armure_plates_surcoat": ("plates",        "armurerie", [("acier", 4), ("fer", 2), ("peaux", 2)]),
	"Heaume_de_fer":         ("metal",         "armurerie", [("fer", 2), ("peaux", 1)]),
	"Heaume_de_plates":      ("plates",        "armurerie", [("acier", 2), ("fer", 1), ("peaux", 1)]),
	"Heaume_ouvert_grave":   ("metal",         "armurerie", [("fer", 2), ("argent", 1), ("peaux", 1)]),
	"Bottes_de_fer":         ("metal",         "armurerie", [("fer", 2), ("peaux", 1)]),
	"Bottes_de_plates":      ("plates",        "armurerie", [("acier", 2), ("peaux", 1)]),
	"Gantelets_acier":       ("metal",         "armurerie", [("acier", 1), ("peaux", 1)]),
	"Gantelets_de_plates":   ("plates",        "armurerie", [("acier", 1), ("fer", 1), ("peaux", 1)]),
	"Jambières_de_plates":   ("plates",        "armurerie", [("acier", 2), ("fer", 1), ("peaux", 1)]),
	"Gantelets_cuir":        ("cuir_renforce", "armurerie", [("peaux", 2), ("poix", 1)]),
	"Cuirasse_cuir_brut":    ("cuir_renforce", "armurerie", [("peaux", 4)]),
	"Cuirasse_cuir_noir":    ("cuir_renforce", "armurerie", [("peaux", 4), ("poix", 1)]),
	"Pourpoint_cuir_renf":   ("cuir_renforce", "armurerie", [("peaux", 3), ("fer", 1)]),
	"Armure_cuir_runee":     ("cuir_renforce", "armurerie", [("peaux", 4), ("argent", 1)]),
	"Armure_cuir_souple_N":  ("cuir_souple",   "armurerie", [("peaux", 2), ("poix", 1)]),
	"Jambières_cuir":        ("cuir_renforce", "armurerie", [("peaux", 2)]),
	"Jambières_cuir_renf":   ("cuir_renforce", "armurerie", [("peaux", 2), ("fer", 1)]),
	"Calotte_cuir_rune":     ("cuir_renforce", "armurerie", [("peaux", 1), ("argent", 1)]),
	"Gants_runiques":        ("cuir_souple",   "armurerie", [("peaux", 1), ("argent", 1)]),
	"Bouclier_ordre":        ("bouclier",      "armurerie", [("hampe", 1), ("fer", 2), ("peaux", 1), ("argent", 1)]),
	"Bouclier_sacre":        ("bouclier",      "armurerie", [("hampe", 1), ("fer", 1), ("peaux", 1), ("argent", 1)]),

	# ── Maroquinerie : vêtements et accessoires de peau ───────────────────────────
	"Veste_cuir_souple":     ("cuir_souple", "maroquinerie", [("peaux", 2)]),
	"Vetements_totémiques":  ("cuir_souple", "maroquinerie", [("peaux", 3)]),
	"Bandeau_de_cuir":       ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	"Braies_fourrure":       ("fourrure",    "maroquinerie", [("peaux", 3)]),
	"Chausses_cuir":         ("cuir_souple", "maroquinerie", [("peaux", 2)]),
	"Jupe_lanieres_cuir":    ("cuir_souple", "maroquinerie", [("peaux", 2)]),
	"Pantalon_cuir":         ("cuir_souple", "maroquinerie", [("peaux", 2)]),
	"Gants_archer":          ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	"Gants_cuir_epais":      ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	"Gants_fins":            ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	"Gants_fins_noirs":      ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	"Gants_peau_noire":      ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	"Gants_prestidigi":      ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	"Gants_sans_doigts":     ("cuir_souple", "maroquinerie", [("peaux", 1)]),
	# Seule pièce « textile » retenue : des bandages SONT du chiffon, et `chiffon` existe
	# déjà comme feuille. ⚠️ Clé item-ref obligatoire : la sous-catégorie `chiffon` résoudrait
	# vers `item:chiffon`, qui n'existe pas — le doc s'appelle `item:Chiffon`.
	"Bandages_de_poing":     ("tissu",       "maroquinerie", [("item:Chiffon", 2)]),

	# ── Cordonnerie : tout ce qui se porte au pied ────────────────────────────────
	"Bottes_cuir_epais":     ("cuir_souple", "cordonnerie", [("peaux", 2)]),
	"Bottes_de_chasse":      ("cuir_souple", "cordonnerie", [("peaux", 2)]),
	"Bottes_de_voyage":      ("cuir_souple", "cordonnerie", [("peaux", 2)]),
	"Bottes_lacees":         ("cuir_souple", "cordonnerie", [("peaux", 2)]),
	"Bottes_noires":         ("cuir_souple", "cordonnerie", [("peaux", 2)]),
	"Bottes_silencieuses":   ("cuir_souple", "cordonnerie", [("peaux", 2)]),
	"Bottines_de_scene":     ("cuir_souple", "cordonnerie", [("peaux", 1)]),
	"Bottines_legeres":      ("cuir_souple", "cordonnerie", [("peaux", 1)]),
	"Chaussons_cuir":        ("cuir_souple", "cordonnerie", [("peaux", 1)]),
	"Chaussons_silencieux":  ("cuir_souple", "cordonnerie", [("peaux", 1)]),
	"Mocassins":             ("cuir_souple", "cordonnerie", [("peaux", 1)]),
	"Sandales_moine":        ("cuir_souple", "cordonnerie", [("peaux", 1)]),
	"Souliers_cuir":         ("cuir_souple", "cordonnerie", [("peaux", 1)]),
	# ⚠️ Alimenté par le joueur : `corde` est produite par la corderie, donc jamais
	# auto-approvisionnée chez le cordonnier. Assumé — c'est une sandale de corde.
	"Sandales_de_corde":     ("apparat",     "cordonnerie", [("item:corde", 2)]),

	# ── Tabletterie : os et bois ──────────────────────────────────────────────────
	"Bracelets_os":          ("os",      "tabletterie", [("os", 1)]),
	"Brassards_os":          ("os",      "tabletterie", [("os", 2), ("peaux", 1)]),
	"Couronne_branchages":   ("apparat", "tabletterie", [("branche", 2)]),

	# ── Plumasserie : parures de plumes (alimentées par le dépeçage, comme `parure`) ─
	"Coiffe_plumes":         ("apparat", "plumasserie", [("plumes", 4)]),
	"Chapeau_a_plume":       ("apparat", "plumasserie", [("plumes", 3)]),

	# ── Textile : bonus_pa seulement, aucune filière pour les produire ────────────
	"Cape_soie_sombre":      ("tissu", None, []),
	"Pourpoint_colore":      ("tissu", None, []),
	"Robe_bordeaux":         ("tissu", None, []),
	"Robe_ceremonie":        ("tissu", None, []),
	"Robe_de_savant":        ("tissu", None, []),
	"Robe_laine_epaisse":    ("tissu", None, []),
	"Robe_lin_ceinturee":    ("tissu", None, []),
	"Robe_noire_capuche":    ("tissu", None, []),
	"Tunique_feuilles":      ("tissu", None, []),
	"Bandeau_meditation":    ("tissu", None, []),
	"Bonnet_de_clerc":       ("tissu", None, []),
	"Cagoule":               ("tissu", None, []),
	"Capuche_bordeaux":      ("tissu", None, []),
	"Capuche_de_laine":      ("tissu", None, []),
	"Capuche_noire":         ("tissu", None, []),
	"Capuche_soie":          ("tissu", None, []),
	"Capuchon_de_lin":       ("tissu", None, []),
	"Chapeau_large_bord":    ("tissu", None, []),
	"Chapeau_mou":           ("tissu", None, []),
	"Couvre_chef_office":    ("tissu", None, []),
	"Chausses_ajustees":     ("tissu", None, []),
	"Chausses_bicolores":    ("tissu", None, []),
	"Chausses_laine":        ("tissu", None, []),
	"Jupe_de_chanvre":       ("tissu", None, []),
	"Jupe_longue_lin":       ("tissu", None, []),
	"Pantalon_ajuste_noir":  ("tissu", None, []),
	"Pantalon_ample":        ("tissu", None, []),
	"Pantalon_toile":        ("tissu", None, []),
	"Pantalon_velours":      ("tissu", None, []),
	"Sous_robe_lin":         ("tissu", None, []),
	"Sous_robe_noire":       ("tissu", None, []),
	"Sandales_lierre":       ("apparat", None, []),

	# ── Armures qui ONT déjà une recette : classe de matière seule, pour le bonus_pa ─
	"Ecu":                   ("bouclier", None, []),
	"bottes":                ("cuir_souple", None, []),
	"gants":                 ("cuir_souple", None, []),
	"ceinture":              ("apparat", None, []),
	"harnais":               ("cuir_souple", None, []),
	"amulette":              ("apparat", None, []),
	"collier":               ("apparat", None, []),
	"talisman":              ("apparat", None, []),
	"parure":                ("apparat", None, []),
	"armure_de_cuir":        ("cuir_renforce", None, []),
	"Bocle":                 ("bouclier", None, []),
	"Bouclier_cerf_volant":  ("bouclier", None, []),
	"Bouclier_chauffe":      ("bouclier", None, []),
	"Bouclier_normand":      ("bouclier", None, []),
	"Ecu_de_joute":          ("bouclier", None, []),
	"Pavois":                ("bouclier", None, []),
	"Pelta":                 ("bouclier", None, []),
	"Rondache":              ("bouclier", None, []),
	"Targe":                 ("bouclier", None, []),
}


# ── Recettes d'origine à corriger ────────────────────────────────────────────────
# Les 11 recettes d'armure déjà en base exigent du `cuir` (et `tendons` pour la Pelta) :
# elles sont GELÉES depuis toujours. On les réémet à l'identique, `cuir` → `peaux` à
# quantité égale — c'est la correction qui remet `item:armure_de_cuir` et les dix boucliers
# en production. ⚠️ `admin_import_bulk` fait un PUT COMPLET : le doc est reproduit en entier
# depuis le dump, seules les clés matières changent.
SUBSTITUTIONS_MATIERE = {"cuir": "peaux", "tendons": "peaux"}


def _slug(texte: str) -> str:
	"""Identifiant ASCII minuscule pour un `_id` de recette (les slugs d'items portent des
	accents : `Jambières_de_plates`)."""
	sans_accent = "".join(
		c for c in unicodedata.normalize("NFD", texte)
		if unicodedata.category(c) != "Mn"
	)
	return "".join(c if (c.isalnum() or c == "_") else "_" for c in sans_accent).lower()


def _dump_le_plus_recent() -> str:
	"""Chemin du dump CouchDB le plus récent (source unique des docs à réémettre)."""
	candidats = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not candidats:
		raise SystemExit(
			"Aucun dump `jsons/telluris-dump-*.json` — exporter d'abord via "
			"GET /admin/exports/couchdb."
		)
	return candidats[-1]


def _charger_docs(chemin: str) -> list:
	with open(chemin, encoding="utf-8") as f:
		return json.load(f).get("docs", [])


def bonus_pa_de(item: dict, classe: str) -> int:
	"""Points d'armure dérivés du poids et de la classe de matière.

	⚠️ Le plancher à 1 ne vaut QUE pour les matières qui protègent vraiment (facteur ≥ 1.0) :
	un gantelet de cuir de 0.1 kg arrête quelque chose, pas une capuche de soie. Le tissu
	(facteur 0.8) est arrondi sans plancher — une robe de laine épaisse garde son point,
	une cape de soie tombe à 0 et n'est pas rééditée."""
	facteur = FACTEUR_PA.get(classe, 0.0)
	if facteur <= 0:
		return 0
	pa = int(round(float(item.get("poids") or 0) * facteur))
	return max(1, pa) if facteur >= 1.0 else pa


def construire_recettes(items: dict, recettes_base: list) -> list:
	"""Docs `recette:*` à importer : les fabrications neuves, puis les recettes d'origine
	corrigées (`cuir`/`tendons` → `peaux`)."""
	docs = []

	for slug, (_classe, categorie, matieres) in ARMURES.items():
		if not categorie:
			continue
		if ("item:" + slug) not in items:
			print(f"  ⚠️  item:{slug} absent du dump — recette ignorée.")
			continue
		docs.append({
			"_id": f"recette:armure_{_slug(slug)}",
			"type": "recette",
			"lieu_categorie": categorie,
			"objet_final": slug,
			"quantite_produite": 1,
			"matieres_premieres": [
				({"item": cle} if cle.startswith("item:") else {"sous_categorie": cle})
				| {"quantite": qte}
				for cle, qte in matieres
			],
		})

	# Correctif des recettes d'origine : mêmes docs, matière débloquée.
	armures_ids = {i["_id"] for i in items.values() if i.get("categorie") == "armure"}
	for r in recettes_base:
		if ("item:" + str(r.get("objet_final"))) not in armures_ids:
			continue
		corrige = {k: v for k, v in r.items() if k != "_rev"}
		touche = False
		if isinstance(corrige.get("matieres_premieres"), list):
			for m in corrige["matieres_premieres"]:
				remplacant = SUBSTITUTIONS_MATIERE.get(m.get("sous_categorie"))
				if remplacant:
					m["sous_categorie"] = remplacant
					touche = True
			# ⚠️ Deux matières distinctes peuvent retomber sur la même après substitution
			# (Pelta : `cuir` 2 + `tendons` 1 → `peaux` deux fois). On FUSIONNE les
			# quantités : `recette_matieres` renvoie les entrées telles quelles, et une clé
			# répétée serait consommée en deux prélèvements — illisible en base.
			fusion: dict[str, int] = {}
			for m in corrige["matieres_premieres"]:
				cle = m.get("item") or m.get("sous_categorie")
				fusion[cle] = fusion.get(cle, 0) + int(m.get("quantite", 1) or 1)
			if len(fusion) != len(corrige["matieres_premieres"]):
				corrige["matieres_premieres"] = [
					({"item": c} if c.startswith("item:") else {"sous_categorie": c})
					| {"quantite": q}
					for c, q in fusion.items()
				]
		remplacant = SUBSTITUTIONS_MATIERE.get(corrige.get("matiere_premiere_sous_categorie"))
		if remplacant:
			corrige["matiere_premiere_sous_categorie"] = remplacant
			touche = True
		if touche:
			docs.append(corrige)

	return docs


def construire_bonus_pa(items: dict) -> list:
	"""Docs `item:*` COMPLETS (PUT intégral) enrichis d'un `bonus_pa`. Une armure qui en
	porte déjà un n'est pas rééditée, une armure sans protection non plus : le fichier ne
	contient que des docs réellement modifiés."""
	docs = []
	for slug, (classe, _categorie, _matieres) in ARMURES.items():
		item = items.get("item:" + slug)
		if not item:
			print(f"  ⚠️  item:{slug} absent du dump — bonus_pa ignoré.")
			continue
		if item.get("bonus_pa") is not None:
			continue
		pa = bonus_pa_de(item, classe)
		if pa <= 0:
			continue
		docs.append({k: v for k, v in item.items() if k != "_rev"} | {"bonus_pa": pa})
	return docs


def main() -> None:
	chemin = _dump_le_plus_recent()
	docs_base = _charger_docs(chemin)
	items = {d["_id"]: d for d in docs_base if d.get("type") == "item"}
	recettes_base = [d for d in docs_base if d.get("type") == "recette"]
	print(f"Dump lu : {os.path.basename(chemin)} ({len(items)} items, {len(recettes_base)} recettes)")

	# Garde-fou : toute armure du dump doit être classée ici, sinon elle passerait à la
	# trappe en silence à la prochaine passe.
	armures_dump = {i["_id"][5:] for i in items.values() if i.get("categorie") == "armure"}
	oubliees = sorted(armures_dump - set(ARMURES))
	if oubliees:
		print(f"  ⚠️  {len(oubliees)} armure(s) non classée(s) dans ARMURES : {', '.join(oubliees)}")

	recettes = construire_recettes(items, recettes_base)
	bonus = construire_bonus_pa(items)

	with open(SORTIE_RECETTES, "w", encoding="utf-8") as f:
		json.dump([ITEM_PEAUX] + recettes, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	with open(SORTIE_BONUS_PA, "w", encoding="utf-8") as f:
		json.dump(bonus, f, ensure_ascii=False, indent="\t")
		f.write("\n")

	neuves = sum(1 for d in recettes if d["_id"].startswith("recette:armure_"))
	print(f"→ {os.path.relpath(SORTIE_RECETTES, RACINE)} : "
		  f"1 matière + {neuves} recettes neuves + {len(recettes) - neuves} corrigées")
	print(f"→ {os.path.relpath(SORTIE_BONUS_PA, RACINE)} : {len(bonus)} armures enrichies d'un bonus_pa")


if __name__ == "__main__":
	main()

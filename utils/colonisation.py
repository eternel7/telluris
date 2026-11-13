"""Voie de colonisation (pur) : fonder une implantation hors des cités et la faire grandir.

Décisions de l'Auteur : docs/lore/systemes/20261112_voie_de_colonisation.md (les § cités
ci-dessous sont les siens). Compétence : `telluris-colonisation`.

- Doc `implantation:<hex12>` (état de partie, `type:"implantation"` : les balayages
  `find_docs({"type":"lieu"})` ne le voient pas), relié par un `link:*` à sa case du pays.
- LIEN PUR au lieu modèle (§ 12.3) : le doc ne porte que `modele` ; image, grille et entrées
  sont posées à la lecture par `db.config.get_doc` et retirées à l'écriture — ce module les
  lit donc sur le doc comme sur n'importe quel lieu, et ne les écrit jamais.
- Chiffres : `rules:colonisation` ; tout bloc absent du doc retombe sur `DEFAUTS` (relu par
  `dev/gen_colonisation.py`, qui le pose dans le doc — le point d'édition est le doc).
- AUCUN tick de fond : `rattraper` rejoue le temps écoulé, passe par passe, au passage du
  fondateur ou d'un associé (§ 1, § 10), plafonné à `reglages.rattrapage_max_s` (§ 6).
- Sécurité et moral : DÉRIVÉS à la lecture, jamais stockés (§ 5).

Module pur : DB injectée, il mute sans sauver (l'appelant persiste).

Pas encore en jeu (voir la compétence) : sous-lieux marchands (boutique, atelier, auberge,
étable) et leurs échanges, combat joué d'une attaque, tanière à vider, guilde du joueur,
colons escortés, coffre d'associé."""

import math
import random
import time
import uuid

from utils import proprietes
from utils.recrutement import RANGS

REGLES_ID = "rules:colonisation"
TYPE_DOC = "implantation"
CATEGORIE = "implantation"
CATEGORIE_PAYS = "pays"
CATEGORIE_CITE = "ville"
TAG_MODELE = "modele_colonie"
PREFIXE_TAG_PAYS = "pays_"

FONDATEUR = "fondateur"
ASSOCIE = "associe"
SOUTIEN = "soutien"
VISITEUR = "visiteur"

REPERE = "repere"
SOUS_LIEU = "sous_lieu"
# Natures de bâtiment que le moteur sait faire vivre : le REPÈRE (une fiche au contact) et le
# SOUS-LIEU (un `lieu:colonie_*` où l'on entre, né à la première pose, § 12.4).
NATURES_OUVERTES = (REPERE, SOUS_LIEU)
PREFIXE_SOUS_LIEU = "lieu:colonie_"

EMPLOYE_MORT = "mort"
EMPLOYE_PARTI = "parti"

JOURNAL_MAX = 40
JOUR_S = 86400

# Teinte du halo des REPÈRES (§ 12.4) : une couleur qu'aucune famille de métier ne porte
# (`enseignes_icones.FAMILLES`, verrouillé par test) — elle dit qu'on n'y entre pas.
RGB_REPERE = "235, 235, 215"

# ── Valeurs de départ (posées dans `rules:colonisation` par le générateur) ───────────
OR = 10000

DEFAUTS = {
	"temps": {"passe_s": 3600},
	"stocks_depart": {"nourriture": 12, "bois": 12, "materiaux": 0, "medicaments": 0},
	"stocks_labels": {"nourriture": "Nourriture", "bois": "Bois", "materiaux": "Matériaux",
					  "medicaments": "Médicaments"},
	"stockage_base": 60,          # unités par stock sans entrepôt
	"logements_base": 2,          # la tente du fondateur
	"consommation": {
		"nourriture_par_habitant_jour": 1.0,
		"bois_feu_jour": {"grand": 6.0, "reduit": 2.0},
		"medicaments_par_soin": 1.0,
		"jours_reserve": 3,       # sous ce nombre de jours d'avance, le stock est « bas »
		"materiaux_seuil": 5, "medicaments_seuil": 2,
	},
	# Ce qu'un objet du sac devient une fois donné : premier stock dont une règle le reconnaît
	# (ordre de la liste). `filtres` = clés de `utils/filtres_boutique.filtres_item`.
	"depots": [
		{"stock": "nourriture", "filtres": ["conso.nourriture", "conso.boisson"],
		 "sous_categories": ["carcasse", "viande", "volaille", "legume", "fruit", "fruit_sec", "grain", "farine",
							 "baie", "miel", "salaison", "truffe", "raisin", "boulangerie", "cuisine"],
		 "unites_par_kg": 1},
		{"stock": "medicaments", "filtres": ["conso.soin"], "sous_categories": ["herbe"], "unites_par_kg": 10},
		{"stock": "bois", "filtres": ["matiere.bois"], "sous_categories": [], "unites_par_kg": 0.5},
		{"stock": "materiaux", "filtres": ["matiere.metal"], "sous_categories": ["corde", "pierre", "sel_gemme"],
		 "unites_par_kg": 1},
	],
	"batiments_def": [
		{"id": "habitation", "label": "Habitation", "icone": "🏠", "nature": REPERE, "palier_min": "campement",
		 "prix_cuivre": 5000, "bois": 10, "materiaux": 2, "logements": 5, "postes": {"medecin": 1},
		 "description": "Cinq habitants y logent ; un soignant peut s'y installer."},
		{"id": "entrepot", "label": "Entrepôt", "icone": "📦", "nature": REPERE, "palier_min": "campement",
		 "prix_cuivre": 5000, "bois": 12, "materiaux": 2, "stockage": 100,
		 "postes": {"intendant": 1, "bucheron": 1, "carrier": 1, "batisseur": 1},
		 "description": "Agrandit les quatre réserves ; intendant, bûcheron, carrier et bâtisseur y ont leur poste."},
		{"id": "poste_de_garde", "label": "Poste de garde", "icone": "🛡️", "nature": REPERE, "palier_min": "campement",
		 "prix_cuivre": 8000, "bois": 15, "materiaux": 5, "postes": {"garde": 2, "chasseur": 1},
		 "description": "Deux gardes et un chasseur : la nuit est couverte, le territoire se lit."},
		{"id": "ferme", "label": "Ferme", "icone": "🌾", "nature": REPERE, "palier_min": "hameau",
		 "prix_cuivre": 10000, "bois": 20, "materiaux": 5, "postes": {"agriculteur": 2, "eleveur": 1, "pecheur": 1},
		 "description": "Cultures, élevage et pêche nourrissent le lieu."},
		# Sous-lieux : `categorie` fixe, ou choisie à la construction parmi les métiers des
		# FAMILLES d'enseigne (`enseignes_icones.METIERS`) dont le marchand générique existe.
		{"id": "etable", "label": "Étable", "icone": "🐴", "nature": SOUS_LIEU, "palier_min": "bourgade",
		 "prix_cuivre": 20000, "bois": 30, "materiaux": 10, "postes": {"palefrenier": 1}, "categorie": "etable",
		 "description": "Un palefrenier y tient l'écurie : montures à vendre."},
		{"id": "auberge", "label": "Auberge", "icone": "🍺", "nature": SOUS_LIEU, "palier_min": "bourgade",
		 "prix_cuivre": 30000, "bois": 40, "materiaux": 15, "postes": {"aubergiste": 1}, "categorie": "auberge",
		 "description": "Salle commune, tableau d'information et chambres : un aubergiste la tient."},
		{"id": "boutique", "label": "Boutique", "icone": "🧺", "nature": SOUS_LIEU, "palier_min": "bourgade",
		 "prix_cuivre": 20000, "bois": 30, "materiaux": 10, "postes": {"marchand": 1},
		 "familles": ["vivres", "savoir"],
		 "description": "Un marchand y vend et y achète ; elle rachète aussi la production du lieu."},
		{"id": "atelier", "label": "Atelier", "icone": "⚒️", "nature": SOUS_LIEU, "palier_min": "bourgade",
		 "prix_cuivre": 25000, "bois": 30, "materiaux": 20, "postes": {"artisan": 1},
		 "familles": ["armes", "soins", "artisanat"],
		 "description": "Un artisan y fabrique sur place, puise et reverse au flux du lieu, prend commande."},
		# Le négoce (§ 8) : le négociant et son personnel vendent la production du lieu à ses boutiques.
		{"id": "comptoir", "label": "Comptoir de négoce", "icone": "⚖️", "nature": REPERE, "palier_min": "bourgade",
		 "prix_cuivre": 15000, "bois": 20, "materiaux": 10,
		 "postes": {"marchand": 1, "commis": 1, "charretier": 1, "teneur_livres": 1, "crieur": 1},
		 "activite": {"metier": "marchand", "categories": ["negociant"]},
		 "effets_metier": {"commis": {"prospection": 2}, "charretier": {"portage_kg": 200},
						   "teneur_livres": {"caisse_facteur": 2}, "crieur": {"crieur": 2}},
		 "description": "Le négociant vend aux boutiques du lieu la production des fermes, coupes et carrières ; "
						"commis, charretier, teneur de livres et crieur l'épaulent."},
	],
	# `requis_pour` : la fortification minimale du palier à ATTEINDRE (§ 4) ; sans ce champ,
	# une défense au-delà du minimum, lue dans le panneau seul (§ 12.1).
	"fortifications": [
		{"id": "palissade", "label": "Palissade complète et porte", "palier_min": "campement",
		 "requis_pour": "hameau", "prix_cuivre": 2 * OR, "bois": 40, "materiaux": 5, "defense": 4},
		{"id": "fosse_tours", "label": "Fossé et tours", "palier_min": "hameau",
		 "requis_pour": "bourgade", "prix_cuivre": 8 * OR, "bois": 80, "materiaux": 40, "defense": 3},
		{"id": "enceinte", "label": "Enceinte et portes fortifiées", "palier_min": "bourgade",
		 "requis_pour": "village", "prix_cuivre": 30 * OR, "bois": 100, "materiaux": 150, "defense": 3},
		{"id": "murailles", "label": "Murailles", "palier_min": "village",
		 "requis_pour": "bourg", "prix_cuivre": 100 * OR, "bois": 100, "materiaux": 400, "defense": 3},
		{"id": "systeme_defensif", "label": "Système défensif complet", "palier_min": "petite_ville",
		 "requis_pour": "ville", "prix_cuivre": 1000 * OR, "bois": 300, "materiaux": 1200, "defense": 3},
		{"id": "eclairage", "label": "Éclairage des abords", "palier_min": "campement",
		 "prix_cuivre": 5000, "bois": 10, "materiaux": 0, "defense": 1},
		{"id": "tour_de_guet", "label": "Tour de guet", "palier_min": "hameau",
		 "prix_cuivre": 3 * OR, "bois": 30, "materiaux": 20, "defense": 2},
	],
	# S'AJOUTENT aux métiers de `rules:proprietes` (jamais recopiés). `produit` : unités par
	# jour et par PNJ au poste, pondérées par l'axe `axe` de la fiche de site.
	"metiers_def": [
		{"id": "agriculteur", "label": "Agriculteur", "cout_embauche_cuivre": 400,
		 "produit": {"stock": "nourriture", "par_jour": 4, "axe": "nourriture",
					 "items": ["item:grain_de_froment", "item:grain_d_orge", "item:grain_de_seigle"]}},
		{"id": "eleveur", "label": "Éleveur", "cout_embauche_cuivre": 400,
		 "produit": {"stock": "nourriture", "par_jour": 3, "axe": "nourriture",
					 "items": ["item:oeufs_de_ferme", "item:motte_de_beurre"]}},
		{"id": "chasseur", "label": "Chasseur", "cout_embauche_cuivre": 600,
		 "produit": {"stock": "nourriture", "par_jour": 2, "axe": "nourriture", "items": ["item:viande"]}},
		{"id": "pecheur", "label": "Pêcheur", "cout_embauche_cuivre": 400,
		 "produit": {"stock": "nourriture", "par_jour": 3, "axe": "eau", "exige_axe": True}},
		{"id": "bucheron", "label": "Bûcheron", "cout_embauche_cuivre": 400,
		 "produit": {"stock": "bois", "par_jour": 5, "axe": "materiaux", "items": ["item:Rondin_de_Chene"]}},
		{"id": "carrier", "label": "Carrier", "cout_embauche_cuivre": 500,
		 "produit": {"stock": "materiaux", "par_jour": 3, "axe": "materiaux", "items": ["item:pierre"]}},
		{"id": "batisseur", "label": "Bâtisseur", "cout_embauche_cuivre": 800},
		{"id": "aubergiste", "label": "Aubergiste", "cout_embauche_cuivre": 800},
	],
	"metiers_roles": {"gardes": ["garde", "gardien"], "soignants": ["medecin", "apothicaire"],
					  "pisteurs": ["chasseur"], "intendants": ["intendant"], "batisseurs": ["batisseur"]},
	# Vente de la production (§ 8) : au-delà de `surplus_facteur` × le seuil « bas » d'un stock,
	# une unité d'objet part pour `unites_par_objet` unités du stock. Ateliers : 2 jours au plus.
	"echanges": {"passes_max": 48, "surplus_facteur": 2, "unites_par_objet": 1,
				 "prospection_base": 3, "portage_kg": 20, "decote_sans_negociant": 0.2,
				 "seuil_refus": 1, "caisse_max_par_rang": 5000, "journal_max": 20},
	"montures_etable": ["espece:ane", "espece:mulet", "espece:cheval"],
	# Un garde nommé, quand il se bat aux côtés du fondateur (§ 6) : un combattant standard.
	"garde_combattant": {"voc": "guerrier", "niveau": 2,
						 "caracts": {"V": 6, "F": 30, "R": 30, "Ag": 25, "Vol": 20, "Int": 15, "Cha": 15, "Ch": 15},
						 "slots": {"main_droite": "item:Epee_courte", "torse": "item:Armure_matelassee"}},
	# Repos au feu : les lignes de la nuit (chacune autonome, joueur au « vous »).
	"nuit_feu": [
		"Les braises claquent ; quelqu'un remet une bûche sans un mot.",
		"Au-delà de la lueur, des yeux s'allument un instant, puis s'éteignent.",
		"Un garde fait le tour du camp, sa lanterne balançant au bout du bras.",
		"La fumée monte droit : demain sera clair.",
		"Une chouette s'interroge dans les arbres ; personne ne lui répond.",
		"Vous vous réveillez une fois, le dos froid, et vous rapprochez des braises.",
		"On chuchote près du feu : une histoire de loup qui parlait, que nul ne croit.",
		"Le vent tourne et rabat la fumée ; on tousse, on rit, on se rendort.",
		"Le ciel pâlit à l'est. Quelqu'un attise déjà le feu pour la soupe.",
		"Un enfant s'est endormi contre un sac de grain, une miche entamée à la main.",
	],
	"intendant_economie": 0.1,    # part de nourriture épargnée (non cumulatif)
	"reparation_materiaux": 5,
	"candidats_duree_s": JOUR_S,
	# Fiche de site (§ 3) : mots-clés cherchés dans les `terrain_tags` des zones qui couvrent
	# la case et dans les tags du pays. Note 0-3 par axe.
	"site": {
		"rayon_eau": 2, "rayon_donjon": 6,
		"facteur_axe": [0.5, 0.75, 1.0, 1.25],
		"mots": {
			"eau": ["source", "riviere", "lac", "cascade", "oasis", "delta", "marais", "cote", "fjord",
					"lagune", "berge", "eau"],
			"nourriture": ["plaine", "herbe", "champ", "culture", "vallee", "bocage", "verger", "ferme",
						   "foret", "bois", "savane", "alpage", "estive", "jardin", "vigne", "steppe"],
			"materiaux": ["foret", "bois", "conifere", "jungle", "bambou", "pierre", "roche", "rocher",
						  "carriere", "calcaire", "falaise", "montagne", "colline", "eboulis"],
			"commerce": ["riviere", "cote", "mer", "delta", "chemin", "plage", "lagune"],
			"defense": ["colline", "plateau", "falaise", "montagne", "rocher", "ile", "gorge", "pente"],
		},
		"categories_donjon": ["portail", "temple_portail", "grotte"],
		"mots_axe": {
			"eau": ["aucune eau proche", "un point d'eau", "de l'eau en suffisance", "de l'eau en abondance"],
			"nourriture": ["terre ingrate", "terre maigre", "terre généreuse", "terre d'abondance"],
			"materiaux": ["ni bois ni pierre", "peu de matériaux", "bois ou pierre à portée", "bois et pierre à foison"],
			"commerce": ["à l'écart de tout", "loin des routes", "bien relié", "au carrefour des échanges"],
			"defense": ["terrain ouvert", "peu d'abri", "bonne position", "position forte"],
			"danger": ["contrée paisible", "contrée surveillée", "contrée dangereuse", "contrée redoutable"],
		},
	},
	"securite": {
		"plafond": 95,            # la sécurité n'atteint jamais le maximum (§ 5)
		"base_physique": 2, "feu_grand": 2,
		"habitants_par_garde": 8,
		"connaissance": {"1": 8, "2": 6, "3": 4, "4": 20, "aucune": 20}, "bonus_pisteur": 4,
		"mots": [[25, "à découvert"], [45, "précaire"], [65, "gardée"], [80, "sûre"], [101, "solide"]],
	},
	"moral": {
		"base": 50, "fenetre_s": 7 * JOUR_S,
		"nourriture_ok": 10, "nourriture_basse": -20, "nourriture_vide": -30,
		"loge": 5, "mal_loge": -10, "soignant": 5,
		"attaque": -5, "attaque_min": -20, "mort": -8, "mort_min": -30,
		"prosperite": 5, "reputation_par_rang": 2,
		"feu": {"grand": 5, "reduit": -5},
		"expedition": 2, "securite_diviseur": 5,
		"mots": [[25, "abattu"], [45, "inquiet"], [60, "stable"], [80, "confiant"], [101, "radieux"]],
	},
	"population": {
		"arrivee_proba": 0.04, "arrivee_moral_min": 50, "arrivee_securite_min": 35,
		"depart_moral": 25, "depart_proba": 0.05,
		"depart_nomme_moral": 15, "depart_nomme_proba": 0.02,
	},
	"sante": {
		"maladie_par_habitant": 0.002, "maladie_max": 0.2,
		"guerison_soignee": 0.25, "guerison_partielle": 0.1, "guerison_seule": 0.04,
		"mort_seule": 0.01,
	},
	"menace": {
		"remarque_proba": 0.01, "feu": {"grand": 1.5, "reduit": 0.7},
		"harcele_proba": 0.008, "pillage_proba": 0.05, "pillage_part": 0.05,
		"taniere_proba": 0.01, "taniere_par_pisteur": 0.03,
		# « plus rare et plus grave à mesure que le lieu grandit » (§ 4)
		"attaque_proba": {"campement": 0.03, "hameau": 0.015, "bourgade": 0.015, "village": 0.008,
						  "bourg": 0.003, "petite_ville": 0.003, "ville": 0.001},
		"nuit_sans_garde": 2.0,   # facteur d'attaque sans garde au poste (§ 5, Nuit)
		# Présence du fondateur ou d'un associé : l'attaque se JOUE (§ 6). Laissée sans réponse
		# `delai_defense_s`, elle se résout comme en son absence.
		"delai_defense_s": 900,
		"assaillants_base": 2,          # + rang du palier : « plus grave à mesure qu'il grandit »
		"taniere_meute": 3,             # bêtes dans la tanière (+ rang du palier)
		"repousse_s": 7 * JOUR_S,       # tanière vidée : une autre bête s'installe ensuite
		"mots": {"0": "aucune menace connue", "1": "une bête rôde dans les environs",
				 "2": "la bête a remarqué le lieu", "3": "elle s'en prend aux troupeaux et aux réserves",
				 "4": "sa tanière est localisée"},
	},
}


def now_epoch() -> int:
	return int(time.time())


def _int(v, defaut=0) -> int:
	try:
		return int(v)
	except (TypeError, ValueError):
		return defaut


def _num(v, defaut=0.0) -> float:
	try:
		return float(v)
	except (TypeError, ValueError):
		return defaut


def _par_id(liste, ident) -> dict | None:
	return next((x for x in liste or [] if isinstance(x, dict) and x.get("id") == ident), None)


def regles(get_doc_fn) -> dict:
	"""Valeur de `rules:colonisation`, chaque bloc de `DEFAUTS` absent du doc repris des
	défauts. Doc absent ⇒ aucun palier : rien ne se fonde, rien ne casse."""
	valeur = dict(((get_doc_fn(REGLES_ID) or {}).get("value")) or {})
	for cle, defaut in DEFAUTS.items():
		if cle not in valeur:
			valeur[cle] = defaut
		elif isinstance(defaut, dict) and isinstance(valeur[cle], dict):
			valeur[cle] = {**defaut, **valeur[cle]}
	return valeur


def est_implantation(doc: dict | None) -> bool:
	return (doc or {}).get("type") == TYPE_DOC


CHAMPS_PUBLICS = ("type", "categorie", "label", "image", "lieu_parent", "palier", "fondateur_nom")


def details_publics(doc: dict) -> dict:
	"""Ce qu'une LISTE de lieux (liens d'une case) peut montrer d'une implantation à
	n'importe qui ; tout autre doc est rendu tel quel."""
	if not est_implantation(doc):
		return doc
	return {k: doc[k] for k in CHAMPS_PUBLICS if k in doc}


# ── Paliers ──────────────────────────────────────────────────────────────────────────

def paliers(reg: dict) -> list:
	return list(reg.get("paliers") or [])


def palier_def(reg: dict, palier_id) -> dict | None:
	return _par_id(paliers(reg), palier_id)


def rang_palier(reg: dict, palier_id) -> int:
	"""Position du palier dans l'échelle (0 = Campement) ; inconnu ⇒ 0."""
	return next((i for i, p in enumerate(paliers(reg)) if p.get("id") == palier_id), 0)


def palier_suivant(reg: dict, palier_id) -> dict | None:
	liste = paliers(reg)
	i = rang_palier(reg, palier_id)
	return liste[i + 1] if i + 1 < len(liste) else None


def palier_atteint(reg: dict, palier_id, minimum) -> bool:
	return rang_palier(reg, palier_id) >= rang_palier(reg, minimum)


# ── Site (§ 2, § 3) ──────────────────────────────────────────────────────────────────

def distance(a, b) -> int:
	"""Cases entre deux positions `[x, y]` de la carte du pays (Chebyshev : un pas en
	diagonale vaut un pas, comme le déplacement)."""
	return max(abs(_int(a[0]) - _int(b[0])), abs(_int(a[1]) - _int(b[1])))


def _xy(position) -> list:
	if isinstance(position, dict):
		return [_int(position.get("x")), _int(position.get("y"))]
	return [_int(position[0]), _int(position[1])]


def lieux_relies(connexions: list, pays_id, get_doc_fn) -> list:
	"""`[{"id", "label", "categorie", "pos"}]` : chaque lieu relié à une case de la carte du
	pays (connexions du pays, nœud du pays porteur d'un `pos`). Dédoublonné par lieu et case."""
	out, vus = [], set()
	for conn in connexions or []:
		nodes = [n for n in conn.get("nodes") or [] if isinstance(n, dict)]
		ici = [n for n in nodes if n.get("lieu") == pays_id and len(n.get("pos") or []) >= 2]
		for autre in (n for n in nodes if n.get("lieu") != pays_id):
			doc = get_doc_fn(autre.get("lieu")) or {}
			for n in ici:
				cle = (autre.get("lieu"), n["pos"][0], n["pos"][1])
				if cle in vus:
					continue
				vus.add(cle)
				out.append({"id": autre.get("lieu"), "label": doc.get("label", ""),
							"categorie": doc.get("categorie"), "pos": [n["pos"][0], n["pos"][1]]})
	return out


def cites(relies: list) -> list:
	return [l for l in relies or [] if l.get("categorie") == CATEGORIE_CITE]


def cites_de_la_charte(relies: list, position) -> list:
	"""Les cités les plus proches de la case : à égale distance, toutes se valent (§ 2)."""
	pos = _xy(position)
	villes = cites(relies)
	if not villes:
		return []
	mini = min(distance(v["pos"], pos) for v in villes)
	out, vus = [], set()
	for v in villes:
		if distance(v["pos"], pos) == mini and v["id"] not in vus:
			vus.add(v["id"])
			out.append(v)
	return out


def case_marchable(lieu_doc: dict, x: int, y: int) -> bool:
	cells = (lieu_doc or {}).get("cells") or []
	return 0 <= y < len(cells) and 0 <= x < len(cells[y]) and cells[y][x] == 1


def rang_suffisant(character: dict, reg: dict) -> bool:
	"""Rang de guilde minimal (§ 2) : le MEILLEUR rang du personnage, toutes cités confondues."""
	minimum = (reg.get("reglages") or {}).get("rang_min", RANGS[-1])
	if minimum not in RANGS:
		return False
	rangs = [r for r in ((character or {}).get("rangs_guilde") or {}).values() if r in RANGS]
	return bool(rangs) and max(RANGS.index(r) for r in rangs) >= RANGS.index(minimum)


def implantations_de(character: dict) -> list:
	return list((character or {}).get("implantations") or [])


def peut_fonder(character: dict, pays_doc: dict, position, relies: list, implantations: list,
				reg: dict) -> tuple[bool, str]:
	"""Les règles du § 2, dans l'ordre où on les dit au joueur. `implantations` = docs des
	implantations déjà posées sur CE pays (tous fondateurs)."""
	r = reg.get("reglages") or {}
	if not paliers(reg):
		return False, "La colonisation n'est pas ouverte."
	if (pays_doc or {}).get("categorie") != CATEGORIE_PAYS:
		return False, "Une implantation se fonde en pleine contrée, sur la carte d'un pays."
	if not rang_suffisant(character, reg):
		return False, f"La charte exige le rang {r.get('rang_min', '?')} de la Guilde."
	pos = _xy(position)
	if not case_marchable(pays_doc, pos[0], pos[1]):
		return False, "On ne s'établit pas sur cette case."
	if any(l["pos"] == pos for l in relies or []):
		return False, "Cette case est déjà prise."
	if any(distance(v["pos"], pos) < _int(r.get("distance_cite_min")) for v in cites(relies)):
		return False, f"Trop près d'une Cité-État : il faut au moins {_int(r.get('distance_cite_min'))} cases."
	miennes = sum(1 for i in implantations or [] if i.get("fondateur") == (character or {}).get("_id"))
	if miennes >= _int(r.get("implantations_par_pays"), 1):
		return False, "Vous avez déjà une implantation dans ce pays."
	if any(distance((i.get("origine") or {}).get("pos") or [0, 0], pos) < _int(r.get("distance_implantation_min"))
		   for i in implantations or []):
		return False, (f"Trop près d'une autre implantation : il faut au moins "
					   f"{_int(r.get('distance_implantation_min'))} cases.")
	return charte_valable(character, relies, pos)


# ── La charte (§ 2) : achetée au bureau d'un maître de guilde ────────────────────────
CATEGORIE_BUREAU = "bureau_maitre_guilde"
CHAMP_CHARTE = "charte_colonie"


def est_bureau_de_guilde(lieu_doc: dict | None) -> bool:
	return (lieu_doc or {}).get("categorie") == CATEGORIE_BUREAU


def charte_de(character: dict) -> dict | None:
	c = (character or {}).get(CHAMP_CHARTE)
	return c if isinstance(c, dict) and c.get("cite") else None


def peut_acheter_charte(character: dict, bureau_doc: dict, reg: dict) -> tuple[bool, str]:
	"""Au bureau du maître de guilde d'une cité : le rang de la charte, une charte à la fois."""
	if not paliers(reg):
		return False, "La colonisation n'est pas ouverte."
	if not est_bureau_de_guilde(bureau_doc) or not bureau_doc.get("lieu_parent"):
		return False, "La charte s'achète au bureau d'un maître de guilde."
	if not rang_suffisant(character, reg):
		return False, f"La charte exige le rang {(reg.get('reglages') or {}).get('rang_min', '?')} de la Guilde."
	tenue = charte_de(character)
	if tenue:
		return False, f"Vous tenez déjà une charte de {tenue.get('label') or 'la Guilde'}."
	return True, ""


def delivrer_charte(character: dict, cite_doc: dict, prix: int, now: int | None = None) -> dict:
	"""La charte est attachée à la CITÉ du maître qui l'a signée (son bureau pend à elle)."""
	charte = {"cite": cite_doc.get("_id"), "label": cite_doc.get("label", ""), "prix": int(prix),
			  "at": now_epoch() if now is None else now}
	character[CHAMP_CHARTE] = charte
	return charte


def charte_valable(character: dict, relies: list, position) -> tuple[bool, str]:
	"""La charte ne vaut que là où sa cité est la plus proche (à égale distance, toutes se
	valent, § 2)."""
	charte = charte_de(character)
	plus_proches = cites_de_la_charte(relies, position)
	noms = " ou ".join(c.get("label") or c["id"] for c in plus_proches) or "aucune cité"
	if not charte:
		return False, f"Il vous faut une charte, achetée au bureau du maître de guilde de {noms}."
	if charte["cite"] not in {c["id"] for c in plus_proches}:
		return False, (f"Votre charte vient de {charte.get('label') or charte['cite']} : ici, elle "
					   f"doit être signée par le maître de guilde de {noms}.")
	return True, ""


def consommer_charte(character: dict) -> dict | None:
	return character.pop(CHAMP_CHARTE, None)


def placements_actifs(pays_doc: dict, position) -> list:
	"""Placements de zone d'influence qui couvrent la case (test géométrique de `zones`)."""
	from utils import zones
	pos = _xy(position)
	return [p for p in (pays_doc or {}).get("zone_influences") or []
			if p.get("zone") and zones.est_dans_zone(pos[0], pos[1], p["zone"], [p])]


def slug_pays(pays_id) -> str:
	return str(pays_id or "").split(":", 1)[-1]


def tags_site(pays_doc: dict, position, zone_defs: dict) -> list:
	"""Tags du site (§ 12.2) : ceux de la zone d'influence qui couvre la case, puis ceux du
	pays parent, puis `pays_<slug>`."""
	from utils import zones
	tags = list(zones.terrain_tags_actifs(placements_actifs(pays_doc, position), zone_defs))
	for t in list((pays_doc or {}).get("tags") or []) + [PREFIXE_TAG_PAYS + slug_pays((pays_doc or {}).get("_id"))]:
		if t and t not in tags:
			tags.append(t)
	return tags


def fiche_site(pays_doc: dict, position, zone_defs: dict, relies: list, reg: dict) -> dict:
	"""Les six axes du § 3, LUS sur la carte du pays autour de la case — rien n'est saisi par
	site, rien n'est stocké. `{axe: {"note": 0-3, "mots": str, "details": [str]}}`."""
	from utils import zones
	conf = reg.get("site") or {}
	mots = conf.get("mots") or {}
	pos = _xy(position)
	actifs = placements_actifs(pays_doc, pos)
	tags = set(tags_site(pays_doc, pos, zone_defs))
	cells = (pays_doc or {}).get("cells") or []

	def note_tags(axe):
		trouves = [m for m in mots.get(axe) or [] if m in tags]
		return min(3, len(trouves)), trouves

	fiche = {}
	for axe in ("eau", "nourriture", "materiaux", "defense"):
		n, trouves = note_tags(axe)
		fiche[axe] = {"note": n, "details": trouves}
	# Eau : une case d'eau (terrain 5) à portée vaut un point d'eau, même sans zone peinte.
	rayon = _int(conf.get("rayon_eau"), 2)
	if any(0 <= y < len(cells) and 0 <= x < len(cells[y]) and cells[y][x] == 5
		   for y in range(pos[1] - rayon, pos[1] + rayon + 1) for x in range(pos[0] - rayon, pos[0] + rayon + 1)):
		fiche["eau"]["note"] = min(3, fiche["eau"]["note"] + 1)
		fiche["eau"]["details"].append("eau à portée")
	# Nourriture : ce que la contrée laisse récolter ici compte aussi.
	zones_ici = {p["zone"] for p in actifs}
	recoltes = [r for r in (pays_doc or {}).get("ressources") or [] if zones_ici & set(r.get("zones") or [])]
	if recoltes:
		fiche["nourriture"]["note"] = min(3, fiche["nourriture"]["note"] + 1)
		fiche["nourriture"]["details"].append(f"{len(recoltes)} ressource(s) à récolter")
	# Commerce : cité proche, fleuve, mer.
	villes = cites(relies)
	n, trouves = note_tags("commerce")
	if villes:
		proche = min(villes, key=lambda v: distance(v["pos"], pos))
		d = distance(proche["pos"], pos)
		n += 2 if d <= 10 else 1 if d <= 20 else 0
		trouves.append(f"{proche.get('label') or 'une cité'} à {d} cases")
	fiche["commerce"] = {"note": min(3, n), "details": trouves}
	# Danger : modificateurs des zones, espèces rencontrables, donjon proche.
	danger = sum(_num(((zone_defs or {}).get(p["zone"]) or {}).get("modificateurs", {}).get("danger")) for p in actifs)
	especes = sorted(zones.especes_rencontrables(pays_doc, zones_ici)) if zones_ici else []
	details = []
	n = 0
	if danger >= 4:
		n += 2
	elif danger >= 2:
		n += 1
	if len(especes) >= 6:
		n += 1
	if especes:
		details.append(f"{len(especes)} espèce(s) rôdent")
	rayon_d = _int(conf.get("rayon_donjon"), 6)
	donjons = [l for l in relies or [] if l.get("categorie") in (conf.get("categories_donjon") or [])
			   and distance(l["pos"], pos) <= rayon_d]
	if donjons:
		n += 1
		details.append("un donjon proche")
	fiche["danger"] = {"note": min(3, n), "details": details}
	mots_axe = conf.get("mots_axe") or {}
	for axe, bloc in fiche.items():
		libelles = mots_axe.get(axe) or []
		bloc["mots"] = libelles[bloc["note"]] if bloc["note"] < len(libelles) else ""
	return fiche


def facteur_axe(site: dict, axe, reg: dict) -> float:
	facteurs = (reg.get("site") or {}).get("facteur_axe") or [1.0]
	note = _int(((site or {}).get(axe) or {}).get("note"))
	return _num(facteurs[min(note, len(facteurs) - 1)], 1.0)


def especes_du_site(pays_doc: dict, position) -> list:
	from utils import zones
	zones_ici = {p["zone"] for p in placements_actifs(pays_doc, position)}
	return sorted(zones.especes_rencontrables(pays_doc, zones_ici)) if zones_ici else []


# ── Lieux modèles (§ 12.1, § 12.2, § 12.5) ───────────────────────────────────────────

def _tags_milieu(modele: dict, reg: dict) -> set:
	"""Tags d'un modèle qui disent son milieu ou son pays : tout sauf `modele_colonie` et
	les ids de palier. Aucun ⇒ modèle GÉNÉRIQUE."""
	hors = {TAG_MODELE} | {p.get("id") for p in paliers(reg)}
	return {t for t in (modele or {}).get("tags") or [] if t not in hors}


def modele_generique(modele: dict, reg: dict) -> bool:
	return not _tags_milieu(modele, reg)


def modeles_proposes(modeles: list, palier_id, tags_ref: list, pays_id, reg: dict) -> list:
	"""Modèles du palier, dans l'ordre de présentation : meilleur recouvrement de tags en
	tête, générique en dernier. S'il existe des modèles PROPRES au pays (`pays_<slug>`),
	seuls ceux-là sont proposés — le générique toujours en plus. Chaque entrée :
	`{"modele": doc, "partages": [tags], "generique": bool}`."""
	du_palier = [m for m in modeles or []
				 if TAG_MODELE in (m.get("tags") or []) and palier_id in (m.get("tags") or [])]
	tag_pays = PREFIXE_TAG_PAYS + slug_pays(pays_id)
	generiques = [m for m in du_palier if modele_generique(m, reg)]
	autres = [m for m in du_palier if not modele_generique(m, reg)]
	du_pays = [m for m in autres if tag_pays in (m.get("tags") or [])]
	if du_pays:
		autres = du_pays
	else:
		# un modèle réservé à d'AUTRES pays ne se propose pas ici
		autres = [m for m in autres if not any(t.startswith(PREFIXE_TAG_PAYS) for t in m.get("tags") or [])]
	ref = set(tags_ref or [])
	classes = sorted(autres, key=lambda m: (-len(_tags_milieu(m, reg) & ref), str(m.get("_id"))))
	return ([{"modele": m, "partages": sorted(_tags_milieu(m, reg) & ref), "generique": False} for m in classes]
			+ [{"modele": m, "partages": [], "generique": True}
			   for m in sorted(generiques, key=lambda m: str(m.get("_id")))])


def entrees_de(lieu_doc: dict) -> list:
	"""Cases d'entrée `[[x, y], …]` (une à quatre, § 12.6) du lieu — lues sur son modèle."""
	return [[_int(e[0]), _int(e[1])] for e in (lieu_doc or {}).get("entrees") or []
			if isinstance(e, (list, tuple)) and len(e) >= 2][:4]


def modele_valide(modele: dict) -> bool:
	"""Un modèle se joue : une grille, des dimensions, au moins une entrée marchable."""
	e = entrees_de(modele)
	return bool((modele or {}).get("cells") and (modele or {}).get("dimensions") and e
				and all(case_marchable(modele, x, y) for x, y in e))


# ── Fonder (§ 2) ─────────────────────────────────────────────────────────────────────

def nettoyer_nom(nom) -> str:
	"""Borne le nom saisi (Convention § 9 : on borne ici, on échappe au rendu)."""
	return " ".join(str(nom or "").split())[:40]


def creer_implantation(character: dict, pays_doc: dict, position, modele: dict, reg: dict,
					   nom=None, espece=None, now: int | None = None) -> dict:
	"""Doc `implantation:*` neuf, au premier palier. Le nom du fondateur est DÉNORMALISÉ (un
	visiteur ne relit pas le `character:*` d'autrui)."""
	now = now_epoch() if now is None else now
	premier = (paliers(reg) or [{}])[0]
	qui = proprietes.nom_personnage(character)
	ident = uuid.uuid4().hex[:12]
	imp = {
		"_id": f"{TYPE_DOC}:{ident}",
		"type": TYPE_DOC,
		"categorie": CATEGORIE,
		"label": nettoyer_nom(nom) or f"{premier.get('label', 'Campement')} de {qui}",
		"lieu_parent": (pays_doc or {}).get("_id"),
		"origine": {"lieu": (pays_doc or {}).get("_id"), "pos": _xy(position)},
		"lien": f"link:{TYPE_DOC}_{ident}",
		"fondateur": character.get("_id"),
		"fondateur_nom": qui,
		"fondee_at": now,
		"palier": premier.get("id"),
		"modele": (modele or {}).get("_id"),
		"stocks": {s: _num((reg.get("stocks_depart") or {}).get(s)) for s in reg.get("stocks") or []},
		"population": 0,
		"feu": "grand",
		"batiments": [],
		"fortifications": [],
		"employes": [],
		"souffrants": 0,
		"menace": {"espece": espece, "etape": 1 if espece else 0},
		"attaques": [],
		"morts": [],
		"rattrape_at": now,
		"journal": [],
		"soutiens": {},
		"associes": [],
		"demandes": [],
	}
	noter_rang(imp, character)
	return imp


def creer_lien(imp: dict, entree) -> dict:
	"""Connexion case du pays ↔ implantation ; on y arrive par la PREMIÈRE entrée (§ 12.6)."""
	origine = imp.get("origine") or {}
	return {
		"_id": imp["lien"],
		"type": "connection",
		"nodes": [
			{"lieu": origine.get("lieu"), "pos": list(origine.get("pos") or [0, 0])},
			{"lieu": imp["_id"], "pos": _xy(entree)},
		],
		"metadata": {"type": CATEGORIE, "status": "ouvert"},
	}


def inscrire(character: dict, imp: dict) -> None:
	liste = character.setdefault("implantations", [])
	if imp["_id"] not in liste:
		liste.append(imp["_id"])


def noter_rang(imp: dict, fondateur: dict) -> None:
	"""Réputation du fondateur (§ 5, moral) : son meilleur rang, relevé à SON passage."""
	rangs = [RANGS.index(r) for r in ((fondateur or {}).get("rangs_guilde") or {}).values() if r in RANGS]
	imp["fondateur_rang"] = RANGS[max(rangs)] if rangs else None


# ── Rôles (§ 10) ─────────────────────────────────────────────────────────────────────

def role_de(character: dict, imp: dict) -> str:
	cid = (character or {}).get("_id")
	if cid and imp.get("fondateur") == cid:
		return FONDATEUR
	if any(a.get("id") == cid for a in imp.get("associes") or []):
		return ASSOCIE
	if cid in (imp.get("soutiens") or {}):
		return SOUTIEN
	return VISITEUR


def vaut_presence(role: str) -> bool:
	"""Le fondateur et l'associé déclenchent le rattrapage du temps écoulé (§ 10)."""
	return role in (FONDATEUR, ASSOCIE)


def places_associes(imp: dict, reg: dict) -> int:
	return _int(((reg.get("autres_joueurs") or {}).get("associes_max") or {}).get(imp.get("palier")))


def peut_demander(character: dict, imp: dict, reg: dict) -> tuple[bool, str]:
	role = role_de(character, imp)
	if role == FONDATEUR:
		return False, "C'est votre implantation."
	if role == ASSOCIE:
		return False, "Vous êtes déjà associé à ce lieu."
	if character.get("association"):
		return False, "Vous êtes déjà associé à une autre implantation."
	if any(d.get("id") == character.get("_id") for d in imp.get("demandes") or []):
		return False, "Votre demande attend déjà la réponse du fondateur."
	if character.get("demande_association"):
		return False, "Vous avez déjà une demande en attente ailleurs."
	if len(imp.get("associes") or []) >= places_associes(imp, reg):
		return False, "Ce lieu n'a plus de place d'associé à ce palier."
	return True, ""


def demander(character: dict, imp: dict, texte, now: int | None = None) -> None:
	"""Demande ÉCRITE d'association : elle attend le fondateur (tout est asynchrone, § 10)."""
	now = now_epoch() if now is None else now
	qui = proprietes.nom_personnage(character)
	imp.setdefault("demandes", []).append(
		{"id": character.get("_id"), "nom": qui, "texte": " ".join(str(texte or "").split())[:300], "at": now})
	character["demande_association"] = imp.get("_id")
	noter(imp, f"{qui} demande à s'associer.", now)


def repondre(imp: dict, reg: dict, demandeur_id, accepter: bool, now: int | None = None) -> tuple[bool, str, dict | None]:
	"""Le fondateur tranche une demande. (ok, raison, demande). L'acceptation n'écrit QUE le
	doc du lieu : le personnage de l'associé pose son `association` à son prochain passage
	(`synchroniser_association`) — on ne mute jamais le `character:*` d'autrui."""
	now = now_epoch() if now is None else now
	demande = next((d for d in imp.get("demandes") or [] if d.get("id") == demandeur_id), None)
	if demande is None:
		return False, "Cette demande n'existe plus.", None
	if accepter and len(imp.get("associes") or []) >= places_associes(imp, reg):
		return False, "Toutes les places d'associés de ce palier sont prises.", demande
	imp["demandes"] = [d for d in imp["demandes"] if d.get("id") != demandeur_id]
	if accepter:
		imp.setdefault("associes", []).append(
			{"id": demandeur_id, "nom": demande.get("nom", ""), "depuis": now, "apports": {}})
		noter(imp, f"{demande.get('nom', '')} devient associé.", now)
	else:
		noter(imp, f"La demande de {demande.get('nom', '')} est refusée.", now)
	return True, "", demande


def retirer_associe(imp: dict, associe_id, exclu: bool, now: int | None = None) -> bool:
	"""Départ volontaire ou exclusion : les apports restent au lieu (§ 10)."""
	associe = next((a for a in imp.get("associes") or [] if a.get("id") == associe_id), None)
	if associe is None:
		return False
	imp["associes"] = [a for a in imp["associes"] if a.get("id") != associe_id]
	noter(imp, f"{associe.get('nom', '')} {'est exclu' if exclu else 'quitte'} l'association.", now)
	return True


def synchroniser_association(character: dict, get_doc_fn) -> bool:
	"""Les champs `association` / `demande_association` du personnage suivent le doc du LIEU,
	qui fait foi : demande acceptée ⇒ association posée ; refusée ⇒ demande effacée ; exclu
	⇒ association retirée. Paresseux (passage par `/play` ou le panneau). True si le
	personnage a changé."""
	change = False
	demande = character.get("demande_association")
	if demande:
		imp = get_doc_fn(demande) or {}
		if role_de(character, imp) == ASSOCIE:
			character["association"] = demande
		if role_de(character, imp) == ASSOCIE \
				or not any(d.get("id") == character.get("_id") for d in imp.get("demandes") or []):
			character.pop("demande_association", None)
			change = True
	actuelle = character.get("association")
	if actuelle and role_de(character, get_doc_fn(actuelle) or {}) != ASSOCIE:
		character.pop("association", None)
		change = True
	return change


# ── Journal (le carnet du fondateur) ─────────────────────────────────────────────────

def noter(imp: dict, texte: str, now: int | None = None) -> None:
	now = now_epoch() if now is None else now
	journal = imp.setdefault("journal", [])
	journal.append({"at": now, "texte": texte})
	del journal[:-JOURNAL_MAX]


# ── Bâtiments (§ 8, § 12.4) ──────────────────────────────────────────────────────────

def batiment_def(reg: dict, type_id) -> dict | None:
	return _par_id(reg.get("batiments_def"), type_id)


def batiment(imp: dict, bid) -> dict | None:
	return _par_id(imp.get("batiments"), bid)


def logements(imp: dict, reg: dict) -> int:
	return _int(reg.get("logements_base")) + sum(
		_int((batiment_def(reg, b.get("type")) or {}).get("logements"))
		for b in imp.get("batiments") or [] if not b.get("endommage"))


def stockage(imp: dict, reg: dict) -> int:
	"""Capacité de CHAQUE stock : la base, plus les entrepôts — qui grandissent avec le palier."""
	rang = rang_palier(reg, imp.get("palier")) + 1
	return _int(reg.get("stockage_base")) + rang * sum(
		_int((batiment_def(reg, b.get("type")) or {}).get("stockage"))
		for b in imp.get("batiments") or [] if not b.get("endommage"))


def _payer_stocks(imp: dict, definition: dict) -> None:
	for s in ("bois", "materiaux"):
		imp["stocks"][s] = _num(imp["stocks"].get(s)) - _int(definition.get(s))


def _stocks_suffisants(imp: dict, definition: dict) -> str:
	for s in ("bois", "materiaux"):
		if _num((imp.get("stocks") or {}).get(s)) < _int(definition.get(s)):
			return f"Il manque du stock : {_int(definition.get(s))} de {s} requis."
	return ""


def categories_possibles(reg: dict, type_id, disponibles) -> list:
	"""Métiers qu'un sous-lieu peut tenir : sa `categorie` fixe, ou ceux de ses `familles`
	d'enseigne (`enseignes_icones.METIERS`, relu) parmi `disponibles` (catégories dont le
	marchand générique `pnj:marchand_<cat>` existe). Ni grande maison ni négociant."""
	from models import character_stats
	from utils import enseignes_icones
	bdef = batiment_def(reg, type_id) or {}
	if bdef.get("categorie"):
		return [bdef["categorie"]]
	familles = set(bdef.get("familles") or [])
	grandes = set(character_stats.LIEU_CATEGORIES_FUSION or {})
	return sorted(c for c, (famille, _i, _l) in enseignes_icones.METIERS.items()
				  if famille in familles and c in set(disponibles or ()) and c not in grandes
				  and c not in ("auberge", "etable") and c not in character_stats.CATEGORIES_NEGOCE)


def libelle_metier(categorie) -> str:
	"""« Boulangerie » pour `boulangerie` (libellé d'enseigne relu, article retiré)."""
	from utils import enseignes_icones
	brut = (enseignes_icones.METIERS.get(categorie) or (None, None, str(categorie or "").replace("_", " ")))[2]
	for article in ("une ", "un ", "des ", "l'"):
		if brut.startswith(article):
			brut = brut[len(article):]
	return brut[:1].upper() + brut[1:]


def peut_construire(imp: dict, reg: dict, type_id, categorie=None, disponibles=()) -> tuple[bool, str]:
	bdef = batiment_def(reg, type_id)
	if not bdef:
		return False, "Bâtiment inconnu."
	if bdef.get("nature") not in NATURES_OUVERTES:
		return False, "Ce bâtiment ne se construit pas encore."
	if not palier_atteint(reg, imp.get("palier"), bdef.get("palier_min")):
		p = palier_def(reg, bdef.get("palier_min")) or {}
		return False, f"Ce bâtiment s'ouvre au palier {p.get('label', bdef.get('palier_min'))}."
	if bdef.get("familles") and categorie is not None \
			and categorie not in categories_possibles(reg, type_id, disponibles):
		return False, "Ce métier ne peut pas s'y tenir."
	manque = _stocks_suffisants(imp, bdef)
	return (False, manque) if manque else (True, "")


def construire(imp: dict, reg: dict, type_id, now: int | None = None, categorie=None) -> dict:
	"""Déclenche l'aménagement (réservé au fondateur, § 12.8) : le bâtiment naît SANS case,
	à poser ensuite par le geste « Poser ici » — du fondateur ou d'un associé. Un sous-lieu
	garde le métier choisi (`categorie`)."""
	bdef = batiment_def(reg, type_id) or {}
	_payer_stocks(imp, bdef)
	b = {"id": f"b_{uuid.uuid4().hex[:8]}", "type": type_id, "pos": None}
	if bdef.get("nature") == SOUS_LIEU:
		b["categorie"] = bdef.get("categorie") or categorie
	imp.setdefault("batiments", []).append(b)
	noter(imp, f"Construction : {bdef.get('label', type_id)}"
			   + (f" ({libelle_metier(b['categorie'])})" if b.get("categorie") and bdef.get("familles") else "") + ".", now)
	return b


# ── Sous-lieux : où l'on entre (§ 12.4) ──────────────────────────────────────────────

def est_sous_lieu(lieu_doc: dict | None) -> bool:
	return bool((lieu_doc or {}).get("colonie")) and str((lieu_doc or {}).get("_id", "")).startswith(PREFIXE_SOUS_LIEU)


def creer_sous_lieu(imp: dict, b: dict, reg: dict, image: str) -> tuple[dict, dict]:
	"""À la PREMIÈRE pose d'un sous-lieu : son `lieu:colonie_*` (forme d'une boutique de cité :
	`categorie`, stocks, `lieu_parent` = l'implantation, qui EST sa cité) et la connexion qui
	part de sa case. Les poses suivantes ne déplacent que le nœud (`deplacer_sous_lieu`)."""
	bdef = batiment_def(reg, b.get("type")) or {}
	ident = uuid.uuid4().hex[:12]
	cat = b.get("categorie") or bdef.get("categorie")
	lieu = {"_id": f"{PREFIXE_SOUS_LIEU}{ident}", "type": "lieu",
			"label": f"{libelle_metier(cat) if bdef.get('familles') else bdef.get('label', '')} de {imp.get('label', '')}",
			"image": image, "categorie": cat, "lieu_parent": imp["_id"], "colonie": imp["_id"],
			"batiment": b["id"], "pnj": [], "stock_matieres": {}, "stock_vente": []}
	lien = {"_id": f"link:colonie_{ident}", "type": "connection",
			"nodes": [{"lieu": imp["_id"], "pos": list(b["pos"])}, {"lieu": lieu["_id"], "pos": [0, 0]}],
			"metadata": {"type": cat, "status": "ouvert"}}
	b["lieu"], b["lien"] = lieu["_id"], lien["_id"]
	return lieu, lien


def deplacer_sous_lieu(lien: dict, imp_id, pos) -> bool:
	"""Le nœud de la connexion suit le bâtiment (déplacement, changement de palier)."""
	for n in (lien or {}).get("nodes") or []:
		if n.get("lieu") == imp_id:
			if pos is None:
				return False
			n["pos"] = list(pos)
			return True
	return False


def tenancier(imp: dict, reg: dict, employes: list, bid) -> dict | None:
	"""Le PNJ nommé au poste du sous-lieu : sans lui, il est fermé (§ 8 : la fonction s'arrête)."""
	return next((e for e in au_poste(imp, reg, employes) if e.get("poste") == bid), None)


def pnj_du_sous_lieu(lieu: dict, e: dict | None, reg: dict) -> list:
	"""L'entrée `pnj` du sous-lieu : le marchand générique du métier, sous le nom et le visage du
	PNJ nommé. L'auberge n'en porte pas (aucun aubergiste générique) ; l'étable vend ses montures."""
	cat = lieu.get("categorie")
	if not e or cat == "auberge":
		return []
	entree = {"character": f"pnj:marchand_{cat}", "nom": proprietes.nom_personnage(e), "portrait": e.get("portrait", "")}
	if cat == "etable":
		entree["montures"] = list(reg.get("montures_etable") or [])
	return [entree]


def synchroniser_tenanciers(imp: dict, reg: dict, employes: list, get_doc_fn) -> list:
	"""Remet l'entrée `pnj` de chaque sous-lieu d'accord avec son poste ; rend les docs changés
	(l'appelant sauve). Appelé après embauche, renvoi et rattrapage (morts, départs)."""
	out = []
	for b in imp.get("batiments") or []:
		if not b.get("lieu"):
			continue
		lieu = get_doc_fn(b["lieu"])
		if not lieu:
			continue
		voulu = pnj_du_sous_lieu(lieu, tenancier(imp, reg, employes, b["id"]), reg)
		if lieu.get("pnj") != voulu:
			lieu["pnj"] = voulu
			out.append(lieu)
	return out


def sous_lieu_ouvert(lieu_doc: dict, get_doc_fn) -> tuple[bool, str]:
	"""Garde d'ENTRÉE (`move_character`) : un sous-lieu sans PNJ au poste est fermé, comme un
	bâtiment endommagé."""
	if not est_sous_lieu(lieu_doc):
		return True, ""
	imp = get_doc_fn(lieu_doc["colonie"]) or {}
	reg = regles(get_doc_fn)
	b = batiment(imp, lieu_doc.get("batiment"))
	if not b:
		return False, "Ce bâtiment n'existe plus."
	if b.get("endommage"):
		return False, "Ce bâtiment est endommagé : il attend sa réparation."
	if not tenancier(imp, reg, employes_effectifs(imp, get_doc_fn), b["id"]):
		return False, "Personne n'y tient le comptoir : c'est fermé."
	return True, ""


def peut_poser(imp: dict, bid, position) -> tuple[bool, str]:
	"""Pose libre (§ 12.4) : toute case marchable et libre, hors entrées ; un bâtiment par case."""
	b = batiment(imp, bid)
	if not b:
		return False, "Ce bâtiment n'existe pas."
	pos = _xy(position)
	if not case_marchable(imp, pos[0], pos[1]):
		return False, "On ne bâtit pas sur cette case."
	if pos in entrees_de(imp):
		return False, "Rien ne se pose sur une entrée."
	if any(o.get("pos") == pos and o.get("id") != bid for o in imp.get("batiments") or []):
		return False, "Cette case est déjà prise."
	return True, ""


def poser(imp: dict, bid, position) -> None:
	batiment(imp, bid)["pos"] = _xy(position)


def peut_agir_sur_carte(role: str) -> bool:
	"""Poser, déplacer : le fondateur, et l'associé une fois l'aménagement déclenché (§ 12.8)."""
	return role in (FONDATEUR, ASSOCIE)


def reparer(imp: dict, reg: dict, bid, now: int | None = None) -> tuple[bool, str]:
	b = batiment(imp, bid)
	if not b or not b.get("endommage"):
		return False, "Ce bâtiment n'a pas besoin de réparation."
	cout = _int(reg.get("reparation_materiaux"))
	if _num(imp["stocks"].get("materiaux")) < cout:
		return False, f"Il faut {cout} de matériaux pour réparer."
	imp["stocks"]["materiaux"] = _num(imp["stocks"].get("materiaux")) - cout
	b.pop("endommage", None)
	noter(imp, f"Réparation : {(batiment_def(reg, b.get('type')) or {}).get('label', '')}.", now)
	return True, ""


def case_libre_proche(lieu_doc: dict, cible, prises: set) -> list | None:
	"""La case marchable, hors entrées et hors `prises`, la plus proche de `cible` (anneaux
	de Chebyshev, ordre de lecture dans l'anneau : déterministe)."""
	cells = (lieu_doc or {}).get("cells") or []
	if not cells:
		return None
	interdites = {tuple(e) for e in entrees_de(lieu_doc)} | set(prises)
	cx, cy = _xy(cible)
	for r in range(0, max(len(cells), len(cells[0]))):
		for y in range(cy - r, cy + r + 1):
			for x in range(cx - r, cx + r + 1):
				if max(abs(x - cx), abs(y - cy)) == r and (x, y) not in interdites \
						and case_marchable(lieu_doc, x, y):
					return [x, y]
	return None


def replacer_batiments(imp: dict, anciennes_dims: dict, nouveau_lieu: dict) -> None:
	"""Changement de palier (§ 12.5) : chaque bâtiment est replacé SEUL — même position
	relative sur la nouvelle grille, case libre la plus proche. Sans place, il redevient « à
	poser »."""
	cells = (nouveau_lieu or {}).get("cells") or [[]]
	aw, ah = max(1, _int((anciennes_dims or {}).get("x"), 1)), max(1, _int((anciennes_dims or {}).get("y"), 1))
	nw, nh = len(cells[0]), len(cells)
	prises = set()
	for b in imp.get("batiments") or []:
		if not b.get("pos"):
			continue
		cible = [round(b["pos"][0] * (nw - 1) / max(1, aw - 1)), round(b["pos"][1] * (nh - 1) / max(1, ah - 1))]
		pos = case_libre_proche(nouveau_lieu, cible, prises)
		b["pos"] = pos
		if pos:
			prises.add(tuple(pos))


def reperes_carte(imp: dict, reg: dict) -> list:
	"""Marqueurs des bâtiments POSÉS, au format des passages de `/play` (`lieux.passages_carte`) :
	pictogramme et halo des repères (§ 12.4). `link_id` absent : on n'y entre pas."""
	out = []
	for b in imp.get("batiments") or []:
		bdef = batiment_def(reg, b.get("type")) or {}
		if not b.get("pos") or bdef.get("nature") != REPERE:
			continue
		out.append({"x": b["pos"][0], "y": b["pos"][1], "link_id": None, "type": REPERE,
					"label": bdef.get("label", "") + (" (endommagé)" if b.get("endommage") else ""),
					"categorie": None, "famille": REPERE, "rgb": RGB_REPERE,
					"icone": bdef.get("icone"), "metier": None, "batiment": b["id"]})
	return out


# ── Fortifications et chantiers (§ 4, § 10 « Financer ») ─────────────────────────────

def fortification_def(reg: dict, fid) -> dict | None:
	return _par_id(reg.get("fortifications"), fid)


def fortification_requise(reg: dict, palier_id) -> dict | None:
	"""La fortification minimale qu'exige le palier À ATTEINDRE."""
	return next((f for f in reg.get("fortifications") or [] if f.get("requis_pour") == palier_id), None)


def conditions_palier(imp: dict, reg: dict, employes: list) -> dict | None:
	"""Seuils du palier suivant (§ 4) : `{palier, conditions: [{label, valeur, cible, ok}],
	pret, prix}` ; None au dernier palier."""
	suivant = palier_suivant(reg, imp.get("palier"))
	if not suivant:
		return None
	fortif = fortification_requise(reg, suivant.get("id"))
	conds = [
		{"label": "Population", "valeur": _int(imp.get("population")), "cible": _int(suivant.get("population_min"))},
		{"label": "Postes nommés tenus", "valeur": len(employes or []), "cible": _int(suivant.get("postes_min"))},
	]
	for c in conds:
		c["ok"] = c["valeur"] >= c["cible"]
	if fortif:
		conds.append({"label": fortif.get("label", ""), "valeur": None, "cible": None,
					  "ok": fortif.get("id") in (imp.get("fortifications") or [])})
	return {"palier": suivant, "conditions": conds, "pret": all(c["ok"] for c in conds),
			"prix": _int(suivant.get("prix_statut_cuivre"))}


CHANTIER_STATUT = "statut"
CHANTIER_FORTIFICATION = "fortification"


def peut_ouvrir_chantier(imp: dict, reg: dict, employes: list, genre, objet=None) -> tuple[bool, str, dict | None]:
	"""Un seul chantier à la fois. (ok, raison, chantier prêt à poser)."""
	if imp.get("chantier"):
		return False, "Un chantier est déjà ouvert.", None
	if genre == CHANTIER_STATUT:
		c = conditions_palier(imp, reg, employes)
		if not c:
			return False, "Le lieu a atteint son dernier palier.", None
		if not c["pret"]:
			return False, "Les seuils du palier suivant ne sont pas atteints.", None
		return True, "", {"genre": genre, "objet": c["palier"]["id"], "label": f"Statut de {c['palier'].get('label', '')}",
						  "cout": c["prix"], "verse": 0, "parts": {}}
	fdef = fortification_def(reg, objet)
	if genre != CHANTIER_FORTIFICATION or not fdef:
		return False, "Chantier inconnu.", None
	if objet in (imp.get("fortifications") or []):
		return False, "Cette défense est déjà en place.", None
	if not palier_atteint(reg, imp.get("palier"), fdef.get("palier_min")):
		return False, "Cette défense n'est pas à la portée de ce palier.", None
	manque = _stocks_suffisants(imp, fdef)
	if manque:
		return False, manque, None
	return True, "", {"genre": genre, "objet": objet, "label": fdef.get("label", ""),
					  "cout": _int(fdef.get("prix_cuivre")), "verse": 0, "parts": {}}


def ouvrir_chantier(imp: dict, reg: dict, chantier: dict, now: int | None = None) -> None:
	"""Le bois et les matériaux d'une fortification partent à l'OUVERTURE ; l'argent se
	verse ensuite, par le fondateur et ses associés."""
	if chantier["genre"] == CHANTIER_FORTIFICATION:
		_payer_stocks(imp, fortification_def(reg, chantier["objet"]) or {})
	imp["chantier"] = chantier
	noter(imp, f"Chantier ouvert : {chantier['label']}.", now)


def reste_chantier(imp: dict) -> int:
	c = imp.get("chantier") or {}
	return max(0, _int(c.get("cout")) - _int(c.get("verse")))


def financer(imp: dict, payeur: dict, montant: int, now: int | None = None) -> int:
	"""Verse au chantier ouvert, au plus ce qu'il reste à payer. Renvoie le montant retenu
	(l'appelant débite). Les parts sont notées, sans droit sur la caisse (§ 10)."""
	c = imp.get("chantier") or {}
	retenu = max(0, min(_int(montant), reste_chantier(imp)))
	if not retenu:
		return 0
	c["verse"] = _int(c.get("verse")) + retenu
	parts = c.setdefault("parts", {})
	parts[payeur.get("_id")] = _int(parts.get(payeur.get("_id"))) + retenu
	_compter_apport(imp, payeur, "cuivre", retenu)
	noter(imp, f"{proprietes.nom_personnage(payeur)} verse {retenu} cu au chantier « {c.get('label', '')} ».", now)
	return retenu


def chantier_pret(imp: dict) -> bool:
	return bool(imp.get("chantier")) and reste_chantier(imp) == 0


def achever_fortification(imp: dict, now: int | None = None) -> bool:
	"""Chantier de fortification entièrement financé : la défense est en place."""
	c = imp.get("chantier") or {}
	if c.get("genre") != CHANTIER_FORTIFICATION or not chantier_pret(imp):
		return False
	imp.setdefault("fortifications", []).append(c["objet"])
	imp.pop("chantier", None)
	noter(imp, f"Achevé : {c.get('label', '')}.", now)
	return True


def changer_palier(imp: dict, reg: dict, modele: dict, anciennes_dims: dict, now: int | None = None) -> bool:
	"""Chantier de statut financé + modèle choisi (§ 12.5) : nouveau palier, nouveau modèle,
	bâtiments replacés. ⚠️ L'appelant met à jour le nœud du lien (`entrees_de(modele)[0]`)."""
	c = imp.get("chantier") or {}
	if c.get("genre") != CHANTIER_STATUT or not chantier_pret(imp):
		return False
	imp["palier"] = c["objet"]
	imp["modele"] = modele.get("_id")
	replacer_batiments(imp, anciennes_dims, modele)
	imp.pop("chantier", None)
	noter(imp, f"Le lieu devient {(palier_def(reg, imp['palier']) or {}).get('label', imp['palier'])}.", now)
	return True


# ── Personnel nommé (§ 8) ────────────────────────────────────────────────────────────

def metiers(reg: dict, cat_proprietes: dict) -> list:
	"""Métiers des propriétés urbaines PLUS ceux de la colonisation (§ 8), sans doublon."""
	propres = list(reg.get("metiers_def") or [])
	ids = {m.get("id") for m in propres}
	return propres + [m for m in (cat_proprietes or {}).get("metiers") or [] if m.get("id") not in ids]


def metier_def(reg: dict, cat_proprietes: dict, metier_id) -> dict | None:
	return _par_id(metiers(reg, cat_proprietes), metier_id)


def employes_effectifs(imp: dict, get_doc_fn) -> list:
	return proprietes.employes_effectifs(imp, get_doc_fn)


def postes(imp: dict, reg: dict) -> list:
	"""`[(batiment_id, metier, places)]` des bâtiments posés ou non, hors endommagés."""
	out = []
	for b in imp.get("batiments") or []:
		if b.get("endommage"):
			continue
		for metier, n in ((batiment_def(reg, b.get("type")) or {}).get("postes") or {}).items():
			if _int(n) > 0:
				out.append((b["id"], metier, _int(n)))
	return out


def postes_libres(imp: dict, reg: dict, employes: list) -> list:
	out = []
	for bid, metier, places in postes(imp, reg):
		pris = sum(1 for e in employes or [] if e.get("poste") == bid and e.get("metier") == metier)
		if places - pris > 0:
			out.append({"amenagement": bid, "metier": metier, "libres": places - pris})
	return out


def au_poste(imp: dict, reg: dict, employes: list) -> list:
	"""Employés dont le poste est debout : un bâtiment endommagé arrête ses PNJ."""
	debout = {b["id"] for b in imp.get("batiments") or [] if not b.get("endommage")}
	return [e for e in employes or [] if e.get("poste") in debout]


def _du_role(imp: dict, reg: dict, employes: list, role: str) -> list:
	ids = (reg.get("metiers_roles") or {}).get(role) or []
	return [e for e in au_poste(imp, reg, employes) if e.get("metier") in ids]


def _cat_embauche(imp: dict, reg: dict, cat_proprietes: dict) -> dict:
	"""Catalogue à la forme qu'attend `proprietes._candidats_pour` : un « aménagement » par
	bâtiment de l'implantation."""
	return {"metiers": metiers(reg, cat_proprietes),
			"amenagements": [{"id": b["id"], "nom": (batiment_def(reg, b.get("type")) or {}).get("label", ""),
							  "activite": (batiment_def(reg, b.get("type")) or {}).get("activite")}
							 for b in imp.get("batiments") or []]}


def rafraichir_candidats(imp: dict, reg: dict, cat_proprietes: dict, employes: list, get_doc_fn,
						 portraits=None, portraits_personnel=(), now: int | None = None, rand=random) -> bool:
	"""Tableau d'embauche, péremption PARESSEUSE (même règle que celui d'une propriété) : un
	candidat par poste libre ; tableau encore valide ⇒ postes pourvus retirés, postes neufs
	complétés sans re-tirer les autres. True si le doc a changé."""
	now = now_epoch() if now is None else now
	cat = _cat_embauche(imp, reg, cat_proprietes)
	libres = postes_libres(imp, reg, employes)
	pris = {e.get("portrait") for e in employes or []}
	if imp.get("candidats") is not None and _int(imp.get("candidats_expire_at")) > now:
		cles = {(p["amenagement"], p["metier"]) for p in libres}
		gardes = [c for c in imp["candidats"] if (c.get("amenagement"), c.get("metier")) in cles]
		couverts = {(c.get("amenagement"), c.get("metier")) for c in gardes}
		gardes += proprietes._candidats_pour(
			[p for p in libres if (p["amenagement"], p["metier"]) not in couverts], cat, get_doc_fn,
			portraits, rand, 1, portraits_personnel, pris | {c.get("portrait") for c in gardes})
		if gardes == imp["candidats"]:
			return False
		imp["candidats"] = gardes
		return True
	imp["candidats"] = proprietes._candidats_pour(libres, cat, get_doc_fn, portraits, rand, 1,
												 portraits_personnel, pris)
	imp["candidats_expire_at"] = now + _int(reg.get("candidats_duree_s"), JOUR_S)
	return True


def peut_engager(imp: dict, reg: dict, employes: list, candidat: dict) -> tuple[bool, str]:
	if not any(p["amenagement"] == candidat.get("amenagement") and p["metier"] == candidat.get("metier")
			   for p in postes_libres(imp, reg, employes)):
		return False, "Ce poste n'est plus libre."
	return True, ""


def engager(imp: dict, candidat: dict, fondateur: dict, now: int | None = None) -> dict:
	"""Le PNJ NOMMÉ naît de ce geste (un `employe:*` attaché à ce lieu) ; il loge sur place."""
	employe = proprietes.creer_employe(imp, candidat, fondateur)
	proprietes.engager(imp, employe)
	proprietes.retirer_candidat(imp, candidat.get("id"))
	noter(imp, f"Engagé : {proprietes.nom_personnage(employe)}.", now)
	return employe


def renvoyer(imp: dict, employe: dict, now: int | None = None) -> None:
	proprietes.renvoyer(imp, employe)
	noter(imp, f"Renvoyé : {proprietes.nom_personnage(employe)}.", now)


# ── Stocks, dons, besoins (§ 7, § 10) ────────────────────────────────────────────────

def habitants(imp: dict, employes: list) -> int:
	"""Bouches à nourrir : la population comptée et les PNJ nommés."""
	return _int(imp.get("population")) + len(employes or [])


def stock_de_item(item: dict, filtres: list, reg: dict) -> dict | None:
	"""Règle de dépôt (`depots`) qui reconnaît cet objet, ou None : il ne se donne pas."""
	cles = set(filtres or [])
	for regle in reg.get("depots") or []:
		if cles & set(regle.get("filtres") or []) or (item or {}).get("sous_categorie") in (regle.get("sous_categories") or []):
			return regle
	return None


def unites_de_item(item: dict, regle: dict) -> float:
	poids = (item or {}).get("poids")
	if isinstance(poids, (list, tuple)):
		poids = sum(_num(p) for p in poids) / max(1, len(poids))
	return max(0.1, round(_num(poids) * _num(regle.get("unites_par_kg"), 1.0), 1))


def _compter_apport(imp: dict, donateur: dict, cle: str, quantite) -> None:
	"""Apports d'un associé (comptés) ou dons d'un autre (un premier don fait un SOUTIEN, § 10).
	Le fondateur ne se compte pas."""
	cid = (donateur or {}).get("_id")
	if not cid or cid == imp.get("fondateur"):
		return
	associe = next((a for a in imp.get("associes") or [] if a.get("id") == cid), None)
	if associe is not None:
		registre = associe.setdefault("apports", {})
	else:
		registre = imp.setdefault("soutiens", {}).setdefault(
			cid, {"nom": proprietes.nom_personnage(donateur), "dons": {}})["dons"]
	registre[cle] = round(_num(registre.get(cle)) + _num(quantite), 1)


def deposer(imp: dict, reg: dict, donateur: dict, stock: str, unites: float, nom_objet: str = "",
			now: int | None = None) -> float:
	"""Verse `unites` au stock, dans la limite de sa capacité. Renvoie ce qui est entré (le
	reste est PERDU pour le donateur : l'appelant refuse en amont un stock plein). Noté au
	carnet du fondateur quand un autre que lui donne (§ 10)."""
	place = max(0.0, stockage(imp, reg) - _num(imp["stocks"].get(stock)))
	entre = round(min(_num(unites), place), 1)
	imp["stocks"][stock] = round(_num(imp["stocks"].get(stock)) + entre, 1)
	_compter_apport(imp, donateur, stock, entre)
	if (donateur or {}).get("_id") != imp.get("fondateur"):
		libelle = (reg.get("stocks_labels") or {}).get(stock, stock)
		noter(imp, f"{proprietes.nom_personnage(donateur)} donne {nom_objet or libelle} ({libelle} +{entre}).", now)
	return entre


def seuils_stocks(imp: dict, reg: dict, employes: list) -> dict:
	"""Niveau sous lequel chaque stock est « bas » : `jours_reserve` jours d'avance."""
	c = reg.get("consommation") or {}
	jours = _num(c.get("jours_reserve"), 3)
	return {
		"nourriture": max(1.0, habitants(imp, employes) + 1) * _num(c.get("nourriture_par_habitant_jour"), 1) * jours,
		"bois": _num((c.get("bois_feu_jour") or {}).get(imp.get("feu"), 2)) * jours,
		"materiaux": _num(c.get("materiaux_seuil"), 5),
		"medicaments": _num(c.get("medicaments_seuil"), 2) + _int(imp.get("souffrants")),
	}


def besoins(imp: dict, reg: dict, employes: list) -> list:
	"""Tableau des besoins (§ 10) : DÉRIVÉ des stocks bas, sans récompense."""
	seuils = seuils_stocks(imp, reg, employes)
	labels = reg.get("stocks_labels") or {}
	return [{"stock": s, "label": labels.get(s, s)} for s in reg.get("stocks") or []
			if _num((imp.get("stocks") or {}).get(s)) < seuils.get(s, 0)]


def regler_feu(imp: dict, reg: dict, reglage, now: int | None = None) -> bool:
	if reglage not in (reg.get("feu") or []) or imp.get("feu") == reglage:
		return False
	imp["feu"] = reglage
	noter(imp, "Grand feu." if reglage == "grand" else "Feu réduit.", now)
	return True


# ── Sécurité et moral (§ 5) : dérivés, jamais stockés ────────────────────────────────

def _mot(echelle: list, valeur: float) -> str:
	return next((m for seuil, m in echelle or [] if valeur < seuil), "")


def securite(imp: dict, reg: dict, site: dict, employes: list) -> dict:
	"""`{valeur, mot, facteurs: [{id, valeur, max}]}` — cinq familles de 0 à 20 chacune,
	somme plafonnée sous le maximum."""
	conf = reg.get("securite") or {}
	physique = _num(conf.get("base_physique")) + sum(
		_num((fortification_def(reg, f) or {}).get("defense")) for f in imp.get("fortifications") or [])
	if imp.get("feu") == "grand":
		physique += _num(conf.get("feu_grand"))
	besoin = max(1, math.ceil(max(1, habitants(imp, employes)) / max(1, _int(conf.get("habitants_par_garde"), 8))))
	gardes = len(_du_role(imp, reg, employes, "gardes"))
	humaine = 20.0 * min(1.0, gardes / besoin)
	note = lambda axe: _int(((site or {}).get(axe) or {}).get("note"))
	environnement = 10 + (note("defense") - note("danger")) * 10 / 3
	seuils = seuils_stocks(imp, reg, employes)
	ratios = [min(1.0, _num((imp.get("stocks") or {}).get(s)) / seuils[s]) if seuils.get(s) else 1.0
			  for s in reg.get("stocks") or []]
	logistique = 20.0 * (sum(ratios) / len(ratios) if ratios else 1.0)
	etape = _int((imp.get("menace") or {}).get("etape"))
	table = conf.get("connaissance") or {}
	connaissance = _num(table.get(str(etape) if etape else "aucune"), 10)
	if etape and _du_role(imp, reg, employes, "pisteurs"):
		connaissance += _num(conf.get("bonus_pisteur"))
	facteurs = [("defense_physique", physique), ("defense_humaine", humaine), ("environnement", environnement),
				("logistique", logistique), ("connaissance_territoire", connaissance)]
	facteurs = [{"id": i, "valeur": round(max(0.0, min(20.0, v)), 1), "max": 20} for i, v in facteurs]
	valeur = min(_num(conf.get("plafond"), 95), sum(f["valeur"] for f in facteurs))
	return {"valeur": round(valeur, 1), "mot": _mot(conf.get("mots"), valeur), "facteurs": facteurs}


def moral(imp: dict, reg: dict, site: dict, employes: list, now: int | None = None, secu: dict | None = None) -> dict:
	"""`{valeur, mot, facteurs: [{id, valeur}]}` — la base, plus les facteurs du § 5."""
	now = now_epoch() if now is None else now
	conf = reg.get("moral") or {}
	c = reg.get("consommation") or {}
	secu = secu or securite(imp, reg, site, employes)
	bouches = max(1, habitants(imp, employes) + 1)
	jours = _num((imp.get("stocks") or {}).get("nourriture")) / (bouches * max(0.01, _num(c.get("nourriture_par_habitant_jour"), 1)))
	if _num((imp.get("stocks") or {}).get("nourriture")) <= 0:
		nourriture = _num(conf.get("nourriture_vide"))
	elif jours < 1:
		nourriture = _num(conf.get("nourriture_basse"))
	elif jours >= _num(c.get("jours_reserve"), 3):
		nourriture = _num(conf.get("nourriture_ok"))
	else:
		nourriture = 0.0
	depuis = now - _int(conf.get("fenetre_s"), 7 * JOUR_S)
	attaques = [a for a in imp.get("attaques") or [] if _int(a.get("at")) >= depuis and not a.get("repoussee")]
	morts = [m for m in imp.get("morts") or [] if _int(m) >= depuis]
	rang = imp.get("fondateur_rang")
	facteurs = [
		("nourriture", nourriture),
		("logement", _num(conf.get("loge")) if habitants(imp, employes) <= logements(imp, reg) else _num(conf.get("mal_loge"))),
		("soignant", _num(conf.get("soignant")) if _du_role(imp, reg, employes, "soignants") else 0.0),
		("attaques", max(_num(conf.get("attaque_min")), _num(conf.get("attaque")) * len(attaques))),
		("morts", max(_num(conf.get("mort_min")), _num(conf.get("mort")) * len(morts))),
		("prosperite", _num(conf.get("prosperite")) if not besoins(imp, reg, employes) else 0.0),
		("expeditions", _num(conf.get("expedition")) * _int(imp.get("expeditions_reussies"))),
		("reputation", _num(conf.get("reputation_par_rang")) * (RANGS.index(rang) if rang in RANGS else 0)),
		("feu", _num((conf.get("feu") or {}).get(imp.get("feu")))),
		("securite", (secu["valeur"] - 50) / max(1.0, _num(conf.get("securite_diviseur"), 5))),
	]
	valeur = max(0.0, min(100.0, _num(conf.get("base"), 50) + sum(v for _, v in facteurs)))
	return {"valeur": round(valeur, 1), "mot": _mot(conf.get("mots"), valeur),
			"facteurs": [{"id": i, "valeur": round(v, 1)} for i, v in facteurs]}


# ── Le temps : rattrapage PARESSEUX (§ 1, § 6, § 7, § 8) ─────────────────────────────

def passes_dues(imp: dict, reg: dict, now: int) -> int:
	"""Passes entières écoulées depuis `rattrape_at`, plafonnées à l'absence maximale (§ 6 :
	au-delà de 3 jours réels, le lieu se fige)."""
	pas = max(60, _int((reg.get("temps") or {}).get("passe_s"), 3600))
	plafond = _int((reg.get("reglages") or {}).get("rattrapage_max_s"), 3 * JOUR_S)
	depuis = _int(imp.get("rattrape_at"), now)
	return max(0, min(now - depuis, plafond)) // pas


def rattraper(imp: dict, reg: dict, site: dict, employes: list, now: int | None = None, rand=random) -> dict:
	"""Rejoue le temps écoulé, passe par passe : production, consommation, santé, population,
	menace. Mute `imp` et les docs `employes` touchés (morts, départs). Renvoie
	`{"passes", "evenements": [str], "employes_touches": [docs]}` ; l'appelant sauve.
	⚠️ `employes` est mis à jour en place : les morts et les partis en sortent."""
	now = now_epoch() if now is None else now
	pas = max(60, _int((reg.get("temps") or {}).get("passe_s"), 3600))
	n = passes_dues(imp, reg, now)
	bilan = {"passes": n, "evenements": [], "employes_touches": []}
	if "rattrape_at" not in imp:
		imp["rattrape_at"] = now
		return bilan
	# Attaque restée sans réponse : elle se résout comme en l'absence du fondateur (§ 6).
	attente = imp.get("attaque_en_cours")
	if attente and now - _int(attente.get("at")) >= _int((reg.get("menace") or {}).get("delai_defense_s"), 900):
		imp.pop("attaque_en_cours", None)
		_attaque(imp, reg, employes, _int(attente.get("at")), rand, bilan, securite(imp, reg, site, employes))
		bilan["evenements_attente"] = True
	if not n:
		for texte in bilan["evenements"]:
			noter(imp, texte, now)
		return bilan
	# Au-delà du plafond, le temps perdu l'est pour de bon : on ne rejoue que les dernières
	# passes. En deçà, le reliquat (moins d'une passe) reste dû au prochain passage.
	plafond = _int((reg.get("reglages") or {}).get("rattrapage_max_s"), 3 * JOUR_S)
	depuis = _int(imp.get("rattrape_at"))
	debut = depuis if now - depuis <= plafond else now - n * pas
	for i in range(n):
		_passe(imp, reg, site, employes, debut + (i + 1) * pas, pas, rand, bilan)
	imp["rattrape_at"] = debut + n * pas
	for texte in bilan["evenements"]:
		noter(imp, texte, now)
	return bilan


def _perdre_un(imp: dict, employes: list, rand, statut: str, bilan: dict) -> str:
	"""Un habitant de moins : un compté d'abord, sinon un PNJ NOMMÉ (définitif, § 8). Renvoie
	le nom du PNJ nommé perdu, ou ''."""
	if _int(imp.get("population")) > 0:
		imp["population"] = _int(imp["population"]) - 1
		return ""
	if not employes:
		return ""
	e = employes.pop(rand.randrange(len(employes)))
	e["statut"] = statut
	imp["employes"] = [x for x in imp.get("employes") or [] if x != e.get("_id")]
	bilan["employes_touches"].append(e)
	return proprietes.nom_personnage(e)


def _passe(imp: dict, reg: dict, site: dict, employes: list, instant: int, pas: int, rand, bilan: dict) -> None:
	part = pas / JOUR_S                     # fraction de jour que dure la passe
	stocks = imp.setdefault("stocks", {})
	capacite = stockage(imp, reg)
	actifs = au_poste(imp, reg, employes)
	c = reg.get("consommation") or {}

	# 1. Production des PNJ au poste, pondérée par le site.
	par_metier = {m.get("id"): m for m in reg.get("metiers_def") or []}
	for e in actifs:
		produit = (par_metier.get(e.get("metier")) or {}).get("produit")
		if not produit:
			continue
		if produit.get("exige_axe") and not _int(((site or {}).get(produit.get("axe")) or {}).get("note")):
			continue
		gain = _num(produit.get("par_jour")) * part * facteur_axe(site, produit.get("axe"), reg)
		s = produit.get("stock")
		stocks[s] = min(float(capacite), _num(stocks.get(s)) + gain)

	# 2. Consommation : bouches et feu.
	economie = _num(reg.get("intendant_economie")) if _du_role(imp, reg, employes, "intendants") else 0.0
	bouches = habitants(imp, employes) + 1
	stocks["nourriture"] = max(0.0, _num(stocks.get("nourriture"))
							   - bouches * _num(c.get("nourriture_par_habitant_jour"), 1) * part * (1 - economie))
	stocks["bois"] = max(0.0, _num(stocks.get("bois")) - _num((c.get("bois_feu_jour") or {}).get(imp.get("feu"), 2)) * part)
	if _num(stocks.get("bois")) <= 0 and imp.get("feu") == "grand":
		imp["feu"] = "reduit"                       # plus de bois : le grand feu ne tient pas
		bilan["evenements"].append("Faute de bois, le grand feu est tombé.")

	# 3. Réparations : un bâtisseur relève un bâtiment endommagé par jour.
	if _du_role(imp, reg, employes, "batisseurs") and rand.random() < part:
		abime = next((b for b in imp.get("batiments") or [] if b.get("endommage")), None)
		if abime and _num(stocks.get("materiaux")) >= _int(reg.get("reparation_materiaux")):
			stocks["materiaux"] = _num(stocks.get("materiaux")) - _int(reg.get("reparation_materiaux"))
			abime.pop("endommage", None)

	# 4. Santé : maladies, soins, morts.
	sante = reg.get("sante") or {}
	if rand.random() < min(_num(sante.get("maladie_max")), _num(sante.get("maladie_par_habitant")) * bouches):
		imp["souffrants"] = min(bouches, _int(imp.get("souffrants")) + 1)
	soignant = bool(_du_role(imp, reg, employes, "soignants"))
	for _ in range(_int(imp.get("souffrants"))):
		remede = _num(stocks.get("medicaments")) >= _num(c.get("medicaments_par_soin"), 1)
		p = sante.get("guerison_soignee") if soignant and remede else \
			sante.get("guerison_partielle") if soignant or remede else sante.get("guerison_seule")
		tirage = rand.random()
		if tirage < _num(p):
			imp["souffrants"] -= 1
			if remede:
				stocks["medicaments"] = _num(stocks.get("medicaments")) - _num(c.get("medicaments_par_soin"), 1)
		elif not soignant and not remede and tirage > 1 - _num(sante.get("mort_seule")):
			imp["souffrants"] -= 1
			_mort(imp, employes, rand, instant, bilan, "de maladie")

	# 5. Sécurité et moral du moment, puis population.
	secu = securite(imp, reg, site, employes)
	mor = moral(imp, reg, site, employes, instant, secu)
	pop = reg.get("population") or {}
	libres = logements(imp, reg) - habitants(imp, employes)
	if libres > 0 and mor["valeur"] >= _num(pop.get("arrivee_moral_min")) \
			and secu["valeur"] >= _num(pop.get("arrivee_securite_min")) \
			and rand.random() < _num(pop.get("arrivee_proba")) * mor["valeur"] / 50:
		imp["population"] = _int(imp.get("population")) + 1
	elif mor["valeur"] < _num(pop.get("depart_moral")):
		if _int(imp.get("population")) > 0:
			if rand.random() < _num(pop.get("depart_proba")):
				imp["population"] -= 1
				bilan["evenements"].append("Un habitant a quitté le lieu.")
		elif mor["valeur"] < _num(pop.get("depart_nomme_moral")) and rand.random() < _num(pop.get("depart_nomme_proba")):
			nom = _perdre_un(imp, employes, rand, EMPLOYE_PARTI, bilan)
			if nom:
				bilan["evenements"].append(f"{nom} a quitté le lieu.")

	# 6. La menace (§ 6).
	_menace(imp, reg, site, employes, instant, rand, bilan, secu)
	for s in list(stocks):
		stocks[s] = round(max(0.0, _num(stocks[s])), 4)     # 2 décimales perdraient 4 % par jour


def _mort(imp: dict, employes: list, rand, instant: int, bilan: dict, cause: str) -> None:
	nom = _perdre_un(imp, employes, rand, EMPLOYE_MORT, bilan)
	imp.setdefault("morts", []).append(instant)
	del imp["morts"][:-30]
	bilan["evenements"].append(f"{nom} est mort {cause}." if nom else f"Un habitant est mort {cause}.")


def _menace(imp: dict, reg: dict, site: dict, employes: list, instant: int, rand, bilan: dict, secu: dict) -> None:
	menace = imp.get("menace") or {}
	etape = _int(menace.get("etape"))
	conf = reg.get("menace") or {}
	# Tanière vidée : la contrée se tait un temps, puis une autre bête s'installe.
	if not etape and menace.get("espece") and menace.get("nettoyee_at") \
			and instant - _int(menace["nettoyee_at"]) >= _int(conf.get("repousse_s"), 7 * JOUR_S):
		menace["etape"] = 1
		menace.pop("nettoyee_at", None)
		imp["menace"] = menace
		bilan["evenements"].append("Une autre bête s'est installée dans les environs.")
		return
	if not etape or not menace.get("espece"):
		return
	danger = _int(((site or {}).get("danger") or {}).get("note"))
	if etape == 1:
		if rand.random() < _num(conf.get("remarque_proba")) * (1 + danger) * _num((conf.get("feu") or {}).get(imp.get("feu")), 1):
			menace["etape"] = 2
			bilan["evenements"].append("La bête des environs a remarqué le lieu.")
		return
	# Étapes 2 et au-delà : le lieu peut être attaqué.
	proba = _num((conf.get("attaque_proba") or {}).get(imp.get("palier"))) * (1 + danger / 3)
	if not _du_role(imp, reg, employes, "gardes"):
		proba *= _num(conf.get("nuit_sans_garde"), 1)
	if rand.random() < proba:
		_attaque(imp, reg, employes, instant, rand, bilan, secu)
	if etape == 2:
		if rand.random() < _num(conf.get("harcele_proba")) * (1 + danger) * (1 - secu["valeur"] / 150):
			menace["etape"] = 3
			bilan["evenements"].append("La bête s'en prend aux troupeaux et aux réserves.")
	elif etape == 3:
		if rand.random() < _num(conf.get("pillage_proba")):
			perte = round(_num(imp["stocks"].get("nourriture")) * _num(conf.get("pillage_part")), 1)
			if perte > 0:
				imp["stocks"]["nourriture"] = _num(imp["stocks"].get("nourriture")) - perte
				bilan["evenements"].append(f"Troupeaux et réserves pillés : nourriture −{perte}.")
		pisteurs = len(_du_role(imp, reg, employes, "pisteurs"))
		if rand.random() < _num(conf.get("taniere_proba")) + pisteurs * _num(conf.get("taniere_par_pisteur")):
			menace["etape"] = 4
			bilan["evenements"].append("La tanière de la bête est localisée.")
	imp["menace"] = menace


def _attaque(imp: dict, reg: dict, employes: list, instant: int, rand, bilan: dict, secu: dict) -> None:
	"""Attaque en l'ABSENCE du fondateur : issue résolue d'après la sécurité (§ 6). Pertes
	possibles — blessés, morts, réserves, bâtiment endommagé, incendie — jamais le lieu."""
	repoussee = rand.random() * 100 < secu["valeur"]
	imp.setdefault("attaques", []).append({"at": instant, "repoussee": repoussee})
	del imp["attaques"][:-20]
	if repoussee:
		if rand.random() < 0.3:
			imp["souffrants"] = _int(imp.get("souffrants")) + 1
		bilan["evenements"].append("Une attaque a été repoussée.")
		return
	gravite = rang_palier(reg, imp.get("palier")) + 1     # plus rare et plus grave en grandissant
	pertes = []
	blesses = rand.randint(1, gravite)
	imp["souffrants"] = _int(imp.get("souffrants")) + blesses
	pertes.append(f"{blesses} blessé(s)")
	for _ in range(rand.randint(0, gravite // 2)):
		if habitants(imp, employes) > 0:
			_mort(imp, employes, rand, instant, bilan, "dans l'attaque")
	part = rand.uniform(0.1, 0.3)
	perdu = round(_num(imp["stocks"].get("nourriture")) * part, 1)
	if perdu > 0:
		imp["stocks"]["nourriture"] = _num(imp["stocks"].get("nourriture")) - perdu
		pertes.append(f"nourriture −{perdu}")
	debout = [b for b in imp.get("batiments") or [] if not b.get("endommage")]
	if debout and rand.random() < 0.4:
		b = rand.choice(debout)
		b["endommage"] = True
		pertes.append(f"{(batiment_def(reg, b.get('type')) or {}).get('label', 'un bâtiment')} endommagé")
	if rand.random() < 0.15:
		brule = round(_num(imp["stocks"].get("bois")) * 0.3, 1)
		imp["stocks"]["bois"] = _num(imp["stocks"].get("bois")) - brule
		pertes.append(f"incendie : bois −{brule}")
	bilan["evenements"].append("Le lieu a été attaqué : " + ", ".join(pertes) + ".")


# ── Vente de la production (§ 8) : la mécanique des biens urbains, l'implantation pour cité ──

def vente_autorisee(employe: dict) -> bool:
	"""Option par PNJ : sa production se vend-elle ? Absent ⇒ oui (comme `echanges_cite`)."""
	return (employe or {}).get("vente_cite") is not False


def effets_negoce(imp: dict, reg: dict, employes: list) -> dict:
	"""Effets du personnel du négoce AU POSTE (`effets_metier` des bâtiments) — le meilleur de
	chaque clé, jamais une somme (même règle que les aménagements urbains)."""
	out = {}
	for e in au_poste(imp, reg, employes):
		b = batiment(imp, e.get("poste")) or {}
		bloc = ((batiment_def(reg, b.get("type")) or {}).get("effets_metier") or {}).get(e.get("metier")) or {}
		for cle, v in bloc.items():
			out[cle] = max(_num(out.get(cle)), _num(v))
	return out


def negociant_de(imp: dict, reg: dict, employes: list) -> dict | None:
	from utils import echanges_cite
	return next((e for e in au_poste(imp, reg, employes) if echanges_cite.est_negociant(e)), None)


def caisse_max(imp: dict, reg: dict, employes: list) -> int:
	base = _int((reg.get("echanges") or {}).get("caisse_max_par_rang"), 5000) * (rang_palier(reg, imp.get("palier")) + 1)
	return int(base * max(1.0, _num(effets_negoce(imp, reg, employes).get("caisse_facteur"), 1)))


def echanger(imp: dict, reg: dict, employes: list, boutiques: list, get_doc_fn, resolve_item, passes: int,
			 rand=random, now: int | None = None) -> dict:
	"""Les PNJ producteurs (fermes, coupes, carrières) vendent le SURPLUS de leur stock aux
	boutiques du lieu — prix du FONDATEUR chez chacune, refus à la cible, plus offrant d'abord,
	marchandise posée chez l'acheteur (`echanges_cite.prix_vente_boutique`, `marche.absorber_achat`).
	Sans négociant : décote ; le crieur vend aux habitants ce que nulle boutique ne prend. Au
	plus `echanges.passes_max` passes (2 jours, § 8). Recette → `imp.caisse_cuivre`. Rend
	`{"gain", "touchees": [boutiques], "journal"}` ; mute `imp`, les boutiques, le négociant."""
	from models import character_stats
	from utils import echanges_cite, marche
	now = now_epoch() if now is None else now
	conf = reg.get("echanges") or {}
	passes = max(0, min(int(passes), _int(conf.get("passes_max"), 48)))
	bilan = {"gain": 0, "touchees": [], "journal": []}
	if not passes:
		return bilan
	eff = effets_negoce(imp, reg, employes)
	negociant = negociant_de(imp, reg, employes)
	ctx = echanges_cite.Contexte.libre(
		imp.get("fondateur"), conf, None, negociant, get_doc_fn, rand, now,
		portage_kg=_num(conf.get("portage_kg"), 20) + _num(eff.get("portage_kg")),
		crieur=_int(eff.get("crieur")), caisse_max=caisse_max(imp, reg, employes))
	ctx.prospection = _int(ctx.prospection) + _int(eff.get("prospection"))
	par_metier = {m.get("id"): m for m in reg.get("metiers_def") or []}
	seuils = seuils_stocks(imp, reg, employes)
	unites_objet = max(0.1, _num(conf.get("unites_par_objet"), 1))
	stocks = imp.setdefault("stocks", {})
	docs = {}

	def item(i):
		if i not in docs:
			docs[i] = resolve_item(i) or {}
		return docs[i]

	for _ in range(passes):
		ctx.portage = ctx.portage_passe
		crieur = [ctx.crieur]
		for e in au_poste(imp, reg, employes):
			produit = (par_metier.get(e.get("metier")) or {}).get("produit") or {}
			objets = [i for i in produit.get("items") or [] if item(i)]
			s = produit.get("stock")
			if not objets or not vente_autorisee(e):
				continue
			plancher = _num(conf.get("surplus_facteur"), 2) * seuils.get(s, 0)
			tour = 0
			while _num(stocks.get(s)) - unites_objet >= plancher and _int(imp.get("caisse_cuivre")) < ctx.caisse_max:
				doc = item(objets[tour % len(objets)])
				tour += 1
				poids = _num(doc.get("poids") if not isinstance(doc.get("poids"), list) else sum(doc["poids"]) / 2, 1)
				if poids > ctx.portage:
					break
				offres = [(p, b) for b in rand.sample(boutiques, min(len(boutiques), max(1, ctx.prospection)))
						  if (p := echanges_cite.prix_vente_boutique(ctx, b, doc)) is not None]
				if offres:
					prix, acheteur = max(offres, key=lambda o: o[0])
					marche.absorber_achat(acheteur, doc)
					ctx.touchees[acheteur.get("_id")] = acheteur
					ctx.noter("vente", doc, acheteur, 1, prix)
				elif crieur[0] > 0:
					pmin, _pmax = marche.prix_range_cuivre(doc, doc.get("_id"))
					prix = max(1, int(round(pmin * float(character_stats.RACHAT_FACTEUR))))
					crieur[0] -= 1
					ctx.noter("crieur", doc, {"label": "les habitants"}, 1, prix)
				else:
					break
				stocks[s] = round(_num(stocks.get(s)) - unites_objet, 4)
				imp["caisse_cuivre"] = _int(imp.get("caisse_cuivre")) + prix
				ctx.portage -= poids
				ctx.gain += prix
				ctx.echange += prix
	if negociant and ctx.echange:
		negociant["negoce_xp"] = _int(negociant.get("negoce_xp")) \
			+ int(ctx.echange * float(ctx.regln["xp_par_cuivre"]))
	journal = [dict(v, t=now) for v in ctx.journal.values()]
	if journal:
		imp["echanges_journal"] = (journal + list(imp.get("echanges_journal") or []))[:_int(conf.get("journal_max"), 20)]
	bilan.update(gain=ctx.gain, touchees=list(ctx.touchees.values()), journal=journal)
	return bilan


def relever_caisse(imp: dict, fondateur: dict, now: int | None = None) -> int:
	"""La caisse du lieu revient au fondateur (réservé au fondateur, § 10)."""
	montant = _int(imp.get("caisse_cuivre"))
	imp["caisse_cuivre"] = 0
	if montant:
		noter(imp, f"Caisse relevée : {montant} cu.", now)
	return montant


def lieu_de_nuit(lieu_doc: dict, get_doc_fn) -> dict:
	"""Pour le log de la nuit (`auberge.messages_nuit`) : une implantation raconte le repos au
	FEU (`nuit_feu`), jamais la salle commune. Copie de surface, jamais sauvée."""
	if not est_implantation(lieu_doc) or (lieu_doc or {}).get("nuit_messages"):
		return lieu_doc
	return {**lieu_doc, "nuit_messages": list(regles(get_doc_fn).get("nuit_feu") or [])}


# ── Combats joués : défense du lieu et tanière (§ 6) ─────────────────────────────────
DEFENSE = "defense"
TANIERE = "taniere"


def attaque_presente(imp: dict, reg: dict, site: dict, employes: list, now: int | None = None, rand=random) -> bool:
	"""Le fondateur ou un associé est là : au plus un tirage par passe écoulée depuis le
	précédent, à la probabilité d'attaque du palier. Une attaque tirée ATTEND sa réponse
	(`attaque_en_cours`) — combat joué — ou se résout seule après `delai_defense_s`. True si
	elle vient d'être tirée."""
	now = now_epoch() if now is None else now
	conf = reg.get("menace") or {}
	pas = max(60, _int((reg.get("temps") or {}).get("passe_s"), 3600))
	menace = imp.get("menace") or {}
	if imp.get("attaque_en_cours") or _int(menace.get("etape")) < 2 or not menace.get("espece"):
		return False
	if now - _int(imp.get("presence_at")) < pas:
		return False
	imp["presence_at"] = now
	danger = _int(((site or {}).get("danger") or {}).get("note"))
	proba = _num((conf.get("attaque_proba") or {}).get(imp.get("palier"))) * (1 + danger / 3)
	if not _du_role(imp, reg, employes, "gardes"):
		proba *= _num(conf.get("nuit_sans_garde"), 1)
	if rand.random() >= proba:
		return False
	imp["attaque_en_cours"] = {"at": now, "espece": menace["espece"]}
	noter(imp, "Le lieu est attaqué !", now)
	return True


def nb_adversaires(imp: dict, reg: dict, genre: str) -> int:
	conf = reg.get("menace") or {}
	base = _int(conf.get("assaillants_base" if genre == DEFENSE else "taniere_meute"), 2)
	return base + rang_palier(reg, imp.get("palier"))


def peut_vider_taniere(imp: dict, role: str) -> tuple[bool, str]:
	"""« Pacifier » (§ 10) : fondateur ou associé, une fois la tanière localisée (étape 4)."""
	if role not in (FONDATEUR, ASSOCIE):
		return False, "Il faut être fondateur ou associé."
	menace = imp.get("menace") or {}
	if _int(menace.get("etape")) < 4 or not menace.get("espece"):
		return False, "La tanière n'est pas encore localisée."
	return True, ""


def garde_combattant(employe: dict, reg: dict) -> dict:
	"""Un garde nommé sous la forme d'un personnage de combat (`build_joueur_snapshot`) :
	nom, visage et Lignée du PNJ, caractéristiques et équipement standards (`garde_combattant`)."""
	conf = reg.get("garde_combattant") or {}
	voc = conf.get("voc", "guerrier")
	return {"_id": employe.get("_id"), "type": "employe", "prenom": employe.get("prenom", ""),
			"nom": employe.get("nom", ""), "race": employe.get("race", ""), "sex": employe.get("sex", ""),
			"image": employe.get("portrait", ""), "voc": voc, "vocations_niveaux": {voc: _int(conf.get("niveau"), 1)},
			"caracteristiques_current": dict(conf.get("caracts") or {}), "currentPV": 10 ** 6, "currentPM": 0,
			"slots": dict(conf.get("slots") or {}), "inventaire": [], "effets_actifs": []}


def gardes_au_poste(imp: dict, reg: dict, employes: list) -> list:
	return _du_role(imp, reg, employes, "gardes")


def placer_assaillants(combat_doc: dict, lieu_doc: dict) -> None:
	"""Les attaquants partent des ENTRÉES (§ 12.6) : chaque monstre d'une case est reposé au
	plus près d'une entrée, en tournant de l'une à l'autre. Un grand jeton garde sa case."""
	entrees = entrees_de(lieu_doc)
	if not entrees:
		return
	prises = {(a["pos"]["x"], a["pos"]["y"]) for a in combat_doc.get("joueurs", []) + combat_doc.get("monstres", [])
			  if a.get("pos")}
	for i, m in enumerate(combat_doc.get("monstres") or []):
		if (m.get("jeton") or {}).get("largeur", 1) != 1 or (m.get("jeton") or {}).get("profondeur", 1) != 1:
			continue
		ancienne = (m["pos"]["x"], m["pos"]["y"]) if m.get("pos") else None
		case = case_libre_proche(lieu_doc, entrees[i % len(entrees)], prises - {ancienne})
		if case:
			prises.discard(ancienne)
			prises.add(tuple(case))
			m["pos"] = {"x": case[0], "y": case[1]}


def issue_combat(imp: dict, reg: dict, info: dict, status: str, gardes_morts: list, employes: list,
				 combat_id, now: int | None = None, rand=random) -> list | None:
	"""Applique l'issue d'un combat joué sur l'implantation. Idempotent (`combats_traites`) :
	None si déjà appliqué. Rend les docs PNJ touchés (gardes tombés, morts pour de bon).
	- défense gagnée : attaque repoussée ; perdue ou fuie : pertes comme en l'absence, sans
	  que la sécurité ne retienne rien ;
	- tanière vidée : la menace se tait (`nettoyee_at`), une expédition réussie de plus."""
	now = now_epoch() if now is None else now
	traites = imp.setdefault("combats_traites", [])
	if combat_id in traites:
		return None
	traites.append(combat_id)
	del traites[:-20]
	bilan = {"evenements": [], "employes_touches": []}
	for gid in gardes_morts or []:
		e = next((x for x in employes if x.get("_id") == gid), None)
		if e is None:
			continue
		employes.remove(e)
		e["statut"] = EMPLOYE_MORT
		imp["employes"] = [x for x in imp.get("employes") or [] if x != gid]
		imp.setdefault("morts", []).append(now)
		bilan["employes_touches"].append(e)
		bilan["evenements"].append(f"{proprietes.nom_personnage(e)} est tombé en défendant le lieu.")
	if info.get("genre") == DEFENSE:
		imp.pop("attaque_en_cours", None)
		if status == "victoire":
			imp.setdefault("attaques", []).append({"at": now, "repoussee": True})
			bilan["evenements"].append("L'attaque a été repoussée.")
		else:
			_attaque(imp, reg, employes, now, rand, bilan, {"valeur": -1})
	elif info.get("genre") == TANIERE and status == "victoire":
		menace = imp.setdefault("menace", {})
		menace.update(etape=0, nettoyee_at=now)
		imp["expeditions_reussies"] = _int(imp.get("expeditions_reussies")) + 1
		bilan["evenements"].append("La tanière est vidée : la contrée respire.")
	for texte in bilan["evenements"]:
		noter(imp, texte, now)
	return bilan["employes_touches"]


# ── Vues (§ 10, § 12.7) ──────────────────────────────────────────────────────────────

def vue(imp: dict, reg: dict, role: str, site: dict, employes: list, cat_proprietes: dict | None = None,
		now: int | None = None, disponibles=()) -> dict:
	"""Ce que le panneau montre. Le VISITEUR (et le soutien) lit le site en MOTS, les besoins
	et les dons ; le détail chiffré est au fondateur — et à l'associé, qui contribue."""
	now = now_epoch() if now is None else now
	secu = securite(imp, reg, site, employes)
	mor = moral(imp, reg, site, employes, now, secu)
	pdef = palier_def(reg, imp.get("palier")) or {}
	menace_mots = (reg.get("menace") or {}).get("mots") or {}
	labels = reg.get("stocks_labels") or {}
	base = {
		"id": imp.get("_id"), "label": imp.get("label"), "role": role,
		"fondateur_nom": imp.get("fondateur_nom"),
		"palier": {"id": pdef.get("id"), "label": pdef.get("label"), "ouvre": pdef.get("ouvre") or [],
				   "menace": pdef.get("menace")},
		"securite": {"mot": secu["mot"]}, "moral": {"mot": mor["mot"]},
		"feu": imp.get("feu"),
		"site": {axe: {"mots": bloc.get("mots", "")} for axe, bloc in (site or {}).items()},
		"besoins": besoins(imp, reg, employes),
		"stocks_ouverts": [{"stock": s, "label": labels.get(s, s)} for s in reg.get("stocks") or []],
		"places_associes": max(0, places_associes(imp, reg) - len(imp.get("associes") or [])),
		"demande_en_attente": False,
		"attaque_en_cours": bool(imp.get("attaque_en_cours")),
		"sous_lieux": [{"label": (batiment_def(reg, b.get("type")) or {}).get("label", ""),
						"metier": libelle_metier(b.get("categorie")), "pos": b.get("pos"),
						"ouvert": bool(tenancier(imp, reg, employes, b["id"])) and not b.get("endommage")}
					   for b in imp.get("batiments") or [] if b.get("lieu")],
	}
	if role not in (FONDATEUR, ASSOCIE):
		return base
	capacite = stockage(imp, reg)
	par_poste = {}
	for e in employes or []:
		par_poste.setdefault(e.get("poste"), []).append(e)
	base.update({
		"securite": secu, "moral": mor,
		"site": site,
		"stocks": [{"stock": s, "label": labels.get(s, s), "quantite": round(_num((imp.get("stocks") or {}).get(s)), 1),
					"capacite": capacite, "seuil": round(seuils_stocks(imp, reg, employes).get(s, 0), 1)}
				   for s in reg.get("stocks") or []],
		"population": _int(imp.get("population")), "nommes": len(employes or []),
		"logements": logements(imp, reg), "souffrants": _int(imp.get("souffrants")),
		"batiments": [{
			"id": b["id"], "type": b.get("type"), "pos": b.get("pos"), "endommage": bool(b.get("endommage")),
			"label": (batiment_def(reg, b.get("type")) or {}).get("label", "")
			+ (f" — {libelle_metier(b['categorie'])}" if b.get("categorie") and (batiment_def(reg, b.get("type")) or {}).get("familles") else ""),
			"nature": (batiment_def(reg, b.get("type")) or {}).get("nature"),
			"icone": (batiment_def(reg, b.get("type")) or {}).get("icone", ""),
			"postes": [{"metier": m, "label": (metier_def(reg, cat_proprietes, m) or {}).get("label", m), "places": n,
						"tenus": [{"id": e["_id"], "nom": proprietes.nom_personnage(e),
								   "vend": vente_autorisee(e) if ((next((m2 for m2 in reg.get("metiers_def") or [] if m2.get("id") == e.get("metier")), {}) .get("produit") or {}).get("items")) else None}
								  for e in par_poste.get(b["id"], []) if e.get("metier") == m]}
					   for bid, m, n in postes(imp, reg) if bid == b["id"]],
		} for b in imp.get("batiments") or []],
		"catalogue": [{
			"id": d.get("id"), "label": d.get("label"), "icone": d.get("icone"), "nature": d.get("nature"),
			"description": d.get("description", ""), "prix": _int(d.get("prix_cuivre")),
			"bois": _int(d.get("bois")), "materiaux": _int(d.get("materiaux")),
			"refus": peut_construire(imp, reg, d.get("id"))[1],
			"categories": ([{"id": c, "label": libelle_metier(c)} for c in categories_possibles(reg, d.get("id"), disponibles)]
						   if d.get("familles") else []),
		} for d in reg.get("batiments_def") or [] if d.get("nature") in NATURES_OUVERTES],
		"fortifications": [{
			"id": f.get("id"), "label": f.get("label"), "prix": _int(f.get("prix_cuivre")),
			"bois": _int(f.get("bois")), "materiaux": _int(f.get("materiaux")), "defense": _num(f.get("defense")),
			"en_place": f.get("id") in (imp.get("fortifications") or []),
			"requis_pour": (palier_def(reg, f.get("requis_pour")) or {}).get("label"),
			"refus": "" if f.get("id") in (imp.get("fortifications") or [])
			else peut_ouvrir_chantier({**imp, "chantier": None}, reg, employes, CHANTIER_FORTIFICATION, f.get("id"))[1],
		} for f in reg.get("fortifications") or []],
		"chantier": ({**imp["chantier"], "reste": reste_chantier(imp)} if imp.get("chantier") else None),
		"palier_suivant": conditions_palier(imp, reg, employes),
		"menace": {"etape": _int((imp.get("menace") or {}).get("etape")),
				   "mot": menace_mots.get(str(_int((imp.get("menace") or {}).get("etape"))), ""),
				   "taniere": peut_vider_taniere(imp, role)[0]},
		"associes": [{"id": a.get("id"), "nom": a.get("nom"), "apports": a.get("apports") or {}}
					 for a in imp.get("associes") or []],
		"negoce": {"negociant": bool(negociant_de(imp, reg, employes)), "caisse": _int(imp.get("caisse_cuivre")),
				   "caisse_max": caisse_max(imp, reg, employes),
				   "journal": list(imp.get("echanges_journal") or [])[:10]},
	})
	if role == FONDATEUR:
		base.update({
			"journal": list(reversed(imp.get("journal") or [])),
			"demandes": list(imp.get("demandes") or []),
			"soutiens": [{"nom": s.get("nom"), "dons": s.get("dons") or {}} for s in (imp.get("soutiens") or {}).values()],
		})
	return base

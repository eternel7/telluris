# models/character_stats.py
# Modèles Pydantic pour les stats de personnage Telluris / Légende

from pydantic import BaseModel, Field
import math

# ── Variables de monde (réglables sans redéploiement) ───────────────────
# Les constantes ci-dessous sont les valeurs PAR DÉFAUT (fallback). Au démarrage,
# `load_world_variables()` les écrase avec le doc CouchDB `rules:world_variables`
# s'il existe (cf. plus bas). Ce module reste SANS dépendance DB au niveau import
# (le chargeur importe db.config paresseusement) pour que les tests pure-Python
# continuent de tourner.
#
# ⚠️ Toujours lire ces tunables via le module (`character_stats.XP_VOC_COEFF`),
# jamais par `from character_stats import XP_VOC_COEFF` : le chargeur réassigne
# les globales, donc une copie importée par valeur resterait figée.

WORLD_VARIABLES_DOC_ID: str = "rules:world_variables"

# Bouton de réglage central de la létalité. Modèle de résolution des dégâts :
#   Dégâts = caract // FACTEUR + arme − (R_cible // FACTEUR)
# où `caract` = F au corps à corps, Ag au tir. Les points d'armure (PA) suivent
# la même règle : PA = R // FACTEUR. Baisser le facteur amplifie le poids des
# caractéristiques brutes (bonus de dégâts ET armure plus gros) → les écarts de
# stats décident plus vite l'issue ; l'augmenter rapproche le combat des seuls
# dés + chances de toucher. C'est le levier pour régler le nombre de rounds.
FACTEUR_DEGATS_ARMURE: int = 20

# Bonus de portée des armes de JET dérivé de la Force : portee_jet = item.portee + F // JET_PORTEE_F_DIV.
# Sur l'échelle ×10 (F ≈ 10-100), un diviseur de 20 donne +0 à +5 cases selon la puissance.
JET_PORTEE_F_DIV: int = 20

# XP gagnée à la découverte d'un lieu (fallback si le lieu n'a pas de xp_decouverte).
XP_DECOUVERTE_LIEU: int = 1

# Dans une ville (lieu à image TOWNS), niveau de profil de monstre maximal rencontrable.
TOWN_PROFIL_NIVEAU_MAX: int = 2

# V coûte 10× plus cher, toutes les autres stats coûtent 1 par point au-dessus du min racial
XP_COEFF: dict[str, int] = {"V": 10}
XP_VOC_COEFF: int = 5

# Réduction du plafond pour les stats hors quota d'accessibilité
# V perd 1 point, toutes les autres perdent 10 points sous le max racial
_SUB_CAP_REDUCTION: dict[str, int] = {"V": 1}

# ── Économie marchande ────────────────────────────────────────────────────────
# Prix dérivé d'un objet vendable sans champ `valeur` (en cuivre) :
#   cuivre = poids × MULT_RARETE[rarete] × PRIX_DERIVE_BASE
PRIX_DERIVE_BASE: float = 2.0
MULT_RARETE: dict[str, float] = {
	"commun": 1, "peu_commun": 10, "rare": 30, "tres_rare": 100, "legendaire": 500, "mythique": 1000, "divin" : 10000
}
# Quelles sous-catégories d'item chaque catégorie de lieu (marchand) achète au personnage.
ACHAT_SOUS_CAT_PAR_LIEU: dict[str, list] = {
	"boucherie": [
	"carcasse"
	],
	"tannerie": [
	"cuir_brut"
	],
	"maroquinerie": [
	"cuir"
	],
	"cordonnerie": [
	"cuir",
	"tendons"
	],
	"bourrellerie": [
	"cuir"
	],
	"armurerie": [
	"cuir",
	"tendons"
	],
	"cuisine": [
	"viande",
	"foie",
	"coeur"
	],
	"fumoir": [
	"viande"
	],
	"salaison": [
	"viande"
	],
	"laboratoire_d_alchimie": [
	"sang",
	"poudre_d_os",
	"griffes",
	"yeux",
	"coeur"
	],
	"scriptorium": [
	"sang",
	"plumes"
	],
	"savonnerie": [
	"graisse"
	],
	"atelier_de_cirier": [
	"graisse"
	],
	"apothicairerie": [
	"graisse",
	"foie"
	],
	"tabletterie": [
	"os",
	"crocs"
	],
	"atelier_d_artisan": [
	"os"
	],
	"jardinier": [
	"poudre_d_os"
	],
	"corderie": [
	"crins"
	],
	"brosserie": [
	"crins",
	"poils"
	],
	"tissage": [
	"poils"
	],
	"plumasserie": [
	"plumes"
	],
	"atelier_de_l_empenneur": [
	"plumes",
	"bois"
	],
	"boyauderie": [
	"boyaux"
	],
	"fletcher": [
	"boyaux",
	"tendons"
	],
	"lutherie": [
	"boyaux"
	],
	"bijouterie": [
	"griffes",
	"crocs"
	],
	"taxidermie": [
	"crane"
	],
	"necromancie": [
	"crane"
	]
	}

# ── Approvisionnement des ateliers (au tick) ─────────────────────────────────────
# À chaque `tick_atelier` (vente/visite), le lieu reçoit des matières premières selon sa
# catégorie : APPRO_MATIERES_PAR_LIEU[categorie] = {sous_categorie: quantite_par_tick}.
# Sert surtout aux matières que le lieu « se procure » lui-même (métaux pour l'armurerie…).
# Défaut = échafaudage : une entrée par métal existant (item tag "metal") × chaque catégorie
# de lieu marchand (clés de ACHAT_SOUS_CAT_PAR_LIEU) — à élaguer via /admin (ex. ne garder
# les métaux que pour l'armurerie).
_APPRO_METAUX_DEFAUT: dict[str, int] = {"fer": 5, "acier": 3, "bronze": 5, "mithril": 1}
APPRO_MATIERES_PAR_LIEU: dict[str, dict] = {
	cat: dict(_APPRO_METAUX_DEFAUT) for cat in ["amurerie"]
}

# ── Marchandage ─────────────────────────────────────────────────────────────────
# Le prix d'une transaction est interpolé entre le min et le max de l'objet
# (`valeur` à deux bornes, sinon min dérivé et max = min × PRIX_MAX_FACTEUR). Le
# marchandage est un jet opposé Cha joueur vs Cha marchand. Le Cha du marchand vient
# de CHA_MARCHAND_PAR_CATEGORIE[lieu.categorie], sinon du global CHA_MARCHAND (un
# champ `cha` posé sur le doc lieu le supplante).
CHA_MARCHAND: int = 50
CHA_MARCHAND_PAR_CATEGORIE: dict[str, int] = { "bijouterie": 70 }
PRIX_MAX_FACTEUR: float = 3.0
# Marge appliquée à chaque étape de transformation (coût de revient propagé) :
# prix_produit ≈ coût_ingrédients × (quantite_matiere / quantite_produite) × MARGE_TRANSFO.
# Composé sur les chaînes (produit en N étapes ≈ ×MARGE^N). Réglable à chaud via /admin.
MARGE_TRANSFO: float = 5.0

# ── Jets de dés (seuils de critique génériques) ──────────────────────────────────
# Bornes de critique applicables à TOUT jet d100 (marchandage, combat futur, etc.) :
# roll ≤ CRIT_REUSSITE_MAX = réussite critique ; roll ≥ CRIT_ECHEC_MIN = échec critique.
CRIT_REUSSITE_MAX: int = 5
CRIT_ECHEC_MIN: int = 96

# ── Relation marchand (marchandage volontaire) ───────────────────────────────────
# La relation perso×lieu (doc `type:"relation"`) est un entier sur 0–100, neutre à
# 50. Elle pondère le prix de base (sans marchander : médian à 50, meilleur au-dessus,
# pire en dessous) ET le seuil du marchandage volontaire, via l'écart au neutre
# (relation−50) × RELATION_SEUIL_COEFF. Relation 0 = transactions interdites au lieu.
# Marchander = action explicite : crit réussite (CRIT_REUSSITE_MAX) → +1 relation ; crit
# échec (CRIT_ECHEC_MIN) → −1 relation ET blocage du marchandage pendant MARCHANDAGE_BLOCAGE_SECONDES.
RELATION_INITIALE: int = 50
RELATION_SEUIL_COEFF: float = 2.0
MARCHANDAGE_BLOCAGE_SECONDES: int = 3600

# ── Quêtes (guilde + moteur de génération) ───────────────────────────────────────
# Le tableau d'une guilde maintient un pool de QUETE_BOARD_TAILLE offres générées
# (complété à la volée à chaque ouverture, en plus des quêtes authorées). La quantité
# d'objectif est tirée dans [QUETE_QTE_MIN, QUETE_QTE_MAX] (réduite pour les cibles
# difficiles). Récompenses dérivées de l'XP unitaire du combat (cohérence avec le grind) :
# xp = round(xp_unitaire × quantite × QUETE_XP_FACTEUR) ; cuivre = round(xp × QUETE_CUIVRE_PAR_XP).
QUETE_BOARD_TAILLE: int = 6
QUETE_QTE_MIN: int = 2
QUETE_QTE_MAX: int = 8
QUETE_XP_FACTEUR: float = 1.5
QUETE_CUIVRE_PAR_XP: float = 3.0
# Poids max (kg) d'un objet d'une quête de collecte : on ne réclame pas d'objet plus lourd
# (ex. un arbre entier) — pour le bois, on cible des pièces transportables de l'essence.
QUETE_COLLECT_POIDS_MAX: float = 100.0

# ── Récolte & découpe du bois ────────────────────────────────────────────────────
# Échelle des tailles de bois, du plus petit au plus grand. Couper un item « a_couper »
# produit des pièces du tier immédiatement plus petit (même `essence`), poids conservé.
# `branche` n'a pas le tag a_couper → terminal. La coupe nécessite un item portant le tag
# OUTIL_COUPE_BOIS_TAG dans le sac/équipement. COUPE_MAX_PIECES borne le nombre de pièces
# générées par coupe (anti-explosion : le reliquat est aggloméré dans la dernière pièce).
BOIS_A_COUPER: list = ["branche", "petit_rondin", "rondin", "gros_rondin", "tronc", "arbre"]
OUTIL_COUPE_BOIS_TAG: str = "outil_coupe_bois"
COUPE_MAX_PIECES: int = 40

# ── Dépeçage des carcasses (boucherie) ──────────────────────────────────────────
# Une carcasse vendue à une boucherie est décomposée en matières premières selon les
# `tags` de son espèce. Table tunable tag → matières produites (un sous-cat répété
# = quantité ; on prend le MAX par sous-cat entre sources, pas la somme, pour ne pas
# gonfler). `_charnu_base` s'applique à toute créature charnue (ni esprit/incorporel,
# ni construct/elementaire, ni mort-vivant). Les morts-vivants n'utilisent que leurs
# propres entrées (os). Garde : `plumes` retiré si l'espèce est `draconique`.
# Les quantités finales sont mises à l'échelle du POIDS de la carcasse (cf.
# DEPECAGE_POIDS_REF) — il n'y a plus de bucket petite_taille/geant.
DEPECAGE_TAGS: dict[str, list] = {
	"_charnu_base": [
	  "viande",
	  "viande",
	  "os",
	  "sang",
	  "graisse"
	],
	"animal": [
	  "cuir_brut",
	  "crocs",
	  "poils"
	],
	"monstre": [
	  "cuir_brut",
	  "crocs"
	],
	"humanoide": [
	  "cuir_brut"
	],
	"monture": [
	  "cuir_brut",
	  "crins",
	  "tendons"
	],
	"bete_de_somme": [
	  "cuir_brut",
	  "crins"
	],
	"draconique": [
	  "cuir_brut",
	  "crocs",
	  "griffes",
	  "tendons",
	  "coeur"
	],
	"reptile": [
	  "cuir_brut",
	  "crocs"
	],
	"demon": [
	  "cuir_brut",
	  "crocs",
	  "griffes",
	  "coeur"
	],
	"infernal": [
	  "griffes",
	  "coeur"
	],
	"celeste": [
	  "griffes",
	  "coeur"
	],
	"ange": [
	  "plumes",
	  "coeur"
	],
	"vol": [
	  "plumes",
	  "griffes"
	],
	"venin": [
	  "crocs"
	],
	"foret": [
	  "poils"
	],
	"froid": [
	  "poils"
	],
	"geant": [
	  "tendons",
	  "boyaux",
	  "foie",
	  "crane"
	],
	"grande_taille": [
	  "boyaux"
	],
	"boss": [
	  "coeur",
	  "yeux",
	  "crane"
	],
	"legendaire": [
	  "coeur",
	  "foie",
	  "yeux"
	],
	"magique": [
	  "yeux"
	],
	"petrification": [
	  "yeux"
	],
	"undead": [
	  "os",
	  "os",
	  "crane"
	],
	"non_mort": [
	  "os",
	  "os"
	]
  }

# Échelle du dépeçage : quantité de chaque matière = max(1, round(base × poids / DEPECAGE_POIDS_REF)).
# Le poids de la carcasse pilote seul la production (conservation de la masse). À ce poids de
# référence on retrouve les quantités de base des recettes ; plus lourd → proportionnellement plus.
DEPECAGE_POIDS_REF: float = 5.0

# Probabilité, à chaque vente à un atelier, de déclencher une passe de production (batch) ;
# sinon la matière vendue est seulement stockée. Réglable à chaud via /admin.
ATELIER_TRANSFO_PROBA: float = 0.10

# ── Prix offre/demande (stock cible) ──────────────────────────────────────────────
# Le prix d'un bien est modulé par l'écart entre le stock du marchand et un stock cible :
# stock élevé → moins cher (le marchand brade) ; stock bas → plus cher. Le facteur est borné
# ±PRIX_AMPLITUDE_STOCK et le prix final reste dans [pmin, pmax]. Le stock cible est défini
# PAR LIEU (champ `stock_cible` : {item|sous_categorie|categorie → cible}), STOCK_CIBLE_DEFAUT
# servant de repli ultime.
STOCK_CIBLE_DEFAUT: int = 100
PRIX_AMPLITUDE_STOCK: float = 0.30
# Écoulement PNJ des produits finis : à chaque vente/visite, proba de vendre aux PNJ une
# fraction de l'excédent (au-dessus de la cible) de chaque produit en rayon.
VENTE_PNJ_PROBA: float = 0.10
VENTE_PNJ_FRACTION: float = 0.50


def current_world_variables() -> dict:
	"""Snapshot des variables de monde effectives (telles qu'appliquées en mémoire)."""
	return {
		"FACTEUR_DEGATS_ARMURE": FACTEUR_DEGATS_ARMURE,
		"JET_PORTEE_F_DIV": JET_PORTEE_F_DIV,
		"XP_DECOUVERTE_LIEU": XP_DECOUVERTE_LIEU,
		"TOWN_PROFIL_NIVEAU_MAX": TOWN_PROFIL_NIVEAU_MAX,
		"XP_COEFF": dict(XP_COEFF),
		"XP_VOC_COEFF": XP_VOC_COEFF,
		"SUB_CAP_REDUCTION": dict(_SUB_CAP_REDUCTION),
		"PRIX_DERIVE_BASE": PRIX_DERIVE_BASE,
		"MULT_RARETE": dict(MULT_RARETE),
		"ACHAT_SOUS_CAT_PAR_LIEU": {k: list(v) for k, v in ACHAT_SOUS_CAT_PAR_LIEU.items()},
		"APPRO_MATIERES_PAR_LIEU": {k: dict(v) for k, v in APPRO_MATIERES_PAR_LIEU.items()},
		"CHA_MARCHAND": CHA_MARCHAND,
		"CHA_MARCHAND_PAR_CATEGORIE": dict(CHA_MARCHAND_PAR_CATEGORIE),
		"PRIX_MAX_FACTEUR": PRIX_MAX_FACTEUR,
		"MARGE_TRANSFO": MARGE_TRANSFO,
		"DEPECAGE_TAGS": {k: list(v) for k, v in DEPECAGE_TAGS.items()},
		"DEPECAGE_POIDS_REF": DEPECAGE_POIDS_REF,
		"ATELIER_TRANSFO_PROBA": ATELIER_TRANSFO_PROBA,
		"STOCK_CIBLE_DEFAUT": STOCK_CIBLE_DEFAUT,
		"PRIX_AMPLITUDE_STOCK": PRIX_AMPLITUDE_STOCK,
		"VENTE_PNJ_PROBA": VENTE_PNJ_PROBA,
		"VENTE_PNJ_FRACTION": VENTE_PNJ_FRACTION,
		"CRIT_REUSSITE_MAX": CRIT_REUSSITE_MAX,
		"CRIT_ECHEC_MIN": CRIT_ECHEC_MIN,
		"RELATION_INITIALE": RELATION_INITIALE,
		"RELATION_SEUIL_COEFF": RELATION_SEUIL_COEFF,
		"MARCHANDAGE_BLOCAGE_SECONDES": MARCHANDAGE_BLOCAGE_SECONDES,
		"QUETE_BOARD_TAILLE": QUETE_BOARD_TAILLE,
		"QUETE_QTE_MIN": QUETE_QTE_MIN,
		"QUETE_QTE_MAX": QUETE_QTE_MAX,
		"QUETE_XP_FACTEUR": QUETE_XP_FACTEUR,
		"QUETE_CUIVRE_PAR_XP": QUETE_CUIVRE_PAR_XP,
		"QUETE_COLLECT_POIDS_MAX": QUETE_COLLECT_POIDS_MAX,
		"BOIS_A_COUPER": list(BOIS_A_COUPER),
		"OUTIL_COUPE_BOIS_TAG": OUTIL_COUPE_BOIS_TAG,
		"COUPE_MAX_PIECES": COUPE_MAX_PIECES,
	}


# Snapshot des valeurs PAR DÉFAUT du code, figé à l'import (AVANT tout load_world_variables) :
# l'état « via le code » seul, indépendant du doc CouchDB. Exposé en lecture seule dans /admin
# comme référence à recopier. current_world_variables() renvoie des copies → snapshot immuable.
CODE_DEFAULTS: dict = current_world_variables()


def load_world_variables() -> dict:
	"""Charge `rules:world_variables` depuis CouchDB et écrase les valeurs par
	défaut de ce module. À appeler une fois au démarrage de l'app (idempotent).

	Fallback robuste : toute clé absente — ou DB injoignable, ou doc manquant —
	conserve la valeur par défaut déjà en place. Format attendu du doc :

		{ "_id": "rules:world_variables", "type": "rules",
		  "value": { "FACTEUR_DEGATS_ARMURE": 20, "XP_DECOUVERTE_LIEU": 1,
					 "XP_COEFF": {"V": 10}, "XP_VOC_COEFF": 5,
					 "SUB_CAP_REDUCTION": {"V": 1} } }

	Les dicts (XP_COEFF, SUB_CAP_REDUCTION) sont mutés en place pour rester vivants
	côté importateurs ; les scalaires sont réassignés (à lire via le module).
	Retourne le snapshot effectif.
	"""
	global FACTEUR_DEGATS_ARMURE, JET_PORTEE_F_DIV, XP_DECOUVERTE_LIEU, TOWN_PROFIL_NIVEAU_MAX, XP_VOC_COEFF, PRIX_DERIVE_BASE
	global CHA_MARCHAND, PRIX_MAX_FACTEUR, MARGE_TRANSFO, DEPECAGE_POIDS_REF, ATELIER_TRANSFO_PROBA
	global STOCK_CIBLE_DEFAUT, PRIX_AMPLITUDE_STOCK, VENTE_PNJ_PROBA, VENTE_PNJ_FRACTION
	global CRIT_REUSSITE_MAX, CRIT_ECHEC_MIN
	global RELATION_INITIALE, RELATION_SEUIL_COEFF, MARCHANDAGE_BLOCAGE_SECONDES
	global QUETE_BOARD_TAILLE, QUETE_QTE_MIN, QUETE_QTE_MAX, QUETE_XP_FACTEUR, QUETE_CUIVRE_PAR_XP
	global QUETE_COLLECT_POIDS_MAX
	global OUTIL_COUPE_BOIS_TAG, COUPE_MAX_PIECES
	try:
		from db.config import get_doc  # import paresseux : pas de dépendance DB à l'import
		doc = get_doc(WORLD_VARIABLES_DOC_ID)
	except Exception:
		doc = None
	v = (doc or {}).get("value") or {}

	FACTEUR_DEGATS_ARMURE  = int(v.get("FACTEUR_DEGATS_ARMURE", FACTEUR_DEGATS_ARMURE))
	JET_PORTEE_F_DIV       = max(1, int(v.get("JET_PORTEE_F_DIV", JET_PORTEE_F_DIV)))
	XP_DECOUVERTE_LIEU     = int(v.get("XP_DECOUVERTE_LIEU", XP_DECOUVERTE_LIEU))
	TOWN_PROFIL_NIVEAU_MAX = int(v.get("TOWN_PROFIL_NIVEAU_MAX", TOWN_PROFIL_NIVEAU_MAX))
	XP_VOC_COEFF           = int(v.get("XP_VOC_COEFF", XP_VOC_COEFF))
	if isinstance(v.get("XP_COEFF"), dict):
		XP_COEFF.clear()
		XP_COEFF.update({k: int(x) for k, x in v["XP_COEFF"].items()})
	if isinstance(v.get("SUB_CAP_REDUCTION"), dict):
		_SUB_CAP_REDUCTION.clear()
		_SUB_CAP_REDUCTION.update({k: int(x) for k, x in v["SUB_CAP_REDUCTION"].items()})

	PRIX_DERIVE_BASE = float(v.get("PRIX_DERIVE_BASE", PRIX_DERIVE_BASE))
	if isinstance(v.get("MULT_RARETE"), dict):
		MULT_RARETE.clear()
		MULT_RARETE.update({k: float(x) for k, x in v["MULT_RARETE"].items()})
	if isinstance(v.get("ACHAT_SOUS_CAT_PAR_LIEU"), dict):
		ACHAT_SOUS_CAT_PAR_LIEU.clear()
		ACHAT_SOUS_CAT_PAR_LIEU.update({k: list(x) for k, x in v["ACHAT_SOUS_CAT_PAR_LIEU"].items()})
	if isinstance(v.get("APPRO_MATIERES_PAR_LIEU"), dict):
		APPRO_MATIERES_PAR_LIEU.clear()
		APPRO_MATIERES_PAR_LIEU.update({
			k: {sc: int(q) for sc, q in x.items()}
			for k, x in v["APPRO_MATIERES_PAR_LIEU"].items() if isinstance(x, dict)
		})

	CHA_MARCHAND     = int(v.get("CHA_MARCHAND", CHA_MARCHAND))
	PRIX_MAX_FACTEUR = float(v.get("PRIX_MAX_FACTEUR", PRIX_MAX_FACTEUR))
	MARGE_TRANSFO    = float(v.get("MARGE_TRANSFO", MARGE_TRANSFO))
	if isinstance(v.get("CHA_MARCHAND_PAR_CATEGORIE"), dict):
		CHA_MARCHAND_PAR_CATEGORIE.clear()
		CHA_MARCHAND_PAR_CATEGORIE.update({k: int(x) for k, x in v["CHA_MARCHAND_PAR_CATEGORIE"].items()})
	if isinstance(v.get("DEPECAGE_TAGS"), dict):
		DEPECAGE_TAGS.clear()
		DEPECAGE_TAGS.update({k: list(x) for k, x in v["DEPECAGE_TAGS"].items()})
	DEPECAGE_POIDS_REF = float(v.get("DEPECAGE_POIDS_REF", DEPECAGE_POIDS_REF))
	ATELIER_TRANSFO_PROBA = float(v.get("ATELIER_TRANSFO_PROBA", ATELIER_TRANSFO_PROBA))
	STOCK_CIBLE_DEFAUT   = int(v.get("STOCK_CIBLE_DEFAUT", STOCK_CIBLE_DEFAUT))
	PRIX_AMPLITUDE_STOCK = float(v.get("PRIX_AMPLITUDE_STOCK", PRIX_AMPLITUDE_STOCK))
	VENTE_PNJ_PROBA      = float(v.get("VENTE_PNJ_PROBA", VENTE_PNJ_PROBA))
	VENTE_PNJ_FRACTION   = float(v.get("VENTE_PNJ_FRACTION", VENTE_PNJ_FRACTION))

	CRIT_REUSSITE_MAX            = int(v.get("CRIT_REUSSITE_MAX", CRIT_REUSSITE_MAX))
	CRIT_ECHEC_MIN               = int(v.get("CRIT_ECHEC_MIN", CRIT_ECHEC_MIN))
	RELATION_INITIALE            = int(v.get("RELATION_INITIALE", RELATION_INITIALE))
	RELATION_SEUIL_COEFF         = float(v.get("RELATION_SEUIL_COEFF", RELATION_SEUIL_COEFF))
	MARCHANDAGE_BLOCAGE_SECONDES = int(v.get("MARCHANDAGE_BLOCAGE_SECONDES", MARCHANDAGE_BLOCAGE_SECONDES))

	QUETE_BOARD_TAILLE  = int(v.get("QUETE_BOARD_TAILLE", QUETE_BOARD_TAILLE))
	QUETE_QTE_MIN       = int(v.get("QUETE_QTE_MIN", QUETE_QTE_MIN))
	QUETE_QTE_MAX       = int(v.get("QUETE_QTE_MAX", QUETE_QTE_MAX))
	QUETE_XP_FACTEUR    = float(v.get("QUETE_XP_FACTEUR", QUETE_XP_FACTEUR))
	QUETE_CUIVRE_PAR_XP = float(v.get("QUETE_CUIVRE_PAR_XP", QUETE_CUIVRE_PAR_XP))
	QUETE_COLLECT_POIDS_MAX = float(v.get("QUETE_COLLECT_POIDS_MAX", QUETE_COLLECT_POIDS_MAX))

	if isinstance(v.get("BOIS_A_COUPER"), list):
		BOIS_A_COUPER[:] = [str(x) for x in v["BOIS_A_COUPER"]]
	OUTIL_COUPE_BOIS_TAG = str(v.get("OUTIL_COUPE_BOIS_TAG", OUTIL_COUPE_BOIS_TAG))
	COUPE_MAX_PIECES     = int(v.get("COUPE_MAX_PIECES", COUPE_MAX_PIECES))

	return current_world_variables()


# ── Caractéristiques de base ──────────────────────────────────────────────────

class BaseStats(BaseModel):
	"""Caractéristiques de base saisies à la création / augmentées par XP."""
	v:   int = Field(0, ge=0, description="Vitesse")
	f:   int = Field(0, ge=0, description="Force")
	r:   int = Field(0, ge=0, description="Résistance")
	ag:  int = Field(0, ge=0, description="Agilité")
	vol: int = Field(0, ge=0, description="Volonté")
	int_: int = Field(0, ge=0, alias="int", description="Intelligence")
	cha: int = Field(0, ge=0, description="Charisme")
	ch:  int = Field(0, ge=0, description="Chance")

	model_config = {"populate_by_name": True}


# ── Bonus d'équipement ────────────────────────────────────────────────────────

class EquipmentBonus(BaseModel):
	"""Bonus cumulés de tous les équipements portés."""
	pv:			int = 0	# Bonus PV (objets magiques)
	pm:			int = 0	# Bonus PM
	pa:			int = 0	# Valeur d'armure totale
	malus_depl:	int = 0	# Malus de déplacement (armure lourde)
	cc_bonus:	  int = 0	# Bonus attaque CàC (arme)
	cd_bonus:	  int = 0	# Bonus attaque distance (arme)
	degats_bonus:  int = 0	# Bonus dégâts plat (arme) : +x
	degats_dice:   str = ""   # Dés de dégâts additionnels (arme) : ex "1D4", "1D4+1D6"
	initiative:	int = 0	# Bonus initiative (objets)


# ── Stats dérivées calculées ──────────────────────────────────────────────────

class DerivedStats(BaseModel):
	"""Stats calculées — jamais stockées en base, toujours recalculées."""

	# Points de ressources
	pv_max:	int
	pm_max:	int

	# Combat
	initiative:  int
	deplacement: int   # cases par action
	cc:		  int   # compétence corps à corps
	cd:		  int   # compétence à distance
	pa:		  int   # points d'armure
	pm_def:	  int   # défense magique
	degats_cc:   str   # ex: "1D6+3"
	degats_cd:   str   # ex: "1D4+1"

	# Divers
	charge_max:  int   # kg
	xp_cout_niv: int   # coût XP pour monter au prochain niveau

def compute_derived_stats(
	base:	  BaseStats,
	niveau:	int,
	equipment: EquipmentBonus = EquipmentBonus(),
) -> DerivedStats:
	"""
	Calcule toutes les stats dérivées à partir des stats de base,
	du niveau et de l'équipement.
	"""
	# ── PV max ──────────────────────────────────────────────────────
	pv_max = (base.r * 3) + base.f + equipment.pv

	# ── PM max ──────────────────────────────────────────────────────
	pm_max = (base.vol * 2) + (base.int_ * 2) + equipment.pm

	# ── Initiative ──────────────────────────────────────────────────
	initiative = base.ag + base.v + equipment.initiative

	# ── Déplacement ─────────────────────────────────────────────────
	deplacement = max(1, base.v - equipment.malus_depl)

	# ── Corps à corps ────────────────────────────────────────────────
	cc = base.f + (base.ag // 2) + equipment.cc_bonus

	# ── À distance ──────────────────────────────────────────────────
	cd = base.ag + (base.v // 2) + equipment.cd_bonus

	# ── Armure ───────────────────────────────────────────────────────
	pa = (base.r // FACTEUR_DEGATS_ARMURE) + equipment.pa

	# ── Défense magique ───────────────────────────────────────────────
	pm_def = (base.vol // 2) + (base.int_ // 4)

	# ── Dégâts corps à corps ─────────────────────────────────────────
	# Bonus de puissance F//FACTEUR, miroir exact des PA = R//FACTEUR : deux builds
	# de caractéristiques égales s'annulent, et ce sont les armes (+x / +1DX) qui
	# font la différence de dégâts.
	degats_cc = _format_damage(
		_caract_to_dice_(base.f), base.f // FACTEUR_DEGATS_ARMURE, equipment
	)

	# ── Dégâts à distance ─────────────────────────────────────────────
	# Même logique : la puissance du tir suit l'Ag (Ag//FACTEUR), miroir des PA.
	degats_cd = _format_damage(
		_caract_to_dice_(base.ag), base.ag // FACTEUR_DEGATS_ARMURE, equipment
	)

	# ── Charge max ────────────────────────────────────────────────────
	charge_max = base.f * 5

	# ── Coût XP niveau suivant ────────────────────────────────────────
	# Règle Légende : niveau cible × 5 PEX
	xp_cout_niv = (niveau + 1) * 5

	return DerivedStats(
		pv_max=pv_max,
		pm_max=pm_max,
		initiative=initiative,
		deplacement=deplacement,
		cc=cc,
		cd=cd,
		pa=pa,
		pm_def=pm_def,
		degats_cc=degats_cc,
		degats_cd=degats_cd,
		charge_max=charge_max,
		xp_cout_niv=xp_cout_niv,
	)

def compute_xp_cost(stat_key: str, from_val: int, to_val: int, race_min: int) -> int:
	"""
	Coût total en XP pour passer `stat_key` de `from_val` à `to_val`.
	Coût marginal de N→N+1 = (N+1 - race_min) × coeff.
	"""
	if to_val <= from_val:
		return 0
	coeff = XP_COEFF.get(stat_key, 1)
	return sum((n + 1 - race_min) * coeff for n in range(from_val, to_val))

def compute_stat_cap(
	stat_key:		   str,
	stats_max:		  dict,
	nb_max_accessibles: int,
	current_stats:	  dict,
	max_bonus:		  dict | None = None,
	max_bonus_used:	 str | None = None,
) -> int:
	"""
	Retourne le plafond effectif d'une stat pour ce personnage.

	- Si la race a un max_bonus et que ce stat est celui utilisé → stats_max + bonus.
	- Si le quota d'accessibilité n'est pas plein → stats_max normal.
	- Sinon → stats_max - 1 (V) ou stats_max - 10 (autres).
	"""
	absolute_max = stats_max.get(stat_key, 0)

	# Bonus racial activé sur cette stat (règle humain)
	if max_bonus_used == stat_key and max_bonus:
		return absolute_max + max_bonus.get(stat_key, 0)

	# Compter les stats déjà au max racial
	nb_at_max = sum(
		1 for k, v in current_stats.items()
		if v >= stats_max.get(k, 0)
	)

	# Cette stat est déjà au max → son plafond reste absolute_max
	if current_stats.get(stat_key, 0) >= absolute_max:
		return absolute_max

	# Quota non atteint → peut monter jusqu'au max racial
	if nb_at_max < nb_max_accessibles:
		return absolute_max

	# Quota plein → sous-plafond
	reduction = _SUB_CAP_REDUCTION.get(stat_key, 10)
	return max(0, absolute_max - reduction)


def compute_character_level(xp_total: int) -> int:
	"""Niveau personnage basé sur l'XP totale. Seuils : >10→1, >30→2, >90→3, … (×3 à chaque palier)."""
	niveau, threshold = 0, 10
	while xp_total > threshold:
		niveau += 1
		threshold *= 3
	return niveau


def _format_damage(base_die: int, stat_bonus: int, equipment: EquipmentBonus) -> str:
	"""Assemble la notation de dégâts : dé de base + dés d'arme + modificateur plat.

	- `base_die`	: dé dérivé de la caractéristique (F au CàC, Ag au tir).
	- `stat_bonus`  : bonus de puissance physique = caract // FACTEUR (miroir des PA).
	- `equipment.degats_dice` : dés additionnels de l'arme (+1DX), concaténables.
	- `equipment.degats_bonus`: modificateur plat de l'arme (+x).

	Ex : F=24 sans arme → "1D6+1" ; avec une épée +1 et +1D4 → "1D6+1D4+2".
	"""
	expr = f"1D{base_die}"
	if equipment.degats_dice:
		expr += f"+{equipment.degats_dice}"
	flat = stat_bonus + equipment.degats_bonus
	if flat:
		expr += f"{flat:+d}"
	return expr


def _caract_to_dice_(f: int) -> int:
	"""Convertit une caracteristique en valeur de dé standard."""
	if f <= 20:  return 4
	if f <= 40:  return 6
	if f <= 60:  return 8
	if f <= 80:  return 10
	if f <= 90:  return 12
	return 20

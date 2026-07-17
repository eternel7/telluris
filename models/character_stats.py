# models/character_stats.py
# Modèles Pydantic pour les stats de personnage Telluris / Légende

from pydantic import BaseModel, Field
import math
import re

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
# Facteur multipliant la distance entre 2 protagoniste dont l'un est furtif. 
# Le resultat obtenu vient augmenté la difficulte du jet de detection
DETECTION_DISTANCE_FACTEUR: int = 5

# XP gagnée à la découverte d'un lieu (fallback si le lieu n'a pas de xp_decouverte).
XP_DECOUVERTE_LIEU: int = 10

# Progression de niveau (suite arithmétique, remplace les ex-seuils ×3) : le passage au
# niveau n coûte XP_NIVEAU_BASE + (n−1)·XP_NIVEAU_INCREMENT. Avec les défauts 50/100 :
# coûts par niveau 50, 150, 250, … → XP cumulée quadratique 50, 200, 450, 800, 1250…
# INCREMENT > 0 garantit chaque niveau strictement plus cher que le précédent ;
# INCREMENT = 0 → coût constant par niveau. Réglable à chaud (world-vars).
XP_NIVEAU_BASE: int = 50
XP_NIVEAU_INCREMENT: int = 100

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
# ── Approvisionnement des ateliers (au tick) ─────────────────────────────────────
# Ce qu'un marchand achète au joueur ET les matières « feuilles » à auto-approvisionner ne
# sont PLUS des world-vars : ils sont DÉRIVÉS des recettes (`recette:*`, champ `lieu_categorie`
# + matières d'entrée) par `utils/marche.py` (`besoins_categorie` / `appro_leaves_categorie`).
# Seul reste réglable ici le **débit/tick** de l'appro (que les recettes n'encodent pas) :
# à chaque `tick_atelier` (vente/visite), chaque feuille consommée par les recettes du lieu
# (entrée jamais produite, hors `carcasse`) est injectée à `APPRO_DEBIT[sous_cat]` unités
# (sinon `APPRO_DEBIT_DEFAUT`). En pratique : les métaux pour l'armurerie. Un débit à 0
# désactive l'appro de la matière (garde `q > 0`) : `herbe` et `seve` restent fournies
# par la récolte des joueurs, pas par l'atelier.
APPRO_DEBIT: dict[str, int] = {"fer": 5, "acier": 3, "bronze": 5, "mithril": 1, "herbe": 0, "seve": 0}
APPRO_DEBIT_DEFAUT: int = 5

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
# Rachat : un lieu rachète au joueur les biens qu'il produit, dans une bande plafonnée à son
# coût de revient `pmin` → `[round(pmin × RACHAT_FACTEUR), pmin]` (garantit rachat ≤ pmin ≤ prix
# de vente, quelle que soit la relation). `RACHAT_FACTEUR` ∈ ]0,1] = plancher de la bande.
RACHAT_FACTEUR: float = 0.6

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
# Seuil de « bonne réputation » par défaut pour les PNJ (services gratuits/améliorés,
# conditions de dialogue relation_min) — 70 = palier « Estimé ». Surchargable par PNJ
# dans la donnée (`gratuit_si.seuil`, `condition.relation_min.seuil`).
PNJ_REPUTATION_SEUIL: int = 70

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
# Durée de vie d'une offre GÉNÉRÉE au tableau : passé son terme, elle est réputée prise par
# un autre aventurier — son doc est supprimé et une nouvelle offre la remplace (péremption
# PARESSEUSE, évaluée à l'ouverture du tableau). Les 6 offres naissant au même instant, un
# délai fixe ferait basculer tout le tableau d'un bloc : la durée effective est donc tirée
# dans [D × (1 − JITTER), D × (1 + JITTER)] → le tableau tourne par petites touches.
# JITTER = 0 → durée fixe (bascule en bloc).
QUETE_BOARD_DUREE_SECONDES: int = 3600
QUETE_BOARD_DUREE_JITTER: float = 0.5

# ── Quêtes de transport (magasins) ───────────────────────────────────────────────
# À chaque ENTRÉE dans un lieu marchand, le tenancier a QUETE_TRANSPORT_PROBA de chance
# de proposer une course : livrer une cargaison à un autre magasin qui rachète ces biens,
# en QUETE_TRANSPORT_DUREE_SECONDES de temps RÉEL. La cargaison est bornée par DEUX
# contraintes (poids cumulé ET nombre d'objets) : on empile les instances une à une et on
# s'arrête dès que l'ajout suivant franchirait l'une d'elles.
# Récompense : QUETE_TRANSPORT_XP (× (1 + distance) si la destination est dans une autre
# ville) + une prime de round(xp × QUETE_CUIVRE_PAR_XP). Réussite → +QUETE_TRANSPORT_RELATION_DELTA
# de relation avec le magasin donneur ; échec (délai dépassé) ou abandon → −autant.
QUETE_TRANSPORT_PROBA: float = 0.30
QUETE_TRANSPORT_DUREE_SECONDES: int = 3600
QUETE_TRANSPORT_POIDS_MAX: float = 100.0
QUETE_TRANSPORT_NB_MAX: int = 10
QUETE_TRANSPORT_XP: int = 10
QUETE_TRANSPORT_RELATION_DELTA: int = 1
# On ne confie pas sa marchandise à quelqu'un qu'on voit d'un mauvais œil : sous ce seuil de
# relation, le tenancier ne propose AUCUNE course générée (0 = garde-fou désactivé). Ne concerne
# pas les courses ÉCRITES (`services.transport.offre`), que le scénario décide de confier.
QUETE_TRANSPORT_RELATION_MIN: int = 50
# À la livraison, chaque objet a cette chance de finir en RAYON (`stock_vente`) du magasin
# destinataire — à condition qu'il vende ce produit (`lieu_produit`). Le reste part à
# l'atelier / à la consommation : la course a donc un effet visible mais partiel sur l'étal.
QUETE_TRANSPORT_STOCK_PROBA: float = 0.50

# ── Quêtes de chasse (élite à profil élevé) + rang de guilde ─────────────────────
# Traquer UN ennemi marqué d'un profil élevé dans un lieu précis. L'élite valant bien plus
# qu'un individu normal, son XP est majorée : xp = round(xp_unitaire × QUETE_CHASSE_XP_FACTEUR)
# (cuivre via QUETE_CUIVRE_PAR_XP). À l'entrée d'un COMPTOIR de guilde avec PNJ présent,
# QUETE_CHASSE_PROBA_RANG donne la chance de se voir proposer une épreuve de rang (grade `max`).
QUETE_CHASSE_XP_FACTEUR: float = 3.0
QUETE_CHASSE_PROBA_RANG: float = 0.5

# ── Focalisation ─────────────────────────────────────────────────────────────────
# Le personnage peut se focaliser sur une quête active : les tirages aléatoires sont
# biaisés vers son objectif. FOCUS_EVENEMENT_MULT multiplie le poids des entrées de
# `table_evenements` du type visé (combat pour kill, ressource pour collect) quand la
# cible est présente dans une zone active ; FOCUS_CIBLE_MULT multiplie le poids de la
# cible elle-même dans le tirage (espèce dans le pool de combat, item dans la récolte).
FOCUS_EVENEMENT_MULT: float = 3.0
FOCUS_CIBLE_MULT: float = 3.0

# ── Sorts (magie) ────────────────────────────────────────────────────────────────
# Apprendre un sort coûte des points de caractéristique : (niveau_sort + 1) × SORT_COUT_COEFF
# (miroir de spend_xp_vocation), à condition de porter le grimoire qui l'enseigne et d'avoir
# le niveau de vocation requis. SORT_VOCATIONS_DEPART = vocations « pures magiciennes » qui
# choisissent UN sort gratuit (parmi les niveau 0 de leur vocation) à la création du perso.
SORT_COUT_COEFF: int = 2
SORT_VOCATIONS_DEPART: list = [
	"elementaliste", "mage", "illusionniste", "lettre", "druide",
	"chaman", "pretre", "necromancien", "demoniste",
]
# Accès aux sorts par ÉCOLE de magie. Les vocations polyvalentes (le lettré, « érudit
# universel ») peuvent ACHETER la pratique d'autres écoles avec des points de
# caractéristique — coût (niveau_ecole + 1) × MAGIE_ECOLE_COUT_COEFF (miroir des sorts).
# Chaque école achetée a son propre niveau (character["magies_apprises"]), monté
# séparément, sans impact sur les stats dérivées. Les spécialistes restent sur leur école
# native. Une école native se monte via spend_xp_vocation (vocations_niveaux).
MAGIE_POLYVALENTE_VOCATIONS: list = ["lettre"]
MAGIE_ECOLE_COUT_COEFF: int = 2

# ── Compétences (vocation) ───────────────────────────────────────────────────────
# Miroir des sorts pour les vocations non magiciennes : un doc `competence:*` porte une
# vocation, un niveau, un mode (passive/active) et des `effets` au même format. Apprendre
# une compétence coûte (niveau + 1) × COMPETENCE_COUT_COEFF points de caractéristique.
# Les vocations qui choisissent une compétence de niveau 0 à la création sont le COMPLÉMENT
# de SORT_VOCATIONS_DEPART (règle dérivée : on choisit un sort OU une compétence, jamais
# les deux) — pas de liste à maintenir en double.
COMPETENCE_COUT_COEFF: int = 2

# ── Recrutement d'aventuriers & compagnons ───────────────────────────────────────
# Un lieu recruteur (tag "recrutement" ou guilde d'aventuriers) affiche un tableau de
# recrues générées (docs `aventurier:*`, miroir du character). L'offre dépend de la
# taille de la cité : table par `sous_categorie` du lieu_parent (repli "defaut"),
# surchargeable champ à champ par `lieu.recrutement_restrictions`. Une recrue offerte
# a une durée de vie jittée (même rotation paresseuse que le tableau de quêtes).
# Une recrue exige une PART du butin : % prélevé sur le cuivre des récompenses de
# quête au turn-in (tirée dans [MIN, MAX], biaisée haut avec le niveau), réduite par
# l'affinité (1 pt de part par AFFINITE_REDUC_PART pts d'affinité au-dessus de 50).
# CARTE_REQUISE : le tableau n'est visible qu'avec la carte d'aventurier de la cité
# en sac. CAUTION_CUIVRE = porte de la phase 2 (compagnie permanente), inerte à 0.
RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE: dict[str, dict] = {
	"capitale": {"nb": 6, "niveau_max": 3},
	"ville":    {"nb": 4, "niveau_max": 2},
	"defaut":   {"nb": 2, "niveau_max": 1},
}
RECRUTEMENT_GROUPE_TAILLE_MAX: int = 2
RECRUTEMENT_BOARD_DUREE_SECONDES: int = 7200
RECRUTEMENT_BOARD_DUREE_JITTER: float = 0.5
RECRUTEMENT_PART_BUTIN_MIN: int = 10
RECRUTEMENT_PART_BUTIN_MAX: int = 30
RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU: int = 6
RECRUTEMENT_CARTE_REQUISE: bool = True
RECRUTEMENT_CAUTION_CUIVRE: int = 0
# Affinité perso×compagnon (0-100, neutre 50) — même échelle que les relations de lieu.
# Mémorisée sur le character (`affinites`), elle survit au congédiement : un ancien
# compagnon apprécié (≥ SEUIL_REMISE) réapparaît au tableau de son giver ; sous
# SEUIL_DEPART, un compagnon actif quitte le groupe de lui-même.
AFFINITE_INITIALE: int = 50
AFFINITE_DELTA_QUETE: int = 2
AFFINITE_DELTA_VICTOIRE: int = 1
AFFINITE_DELTA_KO: int = -5
AFFINITE_DELTA_CONGEDIE: int = -1
AFFINITE_DELTA_CONGEDIE_EN_QUETE: int = -3
AFFINITE_SEUIL_DEPART: int = 30
AFFINITE_SEUIL_REMISE: int = 60
AFFINITE_REDUC_PART: int = 10

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
# Une entrée peut être une sous-catégorie (cas courant) OU une clé item-ref `item:*`
# pour cibler un item précis (ex. `item:Sang_demon_seche` sur `demon`) : elle circule
# telle quelle jusqu'au rayon (matiere_item_id la laisse intacte), sans passer par la
# résolution sous_cat→item.
DEPECAGE_TAGS: dict[str, list] = {
	"_charnu_base": [
	  "viande",
	  "viande",
	  "os",
	  "sang",
	  "graisse",
	  "tendons"
	],
	"animal": [
	  "cuir_brut",
	  "crocs",
	  "poils",
	  "tendons"
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
	  "crins",
	  "tendons"
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
	  "coeur",
	  "item:Sang_demon_seche"
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
	  "coeur",
	  "tendons"
	],
	"vol": [
	  "plumes",
	  "griffes"
	],
	"venin": [
	  "crocs"
	],
	"foret": [
	  "poils",
	  "tendons"
	],
	"froid": [
	  "poils",
	  "tendons"
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
		"DETECTION_DISTANCE_FACTEUR": DETECTION_DISTANCE_FACTEUR,
		"XP_DECOUVERTE_LIEU": XP_DECOUVERTE_LIEU,
		"XP_NIVEAU_BASE": XP_NIVEAU_BASE,
		"XP_NIVEAU_INCREMENT": XP_NIVEAU_INCREMENT,
		"TOWN_PROFIL_NIVEAU_MAX": TOWN_PROFIL_NIVEAU_MAX,
		"XP_COEFF": dict(XP_COEFF),
		"XP_VOC_COEFF": XP_VOC_COEFF,
		"SUB_CAP_REDUCTION": dict(_SUB_CAP_REDUCTION),
		"PRIX_DERIVE_BASE": PRIX_DERIVE_BASE,
		"MULT_RARETE": dict(MULT_RARETE),
		"APPRO_DEBIT": dict(APPRO_DEBIT),
		"APPRO_DEBIT_DEFAUT": APPRO_DEBIT_DEFAUT,
		"CHA_MARCHAND": CHA_MARCHAND,
		"CHA_MARCHAND_PAR_CATEGORIE": dict(CHA_MARCHAND_PAR_CATEGORIE),
		"PRIX_MAX_FACTEUR": PRIX_MAX_FACTEUR,
		"MARGE_TRANSFO": MARGE_TRANSFO,
		"RACHAT_FACTEUR": RACHAT_FACTEUR,
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
		"PNJ_REPUTATION_SEUIL": PNJ_REPUTATION_SEUIL,
		"QUETE_BOARD_TAILLE": QUETE_BOARD_TAILLE,
		"QUETE_QTE_MIN": QUETE_QTE_MIN,
		"QUETE_QTE_MAX": QUETE_QTE_MAX,
		"QUETE_XP_FACTEUR": QUETE_XP_FACTEUR,
		"QUETE_CUIVRE_PAR_XP": QUETE_CUIVRE_PAR_XP,
		"QUETE_COLLECT_POIDS_MAX": QUETE_COLLECT_POIDS_MAX,
		"QUETE_BOARD_DUREE_SECONDES": QUETE_BOARD_DUREE_SECONDES,
		"QUETE_BOARD_DUREE_JITTER": QUETE_BOARD_DUREE_JITTER,
		"QUETE_TRANSPORT_PROBA": QUETE_TRANSPORT_PROBA,
		"QUETE_TRANSPORT_DUREE_SECONDES": QUETE_TRANSPORT_DUREE_SECONDES,
		"QUETE_TRANSPORT_POIDS_MAX": QUETE_TRANSPORT_POIDS_MAX,
		"QUETE_TRANSPORT_NB_MAX": QUETE_TRANSPORT_NB_MAX,
		"QUETE_TRANSPORT_XP": QUETE_TRANSPORT_XP,
		"QUETE_TRANSPORT_RELATION_DELTA": QUETE_TRANSPORT_RELATION_DELTA,
		"QUETE_TRANSPORT_RELATION_MIN": QUETE_TRANSPORT_RELATION_MIN,
		"QUETE_TRANSPORT_STOCK_PROBA": QUETE_TRANSPORT_STOCK_PROBA,
		"QUETE_CHASSE_XP_FACTEUR": QUETE_CHASSE_XP_FACTEUR,
		"QUETE_CHASSE_PROBA_RANG": QUETE_CHASSE_PROBA_RANG,
		"FOCUS_EVENEMENT_MULT": FOCUS_EVENEMENT_MULT,
		"FOCUS_CIBLE_MULT": FOCUS_CIBLE_MULT,
		"SORT_COUT_COEFF": SORT_COUT_COEFF,
		"SORT_VOCATIONS_DEPART": list(SORT_VOCATIONS_DEPART),
		"MAGIE_POLYVALENTE_VOCATIONS": list(MAGIE_POLYVALENTE_VOCATIONS),
		"MAGIE_ECOLE_COUT_COEFF": MAGIE_ECOLE_COUT_COEFF,
		"COMPETENCE_COUT_COEFF": COMPETENCE_COUT_COEFF,
		"RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE": {k: dict(v) for k, v in RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE.items()},
		"RECRUTEMENT_GROUPE_TAILLE_MAX": RECRUTEMENT_GROUPE_TAILLE_MAX,
		"RECRUTEMENT_BOARD_DUREE_SECONDES": RECRUTEMENT_BOARD_DUREE_SECONDES,
		"RECRUTEMENT_BOARD_DUREE_JITTER": RECRUTEMENT_BOARD_DUREE_JITTER,
		"RECRUTEMENT_PART_BUTIN_MIN": RECRUTEMENT_PART_BUTIN_MIN,
		"RECRUTEMENT_PART_BUTIN_MAX": RECRUTEMENT_PART_BUTIN_MAX,
		"RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU": RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU,
		"RECRUTEMENT_CARTE_REQUISE": RECRUTEMENT_CARTE_REQUISE,
		"RECRUTEMENT_CAUTION_CUIVRE": RECRUTEMENT_CAUTION_CUIVRE,
		"AFFINITE_INITIALE": AFFINITE_INITIALE,
		"AFFINITE_DELTA_QUETE": AFFINITE_DELTA_QUETE,
		"AFFINITE_DELTA_VICTOIRE": AFFINITE_DELTA_VICTOIRE,
		"AFFINITE_DELTA_KO": AFFINITE_DELTA_KO,
		"AFFINITE_DELTA_CONGEDIE": AFFINITE_DELTA_CONGEDIE,
		"AFFINITE_DELTA_CONGEDIE_EN_QUETE": AFFINITE_DELTA_CONGEDIE_EN_QUETE,
		"AFFINITE_SEUIL_DEPART": AFFINITE_SEUIL_DEPART,
		"AFFINITE_SEUIL_REMISE": AFFINITE_SEUIL_REMISE,
		"AFFINITE_REDUC_PART": AFFINITE_REDUC_PART,
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
	global FACTEUR_DEGATS_ARMURE, JET_PORTEE_F_DIV, DETECTION_DISTANCE_FACTEUR, XP_DECOUVERTE_LIEU, TOWN_PROFIL_NIVEAU_MAX, XP_VOC_COEFF, PRIX_DERIVE_BASE
	global XP_NIVEAU_BASE, XP_NIVEAU_INCREMENT
	global CHA_MARCHAND, PRIX_MAX_FACTEUR, MARGE_TRANSFO, RACHAT_FACTEUR, DEPECAGE_POIDS_REF, ATELIER_TRANSFO_PROBA, APPRO_DEBIT_DEFAUT
	global STOCK_CIBLE_DEFAUT, PRIX_AMPLITUDE_STOCK, VENTE_PNJ_PROBA, VENTE_PNJ_FRACTION
	global CRIT_REUSSITE_MAX, CRIT_ECHEC_MIN
	global RELATION_INITIALE, RELATION_SEUIL_COEFF, MARCHANDAGE_BLOCAGE_SECONDES
	global PNJ_REPUTATION_SEUIL
	global QUETE_BOARD_TAILLE, QUETE_QTE_MIN, QUETE_QTE_MAX, QUETE_XP_FACTEUR, QUETE_CUIVRE_PAR_XP
	global QUETE_COLLECT_POIDS_MAX, QUETE_BOARD_DUREE_SECONDES, QUETE_BOARD_DUREE_JITTER
	global QUETE_TRANSPORT_PROBA, QUETE_TRANSPORT_DUREE_SECONDES, QUETE_TRANSPORT_POIDS_MAX
	global QUETE_TRANSPORT_NB_MAX, QUETE_TRANSPORT_XP, QUETE_TRANSPORT_RELATION_DELTA
	global QUETE_TRANSPORT_STOCK_PROBA, QUETE_TRANSPORT_RELATION_MIN
	global QUETE_CHASSE_XP_FACTEUR, QUETE_CHASSE_PROBA_RANG
	global FOCUS_EVENEMENT_MULT, FOCUS_CIBLE_MULT
	global SORT_COUT_COEFF, MAGIE_ECOLE_COUT_COEFF, COMPETENCE_COUT_COEFF
	global RECRUTEMENT_GROUPE_TAILLE_MAX, RECRUTEMENT_BOARD_DUREE_SECONDES, RECRUTEMENT_BOARD_DUREE_JITTER
	global RECRUTEMENT_PART_BUTIN_MIN, RECRUTEMENT_PART_BUTIN_MAX, RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU
	global RECRUTEMENT_CARTE_REQUISE, RECRUTEMENT_CAUTION_CUIVRE
	global AFFINITE_INITIALE, AFFINITE_DELTA_QUETE, AFFINITE_DELTA_VICTOIRE, AFFINITE_DELTA_KO
	global AFFINITE_DELTA_CONGEDIE, AFFINITE_DELTA_CONGEDIE_EN_QUETE
	global AFFINITE_SEUIL_DEPART, AFFINITE_SEUIL_REMISE, AFFINITE_REDUC_PART
	global OUTIL_COUPE_BOIS_TAG, COUPE_MAX_PIECES
	try:
		from db.config import get_doc  # import paresseux : pas de dépendance DB à l'import
		doc = get_doc(WORLD_VARIABLES_DOC_ID)
	except Exception:
		doc = None
	v = (doc or {}).get("value") or {}

	FACTEUR_DEGATS_ARMURE      = int(v.get("FACTEUR_DEGATS_ARMURE", FACTEUR_DEGATS_ARMURE))
	JET_PORTEE_F_DIV           = max(1, int(v.get("JET_PORTEE_F_DIV", JET_PORTEE_F_DIV)))
	DETECTION_DISTANCE_FACTEUR = max(0, int(v.get("DETECTION_DISTANCE_FACTEUR", DETECTION_DISTANCE_FACTEUR)))
	XP_DECOUVERTE_LIEU         = int(v.get("XP_DECOUVERTE_LIEU", XP_DECOUVERTE_LIEU))
	XP_NIVEAU_BASE             = max(1, int(v.get("XP_NIVEAU_BASE", XP_NIVEAU_BASE)))
	XP_NIVEAU_INCREMENT        = max(0, int(v.get("XP_NIVEAU_INCREMENT", XP_NIVEAU_INCREMENT)))
	TOWN_PROFIL_NIVEAU_MAX     = int(v.get("TOWN_PROFIL_NIVEAU_MAX", TOWN_PROFIL_NIVEAU_MAX))
	XP_VOC_COEFF               = int(v.get("XP_VOC_COEFF", XP_VOC_COEFF))
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
	if isinstance(v.get("APPRO_DEBIT"), dict):
		APPRO_DEBIT.clear()
		APPRO_DEBIT.update({k: int(x) for k, x in v["APPRO_DEBIT"].items()})
	APPRO_DEBIT_DEFAUT = int(v.get("APPRO_DEBIT_DEFAUT", APPRO_DEBIT_DEFAUT))

	CHA_MARCHAND     = int(v.get("CHA_MARCHAND", CHA_MARCHAND))
	PRIX_MAX_FACTEUR = float(v.get("PRIX_MAX_FACTEUR", PRIX_MAX_FACTEUR))
	MARGE_TRANSFO    = float(v.get("MARGE_TRANSFO", MARGE_TRANSFO))
	RACHAT_FACTEUR   = float(v.get("RACHAT_FACTEUR", RACHAT_FACTEUR))
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
	PNJ_REPUTATION_SEUIL         = int(v.get("PNJ_REPUTATION_SEUIL", PNJ_REPUTATION_SEUIL))

	QUETE_BOARD_TAILLE  = int(v.get("QUETE_BOARD_TAILLE", QUETE_BOARD_TAILLE))
	QUETE_QTE_MIN       = int(v.get("QUETE_QTE_MIN", QUETE_QTE_MIN))
	QUETE_QTE_MAX       = int(v.get("QUETE_QTE_MAX", QUETE_QTE_MAX))
	QUETE_XP_FACTEUR    = float(v.get("QUETE_XP_FACTEUR", QUETE_XP_FACTEUR))
	QUETE_CUIVRE_PAR_XP = float(v.get("QUETE_CUIVRE_PAR_XP", QUETE_CUIVRE_PAR_XP))
	QUETE_COLLECT_POIDS_MAX = float(v.get("QUETE_COLLECT_POIDS_MAX", QUETE_COLLECT_POIDS_MAX))
	QUETE_BOARD_DUREE_SECONDES = int(v.get("QUETE_BOARD_DUREE_SECONDES", QUETE_BOARD_DUREE_SECONDES))
	QUETE_BOARD_DUREE_JITTER = float(v.get("QUETE_BOARD_DUREE_JITTER", QUETE_BOARD_DUREE_JITTER))
	QUETE_TRANSPORT_PROBA   = float(v.get("QUETE_TRANSPORT_PROBA", QUETE_TRANSPORT_PROBA))
	QUETE_TRANSPORT_DUREE_SECONDES = int(v.get("QUETE_TRANSPORT_DUREE_SECONDES", QUETE_TRANSPORT_DUREE_SECONDES))
	QUETE_TRANSPORT_POIDS_MAX = float(v.get("QUETE_TRANSPORT_POIDS_MAX", QUETE_TRANSPORT_POIDS_MAX))
	QUETE_TRANSPORT_NB_MAX  = int(v.get("QUETE_TRANSPORT_NB_MAX", QUETE_TRANSPORT_NB_MAX))
	QUETE_TRANSPORT_XP      = int(v.get("QUETE_TRANSPORT_XP", QUETE_TRANSPORT_XP))
	QUETE_TRANSPORT_RELATION_DELTA = int(v.get("QUETE_TRANSPORT_RELATION_DELTA", QUETE_TRANSPORT_RELATION_DELTA))
	QUETE_TRANSPORT_RELATION_MIN = int(v.get("QUETE_TRANSPORT_RELATION_MIN", QUETE_TRANSPORT_RELATION_MIN))
	QUETE_TRANSPORT_STOCK_PROBA = float(v.get("QUETE_TRANSPORT_STOCK_PROBA", QUETE_TRANSPORT_STOCK_PROBA))
	QUETE_CHASSE_XP_FACTEUR = float(v.get("QUETE_CHASSE_XP_FACTEUR", QUETE_CHASSE_XP_FACTEUR))
	QUETE_CHASSE_PROBA_RANG = float(v.get("QUETE_CHASSE_PROBA_RANG", QUETE_CHASSE_PROBA_RANG))

	FOCUS_EVENEMENT_MULT = float(v.get("FOCUS_EVENEMENT_MULT", FOCUS_EVENEMENT_MULT))
	FOCUS_CIBLE_MULT     = float(v.get("FOCUS_CIBLE_MULT", FOCUS_CIBLE_MULT))

	SORT_COUT_COEFF = max(0, int(v.get("SORT_COUT_COEFF", SORT_COUT_COEFF)))
	if isinstance(v.get("SORT_VOCATIONS_DEPART"), list):
		SORT_VOCATIONS_DEPART[:] = [str(x) for x in v["SORT_VOCATIONS_DEPART"]]
	MAGIE_ECOLE_COUT_COEFF = max(0, int(v.get("MAGIE_ECOLE_COUT_COEFF", MAGIE_ECOLE_COUT_COEFF)))
	if isinstance(v.get("MAGIE_POLYVALENTE_VOCATIONS"), list):
		MAGIE_POLYVALENTE_VOCATIONS[:] = [str(x) for x in v["MAGIE_POLYVALENTE_VOCATIONS"]]
	COMPETENCE_COUT_COEFF = max(0, int(v.get("COMPETENCE_COUT_COEFF", COMPETENCE_COUT_COEFF)))

	if isinstance(v.get("RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE"), dict):
		RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE.clear()
		RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE.update({
			k: {"nb": int(x.get("nb", 0)), "niveau_max": int(x.get("niveau_max", 0))}
			for k, x in v["RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE"].items()
			if isinstance(x, dict)
		})
	RECRUTEMENT_GROUPE_TAILLE_MAX = max(0, int(v.get("RECRUTEMENT_GROUPE_TAILLE_MAX", RECRUTEMENT_GROUPE_TAILLE_MAX)))
	RECRUTEMENT_BOARD_DUREE_SECONDES = int(v.get("RECRUTEMENT_BOARD_DUREE_SECONDES", RECRUTEMENT_BOARD_DUREE_SECONDES))
	RECRUTEMENT_BOARD_DUREE_JITTER = float(v.get("RECRUTEMENT_BOARD_DUREE_JITTER", RECRUTEMENT_BOARD_DUREE_JITTER))
	RECRUTEMENT_PART_BUTIN_MIN = max(0, int(v.get("RECRUTEMENT_PART_BUTIN_MIN", RECRUTEMENT_PART_BUTIN_MIN)))
	RECRUTEMENT_PART_BUTIN_MAX = max(RECRUTEMENT_PART_BUTIN_MIN, int(v.get("RECRUTEMENT_PART_BUTIN_MAX", RECRUTEMENT_PART_BUTIN_MAX)))
	RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU = max(0, int(v.get("RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU", RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU)))
	RECRUTEMENT_CARTE_REQUISE = bool(v.get("RECRUTEMENT_CARTE_REQUISE", RECRUTEMENT_CARTE_REQUISE))
	RECRUTEMENT_CAUTION_CUIVRE = max(0, int(v.get("RECRUTEMENT_CAUTION_CUIVRE", RECRUTEMENT_CAUTION_CUIVRE)))
	AFFINITE_INITIALE = int(v.get("AFFINITE_INITIALE", AFFINITE_INITIALE))
	AFFINITE_DELTA_QUETE = int(v.get("AFFINITE_DELTA_QUETE", AFFINITE_DELTA_QUETE))
	AFFINITE_DELTA_VICTOIRE = int(v.get("AFFINITE_DELTA_VICTOIRE", AFFINITE_DELTA_VICTOIRE))
	AFFINITE_DELTA_KO = int(v.get("AFFINITE_DELTA_KO", AFFINITE_DELTA_KO))
	AFFINITE_DELTA_CONGEDIE = int(v.get("AFFINITE_DELTA_CONGEDIE", AFFINITE_DELTA_CONGEDIE))
	AFFINITE_DELTA_CONGEDIE_EN_QUETE = int(v.get("AFFINITE_DELTA_CONGEDIE_EN_QUETE", AFFINITE_DELTA_CONGEDIE_EN_QUETE))
	AFFINITE_SEUIL_DEPART = int(v.get("AFFINITE_SEUIL_DEPART", AFFINITE_SEUIL_DEPART))
	AFFINITE_SEUIL_REMISE = int(v.get("AFFINITE_SEUIL_REMISE", AFFINITE_SEUIL_REMISE))
	AFFINITE_REDUC_PART = max(1, int(v.get("AFFINITE_REDUC_PART", AFFINITE_REDUC_PART)))

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
	malus_depl:	int = 0	# Delta de V des armures (négatif = lourde) — replié dans `buffs`
	cc_bonus:	  int = 0	# Bonus attaque CàC (arme)
	cd_bonus:	  int = 0	# Bonus attaque distance (arme)
	degats_bonus:  int = 0	# Bonus dégâts plat (arme) : +x
	degats_dice:   str = ""   # Dés de dégâts additionnels (arme) : ex "1D4", "1D4+1D6"
	initiative:	int = 0	# Bonus initiative (objets)
	# Bonus de CARACTÉRISTIQUES (champ item `bonus` = {caract: delta}). Agrégé ici puis
	# replié par utils/consommables._sources_de_buffs comme n'importe quel buff : les
	# dérivées en profitent via BaseStats, sans double comptage avec les champs ci-dessus.
	buffs:		 dict[str, int] = Field(default_factory=dict)
	# Détail nommé du même agrégat, pour le tooltip de la fiche : [{nom, icon, buffs}].
	buffs_sources: list[dict] = Field(default_factory=list)


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
	toucher_magique: int   # compétence de lancer de sorts offensifs
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
	initiative = (base.ag + base.v*20) // 3 + equipment.initiative

	# ── Déplacement ─────────────────────────────────────────────────
	# `equipment.malus_depl` n'est PAS soustrait ici : c'est un delta sur V, replié dans
	# equipment.buffs par recompute_equipment_bonus, donc déjà présent dans `base.v` (et
	# pesant aussi sur l'initiative et le cd). Le soustraire une seconde fois le compterait
	# deux fois. Le champ reste exposé à titre informatif (fiche objet, marché).
	deplacement = max(1, base.v)

	# ── Corps à corps ────────────────────────────────────────────────
	cc = (base.f + (base.ag *3)) // 4 + equipment.cc_bonus

	# ── À distance ──────────────────────────────────────────────────
	cd = ((3*base.ag) + (base.v *10)) // 4 + equipment.cd_bonus

	# ── Armure ───────────────────────────────────────────────────────
	pa = (base.r // FACTEUR_DEGATS_ARMURE) + equipment.pa

	# ── Défense magique ───────────────────────────────────────────────
	pm_def = (base.vol // 2) + (base.int_ // 4)

	# ── Toucher magique ───────────────────────────────────────────────
	# Miroir de cc/cd (bande 0-100, échelle ×10) : Int porte la précision des
	# sorts (3:1), Vol l'appuie. Opposé au pm_def de la cible dans le jet.
	toucher_magique = ((base.int_ * 3) + base.vol) // 4

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
	# Aligné sur compute_character_level : passage au niveau n+1 = BASE + n·INCREMENT.
	xp_cout_niv = XP_NIVEAU_BASE + niveau * XP_NIVEAU_INCREMENT

	return DerivedStats(
		pv_max=pv_max,
		pm_max=pm_max,
		initiative=initiative,
		deplacement=deplacement,
		cc=cc,
		cd=cd,
		pa=pa,
		pm_def=pm_def,
		toucher_magique=toucher_magique,
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
	"""Niveau personnage basé sur l'XP totale. Le passage au niveau n coûte
	XP_NIVEAU_BASE + (n−1)·XP_NIVEAU_INCREMENT."""
	base = int(XP_NIVEAU_BASE)
	inc = int(XP_NIVEAU_INCREMENT)
	if base <= 0:
		return 0
	niveau, seuil = 0, base
	while xp_total > seuil:
		niveau += 1
		seuil += base + niveau * max(0, inc)
	return niveau


def xp_seuil_niveau(niveau: int) -> int:
	"""XP cumulée du seuil d'un niveau (formule fermée de la suite arithmétique) : le
	niveau n est acquis quand xp_total > xp_seuil_niveau(n) ; 0 pour le niveau 0.
	Sert à l'affichage (« Prochain niveau à X XP », barre de progression) — miroir de
	compute_character_level, garder les deux synchro."""
	n = max(0, int(niveau))
	return n * int(XP_NIVEAU_BASE) + max(0, int(XP_NIVEAU_INCREMENT)) * n * (n - 1) // 2


_DICE_RE = re.compile(r"(\d*)D(\d+)", re.IGNORECASE)


def normalize_dice(raw) -> str:
	"""Normalise le champ item `bonus_degats_dice` en notation complète.

	La donnée porte le plus souvent le seul NOMBRE DE FACES (`6` = un dé à 6 faces =
	"1D6") ; une notation déjà complète ("1D6", "2D4+1D6") est acceptée telle quelle.
	Sans cette normalisation, un `6` se retrouverait concaténé en "+6" — c.-à-d. lu comme
	un modificateur plat, à l'affichage comme au jet (roll_dice).
	"""
	if raw is None or raw == "":
		return ""
	if isinstance(raw, bool):
		return ""
	if isinstance(raw, (int, float)):
		faces = int(raw)
		return f"1D{faces}" if faces > 0 else ""
	s = str(raw).strip().upper().replace(" ", "")
	if not s:
		return ""
	if "D" not in s:
		try:
			faces = int(s)
		except ValueError:
			return ""
		return f"1D{faces}" if faces > 0 else ""
	return s


def _format_damage(base_die: int, stat_bonus: int, equipment: EquipmentBonus) -> str:
	"""Assemble la notation de dégâts : dé de base + dés d'arme + modificateur plat.

	- `base_die`	: dé dérivé de la caractéristique (F au CàC, Ag au tir).
	- `stat_bonus`  : bonus de puissance physique = caract // FACTEUR (miroir des PA).
	- `equipment.degats_dice` : dés additionnels de l'arme (+1DX), concaténables.
	- `equipment.degats_bonus`: modificateur plat de l'arme (+x).

	Les dés de MÊME taille sont regroupés (1D6 + 1D6 → "2D6"), dans l'ordre d'apparition
	(le dé de caract d'abord). Ex : F=24 sans arme → "1D6+1" ; avec une hache +4/+1D6 →
	"2D6+5" ; avec une épée +1/+1D4 → "1D6+1D4+2".
	"""
	dice: dict[int, int] = {base_die: 1}
	for n, sides in _DICE_RE.findall(equipment.degats_dice or ""):
		sides = int(sides)
		dice[sides] = dice.get(sides, 0) + int(n or "1")

	expr = "+".join(f"{count}D{sides}" for sides, count in dice.items())
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

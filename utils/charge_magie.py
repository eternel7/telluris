"""Charge portée → canalisation du mana (pur, aucune base).

Le poids n'est pas qu'une limite d'inventaire : c'est la contrainte que le corps subit
pendant qu'il manipule le mana. Plus on porte, plus les PM coûtent cher — jamais au point
d'interdire la magie, ce qui en ferait un mur au lieu d'un arbitrage.

    ratio = charge magique portée / capacité de portage
    pénalité de charge = f(ratio)                              (progressive, cf. `penalite_charge`)
    pénalité finale = pénalité × sensibilité du sort × modificateur de canalisation
    coût effectif = coût de base × (1 + pénalité finale)

⚠️ **DEUX CHARGES, et c'est tout le montage.** La charge PHYSIQUE (`characters.charge_max_of`,
F×5) reste BRUTE et inviolable : c'est elle que lisent la garde de surcharge, le butin et les
montures, et aucun buff ne doit l'ouvrir (CLAUDE.md §3 — sinon on boit une potion, on ramasse,
on laisse expirer). La charge MAGIQUE, elle, est modulable : coefficient `charge_magique` par
item et réduction `canalisation` des objets/buffs. Une ceinture de force n'augmente donc pas
ce qu'on peut emporter, elle rend ce qu'on emporte plus facile à canaliser.

⚠️ **Rien n'est jamais stocké** : tout se recalcule depuis l'état courant, sinon une pénalité
figée survivrait à un changement d'inventaire. Seule exception, documentée et voulue :
`combat._armer_incantation` fige le total d'une incantation longue au moment où le lanceur
s'y engage (elle absorbe tout son budget d'actions et ne s'abandonne pas).

Réglages : `CHARGE_MAGIE_*`, `SENSIBILITE_CHARGE_DEFAUT`, `CHARGE_MAGIQUE_COEF_MAX` et
`CANALISATION_REDUCTION_MAX` (variables de monde). `CHARGE_MAGIE_PEN_MAX = 0` désactive tout.
"""

import math

from models import character_stats
from utils import consommables
from utils.characters import charge_max_of, item_ref_id, item_ref_weight

# Palier de repli quand aucune borne de `CHARGE_MAGIE_PALIERS` n'est franchie — c'est-à-dire
# au-delà de la dernière, donc en surcharge.
PALIER_SURCHARGE = "surcharge"

# Libellés lisibles. Le client affiche ces mots, jamais un coefficient (on veut « plus je
# porte lourd, plus la magie est difficile », pas une formule à l'écran).
PALIER_LABELS: dict[str, str] = {
	"legere": "légère",
	"moderee": "modérée",
	"importante": "importante",
	"lourde": "lourde",
	PALIER_SURCHARGE: "surcharge",
}


def _f(valeur, defaut: float = 0.0) -> float:
	"""Float tolérant : une donnée illisible vaut le défaut plutôt que de lever."""
	try:
		return float(valeur)
	except (TypeError, ValueError):
		return defaut


# ── Charge magique portée ────────────────────────────────────────────────────────

def coefficient_item(item_doc) -> float:
	"""Coefficient `charge_magique` d'un item : le poids que la CANALISATION ressent, pour
	un kilo réellement porté. Défaut 1.0 (le poids physique), borné [0, COEF_MAX].

	Champ absent ⇒ poids magique = poids physique, à la lettre : aucune migration, et tant
	qu'aucun item ne porte le champ la mécanique se comporte comme si elle lisait le poids.
	"""
	if not isinstance(item_doc, dict) or "charge_magique" not in item_doc:
		return 1.0
	coef = _f(item_doc.get("charge_magique"), 1.0)
	return max(0.0, min(float(character_stats.CHARGE_MAGIQUE_COEF_MAX), coef))


def charge_magique_portee(character: dict, resolve_fn=None) -> float:
	"""Poids RESSENTI par la canalisation : Σ poids d'instance × coefficient de l'item.

	Mêmes références que `characters.carried_weight` (inventaire + équipement porté), donc
	exactement le même périmètre — le sol n'appartient à personne et la bourse ne pèse rien.

	`resolve_fn` (id → doc item) est injecté : sans lui, aucun coefficient n'est lu et la
	charge magique **est** la charge physique. C'est le comportement voulu partout où
	résoudre coûterait une lecture base qu'on ne peut pas se permettre.
	"""
	refs = list((character or {}).get("inventaire") or [])
	refs += [v for v in ((character or {}).get("slots") or {}).values() if v]
	total = 0.0
	for ref in refs:
		poids = item_ref_weight(ref)
		if resolve_fn is None or not poids:
			total += poids
			continue
		item_id = item_ref_id(ref)
		total += poids * coefficient_item(resolve_fn(item_id) if item_id else None)
	return total


# ── Du ratio à la pénalité ───────────────────────────────────────────────────────

def ratio_charge(charge, capacite) -> float:
	"""Charge relative : 1.0 = pile à la capacité, > 1 = surcharge.

	⚠️ Capacité absente, nulle ou illisible ⇒ **0.0**, jamais une division par zéro ni un
	infini : un personnage sans capacité valide (fixture, monture sans espèce, doc abîmé)
	garde sa magie intacte. Refuser de canaliser sur une donnée manquante serait le pire
	des deux comportements.
	"""
	cap = _f(capacite)
	if cap <= 0:
		return 0.0
	return max(0.0, _f(charge) / cap)


def penalite_charge(ratio: float) -> float:
	"""Pénalité brute de charge, avant sensibilité du sort et aide d'équipement.

	Trois régimes, sans rupture de valeur (seule la PENTE change à 100 %) :
	  · sous la franchise            → 0, on voyage léger sans y penser ;
	  · franchise → capacité         → QUADRATIQUE jusqu'à `PEN_MAX` : la gêne s'installe
	    doucement puis s'accélère, au lieu de tomber d'un palier à l'autre ;
	  · au-delà de la capacité       → linéaire et plus raide (`PENTE_SURCHARGE`).
	Le tout plafonné par `PEN_PLAFOND` : même écrasé de butin, un mage lance encore.
	"""
	pen_max = max(0.0, _f(character_stats.CHARGE_MAGIE_PEN_MAX))
	plafond = max(0.0, _f(character_stats.CHARGE_MAGIE_PEN_PLAFOND))
	if pen_max <= 0:
		return 0.0                      # interrupteur : mécanique désactivée
	franchise = min(0.99, max(0.0, _f(character_stats.CHARGE_MAGIE_FRANCHISE)))
	r = max(0.0, _f(ratio))
	if r <= franchise:
		return 0.0
	if r <= 1.0:
		part = (r - franchise) / (1.0 - franchise)
		return min(plafond, pen_max * part * part)
	pente = max(0.0, _f(character_stats.CHARGE_MAGIE_PENTE_SURCHARGE))
	return min(plafond, pen_max + (r - 1.0) * pente)


def palier(ratio: float) -> str:
	"""Palier lisible du ratio — la PREMIÈRE borne haute atteinte, table triée à la lecture.

	La table étant réglable à chaud, on ne présume ni de son ordre ni de son contenu : rien
	de franchi ⇒ `surcharge`, ce qui reste vrai quelle que soit la table.
	"""
	r = max(0.0, _f(ratio))
	for nom, borne in sorted(character_stats.CHARGE_MAGIE_PALIERS.items(), key=lambda kv: kv[1]):
		if r <= _f(borne):
			return nom
	return PALIER_SURCHARGE


def palier_label(nom: str) -> str:
	return PALIER_LABELS.get(nom, nom)


# ── Sensibilité et modificateur ──────────────────────────────────────────────────

def sensibilite_de(capacite) -> float:
	"""Sensibilité d'un sort/compétence à la charge, dans [0, 1].

	Champ `sensibilite_charge` du doc ; absent ⇒ `SENSIBILITE_CHARGE_DEFAUT`. Une petite
	étincelle s'annote à 0 (le poids ne la gêne pas), une téléportation ou une invocation
	près de 1. ⚠️ Un 0 EXPLICITE doit rester un 0 : on teste la présence de la clé, jamais
	sa véracité, sinon « insensible » retomberait sur le défaut.
	"""
	defaut = min(1.0, max(0.0, _f(character_stats.SENSIBILITE_CHARGE_DEFAUT, 0.5)))
	if not isinstance(capacite, dict) or capacite.get("sensibilite_charge") is None:
		return defaut
	return min(1.0, max(0.0, _f(capacite.get("sensibilite_charge"), defaut)))


def modificateur_de(canalisation) -> float:
	"""Facteur multiplicatif issu de l'aide à la canalisation (robe de mage, ceinture…).

	`canalisation` = pourcentage retranché à la pénalité, plafonné par
	`CANALISATION_REDUCTION_MAX` (< 100 par construction) : le facteur reste STRICTEMENT
	positif, donc la charge ne peut jamais être entièrement annulée.
	"""
	pct = max(0, int(_f(canalisation)))
	pct = min(int(character_stats.CANALISATION_REDUCTION_MAX), pct)
	return max(0.0, 1.0 - pct / 100.0)


def penalite_finale(ratio: float, capacite=None, canalisation: int = 0) -> float:
	"""Pénalité réellement appliquée à CE sort par CE porteur. Jamais négative."""
	return max(0.0, penalite_charge(ratio) * sensibilite_de(capacite)
			   * modificateur_de(canalisation))


# ── Application aux deux coûts ───────────────────────────────────────────────────

def cout_pm_effectif(cout_base, penalite: float) -> int:
	"""PM de lancement sous la charge. Jamais sous le coût de base.

	⚠️ **Arrondi au PLUS PROCHE, pas au supérieur.** Au supérieur, la moindre pénalité coûte
	un PM plein : à 40 % de charge, 2,4 % de gêne renchérissait un sort à 10 PM de 10 %, et
	la franchise devenait une falaise — exactement la rupture que la courbe quadratique
	s'emploie à éviter. Au plus proche, la gêne se paie quand elle pèse vraiment.
	`floor(x + 0.5)` et non `round()` : ce dernier arrondit les demis au PAIR (3,5 → 4 mais
	4,5 → 4), ce qui rendrait le tarif incompréhensible d'un sort à l'autre.

	⚠️ Un coût de base nul reste nul : beaucoup de compétences de vocation ne coûtent rien,
	et les renchérir ferait payer la charge à des gestes purement martiaux.
	"""
	base = max(0, int(_f(cout_base)))
	if base <= 0 or penalite <= 0:
		return base
	return max(base, math.floor(base * (1.0 + max(0.0, penalite)) + 0.5))


def maintien_effectif(maintien_base, penalite: float) -> int:
	"""PM d'entretien par round sous la charge — même arithmétique que le lancement.

	Plancher à 1 dès que la base l'est (miroir de `sorts.doc_effectif`) : un sort maintenu
	dont l'entretien tomberait à 0 cesserait d'être maintenu.
	"""
	base = max(0, int(_f(maintien_base)))
	if base <= 0:
		return 0
	return max(1, cout_pm_effectif(base, penalite))


# ── Payload ──────────────────────────────────────────────────────────────────────

def etat_porteur(character: dict, resolve_fn=None) -> tuple[float, int]:
	"""`(ratio de charge magique, aide à la canalisation)` d'un personnage HORS COMBAT.

	⚠️ La capacité est `charge_max_of` — **brute**, jamais buffée (CLAUDE.md §3). C'est le
	pivot de tout le montage : les buffs agissent sur le numérateur (coefficients d'items)
	et sur l'aide à la canalisation, jamais sur le dénominateur. Une ceinture de force
	n'ouvre donc pas la limite d'inventaire, elle allège le mana.

	En combat, on ne passe PAS par ici : le snapshot porte déjà `charge_magique`,
	`charge_max` et `canalisation`, et la résolution d'un coup ne lit pas la base.
	"""
	ratio = ratio_charge(charge_magique_portee(character, resolve_fn), charge_max_of(character))
	return ratio, consommables.canalisation_bonus(character)


def penalite_porteur(character: dict, capacite=None, resolve_fn=None) -> float:
	"""Pénalité appliquée à `capacite` pour ce personnage hors combat."""
	ratio, canalisation = etat_porteur(character, resolve_fn)
	return penalite_finale(ratio, capacite, canalisation)


def cout_pm_porteur(character: dict, capacite: dict, resolve_fn=None) -> int:
	"""PM de lancement d'une capacité hors combat, charge comprise. **Source unique** de la
	garde « PM insuffisants » et du débit : lus séparément, ils pourraient diverger."""
	return cout_pm_effectif((capacite or {}).get("cout_pm"),
							penalite_porteur(character, capacite, resolve_fn))


def bloc_charge(charge, capacite, canalisation: int = 0) -> dict:
	"""Le bloc que lit l'interface. Source unique : fiche, /play et combat affichent la même
	chose, et personne ne recalcule la courbe côté client."""
	ratio = ratio_charge(charge, capacite)
	nom = palier(ratio)
	return {
		"charge": round(_f(charge), 2),
		"charge_max": round(_f(capacite), 2),
		"ratio": round(ratio, 4),
		"palier": nom,
		"palier_label": palier_label(nom),
		"penalite": round(penalite_charge(ratio), 4),
		"canalisation": max(0, int(_f(canalisation))),
		"modificateur": round(modificateur_de(canalisation), 4),
		# Sensibilité appliquée à une capacité qui n'en déclare pas : le client en a besoin
		# pour réafficher un coût après un changement d'inventaire, sans relire la liste
		# des sorts. Publié plutôt que recopié en dur dans le template — c'est une
		# variable de monde, elle bouge à l'équilibrage.
		"sensibilite_defaut": min(1.0, max(0.0, _f(
			character_stats.SENSIBILITE_CHARGE_DEFAUT, 0.5))),
	}

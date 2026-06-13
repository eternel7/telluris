# models/character_stats.py
# Modèles Pydantic pour les stats de personnage Telluris / Légende

from pydantic import BaseModel, Field
import math


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
    pv:            int = 0    # Bonus PV (objets magiques)
    pm:            int = 0    # Bonus PM
    pa:            int = 0    # Valeur d'armure totale
    malus_depl:    int = 0    # Malus de déplacement (armure lourde)
    cc_bonus:      int = 0    # Bonus attaque CàC (arme)
    cd_bonus:      int = 0    # Bonus attaque distance (arme)
    degats_bonus:  int = 0    # Bonus dégâts (arme)
    initiative:    int = 0    # Bonus initiative (objets)


# ── Stats dérivées calculées ──────────────────────────────────────────────────

class DerivedStats(BaseModel):
    """Stats calculées — jamais stockées en base, toujours recalculées."""

    # Points de ressources
    pv_max:    int
    pm_max:    int

    # Combat
    initiative:  int
    deplacement: int   # cases par action
    cc:          int   # compétence corps à corps
    cd:          int   # compétence à distance
    pa:          int   # points d'armure
    pm_def:      int   # défense magique
    degats_cc:   str   # ex: "1D6+3"
    degats_cd:   str   # ex: "1D4+1"

    # Divers
    charge_max:  int   # kg
    xp_cout_niv: int   # coût XP pour monter au prochain niveau


def compute_derived_stats(
    base:      BaseStats,
    niveau:    int,
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
    pa = (base.r // 2) + equipment.pa

    # ── Défense magique ───────────────────────────────────────────────
    pm_def = (base.vol // 2) + (base.int_ // 4)

    # ── Dégâts corps à corps ─────────────────────────────────────────
    de_cc = _force_to_dice(base.f)
    bonus_degats = equipment.degats_bonus
    degats_cc = f"1D{de_cc}+{bonus_degats}" if bonus_degats else f"1D{de_cc}"

    # ── Dégâts à distance ─────────────────────────────────────────────
    de_cd = _agility_to_dice(base.ag)
    degats_cd = f"1D{de_cd}+{bonus_degats}" if bonus_degats else f"1D{de_cd}"

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


# ── Coefficients XP par stat ──────────────────────────────────────────────────

# V coûte 10× plus cher, toutes les autres stats coûtent 1 par point au-dessus du min racial
XP_COEFF: dict[str, int] = {"V": 10}

# Réduction du plafond pour les stats hors quota d'accessibilité
# V perd 1 point, toutes les autres perdent 10 points sous le max racial
_SUB_CAP_REDUCTION: dict[str, int] = {"V": 1}


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
    stat_key:           str,
    stats_max:          dict,
    nb_max_accessibles: int,
    current_stats:      dict,
    max_bonus:          dict | None = None,
    max_bonus_used:     str | None = None,
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
    """Niveau personnage basé sur l'XP totale. Seuils : >10→1, >20→2, >40→3, … (×2 à chaque palier)."""
    niveau, threshold = 0, 10
    while xp_total > threshold:
        niveau += 1
        threshold *= 2
    return niveau


def _force_to_dice(f: int) -> int:
    """Convertit la Force en valeur de dé standard."""
    if f <= 2:  return 4
    if f <= 4:  return 6
    if f <= 6:  return 8
    if f <= 8:  return 10
    if f <= 9:  return 12
    return 20


def _agility_to_dice(ag: int) -> int:
    """Convertit l'Agilité en valeur de dé pour les dégâts à distance."""
    if ag <= 3:  return 4
    if ag <= 5:  return 6
    if ag <= 7:  return 8
    if ag <= 9:  return 10
    return 12

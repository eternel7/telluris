# models/character_stats.py
# Modèles Pydantic pour les stats de personnage Telluris / Légende

from pydantic import BaseModel, Field, computed_field
from typing import Optional
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


# ── Bonus de vocation ─────────────────────────────────────────────────────────

class VocationBonus(BaseModel):
    """Bonus fixes apportés par la vocation au niveau actuel."""
    pv:          int = 0   # Bonus PV max
    pm:          int = 0   # Bonus PM max
    cc:          int = 0   # Bonus attaque corps à corps
    cd:          int = 0   # Bonus attaque à distance
    deplacement: int = 0   # Bonus cases de déplacement
    pa:          int = 0   # Bonus armure naturelle


# Bonus par vocation (niveau 1 — à scaler avec le niveau)
VOCATION_BONUS: dict[str, VocationBonus] = {
    "guerrier":      VocationBonus(pv=10, cc=2, pa=1, deplacement=0),
    "barbare":       VocationBonus(pv=12, cc=2, deplacement=1),
    "forestier":     VocationBonus(pv=6,  cd=3, deplacement=1),
    "duelliste":     VocationBonus(pv=6,  cc=3, deplacement=0),
    "moine":         VocationBonus(pv=8,  cc=1, deplacement=1, pa=1),
    "elementaliste": VocationBonus(pm=15, pv=2),
    "magbataille":   VocationBonus(pm=10, pv=4, cc=1),
    "illusionniste": VocationBonus(pm=12, pv=2),
    "lettré":        VocationBonus(pm=8,  pv=3),
    "druide":        VocationBonus(pm=10, pv=4),
    "chaman":        VocationBonus(pm=8,  pv=6, deplacement=1),
    "pretre":        VocationBonus(pm=12, pv=4),
    "paladin":       VocationBonus(pv=8,  pm=6, cc=1, pa=1),
    "templier":      VocationBonus(pv=8,  pm=4, cc=1, pa=1),
    "repurgateur":   VocationBonus(pv=6,  cc=2, pm=4),
    "necromancien":  VocationBonus(pm=14, pv=2),
    "assassin":      VocationBonus(pv=6,  cc=2, cd=1, deplacement=1),
    "voleur":        VocationBonus(pv=4,  cd=2, deplacement=1),
    "menestrel":     VocationBonus(pv=4,  pm=6),
    "demoniste":     VocationBonus(pm=14, pv=2),
}


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
    cc:          int   # compétence corps à corps (jet sous cette valeur)
    cd:          int   # compétence à distance
    pa:          int   # points d'armure (réduction dégâts physiques)
    pm_def:      int   # défense magique
    degats_cc:   str   # ex: "1D6+3"
    degats_cd:   str   # ex: "1D4+1"

    # Divers
    charge_max:  int   # kg
    xp_cout_niv: int   # coût XP pour monter au prochain niveau


def compute_derived_stats(
    base:      BaseStats,
    niveau:    int,
    vocation:  str,
    equipment: EquipmentBonus = EquipmentBonus(),
    pv_bonus_items: int = 0,
) -> DerivedStats:
    """
    Calcule toutes les stats dérivées à partir des stats de base,
    du niveau, de la vocation et de l'équipement.
    """
    voc = VOCATION_BONUS.get(vocation, VocationBonus())

    # ── Scaling du bonus de vocation avec le niveau ──
    # Chaque niveau apporte 50% du bonus de base en plus (arrondi inf.)
    level_scale = 1 + (niveau - 1) * 0.5

    pv_voc  = math.floor(voc.pv  * level_scale)
    pm_voc  = math.floor(voc.pm  * level_scale)
    cc_voc  = math.floor(voc.cc  * level_scale)
    cd_voc  = math.floor(voc.cd  * level_scale)
    pa_voc  = voc.pa   # L'armure naturelle ne scale pas avec le niveau
    depl_voc = voc.deplacement

    # ── PV max ──────────────────────────────────────────────────────
    # Base : R × 3 + F × 1 + bonus vocation + bonus équipement
    pv_max = (base.r * 3) + (base.f * 1) + pv_voc + equipment.pv

    # ── PM max ──────────────────────────────────────────────────────
    # Base : Vol × 2 + Int × 2 + bonus vocation + bonus équipement
    pm_max = (base.vol * 2) + (base.int_ * 2) + pm_voc + equipment.pm

    # ── Initiative ──────────────────────────────────────────────────
    # Ag + V + bonus équipement
    initiative = base.ag + base.v + equipment.initiative

    # ── Déplacement ─────────────────────────────────────────────────
    # V + bonus vocation - malus armure (min 1)
    deplacement = max(1, base.v + depl_voc - equipment.malus_depl)

    # ── Compétence corps à corps ─────────────────────────────────────
    # F + Ag/2 + bonus vocation + bonus arme
    cc = base.f + (base.ag // 2) + cc_voc + equipment.cc_bonus

    # ── Compétence à distance ────────────────────────────────────────
    # Ag + V/2 + bonus vocation + bonus arme
    cd = base.ag + (base.v // 2) + cd_voc + equipment.cd_bonus

    # ── Armure ───────────────────────────────────────────────────────
    # R/2 + armure naturelle vocation + équipement
    pa = (base.r // 2) + pa_voc + equipment.pa

    # ── Défense magique ───────────────────────────────────────────────
    # Vol/2 + Int/4
    pm_def = (base.vol // 2) + (base.int_ // 4)

    # ── Dégâts corps à corps ─────────────────────────────────────────
    # Formule : 1D(F) + bonus équipement
    # Dé : F mappe sur le dé standard supérieur (4,6,8,10,12,20)
    de_cc   = _force_to_dice(base.f)
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

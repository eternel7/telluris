# tests/test_character_stats.py

import pytest
from models.character_stats import (
    BaseStats, EquipmentBonus, DerivedStats,
    compute_derived_stats, compute_xp_cost, compute_stat_cap,
    compute_character_level,
)


def make_base(**kwargs) -> BaseStats:
    defaults = dict(v=3, f=4, r=4, ag=3, vol=3, int_=2, cha=2, ch=2)
    defaults.update(kwargs)
    return BaseStats(**defaults)


# ── PV max ────────────────────────────────────────────────────────────────────

def test_pv_max_formule():
    base = make_base(r=4, f=4)
    stats = compute_derived_stats(base, niveau=1)
    # R×3 + F = 12 + 4 = 16
    assert stats.pv_max == 16

def test_pv_max_avec_equipment():
    base = make_base(r=4, f=4)
    eq = EquipmentBonus(pv=5)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    assert stats.pv_max == 21

def test_pv_stable_avec_niveau():
    base = make_base(r=4, f=4)
    s1 = compute_derived_stats(base, niveau=1)
    s3 = compute_derived_stats(base, niveau=3)
    # Le niveau n'affecte pas PV
    assert s1.pv_max == s3.pv_max


# ── PM max ────────────────────────────────────────────────────────────────────

def test_pm_max_mage():
    base = make_base(vol=6, int_=7)
    stats = compute_derived_stats(base, niveau=1)
    # Vol×2 + Int×2 = 12 + 14 = 26
    assert stats.pm_max == 26

def test_pm_max_guerrier_faible():
    base = make_base(vol=2, int_=2)
    stats = compute_derived_stats(base, niveau=1)
    # Vol×2 + Int×2 = 4 + 4 = 8
    assert stats.pm_max == 8


# ── Combat ────────────────────────────────────────────────────────────────────

def test_initiative():
    base = make_base(ag=5, v=3)
    stats = compute_derived_stats(base, niveau=1)
    assert stats.initiative == 8  # Ag + V

def test_deplacement_min_1():
    base = make_base(v=1)
    eq = EquipmentBonus(malus_depl=5)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    assert stats.deplacement >= 1

def test_cc():
    base = make_base(f=5, ag=4)
    stats = compute_derived_stats(base, niveau=1)
    # F + Ag//2 = 5 + 2 = 7
    assert stats.cc == 7

def test_pa_avec_armure():
    base = make_base(r=4)
    eq = EquipmentBonus(pa=4)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    # R//2 + eq_pa = 2 + 4 = 6
    assert stats.pa == 6


# ── Dégâts ────────────────────────────────────────────────────────────────────

def test_degats_cc_format():
    base = make_base(f=5)
    stats = compute_derived_stats(base, niveau=1)
    assert "D" in stats.degats_cc
    assert stats.degats_cc.startswith("1D")

def test_degats_cc_avec_bonus():
    base = make_base(f=5)
    eq = EquipmentBonus(degats_bonus=3)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    assert "+3" in stats.degats_cc


# ── Charge ────────────────────────────────────────────────────────────────────

def test_charge_max():
    base = make_base(f=6)
    stats = compute_derived_stats(base, niveau=1)
    assert stats.charge_max == 30  # F × 5


# ── Niveau personnage ─────────────────────────────────────────────────────────

def test_compute_character_level_zero():
    assert compute_character_level(0)  == 0
    assert compute_character_level(10) == 0

def test_compute_character_level_un():
    assert compute_character_level(11) == 1
    assert compute_character_level(30) == 1

def test_compute_character_level_deux():
    assert compute_character_level(31) == 2
    assert compute_character_level(90) == 2

def test_compute_character_level_trois():
    assert compute_character_level(91) == 3


# ── XP ────────────────────────────────────────────────────────────────────────

def test_xp_cout_niveau():
    base = make_base()
    s1 = compute_derived_stats(base, niveau=1)
    s5 = compute_derived_stats(base, niveau=5)
    assert s1.xp_cout_niv == 10   # (1+1) × 5
    assert s5.xp_cout_niv == 30   # (5+1) × 5


# ── compute_xp_cost ───────────────────────────────────────────────────────────

def test_xp_cost_stat_normale():
    # F: coeff=1, race_min=2, from=2 to=3 → (3-2)*1 = 1
    assert compute_xp_cost("F", 2, 3, race_min=2) == 1

def test_xp_cost_stat_normale_cumul():
    # F: race_min=2, from=2 to=5
    # N=2: (3-2)*1=1, N=3: (4-2)*1=2, N=4: (5-2)*1=3 → total=6
    assert compute_xp_cost("F", 2, 5, race_min=2) == 6

def test_xp_cost_vitesse():
    # V: coeff=10, race_min=1, from=1 to=2 → (2-1)*10 = 10
    assert compute_xp_cost("V", 1, 2, race_min=1) == 10

def test_xp_cost_vitesse_cumul():
    # V: coeff=10, race_min=1, from=1 to=3
    # N=1: (2-1)*10=10, N=2: (3-1)*10=20 → total=30
    assert compute_xp_cost("V", 1, 3, race_min=1) == 30

def test_xp_cost_no_change():
    assert compute_xp_cost("F", 5, 5, race_min=2) == 0

def test_xp_cost_inverse_nul():
    assert compute_xp_cost("F", 5, 3, race_min=2) == 0


# ── compute_stat_cap ──────────────────────────────────────────────────────────

STATS_MAX = {"V": 5, "F": 10, "R": 10, "Ag": 8, "Vol": 8, "Int": 8, "Cha": 8, "Ch": 8}
NB_MAX = 3

def test_cap_quota_libre():
    # 0 stats au max → peut monter jusqu'à stats_max
    current = {"V": 1, "F": 2, "R": 2, "Ag": 2, "Vol": 2, "Int": 2, "Cha": 2, "Ch": 2}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current)
    assert cap == 10

def test_cap_quota_plein_stat_normale():
    # 3 stats déjà au max → F est hors quota → sous-plafond 10-10=0
    current = {"V": 1, "F": 5, "R": 10, "Ag": 8, "Vol": 8, "Int": 2, "Cha": 2, "Ch": 2}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current)
    assert cap == 0  # 10 - 10 = 0

def test_cap_quota_plein_v():
    # 3 stats au max → V est hors quota → sous-plafond 5-1=4
    current = {"V": 1, "F": 5, "R": 10, "Ag": 8, "Vol": 8, "Int": 2, "Cha": 2, "Ch": 2}
    cap = compute_stat_cap("V", STATS_MAX, NB_MAX, current)
    assert cap == 4  # 5 - 1 = 4

def test_cap_stat_deja_au_max():
    # R est déjà à son max → son plafond reste stats_max
    current = {"V": 1, "F": 10, "R": 10, "Ag": 8, "Vol": 2, "Int": 2, "Cha": 2, "Ch": 2}
    cap = compute_stat_cap("R", STATS_MAX, NB_MAX, current)
    assert cap == 10

def test_cap_max_bonus_humain():
    # Humain avec max_bonus, utilisé sur F
    max_bonus = {"V": 1, "F": 10, "R": 10, "Ag": 10, "Vol": 10, "Int": 10, "Cha": 10, "Ch": 10}
    current = {"V": 1, "F": 10, "R": 10, "Ag": 8, "Vol": 2, "Int": 2, "Cha": 2, "Ch": 2}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current, max_bonus=max_bonus, max_bonus_used="F")
    assert cap == 20  # 10 + 10

def test_cap_max_bonus_non_utilise():
    # Humain avec max_bonus mais utilisé sur une autre stat
    max_bonus = {"V": 1, "F": 10, "R": 10, "Ag": 10, "Vol": 10, "Int": 10, "Cha": 10, "Ch": 10}
    current = {"V": 1, "F": 5, "R": 10, "Ag": 8, "Vol": 8, "Int": 2, "Cha": 2, "Ch": 2}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current, max_bonus=max_bonus, max_bonus_used="Vol")
    # Quota plein (R, Ag, Vol au max) → sous-plafond pour F : 10-10=0
    assert cap == 0

# tests/test_character_stats.py

import pytest
from models.character_stats import (
    BaseStats, EquipmentBonus, compute_derived_stats, VOCATION_BONUS
)


def make_base(**kwargs) -> BaseStats:
    defaults = dict(v=3, f=4, r=4, ag=3, vol=3, int_=2, cha=2, ch=2)
    defaults.update(kwargs)
    return BaseStats(**defaults)


# ── PV max ────────────────────────────────────────────────────────────────────

def test_pv_max_formule():
    base = make_base(r=4, f=4)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier")
    # R×3 + F×1 + voc(10) = 12+4+10 = 26
    assert stats.pv_max == 26

def test_pv_max_avec_equipment():
    base = make_base(r=4, f=4)
    eq = EquipmentBonus(pv=5)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier", equipment=eq)
    assert stats.pv_max == 31

def test_pv_scale_avec_niveau():
    base = make_base(r=4, f=4)
    s1 = compute_derived_stats(base, niveau=1, vocation="guerrier")
    s3 = compute_derived_stats(base, niveau=3, vocation="guerrier")
    assert s3.pv_max > s1.pv_max


# ── PM max ────────────────────────────────────────────────────────────────────

def test_pm_max_mage():
    base = make_base(vol=6, int_=7)
    stats = compute_derived_stats(base, niveau=1, vocation="elementaliste")
    # Vol×2 + Int×2 + voc_pm(15) = 12+14+15 = 41
    assert stats.pm_max == 41

def test_pm_max_guerrier_faible():
    base = make_base(vol=2, int_=2)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier")
    # Vol×2 + Int×2 + voc_pm(0) = 4+4+0 = 8
    assert stats.pm_max == 8


# ── Combat ────────────────────────────────────────────────────────────────────

def test_initiative():
    base = make_base(ag=5, v=3)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier")
    assert stats.initiative == 8  # Ag + V

def test_deplacement_min_1():
    base = make_base(v=1)
    eq = EquipmentBonus(malus_depl=5)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier", equipment=eq)
    assert stats.deplacement >= 1

def test_cc_guerrier():
    base = make_base(f=5, ag=4)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier")
    # F + Ag//2 + voc_cc(2) = 5+2+2 = 9
    assert stats.cc == 9

def test_pa_avec_armure():
    base = make_base(r=4)
    eq = EquipmentBonus(pa=4)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier", equipment=eq)
    # R//2 + voc_pa(1) + eq_pa(4) = 2+1+4 = 7
    assert stats.pa == 7


# ── Dégâts ────────────────────────────────────────────────────────────────────

def test_degats_cc_format():
    base = make_base(f=5)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier")
    assert "D" in stats.degats_cc
    assert stats.degats_cc.startswith("1D")

def test_degats_cc_avec_bonus():
    base = make_base(f=5)
    eq = EquipmentBonus(degats_bonus=3)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier", equipment=eq)
    assert "+3" in stats.degats_cc


# ── Charge ────────────────────────────────────────────────────────────────────

def test_charge_max():
    base = make_base(f=6)
    stats = compute_derived_stats(base, niveau=1, vocation="guerrier")
    assert stats.charge_max == 30  # F × 5


# ── XP ────────────────────────────────────────────────────────────────────────

def test_xp_cout_niveau():
    base = make_base()
    s1 = compute_derived_stats(base, niveau=1, vocation="guerrier")
    s5 = compute_derived_stats(base, niveau=5, vocation="guerrier")
    assert s1.xp_cout_niv == 10   # (1+1) × 5
    assert s5.xp_cout_niv == 30   # (5+1) × 5


# ── Vocation inconnue ─────────────────────────────────────────────────────────

def test_vocation_inconnue_fallback():
    """Une vocation inconnue doit retourner des bonus nuls sans planter."""
    base = make_base()
    stats = compute_derived_stats(base, niveau=1, vocation="__inconnu__")
    assert stats.pv_max > 0  # Toujours calculable


# ── Couverture toutes vocations ───────────────────────────────────────────────

@pytest.mark.parametrize("vocation", list(VOCATION_BONUS.keys()))
def test_toutes_vocations(vocation):
    base = make_base()
    stats = compute_derived_stats(base, niveau=1, vocation=vocation)
    assert stats.pv_max > 0
    assert stats.pm_max >= 0
    assert stats.deplacement >= 1

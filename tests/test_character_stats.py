# tests/test_character_stats.py

import pytest
import models.character_stats as cs
from models.character_stats import (
    BaseStats, EquipmentBonus, DerivedStats,
    compute_derived_stats, compute_xp_cost, compute_stat_cap,
    compute_character_level,
)


# Échelle réelle (dump CouchDB rules:races) : V reste sur l'échelle 1-10,
# les 7 autres caractéristiques sont passées ×10 (≈ 10-100).
def make_base(**kwargs) -> BaseStats:
    defaults = dict(v=5, f=20, r=20, ag=20, vol=30, int_=30, cha=30, ch=20)
    defaults.update(kwargs)
    return BaseStats(**defaults)


# ── PV max ────────────────────────────────────────────────────────────────────

def test_pv_max_formule():
    base = make_base(r=20, f=20)
    stats = compute_derived_stats(base, niveau=1)
    # R×3 + F = 60 + 20 = 80
    assert stats.pv_max == 80

def test_pv_max_avec_equipment():
    base = make_base(r=20, f=20)
    eq = EquipmentBonus(pv=10)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    # 80 + eq.pv 10 = 90
    assert stats.pv_max == 90

def test_pv_stable_avec_niveau():
    base = make_base(r=20, f=20)
    s1 = compute_derived_stats(base, niveau=1)
    s3 = compute_derived_stats(base, niveau=3)
    # Le niveau n'affecte pas PV
    assert s1.pv_max == s3.pv_max


# ── PM max ────────────────────────────────────────────────────────────────────

def test_pm_max_mage():
    base = make_base(vol=50, int_=50)
    stats = compute_derived_stats(base, niveau=1)
    # Vol×2 + Int×2 = 100 + 100 = 200
    assert stats.pm_max == 200

def test_pm_max_guerrier_faible():
    base = make_base(vol=10, int_=10)
    stats = compute_derived_stats(base, niveau=1)
    # Vol×2 + Int×2 = 20 + 20 = 40
    assert stats.pm_max == 40


# ── Combat ────────────────────────────────────────────────────────────────────

def test_initiative():
    base = make_base(ag=30, v=5)
    stats = compute_derived_stats(base, niveau=1)
    # V normalisé ×10 et pondéré 2× l'Ag : (Ag + V*20)//3 = (30 + 100)//3 = 43
    assert stats.initiative == 43

def test_deplacement_min_1():
    # V reste petit (échelle 1-10) et le malus d'armure est déjà replié dedans (delta sur V,
    # cf. recompute_equipment_bonus) : le déplacement ne descend jamais sous 1.
    base = make_base(v=0)
    stats = compute_derived_stats(base, niveau=1)
    assert stats.deplacement == 1


def test_malus_depl_pas_soustrait_deux_fois():
    # `equipment.malus_depl` est informatif : il a déjà été replié dans V via les buffs, le
    # soustraire ici le compterait deux fois (l'armure lourde ralentirait double).
    base = make_base(v=4)
    eq = EquipmentBonus(malus_depl=-1)
    assert compute_derived_stats(base, niveau=1, equipment=eq).deplacement == 4

def test_cc():
    # Pondération 1:3 F/Ag (rééquilibrage 2026-07-02 : F = dégâts, Ag = précision) :
    # (F + Ag×3)//4 = (40 + 60)//4 = 25. f≠ag pour discriminer de l'ancienne moyenne 1:1.
    base = make_base(f=40, ag=20)
    stats = compute_derived_stats(base, niveau=1)
    assert stats.cc == 25

def test_cd():
    base = make_base(ag=20, v=5)
    stats = compute_derived_stats(base, niveau=1)
    # V normalisé ×10, pondération 3:1 Ag/V : (Ag×3 + V×10)//4 = (60 + 50)//4 = 27
    assert stats.cd == 27

def test_pa_sans_armure():
    base = make_base(r=20)
    stats = compute_derived_stats(base, niveau=1)
    # R//20 = 20//20 = 1 (armure naturelle, échelle ×10)
    assert stats.pa == 1

def test_pa_avec_armure():
    base = make_base(r=40)
    eq = EquipmentBonus(pa=4)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    # R//20 + eq_pa = 2 + 4 = 6
    assert stats.pa == 6


# ── Dégâts ────────────────────────────────────────────────────────────────────

def test_degats_cc_format():
    base = make_base(f=20)
    stats = compute_derived_stats(base, niveau=1)
    assert "D" in stats.degats_cc
    assert stats.degats_cc.startswith("1D")

def test_degats_cc_die_value():
    # _caract_to_dice_ : ≤20→D4, ≤40→D6, ≤60→D8, ≤80→D10, ≤90→D12, sinon→D20
    # + bonus de puissance F//20 (miroir des PA = R//20).
    assert compute_derived_stats(make_base(f=20), niveau=1).degats_cc == "1D4+1"
    assert compute_derived_stats(make_base(f=50), niveau=1).degats_cc == "1D8+2"
    assert compute_derived_stats(make_base(f=100), niveau=1).degats_cc == "1D20+5"

def test_degats_cc_avec_bonus():
    base = make_base(f=50)
    eq = EquipmentBonus(degats_bonus=3)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    # F=50 → D8, + puissance F//20 (=2) + bonus arme 3 = +5
    assert stats.degats_cc == "1D8+5"
    assert "+5" in stats.degats_cc

def test_degats_cc_dice_arme():
    # Une arme peut ajouter des dés (+1DX) en plus du modificateur plat.
    base = make_base(f=24)  # D6, puissance F//20 = 1
    eq = EquipmentBonus(degats_dice="1D4", degats_bonus=1)
    stats = compute_derived_stats(base, niveau=1, equipment=eq)
    assert stats.degats_cc == "1D6+1D4+2"


# ── Facteur dégâts / armure ───────────────────────────────────────────────────
# FACTEUR_DEGATS_ARMURE pilote À LA FOIS l'armure (PA = R//FACTEUR) et le bonus de
# puissance des dégâts (F//FACTEUR au CàC, Ag//FACTEUR au tir). Le baisser amplifie
# les deux symétriquement.

def test_facteur_defaut_20():
    assert cs.FACTEUR_DEGATS_ARMURE == 20

def test_facteur_pilote_pa_et_degats(monkeypatch):
    base = make_base(f=40, r=40, ag=40)
    # Défaut 20 : PA = 40//20 = 2 ; F//20 = 2 → D6+2 ; Ag//20 = 2 → D6+2 (CT)
    d = compute_derived_stats(base, niveau=1)
    assert (d.pa, d.degats_cc, d.degats_cd) == (2, "1D6+2", "1D6+2")
    # Facteur 10 : tout double (PA = 4, bonus = 4)
    monkeypatch.setattr(cs, "FACTEUR_DEGATS_ARMURE", 10)
    d = compute_derived_stats(base, niveau=1)
    assert (d.pa, d.degats_cc, d.degats_cd) == (4, "1D6+4", "1D6+4")


# ── Charge ────────────────────────────────────────────────────────────────────

def test_charge_max():
    base = make_base(f=20)
    stats = compute_derived_stats(base, niveau=1)
    assert stats.charge_max == 100  # F × 5 = 20 × 5


# ── Niveau personnage ─────────────────────────────────────────────────────────
# Suite arithmétique : passage au niveau n = XP_NIVEAU_BASE + (n−1)·XP_NIVEAU_INCREMENT.
# Ces tests épinglent BASE=10/INCREMENT=5 (seuils cumulés 10, 25, 45, 70, 100…) pour
# valider la FORMULE indépendamment des défauts de production (world-vars réglables →
# ne pas coder en dur les valeurs par défaut, sinon le test dérive à chaque ajustement).
# Seuils d'XP-totale (pas une caractéristique) → non concernés par le ×10.

def _pin_xp(monkeypatch, base=10, inc=5):
    monkeypatch.setattr(cs, "XP_NIVEAU_BASE", base)
    monkeypatch.setattr(cs, "XP_NIVEAU_INCREMENT", inc)

def test_compute_character_level_zero(monkeypatch):
    _pin_xp(monkeypatch)
    assert compute_character_level(0)  == 0
    assert compute_character_level(10) == 0

def test_compute_character_level_un(monkeypatch):
    _pin_xp(monkeypatch)
    assert compute_character_level(11) == 1
    assert compute_character_level(25) == 1

def test_compute_character_level_deux(monkeypatch):
    _pin_xp(monkeypatch)
    assert compute_character_level(26) == 2
    assert compute_character_level(45) == 2

def test_compute_character_level_trois(monkeypatch):
    _pin_xp(monkeypatch)
    assert compute_character_level(46) == 3
    assert compute_character_level(70) == 3

def test_compute_character_level_world_vars(monkeypatch):
    # Les deux world-vars pilotent les seuils : base 20 / incrément 10 → 20, 50, 90…
    monkeypatch.setattr(cs, "XP_NIVEAU_BASE", 20)
    monkeypatch.setattr(cs, "XP_NIVEAU_INCREMENT", 10)
    assert compute_character_level(20) == 0
    assert compute_character_level(21) == 1
    assert compute_character_level(50) == 1
    assert compute_character_level(51) == 2

def test_xp_seuil_niveau_coherent_avec_compute_character_level():
    # Le seuil fermé (affichage fiche) doit tomber exactement sur les bascules de niveau.
    for n in range(1, 12):
        seuil = cs.xp_seuil_niveau(n)
        assert compute_character_level(seuil) == n - 1
        assert compute_character_level(seuil + 1) == n
    assert cs.xp_seuil_niveau(0) == 0

def test_compute_character_level_increment_zero_cout_constant(monkeypatch):
    # INCREMENT = 0 → chaque niveau coûte BASE (progression linéaire, autorisée).
    _pin_xp(monkeypatch, base=10, inc=0)
    assert compute_character_level(10) == 0
    assert compute_character_level(11) == 1
    assert compute_character_level(20) == 1
    assert compute_character_level(21) == 2


# ── XP ────────────────────────────────────────────────────────────────────────
# xp_cout_niv = coût du prochain niveau, aligné sur compute_character_level :
# BASE + niveau × INCREMENT (constantes épinglées → teste la formule, pas les défauts).

def test_xp_cout_niveau(monkeypatch):
    _pin_xp(monkeypatch)   # BASE=10, INCREMENT=5
    base = make_base()
    s1 = compute_derived_stats(base, niveau=1)
    s5 = compute_derived_stats(base, niveau=5)
    assert s1.xp_cout_niv == 15   # 10 + 1 × 5
    assert s5.xp_cout_niv == 35   # 10 + 5 × 5


# ── compute_xp_cost ───────────────────────────────────────────────────────────
# race_min réalistes : F (×10) ≈ 20, V (échelle 1-10) ≈ 5.

def test_xp_cost_stat_normale():
    # F: coeff=1, race_min=20, from=20 to=21 → (21-20)*1 = 1
    assert compute_xp_cost("F", 20, 21, race_min=20) == 1

def test_xp_cost_stat_normale_cumul():
    # F: race_min=20, from=20 to=23
    # N=20: (21-20)*1=1, N=21: (22-20)*1=2, N=22: (23-20)*1=3 → total=6
    assert compute_xp_cost("F", 20, 23, race_min=20) == 6

def test_xp_cost_vitesse():
    # V: coeff=10, race_min=5, from=5 to=6 → (6-5)*10 = 10
    assert compute_xp_cost("V", 5, 6, race_min=5) == 10

def test_xp_cost_vitesse_cumul():
    # V: coeff=10, race_min=5, from=5 to=7
    # N=5: (6-5)*10=10, N=6: (7-5)*10=20 → total=30
    assert compute_xp_cost("V", 5, 7, race_min=5) == 30

def test_xp_cost_no_change():
    assert compute_xp_cost("F", 25, 25, race_min=20) == 0

def test_xp_cost_inverse_nul():
    assert compute_xp_cost("F", 25, 23, race_min=20) == 0


# ── compute_stat_cap ──────────────────────────────────────────────────────────
# Plafonds réels de l'Humain (dump rules:races) : V sur 1-10, les 7 autres ×10.

STATS_MAX = {"V": 8, "F": 50, "R": 50, "Ag": 60, "Vol": 70, "Int": 70, "Cha": 80, "Ch": 60}
NB_MAX = 3

def test_cap_quota_libre():
    # 0 stats au max → peut monter jusqu'à stats_max
    current = {"V": 5, "F": 20, "R": 20, "Ag": 20, "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current)
    assert cap == 50

def test_cap_quota_plein_stat_normale():
    # 3 stats déjà au max (R, Ag, Vol) → F hors quota → sous-plafond 50-10=40
    current = {"V": 5, "F": 20, "R": 50, "Ag": 60, "Vol": 70, "Int": 30, "Cha": 30, "Ch": 20}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current)
    assert cap == 40  # 50 - 10

def test_cap_quota_plein_v():
    # 3 stats au max → V hors quota → sous-plafond 8-1=7 (réduction V = 1)
    current = {"V": 5, "F": 20, "R": 50, "Ag": 60, "Vol": 70, "Int": 30, "Cha": 30, "Ch": 20}
    cap = compute_stat_cap("V", STATS_MAX, NB_MAX, current)
    assert cap == 7  # 8 - 1

def test_cap_stat_deja_au_max():
    # R est déjà à son max → son plafond reste stats_max
    current = {"V": 5, "F": 50, "R": 50, "Ag": 20, "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20}
    cap = compute_stat_cap("R", STATS_MAX, NB_MAX, current)
    assert cap == 50

def test_cap_max_bonus_humain():
    # Humain avec max_bonus, utilisé sur F
    max_bonus = {"V": 1, "F": 10, "R": 10, "Ag": 10, "Vol": 10, "Int": 10, "Cha": 10, "Ch": 10}
    current = {"V": 5, "F": 20, "R": 50, "Ag": 60, "Vol": 70, "Int": 30, "Cha": 30, "Ch": 20}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current, max_bonus=max_bonus, max_bonus_used="F")
    assert cap == 60  # 50 + 10

def test_cap_max_bonus_non_utilise():
    # Humain avec max_bonus mais utilisé sur une autre stat
    max_bonus = {"V": 1, "F": 10, "R": 10, "Ag": 10, "Vol": 10, "Int": 10, "Cha": 10, "Ch": 10}
    current = {"V": 5, "F": 20, "R": 50, "Ag": 60, "Vol": 70, "Int": 30, "Cha": 30, "Ch": 20}
    cap = compute_stat_cap("F", STATS_MAX, NB_MAX, current, max_bonus=max_bonus, max_bonus_used="Vol")
    # Quota plein (R, Ag, Vol au max) → sous-plafond pour F : 50-10=40
    assert cap == 40

# tests/test_profil_restriction_tags.py
# `restriction_tags ⊆ tags de l'espèce` — la règle qui empêche un loup de porter un profil
# d'archer. Elle vivait en DEUX copies (le grade d'une élite de chasse, la cible d'une
# commission de donjon) et manquait là où elle se voyait le plus : l'ACCOMPAGNEMENT tiré par
# `instantiate_monsters`, traversé par les deux chemins de combat (zones et donjon).
#
# ⚠️ Ce qui est épinglé ici, ce n'est pas seulement « le filtre existe » : c'est qu'il est
# appliqué APRÈS le tirage de l'espèce, monstre par monstre. Un filtre appliqué une fois
# pour toute la fournée imposerait à chaque espèce la contrainte de la plus pauvre en tags —
# le gobelin chamanique perdrait son profil `magique` parce qu'un rat partage sa salle.

import pytest

from utils.combat import instantiate_monsters
from utils.zones import profil_compatible, profils_compatibles


NOVICE = {"_id": "profil:novice", "nom": "Novice", "niveau": 1}
COMBATTANT = {"_id": "profil:combattant", "nom": "Combattant", "niveau": 2}
ARCHER = {"_id": "profil:archer", "nom": "Archer", "niveau": 2, "restriction_tags": ["distance"]}
APPRENTI = {"_id": "profil:apprenti", "nom": "Apprenti", "niveau": 2, "restriction_tags": ["magique"]}
TOUS = [NOVICE, COMBATTANT, ARCHER, APPRENTI]

LOUP = {"_id": "espece:loup_geant", "nom": "Loup Géant", "tags": ["monstre", "predateur"],
        "base_attributes": {c: {"min": 20, "max": 30} for c in
                            ("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch")}}
CHAMAN = {"_id": "espece:gobelin_chamanique", "nom": "Gobelin Chamanique",
          "tags": ["humanoide", "magique"],
          "base_attributes": {c: {"min": 20, "max": 30} for c in
                              ("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch")}}


# ── Le prédicat, source unique ──────────────────────────────────────────────────

def test_un_profil_sans_restriction_convient_a_tout_le_monde():
    """L'ensemble vide est inclus dans n'importe quel ensemble : c'est ce qui garde
    novice/combattant/vétéran universels et rend le filtre indolore sur l'existant."""
    assert profil_compatible(NOVICE, LOUP) is True
    assert profil_compatible(COMBATTANT, LOUP) is True
    assert profil_compatible(NOVICE, {}) is True


def test_un_profil_restreint_exige_le_tag_sur_l_espece():
    assert profil_compatible(ARCHER, LOUP) is False
    assert profil_compatible(APPRENTI, LOUP) is False
    assert profil_compatible(APPRENTI, CHAMAN) is True
    assert profil_compatible(ARCHER, CHAMAN) is False


def test_profils_compatibles_garde_l_ordre_et_peut_rendre_vide():
    assert profils_compatibles(TOUS, LOUP) == [NOVICE, COMBATTANT]
    # ⚠️ Vide et non « toute la liste » : replier sur le non-filtré rouvrirait le défaut.
    assert profils_compatibles([ARCHER, APPRENTI], LOUP) == []
    assert profils_compatibles([], LOUP) == []


# ── Le chokepoint : instantiate_monsters ────────────────────────────────────────

def test_un_loup_ne_porte_jamais_un_profil_de_tir_ni_de_magie():
    monstres = instantiate_monsters([LOUP], TOUS, 40, [])
    assert len(monstres) == 40
    tires = {m["profil_id"] for m in monstres}
    assert tires <= {"profil:novice", "profil:combattant"}


def test_le_filtre_est_PAR_ESPECE_et_non_pour_toute_la_fournee():
    """La salle mêle un loup et un chamane. Le chamane doit GARDER son profil `magique` —
    un filtre appliqué une fois en amont le lui retirerait à cause du loup."""
    monstres = instantiate_monsters([LOUP, CHAMAN], TOUS, 200, [])
    par_espece = {}
    for m in monstres:
        par_espece.setdefault(m["espece_id"], set()).add(m["profil_id"])
    assert par_espece["espece:loup_geant"] <= {"profil:novice", "profil:combattant"}
    assert "profil:apprenti" in par_espece["espece:gobelin_chamanique"]
    assert "profil:archer" not in par_espece["espece:gobelin_chamanique"]


def test_aucun_profil_compatible_retombe_sur_le_point_median_de_l_espece():
    """Même comportement qu'un `profils` vide — surtout pas un repli sur le non-filtré."""
    monstres = instantiate_monsters([LOUP], [ARCHER, APPRENTI], 5, [])
    assert len(monstres) == 5
    assert all(m["profil_id"] is None for m in monstres)
    assert all(m["voc_niveau"] == 1 for m in monstres)


def test_les_poids_de_profil_restent_appliques_dans_le_sous_ensemble_compatible():
    """`profil_weights` (distribution de grades d'une zone) continue de jouer APRÈS le
    filtre : un poids porté par un profil incompatible est simplement sans effet."""
    monstres = instantiate_monsters(
        [LOUP], TOUS, 60, [],
        profil_weights={"profil:combattant": 5.0, "profil:archer": 100.0},
    )
    tires = {m["profil_id"] for m in monstres}
    assert tires == {"profil:combattant"}


# ── Non-régression des deux appelants qui portaient déjà la règle ───────────────

def test_les_deux_anciens_porteurs_de_la_regle_passent_par_le_predicat_partage():
    """`chasse._profils_compatibles` et `donjon._profil_max_compatible` n'ont plus de copie
    locale : leur comportement doit rester identique, sur la même donnée."""
    from utils import donjon

    assert donjon._profil_max_compatible(LOUP, TOUS) is COMBATTANT
    assert donjon._profil_max_compatible(CHAMAN, TOUS) in (COMBATTANT, APPRENTI)
    assert donjon._profil_max_compatible(LOUP, [ARCHER]) is None

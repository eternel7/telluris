# tests/test_effets_non_cumul.py
#
# Non-cumul des effets à durée, en deux règles :
#   1. UNE SOURCE = UNE ENTRÉE — relancer le même sort / reboire la même potion / réutiliser
#      la même compétence REMPLACE l'effet en cours (seul le dernier usage compte).
#   2. SUR UNE MÊME CARACT, RIEN NE S'ADDITIONNE — meilleur bonus + pire malus. Deux effets
#      DIFFÉRENTS coexistent avec leurs durées propres : l'expiration du plus fort fait
#      ressortir le plus faible tant qu'il dure.
#
# Logique pure. Import de utils.* → dépend de db.config (connexion tolérée absente).

from utils.consommables import (
    caracts_avec_buffs, caracts_detail, cle_source, cumul_effets, empiler_effet,
    esquive_bonus, poser_effet, regen_bonus, tick_effets,
)
from utils.competences import empiler_effet_competence, normaliser_competence
from utils.sorts import empiler_effet_sort, normaliser_sort


def _perso(**extra):
    base = {
        "caracteristiques_current": {"V": 5, "F": 40, "R": 40, "Ag": 30,
                                     "Vol": 30, "Int": 30, "Cha": 20, "Ch": 20},
        "currentPV": 100, "currentPM": 50,
    }
    base.update(extra)
    return base


def _potion(item_id="item:potion", nom="Potion", **effets):
    return {"_id": item_id, "nom": nom, "icon": "🧪",
            "categorie": "consommable", "poids": 0.2, "effets": effets}


def _eff(nom, buffs=None, restants=2, **extra):
    entry = {"nom": nom, "icon": "✨", "buffs": dict(buffs or {}),
             "regen_pv": 0, "regen_pm": 0, "esquive": 0, "restants": restants}
    entry.update(extra)
    return entry


# ── cle_source : identité d'un effet ─────────────────────────────────────────────

def test_cle_source_par_famille():
    assert cle_source({"sort_id": "sort:givre"}) == "sort:givre"
    assert cle_source({"competence_id": "competence:rage"}) == "competence:rage"
    assert cle_source({"item_id": "item:potion"}) == "item:potion"
    # Entrée posée en combat (le snapshot ne connaît pas la famille de la source).
    assert cle_source({"source_id": "sort:givre"}) == "sort:givre"
    # Anonyme : repli sur le nom, jamais une clé vide qui confondrait deux effets.
    assert cle_source({"nom": "Bénédiction"}) == "nom:Bénédiction"
    assert cle_source({}) != cle_source({"nom": "X"})


def test_une_entree_de_combat_et_une_d_exploration_partagent_la_meme_cle():
    # Un effet posé en combat remonte sur le doc avec `source_id` ; le même sort relancé en
    # exploration timbre `sort_id`. Les deux doivent se reconnaître, sinon l'effet
    # s'empilerait en sortant du combat.
    assert cle_source({"source_id": "sort:givre"}) == cle_source({"sort_id": "sort:givre"})


# ── poser_effet : une source = une entrée ────────────────────────────────────────

def test_poser_effet_remplace_la_meme_source_en_place():
    perso = _perso(effets_actifs=[
        _eff("Potion", {"F": 10}, restants=1, item_id="item:potion"),
        _eff("Hâte", {"Ag": 10}, restants=3, sort_id="sort:hate"),
    ])
    poser_effet(perso, _eff("Potion", {"F": 20}, restants=5, item_id="item:potion"))

    assert len(perso["effets_actifs"]) == 2
    # Remplacement EN PLACE : la chip ne saute pas de rang sous les yeux du joueur.
    assert perso["effets_actifs"][0]["buffs"] == {"F": 20}
    assert perso["effets_actifs"][0]["restants"] == 5
    assert perso["effets_actifs"][1]["nom"] == "Hâte"


def test_poser_effet_sources_differentes_coexistent():
    perso = _perso()
    poser_effet(perso, _eff("Potion", {"F": 10}, item_id="item:potion"))
    poser_effet(perso, _eff("Hâte", {"F": 5}, sort_id="sort:hate"))
    assert len(perso["effets_actifs"]) == 2


def test_reboire_la_meme_potion_ne_cumule_pas():
    perso = _perso()
    potion = _potion(buffs={"F": 10}, duree=5)
    empiler_effet(perso, potion)
    empiler_effet(perso, potion)
    assert len(perso["effets_actifs"]) == 1
    assert caracts_avec_buffs(perso)["F"] == 50


def test_relancer_le_meme_sort_ne_cumule_pas():
    perso = _perso()
    sort = normaliser_sort({"_id": "sort:vigueur", "type": "sort", "nom": "Vigueur",
                            "vocation": "mage", "cout_pm": 3,
                            "effets": {"buffs": {"R": 6}, "duree": 3}})
    empiler_effet_sort(perso, sort, sort["effets"])
    perso["effets_actifs"][0]["restants"] = 1
    empiler_effet_sort(perso, sort, sort["effets"])
    assert len(perso["effets_actifs"]) == 1
    assert perso["effets_actifs"][0]["restants"] == 3   # durée relancée
    assert caracts_avec_buffs(perso)["R"] == 46


def test_relancer_le_meme_sort_avec_composants_remplace_les_effets():
    # « On prend les effets du dernier sort lancé uniquement » : un lancement sans composant
    # après un lancement renforcé rabaisse bel et bien l'effet en cours.
    perso = _perso()
    sort = normaliser_sort({"_id": "sort:vigueur", "type": "sort", "nom": "Vigueur",
                            "vocation": "mage", "cout_pm": 3,
                            "effets": {"buffs": {"R": 6}, "duree": 3}})
    empiler_effet_sort(perso, sort, {"buffs": {"R": 12}, "duree": 3})
    assert caracts_avec_buffs(perso)["R"] == 52
    empiler_effet_sort(perso, sort, sort["effets"])
    assert len(perso["effets_actifs"]) == 1
    assert caracts_avec_buffs(perso)["R"] == 46


def test_reutiliser_la_meme_competence_ne_cumule_pas():
    perso = _perso()
    comp = normaliser_competence({"_id": "competence:rage", "type": "competence", "nom": "Rage",
                                  "vocation": "guerrier", "mode": "active", "cout_pm": 2,
                                  "effets": {"buffs": {"F": 8}, "duree": 2}})
    empiler_effet_competence(perso, comp)
    empiler_effet_competence(perso, comp)
    assert len(perso["effets_actifs"]) == 1
    assert caracts_avec_buffs(perso)["F"] == 48


def test_deux_potions_differentes_coexistent():
    perso = _perso()
    empiler_effet(perso, _potion("item:force", "Élixir", buffs={"F": 10}, duree=5))
    empiler_effet(perso, _potion("item:vigueur", "Vigueur", buffs={"R": 10}, duree=5))
    assert len(perso["effets_actifs"]) == 2
    buffed = caracts_avec_buffs(perso)
    assert buffed["F"] == 50 and buffed["R"] == 50


# ── cumul_effets : meilleur bonus + pire malus ───────────────────────────────────

def test_cumul_retient_le_meilleur_bonus():
    cumul = cumul_effets([_eff("A", {"R": 5}), _eff("B", {"R": 6})])
    assert cumul["buffs"] == {"R": 6}


def test_cumul_retient_le_pire_malus():
    cumul = cumul_effets([_eff("A", {"Ag": -5}), _eff("B", {"Ag": -10})])
    assert cumul["buffs"] == {"Ag": -10}


def test_cumul_additionne_meilleur_bonus_et_pire_malus():
    # Un buff ne peut pas EFFACER un malus, il le contre : +6 et −10 → −4.
    cumul = cumul_effets([_eff("Bénédiction", {"R": 6}), _eff("Givre", {"R": -10})])
    assert cumul["buffs"] == {"R": -4}


def test_cumul_regen_et_esquive_prennent_le_max():
    cumul = cumul_effets([
        _eff("A", regen_pv=2, regen_pm=5, esquive=10),
        _eff("B", regen_pv=3, regen_pm=1, esquive=4),
    ])
    assert cumul["regen_pv"] == 3 and cumul["regen_pm"] == 5
    assert cumul["esquive"] == 10


def test_cumul_liste_vide():
    assert cumul_effets([]) == {"buffs": {}, "regen_pv": 0, "regen_pm": 0, "esquive": 0}


def test_regen_et_esquive_non_cumulees_sur_le_perso():
    perso = _perso(effets_actifs=[
        _eff("A", regen_pv=2, regen_pm=1, esquive=10),
        _eff("B", regen_pv=3, regen_pm=4, esquive=15),
    ])
    assert regen_bonus(perso) == (3, 4)
    assert esquive_bonus(perso) == 15


# ── Le scénario de l'énoncé, tour par tour ───────────────────────────────────────

def test_scenario_deux_effets_durees_differentes():
    # A : 2 rounds, +5 R / +1 F — B : 1 round, +6 R.
    # Round 1 → +6 R et +1 F ; round 2 → +5 R et +1 F.
    perso = _perso(effets_actifs=[
        _eff("A", {"R": 5, "F": 1}, restants=2, sort_id="sort:a"),
        _eff("B", {"R": 6}, restants=1, sort_id="sort:b"),
    ])
    buffed = caracts_avec_buffs(perso)
    assert buffed["R"] == 46 and buffed["F"] == 41   # 40 + 6 (B domine A) et 40 + 1

    tick_effets(perso)                       # B expire, A tient encore un round
    assert [e["nom"] for e in perso["effets_actifs"]] == ["A"]
    buffed = caracts_avec_buffs(perso)
    assert buffed["R"] == 45 and buffed["F"] == 41   # 40 + 5 : le plus faible ressort


# ── Permanents : toujours additifs, et ils s'ajoutent au meilleur effet ──────────

def _eq_bonus(buffs, nom="Dague", icon="🗡️"):
    return {"pv": 0, "pm": 0, "pa": 0, "malus_depl": 0, "cc_bonus": 0, "cd_bonus": 0,
            "degats_bonus": 0, "degats_dice": "", "initiative": 0,
            "buffs": dict(buffs),
            "buffs_sources": [{"nom": nom, "icon": icon, "buffs": dict(buffs)}]}


def test_equipement_et_passives_restent_additifs():
    # Le non-cumul ne vise QUE les effets à durée : deux objets équipés se cumulent bel et
    # bien entre eux, et leur somme s'ajoute au meilleur effet temporaire.
    perso = _perso(
        equipment_bonus=_eq_bonus({"R": 2}),
        competences_bonus={"buffs": {"R": 3}, "regen_pv": 0, "regen_pm": 0, "esquive": 0},
        effets_actifs=[_eff("A", {"R": 6}), _eff("B", {"R": 5})],
    )
    assert caracts_avec_buffs(perso)["R"] == 51      # 40 + 2 + 3 + 6 (pas 5 de plus)


def test_regen_passive_s_ajoute_au_meilleur_effet():
    perso = _perso(
        competences_bonus={"buffs": {}, "regen_pv": 1, "regen_pm": 0, "esquive": 5},
        effets_actifs=[_eff("A", regen_pv=2, esquive=10), _eff("B", regen_pv=3, esquive=4)],
    )
    assert regen_bonus(perso) == (4, 0)              # 1 (passive) + 3 (meilleur effet)
    assert esquive_bonus(perso) == 15                # 5 + 10


# ── caracts_detail : le tooltip dit ce qui est ignoré ────────────────────────────

def test_caracts_detail_marque_les_effets_domines():
    perso = _perso(effets_actifs=[
        _eff("Fort", {"R": 6}, sort_id="sort:fort"),
        _eff("Faible", {"R": 5}, sort_id="sort:faible"),
    ])
    sources = {s["nom"]: s["actif"] for s in caracts_detail(perso)["R"]["sources"]}
    assert sources == {"Fort": True, "Faible": False}


def test_caracts_detail_actif_des_deux_cotes_du_signe():
    # Le meilleur bonus ET le pire malus sont retenus : les deux sont actifs, les autres non.
    perso = _perso(effets_actifs=[
        _eff("Bénédiction", {"R": 6}, sort_id="sort:benediction"),
        _eff("Souffle", {"R": 2}, sort_id="sort:souffle"),
        _eff("Givre", {"R": -10}, sort_id="sort:givre"),
        _eff("Morsure", {"R": -3}, sort_id="sort:morsure"),
    ])
    detail = caracts_detail(perso)["R"]
    assert detail["delta"] == -4                       # 6 − 10
    sources = {s["nom"]: s["actif"] for s in detail["sources"]}
    assert sources == {"Bénédiction": True, "Souffle": False,
                       "Givre": True, "Morsure": False}


def test_caracts_detail_ex_aequo_un_seul_actif():
    # Deux effets identiques : un seul compte, et un seul est marqué actif (premier arrivé).
    perso = _perso(effets_actifs=[
        _eff("A", {"F": 10}, sort_id="sort:a"),
        _eff("B", {"F": 10}, sort_id="sort:b"),
    ])
    detail = caracts_detail(perso)["F"]
    assert detail["delta"] == 10
    assert [s["actif"] for s in detail["sources"]] == [True, False]


def test_caracts_detail_permanents_toujours_actifs():
    perso = _perso(
        equipment_bonus=_eq_bonus({"F": 3}),
        competences_bonus={"buffs": {"F": 4}, "regen_pv": 0, "regen_pm": 0, "esquive": 0,
                           "buffs_sources": [{"nom": "Maîtrise", "icon": "🗡️",
                                              "buffs": {"F": 4}}]},
    )
    assert all(s["actif"] for s in caracts_detail(perso)["F"]["sources"])

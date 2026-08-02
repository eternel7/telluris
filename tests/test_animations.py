# tests/test_animations.py
#
# Animations de combat (utils/animations.py). Logique pure : arithmétique de découpe
# d'une feuille de sprites, bornage du doc `animation:*`, cascade de résolution
# contenu → défaut de canal, et heuristiques de scan vérifiées sur les VRAIS noms et
# dimensions du dossier `templates/resources/icons/effects`.

import pytest

from models import character_stats
from utils import animations as anim


# ── frame_position : l'ordre de lecture ──────────────────────────────────────────

def _grille(colonnes, lignes, sens="haut_bas", sens_cols="gauche_droite"):
    return {"colonnes": colonnes, "lignes": lignes,
            "sens_lignes": sens, "sens_colonnes": sens_cols}


def test_frame_position_haut_bas():
    """DÉFAUT — gauche → droite, puis de HAUT en BAS : la frame 0 est sur la 1re ligne."""
    g = _grille(3, 2)
    assert anim.frame_position(g, 0) == (0, 0)
    assert anim.frame_position(g, 1) == (1, 0)
    assert anim.frame_position(g, 2) == (2, 0)
    assert anim.frame_position(g, 3) == (0, 1)
    assert anim.frame_position(g, 5) == (2, 1)


def test_frame_position_bas_haut():
    """Sens inverse : la frame 0 est sur la DERNIÈRE ligne."""
    g = _grille(3, 2, "bas_haut")
    assert anim.frame_position(g, 0) == (0, 1)
    assert anim.frame_position(g, 3) == (0, 0)
    assert anim.frame_position(g, 5) == (2, 0)


def test_frame_position_droite_gauche():
    """Miroir horizontal : la frame 0 est sur la DERNIÈRE colonne de sa ligne."""
    g = _grille(3, 2, sens_cols="droite_gauche")
    assert anim.frame_position(g, 0) == (2, 0)
    assert anim.frame_position(g, 1) == (1, 0)
    assert anim.frame_position(g, 2) == (0, 0)
    assert anim.frame_position(g, 3) == (2, 1)
    assert anim.frame_position(g, 5) == (0, 1)


def test_frame_position_deux_axes_inverses_lisent_la_feuille_a_l_envers():
    """Les deux axes sont INDÉPENDANTS : les inverser ensemble parcourt exactement la
    feuille dans l'ordre inverse du défaut."""
    normal = _grille(3, 2)
    inverse = _grille(3, 2, "bas_haut", "droite_gauche")
    total = 3 * 2
    for i in range(total):
        assert anim.frame_position(inverse, i) == anim.frame_position(normal, total - 1 - i)


def test_frame_position_sens_inconnu_retombe_sur_les_defauts():
    assert anim.frame_position(_grille(2, 2, "n_importe_quoi", "de_travers"), 0) == (0, 0)
    assert anim.frame_position({"colonnes": 2, "lignes": 2}, 0) == (0, 0)


def test_frame_position_bornee_a_la_grille():
    """Un index hors grille est ramené dans la feuille : jamais de position vide."""
    g = _grille(4, 1)
    assert anim.frame_position(g, 99) == (3, 0)
    assert anim.frame_position(g, -5) == (0, 0)


def test_frame_position_bande_et_colonne():
    assert anim.frame_position(_grille(22, 1), 21) == (21, 0)
    assert anim.frame_position(_grille(1, 10), 0) == (0, 0)
    assert anim.frame_position(_grille(1, 10), 9) == (0, 9)
    assert anim.frame_position(_grille(1, 10, "bas_haut"), 0) == (0, 9)


# ── normaliser_animation : le bornage ────────────────────────────────────────────

def _doc(**extra):
    base = {"_id": "animation:test_a", "type": "animation", "nom": "Test",
            "fichier": "vfx_slash1.png", "largeur": 738, "hauteur": 638,
            "colonnes": 6, "lignes": 5}
    base.update(extra)
    return base


def test_normaliser_sans_fichier_est_none():
    assert anim.normaliser_animation({"_id": "animation:x", "colonnes": 2}) is None
    assert anim.normaliser_animation(None) is None


def test_normaliser_defauts():
    a = anim.normaliser_animation(_doc())
    assert a["sens_lignes"] == "haut_bas"
    # Champ absent ⇒ sens historique : aucune migration.
    assert a["sens_colonnes"] == "gauche_droite"
    assert a["ancrage"] == "cible"
    assert a["duree_ms"] == anim.DUREE_DEFAUT_MS
    assert a["actif"] is False
    # `fin` absent ⇒ toute la feuille.
    assert (a["debut"], a["fin"]) == (0, 29)


def test_normaliser_whitelist_sens_et_ancrage():
    a = anim.normaliser_animation(_doc(sens_lignes="de_biais", sens_colonnes="de_travers",
                                       ancrage="lune"))
    assert a["sens_lignes"] == "haut_bas"
    assert a["sens_colonnes"] == "gauche_droite"
    assert a["ancrage"] == "cible"
    b = anim.normaliser_animation(_doc(sens_lignes="bas_haut", sens_colonnes="droite_gauche",
                                       ancrage="acteur"))
    assert (b["sens_lignes"], b["sens_colonnes"], b["ancrage"]) == (
        "bas_haut", "droite_gauche", "acteur")


def test_normaliser_borne_la_grille_et_la_plage():
    a = anim.normaliser_animation(_doc(colonnes=0, lignes=-3, debut=50, fin=99))
    assert (a["colonnes"], a["lignes"]) == (1, 1)
    assert (a["debut"], a["fin"]) == (0, 0)
    # fin < debut ⇒ ramenée à debut (une plage vide ne joue rien du tout)
    b = anim.normaliser_animation(_doc(debut=10, fin=2))
    assert (b["debut"], b["fin"]) == (10, 10)
    # fin hors grille ⇒ dernière case
    c = anim.normaliser_animation(_doc(colonnes=3, lignes=2, fin=999))
    assert c["fin"] == 5


def test_normaliser_valeurs_de_rendu():
    a = anim.normaliser_animation(_doc(duree_ms=0, echelle=0, decalage_y="0.5"))
    assert a["duree_ms"] >= 1
    assert a["echelle"] == anim.ECHELLE_DEFAUT
    assert a["decalage_y"] == 0.5


# ── catalogue_payload : les brouillons restent invisibles ────────────────────────

def test_catalogue_ne_publie_que_les_actives():
    docs = [
        _doc(_id="animation:a", actif=True),
        _doc(_id="animation:b", actif=False),
        _doc(_id="", actif=True),          # doc sans id : rien à référencer
        {"_id": "animation:c", "actif": True},   # sans fichier : rien à découper
    ]
    cat = anim.catalogue_payload(docs)
    assert list(cat) == ["animation:a"]
    assert set(cat["animation:a"]) == set(anim.CLES_PAYLOAD)
    assert cat["animation:a"]["largeur"] == 738   # le client en tire le ratio d'une frame


# ── Décalage vertical de base ────────────────────────────────────────────────────

def test_decalage_y_effectif_part_de_la_base():
    """Le zéro d'un doc N'EST PAS le sol : le réglage saisi est un ÉCART à la base."""
    assert anim.decalage_y_effectif(0) == anim.DECALAGE_Y_BASE
    assert anim.decalage_y_effectif(0.5) == anim.DECALAGE_Y_BASE + 0.5
    assert anim.decalage_y_effectif("-0.25") == anim.DECALAGE_Y_BASE - 0.25
    # Champ absent ou illisible ⇒ base seule : c'est ce qui rend la règle sans migration.
    assert anim.decalage_y_effectif(None) == anim.DECALAGE_Y_BASE
    assert anim.decalage_y_effectif("plus haut") == anim.DECALAGE_Y_BASE


def test_decalage_x_effectif_part_de_zero():
    """Miroir horizontal, base NULLE : un sprite est déjà centré sur sa case."""
    assert anim.DECALAGE_X_BASE == 0
    assert anim.decalage_x_effectif(0) == 0
    assert anim.decalage_x_effectif(0.25) == 0.25
    assert anim.decalage_x_effectif(None) == anim.DECALAGE_X_BASE
    assert anim.decalage_x_effectif("à droite") == anim.DECALAGE_X_BASE


def test_catalogue_publie_le_decalage_effectif():
    """Le client rend ce qu'on lui donne : la base est déjà DANS le payload, il n'a pas à
    connaître la règle — et le doc, lui, n'est pas touché."""
    doc = _doc(_id="animation:a", actif=True, decalage_y=0.25, decalage_x=-0.5)
    cat = anim.catalogue_payload([doc])
    assert cat["animation:a"]["decalage_y"] == anim.DECALAGE_Y_BASE + 0.25
    assert cat["animation:a"]["decalage_x"] == anim.DECALAGE_X_BASE - 0.5
    assert doc["decalage_y"] == 0.25 and doc["decalage_x"] == -0.5
    # Doc sans les champs : il descend quand même d'une demi-case, et ne bouge pas en X.
    sans = _doc(_id="animation:b", actif=True)
    sans.pop("decalage_y", None)
    sans.pop("decalage_x", None)
    charge = anim.catalogue_payload([sans])["animation:b"]
    assert charge["decalage_y"] == anim.DECALAGE_Y_BASE
    assert charge["decalage_x"] == anim.DECALAGE_X_BASE


# ── Cascade contenu → défaut de canal ────────────────────────────────────────────

@pytest.fixture
def defauts_vierges():
    avant = dict(character_stats.COMBAT_ANIMATIONS_DEFAUT)
    character_stats.COMBAT_ANIMATIONS_DEFAUT.clear()
    character_stats.COMBAT_ANIMATIONS_DEFAUT.update({k: "" for k in avant})
    yield character_stats.COMBAT_ANIMATIONS_DEFAUT
    character_stats.COMBAT_ANIMATIONS_DEFAUT.clear()
    character_stats.COMBAT_ANIMATIONS_DEFAUT.update(avant)


def test_animation_pour_doc_prime_sur_defaut(defauts_vierges):
    defauts_vierges["cac"] = "animation:defaut_a"
    assert anim.animation_pour("cac", "animation:epee_a") == "animation:epee_a"
    assert anim.animation_pour("cac", "") == "animation:defaut_a"
    assert anim.animation_pour("cac", None) == "animation:defaut_a"


def test_animation_pour_canal_vide_ou_inconnu(defauts_vierges):
    assert anim.animation_pour("cac") == ""
    assert anim.animation_pour("canal_inexistant") == ""
    assert anim.animation_pour("") == ""


def test_vfx_none_quand_rien_nest_configure(defauts_vierges):
    """Cas NORMAL : aucun contenu configuré ⇒ pas de clé `vfx` sur l'entrée de journal,
    donc comportement d'avant, sans migration."""
    assert anim.vfx("cac", "monstre_0") is None
    assert anim.vfx("cac", "monstre_0", "") is None


def test_vfx_charge_complete(defauts_vierges):
    defauts_vierges["miss"] = "animation:rate_a"
    assert anim.vfx("miss", "joueur_1") == {"anim": "animation:rate_a", "cible": "joueur_1"}
    assert anim.vfx("cac", "monstre_2", "animation:epee_a") == {
        "anim": "animation:epee_a", "cible": "monstre_2"}
    # Sans cible, rien à animer : le client n'aurait aucune case où poser le sprite.
    assert anim.vfx("cac", "", "animation:epee_a") is None
    assert anim.vfx("cac", None, "animation:epee_a") is None


# ── deviner_grille : sur les vrais fichiers du dossier ───────────────────────────

@pytest.mark.parametrize("nom,largeur,hauteur,attendu", [
    # 1. taille de frame annoncée (les DEUX graphies du dossier)
    ("spritesheet-512px-by-197px-per-frame-red.png", 1536, 394, (3, 2)),
    ("spritesheet-512px-by197px-per-frame-cyan.png", 1536, 394, (3, 2)),
    # 2. nombre d'images annoncé — cases aussi carrées que possible
    ("Smoke15Frames.png", 1280, 768, (5, 3)),
    ("Smoke30Frames.png", 1536, 1279, (6, 5)),
    ("Smoke45Frames.png", 1792, 1792, (7, 7)),   # 49 cases pour 45 images
    # 3. bandes simples
    ("explosion-5.png", 4224, 192, (22, 1)),
    ("Explosion.png", 1152, 96, (12, 1)),
    ("green_effect.png", 32, 320, (1, 10)),
    ("fx.png", 256, 2048, (1, 8)),
    # 4. planches carrées
    ("Effect36.png", 512, 512, (4, 4)),
    ("0.png", 2048, 2048, (16, 16)),
])
def test_deviner_grille_heuristiques(nom, largeur, hauteur, attendu):
    colonnes, lignes, devinee = anim.deviner_grille(nom, largeur, hauteur)
    assert (colonnes, lignes) == attendu
    assert devinee is True


@pytest.mark.parametrize("nom,largeur,hauteur", [
    ("vfx_slash1.png", 738, 638),
    ("explosion_fire.png", 768, 630),
    ("Huge Sheet.png", 1600, 1200),
    ("Aura38.png", 1024, 512),
])
def test_deviner_grille_repli_image_fixe(nom, largeur, hauteur):
    """Grille atypique : 1×1 non devinée — une image fixe honnête plutôt qu'un
    découpage inventé. Se règle à l'aperçu de l'éditeur."""
    assert anim.deviner_grille(nom, largeur, hauteur) == (1, 1, False)


def test_deviner_grille_dimensions_illisibles():
    assert anim.deviner_grille("x.png", 0, 0) == (1, 1, False)


# ── slug_animation ───────────────────────────────────────────────────────────────

def test_slug_animation():
    assert anim.slug_animation("Slash Small Sheet.png") == "animation:slash_small_sheet_a"
    assert anim.slug_animation("10_weaponhit_spritesheet.png") == "animation:10_weaponhit_spritesheet_a"
    assert anim.slug_animation("hit - yellow.png") == "animation:hit_yellow_a"
    # Le suffixe distingue deux animations d'une MÊME feuille (ou deux fichiers de même slug).
    assert anim.slug_animation("Hit-Yellow.png", "b") == "animation:hit_yellow_b"


def test_est_image():
    assert anim.est_image("vfx_slash1.png")
    assert not anim.est_image("Thumbs.db")


# ── Pose de la charge sur le JOURNAL (le seul canal possible) ────────────────────
# Le journal ne porte aucun id, et un tour de monstre est entièrement résolu côté serveur
# avant la réponse HTTP : si la charge n'est pas posée ici, le client n'a rien à animer.

from utils import combat as combat_mod   # noqa: E402  (après les tests purs, volontairement)


def _character():
    return {
        "_id": "character:test_1", "nom": "Frida", "voc": "guerrier", "race": "humain",
        "caracteristiques_current": {"V": 5, "F": 40, "R": 30, "Ag": 40,
                                     "Vol": 30, "Int": 20, "Cha": 20, "Ch": 20},
        "vocations_niveaux": {"guerrier": 1},
        "currentPV": 100, "currentPM": 20, "inventaire": [], "slots": {},
    }


def _espece(**extra):
    base = {"_id": "espece:loup", "nom": "Loup", "tags": [],
            "base_attributes": {c: {"min": v, "max": v} for c, v in
                                (("V", 4), ("F", 30), ("R", 30), ("Ag", 40),
                                 ("Vol", 20), ("Int", 10), ("Cha", 10), ("Ch", 10))}}
    base.update(extra)
    return base


def _combat(joueur, monstres):
    joueur["pos"] = {"x": 3, "y": 5}
    joueur["vivant"] = True
    for m in monstres:
        m["pos"] = {"x": 3, "y": 4}
    return {
        "_id": "combat:test", "type": "combat", "status": "active", "tour": 1, "log": [],
        "ordre_initiative": ["joueur_0"] + [m["id"] for m in monstres],
        "acteur_courant_index": 0,
        "joueurs": [joueur], "monstres": monstres,
        "grid": {"dims": {"x": 7, "y": 7},
                 "cells": [[1] * 7 for _ in range(7)], "nav": {}},
    }


def _scene(monkeypatch, roll=50):
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: roll)
    joueur = combat_mod.build_joueur_snapshot(_character(), 0)
    monstre = combat_mod.build_monster_snapshot(_espece(), None, 0)
    return _combat(joueur, monstre and [monstre])


def _dernier_vfx(combat):
    for entree in reversed(combat["log"]):
        if "vfx" in entree:
            return entree["vfx"]
    return None


def test_journal_sans_animation_na_pas_la_cle(monkeypatch, defauts_vierges):
    """Cas normal, sans migration : rien de configuré ⇒ aucune clé `vfx` nulle part."""
    combat = _scene(monkeypatch)
    combat_mod.resolve_action(combat, "attaquer", cible_id="monstre_0")
    assert all("vfx" not in e for e in combat["log"])


def test_journal_attaque_pose_lanimation_du_mode(monkeypatch, defauts_vierges):
    defauts_vierges["cac"] = "animation:coup_a"
    combat = _scene(monkeypatch)
    combat_mod.resolve_action(combat, "attaquer", cible_id="monstre_0")
    charge = _dernier_vfx(combat)
    assert charge["anim"] == "animation:coup_a"
    assert charge["cible"] == "monstre_0"       # id que le TEXTE ne porte pas
    assert charge["acteur"] == "joueur_0"


def test_journal_attaque_ratee_pose_le_canal_miss(monkeypatch, defauts_vierges):
    defauts_vierges["cac"] = "animation:coup_a"
    defauts_vierges["miss"] = "animation:rate_a"
    combat = _scene(monkeypatch, roll=95)
    combat_mod.resolve_action(combat, "attaquer", cible_id="monstre_0")
    assert _dernier_vfx(combat)["anim"] == "animation:rate_a"


def test_journal_attaque_de_monstre(monkeypatch, defauts_vierges):
    """LE cas qui justifie tout le transport par le journal : un tour de monstre est
    résolu côté serveur, le client ne le voit passer que par là."""
    defauts_vierges["monstre"] = "animation:croc_a"
    # roll 1 = réussite critique : le coup PORTE quel que soit le seuil (cf. _resoudre_jet).
    combat = _scene(monkeypatch, roll=1)
    combat_mod._do_attack_on(combat, combat["monstres"][0], combat["joueurs"][0])
    charge = _dernier_vfx(combat)
    assert charge == {"anim": "animation:croc_a", "cible": "joueur_0", "acteur": "monstre_0"}


def test_journal_animation_despece_prime_sur_le_canal(monkeypatch, defauts_vierges):
    defauts_vierges["monstre"] = "animation:croc_a"
    monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 1)
    joueur = combat_mod.build_joueur_snapshot(_character(), 0)
    monstre = combat_mod.build_monster_snapshot(_espece(animation="animation:morsure_a"), None, 0)
    combat = _combat(joueur, [monstre])
    combat_mod._do_attack_on(combat, monstre, joueur)
    assert _dernier_vfx(combat)["anim"] == "animation:morsure_a"


def test_journal_sort_et_debuff_sont_deux_canaux(monkeypatch, defauts_vierges):
    """Le coup joue l'animation du SORT ; la ligne d'effet joue celle du canal `debuff` —
    deux entrées, deux charges, jamais confondues."""
    defauts_vierges["debuff"] = "animation:givre_a"
    combat = _scene(monkeypatch)
    sdoc = {"_id": "sort:givre", "nom": "Givre", "icon": "❄️", "cible": "ennemi",
            "cout_pm": 0, "portee": 1, "animation": "animation:trait_a",
            "effets": {"degats": "1D4", "buffs": {"Ag": -5}, "duree": 2}}
    combat_mod.resolve_action(combat, "sort", cible_id="monstre_0",
                              sort={"doc": sdoc, "effets": sdoc["effets"]})
    charges = [e["vfx"]["anim"] for e in combat["log"] if "vfx" in e]
    assert charges == ["animation:trait_a", "animation:givre_a"]


def test_journal_animation_darme_prime_sur_le_mode(monkeypatch, defauts_vierges):
    """L'animation vient du PROFIL d'attaque, figé au snapshot : aucun doc d'item n'est
    relu pendant la résolution d'un coup."""
    defauts_vierges["cac"] = "animation:coup_a"
    combat = _scene(monkeypatch)
    for profil in combat["joueurs"][0]["attaque_profils"]:
        if profil["mode"] == "cac":
            profil["animation"] = "animation:hache_a"
    combat_mod.resolve_action(combat, "attaquer", cible_id="monstre_0")
    assert _dernier_vfx(combat)["anim"] == "animation:hache_a"

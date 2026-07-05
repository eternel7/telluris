# tests/test_intro.py
# Logique pure de l'intro narrative (utils/intro.py) : démarrage à la création,
# overlay, choix de raison, conclusion en zone de sécurité. Aucun accès DB.

from utils import intro
from utils.zones import est_dans_zone


# ---------------------------------------------------------------------------
# Fixtures en mémoire
# ---------------------------------------------------------------------------

def _bloc_intro(**over):
    bloc = {
        "titre": "La route d'Auxerre",
        "texte": "Te voilà au bord des bois, {prenom} {nom} ({race}).",
        "texte_conclusion": "Te voilà en sécurité, {prenom}.",
        "xp_conclusion": 2,
        "position_depart": {"x": 4, "y": 20},
        "zone_securite": "zone::coeur",
        "raisons": [
            {"id": "pillage", "label": "Des pillards.", "texte_suite": "Les flammes…"},
            {"id": "secret", "label": "Je préfère n'en rien dire.", "texte_suite": "Soit."},
        ],
    }
    bloc.update(over)
    return bloc


def _ville(bloc=None, _id="lieu:auxerre"):
    lieu = {
        "_id": _id, "type": "lieu",
        "zone_influences": [
            # Ellipse « cœur » centrée (40, 24), 20×10.
            {"zone": "zone::coeur", "forme": "ellipse", "x": 40, "y": 24, "w": 20, "h": 10, "rot": 0},
            # Rectangle forêt à l'ouest.
            {"zone": "zone:foret", "forme": "rectangle", "x": 4, "y": 20, "w": 8, "h": 8, "rot": 0},
        ],
    }
    if bloc is not None:
        lieu["intro"] = bloc
    return lieu


def _character(cite="lieu:auxerre", statut="en_cours", raison=None, position=None):
    c = {
        "prenom": "Aldo", "nom": "Brasfer", "race": "humain",
        "cite": cite, "lieu": cite,
        "position": position or {"x": 4, "y": 20},
    }
    if statut:
        c["intro"] = {"statut": statut}
        if raison:
            c["intro"]["raison"] = raison
    return c


# ---------------------------------------------------------------------------
# est_dans_zone (géométrie)
# ---------------------------------------------------------------------------

def test_est_dans_zone_ellipse_et_rectangle():
    zi = _ville()["zone_influences"]
    assert est_dans_zone(40, 24, "zone::coeur", zi) is True     # centre ellipse
    assert est_dans_zone(49, 24, "zone::coeur", zi) is True     # bord horizontal
    assert est_dans_zone(60, 24, "zone::coeur", zi) is False    # hors ellipse
    assert est_dans_zone(4, 20, "zone:foret", zi) is True
    assert est_dans_zone(4, 20, "zone::coeur", zi) is False     # mauvaise zone
    assert est_dans_zone(40, 24, "zone::inconnue", zi) is False
    assert est_dans_zone(0, 0, "zone::coeur", []) is False


def test_est_dans_zone_rotation():
    # Rectangle 10×2 tourné à 90° : l'axe long devient vertical.
    zi = [{"zone": "z", "forme": "rectangle", "x": 0, "y": 0, "w": 10, "h": 2, "rot": 90}]
    assert est_dans_zone(0, 4, "z", zi) is True
    assert est_dans_zone(4, 0, "z", zi) is False


# ---------------------------------------------------------------------------
# Démarrage (add_character)
# ---------------------------------------------------------------------------

def test_demarrer_pose_position_et_statut():
    character = {"position": {"x": 0, "y": 0}}
    intro.demarrer(character, _ville(_bloc_intro()))
    assert character["position"] == {"x": 4, "y": 20}
    assert character["intro"] == {"statut": "en_cours"}


def test_demarrer_sans_bloc_no_op():
    character = {"position": {"x": 1, "y": 1}}
    intro.demarrer(character, _ville())
    assert character["position"] == {"x": 1, "y": 1}
    assert "intro" not in character


def test_demarrer_sans_position_depart_garde_le_spawn():
    character = {"position": {"x": 1, "y": 1}}
    intro.demarrer(character, _ville(_bloc_intro(position_depart=None)))
    assert character["position"] == {"x": 1, "y": 1}
    assert character["intro"] == {"statut": "en_cours"}


# ---------------------------------------------------------------------------
# Overlay (/play) + raisons
# ---------------------------------------------------------------------------

def test_payload_overlay_substitue_et_liste_les_raisons():
    payload = intro.payload_overlay(_character(), _ville(_bloc_intro()))
    assert payload["titre"] == "La route d'Auxerre"
    assert payload["texte"] == "Te voilà au bord des bois, Aldo Brasfer (humain)."
    assert payload["raisons"] == [
        {"id": "pillage", "label": "Des pillards."},
        {"id": "secret", "label": "Je préfère n'en rien dire."},
    ]


def test_payload_overlay_none_selon_etat():
    ville = _ville(_bloc_intro())
    # Perso sans champ intro (rétro-compat) ou intro terminée.
    assert intro.payload_overlay(_character(statut=None), ville) is None
    assert intro.payload_overlay(_character(statut="terminee"), ville) is None
    # Raison déjà choisie → l'overlay ne revient pas.
    assert intro.payload_overlay(_character(raison="secret"), ville) is None
    # Hors de sa cité.
    assert intro.payload_overlay(_character(), _ville(_bloc_intro(), _id="lieu:autre")) is None
    # Cité sans bloc intro (donnée retirée depuis la création).
    assert intro.payload_overlay(_character(), _ville()) is None


def test_raison_valide():
    ville = _ville(_bloc_intro())
    assert intro.raison_valide(ville, "secret")["texte_suite"] == "Soit."
    assert intro.raison_valide(ville, "inconnue") is None
    assert intro.raison_valide(ville, None) is None
    assert intro.raison_valide(_ville(), "secret") is None


# ---------------------------------------------------------------------------
# Conclusion (move_character)
# ---------------------------------------------------------------------------

def test_conclusion_dans_la_zone_de_securite():
    character = _character(position={"x": 40, "y": 24})
    evt = intro.conclure_si_en_securite(character, _ville(_bloc_intro()))
    assert evt == {"titre": "La route d'Auxerre", "texte": "Te voilà en sécurité, Aldo.", "xp": 2}
    assert character["intro"]["statut"] == "terminee"
    # Idempotence : déjà terminée → None.
    assert intro.conclure_si_en_securite(character, _ville(_bloc_intro())) is None


def test_conclusion_hors_zone_reste_en_cours():
    character = _character(position={"x": 4, "y": 20})  # forêt, pas le cœur
    assert intro.conclure_si_en_securite(character, _ville(_bloc_intro())) is None
    assert character["intro"]["statut"] == "en_cours"


def test_conclusion_hors_cite_no_op():
    character = _character(position={"x": 40, "y": 24})
    autre = _ville(_bloc_intro(), _id="lieu:autre")
    assert intro.conclure_si_en_securite(character, autre) is None
    assert character["intro"]["statut"] == "en_cours"


def test_conclusion_sans_zone_securite_mode_degrade():
    # Sans zone_securite : conclusion au premier déplacement dans la cité.
    character = _character(position={"x": 1, "y": 1})
    bloc = _bloc_intro(zone_securite=None, xp_conclusion=0)
    evt = intro.conclure_si_en_securite(character, _ville(bloc))
    assert evt is not None and evt["xp"] == 0
    assert character["intro"]["statut"] == "terminee"


def test_conclusion_perso_sans_intro_no_op():
    character = _character(statut=None)
    assert intro.conclure_si_en_securite(character, _ville(_bloc_intro())) is None
    assert "intro" not in character

# models/character_document.py
# Structure du document CouchDB pour un personnage
# Les stats dérivées ne sont PAS stockées — recalculées à la demande.

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class CharacterDocument(BaseModel):
    """
    Document CouchDB complet d'un personnage.
    Préfixe _id : "char::<user_id>::<slug_nom>"
    """

    # ── Identité CouchDB ─────────────────────────────────────────────
    id:  Optional[str] = Field(None, alias="_id")
    rev: Optional[str] = Field(None, alias="_rev")
    type: str = "character"

    # ── Appartenance ─────────────────────────────────────────────────
    user_id:    str           # ID du joueur propriétaire
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Identité du personnage ───────────────────────────────────────
    prenom:   str
    nom:      str
    sexe:     str             # "M" | "F"
    race:     str             # "humain" | "elfe" | "nain" | "ogre" | "hobbit"
    vocation: str             # id de vocation
    image: Optional[str] = None   # URL de l'image

    # ── Progression ──────────────────────────────────────────────────
    niveau:    int = 1
    xp_total:  int = 0        # XP accumulée depuis la création
    attribute_points: int = 0  # Points d'attributs attribués à la montée de niveau

    # ── Caractéristiques de base ─────────────────────────────────────
    # Stockées telles quelles, les dérivées sont recalculées
    base_stats: dict = Field(default_factory=lambda: {
        "v": 1, "f": 1, "r": 1, "ag": 1,
        "vol": 1, "int": 1, "cha": 1, "ch": 1
    })

    # ── État actuel (varie en jeu) ───────────────────────────────────
    pv_actuel:  int = 0       # Recalculé = pv_max à la création
    pm_actuel:  int = 0       # Recalculé = pm_max à la création
    ap_actuel:  int = 2       # Actions restantes ce tour

    # ── Équipement (slots) ───────────────────────────────────────────
    # Chaque slot contient l'_id CouchDB de l'item ou null
    slots: dict = Field(default_factory=lambda: {
        "main_droite":  None,   # arme principale
        "main_gauche":  None,   # bouclier ou arme secondaire
        "torse":        None,   # armure
        "tete":         None,
        "jambes":       None,
        "pieds":        None,
        "mains":        None,
        "anneau_1":     None,
        "anneau_2":     None,
        "cou":          None,
        "ceinture":     None,
    })

    # Bonus cumulés de l'équipement (mis à jour quand on équipe/déséquipe)
    equipment_bonus: dict = Field(default_factory=lambda: {
        "pv": 0, "pm": 0, "pa": 0, "malus_depl": 0,
        "cc_bonus": 0, "cd_bonus": 0, "degats_bonus": 0, "initiative": 0
    })

    # ── Inventaire ───────────────────────────────────────────────────
    inventaire: list[str] = []   # Liste d'_id CouchDB d'items

    # ── Finances ─────────────────────────────────────────────────────
    or_:     int = Field(0, alias="or")
    argent:  int = 0
    cuivre:  int = 0

    # ── Localisation ─────────────────────────────────────────────────
    lieu_id:  str = ""        # _id CouchDB du lieu actuel
    position: dict = Field(default_factory=lambda: {"x": 0, "y": 0})

    # ── Relations (affinités) ────────────────────────────────────────
    # { character_id: score (-100 à +100) }
    affinites: dict[str, int] = {}

    # ── Quêtes ───────────────────────────────────────────────────────
    quetes_actives:   list[str] = []
    quetes_terminees: list[str] = []

    model_config = {"populate_by_name": True}


# ── Helper : créer un nouveau personnage avec PV/PM initialisés ───────────────

def init_character(doc: CharacterDocument, pv_max: int, pm_max: int) -> CharacterDocument:
    """
    Appelé une seule fois après la création, pour initialiser
    pv_actuel et pm_actuel au maximum calculé.
    """
    doc.pv_actuel = pv_max
    doc.pm_actuel = pm_max
    return doc


# ── Exemple de document CouchDB résultant ────────────────────────────────────
EXAMPLE_DOCUMENT = {
    "_id":    "char::user_abc123::aldric-von-brunn",
    "type":   "character",
    "user_id": "user_abc123",
    "prenom": "Aldric",
    "nom":    "von Brunn",
    "sexe":   "M",
    "race":   "humain",
    "vocation": "guerrier",
    "image": "guerrier_m_white10.jpg",
    "niveau":  3,
    "xp_total": 45,
    "attribute_points": 5,
    "base_stats": {
        "v": 3, "f": 5, "r": 4, "ag": 3,
        "vol": 2, "int": 2, "cha": 3, "ch": 2
    },
    "pv_actuel": 28,
    "pm_actuel": 8,
    "ap_actuel": 2,
    "equipment_bonus": {
        "pv": 0, "pm": 0, "pa": 4, "malus_depl": 1,
        "cc_bonus": 1, "cd_bonus": 0, "degats_bonus": 1, "initiative": 0
    },
    "or": 150,
    "argent": 30,
    "cuivre": 0,
    "lieu_id": "lieu::auxerre",
    "position": {"x": 43, "y": 24}
}

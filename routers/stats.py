# routers/stats.py
# Endpoints pour le calcul et la récupération des stats dérivées

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from models.character_stats import (
    BaseStats, EquipmentBonus, DerivedStats,
    compute_derived_stats, VOCATION_BONUS
)

router = APIRouter(prefix="/stats", tags=["stats"])


# ── Requête de calcul à la volée ──────────────────────────────────────────────

class StatsRequest(BaseModel):
    base:      BaseStats
    niveau:    int            = 1
    vocation:  str            = "guerrier"
    equipment: EquipmentBonus = EquipmentBonus()


@router.post("/compute", response_model=DerivedStats)
def compute_stats(req: StatsRequest) -> DerivedStats:
    """
    Calcule les stats dérivées depuis les stats de base.
    Utilisé par le front lors de la création de personnage (preview en temps réel)
    et lors de l'équipement d'un item.
    """
    if req.vocation not in VOCATION_BONUS:
        raise HTTPException(
            status_code=422,
            detail=f"Vocation inconnue : '{req.vocation}'. "
                   f"Valeurs acceptées : {list(VOCATION_BONUS.keys())}"
        )
    return compute_derived_stats(
        base=req.base,
        niveau=req.niveau,
        vocation=req.vocation,
        equipment=req.equipment,
    )


# ── Stats d'un personnage depuis CouchDB ──────────────────────────────────────

@router.get("/character/{character_id}", response_model=DerivedStats)
async def get_character_stats(character_id: str):
    """
    Récupère un personnage depuis CouchDB et retourne ses stats dérivées.
    Les stats dérivées ne sont JAMAIS stockées — toujours recalculées.
    """
    # Import ici pour ne pas créer de dépendance circulaire
    from db import get_doc  # votre helper CouchDB existant

    doc = await get_doc(character_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Personnage introuvable")

    try:
        base = BaseStats(**doc["base_stats"])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Stats de base invalides : {e}")

    equipment = EquipmentBonus()
    if "equipment_bonus" in doc:
        equipment = EquipmentBonus(**doc["equipment_bonus"])

    return compute_derived_stats(
        base=base,
        niveau=doc.get("niveau", 1),
        vocation=doc.get("vocation", "guerrier"),
        equipment=equipment,
    )


# ── Bonus de vocation disponibles ────────────────────────────────────────────

@router.get("/vocation/{vocation_id}")
def get_vocation_bonus(vocation_id: str):
    """Retourne les bonus de vocation (utile pour l'UI de création)."""
    if vocation_id not in VOCATION_BONUS:
        raise HTTPException(status_code=404, detail="Vocation inconnue")
    return VOCATION_BONUS[vocation_id]


@router.get("/vocations")
def list_vocation_bonuses():
    """Retourne tous les bonus de vocation."""
    return {k: v.model_dump() for k, v in VOCATION_BONUS.items()}

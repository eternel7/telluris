import math
import random


def _rotate_point(px: float, py: float, cx: float, cy: float, rot_deg: float) -> tuple[float, float]:
    """Rotate (px, py) around (cx, cy) by -rot_deg (inverse rotation to align point with zone axes)."""
    angle = math.radians(-rot_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rx = px - cx
    ry = py - cy
    return (rx * cos_a - ry * sin_a, rx * sin_a + ry * cos_a)


def compute_zone_intensity(px: float, py: float, placement: dict, zone_def: dict | None = None) -> float:
    """Intensité binaire (membership) : on est dans la zone ou on ne l'est pas.

    Renvoie l'`intensite_max` (plate) du zone_def si le point (px, py) est À L'INTÉRIEUR
    de la forme du placement, 0.0 sinon. Plus aucun falloff (linéaire/quadratique/step) :
    aucune gradation par distance au centre — toute la surface vaut pareil.
    """
    bbox = placement.get("bbox")
    if bbox and not (bbox["x_min"] <= px <= bbox["x_max"] and bbox["y_min"] <= py <= bbox["y_max"]):
        return 0.0

    cx, cy = placement["x"], placement["y"]
    half_w = placement["w"] / 2.0
    half_h = placement["h"] / 2.0
    rot = placement.get("rot", 0)
    rx, ry = _rotate_point(px, py, cx, cy, rot)

    forme = placement.get("forme", "ellipse")
    if forme == "rectangle":
        if abs(rx) > half_w or abs(ry) > half_h:
            return 0.0
    else:  # ellipse
        if (rx / half_w) ** 2 + (ry / half_h) ** 2 > 1.0:
            return 0.0

    return (zone_def or {}).get("intensite_max", 1.0)


def compute_bbox(placement: dict) -> dict:
    """Compute the axis-aligned bounding box for a placement, accounting for rotation."""
    cx, cy = placement["x"], placement["y"]
    half_w = placement["w"] / 2.0
    half_h = placement["h"] / 2.0
    rot = placement.get("rot", 0)
    angle = math.radians(rot)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    forme = placement.get("forme", "ellipse")
    if forme == "rectangle":
        # Rotate the 4 corners
        corners = [
            (half_w, half_h), (half_w, -half_h),
            (-half_w, half_h), (-half_w, -half_h),
        ]
        xs = [cx + dx * cos_a - dy * sin_a for dx, dy in corners]
        ys = [cy + dx * sin_a + dy * cos_a for dx, dy in corners]
    else:
        # Tight bbox of a rotated ellipse
        x_extent = math.sqrt((half_w * cos_a) ** 2 + (half_h * sin_a) ** 2)
        y_extent = math.sqrt((half_w * sin_a) ** 2 + (half_h * cos_a) ** 2)
        xs = [cx - x_extent, cx + x_extent]
        ys = [cy - y_extent, cy + y_extent]

    return {"x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys)}


def resolve_zone_event(
    px: float,
    py: float,
    zone_influences: list,
    zone_defs: dict,
    boost: dict | None = None,
) -> dict | None:
    """
    Resolve a movement event from all active zones at (px, py).

    `boost` (focalisation) : {"type": "combat"|"ressource", "mult": float, "zones": set}
    — multiplie le poids des entrées du type visé si l'une des `zones` (zone_def ids)
    est active. Ne touche PAS à la probabilité de déclenchement.

    Returns {"type", "tags", "zones_actives", "intensite", "modificateurs"} or None.
    """
    active = []
    for placement in zone_influences:
        zone_id = placement.get("zone")
        zone_def = zone_defs.get(zone_id)
        if not zone_def:
            continue
        intensity = compute_zone_intensity(px, py, placement, zone_def)
        if intensity > 0.0:
            active.append((intensity, zone_def))

    if not active:
        return None

    proba_globale = max(intensity for intensity, _ in active)
    if random.random() >= proba_globale:
        return None

    # Composite weighted event table
    boost_actif = bool(
        boost and (boost.get("zones") or set()) & {zd.get("_id") for _, zd in active}
    )
    entries = []
    weights = []
    for intensity, zone_def in active:
        for entry in zone_def.get("table_evenements", []):
            w = entry.get("poids", 1) * intensity
            if boost_actif and entry.get("type") == boost["type"]:
                w *= boost["mult"]
            entries.append(entry)
            weights.append(w)

    if not entries:
        return None

    chosen = random.choices(entries, weights=weights, k=1)[0]

    # Merge modificateurs additively
    modificateurs: dict = {}
    for _, zone_def in active:
        for k, v in zone_def.get("modificateurs", {}).items():
            modificateurs[k] = modificateurs.get(k, 0) + v

    return {
        "type": chosen.get("type", "rien"),
        "tags": chosen.get("tags", []),
        "zones_actives": [zd.get("nom", "") for _, zd in active],
        "zones_actives_ids": [zd.get("_id") for _, zd in active if zd.get("_id")],
        "intensite": proba_globale,
        "modificateurs": modificateurs,
    }


def resolve_recolte(event: dict | None, lieu_doc: dict, get_doc_fn,
                    favori: str | None = None, favori_mult: float = 1.0) -> str | None:
    """Ressource récoltable pour un événement de zone de type « ressource ».

    Candidats = items de `lieu_doc["ressources"]` dont les `zones` recoupent les zones
    actives de l'événement. On compare les `tags` de l'entrée d'événement (table_evenements)
    à la `categorie`, la `sous_categorie` (si non vide) et aux `tags` de chaque item. S'il y
    a des correspondances → on en tire une au hasard ; sinon → une ressource au hasard parmi
    les candidats. Renvoie un `item:*` id, ou None (pas de ressource récoltable).

    `favori`/`favori_mult` (focalisation) : l'item favori pèse `favori_mult` dans le
    tirage (1.0 pour les autres) — sans favori, tirage uniforme inchangé.
    """
    def _choix_pondere(ids: list) -> str:
        if favori is None or favori not in ids:
            return random.choice(ids)
        weights = [max(0.0, favori_mult) if iid == favori else 1.0 for iid in ids]
        if sum(weights) <= 0:
            return random.choice(ids)  # repli uniforme (poids tous nuls)
        return random.choices(ids, weights=weights, k=1)[0]

    if not event or event.get("type") != "ressource":
        return None
    zone_ids = set(event.get("zones_actives_ids", []))
    candidats = [
        r.get("ressource")
        for r in (lieu_doc or {}).get("ressources", [])
        if r.get("ressource") and (set(r.get("zones", [])) & zone_ids)
    ]
    if not candidats:
        return None

    tags = {str(t).lower() for t in (event.get("tags") or [])}
    matched = []
    if tags:
        for item_id in candidats:
            item = get_doc_fn(item_id)
            if not item:
                continue
            item_tags = set()
            if item.get("categorie"):
                item_tags.add(str(item["categorie"]).lower())
            if item.get("sous_categorie"):
                item_tags.add(str(item["sous_categorie"]).lower())
            for t in (item.get("tags") or []):
                item_tags.add(str(t).lower())
            if tags & item_tags:
                matched.append(item_id)

    return _choix_pondere(matched) if matched else _choix_pondere(candidats)


def load_zone_defs_for_lieu(lieu_doc: dict, get_doc_fn) -> dict:
    """Batch-fetch all zone definition documents referenced by lieu_doc's zone_influences."""
    ids = {p["zone"] for p in lieu_doc.get("zone_influences", []) if "zone" in p}
    result = {}
    for zone_id in ids:
        doc = get_doc_fn(zone_id)
        if doc:
            result[zone_id] = doc
    return result

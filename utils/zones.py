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


def _apply_falloff(dist_ratio: float, falloff: str, intensite_max: float) -> float:
    if falloff == "quadratique":
        return (dist_ratio ** 2) * intensite_max
    if falloff == "step":
        return intensite_max if dist_ratio > 0 else 0.0
    # lineaire (défaut)
    return dist_ratio * intensite_max


def compute_zone_intensity(px: float, py: float, placement: dict, zone_def: dict) -> float:
    """Return the intensity [0, intensite_max] for point (px, py) in this placement, 0 if outside."""
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
        dist_ratio = 1.0 - max(abs(rx) / half_w, abs(ry) / half_h)
    else:  # ellipse
        d = (rx / half_w) ** 2 + (ry / half_h) ** 2
        if d > 1.0:
            return 0.0
        dist_ratio = 1.0 - math.sqrt(d)

    return _apply_falloff(dist_ratio, zone_def.get("falloff", "lineaire"), zone_def.get("intensite_max", 1.0))


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
) -> dict | None:
    """
    Resolve a movement event from all active zones at (px, py).

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
    entries = []
    weights = []
    for intensity, zone_def in active:
        for entry in zone_def.get("table_evenements", []):
            entries.append(entry)
            weights.append(entry.get("poids", 1) * intensity)

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
        "intensite": proba_globale,
        "modificateurs": modificateurs,
    }


def load_zone_defs_for_lieu(lieu_doc: dict, get_doc_fn) -> dict:
    """Batch-fetch all zone definition documents referenced by lieu_doc's zone_influences."""
    ids = {p["zone"] for p in lieu_doc.get("zone_influences", []) if "zone" in p}
    result = {}
    for zone_id in ids:
        doc = get_doc_fn(zone_id)
        if doc:
            result[zone_id] = doc
    return result

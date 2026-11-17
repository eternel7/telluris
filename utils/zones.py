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


def est_dans_zone(px: float, py: float, zone_id: str, zone_influences: list) -> bool:
    """Le point (px, py) est-il dans AU MOINS un placement du zone-def `zone_id` ?
    Test géométrique pur (membership), sans lire le doc zone (intensité ignorée)."""
    for placement in zone_influences or []:
        if placement.get("zone") != zone_id:
            continue
        if compute_zone_intensity(px, py, placement, {"intensite_max": 1.0}) > 0.0:
            return True
    return False


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
    rand_fn=None,
    facteur_combat: float = 1.0,
) -> dict | None:
    """
    Resolve a movement event from all active zones at (px, py).

    `boost` (focalisation) : {"type": "combat"|"ressource", "mult": float, "zones": set}
    — multiplie le poids des entrées du type visé si l'une des `zones` (clés de
    localisation : zone_def ids, ou `<zone>@<i>` d'un placement à contenu propre) est active. Ne touche PAS à la probabilité de déclenchement.

    `rand_fn` : tirage de déclenchement injectable (tests) — `random.random` par défaut.

    `facteur_combat` (BRUIT du groupe, `utils/bruit.py`) : multiplie la probabilité d'un
    COMBAT, sans toucher à celle des autres événements. Avec I l'intensité et s la part des
    combats dans la table (boost compris) : déclenchement à min(1, I·(s·f + 1 − s)) puis poids
    des combats × f ⇒ P(combat) = I·s·f et P(autre) = I·(1 − s) (au plafond de 1 près).
    L'`intensite` renvoyée reste I : elle règle le budget de menace, que le bruit ne touche pas.

    Returns {"type", "tags", "zones_actives", "intensite", "modificateurs"} or None.
    """
    active = []
    placements_actifs = []
    for placement in zone_influences:
        zone_id = placement.get("zone")
        zone_def = zone_defs.get(zone_id)
        if not zone_def:
            continue
        intensity = compute_zone_intensity(px, py, placement, zone_def)
        if intensity > 0.0:
            active.append((intensity, zone_def))
            placements_actifs.append(placement)
    cles = cles_actives(placements_actifs)

    if not active:
        return None

    proba_globale = max(intensity for intensity, _ in active)

    # Composite weighted event table
    boost_actif = bool(
        boost and (boost.get("zones") or set()) & cles
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

    proba_tirage = proba_globale
    f = max(0.0, float(facteur_combat if facteur_combat is not None else 1.0))
    total = sum(weights)
    if f != 1.0 and total > 0:
        part_combat = sum(w for e, w in zip(entries, weights) if e.get("type") == "combat") / total
        if part_combat > 0:
            proba_tirage = min(1.0, proba_globale * (part_combat * f + 1 - part_combat))
            weights = [w * f if e.get("type") == "combat" else w for e, w in zip(entries, weights)]

    if (rand_fn or random.random)() >= proba_tirage:
        return None

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
        # Clés de localisation (zones + `<zone>@<i>` des placements à contenu propre) : ce
        # que `resolve_recolte` compare aux `zones` des ressources EFFECTIVES (`peupler_lieu`).
        "cles_actives": sorted(cles),
        "intensite": proba_globale,
        "modificateurs": modificateurs,
    }


def resolve_recolte(event: dict | None, lieu_doc: dict, get_doc_fn,
                    favori: str | None = None, favori_mult: float = 1.0) -> str | None:
    """Ressource récoltable pour un événement de zone de type « ressource ».

    Candidats = items de `lieu_doc["ressources"]` dont les `zones` recoupent les clés
    actives de l'événement — `lieu_doc` PEUPLÉ (`peupler_lieu`) : défauts des zones compris. On compare les `tags` de l'entrée d'événement (table_evenements)
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
    zone_ids = set(event.get("cles_actives") or event.get("zones_actives_ids") or [])
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


def resolve_profil_weights(active_placements: list, lieu: dict) -> dict | None:
    """Poids de profils effectifs pour le tirage du grade des monstres.

    Chaîne : cumul (somme) des `profil_weights` des placements de zone actifs qui en
    définissent un → sinon `profil_weights` par défaut du lieu → sinon None (tirage
    uniforme parmi les profils). Les poids non numériques ou ≤ 0 sont ignorés.

    Pur (aucun accès DB) : partagé par `routers/combat.py` (tirage à l'entrée en combat)
    et `utils/chasse.py` (résolution du grade d'une quête de chasse à la génération).
    """
    merged: dict = {}
    for placement in active_placements or []:
        for pid, w in (placement.get("profil_weights") or {}).items():
            if isinstance(w, bool) or not isinstance(w, (int, float)) or w <= 0:
                continue
            merged[pid] = merged.get(pid, 0) + w
    if merged:
        return merged
    return (lieu or {}).get("profil_weights") or None


def especes_rencontrables(lieu: dict | None, zones_actives: set) -> set:
    """Ids d'espèces que les `rencontres` du lieu ([{espece, zones:[zone_def_id]}]) rattachent
    à au moins une des `zones_actives` (clés : `cles_actives` des placements actifs ; lieu
    PEUPLÉ par `peupler_lieu`). SOURCE UNIQUE du pool d'un combat de zone
    (`routers/combat.start_combat`) et de la lecture des traces (`utils/traces.py`)."""
    return {
        r["espece"] for r in (lieu or {}).get("rencontres", []) or []
        if r.get("espece") and (set(r.get("zones", []) or []) & set(zones_actives or ()))
    }


def profils_candidats(profils: list, profil_weights: dict | None) -> tuple[list, list | None]:
    """`(candidats, poids)` du tirage de grade parmi `profils` (déjà filtrés : cap ville,
    compatibilité d'espèce). Avec des `profil_weights` dont au moins un id est présent dans
    `profils` avec un poids > 0 : ces profils-là et leurs poids. Sinon tous les `profils`, et
    `poids = None` (tirage uniforme).

    SOURCE UNIQUE de « quels grades PEUVENT sortir » : le tirage (`combat._pick_profil`) et la
    lecture des traces (`utils/traces.py`, grade le plus haut possible) la partagent.
    """
    if profil_weights:
        by_id = {p["_id"]: p for p in profils}
        candidats, poids = [], []
        for pid, w in profil_weights.items():
            p = by_id.get(pid)
            if p is not None and isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0:
                candidats.append(p)
                poids.append(w)
        if candidats:
            return candidats, poids
    return list(profils), None


def profil_compatible(profil: dict, espece: dict) -> bool:
    """Ce profil peut-il coiffer cette espèce ? `restriction_tags ⊆ tags de l'espèce`.

    SOURCE UNIQUE de la règle, et la seule. Un profil SANS `restriction_tags` convient à
    tout le monde (l'ensemble vide est inclus dans n'importe quel ensemble) : c'est ce qui
    garde `novice`/`combattant`/`veteran`… universels et rend le filtre indolore sur le
    contenu existant. Un profil `distance` ou `magique` exige au contraire que l'espèce
    porte le tag correspondant — un loup ne tire pas à l'arc.

    ⚠️ Pur, et volontairement dans ce module-ci : `utils/zones.py` est une FEUILLE de
    l'arbre d'imports (il ne dépend que de `math`/`random`), donc `utils/combat.py`,
    `utils/chasse.py` et `utils/donjon.py` peuvent tous les trois s'y brancher sans cycle.
    La règle y rejoint `resolve_profil_weights`, qui décide déjà du grade d'un monstre.
    """
    return set((profil or {}).get("restriction_tags") or []) <= set((espece or {}).get("tags") or [])


def profils_compatibles(profils: list, espece: dict) -> list:
    """Les profils de `profils` compatibles avec `espece`, dans l'ordre reçu.

    ⚠️ Peut rendre une liste VIDE — cas d'un contenu où l'on n'a passé que des profils
    restreints. Les appelants doivent traiter ce cas comme ils traitent déjà « aucun
    profil » (`instantiate_monsters` retombe alors sur le point médian de l'espèce), et
    surtout PAS en repliant sur la liste non filtrée : ce repli rouvrirait exactement le
    défaut que ce filtre ferme.
    """
    return [p for p in (profils or []) if profil_compatible(p, espece)]


def terrain_tags_actifs(active_placements: list, zone_defs: dict) -> list:
    """Tags de TERRAIN des zones actives — union des `terrain_tags` de leurs zone-defs.

    ⚠️ DEUX VOCABULAIRES DE TAGS COEXISTENT SUR UN ZONE-DEF, à ne jamais confondre :
    `terrain_tags` décrit le DÉCOR (foret, ville, falaise, chemin…) et sert à choisir la
    battle map d'un combat (`combat.select_battle_map`) ; les `tags` d'une entrée de
    `table_evenements` décrivent le CONTENU de l'événement tiré — pour une entrée
    `type:"combat"` ce sont des noms de créatures (loup, brigand…). Nourrir la sélection
    de décor avec les seconds ne produit jamais aucun recoupement : c'est ce bug qui
    faisait tirer la mine aux cristaux en pleine forêt.

    Pur (aucun accès DB), même forme que `resolve_profil_weights` : les placements
    actifs sont résolus par l'appelant, qui a déjà chargé les defs.
    """
    tags: list = []
    for placement in active_placements or []:
        zone_def = (zone_defs or {}).get(placement.get("zone")) or {}
        for tag in zone_def.get("terrain_tags") or []:
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def load_zone_defs_for_lieu(lieu_doc: dict, get_doc_fn) -> dict:
    """Batch-fetch all zone definition documents referenced by lieu_doc's zone_influences."""
    ids = {p["zone"] for p in lieu_doc.get("zone_influences", []) if "zone" in p}
    result = {}
    for zone_id in ids:
        doc = get_doc_fn(zone_id)
        if doc:
            result[zone_id] = doc
    return result


# ── Contenu PAR DÉFAUT des zones d'influence ─────────────────────────────────────
#
# Une zone porte `defauts_rencontres: [{espece, regions?}]` et `defauts_ressources:
# [{ressource, regions?}]` ; sans `regions` (ou vide) l'entrée vaut partout, sinon seulement
# dans un lieu dont la RÉGION (`rules:regions`) y figure. Le lieu garde ses `rencontres` /
# `ressources` (COMPLÉMENTS, inchangés), peut retirer un défaut par `exclusions:
# [{espece|ressource, zones?}]` (sans `zones` : toutes ses zones), ou couper tous les défauts
# par le tag `sans_defauts_zones`. Un PLACEMENT peut porter ses propres `rencontres` /
# `ressources` (listes d'ids) : valables dans SA forme seulement, sous la clé
# `<zone>@<index>` (`cle_placement`).
#
# ⚠️ POINT DE PASSAGE UNIQUE : `peupler_lieu` rend une COPIE du lieu dont `rencontres` /
# `ressources` sont le contenu EFFECTIF, dans la forme d'avant (`[{espece, zones}]`), et dont
# les placements à contenu propre portent `_cle`. Tout lecteur de ces champs doit passer par
# lui (verrouillé par `test_zones_defauts.test_aucun_lecteur_ne_contourne_peupler_lieu`), puis
# comparer les placements actifs par `cles_actives` / `placement_couvre`, jamais par
# `p["zone"]` seul. Un lieu peuplé ne se sauve JAMAIS (`db.config.save_doc` le refuse).

REGLES_REGIONS = "rules:regions"
TAG_SANS_DEFAUTS = "sans_defauts_zones"
SEP_PLACEMENT = "@"
CHAMPS_CONTENU = (("rencontres", "espece", "defauts_rencontres"),
                  ("ressources", "ressource", "defauts_ressources"))


def cle_placement(zone_id: str, index: int) -> str:
    """Clé de localisation du contenu PROPRE d'un placement (`zone:foret@3`)."""
    return f"{zone_id}{SEP_PLACEMENT}{index}"


def zone_de_cle(cle: str) -> str:
    """Zone d'une clé de localisation : `zone:foret@3` → `zone:foret` (une zone reste elle-même)."""
    return str(cle or "").split(SEP_PLACEMENT, 1)[0]


def cles_actives(placements: list) -> set:
    """Clés de localisation des placements donnés : leurs zones, plus la `_cle` de ceux qui ont
    un contenu propre (posée par `peupler_lieu`). À comparer aux `zones` des entrées effectives."""
    out = set()
    for p in placements or []:
        if p.get("zone"):
            out.add(p["zone"])
        if p.get("_cle"):
            out.add(p["_cle"])
    return out


def placement_couvre(placement: dict, cles: set) -> bool:
    """Le placement correspond-il à l'une de ces clés (sa zone, ou sa clé propre) ?"""
    return bool(cles_actives([placement]) & set(cles or ()))


def index_regions(regles: dict | None) -> dict:
    """`{lieu_id: region}` depuis `rules:regions` (`{"regions": {id: {nom, lieux:[...]}}}`).
    Un lieu listé dans deux régions garde la PREMIÈRE (ordre du doc)."""
    out: dict = {}
    for rid, reg in ((regles or {}).get("regions") or {}).items():
        for lid in (reg or {}).get("lieux") or []:
            out.setdefault(lid, rid)
    return out


def region_de(lieu: dict | None, regles: dict | None, get_doc_fn=None, profondeur: int = 4) -> str | None:
    """Région d'un lieu : celle où `rules:regions` le liste, sinon celle de son `lieu_parent`
    (remonté jusqu'à `profondeur` crans si `get_doc_fn` est fourni), sinon None."""
    idx = index_regions(regles)
    courant = lieu
    for _ in range(profondeur + 1):
        if not courant:
            return None
        rid = idx.get(courant.get("_id"))
        if rid:
            return rid
        parent = courant.get("lieu_parent")
        if not parent or not get_doc_fn or parent == courant.get("_id"):
            return None
        courant = get_doc_fn(parent)
    return None


def _defaut_vaut_ici(entree: dict, region: str | None) -> bool:
    regions = [r for r in (entree.get("regions") or []) if r]
    return not regions or (region is not None and region in regions)


def _exclu(exclusions: list, cle: str, ident: str, zone_id: str) -> bool:
    for e in exclusions or []:
        if e.get(cle) != ident:
            continue
        zones = e.get("zones") or []
        if not zones or zone_id in zones:
            return True
    return False


def contenu_detaille(lieu: dict | None, zone_defs: dict, region: str | None) -> dict:
    """Contenu d'un lieu ligne par ligne, AVEC sa provenance — la lecture de l'aperçu de
    /admin/zones et la source de `contenu_effectif`. Pur.

    `{"rencontres": [ligne], "ressources": [ligne]}`, ligne = `{id, zone (clé de
    localisation, None = tout le lieu), source: "lieu"|"defaut"|"placement", exclu: bool,
    regions}`. Les défauts ne valent que pour les zones POSÉES sur le lieu ; une exclusion ne
    retire qu'un défaut (le contenu écrit du lieu ou d'un placement n'est jamais exclu)."""
    lieu = lieu or {}
    placements = lieu.get("zone_influences") or []
    sans_defauts = TAG_SANS_DEFAUTS in (lieu.get("tags") or [])
    exclusions = lieu.get("exclusions") or []
    zones_posees = []
    for p in placements:
        z = p.get("zone")
        if z and z not in zones_posees:
            zones_posees.append(z)
    out = {}
    for champ, cle, champ_defaut in CHAMPS_CONTENU:
        lignes = []
        for e in lieu.get(champ) or []:
            ident = e.get(cle)
            if not ident:
                continue
            zones = e.get("zones") if "zones" in e else None
            for z in (zones if zones is not None else [None]):
                lignes.append({"id": ident, "zone": z, "source": "lieu", "exclu": False, "regions": []})
        if not sans_defauts:
            for z in zones_posees:
                for d in ((zone_defs or {}).get(z) or {}).get(champ_defaut) or []:
                    ident = d.get(cle)
                    if not ident or not _defaut_vaut_ici(d, region):
                        continue
                    lignes.append({"id": ident, "zone": z, "source": "defaut",
                                   "exclu": _exclu(exclusions, cle, ident, z),
                                   "regions": list(d.get("regions") or [])})
        for i, p in enumerate(placements):
            if not p.get("zone"):
                continue
            for ident in p.get(champ) or []:
                if ident:
                    lignes.append({"id": ident, "zone": cle_placement(p["zone"], i),
                                   "source": "placement", "exclu": False, "regions": []})
        out[champ] = lignes
    return out


def contenu_effectif(lieu: dict | None, zone_defs: dict, region: str | None) -> dict:
    """`{"rencontres": [...], "ressources": [...]}` dans la forme historique du lieu : les
    entrées écrites du lieu d'abord, INTACTES (même ordre, même forme — une entrée sans `zones`
    reste « tout le lieu »), puis une entrée `{cle: id, zones: [...]}` par id apporté par les
    défauts non exclus et les placements, dans l'ordre d'apparition. Pur."""
    lieu = lieu or {}
    detail = contenu_detaille(lieu, zone_defs, region)
    out = {}
    for champ, cle, _ in CHAMPS_CONTENU:
        entrees = [dict(e) for e in lieu.get(champ) or [] if e.get(cle)]
        ajouts: dict = {}
        for ligne in detail[champ]:
            if ligne["source"] == "lieu" or ligne["exclu"]:
                continue
            zones = ajouts.setdefault(ligne["id"], [])
            if ligne["zone"] not in zones:
                zones.append(ligne["zone"])
        entrees += [{cle: ident, "zones": zones} for ident, zones in ajouts.items()]
        out[champ] = entrees
    return out


def peupler_lieu(lieu: dict | None, get_doc_fn) -> dict | None:
    """COPIE du lieu avec son contenu EFFECTIF (défauts des zones posées, filtrés par région,
    + compléments du lieu + contenu des placements − exclusions). Idempotent (`_peuple`), ne
    mute jamais le doc reçu (souvent en cache). Lieu sans placement : rendu tel quel.
    `get_doc_fn` lit les zone-defs et `rules:regions` (contenu caché par process)."""
    if not lieu or lieu.get("_peuple"):
        return lieu
    placements = lieu.get("zone_influences") or []
    if not placements:
        return lieu
    zone_defs = load_zone_defs_for_lieu(lieu, get_doc_fn)
    region = region_de(lieu, get_doc_fn(REGLES_REGIONS), get_doc_fn)
    eff = contenu_effectif(lieu, zone_defs, region)
    copie = dict(lieu)
    copie["zone_influences"] = [
        dict(p, _cle=cle_placement(p["zone"], i))
        if p.get("zone") and (p.get("rencontres") or p.get("ressources")) else p
        for i, p in enumerate(placements)
    ]
    copie["rencontres"] = eff["rencontres"]
    copie["ressources"] = eff["ressources"]
    copie["_peuple"] = True
    return copie


# ── Édition (/admin/zones, /admin/editor) : normalisation et aperçu, purs ────────

def _ids(raw, prefixe: str) -> list:
    """Ids distincts (ordre gardé) d'une liste brute, réduits à ceux qui commencent par `prefixe`."""
    out = []
    for v in raw if isinstance(raw, list) else []:
        v = str(v or "").strip()
        if v.startswith(prefixe) and v not in out:
            out.append(v)
    return out


def normaliser_defauts(raw, cle: str) -> list:
    """`[{cle: id, regions?}]` propre : ids `espece:` / `item:` seuls, dédoublonnés (le premier
    gagne), `regions` = liste d'ids non vides (absente si vide). Lève ValueError sur un id invalide."""
    prefixe = "espece:" if cle == "espece" else "item:"
    out, vus = [], set()
    for e in raw if isinstance(raw, list) else []:
        ident = str((e or {}).get(cle) or "").strip() if isinstance(e, dict) else ""
        if not ident.startswith(prefixe):
            raise ValueError(f"{cle} invalide : {ident or '(vide)'}")
        if ident in vus:
            continue
        vus.add(ident)
        entree = {cle: ident}
        regions = [str(r).strip() for r in (e.get("regions") or []) if str(r or "").strip()]
        if regions:
            entree["regions"] = list(dict.fromkeys(regions))
        out.append(entree)
    return out


def normaliser_contenu_placement(p: dict) -> dict:
    """Placement à écrire : `rencontres` / `ressources` propres (listes d'ids, retirées si vides)
    et JAMAIS de `_cle` (clé de lecture posée par `peupler_lieu`). Mute et renvoie `p`."""
    p.pop("_cle", None)
    for champ, cle, _ in CHAMPS_CONTENU:
        ids = _ids(p.get(champ), "espece:" if cle == "espece" else "item:")
        if ids:
            p[champ] = ids
        else:
            p.pop(champ, None)
    return p


def normaliser_exclusions(raw) -> list:
    """`[{espece|ressource: id, zones?: [...]}]` propre ; une entrée sans id valide est écartée."""
    out = []
    for e in raw if isinstance(raw, list) else []:
        if not isinstance(e, dict):
            continue
        for _, cle, _ in CHAMPS_CONTENU:
            ident = str(e.get(cle) or "").strip()
            if ident.startswith("espece:" if cle == "espece" else "item:"):
                entree = {cle: ident}
                zones = _ids(e.get("zones"), "zone:")
                if zones:
                    entree["zones"] = zones
                out.append(entree)
                break
    return out


def normaliser_regions(raw) -> dict:
    """`{id: {nom, lieux}}` propre : id en minuscules `[a-z0-9_]`, lieux `lieu:*` distincts.
    Lève ValueError sur un id de région invalide."""
    import re
    out = {}
    for rid, reg in (raw or {}).items() if isinstance(raw, dict) else []:
        rid = str(rid or "").strip()
        if not re.fullmatch(r"[a-z0-9_]+", rid):
            raise ValueError(f"id de région invalide : {rid or '(vide)'}")
        reg = reg if isinstance(reg, dict) else {}
        out[rid] = {"nom": str(reg.get("nom") or rid).strip()[:80],
                    "lieux": _ids(reg.get("lieux"), "lieu:")}
    return out


def usage_des_zones(lieux: list) -> dict:
    """`{zone_id: [{id, label, placements}]}` : quels lieux posent chaque zone, et combien de fois."""
    out: dict = {}
    for lieu in lieux or []:
        compte: dict = {}
        for p in lieu.get("zone_influences") or []:
            if p.get("zone"):
                compte[p["zone"]] = compte.get(p["zone"], 0) + 1
        for z, n in compte.items():
            out.setdefault(z, []).append({"id": lieu.get("_id"), "label": lieu.get("label") or lieu.get("nom") or lieu.get("_id"),
                                          "placements": n})
    return out


def apercu_lieu(lieu: dict, zone_defs: dict, region: str | None) -> dict:
    """Aperçu LECTURE SEULE du contenu d'un lieu, zone par zone (/admin/zones) : chaque ligne de
    `contenu_detaille` rangée sous sa zone (le contenu d'un placement sous la zone du placement,
    avec son index), le contenu « tout le lieu » à part. Ordre des zones = ordre de pose."""
    detail = contenu_detaille(lieu, zone_defs, region)
    placements = (lieu or {}).get("zone_influences") or []
    ordre, blocs = [], {}
    for p in placements:
        z = p.get("zone")
        if z and z not in blocs:
            ordre.append(z)
            blocs[z] = {"zone": z, "nom": ((zone_defs or {}).get(z) or {}).get("nom") or z,
                        "placements": 0, "rencontres": [], "ressources": []}
        if z:
            blocs[z]["placements"] += 1
    tout_le_lieu = {"rencontres": [], "ressources": []}
    for champ in ("rencontres", "ressources"):
        # `doublon` : défaut qui recopie une entrée déjà écrite par le lieu pour la même zone (sans
        # effet — l'entrée du lieu pourrait être retirée, le défaut la couvre).
        ecrits = {(l["id"], l["zone"]) for l in detail[champ] if l["source"] == "lieu"}
        for ligne in detail[champ]:
            z = ligne["zone"]
            ligne = dict(ligne, placement=None,
                         doublon=ligne["source"] == "defaut" and (ligne["id"], z) in ecrits)
            if z is None:
                tout_le_lieu[champ].append(ligne)
                continue
            base = zone_de_cle(z)
            if base != z:
                ligne["placement"] = int(z.split(SEP_PLACEMENT, 1)[1])
            if base not in blocs:  # zone citée par le lieu mais posée nulle part
                ordre.append(base)
                blocs[base] = {"zone": base, "nom": ((zone_defs or {}).get(base) or {}).get("nom") or base,
                               "placements": 0, "rencontres": [], "ressources": []}
            blocs[base][champ].append(ligne)
    return {"lieu": (lieu or {}).get("_id"), "region": region,
            "sans_defauts": TAG_SANS_DEFAUTS in ((lieu or {}).get("tags") or []),
            "zones": [blocs[z] for z in ordre], "tout_le_lieu": tout_le_lieu}

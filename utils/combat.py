import re
import math
import random
import uuid
from db.config import get_doc, save_doc, find_docs
from models.character_stats import (
    BaseStats, EquipmentBonus, compute_derived_stats, compute_character_level
)
from utils.lieux import get_final_mask, VALID_MOVES

# (dx, dy) → bit de direction (cf. utils.lieux.VALID_MOVES) pour la validation nav.
_DIR_BIT: dict = {(dx, dy): bit for bit, dx, dy, _op in VALID_MOVES}


def _nav_allows(nav: dict, x: int, y: int, dx: int, dy: int) -> bool:
    """La direction (dx, dy) depuis (x, y) est-elle autorisée par le masque nav ?

    Même sémantique que play_town : `get_final_mask` renvoie les directions permises
    (vérification bidirectionnelle source ↔ cible). nav vide → tout est permis.
    """
    if not nav:
        return True
    bit = _DIR_BIT.get((dx, dy))
    if bit is None:
        return False
    return bool(get_final_mask(nav, x, y) & bit)

BATTLE_MAPS = [
    "map0001.jpg", "map0002.jpg", "map0003.jpg", "map0004.jpg",
    "map0005.jpg", "map0006.jpg", "map0007.jpg", "abandonned_church01.webp",
]


def _compute_actions_max(ag: int, v: int) -> int:
    """Nombre d'actions par tour dérivé des stats : max(1, ceil(Ag/20 + V/5))."""
    return max(1, math.ceil(ag / 20 + v / 5))


# ── Grille de combat ─────────────────────────────────────────────────────────
# Terrain cells[y][x] : -1 inaccessible, 0 inaccessible sauf vol, 1 accessible,
# n>1 accessible sous condition. Le vol n'étant pas implémenté, seuil >= 1.
DEFAULT_GRID_W = 13
DEFAULT_GRID_H = 11


def _open_grid(w: int = DEFAULT_GRID_W, h: int = DEFAULT_GRID_H) -> dict:
    """Grille entièrement praticable (terrain ouvert, fallback sans battle map)."""
    return {"dims": {"x": w, "y": h}, "cells": [[1] * w for _ in range(h)]}


def _passable(cells: list, x: int, y: int) -> bool:
    if not cells or y < 0 or y >= len(cells):
        return False
    row = cells[y]
    if x < 0 or x >= len(row):
        return False
    return row[x] >= 1


def _cheby(a: dict, b: dict) -> int:
    return max(abs(a["pos"]["x"] - b["pos"]["x"]), abs(a["pos"]["y"] - b["pos"]["y"]))


def _occupied_set(combat_doc: dict, exclude: dict | None = None) -> set:
    """Ensemble des (x,y) occupés par des acteurs vivants (hors `exclude`)."""
    occ = set()
    for j in combat_doc["joueurs"]:
        if j is not exclude and j.get("currentPV", 1) > 0:
            occ.add((j["pos"]["x"], j["pos"]["y"]))
    for m in combat_doc["monstres"]:
        if m is not exclude and m["vivant"]:
            occ.add((m["pos"]["x"], m["pos"]["y"]))
    return occ


def _occupied_at(combat_doc: dict, x: int, y: int) -> bool:
    return (x, y) in _occupied_set(combat_doc)


def _move_ap_used_for(actor: dict, cells_moved: int) -> int:
    """AP consommés pour `cells_moved` cases : ceil(cells * actions_max / deplacement)."""
    dep = max(1, actor.get("deplacement", 1))
    return math.ceil(cells_moved * actor["actions_max"] / dep)


def _refresh_actions(actor: dict) -> None:
    """Recalcule actions_restantes = actions_max - attaques - AP_déplacement."""
    used = actor.get("attaques", 0) + _move_ap_used_for(actor, actor.get("cells_moved", 0))
    actor["actions_restantes"] = max(0, actor["actions_max"] - used)


def _reset_turn_budget(actor: dict) -> None:
    """Réinitialise le budget d'un acteur en début de tour."""
    actor["cells_moved"] = 0
    actor["attaques"] = 0
    actor["actions_restantes"] = actor["actions_max"]


def _find_path(cells: list, dims: dict, start: tuple, goal: tuple, blocked: set,
               nav: dict | None = None) -> list | None:
    """A* 4-directions (heuristique Manhattan). Porté du prototype client.

    Bloque les cases non praticables (`cells <= 0`), celles de `blocked` (sauf la case
    d'arrivée, qui peut être occupée par la cible) et les directions interdites par
    `nav` (mêmes restrictions que le joueur / play_town).
    Retourne la liste [(x,y), ...] de start à goal inclus, ou None.
    """
    nav = nav or {}
    w, h = dims["x"], dims["y"]
    sx, sy = start
    gx, gy = goal
    start_node = {"x": sx, "y": sy, "g": 0, "h": abs(gx - sx) + abs(gy - sy), "parent": None}
    start_node["f"] = start_node["h"]
    open_list = [start_node]
    closed = set()

    while open_list:
        open_list.sort(key=lambda n: n["f"])
        cur = open_list.pop(0)
        if cur["x"] == gx and cur["y"] == gy:
            path = []
            node = cur
            while node:
                path.append((node["x"], node["y"]))
                node = node["parent"]
            return path[::-1]
        closed.add((cur["x"], cur["y"]))
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = cur["x"] + dx, cur["y"] + dy
            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                continue
            if not _passable(cells, nx, ny):
                continue
            if not _nav_allows(nav, cur["x"], cur["y"], dx, dy):
                continue
            if (nx, ny) in closed:
                continue
            is_goal = (nx == gx and ny == gy)
            if (nx, ny) in blocked and not is_goal:
                continue
            g = cur["g"] + 1
            existing = next((n for n in open_list if n["x"] == nx and n["y"] == ny), None)
            if existing is None:
                node = {"x": nx, "y": ny, "g": g, "h": abs(gx - nx) + abs(gy - ny), "parent": cur}
                node["f"] = node["g"] + node["h"]
                open_list.append(node)
            elif g < existing["g"]:
                existing["g"] = g
                existing["f"] = g + existing["h"]
                existing["parent"] = cur
    return None


def _nearest_passable(cells: list, dims: dict, tx: int, ty: int, occupied: set) -> tuple:
    """Case praticable et libre la plus proche de (tx, ty) par recherche en spirale."""
    w, h = dims["x"], dims["y"]
    tx = max(0, min(w - 1, tx))
    ty = max(0, min(h - 1, ty))
    for radius in range(0, max(w, h) + 1):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                x, y = tx + dx, ty + dy
                if _passable(cells, x, y) and (x, y) not in occupied:
                    return (x, y)
    return (tx, ty)


# Arène de combat : les acteurs sont regroupés autour du joueur pour rester dans le
# viewport iso (rayon ~7, cf. combat_telluris.html buildViewportClipPath(7)) et à
# portée de marche, quelle que soit la taille de la battle map (jusqu'à 30×30+).
VIEW_RADIUS: int = 7   # rayon visible du viewport iso
SPAWN_DIST:  int = 4   # distance d'apparition des monstres, devant le joueur
SPAWN_SPREAD: int = 2  # étalement horizontal entre monstres


def _place_actors(combat_doc: dict, grid: dict) -> None:
    """Place le joueur en bas-centre (inséré du bord) et les monstres en arène devant lui.

    Les monstres apparaissent à ~SPAWN_DIST cases devant le joueur, étalés autour de
    son axe x — donc dans le champ de caméra et à quelques tours de marche, même sur
    une grande carte. (Avant : monstres collés à y=1, hors champ sur les maps 30×30.)
    """
    cells, dims = grid["cells"], grid["dims"]
    w, h = dims["x"], dims["y"]
    occupied: set = set()

    # Joueur : bas-centre, mais inséré du bord pour que le viewport reste sur la carte.
    inset = min(VIEW_RADIUS, h // 3)
    joueur = combat_doc["joueurs"][0]
    jx, jy = _nearest_passable(cells, dims, w // 2, h - 1 - inset, occupied)
    joueur["pos"] = {"x": jx, "y": jy}
    occupied.add((jx, jy))

    # Monstres : devant le joueur (y plus petit = vers le haut, sens du regard initial),
    # étalés symétriquement autour de jx.
    monstres = combat_doc["monstres"]
    n = len(monstres)
    target_y = max(0, jy - SPAWN_DIST)
    for i, m in enumerate(monstres):
        tx = jx + int(round((i - (n - 1) / 2) * SPAWN_SPREAD))
        mx, my = _nearest_passable(cells, dims, tx, target_y, occupied)
        m["pos"] = {"x": mx, "y": my}
        occupied.add((mx, my))


def select_battle_map(zone_tags: list, depart_lieu: dict | None) -> dict | None:
    """Sélection pondérée d'un lieu battle map selon le recoupement de tags.

    Poids = nb de tags communs entre la battle map et (tags zone ∪ tags lieu départ),
    avec un minimum de 1 pour rester tirable. Retourne le lieu ou None si aucun.
    """
    candidates = [
        b for b in (find_docs({"type": "lieu", "categorie": "battle_map"}) or [])
        if b.get("cells")
    ]
    if not candidates:
        return None
    pool_tags = set(zone_tags or []) | set((depart_lieu or {}).get("tags", []))
    weights = [max(1, len(set(b.get("tags", [])) & pool_tags)) for b in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def get_combat_grid(combat_doc: dict) -> dict:
    """Résout la grille {dims, cells, nav} du combat.

    `cells`/`nav` ne sont PAS dupliqués dans le doc combat : on référence le lieu
    battle map (`battle_map_id`) et on lit sa grille à la demande. `nav` = masque des
    directions interdites par case (cf. utils.lieux.get_final_mask), comme play_town.
    Repli sur une grille ouverte (taille `grid_dims`) si aucun lieu. Tolère un ancien
    doc avec `grid` en ligne.
    """
    bm_id = combat_doc.get("battle_map_id")
    if bm_id:
        lieu = get_doc(bm_id)
        if lieu and lieu.get("cells"):
            return {
                "dims": lieu["dimensions"],
                "cells": lieu["cells"],
                "nav": lieu.get("nav", {}),
            }
    if combat_doc.get("grid", {}).get("cells"):  # rétro-compat docs existants
        grid = combat_doc["grid"]
        grid.setdefault("nav", {})
        return grid
    dims = combat_doc.get("grid_dims") or {"x": DEFAULT_GRID_W, "y": DEFAULT_GRID_H}
    grid = _open_grid(dims["x"], dims["y"])
    grid["nav"] = {}  # grille ouverte = aucune direction interdite
    return grid


def roll_dice(notation: str) -> int:
    """Parse '1D6+3', '2D8', 'D4-1', etc. Returns at least 1."""
    m = re.match(r"(\d*)D(\d+)([+-]\d+)?", notation.upper())
    if not m:
        return 1
    n = int(m.group(1) or "1")
    sides = int(m.group(2))
    mod = int(m.group(3) or "0")
    return max(1, sum(random.randint(1, sides) for _ in range(n)) + mod)


def roll_monster_stats(espece: dict, profil: dict) -> BaseStats:
    base = espece.get("base_attributes", {})
    mods = profil.get("attributs_modifier", {})

    def roll(key):
        bmin = base.get(key, {}).get("min", 1)
        bmax = base.get(key, {}).get("max", 5)
        mod = mods.get(key, {})
        delta = random.randint(mod.get("min", 0), mod.get("max", 0)) if mod else 0
        return max(bmin, min(bmax, bmin + delta))

    return BaseStats(
        v=roll("V"), f=roll("F"), r=roll("R"), ag=roll("Ag"),
        vol=roll("Vol"), int_=roll("Int"), cha=roll("Cha"), ch=roll("Ch"),
    )


def _espece_midpoint(espece: dict) -> BaseStats:
    base = espece.get("base_attributes", {})
    def mid(key):
        bmin = base.get(key, {}).get("min", 1)
        bmax = base.get(key, {}).get("max", 5)
        return (bmin + bmax) // 2
    return BaseStats(
        v=mid("V"), f=mid("F"), r=mid("R"), ag=mid("Ag"),
        vol=mid("Vol"), int_=mid("Int"), cha=mid("Cha"), ch=mid("Ch"),
    )


def build_joueur_snapshot(character: dict, joueur_index: int = 0) -> dict:
    stats = character.get("caracteristiques_current", {})
    base = BaseStats(
        v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
        ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
        cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
    )
    eq_raw = character.get("equipment_bonus", {})
    equipment = EquipmentBonus(
        pv=eq_raw.get("pv", 0), pm=eq_raw.get("pm", 0),
        pa=eq_raw.get("pa", 0), malus_depl=eq_raw.get("malus_depl", 0),
        cc_bonus=eq_raw.get("cc_bonus", 0), cd_bonus=eq_raw.get("cd_bonus", 0),
        degats_bonus=eq_raw.get("degats_bonus", 0),
        initiative=eq_raw.get("initiative", 0),
    )
    voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
    derived = compute_derived_stats(base, niveau=voc_niveau, equipment=equipment)

    return {
        "id": f"joueur_{joueur_index}",
        "character_id": character["_id"],
        "nom": character.get("nom", "Aventurier"),
        "voc": character.get("voc", ""),
        "race": character.get("race", ""),
        "image": character.get("image", ""),
        "currentPV": character.get("currentPV", derived.pv_max),
        "pv_max": derived.pv_max,
        "currentPM": character.get("currentPM", derived.pm_max),
        "pm_max": derived.pm_max,
        "actions_restantes": _compute_actions_max(base.ag, base.v),
        "actions_max": _compute_actions_max(base.ag, base.v),
        "cc": derived.cc,
        "cd": derived.cd,
        "ag": base.ag,
        "pa": derived.pa,
        "degats_cc": derived.degats_cc,
        "degats_cd": derived.degats_cd,
        "initiative": derived.initiative,
        "deplacement": derived.deplacement,
        "portee": 1,
        "pos": {"x": 0, "y": 0},
        "facing": 0,
        "cells_moved": 0,
        "attaques": 0,
    }


def instantiate_monsters(
    especes: list, profils: list, nb: int, zone_tags: list
) -> list:
    matching = [e for e in especes if set(e.get("tags", [])) & set(zone_tags)]
    pool = matching if matching else especes
    if not pool:
        return []

    monstres = []
    for i in range(nb):
        espece = random.choice(pool)
        profil = random.choice(profils) if profils else None

        if profil:
            base_stats = roll_monster_stats(espece, profil)
            niveau = profil.get("niveau", 1)
            profil_id = profil["_id"]
        else:
            base_stats = _espece_midpoint(espece)
            niveau = 1
            profil_id = None

        derived = compute_derived_stats(base_stats, niveau=niveau)
        # XP dérivée de la difficulté : niveau du profil + somme des stats du monstre.
        sum_stats = (
            base_stats.v + base_stats.f + base_stats.r + base_stats.ag
            + base_stats.vol + base_stats.int_ + base_stats.cha + base_stats.ch
        )
        xp_reward = max(1, niveau * 4 + sum_stats // 10)

        monstres.append({
            "id": f"monstre_{i}",
            "nom": espece.get("nom", "Monstre"),
            "espece_id": espece["_id"],
            "profil_id": profil_id,
            "image": espece.get("image", ""),
            "currentPV": max(1, derived.pv_max),
            "pv_max": max(1, derived.pv_max),
            "actions_restantes": _compute_actions_max(base_stats.ag, base_stats.v),
            "actions_max": _compute_actions_max(base_stats.ag, base_stats.v),
            "cc": derived.cc,
            "ag": base_stats.ag,
            "pa": derived.pa,
            "degats_cc": derived.degats_cc,
            "initiative": derived.initiative,
            "deplacement": derived.deplacement,
            "portee": 1,
            "pos": {"x": 0, "y": 0},
            "cells_moved": 0,
            "attaques": 0,
            "vivant": True,
            "xp_reward": xp_reward,
        })

    return monstres


def create_combat_doc(
    character: dict, monstres: list, zone_tags: list, map_image: str,
    battle_map: dict | None = None,
) -> dict:
    joueur = build_joueur_snapshot(character, joueur_index=0)
    joueurs = [joueur]

    all_actors = [(j["id"], j["initiative"]) for j in joueurs]
    all_actors += [(m["id"], m["initiative"]) for m in monstres]
    all_actors.sort(key=lambda x: x[1], reverse=True)
    ordre = [a[0] for a in all_actors]

    combat_id = f"combat:{uuid.uuid4().hex}"
    combat_doc = {
        "_id": combat_id,
        "type": "combat",
        "user_id": character["user_id"],
        "character_id": character["_id"],
        "status": "active",
        "tour": 1,
        "ordre_initiative": ordre,
        "acteur_courant_index": 0,
        "map_image": map_image,
        "zone_tags": zone_tags,
        "joueurs": joueurs,
        "monstres": monstres,
        "log": [{"tour": 1, "acteur": "Système", "kind": "sys", "texte": "Le combat commence !"}],
        "xp_gagnee": 0,
    }
    # On référence le lieu battle map (grille statique non dupliquée). `cells` est
    # résolu à la demande via get_combat_grid(). Repli = grille ouverte.
    if battle_map:
        combat_doc["battle_map_id"] = battle_map["_id"]
        grid = {"dims": battle_map["dimensions"], "cells": battle_map["cells"]}
    else:
        grid = _open_grid()
        combat_doc["grid_dims"] = grid["dims"]
    _place_actors(combat_doc, grid)
    return combat_doc


# ── Helpers internes ────────────────────────────────────────────────────────

def _get_joueur(combat_doc: dict, actor_id: str) -> dict | None:
    for j in combat_doc["joueurs"]:
        if j["id"] == actor_id:
            return j
    return None


def _get_monstre(combat_doc: dict, actor_id: str) -> dict | None:
    for m in combat_doc["monstres"]:
        if m["id"] == actor_id:
            return m
    return None


def _hit_threshold(attaquant_cc: int, defenseur_ag: int) -> int:
    """Seuil de réussite sur un d100 (jet <= seuil = touché).

    Jet sous CC, difficulté = Ag du défenseur : seuil = 50 + CC - Ag.
    Donc CC == Ag → 50 %. Clampé à [5, 95] pour garder toujours une marge.
    """
    return max(5, min(95, 50 + attaquant_cc - defenseur_ag))


def _flee_threshold(joueur_init: int, monstre_init_max: int) -> int:
    """Seuil de fuite sur d100 : 50 + init joueur - meilleure init ennemie, clampé [5, 95]."""
    return max(5, min(95, 50 + joueur_init - monstre_init_max))


def _check_victory(combat_doc: dict) -> None:
    if all(not m["vivant"] for m in combat_doc["monstres"]):
        xp = sum(m["xp_reward"] for m in combat_doc["monstres"])
        combat_doc["xp_gagnee"] = xp
        combat_doc["status"] = "victoire"
        joueur = combat_doc["joueurs"][0]
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": "Système",
            "kind": "sys",
            "texte": f"Victoire ! {xp} XP gagnés.",
        })


def _do_monster_attack(combat_doc: dict, monstre: dict) -> None:
    joueur = combat_doc["joueurs"][0]
    seuil = _hit_threshold(monstre["cc"], joueur.get("ag", 0))
    roll = random.randint(1, 100)
    if roll <= seuil:
        dmg = max(1, roll_dice(monstre["degats_cc"]) - joueur["pa"])
        joueur["currentPV"] = max(0, joueur["currentPV"] - dmg)
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": monstre["nom"],
            "kind": "hit",
            "texte": (
                f"{monstre['nom']} touche {joueur['nom']} pour {dmg} dégâts ! "
                f"(PV : {joueur['currentPV']}/{joueur['pv_max']})"
            ),
        })
        if joueur["currentPV"] <= 0:
            combat_doc["status"] = "defaite"
            combat_doc["log"].append({
                "tour": combat_doc["tour"],
                "acteur": "Système",
                "kind": "sys",
                "texte": f"{joueur['nom']} est à terre !",
            })
    else:
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": monstre["nom"],
            "kind": "miss",
            "texte": f"{monstre['nom']} rate son attaque ! (jet {roll} / seuil {seuil})",
        })


def _monster_step_toward(combat_doc: dict, monstre: dict, joueur: dict, grid: dict) -> bool:
    """Avance le monstre d'une case vers le joueur via A*. Retourne True si déplacé."""
    blocked = _occupied_set(combat_doc, exclude=monstre)
    path = _find_path(
        grid["cells"], grid["dims"],
        (monstre["pos"]["x"], monstre["pos"]["y"]),
        (joueur["pos"]["x"], joueur["pos"]["y"]),
        blocked,
        grid.get("nav", {}),
    )
    if not path or len(path) < 2:
        return False
    nxt = path[1]
    # Ne pas entrer sur la case du joueur (cible) ni une case occupée.
    if nxt == (joueur["pos"]["x"], joueur["pos"]["y"]) or nxt in blocked:
        return False
    # Vérifier qu'il reste assez d'AP pour ce pas (coût proportionnel).
    projected = monstre["attaques"] + _move_ap_used_for(monstre, monstre["cells_moved"] + 1)
    if projected > monstre["actions_max"]:
        return False
    monstre["pos"] = {"x": nxt[0], "y": nxt[1]}
    monstre["cells_moved"] += 1
    _refresh_actions(monstre)
    return True


def _run_monster_turn(combat_doc: dict, monstre: dict, grid: dict) -> None:
    """Tour d'un monstre : se rapprocher du joueur (A*) puis attaquer si à portée."""
    _reset_turn_budget(monstre)
    joueur = combat_doc["joueurs"][0]
    portee = monstre.get("portee", 1)

    # Phase déplacement : avancer vers le joueur tant qu'éloigné et budget dispo.
    steps = 0
    safety = 0
    while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
           and _cheby(monstre, joueur) > portee
           and monstre["cells_moved"] < monstre.get("deplacement", 1)
           and safety < 100):
        safety += 1
        if not _monster_step_toward(combat_doc, monstre, joueur, grid):
            break
        steps += 1
    if steps > 0:
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": monstre["nom"],
            "kind": "move",
            "texte": f"{monstre['nom']} avance vers {joueur['nom']} ({steps} case(s)).",
        })

    # Phase attaque : frapper tant qu'à portée et qu'il reste des actions.
    while (combat_doc["status"] == "active" and monstre["actions_restantes"] > 0
           and _cheby(monstre, joueur) <= portee):
        _do_monster_attack(combat_doc, monstre)
        monstre["attaques"] += 1
        _refresh_actions(monstre)

    idx = combat_doc["acteur_courant_index"] + 1
    if idx >= len(combat_doc["ordre_initiative"]):
        idx = 0
        combat_doc["tour"] += 1
    combat_doc["acteur_courant_index"] = idx


def _resolve_until_player(combat_doc: dict, grid: dict, start_at_current: bool = False) -> None:
    """Run monster turns until it's a player's turn.

    start_at_current=True  : process the actor at acteur_courant_index first (combat init).
    start_at_current=False : advance past the current actor first (after player action).
    """
    ordre = combat_doc["ordre_initiative"]
    max_iter = len(ordre) * 20

    if not start_at_current:
        # Move past current actor before entering the loop
        idx = combat_doc["acteur_courant_index"] + 1
        if idx >= len(ordre):
            idx = 0
            combat_doc["tour"] += 1
        combat_doc["acteur_courant_index"] = idx

    for _ in range(max_iter):
        if combat_doc["status"] != "active":
            break
        actor_id = ordre[combat_doc["acteur_courant_index"]]
        if actor_id.startswith("joueur_"):
            joueur = _get_joueur(combat_doc, actor_id)
            if joueur:
                _reset_turn_budget(joueur)
            break
        monstre = _get_monstre(combat_doc, actor_id)
        if not monstre or not monstre["vivant"]:
            # Dead monster — skip
            idx = combat_doc["acteur_courant_index"] + 1
            if idx >= len(ordre):
                idx = 0
                combat_doc["tour"] += 1
            combat_doc["acteur_courant_index"] = idx
            continue
        _run_monster_turn(combat_doc, monstre, grid)


def _advance_and_resolve(combat_doc: dict, grid: dict) -> None:
    """After a player action: advance past the player and resolve all monster turns."""
    _resolve_until_player(combat_doc, grid, start_at_current=False)


def resolve_first_turns(combat_doc: dict) -> None:
    """Called after combat creation: if monsters go first, resolve their turns."""
    _resolve_until_player(combat_doc, get_combat_grid(combat_doc), start_at_current=True)


# ── API publique ────────────────────────────────────────────────────────────

def resolve_action(
    combat_doc: dict, action_type: str, cible_id: str | None = None,
    dx: int | None = None, dy: int | None = None, sens: int | None = None,
) -> dict:
    ordre = combat_doc["ordre_initiative"]
    actor_id = ordre[combat_doc["acteur_courant_index"]]

    if not actor_id.startswith("joueur_"):
        return {"error": "Ce n'est pas le tour du joueur."}

    joueur = _get_joueur(combat_doc, actor_id)
    if not joueur:
        return {"error": "Joueur introuvable."}
    if joueur["actions_restantes"] <= 0:
        return {"error": "Plus d'actions disponibles."}

    portee = joueur.get("portee", 1)
    grid = get_combat_grid(combat_doc)
    result: dict = {}

    if action_type == "deplacer":
        if dx is None or dy is None:
            return {"error": "Direction manquante."}
        dx = max(-1, min(1, int(dx)))
        dy = max(-1, min(1, int(dy)))
        if dx == 0 and dy == 0:
            return {"error": "Direction nulle."}

        dims, cells = grid["dims"], grid["cells"]
        nx, ny = joueur["pos"]["x"] + dx, joueur["pos"]["y"] + dy
        if nx < 0 or nx >= dims["x"] or ny < 0 or ny >= dims["y"]:
            return {"error": "Hors de la zone."}
        if not _passable(cells, nx, ny):
            return {"error": "Terrain infranchissable."}
        if not _nav_allows(grid.get("nav", {}), joueur["pos"]["x"], joueur["pos"]["y"], dx, dy):
            return {"error": "Direction bloquée."}
        if _occupied_at(combat_doc, nx, ny):
            return {"error": "Case occupée."}
        if joueur["cells_moved"] >= joueur.get("deplacement", 1):
            return {"error": "Budget de déplacement épuisé."}
        projected = joueur["attaques"] + _move_ap_used_for(joueur, joueur["cells_moved"] + 1)
        if projected > joueur["actions_max"]:
            return {"error": "Plus d'actions pour se déplacer."}

        joueur["pos"] = {"x": nx, "y": ny}
        joueur["cells_moved"] += 1
        _refresh_actions(joueur)
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": joueur["nom"],
            "kind": "move",
            "texte": f"{joueur['nom']} se déplace en [{nx},{ny}].",
        })
        result = {"moved": True, "pos": joueur["pos"]}

    elif action_type == "tourner":
        # Rotation ±90° (caméra). Coûte une case du budget de déplacement.
        if sens not in (-1, 1):
            return {"error": "Sens de rotation invalide."}
        if joueur["cells_moved"] >= joueur.get("deplacement", 1):
            return {"error": "Budget de déplacement épuisé."}
        projected = joueur["attaques"] + _move_ap_used_for(joueur, joueur["cells_moved"] + 1)
        if projected > joueur["actions_max"]:
            return {"error": "Plus d'actions pour pivoter."}

        joueur["facing"] = (joueur.get("facing", 0) + sens * 90) % 360
        joueur["cells_moved"] += 1
        _refresh_actions(joueur)
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": joueur["nom"],
            "kind": "move",
            "texte": f"{joueur['nom']} pivote ({'droite' if sens > 0 else 'gauche'}).",
        })
        result = {"turned": True, "facing": joueur["facing"]}

    elif action_type == "attaquer":
        alive = [m for m in combat_doc["monstres"] if m["vivant"]]
        if not alive:
            return {"error": "Aucune cible disponible."}
        if cible_id:
            monstre = _get_monstre(combat_doc, cible_id)
            if not monstre or not monstre["vivant"]:
                return {"error": "Cible invalide."}
            if _cheby(joueur, monstre) > portee:
                return {"error": "Cible hors de portée."}
        else:
            adjacents = [m for m in alive if _cheby(joueur, m) <= portee]
            if not adjacents:
                return {"error": "Aucune cible à portée. Rapprochez-vous."}
            monstre = adjacents[0]

        seuil = _hit_threshold(joueur["cc"], monstre.get("ag", 0))
        roll = random.randint(1, 100)
        if roll <= seuil:
            dmg = max(1, roll_dice(joueur["degats_cc"]) - monstre["pa"])
            monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
            if monstre["currentPV"] <= 0:
                monstre["vivant"] = False
                combat_doc["log"].append({
                    "tour": combat_doc["tour"],
                    "acteur": joueur["nom"],
                    "kind": "kill",
                    "texte": f"{joueur['nom']} élimine {monstre['nom']} !",
                })
            else:
                combat_doc["log"].append({
                    "tour": combat_doc["tour"],
                    "acteur": joueur["nom"],
                    "kind": "hit",
                    "texte": (
                        f"{joueur['nom']} touche {monstre['nom']} pour {dmg} dégâts ! "
                        f"(PV : {monstre['currentPV']}/{monstre['pv_max']})"
                    ),
                })
            result = {"hit": True, "dmg": dmg, "cible": monstre["nom"], "cible_pv": monstre["currentPV"]}
        else:
            combat_doc["log"].append({
                "tour": combat_doc["tour"],
                "acteur": joueur["nom"],
                "kind": "miss",
                "texte": f"{joueur['nom']} rate son attaque sur {monstre['nom']} ! (jet {roll} / seuil {seuil})",
            })
            result = {"hit": False, "roll": roll, "seuil": seuil}

        joueur["attaques"] += 1
        _refresh_actions(joueur)
        _check_victory(combat_doc)

    elif action_type == "passer":
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": joueur["nom"],
            "kind": "sys",
            "texte": f"{joueur['nom']} passe son tour.",
        })
        joueur["actions_restantes"] = 0
        result = {"passed": True}

    elif action_type == "fuir":
        init_max = max(
            (m["initiative"] for m in combat_doc["monstres"] if m["vivant"]),
            default=0,
        )
        seuil = _flee_threshold(joueur["initiative"], init_max)
        flee_roll = random.randint(1, 100)
        if flee_roll <= seuil:
            combat_doc["status"] = "fuite"
            combat_doc["log"].append({
                "tour": combat_doc["tour"],
                "acteur": joueur["nom"],
                "kind": "flee",
                "texte": f"{joueur['nom']} prend la fuite !",
            })
            result = {"fled": True}
        else:
            combat_doc["log"].append({
                "tour": combat_doc["tour"],
                "acteur": joueur["nom"],
                "kind": "flee",
                "texte": f"{joueur['nom']} tente de fuir mais échoue ! (jet {flee_roll}/{seuil})",
            })
            joueur["actions_restantes"] = 0
            result = {"fled": False, "roll": flee_roll, "seuil": seuil}

    else:
        return {"error": f"Action inconnue : {action_type}"}

    if combat_doc["status"] == "active" and joueur["actions_restantes"] <= 0:
        _advance_and_resolve(combat_doc, grid)

    return result


def finalize_combat(combat_doc: dict) -> bool:
    """Applique l'issue du combat (XP/PV) au personnage en base.

    Idempotent ET atomique : l'id du combat est enregistré dans
    `character["combats_recompenses"]`, c.-à-d. DANS LE MÊME document que l'XP.
    La récompense ne peut donc être appliquée qu'une seule fois, même si la
    sauvegarde du doc combat échoue par ailleurs, et reste rattrapable (par /play)
    si `combat_action` n'a pas pu la finaliser.

    Retourne True si une récompense vient d'être appliquée et sauvegardée.
    """
    status = combat_doc.get("status")
    if status not in ("victoire", "defaite", "fuite"):
        return False  # combat encore actif → rien à appliquer

    character = get_doc(combat_doc["character_id"])
    if not character:
        return False

    combat_id = combat_doc.get("_id")
    rewarded = character.get("combats_recompenses", [])
    if combat_id in rewarded:
        combat_doc["recompense_appliquee"] = True  # déjà appliqué à ce personnage
        return False

    joueur = combat_doc["joueurs"][0]
    if status == "victoire":
        character["currentPV"] = joueur["currentPV"]
        xp_before = character.get("xp_total", 0)
        character["xp_total"] = xp_before + combat_doc.get("xp_gagnee", 0)
        old_niveau = compute_character_level(xp_before)
        new_niveau = compute_character_level(character["xp_total"])
        # +N points par niveau gagné (même règle que la montée de niveau monde).
        for n in range(old_niveau + 1, new_niveau + 1):
            character["attribute_points"] = character.get("attribute_points", 0) + n
    elif status == "defaite":
        character["currentPV"] = 1
    elif status == "fuite":
        character["currentPV"] = max(1, joueur["currentPV"])

    # Idempotence atomique : on enregistre le combat dans le doc personnage,
    # sauvegardé avec l'XP. Borné pour éviter une croissance illimitée.
    rewarded.append(combat_id)
    character["combats_recompenses"] = rewarded[-50:]

    if save_doc(character) is None:
        return False  # échec de sauvegarde → ne pas marquer, on réessaiera

    combat_doc["recompense_appliquee"] = True
    return True

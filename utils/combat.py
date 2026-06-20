import re
import random
import uuid
from db.config import get_doc, save_doc, find_docs
from models.character_stats import (
    BaseStats, EquipmentBonus, compute_derived_stats, compute_character_level
)

BATTLE_MAPS = [
    "map0001.jpg", "map0002.jpg", "map0003.jpg", "map0004.jpg",
    "map0005.jpg", "map0006.jpg", "map0007.jpg", "abandonned_church01.webp",
]


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
        "actions_restantes": 2,
        "actions_max": 2,
        "cc": derived.cc,
        "cd": derived.cd,
        "pa": derived.pa,
        "degats_cc": derived.degats_cc,
        "degats_cd": derived.degats_cd,
        "initiative": derived.initiative,
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
        xp_reward = espece.get("proprietes", {}).get("xp_reward", 5)

        monstres.append({
            "id": f"monstre_{i}",
            "nom": espece.get("nom", "Monstre"),
            "espece_id": espece["_id"],
            "profil_id": profil_id,
            "image": espece.get("image", ""),
            "currentPV": max(1, derived.pv_max),
            "pv_max": max(1, derived.pv_max),
            "actions_restantes": 1,
            "actions_max": 1,
            "cc": derived.cc,
            "pa": derived.pa,
            "degats_cc": derived.degats_cc,
            "initiative": derived.initiative,
            "vivant": True,
            "xp_reward": xp_reward,
        })

    return monstres


def create_combat_doc(
    character: dict, monstres: list, zone_tags: list, map_image: str
) -> dict:
    joueur = build_joueur_snapshot(character, joueur_index=0)
    joueurs = [joueur]

    all_actors = [(j["id"], j["initiative"]) for j in joueurs]
    all_actors += [(m["id"], m["initiative"]) for m in monstres]
    all_actors.sort(key=lambda x: x[1], reverse=True)
    ordre = [a[0] for a in all_actors]

    combat_id = f"combat:{uuid.uuid4().hex}"
    return {
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
        "log": [{"tour": 1, "acteur": "Système", "texte": "Le combat commence !"}],
        "xp_gagnee": 0,
    }


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


def _check_victory(combat_doc: dict) -> None:
    if all(not m["vivant"] for m in combat_doc["monstres"]):
        xp = sum(m["xp_reward"] for m in combat_doc["monstres"])
        combat_doc["xp_gagnee"] = xp
        combat_doc["status"] = "victoire"
        joueur = combat_doc["joueurs"][0]
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": "Système",
            "texte": f"Victoire ! {xp} XP gagnés.",
        })


def _do_monster_attack(combat_doc: dict, monstre: dict) -> None:
    joueur = combat_doc["joueurs"][0]
    roll = random.randint(1, 100)
    if roll <= monstre["cc"]:
        dmg = max(1, roll_dice(monstre["degats_cc"]) - joueur["pa"])
        joueur["currentPV"] = max(0, joueur["currentPV"] - dmg)
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": monstre["nom"],
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
                "texte": f"{joueur['nom']} est à terre !",
            })
    else:
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": monstre["nom"],
            "texte": f"{monstre['nom']} rate son attaque ! (jet {roll} / CC {monstre['cc']})",
        })


def _run_monster_turn(combat_doc: dict, monstre: dict) -> None:
    """Execute all actions for a single monster, then advance acteur_courant_index."""
    monstre["actions_restantes"] = monstre["actions_max"]
    while monstre["actions_restantes"] > 0 and combat_doc["status"] == "active":
        _do_monster_attack(combat_doc, monstre)
        monstre["actions_restantes"] -= 1
    idx = combat_doc["acteur_courant_index"] + 1
    if idx >= len(combat_doc["ordre_initiative"]):
        idx = 0
        combat_doc["tour"] += 1
    combat_doc["acteur_courant_index"] = idx


def _resolve_until_player(combat_doc: dict, start_at_current: bool = False) -> None:
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
                joueur["actions_restantes"] = joueur["actions_max"]
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
        _run_monster_turn(combat_doc, monstre)


def _advance_and_resolve(combat_doc: dict) -> None:
    """After a player action: advance past the player and resolve all monster turns."""
    _resolve_until_player(combat_doc, start_at_current=False)


def resolve_first_turns(combat_doc: dict) -> None:
    """Called after combat creation: if monsters go first, resolve their turns."""
    _resolve_until_player(combat_doc, start_at_current=True)


# ── API publique ────────────────────────────────────────────────────────────

def resolve_action(
    combat_doc: dict, action_type: str, cible_id: str | None = None
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

    result: dict = {}

    if action_type == "attaquer":
        if not cible_id:
            alive = [m for m in combat_doc["monstres"] if m["vivant"]]
            if not alive:
                return {"error": "Aucune cible disponible."}
            cible_id = alive[0]["id"]

        monstre = _get_monstre(combat_doc, cible_id)
        if not monstre or not monstre["vivant"]:
            return {"error": "Cible invalide."}

        roll = random.randint(1, 100)
        if roll <= joueur["cc"]:
            dmg = max(1, roll_dice(joueur["degats_cc"]) - monstre["pa"])
            monstre["currentPV"] = max(0, monstre["currentPV"] - dmg)
            if monstre["currentPV"] <= 0:
                monstre["vivant"] = False
                combat_doc["log"].append({
                    "tour": combat_doc["tour"],
                    "acteur": joueur["nom"],
                    "texte": f"{joueur['nom']} élimine {monstre['nom']} !",
                })
            else:
                combat_doc["log"].append({
                    "tour": combat_doc["tour"],
                    "acteur": joueur["nom"],
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
                "texte": f"{joueur['nom']} rate son attaque sur {monstre['nom']} ! (jet {roll} / CC {joueur['cc']})",
            })
            result = {"hit": False, "roll": roll, "cc": joueur["cc"]}

        joueur["actions_restantes"] -= 1
        _check_victory(combat_doc)

    elif action_type == "passer":
        combat_doc["log"].append({
            "tour": combat_doc["tour"],
            "acteur": joueur["nom"],
            "texte": f"{joueur['nom']} passe son tour.",
        })
        joueur["actions_restantes"] = 0
        result = {"passed": True}

    elif action_type == "fuir":
        flee_roll = random.randint(1, 100)
        if flee_roll <= 60:
            combat_doc["status"] = "fuite"
            combat_doc["log"].append({
                "tour": combat_doc["tour"],
                "acteur": joueur["nom"],
                "texte": f"{joueur['nom']} prend la fuite !",
            })
            result = {"fled": True}
        else:
            combat_doc["log"].append({
                "tour": combat_doc["tour"],
                "acteur": joueur["nom"],
                "texte": f"{joueur['nom']} tente de fuir mais échoue ! (jet {flee_roll}/60)",
            })
            joueur["actions_restantes"] = 0
            result = {"fled": False, "roll": flee_roll}

    else:
        return {"error": f"Action inconnue : {action_type}"}

    if combat_doc["status"] == "active" and joueur["actions_restantes"] <= 0:
        _advance_and_resolve(combat_doc)

    return result


def finalize_combat(combat_doc: dict) -> None:
    """Apply combat outcome to the character document in CouchDB.

    Idempotent: the `recompense_appliquee` guard ensures XP/PV are never applied
    twice if this is called again (e.g. on a retry).
    """
    if combat_doc.get("recompense_appliquee"):
        return

    character = get_doc(combat_doc["character_id"])
    if not character:
        return

    joueur = combat_doc["joueurs"][0]
    status = combat_doc["status"]

    if status == "victoire":
        character["currentPV"] = joueur["currentPV"]
        xp_before = character.get("xp_total", 0)
        character["xp_total"] = xp_before + combat_doc.get("xp_gagnee", 0)
        old_niveau = compute_character_level(xp_before)
        new_niveau = compute_character_level(character["xp_total"])
        if new_niveau > old_niveau:
            character["attribute_points"] = character.get("attribute_points", 0) + new_niveau
    elif status == "defaite":
        character["currentPV"] = 1
    elif status == "fuite":
        character["currentPV"] = max(1, joueur["currentPV"])

    # Mark before persisting the character so a re-entry won't double-apply.
    combat_doc["recompense_appliquee"] = True
    save_doc(character)

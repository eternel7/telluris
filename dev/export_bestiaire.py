"""Exporte le bestiaire (espece:*) + les races jouables (rules:races) vers un Excel.

Feuille unique « Bestiaire » : colonnes partagées entre espèces et races jouables —
attributs au min/max, puis stats dérivées de combat calculées (PV, CC, CT, PA, dégâts…)
au min et au max, **grisées** pour les distinguer des entrées brutes. Outil de
diagnostic d'équilibrage (p. ex. combats trop longs).

Aucune dépendance externe : le .xlsx (Office Open XML) est écrit à la main avec la
librairie standard (`zipfile`). À lancer DANS le conteneur fastapi en marche, où
`couchdb2` est installé et le hostname `couchdb` résout :

    docker compose exec fastapi python dev/export_bestiaire.py

Le fichier `bestiaire.xlsx` est écrit à la racine du repo (volume monté), donc il
apparaît côté hôte dans Z:\\telluris\\bestiaire.xlsx.
"""

import os
import sys
import json

# Permet d'importer les modules de l'app quel que soit le cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.config import find_docs, get_doc  # noqa: E402
from models.character_stats import BaseStats, compute_derived_stats  # noqa: E402
from utils.xlsx import write_xlsx, build_xlsx_bytes  # noqa: E402

STATS = ["V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"]
# Clé attribut (CouchDB) → champ BaseStats.
_STAT_FIELD = {
    "V": "v", "F": "f", "R": "r", "Ag": "ag",
    "Vol": "vol", "Int": "int_", "Cha": "cha", "Ch": "ch",
}
# Stats dérivées exportées : (libellé, attribut DerivedStats).
DERIVED = [
    ("PV", "pv_max"), ("PM", "pm_max"), ("Init", "initiative"), ("Dépl", "deplacement"),
    ("CC", "cc"), ("CT", "cd"), ("PA", "pa"), ("PM déf", "pm_def"), ("Touch. mag", "toucher_magique"),
    ("Dég. CC", "degats_cc"), ("Dég. CT", "degats_cd"),
]


def _derived(stat_values):
    """DerivedStats calculé à partir d'un dict {clé attribut: valeur} (niveau sans impact combat)."""
    base = BaseStats(**{_STAT_FIELD[k]: int(stat_values.get(k, 0) or 0) for k in STATS})
    return compute_derived_stats(base, niveau=0)


# ── Construction de la feuille ───────────────────────────────────────────────
def bestiaire_sheet(especes, races):
    """Feuille unique : races jouables + espèces, colonnes partagées.

    Attributs au min/max ; bloc de stats dérivées calculées (grisé) au min et au max.
    Pour une espèce : min/max = bornes de `base_attributes`. Pour une race jouable :
    min = base racial (`stats`), max = cap racial (`stats_max`).
    """
    headers = ["type", "_id", "nom", "image", "tags", "description"]
    for s in STATS:
        headers += [f"{s} min", f"{s} max"]
    derived_start = len(headers)
    for lbl, _ in DERIVED:
        headers += [f"{lbl} min", f"{lbl} max"]
    greyed = set(range(derived_start, len(headers)))
    headers += ["xp_reward", "proprietes (json)"]

    rows = [headers]

    def _row(type_, _id, nom, image, tags, description, min_stats, max_stats, xp_reward, props):
        row = [type_, _id, nom, image, tags, description]
        for s in STATS:
            row += [min_stats.get(s, ""), max_stats.get(s, "")]
        dmin, dmax = _derived(min_stats), _derived(max_stats)
        for _, attr in DERIVED:
            row += [getattr(dmin, attr), getattr(dmax, attr)]
        row += [xp_reward, props]
        return row

    # Races jouables d'abord (référence « débutant » → « maxé »).
    for r in sorted(races, key=lambda d: (d.get("label") or d.get("id") or "")):
        rows.append(_row(
            "race jouable", r.get("id", ""), r.get("label", r.get("id", "")),
            "", "", "", r.get("stats", {}) or {}, r.get("stats_max", {}) or {}, "", "",
        ))

    # Espèces.
    for e in sorted(especes, key=lambda d: (d.get("nom") or d.get("_id") or "")):
        base = e.get("base_attributes", {}) or {}
        props = e.get("proprietes", {}) or {}
        min_stats = {s: (base.get(s, {}) or {}).get("min", 0) for s in STATS}
        max_stats = {s: (base.get(s, {}) or {}).get("max", 0) for s in STATS}
        rows.append(_row(
            "espèce", e.get("_id", ""), e.get("nom", ""), e.get("image", ""),
            ", ".join(e.get("tags", []) or []), e.get("description", ""),
            min_stats, max_stats,
            props.get("xp_reward", ""), json.dumps(props, ensure_ascii=False),
        ))

    return ("Bestiaire", rows, greyed)


def _build_sheets():
    # Espèces + races jouables dans une feuille unique (profils non inclus).
    especes = find_docs({"type": "espece"}) or []
    races = (get_doc("rules:races") or {}).get("value", []) or []
    return [bestiaire_sheet(especes, races)], len(especes), len(races)


def build_bestiaire_xlsx_bytes() -> bytes:
    """Construit le classeur en mémoire et renvoie les octets .xlsx (pour HTTP)."""
    sheets, _, _ = _build_sheets()
    return build_xlsx_bytes(sheets)


def main():
    sheets, nb_especes, nb_races = _build_sheets()
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bestiaire.xlsx"
    )
    write_xlsx(out_path, sheets)
    print(f"{nb_especes} espèces, {nb_races} races → {out_path}")


if __name__ == "__main__":
    main()

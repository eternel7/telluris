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
import io
import json
import zipfile

# Permet d'importer les modules de l'app quel que soit le cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.config import find_docs, get_doc  # noqa: E402
from models.character_stats import BaseStats, compute_derived_stats  # noqa: E402

STATS = ["V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"]
# Clé attribut (CouchDB) → champ BaseStats.
_STAT_FIELD = {
    "V": "v", "F": "f", "R": "r", "Ag": "ag",
    "Vol": "vol", "Int": "int_", "Cha": "cha", "Ch": "ch",
}
# Stats dérivées exportées : (libellé, attribut DerivedStats).
DERIVED = [
    ("PV", "pv_max"), ("PM", "pm_max"), ("Init", "initiative"), ("Dépl", "deplacement"),
    ("CC", "cc"), ("CT", "cd"), ("PA", "pa"), ("PM déf", "pm_def"),
    ("Dég. CC", "degats_cc"), ("Dég. CT", "degats_cd"),
]


def _derived(stat_values):
    """DerivedStats calculé à partir d'un dict {clé attribut: valeur} (niveau sans impact combat)."""
    base = BaseStats(**{_STAT_FIELD[k]: int(stat_values.get(k, 0) or 0) for k in STATS})
    return compute_derived_stats(base, niveau=0)


# ── Mini-writer XLSX (stdlib uniquement) ─────────────────────────────────────
def _xml_escape(s):
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&apos;")
    )


def _col_ref(idx):
    """0 -> A, 25 -> Z, 26 -> AA …"""
    s = ""
    idx += 1
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


# Feuille de styles : xf 0 = défaut, xf 1 = remplissage gris (champs calculés).
# fills : index 0 (none) et 1 (gray125) réservés par la spec ; gris solide en index 2.
_STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="3">'
    '<fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFD9D9D9"/><bgColor indexed="64"/></patternFill></fill>'
    "</fills>"
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="2">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/>'
    "</cellXfs>"
    "</styleSheet>"
)


def _sheet_xml(rows, greyed_cols=frozenset()):
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r, row in enumerate(rows, start=1):
        out.append(f'<row r="{r}">')
        for c, val in enumerate(row):
            ref = f"{_col_ref(c)}{r}"
            s_attr = ' s="1"' if c in greyed_cols else ""
            if isinstance(val, bool):
                val = str(val)
            if isinstance(val, (int, float)):
                out.append(f'<c r="{ref}"{s_attr}><v>{val}</v></c>')
            else:
                out.append(
                    f'<c r="{ref}"{s_attr} t="inlineStr"><is>'
                    f'<t xml:space="preserve">{_xml_escape(val)}</t></is></c>'
                )
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path, sheets):
    """sheets : liste de (nom_feuille, rows, greyed_cols) ; rows = liste de listes de cellules."""
    n = len(sheets)
    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for i in range(n):
        content_types.append(
            f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    content_types.append("</Types>")

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    wb_sheets = "".join(
        f'<sheet name="{_xml_escape(name)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
        for i, (name, _, _) in enumerate(sheets)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{wb_sheets}</sheets></workbook>"
    )

    wb_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for i in range(n):
        wb_rels.append(
            f'<Relationship Id="rId{i + 1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i + 1}.xml"/>'
        )
    # rId hors de la plage des feuilles pour la feuille de styles.
    wb_rels.append(
        f'<Relationship Id="rId{n + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    wb_rels.append("</Relationships>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(content_types))
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wb_rels))
        z.writestr("xl/styles.xml", _STYLES_XML)
        for i, (_, rows, greyed_cols) in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", _sheet_xml(rows, greyed_cols))


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
    buf = io.BytesIO()
    write_xlsx(buf, sheets)
    return buf.getvalue()


def main():
    sheets, nb_especes, nb_races = _build_sheets()
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bestiaire.xlsx"
    )
    write_xlsx(out_path, sheets)
    print(f"{nb_especes} espèces, {nb_races} races → {out_path}")


if __name__ == "__main__":
    main()

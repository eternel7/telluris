"""Exporte le bestiaire (espece:*) de CouchDB vers un fichier Excel (feuille « Espèces »).

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

# Permet d'importer db.config quel que soit le cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.config import find_docs  # noqa: E402

STATS = ["V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"]


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


def _sheet_xml(rows):
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r, row in enumerate(rows, start=1):
        out.append(f'<row r="{r}">')
        for c, val in enumerate(row):
            ref = f"{_col_ref(c)}{r}"
            if isinstance(val, bool):
                val = str(val)
            if isinstance(val, (int, float)):
                out.append(f'<c r="{ref}"><v>{val}</v></c>')
            else:
                out.append(
                    f'<c r="{ref}" t="inlineStr"><is>'
                    f'<t xml:space="preserve">{_xml_escape(val)}</t></is></c>'
                )
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path, sheets):
    """sheets : liste de (nom_feuille, rows) ; rows = liste de listes de cellules."""
    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
    ]
    for i in range(len(sheets)):
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
        for i, (name, _) in enumerate(sheets)
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
    for i in range(len(sheets)):
        wb_rels.append(
            f'<Relationship Id="rId{i + 1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i + 1}.xml"/>'
        )
    wb_rels.append("</Relationships>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(content_types))
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wb_rels))
        for i, (_, rows) in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", _sheet_xml(rows))


# ── Construction des feuilles ────────────────────────────────────────────────
def especes_sheet(especes):
    headers = ["_id", "nom", "image", "tags", "description"]
    for s in STATS:
        headers += [f"{s} min", f"{s} max"]
    headers += ["xp_reward", "proprietes (json)"]
    rows = [headers]
    for e in sorted(especes, key=lambda d: (d.get("nom") or d.get("_id") or "")):
        base = e.get("base_attributes", {}) or {}
        props = e.get("proprietes", {}) or {}
        row = [
            e.get("_id", ""), e.get("nom", ""), e.get("image", ""),
            ", ".join(e.get("tags", []) or []), e.get("description", ""),
        ]
        for s in STATS:
            cell = base.get(s, {}) or {}
            row += [cell.get("min", ""), cell.get("max", "")]
        row += [props.get("xp_reward", ""), json.dumps(props, ensure_ascii=False)]
        rows.append(row)
    return ("Espèces", rows)


def _build_sheets():
    # Export du bestiaire : espèces uniquement (les profils ne sont pas inclus).
    especes = find_docs({"type": "espece"}) or []
    return [especes_sheet(especes)], len(especes)


def build_bestiaire_xlsx_bytes() -> bytes:
    """Construit le classeur en mémoire et renvoie les octets .xlsx (pour HTTP)."""
    sheets, _ = _build_sheets()
    buf = io.BytesIO()
    write_xlsx(buf, sheets)
    return buf.getvalue()


def main():
    sheets, nb_especes = _build_sheets()
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bestiaire.xlsx"
    )
    write_xlsx(out_path, sheets)
    print(f"{nb_especes} espèces → {out_path}")


if __name__ == "__main__":
    main()

"""Mini-writer XLSX (Office Open XML) sans dépendance externe — librairie standard.

Écrit un classeur `.xlsx` (ZIP de parties XML) via `zipfile`. Briques génériques,
partagées entre :
- l'export bestiaire d'équilibrage (`dev/export_bestiaire.py`) ;
- l'export du tableau d'administration (`POST /admin/table/export.xlsx`, `main.py`).

Une feuille = `(nom, rows, greyed_cols)` où `rows` est une liste de listes de
cellules (la 1re ligne = en-têtes) et `greyed_cols` un ensemble d'indices de
colonnes à griser (style `s="1"`). Types de cellule reconnus : `int`/`float`
(cellule numérique), `bool`/`str` (chaîne). Pour sérialiser des documents en
lignes, voir `rows_from_docs`.
"""

import io
import json
import re
import zipfile

# Caractères de contrôle interdits en XML 1.0 (tout sauf \t \n \r). Retirés avant
# échappement : sinon un octet parasite (p. ex. NUL) casse le fichier.
_XML_CTRL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _xml_escape(s):
    s = _XML_CTRL_RE.sub("", str(s))
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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
    """sheets : liste de (nom_feuille, rows, greyed_cols) ; rows = liste de listes de cellules.

    `path` accepte un chemin de fichier OU un objet fichier (p. ex. io.BytesIO)."""
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


def build_xlsx_bytes(sheets) -> bytes:
    """Construit le classeur en mémoire et renvoie les octets .xlsx (pour HTTP)."""
    buf = io.BytesIO()
    write_xlsx(buf, sheets)
    return buf.getvalue()


def _cell(v):
    """Normalise une valeur de document en cellule : None→"" ; dict/list→JSON ;
    nombres/bool/str laissés tels quels (typage géré par `_sheet_xml`)."""
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def rows_from_docs(columns, docs):
    """Matrice tableur : ligne d'en-têtes (`columns`) + une ligne par document,
    une colonne par clé. Valeurs normalisées par `_cell`."""
    cols = list(columns)
    rows = [cols]
    for d in docs:
        d = d if isinstance(d, dict) else {}
        rows.append([_cell(d.get(c)) for c in cols])
    return rows

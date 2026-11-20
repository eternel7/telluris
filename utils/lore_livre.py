"""Le lore en livre (pur) : sélection de pages, EPUB 3 en stdlib (zipfile, comme
utils/xlsx.py) et chapitres pour la page imprimable `/admin/lore/livre` (Imprimer → PDF).

Le HTML des chapitres vient de `lore.rendre` (texte déjà échappé) ; on le rend XHTML
(balises vides fermées) et on réécrit les liens : vers un chapitre du livre s'il y est,
sinon le lien disparaît et seul son texte reste (le livre se lit hors ligne).
"""

import html
import io
import re
import zipfile
from datetime import datetime, timezone

from utils import lore

SELECTIONS = {
	"redige": "Le lore rédigé",
	"parcours": "Découvrir Telluris (parcours guidé)",
}


def libelle_selection(nom: str) -> str:
	return SELECTIONS.get(nom) or lore.libelle_section(nom)


def selection(nom: str, entrees: list, parcours: dict) -> list:
	"""Entrées d'une sélection : `redige`, `parcours`, ou le nom d'une section du lore."""
	if nom == "parcours":
		par_cle = {e["cle"]: e for e in entrees}
		return [par_cle[et["cle"]] for et in parcours.get("etapes", []) if et["cle"] in par_cle]
	return [e for e in entrees if e["section"] == nom]


def selections_disponibles(entrees: list) -> list:
	"""[(nom, libellé, nombre de pages)] proposées à l'export, rédigé et parcours d'abord."""
	out = [("redige", SELECTIONS["redige"]), ("parcours", SELECTIONS["parcours"])]
	vues = {"redige"}
	for e in entrees:
		if e["section"] not in vues:
			vues.add(e["section"])
			out.append((e["section"], e["section_label"]))
	return out


def nom_fichier(nom: str) -> str:
	"""Nom de fichier sûr de l'EPUB d'une sélection (aucun caractère hors [a-z0-9_])."""
	return "telluris_lore_" + (re.sub(r"[^a-z0-9_]+", "_", nom.lower()).strip("_") or "lore") + ".epub"


_RE_VIDE = re.compile(r"<(br|hr)>")
_RE_LIEN = re.compile(r'<a href="([^"]*)"[^>]*>(.*?)</a>', re.S)


def xhtml(corps: str, chapitre_de: dict) -> str:
	"""HTML de `lore.rendre` → XHTML de livre ; `chapitre_de` = {clé de lore: nom de fichier}."""
	corps = _RE_VIDE.sub(r"<\1/>", corps)

	def lien(m):
		href, texte = html.unescape(m.group(1)), m.group(2)
		if href.startswith("#"):
			return m.group(0)
		if href.startswith(lore.URL_LORE):
			cle, _, ancre = href[len(lore.URL_LORE):].partition("#")
			if cle in chapitre_de:
				cible = chapitre_de[cle] + (("#" + ancre) if ancre else "")
				return f'<a href="{html.escape(cible)}">{texte}</a>'
			return texte
		if re.match(r"^https?://", href):
			return f'<a href="{html.escape(href)}">{texte}</a>'
		return texte

	return _RE_LIEN.sub(lien, corps)


def chapitres(pages: list, rendre) -> list:
	"""[{cle, titre, fichier, xhtml}] ; `rendre(entree)` → HTML du corps."""
	chapitre_de = {e["cle"]: f"ch{i:03d}.xhtml" for i, e in enumerate(pages, 1)}
	return [{"cle": e["cle"], "titre": e["titre"], "fichier": chapitre_de[e["cle"]],
			 "xhtml": xhtml(rendre(e), chapitre_de)} for e in pages]


_CSS = """body { font-family: Georgia, serif; line-height: 1.55; margin: 0 4%; }
h1, h2, h3, h4 { font-family: Georgia, serif; color: #6b2a14; line-height: 1.25; }
h1 { font-size: 1.6em; } h2 { font-size: 1.3em; border-bottom: 1px solid #b49a6a; }
blockquote { border-left: 3px solid #b49a6a; margin-left: 0; padding-left: 0.8em; color: #4a3a28; }
table { border-collapse: collapse; font-size: 0.9em; } th, td { border: 1px solid #b49a6a; padding: 3px 6px; vertical-align: top; }
pre { white-space: pre-wrap; font-size: 0.8em; } code { font-family: monospace; }
"""


def _page_xhtml(titre: str, corps: str) -> str:
	return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
			'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="fr" xml:lang="fr">\n'
			f'<head><meta charset="utf-8"/><title>{html.escape(titre)}</title>'
			'<link rel="stylesheet" type="text/css" href="livre.css"/></head>\n'
			f'<body>\n{corps}\n</body>\n</html>\n')


def epub(titre: str, chaps: list, identifiant: str, maintenant: datetime = None) -> bytes:
	"""Octets d'un EPUB 3 (mimetype non compressé en tête, nav + chapitres)."""
	maintenant = maintenant or datetime.now(timezone.utc)
	modifie = maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
	tampon = io.BytesIO()
	with zipfile.ZipFile(tampon, "w") as z:
		z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)

		def ecrire(nom, contenu):
			z.writestr(nom, contenu, compress_type=zipfile.ZIP_DEFLATED)

		ecrire("META-INF/container.xml",
			   '<?xml version="1.0" encoding="utf-8"?>\n'
			   '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
			   '<rootfiles><rootfile full-path="OEBPS/livre.opf" media-type="application/oebps-package+xml"/>'
			   '</rootfiles></container>\n')
		ecrire("OEBPS/livre.css", _CSS)
		items = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
				 '<item id="css" href="livre.css" media-type="text/css"/>']
		spine = []
		for i, c in enumerate(chaps, 1):
			items.append(f'<item id="c{i}" href="{c["fichier"]}" media-type="application/xhtml+xml"/>')
			spine.append(f'<itemref idref="c{i}"/>')
			ecrire("OEBPS/" + c["fichier"], _page_xhtml(c["titre"], c["xhtml"]))
		toc = "".join(f'<li><a href="{c["fichier"]}">{html.escape(c["titre"])}</a></li>' for c in chaps)
		ecrire("OEBPS/nav.xhtml", _page_xhtml(
			titre, f'<nav epub:type="toc" id="toc"><h1>{html.escape(titre)}</h1><ol>{toc}</ol></nav>'))
		ecrire("OEBPS/livre.opf",
			   '<?xml version="1.0" encoding="utf-8"?>\n'
			   '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="fr">'
			   '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
			   f'<dc:identifier id="uid">{html.escape(identifiant)}</dc:identifier>'
			   f'<dc:title>{html.escape(titre)}</dc:title><dc:language>fr</dc:language>'
			   '<dc:creator>Telluris</dc:creator>'
			   f'<meta property="dcterms:modified">{modifie}</meta></metadata>'
			   f'<manifest>{"".join(items)}</manifest><spine>{"".join(spine)}</spine></package>\n')
	return tampon.getvalue()

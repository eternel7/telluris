"""Lecture du lore dans l'administration (pur) : liste blanche des fichiers et rendu Markdown.

Périmètre : `docs/lore/**/*.md` + `docs/Telluris_Document_Maitre.md` (la synthèse canonique).
Le rendu est un convertisseur Markdown stdlib (aucune dépendance pip : en ajouter une
exige de recréer le conteneur) qui couvre ce que le corpus utilise réellement : titres,
`---`, blocs ``` ```, tableaux GFM, citations, listes imbriquées, gras/italique/code/liens.

⚠️ XSS (CLAUDE.md §9) : tout le texte est ÉCHAPPÉ avant que les motifs ne posent leurs
balises — le HTML brut cité dans une séance s'affiche en texte. Seuls `http(s):`, `#` et
les chemins relatifs deviennent des liens ; le reste reste du texte.
"""

import html
import os
import posixpath
import re
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent / "docs"
DOCUMENT_MAITRE = "Telluris_Document_Maitre.md"
URL_LORE = "/admin/lore/"

# Le lore RÉDIGÉ (`docs/lore/redige/`, prose tirée du seul canon) en tête, puis le groupe
# « référence » (Document maître + README) et les dossiers de matière brute, dans cet ordre.
# Un dossier absent d'ici s'affiche quand même, sous son nom capitalisé.
REDIGE = "redige"
REFERENCE = "reference"
SECTIONS = {
	REDIGE: "✒️ Le lore rédigé",
	REFERENCE: "📜 Référence",
	"monde": "🌍 Monde, cosmologie et chronologie",
	"cites": "🏰 Cités-États et lieux",
	"personnages": "🎭 Personnages, scénarios et quêtes",
	"systemes": "⚙️ Systèmes de jeu",
	"contenu": "📦 Contenu de jeu",
}

_RE_DATE_FICHIER = re.compile(r"^(\d{4})(\d{2})(\d{2})_")
_RE_LIGNE_README = re.compile(r"^- \[([^\]]+)\]\(([^)\s]+)\)\s+—\s+[^—]*?\s+—\s+(.*)$")


# ── Liste blanche ──────────────────────────────────────────────────────────────

def _chemins(racine: Path) -> list:
	"""Chemins relatifs (posix) du périmètre, depuis `racine` (= docs/)."""
	out = []
	if (racine / DOCUMENT_MAITRE).is_file():
		out.append(DOCUMENT_MAITRE)
	lore = racine / "lore"
	# `os.walk` et non `rglob` + `is_file()` : le type vient du scandir, sans un stat par
	# fichier (2-3 ms pièce sur un partage réseau, × 6000 appels par validation de la chronologie).
	lieux = []
	for dossier, _sous, fichiers in os.walk(lore):
		rel = Path(dossier).relative_to(racine).as_posix()
		lieux.extend(f"{rel}/{nom}" for nom in fichiers if nom.endswith(".md"))
	out.extend(sorted(lieux))
	return out


def cle_de(chemin: str) -> str:
	"""Clé d'URL d'un chemin du périmètre : relative à docs/lore (le Document maître
	garde son nom, à la racine)."""
	return chemin[len("lore/"):] if chemin.startswith("lore/") else chemin


def section_de(chemin: str) -> str:
	parts = chemin.split("/")
	if len(parts) <= 2:  # Document maître, lore/README.md
		return REFERENCE
	return parts[1]


def libelle_section(section: str) -> str:
	return SECTIONS.get(section) or section.replace("_", " ").capitalize()


def _titre(fichier: Path, defaut: str) -> str:
	with fichier.open(encoding="utf-8") as f:
		for ligne in f:
			m = re.match(r"^#\s+(.+?)\s*#*\s*$", ligne)
			if m:
				return m.group(1).strip()
	return defaut


def _resumes_readme(racine: Path) -> dict:
	"""{chemin: résumé} relus des lignes `- [titre](chemin) — date — résumé` du README."""
	readme = racine / "lore" / "README.md"
	if not readme.is_file():
		return {}
	out = {}
	for ligne in readme.read_text(encoding="utf-8").splitlines():
		m = _RE_LIGNE_README.match(ligne.strip())
		if m:
			cible = posixpath.normpath(posixpath.join("lore", m.group(2)))
			out[cible] = _texte_brut(m.group(3))
	return out


def lister(racine: Path = RACINE) -> list:
	"""Entrées du lore, triées : référence (Document maître en tête), puis SECTIONS, puis
	les dossiers inconnus ; dans une section, par nom de fichier (= par date)."""
	resumes = _resumes_readme(racine)
	ordre = list(SECTIONS)
	entrees = []
	for chemin in _chemins(racine):
		nom = chemin.rsplit("/", 1)[-1]
		m = _RE_DATE_FICHIER.match(nom)
		section = section_de(chemin)
		entrees.append({
			"chemin": chemin,
			"cle": cle_de(chemin),
			"section": section,
			"section_label": libelle_section(section),
			"titre": _titre(racine / chemin, nom[:-3].replace("_", " ")),
			"date": f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else "",
			"resume": resumes.get(chemin, ""),
			"canon": chemin == DOCUMENT_MAITRE,
			"redige": section == REDIGE,
		})

	def cle(e):
		rang = ordre.index(e["section"]) if e["section"] in ordre else len(ordre)
		return (rang, e["section"], not e["canon"], e["chemin"])

	return sorted(entrees, key=cle)


def chemin_de(cle: str, racine: Path = RACINE):
	"""Chemin (relatif à docs/) d'une clé d'URL si elle appartient à la liste blanche,
	sinon None — aucune traversée, aucun fichier hors périmètre."""
	chemins = _chemins(racine)
	for chemin in (cle, "lore/" + cle):
		if chemin in chemins and cle_de(chemin) == cle:
			return chemin
	return None


def grouper(entrees: list) -> list:
	"""[(section, libellé, [entrées])] dans l'ordre de `lister`."""
	out = []
	for e in entrees:
		if not out or out[-1][0] != e["section"]:
			out.append((e["section"], e["section_label"], []))
		out[-1][2].append(e)
	return out


# ── Liens ──────────────────────────────────────────────────────────────────────

def lien_lore(chemin_courant: str):
	"""Résolveur de liens d'un fichier du lore → (href, externe) ou None (texte seul).
	Un `.md` relatif devient sa page `/admin/lore/…` ; un autre relatif reste du texte
	(rien d'autre n'est servi)."""
	dossier = posixpath.dirname(chemin_courant)

	def resoudre_lien(url: str):
		if re.match(r"^https?://", url, re.I):
			return url, True
		if url.startswith("#"):
			return url, False
		if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I) or url.startswith("/"):
			return None
		cible, _, ancre = url.partition("#")
		cible = posixpath.normpath(posixpath.join(dossier, cible))
		if cible.startswith("..") or not cible.endswith(".md"):
			return None
		return URL_LORE + cle_de(cible) + (("#" + ancre) if ancre else ""), False

	return resoudre_lien


def _lien_externe_seul(url: str):
	if re.match(r"^https?://", url, re.I):
		return url, True
	if url.startswith("#"):
		return url, False
	return None


# ── Rendu en ligne ─────────────────────────────────────────────────────────────

_RE_CODE = re.compile(r"(`+)(.+?)\1")
_RE_ECHAP = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|~>])")
_RE_LIEN = re.compile(r"(!?)\[([^\]]*)\]\(<?((?:[^()\s<>]|\([^()\s]*\))+)>?(?:\s+\"[^\"]*\")?\)")
_RE_URL_NUE = re.compile(r"https?://[^\s<>\"]+")
_RE_PLACE = re.compile(r"\x00(\d+)\x00")


def _inline(texte: str, lien_fn) -> str:
	gardes = []

	def garder(h):
		gardes.append(h)
		return f"\x00{len(gardes) - 1}\x00"

	texte = _RE_ECHAP.sub(lambda m: garder(html.escape(m.group(1))), texte)
	texte = _RE_CODE.sub(lambda m: garder(f"<code>{html.escape(m.group(2).strip())}</code>"), texte)

	def lien(m):
		image, libelle, url = m.group(1), m.group(2), m.group(3)
		libelle_html = _inline(libelle, lien_fn) if libelle else html.escape(url)
		if image:
			libelle_html = "🖼 " + (libelle_html or html.escape(url))
		cible = lien_fn(url)
		if not cible:
			return garder(libelle_html)
		href, externe = cible
		attrs = ' target="_blank" rel="noopener noreferrer"' if externe else ""
		return garder(f'<a href="{html.escape(href)}"{attrs}>{libelle_html}</a>')

	texte = _RE_LIEN.sub(lien, texte)

	def url_nue(m):
		url = m.group(0)
		fin = ""
		while url and url[-1] in ".,;:!?)»":
			fin = url[-1] + fin
			url = url[:-1]
		return garder(f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">'
					  f'{html.escape(url)}</a>') + fin

	texte = _RE_URL_NUE.sub(url_nue, texte)
	texte = html.escape(texte, quote=False)
	texte = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", texte)
	texte = re.sub(r"(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)", r"<strong>\1</strong>", texte)
	texte = re.sub(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])", r"<em>\1</em>", texte)
	texte = re.sub(r"(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])", r"<em>\1</em>", texte)
	texte = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", texte)
	while _RE_PLACE.search(texte):  # un libellé de lien peut contenir ses propres gardes
		texte = _RE_PLACE.sub(lambda m: gardes[int(m.group(1))], texte)
	return texte


def _texte_brut(texte: str) -> str:
	"""Texte d'un titre sans balisage (sommaire, slug)."""
	texte = _RE_LIEN.sub(lambda m: m.group(2), texte)
	return re.sub(r"[`*_~]|\\(?=.)", "", texte).strip()


def _slug(texte: str, pris: set) -> str:
	base = unicodedata.normalize("NFKD", texte)
	base = "".join(c for c in base if not unicodedata.combining(c)).lower()
	base = re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "section"
	slug, n = base, 2
	while slug in pris:
		slug, n = f"{base}-{n}", n + 1
	pris.add(slug)
	return slug


# ── Rendu des blocs ────────────────────────────────────────────────────────────

_RE_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_RE_TITRE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_RE_HR = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
_RE_CITATION = re.compile(r"^\s{0,3}>")
_RE_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$")
_RE_SEP_TABLE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _est_table(lignes, i) -> bool:
	return ("|" in lignes[i] and i + 1 < len(lignes)
			and "-" in lignes[i + 1] and bool(_RE_SEP_TABLE.match(lignes[i + 1])))


def _cellules(ligne: str) -> list:
	ligne = ligne.strip()
	if ligne.startswith("|"):
		ligne = ligne[1:]
	if ligne.endswith("|") and not ligne.endswith("\\|"):
		ligne = ligne[:-1]
	return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", ligne)]


def _debut_de_bloc(lignes, i) -> bool:
	ligne = lignes[i]
	return bool(_RE_FENCE.match(ligne) or _RE_TITRE.match(ligne) or _RE_HR.match(ligne)
				or _RE_CITATION.match(ligne) or _RE_ITEM.match(ligne) or _est_table(lignes, i))


class _Etat:
	def __init__(self, lien_fn):
		self.lien_fn = lien_fn
		self.toc = []
		self.slugs = set()


def _indent(ligne: str) -> int:
	return len(ligne.expandtabs(4)) - len(ligne.expandtabs(4).lstrip(" "))


def _liste(lignes, i, etat, out):
	"""Consomme un bloc de liste (imbrications par indentation) à partir de `i`."""
	pile = []  # [(indent, balise)] des listes ouvertes ; chaque niveau a un <li> ouvert
	n = len(lignes)
	while i < n:
		ligne = lignes[i]
		if not ligne.strip():
			j = i + 1
			while j < n and not lignes[j].strip():
				j += 1
			if j < n and (_RE_ITEM.match(lignes[j]) or (_indent(lignes[j]) >= 2 and pile)):
				i = j
				continue
			break
		m = _RE_ITEM.match(ligne)
		if m and not _RE_HR.match(ligne):
			ind = _indent(m.group(1))
			balise = "ol" if m.group(2)[0].isdigit() else "ul"
			while pile and ind < pile[-1][0]:
				out.append(f"</li></{pile.pop()[1]}>")
			if pile and ind < pile[-1][0] + 2:
				if pile[-1][1] == balise:
					out.append("</li><li>")
				else:
					out.append(f"</li></{pile.pop()[1]}>")
					pile.append((ind, balise))
					out.append(_ouvrir_liste(balise, m.group(2)))
			else:
				pile.append((ind, balise))
				out.append(_ouvrir_liste(balise, m.group(2)))
			out.append(_inline(m.group(3), etat.lien_fn))
			i += 1
			continue
		if pile and (_indent(ligne) >= 2 or not _debut_de_bloc(lignes, i)):
			if _RE_FENCE.match(ligne):
				i = _code(lignes, i, out)
				continue
			out.append("<br>" + _inline(ligne.strip(), etat.lien_fn))
			i += 1
			continue
		break
	while pile:
		out.append(f"</li></{pile.pop()[1]}>")
	return i


def _ouvrir_liste(balise: str, marque: str) -> str:
	if balise == "ol":
		debut = int(marque[:-1])
		return "<ol><li>" if debut == 1 else f'<ol start="{debut}"><li>'
	return "<ul><li>"


def _code(lignes, i, out):
	m = _RE_FENCE.match(lignes[i])
	fence = m.group(1)
	corps = []
	i += 1
	while i < len(lignes):
		fin = lignes[i].strip()
		if fin.startswith(fence[0] * len(fence)) and not fin.strip(fence[0]):
			i += 1
			break
		corps.append(lignes[i])
		i += 1
	out.append(f"<pre><code>{html.escape(chr(10).join(corps))}</code></pre>")
	return i


def _blocs(lignes, etat) -> list:
	out = []
	i, n = 0, len(lignes)
	while i < n:
		ligne = lignes[i]
		if not ligne.strip():
			i += 1
			continue
		if _RE_FENCE.match(ligne):
			i = _code(lignes, i, out)
			continue
		m = _RE_TITRE.match(ligne)
		if m:
			niveau = len(m.group(1))
			brut = m.group(2)
			slug = _slug(_texte_brut(brut), etat.slugs)
			etat.toc.append({"niveau": niveau, "id": slug, "texte": _texte_brut(brut)})
			out.append(f'<h{niveau} id="{slug}">{_inline(brut, etat.lien_fn)}</h{niveau}>')
			i += 1
			continue
		if _RE_HR.match(ligne):
			out.append("<hr>")
			i += 1
			continue
		if _est_table(lignes, i):
			entete = _cellules(ligne)
			aligns = []
			for c in _cellules(lignes[i + 1]):
				aligns.append("center" if c.startswith(":") and c.endswith(":")
							  else "right" if c.endswith(":") else "left" if c.startswith(":") else "")
			def cell(balise, texte, k):
				a = aligns[k] if k < len(aligns) else ""
				style = f' style="text-align:{a}"' if a else ""
				return f"<{balise}{style}>{_inline(texte, etat.lien_fn)}</{balise}>"
			out.append('<div class="table-wrap"><table><thead><tr>'
					   + "".join(cell("th", t, k) for k, t in enumerate(entete))
					   + "</tr></thead><tbody>")
			i += 2
			while i < n and lignes[i].strip() and "|" in lignes[i]:
				cells = _cellules(lignes[i])
				cells += [""] * (len(entete) - len(cells))
				out.append("<tr>" + "".join(cell("td", t, k) for k, t in enumerate(cells)) + "</tr>")
				i += 1
			out.append("</tbody></table></div>")
			continue
		if _RE_CITATION.match(ligne):
			corps = []
			while i < n and _RE_CITATION.match(lignes[i]):
				corps.append(re.sub(r"^\s{0,3}> ?", "", lignes[i]))
				i += 1
			out.append("<blockquote>" + "".join(_blocs(corps, etat)) + "</blockquote>")
			continue
		if _RE_ITEM.match(ligne):
			i = _liste(lignes, i, etat, out)
			continue
		para = []
		while i < n and lignes[i].strip() and (not para or not _debut_de_bloc(lignes, i)):
			para.append(_inline(lignes[i].strip(), etat.lien_fn))
			i += 1
		out.append("<p>" + "<br>\n".join(para) + "</p>")
	return out


def rendre(md: str, lien_fn=_lien_externe_seul):
	"""Markdown → (html, sommaire). `sommaire` = [{niveau, id, texte}] des titres."""
	etat = _Etat(lien_fn)
	html_out = "\n".join(_blocs(md.replace("\r\n", "\n").replace("\r", "\n").split("\n"), etat))
	return html_out, etat.toc


def rendre_fichier(chemin: str, racine: Path = RACINE):
	"""(html, sommaire) d'un fichier du périmètre (chemin relatif à docs/, cf. `chemin_de`)."""
	return rendre((racine / chemin).read_text(encoding="utf-8"), lien_lore(chemin))

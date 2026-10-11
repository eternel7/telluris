"""Tests de la lecture du lore dans l'administration (`utils/lore.py`) : rendu Markdown,
échappement (XSS), liste blanche des fichiers servis, fumée sur le vrai corpus."""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import lore  # noqa: E402


def _html(md, lien_fn=None):
	return lore.rendre(md, lien_fn)[0] if lien_fn else lore.rendre(md)[0]


# ── Rendu ──────────────────────────────────────────────────────────────────────

def test_titres_ids_uniques_et_sommaire():
	html, toc = lore.rendre("# Élise\n\n## Auteur\n\n## Auteur\n\n### *Détail*")
	assert '<h1 id="elise">Élise</h1>' in html
	assert '<h2 id="auteur">' in html and '<h2 id="auteur-2">' in html
	assert [t["niveau"] for t in toc] == [1, 2, 2, 3]
	assert toc[3] == {"niveau": 3, "id": "detail", "texte": "Détail"}


def test_mise_en_forme_en_ligne():
	html = _html("**gras** *ital* _ital2_ `code *x*` ~~barré~~")
	assert "<strong>gras</strong>" in html
	assert "<em>ital</em>" in html and "<em>ital2</em>" in html
	assert "<code>code *x*</code>" in html  # rien n'est interprété dans du code
	assert "<del>barré</del>" in html


def test_soulignes_d_un_identifiant_restent_du_texte():
	assert "<em>" not in _html("le doc lieu_categorie_x et rules_races")


def test_paragraphe_garde_ses_retours_a_la_ligne():
	assert "<p>a<br>\nb</p>" in _html("a\nb")


def test_bloc_de_code_echappe_et_brut():
	html = _html("```text\n<b>**x**</b>\n  │ frise\n```\napres")
	assert "<pre><code>&lt;b&gt;**x**&lt;/b&gt;\n  │ frise</code></pre>" in html
	assert "<p>apres</p>" in html


def test_tableau_avec_alignement():
	html = _html("| a | b |\n|:-:|---|\n| **1** | 2 |\n| 3 |")
	assert '<th style="text-align:center">a</th><th>b</th>' in html
	assert '<td style="text-align:center"><strong>1</strong></td><td>2</td>' in html
	assert '<td style="text-align:center">3</td><td></td>' in html  # ligne courte complétée


def test_listes_imbriquees_et_numerotees():
	html = _html("- a\n  - b\n- c\n\n3. x\n   - y\n4. z")
	assert re.sub(r"\s+", "", html) == (
		"<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>"
		'<olstart="3"><li>x<ul><li>y</li></ul></li><li>z</li></ol>')


def test_citation_rendue_recursivement():
	html = _html("> **Note :** texte\n>\n> - point")
	assert html.startswith("<blockquote><p><strong>Note :</strong> texte</p><ul><li>point")
	assert html.endswith("</blockquote>")


def test_separateur():
	assert "<hr>" in _html("a\n\n---\n\nb")


# ── Sécurité ───────────────────────────────────────────────────────────────────

def test_html_brut_du_fichier_affiche_en_texte():
	html = _html('<script>alert(1)</script>\n\n<div class="card-desc">x</div>')
	assert "<script>" not in html and "<div" not in html
	assert "&lt;script&gt;" in html and "&lt;div" in html


def test_liens_dangereux_neutralises():
	html = _html("[x](javascript:alert(1)) [y](data:text/html,1) [z](/etc/passwd)",
				 lore.lien_lore("lore/README.md"))
	assert "<a" not in html
	assert "javascript" not in html


def test_liens_externes_et_url_nue():
	html = _html("[w](https://fr.wikipedia.org/wiki/A_(b)) voir https://ex.com/a_b.")
	assert '<a href="https://fr.wikipedia.org/wiki/A_(b)" target="_blank"' in html
	assert '<a href="https://ex.com/a_b" target="_blank" rel="noopener noreferrer">https://ex.com/a_b</a>.' in html


def test_liens_md_relatifs_reecrits_vers_la_page():
	fn = lore.lien_lore("lore/README.md")
	html = _html("[a](monde/x.md#y) [m](../Telluris_Document_Maitre.md) [s](../SCHEMA.txt) [h](../../main.md)", fn)
	assert '<a href="/admin/lore/monde/x.md#y">a</a>' in html
	assert '<a href="/admin/lore/Telluris_Document_Maitre.md">m</a>' in html
	assert html.count("<a") == 2  # ni un non-.md, ni une sortie de docs/


def test_liste_blanche():
	assert lore.chemin_de("Telluris_Document_Maitre.md") == "Telluris_Document_Maitre.md"
	assert lore.chemin_de("README.md") == "lore/README.md"
	for refuse in ("../SCHEMA.md", "SCHEMA.md", "competences_vocations_1_10.md",
				   "lore/README.md", "../../main.py", "monde/../../SCHEMA.md", ""):
		assert lore.chemin_de(refuse) is None, refuse


# ── Vrai corpus ────────────────────────────────────────────────────────────────

def test_corpus_complet_rendu_et_liste():
	entrees = lore.lister()
	sur_disque = {p.relative_to(lore.RACINE).as_posix() for p in (lore.RACINE / "lore").rglob("*.md")}
	assert {e["chemin"] for e in entrees} == sur_disque | {lore.DOCUMENT_MAITRE}
	assert entrees[0]["chemin"] == lore.DOCUMENT_MAITRE and entrees[0]["canon"]
	for e in entrees:
		assert lore.chemin_de(e["cle"]) == e["chemin"]
		html, _ = lore.rendre_fichier(e["chemin"])
		assert html and "<script" not in html, e["chemin"]


def test_liens_du_readme_menent_a_des_pages_existantes():
	html, _ = lore.rendre_fichier("lore/README.md")
	cles = re.findall(r'href="/admin/lore/([^"#]+)', html)
	assert cles
	for cle in cles:
		assert lore.chemin_de(cle), cle


def test_resumes_relus_du_readme():
	avec_resume = [e for e in lore.lister() if e["resume"]]
	assert avec_resume  # le README en porte ; chaque résumé appartient à un fichier listé
	assert all(e["section"] != lore.REFERENCE for e in avec_resume)

"""Barre de défilement UNIQUE (`templates/part-defilement.html`) : chaque page l'inclut dans son
<head>, aucune n'en redéfinit une autre — seul `scrollbar-width: none` (barre masquée) reste permis."""

import glob
import os
import re

RACINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
PART = "part-defilement.html"


def _pages():
	for chemin in sorted(glob.glob(os.path.join(RACINE, "*.html"))):
		nom = os.path.basename(chemin)
		if nom.startswith("part-"):
			continue
		with open(chemin, encoding="utf-8") as f:
			texte = f.read()
		if "</head>" in texte:
			yield nom, texte


def test_chaque_page_inclut_la_barre_de_defilement_commune():
	pages = list(_pages())
	assert pages
	sans = [nom for nom, texte in pages
			if f'{{% include "{PART}" %}}' not in texte[:texte.index("</head>")]]
	assert sans == []


def test_aucune_page_ne_redefinit_sa_barre():
	interdit = re.compile(r"scrollbar-color|::-webkit-scrollbar|scrollbar-width:\s*(thin|auto)")
	fautifs = [(nom, m.group(0)) for nom, texte in _pages() for m in interdit.finditer(texte)]
	assert fautifs == []

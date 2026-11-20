"""Outils de parcours du lore (utils/lore_outils.py) et livre (utils/lore_livre.py).

Les cas de logique tournent sur un mini-corpus écrit dans `tmp_path` ; la cohérence des deux
JSON écrits à la main (entités, parcours) est vérifiée contre le VRAI corpus (`lent`).
"""

import io
import json
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime, timezone

import pytest

from utils import lore, lore_livre, lore_outils as lo


@pytest.fixture(autouse=True)
def _cache_vide():
	lo.vider_cache()
	yield
	lo.vider_cache()


def _corpus(tmp_path, entites=None, parcours=None):
	docs = tmp_path / "docs"
	(docs / "lore" / "cites").mkdir(parents=True)
	(docs / "lore" / "redige").mkdir(parents=True)
	(docs / "lore" / "cites" / "20261001_rome.md").write_text(
		"# Rome\n\nRome garde Saint-Pierre. Les Templiers veillent. Rome encore.\n\n"
		"## ✍️ Auteur\n\nUn portail naturel, pas un portail des frères.\n", encoding="utf-8")
	(docs / "lore" / "redige" / "01_monde.md").write_text(
		"# Le monde\n\nDe Rome à Lutecia, les Templiers et les Paladins. Élise attend.\n", encoding="utf-8")
	(docs / "lore" / "entites.json").write_text(json.dumps(entites or {
		"types": {"cite": "Cités", "institution": "Institutions", "figure": "Figures"},
		"entites": [
			{"id": "rome", "nom": "Rome", "type": "cite", "page": "cites/20261001_rome.md",
			 "resume": "La pieuse <et> la pécheresse.", "image": "towns/rome.png", "lat": 41.9, "lon": 12.5},
			{"id": "lutecia", "nom": "Lutecia", "variantes": ["Lutèce"], "type": "cite", "lat": 48.86, "lon": 2.35},
			{"id": "templiers", "nom": "Templiers", "type": "institution", "page": "redige/01_monde.md"},
			{"id": "mu", "nom": "Mu", "type": "cite"},
		],
		"portails": [["rome", "lutecia"], ["rome", "inconnue"]],
	}), encoding="utf-8")
	(docs / "lore" / "parcours.json").write_text(json.dumps(parcours or {
		"titre": "Découvrir", "etapes": [
			{"cle": "redige/01_monde.md", "pourquoi": "Le cadre."},
			{"cle": "absente.md", "pourquoi": "écartée"},
			{"cle": "cites/20261001_rome.md", "pourquoi": "Rome."}]}), encoding="utf-8")
	return docs


def test_recherche_plein_texte_sans_casse_ni_accents(tmp_path):
	docs = _corpus(tmp_path)
	entrees = lore.lister(docs)
	r = lo.rechercher("PORTAIL naturel", entrees, docs)
	assert [x["cle"] for x in r] == ["cites/20261001_rome.md"]
	assert "<mark>portail naturel</mark>" in r[0]["extrait"]  # la phrase entière d'abord
	assert [x["cle"] for x in lo.rechercher("elise", entrees, docs)] == ["redige/01_monde.md"]
	assert lo.rechercher("rome templiers", entrees, docs)[0]["cle"] == "cites/20261001_rome.md"  # le plus cité
	assert lo.rechercher("   ", entrees, docs) == []
	assert lo.rechercher("introuvable", entrees, docs) == []


def test_extrait_echappe_le_texte(tmp_path):
	texte = "avant <script> cible après"
	assert lo.extrait(texte, lo.plier(texte), "cible") == "avant &lt;script&gt; <mark>cible</mark> après"


def test_plier_garde_les_indices():
	for s in ("Élise à Lutèce", "Œuvre ﬁne", "Hārūt et Mārūt"):
		assert len(lo.plier(s)) == len(s)
	assert lo.plier("Élise à Lutèce") == "elise a lutece"


def test_duree_au_moins_une_minute():
	assert lo.duree_minutes(0) == 1
	assert lo.duree_minutes(lo.MOTS_PAR_MINUTE * 3) == 3


def test_entites_mots_entiers_et_casse(tmp_path):
	docs = _corpus(tmp_path)
	d = lo.charger_entites(docs)
	compte = lo.entites_citees("Mu, le mur de Rome-la-Neuve ; Lutèce, Rome.", d)
	assert compte == Counter({"mu": 1, "lutecia": 1, "rome": 1})  # ni « mur », ni « Rome » collé d'un tiret


def test_lier_entites_premiere_mention_hors_titres_et_liens(tmp_path):
	docs = _corpus(tmp_path)
	d = lo.charger_entites(docs)
	corps = ('<h1 id="x">Rome</h1>\n<p>Rome et <a href="#y">Lutecia</a>, puis Lutecia et Rome. '
			 'Les Templiers.</p><pre><code>Mu</code></pre>')
	out = lo.lier_entites(corps, d, "redige/01_monde.md")
	assert out.count('data-entite="rome"') == 1 and out.count('data-entite="lutecia"') == 1
	assert '<h1 id="x">Rome</h1>' in out                   # titre intact
	assert '<a href="#y">Lutecia</a>' in out               # pas de lien dans un lien
	assert 'data-entite="templiers"' not in out             # sa page est la page lue
	assert 'data-entite="mu"' not in out                    # pas dans le code
	assert "La pieuse &lt;et&gt; la pécheresse." in out     # résumé échappé en attribut
	assert 'href="/admin/lore/encyclopedie#e-lutecia"' in out  # sans page : l'encyclopédie


def test_themes_seuils(tmp_path):
	docs = _corpus(tmp_path)
	d = lo.charger_entites(docs)
	assert lo.themes_de(Counter({"rome": 5, "templiers": 1}), d) == ["cite"]
	assert lo.themes_de(Counter({"rome": 2}), d) == []  # sous THEME_MENTIONS_MIN
	assert lo.themes_de(Counter({"rome": 4, "templiers": 4}), d) == ["cite", "institution"]


def test_illustrations(tmp_path):
	docs = _corpus(tmp_path)
	d = lo.charger_entites(docs)
	assert lo.illustrations(Counter({"rome": 1}), d) == []
	assert [e["id"] for e in lo.illustrations(Counter({"rome": 2}), d)] == ["rome"]
	assert [e["id"] for e in lo.illustrations(Counter({"rome": 1}), d, cle_courante="cites/20261001_rome.md")] == ["rome"]


def test_enrichir_parcours_et_nouveautes(tmp_path):
	docs = _corpus(tmp_path)
	entrees = lo.enrichir(lore.lister(docs), docs)
	assert all(e["minutes"] >= 1 and e["mtime"] > 0 for e in entrees)
	p = lo.parcours(entrees, docs)
	assert [et["cle"] for et in p["etapes"]] == ["redige/01_monde.md", "cites/20261001_rome.md"]
	pos = lo.position_parcours(p, "cites/20261001_rome.md")
	assert pos["index"] == 2 and pos["total"] == 2 and pos["suivante"] is None
	assert lo.position_parcours(p, "inconnue.md") is None
	assert {e["cle"] for e in lo.quoi_de_neuf(entrees)} == {e["cle"] for e in entrees}


def test_encyclopedie_et_carte(tmp_path):
	docs = _corpus(tmp_path)
	enc = lo.encyclopedie(lore.lister(docs), docs)
	cites = dict((t, l) for t, _, l in enc)["cite"]
	rome = next(e for e in cites if e["id"] == "rome")
	assert rome["mentions"][0]["cle"] == "cites/20261001_rome.md" and rome["nb_pages"] == 2
	c = lo.carte(docs)
	assert {x["id"] for x in c["cites"]} == {"rome", "lutecia"}   # Mu n'a pas de coordonnées
	assert len(c["liens"]) == 1                                     # lien vers une cité inconnue écarté
	x, y = lo.projeter(48.86, 2.35)
	assert 0 <= x <= 100 and 0 <= y <= 100


def test_livre_xhtml_et_epub(tmp_path):
	docs = _corpus(tmp_path)
	entrees = lore.lister(docs)
	pages = lore_livre.selection("redige", entrees, {})
	assert [e["cle"] for e in pages] == ["redige/01_monde.md"]
	corps = '<p>a<br>b</p><hr><p><a href="/admin/lore/redige/01_monde.md#t">ici</a> <a href="/admin/lore/autre.md">là</a></p>'
	x = lore_livre.xhtml(corps, {"redige/01_monde.md": "ch001.xhtml"})
	assert "<br/>" in x and "<hr/>" in x and 'href="ch001.xhtml#t"' in x and ">là<" not in x and " là" in x
	chaps = lore_livre.chapitres(pages, lambda e: lore.rendre_fichier(e["chemin"], docs)[0])
	data = lore_livre.epub("Titre & co", chaps, "urn:test", datetime(2026, 11, 20, tzinfo=timezone.utc))
	z = zipfile.ZipFile(io.BytesIO(data))
	assert z.namelist()[0] == "mimetype" and z.read("mimetype") == b"application/epub+zip"
	assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
	for nom in z.namelist():
		if nom.endswith((".xhtml", ".opf", ".xml")):
			ET.fromstring(z.read(nom))  # XML bien formé
	assert lore_livre.nom_fichier("../x y") == "telluris_lore_x_y.epub"


@pytest.mark.lent
def test_vrai_corpus_entites_parcours_et_epub():
	"""entites.json et parcours.json, écrits à la main, pointent sur des pages existantes ;
	toute page du vrai lore donne un chapitre d'EPUB bien formé."""
	entrees = lore.lister()
	cles = {e["cle"] for e in entrees}
	data = json.loads((lore.RACINE / lo.FICHIER_ENTITES).read_text(encoding="utf-8"))
	ids = [e["id"] for e in data["entites"]]
	assert len(ids) == len(set(ids)), "id d'entité en double"
	for e in data["entites"]:
		assert e["type"] in data["types"], e["id"]
		assert not e.get("page") or e["page"] in cles, (e["id"], e.get("page"))
		if e.get("image"):
			dossier, _, nom = e["image"].partition("/")
			assert (lore.RACINE.parent / "templates" / "resources" / dossier / nom).is_file(), e["image"]
	for a, b in data["portails"]:
		assert a in ids and b in ids, (a, b)
	parcours = json.loads((lore.RACINE / lo.FICHIER_PARCOURS).read_text(encoding="utf-8"))
	for et in parcours["etapes"]:
		assert et["cle"] in cles, et["cle"]
	chaps = lore_livre.chapitres(entrees, lambda e: lore.rendre_fichier(e["chemin"])[0])
	for c in chaps:
		ET.fromstring(lore_livre._page_xhtml(c["titre"], c["xhtml"]).split("\n", 2)[2])


def test_gras_italique_bien_imbriques():
	"""`***x***` donnait `<strong><em>x</strong></em>` : XHTML de l'EPUB mal formé."""
	assert "<strong><em>upir</em></strong>" in lore.rendre("le nom d'***upir***, puis **gras** et *it*")[0]

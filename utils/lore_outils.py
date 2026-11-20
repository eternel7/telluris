"""Outils de parcours du lore (pur) : recherche plein texte, durée de lecture, entités
(liens croisés, thèmes, illustrations, encyclopédie, carte), parcours guidé, « quoi de neuf ».

Sources : `docs/lore/entites.json` et `docs/lore/parcours.json`, ÉCRITS À LA MAIN (Auteur,
20/11/2026) ; le texte des pages vient du rendu de `utils/lore.py`. Rien n'est lu en base.

Cache de PROCESS par mtime (fichier .md ou JSON) : un `git pull` est suivi sans redémarrage.

⚠️ XSS (CLAUDE.md §9) : `lier_entites` n'opère que sur les segments de TEXTE du HTML déjà
échappé par `lore.rendre` ; les noms et résumés posés en attribut sont échappés ici.
"""

import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from utils import lore

FICHIER_ENTITES = "lore/entites.json"
FICHIER_PARCOURS = "lore/parcours.json"
MOTS_PAR_MINUTE = 230  # vitesse de lecture silencieuse courante d'un adulte (français)
LONGUEUR_EXTRAIT = 90   # caractères de contexte de part et d'autre d'un résultat

# Carte du monde de /admin/lore/carte : `templates/resources/maps/world.png` (1408 × 768),
# peinte, proche d'une projection équirectangulaire. Constantes CALIBRÉES à l'œil sur
# Paris (690, 190) et Sydney (1225, 555), vérifiées sur Tokyo, Teotihuacan et Le Caire.
CARTE_IMAGE = "world.png"
CARTE_L, CARTE_H = 1408, 768
CARTE_X0, CARTE_KX = 682.0, 3.6     # x = X0 + KX × longitude
CARTE_Y0, CARTE_KY = 405.6, -4.41   # y = Y0 + KY × latitude

_cache = {}


def _lire_cache(chemin: Path, calcul):
	"""Valeur de `calcul(chemin)` mémorisée tant que le mtime du fichier ne change pas."""
	try:
		mtime = chemin.stat().st_mtime_ns
	except OSError:
		return None
	cle = (str(chemin), calcul.__name__)
	trouve = _cache.get(cle)
	if trouve and trouve[0] == mtime:
		return trouve[1]
	valeur = calcul(chemin)
	_cache[cle] = (mtime, valeur)
	return valeur


def vider_cache():
	_cache.clear()


# ── Texte des pages ────────────────────────────────────────────────────────────

_RE_BLOC = re.compile(r"</?(?:p|li|h[1-6]|td|th|tr|br|div|blockquote|pre|ul|ol|table|thead|tbody|hr)\b[^>]*>", re.I)
_RE_BALISE = re.compile(r"<[^>]+>")  # balises EN LIGNE (strong, em, a, code…) : ôtées sans espace


def rendu_et_texte(chemin_rel: str, racine: Path = lore.RACINE):
	"""(html, sommaire, texte brut) d'un fichier du périmètre, mémorisés par mtime."""
	fichier = racine / chemin_rel

	def calcul(_f):
		corps, toc = lore.rendre_fichier(chemin_rel, racine)
		texte = html.unescape(_RE_BALISE.sub("", _RE_BLOC.sub(" ", corps)))
		return corps, toc, re.sub(r"\s+", " ", texte).strip()

	calcul.__name__ = "rendu"
	return _lire_cache(fichier, calcul)


def nb_mots(texte: str) -> int:
	return len(re.findall(r"\w+", texte or ""))


def duree_minutes(mots: int) -> int:
	"""Minutes de lecture estimées, au moins une."""
	return max(1, round(mots / MOTS_PAR_MINUTE))


def _plier_car(c: str) -> str:
	"""Un caractère sans accent ni casse, TOUJOURS un seul caractère (les indices du
	texte plié restent ceux du texte d'origine, pour l'extrait)."""
	base = "".join(x for x in unicodedata.normalize("NFKD", c) if not unicodedata.combining(x)).lower()
	return base if len(base) == 1 else c.lower()


def plier(texte: str) -> str:
	return "".join(_plier_car(c) for c in texte)


def termes(requete: str) -> list:
	return [t for t in plier(requete or "").split() if t]


def extrait(texte: str, plie: str, terme: str) -> str:
	"""HTML échappé : contexte autour de la 1re occurrence de `terme`, surlignée."""
	i = plie.find(terme)
	if i < 0:
		return ""
	debut = max(0, i - LONGUEUR_EXTRAIT)
	fin = min(len(texte), i + len(terme) + LONGUEUR_EXTRAIT)
	avant = ("… " if debut else "") + texte[debut:i]
	apres = texte[i + len(terme):fin] + (" …" if fin < len(texte) else "")
	return html.escape(avant) + "<mark>" + html.escape(texte[i:i + len(terme)]) + "</mark>" + html.escape(apres)


def rechercher(requete: str, entrees: list, racine: Path = lore.RACINE, limite: int = 200) -> list:
	"""Recherche PLEIN TEXTE (titre, résumé et corps), sans casse ni accents : tous les
	termes doivent figurer dans le fichier. [{cle, nb, extrait}] du plus au moins cité."""
	mots = termes(requete)
	if not mots:
		return []
	out = []
	for e in entrees:
		rendu = rendu_et_texte(e["chemin"], racine)
		if not rendu:
			continue
		texte = f"{e['titre']} · {e.get('resume', '')} · {rendu[2]}"
		plie = plier(texte)
		if not all(m in plie for m in mots):
			continue
		nb = sum(plie.count(m) for m in mots)
		# Extrait pris dans le CORPS de préférence (le titre est déjà affiché).
		corps = rendu[2]
		corps_plie = plier(corps)
		phrase = " ".join(mots)
		ext = (extrait(corps, corps_plie, phrase) or extrait(corps, corps_plie, mots[0])
			   or extrait(texte, plie, mots[0]))
		out.append({"cle": e["cle"], "nb": nb, "extrait": ext})
	out.sort(key=lambda r: -r["nb"])
	return out[:limite]


# ── Entités ────────────────────────────────────────────────────────────────────

def _charger_entites(fichier: Path):
	data = json.loads(fichier.read_text(encoding="utf-8"))
	entites = data.get("entites", [])
	return {
		"types": data.get("types", {}),
		"entites": entites,
		"par_id": {e["id"]: e for e in entites},
		"portails": data.get("portails", []),
		"motif": _motif(entites),
	}


_charger_entites.__name__ = "entites"


def charger_entites(racine: Path = lore.RACINE) -> dict:
	vide = {"types": {}, "entites": [], "par_id": {}, "portails": [], "motif": None}
	return _lire_cache(racine / FICHIER_ENTITES, _charger_entites) or vide


def _motif(entites: list):
	"""(regex, {variante: id}) : toutes les variantes, les plus longues d'abord, en mots
	entiers SENSIBLES À LA CASSE (« Mu » ne prend pas « mur »)."""
	carte = {}
	for e in entites:
		for v in [e["nom"]] + list(e.get("variantes", [])):
			carte.setdefault(v, e["id"])
	if not carte:
		return None
	alternatives = "|".join(re.escape(v) for v in sorted(carte, key=len, reverse=True))
	return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])"), carte


def entites_citees(texte: str, donnees: dict) -> Counter:
	"""{id: nombre de mentions} dans un texte brut."""
	motif = donnees.get("motif")
	if not motif or not texte:
		return Counter()
	rx, carte = motif
	return Counter(carte[m.group(0)] for m in rx.finditer(texte))


def url_entite(e: dict) -> str:
	return lore.URL_LORE + e["page"] if e.get("page") else lore.URL_LORE + "encyclopedie#e-" + e["id"]


_RE_JETON_HTML = re.compile(r"(<[^>]+>)")
_INTERDITS = {"a", "code", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "mark"}


def lier_entites(corps: str, donnees: dict, cle_courante: str) -> str:
	"""Pose un lien sur la PREMIÈRE mention de chaque entité dans le texte (hors liens,
	code, titres), vers sa page principale (l'encyclopédie à défaut), avec son résumé en
	infobulle. Une entité dont la page est la page lue n'est pas liée."""
	motif = donnees.get("motif")
	if not motif:
		return corps
	rx, carte = motif
	par_id = donnees["par_id"]
	vus = set()
	pile = []
	out = []

	def remplacer(m):
		e = par_id[carte[m.group(0)]]
		if e["id"] in vus or e.get("page") == cle_courante:
			return m.group(0)
		vus.add(e["id"])
		titre = html.escape(f"{e['nom']} — {e.get('resume', '')}")
		return (f'<a class="entite" href="{html.escape(url_entite(e))}" title="{titre}" '
				f'data-entite="{html.escape(e["id"])}">{m.group(0)}</a>')

	for jeton in _RE_JETON_HTML.split(corps):
		if jeton.startswith("<"):
			m = re.match(r"<(/?)([a-zA-Z0-9]+)", jeton)
			if m and m.group(2).lower() in _INTERDITS:
				if m.group(1):
					if pile:
						pile.pop()
				elif not jeton.endswith("/>"):
					pile.append(m.group(2).lower())
			out.append(jeton)
		elif pile or not jeton.strip():
			out.append(jeton)
		else:
			out.append(rx.sub(remplacer, jeton))
	return "".join(out)


THEME_PART_MIN = 0.2   # part des mentions du fichier qu'un type doit peser pour devenir son thème
THEME_MENTIONS_MIN = 3  # … et nombre minimal de mentions (une page courte ne prend pas tout)


def themes_de(compte: Counter, donnees: dict) -> list:
	"""Thèmes d'un fichier (filtres de l'index) : les types d'entités qui pèsent au moins
	THEME_PART_MIN de ses mentions et THEME_MENTIONS_MIN mentions — presque toutes les pages
	nomment une cité ou une institution au passage, ce qui rendrait le filtre inutile."""
	par_type = Counter()
	for i, nb in compte.items():
		e = donnees["par_id"].get(i)
		if e:
			par_type[e["type"]] += nb
	total = sum(par_type.values())
	return [t for t in donnees.get("types", {})
			if par_type[t] >= THEME_MENTIONS_MIN and par_type[t] >= THEME_PART_MIN * total]


def illustrations(compte: Counter, donnees: dict, n: int = 3, cle_courante: str = "") -> list:
	"""Jusqu'à `n` entités illustrées les plus citées par la page (≥ 2 mentions, ou la
	page principale de l'entité), pour le bandeau d'images."""
	par_id = donnees["par_id"]
	candidats = []
	for i, nb in compte.items():
		e = par_id.get(i)
		if not e or not e.get("image"):
			continue
		principal = e.get("page") == cle_courante
		if nb >= 2 or principal:
			candidats.append((not principal, -nb, e["nom"], e))
	candidats.sort(key=lambda c: c[:3])
	return [c[3] for c in candidats[:n]]


# ── Métadonnées de l'index ─────────────────────────────────────────────────────

def enrichir(entrees: list, racine: Path = lore.RACINE) -> list:
	"""Copies des entrées + `mtime` (s), `minutes` de lecture, `themes` (types d'entités)."""
	donnees = charger_entites(racine)
	out = []
	for e in entrees:
		e = dict(e)
		rendu = rendu_et_texte(e["chemin"], racine)
		texte = rendu[2] if rendu else ""
		try:
			e["mtime"] = int((racine / e["chemin"]).stat().st_mtime)
		except OSError:
			e["mtime"] = 0
		e["minutes"] = duree_minutes(nb_mots(texte))
		e["themes"] = themes_de(entites_citees(texte, donnees), donnees)
		out.append(e)
	return out


def _date_iso(e: dict) -> str:
	j, m, a = (e.get("date") or "//").split("/") if e.get("date") else ("", "", "")
	return f"{a}{m}{j}"


def quoi_de_neuf(entrees: list, n: int = 8) -> list:
	"""Les `n` fichiers les plus récents : jour de modification d'abord (un `git pull` ne
	touche que les fichiers changés), puis date du nom (un clone neuf a tous ses mtime égaux)."""
	recents = [e for e in entrees if e.get("section") != lore.REFERENCE]  # README, Document maître : hors fil
	return sorted(recents, key=lambda e: (e.get("mtime", 0) // 86400, _date_iso(e)), reverse=True)[:n]


# ── Parcours guidé ─────────────────────────────────────────────────────────────

def _charger_parcours(fichier: Path):
	return json.loads(fichier.read_text(encoding="utf-8"))


_charger_parcours.__name__ = "parcours"


def parcours(entrees: list, racine: Path = lore.RACINE) -> dict:
	"""{titre, etapes: [{cle, titre, pourquoi, minutes?}]} — étapes inconnues écartées."""
	data = _lire_cache(racine / FICHIER_PARCOURS, _charger_parcours) or {}
	par_cle = {e["cle"]: e for e in entrees}
	etapes = []
	for et in data.get("etapes", []):
		e = par_cle.get(et.get("cle"))
		if e:
			etapes.append({"cle": e["cle"], "titre": e["titre"], "pourquoi": et.get("pourquoi", ""),
						   "minutes": e.get("minutes")})
	return {"titre": data.get("titre", "Parcours"), "etapes": etapes}


def position_parcours(p: dict, cle: str):
	"""(index, précédente, suivante) de `cle` dans le parcours, ou None."""
	cles = [et["cle"] for et in p["etapes"]]
	if cle not in cles:
		return None
	i = cles.index(cle)
	return {"index": i + 1, "total": len(cles),
			"precedente": p["etapes"][i - 1] if i > 0 else None,
			"suivante": p["etapes"][i + 1] if i + 1 < len(cles) else None}


# ── Encyclopédie et carte ──────────────────────────────────────────────────────

def encyclopedie(entrees: list, racine: Path = lore.RACINE, max_mentions: int = 12) -> list:
	"""[(type, libellé, [entité + mentions])] : par type, entités par nom ; `mentions` =
	[{cle, titre, nb}] des pages qui la citent, de la plus à la moins bavarde."""
	donnees = charger_entites(racine)
	mentions = {e["id"]: [] for e in donnees["entites"]}
	for e in entrees:
		rendu = rendu_et_texte(e["chemin"], racine)
		if not rendu:
			continue
		for i, nb in entites_citees(rendu[2], donnees).items():
			mentions[i].append({"cle": e["cle"], "titre": e["titre"], "nb": nb})
	out = []
	for t, libelle in donnees["types"].items():
		liste = []
		for e in sorted((x for x in donnees["entites"] if x["type"] == t), key=lambda x: plier(x["nom"])):
			m = sorted(mentions[e["id"]], key=lambda x: -x["nb"])
			liste.append({**e, "url": url_entite(e), "mentions": m[:max_mentions], "nb_pages": len(m)})
		if liste:
			out.append((t, libelle, liste))
	return out


def projeter(lat: float, lon: float) -> tuple:
	"""(x %, y %) d'un point sur la carte du monde (cf. constantes CARTE_*)."""
	x = (CARTE_X0 + CARTE_KX * lon) / CARTE_L * 100
	y = (CARTE_Y0 + CARTE_KY * lat) / CARTE_H * 100
	return round(min(100, max(0, x)), 2), round(min(100, max(0, y)), 2)


def carte(racine: Path = lore.RACINE) -> dict:
	"""{cites: [{id, nom, x, y, url, resume, image}], liens: [[xa, ya, xb, yb, ida, idb]]}."""
	donnees = charger_entites(racine)
	cites = {}
	for e in donnees["entites"]:
		if e["type"] == "cite" and "lat" in e and "lon" in e:
			# `carte` [x %, y %] corrige un point que la carte PEINTE déforme (côtes déplacées).
			x, y = e["carte"] if e.get("carte") else projeter(e["lat"], e["lon"])
			cites[e["id"]] = {"id": e["id"], "nom": e["nom"], "x": x, "y": y, "url": url_entite(e),
							  "resume": e.get("resume", ""), "image": e.get("image", "")}
	liens = []
	for a, b in donnees["portails"]:
		if a in cites and b in cites:
			liens.append([cites[a]["x"], cites[a]["y"], cites[b]["x"], cites[b]["y"], a, b])
	for c in cites.values():
		c["portails"] = sum(1 for l in liens if c["id"] in l[4:])
	return {"image": CARTE_IMAGE, "cites": list(cites.values()), "liens": liens}

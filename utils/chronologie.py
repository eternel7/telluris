"""Chronologie du lore (pur) : source `docs/lore/chronologie.json`, validation, payload de la
frise SVG de `/admin/lore/chronologie`.

Modèle de temps — aucune date terrestre :
- des ÈRES dans l'ordre de l'axe ; `ordinal` (repérée par rangs : l'antédiluvien, l'Âge des
  Remparts, le temps du joueur), `passe` (« ans avant l'ère actuelle », décroissant) ou `futur` (« dans N ans ») ;
- une BORNE = `{"ere": …}` + UNE clé parmi `ans` · `entre` [plus_ancien, plus_recent] ·
  `dans` · `entre_dans` [plus_proche, plus_lointain] · `rang` · `entre_rangs` [premier, dernier]
  · `inconnu` · `ouvert` ;
- un `quand` = `{"moment": borne}` ou `{"de": borne, "a": borne}`.

Le serveur réduit chaque borne à un intervalle de TEMPS NORMALISÉ `t` = indice de l'ère +
fraction dans l'ère (0 → 1, dans le sens de l'axe). `t` est continu d'une ère numérique à
l'autre (750 ans = fin de l'Âge des Portails = début de l'Âge des Donjons) et ne dépend
d'aucun zoom : le client ne fait que projeter `t` en pixels (`chronoEchelle`), il ne
recalcule jamais une date — une seule vérité, ici.

Vue en FLEUVES (affiches « Time Chart ») :
- une ENTITÉ (`entites`, cité ou ordre) = un fleuve coloré ; sa vie vient de son `evenement`
  (la cité déjà datée) ou de son propre `quand` ; `largeur` = paliers 1 → 3 (établissement mince,
  avènement large), chacun `depuis` une borne ; `issu_de` / `absorbe_par` = branches ;
- un événement se RATTACHE à un fleuve par ses tags (`rattache`, facettes `ORDRE_RATTACHE`,
  valeurs dans l'ordre de l'événement) pourvu que le fleuve vive à ce moment — sinon colonne
  « Telluris entier » ; les autres fleuves touchés deviennent des `echos` ;
- un fleuve « jusqu'à aujourd'hui » se prolonge à travers le temps du joueur (jusqu'au futur) ;
- `bandeaux` = grands événements qui barrent toutes les colonnes ; ères `carte`, entités et
  événements `image` = cartouches et médaillons (vignettes : `dev/gen_vignettes_chronologie.py`).
"""

import json
import re
from pathlib import Path

from utils import lore

CHEMIN = lore.RACINE / "lore" / "chronologie.json"
# Images des cartouches et médaillons : préfixe = mount statique de main.py.
RESSOURCES = Path(__file__).resolve().parent.parent / "templates" / "resources"
PREFIXES_IMAGE = ("maps", "towns", "pnj")
DOSSIER_VIGNETTES = RESSOURCES / "icons" / "chronologie"
URL_VIGNETTES = "/icons/chronologie/"
FAMILLES = {"ordre": "Ordre", "cite": "Cité"}
ORDRE_RATTACHE = ("lieux", "peuples", "institutions", "origine")
LARGEURS = (1, 2, 3)
_COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")

COUCHES = {"histoire": "Histoire", "present": "Présent du monde", "trame": "Trame du joueur"}
AUTORITES = {"auteur": "Auteur", "synthese": "Synthèse", "proposition": "Proposition"}
CATEGORIES = {
	"evenement": "Événement", "figure": "Figure", "cite": "Cité", "institution": "Institution",
	"portail": "Portail", "mythe": "Mythe", "quete": "Quête",
}
VISIBILITES = {"public": "Public", "secret": "Secret", "meta": "Vérité méta"}
TYPES_ERE = ("ordinal", "passe", "futur")
FACETTES_TAGS = ("peuples", "lieux", "institutions", "themes")
# Une borne porte `ere` + exactement UNE de ces clés.
CLES_BORNE = ("ans", "entre", "dans", "entre_dans", "rang", "entre_rangs", "inconnu", "ouvert")
_CLES_PAR_TYPE = {
	"ordinal": {"rang", "entre_rangs", "inconnu", "ouvert"},
	"passe": {"ans", "entre", "inconnu", "ouvert"},
	"futur": {"dans", "entre_dans", "inconnu", "ouvert"},
}
_EPS = 1e-9


def charger(chemin: Path = CHEMIN) -> dict:
	with Path(chemin).open(encoding="utf-8") as f:
		return json.load(f)


def _nombre(n) -> str:
	"""3000 → « 3 000 » (espace fine insécable)."""
	return f"{int(n):,}".replace(",", " ")


def _est_nombre(x) -> bool:
	return isinstance(x, (int, float)) and not isinstance(x, bool)


class _Eres:
	"""Index des ères déclarées : position sur l'axe, rangs, plages numériques."""

	def __init__(self, eres: list):
		self.liste = [e for e in (eres or []) if isinstance(e, dict) and e.get("id")]
		self.par_id = {e["id"]: (i, e) for i, e in enumerate(self.liste)}

	def rangs(self, ere: dict) -> list:
		return [r.get("id") for r in ere.get("rangs") or []]

	def _numerique(self, typ: str, valeur):
		"""(indice, ère) de l'ère `typ` qui contient la valeur, ou None."""
		for i, e in enumerate(self.liste):
			if e.get("type") != typ:
				continue
			lo, hi = sorted((e.get("debut", 0), e.get("fin", 0)))
			if lo - _EPS <= valeur <= hi + _EPS:
				return i, e
		return None

	def t_numerique(self, typ: str, valeur):
		trouve = self._numerique(typ, valeur)
		if trouve is None:
			return None
		i, e = trouve
		debut, fin = e["debut"], e["fin"]
		return i + (valeur - debut) / (fin - debut) if fin != debut else float(i)


def intervalle(borne, eres: _Eres, role: str = None):
	"""(tmin, tmax, genre) d'une borne, ou lève ValueError. `genre` ∈ exact · incertain ·
	rang · inconnu · ouvert. `role` (« de » / « a ») oriente `ouvert` : début ou fin d'ère."""
	if not isinstance(borne, dict):
		raise ValueError("borne qui n'est pas un objet")
	ere_id = borne.get("ere")
	if ere_id not in eres.par_id:
		raise ValueError(f"ère inconnue : {ere_id!r}")
	i, ere = eres.par_id[ere_id]
	cles = [k for k in borne if k != "ere"]
	if len(cles) != 1 or cles[0] not in CLES_BORNE:
		raise ValueError(f"une borne porte `ere` et exactement une clé parmi {', '.join(CLES_BORNE)} : {sorted(cles)}")
	cle, val = cles[0], borne[cles[0]]
	typ = ere.get("type")
	if cle not in _CLES_PAR_TYPE.get(typ, set()):
		raise ValueError(f"clé `{cle}` impossible dans l'ère {ere_id} ({typ})")

	if cle == "inconnu":
		if val is not True:
			raise ValueError("`inconnu` vaut true")
		return float(i), i + 1.0, "inconnu"
	if cle == "ouvert":
		if val is not True:
			raise ValueError("`ouvert` vaut true")
		if role not in ("de", "a"):
			raise ValueError("`ouvert` n'a de sens qu'en début (`de`) ou fin (`a`) de période")
		t = float(i) if role == "de" else i + 1.0
		return t, t, "ouvert"
	if cle in ("rang", "entre_rangs"):
		rangs = eres.rangs(ere)
		vals = [val] if cle == "rang" else val
		if cle == "entre_rangs" and (not isinstance(val, list) or len(val) != 2):
			raise ValueError("`entre_rangs` = [premier, dernier]")
		for v in vals:
			if v not in rangs:
				raise ValueError(f"rang {v!r} absent de l'ère {ere_id}")
		k1, k2 = rangs.index(vals[0]), rangs.index(vals[-1])
		if k1 > k2:
			raise ValueError(f"`entre_rangs` inversé : {val}")
		n = len(rangs)
		return i + k1 / n, i + (k2 + 1) / n, "rang"

	# Numérique : `ans`/`entre` (passé), `dans`/`entre_dans` (futur).
	if cle in ("ans", "dans"):
		vals = [val]
	else:
		if not isinstance(val, list) or len(val) != 2:
			raise ValueError(f"`{cle}` = [a, b]")
		vals = val
	if not all(_est_nombre(v) for v in vals):
		raise ValueError(f"`{cle}` attend des nombres : {val!r}")
	if cle == "entre" and vals[0] < vals[1]:
		raise ValueError(f"`entre` = [plus_ancien, plus_recent] : {val} est inversé")
	if cle == "entre_dans" and vals[0] > vals[1]:
		raise ValueError(f"`entre_dans` = [plus_proche, plus_lointain] : {val} est inversé")
	ts = [eres.t_numerique(typ, v) for v in vals]
	if any(t is None for t in ts):
		raise ValueError(f"`{cle}` {val} hors de toute ère {typ}")
	milieu = sum(vals) / len(vals)
	lo, hi = sorted((ere["debut"], ere["fin"]))
	if not (lo - _EPS <= milieu <= hi + _EPS):
		raise ValueError(f"`{cle}` {val} hors de l'ère déclarée {ere_id} ({ere['debut']} → {ere['fin']})")
	return min(ts), max(ts), ("exact" if len(vals) == 1 else "incertain")


def texte_borne(borne, eres: _Eres, role: str = None) -> str:
	"""Notation lisible d'une borne valide."""
	_, ere = eres.par_id[borne["ere"]]
	nom = ere.get("libelle", borne["ere"])
	libelles = {r.get("id"): r.get("libelle", r.get("id")) for r in ere.get("rangs") or []}
	if "ans" in borne:
		return "aujourd'hui" if borne["ans"] == 0 else f"il y a {_nombre(borne['ans'])} ans"
	if "entre" in borne:
		a, b = borne["entre"]
		return f"? entre {_nombre(a)} et {_nombre(b)} ans avant l'ère actuelle"
	if "dans" in borne:
		return f"dans {_nombre(borne['dans'])} ans"
	if "entre_dans" in borne:
		a, b = borne["entre_dans"]
		return f"? dans {_nombre(a)} à {_nombre(b)} ans"
	if "rang" in borne:
		lib = libelles.get(borne["rang"], borne["rang"])
		return f"rang {lib}" if ere.get("id") == "jeu" else lib
	if "entre_rangs" in borne:
		a, b = (libelles.get(r, r) for r in borne["entre_rangs"])
		return f"? entre {a} et {b}"
	if "inconnu" in borne:
		return f"? à un moment inconnu — {nom}"
	if "ouvert" in borne:
		if role == "de":
			return f"depuis toujours ({nom})" if eres.par_id[borne["ere"]][0] == 0 else f"dès le début — {nom}"
		if ere.get("type") == "passe" and ere.get("fin") == 0:
			return "jusqu'à aujourd'hui"
		return f"jusqu'à la fin — {nom}"
	return "?"


def notation(quand: dict, eres: _Eres) -> str:
	if "moment" in quand:
		return texte_borne(quand["moment"], eres)
	return f"de {texte_borne(quand['de'], eres, 'de')} à {texte_borne(quand['a'], eres, 'a')}"


def _bornes_calc(ev: dict, eres: _Eres) -> dict:
	"""{forme, debut:{t,genre}, fin:{t,genre}} — lève ValueError si le `quand` est faux."""
	q = ev.get("quand")
	if not isinstance(q, dict):
		raise ValueError("`quand` manquant")
	if "moment" in q:
		if "de" in q or "a" in q:
			raise ValueError("`quand` = moment OU de/a, pas les deux")
		a, b, g = intervalle(q["moment"], eres)
		return {"forme": "point", "debut": {"t": [a, b], "genre": g}, "fin": {"t": [a, b], "genre": g}}
	if "de" in q and "a" in q:
		a1, b1, g1 = intervalle(q["de"], eres, "de")
		a2, b2, g2 = intervalle(q["a"], eres, "a")
		if a1 > a2 + _EPS or b1 > b2 + _EPS:
			raise ValueError("`de` postérieur à `a`")
		return {"forme": "periode", "debut": {"t": [a1, b1], "genre": g1}, "fin": {"t": [a2, b2], "genre": g2}}
	raise ValueError("`quand` = {moment} ou {de, a}")


def image_existe(rel) -> bool:
	"""`towns/x.jpg` → vrai si le fichier existe sous un mount d'images autorisé."""
	if not isinstance(rel, str) or "/" not in rel:
		return False
	parties = rel.split("/")
	if parties[0] not in PREFIXES_IMAGE or ".." in parties or "" in parties:
		return False
	return (RESSOURCES / rel).is_file()


def nom_vignette(rel: str) -> str:
	"""Nom ASCII stable de la vignette d'une image (`towns/rome_capital.png` → `towns_rome_capital.jpg`)."""
	return re.sub(r"[^0-9A-Za-z_-]+", "_", rel.rsplit(".", 1)[0]) + ".jpg"


def url_image(rel: str, vignettes: Path = DOSSIER_VIGNETTES) -> str:
	"""La vignette si elle a été générée, sinon l'image d'origine (lourde, mais juste)."""
	from urllib.parse import quote
	nom = nom_vignette(rel)
	return URL_VIGNETTES + nom if (Path(vignettes) / nom).is_file() else "/" + quote(rel)


def t_present(eres: _Eres) -> float:
	"""Fin du « présent » : début de la première ère future (le temps du joueur EST aujourd'hui)."""
	for i, e in enumerate(eres.liste):
		if e.get("type") == "futur":
			return float(i)
	return float(len(eres.liste))


def _jusqu_a_aujourdhui(c: dict, eres: _Eres) -> bool:
	"""Fin `ouvert` sur la fin d'une ère passée qui s'achève à 0 an (« jusqu'à aujourd'hui »)."""
	if c["fin"]["genre"] != "ouvert":
		return False
	t = c["fin"]["t"][1]
	k = int(round(t)) - 1
	return abs(t - round(t)) < _EPS and 0 <= k < len(eres.liste) \
		and eres.liste[k].get("type") == "passe" and eres.liste[k].get("fin") == 0


def _vie(ent: dict, eres: _Eres, calc: dict) -> dict:
	"""{debut, fin, present} d'un fleuve — lève ValueError. La vie d'une entité est celle de son
	`evenement` (une seule date pour la cité et son fleuve) ou son propre `quand`."""
	a_ev, a_quand = "evenement" in ent, "quand" in ent
	if a_ev == a_quand:
		raise ValueError("un fleuve porte `evenement` OU `quand`")
	if a_ev:
		if ent["evenement"] not in calc:
			raise ValueError(f"`evenement` inconnu ou mal daté : {ent['evenement']!r}")
		c = json.loads(json.dumps(calc[ent["evenement"]]))
	else:
		c = _bornes_calc(ent, eres)
	c.pop("jalons", None)
	c["present"] = _jusqu_a_aujourdhui(c, eres)
	if c["present"]:
		tp = t_present(eres)
		c["fin"] = {"t": [tp, tp], "genre": "ouvert"}
	return c


def _largeurs(ent: dict, eres: _Eres) -> list:
	"""[{t: [a, b] | None, l, note}] — paliers de largeur, le premier sans `depuis` = dès la source."""
	paliers = ent.get("largeur") or [{"l": 2}]
	if not isinstance(paliers, list):
		raise ValueError("`largeur` = liste de paliers {l, depuis}")
	out, avant = [], None
	for k, p in enumerate(paliers):
		if not isinstance(p, dict) or p.get("l") not in LARGEURS:
			raise ValueError(f"palier {k} : `l` ∈ {LARGEURS}")
		if "depuis" in p:
			a, b, _ = intervalle(p["depuis"], eres)
			if avant is not None and a < avant - _EPS:
				raise ValueError(f"palier {k} : `depuis` antérieur au palier précédent")
			avant = a
			t = [a, b]
		elif k:
			raise ValueError(f"palier {k} : seul le premier palier se passe de `depuis`")
		else:
			t = None
		out.append({"t": t, "l": p["l"], "note": p.get("note", "")})
	return out


def _verifier_entites(data: dict, eres: _Eres, calc: dict, ids: set, chemin_de, image_ok) -> list:
	"""Messages (globaux : un id d'entité peut être aussi celui d'un événement)."""
	err = []
	voc = data.get("vocabulaire") or {}
	origines = data.get("origines") or {}
	entites = [e for e in data.get("entites") or [] if isinstance(e, dict)]
	vus = set()
	for ent in entites:
		eid = ent.get("id")
		pre = f"fleuve {eid}"
		if not eid or eid in vus:
			err.append(f"fleuve sans id ou en double : {eid!r}")
			continue
		vus.add(eid)
		if not ent.get("libelle"):
			err.append(f"{pre} : `libelle` manquant")
		if ent.get("famille") not in FAMILLES:
			err.append(f"{pre} : `famille` {ent.get('famille')!r} inconnue")
		if not _COULEUR.match(str(ent.get("couleur", ""))):
			err.append(f"{pre} : `couleur` attend #rrggbb")
		if ent.get("autorite", "auteur") not in AUTORITES:
			err.append(f"{pre} : autorité {ent.get('autorite')!r} inconnue")
		try:
			_vie(ent, eres, calc)
		except ValueError as e:
			err.append(f"{pre} : date : {e}")
		try:
			_largeurs(ent, eres)
		except ValueError as e:
			err.append(f"{pre} : largeur : {e}")
		rattache = ent.get("rattache") or {}
		if not rattache:
			err.append(f"{pre} : `rattache` vide — aucun événement n'y coulerait")
		for f, valeurs in rattache.items():
			permis = origines if f == "origine" else voc.get(f)
			if f not in ORDRE_RATTACHE or permis is None:
				err.append(f"{pre} : facette de rattachement inconnue : {f!r}")
				continue
			for v in valeurs:
				if v not in permis:
					err.append(f"{pre} : {f}:{v!r} absent du vocabulaire")
		for champ in ("issu_de", "absorbe_par"):
			if ent.get(champ) is not None and ent[champ] not in {e.get("id") for e in entites}:
				err.append(f"{pre} : `{champ}` vers un fleuve inconnu : {ent[champ]!r}")
		if ent.get("image") is not None and not image_ok(ent["image"]):
			err.append(f"{pre} : image introuvable : {ent['image']!r}")
		sources = ent.get("sources") or []
		if not sources:
			err.append(f"{pre} : aucune source")
		for s in sources:
			if chemin_de(s.get("fichier", "")) is None:
				err.append(f"{pre} : source hors du lore : {s.get('fichier')!r}")
	for b in data.get("bandeaux") or []:
		if not isinstance(b, dict) or b.get("evenement") not in ids or not b.get("libelle"):
			err.append(f"bandeau invalide (`evenement` connu + `libelle`) : {b!r}")
	for e in eres.liste:
		if e.get("carte") is not None and not image_ok(e["carte"]):
			err.append(f"ère {e['id']} : carte introuvable : {e['carte']!r}")
	return err


def rattacher(evenements: list, entites: list) -> dict:
	"""{id d'événement: (fleuve | None, [échos])} — `evenements` / `entites` au format du payload.

	Le fleuve d'une entité porte son propre événement. Sinon on parcourt les facettes dans
	l'ordre `ORDRE_RATTACHE`, et dans chacune les valeurs dans l'ORDRE DE L'ÉVÉNEMENT
	(« Sainte-Sophie ↔ Rome » coule à Constantinople) ; le premier fleuve VIVANT à ce moment
	l'emporte, les autres fleuves touchés et vivants sont des échos."""
	propre = {e["evenement"]: e["id"] for e in entites if e.get("evenement")}
	out = {}
	for ev in evenements:
		if ev["id"] in propre:
			out[ev["id"]] = (propre[ev["id"]], [])
			continue
		lo, hi = ev["calc"]["debut"]["t"][0], ev["calc"]["fin"]["t"][1]
		touches = []
		for f in ORDRE_RATTACHE:
			valeurs = ev.get("origine", []) if f == "origine" else ev.get("tags", {}).get(f, [])
			for v in valeurs:
				for ent in entites:
					vie = ent["calc"]
					vivant = vie["debut"]["t"][0] <= hi + _EPS and vie["fin"]["t"][1] >= lo - _EPS
					if vivant and v in (ent.get("rattache") or {}).get(f, []) and ent["id"] not in touches:
						touches.append(ent["id"])
		out[ev["id"]] = (touches[0], touches[1:]) if touches else (None, [])
	return out


def _verifier_vocabulaire(data: dict) -> list:
	err = []
	ids_eres = set()
	for e in data.get("eres") or []:
		eid = e.get("id")
		if not eid or eid in ids_eres:
			err.append(f"ère sans id ou en double : {eid!r}")
		ids_eres.add(eid)
		if e.get("type") not in TYPES_ERE:
			err.append(f"ère {eid} : type {e.get('type')!r} inconnu")
		elif e["type"] == "ordinal" and not e.get("rangs"):
			err.append(f"ère {eid} : une ère ordinale déclare ses rangs")
		elif e["type"] != "ordinal" and not (_est_nombre(e.get("debut")) and _est_nombre(e.get("fin")) and e["debut"] != e["fin"]):
			err.append(f"ère {eid} : une ère numérique déclare debut ≠ fin")
	voc = data.get("vocabulaire") or {}
	for f in voc:
		if f not in FACETTES_TAGS:
			err.append(f"facette de tags inconnue : {f!r}")
	return err


def verifier(data: dict, chemin_de=lore.chemin_de, image_ok=image_existe) -> list:
	"""[(id ou None, message)] — tout ce qui empêche de lire ou de croire la source."""
	err = [(None, m) for m in _verifier_vocabulaire(data)]
	eres = _Eres(data.get("eres"))
	voc = data.get("vocabulaire") or {}
	origines = data.get("origines") or {}
	evenements = [e for e in data.get("evenements") or [] if isinstance(e, dict)]
	ids, calc = set(), {}
	for ev in evenements:
		eid = ev.get("id")
		if not eid:
			err.append((None, f"événement sans id : {ev.get('titre')!r}"))
			continue
		if eid in ids:
			err.append((eid, "id en double"))
		ids.add(eid)
		for champ in ("titre", "resume"):
			if not ev.get(champ):
				err.append((eid, f"`{champ}` manquant"))
		for champ, permis in (("couche", COUCHES), ("categorie", CATEGORIES), ("autorite", AUTORITES), ("visibilite", VISIBILITES)):
			if ev.get(champ) not in permis:
				err.append((eid, f"`{champ}` {ev.get(champ)!r} inconnu"))
		origine = ev.get("origine")
		if not isinstance(origine, list) or not origine:
			err.append((eid, "`origine` manquante (liste d'au moins une région)"))
		else:
			for o in origine:
				if o not in origines:
					err.append((eid, f"origine {o!r} absente de `origines`"))
		q = ev.get("quand") if isinstance(ev.get("quand"), dict) else {}
		if q.get("autorite") is not None and q["autorite"] not in AUTORITES:
			err.append((eid, f"autorité de la date {q['autorite']!r} inconnue"))
		try:
			calc[eid] = _bornes_calc(ev, eres)
		except ValueError as e:
			err.append((eid, f"date : {e}"))
		for j in ev.get("jalons") or []:
			try:
				intervalle(j.get("borne"), eres)
			except ValueError as e:
				err.append((eid, f"jalon {j.get('libelle')!r} : {e}"))
		tags = ev.get("tags") or {}
		for f, valeurs in tags.items():
			if f not in voc:
				err.append((eid, f"facette de tags inconnue : {f!r}"))
				continue
			for v in valeurs:
				if v not in voc[f]:
					err.append((eid, f"tag {f}:{v!r} absent du vocabulaire"))
		sources = ev.get("sources") or []
		if not sources:
			err.append((eid, "aucune source"))
		for s in sources:
			if chemin_de(s.get("fichier", "")) is None:
				err.append((eid, f"source hors du lore : {s.get('fichier')!r}"))
		for c in ev.get("contradictions") or []:
			if not c.get("texte"):
				err.append((eid, "contradiction sans texte"))
		if ev.get("image") is not None and not image_ok(ev["image"]):
			err.append((eid, f"image introuvable : {ev['image']!r}"))
	for ev in evenements:
		eid = ev.get("id")
		for champ in ("liens", "apres"):
			for cible in ev.get(champ) or []:
				if cible not in ids:
					err.append((eid, f"`{champ}` vers un id inconnu : {cible!r}"))
		for cible in ev.get("apres") or []:
			if eid in calc and cible in calc:
				b, a = calc[eid]["debut"]["t"], calc[cible]["debut"]["t"]
				if b[0] < a[0] - _EPS or b[1] < a[1] - _EPS:
					err.append((eid, f"déclaré après {cible!r} mais daté avant lui"))
	err += [(None, m) for m in _verifier_entites(data, eres, calc, ids, chemin_de, image_ok)]
	return err


def valider(data: dict, chemin_de=lore.chemin_de, image_ok=image_existe) -> list:
	"""Messages lisibles « id : message » (vide = source saine)."""
	return [f"{i} : {m}" if i else m for i, m in verifier(data, chemin_de, image_ok)]


def _eres_touchees(c: dict, eres: _Eres) -> list:
	lo = int(c["debut"]["t"][0])
	hi = c["fin"]["t"][1]
	hi = int(hi) - 1 if hi == int(hi) and hi > lo else int(hi)
	return [eres.liste[k]["id"] for k in range(lo, min(hi, len(eres.liste) - 1) + 1)]


def payload(data: dict, chemin_de=lore.chemin_de, image_ok=image_existe, vignettes: Path = DOSSIER_VIGNETTES) -> dict:
	"""Ce que lit la page : ères, vocabulaire, facettes (avec comptes), événements enrichis
	(temps normalisé, notation, URL des sources, fleuve de rattachement, erreurs propres),
	fleuves, bandeaux, cartes d'ères et l'en-tête brut de la source pour l'export du
	sous-ensemble filtré."""
	eres = _Eres(data.get("eres"))
	erreurs = verifier(data, chemin_de, image_ok)
	par_id = {}
	for i, m in erreurs:
		par_id.setdefault(i, []).append(m)
	evenements = []
	for ev in data.get("evenements") or []:
		if not isinstance(ev, dict) or not ev.get("id"):
			continue
		try:
			c = _bornes_calc(ev, eres)
		except ValueError:
			continue  # déjà signalé ; un événement sans date ne se place pas
		jalons = []
		for j in ev.get("jalons") or []:
			try:
				a, b, g = intervalle(j.get("borne"), eres)
			except ValueError:
				continue
			jalons.append({"libelle": j.get("libelle", ""), "t": [a, b], "genre": g,
						   "notation": texte_borne(j["borne"], eres)})
		c["jalons"] = jalons
		q = ev["quand"]
		sources = []
		for s in ev.get("sources") or []:
			chemin = chemin_de(s.get("fichier", ""))
			sources.append({**s, "url": lore.URL_LORE + lore.cle_de(chemin) if chemin else None})
		evenements.append({
			"id": ev["id"],
			"titre": ev.get("titre", ev["id"]),
			"titre_court": ev.get("titre_court") or ev.get("titre", ev["id"]),
			"resume": ev.get("resume", ""),
			"couche": ev.get("couche"),
			"categorie": ev.get("categorie"),
			"origine": list(ev.get("origine") or []),
			"autorite": ev.get("autorite"),
			"visibilite": ev.get("visibilite", "public"),
			"tags": {f: list(v) for f, v in (ev.get("tags") or {}).items()},
			"liens": list(ev.get("liens") or []),
			"apres": list(ev.get("apres") or []),
			"contradictions": list(ev.get("contradictions") or []),
			"erreurs": par_id.get(ev["id"], []),
			"notation": notation(q, eres),
			"quand_autorite": q.get("autorite", ev.get("autorite")),
			"quand_note": q.get("note", ""),
			"eres": _eres_touchees(c, eres),
			"calc": c,
			"sources": sources,
			"image": url_image(ev["image"], vignettes) if ev.get("image") and image_ok(ev["image"]) else None,
			"brut": ev,
		})
	calc = {e["id"]: e["calc"] for e in evenements}
	entites = []
	for ent in data.get("entites") or []:
		if not isinstance(ent, dict) or not ent.get("id"):
			continue
		try:
			vie, paliers = _vie(ent, eres, calc), _largeurs(ent, eres)
		except ValueError:
			continue  # déjà signalé ; un fleuve sans date ne coule pas
		entites.append({
			"id": ent["id"], "libelle": ent.get("libelle", ent["id"]), "famille": ent.get("famille"),
			"couleur": ent.get("couleur", "#7a6446"), "evenement": ent.get("evenement"),
			"rattache": {f: list(v) for f, v in (ent.get("rattache") or {}).items()},
			"issu_de": ent.get("issu_de"), "absorbe_par": ent.get("absorbe_par"),
			"autorite": ent.get("autorite", "auteur"), "note": ent.get("note", ""),
			"image": url_image(ent["image"], vignettes) if ent.get("image") and image_ok(ent["image"]) else None,
			"calc": vie, "largeurs": paliers,
		})
	liens = rattacher(evenements, entites)
	for ev in evenements:
		ev["riviere"], ev["echos"] = liens[ev["id"]]
	ids_ev = {e["id"] for e in evenements}
	bandeaux = [{"evenement": b["evenement"], "libelle": b["libelle"]} for b in data.get("bandeaux") or []
				if isinstance(b, dict) and b.get("evenement") in ids_ev and b.get("libelle")]
	cartes = {e["id"]: url_image(e["carte"], vignettes) for e in eres.liste if e.get("carte") and image_ok(e["carte"])}
	facettes = {
		"couche": COUCHES, "autorite": AUTORITES, "categorie": CATEGORIES, "visibilite": VISIBILITES,
		"ere": {e["id"]: e.get("libelle", e["id"]) for e in eres.liste},
		"origine": dict(data.get("origines") or {}),
	}
	facettes.update({f: dict((data.get("vocabulaire") or {}).get(f, {})) for f in FACETTES_TAGS})
	comptes = {f: {k: 0 for k in v} for f, v in facettes.items()}
	for ev in evenements:
		for f in ("couche", "autorite", "categorie", "visibilite"):
			if ev[f] in comptes[f]:
				comptes[f][ev[f]] += 1
		for e in ev["eres"]:
			comptes["ere"][e] = comptes["ere"].get(e, 0) + 1
		for o in ev["origine"]:
			if o in comptes["origine"]:
				comptes["origine"][o] += 1
		for f in FACETTES_TAGS:
			for v in ev["tags"].get(f, []):
				if v in comptes[f]:
					comptes[f][v] += 1
	return {
		"eres": eres.liste,
		"facettes": {f: [{"id": k, "libelle": lib, "n": comptes[f].get(k, 0)} for k, lib in v.items()]
					 for f, v in facettes.items()},
		"evenements": evenements,
		"entites": entites,
		"familles": FAMILLES,
		"bandeaux": bandeaux,
		"cartes": cartes,
		"present": t_present(eres),
		"erreurs_globales": par_id.get(None, []),
		"entete": {k: v for k, v in data.items() if k != "evenements"},
	}

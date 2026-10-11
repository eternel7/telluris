"""Chronologie du lore (pur) : source `docs/lore/chronologie.json`, validation, payload de la
frise SVG de `/admin/lore/chronologie`.

Modèle de temps — aucune date terrestre :
- des ÈRES dans l'ordre de l'axe ; `ordinal` (repérée par rangs : l'antédiluvien, le temps
  du joueur), `passe` (« ans avant l'ère actuelle », décroissant) ou `futur` (« dans N ans ») ;
- une BORNE = `{"ere": …}` + UNE clé parmi `ans` · `entre` [plus_ancien, plus_recent] ·
  `dans` · `entre_dans` [plus_proche, plus_lointain] · `rang` · `entre_rangs` [premier, dernier]
  · `inconnu` · `ouvert` ;
- un `quand` = `{"moment": borne}` ou `{"de": borne, "a": borne}`.

Le serveur réduit chaque borne à un intervalle de TEMPS NORMALISÉ `t` = indice de l'ère +
fraction dans l'ère (0 → 1, dans le sens de l'axe). `t` est continu d'une ère numérique à
l'autre (750 ans = fin d'« avant la Vague » = début d'« après la Vague ») et ne dépend
d'aucun zoom : le client ne fait que projeter `t` en pixels (`chronoEchelle`), il ne
recalcule jamais une date — une seule vérité, ici.
"""

import json
from pathlib import Path

from utils import lore

CHEMIN = lore.RACINE / "lore" / "chronologie.json"

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


def verifier(data: dict, chemin_de=lore.chemin_de) -> list:
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
	return err


def valider(data: dict, chemin_de=lore.chemin_de) -> list:
	"""Messages lisibles « id : message » (vide = source saine)."""
	return [f"{i} : {m}" if i else m for i, m in verifier(data, chemin_de)]


def _eres_touchees(c: dict, eres: _Eres) -> list:
	lo = int(c["debut"]["t"][0])
	hi = c["fin"]["t"][1]
	hi = int(hi) - 1 if hi == int(hi) and hi > lo else int(hi)
	return [eres.liste[k]["id"] for k in range(lo, min(hi, len(eres.liste) - 1) + 1)]


def payload(data: dict, chemin_de=lore.chemin_de) -> dict:
	"""Ce que lit la page : ères, vocabulaire, facettes (avec comptes), événements enrichis
	(temps normalisé, notation, URL des sources, erreurs propres) et l'en-tête brut de la
	source pour l'export du sous-ensemble filtré."""
	eres = _Eres(data.get("eres"))
	erreurs = verifier(data, chemin_de)
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
			"brut": ev,
		})
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
		"erreurs_globales": par_id.get(None, []),
		"entete": {k: v for k, v in data.items() if k != "evenements"},
	}

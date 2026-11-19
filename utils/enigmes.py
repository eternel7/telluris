# utils/enigmes.py
# Système d'énigmes (pur) — conception arbitrée par l'Auteur le 19/11 : docs/conception_enigmes.md.
# Référence : Myst (le monde EST l'énigme, indices dans le monde, solutions croisées), dont on
# prend l'esprit, jamais le contenu.
#
# Une énigme est un doc `enigme:*` RÉUTILISABLE, résolu dans un panneau dédié de /play :
#
#   {
#     "_id": "enigme:xxx", "type": "enigme", "nom": "…", "famille": "<une de FAMILLES>",
#     "texte": "ce que l'on voit en ouvrant",
#     "image": "enigmes/xxx.jpg",            # optionnel : scène illustrée (sinon parchemin + SVG)
#     "zones": [{"cle", "x", "y", "w", "h"}], # optionnel : zones cliquables de l'image, en % de l'image
#     "lieux": ["lieu:…"],                   # OBLIGATOIRE : où le panneau peut s'ouvrir (fail-closed)
#     "conditions": [ … ],                   # optionnel : clauses de `utils/acces` (ex. quête active)
#     "prerequis": ["enigme:…"],             # optionnel : énigmes à avoir résolues (croisement)
#     "elements": { … },                     # PUBLIC, propre à la famille
#     "solution": { … },                     # PRIVÉ — ne part JAMAIS au client
#     "reussite": "texte", "echec": "remarque d'un essai faux",
#     "commentaires": [{"quand", "qui": {"protege": "Aélis"} | {"vocation": "lettre"}, "texte"}]
#   }
#
# ⚠️ Le SERVEUR tranche : `vue_client` est le SEUL filtre de ce qui part au navigateur (même
# rôle que `combat.vue_client` pour les pièges cachés). Aucun indice n'est donné par le système :
# l'aide vient du monde (textes, gravures) et des COMMENTAIRES des escortés et des compagnons,
# chacun avec sa voix, jamais la solution.
#
# État sur le personnage (aucune migration : champ absent ⇒ rien de commencé) :
#   character["enigmes"][id] = {"resolue", "resolue_at", "essais", "journal": [...], "etat": {...}}
# Une énigme résolue le reste POUR TOUJOURS (quête abandonnée comprise). Un essai faux ne coûte
# rien : découvertes et étapes validées sont gardées. Le journal se tient tout seul.
#
# Module PUR : rien n'est lu ni sauvé ici ; le router injecte les clauses d'accès et les voix.

FAMILLES = ("deduction", "crans", "graphe", "association", "placement", "reseau")

# Moments où un commentaire peut se dire. Les clés à suffixe nomment un élément de l'énigme :
# `examen:<indice>` (déduction), `salle:<salle>` (graphe), `revele:<noeud>` (réseau).
QUAND_SIMPLES = ("ouverture", "echec", "reussite")
QUAND_PREFIXES = ("examen:", "salle:", "revele:")

JOURNAL_MAX = 200


# ---------------------------------------------------------------------------
# Petits outils
# ---------------------------------------------------------------------------

def _liste(v) -> list:
	return [x for x in (v or []) if isinstance(x, dict)] if isinstance(v, list) else []


def _ids(v) -> list:
	return [x.get("id") for x in _liste(v) if isinstance(x.get("id"), str)]


def _par_id(v) -> dict:
	return {x["id"]: x for x in _liste(v) if isinstance(x.get("id"), str)}


def _label(v, id_) -> str:
	x = _par_id(v).get(id_) or {}
	return str(x.get("label") or x.get("texte") or id_)


def etat_de(character: dict, enigme_id: str) -> dict:
	"""État de l'énigme pour ce personnage, CRÉÉ s'il manque (mute le personnage)."""
	tout = character.setdefault("enigmes", {})
	if not isinstance(tout, dict):
		tout = character["enigmes"] = {}
	e = tout.get(enigme_id)
	if not isinstance(e, dict):
		e = tout[enigme_id] = {}
	e.setdefault("resolue", False)
	e.setdefault("essais", 0)
	if not isinstance(e.get("journal"), list):
		e["journal"] = []
	if not isinstance(e.get("etat"), dict):
		e["etat"] = {}
	return e


def lire_etat(character: dict, enigme_id: str) -> dict:
	"""État en LECTURE seule (copie défensive, ne crée rien)."""
	e = ((character or {}).get("enigmes") or {}).get(enigme_id)
	return e if isinstance(e, dict) else {}


def resolues(character: dict) -> set:
	"""Ids des énigmes résolues — la forme que lisent les conditions `enigme_resolue`."""
	tout = (character or {}).get("enigmes") or {}
	if not isinstance(tout, dict):
		return set()
	return {k for k, v in tout.items() if isinstance(v, dict) and v.get("resolue")}


def est_resolue(character: dict, enigme_id) -> bool:
	return isinstance(enigme_id, str) and enigme_id in resolues(character)


def enigme_resolue_ok(character: dict, filtre) -> bool:
	"""Prédicat de la condition `enigme_resolue: {id, attendu?}` — PARTAGÉ par les choix de
	dialogue (`utils/pnj`) et les clauses d'accès/présence (`utils/acces`). Même forme et même
	fail-closed que `quete_reussie` : filtre mal formé ⇒ faux."""
	if not isinstance(filtre, dict):
		return False
	eid = filtre.get("id")
	if not isinstance(eid, str) or not eid:
		return False
	return est_resolue(character, eid) is bool(filtre.get("attendu", True))


def _noter(e: dict, fait: str) -> None:
	"""Journal automatique : un fait observé, sans doublon, borné."""
	if fait and fait not in e["journal"]:
		e["journal"].append(fait)
		del e["journal"][:-JOURNAL_MAX]


# ---------------------------------------------------------------------------
# Ouverture
# ---------------------------------------------------------------------------

def ouvrable(doc: dict, character: dict, clauses_fn=None) -> tuple[bool, str | None]:
	"""Le panneau peut-il s'ouvrir ICI pour ce personnage ? → (ok, motif du refus).

	- `lieux` OBLIGATOIRE et le personnage doit s'y trouver (fail-closed : sans lieux, nulle part) ;
	- chaque `prerequis` résolu (croisement façon Myst) ;
	- `conditions` (clauses `utils/acces`) via `clauses_fn(conditions) -> bool`, injectée."""
	if not isinstance(doc, dict) or doc.get("type") != "enigme" or doc.get("famille") not in FAMILLES:
		return False, "Énigme inconnue."
	lieux = doc.get("lieux")
	if not isinstance(lieux, list) or (character or {}).get("lieu") not in lieux:
		return False, "Ce n'est pas ici que cela se joue."
	for pre in doc.get("prerequis") or []:
		if not est_resolue(character, pre):
			return False, "Quelque chose vous échappe encore ; il faut comprendre ailleurs d'abord."
	conditions = doc.get("conditions")
	if conditions and not (clauses_fn and clauses_fn(conditions)):
		return False, "Rien ici ne vous retient pour l'instant."
	return True, None


def enigmes_du_lieu(docs, character: dict, clauses_fn=None) -> list:
	"""Boutons d'énigme du lieu courant dans /play : docs `bouton: true` OUVRABLES ici
	(même contrôle que l'ouverture). Les autres s'ouvrent par un choix de dialogue.
	→ [{"id", "nom", "resolue"}], dans l'ordre des ids (stable d'un rendu à l'autre)."""
	out = []
	for d in sorted((x for x in docs or [] if isinstance(x, dict) and x.get("bouton")),
					key=lambda x: str(x.get("_id"))):
		if ouvrable(d, character, clauses_fn)[0]:
			out.append({"id": d["_id"], "nom": d.get("nom") or d["_id"],
						"resolue": est_resolue(character, d["_id"])})
	return out


# ---------------------------------------------------------------------------
# Vue client (le SEUL filtre de ce qui part au navigateur)
# ---------------------------------------------------------------------------

def _liaisons_connues(doc: dict, etat: dict) -> list:
	el = doc.get("elements") or {}
	revelees = set(etat.get("revelees") or [])
	cachees = [l for l in _liste((doc.get("solution") or {}).get("liaisons_cachees")) if l.get("id") in revelees]
	return [{"id": l["id"], "a": l.get("a"), "b": l.get("b"), "revelee": l in cachees}
			for l in _liste(el.get("liaisons")) + cachees if isinstance(l.get("id"), str)]


def vue_client(doc: dict, character: dict) -> dict:
	"""Ce que voit le panneau : jamais `solution`, `conditions` ni `commentaires`."""
	e = lire_etat(character, doc.get("_id"))
	etat = dict(e.get("etat") or {})
	famille = doc.get("famille")
	el = dict(doc.get("elements") or {})
	if famille == "deduction":
		# L'énoncé d'un indice est public ; ce qu'il APPREND n'arrive qu'au journal, une fois examiné.
		el = {"indices": [{"id": i, "label": _label(el.get("indices"), i)} for i in _ids(el.get("indices"))],
			  "conclusions": [{"id": c, "label": _label(el.get("conclusions"), c)} for c in _ids(el.get("conclusions"))]}
	elif famille == "crans":
		etat.setdefault("positions", depart_crans(doc))
	elif famille == "graphe":
		etat.setdefault("position", el.get("depart"))
		etat["arches_ici"] = arches_de(doc, etat["position"])
	elif famille == "reseau":
		el["liaisons"] = _liaisons_connues(doc, etat)
	vue = {
		"id": doc.get("_id"),
		"nom": doc.get("nom", ""),
		"famille": famille,
		"texte": doc.get("texte", ""),
		"image": doc.get("image"),
		"zones": _liste(doc.get("zones")),
		"elements": el,
		"etat": etat,
		"journal": list(e.get("journal") or []),
		"resolue": bool(e.get("resolue")),
	}
	if vue["resolue"]:
		vue["reussite"] = doc.get("reussite", "")
	return vue


# ---------------------------------------------------------------------------
# Familles
# ---------------------------------------------------------------------------

class EssaiInvalide(ValueError):
	"""Requête mal formée (422) — distincte d'un essai FAUX, qui n'est pas une erreur."""


def depart_crans(doc: dict) -> dict:
	return {p["id"]: int(p.get("depart", 0)) for p in _liste((doc.get("elements") or {}).get("pieces"))
			if isinstance(p.get("id"), str)}


def arches_de(doc: dict, salle) -> list:
	"""Arches qu'on peut franchir depuis `salle` : la liste de la salle, sinon toutes."""
	el = doc.get("elements") or {}
	propres = (_par_id(el.get("salles")).get(salle) or {}).get("arches")
	tout = _ids(el.get("arches"))
	if isinstance(propres, list):
		return [a for a in propres if a in tout]
	return tout


def _deduction(doc, e, action, body):
	el, sol = doc.get("elements") or {}, doc.get("solution") or {}
	examines = e["etat"].setdefault("examines", [])
	if action == "examiner":
		cle = body.get("cle")
		indice = _par_id(el.get("indices")).get(cle)
		if not indice:
			raise EssaiInvalide("Indice inconnu.")
		if cle not in examines:
			examines.append(cle)
		_noter(e, str(indice.get("fait") or indice.get("label") or cle))
		return {"evenement": f"examen:{cle}", "essai": False}
	if action == "conclure":
		cle = body.get("cle")
		if cle not in _ids(el.get("conclusions")):
			raise EssaiInvalide("Conclusion inconnue.")
		essentiels = [i for i in (sol.get("indices") or []) if isinstance(i, str)]
		seuil = int(sol.get("seuil", len(essentiels)))
		vus = len(set(examines) & set(essentiels))
		if cle == sol.get("conclusion") and vus >= seuil:
			return {"essai": True, "reussi": True}
		if cle == sol.get("conclusion"):
			# Bonne idée, mais rien ne la prouve encore : on le dit sans désigner l'indice manquant.
			return {"essai": True, "reussi": False, "texte": doc.get("texte_insuffisant")
					or "Rien de ce que vous avez observé ne le prouve encore."}
		return {"essai": True, "reussi": False}
	raise EssaiInvalide("Action inconnue pour une déduction.")


def _crans(doc, e, action, body):
	if action != "essayer":
		raise EssaiInvalide("Action inconnue pour une combinaison.")
	pieces = _par_id((doc.get("elements") or {}).get("pieces"))
	pos = body.get("positions")
	if not isinstance(pos, dict) or set(pos) != set(pieces):
		raise EssaiInvalide("Positions incomplètes.")
	propre = {}
	for pid, v in pos.items():
		if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < int(pieces[pid].get("crans", 1)):
			raise EssaiInvalide("Cran hors limites.")
		propre[pid] = v
	e["etat"]["positions"] = propre
	attendu = (doc.get("solution") or {}).get("positions") or {}
	return {"essai": True, "reussi": propre == attendu}


def _graphe(doc, e, action, body):
	el = doc.get("elements") or {}
	depart = el.get("depart")
	if action == "recommencer":
		e["etat"]["position"] = depart
		return {"essai": False}
	if action != "passer":
		raise EssaiInvalide("Action inconnue pour un réseau de passages.")
	ici = e["etat"].get("position") or depart
	arche = body.get("cle")
	if arche not in arches_de(doc, ici):
		raise EssaiInvalide("Arche inconnue ici.")
	transitions = ((doc.get("solution") or {}).get("transitions") or {}).get(ici) or {}
	dest = transitions.get(arche, depart)
	if dest not in _ids(el.get("salles")):
		dest = depart
	e["etat"]["position"] = dest
	salles, arches = el.get("salles"), el.get("arches")
	_noter(e, f"Depuis {_label(salles, ici)}, l'arche {_label(arches, arche)} mène à {_label(salles, dest)}.")
	# Ramené à l'entrée = un essai faux (rien de perdu : le journal garde la transition).
	return {"evenement": f"salle:{dest}", "essai": dest == depart,
			"reussi": dest == el.get("cible")}


def _association(doc, e, action, body):
	if action != "associer":
		raise EssaiInvalide("Action inconnue pour une association.")
	el, sol = doc.get("elements") or {}, doc.get("solution") or {}
	g, d = body.get("gauche"), body.get("droite")
	if g not in _ids(el.get("gauche")) or d not in _ids(el.get("droite")):
		raise EssaiInvalide("Association inconnue.")
	paires = sol.get("paires") or {}
	trouvees = e["etat"].setdefault("paires", {})
	if paires.get(g) != d:
		return {"essai": True, "reussi": False}
	trouvees[g] = d
	_noter(e, f"« {_label(el.get('gauche'), g)} » — {_label(el.get('droite'), d)}")
	seuil = int(sol.get("seuil", len(paires)))
	return {"essai": True, "reussi": len(trouvees) >= seuil, "partiel": True}


def _placement(doc, e, action, body):
	if action != "essayer":
		raise EssaiInvalide("Action inconnue pour un placement.")
	el = doc.get("elements") or {}
	pl = body.get("placement")
	emplacements, symboles = set(_ids(el.get("emplacements"))), set(_ids(el.get("symboles")))
	if not isinstance(pl, dict) or not set(pl) <= emplacements or not all(v in symboles for v in pl.values()):
		raise EssaiInvalide("Placement invalide.")
	e["etat"]["placement"] = dict(pl)
	return {"essai": True, "reussi": pl == ((doc.get("solution") or {}).get("placement") or {})}


def _reseau(doc, e, action, body):
	el, sol = doc.get("elements") or {}, doc.get("solution") or {}
	if action == "reveler":
		noeud = body.get("cle")
		if noeud not in _ids(el.get("noeuds")):
			raise EssaiInvalide("Lieu inconnu sur la carte.")
		revelees = e["etat"].setdefault("revelees", [])
		trouvees = [l for l in _liste(sol.get("liaisons_cachees")) if noeud in (l.get("a"), l.get("b"))]
		for l in trouvees:
			if l.get("id") not in revelees:
				revelees.append(l["id"])
				noeuds = el.get("noeuds")
				_noter(e, f"Le miroir montre un lien entre {_label(noeuds, l.get('a'))} et {_label(noeuds, l.get('b'))}.")
		return {"evenement": f"revele:{noeud}", "essai": False}
	if action != "essayer":
		raise EssaiInvalide("Action inconnue pour un réseau de liaisons.")
	actives, ancrees = body.get("actives"), body.get("ancrees")
	if not isinstance(actives, list) or not isinstance(ancrees, list):
		raise EssaiInvalide("Liaisons invalides.")
	connues = {l["id"] for l in _liaisons_connues(doc, e["etat"])}
	if not set(actives) <= connues or not set(ancrees) <= set(actives):
		raise EssaiInvalide("Liaison inconnue, ou pierre posée hors d'une liaison ouverte.")
	e["etat"]["actives"], e["etat"]["ancrees"] = list(actives), list(ancrees)
	ok = set(actives) == set(sol.get("actives") or []) and set(ancrees) == set(sol.get("ancrees") or [])
	return {"essai": True, "reussi": ok}


_RESOLVEURS = {
	"deduction": _deduction, "crans": _crans, "graphe": _graphe,
	"association": _association, "placement": _placement, "reseau": _reseau,
}


def agir(doc: dict, character: dict, action: str, body: dict, now: int) -> dict:
	"""Applique une action au personnage (MUTE, ne sauve pas). → résultat :
	{"reussi": bool, "resolue": bool, "texte": str|None, "evenements": [...]}.
	Lève `EssaiInvalide` sur une requête mal formée. Une énigme déjà résolue ne bouge plus."""
	e = etat_de(character, doc.get("_id"))
	if e.get("resolue"):
		return {"reussi": True, "resolue": True, "texte": doc.get("reussite", ""), "evenements": []}
	r = _RESOLVEURS[doc.get("famille")](doc, e, action, body or {})
	evenements = [r["evenement"]] if r.get("evenement") else []
	if r.get("essai"):
		e["essais"] = int(e.get("essais", 0)) + 1
	if r.get("reussi"):
		e["resolue"], e["resolue_at"] = True, int(now)
		evenements.append("reussite")
		return {"reussi": True, "resolue": True, "texte": doc.get("reussite", ""), "evenements": evenements}
	# Essai FAUX : une remarque, aucune pénalité. Une étape juste mais incomplète (paire trouvée,
	# `partiel`) n'est pas un échec : elle s'inscrit au journal en silence.
	texte = None
	if r.get("essai") and not r.get("partiel"):
		texte = r.get("texte") or doc.get("echec") or "Rien ne se passe."
		evenements.append("echec")
	return {"reussi": False, "resolue": False, "texte": texte, "evenements": evenements}


# ---------------------------------------------------------------------------
# Commentaires des escortés et des compagnons
# ---------------------------------------------------------------------------

def commentaires(doc: dict, evenements, voix) -> list:
	"""Répliques dites à ces moments par les présents. `voix` (fournie par le router) =
	[{"prenom", "protege": True} | {"prenom", "vocation"}]. Un commentaire `qui.protege`
	vise un escorté par son prénom ; `qui.vocation` le premier compagnon de cette vocation.
	→ [{"qui": prenom, "texte"}], dans l'ordre des données."""
	moments = set(evenements or [])
	out = []
	for c in _liste(doc.get("commentaires")):
		if c.get("quand") not in moments or not c.get("texte"):
			continue
		qui = c.get("qui") or {}
		parleur = None
		for v in voix or []:
			if "protege" in qui and v.get("protege") and str(v.get("prenom", "")).lower() == str(qui["protege"]).lower():
				parleur = v
				break
			if "vocation" in qui and not v.get("protege") and v.get("vocation") == qui["vocation"]:
				parleur = v
				break
		if parleur:
			out.append({"qui": parleur.get("prenom", ""), "texte": str(c["texte"]).replace("{nom}", parleur.get("prenom", ""))})
	return out


# ---------------------------------------------------------------------------
# Validation (générateurs dev/gen_*.py, linter) — une énigme INSOLUBLE ne doit jamais partir
# ---------------------------------------------------------------------------

def _doublons(ids) -> list:
	vus, d = set(), []
	for i in ids:
		if i in vus:
			d.append(i)
		vus.add(i)
	return d


def valider_enigme(doc: dict) -> list:
	"""Fautes qui rendraient l'énigme impossible à ouvrir ou à résoudre, en clair (vide = OK)."""
	f = []
	if not isinstance(doc, dict):
		return ["doit être un objet"]
	eid = doc.get("_id")
	if not (isinstance(eid, str) and eid.startswith("enigme:")):
		f.append("`_id` doit commencer par `enigme:`")
	if doc.get("type") != "enigme":
		f.append("`type` doit valoir `enigme`")
	famille = doc.get("famille")
	if famille not in FAMILLES:
		return f + [f"`famille` doit être l'une de {', '.join(FAMILLES)}"]
	lieux = doc.get("lieux")
	if not isinstance(lieux, list) or not lieux or not all(isinstance(l, str) and l.startswith("lieu:") for l in lieux):
		f.append("`lieux` : liste non vide d'ids `lieu:…` (sans elle, l'énigme ne s'ouvre nulle part)")
	el, sol = doc.get("elements") or {}, doc.get("solution") or {}
	for cle in ("indices", "conclusions", "pieces", "salles", "arches", "gauche", "droite",
				"symboles", "emplacements", "noeuds", "liaisons"):
		for d in _doublons(_ids(el.get(cle))):
			f.append(f"`elements.{cle}` : id `{d}` en double")
	if famille == "deduction":
		indices = set(_ids(el.get("indices")))
		if sol.get("conclusion") not in _ids(el.get("conclusions")):
			f.append("`solution.conclusion` n'est pas une conclusion proposée")
		ess = sol.get("indices") or []
		if not set(ess) <= indices:
			f.append("`solution.indices` cite un indice absent")
		if int(sol.get("seuil", len(ess))) > len(set(ess) & indices):
			f.append("`solution.seuil` dépasse les indices essentiels : insoluble")
	elif famille == "crans":
		pieces = _par_id(el.get("pieces"))
		pos = sol.get("positions") or {}
		if set(pos) != set(pieces) or not pieces:
			f.append("`solution.positions` doit donner un cran à CHAQUE pièce")
		for pid, v in pos.items():
			p = pieces.get(pid) or {}
			if not isinstance(v, int) or not 0 <= v < int(p.get("crans", 1)):
				f.append(f"`solution.positions.{pid}` hors des crans de la pièce")
	elif famille == "graphe":
		salles = set(_ids(el.get("salles")))
		if el.get("depart") not in salles or el.get("cible") not in salles:
			f.append("`elements.depart` et `elements.cible` doivent être des salles")
		trans = sol.get("transitions") or {}
		for s, t in trans.items():
			for a, dest in (t or {}).items():
				if s not in salles or dest not in salles or a not in arches_de(doc, s):
					f.append(f"`solution.transitions.{s}.{a}` : salle ou arche inconnue")
		# La cible est-elle ATTEIGNABLE depuis le départ ?
		vues, pile = {el.get("depart")}, [el.get("depart")]
		while pile:
			s = pile.pop()
			for a in arches_de(doc, s):
				dest = (trans.get(s) or {}).get(a, el.get("depart"))
				if dest not in vues:
					vues.add(dest)
					pile.append(dest)
		if el.get("cible") not in vues:
			f.append("la cible n'est atteignable depuis le départ par aucun chemin : insoluble")
	elif famille == "association":
		paires = sol.get("paires") or {}
		g, d = set(_ids(el.get("gauche"))), set(_ids(el.get("droite")))
		if not paires or not set(paires) <= g or not set(paires.values()) <= d:
			f.append("`solution.paires` cite un élément absent")
		if int(sol.get("seuil", len(paires))) > len(paires):
			f.append("`solution.seuil` dépasse le nombre de paires : insoluble")
	elif famille == "placement":
		pl = sol.get("placement") or {}
		if not pl or not set(pl) <= set(_ids(el.get("emplacements"))) or not set(pl.values()) <= set(_ids(el.get("symboles"))):
			f.append("`solution.placement` cite un emplacement ou un symbole absent")
	elif famille == "reseau":
		noeuds = set(_ids(el.get("noeuds")))
		toutes = _liste(el.get("liaisons")) + _liste(sol.get("liaisons_cachees"))
		for d in _doublons([l.get("id") for l in toutes]):
			f.append(f"liaison `{d}` en double (visible et cachée ?)")
		for l in toutes:
			if l.get("a") not in noeuds or l.get("b") not in noeuds:
				f.append(f"liaison `{l.get('id')}` : extrémité inconnue")
		ids = {l.get("id") for l in toutes}
		if not set(sol.get("actives") or []) <= ids or not sol.get("actives"):
			f.append("`solution.actives` cite une liaison absente")
		if not set(sol.get("ancrees") or []) <= set(sol.get("actives") or []):
			f.append("`solution.ancrees` doit être incluse dans `solution.actives`")
	zones_cles = set(_ids(el.get("indices"))) | set(_ids(el.get("pieces"))) | set(_ids(el.get("arches"))) \
		| set(_ids(el.get("emplacements"))) | set(_ids(el.get("noeuds"))) | set(_ids(el.get("conclusions")))
	for z in _liste(doc.get("zones")):
		if z.get("cle") not in zones_cles:
			f.append(f"zone `{z.get('cle')}` : ne désigne aucun élément de l'énigme")
	for c in _liste(doc.get("commentaires")):
		q = c.get("quand")
		if not (q in QUAND_SIMPLES or (isinstance(q, str) and q.startswith(QUAND_PREFIXES))):
			f.append(f"commentaire : moment `{q}` inconnu")
		qui = c.get("qui") or {}
		if not (isinstance(qui, dict) and len(qui) == 1 and ("protege" in qui or "vocation" in qui)):
			f.append("commentaire : `qui` doit être `{protege: prénom}` ou `{vocation: …}`")
	for p in doc.get("prerequis") or []:
		if not (isinstance(p, str) and p.startswith("enigme:")) or p == eid:
			f.append(f"prérequis `{p}` invalide")
	return f


def cycles_prerequis(docs) -> list:
	"""Chaînes de prérequis CIRCULAIRES entre énigmes (A attend B qui attend A) : la quête serait
	bloquée pour toujours. → liste de cycles (chacun une liste d'ids) ; vide = aucun blocage.
	Un prérequis vers une énigme absente du lot est aussi un blocage, signalé en cycle d'un."""
	graphe = {d.get("_id"): [p for p in (d.get("prerequis") or []) if isinstance(p, str)]
			  for d in docs or [] if isinstance(d, dict)}
	cycles, couleur = [], {}

	def visiter(n, chemin):
		couleur[n] = 1
		for p in graphe.get(n, []):
			if p not in graphe:
				cycles.append([n, p])
			elif couleur.get(p) == 1:
				cycles.append(chemin[chemin.index(p):] + [p] if p in chemin else [n, p])
			elif not couleur.get(p):
				visiter(p, chemin + [p])
		couleur[n] = 2

	for n in graphe:
		if not couleur.get(n):
			visiter(n, [n])
	return cycles

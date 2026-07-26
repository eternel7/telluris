# utils/lint_dialogues.py
# Contrôle de cohérence des arbres de dialogue PNJ — logique PURE (aucune DB, aucun I/O),
# partagée par le script `dev/lint_dialogues.py` et le bouton « Vérifier » de la page
# d'import `/admin` (même précédent que `utils/xlsx.py`, partagé par l'export bestiaire et
# l'export du tableau admin).
#
# POURQUOI : un dialogue est de la DONNÉE, jamais typée ni exécutée à l'import. Une
# référence morte (`next` vers un nœud inexistant, `services.transport.noeuds.accepte`
# pointant à côté) ou une condition mal orthographiée ne se voit qu'en JOUANT la branche —
# et une branche conditionnée qui ne s'affiche jamais est indiscernable d'un tirage
# malheureux. Ce module rend ces fautes visibles AVANT l'import.
#
# Les listes de référence ci-dessous décrivent ce que le moteur consomme réellement
# (utils/pnj.py, routers/pnj.py) : les tenir à jour quand un service ou un flag est ajouté.

import re

from utils import acces

# ── Ce que le moteur connaît ─────────────────────────────────────────────────────

# Placeholders substituables : {prenom}/{cout} (utils/pnj._substituer) + tout ce que le
# router pose dans `contexte["placeholders"]` (routers/pnj.py).
PLACEHOLDERS_CONNUS = {
	"prenom", "cout",
	# Noms de PERSONNES (jamais d'enseigne) — cf. règle « aucun nom en dur ».
	"pnj", "destinataire", "donneur",
	# Quêtes de transport : enseignes des deux bouts + descriptif de la cargaison.
	"destination", "expediteur", "direction", "repere",
	"colis", "poids", "delai", "xp", "prime",
	# Quêtes de chasse / rang de guilde.
	"espece", "lieu", "rang", "rang_vise",
	# Accès conditionné à un lieu (PNJ gardien) : le label du lieu gardé.
	"portail",
}

# Clés de `condition` : deux formes structurées, tout le reste est traité comme un FLAG
# booléen du contexte (utils/pnj.condition_ok). Un flag inconnu vaut False → le choix
# disparaît pour toujours, silencieusement : c'est la faute la plus coûteuse à diagnostiquer.
CONDITIONS_STRUCTUREES = {"relation_min", "intro_raison"}
FLAGS_CONNUS = {
	"transport_offert", "transport_a_livrer", "transport_a_rapporter",
	"transport_en_cours", "transport_accompli", "transport_mefiance",
	"rang_offert", "rang_a_rapporter", "rang_max",
	"acces_ouvrable", "acces_refuse", "acces_ouvert",
}

# Nœuds de résultat que le ROUTER va chercher par leur clé. Les absents laissent le
# dialogue se fermer sans un mot à l'issue de l'action.
# ⚠️ `propose` / `infos` / `mefiance` n'y figurent pas volontairement : aucun code ne les
# lit, ils sont atteints par un `next` ordinaire — les déclarer reste utile en
# documentation, mais leur absence n'est pas une faute.
NOEUDS_REQUIS = {
	"soin": {"fait", "sans_fonds", "inutile"},
	"don":  {"fait", "sans_fonds", "trop_charge"},
	"rang": {"accepte", "rapporte"},
	# `deja` reste optionnel — un gardien peut ne pas reconnaître les habitués.
	"acces": {"ouvre", "refus"},
}

# Le transport a DEUX rôles, et presque aucun PNJ ne tient les deux :
#  · DONNEUR — il confie la cargaison. Tout PNJ peut l'être (une course écrite dans
#    `services.transport.offre` n'exige pas d'être un magasin).
#  · DESTINATAIRE — il en prend livraison. Seul un magasin l'est (`lieu_buys` suppose des
#    recettes), donc en pratique un tenancier générique `pnj:marchand_*`.
# Exiger les nœuds des deux rôles de tout le monde ferait crier au défaut sur un donneur
# parfaitement correct (le réceptionniste de guilde ne reçoit jamais de colis).
TRANSPORT_DONNEUR = {"accepte", "trop_charge"}
TRANSPORT_DESTINATAIRE = {"livre", "incomplet"}
TRANSPORT_RETOUR = {"rapporte"}   # course `retour` : le donneur solde au retour

# Actions qui n'ont de sens QUE si quelque chose est en cours, et le flag qui l'atteste.
# Sans lui, le PNJ propose « Je vous apporte une livraison » à un joueur qui n'a rien à
# livrer : le choix s'affiche toujours, l'action échoue (ou ne fait rien) à l'exécution.
# `accepter` n'y figure pas : on l'atteint par le nœud d'offre, lui-même déjà conditionné.
ACTIONS_A_CONDITIONNER = {
	("transport", "livrer"):    "transport_a_livrer",
	("transport", "rapporter"): "transport_a_rapporter",
	("rang", "rapporter"):      "rang_a_rapporter",
	("acces", "passer"):        "acces_ouvrable",
}

# Sentinelle de fin : `routers/pnj.py` fait `if not suivant or suivant == "fin"` → nœud
# None → le panneau se ferme. Ce n'est donc PAS un nœud à déclarer.
FIN = "fin"

# Un doc `pnj:marchand_*` est GÉNÉRIQUE : partagé par toutes les boutiques du métier, et
# chaque lieu rebaptise son tenancier via `nom` dans son entrée `pnj`. Un nom écrit dans
# son texte mentirait. Les mots ci-dessous ne sont pas des noms propres (« Le vieux
# Renaud » → seul « Renaud » compte).
MOTS_NON_SIGNIFIANTS = {
	"le", "la", "les", "un", "une", "des", "du", "de", "dame", "maitre", "maître",
	"frere", "frère", "vieux", "vieille", "ombre", "sieur", "messire",
}


def _noms_propres(nom: str) -> set:
	"""Mots significatifs d'un nom de tenancier, pour la détection de nom en dur."""
	return {m for m in re.findall(r"[A-Za-zÀ-ÿ]+", nom or "")
			if len(m) > 3 and m.lower() not in MOTS_NON_SIGNIFIANTS}


def _textes_du_noeud(noeud: dict) -> list:
	"""Tout ce qu'un joueur peut LIRE dans un nœud : les deux variantes de texte et les
	libellés des choix (un placeholder fautif dans un label est tout aussi visible)."""
	textes = [noeud.get("texte", ""), noeud.get("texte_gratuit", "")]
	textes += [c.get("label", "") for c in noeud.get("choix") or []]
	return [t for t in textes if t]


def _entrees(doc: dict, noeuds: dict) -> set:
	"""Points d'entrée de l'arbre : le nœud de départ ET tous les nœuds de service (le
	router y saute directement après une action — ils ne sont atteints par aucun `next`)."""
	depart = ((doc.get("dialogue") or {}).get("noeud_depart"))
	entrees = {depart} if depart else set()
	for conf in (doc.get("services") or {}).values():
		entrees |= {nid for nid in (conf.get("noeuds") or {}).values() if nid}
	return {e for e in entrees if e in noeuds}


def _atteignables(noeuds: dict, entrees: set) -> set:
	"""Fermeture transitive des `next` depuis les points d'entrée."""
	vus, pile = set(), list(entrees)
	while pile:
		nid = pile.pop()
		if nid in vus:
			continue
		vus.add(nid)
		for choix in noeuds[nid].get("choix") or []:
			cible = choix.get("next")
			if cible and cible in noeuds:
				pile.append(cible)
	return vus


def analyser_doc(doc: dict) -> list:
	"""Anomalies d'UN document. Renvoie une liste de
	`{doc_id, niveau: "erreur"|"avertissement", noeud, message}`, vide si tout va bien.
	Un doc sans bloc `dialogue` NI bloc `acces` n'est pas concerné (ce n'est pas une
	faute : la plupart des documents du jeu n'ont ni l'un ni l'autre) — l'appelant le
	compte alors comme « ignoré ». Un `lieu:*` gardé porte `acces` mais typiquement
	AUCUN `dialogue` (c'est son gardien qui en a un) : il est quand même analysé, pour
	le seul contrôle qui le concerne (`acces.conditions_invalides`)."""
	doc_id = doc.get("_id", "?")
	trouvailles = []

	def signaler(niveau, message, noeud=None):
		trouvailles.append({"doc_id": doc_id, "niveau": niveau,
							"noeud": noeud, "message": message})

	def erreur(message, noeud=None):
		signaler("erreur", message, noeud)

	def avertir(message, noeud=None):
		signaler("avertissement", message, noeud)

	# Barrière d'accès (utils/acces.py) : une clé de condition hors vocabulaire connu
	# refuserait TOUJOURS l'accès (fail-closed, silencieusement) — c'est le typo que le
	# moteur ne peut pas rattraper lui-même. Un `lieu:*` gardé n'a le plus souvent AUCUN
	# `dialogue` (c'est son gardien qui en porte un) : ce contrôle doit donc s'exécuter
	# même quand le doc n'a rien d'autre à analyser.
	for cle in acces.conditions_invalides(doc):
		erreur(f"acces.conditions : clé `{cle}` inconnue du vocabulaire — fail-closed, "
			   f"ce lieu refusera TOUJOURS l'accès.")

	dialogue = doc.get("dialogue") or {}
	if not dialogue:
		return trouvailles

	noeuds = dialogue.get("noeuds") or {}
	depart = dialogue.get("noeud_depart")

	# NB : on ne signale PAS un `_rev` présent. `admin_import_bulk` réattache toujours le
	# `_rev` courant avant d'écrire, un `_rev` périmé dans le fichier est donc sans effet —
	# et tous les exports en portent un. Le signaler noierait les vraies fautes.
	if not noeuds:
		erreur("`dialogue.noeuds` est vide : parler à ce PNJ n'affichera rien.")
		return trouvailles
	if not depart:
		erreur("`dialogue.noeud_depart` absent.")
	elif depart not in noeuds:
		erreur(f"`noeud_depart` désigne `{depart}`, qui n'existe pas.")

	# Un dialogue générique ne doit citer aucun nom : le lieu rebaptise son tenancier.
	noms_interdits = _noms_propres(doc.get("nom")) if doc_id.startswith("pnj:marchand_") else set()

	# Flags qui gardent l'ACCÈS à chaque nœud : ceux de ses propres choix, plus ceux des
	# choix qui y mènent (un nœud atteint par « Vous avez une livraison ? » est déjà gardé,
	# ses choix n'ont pas à répéter la condition).
	gardes = {nid: set() for nid in noeuds}
	for nid, noeud in noeuds.items():
		for choix in noeud.get("choix") or []:
			cles = set(choix.get("condition") or {})
			gardes[nid] |= cles
			cible = choix.get("next")
			if cible in gardes:
				gardes[cible] |= cles

	for nid, noeud in noeuds.items():
		choix_list = noeud.get("choix") or []
		if not choix_list:
			erreur("aucun choix : le joueur ne peut ni répondre ni sortir.", nid)

		vus_ids = set()
		for choix in choix_list:
			cid = choix.get("id")
			if not cid:
				erreur("un choix sans `id` : il est ignoré au rendu.", nid)
				continue
			if cid in vus_ids:
				# `choix_valide` renvoie le PREMIER trouvé : le doublon est inaccessible.
				erreur(f"deux choix portent l'id `{cid}` — le second ne sera jamais joué.", nid)
			vus_ids.add(cid)

			cible = choix.get("next")
			if cible and cible != FIN and cible not in noeuds:
				erreur(f"choix `{cid}` mène à `{cible}`, qui n'existe pas.", nid)
			if not cible and not choix.get("action"):
				avertir(f"choix `{cid}` n'a ni `next` ni `action` : il ferme le dialogue "
						f"(comme `{FIN}`). L'écrire explicitement lèverait le doute.", nid)

			conditions = set(choix.get("condition") or {})
			for cle in conditions:
				if cle in CONDITIONS_STRUCTUREES:
					continue
				if cle not in FLAGS_CONNUS:
					erreur(f"choix `{cid}` : condition `{cle}` inconnue du moteur. Un flag "
						   f"absent vaut False → ce choix ne s'affichera JAMAIS.", nid)

			action = choix.get("action") or {}
			attendu = ACTIONS_A_CONDITIONNER.get((action.get("service"), action.get("op")))
			if attendu and attendu not in (conditions | gardes.get(nid, set())):
				erreur(f"choix `{cid}` déclenche `{action['service']}/{action['op']}` sans "
					   f"condition `{attendu}` : il sera proposé au joueur même quand il n'a "
					   f"rien à remettre.", nid)

		for texte in _textes_du_noeud(noeud):
			for cle in re.findall(r"\{(\w+)\}", texte):
				if cle not in PLACEHOLDERS_CONNUS:
					erreur(f"placeholder `{{{cle}}}` inconnu : il restera affiché tel quel.", nid)
			for nom in noms_interdits:
				if re.search(rf"\b{re.escape(nom)}\b", texte):
					erreur(f"le nom « {nom} » est écrit en dur. Ce document est générique et "
						   f"chaque lieu renomme son tenancier : utiliser `{{pnj}}`.", nid)

	# Nœuds de service : déclarés mais absents (référence morte), ou manquants alors que le
	# router ira les chercher.
	for service, conf in (doc.get("services") or {}).items():
		declares = (conf or {}).get("noeuds") or {}
		for cle, nid in declares.items():
			if nid not in noeuds:
				erreur(f"`services.{service}.noeuds.{cle}` désigne `{nid}`, qui n'existe pas "
					   f"dans le dialogue.")
		if service == "transport":
			attendus = set(TRANSPORT_DONNEUR)
			offre = (conf or {}).get("offre")
			if offre and offre.get("retour"):
				attendus |= TRANSPORT_RETOUR
			# Destinataire : réservé aux tenanciers de magasin (cf. commentaire plus haut).
			if doc_id.startswith("pnj:marchand_"):
				attendus |= TRANSPORT_DESTINATAIRE
		else:
			attendus = NOEUDS_REQUIS.get(service, set())
		for cle in attendus - set(declares):
			avertir(f"`services.{service}.noeuds` ne déclare pas `{cle}` : après cette action "
					f"le dialogue se fermera sans réponse.")

	for nid in set(noeuds) - _atteignables(noeuds, _entrees(doc, noeuds)):
		erreur("nœud inatteignable : aucun `next` ni service n'y mène (texte mort).", nid)

	return trouvailles


def analyser(payload) -> dict:
	"""Analyse un payload d'import complet — les deux formats acceptés par
	`/admin/import-bulk` (tableau d'objets, ou `{"docs": [...]}`).

	Renvoie `{analyses, ignores, erreurs, avertissements, trouvailles[]}`. `ignores` compte
	les documents sans bloc `dialogue` : la plupart des docs du jeu (items, lieux, espèces)
	n'en ont pas, ce n'est pas une anomalie."""
	if isinstance(payload, dict) and isinstance(payload.get("docs"), list):
		docs = payload["docs"]
	elif isinstance(payload, list):
		docs = payload
	elif isinstance(payload, dict):
		docs = [payload]          # un document seul, collé tel quel
	else:
		return {"analyses": 0, "ignores": 0, "erreurs": 0, "avertissements": 0,
				"trouvailles": [{"doc_id": "?", "niveau": "erreur", "noeud": None,
								 "message": "Format non reconnu : attendu un tableau "
											"d'objets ou {\"docs\": [...]}."}]}

	trouvailles, analyses, ignores = [], 0, 0
	for doc in docs:
		if not isinstance(doc, dict):
			ignores += 1
			continue
		if not (doc.get("dialogue") or {}) and not (doc.get("acces") or {}):
			ignores += 1
			continue
		analyses += 1
		trouvailles.extend(analyser_doc(doc))

	return {
		"analyses": analyses,
		"ignores": ignores,
		"erreurs": sum(1 for t in trouvailles if t["niveau"] == "erreur"),
		"avertissements": sum(1 for t in trouvailles if t["niveau"] == "avertissement"),
		"trouvailles": trouvailles,
	}

# utils/pnj.py
# PNJ de lieu avec dialogues à choix + services. Un doc `lieu:*` porte un champ `pnj`
# (liste d'entrées {character:"pnj:xxx", portrait, image?, probabilite, description}) ;
# le tirage de présence se fait à l'ENTRÉE dans le lieu et est persisté en champ
# transitoire character["pnj_present"] = {"lieu": id, "character": id|None} — un refresh
# ne re-tire jamais (character:None = « tirage fait, PNJ absent »).
#
# Le doc PNJ (`type:"pnj"`) porte :
# - `dialogue` : {"noeud_depart": id, "noeud_attente"?: id,
#                 "noeuds": {id: {texte, texte_gratuit?, delai_min?, choix:[...]}}}
#   Chaque choix = {id, label, next?, action:{"service":"soin"}?, condition?}. Les choix
#   sont FILTRÉS côté serveur par condition (le client n'adresse que des choix visibles,
#   par `choix_id`). Conditions v1 : {"relation_min": {"lieux":[...], "seuil": n}} (OU
#   logique sur les lieux) et {"intro_raison": "<id>"}.
#   `delai_min` (secondes, sur un NŒUD) ferme le dialogue de ce PNJ le temps voulu, et
#   `noeud_attente` (sur la RACINE) est ce qu'il répond entre-temps — cf. section
#   « Délai de réouverture ».
#   `relation` (sur un NŒUD) = {delta, lieu?, unique?} : le RENDRE fait bouger la réputation
#   du joueur, UNE SEULE FOIS ; `relation_reinit` (sur un autre nœud) rouvre ce versement —
#   cf. section « Récompense de relation portée par un nœud ».
# - `services.soin` : {cout_cuivre, fraction_pv, gratuit_si:{lieux, seuil, fraction_pv},
#   noeuds:{fait, sans_fonds, inutile}} — data-driven, seuil par défaut en world-var
#   PNJ_REPUTATION_SEUIL.
# - `services.don` : {item, quantite, cout_cuivre, gratuit_si:{lieux, seuil},
#   noeuds:{fait, sans_fonds, trop_charge}} — remise d'un objet (ex. eau bénite),
#   gratuit si bonne réputation ; contrôle de charge côté router.
# - `services.transport` : {noeuds:{propose, infos, accepte, trop_charge, livre, incomplet},
#   offre?:{id, destination, cargaison, duree, proba, unique, titre, description, recompenses}}
#   — quête de course (utils/transport.py). Sans `offre`, la course est TIRÉE AU HASARD et le
#   donneur doit être un magasin (cas des tenanciers) ; AVEC `offre`, elle est ÉCRITE et
#   N'IMPORTE QUEL PNJ peut la confier, magasin ou non (ex. le réceptionniste de la guilde et
#   sa mission d'initiation). Les conditions `transport_offert` / `transport_a_livrer` /
#   `transport_en_cours` / `transport_accompli` sont des FLAGS posés par le router.
# Placeholders substitués serveur dans texte/label : {prenom}, {cout}, plus toute clé de
# `contexte["placeholders"]` posée par le router — {pnj} (le nom EFFECTIF de celui à qui l'on
# parle, cf. `nom_effectif`), {destinataire} / {donneur} (les PNJ des deux bouts d'une course),
# {destination}, {direction}, {repere}, {colis}, {poids}, {delai}, {xp}, {prime}, {expediteur},
# {attente} (minutes restant avant qu'un dialogue en délai puisse rouvrir).
# ⚠️ RÈGLE : un dialogue ne cite JAMAIS un nom de PNJ en dur. Les docs `pnj:marchand_*` sont
# GÉNÉRIQUES (un par catégorie, partagé par toutes les boutiques) et chaque lieu peut renommer
# son tenancier via `nom` dans son entrée `pnj` — un nom écrit dans un texte mentirait.
#
# Les magasins ne portent pas de champ `pnj` : leur tenancier est dérivé de leur catégorie
# par `marchand_fn` (utils/transport.entree_marchand), injecté dans la résolution de présence.
#
# Logique pure (DB injectée : relation_value_fn), mute sans save — l'endpoint persiste.

import random

from models import character_stats


# ---------------------------------------------------------------------------
# Présence dans le lieu
# ---------------------------------------------------------------------------

def entrees_pnj(lieu_doc: dict, marchand_fn=None, condition_fn=None) -> list:
	"""Entrées `pnj` effectives du lieu : le champ explicite s'il existe, sinon le tenancier
	implicite fourni par `marchand_fn(lieu_doc)` (les magasins ne portent pas de champ `pnj`
	— leur tenancier est dérivé de leur catégorie, cf. utils/transport.entree_marchand).
	
	CHOKEPOINT de la présence : le filtre `conditions` est posé ICI et nulle part ailleurs,
	si bien que le tirage, la relecture du tirage persisté et le nommage à distance en
	héritent d'un coup. Une entrée peut porter **`conditions: [...]`** — le vocabulaire des
	barrières de lieu (`utils/acces.py`), évalué par le `condition_fn` INJECTÉ : ce module
	n'importe que `random` + `character_stats`, y brancher `utils.acces` y tirerait
	characters + recrutement (même arbitrage que `quetes_reussies`, injecté lui aussi).
	
	⚠️ FAIL-CLOSED : une entrée conditionnée est écartée quand aucun `condition_fn` n'est
	fourni. Un appelant qui l'oublierait montrerait sinon le PNJ dans TOUS les états du
	monde, en silence — la faute exactement inverse de celle qu'on veut. Corollaire
	assumé : `nom_pnj_du_lieu` (qui nomme le tenancier d'un lieu où l'on n'est pas, sans
	personnage sous la main) ne nomme jamais un PNJ conditionné, et passe au suivant.
	
	⚠️ Champ absent ⇒ entrée toujours présente : aucune migration."""
	explicites = (lieu_doc or {}).get("pnj") or []
	if explicites:
		return [e for e in explicites if _entree_visible(e, condition_fn)]
	implicite = marchand_fn(lieu_doc) if marchand_fn else None
	return [implicite] if implicite else []


def _entree_visible(entree, condition_fn) -> bool:
	"""L'entrée est-elle offerte dans l'état du monde courant ? Sans `conditions`, toujours."""
	if not isinstance(entree, dict):
		return False
	conditions = entree.get("conditions")
	if not conditions:
		return True
	return bool(condition_fn and condition_fn(conditions))


def tirer_pnj_present(lieu_doc: dict, rand_fn=random.random, marchand_fn=None,
					 condition_fn=None) -> str | None:
	"""Tire le PNJ présent parmi les entrées `pnj` du lieu : la première entrée dont
	`rand_fn() < probabilite` gagne (ordre de la liste = priorité). None si aucun."""
	for entree in entrees_pnj(lieu_doc, marchand_fn, condition_fn):
		pnj_id = entree.get("character")
		if not pnj_id:
			continue
		try:
			proba = float(entree.get("probabilite", 1.0))
		except (TypeError, ValueError):
			proba = 1.0
		if rand_fn() < proba:
			return pnj_id
	return None


def poser_pnj_present(character: dict, lieu_doc: dict, rand_fn=random.random,
					  marchand_fn=None, condition_fn=None) -> bool:
	"""Pose le champ transitoire `pnj_present` si le personnage vient d'entrer dans ce
	lieu (mute sans save). No-op si le tirage a déjà été fait pour ce lieu (refresh
	stable). Renvoie True si le champ a changé (l'appelant décide de sauvegarder)."""
	lieu_id = (lieu_doc or {}).get("_id")
	if not lieu_id:
		return False
	present = character.get("pnj_present") or {}
	if present.get("lieu") == lieu_id:
		return False
	character["pnj_present"] = {
		"lieu": lieu_id,
		"character": tirer_pnj_present(lieu_doc, rand_fn, marchand_fn, condition_fn),
	}
	return True


def entree_pnj_active(character: dict, lieu_doc: dict, marchand_fn=None,
					  condition_fn=None) -> dict | None:
	"""L'entrée `pnj` du lieu correspondant au tirage persisté, ou None (tirage périmé,
	PNJ absent, lieu sans pnj, entrée retirée de la donnée depuis le tirage).
	
	⚠️ Le filtre `conditions` joue ICI AUSSI, et pas seulement au tirage : `pnj_present` est
	un champ TRANSITOIRE persisté, et `poser_pnj_present` est un no-op tant qu'on reste dans
	le lieu. Un PNJ tiré alors que sa condition tenait continuerait donc de parler après
	qu'elle a cessé de tenir. La condition est autoritative à la LECTURE."""
	present = (character or {}).get("pnj_present") or {}
	lieu_id = (lieu_doc or {}).get("_id")
	pnj_id = present.get("character")
	if not lieu_id or present.get("lieu") != lieu_id or not pnj_id:
		return None
	for entree in entrees_pnj(lieu_doc, marchand_fn, condition_fn):
		if entree.get("character") == pnj_id:
			return entree
	return None


def nom_effectif(entree: dict, pnj_doc: dict) -> str:
	"""Nom sous lequel CE lieu présente le PNJ : l'entrée du lieu prime (une boutique nomme son
	tenancier — « Lucinda Mortecroix » à La Flèche d'Argent), repli sur le doc générique.

	⚠️ Source unique du nom affiché : un dialogue de PNJ **générique** ne doit JAMAIS citer un
	nom en dur (le doc est partagé par toutes les boutiques de la catégorie, et chacune peut
	renommer son tenancier) — il utilise le placeholder `{pnj}`, posé depuis ici par le router."""
	return (entree or {}).get("nom") or (pnj_doc or {}).get("nom", "???")


def nom_pnj_du_lieu(lieu_doc: dict, get_doc_fn, marchand_fn=None) -> str | None:
	"""Nom effectif du PNJ d'un lieu qu'on ne visite PAS (le destinataire d'une livraison, le
	donneur d'une course) : on ne peut pas s'appuyer sur le tirage de présence, on prend donc
	la PREMIÈRE entrée du lieu — l'ordre de la liste vaut priorité, comme dans
	`tirer_pnj_present`. None si personne ne tient ce lieu."""
	for entree in entrees_pnj(lieu_doc, marchand_fn):
		pnj_id = entree.get("character")
		if not pnj_id:
			continue
		return nom_effectif(entree, get_doc_fn(pnj_id) or {})
	return None


def pnj_payload(entree: dict, pnj_doc: dict) -> dict:
	"""Payload de rendu du PNJ présent (template /play + panneau de dialogue).
	Nom/portrait/description : l'entrée du lieu prime (identité propre à la boutique), repli
	doc PNJ. C'est ce qui permet de donner un tenancier NOMMÉ à un magasin tout en réutilisant
	le doc — et donc le dialogue — générique de sa catégorie."""
	return {
		"character": (pnj_doc or {}).get("_id") or entree.get("character"),
		"nom": nom_effectif(entree, pnj_doc),
		"portrait": entree.get("portrait") or (pnj_doc or {}).get("portrait"),
		"image_lieu": entree.get("image"),
		"description": entree.get("description") or (pnj_doc or {}).get("description", ""),
	}


# ---------------------------------------------------------------------------
# Contexte & conditions de dialogue
# ---------------------------------------------------------------------------

def _lieux_cites(pnj_doc: dict) -> set:
	"""Tous les lieux référencés par les conditions de l'arbre + gratuit_si des services
	(pour ne résoudre que les relations utiles)."""
	lieux = set()
	for service in ((pnj_doc or {}).get("services") or {}).values():
		for lid in ((service or {}).get("gratuit_si") or {}).get("lieux") or []:
			lieux.add(lid)
	noeuds = (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {})
	for noeud in noeuds.values():
		for choix in (noeud or {}).get("choix") or []:
			cond = (choix or {}).get("condition") or {}
			for lid in (cond.get("relation_min") or {}).get("lieux") or []:
				lieux.add(lid)
	return lieux


def contexte_dialogue(character: dict, pnj_doc: dict, relation_value_fn,
					  flags: dict | None = None, placeholders: dict | None = None,
					  quetes_reussies: set | None = None,
					  quetes_actives: set | None = None) -> dict:
	"""Contexte d'évaluation des conditions : relations du personnage avec les lieux
	cités par l'arbre/les services (`relation_value_fn(lieu_id) -> int`, injectée par le
	router) + raison d'intro éventuelle. Ajoute aussi `prenom` pour les placeholders.

	`flags` = booléens d'état supplémentaires que les conditions peuvent tester (ex.
	`transport_offert`, `transport_a_livrer`) ; `placeholders` = valeurs à substituer dans
	les textes (ex. `{destination}`, `{direction}`) ; `quetes_reussies` / `quetes_actives` =
	les ids des quêtes menées à bien et de celles EN COURS, que testent les conditions
	`quete_reussie` et `quete_active`. Tous sont fournis par le router, qui seul connaît le
	lieu courant et l'état des quêtes.

	⚠️ Les deux ensembles de quêtes sont INJECTÉS, jamais calculés ici (le router appelle
	`quetes.quetes_reussies` / `quetes.quetes_actives_ids`) : ce module n'importe que `random`
	et `models.character_stats`, et y brancher `utils.quetes` tirerait bois/marche/
	recrutement/db dans un module minimal. Même arbitrage que le commentaire d'import de
	`utils/acces.py`, et même seam que `relation_value_fn`. ⚠️ Paramètres en DERNIER avec
	défaut : `contexte_dialogue` est appelé positionnellement par les tests existants."""
	relations = {}
	for lid in _lieux_cites(pnj_doc):
		try:
			relations[lid] = int(relation_value_fn(lid))
		except (TypeError, ValueError):
			relations[lid] = 0
	return {
		"relations": relations,
		"intro_raison": ((character or {}).get("intro") or {}).get("raison"),
		"prenom": (character or {}).get("prenom", ""),
		"flags": dict(flags or {}),
		"placeholders": dict(placeholders or {}),
		"quetes_reussies": set(quetes_reussies or ()),
		"quetes_actives": set(quetes_actives or ()),
	}


# Clés de `condition` traitées comme des FORMES STRUCTURÉES ; tout le reste est un flag
# booléen du contexte. ⚠️ `utils/lint_dialogues.CONDITIONS_STRUCTUREES` doit rester le miroir
# exact de cet ensemble (épinglé par un test) : une clé structurée absente de la liste du
# linter serait signalée comme flag inconnu, et l'inverse ferait passer une faute en silence.
CONDITIONS_STRUCTUREES = frozenset({
	"relation_min", "intro_raison", "quete_reussie", "quete_active"})

# Les deux conditions qui nomment une QUÊTE : même forme `{id, attendu}`, même sémantique
# fail-closed, seul l'ensemble consulté change — d'où UN prédicat partagé plutôt que deux
# copies qui finiraient par diverger sur le traitement d'un filtre mal formé.
# ⚠️ Elles sont COMPLÉMENTAIRES et non contraires : une quête jamais acceptée est absente des
# DEUX. C'est leur CONJONCTION en `attendu: false` qui dit « tant qu'on ne m'a pas encore
# confié ceci » — `quete_reussie` seul laisserait le choix visible pendant toute la mission,
# `quete_active` seul le laisserait revenir une fois la mission rendue.
CONDITIONS_QUETE = {
	"quete_reussie": "quetes_reussies",
	"quete_active": "quetes_actives",
}


def _quete_nommee_ok(filtre, ids) -> bool:
	"""Prédicat PARTAGÉ de `quete_reussie` et `quete_active`, toutes deux de la forme
	`{"id": "quete:xxx", "attendu": true|false}`.

	Elles testent une quête NOMMÉE, et c'est ce qui les distingue des flags
	`escorte_accomplie` / `transport_accompli` / `escorte_en_cours` : ceux-là sont dérivés de
	l'offre portée par le PNJ à qui l'on PARLE, donc toujours faux chez un tiers. Ici
	n'importe quel PNJ peut réagir à n'importe quelle quête — c'est ce qui permet à deux
	paladins de ne parler d'une rescapée qu'une fois qu'un autre PNJ l'a fait ramener, et à
	un réceptionniste de cesser d'annoncer une mission que son maître a déjà confiée.

	`attendu` absent ⇒ True. La forme `attendu: false` est le seul moyen d'exprimer une
	NÉGATION dans une condition de dialogue — `condition_ok` n'en a pas pour les formes
	structurées, et le couple de flags complémentaires (`acces_libere`/`acces_menace`) ne peut
	pas porter d'id.

	⚠️ FAIL-CLOSED : un filtre mal formé (pas un dict, `id` absent ou non textuel) masque le
	choix au lieu de l'afficher. Même arbitrage que pour un flag inconnu, et pour la même
	raison : le garde-fou contre le contenu muet est le LINTER, pas une permissivité du
	moteur — un choix qui s'affiche à tort révélerait l'intrigue, un choix masqué se voit."""
	if not isinstance(filtre, dict):
		return False
	quete_id = filtre.get("id")
	if not quete_id or not isinstance(quete_id, str):
		return False
	attendu = filtre.get("attendu", True)
	return (quete_id in (ids or set())) is bool(attendu)


def condition_ok(condition: dict | None, contexte: dict) -> bool:
	"""Évalue une condition de choix. Sans condition → True. `relation_min` = OU logique
	sur les lieux (une relation ≥ seuil suffit) ; `intro_raison` = égalité stricte ;
	`quete_reussie` / `quete_active` = état d'une quête NOMMÉE ; toute autre clé est un **flag
	booléen** du contexte (ex. `transport_offert`) — un flag absent vaut False, ce qui masque
	le choix."""
	if not condition:
		return True
	rel_min = condition.get("relation_min")
	if rel_min:
		seuil = int(rel_min.get("seuil", character_stats.PNJ_REPUTATION_SEUIL))
		relations = contexte.get("relations") or {}
		if not any(relations.get(lid, 0) >= seuil for lid in rel_min.get("lieux") or []):
			return False
	if "intro_raison" in condition:
		if contexte.get("intro_raison") != condition["intro_raison"]:
			return False
	for cle, source in CONDITIONS_QUETE.items():
		if cle in condition and not _quete_nommee_ok(condition[cle], contexte.get(source)):
			return False
	flags = contexte.get("flags") or {}
	for cle, attendu in condition.items():
		if cle in CONDITIONS_STRUCTUREES:
			continue
		if bool(flags.get(cle)) is not bool(attendu):
			return False
	return True


# ---------------------------------------------------------------------------
# Marques « ! » / « ? » d'un choix et d'un nœud
# ---------------------------------------------------------------------------
# Convention MMO : « ! » = une offre neuve t'attend ici, « ? » = une quête en cours attend
# une remise ou une rencontre. La marque d'un choix est DÉRIVÉE de sa condition, jamais
# authorée : un choix n'est affiché que si `condition_ok` passe, donc si sa condition cite
# `transport_offert`, c'est que le flag est vrai. Aucune donnée à éditer, aucune migration,
# et la marque ne peut pas mentir.

MARQUE_OFFRE = "!"
MARQUE_RAPPORT = "?"

# ⚠️ Sous-ensembles STRICTS de `lint_dialogues.FLAGS_CONNUS` (épinglé par un test) : un flag
# mal orthographié ici vaudrait False en silence et la marque ne s'afficherait jamais.
FLAGS_OFFRE = frozenset({
	"transport_offert", "escorte_offerte", "rang_offert",
	"commission_offerte", "acces_ouvrable",
})
FLAGS_RAPPORT = frozenset({
	"transport_a_livrer", "transport_a_rapporter",
	"rang_a_rapporter", "commission_a_rapporter", "acces_accompli",
})


def marque_de_condition(condition: dict | None) -> str | None:
	"""La marque d'un choix, dérivée de sa CONDITION. None quand rien n'attend le joueur.

	⚠️ `{"transport_offert": false}` est un VERROU, pas une offre : `condition_ok` compare
	`bool(flags.get(cle)) is not bool(attendu)`, donc une condition peut exiger l'ABSENCE du
	flag. Toute entrée dont `attendu` est faux est ignorée — sinon le nœud « rien à te
	proposer aujourd'hui » porterait un « ! ».

	⚠️ `relation_min` / `intro_raison` ne sont pas des flags : ils sortent d'eux-mêmes du
	test `cle in FLAGS_*`, mais leur `attendu` est un dict (donc truthy) — c'est bien
	l'appartenance aux deux frozensets qui décide, pas la véracité.

	`!` prime sur `?` : un choix qui offre ET attend un rapport annonce l'offre."""
	if not condition:
		return None
	rapport = False
	for cle, attendu in condition.items():
		if not attendu:
			continue
		if cle in FLAGS_OFFRE:
			return MARQUE_OFFRE
		if cle in FLAGS_RAPPORT:
			rapport = True
	return MARQUE_RAPPORT if rapport else None


def _choix_visibles(pnj_doc: dict, noeud_id: str, contexte: dict) -> list:
	"""Choix BRUTS (docs de donnée, pas la vue client) de ce nœud dont la condition passe.

	⚠️ Filtre UNIQUE, consommé par `noeud_client` ET `marque_noeud` : deux boucles de
	filtrage divergeraient un jour, et le badge cesserait de correspondre au contenu du
	panneau."""
	noeud = (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {}).get(noeud_id)
	if not noeud:
		return []
	return [
		choix for choix in (noeud.get("choix") or [])
		if choix.get("id") and condition_ok(choix.get("condition"), contexte)
	]


def marque_noeud(pnj_doc: dict, noeud_id: str, contexte: dict) -> str | None:
	"""La plus forte marque des choix VISIBLES de ce nœud — donc la marque du bouton 🗣 quand
	on la calcule sur le nœud de départ effectif.

	⚠️ Dérivée des CHOIX et non des flags bruts : `any(flags[f] for f in FLAGS_OFFRE)`
	promettrait un « ! » à un PNJ qui n'a aucune branche pour l'exploiter. La promesse tenue
	est « badge ! ⇒ en entrant, je trouve un choix ! ». Bénéfice gratuit : sous `delai_min`,
	`noeud_depart_effectif` sert `noeud_attente`, dont les choix ne portent rien → aucun badge."""
	marque = None
	for choix in _choix_visibles(pnj_doc, noeud_id, contexte):
		m = marque_de_condition(choix.get("condition"))
		if m == MARQUE_OFFRE:
			return MARQUE_OFFRE
		if m == MARQUE_RAPPORT:
			marque = MARQUE_RAPPORT
	return marque


# ---------------------------------------------------------------------------
# Navigation de l'arbre
# ---------------------------------------------------------------------------

# Espace insécable des guillemets français, posée AU RENDU et jamais dans la donnée : les
# docs `pnj:*` gardent des espaces ordinaires, lisibles et éditables à la main dans /admin.
#
# ⚠️ C'est le CARACTÈRE U+00A0, surtout pas l'entité `&nbsp;` : le texte du nœud est écrit
# par le client en **`textContent`** (`renderPnjNoeud`, play_town_telluris.html) — une entité
# HTML y serait affichée telle quelle, « &nbsp;Bonjour » en toutes lettres, sur les 1874
# guillemets du contenu. Les libellés de choix, eux, partent en `innerHTML` : le caractère
# est la seule forme qui rende correctement dans LES DEUX chemins.
#
# ⚠️ U+00A0 et non U+202F (l'espace fine que préconise l'Imprimerie nationale) : c'est
# l'équivalent exact de `&nbsp;`, et sa couverture est totale dans les polices. Changer de
# finesse ne demande que de toucher cette constante.
ESPACE_INSECABLE = " "


def _espaces_insecables(texte: str) -> str:
	"""Colle les guillemets français à ce qu'ils encadrent : `« ` → `« `, ` »` → ` »`.

	Empêche un guillemet de se retrouver seul en fin de ligne. ⚠️ IDEMPOTENT : après la
	première passe il ne reste plus d'espace ordinaire adjacente, donc rejouer ne fait rien
	— et un texte déjà saisi avec des insécables n'est pas touché. ⚠️ Appliqué APRÈS la
	substitution des placeholders : une enseigne ou un nom de PNJ injecté qui porterait des
	guillemets en bénéficie aussi (`« Impitoyable »`, les qualificatifs de chasse)."""
	if not texte:
		return texte
	return (texte
			.replace("« ", "«" + ESPACE_INSECABLE)
			.replace(" »", ESPACE_INSECABLE + "»"))


def _substituer(texte: str, contexte: dict, soin: dict | None) -> str:
	"""Placeholders {prenom} / {cout} (coût effectif du soin, « gratuit » si offert), plus
	toute clé de `contexte["placeholders"]` posée par le router (ex. {destination},
	{direction}, {repere}, {delai}, {xp} pour les quêtes de transport).

	CHOKEPOINT de rendu du texte de dialogue : le texte du nœud ET chaque libellé de choix y
	passent (`noeud_client`), et rien d'autre n'atteint le client. C'est donc ici, et nulle
	part ailleurs, que se pose la typographie."""
	if not texte:
		return ""
	texte = texte.replace("{prenom}", str(contexte.get("prenom", "")))
	if "{cout}" in texte:
		if soin and not soin.get("gratuit") and soin.get("cout_cuivre", 0) > 0:
			cout = f"{soin['cout_cuivre']} cuivre"
		else:
			cout = "gratuit"
		texte = texte.replace("{cout}", cout)
	for cle, valeur in (contexte.get("placeholders") or {}).items():
		texte = texte.replace("{" + str(cle) + "}", str(valeur))
	return _espaces_insecables(texte)


def noeud_client(pnj_doc: dict, noeud_id: str, contexte: dict, soin: dict | None = None) -> dict | None:
	"""Nœud prêt à afficher : texte (variante `texte_gratuit` si le soin est offert),
	placeholders substitués, choix filtrés par condition (id + label + marqueur action
	booléen + `marque` « ! »/« ? » dérivée de la condition — jamais l'arbre entier ni les
	conditions elles-mêmes). None si le nœud n'existe pas."""
	noeuds = (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {})
	noeud = noeuds.get(noeud_id)
	if not noeud:
		return None
	texte = noeud.get("texte", "")
	if soin and soin.get("gratuit") and noeud.get("texte_gratuit"):
		texte = noeud["texte_gratuit"]
	# ⚠️ Filtre PARTAGÉ avec `marque_noeud` : le badge du bouton 🗣 doit correspondre, choix
	# pour choix, à ce que le panneau affichera une fois ouvert.
	choix_visibles = [
		{
			"id": choix["id"],
			"label": _substituer(choix.get("label", ""), contexte, soin),
			"action": bool(choix.get("action")),
			# Verdict de la condition, jamais la condition elle-même (on n'expose pas l'arbre).
			"marque": marque_de_condition(choix.get("condition")),
		}
		for choix in _choix_visibles(pnj_doc, noeud_id, contexte)
	]
	return {
		"id": noeud_id,
		"texte": _substituer(texte, contexte, soin),
		"choix": choix_visibles,
	}


def choix_valide(pnj_doc: dict, noeud_id: str, choix_id: str, contexte: dict) -> dict | None:
	"""Le choix demandé s'il existe dans ce nœud ET que sa condition passe (revalidation
	serveur — le client ne fait pas foi). None sinon (422 côté router)."""
	noeuds = (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {})
	noeud = noeuds.get(noeud_id)
	if not noeud:
		return None
	for choix in noeud.get("choix") or []:
		if choix.get("id") == choix_id:
			return choix if condition_ok(choix.get("condition"), contexte) else None
	return None


# ---------------------------------------------------------------------------
# Délai de réouverture
# ---------------------------------------------------------------------------
# Un nœud peut porter `delai_min` (secondes) : l'atteindre ferme le dialogue de CE PNJ pour
# ce temps-là. La racine peut porter `noeud_attente`, servi à la place de `noeud_depart` tant
# que le délai court (refus PARLÉ — un silence serait indiscernable d'un bug).
#
# ⚠️ Le moteur ne connaît AUCUN « nœud de fin » : `fin` est une sentinelle de chaîne lue par
# le router, et le serveur ne sait jamais qu'une conversation s'achève — il sait seulement
# quel nœud il vient de RENDRE. Le délai s'arme donc au rendu du nœud qui le porte.
#
# État : character["dialogues_delais"][pnj_id] = {"jusqu": epoch, "noeud": id qui a armé} —
# une entrée par PNJ, écrasée à chaque armement. Forme calquée sur `laissez_passer` ;
# péremption PARESSEUSE par comparaison d'epoch (miroir de marche.marchandage_bloque), aucun
# tick de fond, aucune purge : une entrée échue est inerte. Champ absent ⇒ aucun délai.


def delai_min_de(pnj_doc: dict, noeud_id: str) -> int:
	"""Délai de réouverture (secondes) déclaré par ce nœud. 0 = aucun (champ absent, non
	numérique ou ≤ 0 — une valeur illisible ne verrouille rien)."""
	try:
		return max(0, int(_noeud(pnj_doc, noeud_id).get("delai_min", 0) or 0))
	except (TypeError, ValueError):
		return 0


def armer_delai(character: dict, pnj_id: str, pnj_doc: dict, noeud_id: str,
				now: int) -> dict | None:
	"""Arme le délai de ce PNJ si `noeud_id` en déclare un. Renvoie l'entrée posée, ou None
	si le nœud n'en porte pas — dans ce cas RIEN n'est écrit (pas même le dictionnaire).
	Mute sans sauvegarder : l'appelant persiste."""
	delai = delai_min_de(pnj_doc, noeud_id)
	if not delai or not pnj_id:
		return None
	entree = {"jusqu": int(now) + delai, "noeud": noeud_id}
	character.setdefault("dialogues_delais", {})[pnj_id] = entree
	return entree


def delai_restant(character: dict, pnj_id: str, now: int) -> int:
	"""Secondes restant avant que le dialogue de ce PNJ puisse rouvrir ; 0 = libre (aucun
	délai posé, ou déjà échu). ⚠️ Ne mute pas : un getter ne purge pas."""
	entree = ((character or {}).get("dialogues_delais") or {}).get(pnj_id) or {}
	try:
		return max(0, int(entree.get("jusqu", 0) or 0) - int(now))
	except (TypeError, ValueError):
		return 0


def _noeud(pnj_doc: dict, noeud_id: str) -> dict:
	"""Le nœud demandé, ou un dict vide (aucun accès à l'arbre ne doit lever)."""
	return (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {}).get(noeud_id) or {}


def noeud_depart_effectif(pnj_doc: dict, restant: int) -> str:
	"""Nœud par lequel ouvrir le dialogue : `noeud_attente` tant que le délai court,
	`noeud_depart` sinon.

	⚠️ Repli fail-OPEN assumé quand `noeud_attente` désigne un nœud INEXISTANT : `noeud_client`
	renverrait None, donc un PNJ muet dont le panneau se referme aussitôt — injouable, et
	indiscernable d'un bug. Le flag `dialogue_en_attente` reste posé de toute façon (les
	conditions verrouillent quand même) et c'est le linter qui attrape la référence morte."""
	dialogue = (pnj_doc or {}).get("dialogue") or {}
	depart = dialogue.get("noeud_depart", "accueil")
	attente = dialogue.get("noeud_attente")
	if restant > 0 and attente and attente in (dialogue.get("noeuds") or {}):
		return attente
	return depart


# ---------------------------------------------------------------------------
# Récompense de relation portée par un NŒUD
# ---------------------------------------------------------------------------
# Un nœud peut porter `relation` = {delta, lieu?, unique?} : le RENDRE fait bouger la
# réputation du joueur. C'est le seul chemin par lequel un auteur de dialogue peut toucher
# une relation depuis la DONNÉE (tous les autres — transport, marchandage, fidélité,
# renoncement — sont des chemins spécialisés écrits en dur).
#
# ⚠️ VERSÉ UNE SEULE FOIS. Un nœud reste atteignable tant que sa condition tient (le flag
# `acces_accompli` vaut vrai jusqu'au rapport à la guilde) : sans garde, fermer et rouvrir le
# panneau monterait la relation à 100. La clé du marqueur est DÉRIVÉE par défaut
# (`<pnj_id>:<noeud_id>`), donc un auteur qui n'y pense pas obtient quand même le
# comportement sûr ; `unique` (chaîne) la force quand deux nœuds partagent la récompense.
#
# La récompense se ROUVRE explicitement : un autre nœud porte `relation_reinit` = un id de
# nœud (ou une liste), et le rendre OUBLIE le versement — chez le gardien du donjon, c'est le
# nœud par lequel il fait descendre le joueur : redescendre, c'est repartir pour un tour.
# ⚠️ On nomme un NŒUD, jamais une clé brute : la clé est relue par `recompense_relation_de`,
# donc `unique` explicite et clé dérivée marchent pareil, et le linter peut vérifier la cible.
#
# État : character["dialogues_relations"] = {cle: epoch}. Forme calquée sur
# `dialogues_delais`/`laissez_passer` ; champ absent ⇒ rien n'a été versé, AUCUNE migration.


def recompense_relation_de(pnj_doc: dict, noeud_id: str) -> dict | None:
	"""Bloc `relation` de ce nœud, NORMALISÉ en `{lieu, delta, cle}` — `lieu` à None = le lieu
	courant (le router tranche), `cle` = l'identité du versement.

	None si le nœud n'existe pas, ne porte pas de bloc, ou si le `delta` est nul ou illisible :
	miroir de `delai_min_de`, une valeur qu'on ne sait pas lire ne fait rien plutôt que de
	lever — c'est le linter qui signale le bloc fautif, pas le moteur en pleine conversation."""
	bloc = _noeud(pnj_doc, noeud_id).get("relation")
	if not isinstance(bloc, dict):
		return None
	try:
		delta = int(bloc.get("delta", 1))
	except (TypeError, ValueError):
		return None
	if not delta:
		return None
	unique = bloc.get("unique")
	cle = unique if isinstance(unique, str) and unique else f"{(pnj_doc or {}).get('_id')}:{noeud_id}"
	lieu = bloc.get("lieu")
	return {"lieu": lieu if isinstance(lieu, str) and lieu else None, "delta": delta, "cle": cle}


def relation_deja_versee(character: dict, cle: str) -> bool:
	"""Cette récompense a-t-elle déjà été encaissée ? ⚠️ Ne mute pas : un getter ne purge pas
	(même règle que `delai_restant`)."""
	return cle in ((character or {}).get("dialogues_relations") or {})


def marquer_relation_versee(character: dict, cle: str, now: int) -> None:
	"""Note le versement (mute sans sauvegarder : l'appelant persiste). L'epoch n'est lu par
	personne — il est là pour qu'un marqueur reste diagnosticable en base."""
	character.setdefault("dialogues_relations", {})[cle] = int(now)


def relations_a_reinitialiser(pnj_doc: dict, noeud_id: str) -> list:
	"""Clés de versement que le rendu de ce nœud doit OUBLIER (champ `relation_reinit`, chaîne
	ou liste d'ids de nœuds du même doc).

	⚠️ Fail-SOFT : un id qui ne désigne aucun nœud, ou un nœud sans bloc `relation`, est ignoré
	en silence — le moteur ne casse pas une conversation pour une référence morte, et le linter
	la signale avant l'import (une levée qui ne lève rien laisserait une récompense fermée pour
	toujours, sans le moindre symptôme en jeu)."""
	brut = _noeud(pnj_doc, noeud_id).get("relation_reinit")
	if isinstance(brut, str):
		brut = [brut]
	if not isinstance(brut, list):
		return []
	cles = []
	for cible in brut:
		recompense = recompense_relation_de(pnj_doc, cible) if isinstance(cible, str) else None
		if recompense and recompense["cle"] not in cles:
			cles.append(recompense["cle"])
	return cles


def oublier_relations_versees(character: dict, cles) -> bool:
	"""Retire ces marqueurs : les récompenses redeviennent versables une fois. Mute sans
	sauvegarder ; renvoie True si quelque chose a bougé (l'appelant décide de persister)."""
	versees = (character or {}).get("dialogues_relations") or {}
	modifie = False
	for cle in cles or []:
		if versees.pop(cle, None) is not None:
			modifie = True
	return modifie


# ---------------------------------------------------------------------------
# Service de soin
# ---------------------------------------------------------------------------

def soin_effectif(pnj_doc: dict, contexte: dict) -> dict | None:
	"""Paramètres effectifs du soin pour CE personnage : gratuit et plus efficace si
	l'une des relations de `gratuit_si.lieux` atteint le seuil (défaut world-var
	PNJ_REPUTATION_SEUIL). None si le PNJ n'offre pas ce service."""
	service = (((pnj_doc or {}).get("services") or {}).get("soin"))
	if not service:
		return None
	gratuit_si = service.get("gratuit_si") or {}
	seuil = int(gratuit_si.get("seuil", character_stats.PNJ_REPUTATION_SEUIL))
	relations = contexte.get("relations") or {}
	gratuit = any(relations.get(lid, 0) >= seuil for lid in gratuit_si.get("lieux") or [])
	if gratuit:
		fraction = float(gratuit_si.get("fraction_pv", 1.0))
		cout = 0
	else:
		fraction = float(service.get("fraction_pv", 0.5))
		cout = max(0, int(service.get("cout_cuivre", 0)))
	return {"cout_cuivre": cout, "fraction_pv": fraction, "gratuit": gratuit}


def appliquer_soin(character: dict, pv_max: int, fraction: float) -> int:
	"""Rend `fraction × pv_max` PV, clampé au max (mute currentPV, NE SAUVEGARDE PAS).
	Renvoie les PV effectivement rendus."""
	avant = int(character.get("currentPV", pv_max) or 0)
	rendu = max(0, round(int(pv_max) * float(fraction)))
	character["currentPV"] = min(int(pv_max), avant + rendu)
	return character["currentPV"] - avant


# ---------------------------------------------------------------------------
# Service de don (remise d'un objet — ex. eau bénite du temple)
# ---------------------------------------------------------------------------

def don_effectif(pnj_doc: dict, contexte: dict) -> dict | None:
	"""Paramètres effectifs du service `don` pour CE personnage : quel item, quelle
	quantité, et son coût — **gratuit** si l'une des relations de `gratuit_si.lieux`
	atteint le seuil (défaut world-var PNJ_REPUTATION_SEUIL). None si le PNJ n'offre pas
	ce service. Miroir de `soin_effectif`. Schéma data attendu :
	`services.don = {item, quantite, cout_cuivre, gratuit_si:{lieux, seuil},
	noeuds:{fait, sans_fonds, trop_charge}}`."""
	service = (((pnj_doc or {}).get("services") or {}).get("don"))
	if not service or not service.get("item"):
		return None
	gratuit_si = service.get("gratuit_si") or {}
	seuil = int(gratuit_si.get("seuil", character_stats.PNJ_REPUTATION_SEUIL))
	relations = contexte.get("relations") or {}
	gratuit = any(relations.get(lid, 0) >= seuil for lid in gratuit_si.get("lieux") or [])
	cout = 0 if gratuit else max(0, int(service.get("cout_cuivre", 0)))
	return {
		"item": service.get("item"),
		"quantite": max(1, int(service.get("quantite", 1))),
		"cout_cuivre": cout,
		"gratuit": gratuit,
	}


def appliquer_don(character: dict, item_id: str, poids_unitaire: float, quantite: int) -> int:
	"""Ajoute `quantite` instances de `item_id` à l'inventaire, chacune en référence
	`{item, poids}` (mute `inventaire`, NE SAUVEGARDE PAS). Renvoie la quantité ajoutée.
	Le contrôle de charge et le débit se font côté router avant l'appel."""
	inv = character.setdefault("inventaire", [])
	n = max(1, int(quantite))
	for _ in range(n):
		inv.append({"item": item_id, "poids": float(poids_unitaire)})
	return n

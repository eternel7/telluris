# utils/sorts.py
# Sorts (magie) : un doc CouchDB `sort:*` porte une vocation, un niveau, un coût en PM
# et des `effets` au format des consommables ({pv, pm, regen_pv, regen_pm, buffs, duree})
# étendu d'une clé `degats` (notation dés, ex. "2D6"). Deux modes d'utilisation :
# sans composant (PM seuls, effet de base) ou avec composant(s) — chaque entrée de
# `composants` [{item, consomme, bonus}] ajoute son `bonus` (même schéma qu'`effets`)
# aux effets de base. Composant `consomme:true` = retiré du sac (gros bonus) ;
# `consomme:false` = catalyseur, il suffit de le porter (sac ou équipé, bonus moindre).
#
# Apprentissage : le personnage stocke `sorts_connus` (liste d'ids). Un sort de niveau n
# est achetable en points de caractéristique — coût (n+1) × SORT_COUT_COEFF — dès que
# vocations_niveaux[vocation] ≥ n ET qu'un grimoire l'enseignant (item sous_categorie
# "grimoire", champ `sorts` contenant l'id) est porté. Le grimoire n'est PAS consommé.
# Un sort d'une FAMILLE exclue par la vocation (cf. `familles_exclues`) reste inapprenable
# quel que soit le reste — c'est ce qui laisse le répurgateur pratiquer la Démonologie
# sans ses invocations.
#
# Invocations : un sort peut porter un bloc `invocation` (cf. `invocation_de`) À LA PLACE de
# ses `effets`. Il fait apparaître N créatures ALLIÉES sur la grille de combat pour quelques
# tours ; tout ce qui les anime vit dans utils/combat.py (placement, tour d'IA, dissipation),
# ce module ne fait que normaliser et borner la donnée. ⚠️ EXCLUSIF : la branche `sort` de
# `resolve_action` traite l'invocation AVANT la cible et n'applique alors AUCUN `effets` —
# écrire les deux sur un même doc laisserait les seconds silencieusement inertes.
#
# Logique pure (get_doc/find_docs/resolve_ref injectés), ne sauvegarde jamais — les
# endpoints persistent. Comme pour les consommables : pv/pm/degats = instantanés (seuls
# applicables en combat) ; buffs/regen_* + duree = effet actif empilé sur
# character["effets_actifs"] (tour monde uniquement) ; jamais de buff sur V.

from models import character_stats
from utils.characters import item_ref_id
from utils.consommables import _as_int, poser_effet
from utils.zones_effet import normaliser_zone

# Jet de toucher d'un effet offensif, porté par la DONNÉE. SOURCE UNIQUE, partagée avec
# les compétences (utils/competences.py l'importe) — les deux familles se résolvent par
# le même contrat, il ne doit pas exister deux listes qui divergent.
#   `magique` → seuil `_magic_hit_threshold` contre la pm_def, PA NON soustraits ;
#   `cc`/`cd` → seuil `_hit_threshold` contre l'Ag (+ esquive), PA soustraits.
# ⚠️ Le défaut DIFFÈRE entre les deux familles, et c'est voulu : une compétence est
# martiale par défaut (`cc`), un sort est magique par défaut (`magique`) — sans quoi les
# sorts déjà en base changeraient de mode de résolution du jour au lendemain.
JETS = ("cc", "cd", "magique")
JET_SORT_DEFAUT = "magique"

# Cibles possibles d'un sort ou d'une compétence. SOURCE UNIQUE, partagée elle aussi.
#   `soi`    → le lanceur ;
#   `ennemi` → un monstre, jet de toucher (cf. JETS) ;
#   `allie`  → un COMPAGNON ou une MONTURE du groupe, SANS jet (un allié ne se défend
#              pas). Combat uniquement : l'exploration ne sait pas encore désigner un
#              porteur comme cible, cf. `sort_utilisable_exploration`.
CIBLES = ("soi", "ennemi", "allie")
CIBLE_DEFAUT = "soi"

# ── Familles (types) de sorts et de compétences ──────────────────────────────────
# `famille` est une ÉTIQUETTE LIBRE portée par la DONNÉE (doc `sort:*` ou `competence:*`)
# qui classe une capacité par TYPE — et non par école : « invocation » existe en
# Démonologie comme en Nécromancie. Elle ne sert qu'à une chose : permettre à une vocation
# d'EXCLURE tout un type de son apprentissage (`familles_exclues` de son entrée dans
# rules:vocations), sans scinder une école ni énumérer les sorts un par un.
#
# ⚠️ Champ absent ⇒ famille vide ⇒ JAMAIS exclue : un doc déjà en base garde exactement le
# comportement d'avant (aucune migration), et une vocation sans `familles_exclues` non plus.
# SOURCE UNIQUE, partagée avec les compétences (utils/competences.py l'importe) : les deux
# familles se filtrent par le même contrat, il ne doit pas exister deux règles qui divergent.
FAMILLE_INVOCATION = "invocation"

# Bornes du bloc `invocation` (cf. `invocation_de`). Une durée absente vaut
# INVOCATION_DUREE_DEFAUT tours — jamais « illimitée » : une créature qui ne se dissipe
# jamais resterait sur la carte tout le combat pour le prix d'une action.
INVOCATION_DUREE_DEFAUT = 3
INVOCATION_NOMBRE_MAX = 4

# ── Les trois notions du temps magique ───────────────────────────────────────────
# Un sort porte TROIS contraintes distinctes, volontairement séparées pour qu'elles se
# combinent librement (un Météore est long à lancer mais ne s'entretient pas ; un Mur de
# feu part vite et coûte chaque round) :
#   `incantation` → PA de LANCEMENT : le temps nécessaire pour déclencher le sort ;
#   `cout_pm`     → PM de LANCEMENT : l'énergie nécessaire pour le créer ;
#   `maintien`    → PM de MAINTIEN  : l'énergie consommée chaque round pour le garder actif.
#
# ⚠️ Défauts NEUTRES (`incantation` 1, `maintien` 0) : un doc `sort:*` déjà en base se
# comporte exactement comme avant — aucune migration (CLAUDE.md §4).
# ⚠️ COMBAT SEULEMENT pour les deux champs neufs : il n'y a pas de round en exploration,
# donc rien à quoi rattacher un PA reporté ou un prélèvement par tour (cf.
# `sort_utilisable_exploration`). Même arbitrage que l'invocation, et pour la même raison.
INCANTATION_PA_DEFAUT = 1
INCANTATION_PA_MAX = 12
MAINTIEN_PM_MAX = 20

# Bornes des clés d'effet neuves (cf. `_bonus_dict`). Un drain ne rend jamais plus que les
# dégâts infligés, un saut ne franchit pas la moitié d'une carte.
DRAIN_PCT_MAX = 100
LIEN_VIE_PCT_MAX = 100
SAUT_DISTANCE_MAX = 8


def _bonus_dict(raw) -> dict:
	"""Normalise un bloc d'effets/bonus : degats str, entiers ≥ 0, buffs {caract:int},
	duree ≥ 0.

	⚠️ **V est buffable, mais à SON échelle (1-10), pas à celle des autres (×10).** Elle
	en était exclue par prudence — un auteur écrivant `{V: 10}` en pensant « +1 case »
	aurait immobilisé puis catapulté sa cible. L'exclusion a été levée quand il a fallu
	entraver les jambes d'une cible (bolas) : elle ne protégeait aucun contenu (aucun doc
	du jeu n'écrivait de buff de V) et elle rendait l'entrave **impossible à exprimer**,
	alors que toute la chaîne aval la gère déjà (`_refresh_snapshot_stats` recompose
	`deplacement_base` depuis V, l'IA monstre lit `deplacement`). Ordres de grandeur :
	**−2 = un tiers du déplacement d'un humain**, −5 l'immobilise à peu près. Deux
	planchers bornent la casse : V ne descend pas sous 0 (`_refresh_snapshot_stats`) et
	`deplacement = max(1, V)` — une cible entravée avance toujours d'une case.

	Clés de combat partagées sorts/compétences :
	- `esquive`  : malus au seuil de toucher PHYSIQUE (cc/cd) des attaques subies —
	  jamais la magie (elle se résout sur pm_def, pas sur l'Ag).
	- `furtivite`: > 0 = confère l'état furtif ; la valeur s'ajoute à l'Ag dans la
	  difficulté du jet de détection des ennemis.
	- `degats_pm`: notation de dés portée aux PM de la CIBLE (et non à ses PV). Sans
	  soustraction des PA : une armure n'arrête pas une siphonie.
	- `cout_pv`  : PV dépensés par le LANCEUR au lancement. ⚠️ Ce ne sont PAS des dégâts
	  subis — ni test de concentration, ni lien de vie, ni furtivité rompue.
	- `drain_pv` / `drain_pm` : pourcentage des dégâts RÉELLEMENT infligés reversé au
	  lanceur, plafonné par `drain_max` (0 = aucun plafond) une fois par lancement.
	- `saut`     : distance max d'une téléportation (cases). Le sort vise une CASE.
	- `lien_vie` : {part, reduction} — cf. `_lien_vie_dict`.

	⚠️ Toutes les clés neuves sont ≥ 0 par nature : le clamp d'`_as_int` reste valide, et
	un doc déjà en base les reçoit à leur valeur neutre (aucune migration, CLAUDE.md §4)."""
	raw = raw or {}
	buffs = {}
	for k, v in (raw.get("buffs") or {}).items():
		try:
			buffs[str(k)] = int(v)
		except (TypeError, ValueError):
			continue
	return {
		"degats": str(raw.get("degats") or "").strip(),
		"pv": _as_int(raw.get("pv")),
		"pm": _as_int(raw.get("pm")),
		"regen_pv": _as_int(raw.get("regen_pv")),
		"regen_pm": _as_int(raw.get("regen_pm")),
		"buffs": buffs,
		"duree": _as_int(raw.get("duree")),
		"esquive": _as_int(raw.get("esquive")),
		"furtivite": _as_int(raw.get("furtivite")),
		"degats_pm": str(raw.get("degats_pm") or "").strip(),
		"cout_pv": _as_int(raw.get("cout_pv")),
		"drain_pv": min(DRAIN_PCT_MAX, _as_int(raw.get("drain_pv"))),
		"drain_pm": min(DRAIN_PCT_MAX, _as_int(raw.get("drain_pm"))),
		"drain_max": _as_int(raw.get("drain_max")),
		"saut": min(SAUT_DISTANCE_MAX, _as_int(raw.get("saut"))),
		"lien_vie": _lien_vie_dict(raw.get("lien_vie")),
		# Renforts d'un sort qui ne pose pas d'`effets` : ils ne valent QUE comme bonus de
		# composant, appliqués au doc par `doc_effectif` (cf. INVOCATION_* / MAINTIEN_*).
		"invocation_duree": _as_int(raw.get("invocation_duree")),
		"invocation_nombre": min(INVOCATION_NOMBRE_MAX, _as_int(raw.get("invocation_nombre"))),
		"maintien_reduction": min(MAINTIEN_PM_MAX, _as_int(raw.get("maintien_reduction"))),
	}


def _lien_vie_dict(raw) -> dict | None:
	"""Bloc `lien_vie` d'un effet, normalisé — ou None si l'effet n'en porte pas.

	`{part, reduction}` en POURCENTS : sur les dégâts qu'encaisse le protégé, `reduction`
	est d'abord absorbée, puis `part` du reste est TRANSFÉRÉE au protecteur. ⚠️ Le lien ne
	CRÉE aucun dégât — il déplace la perte de PV d'un corps vers l'autre (l'exemple du
	livre de règles : 20 dégâts avec `part: 50` font 10 et 10).

	⚠️ `part` à 0 rendrait le lien inerte tout en le faisant payer : le bloc est alors
	considéré comme absent, plutôt que de laisser un sort s'entretenir pour rien."""
	raw = raw or {}
	part = min(LIEN_VIE_PCT_MAX, _as_int(raw.get("part")))
	if part <= 0:
		return None
	return {"part": part, "reduction": min(LIEN_VIE_PCT_MAX, _as_int(raw.get("reduction")))}


def effets_de_sort(sort_doc) -> dict:
	"""Champ `effets` du sort, normalisé (clés toujours présentes)."""
	return _bonus_dict((sort_doc or {}).get("effets"))


def famille_de(doc) -> str:
	"""Famille (`famille`) d'un doc `sort:*`/`competence:*` OU de sa vue normalisée —
	chaîne vide si le doc n'en porte pas. Partagée avec les compétences."""
	return str((doc or {}).get("famille") or "").strip()


def invocation_de(doc) -> dict | None:
	"""Bloc `invocation` d'un sort, normalisé — ou None si le sort n'invoque rien.

	`{espece, profil, nombre, duree}` : `espece` (doc `espece:*`) est le SEUL champ requis ;
	`profil` vide = point médian de l'espèce au niveau 1 (le tirage `profil:*` est aléatoire,
	son absence rend l'invocation déterministe). `nombre` et `duree` sont bornés — cf.
	INVOCATION_NOMBRE_MAX / INVOCATION_DUREE_DEFAUT."""
	raw = (doc or {}).get("invocation") or {}
	espece = str(raw.get("espece") or "").strip()
	if not espece:
		return None
	return {
		"espece": espece,
		"profil": str(raw.get("profil") or "").strip(),
		"nombre": max(1, min(INVOCATION_NOMBRE_MAX, _as_int(raw.get("nombre")) or 1)),
		"duree": max(1, _as_int(raw.get("duree")) or INVOCATION_DUREE_DEFAUT),
	}


def est_invocation(sort: dict) -> bool:
	"""Le sort (vue normalisée) fait-il apparaître une créature ? SOURCE UNIQUE du test —
	c'est la présence du bloc `invocation` qui décide, jamais la `famille` (une étiquette
	libre, qu'un auteur peut oublier ou orthographier autrement)."""
	return bool((sort or {}).get("invocation"))


def est_maintenu(capacite: dict) -> bool:
	"""La capacité (vue normalisée) demande-t-elle un ENTRETIEN en PM chaque round ?
	SOURCE UNIQUE du test, partagée par les deux éligibilités, le moteur et le client."""
	return _as_int((capacite or {}).get("maintien")) > 0


def est_incantation_longue(capacite: dict) -> bool:
	"""L'incantation déborde-t-elle du lancement immédiat (plus d'un PA) ?

	⚠️ À `incantation == 1` tout se passe exactement comme avant : un sort part dans
	l'appel qui le lance. C'est ce prédicat, et lui seul, qui bascule sur la machinerie
	de canalisation multi-round."""
	return _as_int((capacite or {}).get("incantation")) > INCANTATION_PA_DEFAUT


def pm_par_pa(capacite: dict) -> int:
	"""Tranche de PM versée par PA d'incantation — `ceil(cout_pm / incantation)`.

	Le coût en PM est réparti sur les PA, arrondi AU SUPÉRIEUR, et la réserve baisse au
	fur et à mesure. Les derniers PA peuvent donc coûter ZÉRO si tous les PM nécessaires
	ont déjà été versés : un Météore de 15 PM en 6 PA verse 3 PM par PA, les 15 PM sont
	couverts au 5ᵉ, et le 6ᵉ — celui qui déclenche enfin le sort — est gratuit.

	⚠️ Sert aussi de PÉNALITÉ à une réussite non critique du test de concentration : un
	coup encaissé coûte une tranche, pas le sort entier.
	⚠️ `incantation` est planché à 1 par `normaliser_sort` — pas de division par zéro."""
	c = capacite or {}
	pa = max(INCANTATION_PA_DEFAUT, _as_int(c.get("incantation")))
	return -(-_as_int(c.get("cout_pm")) // pa)


def seuil_concentration(vol: int, degats_subis: int) -> int:
	"""Seuil d100 d'un test de concentration : `50 + Vol/div − dégâts subis`, clampé [5, 95].

	Même forme que les deux autres seuils du moteur (`_hit_threshold`, `_flee_threshold`) :
	la Volonté tient l'incantation, le coup encaissé l'écarte. Le clamp garde toujours une
	marge des deux côtés — aucun mage n'est incassable, aucun coup n'interrompt à coup sûr.

	Logique PURE (aucune lecture de snapshot) : la résolution du jet, elle, reste dans
	`utils/combat._resoudre_jet`, pour que la Chance pilote les fenêtres de critique."""
	div = max(1, character_stats.CONCENTRATION_VOL_DIV)
	return max(5, min(95, 50 + int(vol or 0) // div - max(0, int(degats_subis or 0))))


# Une ARME porte le même bloc `effets` qu'un sort, mais ne sait viser que deux personnes :
# celui qu'elle frappe, ou celui qui la tient. `allie` n'a pas de sens pour un coup porté
# (aucun jet de toucher n'a désigné d'allié) → il retombe sur `ennemi` plutôt que d'ouvrir
# un troisième comportement silencieux, exactement comme `normaliser_sort` clampe `cible`.
CIBLES_ARME = ("ennemi", "soi")
CIBLE_ARME_DEFAUT = "ennemi"


def effets_d_arme(item_doc) -> tuple[dict, str]:
	"""`(effets normalisés, cible)` d'un doc `item:*` — le bloc `effets` d'une arme.

	Même normalisation que les sorts et les compétences (source unique `_bonus_dict`) :
	un effet d'arme se décrit exactement comme un effet de sort, et se pose par les mêmes
	chokepoints. Seule la **part durative** est exploitée à l'impact (`part_durative`) ;
	`degats`/`pv`/`pm` d'une arme passent par ses `bonus_degats*`, pas par ce bloc."""
	doc = item_doc or {}
	cible = str(doc.get("cible") or CIBLE_ARME_DEFAUT)
	if cible not in CIBLES_ARME:
		cible = CIBLE_ARME_DEFAUT
	return _bonus_dict(doc.get("effets")), cible


def normaliser_sort(sort_doc) -> dict | None:
	"""Vue normalisée d'un doc `sort:*`, ou None si le doc n'est pas un sort valide
	(type ≠ "sort", coût PM ≤ 0).

	⚠️ Un sort n'appartient à AUCUNE vocation : il appartient à son école (`magie`). Le
	champ `vocation` des docs anciens n'est plus lu que par le repli de `magie_de_sort`."""
	doc = sort_doc or {}
	if doc.get("type") != "sort":
		return None
	cout_pm = _as_int(doc.get("cout_pm"))
	if cout_pm <= 0:
		return None
	cible = str(doc.get("cible") or CIBLE_DEFAUT)
	if cible not in CIBLES:
		cible = CIBLE_DEFAUT
	jet = str(doc.get("jet") or JET_SORT_DEFAUT)
	if jet not in JETS:
		jet = JET_SORT_DEFAUT
	composants = []
	for c in doc.get("composants") or []:
		item_id = (c or {}).get("item")
		if not item_id:
			continue
		composants.append({
			"item": str(item_id),
			"consomme": bool(c.get("consomme")),
			"bonus": _bonus_dict(c.get("bonus")),
		})
	return {
		"id": doc.get("_id", ""),
		"nom": doc.get("nom", "Sort"),
		"icon": doc.get("icon", "🔮"),
		"description": doc.get("description", ""),
		# Rétro-compat SEULE : repli d'école d'un doc sans `magie` (cf. `magie_de_sort`).
		"vocation": doc.get("vocation"),
		"magie": (str(doc.get("magie")).strip() or None) if doc.get("magie") else None,
		# Type du sort, pour l'exclusion d'apprentissage par vocation (cf. FAMILLE_*).
		"famille": famille_de(doc),
		# Créature(s) appelée(s) par le sort, ou None. EXPLICITE dans cette vue, qui est
		# une liste blanche : sans ce champ la liaison n'atteindrait jamais le moteur de
		# combat (même piège que `animation`).
		"invocation": invocation_de(doc),
		"niveau": _as_int(doc.get("niveau")),
		"cout_pm": cout_pm,
		# ── Les deux notions de TEMPS, à côté du `cout_pm` d'ÉNERGIE (cf. INCANTATION_*).
		# EXPLICITES dans cette liste blanche, comme `animation`, `zone` et `invocation`
		# avant elles : sans ces deux lignes, un sort à incantation longue ou à entretien
		# se lancerait instantanément et gratuitement, sans le moindre message d'erreur.
		# `incantation` : PA de lancement, plancher 1 — 0 n'aurait aucun sens et ferait
		# diviser par zéro le calcul de la tranche de PM par PA.
		"incantation": max(INCANTATION_PA_DEFAUT,
						   min(INCANTATION_PA_MAX, _as_int(doc.get("incantation")))),
		# `maintien` : PM par round pour rester actif, 0 = sort non maintenu.
		"maintien": min(MAINTIEN_PM_MAX, _as_int(doc.get("maintien"))),
		"cible": cible,
		# Jet de toucher (cible ennemie seulement) : `magique` par défaut — un sort de
		# CONTACT peut demander `cc` (« au toucher » : il faut d'abord poser la main).
		"jet": jet,
		"portee": _as_int(doc.get("portee")),
		# Zone d'effet (ou None) : forme touchée autour de la cible désignée ou du
		# lanceur — cf. utils/zones_effet.py. Absente ⇒ la seule case de la cible,
		# comportement d'avant. EXPLICITE dans cette liste blanche, comme `animation`.
		"zone": normaliser_zone(doc.get("zone")),
		"effets": effets_de_sort(doc),
		"composants": composants,
		# Condition d'activation optionnelle (partagée avec les compétences) :
		# {"battle_map_tags": [...]} — évaluée en combat via condition_remplie.
		"condition": dict(doc.get("condition") or {}),
		# Animation de combat (doc `animation:*`), optionnelle : le router passe la vue
		# normalisée à resolve_action, donc sans ce champ EXPLICITE la liaison serait
		# perdue avant d'atteindre le moteur (cette vue est une liste blanche).
		"animation": str(doc.get("animation") or ""),
	}


def concat_degats(a: str, b: str) -> str:
	"""Concatène deux notations de dés/bonus plats ("2D6" + "1D6" → "2D6+1D6"). Publique :
	partagée par les composants de sort (fusionner_effets) et par les compétences de corps à
	corps, qui ajoutent les dégâts d'arme du porteur aux leurs (combat._degats_competence)."""
	a, b = (a or "").strip(), (b or "").strip()
	if not a:
		return b
	if not b:
		return a
	return a + "+" + b


def fusionner_effets(base: dict, bonus_list: list) -> dict:
	"""Effets de base + bonus additifs des composants engagés : entiers additionnés,
	buffs sommés par caract, notations `degats` concaténées, durée additive.

	⚠️ `lien_vie` est ÉCRASÉ par le dernier bloc non vide, jamais fusionné : un composant
	renforce un lien existant (ou en pose un), il n'en recompose pas la géométrie — deux
	`part` additionnés dépasseraient 100 % et transféreraient plus que le coup reçu."""
	out = {
		"degats": base.get("degats", ""),
		"pv": _as_int(base.get("pv")),
		"pm": _as_int(base.get("pm")),
		"regen_pv": _as_int(base.get("regen_pv")),
		"regen_pm": _as_int(base.get("regen_pm")),
		"buffs": dict(base.get("buffs") or {}),
		"duree": _as_int(base.get("duree")),
		"esquive": _as_int(base.get("esquive")),
		"furtivite": _as_int(base.get("furtivite")),
		"degats_pm": base.get("degats_pm", ""),
		"cout_pv": _as_int(base.get("cout_pv")),
		"drain_pv": _as_int(base.get("drain_pv")),
		"drain_pm": _as_int(base.get("drain_pm")),
		"drain_max": _as_int(base.get("drain_max")),
		"saut": _as_int(base.get("saut")),
		"lien_vie": dict(base["lien_vie"]) if base.get("lien_vie") else None,
		"invocation_duree": _as_int(base.get("invocation_duree")),
		"invocation_nombre": _as_int(base.get("invocation_nombre")),
		"maintien_reduction": _as_int(base.get("maintien_reduction")),
	}
	for bonus in bonus_list or []:
		bonus = bonus or {}
		out["degats"] = concat_degats(out["degats"], bonus.get("degats", ""))
		out["degats_pm"] = concat_degats(out["degats_pm"], bonus.get("degats_pm", ""))
		if bonus.get("lien_vie"):
			out["lien_vie"] = dict(bonus["lien_vie"])
		for key in ("pv", "pm", "regen_pv", "regen_pm", "duree", "esquive", "furtivite",
					"cout_pv", "drain_pv", "drain_pm", "drain_max", "saut",
					"invocation_duree", "invocation_nombre", "maintien_reduction"):
			out[key] += _as_int(bonus.get(key))
		for k, delta in (bonus.get("buffs") or {}).items():
			if str(k) == "V":
				continue
			try:
				out["buffs"][str(k)] = int(out["buffs"].get(str(k), 0)) + int(delta)
			except (TypeError, ValueError):
				continue
	# ⚠️ Re-clampage APRÈS l'addition : `_bonus_dict` borne chaque bloc pris isolément,
	# mais deux composants à 60 % de drain feraient 120 % — un sort qui rend plus de PV
	# qu'il n'inflige de dégâts.
	out["drain_pv"] = min(DRAIN_PCT_MAX, out["drain_pv"])
	out["drain_pm"] = min(DRAIN_PCT_MAX, out["drain_pm"])
	out["saut"] = min(SAUT_DISTANCE_MAX, out["saut"])
	return out


def _ids_sac(character: dict) -> list:
	return [item_ref_id(ref) for ref in (character or {}).get("inventaire") or []]


def _ids_portes(character: dict) -> list:
	"""Ids des items portés : sac + slots équipés."""
	ids = _ids_sac(character)
	for ref in ((character or {}).get("slots") or {}).values():
		if ref:
			ids.append(item_ref_id(ref))
	return ids


def composants_etat(sort: dict, character: dict) -> list:
	"""Disponibilité de chaque composant du sort : un catalyseur (`consomme:false`)
	est disponible s'il est porté (sac OU équipé) ; un composant consommé exige au
	moins un exemplaire AU SAC (un item seulement équipé ne se consume pas)."""
	sac = _ids_sac(character)
	portes = _ids_portes(character)
	out = []
	for c in (sort or {}).get("composants") or []:
		pool = sac if c.get("consomme") else portes
		out.append({**c, "disponible": c.get("item") in pool})
	return out


def effets_effectifs(sort: dict, composants_engages: list) -> dict:
	"""Effets du sort avec les bonus des composants dont l'id figure dans
	`composants_engages` (liste d'ids item, déjà re-vérifiés par l'appelant)."""
	engages = set(composants_engages or [])
	bonus = [c["bonus"] for c in (sort or {}).get("composants") or []
			 if c.get("item") in engages]
	return fusionner_effets((sort or {}).get("effets") or {}, bonus)


def doc_effectif(sort: dict, effets: dict) -> dict:
	"""Copie de la vue normalisée `sort` où les renforts de composant qui portent sur le
	SORT et non sur ses effets sont appliqués : durée et nombre d'une invocation, entretien.

	C'est ce qui rend les composants d'une invocation opérants : sa branche du moteur
	n'applique aucun `effets`, elle lit le bloc `invocation` et le `maintien` du doc.
	⚠️ Re-clampé APRÈS l'addition (`nombre` ≤ INVOCATION_NOMBRE_MAX), comme drain et saut.
	⚠️ L'entretien ne descend JAMAIS sous 1 PM : à 0, `est_maintenu` basculerait et le sort
	changerait de nature (un sort tenu sans `duree` n'aurait plus rien pour durer).
	Sans renfort, rend une copie identique — le doc d'origine n'est jamais muté."""
	doc = dict(sort or {})
	eff = effets or {}
	inv = doc.get("invocation")
	if inv:
		doc["invocation"] = {
			**inv,
			"duree": _as_int(inv.get("duree")) + _as_int(eff.get("invocation_duree")),
			"nombre": min(INVOCATION_NOMBRE_MAX,
						  _as_int(inv.get("nombre")) + _as_int(eff.get("invocation_nombre"))),
		}
	reduction = _as_int(eff.get("maintien_reduction"))
	if reduction and est_maintenu(doc):
		doc["maintien"] = max(1, _as_int(doc.get("maintien")) - reduction)
	return doc


def part_durative(effets: dict) -> bool:
	"""Vrai si `effets` porte quelque chose à empiler sur la durée : une `duree` > 0 ET
	au moins un bénéfice prolongé (buffs de caract, régén, esquive).

	SOURCE UNIQUE de ce test — utilisée par les éligibilités combat/exploration des sorts,
	des compétences et des consommables, et par les deux `empiler_effet_*`. Un critère qui
	diverge entre « lançable » et « empilable » produirait un sort accepté puis sans effet.
	"""
	eff = effets or {}
	return _as_int(eff.get("duree")) > 0 and bool(
		eff.get("buffs") or _as_int(eff.get("regen_pv")) or _as_int(eff.get("regen_pm"))
		or _as_int(eff.get("esquive")))


def sort_utilisable_combat(sort: dict) -> bool:
	"""Éligibilité combat : une part instantanée (dégâts, PV, PM — ou furtivité, état de
	combat posé instantanément) OU une part à DURÉE. Depuis que le snapshot porte ses
	effets vivants et les décrémente au tour de son porteur, un buff pur (« Armure de
	givre ») est lançable en combat exactement comme en exploration.

	⚠️ Une INVOCATION est lançable sans porter le moindre `effets` : ce qu'elle fait n'est
	pas un effet posé sur quelqu'un, c'est un combattant de plus sur la grille.

	⚠️ Trois autres capacités n'ont, elles non plus, rien à poser sur personne — et
	seraient refusées ici comme « sans effet » :
	  - un sort MAINTENU (Bouclier magique : des buffs, mais aucune `duree` — c'est
	    l'entretien qui le tient, cf. INCANTATION_*) ;
	  - un SAUT, dont tout l'effet est une case d'arrivée ;
	  - un LIEN DE VIE, dont l'effet vit sur un AUTRE corps que celui qu'il vise.
	⚠️ Ce test et celui de `resolve_action` (branche `sort`) sont JUMEAUX : un critère qui
	diverge entre « lançable » et « applicable » produit un sort accepté puis inerte."""
	s = sort or {}
	if est_invocation(s) or est_maintenu(s):
		return True
	eff = s.get("effets") or {}
	return (bool(eff.get("degats")) or _as_int(eff.get("pv")) > 0
			or _as_int(eff.get("pm")) > 0 or _as_int(eff.get("furtivite")) > 0
			or bool(eff.get("degats_pm")) or _as_int(eff.get("saut")) > 0
			or bool(eff.get("lien_vie")) or part_durative(eff))


def sort_utilisable_exploration(sort: dict) -> bool:
	"""Éligibilité exploration : NON offensif (`soi` ou `allie`) ET au moins un effet
	applicable hors combat (soin/PM instantanés, ou buffs/régén/esquive à durée).

	⚠️ Seul `ennemi` est exclu : il n'y a pas de monstre à viser hors combat. Un sort
	`allie` est lançable sur un compagnon ou une monture — la cible est désignée par le
	`cible_id` du corps de requête (cf. `_cible_alliee`, routers/user.py).

	⚠️ Une INVOCATION est refusée hors combat, même si elle porte par ailleurs un effet
	applicable : la créature n'existe que sur la grille de combat (elle y est placée, y
	joue son tour et s'y dissipe). Rien ne saurait l'accueillir en exploration.

	⚠️ Quatre mécaniques sont refusées pour la MÊME raison — il n'y a **pas de round** en
	exploration, et pas de grille :
	  - une INCANTATION de plus d'un PA : rien à quoi rattacher un PA reporté ;
	  - un sort MAINTENU : rien à prélever, aucun tour ne passe ;
	  - un SAUT : aucune case où atterrir ;
	  - un LIEN DE VIE : aucun coup à rediriger.
	⚠️ `cout_pv`, lui, reste applicable : ce n'est qu'un coût, pas une règle de tour."""
	s = sort or {}
	if est_invocation(s) or est_maintenu(s) or est_incantation_longue(s):
		return False
	if (s.get("cible") or "soi") == "ennemi":
		return False
	eff = s.get("effets") or {}
	if _as_int(eff.get("saut")) > 0 or eff.get("lien_vie"):
		return False
	instant = _as_int(eff.get("pv")) > 0 or _as_int(eff.get("pm")) > 0
	return instant or part_durative(eff)


def empiler_effet_sort(character: dict, sort: dict, effets: dict) -> dict | None:
	"""Empile la part à durée (buffs/régén) des effets FUSIONNÉS sur
	character["effets_actifs"] (mute en place, NE SAUVEGARDE PAS). Même forme d'entrée
	que les consommables → tick_effets/caracts_avec_buffs/regen_bonus/chips inchangés.
	⚠️ Relancer le MÊME sort ne cumule pas : `poser_effet` remplace l'entrée précédente
	(seuls les effets du dernier lancement comptent — composants engagés compris)."""
	eff = effets or {}
	if not part_durative(eff):
		return None
	entry = {
		"sort_id": (sort or {}).get("id", ""),
		"nom": (sort or {}).get("nom", "Sort"),
		"icon": (sort or {}).get("icon", "🔮"),
		"buffs": dict(eff.get("buffs") or {}),
		"regen_pv": _as_int(eff.get("regen_pv")),
		"regen_pm": _as_int(eff.get("regen_pm")),
		"esquive": _as_int(eff.get("esquive")),
		"restants": _as_int(eff.get("duree")),
	}
	return poser_effet(character, entry)


# ── Apprentissage ────────────────────────────────────────────────────────────────

def cout_apprentissage(sort: dict) -> int:
	"""Coût en points de caractéristique : (niveau du sort + 1) × SORT_COUT_COEFF
	(lecture via le module — la world-var est réassignée à chaud)."""
	return (_as_int((sort or {}).get("niveau")) + 1) * character_stats.SORT_COUT_COEFF


def est_grimoire(item_doc) -> bool:
	return bool(item_doc) and item_doc.get("sous_categorie") == "grimoire"


def grimoire_pour(character: dict, sort_id: str, resolve_ref) -> dict | None:
	"""Premier grimoire porté (sac puis équipé) qui enseigne `sort_id`
	(item `sous_categorie:"grimoire"` dont le champ `sorts` contient l'id)."""
	refs = list((character or {}).get("inventaire") or [])
	refs += [ref for ref in ((character or {}).get("slots") or {}).values() if ref]
	for ref in refs:
		doc = resolve_ref(ref)
		if est_grimoire(doc) and sort_id in (doc.get("sorts") or []):
			return doc
	return None


def sorts_connus_docs(character: dict, get_doc) -> list:
	"""Docs normalisés des sorts connus du personnage (ids morts ignorés)."""
	out = []
	for sort_id in (character or {}).get("sorts_connus") or []:
		sort = normaliser_sort(get_doc(sort_id))
		if sort:
			out.append(sort)
	return out


def purger_sorts_hors_ecole(character: dict, get_doc, rules_vocations) -> list:
	"""Retire de `sorts_connus` (et de `sorts_epingles`) les sorts dont l'ÉCOLE n'est plus
	pratiquée par le personnage. MUTE, NE SAUVEGARDE PAS — l'appelant persiste.
	Renvoie `[{id, nom, icon, magie}]` de ce qui est parti (liste vide = rien à faire).

	POURQUOI. Changer la `magie` d'une vocation en base ferme sa liste « à apprendre », mais
	`sorts_connus` n'est jamais relu contre l'école : un répurgateur passé en Démonologie
	continuerait de lancer indéfiniment les sorts Saints qu'il avait déjà achetés. Ce contrôle
	est PARESSEUX, comme tout ce qui périme dans le jeu (CLAUDE.md §5) — aucun tick de fond,
	aucune migration de base : il se fait au passage, et réécrit le doc à ce moment-là.

	⚠️ Un sort n'est retiré QUE si son doc a été résolu ET que son école est identifiable ET
	qu'elle n'est pas pratiquée. Un id mort, un doc illisible ou une école non résoluble sont
	LAISSÉS EN PLACE : une lecture qui échoue ne doit jamais détruire ce qu'un joueur a payé.
	⚠️ Aucun contrôle de NIVEAU : l'école pratiquée à un niveau devenu insuffisant garde ses
	sorts. Ce qui se perd est un répertoire entier, jamais un sort trop cher pour son
	propriétaire actuel.
	⚠️ La barre d'action n'a rien à purger : `slots_actions.slots_effectifs` écarte déjà à la
	lecture toute case qui pointe un sort absent de `sorts_connus`.
	"""
	character = character or {}
	connus = character.get("sorts_connus") or []
	if not connus:
		return []

	partis, gardes = [], []
	for sort_id in connus:
		sort = normaliser_sort(get_doc(sort_id))
		ecole = magie_de_sort(sort, rules_vocations) if sort else None
		if sort is None or ecole is None or niveau_ecole(character, ecole, rules_vocations) is not None:
			gardes.append(sort_id)
			continue
		partis.append({"id": sort["id"], "nom": sort["nom"], "icon": sort["icon"],
					   "magie": ecole})
	if not partis:
		return []

	character["sorts_connus"] = gardes
	# ⚠️ Épinglés filtrés SEULEMENT si la clé existe : l'absence est un état à part entière
	# (auto-épinglage du premier sort connu, cf. `sorts_epingles_effectifs`) — la poser ici
	# figerait le choix du joueur sur ce qui lui reste, sans qu'il ait rien décidé.
	if "sorts_epingles" in character:
		restants = set(gardes)
		character["sorts_epingles"] = [s for s in (character.get("sorts_epingles") or [])
									   if s in restants]
	return partis


def sorts_epingles_effectifs(character: dict) -> list:
	"""Sorts d'accès rapide (barre d'icônes en combat), ids ordonnés.

	Champ `sorts_epingles` présent → liste filtrée aux sorts encore connus (ordre
	conservé, y compris vide = choix explicite du joueur). Champ absent (perso
	d'avant la feature ou jamais touché) → **auto-épinglage du premier sort connu**,
	sans migration."""
	character = character or {}
	connus = character.get("sorts_connus") or []
	if "sorts_epingles" in character:
		epingles = character.get("sorts_epingles") or []
		return [s for s in epingles if s in connus]
	return connus[:1]


# ── Écoles de magie (accès par école, pas par vocation) ──────────────────────────
# L'accès aux sorts se fait par ÉCOLE de magie (`magie` du sort, en miroir du `magie`
# de rules:vocations), pas par la vocation. Chaque personnage « pratique » son école
# native (dérivée de sa vocation) ; seules les vocations polyvalentes (lettré) peuvent
# ACHETER la pratique d'autres écoles avec des points de caractéristique. Le niveau de
# l'école native = niveau de la vocation native (vocations_niveaux) ; les écoles achetées
# ont leur propre niveau, stocké dans character["magies_apprises"] = {ecole: niveau}, et
# n'affectent JAMAIS les stats dérivées (anti-exploit).

def _vocations_entries(rules_vocations) -> list:
	"""Entrées de vocation depuis le doc rules:vocations (doc complet OU sa `value` nue).
	Tolère None → liste vide. Source unique de cette normalisation d'entrée."""
	entries = rules_vocations
	if isinstance(rules_vocations, dict):
		entries = rules_vocations.get("value") or []
	return entries or []


def _vocation_magie_map(rules_vocations) -> dict:
	"""Map {id_vocation: ecole} depuis le doc rules:vocations (doc complet OU sa `value`).
	Tolère None (→ map vide) et les vocations sans magie (→ chaîne vide)."""
	out = {}
	for v in _vocations_entries(rules_vocations):
		vid = (v or {}).get("id")
		if vid:
			out[str(vid)] = (str((v or {}).get("magie") or "")).strip()
	return out


def familles_exclues(voc, rules_vocations) -> set:
	"""Familles (cf. FAMILLE_*) que la vocation `voc` ne peut PAS apprendre — champ
	`familles_exclues` de son entrée dans rules:vocations, vide par défaut.

	C'est ce qui permet à une vocation de pratiquer une école SANS en pratiquer tout le
	répertoire : le répurgateur partage la Démonologie du démoniste, mais pas ses
	invocations. Lu à chaque appel (aucune dénormalisation sur le personnage) : retirer
	une exclusion en base rouvre aussitôt l'apprentissage, sans migration."""
	for v in _vocations_entries(rules_vocations):
		if str((v or {}).get("id") or "") == str(voc or ""):
			return {f for f in (str(x).strip() for x in ((v or {}).get("familles_exclues") or [])) if f}
	return set()


def apprentissage_exclu(doc, voc, rules_vocations) -> bool:
	"""Ce sort / cette compétence est-il d'une famille INTERDITE à cette vocation ?

	SOURCE UNIQUE de la règle, partagée par les sorts et les compétences, par les listes
	d'apprenables et par les endpoints qui les valident. Accepte indifféremment un doc brut
	ou sa vue normalisée (les deux portent `famille`). Doc sans famille ⇒ jamais exclu."""
	famille = famille_de(doc)
	return bool(famille) and famille in familles_exclues(voc, rules_vocations)


def ecole_native(voc, rules_vocations) -> str | None:
	"""École de magie de la vocation native, ou None si la vocation n'est pas magique."""
	return _vocation_magie_map(rules_vocations).get(str(voc or ""), "") or None


def magie_de_sort(sort: dict, rules_vocations) -> str | None:
	"""École d'un sort : champ `magie` s'il est présent, sinon fallback dérivé de sa
	`vocation` via rules:vocations (rétro-compat des sorts non ré-importés)."""
	m = (sort or {}).get("magie")
	if m:
		return str(m).strip()
	return _vocation_magie_map(rules_vocations).get(str((sort or {}).get("vocation") or ""), "") or None


def ecoles_de_grimoire(item_doc: dict, get_doc, rules_vocations) -> list:
	"""Écoles de magie enseignées par un grimoire = union des écoles de ses sorts, triée.

	Un grimoire ne porte AUCUNE école en propre : elle vit sur les sorts de son champ
	`sorts`. Un id mort est ignoré, un sort dont l'école n'est pas résoluble (vocation
	non magique) ne contribue rien — un grimoire peut donc légitimement rendre []."""
	if not est_grimoire(item_doc):
		return []
	out = set()
	for sort_id in (item_doc.get("sorts") or []):
		doc = get_doc(sort_id)
		if not doc:
			continue
		if (ecole := magie_de_sort(doc, rules_vocations)):
			out.add(ecole)
	return sorted(out)


def niveau_ecole(character: dict, ecole, rules_vocations) -> int | None:
	"""Niveau effectif d'une école POUR CE PERSONNAGE, ou None si non pratiquée.
	École native → niveau de la vocation native ; école achetée → magies_apprises."""
	character = character or {}
	if not ecole:
		return None
	native = ecole_native(character.get("voc"), rules_vocations)
	if ecole == native:
		return _as_int((character.get("vocations_niveaux") or {}).get(character.get("voc", ""), 0))
	apprises = character.get("magies_apprises") or {}
	if ecole in apprises:
		return _as_int(apprises[ecole])
	return None


def magies_pratiquees(character: dict, rules_vocations) -> dict:
	"""{ecole: niveau} de toutes les écoles pratiquées : native + achetées."""
	character = character or {}
	out = {}
	native = ecole_native(character.get("voc"), rules_vocations)
	if native:
		out[native] = _as_int((character.get("vocations_niveaux") or {}).get(character.get("voc", ""), 0))
	for ecole, niv in (character.get("magies_apprises") or {}).items():
		out[str(ecole)] = _as_int(niv)
	return out


def ecoles_du_monde(rules_vocations) -> list:
	"""Toutes les écoles de magie existantes (valeurs `magie` non vides), triées."""
	return sorted({m for m in _vocation_magie_map(rules_vocations).values() if m})


def peut_apprendre_magie(character: dict) -> bool:
	"""Vrai si la vocation du perso est polyvalente (lettré) et peut acheter des écoles."""
	return (character or {}).get("voc") in character_stats.MAGIE_POLYVALENTE_VOCATIONS


def ecoles_achetables(character: dict, rules_vocations) -> list:
	"""Écoles que le perso peut encore acheter (polyvalent uniquement, hors déjà pratiquées)."""
	if not peut_apprendre_magie(character):
		return []
	pratiquees = set(magies_pratiquees(character, rules_vocations))
	return [e for e in ecoles_du_monde(rules_vocations) if e not in pratiquees]


def cout_ecole(niveau) -> int:
	"""Coût en points pour acheter (niveau 0) ou monter une école : (niveau+1) × coeff
	(lecture via le module — world-var réassignée à chaud)."""
	return (_as_int(niveau) + 1) * character_stats.MAGIE_ECOLE_COUT_COEFF


def apprentissage_magies_payload(character: dict, rules_vocations) -> dict:
	"""État des écoles pour l'onglet ⚡ (rendu initial + resync) : écoles pratiquées
	(niveau, native/achetée, coût de montée) et écoles achetables (coût d'achat)."""
	native = ecole_native((character or {}).get("voc"), rules_vocations)
	pratiquees = magies_pratiquees(character, rules_vocations)
	return {
		"peut_apprendre": peut_apprendre_magie(character),
		"native": native,
		"pratiquees": [
			{"ecole": e, "niveau": n, "native": e == native,
			 "montable": e != native, "cout_montee": cout_ecole(n)}
			for e, n in sorted(pratiquees.items())
		],
		"achetables": [{"ecole": e, "cout": cout_ecole(0)}
					   for e in ecoles_achetables(character, rules_vocations)],
	}


def sorts_apprenables(character: dict, find_docs, resolve_ref, rules_vocations) -> list:
	"""Sorts achetables par le personnage : école pratiquée (native ou achetée), niveau
	d'école suffisant, famille non exclue par la vocation, pas déjà connu. Chaque entrée est
	enrichie de `cout_points`, `grimoire_ok` (grimoire enseignant porté) et `magie` (école
	résolue)."""
	connus = set((character or {}).get("sorts_connus") or [])
	exclues = familles_exclues((character or {}).get("voc"), rules_vocations)
	out = []
	for doc in find_docs({"type": "sort"}) or []:
		sort = normaliser_sort(doc)
		if not sort or sort["id"] in connus:
			continue
		# Famille interdite à cette vocation : le sort n'apparaît même pas dans la liste
		# (l'endpoint `apprendre_sort` refait le test — la liste n'est pas la garde).
		if sort["famille"] and sort["famille"] in exclues:
			continue
		ecole = magie_de_sort(sort, rules_vocations)
		niv = niveau_ecole(character, ecole, rules_vocations)
		if niv is None or niv < sort["niveau"]:
			continue
		sort["magie"] = ecole
		sort["cout_points"] = cout_apprentissage(sort)
		sort["grimoire_ok"] = grimoire_pour(character, sort["id"], resolve_ref) is not None
		out.append(sort)
	out.sort(key=lambda s: (s.get("magie") or "", s["niveau"], s["nom"]))
	return out


def sort_de_depart_valide(sort: dict | None, voc, rules_vocations) -> bool:
	"""Ce sort (vue normalisée) peut-il être le sort de départ de la vocation `voc` ?

	SOURCE UNIQUE de la règle, partagée par la liste de la création et par sa validation
	serveur : niveau 0, de l'ÉCOLE NATIVE de la vocation, d'une famille qu'elle peut
	apprendre (un répurgateur ne démarre pas sur une invocation qu'il ne pourrait acheter).
	Deux vocations de même école (druide/chaman) partagent donc la même liste."""
	if not sort or sort["niveau"] != 0:
		return False
	native = ecole_native(voc, rules_vocations)
	return (native is not None and magie_de_sort(sort, rules_vocations) == native
			and not apprentissage_exclu(sort, voc, rules_vocations))


def sorts_depart_par_vocation(find_docs, rules_vocations) -> dict:
	"""Sorts de départ groupés par vocation — choix à la création de personnage :
	{vocation: [{id, nom, icon, description}]}, cf. `sort_de_depart_valide`."""
	sorts = [s for doc in find_docs({"type": "sort"}) or [] if (s := normaliser_sort(doc))]
	out: dict = {}
	for entree in _vocations_entries(rules_vocations):
		voc = entree.get("id")
		lst = [{"id": s["id"], "nom": s["nom"], "icon": s["icon"],
				"description": s["description"]}
			   for s in sorts if sort_de_depart_valide(s, voc, rules_vocations)]
		if lst:
			out[voc] = sorted(lst, key=lambda x: x["nom"])
	return out


# ── Payloads UI ──────────────────────────────────────────────────────────────────

def _composants_payload(sort: dict, character: dict, resolve_ref_doc) -> list:
	"""Composants avec disponibilité + nom/icône résolus pour l'affichage."""
	out = []
	for c in composants_etat(sort, character):
		doc = resolve_ref_doc(c["item"]) or {}
		out.append({
			"item": c["item"],
			"nom": doc.get("nom", c["item"]),
			"icon": doc.get("icon", "❔"),
			"consomme": c["consomme"],
			"bonus": c["bonus"],
			"disponible": c["disponible"],
		})
	return out


def liste_sorts_payload(character: dict, get_doc, contexte: str) -> list:
	"""Sorts connus pour l'UI (rendu initial ET resync après action) : effets de base +
	composants avec disponibilité — le client affiche les bonus et envoie les ids engagés.
	Contexte "combat" : seuls les sorts à part instantanée (sélecteur 🔮). Contexte
	"exploration" : TOUS les sorts connus (onglet ⚡ = catalogue), drapeau `lancable`
	pour les seuls lançables hors combat."""
	out = []
	for sort in sorts_connus_docs(character, get_doc):
		if contexte == "combat" and not sort_utilisable_combat(sort):
			continue
		out.append({
			"lancable": True if contexte == "combat" else sort_utilisable_exploration(sort),
			"sort_id": sort["id"],
			"nom": sort["nom"],
			"icon": sort["icon"],
			"description": sort["description"],
			"niveau": sort["niveau"],
			"cout_pm": sort["cout_pm"],
			# Les deux autres notions de coût, à côté des PM de lancement : le client en
			# tire l'étiquette de la case ET le grisage (un sort maintenu n'est lançable
			# que si l'on peut payer le premier round). Sans elles, un joueur découvrirait
			# la facture APRÈS avoir cliqué.
			"incantation": sort["incantation"],
			"maintien": sort["maintien"],
			"cible": sort["cible"],
			"portee": sort["portee"],
			# Le client en tire l'étiquette de la case ET l'APERÇU des cases touchées
			# pendant le ciblage (scripts/zones_effet.js) : sans ce champ, un sort de
			# zone se lancerait à l'aveugle.
			"zone": sort["zone"],
			"effets": sort["effets"],
			# Bloc `invocation` (ou None) : le client en tire l'étiquette de la case — sans
			# lui, un sort d'invocation s'afficherait sans le moindre effet annoncé, ses
			# `effets` étant vides par construction.
			"invocation": sort["invocation"],
			"composants": _composants_payload(sort, character, get_doc),
		})
	return out

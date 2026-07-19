# utils/slots_actions.py
# Barre d'action de combat : une GRILLE DE SLOTS à positions stables, plutôt que la
# liste flex qui grandissait toute seule (ex-`sorts_epingles` / `competences_epinglees`).
#
# Le personnage stocke `slots_actions` : liste DENSE POSITIONNELLE de longueur
# COMBAT_SLOTS_MAX (index 0 = slot 1), trous = None. Une entrée est un dict
# {"type": …, "ref": …} :
#   - "attaque"     ref ∈ {"cac","jet","tir"}  — mode d'attaque
#   - "sort"        ref = id d'un sort connu
#   - "competence"  ref = id d'une compétence connue ACTIVE
#   - "consommable" ref = item_id (TYPE d'objet, jamais un index d'instance : le sac
#                   bouge à chaque ramassage, un index serait périmé au tour suivant)
#   - "ramasser" / "fuir" — sans ref
#
# ⚠️ INVARIANTE : les trois entrées OBLIGATOIRES (mêlée, ramasser, fuir) apparaissent
# exactement une fois chacune. Elles se DÉPLACENT librement (n'importe quelle position)
# mais ne peuvent jamais être retirées — une barre sans bouton de fuite enfermerait le
# joueur dans le combat. L'invariante est réparée À LA LECTURE (`slots_effectifs`), pas
# seulement à l'écriture : un doc bricolé à la main ne peut pas la violer.
#
# Champ ABSENT ⇒ dérivation depuis les anciens épinglés (mêlée/ramasser/fuir aux slots
# 1-2-3, puis sorts puis compétences à partir du slot 4) ⇒ aucune migration de base.
#
# Logique pure (get_doc / resolve_ref injectés), ne sauvegarde jamais — les endpoints
# persistent. Même contrat que utils/sorts.py et utils/competences.py.

from models import character_stats
from utils import competences as competences_util
from utils import sorts as sorts_util
from utils.characters import item_ref_id
from utils.consommables import est_consommable, effet_instantane

# Types d'entrée acceptés. "ramasser"/"fuir" n'ont pas de `ref` (l'action est unique).
TYPES_VALIDES = ("attaque", "sort", "competence", "consommable", "ramasser", "fuir")

# Modes d'attaque assignables. "cac" est obligatoire (on peut toujours frapper au poing,
# cf. `_weapon_attacks` qui garantit un profil de portée 1) ; jet et tir sont optionnels
# et se grisent quand l'arme correspondante n'est pas équipée.
MODES_ATTAQUE = ("cac", "jet", "tir")

# Les trois entrées que la barre porte TOUJOURS, dans leur ordre de placement par défaut.
ENTREES_OBLIGATOIRES = (
	{"type": "attaque", "ref": "cac"},
	{"type": "ramasser", "ref": ""},
	{"type": "fuir", "ref": ""},
)

# Icônes de repli des actions sans doc à interroger.
ICONES_DEFAUT = {
	"cac": "⚔", "jet": "🪃", "tir": "🏹",
	"ramasser": "🫳", "fuir": "🏃",
}

LIBELLES_DEFAUT = {
	"cac": "Corps à corps", "jet": "Jet", "tir": "Tir",
	"ramasser": "Ramasser", "fuir": "Fuir",
}


def slots_max() -> int:
	"""Nombre de cases de la barre. Lu VIA LE MODULE (jamais `from … import`) pour rester
	sensible au rechargement à chaud de `rules:world_variables`. Planché à la taille du
	socle obligatoire : une barre trop courte pour ⚔🫳🏃 serait injouable."""
	return max(len(ENTREES_OBLIGATOIRES), int(character_stats.COMBAT_SLOTS_MAX))


def normaliser_entree(entree) -> dict | None:
	"""Vue normalisée d'une entrée de slot, ou None si la forme est invalide. Ne vérifie
	PAS l'appartenance (le personnage connaît-il ce sort ?) : c'est le rôle de
	`_entree_possedee`, qui a besoin du personnage et de la base.

	Une entrée de SORT porte en plus un booléen **`composants`** : engager ou non les
	composants **consommés** au lancement. Les catalyseurs (`consomme:false`), eux, sont
	toujours engagés — ne rien dépenser pour s'en priver n'aurait aucune contrepartie.
	Défaut **True** = comportement historique de l'accès rapide (« engager tout le
	disponible »), donc les barres dérivées des anciens épinglés ne changent pas de
	comportement. Deux entrées d'un même sort qui diffèrent par ce flag sont DISTINCTES :
	le même sort peut occuper deux cases, une qui dépense et une qui économise."""
	entree = entree or {}
	if not isinstance(entree, dict):
		return None
	type_ = str(entree.get("type") or "")
	if type_ not in TYPES_VALIDES:
		return None
	ref = str(entree.get("ref") or "")
	if type_ in ("ramasser", "fuir"):
		return {"type": type_, "ref": ""}
	if type_ == "attaque":
		return {"type": type_, "ref": ref} if ref in MODES_ATTAQUE else None
	if not ref:
		return None
	if type_ == "sort":
		compo = entree.get("composants")
		return {"type": type_, "ref": ref, "composants": True if compo is None else bool(compo)}
	return {"type": type_, "ref": ref}


def est_obligatoire(entree) -> bool:
	"""Cette entrée fait-elle partie du socle intouchable ? Source unique du test —
	`vider_slot`, `poser_slot`, la réparation d'invariante et l'UI s'y réfèrent tous."""
	e = normaliser_entree(entree)
	return e in [dict(o) for o in ENTREES_OBLIGATOIRES] if e else False


def _memes_entrees(a, b) -> bool:
	na, nb = normaliser_entree(a), normaliser_entree(b)
	return na is not None and na == nb


def _entree_possedee(entree: dict, character: dict, get_doc) -> bool:
	"""Le personnage a-t-il encore de quoi honorer cette entrée ? Filtre les refs devenues
	caduques (sort désappris, potion épuisée du sac au sens du TYPE, compétence oubliée).
	Un consommable absent du sac reste POSSÉDÉ au sens des slots : il occupe sa case et
	s'affiche grisé — le joueur rachètera des potions et retrouvera son bouton en place."""
	type_, ref = entree["type"], entree["ref"]
	if type_ in ("attaque", "ramasser", "fuir"):
		return True
	if type_ == "sort":
		return ref in (character.get("sorts_connus") or [])
	if type_ == "competence":
		if ref not in (character.get("competences_connues") or []):
			return False
		comp = competences_util.normaliser_competence(get_doc(ref))
		return bool(comp and competences_util.est_active(comp))
	if type_ == "consommable":
		# Le TYPE doit rester un consommable utilisable en combat ; la présence d'un
		# exemplaire est une question de disponibilité, pas d'appartenance.
		doc = get_doc(ref)
		return bool(doc and est_consommable(doc) and effet_instantane(doc))
	return False


def _slots_derives(character: dict, get_doc, taille: int) -> list:
	"""Barre d'un personnage qui n'a JAMAIS configuré ses slots : le socle obligatoire aux
	trois premières cases, puis les anciens épinglés (sorts d'abord, compétences ensuite)
	à la suite. C'est la migration à la lecture — elle reproduit exactement la barre que
	le joueur avait avant la refonte, sans toucher à la base."""
	slots = [None] * taille
	for i, obligatoire in enumerate(ENTREES_OBLIGATOIRES):
		if i < taille:
			slots[i] = dict(obligatoire)

	# Normalisées comme celles qui viennent de la base : sans quoi une barre migrée
	# livrerait des entrées de sort SANS le flag `composants`, et deux formes
	# circuleraient jusque dans le client.
	anciens = [normaliser_entree({"type": "sort", "ref": s})
	           for s in sorts_util.sorts_epingles_effectifs(character)]
	anciens += [normaliser_entree({"type": "competence", "ref": c})
	            for c in competences_util.competences_epinglees_effectives(character, get_doc)]
	anciens = [e for e in anciens if e]

	libres = (i for i in range(taille) if slots[i] is None)
	for entree in anciens:
		position = next(libres, None)
		if position is None:
			break
		slots[position] = entree
	return slots


def _reparer_obligatoires(slots: list) -> list:
	"""Garantit l'invariante : chaque entrée obligatoire présente exactement une fois.
	Les doublons sont effacés (on garde le premier), les manquantes replacées dans la
	première case libre — et, en dernier recours, en ÉCRASANT la dernière case, car une
	barre pleine d'entrées libres ne doit pas pouvoir coûter au joueur son bouton de fuite."""
	for obligatoire in ENTREES_OBLIGATOIRES:
		positions = [i for i, s in enumerate(slots) if _memes_entrees(s, obligatoire)]
		for doublon in positions[1:]:
			slots[doublon] = None
		if positions:
			continue
		libre = next((i for i, s in enumerate(slots) if s is None), None)
		slots[len(slots) - 1 if libre is None else libre] = dict(obligatoire)
	return slots


def slots_effectifs(character: dict, get_doc) -> list:
	"""Barre effective du personnage : liste de longueur `slots_max()`, trous = None.

	Champ `slots_actions` présent → normalisé, tronqué/complété à la taille courante
	(la world-var peut changer à chaud), purgé des refs caduques, invariante réparée.
	Champ absent → barre dérivée des anciens épinglés (cf. `_slots_derives`)."""
	character = character or {}
	taille = slots_max()

	if "slots_actions" not in character:
		return _reparer_obligatoires(_slots_derives(character, get_doc, taille))

	brut = character.get("slots_actions") or []
	slots = []
	for i in range(taille):
		entree = normaliser_entree(brut[i]) if i < len(brut) else None
		if entree and not _entree_possedee(entree, character, get_doc):
			entree = None
		slots.append(entree)
	return _reparer_obligatoires(slots)


def _valider_position(position, taille: int) -> int:
	try:
		position = int(position)
	except (TypeError, ValueError):
		raise ValueError("Position de slot invalide")
	if not 1 <= position <= taille:
		raise ValueError(f"Position de slot hors barre (1–{taille})")
	return position


def poser_slot(character: dict, position, entree, get_doc) -> list:
	"""Place une entrée à `position`. Mute `character["slots_actions"]` SANS sauvegarder.

	Deux règles qui protègent l'invariante :
	- poser une obligatoire déjà présente ailleurs la DÉPLACE (on efface son ancienne
	  case) au lieu de la dupliquer ;
	- si la case cible contenait une obligatoire, les deux entrées s'ÉCHANGENT au lieu
	  que la seconde soit écrasée — sinon déposer un sort sur la case de 🏃 supprimerait
	  la fuite, que `_reparer_obligatoires` remettrait ailleurs à l'insu du joueur.

	Lève ValueError (→ 422 côté router) sur position hors barre, forme invalide, ou
	entrée que le personnage ne possède pas."""
	character = character if character is not None else {}
	taille = slots_max()
	position = _valider_position(position, taille)

	nouvelle = normaliser_entree(entree)
	if nouvelle is None:
		raise ValueError("Entrée de slot invalide")
	if not _entree_possedee(nouvelle, character, get_doc):
		raise ValueError("Action indisponible pour ce personnage")

	slots = slots_effectifs(character, get_doc)
	idx = position - 1
	ancienne_cible = slots[idx]

	precedente = next((i for i, s in enumerate(slots) if _memes_entrees(s, nouvelle)), None)
	slots[idx] = nouvelle
	if precedente is not None and precedente != idx:
		# Déplacement : la case d'origine reçoit ce que la cible portait (échange) si
		# c'était une obligatoire, sinon elle se vide.
		slots[precedente] = ancienne_cible if est_obligatoire(ancienne_cible) else None
	elif est_obligatoire(ancienne_cible):
		# L'obligatoire évincée doit atterrir quelque part : première case libre.
		libre = next((i for i, s in enumerate(slots) if s is None), None)
		if libre is None:
			raise ValueError("Barre pleine : videz d'abord une case")
		slots[libre] = ancienne_cible

	character["slots_actions"] = slots
	return slots


def vider_slot(character: dict, position, get_doc) -> list:
	"""Vide une case. Refuse (ValueError → 422) sur une obligatoire : on la DÉPLACE
	(`deplacer_slot`), on ne la supprime pas."""
	character = character if character is not None else {}
	position = _valider_position(position, slots_max())
	slots = slots_effectifs(character, get_doc)
	idx = position - 1
	if est_obligatoire(slots[idx]):
		raise ValueError("Cette action est obligatoire : déplacez-la au lieu de la retirer")
	slots[idx] = None
	character["slots_actions"] = slots
	return slots


def deplacer_slot(character: dict, source, cible, get_doc) -> list:
	"""Échange deux cases (glisser-déposer). Seul geste capable de bouger une entrée
	obligatoire — d'où l'échange plutôt que l'écrasement."""
	character = character if character is not None else {}
	taille = slots_max()
	source = _valider_position(source, taille)
	cible = _valider_position(cible, taille)
	slots = slots_effectifs(character, get_doc)
	i, j = source - 1, cible - 1
	slots[i], slots[j] = slots[j], slots[i]
	character["slots_actions"] = slots
	return slots


def _index_consommable(character: dict, item_id: str) -> int | None:
	"""Index dans le sac du PREMIER exemplaire de ce type d'objet, ou None. C'est le pont
	entre le slot (qui référence un TYPE) et l'API de combat (qui exige index + item_id
	pour désigner une instance, les exemplaires d'un même item pouvant différer de poids).
	Résolu à chaque rendu, jamais persisté."""
	for idx, ref in enumerate((character or {}).get("inventaire") or []):
		if item_ref_id(ref) == item_id:
			return idx
	return None


def slots_payload(character: dict, get_doc, resolve_ref_fn=None) -> list:
	"""Ce que consomme l'UI : une entrée par case, avec de quoi l'afficher (nom, icône)
	et l'activer. `disponible` = l'action est réalisable dans l'absolu (potion en sac,
	compétence connue) ; les conditions de TOUR (portée, PM, budget d'action) restent au
	client, qui les réévalue à chaque rafraîchissement de l'état du combat."""
	character = character or {}
	out = []
	for position, entree in enumerate(slots_effectifs(character, get_doc), start=1):
		if entree is None:
			out.append({"position": position, "type": None, "ref": "", "nom": "",
			            "icon": "", "disponible": False, "obligatoire": False})
			continue

		type_, ref = entree["type"], entree["ref"]
		vue = {
			"position": position, "type": type_, "ref": ref,
			"nom": LIBELLES_DEFAUT.get(ref or type_, ""),
			"icon": ICONES_DEFAUT.get(ref or type_, ""),
			"disponible": True,
			"obligatoire": est_obligatoire(entree),
		}

		if type_ == "sort":
			doc = sorts_util.normaliser_sort(get_doc(ref))
			vue["nom"] = (doc or {}).get("nom", ref)
			vue["icon"] = (doc or {}).get("icon") or "🔮"
			vue["disponible"] = doc is not None
			# Le RÉGLAGE seulement — pas la disponibilité des composants. La calculer ici
			# dupliquerait ce que fait déjà `liste_sorts_payload`, et la valeur serait
			# périmée dès le premier lancement : le client la dérive de SORTS, qu'il
			# resynchronise après chaque sort.
			vue["composants"] = entree.get("composants", True)
		elif type_ == "competence":
			doc = competences_util.normaliser_competence(get_doc(ref))
			vue["nom"] = (doc or {}).get("nom", ref)
			vue["icon"] = (doc or {}).get("icon") or "⚡"
			vue["disponible"] = doc is not None
		elif type_ == "consommable":
			doc = get_doc(ref)
			vue["nom"] = (doc or {}).get("nom", ref)
			vue["icon"] = (doc or {}).get("icon") or "🧪"
			# L'index de l'exemplaire à consommer : None = plus rien en sac → grisé.
			index = _index_consommable(character, ref)
			vue["index"] = index
			vue["disponible"] = index is not None

		out.append(vue)
	return out

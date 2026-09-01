# utils/donjon.py
# Donjons : un lieu de combat FERMÉ, dont l'entrée est gardée par un PNJ et le contenu
# curaté par un document — et la « commission d'éradication » qui y donne droit.
#
# Un doc `donjon:*` dit TROIS choses, et rien d'autre :
#
#   {
#     "_id": "donjon:xxx", "type": "donjon", "nom": "...",
#     "portail": "lieu:yyy",                    # informatif (lore) : d'où l'on descend
#     "niveau_max": 3,                          # plafond de GRADE (optionnel, cf. plus bas)
#     "niveau_min": 2,                          # plancher de GRADE (optionnel, même cascade)
#     "battle_maps": [                          # les salles, et QUI y vit
#       {"lieu": "lieu:zzz", "especes": ["espece:a", "espece:b"],
#        "niveau_max": 4, "niveau_min": 2, "nb_monstres": 3}
#     ]
#   }
#
# ⚠️ `niveau_max` EST LE BOUTON DE DIFFICULTÉ, et il n'est pas optionnel en pratique. Un lieu
# explorable borne implicitement ses grades par la distribution de ses zones d'influence
# (`resolve_profil_weights`) ; un donjon n'a pas de zones, donc RIEN ne le borne — sans ce
# plafond, l'élite reçoit le profil de plus haut niveau de toute la base (niveau 6), ce qui
# donne des monstres à 5 points d'armure et ~400 PV : mathématiquement imbattable pour qui
# vient de décrocher son rang D. Le plafond se pose par SALLE (elle prime) ou pour le donjon
# entier ; absent = aucune borne (comportement historique, à réserver aux donjons profonds).
#
# ⚠️ `niveau_min` est son SYMÉTRIQUE, et suit la MÊME cascade (salle → donjon → aucune) : il
# empêche une salle de fin d'opposer encore des Novices. Les deux bornes valent pour toute la
# salle — l'ÉLITE mandatée comme son ESCORTE (`_profils_dans_fourchette`). Elles ne sont
# toutefois pas symétriques en cas de conflit : le plancher CÈDE au plafond plutôt que de
# vider la salle (cf. `_profils_dans_fourchette`).
#
# ⚠️ `nb_monstres` (même cascade encore) fixe l'EFFECTIF de la salle, là où le moteur calcule
# sinon `3 + compagnons // 2`. C'est ce qui permet à une fiction de COMPTER ses ennemis : dès
# qu'un dialogue dit « trois, toujours les trois mêmes », le bonus de compagnons dément le
# texte sous les yeux du joueur. L'effectif écrit est donc FIXE — la fiction l'emporte sur
# l'équilibrage automatique, salle par salle, et seulement là où l'auteur le demande.
#
# ⚠️ POURQUOI un doc à part, et pas des `rencontres`/`zone_influences` sur le lieu : une
# salle de donjon est un lieu `categorie:"battle_map"` — il n'a ni `connection`, ni
# `lieu_parent`, ni grille d'exploration. On n'y « marche » pas, donc il n'a pas de zones
# d'influence où placer des espèces, et `resolve_profil_weights` n'a rien à résoudre. Le
# contenu d'un donjon est CURATÉ (choisi à la main, pièce par pièce), là où celui d'un lieu
# explorable est tiré par géométrie. D'où : pas de position, pas de zones, et le grade de
# l'élite = le profil compatible de plus haut niveau de la base (`_profil_max_compatible`).
#
# La COMMISSION D'ÉRADICATION est une quête `chasse` ORDINAIRE (`objectif.type == "chasse"`),
# pas un troisième système : elle est donc progressée par `quetes.maj_progress_chasse` (déjà
# appelée dans `finalize_combat`) et focalisable comme les autres — aucune ligne à ajouter
# dans utils/combat.py ni utils/quetes.py. Seule sa GÉNÉRATION diffère (tirée dans le doc
# donjon, pas dans les zones du lieu). Elle se distingue d'une épreuve de rang par
# `source == "commission"` — `utils/chasse.py` filtrant partout sur `source == "rang"`, les
# deux familles ne se confondent jamais.
#
# ⚠️ Une seule commission active à la fois (`commission_active`), et pas de `unique` : une
# commission soldée peut être redemandée. C'est un contrat de travail répétable, pas une
# étape de scénario.
#
# Logique pure (DB injectée : get_doc_fn / find_docs_fn), mute sans jamais sauvegarder —
# l'endpoint persiste. Pattern de utils/transport.py et utils/chasse.py.

import random
import uuid

from models import character_stats
from utils.characters import lieu_label, victoire_acquise
from utils import acces, chasse, quetes
from utils.zones import profils_compatibles


# Rang d'une commission quand AUCUNE barrière `rang_min` ne la commande (cf.
# `rang_commission`). Valeur historique, conservée pour ne rien changer au contenu déjà en
# base : un donjon libre d'accès reste étiqueté `D`.
RANG_COMMISSION_DEFAUT = "D"


# ── Lecture du doc donjon ────────────────────────────────────────────────────────

def battle_maps_de(donjon_doc: dict) -> list:
	"""Les entrées `{lieu, especes}` du donjon (liste vide si le doc est absent/mal formé)."""
	entrees = (donjon_doc or {}).get("battle_maps") or []
	return [e for e in entrees if isinstance(e, dict) and e.get("lieu")]


def battle_map_entry(donjon_doc: dict, lieu_id: str) -> dict | None:
	"""L'entrée du donjon décrivant CETTE salle, ou None. C'est elle qui porte le pool
	d'espèces du combat qu'on y déclenche."""
	for e in battle_maps_de(donjon_doc):
		if e.get("lieu") == lieu_id:
			return e
	return None


def donjon_de_lieu(lieu_id: str, find_docs_fn) -> dict | None:
	"""Le donjon dont une salle est `lieu_id` (None si aucun). C'est le SEUL lien salle →
	donjon : un lieu `battle_map` ne sait pas à quel donjon il appartient (il est aussi
	tirable comme décor de combat ordinaire par `combat.select_battle_map`), c'est le donjon
	qui le revendique."""
	if not lieu_id:
		return None
	for d in (find_docs_fn({"type": "donjon"}) or []):
		if battle_map_entry(d, lieu_id):
			return d
	return None


def _niveau(profil: dict) -> int:
	"""Niveau d'un profil, défaut 1 — lu partout par la même formule (un `niveau: 0` ou
	`null` vaut 1, comme dans le reste du moteur)."""
	return int((profil or {}).get("niveau", 1) or 1)


def _borne_de(donjon_doc: dict, lieu_id: str | None, cle: str) -> int | None:
	"""Cascade d'une borne de grade : la SALLE prime, le donjon sert de défaut, sinon None.

	⚠️ Écrite UNE fois pour les deux bornes. `niveau_max` et `niveau_min` doivent se résoudre
	exactement pareil — deux cascades séparées finiraient par diverger (l'une tolérant une
	valeur illisible que l'autre refuse), et un contenu se retrouverait avec un plancher lu
	sur la salle et un plafond lu sur le donjon sans que rien ne le signale."""
	entree = battle_map_entry(donjon_doc, lieu_id) if lieu_id else None
	for source in (entree, donjon_doc):
		brut = (source or {}).get(cle)
		if brut is not None:
			try:
				return int(brut)
			except (TypeError, ValueError):
				# Donnée illisible : on ne DEVINE pas une borne (ni 0, qui bloquerait tout,
				# ni « pas de borne », qui rendrait le donjon imbattable en silence). On
				# passe à la source suivante, et le linter du contenu reste le garde-fou.
				continue
	return None


def niveau_max_de(donjon_doc: dict, lieu_id: str = None) -> int | None:
	"""Plafond de grade applicable à cette salle : son `niveau_max` s'il en a un, sinon celui
	du donjon, sinon None (aucune borne). La salle PRIME — une antichambre et le fond d'une
	mine n'ont aucune raison d'opposer la même chose."""
	return _borne_de(donjon_doc, lieu_id, "niveau_max")


def niveau_min_de(donjon_doc: dict, lieu_id: str = None) -> int | None:
	"""Plancher de grade applicable à cette salle — même cascade que `niveau_max_de`.

	Il répond au besoin inverse du plafond : empêcher qu'une salle de fin de donjon oppose
	encore des Novices. Champ absent ⇒ aucun plancher, donc le comportement d'avant à la
	lettre (aucune migration)."""
	return _borne_de(donjon_doc, lieu_id, "niveau_min")


# Garde-fou de l'effectif d'une salle. Ce n'est pas une devinette (le projet n'en fait pas
# sur une donnée illisible) mais une borne : un `nb_monstres: 30` tapé pour `3` produirait un
# combat injouable et un placement interminable, sans que rien ne le signale.
NB_MONSTRES_MAX = 12


def nb_monstres_de(donjon_doc: dict, lieu_id: str = None) -> int | None:
	"""Effectif EXACT de la salle, ou None si l'auteur n'en impose aucun — même cascade que
	les bornes de grade (la salle prime, le donjon sert de défaut).

	⚠️ C'est le seul moyen de tenir une fiction qui COMPTE ses ennemis. Le défaut du moteur
	(`3 + compagnons // 2`) est une règle d'équilibrage : elle ajoute un monstre par tranche
	de deux compagnons, ce qui est juste pour un donjon générique et faux dès qu'un dialogue
	dit « trois, toujours les trois mêmes ». Champ absent ⇒ le défaut s'applique, donc
    comportement d'avant à la lettre et AUCUNE migration.

	⚠️ L'effectif fixé est FIXE : le bonus de compagnons ne s'y ajoute pas. C'est le prix
	assumé — on choisit la fiction contre l'équilibrage automatique, salle par salle.
	⚠️ Planché à 1 : une salle gardée sans opposition rendrait `instantiate_monsters` vide,
	donc un 422 « Ce passage ne mène à aucun danger connu » — une porte morte au lieu d'un
	combat. Plafonné à `NB_MONSTRES_MAX`."""
	brut = _borne_de(donjon_doc, lieu_id, "nb_monstres")
	if brut is None:
		return None
	return max(1, min(NB_MONSTRES_MAX, brut))


def _profils_dans_fourchette(profils: list, niveau_max: int | None,
							 niveau_min: int | None = None) -> list:
	"""Les profils utilisables dans la fourchette de grade `[niveau_min, niveau_max]`.

	⚠️ LES DEUX BORNES SONT DES SOUHAITS, PAS DES GARDES — et elles ne se valent pas en cas
	de conflit. La règle, dans l'ordre :

	1. le PLAFOND s'applique ; s'il est si bas qu'il n'admet aucun profil, on retombe sur
	   les profils de plus bas niveau disponibles (règle d'origine, inchangée) ;
	2. le PLANCHER s'applique ensuite ; s'il ne laisse rien (plancher au-dessus du plafond,
	   ou aucun profil compatible à ce niveau), il est IGNORÉ et l'on garde le résultat du
	   plafond.

	Le plancher cède donc toujours au plafond. C'est délibéré et c'est le prolongement du
	choix déjà fait pour le plafond : mieux vaut un donjon trop facile qu'un donjon VIDE de
	monstres — `instantiate_monsters` sans profil retomberait sur le point médian de
	l'espèce, tous grades confondus, ce qui est précisément ce que ces bornes cherchent à
	éviter. Un donjon trop tendre est un défaut visible en jeu ; un donjon sans opposition
	est un blocage, et un `niveau_min: 4` posé par erreur sous un `niveau_max: 2` ne doit pas
	vider la salle en silence.
	"""
	if niveau_max is None:
		sous = list(profils or [])
	else:
		sous = [p for p in (profils or []) if _niveau(p) <= niveau_max]
		if not sous and profils:
			plancher = min(_niveau(p) for p in profils)
			sous = [p for p in profils if _niveau(p) == plancher]
	if niveau_min is None:
		return sous
	hauts = [p for p in sous if _niveau(p) >= niveau_min]
	return hauts or sous


def especes_de_salle(donjon_doc: dict, lieu_id: str, get_doc_fn) -> list:
	"""Docs `espece:*` peuplant cette salle (ceux qui existent réellement en base)."""
	entree = battle_map_entry(donjon_doc, lieu_id) or {}
	docs = []
	for eid in entree.get("especes") or []:
		doc = get_doc_fn(eid)
		if doc:
			docs.append(doc)
	return docs


# ── Grade de l'élite ────────────────────────────────────────────────────────────

def _profil_max_compatible(espece_doc: dict, profils: list) -> dict | None:
	"""Profil de plus haut niveau COMPATIBLE avec l'espèce (`restriction_tags ⊆ tags`), parmi
	les `profils` fournis. Égalité de niveau → tirage au hasard.

	⚠️ Prend la LISTE des profils, pas un `find_docs_fn` : `tirer_cible` l'appelle une fois
	par espèce du donjon, et `_contexte` (routers/pnj.py) appelle `tirer_cible` à CHAQUE
	rendu de nœud de dialogue — une requête par espèce et par affichage serait gratuite.

	⚠️ Pas de `resolve_profil_weights` ici, contrairement à `chasse._profils_compatibles` :
	il n'y a ni zone d'influence ni position dans un donjon. Le contenu étant curaté à la
	main, l'élite est simplement « ce que la base sait faire de plus redoutable » pour cette
	espèce — un donjon n'est pas censé être tendre."""
	# Prédicat PARTAGÉ (`zones.profil_compatible`), jamais recopié : c'est la même règle qui
	# borne l'ACCOMPAGNEMENT dans `instantiate_monsters` et le grade d'une élite de chasse.
	compat = profils_compatibles(profils, espece_doc)
	if not compat:
		return None
	niv_max = max(int(p.get("niveau", 1) or 1) for p in compat)
	return random.choice([p for p in compat if int(p.get("niveau", 1) or 1) == niv_max])


def tirer_cible(donjon_doc: dict, get_doc_fn, find_docs_fn) -> dict | None:
	"""Choisit la proie d'une commission : `{lieu, lieu_doc, espece, profil}` (docs résolus),
	ou None si le donjon n'offre aucune cible jouable.

	Une salle ne compte que si son lieu existe ET porte une grille (`cells`) : sans grille,
	`create_combat_doc` retomberait sur une carte ouverte générique et le décor du donjon
	serait perdu. Une espèce ne compte que si un profil lui est compatible.

	Le grade de l'élite est le plus haut de la FOURCHETTE de la salle (`niveau_min_de` /
	`niveau_max_de`). Le plancher ne la change qu'au cas limite : elle prend déjà le plus
	haut grade compatible, il ne joue donc que si le plafond de la salle admettait des
	profils qu'aucune espèce ne peut porter et que le repli descendait trop bas."""
	profils = find_docs_fn({"type": "profil"}) or []
	candidats = []
	for entree in battle_maps_de(donjon_doc):
		lieu_doc = get_doc_fn(entree["lieu"])
		if not lieu_doc or not lieu_doc.get("cells"):
			continue
		dispo = _profils_dans_fourchette(
			profils,
			niveau_max_de(donjon_doc, entree["lieu"]),
			niveau_min_de(donjon_doc, entree["lieu"]),
		)
		for espece_doc in especes_de_salle(donjon_doc, entree["lieu"], get_doc_fn):
			profil = _profil_max_compatible(espece_doc, dispo)
			if profil:
				candidats.append({
					"lieu": entree["lieu"], "lieu_doc": lieu_doc,
					"espece": espece_doc, "profil": profil,
				})
	if not candidats:
		return None
	return random.choice(candidats)


# ── Construction de la commission ───────────────────────────────────────────────

def rang_commission(bureau_doc: dict, lieu_doc: dict) -> str:
	"""Rang AFFICHÉ d'une commission : **le rang qui commande réellement son accès**, pris
	sur les barrières de la chaîne — la SALLE visée et le BUREAU qui la mandate —, le plus
	élevé des deux l'emportant. Aucune barrière de rang ⇒ `RANG_COMMISSION_DEFAUT`.

	⚠️ Lire la seule salle ne suffirait pas, et c'est le cœur du sujet : dans la chaîne
	écrite, la mine est gardée par un `quete_active` (« montre ton mandat »), et c'est le
	BUREAU du maître de guilde qui porte le `rang_min` (la porte de Borin). Le prix d'entrée
	d'une commission, c'est la porte la plus stricte qu'il faut franchir pour l'obtenir —
	pas seulement celle qui se trouve au bout.

	Une commission n'a pas de `rang` d'auteur (elle est générée) : le premier argument de
	`acces.rang_de_quete` est donc None. Tout le reste de la règle — maximum des seuils,
	bornage sur l'échelle, repli — vit là-bas, en SOURCE UNIQUE partagée avec les offres
	écrites (`escorte.rang_de_offre`) : aucune exception, aucun comportement à faire diverger."""
	return acces.rang_de_quete(
		None,
		acces.rang_min_du_lieu(lieu_doc),
		acces.rang_min_du_lieu(bureau_doc),
		defaut=RANG_COMMISSION_DEFAUT,
	)


def construire_commission(bureau_doc: dict, cible: dict) -> dict | None:
	"""Doc `quete:*` d'une commission d'éradication (NON persisté : l'acceptation en fait un
	snapshot, comme les épreuves de rang). None si la cible est incomplète.

	⚠️ Aucune `position` dans l'objectif : on n'entre pas dans un donjon en marchant sur une
	case, mais en passant devant son gardien. `dans_zone_chasse` traite l'absence de position
	comme « contrainte de lieu seule », qui est exactement la règle voulue ici."""
	if not cible or not cible.get("espece") or not cible.get("profil"):
		return None
	espece_doc, profil = cible["espece"], cible["profil"]
	lieu_doc = cible.get("lieu_doc") or {}
	niv = int(profil.get("niveau", 1) or 1)
	grade = chasse.qualificatif_de(profil)
	nom = espece_doc.get("nom") or (espece_doc.get("_id") or "").split(":", 1)[-1]
	lieu_nom = lieu_label(lieu_doc, cible.get("lieu") or "")
	xp = max(1, round(quetes._xp_unitaire(espece_doc, niv) * character_stats.QUETE_CHASSE_XP_FACTEUR))
	cuivre = max(0, round(xp * character_stats.QUETE_CUIVRE_PAR_XP))
	sub = (bureau_doc.get("_id", "") or "").split(":", 1)[-1]
	return {
		"_id": f"quete:{sub}_commission_{uuid.uuid4().hex[:12]}",
		"type": "quete",
		"source": "commission",
		"giver": bureau_doc.get("_id"),
		"lieu_parent": bureau_doc.get("lieu_parent"),
		"titre": f"Commission d'éradication : le {nom} « {grade} »",
		"description": (
			f"La Guilde mandate une compagnie pour purger {lieu_nom}. Un {nom} « {grade} » y "
			f"tient les galeries : abattez-le, et le rapport suffira à rouvrir le chantier."
		),
		"rang": rang_commission(bureau_doc, lieu_doc),
		"objectif": {
			"type": "chasse",
			"cible": espece_doc["_id"],
			"lieu": cible["lieu"],
			"profil": profil["_id"],
			"quantite": 1,
		},
		"recompenses": {"xp": xp, "cuivre": cuivre, "items": []},
		"narration": _narration_commission(nom, grade, lieu_nom),
		"statut": "offerte",
	}


def _narration_commission(nom: str, grade: str, lieu_nom: str) -> str:
	"""Ambiance pré-combat à la descente dans le donjon (l'espèce variant, elle est générée
	à la volée, pas figée dans un nœud de dialogue — même parti que `chasse._narration_rang`)."""
	return (
		f"L'air de {lieu_nom} est saturé de poussière de pierre. Quelque part dans le noir, "
		f"un {nom} « {grade} » a fait des galeries son territoire — et il vous a entendus venir "
		f"bien avant que vous ne le voyiez."
	)


# ── État joueur ─────────────────────────────────────────────────────────────────

def commission_active(character: dict) -> dict | None:
	"""LA commission en cours (une seule à la fois), ou None."""
	for q in (character or {}).get("quetes_actives") or []:
		if q.get("source") == "commission":
			return q
	return None


def commission_active_pour_lieu(character: dict, lieu_id: str) -> dict | None:
	"""La commission en cours qui vise CETTE salle, ou None — c'est elle qui décide de l'élite
	à faire surgir dans le combat qu'on y déclenche."""
	q = commission_active(character)
	if q and (q.get("objectif") or {}).get("lieu") == lieu_id:
		return q
	return None


def commission_a_rapporter(character: dict) -> dict | None:
	"""La commission dont l'élite est tombée (`progress >= quantite`) mais qui n'a pas encore
	été soldée au bureau. La progression vient de `quetes.maj_progress_chasse`, générique."""
	q = commission_active(character)
	if q and quetes.objectif_atteint(character, q):
		return q
	return None


def offre_commission_pour(character: dict, bureau_doc: dict, donjon_doc: dict,
						  get_doc_fn, find_docs_fn) -> dict | None:
	"""La commission que ce bureau peut confier MAINTENANT, ou None (une déjà en cours, ou
	donjon sans cible jouable). Lecture pure : rien n'est muté, rien n'est mémorisé.

	⚠️ Pas de champ transitoire `*_offert` ici, contrairement à `transport`/`rang` : l'offre
	est REBÂTIE à chaque affichage. Ça se voit — la cible peut changer entre deux ouvertures
	du dialogue —, et c'est assumé : le maître de guilde puise dans une pile de contrats, il
	ne réserve pas un dossier au joueur qui n'a rien signé."""
	if commission_active(character):
		return None
	cible = tirer_cible(donjon_doc, get_doc_fn, find_docs_fn)
	if not cible:
		return None
	return construire_commission(bureau_doc, cible)


def accepter_commission(character: dict, offre: dict) -> dict | None:
	"""Empile le snapshot de l'offre dans `quetes_actives` (mute, sans save). None si l'offre
	est vide. `source`/`narration` sont reposés APRÈS le snapshot, qui ne copie que les champs
	communs à toutes les quêtes (miroir de `chasse.accepter_rang`)."""
	if not offre:
		return None
	snap = quetes.snapshot_quete(offre)
	snap["type"] = "quete"
	snap["source"] = "commission"
	snap["narration"] = offre.get("narration")
	character.setdefault("quetes_actives", []).append(snap)
	return snap


def solder_commission(character: dict, quete_id: str) -> dict | None:
	"""Rend compte au bureau d'une commission accomplie : XP + prime, quête archivée (mute
	sans save). None si la quête est introuvable ou pas encore accomplie. Miroir de
	`chasse.solder_rang`, SANS promotion de rang : une commission paie, elle n'élève pas."""
	actives = (character or {}).get("quetes_actives") or []
	q = next(
		(x for x in actives
		 if (x.get("id") or x.get("_id")) == quete_id and x.get("source") == "commission"),
		None,
	)
	if q is None or not quetes.objectif_atteint(character, q):
		return None
	recap = quetes.appliquer_recompenses(character, q)
	character["quetes_actives"] = [x for x in actives if x is not q]
	character.setdefault("quetes_terminees", []).append({
		"id": q.get("id") or q.get("_id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", "D"),
		# ⚠️ `source` + `lieu` en plus de la forme archivée habituelle : sans eux, l'archive
		# ne dit pas QUEL donjon a été purgé, et plus rien ne distingue « la mine est
		# nettoyée » de « je n'y suis jamais allé » (cf. `donjon_purge`). Les deux clés sont
		# inertes pour le reste du jeu, qui ne lit que `titre`/`rang`/`termine_at`.
		"source": "commission",
		"lieu": (q.get("objectif") or {}).get("lieu"),
		"termine_at": quetes.now_epoch(),
	})
	return {"recompenses": recap}


def donjon_purge(character: dict, lieu_id: str) -> bool:
	"""La menace de CETTE salle a-t-elle été éliminée — que le rapport soit rendu ou non ?

	Deux traces possibles : la commission encore active dont l'objectif est atteint (le joueur
	revient du donjon mais n'a pas encore rendu compte), ou l'archive d'une commission soldée
	visant ce lieu. C'est ce que le gardien doit savoir pour dire si les mineurs descendent.

	⚠️ Se distingue de `commission_a_rapporter` (le laps de temps AVANT le rapport) : cette
	fonction reste vraie APRÈS. ⚠️ Une commission soldée avant l'ajout de `lieu` à l'archive
	n'est pas détectable — dégradation gracieuse assumée (le gardien parle alors comme si la
	mine était encore infestée), aucune migration.
	"""
	# Une VICTOIRE remportée dans la salle est, littéralement, la menace éliminée. C'est la
	# trace la plus directe des trois, et la seule qui ne suppose aucune commission : elle
	# rend `acces_libere` / `acces_menace` utilisables par TOUT lieu gardé, pas seulement par
	# un donjon mandaté — sans quoi un gardien réciterait son refus générique à un joueur qui
	# vient d'abattre ce qu'il gardait.
	if victoire_acquise(character, lieu_id):
		return True
	q = commission_active_pour_lieu(character, lieu_id)
	if q and quetes.objectif_atteint(character, q):
		return True
	for t in (character or {}).get("quetes_terminees") or []:
		if t.get("source") == "commission" and t.get("lieu") == lieu_id:
			return True
	return False

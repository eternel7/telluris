# utils/escorte.py
# Quêtes d'ESCORTE : retrouver une ou plusieurs personnes, les faire voyager avec le groupe,
# et les amener VIVANTES à un lieu de dépose. C'est la première famille de quêtes dont la
# réussite ne dépend pas de ce que le joueur tue ou porte, mais de ce qu'il EMPÊCHE.
#
# La personne protégée se comporte en combat COMME UNE MONTURE : snapshot dans `joueurs`
# (donc placée, rendue, CIBLABLE), `jouable: False`, `deplacement: 0`, hors
# `ordre_initiative`. Toute la mécanique existe déjà — `utils/montures.py` et
# `create_combat_doc(montures=…)` en sont le patron exact, à ceci près qu'un protégé ne
# porte rien pour le groupe et ne s'achète pas.
#
# Un doc `protege:*` est un MIROIR du character (mêmes champs que consomment
# `compute_derived_stats`, `build_joueur_snapshot`, `_apply_world_turn_regen`), calqué sur
# `monture:*`. Ses stats sont celles de la BASE RACIALE seule (`rules:races`) : une civile
# n'est pas une aventurière, aucun point n'est dépensé. Appartenance = `statut: "escorte"`
# + `escorte_par` (aucun `user_id`, comme `aventurier:*`/`monture:*`), plus `quete` — l'id
# de la quête qui l'a fait naître.
#
# ⚠️ Un protégé n'est PAS un porteur : absent de `recrutement.porteurs_effectifs` et de
# `expedition.membres`. On ne lui transfère rien, il ne vend rien, il ne manie pas de hache.
# Son index vit dans `character["proteges"]`, SÉPARÉ de `groupe` et de `montures`.
#
# TROIS FORMES DE RENDEZ-VOUS, une seule résolution (`position_de_rencontre`) :
#   · `rencontre` absent      → chez le donneur : elle rejoint le groupe À L'ACCEPTATION ;
#   · `{lieu}` seul           → à l'ENTRÉE de ce lieu ;
#   · `{lieu, zones[]}`       → case tirée dans un placement de ces zones, zone 3×3 comme
#                               une chasse (`chasse.dans_zone_chasse`, à qui l'on passe le
#                               bloc `rencontre` tel quel — il porte déjà `position`).
#
# ⚠️ Chaîne d'import : `escorte` importe `chasse` + `quetes`, JAMAIS `combat`
# (c'est `combat` qui importera `escorte`). `chasse` fait déjà exactement ce détour, par
# import paresseux, pour `_walkable`.
#
# Logique pure (DB injectée : get_doc_fn / save_doc_fn / find_docs_fn), mute sans sauver —
# l'appelant persiste. Pattern de utils/transport.py et utils/montures.py. World-vars lues
# via le module (jamais from-import) : elles sont réglables à chaud depuis /admin.

import random
import unicodedata
import uuid

from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats
from utils.characters import sync_equipment_bonus, poids_bounds
from utils.consommables import caracts_avec_buffs
from utils import acces, chasse, marche, quetes


# Stats de repli quand la race du protégé est introuvable dans `rules:races` (contenu non
# importé, race mal orthographiée dans la spec). ⚠️ Un dict VIDE donnerait `pv_max = 0`,
# donc une civile morte à la seconde où elle apparaît : la quête échouerait au premier
# combat sans qu'aucun coup soit porté. Mieux vaut une passante quelconque qu'un cadavre.
STATS_DEFAUT = {"V": 4, "F": 20, "R": 20, "Ag": 20, "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20}

# Rang d'une escorte qu'AUCUNE barrière ne commande (miroir de `donjon.RANG_COMMISSION_DEFAUT`).
# Premier cran de l'échelle : comportement d'avant, aucune migration.
RANG_DEFAUT = "F"


# ---------------------------------------------------------------------------
# L'offre écrite portée par un PNJ (services.escorte.offre)
# ---------------------------------------------------------------------------

def offre_spec(pnj_doc: dict) -> dict | None:
	"""L'escorte ÉCRITE que ce PNJ confie, ou None. Miroir strict de
	`transport.offre_spec` — donc N'IMPORTE QUEL PNJ peut confier une escorte, il n'a pas
	à tenir boutique. `services.escorte.offre` = {id, destination, rencontre?{lieu, zones?},
	proteges:[{prenom, nom, race, sex, image?, inventaire?}], unique?, proba?, titre?,
	description?, recompenses?{xp, cuivre}}."""
	service = (((pnj_doc or {}).get("services") or {}).get("escorte") or {})
	spec = service.get("offre")
	if not spec or not spec.get("destination") or not spec.get("proteges"):
		return None
	return spec


def rang_requis(spec: dict) -> dict | None:
	"""Le filtre `rang_min` = `{cite, rang}` exigé par l'offre écrite, ou None (offre ouverte
	à tous). Même vocabulaire que la barrière de lieu (`acces.SOUS_FILTRES_CONNUS`) : un
	donneur peut ainsi réserver sa mission à qui s'est déjà fait un nom à la guilde."""
	filtre = (spec or {}).get("rang_min")
	return filtre if isinstance(filtre, dict) and filtre else None


def rang_suffisant(character: dict, spec: dict) -> bool:
	"""Le personnage a-t-il le rang de guilde exigé par cette offre ? Pas de `rang_min` ⇒
	True (comportement d'avant, aucune migration).

	⚠️ Comparateur PARTAGÉ avec les barrières de lieu (`acces.rang_min_satisfait`), donc
	FAIL-CLOSED : un `cite`/`rang` manquant ou hors échelle refuse. Un seuil illisible ne
	doit pas rendre l'offre PERMISSIVE — le symptôme (le donneur ne propose plus rien) est
	bruyant, là où une mission ouverte à tous par erreur passerait inaperçue."""
	filtre = rang_requis(spec)
	if not filtre:
		return True
	return acces.rang_min_satisfait(character, filtre)


def rang_de_offre(spec: dict, dest_doc: dict | None = None) -> str:
	"""Rang AFFICHÉ de la quête (badge de la fiche, archive) — **délégué à
	`acces.rang_de_quete`, la source unique partagée avec les commissions de donjon**
	(`donjon.rang_commission`). Aucune exception : même ordre, même maximum, même bornage.

	DEUX seuils lui sont soumis, parce que deux portes commandent une escorte :
	· le `rang_min` de la spec — ce que le donneur exige pour la confier ;
	· la barrière `acces.rang_min` du LIEU DE DÉPOSE — sans elle, une mission qu'on ne peut
	  pas rendre s'annoncerait plus facile qu'elle n'est.
	Le plus élevé des deux gagne, comme pour une commission."""
	return acces.rang_de_quete(
		(spec or {}).get("rang"),
		acces.rang_min_de(rang_requis(spec)),
		acces.rang_min_du_lieu(dest_doc),
		defaut=RANG_DEFAUT,
	)


def rang_insuffisant(character: dict, pnj_doc: dict) -> bool:
	"""Le donneur refuse-t-il de confier sa mission, faute de rang ? C'est le pendant
	PARLANT de `rang_suffisant` — miroir de `transport.mefiance` : sans lui le choix
	disparaîtrait purement et simplement, indiscernable d'un « rien à proposer aujourd'hui »,
	et le joueur n'aurait aucun moyen d'apprendre ce qu'on attend de lui.

	Vaut pour l'offre ÉCRITE comme pour le REGISTRE de la guilde (`recherche`), qui peut lui
	aussi réserver ses disparitions à un rang. ⚠️ Pas pour la progéniture d'un magasin : sa
	porte à lui est la CONFIANCE, et c'est `mefiance` qui la met en mots.

	Faux dès qu'il n'y a rien à refuser : pas d'offre, pas de seuil, escorte déjà en cours,
	ou mission déjà accomplie."""
	spec = offre_spec(pnj_doc) or recherche_spec(pnj_doc)
	if not spec or not rang_requis(spec):
		return False
	if escortes_actives(character) or deja_reussie(character, spec.get("id")):
		return False
	return not rang_suffisant(character, spec)


def deja_reussie(character: dict, quete_id: str) -> bool:
	"""Cette escorte a-t-elle déjà été MENÉE À BIEN ? (Un échec ne compte pas : le donneur
	repropose — on ne condamne pas un joueur pour une perte.) Gate des offres `unique`,
	d'où la nécessité d'un id STABLE sur la spec. Miroir de `transport.deja_reussie`."""
	if not quete_id:
		return False
	return any(
		t.get("id") == quete_id and not t.get("echec")
		for t in (character or {}).get("quetes_terminees", [])
	)


# ---------------------------------------------------------------------------
# Le rendez-vous
# ---------------------------------------------------------------------------

def position_de_rencontre(lieu_doc: dict, zones: list | None) -> dict | None:
	"""Case `{x,y}` où l'on retrouve la personne : centre d'un placement d'une des `zones`,
	BORNÉ à la grille à `chasse.MARGE_BORDS` cases des bords puis ramené sur une case
	PRATICABLE. `None` si le lieu n'a pas de grille, si aucune zone n'est demandée (forme
	« à l'entrée du lieu ») ou si aucune des zones n'est placée ici.

	⚠️ Les DEUX filtres de `chasse.position_de_chasse` sont indispensables et RÉUTILISÉS
	tels quels : une zone d'influence déborde légitimement du bord de carte (bbox négatives
	fréquentes, rien ne les valide), et une case dans la carte peut être un mur ou une
	falaise — le joueur ne pourrait alors jamais entrer dans le 3×3 du rendez-vous."""
	cibles = set(zones or ())
	if not cibles or not lieu_doc or not lieu_doc.get("dimensions"):
		return None
	placements = [
		p for p in (lieu_doc.get("zone_influences") or []) if p.get("zone") in cibles
	]
	if not placements:
		return None
	p = random.choice(placements)
	pos = chasse.borner_position(
		{"x": p.get("x", 0), "y": p.get("y", 0)}, lieu_doc.get("dimensions"))
	return chasse.case_praticable_proche(pos, lieu_doc)


def bloc_rencontre(spec: dict, get_doc_fn) -> dict | None:
	"""Le bloc `rencontre` figé de l'objectif — `{lieu, position?}` —, ou None quand la
	spec n'en porte pas (la personne rejoint le groupe à l'acceptation).

	⚠️ Résolu ICI, une fois pour toutes : la case est ensuite recopiée dans le snapshot de
	`quetes_actives` et n'est JAMAIS re-tirée en jeu, exactement comme le grade d'une
	chasse. Sans grille ou sans zone placée, on retombe sur la contrainte de lieu seule
	(`chasse.dans_zone_chasse` traite l'absence de `position` comme « n'importe où ici ») —
	dégradation gracieuse, jamais une quête qui disparaît."""
	rdv = (spec or {}).get("rencontre") or None
	if not rdv or not rdv.get("lieu"):
		return None
	bloc = {"lieu": rdv["lieu"]}
	pos = position_de_rencontre(get_doc_fn(rdv["lieu"]), rdv.get("zones"))
	if pos is not None:
		bloc["position"] = pos
	return bloc


# ---------------------------------------------------------------------------
# Génération de l'offre
# ---------------------------------------------------------------------------

def _nom_protege(spec_p: dict) -> str:
	return " ".join(x for x in (spec_p.get("prenom"), spec_p.get("nom")) if x).strip() or "l'inconnu"


def noms_proteges(proteges: list) -> str:
	"""« Aline », « Aline et Bertrand », « Aline, Bertrand et Cyprien » — pour les titres,
	descriptions et placeholders. Une liste vide rend une chaîne vide."""
	noms = [_nom_protege(p) for p in proteges or []]
	if not noms:
		return ""
	if len(noms) == 1:
		return noms[0]
	return ", ".join(noms[:-1]) + " et " + noms[-1]


def generer_escorte_authoree(spec: dict, giver_doc: dict, find_docs_fn, get_doc_fn) -> dict | None:
	"""Construit l'offre décrite par la spec du PNJ (non persistée, pas encore acceptée).
	Rien n'est tiré au sort sauf la CASE du rendez-vous. None si la spec ne nomme personne.

	Miroir de `transport.generer_transport_authore` : titre/description/récompenses absents
	sont dérivés, l'id vient de la spec (gate de `unique`).

	⚠️ Le getter est MÉMOÏSÉ pour toute la passe (`quetes._cached_getter`) : cette fonction
	est rappelée à CHAQUE rendu de nœud de dialogue (branche « aperçu » de `_contexte`), et
	elle lit maintenant le doc du lieu de dépose **deux fois** — une pour son rang, une dans
	`indice_destination`. Les docs `lieu:*` sont les plus gros du jeu ET sont EXCLUS du cache
	de requête (ils portent un état de partie) : sans ce mémo, contrôler le rang coûterait un
	aller-retour de plus par affichage."""
	proteges = [p for p in (spec or {}).get("proteges") or [] if isinstance(p, dict)]
	if not proteges:
		return None
	get_doc_fn = quetes._cached_getter(get_doc_fn)
	dest_id = spec.get("destination")
	indice = _indice(giver_doc, dest_id, find_docs_fn, get_doc_fn)
	rec = dict(spec.get("recompenses") or {})
	xp = int(rec.get("xp", character_stats.QUETE_TRANSPORT_XP))
	cuivre = int(rec.get("cuivre", max(0, round(xp * float(character_stats.QUETE_CUIVRE_PAR_XP)))))
	qui = noms_proteges(proteges)
	objectif = {"type": "escorte", "cible": dest_id, "quantite": 1}
	rdv = bloc_rencontre(spec, get_doc_fn)
	if rdv:
		objectif["rencontre"] = rdv
	recompenses = {"xp": xp, "cuivre": cuivre, "items": list(rec.get("items") or [])}
	# Lieux REMERCIÉS en plus du donneur (`quetes.recompenser_lieux`). Une escorte de
	# progéniture confiée par la guilde remercie AUSSI le magasin dont on ramène l'enfant ;
	# une escorte écrite peut faire de même en le déclarant. Champ absent ⇒ seul le donneur
	# encaisse, comportement d'avant.
	autres = [x for x in (rec.get("relation_lieux") or []) if x]
	if autres:
		recompenses["relation_lieux"] = autres
	return {
		"id": spec.get("id") or ("quete:escorte_" + uuid.uuid4().hex[:12]),
		"type_quete": "escorte",
		"titre": spec.get("titre") or f"Escorte : {qui}",
		# ⚠️ Les enseignes portent leur article (« L'Athanor ») : deux-points, jamais de
		# préposition — « à L'Athanor » serait fautif (règle commune au transport).
		"description": spec.get("description") or (
			f"Retrouvez {qui} et ramenez-la vivante. Destination : {indice['nom']}, "
			f"{_texte_indice(indice)}."
		),
		# Le lieu de DÉPOSE compte parmi les portes de la quête : s'il est gardé par un
		# `rang_min`, la mission vaut au moins ce rang — on ne peut pas la rendre sans.
		"rang": rang_de_offre(spec, get_doc_fn(dest_id) if dest_id else None),
		"giver": (giver_doc or {}).get("_id"),
		"objectif": objectif,
		# Les SPECS des personnes, pas encore incarnées — miroir de `cargaison`. Les docs
		# `protege:*` naissent à la rencontre, pas à l'offre.
		"proteges": [dict(p) for p in proteges],
		"recompenses": recompenses,
		"progress": 0,
	}


def _indice(giver_doc: dict, dest_id: str, find_docs_fn, get_doc_fn) -> dict:
	"""Indices d'orientation vers le lieu de dépose. Délégué à `transport.indice_destination`
	par import PARESSEUX : rien n'oblige ce module à dépendre de `transport` au chargement."""
	from utils import transport
	return transport.indice_destination(giver_doc, dest_id, find_docs_fn, get_doc_fn)


def _texte_indice(indice: dict) -> str:
	from utils import transport
	return transport.texte_indice(indice)


# ---------------------------------------------------------------------------
# PROGÉNITURE — la seule source d'escorte GÉNÉRÉE
# ---------------------------------------------------------------------------
# Un magasin dont l'entrée `pnj` du lieu déclare une `progeniture` peut demander qu'on
# retrouve son enfant ; le comptoir de la guilde, lui, recense ces disparitions pour toute
# la cité (`services.escorte.recherche`).
#
# ⚠️ RIEN N'EST DUPLIQUÉ DU MOTEUR : cette source SYNTHÉTISE une spec à la forme EXACTE de
# `services.escorte.offre`, puis passe par `generer_escorte_authoree`. Acceptation,
# incarnation, rendez-vous, combat, dépose, solde, dialogue et carte 🗺️ ne savent pas d'où
# vient l'offre, et n'ont pas à le savoir.
#
# ⚠️ L'information de nommage vit sur l'ENTRÉE du lieu, pas sur le doc PNJ : un
# `pnj:marchand_*` est GÉNÉRIQUE (deux boutiques d'un même métier partagent le même doc), et
# elles ne peuvent pas avoir le même enfant. Priorité entrée → doc, miroir exact de
# `pnj.nom_effectif` ; le repli sur le doc laisse un PNJ nommé et unique la porter lui-même.


def _slug(txt: str) -> str:
	"""Fragment d'identifiant stable : sans accent, sans ponctuation, en minuscules."""
	base = unicodedata.normalize("NFKD", str(txt or ""))
	base = "".join(c for c in base if not unicodedata.combining(c))
	brut = "".join(c if c.isalnum() else "_" for c in base.lower())
	return "_".join(x for x in brut.split("_") if x)


def _enfants_de(bloc: dict | None) -> list:
	return [e for e in (bloc or {}).get("enfants") or []
			if isinstance(e, dict) and str(e.get("prenom") or "").strip()]


def progeniture_de(entree: dict | None, pnj_doc: dict | None) -> dict | None:
	"""Le bloc `progeniture` qui vaut ICI — l'entrée du lieu prime, le doc PNJ sert de repli
	(miroir de `pnj.nom_effectif`). None si personne n'y est nommé : une famille sans enfant
	nommé n'ouvre aucune quête, et c'est ainsi qu'une boutique reste muette tant qu'on ne lui
	a rien écrit."""
	candidats = (
		(entree or {}),
		(((pnj_doc or {}).get("services") or {}).get("escorte") or {}),
	)
	for source in candidats:
		bloc = source.get("progeniture")
		if isinstance(bloc, dict) and _enfants_de(bloc):
			return bloc
	return None


def id_enfant(lieu_id: str, enfant: dict) -> str:
	"""Identifiant de la quête qui ramène CET enfant.

	⚠️ Bâti sur le lieu du MAGASIN et jamais sur le donneur : la même disparition, confiée
	par le père ou par le comptoir de la guilde, doit porter le MÊME id — sinon
	`deja_reussie` laisserait ramener deux fois le même enfant, une fois par canal."""
	return ("quete:escorte_progeniture_"
			+ _slug(str(lieu_id or "").split(":", 1)[-1]) + "_" + _slug(enfant.get("prenom")))


def enfants_a_retrouver(character: dict, lieu_id: str, bloc: dict | None) -> list:
	"""Les enfants de cette famille qui ne sont pas encore rentrés. Un ÉCHEC ne consomme rien
	(`deja_reussie` ignore les archives en échec) : le parent repropose. Liste vide ⇒ plus
	aucune offre pour cette maison, et le gain de réputation est donc borné par le nombre
	d'enfants ÉCRITS."""
	return [e for e in _enfants_de(bloc) if not deja_reussie(character, id_enfant(lieu_id, e))]


def progeniture_accomplie(character: dict, lieu_id: str, bloc: dict | None) -> bool:
	"""Au moins un enfant de cette maison a été ramené — de quoi laisser le parent remercier
	(flag `escorte_accomplie` côté magasin)."""
	return any(deja_reussie(character, id_enfant(lieu_id, e)) for e in _enfants_de(bloc))


def zones_dangereuses(lieu_doc: dict, get_doc_fn) -> list:
	"""Zones placées sur cette carte où un enfant peut se perdre : celles dont le doc `zone:*`
	porte `modificateurs.danger > 0` (forêts, rivière — le cœur de ville est à −3). C'est ce
	qui rend le rendez-vous DÉRIVÉ : aucune donnée à écrire par boutique, et une zone ajoutée
	à la carte devient un lieu de disparition sans une ligne de code.

	⚠️ Repli EN CASCADE, jamais de disparition silencieuse : aucune zone dangereuse ⇒ toutes
	les zones placées ; aucune zone du tout ⇒ liste vide, et l'appelant retombe sur la
	contrainte de lieu seule. Une carte muette est un défaut d'authoring, son prix ne doit pas
	être l'évaporation du contenu.

	⚠️ Les docs `zone:*` ne sont PAS dans le cache de requête : au plus une poignée de
	lectures, et seulement à la POSE de l'offre (une fois par entrée dans le lieu)."""
	placees = []
	for p in (lieu_doc or {}).get("zone_influences") or []:
		zid = p.get("zone")
		if zid and zid not in placees:
			placees.append(zid)
	dangereuses = []
	for zid in placees:
		doc = get_doc_fn(zid) or {}
		try:
			danger = float((doc.get("modificateurs") or {}).get("danger", 0) or 0)
		except (TypeError, ValueError):
			danger = 0.0
		if danger > 0:
			dangereuses.append(zid)
	return dangereuses or placees


def _rencontre_progeniture(bloc: dict, magasin_doc: dict, get_doc_fn) -> dict | None:
	"""Le bloc `rencontre` de la spec synthétisée : celui écrit dans la donnée s'il y est,
	sinon la CITÉ du magasin et ses zones dangereuses."""
	ecrit = bloc.get("rencontre")
	if isinstance(ecrit, dict) and ecrit.get("lieu"):
		return dict(ecrit)
	cite = (magasin_doc or {}).get("lieu_parent")
	if not cite:
		return None
	rdv = {"lieu": cite}
	zones = zones_dangereuses(get_doc_fn(cite), get_doc_fn)
	if zones:
		rdv["zones"] = zones
	return rdv


def spec_progeniture(character: dict, magasin_doc: dict, bloc: dict, get_doc_fn,
					 pnj_doc: dict | None = None, choix_fn=random.choice,
					 recompenses_defaut: dict | None = None) -> dict | None:
	"""Une spec à la forme EXACTE de `services.escorte.offre`, tirée de la progéniture d'un
	magasin. None quand tous les enfants sont rentrés.

	Le magasin est à la fois le lieu de DÉPOSE (on ramène l'enfant chez lui) et le lieu
	remercié (`recompenses.relation_lieux`) — quand c'est LUI qui confie la mission, donneur
	et remercié sont le même lieu, et c'est `quetes.recompenser_lieux` qui garantit alors un
	+1 et non un +2."""
	lieu_id = (magasin_doc or {}).get("_id")
	restants = enfants_a_retrouver(character, lieu_id, bloc)
	if not lieu_id or not restants:
		return None
	# Mémo partagé avec `generer_escorte_authoree` : sans lui le doc de la CITÉ (le plus gros
	# du jeu, ~28 Ko avec ses `cells`, et exclu du cache de requête) serait relu deux fois —
	# une pour ses zones, une pour la case du rendez-vous.
	get_doc_fn = quetes._cached_getter(get_doc_fn)
	enfant = choix_fn(restants)
	protege = dict(enfant)
	protege.setdefault("nom", str(bloc.get("nom") or "").strip())
	protege.setdefault("race", bloc.get("race") or (pnj_doc or {}).get("race") or "humain")
	qui = _nom_protege(protege)
	enseigne = (magasin_doc.get("label") or magasin_doc.get("nom") or "").strip()
	rec = dict(bloc.get("recompenses") or recompenses_defaut or {})
	xp = int(rec.get("xp", character_stats.ESCORTE_PROGENITURE_XP))
	rec["xp"] = xp
	rec["cuivre"] = int(rec.get("cuivre", max(0, round(xp * float(character_stats.QUETE_CUIVRE_PAR_XP)))))
	rec["relation_lieux"] = [lieu_id]
	spec = {
		"id": id_enfant(lieu_id, enfant),
		"destination": lieu_id,
		"proteges": [protege],
		# Un enfant ramené ne se reperd pas : l'unicité est PAR ENFANT, portée par l'id.
		"unique": True,
		"titre": bloc.get("titre") or f"Disparition : {qui}",
		# ⚠️ Formulation NEUTRE en genre : `sex` est facultatif dans la donnée, et « cet
		# enfant » accorde correctement quel que soit le sexe de l'enfant. Les enseignes
		# portent leur article : deux-points, jamais de préposition (règle du transport).
		"description": bloc.get("description") or (
			f"{qui} n'a pas reparu. Retrouvez la trace de cet enfant et ramenez-le sain et "
			f"sauf à : {enseigne}."
		),
		"recompenses": rec,
	}
	if bloc.get("rang_min"):
		spec["rang_min"] = bloc["rang_min"]
	rdv = _rencontre_progeniture(bloc, magasin_doc, get_doc_fn)
	if rdv:
		spec["rencontre"] = rdv
	return spec


def generer_escorte_progeniture(character: dict, magasin_doc: dict, bloc: dict, giver_doc: dict,
								find_docs_fn, get_doc_fn, pnj_doc: dict | None = None,
								choix_fn=random.choice,
								recompenses_defaut: dict | None = None) -> dict | None:
	"""Synthétise la spec puis la passe au générateur d'offre ÉCRITE, inchangé. `giver_doc`
	est le magasin (le parent se saisit lui-même) OU le comptoir de la guilde (le registre des
	disparitions) : c'est la seule différence entre les deux canaux."""
	spec = spec_progeniture(character, magasin_doc, bloc, get_doc_fn, pnj_doc, choix_fn,
							recompenses_defaut)
	if not spec:
		return None
	return generer_escorte_authoree(spec, giver_doc, find_docs_fn, get_doc_fn)


# ── La confiance du tenancier ────────────────────────────────────────────────────

def confiance_suffisante(character: dict, lieu_doc: dict, get_doc_fn,
						 now: int | None = None) -> bool:
	"""Le tenancier a-t-il assez confiance pour parler de sa famille ? Miroir de
	`transport.confiance_suffisante`, avec son propre seuil (on confie plus volontiers un
	colis qu'un enfant) : relation < ESCORTE_PROGENITURE_RELATION_MIN, ou marchandage bloqué
	— une brouille datée ferme la porte même à cote suffisante, et même garde-fou désactivé.

	⚠️ Comparateur `>=`, comme le transport : deux comparateurs divergents pour la même notion
	de confiance coûteraient bien plus cher que le point d'écart avec « > 60 »."""
	relation = marche.get_relation(character, lieu_doc, get_doc_fn)
	now = int(quetes.now_epoch() if now is None else now)
	if marche.marchandage_bloque(relation, now):
		return False
	seuil = int(character_stats.ESCORTE_PROGENITURE_RELATION_MIN)
	if seuil <= 0:
		return True
	return marche.relation_value(relation) >= seuil


def mefiance(character: dict, lieu_doc: dict, entree: dict | None, pnj_doc: dict | None,
			 get_doc_fn, now: int | None = None) -> bool:
	"""Le tenancier refuse-t-il de parler de sa progéniture, faute de confiance ? Pendant
	PARLANT de `confiance_suffisante`, miroir de `transport.mefiance` : sans lui le choix
	disparaîtrait sans un mot, indiscernable d'un tirage négatif, et le joueur n'apprendrait
	jamais ce qu'on attend de lui.

	MUET dès qu'il n'y a plus rien à refuser : pas de progéniture écrite, tous les enfants
	rentrés, offre déjà posée, ou escorte en cours."""
	bloc = progeniture_de(entree, pnj_doc)
	if not bloc or offre_spec(pnj_doc):
		return False
	if not enfants_a_retrouver(character, (lieu_doc or {}).get("_id"), bloc):
		return False
	if offre_courante(character, lieu_doc) or escortes_actives(character):
		return False
	return not confiance_suffisante(character, lieu_doc, get_doc_fn, now)


# ── Le registre de la guilde ─────────────────────────────────────────────────────

def recherche_spec(pnj_doc: dict | None) -> dict | None:
	"""Le bloc `services.escorte.recherche` : le comptoir recense les disparitions de la
	cité. Frère de `offre`, qui reste prioritaire — une mission ÉCRITE passe avant."""
	bloc = ((pnj_doc or {}).get("services") or {}).get("escorte") or {}
	rec = bloc.get("recherche")
	return rec if isinstance(rec, dict) else None


def familles_de_la_cite(character: dict, cite_id: str, find_docs_fn, get_doc_fn) -> list:
	"""Les `(lieu, entree, bloc)` des maisons de la cité qui attendent encore un enfant.

	⚠️ `find_docs` PROJETÉ (index `["type","lieu_parent"]` déjà posé) : sans projection on
	rapatrierait les `cells` de chaque carte. Les docs `pnj:*` lus au passage sont, eux, dans
	le cache de requête. Le doc `lieu` COMPLET n'est relu que pour la famille finalement
	tirée, par l'appelant."""
	if not cite_id or not find_docs_fn:
		return []
	selector = {"type": "lieu", "lieu_parent": cite_id}
	champs = ["_id", "label", "nom", "categorie", "sous_categorie", "lieu_parent", "pnj"]
	try:
		docs = find_docs_fn(selector, fields=champs)
	except TypeError:
		# Finder injecté sans projection (tests purs) : le comportement reste correct.
		docs = find_docs_fn(selector)
	sorties = []
	for d in docs or []:
		for entree in d.get("pnj") or []:
			pnj_id = entree.get("character")
			bloc = progeniture_de(entree, get_doc_fn(pnj_id) if pnj_id else None)
			if bloc and enfants_a_retrouver(character, d.get("_id"), bloc):
				sorties.append((d, entree, bloc))
				break
	return sorties


# ---------------------------------------------------------------------------
# Offre du lieu (champ transitoire, miroir de transport_offert)
# ---------------------------------------------------------------------------

def escortes_actives(character: dict) -> list:
	return [
		q for q in (character or {}).get("quetes_actives", [])
		if (q.get("objectif") or {}).get("type") == "escorte"
	]


def _offre_du_registre(character: dict, lieu_doc: dict, recherche: dict, find_docs_fn,
					   get_doc_fn, rand_fn, choix_fn) -> dict | None:
	"""Une disparition tirée du registre de la guilde : la cité est balayée, une maison qui
	attend encore un enfant est choisie, et l'offre est bâtie comme si le parent l'avait
	confiée — seul le `giver` change (le comptoir), et c'est lui qui encaissera le +1 en plus
	du magasin."""
	if not rang_suffisant(character, recherche):
		return None
	if rand_fn() >= float(recherche.get("proba", character_stats.ESCORTE_GUILDE_PROBA)):
		return None
	cite = recherche.get("cite") or (lieu_doc or {}).get("lieu_parent")
	familles = familles_de_la_cite(character, cite, find_docs_fn, get_doc_fn)
	if not familles:
		return None
	magasin, entree_m, bloc = choix_fn(familles)
	# Le doc COMPLET du magasin retenu : `familles_de_la_cite` ne rend qu'une projection, et
	# `generer_escorte_authoree` a besoin du lieu entier (indices d'orientation, barrière de
	# rang du lieu de dépose).
	magasin_complet = get_doc_fn(magasin.get("_id")) or magasin
	pnj_id = (entree_m or {}).get("character")
	return generer_escorte_progeniture(
		character, magasin_complet, bloc, lieu_doc, find_docs_fn, get_doc_fn,
		get_doc_fn(pnj_id) if pnj_id else None, choix_fn,
		recompenses_defaut=recherche.get("recompenses"))


def poser_escorte_offerte(character: dict, lieu_doc: dict, find_docs_fn, get_doc_fn,
						  rand_fn=random.random, pnj_doc: dict | None = None,
						  entree: dict | None = None, choix_fn=random.choice,
						  now: int | None = None) -> bool:
	"""Tire (une seule fois par entrée) l'escorte que ce lieu peut confier et la pose dans le
	champ transitoire `escorte_offerte` (mute sans save). Miroir de
	`transport.poser_transport_offert`, avec TROIS branches ordonnées au lieu de deux :

	1. **écrite** — `services.escorte.offre` : le scénario décide de tout, rien n'est tiré au
	   sort sauf la case du rendez-vous. Prioritaire : le contenu existant ne bouge pas ;
	2. **progéniture** — le tenancier se saisit lui-même du cas de son enfant. Exige la
	   CONFIANCE (`confiance_suffisante`) en plus du tirage ;
	3. **registre de guilde** — `services.escorte.recherche` : le comptoir recense les
	   disparitions de toute la cité.

	No-op si le tirage a déjà été fait pour ce lieu → un refresh ne re-tire pas, ressortir et
	rentrer re-tire. Aucune offre tant qu'une escorte est en cours (pas d'empilement).
	Renvoie True si le champ a changé (l'appelant décide de sauvegarder).

	⚠️ Les garde-fous (rang, confiance) sont contrôlés ICI, à la POSE, et pas seulement dans
	le dialogue : sans offre posée, `offre_courante` rend None et `_resoudre_escorte` refuse
	en 422. Une requête forgée sur le nœud d'acceptation ne contourne donc rien, là où un
	simple choix conditionné n'aurait masqué que le bouton."""
	lieu_id = (lieu_doc or {}).get("_id")
	spec = offre_spec(pnj_doc)
	bloc = progeniture_de(entree, pnj_doc)
	recherche = recherche_spec(pnj_doc)
	if not lieu_id or not (spec or bloc or recherche):
		# Lieu sans donneur : on nettoie l'offre restée sur l'ancien lieu.
		if (character.get("escorte_offerte") or {}).get("lieu"):
			character["escorte_offerte"] = None
			return True
		return False
	offert = character.get("escorte_offerte") or {}
	if offert.get("lieu") == lieu_id:
		return False
	quete = None
	if not escortes_actives(character):
		if spec:
			deja = bool(spec.get("unique")) and deja_reussie(character, spec.get("id"))
			if not deja and rang_suffisant(character, spec) and rand_fn() < float(spec.get("proba", 1.0)):
				quete = generer_escorte_authoree(spec, lieu_doc, find_docs_fn, get_doc_fn)
		elif bloc:
			proba = float(bloc.get("proba", character_stats.ESCORTE_PROGENITURE_PROBA))
			if (rang_suffisant(character, bloc)
					and confiance_suffisante(character, lieu_doc, get_doc_fn, now)
					and rand_fn() < proba):
				quete = generer_escorte_progeniture(character, lieu_doc, bloc, lieu_doc,
													find_docs_fn, get_doc_fn, pnj_doc, choix_fn)
		else:
			quete = _offre_du_registre(character, lieu_doc, recherche, find_docs_fn, get_doc_fn,
									   rand_fn, choix_fn)
	character["escorte_offerte"] = {"lieu": lieu_id, "quete": quete}
	return True


def offre_courante(character: dict, lieu_doc: dict) -> dict | None:
	"""L'offre tirée pour le lieu courant, ou None (tirage périmé / pas d'offre)."""
	offert = (character or {}).get("escorte_offerte") or {}
	lieu_id = (lieu_doc or {}).get("_id")
	if not lieu_id or offert.get("lieu") != lieu_id:
		return None
	return offert.get("quete") or None


def escorte_vers(character: dict, lieu_id: str) -> dict | None:
	"""L'escorte active qu'il faut DÉPOSER ici, quel qu'en soit le donneur — de quoi laisser
	le parent dire un mot d'un enfant que la GUILDE lui ramène. Sans elle il resterait muet
	pendant toute la mission menée en son nom, et `{protege}` serait vide dans sa bouche."""
	for q in escortes_actives(character):
		if (q.get("objectif") or {}).get("cible") == lieu_id:
			return q
	return None


def escorte_du_donneur(character: dict, lieu_id: str) -> dict | None:
	"""L'escorte active confiée par CE lieu, ou None — de quoi laisser le donneur relancer
	le joueur tant qu'il n'a pas ramené la personne."""
	for q in escortes_actives(character):
		if q.get("giver") == lieu_id:
			return q
	return None


# ---------------------------------------------------------------------------
# Acceptation
# ---------------------------------------------------------------------------

def accepter_escorte(character: dict, offre: dict, get_doc_fn,
					 now: int | None = None) -> tuple[dict, list]:
	"""Pose la quête dans `quetes_actives` et vide l'offre du lieu (mute sans save).

	Quand la spec ne porte AUCUN rendez-vous, la personne est là, chez le donneur : les docs
	`protege:*` sont créés et attachés SUR-LE-CHAMP et `rencontre_at` est posé. Renvoie
	`(snapshot, docs créés)` — les docs sont ANNEXES, à persister par l'appelant APRÈS son
	`save_doc(character)` autoritatif."""
	now = int(quetes.now_epoch() if now is None else now)
	snapshot = {
		"id": offre.get("id"),
		"titre": offre.get("titre", "—"),
		"description": offre.get("description", ""),
		"rang": offre.get("rang", "F"),
		"giver": offre.get("giver"),
		"objectif": dict(offre.get("objectif", {})),
		"recompenses": dict(offre.get("recompenses", {})),
		"proteges": [dict(p) for p in offre.get("proteges", [])],
		"progress": 0,
		"accepte_at": now,
	}
	character.setdefault("quetes_actives", []).append(snapshot)
	character["escorte_offerte"] = None
	docs = []
	if not (snapshot["objectif"].get("rencontre") or {}).get("lieu"):
		docs = incarner(character, snapshot, get_doc_fn, now)
	return snapshot, docs


# ---------------------------------------------------------------------------
# Les personnes protégées (docs `protege:*`)
# ---------------------------------------------------------------------------

def _derives_de(protege: dict):
	"""Stats dérivées (miroir de `montures._derives_de` : pas de vocation, niveau 0)."""
	equipment = sync_equipment_bonus(protege)
	stats = caracts_avec_buffs(protege)
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	return compute_derived_stats(base, niveau=0, equipment=equipment)


def vitaux_de(protege: dict) -> dict:
	"""État vital pour les payloads (miroir de `montures.vitaux_de`)."""
	derived = _derives_de(protege)
	return {
		"currentPV": protege.get("currentPV", derived.pv_max),
		"pv_max": derived.pv_max,
		"currentPM": protege.get("currentPM", derived.pm_max),
		"pm_max": derived.pm_max,
	}


def _stats_de_race(race_id: str, get_doc_fn) -> dict:
	"""Stats de BASE de la race, telles que `rules:races` les donne — aucun point dépensé :
	une civile n'est pas une aventurière (c'est là toute la différence avec
	`recrutement.generer_aventurier`, qui répartit un budget de création)."""
	races = (get_doc_fn("rules:races") or {}).get("value") or []
	race = next((r for r in races if r.get("id") == race_id), None)
	stats = dict((race or {}).get("stats") or {})
	return stats or dict(STATS_DEFAUT)


def creer_protege(spec_p: dict, character: dict, quete_id: str, get_doc_fn,
				  giver_id: str | None = None) -> dict:
	"""Doc `protege:*` neuf — MIROIR du character, calqué sur `montures.creer_monture`.

	Le doc porte le SOUS-ENSEMBLE des champs qui rend opérants `compute_derived_stats`,
	`build_joueur_snapshot` et `_apply_world_turn_regen`. `slots` reste vide (une civile
	n'équipe rien, mais le champ doit exister — `carried_weight` le somme) ; `inventaire`
	reçoit ce que la spec lui fait porter (les herbes d'Aline arrivent AVEC elle et ne sont
	pas transférables : un protégé n'est pas un porteur)."""
	caract = dict(spec_p.get("caracteristiques") or _stats_de_race(spec_p.get("race", ""), get_doc_fn))
	inventaire = []
	for ligne in spec_p.get("inventaire") or []:
		ref = dict(ligne) if isinstance(ligne, dict) else {"item": ligne}
		iid = ref.get("item")
		if not iid:
			continue
		if ref.get("poids") is None:
			doc = get_doc_fn(iid)
			if doc:
				ref["poids"] = poids_bounds(doc)[0]
			else:
				ref.pop("poids", None)
		inventaire.append(ref)
	protege = {
		"_id": f"protege:{uuid.uuid4().hex[:16]}",
		"type": "protege",
		"statut": "escorte",
		"escorte_par": character.get("_id"),
		"escorte_at": quetes.now_epoch(),
		"quete": quete_id,
		"giver": giver_id,
		"prenom": spec_p.get("prenom", ""),
		"nom": spec_p.get("nom", "") or spec_p.get("prenom", "") or "Protégé",
		"race": spec_p.get("race", ""),
		"sex": spec_p.get("sex", ""),
		"image": spec_p.get("image", ""),
		"description": spec_p.get("description", ""),
		"caracteristiques_current": caract,
		"currentPV": 0,   # posés au max dérivé ci-dessous
		"currentPM": 0,
		"inventaire": inventaire,
		"slots": {},
		"equipment_bonus": {},
		"competences_bonus": {},
		"effets_actifs": [],
		"combats_recompenses": [],   # requis par la finalisation de combat
		"jouable": False,            # ← lu par le combat : ni tour, ni déplacement
	}
	derived = _derives_de(protege)
	protege["currentPV"] = derived.pv_max
	protege["currentPM"] = derived.pm_max
	return protege


def nom_complet(protege: dict) -> str:
	return " ".join(
		x for x in ((protege or {}).get("prenom"), (protege or {}).get("nom")) if x
	).strip() or "l'inconnu"


def attacher(character: dict, protege: dict) -> None:
	"""Place la personne sous la protection du joueur. Mute les DEUX docs, sans sauvegarder —
	l'état vit sur le doc du protégé (`escorte_par`), la liste du character n'en est que
	l'index (miroir de `montures.acquerir`)."""
	protege["statut"] = "escorte"
	protege["escorte_par"] = character.get("_id")
	index = character.setdefault("proteges", [])
	if protege["_id"] not in index:
		index.append(protege["_id"])


def detacher(character: dict, protege: dict, statut: str = "libere") -> None:
	"""La personne quitte le groupe (arrivée à bon port, escorte abandonnée). Mute les deux
	docs, sans save. Miroir de `montures.relacher`, sans garde de cargaison : ce qu'elle
	porte lui appartient et repart avec elle."""
	protege["statut"] = statut
	protege.pop("escorte_par", None)
	character["proteges"] = [
		pid for pid in character.get("proteges", []) or [] if pid != protege.get("_id")
	]


def tuer(character: dict, protege: dict) -> None:
	"""Mort de la personne protégée : elle quitte le groupe définitivement. Mute les deux
	docs, sans save. ⚠️ Contrairement à une monture, elle n'a rien à rendre — son sac part
	avec elle : ce ne serait pas un butin, ce serait un dépouillement."""
	detacher(character, protege, statut="morte")
	protege["currentPV"] = 0


def proteges_effectifs(character: dict, get_doc_fn) -> list:
	"""Docs des personnes actuellement sous protection : ids de `character["proteges"]`
	résolus, filtrés sur statut `escorte` + escortés PAR CE personnage. Miroir exact de
	`montures.montures_effectives` — un doc `protege:*` n'ayant pas de `user_id`, c'est la
	SEULE preuve d'appartenance. Un id périmé est ignoré."""
	out = []
	for pid in (character or {}).get("proteges", []) or []:
		p = get_doc_fn(pid)
		if p and p.get("statut") == "escorte" and p.get("escorte_par") == character.get("_id"):
			out.append(p)
	return out


def proteges_de_quete(character: dict, quete_id: str, get_doc_fn) -> list:
	"""Les personnes vivantes rattachées à CETTE quête (une escorte peut en compter
	plusieurs, et rien n'interdit qu'une autre quête en ait attaché d'autres)."""
	return [p for p in proteges_effectifs(character, get_doc_fn) if p.get("quete") == quete_id]


def incarner(character: dict, q: dict, get_doc_fn, now: int | None = None) -> list:
	"""Fait naître et attache les docs `protege:*` de la quête, puis pose `rencontre_at`
	(miroir de `livree_at` du transport). Mute le character sans save ; renvoie les docs
	créés, ANNEXES, à persister par l'appelant.

	No-op — liste vide — si la rencontre a déjà eu lieu : c'est ce qui rend le chokepoint de
	déplacement idempotent, alors qu'il est appelé à CHAQUE pas dans le 3×3."""
	if q.get("rencontre_at"):
		return []
	docs = []
	qid = q.get("id") or q.get("_id")
	for spec_p in q.get("proteges") or []:
		doc = creer_protege(spec_p, character, qid, get_doc_fn, q.get("giver"))
		attacher(character, doc)
		docs.append(doc)
	q["rencontre_at"] = int(quetes.now_epoch() if now is None else now)
	return docs


# ---------------------------------------------------------------------------
# Archivage, réussite, échec
# ---------------------------------------------------------------------------

def archiver(character: dict, q: dict, echec: bool, now: int) -> None:
	"""Sort la quête des actives et l'archive dans `quetes_terminees` (mute sans save).
	Miroir de `transport.archiver` — c'est `echec` qui décide si `deja_reussie` la
	considérera comme accomplie (gate des offres `unique`)."""
	character["quetes_actives"] = [
		a for a in character.get("quetes_actives", []) if a.get("id") != q.get("id")
	]
	character.setdefault("quetes_terminees", []).append({
		"id": q.get("id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", "F"),
		"echec": bool(echec),
		"recompenses": {} if echec else dict(q.get("recompenses", {})),
		"termine_at": now,
	})


def liberer_proteges(character: dict, q: dict, get_doc_fn, statut: str = "libere") -> list:
	"""Détache toutes les personnes rattachées à cette quête (mute sans save) ; renvoie
	leurs docs, ANNEXES. Utilisé à l'arrivée (`arrivee`) comme à l'abandon (`libere`) : dans
	les deux cas elles cessent de suivre le groupe et de figurer dans les combats."""
	docs = proteges_de_quete(character, q.get("id") or q.get("_id"), get_doc_fn)
	for doc in docs:
		detacher(character, doc, statut=statut)
	return docs


def echouer(character: dict, q: dict, get_doc_fn, save_doc_fn, find_docs_fn=None,
			now: int | None = None) -> list:
	"""L'escorte est perdue (une personne est tombée, ou le joueur renonce) : la quête est
	archivée EN ÉCHEC, les survivants sont libérés, et le donneur — AVEC TOUTE SA MAISON —
	encaisse la sanction de renoncement (`quetes.sanctionner_renoncement`, chokepoint
	commun au transport et à l'abandon de quête).

	Le character est muté SANS save ; les docs `relation` sont ANNEXES et persistés ici (ils
	ne vivent pas dans le character). Renvoie les docs `protege:*` mutés, à persister."""
	now = int(quetes.now_epoch() if now is None else now)
	docs = liberer_proteges(character, q, get_doc_fn, statut="libere")
	archiver(character, q, echec=True, now=now)
	giver_doc = get_doc_fn(q.get("giver")) if q.get("giver") else None
	if giver_doc:
		quetes.sanctionner_renoncement(character, giver_doc, get_doc_fn, save_doc_fn, find_docs_fn)
	return docs


def _solder(character: dict, q: dict, get_doc_fn, save_doc_fn, now: int) -> dict:
	"""Solde l'escorte : récompenses (XP + prime + items), archivage, +1 relation avec le
	DONNEUR. Miroir de `transport._solder`.

	⚠️ `appliquer_recompenses` est appelée avec `compagnons=[]` : sur le chemin de
	déplacement, c'est `_apply_world_turn_groupe` — et lui seul — qui charge ET sauve les
	docs compagnons. Les faire recharger ici rendrait un SECOND dict du même document, donc
	deux `save_doc` sur le même `_rev` et une écriture perdue en silence. L'XP part avec
	`xp_partage`, comme celle de découverte."""
	recap = quetes.appliquer_recompenses(character, q, compagnons=[])
	archiver(character, q, echec=False, now=now)
	giver_id = q.get("giver")
	giver_doc = get_doc_fn(giver_id) if giver_id else None
	lieux = [giver_doc] if giver_doc else []
	# Lieux remerciés EN PLUS du donneur : une escorte de progéniture confiée par la guilde
	# fait aussi monter la réputation du magasin dont on ramène l'enfant. Le pré-filtre sur
	# `giver_id` n'économise qu'une lecture — c'est `recompenser_lieux` qui garantit qu'un
	# lieu à la fois donneur ET remercié n'encaisse qu'UN seul +1.
	for lid in (q.get("recompenses") or {}).get("relation_lieux") or []:
		if lid and lid != giver_id:
			doc = get_doc_fn(lid)
			if doc:
				lieux.append(doc)
	valeurs = quetes.recompenser_lieux(character, lieux, get_doc_fn, save_doc_fn)
	return {"xp": recap["xp"], "purse": recap["purse"],
			"relation": valeurs.get(giver_id), "relations": valeurs}


# ---------------------------------------------------------------------------
# CHOKEPOINT : le déplacement
# ---------------------------------------------------------------------------

def _rendez_vous_ici(q: dict, lieu_id: str, position: dict | None) -> bool:
	"""Le pas qui vient d'être fait amène-t-il le groupe sur la personne à retrouver ?
	`chasse.dans_zone_chasse` reçoit le bloc `rencontre` TEL QUEL (il porte déjà `position`)
	— zone 3×3 de Chebyshev, ou contrainte de lieu seule quand la case est absente."""
	rdv = (q.get("objectif") or {}).get("rencontre") or {}
	if not rdv.get("lieu") or rdv["lieu"] != lieu_id:
		return False
	return chasse.dans_zone_chasse(rdv, position)


def traiter_deplacement(character: dict, lieu_doc: dict, position: dict | None,
						get_doc_fn, save_doc_fn, find_docs_fn=None,
						now: int | None = None) -> dict:
	"""CHOKEPOINT unique appelé par le déplacement, dans les DEUX branches (miroir de
	`transport.traiter_expirations` : traitement paresseux à chaque point de passage,
	aucun tick de fond n'existe dans le jeu).

	(a) RENCONTRE — le lieu et la zone 3×3 correspondent : les docs `protege:*` naissent,
	    sont attachés, et `rencontre_at` est posé (idempotent, cf. `incarner`).
	(b) DÉPOSE — le lieu courant est `objectif.cible`, la rencontre a eu lieu et tout le
	    monde est debout : récompenses + archivage + +1 relation chez le donneur, et les
	    personnes quittent le groupe (statut `arrivee`).

	Le character est muté SANS save (l'appelant le sauvegarde) ; les docs `protege:*` et
	`relation` sont ANNEXES et persistés ICI. Renvoie `{"rencontres": [...], "depose": …}`
	— `rencontres` = les libellés à annoncer, `depose` = le récap de la quête soldée."""
	now = int(quetes.now_epoch() if now is None else now)
	lieu_id = (lieu_doc or {}).get("_id")
	rencontres: list = []
	depose = None
	if not lieu_id:
		return {"rencontres": rencontres, "depose": depose}

	for q in list(escortes_actives(character)):
		# (a) On les retrouve.
		if not q.get("rencontre_at") and _rendez_vous_ici(q, lieu_id, position):
			docs = incarner(character, q, get_doc_fn, now)
			for doc in docs:
				save_doc_fn(doc)
			if docs:
				rencontres.append({
					"quete": q.get("id"),
					"titre": q.get("titre", "—"),
					"noms": noms_proteges(q.get("proteges") or []),
				})
		# (b) On les dépose. ⚠️ Jamais dans le même passage que la rencontre si le
		# rendez-vous et la dépose sont au même lieu : `rencontre_at` vient d'être posé, mais
		# le test ci-dessous exige AUSSI d'être sur `objectif.cible` — deux lieux distincts
		# dans tous les contenus écrits, et un contenu qui les confondrait solderait
		# instantanément, ce qui reste cohérent (la personne est arrivée).
		if not q.get("rencontre_at"):
			continue
		if (q.get("objectif") or {}).get("cible") != lieu_id:
			continue
		vivants = proteges_de_quete(character, q.get("id") or q.get("_id"), get_doc_fn)
		if not vivants or any(int(p.get("currentPV", 0) or 0) <= 0 for p in vivants):
			continue
		noms = ", ".join(nom_complet(p) for p in vivants)
		for doc in liberer_proteges(character, q, get_doc_fn, statut="arrivee"):
			save_doc_fn(doc)
		recap = _solder(character, q, get_doc_fn, save_doc_fn, now)
		depose = {
			"quete": q.get("id"),
			"titre": q.get("titre", "—"),
			"noms": noms,
			"xp": recap["xp"].get("xp_gain", 0),
			"niveau_up": recap["xp"].get("niveau_up", False),
			"purse": recap["purse"],
			"relation": recap["relation"],
			"lieu": lieu_id,
		}
	return {"rencontres": rencontres, "depose": depose}

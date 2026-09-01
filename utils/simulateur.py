# utils/simulateur.py
# Simulateur de duel 1D (pur) — banc d'essai Monte Carlo de l'écran /admin/simulateur.
#
# Deux belligérants (espèce ± profil, ou character de la base) s'affrontent en duel sur
# une LIGNE : la géométrie du combat est réduite à une distance scalaire (pas de grille,
# pas d'obstacles, pas de ligne de vue), mais TOUTES les résolutions passent par les
# helpers de utils/combat — seuils de toucher, critiques/fumbles, dés de dégâts, budget
# d'actions, tick des effets à durée. Ne rien recopier de ces formules : une retouche du
# moteur doit se refléter ici sans une ligne.
#
# Ce que le modèle 1D assume (écarts au vrai moteur, tous volontaires) :
#   • distance de départ fixée par l'écran, chacun avance en ligne droite (min 1 case,
#     deux acteurs ne partagent pas une case) ; pas de kiting — un archer ne recule pas ;
#   • interdit ranged du moteur traduit en 1D : distance <= 1 = engagé au corps à corps,
#     donc pas de tir/jet ni de sort de portée > 1 ;
#   • politique d'action simple et documentée (soin sous SEUIL_SOIN_PV, buffs d'ouverture
#     au round 1, puis meilleure option offensive à l'espérance de dégâts par action) ;
#   • sorts lancés NUS (composants ignorés — pas de gestion d'inventaire de composants) ;
#   • les sorts/compétences offensifs SANS dégâts (pur debuff) sont hors politique : le
#     simulateur ne sait pas encore arbitrer « entraver d'abord » ; un sort de dégâts à
#     part durative applique en revanche bien son debuff sur la cible touchée ;
#   • pas de fuite, pas de ramassage — un duel jusqu'au bout.
#
# TERRAIN (`map_tags`) — le type de lieu du combat, pour tester un forestier en forêt :
#   • les passives conditionnées à furtivité (furtivite_sylvestre) posent l'état FURTIF à
#     l'entrée (competences.furtivite_passive, comme start_combat) — character seulement ;
#   • un adversaire furtif non détecté n'est ni approché ni attaqué : un jet de détection
#     par tour (combat._tenter_detection, distance comprise via des positions 1D posées
#     pour que _cheby mesure l'écart), réussite DÉFINITIVE ; en attendant, l'acteur
#     aveugle erre (il peut toujours se soigner/se buffer) ;
#   • la furtivité se rompt comme au moteur (combat._furtivite_apres_offensive) : corps à
#     corps = révélation, à distance = la cible seule tente un jet ;
#   • les sorts/compétences à `condition` (battle_map_tags) ne sont engagés que si le
#     terrain les remplit (condition_remplie) ;
#   • hors périmètre : les actives/sorts qui POSENT la furtivité en cours de combat
#     (l'arsenal ne retient pas un soutien à furtivité seule).
#
# Un CHARACTER est simulé à PLEINE FORME (currentPV/PM forcés aux max — un banc d'essai
# ne mesure pas l'état de jeu du moment) et n'engage que ce que sa barre d'action porte
# (slots_actions) plus ses armes équipées (attaque_profils du snapshot). Une ESPÈCE est
# re-tirée à CHAQUE passe (roll_monster_stats), fidèle au jeu.
#
# Les helpers `combat._xxx` réutilisés opèrent sur un acteur seul ou sur un pseudo-doc
# dont ils ne lisent que `tour` et `log` — les deux clés doivent TOUJOURS exister
# (_appliquer_fumble y accède sans setdefault), et `tour` avance à chaque round, sinon la
# règle « un effet posé ce tour est épargné du décrément » (pose_tour) dérive.

import copy
import math
import random
import re

from models import character_stats
from models.character_stats import BaseStats, compute_character_level
from utils import combat
from utils.characters import (SLOT_ZONE, item_ref_id, main_occupee_par_deux_mains,
							  recompute_equipment_bonus, restriction_satisfaite)
from utils.competences import (competence_utilisable_combat, condition_remplie,
							   furtivite_passive, normaliser_competence)
from utils.consommables import effet_instantane, est_consommable
from utils.consommables import effets_de as effets_de_consommable
from utils.slots_actions import slots_effectifs
from utils.sorts import normaliser_sort, part_durative, sort_utilisable_combat

# ── Politique de duel (réglages du simulateur, PAS des world-vars : un banc d'essai
# n'a pas à être réglable à chaud, il doit être lisible dans le code) ─────────────────
SEUIL_SOIN_PV = 0.4     # un acteur se soigne dès que currentPV < 40 % de son max
PLAFOND_ROUNDS = 100    # au-delà, la passe est déclarée NULLE (deux murs de PV)


# ── Espérance de dés ─────────────────────────────────────────────────────────────────

def moyenne_de_des(notation: str) -> float:
	"""Espérance de `combat.roll_dice` — MIROIR de ses deux regex (termes nDm puis
	entiers plats). Chaque terme nDm vaut n×(m+1)/2. Le clamp `max(1.0, …)` est une
	approximation du `max(1, total)` du moteur (l'espérance exacte de max(1, X) n'a
	pas d'intérêt pour un score) ; chaîne vide → 1.0."""
	notation = (notation or "").upper().replace(" ", "")
	total = 0.0
	for sign, n, sides in re.findall(r"([+-]?)(\d*)D(\d+)", notation):
		esperance = int(n or "1") * (int(sides) + 1) / 2.0
		total += -esperance if sign == "-" else esperance
	for mod in re.findall(r"[+-]?\d+", re.sub(r"[+-]?\d*D\d+", "", notation)):
		total += int(mod)
	return max(1.0, total)


# ── Construction des belligérants ────────────────────────────────────────────────────

def _normaliser_snapshot(snap: dict) -> dict:
	"""Comble les champs absents d'un snapshot (reconstruction à la lecture, jamais de
	migration) : un snapshot MONSTRE n'a ni cd/PM/toucher_magique/esquive ni
	`attaque_profils` — le duel les lit tous. Inoffensif sur un snapshot joueur."""
	snap.setdefault("cd", 0)
	snap.setdefault("currentPM", 0)
	snap.setdefault("pm_max", 0)
	snap.setdefault("toucher_magique", 0)
	snap.setdefault("esquive", 0)
	snap.setdefault("degats_cd", "")
	# `vivant` : le snapshot joueur ne le porte pas (sa vie = currentPV > 0) mais
	# _appliquer_effet_sur_cible le teste — le poser rend les deux camps symétriques.
	snap.setdefault("vivant", True)
	# Détection d'un adversaire furtif : _detection_threshold lit `vol`/`int` (présents
	# sur un snapshot monstre, absents d'un snapshot joueur → repli sur caracts_base) et
	# `detecte` porte « j'ai repéré MON adversaire » (un seul adversaire en duel).
	caracts = snap.get("caracts_base") or {}
	snap.setdefault("vol", int(caracts.get("Vol", 0) or 0))
	snap.setdefault("int", int(caracts.get("Int", 0) or 0))
	snap.setdefault("detecte", False)
	snap.setdefault("furtif", False)
	snap.setdefault("furtivite_bonus", 0)
	snap.setdefault("attaque_profils", [{
		"mode": "cac", "portee": max(1, int(snap.get("portee", 1) or 1)), "ranged": False,
		"toucher": "cc", "degats": "degats_cc", "label": "Attaque naturelle",
	}])
	return snap


def _snapshot_median(espece: dict, profil: dict | None) -> dict:
	"""Snapshot DÉTERMINISTE d'une espèce (pour les potentiels et le récap, qui ne
	doivent pas changer d'un run à l'autre) : le tirage du profil est remplacé par le
	MILIEU de son modificateur — même clamp que roll_monster_stats (randint(mid, mid)
	est déterministe), sans dupliquer la formule. Sans profil, build_monster_snapshot
	prend déjà le point médian de l'espèce."""
	profil_median = None
	if profil:
		mods = {}
		for caract, borne in (profil.get("attributs_modifier") or {}).items():
			milieu = (int(borne.get("min", 0)) + int(borne.get("max", 0))) // 2
			mods[caract] = {"min": milieu, "max": milieu}
		profil_median = {**profil, "attributs_modifier": mods}
	return _normaliser_snapshot(combat.build_monster_snapshot(espece, profil_median, 0))


# ── Stats FORCÉES (overlay JSON de l'écran) ──────────────────────────────────────────
# « Et si cet ours avait 300 PV ? » — le banc d'essai doit pouvoir écraser une dérivée
# pour un run, sans créer de doc de test en base. Les clés sont exactement celles que la
# fiche affiche (cf. `fiche_snapshot` moins `caracts`) : offrir une clé que le duel ne
# lit pas serait une promesse en l'air, d'où le test qui épingle les deux listes ensemble.
STATS_FORCABLES_NUM = ("pv_max", "pm_max", "cc", "cd", "initiative", "actions_max",
					   "deplacement", "pa", "pm_def", "toucher_magique", "esquive")
STATS_FORCABLES_TEXTE = ("degats_cc", "degats_cd")
STATS_FORCABLES = STATS_FORCABLES_NUM + STATS_FORCABLES_TEXTE

# Planchers repris de `_refresh_snapshot_stats` : un pv_max à 0 tuerait l'acteur au
# re-clamp sans lever `vivant` (cadavre debout, duel bloqué) et un acteur sans action
# ne jouerait jamais.
STATS_PLANCHER_1 = ("pv_max", "actions_max")


def normaliser_stats_forcees(brut) -> dict:
	"""Vue validée d'un bloc de stats forcées, ou `{}` si rien n'est demandé.

	⚠️ Whitelist FAIL-CLOSED : une clé inconnue lève `ValueError` au lieu d'être ignorée.
	Une faute de frappe (`pv` pour `pv_max`) doit se voir tout de suite — silencieusement
	écartée, elle produirait un run où l'on croit avoir forcé quelque chose."""
	if not brut:
		return {}
	if not isinstance(brut, dict):
		raise ValueError("Les stats forcées doivent être un objet JSON")
	out = {}
	for cle, valeur in brut.items():
		cle = str(cle)
		if cle not in STATS_FORCABLES:
			raise ValueError(f"Stat inconnue : {cle!r} (attendu : {', '.join(STATS_FORCABLES)})")
		if cle in STATS_FORCABLES_TEXTE:
			out[cle] = str(valeur or "").strip()
			continue
		try:
			nombre = int(valeur)
		except (TypeError, ValueError):
			raise ValueError(f"La stat {cle!r} attend un entier, reçu {valeur!r}")
		out[cle] = max(1 if cle in STATS_PLANCHER_1 else 0, nombre)
	return out


def _appliquer_stats_forcees(snap: dict, plein: bool = False) -> dict:
	"""Écrase les dérivées du snapshot par celles qu'on a forcées (`_sim_stats`).

	⚠️ Appelée à la construction ET après chaque recalcul du moteur : une valeur forcée
	doit être FIGÉE. `_refresh_snapshot_stats` recompose les dérivées depuis `caracts_base`
	dès qu'un effet est posé ou expire — sans cette ré-application, la valeur saisie
	disparaîtrait au premier buff, en plein duel et sans un mot. Contrepartie assumée :
	un buff de caractéristique ne fait plus bouger une stat forcée.

	⚠️ `plein=True` à la CONSTRUCTION seulement : les PV/PM courants sont remis au max
	(le banc d'essai part à pleine forme). En cours de duel ils sont simplement
	RE-CLAMPÉS — les remettre au max à chaque ré-application soignerait l'acteur à tous
	les tours, et le duel ne finirait jamais."""
	forcees = snap.get("_sim_stats") or {}
	if not forcees:
		return snap
	snap.update(forcees)
	for maximum, courant in (("pv_max", "currentPV"), ("pm_max", "currentPM")):
		if maximum in forcees:
			snap[courant] = (forcees[maximum] if plein
							 else min(int(snap.get(courant, 0) or 0), forcees[maximum]))
	return snap


# ── Équiper une espèce HUMANOÏDE (paperdoll de l'écran) ──────────────────────────────
# Un monstre n'a pas d'équipement en jeu ; le banc d'essai, lui, doit pouvoir répondre à
# « et si cet orc portait une cotte de mailles et une hache ? ». Rien n'est écrit en base
# et le moteur n'est pas touché : on habille le SNAPSHOT, avec les helpers existants.

# Les 12 emplacements du paperdoll (miroir de `_VALID_SLOTS`, routers/user.py).
SLOTS_EQUIPABLES = ("tete", "epaules", "torse", "mains", "jambes", "pieds",
					"cou", "anneau_1", "anneau_2", "ceinture",
					"main_droite", "main_gauche")
# Seul le tag qui ouvre le paperdoll — une espèce sans lui reste nue. ⚠️ SOURCE UNIQUE
# `character_stats.TAG_HUMANOIDE`, et non une seconde chaîne en dur : c'est exactement le
# même tag qui décide qu'une espèce frappe avec son ARME plutôt qu'avec ses crocs
# (cf. `combat.des_cc_espece`). Deux copies finiraient par diverger, et le banc d'essai
# habillerait une bête qui garderait son dé d'attaque naturelle.
TAG_EQUIPABLE = character_stats.TAG_HUMANOIDE


def espece_equipable(espece: dict) -> bool:
	"""Cette espèce peut-elle porter un équipement dans le simulateur ?"""
	return TAG_EQUIPABLE in ((espece or {}).get("tags") or [])


def normaliser_slots_equipes(brut, get_doc_fn, caracts: dict) -> dict:
	"""Vue validée d'un équipement `{slot: item_id}`, ou `{}` si rien n'est porté.

	⚠️ FAIL-CLOSED, comme `equip_item` en jeu : slot inconnu, item introuvable, item
	incompatible avec le slot, restriction de caractéristique non tenue ou arme à deux
	mains dont l'autre main est occupée ⇒ `ValueError` (→ 422). Une pièce silencieusement
	écartée donnerait un run qu'on croirait équipé.

	⚠️ `caracts` = celles du snapshot de RÉFÉRENCE (médian ou borné), jamais celles d'une
	passe : une espèce est re-tirée à chaque passe, donc une même pièce passerait ou non
	selon le tirage — l'équipement doit être décidé une fois pour toutes."""
	if not brut:
		return {}
	if not isinstance(brut, dict):
		raise ValueError("L'équipement doit être un objet JSON {slot: item_id}")
	slots = {}
	for slot, ref in brut.items():
		slot = str(slot)
		if not ref:
			continue
		if slot not in SLOTS_EQUIPABLES:
			raise ValueError(f"Emplacement inconnu : {slot!r}")
		item_id = str(ref)
		item = get_doc_fn(item_id)
		if not item or item.get("type") != "item":
			raise LookupError(f"Objet introuvable : {item_id}")
		if slot not in (item.get("slots") or []):
			raise ValueError(f"{item.get('nom', item_id)} ne se porte pas à « {slot} »")
		ok, manque = restriction_satisfaite(item.get("restriction"), caracts)
		if not ok:
			exige = ", ".join(f"{c} {v}" for c, v in manque.items())
			raise ValueError(f"{item.get('nom', item_id)} exige {exige}")
		slots[slot] = item_id
	# Deux mains : contrôlé APRÈS coup, l'ordre des clés d'un dict ne dit rien de
	# l'intention et une hache posée avant le bouclier doit refuser tout autant.
	for slot in ("main_droite", "main_gauche"):
		bloqueur = main_occupee_par_deux_mains(
			slots, lambda r: get_doc_fn(item_ref_id(r)), slot)
		if slots.get(slot) and bloqueur:
			raise ValueError(f"{bloqueur.get('nom', 'Une arme à deux mains')} occupe les deux mains")
	return slots


def _equiper_snapshot(snap: dict, slots: dict) -> dict:
	"""Habille un snapshot d'espèce : PA ventilés par zone, bonus d'arme, modes cac/jet/tir.

	Ne duplique AUCUNE formule — tout passe par les helpers du moteur :
	  • `recompute_equipment_bonus(slots)` prend un dict de slots, pas un character ;
	  • `_refresh_snapshot_stats` recompose les dérivées, y compris `cd`, `degats_cd`,
		`toucher_magique` et `pm_max` — absents d'un snapshot monstre, et indispensables
		dès qu'on équipe un arc ;
	  • `_weapon_attacks` ne lit que `character["slots"]` : un dict synthétique suffit.

	⚠️ `caracts_base` ET `equipment_bonus` sont posés sur le snapshot, tous les deux :
	c'est ce que relit `_refresh_snapshot_stats` à chaque pose ou expiration d'effet.
	Sans eux, l'équipement se volatiliserait au premier buff du duel — même piège que les
	stats forcées, résolu ici en donnant au monstre la forme d'un snapshot de joueur.

	⚠️ `attaque_profils` est posé APRÈS le refresh : le moteur le laisse volontairement
	figé (le recalculer relirait les docs d'items à chaque tour)."""
	if not slots:
		return snap
	equipment = recompute_equipment_bonus(slots)
	caracts = dict(snap.get("caracts_base") or {})
	for code, delta in (equipment.buffs or {}).items():
		if code in caracts:
			caracts[code] = max(0, int(caracts[code] or 0) + int(delta))
	snap["caracts_base"] = caracts
	snap["equipment_bonus"] = equipment.model_dump()
	snap["esquive_base"] = snap.get("esquive_base", 0) + equipment.esquive
	# Régén conférée par l'équipement d'essai (focus magique…) : `_tick_effets_combat` la
	# lit sur le snapshot. Sans ces deux lignes, essayer un objet à `regen_*` au banc ne
	# rendrait rien alors qu'il rend en jeu — un banc qui ment sur ce qu'il mesure.
	# ⚠️ Aucun double comptage possible : ce chemin ne sert qu'aux belligérants ESPÈCE,
	# qui n'ont ni équipement ni passive (un `character` passe par build_joueur_snapshot,
	# qui a déjà compté les siens).
	snap["regen_pv_base"] = equipment.regen_pv
	snap["regen_pm_base"] = equipment.regen_pm
	combat._refresh_snapshot_stats(snap)
	snap["currentPV"], snap["currentPM"] = snap["pv_max"], snap["pm_max"]

	base = BaseStats(v=caracts.get("V", 0), f=caracts.get("F", 0), r=caracts.get("R", 0),
					 ag=caracts.get("Ag", 0), vol=caracts.get("Vol", 0),
					 int_=caracts.get("Int", 0), cha=caracts.get("Cha", 0),
					 ch=caracts.get("Ch", 0))
	profils = combat._weapon_attacks({"slots": slots}, base)
	snap["attaque_profils"] = profils
	snap["portee"] = next((p["portee"] for p in profils if p["mode"] == "cac"), 1)
	snap["_sim_equipement"] = dict(slots)
	return snap


# Bornes d'une espèce offertes dans la liste des profils de l'écran, à côté du point
# médian : le PIRE et le MEILLEUR spécimen possible, sans profil.
BORNES = ("min", "max")


def _profil_borne(espece: dict, borne: str) -> dict:
	"""Profil SYNTHÉTIQUE qui force les stats d'une espèce à une borne de sa fourchette.

	Aucune formule dupliquée — tout repose sur celle de `combat.roll_monster_stats` :
	`max(bmin, min(bmax, bmin + delta))`, où `delta = randint(mod.min, mod.max)` si le
	modificateur existe, et 0 sinon. Donc :
	  • `min` → AUCUN modificateur ⇒ delta 0 ⇒ `bmin` ;
	  • `max` → un delta figé à `bmax − bmin` par caract ⇒ `bmin + d` ⇒ `bmax`
		(une donnée où `bmax < bmin` reste rattrapée par le clamp du moteur).
	Même ruse que `_snapshot_median`, qui replie les bornes d'un VRAI profil sur leur
	milieu : un modificateur à intervalle nul rend le tirage déterministe.

	⚠️ `build_monster_snapshot` lit `profil["_id"]` sans `.get` → l'`_id` est obligatoire.
	`niveau` 1 comme le cas médian : c'est lui que lisent `xp_reward` et `voc_niveau`."""
	mods = {}
	if borne == "max":
		for caract, bornes in (espece.get("base_attributes") or {}).items():
			bmin = int((bornes or {}).get("min", 0) or 0)
			bmax = int((bornes or {}).get("max", 0) or 0)
			mods[caract] = {"min": bmax - bmin, "max": bmax - bmin}
	return {"_id": f"profil:_borne_{borne}", "type": "profil",
			"nom": borne, "niveau": 1, "attributs_modifier": mods}


def _arsenal_de_barre(character: dict, get_doc_fn, map_tags=(), objets: bool = True) -> dict:
	"""Ce que le personnage ENGAGE dans le duel = sa barre d'action (slots_actions).
	Sorts/compétences offensifs (`cible: ennemi`), soutiens (`soi`/`allie` — en duel,
	l'allié c'est soi), consommables du sac (stock = nb d'exemplaires du TYPE). Les
	passives sont déjà dans le snapshot (competences_bonus, esquive) — jamais recomptées.
	Deux cases d'un même sort (avec/sans composants) = UNE option : les composants sont
	ignorés par le simulateur. Un sort/une compétence à `condition` (battle_map_tags)
	n'est retenu que si le TERRAIN la remplit (condition_remplie du moteur).

	`objets=False` prive les deux camps de leurs CONSOMMABLES (potions, élixirs) : on
	mesure alors ce que valent des belligérants sur leurs seules ressources propres —
	stats, armes, sorts et compétences. Sorts et compétences ne sont PAS des objets et
	restent en place ; l'équipement non plus (un duel aux poings ne se demande pas)."""
	sorts_off, comps_off, soutiens, consommables = [], [], [], []
	vus = set()
	for entree in slots_effectifs(character, get_doc_fn):
		if not entree:
			continue
		type_, ref = entree.get("type"), entree.get("ref")
		if (type_, ref) in vus:
			continue
		vus.add((type_, ref))
		if type_ == "sort":
			sort = normaliser_sort(get_doc_fn(ref))
			if not sort or not sort_utilisable_combat(sort) or not condition_remplie(sort, map_tags):
				continue
			eff = sort["effets"]
			if sort["cible"] == "ennemi":
				sorts_off.append(sort)
			elif eff.get("pv") or eff.get("pm") or part_durative(eff):
				soutiens.append({"kind": "sort", "id": sort["id"], "label": sort["nom"],
								 "icon": sort["icon"], "cout_pm": sort["cout_pm"],
								 "effets": eff, "compteur": "sorts", "source": sort})
		elif type_ == "competence":
			comp = normaliser_competence(get_doc_fn(ref))
			if not comp or not competence_utilisable_combat(comp) or not condition_remplie(comp, map_tags):
				continue
			eff = comp["effets"]
			if comp["cible"] == "ennemi":
				comps_off.append(comp)
			elif eff.get("pv") or eff.get("pm") or part_durative(eff):
				soutiens.append({"kind": "competence", "id": comp["id"], "label": comp["nom"],
								 "icon": comp["icon"], "cout_pm": comp["cout_pm"],
								 "effets": eff, "compteur": "competences", "source": comp})
		elif type_ == "consommable":
			if not objets:
				continue        # objets interdits pour ce duel
			doc = get_doc_fn(ref)
			if not doc or not est_consommable(doc) or not effet_instantane(doc):
				continue
			stock = sum(1 for r in character.get("inventaire") or [] if item_ref_id(r) == ref)
			entry = {"kind": "consommable", "id": ref, "label": doc.get("nom", ref),
					 "icon": doc.get("icon", "🧪"), "cout_pm": 0,
					 "effets": effets_de_consommable(doc), "stock": stock,
					 "compteur": "consommes", "source": doc}
			consommables.append(entry)
			soutiens.append(entry)
	return {"sorts": sorts_off, "competences": comps_off,
			"soutiens": soutiens, "consommables": consommables}


def construire_belligerant(spec: dict, get_doc_fn, map_tags=(), objets: bool = True) -> dict:
	"""`spec = {"type": "espece"|"character", "id", "profil"?}` → belligérant prêt à
	dueller : `fabrique()` rend un snapshot FRAIS à chaque passe (les snapshots sont
	MUTÉS par le duel — espèce re-tirée, character deepcopié), `snapshot_reference` un
	snapshot déterministe pour les potentiels et le récap.

	`map_tags` = le TERRAIN du duel (tags de battle_map) : il pose la furtivité d'entrée
	des passives conditionnées (comme start_combat) et filtre l'arsenal conditionné.
	`objets=False` retire les consommables de l'arsenal (cf. `_arsenal_de_barre`).

	Lève ValueError (spec malformée) ou LookupError (doc absent / mauvais type)."""
	spec = spec or {}
	type_ = str(spec.get("type") or "")
	doc_id = str(spec.get("id") or "")
	# Dérivées forcées pour ce run (overlay JSON de l'écran) — validées AVANT toute
	# lecture de doc : une clé fautive doit être signalée, pas noyée dans un 404.
	stats_forcees = normaliser_stats_forcees(spec.get("stats"))

	# Équipement d'une espèce humanoïde — validé plus bas (il faut les caracts de
	# référence), posé par `_fini`. Vide pour un character : il a déjà ses vrais slots.
	equipement: dict = {}

	def _fini(snap: dict) -> dict:
		"""Snapshot prêt : normalisé, ÉQUIPÉ, puis les stats forcées à pleine forme.

		⚠️ L'ordre compte : la normalisation pose un `attaque_profils` par défaut
		(« Attaque naturelle ») que l'équipement doit écraser, et une valeur saisie à la
		main doit primer sur tout le reste."""
		snap["_sim_stats"] = dict(stats_forcees)
		snap = _equiper_snapshot(_normaliser_snapshot(snap), equipement)
		return _appliquer_stats_forcees(snap, plein=True)

	if type_ == "espece":
		if not doc_id.startswith("espece:"):
			raise ValueError(f"Id d'espèce attendu (espece:…) : {doc_id!r}")
		espece = get_doc_fn(doc_id)
		if not espece or espece.get("type") != "espece":
			raise LookupError(f"Espèce introuvable : {doc_id}")
		profil = None
		profil_id = str(spec.get("profil") or "")
		# Borne de la fourchette de l'espèce (le pire / le meilleur spécimen), offerte
		# dans la liste des profils à côté du point médian. ⚠️ Whitelist FAIL-CLOSED :
		# une borne illisible ne doit pas retomber en silence sur le médian, on
		# simulerait autre chose que ce que l'écran annonce.
		borne = str(spec.get("borne") or "")
		if borne:
			if borne not in BORNES:
				raise ValueError(f"Borne inconnue : {borne!r} (min|max)")
			if profil_id:
				raise ValueError("Une borne d'espèce et un profil ne se combinent pas")
		if profil_id:
			if not profil_id.startswith("profil:"):
				raise ValueError(f"Id de profil attendu (profil:…) : {profil_id!r}")
			profil = get_doc_fn(profil_id)
			if not profil or profil.get("type") != "profil":
				raise LookupError(f"Profil introuvable : {profil_id}")
		elif borne:
			profil = _profil_borne(espece, borne)
		label = espece.get("nom", doc_id)
		if borne:
			label += f" ({'minimum' if borne == 'min' else 'maximum'})"
		elif profil:
			label += f" ({profil.get('nom', profil_id)})"

		# Équipement : validé contre les caracts de RÉFÉRENCE (le snapshot nu, médian ou
		# borné), donc une seule fois — pas contre le tirage d'une passe.
		if spec.get("slots"):
			if not espece_equipable(espece):
				raise ValueError(
					f"{espece.get('nom', doc_id)} n'est pas humanoïde : rien à équiper")
			nu = (_normaliser_snapshot(combat.build_monster_snapshot(espece, profil, 0))
				  if borne else _snapshot_median(espece, profil))
			equipement = normaliser_slots_equipes(
				spec.get("slots"), get_doc_fn, nu.get("caracts_base") or {})

		def fabrique():
			# Re-tirage PAR PASSE : fidèle au jeu, où chaque rencontre re-tire les stats.
			# Avec une borne, le profil synthétique rend ce tirage déterministe.
			return _fini(combat.build_monster_snapshot(espece, profil, 0))

		return {"type": "espece", "label": label, "fabrique": fabrique,
				"arsenal": {"sorts": [], "competences": [], "soutiens": [], "consommables": []},
				# Avec une borne, la référence est le snapshot BORNÉ lui-même : les
				# potentiels doivent décrire ce qui est simulé, pas le médian.
				# La référence porte les mêmes stats forcées : les potentiels doivent
				# décrire ce qui est simulé.
				"snapshot_reference": (fabrique() if borne
									   else _fini(_snapshot_median(espece, profil))),
				# Route servable de l'image — c'est le SERVEUR qui sait où elle vit
				# (mount /monsters), le client ne fait que la rendre.
				"image_route": f"/monsters/{espece['image']}" if espece.get("image") else ""}

	if type_ == "character":
		if not doc_id.startswith("character:"):
			raise ValueError(f"Id de personnage attendu (character:…) : {doc_id!r}")
		character = get_doc_fn(doc_id)
		if not character or character.get("type") != "character":
			raise LookupError(f"Personnage introuvable : {doc_id}")
		# ⚠️ build_joueur_snapshot lit la base via le get_doc GLOBAL (sync_equipment_bonus,
		# _weapon_attacks) : on ne l'appelle qu'UNE fois, puis deepcopy par passe.
		base = _normaliser_snapshot(combat.build_joueur_snapshot(character))
		base["currentPV"] = base["pv_max"]     # banc d'essai = pleine forme
		base["currentPM"] = base["pm_max"]
		base = _fini(base)                     # dérivées forcées par-dessus
		# Furtivité d'entrée : passives conditionnées évaluées contre le terrain — le
		# même chemin que start_combat (c'est LE cas du forestier en forêt).
		bonus_furtif = furtivite_passive(character, get_doc_fn, map_tags)
		if bonus_furtif > 0:
			base["furtif"] = True
			base["furtivite_bonus"] = bonus_furtif
		arsenal = _arsenal_de_barre(character, get_doc_fn, map_tags, objets)
		# Stock de consommables PAR PASSE : porté par le snapshot (deepcopié avec lui),
		# jamais par l'arsenal partagé — une passe ne doit pas vider les fioles de la
		# suivante.
		base["_sim_stocks"] = {c["id"]: c["stock"] for c in arsenal["consommables"]}
		label = " ".join(x for x in (character.get("prenom", ""), character.get("nom", "")) if x) or doc_id

		def fabrique():
			return copy.deepcopy(base)

		return {"type": "character", "label": label, "fabrique": fabrique,
				"arsenal": arsenal, "snapshot_reference": copy.deepcopy(base),
				"image_route": f"/characters/{character['image']}" if character.get("image") else "",
				# Niveaux affichés par l'écran — un character seulement (une espèce n'a ni
				# XP ni vocation ; il n'existe pas de « niveau de race » : la race est un nom,
				# le niveau global se dérive de l'XP totale).
				"niveaux": {
					"niveau": compute_character_level(int(character.get("xp_total", 0) or 0)),
					"race": str(character.get("race", "") or ""),
					"vocations": {str(k): int(v or 0) for k, v
								  in (character.get("vocations_niveaux") or {}).items()},
				}}

	raise ValueError(f"Type de belligérant inconnu : {type_!r} (espece|character)")


# ── Options offensives — vue statique partagée avec utils/potentiel ──────────────────

def options_offensives_statiques(snapshot: dict, arsenal: dict) -> list:
	"""Toutes les options offensives d'un belligérant, notation de dégâts résolue :
	armes du snapshot (attaque_profils) + sorts/compétences offensifs de l'arsenal.
	Consommée par potentiel_combat — la politique de duel refait le même parcours mais
	filtrée par la distance et les PM courants."""
	out = []
	for profil in snapshot.get("attaque_profils") or []:
		notation = snapshot.get(profil.get("degats", "degats_cc")) or snapshot.get("degats_cc") or ""
		if not notation:
			continue
		out.append({"kind": "arme", "label": profil.get("label", "Arme"),
					"jet": profil.get("toucher", "cc"), "portee": max(1, int(profil.get("portee", 1) or 1)),
					"ranged": bool(profil.get("ranged")), "notation": notation, "cout_pm": 0})
	for sort in arsenal.get("sorts") or []:
		notation = sort["effets"].get("degats") or ""
		if not notation:
			continue
		out.append({"kind": "sort", "label": sort["nom"], "jet": sort.get("jet", "magique"),
					"portee": max(1, sort["portee"]), "ranged": max(1, sort["portee"]) > 1,
					"notation": notation, "cout_pm": sort["cout_pm"]})
	for comp in arsenal.get("competences") or []:
		# jet "cc" → la frappe est portée AVEC l'arme (source unique _degats_competence).
		notation = combat._degats_competence(snapshot, comp, comp["effets"])
		if not notation:
			continue
		out.append({"kind": "competence", "label": comp["nom"], "jet": comp.get("jet", "cc"),
					"portee": comp["portee"], "ranged": comp["portee"] > 1,
					"notation": notation, "cout_pm": comp["cout_pm"]})
	return out


# ── Politique de duel ────────────────────────────────────────────────────────────────

def _vivant(actor: dict) -> bool:
	return int(actor.get("currentPV", 0) or 0) > 0


def _log(pseudo: dict, actor: dict, kind: str, texte: str) -> None:
	pseudo["log"].append({"tour": pseudo["tour"], "acteur": actor.get("nom", "?"),
						  "kind": kind, "texte": texte})


def _seuil_de(actor: dict, cible: dict, option: dict) -> int:
	"""Seuil de toucher de CETTE option contre CETTE cible — les trois helpers du moteur."""
	if option["jet"] == "magique":
		return combat._magic_hit_threshold(actor.get("toucher_magique", 0), cible.get("pm_def", 0))
	skill = actor.get("cd", 0) if option["jet"] == "cd" else actor.get("cc", 0)
	return combat._hit_threshold(skill, combat._defense_physique(cible))


def _options_jouables(actor: dict, arsenal: dict, distance: int):
	"""Options offensives jouables ICI et MAINTENANT : à portée, hors interdit ranged
	(distance <= 1 = engagé), sort/compétence finançable en PM."""
	for profil in actor.get("attaque_profils") or []:
		portee = max(1, int(profil.get("portee", 1) or 1))
		if distance > portee or (profil.get("ranged") and distance <= 1):
			continue
		notation = actor.get(profil.get("degats", "degats_cc")) or actor.get("degats_cc") or ""
		if not notation:
			continue
		yield {"kind": "arme", "label": profil.get("label", "Arme"),
			   "jet": profil.get("toucher", "cc"), "notation": notation, "cout_pm": 0,
			   "ranged": bool(profil.get("ranged")),
			   "effets": profil.get("effets"), "effets_cible": profil.get("effets_cible", "ennemi"),
			   "source": {"id": profil.get("effets_source_id") or profil.get("item_id", ""),
						  "nom": profil.get("label", "Arme"), "icon": "⚔"},
			   "compteur": "attaques"}
	for sort in arsenal.get("sorts") or []:
		portee = max(1, sort["portee"])
		if distance > portee or (portee > 1 and distance <= 1):
			continue
		if sort["cout_pm"] > actor.get("currentPM", 0):
			continue
		notation = sort["effets"].get("degats") or ""
		if not notation:
			continue   # pur debuff : hors politique (cf. en-tête de module)
		yield {"kind": "sort", "label": sort["nom"], "jet": sort.get("jet", "magique"),
			   "notation": notation, "cout_pm": sort["cout_pm"], "effets": sort["effets"],
			   "ranged": portee > 1,
			   "effets_cible": "ennemi", "source": sort, "compteur": "sorts"}
	for comp in arsenal.get("competences") or []:
		portee = comp["portee"]
		if distance > portee or (portee > 1 and distance <= 1):
			continue
		if comp["cout_pm"] > actor.get("currentPM", 0):
			continue
		notation = combat._degats_competence(actor, comp, comp["effets"])
		if not notation:
			continue
		yield {"kind": "competence", "label": comp["nom"], "jet": comp.get("jet", "cc"),
			   "notation": notation, "cout_pm": comp["cout_pm"], "effets": comp["effets"],
			   "ranged": portee > 1,
			   "effets_cible": "ennemi", "source": comp, "compteur": "competences"}


def _meilleure_offensive(actor: dict, cible: dict, arsenal: dict, distance: int) -> dict | None:
	"""Meilleure espérance de dégâts par action contre CETTE cible. Crit/fumble hors
	du SCORE (ils jouent dans l'exécution) — le score départage, il ne prédit pas."""
	meilleure, meilleur_score = None, -1.0
	for option in _options_jouables(actor, arsenal, distance):
		p = _seuil_de(actor, cible, option) / 100.0
		# Même formule que le coup réel, l'espérance des dés remplaçant le tirage : le
		# score classe les options selon ce qu'elles feront VRAIMENT.
		score = p * combat.calculer_degats(actor, cible, option["notation"],
										   1, option["jet"], des_fn=moyenne_de_des)
		if score > meilleur_score:
			meilleure, meilleur_score = option, score
	return meilleure


def _refiger(*acteurs) -> None:
	"""Repose les stats forcées après un recalcul du moteur (`_refresh_snapshot_stats`,
	déclenché par la pose ou l'expiration d'un effet). Sans appel ici, une valeur saisie
	dans l'overlay disparaîtrait au premier buff du duel."""
	for acteur in acteurs:
		if acteur and acteur.get("_sim_stats"):
			_appliquer_stats_forcees(acteur)


def _poser_positions(actor: dict, adversaire: dict, distance: int) -> None:
	"""Positions 1D posées sur les snapshots pour que les helpers de furtivité du moteur
	(_detection_threshold via _cheby) mesurent la vraie distance du duel."""
	actor["pos"] = {"x": 0, "y": 0}
	adversaire["pos"] = {"x": max(0, int(distance)), "y": 0}


def _executer_attaque(actor: dict, cible: dict, option: dict, etat: dict) -> None:
	"""Un coup, résolu comme au moteur : PM débités AVANT le jet (un sort raté coûte),
	critique ×2 sur les dés avant la soustraction des PA, magie sans PA, fumble = une
	action de plus perdue, part durative posée sur la cible touchée vivante. Un
	attaquant FURTIF en sort comme au moteur : corps à corps = révélation, à distance =
	la cible seule tente un jet (_furtivite_apres_offensive)."""
	pseudo = etat["pseudo"]
	if option["cout_pm"]:
		actor["currentPM"] = max(0, int(actor.get("currentPM", 0)) - option["cout_pm"])
	seuil = _seuil_de(actor, cible, option)
	jet = combat._resoudre_jet(actor, cible, seuil)
	actor[option["compteur"]] = actor.get(option["compteur"], 0) + 1
	combat._refresh_actions(actor)
	if jet["touche"]:
		# Formule PARTAGÉE avec le moteur (combat.calculer_degats) : un duel simulé et un
		# coup joué en jeu doivent blesser exactement pareil — localisation comprise.
		zone = combat.tirer_localisation()
		ou = f" {combat.ZONE_LIBELLE[zone]}" if zone in combat.ZONE_LIBELLE else ""
		dmg = combat.calculer_degats(actor, cible, option["notation"],
									 jet["mult_degats"], option["jet"], zone=zone)
		cible["currentPV"] = max(0, int(cible.get("currentPV", 0)) - dmg)
		cible["vivant"] = cible["currentPV"] > 0
		suffixe = " — CRITIQUE ×2" if jet["critique"] else ""
		_log(pseudo, actor, "crit" if jet["critique"] else "hit",
			 f"{actor.get('nom', '?')} touche {cible.get('nom', '?')}{ou} avec "
			 f"{option['label']} : {dmg} dégâts{suffixe} "
			 f"({cible['currentPV']}/{cible.get('pv_max', '?')} PV).")
		effets = option.get("effets")
		if effets and part_durative(effets):
			if option.get("effets_cible") == "soi":
				combat._empiler_effet_combat(actor, option["source"], effets, pseudo["tour"])
			else:
				combat._appliquer_effet_sur_cible(pseudo, cible, option["source"], effets, pseudo["tour"])
			# Poser un effet a recalculé les dérivées du porteur : refiger.
			_refiger(actor, cible)
	else:
		_log(pseudo, actor, "miss",
			 f"{actor.get('nom', '?')} manque {cible.get('nom', '?')} ({option['label']}, "
			 f"jet {jet['roll']} > seuil {seuil}).")
	if jet["fumble"]:
		combat._appliquer_fumble(pseudo, actor)
	# Rupture de furtivité — APRÈS la résolution (vivant à jour), touché ou raté,
	# exactement comme les trois sites joueur du moteur.
	if actor.get("furtif"):
		_poser_positions(actor, cible, etat["distance"])
		combat._furtivite_apres_offensive(pseudo, actor, cible, bool(option.get("ranged")))


def _utiliser_soutien(actor: dict, soutien: dict, pseudo: dict) -> bool:
	"""Joue un soutien sur SOI (1 action) : paie (PM ou stock), applique la part
	instantanée clampée aux max, empile la part durative. False si infinançable."""
	if soutien["kind"] == "consommable":
		stocks = actor.setdefault("_sim_stocks", {})
		if stocks.get(soutien["id"], 0) <= 0:
			return False
		stocks[soutien["id"]] -= 1
	else:
		if soutien["cout_pm"] > actor.get("currentPM", 0):
			return False
		actor["currentPM"] = int(actor.get("currentPM", 0)) - soutien["cout_pm"]
	eff = soutien["effets"]
	gains = []
	if eff.get("pv"):
		avant = int(actor.get("currentPV", 0))
		actor["currentPV"] = min(int(actor.get("pv_max", avant)), avant + eff["pv"])
		if actor["currentPV"] != avant:
			gains.append(f"+{actor['currentPV'] - avant} PV")
	if eff.get("pm"):
		avant = int(actor.get("currentPM", 0))
		actor["currentPM"] = min(int(actor.get("pm_max", avant)), avant + eff["pm"])
		if actor["currentPM"] != avant:
			gains.append(f"+{actor['currentPM'] - avant} PM")
	if part_durative(eff):
		combat._empiler_effet_combat(actor, soutien["source"], eff, pseudo["tour"])
		_refiger(actor)
	actor[soutien["compteur"]] = actor.get(soutien["compteur"], 0) + 1
	combat._refresh_actions(actor)
	detail = f" ({', '.join(gains)})" if gains else ""
	_log(pseudo, actor, "sys",
		 f"{actor.get('nom', '?')} utilise {soutien['icon']} {soutien['label']}{detail}.")
	return True


def _tenter_soin(actor: dict, arsenal: dict, pseudo: dict) -> bool:
	if actor.get("currentPV", 0) >= SEUIL_SOIN_PV * max(1, actor.get("pv_max", 1)):
		return False
	for soutien in arsenal.get("soutiens") or []:
		if soutien["effets"].get("pv", 0) <= 0:
			continue
		if _utiliser_soutien(actor, soutien, pseudo):
			return True
	return False


def _tenter_buff_ouverture(actor: dict, arsenal: dict, pseudo: dict) -> bool:
	"""Round 1 : chaque soutien duratif SANS soin est lancé une fois (un joueur se buffe
	avant l'engagement). Mémo `_sim_buffs_lances` porté par le snapshot (deepcopy-safe)."""
	lances = actor.setdefault("_sim_buffs_lances", [])
	for soutien in arsenal.get("soutiens") or []:
		if soutien["effets"].get("pv", 0) > 0 or not part_durative(soutien["effets"]):
			continue
		if soutien["id"] in lances:
			continue
		if _utiliser_soutien(actor, soutien, pseudo):
			lances.append(soutien["id"])
			return True
	return False


def _portee_visee(actor: dict, arsenal: dict) -> int:
	"""Distance à laquelle l'acteur veut se tenir : la plus grande portée parmi ses
	options offensives finançables (l'approche s'arrête là — pas de kiting)."""
	portees = [max(1, int(p.get("portee", 1) or 1)) for p in actor.get("attaque_profils") or []]
	for sort in arsenal.get("sorts") or []:
		if sort["cout_pm"] <= actor.get("currentPM", 0) and sort["effets"].get("degats"):
			portees.append(max(1, sort["portee"]))
	for comp in arsenal.get("competences") or []:
		if comp["cout_pm"] <= actor.get("currentPM", 0) and comp["effets"].get("degats"):
			portees.append(comp["portee"])
	return max(portees) if portees else 1


def _avancer_d_une_case(actor: dict, arsenal: dict, etat: dict) -> bool:
	"""Un pas vers l'adversaire — même contrat que la boucle d'approche du moteur
	(_run_monster_turn) : on avance tant que le budget d'actions le permet (le coût AP
	est celui de _move_ap_used_for, recalculé par _refresh_actions), sans jamais
	descendre sous 1 case (deux acteurs ne partagent pas une case)."""
	if etat["distance"] <= _portee_visee(actor, arsenal):
		return False
	if actor.get("cells_moved", 0) >= max(1, actor.get("deplacement", 1)):
		return False
	actor["cells_moved"] = actor.get("cells_moved", 0) + 1
	etat["distance"] = max(1, etat["distance"] - 1)
	combat._refresh_actions(actor)
	return True


def _jouer_tour(actor: dict, adversaire: dict, arsenal: dict, etat: dict, round_no: int) -> None:
	pseudo = etat["pseudo"]
	# Tick des effets (régén, décrément, expiration → _refresh_snapshot_stats) + budget.
	combat._reset_turn_budget(actor, pseudo)
	_refiger(actor)   # une expiration vient peut-être de recomposer les dérivées
	# Adversaire furtif non repéré : UN jet de détection par tour, comme au début d'un
	# tour de monstre (_run_monster_turn) — réussite définitive.
	if adversaire.get("furtif") and not actor.get("detecte"):
		_poser_positions(actor, adversaire, etat["distance"])
		combat._tenter_detection(
			pseudo, actor, adversaire,
			echec_texte=f"{actor.get('nom', '?')} scrute les alentours sans repérer son adversaire !")
	distance_avant = etat["distance"]
	while _vivant(actor) and _vivant(adversaire) and actor.get("actions_restantes", 0) > 0:
		if _tenter_soin(actor, arsenal, pseudo):
			continue
		if round_no == 1 and _tenter_buff_ouverture(actor, arsenal, pseudo):
			continue
		# Aveugle face à un furtif : ni approche ni attaque — l'acteur erre, comme un
		# monstre qui n'a pas repéré le joueur. Les soins/buffs sur soi restent permis.
		if adversaire.get("furtif") and not actor.get("detecte"):
			_log(pseudo, actor, "sys", f"{actor.get('nom', '?')} erre sans trouver sa cible.")
			break
		option = _meilleure_offensive(actor, adversaire, arsenal, etat["distance"])
		if option is not None:
			_executer_attaque(actor, adversaire, option, etat)
			continue
		if not _avancer_d_une_case(actor, arsenal, etat):
			break   # rien à faire : hors de portée et plus de jambes — tour fini
	if etat["distance"] != distance_avant:
		_log(pseudo, actor, "sys",
			 f"{actor.get('nom', '?')} avance de {distance_avant - etat['distance']} case(s) "
			 f"(distance {etat['distance']}).")


# ── Duel & Monte Carlo ───────────────────────────────────────────────────────────────

def _derouler_duel(bel_a: dict, bel_b: dict, distance: int, journal: list | None,
				   plafond_rounds: int = PLAFOND_ROUNDS) -> dict:
	"""UNE passe : → {"vainqueur": "a"|"b"|None, "rounds", "pv_restants" (du vainqueur)}.
	Ordre du round = initiative décroissante, recalculée à chaque round (un buff peut
	inverser l'ordre) ; tri stable, égalité → A joue d'abord (comme le sorted du moteur,
	joueurs avant monstres). Un acteur tué en cours de round ne joue pas son tour."""
	snap_a, snap_b = bel_a["fabrique"](), bel_b["fabrique"]()
	snap_a["nom"] = f"[A] {snap_a.get('nom', bel_a['label'])}"
	snap_b["nom"] = f"[B] {snap_b.get('nom', bel_b['label'])}"
	pseudo = {"tour": 0, "log": journal if journal is not None else []}
	etat = {"distance": max(1, int(distance)), "pseudo": pseudo}
	camps = [(snap_a, snap_b, bel_a["arsenal"]), (snap_b, snap_a, bel_b["arsenal"])]

	for round_no in range(1, max(1, int(plafond_rounds)) + 1):
		pseudo["tour"] = round_no
		for actor, adversaire, arsenal in sorted(camps, key=lambda c: -int(c[0].get("initiative", 0) or 0)):
			if not (_vivant(actor) and _vivant(adversaire)):
				break
			_jouer_tour(actor, adversaire, arsenal, etat, round_no)
		if not (_vivant(snap_a) and _vivant(snap_b)):
			vainqueur = "a" if _vivant(snap_a) else ("b" if _vivant(snap_b) else None)
			gagnant = {"a": snap_a, "b": snap_b}.get(vainqueur)
			if gagnant is not None:
				_log(pseudo, gagnant, "sys",
					 f"{gagnant['nom']} l'emporte au round {round_no} "
					 f"({gagnant.get('currentPV', 0)}/{gagnant.get('pv_max', '?')} PV restants).")
			return {"vainqueur": vainqueur, "rounds": round_no,
					"pv_restants": int(gagnant.get("currentPV", 0)) if gagnant else 0}
	return {"vainqueur": None, "rounds": int(plafond_rounds), "pv_restants": 0}


def fiche_snapshot(snap: dict) -> dict:
	"""Le PROFIL d'un belligérant tel que l'écran l'affiche : caracts + dérivées du
	snapshot de référence (déterministe — médian pour une espèce, pleine forme pour un
	character). Une vue, pas un recalcul : tout vient du snapshot."""
	return {
		"caracts": dict(snap.get("caracts_base") or {}),
		"pv_max": int(snap.get("pv_max", 0) or 0),
		"pm_max": int(snap.get("pm_max", 0) or 0),
		"cc": int(snap.get("cc", 0) or 0),
		"cd": int(snap.get("cd", 0) or 0),
		"initiative": int(snap.get("initiative", 0) or 0),
		"actions_max": int(snap.get("actions_max", 1) or 1),
		"deplacement": int(snap.get("deplacement", 1) or 1),
		"pa": int(snap.get("pa", 0) or 0),
		# Localisation des touches : le total ne dit plus ce qu'un coup rencontre —
		# l'écran affiche donc la ventilation, et la part globale DÉRIVÉE (jamais
		# stockée à côté du total, cf. combat.pa_de_zone).
		"pa_zones": dict(snap.get("pa_zones") or {}),
		"pa_global": int(snap.get("pa", 0) or 0)
					 - sum(int(v or 0) for v in (snap.get("pa_zones") or {}).values()),
		"pm_def": int(snap.get("pm_def", 0) or 0),
		"toucher_magique": int(snap.get("toucher_magique", 0) or 0),
		"esquive": int(snap.get("esquive", 0) or 0),
		"degats_cc": snap.get("degats_cc", "") or "",
		"degats_cd": snap.get("degats_cd", "") or "",
	}


def equipement_du_snapshot(snap: dict) -> dict:
	"""Ce que porte un belligérant : `{slot: item_id}` — vide pour un character (il a
	ses vrais slots) comme pour une espèce nue."""
	return dict((snap or {}).get("_sim_equipement") or {})


def _recap_arsenal(bel: dict) -> dict:
	"""Récap lisible de ce que le belligérant engage (affiché par l'écran)."""
	snap = bel["snapshot_reference"]
	arsenal = bel["arsenal"]
	return {
		"attaques": [{"label": p.get("label", ""), "mode": p.get("mode", ""),
					  "portee": max(1, int(p.get("portee", 1) or 1)),
					  "degats": snap.get(p.get("degats", "degats_cc"), "")}
					 for p in snap.get("attaque_profils") or []],
		"sorts": [{"label": s["nom"], "cout_pm": s["cout_pm"], "portee": max(1, s["portee"]),
				   "degats": s["effets"].get("degats", "")} for s in arsenal["sorts"]],
		"competences": [{"label": c["nom"], "cout_pm": c["cout_pm"], "portee": c["portee"],
						 "degats": c["effets"].get("degats", "")} for c in arsenal["competences"]],
		"soutiens": [{"label": s["label"], "cout_pm": s["cout_pm"], "stock": s.get("stock")}
					 for s in arsenal["soutiens"]],
	}


def simuler_duel(spec_a: dict, spec_b: dict, distance: int, passes: int, get_doc_fn,
				 plafond_rounds: int = PLAFOND_ROUNDS, map_tags=(), objets: bool = True) -> dict:
	"""N passes Monte Carlo du duel A vs B à `distance` cases (specs → belligérants)."""
	return simuler_belligerants(construire_belligerant(spec_a, get_doc_fn, map_tags, objets),
								construire_belligerant(spec_b, get_doc_fn, map_tags, objets),
								distance, passes, plafond_rounds)


def simuler_belligerants(bel_a: dict, bel_b: dict, distance: int, passes: int,
						 plafond_rounds: int = PLAFOND_ROUNDS) -> dict:
	"""Le Monte Carlo sur des belligérants DÉJÀ construits — l'endpoint les construit
	une seule fois et les repasse aussi aux potentiels (build_joueur_snapshot lit la
	base : il ne doit tourner qu'une fois par requête). Agrégat complet pour l'écran ;
	le journal détaillé est celui de la PREMIÈRE passe uniquement."""
	distance = max(1, int(distance))
	passes = max(1, int(passes))

	victoires = {"a": 0, "b": 0}
	pv_restants = {"a": [], "b": []}
	rounds_liste = []
	nuls = 0
	journal: list = []

	for i in range(passes):
		res = _derouler_duel(bel_a, bel_b, distance, journal if i == 0 else None, plafond_rounds)
		rounds_liste.append(res["rounds"])
		if res["vainqueur"] is None:
			nuls += 1
		else:
			victoires[res["vainqueur"]] += 1
			pv_restants[res["vainqueur"]].append(res["pv_restants"])

	rounds_tries = sorted(rounds_liste)

	def _cote(camp: str, bel: dict) -> dict:
		pv = pv_restants[camp]
		return {
			"label": bel["label"],
			"victoires": victoires[camp],
			"taux": round(victoires[camp] / passes, 4),
			"pv_restants_moyens": round(sum(pv) / len(pv), 1) if pv else None,
			"pv_max_reference": int(bel["snapshot_reference"].get("pv_max", 0) or 0),
			"profil": fiche_snapshot(bel["snapshot_reference"]),
			"image_route": bel.get("image_route", ""),
			"niveaux": bel.get("niveaux"),
			"arsenal": _recap_arsenal(bel),
		}

	return {
		"passes": passes,
		"distance": distance,
		"a": _cote("a", bel_a),
		"b": _cote("b", bel_b),
		"nuls": nuls,
		"rounds": {
			"moyen": round(sum(rounds_liste) / passes, 1),
			"mediane": rounds_tries[passes // 2],
			"min": rounds_tries[0],
			"max": rounds_tries[-1],
		},
		"journal": journal,
	}

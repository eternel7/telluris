# utils/journal.py
# Le CARNET du personnage : ce qu'il consigne lui-même (entrées libres) et ce qu'il a croisé
# (bestiaire des espèces rencontrées). C'est le contenu de l'onglet 📖 de la fiche.
#
# ⚠️ COLLISION DE VOCABULAIRE — partout ailleurs dans ce projet, « journal » désigne un LOG :
# `combat_doc["journal"]` est le journal de combat, `dev_tools.journal` le tampon de sortie
# d'un script, `simulateur` a le sien. Ici, et ici seulement, c'est le carnet d'un joueur.
#
# ⚠️ Le journal appartient au PRINCIPAL et à lui seul : l'onglet est `tab-principal-only`
# (un compagnon n'a ni quêtes, ni relations marchandes, ni journal). Aucun `_acteur`, aucun
# choix d'écrivain — contrairement au tableau d'information de l'auberge.
#
# ⚠️ Les fournitures d'écriture ne sont PAS redéfinies ici : papier + encre + plume, la
# dépense TOUT OU RIEN et le scan sac + slots vivent dans `utils/auberge.py` et y sont testés.
# Deux règles d'écriture divergentes seraient le défaut que ce module doit éviter.
#
# ⚠️ SENS D'IMPORT : `utils/combat.py` → `utils/journal.py` → `utils/auberge.py`. La chaîne
# d'`auberge` ne tire jamais `combat` (vérifié), il n'y a donc pas de cycle — mais `auberge`
# ne doit JAMAIS se mettre à importer `combat` ni `journal`, sous peine d'en créer un.
#
# Logique pure : accès base injectés, on MUTE sans sauver — l'appelant persiste. World-vars
# lues VIA le module `character_stats`, jamais en `from … import` (la valeur serait figée à
# l'import et le réglage à chaud sans effet).

import time

from models import character_stats
from utils import auberge

# Le carnet et le bestiaire vivent sur le doc personnage, comme `lieux_visites` et
# `compagnons_connus`. ⚠️ Champs ABSENTS ⇒ carnet vide et bestiaire vide (Convention §4) :
# aucune migration, un doc déjà en base continue de tourner.
CHAMP_ENTREES = "journal"
CHAMP_BESTIAIRE = "bestiaire"


def now_epoch() -> int:
	"""Epoch entier — miroir de `auberge.now_epoch` / `montures.now_epoch`. Local pour que ce
	module reste léger : importer `utils.quetes` (la source unique du jeu) tirerait bois +
	expedition + recrutement + marche derrière lui."""
	return int(time.time())


# ── Le carnet : ce que le personnage écrit lui-même ─────────────────────────────

def entrees_de(character: dict) -> list:
	"""Les entrées du carnet, de la PLUS ANCIENNE à la plus récente (ordre d'écriture).
	C'est le rendu qui les retourne — le stockage garde l'ordre naturel, sans quoi le
	bornage `[-MAX:]` sacrifierait les plus RÉCENTES au lieu des plus vieilles."""
	return list((character or {}).get(CHAMP_ENTREES) or [])


def entrees_max() -> int:
	"""⚠️ Planché à 1 : un carnet qui ne peut rien retenir ne serait pas un carnet."""
	return max(1, int(character_stats.JOURNAL_ENTREES_MAX))


def longueur_max() -> int:
	return max(1, int(character_stats.JOURNAL_LONGUEUR_MAX))


def nouvelle_entree(character: dict, texte: str, lieu_label_txt: str = "",
					now: int | None = None) -> dict:
	"""Consigne une entrée et la renvoie. Mute le personnage SANS le sauver.

	⚠️ `texte` est supposé DÉJÀ borné par l'appelant (`auberge.nettoyer_texte`, qui préserve
	les sauts de ligne) — même contrat que `auberge.nouveau_message` : c'est l'appelant qui
	sait de quelle sorte de saisie il s'agit et qui doit lever le 422 sur un texte vide.

	⚠️ Le LIEU est stocké sous son LIBELLÉ, pas sous son id : les docs `lieu:*` sont les plus
	gros du jeu et sont exclus du cache de requête. Le résoudre au rendu coûterait une lecture
	énorme par entrée affichée — c'est la même dénormalisation qu'`auteur_nom` sur un message
	de taverne, et pour exactement la même raison.

	⚠️ Le bornage sacrifie les entrées les plus ANCIENNES (`[-MAX:]`), patron de
	`combats_recompenses` / `compagnons_connus`."""
	entree = {
		"cree_at": now_epoch() if now is None else int(now),
		"lieu": str(lieu_label_txt or ""),
		"texte": texte,
	}
	entrees = entrees_de(character)
	entrees.append(entree)
	character[CHAMP_ENTREES] = entrees[-entrees_max():]
	return entree


# ── Le bestiaire : ce que le personnage a croisé ────────────────────────────────
# Une espèce entre au bestiaire dès qu'elle a été RENCONTRÉE, tuée ou non — c'est un carnet
# d'observation, pas un tableau de chasse. Le compteur `tues` dit le reste.

def lieux_max() -> int:
	return max(1, int(character_stats.JOURNAL_BESTIAIRE_LIEUX_MAX))


def bestiaire_de(character: dict) -> dict:
	return dict((character or {}).get(CHAMP_BESTIAIRE) or {})


def lieu_connu(character: dict, espece_id: str, lieu_id: str) -> bool:
	"""Cette espèce a-t-elle DÉJÀ été notée dans ce lieu ? C'est ce test qui permet à
	l'appelant de n'aller relire le doc `lieu:*` (le plus gros du jeu, hors cache) que lorsque
	la paire est neuve — un combat répété au même endroit ne coûte alors aucune lecture."""
	fiche = bestiaire_de(character).get(espece_id) or {}
	return any(l.get("id") == lieu_id for l in (fiche.get("lieux") or []))


def noter_rencontres(character: dict, monstres: list, lieu_id: str = "",
					 lieu_label_txt: str = "", now: int | None = None) -> bool:
	"""Note au bestiaire TOUTES les espèces de ce combat. Mute sans sauver ; renvoie True si
	quelque chose a changé.

	⚠️ Compte les monstres VIVANTS COMME MORTS — c'est toute la différence avec
	`quetes.maj_progress_kills`, qui ne retient que `not vivant`. Une bête qu'on a fuie a bien
	été rencontrée, et elle doit figurer au carnet.

	⚠️ Un seul incrément de `combats` par combat et par espèce, même si le combat en aligne
	cinq exemplaires : `combats` compte les RENCONTRES, `tues` compte les bêtes.

	⚠️ `lieux` est borné à `JOURNAL_BESTIAIRE_LIEUX_MAX` et garde les PREMIERS vus : le carnet
	dit où l'on a commencé à croiser l'espèce, il n'a pas à devenir un journal de bord."""
	instant = now_epoch() if now is None else int(now)
	fiches = bestiaire_de(character)
	change = False

	vues: dict[str, int] = {}
	for m in monstres or []:
		eid = (m or {}).get("espece_id")
		if not eid:
			continue
		# Le monstre est compté comme TUÉ seulement s'il est tombé ; l'espèce, elle, est
		# notée dans tous les cas — d'où deux compteurs et un seul passage.
		vues[eid] = vues.get(eid, 0) + (0 if m.get("vivant", True) else 1)

	for eid, tues in vues.items():
		fiche = dict(fiches.get(eid) or {})
		if not fiche:
			fiche = {"vu_at": instant, "combats": 0, "tues": 0, "lieux": []}
		fiche["combats"] = int(fiche.get("combats", 0) or 0) + 1
		fiche["tues"] = int(fiche.get("tues", 0) or 0) + tues
		fiche["vu_at"] = int(fiche.get("vu_at") or instant)
		lieux = list(fiche.get("lieux") or [])
		if lieu_id and len(lieux) < lieux_max() and not any(l.get("id") == lieu_id for l in lieux):
			lieux.append({"id": lieu_id, "label": str(lieu_label_txt or "")})
		fiche["lieux"] = lieux
		fiches[eid] = fiche
		change = True

	if change:
		character[CHAMP_BESTIAIRE] = fiches
	return change


def lieux_a_nommer(character: dict, monstres: list, lieu_id: str) -> bool:
	"""Faut-il relire le doc lieu pour cette passe ? True dès qu'UNE espèce du combat n'a pas
	encore ce lieu à son actif et qu'il lui reste de la place. Sert d'aiguillage à l'appelant :
	sans lui, `finalize_combat` paierait une lecture de `lieu:*` à chaque combat."""
	if not lieu_id:
		return False
	fiches = bestiaire_de(character)
	for m in monstres or []:
		eid = (m or {}).get("espece_id")
		if not eid:
			continue
		lieux = (fiches.get(eid) or {}).get("lieux") or []
		if len(lieux) < lieux_max() and not any(l.get("id") == lieu_id for l in lieux):
			return True
	return False


# ── Payloads ────────────────────────────────────────────────────────────────────

def bestiaire_payload(character: dict, get_doc_fn) -> list:
	"""Ce que le joueur a le droit de lire d'une espèce : nom, image, description, tags, et
	les lieux où il l'a croisée. Trié de la plus récemment vue à la plus ancienne.

	⚠️ PROJECTION CONTRÔLÉE, jamais le doc brut (patron `montures._offre_view`) :
	`base_attributes` reste au serveur. Le carnet d'un aventurier n'est pas une feuille de
	stats, et publier les fourchettes livrerait l'équilibrage au joueur.

	⚠️ Les `espece:*` sont dans `_CACHEABLE_PREFIXES` : les relire ici est amorti par le cache
	de requête, et donne un nom et une image toujours à jour (une espèce renommée en admin se
	corrige d'elle-même dans tous les carnets)."""
	sortie = []
	for eid, fiche in bestiaire_de(character).items():
		doc = get_doc_fn(eid) if eid else None
		if not doc:
			continue                     # espèce supprimée en admin : on ne l'invente pas
		sortie.append({
			"id": eid,
			"nom": doc.get("nom", "") or eid.split(":", 1)[-1],
			"image": doc.get("image", ""),
			"description": doc.get("description", ""),
			"tags": list(doc.get("tags") or []),
			"lieux": [str(l.get("label") or "") for l in (fiche.get("lieux") or [])
					  if l.get("label")],
			"combats": int(fiche.get("combats", 0) or 0),
			"tues": int(fiche.get("tues", 0) or 0),
			"vu_at": int(fiche.get("vu_at", 0) or 0),
		})
	sortie.sort(key=lambda e: (-e["vu_at"], e["nom"]))
	return sortie


def journal_payload(character: dict, get_doc_fn) -> dict:
	"""TOUT le contenu de l'onglet 📖, recalculé (Convention §10) : servi au contexte `/play`
	ET renvoyé par l'endpoint d'écriture. Sans ce bloc unique, l'onglet resterait figé sur
	l'état du dernier chargement de la page.

	⚠️ Les entrées partent de la PLUS RÉCENTE : c'est l'ordre de lecture d'un carnet, et le
	client ne réordonne rien.

	⚠️ `fournitures` est un DÉTAIL et pas un booléen — le refus doit pouvoir dire CE QUI
	manque, sinon le joueur ne sait pas quoi aller acheter. Testé sur le personnage SEUL : on
	écrit son journal avec sa propre plume, jamais avec celle d'un compagnon."""
	return {
		"entrees": list(reversed(entrees_de(character))),
		"bestiaire": bestiaire_payload(character, get_doc_fn),
		"fournitures": auberge.fournitures_presentes(get_doc_fn, [character]),
		"longueur_max": longueur_max(),
		"entrees_max": entrees_max(),
	}

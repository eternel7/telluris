# utils/expedition.py
# Capacités MISES EN COMMUN par l'expédition : ce que le groupe sait faire ensemble, et
# non ce que chaque personnage sait faire seul. Premier branchement historique : la hache
# partagée (`bois.a_outil_coupe`) — il suffit qu'UN membre porte l'outil pour que tout le
# monde puisse abattre. Second : le marchandage, mené par le plus charismatique du groupe.
#
# ⚠️ « L'expédition » = le principal + ses COMPAGNONS, JAMAIS les montures : une bête ne
# négocie pas et ne manie pas une hache. C'est toute la raison d'être de `membres()` — ne
# pas retomber sur `recrutement.porteurs_effectifs`, qui répond à une autre question
# (« qui porte pour moi ? », montures comprises).
#
# Logique pure (get_doc injecté), ne sauvegarde jamais — l'endpoint persiste. World-vars
# lues via le module character_stats (jamais from-import).

from models import character_stats
from utils.characters import item_ref_id, item_sous_categorie
from utils.consommables import caracts_avec_buffs
from utils import recrutement


def membres(character: dict, get_doc_fn=None) -> list:
	"""Les personnages de l'expédition : le principal EN TÊTE, puis ses compagnons actifs.

	L'ordre compte — plusieurs appelants départagent les ex æquo par « le premier de la
	liste gagne », et c'est le joueur qui doit gagner à mérite égal."""
	return [character, *recrutement.groupe_effectif(character, get_doc_fn)]


def porteur_avec_tag(get_doc_fn, porteurs: list, tag: str) -> bool:
	"""True si UN des porteurs a l'item taggé dans son sac OU dans son équipement.

	Scanner les slots autant que l'inventaire est indispensable : une hache est le plus
	souvent EN MAIN, pas rangée."""
	besoin = str(tag or "").lower()
	if not besoin:
		return False
	for porteur in porteurs or []:
		refs = list((porteur or {}).get("inventaire", []) or [])
		refs += [r for r in ((porteur or {}).get("slots", {}) or {}).values() if r]
		for ref in refs:
			item_id = item_ref_id(ref)
			if not item_id:
				continue
			doc = get_doc_fn(item_id)
			if doc and besoin in [str(t).lower() for t in (doc.get("tags") or [])]:
				return True
	return False


def porteur_avec_sous_categorie(get_doc_fn, porteurs: list, sous_categorie: str) -> bool:
	"""True si UN des porteurs a un item de cette SOUS-CATÉGORIE dans son sac OU dans son
	équipement. Frère de `porteur_avec_tag` — même parcours (les slots comptent autant que
	l'inventaire : une plume est le plus souvent en main), autre prédicat.

	⚠️ Le test passe par `characters.item_sous_categorie` et JAMAIS par `doc["sous_categorie"]`
	lu à la main : ce chokepoint retombe sur la `categorie` quand la sous-catégorie est vide.
	C'est ce qui faisait passer les encres pour de simples « composant » avant qu'elles ne
	reçoivent la leur, et c'est la seule lecture qui s'accorde avec le marché."""
	besoin = str(sous_categorie or "").lower()
	if not besoin:
		return False
	for porteur in porteurs or []:
		refs = list((porteur or {}).get("inventaire", []) or [])
		refs += [r for r in ((porteur or {}).get("slots", {}) or {}).values() if r]
		for ref in refs:
			item_id = item_ref_id(ref)
			if not item_id:
				continue
			doc = get_doc_fn(item_id)
			if doc and str(item_sous_categorie(doc) or "").lower() == besoin:
				return True
	return False


def meilleur_negociateur(character: dict, compagnons: list, seuil_min: int | None = None) -> tuple:
	"""Qui parle au marchand : `(doc, cha, est_compagnon)` — le plus haut Cha BUFFÉ.

	Un compagnon ne prend la parole à la place du joueur que si sa confiance atteint
	`seuil_min` (défaut MARCHANDAGE_COMPAGNON_AFFINITE_MIN) : c'est ce qui rattache le
	partage de capacités à la relation. ⚠️ Le seuil ne filtre QUE les compagnons — le
	principal est toujours candidat, il n'a pas d'affinité envers lui-même ; `seuil_min=0`
	signifie donc « tous les compagnons éligibles », pas « principal seul ».

	Départage à Cha ÉGAL : le principal d'abord (il ouvre la liste et l'on n'écrase qu'à
	strictement mieux) — le joueur ne se fait pas voler la parole à mérite identique.

	Fonction PURE : `caracts_avec_buffs` ne lit que des champs dénormalisés. ⚠️ En
	contrepartie, l'appelant doit avoir appelé `sync_equipment_bonus(m)` sur chaque membre
	AVANT, sinon les buffs d'équipement lus ici sont ceux du dernier calcul."""
	seuil = (character_stats.MARCHANDAGE_COMPAGNON_AFFINITE_MIN
			 if seuil_min is None else int(seuil_min))
	meilleur, meilleur_cha, est_compagnon = character, _cha_buffe(character), False
	for av in compagnons or []:
		if recrutement.affinite_de(character, av.get("_id")) < seuil:
			continue
		cha = _cha_buffe(av)
		if cha > meilleur_cha:
			meilleur, meilleur_cha, est_compagnon = av, cha, True
	return meilleur, meilleur_cha, est_compagnon


def _cha_buffe(porteur: dict) -> int:
	"""Cha effectif (échelle ×10) : caract courante + les 3 sources de buffs repliées par
	`consommables._sources_de_buffs` (équipement, passives, effets à durée). Le lire brut
	était le bug historique du marchandage — `aura_sympathique` (+5 Cha) n'y pesait rien."""
	return int(caracts_avec_buffs(porteur or {}).get("Cha", 0) or 0)

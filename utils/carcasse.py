# utils/carcasse.py
# Découpe d'une grosse carcasse en PORTIONS LOCALISÉES (tête, corps, pattes, queue, ailes).
#
# POURQUOI. `charge_max = F×5`, soit 250 à 500 kg pour un personnage abouti — et vingt
# carcasses du bestiaire dépassent 100 kg, jusqu'aux 12 tonnes du mammouth. Le ramassage en
# combat les REFUSE (« Trop lourd »), si bien que le plus gros gibier du jeu ne rapportait
# rigoureusement RIEN. La découpe rend ce butin accessible en le rendant divisible : on
# emporte la tête et les pattes, on abandonne le corps.
#
# Miroir délibéré de `utils/bois.py` — même geste joueur (`POST /api/couper`, bouton 🪓),
# même mise en commun de l'outil dans le groupe (`expedition.porteur_avec_tag`), même
# contrat (« retire la source, dépose les pièces au sol »). Deux différences seulement :
#   · l'OUTIL est une lame (`CARCASSE_TRANCHANT_TAG`) et non une hache de bûcheron — on ne
#     débite pas un cerf à la scie passe-partout ;
#   · la cible n'est pas un tier plus petit de la même essence mais une LISTE de portions
#     hétérogènes, lue dans la donnée.
#
# ⚠️ LA TABLE ANATOMIQUE EST DE LA DONNÉE, PAS DU CODE. Le doc carcasse porte un champ
# `decoupe: [{item, quantite, fraction}, …]` (posé par `dev/gen_carcasses_parties.py`) et
# c'est LUI, et lui seul, qui rend une carcasse découpable. Conséquences voulues :
#   · champ absent ⇒ comportement d'avant, aucune migration ;
#   · l'auteur décide espèce par espèce, sans toucher au code (un homme-arbre n'a pas de
#     queue, un dragon a des ailes) ;
#   · le seuil de poids (`CARCASSE_DECOUPE_POIDS_MIN`) ne sert qu'au générateur — en jeu il
#     n'y a rien à comparer, la question est déjà tranchée par la présence du champ.
#
# ⚠️ CONSERVATION DE LA MASSE. Les `fraction` d'une carcasse somment à 1.0 (contrôlé par le
# générateur) et la dernière pièce reçoit le RELIQUAT, exactement comme `bois.repartir_poids`
# : le total des portions égale le poids de l'instance au centime près, quels que soient les
# arrondis. Sans ce reliquat, découper créerait ou détruirait de la matière — et le prix d'un
# item dérivant de son poids, ce serait une machine à or (ou à perte) selon le sens.
#
# Logique pure (get_doc injecté), ne sauvegarde jamais — l'endpoint persiste.
# Tunables lus via le module character_stats (réassignés par load_world_variables).

from models import character_stats
from utils.characters import item_ref_weight
from utils import expedition


def entrees_decoupe(item_doc) -> list:
	"""Entrées `decoupe` NORMALISÉES d'un doc carcasse → [{item, quantite, fraction}].

	Fail-soft entrée par entrée : une entrée sans `item`, de quantité nulle ou de fraction
	non strictement positive est écartée plutôt que de faire échouer toute la découpe — une
	donnée à moitié fausse doit coûter une portion, pas la mécanique entière."""
	out = []
	for e in ((item_doc or {}).get("decoupe") or []):
		if not isinstance(e, dict):
			continue
		cible = str(e.get("item") or "").strip()
		if not cible.startswith("item:"):
			continue
		try:
			# ⚠️ PAS de `or 1` sur la quantité : `0 or 1` vaut 1 en Python, ce qui
			# transformerait un « zéro » explicite (une partie qu'on a voulu désactiver) en
			# une pièce bien réelle. Absent ⇒ 1 ; zéro ⇒ entrée écartée, plus bas.
			quantite = int(1 if e.get("quantite") is None else e["quantite"])
			fraction = float(e.get("fraction") or 0)
		except (TypeError, ValueError):
			continue
		if quantite <= 0 or fraction <= 0:
			continue
		out.append({"item": cible, "quantite": quantite, "fraction": fraction})
	return out


def seuil_decoupe(item_doc) -> float:
	"""Poids d'instance minimal pour débiter cet item — champ `decoupe_poids_min` du doc,
	repli sur la world-var. La valeur est BAKÉE par le générateur sur chaque carcasse
	découpable, si bien que le client la lit dans l'item qu'il affiche déjà et n'a aucune
	variable de monde à connaître."""
	try:
		seuil = float((item_doc or {}).get("decoupe_poids_min"))
	except (TypeError, ValueError):
		seuil = float(character_stats.CARCASSE_DECOUPE_POIDS_MIN)
	return max(0.0, seuil)


def item_est_decoupable(item_doc, poids=None) -> bool:
	"""Item débitable : il porte au moins une entrée `decoupe` exploitable, et l'instance
	pèse au moins `seuil_decoupe`.

	⚠️ On ne teste PAS la sous-catégorie — c'est la donnée qui décide, pas une famille d'items.
	⚠️ Mais on teste BIEN le poids, et c'est un garde-fou, pas une commodité : les quantités du
	dépeçage sont planchées à 1 (`max(1, round(base × poids / DEPECAGE_POIDS_REF))`), donc
	débiter sans fin finirait par rendre 1 crâne et 1 cœur PAR MORCEAU, quelle que soit sa
	petitesse — une machine à matière première. Le seuil ferme cette porte avant qu'une
	découpe récursive ne soit authorée. `poids=None` (le doc seul, sans instance) répond sur
	la seule présence du champ : c'est ce dont le générateur et les tests ont besoin."""
	if not entrees_decoupe(item_doc):
		return False
	if poids is None:
		return True
	try:
		return float(poids) >= seuil_decoupe(item_doc)
	except (TypeError, ValueError):
		return False


def decouper_ref(source_ref, source_item_doc) -> list | None:
	"""Débite une réf de carcasse → liste de réfs `{item, poids}` (une par pièce), ou None
	si l'item n'est pas découpable.

	Le poids de chaque pièce = `fraction / quantite × poids de l'instance` ; la DERNIÈRE
	pièce emporte le reliquat, si bien que la somme retombe exactement sur le poids source
	(cf. l'avertissement de conservation de la masse en tête de module)."""
	total = round(float(item_ref_weight(source_ref) or 0), 2)
	if not item_est_decoupable(source_item_doc, total) or total <= 0:
		return None
	entrees = entrees_decoupe(source_item_doc)

	pieces = []
	for e in entrees:
		part = total * e["fraction"] / e["quantite"]
		for _ in range(e["quantite"]):
			pieces.append({"item": e["item"], "poids": round(part, 2)})
	if not pieces:
		return None
	# Reliquat sur la dernière pièce : les fractions somment à 1.0 mais les arrondis, eux,
	# ne se compensent pas tout seuls. Plancher à 0.01 — une pièce de poids nul serait
	# gratuite ET invisible dans la fiche d'inventaire.
	ecart = round(total - sum(p["poids"] for p in pieces), 2)
	pieces[-1]["poids"] = max(0.01, round(pieces[-1]["poids"] + ecart, 2))
	return pieces


def a_arme_tranchante(character, get_doc_fn, compagnons=None) -> bool:
	"""True si un item du sac OU de l'équipement porte le tag d'arme tranchante.

	PARTAGÉ par l'expédition, comme la hache de `bois.a_outil_coupe` et par le même
	chokepoint (`expedition.porteur_avec_tag`) : il suffit qu'UN membre porte une lame.
	⚠️ Signature et sémantique CALQUÉES sur `bois.a_outil_coupe` — `compagnons` reçoit ce que
	l'endpoint lui passe (`recrutement.groupe_effectif`, donc des compagnons, PAS de monture) ;
	`None` ne scanne que le personnage."""
	return expedition.porteur_avec_tag(
		get_doc_fn, [character, *(compagnons or [])], character_stats.CARCASSE_TRANCHANT_TAG)

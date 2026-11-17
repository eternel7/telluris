# utils/bruit.py
# BRUIT DU GROUPE (pur, Auteur 17/11) — un petit groupe léger fait moins de bruit, donc attire
# moins d'ennemis. Une seule mesure, trois effets sur les rencontres de zone :
#   • POSITION dans la fourchette d'effectif de l'espèce (`combat.instantiate_groupes`) :
#     seul ⇒ bas de fourchette, groupe de référence ⇒ milieu, convoi ⇒ haut (jamais au-delà) ;
#   • chance d'un SECOND groupe ;
#   • FRÉQUENCE des combats (`zones.resolve_zone_event`, combats seulement : les récoltes gardent
#     la leur).
# Les GRADES ne bougent pas : la part de budget par spécimen se calcule sur le milieu de la
# fourchette, quel que soit l'effectif tiré.
#
# Points = 1 (joueur) + compagnons, montures (guides compris) et escortés pondérés, + le TAUX DE
# CHARGE du groupe (poids porté par tous les porteurs / leur charge max cumulée) × un poids.
# Réglages : variables de monde `RENCONTRE_BRUIT_*` (lues par attribut de module, à chaud).
# `RENCONTRE_BRUIT_REFERENCE` à 0 ⇒ `actif()` faux ⇒ comportement d'avant partout.
# Portée : zones de nature (ni ville, ni mer ; les donjons à étages ont leurs salles) — `s_applique`.

from models import character_stats

NIVEAUX = (
	# (rapport maximal, clé, libellé) — le premier dont le rapport tient gagne.
	(0.75, "discret", "🤫 Discret"),
	(1.25, "audible", "👣 Audible"),
	(None, "bruyant", "📣 Bruyant"),
)


def actif() -> bool:
	return float(character_stats.RENCONTRE_BRUIT_REFERENCE or 0) > 0


def taux_charge(porte: float, charge_max: float) -> float:
	"""Poids porté / charge max cumulée ; aucune capacité ⇒ 0 (rien ne peut être chargé)."""
	try:
		porte, charge_max = float(porte or 0), float(charge_max or 0)
	except (TypeError, ValueError):
		return 0.0
	if charge_max <= 0:
		return 0.0
	return max(0.0, porte / charge_max)


def sources(nb_compagnons: int, nb_montures: int, nb_proteges: int, taux: float) -> list:
	"""Détail des points, dans l'ordre d'affichage : `[{cle, libelle, nb, points}]`.
	Le joueur vaut toujours 1 point."""
	cs = character_stats
	out = [{"cle": "joueur", "libelle": "Vous", "nb": 1, "points": 1.0}]
	for cle, libelle, nb, poids in (
		("compagnons", "Compagnons", nb_compagnons, cs.RENCONTRE_BRUIT_COMPAGNON),
		("montures", "Montures", nb_montures, cs.RENCONTRE_BRUIT_MONTURE),
		("proteges", "Personnes escortées", nb_proteges, cs.RENCONTRE_BRUIT_PROTEGE),
	):
		nb = max(0, int(nb or 0))
		if nb:
			out.append({"cle": cle, "libelle": libelle, "nb": nb, "points": nb * float(poids)})
	taux = max(0.0, float(taux or 0))
	if taux > 0:
		out.append({"cle": "charge", "libelle": "Charge", "taux": round(taux, 2),
					"points": taux * float(cs.RENCONTRE_BRUIT_CHARGE)})
	return out


def points(srcs: list) -> float:
	return sum(float(s.get("points") or 0) for s in srcs or [])


def rapport(pts: float) -> float:
	"""Points / référence : 1 = le groupe qui joue comme avant. Inactif ⇒ 1."""
	ref = float(character_stats.RENCONTRE_BRUIT_REFERENCE or 0)
	if ref <= 0:
		return 1.0
	return max(0.0, float(pts or 0)) / ref


def position_fourchette(pts: float) -> float:
	"""Position [0, 1] dans la fourchette d'effectif : référence ⇒ 0,5, double ⇒ haut."""
	return max(0.0, min(1.0, rapport(pts) / 2))


def facteur_second(pts: float) -> float:
	return max(0.0, min(rapport(pts), float(character_stats.RENCONTRE_BRUIT_SECOND_MAX)))


def facteur_combat(pts: float) -> float:
	cs = character_stats
	lo = float(cs.RENCONTRE_BRUIT_FREQ_MIN)
	hi = max(lo, float(cs.RENCONTRE_BRUIT_FREQ_MAX))
	return max(lo, min(hi, rapport(pts)))


def niveau(pts: float) -> tuple:
	"""`(clé, libellé)` du niveau de bruit affiché au joueur."""
	r = rapport(pts)
	for borne, cle, libelle in NIVEAUX:
		if borne is None or r < borne:
			return cle, libelle
	return NIVEAUX[-1][1], NIVEAUX[-1][2]


def tirer_effectif(fourch: tuple, position: float, rand) -> int:
	"""Effectif dans `fourch` = (min, max) autour de `min + position × écart`, à ±1 près
	(différence de deux uniformes : penché vers le centre visé), BORNÉ à la fourchette."""
	mn, mx = fourch
	centre = mn + max(0.0, min(1.0, float(position))) * (mx - mn)
	n = int(round(centre + rand.random() - rand.random()))
	return max(mn, min(mx, n))


def milieu(fourch: tuple) -> float:
	"""Effectif de référence d'une fourchette : sert à la part de budget par spécimen."""
	mn, mx = fourch
	return (mn + mx) / 2


def s_applique(lieu: dict | None, en_mer: bool = False, est_ville: bool = False) -> bool:
	"""Le bruit agit-il ici ? Zones de nature seulement (Auteur, 17/11) : ni en ville, ni en
	mer. Les donjons à étages n'y passent pas (leurs salles fixent l'effectif)."""
	return actif() and bool(lieu) and not en_mer and not est_ville


def mesurer(character: dict, compagnons: list, montures: list, proteges: list,
			poids_fn, charge_max_fn) -> dict:
	"""Bloc du bruit, servi tel quel au client : `{points, rapport, niveau, libelle, sources}`.
	`poids_fn(doc)` = poids porté, `charge_max_fn(doc)` = capacité (porteur quelconque) ;
	les porteurs sont le joueur, ses compagnons et ses montures (les escortés ne portent rien)."""
	porteurs = [character] + list(compagnons or []) + list(montures or [])
	porte = sum(float(poids_fn(p) or 0) for p in porteurs)
	cap = sum(float(charge_max_fn(p) or 0) for p in porteurs)
	srcs = sources(len(compagnons or []), len(montures or []), len(proteges or []),
				   taux_charge(porte, cap))
	pts = points(srcs)
	cle, libelle = niveau(pts)
	return {"points": round(pts, 2), "rapport": round(rapport(pts), 2),
			"niveau": cle, "libelle": libelle, "actif": actif(),
			"sources": [{**s, "points": round(s["points"], 2)} for s in srcs]}


def du_groupe(character: dict, get_doc_fn) -> dict:
	"""`mesurer` avec le groupe lu en base (chokepoints `groupe_effectif`,
	`montures_effectives`, `proteges_effectifs`). Imports différés : module pur importable
	par `combat` sans tirer le recrutement."""
	from utils import escorte, montures, recrutement
	from utils.characters import carried_weight
	return mesurer(
		character,
		recrutement.groupe_effectif(character, get_doc_fn),
		montures.montures_effectives(character, get_doc_fn),
		escorte.proteges_effectifs(character, get_doc_fn),
		carried_weight,
		lambda p: montures.charge_max_porteur(p, get_doc_fn),
	)


def bloc_ici(character: dict, lieu: dict | None, get_doc_fn, en_mer: bool = False,
			 est_ville: bool = False) -> dict | None:
	"""Bloc `bruit` de /play et des pas : `du_groupe` là où le bruit agit, None ailleurs
	(l'indicateur se masque)."""
	if not s_applique(lieu, en_mer=en_mer, est_ville=est_ville):
		return None
	return du_groupe(character, get_doc_fn)

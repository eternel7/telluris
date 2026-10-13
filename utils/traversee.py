# utils/traversee.py
# Traversées maritimes (pur) : un capitaine, sur les quais d'un port, vend le passage ; le
# joueur perd alors la main, le navire avance seul case par case sur une carte de mer et
# chaque case peut tirer une rencontre. À la dernière case, il débarque sur les quais d'en face.
#
# Une ROUTE = un doc `traversee:<depart>_<arrivee>` :
#   {"type": "traversee", "label", "depart": {"lieu"}, "arrivee": {"lieu", "pos": [x, y]},
#    "carte": "lieu:<mer>", "chemin": [[x, y], …]  (points de passage, développés ici),
#    "segments": [{"de": etape, "zone": "zone:<id>", "intensite": p}, …],
#    "rencontres": [{"espece", "zones": [...]}], "prix": {"passager_cuivre", "monture_cuivre"},
#    "profil_weights"?: {...}}
# ⚠️ La gradation du danger (côtier / haute mer) est portée par la ROUTE (`segments`), pas
# par des `zone_influences` sur la carte de mer : la route se suffit et la carte reste nue.
#
# État sur le personnage, champ absent = à terre (aucune migration) :
#   character["traversee"] = {"route", "etape", "depart_lieu", "debut"}
# En mer, `lieu` vaut la CARTE de mer et `position` la case du navire : /play, le cycle
# combat → /play et les vitaux marchent sans cas particulier. Une défaite en mer laisse le
# joueur à 1 PV (règle commune) et la traversée intacte : le voyage reprend au /play suivant.
#
# Mute sans sauver ; DB injectée là où il en faut. Le hasard passe par `rand_fn`.

import random

from utils import zones as zones_util
from utils.characters import CUIVRE_PAR_ARGENT, CUIVRE_PAR_OR


def est_route(doc: dict | None) -> bool:
	return bool(doc) and doc.get("type") == "traversee"


def cases_du_chemin(points: list) -> list:
	"""Points de passage → cases CONTIGUËS sur 8 directions (pas diagonal permis), sans
	doublon consécutif. Chaque tronçon avance d'une case à la fois sur l'axe dominant et
	répartit l'autre (Bresenham), donc le navire ne saute jamais de case."""
	cases: list = []
	for point in points or []:
		x1, y1 = int(point[0]), int(point[1])
		if not cases:
			cases.append([x1, y1])
			continue
		x0, y0 = cases[-1]
		dx, dy = x1 - x0, y1 - y0
		n = max(abs(dx), abs(dy))
		for i in range(1, n + 1):
			case = [x0 + round(dx * i / n), y0 + round(dy * i / n)]
			if case != cases[-1]:
				cases.append(case)
	return cases


def total_etapes(route: dict) -> int:
	"""Nombre de cases de la route (départ compris)."""
	return len(cases_du_chemin(route.get("chemin")))


def segment_a(route: dict, etape: int) -> dict | None:
	"""Le segment de danger en vigueur à `etape` : le DERNIER dont `de` est ≤ etape."""
	courant = None
	for seg in sorted(route.get("segments") or [], key=lambda s: int(s.get("de", 0))):
		if int(seg.get("de", 0)) <= etape:
			courant = seg
	return courant


def prix(route: dict, nb_passagers: int, nb_montures: int) -> int:
	"""Prix du passage en cuivre : par tête (joueur + compagnons) + supplément par monture."""
	tarif = route.get("prix") or {}
	return (max(0, int(tarif.get("passager_cuivre", 0))) * max(1, int(nb_passagers))
			+ max(0, int(tarif.get("monture_cuivre", 0))) * max(0, int(nb_montures)))


def texte_bourse(cuivre: int) -> str:
	"""« 1 or, 2 argent et 50 cuivre » — les seules dénominations non nulles."""
	cuivre = max(0, int(cuivre or 0))
	o, reste = divmod(cuivre, CUIVRE_PAR_OR)
	a, c = divmod(reste, CUIVRE_PAR_ARGENT)
	parts = [f"{n} {nom}" for n, nom in ((o, "or"), (a, "argent"), (c, "cuivre")) if n]
	if not parts:
		return "rien"
	return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " et " + parts[-1]


def _placement(zone_id: str, x: int, y: int) -> dict:
	"""Placement synthétique d'une case autour du navire : la zone du segment est active
	là où il se trouve, et nulle part ailleurs."""
	return {"zone": zone_id, "x": x, "y": y, "w": 1, "h": 1, "rot": 0, "forme": "rectangle",
			"bbox": {"x_min": x - 0.5, "x_max": x + 0.5, "y_min": y - 0.5, "y_max": y + 0.5}}


def lieu_en_mer(carte_doc: dict | None, route: dict, etape: int) -> dict:
	"""Copie de la carte de mer « vue depuis le navire » à `etape` : zone du segment posée
	sur la case du navire, `rencontres` et `profil_weights` de la route. C'est CE lieu que
	`combat.start_combat` lit en mer — son code ne connaît aucune traversée."""
	cases = cases_du_chemin(route.get("chemin"))
	x, y = cases[min(max(0, etape), len(cases) - 1)] if cases else (0, 0)
	lieu = dict(carte_doc or {"_id": route.get("carte")})
	seg = segment_a(route, etape)
	lieu["zone_influences"] = [_placement(seg["zone"], x, y)] if seg and seg.get("zone") else []
	lieu["rencontres"] = list(route.get("rencontres") or [])
	if route.get("profil_weights"):
		lieu["profil_weights"] = dict(route["profil_weights"])
	return lieu


def evenement_etape(route: dict, etape: int, zone_defs: dict, rand_fn=random.random) -> dict | None:
	"""Tirage d'une rencontre à `etape`. La probabilité est l'`intensite` du SEGMENT (la
	route règle son danger), pas l'`intensite_max` du zone-def, faite pour l'exploration."""
	seg = segment_a(route, etape)
	if not seg or not seg.get("zone"):
		return None
	zone_def = (zone_defs or {}).get(seg["zone"])
	if not zone_def:
		return None
	zone_def = dict(zone_def, intensite_max=float(seg.get("intensite", 0) or 0))
	cases = cases_du_chemin(route.get("chemin"))
	if not cases:
		return None
	x, y = cases[min(max(0, etape), len(cases) - 1)]
	return zones_util.resolve_zone_event(
		x, y, [_placement(seg["zone"], x, y)], {seg["zone"]: zone_def}, rand_fn=rand_fn)


def zones_de_route(route: dict) -> set:
	return {s["zone"] for s in (route.get("segments") or []) if s.get("zone")}


def embarquer(character: dict, route: dict, debut: int = 0) -> None:
	"""Le joueur monte à bord : état posé, `lieu` = carte de mer, navire sur la 1re case.
	Les champs transitoires de lieu (Conventions §6) sont vidés comme pour un déplacement."""
	cases = cases_du_chemin(route.get("chemin"))
	if not cases:
		raise ValueError("route sans chemin")
	character["traversee"] = {
		"route": route["_id"],
		"etape": 0,
		"depart_lieu": character.get("lieu"),
		"debut": int(debut),
	}
	character["lieu"] = route["carte"]
	character["position"] = {"x": cases[0][0], "y": cases[0][1]}
	character["objets_au_sol"] = []
	character["ressource_recoltable"] = None
	character.pop("atelier_courant", None)


def en_mer(character: dict) -> bool:
	return bool((character or {}).get("traversee"))


def avancer(character: dict, route: dict) -> str:
	"""Une case de plus. Renvoie "arrivee" quand le navire a touché la dernière case
	(le débarquement est un geste à part, `debarquer`), sinon "en_mer"."""
	etat = character["traversee"]
	cases = cases_du_chemin(route.get("chemin"))
	etape = min(int(etat.get("etape", 0)) + 1, len(cases) - 1)
	etat["etape"] = etape
	character["position"] = {"x": cases[etape][0], "y": cases[etape][1]}
	return "arrivee" if etape >= len(cases) - 1 else "en_mer"


def debarquer(character: dict, route: dict) -> dict:
	"""Fin de traversée : `lieu`/`position` d'arrivée, état retiré. Renvoie la position."""
	arrivee = route.get("arrivee") or {}
	pos = arrivee.get("pos") or [0, 0]
	character["lieu"] = arrivee["lieu"]
	character["position"] = {"x": int(pos[0]), "y": int(pos[1])}
	character.pop("traversee", None)
	return character["position"]


def payload_client(character: dict, route: dict, destination_label: str, pas_ms: int) -> dict | None:
	"""Ce que /play injecte en `TRAVERSEE` pour le mode voyage."""
	if not en_mer(character) or not route:
		return None
	etat = character["traversee"]
	return {
		"route": route["_id"],
		"etape": int(etat.get("etape", 0)),
		"total": total_etapes(route),
		"destination": destination_label,
		"pas_ms": int(pas_ms),
	}

# utils/traces.py
# TRACES de monstres sur la carte (pur) : à chaque pas, le groupe relève les traces de la PIRE
# menace qu'un combat de zone pourrait faire surgir ICI — espèces rattachées aux zones actives
# à la position (`zones.especes_rencontrables`, le pool même de `start_combat`), chacune à
# chacun des grades qui PEUVENT sortir (`zones.profils_candidats` après compatibilité et cap
# ville, le tirage même de `combat._pick_profil`), mesurée par `potentiel.potentiel_menace`
# (combat × fuite interdite, la mesure du rang de /admin/table et des épreuves).
#
# - Sans forestier : le seul LIBELLÉ de dangerosité (`potentiel.RANG_LIBELLES`) et le rang.
# - Avec un FORESTIER dans le groupe (`expedition.membres`, principal ou compagnon, vocation
#   `forestier`) : il nomme l'espèce et son grade.
#
# Rien n'est stocké sur le personnage : la lecture est refaite à chaque pas (aucune
# migration, rien à périmer). Le client n'annonce qu'un CHANGEMENT de lecture (`cle`).
# ⚠️ Le potentiel est mémoïsé par process sur les `_rev` de l'espèce et du profil : un objet
# de la liste `items` d'une espèce modifié sans toucher l'espèce garde l'ancienne valeur
# jusqu'au redémarrage.

from models import character_stats
from utils import accord_espece, potentiel
from utils.zones import (
	compute_zone_intensity, load_zone_defs_for_lieu, especes_rencontrables, profils_candidats, profils_compatibles,
	resolve_profil_weights,
)

VOCATION_PISTEUR = "forestier"

_MENACE_CACHE: dict = {}


def _menace(espece: dict, profil: dict | None, get_doc_fn) -> float:
	"""`potentiel_menace` mémoïsé sur (espèce, _rev, profil, _rev). 0 si illisible."""
	cle = (espece.get("_id"), espece.get("_rev"),
		   (profil or {}).get("_id"), (profil or {}).get("_rev"))
	if cle not in _MENACE_CACHE:
		try:
			_MENACE_CACHE[cle] = potentiel.potentiel_menace(
				espece["_id"], (profil or {}).get("_id"), get_doc_fn)[0]
		except Exception:
			_MENACE_CACHE[cle] = 0.0
	return _MENACE_CACHE[cle]


def placements_actifs(lieu: dict, position: dict, zone_defs: dict) -> list:
	"""Placements de zone dont la forme contient la position (même test que `start_combat`)."""
	px, py = (position or {}).get("x", 0), (position or {}).get("y", 0)
	return [p for p in (lieu or {}).get("zone_influences", []) or []
			if zone_defs.get(p.get("zone"))
			and compute_zone_intensity(px, py, p, zone_defs[p.get("zone")]) > 0.0]


def pire_menace(lieu: dict, position: dict, zone_defs: dict, especes: dict, profils: list,
				get_doc_fn, cap_niveau: int | None = None, menace_fn=None) -> dict | None:
	"""`{espece, profil, potentiel, rang}` de la pire rencontre possible à cette position, ou
	None (aucune espèce rattachée aux zones actives). `especes` = {id: doc} ; `profils` = tous
	les docs profil ; `cap_niveau` = plafond de grade d'une ville (`TOWN_PROFIL_NIVEAU_MAX`).
	`menace_fn(espece, profil, get_doc_fn)` injectable (tests). Ex æquo : la première espèce
	des rencontres l'emporte."""
	menace_fn = menace_fn or _menace
	actifs = placements_actifs(lieu, position, zone_defs)
	ids = especes_rencontrables(lieu, {p.get("zone") for p in actifs})
	if not ids:
		return None
	if cap_niveau is not None:
		profils = [p for p in profils if p.get("niveau", 1) <= cap_niveau]
	weights = resolve_profil_weights(actifs, lieu or {})
	meilleur = None
	ordre = [r.get("espece") for r in (lieu or {}).get("rencontres", []) or []]
	for eid in sorted(ids, key=lambda i: ordre.index(i) if i in ordre else len(ordre)):
		espece = especes.get(eid)
		if not espece:
			continue
		compat = profils_compatibles(profils, espece)
		# Aucun compatible ⇒ point médian sans profil (cf. `combat.instantiate_monsters`).
		candidats = profils_candidats(compat, weights)[0] if compat else [None]
		for profil in candidats:
			v = menace_fn(espece, profil, get_doc_fn)
			if meilleur is None or v > meilleur["potentiel"]:
				meilleur = {"espece": espece, "profil": profil, "potentiel": v}
	if meilleur is None:
		return None
	meilleur["rang"] = potentiel.rang_de_potentiel(meilleur["potentiel"])
	return meilleur


def pisteur(membres: list) -> dict | None:
	"""Le premier membre du groupe de vocation forestier (principal EN TÊTE), ou None."""
	return next((m for m in membres or [] if (m or {}).get("voc") == VOCATION_PISTEUR), None)


def _nom_membre(m: dict) -> str:
	return (m or {}).get("prenom") or (m or {}).get("nom") or "Votre forestier"


def payload(menace: dict | None, lecteur: dict | None) -> dict | None:
	"""Bloc `traces` du client : `{cle, texte, rang, libelle}` (+ `espece`, `profil` lus par un
	forestier), ou None. `cle` change quand la lecture change — le client n'annonce que ça."""
	if not menace:
		return None
	rang = menace["rang"]
	libelle = potentiel.RANG_LIBELLES.get(rang, "")
	danger = f"{libelle} (rang {rang})"
	out = {"rang": rang, "libelle": libelle}
	if not lecteur:
		out["cle"] = "rang|" + rang
		out["texte"] = f"🐾 Des traces dans les parages — danger : {danger}."
		return out
	espece, profil = menace["espece"], menace["profil"]
	nom = accord_espece.groupe(espece, "un")
	grade = f" « {profil['nom']} »" if profil and profil.get("nom") else ""
	verbe = "peuvent" if accord_espece.est_pluriel(espece) else "peut"
	out.update({"espece": espece.get("nom") or espece.get("_id"),
				"profil": (profil or {}).get("nom") or ""})
	out["cle"] = "espece|" + espece.get("_id", "") + "|" + (profil or {}).get("_id", "")
	out["texte"] = (f"🐾 {_nom_membre(lecteur)} lit les traces : {nom}{grade} {verbe} rôder ici — "
					f"{danger}.")
	return out


def traces_ici(character: dict, lieu_doc: dict | None, get_doc_fn, find_docs_fn, membres: list,
			   ville: bool) -> dict | None:
	"""Bloc `traces` à la position du personnage (DB injectée). `membres` =
	`expedition.membres(character)` ; `ville` = lieu à image de ville (grades plafonnés)."""
	if not lieu_doc or not lieu_doc.get("rencontres") or not lieu_doc.get("zone_influences"):
		return None
	zone_defs = load_zone_defs_for_lieu(lieu_doc, get_doc_fn)
	ids = {r.get("espece") for r in lieu_doc.get("rencontres", []) if r.get("espece")}
	especes = {i: d for i, d in ((i, get_doc_fn(i)) for i in ids) if d}
	profils = find_docs_fn({"type": "profil"}) or []
	menace = pire_menace(lieu_doc, character.get("position") or {}, zone_defs, especes, profils,
						 get_doc_fn,
						 cap_niveau=character_stats.TOWN_PROFIL_NIVEAU_MAX if ville else None)
	return payload(menace, pisteur(membres))

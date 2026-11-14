# utils/exigence_arme.py
# Exigence d'ARME d'une compétence (pur) — champ `arme` d'un doc `competence:*` :
#
#     "arme": {"mode": "tir" | ["tir", "jet"], "tags": ["arc"]}
#
# Champ absent (ou sans mode valide) ⇒ aucune exigence : comportement d'avant, aucune
# migration (CLAUDE.md §4).
#
# - `mode` : UN des modes suffit (OU) — cac / jet / tir / bouclier / mains_nues / deux_armes.
# - `tags` (facultatif) : précision relue sur l'objet qui remplit le mode, UN des tags suffit
#   (OU). Les tags d'un objet = ses `tags` + sa `sous_categorie` (arc, arbalete, instrument…) :
#   aucun tag neuf à poser sur les items.
#   `mains_nues` ignore les tags (il n'y a rien à lire) ; `deux_armes` les exige sur CHACUNE.
#
# Ce que l'on PORTE (`armes_portees`) se lit sur les slots du personnage. En combat il est
# FIGÉ dans le snapshot à l'entrée (`armes_portees`), la résolution d'un coup ne lisant
# jamais la base ; un snapshot d'avant n'a pas la clé ⇒ `None` ⇒ aucune vérification.
#
# Consommateurs : `competences` (normalisation, passives, payload), `combat` (garde de
# lancement, profil emprunté), `routers/user.utiliser_competence`, `simulateur` (arsenal).

MODES = ("cac", "jet", "tir", "bouclier", "mains_nues", "deux_armes")

# Mode d'ATTAQUE (profil de `combat._weapon_attacks`) emprunté quand ce mode est rempli.
# `bouclier` et `mains_nues` n'en désignent aucun : la règle d'emprunt d'avant s'applique.
PROFIL_DU_MODE = {"cac": "cac", "deux_armes": "cac", "jet": "jet", "tir": "tir"}

LIBELLES_MODE = {
	"cac": "une arme de mêlée",
	"jet": "une arme de jet",
	"tir": "une arme de tir",
	"bouclier": "un bouclier",
	"mains_nues": "les mains nues",
	"deux_armes": "deux armes de mêlée",
}

# Affichage d'un tag de donnée (sans accent en base) ; un tag absent s'affiche tel quel.
LIBELLES_TAG = {"arbalete": "arbalète", "legere": "légère", "tranchant": "tranchante", "hast": "d'hast"}


def normaliser_arme(raw) -> dict | None:
	"""Vue normalisée `{modes: [...], tags: [...]}`, ou None (aucune exigence). Les modes
	inconnus sont écartés en silence ; s'il n'en reste aucun, il n'y a pas d'exigence."""
	if not isinstance(raw, dict):
		return None
	mode = raw.get("mode")
	brut = mode if isinstance(mode, (list, tuple)) else [mode]
	modes = []
	for m in brut:
		m = str(m or "").strip()
		if m in MODES and m not in modes:
			modes.append(m)
	if not modes:
		return None
	tags = []
	for t in raw.get("tags") or []:
		t = str(t or "").strip()
		if t and t not in tags:
			tags.append(t)
	return {"modes": modes, "tags": tags}


def _entree(item: dict, slot: str) -> dict | None:
	"""Ce que l'objet apporte à une exigence, ou None (ni arme ni bouclier). Le mode d'une
	arme suit `combat._weapon_attacks` : tag `tir`, sinon `jet`, sinon mêlée."""
	categorie = item.get("categorie")
	tags = [str(t) for t in (item.get("tags") or [])]
	sc = str(item.get("sous_categorie") or "")
	if sc:
		tags.append(sc)
	if categorie == "arme":
		mode = "tir" if "tir" in tags else "jet" if "jet" in tags else "cac"
	elif categorie == "armure" and (sc == "bouclier" or "bouclier" in tags):
		mode = "bouclier"
	else:
		return None
	return {"mode": mode, "tags": tags, "slot": slot, "item_id": str(item.get("_id") or "")}


def armes_portees(character: dict, get_doc) -> list:
	"""Armes et bouclier ÉQUIPÉS : `[{mode, tags, slot, item_id}]`, main droite d'abord.
	Tous les slots sont lus, comme `combat._weapon_attacks`."""
	from utils.characters import item_ref_id   # paresseux : `characters` tire beaucoup
	out = []
	slots = (character or {}).get("slots") or {}
	ordre = sorted(slots, key=lambda s: (s != "main_droite", s != "main_gauche", s))
	for slot in ordre:
		item_id = item_ref_id(slots[slot])
		if not item_id:
			continue
		e = _entree(get_doc(item_id) or {}, slot)
		if e:
			out.append(e)
	return out


def _tags_ok(entree: dict, tags: list) -> bool:
	return not tags or any(t in entree["tags"] for t in tags)


def mode_rempli(mode: str, tags: list, armes: list) -> bool:
	if mode == "mains_nues":
		return not any(a["mode"] in ("cac", "jet", "tir") for a in armes)
	if mode == "deux_armes":
		return sum(1 for a in armes if a["mode"] == "cac" and _tags_ok(a, tags)) >= 2
	return any(a["mode"] == mode and _tags_ok(a, tags) for a in armes)


def satisfaite(exigence: dict | None, armes: list | None) -> bool:
	"""Vrai sans exigence, ou si l'on ne sait pas ce qui est porté (`armes` None : snapshot
	d'avant), ou si l'UN des modes est rempli."""
	if not exigence or armes is None:
		return True
	return any(mode_rempli(m, exigence.get("tags") or [], armes) for m in exigence["modes"])


def libelle(exigence: dict | None) -> str:
	"""« une arme de tir (arc) », « une arme de jet ou une arme de tir »… — vide sans
	exigence. Texte servi tel quel au client (`arme_requise`)."""
	if not exigence:
		return ""
	texte = " ou ".join(LIBELLES_MODE[m] for m in exigence["modes"])
	tags = exigence.get("tags") or []
	if tags and exigence["modes"] != ["mains_nues"]:
		texte += f" ({', '.join(LIBELLES_TAG.get(t, t) for t in tags)})"
	return texte


def manquante(comp: dict, armes: list | None) -> str:
	"""Libellé de l'exigence NON remplie, ou "" si la compétence peut partir."""
	exigence = (comp or {}).get("arme")
	return "" if satisfaite(exigence, armes) else libelle(exigence)


def mode_emprunte(exigence: dict | None, armes: list | None) -> str | None:
	"""Mode de profil d'attaque (cac / jet / tir) qu'une frappe martiale emprunte pour
	satisfaire son exigence : le PREMIER mode rempli, dans l'ordre écrit. None ⇒ règle
	d'emprunt d'avant (`combat._profil_emprunte`) — pas d'exigence, rien de porté connu, ou
	un mode qui ne désigne aucun profil (bouclier, mains nues)."""
	if not exigence or armes is None:
		return None
	for m in exigence["modes"]:
		if mode_rempli(m, exigence.get("tags") or [], armes):
			return PROFIL_DU_MODE.get(m)
	return None

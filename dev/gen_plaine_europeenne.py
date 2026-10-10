"""La Plaine européenne, Bruges et Aix-la-Chapelle : trois lieux, leurs grilles et leurs connexions.

POURQUOI UN GÉNÉRATEUR DÉDIÉ : `gen_cartes_pays.py` et `gen_villes_images.py` créent chacun
un lieu par image orpheline, sans parent hors de France et sans connexion. Ici les trois lieux
vont ensemble : les deux cités sont POSÉES sur la plaine (`lieu_parent` + connexions) et la
plaine est rattachée à `lieu:france`. On ne recopie rien : docs minimaux par
`cartes_a_creer` / `villes_a_creer`, grilles par `gen_grille_image.proposer_pour_image`
(profil `pays` : côte murée en nav ; profil ville : `cells` + `nav`).

CONNEXIONS — on ne passe d'une carte à l'autre QUE par elles (le bord d'une carte est une
borne, pas un passage) :
  · France ↔ plaine : côté France, la rangée `FRANCE_Y` — la dernière accessible (les murs
    nav peints de la rangée 1 ferment le nord) ; côté plaine, la case de la zone principale
    la plus au SUD de la colonne correspondante (limite sud accessible).
  · cité ↔ plaine : sur la plaine, la case de la cité et ses voisines (une case par lien, le
    schéma de Reims ↔ France) ; dans la cité, une sortie par route qui quitte la carte : la
    case libre de la zone principale la plus proche du point visé.
  Chaque case est éprouvée sur la grille PROPOSÉE (`grille_image.zones`, règle de marche
  d'exploration) : hors zone principale ⇒ lot refusé, plutôt qu'une porte inatteignable.

REJOUABLE : si `lieu:plaine_europeenne` est déjà dans le dump, rien à créer et AUCUN fichier
écrit ; un seul des `_id` visés déjà pris (lieu ou connexion) ⇒ lot refusé.

Usage :
  python dev/gen_plaine_europeenne.py [--dump jsons/telluris-dump-….json] [--sans-apercu]

Sortie : jsons/plaine_europeenne_a_importer.json (+ jsons/<slug>_grille_apercu.png)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_cartes_pays import cartes_a_creer  # noqa: E402
from dev.gen_villes_images import _taille_image, poser_grille, villes_a_creer  # noqa: E402
from utils import grille_image  # noqa: E402

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "plaine_europeenne_a_importer.json")

IMAGE_PLAINE = "plaine_europeenne.jpg"
PLAINE = "lieu:plaine_europeenne"
FRANCE = "lieu:france"
IMAGES_CITES = ("bruges_city.jpg", "aix_la_chapelle_city.jpg")

# Place des cités sur la plaine (lue sur l'image, 88×48 cases de 16 px) :
#   Bruges — le château dessiné sur le delta de l'Escaut, au débouché du Zwin ;
#   Aix-la-Chapelle — entre Meuse et Rhin, au nord des forêts de l'Ardenne et de l'Eifel.
POSITIONS_PLAINE = {
	"lieu:bruges": (28, 25),
	"lieu:aix_la_chapelle": (41, 29),
}

# Sorties des cités : nom → point visé (une route qui quitte la carte, hors du cadre).
# Bruges n'a pas de sortie au nord : c'est le Zwin et la mer.
SORTIES_CITES = {
	"lieu:bruges": {"ouest": (1, 30), "sud": (40, 46), "est": (86, 30)},
	"lieu:aix_la_chapelle": {"nord": (53, 1), "ouest": (4, 22), "est": (83, 20), "sud": (55, 43)},
}

# France ↔ plaine : (x sur la France, x sur la plaine), d'ouest en est — Flandres, Ardenne,
# Moselle, Rhin. La France, peinte à la main, se lit sur sa rangée 1 : nord fermé par nav.
FRANCE_Y = 1
PASSAGES_FRANCE = ((49, 12), (56, 26), (64, 36), (76, 46))

METADATA = {"type": "chemin", "status": "ouvert"}

# Voisines d'une case, dans l'ordre où les liens les prennent (la case elle-même d'abord).
VOISINES = ((0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1))


def zone_principale(cells, nav):
	"""Ensemble des cases `(x, y)` de la plus grande zone sous la règle de marche."""
	zone, tailles = grille_image.zones(cells, nav)
	if not tailles:
		return set()
	z = max(range(len(tailles)), key=tailles.__getitem__)
	return {(x, y) for y, ligne in enumerate(zone) for x, v in enumerate(ligne) if v == z}


def case_proche(principale, cible):
	"""La case de `principale` la plus proche de `cible` (euclidienne, puis y, puis x) ou None."""
	if not principale:
		return None
	cx, cy = cible
	return min(principale, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0]))


def case_la_plus_au_sud(principale, x):
	"""La case de `principale` de la colonne `x` la plus au sud, ou None."""
	ys = [cy for cx, cy in principale if cx == x]
	return (x, max(ys)) if ys else None


def cases_autour(principale, centre, n):
	"""`n` cases distinctes de `principale` autour de `centre` (lui d'abord), ou None."""
	cases = [(centre[0] + dx, centre[1] + dy) for dx, dy in VOISINES]
	cases = [c for c in cases if c in principale]
	return cases[:n] if len(cases) >= n else None


def connexion(_id, lieu_a, pos_a, lieu_b, pos_b):
	return {"_id": _id, "type": "connection",
		"nodes": [{"lieu": lieu_a, "pos": list(pos_a)}, {"lieu": lieu_b, "pos": list(pos_b)}],
		"metadata": dict(METADATA)}


def connexions_cite(cite_id, principale_cite, principale_plaine):
	"""(docs, refus) des liens plaine ↔ cité."""
	slug = cite_id.split(":", 1)[1]
	sorties = SORTIES_CITES[cite_id]
	centre = POSITIONS_PLAINE[cite_id]
	if centre not in principale_plaine:
		return [], [f"{cite_id} : la case {list(centre)} de la plaine n'est pas dans sa zone principale"]
	cases_plaine = cases_autour(principale_plaine, centre, len(sorties))
	if not cases_plaine:
		return [], [f"{cite_id} : pas {len(sorties)} cases libres autour de {list(centre)} sur la plaine"]
	docs, refus = [], []
	for (nom, cible), pos_plaine in zip(sorties.items(), cases_plaine):
		pos_cite = case_proche(principale_cite, cible)
		if pos_cite is None:
			refus.append(f"{cite_id} : aucune case de sa zone principale pour la sortie {nom}")
			continue
		docs.append(connexion(f"link:plaine_europeenne_to_{slug}_{nom}",
			PLAINE, pos_plaine, cite_id, pos_cite))
	return docs, refus


def connexions_france(france_doc, principale_plaine):
	"""(docs, refus) des liens France ↔ plaine."""
	cells = (france_doc or {}).get("cells") or []
	docs, refus = [], []
	for i, (x_fr, x_pl) in enumerate(PASSAGES_FRANCE, start=1):
		if not grille_image._dans(cells, x_fr, FRANCE_Y) or cells[FRANCE_Y][x_fr] < 1:
			refus.append(f"{FRANCE} : la case [{x_fr}, {FRANCE_Y}] n'est pas accessible")
			continue
		pos_pl = case_la_plus_au_sud(principale_plaine, x_pl)
		if pos_pl is None:
			refus.append(f"{PLAINE} : aucune case de la zone principale en colonne {x_pl}")
			continue
		docs.append(connexion(f"link:france_to_plaine_europeenne_{i:02d}",
			FRANCE, (x_fr, FRANCE_Y), PLAINE, pos_pl))
	return docs, refus


def lieux_a_creer(docs, taille_fn):
	"""(plaine, [cités], refus) — docs SANS grille. Plaine déjà en base ⇒ (None, [], [])."""
	ids = {d.get("_id") for d in docs}
	if PLAINE in ids:
		return None, [], []
	plaines, refus = cartes_a_creer([IMAGE_PLAINE], docs, taille_fn)
	cites, refus_c = villes_a_creer(list(IMAGES_CITES), docs, taille_fn)
	refus = refus + refus_c
	if not plaines:
		refus.append(f"{IMAGE_PLAINE} : déjà citée par un lieu, ou absente de CARTES")
	attendus = set(POSITIONS_PLAINE)
	trouves = {c["_id"] for c in cites}
	for manquant in sorted(attendus - trouves):
		refus.append(f"{manquant} : non créé (image déjà citée ou `_id` pris)")
	if refus:
		return None, [], refus
	for cite in cites:
		cite["lieu_parent"] = PLAINE
	return plaines[0], sorted(cites, key=lambda c: c["_id"]), []


def ids_deja_pris(docs, sortants):
	ids = {d.get("_id") for d in docs}
	return [d["_id"] for d in sortants if d["_id"] in ids]


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = None
	if "--dump" in args:
		i = args.index("--dump")
		if i + 1 >= len(args):
			print("✗ --dump attend un chemin.")
			return 2
		chemin_dump = args[i + 1]
	docs = ggi.charger_dump(chemin_dump)
	if not docs:
		print("✗ aucun dump : passer --dump ou exporter un telluris-dump-*.json dans jsons/.")
		return 1
	france = next((d for d in docs if d.get("_id") == FRANCE), None)
	if not france:
		print(f"✗ {FRANCE} absent du dump : impossible d'y rattacher la plaine.")
		return 1

	plaine, cites, refus = lieux_a_creer(docs, _taille_image)
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if plaine is None:
		print(f"{PLAINE} est déjà en base : rien à créer.")
		return 0

	lieux, principales = [], {}
	for doc, profil in [(plaine, "pays")] + [(c, "") for c in cites]:
		chemin = ggi.trouver_image(doc["image"])
		dim = doc["dimensions"]
		proposition = ggi.proposer_pour_image(chemin, dim["x"], dim["y"], doc, profil=profil)
		print(f"{doc['_id']} — {doc['label']}"
			f"{' (' + doc['lieu_parent'] + ')' if doc.get('lieu_parent') else ''}")
		ggi.imprimer_resume(chemin, proposition)
		if "--sans-apercu" not in args:
			slug = doc["_id"].split(":", 1)[1]
			apercu = os.path.join(ggi.DOSSIER_JSONS, f"{slug}_grille_apercu.png")
			ggi.ecrire_apercu(chemin, proposition["cells"], apercu, proposition["nav"],
				proposition["rapport"])
			print(f"  ✎ {os.path.relpath(apercu, RACINE)}")
		print()
		lieux.append(poser_grille(doc, proposition))
		principales[doc["_id"]] = zone_principale(proposition["cells"], proposition["nav"])

	liens, refus = connexions_france(france, principales[PLAINE])
	for cite in cites:
		d, r = connexions_cite(cite["_id"], principales[cite["_id"]], principales[PLAINE])
		liens += d
		refus += r
	sortants = lieux + liens
	refus += [f"{i} : `_id` déjà pris" for i in ids_deja_pris(docs, sortants)]
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	for lien in liens:
		a, b = lien["nodes"]
		print(f"  🔗 {lien['_id']} : {a['lieu']} {a['pos']} ↔ {b['lieu']} {b['pos']}")

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortants, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"\n✎ {os.path.relpath(SORTIE, RACINE)} — {len(lieux)} lieu(x), {len(liens)} connexion(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

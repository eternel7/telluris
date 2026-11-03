"""Les 15 cartes de pays d'Afrique (02/11/2026) : grilles NETTOYÉES, passages, Aksoum sur l'Abyssinie.

Même moteur que `dev/gen_europe_orientale.py` (cette configuration lui est passée : `CARTES`,
`EAUX`, `ANCRES`, `TERRITOIRES`, `CADRE_MINIMUM`, `PAIRES_CALEES`, `extras`) — voir sa docstring :
calage par SUPERPOSITION (`dev/georeferencement_cartes.py` → `calage_cartes.PAIRES`), recalage
de la carte la moins détaillée, passages projetés une case sur deux.

  · `lieu:afrique_du_nord` garde son image et sa grille ; seule la terre que montre une carte
    plus fine (Maroc, Ifriqiya, Sahel, Nubie, Abyssinie) y est mise à 0, comme l'avait fait
    l'Égypte. `lieu:egypte` n'est pas touchée (elle fait foi sur la Nubie).
  · `lieu:afrique` (vue d'ensemble, `continent`) et `lieu:madagascar` (île) : aucun passage.
  · Aksoum passe de l'Afrique du Nord à l'Abyssinie (Auteur, 03/11) : `lieu_parent` réécrit,
    sorties reposées autour de la cité dessinée (stèles, `POSITION_AKSOUM`), mêmes cases dans la
    cité ; les trois liens `link:afrique_du_nord_to_aksoum_*` partent en suppression.

Validation : `python dev/superposer_cartes.py <paire> --import jsons/afrique_a_importer.json`.
Usage : python dev/gen_afrique.py [--dump jsons/telluris-dump-….json] [--sans-apercu]
Sortie : jsons/afrique_a_importer.json (+ jsons/<slug>_grille_apercu.png)
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_europe_orientale as moteur  # noqa: E402

RACINE = moteur.RACINE
SORTIE = os.path.join(RACINE, "jsons", "afrique_a_importer.json")

CARTES = {
	"afrique": ("afrique.jpg", "Afrique"),
	"maroc": ("maroc.jpg", "Maroc et Canaries"),
	"ifriqiya": ("ifriqiya.jpg", "Ifriqiya et Tripolitaine"),
	"senegambie": ("senegambie.jpg", "Sénégambie et Niger"),
	"cote_de_guinee": ("cote_de_guinee.jpg", "Côte de Guinée"),
	"lac_tchad": ("lac_tchad.jpg", "Lac Tchad et Cameroun"),
	"nubie": ("nubie.jpg", "Nubie"),
	"abyssinie": ("abyssinie.jpg", "Abyssinie et Corne"),
	"bassin_du_congo": ("bassin_du_congo.jpg", "Bassin du Congo"),
	"grands_lacs": ("grands_lacs.jpg", "Grands Lacs et côte swahilie"),
	"angola": ("angola.jpg", "Angola et Katanga"),
	"zambeze": ("zambeze.jpg", "Zambèze"),
	"namib_kalahari": ("namib_kalahari.jpg", "Namib et Kalahari"),
	"le_cap": ("le_cap.jpg", "Le Cap"),
	"madagascar": ("madagascar.jpg", "Madagascar"),
}
SOUS_CATEGORIES = {"afrique": "continent"}

# Graines posées dans chaque mer et grand lac (cases), tolérance de couleur.
EAUX = {
	# Vue d'ensemble : mer grise et beige, de la teinte du Sahel — rien n'est muré (comme `europe`).
	"afrique": {"tolerance": 40, "graines": ()},
	"maroc": {"tolerance": 40, "graines": ((15, 30), (8, 8), (70, 7), (78, 6))},
	"ifriqiya": {"tolerance": 40, "graines": ((40, 8), (60, 20), (20, 6), (75, 26))},
	"senegambie": {"tolerance": 40, "graines": ((8, 20), (6, 38))},
	"cote_de_guinee": {"tolerance": 40, "graines": ((30, 42), (60, 38), (12, 40))},
	"lac_tchad": {"tolerance": 40, "graines": ((8, 35), (15, 38), (20, 30), (25, 40), (10, 43), (45, 9), (52, 8))},
	"nubie": {"tolerance": 40, "graines": ((72, 10), (80, 22))},
	"abyssinie": {"tolerance": 40, "graines": ((50, 6), (68, 14), (80, 35))},
	"bassin_du_congo": {"tolerance": 40, "graines": ((5, 30), (5, 12), (7, 22), (9, 34), (72, 38), (80, 20))},
	"grands_lacs": {"tolerance": 40, "graines": ((35, 10), (19, 23), (22, 33), (75, 30), (62, 15), (63, 30), (66, 40), (78, 6))},
	"angola": {"tolerance": 40, "graines": ((6, 20), (8, 40), (18, 10), (16, 25), (15, 38))},
	"zambeze": {"tolerance": 40, "graines": ((75, 35), (73, 25))},
	"namib_kalahari": {"tolerance": 45, "graines": ((8, 20), (8, 30), (15, 10), (15, 25), (17, 38), (5, 5), (8, 42), (12, 15))},
	"le_cap": {"tolerance": 40, "graines": ((6, 20), (15, 40), (65, 38), (75, 25), (10, 10), (10, 30), (70, 20), (60, 32), (45, 36))},
	"madagascar": {"tolerance": 40, "graines": ((25, 20), (60, 25), (30, 40), (65, 10), (75, 40))},
}

ANCRES = {
	"afrique": (40, 20), "maroc": (40, 30), "ifriqiya": (30, 35), "senegambie": (50, 25),
	"cote_de_guinee": (40, 20), "lac_tchad": (40, 25), "nubie": (40, 25), "abyssinie": (25, 25),
	"bassin_du_congo": (40, 25), "grands_lacs": (40, 25), "angola": (50, 25), "zambeze": (40, 25),
	"namib_kalahari": (60, 25), "le_cap": (40, 15), "madagascar": (40, 25),
	"afrique_du_nord": (40, 30), "espagne": (40, 24), "egypte": (40, 30),
}

# Les déferlantes blanches du cap (Le Cap) : de la mer, illisible à la couleur.
TERRITOIRES = {
	"le_cap": ((0, 17, 35, 47), (18, 45, 40, 47)),
}
# Cadre plus épais que ce que lit le profil (haut, bas, gauche, droite).
CADRE_MINIMUM = {
	"maroc": (5, 4, 4, 4),
	"le_cap": (5, 4, 5, 5),
}

# Paires CALÉES (`dev/georeferencement_cartes.py`) : (carte qui FAIT FOI, carte RECALÉE, nom de
# la frontière | None = recalage seul). La carte PLUS DÉTAILLÉE fait foi : l'Afrique du Nord,
# à petite échelle, est RECALÉE sur le Maroc, l'Ifriqiya, la Sénégambie, le lac Tchad, la Nubie
# et l'Abyssinie (comme sur l'Égypte) — la carte et son image restent, seule la terre que montre
# une carte plus fine y est fermée. L'Égypte ne bouge pas : elle fait foi sur l'Afrique du Nord
# (déjà recalée) et sur la Nubie.
PAIRES_CALEES = (
	("espagne", "maroc", None),
	("maroc", "afrique_du_nord", "Route du Sahara"),
	("ifriqiya", "afrique_du_nord", "Route des oasis"),
	("maroc", "ifriqiya", "Route du Maghreb"),
	("senegambie", "afrique_du_nord", "Piste de Tombouctou"),
	("lac_tchad", "afrique_du_nord", "Piste du Kanem"),
	("egypte", "nubie", None),
	("nubie", "afrique_du_nord", "Route de Méroé"),
	("abyssinie", "afrique_du_nord", "Route d'Adulis"),
	("senegambie", "cote_de_guinee", "Route du Fouta"),
	("cote_de_guinee", "lac_tchad", "Route du Bénin"),
	("lac_tchad", "bassin_du_congo", "Route de l'Oubangui"),
	("lac_tchad", "nubie", "Route du Darfour"),
	("nubie", "bassin_du_congo", "Route du Bahr el-Ghazal"),
	("nubie", "grands_lacs", "Route du Sudd"),
	("abyssinie", "nubie", "Route du Nil Bleu"),
	("abyssinie", "grands_lacs", "Route du Rift"),
	("grands_lacs", "bassin_du_congo", "Route des Grands Lacs"),
	("bassin_du_congo", "angola", "Route du Kasaï"),
	("grands_lacs", "angola", "Route du Katanga"),
	("grands_lacs", "zambeze", "Route du Zambèze"),
	("angola", "zambeze", "Route du Barotsé"),
	("angola", "namib_kalahari", "Route du Cunene"),
	("zambeze", "namib_kalahari", "Route de l'Okavango"),
	("le_cap", "namib_kalahari", "Gué de l'Orange"),
	("le_cap", "zambeze", "Route du Limpopo"),
	("zambeze", "madagascar", None),
)

# Aksoum sur l'Abyssinie : la cité aux stèles, au nord du plateau (lue sur l'image).
AKSOUM = "lieu:aksoum"
# Liens en base remplacés par ce lot (pas de case protégée autour) : les sorties d'Aksoum.
LIENS_REMPLACES = ("link:afrique_du_nord_to_aksoum_",)
ANCIEN_PARENT = "lieu:afrique_du_nord"
POSITION_AKSOUM = (31, 13)
SORTIES_AKSOUM = ("est", "ouest", "sud")


def extras(par_id, cartes, zones):
	"""(docs, suppressions, rapport) : Aksoum rattachée à l'Abyssinie, sorties reposées."""
	from dev.gen_plaine_europeenne import cases_autour, libelle_sortie, sans_rev
	aksoum = par_id.get(AKSOUM)
	if not aksoum:
		return [], [], ["⚠ lieu:aksoum absent du dump : rien à déplacer"]
	anciens = {n: par_id.get(f"link:afrique_du_nord_to_aksoum_{n}") for n in SORTIES_AKSOUM}
	cases = cases_autour(zones["abyssinie"], POSITION_AKSOUM, len(SORTIES_AKSOUM))
	if not cases:
		return [], [], [f"✗ Abyssinie : pas {len(SORTIES_AKSOUM)} cases libres autour de "
			f"{list(POSITION_AKSOUM)}"]
	docs = []
	if aksoum.get("lieu_parent") != moteur.lid("abyssinie"):
		doc = sans_rev(copy.deepcopy(aksoum))
		doc["lieu_parent"] = moteur.lid("abyssinie")
		docs.append(doc)
	label = aksoum.get("label") or "Aksoum"
	for nom, pos in zip(SORTIES_AKSOUM, cases):
		ancien = anciens[nom]
		dans_cite = next((n["pos"] for n in (ancien or {}).get("nodes", []) if n.get("lieu") == AKSOUM),
			None)
		if dans_cite is None:
			continue
		docs.append({"_id": f"link:abyssinie_to_aksoum_{nom}", "type": "connection",
			"nodes": [{"lieu": moteur.lid("abyssinie"), "pos": list(pos)},
				{"lieu": AKSOUM, "pos": list(dans_cite), "label": libelle_sortie(label, nom)}],
			"metadata": dict(moteur.METADATA)})
	suppressions = [{"_id": a["_id"], "_deleted": True} for a in anciens.values() if a]
	return docs, suppressions, [f"Aksoum → Abyssinie : {len(docs) - (1 if docs and docs[0].get('type') == 'lieu' else 0)} "
		f"sortie(s), {len(suppressions)} ancien(s) lien(s) supprimé(s)"]


if __name__ == "__main__":
	raise SystemExit(moteur.main(sys.modules[__name__]))

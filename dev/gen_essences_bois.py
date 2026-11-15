"""Essences de bois au-delà des feuillus tempérés : conifères, Méditerranée, terres sèches,
forêts tropicales — chacune avec sa chaîne de découpe complète.

    python dev/gen_essences_bois.py [--dump chemin]

Sortie : jsons/essences_bois_a_importer.json   (carte d'import de /admin)

- Une essence = tag `essence_<slug>` + une pièce par calibre de `BOIS_A_COUPER` : `arbre`,
  `tronc`, `gros_rondin`, `rondin`, `petit_rondin`, `branche` — les ids suivent ceux des
  15 feuillus déjà en base (`item:<Nom>`, `item:Tronc_<Nom>`, `item:<Forme>_de_<Nom>`).
  `bois.cible_coupe` et le bûcheron de colonisation (`colonisation.objets_du_metier`) les
  trouvent par ce tag et cette sous-catégorie, sans autre déclaration.
- PALMIERS (tag `palmier`) : chaîne RÉDUITE — arbre → stipe (tronc) → tronçon (rondin,
  TERMINAL : sans `a_couper`) + palme (branche). La découpe saute déjà les calibres absents.
- Complète aussi le `petit_rondin` qui manquait à l'alisier, l'aulne, l'orme et le saule
  (rareté reprise de leur rondin en base).
- Descriptions : la table UNIQUE `gen_descriptions_items.ESSENCES` × `FORMES_BOIS` /
  `FORMES_PALMIER` (le trait de chaque essence n'est écrit qu'une fois).

Idempotent : relit le dump le plus récent et n'émet que les docs ABSENTS ; un `_id` déjà en
base n'est jamais réécrit (l'import fait un PUT complet)."""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import gen_descriptions_items as desc  # noqa: E402
from models import character_stats  # noqa: E402
from utils import bois  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "essences_bois_a_importer.json")

# Masse d'un RONDIN par densité de bois (kg, min-max) — les autres calibres en dérivent selon
# les rapports des feuillus en base (chêne : rondin 35-75, gros 90-170, petit 14-28).
DENSITES = {
	"tres_leger": (14, 32),
	"leger": (18, 40),
	"moyen": (22, 50),
	"lourd": (25, 55),
	"tres_lourd": (35, 75),
}
BRANCHES = {"tres_leger": (0.3, 1.5), "leger": (0.4, 1.8), "moyen": (0.6, 2.2), "lourd": (0.7, 2.5),
			"tres_lourd": (1, 3)}

# slug d'essence → (suffixe d'id, nom de l'arbre, nom dans les formes, densité, masse max de
# l'arbre sur pied (kg), rareté, famille). `famille` : icône et chaîne (palmier = réduite).
ESSENCES = {
	# Conifères boréaux et montagnards
	"pin_sylvestre": ("Pin_sylvestre", "Pin sylvestre", "Pin sylvestre", "leger", 9000, "commun", "conifere"),
	"sapin": ("Sapin", "Sapin", "Sapin", "leger", 12000, "commun", "conifere"),
	"epicea": ("Epicea", "Épicéa", "Épicéa", "tres_leger", 10000, "commun", "conifere"),
	"meleze": ("Meleze", "Mélèze", "Mélèze", "moyen", 9000, "commun", "conifere"),
	"if": ("If", "If", "If", "lourd", 4000, "peu commun", "conifere"),
	"pin_cembro": ("Pin_cembro", "Pin cembro", "Pin cembro", "leger", 6000, "peu commun", "conifere"),
	# Méditerranée et Levant
	"olivier": ("Olivier", "Olivier", "Olivier", "tres_lourd", 4000, "commun", "feuillu"),
	"chene_vert": ("Chene_vert", "Chêne vert", "Chêne vert", "tres_lourd", 6000, "commun", "feuillu"),
	"chene_liege": ("Chene_liege", "Chêne-liège", "Chêne-liège", "lourd", 6000, "peu commun", "feuillu"),
	"pin_parasol": ("Pin_parasol", "Pin parasol", "Pin parasol", "leger", 8000, "commun", "conifere"),
	"cypres": ("Cypres", "Cyprès", "Cyprès", "moyen", 6000, "commun", "conifere"),
	"cedre": ("Cedre", "Cèdre", "Cèdre", "moyen", 20000, "peu commun", "conifere"),
	"caroubier": ("Caroubier", "Caroubier", "Caroubier", "lourd", 5000, "peu commun", "feuillu"),
	"figuier": ("Figuier", "Figuier", "Figuier", "tres_leger", 2500, "commun", "feuillu"),
	# Terres sèches et chaudes
	"palmier_dattier": ("Palmier_dattier", "Palmier dattier", "Dattier", "moyen", 2500, "commun", "palmier"),
	"doum": ("Doum", "Palmier doum", "Doum", "moyen", 2000, "peu commun", "palmier"),
	"acacia": ("Acacia", "Acacia", "Acacia", "tres_lourd", 3500, "commun", "feuillu"),
	"tamaris": ("Tamaris", "Tamaris", "Tamaris", "lourd", 1500, "commun", "feuillu"),
	"sycomore": ("Sycomore", "Sycomore", "Sycomore", "leger", 7000, "peu commun", "feuillu"),
	"baobab": ("Baobab", "Baobab", "Baobab", "tres_leger", 40000, "peu commun", "feuillu"),
	"arganier": ("Arganier", "Arganier", "Arganier", "tres_lourd", 2500, "peu commun", "feuillu"),
	"eucalyptus": ("Eucalyptus", "Eucalyptus", "Eucalyptus", "lourd", 15000, "commun", "feuillu"),
	# Forêts tropicales
	"ebene": ("Ebene", "Ébénier", "Ébène", "tres_lourd", 5000, "rare", "feuillu"),
	"acajou": ("Acajou", "Acajou", "Acajou", "moyen", 20000, "peu commun", "feuillu"),
	"iroko": ("Iroko", "Iroko", "Iroko", "lourd", 25000, "peu commun", "feuillu"),
	"okoume": ("Okoume", "Okoumé", "Okoumé", "tres_leger", 20000, "commun", "feuillu"),
	"palissandre": ("Palissandre", "Palissandre", "Palissandre", "tres_lourd", 8000, "rare", "feuillu"),
	"santal": ("Santal", "Santal", "Santal", "lourd", 1500, "rare", "feuillu"),
}

# Le `petit_rondin` manquant des feuillus déjà en base : slug → (suffixe d'id, nom, densité).
PETITS_RONDINS_MANQUANTS = {
	"alisier": ("Alisier", "Alisier", "moyen"),
	"aulne": ("Aulne", "Aulne", "tres_leger"),
	"orme": ("Orme", "Orme", "moyen"),
	"saule": ("Saule", "Saule", "tres_leger"),
}

ICONES = {"arbre": {"conifere": "🌲", "feuillu": "🌳", "palmier": "🌴"},
		  "tronc": {"conifere": "🌲", "feuillu": "🌳", "palmier": "🌴"},
		  "branche": {"conifere": "🌲", "feuillu": "🌳", "palmier": "🌿"}}
FORMES_NOM = {"tronc": "Tronc", "gros_rondin": "Gros rondin", "rondin": "Rondin",
			  "petit_rondin": "Petit rondin", "branche": "Branche"}
FORMES_NOM_PALMIER = {"tronc": "Stipe", "rondin": "Tronçon de stipe", "branche": "Palme"}
CHAINE_PALMIER = ("arbre", "tronc", "rondin", "branche")


def _de(nom: str) -> str:
	"""« de Sapin » / « d'If » — élision devant voyelle (accentuée comprise)."""
	return ("d'" if nom[0].lower() in "aeiouyéèêàâîïôöûü" else "de ") + nom


def _poids(forme: str, densite: str, arbre_max: int) -> list:
	r1, r2 = DENSITES[densite]
	plancher = max(80, arbre_max // 60)
	return {
		"arbre": [plancher, arbre_max],
		"tronc": [plancher, arbre_max // 2],
		"gros_rondin": [round(r1 * 2.5), round(r2 * 2.3)],
		"rondin": [r1, r2],
		"petit_rondin": [round(r1 * 0.4), round(r2 * 0.37)],
		"branche": list(BRANCHES[densite]),
	}[forme]


def _id(forme: str, suffixe: str) -> str:
	if forme == "arbre":
		return f"item:{suffixe}"
	if forme == "tronc":
		return f"item:Tronc_{suffixe}"
	return f"item:{FORMES_NOM[forme].replace(' ', '_')}_de_{suffixe}"


def piece(slug: str, forme: str, suffixe: str, nom_arbre: str, nom_forme: str, densite: str,
		  arbre_max: int, rarete: str, famille: str) -> dict:
	palmier = famille == "palmier"
	tags = ["bois", f"essence_{slug}"]
	if palmier:
		tags.append("palmier")
	# Coupable : tout calibre au-dessus de la branche, sauf le tronçon de stipe (terminal).
	if forme != "branche" and not (palmier and forme == "rondin"):
		tags.insert(1, "a_couper")
	noms = FORMES_NOM_PALMIER if palmier else FORMES_NOM
	nom = nom_arbre if forme == "arbre" else f"{noms[forme]} {_de(nom_forme)}"
	doc = {"_id": _id(forme, suffixe), "type": "item", "nom": nom, "sous_categorie": forme,
		   "icon": ICONES.get(forme, {}).get(famille, "🪵"), "rarete": rarete, "categorie": "composant",
		   "slots": [], "tags": tags, "poids": _poids(forme, densite, arbre_max)}
	texte = desc.description_de(doc, {}, {})
	if not texte:
		sys.exit(f"ERREUR : aucune description pour {doc['_id']} (essence absente de gen_descriptions_items.ESSENCES ?)")
	return desc.avec_description(doc, texte)


def generer(par_id: dict) -> list:
	docs = []
	for slug, (suffixe, nom_arbre, nom_forme, densite, arbre_max, rarete, famille) in ESSENCES.items():
		formes = CHAINE_PALMIER if famille == "palmier" else character_stats.BOIS_A_COUPER
		for forme in formes:
			docs.append(piece(slug, forme, suffixe, nom_arbre, nom_forme, densite, arbre_max, rarete, famille))
	for slug, (suffixe, nom, densite) in PETITS_RONDINS_MANQUANTS.items():
		rondin = par_id.get(f"item:Rondin_de_{suffixe}") or {}
		docs.append(piece(slug, "petit_rondin", suffixe, nom, nom, densite, 0,
						  rondin.get("rarete", "commun"), "feuillu"))
	return [d for d in docs if d["_id"] not in par_id]


def controler(docs: list, par_id: dict) -> None:
	"""Collisions d'`_id`, et chaque pièce coupable descend bien vers la pièce attendue."""
	ids = [d["_id"] for d in docs]
	assert len(ids) == len(set(ids)), "doublon d'_id dans la sortie"
	tous = {**par_id, **{d["_id"]: d for d in docs}}
	items = [d for d in tous.values() if d.get("type") == "item"]
	find = lambda q: [d for d in items if all(d.get(k) == v for k, v in q.items())]
	for d in docs:
		if not bois.item_est_coupable(d):
			continue
		cible = bois.cible_coupe(d, find)
		assert cible and bois.essence_de(cible) == bois.essence_de(d), f"découpe sans suite : {d['_id']}"
	for slug, (_s, _n, _f, _d, _m, _r, famille) in ESSENCES.items():
		attendu = CHAINE_PALMIER if famille == "palmier" else character_stats.BOIS_A_COUPER
		chaine = {d.get("sous_categorie") for d in items if bois.essence_de(d) == slug}
		assert chaine == set(attendu), f"chaîne incomplète pour {slug} : {sorted(chaine)}"
	for slug in PETITS_RONDINS_MANQUANTS:
		assert any(bois.essence_de(d) == slug and d.get("sous_categorie") == "petit_rondin" for d in items), slug


def dernier_dump(chemin=None) -> dict:
	chemin = chemin or sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))[-1]
	return {d["_id"]: d for d in desc.charger(chemin)}


def main(argv: list) -> None:
	chemin = argv[argv.index("--dump") + 1] if "--dump" in argv else None
	par_id = dernier_dump(chemin)
	docs = generer(par_id)
	controler(docs, par_id)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump({"docs": docs}, f, ensure_ascii=False, indent=1)
		f.write("\n")
	print(f"{len(docs)} doc(s) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv[1:])

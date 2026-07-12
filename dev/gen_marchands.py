"""Génère `jsons/marchands_a_importer.json` : un tenancier `pnj:marchand_<categorie>` par
catégorie de lieu marchand (= toute catégorie ayant des recettes).

Les magasins ne portent PAS de champ `pnj` : `utils/transport.entree_marchand` dérive le
tenancier de la catégorie du lieu. Il suffit donc que ces docs existent en base — aucun doc
`lieu:*` n'est à modifier.

Chaque marchand porte le MÊME arbre de dialogue (le squelette de la quête de transport,
piloté par les flags `transport_offert` / `transport_a_livrer`), avec un texte d'accueil
propre à son métier. La liste des catégories est lue dans l'export des recettes — la même
source que `marche.besoins_categorie`, pour ne jamais diverger.

⚠️ Le `nom` d'un doc généré n'est qu'un REPLI : chaque boutique peut rebaptiser son tenancier
via `nom` dans son entrée `pnj` (Lucinda Mortecroix à La Flèche d'Argent, Hermine Valcorbe au
fumoir…). Un texte de dialogue ne cite donc JAMAIS un nom en dur — il utilise `{pnj}` (celui
à qui l'on parle), `{donneur}` / `{destinataire}` (les deux bouts d'une course), et aucun
pronom genré autour d'eux : le tenancier peut être une femme.

	python dev/gen_marchands.py
"""

import glob
import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "marchands_a_importer.json")

# Portraits actuellement présents dans templates/resources/pnj/ — attribués en rotation pour
# que la fonctionnalité tourne dès l'import. À remplacer par un portrait par métier.
PORTRAITS = [
	"humain_m_guerrier01.jpg", "humain_f_duelliste01.jpg", "humain_m_lettre01.jpg",
	"humain_m_guerrier02.jpg", "elfe_m_lettre01.jpg", "humain_m_guerrier03.jpg",
	"elfe_m_lettre02.jpg",
]

# Métier → (nom du tenancier, ce qu'il vend, ambiance de sa boutique).
METIERS = {
	"apothicairerie":       ("Dame Ysoline", "l'apothicaire", "Des bocaux d'herbes sèches montent jusqu'au plafond."),
	"armurerie":            ("Maître Gorm", "l'armurier", "Le marteau retombe en cadence sur l'enclume."),
	"atelier_d_artisan":    ("Maître Aldric", "l'artisan", "Copeaux et limaille jonchent l'établi."),
	"atelier_de_cirier":    ("Dame Bertrade", "la cirière", "L'odeur chaude de la cire d'abeille sature l'air."),
	"atelier_de_l_empenneur": ("Le vieux Renaud", "l'empenneur", "Des plumes triées par teinte attendent en fagots."),
	"bijouterie":           ("Maître Orfeo", "le bijoutier", "Une loupe pend au-dessus d'un plateau de pierres."),
	"boucherie":            ("Maître Barnabé", "le boucher", "Les quartiers de viande pendent aux crocs."),
	"bourrellerie":         ("Maître Guerric", "le bourrelier", "Harnais et colliers de trait sèchent sur des tréteaux."),
	"boyauderie":           ("Dame Mahaut", "la boyaudière", "Des boyaux tendus sèchent sur des perches."),
	"brosserie":            ("Le vieux Colin", "le brossier", "Des touffes de soies attendent d'être montées."),
	"corderie":             ("Maître Erwan", "le cordier", "Le chanvre torsadé court sur toute la longueur de l'atelier."),
	"cordonnerie":          ("Maître Simon", "le cordonnier", "Des formes de bois s'alignent sous l'établi."),
	"cuisine":              ("Dame Perrine", "la cuisinière", "Un bouillon mijote sur le feu."),
	"fletcher":             ("Le vieux Thibaut", "le flèchier", "Des hampes bien droites sèchent en faisceaux."),
	"fumoir":               ("Maître Colin", "le fumeur", "Une fumée grasse pique les yeux."),
	"jardinier":            ("Dame Aveline", "la jardinière", "Des semis attendent en caissettes."),
	"laboratoire_d_alchimie": ("Maître Corvin", "l'alchimiste", "Un alambic siffle doucement dans la pénombre."),
	"lutherie":             ("Maître Anselme", "le luthier", "Un manche à peine dégrossi repose sur l'établi."),
	"maroquinerie":         ("Dame Ermeline", "la maroquinière", "Le cuir teint embaume la boutique."),
	"necromancie":          ("L'ombre de Vaudrec", "le nécromant", "Le froid s'accroche aux murs sans raison."),
	"plumasserie":          ("Dame Alaïs", "la plumassière", "Les plumes d'apparat frémissent au moindre courant d'air."),
	"salaison":             ("Maître Gontran", "le saleur", "Des baquets de saumure occupent tout le fond."),
	"savonnerie":           ("Dame Osanne", "la savonnière", "La soude et la graisse se disputent l'air."),
	"scriptorium":          ("Frère Anselin", "le copiste", "On n'entend que le grattement des calames."),
	"tabletterie":          ("Maître Ivon", "le tabletier", "L'os poli luit sous la lampe."),
	"tannerie":             ("Maître Rufin", "le tanneur", "L'odeur du tan prend à la gorge."),
	"taxidermie":           ("Maître Sylvain", "le taxidermiste", "Des regards de verre vous suivent depuis les étagères."),
	"tissage":              ("Dame Guillemette", "la tisserande", "Le métier à tisser bat une mesure obstinée."),
}

# Nœuds du service `transport` — mêmes ids pour tous les marchands (le router ne fait que
# les router, ils sont déclarés dans `services.transport.noeuds`).
NOEUDS_TRANSPORT = {
	"propose": "transport_propose",
	"infos": "transport_infos",
	"accepte": "transport_accepte",
	"trop_charge": "transport_trop_charge",
	"livre": "transport_livre",
	"livre_retour": "transport_livre_retour",
	"incomplet": "transport_incomplet",
}

# Décider = accepter ou refuser. On n'y remet PAS « Où est-ce ? » : le nœud d'information
# aurait reproposé la question à laquelle il vient de répondre.
CHOIX_DECIDER = [
	{"id": "transport_accepter", "label": "C'est entendu, je m'en charge.",
	 "action": {"service": "transport", "op": "accepter"}},
	{"id": "transport_refuser", "label": "Pas cette fois.", "next": "accueil"},
]
CHOIX_PRENDRE = [
	{"id": "transport_infos", "label": "Où est-ce, exactement ?", "next": "transport_infos"},
] + CHOIX_DECIDER


def dialogue(metier: str, ambiance: str) -> dict:
	return {
		"noeud_depart": "accueil",
		"noeuds": {
			"accueil": {
				"texte": f"{ambiance} « Bien le bonjour, {{prenom}}. Que puis-je pour vous ? »",
				"choix": [
					# Visibles seulement si le contexte le permet (flags posés par le router).
					{"id": "course", "label": "Vous auriez une course pour moi ?",
					 "next": "transport_propose", "condition": {"transport_offert": True}},
					{"id": "livraison", "label": "Je vous apporte une livraison.",
					 "action": {"service": "transport", "op": "livrer"},
					 "condition": {"transport_a_livrer": True}},
					{"id": "rien", "label": "Je ne faisais que passer.", "next": "fin"},
				],
			},
			# Les enseignes portent déjà leur article (« Le Saloir ») : on les amène toujours par
			# un deux-points ou une question, jamais par une préposition — « à Le Saloir » serait
			# fautif, et on ne peut pas contracter dans un gabarit.
			"transport_propose": {
				"texte": (
					"« Justement ! {colis} colis, {poids} kg. Destination : {destination}. "
					"Il me les faut là-bas dans les {delai} minutes — après, la marchandise ne vaut "
					"plus rien. {xp} points d'expérience et {prime} pièces de cuivre à votre retour, "
					"et vous grimperez dans mon estime. »"
				),
				"choix": CHOIX_PRENDRE,
			},
			"transport_infos": {
				"texte": (
					"« {destination} ? C'est {direction}. Vous ne pouvez pas la manquer. "
					"{delai} minutes, {prenom}, pas une de plus. »"
				),
				"choix": CHOIX_DECIDER,
			},
			"transport_accepte": {
				"texte": (
					"« Voilà la marchandise — {colis} colis, comptez-les. Destination : "
					"{destination}, dans les {delai} minutes. Ne me faites pas regretter. »"
				),
				"choix": [{"id": "ok", "label": "J'y vais de ce pas.", "next": "fin"}],
			},
			"transport_trop_charge": {
				"texte": (
					"« Vous ployez déjà sous votre barda, {prenom}. Délestez-vous et revenez : "
					"la marchandise ne s'envolera pas. »"
				),
				"choix": [{"id": "ok", "label": "Je reviendrai plus léger.", "next": "fin"}],
			},
			"transport_livre": {
				"texte": (
					"« Ah, enfin ! {colis} colis, le compte y est. Voici votre dû — {prime} pièces "
					"de cuivre. Je fais porter le mot à l'expéditeur : {expediteur} saura qu'on "
					"peut compter sur vous. »"
				),
				"choix": [{"id": "ok", "label": "Ce fut un plaisir.", "next": "fin"}],
			},
			# Course à RETOUR : le destinataire prend la marchandise mais ne paie pas — c'est le
			# donneur qui solde, une fois qu'on est allé lui en rendre compte. Le nœud `livre`
			# promettrait une prime que personne ne verse ici.
			"transport_livre_retour": {
				"texte": (
					"« {colis} colis, le compte y est. » Un reçu est griffonné, séché d'un souffle, "
					"et vous atterrit dans la main. « Je ne vous dois rien, l'ami : c'est {donneur} "
					"qui paie les siens. Rapportez-lui ce papier, il fait foi. »"
				),
				"choix": [{"id": "ok", "label": "J'y retourne de ce pas.", "next": "fin"}],
			},
			"transport_incomplet": {
				"texte": (
					"« Il manque des colis, {prenom}. Je ne signe rien tant que le compte n'y est "
					"pas — et le temps court toujours. »"
				),
				"choix": [{"id": "ok", "label": "Je vais arranger ça.", "next": "fin"}],
			},
		},
	}


def categories_marchandes() -> list:
	"""Catégories ayant des recettes — même source que `marche.besoins_categorie`."""
	exports = sorted(glob.glob(os.path.join(RACINE, "jsons", "recette-*.json")))
	if not exports:
		raise SystemExit("Aucun export `jsons/recette-*.json` — exporter le type `recette` depuis /admin.")
	brut = json.load(open(exports[-1], encoding="utf-8"))
	docs = brut["docs"] if isinstance(brut, dict) and "docs" in brut else brut
	return sorted({r.get("lieu_categorie") for r in docs if r.get("lieu_categorie")})


def main() -> None:
	docs = []
	for i, cat in enumerate(categories_marchandes()):
		nom, metier, ambiance = METIERS.get(
			cat, (f"Le tenancier", "le marchand", "La boutique sent le travail bien fait.")
		)
		# PAS de `description` : le doc est partagé par toutes les boutiques du métier, il ne
		# peut donc pas décrire le tenancier — une entrée `pnj` de lieu qui le renomme (ex.
		# Lucinda Mortecroix à La Flèche d'Argent) hériterait d'une description parlant de
		# quelqu'un d'autre. L'ambiance du métier vit dans le texte d'accueil du dialogue ;
		# une boutique qui veut sa propre description la pose sur son entrée `pnj`.
		docs.append({
			"_id": "pnj:marchand_" + cat,
			"type": "pnj",
			"nom": nom,
			"race": "humain",
			"vocation": "marchand",
			"portrait": PORTRAITS[i % len(PORTRAITS)],
			"services": {"transport": {"noeuds": dict(NOEUDS_TRANSPORT)}},
			"dialogue": dialogue(metier, ambiance),
		})
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
	print(f"{len(docs)} marchands écrits dans {SORTIE}")


if __name__ == "__main__":
	main()

"""Recettes à TROPHÉE : des pièces nommées faites d'un morceau de monstre que seul le client
apporte — le Casque cornu se commande au Grand Arsenal avec la tête du Minotaure qu'on a
abattu, jamais avec une tête achetée.

    python dev/gen_trophees.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/trophees_a_importer.json   (carte d'import de /admin)

Le TROPHÉE est une portion de carcasse qui existe déjà (`item:minotaure_tete`, posée par
dev/gen_carcasses_parties.py et rapportée par la découpe 🪓). La recette le cite par son id,
marqué `trophee: true` (`marche.est_recette_trophee`) : elle reste au catalogue de commande de
sa grande maison, sort du tick et des matières livrées, et la commande ne prend le trophée que
dans les sacs de l'expédition (`commande.sourcer`, `trophees`).

Chaque pièce part d'un SOCLE existant (mêmes slots, portée, tags, restriction…) auquel
s'ajoute l'APPORT du trophée. Le gain suit la dangerosité de l'espèce : le palier 1-5 de
dev/gen_fabrication_matieres.py (somme des attributs de base) fixe le budget de points de
l'apport — mesuré comme score(pièce) − score(socle) par `score_matiere` — et la rareté
minimale de la pièce.

⚠️ Garde-fous — rien n'est écrit si l'un d'eux échoue :
  · aucun `_id` déjà pris par un AUTRE doc ; un doc identique en base est sauté (idempotent) ;
  · le trophée est une portion de créature du dump (`portion_de`, `source_espece`) ;
  · la catégorie est une GRANDE MAISON présente dans le monde ;
  · tout intrant ordinaire est déjà acheté OU produit par la maison (fusion comprise) — elle
    l'a donc en réserve ou au rayon, la commande ne naît pas en attente pour lui ;
  · lot ajouté : les feuilles du monde sont INCHANGÉES (ni fausse feuille, ni trophée livré),
    le trophée n'est consommé par aucune recette de production, la recette sort du tick et
    la pièce entre au catalogue de commande de chaque maison de la catégorie ;
  · budget du palier, plafonds d'une matière (+10 dégâts, +6 par carac), `effets` bien
    dirigés selon la famille (débuffs sur une arme seulement).
"""

import argparse
import copy
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_recettes_orphelins import brancher_moteur, dernier_dump  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "trophees_a_importer.json")

# Dangerosité d'une espèce (somme des milieux de `base_attributes`) → palier. Bornes reprises
# de l'en-tête de la table de dev/gen_fabrication_matieres.py : basilic, cockatrice → 2 ;
# chimère, cerbère → 3 ; anges, archanges → 4 ; avatar, Bête de l'Apocalypse → 5.
SEUILS_PALIER = ((150, 1), (230, 2), (330, 3), (450, 4))
PALIER_MAX = 5

RARETES = ("commun", "peu_commun", "rare", "tres_rare", "legendaire")

# Champs du socle qui ne passent pas à la pièce : identité, prix et traçabilité.
CHAMPS_PROPRES = {"_id", "_rev", "type", "nom", "icon", "description", "rarete", "poids",
				  "valeur", "fabrication"}


# ── La table ────────────────────────────────────────────────────────────────────
# slug → {nom, icon, poids, description, socle, trophee, categorie, intrants, apport[, tags]}
# `tags` : ajoutés à ceux du socle (ex. `non_personnalisable`).
# `apport` : additif sur les `bonus_*` et `bonus`, fusion sur `effets` (buffs additionnés,
# `duree` au maximum), maximum sur `restriction`, additif sur `monture.charge_pct`.
PIECES = {
	# ── Armures ───────────────────────────────────────────────────────────────
	"Casque_cornu": {
		"nom": "Casque cornu", "icon": "🐂", "poids": 3.0,
		"description": "Le crâne d'un Minotaure, cornes comprises, évidé et doublé de cuir, "
					   "cerclé de fer à la nuque. On baisse la tête pour le porter, et l'on "
					   "garde l'habitude de foncer.",
		"socle": "item:Casque_de_cuir_bouilli", "trophee": "item:minotaure_tete",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 1)],
		"apport": {"bonus": {"F": 2}, "bonus_pv": 4},
	},
	"Cape_ailes_de_griffon": {
		"nom": "Cape-ailes de Griffon", "icon": "🪶", "poids": 2.5,
		"description": "Les rémiges d'une aile de griffon, montées à plat sur une doublure de "
					   "soie. Au moindre pas de côté, elle s'ouvre comme pour prendre le vent.",
		"socle": "item:Cape_de_plumes_noires", "trophee": "item:griffon_aile",
		"categorie": "grande_manufacture_textile", "intrants": [("soie", 2)],
		"apport": {"bonus": {"Ag": 3}, "effets": {"esquive": 2}, "bonus_initiative": 1},
	},
	"Pavois_de_tarasque": {
		"nom": "Pavois de Tarasque", "icon": "🛡️", "poids": [10, 16],
		"description": "Un pan de la carapace hérissée d'une tarasque, assis sur un châssis de "
					   "fer. On le plante en terre comme un pavois ordinaire ; les riverains du "
					   "Rhône jurent que rien de ce qui l'a frappé ne l'a jamais percé.",
		"socle": "item:Pavois", "trophee": "item:tarasque_corps_morceau",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 1)],
		"apport": {"bonus_pa": 4, "bonus_pv": 6},
	},
	"Pelisse_d_ulfhedinn": {
		"nom": "Pelisse d'ulfheðinn", "icon": "🐺", "poids": 4.0,
		"description": "La peau d'un loup géant portée à même le dos, la tête de la bête en "
					   "capuchon. Les chasseurs de Reykjavik et d'Akureyri s'en couvrent ainsi "
					   "depuis toujours — mais leurs loups faisaient moitié moins.",
		"socle": "item:Veste_cuir_souple", "trophee": "item:loup_geant_corps",
		"categorie": "grande_manufacture_du_cuir",
		"intrants": [("item:Sangle_de_cuir", 1), ("item:Boucle_de_fer", 1)],
		"apport": {"bonus": {"R": 2, "Vol": 2}},
	},
	# ── Armes ─────────────────────────────────────────────────────────────────
	"Glaive_croc_de_basilic": {
		"nom": "Glaive-croc de Basilic", "icon": "🐍", "poids": 3.0,
		"description": "Un croc de basilic emmanché au bout d'une hampe, à la place du fer. Le "
					   "regard de la bête n'y est plus, mais ce qu'il entaille se raidit encore.",
		"socle": "item:Glaive", "trophee": "item:basilic_tete",
		"categorie": "grand_arsenal", "intrants": [("hampe", 1), ("tendons", 1)],
		"apport": {"bonus_degats": 2, "effets": {"buffs": {"Ag": -2}, "duree": 2}},
	},
	"Fouet_dard_de_manticore": {
		"nom": "Fouet-dard de Manticore", "icon": "🦂", "poids": 2.0,
		"description": "La queue d'une manticore, tressée de cuir jusqu'au dard. Les vieux "
					   "récits de Perse disent que la bête lançait ses dards comme des flèches ; "
					   "celui-ci se contente de mordre, et le venin fait le reste.",
		"socle": "item:Fouet", "trophee": "item:manticore_queue",
		"categorie": "grande_manufacture_du_cuir", "intrants": [("cuir", 1), ("tendons", 1)],
		"apport": {"bonus_degats": 2, "effets": {"buffs": {"R": -3}, "duree": 3}},
	},
	"Masse_poing_de_troll": {
		"nom": "Masse-poing de Troll", "icon": "👊", "poids": 6.0,
		"description": "Un avant-bras de troll, poing fermé, durci au feu et ferré aux "
					   "phalanges. Les forgerons qui l'ont cerclé jurent qu'il serrait un peu "
					   "plus chaque matin.",
		"socle": "item:Kanabo", "trophee": "item:troll_bras",
		"categorie": "grand_arsenal", "intrants": [("fer", 2), ("cuir", 1)],
		"apport": {"bonus_degats": 4, "bonus_degats_dice": 2, "restriction": {"F": 28}},
	},
	"Lance_dent_de_wyvern": {
		"nom": "Lance-dent de Wyvern", "icon": "🔱", "poids": 2.5,
		"description": "Une griffe de wyverne ligaturée de tendons au bout d'une hampe. Faite "
					   "pour ce qui fond du ciel, elle se souvient encore du venin de sa bête.",
		"socle": "item:Lance", "trophee": "item:wyvern_patte",
		"categorie": "grand_arsenal", "intrants": [("hampe", 1), ("tendons", 1)],
		"apport": {"bonus_degats": 3, "bonus_cc": 2, "effets": {"buffs": {"R": -2}, "duree": 2}},
	},
	# ── Focus magiques ────────────────────────────────────────────────────────
	"Oeil_de_gorgone_serti": {
		"nom": "Œil de Gorgone serti", "icon": "👁️", "poids": 0.6,
		"description": "L'œil d'une gorgone, figé dans une monture de métal précieux. Il ne "
					   "pétrifie plus personne ; il fixe, et la volonté de qui le tient se "
					   "durcit à son contact.",
		"socle": "item:Orbe_arcanique", "trophee": "item:gorgone_tete",
		"categorie": "grande_orfevrerie", "intrants": [("metaux_precieux", 1)],
		"apport": {"bonus_pm": 4, "bonus": {"Vol": 2}, "effets": {"canalisation": 2},
				   "restriction": {"Vol": 25}},
	},
	"Corne_de_licorne": {
		"nom": "Corne de Licorne", "icon": "🦄", "poids": 1.2,
		"description": "La corne torse d'une licorne, baguée de métal précieux. Les "
					   "apothicaires en grattent la poudre contre les poisons ; entière, elle "
					   "fait couler le soin d'elle-même dans la main qui la porte.",
		"socle": "item:Orbe_arcanique", "trophee": "item:licorne_tete",
		"categorie": "grande_orfevrerie", "intrants": [("metaux_precieux", 1)],
		"apport": {"bonus_pm": 4, "bonus": {"Vol": 2}, "effets": {"regen_pv": 1},
				   "restriction": {"Vol": 25}},
	},
	"Remige_de_phenix": {
		"nom": "Rémige de Phénix", "icon": "🔥", "poids": 0.4,
		"description": "Une seule plume d'aile de grand phénix, emmanchée d'os. Elle reste "
					   "tiède, et nul ne sait si elle se consumera un jour pour renaître ailleurs.",
		"socle": "item:Orbe_arcanique", "trophee": "item:grand_phenix_aile",
		"categorie": "cabinet_des_specimens", "intrants": [("os", 1)],
		"apport": {"bonus_pm": 8, "bonus": {"Int": 2}, "effets": {"regen_pm": 2},
				   "restriction": {"Vol": 30}},
	},
	"Lanterne_de_cyclope": {
		"nom": "Lanterne de Cyclope", "icon": "🏮", "poids": 2.0,
		"description": "L'orbite unique d'un cyclope, évidée, garnie de cire et d'une mèche. "
					   "Certains récits disent que les cyclopes avaient troqué un œil contre la "
					   "vue de l'avenir ; à sa lueur, les lettres d'un grimoire se lisent plus vite.",
		"socle": "item:Orbe_arcanique", "trophee": "item:cyclope_tete",
		"categorie": "cabinet_des_specimens",
		"intrants": [("item:Cire_d_abeille", 2), ("item:Meche", 1)],
		"apport": {"bonus_pm": 2, "bonus": {"Int": 2}, "effets": {"canalisation": 1},
				   "restriction": {"Int": 20}},
	},
	# ── Bijou, consommable, instrument, harnachement ──────────────────────────
	"Collier_des_trois_crocs": {
		"nom": "Collier des trois crocs", "icon": "🦷", "poids": 0.3,
		"description": "Un croc de chacune des trois gueules d'un cerbère, enfilés sur un même "
					   "lacet serti de métal précieux. Trois têtes, une seule garde : qui le "
					   "porte dort d'un œil.",
		"socle": "item:Collier_de_crocs", "trophee": "item:cerbere_tete",
		"categorie": "grande_orfevrerie", "intrants": [("metaux_precieux", 1), ("cuir", 1)],
		"apport": {"bonus": {"Vol": 2}, "bonus_pv": 6, "bonus_initiative": 1},
	},
	"Elixir_de_sang_de_dragon": {
		"nom": "Élixir de sang de dragon", "icon": "🩸", "poids": 0.3,
		"description": "Sang de dragon rouge réduit au bain-marie, coupé d'herbes et de réactif "
					   "pour qu'il ne brûle pas la gorge. Sigurd s'y serait baigné tout entier ; "
					   "une gorgée suffit à tenir debout.",
		"socle": "item:elixir_revigorant", "trophee": "item:dragon_rouge_corps_morceau",
		"categorie": "grand_laboratoire_alchimique",
		"intrants": [("item:Herbes_medicinales", 2), ("reactif_brut", 1)],
		"apport": {"effets": {"pv": 20, "buffs": {"F": 6, "R": 4}, "duree": 6}},
		# Se commande tel quel : pas de variante sur mesure d'un élixir de trophée.
		"tags": ["non_personnalisable"],
	},
	"Olifant_de_mammouth": {
		"nom": "Olifant de Mammouth", "icon": "📯", "poids": 1.5,
		"description": "Une pointe de défense de mammouth, évidée et cerclée de bronze. Son "
					   "appel grave roule sur la plaine comme un troupeau en marche, et ceux "
					   "qu'il vise sentent faiblir leur résolution.",
		"socle": "item:Olifant", "trophee": "item:mammouth_tete_morceau",
		"categorie": "manufacture_des_instruments", "intrants": [("bronze", 1), ("cuir", 1)],
		"apport": {"bonus": {"Cha": 1}, "effets": {"buffs": {"Vol": -2}}},
	},
	"Bat_en_cuir_de_wyvern": {
		"nom": "Bât en cuir de Wyvern", "icon": "🐉", "poids": 4.5,
		"description": "Des panneaux taillés dans la membrane d'une aile de wyverne, tendus sur "
					   "des arcs et bouclés de fer. Plus léger qu'un bât de toile : la pluie "
					   "glisse dessus, et les griffes aussi.",
		"socle": "item:Bat_de_portage", "trophee": "item:wyvern_aile",
		"categorie": "grande_manufacture_du_cuir",
		"intrants": [("item:Sangle_de_cuir", 2), ("item:Boucle_de_fer", 2)],
		"apport": {"bonus_pa": 3, "bonus_pv": 6, "monture": {"charge_pct": 5}},
	},
}


# ── Construction (pur) ──────────────────────────────────────────────────────────

def palier_espece(espece_doc: dict) -> int:
	"""Palier 1-5 d'une espèce : somme des milieux de ses attributs de base (cf. SEUILS_PALIER)."""
	attrs = (espece_doc or {}).get("base_attributes") or {}
	total = sum((float(v.get("min", 0)) + float(v.get("max", 0))) / 2
				for v in attrs.values() if isinstance(v, dict))
	for seuil, palier in SEUILS_PALIER:
		if total <= seuil:
			return palier
	return PALIER_MAX


def appliquer_apport(socle: dict, apport: dict) -> dict:
	"""Les champs de jeu du socle, augmentés de l'apport du trophée (cf. table)."""
	doc = {k: copy.deepcopy(v) for k, v in socle.items() if k not in CHAMPS_PROPRES}
	for cle, val in apport.items():
		if cle == "bonus":
			bonus = doc.setdefault("bonus", {})
			for carac, n in val.items():
				bonus[carac] = bonus.get(carac, 0) + n
		elif cle == "effets":
			eff = doc.setdefault("effets", {})
			for k, n in val.items():
				if k == "buffs":
					buffs = eff.setdefault("buffs", {})
					for carac, d in n.items():
						buffs[carac] = buffs.get(carac, 0) + d
				elif k == "duree":
					eff["duree"] = max(eff.get("duree", 0), n)
				else:
					eff[k] = eff.get(k, 0) + n
		elif cle == "restriction":
			r = doc.setdefault("restriction", {})
			for carac, n in val.items():
				r[carac] = max(r.get(carac, 0), n)
		elif cle == "monture":
			m = doc.setdefault("monture", {})
			for k, n in val.items():
				m[k] = m.get(k, 0) + n
		else:
			doc[cle] = doc.get(cle, 0) + val
	return doc


def item_doc(slug: str, socle: dict, rarete_palier: str | None) -> dict:
	p = PIECES[slug]
	jeu = appliquer_apport(socle, p["apport"])
	rarete = max((socle.get("rarete") or "commun", rarete_palier or "commun"), key=RARETES.index)
	doc = {"_id": "item:" + slug, "type": "item", "nom": p["nom"], "icon": p["icon"],
		   "description": p["description"], "rarete": rarete,
		   "categorie": jeu.pop("categorie"), "sous_categorie": jeu.pop("sous_categorie", ""),
		   "slots": jeu.pop("slots"), "poids": p["poids"],
		   "tags": list(dict.fromkeys(jeu.pop("tags", []) + p.get("tags", [])))}
	doc.update(jeu)
	return doc


def recette_doc(slug: str) -> dict:
	"""Le trophée en tête, marqué `trophee: true` ; les intrants ordinaires ensuite."""
	p = PIECES[slug]
	return {
		"_id": "recette:%s_%s" % (p["categorie"], slug.lower()),
		"type": "recette",
		"lieu_categorie": p["categorie"],
		"objet_final": slug,
		"quantite_produite": 1,
		"matieres_premieres": [{"item": p["trophee"], "quantite": 1, "trophee": True}] + [
			({"item": cle} if cle.startswith("item:") else {"sous_categorie": cle}) | {"quantite": q}
			for cle, q in p["intrants"]
		],
	}


def tags_famille(doc: dict) -> list:
	"""Famille de la pièce au sens de dev/gen_fabrication_matieres.py (score et `effets`)."""
	import gen_fabrication_matieres as gfm
	return {"arme": [gfm.TAG_ARME], "consommable": [gfm.TAG_CONSOMMABLE],
			"catalyseur": [gfm.TAG_CATALYSEUR]}.get(doc.get("categorie"), [gfm.TAG_ARMURE])


def erreurs_de_budget(slug: str, socle: dict, doc: dict, palier: int) -> list:
	"""Apport hors du budget du palier, plafonds d'une matière, `effets` mal dirigés."""
	import gen_fabrication_matieres as gfm
	tags = tags_famille(doc)
	gain = gfm.score_matiere(doc, tags) - gfm.score_matiere(socle, tags)
	bas, haut = gfm.PALIERS[palier]["budget"]
	erreurs = []
	if not bas <= gain <= haut:
		erreurs.append("%s : apport %g hors du budget %d-%d du palier %d" % (slug, gain, bas, haut, palier))
	apport = PIECES[slug]["apport"]
	if gfm._num(apport.get("bonus_degats")) > gfm.PLAFOND_DEGATS:
		erreurs.append("%s : +%g dégâts > plafond %d" % (slug, apport["bonus_degats"], gfm.PLAFOND_DEGATS))
	for carac, v in (apport.get("bonus") or {}).items():
		if gfm._num(v) > gfm.PLAFOND_CARAC:
			erreurs.append("%s : %s +%g > plafond %d" % (slug, carac, v, gfm.PLAFOND_CARAC))
	entree = {"modificateurs": {"effets": doc.get("effets") or {}}, "tags": tags}
	erreurs += ["%s : %s" % (slug, e.split(" : ", 1)[1]) for e in gfm.effets_mal_diriges({slug: entree})]
	return erreurs


def valeur_piece(marche, commande, fabrication, socle: dict, matieres: list, facteur) -> list:
	"""`valeur` explicite de la pièce : celle d'une VARIANTE SUR MESURE de son socle façonnée
	avec le trophée et les intrants — même source unique (`commande.prix_variante` →
	`fabrication.valeur_variante`), facteur de `valeur` du palier de l'espèce.

	⚠️ Sans elle, le prix se propageait du POIDS de la portion (× rareté) : un œil de gorgone
	de 7 kg faisait une pièce à 220 cu, une tête de cerbère de 48 kg une pièce à 14 675 cu, à
	palier égal. Explicite, elle coupe aussi la propagation × MARGE_TRANSFO."""
	args = commande.prix_variante(socle, matieres)
	return fabrication.valeur_variante(facteur_valeur=facteur or 1.0, **args)


# ── Lancement ───────────────────────────────────────────────────────────────────

def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	args = ap.parse_args()
	chemin = args.dump or dernier_dump()
	print("source : %s" % os.path.relpath(chemin, RACINE))
	docs = [d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")]
	index = {d["_id"]: d for d in docs}

	marche = brancher_moteur(docs)
	import gen_fabrication_matieres as gfm
	from models import character_stats
	from utils import commande, fabrication

	erreurs, nouveaux, deja, lot = [], [], 0, []
	lieux = [d for d in docs if d["_id"].startswith("lieu:")]
	for slug in sorted(PIECES):
		p = PIECES[slug]
		socle, trophee = index.get(p["socle"]), index.get(p["trophee"])
		if not socle:
			erreurs.append("%s : socle %s absent du dump" % (slug, p["socle"]))
			continue
		if not trophee or not trophee.get("portion_de") or not trophee.get("source_espece"):
			erreurs.append("%s : %s n'est pas une portion de créature du dump" % (slug, p["trophee"]))
			continue
		palier = palier_espece(index.get(trophee["source_espece"]))
		doc = item_doc(slug, socle, gfm.PALIERS[palier]["rarete"])
		erreurs += erreurs_de_budget(slug, socle, doc, palier)
		if p["categorie"] not in character_stats.LIEU_CATEGORIES_FUSION:
			erreurs.append("%s : « %s » n'est pas une grande maison" % (slug, p["categorie"]))
		if not any(l.get("categorie") == p["categorie"] for l in lieux):
			erreurs.append("%s : aucun lieu de catégorie « %s »" % (slug, p["categorie"]))
		connus = set(marche.besoins_categorie(p["categorie"])) | marche.produits_categorie(p["categorie"])
		matieres = [(trophee, 1)]
		for cle, q in p["intrants"]:
			if cle not in connus and marche.matiere_item_id(cle) not in connus:
				erreurs.append("%s : %s n'est ni acheté ni produit par « %s »" % (slug, cle, p["categorie"]))
			intrant = index.get(marche.matiere_item_id(cle))
			if not intrant:
				erreurs.append("%s : intrant %s sans doc" % (slug, cle))
				continue
			matieres.append((intrant, q))
		doc["valeur"] = valeur_piece(marche, commande, fabrication, socle, matieres,
									 gfm.PALIERS[palier]["valeur"])
		lot.append((slug, palier, doc, recette_doc(slug)))

	for _slug, _palier, *paire in lot:
		for d in paire:
			existant = index.get(d["_id"])
			if existant is None:
				nouveaux.append(d)
			elif {k: v for k, v in existant.items() if k != "_rev"} == d:
				deja += 1
			else:
				erreurs.append("%s : _id déjà pris par un autre doc" % d["_id"])

	# ── Lot ajouté : le moteur doit le voir comme une recette de COMMANDE seule ──
	feuilles_avant = set(marche._get_marche_map()["feuilles"])
	docs.extend(d for d in nouveaux if d["_id"] not in index)
	marche.reset_prix_cache()
	mm = marche._get_marche_map()
	if mm["feuilles"] != feuilles_avant:
		erreurs.append("feuilles du monde modifiées : %s" % sorted(mm["feuilles"] ^ feuilles_avant))
	consommees = marche.cles_consommees()
	for slug, palier, doc, recette in lot:
		p = PIECES[slug]
		if p["trophee"] in consommees:
			erreurs.append("%s : %s consommé par une recette de production" % (slug, p["trophee"]))
		for l in (l for l in lieux if l.get("categorie") == p["categorie"]):
			if any(r["_id"] == recette["_id"] for r in marche.recettes_lieu(l)):
				erreurs.append("%s : cuit par le tick de %s" % (slug, l["_id"]))
			if doc["_id"] not in commande.catalogue_commandable(l):
				erreurs.append("%s : absent du catalogue de commande de %s" % (slug, l["_id"]))
			if (commande.recette_pour(l, doc["_id"]) or {}).get("_id") != recette["_id"]:
				erreurs.append("%s : %s ne retrouve pas la recette" % (slug, l["_id"]))
		print("  %-26s palier %d  %-11s trophée %-30s revient %6d cu (trophée %d cu)" % (
			slug, palier, doc["rarete"], p["trophee"], marche.cout_production_cuivre(doc["_id"]),
			marche.cout_production_cuivre(p["trophee"])))

	if erreurs:
		print("\n%d ERREUR(S) — rien n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("  ✗ " + e)
		sys.exit(1)
	print("%d doc(s) déjà en base ; %d à importer (%d items, %d recettes)" % (
		deja, len(nouveaux), sum(1 for d in nouveaux if d["type"] == "item"),
		sum(1 for d in nouveaux if d["type"] == "recette")))
	if not nouveaux:
		print("Base à jour — aucun fichier écrit.")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(nouveaux, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("→ %s" % os.path.relpath(SORTIE, RACINE))


if __name__ == "__main__":
	main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Peuple l'emplacement d'équipement **épaules**, resté vide dans tout le jeu.

Constat : la silhouette de la fiche affiche bien un emplacement « Epaules »
(`play_town_telluris.html`), mais **aucun des 676 items n'a `epaules` dans ses `slots`** —
l'emplacement n'a jamais rien eu à porter. (Le câblage serveur/client de la clé `epaules`
est une passe de CODE, à part : cf. `_VALID_SLOTS` et `SLOT_LABELS`.)

Écrit `jsons/epaulieres_a_importer.json` : 20 pièces d'épaules + leurs 20 recettes.

Trois règles héritées de `dev/gen_armures.py`, à ne pas défaire :

1. **`bonus_pa = round(poids × FACTEUR_PA[classe])`** — même barème que la passe armures,
   pour qu'une épaulière de plates et une cuirasse de plates se comparent honnêtement.
2. **Matières « feuilles » uniquement** (auto-approvisionnées par
   `marche.appro_leaves_categorie`) : `peaux`, `fer`, `acier`, `bronze`, `argent`, `poix`.
   ⚠️ Une recette qui exige du `cuir`, des `ligatures` ou des `tendons` — produits par une
   AUTRE recette, donc jamais auto-approvisionnés — ne se déclenche jamais : c'est le bug
   qui gelait les 11 recettes d'armure d'origine. Seules exceptions, assumées : les pièces
   dont l'os, la plume ou le poil EST le sujet, alimentées par le joueur comme `collier`,
   `talisman` et `parure` le sont déjà.
3. **Aucun `objet_final` qui soit déjà une matière** : les 20 slugs sont neufs, donc aucune
   feuille existante ne sort de l'auto-appro.

`objet_final` == le slug de l'`_id` (`marche.objet_final_item_id` → `item:<slug>`) : les
deux doivent rester rigoureusement synchrones, sans quoi l'atelier produirait un item
fantôme. Le contrôle est fait ici, à la génération.

	python dev/gen_epaulieres.py
"""
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "epaulieres_a_importer.json")

# Barème d'armure — copie déclarée de `dev/gen_armures.py` (même échelle, mêmes classes).
FACTEUR_PA = {
	"plates": 2.1, "mailles": 2.1, "metal": 2.1,
	"cuir_renforce": 1.8, "cuir_souple": 1.4,
	"os": 1.5, "fourrure": 1.0, "tissu": 0.8, "apparat": 0.0,
}

# Matières autorisées : feuilles auto-approvisionnées + les exceptions « le butin EST le
# sujet de la pièce ». Toute clé hors de ces deux ensembles fait échouer la génération.
FEUILLES = {"peaux", "fer", "acier", "bronze", "argent", "plomb", "poix", "branche"}
BUTIN_JOUEUR = {"os", "plumes", "poils"}

# slug, nom, icon, rareté, classe, poids, lieu, matières, extras (champs de bonus), description
PIECES = [
	# ── Armurerie : métal, mailles, cuir renforcé ─────────────────────────────────
	("Epaulieres_de_plates", "Épaulières de plates", "🛡️", "peu_commun",
	 "plates", 4.0, "armurerie", [("acier", 3), ("fer", 1), ("peaux", 1)],
	 {"bonus_malus_depl": -1, "restriction": {"F": 24}},
	 "Deux plaques d'acier articulées qui couvrent l'épaule jusqu'au haut du bras. "
	 "Elles arrêtent une hache ; elles interdisent aussi de lever le bras bien haut."),

	("Epaulieres_acier_gravees", "Épaulières d'acier gravées", "⚜️", "rare",
	 "plates", 3.5, "armurerie", [("acier", 2), ("argent", 1), ("peaux", 1)],
	 {"bonus": {"Cha": 2}},
	 "Le graveur a couru l'argent en volutes sur l'acier. On les reconnaît de loin, "
	 "ce qui est tout l'objet de la dépense."),

	("Epaulieres_benies", "Épaulières bénies", "✨", "rare",
	 "plates", 3.0, "armurerie", [("acier", 2), ("argent", 2), ("peaux", 1)],
	 {"bonus_pm": 5},
	 "Bénies au temple avant d'être rivetées. L'argent y tient moins pour l'ornement "
	 "que pour ce qu'il repousse."),

	("Mantelet_de_mailles", "Mantelet de mailles", "⛓️", "commun",
	 "mailles", 3.0, "armurerie", [("fer", 3), ("peaux", 1)],
	 {"restriction": {"F": 18}},
	 "Une pèlerine de maille rivetée qui tombe sur les deux épaules. Lourde à porter "
	 "toute une journée, précieuse au premier coup de taille."),

	("Camail_de_mailles", "Camail de mailles", "⛓️", "commun",
	 "mailles", 2.5, "armurerie", [("fer", 2), ("peaux", 1)],
	 {},
	 "Court capuchon de maille couvrant la nuque et le haut des épaules, lacé sous "
	 "le heaume. Ce que le heaume laisse passer, il l'attrape."),

	("Epaulieres_de_fer", "Épaulières de fer", "🛡️", "commun",
	 "metal", 3.0, "armurerie", [("fer", 2), ("peaux", 1)],
	 {},
	 "Ouvrage de forge honnête, martelé sur le patron le plus courant de la ville. "
	 "Rien d'élégant, et rien à redire."),

	("Epaulieres_de_bronze", "Épaulières de bronze", "🟠", "commun",
	 "metal", 2.5, "armurerie", [("bronze", 2), ("peaux", 1)],
	 {},
	 "Vieille facture, d'un bronze qui verdit. Le métal est plus doux que le fer : "
	 "il encaisse en se déformant plutôt qu'en cassant."),

	("Rondelles_d_epaule", "Rondelles d'épaule", "💠", "commun",
	 "metal", 1.0, "armurerie", [("fer", 1), ("peaux", 1)],
	 {},
	 "Deux disques de fer lacés à l'emmanchure, juste devant le creux de l'aisselle — "
	 "le seul endroit qu'une pointe cherche vraiment."),

	("Epaulieres_cuir_cloutees", "Épaulières de cuir cloutées", "🟤", "commun",
	 "cuir_renforce", 2.0, "armurerie", [("peaux", 2), ("fer", 1)],
	 {},
	 "Cuir épais semé de clous à large tête. Le compromis du soudard : on la porte "
	 "tout le jour et elle mord quand même la lame."),

	("Epaulieres_cuir_bouilli", "Épaulières de cuir bouilli", "🟫", "peu_commun",
	 "cuir_renforce", 1.8, "armurerie", [("peaux", 2), ("poix", 1)],
	 {},
	 "Cuir trempé bouillant puis moulé sur la forme, dur comme une écaille. "
	 "Il craint la flamme autant qu'il protège du tranchant."),

	# ── Maroquinerie : sangles, pèlerines, fourrures ──────────────────────────────
	("Baudrier_de_cuir", "Baudrier de cuir", "🪢", "commun",
	 "cuir_souple", 0.6, "maroquinerie", [("peaux", 1)],
	 {"bonus_initiative": 2},
	 "Sangle passée d'une épaule à la hanche opposée. Ce qu'elle porte tombe dans la "
	 "main sans qu'on ait à le chercher."),

	("Bandouliere_a_fioles", "Bandoulière à fioles", "🧪", "peu_commun",
	 "cuir_souple", 0.5, "maroquinerie", [("peaux", 1), ("poix", 1)],
	 {"bonus_pm": 3},
	 "Une rangée de gaines cousues au poitrail, chacune à la taille d'un flacon. "
	 "L'alchimiste y compte ses doses sans baisser les yeux."),

	("Pelerine_de_cuir", "Pèlerine de cuir", "🧥", "commun",
	 "cuir_souple", 1.2, "maroquinerie", [("peaux", 2)],
	 {},
	 "Courte cape de peau souple qui couvre les épaules et le haut du dos. "
	 "Elle prend la pluie pour vous."),

	("Mantelet_de_chasse", "Mantelet de chasse", "🏹", "peu_commun",
	 "cuir_souple", 1.0, "maroquinerie", [("peaux", 2)],
	 {"bonus_cd": 2},
	 "Coupé court à droite pour dégager la corde. Un archer reconnaît le vêtement "
	 "avant de reconnaître celui qui le porte."),

	("Manteau_de_loup", "Manteau de loup", "🐺", "peu_commun",
	 "fourrure", 2.5, "maroquinerie", [("peaux", 3)],
	 {"bonus": {"R": 2}},
	 "La dépouille entière jetée sur les épaules, la tête retombant sur la poitrine. "
	 "On dort dedans, et on tient le froid des routes du nord."),

	("Etole_de_fourrure", "Étole de fourrure", "🧣", "peu_commun",
	 "fourrure", 1.0, "maroquinerie", [("peaux", 2)],
	 {"bonus": {"Cha": 2}},
	 "Bande de fourrure lustrée portée en travers des épaules. Elle ne protège de "
	 "rien qu'on puisse craindre en combat, et de tout ce qui se juge en salle."),

	# ── Tabletterie : l'os EST le sujet (alimentée par le joueur) ─────────────────
	("Epaulieres_d_os", "Épaulières d'os", "🦴", "commun",
	 "os", 1.5, "tabletterie", [("os", 2), ("peaux", 1)],
	 {},
	 "Plaques d'os poli lacées côte à côte comme des écailles. Léger, bruyant, et "
	 "assez laid pour qu'on hésite à s'approcher."),

	("Harnais_d_ossements", "Harnais d'ossements", "☠️", "peu_commun",
	 "os", 2.0, "tabletterie", [("os", 3), ("peaux", 1)],
	 {"bonus": {"Cha": -1, "Vol": 2}},
	 "Une cage d'os montée sur sangles, qui monte des épaules jusqu'à la nuque. "
	 "Ceux qui la portent ont cessé de se soucier de l'accueil qu'on leur fait."),

	# ── Plumasserie : parade (aucune protection, tout le prestige) ────────────────
	("Mantelet_de_plumes", "Mantelet de plumes", "🪶", "peu_commun",
	 "apparat", 0.6, "plumasserie", [("plumes", 5)],
	 {"bonus": {"Cha": 3}},
	 "Des centaines de plumes cousues en rangs serrés, montées en courtes ailes sur "
	 "les épaules. Un ouvrage de mois, qu'une averse suffit à ruiner."),

	("Cape_de_plumes_noires", "Cape de plumes noires", "🌑", "rare",
	 "apparat", 0.5, "plumasserie", [("plumes", 4), ("peaux", 1)],
	 {"bonus": {"Ag": 1}, "bonus_initiative": 2},
	 "Plumes de corneille montées à plat, sans un reflet. Elle ne pèse rien et "
	 "avale le peu de lumière qui aurait pu vous trahir."),

	# ── Tissage : le feutre part des `poils` du dépeçage ──────────────────────────
	("Mantelet_de_feutre", "Mantelet de feutre", "🧵", "commun",
	 "tissu", 0.8, "tissage", [("poils", 3)],
	 {},
	 "Feutre foulé épais, taillé en carré et fendu pour la tête. Le vêtement du "
	 "pauvre et du berger : il tient chaud même trempé."),
]


def main() -> int:
	docs, erreurs = [], []
	for (slug, nom, icon, rarete, classe, poids, lieu, matieres, extras, desc) in PIECES:
		if classe not in FACTEUR_PA:
			erreurs.append("%s : classe de matière inconnue %r" % (slug, classe))
			continue
		for (cle, _q) in matieres:
			if cle not in FEUILLES | BUTIN_JOUEUR:
				erreurs.append(
					"%s : matière %r n'est ni une feuille auto-approvisionnée ni du butin "
					"joueur — la recette ne se déclencherait jamais." % (slug, cle))

		facteur = FACTEUR_PA[classe]
		pa = round(poids * facteur)
		if facteur >= 1.0:
			pa = max(1, pa)

		item = {
			"_id": "item:" + slug,
			"type": "item",
			"nom": nom,
			"description": desc,
			"icon": icon,
			"rarete": rarete,
			"categorie": "armure",
			"sous_categorie": "",
			"slots": ["epaules"],
			"tags": [],
			"poids": poids,
		}
		if pa:
			item["bonus_pa"] = pa
		item.update(extras)
		docs.append(item)

		docs.append({
			"_id": "recette:epauliere_" + slug.lower(),
			"type": "recette",
			"lieu_categorie": lieu,
			"objet_final": slug,              # ⚠️ doit valoir `_id` sans le préfixe `item:`
			"quantite_produite": 1,
			"matieres_premieres": [
				{"sous_categorie": cle, "quantite": q} for (cle, q) in matieres
			],
		})

	# Garde-fou : `objet_final` → `item:<slug>` doit exister dans ce même fichier.
	ids = {d["_id"] for d in docs if d["type"] == "item"}
	for d in docs:
		if d["type"] == "recette" and "item:" + d["objet_final"] not in ids:
			erreurs.append("recette %s : objet_final sans item (%s)"
						   % (d["_id"], d["objet_final"]))

	if erreurs:
		print("Génération refusée :", file=sys.stderr)
		for e in erreurs:
			print("  x " + e, file=sys.stderr)
		return 1

	with open(SORTIE, "w", encoding="utf-8") as fh:
		json.dump(docs, fh, ensure_ascii=False, indent=2)

	pieces = [d for d in docs if d["type"] == "item"]
	recettes = {r["objet_final"]: r for d in docs for r in [d] if d["type"] == "recette"}
	print("→ %s" % os.path.relpath(SORTIE, RACINE))
	print("   %d pièces d'épaules + %d recettes" % (len(pieces), len(recettes)))
	for d in pieces:
		r = recettes[d["_id"][len("item:"):]]
		print("   %-26s %5.1f kg  PA %-3s  %-14s %s" % (
			d["_id"][len("item:"):], d["poids"], d.get("bonus_pa", "-"),
			r["lieu_categorie"],
			" + ".join("%s×%s" % (m["sous_categorie"], m["quantite"])
					   for m in r["matieres_premieres"])))
	return 0


if __name__ == "__main__":
	sys.exit(main())

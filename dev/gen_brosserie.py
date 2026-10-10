"""Brosserie : demi-produits (fûts, faisceaux, crin frisé, mèches d'archet), catalyseurs et
parures — et enfin un DÉBOUCHÉ pour la brosse et le pinceau qu'elle fabriquait déjà.

Avant ce lot, la brosserie cuisait 4 recettes (brosse, pinceau) dont les produits ne servaient
qu'au Nécessaire de toilette, sans effet. Ce lot :
  · donne à la brosserie quatre demi-produits et cinq pièces (trois catalyseurs d'entrée de
    gamme, un chasse-mouches d'apparat, un peigne) ;
  · fait consommer le PINCEAU par la bijouterie (miniature) et le cirier (chandelle), la
    BROSSE par la savonnerie (toilette de marchand — le Cha buffé décide de qui marchande) et
    le tissage (ratine) ;
  · fait consommer ses demi-produits par le tissage, la lutherie et la grande manufacture
    textile (recette croisée).

    python dev/gen_brosserie.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/brosserie_a_importer.json   (carte d'import de /admin)

Garde-fous : ceux de dev/gen_bourrellerie.py (`main` paramétré) — `_id` pris, intrant ou
produit sans doc, produit qui serait une feuille, catégorie absente, FAUSSE FEUILLE (contrôle
du flux par cité), grande maison non croisée, emplacements mal formés.

⚠️ Choix assumés :
  · la virole des pinceaux et du chasse-mouches est en `fer` (pas en grenaille précieuse :
    elle serait mise en vente au comptoir du brossier) ;
  · `crins` n'arrive à la brosserie que par le flux des boucheries, déjà disputé (corderie,
    cirier, lutherie, bourrellerie) : crin frisé et mèches d'archet resteront rares.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_bourrellerie as base  # noqa: E402
from gen_bourrellerie import _composant, _piece  # noqa: E402

SORTIE = os.path.join(base.RACINE, "jsons", "brosserie_a_importer.json")


def _catalyseur(nom, icon, poids, description, rarete="commun", **bonus):
	doc = _piece(nom, icon, "main_gauche", poids, description, rarete, **bonus)
	doc["categorie"] = "catalyseur"
	return doc


def _consommable(nom, icon, poids, description, effets, rarete="commun"):
	return {"nom": nom, "icon": icon, "rarete": rarete, "categorie": "consommable",
			"slots": [], "poids": poids, "description": description, "effets": effets}


# ── Les items ─────────────────────────────────────────────────────────────────
# Repères (dump 10/10) : focus_magique PM +3 / Vol 35 ; epingle_cheveux Cha +1 ; savon Cha +5
# durée 10 ; Bougie_arcanique régén PM 3 + Int 5 ; Armure_matelassee PA 5 ; Rebec Cha 5,
# Vielle à roue Cha 6 ; Cornemuse : débuff ennemi 2 tours.
ITEMS = {
	# ── Demi-produits ─────────────────────────────────────────────────────────
	"Fut_de_brosse": _composant(
		"Fûts de brosse", "🪵", 0.1,
		"Montures de bois fendu, poncées et percées de rangées de trous où l'on noue les "
		"touffes. Le brossier en taille des paniers entiers."),
	"Faisceau_de_poils": _composant(
		"Faisceau de poils", "🖌️", 0.05,
		"Poils triés à la main, dégraissés, égalisés à la pointe et liés en botte serrée."),
	"Crin_frise": _composant(
		"Crin frisé", "🧶", 0.1,
		"Crin bouilli, tordu en corde puis détordu après séchage : il garde une frisure "
		"élastique qui ne se tasse jamais."),
	"Meche_d_archet": _composant(
		"Mèches d'archet", "🎻", 0.02,
		"Crins de queue choisis un à un, de même longueur et sans nœud, prêts à être tendus "
		"sur la baguette d'un archet."),
	# ── Pièces de la brosserie ────────────────────────────────────────────────
	"Pinceau_de_glyphes": _catalyseur(
		"Pinceau de glyphes", "🖌️", 0.1,
		"Un pinceau à pointe fine bagué de fer, dont on trace dans l'air les signes d'un sort "
		"avant de le lancer. La main sûre gaspille moins.",
		bonus_pm=2, bonus={"Int": 1}, restriction={"Int": 20}),
	"Aspersoir_de_sauge": _catalyseur(
		"Aspersoir de sauge", "🌿", 0.3,
		"Un faisceau de poils lié à de la sauge séchée, que l'on trempe et secoue sur les "
		"plaies et les seuils. L'odeur seule apaise.",
		bonus_pm=1, effets={"regen_pv": 1}, restriction={"Vol": 20}),
	"Plumeau_d_augure": _catalyseur(
		"Plumeau d'augure", "🪶", 0.2,
		"Des pennes montées en éventail sur un fût passé à la résine. On y lit le vent, et l'on "
		"y fait passer ce que l'on ne retient plus.",
		rarete="peu_commun", bonus_pm=2, effets={"canalisation": 1}, restriction={"Vol": 25}),
	"Chasse_mouches_de_crin": _piece(
		"Chasse-mouches de crin", "🪄", "main_gauche", 0.3,
		"Une queue de crin frisé sur un manche d'os bagué de fer. Celui qui le tient ne "
		"chasse pas les mouches : il fait savoir qui commande.",
		rarete="peu_commun", bonus={"Cha": 3}),
	"Peigne_d_os": _piece(
		"Peigne d'os", "🪮", "tete", 0.05,
		"Un peigne taillé dans un os plat et poli, planté dans la chevelure une fois la "
		"coiffure faite.", bonus={"Cha": 2}),
	# ── Débouchés chez les autres métiers ─────────────────────────────────────
	"Miniature_peinte": _piece(
		"Miniature peinte", "🖼️", "cou", 0.1,
		"Un portrait grand comme l'ongle, peint au pinceau d'un seul poil et serti d'un "
		"cadre de métal. On le porte pour qu'on le regarde.",
		rarete="peu_commun", bonus_pm=1, bonus={"Cha": 2}),
	"Chandelle_de_glyphes": _consommable(
		"Chandelle de glyphes", "🕯️", 0.2,
		"Une chandelle dont la cire porte des signes peints au pinceau. Tant qu'elle brûle, "
		"l'esprit se ferme aux distractions.",
		{"duree": 8, "regen_pm": 2, "buffs": {"Vol": 3}}),
	"Toilette_de_marchand": _consommable(
		"Toilette de marchand", "🧼", 0.3,
		"Savon, brosse à habits et eau parfumée : une heure d'apprêt avant d'entrer chez qui "
		"l'on veut convaincre. Le marchand juge d'abord sur la mine.",
		{"duree": 20, "buffs": {"Cha": 8}}),
	"Manteau_de_ratine": _piece(
		"Manteau de ratine", "🧥", "epaules", 1.0,
		"Un drap de laine gratté à la brosse jusqu'à friser : le poil retient l'air et rejette "
		"la pluie.", bonus_pa=1, bonus={"R": 1}),
	"Jaque_de_crin": _piece(
		"Jaque de crin", "🦺", "torse", [3, 5],
		"Plusieurs épaisseurs de toile piquées sur un garnissage de crin frisé. Le crin ne se "
		"tasse pas : la jaque amortit encore au centième coup.",
		bonus_pa=6, bonus={"Ag": -2}),
	"Perruque_d_apparat": _piece(
		"Perruque d'apparat", "🎩", "tete", 0.3,
		"Une coiffe de crin frisé montée sur soie et rehaussée d'une parure de plumes. On la "
		"porte aux audiences, jamais sur la route.",
		rarete="peu_commun", bonus={"Cha": 4}),
	"Viole_d_archet": _piece(
		"Viole d'archet", "🎻", "main_droite", 2.5,
		"Une viole à six cordes jouée à l'archet. Sa plainte grave engourdit les membres de "
		"qui l'écoute de trop près.",
		rarete="peu_commun", sous_categorie="instrument", portee=1, deux_mains=True,
		bonus_degats_dice=2, bonus={"Cha": 6, "Vol": 1}, restriction={"Cha": 35},
		effets={"buffs": {"Ag": -3}, "duree": 2}, cible="ennemi"),
}
# Une viole se tient comme les autres instruments : arme `cac`, deux emplacements de main.
ITEMS["Viole_d_archet"].update(categorie="arme", slots=["main_droite", "main_gauche"], tags=["cac"])

# ── Les recettes ──────────────────────────────────────────────────────────────
RECETTES = {
	# Demi-produits
	"Fut_de_brosse":          ("brosserie", [("branche", 1)], 4),
	"Faisceau_de_poils":      ("brosserie", [("poils", 2)], 3),
	"Crin_frise":             ("brosserie", [("crins", 2)], 3),
	"Meche_d_archet":         ("brosserie", [("crins", 1)], 2),
	# Pièces de la brosserie
	"Pinceau_de_glyphes":     ("brosserie", [("item:Fut_de_brosse", 1), ("item:Faisceau_de_poils", 1), ("fer", 1)], 1),
	"Aspersoir_de_sauge":     ("brosserie", [("item:Fut_de_brosse", 1), ("item:Faisceau_de_poils", 2), ("item:Herbes_aromatiques", 2)], 1),
	"Plumeau_d_augure":       ("brosserie", [("item:Fut_de_brosse", 1), ("plumes", 3), ("poix", 1)], 1),
	"Chasse_mouches_de_crin": ("brosserie", [("item:Crin_frise", 2), ("ossements", 1), ("fer", 1)], 1),
	"Peigne_d_os":            ("brosserie", [("ossements", 1)], 2),
	# Débouchés : brosse et pinceau existants, demi-produits par le flux de cité
	"Miniature_peinte":       ("bijouterie", [("item:pinceau", 1), ("item:pigment", 1), ("metaux_precieux", 1)], 1),
	"Chandelle_de_glyphes":   ("atelier_de_cirier", [("item:Cire_d_abeille", 2), ("item:Meche", 1), ("item:pinceau", 1), ("item:pigment", 1)], 1),
	"Toilette_de_marchand":   ("savonnerie", [("item:savon", 1), ("item:brosse", 1), ("item:Herbes_aromatiques", 1)], 1),
	"Manteau_de_ratine":      ("tissage", [("laine_tissee", 3), ("item:brosse", 1)], 1),
	"Jaque_de_crin":          ("tissage", [("lin", 3), ("item:Crin_frise", 2)], 1),
	"Perruque_d_apparat":     ("grande_manufacture_textile", [("item:Crin_frise", 2), ("soie", 1), ("item:parure", 1)], 1),
	"Viole_d_archet":         ("lutherie", [("item:Table_d_harmonie", 3), ("item:cordes_d_instrument", 5), ("item:Meche_d_archet", 2), ("poix", 1)], 1),
}


def main():
	base.main(ITEMS, RECETTES, SORTIE)


if __name__ == "__main__":
	main()

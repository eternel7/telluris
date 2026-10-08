#!/usr/bin/env python
"""50 attaques magiques de compétence DEVENUES DES SORTS, en un seul fichier d'import.

    python dev/gen_sorts_migres.py [--dump jsons/telluris-dump-*.json] [--sortie …]

Sortie unique : jsons/migration_competences_sorts_a_importer.json, dans cet ordre :
  1. les compétences REMPLAÇANTES (contrôle / soutien, même `_id`) — reprises telles quelles
     de `gen_competences_1_10` (`remplace=`), qui reste leur source ;
  2. les 50 `sort:*` ;
  3. le grimoire UNIQUE et la recette de scriptorium de chacun (`utils/grimoires`).

POURQUOI. Les vocations à magie portaient des attaques en COMPÉTENCE (jet magique, dés
propres) qui doublonnaient les sorts de leur école sans grimoire ni composant. Les « frappes
pures » qui comblaient un trou de l'école (aucun sort offensif à ±1 niveau) passent en sort ;
leur `_id` de compétence est repris par un contrôle ou un soutien.

TABLE FIGÉE. `MIGRES` recopie l'attaque d'origine (dump du 08/10) : une fois les remplaçants
importés, la base ne la contient plus — la relire rendrait le générateur non rejouable.
Chaque sort garde ses effets, sa portée, sa zone, son incantation et son animation ; seuls
changent :
  · `cout_pm` × `PM_FACTEUR` : le composant consommé ajoute des dés gratuits ;
  · les composants — un catalyseur (constante) PUIS un consommé (dés), par école (`COMPOSANTS`).

GARDES — une violation arrête tout, rien n'est écrit : école connue, composants et
animations présents dans le dump, `normaliser_sort` + éligibilité au combat, aucun `_id`
pris par un doc DIFFÉRENT (déjà importé à l'identique ⇒ sauté), aucun nom de sort en double.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "migration_competences_sorts_a_importer.json")

import gen_competences_1_10 as lot_1_10  # noqa: E402
from utils import grimoires, sorts as S  # noqa: E402

# Le consommé ajoute 1D6 à 2D6 par lancement (~25 % des dés d'origine aux niveaux 3-10) :
# le sort coûte d'autant plus que l'attaque de compétence dont il vient.
PM_FACTEUR = 1.25

# (catalyseur, consommé) par école — les paires les plus employées par les sorts d'attaque
# déjà en base (relevé du dump du 08/10).
COMPOSANTS = {
	"Bataille": ("Cristal_canalisation", "poudre_alchimique"),
	"Démonologie": ("Sel_noir", "Sang_demon_seche"),
	"Illusoire": ("Plume_d_oie", "Poudre_de_miroir"),
	"Nature": ("Seve_de_chene", "Herbes_a_bruler"),
	"Nécromancie": ("os", "sang"),
	"Sainte": ("encens", "Eau_benite"),
	"Élémentaire": ("Cristal_canalisation", "Soufre"),
}


def bonus_composants(niveau: int) -> tuple:
	"""(catalyseur, consommé) : une constante contre des dés — le catalyseur pèse MOINS."""
	catalyseur = str(1 + niveau // 4)
	consomme = "1D6" if niveau <= 3 else ("1D8" if niveau <= 6 else "2D6")
	return catalyseur, consomme


# Attaques d'origine, recopiées du dump (cf. TABLE FIGÉE).
MIGRES = [
	{"competence": "competence:missile_guide", "magie": "Bataille", "nom": "Projectile savant", "icon": "🔮", "description": "Plus le mage est savant, plus le trait est lourd et plus il porte loin.", "niveau": 3, "cout_pm": 15, "portee": "4+{Int/15}", "effets": {"degats": "2D{Int/8}"}, "animation": "animation:capa_arcane"},
	{"competence": "competence:explosion_arcanique", "magie": "Bataille", "nom": "Explosion arcanique", "icon": "💥", "description": "Une sphère d'énergie éclate au milieu des ennemis.", "niveau": 4, "cout_pm": 18, "portee": 6, "effets": {"degats": "2D6+{Int/8}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "animation": "animation:capa_arcane"},
	{"competence": "competence:explosion_runique", "magie": "Bataille", "nom": "Explosion runique", "icon": "💥", "description": "Une rune gravée explose au milieu des ennemis.", "niveau": 5, "cout_pm": 21, "portee": 5, "effets": {"degats": "2D8+{F/10}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "animation": "animation:capa_explosion_feu"},
	{"competence": "competence:eclair_de_bataille", "magie": "Bataille", "nom": "Éclair de bataille", "icon": "⚡", "description": "La foudre des champs de bataille, maîtrisée.", "niveau": 5, "cout_pm": 21, "portee": 6, "effets": {"degats": "3D8+{Int/12}"}, "animation": "animation:capa_foudre"},
	{"competence": "competence:tourbillon_arcanique", "magie": "Bataille", "nom": "Tourbillon arcanique", "icon": "🌀", "description": "L'énergie tourbillonne autour de lui et frappe tout ce qu'elle touche.", "niveau": 6, "cout_pm": 25, "portee": 6, "effets": {"degats": "2D8+{Int/12}"}, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1}, "animation": "animation:capa_arcane"},
	{"competence": "competence:decharge", "magie": "Bataille", "nom": "Décharge", "icon": "⚡", "description": "Une décharge en éventail qui grille les premiers rangs.", "niveau": 7, "cout_pm": 29, "portee": 6, "effets": {"degats": "2D8+{Int/10}"}, "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "decalage": 1, "longueur": 3, "angle": 90}, "animation": "animation:capa_impact_etincelles", "animation_zone": "animation:capa_cone_decharge"},
	{"competence": "competence:lance_arcanique", "magie": "Bataille", "nom": "Lance arcanique", "icon": "🔱", "description": "Une lance de pure énergie qui transperce tout.", "niveau": 7, "cout_pm": 29, "portee": 6, "effets": {"degats": "3D10+{Int/8}"}, "animation": "animation:capa_arcane"},
	{"competence": "competence:bombardement", "magie": "Bataille", "nom": "Bombardement", "icon": "☄️", "description": "Une pluie de projectiles s'abat sur la zone.", "niveau": 8, "cout_pm": 33, "portee": 6, "effets": {"degats": "3D8+{Int/15}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_meteore"},
	{"competence": "competence:tempete_arcanique", "magie": "Bataille", "nom": "Tempête arcanique", "icon": "⛈️", "description": "Il rassemble l'énergie pendant de longs instants avant de la libérer.", "niveau": 9, "cout_pm": 48, "portee": 6, "effets": {"degats": "5D10+{Int/7}"}, "incantation": 3, "animation": "animation:capa_arcane"},
	{"competence": "competence:tempete_runique", "magie": "Bataille", "nom": "Tempête runique", "icon": "🌩️", "description": "Les runes s'embrasent et la foudre tombe sur les ennemis.", "niveau": 9, "cout_pm": 37, "portee": 5, "effets": {"degats": "3D8+{F/10}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_foudre"},
	{"competence": "competence:nova_arcanique", "magie": "Bataille", "nom": "Nova arcanique", "icon": "💥", "description": "Une explosion d'énergie pure tout autour de lui.", "niveau": 10, "cout_pm": 40, "portee": 6, "effets": {"degats": "3D8+{Int/10}"}, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 2}, "animation": "animation:capa_arcane"},
	{"competence": "competence:flamme_noire", "magie": "Démonologie", "nom": "Flamme noire", "icon": "🔥", "description": "Une flamme infernale retournée contre ses semblables.", "niveau": 3, "cout_pm": 15, "portee": 5, "effets": {"degats": "2D8+{Vol/12}"}, "animation": "animation:capa_projectile_infernal"},
	{"competence": "competence:pluie_de_soufre", "magie": "Démonologie", "nom": "Pluie de soufre", "icon": "🌋", "description": "Une pluie de soufre ardent sur les ennemis.", "niveau": 3, "cout_pm": 15, "portee": 6, "effets": {"degats": "2D6+{Int/12}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "animation": "animation:capa_soufre"},
	{"competence": "competence:lance_de_l_enfer", "magie": "Démonologie", "nom": "Brasier du pacte", "icon": "🔥", "description": "Un feu d'en bas, que le démon fait payer en sang — moins cher à qui le tient en laisse.", "niveau": 4, "cout_pm": 18, "portee": 5, "effets": {"degats": "2D8+{Int/10}", "cout_pv": "6-{Vol/15}"}, "animation": "animation:capa_projectile_infernal"},
	{"competence": "competence:soufre", "magie": "Démonologie", "nom": "Soufre", "icon": "💨", "description": "Une bouffée de soufre qui suffoque tout le nid.", "niveau": 4, "cout_pm": 18, "portee": 5, "effets": {"degats": "2D6+{Vol/8}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "animation": "animation:capa_soufre"},
	{"competence": "competence:explosion_infernale", "magie": "Démonologie", "nom": "Explosion infernale", "icon": "💥", "description": "Une explosion de feu noir.", "niveau": 5, "cout_pm": 21, "portee": 6, "effets": {"degats": "2D6+{Int/10}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_explosion_feu"},
	{"competence": "competence:griffe_du_familier", "magie": "Démonologie", "nom": "Griffe du familier", "icon": "👹", "description": "Il ouvre à peine. Ce qui passe la main de l'autre côté fait le travail et repart.", "niveau": 6, "cout_pm": 25, "portee": 6, "effets": {"degats": "2D10+6", "drain_pv": 35}, "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "longueur": 2, "decalage": 1, "angle": 90}, "animation": "animation:capa_impact_plaie", "animation_zone": "animation:capa_cone_griffe"},
	{"competence": "competence:feu_de_l_ame", "magie": "Démonologie", "nom": "Feu de l'âme", "icon": "🔥", "description": "Un feu qui brûle l'âme de la cible.", "niveau": 7, "cout_pm": 29, "portee": 6, "effets": {"degats": "3D10+{Int/8}"}, "animation": "animation:capa_projectile_infernal"},
	{"competence": "competence:feu_de_l_enfer_retourne", "magie": "Démonologie", "nom": "Feu de l'enfer retourné", "icon": "🔥", "description": "Il retourne le feu des démons contre leur nid.", "niveau": 8, "cout_pm": 33, "portee": 5, "effets": {"degats": "3D8+{Vol/15}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_explosion_feu"},
	{"competence": "competence:pacte_de_sang_majeur", "magie": "Démonologie", "nom": "Pacte de sang majeur", "icon": "🩸", "description": "Un pacte majeur, payé au prix fort.", "niveau": 8, "cout_pm": 33, "portee": 6, "effets": {"degats": "4D10+{Int/6}", "cout_pv": 12}, "animation": "animation:capa_rage"},
	{"competence": "competence:rituel_d_exorcisme", "magie": "Démonologie", "nom": "Rituel d'exorcisme", "icon": "📿", "description": "Un rite lent, qui chasse ce qui ne devrait pas être là. Une volonté ferme en abrège les versets.", "niveau": 9, "cout_pm": 48, "portee": 5, "effets": {"degats": "5D10+{Vol/6}"}, "incantation": "5-{Vol/30}", "animation": "animation:capa_lumiere_zone"},
	{"competence": "competence:apocalypse", "magie": "Démonologie", "nom": "Apocalypse", "icon": "🌋", "description": "Le ciel s'ouvre et le feu infernal tombe.", "niveau": 10, "cout_pm": 40, "portee": 6, "effets": {"degats": "3D10+{Int/12}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_meteore"},
	{"competence": "competence:fleau_des_demons", "magie": "Démonologie", "nom": "Fléau des démons", "icon": "😈", "description": "La flamme qui a chassé les démons de trois provinces.", "niveau": 10, "cout_pm": 40, "portee": 5, "effets": {"degats": "5D10+{Vol/6}"}, "animation": "animation:capa_projectile_infernal"},
	{"competence": "competence:eventail_de_folie", "magie": "Illusoire", "nom": "Éventail de folie", "icon": "🌀", "description": "Une vague de démence qui déferle devant lui.", "niveau": 6, "cout_pm": 25, "portee": 6, "effets": {"degats": "2D6+{Int/10}"}, "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "decalage": 1, "longueur": 4, "angle": 90}, "animation": "animation:capa_impact_etincelles", "animation_zone": "animation:capa_cone_folie"},
	{"competence": "competence:lame_de_cauchemar", "magie": "Illusoire", "nom": "Lame de cauchemar", "icon": "🗡️", "description": "Une lame forgée dans les cauchemars de la cible.", "niveau": 7, "cout_pm": 29, "portee": 6, "effets": {"degats": "3D10+{Int/8}"}, "animation": "animation:capa_spectre"},
	{"competence": "competence:champ_de_ronces", "magie": "Nature", "nom": "Champ de ronces", "icon": "🌾", "description": "Le sol se couvre de ronces acérées sous les ennemis.", "niveau": 3, "cout_pm": 15, "portee": 6, "effets": {"degats": "2D6+{Vol/12}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "animation": "animation:capa_griffe"},
	{"competence": "competence:foudre_des_ancetres", "magie": "Nature", "nom": "Foudre des ancêtres", "icon": "⚡", "description": "Les ancêtres frappent du haut des nuages.", "niveau": 4, "cout_pm": 18, "portee": 6, "effets": {"degats": "2D8+{Vol/8}"}, "animation": "animation:capa_foudre"},
	{"competence": "competence:hurlement_de_la_meute", "magie": "Nature", "nom": "Hurlement de la meute", "icon": "🐺", "description": "Un hurlement qui fait trembler tout un groupe d'ennemis.", "niveau": 4, "cout_pm": 18, "portee": 6, "effets": {"degats": "2D6+{Vol/8}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "animation": "animation:capa_appel_sauvage"},
	{"competence": "competence:fouet_de_liane", "magie": "Nature", "nom": "Fouet de liane", "icon": "🌿", "description": "Une liane épaisse qui claque comme un fouet.", "niveau": 5, "cout_pm": 21, "portee": 6, "effets": {"degats": "3D8+{Vol/12}"}, "animation": "animation:capa_nature_buff"},
	{"competence": "competence:spores_etouffantes", "magie": "Nature", "nom": "Spores étouffantes", "icon": "🍄", "description": "Un nuage de spores qui s'abat sur les ennemis.", "niveau": 5, "cout_pm": 21, "portee": 6, "effets": {"degats": "2D6+{Vol/10}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_poison"},
	{"competence": "competence:colere_de_la_foret", "magie": "Nature", "nom": "Colère de la forêt", "icon": "🌲", "description": "Des branches fouettent le premier rang ennemi.", "niveau": 6, "cout_pm": 25, "portee": 6, "effets": {"degats": "3D6+{Vol/8}"}, "zone": {"forme": "rectangle", "origine": "lanceur", "orientation": "cible", "decalage": 1, "longueur": 1, "largeur": 3}, "animation": "animation:capa_griffe"},
	{"competence": "competence:pieu_de_bois_vivant", "magie": "Nature", "nom": "Pieu de bois vivant", "icon": "🪵", "description": "Une souche jaillit du sol comme une lance.", "niveau": 7, "cout_pm": 29, "portee": 6, "effets": {"degats": "3D10+{Vol/8}"}, "animation": "animation:capa_roc"},
	{"competence": "competence:orage_ancestral", "magie": "Nature", "nom": "Orage ancestral", "icon": "⛈️", "description": "Les ancêtres déchaînent l'orage sur les ennemis.", "niveau": 8, "cout_pm": 33, "portee": 6, "effets": {"degats": "3D8+{Vol/15}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_foudre"},
	{"competence": "competence:marais", "magie": "Nature", "nom": "Marais", "icon": "🐸", "description": "Le sol devient un marais qui engloutit les ennemis.", "niveau": 9, "cout_pm": 37, "portee": 6, "effets": {"degats": "3D8+{Vol/10}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_eau"},
	{"competence": "competence:rituel_du_cycle", "magie": "Nature", "nom": "Rituel du cycle", "icon": "♻️", "description": "Un rituel lent qui retourne la cible à la terre.", "niveau": 9, "cout_pm": 48, "portee": 6, "effets": {"degats": "5D10+{Vol/7}"}, "incantation": 3, "animation": "animation:capa_nature_buff"},
	{"competence": "competence:colere_des_ancetres", "magie": "Nature", "nom": "Colère des ancêtres", "icon": "⚡", "description": "Les ancêtres frappent tout autour de lui.", "niveau": 10, "cout_pm": 40, "portee": 6, "effets": {"degats": "3D8+{Vol/10}"}, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 2}, "animation": "animation:capa_foudre"},
	{"competence": "competence:explosion_de_cadavre", "magie": "Nécromancie", "nom": "Explosion de cadavre", "icon": "💥", "description": "Un cadavre éclate au milieu des ennemis.", "niveau": 5, "cout_pm": 21, "portee": 6, "effets": {"degats": "2D6+{Int/10}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_explosion_feu"},
	{"competence": "competence:pacte_de_sang_noir", "magie": "Nécromancie", "nom": "Pacte de sang noir", "icon": "🩸", "description": "Il paie de son sang un sort de mort.", "niveau": 5, "cout_pm": 21, "portee": 6, "effets": {"degats": "3D8+{Int/6}", "cout_pv": 8}, "animation": "animation:capa_drain"},
	{"competence": "competence:nuee_de_spectres", "magie": "Nécromancie", "nom": "Nuée de spectres", "icon": "👻", "description": "Des spectres tourbillonnent autour de lui et frappent.", "niveau": 9, "cout_pm": 37, "portee": 6, "effets": {"degats": "3D8+{Int/15}"}, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 2}, "animation": "animation:capa_spectre"},
	{"competence": "competence:rituel_de_mort", "magie": "Nécromancie", "nom": "Rituel de mort", "icon": "⚰️", "description": "Un rituel long qui arrache la vie de la cible.", "niveau": 9, "cout_pm": 48, "portee": 6, "effets": {"degats": "5D10+{Int/7}"}, "incantation": 3, "animation": "animation:capa_tombeau"},
	{"competence": "competence:mot_de_mort", "magie": "Nécromancie", "nom": "Mot de mort", "icon": "💀", "description": "Un mot que seuls les morts connaissent.", "niveau": 10, "cout_pm": 40, "portee": 6, "effets": {"degats": "5D10+{Int/6}"}, "animation": "animation:capa_spectre"},
	{"competence": "competence:lumiere_de_l_aube", "magie": "Sainte", "nom": "Lumière de l'aube", "icon": "🌅", "description": "Une lumière aveuglante sur le groupe ennemi.", "niveau": 4, "cout_pm": 18, "portee": 6, "effets": {"degats": "2D6+{Vol/8}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "animation": "animation:capa_lumiere_zone"},
	{"competence": "competence:eclat_divin", "magie": "Sainte", "nom": "Éclat divin", "icon": "🌟", "description": "Un éclat de pure divinité.", "niveau": 4, "cout_pm": 18, "portee": 6, "effets": {"degats": "2D8+{Vol/8}"}, "animation": "animation:capa_lumiere"},
	{"competence": "competence:paume_de_lumiere", "magie": "Sainte", "nom": "Paume de lumière", "icon": "☀️", "description": "Une paume chargée d'énergie pure.", "niveau": 5, "cout_pm": 21, "portee": 4, "effets": {"degats": "3D8+{Ag/12}"}, "animation": "animation:capa_lumiere"},
	{"competence": "competence:colonne_de_lumiere", "magie": "Sainte", "nom": "Colonne de lumière", "icon": "☀️", "description": "Une colonne de lumière s'abat sur la cible.", "niveau": 6, "cout_pm": 25, "portee": 6, "effets": {"degats": "3D8+{Vol/8}"}, "animation": "animation:capa_lumiere_zone"},
	{"competence": "competence:chatiment_divin", "magie": "Sainte", "nom": "Châtiment divin", "icon": "⚡", "description": "Le ciel frappe le groupe ennemi.", "niveau": 7, "cout_pm": 29, "portee": 6, "effets": {"degats": "2D8+{Vol/10}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_lumiere_zone"},
	{"competence": "competence:colere_divine", "magie": "Sainte", "nom": "Colère divine", "icon": "⚡", "description": "La lumière tombe du ciel sur les ennemis rassemblés.", "niveau": 8, "cout_pm": 33, "portee": 5, "effets": {"degats": "3D8+{F/15}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_lumiere_zone"},
	{"competence": "competence:jugement_celeste", "magie": "Sainte", "nom": "Jugement céleste", "icon": "⚖️", "description": "Le ciel juge, et le ciel frappe.", "niveau": 8, "cout_pm": 33, "portee": 6, "effets": {"degats": "4D10+{Vol/10}"}, "animation": "animation:capa_lumiere"},
	{"competence": "competence:courroux_du_ciel", "magie": "Sainte", "nom": "Courroux du ciel", "icon": "⚡", "description": "La colère du ciel s'abat sur l'ennemi.", "niveau": 10, "cout_pm": 40, "portee": 6, "effets": {"degats": "3D10+{Vol/12}"}, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "animation": "animation:capa_lumiere_zone"},
	{"competence": "competence:fureur_elementaire", "magie": "Élémentaire", "nom": "Fureur élémentaire", "icon": "💥", "description": "Feu, glace, foudre et roc frappent ensemble la même cible.", "niveau": 10, "cout_pm": 52, "portee": 6, "effets": {"degats": "6D10+{Int/6}"}, "incantation": 3, "animation": "animation:capa_explosion_feu"},
]


def slug(nom: str) -> str:
	s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
	return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def sort_doc(m: dict) -> dict:
	cat, cons = COMPOSANTS[m["magie"]]
	b_cat, b_cons = bonus_composants(m["niveau"])
	doc = {
		"_id": "sort:" + slug(m["nom"]),
		"type": "sort",
		"nom": m["nom"],
		"icon": m["icon"],
		"description": m["description"],
		"magie": m["magie"],
		"niveau": m["niveau"],
		"cout_pm": round(m["cout_pm"] * PM_FACTEUR),
		"cible": "ennemi",
		"jet": "magique",
		"portee": m["portee"],
		"effets": m["effets"],
		# ⚠️ Catalyseur AVANT le consommé (règle de contenu des sorts).
		"composants": [{"item": "item:" + cat, "consomme": False, "bonus": {"degats": b_cat}},
					   {"item": "item:" + cons, "consomme": True, "bonus": {"degats": b_cons}}],
		"animation": m["animation"],
	}
	for cle in ("zone", "incantation", "animation_zone"):
		if m.get(cle):
			doc[cle] = m[cle]
	return doc


def deja_importe(genere: dict, existant: dict) -> bool:
	"""Même règle que gen_sorts_caracteristiques : chaque champ produit s'y retrouve."""
	return all((existant or {}).get(k) == v for k, v in genere.items())


def generer(base: dict) -> tuple:
	"""`(docs, erreurs)` — docs à importer, dans l'ordre compétences → sorts → grimoires."""
	erreurs = []
	ecoles = {str(v.get("magie")) for v in (base.get("rules:vocations") or {}).get("value") or []
			  if isinstance(v, dict) and v.get("magie")}
	noms_sorts = {str(d.get("nom", "")).lower(): i for i, d in base.items() if d.get("type") == "sort"}
	sorts, vus = [], set()
	for m in MIGRES:
		doc = sort_doc(m)
		sid = doc["_id"]
		if m["magie"] not in ecoles or m["magie"] not in COMPOSANTS:
			erreurs.append("%s : école inconnue %r" % (sid, m["magie"]))
		for c in doc["composants"]:
			if c["item"] not in base:
				erreurs.append("%s : composant absent du dump %s" % (sid, c["item"]))
		for cle in ("animation", "animation_zone"):
			if doc.get(cle) and doc[cle] not in base:
				erreurs.append("%s : %s absente du dump %s" % (sid, cle, doc[cle]))
		norm = S.normaliser_sort(doc)
		if norm is None or not S.capacite_utilisable_combat(norm):
			erreurs.append("%s : refusé par le moteur (normaliser_sort / combat)" % sid)
		if sid in vus:
			erreurs.append("%s : `_id` en double dans la table" % sid)
		vus.add(sid)
		autre = noms_sorts.get(doc["nom"].lower())
		if autre and autre != sid:
			erreurs.append("%s : nom déjà porté par %s" % (sid, autre))
		sorts.append(doc)

	docs = []
	# 1. Compétences remplaçantes : la sortie de gen_competences_1_10, source unique.
	_lot, comps, err_lot, _compte = lot_1_10.construire()
	erreurs.extend("gen_competences_1_10 : " + e for e in err_lot)
	docs.extend(comps)
	# 2. Sorts neufs (ou différents de la base).
	for doc in sorts:
		existant = base.get(doc["_id"])
		if existant is None:
			docs.append(doc)
		elif not deja_importe(doc, existant):
			erreurs.append("%s existe déjà et diffère — l'import (PUT complet) l'écraserait" % doc["_id"])
	# 3. Grimoires + recettes de NOS sorts seulement (base réduite, cf. gen_sorts_caracteristiques).
	reduite = {k: d for k, d in base.items() if d.get("type") == "recette" or grimoires.est_grimoire(d)}
	g_docs, _lignes, g_erreurs = grimoires.grimoires_manquants(reduite, sorts_en_plus=sorts)
	erreurs.extend(g_erreurs)
	docs.extend(g_docs)
	return docs, erreurs


def charger_dump(chemin=None) -> dict:
	if chemin:
		print("source : %s" % chemin)
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(f for f in os.listdir(DOSSIER_JSONS)
				   if f.startswith("telluris-dump-") and f.endswith(".json"))
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
	print("source : jsons/%s" % dumps[-1])
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	parser = argparse.ArgumentParser(description="Attaques de compétence devenues des sorts")
	parser.add_argument("--dump", help="dump à relire (défaut : le plus récent de jsons/)")
	parser.add_argument("--sortie", default=SORTIE, help="fichier écrit")
	args = parser.parse_args()

	dump = charger_dump(args.dump)
	base = {d["_id"]: d for d in dump["docs"] if isinstance(d, dict) and d.get("_id")}
	docs, erreurs = generer(base)
	if erreurs:
		print("\n⚠️ %d erreur(s) — RIEN n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("   " + e)
		sys.exit(1)
	if not docs:
		print("Tout est déjà en base. Aucun fichier écrit.")
		return
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	compte = lambda t: sum(1 for d in docs if d.get("type") == t)  # noqa: E731
	print("écrit %s : %d compétence(s), %d sort(s), %d grimoire(s), %d recette(s)" % (
		os.path.relpath(args.sortie, RACINE), compte("competence"), compte("sort"),
		compte("item"), compte("recette")))


if __name__ == "__main__":
	main()

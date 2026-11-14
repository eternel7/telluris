"""Magie et capacités propres des monstres — contenu (cf. utils/capacites_monstre.py,
utils/ia_monstre.py).

    python dev/gen_capacites_monstres.py [--dump jsons/telluris-dump-*.json]

Sortie UNIQUE : jsons/capacites_monstres_a_importer.json (carte d'import de /admin) :
  · les compétences innées `competence:monstre_*` (vocation `monstre`, jamais apprenables) ;
  · les `espece:*` RELUES dans le dump, où seuls `competences` et `tags` changent :
    compétences innées, tags de magie `magie_<école>_<niveau>[_<profil>]` et tags d'IA
    `ia_<type>[_<nombre>][_<profil>]` ajoutés (rien n'est retiré, l'ordre existant est gardé).

N'émet que le DELTA contre le dump (un doc identique est sauté) : relancer est idempotent.
Refuse tout le lot sur : une espèce absente, une compétence inconnue de la table, un
`_id` de compétence déjà pris par un doc d'une autre vocation, un profil cité par un tag
qui n'existe pas, un tag illisible, une compétence qui ne se normalise pas.
Prévient (sans refuser) quand une espèce n'a pas les PM d'une capacité qui en coûte.
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.capacites_monstre import VOCATION_MONSTRE, magies_de_tags  # noqa: E402
from utils.competences import normaliser_competence  # noqa: E402
from utils.ia_monstre import _lire_tag  # noqa: E402

DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "capacites_monstres_a_importer.json")

# Animations reprises de capacités de joueurs déjà réglées (à revoir dans /admin/animations).
FEU, FEU_CONE = "animation:capa_impact_brulure", "animation:capa_cone_souffle_feu"


def _cone(longueur):
	return {"forme": "cone", "origine": "lanceur", "orientation": "cible", "decalage": 1,
			"longueur": longueur, "angle": 90}


def _cercle(rayon):
	return {"forme": "cercle", "origine": "lanceur", "rayon": rayon}


def _active(nom, icon, description, cible, portee, jet, effets, recharge, cout_pm=0,
			zone=None, animation="", animation_zone=""):
	doc = {"nom": nom, "icon": icon, "description": description, "mode": "active",
		   "cible": cible, "portee": portee, "jet": jet, "cout_pm": cout_pm,
		   "recharge": recharge, "effets": effets}
	if zone:
		doc["zone"] = zone
	if animation:
		doc["animation"] = animation
	if animation_zone:
		doc["animation_zone"] = animation_zone
	return doc


def _passive(nom, icon, description, cible, effets):
	return {"nom": nom, "icon": icon, "description": description, "mode": "passive",
			"cible": cible, "cout_pm": 0, "effets": effets}


COMPETENCES = {
	"souffle_de_feu": _active(
		"Souffle ardent", "🔥",
		"Le feu monte de la gorge et balaie tout ce qui se tient devant la bête ; "
		"ce qu'il ne consume pas garde la brûlure.",
		"ennemi", 5, "magique", {"degats": "4D6+{Vol/10}", "regen_pv": -3, "duree": 2}, 3,
		zone=_cone(4), animation=FEU, animation_zone=FEU_CONE),
	"grand_souffle_de_feu": _active(
		"Grand souffle de feu", "🔥",
		"Un fleuve de flammes que seuls les plus anciens dragons savent tenir si longtemps.",
		"ennemi", 7, "magique", {"degats": "6D6+{Vol/8}", "regen_pv": -5, "duree": 2}, 4,
		zone=_cone(6), animation=FEU, animation_zone=FEU_CONE),
	"crachat_de_feu": _active(
		"Crachat de feu", "🔥",
		"Une gerbe brève, encore maladroite, mais qui brûle bel et bien.",
		"ennemi", 3, "magique", {"degats": "2D6"}, 3,
		zone=_cone(2), animation=FEU, animation_zone=FEU_CONE),
	"souffle_de_givre": _active(
		"Souffle de givre", "❄️",
		"Un vent blanc qui gèle la peau et raidit les jambes.",
		"ennemi", 6, "magique", {"degats": "4D6", "buffs": {"V": -2, "Ag": -10}, "duree": 2}, 3,
		zone=_cone(5), animation="animation:capa_givre", animation_zone="animation:capa_cone_decharge"),
	"souffle_empoisonne": _active(
		"Souffle empoisonné", "☠️",
		"Une haleine verte et lourde ; qui la respire la sent encore des heures après.",
		"ennemi", 5, "magique", {"degats": "3D6", "regen_pv": -4, "duree": 3}, 3,
		zone=_cone(4), animation="animation:capa_poison", animation_zone="animation:capa_cone_folie"),
	"souffle_de_la_tombe": _active(
		"Haleine de la tombe", "💀",
		"L'air des os : il glace le sang et vide l'esprit de sa force.",
		"ennemi", 5, "magique",
		{"degats": "3D6", "regen_pm": -3, "buffs": {"Vol": -10}, "duree": 2}, 3,
		zone=_cone(4), animation="animation:capa_tombeau", animation_zone="animation:capa_cone_folie"),
	"venin_faible": _passive(
		"Venin", "🕷️", "Sa morsure laisse un poison qui brûle quelques instants.",
		"ennemi", {"regen_pv": -2, "duree": 3}),
	"venin": _passive(
		"Venin puissant", "☠️",
		"Chaque coup qui porte injecte un poison qui affaiblit et ronge.",
		"ennemi", {"regen_pv": -4, "buffs": {"F": -5}, "duree": 3}),
	"dard_caudal": _active(
		"Dard caudal", "🦂",
		"La queue se cambre et décoche ses piquants à distance ; leur venin suit.",
		"ennemi", 4, "cd", {"degats": "2D8", "regen_pv": -5, "duree": 3}, 2,
		animation="animation:capa_poison"),
	"toile": _active(
		"Toile", "🕸️", "Un jet de soie collante qui entrave les jambes.",
		"ennemi", 3, "cd", {"buffs": {"V": -5, "Ag": -10}, "duree": 2}, 3,
		animation="animation:capa_lien"),
	"regard_petrifiant": _active(
		"Regard pétrifiant", "🗿",
		"Croiser ce regard fige les membres comme la pierre.",
		"ennemi", 5, "magique", {"buffs": {"V": -5, "Ag": -20}, "duree": 2}, 4,
		animation="animation:capa_roc"),
	"toucher_petrifiant": _active(
		"Toucher pétrifiant", "🗿", "Là où le bec touche, la chair se raidit en pierre.",
		"ennemi", 1, "cc", {"degats": "1D6", "buffs": {"V": -5, "Ag": -20}, "duree": 2}, 3,
		animation="animation:capa_roc"),
	"hurlement_terrifiant": _active(
		"Hurlement terrifiant", "😱",
		"Un cri qui fait trembler les mains et faiblir le cœur des plus braves.",
		"ennemi", 2, "magique", {"buffs": {"Vol": -15, "F": -5}, "duree": 3}, 4,
		zone=_cercle(2), animation="animation:capa_spectre"),
	"lamentation": _active(
		"Plainte funèbre", "👻", "Une plainte qui transperce les os de ceux qui l'entendent.",
		"ennemi", 3, "magique", {"degats": "3D6", "buffs": {"Vol": -10}, "duree": 2}, 4,
		cout_pm=5, zone=_cercle(3), animation="animation:capa_spectre"),
	"charme": _active(
		"Charme envoûtant", "💋", "Une voix, un regard : la volonté s'effrite et la magie se dérobe.",
		"ennemi", 4, "magique",
		{"degats_pm": "2D6", "buffs": {"Vol": -15, "Ag": -10}, "duree": 2}, 3,
		cout_pm=5, animation="animation:capa_illusion"),
	"morsure_vampirique": _active(
		"Morsure vampirique", "🩸", "Les crocs s'enfoncent ; le sang bu referme ses plaies.",
		"ennemi", 1, "cc", {"degats": "3D6", "drain_pv": 50}, 2,
		animation="animation:capa_drain"),
	"toucher_spectral": _active(
		"Toucher spectral", "👻",
		"Une main froide traverse l'armure et boit la force de l'esprit.",
		"ennemi", 1, "magique", {"degats_pm": "2D6", "buffs": {"Vol": -10}, "duree": 2}, 1,
		animation="animation:capa_spectre"),
	"etreinte": _active(
		"Étreinte", "🐍", "Les anneaux se referment et serrent jusqu'à couper le souffle.",
		"ennemi", 1, "cc", {"degats": "2D8", "buffs": {"V": -5}, "duree": 2}, 3,
		animation="animation:capa_lien"),
	"malediction_du_tombeau": _active(
		"Malédiction du tombeau", "⚱️",
		"Qui trouble le repos des morts emporte leur malchance avec lui.",
		"ennemi", 3, "magique", {"regen_pv": -3, "buffs": {"Ch": -20}, "duree": 4}, 5,
		cout_pm=5, animation="animation:capa_tombeau"),
	"embrasement": _active(
		"Embrasement", "🔥", "Le corps s'embrase et brûle tout ce qui l'approche.",
		"ennemi", 1, "magique", {"degats": "3D6", "regen_pv": -3, "duree": 2}, 3,
		zone=_cercle(1), animation="animation:capa_explosion_feu"),
	"hurlement_de_meute": _active(
		"Hurlement de meute", "🐺", "Un appel qui rassemble la meute et la jette en avant.",
		"soi", 1, "magique", {"buffs": {"F": 8, "Ag": 5}, "duree": 3}, 5,
		zone={"forme": "carre", "origine": "lanceur", "rayon": 3},
		animation="animation:capa_rage"),
	"regeneration": _passive(
		"Régénération", "💚", "Ses plaies se referment à vue d'œil.",
		"soi", {"regen_pv": "{R/10}"}),
}

# Espèce → compétences innées (suffixes de COMPETENCES).
ATTRIBUTION = {}
for _c, _especes in {
	"souffle_de_feu": ["dragon", "grand_dragon", "dragon_rouge", "zmey_gorynych", "balaur",
					   "tarasque", "chimere", "xiuhcoatl"],
	"grand_souffle_de_feu": ["dragon_empereur"],
	"crachat_de_feu": ["petit_dragon"],
	"souffle_de_givre": ["dragon_blanc", "polar_kraken"],
	"souffle_empoisonne": ["dragon_hydre"],
	"souffle_de_la_tombe": ["dragon_zombie"],
	"venin_faible": ["araignee", "serpent"],
	"venin": ["araignee_geante", "scorpion_geant", "mushhushshu", "wyvern", "nuee_de_scarabees",
			  "manticore"],
	"toile": ["araignee_geante"],
	"dard_caudal": ["manticore"],
	"regard_petrifiant": ["basilic", "gorgone"],
	"toucher_petrifiant": ["cockatrice"],
	"hurlement_terrifiant": ["bete_glatissante", "boukhnoun", "cu_sidhe", "cwn_annwn", "horreur"],
	"lamentation": ["banshee"],
	"charme": ["succube", "incube", "vouivre", "lamie", "aicha_kandicha", "sirene", "dearg_due"],
	"morsure_vampirique": ["vampire", "comte_vampire", "nosferatu", "strigoi", "penanggalan",
						   "dearg_due", "seigneur_du_sang", "chevalier_du_sang"],
	"toucher_spectral": ["spectre", "fantome", "revenant", "banshee"],
	"etreinte": ["serpent_geant", "kraken", "polar_kraken", "leviathan", "grootslang", "apep",
				 "illuyanka", "yamata_no_orochi"],
	"malediction_du_tombeau": ["momie", "roi_des_tombes"],
	"embrasement": ["phenix", "grand_phenix", "ifrit"],
	"hurlement_de_meute": ["loup_garou", "lycaon", "faoladh"],
	"regeneration": ["troll", "hydre", "dragon_hydre", "balaur", "zmey_gorynych"],
}.items():
	for _e in _especes:
		ATTRIBUTION.setdefault(_e, []).append(_c)

# Tags de magie (sorts tirés) — repères : apprenti 2 · mage 5 · héros mage 8 · seigneur mage 10.
MAGIE = {
	"liche": ["magie_necromancie_3", "magie_necromancie_5_mage", "magie_necromancie_8_heros_mage",
			  "magie_necromancie_10_seigneur_mage"],
	"roi_liche": ["magie_necromancie_10"],
	"vampire": ["magie_necromancie_2", "magie_necromancie_5_mage", "magie_necromancie_8_heros_mage"],
	"comte_vampire": ["magie_necromancie_4", "magie_illusoire_3", "magie_necromancie_8_heros_mage",
					  "magie_necromancie_10_seigneur_mage"],
	"nosferatu": ["magie_necromancie_6", "magie_necromancie_10_seigneur_mage"],
	"dearg_due": ["magie_necromancie_4", "magie_illusoire_3"],
	"lamie": ["magie_necromancie_3", "magie_illusoire_3"],
	"dragon_de_sang": ["magie_necromancie_3", "magie_bataille_4"],
	"gobelin_chamanique": ["magie_nature_1", "magie_nature_3_mage"],
	"dryade": ["magie_nature_4"],
	"oreade": ["magie_nature_4"],
	"nahual": ["magie_nature_3"],
	"gwyn_ap_nudd": ["magie_nature_8", "magie_necromancie_6"],
	"elementaux": ["magie_elementaire_4"],
	"genie": ["magie_elementaire_6"],
	"ifrit": ["magie_elementaire_6"],
	"jann": ["magie_elementaire_4"],
	"marid": ["magie_elementaire_8"],
	"naiade": ["magie_elementaire_3"],
	"nereide": ["magie_elementaire_3"],
	"oceanide": ["magie_elementaire_3"],
	"ondin": ["magie_elementaire_3"],
	"phenix": ["magie_elementaire_4"],
	"grand_phenix": ["magie_elementaire_8"],
	"xiuhcoatl": ["magie_elementaire_4"],
	"fee": ["magie_illusoire_2"],
	"leprechaun": ["magie_illusoire_3"],
	"familier": ["magie_illusoire_1"],
	"sirene": ["magie_illusoire_4"],
	"aicha_kandicha": ["magie_illusoire_4"],
	"silat": ["magie_illusoire_3"],
	"sphinx": ["magie_illusoire_6", "magie_sainte_4"],
	"ange_de_la_connaissance": ["magie_sainte_5"],
	"archange_du_savoir": ["magie_sainte_9"],
	"seraphin": ["magie_sainte_10"],
	"avatar": ["magie_sainte_10"],
	"demon_majeur_de_la_destinee": ["magie_demonologie_8", "magie_demonologie_10_seigneur_mage"],
	"prince_demon": ["magie_demonologie_9"],
	"succube": ["magie_demonologie_2"],
	"incube": ["magie_demonologie_2"],
}

# Tags d'IA.
IA = {}
for _tag, _especes in {
	"ia_hit_and_run": ["bete_du_gevaudan", "nasnas", "serpopard", "cath_palug", "harpie",
					   "chauve_souris_geante", "griffon", "hippogriffe", "aigle_geant", "rapaces",
					   "oiseaux_de_proies", "corneille_noire", "penanggalan"],
	"ia_artilleur": ["liche", "roi_liche", "sirene", "banshee", "aicha_kandicha", "fee",
					 "leprechaun", "jann", "genie", "marid", "ange_de_la_connaissance",
					 "archange_du_savoir", "sphinx"],
	"ia_meute": ["loup", "fauves", "cwn_annwn", "cu_sidhe", "lycaon", "faoladh", "goule",
				 "ghul_des_sables", "gobelin", "gobelin_des_marais", "rat_geant", "orc"],
	"ia_embuscade": ["araignee_geante", "grootslang", "vers_des_sables", "crocodile", "dobhar_chu",
					 "bunyip", "homme_arbre", "golem_de_chair", "golem_de_fer", "golem_de_pierre",
					 "gargouille", "cerbere", "ladon", "ammit", "fils_de_sobek"],
	"ia_embuscade_1": ["mimique"],
	"ia_protecteur": ["gobelin_chamanique", "dryade", "naiade", "familier"],
	"ia_predateur": ["loup", "fauves", "manticore", "bete_du_gevaudan", "boukhnoun", "vampire",
					 "comte_vampire", "nosferatu", "strigoi", "chauve_souris_geante"],
	"ia_fuyard_30": ["gobelin", "gobelin_des_marais"],
	"ia_fuyard_40": ["besien", "gnome", "araignee"],
	"ia_fuyard_50": ["leprechaun", "cerf", "lievre", "ecureuil", "petits_animaux_divers", "renard"],
	"ia_fuyard_20": ["rat_geant"],
	"ia_berserker": ["ulfhedinn", "demon_guerrier", "minotaure", "ours", "sanglier", "taureau",
					 "troll", "loup_garou", "bete_glatissante", "twrch_trwyth"],
	"ia_berserker_champion": ["orc"],
	"ia_berserker_seigneur": ["orc"],
	"ia_artilleur_mage": ["vampire", "comte_vampire", "nosferatu", "gwyn_ap_nudd",
						  "demon_majeur_de_la_destinee"],
	"ia_artilleur_heros_mage": ["vampire", "comte_vampire", "nosferatu", "gwyn_ap_nudd",
								"demon_majeur_de_la_destinee"],
	"ia_artilleur_seigneur_mage": ["vampire", "comte_vampire", "nosferatu", "gwyn_ap_nudd",
								   "demon_majeur_de_la_destinee"],
	"ia_artilleur_apprenti": ["gobelin_chamanique"],
}.items():
	for _e in _especes:
		IA.setdefault(_e, []).append(_tag)


def doc_competence(suffixe: str) -> dict:
	return {"_id": f"competence:monstre_{suffixe}", "type": "competence",
			"vocation": VOCATION_MONSTRE, "niveau": 0, **COMPETENCES[suffixe]}


def _sans_rev(doc):
	return {k: v for k, v in (doc or {}).items() if k != "_rev"}


def _pm_median(espece: dict) -> int:
	attrs = espece.get("base_attributes") or {}
	mid = lambda c: ((attrs.get(c) or {}).get("min", 0) + (attrs.get(c) or {}).get("max", 0)) // 2
	return mid("Vol") * 2 + mid("Int") * 2


def construire(docs: list) -> tuple:
	"""(docs à émettre, avertissements). Lève ValueError sur toute incohérence."""
	base = {d["_id"]: d for d in docs if d.get("_id")}
	profils = {i.split(":", 1)[1] for i in base if i.startswith("profil:")}
	erreurs, avertissements, sortie = [], [], []

	for suffixe in COMPETENCES:
		doc = doc_competence(suffixe)
		if normaliser_competence(doc) is None:
			erreurs.append(f"{doc['_id']} : ne se normalise pas")
			continue
		existant = base.get(doc["_id"])
		if existant and existant.get("vocation") != VOCATION_MONSTRE:
			erreurs.append(f"{doc['_id']} : déjà pris par un doc de vocation {existant.get('vocation')!r}")
			continue
		if _sans_rev(existant) != doc:
			sortie.append(doc)

	especes = sorted(set(ATTRIBUTION) | set(MAGIE) | set(IA))
	for e in especes:
		eid = f"espece:{e}"
		espece = base.get(eid)
		if not espece:
			erreurs.append(f"{eid} : absente du dump")
			continue
		for tag in MAGIE.get(e, []) + IA.get(e, []):
			if tag.startswith("magie_"):
				pour = tag.split("_", 3)[3] if tag.count("_") >= 3 else ""
				if not magies_de_tags([tag], f"profil:{pour}" if pour else None):
					erreurs.append(f"{eid} : tag illisible {tag!r}")
			else:
				lu = _lire_tag(tag)
				if not lu:
					erreurs.append(f"{eid} : tag illisible {tag!r}")
					continue
				pour = lu[2]
			if pour and pour not in profils:
				erreurs.append(f"{eid} : tag {tag!r} cite un profil absent")
		nouveau = dict(espece)
		comps = list(espece.get("competences") or [])
		for c in ATTRIBUTION.get(e, []):
			cid = f"competence:monstre_{c}"
			if cid not in comps:
				comps.append(cid)
			cout = COMPETENCES[c].get("cout_pm", 0)
			if cout and _pm_median(espece) < cout:
				avertissements.append(f"{eid} : {cout} PM pour {cid}, {_pm_median(espece)} PM au médian")
		tags = list(espece.get("tags") or [])
		for t in MAGIE.get(e, []) + IA.get(e, []):
			if t not in tags:
				tags.append(t)
		if comps:
			nouveau["competences"] = comps
		nouveau["tags"] = tags
		if nouveau != espece:
			sortie.append(_sans_rev(nouveau))

	if erreurs:
		raise ValueError("\n".join(erreurs))
	return sortie, avertissements


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("Aucun dump dans jsons/ : passer --dump.")
	return dumps[-1]


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--dump", default=None)
	args = parser.parse_args()
	chemin = args.dump or dernier_dump()
	with open(chemin, encoding="utf-8") as f:
		docs = json.load(f)["docs"]
	print(f"Dump : {os.path.basename(chemin)} ({len(docs)} docs)")
	try:
		sortie, avertissements = construire(docs)
	except ValueError as exc:
		print(f"❌ Lot refusé :\n{exc}")
		sys.exit(1)
	for a in avertissements:
		print(f"⚠ {a}")
	if not sortie:
		print("Rien à émettre : la base est à jour.")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
	nb_c = sum(1 for d in sortie if d["_id"].startswith("competence:"))
	print(f"✅ {SORTIE} : {nb_c} compétences, {len(sortie) - nb_c} espèces.")


if __name__ == "__main__":
	main()

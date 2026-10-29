"""Une maison de guilde des aventuriers pour chaque cité qui n'en a pas — UN fichier à importer
(CLAUDE.md §18).

Même chaîne que le Grand Relais des Frontières (Lutecia) et le Bastion de l'Yonne (Auxerre), même
forme que les docs du geste 🏛️ Guilde de l'éditeur (`_gdEtapes` / `_gdDocs`, admin_map_editor.html) :

	cité ──(case de la carte)── façade ── réception ── comptoir ── bureau du maître

- 4 lieux par cité : `lieu:<slug>_exterieur` (`guilde_aventurier_exterieur`), `_interieur`
  (`guilde_aventurier`), `_comptoir` (`guilde_aventurier_comptoir`), `_bureau_du_maitre`
  (`bureau_maitre_guilde`, SANS `sous_categorie`, cf. utils/recrutement.py § Maison de guilde).
- `relation_lieu` → comptoir sur la façade, la réception et le bureau (une seule cote par maison).
- Bureau gardé par le rang D de SA cité (`acces.conditions[rang_min]`), sans `gardien` : aucun PNJ
  n'est posé (demande de l'Auteur, 29/10/2026) — le comptoir reste muet tant qu'on n'y met personne.
- Pas de tag `recrutement` sur la réception : sa catégorie l'accorde (`recrutement.lieu_recrute`).
- 4 connexions : la cité → la façade (la case de la porte), puis façade ↔ réception ↔ comptoir ↔
  bureau, nœuds en [0, 0]. Le label d'un nœud est le bouton qui MÈNE à ce nœud.

Porte sur la carte de la cité : case praticable (`cells == 1`, aucun mur nav), dans une zone
joignable (`nav_allows`) où mène déjà une porte de la carte, ni sur ni à moins de 2 cases d'une autre porte ; la plus proche d'un point visé À L'ŒIL au cœur
de la cité (`VISEES`).
⚠️ Choix MÉCANIQUE : à revoir dans /admin/editor (🧾 JSON → 🎯 Repositionner).

Noms des guildes : proposés le 28/10/2026 (docs/lore/cites/20261029_maisons_de_guilde_des_cites.md),
images : docs/prompts_guildes.md → templates/resources/towns/guilde_<cité>_<maillon>.jpg.

REJOUABLE : un `_id` déjà au dump est signalé et n'est pas réécrit (PUT complet, §11).

Usage : python dev/gen_guildes_cites.py [--dump jsons/telluris-dump-….json]
Sortie : jsons/guildes_cites_a_importer.json
"""

import json
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from utils.lieux import nav_allows  # noqa: E402

SORTIE = os.path.join(ggi.DOSSIER_JSONS, "guildes_cites_a_importer.json")
TOWNS = os.path.join(ggi.RESSOURCES, "towns")

# cité → (nom de la guilde, slug des `_id`). Le slug suit l'article du nom, comme
# `le_grand_relais_des_frontieres`.
GUILDES = {
	"lieu:lyon": ("La Maison des Deux Fleuves", "la_maison_des_deux_fleuves"),
	"lieu:orleans": ("Le Relais de la Loire", "le_relais_de_la_loire"),
	"lieu:calais": ("Le Fanal du Détroit", "le_fanal_du_detroit"),
	"lieu:chartres": ("Le Relais de la Beauce", "le_relais_de_la_beauce"),
	"lieu:rhemi": ("Le Carrefour des Rèmes", "le_carrefour_des_remes"),
	"lieu:douvres": ("La Tour des Falaises", "la_tour_des_falaises"),
	"lieu:london": ("La Salle Ronde", "la_salle_ronde"),
	"lieu:camelot": ("La Halle des Brèches", "la_halle_des_breches"),
	"lieu:bruges": ("La Maison du Zwin", "la_maison_du_zwin"),
	"lieu:aix_la_chapelle": ("Le Relais Palatin", "le_relais_palatin"),
	"lieu:reykjavik": ("La Halle des Fumées", "la_halle_des_fumees"),
	"lieu:akureyri": ("Le Refuge du Fjord", "le_refuge_du_fjord"),
	"lieu:rome": ("La Maison des Sept Collines", "la_maison_des_sept_collines"),
	"lieu:alexandrie": ("Le Relais du Phare", "le_relais_du_phare"),
	"lieu:cairo": ("La Wakala du Nil", "la_wakala_du_nil"),
	"lieu:bucarest": ("Le Han de la Dâmbovița", "le_han_de_la_dambovita"),
	"lieu:pekin": ("La Maison des Neuf Portes", "la_maison_des_neuf_portes"),
	"lieu:tokyo": ("La Maison du Pont d'Edo", "la_maison_du_pont_d_edo"),
	"lieu:teotihuacan": ("La Maison de la Chaussée", "la_maison_de_la_chaussee"),
	"lieu:sydney": ("La Maison de la Grande Baie", "la_maison_de_la_grande_baie"),
	"lieu:melbourne": ("La Maison de la Yarra", "la_maison_de_la_yarra"),
	"lieu:atlantis": ("La Maison du Port Extérieur", "la_maison_du_port_exterieur"),
	"lieu:abou_simbel": ("La Maison des Deux Rives", "la_maison_des_deux_rives"),
}

RANG_BUREAU = "D"  # comme le Bastion et le Grand Relais
REFUS = ("Un employé de la Guilde barre l'escalier du fond d'un bras tranquille : "
		 "le bureau du maître de la Guilde n'est pas ouvert aux recrues.")
ECART_MIN = 2  # cases, entre la porte de la guilde et toute autre porte de la carte
# Point visé sur l'image de chaque cité, en fractions (x, y) de sa largeur et de sa hauteur :
# relevé À L'ŒIL au cœur des murs (une place, une grande rue). Aucun critère automatique ne
# tenait sur des cartes aussi différentes (campagne, montagnes, cadre, mer).
VISEES = {
	"lieu:lyon": (0.47, 0.62), "lieu:orleans": (0.42, 0.55), "lieu:calais": (0.58, 0.55),
	"lieu:chartres": (0.50, 0.55), "lieu:rhemi": (0.45, 0.60), "lieu:douvres": (0.35, 0.50),
	"lieu:london": (0.40, 0.42), "lieu:camelot": (0.55, 0.60), "lieu:bruges": (0.52, 0.42),
	"lieu:aix_la_chapelle": (0.55, 0.60), "lieu:reykjavik": (0.60, 0.55), "lieu:akureyri": (0.50, 0.60),
	"lieu:rome": (0.55, 0.45), "lieu:alexandrie": (0.45, 0.50), "lieu:cairo": (0.60, 0.55),
	"lieu:bucarest": (0.47, 0.60), "lieu:pekin": (0.50, 0.72), "lieu:tokyo": (0.50, 0.55),
	"lieu:teotihuacan": (0.47, 0.60), "lieu:sydney": (0.50, 0.50), "lieu:melbourne": (0.50, 0.47),
	"lieu:atlantis": (0.70, 0.70),
	"lieu:abou_simbel": (0.50, 0.55),  # ville extérieure, au bord du Nil (la ville souterraine n'est pas sur la carte)
}
PAS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]


def _libre(cells, x, y):
	return 0 <= y < len(cells) and 0 <= x < len(cells[y]) and cells[y][x] == 1


def zones(cite):
	"""Les zones joignables à pied (cells == 1, pas autorisés par nav), chacune un ensemble de cases."""
	cells, nav = cite["cells"], cite.get("nav") or {}
	vues, out = set(), []
	for y in range(len(cells)):
		for x in range(len(cells[y])):
			if (x, y) in vues or not _libre(cells, x, y):
				continue
			zone, file = {(x, y)}, deque([(x, y)])
			vues.add((x, y))
			while file:
				cx, cy = file.popleft()
				for dx, dy in PAS:
					nx, ny = cx + dx, cy + dy
					if (nx, ny) in vues or not _libre(cells, nx, ny) or not nav_allows(nav, cx, cy, dx, dy):
						continue
					vues.add((nx, ny))
					zone.add((nx, ny))
					file.append((nx, ny))
			out.append(zone)
	return out


def portes_de(cite_id, docs):
	return [tuple(n["pos"]) for c in docs if c.get("type") == "connection"
			for n in c.get("nodes") or [] if n.get("lieu") == cite_id and n.get("pos")]


def case_de_porte(cite, docs, vise):
	"""La case praticable la plus proche du point VISÉ (fractions de l'image, choisies à l'œil), ou None.

	Case libre de la grande zone, sans mur nav, ni sur ni à moins de `ECART_MIN` d'une autre porte,
	dans une zone où mène déjà une porte de la carte."""
	W, H = cite["dimensions"]["x"], cite["dimensions"]["y"]
	cible = (vise[0] * W, vise[1] * H)
	nav = cite.get("nav") or {}
	portes = portes_de(cite["_id"], docs)
	# Une cité à remparts a son dedans et son dehors en zones DISJOINTES (la porte de rempart est
	# une connexion, pas un pas) : on garde toute zone où mène déjà une porte de la carte, sinon
	# la plus grande.
	toutes = zones(cite)
	desservies = set().union(*[z for z in toutes if any(p in z for p in portes)]) if portes else set()
	ouvertes = desservies or max(toutes, key=len, default=set())
	candidates = [
		(x, y) for (x, y) in ouvertes
		if f"{x},{y}" not in nav
		and all(max(abs(x - px), abs(y - py)) >= ECART_MIN for px, py in portes)
	]
	if not candidates:
		return None
	return min(candidates, key=lambda c: ((c[0] + .5 - cible[0]) ** 2 + (c[1] + .5 - cible[1]) ** 2, c[1], c[0]))


def docs_guilde(cite, nom, slug, porte):
	cite_id = cite["_id"]
	cs = cite_id.split(":", 1)[1]
	ids = {k: f"lieu:{slug}{suf}" for k, suf in
		   (("facade", "_exterieur"), ("reception", "_interieur"),
			("comptoir", "_comptoir"), ("bureau", "_bureau_du_maitre"))}
	img = {k: f"guilde_{cs}_{v}.jpg" for k, v in
		   (("facade", "exterieur"), ("reception", "reception"), ("comptoir", "comptoir"), ("bureau", "bureau"))}
	lieux = [
		{"_id": ids["facade"], "type": "lieu", "label": nom, "image": img["facade"],
		 "categorie": "guilde_aventurier_exterieur", "lieu_parent": cite_id,
		 "relation_lieu": ids["comptoir"]},
		{"_id": ids["reception"], "type": "lieu", "label": f"{nom} - réception", "image": img["reception"],
		 "categorie": "guilde_aventurier", "sous_categorie": "guilde_aventurier", "lieu_parent": cite_id,
		 "relation_lieu": ids["comptoir"]},
		{"_id": ids["comptoir"], "type": "lieu", "label": f"{nom} - comptoir", "image": img["comptoir"],
		 "categorie": "guilde_aventurier_comptoir", "sous_categorie": "guilde_aventurier",
		 "lieu_parent": cite_id},
		{"_id": ids["bureau"], "type": "lieu", "label": f"{nom} - bureau du maître", "image": img["bureau"],
		 "categorie": "bureau_maitre_guilde", "lieu_parent": cite_id, "relation_lieu": ids["comptoir"],
		 "acces": {"refus": REFUS, "cycle": 1,
				   "conditions": [{"rang_min": {"cite": cite_id, "rang": RANG_BUREAU}}]}},
	]

	def lien(_id, a, la, b, lb, typ="guilde_aventurier", pos_a=(0, 0)):
		na = {"lieu": a, "pos": list(pos_a)}
		if la:
			na["label"] = la
		nb = {"lieu": b, "pos": [0, 0]}
		if lb:
			nb["label"] = lb
		return {"_id": _id, "type": "connection", "nodes": [na, nb],
				"metadata": {"type": typ, "status": "ouvert"}}

	s = lambda i: i.split(":", 1)[1]  # noqa: E731
	liens = [
		lien(f"link:guilde_aventurier_exterieur01_to_{cs}", cite_id, "", ids["facade"], "",
			 typ="guilde_aventurier_exterieur", pos_a=porte),
		lien(f"link:{s(ids['reception'])}_to_{s(ids['facade'])}", ids["facade"], "sortir dans la rue",
			 ids["reception"], "Entrer dans la guilde"),
		lien(f"link:{s(ids['comptoir'])}_to_{s(ids['reception'])}", ids["reception"],
			 "retourner dans la salle commune", ids["comptoir"], "s'approcher du comptoir"),
		lien(f"link:{s(ids['bureau'])}_to_{s(ids['comptoir'])}", ids["comptoir"], "redescendre au comptoir",
			 ids["bureau"], "monter l'escalier du fond"),
	]
	return lieux, liens


def main(argv):
	dump = None
	if "--dump" in argv:
		dump = argv[argv.index("--dump") + 1]
	docs = ggi.charger_dump(dump)
	par_id = {d["_id"]: d for d in docs}
	sortie, ecartes = [], []
	for cite_id, (nom, slug) in GUILDES.items():
		cite = par_id.get(cite_id)
		if not cite or not cite.get("cells"):
			ecartes.append(f"{cite_id} : cité absente du dump ou sans grille")
			continue
		porte = case_de_porte(cite, docs, VISEES[cite_id])
		if not portes_de(cite_id, docs):
			ecartes.append(f"{cite_id} : AUCUNE connexion sur la carte — cité injoignable en jeu, guilde comprise")
		if porte is None:
			ecartes.append(f"{cite_id} : aucune case libre pour la porte")
			continue
		lieux, liens = docs_guilde(cite, nom, slug, porte)
		for d in lieux + liens:
			if d["_id"] in par_id:
				ecartes.append(f"{d['_id']} : déjà au dump, non réécrit")
				continue
			if d["type"] == "lieu" and not os.path.exists(os.path.join(TOWNS, d["image"])):
				ecartes.append(f"{d['_id']} : image absente {d['image']}")
			sortie.append(d)
		print(f"{cite_id:22} porte {porte}  « {nom} »")
	ids = [d["_id"] for d in sortie]
	assert len(ids) == len(set(ids)), "collision d'_id dans la sortie"
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	for e in ecartes:
		print("⚠️", e)
	print(f"{len(sortie)} docs → {os.path.relpath(SORTIE, ggi.RACINE)}")


if __name__ == "__main__":
	main(sys.argv[1:])

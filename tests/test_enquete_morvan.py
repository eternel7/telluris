"""La bête de Dun-les-Places — l'enquête du rang E (Borin → Dun-les-Places → la clairière → Borin).

Contenu pur (`dev/gen_enquete_morvan.py` → UN fichier d'import) : on verrouille ce qu'aucun
symptôme ne trahirait en jeu — une offre visible avant le rang E, une clairière qui ne
s'ouvre jamais ou se referme pour toujours sur une tête perdue (quête bloquée), une salle
sans loup-garou garanti, un charbonnier qui ne disparaît pas, une grille qui enferme le groupe."""

import glob
import json
import os

from dev import gen_enquete_morvan as gen
from utils import acces, apport, lint_dialogues, pnj

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
CONTENU = os.path.join(JSONS, "enquete_morvan_a_importer.json")

QUETE = "quete:la_bete_de_dun_les_places"
BORIN = "pnj:borin_barbe_de_jais"
VILLAGE = "lieu:dun_les_places"
CLAIRIERE = "lieu:clairiere_du_charbonnier"
DONJON = "donjon:clairiere_du_charbonnier"
TETE = "item:loup_garou_tete"
CHARBONNIER = "pnj:charbonnier_pierre_chaumereuil"
MENEUSE = "pnj:meneuse_de_loups_jacotte"

VILLAGEOIS = {  # pnj → (choix de l'enquête, branche après : "gardien" = sous `acces_libere`)
	MENEUSE: ({"loups"}, "gardien"),
	"pnj:bergere_margot_gueneau": ({"frere", "bete"}, "quete"),
	CHARBONNIER: ({"accuse", "bras", "nuits"}, None),  # disparu une fois la clairière gagnée
}


def _charger(chemin):
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def _docs():
	return {d["_id"]: d for d in _charger(CONTENU)}


def _dump():
	dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
	return {d["_id"]: d for d in _charger(dumps[-1])["docs"]}


def _collecte():
	"""La quête telle que `apport.accepter` la pose dans `quetes_actives`."""
	return {"id": QUETE, "objectif": {"type": "collect", "cible": TETE, "quantite": 1}}


def test_dialogues_sans_faute():
	rapport = lint_dialogues.analyser(list(_docs().values()))
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


def test_l_offre_de_borin_vise_la_tete_du_loup_garou():
	spec = apport.offre_spec(_docs()[BORIN])
	assert spec["id"] == QUETE and spec["item"] == TETE and spec["quantite"] == 1
	assert spec["unique"]
	# La tête est une PORTION de la carcasse que tout loup-garou abattu laisse au butin.
	base = _dump()
	assert base[TETE]["portion_de"] == "item:loup_garou"
	assert base["item:loup_garou"]["source_espece"] == "espece:loup_garou"
	assert any(p["item"] == TETE for p in base["item:loup_garou"]["decoupe"])


def test_l_offre_n_apparait_qu_au_rang_e():
	"""Le choix d'offre porte `rang_min {cite: auxerre, rang: E}` : invisible au rang F."""
	(choix,) = [c for c in _docs()[BORIN]["dialogue"]["noeuds"]["accueil"]["choix"]
				if c["id"] == "morvan_offre"]
	flags = {"apport_offert": True}
	ctx = lambda rangs: {"flags": flags, "rangs_guilde": rangs}
	assert not pnj.condition_ok(choix["condition"], ctx({}))
	assert not pnj.condition_ok(choix["condition"], ctx({"lieu:auxerre": "F"}))
	assert pnj.condition_ok(choix["condition"], ctx({"lieu:auxerre": "E"}))
	assert pnj.condition_ok(choix["condition"], ctx({"lieu:auxerre": "D"}))
	# Rang E dans une AUTRE cité : ne compte pas.
	assert not pnj.condition_ok(choix["condition"], ctx({"lieu:lutecia": "C"}))


def test_toute_quete_nommee_est_l_offre():
	neufs = [d for i, d in _docs().items() if i != BORIN]
	cites = {m for m in json.dumps(neufs, ensure_ascii=False).split('"') if m.startswith("quete:")}
	assert cites == {QUETE}


def test_borin_garde_ses_autres_services_et_choix():
	"""Le générateur RÉÉCRIT Borin en entier (PUT complet à l'import, CLAUDE.md §11) : appliqué
	au doc du dump courant, il ajoute sa quête sans rien retirer. On teste la TRANSFORMATION,
	pas le fichier figé : Borin peut évoluer en base sans casser ce test. Le service `apport`
	et les nœuds que le générateur possède sont les siens : il les réécrit, on ne les compare pas."""
	avant = _dump()[BORIN]
	apres = gen.borin(avant)
	for service, conf in avant.get("services", {}).items():
		if service != "apport":
			assert apres["services"][service] == conf, service
	for nid, noeud in avant["dialogue"]["noeuds"].items():
		if nid in gen.NOEUDS_BORIN:
			continue
		ids_avant = [c["id"] for c in noeud.get("choix", [])]
		ids_apres = [c["id"] for c in apres["dialogue"]["noeuds"][nid].get("choix", [])]
		assert [i for i in ids_apres if i in ids_avant] == ids_avant, nid
		# La sortie reste le dernier choix.
		if ids_avant:
			assert ids_apres[-1] == ids_avant[-1], nid


def test_conditions_de_presence_et_d_acces_lisibles():
	for doc in _docs().values():
		if doc.get("type") != "lieu":
			continue
		assert acces.conditions_invalides(doc) == [], doc["_id"]
		assert acces.conditions_pnj_invalides(doc) == [], doc["_id"]


def test_la_clairiere_s_ouvre_tant_que_la_tete_reste_a_rapporter():
	"""Fermée sans la quête ; ouverte quête en cours, MÊME après une victoire (une tête
	perdue au sol ne doit pas bloquer la quête) ; refermée la tête REMISE (`progress`)."""
	clairiere = _docs()[CLAIRIERE]
	sans = {"quetes_actives": [], "battle_maps_gagnees": [], "inventaire": []}
	assert not acces.acces_autorise(sans, clairiere, lambda _id: None)[0]
	pendant = {"quetes_actives": [_collecte()], "battle_maps_gagnees": [], "inventaire": []}
	assert acces.acces_autorise(pendant, clairiere, lambda _id: None)[0]
	tete_perdue = dict(pendant, battle_maps_gagnees=[CLAIRIERE])
	assert acces.acces_autorise(tete_perdue, clairiere, lambda _id: None)[0]
	remise = dict(tete_perdue, quetes_actives=[dict(_collecte(), progress=1)])
	assert not acces.acces_autorise(remise, clairiere, lambda _id: None)[0]


def test_le_charbonnier_disparait_une_fois_la_clairiere_gagnee():
	(entree,) = [e for e in _docs()[VILLAGE]["pnj"] if e["character"] == CHARBONNIER]
	assert entree["conditions"] == [{"combat_gagne": {"lieu": CLAIRIERE, "attendu": False}}]
	# Les deux autres restent après le combat (le doute se dit par eux).
	autres = [e for e in _docs()[VILLAGE]["pnj"] if e["character"] != CHARBONNIER]
	assert len(autres) == 2 and not any(e.get("conditions") for e in autres)


def test_la_clairiere_garantit_un_seul_loup_garou():
	"""Le moteur tire chaque monstre AU HASARD parmi les espèces de la salle : une seule
	espèce, sinon la tête pourrait manquer (Auteur, 14/10 : un seul loup-garou)."""
	docs = _docs()
	donjon = docs[DONJON]
	assert donjon["portail"] == VILLAGE
	(salle,) = donjon["battle_maps"]
	assert salle["lieu"] == CLAIRIERE and salle["especes"] == ["espece:loup_garou"]
	assert salle["nb_monstres"] == 1
	assert docs[MENEUSE]["services"]["acces"]["lieu"] == CLAIRIERE


def test_la_clairiere_est_une_salle_jouable():
	clairiere = _docs()[CLAIRIERE]
	cells = clairiere["cells"]
	w, h = clairiere["dimensions"]["x"], clairiere["dimensions"]["y"]
	assert len(cells) == h and all(len(r) == w for r in cells)
	ok = lambda x, y: 0 <= x < w and 0 <= y < h and cells[y][x] >= 1 and cells[y][x] != 3
	praticables = {(x, y) for y in range(h) for x in range(w) if ok(x, y)}
	depart = next(iter(sorted(praticables)))
	vues, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				n = (x + dx, y + dy)
				if n in praticables and n not in vues:
					vues.add(n)
					pile.append(n)
	assert vues == praticables


def test_dun_les_places_sur_une_case_libre_de_la_carte_de_france():
	docs = _docs()
	base = _dump()
	(noeud_france,) = [n for n in docs["link:dun_les_places_to_france"]["nodes"] if n["lieu"] == "lieu:france"]
	x, y = noeud_france["pos"]
	assert base["lieu:france"]["cells"][y][x] >= 1
	# Le lien lui-même est au dump une fois importé : seules les AUTRES connexions comptent.
	prises = {tuple(n["pos"]) for d in base.values()
			  if d.get("type") == "connection" and d.get("_id") != "link:dun_les_places_to_france"
			  for n in d.get("nodes", []) if n.get("lieu") == "lieu:france"}
	assert (x, y) not in prises


def test_images_presentes():
	docs = _docs()
	ressources = os.path.join(RACINE, "templates", "resources")
	chemins = [
		os.path.join(ressources, "battle_maps", docs[CLAIRIERE]["image"]),
		os.path.join(ressources, "towns", docs[VILLAGE]["image"]),
	]
	for e in docs[VILLAGE]["pnj"]:
		chemins.append(os.path.join(ressources, "pnj", e["portrait"]))
	for d in docs.values():
		if d.get("type") == "pnj" and d["_id"] != BORIN:
			chemins.append(os.path.join(ressources, "pnj", d["portrait"]))
	for p in chemins:
		assert os.path.exists(p), p


def test_la_grille_suit_le_quadrillage_de_la_carte():
	"""40 × 20 cases sur une image rognée à 1376×746 : 34,4 × 37,3 px par case, le
	quadrillage dessiné (cf. en-tête de la grille dans le générateur)."""
	from PIL import Image
	clairiere = _docs()[CLAIRIERE]
	chemin = os.path.join(RACINE, "templates", "resources", "battle_maps", clairiere["image"])
	assert Image.open(chemin).size == (1376, 746)
	assert clairiere["dimensions"] == {"x": 40, "y": 20}


def _accueil(pnj_id, actives=(), reussies=(), flags=None):
	"""Ids des choix visibles à l'accueil d'un villageois, selon l'état de la quête."""
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {}}
	return {c["id"] for c in pnj._choix_visibles(_docs()[pnj_id], "accueil", contexte)}


def test_les_villageois_ne_parlent_de_l_enquete_que_quete_en_cours():
	"""Avant : un bonjour et rien d'autre ; pendant : l'enquête ; après : ce qui a changé
	(Auteur, 15/10). Gardiens : la porte s'ouvre par `acces_ouvrable`, l'après par
	`acces_libere` (état du monde, tous deux posés par le router)."""
	for pnj_id, (enquete, apres) in VILLAGEOIS.items():
		assert _accueil(pnj_id) == {"bonjour", "fin"}, pnj_id
		pendant = _accueil(pnj_id, actives=[QUETE])
		assert enquete <= pendant and "bonjour" not in pendant and "apres" not in pendant, pnj_id
		flags = {"acces_libere": True} if apres == "gardien" else {}
		fini = _accueil(pnj_id, reussies=[QUETE], flags=flags)
		attendu = {"fin"} if apres is None else {"apres", "fin"}
		assert fini == attendu, pnj_id

"""Les morts d'Escolives — l'enquête du rang D (Gautier → Escolives → la crypte → Gautier).

Contenu pur (`dev/gen_enquete_escolives.py` → UN fichier d'import) : on verrouille ce qu'aucun
symptôme ne trahirait en jeu — une crypte qui ne s'ouvre jamais (barrière mal posée), une
salle sans Strigoï garanti (aucun ossement à rapporter : quête infaisable), une grille trouée
qui enferme le groupe, un id de quête mal recopié qui cache un choix pour toujours."""

import glob
import json
import os

from utils import acces, apport, lint_dialogues, pnj

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
CONTENU = os.path.join(JSONS, "enquete_escolives_a_importer.json")
RESSOURCES = os.path.join(RACINE, "templates", "resources")

QUETE = "quete:les_morts_d_escolives"
GAUTIER = "pnj:gautier_de_valcroix"
VILLAGE = "lieu:escolives"
CRYPTE = "lieu:crypte_de_la_necropole_d_escolives"
DONJON = "donjon:crypte_d_escolives"
OSSEMENTS = "item:strigoi"

VILLAGEOIS = {  # pnj → (choix de l'enquête, branche après : "gardien" = sous `acces_libere`)
	"pnj:fossoyeur_gaspard_fouquet": ({"tombes"}, "gardien"),
	"pnj:guerisseuse_ysolde_vernier": ({"morts"}, "quete"),
	"pnj:veuve_perrine_vaudin": ({"aubepine"}, "quete"),
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
	return {"id": QUETE, "objectif": {"type": "collect", "cible": OSSEMENTS, "quantite": 1}}


def test_dialogues_sans_faute():
	rapport = lint_dialogues.analyser(list(_docs().values()))
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


def test_l_offre_de_gautier_vise_les_ossements_du_strigoi():
	spec = apport.offre_spec(_docs()[GAUTIER])
	assert spec["id"] == QUETE and spec["item"] == OSSEMENTS and spec["quantite"] == 1
	assert spec["unique"]
	# Tout Strigoï abattu laisse sa carcasse `item:<slug>` au butin : l'objet existe en base
	# et c'est bien la dépouille du Strigoï.
	base = _dump()
	assert base[OSSEMENTS]["source_espece"] == "espece:strigoi"


def test_toute_quete_nommee_est_l_offre():
	texte = json.dumps(list(_docs().values()), ensure_ascii=False)
	cites = {m for m in texte.split('"') if m.startswith("quete:") and m != "quete:"}
	assert QUETE in cites
	# Gautier porte d'autres quêtes (bûcherons) : seules celles de CE fichier neuf comptent.
	neufs = [d for i, d in _docs().items() if i != GAUTIER]
	cites_neufs = {m for m in json.dumps(neufs, ensure_ascii=False).split('"') if m.startswith("quete:")}
	assert cites_neufs == {QUETE}


def test_gautier_garde_ses_autres_services_et_choix():
	"""Gautier est RELU du dump : la quête s'ajoute sans rien retirer."""
	avant = _dump()[GAUTIER]
	apres = _docs()[GAUTIER]
	for service, conf in avant.get("services", {}).items():
		assert apres["services"][service] == conf
	for nid, noeud in avant["dialogue"]["noeuds"].items():
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


def test_la_crypte_ne_s_ouvre_que_la_preuve_a_rapporter():
	"""Fermée sans la quête, ouverte quête en cours, refermée après la victoire ou une fois
	les ossements en poche."""
	crypte = _docs()[CRYPTE]
	sans = {"quetes_actives": [], "battle_maps_gagnees": [], "inventaire": []}
	assert not acces.acces_autorise(sans, crypte, lambda _id: None)[0]
	pendant = {"quetes_actives": [_collecte()], "battle_maps_gagnees": [], "inventaire": []}
	assert acces.acces_autorise(pendant, crypte, lambda _id: None)[0]
	gagnee = dict(pendant, battle_maps_gagnees=[CRYPTE])
	assert not acces.acces_autorise(gagnee, crypte, lambda _id: None)[0]


def test_la_crypte_garantit_un_strigoi():
	"""Le moteur tire chaque monstre AU HASARD parmi les espèces de la salle : une seule
	espèce, sinon la preuve pourrait manquer (Auteur, 13/10 : trois Strigoï)."""
	docs = _docs()
	donjon = docs[DONJON]
	assert donjon["portail"] == VILLAGE
	(salle,) = donjon["battle_maps"]
	assert salle["lieu"] == CRYPTE and salle["especes"] == ["espece:strigoi"]
	assert salle["nb_monstres"] == 3
	assert docs["pnj:fossoyeur_gaspard_fouquet"]["services"]["acces"]["lieu"] == CRYPTE


def test_la_crypte_est_une_salle_jouable():
	crypte = _docs()[CRYPTE]
	cells = crypte["cells"]
	w, h = crypte["dimensions"]["x"], crypte["dimensions"]["y"]
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


def test_escolives_sur_une_case_libre_de_la_carte_de_france():
	docs = _docs()
	base = _dump()
	(noeud_france,) = [n for n in docs["link:escolives_to_france"]["nodes"] if n["lieu"] == "lieu:france"]
	x, y = noeud_france["pos"]
	assert base["lieu:france"]["cells"][y][x] >= 1
	prises = {tuple(n["pos"]) for d in base.values() if d.get("type") == "connection"
			  for n in d.get("nodes", []) if n.get("lieu") == "lieu:france"}
	assert (x, y) not in prises


def test_images_presentes():
	docs = _docs()
	chemins = [
		os.path.join(RESSOURCES, "battle_maps", docs[CRYPTE]["image"]),
		os.path.join(RESSOURCES, "towns", docs[VILLAGE]["image"]),
	]
	for e in docs[VILLAGE]["pnj"]:
		chemins.append(os.path.join(RESSOURCES, "pnj", e["portrait"]))
	for d in docs.values():
		if d.get("type") == "pnj":
			chemins.append(os.path.join(RESSOURCES, "pnj", d["portrait"]))
	for p in chemins:
		assert os.path.exists(p), p


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

# tests/test_zones_defauts.py
#
# CONTENU PAR DÉFAUT DES ZONES D'INFLUENCE (utils/zones.py, `peupler_lieu`) : une zone porte
# `defauts_rencontres` / `defauts_ressources` (filtrés par RÉGION, `rules:regions`) ; le lieu
# garde ses `rencontres` / `ressources` (compléments), retire un défaut par `exclusions`, coupe
# tout par le tag `sans_defauts_zones` ; un PLACEMENT porte son propre contenu, valable dans sa
# seule forme (clé `<zone>@<i>`). Aucun accès DB : `get_doc_fn` = dict.get.

import asyncio
import re
from pathlib import Path

import pytest

from utils import chasse, quetes, zones


RACINE = Path(__file__).resolve().parent.parent


# ── Fixtures ─────────────────────────────────────────────────────────────────────

def _placement(zone, x, y, w=4, h=4, **extra):
	p = {"zone": zone, "x": x, "y": y, "w": w, "h": h, "rot": 0, "forme": "rectangle"}
	p["bbox"] = zones.compute_bbox(p)
	p.update(extra)
	return p


def _zone(zid, renc=(), ress=()):
	return {
		"_id": zid, "type": "zone_influence", "nom": zid, "intensite_max": 1.0,
		"table_evenements": [{"type": "combat", "poids": 1}, {"type": "ressource", "poids": 1}],
		"defauts_rencontres": list(renc), "defauts_ressources": list(ress),
	}


def _monde(**lieu_extra):
	"""Pays européen : une forêt (défauts loup partout, ours en Europe, lion en Afrique) et une
	rivière (défaut : roseau). Le lieu ajoute un sanglier dans la forêt."""
	foret = _zone("zone:foret",
				  renc=[{"espece": "espece:loup"},
						{"espece": "espece:ours", "regions": ["europe"]},
						{"espece": "espece:lion", "regions": ["afrique"]}],
				  ress=[{"ressource": "item:bois"}])
	riviere = _zone("zone:riviere", ress=[{"ressource": "item:roseau"}])
	lieu = {
		"_id": "lieu:gaule", "type": "lieu", "categorie": "pays",
		"dimensions": {"x": 40, "y": 40},
		"zone_influences": [_placement("zone:foret", 10, 10), _placement("zone:riviere", 30, 30)],
		"rencontres": [{"espece": "espece:sanglier", "zones": ["zone:foret"]}],
		"ressources": [],
	}
	lieu.update(lieu_extra)
	regles = {"_id": zones.REGLES_REGIONS, "regions": {
		"europe": {"nom": "Europe", "lieux": ["lieu:gaule"]},
		"afrique": {"nom": "Afrique", "lieux": ["lieu:maghreb"]},
	}}
	docs = {d["_id"]: d for d in (foret, riviere, lieu, regles)}
	return docs, lieu


def _especes(lieu, zone):
	return {e["espece"] for e in lieu["rencontres"] if zone in (e.get("zones") or [])}


# ── Fusion ───────────────────────────────────────────────────────────────────────

def test_defauts_filtres_par_region_et_complements_du_lieu():
	docs, lieu = _monde()
	p = zones.peupler_lieu(lieu, docs.get)
	assert _especes(p, "zone:foret") == {"espece:sanglier", "espece:loup", "espece:ours"}
	assert {e["ressource"] for e in p["ressources"]} == {"item:bois", "item:roseau"}


def test_les_entrees_ecrites_du_lieu_restent_en_tete_et_intactes():
	"""L'ordre des rencontres départage les ex æquo des traces : le contenu écrit passe d'abord."""
	docs, lieu = _monde(rencontres=[{"espece": "espece:sanglier"}])
	p = zones.peupler_lieu(lieu, docs.get)
	assert p["rencontres"][0] == {"espece": "espece:sanglier"}  # sans `zones` : tout le lieu


def test_lieu_hors_regions_ne_recoit_que_les_defauts_sans_region():
	docs, lieu = _monde(_id="lieu:inconnu")
	p = zones.peupler_lieu(lieu, docs.get)
	assert _especes(p, "zone:foret") == {"espece:sanglier", "espece:loup"}


def test_la_region_se_lit_sur_le_lieu_parent():
	docs, lieu = _monde(_id="lieu:clairiere", lieu_parent="lieu:gaule")
	docs["lieu:gaule"] = dict(lieu, _id="lieu:gaule")
	assert zones.region_de(lieu, docs[zones.REGLES_REGIONS], docs.get) == "europe"


def test_exclusion_par_zone_ne_retire_que_le_defaut():
	docs, lieu = _monde(exclusions=[{"espece": "espece:ours", "zones": ["zone:foret"]},
									{"espece": "espece:sanglier"}])
	p = zones.peupler_lieu(lieu, docs.get)
	# L'ours (défaut) part ; le sanglier, ÉCRIT par le lieu, n'est jamais exclu.
	assert _especes(p, "zone:foret") == {"espece:sanglier", "espece:loup"}


def test_exclusion_sans_zones_vaut_pour_toutes_les_zones():
	docs, lieu = _monde(exclusions=[{"ressource": "item:roseau"}])
	p = zones.peupler_lieu(lieu, docs.get)
	assert {e["ressource"] for e in p["ressources"]} == {"item:bois"}


def test_tag_sans_defauts_coupe_tous_les_defauts():
	docs, lieu = _monde(tags=[zones.TAG_SANS_DEFAUTS])
	p = zones.peupler_lieu(lieu, docs.get)
	assert p["rencontres"] == lieu["rencontres"]
	assert p["ressources"] == []


def test_un_defaut_ne_vaut_que_pour_une_zone_posee():
	docs, lieu = _monde()
	lieu["zone_influences"] = [lieu["zone_influences"][1]]  # rivière seule
	p = zones.peupler_lieu(lieu, docs.get)
	assert not any(e["espece"] == "espece:loup" for e in p["rencontres"])


def test_peupler_ne_mute_rien_et_est_idempotent():
	docs, lieu = _monde()
	avant = repr(lieu)
	p = zones.peupler_lieu(lieu, docs.get)
	assert repr(lieu) == avant
	assert zones.peupler_lieu(p, docs.get) is p
	assert p["_peuple"] is True


def test_lieu_sans_placement_rendu_tel_quel():
	docs, lieu = _monde(zone_influences=[])
	assert zones.peupler_lieu(lieu, docs.get) is lieu


# ── Contenu d'un placement ───────────────────────────────────────────────────────

def test_contenu_de_placement_ne_vaut_que_dans_sa_forme():
	docs, lieu = _monde()
	lieu["zone_influences"].append(_placement("zone:foret", 30, 10, rencontres=["espece:bete"]))
	p = zones.peupler_lieu(lieu, docs.get)
	cle = zones.cle_placement("zone:foret", 2)
	assert p["zone_influences"][2]["_cle"] == cle
	assert "_cle" not in p["zone_influences"][0]
	dans = zones.cles_actives([p["zone_influences"][2]])
	ailleurs = zones.cles_actives([p["zone_influences"][0]])
	assert "espece:bete" in zones.especes_rencontrables(p, dans)
	assert "espece:bete" not in zones.especes_rencontrables(p, ailleurs)
	# La forêt reste la forêt : ses défauts valent aussi dans ce placement.
	assert "espece:loup" in zones.especes_rencontrables(p, dans)


def test_recolte_de_placement_par_l_evenement_de_zone():
	docs, lieu = _monde()
	lieu["zone_influences"].append(_placement("zone:riviere", 10, 30, ressources=["item:perle"]))
	lieu["tags"] = [zones.TAG_SANS_DEFAUTS]
	p = zones.peupler_lieu(lieu, docs.get)
	zdefs = zones.load_zone_defs_for_lieu(p, docs.get)
	zdefs = {k: dict(v, table_evenements=[{"type": "ressource", "poids": 1}]) for k, v in zdefs.items()}
	evt = zones.resolve_zone_event(10, 30, p["zone_influences"], zdefs, rand_fn=lambda: 0.0)
	assert zones.cle_placement("zone:riviere", 2) in evt["cles_actives"]
	assert zones.resolve_recolte(evt, p, docs.get) == "item:perle"
	evt = zones.resolve_zone_event(30, 30, p["zone_influences"], zdefs, rand_fn=lambda: 0.0)
	assert zones.resolve_recolte(evt, p, docs.get) is None


def test_chasse_vise_le_placement_de_la_bete():
	docs, lieu = _monde(tags=[zones.TAG_SANS_DEFAUTS], rencontres=[])
	lieu["zone_influences"].append(_placement("zone:foret", 30, 10, rencontres=["espece:bete"]))
	p = zones.peupler_lieu(lieu, docs.get)
	pos = chasse.position_de_chasse(p, {"_id": "espece:bete"})
	assert pos == {"x": 30, "y": 10}


def test_portee_d_une_capitale_garde_le_contenu_des_placements_proches():
	docs, lieu = _monde()
	lieu["zone_influences"].append(_placement("zone:foret", 30, 10, rencontres=["espece:bete"]))
	p = zones.peupler_lieu(lieu, docs.get)
	proche = quetes.pays_a_portee(p, [(31, 11)], 3)
	loin = quetes.pays_a_portee(p, [(10, 10)], 3)
	assert "espece:bete" in quetes.especes_du_parent(proche)
	assert "espece:bete" not in quetes.especes_du_parent(loin)


# ── Point de passage unique ──────────────────────────────────────────────────────

def test_un_lieu_peuple_ne_se_sauve_jamais(monkeypatch):
	from db import config as db_config
	ecrits = []

	class _DB:
		def put(self, doc):
			ecrits.append(doc["_id"])

	monkeypatch.setattr(db_config, "db", _DB())
	docs, lieu = _monde()
	p = zones.peupler_lieu(lieu, docs.get)
	assert db_config.save_doc(p) is None
	assert db_config.save_docs([p]) == [False]
	assert db_config.save_doc(lieu) is lieu
	assert ecrits == ["lieu:gaule"]


# Fichiers qui lisent `rencontres` / `ressources` d'un lieu, et POURQUOI c'est sûr. Un nouveau
# lecteur doit passer par `zones.peupler_lieu` (ou recevoir un lieu déjà peuplé) puis
# s'inscrire ici — sinon il ignorerait en silence les défauts des zones.
LECTEURS = {
	"utils/zones.py": "le helper lui-même",
	"utils/traces.py": "peuple à l'entrée (traces_ici, menace_lieu)",
	"utils/chasse.py": "peuple dans lieux_chasse_de ; pays déjà peuplés par quetes.pays_relies",
	"utils/quetes.py": "peuple parent_doc (remplir_tableau), les pays (pays_relies), _candidats_chasse",
	"utils/renseignement.py": "index peuplé par routers/renseignement",
	"routers/renseignement.py": "_index_chaine / _index_complet / _contexte peuplent",
	"utils/focalisation.py": "boost_zone_event reçoit le lieu peuplé de routers/user._evenement_de_zone",
	"utils/guides.py": "index_lieux(…, get_doc_fn) peuple",
	"utils/colonisation.py": "reçoit le pays peuplé de routers/colonisation",
	"routers/colonisation.py": "lire_site / fonder peuplent",
	"utils/traversee.py": "construit la carte vue du navire, peuplée par start_combat",
	"routers/zones.py": "écritures d'édition : lit et sauve le doc BRUT, à dessein",
}


def test_aucun_lecteur_ne_contourne_peupler_lieu():
	motif = re.compile(r"""get\(\s*["'](rencontres|ressources)["']""")
	trouves = set()
	for f in [RACINE / "main.py", *(RACINE / "utils").glob("*.py"), *(RACINE / "routers").glob("*.py")]:
		if motif.search(f.read_text(encoding="utf-8")):
			trouves.add(f.relative_to(RACINE).as_posix())
	inconnus = trouves - set(LECTEURS)
	assert not inconnus, f"Lecteur(s) de rencontres/ressources hors de peupler_lieu : {sorted(inconnus)}"


# ── Édition : normalisation, usage, aperçu ───────────────────────────────────────


def test_normaliser_defauts_dedoublonne_et_refuse_un_id_invalide():
	out = zones.normaliser_defauts([{"espece": "espece:loup", "regions": ["europe", "", "europe"]},
									 {"espece": "espece:loup"}, {"espece": "espece:ours", "regions": []}], "espece")
	assert out == [{"espece": "espece:loup", "regions": ["europe"]}, {"espece": "espece:ours"}]
	with pytest.raises(ValueError):
		zones.normaliser_defauts([{"espece": "item:bois"}], "espece")


def test_normaliser_contenu_placement_retire_la_cle_de_lecture():
	p = zones.normaliser_contenu_placement({"zone": "zone:foret", "_cle": "zone:foret@0",
											"rencontres": ["espece:bete", "espece:bete", "x"], "ressources": []})
	assert p == {"zone": "zone:foret", "rencontres": ["espece:bete"]}


def test_normaliser_exclusions_et_regions():
	assert zones.normaliser_exclusions([{"espece": "espece:ours", "zones": ["zone:foret", "lieu:x"]},
										 {"ressource": "item:roseau"}, {"espece": ""}, "x"]) == [
		{"espece": "espece:ours", "zones": ["zone:foret"]}, {"ressource": "item:roseau"}]
	assert zones.normaliser_regions({"europe": {"nom": "", "lieux": ["lieu:a", "lieu:a", "zone:z"]}}) == {
		"europe": {"nom": "europe", "lieux": ["lieu:a"]}}
	with pytest.raises(ValueError):
		zones.normaliser_regions({"Mauvais Id": {}})


def test_usage_des_zones_compte_les_placements_par_lieu():
	_, lieu = _monde()
	lieu["zone_influences"].append(_placement("zone:foret", 30, 10))
	u = zones.usage_des_zones([lieu, {"_id": "lieu:vide"}])
	assert u == {"zone:foret": [{"id": "lieu:gaule", "label": "lieu:gaule", "placements": 2}],
				 "zone:riviere": [{"id": "lieu:gaule", "label": "lieu:gaule", "placements": 1}]}


def test_apercu_range_chaque_ligne_sous_sa_zone_avec_sa_provenance():
	docs, lieu = _monde(exclusions=[{"espece": "espece:ours"}])
	lieu["rencontres"].append({"espece": "espece:esprit"})  # tout le lieu
	lieu["zone_influences"].append(_placement("zone:foret", 30, 10, rencontres=["espece:bete"]))
	a = zones.apercu_lieu(lieu, zones.load_zone_defs_for_lieu(lieu, docs.get), "europe")
	assert [b["zone"] for b in a["zones"]] == ["zone:foret", "zone:riviere"]
	foret = a["zones"][0]
	assert foret["placements"] == 2
	vues = {(l["id"], l["source"], l["exclu"], l["placement"]) for l in foret["rencontres"]}
	assert ("espece:sanglier", "lieu", False, None) in vues
	assert ("espece:ours", "defaut", True, None) in vues
	assert ("espece:bete", "placement", False, 2) in vues
	assert [l["id"] for l in a["tout_le_lieu"]["rencontres"]] == ["espece:esprit"]


def test_apercu_marque_le_defaut_qui_recopie_une_entree_du_lieu():
	docs, lieu = _monde()
	lieu["rencontres"].append({"espece": "espece:loup", "zones": ["zone:foret"]})
	a = zones.apercu_lieu(lieu, zones.load_zone_defs_for_lieu(lieu, docs.get), "europe")
	loups = {(l["source"], l["doublon"]) for l in a["zones"][0]["rencontres"] if l["id"] == "espece:loup"}
	assert loups == {("lieu", False), ("defaut", True)}


# ── Endpoints de /admin/zones ────────────────────────────────────────────────────

ADMIN = {"_id": "user:admin", "admin": 1}


@pytest.fixture
def base(monkeypatch):
	from routers import zones as rz
	docs, lieu = _monde()
	ecrits = []

	def save(doc):
		assert not doc.get("_peuple")
		docs[doc["_id"]] = doc
		ecrits.append(doc["_id"])
		return doc

	def find(selector, fields=None):
		return [dict(d) for d in docs.values() if d.get("type") == selector.get("type")]

	monkeypatch.setattr(rz, "get_doc", lambda i: dict(docs[i]) if i in docs else None)
	monkeypatch.setattr(rz, "save_doc", save)
	monkeypatch.setattr(rz, "find_docs", find)
	monkeypatch.setattr(rz, "delete_doc", lambda d: docs.pop(d["_id"]))
	return rz, docs, ecrits


def test_modifier_une_zone_fusionne_sur_le_doc_relu(base):
	rz, docs, _ = base
	docs["zone:foret"]["champ_inconnu"] = 7
	z = asyncio.run(rz.zones_admin_modifier("zone:foret", ADMIN, {
		"defauts_rencontres": [{"espece": "espece:cerf", "regions": ["europe"]}], "_id": "zone:pirate", "usage": []}))
	assert z["_id"] == "zone:foret" and z["champ_inconnu"] == 7
	assert docs["zone:foret"]["defauts_rencontres"] == [{"espece": "espece:cerf", "regions": ["europe"]}]
	assert docs["zone:foret"]["defauts_ressources"] == [{"ressource": "item:bois"}]  # non envoyé : gardé


def test_modifier_refuse_une_valeur_invalide(base):
	from fastapi import HTTPException
	rz, _, ecrits = base
	with pytest.raises(HTTPException) as e:
		asyncio.run(rz.zones_admin_modifier("zone:foret", ADMIN, {"intensite_max": 3}))
	assert e.value.status_code == 422 and not ecrits


def test_creer_refuse_un_id_pris_et_supprimer_une_zone_posee(base):
	from fastapi import HTTPException
	rz, docs, _ = base
	with pytest.raises(HTTPException) as e:
		asyncio.run(rz.zones_admin_creer(ADMIN, {"_id": "zone:foret"}))
	assert e.value.status_code == 409
	z = asyncio.run(rz.zones_admin_creer(ADMIN, {"_id": "zone:lande_grise"}))
	assert docs["zone:lande_grise"]["type"] == "zone_influence" and z["usage"] == []
	with pytest.raises(HTTPException) as e:
		asyncio.run(rz.zones_admin_supprimer("zone:foret", ADMIN))
	assert e.value.status_code == 409 and "zone:foret" in docs
	asyncio.run(rz.zones_admin_supprimer("zone:lande_grise", ADMIN))
	assert "zone:lande_grise" not in docs


def test_apercu_et_exclusions_d_un_lieu(base):
	rz, docs, _ = base
	asyncio.run(rz.update_lieu_exclusions("lieu:gaule", ADMIN, {
		"exclusions": [{"espece": "espece:ours", "zones": ["zone:foret"]}], "sans_defauts": False}))
	a = rz.zones_admin_apercu("lieu:gaule", ADMIN)
	assert a["region"] == "europe" and a["exclusions"] == [{"espece": "espece:ours", "zones": ["zone:foret"]}]
	ours = [l for l in a["zones"][0]["rencontres"] if l["id"] == "espece:ours"]
	assert ours and ours[0]["exclu"]
	asyncio.run(rz.update_lieu_exclusions("lieu:gaule", ADMIN, {"exclusions": [], "sans_defauts": True}))
	assert "exclusions" not in docs["lieu:gaule"]
	assert zones.TAG_SANS_DEFAUTS in docs["lieu:gaule"]["tags"]


def test_placements_sauves_sans_cle_de_lecture(base):
	rz, docs, _ = base
	p = _placement("zone:foret", 5, 5, rencontres=["espece:bete"], _cle="zone:foret@0")
	asyncio.run(rz.update_lieu_zone_influences("lieu:gaule", ADMIN, {"zone_influences": [p]}))
	(sauve,) = docs["lieu:gaule"]["zone_influences"]
	assert "_cle" not in sauve and sauve["rencontres"] == ["espece:bete"]


def test_regions_remplacees_dans_rules_regions(base):
	rz, docs, _ = base
	asyncio.run(rz.zones_admin_regions(ADMIN, {"regions": {"mers": {"nom": "Mers", "lieux": ["lieu:mer"]}}}))
	assert docs[zones.REGLES_REGIONS]["regions"] == {"mers": {"nom": "Mers", "lieux": ["lieu:mer"]}}


def test_catalogue_liste_zones_usage_et_selecteurs(base):
	rz, docs, _ = base
	docs["espece:loup"] = {"_id": "espece:loup", "type": "espece", "nom": "Loup"}
	c = rz.zones_admin_catalogue(ADMIN)
	foret = next(z for z in c["zones"] if z["_id"] == "zone:foret")
	assert foret["usage"] == [{"id": "lieu:gaule", "label": "lieu:gaule", "placements": 1}]
	assert c["regions"]["europe"]["lieux"] == ["lieu:gaule"]
	assert c["especes"] == [{"id": "espece:loup", "nom": "Loup"}]
	assert c["lieux_a_zones"] == [{"id": "lieu:gaule", "label": "lieu:gaule", "placements": 2}]
	assert c["pays"] == [{"id": "lieu:gaule", "label": "lieu:gaule"}]

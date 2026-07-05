# tests/test_pnj.py
# Logique pure des PNJ de lieu (utils/pnj.py) : tirage de présence persisté, navigation
# de l'arbre de dialogue (conditions, placeholders), service de soin (payant/gratuit
# selon relation). Aucun accès DB — tout est passé en dicts.

from utils import pnj


# ---------------------------------------------------------------------------
# Fixtures en mémoire
# ---------------------------------------------------------------------------

def _lieu(pnj_entries=None, _id="lieu:temple_test"):
    return {"_id": _id, "type": "lieu", "pnj": pnj_entries or []}


def _entree(character="pnj:reverend", proba=0.7, **extra):
    return {"character": character, "probabilite": proba, "portrait": "pretre.png", **extra}


def _pnj_doc():
    return {
        "_id": "pnj:reverend",
        "type": "pnj",
        "nom": "Révérend Malakor",
        "portrait": "pretre_doc.png",
        "description": "Un prêtre ogre.",
        "services": {
            "soin": {
                "cout_cuivre": 1,
                "fraction_pv": 0.5,
                "gratuit_si": {
                    "lieux": ["lieu:auxerre", "lieu:guilde"],
                    "seuil": 70,
                    "fraction_pv": 1.0,
                },
                "noeuds": {"fait": "soin_fait", "sans_fonds": "soin_sans_fonds", "inutile": "soin_inutile"},
            }
        },
        "dialogue": {
            "noeud_depart": "accueil",
            "noeuds": {
                "accueil": {
                    "texte": "Bienvenue, {prenom}.",
                    "choix": [
                        {"id": "soin", "label": "Soignez-moi ({cout})", "next": "soin_propose"},
                        {"id": "secret", "label": "…", "next": "fin",
                         "condition": {"intro_raison": "secret"}},
                        {"id": "vip", "label": "Salut l'ami", "next": "fin",
                         "condition": {"relation_min": {"lieux": ["lieu:guilde"], "seuil": 70}}},
                        {"id": "fin", "label": "Au revoir"},
                    ],
                },
                "soin_propose": {
                    "texte": "Une offrande de {cout}.",
                    "texte_gratuit": "Pour toi, {prenom}, ce sera gratuit.",
                    "choix": [
                        {"id": "accepter", "label": "Accepter", "action": {"service": "soin"}},
                        {"id": "refuser", "label": "Refuser", "next": "accueil"},
                    ],
                },
                "soin_fait": {"texte": "Voilà.", "choix": [{"id": "fin", "label": "Merci"}]},
            },
        },
    }


def _character(prenom="Aldo", intro_raison=None):
    c = {"prenom": prenom, "currentPV": 10}
    if intro_raison:
        c["intro"] = {"statut": "terminee", "raison": intro_raison}
    return c


def _ctx(relations=None, intro_raison=None, prenom="Aldo"):
    return {"relations": relations or {}, "intro_raison": intro_raison, "prenom": prenom}


# ---------------------------------------------------------------------------
# Tirage de présence
# ---------------------------------------------------------------------------

def test_tirage_present_si_jet_sous_proba():
    lieu = _lieu([_entree(proba=0.7)])
    assert pnj.tirer_pnj_present(lieu, rand_fn=lambda: 0.69) == "pnj:reverend"
    assert pnj.tirer_pnj_present(lieu, rand_fn=lambda: 0.7) is None


def test_tirage_ordre_premiere_entree_gagne():
    lieu = _lieu([_entree("pnj:a", proba=1.0), _entree("pnj:b", proba=1.0)])
    assert pnj.tirer_pnj_present(lieu, rand_fn=lambda: 0.0) == "pnj:a"


def test_tirage_lieu_sans_pnj():
    assert pnj.tirer_pnj_present(_lieu()) is None
    assert pnj.tirer_pnj_present({"_id": "lieu:x"}) is None


def test_poser_pnj_present_pose_et_persiste():
    character = _character()
    lieu = _lieu([_entree(proba=1.0)])
    assert pnj.poser_pnj_present(character, lieu, rand_fn=lambda: 0.0) is True
    assert character["pnj_present"] == {"lieu": "lieu:temple_test", "character": "pnj:reverend"}
    # Même lieu → no-op (refresh stable), même si le jet aurait donné autre chose.
    assert pnj.poser_pnj_present(character, lieu, rand_fn=lambda: 0.99) is False
    assert character["pnj_present"]["character"] == "pnj:reverend"


def test_poser_pnj_present_absent_reste_stable():
    character = _character()
    lieu = _lieu([_entree(proba=0.5)])
    assert pnj.poser_pnj_present(character, lieu, rand_fn=lambda: 0.9) is True
    assert character["pnj_present"] == {"lieu": "lieu:temple_test", "character": None}
    assert pnj.poser_pnj_present(character, lieu, rand_fn=lambda: 0.0) is False


def test_poser_pnj_present_changement_de_lieu_retire():
    character = _character()
    pnj.poser_pnj_present(character, _lieu([_entree(proba=1.0)]), rand_fn=lambda: 0.0)
    autre = _lieu(_id="lieu:autre")
    assert pnj.poser_pnj_present(character, autre, rand_fn=lambda: 0.0) is True
    assert character["pnj_present"] == {"lieu": "lieu:autre", "character": None}


def test_entree_pnj_active():
    character = _character()
    lieu = _lieu([_entree(proba=1.0)])
    pnj.poser_pnj_present(character, lieu, rand_fn=lambda: 0.0)
    entree = pnj.entree_pnj_active(character, lieu)
    assert entree and entree["character"] == "pnj:reverend"
    # Tirage périmé (autre lieu) → None.
    assert pnj.entree_pnj_active(character, _lieu(_id="lieu:autre")) is None
    # PNJ absent au tirage → None.
    character["pnj_present"]["character"] = None
    assert pnj.entree_pnj_active(character, lieu) is None
    # Entrée retirée de la donnée depuis le tirage → None.
    character["pnj_present"]["character"] = "pnj:disparu"
    assert pnj.entree_pnj_active(character, lieu) is None


def test_pnj_payload_priorite_entree_puis_doc():
    entree = _entree(image="temple_avec_pnj.png", description="Sur les marches.")
    payload = pnj.pnj_payload(entree, _pnj_doc())
    assert payload["nom"] == "Révérend Malakor"
    assert payload["portrait"] == "pretre.png"          # entrée du lieu prioritaire
    assert payload["image_lieu"] == "temple_avec_pnj.png"
    assert payload["description"] == "Sur les marches."
    # Sans portrait/description d'entrée → repli sur le doc PNJ.
    payload2 = pnj.pnj_payload({"character": "pnj:reverend"}, _pnj_doc())
    assert payload2["portrait"] == "pretre_doc.png"
    assert payload2["description"] == "Un prêtre ogre."
    assert payload2["image_lieu"] is None


# ---------------------------------------------------------------------------
# Contexte & conditions
# ---------------------------------------------------------------------------

def test_contexte_dialogue_resout_les_lieux_cites():
    character = _character(intro_raison="secret")
    valeurs = {"lieu:auxerre": 80, "lieu:guilde": 40}
    ctx = pnj.contexte_dialogue(character, _pnj_doc(), lambda lid: valeurs.get(lid, 50))
    assert ctx["relations"] == {"lieu:auxerre": 80, "lieu:guilde": 40}
    assert ctx["intro_raison"] == "secret"
    assert ctx["prenom"] == "Aldo"


def test_condition_relation_min_ou_logique():
    cond = {"relation_min": {"lieux": ["lieu:a", "lieu:b"], "seuil": 70}}
    assert pnj.condition_ok(cond, _ctx({"lieu:a": 30, "lieu:b": 70})) is True
    assert pnj.condition_ok(cond, _ctx({"lieu:a": 69, "lieu:b": 69})) is False
    assert pnj.condition_ok(cond, _ctx()) is False        # aucune relation connue
    assert pnj.condition_ok(None, _ctx()) is True         # sans condition


def test_condition_intro_raison():
    cond = {"intro_raison": "secret"}
    assert pnj.condition_ok(cond, _ctx(intro_raison="secret")) is True
    assert pnj.condition_ok(cond, _ctx(intro_raison="famine")) is False
    assert pnj.condition_ok(cond, _ctx()) is False


# ---------------------------------------------------------------------------
# Navigation de l'arbre
# ---------------------------------------------------------------------------

def test_noeud_client_filtre_les_choix_et_substitue():
    doc = _pnj_doc()
    soin = {"cout_cuivre": 1, "fraction_pv": 0.5, "gratuit": False}
    noeud = pnj.noeud_client(doc, "accueil", _ctx(), soin)
    assert noeud["texte"] == "Bienvenue, Aldo."
    ids = [c["id"] for c in noeud["choix"]]
    assert ids == ["soin", "fin"]                         # secret + vip filtrés
    assert noeud["choix"][0]["label"] == "Soignez-moi (1 cuivre)"
    assert noeud["choix"][0]["action"] is False           # pas d'action sur ce choix
    # Conditions remplies → choix visibles.
    ctx = _ctx({"lieu:guilde": 90}, intro_raison="secret")
    ids2 = [c["id"] for c in pnj.noeud_client(doc, "accueil", ctx, soin)["choix"]]
    assert ids2 == ["soin", "secret", "vip", "fin"]


def test_noeud_client_texte_gratuit_et_cout():
    doc = _pnj_doc()
    gratuit = {"cout_cuivre": 0, "fraction_pv": 1.0, "gratuit": True}
    noeud = pnj.noeud_client(doc, "soin_propose", _ctx(), gratuit)
    assert noeud["texte"] == "Pour toi, Aldo, ce sera gratuit."
    payant = {"cout_cuivre": 1, "fraction_pv": 0.5, "gratuit": False}
    noeud2 = pnj.noeud_client(doc, "soin_propose", _ctx(), payant)
    assert noeud2["texte"] == "Une offrande de 1 cuivre."
    assert noeud2["choix"][0]["action"] is True


def test_noeud_client_inconnu():
    assert pnj.noeud_client(_pnj_doc(), "nexiste_pas", _ctx()) is None
    assert pnj.noeud_client({}, "accueil", _ctx()) is None


def test_choix_valide_revalide_serveur():
    doc = _pnj_doc()
    assert pnj.choix_valide(doc, "accueil", "soin", _ctx())["next"] == "soin_propose"
    assert pnj.choix_valide(doc, "accueil", "inconnu", _ctx()) is None
    assert pnj.choix_valide(doc, "nexiste_pas", "soin", _ctx()) is None
    # Choix existant mais condition non remplie → None (pas de triche client).
    assert pnj.choix_valide(doc, "accueil", "vip", _ctx()) is None
    assert pnj.choix_valide(doc, "accueil", "vip", _ctx({"lieu:guilde": 75})) is not None


# ---------------------------------------------------------------------------
# Service de soin
# ---------------------------------------------------------------------------

def test_soin_effectif_payant_par_defaut():
    soin = pnj.soin_effectif(_pnj_doc(), _ctx({"lieu:auxerre": 50, "lieu:guilde": 69}))
    assert soin == {"cout_cuivre": 1, "fraction_pv": 0.5, "gratuit": False}


def test_soin_effectif_gratuit_si_une_relation_suffit():
    soin = pnj.soin_effectif(_pnj_doc(), _ctx({"lieu:auxerre": 20, "lieu:guilde": 70}))
    assert soin == {"cout_cuivre": 0, "fraction_pv": 1.0, "gratuit": True}


def test_soin_effectif_sans_service():
    assert pnj.soin_effectif({"services": {}}, _ctx()) is None
    assert pnj.soin_effectif({}, _ctx()) is None


def test_soin_effectif_seuil_defaut_world_var():
    doc = _pnj_doc()
    del doc["services"]["soin"]["gratuit_si"]["seuil"]    # → défaut PNJ_REPUTATION_SEUIL (70)
    assert pnj.soin_effectif(doc, _ctx({"lieu:auxerre": 70}))["gratuit"] is True
    assert pnj.soin_effectif(doc, _ctx({"lieu:auxerre": 69}))["gratuit"] is False


def test_appliquer_soin_fraction_et_clamp():
    character = {"currentPV": 10}
    assert pnj.appliquer_soin(character, pv_max=100, fraction=0.5) == 50
    assert character["currentPV"] == 60
    # Clamp au max : il ne restait que 40 PV à rendre.
    assert pnj.appliquer_soin(character, pv_max=100, fraction=1.0) == 40
    assert character["currentPV"] == 100
    # PV pleins → 0 rendu.
    assert pnj.appliquer_soin(character, pv_max=100, fraction=1.0) == 0

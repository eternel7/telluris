# tests/test_pnj.py
# Logique pure des PNJ de lieu (utils/pnj.py) : tirage de présence persisté, navigation
# de l'arbre de dialogue (conditions, placeholders), service de soin (payant/gratuit
# selon relation). Aucun accès DB — tout est passé en dicts.

from models import character_stats
from utils import lint_dialogues, pnj


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
            },
            "don": {
                "item": "item:Eau_benite",
                "quantite": 1,
                "cout_cuivre": 5,
                "gratuit_si": {"lieux": ["lieu:auxerre", "lieu:guilde"], "seuil": 70},
                "noeuds": {"fait": "don_fait", "sans_fonds": "don_sans_fonds", "trop_charge": "don_trop_charge"},
            },
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
# Délai de réouverture
# ---------------------------------------------------------------------------

def _doc_delai(delai=1800, attente="repos"):
    """Arbre minimal : `adieu` ferme le dialogue pour un temps, `repos` est ce que le PNJ
    répond entre-temps."""
    dialogue = {
        "noeud_depart": "accueil",
        "noeuds": {
            "accueil": {"texte": "Bonjour.", "choix": [{"id": "ok", "next": "adieu"}]},
            "adieu": {"texte": "Repassez.", "delai_min": delai,
                      "choix": [{"id": "ok", "next": "fin"}]},
            "repos": {"texte": "Pas maintenant.", "choix": [{"id": "ok", "next": "fin"}]},
        },
    }
    if attente is not None:
        dialogue["noeud_attente"] = attente
    return {"_id": "pnj:gautier", "type": "pnj", "dialogue": dialogue}


def test_delai_min_de_lit_le_noeud():
    doc = _doc_delai()
    assert pnj.delai_min_de(doc, "adieu") == 1800
    assert pnj.delai_min_de(doc, "accueil") == 0        # champ absent
    assert pnj.delai_min_de(doc, "nexiste_pas") == 0
    assert pnj.delai_min_de({}, "adieu") == 0


def test_delai_min_illisible_ne_verrouille_rien():
    # Une valeur qu'on ne sait pas lire ne doit pas verrouiller un PNJ en silence.
    for brut in (None, 0, -60, "beaucoup", [1800]):
        assert pnj.delai_min_de(_doc_delai(delai=brut), "adieu") == 0


def test_armer_delai_pose_l_entree():
    doc, character = _doc_delai(), {}
    entree = pnj.armer_delai(character, "pnj:gautier", doc, "adieu", 1000)
    assert entree == {"jusqu": 2800, "noeud": "adieu"}
    assert character["dialogues_delais"]["pnj:gautier"] == entree


def test_armer_delai_n_ecrit_rien_sans_delai():
    # ⚠️ Pas même le dictionnaire : un nœud ordinaire ne doit laisser aucune trace.
    character = {}
    assert pnj.armer_delai(character, "pnj:gautier", _doc_delai(), "accueil", 1000) is None
    assert pnj.armer_delai(character, "pnj:gautier", _doc_delai(), None, 1000) is None
    assert pnj.armer_delai(character, "pnj:gautier", _doc_delai(), "fin", 1000) is None
    assert "dialogues_delais" not in character


def test_delai_restant_est_paresseux():
    assert pnj.delai_restant({}, "pnj:gautier", 1000) == 0
    character = {"dialogues_delais": {"pnj:gautier": {"jusqu": 2800, "noeud": "adieu"}}}
    assert pnj.delai_restant(character, "pnj:gautier", 1000) == 1800
    assert pnj.delai_restant(character, "pnj:gautier", 2800) == 0     # échu pile
    assert pnj.delai_restant(character, "pnj:gautier", 9999) == 0
    assert pnj.delai_restant(character, "pnj:autre", 1000) == 0
    # ⚠️ Un getter ne purge pas : l'entrée échue reste en base, inerte.
    assert "pnj:gautier" in character["dialogues_delais"]


def test_noeud_depart_effectif_devie_pendant_le_delai():
    doc = _doc_delai()
    assert pnj.noeud_depart_effectif(doc, 1800) == "repos"
    assert pnj.noeud_depart_effectif(doc, 0) == "accueil"


def test_noeud_depart_effectif_replis():
    # Sans `noeud_attente` déclaré : le départ ordinaire (seul le flag agira).
    assert pnj.noeud_depart_effectif(_doc_delai(attente=None), 1800) == "accueil"
    # ⚠️ Nœud d'attente MORT → repli fail-open sur le départ. Le renvoyer quand même donnerait
    # un `noeud_client` à None, donc un PNJ muet dont le panneau se referme aussitôt.
    assert pnj.noeud_depart_effectif(_doc_delai(attente="disparu"), 1800) == "accueil"
    assert pnj.noeud_depart_effectif({}, 1800) == "accueil"


def test_condition_dialogue_en_attente_se_teste_dans_les_deux_sens():
    # C'est `{"flag": false}` qui verrouille un choix pendant le délai — sans lui, revenir à
    # l'accueil par une branche annexe reproposerait la mission.
    libre = _ctx()
    bloque = _ctx()
    bloque["flags"] = {"dialogue_en_attente": True}
    assert pnj.condition_ok({"dialogue_en_attente": False}, libre) is True
    assert pnj.condition_ok({"dialogue_en_attente": False}, bloque) is False
    assert pnj.condition_ok({"dialogue_en_attente": True}, bloque) is True


# ---------------------------------------------------------------------------
# Récompense de relation portée par un nœud
# ---------------------------------------------------------------------------

_DEFAUT = object()


def _doc_relation(bloc=_DEFAUT, reinit="merci"):
    """Arbre minimal : `merci` verse la réputation, `porte` rouvre ce versement."""
    bloc = {"delta": 1} if bloc is _DEFAUT else bloc
    noeuds = {
        "accueil": {"texte": "Oui ?", "choix": [{"id": "ok", "next": "merci"},
                                                {"id": "go", "next": "porte"}]},
        "merci": {"texte": "Beau travail.", "choix": [{"id": "ok", "next": "fin"}]},
        "porte": {"texte": "Descendez.", "choix": [{"id": "ok", "next": "fin"}]},
    }
    if bloc is not None:
        noeuds["merci"]["relation"] = bloc
    if reinit is not None:
        noeuds["porte"]["relation_reinit"] = reinit
    return {"_id": "pnj:armand", "type": "pnj",
            "dialogue": {"noeud_depart": "accueil", "noeuds": noeuds}}


def test_recompense_relation_normalisee():
    doc = _doc_relation()
    # `lieu` absent = le lieu courant (c'est le router qui tranche) ; la clé est DÉRIVÉE, donc
    # un auteur qui n'écrit pas `unique` obtient quand même le comportement sûr.
    assert pnj.recompense_relation_de(doc, "merci") == {
        "lieu": None, "delta": 1, "cle": "pnj:armand:merci"}
    explicite = _doc_relation({"delta": -2, "lieu": "lieu:auxerre", "unique": "partage"})
    assert pnj.recompense_relation_de(explicite, "merci") == {
        "lieu": "lieu:auxerre", "delta": -2, "cle": "partage"}


def test_recompense_relation_absente_ou_illisible():
    doc = _doc_relation()
    assert pnj.recompense_relation_de(doc, "accueil") is None       # aucun bloc
    assert pnj.recompense_relation_de(doc, "nexiste_pas") is None
    assert pnj.recompense_relation_de({}, "merci") is None
    # Un delta nul ou qu'on ne sait pas lire ne verse rien plutôt que de lever.
    for brut in ({"delta": 0}, {"delta": "beaucoup"}, {"delta": None}, "non", [1]):
        assert pnj.recompense_relation_de(_doc_relation(brut), "merci") is None
    # `unique` non textuel retombe silencieusement sur la clé dérivée (le linter le signale).
    assert pnj.recompense_relation_de(_doc_relation({"delta": 1, "unique": True}),
                                      "merci")["cle"] == "pnj:armand:merci"


def test_marqueur_de_versement_est_unique_et_ne_mute_pas_en_lecture():
    character = {}
    assert pnj.relation_deja_versee(character, "pnj:armand:merci") is False
    assert "dialogues_relations" not in character          # ⚠️ un getter n'initialise rien
    pnj.marquer_relation_versee(character, "pnj:armand:merci", 1000)
    assert character["dialogues_relations"] == {"pnj:armand:merci": 1000}
    assert pnj.relation_deja_versee(character, "pnj:armand:merci") is True
    assert pnj.relation_deja_versee(character, "pnj:armand:autre") is False


def test_relations_a_reinitialiser_resout_la_cle_du_noeud_nomme():
    # On nomme un NŒUD, jamais une clé brute : `unique` explicite et clé dérivée marchent pareil.
    assert pnj.relations_a_reinitialiser(_doc_relation(), "porte") == ["pnj:armand:merci"]
    liste = _doc_relation(reinit=["merci", "merci"])
    assert pnj.relations_a_reinitialiser(liste, "porte") == ["pnj:armand:merci"]   # dédoublonné
    nomme = _doc_relation({"delta": 1, "unique": "partage"})
    assert pnj.relations_a_reinitialiser(nomme, "porte") == ["partage"]
    # ⚠️ Fail-soft : une cible morte est ignorée en jeu (c'est le linter qui la signale).
    assert pnj.relations_a_reinitialiser(_doc_relation(reinit="disparu"), "porte") == []
    assert pnj.relations_a_reinitialiser(_doc_relation(bloc=None), "porte") == []
    assert pnj.relations_a_reinitialiser(_doc_relation(reinit=None), "porte") == []
    assert pnj.relations_a_reinitialiser(_doc_relation(reinit=42), "porte") == []


def test_cycle_verser_lever_verser():
    # C'est toute la boucle du donjon : la seconde commission doit pouvoir rapporter à nouveau.
    doc, character = _doc_relation(), {}
    cle = pnj.recompense_relation_de(doc, "merci")["cle"]
    pnj.marquer_relation_versee(character, cle, 1000)
    assert pnj.relation_deja_versee(character, cle) is True
    assert pnj.oublier_relations_versees(
        character, pnj.relations_a_reinitialiser(doc, "porte")) is True
    assert pnj.relation_deja_versee(character, cle) is False
    # Rien à retirer → rien n'a bougé : l'appelant n'a pas à sauvegarder.
    assert pnj.oublier_relations_versees(character, [cle]) is False
    assert pnj.oublier_relations_versees({}, ["pnj:armand:merci"]) is False


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
    """⚠️ Le seuil est lu SUR LE MODULE et jamais recopié en dur : c'est une variable de monde,
    réglable à chaud depuis `/admin`. Un littéral ici ferait échouer le test à la première
    retouche d'équilibrage — pour un comportement rigoureusement correct."""
    seuil = int(character_stats.PNJ_REPUTATION_SEUIL)
    doc = _pnj_doc()
    del doc["services"]["soin"]["gratuit_si"]["seuil"]    # → défaut PNJ_REPUTATION_SEUIL
    assert pnj.soin_effectif(doc, _ctx({"lieu:auxerre": seuil}))["gratuit"] is True
    assert pnj.soin_effectif(doc, _ctx({"lieu:auxerre": seuil - 1}))["gratuit"] is False


def test_appliquer_soin_fraction_et_clamp():
    character = {"currentPV": 10}
    assert pnj.appliquer_soin(character, pv_max=100, fraction=0.5) == 50
    assert character["currentPV"] == 60
    # Clamp au max : il ne restait que 40 PV à rendre.
    assert pnj.appliquer_soin(character, pv_max=100, fraction=1.0) == 40
    assert character["currentPV"] == 100
    # PV pleins → 0 rendu.
    assert pnj.appliquer_soin(character, pv_max=100, fraction=1.0) == 0


# ---------------------------------------------------------------------------
# Service de don (eau bénite)
# ---------------------------------------------------------------------------

def test_don_effectif_payant_par_defaut():
    don = pnj.don_effectif(_pnj_doc(), _ctx({"lieu:auxerre": 50, "lieu:guilde": 69}))
    assert don == {"item": "item:Eau_benite", "quantite": 1, "cout_cuivre": 5, "gratuit": False}


def test_don_effectif_gratuit_si_une_relation_suffit():
    don = pnj.don_effectif(_pnj_doc(), _ctx({"lieu:auxerre": 20, "lieu:guilde": 70}))
    assert don == {"item": "item:Eau_benite", "quantite": 1, "cout_cuivre": 0, "gratuit": True}


def test_don_effectif_sans_service_ou_sans_item():
    assert pnj.don_effectif({"services": {}}, _ctx()) is None
    assert pnj.don_effectif({}, _ctx()) is None
    # Service présent mais sans item → None (rien à donner).
    doc = _pnj_doc(); doc["services"]["don"].pop("item")
    assert pnj.don_effectif(doc, _ctx()) is None


def test_don_effectif_seuil_defaut_world_var():
    """Même règle que pour le soin : le seuil se lit sur le module, il ne se recopie pas."""
    seuil = int(character_stats.PNJ_REPUTATION_SEUIL)
    doc = _pnj_doc()
    del doc["services"]["don"]["gratuit_si"]["seuil"]     # → défaut PNJ_REPUTATION_SEUIL
    assert pnj.don_effectif(doc, _ctx({"lieu:auxerre": seuil}))["gratuit"] is True
    assert pnj.don_effectif(doc, _ctx({"lieu:auxerre": seuil - 1}))["gratuit"] is False


def test_appliquer_don_ajoute_references_inventaire():
    character = {}
    assert pnj.appliquer_don(character, "item:Eau_benite", 0.4, 2) == 2
    assert character["inventaire"] == [
        {"item": "item:Eau_benite", "poids": 0.4},
        {"item": "item:Eau_benite", "poids": 0.4},
    ]
    # Ajout cumulatif (au moins 1 même si quantite < 1).
    assert pnj.appliquer_don(character, "item:Bougie", 0.1, 0) == 1
    assert len(character["inventaire"]) == 3
    assert character["inventaire"][-1] == {"item": "item:Bougie", "poids": 0.1}


# ---------------------------------------------------------------------------
# Linter — contrôles du délai de réouverture
# ---------------------------------------------------------------------------
# Un délai est de la donnée muette : une faute ne se verrait qu'en jouant la branche.

def _messages(doc, niveau=None):
    return [t["message"] for t in lint_dialogues.analyser_doc(doc)
            if niveau is None or t["niveau"] == niveau]


def test_lint_noeud_attente_valide_est_atteignable():
    # Le nœud d'attente n'est atteint par aucun `next` : sans son ajout aux points d'entrée
    # du BFS, il serait signalé « inatteignable ».
    assert lint_dialogues.analyser_doc(_doc_delai()) == []


def test_lint_noeud_attente_mort():
    msgs = _messages(_doc_delai(attente="disparu"), "erreur")
    assert any("noeud_attente" in m and "disparu" in m for m in msgs)


def test_lint_delai_min_illisible():
    doc = _doc_delai(delai="beaucoup")
    assert any("delai_min" in m for m in _messages(doc, "erreur"))


def test_lint_delai_min_sur_le_noeud_de_depart():
    # Le PNJ se verrouillerait lui-même à chaque ouverture — et le GET n'arme jamais, donc
    # rien en jeu ne rendrait la faute visible.
    doc = _doc_delai()
    doc["dialogue"]["noeuds"]["accueil"]["delai_min"] = 600
    assert any("se verrouillerait" in m for m in _messages(doc, "erreur"))
    doc = _doc_delai()
    doc["dialogue"]["noeuds"]["repos"]["delai_min"] = 600
    assert any("se verrouillerait" in m for m in _messages(doc, "erreur"))


def test_lint_delai_invisible_est_signale():
    # Ni nœud d'attente, ni choix conditionné : le joueur ne verrait qu'un PNJ devenu muet.
    doc = _doc_delai(attente=None)
    assert any("invisible" in m for m in _messages(doc, "avertissement"))
    # Une condition `dialogue_en_attente` quelque part suffit à lever l'avertissement.
    doc["dialogue"]["noeuds"]["accueil"]["choix"][0]["condition"] = {"dialogue_en_attente": False}
    assert not any("invisible" in m for m in _messages(doc, "avertissement"))


# ---------------------------------------------------------------------------
# Linter — récompense de relation portée par un nœud
# ---------------------------------------------------------------------------

def test_lint_relation_valide_est_silencieuse():
    assert lint_dialogues.analyser_doc(_doc_relation()) == []


def test_lint_relation_bloc_fautif():
    assert any("clé inconnue" in m
               for m in _messages(_doc_relation({"delta": 1, "valeur": 3}), "erreur"))
    assert any("delta" in m for m in _messages(_doc_relation({"delta": 0}), "erreur"))
    assert any("delta" in m for m in _messages(_doc_relation({"delta": "bcp"}), "erreur"))
    assert any("lieu" in m
               for m in _messages(_doc_relation({"delta": 1, "lieu": "auxerre"}), "erreur"))
    assert any("unique" in m
               for m in _messages(_doc_relation({"delta": 1, "unique": True}), "erreur"))
    assert any("attendu un objet" in m for m in _messages(_doc_relation("oui"), "erreur"))


def test_lint_relation_reinit_qui_ne_leve_rien():
    # ⚠️ Le contrôle qui compte : une levée morte laisse la récompense fermée POUR TOUJOURS,
    # et le dialogue se déroule pourtant normalement — rien ne le montrerait en jeu.
    assert any("ne se rouvrira JAMAIS" in m
               for m in _messages(_doc_relation(reinit="disparu"), "erreur"))
    assert any("ne lève rien" in m
               for m in _messages(_doc_relation(bloc=None, reinit="merci"), "erreur"))
    assert any("attendu un id de nœud" in m
               for m in _messages(_doc_relation(reinit=42), "erreur"))


def test_lint_relation_reinit_sur_soi_meme_est_legitime():
    # Une récompense volontairement répétable à chaque lecture : pas une faute.
    doc = _doc_relation(reinit=None)
    doc["dialogue"]["noeuds"]["merci"]["relation_reinit"] = "merci"
    assert lint_dialogues.analyser_doc(doc) == []

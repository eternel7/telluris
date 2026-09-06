---
name: telluris-recrutement
description: Recruitment, group combat and companions: expedition's pooled group capabilities, hiring recruits and group combat, permanent company membership, single-mission contracts, and mounts (utils/recrutement.py, expedition.py, montures.py, routers/recrutement.py, routers/montures.py). Load when working on the group/companion system, recruitment, or mounts.
---

### Capacités mises en commun par l'expédition (`utils/expedition.py`)
Ce que le groupe sait faire **ensemble**, et non ce que chacun sait faire seul : `membres` (principal en tête, **jamais de monture** — cf. Conventions §7), `porteur_avec_tag` (sac + slots, tout membre), `meilleur_negociateur` (Cha **buffé**, seuil d'affinité pour qu'un compagnon prenne la parole). Chaîne d'import acyclique `bois → expedition → recrutement`. Couvert par `tests/test_expedition.py` et `tests/test_marchandage_groupe.py`.

Contenu : `jsons/competences_allie_a_importer.json` — compétences actives `cible:"allie"`, niveau 1 et non 0 (absentes du choix de création).


### Recrutement d'aventuriers & combat de groupe
**Recrue = doc `aventurier:*` MIROIR du character** (mêmes champs que `build_joueur_snapshot`/`compute_derived_stats`/`grant_xp`/`carried_weight`, + `statut`/`giver`/`exigences`/`expire_at`) → tout le moteur de combat marche dessus tel quel. Logique pure `utils/recrutement.py`, router `routers/recrutement.py` (congédier autorisé **PARTOUT**). ⚠️ **Le rang de guilde n'appartient qu'au principal** : une recrue, un compagnon, une monture et une personne escortée n'en ont aucun et n'en gagnent jamais.

Génération procédurale (race/sexe/vocation, stats, équipement équipé dans les slots, portrait par nommage strict), rotation paresseuse du tableau (recrue expirée supprimée, ex-compagnon repassé `parti` et ré-offert en priorité), groupe/contrat (plafond, départ volontaire sous un seuil d'affinité), exigences (part de butin prélevée au turn-in via `regler_part_butin`, clauses à accepter), affinités et combat de groupe (`groupe_effectif`, IA monstre ciblant le joueur vivant le plus proche, défaite seulement si tout le monde est à terre, `finalize_combat` multi-docs idempotent par doc) sont couverts par `tests/test_recrutement.py`, `tests/test_recrutement_endpoints.py`, `tests/test_groupe.py` et `tests/test_combat_groupe.py`.

**Butin de victoire réparti** : `/collect` reçoit des `attributions:[{monstre_id, beneficiaire_id}]`, chaque carcasse allant au sac de SON bénéficiaire, borné par sa charge. UI de l'overlay de fin : une rangée de pastilles-portrait par carcasse (`buildLootList`/`recomputeCharge`, défaut = principal, « 🫳 laisser au sol » en ocre), jauge de charge par membre (`renderLootCharges`). ⚠️ `leaveCombat` POSTe dès que la section butin est visible, même sans attribution — c'est cet appel qui verse au sol.

**Client en combat** : `me() = activePlayer(state)` remplace `joueurs[0]` partout (caméra centrée sur le membre actif) ; membres non actifs = `.ally-token` bleus ; bandeau d'initiative résolu par id.

**Gestion du groupe hors combat** — bouton **👥 Groupe** → `#groupe-panel`, accessible **PARTOUT**. Deux sections en accordéon : **👥 Compagnons** (fiche + congédier) et **🎒 Inventaire du groupe** (sac du joueur et sac d'UN porteur côte à côte, sélecteur si ≥2, une flèche par ligne transfère l'objet, grisée quand il ne rentre pas chez le destinataire). **Fiche objet dans les deux sacs** : icône + nom ouvrent `#item-detail-overlay` en mode **mono, sans comparaison** ; seule action offerte = le transfert.

**Fiche d'un compagnon = le MÊME `#sheet-panel`, en « mode compagnon »** (`openCompagnonSheet`/`closeCompagnonSheet`) : les globales du joueur sont mises de côté, remplacées par le payload de `GET /api/groupe/compagnon/{id}`, et **toutes les fonctions de rendu existantes sont rappelées telles quelles** (zéro duplication). Onglets 📜/🤝/📖 masqués. ⚠️ `_objetsAuSol` n'est **PAS** snapshotté : le sol appartient au LIEU. Silhouette du paperdoll rendue 100 % client depuis les globales race/sexe.

**Fiche = source unique `utils/fiche.py`** (`bloc_fiche`, `derived_de`, `stat_caps`, `race_de`) : le contenu des onglets Stats et ⚡ est bâti une seule fois, consommé par `/play` ET par la fiche de compagnon.

**Transfert** : logique pure `recrutement.transferer_ref` + `peut_porter` (adressage index + item_id, refus avant de retirer, 409 si charge dépassée — rien ne tombe au sol, contrairement au pickup), couverte par `tests/test_groupe.py`.


### Compagnie permanente — engagement durable d'un compagnon
Au-delà d'`AFFINITE_SEUIL_ENGAGEMENT`, un compagnon cesse d'être un contrat : il renonce à sa part de butin, sort du plafond de groupe, et rejoint la COMPAGNIE du joueur (bouton du panneau 👥, pas de tirage). État `av["permanent"] = True` + `character["compagnie"]`. XP partagée avec le principal (au lieu d'une part de butin) via `partager_xp`/`compagnie_effective`, appliquée aux quatre turn-in de quête et à l'XP de découverte de lieu/conclusion d'intro — **jamais en combat**, où tous les compagnons touchent l'XP pleine. Invariants (un permanent ne part jamais de lui-même, la compagnie garde son nom même sans membre, le plafond de groupe ne compte que les non-permanents) couverts par `tests/test_recrutement.py`.

**UI** : bouton `✦ Engager durablement` dans `renderGroupe` seulement (jamais dans le tableau de recrutement). Badge `✦ <compagnie>` à la place de « 💰 part 0% » dans le pied de carte. Overlay `#engagement-overlay` calqué sur `#clauses-overlay` (z-index au-dessus, fermé en premier dans la cascade Échap). ⚠️ La réponse d'engagement ne portant pas les inventaires, le client re-tire `GET /api/groupe`.


### Contrat d'UNE MISSION — le troisième mode de lien
Entre le contrat ordinaire (sans terme, part 10-30 %) et l'engagement durable (part nulle, hors plafond), le contrat d'une mission se signe **à la guilde**, se paie d'avance en cuivre contre une part de butin réduite, et s'achève de lui-même à la première quête rendue **dans une guilde**. Donnée `av["contrat"] = {"mode":"mission", part_butin_pct, cout_cuivre, signe_at, giver}` — mutuellement exclusif avec `permanent` (invariant testé). `recrutement.lieu_de_guilde` reconnaît les quatre lieux d'une maison de guilde. Termes (`offre_mission`), part effective, clôture (`cloturer_contrats_mission`, sans delta d'affinité) aux quatre sites de turn-in, reprise (`peut_reprendre`/`reprendre`, contrat neuf et non prolongé) et rupture (gratuite à la guilde) sont couverts par `tests/test_recrutement.py`, `tests/test_recrutement_endpoints.py` et `tests/test_quetes_endpoints.py`.

**UI** (`play_town_telluris.html`) : global Jinja `LIEU_DE_GUILDE` pilote libellés et grisage (la garde reste le 403/409 serveur). Dialogue d'embauche (`openClauses`) dédouble l'accord (mission vs sans terme), grisé si la bourse ne suit pas. Pied de carte : `📜 mission — part X %`. Rupture : `congedierAventurier` a trois `confirm()`, dont un qui prévient que rompre loin de la guilde coûte quelque chose. Pop-up de fin : overlay `#contrat-overlay` (z-index 9460, ✕/Échap/backdrop = laisser partir, correct ici car le contrat est déjà clos côté serveur), file d'attente `_contratsEchusFile` pour plusieurs échéances simultanées.


### Montures de transport (étables)
Premier moyen de transport de charge au-delà de la Force et des compagnons. Une étable vend des montures (`montures.lieu_vend_montures`). Logique pure `utils/montures.py`, router `routers/montures.py`. Doc `monture:*` = MIROIR du character (comme `aventurier:*`), type distinct → jamais ramassé par les boucles de recrutement ; les tags d'espèce (proie/prédateur) ne sont **pas** recopiés sur le doc. Charge multipliée (`charge_max_porteur`, relue à chaud sur le doc espèce), groupe séparé (`character["montures"]`, plafond `MONTURE_GROUPE_MAX`), et le comportement en combat — ciblable mais jamais jouable (`jouable:False`, hors `ordre_initiative` **et** hors `_combattants_vivants`, sans quoi une bête indemne empêcherait la défaite), mort définitive versant sa cargaison au sol du principal **quelle que soit l'issue du combat** — sont couverts par `tests/test_montures.py` et `tests/test_combat_montures.py`.

**UI** : bouton sidebar `🐴 Montures` (`est_etable`) → `#montures-panel` (offres en lignes, pas en cartes). Panneau 👥 : les montures ferment la marche sous un sous-titre `🐴 Montures`, cartes non éditables et non cliquables. Jeton de combat `.ally-token.monture` (anneau ocre).


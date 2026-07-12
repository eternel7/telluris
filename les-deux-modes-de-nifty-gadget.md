# Recrutement d'aventuriers + combat de groupe (mode opportuniste)

## Contexte

Le joueur doit pouvoir composer un groupe d'aventuriers PNJ et **jouer tous les personnages du groupe** en combat. Deux modes prévus à terme : **opportuniste** (quête-à-quête, payé en part de butin — **ce plan**) et **compagnie permanente** (salaires — phase 2, différée ; le plan ne doit pas la rendre impossible). Les recrues sont listées à la guilde d'aventuriers et potentiellement ailleurs (tag lieu `"recrutement"` + objet optionnel `recrutement_restrictions`). L'offre dépend de la `sous_categorie` du `lieu_parent` (cité) via une table world-var. Les liens formés (affinités) sont mémorisés et influencent les disponibilités futures.

### Décisions de design actées (utilisateur)
- **Périmètre v1** : tableau de recrues + embauche + exigences + affinités + **combat de groupe complet** (serveur + client). Compagnie/salaires différés.
- **Modèle recrue = doc `aventurier:*` miroir du character** → `build_joueur_snapshot` et `compute_derived_stats` marchent dessus tels quels.
- **Taille de ville** = `sous_categorie` du lieu_parent (valeurs réelles : `"capitale"` Lutecia, `"ville"` Auxerre/Rhemi) mappée par une table dans les world-vars (+ entrée `defaut`).
- **Exigences v1** : part de butin **affichée ET prélevée** ; clauses de conduite = données affichées, sans détection de violation.
- **Contrat** : dure **jusqu'au congédiement** (+ départ de lui-même si affinité < seuil). Pas de durée, pas de lien à une quête précise.
- **0 PV compagnon = KO seulement** (relève à 1 PV en fin de combat + malus d'affinité). Jamais de mort définitive.
- **Assiette de la part** : % prélevé sur le **cuivre des récompenses de quête** au turn-in. Le butin ramassé en combat par un compagnon va déjà dans SON sac.
- **Accès** : tableau visible seulement avec la **carte d'aventurier de la cité** en sac (`RECRUTEMENT_CARTE_REQUISE`, désactivable) ; **embauche gratuite**.

### État du code vérifié
- `utils/combat.py` : `build_joueur_snapshot(character, joueur_index=0)` (l.543) paramétré, snapshot porte `character_id` ; `_place_actors` (l.337) place déjà `joueurs[1:]` ; `resolve_action` agit sur le joueur **courant** via `_get_joueur` ; `ordre_initiative` = ids `joueur_N`. **Frictions** : `joueurs = [joueur]` en dur (l.731), IA monstre cible `joueurs[0]` (l.876, l.1090), défaite au 1er joueur KO (l.844-852), `finalize_combat` n'applique qu'au character principal (l.1790+), `combat_action` (routers/combat.py l.300-363) relit `combat_doc["character_id"]` pour consommer/sort/compétence.
- Client `combat_telluris.html` : ~35 lectures de `joueurs[0]` (caméra, prédicats, panneau Jinja) ; `activePlayer(data)` (l.885) résout déjà l'acteur courant mais est sous-utilisé ; le bandeau d'initiative Jinja (l.600-612) duplique des ids pour tout `joueur_*`.
- Les `pnj:*` n'ont aucune stat → le type `aventurier:*` est bien un type neuf. `character["affinites"]` (models/character_document.py) et `affinites_detail` (play_town l.1592) sont **inertes** — cette feature les active.
- Guilde réelle : `lieu:le_bastion_de_l_yonne_interieur` (`categorie:"guilde_aventurier"`, sans `tags`).
- 742 portraits `templates/resources/characters/`, nommage `{voc}_{sexe}_{race}NN.jpg` → génération de portrait par filtre de préfixe, zéro asset nouveau.
- Ground truth des champs character : `routers/user.py` `add_character` (l.100-252).

---

## 1. Doc `aventurier:*`

`_id: aventurier:<sub_guilde>_<uuid12>`, `type:"aventurier"`.

**Champs miroirs** (exactement ce que consomment `build_joueur_snapshot`, `sync_equipment_bonus`, `caracts_avec_buffs`, `compute_derived_stats`, `grant_xp`, `carried_weight`) : `prenom, nom, sex, race, voc, image, caracteristiques_current, currentPV, currentPM, vocations_niveaux, xp_total, attribute_points, inventaire, slots, equipment_bonus, sorts_connus, competences_connues, competences_bonus, effets_actifs, or/argent/cuivre (0), combats_recompenses`.

**Champs propres** : `statut: "offert"|"embauche"|"parti"`, `giver`, `lieu_parent`, `rang` (dérivé du niveau), `specialite` (blurb dérivé de la vocation), `exigences: {part_butin_pct, clauses:[str]}`, `genere_at`, `expire_at` (offert seulement), `embauche_par`, `embauche_at`.

**Génération procédurale** (pur, tout injecté) : race/sexe/vocation tirés sur `rules:races`/`rules:vocations` ; stats = base raciale + ~10 pts répartis (miroir du budget `bonusStats` d'`add_character`) + `RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU` pts par niveau ; niveau tiré dans `[0, niveau_max]` de l'offre du lieu (le tableau est partagé entre persos, comme les quêtes — pas calé sur le joueur) ; équipement = `equipement_de_base` de la vocation validé `resolve_item_ref` puis **équipé dans les `slots`** par un helper `_equiper_defaut` (mapping catégorie→slot ; indispensable, `_weapon_attacks` lit les slots) ; portrait = `choisir_portrait(voc, sex, race, portraits)` par préfixe avec replis ; prénom/nom = constantes de module par race ; PV/PM = max dérivé. `part_butin_pct` tiré dans `[MIN, MAX]` biaisé haut avec le rang ; `clauses` = 0-2 tirées d'une liste type du module.

**Extensibilité phase 2** : `exigences` reste un objet ouvert (`salaire_jour_cuivre` s'y ajoutera), `statut` extensible, règlement via chokepoint unique `regler_part_butin`.

## 2. Module pur `utils/recrutement.py` + `tests/test_recrutement.py`

Pattern `utils/transport.py` : logique pure, DB injectée, mute sans save (sauf remplissage du tableau, comme `quetes.remplir_tableau`). World-vars via `from models import character_stats` (jamais from-import).

- **Éligibilité lieu** : `lieu_recrute(lieu)` = `"recrutement" in tags` OU `categorie=="guilde_aventurier"` (le OU évite une migration bloquante ; le json d'import pose quand même le tag). `offre_du_lieu(lieu, parent)` = `RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE[parent.sous_categorie]` (repli `"defaut"`) surchargée champ à champ par `lieu.recrutement_restrictions` → `{nb, niveau_max}`. `acces_autorise(character, lieu, …)` : si `RECRUTEMENT_CARTE_REQUISE`, exiger en sac une réf `item:carte_aventurier` dont `item_ref_lieu == lieu_parent` du lieu.
- **Tableau** (miroir exact du board de quêtes, `utils/quetes.py` l.210-293) : `recrue_perimee` (statut `offert` seul), `purger_recrues_perimees` (doc SUPPRIMÉ), `recrues_du_giver`, `remplir_tableau_recrues` (purge paresseuse → complète jusqu'à `offre["nb"]` → **ré-offre** les anciens compagnons `parti` de ce giver dont l'affinité avec CE character ≥ `AFFINITE_SEUIL_REMISE` : c'est là que les liens mémorisés influencent la disponibilité), `_duree_de_vie_recrue` (durée jittée).
- **Groupe & embauche** : `character["groupe"]` = liste d'**ids** (l'état du compagnon vit sur SON doc). `groupe_effectif(character, get_doc)`, `taille_max_groupe()`, `conditions_effectives(av, affinite)` (part réduite de 1 pt par `AFFINITE_REDUC_PART` pts d'affinité au-dessus de 50, plancher MIN), `peut_embaucher` (statut offert, plafond), `embaucher` (statuts + `groupe` + memo `compagnons_connus` + `affinites.setdefault(id, AFFINITE_INITIALE)`), `congedier` (retire du groupe, statut `parti`, delta affinité aggravé si quêtes actives ; doc CONSERVÉ).
- **Affinités** : `ajuster_affinite` (clamp 0-100), `memoriser_liens_post_quete` (+`AFFINITE_DELTA_QUETE` par quête réussie ensemble), `affinites_detail_payload(character, get_doc)` → alimente enfin le bloc 👥 de play_town.
- **Règlement** : `regler_part_butin(character, groupe_docs, cuivre_total)` → `{parts:{av_id: cuivre}, reste}` ; crédite chaque av (`credit_character`), le reste au joueur. Chokepoint unique (phase 2 s'y branchera).
- `character["compagnons_connus"] : {av_id: {prenom, nom, voc, race, image, rang}}` borné (~30, pattern `combats_recompenses[-50:]`).

**Tests** (DB stub dict, miroir `test_quetes_board.py`) : génération (stats bornées, portrait cohérent, équipement en slots, PV=max), **test pivot** `build_joueur_snapshot(av_genere, 1)` valide, rotation (purge/complétion/ré-offre), éligibilité (tags/catégorie/restrictions/table), embauche/plafond/congédiement, parts (arrondis sol, plancher, réduction affinité), affinités (clamp, memo).

## 3. Router `routers/recrutement.py` (monté dans main.py comme `quetes_router`)

- `GET /api/recrutement/board` : lieu courant recrutable sinon 403 (miroir `_guild_lieu`) ; carte manquante → 403 explicite ; `remplir_tableau_recrues` → `{recrues:[vue], groupe:[vue], plafond, purse}`. Vue recrue = `{id, prenom, nom, race, voc, rang, niveau, specialite, image, exigences_effectives, affinite|None, deja_connu}`.
- `POST /api/recrutement/embaucher {aventurier_id}` : gratuit ; save character puis av_doc (best-effort, pattern acceptation de quête).
- `POST /api/recrutement/congedier {aventurier_id}` : autorisé partout (miroir `quetes_abandonner`).
- **Départ de lui-même** : check paresseux au board/`play` — compagnon dont l'affinité < `AFFINITE_SEUIL_DEPART` quitte le groupe (statut `parti`, toast).

## 4. Combat de groupe — serveur

1. **`create_combat_doc`** (utils/combat.py l.719) : param `compagnons: list[dict]|None` → `joueurs = [snapshot(character,0)] + [snapshot(c, i+1) …]`. Furtivité initiale sur `joueur_0` seul (v1). `_place_actors` et l'initiative gèrent déjà N.
2. **IA monstre** : helper `_cible_joueur(combat_doc, monstre)` = joueur vivant le plus proche (Chebyshev), furtifs non détectés exclus si autre cible ; `_do_monster_attack` prend la cible en param ; `_run_monster_turn` résout sa cible en début de tour et re-résout si KO en cours.
3. **Défaite = TOUS KO** : dans `_do_attack_on` (l.844-852), joueur à 0 → log « à terre », `defaite` seulement si `all(j.currentPV <= 0)`. `_resolve_until_player` saute les `joueur_*` KO ; garde défensive dans `resolve_action`. (`_occupied_set` exclut déjà les KO.)
4. **`finalize_combat`** : boucle sur `joueurs[]`, relit chaque `j["character_id"]`, **garde d'idempotence par-doc** (`combats_recompenses`), applique PV (KO→1)/PM/`grant_xp` (XP pleine chacun, v1)/`butin_ramasse`→sac de CE membre. Sur le principal seul : `maj_progress_kills`, focalisation, deltas d'affinité (`AFFINITE_DELTA_VICTOIRE` / `AFFINITE_DELTA_KO`, même doc que l'XP). Saves : compagnons d'abord, principal en dernier.
5. **`combat_action`** (routers/combat.py) : helper `_actor_character_id(combat_doc)` = `character_id` du joueur courant (repli principal) ; branches consommer/sort/competence chargent/sauvent CE doc — le compagnon boit SES potions, lance SES sorts. `collect_loot` : butin de victoire → sac du principal (v1).
- **`start_combat`** : `compagnons = recrutement.groupe_effectif(character, get_doc)` ; nb monstres +`len(compagnons)//2` (à équilibrer).
- **Nouveau `GET /api/combat/{id}/acteur`** : consommables/sorts/compétences/épinglés + portrait du doc du joueur courant (mêmes helpers, character-shaped). La page `/combat/{id}` (main.py) fournit `portraits_joueurs: {joueur_id: {image, largeur, hauteur}}`.
- **Fuir** : la fuite de l'acteur courant fait fuir tout le groupe (1 jet).
- Tests `tests/test_combat_groupe.py` (docs à la main, pattern `test_combat_ranged.py`, monkeypatch DB comme l'existant) : ciblage IA, défaite tous-KO, saut des KO, finalize multi-docs idempotent.

## 5. Combat de groupe — client (`combat_telluris.html`)

Principe : `const me = () => activePlayer(state)` et **tout ce qui lisait `state.joueurs[0]` lit `me()`**. Caméra centrée sur le **membre actif** (le monde re-pivote au changement d'acteur).

- Caméra/rendu : `facingDeg` (l.1013), `chebyToPlayer` (l.1019), `renderTokens` (l.1025), `updateCamera` (l.1058), `logClass` (l.1073).
- Prédicats (l.1112-1271 + `refreshBadgeTargets` l.977) : remplacer `joueurs[0]` par `me()` ; `cellOccupied` = tous les joueurs vivants.
- **Tokens alliés** : membres non actifs vivants rendus `.ally-token` (portrait via `portraits_joueurs`, mini-barre PV) aux coords relatives à `me().pos` ; le `.player-token` central affiche le portrait du membre actif (rendu JS, plus de `{% if combat.joueurs[0].image %}`). Alliés non ciblables en v1 (soin d'allié = extension différée).
- **Panneau gauche** : le Jinja `joueurs[0]` (l.501-525) reste comme rendu initial, piloté ensuite par `updateJoueur(me())` (déjà générique) + `applyPlayerPortrait` paramétré.
- **Bandeau d'initiative** : corriger la boucle Jinja (l.600-612) — résoudre chaque `joueur_*` par id (`selectattr`), ids DOM uniques par acteur ; `updateInitiativeStrip` gère anneaux + classe KO ; badge actif = indicateur de tour.
- **Hook changement d'acteur** : mémoriser `lastActorId` dans le re-rendu ; s'il change vers un `joueur_*` → `updateJoueur(me())`, portrait, `fetch /acteur` → remplace CONSOS/SORTS/COMPS/épinglés, re-rend `#quick-sorts`/`#quick-comps`.
- Overlay de fin : texte défaite « tout le groupe est à terre ».

## 6. UI `play_town_telluris.html` + turn-in

- **Panneau recrutement** : bouton sidebar (visible si flag contexte `est_recrutement` posé dans `/play`) → `#recrutement-panel` (clone structurel de `#quetes-panel` : `panel-frame board-panel`, AJAX board, rendu client). Carte recrue : portrait, nom, race·voc, rang, spécialité, **part effective + clauses**, badge affinité si connue, bouton Embaucher (désactivé + raison). Section « Votre groupe » avec Congédier.
- **Onglet 🤝 section 👥** : remplacer le bloc Jinja inerte (l.1606-1614) par `renderFicheCompagnons` (miroir `renderFicheRelations`), payload `affinites_detail` ajouté au contexte `/play` + resync après embaucher/congedier/retour de combat. Même échelle 0-100 neutre 50.
- **Turn-in** (`routers/quetes.py` `quetes_terminer`) : `regler_part_butin` sur le cuivre de la récompense + `memoriser_liens_post_quete` ; toast détaillant les parts. `quetes_abandonner` : petit malus d'affinité de groupe.

## 7. World-vars — nouveau groupe « Recrutement » (`CODE_DEFAULTS` + doc)

```
RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE = {"capitale":{"nb":6,"niveau_max":3},
    "ville":{"nb":4,"niveau_max":2}, "defaut":{"nb":2,"niveau_max":1}}
RECRUTEMENT_GROUPE_TAILLE_MAX = 2
RECRUTEMENT_BOARD_DUREE_SECONDES = 7200 ; RECRUTEMENT_BOARD_DUREE_JITTER = 0.5
RECRUTEMENT_PART_BUTIN_MIN = 10 ; RECRUTEMENT_PART_BUTIN_MAX = 30
RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU = 6
RECRUTEMENT_CARTE_REQUISE = True ; RECRUTEMENT_CAUTION_CUIVRE = 0   # porte phase 2
AFFINITE_INITIALE = 50 ; AFFINITE_DELTA_QUETE = 2 ; AFFINITE_DELTA_VICTOIRE = 1
AFFINITE_DELTA_KO = -5 ; AFFINITE_DELTA_CONGEDIE = -1 ; AFFINITE_DELTA_CONGEDIE_EN_QUETE = -3
AFFINITE_SEUIL_DEPART = 30 ; AFFINITE_SEUIL_REMISE = 60 ; AFFINITE_REDUC_PART = 10
```

## 8. Données / contenu

- `jsons/recrutement_a_importer.json` : `lieu:le_bastion_de_l_yonne_interieur` → `tags:["recrutement"]` (sans `recrutement_restrictions` = sans restriction).
- Aucun portrait/item nouveau. CLAUDE.md : section « Recrutement & combat de groupe » + world-vars, en fin d'implémentation.

## Fichiers

**Nouveaux** : `utils/recrutement.py`, `routers/recrutement.py`, `tests/test_recrutement.py`, `tests/test_combat_groupe.py`, `jsons/recrutement_a_importer.json`.
**Modifiés** : `utils/combat.py`, `routers/combat.py`, `routers/quetes.py` (turn-in), `main.py` (montage router, contexte /play et /combat), `models/character_stats.py` (world-vars), `templates/combat_telluris.html`, `templates/play_town_telluris.html`, `CLAUDE.md`.
**Réutilisés tels quels** : `build_joueur_snapshot`, `compute_derived_stats`, `sync_equipment_bonus`, `caracts_avec_buffs`, `credit_character`/`debit_character`, `resolve_item_ref`/`item_ref_lieu`, patterns board (`utils/quetes.py` l.210-293) et expiration paresseuse (`transport.traiter_expirations`).

⚠️ Indentation en **tabulations** partout (convention du repo).

## Ordre d'implémentation (étapes testables)

1. **E1** — World-vars + `utils/recrutement.py` (génération, tableau, éligibilité) + tests. Pivot : `build_joueur_snapshot(av, 1)` valide.
2. **E2** — Groupe/embauche/parts/affinités purs + tests.
3. **E3** — Combat serveur multi (frictions 1-4) + `tests/test_combat_groupe.py`.
4. **E4** — Routers : `recrutement.py`, `start_combat` groupe, `combat_action` par acteur, `/acteur`, turn-in parts + liens.
5. **E5** — Client combat (`me()`, tokens alliés, bandeau, panneau, hook acteur).
6. **E6** — UI play_town (panneau recrutement, onglet 👥, resyncs).
7. **E7** — Json d'import + CLAUDE.md.

## Vérification

- `pytest tests/test_recrutement.py tests/test_combat_groupe.py` à chaque étape ; suite complète `pytest tests/` (5 échecs pré-existants connus `test_character_stats.py`, hors périmètre).
- En jeu (docker côté utilisateur) : import json → tableau visible à la guilde **seulement avec la carte** → embauche de 2 recrues (plafond respecté) → combat : 3 badges joueurs, caméra pivotant par acteur, compagnon consommant SA potion, KO d'un compagnon **sans** défaite, défaite seulement tous à terre → victoire : XP/PV sur les 3 docs (`/admin/table` type `aventurier`) → turn-in : parts prélevées, affinité +2 dans l'onglet 🤝 → congédiement → ré-offre au tableau une fois l'affinité ≥ seuil.

# Telluris — CouchDB document schema

Derived from `jsons/telluris-dump-20260906-081358.json` (2,440 docs, all types) by field-frequency
analysis, cross-checked against `utils/*.py` and `routers/*.py` for wiring. Percentages below are
observed presence across all docs of that type in this dump, not a formal schema — a field at
<100% may still be "required" if it was only added by a later code path (noted where relevant).
Convention (`models/character_document.py` is a stale reference only — creation code in
`routers/user.py` is truth): `_id` = `type:identifier`, except two documented exceptions below.

FK notation: `field -> Type` means the field's string value is another doc's `_id` (or, for
sub-category/name keys, is used to look one up).

---

## Content docs (author-imported, rarely mutated at runtime)

### `item` (924)
`_id: item:<Nom_Libre>` (human slug, not uuid; also used as inventory-ref default id).
- **Required**: `categorie`, `icon`, `nom`, `sous_categorie` (often `""`), `type`.
- **Optional**: `rarete` (93%), `poids` number-or-`[min,max]` (77%), `description` (55%),
  `tags[]` (40%), `slots[]` (27%, equip slots this item fills), `loot_defaut` bool (15%),
  `portee`/`bonus_pa`/`bonus_degats`/`bonus_degats_dice`/`bonus_cc`/`bonus_cd`/`bonus_pm`/`bonus_pv`/
  `bonus_initiative`/`bonus_malus_depl` (weapon/armor stat bonuses, 2-11%), `bonus.<Caract>` (worn
  buff, 1-4%), `deux_mains` bool (4%), `restriction.<Caract>` min-to-equip (1-6%),
  `effets.{buffs,duree,pv,pm,regen_pv,regen_pm}` + top-level `cible` (durative effect carried by a
  weapon — non-equippable "instant" items reuse the same `effets` shape), `valeur[]` (`{ag|cu|or}`,
  base sell value, 7%), `sorts[]` FK->`sort` (grimoire item, 7%), `carte.{dimensions,image,
  image_route,lieu_nom,position}` (a written/copied map — Scriptorium output, 2%).
- **Depeçage-only fields** (10%, on a carcass/"partie" item): `partie`, `portion_de -> item`
  (parent creature item), `depecage[][]` (loot tag matrix), `decoupe[].{item -> item,fraction,
  quantite}` + `decoupe_poids_min` (woodcutting-style splitting).
- **FK**: `source_espece -> espece` (24%, which creature this carcass/part comes from),
  `sorts[] -> sort`, `portion_de`/`decoupe[].item -> item` (self-referential).

### `recette` (498)
`_id: recette:<uuid>`.
- **Required**: `lieu_categorie`, `objet_final` (sous-catégorie key, not an `item:` id — resolved via
  `matiere_item_id`), `quantite_produite`, `type`.
- **Optional, two mutually-exclusive input shapes**: list form `matieres_premieres[].{item ->
  item (32%) | sous_categorie (58%), quantite}` (82% of recettes), or legacy single-entry form
  `matiere_premiere_sous_categorie` + `quantite_matiere` (18%) — both read by `utils/marche.py`.
- **FK**: `matieres_premieres[].item -> item`.

### `espece` (139)
`_id: espece:<slug>`.
- **Required**: `base_attributes.<Caract>.{min,max}` (all 7 stats + V), `description`, `image`,
  `nom`, `tags[]`, `type`.
- **Optional**: `proprietes.charge_mult` (mount carry multiplier, 14%), `proprietes.prix_cuivre`
  (mount base price, 14%).
- **FK**: none outward; referenced by `monture.espece`, `item.source_espece`,
  `donjon.battle_maps[].especes[]`, `zone_influence.table_evenements[]` (via species tags), quest
  `objectif.cible`.

### `profil` (16)
`_id: profil:<slug>`. Modulates an `espece` roll (monster grade).
- **Required**: `attributs_modifier.<Caract>.{min,max}` (delta added to espece range; `V` at 94%),
  `description`, `niveau`, `nom`, `type`.
- **Optional**: `restriction_tags[]` (62% — gates which species this profil may roll onto; consumed
  by `chasse.resoudre_profil_chasse`).

### `sort` (61) / `competence` (38)
`_id: sort:<slug>` / `competence:<slug>`. Same `effets` shape as items/consommables.
- **`sort` required**: `cible`, `composants[].{item -> item, consomme}`, `cout_pm`, `description`,
  `icon`, `magie` (school), `niveau`, `nom`, `portee`, `type`, `vocation`.
- **`competence` required**: `description`, `icon`, `mode` (`passive`/active), `niveau`, `nom`,
  `type`, `vocation`. Active-only: `cible`, `cout_pm`, `portee` (42%).
- **Both, optional**: `effets.{buffs.<Caract>,degats,pv,pm,regen_pv,regen_pm,esquive,furtivite,
  duree}`, `jet` (`cc`/`cd`/`magique`, 10-21%), `animation -> animation` (2-5%), `condition` (fires
  only in dialogue context — wired, `utils/{sorts,competences}.py`), `composants[].bonus.*`
  (catalyst variant of the same effect, sort only).

### `animation` (198)
`_id: animation:<slug>`.
- **Required**: `actif` bool, `nom`, `type`.
- **Optional** (92% — the ~8% without are stub/unconfigured scans): `ancrage`, `colonnes`/`lignes`,
  `debut`/`fin` (frame range), `decalage_y`, `duree_ms`, `echelle`, `fichier`, `hauteur`/`largeur`,
  `sens_lignes`/`sens_colonnes`. Trajectory sub-set (2-4%): `arc`, `decalage_x`,
  `depart_ancrage`/`depart_decalage_x/y`, `duree_trajet_ms`, `rotation`, `rotation_auto`. Sound
  sub-set (10%): `son`, `son_debut_ms`, `son_fin_ms`, `son_volume`.

### `donjon` (2)
`_id: donjon:<slug>`.
- **Required**: `battle_maps[].{especes[] -> espece, lieu -> lieu}`, `description`, `niveau_max`,
  `nom`, `portail -> lieu`, `type`.
- **Optional**: `battle_maps[].{nb_monstres,niveau_max,niveau_min}` (per-room override).

### `zone_influence` (80)
`_id: zone::<slug>` — **naming exception**: prefix is `zone` (not the `type` value
`zone_influence`) and uses a doubled colon; hardcoded in `routers/zones.py`
(`zone_id.startswith("zone::")`) and `db/config.py`'s cache-prefix list, so not a typo.
- **Required**: `intensite_max`, `modificateurs.{danger,visibilite}`, `nom`,
  `table_evenements[].{poids,tags[],type}`, `terrain_tags[]`, `type`.
- **Optional**: `modificateurs.{deplacement (65%), reputation (14%), prix (11%),
  acces_restreint (2%), moral (1%)}`.
- ⚠️ **Unwired**: `resolve_zone_event` (`utils/zones.py`) additively merges *all*
  `modificateurs.*` keys into the event payload, but only `modificateurs.danger` is ever read
  downstream (`utils/escorte.py`, for progeniture rendezvous placement). `visibilite`,
  `deplacement`, `reputation`, `prix`, `acces_restreint` and `moral` are computed and then
  dropped by every caller — data with no gameplay effect yet.
- Also per `zone_influence.table_evenements[].type`: CLAUDE.md documents only `combat`
  and `ressource` as consumed; `pnj`/`ambiance`/`quete`/`commerce`/`malus`/`tresor`/`meteo`/
  `piege`/`rien` are intentional dead-weight kept for tirage-pondéré dilution (not a bug — do not
  "fix").

### `connection` (104, `type: connection`)
`_id: link:<slugA>_to_<slugB>` — same prefix-≠-type exception as `zone_influence`.
- **Required**: `metadata.{status,type}`, `nodes[].{lieu -> lieu, pos: [x,y]}` (exactly 2 nodes),
  `type`.
- **Optional**: `nodes[].label` (12% — display override for the destination name, read by
  `utils/lieux.py`).

### `pnj` (41)
`_id: pnj:<slug>` (generic `pnj:marchand_<categorie>` for shopkeepers, named otherwise).
- **Required**: `dialogue.noeud_depart`, `dialogue.noeuds.<id>.{choix[]}` (arbitrary node graph —
  linted by `utils/lint_dialogues.py`), `nom`, `portrait`, `race`, `type`, `vocation`.
- **Optional**: `description` (27%), `services.<kind>` where `kind ∈ {soin, don, acces, rang,
  commission, transport, escorte}`, each with its own sub-shape (see CLAUDE.md "PNJ de lieu" /
  "Accès conditionné" / quest-family sections — all confirmed wired). Dialogue node extras:
  `relation{cle,delta,lieu,unique}`, `relation_reinit`, `delai_min`/`noeud_attente`.
- **FK**: `services.acces.lieu/gardien -> lieu/pnj`, `services.commission.donjon -> donjon`,
  `services.escorte.offre.id -> quete`, `services.*.offre.destination/rencontre.lieu -> lieu`.

### `rules` (5 — singleton config docs, not a repeating type)
All share `_id: rules:<name>`, `type: "rules"`, and wrap their real payload in one `value` field.
- `rules:races` — `value[]` of `{id, label, icon, stats, stats_max, max_bonus, trait}`.
- `rules:races_proximity` / `rules:vocations_proximity` — `value{<id>: [<related ids>]}`.
- `rules:vocations` — `value[]` of `{id, label, icon, img, magie, blurb, equipement_de_base[]}`.
- `rules:world_variables` — `value{<VAR_NAME>: <value>}`, ~116 keys; see CLAUDE.md "Variables de
  monde réglables" (now in `.claude/skills/telluris-admin-tools/`) for the full catalogue.
- ⚠️ **Stale doc reference, not a live field**: CLAUDE.md's "Character document vs. Pydantic
  model" note names `caracteristiques_standard` as a real (if divergent) field. It appears in
  **zero** of the 2,440 docs and **zero** `.py`/`.html` files — only `caracteristiques_current`
  exists anywhere in code or data. Treat that CLAUDE.md line as outdated.

---

## Player / world state docs (mutated at runtime)

### `character` (11)
`_id: character:<user_id>_<uuid>`. Same core shape as `aventurier`/`monture`/`protege` (creation
code in `routers/user.py` is the source of truth, not `models/character_document.py`).
- **Required**: `argent`,`attribute_points`,`caracteristiques_current.<Caract>`,`cite -> lieu`,
  `cuivre`,`currentPM`,`currentPV`,`image`,`lieu -> lieu`,`lieux_visites[] -> lieu`,`nom`,`or`,
  `prenom`,`race`,`sex`,`slots.<emplacement> -> item|null` (12 slots incl. `epaules` — wired, cf.
  equipment_bonus.pa_zones.epaules and SLOT_LABELS),`type`,`voc`,`xp_total`.
- **Optional**: `combats_recompenses[] -> combat` (idempotency guard), `inventaire[]` (string ref
  or `{item,poids}`), `competences_connues[]/sorts_connus[]/sorts_epingles[] -> competence/sort`,
  `groupe[] -> aventurier`, `montures[] -> monture`, `proteges[] -> protege`, `slots_actions[]`,
  `quetes_actives[]/quetes_terminees[] -> quete` (embedded snapshot, not a live FK read-back),
  `focalisation.{type,cible,posee_at}`, `pnj_present.{character -> pnj, lieu -> lieu}`,
  `transport_offert`/`escorte_offerte`/`ressource_recoltable`/`objets_au_sol` (transient, tirés à
  l'entrée), `max_bonus_used`, `rang`, `compagnie.{nom,fondee_at}`, `vocations_niveaux.<voc>`,
  `dialogues_relations.<pnj_id>:<flag>`, `compagnons_connus.<aventurier_id>.*` (denormalized cache
  for the roster UI), `portrait_zoom`/`portrait_translate.{x,y}`, `equipment_bonus.*`/
  `competences_bonus.*` (denormalized, rebuilt by `sync_equipment_bonus`, never hand-edited).

### `aventurier` (17) / `monture` (5) / `protege` (16)
Mirror-of-`character` docs for companions / mounts / escortees (same combat snapshot code path).
`_id`: `aventurier:<lieu_slug>_<hex12>`, `monture:<slug>_<hex12>`, `protege:<hex16>`.
- All three: `caracteristiques_current`, `currentPV/PM`, `equipment_bonus.*`, `image`, `nom`,
  `statut`, `type`. `giver -> lieu`, `lieu_parent -> lieu`.
- `aventurier`-only: `slots.*`, `voc`, `rang` (76%), `exigences.{part_butin_pct,clauses[]}` (paid
  contract), `embauche_at`/`embauche_par -> character`, `permanent` bool (18% — compagnie),
  `contrat.{mode,part_butin_pct,cout_cuivre,signe_at,giver}` (mission contract — mutually
  exclusive with `permanent`, per CLAUDE.md invariant), `competences_bonus.*`,
  `vocations_niveaux.<voc>`.
- `monture`-only: `acquise_at`,`acquise_par -> character`,`jouable:false`,`espece -> espece`.
- `protege`-only: `prenom`,`race`,`sex`,`escorte_at`,`quete -> quete`,`jouable:false`.

### `relation` (165)
`_id: relation:<character_id>::<lieu_id>` (both halves are full ids, not shortened).
- **Required**: `character_id -> character`, `lieu_id -> lieu`, `marchandage_bloque_jusqu`
  (epoch, 0 = not blocked), `value` (0-100), `type`.
- **Optional**: `fidelite_transactions` (16%), `prix_negocies.<item_id>.{achat|vente}.frac` (16%,
  4/165 docs but many keys each — per-item negotiated price fraction).

### `quete` (7 sampled; ids vary by source)
`_id`: authored → free slug (`quete:bastion_authoree_exemple`); generated → `quete:<lieu_slug>_
<hex12>` or `quete:<family>_<hex>` (`transport_…`) or `quete:escorte_progeniture_<lieu>_<nom>`
(progeniture — same id from both the parent-shop and guild-board channels, by design).
- **Required**: `description`,`giver -> lieu`,`lieu_parent -> lieu`,`objectif.{cible,quantite,
  type}` (`cible` is an `espece`/`item`/`lieu` id depending on `objectif.type`),`rang`,
  `recompenses.{cuivre,xp}`,`source` (`authoree`/`rang`/generated-family),`statut`,`titre`,`type`.
- **Optional**: `expire_at`/`genere_at` (86% — board rotation), `accepte_par -> character`.

### `lieu` (99)
`_id: lieu:<slug>`. Widest doc in the game — content template AND live mutable market/access
state on the same doc.
- **Required**: `categorie`, `image`, `label` (only display-name field — never `nom`/
  `description`; `characters.lieu_label` is the one place that derives a fallback), `type`.
- **Grid lieus only** (9%, `dimensions` present ⇒ playable map): `dimensions.{x,y}`,
  `cells[][]`, `nav.<x>,<y>` (bitmask, sparse — absent cell = fully open).
- **Optional, market/shop**: `lieu_parent -> lieu`, `sous_categorie`, `stock_vente[].{item_id ->
  item, qty}`, `stock_matieres.<sous_categorie|item_id>` (qty, keyed dynamically),
  `stock_cible.{item.<item_id>|sous_categorie.<sc>|categorie.<cat>}` (target restock level —
  wired, `utils/marche.py:stock_cible_pour`), `relation_lieu -> lieu` (delegate reputation to
  another lieu), `pnj[].{character -> pnj, portrait, nom, description, probabilite, conditions,
  montures[]}`.
- ⚠️ **`pnj[].montures[]`** (3%, e.g. `espece:ane` on a mounted paladin entry) is never read by
  `utils/pnj.py` or anywhere else — looks like an intended "arrives mounted" visual that was
  authored but never wired into `pnj_payload`/rendering.
- **Optional, other systems**: `zone_influences[].{zone -> zone_influence,forme,x,y,w,h,rot}`,
  `ressources[].{ressource -> item,zones[]}`, `rencontres[].{espece -> espece,zones[]}`,
  `profil_weights.<profil_id>` (weight), `acces.{gardien -> pnj,refus,cycle,conditions[]}` (5
  condition kinds — see CLAUDE.md "Accès conditionné"), `intro.{titre,texte,texte_conclusion,
  raisons[],xp_conclusion,zone_securite -> zone_influence}` (city-of-origin doc only), `texte`
  (PNJ-less flavor text), `tags[]`.

### `message` (2)
`_id: message:<hex16>`.
- **Required**: `auteur -> character|aventurier` (companion writer), `auteur_image`,`auteur_nom`,
  `auteur_translate.{x,y}`,`auteur_zoom`,`cree_at`,`lieu -> lieu`,`support` (`table`/`tableau`),
  `texte`,`type`. No `expire_at` on tableau messages (they never expire, by design); table
  messages carry one via `AUBERGE_MESSAGE_DUREE_SECONDES` at write time (not present in this
  sample, both docs being tableau notices).

### `combat` (1 — ephemeral, deleted/rotated; do not treat as content schema)
`_id: combat:<hex32>`. Full battle snapshot: `joueurs[]`/`monstres[]` (stats + `attaque_profils[]`
+ `equipment_bonus.*`, denormalized at combat start and frozen), `ordre_initiative`,
`battle_map_id -> lieu`, `log[].{acteur,kind,texte,tour,etat.<acteur_id>.*,vfx}` (deferred-reveal
state snapshots, cf. CLAUDE.md "Révélation différée").

---

## Summary of flagged unwired mechanisms

| Field(s) | Type | Status |
|---|---|---|
| `modificateurs.{visibilite,deplacement,reputation,prix,moral,acces_restreint}` | `zone_influence` | Merged by `resolve_zone_event`, never read past that — only `danger` has a consumer. |
| `pnj[].montures[]` | `lieu` | Authored on 3 lieus, never read by `utils/pnj.py`. |
| `caracteristiques_standard` | (documented in CLAUDE.md only) | Doesn't exist in any of 2,440 docs or in any `.py`/`.html` file — stale doc, not live schema. |
| `table_evenements[].type` values other than `combat`/`ressource` | `zone_influence` | Intentional dilution weight, not a bug — flagged in CLAUDE.md already, listed here for completeness. |

Everything else cross-checked while writing this doc (`epaules` slot, `stock_cible`, `deux_mains`,
`condition` on sort/competence, `charge_mult`, recette's dual matiere-input shapes, connection
node `label`) is actively read by engine code.

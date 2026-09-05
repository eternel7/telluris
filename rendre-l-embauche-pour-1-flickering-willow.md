# Embauche pour UNE MISSION — contrat court à la guilde

## Context

Le recrutement n'offre aujourd'hui que **deux** liens, tous deux sans terme : le **contrat
ordinaire** (gratuit, part de butin 10–30 %, rompu par un congédiement qui froisse) et
l'**engagement durable** (part nulle, hors plafond, `permanent: True` sur le doc du compagnon).
Rien entre les deux : le joueur qui veut une lame de plus **pour une seule quête** doit
embaucher sans terme puis congédier, ce qui lui coûte de l'affinité alors qu'il n'a rien trahi.

On ajoute un **troisième mode : le contrat d'UNE MISSION**, signé à la guilde d'aventuriers.
Il se paie **d'avance, en cuivre**, contre une **part de butin plus faible** ; il **s'achève de
lui-même** à la prochaine quête rendue dans une guilde, par un pop-up qui prévient et propose
de le **reprendre pour une mission de plus** (en repayant). Il se rompt **sans frais** à la
guilde, avec le malus habituel ailleurs. Toute rupture passe par une confirmation.

Décisions tranchées avec l'utilisateur :
1. Renvoi hors guilde = **affinité seule** (deltas existants) ; aucune réputation de lieu en jeu.
2. Renvoi gratuit à la guilde = **contrats d'une mission SEULEMENT** (l'ordinaire garde son
   malus partout, le permanent garde son −15 partout : ce n'est pas un contrat qui s'achève).
3. Fin de contrat = **littérale** : contrôle au turn-in, déclenchée si le rendu se fait **dans
   une guilde**. Une escorte déposée ailleurs ne rompt rien — le contrat court jusqu'au
   prochain rendu en guilde.
4. Part réduite = **facteur sur la part normale**, plancher propre, affinité toujours déductible.

Aucune migration : `contrat` absent ⇒ comportement d'avant à la lettre.

---

## 1. Données — `av["contrat"]`, jumeau de `permanent`

Nouveau champ sur le doc `aventurier:*`, exactement le précédent de `permanent` (l'état du
lien vit sur le doc du compagnon, pas sur celui du joueur) :

```python
av["contrat"] = {"mode": "mission", "part_butin_pct": 12, "cout_cuivre": 700,
                 "signe_at": epoch, "giver": "lieu:…"}
```

⚠️ **`permanent` et `contrat` sont MUTUELLEMENT EXCLUSIFS**, et c'est cet invariant qui rend
sûr le câblage de `routers/pnj.py` (§4) : `_sauver_compagnie` n'y sauve que des **permanents**,
la clôture des contrats que des **non-permanents** — deux ensembles disjoints, donc jamais deux
dicts du même document. À tenir en trois points, sur le modèle du `av.pop("permanent")` déjà
présent dans `embaucher` :
- `embaucher(..., contrat=None)` → **`av.pop("contrat", None)`** quand aucun contrat n'est passé
  (une ré-embauche ordinaire ne doit pas hériter d'un contrat périmé — miroir exact du filet
  `permanent` de `utils/recrutement.py:891`) ;
- `engager_permanent` → `av.pop("contrat", None)` ;
- `congedier` → `av.pop("contrat", None)`.

`cloturer_contrats_mission` (§3), elle, **CONSERVE** le bloc : c'est lui qui porte le prix de
la reprise. Elle n'y ajoute qu'un `echu_at`.

---

## 2. `utils/recrutement.py` — module pur

### `lieu_de_guilde(lieu_doc) -> bool` — source unique
La maison de guilde est éclatée en quatre lieux aux `categorie` différentes (dump : réception
`guilde_aventurier`, comptoir `guilde_aventurier_comptoir`, façade `guilde_aventurier_exterieur`,
bureau du maître **`bureau_maitre_guilde`** — ce dernier sans `sous_categorie`). Aucun prédicat
existant ne les couvre tous : `lieu_recrute` rate le comptoir et le bureau,
`quetes.lieux_solidaires` rate la façade et le bureau (pas de `sous_categorie`).

Idiome repris de `lieu_recrute` (tag OU catégorie, pour qu'une faction future s'y branche sans
une ligne de code) :

```python
GUILDE_SOUS_CATEGORIE = "guilde_aventurier"
GUILDE_CATEGORIES = ("guilde_aventurier", "guilde_aventurier_comptoir",
                     "guilde_aventurier_exterieur", "bureau_maitre_guilde")

def lieu_de_guilde(lieu_doc) -> bool:
    d = lieu_doc or {}
    return ("guilde" in (d.get("tags") or [])
            or d.get("sous_categorie") == GUILDE_SOUS_CATEGORIE
            or d.get("categorie") in GUILDE_CATEGORIES)
```
⚠️ **Ne PAS toucher `categorie`/`sous_categorie` dans la donnée** : celle du bureau est lue par
les blocs `acces` de la mine et du temple-portail (`quete_active.giver_categorie`).

### `offre_mission(av) -> dict` — les termes proposés
```python
{"cout_cuivre": BASE + PAR_NIVEAU * niveau, "part_butin_pct": max(MIN, round(part * FACTEUR))}
```
`niveau` = `character_stats.compute_character_level(av.get("xp_total", 0))` (le module est déjà
importé — on lit **par le module**, jamais par un `from … import`). `part` = la part **BRUTE**
de `av["exigences"]["part_butin_pct"]`, jamais la part déjà réduite par l'affinité : la
réduction reste appliquée une seule fois, au règlement.

### `conditions_effectives(av, affinite)` — une branche de plus
Ordre : **permanent d'abord** (sortie immédiate à 0, inchangé), puis contrat de mission, puis
ordinaire. Le contrat fournit sa base **et son plancher** :
```python
contrat = av.get("contrat") or {}
if contrat.get("mode") == "mission":
    base, plancher = int(contrat.get("part_butin_pct", 0) or 0), MISSION_PART_MIN
else:
    base, plancher = int(exigences.get("part_butin_pct", PART_BUTIN_MIN) or 0), PART_BUTIN_MIN
part = max(plancher, base - reduc)
```
Le dict renvoyé gagne **`"mode"`** (`"mission"` ou `""`). Il a **quatre lecteurs**
(`regler_part_butin:1095`, `affinites_detail_payload:1070`, `_recrue_view:97`,
`groupe_compagnon:447`) : la clé s'y propage sans autre édition, `regler_part_butin` paie donc
la part réduite sans être modifiée.

### `_attacher(character, av, contrat=None)` — extrait du corps d'`embaucher`
La mutation du lien (statuts, groupe, affinité, `memo_compagnon`, `pop` de `permanent`/`contrat`)
devient une fonction privée. **Deux appelants** : `embaucher` (garde `peut_embaucher`, statut
`offert`) et `reprendre` (garde `peut_reprendre`, statut `parti`) — un seul endroit écrit le
lien. `embaucher(character, av, get_doc_fn=None, contrat=None)` : le paramètre est optionnel,
les appelants existants sont inchangés.

### `peut_reprendre(character, av, get_doc_fn=None) -> (bool, str)`
Statut `parti` **ET** `av["embauche_par"] == character["_id"]` (seule preuve du lien passé, un
doc `aventurier:*` n'ayant pas de `user_id`) **ET** `contrat.mode == "mission"` **ET** groupe
sous le plafond (`places_occupees`).
⚠️ Cas limite assumé : si le tableau l'a **re-proposé** entre-temps (`remplir_tableau_recrues`
ré-offre les anciens compagnons à affinité ≥ `AFFINITE_SEUIL_REMISE`), son statut est repassé à
`offert` et la reprise répond 409 — le joueur le ré-embauche alors par le tableau.

### `cloturer_contrats_mission(character, lieu_doc, compagnons=None, get_doc_fn=None) -> list`
Chokepoint UNIQUE de la fin de mission. Miroir de `partager_xp` pour le passage des docs :
`compagnons` = les docs **déjà chargés par l'appelant**, à repasser ; `None` ⇒ chargés ici via
`groupe_effectif` (ils ne sont alors mutés que par nous).
- `lieu_de_guilde(lieu_doc)` faux ⇒ `[]`, rien n'est muté ;
- sinon, pour chaque compagnon actif à `contrat.mode == "mission"` : retrait de
  `character["groupe"]`, `statut = "parti"`, `contrat["echu_at"] = now_epoch()`,
  **AUCUN delta d'affinité** (le contrat a été honoré, personne n'est froissé) ;
- renvoie les docs libérés. **Mute sans sauver** — l'appelant persiste **après** son
  `save_doc(character)` autoritatif.
Idempotente : un second appel ne trouve plus personne dans le groupe.

### `vue_contrat_echu(av) -> dict`
`{id, prenom, nom, image, specialite, cout_cuivre, part_butin_pct}` — juste ce qu'il faut au
pop-up, qui est bâti sur le modèle du `#clauses-overlay` (portrait + réplique + choix) et non
sur une carte de personnage. Pure, dans `utils/` : aucun import croisé entre routers.

### `congedier(character, av, lieu_doc=None)`
Un paramètre optionnel (appelants existants inchangés) ; le prédicat reste dans le module pur :
```python
if av.pop("permanent", None):           delta = AFFINITE_DELTA_CONGEDIE_PERMANENT
elif mission and lieu_de_guilde(lieu_doc):  delta = 0    # le contrat s'achève dans les règles
else:                                   delta = _EN_QUETE si quêtes actives sinon _CONGEDIE
av.pop("contrat", None)
```

---

## 3. `models/character_stats.py` — quatre variables de monde

Déclaration près de `RECRUTEMENT_CAUTION_CUIVRE` (`:372`, qui **reste inerte** — « caution » et
« prix d'une mission » sont deux notions, la renommer en silence tromperait) :

| var | défaut | bornage au chargement |
|---|---|---|
| `RECRUTEMENT_MISSION_COUT_CUIVRE` | 300 | ≥ 0 |
| `RECRUTEMENT_MISSION_COUT_PAR_NIVEAU` | 200 | ≥ 0 |
| `RECRUTEMENT_MISSION_PART_FACTEUR` | 0.5 | clampé [0.0, 1.0] — > 1 rendrait le contrat court **plus** cher en butin, l'inverse de son objet |
| `RECRUTEMENT_MISSION_PART_MIN` | 0 | ≥ 0 |

⚠️ **Trois listes à toucher ensemble** : la déclaration, `current_world_variables` (`~:786`) et
le couple `global` (`~:869`) + `load_world_variables` (`~:1013`). En oublier une rend la
variable non réglable à chaud, sans le moindre symptôme.

---

## 4. Serveur — câblage

### `routers/recrutement.py`
- Import de **`debit_character` depuis `utils.marche`** (le module ne l'a pas ; `credit`/`purse`
  viennent de `utils.characters`, `debit_character` vit dans `marche.py:48`).
- **`_recrue_view`** (source unique de `recrues[]` ET `groupe[]`) gagne
  `"contrat_mode"` et, quand `lieu_de_guilde(lieu_doc)`, un bloc **`"mission"`** =
  `offre_mission(av)`. Signature `_recrue_view(character, av, lieu_doc=None)`.
- **`_payload`** gagne `"lieu_de_guilde": bool` là où le lieu est **déjà en main**
  (`/board`, `/embaucher`, `/refuser`, `/congedier`, `/reprendre`). ⚠️ Ne PAS le faire lire un
  doc `lieu:*` là où il n'en a pas besoin (`GET /groupe`) : ce sont les plus gros documents du
  jeu et ils sont hors du cache de requête — le client dispose du global Jinja (§5).
- **`POST /recrutement/embaucher`** accepte `mode` (absent ou `"contrat"` ⇒ comportement
  d'avant, à la lettre). Ordre des gardes, calqué sur `consommer`/`don` (**contrôle avant la
  dépense**) :
  1. `_acces_tableau` (404 perso → 403 lieu → 403 carte), `_recrue_du_tableau` (404/403) ;
  2. `mode == "mission"` et pas `lieu_de_guilde(lieu_doc)` → **403** « Un contrat de mission se
     signe à la guilde. » ;
  3. `peut_embaucher` → **409** (groupe complet / recrue partie) — **avant** tout débit ;
  4. `debit_character(character, cout)` → `None` ⇒ **409** « Fonds insuffisants. » (tout ou rien,
     la bourse est intacte en cas de refus, et rien n'est encore sauvé) ;
  5. `embaucher(character, av, contrat=…)` → `save_doc(character)` 409 → `save_doc(av)` best-effort.
  Le payload porte déjà `purse` ; le client appelle déjà `updatePurse`.
- **`POST /recrutement/reprendre` (NOUVEAU)** — mêmes gardes ordonnées du plus général au plus
  précis : 404 perso → 404 doc → 403 `lieu_de_guilde` → 409 `peut_reprendre` → 409 fonds →
  `_attacher` avec un contrat **neuf** (termes recalculés par `offre_mission`, pas ceux du
  contrat échu : le tarif suit le niveau atteint) → save perso (409) → save av. Payload
  `_payload(...)` + `"reprise": {"nom": …}`.
- **`POST /recrutement/congedier`** : remonter la lecture `lieu_doc = get_doc(character["lieu"])`
  **avant** l'appel (elle est déjà faite plus bas pour le payload — aucune lecture de plus) et
  la passer à `congedier`. Le payload gagne `"congedie": {"nom", "sans_frais": bool}`.

### `routers/quetes.py` — `quetes_terminer` (le site le plus riche)
Une ligne après `memoriser_liens_post_quete`, **avant** le `save_doc(character)` autoritatif :
```python
contrats_echus = recrutement.cloturer_contrats_mission(character, lieu_doc, compagnons=groupe)
```
⚠️ `compagnons=groupe` : ce sont les **mêmes dicts** que `appliquer_recompenses` et
`regler_part_butin` ont déjà servis, et que la boucle `for av in groupe: save_doc(av)` (`:243`)
persiste — **aucune I/O de plus, aucun second dict**. Ordre correct par construction : le
compagnon touche sa part de butin puis s'en va.
Payload : `payload["contrats_echus"] = [recrutement.vue_contrat_echu(av) for av in contrats_echus]`
(seulement s'il y en a).

### `routers/pnj.py` — trois branches de turn-in
Deux helpers minces, jumeaux de `_sauver_compagnie` :
```python
def _cloturer_contrats(character, lieu_doc):   # AVANT le save autoritatif
    return recrutement.cloturer_contrats_mission(character, lieu_doc)

def _sauver_contrats(libres, reponse):         # APRÈS le save autoritatif
    for av in libres: save_doc(av)
    if libres: reponse["contrats_echus"] = [recrutement.vue_contrat_echu(av) for av in libres]
```
Câblés dans `_resoudre_rang` (`rapporter`), `_resoudre_commission` (`rapporter`) et
`_resoudre_transport` (branches `livrer`/`rapporter` — elles soldent bien une quête et
`routers/pnj` y sauve lui-même le personnage, contrairement au chemin de déplacement).
⚠️ La clôture charge le groupe elle-même : c'est **sans danger** parce qu'elle ne mute et ne
renvoie que des **non-permanents**, là où `_sauver_compagnie` ne sauve que des permanents
(invariant §1). Sans cet invariant, les deux sauveraient deux dicts du même doc.

### Hors périmètre, assumé et documenté
**`escorte._solder`** (chemin de déplacement) n'est **pas** câblé : il appelle délibérément
`appliquer_recompenses(compagnons=[])` parce que seul `_apply_world_turn_groupe` charge **et**
sauve les docs compagnons sur ce chemin — y charger le groupe rendrait un second dict, donc
deux `save_doc` sur le même `_rev` et une écriture perdue en silence. Conséquence : une escorte
déposée **dans** une guilde ne clôt pas le contrat ; il s'achèvera au prochain rendu en guilde.
C'est exactement le cas que l'utilisateur a écarté (« pas à la fin d'une escorte qui finit
ailleurs »), et le joueur peut de toute façon rompre sans frais sur place.

### `main.py`
À côté d'`est_recrutement` (`:732`, le doc lieu est déjà en main) :
`lieu_de_guilde = recrutement_util.lieu_de_guilde(grid_doc)` → contexte `/play`.
⚠️ **Variable NOUVELLE, ne pas toucher `est_guilde` (`:728`)**, qui doit rester strictement
`categorie == "guilde_aventurier"` : c'est elle qui conditionne le bouton « Tableau des quêtes ».

---

## 5. Client — `templates/play_town_telluris.html`

Global Jinja **`LIEU_DE_GUILDE`** (seeded depuis le contexte `/play`) : toujours exact, puisque
tout changement de lieu passe par la branche « lien » de `moveTo`, qui recharge `/play`. Il ne
pilote que **les libellés et le grisage** — la garde reste le 403/409 du serveur (patron
« grisage indicatif » du projet). Zéro lecture de doc `lieu:*` supplémentaire.

**Tableau de recrutement** — `openClauses` (`:7345`) montre déjà les conditions et deux réponses ;
quand `r.mission` est présent, l'accord se dédouble :
- `✔ « J'accepte — pour une mission. » (700 cu · part 12 %)` → `embaucherAventurier(id, 'mission')`
  — **grisé** (avec `title`) si la bourse ne suffit pas (`_purseEnCuivre`, déjà utilisé par l'étable) ;
- `✔ « J'accepte — sans terme. » (part 25 %)` → `embaucherAventurier(id)` ;
- `✕ refuser` / `↩ réfléchir` inchangés.
`embaucherAventurier(avId, mode)` passe `mode` dans le corps ; le reste (`updatePurse`,
`renderRecrutement`, toast) est inchangé.

**Carte de compagnon** — `_piedCompagnon` (`:6580`) gagne une **troisième** branche entre
`permanent` et l'ordinaire : `📜 mission — part X %`, `title` expliquant qu'il s'en va à la
prochaine quête rendue à la guilde. `_btnEngager` (`:6612`) reste offert (un compagnon dévoué
sous contrat court peut être engagé durablement : `engager_permanent` efface le contrat).
`_btnCongedier` (`:6601`) : libellé `✕ Mettre fin au contrat` quand `contrat_mode === 'mission'`.

**Confirmation de TOUT débauchage** — `congedierAventurier` (`:7492`) garde son `confirm()` avec
trois textes : rupture d'engagement durable (blesse durablement) / fin de contrat à la guilde
(« sans froisser personne ») / congédiement ordinaire (« il s'en souviendra »).

**Pop-up de fin de mission** — nouvel overlay `#contrat-overlay`, **cloné de
`#engagement-overlay`** (markup `:2555-2561`, CSS `:2444-2456`) :
- z-index **9460**, et **première branche** de la cascade Échap (`:3400`) — il est au-dessus ;
- ⚠️ ✕ / Échap / backdrop = **laisser partir** : le contrat est déjà clos côté serveur, la
  reprise est le geste positif ; aucun geste de sortie n'engage donc quoi que ce soit
  (Convention §8 respectée sans promesse en attente) ;
- contenu : portrait + « Notre contrat s'achève ici. » + les termes de la reprise +
  `✔ Le reprendre pour une mission (X)` / `✕ Le laisser partir` ;
- **file d'attente** `_contratsEchusFile` : plusieurs contrats peuvent échoir ensemble, un
  overlay à la fois, `_contratSuivant()` après chaque décision ;
- un **toast** accompagne chaque échéance, pour que l'information subsiste si l'overlay est
  écarté.

Points d'appel : `terminerQuete` (`:6428`, après les rendus — pas de rechargement) et
`choisirPnj` (`:8061`, avec les blocs `rang`/`commission`/`transport`, donc **avant** les
sorties anticipées `combat_id` (`:8137`) et `deplacer` (`:8142`)). Aucun relais `sessionStorage`
n'est nécessaire : ces deux chemins ne rechargent pas la page — c'est le bénéfice direct de la
règle « fin de contrat au turn-in » plutôt qu'« à l'arrivée en guilde ».

`reprendreAventurier(avId)` → `POST api/recrutement/reprendre` → `updatePurse` + toast, et
re-rendu du panneau 👥 / du tableau **seulement s'il est ouvert** (miroir de
`congedierAventurier`, qui re-fetch `api/groupe` dans ce cas).

⚠️ `escapeHtml` sur nom/spécialité avant toute interpolation `innerHTML` ; **jamais** dans un
`onclick="…('${x}')"` (les ids d'`aventurier:*` sont sûrs, ils suivent le patron de
`ouvrirEngagement`) ; jamais pour `showToast`, qui écrit en `textContent`.

---

## 6. Tests

**`tests/test_recrutement.py`** (fixture `monde` + `perso()`/`recrue()` existants ; ajouter les
quatre nouvelles world-vars au `monkeypatch` de la fixture) :
- `lieu_de_guilde` : réception / comptoir / façade / **bureau du maître** / tag `guilde` = vrai ;
  boucherie = faux.
- `offre_mission` : le coût suit le niveau ; part = `part × facteur` plancherée.
- `embaucher(contrat=…)` estampille `av["contrat"]` ; une ré-embauche **sans** contrat efface un
  contrat périmé (miroir du test existant sur `permanent`).
- `conditions_effectives` : part de mission, toujours rognée par l'affinité, plancher
  `MISSION_PART_MIN` ; un permanent l'emporte (0) même avec un `contrat` résiduel.
- `regler_part_butin` paie la part réduite **sans modification du chokepoint**.
- `cloturer_contrats_mission` : ne fait rien hors guilde ; ne libère que les contrats de mission
  (ordinaire et permanent intacts) ; **n'ajuste AUCUNE affinité** ; idempotente.
- **Invariant** : un permanent ne porte jamais `contrat` ⇒ `cloturer_contrats_mission` et
  `partager_xp` ne renvoient jamais le même doc (le test qui protège le câblage de `routers/pnj`).
- `congedier` : gratuit à la guilde pour un contrat de mission ; malus normal ailleurs ; le
  permanent garde `−15` **même à la guilde** ; `contrat` retiré dans tous les cas.
- `peut_reprendre` : refuse un doc d'un autre employeur, un contrat ordinaire, un groupe plein.

**`tests/test_recrutement_endpoints.py` (nouveau)** — patron de `tests/test_quetes_endpoints.py`
(base en mémoire, patch de `get_doc`/`save_doc`/`find_docs` sur le router **et** les utils,
`get_selected_character` stubbé, `asyncio.run`) : `embaucher(mode="mission")` débite et
estampille ; 403 hors guilde ; 409 fonds insuffisants **sans toucher la bourse** ; `reprendre`
nominal et ses refus.

**`tests/test_quetes_endpoints.py`** — le turn-in renvoie `contrats_echus` et le compagnon a
bien touché sa part **avant** de partir.

**`node dev/check_js.js`** (chemin complet vers `node.exe`) pour le template.

Rappel d'environnement : `python -m pytest tests/` (l'exe est hors `PATH`).

---

## 7. Documentation

`CLAUDE.md` § *Recrutement d'aventuriers & combat de groupe* : une sous-section **« Contrat
d'une mission »** (modèle de données, invariant d'exclusion avec `permanent`, `lieu_de_guilde`
comme source unique, les trois sites de clôture et **la limite assumée sur `escorte._solder`**),
plus les quatre variables dans § *Variables de monde réglables*.

---

## Vérification de bout en bout

1. `python -m pytest tests/` puis `node dev/check_js.js`.
2. `docker compose up`, se rendre à la réception du Bastion (`lieu:le_bastion_de_l_yonne_interieur`)
   avec la carte d'aventurier d'Auxerre → 🤝 Recrues → « Embaucher » : le dialogue offre les
   **deux** accords ; prendre celui d'une mission → la bourse baisse, la carte du groupe affiche
   `📜 mission — part X %`.
3. Prendre une quête au tableau, l'accomplir, la rendre **à la guilde** → le pop-up annonce la
   fin du contrat et propose la reprise ; vérifier que le compagnon a bien touché sa part de
   butin (toast `💰 … prend sa part`) **avant** de partir.
4. Reprendre → la bourse rebaisse, il revient au groupe. Recommencer et **laisser partir** →
   il quitte le groupe **sans perte d'affinité** (onglet 🤝, section 👥).
5. Ré-embaucher un contrat de mission, sortir de la guilde, le congédier → confirmation, et
   l'affinité baisse. Le reprendre, revenir à la guilde, le congédier → confirmation, et
   l'affinité **ne bouge pas**.
6. Contrôles de non-régression : un compagnon **ordinaire** garde son malus de congédiement à
   la guilde ; un **permanent** garde son `−15` ; une quête rendue au comptoir (épreuve de
   rang) et au bureau (commission) clôt aussi le contrat.

# Page d'administration : dialogues PNJ & offres de quête

## Context

Le contenu narratif de Telluris vit **entièrement dans les docs `pnj:*`** : 59 documents,
**903 nœuds, 1897 choix** en base. Et les quêtes authorées ne sont pas des docs `quete:*` —
sur les 7 en base, 6 sont des offres de tableau générées (`..._<hash>`, statut `offerte`) et
la 7ᵉ est `quete:bastion_authoree_exemple`. Le contenu authoré, lui, est porté par les PNJ,
en specs `services.transport.offre` (49 PNJ) et `services.escorte.offre` (51 PNJ).

Aujourd'hui, retoucher une réplique ou une offre oblige à réécrire le document JSON entier à
la main puis à le réimporter. Le dépôt en porte la trace : `jsons/*_correctif_a_importer.json`
ne contiennent souvent qu'un seul doc PNJ. C'est laborieux et surtout risqué —
`admin_import_bulk` fait un **PUT complet, jamais un merge** (CLAUDE.md §11) : une clé oubliée
disparaît en silence.

`/admin/table` sait déjà éditer un doc `pnj:*`, mais en **JSON brut**, sans rien comprendre au
schéma : il ne dit pas qu'un `next` pointe dans le vide, qu'un nœud est inatteignable, ni
qu'un flag de condition est inconnu du moteur — auquel cas le choix ne s'affiche **jamais**,
silencieusement.

**Résultat visé** : un écran `/admin/dialogues` qui donne au contenu narratif l'édition
structurée qui lui manque — formulaire par nœud, vue d'ensemble en graphe, formulaire dédié
aux offres — et qui produit le document complet à importer.

## Décisions déjà cadrées

1. **Dialogues** : formulaire d'édition complet **et** vue graphe **en lecture seule**.
2. **Quêtes** : édition des specs `services.transport.offre` et `services.escorte.offre`
   seulement. Pas d'aperçu du tableau de guilde, pas d'édition des docs `quete:*`.
3. **Écriture** : **JSON à copier seulement**. La page ne fait **aucune** écriture en base ;
   elle produit le doc `pnj:*` complet à coller dans la carte d'import de `/admin`. La
   lecture depuis la base reste permise, et nécessaire pour éditer l'existant.

## Le schéma réel (vérifié sur le dump)

```
pnj:*  →  _id, _rev, type, nom, race, vocation, portrait, description?, services?, dialogue
dialogue → { noeud_depart, noeud_attente?, noeuds: { <id>: nœud } }
nœud     → { texte, choix[] }  + rares : delai_min, texte_gratuit, relation, relation_reinit
choix    → { id, label }       + next (1684/1897), condition (444), action (213), deplacer (8)
services → transport 49 · escorte 51 · acces 7 · rang 1 · commission 1 · soin 1 · don 1
```

⚠️ **`noeud_depart` et `noeud_attente` vivent DANS `dialogue`**, à côté de `noeuds` — pas au
niveau du document. Ils appartiennent donc à la carte Dialogue, pas à la carte Identité.

## Le point de conception qui commande le reste

Le formulaire **ne possède pas tout le document** : `description` (11 docs), les sous-clés de
`services` qu'il ne modélise pas, et les clés que la page ignorera demain — au niveau du doc,
du **nœud** et du **choix**. Le JSON produit partant vers un import qui écrase tout, une clé
absente est une **perte de contenu silencieuse**.

C'est la classe de bug déjà traitée pour les lieux et les connexions par `_fusionLieu`
(`templates/admin_map_editor.html`) et `_fusionConnexion` (idem), verrouillées par
`dev/test_lieu_form_client.js` et `dev/test_connexions_client.js`. On reprend leur idiome **à
la lettre** : copie profonde du doc relu, `Object.assign` par sous-objet, n'écrire que les
champs possédés, supprimer explicitement ce qui est vidé.

## Fichiers

| Fichier | Nature | Rôle |
|---|---|---|
| `templates/admin_dialogues.html` | **créé** | Toute la page : CSS, markup, JS vanilla inline. |
| `main.py` | modifié | Route `GET /admin/dialogues` (~15 l.), près de `/admin/dev-tools` (l.1100). |
| `templates/admin_telluris.html` | modifié | Carte-lien sous `.section-label` « Editeurs » (l.127). |
| `dev/test_dialogues_client.js` | **créé** | Harnais Node des fonctions pures. |
| `utils/dev_tools.py` | modifié | Entrée `CATALOGUE` (l.57) pour lancer le harnais depuis `/admin/dev-tools`. |
| `CLAUDE.md` | modifié | Ligne « Running tests » + entrée `dev/` + section de la page. |

Aucun module `utils/*` neuf, **aucun endpoint neuf**.

## Route

Dans `main.py`, calquée sur `admin_dev_tools` (l.1100) avec `_require_admin_page` (l.180) :

```python
@app.get("/admin/dialogues", response_class=HTMLResponse)
def admin_dialogues(request, current_user): ...
    context={"title": "Dialogues & quêtes", "vocabulaire": _vocabulaire_dialogues()}
```

`_vocabulaire_dialogues()` — helper local à `main.py`, à côté de `_require_admin_page` —
assemble le vocabulaire servi au template. **`utils.lint_dialogues` et `utils.acces` sont déjà
importés** (`main.py:49` et `:46`) :

- de `lint_dialogues` : `PLACEHOLDERS_CONNUS`, `FLAGS_CONNUS`, `CONDITIONS_STRUCTUREES`,
  `CONDITIONS_QUETE`, `QUETE_REUSSIE_CLES`, `NOEUDS_REQUIS`, `ACTIONS_A_CONDITIONNER`,
  `RELATION_CLES`, `TRANSPORT_DONNEUR/DESTINATAIRE/RETOUR`, `ESCORTE_MEFIANCE` ;
- de `acces` : `CONDITIONS_CONNUES` (l.68), `SOUS_FILTRES_CONNUS` (l.74).

⚠️ **Ce sont des `set` Python**, non sérialisables par `| tojson` : les convertir en **listes
triées**. `ACTIONS_A_CONDITIONNER` (l.128) est un dict à clés tuple → le sérialiser en
`[{service, op, flag}]`.

⚠️ **Servir ce vocabulaire, jamais le recopier en JS.** C'est le risque documenté pour
`utils/capacites.py` (CLAUDE.md, « Capacités d'un lieu ») : une liste recopiée diverge du
moteur en silence. Injection en Jinja comme `admin_dev_tools.html` :
`const VOCAB = {{ vocabulaire | tojson | safe }};`

## Écran

Template autonome (ni `extends` ni `include` — aucune page admin n'en utilise), préambule CSS
`:root` + `.card`/`.btn` recopié depuis `admin_table.html`, header à deux enfants
(`<h1>` + `<a href="/admin">← Retour à l'administration</a>`).

```
┌─ header ────────────────────────────────────────────────────────┐
├─ carte « PNJ » : <select> des 59 docs + ↻ Charger + statut ─────┤
├─ carte « Identité » : _id (gelé), nom, race, vocation,          │
│   portrait (<select> + aperçu), description                     │
├─ carte « Dialogue » : noeud_depart, noeud_attente ──────────────┤
│  ┌── liste des nœuds ──┬── graphe SVG (lecture seule) ────────┐ │
│  │ id · badges  ⚠ mort │  nœuds reliés par leurs `next`       │ │
│  │ (clic = éditer)     │  (clic = sélectionne, ne modifie pas)│ │
│  └─────────────────────┴──────────────────────────────────────┘ │
├─ carte « Services & offres » : un bloc pliable par service,     │
│   dont le formulaire d'offre transport / escorte                │
├─ carte « JSON du document » : <textarea readonly> + 📋 Copier   │
│   + 🔍 Vérifier (POST /admin/lint-dialogues) + rapport          │
└─ #noeud-overlay : formulaire du nœud sélectionné (fixe à droite)│
```

**Overlay du nœud** — même géométrie que `#editor-card` (`admin_table.html:138`), piloté par
`style.display = 'flex'|'none'` comme à la l.594. Contenu : `texte`, `texte_gratuit`,
`delai_min`, `relation`, `relation_reinit`, puis **une ligne par choix** (`id`, `label`,
`next` en `<select>` des nœuds existants + `fin`, `condition`, `action` service/op,
`deplacer`), avec ajout/suppression/réordonnancement.

⚠️ Si l'on préfère l'attribut `hidden` à `style.display`, il **faut** `#id[hidden]{display:none}` :
`#id{display:flex}` (spécificité 1,0,0) écrase le `display:none` du navigateur — piège déjà
documenté dans `admin_simulateur.html`.

⚠️ L'overlay et le graphe occupent tous deux la moitié droite : **ouvrir l'overlay rétrécit la
carte Dialogue**, ou le graphe est masqué le temps de l'édition. Précédent direct :
`#lj-overlay` et `#conn-overlay` de l'éditeur de carte, qui se ferment l'un l'autre.

## Fonctions JS pures (celles que le harnais testera)

Préfixe `_dlg`, dans l'idiome `_cx*` / `_nl*` de l'éditeur de carte.

| Fonction | Signature | Rôle |
|---|---|---|
| `_dlgFusionDoc` | `(existant, champs) → doc` | **La plus importante.** Copie profonde du doc relu ; écrit identité + `dialogue` + `services` ; **conserve toute clé inconnue** au niveau doc, nœud et choix. Miroir de `_fusionLieu`/`_fusionConnexion`. |
| `_dlgFusionNoeud` | `(ancien, champs) → noeud` | `Object.assign({}, ancien)` ; champs vidés **supprimés** — un `delai_min: 0` ou un `relation` vide sont des fautes que le linter signale. |
| `_dlgFusionChoix` | `(ancien, champs) → choix` | Idem au niveau choix. `next` absent quand une `action` est posée (le moteur l'ignore alors — `routers/pnj.py:645`). |
| `_dlgEntrees` | `(doc) → Set` | Miroir de `lint_dialogues._entrees` : `noeud_depart` + `noeud_attente` + **toutes** les valeurs de `services.*.noeuds`. |
| `_dlgAtteignables` | `(noeuds, entrees) → Set` | Miroir de `lint_dialogues._atteignables` (fermeture transitive des `next`). Alimente le badge « nœud mort ». |
| `_dlgNextMorts` | `(noeuds) → [{noeud, choix, cible}]` | `next` ni `fin` ni existant. |
| `_dlgValiderNoeud` | `(noeuds, nid, noeud) → ''\|message` | Idiome `_cxValider` : rend un motif ou `''`. Nœud sans choix, `id` de choix dupliqué, `id` vide. |
| `_dlgValiderDoc` | `(doc) → ''\|message` | `_id` en `pnj:`, `noeud_depart` présent **et existant dans `noeuds`**. |
| `_dlgOffreTransport` | `(ancienne, champs) → offre\|null` | Construit `services.transport.offre` ; `null` si `destination` ou `cargaison` manque — miroir de `transport.offre_spec` (`utils/transport.py:378`), qui rendrait `None` : une offre incomplète est **silencieusement inerte**. |
| `_dlgOffreEscorte` | `(ancienne, champs) → offre\|null` | Idem pour `escorte.offre_spec` (`utils/escorte.py:64`). Gère les **trois** formes de `rencontre` : absente / `{lieu}` / `{lieu, zones[]}`. |
| `_dlgLayoutGraphe` | `(noeuds, entrees) → {noeuds:[{id,x,y,rang}], liens:[{de,vers,conditionne}]}` | Placement en couches, pur, sans DOM. |

## Graphe (lecture seule)

**SVG inline**, pas `<canvas>` : l'éditeur de carte est en canvas parce qu'il peint des
grilles de pixels ; ici le SVG donne gratuitement le texte, le survol et le clic. Volume
réel : **24 nœuds au maximum** (`pnj:borin_barbe_de_jais`), médiane bien plus basse — aucun
besoin de moteur de placement.

**Placement** : couches par BFS depuis `_dlgEntrees` (rang = distance), un `x` par rang, un `y`
par position dans la couche ; les nœuds inatteignables dans une bande à part, en bas. Liens en
courbes de Bézier ; `fin` rendu comme terminaison, pas comme nœud.

**Ce que le graphe doit rendre visible** (sa raison d'être) : nœud **inatteignable** (rouge),
`next` **mort** (lien pointillé rouge), choix **conditionné** (lien pointillé sourd), nœud de
**service** (liseré doré — il est une entrée sans `next` entrant), nœud **sélectionné**.
Clic = sélectionne, ne modifie jamais.

## Validation

Deux niveaux, sans jamais réimplémenter le moteur en JS :

1. **Immédiat, local** : badges de la liste et du graphe (`_dlgAtteignables` / `_dlgNextMorts`),
   et `<select>` plutôt que saisie libre partout où le vocabulaire est fini (`next`, flags,
   service/op, nœuds de service) — ce qui rend la plupart des fautes du linter **impossibles
   à saisir**.
2. **Complet, serveur** : bouton **🔍 Vérifier** → `POST /admin/lint-dialogues` (`main.py:1074`)
   avec le doc **seul** — le corps est typé `list | dict` et l'endpoint est **en lecture
   seule**. Réponse : `{analyses, ignores, erreurs, avertissements, trouvailles[]}`, chaque
   trouvaille `{doc_id, niveau, noeud, message}`. **Rendu repris tel quel** de
   `admin_telluris.html:565-570` (`.lint-line.erreur` / `.avertissement`, avec `escapeHtml`).
   C'est la source unique : les 30+ contrôles restent en Python.

⚠️ **Angle mort à signaler dans l'UI.** Les flags ne sont posés par `routers/pnj.py:_contexte`
(l.64) **que si le PNJ porte le service correspondant** : `flags["acces_ouvrable"]` et ses
voisins sont écrits dans un `if lieu_garde:` qui exige `services.acces.lieu` (l.223-234) ; les
`commission_*` dans un `if donjon_doc:` qui exige `services.commission.donjon` (l.206-217). Or
le linter ne fait qu'un test d'appartenance (`if cle not in FLAGS_CONNUS`, l.374) : un choix
conditionné par `acces_ouvrable` sur un PNJ sans `services.acces` **ne s'affiche jamais et le
linter ne le voit pas**. Le `<select>` des flags groupera donc les flags par service et
**avertira** quand le service n'est pas déclaré.

⚠️ `services.transport.noeuds.livre_retour` est lu par `routers/pnj.py:783` mais **absent de
toutes les listes du linter** : le formulaire doit l'offrir explicitement.

## Sécurité et rendu

- **XSS** : ids, labels et textes partent dans du markup généré → `escapeHtml` obligatoire
  (idiome `admin_table.html`). Le rapport de lint contient des ids de contenu : même règle.
- **Typographie** : les espaces insécables autour de `« »` sont posées **au rendu** par
  `utils/pnj._espaces_insecables` (`utils/pnj.py:423`). L'éditeur **ne doit pas les
  pré-écrire** dans le doc — sinon le doc diverge de tout le corpus existant.
- **`_id` gelé** en édition : CouchDB ne renomme pas (même règle que le formulaire de lieu).

## Tests

`dev/test_dialogues_client.js`, méthode **identique** à `dev/test_connexions_client.js` :
concaténer les blocs `<script>` sans `src`, extraire chaque fonction **par nom** (accolades
équilibrées), puis **`vm.runInThisContext`** — ⚠️ jamais `vm.createContext` : un realm séparé
a un autre prototype `Array` et `deepStrictEqual` refuserait tous les tableaux (piège
documenté pour `test_resize_client.js`). Compteurs `passes`/`echecs`,
`process.exit(echecs ? 1 : 0)`.

Ce que le harnais **verrouille** :
- une clé inconnue du doc, d'un **nœud** et d'un **choix** survit à `_dlgFusionDoc` (la classe
  de bug qui justifie la fusion — perte silencieuse à l'import) ;
- `race`/`vocation`/`description` et les sous-clés de `services` non modélisées survivent ;
- un champ vidé est **supprimé**, pas écrit à zéro ;
- `_dlgEntrees` compte bien les nœuds de service — sinon tout nœud de service serait
  faussement signalé « inatteignable » ;
- `_dlgAtteignables` = fermeture transitive, cycles compris (`retour → accueil`, très fréquent) ;
- une offre sans `destination`/`cargaison` (ou `proteges`) rend `null` et **n'est pas écrite** ;
- les trois formes de `rencontre` d'escorte ;
- `_dlgLayoutGraphe` est déterministe et place tout nœud exactement une fois.

`node dev/check_js.js` couvre la nouvelle page **sans modification** : il balaie
`templates/*.html` par lecture de répertoire.

`pytest` : **aucun test neuf requis** — la page n'ajoute aucune logique Python hors le helper
de sérialisation. Relancer la suite (1758 tests) pour la non-régression de la route ajoutée.

**Hors de portée du harnais** (à vérifier en jeu, CLAUDE.md §15) : rendu SVG réel, ouverture de
l'overlay, cohabitation overlay/graphe, échange avec `/admin/lint-dialogues`.

## Vérification de bout en bout

1. `python3 -m pytest tests/ -q` → 1758 passés (référence mesurée sur ce dépôt).
2. `node dev/check_js.js` → aucune erreur de syntaxe, nouvelle page incluse.
3. `node dev/test_dialogues_client.js` → tout vert ; puis les sept harnais existants, inchangés.
4. `docker compose up`, `/admin` → la carte apparaît sous « Editeurs » → ouvrir.
5. Charger `pnj:templier_armand_de_vaucremont_01` (service `acces`) : vérifier que le graphe
   montre ses nœuds et que `acces_ouvre`/`acces_refus` ne sont **pas** marqués inatteignables
   — ils n'ont pas de `next` entrant, ils sont atteints par le service.
6. Charger `pnj:borin_barbe_de_jais` (**24 nœuds**, le plus gros du jeu ; `transport.offre`
   avec `retour`, plus `rang`, `acces`, `escorte.recherche`) : vérifier le placement et le
   formulaire d'offre.
7. **Test de non-perte** : charger `pnj:reverend_malakor` (`escorte.offre` avec
   `rencontre.zones`, plus `soin` et `don`), ne rien changer, copier le JSON produit et le
   **differ** avec le doc d'origine — il doit être identique aux clés ordonnées près. C'est la
   vérification qui compte le plus.
8. Modifier une réplique, 🔍 Vérifier → 0 erreur, copier, coller dans la carte d'import de
   `/admin`, importer, relire le PNJ en jeu.
# Conception — inventaire de contenant

- **Créée :** 02/11/2026. **Statut :** conception arbitrée par l'Auteur (trois questionnaires, § Décisions). **Mécanique implémentée** le 02/11 (`utils/contenants.py`, `routers/contenants.py`, fenêtre 👜 de `/play`) ; contenu : `dev/gen_contenants.py` → `jsons/contenants_a_importer.json` ; service `vente` et vendeur des copies (Maître Villard de Honnecourt, Cour des Arches) le 08/11 ; reste l'obtention des reliques et des objets du lore.
- **Lore :** `docs/lore/monde/20261102_sacs_des_legendes.md` (reliques, copies d'Architectes, chiffres).
- **Besoin :** un objet à poids fixe qui contient un poids supérieur ; ce qui est dedans ne pèse rien pour le porteur.

## Décisions de l'Auteur (02/11/2026)

| Sujet | Décision |
|---|---|
| Coffre de propriété | ne compte que le **poids du contenant** (un contenant agrandit le stockage d'un bien : voulu) |
| Poser au sol un contenant plein | **autorisé** (perdu avec son contenu au déplacement, comme tout objet au sol) |
| Marée (Sac de Manannán) | **temps réel**, vraie période semi-diurne **12 h 25**, fenêtre **3 h**, même moment pour tous |
| Équiper | **jamais** : objet du sac |
| Vol au coffre sans gardien | le contenant plein part **avec tout** ; la limite de vol compte le contenant **et** son contenu |
| Vendre / confier à un atelier | **refusé s'il n'est pas vide** (le contenant lui-même ; son contenu, lui, se vend et se confie sans être sorti — 07/11) |
| Combat | contenu **inaccessible** ; ranger et sortir hors combat seulement |
| Où ranger et sortir | **partout** hors combat (sauf la marée de Manannán) |
| Charge magique | ce qui est rangé **ne gêne pas la magie** non plus (« il ne pèse rien ») |
| Reliques | **une par personnage** : chacun peut obtenir la sienne une fois |
| Vente des copies | **PNJ Architecte de l'institut, vente à prix fixe**, sans stock ni fabrication ; un institut pareil à Petra et dans les cités à portail à venir |
| Vendeur de Lutecia (08/11) | **à la Cour des Arches, avec Aélis** — Maître Villard de Honnecourt |
| Sacs à dos à trophée (08/11) | **deux havresacs** chez Maître Villard, 200 kg · 1,5 kg · 10 or **+ un morceau de monstre laissé** : Havresac de Grendel (aile de Dragon), Havresac de mimique (carcasse de Mimique) |
| Objets du lore (08/11) | **pas uniques** : coffres de Thot, tente, outre, gourde, kibisis peuvent exister en plusieurs exemplaires, sans trace « une par personnage » |
| Cinq objets du lore | contenance / poids selon leur légende (§ Contenu) |

Rappel du lore arbitré : inventaire séparé à limite propre ; **aucun contenant magique dans un autre** ; **aucun être vivant** (aucun objet du jeu n'en est un : rien à garder) ; on dépose dans le Sac de Manannán à tout moment, on ne reprend (ni ne voit) qu'à marée haute.

## Modèle

### Le doc item porte la capacité
```json
{"_id": "item:besace_profonde", "type": "item", "nom": "Besace profonde", "categorie": "outil",
 "sous_categorie": "contenant", "slots": [], "poids": 0.5,
 "tags": ["contenant", "non_personnalisable"],
 "contenant": {"capacite_kg": 100}}
```
- `contenant.maree: true` pour le Sac de Manannán seul ; période, fenêtre et phase = **variables de monde** (`MAREE_PERIODE_S` 44 712, `MAREE_FENETRE_S` 10 800, `MAREE_REFERENCE_EPOCH`).
- Tag `non_personnalisable` : une variante sur mesure aurait un autre `_id` et perdrait la référence au contenu.

### Le contenu vit sur la RÉFÉRENCE d'inventaire
```json
{"item": "item:besace_profonde", "poids": 0.5, "contenu": ["item:pain", {"item": "item:Cuir", "poids": 3.2}]}
```
- Même patron que le texte d'un livre écrit (`scriptorium`) ou `nom_perso` : l'état de l'**exemplaire** sur sa référence, jamais sur le doc générique.
- **Le contenu suit le contenant partout** sans code : sac, compagnon, monture (`groupe/transferer`), coffre de propriété, sol, butin.
- **Rangé = inerte** : les 27 fichiers qui lisent `inventaire` ne voient que la référence du contenant. Grimoires de « 📖 Apprendre », outils partagés, pièges, combat, charge magique : rien à modifier, l'objet doit être **sorti** pour servir.
- **Exception (Auteur, 07/11 — l'inaccessible, c'est surtout la barre d'action et le combat)** : à la **vente en boutique**, aux **remises de quête** (collecte, apport, épreuve d'apport, cargaison de transport) et aux **dons à un artisan** (matières et pièce d'une commande, objet confié au marchand d'une propriété) et au **cristal jaune du portail de Notre-Dame** (sac du voyageur puis ses contenants), le contenant est un **porteur de plus**, comme un compagnon ou une monture — son contenu se vend et se remet sans être sorti (`contenants.avec_contenants` / `sac_vise`). Hors marée, le contenu du Sac de Manannán reste hors d'atteinte.
- **Charge magique** : `charge_magie.charge_magique_portee` lit l'inventaire, donc ignore aussi le contenu — voulu (décision de l'Auteur).
- **Poids** : `item_ref_weight` ignore déjà `contenu` → `carried_weight`, `peut_porter`, `poids_coffre` comptent le seul contenant **sans changement**.
- **Aucune migration** : une référence chaîne devient un dict à la première mise (comme `renommer_ref`) ; `contenu` absent = vide.

## Module pur `utils/contenants.py`
DB injectée, mute sans sauver (convention 2).

| Fonction | Rôle |
|---|---|
| `est_contenant(doc)` | bloc `contenant` présent |
| `capacite(doc)` · `poids_contenu(ref)` | limite ; Σ `item_ref_weight` du contenu |
| `poids_total(ref)` | contenant + contenu — **seul** usage : la limite de vol |
| `peut_ranger(ref_c, doc_c, ref, doc)` | refus : objet contenant (emboîtement), capacité dépassée |
| `ranger(porteur, i_c, i)` / `sortir(porteur, i_c, j)` | déplace la référence ; `sortir` exige `recrutement.peut_porter` (409 sinon) |
| `maree_haute(now)` · `prochaine_maree(now)` | `(now − référence) mod période` dans la fenêtre centrée ; même résultat pour tous (cf. `portails.fenetre_secondes`) |
| `accessible(doc, now)` | faux pour un contenant `maree` hors fenêtre |

## Endpoints (`routers/contenants.py`)
Tous par **`_acteur(current_user, body)`** : le contenant peut être dans le sac d'un compagnon ou d'une monture, et l'action porte le `compagnon_id` de l'acteur courant (convention 1).

- `GET /api/contenant?index=&item_id=&compagnon_id=` → bloc `contenant` : `capacite_kg`, `charge_kg`, `accessible`, `prochaine_maree_at`, `contenu` résolu (`resolve_item_ref`) — **vide hors marée** (« le sac semble vide »).
- `POST /api/contenant/ranger {index_contenant, item_id_contenant, index, item_id, compagnon_id}`.
- `POST /api/contenant/sortir {index_contenant, item_id_contenant, index_contenu, item_id, compagnon_id}` — 409 hors marée.
- **Refus 409 en combat** : doc `combat` du personnage au `status` `active` (même test que l'anti-doublon de `routers/combat.py`). L'interface n'existe que dans `/play`, qui redirige déjà vers un combat actif : la garde serveur vise la requête forgée.
- Réponse : `_inventory_payload` + bloc `contenant` + `fiche` (sortir un grimoire ouvre un sort, convention 10).

## Gardes à poser ailleurs

| Chemin | Garde |
|---|---|
| `sell_item` (négociant compris) | 409 « Videz-le d'abord » si `contenu` non vide |
| `proprietes/atelier/donner`, vente d'un visiteur à un atelier | idem |
| `proprietes.vol_coffre_autorise` / `noter_vol_coffre` | compter `contenants.poids_total(ref)` au lieu de `item_ref_weight` |
| commande, pièce apportée | rien : `non_personnalisable` l'exclut déjà |
| `drop_item`, `pickup_item` (surcharge → chute aléatoire), `coffre/transferer`, `groupe/transferer` | **rien** : le contenu suit la référence |

## Interface (`play_town_telluris.html`)
- Fiche objet d'un contenant : jauge `charge/capacité` + bouton **« 👜 Ouvrir »** (caché en combat).
- Overlay **deux colonnes**, patron de `#prop-coffre-panel` : à gauche le sac de l'acteur, à droite le contenu ; flèches grisées si la capacité ou la charge du porteur l'interdit.
- Sac de Manannán hors marée : colonne de droite vide, « La mer s'est retirée — prochaine marée haute dans 4 h 12 » ; le dépôt reste possible.
- Overlay bloquant : ✕ / Échap / clic sur le fond = fermer (convention 8).
- Harnais : `dev/test_contenants_client.js` (jauge, flèches grisées, texte de marée).

## Tests (`tests/test_contenants.py`)
Capacité, emboîtement refusé, chaîne → dict, poids porté inchangé, `sortir` refusé en surcharge, marée sur `now` injecté (bords de fenêtre, période), refus de vente plein, limite de vol au poids total, contenu conservé par `groupe/transferer` et `coffre/transferer`.

## Vente des copies — service `vente` (08/11)
- `services.vente = {articles: [{item, cout_cuivre}], noeuds: {fait, sans_fonds, trop_charge}}` ; un choix par article, action `{"service": "vente", "op": "acheter", "item": "item:x"}` ; placeholders `{objet}`, `{prix}` (`utils/pnj.article_en_vente`, `routers/pnj._resoudre_vente`).
- Prix **fixe**, écrit dans l'article par le générateur depuis la `valeur` du doc item (min = max) ; ni stock, ni relation, ni marchandage, ni rang. Principal seul : charge contrôlée, puis débit, puis remise — un refus ne touche à rien.
- Vendeur : `pnj:villard_de_honnecourt` (nain, maître d'œuvre de l'Institut), toujours présent à `lieu:la_cour_des_arches` à côté d'Aélis — `dev/gen_architecte_contenants.py` → `jsons/architecte_contenants_a_importer.json`. Verrouillé par `tests/test_vente_architecte.py`.
- **Article à trophée** (`trophee: "item:…"`) : un exemplaire laissé au vendeur en plus du prix, pris dans les sacs de l'expédition (principal en tête, compagnons, montures, contenants) ; absent ⇒ nœud `sans_trophee`, rien n'est pris ; la charge compte ce que le trophée libère du sac du principal. ⚠️ Le négociant rachète tout et peut remettre un trophée en rayon (une carcasse de Mimique au Comptoir d'or de Saint-André, Chartres, au dump du 08/11) : rien n'interdit de l'y acheter.
- Restent : un institut à **Petra**, puis chaque cité à portail transversal décrite (même service, autre vendeur).

## Contenu (générateur, plus tard)
Un `dev/gen_contenants.py` → **un** `jsons/contenants_a_importer.json`, chiffres du tableau de la séance de lore :

| Objet | Contenance | Poids | Nature |
|---|---|---|---|
| Besace profonde · Urne intérieure · Coffre de retrait | 100 · 300 · 1 000 kg | 0,5 · 8 · 20 kg | copies, 50 000 · 200 000 · 750 000 cu (×5, Auteur 08/11) |
| Carquois d'Arjuna · Pot d'Anansi | 300 kg | 1 · 3 kg | relique · plusieurs pots |
| Sac de Manannán (marée) · Sac de Rhiannon | 500 · 1 000 kg | 0,5 kg | reliques |
| Coquille d'Oduduwa | 2 000 kg | 0,1 kg | relique |
| Coffres du Livre de Thot | 1 000 kg | 30 kg | objet du lore |
| Tente de Pari Banou | 1 500 kg | 2 kg | objet du lore |
| Outre d'Éole | 300 kg | 1,5 kg | objet du lore |
| Gourde de Li Tieguai | 200 kg | 1 kg | objet du lore |
| Kibisis de Persée | 100 kg | 0,5 kg | objet du lore |

**Une relique par personnage** : l'obtention (quête, coffre de donjon) vérifie qu'il ne l'a jamais reçue — trace sur le personnage, comme une quête unique réussie.

## Points ouverts
- **Où trouver** le carquois d'Arjuna (Muziris, plus tard) et les cinq objets du lore (coffres de Thot, gourde, tente, kibisis, outre — **pas uniques**, Auteur 08/11).
- **Obtention des reliques** : quelle quête ou quel coffre de donjon pour chacune (île de Man, Annwn, zones blanches).

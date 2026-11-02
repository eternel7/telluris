# Conception — inventaire de contenant

- **Créée :** 02/11/2026. **Statut :** conception arbitrée par l'Auteur (deux questionnaires, § Décisions), **non implémentée**.
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
| Vendre / confier à un atelier | **refusé s'il n'est pas vide** |
| Combat | contenu **inaccessible** ; ranger et sortir hors combat seulement |
| Où ranger et sortir | **partout** hors combat (sauf la marée de Manannán) |

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
- **Rangé = inerte** : les 27 fichiers qui lisent `inventaire` ne voient que la référence du contenant. Vente groupée, quêtes (cargaison comprise), grimoires de « 📖 Apprendre », outils partagés, pièges, combat, charge magique : rien à modifier, l'objet doit être **sorti** pour servir.
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

## Contenu (générateur, plus tard)
Un `dev/gen_contenants.py` → **un** `jsons/contenants_a_importer.json` : 3 copies (Besace profonde, Urne intérieure, Coffre de retrait) + reliques (sacs de Manannán et de Rhiannon, carquois d'Arjuna, coquille d'Oduduwa, pot d'Anansi) ; capacité, poids et prix repris du tableau de la séance de lore. Vente des copies : boutiques d'Architectes de Lutecia et des cités à portail transversal (à poser).

## Points ouverts
- **Charge magique** : ce qui est rangé ne pèse rien, donc ne gêne plus la canalisation non plus — conséquence directe de « ne pèse rien » ; à confirmer.
- **Unicité d'une relique** : une par monde, ou une par personnage ? (dépend de la façon de l'obtenir : quête, coffre de donjon).
- **Boutique des copies** : quelle catégorie de lieu (atelier d'Architecte neuf, ou tag sur un lieu existant) dans chaque cité à portail.
- Les cinq objets ajoutés au lore (coffres de Thot, gourde de Li Tieguai, tente de Pari Banou, kibisis, outre d'Éole) : contenance et poids.

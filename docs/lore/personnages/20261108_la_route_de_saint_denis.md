# La route de Saint-Denis — l'escorte du rang C

- **Source :** séance Claude Code du 08/11/2026, d'après la trame retenue des quêtes par rang (`personnages/20260924_idees_de_quetes_a_lutecia.md`, rang C : « La route de Saint-Denis », avec un paladin du Sacré-Cœur).
- **Créée :** 08/11/2026
- **Statut :** le § 1 **fait foi** (arbitrage de l'Auteur, 08/11, questionnaire : les neuf recommandations retenues) ; les textes de dialogue restent **proposés**. Contenu importable : § 6.

---

## 0. Ce qui fait déjà foi

| Point | Source |
|---|---|
| Rang C, route du nord, un paladin, « les monstres existaient déjà avant les donjons » | trame retenue (Auteur, 24/09 : « On va garder ta dernière version » ; D–B de la première version) |
| **Vérité du monde** : les monstres précèdent les portails ; les trois frères les ont inventés dans un monde où les monstres rendaient déjà les routes mortelles | Auteur, 24/09 (`20260924_etoffer_l_intrigue_des_catacombes.md`) |
| L'épreuve du rang C à Lutecia, c'est **Jumièges** (Maëlys) : Saint-Denis n'est donc **pas une épreuve de rang**, c'est une escorte | Auteur, 11/10 (`20261011_maelys_maitresse_de_guilde.md`) |
| Bouchard de Clignancourt (nain, paladin des routes, Montmartre) a une chaîne d'escortes **en jeu** : *Le convoi de Chartres* → *Les pèlerins de Reims* (rang E) → *La route silencieuse* (rang D). Elle se termine sur : « Maintenant, j'ai des convois que je ne confie pas à n'importe qui. » | dump du 08/11 (`pnj:bouchard_de_clignancourt*`) |
| Paladins antérieurs aux portails ; auberges-relais avant les monothéismes, beaucoup devenues **monastères-relais** depuis | Auteur, 21/08 et 11/10 |
| Pas de référence au christianisme dans une histoire : les édifices gardent leur nom réel, leur **fonction** est tellurienne | règle d'écriture de l'Auteur |

## 1. Arbitrage (Auteur, 08/11, questionnaire)

| # | Point | Décision |
|---|---|---|
| 1 | Donneur | **Bouchard de Clignancourt, quatrième escorte de sa chaîne** (`pnj:bouchard_de_clignancourt_saint_denis`, après *La route silencieuse*) |
| 2 | Garde de rang | **`rang_min` C à Lutecia** (après E pour Reims, D pour la route silencieuse) |
| 3 | Destination | **le Relais de Saint-Denis**, lieu neuf : monastère-relais fortifié sur la route du nord, autour de la **basilique** (nom réel ; fonction : relais, et le tombeau de Denis), ancienne auberge-relais d'avant les monothéismes |
| 4 | La bête | **le serpent de Marcel** (le dragon de Paris), **être unique**, `espece:` neuve |
| 5 | Ceux qui rabattent | **loups et corneilles** (`espece:loup`, `espece:corneille_noire`, déjà en jeu) : ils harcèlent les flancs du convoi sans le tuer et le poussent vers le vieux chemin |
| 6 | Issue | **combat + doute** (comme le Morvan) : le serpent barre le coude, on le combat ; les théories vivent dans les dialogues d'après |
| 7 | Les légendes | **Denis et Marcel tous deux, sans leur christianisme** (§ 2) |
| 8 | PNJ neufs | **validés tels quels** : Frère Hilduin et les trois protégés du § 3 |
| 9 | Récompense | **200 XP + 3 000 cuivres** |

## 2. Les deux légendes réelles, adaptées

**Denis, le porteur de tête** (*Passio* de saint Denis ; la Vie qu'en écrit l'abbé Hilduin au IXᵉ siècle le confond avec Denys l'Aréopagite : déjà une légende déformée).
- Sur la Terre : décapité sur la butte de Montmartre (« mont des Martyrs »), il se relève, prend sa tête dans ses mains et marche vers le nord. Là où il tombe, on l'enterre ; la basilique s'élève sur sa tombe.
- **Sur Telluris (proposé)** : Denis est un **paladin de la Butte**, à l'Âge des Remparts, avant les portails. Une bête le décapite sur la Butte. Il marche vers le nord sa tête entre les mains, et la bête le suit sans jamais le rattraper. Là où il tombe, elle s'arrête et ne va pas plus loin. On bâtit une **auberge-relais** sur sa tombe ; elle est devenue un **monastère-relais** avec les monothéismes. Le vieux chemin qu'il a suivi s'appelle encore **le Chemin du Saint**. La grande route l'a abandonné depuis longtemps, parce qu'elle faisait un coude que personne ne savait expliquer.

**Marcel et le serpent** (le dragon de saint Marcel, légende parisienne du Vᵉ siècle).
- Sur la Terre : un serpent monstrueux hante le tombeau d'une femme, aux portes de Paris. L'évêque Marcel le frappe de sa crosse, lui passe son étole au cou et l'emmène hors de la ville. Le serpent disparaît. **Il n'est pas tué**, et la légende ne dit pas où il est allé.
- **Sur Telluris (proposé)** : Marcel est un vieil homme au **bâton** (ni évêque ni prêtre) qui fait sortir le serpent de Lutecia et le perd de vue. Dans les faubourgs, on dit « emmené par Marcel » de ce qui a disparu sans qu'on sache où.

Les deux récits **se contredisent** sur le Chemin : selon le premier, la bête s'y est arrêtée derrière Denis ; selon le second, Marcel l'y a conduite bien plus tard. Ce n'est peut-être pas la même bête. **Ce n'est jamais tranché.**

## 3. Scénario proposé

1. **Montmartre.** Au rang C, Bouchard propose l'escorte `quete:escorte_montmartre_route_de_saint_denis`. Trois convois sont arrivés au Relais de Saint-Denis avec des blessés, mais **sans aucun mort**, ce qui l'inquiète plus que des morts. « Ils ne cherchaient pas à tuer. Ils cherchaient à faire sortir les chariots de la route. »
2. **La route du nord.** Une rencontre (comme *La route silencieuse*) : loups sur les flancs, corneilles au-dessus. Ils rabattent le convoi vers **le Chemin du Saint**, envahi de ronces, qui quitte la grande route.
3. **Le coude du Chemin.** Combat : le serpent, dans les ruines d'une borne et d'un ancien muret de pierres sèches. Les loups restent à la lisière : ils attendent les restes. Sur la Terre, loups et corbeaux chassent réellement ensemble.
4. **Le Relais de Saint-Denis.** Frère Hilduin reçoit le convoi et montre la dalle sous laquelle Denis serait tombé.
5. **Retour à Montmartre.** Bouchard écoute le rapport, puis Dame Geneviève, qui voit la route du nord depuis le Sacré-Cœur, ajoute une réplique.

**Protégés (proposés) :**

| Prénom Nom | Lignée | Description |
|---|---|---|
| Perrine Lenoir | humaine | Marchande de cire et de chandelles pour le relais. Elle a déjà fait la route deux fois et a été rabattue deux fois. Elle refuse qu'on la plaigne. |
| Aubry Tanneguy | nain | Charretier. Il conduit le chariot et ne le quittera pour rien au monde, pas même quand il le faudrait. `se_defend`. |
| Ysoré | elfe | Novice qui rejoint le relais. Il récite la marche de Denis à voix basse, et la récite de travers quand il a peur. |

**PNJ neuf :**

| Rôle | Lignée | Nom | Ce qu'il croit |
|---|---|---|---|
| Frère portier du relais | elfe (très vieux) | Frère Hilduin | La bête du Chemin est celle qui a décapité Denis. Elle s'arrête là où il est tombé, et le relais existe pour que la route ne l'oublie pas. Il a lui-même écrit la *Vie de Denis* que lisent les novices, et il admet qu'il y a mis « ce qu'on lui a raconté ». |

## 4. Dialogues clés (proposés)

**Bouchard — proposition**
> Bouchard a déroulé une carte de la route du nord sur le registre. Trois croix au crayon, toutes au même endroit. « Trois convois pour le Relais de Saint-Denis. Tous arrivés. Des blessés, des chariots griffés, pas un mort. » Il tapote les croix. « Une bête qui attaque, elle tue ou elle mange. Celles-là poussaient. Elles faisaient sortir les chariots de la route, toujours au même coude. Je n'aime pas ce que je ne comprends pas, {prenom}. »

**Bouchard — instruction**
> « Vous ne quittez pas la grande route. Quoi qu'il arrive sur les flancs. » Un temps. « Et si vous la quittez quand même, regardez où l'on vous emmène avant de regarder qui vous pousse. »

**Frère Hilduin — au relais**
> Le frère portier, un elfe si vieux que sa peau semble de parchemin, vous mène jusqu'à une dalle usée au pied de la basilique. « Il est tombé ici, sa tête entre les mains. La bête qui le suivait s'est arrêtée au coude, et elle n'a jamais passé ce point. » Il sourit à peine. « C'est moi qui ai écrit sa Vie, pour les novices. J'y ai mis ce qu'on m'a raconté. Je ne jurerais pas que tout est vrai. »

**Bouchard — rapport**
> Il écoute jusqu'au bout. « Pas un donjon à deux lieues, j'ai fait demander à l'Enclos. Les Templiers n'ont rien. » Il replie la carte. « Elle était là avant la route. Avant le relais, peut-être avant les murs. On a fait un coude pour l'éviter, puis on a oublié pourquoi, et un jour quelqu'un a coupé au plus court. »

**Dame Geneviève — après (Sacré-Cœur)**
> Elle ne quitte pas le ciel des yeux. « D'ici, le Chemin du Saint dessine un coude autour de rien. Je le regarde depuis des années. » Un silence. « Les vieux du faubourg disent qu'on l'a emmenée là. Marcel, avec son bâton. Le frère dit qu'elle s'est arrêtée derrière Denis. Moi, je dis qu'une bête ne s'arrête pas pour un mort. »

## 5. Le doute qui reste

- **Bouchard** : elle était là **avant** la route, avant les donjons, avant les portails. C'est la thèse de la vérité du monde, mais il ne peut pas la prouver.
- **Frère Hilduin** : c'est la bête de Denis, et elle s'arrête là où il est tombé. Pourtant, c'est lui qui a écrit la légende.
- **Le faubourg** (par Geneviève) : Marcel l'a emmenée. Mais où ? Et est-ce la même bête ?
- **Ce qui est resté ouvert** : pourquoi les loups rabattent-ils **maintenant** ? Personne ne le sait.

## 6. Contenu en jeu

`dev/gen_route_saint_denis.py` → **un seul** `jsons/route_saint_denis_a_importer.json` (21 docs) ; verrouillé par `tests/test_route_saint_denis.py`.

- Relus du dump et fusionnés : `lieu:montmartre` (la variante de la route silencieuse part dès sa quête réussie, la variante Saint-Denis arrive) et `pnj:genevieve_du_sacre_coeur` (deux répliques : pendant, après).
- Neufs : `pnj:bouchard_de_clignancourt_saint_denis` (il reprend aussi les scènes d'après la route silencieuse) · `lieu:chemin_du_saint` (France (45,11), visible pendant l'escorte) et sa gardienne `pnj:perrine_lenoir_chemin_du_saint` · `lieu:coude_du_chemin_du_saint` + `donjon:chemin_du_saint` (un serpent, grades 2-3, protégés dans la salle) · `lieu:relais_de_saint_denis` (France (45,10), ouvert par la victoire au coude) et `pnj:frere_hilduin` · `espece:serpent_de_marcel`, sa carcasse et sa découpe.
- Serpent mesuré entre les planchers C et B (`potentiel.potentiel_menace`, verrouillé).
- Ajustement de texte : Bouchard ne dit plus « ne quittez pas la grande route ». Le relais ne s'atteint que par le coude, donc les loups ferment la grande route et rabattent le convoi : c'est la mécanique même de la quête.

**Images livrées (08/11)** : `battle_maps/coude_du_chemin_du_saint.jpg` (livrée en 1376×768, rognée à **1376×733** : y 20 → 753, pour que son quadrillage dessiné tombe sur **30 × 16 cases** ; grille `GRILLE_COUDE` relevée case par case), `towns/chemin_du_saint.jpg`, `towns/relais_de_saint_denis.jpg`, `monsters/serpent_de_marcel_transparent.png`, `pnj/frere_portier_Hilduin_elfe_m.jpg`, `pnj/marchande_de_cire_Perrine_Lenoir_humain_f.jpg` (PNJ et carte de protégée). Sans portrait : Aubry et Ysoré (initiale sur la carte 👥).

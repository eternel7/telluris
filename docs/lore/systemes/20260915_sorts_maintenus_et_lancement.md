# Sorts maintenus et lancement

- **Source :** [conversation ChatGPT](https://chatgpt.com/g/g-p-6a836af71c6c8191a84e3d2ec701c896/c/6aa8dc52-d774-83ed-8e5d-e2589699202e)
- **Créée :** 15/09/2026 · **mise à jour :** 16/09/2026
- **Messages :** 16

---

## ✍️ Auteur — 15/09/2026

Est ce que des sorts maintenus doivent empêcher le sorcier d'effectuer de nouveau sorts? Un sort maintenu ne s'arrête que lorsque le jetteur de sort n'a plus les pm pour le maintenir.  Le coût en pm est a dépenser à chaque tour/round. Exemples un mur de feu ou une invocation.

---

## 🤖 ChatGPT — 15/09/2026

Oui. Pour **Telluris**, je te conseillerais que les sorts maintenus **n'empêchent pas le sorcier de lancer d'autres sorts**.

Cela donne une mécanique assez naturelle :

- Un sort instantané est payé au lancement.
- Un sort maintenu coûte des **PM à chaque round**.
- Tant que le sorcier peut payer le coût, le sort continue.
- Le sorcier reste libre de lancer d'autres sorts pendant ce temps.
- Si, au début ou à la fin du round selon la règle que tu choisis, il ne peut plus payer le coût, le sort s'arrête.



### Je ferais cependant une distinction importante

Le fait de maintenir un sort ne devrait pas être **gratuit en termes d'attention**, même si cela ne bloque pas les autres sorts.

Par exemple :

| Type de magie | Exemple | Maintien | Peut lancer d'autres sorts ? |
|---|---|---:|---|
| Sort instantané | Boule de feu | Non | Oui |
| Sort maintenu | Mur de feu | X PM/round | Oui |
| Invocation maintenue | Golem invoqué | X PM/round | Oui |
| Protection maintenue | Bouclier magique | X PM/round | Oui |
| Contrôle maintenu | Immobilisation | X PM/round | Oui |

Ainsi, un mage pourrait avoir :

> **Invocation : 5 PM/round**  
> **Mur de feu : 3 PM/round**

et continuer à combattre avec des sorts instantanés.

Mais il paierait **8 PM à chaque round** tant que les deux effets sont actifs.

### Le point intéressant : les limites viennent des PM

Cela crée une mécanique très lisible :

**Plus le mage maintient de choses, plus son réservoir de PM se vide rapidement.**

Exemple :

Un sorcier possède **30 PM**.

Il invoque une créature coûtant **6 PM/round**.

Il crée ensuite un mur de feu coûtant **4 PM/round**.

Il dépense donc :

**10 PM/round**

Il peut continuer à lancer des sorts ponctuels, mais il ne pourra maintenir cette configuration que pendant **3 rounds** avant de devoir abandonner l'un des effets.

Cela donne aux sorts maintenus une vraie puissance sans avoir besoin d'une règle artificielle du type *« concentration : impossible de lancer autre chose »*.

### Je rajouterais une règle de surcharge

Pour éviter qu'un sorcier puisse accumuler une quantité absurde d'effets maintenus, tu pourrais avoir :

> **Un sorcier peut maintenir autant de sorts qu'il le souhaite, à condition de pouvoir payer leur coût en PM.**

C'est volontairement très permissif.

Un mage très puissant pourrait donc être entouré d'une invocation, d'un bouclier, d'un mur de feu et d'une aura magique simultanément — **mais sa consommation de PM deviendrait énorme**.

Cela correspond assez bien à ton système où le mana est une ressource physique et économique importante.

### Une règle que je recommande fortement

Le coût de maintien devrait être payé **au début du tour du lanceur**, plutôt qu'à la fin.

Exemple :

> **Début du tour du mage → paiement des PM de maintien → les sorts restent actifs → le mage agit normalement.**

S'il n'a plus assez de PM :

> **le sort maintenu s'arrête immédiatement.**

Cela évite les situations ambiguës où un joueur bénéficie du dernier round d'un sort alors qu'il n'avait déjà plus les moyens de le maintenir.

**En résumé :**

> **Maintenir un sort ne consomme pas une action et n'interdit pas de lancer d'autres sorts. Il impose simplement une dépense récurrente de PM à chaque round.**

Je pense que c'est particulièrement adapté à Telluris : **la limite du sorcier est son énergie magique, pas une interdiction abstraite de faire deux choses à la fois.**

---

## ✍️ Auteur — 15/09/2026

Ok. Maintenant que penses-tu et comment decrirais tu le fonctionnement de sort dont le lancement consomme plus d'un point d'action. Par exemple le sort de météor qui pour être lancé nécessite plus de points d'actions que le jetteur de sort ne peut en un round.

---

## 🤖 ChatGPT — 15/09/2026

Je trouve cette mécanique intéressante, surtout pour les sorts très puissants comme le météore. Je la traiterais comme une **incantation longue**, distincte du simple maintien.

L'idée fondamentale serait :

> **Le coût en points d'action (PA) représente le temps nécessaire pour construire et libérer le sort. Si le sort demande plus de PA que le lanceur n'en possède dans un round, l'incantation se poursuit sur les rounds suivants.**

### Exemple : Météore

Imaginons :

**Météore**
- Coût : 20 PM
- Temps d'incantation : **6 PA**
- Le sorcier possède : **3 PA / round**

Il commence au round 1 :

**Round 1**
- dépense 3 PA
- progression : 3 / 6
- le météore n'est pas encore lancé.

**Round 2**
- dépense 3 PA
- progression : 6 / 6
- le météore est lancé.

Cela signifie que pendant deux rounds, le sorcier est en train de préparer son sort.

---

## Je ferais une distinction avec les sorts maintenus

C'est important pour la lisibilité du système.

### Sort maintenu

Le sort est **déjà lancé**.

> « Je maintiens mon mur de feu. »

Il coûte X PM par round mais ne consomme plus de PA.

### Sort à incantation longue

Le sort **n'est pas encore lancé**.

> « Je commence à invoquer le météore. »

Il consomme progressivement des PA jusqu'à atteindre son temps d'incantation.

On aurait donc :

**Incantation → lancement → éventuellement maintien**

C'est une distinction assez propre.

---

# Le lanceur peut-il faire autre chose pendant l'incantation ?

Je lui permettrais de faire certaines choses, mais **pas de recommencer à lancer un autre sort nécessitant une incantation simultanée**.

Par exemple, pendant son météore :

**Autorisé :**
- se déplacer, éventuellement avec une pénalité ;
- parler ;
- utiliser certains objets ;
- effectuer des actions simples ;
- maintenir des sorts déjà actifs.

**Interdit ou fortement limité :**
- lancer un second sort à incantation ;
- effectuer une action qui exige une concentration importante ;
- subir certaines interruptions.

Cela donne au joueur un vrai choix tactique :

> **« Est-ce que je continue mon météore pendant deux rounds en prenant le risque d'être interrompu, ou est-ce que je l'abandonne pour lancer quelque chose d'immédiat ? »**

---

# J'ajouterais surtout la possibilité d'interrompre l'incantation

C'est, à mon avis, ce qui rendrait cette mécanique intéressante en combat.

Supposons que le météore nécessite **6 PA**.

Le mage fait :

> Round 1 : 3/6 PA

Un gobelin arrive et le frappe.

Le mage peut alors :

> **continuer l'incantation**

ou

> **interrompre l'incantation**

S'il l'interrompt, il perd éventuellement les PA déjà investis, mais il peut recommencer plus tard.

Cela donne une vraie valeur aux personnages qui protègent le mage.

---

# Et surtout : que se passe-t-il si le mage est interrompu ?

Je te conseille de ne pas faire une règle binaire du genre :

> « Une attaque = incantation automatiquement perdue. »

Cela rendrait les sorts longs pratiquement inutilisables.

Je préférerais une mécanique de **test d'interruption**.

Par exemple :

> Lorsqu'un lanceur subit une attaque pendant une incantation, il effectue un test de concentration.

Selon le résultat :

- **Réussite critique** → l'incantation continue normalement.
- **Réussite** → l'incantation continue, éventuellement avec une pénalité.
- **Échec** → progression perdue pour le round ou recul de quelques PA.
- **Échec critique** → incantation interrompue.

Ainsi, un mage peut véritablement devenir un **artilleriste** que ses alliés doivent protéger.

---

# Une autre possibilité très intéressante : l'incantation peut dépasser plusieurs rounds

Je ne limiterais pas le système à « maximum deux rounds ».

Un sort pourrait demander :

| Sort | PA nécessaires |
|---|---:|
| Éclair | 1 |
| Boule de feu | 2 |
| Foudre | 3 |
| Invocation majeure | 5 |
| Météore | 6 |
| Portail majeur | 12 |
| Rituel de résurrection | 20 |

Avec un personnage disposant de **3 PA par round** :

- sort à 3 PA → immédiat ;
- sort à 5 PA → 2 rounds ;
- sort à 6 PA → 2 rounds ;
- sort à 12 PA → 4 rounds ;
- rituel à 20 PA → 7 rounds.

Cela permet de faire évoluer naturellement les sorts vers des **rituels de combat ou de siège**.

---

## Je formaliserais donc la règle ainsi

> ### Incantation longue
> Certains sorts nécessitent plusieurs Points d'Action pour être lancés. Lorsque le nombre de PA requis dépasse les PA disponibles au cours d'un round, l'incantation se poursuit automatiquement au round suivant.
>
> À chaque tour, le lanceur peut consacrer ses PA restants à l'incantation. La progression est conservée jusqu'à atteindre le nombre de PA requis.
>
> Le sort n'est considéré comme lancé qu'une fois la totalité des PA nécessaires dépensée.
>
> Tant que l'incantation n'est pas terminée, le lanceur peut continuer à maintenir ses sorts actifs, mais ne peut pas commencer une autre incantation.
>
> Certaines actions ou certains événements peuvent provoquer un test d'interruption.

### Et je séparerais les trois notions

**PA de lancement**
→ temps nécessaire pour déclencher le sort.

**PM de lancement**
→ énergie magique consommée pour créer le sort.

**PM de maintien**
→ énergie consommée chaque round pour conserver un effet actif.

Cela donnerait par exemple :

**Météore**
> Incantation : 6 PA  
> Coût : 15 PM  
> Maintien : aucun

**Mur de feu**
> Incantation : 2 PA  
> Coût : 5 PM  
> Maintien : 3 PM/round

**Invocation**
> Incantation : 4 PA  
> Coût : 8 PM  
> Maintien : 4 PM/round

C'est, à mon sens, une bonne base pour le système de magie de Telluris, parce que **PA et PM représentent deux contraintes différentes : le temps nécessaire pour produire la magie et l'énergie nécessaire pour la produire.**

---

## ✍️ Auteur — 15/09/2026

Résume les concepts et règles de sort maintenu et de coût en point d'action (temps d'incantation). Ajoute sous la même forme le concept de sort de drain de PV ou PM qui transforme les dégâts de PV fait à l'ennemi, en PV ou PM pour le jetteur de sort. Le concept de drain est à expliquer en une seule règle. Rajoute aussi les sorts effectuant des dégâts aux PM et non les PV. Les deux types de dégâts pouvant être cumulé dans un même sort.

---

## 🤖 ChatGPT — 15/09/2026

Voici une synthèse sous une forme homogène, utilisable comme base de règles pour le système de magie de **Telluris**.

### Sort maintenu
Un **sort maintenu** est un sort dont l'effet persiste après son lancement et qui nécessite une dépense régulière de PM pour rester actif.

- Le sort est lancé normalement et son coût initial en PM est payé.
- À chaque round, le jeteur doit dépenser le **coût de maintien en PM**.
- Tant qu'il peut payer ce coût, le sort reste actif.
- Le maintien ne consomme pas de PA et **n'empêche pas le jeteur de lancer d'autres sorts**.
- Si le jeteur ne peut plus payer le coût de maintien, le sort s'arrête.

**Exemples :** mur de feu, invocation, bouclier magique.

---

### Temps d'incantation
Certains sorts nécessitent plusieurs **Points d'Action (PA)** pour être lancés. Lorsque leur coût dépasse les PA disponibles en un round, leur lancement se poursuit sur les rounds suivants.

- Le jeteur dépense ses PA disponibles pour faire progresser l'incantation.
- Les PA investis dans l'incantation sont conservés d'un round à l'autre.
- Le sort n'est lancé qu'une fois la totalité des PA nécessaires dépensée.
- Pendant l'incantation, le jeteur peut maintenir ses sorts déjà actifs, mais ne peut pas commencer une autre incantation.
- Une interruption peut éventuellement empêcher ou retarder la progression de l'incantation selon les règles propres au sort ou à l'interruption.

**Exemple :** un météore nécessitant 6 PA lancé par un mage disposant de 3 PA par round demande deux rounds d'incantation.

---

### Sort de drain
Un **sort de drain** convertit les dégâts infligés à l'ennemi en une récupération de ressources pour le jeteur : les dégâts de PV peuvent ainsi restaurer des **PV ou des PM** selon l'effet du sort.

> **Drain : pour chaque quantité de dégâts de PV infligée par le sort, une quantité correspondante de PV ou de PM est récupérée par le jeteur selon le type de drain, dans la limite éventuellement fixée par le sort.**

Le drain ne récupère donc que sur les **dégâts effectivement infligés** à la cible, et non sur les dégâts théoriques du sort.

---

### Dégâts aux PM
Certains sorts infligent des dégâts directement aux **Points de Mana (PM)** de leur cible plutôt qu'à ses PV.

- Les dégâts de PM réduisent directement les PM disponibles de la cible.
- Ils peuvent représenter une attaque contre les réserves magiques ou la capacité de la cible à utiliser sa magie.
- Ils ne réduisent pas directement les PV.

Un sort peut cependant infliger **simultanément des dégâts aux PV et aux PM**.

**Exemple :**

> **Éclair siphonnant** : inflige 10 dégâts aux PV et 5 dégâts aux PM.

Cela permet notamment de créer des sorts spécialisés contre les lanceurs de sorts, mais aussi des effets hybrides capables d'affaiblir **à la fois le corps et les réserves magiques**.

---

## ✍️ Auteur — 15/09/2026

Décrit de la même manière le concept de sort de téléportation

---

## 🤖 ChatGPT — 15/09/2026

### Sort de téléportation

Un **sort de téléportation** permet au jeteur de déplacer instantanément une créature ou un objet d'un emplacement à un autre, sans parcourir physiquement la distance qui les sépare.

- Le jeteur doit définir une **destination valide** avant ou pendant l'incantation.
- La destination doit être accessible selon les conditions propres au sort : emplacement connu, visible, marqué, portail, distance maximale, etc.
- La téléportation déplace instantanément la cible une fois l'incantation terminée.
- Le sort peut cibler le jeteur lui-même, une autre créature, plusieurs créatures ou un objet selon ses caractéristiques.
- La téléportation ne permet pas nécessairement de franchir toutes les protections : certains lieux ou effets magiques peuvent **bloquer, dévier ou empêcher** une téléportation.
- Une téléportation peut nécessiter plusieurs PA d'incantation comme n'importe quel sort complexe, mais le déplacement lui-même est instantané.
- Le coût en PM dépend de la puissance du déplacement : distance, nombre de cibles, masse transportée et éventuelles contraintes particulières.

**Exemple :** un sort permettant au jeteur de se téléporter à 20 mètres peut demander 2 PA et 5 PM. Une téléportation longue distance entre deux lieux connus peut nécessiter davantage de PA et de PM.

> **Principe : la téléportation supprime le déplacement physique entre le point de départ et la destination ; le temps et le coût du sort correspondent à la puissance magique nécessaire pour réaliser ce déplacement.**

---

## ✍️ Auteur — 15/09/2026

Faire de même pour les concepts :
- téléportation (en combat "saut" d'une case à une autre)
- dépenser des PV pour utiliser une compétence ou un sort, 
- lien de vie / protection

---

## 🤖 ChatGPT — 15/09/2026

Voici les trois concepts dans la même logique que les précédents.

### Téléportation en combat — Saut

Un **sort de saut** permet au jeteur de se déplacer instantanément d'une case à une autre sans parcourir les cases intermédiaires.

- Le jeteur définit une **case de destination valide**.
- Le déplacement est instantané : les cases situées entre le départ et l'arrivée ne sont pas parcourues.
- Le saut peut permettre de franchir des obstacles, des créatures ou certains terrains infranchissables par un déplacement normal.
- La distance maximale du saut dépend du sort.
- Le saut peut cibler le jeteur lui-même ou, selon le sort, une autre créature.
- Le saut ne permet pas nécessairement de traverser toutes les protections ou zones magiques : certaines peuvent empêcher la téléportation.
- Le saut peut être instantané ou nécessiter plusieurs PA d'incantation selon la puissance du sort.

**Exemple :** un sort de Saut permet au mage de se téléporter jusqu'à 4 cases. Il peut passer instantanément de sa case à une case située derrière un mur ou un ennemi, si la destination est valide.

> **Principe : le saut est une téléportation de courte portée utilisée comme déplacement tactique, permettant de passer instantanément d'une case à une autre sans parcourir les cases intermédiaires.**

---

### Dépense de PV

Certains sorts ou compétences peuvent utiliser les **Points de Vie (PV) du jeteur comme ressource**.

- L'utilisation du sort ou de la compétence retire directement le coût indiqué des PV du jeteur.
- Cette dépense est volontaire et constitue le prix à payer pour utiliser l'effet.
- Les PV dépensés ne sont pas considérés comme des dégâts infligés par un adversaire.
- La dépense peut avoir lieu au lancement ou selon le fonctionnement du sort.
- Un personnage ne peut pas dépenser plus de PV qu'il n'en possède, sauf si une règle particulière autorise une dette de vie ou un effet similaire.

**Exemple :** un sort coûte **10 PV**. Le mage possède 35 PV : après le lancement, il lui reste 25 PV.

> **Principe : certains effets peuvent remplacer tout ou partie de leur coût en PM par une dépense directe de PV, faisant de la vie du jeteur une ressource magique utilisable.**

---

### Lien de vie / Protection

Un **lien de vie** est un effet magique qui établit un lien entre deux ou plusieurs créatures et permet au jeteur ou à une créature protégée de **transférer, absorber ou partager les dégâts subis** selon les règles du sort.

- Le lien désigne une ou plusieurs créatures concernées.
- Lorsqu'une créature liée subit des dégâts, le sort peut transférer tout ou partie de ces dégâts vers le protecteur ou une autre créature liée.
- Le transfert ne crée pas de nouveaux dégâts : il **déplace la perte de PV** d'une cible vers une autre.
- Le sort peut également réduire les dégâts reçus par la cible protégée avant d'appliquer la partie transférée.
- Le lien peut être maintenu pendant plusieurs rounds et suivre alors les règles des **sorts maintenus**.
- Le lien prend fin lorsque sa durée est écoulée, que le sort est interrompu ou que ses conditions de maintien ne sont plus respectées.

**Exemple :** un paladin établit un lien avec un allié. Lorsqu'un ennemi inflige 20 dégâts à l'allié, le lien peut transférer 10 dégâts au paladin. L'allié perd alors 10 PV et le paladin 10 PV.

> **Principe : un lien de vie permet de répartir ou de transférer la perte de PV entre des créatures liées afin de protéger une cible au prix de la vie d'une autre.**

---

## ✍️ Auteur — 16/09/2026

Liste des mécaniques qui n'auraient pas encore été encore proposées, sans en expliquer le concept de manière trop longue, au maximum une seule petite phrase.

---

## 🤖 ChatGPT — 16/09/2026

En restant sur les mécaniques déjà évoquées dans nos échanges, les principales mécaniques qui **n'ont pas encore été formalisées** seraient :

### Ressources et coûts
- **Coût mixte PV/PM** — un sort peut payer son coût en combinant une dépense de PV et de PM.
- **Coût conditionnel** — le coût d'un sort varie selon la cible, la distance ou les circonstances.
- **Réduction/augmentation de coût** — certains effets peuvent modifier temporairement le coût en PA, PV ou PM d'un sort.

### Effets sur les caractéristiques
- **Buff** — augmente temporairement une caractéristique, compétence ou capacité.
- **Debuff** — réduit temporairement une caractéristique, compétence ou capacité.
- **Altération d'état** — applique un état particulier comme poison, paralysie, peur, silence ou sommeil.
- **Dissipation** — supprime un effet magique actif sur une cible.
- **Purification** — retire une altération négative ou une corruption.
- **Vol de caractéristique** — réduit temporairement une caractéristique de la cible pour augmenter celle du jeteur.

### Contrôle et déplacement
- **Immobilisation** — empêche ou limite les déplacements d'une cible.
- **Contrôle de cible** — impose temporairement certaines actions ou déplacements à une créature.
- **Attraction / répulsion** — déplace une cible vers ou à l'écart d'un point donné.
- **Création de terrain** — transforme certaines cases en zone particulière affectant les déplacements ou les actions.
- **Passage à travers les obstacles** — permet de traverser temporairement certaines matières ou structures.

### Défense et réaction
- **Bouclier magique** — absorbe une quantité déterminée de dégâts avant de disparaître.
- **Réduction de dégâts** — diminue directement les dégâts reçus sans absorber une quantité fixe.
- **Renvoi de dégâts** — retourne une partie des dégâts subis vers leur source.
- **Contre-sort** — interrompt ou neutralise un sort en cours de lancement.
- **Sort réactionnel** — peut être lancé en réaction à une action adverse plutôt que pendant son propre tour.

### Cibles et propagation
- **Zone d'effet** — affecte toutes les créatures ou cases correspondant à une zone définie.
- **Propagation** — un effet se transmet d'une cible à une autre selon certaines conditions.
- **Chaîne** — un même sort frappe successivement plusieurs cibles.
- **Ciblage multiple** — permet de sélectionner plusieurs cibles indépendantes.
- **Effet cumulatif** — plusieurs applications du même effet peuvent s'empiler ou renforcer son intensité.

### Temps et déclenchement
- **Durée limitée** — un effet reste actif pendant un nombre déterminé de rounds.
- **Délai** — un sort produit son effet après un nombre déterminé de rounds.
- **Déclenchement conditionnel** — un effet préparé se déclenche lorsqu'une condition définie est remplie.
- **Sort préparé** — le jeteur prépare un sort à l'avance pour pouvoir le déclencher ultérieurement.
- **Canalisation** — le jeteur consacre continuellement ses actions à un effet tant qu'il souhaite le poursuivre.

### Mort et récupération
- **Résurrection** — ramène une créature morte à la vie sous certaines conditions.
- **Régénération** — restaure progressivement des PV ou PM pendant plusieurs rounds.
- **Récupération différée** — restitue une ressource après un délai plutôt qu'immédiatement.
- **Seuil de mort** — certains effets se déclenchent automatiquement lorsqu'une créature atteint un seuil critique de PV.

### Magie et espace
- **Création d'objet magique temporaire** — matérialise un objet ou équipement magique pour une durée limitée.
- **Invocation de créature** — fait apparaître une créature contrôlée ou alliée.
- **Création de portail** — crée temporairement un passage entre deux emplacements.
- **Ancrage magique** — empêche certaines téléportations ou déplacements magiques dans une zone.
- **Détection magique** — révèle les créatures, objets, effets ou traces de magie présents dans une zone.



Les mécaniques déjà établies sont donc notamment : **maintien, temps d'incantation en PA, drain PV/PM, dégâts aux PM, téléportation/saut, dépense de PV, et lien de vie/protection**.

---

## ✍️ Auteur — 16/09/2026

Buff et debuff sont déjà possibles.
Les zones d'effet sont déjà possibles.
Les effets cumulatifs sont exclus.
La durée est déjà potentiellement limitée.
La proposition de délai me semble très similaire au temps d'incantation. 
La canalisation me semble très similaire à un sort maintenu.
Les invocations de créatures sont déjà gérées.
La création de portails qui permet le passage entre deux emplacements est actuellement déjà envisagée et consiste uniquement à un saut d'une case à une autre en mode combat. Pas de déplacement facilité entre des lieux, car la magie des portails est quelque chose de bien trop important dans le monde de Telluris pour être maîtrisé par les magiciens, quels qu'ils soient.

Réécris donc ta proposition en fonction de ces remarques.

---

## 🤖 ChatGPT — 16/09/2026

Oui. En retirant les mécaniques que tu considères déjà couvertes ou incompatibles avec le fonctionnement de Telluris, la liste se resserre.

### Mécaniques encore pertinentes

#### Effets sur les cibles
- **Altération d'état** — applique un état particulier à une cible, comme poison, paralysie, peur, sommeil ou silence.
- **Dissipation** — supprime un effet magique actif sur une cible.
- **Purification** — retire une altération négative, une maladie magique ou une corruption.
- **Vol de caractéristique** — réduit temporairement une caractéristique de la cible pour augmenter celle du jeteur.

#### Déplacement et contrôle
- **Immobilisation** — empêche totalement ou partiellement une cible de se déplacer.
- **Attraction / répulsion** — déplace une cible de plusieurs cases vers ou à l'écart d'un point.
- **Contrôle de cible** — permet d'imposer temporairement certaines actions ou déplacements à une créature.
- **Traversée** — permet à une créature de franchir temporairement un obstacle ou un type de terrain normalement infranchissable.

#### Défense et interaction avec les sorts
- **Bouclier magique** — absorbe une quantité déterminée de dégâts avant de disparaître.
- **Réduction de dégâts** — diminue directement les dégâts reçus par une cible.
- **Renvoi de dégâts** — retourne une partie des dégâts reçus vers leur source.
- **Contre-sort** — interrompt ou neutralise un sort avant qu'il ne produise son effet.
- **Sort réactionnel** — permet de lancer un sort en réponse à une action ou un événement plutôt que pendant son propre tour.

#### Ciblage et propagation
- **Propagation** — transmet un effet d'une cible à une autre lorsque certaines conditions sont réunies.
- **Chaîne** — fait successivement passer un même effet d'une cible à plusieurs autres.
- **Ciblage multiple** — permet à un même sort de sélectionner plusieurs cibles indépendantes.

#### Déclenchement
- **Déclenchement conditionnel** — un effet déjà actif ou préparé se déclenche lorsqu'une condition déterminée est remplie.
- **Sort préparé** — permet de préparer un sort afin de le déclencher ultérieurement selon une condition définie.

#### Ressources
- **Coût mixte PV/PM** — permet de payer un même sort avec une combinaison de PV et de PM.
- **Coût conditionnel** — fait varier le coût en fonction de la cible, de la distance ou des circonstances.
- **Modification de coût** — un effet peut temporairement augmenter ou réduire le coût en PA, PV ou PM d'un sort.

#### Récupération
- **Régénération** — restaure progressivement des PV ou PM pendant plusieurs rounds.
- **Récupération différée** — restitue une ressource après un délai ou lorsque certaines conditions sont remplies.

#### Magie
- **Détection magique** — révèle la présence de magie, d'effets magiques, de créatures ou d'objets selon les capacités du sort.
- **Ancrage magique** — empêche ou limite les effets de téléportation dans une zone.
- **Création magique temporaire** — matérialise temporairement un objet ou une structure magique.

### Deux points que je sortirais explicitement de la liste

**Portail longue distance :** exclu du système de sorts. Dans Telluris, la maîtrise des véritables portails appartient à une connaissance exceptionnelle liée à l'histoire des Architectes et ne constitue pas une magie ordinaire utilisable par un mage.

**Délai / canalisation :** exclus comme mécaniques distinctes, puisqu'ils peuvent être représentés respectivement par le **temps d'incantation en PA** et le **maintien en PM**.

Cela laisse surtout une distinction intéressante à formaliser ensuite entre **effets instantanés, effets maintenus, incantations longues, réactions et déclenchements conditionnels**.

---

## ✍️ Auteur — 16/09/2026

Pour moi le coup mix PVPM est déjà aussi couvert. La régénération de PV de PM est, elle aussi, déjà couverte. 

Je ne sais pas si jamais c'est une bonne idée ou pas et j'aimerais en discuter. Il y a le transport des objets, des choses, est aussi quelque chose d'un peu compliqué. Quelque chose qu'on voit souvent dans des jeux ou surtout dans des dessins animés, c'est la bourse qui permet de mettre des objets de manière infinie à l'intérieur. Je ne sais pas si jamais ça doit être un item qui permet ça, ou si jamais c'est un sort ou une compétence. J'avoue que là, je trouve que c'est plus intéressant un item et je sais pas si jamais ça pourrait se traduire en une mécanique de sort ou de compétence. Qu'en penses-tu ? Reformule la liste en fonction de tous les nouveaux trucs que j'ai dits là.

---

## 🤖 ChatGPT — 16/09/2026

Oui, je suis plutôt d'accord avec ton intuition : **la bourse à espace infini devrait être un objet**, plutôt qu'un sort ou une compétence.

Cela permet de faire une distinction intéressante entre ce que permet naturellement la magie et ce qui relève de l'équipement.

### La bourse à espace infini

Je la verrais comme un **objet magique de stockage**, avec éventuellement plusieurs niveaux de qualité.

Son fonctionnement pourrait être très simple :

> **La bourse possède un espace intérieur plus grand que son volume extérieur et permet de stocker des objets sans augmenter proportionnellement son poids ou son encombrement.**

Je déconseillerais toutefois le « véritablement infini ». Une capacité extrêmement grande, voire pratiquement illimitée pour les besoins du jeu, donne le même confort sans créer des problèmes logiques comme y ranger une maison, une créature ou un autre objet de stockage.

Elle pourrait avoir des contraintes propres à l'item :
- poids maximal stockable ;
- volume maximal ;
- objets vivants interdits ;
- impossibilité de stocker certains objets magiques ;
- accès nécessitant une action ;
- objets récupérables uniquement individuellement.

Cela en fait surtout une **mécanique d'inventaire**, plutôt qu'une mécanique de magie de combat.

Je ne créerais donc pas de « sort de stockage » équivalent. Un mage pourrait éventuellement posséder une bourse magique, mais **le stockage dimensionnel n'est pas une catégorie de sort**.

---

## Liste révisée des mécaniques encore à envisager

En retirant maintenant le coût mixte PV/PM et la régénération, ainsi que toutes les mécaniques précédemment écartées :

### Effets sur les cibles
- **Altération d'état** — applique un état particulier à une cible, comme poison, paralysie, peur, sommeil ou silence.
- **Dissipation** — supprime un effet magique actif sur une cible.
- **Purification** — retire une altération négative, une maladie magique ou une corruption.
- **Vol de caractéristique** — réduit temporairement une caractéristique de la cible pour augmenter celle du jeteur.

### Déplacement et contrôle
- **Immobilisation** — empêche totalement ou partiellement une cible de se déplacer.
- **Attraction / répulsion** — déplace une cible de plusieurs cases vers ou à l'écart d'un point.
- **Contrôle de cible** — permet d'imposer temporairement certaines actions ou déplacements à une créature.
- **Traversée** — permet de franchir temporairement un obstacle ou un terrain normalement infranchissable.

### Défense et interaction magique
- **Bouclier magique** — absorbe une quantité déterminée de dégâts avant de disparaître.
- **Réduction de dégâts** — diminue directement les dégâts reçus par une cible.
- **Renvoi de dégâts** — retourne une partie des dégâts reçus vers leur source.
- **Contre-sort** — interrompt ou neutralise un sort avant qu'il ne produise son effet.
- **Sort réactionnel** — permet de lancer un sort en réponse à une action ou un événement.

### Ciblage et propagation
- **Propagation** — transmet un effet d'une cible à une autre sous certaines conditions.
- **Chaîne** — fait successivement passer un même effet d'une cible à plusieurs autres.
- **Ciblage multiple** — permet à un même sort de sélectionner plusieurs cibles indépendantes.

### Déclenchement
- **Déclenchement conditionnel** — un effet se déclenche lorsqu'une condition déterminée est remplie.
- **Sort préparé** — permet de préparer un sort afin de le déclencher ultérieurement.

### Modification des coûts
- **Coût conditionnel** — fait varier le coût d'un sort selon la cible, la distance ou les circonstances.
- **Modification de coût** — augmente ou réduit temporairement le coût en PA, PV ou PM d'un sort.

### Magie et perception
- **Détection magique** — révèle la présence de magie, d'effets magiques ou d'objets selon les capacités du sort.
- **Ancrage magique** — empêche ou limite la téléportation dans une zone.
- **Création magique temporaire** — matérialise temporairement un objet ou une structure magique.

### Équipement et inventaire
- **Stockage dimensionnel** — un objet magique, comme une bourse enchantée, permet de transporter une quantité de matériel largement supérieure à ce que son volume extérieur laisserait supposer.

---

### Et je pense qu'il y a une conséquence intéressante pour Telluris

Je séparerais clairement **les mécaniques de personnage** et **les propriétés des objets**.

Par exemple :

| Mécanique | Nature |
|---|---|
| Téléportation / saut | Sort |
| Temps d'incantation | Propriété du sort |
| Maintien | Propriété du sort |
| Drain PV/PM | Propriété du sort |
| Dégâts PV/PM | Propriété du sort |
| Lien de vie | Sort |
| Buff / debuff | Effet de sort/compétence |
| Stockage dimensionnel | **Objet magique** |
| Arme magique | Objet |
| Armure magique | Objet |
| Cristal de mana | Objet/ressource |

Cela évite surtout que **toute possibilité fantastique devienne automatiquement un sort**. Dans Telluris, certains phénomènes peuvent être des propriétés d'objets rares, de techniques artisanales ou de connaissances perdues.

Et pour la bourse, cela ouvre même une possibilité intéressante : **les bourses à espace dimensionnel pourraient être des objets très anciens dont la fabrication est aujourd'hui impossible**, ce qui leur donnerait une place naturelle dans le lore sans banaliser la magie des portails.

---

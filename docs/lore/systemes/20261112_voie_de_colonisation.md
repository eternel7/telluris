# Voie de colonisation — décisions de l'Auteur

- **Arrêtées le :** 12/11/2026, par questionnaire
- **Séance d'origine :** [Progression des lieux de guilde](20260924_progression_des_lieux_de_guilde.md) (24 au 28/09/2026)
- **Statut :** tout ce qui suit est **décidé par l'Auteur**. Rien n'est encore en jeu.
- **Chiffres :** valeurs de départ, portées par le doc de règles `rules:colonisation` (`dev/gen_colonisation.py`).

La voie de colonisation est le pendant de la voie urbaine (Chambre → Logement → Maison → Demeure → Domaine, déjà en jeu).

---

## 1. Principes

- **But final** : une guilde d'aventuriers avec gestion de PNJ.
- **Deux voies** : en cité, on s'arrête au Domaine. Hors des cités, on fonde une implantation dans un lieu de type pays.
- L'implantation **évolue sur place** et se fortifie jusqu'à devenir une ville. Un bien urbain, lui, a un type figé.
- **Le fondateur ne fabrique rien** : tout métier est tenu par un PNJ.
- **Aucun tick de fond** : le temps écoulé est calculé au passage du fondateur.

## 2. Fonder

- **Site** : une case libre d'un lieu de type pays.
- **Distance** : au moins **6 cases** de toute Cité-État et **4 cases** d'une autre implantation.
- **Charte** : **4 or**, payée au maître de guilde d'aventuriers de la cité la plus proche. À égale distance, toutes les cités concernées se valent.
- **Prérequis** : **rang C** de la guilde au minimum.
- **Nombre** : une implantation par pays et par personnage.
- **Visibilité** : les autres joueurs la voient dès le campement.

## 3. La fiche de site

Six axes, lus sur la carte du pays autour de la case (terrain, eau, zones d'influence, tables de rencontres et de ressources, distance aux cités). Rien n'est saisi par site.

| Axe | Exemples |
|---|---|
| Eau | source, rivière, lac |
| Nourriture | fertilité, gibier, pêche |
| Matériaux | bois, pierre |
| Commerce | cité proche, fleuve, mer |
| Défense | hauteur, visibilité, abri naturel |
| Danger | monstres, tanière, donjon proche |

L'eau est un trait du site, pas un stock.

## 4. Les paliers

**Campement → Hameau → Bourgade → Village → Bourg → Petite ville → Ville**

Passage au palier suivant : des seuils atteints (population, postes tenus, fortification minimale), puis un **investissement dans l'aménagement qui change le statut** du lieu.

| Palier | Ce qu'il ouvre | Fortification minimale | Menace |
|---|---|---|---|
| Campement | logement du fondateur, stockage, feu | feu et surveillance | danger permanent |
| Hameau | premiers PNJ, cultures, élevage | palissade complète et porte | attaques occasionnelles |
| Bourgade | métiers et bâtiments spécialisés, boutique et auberge | fossé et tours | attaques occasionnelles |
| Village | production locale, Auberge d'aventuriers | enceinte et portes fortifiées | menaces contrôlables |
| Bourg | marché, grande auberge, administration | murailles | menaces exceptionnelles |
| Petite ville | quartiers spécialisés, nombreux services | murailles | menaces exceptionnelles |
| Ville | infrastructure complète, Guilde d'aventuriers | système défensif complet | rares mais majeures |

Seuils et prix de départ :

| Palier | Population | Postes nommés tenus | Aménagement de statut |
|---|---:|---:|---:|
| Hameau | 5 | 4 | 16 or |
| Bourgade | 15 | 12 | 60 or |
| Village | 40 | 24 | 200 or |
| Bourg | 100 | 40 | 600 or |
| Petite ville | 250 | 64 | 2 000 or |
| Ville | 600 | 100 | 6 000 or |

Les fortifications sont des aménagements. La menace devient plus rare et plus grave à mesure que le lieu grandit.

## 5. Sécurité et moral

Affichage : un palier **en mots**, avec le **détail chiffré** des facteurs. Les deux valeurs sont recalculées à la lecture, jamais stockées. La sécurité n'atteint jamais le maximum.

**Sécurité**, cinq familles de facteurs :

- défense physique : palissade, fossé, portes, tours, éclairage ;
- défense humaine : nombre et qualité des gardes ;
- environnement : relief, visibilité, danger du site ;
- logistique : état des quatre stocks ;
- connaissance du territoire : tanière identifiée ou non.

**Moral** : attaques récentes, morts, nourriture, logement, soignant présent, prospérité, expéditions réussies, réputation du fondateur.
Un moral bas ralentit les arrivées puis provoque des **départs**, PNJ nommés compris. Un moral haut attire.

**Nuit** : couverte d'office par les gardes en poste. Sans garde, elle est plus risquée.

**Feu**, deux réglages :

- grand feu : confort, moral, dissuasion ; mais visible de loin et gourmand en bois ;
- feu réduit : discret et économe ; mais vie plus dure.

**Écartés** : les anneaux de sécurisation du territoire, la mécanique de route.

## 6. La menace

**Faune territoriale par étapes** : une espèce du pays tient une tanière proche.

1. Elle est présente dans les environs.
2. Elle a remarqué le lieu.
3. Elle attaque les troupeaux et les réserves.
4. Sa tanière est localisée : on peut aller la vider.

**Attaque du lieu** :

- fondateur présent : un combat joué sur la carte du lieu, gardes à ses côtés ;
- fondateur absent : issue résolue au passage d'après la sécurité.

**Pertes possibles** : blessés, morts, bétail, réserves, bâtiments endommagés, incendie, moral. Jamais la perte du lieu.

**Absence longue** : le rattrapage est plafonné à **3 jours réels**. Le lieu peut avoir souffert, il n'est jamais détruit.

## 7. Besoins et santé

**Quatre stocks** : nourriture, bois, matériaux, médicaments. Ils se consomment au fil du temps, calculé au passage.

**Santé** : blessures d'attaque et maladies (accidents, morsures, infections, intoxications, épuisement).
Les soignants en poste et le stock de médicaments en limitent la gravité.

## 8. Population, métiers, bâtiments

**Habitants** :

- les PNJ qui tiennent un poste sont **nommés** et **engagés par le fondateur** ;
- le reste est une **population comptée**, qui arrive d'elle-même selon la sécurité, les logements, le moral et la prospérité.

**Mort d'un PNJ nommé** : définitive. Sa fonction s'arrête jusqu'à son remplacement.

**Métiers** : ceux déjà en jeu dans les propriétés urbaines, plus agriculteur, éleveur, intendant, bûcheron, chasseur, aubergiste, garde, bâtisseur, carrier, pêcheur.

**Bâtiments** (aménagements du lieu, chacun avec ses postes) : habitation, entrepôt, ferme, étable, auberge, boutique, atelier, poste de garde. Pas de lieu de culte.

**Production** : fermes, élevages et coupes de bois alimentent les stocks. Ateliers et boutiques tournent comme les ateliers des propriétés urbaines.

**Échanges des ateliers** (Auteur, 12/11, en jeu pour les biens urbains) : la mécanique des biens urbains s'applique telle quelle. L'implantation **est elle-même la cité** : ses ateliers échangent avec ses propres boutiques, sans cité de rattachement ni distance.

- **Temps** : une passe par heure réelle environ (tirée entre 30 et 90 minutes), rattrapée au passage, au plus **2 jours** d'absence. Ce plafond est propre aux ateliers ; celui du lieu reste de 3 jours (§ 6).
- **Vente** : chaque boutique est un acheteur distinct. Elle paie le prix qu'obtiendrait le **fondateur** chez elle (sa relation, ses prix négociés). Elle n'achète plus dès que son stock atteint sa cible. Le plus offrant passe d'abord ; la marchandise arrive vraiment chez lui.
- **Négociant** : sans lui, les ateliers vendent moins cher et n'achètent rien. Avec lui, ils achètent leurs matières aux seules boutiques qui en ont trop. Il progresse : par le commerce, par une formation payée, et par la séance « Tenir les livres » si le fondateur est **Lettré**.
- **Personnel du négoce** : commis (compare plus de boutiques), charretier (porte davantage), teneur de livres (achats plus justes, caisse plus grande), crieur (vend aux habitants ce que nulle boutique ne prend).
- **Ce qui produit le fait seul** : fermes, jardins, potagers et vergers (la terre fournit ses semences), ainsi que les récoltes.
- **Option par PNJ** : le fondateur décide, en cliquant sur un PNJ, si sa production se vend. Interdite, elle reste au lieu.

Moteur : `utils/echanges_cite.py` ; une implantation y entrera en devenant une cité (`marche.est_cite`).

## 9. La guilde du joueur

Elle est **indépendante** de la Guilde existante. Cinq échelons, étalés sur les paliers :

| Échelon | S'ouvre au palier |
|---|---|
| Auberge d'aventuriers | Village |
| Maison d'aventuriers | Bourg |
| Demeure des aventuriers | Petite ville |
| Guilde d'aventuriers | Ville |
| Grande guilde d'aventuriers | Ville |

Fonctions, ouvertes peu à peu avec les échelons :

- recruter des aventuriers PNJ et former des groupes ;
- proposer des missions, gérer contrats et récompenses ;
- employer des spécialistes, stocker le matériel commun ;
- explorer les donjons alentour, défendre la ville ;
- attirer de nouveaux habitants.

Les groupes envoyés en mission sont résolus au passage.

Portail propre à la ville : perspective lointaine, non décidée.

## 10. Les autres joueurs

Arrêté le 12/11/2026, par questionnaire. Dès le campement, l'implantation est une connexion (point bleu) dans laquelle on entre. Seul le **personnage principal** a un statut : ni le clone d'un compagnon-joueur, ni une monture.

**Trois statuts** :

| Statut | S'obtient | Accord du fondateur |
|---|---|---|
| Visiteur | en entrant | non |
| Soutien | par un premier don | non |
| Associé | par une demande écrite, acceptée | oui |

**Le visiteur** :

- lit le site : nom, fondateur, palier, sécurité et moral **en mots** (le détail chiffré reste au fondateur) ;
- se sert de ce qui existe : repos au feu, boutique et auberge dès la Bourgade ;
- **donne librement** aux quatre stocks ; le don est noté au carnet du fondateur ;
- voit le **tableau des besoins** : dérivé des stocks bas, sans récompense ;
- rien d'hostile : ni vol, ni attaque.

**L'associé** : le fondateur décide, l'associé contribue.

- **Approvisionner** : récoltes et chasses du site livrées au lieu, comptées comme apports.
- **Financer** : verser une part d'un chantier ouvert par le fondateur (fortification, aménagement de statut).
- **Pacifier** : suivre les traces de la faune, localiser la tanière, la vider.
- **Amener des colons** : escorter des habitants depuis une cité proche ; la population comptée augmente.
- **Loger** : nuit gratuite dans une habitation, petit coffre personnel.
- **Présence** : il vaut le fondateur. Une attaque pendant sa visite se joue en combat, et sa visite déclenche le rattrapage du temps écoulé.
- **Entrepôt commun** : dépôt seulement ; le retrait, si le fondateur l'autorise, associé par associé.

**Ce que l'associé y gagne** : des **prix de faveur** dans les boutiques et à l'auberge du lieu, et le titre de **membre fondateur** de la guilde quand elle ouvre (rang d'office). Pas de parts sur la caisse. Rejoindre la guilde plus tard reste possible sans avoir été associé.

**Réservé au fondateur** : engager ou renvoyer les PNJ nommés, choisir les aménagements, régler le feu, vendre la production, la caisse, accepter ou exclure un associé.

**Garde-fous** :

- places d'associés par palier : 1, 2, 4, puis doublement (Campement 1 … Ville 64) ;
- une seule association active par personnage, en plus de ses propres implantations ;
- **pas d'expiration** : l'association prend fin par départ volontaire ou par exclusion ; les apports restent au lieu ;
- tout est asynchrone : la demande attend le fondateur, chacun lit les actes de l'autre dans son carnet.

## 11. Les deux voies côte à côte

| | Voie urbaine (en jeu) | Voie de colonisation |
|---|---|---|
| Départ | Cité existante | case d'un pays, charte du maître de guilde |
| Progression | cinq types figés | sept paliers, évolution sur place |
| PNJ | personnel et spécialistes | postes nommés + population comptée |
| Défense | assurée par la ville | à construire, exigée par palier |
| Économie | celle de la cité : ateliers échangeant avec chaque boutique | quatre stocks + production des PNJ, échanges avec ses propres boutiques |
| Limite | Domaine | Ville |
| Guilde | impossible à fonder | cinq échelons, du Village à la Ville |
| Carte | celle de la cité, le bien est une porte | la sienne : un modèle par palier, bâtiments posés par le fondateur (§ 12) |

## 12. Interface de l'implantation

Arrêté le 12/11/2026, par questionnaire. L'implantation se joue comme une ville : une carte sur laquelle on marche, des icônes de métier près des bâtiments, des lieux où l'on entre.

### 12.1 Lieux modèles

- Une **image par palier et par milieu** : un campement de désert n'est pas un campement de forêt.
- Chaque image a son **lieu modèle**, qui porte l'image, les dimensions, la grille (`cells`, `nav`), les **entrées** et ses tags : `modele_colonie`, le palier, un ou plusieurs milieux, éventuellement un pays.
- **Taille de grille libre par modèle** : le campement tient sur une petite carte, la ville sur une grande. Monter de palier, c'est voir le lieu grandir.
- Un milieu peut être **incomplet** : un palier sans image de son milieu prend le modèle **générique** de ce palier. Le jeu générique des sept paliers est le seul prérequis.
- **Fortifications peintes dans l'image du palier** et murées dans sa grille : la palissade du Hameau, les murailles du Bourg se voient et arrêtent le pas. Une défense au-delà du minimum exigé ne se lit que dans le panneau.

### 12.2 Choisir son modèle

- Tags du site : ceux de la **zone d'influence** qui couvre la case, puis ceux du **pays** parent.
- Le fondateur **choisit** parmi les modèles du palier, présentés en vignettes avec les tags qu'ils partagent avec le site : **meilleur recouvrement en tête, générique en dernier**.
- S'il existe des modèles **propres au pays**, seuls ceux-là sont proposés — le générique toujours en plus.

### 12.3 Lien au modèle

Proposition de Claude Code, à valider à l'implémentation.

- Le lieu de l'implantation garde la référence de son modèle et en **recopie** l'image et la grille : à la fondation, à chaque palier, et au passage du fondateur si le modèle a été corrigé depuis (paresseux, § 1).
- L'état — palier, bâtiments posés, stocks — vit dans un doc à part : la grille n'est jamais réécrite en jeu.

### 12.4 Poser un bâtiment

- **Pose libre** : toute case marchable et libre, hors entrées ; un bâtiment par case.
- Geste : **« Poser ici »**. On marche jusqu'à la case, on choisit le bâtiment dans le panneau, il se pose sous ses pieds. Un refus (case prise, entrée) se dit en toast.
- L'**icône** du bâtiment s'affiche à proximité, comme l'enseigne d'une boutique en cité.
- **Déplacer** : même geste, disponible en tout temps.

| Nature | Bâtiments | Sur la carte | Au contact |
|---|---|---|---|
| Sous-lieu | boutique, atelier, auberge, étable | icône du métier | on entre |
| Repère | habitation, entrepôt, ferme, poste de garde | icône propre | une fiche : occupants, stock, PNJ en poste |

### 12.5 Changer de palier

- Nouvelle image, nouvelle grille.
- Chaque bâtiment est **replacé seul** : même position relative, case libre la plus proche.
- Le fondateur ou un associé corrige ensuite, par le geste de déplacement.

### 12.6 Entrées

- **Une à quatre cases** déclarées sur le modèle : les portes de l'enceinte peinte.
- Le joueur arrive par la première ; les attaquants (§ 6) partent des entrées ; rien ne s'y pose.

### 12.7 Panneau de l'implantation

- Un bouton visible seulement sur la carte de l'implantation ; onglets **Site, Population, Bâtiments, Défense**.
- Le visiteur en a la lecture : site en mots, tableau des besoins, dons (§ 10).

### 12.8 Qui fait quoi sur la carte

Précise le § 10. Tous voient la même carte et les mêmes icônes.

| Statut | Déclencher un aménagement | Poser, déplacer |
|---|---|---|
| Fondateur | oui | oui |
| Associé | non | oui, une fois l'aménagement déclenché |
| Soutien, visiteur | non | non |

**Écartés** : parcelles peintes ou typées ; calque de fortification par-dessus l'image ; clic sur la carte pour poser ; gestion dans le panneau des propriétés ; visiteur sans carte ; grille identique aux sept paliers.

**Non décidé** :

- à la montée de palier, le choix du modèle est-il reproposé, ou suit-il le milieu retenu à la fondation ;
- la forme du tag « pays » d'un modèle ;
- les icônes des repères.

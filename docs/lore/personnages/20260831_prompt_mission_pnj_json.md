# Prompt mission PNJ JSON

- **Source :** [conversation ChatGPT](https://chatgpt.com/g/g-p-6a836af71c6c8191a84e3d2ec701c896/c/6a95b4b4-72e8-83ed-a61c-01ec9e305faf)
- **Créée :** 31/08/2026 · **mise à jour :** 06/09/2026
- **Messages :** 2

---

## ✍️ Auteur — 31/08/2026

Rédige le prompt pour Claude.ai pour créer un json importable dans le jeu qui mettra en place la mission pour retrouver les bûcherons à Auxerre. C'est la mission qui fini par le voyage vers Lutecia avec une escorte paladin pour y amené la dernière livraison de cristal de mana et la jeune architecte humaine Aélis de Montfaucon retrouvée avec les bûcherons. Décrit le scenario de la mission et nomme les personnages impliqués. Gautier de Valcroix, le maitre de la guilde d'aventurier d'Auxerre (humain mâle) demande la réalisation de cette mission au personnage. Borin Barbe-de-Jais, réceptionniste de la guilde (nain mâle), informe le personnage que le maitre de la guilde le cherche pour une mission importante. 
La jeune architecte tentait de rejoindre Auxerre pour étudier les cristaux de mana et on la retrouve cacher dans une grotte avec les trois bucherons. L'entrée de la grotte est bloqué par trois Loups Géant qui n'arrivent pas à se fauffiler dans l'entrée et rôdent à faible distance.
Décrit les bûcherons et la jeune architecte ainsi que les paladins que l'on rencontre dans Auxerre. Cette description doit répondre à la forme suivante :
Nom : Borin Barbe-de-Jais
Fonction : réceptionniste de la Guilde des aventuriers d'Auxerre
Race : nain
Sexe : masculin
Lieu : réception du Bastion de l'Yonne
Rôle : déclencheur de la mission.

Pour les personnages non existant rajoute une description physique pouvant être donner en prompt à Gémini pour en créer le portrait (image).

Important : 
Rédige le scénario et les différents dialogues entre les personnages.

---

## 🤖 ChatGPT — 31/08/2026

Voici un prompt conçu pour être donné directement à Claude.ai. Il demande à Claude de produire **le JSON final importable**, tout en lui imposant une structure narrative complète, les PNJ, les dialogues et les différentes étapes de la mission.

:::writing{variant="document" id="58321"}
# Mission RPG — Retrouver les bûcherons d'Auxerre

Tu dois créer **un fichier JSON directement importable dans mon jeu de rôle médiéval-fantastique Telluris**.

## Consigne principale

À partir des fichiers JSON de référence que je vais te fournir, respecte **strictement le schéma, les noms de champs, les types de données, les conventions d'identifiants, les relations entre objets et la structure JSON** utilisés par mon jeu.

Ne crée pas un nouveau format arbitraire.

Le résultat doit être directement exploitable par le moteur du jeu.

Si les fichiers de référence contiennent plusieurs exemples similaires, utilise celui qui correspond le mieux à une **mission/quête scénarisée avec PNJ, objectifs, dialogues, lieux, combats et évolution de l'état de la quête**.

### Contraintes de sortie

- Retourne uniquement le JSON final.
- Pas de Markdown.
- Pas de commentaires dans le JSON.
- Pas d'explication avant ou après le JSON.
- Le JSON doit être valide.
- Tous les identifiants doivent être uniques et cohérents.
- Les références entre objets doivent utiliser les mêmes conventions que les fichiers de référence.
- N'invente pas de champs qui n'existent pas dans le modèle fourni.
- Si une information nécessaire au scénario n'existe pas explicitement dans les exemples, adapte-la au champ existant le plus approprié.
- Ne supprime aucune information narrative importante sous prétexte de simplifier.
- Les dialogues doivent être suffisamment détaillés pour pouvoir être utilisés directement dans le jeu.

---

# Contexte du monde

L'histoire se déroule à **Auxerre**, dans le monde médiéval-fantastique de Telluris.

Auxerre est une cité importante de la région. La Guilde des aventuriers est installée dans le **Bastion de l'Yonne**.

Les routes entre les cités sont dangereuses et les voyageurs peuvent rencontrer des monstres. Les cristaux de mana sont des ressources rares et précieuses utilisées notamment pour alimenter certaines technologies et recherches magiques.

**Lutecia**, ancienne Paris, est un important centre de connaissances et de recherches. La cité entretient notamment des recherches avancées autour du mana, de la magie et de l'architecture.

La mission à créer constitue une étape importante de l'histoire du personnage et doit servir de transition vers une future aventure à Lutecia.

---

# Mission

La mission consiste initialement à :

**Retrouver trois bûcherons d'Auxerre qui ne sont pas revenus d'une expédition en forêt.**

La mission est donnée par :

Nom : Gautier de Valcroix  
Fonction : maître de la Guilde des aventuriers d'Auxerre  
Race : humain  
Sexe : masculin  
Lieu : Bastion de l'Yonne, Auxerre  
Rôle : donneur de mission et supérieur de Borin Barbe-de-Jais.

Le personnage joueur n'est pas directement convoqué par Gautier au début.

La mission commence lorsque :

Nom : Borin Barbe-de-Jais  
Fonction : réceptionniste de la Guilde des aventuriers d'Auxerre  
Race : nain  
Sexe : masculin  
Lieu : réception du Bastion de l'Yonne  
Rôle : déclencheur de la mission.

Borin informe le personnage que **Gautier de Valcroix le cherche pour une mission importante**.

---

# Personnages

## Borin Barbe-de-Jais

Nom : Borin Barbe-de-Jais  
Fonction : réceptionniste de la Guilde des aventuriers d'Auxerre  
Race : nain  
Sexe : masculin  
Lieu : réception du Bastion de l'Yonne  
Rôle : déclencheur de la mission.

Description physique :

Borin est un nain trapu et solidement bâti, d'âge mûr. Il possède une chevelure noire de jais et une barbe particulièrement dense de la même couleur, soigneusement entretenue malgré son travail quotidien à la réception. Son visage est marqué par quelques rides et son regard sombre est attentif et professionnel. Il porte des vêtements robustes de guilde, adaptés à son travail derrière le comptoir, avec une veste sombre renforcée de cuir et plusieurs petits registres posés à portée de main.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'un réceptionniste nain adulte d'âge mûr, homme trapu et robuste, cheveux noirs de jais, très longue barbe noire soigneusement entretenue, visage marqué par quelques rides, regard attentif et sérieux, vêtements de guilde médiévale en cuir sombre, intérieur d'une guilde d'aventuriers, comptoir en bois derrière lui, ambiance réaliste, lumière chaleureuse, character portrait, fantasy RPG, aucun texte."

---

## Gautier de Valcroix

Nom : Gautier de Valcroix  
Fonction : maître de la Guilde des aventuriers d'Auxerre  
Race : humain  
Sexe : masculin  
Lieu : Bastion de l'Yonne, bureau du maître de guilde  
Rôle : donneur de mission.

Description physique :

Gautier est un homme humain d'une cinquantaine d'années, grand et droit malgré son âge. Ses cheveux bruns commencent à grisonner aux tempes. Il porte une barbe courte soigneusement taillée. Son visage est sévère sans être hostile et son regard donne l'impression d'un homme habitué à prendre des décisions difficiles. Il porte une tenue sobre de maître de guilde, composée d'une tunique sombre, d'un manteau épais et d'éléments d'armure légère. Une épée est toujours portée à sa ceinture.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'un maître de guilde humain d'environ cinquante ans, homme grand et robuste, cheveux bruns légèrement grisonnants aux tempes, barbe courte soigneusement taillée, visage sérieux et autoritaire mais bienveillant, regard intelligent et observateur, tunique sombre de qualité, manteau médiéval, légère armure de cuir, épée à la ceinture, bureau en pierre et bois d'une guilde d'aventuriers, fantasy RPG réaliste, character portrait, aucun texte."

---

# Les trois bûcherons disparus

Créer trois PNJ distincts.

Ils travaillent pour Auxerre et connaissent bien les forêts environnantes.

Ils étaient partis couper du bois avec leur équipement habituel mais ne sont jamais revenus.

Ils se sont finalement réfugiés dans une grotte après avoir découvert un phénomène inhabituel dans la forêt.

Créer les personnages suivants.

---

## Armand Renaud

Nom : Armand Renaud  
Fonction : bûcheron  
Race : humain  
Sexe : masculin  
Lieu : grotte forestière au nord-ouest d'Auxerre  
Rôle : chef de fait du groupe de bûcherons et témoin principal.

Description physique :

Armand est un homme robuste d'une quarantaine d'années, habitué au travail physique. Il possède des épaules larges, des mains calleuses et une barbe brune épaisse mais courte. Ses cheveux bruns sont souvent en désordre à cause de son travail en forêt. Il porte des vêtements de travail grossiers, une veste de cuir usée et des bottes renforcées. Son équipement de bûcheron est encore avec lui.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'un bûcheron humain d'environ quarante ans, homme robuste et musclé, épaules larges, cheveux bruns légèrement désordonnés, barbe brune courte et épaisse, visage marqué par le travail en forêt, mains calleuses, vêtements médiévaux de travail usés, veste de cuir, bottes robustes, hache de bûcheron, ambiance de forêt médiévale fantastique, character portrait réaliste, aucun texte."

---

## Étienne Morel

Nom : Étienne Morel  
Fonction : bûcheron  
Race : humain  
Sexe : masculin  
Lieu : grotte forestière au nord-ouest d'Auxerre  
Rôle : bûcheron du groupe, blessé légèrement lors de la fuite.

Description physique :

Étienne est un homme d'une trentaine d'années, plus mince qu'Armand mais très endurant. Il possède des cheveux châtains courts et une barbe naissante. Son visage est marqué par la fatigue et l'inquiétude. Une petite blessure est visible sur son avant-bras, conséquence de leur fuite dans la forêt. Il porte une tunique de travail, un pantalon épais et des bottes couvertes de boue.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'un jeune bûcheron humain d'environ trente ans, silhouette mince mais robuste, cheveux châtains courts, barbe de quelques jours, visage fatigué et inquiet, petite blessure visible sur l'avant-bras, vêtements médiévaux de travail couverts de boue, bottes usées, hache de bûcheron, forêt fantastique en arrière-plan, character portrait réaliste, aucun texte."

---

## Matthieu Perrin

Nom : Matthieu Perrin  
Fonction : bûcheron  
Race : humain  
Sexe : masculin  
Lieu : grotte forestière au nord-ouest d'Auxerre  
Rôle : troisième bûcheron, connaît l'emplacement exact de la grotte.

Description physique :

Matthieu est le plus jeune des trois bûcherons, âgé d'environ vingt-cinq ans. Il est grand et élancé. Ses cheveux blonds foncés sont courts et ses yeux clairs trahissent son inquiétude. Il porte une tunique de laine, un pantalon de toile épaisse et une ceinture à laquelle sont accrochés quelques outils de travail. Il tient encore sa hache lorsqu'il est retrouvé.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'un jeune bûcheron humain d'environ vingt-cinq ans, homme grand et élancé, cheveux blond foncé courts, yeux clairs, visage inquiet, vêtements médiévaux simples en laine et toile, ceinture d'outils, hache de bûcheron, vêtements légèrement sales après plusieurs jours dans une forêt humide, fantasy RPG réaliste, character portrait, aucun texte."

---

# Aélis de Montfaucon

Créer ce personnage comme un PNJ majeur.

Nom : Aélis de Montfaucon  
Fonction : jeune architecte et chercheuse spécialisée dans l'étude des cristaux de mana  
Race : humaine  
Sexe : féminin  
Lieu initial : grotte forestière au nord-ouest d'Auxerre  
Destination : Auxerre puis Lutecia  
Rôle : personnage retrouvé avec les bûcherons et élément central de la suite de l'histoire.

## Histoire

Aélis est une jeune architecte humaine qui devait rejoindre Auxerre afin d'y étudier les cristaux de mana.

Elle possède des connaissances particulières dans leur utilisation pour l'architecture et souhaite notamment comprendre comment les cristaux peuvent être intégrés à des constructions, des systèmes de protection et des infrastructures.

Elle voyageait seule vers Auxerre lorsqu'elle a été confrontée à un problème sur la route.

Elle a finalement trouvé refuge auprès des trois bûcherons.

Le groupe s'est retrouvé bloqué dans une grotte forestière.

Aélis a volontairement évité de sortir de la grotte car **trois Loups Géants rôdent devant l'entrée**.

Les loups sont trop grands pour se faufiler à l'intérieur de la grotte.

Ils restent à faible distance de l'entrée, attendant que les humains sortent.

Les trois bûcherons et Aélis sont donc prisonniers de la grotte.

Aélis doit être présentée comme intelligente, déterminée et rationnelle, mais clairement soulagée lorsqu'elle comprend que les aventuriers sont venus les secourir.

Elle n'est pas une combattante expérimentée.

Description physique :

Aélis est une jeune femme humaine d'environ vingt-deux ans. Elle possède une silhouette fine et une apparence davantage adaptée au travail intellectuel qu'au combat. Ses cheveux sont longs, châtains et légèrement ondulés. Ses yeux sont verts ou noisette. Son visage est fin et expressif. Ses vêtements de voyage sont élégants mais pratiques : une robe-tunique de voyage renforcée, un manteau poussiéreux et des bottes adaptées aux longues marches. Elle porte une sacoche contenant des carnets, des plans architecturaux, des instruments de mesure et quelques notes concernant les cristaux de mana. Son apparence montre qu'elle voyage depuis plusieurs jours dans des conditions difficiles.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'une jeune architecte humaine d'environ vingt-deux ans, femme mince et élégante, longs cheveux châtains légèrement ondulés, yeux verts ou noisette, visage fin et intelligent, expression déterminée mais fatiguée, vêtements de voyage médiévaux pratiques mais raffinés, robe-tunique renforcée, manteau poussiéreux, bottes de voyage, sacoche contenant des carnets et des plans architecturaux, petit instrument de mesure attaché à la ceinture, ambiance de grotte forestière, fantasy RPG réaliste, character portrait, aucun texte."

---

# Les trois Loups Géants

Créer trois créatures distinctes de l'espèce :

_id : espece:loup_geant

Ils doivent être liés à la rencontre de la grotte.

Les trois Loups Géants ne doivent pas entrer dans la grotte.

Ils sont trop volumineux pour passer par l'ouverture.

Ils rôdent à faible distance de l'entrée et empêchent les occupants de sortir.

Ils doivent être présentés comme des prédateurs dangereux, mais naturels : pas de transformation humanoïde, pas de caractéristiques humaines.

Créer trois individus distincts si le schéma du jeu permet de donner des identifiants aux créatures.

---

# Déroulement de la mission

La mission doit être structurée en plusieurs étapes cohérentes.

## Étape 1 — L'appel de la guilde

Le personnage se trouve au Bastion de l'Yonne.

Borin Barbe-de-Jais l'interpelle et lui explique que Gautier de Valcroix souhaite le voir.

Dialogue attendu :

Borin :
"Ah, vous voilà. Le maître de la guilde vous cherche."

Le personnage demande pourquoi.

Borin explique que trois bûcherons partis dans les environs d'Auxerre ne sont pas revenus et que Gautier veut confier l'affaire au personnage.

Le dialogue doit rester naturel et médiéval-fantastique, sans langage moderne.

---

## Étape 2 — Entretien avec Gautier de Valcroix

Le personnage rejoint le bureau de Gautier.

Gautier explique :

- trois bûcherons ne sont pas revenus ;
- leur absence devient inquiétante ;
- ils connaissent bien la forêt ;
- une simple recherche aurait normalement dû permettre leur retour ;
- la guilde veut éviter d'envoyer une grande troupe ;
- le personnage est chargé de retrouver les disparus ;
- s'ils sont vivants, il faut les ramener à Auxerre.

Gautier ne connaît pas encore l'existence d'Aélis.

Il peut également mentionner qu'une voyageuse devait arriver récemment à Auxerre et que sa disparition pourrait être liée à la situation, mais cette information ne doit être qu'un indice secondaire si cela reste cohérent avec le schéma du jeu.

Gautier donne la zone générale où les bûcherons travaillaient.

---

## Étape 3 — Voyage dans la forêt

Le personnage doit se rendre dans la zone forestière.

Prévoir éventuellement des descriptions ou événements de voyage :

- traces de pas ;
- branches cassées ;
- outils abandonnés ;
- traces de lutte ou de fuite ;
- empreintes de grands canidés ;
- silence inhabituel de la forêt ;
- découverte progressive de la piste menant à la grotte.

Ne transforme pas cette étape en combat obligatoire si le modèle de mission permet plusieurs types d'événements.

---

# Étape 4 — La grotte

Le personnage découvre finalement une grotte.

À proximité de l'entrée se trouvent **trois Loups Géants**.

Ils rôdent à faible distance.

Ils grondent lorsque le personnage approche.

Ils ne peuvent pas entrer dans la grotte car l'ouverture est trop étroite pour leur taille.

À l'intérieur, le personnage découvre :

- Armand Renaud ;
- Étienne Morel ;
- Matthieu Perrin ;
- Aélis de Montfaucon.

Les quatre personnes sont vivantes.

Les bûcherons sont épuisés.

Aélis est particulièrement inquiète car elle comprend que les loups empêchent toute sortie.

Prévoir une rencontre permettant au personnage de comprendre progressivement ce qui s'est passé.

---

# Dialogue dans la grotte

Armand doit expliquer que les bûcherons ont été surpris par les Loups Géants alors qu'ils travaillaient.

Ils ont fui jusqu'à la grotte.

Ils ont découvert Aélis peu avant ou au cours de leur fuite.

Aélis doit expliquer qu'elle voyageait vers Auxerre pour étudier les cristaux de mana.

Elle révèle qu'elle possède des documents et des connaissances qui pourraient intéresser les chercheurs d'Auxerre et de Lutecia.

Elle ne doit pas révéler immédiatement toute son importance.

Le dialogue doit être naturel et progressif.

Exemple de tonalité :

Armand :
"Nous pensions pouvoir les semer dans les bois. Nous nous sommes trompés. Ils nous ont suivis jusqu'ici."

Étienne :
"Ils sont là depuis que nous avons trouvé cette grotte. Dès que l'un de nous approche de l'entrée, ils se mettent à grogner."

Matthieu :
"Et nous n'avons plus rien à manger."

Aélis :
"Je ne pensais pas que mon voyage vers Auxerre se terminerait ainsi."

Le personnage demande qui elle est.

Aélis répond qu'elle s'appelle Aélis de Montfaucon et qu'elle est architecte.

Elle explique qu'elle se rendait à Auxerre pour étudier les cristaux de mana.

---

# Étape 5 — Affrontement avec les Loups Géants

Le personnage doit pouvoir combattre les trois Loups Géants afin de libérer la sortie.

Utiliser l'espèce existante :

espece:loup_geant

Le combat doit être représenté comme une rencontre dangereuse mais raisonnable pour un groupe d'aventuriers.

Les trois loups doivent occuper la zone extérieure devant l'entrée de la grotte.

Après leur défaite, les survivants peuvent sortir.

---

# Étape 6 — Retour vers Auxerre

Le personnage ramène :

- Armand Renaud ;
- Étienne Morel ;
- Matthieu Perrin ;
- Aélis de Montfaucon.

À Auxerre, les bûcherons sont accueillis par la guilde.

Aélis se présente à Gautier de Valcroix.

Gautier comprend rapidement que sa présence est importante.

Il apprend qu'elle est venue pour étudier les cristaux de mana.

---

# La dernière livraison de cristaux de mana

La mission doit alors évoluer.

La Guilde possède une **dernière livraison de cristaux de mana destinée à Lutecia**.

Cette livraison doit être escortée jusqu'à la cité.

La présence d'Aélis change la nature de la mission.

Elle doit maintenant se rendre à Lutecia pour poursuivre ses recherches et rencontrer les personnes susceptibles de l'aider dans ses travaux.

Gautier décide donc de proposer au personnage une nouvelle étape :

**escorter Aélis et la dernière livraison de cristaux de mana jusqu'à Lutecia.**

Cette partie doit être intégrée à la fin de la mission comme une transition narrative vers une prochaine mission ou un nouveau chapitre.

---

# Les paladins

Créer au moins deux paladins chargés d'accompagner le convoi.

Ils sont présents à Auxerre lorsque la décision du voyage vers Lutecia est prise.

Créer les personnages suivants :

## Dame Éléonore de Rochefort

Nom : Dame Éléonore de Rochefort  
Fonction : paladine, commandante de l'escorte vers Lutecia  
Race : humaine  
Sexe : féminin  
Lieu : Auxerre, Bastion de l'Yonne puis route vers Lutecia  
Rôle : commandante de l'escorte.

Description physique :

Éléonore est une femme d'environ trente-cinq ans, grande et athlétique. Elle porte une armure de plaques sobrement décorée, entretenue avec soin. Ses cheveux châtains sont attachés derrière sa tête. Son visage est sérieux et calme. Elle porte une épée longue et un bouclier marqué d'un symbole religieux ou chevaleresque cohérent avec le monde de Telluris. Elle inspire davantage la discipline et la confiance que la brutalité.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'une paladine humaine d'environ trente-cinq ans, grande et athlétique, cheveux châtains attachés, visage sérieux et calme, armure de plaques médiévale élégante mais fonctionnelle, épée longue et bouclier, posture droite et disciplinée, expression protectrice, cour intérieure fortifiée d'une cité médiévale en arrière-plan, fantasy RPG réaliste, character portrait, aucun texte."

---

## Frère Martin de Clairvaux

Nom : Frère Martin de Clairvaux  
Fonction : paladin et protecteur de l'escorte  
Race : humain  
Sexe : masculin  
Lieu : Auxerre, Bastion de l'Yonne puis route vers Lutecia  
Rôle : second de l'escorte.

Description physique :

Martin est un homme d'environ quarante ans, large d'épaules et fortement bâti. Il possède des cheveux bruns courts et une barbe courte. Son armure est plus lourde que celle d'Éléonore et porte les traces de nombreuses campagnes. Son expression est calme et réservée. Il manie une masse d'armes et un bouclier lourd.

Portrait Gemini :

"Portrait fantasy médiéval réaliste d'un paladin humain d'environ quarante ans, homme massif et fortement bâti, épaules larges, cheveux bruns courts, barbe courte, visage calme et réservé, armure de plaques lourde portant quelques marques d'usure, masse d'armes et grand bouclier, posture protectrice, forteresse médiévale en arrière-plan, fantasy RPG réaliste, character portrait, aucun texte."

---

# Dialogue à Auxerre avant le départ

Créer une scène entre :

- Gautier de Valcroix ;
- Aélis de Montfaucon ;
- Dame Éléonore de Rochefort ;
- Frère Martin de Clairvaux ;
- le personnage joueur.

Gautier explique que les cristaux doivent parvenir à Lutecia.

Aélis explique pourquoi elle souhaite les accompagner.

Éléonore explique qu'une escorte est nécessaire.

Martin peut rappeler que les routes ne sont pas sûres.

Gautier doit finalement confier officiellement la mission au personnage.

La scène doit donner le sentiment que le personnage vient de franchir une étape importante : il ne s'agit plus seulement de retrouver des personnes disparues, mais d'accompagner une jeune chercheuse et une ressource précieuse jusqu'à une grande cité.

---

# Dialogue final de départ

Créer un dialogue final suffisamment long entre Gautier et le personnage.

Gautier peut dire notamment, dans une formulation naturelle :

"Vous êtes parti retrouver trois bûcherons. Vous revenez avec quatre personnes, dont une architecte venue étudier les cristaux de mana. Le hasard a parfois une drôle de manière de choisir ses chemins."

Puis il explique :

"Il reste une dernière livraison de cristaux destinée à Lutecia. Elle doit partir maintenant. Aélis doit également rejoindre cette cité. Vous l'avez retrouvée, vous connaissez déjà les circonstances de sa disparition. Je préfère donc vous confier la suite."

Éléonore confirme qu'elle prendra la tête de l'escorte.

Aélis remercie le personnage pour son aide.

Le personnage reçoit alors l'objectif :

**Escorter Aélis de Montfaucon et la dernière livraison de cristaux de mana jusqu'à Lutecia.**

Cette nouvelle destination doit constituer la conclusion de la mission actuelle et le point de départ logique de la prochaine aventure.

---

# Ton narratif

Le scénario doit respecter les principes suivants :

- fantasy médiévale sérieuse ;
- dialogues naturels ;
- pas de vocabulaire contemporain ;
- pas d'humour excessif ;
- pas de personnages caricaturaux ;
- pas de races hybrides humanoïdes/animales ;
- les humains, nains et autres races humanoïdes peuvent vivre ensemble sans racisme structurel ;
- les Loups Géants sont des créatures animales fantastiques ;
- Aélis est une intellectuelle et une architecte, pas une guerrière ;
- les bûcherons sont des travailleurs ordinaires et non des aventuriers ;
- les paladins sont des professionnels chargés de la protection du convoi ;
- Gautier est expérimenté et pragmatique ;
- Borin est efficace et direct ;
- la découverte d'Aélis doit donner l'impression d'être une conséquence inattendue de la mission initiale ;
- la transition vers Lutecia doit être claire et logique.

---

# Résultat attendu

Génère maintenant le **JSON complet et directement importable dans le jeu**, en utilisant strictement le schéma des fichiers de référence fournis.

Le JSON doit contenir, lorsque le schéma le permet :

1. la définition de la mission ;
2. son identifiant unique ;
3. son titre ;
4. sa description ;
5. ses objectifs ;
6. ses étapes ;
7. les PNJ impliqués ;
8. les trois bûcherons ;
9. Aélis de Montfaucon ;
10. Gautier de Valcroix ;
11. Borin Barbe-de-Jais ;
12. Dame Éléonore de Rochefort ;
13. Frère Martin de Clairvaux ;
14. les trois Loups Géants ;
15. les lieux nécessaires ;
16. les conditions de déclenchement ;
17. les conditions de progression ;
18. les conditions de réussite ;
19. les dialogues complets ;
20. les conséquences de la découverte d'Aélis ;
21. la récupération des bûcherons ;
22. le retour à Auxerre ;
23. la remise de la mission d'escorte ;
24. la dernière livraison de cristaux de mana ;
25. la destination Lutecia ;
26. toutes les références nécessaires entre les différents objets.

La mission doit se terminer narrativement au moment où **le personnage, Aélis de Montfaucon, Dame Éléonore de Rochefort, Frère Martin de Clairvaux et la dernière livraison de cristaux de mana sont prêts à quitter Auxerre pour prendre la route de Lutecia**.

La suite du voyage vers Lutecia pourra être traitée comme une mission distincte.
:::

Ce prompt est volontairement formulé pour que Claude **s'appuie sur ton modèle JSON existant plutôt que d'inventer sa propre structure**. Si tu lui fournis en même temps un ou deux JSON de missions déjà fonctionnelles de ton jeu, il pourra normalement reproduire beaucoup plus fidèlement le format d'import.

---

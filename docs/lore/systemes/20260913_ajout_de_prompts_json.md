# Ajout de prompts JSON

- **Source :** [conversation ChatGPT](https://chatgpt.com/g/g-p-6a836af71c6c8191a84e3d2ec701c896/c/6aa6c5c4-5538-83ed-a846-2a914fda5afe)
- **Créée :** 13/09/2026 · **mise à jour :** 13/09/2026
- **Messages :** 2

---

## ✍️ Auteur — 13/09/2026

ajoute à ce json un prompt par entrée : [
  {
    "_id": "lieu:auberge_de_la_greve",
    "label": "Auberge de la Grève",
    "categorie": "auberge"
  },
  {
    "_id": "lieu:auberge_de_la_seine",
    "label": "Auberge de la Seine",
    "categorie": "auberge"
  },
  {
    "_id": "lieu:auberge_des_ecoles",
    "label": "Auberge des Écoles",
    "categorie": "auberge"
  },
  {
    "_id": "lieu:auberge_des_halles",
    "label": "Auberge des Halles",
    "categorie": "auberge"
  },
  {
    "_id": "lieu:auberge_du_palais",
    "label": "Auberge du Palais",
    "categorie": "auberge"
  },
  {
    "_id": "lieu:auberge_du_parvis",
    "label": "Auberge du Parvis de Saint Sulpice",
    "categorie": "auberge"
  },
  {
    "_id": "lieu:auberge_du_petit_pont",
    "label": "Auberge du Petit-Pont",
    "categorie": "auberge"
  }
]

voici un prompt à suivre en exemple: 
"Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge de la Cité' dans un monde médiéval fantastique auberge à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge est devant une porte de rempart fermée et gardée de la cité." 

Ajoute pour chaque auberge un détail qui permet de la rattacher à un lieu parisien lui correspondant.

---

## 🤖 ChatGPT — 13/09/2026

Voici le JSON complété. J’ai rattaché chaque auberge à un élément parisien correspondant à son nom ou à son emplacement historique : la Seine, les Écoles, les Halles, le Palais, Saint-Sulpice et le Petit-Pont.

```json
[
  {
    "_id": "lieu:auberge_de_la_greve",
    "label": "Auberge de la Grève",
    "categorie": "auberge",
    "prompt": "Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge de la Grève' dans un monde médiéval fantastique, à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge est bâtie au bord de la Seine, sur une berge pavée correspondant à l'ancienne grève de Paris, avec des quais en pierre, des barques et des marchands déchargeant leurs marchandises au bord de l'eau. Une partie des remparts de Lutecia est visible en arrière-plan."
  },
  {
    "_id": "lieu:auberge_de_la_seine",
    "label": "Auberge de la Seine",
    "categorie": "auberge",
    "prompt": "Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge de la Seine' dans un monde médiéval fantastique, à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge domine directement un bras de la Seine, avec une terrasse en bois donnant sur l'eau, des pontons, des barques de voyageurs et des pêcheurs. Le fleuve et ses deux rives doivent être immédiatement reconnaissables comme une évocation médiévale de la Seine parisienne. Des bâtiments fortifiés de Lutecia apparaissent au loin."
  },
  {
    "_id": "lieu:auberge_des_ecoles",
    "label": "Auberge des Écoles",
    "categorie": "auberge",
    "prompt": "Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge des Écoles' dans un monde médiéval fantastique, à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge se trouve dans un quartier universitaire de Lutecia inspiré du Quartier Latin, entourée de petites écoles médiévales, de salles d'étude, de pupitres et de jeunes apprentis de différentes Lignées transportant des livres et des parchemins. L'architecture évoque les anciennes écoles de la rive gauche de Paris."
  },
  {
    "_id": "lieu:auberge_des_halles",
    "label": "Auberge des Halles",
    "categorie": "auberge",
    "prompt": "Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge des Halles' dans un monde médiéval fantastique, à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge est installée au cœur d'un immense marché couvert inspiré des Halles de Paris, avec des étals de viande, de poisson, de pain, de fruits et de légumes, des charrettes de marchandises et une foule de commerçants. La proximité immédiate d'un grand marché très animé doit être le détail parisien dominant."
  },
  {
    "_id": "lieu:auberge_du_palais",
    "label": "Auberge du Palais",
    "categorie": "auberge",
    "prompt": "Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge du Palais' dans un monde médiéval fantastique, à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge est située à proximité du palais fortifié de Lutecia, inspiré du Palais de la Cité sur l'île de la Cité. On distingue derrière elle une imposante forteresse royale en pierre, des tours médiévales et des bannières, tandis que nobles, gardes et voyageurs fréquentent l'auberge."
  },
  {
    "_id": "lieu:auberge_du_parvis",
    "label": "Auberge du Parvis de Saint Sulpice",
    "categorie": "auberge",
    "prompt": "Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge du Parvis de Saint Sulpice' dans un monde médiéval fantastique, à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge donne directement sur une vaste place pavée inspirée du parvis de l'église Saint-Sulpice à Paris. Derrière l'auberge s'élève une immense église médiévale à deux grandes tours de pierre, dont les proportions et la façade évoquent Saint-Sulpice. Des paladins, des pèlerins et des habitants traversent la place."
  },
  {
    "_id": "lieu:auberge_du_petit_pont",
    "label": "Auberge du Petit-Pont",
    "categorie": "auberge",
    "prompt": "Réalise l'image d'un magasin du type 'auberge' du nom de 'Auberge du Petit-Pont' dans un monde médiéval fantastique, à 'Lutecia'. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. L'auberge est construite juste à côté d'un petit pont de pierre enjambant la Seine, inspiré du Petit-Pont de Paris reliant l'île de la Cité à la rive gauche. Des voyageurs, des charrettes et des paladins franchissent le pont, tandis que l'on distingue les bâtiments fortifiés de Lutecia et les quais de la Seine en arrière-plan."
  }
]
```

Les correspondances parisiennes principales sont donc :

- **Grève** → ancienne place de Grève, au bord de la Seine.
- **Seine** → quais et activités fluviales.
- **Écoles** → quartier des écoles de la rive gauche / Quartier Latin.
- **Halles** → grand marché central.
- **Palais** → Palais de la Cité / île de la Cité.
- **Parvis de Saint-Sulpice** → église et grande place de Saint-Sulpice.
- **Petit-Pont** → pont reliant l'île de la Cité à la rive gauche.

---

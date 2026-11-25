# Liste boulangerie médiévale

- **Source :** [conversation ChatGPT](https://chatgpt.com/g/g-p-6a836af71c6c8191a84e3d2ec701c896/c/6a9c0c3b-f374-83ed-93c9-6d3220ff6d59)
- **Créée :** 05/09/2026 · **mise à jour :** 06/09/2026
- **Messages :** 6

---

## ✍️ Auteur — 05/09/2026

Fait moi une liste de 15 produits pouvant être achetés dans une boulangerie dans un monde médiéval fantastique inspiré de notre propre monde.

---

## 🤖 ChatGPT — 05/09/2026

Voici une liste de **15 produits plausibles pour une boulangerie médiévale fantastique**, en restant proche de produits que l’on aurait pu trouver dans une boulangerie européenne historique, avec quelques variantes adaptées à Telluris.

| # | Produit | Description |
|---|---|---|
| 1 | **Pain de froment** | Pain blanc courant, fabriqué avec de la farine de blé. |
| 2 | **Pain de seigle** | Pain sombre et dense, particulièrement apprécié dans les régions froides. |
| 3 | **Pain d’orge** | Pain rustique, nourrissant et peu coûteux. |
| 4 | **Pain de méteil** | Pain fabriqué avec un mélange de blé et de seigle. |
| 5 | **Pain aux noix** | Pain rustique contenant des noix concassées. |
| 6 | **Pain aux herbes** | Petit pain parfumé avec des herbes locales comme le thym, la sauge ou le romarin. |
| 7 | **Petit pain** | Portion individuelle de pain blanc, pratique pour les voyageurs et les soldats. |
| 8 | **Galette de céréales** | Galette plate cuite directement sur la pierre ou la plaque du four. |
| 9 | **Fouace au miel** | Pain moelleux légèrement sucré au miel, souvent préparé pour les jours de fête. |
| 10 | **Brioche au miel** | Pâte riche en œufs et en beurre, sucrée au miel. Produit plus luxueux. |
| 11 | **Tourte aux pommes** | Pâte garnie de pommes coupées et légèrement sucrées. |
| 12 | **Tourte aux poires** | Variante aux poires, parfois parfumée aux épices. |
| 13 | **Galette aux fruits secs** | Galette garnie de noix, noisettes, raisins secs ou autres fruits séchés. |
| 14 | **Biscuits de voyage** | Biscuits très secs et résistants, conçus pour être conservés plusieurs semaines. |
| 15 | **Pain d’épices au miel** | Pain dense et parfumé au miel, avec cannelle, gingembre ou autres épices importées. |

### Pour une économie de jeu

Je répartirais ces produits en trois catégories :

- **Courants :** pain de froment, seigle, orge, méteil, petit pain, galette.
- **Améliorés :** pain aux noix, pain aux herbes, fouace, tourtes, galette aux fruits secs.
- **Luxueux :** brioche au miel, pain d’épices, pâtisseries aux fruits et aux épices.

Pour une boulangerie d'**Auxerre**, cela permettrait notamment d'avoir des produits très bon marché pour les habitants et les aventuriers, mais aussi quelques produits plus chers destinés aux notables, voyageurs et fêtes.

---

## ✍️ Auteur — 05/09/2026

donne moi les sous une forme json

---

## 🤖 ChatGPT — 05/09/2026

Voici les 15 produits sous forme de JSON, avec des identifiants simples et directement exploitables dans ton système de jeu :

```json
[
  {
    "id": "pain_froment",
    "nom": "Pain de froment",
    "description": "Pain blanc courant fabriqué avec de la farine de blé.",
    "categorie": "boulangerie"
  },
  {
    "id": "pain_seigle",
    "nom": "Pain de seigle",
    "description": "Pain sombre et dense, nourrissant et apprécié dans les régions froides.",
    "categorie": "boulangerie"
  },
  {
    "id": "pain_orge",
    "nom": "Pain d'orge",
    "description": "Pain rustique, nourrissant et peu coûteux.",
    "categorie": "boulangerie"
  },
  {
    "id": "pain_meteil",
    "nom": "Pain de méteil",
    "description": "Pain fabriqué avec un mélange de farine de blé et de seigle.",
    "categorie": "boulangerie"
  },
  {
    "id": "pain_noix",
    "nom": "Pain aux noix",
    "description": "Pain rustique contenant des noix concassées.",
    "categorie": "boulangerie"
  },
  {
    "id": "pain_herbes",
    "nom": "Pain aux herbes",
    "description": "Petit pain parfumé avec des herbes locales comme le thym, la sauge ou le romarin.",
    "categorie": "boulangerie"
  },
  {
    "id": "petit_pain",
    "nom": "Petit pain",
    "description": "Portion individuelle de pain blanc, pratique pour les voyageurs et les soldats.",
    "categorie": "boulangerie"
  },
  {
    "id": "galette_cereales",
    "nom": "Galette de céréales",
    "description": "Galette plate préparée avec des céréales et cuite sur une plaque ou une pierre chaude.",
    "categorie": "boulangerie"
  },
  {
    "id": "fouace_miel",
    "nom": "Fouace au miel",
    "description": "Pain moelleux légèrement sucré au miel, souvent préparé pour les jours de fête.",
    "categorie": "boulangerie"
  },
  {
    "id": "brioche_miel",
    "nom": "Brioche au miel",
    "description": "Pâte riche en œufs et en beurre, légèrement sucrée au miel.",
    "categorie": "boulangerie"
  },
  {
    "id": "tourte_pommes",
    "nom": "Tourte aux pommes",
    "description": "Pâte garnie de pommes coupées et légèrement sucrées.",
    "categorie": "boulangerie"
  },
  {
    "id": "tourte_poires",
    "nom": "Tourte aux poires",
    "description": "Tourte garnie de poires et parfois parfumée avec des épices.",
    "categorie": "boulangerie"
  },
  {
    "id": "galette_fruits_secs",
    "nom": "Galette aux fruits secs",
    "description": "Galette garnie de noix, noisettes, raisins secs ou autres fruits séchés.",
    "categorie": "boulangerie"
  },
  {
    "id": "biscuits_voyage",
    "nom": "Biscuits de voyage",
    "description": "Biscuits très secs et résistants conçus pour être conservés plusieurs semaines.",
    "categorie": "boulangerie"
  },
  {
    "id": "pain_epices_miel",
    "nom": "Pain d'épices au miel",
    "description": "Pain dense et parfumé au miel, à la cannelle et au gingembre.",
    "categorie": "boulangerie"
  }
]
```

---

## ✍️ Auteur — 05/09/2026

Que pourrait vendre autre que du savon une savonnerie dans un monde médiéval fantastique ?

---

## 🤖 ChatGPT — 05/09/2026

Oui. Une **savonnerie médiévale** pourrait avoir une activité assez large autour de l’hygiène, des soins corporels, des parfums et de l’entretien domestique. Dans un monde fantastique, elle peut aussi proposer quelques produits liés à l'alchimie sans devenir une apothicairerie.

### Produits possibles

1. **Savon de cendre** — savon rustique fabriqué à partir de cendres et de graisse.
2. **Savon d’huile** — savon plus doux fabriqué avec une huile végétale.
3. **Savon parfumé** — savon enrichi de plantes ou d’huiles aromatiques.
4. **Savon au miel** — savon doux contenant du miel.
5. **Savon aux herbes** — parfumé au thym, romarin, lavande ou sauge.
6. **Savon médicinal** — savon destiné à nettoyer les plaies et la peau.
7. **Savon détachant** — savon particulièrement efficace pour le linge.
8. **Lessive de cendres** — solution alcaline utilisée pour laver le linge.
9. **Poudre à lessiver** — mélange de cendres, sels et poudres végétales.
10. **Cire à cheveux** — mélange de cire d’abeille et d’huiles pour entretenir et coiffer les cheveux.
11. **Pommade corporelle** — graisse ou huile parfumée destinée à protéger la peau.
12. **Huile parfumée** — huile utilisée pour le corps, les cheveux ou les vêtements.
13. **Parfum solide** — cire parfumée à appliquer sur la peau.
14. **Eau parfumée** — eau aromatique destinée à la toilette ou à parfumer les vêtements.
15. **Sachet parfumé** — petit sachet de plantes séchées destiné à parfumer les vêtements et les coffres.
16. **Bougie parfumée** — bougie à base de cire d’abeille ou de suif, parfumée aux plantes.
17. **Cire pour cuir** — produit servant à nourrir et imperméabiliser les chaussures et objets en cuir.
18. **Cire pour bois** — produit d’entretien pour meubles et objets en bois.
19. **Pâte à polir** — mélange abrasif doux pour nettoyer et faire briller certains objets.
20. **Sel de bain** — mélange de sel et de plantes aromatiques pour le bain.

### Pour ton système de boutiques

Je distinguerais ainsi les produits d'une savonnerie :

- **Hygiène :** savons, lessive, sels de bain
- **Cosmétique :** huiles, pommades, parfums, cire à cheveux
- **Entretien :** cire pour cuir, cire pour bois, pâte à polir
- **Parfumerie :** sachets parfumés, eaux parfumées, bougies parfumées

Cela donne une boutique qui reste cohérente historiquement tout en étant suffisamment intéressante pour les PNJ et les aventuriers.

---

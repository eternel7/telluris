# Images des livres — servies par `/livres`

- **Une image à la racine** de ce dossier devient un objet achetable dans les scriptoriums, le grand scriptorium et les bibliothèques (toujours au moins une planche en rayon, tirée au hasard ; d'autres viennent plus rarement par la production, au prix d'un livre de contenu). Rien à importer.
  - `carte_….jpg` → une **carte** 🗺️ ; tout autre nom → une **œuvre** 🖼️.
  - Le nom de l'objet vient du fichier : soulignés et tirets deviennent des espaces, la première lettre passe en capitale, la casse et les accents sont gardés (`carte_de_la_Beauce.jpg` → « Carte de la Beauce »).
  - L'objet est créé au premier tirage puis n'est plus retouché : renommer le fichier crée un autre objet.
- **Un sous-dossier** nommé comme l'id d'un livre sans « item: » (`ouvrage_critias/`) porte les illustrations de ce livre, montrées dans sa fiche dans l'ordre des noms de fichier (`01.jpg`, `02.jpg`…).
- Formats lus : `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`. Prise en compte en 30 secondes au plus.
- Convention du dossier : **`.webp`, 2048 px au plus** sur le côté le plus long, proportions d'origine. Une image reconvertie (même nom, autre extension) garde son objet.

Détail : `utils/livres_images.py`.

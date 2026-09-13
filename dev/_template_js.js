// dev/_template_js.js
//
// Source d'un template Jinja AVEC SES INCLUDES DÉVELOPPÉS — ce que les harnais Node lisent.
//
// POURQUOI : depuis que le mode Lieux vit dans des parts (`part-lieux-*.html`, partagés par
// /admin/editor et /admin/lieux), les fonctions extraites PAR NOM ne sont plus dans le texte
// d'admin_map_editor.html. Lire le template brut ferait échouer les harnais sur « fonction
// introuvable » alors que la page, elle, les a bien toutes.
//
// Seuls `{% include "x.html" %}` (guillemets simples ou doubles) sont développés, récursivement,
// depuis templates/. Un `{% import %}` est une macro sans script de page : laissé tel quel.

const fs = require('fs');
const path = require('path');

const DOSSIER = path.join(__dirname, '..', 'templates');

function lireAvecIncludes(chemin, pile) {
	const deja = pile || [];
	const absolu = path.resolve(chemin);
	if (deja.includes(absolu)) throw new Error('include circulaire : ' + absolu);
	// ⚠️ Commentaires Jinja retirés D'ABORD, comme au rendu : l'en-tête d'une part documente son
	// propre `{% include %}`, qu'on développerait sinon en boucle.
	const src = fs.readFileSync(absolu, 'utf8').replace(/\{#[\s\S]*?#\}/g, '');
	return src.replace(/\{%-?\s*include\s+["']([^"']+)["'][^%]*-?%\}/g, (_m, nom) =>
		lireAvecIncludes(path.join(DOSSIER, nom), deja.concat([absolu])));
}

// Corps concaténés des `<script>` sans `src`, includes compris — la forme que les harnais
// fouillent avec leur `extraire(nom)`.
function scriptsInline(src) {
	return [...src.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
		.map(m => m[1]).join('\n');
}

module.exports = { lireAvecIncludes, scriptsInline };

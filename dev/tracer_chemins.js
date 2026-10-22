// dev/tracer_chemins.js
//
// Chemins A → B sur une grille, par le tracé des voies de l'éditeur (templates/scripts/voies.js),
// le MÊME code que la carte « 🛤️ Tracer les voies » : la règle de pas est `pasAutoriseRegle`.
//
//   node dev/tracer_chemins.js entree.json > sortie.json
//
// entree.json : { cells, nav, dims: {x, y}, regle: "exploration" | "combat", max: 1-8,
//                 paires: [{ nom, a: [x, y], b: [x, y] }] }
// sortie : { paires: [{ nom, a, b, chemins: [[[x, y], …], …] }], regions: n }
// Une paire injoignable rend `chemins: []`. Appelé par dev/tracer_chemins.py.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SCRIPTS = path.join(__dirname, '..', 'templates', 'scripts');
for (const f of ['nav.js', 'deplacement.js', 'voies.js']) {
	const p = path.join(SCRIPTS, f);
	vm.runInThisContext(fs.readFileSync(p, 'utf8'), { filename: p });
}

const entree = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const dims = entree.dims;
const graphe = voiesGraphe(entree.cells, entree.nav || {}, dims, entree.regle || 'exploration');
const regions = voiesRegions(graphe);
const idx = ([x, y]) => y * dims.x + x;
const xy = i => [i % dims.x, Math.floor(i / dims.x)];
const sortie = {
	regions: regions.nb !== undefined ? regions.nb : null,
	paires: (entree.paires || []).map(p => ({
		nom: p.nom, a: p.a, b: p.b,
		chemins: voiesChemins(graphe, idx(p.a), idx(p.b), entree.max || 8).map(c => c.map(xy)),
	})),
};
process.stdout.write(JSON.stringify(sortie));

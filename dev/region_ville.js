// dev/region_ville.js
//
// Cases de la RÉGION DE LA VILLE d'une carte, par le MÊME code que « 📍 Compléter les positions »
// de /admin/lieux : `_regionCible` (extraite de templates/admin_lieux.html) sur les régions de
// templates/scripts/voies.js (règle d'exploration de deplacement.js, cells + nav, sans connexions).
//
//   node dev/region_ville.js entree.json > sortie.json
//
// entree.json : { cells, nav, dims: {x, y}, ancres: [[x, y], …], zone: [x, y] | null }
// sortie      : { rang, raison, taille, cases: [[x, y], …] }   (cases triées y puis x)
// Appelé par les générateurs de magasins (dev/gen_orleans_magasins.py).

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');

const SCRIPTS = path.join(__dirname, '..', 'templates', 'scripts');
for (const f of ['nav.js', 'deplacement.js', 'voies.js']) {
	const p = path.join(SCRIPTS, f);
	vm.runInThisContext(fs.readFileSync(p, 'utf8'), { filename: p });
}
const js = scriptsInline(lireAvecIncludes(path.join(__dirname, '..', 'templates', 'admin_lieux.html')));
const debut = js.indexOf('function _regionCible(');
if (debut < 0) throw new Error('_regionCible introuvable dans admin_lieux.html');
let prof = 0, fin = -1;
for (let j = js.indexOf('{', debut); j < js.length; j++) {
	if (js[j] === '{') prof++;
	else if (js[j] === '}' && --prof === 0) { fin = j + 1; break; }
}
vm.runInThisContext(js.slice(debut, fin));
const plancher = /const REGION_TAILLE_MIN = ([^;]+);/.exec(js);
if (!plancher) throw new Error('REGION_TAILLE_MIN introuvable dans admin_lieux.html');
vm.runInThisContext('var REGION_TAILLE_MIN = ' + plancher[1] + ';');

const e = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const W = e.dims.x, H = e.dims.y;
const { region, tailles } = voiesRegions(voiesGraphe(e.cells, e.nav || {}, e.dims, 'exploration'));
const cible = _regionCible(region, W, H, e.ancres || [], e.zone || null, REGION_TAILLE_MIN);
const cases = [];
for (let i = 0; i < region.length; i++) if (cible.rang >= 0 && region[i] === cible.rang) cases.push([i % W, Math.floor(i / W)]);
process.stdout.write(JSON.stringify({
	rang: cible.rang, raison: cible.raison, taille: cible.rang >= 0 ? tailles[cible.rang] : 0, cases,
}));

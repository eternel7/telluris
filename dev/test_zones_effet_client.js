// dev/test_zones_effet_client.js
//
// Tests d'EXÉCUTION du miroir client des zones d'effet (templates/scripts/zones_effet.js).
//
//   node dev/test_zones_effet_client.js     # sort en code 1 au premier échec
//
// POURQUOI : ce fichier n'est PAS la règle (le serveur résout les dégâts, cf.
// utils/zones_effet.py) — il dessine l'APERÇU des cases touchées pendant le ciblage. Un
// aperçu qui ment est pire que pas d'aperçu : le joueur paie une action et des PM sur la
// foi de ce qu'il voit. Les cas ci-dessous sont donc les MÊMES que ceux de
// tests/test_zones_effet.py, valeurs comprises — les deux fichiers se lisent en vis-à-vis,
// et une divergence de géométrie fait tomber l'un ou l'autre.
//
// MÉTHODE : comme test_deplacement_client, on charge DIRECTEMENT le `.js` — il n'a aucune
// dépendance. `vm.runInThisContext` et non `vm.createContext` : un contexte séparé est un
// autre realm, donc `deepStrictEqual` refuserait ses tableaux.
//
// La dernière section extrait EN PLUS `apercuZone`/`effacerApercuZone`/`_armerApercuZone`
// de `combat_telluris.html` et les joue contre un DOM factice — leur PARCOURS (ce qui est
// créé, placé, nettoyé), comme `majFleches` dans test_deplacement_client.
//
// HORS DE PORTÉE (à vérifier en jeu) : le RENDU proprement dit — la trigonométrie de
// `_placerToken` (ici remplacée par un espion), la superposition des calques, et le fait
// qu'un doigt n'a pas de survol.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const SCRIPT = path.join(__dirname, '..', 'templates', 'scripts', 'zones_effet.js');
assert.ok(fs.existsSync(SCRIPT), 'fichier introuvable : ' + SCRIPT);
vm.runInThisContext(fs.readFileSync(SCRIPT, 'utf8'), { filename: SCRIPT });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Ensemble de cases, insensible à l'ordre — pour les cas où seul le contenu compte.
function ens(cases) { return new Set(cases.map(c => c[0] + ',' + c[1])); }
function a(cases) { return cases.map(c => c[0] + ',' + c[1]).sort(); }

console.log('\n── Normalisation ───────────────────────────────────────────────────────────');

t('bloc absent ou forme inconnue ⇒ null (capacité mono-case)', () => {
	assert.strictEqual(normaliserZone(null), null);
	assert.strictEqual(normaliserZone({}), null);
	assert.strictEqual(normaliserZone({ forme: 'triangle' }), null);
	assert.strictEqual(normaliserZone('cercle'), null);
});

t('toutes les clés présentes, même celles des autres formes', () => {
	const z = normaliserZone({ forme: 'CERCLE', rayon: 3 });
	assert.deepStrictEqual(z, {
		forme: 'cercle', origine: 'cible', orientation: 'cible',
		rayon: 3, longueur: 1, largeur: 1, decalage: 0, angle: 90,
	});
});

t('valeurs hors contrat : défaut pour les énumérations, bornes pour les nombres', () => {
	const z = normaliserZone({ forme: 'cone', origine: 'ailleurs', orientation: 'lune',
							   longueur: 999, angle: 0 });
	assert.strictEqual(z.origine, 'cible');
	assert.strictEqual(z.orientation, 'cible');
	assert.strictEqual(z.longueur, 12);
	assert.strictEqual(z.angle, 1, 'jamais 0 : un cône d’ouverture nulle ne touche rien');
});

t('rayon absent = 1, rayon 0 écrit = 0 (la clé écrite fait foi)', () => {
	assert.strictEqual(normaliserZone({ forme: 'carre' }).rayon, 1);
	assert.strictEqual(normaliserZone({ forme: 'carre', rayon: 0 }).rayon, 0);
	assert.strictEqual(normaliserZone({ forme: 'carre', rayon: 99 }).rayon, 8);
});

console.log('\n── Ancre et axe ────────────────────────────────────────────────────────────');

t('l’ancre suit `origine`', () => {
	assert.deepStrictEqual(zoneAncre(normaliserZone({ forme: 'cercle' }), [5, 5], [7, 3]), [7, 3]);
	assert.deepStrictEqual(
		zoneAncre(normaliserZone({ forme: 'cercle', origine: 'lanceur' }), [5, 5], [7, 3]), [5, 5]);
});

t('l’axe vers la cible est ramené au huitième de tour le plus proche', () => {
	const z = normaliserZone({ forme: 'cone' });
	assert.deepStrictEqual(zoneAxe(z, [5, 5], [5, 1], 0), [0, -1]);
	assert.deepStrictEqual(zoneAxe(z, [5, 5], [9, 5], 0), [1, 0]);
	assert.deepStrictEqual(zoneAxe(z, [5, 5], [8, 2], 0), [1, -1]);
	assert.deepStrictEqual(zoneAxe(z, [5, 5], [10, 4], 0), [1, 0], 'presque aligné ⇒ cardinal');
});

t('`facing` : mêmes quarts que rot() de combat_telluris, replis compris', () => {
	assert.deepStrictEqual(zoneAxeFacing(0), [0, -1]);
	assert.deepStrictEqual(zoneAxeFacing(90), [1, 0]);
	assert.deepStrictEqual(zoneAxeFacing(180), [0, 1]);
	assert.deepStrictEqual(zoneAxeFacing(270), [-1, 0]);
	assert.deepStrictEqual(zoneAxeFacing(45), [0, -1], 'hors des quarts ⇒ nord');
	const z = normaliserZone({ forme: 'cone', orientation: 'facing' });
	assert.deepStrictEqual(zoneAxe(z, [5, 5], [9, 5], 180), [0, 1]);
	// Cible posée SUR le lanceur : aucun axe à lire, repli sur le facing.
	assert.deepStrictEqual(zoneAxe(normaliserZone({ forme: 'cone' }), [5, 5], [5, 5], 90), [1, 0]);
});

console.log('\n── Les quatre figures de référence ─────────────────────────────────────────');

t('boule de feu : cercle EUCLIDIEN de rayon 2 sur la cible (13 cases)', () => {
	const cases = casesZone(normaliserZone({ forme: 'cercle', rayon: 2 }), [5, 5], [5, 3], 0);
	assert.strictEqual(cases.length, 13);
	const s = ens(cases);
	assert.ok(s.has('5,3'), 'la cible désignée, au centre');
	assert.ok(s.has('5,1') && s.has('3,3'), 'les pointes cardinales');
	assert.ok(s.has('4,2'), 'la diagonale proche');
	assert.ok(!s.has('3,1'), 'le coin (2√2) reste dehors');
});

t('tourbillon : carré de CHEBYSHEV de rayon 1 autour de soi (9 cases)', () => {
	const z = normaliserZone({ forme: 'carre', origine: 'lanceur', rayon: 1 });
	const attendu = [];
	for (const x of [4, 5, 6]) for (const y of [4, 5, 6]) attendu.push([x, y]);
	assert.deepStrictEqual(a(casesZone(z, [5, 5], [5, 4], 0)), a(attendu));
});

t('cercle et carré de rayon 1 sont DEUX figures distinctes', () => {
	const croix = casesZone(normaliserZone({ forme: 'cercle', rayon: 1 }), [0, 0], [0, 0], 0);
	const carre = casesZone(normaliserZone({ forme: 'carre', rayon: 1 }), [0, 0], [0, 0], 0);
	assert.strictEqual(croix.length, 5);
	assert.strictEqual(carre.length, 9);
	assert.ok(ens(carre).has('1,1') && !ens(croix).has('1,1'));
});

t('coup d’épée : les trois cases DEVANT', () => {
	const z = normaliserZone({ forme: 'rectangle', origine: 'lanceur',
							   longueur: 1, largeur: 3, decalage: 1 });
	assert.deepStrictEqual(a(casesZone(z, [5, 5], [5, 4], 0)), a([[4, 4], [5, 4], [6, 4]]));
});

t('coup d’épée en diagonale : une bande EN BIAIS, pas un escalier', () => {
	const z = normaliserZone({ forme: 'rectangle', origine: 'lanceur',
							   longueur: 1, largeur: 3, decalage: 1 });
	assert.deepStrictEqual(a(casesZone(z, [5, 5], [6, 4], 0)), a([[5, 3], [6, 4], [7, 5]]));
});

t('souffle de feu : cône de 90° qui s’élargit de 2 par cran (3 + 5 + 7)', () => {
	const z = normaliserZone({ forme: 'cone', origine: 'lanceur', longueur: 3, decalage: 1 });
	const cases = casesZone(z, [5, 5], [5, 3], 0);
	assert.strictEqual(cases.length, 15);
	assert.deepStrictEqual(a(cases.filter(c => c[1] === 4)), a([[4, 4], [5, 4], [6, 4]]));
	assert.deepStrictEqual(a(cases.filter(c => c[1] === 3)),
						   a([[3, 3], [4, 3], [5, 3], [6, 3], [7, 3]]));
	assert.ok(!ens(cases).has('5,5'), '`decalage: 1` épargne le lanceur');
});

console.log('\n── Ouverture, décalage, cas limites ────────────────────────────────────────');

t('l’ouverture du cône pilote sa largeur', () => {
	const base = { forme: 'cone', origine: 'lanceur', longueur: 2, decalage: 1 };
	const etroit = casesZone(normaliserZone(Object.assign({}, base, { angle: 20 })), [5, 5], [5, 3], 0);
	const large = casesZone(normaliserZone(Object.assign({}, base, { angle: 180 })), [5, 5], [5, 3], 0);
	assert.deepStrictEqual(a(etroit), a([[5, 4], [5, 3]]), 'un simple rayon');
	assert.ok(large.length > casesZone(normaliserZone(base), [5, 5], [5, 3], 0).length);
});

t('`decalage` repousse la forme le long de l’axe', () => {
	const z = normaliserZone({ forme: 'rectangle', origine: 'lanceur',
							   longueur: 2, largeur: 1, decalage: 2 });
	assert.deepStrictEqual(casesZone(z, [5, 5], [5, 4], 0), [[5, 2], [5, 3]]);
	// decalage 0 ⇒ la forme commence SUR l'ancre (ici le lanceur lui-même).
	const z0 = normaliserZone({ forme: 'rectangle', origine: 'lanceur', longueur: 2, largeur: 1 });
	assert.ok(ens(casesZone(z0, [5, 5], [5, 4], 0)).has('5,5'));
});

t('forme orientée ancrée sur la CIBLE : la cible est la première case', () => {
	const z = normaliserZone({ forme: 'rectangle', longueur: 1, largeur: 5 });
	assert.deepStrictEqual(a(casesZone(z, [5, 5], [5, 2], 0)),
						   a([[3, 2], [4, 2], [5, 2], [6, 2], [7, 2]]));
});

t('largeur PAIRE : débordement à droite (cas limite assumé)', () => {
	const z = normaliserZone({ forme: 'rectangle', origine: 'lanceur',
							   longueur: 1, largeur: 2, decalage: 1 });
	assert.deepStrictEqual(casesZone(z, [5, 5], [5, 4], 0), [[5, 4], [6, 4]]);
});

t('sortie triée par (y, x) et sans doublon — même ordre que le serveur', () => {
	const cases = casesZone(normaliserZone({ forme: 'carre', rayon: 1 }), [0, 0], [0, 0], 0);
	const trie = cases.slice().sort((p, q) => (p[1] - q[1]) || (p[0] - q[0]));
	assert.deepStrictEqual(cases, trie);
	assert.strictEqual(new Set(cases.map(c => c.join(','))).size, cases.length);
});

console.log('\n── Filtrage par la carte (casesEffet) ──────────────────────────────────────');

// Grille 7×5, mur vertical en x=4 sauf une ouverture en y=2 — la même que côté pytest.
//         x= 0  1  2  3  4  5  6
const CELLS = [
	[1, 1, 1, 1, 0, 1, 1],   // y=0
	[1, 1, 1, 1, 0, 1, 1],   // y=1
	[1, 1, 1, 1, 1, 1, 1],   // y=2
	[1, 1, 1, 1, 0, 1, 1],   // y=3
	[1, 1, 1, 1, 0, 1, 1],   // y=4
];
const DIMS = { x: 7, y: 5 };

t('les murs sont écartés, l’ouverture non', () => {
	const cases = ens(casesEffet(normaliserZone({ forme: 'carre', rayon: 1 }),
								 [2, 2], [3, 1], 0, CELLS, DIMS));
	assert.ok(!cases.has('4,0') && !cases.has('4,1'), 'le mur');
	assert.ok(cases.has('4,2'), 'l’ouverture');
});

t('une explosion ne contourne pas l’angle d’un couloir', () => {
	const cases = ens(casesEffet(normaliserZone({ forme: 'carre', rayon: 2 }),
								 [0, 2], [3, 2], 0, CELLS, DIMS));
	assert.ok(cases.has('5,2'), 'dans l’axe de l’ouverture');
	assert.ok(!cases.has('5,0'), 'à l’abri derrière le mur');
	assert.ok(cases.has('3,2'), 'l’ancre n’est jamais écartée par la ligne de vue');
});

t('ce qui sort de la carte n’est pas peint', () => {
	const cases = casesEffet(normaliserZone({ forme: 'carre', rayon: 2 }),
							 [0, 0], [0, 0], 0, CELLS, DIMS);
	assert.ok(cases.every(c => c[0] >= 0 && c[1] >= 0 && c[0] < DIMS.x && c[1] < DIMS.y));
});

t('ligneDeVueZone : miroir de _line_of_sight (extrémités jamais bloquantes)', () => {
	assert.strictEqual(ligneDeVueZone(CELLS, 3, 0, 5, 0), false, 'le mur en x=4');
	assert.strictEqual(ligneDeVueZone(CELLS, 3, 2, 5, 2), true, 'l’ouverture en y=2');
	assert.strictEqual(ligneDeVueZone(CELLS, 4, 0, 4, 0), true, 'une case sur elle-même');
	assert.strictEqual(ligneDeVueZone(CELLS, 3, 0, 4, 0), true, 'le mur EST l’extrémité');
});

console.log('\n── Étiquette d’infobulle ───────────────────────────────────────────────────');

t('libelleZone : vide sans zone, et décrit la forme sinon', () => {
	assert.strictEqual(libelleZone(null), '');
	assert.ok(libelleZone(normaliserZone({ forme: 'cercle', rayon: 2 })).includes('rayon 2'));
	assert.ok(libelleZone(normaliserZone({ forme: 'carre', rayon: 2 })).includes('carré rayon 2'));
	assert.ok(libelleZone(normaliserZone({ forme: 'cone', longueur: 3 })).includes('cône 3'));
	assert.ok(libelleZone(normaliserZone({ forme: 'rectangle', longueur: 1, largeur: 3 }))
		.includes('1×3'));
});

t('libelleZone : une capacité `soi` ne dit JAMAIS « sur la cible »', () => {
	// Elle n'en désigne aucune, quelle que soit l'`origine` écrite dans la donnée — le
	// moteur ancre de toute façon la forme sur le lanceur.
	const z = normaliserZone({ forme: 'cercle', origine: 'cible', rayon: 2 });
	assert.ok(libelleZone(z, 'ennemi').includes('sur la cible'));
	assert.ok(libelleZone(z, 'soi').includes('autour de soi'));
	assert.ok(!libelleZone(z, 'soi').includes('sur la cible'));
});

t('libelleZone : l’icône suit le camp, comme la couleur de l’aperçu', () => {
	const z = normaliserZone({ forme: 'carre', rayon: 1 });
	assert.ok(libelleZone(z, 'ennemi').startsWith('💥'));
	assert.ok(libelleZone(z, 'allie').startsWith('✨'));
	assert.ok(libelleZone(z, 'soi').startsWith('✨'));
	assert.ok(libelleZone(z).startsWith('💥'), 'camp inconnu ⇒ offensif, comme avant');
});

console.log('\n── Aperçu sur la carte (combat_telluris.html) ──────────────────────────────');

// Le PARCOURS de l'aperçu, avec un DOM factice — comme `majFleches` dans
// test_deplacement_client : on éprouve ce que le code crée, place et nettoie, pas ce que
// le navigateur peint (il faudrait jsdom, que le projet n'a pas). Extraction par NOM :
// renommer une de ces fonctions fait échouer ici, et c'est voulu.
const TEMPLATE = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const srcTpl = fs.readFileSync(TEMPLATE, 'utf8');
const jsTpl = (srcTpl.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/i) || [])[1];
assert.ok(jsTpl, 'aucun bloc <script> inline dans ' + TEMPLATE);

function extraire(nom) {
	const debut = jsTpl.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable dans le template');
	let prof = 0;
	for (let j = jsTpl.indexOf('{', debut); j < jsTpl.length; j++) {
		if (jsTpl[j] === '{') prof++;
		else if (jsTpl[j] === '}' && --prof === 0) return jsTpl.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

// DOM factice minimal : de quoi créer, empiler et retirer des éléments.
function elementFactice() {
	const el = { className: '', style: {}, enfants: [], parent: null,
				 onpointerenter: undefined, onpointerleave: undefined };
	el.appendChild = (c) => { c.parent = el; el.enfants.push(c); return c; };
	el.remove = () => {
		if (!el.parent) return;
		el.parent.enfants = el.parent.enfants.filter(c => c !== el);
		el.parent = null;
	};
	return el;
}
const LAYER = elementFactice();
globalThis.document = { createElement: () => elementFactice(),
						getElementById: (id) => (id === 'tokens-layer' ? LAYER : null) };
// `_placerToken` du template repose sur la caméra et les variables CSS : on n'éprouve pas
// sa trigonométrie ici (elle est commune à tous les jetons), seulement qu'elle est APPELÉE
// avec l'écart MONDE, et avant l'insertion dans le calque.
const PLACEMENTS = [];
globalThis._placerToken = (el, wx, wy) => {
	assert.strictEqual(el.parent, null, 'placé AVANT insertion : pas de transition à la naissance');
	PLACEMENTS.push([wx, wy]);
	el.style.transform = `w(${wx},${wy})`;
};
globalThis.GRID = { dims: DIMS, cells: CELLS };
globalThis.me = () => ({ id: 'joueur_0', pos: { x: 2, y: 2 }, facing: 0 });

// ⚠️ UN SEUL script : `const _apercuZoneCases` est une liaison lexicale de script, elle ne
// serait pas visible des fonctions chargées séparément.
vm.runInThisContext([
	'const _apercuZoneCases = [];',
	extraire('effacerApercuZone'),
	extraire('apercuZone'),
	extraire('_armerApercuZone'),
].join('\n'), { filename: 'combat_telluris.html:apercuZone' });

t('apercuZone peint une case par case touchée, placée en coordonnées MONDE', () => {
	PLACEMENTS.length = 0;
	const capa = { zone: { forme: 'carre', origine: 'lanceur', rayon: 1 } };
	apercuZone(capa, { pos: { x: 2, y: 1 } });
	// Lanceur en (2,2), carré de rayon 1 : 9 cases, toutes dans la grille 7×5.
	assert.strictEqual(LAYER.enfants.length, 9);
	assert.ok(LAYER.enfants.every(e => e.className === 'zone-case'));
	assert.deepStrictEqual(a(PLACEMENTS), a([[-1, -1], [0, -1], [1, -1],
											 [-1, 0], [0, 0], [1, 0],
											 [-1, 1], [0, 1], [1, 1]]));
});

t('un second aperçu REMPLACE le premier (aucune traînée)', () => {
	apercuZone({ zone: { forme: 'cercle', rayon: 1 } }, { pos: { x: 2, y: 1 } });
	assert.strictEqual(LAYER.enfants.length, 5, 'la croix, et rien du carré précédent');
	effacerApercuZone();
	assert.strictEqual(LAYER.enfants.length, 0);
});

t('capacité SANS zone : rien n’est peint, et ce qui restait est effacé', () => {
	apercuZone({ zone: { forme: 'carre', rayon: 1 } }, { pos: { x: 2, y: 2 } });
	assert.ok(LAYER.enfants.length > 0);
	apercuZone({ zone: null }, { pos: { x: 2, y: 2 } });
	assert.strictEqual(LAYER.enfants.length, 0);
});

t('cible ou position manquante : aucun plantage, aucune case', () => {
	apercuZone({ zone: { forme: 'carre', rayon: 1 } }, null);
	assert.strictEqual(LAYER.enfants.length, 0);
	apercuZone({ zone: { forme: 'carre', rayon: 1 } }, {});
	assert.strictEqual(LAYER.enfants.length, 0);
	apercuZone(null, { pos: { x: 2, y: 1 } });
	assert.strictEqual(LAYER.enfants.length, 0);
});

t('capacité BÉNÉFIQUE : les cases portent la variante verte', () => {
	apercuZone({ cible: 'allie', zone: { forme: 'carre', origine: 'lanceur', rayon: 1 } },
			   { pos: { x: 2, y: 1 } });
	assert.ok(LAYER.enfants.every(e => e.className === 'zone-case soutien'));
	effacerApercuZone();
});

t('capacité `soi` : la forme se pose sur le LANCEUR, sans cible désignée', () => {
	PLACEMENTS.length = 0;
	// Aucune cible passée (une case de la barre n'en connaît pas) : l'ancre est le
	// lanceur, en (2,2) — mêmes 9 cases, toutes centrées sur lui.
	apercuZone({ cible: 'soi', zone: { forme: 'carre', origine: 'cible', rayon: 1 } }, null);
	assert.strictEqual(LAYER.enfants.length, 9);
	assert.ok(LAYER.enfants.every(e => e.className === 'zone-case soutien'));
	assert.deepStrictEqual(a(PLACEMENTS), a([[-1, -1], [0, -1], [1, -1],
											 [-1, 0], [0, 0], [1, 0],
											 [-1, 1], [0, 1], [1, 1]]));
	effacerApercuZone();
});

t('_armerApercuZone : une capacité `soi` s’arme SANS cible (sa case suffit)', () => {
	const casebtn = elementFactice();
	_armerApercuZone(casebtn, { cible: 'soi', zone: { forme: 'carre', rayon: 1 } }, null);
	assert.strictEqual(typeof casebtn.onpointerenter, 'function');
	// Une capacité CIBLÉE, elle, n'a rien à montrer tant qu'aucune cible n'est connue.
	_armerApercuZone(casebtn, { cible: 'ennemi', zone: { forme: 'carre', rayon: 1 } }, null);
	assert.strictEqual(casebtn.onpointerenter, null);
});

t('_armerApercuZone REMET À NULL : un jeton réutilisé ne garde pas l’ancien survol', () => {
	const jeton = elementFactice();
	_armerApercuZone(jeton, { zone: { forme: 'carre', rayon: 1 } }, { pos: { x: 2, y: 1 } });
	assert.strictEqual(typeof jeton.onpointerenter, 'function');
	_armerApercuZone(jeton, null, { pos: { x: 2, y: 1 } });
	assert.strictEqual(jeton.onpointerenter, null);
	assert.strictEqual(jeton.onpointerleave, null);
	// Capacité sans zone : ciblable, mais rien à montrer au survol.
	_armerApercuZone(jeton, { zone: null }, { pos: { x: 2, y: 1 } });
	assert.strictEqual(jeton.onpointerenter, null);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).\n`);
process.exit(echecs ? 1 : 0);

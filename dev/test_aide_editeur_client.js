// dev/test_aide_editeur_client.js
//
// Tests de la visite guidée « ? » de /admin/editor (templates/admin_map_editor.html,
// bloc `AIDE_ED_ETAPES` en fin de fichier).
//
//   node dev/test_aide_editeur_client.js     # sort en code 1 au premier échec
//
// POURQUOI : la visite promet de ne RIEN modifier. Un appel réseau, un `setMode`, un clic
// simulé ou une valeur de champ affectée glissés dans son code casseraient la promesse sans
// qu'aucun autre test ne le voie. Et une étape dont la cible a été renommée s'afficherait
// sans projecteur, avec l'avis « pas affiché pour le moment » pour toujours.
//
// MÉTHODE : le bloc <script> de la visite est extrait entier, scanné (motifs d'écriture
// interdits), puis exécuté dans un contexte `vm` avec un DOM minimal semé (getElementById,
// querySelector, localStorage) pour la navigation : bornes, Suivant/Terminer, Échap.
//
// HORS DE PORTÉE (vérifié au rendu, Playwright) : la place du projecteur et de la carte.

const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_map_editor.html');
const src = require('./_template_js').lireAvecIncludes(TEMPLATE);
const blocs = [...src.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]);
const aide = blocs.filter(b => b.includes('const AIDE_ED_ETAPES'));

let echecs = 0;
function test(nom, fn) {
	try { fn(); console.log('  ✓ ' + nom); }
	catch (e) { echecs++; console.log('  ✗ ' + nom + '\n      ' + e.message); }
}

test('un seul bloc de visite', () => assert.strictEqual(aide.length, 1));
const code = aide[0] || '';

test('la visite n\'écrit rien (aucun motif d\'écriture dans son code)', () => {
	const interdits = [
		/\bfetch\s*\(/, /XMLHttpRequest/, /sendBeacon/, /\bsetMode\s*\(/, /\.click\s*\(/,
		/dispatchEvent/, /scheduleGridSend|sendGrid/, /\.value\s*=[^=]/, /\.checked\s*=[^=]/,
		/\bgrid\s*\[/, /\bnav\s*\[/, /editMode\s*=[^=]/,
	];
	// Commentaires retirés : ils CITENT les gestes interdits pour dire qu'on ne les fait pas.
	const sans = code.replace(/\/\/[^\n]*/g, '');
	for (const re of interdits) assert.ok(!re.test(sans), 'motif interdit dans la visite : ' + re);
	// Le seul stockage écrit est le drapeau « déjà vue » du pouls.
	const ecrits = [...sans.matchAll(/localStorage\.setItem\(\s*([A-Z_]+)/g)].map(m => m[1]);
	assert.deepStrictEqual(ecrits, ['AIDE_ED_VUE']);
});

// ── Exécution, DOM minimal ──────────────────────────────────────────────────
function element(id) {
	const attrs = {};
	const classes = new Set();
	return {
		id, hidden: false, textContent: '', innerHTML: '', disabled: false, scrollTop: 0,
		offsetWidth: 400, offsetHeight: 300, style: {}, children: [],
		classList: { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c) },
		setAttribute: (k, v) => { attrs[k] = v; }, removeAttribute: k => { delete attrs[k]; },
		getAttribute: k => attrs[k], focus() { ctx.document.activeElement = this; },
		closest: () => null, getClientRects: () => [1],
		getBoundingClientRect: () => ({ top: 10, left: 10, right: 110, bottom: 60 }),
		scrollIntoView: () => {},
	};
}
const els = {};
['aide-ed-overlay', 'aide-ed-spot', 'aide-ed-carte', 'aide-ed-titre', 'aide-ed-compteur', 'aide-ed-corps',
	'aide-ed-points', 'aide-ed-prec', 'aide-ed-suiv', 'aide-ed-btn'].forEach(id => { els[id] = element(id); });
els['aide-ed-overlay'].hidden = true;
const ecouteurs = [];
const stockage = {};
const ctx = {
	window: { innerWidth: 1400, innerHeight: 900, addEventListener: () => {} },
	localStorage: { getItem: k => stockage[k] ?? null, setItem: (k, v) => { stockage[k] = String(v); } },
	requestAnimationFrame: f => f(),
	_escHtml: s => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`),
	document: {
		activeElement: null,
		getElementById: id => els[id] || null,
		// Toute cible d'étape est « présente » ; les pastilles, elles, sont lues dans `points`.
		querySelector: () => element('cible'),
		querySelectorAll: sel => sel.startsWith('#aide-ed-points') ? pastilles : [],
		addEventListener: (type, fn, capture) => ecouteurs.push({ type, fn, capture }),
	},
};
let pastilles = [];
vm.createContext(ctx);
if (code) vm.runInContext(code + '\nthis.AIDE_ED_ETAPES = AIDE_ED_ETAPES; this.etape = () => aideEdEtape;', ctx);
const N = ctx.AIDE_ED_ETAPES ? ctx.AIDE_ED_ETAPES.length : 0;

test('chaque cible d\'étape existe dans le markup de la page', () => {
	assert.ok(N > 0);
	for (const e of ctx.AIDE_ED_ETAPES) {
		if (!e.cible) continue;
		const m = /^([#.])([\w-]+)$/.exec(e.cible);
		assert.ok(m, 'sélecteur simple attendu : ' + e.cible);
		const re = m[1] === '#' ? new RegExp(`id="${m[2]}"`) : new RegExp(`class="(?:[^"]*\\s)?${m[2]}(?:\\s[^"]*)?"`);
		assert.ok(re.test(src), 'cible absente du template : ' + e.cible);
	}
});

test('pouls tant que la visite n\'a jamais été ouverte', () => {
	assert.ok(els['aide-ed-btn'].classList.contains('aide-pouls'));
});

test('ouvrir : étape 1, Précédent grisé, pouls éteint et mémorisé', () => {
	// Pastilles fabriquées par `ouvrirAideEditeur` : une par étape.
	pastilles = Array.from({ length: N }, () => element('p'));
	els['aide-ed-points'].children = pastilles;
	ctx.ouvrirAideEditeur();
	assert.strictEqual(els['aide-ed-overlay'].hidden, false);
	assert.strictEqual(ctx.etape(), 0);
	assert.strictEqual(els['aide-ed-compteur'].textContent, `1 / ${N}`);
	assert.strictEqual(els['aide-ed-prec'].disabled, true);
	assert.strictEqual(pastilles[0].getAttribute('aria-current'), 'step');
	assert.ok(!els['aide-ed-btn'].classList.contains('aide-pouls'));
	assert.strictEqual(stockage['editeur-carte.aide_vue'], '1');
});

test('sauter à une étape, puis hors bornes ignoré', () => {
	ctx.aideEditeurAller(5);
	assert.strictEqual(ctx.etape(), 5);
	assert.strictEqual(pastilles[5].getAttribute('aria-current'), 'step');
	assert.strictEqual(pastilles[0].getAttribute('aria-current'), undefined);
	ctx.aideEditeurAller(-1); ctx.aideEditeurAller(N);
	assert.strictEqual(ctx.etape(), 5);
});

test('dernière étape : « Terminer » ferme la visite', () => {
	ctx.aideEditeurAller(N - 1);
	assert.match(els['aide-ed-suiv'].textContent, /Terminer/);
	ctx.aideEditeurSuivant();
	assert.strictEqual(els['aide-ed-overlay'].hidden, true);
});

test('Échap arrête la visite en CAPTURE, sans atteindre le gestionnaire de l\'éditeur', () => {
	const kd = ecouteurs.find(l => l.type === 'keydown');
	assert.ok(kd && kd.capture === true, 'écouteur keydown en capture attendu');
	ctx.ouvrirAideEditeur();
	ctx.aideEditeurAller(3);
	let arrete = false;
	kd.fn({ key: 'ArrowRight', preventDefault() {}, stopImmediatePropagation() {} });
	assert.strictEqual(ctx.etape(), 4);
	kd.fn({ key: 'Escape', preventDefault() {}, stopImmediatePropagation() { arrete = true; } });
	assert.strictEqual(els['aide-ed-overlay'].hidden, true);
	assert.ok(arrete);
	// Fermée : Échap repart à l'éditeur.
	arrete = false;
	kd.fn({ key: 'Escape', preventDefault() {}, stopImmediatePropagation() { arrete = true; } });
	assert.ok(!arrete);
});

if (echecs) { console.log(`\n${echecs} échec(s)`); process.exit(1); }
console.log('\nOK — visite guidée de l\'éditeur');

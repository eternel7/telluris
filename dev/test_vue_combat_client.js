// dev/test_vue_combat_client.js
//
// Tests d'EXÉCUTION de l'échelle du viewport de combat (`syncViewSize`, combat_telluris.html).
//
//   node dev/test_vue_combat_client.js     # sort en code 1 au premier échec
//
// POURQUOI : --step et --view-width variaient d'un tick à l'autre SANS action de l'utilisateur.
// La largeur mesurée dépend de ce que la fonction écrit (un --step plus grand allonge la carte,
// fait apparaître la barre de défilement et rétrécit la colonne) et le ResizeObserver relançait
// le calcul à chaque notification : boucle de rétroaction. Règle verrouillée ici — deux appels
// successifs sans changement de fenêtre rendent la MÊME échelle et n'écrivent plus rien.
//
// MÉTHODE : `tailleVue`, `_largeurVue`, `_appliquerVue`, `syncViewSize`, `_surRedimensionnement`
// et leurs deux `let` sont extraits PAR NOM du template (lu par `_template_js`, includes
// développés), dans UN seul script — les `let` sont des liaisons lexicales de script. Le DOM est
// remplacé par un MODÈLE DE MISE EN PAGE : la colonne perd la largeur de la barre de défilement
// dès que la page (autres blocs + carte de step×(MAX_H−1) px) dépasse la hauteur de fenêtre.
//
// HORS DE PORTÉE (à vérifier à l'écran) : la mise en page réelle du navigateur (grille à trois
// colonnes, largeur des panneaux latéraux, largeur effective de la barre).

const path = require('path');
const assert = require('assert');
const vm = require('vm');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const js = scriptsInline(lireAvecIncludes(TEMPLATE));

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

function extraire(nom) {
	const debut = js.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable dans le template');
	let prof = 0;
	for (let j = js.indexOf('{', debut); j < js.length; j++) {
		if (js[j] === '{') prof++;
		else if (js[j] === '}' && --prof === 0) return js.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}
function extraireLet(nom) {
	const m = js.match(new RegExp('^let ' + nom + '\\b[^\\n]*$', 'm'));
	assert.ok(m, 'let ' + nom + ' introuvable dans le template');
	return m[0];
}

// ── Modèle de mise en page ──────────────────────────────────────────────────────
const MAX_H = 10;   // rangées visibles (MAX_H du template) ; --floor vaut 0
const monde = {};
const ROOT = { vars: {}, ecritures: 0,
			   style: { setProperty(k, v) { ROOT.vars[k] = v; ROOT.ecritures++; } } };
function stepPx() { return parseFloat(ROOT.vars['--step']) || 24; }   // 24px : repli CSS de :root
function barreVisible() { return monde.autresHauteurs + stepPx() * (MAX_H - 1) > monde.hauteur; }
const CENTRE = {
	get clientWidth() {
		if (monde.colonneMasquee) return 0;
		return monde.largeur - monde.lateraux - (barreVisible() ? monde.barre : 0);
	},
};
let coupures = 0, rendus = 0;
globalThis.document = { documentElement: ROOT, querySelector: s => (s === '.combat-center' ? CENTRE : null) };
globalThis.window = { get innerWidth() { return monde.largeur; }, _combatReady: true };
globalThis.sansAnimationCarte = () => { coupures++; };
globalThis.renderTokens = () => { rendus++; };
globalThis.updateCamera = () => {};

vm.runInThisContext([
	extraireLet('_vueResolue'), extraireLet('_stepApplique'),
	extraire('tailleVue'), extraire('_largeurVue'), extraire('_appliquerVue'),
	extraire('syncViewSize'), extraire('_surRedimensionnement'),
].join('\n'), { filename: 'combat_telluris.html:syncViewSize' });

// Page neuve : état du template remis à zéro (affectation des `let` existants, pas redéclaration).
function page(opts) {
	Object.assign(monde, { largeur: 1200, hauteur: 800, lateraux: 0, autresHauteurs: 420,
						   barre: 17, colonneMasquee: false }, opts || {});
	vm.runInThisContext('_vueResolue = null; _stepApplique = null;');
	ROOT.vars = {};
	ROOT.ecritures = 0;
	coupures = 0;
	rendus = 0;
}

// L'ANCIENNE formule, sans garde — seulement pour prouver que le modèle reproduit la rétroaction.
function ancienneSync() {
	const step = Math.max(8, CENTRE.clientWidth / 17) - 1;
	ROOT.style.setProperty('--step', step + 'px');
	return step;
}

console.log('\n── tailleVue (pure) ────────────────────────────────────────────────────────');

t('pas entier, plancher à 8, jamais plus large que la colonne, croissant', () => {
	let avant = 0;
	for (let w = 0; w <= 3000; w++) {
		const r = tailleVue(w);
		assert.ok(Number.isInteger(r.step) && r.step >= 8, 'w=' + w);
		assert.strictEqual(r.viewWidth, r.step * 17);
		if (w >= 170) assert.ok(r.viewWidth <= w - 17, 'déborde à w=' + w);
		assert.ok(r.step >= avant, 'décroît à w=' + w);
		avant = r.step;
	}
});

console.log('\n── Rétroaction barre de défilement ↔ largeur mesurée ───────────────────────');

t('le modèle REPRODUIT l’oscillation avec l’ancienne formule', () => {
	page({ hauteur: 1040 });
	const a = ancienneSync(), b = ancienneSync(), c = ancienneSync();
	assert.notStrictEqual(a, b, 'aucune oscillation : le scénario ne teste rien');
	assert.strictEqual(a, c);
});

t('même scénario : deux appels successifs rendent la même échelle et n’écrivent plus rien', () => {
	page({ hauteur: 1040 });
	const r1 = syncViewSize();
	const vars = Object.assign({}, ROOT.vars), ecritures = ROOT.ecritures, coupe = coupures;
	for (let i = 0; i < 10; i++) assert.deepStrictEqual(syncViewSize(), r1, 'appel ' + (i + 2));
	assert.deepStrictEqual(ROOT.vars, vars);
	assert.strictEqual(ROOT.ecritures, ecritures, 'une écriture sans action utilisateur');
	assert.strictEqual(coupures, coupe, 'une animation coupée sans action utilisateur');
	assert.strictEqual(r1.step, 68, 'le plus petit des deux pas en conflit');
	assert.strictEqual(ROOT.vars['--view-width'], (r1.step * 17) + 'px');
});

t('balayage : largeurs × hauteurs × panneaux latéraux, toujours idempotent et sans débordement', () => {
	let oscillants = 0;
	[0, 560].forEach(lateraux => [500, 700, 900, 1040, 1200].forEach(hauteur => {
		// Colonne d'au moins 320 px : `.combat-center` porte `min-width: 300px`, une colonne
		// négative n'existe pas (et n'écrit rien — cas couvert à part, colonne à 0 px).
		for (let largeur = lateraux + 320; largeur <= 2000; largeur += 3) {
			page({ largeur, hauteur, lateraux });
			const a = ancienneSync(), b = ancienneSync();
			if (a !== b) oscillants++;
			page({ largeur, hauteur, lateraux });
			const r1 = syncViewSize();
			const ecritures = ROOT.ecritures, vars = Object.assign({}, ROOT.vars);
			const ctx = `largeur=${largeur} hauteur=${hauteur} latéraux=${lateraux}`;
			assert.deepStrictEqual(syncViewSize(), r1, ctx);
			assert.deepStrictEqual(syncViewSize(), r1, ctx);
			assert.strictEqual(ROOT.ecritures, ecritures, ctx);
			assert.deepStrictEqual(ROOT.vars, vars, ctx);
			if (r1.step > 8) assert.ok(r1.viewWidth <= CENTRE.clientWidth, 'déborde : ' + ctx);
		}
	}));
	assert.ok(oscillants > 0, 'aucun cas oscillant dans le balayage : il ne prouve rien');
});

console.log('\n── Notifications du ResizeObserver / de la fenêtre ─────────────────────────');

t('un vrai redimensionnement relance le calcul, une fois, puis plus rien', () => {
	page({ largeur: 1200, hauteur: 2000 });
	assert.strictEqual(syncViewSize().step, 69);
	monde.largeur = 900;
	_surRedimensionnement();
	assert.strictEqual(syncViewSize().step, 51);
	assert.strictEqual(rendus, 1);
	const coupe = coupures;
	for (let i = 0; i < 5; i++) _surRedimensionnement();
	assert.strictEqual(rendus, 1, 'jetons replacés sans changement de pas');
	assert.strictEqual(coupures, coupe, 'animation coupée sans changement de pas');
});

t('colonne momentanément à 0 px : l’échelle en place est gardée, rien n’est écrit', () => {
	page({ hauteur: 2000 });
	const r1 = syncViewSize();
	const ecritures = ROOT.ecritures;
	monde.colonneMasquee = true;
	assert.deepStrictEqual(syncViewSize(), r1);
	assert.strictEqual(ROOT.ecritures, ecritures);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).\n`);
process.exit(echecs ? 1 : 0);

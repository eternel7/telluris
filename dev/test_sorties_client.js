// dev/test_sorties_client.js
//
// Tests des SORTIES de /play et de /embleme (play_town_telluris.html, user_home_telluris.html).
//
//   node dev/test_sorties_client.js     # sort en code 1 au premier échec
//
// POURQUOI : « ⟵ Retour » (ex-« ✕ Fermer ») referme un panneau ; 🛡 Emblème, au même bord
// du bandeau, QUITTE /play. Classes de bug :
//
//   1. Garde anti double-clic : 🛡 doit rester inerte `RETOUR_GARDE_MS` après la réapparition
//      de la vue du lieu — sinon un double-clic sur « ⟵ Retour » fait quitter la partie.
//   2. Un « ✕ Fermer » oublié sur un panneau (deux vocabulaires pour le même geste).
//   3. Le 🛡 du bandeau appelé SANS son bouton : la garde ne s'appliquerait plus ; à
//      l'inverse, le menu ⚙️ appelé AVEC : un geste délibéré bloqué pour rien.
//   4. /embleme : part-nav-css style l'ÉLÉMENT `nav` (bandeau fixe) — la liste des
//      personnages, un `<nav>` elle aussi, devenait fixe et avalait les clics de la page.
//
// HORS DE PORTÉE (sans jsdom) : le MutationObserver qui arme la garde, la navigation, la
// déconnexion réelle — vérifiés dans un vrai navigateur (CLAUDE.md §15).

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const DOSSIER = path.join(__dirname, '..', 'templates');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');
const play = lireAvecIncludes(path.join(DOSSIER, 'play_town_telluris.html'));
const jsPlay = scriptsInline(play);
const embleme = lireAvecIncludes(path.join(DOSSIER, 'user_home_telluris.html'));
assert.ok(jsPlay, 'aucun bloc <script> dans play_town_telluris.html');

function extraire(nom, source) {
	const debut = source.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable');
	let prof = 0;
	for (let j = source.indexOf('{', debut); j < source.length; j++) {
		if (source[j] === '{') prof++;
		else if (source[j] === '}' && --prof === 0) return source.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}
function extraireConst(nom, source) {
	const m = source.match(new RegExp('const ' + nom + '\\s*=\\s*([^;]+);'));
	assert.ok(m, 'constante ' + nom + ' introuvable');
	return vm.runInThisContext('(' + m[1] + ')');
}

vm.runInThisContext(extraire('_emblemePermis', jsPlay));
const GARDE = extraireConst('RETOUR_GARDE_MS', jsPlay);

let ok = 0;
function test(nom, fn) {
	try { fn(); ok++; }
	catch (e) { console.error('✗ ' + nom + '\n  ' + e.message); process.exit(1); }
}

test('la garde est une durée humaine (un double-clic, pas une attente)', () => {
	assert.ok(GARDE >= 300 && GARDE <= 1500, 'RETOUR_GARDE_MS = ' + GARDE);
});

test('🛡 inerte pendant la garde, libre à son terme (borne comprise)', () => {
	const t0 = 10_000;
	assert.strictEqual(_emblemePermis(t0, t0, GARDE), false);
	assert.strictEqual(_emblemePermis(t0, t0 + GARDE - 1, GARDE), false);
	assert.strictEqual(_emblemePermis(t0, t0 + GARDE, GARDE), true);
});

test('jamais armée (vue du lieu dès le chargement) : 🛡 libre', () => {
	assert.strictEqual(_emblemePermis(0, Date.now(), GARDE), true);
});

test('plus aucun « ✕ Fermer » sur les panneaux : tous disent « ⟵ Retour »', () => {
	const boutons = play.match(/<button[^>]*close-sheet-btn[^>]*>[\s\S]*?<\/button>/g) || [];
	assert.ok(boutons.length > 0, 'aucun bouton .close-sheet-btn trouvé');
	for (const b of boutons) {
		assert.ok(!/✕\s*Fermer/.test(b), 'reste un « ✕ Fermer » : ' + b);
		assert.ok(/⟵ Retour/.test(b), 'bouton sans « ⟵ Retour » : ' + b);
	}
});

test('fiche : « ⟵ Groupe » en mode compagnon, basculé par body.sheet-compagnon', () => {
	const fiche = play.match(/<button id="close-sheet"[\s\S]*?<\/button>/);
	assert.ok(fiche && /retour-lib-compagnon">⟵ Groupe/.test(fiche[0]), 'libellé compagnon absent');
	assert.ok(/body\.sheet-compagnon \.retour-lib-compagnon\s*\{\s*display:\s*inline/.test(play));
	// la classe que la CSS attend est bien celle que pose openCompagnonSheet
	assert.ok(/classList\.add\('sheet-compagnon'\)/.test(jsPlay), 'openCompagnonSheet ne pose plus sheet-compagnon');
});

test('🛡 du bandeau passe son bouton (garde) ; le menu ⚙️ non (geste délibéré)', () => {
	const bandeau = play.match(/<button[^>]*id="retour-embleme"[^>]*>/);
	assert.ok(bandeau, 'bouton #retour-embleme absent');
	assert.ok(/onclick="allerEmbleme\(this\)"/.test(bandeau[0]), bandeau[0]);
	const menu = play.match(/<span class="affichage-menu"[\s\S]*?<\/span>\s*<\/span>/);
	assert.ok(menu, 'menu ⚙️ introuvable');
	assert.ok(/onclick="allerEmbleme\(\)"/.test(menu[0]), 'entrée « Changer de personnage » absente du menu');
	assert.ok(/onclick="seDeconnecter\(\)"/.test(menu[0]), 'entrée « Se déconnecter » absente du menu');
});

test('les deux pages déconnectent par la même route, qui existe côté serveur', () => {
	const routeur = fs.readFileSync(path.join(__dirname, '..', 'routers', 'user.py'), 'utf8');
	assert.ok(/@user_router\.post\("\/auth\/deconnexion"\)/.test(routeur), 'route /auth/deconnexion disparue');
	for (const [nom, src] of [['play', jsPlay], ['embleme', scriptsInline(embleme)]]) {
		const f = extraire('seDeconnecter', src);
		assert.ok(/fetch\('\/api\/auth\/deconnexion',\s*\{\s*method:\s*'POST'/.test(f), nom + ' : ' + f);
	}
});

test('/embleme : bandeau du site, « ⟵ Accueil », et la liste des personnages hors du bandeau fixe', () => {
	assert.ok(/<a href="\/" class="nav-logo">/.test(embleme), 'logo du bandeau absent');
	assert.ok(/<a href="\/" class="retour-accueil"/.test(embleme), '« ⟵ Accueil » absent');
	assert.ok(/\bnav\s*\{[^}]*position:\s*fixed/.test(embleme), 'part-nav-css n\'est plus inclus');
	const reset = embleme.match(/nav\.char-list\s*\{([^}]*)\}/);
	assert.ok(reset && /position:\s*static/.test(reset[1]), 'la liste des personnages hérite du bandeau fixe');
});

console.log('OK — ' + ok + ' tests des sorties de /play et /embleme passés.');

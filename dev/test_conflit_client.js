// dev/test_conflit_client.js
//
// Tests d'EXÉCUTION de templates/scripts/conflit.js (conflit d'écriture 409 dit en douceur) :
//   • tout libellé de conflit des routeurs est reconnu, préfixé « Erreur : » ou non ;
//   • il devient UN message adouci, sans jargon ; tout autre texte est rendu intact ;
//   • /play et /combat chargent le script, et `showToast` y fait passer ses messages.
//
//   node dev/test_conflit_client.js     # sort en code 1 au premier échec
//
// MÉTHODE : le script est chargé tel quel par `vm.runInThisContext` (fonctions pures, aucun
// DOM). Les libellés serveur sont RELUS dans routers/*.py et main.py — un nouveau libellé de
// conflit que le client ne reconnaîtrait pas fait échouer le harnais.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const RACINE = path.join(__dirname, '..');
const SCRIPT = path.join(RACINE, 'templates', 'scripts', 'conflit.js');
// `const` de haut niveau d'un script : invisible sur globalThis — on l'expose pour le lire.
vm.runInThisContext(fs.readFileSync(SCRIPT, 'utf8') + '\nglobalThis.MESSAGE_CONFLIT = MESSAGE_CONFLIT;',
	{ filename: SCRIPT });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Libellés de conflit levés par le serveur : `detail="Conflit …"`.
function libellesServeur() {
	const fichiers = [path.join(RACINE, 'main.py')].concat(
		fs.readdirSync(path.join(RACINE, 'routers')).filter(f => f.endsWith('.py'))
			.map(f => path.join(RACINE, 'routers', f)));
	const vus = new Set();
	for (const f of fichiers) {
		for (const m of fs.readFileSync(f, 'utf8').matchAll(/detail="(Conflit [^"]*)"/g)) vus.add(m[1]);
	}
	return [...vus];
}

t('les routeurs lèvent bien des conflits (le harnais ne passe pas à vide)', () => {
	assert.ok(libellesServeur().length >= 1);
});

t('chaque libellé de conflit du serveur est reconnu, avec ou sans préfixe', () => {
	for (const l of libellesServeur()) {
		assert.ok(estConflit(l), l);
		assert.ok(estConflit('Erreur : ' + l), l);
	}
});

t('un conflit devient le message adouci, sans « Erreur » ni « Conflit »', () => {
	for (const l of libellesServeur()) {
		assert.strictEqual(adoucirConflit('Erreur : ' + l), MESSAGE_CONFLIT);
	}
	assert.ok(!/Erreur|Conflit/.test(MESSAGE_CONFLIT));
});

t('tout autre message est rendu intact', () => {
	for (const m of ['Erreur : Points insuffisants', 'Trop chargé pour vous déplacer — déposez un objet.', '']) {
		assert.strictEqual(estConflit(m), false);
		assert.strictEqual(adoucirConflit(m), m);
	}
	assert.strictEqual(estConflit(undefined), false);
	assert.strictEqual(estConflit(null), false);
});

t('/play et /combat chargent conflit.js, et showToast y fait passer ses messages', () => {
	for (const page of ['play_town_telluris.html', 'combat_telluris.html']) {
		const html = fs.readFileSync(path.join(RACINE, 'templates', page), 'utf8');
		assert.ok(html.includes("script_url('conflit.js')"), page);
	}
	const play = fs.readFileSync(path.join(RACINE, 'templates', 'play_town_telluris.html'), 'utf8');
	const corps = play.slice(play.indexOf('function showToast('), play.indexOf('function showToast(') + 900);
	assert.ok(corps.includes('adoucirConflit(msg)'));
});

console.log(`\n${passes} passé(s), ${echecs} échec(s)`);
process.exit(echecs ? 1 : 0);

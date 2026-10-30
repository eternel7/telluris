// dev/test_session_client.js
//
// Tests d'EXÉCUTION de templates/scripts/session.js (session expirée → /auth) :
//   • 401 ou `x-session: aucune` → navigation vers /auth, UNE fois, promesse en suspens ;
//   • toute autre réponse est rendue intacte ;
//   • une requête vers une autre origine n'est jamais interprétée.
//
//   node dev/test_session_client.js     # sort en code 1 au premier échec
//
// MÉTHODE : `window` factice (fetch + location) semé AVANT de charger le script tel quel par
// `vm.runInThisContext` — il s'installe à l'évaluation.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const SCRIPT = path.join(__dirname, '..', 'templates', 'scripts', 'session.js');

function reponse(status, entetes = {}) {
	return { status, ok: status < 400, headers: { get: k => entetes[k.toLowerCase()] ?? null } };
}

let prochaine = reponse(200);
globalThis.window = {
	location: { href: 'https://telluris.fr/play', origin: 'https://telluris.fr' },
	fetch: () => Promise.resolve(prochaine),
};
vm.runInThisContext(fs.readFileSync(SCRIPT, 'utf8'), { filename: SCRIPT });

let passes = 0, echecs = 0;
async function t(nom, fn) {
	try { await fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const EN_SUSPENS = Symbol('suspens');
const course = p => Promise.race([p, new Promise(r => setTimeout(() => r(EN_SUSPENS), 20))]);

(async () => {
	await t('réponse normale rendue intacte', async () => {
		prochaine = reponse(400);
		const r = await course(window.fetch('/api/equip'));
		assert.strictEqual(r, prochaine);
		assert.strictEqual(window.location.href, 'https://telluris.fr/play');
	});
	await t('autre origine : jamais interprétée', async () => {
		prochaine = reponse(401);
		const r = await course(window.fetch('https://ailleurs.example/api'));
		assert.strictEqual(r, prochaine);
		assert.strictEqual(window.location.href, 'https://telluris.fr/play');
	});
	await t('401 → /auth, promesse en suspens', async () => {
		prochaine = reponse(401);
		assert.strictEqual(await course(window.fetch('api/move')), EN_SUSPENS);
		assert.strictEqual(window.location.href, '/auth');
	});
	await t('x-session: aucune (code quelconque) → /auth, une seule navigation', async () => {
		window.location.href = 'https://telluris.fr/play';
		prochaine = reponse(404, { 'x-session': 'aucune' });
		assert.strictEqual(await course(window.fetch('/api/quetes')), EN_SUSPENS);
		// Déjà redirigé par le cas précédent : on ne renavigue pas.
		assert.strictEqual(window.location.href, 'https://telluris.fr/play');
	});
	await t('enveloppe posée une seule fois', async () => {
		const avant = window.fetch;
		installerSessionApi();
		assert.strictEqual(window.fetch, avant);
	});
	console.log(`\n${passes} OK, ${echecs} échec(s)`);
	process.exit(echecs ? 1 : 0);
})();

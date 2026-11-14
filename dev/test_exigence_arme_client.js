// dev/test_exigence_arme_client.js
//
// Tests d'EXÉCUTION de l'exigence d'arme côté client (combat_telluris.html) — miroir de
// `combat._profil_emprunte` (emprunt aligné sur `arme_profil`) et grisage de `compCastable`
// (`arme_ok`, décidé au serveur par utils/exigence_arme).
//
//   node dev/test_exigence_arme_client.js     # sort en code 1 au premier échec
//
// MÉTHODE : extraction par NOM depuis le template puis `vm.runInThisContext` (cf.
// dev/test_provocation_client.js) ; les voisins (`attackProfile`, `playerAttacks`, `me`,
// `coutPmCharge`, `coutPvPayable`, `canalise`, `capaCibles`) sont des bouchons en globales.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

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

vm.runInThisContext(['capaProfilEmprunte', 'compCastable'].map(extraire).join('\n'),
					{ filename: TEMPLATE });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const CAC = { mode: 'cac', portee: 1 }, ARC = { mode: 'tir', portee: 10 }, LANCER = { mode: 'jet', portee: 4 };
global.PROFILS = [CAC, LANCER, ARC];
global.playerAttacks = () => global.PROFILS;
global.attackProfile = mode => global.PROFILS.find(a => a.mode === mode) || CAC;
global.me = () => ({ currentPM: 10, currentPV: 50 });
global.coutPmCharge = c => c.cout_pm || 0;
global.coutPvPayable = () => true;
global.canalise = () => false;
global.capaCibles = () => [{ id: 'monstre_0' }];

const TIR = { competence_id: 'competence:couteaux', jet: 'cd', cible: 'ennemi', effets: { degats: '1D6' } };

t('sans exigence, un `cd` emprunte l\'arc avant l\'arme de lancer (règle d\'avant)', () => {
	assert.strictEqual(capaProfilEmprunte(TIR), ARC);
});

t('`arme_profil` aligne l\'emprunt : le couteau même arc en main', () => {
	assert.strictEqual(capaProfilEmprunte({ ...TIR, arme_profil: 'jet' }), LANCER);
	assert.strictEqual(capaProfilEmprunte({ ...TIR, jet: 'cc', arme_profil: 'cac' }), CAC);
});

t('profil désigné absent du snapshot ⇒ règle d\'avant', () => {
	global.PROFILS = [CAC, ARC];
	assert.strictEqual(capaProfilEmprunte({ ...TIR, arme_profil: 'jet' }), ARC);
	global.PROFILS = [CAC, LANCER, ARC];
});

t('une compétence magique n\'emprunte jamais, même avec `arme_profil`', () => {
	assert.strictEqual(capaProfilEmprunte({ ...TIR, jet: 'magique', arme_profil: 'tir' }), null);
});

t('`arme_ok: false` grise la case ; absent ou vrai ne change rien', () => {
	assert.strictEqual(compCastable({ ...TIR, arme_ok: false }), false);
	assert.strictEqual(compCastable({ ...TIR, arme_ok: true }), true);
	assert.strictEqual(compCastable(TIR), true);
});

console.log(`${passes} passé(s), ${echecs} échec(s)`);
if (echecs) process.exit(1);

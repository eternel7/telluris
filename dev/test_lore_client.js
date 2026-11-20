// dev/test_lore_client.js
//
// Tests d'EXÉCUTION du parcours du lore côté client : filtre de l'index (recherche + thèmes),
// statut lu / nouveau / modifié, surlignage sans accents, repli « canon d'abord »
// (templates/admin_lore.html) et réglages de lecture (templates/scripts/lore_reglages.js).
//
//   node dev/test_lore_client.js     # sort en code 1 au premier échec
//
// MÉTHODE : extraction par nom (accolades équilibrées), `runInThisContext`.
//
// HORS DE PORTÉE (à vérifier à l'écran, CLAUDE.md §15) : la recherche serveur (fetch), la
// lecture vocale, la carte, le DOM des replis et du surlignage.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_lore.html');
const REGLAGES = path.join(__dirname, '..', 'templates', 'scripts', 'lore_reglages.js');
const js = scriptsInline(lireAvecIncludes(TEMPLATE)) + '\n' + fs.readFileSync(REGLAGES, 'utf8');

function extraire(nom) {
	const debut = js.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable');
	let prof = 0;
	for (let j = js.indexOf('{', debut); j < js.length; j++) {
		if (js[j] === '{') prof++;
		else if (js[j] === '}' && --prof === 0) return js.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

const FONCTIONS = ['loreFichierRetenu', 'loreStatutLecture', 'lorePlier', 'loreOccurrences',
	'loreSectionsChatgpt', 'loreReglagesNormaliser'];
vm.runInThisContext(FONCTIONS.map(extraire).join('\n') + '\nglobalThis.F = {' + FONCTIONS.join(',') + '};');

let echecs = 0, n = 0;
function t(nom, fn) {
	n++;
	try { fn(); console.log('  ok  ' + nom); }
	catch (e) { echecs++; console.log('  ÉCHEC ' + nom + '\n       ' + (e && e.stack || e)); }
}

const fichier = { cle: 'cites/rome.md', texte: 'décrire rome dans telluris', themes: ['cite', 'institution'] };
const etat = (o) => Object.assign({ mots: [], serveur: null, themes: new Set() }, o);

t('filtre : sans critère, tout est retenu', () => {
	assert.strictEqual(F.loreFichierRetenu(fichier, etat()), true);
});

t('filtre : titre local OU trouvé par la recherche plein texte', () => {
	assert.strictEqual(F.loreFichierRetenu(fichier, etat({ mots: ['rome'] })), true);
	assert.strictEqual(F.loreFichierRetenu(fichier, etat({ mots: ['pape'] })), false);  // avant la réponse
	assert.strictEqual(F.loreFichierRetenu(fichier, etat({ mots: ['pape'], serveur: new Set(['cites/rome.md']) })), true);
	assert.strictEqual(F.loreFichierRetenu(fichier, etat({ mots: ['pape'], serveur: new Set(['autre.md']) })), false);
});

t('filtre : un thème coché suffit (union), combiné à la recherche', () => {
	assert.strictEqual(F.loreFichierRetenu(fichier, etat({ themes: new Set(['creature', 'cite']) })), true);
	assert.strictEqual(F.loreFichierRetenu(fichier, etat({ themes: new Set(['creature']) })), false);
	assert.strictEqual(F.loreFichierRetenu(fichier, etat({ themes: new Set(['cite']), mots: ['venise'] })), false);
});

t('statut : lu, modifié depuis la lecture, nouveau depuis la visite précédente, non lu', () => {
	assert.strictEqual(F.loreStatutLecture(100, 200, 50), 'lu');
	assert.strictEqual(F.loreStatutLecture(300, 200, 50), 'modifie');
	assert.strictEqual(F.loreStatutLecture(300, undefined, 250), 'nouveau');
	assert.strictEqual(F.loreStatutLecture(100, undefined, 250), 'non_lu');
	assert.strictEqual(F.loreStatutLecture(100, undefined, 0), 'non_lu');  // première visite : rien de « nouveau »
});

t('plier : sans accents ni casse, même longueur', () => {
	for (const s of ['Élise à Lutèce', 'Hārūt et Mārūt', 'Œuvre']) assert.strictEqual(F.lorePlier(s).length, s.length);
	assert.strictEqual(F.lorePlier('Élise à Lutèce'), 'elise a lutece');
});

t('occurrences : sans accents, triées, sans chevauchement', () => {
	assert.deepStrictEqual(F.loreOccurrences('Élise et elise, puis ÉLISE', ['elise']), [[0, 5], [9, 14], [21, 26]]);
	assert.deepStrictEqual(F.loreOccurrences('portail naturel', ['portail', 'tail']), [[0, 7]]);
	assert.deepStrictEqual(F.loreOccurrences('rien', ['x', '']), []);
});

t('canon d\'abord : ce qui suit un h2 🤖, jusqu\'au h2 suivant', () => {
	const b = (h2, chatgpt) => ({ h2, chatgpt: !!chatgpt });
	// h1, h2 auteur, p, h2 🤖, p, p, hr, h2 auteur, p, h2 🤖, p
	const blocs = [b(false), b(true), b(false), b(true, 1), b(false), b(false), b(false), b(true), b(false), b(true, 1), b(false)];
	assert.deepStrictEqual(F.loreSectionsChatgpt(blocs), [[4, 7], [10, 11]]);
	assert.deepStrictEqual(F.loreSectionsChatgpt([b(true, 1), b(true)]), []);  // h2 🤖 vide
	assert.deepStrictEqual(F.loreSectionsChatgpt([b(false), b(false)]), []);
});

t('réglages : valeurs bornées, inconnues ramenées au défaut', () => {
	assert.deepStrictEqual(F.loreReglagesNormaliser(null), { theme: 'sombre', taille: 1, police: 'defaut' });
	assert.deepStrictEqual(F.loreReglagesNormaliser({ theme: 'parchemin', taille: 1.27, police: 'dyslexie' }),
		{ theme: 'parchemin', taille: 1.3, police: 'dyslexie' });
	assert.strictEqual(F.loreReglagesNormaliser({ taille: 9 }).taille, 1.6);
	assert.strictEqual(F.loreReglagesNormaliser({ taille: 0.1 }).taille, 0.8);
	assert.strictEqual(F.loreReglagesNormaliser({ theme: 'rose', police: 'comic' }).theme, 'sombre');
});

console.log(`\n${n - echecs} / ${n} tests passés`);
process.exit(echecs ? 1 : 0);

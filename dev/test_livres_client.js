// dev/test_livres_client.js
//
// Tests d'EXÉCUTION des livres de /play (templates/scripts/lecture.js) : ce que lit le bouton
// ▶ Lire, et le rendu des planches et illustrations.
//
//   node dev/test_livres_client.js     # sort en code 1 au premier échec
//
// POURQUOI : un livre scellé (sort, recette, carte de scriptorium) ne doit ni se lire ni se
// montrer en vitrine ; une URL d'image vient du serveur et ne doit jamais casser l'attribut.
//
// HORS DE PORTÉE (à vérifier à l'écran, CLAUDE.md §15) : `speechSynthesis`, le basculement
// ▶ Lire / ■ Arrêter, l'arrêt à la fermeture de la fiche.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'templates', 'scripts', 'lecture.js'), 'utf8');
vm.runInThisContext(SRC + '\nglobalThis.F = { lectureNettoyer, lectureDecouper, livreTextesALire, livreImagesHtml };');

let echecs = 0, n = 0;
function test(nom, fn) {
	n++;
	try { fn(); } catch (e) { echecs++; console.error('✗ ' + nom + '\n  ' + e.message); }
}

const livre = { categorie: 'livre', nom: '« Critias » — Platon', description: 'Écoute donc, Socrate. Une histoire étrange 📜.' };

test('un livre se lit : titre puis texte, pictogrammes retirés', () => {
	const t = F.livreTextesALire(livre);
	assert.strictEqual(t[0], '« Critias » — Platon');
	assert.ok(t.slice(1).join(' ').includes('Socrate'));
	assert.ok(!t.join(' ').includes('📜'));
});

test('un livre scellé, sans texte, ou un autre objet ne se lit pas', () => {
	assert.deepStrictEqual(F.livreTextesALire({ ...livre, contenu_scelle: true }), []);
	assert.deepStrictEqual(F.livreTextesALire({ ...livre, description: '' }), []);
	assert.deepStrictEqual(F.livreTextesALire({ ...livre, categorie: 'arme' }), []);
	assert.deepStrictEqual(F.livreTextesALire(null), []);
});

test('un texte long est découpé en énoncés bornés', () => {
	const long = Array(40).fill('Une phrase assez longue pour remplir la ligne.').join(' ');
	const t = F.livreTextesALire({ ...livre, description: long });
	assert.ok(t.length > 2);
	assert.ok(t.slice(1).every(s => s.length <= 200));
});

test('les images se rendent, une par lien', () => {
	const html = F.livreImagesHtml({ images: [{ url: '/livres/a.jpg' }, { url: '/livres/ouvrage_x/01.jpg' }] });
	assert.strictEqual((html.match(/<img /g) || []).length, 2);
	assert.ok(html.includes('src="/livres/ouvrage_x/01.jpg"'));
});

test('une URL ne casse jamais l\'attribut', () => {
	const html = F.livreImagesHtml({ images: [{ url: '/livres/a".jpg' }] });
	assert.ok(!html.includes('a".jpg'));
	assert.ok(html.includes('a&quot;.jpg'));
});

test('pas d\'image : scellé, liste vide ou absente', () => {
	assert.strictEqual(F.livreImagesHtml({ images: [{ url: '/livres/a.jpg' }], contenu_scelle: true }), '');
	assert.strictEqual(F.livreImagesHtml({ images: [] }), '');
	assert.strictEqual(F.livreImagesHtml({}), '');
});

console.log(echecs ? `${echecs}/${n} échec(s)` : `OK — ${n} tests`);
process.exit(echecs ? 1 : 0);

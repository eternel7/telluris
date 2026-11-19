// dev/test_enigmes_client.js
//
// Tests d'EXÉCUTION de templates/scripts/enigmes.js (panneau d'énigme de /play) :
//   • chaque famille du moteur (RELUE dans utils/enigmes.py) a son rendu, avec ses commandes ;
//   • tout texte de donnée est échappé (labels, journal, voix) ;
//   • une énigme résolue n'affiche que sa réussite ; scène illustrée seulement avec une image ;
//   • le brouillon local est une COPIE de l'état serveur (le manipuler ne le corrompt pas) ;
//   • /play charge le script et ouvre le panneau sur le hook `enigme` d'un choix de dialogue.
//
//   node dev/test_enigmes_client.js     # sort en code 1 au premier échec
//
// MÉTHODE : le script est chargé tel quel par `vm.runInThisContext` ; seules ses fonctions de
// rendu PURES sont appelées (aucun DOM).

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const RACINE = path.join(__dirname, '..');
const SCRIPT = path.join(RACINE, 'templates', 'scripts', 'enigmes.js');
vm.runInThisContext(fs.readFileSync(SCRIPT, 'utf8'), { filename: SCRIPT });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const PIEGE = '<img src=x onerror=alert(1)>';
const VUES = {
	deduction: { famille: 'deduction', etat: { examines: ['porte'] },
		elements: { indices: [{ id: 'porte', label: 'La porte' }, { id: 'sol', label: PIEGE }],
			conclusions: [{ id: 'ailleurs', label: 'Partie ailleurs' }] } },
	crans: { famille: 'crans', etat: { positions: { a: 2 } },
		elements: { pieces: [{ id: 'a', label: 'Tiroir A', crans: 4 }] } },
	graphe: { famille: 'graphe', etat: { position: 's1', arches_ici: ['spirale'] },
		elements: { depart: 'entree', salles: [{ id: 'entree', label: "l'entrée" }, { id: 's1', label: 'la cave' }],
			arches: [{ id: 'spirale', label: 'Spirale', symbole: '🌀' }] } },
	association: { famille: 'association', etat: { paires: { porte: 'dest' } },
		elements: { gauche: [{ id: 'porte', texte: 'La porte' }, { id: 'chemin', texte: 'Le chemin' }],
			droite: [{ id: 'dest', texte: 'inaccessible' }, { id: 'proj', texte: 'projection' }] } },
	placement: { famille: 'placement', etat: { placement: { p1: 'soleil' } },
		elements: { symboles: [{ id: 'soleil', label: 'Soleil', icone: '☀' }], emplacements: [{ id: 'p1', label: 'Pièce 1' }] } },
	reseau: { famille: 'reseau', etat: { actives: ['l1'], ancrees: ['l1'] },
		elements: { noeuds: [{ id: 'cour', label: 'Cour' }, { id: 'galerie', label: 'Galerie' }],
			liaisons: [{ id: 'l1', a: 'cour', b: 'galerie' }] } },
};

t('chaque famille du moteur a une vue de test et un rendu non vide', () => {
	const py = fs.readFileSync(path.join(RACINE, 'utils', 'enigmes.py'), 'utf8');
	const familles = [...py.match(/^FAMILLES = \(([^)]*)\)/m)[1].matchAll(/"(\w+)"/g)].map(m => m[1]);
	assert.ok(familles.length >= 6, 'FAMILLES relue');
	for (const f of familles) {
		assert.ok(VUES[f], 'vue de test pour ' + f);
		const v = VUES[f];
		assert.ok(enigmeCorps(v, enigmeBrouillonInitial(v), 'cle', {}).length > 0, f);
	}
});

t('déduction : indices examinés marqués, conclusions proposées', () => {
	const h = enigmeCorps(VUES.deduction, {});
	assert.ok(h.includes('data-eni-cle="porte"') && h.includes('✓ La porte'));
	assert.ok(h.includes('data-eni-conclure="ailleurs"'));
});

t('crans : position affichée depuis le brouillon, boutons ±', () => {
	const h = enigmeCorps(VUES.crans, enigmeBrouillonInitial(VUES.crans));
	assert.ok(h.includes('3 / 4') && h.includes('data-eni-pas="-1"') && h.includes('data-eni-essayer'));
});

t('graphe : salle courante, arches d\'ici, retour à l\'entrée hors départ', () => {
	const h = enigmeCorps(VUES.graphe, {});
	assert.ok(h.includes('la cave') && h.includes('data-eni-cle="spirale"') && h.includes('data-eni-recommencer'));
	const auDepart = Object.assign({}, VUES.graphe, { etat: { position: 'entree', arches_ici: [] } });
	assert.ok(!enigmeCorps(auDepart, {}).includes('data-eni-recommencer'));
});

t('association : paires trouvées désactivées, sélection marquée', () => {
	const h = enigmeCorps(VUES.association, {}, null, { gauche: 'chemin' });
	assert.ok(/data-eni-id="porte"[^>]*disabled/.test(h));
	assert.ok(/eni-choisi"[^>]*data-eni-id="chemin"/.test(h) || /eni-choisi" data-eni-assoc="gauche" data-eni-id="chemin"/.test(h));
});

t('placement : symbole posé présélectionné', () => {
	const h = enigmeCorps(VUES.placement, enigmeBrouillonInitial(VUES.placement));
	assert.ok(h.includes('value="soleil" selected'));
});

t('réseau : liaison ouverte et ancrée, outils, carte SVG', () => {
	const h = enigmeCorps(VUES.reseau, enigmeBrouillonInitial(VUES.reseau), 'pierre');
	assert.ok(h.includes('eni-lien eni-ouvert eni-ancre') && h.includes('<svg') && h.includes('data-eni-outil="miroir"'));
	assert.ok(h.includes('eni-choisi" data-eni-outil="pierre"'));
});

t('tout texte de donnée est échappé', () => {
	assert.ok(!enigmeCorps(VUES.deduction, {}).includes('<img'));
	assert.ok(!enigmeJournal({ journal: [PIEGE] }).includes('<img'));
	assert.ok(!enigmeVoix([{ qui: PIEGE, texte: PIEGE }]).includes('<img'));
	assert.ok(!enigmeCorps({ resolue: true, reussite: PIEGE }, {}).includes('<img'));
});

t('énigme résolue : seulement la réussite', () => {
	const h = enigmeCorps(Object.assign({}, VUES.crans, { resolue: true, reussite: 'Ouvert.' }), {});
	assert.ok(h.includes('Ouvert.') && !h.includes('data-eni-essayer'));
});

t('scène illustrée : rien sans image, zones en % avec image', () => {
	assert.strictEqual(enigmeScene({ famille: 'crans' }), '');
	const h = enigmeScene({ image: 'meuble.jpg', zones: [{ cle: 'a', x: 10, y: 20, w: 30, h: 15 }] });
	assert.ok(h.includes('/enigmes/meuble.jpg') && h.includes('data-eni-zone="a"'));
	assert.ok(h.includes('left:10%;top:20%;width:30%;height:15%'));
	// Une image absente se retire : le panneau retombe sur ses commandes.
	assert.ok(h.includes('onerror="this.parentNode.remove()"'));
});

t('le brouillon est une copie de l\'état serveur', () => {
	const v = JSON.parse(JSON.stringify(VUES.reseau));
	const b = enigmeBrouillonInitial(v);
	b.actives.push('l9');
	assert.deepStrictEqual(v.etat.actives, ['l1']);
});

t('/play charge le script et ouvre le panneau sur le hook `enigme`', () => {
	const play = fs.readFileSync(path.join(RACINE, 'templates', 'play_town_telluris.html'), 'utf8');
	assert.ok(play.includes("script_url('enigmes.js')"));
	assert.ok(/if \(data\.enigme\) ouvrirEnigme\(data\.enigme\)/.test(play));
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);

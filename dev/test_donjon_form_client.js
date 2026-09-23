// dev/test_donjon_form_client.js
//
// Tests d'EXÉCUTION de la section 🏰 Donjon du formulaire de lieu
// (templates/part-lieux-js.html, inclus par admin_map_editor.html).
//
//   node dev/test_donjon_form_client.js     # sort en code 1 au premier échec
//
// POURQUOI : enregistrer une salle écrit, par PUT COMPLET, le lieu ET un ou deux docs
// `donjon:*` — celui qui reçoit la salle, et celui qu'elle quitte. Une fusion naïve
// effacerait la salle d'à côté, ses espèces ou ses bornes de grade, sans une erreur ; une
// porte gardée personnalisée (`ou`, `rang_min`…) réécrite en forme simple ouvrirait ou
// fermerait un donjon pour de bon. Et « ouvrir puis enregistrer » ne doit RIEN changer.
//
// MÉTHODE : celle de dev/test_lieu_form_client.js — extraction par nom, `runInThisContext`.
// HORS DE PORTÉE (à vérifier en jeu) : le rendu de la section, la relecture des donjons avant
// écriture, l'ouverture du formulaire de connexion par « ➕ Passage ».

const assert = require('assert');
const path = require('path');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_map_editor.html');
const tpl = require('./_template_js');
const js = tpl.scriptsInline(tpl.lireAvecIncludes(TEMPLATE));

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

// `_slugLieu` lit cette constante de module (plage de diacritiques).
vm.runInThisContext("const _DIACRITIQUES = new RegExp('[\\\\u0300-\\\\u036f]', 'g');");
for (const f of ['_slugLieu', '_donjonDeSalle', '_idDonjon', '_djPoserBornes', '_fusionDonjon',
				 '_fusionSalle', '_retirerSalle', '_accesClauseDonjon', '_djCanon', '_accesEstSimple',
				 '_accesSimple', '_djTags', '_djAppliquerAuLieu', '_donjonsAEcrire', '_djPassages',
				 '_djSortieExiste', '_djPassageSuggere']) {
	vm.runInThisContext(extraire(f));
}

let ok = 0, ko = 0;
function t(nom, fn) {
	try { fn(); ok++; console.log('  OK   ' + nom); }
	catch (e) { ko++; console.log('  ÉCHEC ' + nom + '\n       ' + e.message); }
}
const clone = o => JSON.parse(JSON.stringify(o));

// Les deux donjons de la base (dump du 23/09), `_rev` compris : c'est ce que le formulaire relit.
const MINE = {
	_id: 'donjon:mine_de_saint_austrelin', _rev: '3-a', type: 'donjon',
	nom: 'Le donjon-mine de Saint-Austrelin', description: 'Sous le Temple-Portail…',
	portail: 'lieu:temple_portail_de_saint_austrelin_interieur', niveau_max: 2,
	battle_maps: [{ lieu: 'lieu:la_mine_aux_cristaux',
		especes: ['espece:gobelin', 'espece:rat_geant', 'espece:araignee_geante'] }],
};
const GROTTE = {
	_id: 'donjon:les_loups_de_la_grotte_humide', _rev: '5-b', type: 'donjon',
	nom: 'La meute du seuil', description: 'Trois loups géants…',
	portail: 'lieu:grotte_dans_foret_humide',
	battle_maps: [{ lieu: 'lieu:grotte_en_foret', especes: ['espece:loup_geant'],
		niveau_max: 3, nb_monstres: 3, niveau_min: 2 }],
	niveau_max: 2,
};
const DONJONS = [GROTTE, MINE];
const ACCES_MINE = {
	gardien: 'pnj:templier_armand_de_vaucremont_01', refus: 'Armand barre l’accès.', cycle: 1,
	conditions: [{ quete_active: { lieu: 'lieu:la_mine_aux_cristaux', types: ['chasse'],
		giver_categorie: 'bureau_maitre_guilde', objectif_atteint: false } }],
};

// L'état que la section produit à l'ouverture d'une salle, sans rien toucher (cf. `_djOuvrir`).
function etatOuvert(donjon, lieuId) {
	const e = donjon.battle_maps.find(x => x.lieu === lieuId) || {};
	const n = v => (v === undefined ? null : v);
	return {
		salle: true, donjonId: donjon._id, nouveau: false, nouvelId: '',
		donjon: { nom: donjon.nom, description: donjon.description || '', portail: donjon.portail || '',
			etages: donjon.mode === 'etages', niveau_min: n(donjon.niveau_min),
			niveau_max: n(donjon.niveau_max), nb_monstres: n(donjon.nb_monstres) },
		piece: { especes: (e.especes || []).slice(), niveau_min: n(e.niveau_min),
			niveau_max: n(e.niveau_max), nb_monstres: n(e.nb_monstres) },
	};
}

console.log('\n── Appartenance et identité ──');

t('la salle appartient au PREMIER donjon qui la revendique (miroir de donjon_de_lieu)', () => {
	const doublon = clone(MINE);
	doublon._id = 'donjon:doublon';
	assert.strictEqual(_donjonDeSalle([MINE, doublon], 'lieu:la_mine_aux_cristaux')._id, MINE._id);
	assert.strictEqual(_donjonDeSalle(DONJONS, 'lieu:auxerre'), null);
	assert.strictEqual(_donjonDeSalle(DONJONS, ''), null);
});

t('l’_id d’un donjon neuf est le slug de son nom', () => {
	assert.strictEqual(_idDonjon('Les Catacombes de Lutèce'), 'donjon:les_catacombes_de_lutece');
	assert.strictEqual(_idDonjon('  '), '');
});

console.log('\n── « Ouvrir puis enregistrer » ne change rien ──');

for (const [donjon, lieu] of [[MINE, 'lieu:la_mine_aux_cristaux'], [GROTTE, 'lieu:grotte_en_foret']]) {
	t(`${donjon._id} : aucun doc donjon à écrire`, () => {
		const r = _donjonsAEcrire(clone(DONJONS), lieu, etatOuvert(donjon, lieu));
		assert.strictEqual(r.erreur, '');
		assert.deepStrictEqual(r.docs, []);
	});
}

t('une borne égale mais écrite en texte n’est pas retypée', () => {
	const d = clone(GROTTE);
	d.niveau_max = '2';
	const out = _fusionDonjon(d, Object.assign(etatOuvert(GROTTE, 'lieu:grotte_en_foret').donjon));
	assert.strictEqual(out.niveau_max, '2');
});

console.log('\n── Fusion du doc donjon ──');

t('seuls les champs du formulaire bougent ; salles et clés inconnues traversent', () => {
	const d = clone(MINE);
	d.cle_future = { a: 1 };
	const out = _fusionDonjon(d, { nom: 'Mine', description: '', portail: '', etages: true,
		niveau_min: 1, niveau_max: null, nb_monstres: 4 });
	assert.strictEqual(out.nom, 'Mine');
	assert.ok(!('description' in out), 'description vide ⇒ absente');
	assert.ok(!('portail' in out), 'portail vide ⇒ absent');
	assert.strictEqual(out.mode, 'etages');
	assert.strictEqual(out.niveau_min, 1);
	assert.ok(!('niveau_max' in out), 'borne vide ⇒ héritée (absente)');
	assert.strictEqual(out.nb_monstres, 4);
	assert.deepStrictEqual(out.battle_maps, MINE.battle_maps);
	assert.deepStrictEqual(out.cle_future, { a: 1 });
	assert.strictEqual(out._rev, MINE._rev);
});

t('repasser en classique RETIRE `mode`', () => {
	const out = _fusionDonjon(Object.assign(clone(MINE), { mode: 'etages' }),
		Object.assign(etatOuvert(MINE, 'lieu:la_mine_aux_cristaux').donjon, { etages: false }));
	assert.ok(!('mode' in out));
});

t('la salle est fusionnée à SA place, ses clés inconnues gardées ; une salle neuve va en fin', () => {
	const d = clone(GROTTE);
	d.battle_maps.push({ lieu: 'lieu:autre', especes: ['espece:x'] });
	d.battle_maps[0].note = 'garder';
	const out = _fusionSalle(d, 'lieu:grotte_en_foret', { especes: ['espece:loup_geant', 'espece:ours'],
		niveau_min: null, niveau_max: 3, nb_monstres: 3 });
	assert.strictEqual(out.battle_maps[0].lieu, 'lieu:grotte_en_foret');
	assert.deepStrictEqual(out.battle_maps[0].especes, ['espece:loup_geant', 'espece:ours']);
	assert.ok(!('niveau_min' in out.battle_maps[0]));
	assert.strictEqual(out.battle_maps[0].note, 'garder');
	assert.deepStrictEqual(out.battle_maps[1], { lieu: 'lieu:autre', especes: ['espece:x'] });
	const neuf = _fusionSalle(d, 'lieu:etage2', { especes: ['espece:rat_geant'] });
	assert.deepStrictEqual(neuf.battle_maps[neuf.battle_maps.length - 1], { lieu: 'lieu:etage2', especes: ['espece:rat_geant'] });
});

console.log('\n── Docs à écrire ──');

t('changer de donjon : le nouveau reçoit la salle PUIS l’ancien la perd', () => {
	const etat = etatOuvert(MINE, 'lieu:la_mine_aux_cristaux');
	etat.donjonId = GROTTE._id;
	Object.assign(etat.donjon, etatOuvert(GROTTE, 'lieu:grotte_en_foret').donjon);
	const r = _donjonsAEcrire(clone(DONJONS), 'lieu:la_mine_aux_cristaux', etat);
	assert.deepStrictEqual(r.docs.map(d => d._id), [GROTTE._id, MINE._id]);
	assert.deepStrictEqual(r.docs[0].battle_maps.map(e => e.lieu), ['lieu:grotte_en_foret', 'lieu:la_mine_aux_cristaux']);
	assert.deepStrictEqual(r.docs[1].battle_maps, []);
});

t('salle décochée : l’ancien donjon la perd, rien d’autre', () => {
	const r = _donjonsAEcrire(clone(DONJONS), 'lieu:grotte_en_foret', { salle: false });
	assert.strictEqual(r.docs.length, 1);
	assert.strictEqual(r.docs[0]._id, GROTTE._id);
	assert.deepStrictEqual(r.docs[0].battle_maps, []);
	assert.strictEqual(r.docs[0].nom, GROTTE.nom);
	assert.deepStrictEqual(_donjonsAEcrire(clone(DONJONS), 'lieu:libre', { salle: false }).docs, []);
});

t('donjon neuf : créé avec la salle ; `_id` déjà pris ⇒ refus', () => {
	const etat = { salle: true, donjonId: '', nouveau: true, nouvelId: 'donjon:catacombes',
		donjon: { nom: 'Catacombes', description: '', portail: 'lieu:lutece', etages: true,
			niveau_min: null, niveau_max: 3, nb_monstres: null },
		piece: { especes: ['espece:squelette'], niveau_min: null, niveau_max: null, nb_monstres: null } };
	const r = _donjonsAEcrire(clone(DONJONS), 'lieu:catacombes_1', etat);
	assert.strictEqual(r.erreur, '');
	assert.deepStrictEqual(r.docs, [{ _id: 'donjon:catacombes', type: 'donjon', nom: 'Catacombes',
		portail: 'lieu:lutece', mode: 'etages', niveau_max: 3,
		battle_maps: [{ lieu: 'lieu:catacombes_1', especes: ['espece:squelette'] }] }]);
	etat.nouvelId = MINE._id;
	const pris = _donjonsAEcrire(clone(DONJONS), 'lieu:catacombes_1', etat);
	assert.deepStrictEqual(pris.docs, []);
	assert.ok(/existe déjà/.test(pris.erreur));
});

t('donjon introuvable (supprimé depuis l’ouverture) ⇒ refus, rien d’écrit', () => {
	const etat = etatOuvert(MINE, 'lieu:la_mine_aux_cristaux');
	const r = _donjonsAEcrire([GROTTE], 'lieu:la_mine_aux_cristaux', etat);
	assert.deepStrictEqual(r.docs, []);
	assert.ok(/introuvable/.test(r.erreur));
});

console.log('\n── Porte gardée ──');

t('la porte de la mine est reconnue comme SIMPLE, quel que soit l’ordre des clés', () => {
	assert.ok(_accesEstSimple(ACCES_MINE, 'lieu:la_mine_aux_cristaux'));
	const permute = clone(ACCES_MINE);
	permute.conditions = [{ quete_active: { objectif_atteint: false, giver_categorie: 'bureau_maitre_guilde',
		types: ['chasse'], lieu: 'lieu:la_mine_aux_cristaux' } }];
	assert.ok(_accesEstSimple(permute, 'lieu:la_mine_aux_cristaux'));
	assert.ok(_accesEstSimple(undefined, 'lieu:x'), 'pas de bloc ⇒ le formulaire peut en poser un');
});

t('un bloc personnalisé n’est pas simple (autre salle, `ou`, deux clauses)', () => {
	assert.ok(!_accesEstSimple(ACCES_MINE, 'lieu:autre_salle'));
	const ou = clone(ACCES_MINE);
	ou.conditions = [{ ou: [ACCES_MINE.conditions[0], { rang_min: { rang: 'C' } }] }];
	assert.ok(!_accesEstSimple(ou, 'lieu:la_mine_aux_cristaux'));
	const deux = clone(ACCES_MINE);
	deux.conditions.push({ item: 'item:cle' });
	assert.ok(!_accesEstSimple(deux, 'lieu:la_mine_aux_cristaux'));
});

t('le bloc simple regénéré sur celui de la mine est IDENTIQUE', () => {
	const a = _accesSimple(clone(ACCES_MINE), 'lieu:la_mine_aux_cristaux', ACCES_MINE.gardien, ACCES_MINE.refus);
	assert.strictEqual(JSON.stringify(a), JSON.stringify(ACCES_MINE));
});

t('bloc simple neuf : cycle 1 ; refus vide ⇒ absent ; clés inconnues gardées', () => {
	assert.deepStrictEqual(_accesSimple(undefined, 'lieu:s', 'pnj:g', ''),
		{ gardien: 'pnj:g', cycle: 1, conditions: [_accesClauseDonjon('lieu:s')] });
	const a = _accesSimple({ cycle: 3, note: 'x', refus: 'non' }, 'lieu:s', 'pnj:g', '');
	assert.strictEqual(a.cycle, 3);
	assert.strictEqual(a.note, 'x');
	assert.ok(!('refus' in a));
});

console.log('\n── Le doc lieu ──');

const SALLE = { _id: 'lieu:la_mine_aux_cristaux', categorie: 'battle_map', tags: ['mine', 'cristaux', 'donjon'],
	acces: clone(ACCES_MINE) };

t('section inactive ou salle décochée : le lieu ne bouge pas', () => {
	assert.deepStrictEqual(_djAppliquerAuLieu(clone(SALLE), null), SALLE);
	assert.deepStrictEqual(_djAppliquerAuLieu(clone(SALLE), { salle: false, reservee: false, garde: false }), SALLE);
});

t('rouvrir la mine sans rien toucher : lieu identique', () => {
	const dj = { salle: true, reservee: true, garde: true, gardien: ACCES_MINE.gardien, refus: ACCES_MINE.refus };
	assert.strictEqual(JSON.stringify(_djAppliquerAuLieu(clone(SALLE), dj)), JSON.stringify(SALLE));
});

t('le tag `donjon` suit la case « réservée », les autres tags restent', () => {
	const sans = _djAppliquerAuLieu(clone(SALLE), { salle: true, reservee: false, garde: true,
		gardien: ACCES_MINE.gardien, refus: ACCES_MINE.refus });
	assert.deepStrictEqual(sans.tags, ['mine', 'cristaux']);
	const seul = _djAppliquerAuLieu({ _id: 'lieu:s', tags: ['donjon'] }, { salle: true, reservee: false, garde: false });
	assert.ok(!('tags' in seul), 'liste vide ⇒ clé retirée');
	assert.deepStrictEqual(_djTags(undefined, true), ['donjon']);
});

t('« gardée » décochée retire un bloc SIMPLE, jamais un bloc personnalisé', () => {
	const libre = _djAppliquerAuLieu(clone(SALLE), { salle: true, reservee: true, garde: false });
	assert.ok(!('acces' in libre));
	const perso = clone(SALLE);
	perso.acces.conditions.push({ rang_min: { rang: 'C' } });
	const garde = _djAppliquerAuLieu(clone(perso), { salle: true, reservee: true, garde: false });
	assert.deepStrictEqual(garde.acces, perso.acces);
	const regarde = _djAppliquerAuLieu(clone(perso), { salle: true, reservee: true, garde: true, gardien: 'pnj:autre', refus: '' });
	assert.deepStrictEqual(regarde.acces, perso.acces);
});

console.log('\n── Passages d’un donjon à étages ──');

const ETAGES = { _id: 'donjon:cata', battle_maps: [{ lieu: 'lieu:e1' }, { lieu: 'lieu:e2' }], portail: 'lieu:parvis' };
const CONNS = [
	{ _id: 'link:e1_to_parvis', nodes: [{ lieu: 'lieu:parvis', pos: [0, 0] }, { lieu: 'lieu:e1', pos: [3, 4] }] },
	{ _id: 'link:e2_to_e1', nodes: [{ lieu: 'lieu:e1', pos: [10, 2] }, { lieu: 'lieu:e2', pos: [1, 1] }] },
	{ _id: 'link:ailleurs', nodes: [{ lieu: 'lieu:a', pos: [0, 0] }, { lieu: 'lieu:b', pos: [0, 0] }] },
];

t('passages vus depuis un étage : surface = hors des salles du donjon', () => {
	assert.deepStrictEqual(_djPassages(CONNS, 'lieu:e1', ETAGES), [
		{ id: 'link:e1_to_parvis', pos: [3, 4], vers: 'lieu:parvis', versPos: [0, 0], surface: true },
		{ id: 'link:e2_to_e1', pos: [10, 2], vers: 'lieu:e2', versPos: [1, 1], surface: false },
	]);
	assert.deepStrictEqual(_djPassages(CONNS, 'lieu:e2', ETAGES).map(p => p.surface), [false]);
});

t('sortie du donjon : une connexion salle ↔ hors-salle, n’importe où', () => {
	assert.ok(_djSortieExiste(CONNS, ETAGES));
	assert.ok(!_djSortieExiste(CONNS.slice(1), ETAGES));
});

t('passage proposé : l’étage pas encore relié, puis le portail', () => {
	assert.strictEqual(_djPassageSuggere([], 'lieu:e1', ETAGES), 'lieu:e2');
	assert.strictEqual(_djPassageSuggere(_djPassages(CONNS, 'lieu:e1', ETAGES), 'lieu:e1', ETAGES), 'lieu:parvis');
	assert.strictEqual(_djPassageSuggere([], 'lieu:e1', { battle_maps: [{ lieu: 'lieu:e1' }] }), '');
});

console.log(`\n${ok} test(s) OK, ${ko} échec(s).`);
process.exit(ko ? 1 : 0);

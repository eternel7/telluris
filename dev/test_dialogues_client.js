// dev/test_dialogues_client.js
//
// Tests d'EXÉCUTION du JavaScript de l'ÉDITEUR DE DIALOGUES & D'OFFRES DE QUÊTE
// (templates/admin_dialogues.html, écran /admin/dialogues).
//
//   node dev/test_dialogues_client.js     # sort en code 1 au premier échec
//
// POURQUOI : une classe de bug SILENCIEUSE, qu'aucun test pytest ne peut atteindre (la
// logique vit dans un template).
//   Le JSON produit par cet écran part vers `/admin/import-bulk`, qui fait un PUT COMPLET,
//   JAMAIS un merge (CLAUDE.md §11). Or le formulaire ne possède PAS tout le document :
//   ni `description`, ni `services.escorte.recherche`, ni `recompenses.items` / son
//   `rang_guilde`, ni `soin.gratuit_si` — et pas davantage les clés qu'un nœud ou un choix
//   porteront demain. Toute clé absente du JSON DISPARAÎT de la base sans une erreur.
//   D'où `_dlgFusionDoc` / `_dlgFusionNoeud` / `_dlgFusionChoix`, et d'où ce fichier.
//
//   Second enjeu : l'ATTEIGNABILITÉ. `_dlgEntrees` doit compter les nœuds de service — le
//   router y saute directement, aucun `next` n'y mène. Les oublier ferait signaler chaque
//   nœud de service comme « texte mort », un faux positif sur du contenu correct.
//
// MÉTHODE : identique à dev/test_connexions_client.js — extraction par nom (accolades
// équilibrées) et exécution dans le realm du test (`runInThisContext`), pour que
// `deepStrictEqual` accepte les tableaux produits.
//
// ⚠️ Les fonctions extraites lisent la globale `VOCAB` (le vocabulaire servi par
// `main._vocabulaire_dialogues`). On la sème sur `globalThis` avant de les évaluer — même
// procédé que `test_resize_client.js` pour `_reappliquerPortes`.
//
// HORS DE PORTÉE (à vérifier en jeu, cf. CLAUDE.md §15) : le rendu SVG, l'ouverture de
// l'overlay et sa cohabitation avec le graphe, l'échange avec /admin/lint-dialogues.
//
// ⚠️ L'extraction se fait par NOM : renommer une fonction ici visée fait échouer le test
// avec « fonction introuvable » — c'est voulu, pas un faux positif.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_dialogues.html');
const src = fs.readFileSync(TEMPLATE, 'utf8');

const js = [...src.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
	.map(m => m[1]).join('\n');
assert.ok(js, 'aucun bloc <script> trouvé dans ' + TEMPLATE);

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

// Le strict nécessaire de ce que sert `_vocabulaire_dialogues` : les fonctions pures ne
// lisent que `fin` et `conditions_structurees`.
globalThis.VOCAB = {
	fin: 'fin',
	conditions_structurees: ['relation_min', 'intro_raison', 'quete_reussie', 'quete_active'],
};

for (const f of ['_dlgEntrees', '_dlgAtteignables', '_dlgNextMorts',
	'_dlgFusionChoix', '_dlgFusionNoeud', '_dlgFusionDoc',
	'_dlgPoserTexte', '_dlgPoserNombre', '_dlgPoserBooleen', '_dlgPoserRecompenses',
	'_dlgOffreTransport', '_dlgOffreEscorte',
	'_dlgValiderNoeud', '_dlgValiderDoc', '_dlgLayoutGraphe']) {
	vm.runInThisContext(extraire(f));
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Un document de référence calqué sur `pnj:templier_armand_de_vaucremont_01` : un service
// `acces` dont les deux nœuds de résultat ne sont atteints par AUCUN `next`.
function docRef() {
	return {
		_id: 'pnj:gardien',
		_rev: '3-abc',
		type: 'pnj',
		nom: 'Armand',
		race: 'humain',
		vocation: 'garde',
		portrait: 'garde.png',
		description: 'Un templier.',
		services: {
			acces: { lieu: 'lieu:la_mine', noeuds: { ouvre: 'acces_ouvre', refus: 'acces_refus' } },
		},
		dialogue: {
			noeud_depart: 'accueil',
			noeuds: {
				accueil: {
					texte: 'Halte.',
					choix: [
						{ id: 'passer', label: 'Passer', condition: { acces_ouvrable: true }, action: { service: 'acces', op: 'passer' } },
						{ id: 'infos', label: 'Pourquoi ?', next: 'registre' },
						{ id: 'rien', label: 'Rien.', next: 'fin' },
					],
				},
				registre: { texte: 'Le registre.', choix: [{ id: 'retour', label: 'Revenir.', next: 'accueil' }] },
				acces_ouvre: { texte: 'Passez.', choix: [{ id: 'fin', label: 'Descendre.', next: 'fin' }] },
				acces_refus: { texte: 'Non.', choix: [{ id: 'fin', label: 'Partir.', next: 'fin' }] },
			},
		},
	};
}

// ── _dlgEntrees ──────────────────────────────────────────────────────────────
t('les entrées comptent le départ, l_attente ET les nœuds de service', () => {
	const doc = docRef();
	doc.dialogue.noeud_attente = 'registre';
	const e = _dlgEntrees(doc);
	assert.deepStrictEqual([...e].sort(), ['acces_ouvre', 'acces_refus', 'accueil', 'registre']);
});

t('une entrée qui ne désigne aucun nœud existant est écartée', () => {
	const doc = docRef();
	// Référence morte : le linter la signale, mais la traversée ne doit pas planter.
	doc.services.acces.noeuds.ouvre = 'noeud_absent';
	const e = _dlgEntrees(doc);
	assert.ok(!e.has('noeud_absent'));
	assert.ok(e.has('acces_refus'));
});

t('un document sans dialogue ni services ne lève pas', () => {
	assert.deepStrictEqual([..._dlgEntrees({})], []);
	assert.deepStrictEqual([..._dlgEntrees(null)], []);
});

// ── _dlgAtteignables ─────────────────────────────────────────────────────────
t('l_atteignabilité suit les next, cycles compris', () => {
	const doc = docRef();
	const noeuds = doc.dialogue.noeuds;
	// `registre → accueil → registre` : sans le garde-fou, la traversée boucle sans fin.
	const vus = _dlgAtteignables(noeuds, _dlgEntrees(doc));
	assert.deepStrictEqual([...vus].sort(), ['acces_ouvre', 'acces_refus', 'accueil', 'registre']);
});

t('un nœud que rien n_atteint est bien signalé mort', () => {
	const doc = docRef();
	doc.dialogue.noeuds.orphelin = { texte: 'Personne ne me lit.', choix: [{ id: 'f', label: 'x', next: 'fin' }] };
	const vus = _dlgAtteignables(doc.dialogue.noeuds, _dlgEntrees(doc));
	assert.ok(!vus.has('orphelin'));
});

t('sans le service, ses nœuds de résultat passeraient pour morts', () => {
	const doc = docRef();
	delete doc.services;   // le PNJ perd son service `acces`
	const vus = _dlgAtteignables(doc.dialogue.noeuds, _dlgEntrees(doc));
	// C'est la raison d'être du paramètre : ils ne sont atteints par aucun `next`.
	assert.ok(!vus.has('acces_ouvre'));
	assert.ok(!vus.has('acces_refus'));
});

// ── _dlgNextMorts ────────────────────────────────────────────────────────────
t('un next qui ne mène nulle part est repéré, la sentinelle fin ne l_est pas', () => {
	const doc = docRef();
	doc.dialogue.noeuds.accueil.choix[1].next = 'nulle_part';
	const morts = _dlgNextMorts(doc.dialogue.noeuds);
	assert.deepStrictEqual(morts, [{ noeud: 'accueil', choix: 'infos', cible: 'nulle_part' }]);
});

t('aucun next mort sur un document sain', () => {
	assert.deepStrictEqual(_dlgNextMorts(docRef().dialogue.noeuds), []);
});

// ── _dlgFusionChoix ──────────────────────────────────────────────────────────
t('une clé inconnue d_un CHOIX survit à la fusion', () => {
	const ancien = { id: 'a', label: 'A', next: 'b', ma_cle_a_moi: 42 };
	const out = _dlgFusionChoix(ancien, { id: 'a', label: 'Abis', next: 'c' });
	assert.strictEqual(out.ma_cle_a_moi, 42);
	assert.strictEqual(out.label, 'Abis');
	assert.strictEqual(out.next, 'c');
});

t('une action efface le next (le moteur l_ignore de toute façon)', () => {
	const out = _dlgFusionChoix({ id: 'a', label: 'A', next: 'b' },
		{ id: 'a', label: 'A', next: 'b', action: { service: 'acces', op: 'passer' } });
	assert.deepStrictEqual(out.action, { service: 'acces', op: 'passer' });
	assert.ok(!('next' in out), 'le next doit être retiré quand une action est posée');
});

t('soin et don n_ont pas d_op', () => {
	const out = _dlgFusionChoix({}, { id: 'a', label: 'A', action: { service: 'soin', op: '' } });
	assert.deepStrictEqual(out.action, { service: 'soin' });
});

t('un champ vidé est SUPPRIMÉ, jamais écrit à vide', () => {
	const ancien = { id: 'a', label: 'A', next: 'b', condition: { x: true }, deplacer: 'lieu:z' };
	const out = _dlgFusionChoix(ancien, { id: 'a', label: 'A', next: '', condition: {}, deplacer: '' });
	assert.ok(!('next' in out));
	assert.ok(!('condition' in out));
	assert.ok(!('deplacer' in out));
});

// ── _dlgFusionNoeud ──────────────────────────────────────────────────────────
t('une clé inconnue d_un NŒUD survit à la fusion', () => {
	const ancien = { texte: 'x', choix: [], portee_secrete: 'ne pas perdre' };
	const out = _dlgFusionNoeud(ancien, { texte: 'y', choix: [] });
	assert.strictEqual(out.portee_secrete, 'ne pas perdre');
	assert.strictEqual(out.texte, 'y');
});

t('un delai_min nul ou illisible n_est PAS écrit', () => {
	// Le linter refuse `delai_min <= 0` : « il doit être un entier de secondes > 0, sinon
	// il ne verrouille rien ». L'écrire quand même produirait un document fautif.
	for (const brut of ['', '0', '-5', 'abc']) {
		const out = _dlgFusionNoeud({}, { texte: 'x', delai_min: brut, choix: [] });
		assert.ok(!('delai_min' in out), 'delai_min ne doit pas être écrit pour ' + JSON.stringify(brut));
	}
	const ok = _dlgFusionNoeud({}, { texte: 'x', delai_min: '3600', choix: [] });
	assert.strictEqual(ok.delai_min, 3600);
});

t('un relation.delta nul retire tout le bloc relation', () => {
	const ancien = { texte: 'x', choix: [], relation: { delta: 1, lieu: 'lieu:a' } };
	const out = _dlgFusionNoeud(ancien, { texte: 'x', choix: [], relation: { delta: '0' } });
	assert.ok(!('relation' in out));
});

t('relation conserve les clés inconnues du bloc et écrit ce qu_on lui donne', () => {
	const ancien = { texte: 'x', choix: [], relation: { delta: 1, mystere: true } };
	const out = _dlgFusionNoeud(ancien, {
		texte: 'x', choix: [], relation: { delta: '2', lieu: 'lieu:b', unique: 'u1' }
	});
	assert.deepStrictEqual(out.relation, { delta: 2, mystere: true, lieu: 'lieu:b', unique: 'u1' });
});

t('relation_reinit est une chaîne à un élément, une liste au-delà', () => {
	const un = _dlgFusionNoeud({}, { texte: 'x', choix: [], relation_reinit: ['a'] });
	assert.strictEqual(un.relation_reinit, 'a');
	const deux = _dlgFusionNoeud({}, { texte: 'x', choix: [], relation_reinit: ['a', 'b'] });
	assert.deepStrictEqual(deux.relation_reinit, ['a', 'b']);
	const zero = _dlgFusionNoeud({}, { texte: 'x', choix: [], relation_reinit: ['', '  '.trim()] });
	assert.ok(!('relation_reinit' in zero));
});

// ── _dlgFusionDoc ────────────────────────────────────────────────────────────
function champsDepuis(doc) {
	return {
		nom: doc.nom, race: doc.race, vocation: doc.vocation, portrait: doc.portrait,
		description: doc.description || '',
		noeud_depart: doc.dialogue.noeud_depart,
		noeud_attente: doc.dialogue.noeud_attente || '',
		noeuds: doc.dialogue.noeuds,
		services: doc.services || {},
	};
}

t('une passe à blanc rend un document IDENTIQUE à l_original', () => {
	// LE test qui compte : charger un PNJ, ne rien changer, et retrouver exactement le
	// même document. Toute divergence ici serait une perte de contenu à l'import.
	const doc = docRef();
	const out = _dlgFusionDoc(doc, champsDepuis(doc));
	assert.deepStrictEqual(out, doc);
});

t('le _rev et les clés inconnues du DOCUMENT survivent', () => {
	const doc = docRef();
	doc.champ_inconnu = { garde: true };
	const out = _dlgFusionDoc(doc, champsDepuis(doc));
	assert.strictEqual(out._rev, '3-abc');
	assert.deepStrictEqual(out.champ_inconnu, { garde: true });
});

t('les sous-clés de services que le formulaire ne montre pas survivent', () => {
	// `escorte.recherche` (le registre de guilde) et `soin.gratuit_si` existent en base et
	// ne sont modélisés nulle part dans le formulaire.
	const doc = docRef();
	doc.services.escorte = { noeuds: { accepte: 'accueil' }, recherche: { cite: 'lieu:auxerre', proba: 0.5 } };
	doc.services.soin = { cout_cuivre: 1, gratuit_si: { seuil: 70 }, noeuds: { fait: 'accueil' } };
	const champs = champsDepuis(doc);
	const out = _dlgFusionDoc(doc, champs);
	assert.deepStrictEqual(out.services.escorte.recherche, { cite: 'lieu:auxerre', proba: 0.5 });
	assert.deepStrictEqual(out.services.soin.gratuit_si, { seuil: 70 });
});

t('un service retiré du formulaire disparaît du document', () => {
	const doc = docRef();
	const champs = champsDepuis(doc);
	champs.services = {};
	const out = _dlgFusionDoc(doc, champs);
	assert.ok(!('services' in out));
});

t('une description vidée est supprimée, pas écrite à vide', () => {
	const doc = docRef();
	const champs = champsDepuis(doc);
	champs.description = '';
	const out = _dlgFusionDoc(doc, champs);
	assert.ok(!('description' in out));
});

t('un noeud_attente vidé est supprimé du bloc dialogue', () => {
	const doc = docRef();
	doc.dialogue.noeud_attente = 'registre';
	const champs = champsDepuis(doc);
	champs.noeud_attente = '';
	const out = _dlgFusionDoc(doc, champs);
	assert.ok(!('noeud_attente' in out.dialogue));
	assert.strictEqual(out.dialogue.noeud_depart, 'accueil');
});

t('la fusion ne MUTE pas le document d_origine', () => {
	const doc = docRef();
	const copie = JSON.parse(JSON.stringify(doc));
	const champs = champsDepuis(doc);
	champs.nom = 'Autre';
	_dlgFusionDoc(doc, champs);
	assert.deepStrictEqual(doc, copie);
});

// ── _dlgOffreTransport ───────────────────────────────────────────────────────
t('une offre de transport sans destination ni cargaison n_est PAS écrite', () => {
	// `transport.offre_spec` rendrait None : l'offre serait silencieusement inerte.
	assert.strictEqual(_dlgOffreTransport(null, { id: 'quete:x', cargaison: [{ item: 'item:a' }] }), null);
	assert.strictEqual(_dlgOffreTransport(null, { id: 'quete:x', destination: 'lieu:b', cargaison: [] }), null);
	assert.strictEqual(_dlgOffreTransport(null, { id: 'quete:x', destination: 'lieu:b', cargaison: [{ item: '' }] }), null);
});

t('une offre de transport complète est écrite avec sa cargaison', () => {
	const out = _dlgOffreTransport(null, {
		id: 'quete:x', destination: 'lieu:b', titre: 'T', description: 'D', rang: 'F',
		duree: '3600', unique: true, retour: true,
		cargaison: [{ item: 'item:a', quantite: '2', poids: '5' }],
		recompenses: { xp: '30', cuivre: '200' },
	});
	assert.deepStrictEqual(out.cargaison, [{ item: 'item:a', quantite: 2, poids: 5 }]);
	assert.strictEqual(out.duree, 3600);
	assert.strictEqual(out.unique, true);
	assert.strictEqual(out.retour, true);
	assert.deepStrictEqual(out.recompenses, { xp: 30, cuivre: 200 });
});

t('les récompenses non modélisées (items, rang_guilde) survivent', () => {
	// Vues en base sur `pnj:borin_barbe_de_jais` : `items` porte la sentinelle
	// `lieu_parent: "auto"`, et `rang_guilde` ouvre le rang de guilde. Ni l'un ni l'autre
	// n'est saisissable ici — les perdre casserait la première mission du jeu.
	const ancienne = {
		id: 'quete:x', destination: 'lieu:b', cargaison: [{ item: 'item:a', quantite: 2 }],
		recompenses: { xp: 30, cuivre: 200, items: [{ item: 'item:carte', lieu_parent: 'auto' }], rang_guilde: 'F' },
	};
	const out = _dlgOffreTransport(ancienne, {
		id: 'quete:x', destination: 'lieu:b',
		cargaison: [{ item: 'item:a', quantite: '2' }],
		recompenses: { xp: '30', cuivre: '200' },
	});
	assert.deepStrictEqual(out.recompenses.items, [{ item: 'item:carte', lieu_parent: 'auto' }]);
	assert.strictEqual(out.recompenses.rang_guilde, 'F');
});

t('un poids absent n_est pas écrit, un poids donné l_est', () => {
	const sans = _dlgOffreTransport(null, {
		id: 'q', destination: 'lieu:b', cargaison: [{ item: 'item:a', quantite: '1', poids: '' }],
	});
	assert.ok(!('poids' in sans.cargaison[0]));
	const avec = _dlgOffreTransport(null, {
		id: 'q', destination: 'lieu:b', cargaison: [{ item: 'item:a', quantite: '1', poids: '0.5' }],
	});
	assert.strictEqual(avec.cargaison[0].poids, 0.5);
});

// ── _dlgOffreEscorte ─────────────────────────────────────────────────────────
t('une offre d_escorte sans destination ni protégés n_est PAS écrite', () => {
	assert.strictEqual(_dlgOffreEscorte(null, { id: 'q', proteges: [{ prenom: 'A' }] }), null);
	assert.strictEqual(_dlgOffreEscorte(null, { id: 'q', destination: 'lieu:b', proteges: [] }), null);
});

t('les TROIS formes de rendez-vous sont distinguées', () => {
	const base = { id: 'q', destination: 'lieu:b', proteges: [{ prenom: 'Aline' }] };
	// 1. Aucune rencontre : la personne attend chez le donneur.
	const chezLui = _dlgOffreEscorte(null, Object.assign({}, base, { rencontre_lieu: '' }));
	assert.ok(!('rencontre' in chezLui));
	// 2. Un lieu seul : à l'entrée du lieu.
	const entree = _dlgOffreEscorte(null, Object.assign({}, base, { rencontre_lieu: 'lieu:foret' }));
	assert.deepStrictEqual(entree.rencontre, { lieu: 'lieu:foret' });
	// 3. Lieu + zones : une case tirée dans le placement.
	const zone = _dlgOffreEscorte(null, Object.assign({}, base, {
		rencontre_lieu: 'lieu:auxerre', rencontre_zones: ['zone:foret_feuillus'],
	}));
	assert.deepStrictEqual(zone.rencontre, { lieu: 'lieu:auxerre', zones: ['zone:foret_feuillus'] });
});

t('rang_min n_est écrit que si la cité ET le rang sont donnés', () => {
	const base = { id: 'q', destination: 'lieu:b', proteges: [{ prenom: 'A' }] };
	const sans = _dlgOffreEscorte(null, Object.assign({}, base, { rang_min_cite: 'lieu:auxerre' }));
	assert.ok(!('rang_min' in sans));
	const avec = _dlgOffreEscorte(null, Object.assign({}, base, {
		rang_min_cite: 'lieu:auxerre', rang_min_rang: 'E',
	}));
	assert.deepStrictEqual(avec.rang_min, { cite: 'lieu:auxerre', rang: 'E' });
});

t('l_inventaire d_un protégé, non modélisé, survit', () => {
	const ancienne = {
		id: 'q', destination: 'lieu:b',
		proteges: [{ prenom: 'Aline', nom: 'V', inventaire: [{ item: 'item:herbes', poids: 0.1 }] }],
	};
	const out = _dlgOffreEscorte(ancienne, {
		id: 'q', destination: 'lieu:b', proteges: [{ prenom: 'Aline', nom: 'V' }],
	});
	assert.deepStrictEqual(out.proteges[0].inventaire, [{ item: 'item:herbes', poids: 0.1 }]);
});

// ── _dlgValiderNoeud ─────────────────────────────────────────────────────────
t('un nœud sans choix est refusé', () => {
	assert.match(_dlgValiderNoeud({}, 'a', { texte: 'x', choix: [] }), /sans choix/);
});

t('un identifiant vide, espacé, ou égal à la sentinelle est refusé', () => {
	assert.match(_dlgValiderNoeud({}, '', {}), /requis/);
	assert.match(_dlgValiderNoeud({}, 'mon noeud', { choix: [{ id: 'a' }] }), /espace/);
	assert.match(_dlgValiderNoeud({}, 'fin', { choix: [{ id: 'a' }] }), /sentinelle/);
});

t('deux choix de même id sont refusés (le second ne serait jamais joué)', () => {
	const noeud = { texte: 'x', choix: [{ id: 'a' }, { id: 'a' }] };
	assert.match(_dlgValiderNoeud({}, 'n', noeud), /jamais joué/);
});

t('un nœud correct passe', () => {
	assert.strictEqual(_dlgValiderNoeud({}, 'accueil', { texte: 'x', choix: [{ id: 'a' }, { id: 'b' }] }), '');
});

// ── _dlgValiderDoc ───────────────────────────────────────────────────────────
t('l__id doit commencer par pnj: et ne porter aucun espace', () => {
	const doc = docRef(); doc._id = 'gardien';
	assert.match(_dlgValiderDoc(doc), /pnj:/);
});

t('un noeud_depart absent ou mort est refusé', () => {
	const sans = docRef(); delete sans.dialogue.noeud_depart;
	assert.match(_dlgValiderDoc(sans), /noeud_depart/);
	const mort = docRef(); mort.dialogue.noeud_depart = 'nulle_part';
	assert.match(_dlgValiderDoc(mort), /n'existe pas/);
});

t('un noeud_attente mort est refusé', () => {
	const doc = docRef(); doc.dialogue.noeud_attente = 'nulle_part';
	assert.match(_dlgValiderDoc(doc), /noeud_attente/);
});

t('un document correct passe', () => {
	assert.strictEqual(_dlgValiderDoc(docRef()), '');
});

// ── _dlgLayoutGraphe ─────────────────────────────────────────────────────────
t('chaque nœud est placé EXACTEMENT une fois', () => {
	const doc = docRef();
	doc.dialogue.noeuds.orphelin = { texte: 'x', choix: [] };
	const noeuds = doc.dialogue.noeuds;
	const layout = _dlgLayoutGraphe(noeuds, _dlgEntrees(doc));
	const ids = layout.noeuds.map(n => n.id).sort();
	assert.deepStrictEqual(ids, Object.keys(noeuds).sort());
	assert.strictEqual(new Set(ids).size, ids.length, 'aucun doublon');
});

t('le placement est DÉTERMINISTE', () => {
	const doc = docRef();
	const a = _dlgLayoutGraphe(doc.dialogue.noeuds, _dlgEntrees(doc));
	const b = _dlgLayoutGraphe(doc.dialogue.noeuds, _dlgEntrees(doc));
	assert.deepStrictEqual(a.noeuds, b.noeuds);
	assert.deepStrictEqual(a.liens, b.liens);
});

t('les entrées sont au rang 0, un nœud plus profond après', () => {
	const doc = docRef();
	const layout = _dlgLayoutGraphe(doc.dialogue.noeuds, _dlgEntrees(doc));
	const parId = {};
	for (const n of layout.noeuds) parId[n.id] = n;
	assert.strictEqual(parId.accueil.rang, 0);
	assert.strictEqual(parId.registre.rang, 1);
});

t('un nœud inatteignable est marqué orphelin et rangé après les autres', () => {
	const doc = docRef();
	doc.dialogue.noeuds.orphelin = { texte: 'x', choix: [] };
	const layout = _dlgLayoutGraphe(doc.dialogue.noeuds, _dlgEntrees(doc));
	const parId = {};
	for (const n of layout.noeuds) parId[n.id] = n;
	assert.strictEqual(parId.orphelin.orphelin, true);
	assert.strictEqual(parId.accueil.orphelin, false);
	assert.ok(parId.orphelin.rang > parId.registre.rang);
});

t('un lien conditionné est signalé, la sentinelle fin ne produit aucun lien', () => {
	const doc = docRef();
	doc.dialogue.noeuds.accueil.choix[1].condition = { acces_refuse: true };
	const layout = _dlgLayoutGraphe(doc.dialogue.noeuds, _dlgEntrees(doc));
	const lien = layout.liens.filter(l => l.de === 'accueil' && l.vers === 'registre')[0];
	assert.ok(lien && lien.conditionne, 'le lien conditionné doit être marqué');
	assert.strictEqual(layout.liens.filter(l => l.vers === 'fin').length, 0);
});

t('un graphe vide ne lève pas', () => {
	const layout = _dlgLayoutGraphe({}, new Set());
	assert.deepStrictEqual(layout.noeuds, []);
	assert.deepStrictEqual(layout.liens, []);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);

// ── Sons d'action et musique ────────────────────────────────────────────────
// Brique partagée par /play et /combat. Trois choses, et rien d'autre :
//   1. `jouerSonUi(cle)` — un bruit d'INTERFACE (pas, porte, pièces, équipement…), tiré au
//      hasard parmi les variantes de sa clé (`SONS_UI`) ;
//   2. `installerSonsApi(table)` — le CHOKEPOINT des actions : un POST réussi vers une route
//      de la table joue sa clé. Une action neuve se sonorise en ajoutant UNE ligne à
//      `SONS_API`, sans toucher à son gestionnaire ;
//   3. `demarrerMusique({fichier, volume})` — une musique en BOUCLE (celle d'un donjon,
//      `donjon.musique_du_donjon`), reprise là où elle en était après un rechargement.
//
// ⚠️ Les sons de COMBAT (coups, sorts) ne passent PAS par ici : ils sont portés par les docs
// `animation:*` et joués par `jouerSon` (combat_telluris.html), un seul lecteur à la fois.
// Ce module ne fait que partager leur coupe-son.
//
// ⚠️ `play()` REJETTE quand le navigateur bloque la lecture (aucun geste de l'utilisateur sur
// la page) : chaque appel l'avale. Un son qui ne part pas ne doit jamais casser une action.
// La musique, elle, attend le premier geste pour démarrer.
//
// Volumes : niveau moyen MESURÉ de chaque fichier (ffmpeg volumedetect) ramené vers −21 dB,
// puis ×0,7 — un bruit d'interface reste sous les sons de combat.

// Coupe-son de TOUS les sons. ⚠️ Clé historique du bouton 🔊 de combat, gardée telle quelle :
// en changer ferait perdre leur réglage aux joueurs qui avaient déjà coupé le son.
const SONS_COUPE_CLE = 'telluris.combat.son';
const MUSIQUE_COUPEE_CLE = 'telluris.musique';
// sessionStorage : `{fichier, t}` — position de la musique au départ de la page (un changement
// d'étage de donjon recharge la page de combat ; la musique ne repart pas du début).
const MUSIQUE_REPRISE_CLE = 'telluris.musique.reprise';

function _serie(prefixe, n, ext) {
	return Array.from({ length: n }, (_, i) => prefixe + String(i).padStart(2, '0') + ext);
}

// clé → { fichiers: [variantes], volume }
const SONS_UI = {
	pas:          { fichiers: _serie('Footstep_Dirt_', 10, '.mp3'), volume: 0.7 },
	pas_eau:      { fichiers: _serie('Footstep_Water_', 8, '.mp3'), volume: 0.7 },
	porte:        { fichiers: ['world-door.wav'], volume: 0.6 },
	equiper:      { fichiers: ['inventory-chainmail1.wav', 'inventory-chainmail2.wav',
		'inventory-armor-light.wav', 'inventory-metal-small1.wav'], volume: 0.65 },
	desequiper:   { fichiers: ['inventory-cloth.wav', 'inventory-metal-small2.wav'], volume: 0.6 },
	poser:        { fichiers: ['inventory-cloth-heavy.wav'], volume: 0.55 },
	ramasser:     { fichiers: ['inventory-cloth.wav', 'inventory-wood-small.wav'], volume: 0.65 },
	pieces:       { fichiers: ['inventory-coin.wav', 'inventory-coin2.wav', 'inventory-coin3.wav',
		..._serie('Pickup_Gold_', 5, '.mp3')], volume: 0.55 },
	boire:        { fichiers: ['inventory-bottle.wav', 'inventory-bubble.wav',
		'inventory-bubble2.wav', 'inventory-bubble3.wav'], volume: 0.55 },
	bois:         { fichiers: ['inventory-wood-small.wav'], volume: 0.7 },
	recolte:      { fichiers: ['inventory-beads.wav', 'inventory-cloth.wav'], volume: 0.7 },
	ecrire:       { fichiers: ['inventory-cloth.wav'], volume: 0.5 },
	progression:  { fichiers: ['power_up_sound_v1.ogg'], volume: 0.6 },
	apprentissage:{ fichiers: ['Jingle_Achievement_00.mp3'], volume: 0.6 },
	succes:       { fichiers: ['Jingle_Achievement_00.mp3'], volume: 0.6 },
	sort:         { fichiers: ['Spell_00.mp3', 'Spell_01.mp3'], volume: 0.7 },
	competence:   { fichiers: ['battle-sword-unsheathe.wav', 'battle-sword-unsheathe3.wav'], volume: 0.5 },
	nuit:         { fichiers: ['power_up_sound_v0.ogg'], volume: 0.6 },
	choix:        { fichiers: ['Menu_Select_00.mp3'], volume: 0.7 },
	valider:      { fichiers: ['interface3.wav'], volume: 0.45 },
	annuler:      { fichiers: ['interface6.wav'], volume: 0.4 },
	onglet:       { fichiers: ['interface1.wav'], volume: 0.5 },
	sac:          { fichiers: ['Inventory_Open_00.mp3'], volume: 0.7 },
	ouvrir:       { fichiers: ['Inventory_Open_01.mp3'], volume: 0.5 },
	fermer:       { fichiers: ['interface2.wav'], volume: 0.5 },
	degainer:     { fichiers: ['battle-sword-unsheathe.wav', 'battle-sword-unsheathe2.wav',
		'battle-sword-unsheathe4.wav', 'battle-sword-unsheathe5.wav'], volume: 0.5 },
	fuite:        { fichiers: ['Footstep_Dirt_02.mp3', 'Footstep_Dirt_05.mp3'], volume: 0.7 },
	victoire:     { fichiers: ['Jingle_Win_00.mp3'], volume: 0.35 },
	defaite:      { fichiers: ['Jingle_Lose_00.mp3'], volume: 0.35 },
	coffre:       { fichiers: ['world-door.wav'], volume: 0.5 },
};

// Route POST (chemin après `api/`, `*` = un segment quelconque) → clé de `SONS_UI`.
// Seule une réponse HTTP RÉUSSIE sonne : un refus du serveur reste muet.
const SONS_API = {
	'equip': 'equiper', 'unequip': 'desequiper',
	'drop_item': 'poser', 'pickup_item': 'ramasser', 'groupe/transferer': 'poser',
	'buy_item': 'pieces', 'sell_item': 'pieces', 'marchander': 'pieces',
	'consommer': 'boire', 'couper': 'bois', 'recolter': 'recolte',
	'spend_xp': 'progression', 'spend_xp_vocation': 'progression',
	'apprendre_sort': 'apprentissage', 'apprendre_competence': 'apprentissage',
	'apprendre_magie': 'apprentissage', 'monter_magie': 'apprentissage',
	'lancer_sort': 'sort', 'utiliser_competence': 'competence',
	'renommer_objet': 'ecrire', 'journal': 'ecrire', 'scriptorium/ecrire': 'ecrire',
	'focaliser': 'valider', 'intro/raison': 'choix', 'pnj/dialogue/choix': 'choix',
	'quetes/accepter': 'valider', 'quetes/terminer': 'succes', 'quetes/deposer': 'pieces',
	'quetes/abandonner': 'annuler',
	'recrutement/embaucher': 'pieces', 'recrutement/engager': 'pieces',
	'recrutement/reprendre': 'valider', 'recrutement/refuser': 'annuler',
	'recrutement/congedier': 'annuler', 'groupe/compagnie': 'valider',
	'montures/acheter': 'pieces', 'montures/relacher': 'annuler',
	'commande/passer': 'pieces', 'commande/retirer': 'ramasser',
	'commande/relancer': 'valider', 'commande/annuler': 'annuler',
	'auberge/nuit': 'nuit', 'auberge/table': 'choix', 'auberge/message': 'ecrire',
	'auberge/annonce': 'ecrire', 'auberge/annonce/retirer': 'annuler',
	'proprietes/acheter': 'pieces', 'proprietes/louer': 'pieces', 'proprietes/vendre': 'pieces',
	'proprietes/caisse/relever': 'pieces', 'proprietes/registre/relever': 'ecrire',
	'proprietes/abandonner': 'annuler', 'proprietes/occuper': 'porte',
	'proprietes/quitter': 'porte', 'proprietes/installer': 'bois',
	'proprietes/engager': 'pieces', 'proprietes/renvoyer': 'annuler',
	'proprietes/heberger': 'valider', 'proprietes/reprendre': 'valider',
	'proprietes/coffre/transferer': 'poser', 'proprietes/atelier/donner': 'poser',
	'proprietes/atelier/reprendre': 'ramasser', 'proprietes/atelier/choisir': 'valider',
	'proprietes/recolter': 'recolte', 'proprietes/ecurie/loger': 'valider',
	'proprietes/ecurie/reprendre': 'valider',
	'combat/*/collect': 'pieces',
};

// Clé de `table` pour une URL (relative, absolue, avec ou sans `/`, avec ou sans query), ou ''.
// Pur : testé par dev/test_sons_client.js.
function cleSonApi(url, table) {
	let chemin = String(url || '');
	const i = chemin.search(/[?#]/);
	if (i >= 0) chemin = chemin.slice(0, i);
	const m = chemin.match(/(?:^|\/)api\/(.+)$/);
	if (!m) return '';
	const segs = m[1].replace(/\/+$/, '').split('/');
	for (const motif of Object.keys(table || {})) {
		const ms = motif.split('/');
		if (ms.length === segs.length && ms.every((s, k) => s === '*' || s === segs[k])) {
			return table[motif];
		}
	}
	return '';
}

// Variante tirée par `alea()` ∈ [0,1) (injecté : Math.random en jeu, fixé en test).
function choisirFichier(entree, alea) {
	const f = (entree && entree.fichiers) || [];
	if (!f.length) return '';
	const r = (alea || Math.random)();
	return f[Math.min(f.length - 1, Math.max(0, Math.floor(r * f.length)))];
}

function _lireCle(stockage, cle) {
	try { return stockage.getItem(cle); } catch (e) { return null; }   // mode privé, bac à sable
}
function _ecrireCle(stockage, cle, val) {
	try { stockage.setItem(cle, val); } catch (e) { /* mode privé */ }
}

// Relu à CHAQUE son : la page de combat a son propre bouton 🔊 sur la même clé.
function sonsCoupes() { return _lireCle(localStorage, SONS_COUPE_CLE) === '0'; }
function basculerSons() {
	const coupe = !sonsCoupes();
	_ecrireCle(localStorage, SONS_COUPE_CLE, coupe ? '0' : '1');
	return coupe;
}

function jouerSonUi(cle, alea) {
	const entree = SONS_UI[cle];
	if (!entree || sonsCoupes() || typeof Audio === 'undefined') return;
	const fichier = choisirFichier(entree, alea);
	if (!fichier) return;
	// Un `Audio` neuf par son : deux bruits rapprochés (deux pas) se chevauchent au lieu de
	// se couper ; le cache HTTP évite de retélécharger le fichier.
	const a = new Audio('/sounds/' + encodeURIComponent(fichier));
	a.volume = Math.min(1, Math.max(0, entree.volume == null ? 1 : entree.volume));
	const p = a.play();
	if (p && p.catch) p.catch(() => {});
}

// Enveloppe `window.fetch` UNE fois : chaque POST réussi vers une route de `table` sonne.
// ⚠️ La réponse est rendue intacte à l'appelant — on n'y lit que `ok`, jamais le corps.
function installerSonsApi(table) {
	if (typeof window === 'undefined' || !window.fetch || window.fetch._sonsApi) return;
	const origine = window.fetch;
	const enveloppe = function (input, init) {
		const p = origine.apply(this, arguments);
		const methode = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
		const url = typeof input === 'string' ? input : (input && input.url) || '';
		const cle = methode === 'POST' ? cleSonApi(url, table) : '';
		if (cle) p.then(r => { if (r && r.ok) jouerSonUi(cle); }).catch(() => {});
		return p;
	};
	enveloppe._sonsApi = true;
	window.fetch = enveloppe;
}

// Clics délégués : `[{selecteur, cle}]`, la PREMIÈRE règle dont le sélecteur contient la
// cible gagne (les plus précises d'abord). `cle` peut être une fonction de l'élément.
function brancherSonsClics(racine, regles) {
	if (!racine || !racine.addEventListener) return;
	racine.addEventListener('click', e => {
		const cible = e.target;
		if (!cible || !cible.closest) return;
		for (const r of regles || []) {
			const el = cible.closest(r.selecteur);
			if (!el) continue;
			const cle = typeof r.cle === 'function' ? r.cle(el) : r.cle;
			if (cle) jouerSonUi(cle);
			return;
		}
	}, true);
}

// ── Musique en boucle ───────────────────────────────────────────────────────
let _musique = null;          // HTMLAudioElement en cours
let _musiqueVolume = 0.5;

function musiqueCoupee() { return _lireCle(localStorage, MUSIQUE_COUPEE_CLE) === '0'; }

function _memoriserMusique() {
	if (!_musique || !_musique.dataset.fichier) return;
	_ecrireCle(sessionStorage, MUSIQUE_REPRISE_CLE,
		JSON.stringify({ fichier: _musique.dataset.fichier, t: _musique.currentTime || 0 }));
}

function _lancerMusique() {
	if (!_musique || musiqueCoupee()) return;
	const p = _musique.play();
	if (p && p.catch) p.catch(() => {
		// Lecture bloquée faute de geste : elle démarre au premier clic ou touche.
		const relancer = () => {
			document.removeEventListener('pointerdown', relancer, true);
			document.removeEventListener('keydown', relancer, true);
			if (_musique && !musiqueCoupee()) { const q = _musique.play(); if (q && q.catch) q.catch(() => {}); }
		};
		document.addEventListener('pointerdown', relancer, true);
		document.addEventListener('keydown', relancer, true);
	});
}

// `m` = `{fichier, volume}` (cf. `donjon.musique_du_donjon`) ; null ⇒ rien.
function demarrerMusique(m) {
	if (!m || !m.fichier || typeof Audio === 'undefined') return;
	if (_musique) _musique.pause();   // ⚠️ pas arreterMusique : elle effacerait la reprise
	_musiqueVolume = Math.min(1, Math.max(0, parseFloat(m.volume)));
	if (isNaN(_musiqueVolume)) _musiqueVolume = 0.5;
	const a = new Audio('/sounds/' + encodeURIComponent(m.fichier));
	a.loop = true;
	a.volume = _musiqueVolume;
	a.dataset.fichier = m.fichier;
	let reprise = null;
	try { reprise = JSON.parse(_lireCle(sessionStorage, MUSIQUE_REPRISE_CLE) || 'null'); } catch (e) { reprise = null; }
	if (reprise && reprise.fichier === m.fichier && reprise.t > 0) {
		// ⚠️ `currentTime` ne se pose qu'une fois les métadonnées là (sinon ignoré).
		a.addEventListener('loadedmetadata', () => {
			try { a.currentTime = reprise.t % (a.duration || Infinity); } catch (e) { /* pas de seek */ }
		}, { once: true });
	}
	_musique = a;
	window.addEventListener('pagehide', _memoriserMusique);
	_lancerMusique();
}

// Fondu de `ms` puis arrêt ; la position mémorisée est effacée (la scène est finie).
function arreterMusique(ms) {
	const a = _musique;
	_musique = null;
	_ecrireCle(sessionStorage, MUSIQUE_REPRISE_CLE, 'null');
	if (!a) return;
	if (!ms) { a.pause(); return; }
	const v0 = a.volume, t0 = Date.now();
	const pas = () => {
		const k = Math.min(1, (Date.now() - t0) / ms);
		a.volume = v0 * (1 - k);
		if (k < 1) setTimeout(pas, 50); else a.pause();
	};
	pas();
}

// → true si la musique est maintenant coupée.
function basculerMusique() {
	const coupe = !musiqueCoupee();
	_ecrireCle(localStorage, MUSIQUE_COUPEE_CLE, coupe ? '0' : '1');
	if (_musique) { if (coupe) _musique.pause(); else _lancerMusique(); }
	return coupe;
}

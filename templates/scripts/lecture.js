// templates/scripts/lecture.js — lecture à voix haute PARTAGÉE (speechSynthesis) :
// /admin/lore (séances, parcours) ↔ livres de /play (fiche d'un livre du sac ou de la vitrine).
//
// Fonctions pures (dev/test_lecture_lore_client.js, dev/test_livres_client.js) :
//   lectureNettoyer, lectureDecouper, livreTextesALire, livreImagesHtml.
// Lecteur des livres de /play : livreLire(btn) / livreArreter(). Le lore garde son propre
// lecteur (surlignage des blocs, reprise au clic) et n'emprunte ici que les deux fonctions pures.

/** Texte à prononcer : pictogrammes retirés, en-têtes des séances lus en clair. */
function lectureNettoyer(texte) {
	return String(texte || '')
		.replace(/✍️?\s*Auteur/g, "L'Auteur")
		.replace(/🤖\s*ChatGPT/g, 'ChatGPT')
		.replace(/[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu, '')
		.replace(/[←→↔▸▾·•|#*_`]/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

/** Énoncés d'au plus `max` caractères, coupés aux fins de phrase puis aux virgules
 *  (Chrome interrompt un énoncé trop long). Un mot plus long que `max` reste entier. */
function lectureDecouper(texte, max) {
	const out = [];
	const ajouter = morceau => {
		morceau = morceau.trim();
		if (!morceau) return;
		if (out.length && (out[out.length - 1] + ' ' + morceau).length <= max) out[out.length - 1] += ' ' + morceau;
		else out.push(morceau);
	};
	for (const phrase of String(texte || '').match(/[^.!?…;:]+[.!?…;:]*\s*/g) || []) {
		if (phrase.trim().length <= max) { ajouter(phrase); continue; }
		let courant = '';
		for (const mot of phrase.split(/(?<=,)\s+|\s+/)) {
			if (courant && (courant + ' ' + mot).length > max) { ajouter(courant); courant = mot; }
			else courant = courant ? courant + ' ' + mot : mot;
		}
		ajouter(courant);
	}
	return out;
}

/** Énoncés d'un livre : son titre puis son texte, nettoyés et découpés. Rien pour un objet
 *  qui n'est pas un livre, ni pour un livre scellé ou sans texte. */
function livreTextesALire(item) {
	if (!item || item.categorie !== 'livre' || item.contenu_scelle || !item.description) return [];
	return [item.nom || ''].concat(lectureDecouper(lectureNettoyer(item.description), 200))
		.map(lectureNettoyer).filter(Boolean);
}

/** Planche et illustrations d'un livre (`item.images` = [{url}], URL bâties et encodées par
 *  le serveur). Rien pour un livre scellé. Une image absente s'efface d'elle-même. */
function livreImagesHtml(item) {
	if (!item || item.contenu_scelle || !Array.isArray(item.images) || !item.images.length) return '';
	const esc = s => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
	return '<div class="livre-images">' + item.images.map(im =>
		`<a href="${esc(im.url)}" target="_blank" rel="noopener"><img src="${esc(im.url)}" alt="" loading="lazy" onerror="this.parentNode.remove()"></a>`
	).join('') + '</div>';
}

// ── Lecteur des livres de /play ──────────────────────────────────────────────
let _livreBtn = null;

/** Arrête la lecture en cours et rend son libellé au bouton. */
function livreArreter() {
	if (window.speechSynthesis) window.speechSynthesis.cancel();
	if (_livreBtn) { _livreBtn.textContent = '▶ Lire'; _livreBtn.setAttribute('aria-pressed', 'false'); }
	_livreBtn = null;
}

/** ▶ Lire / ■ Arrêter. `item` est passé par l'appelant (jamais relu dans le DOM). Voix
 *  française si le navigateur en a une ; vitesse et voix mémorisées par le lore réutilisées. */
function livreLire(btn, item) {
	const synth = window.speechSynthesis;
	if (!synth) return;
	if (_livreBtn === btn) { livreArreter(); return; }
	livreArreter();
	const morceaux = livreTextesALire(item);
	if (!morceaux.length) return;
	let pref = {};
	try { pref = JSON.parse(localStorage.getItem('telluris.lore_lecture.v1') || '{}') || {}; } catch (e) { pref = {}; }
	const voix = synth.getVoices();
	const voixChoisie = voix.find(v => v.name === pref.voix) || voix.find(v => /^fr/i.test(v.lang)) || null;
	_livreBtn = btn;
	btn.textContent = '■ Arrêter';
	btn.setAttribute('aria-pressed', 'true');
	morceaux.forEach((texte, i) => {
		const u = new SpeechSynthesisUtterance(texte);
		u.lang = 'fr-FR';
		if (voixChoisie) u.voice = voixChoisie;
		u.rate = Number(pref.vitesse) || 1;
		if (i === morceaux.length - 1) u.onend = () => { if (_livreBtn === btn) livreArreter(); };
		synth.speak(u);
	});
}

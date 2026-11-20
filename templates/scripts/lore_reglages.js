// scripts/lore_reglages.js — réglages de LECTURE des pages du lore (/admin/lore et suivantes).
//
// Thème (sombre / parchemin), taille du texte (A− / A+), police (défaut / lisible / dyslexie),
// mémorisés par navigateur. Chargé SANS defer dans le <head> (part-lore-base-css.html) :
// les attributs de <html> sont posés avant le premier rendu, sans flash de l'autre thème.
// Le bouton « Aa » est monté par `LoreReglages.monter(conteneur)`. Une page qui a déjà son
// propre thème (chronologie, parchemin d'office) passe `{ theme: false }` ; `{ aide: false }`
// ôte la ligne des raccourcis (page qui ne les a pas).
// Fonctions pures testées : dev/test_lore_client.js.

/** Réglages valides depuis n'importe quel objet lu (localStorage peut contenir n'importe quoi). */
function loreReglagesNormaliser(r) {
	r = (r && typeof r === 'object') ? r : {};
	const taille = Math.round(Math.min(1.6, Math.max(0.8, Number(r.taille) || 1)) * 10) / 10;
	return {
		theme: r.theme === 'parchemin' ? 'parchemin' : 'sombre',
		taille,
		police: ['lisible', 'dyslexie'].includes(r.police) ? r.police : 'defaut',
	};
}

(function () {
	const CLE = 'telluris.lore_reglages.v1';
	const lire = () => { try { return loreReglagesNormaliser(JSON.parse(localStorage.getItem(CLE) || '{}')); } catch (e) { return loreReglagesNormaliser({}); } };
	const ecrire = r => { try { localStorage.setItem(CLE, JSON.stringify(r)); } catch (e) { /* mode privé */ } };
	let reglages = lire();
	const appliquer = () => {
		const h = document.documentElement;
		if (h.dataset.themeFixe !== '1') h.dataset.theme = reglages.theme;
		h.dataset.police = reglages.police;
		h.style.setProperty('--lore-echelle', String(reglages.taille));
	};
	appliquer();

	function monter(conteneur, options) {
		options = options || {};
		if (!conteneur) return;
		if (options.theme === false) document.documentElement.dataset.themeFixe = '1';
		const btn = document.createElement('button');
		btn.type = 'button';
		btn.className = 'icone-btn';
		btn.textContent = 'Aa';
		btn.title = 'Réglages de lecture (thème, taille, police)';
		btn.setAttribute('aria-label', 'Réglages de lecture');
		btn.setAttribute('aria-expanded', 'false');
		btn.setAttribute('aria-controls', 'reglages-panneau');
		const p = document.createElement('div');
		p.className = 'reglages-panneau';
		p.id = 'reglages-panneau';
		p.hidden = true;
		p.setAttribute('role', 'dialog');
		p.setAttribute('aria-label', 'Réglages de lecture');
		p.innerHTML =
			(options.theme === false ? '' :
			'<fieldset><legend>Thème</legend><div class="ligne">' +
			'<button type="button" data-theme="sombre">🌙 Sombre</button>' +
			'<button type="button" data-theme="parchemin">📜 Parchemin</button></div></fieldset>') +
			'<fieldset><legend>Taille du texte</legend><div class="ligne">' +
			'<button type="button" data-taille="-1" aria-label="Réduire le texte">A−</button>' +
			'<span class="taille-val" aria-live="polite"></span>' +
			'<button type="button" data-taille="1" aria-label="Agrandir le texte">A+</button>' +
			'<button type="button" data-taille="0">Normal</button></div></fieldset>' +
			'<fieldset><legend>Police</legend><div class="ligne">' +
			'<button type="button" data-police="defaut">Habituelle</button>' +
			'<button type="button" class="f-lisible" data-police="lisible">Lisible</button>' +
			'<button type="button" class="f-dyslexie" data-police="dyslexie">Dyslexie</button></div></fieldset>' +
			(options.aide === false ? '' :
			'<p class="aide">Raccourcis : <kbd>/</kbd> chercher · <kbd>←</kbd> <kbd>→</kbd> page précédente / suivante (en lecture) · <kbd>Échap</kbd> fermer.</p>');
		const rafraichir = () => {
			for (const b of p.querySelectorAll('[data-theme]')) b.setAttribute('aria-pressed', String(b.dataset.theme === reglages.theme));
			for (const b of p.querySelectorAll('[data-police]')) b.setAttribute('aria-pressed', String(b.dataset.police === reglages.police));
			p.querySelector('.taille-val').textContent = Math.round(reglages.taille * 100) + ' %';
		};
		const changer = maj => { reglages = loreReglagesNormaliser(Object.assign({}, reglages, maj)); ecrire(reglages); appliquer(); rafraichir(); };
		p.addEventListener('click', e => {
			const b = e.target.closest('button');
			if (!b) return;
			if (b.dataset.theme) changer({ theme: b.dataset.theme });
			else if (b.dataset.police) changer({ police: b.dataset.police });
			else if (b.dataset.taille !== undefined) {
				const d = Number(b.dataset.taille);
				changer({ taille: d === 0 ? 1 : reglages.taille + d * 0.1 });
			}
		});
		const afficher = v => { p.hidden = !v; btn.setAttribute('aria-expanded', String(v)); if (v) { rafraichir(); const f = p.querySelector('button'); if (f) f.focus(); } };
		btn.addEventListener('click', () => afficher(p.hidden));
		document.addEventListener('keydown', e => { if (e.key === 'Escape' && !p.hidden) { afficher(false); btn.focus(); } });
		document.addEventListener('click', e => { if (!p.hidden && !p.contains(e.target) && !btn.contains(e.target)) afficher(false); });
		conteneur.appendChild(btn);
		document.body.appendChild(p);
	}

	window.LoreReglages = { monter, lire: () => reglages };
})();

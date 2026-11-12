// Bouton de partage (icône) des pages du lore (/admin/lore, une lecture, /admin/lore/chronologie).
// Tout bouton `[data-partager]` partage l'URL COURANTE (ancre comprise) : feuille de partage
// native si le navigateur en a une (mobile), sinon copie dans le presse-papiers ; repli
// `execCommand('copy')` hors contexte sécurisé (http sur une IP du réseau : pas de clipboard).
// Bouton à icône seule (SVG, couleur `--muted` de la page) : le retour s'affiche à la place de l'icône (✓ / ✗), puis
// l'icône revient ; le libellé passe dans `title`. Verrouillé par dev/test_partage_client.js.

/** Copie `texte` ; résout `true` si la copie a eu lieu. */
async function partageCopier(texte, nav, doc) {
	if (nav && nav.clipboard && typeof nav.clipboard.writeText === 'function') {
		try { await nav.clipboard.writeText(texte); return true; } catch (e) { /* repli */ }
	}
	if (!doc || !doc.body) return false;
	const zone = doc.createElement('textarea');
	zone.value = texte;
	zone.setAttribute('readonly', '');
	zone.style.position = 'fixed';
	zone.style.opacity = '0';
	doc.body.appendChild(zone);
	zone.select();
	let ok = false;
	try { ok = !!doc.execCommand('copy'); } catch (e) { ok = false; }
	doc.body.removeChild(zone);
	return ok;
}

/** Partage `{url, titre}` → 'partage' | 'copie' | 'annule' | 'echec'. */
async function partagerLien(url, titre, nav, doc) {
	if (nav && typeof nav.share === 'function') {
		try { await nav.share({ title: titre, url }); return 'partage'; }
		catch (e) {
			if (e && e.name === 'AbortError') return 'annule';  // feuille fermée par l'utilisateur
			// Autre refus (NotAllowedError…) : on copie à la place.
		}
	}
	return (await partageCopier(url, nav, doc)) ? 'copie' : 'echec';
}

const PARTAGE_RETOURS = {
	partage: ['✓', 'Lien partagé'],
	copie: ['✓', 'Lien copié'],
	echec: ['✗', 'Copie impossible : '],
};

function installerPartage(racine) {
	for (const btn of racine.querySelectorAll('[data-partager]')) {
		const icone = btn.innerHTML;
		const titre = btn.title;
		let minuteur = null;
		btn.addEventListener('click', async () => {
			const r = await partagerLien(window.location.href, document.title, navigator, document);
			const retour = PARTAGE_RETOURS[r];
			if (!retour) return;
			btn.textContent = retour[0];
			btn.title = retour[1] + (r === 'echec' ? window.location.href : '');
			clearTimeout(minuteur);
			minuteur = setTimeout(() => { btn.innerHTML = icone; btn.title = titre; }, 1800);
		});
	}
}

if (typeof document !== 'undefined' && document.querySelectorAll) {
	if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => installerPartage(document));
	else installerPartage(document);
}

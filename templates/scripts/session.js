// ── Session expirée → page d'authentification ───────────────────────────────
// Le renouvellement du jeton est fait par le SERVEUR (utils/session.py,
// RafraichissementMiddleware) sur toute requête : tant que le jeton de rafraîchissement
// vit, le joueur ne voit rien. Quand il est mort (périmé, révoqué, réutilisé), plus
// rien ne peut être fait sur la page : on part sur /auth au lieu d'afficher
// « Invalid session credentials ».
//
// Signal : une réponse 401, ou l'en-tête `x-session: aucune` (posé sur toute réponse
// servie sans session, quel que soit le code d'erreur de l'endpoint).
// La promesse rendue à l'appelant reste alors EN SUSPENS : aucun toast d'erreur ne
// s'affiche pendant la navigation.
//
// À charger dans le <head> des pages connectées, AVANT leurs scripts (les fetch du
// chargement passent déjà par l'enveloppe). Compose avec `installerSonsApi` (sons.js).

const SESSION_PAGE_AUTH = '/auth';

function sessionExpiree(reponse) {
	if (!reponse) return false;
	if (reponse.status === 401) return true;
	const entete = reponse.headers && reponse.headers.get ? reponse.headers.get('x-session') : null;
	return entete === 'aucune';
}

function _memeOrigine(url) {
	try { return new URL(url, window.location.href).origin === window.location.origin; }
	catch (e) { return false; }
}

function installerSessionApi() {
	if (typeof window === 'undefined' || !window.fetch || window.fetch._sessionApi) return;
	const origine = window.fetch;
	let redirige = false;
	const enveloppe = function (input, init) {
		const url = typeof input === 'string' ? input : (input && input.url) || String(input || '');
		const p = origine.apply(this, arguments);
		if (!_memeOrigine(url)) return p;
		return p.then(r => {
			if (!sessionExpiree(r)) return r;
			if (!redirige) {
				redirige = true;
				window.location.href = SESSION_PAGE_AUTH;
			}
			return new Promise(() => {});
		});
	};
	enveloppe._sessionApi = true;
	window.fetch = enveloppe;
}

installerSessionApi();

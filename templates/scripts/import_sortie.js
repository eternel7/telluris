// templates/scripts/import_sortie.js
// 📥 Importer : le fichier produit par le DERNIER run réussi d'un outil de dev/, envoyé à
// `/admin/import-bulk`. Partagé par /admin/dev-tools et /admin/lieux.
//
// ⚠️ PUT COMPLET (CLAUDE.md §11) : un `_id` existant est remplacé — d'où le confirm() qui
// liste les `_id`. Le serveur refuse un fichier plus ancien que le run (`sortie_fraiche`) :
// un générateur qui n'a rien écrit ne laisse pas renvoyer le lot d'un run précédent.
//
// `ui` = { setStatus(msg, kind), progress: <conteneur de barre>, bar: <barre> }.
// Rend l'événement `done` du flux (imported/failed/total), ou null (annulé, refusé, échec) —
// l'appelant décide de ce qui se rafraîchit ensuite.

function _importDetailErreur(data, code) {
	const d = data && data.detail;
	return typeof d === 'string' ? d : (d ? JSON.stringify(d) : String(code));
}

async function importerSortieOutil(outilId, ui) {
	const r = await fetch('/admin/dev-tools/sortie?outil=' + encodeURIComponent(outilId));
	const data = await r.json().catch(() => ({}));
	if (!r.ok) { ui.setStatus('Import impossible : ' + _importDetailErreur(data, r.status), 'err'); return null; }
	const ids = (data.ids || []).filter(Boolean);
	const apercu = ids.slice(0, 15).join('\n') + (ids.length > 15 ? '\n… et ' + (ids.length - 15) + ' autre(s)' : '');
	if (!confirm(`Importer ${data.docs.length} document(s) de ${data.chemin} ?\n\n`
			+ `⚠️ PUT complet : un document existant de même _id est remplacé.\n\n${apercu}`)) return null;
	ui.setStatus('Import…', 'run');
	ui.progress.hidden = false;
	ui.bar.style.width = '0%';
	try {
		const res = await fetch('/admin/import-bulk', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(data.docs),
		});
		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			ui.setStatus('Échec : ' + _importDetailErreur(err, res.status), 'err');
			return null;
		}
		const reader = res.body.getReader();
		const decoder = new TextDecoder();
		let buf = '', fin = null;
		while (true) {
			const morceau = await reader.read();
			if (morceau.done) break;
			buf += decoder.decode(morceau.value, { stream: true });
			let nl;
			while ((nl = buf.indexOf('\n')) >= 0) {
				const ligne = buf.slice(0, nl).trim();
				buf = buf.slice(nl + 1);
				if (!ligne) continue;
				let ev;
				try { ev = JSON.parse(ligne); } catch (e) { continue; }
				if (ev.event === 'progress') {
					ui.bar.style.width = Math.round(100 * ev.processed / ev.total) + '%';
					ui.setStatus(`Import… ${ev.processed}/${ev.total}`, 'run');
				} else if (ev.event === 'done') {
					fin = ev;
				}
			}
		}
		if (!fin) { ui.setStatus('Import interrompu : réponse incomplète.', 'err'); return null; }
		ui.setStatus(`✓ ${fin.imported}/${fin.total} document(s) importé(s).` + (fin.failed ? ` ${fin.failed} échec(s).` : ''),
			fin.failed ? 'err' : 'ok');
		return fin;
	} finally {
		ui.progress.hidden = true;
	}
}

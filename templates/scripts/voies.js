// voies.js — TRACÉ DES VOIES d'une carte (éditeur de carte, carte « 🔍 Analyse d'image »).
//
// Où circule-t-on VRAIMENT ? Trois lectures d'une même grille :
//   • les RÉGIONS connexes — une enclave injoignable, deux rives de même région (le fleuve se traverse) ;
//   • les GOULOTS — cases dont le blocage coupe une région : trou de rempart, gué, pont ;
//   • la carte de PASSAGE — centralité d'intermédiarité : les axes et les brèches, quelle que soit leur largeur.
//
// ⚠️ LECTURE SEULE et PUR : rien n'est écrit, et aucune globale n'est lue hormis nav.js et
// deplacement.js. La règle de marche vient de `pasAutoriseRegle` / `caseType1` /
// `caseFranchissable` — ce fichier n'en recopie AUCUNE, sinon le tracé et le mode test
// finiraient par dire deux choses différentes. Testé par dev/test_voies_client.js.
//
// Chargé en <script> classique APRÈS nav.js et deplacement.js. Cases indexées `i = y * W + x`.

// Importance minimale d'un goulot = taille du plus petit côté qu'il isole. En dessous, chaque
// impasse d'une case serait « un goulot » : du bruit qui noierait les vrais passages.
const VOIES_GOULOT_MIN = 3;
// Sources de la carte de passage. Au-delà, échantillonnage au PAS FIXE, donc déterministe :
// Brandes exact coûte N × (N + arêtes), ~150 M d'opérations sur Auxerre (86×48).
const VOIES_SOURCES_MAX = 400;
const VOIES_DIRS = [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]];

// Graphe de marche : un nœud par case qui TIENT sous la règle, une arête par pas accepté.
// Non orienté par construction — `getFinalMask` est bidirectionnel et le prédicat de case est
// le même aux deux bouts. Les diagonales comptent : un rempart ouvert EN COIN est un trou.
function voiesGraphe(cells, nav, dims, regle) {
	const W = (dims && dims.x) || 0, H = (dims && dims.y) || 0;
	const N = W * H;
	// ⚠️ `caseFranchissable(null, …)` rend true : sans grille, TOUT deviendrait praticable.
	const grille = Array.isArray(cells) ? cells : [];
	const tient = regle === 'combat'
		? (x, y) => caseFranchissable(grille, x, y)
		: (x, y) => caseType1(grille, x, y);
	const noeud = new Uint8Array(N);
	const voisins = new Array(N);
	for (let y = 0; y < H; y++) {
		for (let x = 0; x < W; x++) {
			const i = y * W + x;
			const liste = [];
			if (tient(x, y)) {
				noeud[i] = 1;
				for (const [dx, dy] of VOIES_DIRS) {
					if (pasAutoriseRegle(regle, grille, nav, dims, x, y, dx, dy).ok) liste.push((y + dy) * W + (x + dx));
				}
			}
			voisins[i] = liste;
		}
	}
	return { W, H, N, noeud, voisins };
}

// Régions connexes (BFS itératif). `region[i]` = rang de la région, -1 hors nœud.
// Renumérotées par taille DÉCROISSANTE : la région 0 est toujours la principale, le rendu et les
// comptes n'ont pas à la chercher. À taille égale, l'ordre de découverte départage.
function voiesRegions(graphe) {
	const { N, noeud, voisins } = graphe;
	const region = new Int32Array(N).fill(-1);
	const tailles = [];
	const file = new Int32Array(N);
	for (let s = 0; s < N; s++) {
		if (!noeud[s] || region[s] !== -1) continue;
		const id = tailles.length;
		let tete = 0, queue = 0;
		file[queue++] = s;
		region[s] = id;
		while (tete < queue) {
			const u = file[tete++];
			for (const v of voisins[u]) {
				if (region[v] === -1) { region[v] = id; file[queue++] = v; }
			}
		}
		tailles.push(queue);
	}
	const ordre = tailles.map((_, id) => id).sort((a, b) => tailles[b] - tailles[a] || a - b);
	const rang = new Int32Array(tailles.length);
	ordre.forEach((id, r) => { rang[id] = r; });
	for (let i = 0; i < N; i++) if (region[i] !== -1) region[i] = rang[region[i]];
	return { region, tailles: ordre.map(id => tailles[id]) };
}

// Goulots = points d'articulation (Tarjan), filtrés par IMPORTANCE : pour chaque enfant DFS qui
// ne remonte pas au-dessus de la case, min(sous-arbre, région − 1 − sous-arbre), et on garde le
// max. La racine n'a pas de cas à part : avec un seul enfant, l'autre côté vaut 0.
// ⚠️ ITÉRATIF : une région de 4 000 cases en file indienne ferait sauter la pile en récursif.
// ⚠️ Une brèche de 2 cases de large n'a PAS de goulot unique — c'est la carte de passage qui la montre.
function voiesGoulots(graphe, regions, seuil) {
	const min = Math.max(1, seuil == null ? VOIES_GOULOT_MIN : seuil);
	const { N, noeud, voisins } = graphe;
	const disc = new Int32Array(N).fill(-1);
	const low = new Int32Array(N);
	const taille = new Int32Array(N);
	const parent = new Int32Array(N).fill(-1);
	const suivant = new Int32Array(N);
	const importance = new Int32Array(N);
	const pile = new Int32Array(N);
	let temps = 0;
	for (let r = 0; r < N; r++) {
		if (!noeud[r] || disc[r] !== -1) continue;
		const total = regions.tailles[regions.region[r]];
		let sommet = 0;
		pile[sommet++] = r;
		disc[r] = low[r] = temps++;
		taille[r] = 1;
		while (sommet > 0) {
			const u = pile[sommet - 1];
			const vs = voisins[u];
			if (suivant[u] < vs.length) {
				const v = vs[suivant[u]++];
				if (disc[v] === -1) {
					parent[v] = u;
					disc[v] = low[v] = temps++;
					taille[v] = 1;
					pile[sommet++] = v;
				} else if (v !== parent[u] && disc[v] < low[u]) {
					low[u] = disc[v];
				}
			} else {
				sommet--;
				const p = parent[u];
				if (p === -1) continue;
				if (low[u] < low[p]) low[p] = low[u];
				taille[p] += taille[u];
				if (low[u] >= disc[p]) {
					const coupe = Math.min(taille[u], total - 1 - taille[u]);
					if (coupe > importance[p]) importance[p] = coupe;
				}
			}
		}
	}
	const res = [];
	for (let i = 0; i < N; i++) if (importance[i] >= min) res.push({ i, importance: importance[i] });
	return res;
}

// Carte de passage : centralité d'intermédiarité de Brandes, BFS NON PONDÉRÉ, normalisée sur [0,1].
// ⚠️ Chaque pas compte 1 : le surcoût ×2/×5 du terrain difficile en combat n'est pas pondéré.
// Sources au pas fixe `ceil(nœuds / maxSources)` : même grille ⇒ même carte, à la décimale près.
function voiesPassage(graphe, maxSources) {
	const { N, noeud, voisins } = graphe;
	const score = new Float64Array(N);
	const noeuds = [];
	for (let i = 0; i < N; i++) if (noeud[i]) noeuds.push(i);
	if (!noeuds.length) return score;
	const pas = Math.ceil(noeuds.length / Math.max(1, maxSources || VOIES_SOURCES_MAX));
	const dist = new Int32Array(N).fill(-1);
	const sigma = new Float64Array(N);
	const delta = new Float64Array(N);
	const ordre = new Int32Array(N);
	for (let k = 0; k < noeuds.length; k += pas) {
		const s = noeuds[k];
		let tete = 0, queue = 0;
		ordre[queue++] = s;
		dist[s] = 0;
		sigma[s] = 1;
		while (tete < queue) {
			const u = ordre[tete++];
			for (const v of voisins[u]) {
				if (dist[v] === -1) { dist[v] = dist[u] + 1; ordre[queue++] = v; }
				if (dist[v] === dist[u] + 1) sigma[v] += sigma[u];
			}
		}
		for (let q = queue - 1; q >= 0; q--) {
			const w = ordre[q];
			for (const v of voisins[w]) {
				if (dist[v] === dist[w] - 1) delta[v] += sigma[v] / sigma[w] * (1 + delta[w]);
			}
			if (w !== s) score[w] += delta[w];
		}
		// Remise à zéro de ce que CE parcours a touché, et de lui seul.
		for (let q = 0; q < queue; q++) { const w = ordre[q]; dist[w] = -1; sigma[w] = 0; delta[w] = 0; }
	}
	let haut = 0;
	for (let i = 0; i < N; i++) if (score[i] > haut) haut = score[i];
	if (haut > 0) for (let i = 0; i < N; i++) score[i] /= haut;
	return score;
}

// Empreinte d'une grille (FNV-1a sur cases, `nav` et dimensions) : un tracé dont l'empreinte ne
// correspond plus à ce qui est affiché est PÉRIMÉ, et le peindre mentirait. Les clés de `nav`
// sont triées — l'ordre d'insertion ne change rien au jeu, il ne doit rien changer ici.
function voiesSignature(cells, nav, dims) {
	const W = (dims && dims.x) || 0, H = (dims && dims.y) || 0;
	let h = 0x811c9dc5;
	const mixe = (n) => { h = Math.imul(h ^ (n | 0), 16777619); };
	const grille = Array.isArray(cells) ? cells : [];
	for (let y = 0; y < H; y++) {
		const ligne = grille[y];
		for (let x = 0; x < W; x++) {
			const v = ligne ? ligne[x] : undefined;
			mixe(v === undefined ? -1 : (Number.isFinite(Number(v)) ? Number(v) : -2));
		}
	}
	for (const cle of Object.keys(nav || {}).sort()) {
		for (let c = 0; c < cle.length; c++) mixe(cle.charCodeAt(c));
		mixe(Number(nav[cle]) || 0);
	}
	return `${W}x${H}:${(h >>> 0).toString(16)}`;
}

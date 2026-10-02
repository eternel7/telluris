"""Connexions orphelines : règle partagée par `dev/purge_connexions_orphelines.py` et la
colonne calculée `node_inexistant` de `/admin/table`."""

from utils import connexions_orphelines as co


def _conn(*lieux):
	return {"_id": "link:x", "type": "connection",
		"nodes": [{"lieu": l, "pos": [0, 0]} for l in lieux]}


def test_lieux_cites_sans_doublon_et_tries():
	cs = [_conn("lieu:b", "lieu:a"), _conn("lieu:a", "lieu:c")]
	assert co.lieux_cites(cs) == ["lieu:a", "lieu:b", "lieu:c"]


def test_lieux_cites_ignore_les_noeuds_mal_formes():
	cs = [{"nodes": ["lieu:a", {"pos": [0, 0]}, {"lieu": ""}, {"lieu": "lieu:b"}]}, {}]
	assert co.lieux_cites(cs) == ["lieu:b"]


def test_connexion_saine():
	assert co.noeuds_inexistants(_conn("lieu:a", "lieu:b"), {"lieu:a", "lieu:b"}) == []


def test_un_seul_noeud_inexistant_suffit():
	assert co.noeuds_inexistants(_conn("lieu:a", "lieu:disparu"), {"lieu:a"}) == [(1, "lieu:disparu")]


def test_noeud_sans_lieu_ou_mal_forme_est_inexistant():
	c = {"nodes": [{"pos": [0, 0]}, "lieu:a", {"lieu": "lieu:a"}]}
	assert co.noeuds_inexistants(c, {"lieu:a"}) == [(0, None), (1, None)]


def test_orphelines_garde_l_ordre_et_ecarte_les_saines():
	saine, orph1, orph2 = _conn("lieu:a", "lieu:b"), _conn("lieu:z", "lieu:a"), _conn("lieu:y", "lieu:x")
	sortie = co.orphelines([orph1, saine, orph2], {"lieu:a", "lieu:b"})
	assert [c for c, _ in sortie] == [orph1, orph2]
	assert sortie[1][1] == [(0, "lieu:y"), (1, "lieu:x")]

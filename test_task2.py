"""
Tests unitaires pour Task 2 : State Management, LWW & Failure Detection
========================================================================
Utilise pytest + unittest.mock.patch pour contrôler time.time()
et garantir des résultats déterministes.
"""

import pytest
from unittest.mock import patch
from task2_state import (
    merge_stores,
    merge_heartbeats,
    get_live_nodes,
    increment_own_heartbeat,
)


# ==================================================================
# Tests pour merge_stores
# ==================================================================
class TestMergeStores:

    def test_remote_key_not_in_local(self):
        """Une clé présente uniquement dans remote doit être ajoutée."""
        local = {}
        remote = {"key_a": ("value_a", 1.0)}

        merge_stores(local, remote)

        assert local == {"key_a": ("value_a", 1.0)}

    def test_local_key_not_in_remote(self):
        """Une clé présente uniquement dans local doit rester inchangée."""
        local = {"key_a": ("value_a", 1.0)}
        remote = {}

        merge_stores(local, remote)

        assert local == {"key_a": ("value_a", 1.0)}

    def test_remote_newer_wins(self):
        """Si le remote a un timestamp plus récent, il remplace le local."""
        local = {"key_a": ("old_value", 1.0)}
        remote = {"key_a": ("new_value", 2.0)}

        merge_stores(local, remote)

        assert local["key_a"] == ("new_value", 2.0)

    def test_local_newer_wins(self):
        """Si le local a un timestamp plus récent, il reste inchangé."""
        local = {"key_a": ("local_value", 5.0)}
        remote = {"key_a": ("remote_value", 3.0)}

        merge_stores(local, remote)

        assert local["key_a"] == ("local_value", 5.0)

    def test_equal_timestamps_keeps_local(self):
        """En cas d'égalité de timestamps, le local est conservé (pas strictement >)."""
        local = {"key_a": ("local_value", 1.0)}
        remote = {"key_a": ("remote_value", 1.0)}

        merge_stores(local, remote)

        assert local["key_a"] == ("local_value", 1.0)

    def test_empty_stores(self):
        """Fusionner deux stores vides ne doit pas lever d'erreur."""
        local = {}
        remote = {}

        merge_stores(local, remote)

        assert local == {}

    def test_multiple_keys_mixed(self):
        """Test avec plusieurs clés dans des cas différents."""
        local = {
            "existing_local_only": ("v1", 1.0),
            "conflict_local_wins": ("local_v", 10.0),
            "conflict_remote_wins": ("old_v", 1.0),
        }
        remote = {
            "new_from_remote": ("v2", 2.0),
            "conflict_local_wins": ("remote_v", 5.0),
            "conflict_remote_wins": ("new_v", 99.0),
        }

        merge_stores(local, remote)

        assert local["existing_local_only"] == ("v1", 1.0)
        assert local["new_from_remote"] == ("v2", 2.0)
        assert local["conflict_local_wins"] == ("local_v", 10.0)
        assert local["conflict_remote_wins"] == ("new_v", 99.0)


# ==================================================================
# Tests pour merge_heartbeats
# ==================================================================
class TestMergeHeartbeats:

    @patch("task2_state.time")
    def test_new_node_added(self, mock_time):
        """Un nœud inconnu dans remote doit être ajouté avec time.time()."""
        mock_time.time.return_value = 100.0
        local = {}
        remote = {18001: (5, 50.0)}

        merge_heartbeats(local, remote)

        assert local[18001] == (5, 100.0)

    @patch("task2_state.time")
    def test_higher_counter_updates(self, mock_time):
        """Si le counter remote est plus grand, on met à jour avec time.time()."""
        mock_time.time.return_value = 200.0
        local = {18001: (3, 100.0)}
        remote = {18001: (7, 150.0)}

        merge_heartbeats(local, remote)

        assert local[18001] == (7, 200.0)

    @patch("task2_state.time")
    def test_lower_counter_no_change(self, mock_time):
        """Si le counter remote est plus petit, le local reste inchangé."""
        mock_time.time.return_value = 200.0
        local = {18001: (10, 100.0)}
        remote = {18001: (5, 150.0)}

        merge_heartbeats(local, remote)

        assert local[18001] == (10, 100.0)

    @patch("task2_state.time")
    def test_equal_counter_no_change(self, mock_time):
        """Si les counters sont égaux, le local reste inchangé."""
        mock_time.time.return_value = 200.0
        local = {18001: (5, 100.0)}
        remote = {18001: (5, 150.0)}

        merge_heartbeats(local, remote)

        assert local[18001] == (5, 100.0)

    def test_empty_heartbeats(self):
        """Fusionner des heartbeats vides ne doit pas lever d'erreur."""
        local = {}
        remote = {}

        merge_heartbeats(local, remote)

        assert local == {}

    @patch("task2_state.time")
    def test_multiple_nodes_mixed(self, mock_time):
        """Test avec plusieurs nœuds dans des situations différentes."""
        mock_time.time.return_value = 300.0
        local = {
            18000: (10, 250.0),  # counter local > remote → inchangé
            18001: (3, 250.0),   # counter local < remote → mis à jour
        }
        remote = {
            18000: (5, 200.0),   # counter < local
            18001: (8, 200.0),   # counter > local
            18002: (1, 200.0),   # nœud inconnu → ajouté
        }

        merge_heartbeats(local, remote)

        assert local[18000] == (10, 250.0)    # inchangé
        assert local[18001] == (8, 300.0)     # mis à jour avec time.time()
        assert local[18002] == (1, 300.0)     # ajouté avec time.time()


# ==================================================================
# Tests pour get_live_nodes
# ==================================================================
class TestGetLiveNodes:

    @patch("task2_state.time")
    def test_all_alive(self, mock_time):
        """Tous les nœuds avec un timestamp récent sont retournés."""
        mock_time.time.return_value = 100.0
        heartbeats = {
            18000: (5, 95.0),   # 5s ago → alive
            18001: (3, 98.0),   # 2s ago → alive
            18002: (7, 99.0),   # 1s ago → alive
        }

        result = get_live_nodes(heartbeats, t_mort=10.0)

        assert sorted(result) == [18000, 18001, 18002]

    @patch("task2_state.time")
    def test_all_dead(self, mock_time):
        """Tous les nœuds avec un timestamp trop ancien → liste vide."""
        mock_time.time.return_value = 100.0
        heartbeats = {
            18000: (5, 50.0),   # 50s ago → dead
            18001: (3, 80.0),   # 20s ago → dead
        }

        result = get_live_nodes(heartbeats, t_mort=10.0)

        assert result == []

    @patch("task2_state.time")
    def test_mixed_alive_dead(self, mock_time):
        """Mix de nœuds vivants et morts → seuls les vivants retournés."""
        mock_time.time.return_value = 100.0
        heartbeats = {
            18000: (5, 95.0),   # 5s ago → alive (< 10)
            18001: (3, 80.0),   # 20s ago → dead (>= 10)
            18002: (7, 99.0),   # 1s ago → alive (< 10)
        }

        result = get_live_nodes(heartbeats, t_mort=10.0)

        assert sorted(result) == [18000, 18002]

    def test_empty_heartbeats(self):
        """Heartbeats vide → liste vide."""
        result = get_live_nodes({}, t_mort=10.0)

        assert result == []

    @patch("task2_state.time")
    def test_custom_t_mort(self, mock_time):
        """Le seuil t_mort custom est bien respecté."""
        mock_time.time.return_value = 100.0
        heartbeats = {
            18000: (5, 97.0),   # 3s ago → alive with t_mort=5
            18001: (3, 93.0),   # 7s ago → dead with t_mort=5
        }

        result = get_live_nodes(heartbeats, t_mort=5.0)

        assert result == [18000]

    @patch("task2_state.time")
    def test_exactly_at_threshold(self, mock_time):
        """Un nœud exactement au seuil (= t_mort) est considéré mort (pas strictement <)."""
        mock_time.time.return_value = 100.0
        heartbeats = {
            18000: (5, 90.0),   # exactement 10s ago → dead (not < 10)
        }

        result = get_live_nodes(heartbeats, t_mort=10.0)

        assert result == []


# ==================================================================
# Tests pour increment_own_heartbeat
# ==================================================================
class TestIncrementOwnHeartbeat:

    @patch("task2_state.time")
    def test_existing_node_incremented(self, mock_time):
        """Le counter d'un nœud existant est incrémenté de 1."""
        mock_time.time.return_value = 500.0
        heartbeats = {18000: (5, 400.0)}

        increment_own_heartbeat(heartbeats, 18000)

        assert heartbeats[18000] == (6, 500.0)

    @patch("task2_state.time")
    def test_new_node_initialized(self, mock_time):
        """Un nœud inexistant est initialisé à (1, time.time())."""
        mock_time.time.return_value = 500.0
        heartbeats = {}

        increment_own_heartbeat(heartbeats, 18000)

        assert heartbeats[18000] == (1, 500.0)

    @patch("task2_state.time")
    def test_only_own_node_affected(self, mock_time):
        """Seul le nœud ciblé est modifié, les autres restent inchangés."""
        mock_time.time.return_value = 500.0
        heartbeats = {
            18000: (5, 400.0),
            18001: (3, 400.0),
        }

        increment_own_heartbeat(heartbeats, 18000)

        assert heartbeats[18000] == (6, 500.0)
        assert heartbeats[18001] == (3, 400.0)  # inchangé


# ==================================================================
# Point d'entrée direct (python test_task2.py)
# ==================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

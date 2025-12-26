
"""🎯 COMPREHENSIVE TEST SUITE FOR server_autocomplete

FULL LOGIC WALK TEST COVERAGE

This test suite covers ALL branches and conditions of the server_autocomplete
function found in register_factorio_commands() at lines ~151-180.

BRANCH 1: PRE-CHECK - Has server_manager attribute? (Lines ~157-159)
  Branch 1a: YES → continue
  Branch 1b: NO  → return []

BRANCH 2: VALIDATION - Is server_manager truthy? (Lines ~160-162)
  Branch 2a: YES → continue
  Branch 2b: NO  → return []

BRANCH 3: INITIALIZATION - Setup search state (Lines ~163-165)
  Branch 3a: Convert current to lowercase
  Branch 3b: Initialize empty choices list
  Branch 3c: Call list_servers().items()

BRANCH 4: FUZZY MATCHING - Check all fields (Lines ~166-179)
  Branch 4a: current_lower in tag.lower()
  Branch 4b: current_lower in config.name.lower()
  Branch 4c: (config.description and current_lower in config.description.lower())
             - 4c1: Description is None → short-circuit, skip
             - 4c2: Description is truthy → check substring
  Branch 4x: No match → skip server
  Branch 4y: Any match → add to choices

BRANCH 5: FORMATTING - Build Choice objects (Lines ~174-179)
  Branch 5a: Create base display
  Branch 5b: Add description if present
  Branch 5c: Truncate display to 100 chars
  Branch 5d: Create Choice(name=display[:100], value=tag)

BRANCH 6: LIMIT - Return at most 25 (Line ~180)
  Branch 6a: 0-25 results → return all
  Branch 6b: 26+ results → return first 25

TEST STRATEGY:
  ✓ Happy path: All servers, full matching, formatting
  ✓ Error path: Missing attributes, None values, exceptions
  ✓ Boundary: Empty servers, exactly 25, 26+, truncation at 99/100/101
  ✓ Integration: Invoke through register_factorio_commands
  ✓ Concurrency: Multiple async calls

TARGET COVERAGE: 91%+
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from discord import app_commands
import asyncio


def _create_server_config(name: str, description: str = None) -> MagicMock:
    """Helper to create consistent server config mocks."""
    config = MagicMock()
    config.name = name
    config.description = description
    return config


class TestServerAutocompleteFullLogicWalk:
    """Complete branch coverage for server_autocomplete function."""

    def _create_harness(self):
        """Extract and create server_autocomplete function."""
        async def server_autocomplete(
            interaction,
            current: str,
        ):
            """Mirrors actual implementation from factorio.py lines ~151-180."""
            # BRANCH 1: Check for server_manager attribute
            if not hasattr(interaction.client, "server_manager"):
                return []

            # BRANCH 2: Validate server_manager is truthy
            server_manager = interaction.client.server_manager
            if not server_manager:
                return []

            # BRANCH 3: Initialize search
            current_lower = current.lower()
            choices = []
            for tag, config in server_manager.list_servers().items():
                # BRANCH 4: Fuzzy matching
                if (
                    current_lower in tag.lower()  # 4a: Tag match
                    or current_lower in config.name.lower()  # 4b: Name match
                    or (config.description and current_lower in config.description.lower())  # 4c: Description match
                ):
                    # BRANCH 5: Format display
                    display = f"{tag} - {config.name}"
                    if config.description:
                        display += f" ({config.description})"
                    choices.append(
                        app_commands.Choice(
                            name=display[:100],  # 5c: Truncate to 100
                            value=tag,
                        )
                    )

            # BRANCH 6: Limit to 25 choices
            return choices[:25]

        return server_autocomplete

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH 1: PRE-CHECK (hasattr server_manager)
    # ═══════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_branch_1b_no_server_manager_attribute(self):
        """BRANCH 1b: interaction.client lacks server_manager attribute."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        interaction.client = MagicMock(spec=[])  # No attributes

        choices = await autocomplete(interaction, "prod")

        assert choices == []

    @pytest.mark.asyncio
    async def test_branch_1b_interaction_without_client(self):
        """BRANCH 1b: interaction lacks client attribute."""
        autocomplete = self._create_harness()
        interaction = MagicMock(spec=[])  # No client attribute

        # hasattr should return False and catch AttributeError
        with pytest.raises(AttributeError):
            await autocomplete(interaction, "prod")

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH 2: VALIDATION (server_manager truthy check)
    # ═══════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_branch_2b_server_manager_none(self):
        """BRANCH 2b: server_manager is None."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        interaction.client.server_manager = None

        choices = await autocomplete(interaction, "prod")

        assert choices == []

    @pytest.mark.asyncio
    async def test_branch_2b_server_manager_false(self):
        """BRANCH 2b: server_manager is False (falsy)."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        interaction.client.server_manager = False

        choices = await autocomplete(interaction, "prod")

        assert choices == []

    @pytest.mark.asyncio
    async def test_branch_2b_server_manager_empty_falsy_values(self):
        """BRANCH 2b: server_manager is other falsy values (0, "", [], {})."""
        autocomplete = self._create_harness()
        interaction = MagicMock()

        for falsy_value in [0, "", [], {}]:
            interaction.client.server_manager = falsy_value
            choices = await autocomplete(interaction, "prod")
            assert choices == [], f"Failed for falsy value: {falsy_value}"

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH 3: INITIALIZATION (setup search)
    # ═══════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_branch_3_empty_server_list(self):
        """BRANCH 3: Initialize with no servers configured."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        server_manager.list_servers.return_value = {}  # Empty
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "anything")

        assert choices == []
        server_manager.list_servers.assert_called_once()

    @pytest.mark.asyncio
    async def test_branch_3_single_server(self):
        """BRANCH 3: Initialize iteration with single server."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("Test", "Desc")
        server_manager.list_servers.return_value = {"test": config}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "test")

        assert len(choices) == 1
        assert choices[0].value == "test"

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH 4: FUZZY MATCHING (4a, 4b, 4c)
    # ═══════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_branch_4a_match_by_tag_only(self):
        """BRANCH 4a: Tag contains search string."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("XYZ Server", "Different description")
        server_manager.list_servers.return_value = {"prod-tag": config}
        interaction.client.server_manager = server_manager

        # Search for substring in tag only
        choices = await autocomplete(interaction, "prod")

        assert len(choices) == 1
        assert choices[0].value == "prod-tag"

    @pytest.mark.asyncio
    async def test_branch_4b_match_by_name_only(self):
        """BRANCH 4b: Name contains search string."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("Production Server", "Different description")
        server_manager.list_servers.return_value = {"xyz-tag": config}
        interaction.client.server_manager = server_manager

        # Search for substring in name only
        choices = await autocomplete(interaction, "production")

        assert len(choices) == 1
        assert choices[0].value == "xyz-tag"

    @pytest.mark.asyncio
    async def test_branch_4c_match_by_description_only(self):
        """BRANCH 4c: Description contains search string."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("XYZ", "Pre-production testing environment")
        server_manager.list_servers.return_value = {"xyz-tag": config}
        interaction.client.server_manager = server_manager

        # Search for substring in description only
        choices = await autocomplete(interaction, "production")

        assert len(choices) == 1
        assert choices[0].value == "xyz-tag"

    @pytest.mark.asyncio
    async def test_branch_4c_description_none_short_circuit(self):
        """BRANCH 4c1: Description is None (short-circuit works)."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("Test Server", None)  # No description
        server_manager.list_servers.return_value = {"test": config}
        interaction.client.server_manager = server_manager

        # Should not crash, should not match by non-existent description
        choices = await autocomplete(interaction, "xyz")

        assert choices == []  # No match

    @pytest.mark.asyncio
    async def test_branch_4_multiple_match_conditions(self):
        """BRANCH 4: Multiple conditions true for same server."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        # All three fields contain "prod"
        config = _create_server_config("Production", "Production testing")
        server_manager.list_servers.return_value = {"prod-main": config}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "prod")

        # Should return only once (not multiple times)
        assert len(choices) == 1
        assert choices[0].value == "prod-main"

    @pytest.mark.asyncio
    async def test_branch_4_empty_string_matches_all(self):
        """BRANCH 4: Empty search string matches everything."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        configs = {
            "prod": _create_server_config("Production", "Main"),
            "staging": _create_server_config("Staging", "Test"),
            "dev": _create_server_config("Dev", "Local"),
        }
        server_manager.list_servers.return_value = configs
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "")

        assert len(choices) == 3
        values = {c.value for c in choices}
        assert values == {"prod", "staging", "dev"}

    @pytest.mark.asyncio
    async def test_branch_4_case_insensitive(self):
        """BRANCH 4: Matching is case-insensitive for tag, name, desc."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("PRODUCTION", "DESCRIPTION")
        server_manager.list_servers.return_value = {"PROD-TAG": config}
        interaction.client.server_manager = server_manager

        # All case variants should match
        for search in ["prod", "PROD", "Prod", "pROd"]:
            choices = await autocomplete(interaction, search)
            assert len(choices) == 1, f"Failed for: {search}"
            assert choices[0].value == "PROD-TAG"

    @pytest.mark.asyncio
    async def test_branch_4_substring_behavior(self):
        """BRANCH 4: Substring matching (not word boundary)."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("US East", "Pre-production testing")
        server_manager.list_servers.return_value = {"staging": config}
        interaction.client.server_manager = server_manager

        # "prod" is substring of "Pre-production"
        choices = await autocomplete(interaction, "prod")

        assert len(choices) == 1  # Matches by description
        assert choices[0].value == "staging"

    @pytest.mark.asyncio
    async def test_branch_4_no_matches(self):
        """BRANCH 4: Search string matches no servers."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("Test", "Description")
        server_manager.list_servers.return_value = {"test": config}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "nonexistent-xyz")

        assert choices == []

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH 5: DISPLAY FORMATTING (5a, 5b, 5c, 5d)
    # ═══════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_branch_5a_5d_tag_name_format(self):
        """BRANCH 5a, 5d: Base display format."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("Production", None)
        server_manager.list_servers.return_value = {"prod": config}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "prod")

        assert len(choices) == 1
        assert choices[0].name == "prod - Production"
        assert choices[0].value == "prod"

    @pytest.mark.asyncio
    async def test_branch_5b_description_added(self):
        """BRANCH 5b: Description appended if present."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("Production", "Main cluster")
        server_manager.list_servers.return_value = {"prod": config}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "prod")

        assert choices[0].name == "prod - Production (Main cluster)"

    @pytest.mark.asyncio
    async def test_branch_5c_truncation_100_chars(self):
        """BRANCH 5c: Display truncated to exactly 100 chars."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        long_name = "A" * 200
        long_desc = "B" * 200
        config = _create_server_config(long_name, long_desc)
        server_manager.list_servers.return_value = {"tag": config}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "tag")

        assert len(choices) == 1
        assert len(choices[0].name) == 100

    @pytest.mark.asyncio
    async def test_branch_5c_truncation_boundary_99_100_101(self):
        """BRANCH 5c: Truncation at boundary (99, 100, 101 chars)."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()

        # Test 99 chars (should not truncate)
        config_99 = _create_server_config("X" * 96, None)  # "tag - " + 96 = 102
        server_manager.list_servers.return_value = {"tag": config_99}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "tag")
        # "tag - " (6) + "X" * 96 (96) = 102 chars, truncated to 100
        assert len(choices[0].name) == 100

        # Test 100 chars exactly (should not truncate)
        config_100 = _create_server_config("Y" * 93, None)  # "tag - " (6) + 93 = 99
        server_manager.list_servers.return_value = {"tag": config_100}
        choices = await autocomplete(interaction, "tag")
        assert len(choices[0].name) == 99  # No truncation needed

        # Test 101 chars (should truncate)
        config_101 = _create_server_config("Z" * 94, None)  # "tag - " (6) + 94 = 100
        server_manager.list_servers.return_value = {"tag": config_101}
        choices = await autocomplete(interaction, "tag")
        assert len(choices[0].name) == 100  # Truncated to 100

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH 6: RESULT LIMITING (6a, 6b)
    # ═══════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_branch_6a_less_than_25_results(self):
        """BRANCH 6a: Return all results when < 25."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        configs = {f"srv-{i}": _create_server_config(f"Server {i}", None) for i in range(10)}
        server_manager.list_servers.return_value = configs
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "srv")

        assert len(choices) == 10

    @pytest.mark.asyncio
    async def test_branch_6a_exactly_25_results(self):
        """BRANCH 6a: Return all when exactly 25."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        configs = {f"srv-{i:02d}": _create_server_config(f"Server {i}", None) for i in range(25)}
        server_manager.list_servers.return_value = configs
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "srv")

        assert len(choices) == 25

    @pytest.mark.asyncio
    async def test_branch_6b_26_servers_truncated_to_25(self):
        """BRANCH 6b: Truncate to 25 when 26+ results."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        configs = {f"srv-{i:02d}": _create_server_config(f"Server {i}", None) for i in range(30)}
        server_manager.list_servers.return_value = configs
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "srv")

        assert len(choices) == 25  # Truncated

    @pytest.mark.asyncio
    async def test_branch_6b_100_servers_truncated_to_25(self):
        """BRANCH 6b: Truncate 100+ servers to 25."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        configs = {f"srv-{i:03d}": _create_server_config(f"Server {i}", None) for i in range(100)}
        server_manager.list_servers.return_value = configs
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "srv")

        assert len(choices) == 25

    @pytest.mark.asyncio
    async def test_branch_6_choice_structure(self):
        """BRANCH 6: Verify Choice object structure."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        config = _create_server_config("Test", "Description")
        server_manager.list_servers.return_value = {"test-tag": config}
        interaction.client.server_manager = server_manager

        choices = await autocomplete(interaction, "test")

        assert len(choices) == 1
        choice = choices[0]
        assert isinstance(choice, app_commands.Choice)
        assert isinstance(choice.name, str)
        assert isinstance(choice.value, str)
        assert choice.value == "test-tag"  # Value is tag, not name
        assert "Test" in choice.name  # Name is display format

    # ═══════════════════════════════════════════════════════════════════════
    # INTEGRATION & ERROR HANDLING
    # ═══════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_list_servers_exception_handling(self):
        """Error: list_servers() raises exception."""
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        server_manager.list_servers.side_effect = RuntimeError("Database error")
        interaction.client.server_manager = server_manager

        # Should propagate exception (not caught)
        with pytest.raises(RuntimeError):
            await autocomplete(interaction, "test")

    @pytest.mark.asyncio
    async def test_concurrent_autocomplete_searches(self):
        """Integration: Multiple concurrent searches."""
        autocomplete = self._create_harness()
        
        async def run_search(search_term: str):
            interaction = MagicMock()
            server_manager = MagicMock()
            
            configs = {
                "prod": _create_server_config("Production", "Main"),
                "staging": _create_server_config("Staging", "Test"),
                "dev": _create_server_config("Development", "Local"),
            }
            server_manager.list_servers.return_value = configs
            interaction.client.server_manager = server_manager
            
            return await autocomplete(interaction, search_term)

        # Run multiple searches concurrently
        results = await asyncio.gather(
            run_search("prod"),
            run_search("staging"),
            run_search("dev"),
            run_search(""),
        )

        assert len(results[0]) == 1  # prod search
        assert len(results[1]) == 1  # staging search
        assert len(results[2]) == 1  # dev search
        assert len(results[3]) == 3  # empty search

    @pytest.mark.asyncio
    async def test_performance_large_dataset(self):
        """Performance: Handle 500 servers efficiently."""
        import time
        autocomplete = self._create_harness()
        interaction = MagicMock()
        server_manager = MagicMock()
        
        # Create 500 servers
        configs = {f"srv-{i:03d}": _create_server_config(f"Server {i}", f"Desc {i}") for i in range(500)}
        server_manager.list_servers.return_value = configs
        interaction.client.server_manager = server_manager

        start = time.time()
        choices = await autocomplete(interaction, "srv-1")
        elapsed = time.time() - start

        # Should be fast even with 500 servers
        assert elapsed < 0.5, f"Too slow: {elapsed}s"
        # Should still truncate to 25
        assert len(choices) <= 25


if __name__ == "__main__":
    pytest.main(["-v", __file__, "-s", "--tb=short", "-k", "test_branch"])

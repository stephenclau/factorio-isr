"""
Tests for DiscordInterfaceFactory helper methods.
These test the extracted import logic that was previously untestable.
"""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Mock discord module
discord_mock = MagicMock()
discord_mock.Embed = MagicMock(return_value=MagicMock())
discord_mock.utils = MagicMock()
discord_mock.utils.utcnow = MagicMock(return_value="2025-12-03T00:00:00")
sys.modules['discord'] = discord_mock

from discord_interface import DiscordInterfaceFactory


class TestImportHelpers:
    """Test the import helper methods."""

    def test_import_discord_bot_success(self):
        """Test successful import of DiscordBot."""
        with patch('discord_bot.DiscordBot') as mock_class:
            result = DiscordInterfaceFactory._import_discord_bot()
            assert result is mock_class

    def test_import_discord_client_success(self):
        """Test successful import of DiscordClient."""
        with patch('discord_client.DiscordClient') as mock_class:
            result = DiscordInterfaceFactory._import_discord_client()
            assert result is mock_class

    def test_import_discord_bot_falls_back_to_importlib(self):
        """Test that importlib fallback is used when normal import fails."""
        with patch('builtins.__import__', side_effect=ImportError("No module")):
            with patch.object(
                DiscordInterfaceFactory,
                '_import_with_importlib'
            ) as mock_importlib:
                mock_class = MagicMock()
                mock_importlib.return_value = mock_class

                result = DiscordInterfaceFactory._import_discord_bot()

                mock_importlib.assert_called_once_with('discord_bot', 'DiscordBot')
                assert result is mock_class

    def test_import_with_importlib_success(self):
        """Test successful import using importlib."""
        with patch('importlib.util.spec_from_file_location') as mock_spec_from:
            with patch('importlib.util.module_from_spec') as mock_module_from:
                # Setup mocks
                mock_spec = MagicMock()
                mock_loader = MagicMock()
                mock_spec.loader = mock_loader
                mock_spec_from.return_value = mock_spec

                mock_module = MagicMock()
                mock_class = MagicMock()
                mock_module.DiscordBot = mock_class
                mock_module_from.return_value = mock_module

                # Execute
                result = DiscordInterfaceFactory._import_with_importlib(
                    'discord_bot', 'DiscordBot'
                )

                # Verify
                assert result is mock_class
                mock_spec_from.assert_called_once()
                mock_module_from.assert_called_once_with(mock_spec)
                mock_loader.exec_module.assert_called_once_with(mock_module)

    def test_import_with_importlib_spec_none(self):
        """Test error when spec is None - NOW TESTABLE!"""
        with patch('importlib.util.spec_from_file_location', return_value=None):
            with pytest.raises(ImportError, match="Could not load"):
                DiscordInterfaceFactory._import_with_importlib(
                    'discord_bot', 'DiscordBot'
                )

    def test_import_with_importlib_no_loader(self):
        """Test error when spec has no loader - NOW TESTABLE!"""
        mock_spec = MagicMock()
        mock_spec.loader = None

        with patch('importlib.util.spec_from_file_location', return_value=mock_spec):
            with pytest.raises(ImportError, match="Could not load"):
                DiscordInterfaceFactory._import_with_importlib(
                    'discord_bot', 'DiscordBot'
                )

    def test_import_with_importlib_no_current_path(self):
        """Test error when module has no __file__ - NOW TESTABLE!"""
        with patch('sys.modules') as mock_modules:
            mock_module = MagicMock()
            # Make __file__ attribute return None
            type(mock_module).__file__ = property(lambda self: None)
            mock_modules.__getitem__.return_value = mock_module

            with pytest.raises(ImportError, match="Could not determine module path"):
                DiscordInterfaceFactory._import_with_importlib(
                    'discord_bot', 'DiscordBot'
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

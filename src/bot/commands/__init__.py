

"""Discord slash command registration.

Exports register_factorio_commands() which registers all /factorio subcommands
under the command limit of 25 per Discord group.
"""

from .factorio import register_factorio_commands

__all__ = ["register_factorio_commands"]

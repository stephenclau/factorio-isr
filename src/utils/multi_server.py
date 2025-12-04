"""
Multi-server management utilities (framework-agnostic).

Can manage multiple Factorio servers, Prometheus endpoints, Logstash endpoints, etc.
"""

from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class ServerConfig:
    """Configuration for a single server/endpoint."""

    server_id: str
    name: str
    host: str
    port: int
    password: Optional[str] = None
    credentials: Optional[Union[str, Dict[str, str]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration."""
        if not self.server_id:
            raise ValueError("server_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.host:
            raise ValueError("host cannot be empty")
        if not isinstance(self.port, int) or self.port <= 0 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")

        # Ensure metadata is always a dict (never None)
        if self.metadata is None:
            self.metadata = {}

    def connection_string(self) -> str:
        """
        Generate connection string for this server.

        Returns:
            Connection string in format "host:port"
        """
        return f"{self.host}:{self.port}"


class MultiServerManager:
    """Manages multiple servers/endpoints for a single application."""

    def __init__(self):
        self.servers: Dict[str, ServerConfig] = {}
        self.default_server: Optional[str] = None
        logger.info("multi_server_manager_initialized")

    def add_server(self, config: ServerConfig) -> None:
        """
        Add a server configuration.

        Args:
            config: ServerConfig instance

        Raises:
            ValueError: If server with same ID already exists
        """
        # Check for duplicate
        if config.server_id in self.servers:
            raise ValueError(f"Server with ID '{config.server_id}' already exists")

        self.servers[config.server_id] = config
        if self.default_server is None:
            self.default_server = config.server_id

        logger.info(
            "server_added",
            server_id=config.server_id,
            name=config.name,
            host=config.host,
            port=config.port,
            is_default=self.default_server == config.server_id
        )

    def remove_server(self, server_id: str) -> None:
        """
        Remove a server configuration.

        Args:
            server_id: Server ID to remove

        Raises:
            ValueError: If server not found
        """
        if server_id not in self.servers:
            raise ValueError(f"Server with ID '{server_id}' not found")

        del self.servers[server_id]

        # Update default if necessary
        if self.default_server == server_id:
            self.default_server = next(iter(self.servers.keys()), None)

        logger.info("server_removed", server_id=server_id)

    def get_server(self, server_id: Optional[str] = None) -> Optional[ServerConfig]:
        """
        Get server config by ID, or default if None.

        Args:
            server_id: Server ID (uses default if None)

        Returns:
            ServerConfig or None if not found
        """
        # Use default if no server_id provided
        if server_id is None:
            server_id = self.default_server

        # If still None (no default set), return None
        if server_id is None:
            return None

        return self.servers.get(server_id)

    def set_default(self, server_id: str) -> None:
        """
        Set default server.

        Args:
            server_id: Server ID to set as default

        Raises:
            ValueError: If server not found
        """
        if server_id not in self.servers:
            raise ValueError(f"Server with ID '{server_id}' not found")

        self.default_server = server_id
        logger.info("default_server_changed", server_id=server_id)

    def list_servers(self) -> List[ServerConfig]:
        """List all configured servers."""
        return list(self.servers.values())

    def get_server_names(self) -> List[str]:
        """Get list of server names for autocomplete."""
        return [server.name for server in self.servers.values()]

    def get_server_by_name(self, name: str) -> Optional[ServerConfig]:
        """
        Get server by name (case-insensitive).

        Args:
            name: Server name

        Returns:
            ServerConfig or None if not found
        """
        name_lower = name.lower()
        for server in self.servers.values():
            if server.name.lower() == name_lower:
                return server
        return None

    def get_default_id(self) -> Optional[str]:
        """
        Get the default server ID.

        Returns:
            Default server ID or None if no default set
        """
        return self.default_server

    def has_default(self) -> bool:
        """
        Check if a default server is set.

        Returns:
            True if default is set, False otherwise
        """
        return self.default_server is not None

    def count(self) -> int:
        """
        Return number of configured servers.

        Returns:
            Number of servers
        """
        return len(self.servers)

    def __len__(self) -> int:
        """Return number of configured servers."""
        return len(self.servers)

    def __contains__(self, server_id: str) -> bool:
        """Check if server exists."""
        return server_id in self.servers

    def __bool__(self) -> bool:
        """Return True if manager has any servers."""
        return len(self.servers) > 0

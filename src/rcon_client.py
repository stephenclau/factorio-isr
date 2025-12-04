"""
RCON client for Factorio server queries with automatic reconnection.

Handles connection, authentication, and command execution using rcon library.
Includes automatic reconnection with exponential backoff.
"""

import asyncio
from typing import Optional, Any
import structlog

# Optional RCON support using rcon library
try:
    from rcon.source import Client as RCONClient
    RCON_AVAILABLE = True
except ImportError:
    RCONClient = None  # type: ignore
    RCON_AVAILABLE = False

logger = structlog.get_logger()


class RconClient:
    """Async wrapper for synchronous RCON client with auto-reconnection."""

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        timeout: float = 10.0,
        reconnect_delay: float = 5.0,
        max_reconnect_delay: float = 60.0,
        reconnect_backoff: float = 2.0
    ):
        """
        Initialize RCON client with reconnection support.

        Args:
            host: RCON server hostname
            port: RCON server port
            password: RCON authentication password
            timeout: Command execution timeout in seconds
            reconnect_delay: Initial delay between reconnection attempts (default: 5s)
            max_reconnect_delay: Maximum delay between reconnection attempts (default: 60s)
            reconnect_backoff: Backoff multiplier for reconnection delay (default: 2.0)
        """
        if not RCON_AVAILABLE:
            raise ImportError(
                "rcon package not installed. "
                "Install with: pip install rcon"
            )

        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout

        # Reconnection settings
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.reconnect_backoff = reconnect_backoff
        self.current_reconnect_delay = reconnect_delay

        # State
        self.client: Optional[Any] = None
        self.connected = False
        self.reconnect_task: Optional[asyncio.Task] = None
        self._should_reconnect = True  # Flag to control reconnection

    async def start(self) -> None:
        """Start RCON client with automatic reconnection."""
        self._should_reconnect = True
        await self.connect()

        # Start background reconnection task
        if self.reconnect_task is None:
            self.reconnect_task = asyncio.create_task(self._reconnection_loop())
            logger.info(
                "rcon_reconnection_enabled",
                initial_delay=self.reconnect_delay,
                max_delay=self.max_reconnect_delay,
                backoff=self.reconnect_backoff
            )

    async def stop(self) -> None:
        """Stop RCON client and cancel reconnection."""
        self._should_reconnect = False

        # Cancel reconnection task
        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass
            self.reconnect_task = None
            logger.info("rcon_reconnection_disabled")

        await self.disconnect()

    async def connect(self) -> None:
        """Establish RCON connection and authenticate."""
        if not RCON_AVAILABLE or RCONClient is None:
            logger.error("rcon_library_not_available")
            return

        try:
            # Test connection by creating and immediately closing a client
            def _test_connect():
                assert RCONClient is not None
                with RCONClient(self.host, self.port, passwd=self.password, timeout=self.timeout) as client:
                    # Connection successful if we get here
                    return True

            # Run test in executor
            result = await asyncio.to_thread(_test_connect)

            if result:
                self.connected = True
                self.current_reconnect_delay = self.reconnect_delay  # Reset backoff on success
                logger.info(
                    "rcon_connected",
                    host=self.host,
                    port=self.port
                )

        except Exception as e:
            self.connected = False
            logger.error(
                "rcon_connection_failed",
                host=self.host,
                port=self.port,
                error=str(e),
                exc_info=True
            )
            # Don't raise - let reconnection loop handle retries

    async def _reconnection_loop(self) -> None:
        """Background task that monitors connection and reconnects if needed."""
        logger.info("rcon_reconnection_loop_started")

        while self._should_reconnect:
            try:
                # Check connection every 5 seconds
                await asyncio.sleep(5.0)

                if not self.connected:
                    logger.info(
                        "rcon_attempting_reconnect",
                        next_retry_delay=self.current_reconnect_delay
                    )

                    await self.connect()

                    if not self.connected:
                        # Connection failed - wait with exponential backoff
                        await asyncio.sleep(self.current_reconnect_delay)

                        # Increase delay for next attempt (with cap)
                        self.current_reconnect_delay = min(
                            self.current_reconnect_delay * self.reconnect_backoff,
                            self.max_reconnect_delay
                        )

                        logger.debug(
                            "rcon_reconnect_backoff",
                            next_delay=self.current_reconnect_delay
                        )

            except asyncio.CancelledError:
                logger.info("rcon_reconnection_loop_cancelled")
                break
            except Exception as e:
                logger.error(
                    "rcon_reconnection_loop_error",
                    error=str(e),
                    exc_info=True
                )
                await asyncio.sleep(5.0)  # Wait before next iteration

    async def disconnect(self) -> None:
        """Close RCON connection."""
        # With connection-per-command pattern, just mark as disconnected
        self.connected = False
        logger.info("rcon_disconnected")

    async def execute(self, command: str) -> str:
        """
        Execute RCON command with automatic reconnect attempt.

        Args:
            command: RCON command to execute

        Returns:
            Command response string

        Raises:
            ConnectionError: If not connected and can't reconnect
            TimeoutError: If command times out
        """
        if not self.connected:
            # Try to reconnect once before failing
            logger.warning("rcon_not_connected_attempting_immediate_reconnect")
            await self.connect()

            if not self.connected:
                raise ConnectionError("RCON not connected - connection failed")

        if RCONClient is None:
            raise ConnectionError("RCON library not available")

        try:
            # Create new connection for each command (more reliable for remote servers)
            def _execute():
                assert RCONClient is not None
                with RCONClient(self.host, self.port, passwd=self.password, timeout=self.timeout) as client:
                    response = client.run(command)
                    return response

            # Run with asyncio timeout wrapper
            response = await asyncio.wait_for(
                asyncio.to_thread(_execute),
                timeout=self.timeout + 5.0  # Add 5 second buffer
            )

            logger.debug(
                "rcon_command_executed",
                command=command[:50],
                response_length=len(response) if response else 0
            )

            return response if response else ""

        except asyncio.TimeoutError:
            logger.error("rcon_command_timeout", command=command, timeout=self.timeout)
            raise TimeoutError(f"RCON command timed out after {self.timeout + 5.0}s: {command}")

        except Exception as e:
            # Mark as disconnected on error - will trigger reconnection
            self.connected = False
            logger.error("rcon_command_failed", command=command, error=str(e), exc_info=True)
            raise

    @property
    def is_connected(self) -> bool:
        """Check if RCON is currently connected."""
        return self.connected

    async def get_player_count(self) -> int:
        """
        Get current online player count.

        Returns:
            Number of online players, or -1 on error
        """
        try:
            response = await self.execute("/players")
            logger.debug("player_count_response", response=response)

            # Parse response - count lines with "(online)"
            if not response:
                return 0

            lines = response.split("\n")
            count = 0

            for line in lines:
                if "(online)" in line.lower():
                    count += 1

            return count

        except Exception as e:
            logger.warning("failed_to_get_player_count", error=str(e))
            return -1

    async def get_players_online(self) -> list[str]:
        """
        Get list of online player names.

        Returns:
            List of player names
        """
        try:
            response = await self.execute("/players")
            logger.debug("players_online_response", response=response)

            if not response:
                return []

            # Parse player list from response
            players: list[str] = []
            lines = response.split("\n")

            for line in lines:
                line = line.strip()

                # Look for lines with "(online)"
                if "(online)" in line.lower():
                    # Extract player name before "(online)"
                    player_name = line.split("(online)")[0].strip()

                    # Remove any leading markers like "-" or numbers
                    player_name = player_name.lstrip("-").strip()

                    if player_name and not player_name.startswith("Player"):
                        players.append(player_name)

            return players

        except Exception as e:
            logger.warning("failed_to_get_players", error=str(e))
            return []

    async def get_players(self) -> list[str]:
        """Alias for get_players_online() for compatibility."""
        return await self.get_players_online()

    async def get_server_time(self) -> str:
        """
        Get current in-game time.

        Returns:
            Game time string
        """
        try:
            response = await self.execute("/time")
            logger.debug("server_time_response", response=response)

            if response and response.strip():
                return response.strip()

            return "Unknown"

        except Exception as e:
            logger.warning("failed_to_get_server_time", error=str(e))
            return "Unknown"


class RconStatsCollector:
    """Periodically collect and post server statistics."""

    def __init__(
        self,
        rcon_client: RconClient,
        discord_client: Any,
        interval: int | float = 300
    ):
        """
        Initialize stats collector.

        Args:
            rcon_client: Connected RCON client
            discord_client: Discord client for posting stats
            interval: Collection interval in seconds (default: 5 minutes)
        """
        self.rcon_client = rcon_client
        self.discord_client = discord_client
        self.interval = interval
        self.running = False
        self.task: Optional[asyncio.Task[None]] = None
        
        logger.info(
            "stats_collector_initialized",
            interval=interval,
            rcon_connected=rcon_client.is_connected,
            discord_connected=getattr(discord_client, 'is_connected', None)
        )

    async def start(self) -> None:
        """Start periodic stats collection."""
        if self.running:
            logger.warning("stats_collector_already_running")
            return

        self.running = True
        self.task = asyncio.create_task(self._collection_loop())
        logger.info(
            "stats_collector_started", 
            interval=self.interval,
            rcon_connected=self.rcon_client.is_connected,
            discord_connected=getattr(self.discord_client, 'is_connected', None)
        )

    async def stop(self) -> None:
        """Stop stats collection."""
        if not self.running:
            logger.debug("stats_collector_stop_called_but_not_running")
            return

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.debug("stats_collector_task_cancelled")
                pass

        logger.info("stats_collector_stopped")

    async def _collection_loop(self) -> None:
        """Main collection loop."""
        logger.info("stats_collection_loop_started")
        iteration = 0
        
        while self.running:
            iteration += 1
            try:
                logger.debug(
                    "stats_collection_iteration_starting",
                    iteration=iteration,
                    interval=self.interval
                )
                
                await self._collect_and_post()
                
                logger.debug(
                    "stats_collection_iteration_complete",
                    iteration=iteration,
                    next_collection_in=self.interval
                )
                
            except Exception as e:
                logger.error(
                    "stats_collection_error",
                    iteration=iteration,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True
                )
            
            # Wait for next interval
            if self.running:  # Check if still running before sleeping
                logger.debug(
                    "stats_collector_sleeping",
                    duration=self.interval,
                    next_iteration=iteration + 1
                )
                await asyncio.sleep(self.interval)
        
        logger.info("stats_collection_loop_exited", total_iterations=iteration)

    async def _collect_and_post(self) -> None:
        """Collect stats and post to Discord."""
        try:
            # Gather stats
            player_count = await self.rcon_client.get_player_count()
            players = await self.rcon_client.get_players_online()
            server_time = await self.rcon_client.get_server_time()

            # Format message
            message = self._format_stats(player_count, players, server_time)

            # Post to Discord
            await self.discord_client.send_message(message)

            logger.info(
                "stats_posted",
                player_count=player_count,
                players=len(players)
            )

        except Exception as e:
            logger.error("failed_to_post_stats", error=str(e))

    def _format_stats(
        self,
        player_count: int,
        players: list[str],
        server_time: str
    ) -> str:
        """
        Format stats as Discord message.

        Args:
            player_count: Number of online players
            players: List of player names
            server_time: Current game time

        Returns:
            Formatted message string
        """
        lines = [
            "📊 **Server Stats**",
            f"👥 Players Online: {player_count}",
        ]

        if players:
            lines.append(f"📝 {', '.join(players)}")

        lines.append(f"⏰ Game Time: {server_time}")

        return "\n".join(lines)

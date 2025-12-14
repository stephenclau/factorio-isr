# ════════════════════════════════════════════════════════════════════════════
# FIXTURES: Type-Safe Mocks with Clear Contracts
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_interaction() -> MagicMock:
    """Mock Discord interaction with required attributes.
    
    Type Contract:
    - client: object with server_manager, user_context
    - response: MagicMock with send_message, defer methods
    - followup: MagicMock with send method
    - user: Mock with name, id
    - guild: Mock with id
    
    Returns:
        MagicMock configured as Discord interaction
    """
    interaction = MagicMock(spec=discord.Interaction)
    interaction.client = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.user = Mock(id=12345, name="TestUser")
    interaction.guild = Mock(id=67890)
    return interaction


@pytest.fixture
def mock_embed_builder() -> MagicMock:
    """Mock EmbedBuilder with type-safe methods.
    
    Type Contract:
    - error_embed(message: str) -> discord.Embed
    - success_embed(...) -> discord.Embed
    - info_embed(...) -> discord.Embed
    
    Returns:
        MagicMock configured as EmbedBuilder class
    """
    builder = MagicMock()
    builder.error_embed = MagicMock(return_value=MagicMock(spec=discord.Embed))
    builder.success_embed = MagicMock(return_value=MagicMock(spec=discord.Embed))
    builder.info_embed = MagicMock(return_value=MagicMock(spec=discord.Embed))
    return builder


@pytest.fixture
def mock_command_result() -> MagicMock:
    """Mock CommandResult object.
    
    Type Contract:
    - success: bool
    - embed: Optional[discord.Embed]
    - error_embed: Optional[discord.Embed]
    - ephemeral: bool
    
    Returns:
        MagicMock configured as CommandResult
    """
    result = MagicMock()
    result.success = True
    result.embed = MagicMock(spec=discord.Embed)
    result.error_embed = None
    result.ephemeral = False
    return result


@pytest.fixture
def mock_bot() -> MagicMock:
    """Mock DiscordBot with dependencies.
    
    Type Contract:
    - user_context: object with user methods
    - server_manager: object with list_servers method
    - tree: app_commands tree
    
    Returns:
        MagicMock configured as bot instance
    """
    bot = MagicMock()
    bot.user_context = MagicMock()
    bot.server_manager = MagicMock()
    bot.server_manager.list_servers = MagicMock(return_value={})
    bot.tree = MagicMock()
    bot.tree.add_command = MagicMock()
    return bot

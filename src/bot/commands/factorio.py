    @factorio_group.command(name="seed", description="Show the map seed")
    async def seed_command(interaction: discord.Interaction) -> None:
        """Display the current map seed."""
        is_limited, retry = QUERY_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        rcon_client = bot.get_rcon_for_user(interaction.user.id)
        if rcon_client is None or not rcon_client.is_connected:
            server_name = bot.get_server_display_name(interaction.user.id)
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            resp = await rcon_client.execute('/sc rcon.print(game.surfaces["nauvis"].map_gen_settings.seed)')
            embed = EmbedBuilder.info_embed(
                title="🌱 Map Seed",
                message=f"Seed: `{resp.strip()}`\n\nUse this seed to generate an identical map.",
            )
            await interaction.followup.send(embed=embed)
            logger.info("seed_requested", moderator=interaction.user.name)
        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Failed to get map seed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error("seed_command_failed", error=str(e))
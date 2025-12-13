"""Complete research_command implementation for factorio.py (Multi-Force v2)

COPY THIS ENTIRE BLOCK AND PASTE INTO src/bot/commands/factorio.py
Replace existing research_command function (~line 1600-1630)

Do NOT include the triple quotes or docstring when copying to factorio.py
"""

    @factorio_group.command(
        name="research",
        description="Manage technology research (Coop: player force, PvP: specify force)"
    )
    @app_commands.describe(
        force='Force name (e.g., "player", "enemy"). Defaults to "player".',
        action='Action: "all", tech name, "undo", or empty to display status',
        technology='Technology name (for undo operations with specific tech)',
    )
    async def research_command(
        interaction: discord.Interaction,
        force: Optional[str] = None,
        action: Optional[str] = None,
        technology: Optional[str] = None,
    ) -> None:
        """Manage technology research with multi-force support.
        
        Operational modes:
        - Display: /factorio research [force] (shows research progress)
        - Research All: /factorio research [force] all (unlock all technologies)
        - Research Single: /factorio research [force] <tech-name> (complete tech)
        - Undo Single: /factorio research [force] undo <tech-name> (revert tech)
        - Undo All: /factorio research [force] undo all (revert all tech)
        
        Coop (default force="player"):
        - /factorio research
        - /factorio research all
        - /factorio research automation-2
        - /factorio research undo automation-2
        - /factorio research undo all
        
        PvP (force-specific, e.g., force="enemy"):
        - /factorio research enemy
        - /factorio research enemy all
        - /factorio research enemy automation-2
        - /factorio research enemy undo automation-2
        - /factorio research enemy undo all
        """
        is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
        if is_limited:
            embed = EmbedBuilder.cooldown_embed(retry)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)

        if rcon_client is None or not rcon_client.is_connected:
            embed = EmbedBuilder.error_embed(
                f"RCON not available for {server_name}.\n\n"
                f"Use `/factorio servers` to see available servers."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # ════════════════════════════════════════════════════════════════
            # PARAMETER RESOLUTION
            # ════════════════════════════════════════════════════════════════
            # Default force to "player" if not provided (Coop mode)
            target_force = (force.lower().strip() if force else None) or "player"

            # ════════════════════════════════════════════════════════════════
            # MODE 1: DISPLAY STATUS (No arguments)
            # ════════════════════════════════════════════════════════════════
            if action is None:
                # Count researched vs total technologies
                resp = await rcon_client.execute(
                    f'/sc '
                    f'local researched = 0; '
                    f'local total = 0; '
                    f'for _, tech in pairs(game.forces["{target_force}"].technologies) do '
                    f' total = total + 1; '
                    f' if tech.researched then researched = researched + 1 end; '
                    f'end; '
                    f'rcon.print(string.format("%d/%d", researched, total))'
                )

                researched_count = "0/0"
                try:
                    parts = resp.strip().split("/")
                    if len(parts) == 2:
                        researched_count = resp.strip()
                except (ValueError, IndexError):
                    logger.warning(
                        "research_status_parse_failed",
                        response=resp,
                        force=target_force,
                    )

                embed = EmbedBuilder.info_embed(
                    title="🔬 Technology Status",
                    message=f"Force: **{target_force}**\n"
                            f"Technologies researched: **{researched_count}**\n\n"
                            f"Use `/factorio research {target_force if target_force != 'player' else ''}all` to research all.\n"
                            f"Or `/factorio research {target_force + ' ' if target_force != 'player' else ''}<tech-name>` for specific tech.",
                )
                await interaction.followup.send(embed=embed)
                logger.info(
                    "research_status_checked",
                    user=interaction.user.name,
                    force=target_force,
                )
                return

            # ════════════════════════════════════════════════════════════════
            # MODE 2: RESEARCH ALL TECHNOLOGIES
            # ════════════════════════════════════════════════════════════════
            action_lower = action.lower().strip()

            if action_lower == "all" and technology is None:
                resp = await rcon_client.execute(
                    f'/sc game.forces["{target_force}"].research_all_technologies(); '
                    f'rcon.print("All technologies researched")'
                )

                embed = EmbedBuilder.info_embed(
                    title="🔬 All Technologies Researched",
                    message=f"Force: **{target_force}**\n\n"
                            f"All technologies have been instantly unlocked!\n\n"
                            f"{target_force.capitalize()} force can now access all previously locked content.",
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS
                await interaction.followup.send(embed=embed)

                logger.info(
                    "all_technologies_researched",
                    moderator=interaction.user.name,
                    force=target_force,
                )
                return

            # ════════════════════════════════════════════════════════════════
            # MODE 3: UNDO OPERATIONS
            # ════════════════════════════════════════════════════════════════
            if action_lower == "undo":
                # MODE 3a: UNDO ALL
                if technology is None or technology.lower().strip() == "all":
                    resp = await rcon_client.execute(
                        f'/sc '
                        f'for _, tech in pairs(game.forces["{target_force}"].technologies) do '
                        f' tech.researched = false; '
                        f'end; '
                        f'rcon.print("All technologies reverted")'
                    )

                    embed = EmbedBuilder.info_embed(
                        title="⏮️ All Technologies Reverted",
                        message=f"Force: **{target_force}**\n\n"
                                f"All technology research has been undone!\n\n"
                                f"{target_force.capitalize()} force must re-research technologies from scratch.",
                    )
                    embed.color = EmbedBuilder.COLOR_WARNING
                    await interaction.followup.send(embed=embed)

                    logger.info(
                        "all_technologies_reverted",
                        moderator=interaction.user.name,
                        force=target_force,
                    )
                    return

                # MODE 3b: UNDO SINGLE TECHNOLOGY
                tech_name = technology.strip()
                try:
                    resp = await rcon_client.execute(
                        f'/sc game.forces["{target_force}"].technologies["{tech_name}"].researched = false; '
                        f'rcon.print("Technology reverted: {tech_name}")'
                    )

                    embed = EmbedBuilder.info_embed(
                        title="⏮️ Technology Reverted",
                        message=f"Force: **{target_force}**\n"
                                f"Technology: **{tech_name}**\n\n"
                                f"Technology has been undone.",
                    )
                    embed.color = EmbedBuilder.COLOR_WARNING
                    await interaction.followup.send(embed=embed)

                    logger.info(
                        "technology_reverted",
                        technology=tech_name,
                        moderator=interaction.user.name,
                        force=target_force,
                    )
                    return

                except Exception as e:
                    embed = EmbedBuilder.error_embed(
                        f"Failed to revert technology: {str(e)}\n\n"
                        f"Force: `{target_force}`\n"
                        f"Technology: `{tech_name}`\n\n"
                        f"Verify the force exists and technology name is correct\n"
                        f"(e.g., automation-2, logistics-3, steel-processing)"
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    logger.error(
                        "research_undo_failed",
                        technology=tech_name,
                        force=target_force,
                        error=str(e),
                    )
                    return

            # ════════════════════════════════════════════════════════════════
            # MODE 4: RESEARCH SINGLE TECHNOLOGY
            # ════════════════════════════════════════════════════════════════
            if technology is None:
                # User provided action but no technology
                # Assume action is the technology name
                tech_name = action_lower
            else:
                tech_name = technology.strip()

            try:
                resp = await rcon_client.execute(
                    f'/sc game.forces["{target_force}"].technologies["{tech_name}"].researched = true; '
                    f'rcon.print("Technology researched: {tech_name}")'
                )

                embed = EmbedBuilder.info_embed(
                    title="🔬 Technology Researched",
                    message=f"Force: **{target_force}**\n"
                            f"Technology: **{tech_name}**\n\n"
                            f"Technology has been researched.",
                )
                embed.color = EmbedBuilder.COLOR_SUCCESS
                await interaction.followup.send(embed=embed)

                logger.info(
                    "technology_researched",
                    technology=tech_name,
                    moderator=interaction.user.name,
                    force=target_force,
                )

            except Exception as e:
                embed = EmbedBuilder.error_embed(
                    f"Failed to research technology: {str(e)}\n\n"
                    f"Force: `{target_force}`\n"
                    f"Technology: `{tech_name}`\n\n"
                    f"Valid examples: automation-2, logistics-3, steel-processing, electric-furnace\n\n"
                    f"Use `/factorio research {target_force if target_force != 'player' else ''}` to see progress."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.error(
                    "research_command_failed",
                    technology=tech_name,
                    force=target_force,
                    error=str(e),
                )

        except Exception as e:
            embed = EmbedBuilder.error_embed(f"Research command failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error(
                "research_command_failed",
                error=str(e),
                force=force,
                action=action,
                technology=technology,
            )

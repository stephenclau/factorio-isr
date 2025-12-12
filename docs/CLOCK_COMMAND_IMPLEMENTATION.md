# Clock Command Implementation - Code Review Reference

## Overview
This document provides the complete implementation for the `/clock` command refactoring that replaces the incorrect `/time` command.

## Current Problem
- `/time` uses Factorio RCON `/time` which returns total save playtime
- Not the in-game clock (daytime cycle 0.0-1.0)
- Semantically incorrect for game time control

## Solution: clock_command Implementation

```python
@factorio_group.command(name="clock", description="Set or display game daytime (0.0-1.0 scale or eternal day/night)")
@app_commands.describe(
    value="'day'/'night'/'eternal-day'/'eternal-night' or float 0.0-1.0 (0=midnight, 0.5=noon), or leave empty to view"
)
async def clock_command(interaction: discord.Interaction, value: Optional[str] = None) -> None:
    """Set or display the game clock with optional freeze_daytime.
    
    Parameters:
    - No argument: Show current daytime
    - 'day' or 'eternal-day': Set daytime to noon and freeze it
    - 'night' or 'eternal-night': Set daytime to midnight and freeze it  
    - Float 0.0-1.0: Set daytime (0.0=midnight, 0.5=noon, 1.0=next midnight)
    """
    is_limited, retry = ADMIN_COOLDOWN.is_rate_limited(interaction.user.id)
    if is_limited:
        embed = EmbedBuilder.cooldown_embed(retry)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()

    rcon_client = bot.user_context.get_rcon_for_user(interaction.user.id)
    if rcon_client is None or not rcon_client.is_connected:
        server_name = bot.user_context.get_server_display_name(interaction.user.id)
        embed = EmbedBuilder.error_embed(
            f"RCON not available for {server_name}.\n\n"
            f"Use `/factorio servers` to see available servers."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    try:
        if value is None:
            # Display current daytime
            resp = await rcon_client.execute(
                '/sc local daytime = game.surfaces["nauvis"].daytime; '
                'local hours = math.floor(daytime * 24); '
                'local minutes = math.floor((daytime * 24 - hours) * 60); '
                'rcon.print(string.format("Current daytime: %.2f (🕐 %02d:%02d)", daytime, hours, minutes))'
            )
            embed = EmbedBuilder.info_embed(
                title="🕐 Current Game Clock",
                message=resp,
            )
        else:
            # Parse value
            value_lower = value.lower().strip()
            
            if value_lower in ["day", "eternal-day"]:
                # Eternal day: daytime = 0.5, freeze_daytime = true
                resp = await rcon_client.execute(
                    '/sc game.surfaces["nauvis"].daytime = 0.5; '
                    'game.surfaces["nauvis"].freeze_daytime = 0.5; '
                    'rcon.print("☀️ Set to eternal day (12:00)")'
                )
                embed = EmbedBuilder.info_embed(
                    title="☀️ Eternal Day Set",
                    message="Game time is now permanently frozen at noon (12:00)\n\nServer response:\n" + resp,
                )
                logger.info("eternal_day_set", moderator=interaction.user.name)
                
            elif value_lower in ["night", "eternal-night"]:
                # Eternal night: daytime = 0.0, freeze_daytime = true  
                resp = await rcon_client.execute(
                    '/sc game.surfaces["nauvis"].daytime = 0.0; '
                    'game.surfaces["nauvis"].freeze_daytime = 0.0; '
                    'rcon.print("🌙 Set to eternal night (00:00)")'
                )
                embed = EmbedBuilder.info_embed(
                    title="🌙 Eternal Night Set",
                    message="Game time is now permanently frozen at midnight (00:00)\n\nServer response:\n" + resp,
                )
                logger.info("eternal_night_set", moderator=interaction.user.name)
                
            else:
                # Parse as float
                try:
                    daytime_value = float(value_lower)
                    if not 0.0 <= daytime_value <= 1.0:
                        raise ValueError("Value must be between 0.0 and 1.0")
                    
                    # Set daytime and unfreeze time progression
                    resp = await rcon_client.execute(
                        f'/sc game.surfaces["nauvis"].daytime = {daytime_value}; '
                        f'game.surfaces["nauvis"].freeze_daytime = nil; '
                        f'local hours = math.floor({daytime_value} * 24); '
                        f'local minutes = math.floor(({daytime_value} * 24 - hours) * 60); '
                        f'rcon.print(string.format("Set daytime to %.2f (🕐 %02d:%02d)", {daytime_value}, hours, minutes))'
                    )
                    
                    time_desc = "noon" if abs(daytime_value - 0.5) < 0.05 else "midnight" if daytime_value < 0.05 else f"{daytime_value:.2f}"
                    embed = EmbedBuilder.info_embed(
                        title="🕐 Game Clock Updated",
                        message=f"Game time set to: **{time_desc}**\n\nServer response:\n{resp}",
                    )
                    logger.info("daytime_set", value=daytime_value, moderator=interaction.user.name)
                
                except ValueError as e:
                    embed = EmbedBuilder.error_embed(
                        f"Invalid time value: {value}\n\n"
                        f"Valid formats:\n"
                        f"- 'day' or 'eternal-day' → Eternal noon\n"
                        f"- 'night' or 'eternal-night' → Eternal midnight\n"
                        f"- 0.0-1.0 → Custom time (0=midnight, 0.5=noon)"
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

        embed.color = EmbedBuilder.COLOR_SUCCESS
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        embed = EmbedBuilder.error_embed(f"Clock command failed: {str(e)}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.error("clock_command_failed", error=str(e), value=value)
```

## Integration Instructions

1. **Location**: `src/bot/commands/factorio.py`
2. **Section**: GAME CONTROL COMMANDS (3/25)
3. **Replace**: `time_command` function with `clock_command` function
4. **Update**: Help text in `help_command()` to reflect `/clock` instead of `/time`
5. **Update**: Module docstring to show `clock` instead of `time` in the command list

## Test Scenarios

| Input | Output | Lua Effect |
|-------|--------|----------|
| `/factorio clock` | Show current time | Read-only |
| `/factorio clock day` | Frozen at 12:00 | `freeze_daytime = 0.5` |
| `/factorio clock night` | Frozen at 00:00 | `freeze_daytime = 0.0` |
| `/factorio clock 0.75` | Set to 18:00 | `freeze_daytime = nil` |

## Lua Safety Notes

✅ **Safe Pattern**: Uses f-string with validated float  
```lua
f'/sc game.surfaces["nauvis"].daytime = {daytime_value}; ...'
```

✅ **No Injection Risk**: Float value is validated before Lua execution  
```python
if not 0.0 <= daytime_value <= 1.0:
    raise ValueError(...)
```

## Logging Events

- `eternal_day_set`: User set eternal day
- `eternal_night_set`: User set eternal night
- `daytime_set`: User set custom daytime value
- `clock_command_failed`: Command execution error

---

**Ready for review and implementation in factorio.py**

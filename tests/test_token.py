# quick_token_test.py
import asyncio
import discord
from pathlib import Path

async def test():
    token_path = Path(".secrets/DISCORD_BOT_TOKEN.txt")
    token = token_path.read_text().strip()
    
    print(f"Token length: {len(token)}")
    print(f"Token preview: {token[:20]}...")
    
    intents = discord.Intents.default()
    intents.message_content = True
    
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"✅ SUCCESS! Logged in as {client.user}")
        await client.close()  # This properly closes everything
    
    try:
        await asyncio.wait_for(client.start(token), timeout=10.0)
    except discord.errors.LoginFailure as e:
        print(f"❌ Login failed: {e}")
    except asyncio.TimeoutError:
        print(f"❌ Timed out")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
    finally:
        if not client.is_closed():
            await client.close()

asyncio.run(test())

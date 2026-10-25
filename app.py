import os
import re
import discord
import aiohttp
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
LINK_API_URL = os.getenv("LINK_API_URL", "").rstrip("/")
API_SECRET = os.getenv("API_SECRET", "")
WELCOME_CHANNEL_ID = 1562478859956391996

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)


async def api_request(session, endpoint, payload=None):
    async with session.post(
        f"{LINK_API_URL}/{endpoint}",
        json=payload or {},
        headers={"X-API-Secret": API_SECRET}
    ) as response:
        data = await response.json(content_type=None)
        if response.status != 200:
            raise RuntimeError(f"{endpoint}: HTTP {response.status}: {data}")
        return data


def is_mc_verified(member):
    return any(role.name == "MC Verified" for role in member.roles)


def verified_only_blocked(interaction):
    return (
        isinstance(interaction.user, discord.Member)
        and is_mc_verified(interaction.user)
    )


async def reject_verified(interaction):
    if verified_only_blocked(interaction):
        await interaction.response.send_message(
            "✅ Your Minecraft account is already verified. "
            "You cannot use `/link` or `/verify` again.",
            ephemeral=True
        )
        return True
    return False


@client.event
async def on_ready():
    try:
        await tree.sync()
        print("Slash commands synced!")
    except Exception as e:
        print(f"Command sync error: {e}")

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Minecraft")
    )
    if not process_verifications.is_running():
        process_verifications.start()
    print(f"Bot online: {client.user}")


@client.event
async def on_member_join(member):
    roles = [
        discord.utils.get(member.guild.roles, name=name)
        for name in ("Member", "Non MC Verified")
    ]
    roles = [role for role in roles if role]
    try:
        if roles:
            await member.add_roles(*roles, reason="New member")
    except discord.HTTPException as e:
        print(f"Join role error: {e}")

    channel = client.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(WELCOME_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            print("Welcome channel unavailable")
            return

    embed = discord.Embed(
        title="💎 WELCOME TO NAGATO MC! 🎉",
        description=(
            f"Hey {member.mention}! 👋\n\n"
            "⛏️ Welcome to our Minecraft community!\n"
            "✨ Get ready for adventures and fun!\n\n"
            f"👥 You are member **#{member.guild.member_count}**!\n\n"
            "💚 Enjoy your stay, warrior!"
        ),
        color=discord.Color.from_rgb(0, 255, 170)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    if member.guild.icon:
        embed.set_author(
            name="Nagato MC Community",
            icon_url=member.guild.icon.url
        )
        embed.set_image(url=member.guild.icon.url)
    embed.set_footer(text="Nagato MC • Minecraft Community")

    try:
        await channel.send(
            content=f"🎊 Welcome {member.mention}!",
            embed=embed
        )
    except discord.HTTPException as e:
        print(f"Welcome message error: {e}")


@tree.command(name="link", description="Start linking your Minecraft username")
@discord.app_commands.describe(username="Your exact Minecraft username")
async def link(interaction: discord.Interaction, username: str):
    if await reject_verified(interaction):
        return

    if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", username):
        await interaction.response.send_message(
            "❌ Enter a valid Minecraft username (3–16 letters, numbers, or underscores).",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    if not LINK_API_URL or not API_SECRET:
        await interaction.followup.send("❌ Link API is not configured.", ephemeral=True)
        return

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        ) as session:
            data = await api_request(
                session,
                "create-link-request",
                {
                    "discord_id": str(interaction.user.id),
                    "username": username
                }
            )

        await interaction.followup.send(
            f"✅ Request created for **{username}**.\n"
            "Now join the Minecraft server. Your code will appear in chat "
            "and the action bar. Then use `/verify CODE` here.\n"
            "⏳ Request expires in 5 minutes.",
            ephemeral=True
        )
    except Exception as e:
        print(f"Link request error: {e}")
        await interaction.followup.send(
            "❌ Could not start linking. Try again later.",
            ephemeral=True
        )


@tree.command(name="verify", description="Verify your Minecraft join code")
@discord.app_commands.describe(code="The code shown in Minecraft")
async def verify(interaction: discord.Interaction, code: str):
    if await reject_verified(interaction):
        return

    code = code.strip().upper()
    if not re.fullmatch(r"[A-F0-9]{8}", code):
        await interaction.response.send_message(
            "❌ Invalid code format. Enter the 8-character code from Minecraft.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        ) as session:
            data = await api_request(session, "verify-code", {"code": code})

        await interaction.followup.send(
            "✅ Code accepted! Your Discord role will update shortly.",
            ephemeral=True
        )
    except Exception as e:
        print(f"Verification error: {e}")
        await interaction.followup.send(
            "❌ Code invalid, expired, or already used. Join Minecraft again for a new code.",
            ephemeral=True
        )


@tasks.loop(seconds=15)
async def process_verifications():
    if not LINK_API_URL or not API_SECRET:
        return

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        ) as session:
            result = await api_request(session, "pending-verifications")

            for item in result.get("verifications", []):
                discord_id = str(item.get("discord_id", ""))
                minecraft_uuid = str(item.get("minecraft_uuid", ""))
                if not discord_id.isdigit() or not minecraft_uuid:
                    continue

                channel = client.get_channel(WELCOME_CHANNEL_ID)
                if channel is None:
                    channel = await client.fetch_channel(WELCOME_CHANNEL_ID)
                guild = channel.guild

                try:
                    member = guild.get_member(int(discord_id))
                    if member is None:
                        member = await guild.fetch_member(int(discord_id))
                except discord.NotFound:
                    continue

                verified = discord.utils.get(guild.roles, name="MC Verified")
                unverified = discord.utils.get(guild.roles, name="Non MC Verified")
                if verified is None:
                    print("Missing MC Verified role")
                    continue

                try:
                    if verified not in member.roles:
                        await member.add_roles(verified, reason="Minecraft verified")
                    if unverified and unverified in member.roles:
                        await member.remove_roles(unverified, reason="Minecraft verified")

                    await api_request(
                        session,
                        "ack-verification",
                        {
                            "discord_id": discord_id,
                            "minecraft_uuid": minecraft_uuid
                        }
                    )
                except discord.HTTPException as e:
                    print(f"Role update error: {e}")

    except Exception as e:
        print(f"Verification polling error: {e}")


@process_verifications.before_loop
async def before_poll():
    await client.wait_until_ready()


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing from environment")

client.run(TOKEN)

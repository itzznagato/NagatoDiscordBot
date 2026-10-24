
import os
import discord
import aiohttp
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
LINK_API_URL = os.getenv("LINK_API_URL", "").rstrip("/")
API_SECRET = os.getenv("API_SECRET", "")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

WELCOME_CHANNEL_ID = 1562478859956391996


async def api_request(session, endpoint, payload=None):
    headers = {"X-API-Secret": API_SECRET}

    async with session.post(
        f"{LINK_API_URL}/{endpoint}",
        json=payload or {},
        headers=headers
    ) as response:
        data = await response.json(content_type=None)

        if response.status != 200:
            raise RuntimeError(
                f"API {endpoint} returned HTTP {response.status}: {data}"
            )

        return data


@client.event
async def on_ready():
    try:
        await tree.sync()
        print("Slash commands synced!")
    except Exception as error:
        print(f"Command sync error: {error}")

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Minecraft")
    )

    if not process_verifications.is_running():
        process_verifications.start()

    print(f"Bot online: {client.user}")


@client.event
async def on_member_join(member):
    # Give the two default roles first.
    member_role = discord.utils.get(
        member.guild.roles, name="Member"
    )
    unverified_role = discord.utils.get(
        member.guild.roles, name="Non MC Verified"
    )

    roles_to_add = [
        role for role in (member_role, unverified_role)
        if role is not None
    ]

    try:
        if roles_to_add:
            await member.add_roles(
                *roles_to_add,
                reason="Automatic roles for new member"
            )
    except discord.Forbidden:
        print("Missing permission to assign join roles!")
    except discord.HTTPException as error:
        print(f"Could not assign join roles: {error}")

    # Keep the existing welcome message.
    channel = client.get_channel(WELCOME_CHANNEL_ID)

    if channel is None:
        try:
            channel = await client.fetch_channel(WELCOME_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            print("Welcome channel not found or inaccessible!")
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
        embed.set_image(url=member.guild.icon.url)
        embed.set_author(
            name="Nagato MC Community",
            icon_url=member.guild.icon.url
        )

    embed.set_footer(text="Nagato MC • Minecraft Community")

    try:
        await channel.send(
            content=f"🎊 Welcome {member.mention}!",
            embed=embed
        )
        print(f"Welcome message sent for {member}")
    except discord.Forbidden:
        print("Missing channel permissions!")
    except discord.HTTPException as error:
        print(f"Discord error: {error}")


@tree.command(
    name="link",
    description="Get a one-time code to link your Minecraft account"
)
async def link(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not LINK_API_URL or not API_SECRET:
        await interaction.followup.send(
            "❌ Link API settings are missing. Contact an administrator.",
            ephemeral=True
        )
        return

    payload = {"discord_id": str(interaction.user.id)}

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = await api_request(session, "create-code", payload)

        await interaction.followup.send(
            f"🔗 **Your Nagato MC link code**\n\n"
            f"```{data['code']}```\n"
            f"⏳ Expires in {data['expires_in'] // 60} minutes.\n\n"
            "Next, enter `/link CODE` in Minecraft.",
            ephemeral=True
        )

    except Exception as error:
        print(f"Link API connection error: {error}")
        await interaction.followup.send(
            "❌ Could not create a link code. Please try again later.",
            ephemeral=True
        )


@tasks.loop(seconds=10)
async def process_verifications():
    if not LINK_API_URL or not API_SECRET:
        return

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            result = await api_request(
                session, "pending-verifications"
            )

            for item in result.get("verifications", []):
                discord_id = str(item.get("discord_id", ""))
                minecraft_uuid = str(item.get("minecraft_uuid", ""))

                if not discord_id or not minecraft_uuid:
                    continue

                # Find the server using the existing welcome channel.
                channel = client.get_channel(WELCOME_CHANNEL_ID)

                if channel is None:
                    channel = await client.fetch_channel(
                        WELCOME_CHANNEL_ID
                    )

                guild = channel.guild
                member = guild.get_member(int(discord_id))

                if member is None:
                    try:
                        member = await guild.fetch_member(
                            int(discord_id)
                        )
                    except discord.NotFound:
                        print(
                            f"Linked Discord member {discord_id} "
                            "is no longer in the server."
                        )
                        # Keep the queue item for manual handling.
                        continue

                verified_role = discord.utils.get(
                    guild.roles, name="MC Verified"
                )
                unverified_role = discord.utils.get(
                    guild.roles, name="Non MC Verified"
                )

                if verified_role is None:
                    print("Role 'MC Verified' was not found.")
                    continue

                try:
                    if verified_role not in member.roles:
                        await member.add_roles(
                            verified_role,
                            reason="Minecraft account linked successfully"
                        )

                    if (
                        unverified_role is not None
                        and unverified_role in member.roles
                    ):
                        await member.remove_roles(
                            unverified_role,
                            reason="Minecraft account linked successfully"
                        )

                    await api_request(
                        session,
                        "ack-verification",
                        {
                            "discord_id": discord_id,
                            "minecraft_uuid": minecraft_uuid
                        }
                    )

                    print(
                        f"Verified Minecraft link for Discord "
                        f"member {discord_id}"
                    )

                except discord.Forbidden:
                    print(
                        "Missing Manage Roles permission or the bot's "
                        "role is too low."
                    )
                except discord.HTTPException as error:
                    print(f"Discord role update failed: {error}")

    except Exception as error:
        print(f"Verification polling error: {error}")


@process_verifications.before_loop
async def before_process_verifications():
    await client.wait_until_ready()


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from environment")

client.run(TOKEN)
    

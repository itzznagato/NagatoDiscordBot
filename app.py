
import os
import discord
import aiohttp
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
    print(f"Bot online: {client.user}")


@client.event
async def on_member_join(member):
    channel = client.get_channel(WELCOME_CHANNEL_ID)

    if channel is None:
        print("Welcome channel not found!")
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

    headers = {"X-API-Secret": API_SECRET}
    payload = {"discord_id": str(interaction.user.id)}

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{LINK_API_URL}/create-code",
                json=payload,
                headers=headers
            ) as response:
                data = await response.json(content_type=None)

                if response.status != 200:
                    print(f"Create-code API error: {response.status}")
                    await interaction.followup.send(
                        "❌ Could not create a link code. Please try again later.",
                        ephemeral=True
                    )
                    return

        await interaction.followup.send(
            f"🔗 **Your Nagato MC link code**\n\n"
            f"```{data['code']}```\n"
            f"⏳ Expires in {data['expires_in'] // 60} minutes.\n\n"
            "Next, enter `/link CODE` in Minecraft if the server plugin supports it.",
            ephemeral=True
        )

    except Exception as error:
        print(f"Link API connection error: {error}")
        await interaction.followup.send(
            "❌ Could not reach the link service. Please try again later.",
            ephemeral=True
        )


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

client.run(TOKEN)

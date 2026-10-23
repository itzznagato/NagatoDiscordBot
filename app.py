
import discord

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)

WELCOME_CHANNEL_ID = 1562478859956391996


@client.event
async def on_ready():
    print(f"Bot online: {client.user}")

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Minecraft")
    )


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

    # New member's Discord avatar
    embed.set_thumbnail(url=member.display_avatar.url)

    # Automatically use your Discord server icon
    if member.guild.icon:
        embed.set_image(url=member.guild.icon.url)
        embed.set_author(
            name="Nagato MC Community",
            icon_url=member.guild.icon.url
        )

    embed.set_footer(
        text="Nagato MC • Minecraft Community"
    )

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


client.run("BOT_TOKEN")
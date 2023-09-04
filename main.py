# ------------------- Imports -------------------
from interactions import Embed
import json
import os
import asyncio
import aiohttp
import base64
import re
import coc
import datetime
from pytz import utc
from coc import GatewayError
import traceback
from dotenv import load_dotenv
from interactions import (Client, listen, slash_command, slash_option,
                          Embed, OptionType, Button, ActionRow, ButtonStyle, SlashContext, StringSelectMenu, ComponentContext, component_callback)
from interactions.api.events import Component
from bot import bot, coc_client


# ------------------- Load Environment Variables -------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
Email = os.getenv("Email")
Password = os.getenv("Password")

# ------------------- Initialize Global Variables -------------------
embed_colour = 0x00ff00  # Default to green
player_tags = {}  # Initialize empty dictionary for player tags
clan_data = {}
COLOURS = {
    "Red": 0xFF0000,
    "Blue": 0x0000FF,
    "White": 0xFFFFFF,
    "Black": 0x000000,
    "Green": 0x00FF00,
    "Yellow": 0xFFFF00
}

# ------------------- Utility Functions -------------------
# JSON Handling


def load_clan_data():
    with open('clans_data.json', 'r') as f:
        return json.load(f)


try:
    clan_data = load_clan_data()
    if not isinstance(clan_data, dict):
        clan_data = {}
except FileNotFoundError:
    clan_data = {}


def save_clan_data(data):
    serializable_data = {}
    for key, value in data.items():
        if isinstance(value, dict):
            serializable_data[key] = {}
            for sub_key, sub_value in value.items():

                if hasattr(sub_value, 'id'):

                    serializable_data[key][sub_key] = sub_value.id
                else:

                    serializable_data[key][sub_key] = sub_value
        else:
            serializable_data[key] = value

    with open('clans_data.json', 'w') as f:
        json.dump(serializable_data, f, indent=4)


# ------------------- Embed Handling -------------------


def load_embed_colour():
    global embed_colour
    try:
        with open('embed_colour.json', 'r') as f:
            embed_colour = json.load(f)
    except FileNotFoundError:
        pass


def save_embed_colour(colour):
    global embed_colour
    embed_colour = colour
    with open('embed_colour.json', 'w') as f:
        json.dump(embed_colour, f)

# ------------------- Player Handling -------------------


def load_tags_from_file():
    try:
        with open('player_tags.json', 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_tags_to_file(tags):
    with open('player_tags.json', 'w') as file:
        json.dump(tags, file)
# ------------------- Clan Handling -------------------


def load_clan_tags():
    try:
        with open('clans_data.json', 'r') as f:
            data = json.load(f)
        return [{"name": tag, "value": tag} for tag in data.keys()]
    except FileNotFoundError:
        return []


clan_tags_choices = load_clan_tags()

# ------------------- Async Functions -------------------


async def get_guild_emojis(guild_id):
    url = f"https://discord.com/api/v10/guilds/{guild_id}/emojis"
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch emojis. Status: {response.status}, Message: {await response.text()}")


async def create_custom_emoji_via_api(guild_id, name, image_url):

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            image_data = await response.read()
    encoded_image_data = base64.b64encode(image_data).decode('utf-8')
    url = f"https://discord.com/api/v10/guilds/{guild_id}/emojis"
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name,
        "image": f"data:image/png;base64,{encoded_image_data}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 201:
                return await response.json()
            else:
                raise Exception(f"Failed to create emoji. Status: {response.status}, Message: {await response.text()}")


async def create_clan_embed(clan):
    embed = Embed(title=f"**{clan.name} | {clan.tag}**", color=(embed_colour))
    embed.set_thumbnail(url=clan.badge.medium)
    embed.add_field(name="Level", value=clan.level, inline=True)
    embed.add_field(name="Clan Description",
                    value=clan.description, inline=False)
    embed.add_field(
        name="Clan Link", value=f"[Press here](https://link.clashofclans.com/en?action=OpenClanProfile&tag={clan.tag})")
    embed.add_field(
        name="Members", value=f"{clan.member_count}/50", inline=False)
    embed.add_field(name="Trophies", value=clan.points, inline=False)
    embed.add_field(name="War Wins", value=clan.war_wins, inline=False)
    embed.add_field(name="War Win Streak",
                    value=clan.war_win_streak, inline=False)
    embed.add_field(name="Type", value=clan.type, inline=False)
    embed.add_field(name="Required Trophies",
                    value=clan.required_trophies, inline=False)
    embed.set_footer(text=clan.tag, icon_url=clan.badge.medium)
    return embed


async def create_player_embed(ctx, player):
    player_embed = Embed(title=f"Profile: {player.name}", color=0x00ff00)
    # Fetch the list of emojis for the guild
    guild_emojis = await get_guild_emojis(ctx.guild_id)
    unranked_emoji_id = 1144673082397704222
    unranked_icon_url = f"https://cdn.discordapp.com/emojis/{unranked_emoji_id}.png"
    player_embed.add_field(name="Name", value=player.name, inline=True)
    player_embed.add_field(name="Tag", value=player.tag, inline=True)
    player_embed.add_field(name="Level", value=player.exp_level, inline=True)
    if player.league and player.league.name and player.league.icon.url:
        league_emoji_name = player.league.name.replace(" ", "_").lower()
        existing_league_emoji = next(
            (e for e in guild_emojis if e['name'] == league_emoji_name), None)
        if not existing_league_emoji:
            try:
                league_emoji = await create_custom_emoji_via_api(ctx.guild_id, league_emoji_name, player.league.icon.url)
            except Exception as e:
                print(f"Failed to create league emoji: {e}")
            trophies_with_league = f"{player.trophies} <:{league_emoji_name}:{league_emoji['id']}>"
        else:
            trophies_with_league = f"{player.trophies} <:{league_emoji_name}:{existing_league_emoji['id']}>"
    else:
        league_emoji_name = "unranked"
        existing_league_emoji = next(
            (e for e in guild_emojis if e['name'] == league_emoji_name), None)
        if not existing_league_emoji:
            try:
                league_emoji = await create_custom_emoji_via_api(ctx.guild_id, "unranked", unranked_icon_url)
            except Exception as e:
                print(f"Failed to create 'unranked' emoji: {e}")
            trophies_with_league = f"{player.trophies} <:{league_emoji_name}:{league_emoji['id']}>"
        else:
            trophies_with_league = f"{player.trophies} <:{league_emoji_name}:{existing_league_emoji['id']}>"
    player_embed.add_field(
        name="Trophies", value=trophies_with_league, inline=True)
    if player.clan:
        emoji_name = player.clan.name
        existing_emoji = next(
            (e for e in guild_emojis if e['name'] == emoji_name), None)
        if existing_emoji:
            clan_badge_emoji = existing_emoji
        else:
            clan_badge_emoji = await create_custom_emoji_via_api(ctx.guild_id, emoji_name, player.clan.badge.medium)
        clan_name_with_emoji = f" {player.clan.name}<:{emoji_name}:{clan_badge_emoji['id']}>"
        player_embed.add_field(
            name="Clan", value=clan_name_with_emoji, inline=True)
        player_embed.add_field(name="Role", value=player.role, inline=True)
        player_embed.set_footer(text=player.clan.tag,
                                icon_url=player.clan.badge.medium)
    player_embed.add_field(
        name="War Stars", value=player.war_stars, inline=True)
    player_embed.add_field(name="Donations Given", value=player.donations if hasattr(
        player, 'donations') else "N/A", inline=True)
    player_embed.add_field(
        name="Attack Wins", value=player.attack_wins, inline=True)
    player_embed.add_field(name="Defense Wins",
                           value=player.defense_wins, inline=True)
    return player_embed


async def create_clan_leaderboard_embed():
    clan_data = load_clan_data()
    sorted_clans = sorted(clan_data.items(), key=lambda x: x[1].get(
        'activity_score', 0), reverse=True)
    embed = Embed(title="Clan Activity Leaderboard", color=embed_colour)

    for i, (clan_tag, clan_info) in enumerate(sorted_clans):
        clan_name = f"Clan {i+1}"
        activity_score = clan_info.get('activity_score', 0)
        embed.add_field(
            name=clan_name, value=f"Tag: {clan_tag}\nActivity Score: {activity_score}", inline=False)

    return embed


def create_ticket_embed(member_id: int):
    embed = Embed(title="**Divide by Zero™ Clan Interview**",
                  description="<a:yellowpointright:1147157048484704326> 1. Click the button `Start Application` to start.\n"
                              "<a:yellowpointright:1147157048484704326> 2. You will do a short interview that takes only **2-3 minutes.**\n"
                              "<a:yellowpointright:1147157048484704326> 3. The bot will guide you step by step.\n"
                              "<a:yellowpointright:1147157048484704326> 4. Our staffs are also available for help.",
                  color=9180869)
    embed.set_footer(text="Press \"Human Support\" if further supports are needed.",
                     icon_url="https://cdn.discordapp.com/attachments/1012759819687571476/1108073866640760922/BOT.png")
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/1030039134963777556/1095783760747839539/Untitled-2.png")
    return embed


def create_start_application_embed():
    embed = Embed(title="**With how many account do you want to apply?**",
                  description="- Choose the number of accounts you will be applying with using the select menu.",
                  color=9180869)
    embed.set_footer(text="Feel free to ask for help for any confusions.",
                     icon_url="https://cdn.discordapp.com/attachments/1012759819687571476/1108073866640760922/BOT.png")
    return embed


def welcome_embed(member_id, member_display_name, member_avatar_url):
    embed = Embed(
        title="**Welcome to Divide by Zero™**",
        description=f"<a:pandawave:853168924434235402> Hey <@{member_id}>! We offer a diverse array of high-quality clans...",
        color=9180869
    )
    embed.set_author(name=member_display_name, icon_url=member_avatar_url)
    embed.set_footer(
        text="Join Time", icon_url="https://cdn.discordapp.com/attachments/1012759819687571476/1108073866640760922/BOT.png")
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/881073424884199435/1129845191071776819/DIVIDE_BY_ZERO_1.png")
    return embed


# ------------------- Ticket Handling -------------------
original_message_ids = {}


async def wait_for_message(bot, author_id, channel_id, timeout=60):
    for _ in range(timeout):
        def check(m):
            return m.author.id == author_id and m.channel.id == channel_id

        try:
            message = await bot.wait_for('message', timeout=1, check=check)
            return message
        except asyncio.TimeoutError:
            continue

    return None


async def change_ticket_name_to_clan(ctx, clan_tag):
    channel = ctx.channel
    if channel.name.startswith("TBD|"):
        clan_name = clan_data.get(clan_tag, {}).get("name", "Unknown")
        await channel.edit(name=f"{clan_name}|{ctx.author.name}")


def save_ticket_data(data):
    with open('tickets_data.json', 'w') as f:
        json.dump(data, f, indent=4)


# ------------------- Bot Events -------------------


@bot.event()
async def on_ready():
    global coc_client
    load_embed_colour()
    global clan_data
    clan_data = load_clan_data()
    print(f"Logged in as {bot.user}")
    if not coc_client:
        coc_client = coc.Client(
            key_names="keys for my windows pc", key_count=5)
        await coc_client.login(Email, Password)
        print("Successfully connected to the coc API!")
    asyncio.get_event_loop().create_task(update_message_counters())


@bot.event()
async def on_message(message):
    if message.author.bot:
        return

    for tag, data in clan_data.items():
        if message.channel.id == data["default_channel"]:
            data["messages"] += 1  # Increment the message count
            save_clan_data(clan_data)  # Save the updated data
            break

# ------------------- Bot Commands -------------------


@slash_command("player_lookup", description="Provides a detailed overview of the player")
@slash_option("discord_user", "The Discord user to lookup", opt_type=OptionType.USER, required=True)
@slash_option("hidden", "Should the response be hidden?", opt_type=OptionType.STRING, required=True, choices=[{"name": "Yes", "value": "yes"}, {"name": "No", "value": "no"}])
async def player_lookup(ctx, discord_user, hidden):
    plhide = hidden.lower() == "yes"
    await ctx.defer(ephemeral=plhide)
    user_id = str(discord_user.id)
    if user_id in player_tags:
        for tag in player_tags[user_id]:
            retries = 3  # Number of retries
            while retries:
                try:
                    player = await coc_client.get_player(tag)
                    embed = await create_player_embed(ctx, player)
                    player_profile_url = f"https://link.clashofclans.com/en?action=OpenPlayerProfile&tag={tag}"
                    link_button = Button(
                        style=ButtonStyle.LINK, label=f"Open {player.name} Profile", url=player_profile_url)
                    action_row = ActionRow(link_button)
                    await ctx.send(embed=embed, components=[action_row], ephemeral=plhide)
                    break  # Break the loop if successful
                except GatewayError:
                    retries -= 1
                    if retries == 0:
                        await ctx.send(f"Failed to fetch data for {tag} after multiple attempts.", ephemeral=plhide)
                        return
                    await asyncio.sleep(1)  # Wait for 1 second before retrying
                except Exception as e:
                    traceback.print_exc()  # This will print the full traceback
                    await ctx.send(f"An error occurred: {e}", ephemeral=plhide)
                    break  # Break the loop if an exception other than GatewayError occurs
    else:
        await ctx.send(f"{discord_user.mention} has no linked Clash of Clans accounts.", ephemeral=True)


@slash_command("player_link", description="Link a Discord user to a Clash of Clans tag")
@slash_option("discord_user", "The Discord user to link", opt_type=OptionType.USER, required=True)
@slash_option("player_tag", "The Clash of Clans ingame tag", opt_type=OptionType.STRING, required=True)
@slash_option("hidden", "Should the response be hidden?", opt_type=OptionType.STRING, required=True, choices=[{"name": "Yes", "value": "yes"}, {"name": "No", "value": "no"}])
async def player_link(ctx, discord_user, player_tag, hidden):
    linkhide = hidden.lower() == "yes"
    user_id = str(discord_user.id)
    if user_id not in player_tags:
        player_tags[user_id] = []
    if player_tag not in player_tags[user_id]:
        player_tags[user_id].append(player_tag)
        save_tags_to_file(player_tags)
        await ctx.send(f"Successfully linked {discord_user.mention} to the tag {player_tag}!", ephemeral=linkhide)
    else:
        await ctx.send(f"{discord_user.mention} is already linked to the tag {player_tag}.", ephemeral=True)


@slash_command("clan", description="Manage your clan")
async def clan_command(ctx):
    pass  # Placeholder


@clan_command.subcommand("add", sub_cmd_description="Adds a clan")
@slash_option("tag", "The tag of the clan", opt_type=OptionType.STRING, required=True)
@slash_option("name", "Clan Name", opt_type=OptionType.STRING, required=True)
@slash_option("default_channel", "The default channel for the clan", opt_type=OptionType.CHANNEL, required=True)
@slash_option("clan_leader_role", "The clan leader role", opt_type=OptionType.ROLE, required=True)
@slash_option("clan_role", "The clan role", opt_type=OptionType.ROLE, required=True)
@slash_option("requirement", "The requirement for the clan", opt_type=OptionType.STRING, required=True)
async def add_clan(ctx, tag, name, default_channel, clan_leader_role, clan_role, requirement):
    print(ctx.kwargs)
    if tag not in clan_data:
        default_channel_id = default_channel.id  # Convert to ID
        clan_leader_role_id = clan_leader_role.id  # Convert to ID
        clan_role_id = clan_role.id  # Convert to ID

        clan_data[tag] = {
            "name": name,
            "default_channel": default_channel_id,
            "leader_role": clan_leader_role_id,
            "clan_role": clan_role_id,
            "requirement": requirement,
            "lastdaymessages": 0,
            "lastweekmessages": 0,
            "last2weeksmessages": 0,
            "lastmonthsmessages": 0,
            "activity_score": 0
        }
        save_clan_data(clan_data)
        global clan_tags_choices
        clan_tags_choices = load_clan_tags()
        await ctx.send(f"Clan {tag} has been added.")
    else:
        await ctx.send(f"Clan {tag} is already added.")


@clan_command.subcommand("remove", sub_cmd_description="Removes a clan")
@slash_option("tag", "The tag of the clan", opt_type=OptionType.STRING, required=True, choices=clan_tags_choices)
async def remove_clan(ctx, tag):
    if tag in clan_data:
        del clan_data[tag]
        save_clan_data(clan_data)
        await ctx.send(f"Clan {tag} has been removed.")
    else:
        await ctx.send(f"Clan {tag} does not exist.")


@clan_command.subcommand("select", sub_cmd_description="Select a clan")
@slash_option("tag", "The tag of the clan", opt_type=OptionType.STRING, required=True, choices=clan_tags_choices)
async def select_clan(ctx, tag):
    await ctx.defer()
    clan = await coc_client.get_clan(tag)
    if clan is None:
        await ctx.send("Clan not found.")
        return
    embed = await create_clan_embed(clan)
    if embed is None:
        await ctx.send("Failed to create embed.")
        return
    clan_profile_url = f"https://link.clashofclans.com/en?action=OpenClanProfile&tag={clan.tag}"
    link_button = Button(style=ButtonStyle.LINK,
                         label=f"Check Out {clan.name}!", url=clan_profile_url)
    action_row = ActionRow(link_button)
    await ctx.send(embed=embed, components=[action_row])


@clan_command.subcommand("activity", sub_cmd_description="Check clan activity score")
@slash_option("tag", "The tag of the clan", opt_type=OptionType.STRING, required=True, choices=clan_tags_choices)
async def clan_activity(ctx, tag):
    clan_info = clan_data.get(tag, None)
    if clan_info:
        activity_score = await calculate_activity_score(clan_info)
        await ctx.send(f"The activity score for clan {tag} is {activity_score:.2f}")
    else:
        await ctx.send(f"Clan {tag} does not exist.")


@clan_command.subcommand("leaderboard", sub_cmd_description="Displays the clan activity leaderboard")
async def clan_leaderboard(ctx):
    await ctx.defer()
    embed = await create_clan_leaderboard_embed()
    await ctx.send(embed=embed, ephemeral=True)


@slash_command("embed-colour", description="Change the colour of the embed")
@slash_option("colour", "Choose a colour", opt_type=OptionType.STRING, required=True, choices=[{"name": colour, "value": colour} for colour in COLOURS.keys()])
async def change_embed_colour(ctx, colour):
    selected_colour = COLOURS[colour]
    save_embed_colour(selected_colour)  # Save the colour
    await ctx.send(f"Embed colour has been changed to {colour}.")


# ------------------- Ticket Commands ------------------

@slash_command("ticket", description="Manage your tickets")
async def ticket_command(ctx):
    pass  # Placeholder


@ticket_command.subcommand("open", sub_cmd_description="Opens a new ticket")
async def open_ticket(ctx, reason=None):
    guild = ctx.guild
    channel_name = f'𝐓𝐁𝐃｜{ctx.author.username}'
    channel = await guild.create_text_channel(channel_name)
    embed = create_ticket_embed(ctx.author.id)

    # Create buttons
    start_application_button = Button(
        style=ButtonStyle.PRIMARY,
        label="Start Application",
        custom_id="start_application"

    )
    human_support_button = Button(
        style=ButtonStyle.SECONDARY,
        label="Human Support",
        custom_id="human_support"
    )
    action_row1 = ActionRow(start_application_button, human_support_button)

    message = await channel.send(
        content=f"<@{ctx.author.id}> Thanks for applying to the Divide by Zero™ Family, please read the embed message!",
        embed=embed,
        components=[action_row1]
    )
    original_message_ids[channel.id] = message.id


@ticket_command.subcommand("close", sub_cmd_description="Closes the ticket")
async def close_ticket(ctx):
    channel = ctx.channel
    if channel.name.startswith("𝐓𝐁𝐃｜") or channel.name.startswith("ticket|"):
        await channel.delete()


@ticket_command.subcommand("change", sub_cmd_description="Changes the ticket name to the clan name")
@slash_option("clan_tag", "The clan tag", opt_type=OptionType.STRING, required=True, choices=clan_tags_choices)
async def change_ticket_name_to_clan(ctx, clan_tag):
    channel = ctx.channel
    if channel.name.startswith("𝐓𝐁𝐃｜"):
        clan_name = clan_data.get(clan_tag, {}).get("name", "Unknown")
        await channel.edit(name=f"{clan_name}|{ctx.author.username}")


@ticket_command.subcommand("add", sub_cmd_description="Adds a user to the ticket")
@slash_option("user", "The user to add", opt_type=OptionType.USER, required=True)
async def add_user(ctx, user):
    channel = ctx.channel
    if channel.name.startswith("𝐓𝐁𝐃｜") or channel.name.startswith("ticket|"):
        await channel.set_permissions(user, read_messages=True)


@ticket_command.subcommand("remove", sub_cmd_description="Removes a user from the ticket")
@slash_option("user", "The user to remove", opt_type=OptionType.USER, required=True)
async def remove_user(ctx, user):
    channel = ctx.channel
    if channel.name.startswith("TBD|") or channel.name.startswith("ticket|"):
        await channel.set_permissions(user, read_messages=False)


# ------------------- Listeners ------------------


@listen()
async def on_message_create(event):
    message_channel = event.message._channel_id

    print(f"Message received in channel {message_channel}")
    for clan_tag, clan_info in clan_data.items():
        print(f"Checking clan {clan_tag}")

        if "default_channel" in clan_info and clan_info["default_channel"] == message_channel:

            print(f"Message was in the default channel for clan {clan_tag}")
            if "messages" not in clan_info:
                clan_info["messages"] = 0
            clan_info["messages"] += 1
            save_clan_data(clan_data)

            print(
                f"Updated message count for clan {clan_tag}: {clan_info['messages']}")
            break


@listen()
async def on_message_delete(event):
    message_channel = event.message._channel_id

    print(f"Message deleted in channel {message_channel}")
    for clan_tag, clan_info in clan_data.items():
        print(f"Checking clan {clan_tag}")

        if "default_channel" in clan_info and clan_info["default_channel"] == message_channel:

            print(f"Message was in the default channel for clan {clan_tag}")
            if "messages" in clan_info and clan_info["messages"] > 0:
                clan_info["messages"] -= 1
            save_clan_data(clan_data)

            print(
                f"Updated message count for clan {clan_tag}: {clan_info['messages']}")
            break


async def fetch_messages_from_channel(channel_id, time_limit=None):
    channel = bot.get_channel(channel_id)
    if channel is None:
        return []
    messages = []
    async for message in channel.history(limit=100):
        if time_limit is None or message.created_at >= time_limit:
            messages.append(message)

    return messages


async def update_message_counters():
    while True:
        for clan_tag, clan_info in clan_data.items():
            counters = {
                "lastdaymessages": 0,
                "lastweekmessages": 0,
                "last2weeksmessages": 0,
                "lastmonthsmessages": 0,
            }
            time_limit = datetime.datetime.utcnow().replace(
                tzinfo=utc) - datetime.timedelta(days=30)
            messages = await fetch_messages_from_channel(clan_info["default_channel"], time_limit)

            for message in messages:
                timestamp = message.created_at
                delta = datetime.datetime.utcnow().replace(tzinfo=utc) - timestamp

                if delta < datetime.timedelta(days=1):
                    counters["lastdaymessages"] += 1
                if delta < datetime.timedelta(days=7):
                    counters["lastweekmessages"] += 1
                if delta < datetime.timedelta(days=14):
                    counters["last2weeksmessages"] += 1
                if delta < datetime.timedelta(days=30):
                    counters["lastmonthsmessages"] += 1
            clan_data[clan_tag].update(counters)

            activity_score = await calculate_activity_score(clan_info)
            clan_info["activity_score"] = activity_score
            clan_role_id = clan_info.get("clan_role", None)
            if clan_role_id:
                if activity_score < 2:
                    await bot.get_channel(clan_info["default_channel"]).send(f"<@&{clan_role_id}> improve clan activity, currently you're at {activity_score:.2f}")
                elif activity_score == 10:
                    await bot.get_channel(clan_info["default_channel"]).send(f"<@&{clan_role_id}> Well done, you reached a {activity_score:.2f} rating!")
            save_clan_data(clan_data)
        await asyncio.sleep(600)


async def calculate_activity_score(clan_info):
    last_day = clan_info.get("lastdaymessages", 0)
    last_week = clan_info.get("lastweekmessages", 0)
    last_2_weeks = clan_info.get("last2weeksmessages", 0)
    last_month = clan_info.get("lastmonthsmessages", 0)

    raw_score = (0.4 * last_day) + (0.3 * last_week) + \
        (0.2 * last_2_weeks) + (0.1 * last_month)
    normalized_score = min(10, raw_score / 100 * 10)
    return normalized_score


original_message_urls = {}


@bot.listen()
async def on_component(event: Component):
    ctx = event.ctx

    match ctx.custom_id:
        case "start_application":
            original_message_id = original_message_ids.get(ctx.channel.id)
            if original_message_id:
                original_message_url = f"https://discord.com/channels/{ctx.guild_id}/{ctx.channel_id}/{original_message_id}"
                # Store the URL
                original_message_urls[ctx.channel.id] = original_message_url

                embed = create_start_application_embed()
                embed.description += f"\n- Go to this [message]({original_message_url}) and click **\"Human Support\"** button for help."

                # Create the selection menu
                selection_menu = StringSelectMenu(
                    "1", "2", "3",
                    placeholder="How many accounts are you applying with?",
                    min_values=1,
                    max_values=1,
                    custom_id="account_selection"
                )
                action_row = ActionRow(selection_menu)

                await ctx.send(embed=embed, components=[action_row])

        case "human_support":
            await ctx.send("<:success:1147171540962648237> Human support will arrive soon, in the meanwhile please wait patiently, and please write down how we can help you.", ephemeral=True)
            # Notify the staff in the channel
            staff_roles = "<@&1147169476513644636> <@&1147169514635673670>"
            await ctx.channel.send(f"{staff_roles} {ctx.author.display_name} needs support!")


@slash_command(name='button', description='Testing a button.')
async def button(ctx: SlashContext):
    components = Button(
        style=ButtonStyle.GREEN,
        label="Click Me",
        custom_id='test',
    )
    await ctx.send("Look, Buttons!", components=components)


@component_callback("account_selection")
async def menu_callback(ctx: ComponentContext):
    selected_option = ctx.values[0]  # Get the selected option
    original_message_url = original_message_urls.get(
        ctx.channel.id)  # Retrieve the stored URL

    # Create a disabled selection menu
    disabled_selection_menu = StringSelectMenu(
        "1", "2", "3",
        placeholder=f"{selected_option} account/s chosen",
        min_values=1,
        max_values=1,
        custom_id="account_selection",
        disabled=True  # Disable the menu
    )
    disabled_action_row = ActionRow(disabled_selection_menu)

    # Edit the original message to disable the selection menu
    await ctx.edit_origin(components=[disabled_action_row])

    # Create the new embed
    embed = Embed(
        title=f"**Can you kindly provide the tag of your `{selected_option}st` account?**",
        description=f"- Post the tag of your Clash of Clans account in the chat.\n- Example answer: `#LCCYJVRUY` (can be copied from your profile)\n- Go to this [message]({original_message_url}) and click **\"Human Support\"** button for help.",
        color=9180869
    )
    embed.set_footer(text="Feel free to ask for help for any confusions.",
                     icon_url="https://cdn.discordapp.com/attachments/1012759819687571476/1108073866640760922/BOT.png")
    # Wait for the next message from the user in the channel

    # Wait for the next message from the user in the channel
    message = await wait_for_message(bot, ctx.author.id, ctx.channel.id)
    if message is None:
        await ctx.channel.send("You took too long to respond. Please try again.")
        return

    # Check if the message content is a valid Clash of Clans player tag
    if not re.match(r'^#([0-9A-Za-z]{8})$', message.content):
        await ctx.channel.send("Invalid Clash of Clans player tag. Please try again.")
        return

    # Create the new embed for the screenshot request
    embed = Embed(
        title=f"**Can you kindly send a screenshot of the base of your `{selected_option}st` account?**",
        description=f"- Please upload the screenshot as an attachment or send it as image URL.\n- This section is optional, you can **skip** this.\n- Go to this [message]({original_message_url}) and click **\"Human Support\"** button for help.",
        color=9180869
    )
    embed.set_footer(text="Feel free to ask for help for any confusions.",
                     icon_url="https://cdn.discordapp.com/attachments/1012759819687571476/1108073866640760922/BOT.png")

    await ctx.channel.send(embed=embed)


@bot.listen()
async def on_component(event: Component):
    ctx = event.ctx
    embed = Embed(
        title="You clicked the button!",
        color='#ADD8E6',
    )
    match ctx.custom_id:
        case "test":
            await ctx.send(embed=embed)


@slash_command("testgreet", description="Manually trigger the welcome message for testing")
async def testgreet_command(ctx):
    await send_welcome_message(ctx.author)


async def send_welcome_message(member):
    # Replace with the channel where you want to send the welcome message
    channel = member.guild.system_channel
    if channel is not None:
        embed = welcome_embed(
            member.id, member.display_name, member.avatar_url)
        await channel.send(content=f"<@{member.id}> | <@&958001363156099103>", embed=embed)


@bot.listen("on_member_join")
async def on_member_join(member):
    await send_welcome_message(member)
# ------------------- Main -------------------
bot.start(BOT_TOKEN)

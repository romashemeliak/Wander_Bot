import os
import re
import json
import datetime
import discord
import requests
from dotenv import load_dotenv
from discord.ext import commands
from hashlib import md5
from pathlib import Path
from io import BytesIO


# Get the path to the .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WANDER_SHARK_JSON = json.loads(os.getenv('WANDER_SHARK_JSON'))
BASE_URL = os.getenv('SHARKSCOPE_BASE_URL')


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)


# Basic functions
def get_tournament(tournament_id, platform):
    return make_request(f'networks/{platform}/tournaments/{tournament_id}')


def make_request(endpoint):
    header = get_header_dict(WANDER_SHARK_JSON)  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< HERE!
    url = f"{BASE_URL}/{header['User-Agent']}/{endpoint}"

    try:
        response = requests.get(url, headers=header)
        if response.status_code == 200:
            return response.json()
        return f"Error: {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"


def get_header_dict(cred):
    password_hash = md5(cred['password'].encode('utf-8')).hexdigest()
    key = md5((password_hash + cred['api']).encode('utf-8')).hexdigest()
    header = {
        'Accept': cred['type'],
        'Password': key,
        'Username': cred['username'],
        'User-Agent': cred['app']
    }
    return header


def sanitize_filename(filename):
    return re.sub(r'[^\w\s-]', '', filename).strip().replace(' ', '_')


# Main functions
def get_tournament_structure(tournament_id, platform, starting_stack):
    # Get tournament info
    tournament_info = get_tournament(tournament_id, platform)

    # Get tournament summary and participants list
    try:
        t_sum = tournament_info["Response"]["TournamentResponse"]["CompletedTournament"]
        participants = tournament_info["Response"]["TournamentResponse"]["CompletedTournament"]["TournamentEntry"]
    except:
        t_sum = tournament_info["Response"]["TournamentResponse"]["ActiveTournament"]

    # Get results
    entrants = int(t_sum.get("@totalEntrants", 0))
    reentries = int(t_sum.get("@reEntries", 0))
    tournament_name = t_sum.get("@name", 'NA')
    buy_in = float(t_sum.get("@rake", 0.0)) + float(t_sum.get("@stake", 0.0))
    table_size = int(t_sum.get("@playersPerTable", 0))
    tournament_date = datetime.datetime.fromtimestamp(int(t_sum.get("@date", 0))).date()
    total_chips = starting_stack * (entrants + reentries)
    tournament_data = []

    for participant in participants:
        position = int(participant["@position"])
        prize = float(participant.get("@prize", 0.0)) - float(participant.get("@prizeBountyComponent", 0.0))

        if prize > 0:
            tournament_data.append([position, round(prize, 2)])
        else:
            itm = position - 1
            break

    tournament_structure = {
        "name": "/",
        "folders": [],
        "structures": [
            {
                "name": tournament_name,
                "chips": total_chips,
                "prizes": {str(item[0]): item[1] for item in tournament_data}
            }
        ]
    }

    return tournament_structure, tournament_name, buy_in, entrants, reentries, table_size, tournament_date, itm


# Discord command
@bot.command()
async def get_structure(ctx, tid, platform, stack):
    structure, name, buy_in, entrants, reentries, table_size, tournament_date, itm \
        = get_tournament_structure(tid, platform, stack)

    # Send tournament info to user
    tournament_info = f"""
**{name}**
**Room:**   {platform}
**Date:**   {tournament_date}
**BuyIn:**   {buy_in}
**Table size:**   {table_size}
**Entrants:**   {entrants} + {reentries} reentry
**ITM:**   {itm}
    """
    await ctx.send(tournament_info)

    # Send JSON file to user
    json_data = json.dumps(structure, indent=4).encode('utf-8')
    file = discord.File(BytesIO(json_data), filename=f'{name}.json')
    await ctx.send(file=file)

    print(f"{name}.json was send to the user {ctx.author.name}")


@bot.command()
async def help(ctx):
    help_message = """
**!get_structure**    -    for Holdem Resource Calculator
Usage:         *!get_structure <tournament_id> <platform_id> <starting_stack>*
Platform:     *Winamax.fr, PokerStars, 888Poker, PokerStars(FR-ES-PT) ... (from sharkscope)*
Example:                    *!get_structure 683221385 Winamax.fr 10000*
    """
    await ctx.send(help_message)

bot.run(DISCORD_TOKEN)

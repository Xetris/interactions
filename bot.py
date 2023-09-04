import coc
from interactions import (Client, Embed)
from dotenv import load_dotenv
import os
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
Email = os.getenv("Email")
Password = os.getenv("Password")

bot = Client()
coc_client = None

gkroleid = "<@1147169514635673670>"
recruitmentroleid = "<@1147169476513644636>"

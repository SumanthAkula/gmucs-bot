from os import environ as env
from time import time


RELEASE = env.get("RELEASE", "LOCAL")
IS_DOCKER = bool(env.get("RELEASE"))

SHARDS_PER_CLUSTER = int(env.get("SHARDS_PER_CLUSTER", "1"))

STARTED = time()

RED_COLOR       = 0xdb2323
INVISIBLE_COLOR = 0x36393E
ORANGE_COLOR    = 0xCE8037
GOLD_COLOR      = 0xFDC333
CYAN_COLOR      = 0x4DD3CC
PURPLE_COLOR    = 0xa830c5
GREEN_COLOR     = 0x0ec37e
BROWN_COLOR     = 0xa2734a
BLURPLE_COLOR   = 0x4a58a2
YELLOW_COLOR    = 0xf1c40f
PINK_COLOR      = 0xf47fff

if RELEASE == "MAIN":
    EMBED_COLOR = RED_COLOR
elif RELEASE == "CANARY":
    EMBED_COLOR = ORANGE_COLOR
elif RELEASE == "LOCAL":
    EMBED_COLOR = PURPLE_COLOR

HTTP_RETRY_LIMIT = 5

DEFAULTS = {
    "promptDelete": True,
    "prefix": ":V "
}

MODULE_DIR = [
	"src/resources/modules",
	"src/resources/events",
	"src/commands",
    "src/apps"
]

PROMPT = {
	"PROMPT_TIMEOUT": 300,
	"PROMPT_ERROR_COUNT": 5
}

ARROW = "\u2192"

OWNER = 177812127363497984

TRANSFER_COOLDOWN = 5

SERVER_INVITE = "https://discord.gg/jJKWpsr"

TABLE_STRUCTURE = {
    "bloxlink": [
        "users",
        "guilds",
        "gameVerification",
        "robloxAccounts",
        "commands",
        "miscellaneous",
        "restrictedUsers",
        "addonData",
        "applications",
        "ads"
    ],
    "canary": [
        "guilds",
        "addonData"
    ],
    "patreon": [
        "refreshTokens",
        "patrons"
    ]
}

PLAYING_STATUS = "{prefix}help"


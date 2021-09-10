from os import environ as env
import config


VALID_SECRETS = ("RETHINKDB_HOST", "RETHINKDB_PASSWORD", "RETHINKDB_PORT", "RETHINKDB_DB", "TOKEN")



for secret in VALID_SECRETS:
    globals()[secret] = env.get(secret) or getattr(config, secret, "")

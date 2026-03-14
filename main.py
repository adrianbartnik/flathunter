""" Startup file for Google Cloud deployment or local webserver"""
from flathunter.argument_parser import parse
from flathunter.idmaintainer import IdMaintainer
from flathunter.web_hunter import WebHunter
from flathunter.config import Config
from flathunter.logging import configure_logging

from flathunter.web import app

# load config
args = parse()
config_handle = args.config
if config_handle is not None:
    config = Config(config_handle.name)
else:
    config = Config()

# Use the SQLite DB file if we are running locally
id_watch = IdMaintainer(f'{config.database_location()}/processed_ids.db')

configure_logging(config)

# initialize search plugins for config
config.init_searchers()

hunter = WebHunter(config, id_watch)

app.config["HUNTER"] = hunter
if config.has_website_config():
    app.secret_key = config.website_session_key()
    app.config["DOMAIN"] = config.website_domain()
    app.config["BOT_NAME"] = config.website_bot_name()
else:
    app.secret_key = b'Not a secret'
notifiers = config.notifiers()
if "telegram" in notifiers:
    app.config["BOT_TOKEN"] = config.telegram_bot_token()

if __name__ == '__main__':
    listen = config['website'].get('listen', {})
    host = listen.get('host', '127.0.0.1')
    port = listen.get('port', '8080')
    app.run(host=host, port=port, debug=True)

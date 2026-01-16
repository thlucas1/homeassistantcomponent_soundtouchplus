"""
Constants for the Bose SoundTouchPlus component.
"""
DOMAIN = "soundtouchplus"
""" Domain identifier for this integration. """

DOMAIN_SPOTIFYPLUS:str = "spotifyplus"
""" Domain identifier of the SpotifyPlus integration. """

CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_ID = "device_id"
CONF_PING_WEBSOCKET_INTERVAL = "ping_websocket_interval"
CONF_PORT_WEBSOCKET = "port_websocket"
CONF_OPTION_SOURCE_LIST = "source_list"
CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID = "spotify_mediaplayer_entity_id"
CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE = "tts_force_google_translate"
CONF_OPTION_RECENTS_CACHE_MAX_ITEMS = "recents_cache_max_items"
CONF_OPTION_SOURCE_ALIASES = "source_aliases"
CONF_OPTION_CONFIGURE_ALIASES = "configure_aliases"

DEFAULT_PING_WEBSOCKET_INTERVAL = 0
DEFAULT_PORT = 8090
DEFAULT_PORT_WEBSOCKET = 8080
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 15

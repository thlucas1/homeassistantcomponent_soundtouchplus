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

DEFAULT_PING_WEBSOCKET_INTERVAL = 0
DEFAULT_PORT = 8090
DEFAULT_PORT_WEBSOCKET = 8080
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 15

# custom service names.
SERVICE_AUDIO_TONE_LEVELS = "audio_tone_levels"
SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS = "clear_source_nowplayingstatus"
SERVICE_GET_SOURCE_LIST = "get_source_list"
SERVICE_MUSICSERVICE_STATION_LIST = "musicservice_station_list"
SERVICE_PLAY_CONTENTITEM = "play_contentitem"
SERVICE_PLAY_HANDOFF = "play_handoff"
SERVICE_PLAY_TTS = "play_tts"
SERVICE_PLAY_URL = "play_url"
SERVICE_PRESET_LIST = "preset_list"
SERVICE_PRESET_REMOVE = "preset_remove"
SERVICE_REBOOT_DEVICE = "reboot_device"
SERVICE_RECENT_LIST = "recent_list"
SERVICE_RECENT_LIST_CACHE = "recent_list_cache"
SERVICE_REMOTE_KEYPRESS = "remote_keypress"
SERVICE_SNAPSHOT_RESTORE = "snapshot_restore"
SERVICE_SNAPSHOT_STORE = "snapshot_store"
SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS = "update_source_nowplayingstatus"
SERVICE_ZONE_TOGGLE_MEMBER = "zone_toggle_member"

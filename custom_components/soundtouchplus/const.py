"""
Constants for the Bose SoundTouchPlus component.
"""
DOMAIN = "soundtouchplus"

CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_ID = "device_id"
CONF_PING_WEBSOCKET_INTERVAL = "ping_websocket_interval"
CONF_PORT_WEBSOCKET = "port_websocket"

DEFAULT_PING_WEBSOCKET_INTERVAL = 0
DEFAULT_PORT = 8090
DEFAULT_PORT_WEBSOCKET = 8080
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 15

# custom service names.
SERVICE_AUDIO_TONE_LEVELS = "audio_tone_levels"
SERVICE_PLAY_CONTENTITEM = "play_contentitem"
SERVICE_PLAY_HANDOFF = "play_handoff"
SERVICE_PLAY_TTS = "play_tts"
SERVICE_PLAY_URL = "play_url"
SERVICE_PRESETLIST = "preset_list"
SERVICE_REBOOT_DEVICE = "reboot_device"
SERVICE_RECENTLIST = "recent_list"
SERVICE_REMOTE_KEYPRESS = "remote_keypress"
SERVICE_SNAPSHOT_RESTORE = "snapshot_restore"
SERVICE_SNAPSHOT_STORE = "snapshot_store"

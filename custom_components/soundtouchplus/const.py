"""
Constants for the Bose SoundTouchPlus component.
"""
DOMAIN = "soundtouchplus"

CONF_WS_PORT = "ws_port"
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_ID = "device_id"

DEFAULT_PORT = 8090
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 15
DEFAULT_WS_PORT = 8080

# custom service names.
SERVICE_PLAY_HANDOFF = "play_handoff"
SERVICE_PLAY_TTS = "play_tts"
SERVICE_PRESETLIST = "preset_list"
SERVICE_RECENTLIST = "recent_list"
SERVICE_REMOTE_KEYPRESS = "remote_keypress"
SERVICE_SNAPSHOT_RESTORE = "snapshot_restore"
SERVICE_SNAPSHOT_STORE = "snapshot_store"

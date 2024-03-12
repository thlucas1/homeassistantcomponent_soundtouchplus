from bosesoundtouchapi import SoundTouchClient
from bosesoundtouchapi.ws import SoundTouchWebSocket

from dataclasses import dataclass
from homeassistant.components.media_player import MediaPlayerEntity
from types import MappingProxyType
from typing import Any

from .const import (
    CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID,
    CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE,
)


@dataclass
class InstanceDataSoundTouchPlus:
    """ 
    SoundTouchPlus instance data stored in the Home Assistant data object.

    This contains various attributes and object instances that the integration needs
    to function.  It is created in `__init__.py`, and referenced in various other
    modules.
    """
    
    client:SoundTouchClient
    """
    The SoundTouchClient instance used to interface with the SoundTouch device.
    """

    media_player:MediaPlayerEntity
    """
    The Home Assistant MediaPlayerEntity instance used to control media playback.
    """
    
    options: MappingProxyType[str, Any]
    """
    Configuration entry options.
    """

    socket:SoundTouchWebSocket
    """
    SoundTouchWebSocket instance that receieves real-time updates from the SoundTouch device
    if websocket processing is enabled.
    """

    @property
    def OptionSpotifyMediaPlayerEntityId(self) -> str | None:
        """
        Spotify media_player entity_id to use for calls to the SpotifyPlus integration.
        Only used by the Spotify calls in media browser.
        """
        return self.options.get(CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID, None)
    
    @property
    def OptionTtsForceGoogleTranslate(self) -> bool | None:
        """
        TTS Force Google Translate option.  If True, all play media announcement type of 
        requests will use the SoundTouchPlus Play TTS service (which uses Google
        Translate); otherwise, use the specified service.
        """
        return self.options.get(CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE, False)

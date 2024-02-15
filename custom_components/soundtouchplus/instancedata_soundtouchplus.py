from bosesoundtouchapi import SoundTouchClient
from bosesoundtouchapi.ws import SoundTouchWebSocket

from dataclasses import dataclass
from homeassistant.components.media_player import MediaPlayerEntity
from types import MappingProxyType
from typing import Any


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
    
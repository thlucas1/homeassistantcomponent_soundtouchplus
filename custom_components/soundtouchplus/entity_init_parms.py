"""
The soundtouchplus component.
"""
import logging
from smartinspectpython.siauto import SIAuto, SISession

from bosesoundtouchapi import SoundTouchClient
from bosesoundtouchapi.ws import SoundTouchWebSocket

from homeassistant.core import HomeAssistant
from homeassistant.components.media_player import MediaPlayerEntity

# get smartinspect logger reference; create a new session for this module name.
_logsi:SISession = SIAuto.Si.GetSession(__name__)
if (_logsi == None):
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


class EntityInitParms:
    """ 
    Parameter list used to initialize a MediaPLayerEntity instance.

    This contains the various objects that are needed when initializing the media
    player entity.
    """

    def __init__(self, hass:HomeAssistant, client:SoundTouchClient, socket:SoundTouchWebSocket) -> None:
        """ 
        Initialize the SoundTouch data object for a device. 

        Args:
            hass (HomeAssistant):
                Home Assistant instance.
            client (SoundTouchClient):
                SoundTouchClient instance.
            socket (SoundTouchWebSocket):
                SoundTouchWebSocket instance.
        """
        _logsi.LogVerbose("Component EntityInitParms object is initializing")

        # initialize instance.
        self.hass = hass
        self.client:SoundTouchClient = client
        self.socket:SoundTouchWebSocket = socket
        self.media_player:MediaPlayerEntity = None

"""
The soundtouchplus component.
"""
import logging
from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIColors
import threading
from xml.etree.ElementTree import Element
from xml.etree import ElementTree

from bosesoundtouchapi import SoundTouchDevice, SoundTouchClient
from bosesoundtouchapi.models import *
from bosesoundtouchapi.uri import *
from bosesoundtouchapi.ws import SoundTouchWebSocket

from homeassistant.core import HomeAssistant, callback

# get smartinspect logger reference; create a new session for this module name.
_logsi:SISession = SIAuto.Si.GetSession(__name__)
if (_logsi == None):
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


class SoundTouchPlusData:
    """ 
    SoundTouch data stored in the Home Assistant data object.

    This contains the SoundTouchDevice and SoundTouchClient objects that are
    created when the component is initialized.
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
        _logsi.LogVerbose("Component SoundTouchPlusData object is initializing")

        # initialize instance.
        self.hass = hass
        self.client:SoundTouchClient = client
        self.socket:SoundTouchWebSocket = socket
        self.media_player = None


    @callback
    def OnSoundTouchUpdateEvent(client:SoundTouchClient, args:Element) -> None:
        if (args != None):
            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "OnSoundTouchUpdateEvent: %s - %s" % (client.Device.DeviceName, args.tag), argsEncoded, colorValue=SIColors.LightGreen)


    @callback
    def OnSoundTouchUpdateEvent_VolumeChanged(client:SoundTouchClient, args:Element) -> None:
        if (args != None):
            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "OnSoundTouchUpdateEvent_VolumeChanged: %s - %s" % (client.Device.DeviceName, args.tag), argsEncoded, colorValue=SIColors.LightGreen)
            # create config object from update event arguments.
            _logsi.LogVerbose("Updating client configuration cache: %s - %s" % (client.Device.DeviceName, args.tag), colorValue=SIColors.LightGreen)
            config:Volume = Volume(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.volume.Path] = config


    @callback
    def OnSoundTouchUpdateEvent_NowPlayingStatus(client:SoundTouchClient, args:Element) -> None:
        if (args != None):
            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "OnSoundTouchUpdateEvent_NowPlayingStatus: %s - %s" % (client.Device.DeviceName, args.tag), argsEncoded, colorValue=SIColors.LightGreen)
            # create config object from update event arguments.
            _logsi.LogVerbose("Updating client configuration cache: %s - %s" % (client.Device.DeviceName, args.tag), colorValue=SIColors.LightGreen)
            config:NowPlayingStatus = NowPlayingStatus(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path] = config


    @callback
    def OnSoundTouchInfoEvent(client:SoundTouchClient, args:Element) -> None:
        if (args != None):
            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "OnSoundTouchInfoEvent: %s - %s" % (client.Device.DeviceName, args.tag), argsEncoded, colorValue=SIColors.LightGreen)

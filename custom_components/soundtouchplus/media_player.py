"""
Support for interface with a Bose SoundTouch.
"""
from __future__ import annotations

from functools import partial
import logging
import re
import requests
import time
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from typing import Any

from bosesoundtouchapi import *
from bosesoundtouchapi.uri import *
from bosesoundtouchapi.models import *
from bosesoundtouchapi.ws import SoundTouchWebSocket

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity_init_parms import EntityInitParms
from .stappmessages import STAppMessages

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIColors
_logsi:SISession = SIAuto.Si.GetSession(__name__)
if (_logsi == None):
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)

# our extra state attribute names.
ATTR_SOUNDTOUCHPLUS_WARN_MSG = "soundtouchplus_warn_msg"


async def async_setup_entry(hass:HomeAssistant, entry:ConfigEntry, async_add_entities:AddEntitiesCallback) -> None:
    """
    Set up the Bose SoundTouch media player based on a config entry.

    This function is called as part of the __init__.async_setup_entry event flow,
    which was initiated via the `hass.config_entries.async_forward_entry_setup` call.
    """
    # get media player entity initialization parameters (e.g. EntityInitParms).
    initParms:EntityInitParms = hass.data[DOMAIN][entry.entry_id]

    # create the platform instance, passing our initialiation parameters.
    _logsi.LogVerbose("media_player.py - async_setup_entry is creating the SoundTouchMediaPlayer instance")
    media_player = SoundTouchMediaPlayer(initParms)

    # add all entities to Home Assistant.
    async_add_entities([media_player], True)

    # store the reference to the media player object.
    hass.data[DOMAIN][entry.entry_id].media_player = media_player


class SoundTouchMediaPlayer(MediaPlayerEntity):
    """
    Representation of a Bose SoundTouch device.
    """

    def __init__(self, initParms:EntityInitParms) -> None:
        """
        Initializes a new instance of the SoundTouch media player entity class.
        
        Args:
            initParms (EntityInitParms):
                The media player entity initialization parameters that were created
                in the `__init__.async_setup_entry` method.
        """
        # initialize storage.
        self._client:SoundTouchClient = initParms.client
        self._socket:SoundTouchWebSocket = initParms.socket
        self._nowPlayingStatus:NowPlayingStatus = None
        self._volume:Volume = None
        self._zone:Zone = None
        self._WarnMsg:str = ""

        # A unique_id for this entity within this domain.
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = self._client.Device.DeviceId

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used in automations etc.
        self._attr_name = self._client.Device.DeviceName
        
        # we will (by default) set polling to false, as the SoundTouch device should be
        # sending us updates as they happen if it supports websocket notificationss.  
        self._attr_should_poll = False
        
        # if websockets are not supported, then we need to enable device polling.
        if self._socket is None:
            _logsi.LogVerbose("'%s': _attr_should_poll is being enabled, as the device does not support websockets" % (self.name))
            self._attr_should_poll = True

        _logsi.LogObject(SILevel.Verbose, "'%s': initialized" % (self.name), self._client)
        return


    # @property
    # def should_poll(self) -> bool:
    #     """Return True if entity has to be polled for state.

    #     False if entity pushes its state to HA.
    #     """
    #     return self._attr_should_poll

    # @should_poll.setter
    # def should_poll(self, value:bool):
    #     """ 
    #     Sets the _attr_should_poll property value.
    #     """
    #     if isinstance(value, bool):
    #         self._attr_should_poll = value
    

    async def async_added_to_hass(self) -> None:
        """
        Run when this Entity has been added to HA.

        Importantly for a push integration, the module that will be getting updates
        needs to notify HA of changes.  In our case, we created a SoundTouchWebSocket
        instance that will inform us when something on the device has changed.  We
        will register some callback methods here so that we can forward the change
        notifications on to Home Assistant (e.g. a call to `self.async_write_ha_state`).

        The call back registration is done once this entity is registered with Home
        Assistant (rather than in the `__init__` method).
        """
        # load list of supported sources.
        _logsi.LogVerbose("'%s': loading list of sources that the device supports" % (self.name))
        sourceList:SourceList = await self.hass.async_add_executor_job(self._client.GetSourceList, True)
        self._attr_source_list = sourceList.ToSourceArray(True)
        _logsi.LogVerbose("'%s': _attr_source_list = %s" % (self.name, str(self._attr_source_list)))

        # if websocket support is disabled then we are done at this point.
        if self._socket is None:
            return
        
        _logsi.LogVerbose("'%s': async_added_to_hass is adding notification event listeners" % (self.name))

        # add our listener(s) that will handle SoundTouch device status updates.
        self._socket.AddListener(SoundTouchNotifyCategorys.nowPlayingUpdated, self._OnSoundTouchUpdateEvent_nowPlayingUpdated)
        # self._socket.AddListener(SoundTouchNotifyCategorys.nowSelectionUpdated, self.OnSoundTouchUpdateEvent)
        self._socket.AddListener(SoundTouchNotifyCategorys.sourcesUpdated, self._OnSoundTouchUpdateEvent_sourcesUpdated)
        self._socket.AddListener(SoundTouchNotifyCategorys.volumeUpdated, self._OnSoundTouchUpdateEvent_volumeUpdated)
        self._socket.AddListener(SoundTouchNotifyCategorys.zoneUpdated, self._OnSoundTouchUpdateEvent_zoneUpdated)
        #self._socket.AddListener(SoundTouchNotifyCategorys.groupUpdated, self._OnSoundTouchUpdateEvent_groupUpdated)
        # self._socket.AddListener(SoundTouchNotifyCategorys.presetsUpdated, self.OnSoundTouchUpdateEvent)
        # self._socket.AddListener(SoundTouchNotifyCategorys.recentsUpdated, self.OnSoundTouchUpdateEvent)
        # self._socket.AddListener(SoundTouchNotifyCategorys.infoUpdated, self.OnSoundTouchUpdateEvent)

        # add our listener(s) that will handle SoundTouch device informational events.
        self._socket.AddListener(SoundTouchNotifyCategorys.SoundTouchSdkInfo, self._OnSoundTouchInfoEvent)

        # add our listener that will handle SoundTouch websocket related events.
        self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketClose, self._OnSoundTouchWebSocketConnectionEvent)
        self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketOpen, self._OnSoundTouchWebSocketConnectionEvent)
        self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketError, self._OnSoundTouchWebSocketErrorEvent)
        self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketPong, self._OnSoundTouchWebSocketPongEvent)

        # start receiving device event notifications.
        _logsi.LogVerbose("'%s': async_added_to_hass is starting websocket notifications" % (self.name))
        self._socket.StartNotification()

        # list various details
        _logsi.LogObject(SILevel.Verbose, "'%s': async_added_to_hass identifiers: name=%s, unique_id=%s, entity_id=%s" % (self.name, self.name, self.unique_id, self.entity_id), self)


    async def async_will_remove_from_hass(self) -> None:
        """
        Entity being removed from hass (the opposite of async_added_to_hass).

        Remove any registered call backs here.
        """
        # stop receiving device event notifications.
        if self._socket is not None:
            _logsi.LogVerbose("'%s': async_will_remove_from_hass is stopping websocket notifications" % (self.name))
            self._socket.StopNotification()
            self._socket.ClearListeners()
            self._socket = None


    # Information about the devices that is partially visible in the UI.
    # The most critical thing here is to give this entity a name so it is displayed
    # as a "device" in the HA UI. This name is used on the Devices overview table,
    # and the initial screen when the device is added (rather than the entity name
    # property below). You can then associate other Entities (eg: a battery
    # sensor) with this device, so it shows more like a unified element in the UI.
    # For example, an associated battery sensor will be displayed in the right most
    # column in the Configuration > Devices view for a device.
    # To associate an entity with this device, the device_info must also return an
    # identical "identifiers" attribute, but not return a name attribute.
    # See the sensors.py file for the corresponding example setup.
    # Additional meta data can also be returned here, including sw_version (displayed
    # as Firmware), model and manufacturer (displayed as <model> by <manufacturer>)
    # shown on the device info screen. The Manufacturer and model also have their
    # respective columns on the Devices overview table. Note: Many of these must be
    # set when the device is first added, and they are not always automatically
    # refreshed by HA from it's internal cache.
    # For more information see:
    # https://developers.home-assistant.io/docs/device_registry_index/#device-properties
    @property
    def device_info(self) -> DeviceInfo:
        """
        Information about this entity/device.
        """
        return {
            "identifiers": {(DOMAIN, self._client.Device.DeviceId)},
            "connections": {(CONNECTION_NETWORK_MAC, format_mac(self._client.Device.MacAddress))},
            "manufacturer": "Bose Corporation",
            "model": self._client.Device.DeviceType,
            "name": self._client.Device.DeviceName,
            "hw_version": self._client.Device.ModuleType,
            #"sw_version": self._client.Device.???,
        }

    # -----------------------------------------------------------------------------------
    # Implement MediaPlayerEntity Properties
    # -----------------------------------------------------------------------------------
    @property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        """
        Return the class of this entity.
        """
        return MediaPlayerDeviceClass.SPEAKER


    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """
        Flag media player features that are supported.
        Supporting methods and properties of these features are implemented below.
        """
        return MediaPlayerEntityFeature.BROWSE_MEDIA \
            | MediaPlayerEntityFeature.GROUPING \
            | MediaPlayerEntityFeature.NEXT_TRACK \
            | MediaPlayerEntityFeature.PAUSE \
            | MediaPlayerEntityFeature.PLAY \
            | MediaPlayerEntityFeature.PLAY_MEDIA \
            | MediaPlayerEntityFeature.PREVIOUS_TRACK \
            | MediaPlayerEntityFeature.REPEAT_SET \
            | MediaPlayerEntityFeature.SELECT_SOURCE \
            | MediaPlayerEntityFeature.SHUFFLE_SET \
            | MediaPlayerEntityFeature.STOP \
            | MediaPlayerEntityFeature.TURN_OFF \
            | MediaPlayerEntityFeature.TURN_ON \
            | MediaPlayerEntityFeature.VOLUME_MUTE \
            | MediaPlayerEntityFeature.VOLUME_SET \
            | MediaPlayerEntityFeature.VOLUME_STEP \


    @property
    def is_volume_muted(self):
        """ Boolean if volume is currently muted. """
        if self._volume is not None:
            return self._volume.IsMuted
        return False


    @property
    def media_album_name(self):
        """ Album name of current playing media. """
        if self._nowPlayingStatus is not None:
            return self._nowPlayingStatus.Album
        return None


    @property
    def media_artist(self):
        """ Artist of current playing media. """
        if self._nowPlayingStatus is not None:
            return self._nowPlayingStatus.Artist
        return None


    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        if self._nowPlayingStatus is not None:
            return self._nowPlayingStatus.Duration
        return None


    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        if self._nowPlayingStatus is not None:
            return self._nowPlayingStatus.Image
        return None


    @property
    def media_title(self):
        """ Title of current playing media. """
        if self._nowPlayingStatus is not None:
            if self._nowPlayingStatus.StationName is not None:
                return self._nowPlayingStatus.StationName
            if self._nowPlayingStatus.Artist is not None:
                return f"{self._nowPlayingStatus.Artist} - {self._nowPlayingStatus.Track}"
        return None


    @property
    def media_track(self):
        """ Artist of current playing media. """
        if self._nowPlayingStatus is not None:
            return self._nowPlayingStatus.Track
        return None


    @property
    def source(self):
        """ Name of the current input source. """
        if self._nowPlayingStatus is not None:
            return self._nowPlayingStatus.Source
        return None


    @property
    def state(self) -> MediaPlayerState | None:
        """ Return the state of the device. """
        if self._nowPlayingStatus is None or self._nowPlayingStatus.Source == "STANDBY":
            result = MediaPlayerState.OFF
        elif self._nowPlayingStatus.Source == "INVALID_SOURCE":
            result = None
        elif self._nowPlayingStatus.PlayStatus == "PLAY_STATE":
            result = MediaPlayerState.PLAYING
        elif self._nowPlayingStatus.PlayStatus == "BUFFERING_STATE":
            result = MediaPlayerState.PLAYING
        elif self._nowPlayingStatus.PlayStatus == "PAUSE_STATE":
            result = MediaPlayerState.PAUSED
        elif self._nowPlayingStatus.PlayStatus == "STOP_STATE":
            result = MediaPlayerState.PAUSED
        else:
            result = None
        return result


    @property
    def extra_state_attributes(self):
        """ Return entity specific state attributes. """
        # build list of our extra state attributes to return to HA UI.
        attributes = {}
        attributes[ATTR_SOUNDTOUCHPLUS_WARN_MSG] = self._WarnMsg
        return attributes


    @property
    def volume_level(self) -> float | None:
        """ Volume level of the media player (0.0 to 1.0). """
        if self._volume is not None:
            #_logsi.LogVerbose("'%s': volume_level = %s" % (self.name, self._volume.Actual))
            return self._volume.Actual / 100
        return None

    # -----------------------------------------------------------------------------------
    # Implement MediaPlayerEntity Methods
    # -----------------------------------------------------------------------------------

    def media_next_track(self) -> None:
        """ Send next track command. """
        self._client.MediaNextTrack()


    def media_pause(self) -> None:
        """ Send media pause command to media player. """
        self._client.MediaPause()


    def media_play(self) -> None:
        """ Send play command. """
        self._client.MediaPlay()


    def media_play_pause(self) -> None:
        """ Simulate play pause media player. """
        self._client.MediaPlayPause()


    def media_previous_track(self) -> None:
        """ Send the previous track command. """
        self._client.MediaPreviousTrack()


    def media_stop(self) -> None:
        """Send stop command."""
        self._client.MediaStop()


    def mute_volume(self, mute:bool) -> None:
        """ Send mute command. """
        self._client.Mute()


    def set_repeat(self, repeat:RepeatMode) -> None:
        """ Set repeat mode. """
        if repeat == RepeatMode.ALL:
            self._client.MediaRepeatAll()
        elif repeat == RepeatMode.OFF:
            self._client.MediaRepeatOff()
        elif repeat == RepeatMode.ONE:
            self._client.MediaRepeatOne()


    def set_shuffle(self, shuffle:bool) -> None:
        """ Enable/disable shuffle mode. """
        if shuffle:
            self._client.MediaShuffleOn()
        else:
            self._client.MediaShuffleOff()


    def set_volume_level(self, volume:float) -> None:
        """ Set volume level, range 0..1. """
        self._client.SetVolumeLevel(int(volume * 100))


    def turn_off(self) -> None:
        """ Turn off media player. """ 
        self._client.PowerOff()


    def turn_on(self) -> None:
        """ Turn on media player. """
        self._client.PowerOn()


    def update(self) -> None:
        """ Retrieve the latest data. """
        _logsi.LogVerbose("'%s': update method (_attr_should_poll=%s)" % (self.name, self._attr_should_poll))
        
        # get updated device status.
        _logsi.LogVerbose("'%s': update method - getting nowPlaying status" % (self.name))
        self._nowPlayingStatus = self._client.GetNowPlayingStatus(self._attr_should_poll)
        _logsi.LogVerbose("'%s': update method - getting volume status" % (self.name))
        self._volume = self._client.GetVolume(self._attr_should_poll)
        _logsi.LogVerbose("'%s': update method - getting zone status" % (self.name))
        self._zone = self._client.GetZoneStatus(self._attr_should_poll)
                    
        # does this device support websocket notifications?
        # note - if socket is None, it denotes that websocket notifications are NOT
        # supported for the device (or are disabled), and we should not try to restart.
        if self._socket is not None:
                      
            # is polling enabled?  if so it should NOT be since websockets are supported.
            # this denotes that a websocket error previously occured which broke the connection.
            # this can happen if the SoundTouch device loses power and drops the connection.
            if self._attr_should_poll == True:
                
                _logsi.LogVerbose("'%s': update method - checking _socket.IsThreadRunForeverActive status" % (self.name))
                
                # if device notification events thread is stopped, then restart it if possible.
                if self._socket.IsThreadRunForeverActive == False:
                    _logsi.LogVerbose("'%s': update is re-starting websocket notifications" % (self.name))
                    self._socket.StopNotification()
                    self._socket.StartNotification()
                    _logsi.LogVerbose("'%s': update is setting _attr_should_poll=False since event notifications are active again" % (self.name))
                    self._attr_should_poll = False
                    

    def volume_down(self) -> None:
        """ Volume down media player. """
        self._client.VolumeDown()


    def volume_up(self) -> None:
        """ Volume up the media player. """
        self._client.VolumeUp()


    def join_players(self, group_members: list[str]) -> None:
        """ Join `group_members` as a player group with the current player. """
        try:
            serviceName:str = "join_players"
            _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, serviceName, self.name, self.entity_id)
            _logsi.LogArray(SILevel.Verbose, "group_members argument", group_members)

            if group_members is None or len(group_members) == 0:
                _logsi.LogError(STAppMessages.MSG_ARGUMENT_NULL, "group_members", serviceName)
                return

            # we will let the zoneUpdated event take care of updating HA state, as ALL
            # players receive a zoneUpdated event when zone members change.

            # the master zone is the entity_id of the media_player that received the join_players request.
            # group_members is a list of entity_id's to add to the master zone.
            masterZone:Zone = Zone(self._client.Device.DeviceId, self._client.Device.Host, True) # <- master

            # create zone members from specified list of entity id's.
            for entity_id in group_members:
                entity_client:SoundTouchClient = self._FindClientInstanceFromEntityId(entity_id, serviceName)
                if (entity_client is not None):
                    # we only need to add group members that are NOT the master.
                    if entity_client.Device.DeviceId != self._client.Device.DeviceId:
                        masterZone.AddMember(ZoneMember(entity_client.Device.Host, entity_client.Device.DeviceId)) # <- member

            # create a new master zone configuration on the device.
            self._client.CreateZone(masterZone)

        except SoundTouchWarning as ex:
            self._WarnMsg = ex.Message
            _logsi.LogWarning(ex.Message)
            raise


    async def async_join_players(self, group_members: list[str]) -> None:
        """ Join `group_members` as a player group with the current player. """
        await self.hass.async_add_executor_job(self.join_players, group_members)


    def unjoin_player(self) -> None:
        """ Remove this player from any group. """
        try:
            _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "Unjoin Player", self.name, self.entity_id)

            # we will let the zoneUpdated event take care of updating HA state, as ALL
            # players receive a zoneUpdated event when zone members change.

            # get master zone status.
            # we do this to retrieve the master zone device id.
            masterZone:Zone = self._client.GetZoneStatus(refresh=True)

            # if we are the master, then we will remove the zone.
            if masterZone.MasterDeviceId == self._client.Device.DeviceId:
                _logsi.LogVerbose("We are the Master zone (%s) - removing zone" % self.entity_id)
                self._client.RemoveZone()
            else:
                # otherwise, just remove ourselves from the zone member list.
                _logsi.LogVerbose("We are a zone member (%s) - removing zone member" % self.entity_id)
                zoneMember:ZoneMember = ZoneMember(self._client.Device.Host, self._client.Device.DeviceId)
                self._client.RemoveZoneMembers([zoneMember])

        except SoundTouchWarning as ex:
            self._WarnMsg = ex.Message
            _logsi.LogWarning(ex.Message)
            raise


    async def async_unjoin_player(self) -> None:
        """ Remove this player from any group. """
        await self.hass.async_add_executor_job(self.unjoin_player)


    async def async_play_media(self, media_type:MediaType|str, media_id:str, **kwargs: Any) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.name
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        await self.hass.async_add_executor_job(
            partial(self.play_media, media_type, media_id, **kwargs)
        )


    def play_media(self, media_type:MediaType|str, media_id:str, **kwargs: Any) -> None:
        """
        Play a piece of media.
        
        Args:
            media_type (MediaType):
                Type of media to play.
            media_id (str):
                Media that will be played; this can be a URL or PRESET value.
                If a preset value is specified, then the SoundTouch device is
                first queried to validate that the preset is correctly set with
                a valid source; if so, then the preset is selected.
            **kwargs (Any):
                Keyword arguments.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND + " - Media=%s ('%s')", "Play Media", self.name, self.name, str(media_type), media_id)

        # is the media an http or https url?
        if re.match(r"http[s]?://", str(media_id)):
            # yes - use PlayUrl method to play the content.
            _logsi.LogVerbose("Executing Play Url command: '%s' ('%s')", str(media_type), media_id)
            self._client.PlayUrl(str(media_id), getMetaDataFromUrlFile=True, volumeLevel=0)
        else:
            # no - treat it as a preset selection.
            _logsi.LogVerbose("Executing Play Preset command - Preset ID = '%s'", media_id)
            presets = self._client.GetPresetList()
            preset:Preset
            for preset in presets:
                if (str(preset.PresetId) == str(media_id)):
                    _logsi.LogVerbose("Playing Preset: '%s'", preset.Name)
                    self._client.SelectPreset(preset)
                    break


    def select_source(self, source:str) -> None:
        """
        Select input source.
        
        Args:
            source (str):
                Source to select.

        The source argument can be specified as just a source value (e.g. "AUX", "BLUETOOTH", etc),
        or as a source and sourceAccount value delimited by a colon (e.g. "PRODUCT:TV").  
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND + " - Source='%s'", "Select Source", self.name, self.name, source)

        # does source contain the source and account name (delimited by ":")?
        dlmidx:int = source.find(":")
        if dlmidx > -1:
            sourceAccount:str = source[dlmidx + 1:]
            source = source[0:dlmidx]
            self._client.SelectSource(source, sourceAccount)
        else:
            self._client.SelectSource(source)


    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(self.hass, media_content_id)

    # -----------------------------------------------------------------------------------
    # SoundTouch Event Notification Handlers
    #
    # The SoundTouch device will send us status update notifications when something
    # changes on the device.  These could be caused by events that WE initiate (e.g. a
    # play_media service call), or by something a user did outside of HA (e.g. turned up
    # the volume via a remote control).
    # -----------------------------------------------------------------------------------

    @callback
    def _OnSoundTouchWebSocketConnectionEvent(self, client:SoundTouchClient, args:str) -> None:
        if (args != None):
            _logsi.LogVerbose("SoundTouch device websocket connection event: %s" % (str(args)), colorValue=SIColors.Coral)


    @callback
    def _OnSoundTouchWebSocketErrorEvent(self, client:SoundTouchClient, ex:Exception) -> None:
        if (ex != None):
            _logsi.LogError("SoundTouch device websocket error event: (%s) %s" % (str(type(ex)), str(ex)), colorValue=SIColors.Coral)
            _logsi.LogVerbose("'%s': Setting _attr_should_poll=True due to websocket error event" % (client.Device.DeviceName), colorValue=SIColors.Coral)
            self._attr_should_poll = True
            
            # at this point we will assume that the device lost power since it lost the websocket connection.
            # reset nowPlayingStatus, which will drive a MediaPlayerState.OFF state.
            _logsi.LogVerbose("'%s': Setting _nowPlayingStatus to None to simulate a MediaPlayerState.OFF state" % (client.Device.DeviceName), colorValue=SIColors.Coral)
            self._nowPlayingStatus = None
            
            # inform Home Assistant of the status update.
            # this will turn the player off in the Home Assistant UI.
            _logsi.LogVerbose("'%s': Calling async_write_ha_state to update player status" % (client.Device.DeviceName), colorValue=SIColors.Coral)          
            self.async_write_ha_state()
            

    @callback
    def _OnSoundTouchWebSocketPongEvent(self, client:SoundTouchClient, args:bytes) -> None:
        _logsi.LogVerbose("SoundTouch device websocket pong event: (%s)" % (str(args)), colorValue=SIColors.Coral)
            

    @callback
    def _OnSoundTouchInfoEvent(self, client:SoundTouchClient, args:Element) -> None:
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # inform Home Assistant of the status update.
            self.update()
            self.async_write_ha_state()

    @callback
    def _OnSoundTouchUpdateEvent_nowPlayingUpdated(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a nowPlayingUpdated event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:NowPlayingStatus = NowPlayingStatus(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path] = config

            # inform Home Assistant of the status update.
            self.update()
            self.async_write_ha_state()


    @callback
    def _OnSoundTouchUpdateEvent_sourcesUpdated(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a sourcesUpdated event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:SourceList = SourceList(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.sources.Path] = config

            # update HA UI source list as well.
            self._attr_source_list = config.ToSourceArray(True)
            _logsi.LogVerbose("'%s': _attr_source_list updated = %s" % (self.name, str(self._attr_source_list)))

            # inform Home Assistant of the status update.
            self.update()
            self.async_write_ha_state()


    @callback
    def _OnSoundTouchUpdateEvent_volumeUpdated(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a volumeUpdated event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:Volume = Volume(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.volume.Path] = config

            # inform Home Assistant of the status update.
            self.update()
            self.async_write_ha_state()


    @callback
    def _OnSoundTouchUpdateEvent_zoneUpdated(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a zoneUpdated event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:Zone = Zone(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.getZone.Path] = config

            # update group_members state.
            members:list[str] = []
            member:ZoneMember
            for member in config.Members:
                entity_id:str = self._FindEntityIdFromClientDeviceId(member.DeviceId, "zoneUpdated")
                if (entity_id is not None):
                    members.append(entity_id)

            self._attr_group_members = members
            _logsi.LogArray(SILevel.Verbose, "zone updated - group_members list (%s)" % (client.Device.DeviceName), self._attr_group_members)

            # inform Home Assistant of the status update.
            self.async_write_ha_state()


    # -----------------------------------------------------------------------------------
    # Helpfer functions
    # -----------------------------------------------------------------------------------

    def _FindClientInstanceFromEntityId(self, entity_id:str, serviceName:str) -> SoundTouchClient:
        """
        Finds a SoundTouch client instance from a string entity id.

        Args:
            entity_id (str):
                Media player entity_id to resolve (e.g. "bose_soundtouch_300").
            serviceName (str):
                Service name that called this function.

        Returns:
            A `SoundTouchClient` instance if one could be resolved; otherwise, None.
        """
        # get service parameter: device id.
        if entity_id is None:
            _logsi.LogError(STAppMessages.MSG_ARGUMENT_NULL, entity_id, serviceName)
            return None

        # search all media_player instances for the specified entity_id.
        # if found, then return the SoundTouchClient assigned to the media_player instance.
        client:SoundTouchClient = None
        data:EntityInitParms = None
        for data in self.hass.data[DOMAIN].values():
            if data.media_player.entity_id == entity_id:
                client = data.client
                break

        # did we resolve it? if not, then log a message.
        if client is None:
            _logsi.LogError("Entity id value of '%s' could not be resolved to a SoundTouch client instance for the '%s' method call" % (str(entity_id), serviceName))
            return None

        # return the client instance.
        _logsi.LogVerbose("Entity id value of '%s' was resolved to SoundTouch client instance '%s' ('%s') for the '%s' method call" % (str(entity_id), client.Device.DeviceName, client.Device.DeviceId, serviceName))
        return client
    

    def _FindEntityIdFromClientDeviceId(self, deviceId:str, serviceName:str) -> str:
        """
        Finds a string entity id from a SoundTouch client DeviceId.

        Args:
            deviceId (str):
                SoundTouchClient DeviceId to resolve (e.g. "E8EB11B9B723").
            serviceName (str):
                Service name that called this function.

        Returns:
            A string entity_id (e.g. "bose_soundtouch_300") if one could be resolved; otherwise, None.
        """
        # get service parameter: device id.
        if deviceId is None:
            _logsi.LogError(STAppMessages.MSG_ARGUMENT_NULL, deviceId, serviceName)
            return None

        # search all media_player instances for the specified deviceId.
        # if found, then return the entity_id assigned to the media_player instance.
        entity_id:str = None
        data:EntityInitParms = None
        for data in self.hass.data[DOMAIN].values():
            if data.client.Device.DeviceId == deviceId:
                entity_id = data.media_player.entity_id
                break

        # did we resolve it? if not, then log a message.
        if entity_id is None:
            _logsi.LogError("DeviceId value of '%s' could not be resolved to a media_player entity_id for the '%s' method call" % (str(deviceId), serviceName))
            return None

        # return the client instance.
        _logsi.LogVerbose("DeviceId value of '%s' was resolved to media_player entity_id '%s' for the '%s' method call" % (str(deviceId), entity_id, serviceName))
        return entity_id
    
    # -----------------------------------------------------------------------------------
    # Custom Services
    # -----------------------------------------------------------------------------------

    def play_handoff(self, to_player:MediaPlayerEntity, restore_volume:bool, snapshot_only:bool) -> None:
        """
        Handoff playing source from one SoundTouch MediaPlayerEntity to another.
        
        Args:
            to_player (MediaPlayerEntity):
                A SoundTouch MediaPlayerEntity that needs to play what we are playing.
            restore_volume (bool):
                True to handoff the FROM player volume level to the TO player;  
                False (default) to leave the TO player volume level as-is.
            snapshot_only (bool):
                True to only handoff the snapshot and not trigger the restore and 
                power off; False (default) to handoff the snapshot, restore it, 
                and power off the FROM player.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "Play Handoff", self.name, self.entity_id)

        if not to_player:
            _logsi.LogWarning("Unable to find SoundTouch TO player")
            return
        
        # take a snapshot of what we are currently playing.
        _logsi.LogVerbose("FROM player '%s' is taking a snapshot", self.entity_id)
        self._client.StoreSnapshot()

        # copy our snapshot settings to the TO player snapshot settings.
        _logsi.LogVerbose("Copying snapshot settings from player '%s' to player '%s'", self.entity_id, to_player.entity_id)
        to_player._client.SnapshotSettings.clear()
        for key in self._client.SnapshotSettings.keys():
            to_player._client.SnapshotSettings[key] = self._client.SnapshotSettings[key]

        # if only taking a snapshot then we are done.
        if snapshot_only:
            _logsi.LogVerbose("Snapshot copy only selected - play handoff complete")
            return
        
        # restore snapshot on TO player.
        _logsi.LogVerbose("TO player '%s' is restoring snapshot settings", to_player.entity_id)
        to_player._client.RestoreSnapshot(restore_volume)

        # turn FROM player off.
        _logsi.LogVerbose("FROM player '%s' is being powered off", self.entity_id)
        self.turn_off()

        _logsi.LogVerbose("Play handoff from player '%s' to player '%s' complete", self.entity_id, to_player.entity_id)


    def play_tts(self, message:str, artist:str, album:str, track:str, ttsUrl:str, volumeLevel:int, appKey:str):
        """
        Plays a notification message via Google TTS (Text-To-Speech) processing.
        
        Args:
            message (str):
                The message that will be converted from text to speech and played on the device.
            artist (str):
                The message text that will appear in the NowPlaying Artist node; if omitted, default is "TTS Notification".
            album (str):
                The message text that will appear in the NowPlaying Album node; if omitted, default is "Google TTS".
            track (str):
                The message text that will appear in the NowPlaying Track node; if omitted, default is the message value.
            ttsUrl (str):
                The Text-To-Speech url used to translate the message.  The value should contain a "{saytext}" format parameter, 
                that will be used to insert the encoded message text.
            volumeLevel (int):
                The temporary volume level that will be used when the message is played.  
                Specify a value of zero to play at the current volume.  
                Default is zero.
            appKey (str):
                Bose Developer API application key.
        """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['message'] = message
            parms['artist'] = artist
            parms['album'] = album
            parms['track'] = track
            parms['ttsUrl'] = ttsUrl
            parms['volumeLevel'] = volumeLevel
            parms['appKey'] = appKey
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_PLAYER_COMMAND % ("play_tts", self.name, self.entity_id), parms)

        self._client.PlayNotificationTTS(message, ttsUrl, artist, album, track, volumeLevel, appKey)


    def play_url(self, url:str, artist:str, album:str, track:str, volumeLevel:int, appKey:str, getMetadataFromUrlFile:bool):
        """
        Play media content from a URL on a SoundTouch device.
        
        Args:
            url (str):
                The URL media content to play on the device.
            artist (str):
                The text that will appear in the NowPlaying Artist node; if omitted, default is "Unknown Artist".
            album (str):
                The text that will appear in the NowPlaying Album node; if omitted, default is "Unknown Album".
            track (str):
                The text that will appear in the NowPlaying Track node; if omitted, default is "Unknown Track".
            volumeLevel (int):
                The temporary volume level that will be used when the media is played.  
                Specify a value of zero to play at the current volume.  
                Default is zero.
            appKey (str):
                Bose Developer API application key.
            getMetadataFromUrlFile (bool):
                The Text-To-Speech url used to translate the message.  The value should contain a "{saytext}" format parameter, 
                that will be used to insert the encoded message text.
        """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['url'] = url
            parms['artist'] = artist
            parms['album'] = album
            parms['track'] = track
            parms['volumeLevel'] = volumeLevel
            parms['appKey'] = appKey
            parms['getMetadataFromUrlFile'] = getMetadataFromUrlFile
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_PLAYER_COMMAND % ("play_url", self.name, self.entity_id), parms)

        self._client.PlayUrl(url, artist, album, track, volumeLevel, appKey, getMetadataFromUrlFile)


    def preset_list(self) -> PresetList:
        """
        Retrieves the list of presets defined for a device.

        Returns:
            A `PresetList` instance that contains defined presets.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "GetPresetList", self.name, self.entity_id)
        return self._client.GetPresetList(True)


    def recent_list(self) -> RecentList:
        """
        Retrieves the list of recently played items defined for a device.

        Returns:
            A `RecentList` instance that contains defined recently played items.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "GetRecentList", self.name, self.entity_id)
        return self._client.GetRecentList(True)


    def remote_keypress(self, key_id:str):
        """
        Send key press and release requests to the player.
        
        Args:
            key_id (str):
                The key to send, which must be one of the pre-defined keys.
                The value is case-sensitive, and should be in UPPER case.
                Example: "POWER", "MUTE", "PLAY", "PAUSE", etc.

        The key_id argument is a string (instead of the Keys ennum), which will 
        allow it to be used for keys defined in the future that are not currently 
        defined.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND + " - Key='%s'", "Remote Keypress", self.name, self.entity_id, str(key_id))
        self._client.Action(key_id)


    def snapshot_restore(self, restore_volume:bool) -> None:
        """
        Restore now playing settings from a snapshot that was previously taken by 
        the snapshot_store method.
        
        Args:
            restore_volume (bool):
                True to restore volume setting; otherwise, False to not change volume.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND + " - Restore Volume='%s'", "Snapshot Restore", self.name, self.entity_id, str(restore_volume))

        # if not restoring volume then remove it from the snapshot settings.
        if not restore_volume:
            if SoundTouchNodes.volume.Path in self._client.SnapshotSettings:
                self._client.SnapshotSettings.pop(SoundTouchNodes.volume.Path)

        self._client.RestoreSnapshot()


    def snapshot_store(self) -> None:
        """
        Store now playing settings to a snapshot, which can be restored later via
        the snapshot_restore method.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "Snapshot Store", self.name, self.entity_id)
        self._client.StoreSnapshot()

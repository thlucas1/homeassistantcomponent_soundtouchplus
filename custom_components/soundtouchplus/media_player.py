"""
Support for interface with a Bose SoundTouch.
"""
from __future__ import annotations

from datetime import datetime
from functools import partial
import logging
import re
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
ATTR_SOUNDTOUCHPLUS_PRESETS_LASTUPDATED = "soundtouchplus_presets_lastupdated"
ATTR_SOUNDTOUCHPLUS_RECENTS_LASTUPDATED = "soundtouchplus_recents_lastupdated"
ATTR_SOUNDTOUCHPLUS_SOUND_MODE = "soundtouchplus_sound_mode"
ATTR_SOUNDTOUCHPLUS_SOURCE = "soundtouchplus_source"
ATTR_SOUNDTOUCHPLUS_TONE_BASS_LEVEL = "soundtouchplus_tone_bass_level"
ATTR_SOUNDTOUCHPLUS_TONE_BASS_LEVEL_RANGE = "soundtouchplus_tone_bass_level_range"
ATTR_SOUNDTOUCHPLUS_TONE_TREBLE_LEVEL = "soundtouchplus_tone_treble_level"
ATTR_SOUNDTOUCHPLUS_TONE_TREBLE_LEVEL_RANGE = "soundtouchplus_tone_treble_level_range"
ATTRVALUE_NOT_CAPABLE = "not capable"


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
        self.soundtouchplus_presets_lastupdated:int = 0
        self.soundtouchplus_recents_lastupdated:int = 0

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
        await self.hass.async_add_executor_job(self._client.GetSourceList, True)
        _logsi.LogVerbose("'%s': source_list = %s" % (self.name, str(self.source_list)))
        _logsi.LogVerbose("'%s': source = %s" % (self.name, str(self.source)))

        # load list of supported sound modes.
        if SoundTouchNodes.audiodspcontrols.Path in self._client.Device.SupportedUris:
            _logsi.LogVerbose("'%s': loading list of sound modes (audiodspcontrols) that the device supports" % (self.name))
            await self.hass.async_add_executor_job(self._client.GetAudioDspControls, True)
            _logsi.LogVerbose("'%s': sound_mode_list = %s" % (self.name, str(self.sound_mode_list)))
            _logsi.LogVerbose("'%s': sound_mode = %s" % (self.name, str(self.sound_mode)))
        else:
            _logsi.LogVerbose("'%s': device does not support sound modes (audiodspcontrols)" % (self.name))
        
        # load list of supported tone levels.
        if SoundTouchNodes.audioproducttonecontrols.Path in self._client.Device.SupportedUris:
            _logsi.LogVerbose("'%s': loading bass tone range levels (audioproducttonecontrols) that the device supports" % (self.name))
            await self.hass.async_add_executor_job(self._client.GetAudioProductToneControls, True)
        else:
            _logsi.LogVerbose("'%s': device does not support tone level adjustments (audioproducttonecontrols)" % (self.name))

        # load zone configuration.
        if SoundTouchNodes.getZone.Path in self._client.Device.SupportedUris:
            _logsi.LogVerbose("'%s': loading zone configuration" % (self.name))
            config:Zone = await self.hass.async_add_executor_job(self._client.GetZoneStatus, True)
            self._attr_group_members = self._BuildZoneMemberEntityIdList(config)

        # if websocket support is disabled then we are done at this point.
        if self._socket is None:
            return
        
        _logsi.LogVerbose("'%s': async_added_to_hass is adding notification event listeners" % (self.name))

        # add our listener(s) that will handle SoundTouch device status updates.
        self._socket.AddListener(SoundTouchNotifyCategorys.audiodspcontrols, self._OnSoundTouchUpdateEvent_audiodspcontrols)
        self._socket.AddListener(SoundTouchNotifyCategorys.audioproducttonecontrols, self._OnSoundTouchUpdateEvent_audioproducttonecontrols)
        self._socket.AddListener(SoundTouchNotifyCategorys.nowPlayingUpdated, self._OnSoundTouchUpdateEvent_nowPlayingUpdated)
        self._socket.AddListener(SoundTouchNotifyCategorys.presetsUpdated, self._OnSoundTouchUpdateEvent_presetsUpdated)
        self._socket.AddListener(SoundTouchNotifyCategorys.recentsUpdated, self._OnSoundTouchUpdateEvent_recentsUpdated)
        self._socket.AddListener(SoundTouchNotifyCategorys.sourcesUpdated, self._OnSoundTouchUpdateEvent_sourcesUpdated)
        self._socket.AddListener(SoundTouchNotifyCategorys.volumeUpdated, self._OnSoundTouchUpdateEvent_volumeUpdated)
        self._socket.AddListener(SoundTouchNotifyCategorys.zoneUpdated, self._OnSoundTouchUpdateEvent_zoneUpdated)

        # add our listener(s) that will handle SoundTouch device informational events.
        self._socket.AddListener(SoundTouchNotifyCategorys.SoundTouchSdkInfo, self._OnSoundTouchInfoEvent)

        # add our listener(s) that will handle SoundTouch websocket related events.
        self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketClose, self._OnSoundTouchWebSocketClosedEvent)
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
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE \
            | MediaPlayerEntityFeature.SELECT_SOURCE \
            | MediaPlayerEntityFeature.SHUFFLE_SET \
            | MediaPlayerEntityFeature.STOP \
            | MediaPlayerEntityFeature.TURN_OFF \
            | MediaPlayerEntityFeature.TURN_ON \
            | MediaPlayerEntityFeature.VOLUME_MUTE \
            | MediaPlayerEntityFeature.VOLUME_SET \
            | MediaPlayerEntityFeature.VOLUME_STEP \


    @property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        """
        Return the class of this entity.
        """
        return MediaPlayerDeviceClass.SPEAKER


    @property
    def extra_state_attributes(self):
        """ Return entity specific state attributes. """
        # build list of our extra state attributes to return to HA UI.
        attributes = {}
        attributes[ATTR_SOUNDTOUCHPLUS_PRESETS_LASTUPDATED] = self.soundtouchplus_presets_lastupdated
        attributes[ATTR_SOUNDTOUCHPLUS_RECENTS_LASTUPDATED] = self.soundtouchplus_recents_lastupdated
        attributes[ATTR_SOUNDTOUCHPLUS_SOURCE] = self.soundtouchplus_source

        if SoundTouchNodes.audiodspcontrols.Path in self._client.ConfigurationCache:
            config:AudioDspControls = self._client.ConfigurationCache[SoundTouchNodes.audiodspcontrols.Path]
            attributes[ATTR_SOUNDTOUCHPLUS_SOUND_MODE] = config.AudioMode
        else:
            attributes[ATTR_SOUNDTOUCHPLUS_SOUND_MODE] = ATTRVALUE_NOT_CAPABLE

        if SoundTouchNodes.audioproducttonecontrols.Path in self._client.ConfigurationCache:
            config:AudioProductToneControls = self._client.ConfigurationCache[SoundTouchNodes.audioproducttonecontrols.Path]
            attributes[ATTR_SOUNDTOUCHPLUS_TONE_BASS_LEVEL] = config.Bass.Value
            attributes[ATTR_SOUNDTOUCHPLUS_TONE_BASS_LEVEL_RANGE] = config.Bass.ToMinMaxString()
            attributes[ATTR_SOUNDTOUCHPLUS_TONE_TREBLE_LEVEL] = config.Treble.Value
            attributes[ATTR_SOUNDTOUCHPLUS_TONE_TREBLE_LEVEL_RANGE] = config.Treble.ToMinMaxString()
        else:
            attributes[ATTR_SOUNDTOUCHPLUS_TONE_BASS_LEVEL] = ATTRVALUE_NOT_CAPABLE
            attributes[ATTR_SOUNDTOUCHPLUS_TONE_TREBLE_LEVEL] = ATTRVALUE_NOT_CAPABLE
            
        return attributes


    @property
    def group_members(self) -> list[str] | None:
        """ List of members which are currently grouped together. """
        return self._attr_group_members


    @property
    def is_volume_muted(self):
        """ Boolean if volume is currently muted. """
        if SoundTouchNodes.volume.Path in self._client.ConfigurationCache:
            config:Volume = self._client.ConfigurationCache[SoundTouchNodes.volume.Path]
            return config.IsMuted
        return False


    @property
    def media_album_name(self):
        """ Album name of current playing media. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            return config.Album
        return None


    @property
    def media_artist(self):
        """ Artist of current playing media. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            return config.Artist
        return None


    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            return config.Duration
        return None


    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            return config.ArtUrl
        return None


    @property
    def media_title(self):
        """ Title of current playing media. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            if config.StationName is not None:
                return config.StationName
            if config.Artist is not None:
                return f"{config.Artist} - {config.Track}"
        return None


    @property
    def media_track(self):
        """ Artist of current playing media. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            return config.Track
        return None


    @property
    def sound_mode(self) -> str | None:
        """ Name of the current sound mode. """
        if SoundTouchNodes.audiodspcontrols.Path in self._client.ConfigurationCache:
            config:AudioDspControls = self._client.ConfigurationCache[SoundTouchNodes.audiodspcontrols.Path]
            return config.AudioMode
        return None


    @property
    def sound_mode_list(self) -> list[str] | None:
        """ List of available sound modes. """
        if SoundTouchNodes.audiodspcontrols.Path in self._client.ConfigurationCache:
            config:AudioDspControls = self._client.ConfigurationCache[SoundTouchNodes.audiodspcontrols.Path]
            return config.ToSupportedAudioModesArray()
        return None


    @property
    def source(self):
        """ Name of the current input source. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            return config.Source
        return None


    @property
    def source_list(self) -> list[str] | None:
        """ List of available input sources. """
        if SoundTouchNodes.sources.Path in self._client.ConfigurationCache:
            config:SourceList = self._client.ConfigurationCache[SoundTouchNodes.sources.Path]
            return config.ToSourceArray(True)
        return None


    @property
    def state(self) -> MediaPlayerState | None:
        """ Return the state of the device. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            if config.Source == "STANDBY":
                result = MediaPlayerState.OFF
            elif config.Source == "INVALID_SOURCE":
                result = None
            elif config.PlayStatus == "PLAY_STATE":
                result = MediaPlayerState.PLAYING
            elif config.PlayStatus == "BUFFERING_STATE":
                result = MediaPlayerState.PLAYING
            elif config.PlayStatus == "PAUSE_STATE":
                result = MediaPlayerState.PAUSED
            elif config.PlayStatus == "STOP_STATE":
                result = MediaPlayerState.PAUSED
        else:
            result = None
        return result


    @property
    def volume_level(self) -> float | None:
        """ Volume level of the media player (0.0 to 1.0). """
        if SoundTouchNodes.volume.Path in self._client.ConfigurationCache:
            config:Volume = self._client.ConfigurationCache[SoundTouchNodes.volume.Path]
            return config.Actual / 100
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
        
        # get updated device status - this will also update the client configuration cache for each.
        _logsi.LogVerbose("'%s': update method - getting nowPlaying status" % (self.name))
        self._client.GetNowPlayingStatus(self._attr_should_poll)
        _logsi.LogVerbose("'%s': update method - getting volume status" % (self.name))
        self._client.GetVolume(self._attr_should_poll)
        _logsi.LogVerbose("'%s': update method - getting zone status" % (self.name))
        config:Zone = self._client.GetZoneStatus(self._attr_should_poll)
        
        # if we are polling, then we need to rebuild the group_members in case it changes;
        # otherwise, the group_members are rebuilt in the zoneupdated event.
        if self._attr_should_poll == True:
            self._attr_group_members = self._BuildZoneMemberEntityIdList(config)
        
        # does this device support audiodspcontrols?
        if SoundTouchNodes.audiodspcontrols.Path in self._client.Device.SupportedUris:
            _logsi.LogVerbose("'%s': update method - getting audio dsp controls (e.g. sound_mode)" % (self.name))
            self._client.GetAudioDspControls(self._attr_should_poll)
                    
        # does this device support audioproducttonecontrols?
        if SoundTouchNodes.audioproducttonecontrols.Path in self._client.Device.SupportedUris:
            _logsi.LogVerbose("'%s': update method - getting audio product tone controls (e.g. bass, treble levels)" % (self.name))
            self._client.GetAudioProductToneControls(self._attr_should_poll)
                    
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


    def select_sound_mode(self, sound_mode: str) -> None:
        """
        Select sound mode.
        
        Args:
            sound_mode (str):
                Sound mode to select.

        The sound_mode argument must be one of the audio modes supported by the device.
        Be aware that some devices do not support audiodspcontrols (e.g. sound modes).
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND + " - SoundMode='%s'", "Select Sound Mode", self.name, self.name, sound_mode)

        # if device does not support audio modes then we are done.
        if SoundTouchNodes.audiodspcontrols.Path in self._client.ConfigurationCache:
            config:AudioDspControls = self._client.ConfigurationCache[SoundTouchNodes.audiodspcontrols.Path]
            
            # does sound mode list contain the specified sound_mode?
            # if so, then change the sound mode; otherwise log an error message.
            if sound_mode in config.SupportedAudioModes:
                cfgUpdate:AudioDspControls = AudioDspControls(audioMode=sound_mode)
                self._client.SetAudioDspControls(cfgUpdate)
            else:
                _logsi.LogError("'%s': Specified sound_mode value '%s' is not a supported audio mode; check the sound_mode_list state value for valid audio modes" % (self.name, sound_mode))
        else:
            _logsi.LogWarning("'%s': Device does not support AudioDspControls; cannot change the sound mode" % (self.name))
                    

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
            
        # is the LOCAL source specified? if so, then use the SelectLocalSource() method to select the 
        # source, as this is the only way to select the LOCAL source for some SoundTouch devices.
        elif source == 'LOCAL':
            _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "SelectLocalSource", self.name, self.name)
            self._client.SelectLocalSource()
            
        elif source == 'LASTSOURCE':
            _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "SelectLastSource", self.name, self.name)
            self._client.SelectLastSource()
            
        elif source == 'LASTSOUNDTOUCHSOURCE':
            _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "SelectLastSoundTouchSource", self.name, self.name)
            self._client.SelectLastSoundTouchSource()
            
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
    def _OnSoundTouchWebSocketClosedEvent(self, client:SoundTouchClient, statCode, args:str) -> None:
        if (args != None):
            _logsi.LogVerbose("SoundTouch device websocket closed event: (%s) %s" % (str(statCode), str(args)), colorValue=SIColors.Coral)


    @callback
    def _OnSoundTouchWebSocketErrorEvent(self, client:SoundTouchClient, ex:Exception) -> None:
        if (ex != None):
            _logsi.LogError("SoundTouch device websocket error event: (%s) %s" % (str(type(ex)), str(ex)), colorValue=SIColors.Coral)
            _logsi.LogVerbose("'%s': Setting _attr_should_poll=True due to websocket error event" % (client.Device.DeviceName), colorValue=SIColors.Coral)
            self._attr_should_poll = True
            
            # at this point we will assume that the device lost power since it lost the websocket connection.
            # reset nowPlayingStatus, which will drive a MediaPlayerState.OFF state.
            _logsi.LogVerbose("'%s': Setting _nowPlayingStatus to None to simulate a MediaPlayerState.OFF state" % (client.Device.DeviceName), colorValue=SIColors.Coral)
            if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
                self._client.ConfigurationCache.pop(SoundTouchNodes.nowPlaying.Path)
            
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
    def _OnSoundTouchUpdateEvent_audiodspcontrols(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a audiodspcontrols event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:AudioDspControls = AudioDspControls(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.audiodspcontrols.Path] = config
            _logsi.LogVerbose("'%s': audiodspcontrols (sound_mode_list) updated = %s" % (self.name, config.ToString()))
            
            # inform Home Assistant of the status update.
            self.async_write_ha_state()


    @callback
    def _OnSoundTouchUpdateEvent_audioproducttonecontrols(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a audioproducttonecontrols event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:AudioProductToneControls = AudioProductToneControls(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.audioproducttonecontrols.Path] = config
            _logsi.LogVerbose("'%s': audioproducttonecontrols updated = %s" % (self.name, config.ToString()))
            
            # inform Home Assistant of the status update.
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
            if len(args) > 0:
                config:NowPlayingStatus = NowPlayingStatus(root=args[0])
                client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path] = config
                _logsi.LogVerbose("'%s': NowPlayingStatus updated = %s" % (self.name, config.ToString()))

            # inform Home Assistant of the status update.
            self.async_write_ha_state()


    @callback
    def _OnSoundTouchUpdateEvent_presetsUpdated(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a presetsUpdated event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            if len(args) > 0:
                config:PresetList = PresetList(root=args[0])
            else:
                config:PresetList = PresetList()
            client.ConfigurationCache[SoundTouchNodes.presets.Path] = config

            # inform Home Assistant of the status update.
            self.soundtouchplus_presets_lastupdated = config.LastUpdatedOn
            self.async_write_ha_state()


    @callback
    def _OnSoundTouchUpdateEvent_recentsUpdated(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a recentsUpdated event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': event notification - %s" % (client.Device.DeviceName, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            if len(args) > 0:
                config:RecentList = RecentList(root=args[0])
            else:
                config:RecentList = RecentList()
            client.ConfigurationCache[SoundTouchNodes.recents.Path] = config

            # inform Home Assistant of the status update.
            self.soundtouchplus_recents_lastupdated = config.LastUpdatedOn
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

            # refresh the list of sources since the sourcesUpdated event does not supply them.
            config:SourceList = self._client.GetSourceList(True)
            _logsi.LogVerbose("'%s': sources (source_list) updated = %s" % (self.name, config.ToString()))

            # inform Home Assistant of the status update.
            self._attr_source_list = config.ToSourceArray(True)
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
            _logsi.LogVerbose("'%s': volume updated = %s" % (self.name, config.ToString()))

            # inform Home Assistant of the status update.
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
            self._attr_group_members = self._BuildZoneMemberEntityIdList(config)
            _logsi.LogArray(SILevel.Verbose, "zone updated - group_members list (%s)" % (client.Device.DeviceName), self._attr_group_members)

            # inform Home Assistant of the status update.
            self.async_write_ha_state()


    # -----------------------------------------------------------------------------------
    # Helpfer functions
    # -----------------------------------------------------------------------------------

    def _BuildZoneMemberEntityIdList(self, config:Zone) -> list:
        """
        Builds a HA "_attr_group_members" state value from a Zone configuration object.
        
        Args:
            config (Zone):
                A Zone configuration object that contains zone member details.
                
        Returns:
            A list object of HA entity id's that represent zone members.
        """
        # build group_members state from Zone configuration.
        members:list[str] = []
        member:ZoneMember
        for member in config.Members:
            entity_id:str = self._FindEntityIdFromClientDeviceId(member.DeviceId, "zoneUpdated")
            if (entity_id is not None):
                members.append(entity_id)
                
        _logsi.LogArray(SILevel.Verbose, "'%s' - zone group_members entity list was refreshed" % self._client.Device.DeviceName, members)
        return members


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

    @property
    def soundtouchplus_source(self):
        """ Name of the current input source (extended). """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            if (config.ContentItem is None):
                return config.Source
            elif (config.ContentItem.SourceAccount is not None) and (len(config.ContentItem.SourceAccount) > 0):
                return "%s:%s" % (config.Source, config.ContentItem.SourceAccount)
            elif (config.ContentItem.Source is not None):
                return config.ContentItem.Source
            else:
                return config.Source
        return None


    def service_audio_tone_levels(self, bassLevel:int, trebleLevel:int):
        """
        Adjust the Bass and Treble values for SoundTouch devices that support it.
        
        Args:
            bassLevel (int):
                The bass level to set; if None, then the level is not adjusted.
            trebleLevel (int):
                The treble level to set; if None, then the level is not adjusted.
        """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['bassLevel'] = bassLevel
            parms['trebleLevel'] = trebleLevel
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_PLAYER_COMMAND % ("service_audio_tone_levels", self.name, self.entity_id), parms)

        # if not supported then log a warning.
        if SoundTouchNodes.audioproducttonecontrols.Path not in self._client.ConfigurationCache:
            _logsi.LogWarning("'%s': Device does not support AudioProductToneControls; cannot change the tone levels" % (self.name))
            return

        # get current tone levels.
        config:AudioProductToneControls = self._client.GetAudioProductToneControls()
        
        # set new tone control values.
        config.Bass.Value = bassLevel
        config.Treble.Value = bassLevel
        self._client.SetAudioProductToneControls(config)

        
    def service_play_contentitem(self, name:str, source:str, sourceAccount:str, itemType:str, location:str, containerArt:str, isPresetable:bool):
        """
        Play media content from a content item source (e.g. TUNEIN station, etc) on a SoundTouch device.
        
        Args:
            name (str):
                Name of the content item (e.g. "K-LOVE Radio").
            source (str):
                Source to select to play the content (e.g. "TUNEIN").  
                The value is case-sensitive, and should normally be UPPER case.
            sourceAccount (str):
                Source account this content item is played with.  
                Default is none.
            itemType (str):
                Type of content item to play (e.g. "stationurl").  
                The value is case-sensitive, and should normally be lower case.
            location (str):
                A direct link to the media content that will be played (e.g. "/v1/playback/station/s33828").
            containerArt (str):
                A direct link to the container art, if present (e.g. "http://cdn-profiles.tunein.com/s33828/images/logog.png?t=637986894890000000").
            isPresetable (bool):
                True if this item can be saved as a Preset; otherwise, False.
        """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['name'] = name
            parms['source'] = source
            parms['sourceAccount'] = sourceAccount
            parms['itemType'] = itemType
            parms['location'] = location
            parms['containerArt'] = containerArt
            parms['isPresetable'] = isPresetable
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_PLAYER_COMMAND % ("service_play_contentitem", self.name, self.entity_id), parms)

        # is this a LOCAL source?
        if source is not None and len(source) > 0 and source == 'LOCAL':
            _logsi.LogVerbose("LOCAL source detected - calling SelectLocalSource for player '%s'", self.entity_id)
            self._client.SelectLocalSource()
            
        # set content item to play, and play it.
        contentItem:ContentItem = ContentItem(source, itemType, location, sourceAccount, isPresetable, name, containerArt)
        self._client.PlayContentItem(contentItem)


    def service_play_handoff(self, to_player:MediaPlayerEntity, restore_volume:bool, snapshot_only:bool) -> None:
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
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "service_play_handoff", self.name, self.entity_id)

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


    def service_play_tts(self, message:str, artist:str, album:str, track:str, ttsUrl:str, volumeLevel:int, appKey:str):
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
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_PLAYER_COMMAND % ("service_play_tts", self.name, self.entity_id), parms)

        self._client.PlayNotificationTTS(message, ttsUrl, artist, album, track, volumeLevel, appKey)


    def service_play_url(self, url:str, artist:str, album:str, track:str, volumeLevel:int, appKey:str, getMetadataFromUrlFile:bool):
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
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_PLAYER_COMMAND % ("service_play_url", self.name, self.entity_id), parms)

        self._client.PlayUrl(url, artist, album, track, volumeLevel, appKey, getMetadataFromUrlFile)


    def service_preset_list(self) -> PresetList:
        """
        Retrieves the list of presets defined for a device.

        Returns:
            A `PresetList` instance that contains defined presets.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "service_preset_list", self.name, self.entity_id)
        return self._client.GetPresetList(True)


    def service_reboot_device(self, sshPort:int):
        """
        Reboots the SoundTouch device operating system.
        
        Args:
            sshPort (int):
                SSH port to connect to; default is 17000.
                
        Returns:
            The server response, in string format.
                
        This method will open a telnet connection to the SoundTouch SSH server
        running on the device (port 17000).  It will then issue a `sys reboot`
        command to reboot the device.  The telnet session will fail if any other
        process has a telnet session open to the device; this is a SoundTouch
        device limitation, as only one SSH session is allowed per device.
        
        If successful, all communication with the device will be lost while the 
        device is rebooting. SoundTouch web-services API connectivity should be 
        restored within 30 - 45 seconds if the reboot is successful.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "service_reboot_device", self.name, self.entity_id)
        self._client.Device.RebootDevice(sshPort)


    def service_recent_list(self) -> RecentList:
        """
        Retrieves the list of recently played items defined for a device.

        Returns:
            A `RecentList` instance that contains defined recently played items.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "service_recent_list", self.name, self.entity_id)
        return self._client.GetRecentList(True)


    def service_remote_keypress(self, key_id:str, key_state:str):
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
        if key_state is None:
            key_state = KeyStates.Both.value
            if key_id is not None and key_id.startswith('PRESET_'):
                key_state = KeyStates.Release.value
        key_state = key_state.lower()

        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND + " - Key='%s', State='%s'", "service_remote_keypress", self.name, self.entity_id, str(key_id), str(key_state))
        self._client.Action(key_id, key_state)


    def service_snapshot_restore(self, restore_volume:bool) -> None:
        """
        Restore now playing settings from a snapshot that was previously taken by 
        the service_snapshot_store method.
        
        Args:
            restore_volume (bool):
                True to restore volume setting; otherwise, False to not change volume.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND + " - Restore Volume='%s'", "service_snapshot_restore", self.name, self.entity_id, str(restore_volume))

        # if not restoring volume then remove it from the snapshot settings.
        if not restore_volume:
            if SoundTouchNodes.volume.Path in self._client.SnapshotSettings:
                self._client.SnapshotSettings.pop(SoundTouchNodes.volume.Path)

        self._client.RestoreSnapshot()


    def service_snapshot_store(self) -> None:
        """
        Store now playing settings to a snapshot, which can be restored later via
        the service_snapshot_restore method.
        """
        _logsi.LogVerbose(STAppMessages.MSG_PLAYER_COMMAND, "service_snapshot_store", self.name, self.entity_id)
        self._client.StoreSnapshot()

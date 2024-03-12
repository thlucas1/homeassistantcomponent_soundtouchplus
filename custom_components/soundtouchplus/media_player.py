"""
Support for interface with a Bose SoundTouch.
"""
from __future__ import annotations

# external package imports.
from bosesoundtouchapi import *
from bosesoundtouchapi.uri import *
from bosesoundtouchapi.models import *
from bosesoundtouchapi.ws import SoundTouchWebSocket

import datetime as dt
from functools import partial
import logging
import re
from typing import Any
import urllib.parse
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_EXTRA,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import entity_sources
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from homeassistant.util.dt import utcnow

# our package imports.
from .browse_media import (
    async_browse_media_library_index, 
    BrowsableMedia,
    browse_media_node, 
    deserialize_object, 
    CONTENT_ITEM_BASE64, 
    LIBRARY_MAP,
    SPOTIFY_LIBRARY_MAP,
)
from .const import (
    CONF_OPTION_SOURCE_LIST, 
    DOMAIN, 
    DOMAIN_SPOTIFYPLUS
)
from .instancedata_soundtouchplus import InstanceDataSoundTouchPlus
from .stappmessages import STAppMessages

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIColors, SIMethodParmListContext
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
    Set up the media player based on a config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry dictionary.  This contains configuration
            settings for the specific component device entry.
        async_add_entities (AddEntitiesCallback):
            Callback function to add all entities to Home Assistant for this platform.

    This function is called as part of the __init__.async_setup_entry event flow,
    which was initiated via the `hass.config_entries.async_forward_entry_setup` call.
    """
    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer async_setup_entry is starting - entry (ConfigEntry) object" % entry.title, entry)

        # get integration instance data from HA datastore.
        data:InstanceDataSoundTouchPlus = hass.data[DOMAIN][entry.entry_id]

        # create the platform instance, passing our initialization parameters.
        _logsi.LogVerbose("'%s': MediaPlayer async_setup_entry is creating the SoundTouchMediaPlayer instance" % entry.title)
        media_player = SoundTouchMediaPlayer(data)

        # add all entities to Home Assistant.
        _logsi.LogVerbose("'%s': MediaPlayer async_setup_entry is adding SoundTouchMediaPlayer instance entities to Home Assistant" % entry.title)
        async_add_entities([media_player], True)

        # store the reference to the media player object.
        _logsi.LogVerbose("'%s': MediaPlayer async_setup_entry is storing the SoundTouchMediaPlayer reference to hass.data[DOMAIN]" % entry.title)
        hass.data[DOMAIN][entry.entry_id].media_player = media_player

        _logsi.LogVerbose("'%s': MediaPlayer async_setup_entry complete" % entry.title)

    except Exception as ex:
        
        # trace.
        _logsi.LogException("'%s': MediaPlayer async_setup_entry exception" % entry.title, ex, logToSystemLogger=False)
        raise

    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


class SoundTouchMediaPlayer(MediaPlayerEntity):
    """
    Representation of a SoundTouchPlus media player device.
    """

    def __init__(self, data:InstanceDataSoundTouchPlus) -> None:
        """
        Initializes a new instance of the SoundTouchPlus media player entity class.
        
        Args:
            data (InstanceDataSoundTouchPlus):
                The media player entity instance data parameters that were created
                in the `__init__.async_setup_entry` method.
        """
        methodParms:SIMethodParmListContext = None
        
        try:

            # trace.
            methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            methodParms.AppendKeyValue("data.client", str(data.client))
            methodParms.AppendKeyValue("data.socket", str(data.socket))
            methodParms.AppendKeyValue("data.media_player", str(data.media_player))
            _logsi.LogMethodParmList(SILevel.Verbose, "'%s': MediaPlayer is initializing - arguments" % data.client.Device.DeviceName, methodParms)
            _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer configuration options" % data.client.Device.DeviceName, data.options, prettyPrint=True)

            # initialize instance storage.
            self._client:SoundTouchClient = data.client
            self._socket:SoundTouchWebSocket = data.socket
            self.data:InstanceDataSoundTouchPlus = data
            self.soundtouchplus_presets_lastupdated:int = 0
            self.soundtouchplus_recents_lastupdated:int = 0
            self.websocket_error_count:int = 0

            # initialize base class attributes (MediaPlayerEntity).
            self._attr_icon = "mdi:speaker"
            self._attr_media_image_remotely_accessible = False
            self._attr_state = MediaPlayerState.IDLE
            
            # A unique_id for this entity within this domain.
            # Note: This is NOT used to generate the user visible Entity ID used in automations.
            self._attr_unique_id = self._client.Device.DeviceId

            # we will set "self._attr_has_entity_name = False", which causes the "self._attr_name"
            # to be used as-is.  use "self._attr_has_entity_name = True", to append the "self._attr_name"
            # value to the end of "DeviceInfo.name" value.
            self._attr_has_entity_name = False
            self._attr_name = self._client.Device.DeviceName

            # set device information.
            # this contains information about the device that is partially visible in the UI.
            # for more information see: https://developers.home-assistant.io/docs/device_registry_index/#device-properties
            self._attr_device_info = DeviceInfo(
                identifiers={ (DOMAIN, self._client.Device.DeviceId) },
                connections={ (CONNECTION_NETWORK_MAC, format_mac(self._client.Device.MacAddress)) },
                hw_version=self._client.Device.ModuleType,
                manufacturer="Bose Corporation",
                model=self._client.Device.DeviceType,
                name=self._client.Device.DeviceName
            )
            _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer device information dictionary" % self.name, self._attr_device_info, prettyPrint=True)

            # set features supported by this media player.
            # supporting methods and properties of these features are implemented below.
            self._attr_supported_features = MediaPlayerEntityFeature.BROWSE_MEDIA \
                                          | MediaPlayerEntityFeature.GROUPING \
                                          | MediaPlayerEntityFeature.NEXT_TRACK \
                                          | MediaPlayerEntityFeature.PAUSE \
                                          | MediaPlayerEntityFeature.PLAY \
                                          | MediaPlayerEntityFeature.PLAY_MEDIA \
                                          | MediaPlayerEntityFeature.PREVIOUS_TRACK \
                                          | MediaPlayerEntityFeature.REPEAT_SET \
                                          | MediaPlayerEntityFeature.SEEK \
                                          | MediaPlayerEntityFeature.SELECT_SOUND_MODE \
                                          | MediaPlayerEntityFeature.SELECT_SOURCE \
                                          | MediaPlayerEntityFeature.SHUFFLE_SET \
                                          | MediaPlayerEntityFeature.STOP \
                                          | MediaPlayerEntityFeature.TURN_OFF \
                                          | MediaPlayerEntityFeature.TURN_ON \
                                          | MediaPlayerEntityFeature.VOLUME_MUTE \
                                          | MediaPlayerEntityFeature.VOLUME_SET \
                                          | MediaPlayerEntityFeature.VOLUME_STEP \
        
            # we will (by default) set polling to false, as the SoundTouch device should be
            # sending us updates as they happen if it supports websocket notificationss.  
            self._attr_should_poll = False
        
            # if websockets are not supported, then we need to enable device polling.
            if self._socket is None:
                _logsi.LogVerbose("'%s': MediaPlayer device polling is being enabled, as the device does not support websockets" % self.name)
                self._attr_should_poll = True
            
            # load option: source_list - list of supported sources.
            self._attr_source_list = data.options.get(CONF_OPTION_SOURCE_LIST, None)
            _logsi.LogArray(SILevel.Verbose, "'%s': MediaPlayer configuration option: '%s' = '%s'" % (self.name, CONF_OPTION_SOURCE_LIST, str(self._attr_source_list)), self._attr_source_list)

            # trace.
            _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer SoundTouchClient object" % self.name, self._client)
            _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer initialization complete" % self.name, self)

        except Exception as ex:
        
            # trace.
            _logsi.LogException("'%s': MediaPlayer initialization exception" % self.name, ex, logToSystemLogger=False)
            raise

        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


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
        config:NowPlayingStatus = self._GetNowPlayingStatusConfiguration()
        if config is not None:
            return config.Album
        return None


    @property
    def media_artist(self):
        """ Artist of current playing media. """
        config:NowPlayingStatus = self._GetNowPlayingStatusConfiguration()
        if config is not None:
            return config.Artist
        return None


    @property
    def media_duration(self) -> int | None:
        """ Duration of current playing media in seconds. """
        return self._attr_media_duration


    @property
    def media_position(self) -> int | None:
        """ Position of current playing media in seconds. """
        return self._attr_media_position


    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """ 
        When was the position of the current playing media valid.
        
        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._attr_media_position_updated_at


    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        config:NowPlayingStatus = self._GetNowPlayingStatusConfiguration()
        if config is not None:
            return config.ArtUrl
        return None


    @property
    def media_title(self):
        """ Title of current playing media. """
        config:NowPlayingStatus = self._GetNowPlayingStatusConfiguration()
        if config is not None:
            # if self._attr_media_content_type == 'music':
            #     return f"{config.Artist} - {config.Track}"
            if config.StationName is not None:
                return config.StationName
            if config.Artist is not None:
                return f"{config.Artist} - {config.Track}"
        return None


    @property
    def media_track(self):
        """ Artist of current playing media. """
        config:NowPlayingStatus = self._GetNowPlayingStatusConfiguration()
        if config is not None:
            return config.Track
        return None


    @property
    def repeat(self) -> RepeatMode | str | None:
        """ Return current repeat mode. """
        return self._attr_repeat


    @property
    def shuffle(self) -> bool | None:
        """ Boolean if shuffle is enabled. """
        return self._attr_shuffle


    @property
    def sound_mode(self) -> str | None:
        """ Name of the current sound mode. """
        return self._attr_sound_mode


    @property
    def sound_mode_list(self) -> list[str] | None:
        """ List of available sound modes. """
        return self._attr_sound_mode_list


    @property
    def source(self):
        """ Title of the current input source. """
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            if SoundTouchNodes.sources.Path in self._client.ConfigurationCache:
                sourceList:SourceList = self._client.ConfigurationCache[SoundTouchNodes.sources.Path]
                return sourceList.GetTitleBySource(config.Source, config.SourceAccount)
            return config.Source
        return None


    @property
    def source_list(self) -> list[str] | None:
        """ List of configured input sources. """
        return self._attr_source_list


    @property
    def state(self) -> MediaPlayerState | None:
        """ Return the state of the device. """
        result = None
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            if config.Source == SoundTouchSources.STANDBY.value:
                result = MediaPlayerState.STANDBY
            elif config.Source == SoundTouchSources.INVALID:
                result = MediaPlayerState.STANDBY
            elif config.PlayStatus == PlayStatusTypes.Playing.value:
                result = MediaPlayerState.PLAYING
            elif config.PlayStatus == PlayStatusTypes.Buffering.value:
                result = MediaPlayerState.PLAYING
            elif config.PlayStatus == PlayStatusTypes.Paused.value:
                result = MediaPlayerState.PAUSED
            elif config.PlayStatus == PlayStatusTypes.Stopped.value:
                result = MediaPlayerState.PAUSED
            elif config.PlayStatus == PlayStatusTypes.Invalid.value:
                result = MediaPlayerState.PAUSED
        else:
            result = MediaPlayerState.OFF
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

    def media_seek(self, position: float) -> None:
        """ Send seek command. """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['position'] = position
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "media_seek", str(parms)), parms)

        # is seek supported for the currently playing media?
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config:NowPlayingStatus = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]
            if config.IsSeekSupported:
                
                # execute seek function and update seek-related attributes.
                self._client.MediaSeekToTime(int(position), delay=0)
                self._attr_media_position = config.Position
                self._attr_media_duration = config.Duration
                self._attr_media_position_updated_at = utcnow()
                _logsi.LogVerbose("media_seek - position float=%s, int=%s, date_updated=%s" % (str(position), int(position), str(self._attr_media_position_updated_at)))
            else:
                _logsi.LogVerbose("media_seek - currently playing media does not support seek function")
        

    def media_next_track(self) -> None:
        """ Send next track command. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_next_track")
        self._client.MediaNextTrack()


    def media_pause(self) -> None:
        """ Send media pause command to media player. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_pause")
        self._client.MediaPause()


    def media_play(self) -> None:
        """ Send play command. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_play")
        self._client.MediaPlay()


    def media_play_pause(self) -> None:
        """ Simulate play pause media player. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_play_pause")
        self._client.MediaPlayPause()


    def media_previous_track(self) -> None:
        """ Send the previous track command. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_previous_track")
        self._client.MediaPreviousTrack()


    def media_stop(self) -> None:
        """ Send stop command. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_stop")
        self._client.MediaStop()


    def mute_volume(self, mute:bool) -> None:
        """ Send mute command. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "mute_volume")
        self._client.Mute()


    def set_repeat(self, repeat:RepeatMode) -> None:
        """ Set repeat mode. """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['repeat'] = repeat
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "set_repeat", str(parms)), parms)

        _logsi.LogVerbose("set_repeat - repeat = '%s'" % (str(repeat)))
        if repeat == RepeatMode.ALL.value:
            self._client.MediaRepeatAll()
        elif repeat == RepeatMode.OFF.value:
            self._client.MediaRepeatOff()
        elif repeat == RepeatMode.ONE.value:
            self._client.MediaRepeatOne()


    def set_shuffle(self, shuffle:bool) -> None:
        """ Enable/disable shuffle mode. """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['shuffle'] = shuffle
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "set_shuffle", str(parms)), parms)

        if shuffle:
            self._client.MediaShuffleOn()
        else:
            self._client.MediaShuffleOff()


    def set_volume_level(self, volume:float) -> None:
        """ Set volume level, range 0..1. """
        if _logsi.IsOn(SILevel.Verbose):
            parms:dict = {}
            parms['volume'] = volume
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "set_volume_level", str(parms)), parms)
            
        self._client.SetVolumeLevel(int(volume * 100))


    def turn_off(self) -> None:
        """ Turn off media player. """ 
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "turn_off")
        self._client.PowerOff()


    def turn_on(self) -> None:
        """ Turn on media player. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "turn_on")
        self._client.PowerOn()


    def update(self) -> None:
        """ Retrieve the latest data. """
        try:
            
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose("'%s': MediaPlayer update (_attr_should_poll=%s)" % (self.name, self._attr_should_poll))

            # if `_attr_should_poll` is True, then cache values are refreshed every 10 seconds for each configuration type.
            # otherwise, the cache updates are performed in the websocket event processing when we get updates from the device.

            # check for websocket restart due to previous error (if websockets are enabled). if socket is None, it denotes 
            # that websocket notifications are NOT supported for the device (or are disabled), and we should NOT try to restart.

            # does this device support websocket notifications?
            if self._socket is not None:
                      
                # is polling enabled?  if so, it should NOT be since websockets are supported.
                # this denotes that a websocket error previously occured which broke the connection.
                # this can happen if the SoundTouch device loses power or drops off the network.
                if self._attr_should_poll == True:
                
                    _logsi.LogVerbose("'%s': MediaPlayer will now try to recover from a previous websocket error (power loss, connection drop, etc)" % self.name)
                
                    # if device notification events thread is stopped, then restart it if possible.
                    _logsi.LogVerbose("'%s': MediaPlayer websocket IsThreadRunForeverActive=%s" % (self.name, str(self._socket.IsThreadRunForeverActive)))
                    if self._socket.IsThreadRunForeverActive == False:
                        
                        # restart websocket notifications.
                        _logsi.LogVerbose("'%s': MediaPlayer is re-starting websocket notifications" % self.name)
                        self._socket.StopNotification()
                        self._socket.StartNotification()
                        
                        # reset polling and media player state.
                        _logsi.LogVerbose("'%s': MediaPlayer will now disable polling of the device for updates going forward, as websocket processing is enabled" % self.name, colorValue=SIColors.Coral)
                        self._attr_should_poll = False
                        
                        # exit update, as we will let the websocket events update the player.
                        return
                    
            # get now playing status.
            _logsi.LogVerbose("'%s': MediaPlayer is getting nowPlaying status" % self.name)
            config:NowPlayingStatus = self._client.GetNowPlayingStatus(self._attr_should_poll)
            self._UpdateNowPlayingData(config)
        
            # get volume status.
            _logsi.LogVerbose("'%s': MediaPlayer is getting volume status" % self.name)
            self._client.GetVolume(self._attr_should_poll)

            # get zone status.
            _logsi.LogVerbose("'%s': MediaPlayer is getting zone status" % self.name)
            config:Zone = self._client.GetZoneStatus(self._attr_should_poll)

            # if we are polling, then we need to rebuild the group_members in case it changes;
            # otherwise, the group_members are rebuilt in the zoneupdated event.
            if self._attr_should_poll == True:
                self._attr_group_members = self._BuildZoneMemberEntityIdList(config)
        
            # does this device support audiodspcontrols?
            if SoundTouchNodes.audiodspcontrols.Path in self._client.Device.SupportedUris:
                _logsi.LogVerbose("'%s': MediaPlayer is getting audio dsp controls (e.g. sound_mode)" % self.name)
                self._client.GetAudioDspControls(self._attr_should_poll)
                    
            # does this device support audioproducttonecontrols?
            if SoundTouchNodes.audioproducttonecontrols.Path in self._client.Device.SupportedUris:
                _logsi.LogVerbose("'%s': MediaPlayer is getting audio product tone controls (e.g. bass, treble levels)" % self.name)
                self._client.GetAudioProductToneControls(self._attr_should_poll)
                    
        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer update exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:
            
            # trace.
            _logsi.LeaveMethod(SILevel.Verbose)


    def volume_down(self) -> None:
        """ Volume down media player. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "volume_down")
        self._client.VolumeDown()


    def volume_up(self) -> None:
        """ Volume up the media player. """
        _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "volume_up")
        self._client.VolumeUp()


    def join_players(self, group_members: list[str]) -> None:
        """ Join `group_members` as a player group with the current player. """
        serviceName:str = "join_players"
        
        try:
            
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS, self.name, serviceName, "group_members='%s'" % str(group_members))
            _logsi.LogArray(SILevel.Verbose, "group_members argument", group_members)

            if group_members is None or len(group_members) == 0:
                raise ValueError(STAppMessages.MSG_ARGUMENT_NULL, "group_members", serviceName)

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

        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer join_players exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:
            
            # trace.
            _logsi.LeaveMethod(SILevel.Verbose)


    async def async_join_players(self, group_members: list[str]) -> None:
        """ Join `group_members` as a player group with the current player. """
        await self.hass.async_add_executor_job(self.join_players, group_members)


    def unjoin_player(self) -> None:
        """ Remove this player from any group. """
        try:
            
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "Unjoin Player")

            # we will let the zoneUpdated event take care of updating HA state, as ALL
            # players receive a zoneUpdated event when zone members change.

            # get master zone status.
            # we do this to retrieve the master zone device id.
            masterZone:Zone = self._client.GetZoneStatus(refresh=True)

            # if we are the master, then we will remove the zone.
            if masterZone.MasterDeviceId == self._client.Device.DeviceId:
                _logsi.LogVerbose("'%s': MediaPlayer is the Master zone - removing zone" % self.name)
                self._client.RemoveZone()
            else:
                # otherwise, just remove ourselves from the zone member list.
                _logsi.LogVerbose("'%s': MediaPlayer is a zone member - removing zone member" % self.name)
                zoneMember:ZoneMember = ZoneMember(self._client.Device.Host, self._client.Device.DeviceId)
                self._client.RemoveZoneMembers([zoneMember])

        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer unjoin_player exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:
            
            # trace.
            _logsi.LeaveMethod(SILevel.Verbose)
        

    async def async_unjoin_player(self) -> None:
        """ Remove this player from any group. """
        await self.hass.async_add_executor_job(self.unjoin_player)


    async def async_play_media(self, media_type:MediaType|str, media_id:str, **kwargs: Any) -> None:
        """Play a piece of media."""
        try:
            
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS, self.name, "async_play_media", "media_type='%s', media_id='%s', kwargs='%s'" % (str(media_type), media_id, str(kwargs)))

            # is media to play from a media source?
            if media_source.is_media_source_id(media_id):
                _logsi.LogVerbose("'%s': MediaPlayer detected that media_id is a media-source item: '%s'" % (self.name, media_id))
                
                # is this an announcement tts message?
                announce:bool = kwargs.get(ATTR_MEDIA_ANNOUNCE, False)
                
                if (announce == True) \
                and (media_id is not None) \
                and (media_id.startswith('media-source://tts/')):
                    
                    _logsi.LogVerbose("'%s': MediaPlayer detected that media_id is an announcement: '%s'" % (self.name, media_id))

                    # ensure we have querystring parameters.
                    idx:int = media_id.find('?')
                    if idx > -1:
                        
                        urlValues:dict = dict(urllib.parse.parse_qsl(media_id[idx+1:], keep_blank_values=True))
                        _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer announcement parameters dictionary: '%s'" % (self.name, str(urlValues)), urlValues)
                        
                        # are we forcing tts announcements to use our play tts service?
                        if self.data.OptionTtsForceGoogleTranslate:

                            # get message parameters.
                            # parameters will vary based upon the media-source (e.g. google cloud vs google translate).
                            message:str = urlValues.get("message", None)
                            language:str = urlValues.get("language", "EN")
                            voice:str = urlValues.get("voice", None)  # google cloud parameter
                            ttsUrl:str = "http://translate.google.com/translate_tts?ie=UTF-8&tl={language}&client=tw-ob&q={saytext}".replace("{language}", language)
    
                            # play announcement via play_tts service.
                            _logsi.LogVerbose("'%s': MediaPlayer is calling play_tts service to play announcement: '%s'" % (self.name, message))
                            await self.hass.async_add_executor_job(
                                self.service_play_tts, message, "Announcement", "Announcement", None, ttsUrl, None, None
                                )
                            return

                # resolve the media to play.  
                # if it's an announcement, then it turns the text message into a playable MP3 
                # url from the selected tts media source.
                play_item = await media_source.async_resolve_media(
                    self.hass, media_id, self.entity_id
                )
                _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer resolved media_id to a PlayItem object: '%s'" % (self.name, play_item.url), play_item)
                media_id = async_process_play_media_url(self.hass, play_item.url)

            _logsi.LogVerbose("'%s': MediaPlayer is calling play_media to play content: %s" % (self.name, "media_type='%s', media_id='%s', kwargs='%s'" % (str(media_type), media_id, str(kwargs))))
            await self.hass.async_add_executor_job(
                partial(self.play_media, media_type, media_id, **kwargs)
        )

        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer async_play_media exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:
            
            # trace.
            _logsi.LeaveMethod(SILevel.Verbose)


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
                Extra arguments supported are:  
                `announce` - set to true if the request is coming from a tts service; otherwise not supplied.  
                `source`   - source title to select for playing the content; must exactly match (case-sensitive) a source title in the source list.  
        """
        try:
            
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS, self.name, "play_media", "media_type='%s', media_id='%s', kwargs='%s'" % (str(media_type), media_id, str(kwargs)))

            # get keyword arguments (if any).
            # these are in the form of a {"extra:" {} } dictionary.
            extra_options:str = kwargs.get(ATTR_MEDIA_EXTRA, None)
            source:str = None
            announce:bool = False
            announceValue:str = None
            if extra_options is not None:

                _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer play media detected keyword arguments" % self.name, extra_options, prettyPrint=True)
                source = extra_options.get(ATTR_INPUT_SOURCE, None)
                announce = bool(kwargs.get(ATTR_MEDIA_ANNOUNCE, False))

                # if this is an announcement (e.g. say text) then set arguments to reflect this.
                if announce:
                    announceValue = "Announcement"

            # was a content item in base64 encoded format supplied?  
            # this would be coming from a browse media selection.
            if media_id is not None and media_id.startswith(CONTENT_ITEM_BASE64):

                # drop the eye-ctacher prefix before we deserialize.
                media_id = media_id[len(CONTENT_ITEM_BASE64):]
                contentItem:ContentItem = deserialize_object(media_id)
                _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer is playing media from %s" % (self.name, contentItem.ToString()), contentItem, excludeNonPublic=True)
                self._client.PlayContentItem(contentItem)
                
            # is the media an http or https url?
            elif re.match(r"http[s]?://", media_id):
                
                _logsi.LogVerbose("'%s': MediaPlayer play_media detected URL media: Url='%s'", self.name, media_id)
                self._client.PlayUrl(media_id, artist=announceValue, album=announceValue, getMetaDataFromUrlFile=True, volumeLevel=0)
            
            # is the media a spotify uri?
            elif re.match(r"spotify:", media_id):
            
                _logsi.LogVerbose("'%s': MediaPlayer play_media detected spotify uri media: Uri='%s', Source='%s'", self.name, media_id, source)
                sourceItem:SourceItem = self._GetSourceItemByTitle(source)
                if sourceItem is None:
                    raise ValueError("'%s': MediaPlayer play_media did not find source '%s' in the source list" % (self.name, source))
                else:
                    if self.source != sourceItem.SourceTitle:
                        _logsi.LogVerbose("'%s': MediaPlayer is selecting spotify source: '%s'", self.name, source)
                        self._client.SelectSource(sourceItem.Source, sourceItem.SourceAccount)
                    ci:ContentItem = ContentItem(sourceItem.Source, "uri", media_id, sourceItem.SourceAccount, True)
                    self._client.PlayContentItem(ci)
                
            # otherwise treat it as a preset selection.
            else:
            
                _logsi.LogVerbose("'%s': MediaPlayer play_media detected Preset selection: Preset='%s'", self.name, media_id)
                presets = self._client.GetPresetList()
                preset:Preset
                for preset in presets:
                    if (str(preset.PresetId) == media_id):
                        _logsi.LogVerbose("'%s': MediaPlayer play_media found matching Preset Name '%s' - selecting preset", self.name, preset.Name)
                        self._client.SelectPreset(preset)
                        return
                raise ValueError("'%s': MediaPlayer play_media did not find a matching Preset ID '%s'" % (self.name, preset.Name))

        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer play_media exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:
            
            # trace.
            _logsi.LeaveMethod(SILevel.Verbose)


    def select_sound_mode(self, sound_mode: str) -> None:
        """
        Select sound mode.
        
        Args:
            sound_mode (str):
                Sound mode to select - the following (case-sensitive) formats are supported:  
                - audio mode name string (e.g. "Dialog")
                - audio mode value string (e.g. "AUDIO_MODE_DIALOG")

        The sound_mode argument must be one of the audio modes supported by the device.
        Be aware that some devices do not support audiodspcontrols (e.g. sound modes).
        """
        try:
            
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS, self.name, "select_sound_mode", "sound_mode='%s'" % (sound_mode))

            # does device support audio dsp controls?
            if SoundTouchNodes.audiodspcontrols.Path in self._client.ConfigurationCache:
            
                # is sound_mode an audio mode name?  if so, then we need the value.
                audioDspAudioMode:str = AudioDspAudioModes.GetValueByName(sound_mode)
                if audioDspAudioMode is not None:
                    sound_mode = audioDspAudioMode

                # does sound mode list contain the specified sound_mode?
                # if so, then change the sound mode; otherwise log an error message.
                config:AudioDspControls = self._client.ConfigurationCache[SoundTouchNodes.audiodspcontrols.Path]
                if sound_mode in config.SupportedAudioModes:
                    cfgUpdate:AudioDspControls = AudioDspControls(audioMode=sound_mode)
                    self._client.SetAudioDspControls(cfgUpdate)
                else:
                    _logsi.LogError("'%s': Specified sound_mode value '%s' is not a supported audio mode; check the sound_mode_list state value for valid audio modes" % (self.name, sound_mode))
            else:
                _logsi.LogWarning("'%s': Device does not support AudioDspControls; cannot change the sound mode" % self.name)
                    
        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer select_sound_mode exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:
            
            # trace.
            _logsi.LeaveMethod(SILevel.Verbose)


    def select_source(self, source:str) -> None:
        """
        Select input source.
        
        Args:
            source (str):
                Source to select - the following (case-sensitive) formats are supported:  
                - source string (e.g. "AIRPLAY")  
                - source and account string (e.g. "PANDORA:yourpandorauserid")  
                - source title string (e.g. "My NAS Music")  
        """
        try:
            
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS, self.name, "select_source", "source='%s'" % (source))
        
            sourceAccount:str = None

            # is source a SourceTitle value?
            sourceItem = self._GetSourceItemByTitle(source)
            if sourceItem is not None:
            
                source = sourceItem.Source
                sourceAccount = sourceItem.SourceAccount
            
            else:

                # does source contain the source and account name (delimited by ":")?
                dlmidx:int = source.find(":")
                if dlmidx > -1:
                    sourceAccount:str = source[dlmidx + 1:]
                    source:str = source[0:dlmidx]

            # is the LOCAL source specified? if so, then use the SelectLocalSource() method to select the 
            # source, as this is the only way to select the LOCAL source for some SoundTouch devices.
            if source == 'LOCAL':
                _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "SelectLocalSource")
                self._client.SelectLocalSource()
            
            elif source == 'LASTSOURCE':
                _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "SelectLastSource")
                self._client.SelectLastSource()
            
            elif source == 'LASTSOUNDTOUCHSOURCE':
                _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "SelectLastSoundTouchSource")
                self._client.SelectLastSoundTouchSource()
            
            elif source == 'LASTWIFISOURCE':
                _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "SelectLastWifiSource")
                self._client.SelectLastWifiSource()

            elif source in ['AUX','AIRPLAY']: # AUX requires both source and source account.
                _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "SelectSource")
                self._client.SelectSource(source, sourceAccount)
            
            elif source in ['BLUETOOTH']:
                _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "SelectSource")
                self._client.SelectSource(source)
            
            else:
            
                # if source is for a music service, then the select source requires a location
                # variable.  since we cannot supply that on this method, we will perform a 
                # lookup in the recently played items to retrieve the last station played for the source.
                _logsi.LogVerbose("'%s': retrieving recently played content for source '%s (%s)' ..." % (self.name, source, sourceAccount))
                recentList:RecentList = self._client.GetRecentList(False)
                recent:Recent
                for recent in recentList.Recents:
                    if recent.Source == source:
                        _logsi.LogObject(SILevel.Verbose, "'%s': recently played contentItem found for source '%s (%s)'" % (self.name, source, sourceAccount), recent.ContentItem, excludeNonPublic=True)
                        self._client.PlayContentItem(recent.ContentItem)
                        return
                
                # if no recent was found, then just try to select the source (with source account).
                self._client.SelectSource(source, sourceAccount)

        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer select_source exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:
            
            # trace.
            _logsi.LeaveMethod(SILevel.Verbose)


    def _GetNowPlayingStatusConfiguration(self) -> NowPlayingStatus:

        config:NowPlayingStatus = None

        # get device nowplaying status.
        if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
            config = self._client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path]

            # do we have a source-specific nowplaying status?  if so, then return it.
            cacheKey = "%s-%s:%s" % (SoundTouchNodes.nowPlaying.Path, config.Source, config.SourceAccount)
            if cacheKey in self._client.ConfigurationCache:
                config = self._client.ConfigurationCache[cacheKey]

        return config


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
            _logsi.LogVerbose("'%s': MediaPlayer client device websocket connection event: %s (websocket error count will be reset)" % (self.name, str(args)), colorValue=SIColors.Coral)

        # reset websocket error count, as we know websockets are active again.
        self.websocket_error_count = 0


    @callback
    def _OnSoundTouchWebSocketCloseEvent(self, client:SoundTouchClient, statCode=None, args:str=None) -> None:
        if (args != None):
            _logsi.LogVerbose("'%s': MediaPlayer client device websocket close event: (%s) %s" % (self.name, str(statCode), str(args)), colorValue=SIColors.Coral)


    @callback
    def _OnSoundTouchWebSocketErrorEvent(self, client:SoundTouchClient, ex:Exception) -> None:
        if (ex != None):
            
            # suppress error logging after the first message, as this could quickly fill up the error log if we don't!
            # we will log an error for every 60 times we get a message.
            self.websocket_error_count = self.websocket_error_count + 1
            if (self.websocket_error_count %60 == 0) or (self.websocket_error_count == 1):
                _logsi.LogError("'%s': MediaPlayer client device websocket error event - count=%d: (%s) %s" % (self.name, self.websocket_error_count, str(type(ex)), str(ex)), colorValue=SIColors.Coral)

            # at this point we will assume that the websocket connection is lost or in an unusable state.
            # this can happen when the SoundTouch device loses power or network connectivity.
            
            # enable polling, so that the device is checked for updates periodically (every 10 seconds).
            _logsi.LogVerbose("'%s': MediaPlayer will now enable polling of the device for updates going forward, until websocket processing can be restarted" % self.name, colorValue=SIColors.Coral)
            self._attr_should_poll = True
            
            # reset nowPlayingStatus, which will drive a MediaPlayerState.IDLE state.
            _logsi.LogVerbose("'%s': MediaPlayer is resetting nowPlayingStatus to force an IDLE state of the media player" % self.name, colorValue=SIColors.Coral)
            if SoundTouchNodes.nowPlaying.Path in self._client.ConfigurationCache:
                self._client.ConfigurationCache.pop(SoundTouchNodes.nowPlaying.Path)
            
            # stop the websocket notification thread.
            # we will try to restart websocket notifications (in the update method) on the next polling update.
            _logsi.LogVerbose("'%s': MediaPlayer is stopping websocket notification events thread; this will force a restart of the thread on the next device poll update" % self.name, colorValue=SIColors.Coral)
            self._socket.StopNotification()
            
            # inform Home Assistant of the status update.
            self.async_write_ha_state()
            

    @callback
    def _OnSoundTouchWebSocketPongEvent(self, client:SoundTouchClient, args:bytes) -> None:
        _logsi.LogVerbose("'%s': MediaPlayer client device websocket pong event: (%s)" % (self.name, str(args)), colorValue=SIColors.Coral)
            

    @callback
    def _OnSoundTouchInfoEvent(self, client:SoundTouchClient, args:Element) -> None:
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

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
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:AudioDspControls = AudioDspControls(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.audiodspcontrols.Path] = config
            _logsi.LogVerbose("'%s': MediaPlayer audiodspcontrols (sound_mode_list) updated: %s" % (self.name, config.ToString()))
            
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
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:AudioProductToneControls = AudioProductToneControls(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.audioproducttonecontrols.Path] = config
            _logsi.LogVerbose("'%s': MediaPlayer audioproducttonecontrols updated: %s" % (self.name, config.ToString()))
            
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
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            if len(args) > 0:
                config:NowPlayingStatus = NowPlayingStatus(root=args[0])
                client.ConfigurationCache[SoundTouchNodes.nowPlaying.Path] = config
                _logsi.LogVerbose("'%s': MediaPlayer NowPlayingStatus updated: %s" % (self.name, config.ToString()))
                
                # update nowplaying attributes.
                self._UpdateNowPlayingData(config)

            # inform Home Assistant of the status update.
            self.async_write_ha_state()
            
        # reset websocket error count, as we know websockets are active again.
        self.websocket_error_count = 0
                

    @callback
    def _OnSoundTouchUpdateEvent_presetsUpdated(self, client:SoundTouchClient, args:Element) -> None:
        """
        Process a presetsUpdated event notification from the SoundTouch device.
        """
        if (args != None):

            if (_logsi.IsOn(SILevel.Verbose)):
                ElementTree.indent(args)  # for pretty printing
                argsEncoded = ElementTree.tostring(args, encoding="unicode")
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

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
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

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
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

            # refresh the list of sources since the sourcesUpdated event does not supply them.
            config:SourceList = self._client.GetSourceList(True)
            _logsi.LogVerbose("'%s': sources (source_list) updated = %s" % (self.name, config.ToString()))

            # inform Home Assistant of the status update.
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
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:Volume = Volume(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.volume.Path] = config
            _logsi.LogVerbose("'%s': MediaPlayer volume updated: %s" % (self.name, config.ToString()))

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
                _logsi.LogXml(SILevel.Verbose, "'%s': MediaPlayer client device event notification - %s" % (self.name, args.tag), argsEncoded)

            # create configuration model from update event argument and update the cache.
            config:Zone = Zone(root=args[0])
            client.ConfigurationCache[SoundTouchNodes.getZone.Path] = config

            # update group_members state.
            self._attr_group_members = self._BuildZoneMemberEntityIdList(config)
            _logsi.LogArray(SILevel.Verbose, "'%s': MediaPlayer zone updated - group_members list" % self.name, self._attr_group_members)

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
                
        _logsi.LogArray(SILevel.Verbose, "'%s': MediaPlayer zone group_members entity list was refreshed" % self.name, members)
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
        data:InstanceDataSoundTouchPlus = None
        for data in self.hass.data[DOMAIN].values():
            if data.media_player.entity_id == entity_id:
                client = data.client
                break

        # did we resolve it? if not, then log a message.
        if client is None:
            _logsi.LogError("'%s': MediaPlayer could not resolve entity id value of '%s' to a SoundTouch client instance for the '%s' method call" % (self.name, str(entity_id), serviceName))
            return None

        # return the client instance.
        _logsi.LogVerbose("'%s': MediaPlayer resolved entity id value of '%s' to SoundTouch client instance '%s' for the '%s' method call" % (self.name, str(entity_id), client.Device.DeviceName, serviceName))
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
        data:InstanceDataSoundTouchPlus = None
        for data in self.hass.data[DOMAIN].values():
            if data.client.Device.DeviceId == deviceId:
                entity_id = data.media_player.entity_id
                break

        # did we resolve it? if not, then log a message.
        if entity_id is None:
            _logsi.LogError("'%s': MediaPlayer could not resolve DeviceId value of '%s' to a media_player entity_id for the '%s' method call" % (self.name, str(deviceId), serviceName))
            return None

        # return the client instance.
        _logsi.LogVerbose("'%s': MediaPlayer resolved DeviceId value of '%s' to media_player entity_id '%s' for the '%s' method call" % (self.name, str(deviceId), entity_id, serviceName))
        return entity_id
    

    def _GetSourceItemByTitle(self, title:str) -> SourceItem:
        """
        Returns a `SourceItem` instance for the given source title value
        if a matching title was found in the source_list; otherwise, None.
        
        Args:
            title (str):
                Source title string to locate in the `SourceItems` cache
                configuration list.  
                Value is case-sensitive, and must match exactly.
                
        Returns:
            A `SourceItem` if the title argument value was found; otherwise, None.
        """
        # is source argument a source title value?
        sourceList:SourceList = self._client.GetSourceList(False)
        sourceItem:SourceItem = sourceList.GetSourceItemByTitle(title)
        if sourceItem is None:
            _logsi.LogVerbose("'%s': MediaPlayer source title '%s' was NOT resolved" % (self.name, title))
        else:
            _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer source title '%s' was resolved to %s" % (self.name, title, str(sourceItem)), sourceItem, excludeNonPublic=True)
        return sourceItem


    def _UpdateNowPlayingData(self, config:NowPlayingStatus) -> None:
        """
        Updates all media_player attributes that have to do with now playing information.
        """
        # update seek-related attributes.
        self._attr_media_position = config.Position
        self._attr_media_duration = config.Duration
        self._attr_media_position_updated_at = utcnow()
        
        # update shuffle related attributes.
        self._attr_shuffle = None
        if config.ShuffleSetting is not None:
            self._attr_shuffle = config.IsShuffleEnabled
        
        # update repeat related attributes.
        self._attr_repeat = None
        if config.IsRepeatEnabled:
            if config.RepeatSetting == RepeatSettingTypes.All.value:
                self._attr_repeat = RepeatMode.ALL.value
            elif config.RepeatSetting == RepeatSettingTypes.Off.value:
                self._attr_repeat = RepeatMode.OFF.value
            elif config.RepeatSetting == RepeatSettingTypes.One.value:
                self._attr_repeat = RepeatMode.ONE.value
               
    
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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['bassLevel'] = bassLevel
                parms['trebleLevel'] = trebleLevel
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_audio_tone_levels", str(parms)), parms)

            # if not supported then log a warning.
            if SoundTouchNodes.audioproducttonecontrols.Path not in self._client.ConfigurationCache:
                _logsi.LogWarning("'%s': MediaPlayer device does not support AudioProductToneControls; cannot change the tone levels" % self.name)
                return

            # get current tone levels.
            config:AudioProductToneControls = self._client.GetAudioProductToneControls()
        
            # set new tone control values.
            config.Bass.Value = bassLevel
            config.Treble.Value = bassLevel
            self._client.SetAudioProductToneControls(config)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

        
    def service_clear_source_nowplayingstatus(self, 
                                              sourceTitle:str,
                                              ) -> None:
        """
        Clears the NowPlayingStatus object for a given source title.
        """
        apiMethodParms:SIMethodParmListContext = None

        try:

            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            apiMethodParms.AppendKeyValue("sourceTitle", sourceTitle)
            _logsi.LogMethodParmList(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE % (self.name, 'service_clear_source_nowplayingstatus'), apiMethodParms)

            # get source and account values from source title.
            sourceList:SourceList = self._client.GetSourceList(refresh=False)
            sourceItem:SourceItem = sourceList.GetSourceItemByTitle(sourceTitle)

            # clear nowplaying status for source.
            cacheKey = "%s-%s:%s" % (SoundTouchNodes.nowPlaying.Path, sourceItem.Source, sourceItem.SourceAccount)
            if cacheKey in self._client.ConfigurationCache:
                del self._client.ConfigurationCache[cacheKey]
                _logsi.LogVerbose("'%s': NowPlayingStatus for source '%s' was removed" % (self.name, cacheKey))

            # inform Home Assistant of the status update.
            self.async_write_ha_state()
            return

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_musicservice_station_list(self, source:str, sourceAccount:str, sortType:str) -> NavigateResponse:
        """
        Retrieves a list of your stored stations from the specified music service (e.g. PANDORA, etc).

        Args:
            source (str):
                Music service source to navigate (e.g. "PANDORA", "STORED_MUSIC", etc).  
                This can also be a source title value (e.g. "Tunein").  
                The value is case-sensitive.
            sourceAccount (str):
                Music service source account (e.g. the music service user-id).  
                Ignored if the source argument contains a source title value.  
            sortType (str):
                Sort type used by the Music Service to sort the returned items by.  
                The value is case-sensitive.

        Returns:
            A `NavigateResponse` instance that contain the results.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['source'] = source
                parms['sourceAccount'] = sourceAccount
                parms['sortType'] = sortType
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_musicservice_station_list", str(parms)), parms)

            # is source argument a source title value?
            sourceItem = self._GetSourceItemByTitle(source)
            if sourceItem is not None:
                source = sourceItem.Source
                sourceAccount = sourceItem.SourceAccount

            criteria:Navigate = Navigate(source, sourceAccount, sortType=sortType)
            return self._client.GetMusicServiceStations(criteria)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
                
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_play_contentitem(self, name:str, source:str, sourceAccount:str, itemType:str, location:str, containerArt:str, isPresetable:bool):
        """
        Play media content from a content item source (e.g. TUNEIN station, etc) on a SoundTouch device.
        
        Args:
            name (str):
                Name of the content item (e.g. "K-LOVE Radio").
            source (str):
                Source to select to play the content (e.g. "TUNEIN").  
                This can also be a source title value (e.g. "Tunein").  
                The value is case-sensitive.
            sourceAccount (str):
                Source account this content item is played with.  
                Ignored if the source argument contains a source title value.  
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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['name'] = name
                parms['source'] = source
                parms['sourceAccount'] = sourceAccount
                parms['itemType'] = itemType
                parms['location'] = location
                parms['containerArt'] = containerArt
                parms['isPresetable'] = isPresetable
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_play_contentitem", str(parms)), parms)

            # is source argument a source title value?
            sourceItem:SourceItem = self._GetSourceItemByTitle(source)
            if sourceItem is not None:
                source = sourceItem.Source
                sourceAccount = sourceItem.SourceAccount

            # is this a LOCAL source?
            if source is not None and len(source) > 0 and source == 'LOCAL':
                _logsi.LogVerbose("LOCAL source detected - calling SelectLocalSource for player '%s'", self.entity_id)
                self._client.SelectLocalSource()
            
            # set content item to play, and play it.
            contentItem:ContentItem = ContentItem(source, itemType, location, sourceAccount, isPresetable, name, containerArt)
            self._client.PlayContentItem(contentItem)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                if to_player is not None:
                    parms['to_player'] = to_player.name
                parms['restore_volume'] = restore_volume
                parms['snapshot_only'] = snapshot_only
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_play_handoff", str(parms)), parms)
        
            if to_player is None:
                _logsi.LogWarning("'%s': MediaPlayer service 'service_play_handoff' argument 'to_player' cannot be null")
                return
        
            # take a snapshot of what we are currently playing.
            _logsi.LogVerbose("'%s': MediaPlayer is taking a snapshot", self.name)
            self._client.StoreSnapshot()

            # copy our snapshot settings to the TO player snapshot settings.
            _logsi.LogVerbose("'%s': MediaPlayer is copying snapshot settings TO player '%s'", self.name, to_player.name)
            to_player._client.SnapshotSettings.clear()
            for key in self._client.SnapshotSettings.keys():
                to_player._client.SnapshotSettings[key] = self._client.SnapshotSettings[key]

            # if only taking a snapshot then we are done.
            if snapshot_only:
                _logsi.LogVerbose("'%s': MediaPlayer snapshot copy only selected - play handoff complete", self.name)
                return
        
            # restore snapshot on TO player.
            _logsi.LogVerbose("'%s': MediaPlayer TO player '%s' is restoring snapshot settings", self.name, to_player.name)
            to_player._client.RestoreSnapshot(restore_volume)

            # turn FROM player off.
            _logsi.LogVerbose("'%s': MediaPlayer is being powered off", self.name)
            self.turn_off()

            _logsi.LogVerbose("'%s': MediaPlayer play handoff to player '%s' is complete", self.name, to_player.name)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['message'] = message
                parms['artist'] = artist
                parms['album'] = album
                parms['track'] = track
                parms['ttsUrl'] = ttsUrl
                parms['volumeLevel'] = volumeLevel
                parms['appKey'] = appKey
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_play_tts", str(parms)), parms)
        
            self._client.PlayNotificationTTS(message, ttsUrl, artist, album, track, volumeLevel, appKey)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['url'] = url
                parms['artist'] = artist
                parms['album'] = album
                parms['track'] = track
                parms['volumeLevel'] = volumeLevel
                parms['appKey'] = appKey
                parms['getMetadataFromUrlFile'] = getMetadataFromUrlFile
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_play_url", str(parms)), parms)

            self._client.PlayUrl(url, artist, album, track, volumeLevel, appKey, getMetadataFromUrlFile)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_preset_list(self) -> PresetList:
        """
        Retrieves the list of presets defined for a device.

        Returns:
            A `PresetList` instance that contains defined presets.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "service_preset_list")
            
            return self._client.GetPresetList(True, resolveSourceTitles=True)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['sshPort'] = sshPort
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_reboot_device", str(parms)), parms)

            self._client.Device.RebootDevice(sshPort)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_recent_list(self) -> RecentList:
        """
        Retrieves the list of recently played items defined for a device.

        Returns:
            A `RecentList` instance that contains defined recently played items.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "service_recent_list")
            
            return self._client.GetRecentList(True, resolveSourceTitles=True)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['key_id'] = key_id
                parms['key_state'] = key_state
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_remote_keypress", str(parms)), parms)

            if key_state is None:
                key_state = KeyStates.Both.value
                if key_id is not None and key_id.startswith('PRESET_'):
                    key_state = KeyStates.Release.value
            key_state = key_state.lower()

            self._client.Action(key_id, key_state)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_snapshot_restore(self, restore_volume:bool) -> None:
        """
        Restore now playing settings from a snapshot that was previously taken by 
        the service_snapshot_store method.
        
        Args:
            restore_volume (bool):
                True to restore volume setting; otherwise, False to not change volume.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                parms['restore_volume'] = restore_volume
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_snapshot_restore", str(parms)), parms)

            # if not restoring volume then remove it from the snapshot settings.
            if not restore_volume:
                if SoundTouchNodes.volume.Path in self._client.SnapshotSettings:
                    self._client.SnapshotSettings.pop(SoundTouchNodes.volume.Path)

            self._client.RestoreSnapshot()

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_snapshot_store(self) -> None:
        """
        Store now playing settings to a snapshot, which can be restored later via
        the service_snapshot_restore method.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "service_snapshot_store")
            
            self._client.StoreSnapshot()

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_update_source_nowplayingstatus(self, 
                                               sourceTitle:str,
                                               album:str, artist:str, artistId:str, artUrl:str, description:str, 
                                               duration:int, genre:str, playStatus:str, position:int, 
                                               sessionId:str, stationLocation:str, stationName:str,
                                               track:str, trackId:str,
                                               ) -> None:
        """
        Updates the NowPlayingStatus object for a given source title.
        """
        apiMethodParms:SIMethodParmListContext = None

        try:

            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            apiMethodParms.AppendKeyValue("sourceTitle", sourceTitle)
            apiMethodParms.AppendKeyValue("album", album)
            apiMethodParms.AppendKeyValue("artist", artist)
            apiMethodParms.AppendKeyValue("artistId", artistId)
            apiMethodParms.AppendKeyValue("artUrl", artUrl)
            apiMethodParms.AppendKeyValue("description", description)
            apiMethodParms.AppendKeyValue("duration", duration)
            apiMethodParms.AppendKeyValue("genre", genre)
            apiMethodParms.AppendKeyValue("playStatus", playStatus)
            apiMethodParms.AppendKeyValue("position", position)
            apiMethodParms.AppendKeyValue("sessionId", sessionId)
            apiMethodParms.AppendKeyValue("stationLocation", stationLocation)
            apiMethodParms.AppendKeyValue("stationName", stationName)
            apiMethodParms.AppendKeyValue("track", track)
            apiMethodParms.AppendKeyValue("trackId", trackId)
            _logsi.LogMethodParmList(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE % (self.name, 'service_update_source_nowplayingstatus'), apiMethodParms)

            # validations.
            if duration == 0: duration = None
            if position == 0: position = None
            
            # get source and account values from source title.
            sourceList:SourceList = self._client.GetSourceList(refresh=False)
            sourceItem:SourceItem = sourceList.GetSourceItemByTitle(sourceTitle)

            # call service.
            config:NowPlayingStatus = self._client.UpdateNowPlayingStatusForSource(
                                            sourceItem.Source, sourceItem.SourceAccount, 
                                            album, artist, artistId, artUrl, description,
                                            duration, genre, playStatus, position, 
                                            sessionId, stationLocation, stationName,
                                            track, trackId)
            
            # update nowplaying attributes.
            self._UpdateNowPlayingData(config)

            # inform Home Assistant of the status update.
            self.async_write_ha_state()
            return

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def service_zone_toggle_member(self, zone_member_player:MediaPlayerEntity) -> None:
        """
        Toggles the given zone member in the master device's zone.  If the member exists in the
        zone then it is removed; if the member does not exist in the zone, then it is added.
        
        Args:
            zone_member_player (MediaPlayerEntity):
                A SoundTouch MediaPlayerEntity that will be toggled in the master zone.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            if _logsi.IsOn(SILevel.Verbose):
                parms:dict = {}
                if zone_member_player is not None:
                    parms['zone_member_player'] = zone_member_player.name
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS % (self.name, "service_zone_toggle_member", str(parms)), parms)
        
            if zone_member_player is None:
                _logsi.LogWarning("'%s': MediaPlayer service 'service_zone_toggle_member' argument 'zone_member_player' cannot be null")
                return

            # toggle the zone member.
            _logsi.LogVerbose("Master Zone player '%s' is toggling zone member '%s'", self.entity_id, zone_member_player.entity_id)
            zoneMember:ZoneMember = ZoneMember(zone_member_player._client.Device.Host, zone_member_player._client.Device.DeviceId)
            self._client.ToggleZoneMember(zoneMember)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SoundTouchError as ex:
            raise HomeAssistantError(ex.Message)
        
        finally:
                
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


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
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose("'%s': MediaPlayer async_added_to_hass is starting" % self.name)
        
            # call base class method.
            await super().async_added_to_hass()
        
            # load list of supported sources.
            _logsi.LogVerbose("'%s': MediaPlayer is loading list of ALL sources that the device supports" % self.name)
            config:SourceList = await self.hass.async_add_executor_job(self._client.GetSourceList, True)

            if self._attr_source_list is None or len(self._attr_source_list) == 0:
                _logsi.LogVerbose("'%s': MediaPlayer source_list is not defined in configuration options; defaulting to ALL sources" % self.name)
                self._attr_source_list = config.ToSourceTitleArray()
            
            _logsi.LogVerbose("'%s': MediaPlayer source_list = %s" % (self.name, str(self._attr_source_list)))
            _logsi.LogVerbose("'%s': MediaPlayer current source = %s" % (self.name, str(self.source)))

            # load list of supported sound modes.
            if SoundTouchNodes.audiodspcontrols.Path in self._client.Device.SupportedUris:
                _logsi.LogVerbose("'%s': MediaPlayer is loading list of sound modes (audiodspcontrols) that the device supports" % self.name)
                dspconfig:AudioDspControls = await self.hass.async_add_executor_job(self._client.GetAudioDspControls, True)

                if self._attr_sound_mode_list is None or len(self._attr_sound_mode_list) == 0:
                    self._attr_sound_mode_list = dspconfig.ToSupportedAudioModeTitlesArray()
                
                # load current sound mode.
                self._attr_sound_mode = AudioDspAudioModes.GetNameByValue(dspconfig.AudioMode)

                _logsi.LogVerbose("'%s': MediaPlayer sound_mode_list = %s" % (self.name, str(self._attr_sound_mode_list)))
                _logsi.LogVerbose("'%s': MediaPlayer current sound_mode = %s" % (self.name, str(self._attr_sound_mode)))
            else:
                _logsi.LogVerbose("'%s': MediaPlayer device does not support sound modes (audiodspcontrols)" % self.name)
        
            # load list of supported tone levels.
            if SoundTouchNodes.audioproducttonecontrols.Path in self._client.Device.SupportedUris:
                _logsi.LogVerbose("'%s': MediaPlayer is loading bass tone range levels (audioproducttonecontrols) that the device supports" % self.name)
                await self.hass.async_add_executor_job(self._client.GetAudioProductToneControls, True)
            else:
                _logsi.LogVerbose("'%s': MediaPlayer device does not support tone level adjustments (audioproducttonecontrols)" % self.name)

            # load zone configuration.
            if SoundTouchNodes.getZone.Path in self._client.Device.SupportedUris:
                _logsi.LogVerbose("'%s': MediaPlayer is loading zone configuration" % self.name)
                config:Zone = await self.hass.async_add_executor_job(self._client.GetZoneStatus, True)
                self._attr_group_members = self._BuildZoneMemberEntityIdList(config)

            # if websocket support is disabled then we are done at this point.
            if self._socket is None:
                return
        
            _logsi.LogVerbose("'%s': MediaPlayer is adding notification event listeners" % self.name)

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
            self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketClose, self._OnSoundTouchWebSocketCloseEvent)
            self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketOpen, self._OnSoundTouchWebSocketConnectionEvent)
            self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketError, self._OnSoundTouchWebSocketErrorEvent)
            self._socket.AddListener(SoundTouchNotifyCategorys.WebSocketPong, self._OnSoundTouchWebSocketPongEvent)

            # start receiving device event notifications.
            _logsi.LogVerbose("'%s': MediaPlayer is starting websocket notifications" % self.name)
            self._socket.StartNotification()

            # trace.
            _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer is now fully initialized and added to HAAS: name=%s, unique_id=%s, entity_id=%s" % (self.name, self.name, self.unique_id, self.entity_id), self)
            _logsi.LogVerbose("'%s': MediaPlayer async_added_to_hass is complete" % self.name)

        finally:
                
            _logsi.LeaveMethod(SILevel.Debug)


    async def async_will_remove_from_hass(self) -> None:
        """
        Entity being removed from hass (the opposite of async_added_to_hass).

        Remove any registered call backs here.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
       
            # stop receiving device event notifications.
            if self._socket is not None:
                _logsi.LogVerbose("'%s': MediaPlayer is stopping websocket notifications" % self.name)
                self._socket.StopNotification()
                self._socket.ClearListeners()
                self._socket = None

        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer async_will_remove_from_hass exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    async def async_browse_media(self, media_content_type:MediaType|str|None=None, media_content_id:str|None=None) -> BrowseMedia:
        """
        Implement the websocket media browsing helper.
        
        Args:
            media_content_type (MediaType):
                The type of media to browse for.
            media_content_id (str):
                The media content id root node to start browsing at.
                
        Returns:
            A `BrowseMedia` object.
        """
        methodParms:SIMethodParmListContext = None
        
        try:

            # trace.
            methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            methodParms.AppendKeyValue("media_content_type", media_content_type)
            methodParms.AppendKeyValue("media_content_id", media_content_id)
            _logsi.LogMethodParmList(SILevel.Verbose, "'%s': MediaPlayer is browsing for media content type '%s'" % (self.name, media_content_type), methodParms)

            # browse soundtouch device media.
            if media_content_type is None and media_content_id is None:

                # if SpotifyPlus integration is not installed, then hide spotify icon.
                isSpotifyPlusInstalled:bool = self._IsSpotifyPlusIntegrationInstalled()
                LIBRARY_MAP[BrowsableMedia.SPOTIFY_LIBRARY_INDEX]["is_index_item"] = isSpotifyPlusInstalled

                # handle initial media browser selection (e.g. show the starting index).
                _logsi.LogVerbose("'%s': MediaPlayer is browsing main media library index content id '%s'" % (self.name, media_content_id))
                return await async_browse_media_library_index(
                    self.hass,
                    self.data,
                    self.name,
                    self.source,
                    LIBRARY_MAP,
                    BrowsableMedia.LIBRARY_INDEX,
                    media_content_type,
                    media_content_id,
                )

            elif media_content_type == BrowsableMedia.SPOTIFY_LIBRARY_INDEX.value:

                # verify SpotifyPlus integration configuration.
                self._VerifySpotifyPlusIntegrationSetup()

                # handle spotify media browser selection (e.g. show the starting Spotify index).
                _logsi.LogVerbose("'%s': MediaPlayer is browsing Spotify media library index content id '%s'" % (self.name, media_content_id))
                return await async_browse_media_library_index(
                    self.hass,
                    self.data,
                    self.name,
                    self.source,
                    SPOTIFY_LIBRARY_MAP,
                    BrowsableMedia.SPOTIFY_LIBRARY_INDEX,
                    media_content_type,
                    media_content_id,
                )

            elif media_content_id is not None and media_content_id.startswith('media-source://'):

                # handle base media library item selection.
                _logsi.LogVerbose("'%s': MediaPlayer is browsing media-source content id '%s'" % (self.name, media_content_id))
                return await media_source.async_browse_media(
                    self.hass,
                    media_content_id
                )

            else:
                
                # set library map based upon the content we are currently browsing.
                library_map:dict = LIBRARY_MAP
                if media_content_type.startswith('spotify_'):
                    library_map:dict = SPOTIFY_LIBRARY_MAP
                
                # handle soundtouchplus media library selection.
                # note that this is NOT async, as SoundTouchClient is not async!
                _logsi.LogVerbose("'%s': MediaPlayer is browsing media node content id '%s'" % (self.name, media_content_id))
                return await self.hass.async_add_executor_job(
                    browse_media_node,
                    self.hass,
                    self.data,
                    self.name,
                    self.source,
                    library_map,
                    media_content_type,
                    media_content_id,
                )

        except Exception as ex:
            
            # trace.
            _logsi.LogException("'%s': MediaPlayer async_browse_media exception: %s" % (self.name, str(ex)), ex, logToSystemLogger=False)
            raise HomeAssistantError(str(ex)) from ex
        
        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def _IsSpotifyPlusIntegrationInstalled(self) -> bool:
        """
        Returns a flag indicating if the SpotifyPlus integration is installed (True) or not (False).
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose("'%s': MediaPlayer is verifying SpotifyPlus integration is installed" % self.name)

            # SpotifyPlus integration common service name check.
            # the service name will NOT exist if the integration is not installed.
            # the service name will exist if the integration is installed, though it could
            # be disabled (will check for that condition later).
            checkServiceName:str = "get_playlist"
            isSpotifyPlusInstalled:bool = self.hass.services.has_service(DOMAIN_SPOTIFYPLUS, checkServiceName)

            # trace.
            if _logsi.IsOn(SILevel.Verbose):
                _logsi.LogVerbose("'%s': MediaPlayer SpotifyPlus service check: '%s' = '%s'" % (self.name, checkServiceName, str(isSpotifyPlusInstalled)))
                if isSpotifyPlusInstalled:
                    # if SpotifyPlus integration IS installed, then log its services list.
                    service = self.hass.services.async_services().get(DOMAIN_SPOTIFYPLUS.lower(), [])
                    _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer SpotifyPlus service list" % self.name, service, prettyPrint=True)
                else:
                    # if SpotifyPlus integration is NOT installed, then log the services that ARE installed in case we need it.
                    serviceAll = self.hass.services.async_services()
                    _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer ALL services list" % self.name, serviceAll, prettyPrint=True)

            return isSpotifyPlusInstalled

        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def _VerifySpotifyPlusIntegrationSetup(self) -> None:
        """
        Verifies that the SpotifyPlus integration is installed, and the media player entity id
        is valid and available (not disabled).
        """
        entity_registry:EntityRegistry = None
        
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose("'%s': MediaPlayer is verifying SpotifyPlus integration configuration" % self.name)

            # is SpotifyPlus integration installed?
            if not self._IsSpotifyPlusIntegrationInstalled():
                raise HomeAssistantError("'%s': The SpotifyPlus integration is required in order to browse the Spotify media library" % self.name)

            # get the spotify media player entity id from options.
            # if one has not been configured, then it's a problem.
            spotifyMPEntityId:str = self.data.OptionSpotifyMediaPlayerEntityId
            if spotifyMPEntityId is None:
                raise HomeAssistantError("'%s': A SpotifyPlus media player entity id has not been assigned in SoundTouchPlus configuration options" % self.name)

            # is the specified entity id in the hass entity registry?
            # it will NOT be in the entity registry if it's deleted.
            # it WILL be in the entity registry if it is disabled, with disabled property = True.
            entity_registry = er.async_get(self.hass)
            registry_entry:RegistryEntry = entity_registry.async_get(spotifyMPEntityId)
            _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer RegistryEntry for entity_id: '%s'" % (self.name, spotifyMPEntityId), registry_entry)

            # raise exceptions if SpotifyPlus Entity is not configured or is disabled.
            if registry_entry is None:
                raise HomeAssistantError("'%s': The SpotifyPlus media player entity '%s' does not exist (recently deleted maybe?); update the SpotifyPlus media player in the SoundTouchPlus options configuration" % (self.name, spotifyMPEntityId))
            if registry_entry.disabled:
                raise HomeAssistantError("'%s': The SpotifyPlus media player entity '%s' is currently disabled; re-enable the SpotifyPlus media player, or choose another SpotifyPlus media player in the SoundTouchPlus options configuration" % (self.name, spotifyMPEntityId))

            # modify spotify library map title to append the spotifyplus media
            # player friendly name that will be used to query spotify for data.
            titleWithName = SPOTIFY_LIBRARY_MAP[BrowsableMedia.SPOTIFY_LIBRARY_INDEX].get("title_with_name","")
            titleWithName = titleWithName % (registry_entry.name or registry_entry.original_name)
            SPOTIFY_LIBRARY_MAP[BrowsableMedia.SPOTIFY_LIBRARY_INDEX]["title"] = titleWithName

        finally:

            # free resources.
            entity_registry = None

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

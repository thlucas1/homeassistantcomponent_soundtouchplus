"""
The soundtouchplus integration.
"""
import functools
import logging
from urllib3._version import __version__ as urllib3_version
import voluptuous as vol

from bosesoundtouchapi import *
from bosesoundtouchapi.uri import *
from bosesoundtouchapi.models import *
from bosesoundtouchapi.ws import *

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .instancedata_soundtouchplus import InstanceDataSoundTouchPlus
from .stappmessages import STAppMessages
from .const import (
    DOMAIN,
    CONF_PORT_WEBSOCKET,
    CONF_PING_WEBSOCKET_INTERVAL,
    CONF_OPTION_RECENTS_CACHE_MAX_ITEMS,
    CONF_OPTION_SOURCE_LIST,
    DEFAULT_PING_WEBSOCKET_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_PORT_WEBSOCKET,
    SERVICE_AUDIO_TONE_LEVELS,
    SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS,
    SERVICE_GET_SOURCE_LIST,
    SERVICE_MUSICSERVICE_STATION_LIST,
    SERVICE_PLAY_CONTENTITEM,
    SERVICE_PLAY_HANDOFF,
    SERVICE_PLAY_TTS,
    SERVICE_PLAY_URL,
    SERVICE_PRESET_LIST,
    SERVICE_PRESET_REMOVE,
    SERVICE_REBOOT_DEVICE,
    SERVICE_RECENT_LIST,
    SERVICE_RECENT_LIST_CACHE,
    SERVICE_REMOTE_KEYPRESS,
    SERVICE_SNAPSHOT_RESTORE,
    SERVICE_SNAPSHOT_STORE,
    SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS,
    SERVICE_ZONE_TOGGLE_MEMBER
)

_LOGGER = logging.getLogger(__name__)

try:

    from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIConfigurationTimer, SIColors, SIMethodParmListContext

    # load SmartInspect settings from a configuration settings file.
    siConfigPath: str = "./smartinspect.cfg"
    SIAuto.Si.LoadConfiguration(siConfigPath)

    # start monitoring the configuration file for changes, and reload it when it changes.
    # this will check the file for changes every 60 seconds.
    siConfig:SIConfigurationTimer = SIConfigurationTimer(SIAuto.Si, siConfigPath)

    # get smartinspect logger reference; create a new session for this module name.
    _logsi:SISession = SIAuto.Si.GetSession(__name__)
    if (_logsi == None):
        _logsi = SIAuto.Si.AddSession(__name__, True)
    _logsi.SystemLogger = _LOGGER
    _logsi.LogSeparator(SILevel.Error)
    _logsi.LogVerbose("__init__.py HAS SoundTouchPlus: initialization")
    _logsi.LogAppDomain(SILevel.Verbose)
    _logsi.LogSystem(SILevel.Verbose)

except Exception as ex:

    _LOGGER.warning("HAS SoundtouchPlus could not init SmartInspect debugging! %s", str(ex))

PLATFORMS:list[str] = [Platform.MEDIA_PLAYER]
""" 
List of platforms to support. 
There should be a matching .py file for each (e.g. "media_player")
"""

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
""" Configuration schema. """

# -----------------------------------------------------------------------------------
# Custom Service Schemas.
# -----------------------------------------------------------------------------------
SERVICE_AUDIO_TONE_LEVELS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("bass_level", default=0): vol.All(vol.Range(min=-100,max=100)),
        vol.Required("treble_level", default=0): vol.All(vol.Range(min=-100,max=100)),
    }
)

SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("source_title"): cv.string,
    }
)

SERVICE_GET_SOURCE_LIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

SERVICE_MUSICSERVICE_STATION_LIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("source"): cv.string,
        vol.Required("source_account"): cv.string,
        vol.Optional("sort_type", default='stationName'): cv.string
    }
)

SERVICE_PLAY_CONTENTITEM_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("name"): cv.string,
        vol.Required("source"): cv.string,
        vol.Optional("source_account"): cv.string,
        vol.Optional("item_type"): cv.string,
        vol.Optional("location"): cv.string,
        vol.Optional("container_art"): cv.string,
        vol.Required("is_presetable", default=False): cv.boolean
    }   
)

SERVICE_PLAY_HANDOFF_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id_from"): cv.entity_id,
        vol.Required("entity_id_to"): cv.entity_id,
        vol.Required("restore_volume", default=False): cv.boolean,
        vol.Required("snapshot_only", default=False): cv.boolean
    }
)

SERVICE_PLAY_TTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("message"): cv.string,
        vol.Optional("artist"): cv.string,
        vol.Optional("album"): cv.string,
        vol.Optional("track"): cv.string,
        vol.Optional("tts_url"): cv.string,
        vol.Optional("volume_level", default=0): vol.All(vol.Range(min=0,max=70)),
        vol.Optional("app_key"): cv.string
    }
)

SERVICE_PLAY_URL_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("url"): cv.string,
        vol.Optional("artist"): cv.string,
        vol.Optional("album"): cv.string,
        vol.Optional("track"): cv.string,
        vol.Optional("volume_level", default=0): vol.All(vol.Range(min=0,max=70)),
        vol.Optional("app_key"): cv.string,
        vol.Required("get_metadata_from_url_file", default=False): cv.boolean
    }
)

SERVICE_PRESET_LIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("include_empty_slots", default=False): cv.boolean,
    }
)

SERVICE_PRESET_REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("preset_id", default=1): vol.All(vol.Range(min=1,max=6)),
    }
)

SERVICE_REBOOT_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("port", default=17000): vol.All(vol.Range(min=1,max=65535))
    }
)

SERVICE_RECENT_LIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

SERVICE_RECENT_LIST_CACHE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

SERVICE_REMOTE_KEYPRESS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("key_id"): cv.string,
        vol.Optional("key_state", default=KeyStates.Both.value): cv.string,
    }
)

SERVICE_SNAPSHOT_RESTORE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("restore_volume", default=True): cv.boolean,
    }
)

SERVICE_SNAPSHOT_STORE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id
    }
)

SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("source_title"): cv.string,
        vol.Optional("album"): cv.string,
        vol.Optional("artist"): cv.string,
        vol.Optional("artist_id"): cv.string,
        vol.Optional("art_url"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("duration", default=0): vol.All(vol.Range(min=0,max=99999999)),
        vol.Optional("genre"): cv.string,
        vol.Optional("play_status"): cv.string,
        vol.Optional("position", default=0): vol.All(vol.Range(min=0,max=99999999)),
        vol.Optional("session_id"): cv.string,
        vol.Optional("station_location"): cv.string,
        vol.Optional("station_name"): cv.string,
        vol.Optional("track"): cv.string,
        vol.Optional("track_id"): cv.string,
    }
)

SERVICE_ZONE_TOGGLE_MEMBER_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id_master"): cv.entity_id,
        vol.Required("entity_id_member"): cv.entity_id,
    }
)


def _trace_LogTextFile(filePath: str, title: str) -> None:
    """
    Log the contents of the specified text file to the SmartInspect trace log.
    
    Args:
        filePath (str):
            Fully-qualified file path to log.
        title (str):
            Title to assign to the log entry.

    """
    _logsi.LogTextFile(SILevel.Verbose, title, filePath)


async def async_setup(hass:HomeAssistant, config:ConfigType) -> bool:
    """
    Set up the component.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        config (ConfigType):
            HomeAssistant validation configuration object.

    The __init__.py module "async_setup" method is executed once for the component 
    configuration, no matter how many devices are configured for the component.  
    It takes care of loading the services that the component provides, as well as the 
    ConfigType dictionary.  The ConfigType dictionary contains Home Assistant configuration 
    entries that reference this component type: 'default_config', 'frontend' (themes, etc), 
    'automation', 'script', and 'scenes' sub-dictionaries.
    """
    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        if _logsi.IsOn(SILevel.Verbose):

            _logsi.LogObject(SILevel.Verbose, "Component async_setup for configuration type", config)

            # log the manifest file contents.
            # as of HA 2024.6, we have to use an executor job to do this as the trace uses a blocking file open / read call.
            myConfigDir:str = "%s/custom_components/%s" % (hass.config.config_dir, DOMAIN)
            myManifestPath:str = "%s/manifest.json" % (myConfigDir)
            await hass.async_add_executor_job(_trace_LogTextFile, myManifestPath, "Integration Manifest File (%s)" % myManifestPath)
    
            # log verion information for supporting packages.
            _logsi.LogValue(SILevel.Verbose, "urllib3 version", urllib3_version)

            for item in config:
                itemKey:str = str(item)
                itemObj = config[itemKey]
                if isinstance(itemObj,dict):
                    _logsi.LogDictionary(SILevel.Verbose, "ConfigType '%s' data (dictionary)" % itemKey, itemObj, prettyPrint=True)
                elif isinstance(itemObj,list):
                    _logsi.LogArray(SILevel.Verbose, "ConfigType '%s' data (list)" % itemKey, itemObj)
                else:
                    _logsi.LogObject(SILevel.Verbose, "ConfigType '%s' data (object)" % (itemKey), itemObj)


        async def service_handle_entity(service:ServiceCall) -> None:
            """
            Handle service requests that utilize a single entity.

            Args:
                service (ServiceCall):
                    ServiceCall instance that contains service data (requested service name, field parameters, etc).
            """
            try:

                # trace.
                _logsi.EnterMethod(SILevel.Debug)
                _logsi.LogVerbose(STAppMessages.MSG_SERVICE_CALL_START, service.service, "service_handle_entity")
                _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_PARM, service)
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_DATA, service.data)

                # get media_player instance from service parameter; if not found, then we are done.
                player = _GetEntityFromServiceData(hass, service, "entity_id")
                if player is None:
                    return

                # process service request.
                if service.service == SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS:
                    source_title = service.data.get("source_title")
                    await hass.async_add_executor_job(player.service_clear_source_nowplayingstatus, source_title)

                elif service.service == SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS:
                    source_title = service.data.get("source_title")
                    album = service.data.get("album")
                    artist = service.data.get("artist")
                    artist_id = service.data.get("artist_id")
                    art_url = service.data.get("art_url")
                    description = service.data.get("description")
                    duration = service.data.get("duration")
                    genre = service.data.get("genre")
                    play_status = service.data.get("play_status")
                    position = service.data.get("position")
                    session_id = service.data.get("session_id")
                    station_location = service.data.get("station_location")
                    station_name = service.data.get("station_name")
                    track = service.data.get("track")
                    track_id = service.data.get("track_id")
                    await hass.async_add_executor_job(player.service_update_source_nowplayingstatus, source_title, 
                                                      album, artist, artist_id, art_url, description, duration, genre, play_status, 
                                                      position, session_id, station_location, station_name, track, track_id)

                elif service.service == SERVICE_SNAPSHOT_STORE:
                    await hass.async_add_executor_job(player.service_snapshot_store)

                elif service.service == SERVICE_SNAPSHOT_RESTORE:
                    restore_volume = service.data.get("restore_volume")
                    await hass.async_add_executor_job(player.service_snapshot_restore, restore_volume)

                elif service.service == SERVICE_REMOTE_KEYPRESS:
                    key_id = service.data.get("key_id")
                    key_state = service.data.get("key_state")
                    if key_id is None:
                        _logsi.LogError(STAppMessages.MSG_SERVICE_ARGUMENT_NULL, "key_id", service.service)
                        return
                    if key_state is None:
                        key_state = KeyStates.Both
                    await hass.async_add_executor_job(player.service_remote_keypress, key_id, key_state)

                elif service.service == SERVICE_REBOOT_DEVICE:
                    port = service.data.get("port")
                    await hass.async_add_executor_job(player.service_reboot_device, port)

                elif service.service == SERVICE_PLAY_CONTENTITEM:
                    name = service.data.get("name")
                    source = service.data.get("source")
                    source_account = service.data.get("source_account")
                    item_type = service.data.get("item_type")
                    location = service.data.get("location")
                    container_art = service.data.get("container_art")
                    is_presetable = service.data.get("is_presetable")
                    await hass.async_add_executor_job(player.service_play_contentitem, name, source, source_account, item_type, location, container_art, is_presetable)

                elif service.service == SERVICE_PLAY_TTS:
                    message = service.data.get("message")
                    artist = service.data.get("artist")
                    album = service.data.get("album")
                    track = service.data.get("track")
                    tts_url = service.data.get("tts_url")
                    volume_level = service.data.get("volume_level")
                    app_key = service.data.get("app_key")
                    await hass.async_add_executor_job(player.service_play_tts, message, artist, album, track, tts_url, volume_level, app_key)

                elif service.service == SERVICE_PLAY_URL:
                    url = service.data.get("url")
                    artist = service.data.get("artist")
                    album = service.data.get("album")
                    track = service.data.get("track")
                    volume_level = service.data.get("volume_level")
                    app_key = service.data.get("app_key")
                    get_metadata_from_url_file = service.data.get("get_metadata_from_url_file")
                    await hass.async_add_executor_job(player.service_play_url, url, artist, album, track, volume_level, app_key, get_metadata_from_url_file)

                elif service.service == SERVICE_PRESET_REMOVE:
                    preset_id = service.data.get("preset_id")
                    await hass.async_add_executor_job(player.service_preset_remove, preset_id)

                elif service.service == SERVICE_AUDIO_TONE_LEVELS:
                    bass_level = service.data.get("bass_level")
                    treble_level = service.data.get("treble_level")
                    await hass.async_add_executor_job(player.service_audio_tone_levels, bass_level, treble_level)

                else:
                    _logsi.LogError(STAppMessages.MSG_SERVICE_REQUEST_UNKNOWN, service.service, "service_handle_entity")
                    return
            
            except HomeAssistantError as ex: 
                
                # log error, but not to system logger as HA will take care of it.
                _logsi.LogError(str(ex), logToSystemLogger=False)
                raise
            
            except Exception as ex:

                # log exception, but not to system logger as HA will take care of it.
                _logsi.LogException(STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION % (service.service, "service_handle_entity"), ex, logToSystemLogger=False)
                raise
            
            finally:
                
                # trace.
                _logsi.LeaveMethod(SILevel.Debug)


        async def service_handle_entityfromto(service: ServiceCall) -> None:
            """
            Handle service requests that utilize a single FROM entity and a single TO entity.

            Args:
                service (ServiceCall):
                    ServiceCall instance that contains service data (requested service name, field parameters, etc).
            """
            try:

                # trace.
                _logsi.EnterMethod(SILevel.Debug)
                _logsi.LogVerbose(STAppMessages.MSG_SERVICE_CALL_START, service.service, "service_handle_entityfromto")
                _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_PARM, service)
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_DATA, service.data)

                # process service request.
                if service.service == SERVICE_PLAY_HANDOFF:

                    # get player instance from service parameter; if not found, then we are done.
                    from_player = _GetEntityFromServiceData(hass, service, "entity_id_from")
                    if from_player is None:
                        return

                    # get player instance from service parameter; if not found, then we are done.
                    to_player = _GetEntityFromServiceData(hass, service, "entity_id_to")
                    if to_player is None:
                        return

                    # if FROM and TO player are the same then don't allow it.
                    if from_player.entity_id == to_player.entity_id:
                        _logsi.LogWarning("FROM and TO players (id='%s') are the same; handoff not needed", str(to_player.entity_id))
                        return

                    # process play handoff service.
                    restore_volume = service.data.get("restore_volume")
                    snapshot_only = service.data.get("snapshot_only")
                    await hass.async_add_executor_job(from_player.service_play_handoff, to_player, restore_volume, snapshot_only)

                elif service.service == SERVICE_ZONE_TOGGLE_MEMBER:

                    # get player instance from service parameter; if not found, then we are done.
                    from_player = _GetEntityFromServiceData(hass, service, "entity_id_master") # for zone services
                    if from_player is None:
                        return

                    # get player instance from service parameter; if not found, then we are done.
                    to_player = _GetEntityFromServiceData(hass, service, "entity_id_member") # for zone services
                    if to_player is None:
                        return

                    # if FROM and TO player are the same then don't allow it.
                    if from_player.entity_id == to_player.entity_id:
                        _logsi.LogWarning("FROM and TO players (id='%s') are the same; cannot toggle the master zone", str(to_player.entity_id))
                        return

                    # process zone toggle member service.
                    await hass.async_add_executor_job(from_player.service_zone_toggle_member, to_player)

                else:
                    _logsi.LogError(STAppMessages.MSG_SERVICE_REQUEST_UNKNOWN, service.service, "service_handle_entityfromto")
                    return
            
            except HomeAssistantError as ex: 
                
                # log error, but not to system logger as HA will take care of it.
                _logsi.LogError(str(ex), logToSystemLogger=False)
                raise
            
            except Exception as ex:
            
                # log exception, but not to system logger as HA will take care of it.
                _logsi.LogException(STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION % (service.service, "service_handle_entityfromto"), ex, logToSystemLogger=False)
                raise

            finally:
                
                # trace.
                _logsi.LeaveMethod(SILevel.Debug)


        async def service_handle_getlist(service: ServiceCall) -> ServiceResponse:
            """
            Handle service request to retrieve a list of presets for an entity.

            Args:
                service (ServiceCall):
                    ServiceCall instance that contains service data (requested service name, field parameters, etc).
            """
            try:

                # trace.
                _logsi.EnterMethod(SILevel.Debug)
                _logsi.LogVerbose(STAppMessages.MSG_SERVICE_CALL_START, service.service, "service_handle_getlist")
                _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_PARM, service)
                _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_DATA, service.data)

                # get player instance from service parameter; if not found, then we are done.
                player = _GetEntityFromServiceData(hass, service, "entity_id")
                if player is None:
                    return

                response:dict = {}

                # process service request.
                if service.service == SERVICE_GET_SOURCE_LIST:

                    # get list of sources defined for the device.
                    results:SourceList = await hass.async_add_executor_job(player.service_get_source_list)
                    response = results.ToDictionary()

                elif service.service == SERVICE_MUSICSERVICE_STATION_LIST:

                    # get list of music service stations.
                    source = service.data.get("source")
                    source_account = service.data.get("source_account")
                    sort_type = service.data.get("sort_type")
                    results:NavigateResponse = await hass.async_add_executor_job(player.service_musicservice_station_list, source, source_account, sort_type)
                    response = results.ToDictionary()

                elif service.service == SERVICE_PRESET_LIST:

                    # get list of presets defined for the device.
                    include_empty_slots = service.data.get("include_empty_slots")
                    if include_empty_slots is None:
                        include_empty_slots = False
                    results:PresetList = await hass.async_add_executor_job(player.service_preset_list)
                    response = results.ToDictionary(includeEmptyPresets=include_empty_slots)

                elif service.service == SERVICE_RECENT_LIST:

                    # get list of recently played items defined for the device.
                    results:RecentList = await hass.async_add_executor_job(player.service_recent_list)
                    response = results.ToDictionary()

                elif service.service == SERVICE_RECENT_LIST_CACHE:

                    # get list of recently played cached items defined for the device.
                    results:RecentList = await hass.async_add_executor_job(player.service_recent_list_cache)
                    response = results.ToDictionary()

                # build list of items to return.
                _logsi.LogDictionary(SILevel.Verbose, "Service Response data: '%s'" % (service.service), response, prettyPrint=True)
                return response 

            except HomeAssistantError as ex: 
                
                # log error, but not to system logger as HA will take care of it.
                _logsi.LogError(str(ex), logToSystemLogger=False)
                raise
            
            except Exception as ex:
                
                # log exception, but not to system logger as HA will take care of it.
                _logsi.LogException(STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION % (service.service, "service_handle_getlist"), ex, logToSystemLogger=False)
                raise

            finally:
                
                # trace.
                _logsi.LeaveMethod(SILevel.Debug)


        @staticmethod
        def _GetEntityFromServiceData(hass:HomeAssistant, service:ServiceCall, field_id:str) -> MediaPlayerEntity:
            """
            Resolves a `MediaPlayerEntity` instance from a ServiceCall field id.

            Args:
                hass (HomeAssistant):
                    HomeAssistant instance.
                service (ServiceCall):
                    ServiceCall instance that contains service data (requested service name, field parameters, etc).
                field_id (str):
                    Service parameter field id whose value contains a SoundTouch entity id.  
                    The ServiceCall data area will be queried with the field id to retrieve the entity id value.

            Returns:
                A `MediaPlayerEntity` instance if one could be resolved; otherwise, None.
        
            The service.data collection is queried for the field_id argument name.  If not supplied, 
            then an error message is logged and the return value is None.  

            The Haas data is then queried for the entity_id to retrieve the `MediaPlayerEntity` instance.
            """
            # get service parameter: entity_id.
            entity_id = service.data.get(field_id)
            if entity_id is None:
                _logsi.LogError(STAppMessages.MSG_SERVICE_ARGUMENT_NULL, field_id, service.service)
                return None

            # search all MediaPlayerEntity instances for the specified entity_id.
            # if found, then return the MediaPlayerEntity instance.
            player:MediaPlayerEntity = None
            data:InstanceDataSoundTouchPlus = None
            for data in hass.data[DOMAIN].values():
                if data.media_player.entity_id == entity_id:
                    player = data.media_player
                    break

            # did we resolve it? if not, then log a message.
            if player is None:
                raise HomeAssistantError("Entity id value of '%s' could not be resolved to a MediaPlayerEntity instance for the '%s' method call" % (str(entity_id), service.service))

            # return the MediaPlayerEntity instance.
            _logsi.LogVerbose("Entity id value of '%s' was resolved to MediaPlayerEntity instance for the '%s' method call" % (str(entity_id), service.service))
            return player


        # register all services this component provides, and their corresponding schemas.
        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS, SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS,
            service_handle_entity,
            schema=SERVICE_CLEAR_SOURCE_NOWPLAYINGSTATUS_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_AUDIO_TONE_LEVELS, SERVICE_AUDIO_TONE_LEVELS_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_AUDIO_TONE_LEVELS,
            service_handle_entity,
            schema=SERVICE_AUDIO_TONE_LEVELS_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_GET_SOURCE_LIST, SERVICE_GET_SOURCE_LIST_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_SOURCE_LIST,
            service_handle_getlist,
            schema=SERVICE_GET_SOURCE_LIST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_MUSICSERVICE_STATION_LIST, SERVICE_MUSICSERVICE_STATION_LIST_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_MUSICSERVICE_STATION_LIST,
            service_handle_getlist,
            schema=SERVICE_MUSICSERVICE_STATION_LIST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_PLAY_CONTENTITEM, SERVICE_PLAY_CONTENTITEM_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_CONTENTITEM,
            service_handle_entity,
            schema=SERVICE_PLAY_CONTENTITEM_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_PLAY_HANDOFF, SERVICE_PLAY_HANDOFF_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_HANDOFF,
            service_handle_entityfromto,
            schema=SERVICE_PLAY_HANDOFF_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_PLAY_TTS, SERVICE_PLAY_TTS_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_TTS,
            service_handle_entity,
            schema=SERVICE_PLAY_TTS_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_PLAY_URL, SERVICE_PLAY_URL_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_URL,
            service_handle_entity,
            schema=SERVICE_PLAY_URL_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_PRESET_LIST, SERVICE_PRESET_LIST_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PRESET_LIST,
            service_handle_getlist,
            schema=SERVICE_PRESET_LIST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_PRESET_REMOVE, SERVICE_PRESET_REMOVE_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PRESET_REMOVE,
            service_handle_entity,
            schema=SERVICE_PRESET_REMOVE_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_REBOOT_DEVICE, SERVICE_REBOOT_DEVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_REBOOT_DEVICE,
            service_handle_entity,
            schema=SERVICE_REBOOT_DEVICE_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_RECENT_LIST, SERVICE_RECENT_LIST_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_RECENT_LIST,
            service_handle_getlist,
            schema=SERVICE_RECENT_LIST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_RECENT_LIST_CACHE, SERVICE_RECENT_LIST_CACHE_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_RECENT_LIST_CACHE,
            service_handle_getlist,
            schema=SERVICE_RECENT_LIST_CACHE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_REMOTE_KEYPRESS, SERVICE_REMOTE_KEYPRESS_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOTE_KEYPRESS,
            service_handle_entity,
            schema=SERVICE_REMOTE_KEYPRESS_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SNAPSHOT_RESTORE, SERVICE_SNAPSHOT_RESTORE_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_SNAPSHOT_RESTORE,
            service_handle_entity,
            schema=SERVICE_SNAPSHOT_RESTORE_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SNAPSHOT_STORE, SERVICE_SNAPSHOT_STORE_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_SNAPSHOT_STORE,
            service_handle_entity,
            schema=SERVICE_SNAPSHOT_STORE_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS, SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS,
            service_handle_entity,
            schema=SERVICE_UPDATE_SOURCE_NOWPLAYINGSTATUS_SCHEMA,
        )

        _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_ZONE_TOGGLE_MEMBER, SERVICE_ZONE_TOGGLE_MEMBER_SCHEMA)
        hass.services.async_register(
            DOMAIN,
            SERVICE_ZONE_TOGGLE_MEMBER,
            service_handle_entityfromto,
            schema=SERVICE_ZONE_TOGGLE_MEMBER_SCHEMA,
        )
    
        # indicate success.
        _logsi.LogVerbose("Component async_setup complete")
        return True

    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def async_setup_entry(hass:HomeAssistant, entry:ConfigEntry) -> bool:
    """
    Set up device instance from a config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry dictionary.  This contains configuration
            settings for the specific component device entry.

    The __init__.py module "async_setup_entry" method is executed for each device that is 
    configured for the component.  It takes care of loading the device controller instance 
    (e.g. SoundTouchClient in our case) for each device that will be controlled.
    """
    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(SILevel.Verbose, "'%s': Component async_setup_entry is starting - entry (ConfigEntry) object" % entry.title, entry)
        _logsi.LogDictionary(SILevel.Verbose, "'%s': Component async_setup_entry entry.data dictionary" % entry.title, entry.data)
        _logsi.LogDictionary(SILevel.Verbose, "'%s': Component async_setup_entry entry.options dictionary" % entry.title, entry.options)

        # load config entry base parameters.
        host:str = entry.data[CONF_HOST]

        # load config entry user-specified parameters.
        port:int = entry.data.get(CONF_PORT, DEFAULT_PORT)
        port_websocket:int = entry.data.get(CONF_PORT_WEBSOCKET, DEFAULT_PORT_WEBSOCKET)
        ping_websocket_interval:int = entry.data.get(CONF_PING_WEBSOCKET_INTERVAL, DEFAULT_PING_WEBSOCKET_INTERVAL)
        option_source_list:list[str] = entry.options.get(CONF_OPTION_SOURCE_LIST, [])
        option_recents_cache_max_items:int = entry.options.get(CONF_OPTION_RECENTS_CACHE_MAX_ITEMS, 0)

        device:SoundTouchDevice = None
        client:SoundTouchClient = None
        socket:SoundTouchWebSocket = None
    
        # create the SoundTouchDevice object.
        _logsi.LogVerbose("'%s': Component async_setup_entry is creating SoundTouchDevice instance: IP Address=%s, Port=%s" % (entry.title, host, str(port)))
        device:SoundTouchDevice = await hass.async_add_executor_job(SoundTouchDevice, host, 30, None, port)
        _logsi.LogVerbose("'%s': Device Info: Name='%s', ID='%s', Type='%s', Country='%s', Region='%s'" % (entry.title, device.DeviceName, device.DeviceId, device.DeviceType, device.CountryCode, device.RegionCode))
        _logsi.LogVerbose("'%s': Device does NOT support the following URL services: %s" % (entry.title, device.UnSupportedUrlNames))
        if len(device.UnknownUrlNames) > 0:
            _logsi.LogVerbose("'%s': Device contains URL services that are not known by the API: %s" % (entry.title, device.UnknownUrlNames))
    
        # create the SoundTouchClient object, which contains all of the methods used to control the actual device.
        _logsi.LogVerbose("'%s': Component async_setup_entry is creating SoundTouchClient instance: IP Address=%s, Port=%s" % (entry.title, host, str(port)))
        client:SoundTouchClient = await hass.async_add_executor_job(SoundTouchClient, device)
        
        # handle websocket failures. if it fails, the configuration can still function but polling
        # will be used instead of websocket notifications from the SoundTouch device.
        try:

            _logsi.LogVerbose("'%s': Component async_setup_entry is verifying SoundTouch WebSocket connectivity" % entry.title)

            # get device capabilities - must have IsWebSocketApiProxyCapable=True 
            # in order to support notifications.
            capabilities:Capabilities = await hass.async_add_executor_job(client.GetCapabilities)
            if (port_websocket == 0):

                # SoundTouch device websocket notifications were disabled by user - device will be polled.
                _logsi.LogMessage("'%s': Component async_setup_entry - device websocket notifications were disabled by the user; polling will be enabled" % entry.title)
            
            elif (capabilities.IsWebSocketApiProxyCapable == True):

                _logsi.LogVerbose("'%s': Component async_setup_entry has verified device is capable of websocket notifications" % entry.title)

                # create a websocket to receive notifications from the device.
                _logsi.LogVerbose("'%s': Component async_setup_entry is creating SoundTouchWebSocket instance: port=%s, pingInterval=%s" % (entry.title, str(port_websocket), str(ping_websocket_interval)))
                socket = await hass.async_add_executor_job(SoundTouchWebSocket, client, port_websocket, ping_websocket_interval)
                
                # enable recently played items cache.
                if (option_recents_cache_max_items > 0):
                    cacheDir:str = "%s/www/%s" % (hass.config.config_dir, DOMAIN)
                    await hass.async_add_executor_job(
                        functools.partial(
                            client.UpdateRecentListCacheStatus, 
                            True, 
                            cacheDir, 
                            maxItems=option_recents_cache_max_items)
                        )
                        
                # we cannot start listening for notifications just yet, as the entity has not been
                # added to HA UI yet.  this will happen in the `media_player.async_added_to_hass` method.

            else:

                # SoundTouch device does not support websocket notifications!
                _logsi.LogWarning("'%s': Component async_setup_entry - device does not support websocket notifications; polling will be enabled" % entry.title)

        except Exception as ex:
        
            # log failure.
            _logsi.LogError("'%s': Component async_setup_entry - SoundTouchWebSocket instance could not be created; polling will be enabled: %s" % (entry.title, str(ex)))
            socket = None

        # create media player entity instance data.
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = InstanceDataSoundTouchPlus(
            client=client, 
            socket=socket,
            media_player=None,
            options=entry.options
        )
        _logsi.LogObject(SILevel.Verbose, "'%s': Component async_setup_entry media_player instance data object" % entry.title, hass.data[DOMAIN][entry.entry_id])

        # we are now ready for HA to create individual objects for each platform that
        # our device requires; in our case, it's just a media_player platform.
        # we initiate this by calling the `async_forward_entry_setups`, which 
        # calls the `async_setup_entry` function in each platform module (e.g.
        # media_player.py) for each device instance.
        _logsi.LogVerbose("'%s': Component async_setup_entry is forwarding configuration entry setups to create the individual media player platforms" % entry.title)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # register an update listener to reload configuration entry when options are updated.
        # this will return an "unlisten" function, which will be added to the configuration
        # "on_unload" event handler to automatically unregister the update listener when
        # the configuration is unloaded.
        listenerRemovePtr = entry.add_update_listener(options_update_listener)
        _logsi.LogArray(SILevel.Verbose, "'%s': Component update listener has been registered and added to update listeners array (%d array items)" % (entry.title, len(entry.update_listeners)), entry.update_listeners)

        entry.async_on_unload(listenerRemovePtr)
        _logsi.LogArray(SILevel.Verbose, "'%s': Component update listener auto-unregister method has been added to on_unload event handlers array (%d array items)" % (entry.title, len(entry._on_unload)), entry._on_unload)

        # trace.
        _logsi.LogVerbose("'%s': Component async_setup_entry is complete" % entry.title)

        # indicate success.
        return True

    except Exception as ex:

        # this is usually caused by a temporary error (e.g. device unplugged, network connectivity, etc), in 
        # which case the user will need to manually reload the device when the temporary condition is cleared.
        # if it's a permanent error (e.g. ip address change), then the user needs to correct the configuration.
        
        # trace.
        _logsi.LogException("'%s': Component async_setup_entry exception" % entry.title, ex, logToSystemLogger=False)
        
        # reset 
        device = None
        client = None
        
        # inform HA that the configuration is not ready.
        raise ConfigEntryNotReady from ex
    
    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def async_unload_entry(hass:HomeAssistant, entry:ConfigEntry) -> bool:
    """
    Unloads a configuration entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry object.

    The __init__.py module "async_unload_entry" unloads a configuration entry.
            
    This method is called when a configuration entry is to be removed. The class
    needs to unload itself, and remove any callbacks.  
    
    Note that any options update listeners (added via "add_update_listener") do not need 
    to be removed, as they are already removed by the time this method is called.
    This is accomplished by the "entry.async_on_unload(listener)" call in async_setup_entry,
    which removes them from the configuration entry just before it is unloaded.
    """
    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(SILevel.Verbose, "'%s': Component async_unload_entry configuration entry" % entry.title, entry)

        # unload any platforms this device supports.
        _logsi.LogVerbose("'%s': Component async_unload_entry is unloading our device instance from the domain" % entry.title)
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        # if unload was successful, then remove data associated with the device.
        if unload_ok:

            # remove instance data from domain.
            _logsi.LogVerbose("'%s': Component async_unload_entry is removing our device instance data from the domain" % entry.title)
            data:InstanceDataSoundTouchPlus = hass.data[DOMAIN].pop(entry.entry_id)
            _logsi.LogObject(SILevel.Verbose, "'%s': Component async_unload_entry unloaded configuration entry instance data" % entry.title, data)

            # a quick check to make sure all update listeners were removed (see method doc notes above).
            if len(entry.update_listeners) > 0:
                _logsi.LogArray(SILevel.Warning, "'%s': Component configuration update_listener(s) did not get removed before configuration unload (%d items - should be 0 prioer to HA 2026.0 release, but after that release still contains entries)" % (entry.title, len(entry.update_listeners)), entry.update_listeners)
                # something changed with HA 2024.6 release that causes the `update_listeners` array to still contain entries!
                # prior to this release, the `update_listeners` array was empty by this point.
                # I commented out the following line to clear the `update_listeners`, as it was causing `ValueError: list.remove(x): x not in list`
                # exceptions starting with the HA 2024.6.0 release!
                #entry.update_listeners.clear()

        # return status to caller.
        _logsi.LogVerbose("'%s': Component async_unload_entry completed" % entry.title)
        return unload_ok

    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def async_reload_entry(hass:HomeAssistant, entry:ConfigEntry) -> None:
    """
    Reload config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry object.

    The __init__.py module "async_reload_entry" reloads a configuration entry.
            
    This method is called when an entry/configured device is to be reloaded. The class
    needs to unload itself, remove callbacks, and call async_setup_entry.
    """
    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(SILevel.Verbose, "'%s': Component async_reload_entry configuration entry" % entry.title, entry)

        # unload the configuration entry.
        _logsi.LogVerbose("'%s': Component async_reload_entry is unloading the configuration entry" % entry.title)
        await async_unload_entry(hass, entry)

        # reload (setup) the configuration entry.
        _logsi.LogVerbose("'%s': Component async_reload_entry is reloading the configuration entry" % entry.title)
        await async_setup_entry(hass, entry)

        # trace.
        _logsi.LogVerbose("'%s': Component async_reload_entry completed" % entry.title)

    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def options_update_listener(hass:HomeAssistant, entry:ConfigEntry) -> None:
    """
    Configuration entry update event handler.
    
    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry object.
    
    Reloads the config entry after updates have been applied to a configuration entry.

    This method is called when a user has updated configuration options via the UI, or
    when a call is made to async_update_entry with changed configuration data.
    """
    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(SILevel.Verbose, "'%s': Component detected configuration entry options update" % entry.title, entry)
        
        # reload the configuration entry.
        await hass.config_entries.async_reload(entry.entry_id)

        # trace.
        _logsi.LogVerbose("'%s': Component options_update_listener completed" % entry.title)

    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)
        
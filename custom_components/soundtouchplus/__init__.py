"""
The soundtouchplus component.
"""
import logging

from bosesoundtouchapi import *
from bosesoundtouchapi.uri import *
from bosesoundtouchapi.models import *
from bosesoundtouchapi.ws import *

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .entity_init_parms import EntityInitParms
from .stappmessages import STAppMessages
from .const import (
    DOMAIN,
    CONF_PORT_WEBSOCKET,
    CONF_PING_WEBSOCKET_INTERVAL,
    CONF_OPTION_SOURCE_LIST,
    DEFAULT_PING_WEBSOCKET_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_PORT_WEBSOCKET,
    SERVICE_AUDIO_TONE_LEVELS,
    SERVICE_MUSICSERVICE_STATION_LIST,
    SERVICE_PLAY_CONTENTITEM,
    SERVICE_PLAY_HANDOFF,
    SERVICE_PLAY_TTS,
    SERVICE_PLAY_URL,
    SERVICE_PRESET_LIST,
    SERVICE_REBOOT_DEVICE,
    SERVICE_RECENT_LIST,
    SERVICE_REMOTE_KEYPRESS,
    SERVICE_SNAPSHOT_RESTORE,
    SERVICE_SNAPSHOT_STORE,
    SERVICE_ZONE_TOGGLE_MEMBER
)

OPTIONS_UPDATE_LISTENER_REMOVE = "options_update_listener_remove"

_LOGGER = logging.getLogger(__name__)
#LOGGER = logging.getLogger(__package__)

try:

    from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIConfigurationTimer

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

SERVICE_ZONE_TOGGLE_MEMBER_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id_master"): cv.entity_id,
        vol.Required("entity_id_member"): cv.entity_id,
    }
)


async def async_setup(hass:HomeAssistant, config:ConfigType) -> bool:
    """
    Set up Bose SoundTouchPlus component.

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
    # trace the ConfigType dictionary for debugging purposes.
    if _logsi.IsOn(SILevel.Verbose):

        _logsi.LogVerbose("Component async_setup starting")

        # log the manifest file contents.
        myConfigDir:str = "%s/custom_components/%s" % (hass.config.config_dir, DOMAIN)
        myManifestPath:str = "%s/manifest.json" % (myConfigDir)
        _logsi.LogTextFile(SILevel.Verbose, "Integration Manifest File (%s)" % myManifestPath, myManifestPath)

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
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_CALL_START, service.service, "service_handle_entity")
            _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_PARM, service)
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_DATA, service.data)

            # get media_player instance from service parameter; if not found, then we are done.
            player = _GetEntityFromServiceData(hass, service, "entity_id")
            if player is None:
                return

            # process service request.
            if service.service == SERVICE_SNAPSHOT_STORE:
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

            elif service.service == SERVICE_AUDIO_TONE_LEVELS:
                bass_level = service.data.get("bass_level")
                treble_level = service.data.get("treble_level")
                await hass.async_add_executor_job(player.service_audio_tone_levels, bass_level, treble_level)

            else:
                _logsi.LogError(STAppMessages.MSG_SERVICE_REQUEST_UNKNOWN, service.service, "service_handle_entity")
                return
            
        except SoundTouchWarning as ex:  pass   # should already be logged
        except SoundTouchError as ex:  pass     # should already be logged
        except Exception as ex:
            # log exception, but not to system logger as HA will take care of it.
            _logsi.LogException(STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION % (service.service, "service_handle_entity"), ex, logToSystemLogger=False)
            raise


    async def service_handle_entityfromto(service: ServiceCall) -> None:
        """
        Handle service requests that utilize a single FROM entity and a single TO entity.

        Args:
            service (ServiceCall):
                ServiceCall instance that contains service data (requested service name, field parameters, etc).
        """
        try:
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
            
        except SoundTouchWarning as ex:  pass   # should already be logged
        except SoundTouchError as ex:  pass     # should already be logged
        except Exception as ex:
            
            # log exception, but not to system logger as HA will take care of it.
            _logsi.LogException(STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION % (service.service, "service_handle_entityfromto"), ex, logToSystemLogger=False)
            raise


    async def service_handle_getlist(service: ServiceCall) -> ServiceResponse:
        """
        Handle service request to retrieve a list of presets for an entity.

        Args:
            service (ServiceCall):
                ServiceCall instance that contains service data (requested service name, field parameters, etc).
        """
        try:
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_CALL_START, service.service, "service_handle_getlist")
            _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_PARM, service)
            _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_DATA, service.data)

            # get player instance from service parameter; if not found, then we are done.
            player = _GetEntityFromServiceData(hass, service, "entity_id")
            if player is None:
                return

            response:dict = {}

            # process service request.
            if service.service == SERVICE_MUSICSERVICE_STATION_LIST:

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

            # build list of items to return.
            _logsi.LogDictionary(SILevel.Verbose, "Service Response data: '%s'" % (service.service), response, prettyPrint=True)
            return response 

        except SoundTouchWarning as ex:  pass   # should already be logged
        except SoundTouchError as ex:  pass     # should already be logged
        except Exception as ex:
            # log exception, but not to system logger as HA will take care of it.
            _logsi.LogException(STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION % (service.service, "service_handle_getlist"), ex, logToSystemLogger=False)
            raise


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
        data:EntityInitParms = None
        for data in hass.data[DOMAIN].values():
            if data.media_player.entity_id == entity_id:
                player = data.media_player
                break

        # did we resolve it? if not, then log a message.
        if player is None:
            _logsi.LogError("Entity id value of '%s' could not be resolved to a MediaPlayerEntity instance for the '%s' method call" % (str(entity_id), service.service))
            return None

        # return the MediaPlayerEntity instance.
        _logsi.LogVerbose("Entity id value of '%s' was resolved to MediaPlayerEntity instance for the '%s' method call" % (str(entity_id), service.service))
        return player


    # register all services this component provides, and their corresponding schemas.
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_AUDIO_TONE_LEVELS, SERVICE_AUDIO_TONE_LEVELS_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_AUDIO_TONE_LEVELS,
        service_handle_entity,
        schema=SERVICE_AUDIO_TONE_LEVELS_SCHEMA,
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


async def async_setup_entry(hass:HomeAssistant, configEntry:ConfigEntry) -> bool:
    """
    Set up device instance from a config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        configEntry (ConfigEntry):
            HomeAssistant configuration entry dictionary.  This contains configuration
            settings for the specific component device entry.

    The __init__.py module "async_setup_entry" method is executed for each device that is 
    configured for the component.  It takes care of loading the device controller instance 
    (e.g. SoundTouchClient in our case) for each device that will be controlled.
    """
    host:str = configEntry.data[CONF_HOST]
    port:int = DEFAULT_PORT
    port_websocket:int = DEFAULT_PORT_WEBSOCKET
    ping_websocket_interval:int = DEFAULT_PING_WEBSOCKET_INTERVAL
    option_source_list:list[str] = []

    _logsi.LogObject(SILevel.Verbose, "Component async_setup_entry is starting (%s)" % host, configEntry)
    _logsi.LogDictionary(SILevel.Verbose, "Component async_setup_entry configEntry.data dictionary (%s)" % host, configEntry.data)
    _logsi.LogDictionary(SILevel.Verbose, "Component async_setup_entry configEntry.options dictionary (%s)" % host, configEntry.options)

    # always check for keys, in case of an upgrade that contains a new key
    # that is not present in a previous version.

    # load config entry parameters.
    if CONF_PORT in configEntry.data.keys():
        port = configEntry.data[CONF_PORT]
    if CONF_PORT_WEBSOCKET in configEntry.data.keys():
        port_websocket = configEntry.data[CONF_PORT_WEBSOCKET]
    if CONF_PING_WEBSOCKET_INTERVAL in configEntry.data.keys():
        ping_websocket_interval = configEntry.data[CONF_PING_WEBSOCKET_INTERVAL]
        
    # load config entry options.
    if CONF_OPTION_SOURCE_LIST in configEntry.options.keys():
        option_source_list = configEntry.options.get(CONF_OPTION_SOURCE_LIST)
    
    _logsi.LogVerbose("Component async_setup_entry is creating SoundTouchDevice and SoundTouchClient instance (%s): port=%s" % (host, str(port)))

    device:SoundTouchDevice = None
    client:SoundTouchClient = None
    socket:SoundTouchWebSocket = None
    
    try:
        
        # create the SoundTouchDevice object.
        device:SoundTouchDevice = await hass.async_add_executor_job(SoundTouchDevice, host, 30, None, port)
        _logsi.LogObject(SILevel.Verbose, "Component async_setup_entry created SoundTouchDevice instance (%s): %s"  % (host, device.DeviceName), device)
        _logsi.LogVerbose("(%s): %s - Device Info: ID='%s', Type='%s', Country='%s', Region='%s'" % (host, device.DeviceName, device.DeviceId, device.DeviceType, device.CountryCode, device.RegionCode))
        _logsi.LogVerbose("(%s): %s - Device does NOT support the following URL services: %s" % (host, device.DeviceName, device.UnSupportedUrlNames))
        if len(device.UnknownUrlNames) > 0:
            _logsi.LogVerbose("(%s): %s - Device contains URL services that are not known by the API: %s" % (host, device.DeviceName, device.UnknownUrlNames))
    
        # create the SoundTouchClient object, which contains all of the methods used to control the actual device.
        client:SoundTouchClient = await hass.async_add_executor_job(SoundTouchClient, device)
        _logsi.LogObject(SILevel.Verbose, "Component async_setup_entry created SoundTouchClient instance (%s): %s"  % (host, device.DeviceName), client)
        
    except Exception as ex:

        # this is usually caused by a temporary error (e.g. device unplugged, network connectivity, etc), in 
        # which case the user will need to manually reload the device when the temporary condition is cleared.
        # if it's a permanent error (e.g. ip address change), then the user needs to correct the configuration.
        
        # indicate failure.
        _logsi.LogError("Component async_setup_entry - SoundTouchDevice instance could not be created; exception details should already be logged.")
        device = None
        client = None
        return False

    try:

        _logsi.LogVerbose("Component async_setup_entry is verifying SoundTouch WebSocket connectivity (%s)" % (host))

        # get device capabilities - must have IsWebSocketApiProxyCapable=True 
        # in order to support notifications.
        capabilities:Capabilities = await hass.async_add_executor_job(client.GetCapabilities)
        if (port_websocket == 0):

            # SoundTouch device websocket notifications were disabled by user - device will be polled.
            _logsi.LogMessage("Component async_setup_entry - device websocket notifications were disabled by the user; polling will be enabled (%s)" % (host))
            
        elif (capabilities.IsWebSocketApiProxyCapable == True):

            _logsi.LogVerbose("Component async_setup_entry has verified device is capable of websocket notifications (%s)" % (host))

            # create a websocket to receive notifications from the device.
            _logsi.LogVerbose("Component async_setup_entry is creating SoundTouchWebSocket instance (%s): port=%s, pingInterval=%s" % (host, str(port_websocket), str(ping_websocket_interval)))
            socket = await hass.async_add_executor_job(SoundTouchWebSocket, client, port_websocket, ping_websocket_interval)

            # we cannot start listening for notifications just yet, as the entity has not been
            # added to HA UI yet.  this will happen in the `media_player.async_added_to_hass` method.

        else:

            # SoundTouch device does not support websocket notifications!
            _logsi.LogWarning("Component async_setup_entry - device does not support websocket notifications; polling will be enabled (%s)" % (host))

    except Exception as ex:
        
        # log failure.
        _logsi.LogError("Component async_setup_entry - SoundTouchWebSocket instance could not be created: %s" % str(ex))
        socket = None

    # create media player entity initialization parameters.
    hass.data.setdefault(DOMAIN, {})[configEntry.entry_id] = EntityInitParms(hass, configEntry, client, socket)

    # we are now ready for HA to create individual objects for each platform that
    # our device requires; in our case, it's just a media_player platform.
    # we initiate this by calling the `async_forward_entry_setups`, which 
    # calls the `async_setup_entry` function in each platform module for 
    # each device instance.
    await hass.config_entries.async_forward_entry_setups(configEntry, PLATFORMS)

    # register an update listener to update config entry when options are updated.
    # we also store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    _logsi.LogVerbose("Component async_setup_entry registering options update listener (%s): %s"  % (host, device.DeviceName))
    configEntry.async_on_unload(configEntry.add_update_listener(options_update_listener))

    # indicate success.
    _logsi.LogVerbose("Component async_setup_entry is complete (%s): %s"  % (host, device.DeviceName))
    return True


async def async_unload_entry(hass:HomeAssistant, configEntry:ConfigEntry) -> bool:
    """
    Unload config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        configEntry (ConfigEntry):
            HomeAssistant configuration entry object.

    The __init__.py module "async_unload_entry" unloads a configuration entry.
            
    This method is called when an entry/configured device is to be removed. The class
    needs to unload itself, and remove callbacks.
    """
    _logsi.LogObject(SILevel.Verbose, "Component async_unload_entry starting", configEntry)

    # unload any platforms this device supports.
    unload_ok = await hass.config_entries.async_unload_platforms(configEntry, PLATFORMS)
    
    # if unload was successful, then remove data associated with the device.
    if unload_ok:

        # remove config entry from domain.
        _logsi.LogVerbose("Component async_unload_entry removing configEntry from hass.data for our domain")
        initParms:EntityInitParms = hass.data[DOMAIN].pop(configEntry.entry_id)
        _logsi.LogObject(SILevel.Verbose, "Component async_unload_entry removed configEntry from hass.data for our domain - initParms", initParms)
        _logsi.LogObject(SILevel.Verbose, "Component async_unload_entry removed configEntry from hass.data for our domain - initParms.configEntry", initParms.configEntry)

        # remove options_update_listener.
        # not sure if this code is needed, but left it in just in case.
        if OPTIONS_UPDATE_LISTENER_REMOVE in initParms.configEntry.update_listeners:
            _logsi.LogVerbose("Component async_unload_entry options update listener remove is starting")
            initParms.configEntry.update_listeners[OPTIONS_UPDATE_LISTENER_REMOVE]()
            _logsi.LogVerbose("Component async_unload_entry options update listener remove complete")

    _logsi.LogVerbose("Component async_unload_entry completed")
    return unload_ok


async def async_reload_entry(hass:HomeAssistant, configEntry:ConfigEntry) -> None:
    """
    Reload config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        configEntry (ConfigEntry):
            HomeAssistant configuration entry object.

    The __init__.py module "async_reload_entry" reloads a configuration entry.
            
    This method is called when an entry/configured device is to be reloaded. The class
    needs to unload itself, remove callbacks, and call async_setup_entry.
    """
    _logsi.LogObject(SILevel.Verbose, "Component async_reload_entry starting", configEntry)

    await async_unload_entry(hass, configEntry)
    await async_setup_entry(hass, configEntry)

    _logsi.LogVerbose("Component async_reload_entry completed")


async def options_update_listener(hass:HomeAssistant, configEntry:ConfigEntry) -> None:
    """
    Handle options update.
    
    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        configEntry (ConfigEntry):
            HomeAssistant configuration entry object.

    Reloads the config entry so that we can act on updated options data that was saved.

    This method is called when a user has updated configuration options via the UI.
    """
    _logsi.LogVerbose("Component Options have been updated; reloading configuration (%s)" % configEntry.entry_id)
    await hass.config_entries.async_reload(configEntry.entry_id)
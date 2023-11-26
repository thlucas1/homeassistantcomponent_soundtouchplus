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
    DEFAULT_PING_WEBSOCKET_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_PORT_WEBSOCKET,
    SERVICE_AUDIO_TONE_LEVELS,
    SERVICE_PLAY_HANDOFF,
    SERVICE_PLAY_TTS,
    SERVICE_PLAY_URL,
    SERVICE_PRESETLIST,
    SERVICE_RECENTLIST,
    SERVICE_REMOTE_KEYPRESS,
    SERVICE_SNAPSHOT_RESTORE,
    SERVICE_SNAPSHOT_STORE
)

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
        vol.Optional("volume_level", default=0): vol.All(vol.Range(min=10,max=70)),
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
        vol.Optional("volume_level", default=0): vol.All(vol.Range(min=10,max=70)),
        vol.Optional("app_key"): cv.string,
        vol.Required("get_metadata_from_url_file", default=False): cv.boolean
    }
)

SERVICE_PRESETLIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

SERVICE_RECENTLIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

SERVICE_REMOTE_KEYPRESS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("key_id"): cv.string,
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
        for item in config:
            itemKey:str = str(item)
            itemObj = config[itemKey]
            if isinstance(itemObj,dict):
                _logsi.LogDictionary(SILevel.Verbose, "ConfigType '%s' data (dictionary)" % itemKey, itemObj)
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
                if key_id is None:
                    _logsi.LogError(STAppMessages.MSG_SERVICE_ARGUMENT_NULL, "key_id", service.service)
                    return
                await hass.async_add_executor_job(player.service_remote_keypress, key_id)

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

            # get player instance from service parameter; if not found, then we are done.
            from_player = _GetEntityFromServiceData(hass, service, "entity_id_from")
            if from_player is None:
                return

            # get player instance from service parameter; if not found, then we are done.
            to_player = _GetEntityFromServiceData(hass, service, "entity_id_to")
            if to_player is None:
                return

            # process service request.
            if service.service == SERVICE_PLAY_HANDOFF:

                # if FROM and TO player are the same then don't allow it.
                if from_player.entity_id == to_player.entity_id:
                    _logsi.LogWarning("FROM and TO players (id='%s') are the same; handoff not needed", str(to_player.entity_id))
                    return

                # process play handoff service.
                restore_volume = service.data.get("restore_volume")
                snapshot_only = service.data.get("snapshot_only")
                await hass.async_add_executor_job(from_player.service_play_handoff, to_player, restore_volume, snapshot_only)

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

            # get player instance from service parameter; if not found, then we are done.
            player = _GetEntityFromServiceData(hass, service, "entity_id")
            if player is None:
                return

            response:dict = {}

            # process service request.
            if service.service == SERVICE_PRESETLIST:

                # get list of presets defined for the device.            
                presetList:PresetList = await hass.async_add_executor_job(player.service_preset_list)
                response = presetList.ToDictionary()

            elif service.service == SERVICE_RECENTLIST:

                # get list of recently played items defined for the device.            
                recentList:RecentList = await hass.async_add_executor_job(player.service_recent_list)
                response = recentList.ToDictionary()

            # build list of items to return.
            _logsi.LogDictionary(SILevel.Verbose, "Service Response data", response)
            return response 

        except SoundTouchWarning as ex:  pass   # should already be logged
        except SoundTouchError as ex:  pass     # should already be logged
        except Exception as ex:
            # log exception, but not to system logger as HA will take care of it.
            _logsi.LogException(STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION % (service.service, "service_handle_presetlist"), ex, logToSystemLogger=False)
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

    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_PRESETLIST, SERVICE_PRESETLIST_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_PRESETLIST,
        service_handle_getlist,
        schema=SERVICE_PRESETLIST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_RECENTLIST, SERVICE_RECENTLIST_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECENTLIST,
        service_handle_getlist,
        schema=SERVICE_RECENTLIST_SCHEMA,
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

    # indicate success.
    _logsi.LogVerbose("Component async_setup complete")
    return True


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
    host:str = entry.data[CONF_HOST]
    port:int = DEFAULT_PORT
    port_websocket:int = DEFAULT_PORT_WEBSOCKET
    ping_websocket_interval:int = DEFAULT_PING_WEBSOCKET_INTERVAL

    _logsi.LogObject(SILevel.Verbose, "Component async_setup_entry is starting (%s)" % host, entry)
    _logsi.LogDictionary(SILevel.Verbose, "Component async_setup_entry entry.data dictionary (%s)" % host, entry.data)

    # always check for keys, in case up an upgrade that contains a new key
    # that is not present in a previous version.
    if CONF_PORT in entry.data.keys():
        port = entry.data[CONF_PORT]
    if CONF_PORT_WEBSOCKET in entry.data.keys():
        port_websocket = entry.data[CONF_PORT_WEBSOCKET]
    if CONF_PING_WEBSOCKET_INTERVAL in entry.data.keys():
        ping_websocket_interval = entry.data[CONF_PING_WEBSOCKET_INTERVAL]
    
    # create the SoundTouchDevice and SoundTouchClient objects.
    # the SoundTouchClient contains all of the methods used to control the actual device.
    _logsi.LogVerbose("Component async_setup_entry is creating SoundTouchDevice and SoundTouchClient instance (%s): port=%s" % (host, str(port)))
    device:SoundTouchDevice = await hass.async_add_executor_job(SoundTouchDevice, host, 30, None, port)
    client:SoundTouchClient = await hass.async_add_executor_job(SoundTouchClient, device)
    _logsi.LogObject(SILevel.Verbose, "Component async_setup_entry created SoundTouchClient instance (%s): %s"  % (host, device.DeviceName), client)

    socket:SoundTouchWebSocket = None

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
            _logsi.LogMessage("Component async_setup_entry - device does not support websocket notifications; polling will be enabled (%s)" % (host))

    except Exception as ex:
        _logsi.LogException("SoundTouch WebSocket creation exception!", ex)

    # create media player entity initialization parameters.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = EntityInitParms(hass, client, socket)

    # we are now ready for HA to create individual objects for each platform that
    # our device requires; in our case, it's just a media_player platform.
    # we initiate this by calling the `async_forward_entry_setups`, which 
    # calls the `async_setup_entry` function in each platform module for 
    # each device instance.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # indicate success.
    _logsi.LogVerbose("Component async_setup_entry is complete (%s): %s"  % (host, device.DeviceName))
    return True


async def async_unload_entry(hass:HomeAssistant, entry:ConfigEntry) -> bool:
    """
    Unload config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry object.

    The __init__.py module "async_unload_entry" unloads a configuration entry.
            
    This method is called when an entry/configured device is to be removed. The class
    needs to unload itself, and remove callbacks.
    """
    _logsi.LogObject(SILevel.Verbose, "Component async_unload_entry starting", entry)

    # unload any platforms this device supports.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # if unload was successful, then remove data associated with the device.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    _logsi.LogVerbose("Component async_unload_entry completed")
    return unload_ok


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
    _logsi.LogObject(SILevel.Verbose, "Component async_reload_entry starting", entry)

    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

    _logsi.LogVerbose("Component async_reload_entry completed")

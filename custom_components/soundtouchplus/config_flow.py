"""
User interface config flow for Bose SoundTouchPlus integration.

Integrations can be set up via the user interface by adding support for a config 
flow to create a config entry. Components that want to support config entries will 
need to define a Config Flow Handler. This handler will manage the creation of 
entries from user input, discovery or other sources (like Home Assistant OS).

Config Flow Handlers control the data that is stored in a config entry. This means 
that there is no need to validate that the config is correct when Home Assistant 
starts up. It will also prevent breaking changes, because we will be able to migrate
 configuration entries to new formats if the version changes.

When instantiating the handler, Home Assistant will make sure to load all 
dependencies and install the requirements of the component.

"""
from __future__ import annotations

from bosesoundtouchapi import SoundTouchDevice, SoundTouchClient
from bosesoundtouchapi.models import SourceList, SourceItem
import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    Platform
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
#from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo  # required by 2026.02

from .const import (
    DOMAIN,
    DOMAIN_SPOTIFYPLUS,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ID,
    CONF_OPTION_SOURCE_LIST,
    CONF_OPTION_SOURCE_ALIASES,
    CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID,
    CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE,
    CONF_OPTION_RECENTS_CACHE_MAX_ITEMS,
    CONF_OPTION_CONFIGURE_ALIASES,
    CONF_PING_WEBSOCKET_INTERVAL,
    CONF_PORT_WEBSOCKET,
    DEFAULT_PING_WEBSOCKET_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_PORT_WEBSOCKET,
    DEFAULT_TIMEOUT
)

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIColors
_logsi:SISession = SIAuto.Si.GetSession(__name__)
if (_logsi == None):
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


async def validate_device_connection_http(hass:HomeAssistant, data:dict) -> dict:
    """
    Validate that the user input allows us to connect to the SoundTouch device
    over an HTTP connection using the specified port.

    The data argument has the keys from vol.schema (built in _show_user_form) 
    with values provided by the user.

    Returns:
        A dictionary of details obtained from the device (if no errors):
        CONF_DEVICE_NAME = the name of the device (e.g. "SoundTouch 300").
        CONF_DEVICE_ID   = the id of the device (e.g. "E8EB11B9B723").
    """
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    timeout = data[CONF_TIMEOUT]

    try:

        _logsi.LogVerbose("ConfigFlow is validating HTTP connection for device: IP=%s, port=%s, timeout=%s" % (host, port, timeout))

        # create new instance of SoundTouchDevice to ensure we can connect via HTTP.
        # we have to use the executor since the bosesoundtouchapi does not support async.
        # SoundTouchDevice init arguments: host, connectTimeout, proxyManager, port
        device:SoundTouchDevice = await hass.async_add_executor_job(SoundTouchDevice, host, timeout, None, port)

        _logsi.LogVerbose("ConfigFlow HTTP connection is valid for device: IP=%s, port=%s, name=%s, id=%s" % (host, port, device.DeviceName, device.DeviceId))

        # return other device details that we want to store in the config entry.
        # CONF_DEVICE_NAME is what is displayed to the user for this device.
        return {
            CONF_DEVICE_NAME: device.DeviceName,
            CONF_DEVICE_ID: device.DeviceId,
        }

    except Exception as ex:
        
        raise CannotConnect from ex


class SoundTouchPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle a config flow for Bose SoundTouchPlus.

    Config entries uses the data flow entry framework to define their config flows. 
    The config flow needs to be defined in the file config_flow.py in your integration 
    folder, extend homeassistant.config_entries.ConfigFlow and pass a domain key as 
    part of inheriting ConfigFlow.    
    """
    
    # integration configuration entry major version number.
    VERSION = 2

    def __init__(self):
        """
        Initialize a new SoundTouchPlus configflow.
        """
        _logsi.LogVerbose("ConfigFlow is initializing")
        self._device_id: str | None = None
        self._discovery_name: str | None = None
        self._host: str | None = None
        self._name: str | None = None
        self._ping_websocket_interval: int | None = DEFAULT_PING_WEBSOCKET_INTERVAL
        self._port: int | None = DEFAULT_PORT
        self._port_websocket: int | None = DEFAULT_PORT_WEBSOCKET


    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """
        Get the options flow for this handler, which enables options support.

        This method is invoked when a user clicks the "Configure" button from the integration
        details page of the UI.
        """
        return SoundTouchPlusOptionsFlow(config_entry)


    async def async_step_user(self, user_input=None):
        """
        Handle the initial step.

        This method is invoked when a user clicks the "Add Integration" button and 
        chooses the "Bose SoundTouch Plus" custom integration.
        """
        _logsi.LogDictionary(SILevel.Verbose, "ConfigFlow is executing async_step_user for: '%s' (%s)" % (self._name, self._host), user_input)
        errors = {}

        # the user_input variable defaults to None when this step is first called. 
        # when the user clicks the submit button on the form, the user_input variable will be 
        # a dictionary containing the data that was entered.  Home Assistant will do some basic 
        # validation on your behalf based on the data schema that you defined (e.g. required field,
        # port number is within a numeric range, etc). 
        if user_input is not None:

            # get form data that was entered by the user.
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._port_websocket = user_input[CONF_PORT_WEBSOCKET]
            self._ping_websocket_interval = user_input[CONF_PING_WEBSOCKET_INTERVAL]

            try:
                # validate the user input.
                deviceInfo:dict = await validate_device_connection_http(self.hass, self._get_data())
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _logsi.LogException("async_step_user exception", ex)
                errors["base"] = "unknown"
            else:

                # save device details for later.
                self._name = deviceInfo[CONF_DEVICE_NAME]
                self._device_id = deviceInfo[CONF_DEVICE_ID]

                # set configuration entry unique id (e.g. device id).
                # this value should match the value assigned in media_player `_attr_unique_id` attribute.
                await self.async_set_unique_id(self._device_id + "_" + DOMAIN)
                _logsi.LogVerbose("ConfigFlow assigned unique_id of '%s' for SoundTouch device name '%s' (via user config)" % (self.unique_id, self._name))

                # one final check to see if a configuration entry already exists for the device.
                # If it IS already configured, then we will send an "already_configured" message 
                # to the user and halt the flow to prevent a duplicate configuration entry.
                _logsi.LogVerbose("ConfigFlow is verifying USER ENTRY device details have not already been configured: unique_id=%s, ip=%s, port=%s, name=%s" % (self._device_id, self._host, self._port, self._name))
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_DEVICE_ID: self._device_id,
                    }
                )

                # create the configuration entry.
                return self._create_entry()

        # show the user input form if this is the initial setup, or if an error
        # occurs validating http or websocket connectivity.
        return self._show_user_form(errors)


    @callback
    def _show_user_form(self, errors=None):
        """
        Shows the user input form when the "Add Device" button is pressed by the user
        to add a new device instance.
        """
        default_port = self._port or DEFAULT_PORT
        default_port_websocket = self._port_websocket or DEFAULT_PORT_WEBSOCKET
        default_ping_websocket_interval = self._ping_websocket_interval or DEFAULT_PING_WEBSOCKET_INTERVAL
        
        _logsi.LogVerbose("_show_user_form data: IP=%s, port=%s, portws=%s, pinginterval=%s" % (self._host, str(default_port), str(default_port_websocket), str(default_ping_websocket_interval)))

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_PORT, default=default_port): cv.port,
                vol.Required(CONF_PORT_WEBSOCKET, default=default_port_websocket): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
                vol.Required(CONF_PING_WEBSOCKET_INTERVAL, default=default_ping_websocket_interval): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
            }
        )

        _logsi.LogVerbose("ConfigFlow is showing the user configuration form: '%s' (%s)" % (self._name, self._host))
        return self.async_show_form(
            step_id="user", 
            data_schema=schema, 
            description_placeholders={CONF_NAME: self._name},
            errors=errors or {}
        )


    async def async_step_zeroconf(self, discovery_info:zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """
        Handle a flow initiated by a zeroconf discovery.
        This method is invoked as part of the HA configuration event pipeline.

        When an integration is discovered, their respective discovery step is invoked (ie 
        async_step_dhcp or async_step_zeroconf) with the discovery information. 
        The step will have to check the following things:

        1) Make sure there are no other instances of this config flow in progress of setting 
        up the discovered device.  This can happen if there are multiple ways of discovering 
        that a device is on the network.
        2) Make sure that the device is not already set up.

        Invoking a discovery step should never result in a finished flow and a config entry. 
        Always confirm with the user.
        """
        _logsi.LogObject(SILevel.Verbose, "ConfigFlow is handling a ZeroConf discovery event", discovery_info)

        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        self._name = discovery_info.name.removesuffix("._soundtouch._tcp.local.")
        self._discovery_name = discovery_info.name

        # set the discovered device title.
        self.context.update({"title_placeholders": {CONF_NAME: self._name}})

        try:
            # validate the zeroconf discovery details.
            deviceInfo:dict = await validate_device_connection_http(self.hass, self._get_data())
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception as ex:  # pylint: disable=broad-except
            _logsi.LogException("Unexpected exception", ex)
            return self.async_abort(reason="unknown")

        # save device details for later.
        self._name = deviceInfo[CONF_DEVICE_NAME]
        self._device_id = deviceInfo[CONF_DEVICE_ID]

        # set configuration entry unique id (e.g. device id).
        # this value should match the value assigned in media_player `_attr_unique_id` attribute.
        await self.async_set_unique_id(self._device_id + "_" + DOMAIN)
        _logsi.LogVerbose("ConfigFlow assigned unique_id of '%s' for SoundTouch device name '%s' (via zeroconf config)" % (self.unique_id, self._name))

        # one final check to see if a configuration entry already exists for the device id.
        # if it IS already configured, then we will send an "already_configured" message 
        # to the user and halt the flow to prevent a duplicate configuration entry.
        _logsi.LogVerbose("ConfigFlow is verifying ZeroConf discovered device details have not already been configured: unique_id=%s, ip=%s, port=%s, name=%s" % (self._device_id, self._host, self._port, self._name))
        self._abort_if_unique_id_configured(
            updates={
                CONF_DEVICE_ID: self._device_id,
            }
        )

        # if we make it here, then the dicovered device is valid.
        return await self.async_step_discovery_confirm()


    async def async_step_discovery_confirm(self, user_input=None):
        """
        Handle user-confirmation of a zeroconf discovered device.

        This will confirm the zeroconf discovery of the device; if the user input is valid,
        then it will create a SoundTouch config entry.  if the user input is not valid, or if
        the device no longer exists on the network, then it will show a form to allow the 
        user to manually verify the confiugration parameters.
        """
        # confirm with the user the discovered details.
        if user_input is None:
            _logsi.LogVerbose("ConfigFlow is prompting user for confirmation of ZeroConf discovered device details: '%s'" % self._name)
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={
                    CONF_NAME: self._name,
                    CONF_HOST: self._host
                },
            )

        # create the configuration entry.
        return self._create_entry()


    @callback
    def _create_entry(self):

        # get configuration data.
        configData:dict = self._get_data()

        # create the configuration entry.
        _logsi.LogDictionary(SILevel.Verbose, "ConfigFlow is creating a configuration entry for deviceIP=%s, port=%s, name=%s, id=%s" % (self._host, self._port, self._name, self._device_id), configData)
        return self.async_create_entry(
            title=self._name or self._host,
            data=configData,
        )


    @callback
    def _get_data(self) -> dict:
        """
        Returns a dictionary of configuration data.
        """
        data:dict = {
            CONF_NAME: self._name,
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_PORT_WEBSOCKET: self._port_websocket,
            CONF_PING_WEBSOCKET_INTERVAL: self._ping_websocket_interval,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        }

        if data is not None:
            _logsi.LogDictionary(SILevel.Verbose, "ConfigFlow data block for '%s' (%s) over HTTP" % (self._name, self._host), data)
        return data


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class WSCannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect to websocket."""


class SoundTouchPlusOptionsFlow(OptionsFlow):
    """
    Handles options flow for the component.
    
    The options flow allows a user to configure additional options for the component at any time by 
    navigating to the integrations page and clicking the Options button on the card for your component. 
    Generally speaking these configuration values are optional, whereas values in the config flow are 
    required to make the component function.
    """

    def __init__(self, entry:ConfigEntry) -> None:
        """
        Initialize options flow.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogObject(SILevel.Verbose, "'%s': OptionsFlow is initializing - entry (ConfigEntry) object" % entry.title, entry)
            _logsi.LogDictionary(SILevel.Verbose, "'%s': OptionsFlow entry.data dictionary" % entry.title, entry.data)
            _logsi.LogDictionary(SILevel.Verbose, "'%s': OptionsFlow entry.options dictionary" % entry.title, entry.options)
       
            # initialize storage.
            self._name:str = None
            self._host:str = None
            self._port:int = DEFAULT_PORT

            # always use a ".get()" for keys, in case of an upgrade that contains a new key
            # that is not present in a previous version.           

            # load config entry base values.
            self._ConfigEntry = entry
            self._name = entry.data.get(CONF_NAME, None)
            self._host = entry.data.get(CONF_HOST, None)
            self._port = entry.data.get(CONF_PORT, DEFAULT_PORT)

            # load config entry options values.
            self._Options = dict(entry.options)

        except Exception as ex:
            
            # trace.
            _logsi.LogException(None, ex, logToSystemLogger=False)
            raise
        
        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    async def async_step_init(self, user_input:dict[str,Any]=None) -> FlowResult:
        """
        Manage the options for the custom component.

        Args:
            user_input (dict[str,Any]):
                User input gathered from the input form.  
                This argument defaults to None when this step is first called.  
                When the user clicks the submit button on the form, the argument will contain
                a dictionary of the data that was entered.  Home Assistant will do some basic 
                # validation on your behalf based on the data schema that you defined (e.g. 
                # required field, port number is within a numeric range, etc). 
                
        For a good example, look at HA demo source code:
            /home-assistant-core/homeassistant/components/demo/config_flow.py
            
        Note that the "self.hass.data[DOMAIN][entry.entry_id]" object is present in the
        OptionsFlow "async_step_init" step.  This allows you to access the client if one
        is assigned to the data area.  All you need to do is assign a reference to the 
        "entry:ConfigEntry" in the "__init__" in order to access it.  This saves you from
        instantiating a new instance of the client to retrieve settings.  
        """
        errors: dict[str, str] = {}
        
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogDictionary(SILevel.Verbose, "'%s': OptionsFlow async_step_init is starting - user_input" % self._name, user_input)

            # if not the initial entry, then save the entered options; otherwise, prepare the form.
            if user_input is not None:
            
                # sort updated config entry options.
                if CONF_OPTION_SOURCE_LIST in user_input:
                    user_input[CONF_OPTION_SOURCE_LIST].sort()

                # update config entry options from user input values.
                self._Options[CONF_OPTION_SOURCE_LIST] = user_input.get(CONF_OPTION_SOURCE_LIST, None)
                self._Options[CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID] = user_input.get(CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID, None)
                self._Options[CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE] = user_input.get(CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE, None)
                self._Options[CONF_OPTION_RECENTS_CACHE_MAX_ITEMS] = user_input.get(CONF_OPTION_RECENTS_CACHE_MAX_ITEMS, 0)

                # store the updated config entry options.
                if user_input.get(CONF_OPTION_CONFIGURE_ALIASES) is True:
                    return await self.async_step_aliases()

                return await self._update_options(self._Options)

            # load available sources from the device.
            source_list_all:dict = await self.hass.async_add_executor_job(self._GetSourceTitleList, self._host, self._port)
            if source_list_all is None:
                errors["base"] = "getsourcelist_empty"
                return

            # log sources that are currently selected.
            source_list_selected:list[str] = self._Options.get(CONF_OPTION_SOURCE_LIST, [])
            _logsi.LogArray(SILevel.Verbose, "'%s': OptionsFlow currently SELECTED '%s' items for device" % (self._name, CONF_OPTION_SOURCE_LIST), source_list_selected)
            
            # remove any previously selected sources that no longer exist in the source list.
            # if we don't do this, then the user won't be able to save any changes in the form.
            idx:int = 0
            while idx < len(source_list_selected):
                if (source_list_selected[idx] not in source_list_all):
                    _logsi.LogVerbose("'%s': OptionsFlow is removing source '%s' as it no longer exists in the current list of defined sources" % (self._name, source_list_selected[idx]))
                    del source_list_selected[idx]
                else:
                    idx += 1
                   
            # create validation schema.
            # default source list to empty array, which will cause the entire list to be displayed in the media player.
            schema = vol.Schema(
                {
                    vol.Optional(CONF_OPTION_SOURCE_LIST, 
                                 default=source_list_selected
                                 ): cv.multi_select(source_list_all),
                    # note - DO NOT use "default" argument on the following - use "suggested_value" instead.
                    # using "default=" does not allow a null entity_id to be selected!
                    vol.Optional(CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID, 
                                 description={"suggested_value": self._Options.get(CONF_OPTION_SPOTIFY_MEDIAPLAYER_ENTITY_ID)},
                                 ): selector.EntitySelector(selector.EntitySelectorConfig(integration=DOMAIN_SPOTIFYPLUS, 
                                                            domain=Platform.MEDIA_PLAYER, 
                                                            multiple=False),
                    ),
                    vol.Optional(CONF_OPTION_RECENTS_CACHE_MAX_ITEMS, 
                                 description={"suggested_value": self._Options.get(CONF_OPTION_RECENTS_CACHE_MAX_ITEMS)},
                                 default=self._Options.get(CONF_OPTION_RECENTS_CACHE_MAX_ITEMS, 0)
                                 ): cv.positive_int,
                    vol.Optional(CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE, 
                                 default=self._Options.get(CONF_OPTION_TTS_FORCE_GOOGLE_TRANSLATE, False)
                                 ): cv.boolean,
                    vol.Optional(CONF_OPTION_CONFIGURE_ALIASES,
                                 default=False,
                                 ): cv.boolean,
                }
            )
            
            _logsi.LogVerbose("'%s': OptionsFlow is showing the init configuration options form" % self._name)
            return self.async_show_form(
                step_id="init", 
                data_schema=schema, 
                description_placeholders={CONF_NAME: self._name},
                errors=errors or {}
            )
        
        except Exception as ex:
            
            # trace.
            _logsi.LogException(None, ex, logToSystemLogger=False)
            raise
        
        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    
    async def async_step_aliases(self, user_input:dict[str,Any]=None) -> FlowResult:
        """
        Configure source aliases.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogDictionary(SILevel.Verbose, "'%s': OptionsFlow async_step_aliases user_input" % self._name, user_input)

            errors:dict = {}

            if user_input is not None:

                # get current alias string
                current_aliases_str:str = self._Options.get(CONF_OPTION_SOURCE_ALIASES, "")
                aliases_dict:dict[str,str] = {}
                if current_aliases_str:
                    for pair in current_aliases_str.split(";"):
                        if "=" in pair:
                            source_key, alias_name = pair.split("=", 1)
                            aliases_dict[source_key.strip()] = alias_name.strip()

                # handle removal of selected aliases
                aliases_to_remove:list[str] = user_input.get("remove_aliases", [])
                for source_key in aliases_to_remove:
                    if source_key in aliases_dict:
                        del aliases_dict[source_key]

                # handle adding new alias
                new_source:str = user_input.get("add_source", "").strip()
                new_alias_name:str = user_input.get("add_alias_name", "").strip()
                if new_source:
                    if not new_alias_name:
                        errors["base"] = "alias_name_required"
                    else:
                        aliases_dict[new_source] = new_alias_name

                # convert dict back to semicolon-delimited string
                if aliases_dict:
                    alias_string = ";".join([f"{k}={v}" for k, v in aliases_dict.items()])
                else:
                    alias_string = ""

                self._Options[CONF_OPTION_SOURCE_ALIASES] = alias_string

                if not errors:
                    # check what action user wants to take
                    next_action:str = user_input.get("next_action", "continue_editing")
                    if next_action == "save_and_close":
                        # save and return to main options
                        return await self._update_options(self._Options)
                    else:
                        # continue editing - reload the form with updated aliases
                        # by calling async_step_aliases again without user_input
                        return await self.async_step_aliases()

            # load available sources from the device.
            source_list_all:dict = await self.hass.async_add_executor_job(self._GetSourceTitleList, self._host, self._port)
            if source_list_all is None:
                errors["base"] = "getsourcelist_empty"
                return

            # parse current aliases
            current_aliases_str:str = self._Options.get(CONF_OPTION_SOURCE_ALIASES, "")
            aliases_dict:dict[str,str] = {}
            if current_aliases_str:
                for pair in current_aliases_str.split(";"):
                    if "=" in pair:
                        source_key, alias_name = pair.split("=", 1)
                        aliases_dict[source_key.strip()] = alias_name.strip()

            # build removal options from current aliases
            remove_options:dict[str,str] = {}
            for source_key, alias_name in aliases_dict.items():
                display_name = f"{alias_name} ({source_key})"
                remove_options[source_key] = display_name

            # build schema
            schema_dict:dict = {}
            
            # show current aliases for removal if any exist
            if remove_options:
                schema_dict[vol.Optional("remove_aliases", 
                                         default=[]
                                         )] = cv.multi_select(remove_options)

            # show form to add new alias
            # build options list with empty string as first option to allow skipping source selection
            source_options = [""] + list(source_list_all.keys())
            schema_dict[vol.Optional("add_source",
                                     default=""
                                     )] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=source_options,
                    multiple=False,
                    custom_value=False
                ),
            )
            schema_dict[vol.Optional("add_alias_name",
                                     default=""
                                     )] = cv.string

            # add action selection field
            schema_dict[vol.Optional("next_action",
                                     default="continue_editing"
                                     )] = vol.In({
                "continue_editing": "Continue Editing",
                "save_and_close": "Save and Close"
            })

            schema = vol.Schema(schema_dict)

            _logsi.LogVerbose("'%s': OptionsFlow is showing the aliases configuration form" % self._name)
            return self.async_show_form(
                step_id="aliases",
                data_schema=schema,
                description_placeholders={CONF_NAME: self._name},
                errors=errors or {}
            )

        except Exception as ex:

            # trace.
            _logsi.LogException(None, ex, logToSystemLogger=False)
            raise

        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    
    async def _update_options(self, options:dict[str,Any]=None) -> FlowResult:
        """
        Update config entry options.
        """
        try:

            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogDictionary(SILevel.Verbose, "'%s': OptionsFlow is updating configuration options - options" % self._name, options)
            
            # update the configuration entry options.
            return self.async_create_entry(
                title="", 
                data=options
            )
    
        finally:

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)


    def _GetSourceTitleList(self, host:str, port:int) -> dict:
        """
        Retrieves SourceList object from the SoundTouch device.
        Returns a dictionary mapping source identifiers to display titles.
        """
        try:

            _logsi.LogVerbose("'%s': OptionsFlow is creating SoundTouchDevice instance (port=%s)" % (self._name, port))
            device:SoundTouchDevice = SoundTouchDevice(host, 30, None, port)

            _logsi.LogVerbose("'%s': OptionsFlow is creating SoundTouchClient instance" % self._name)
            client:SoundTouchClient = SoundTouchClient(device)
            
            # get device source list.
            _logsi.LogVerbose("'%s': OptionsFlow is retrieving SourceList configuration for device" % self._name)
            sourceList:SourceList = client.GetSourceList()
            
            # sort the results (in place) by SourceTitle, ascending order.
            sourceList.SourceItems.sort(key=lambda x: (x.SourceTitle or "").lower(), reverse=False)
           
            # build dictionary of source identifiers to display titles.
            # use SourceTitle as the key for simplicity since it's unique.
            result:dict = {}
            item:SourceItem
            for item in sourceList:
                if item.SourceTitle not in result:
                    result[item.SourceTitle] = item.SourceTitle

            _logsi.LogDictionary(SILevel.Verbose, "'%s': OptionsFlow ALL available '%s' items for device" % (self._name, CONF_OPTION_SOURCE_LIST), result)
            
            return result
            
        except Exception as ex:
            
            _logsi.LogError("'%s': OptionsFlow could not retrieve source list for device: %s" % (self._name, str(ex)))
            return None


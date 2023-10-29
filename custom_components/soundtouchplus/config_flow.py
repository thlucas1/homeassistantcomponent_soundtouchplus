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

import logging

from bosesoundtouchapi import SoundTouchDevice
from requests import RequestException
from typing import Any
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_WS_PORT,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ID,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_WS_PORT
)

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession
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
        device:SoundTouchDevice = await hass.async_add_executor_job(
             SoundTouchDevice, host, timeout, None, port
        )

        _logsi.LogVerbose("ConfigFlow HTTP connection is valid for device: IP=%s, port=%s, name=%s, id=%s" % (host, port, device.DeviceName, device.DeviceId))

        # return other device details that we want to store in the config entry.
        # CONF_DEVICE_NAME is what is displayed to the user for this device.
        return {
            CONF_DEVICE_NAME: device.DeviceName,
            CONF_DEVICE_ID: device.DeviceId,
        }

    except Exception as ex:
        # return self.async_abort(reason="cannot_connect")
        raise CannotConnect from ex


class SoundTouchPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle a config flow for Bose SoundTouchPlus.

    Config entries uses the data flow entry framework to define their config flows. 
    The config flow needs to be defined in the file config_flow.py in your integration 
    folder, extend homeassistant.config_entries.ConfigFlow and pass a domain key as 
    part of inheriting ConfigFlow.    
    """
    VERSION = 1

    def __init__(self):
        """
        Initialize a new SoundTouchPlus configflow.
        """
        _logsi.LogVerbose("ConfigFlow is initializing")
        self._name: str | None = None
        self._host: str | None = None
        self._port: int | None = DEFAULT_PORT
        self._ws_port: int | None = DEFAULT_WS_PORT
        self._discovery_name: str | None = None
        self._device_id: str | None = None


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

                # one final check to see if a configuration entry already exists for the device.
                # If it IS already configured, then we will send an "already_configured" message 
                # to the user and halt the flow to prevent a duplicate configuration entry.
                _logsi.LogVerbose("ConfigFlow is verifying USER ENTRY device details have not already been configured: IP=%s, port=%s, name=%s, id=%s" % (self._host, self._port, self._name, self._device_id))
                await self.async_set_unique_id(self._name)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_NAME: self._name,
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
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
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_PORT, default=default_port): cv.port,
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

        # one final check to see if a configuration entry already exists for the device.
        # If it IS already configured, then we will send an "already_configured" message 
        # to the user and halt the flow to prevent a duplicate configuration entry.
        _logsi.LogVerbose("ConfigFlow is verifying ZeroConf discovered device details have not already been configured: IP=%s, port=%s, name=%s, id=%s" % (self._host, self._port, self._name, self._device_id))
        await self.async_set_unique_id(self._name)
        self._abort_if_unique_id_configured(
            updates={
                CONF_NAME: self._name,
                CONF_HOST: self._host,
                CONF_PORT: self._port,
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
        _logsi.LogDictionary(SILevel.Verbose, "ConfigFlow is creating a configuration entry for a deviceIP=%s, port=%s, name=%s, id=%s" % (self._host, self._port, self._name, self._device_id), configData)
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
            CONF_WS_PORT: self._ws_port,
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

"""Provide info to system health."""
from typing import Any
import json

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .instancedata_soundtouchplus import InstanceDataSoundTouchPlus

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession
import logging
_logsi:SISession = SIAuto.Si.GetSession(__name__)
if (_logsi == None):
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


@callback
def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info, "/config/integrations/integration/%s" % DOMAIN)


async def system_health_info(hass):
    """Get info for the info page."""

    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)

        # create dictionary for health information.
        healthInfo: dict[str, Any] = {}
    
        # add manifest file details.
        # as of HA 2024.6, we have to use an executor job to load the file contents as the trace uses a blocking file open / read call.
        myConfigDir:str = "%s/custom_components/%s" % (hass.config.config_dir, DOMAIN)
        myManifestPath:str = "%s/manifest.json" % (myConfigDir)
        myManifest:dict = await hass.async_add_executor_job(_getManifestFile, myManifestPath, "Integration Manifest File (%s)" % myManifestPath)
        healthInfo["integration_version"] = myManifest.get('version','unknown')

        # add device configuration data.
        deviceConfig:str = ""
        if len(hass.data[DOMAIN]) > 0:
            deviceConfig = str("%d: " % len(hass.data[DOMAIN]))
            data:InstanceDataSoundTouchPlus = None
            for data in hass.data[DOMAIN].values():
                _logsi.LogDictionary(SILevel.Verbose, "InstanceDataSoundTouchPlus data", data, prettyPrint=True)
                if data.client != None:
                    if data.client.Device != None:
                        deviceConfig = deviceConfig + "%s (%s), " % (data.client.Device.DeviceName, data.client.Device.DeviceType)
            deviceConfig = deviceConfig[:len(deviceConfig)-2]  # drop ending ", "
        else:
            deviceConfig = "(None Defined)"
        healthInfo["devices_configured"] = deviceConfig
        
        # trace.
        _logsi.LogDictionary(SILevel.Verbose, "System Health results", healthInfo)

        # return system health data.
        return healthInfo

    except Exception as ex:
            
        # trace.
        _logsi.LogException("system_health_info exception: %s" % str(ex), ex, logToSystemLogger=False)
        raise
        
    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


def _getManifestFile(filePath: str, title: str) -> str:
    """
    Loads the contents of the specified text file and returns them.
    
    Args:
        filePath (str):
            Fully-qualified file path to log.
        title (str):
            Title to assign to the log entry.

    """
    try:

        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogTextFile(SILevel.Verbose, title, filePath)

        # open file and read the contents.
        with open(filePath) as reader:
            data = reader.read()
            
        # return contents to caller.
        return json.loads(data) 

    except Exception as ex:
            
        # trace.
        _logsi.LogException("system_health_info _getManifestFile exception: %s" % str(ex), ex, logToSystemLogger=False)
        return {}
        
    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)

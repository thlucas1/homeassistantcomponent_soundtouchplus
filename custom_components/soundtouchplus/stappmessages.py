# external package imports.
# none

# our package imports.
# none

class STAppMessages:
    """
    A strongly-typed resource class, for looking up localized strings, etc.
    
    Threadsafety:
        This class is fully thread-safe.
    """

    MSG_SERVICE_ARGUMENT_NULL:str = "The '%s' service parameter was not specified for the '%s' service call"
    """
    The '%s' service parameter was not specified for the '%s' service call
    """

    MSG_ARGUMENT_NULL:str = "The '%s' argument was not specified for the '%s' function"
    """
    The '%s' argument was not specified for the '%s' function
    """

    MSG_SERVICE_CALL_START:str = "Processing service call '%s' in async '%s' method"
    """
    Processing service call '%s' in async '%s' method
    """

    MSG_SERVICE_CALL_PARM:str = "ServiceCall Parameters"
    """
    ServiceCall Parameters
    """

    MSG_SERVICE_CALL_DATA:str = "ServiceCall Data"
    """
    ServiceCall Data
    """

    MSG_SERVICE_REQUEST_REGISTER:str = "SoundTouch - Component async_setup is registering component async service request: '%s'"
    """
    SoundTouch - Component async_setup is registering component async service request: '%s'
    """

    MSG_SERVICE_REQUEST_UNKNOWN:str = "Service request '%s' was not recognized by the '%s' method"
    """
    Service request '%s' was not recognized by the '%s' method
    """

    MSG_SERVICE_REQUEST_EXCEPTION:str = "An unhandled exception occurred in Service request method '%s'; exception: %s"
    """
    Service request '%s' was not recognized by the '%s' method
    """

    MSG_PLAYER_COMMAND:str = "Executing '%s' command for SoundTouch device '%s' (id=%s)"
    """
    Executing '%s' command for SoundTouch device '%s' (id=%s)
    """

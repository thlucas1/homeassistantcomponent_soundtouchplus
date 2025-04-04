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

    MSG_SERVICE_EXECUTE:str = "Executing '%s' service on media player '%s'"
    """
    Executing '%s' service on media player '%s'
    """
    
    MSG_SERVICE_REQUEST_REGISTER:str = "Component async_setup is registering async service: '%s'"
    """
    Component async_setup is registering component async service request: '%s'
    """

    MSG_SERVICE_REQUEST_UNKNOWN:str = "Service request '%s' was not recognized by the '%s' method"
    """
    Service request '%s' was not recognized by the '%s' method
    """

    MSG_SERVICE_REQUEST_EXCEPTION:str = "An unhandled exception occurred in Service request method '%s'; exception: %s"
    """
    Service request '%s' was not recognized by the '%s' method
    """

    MSG_MEDIAPLAYER_SERVICE:str = "'%s': MediaPlayer is executing service '%s'"
    """
    '%s': MediaPlayer is executing service '%s'
    """

    MSG_MEDIAPLAYER_SERVICE_WITH_PARMS:str = "'%s': MediaPlayer is executing service '%s' - parameters: %s"
    """
    '%s': MediaPlayer is executing service '%s' - parameters: %s
    """

    MSG_SPOTIFYPLUS_USERPROFILE:str = "'%s': spotifyplus integration service userProfile (partial)"
    """
    '%s': spotifyplus integration service userProfile (partial)
    """

    MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR:str = "'%s': spotifyPlus integration did not return a properly formatted userProfile for content type '%s'"
    """
    '%s': spotifyPlus integration did not return a properly formatted userProfile for content type '%s'
    """
    
    MSG_SPOTIFYPLUS_RESULT_ITEMS:str = "'%s': spotifyplus integration service result items"
    """
    '%s': spotifyplus integration service result items
    """

    MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR:str = "'%s': spotifyPlus integration did not return a properly formatted result for content type '%s'"
    """
    '%s': spotifyPlus integration did not return a properly formatted result for content type '%s'
    """
    
    MSG_SPOTIFYPLUS_RESULT_DICTIONARY:str = "'%s': result from spotifyplus integration service - dictionary"
    """
    '%s': result from spotifyplus integration service - dictionary
    """
    
    MSG_SPOTIFYPLUS_SERVICE_EXECUTE:str = "'%s': executing %s integration service for media content: '%s'"
    """
    '%s': executing %s integration service for media content: '%s'
    """
    
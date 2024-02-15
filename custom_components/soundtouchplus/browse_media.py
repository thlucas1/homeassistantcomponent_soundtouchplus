"""Support for SoundTouchPlus media browsing."""
from __future__ import annotations
import base64
import os
import pickle
import logging
from typing import Any

from homeassistant.backports.enum import StrEnum
from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from bosesoundtouchapi import *
from bosesoundtouchapi.models import *

from .const import DOMAIN

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIMethodParmListContext
import logging
_logsi:SISession = SIAuto.Si.GetSession(__name__)
if (_logsi == None):
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


class BrowsableMedia(StrEnum):
    """
    Enum of browsable media.
    Contains the library root node key value definitions.
    """
    # library custom root node title definitions.
    LIBRARY_INDEX = "library_index"
    PANDORA_STATIONS = "pandora_stations"
    SOUNDTOUCH_PRESETS = "soundtouch_presets"
    SOUNDTOUCH_RECENTLY_PLAYED = "soundtouch_recently_played"
    # CURRENT_USER_PLAYLISTS = "current_user_playlists"
    # CURRENT_USER_FOLLOWED_ARTISTS = "current_user_followed_artists"
    # CURRENT_USER_SAVED_ALBUMS = "current_user_saved_albums"
    # CURRENT_USER_SAVED_TRACKS = "current_user_saved_tracks"
    # CURRENT_USER_SAVED_SHOWS = "current_user_saved_shows"
    # CURRENT_USER_TOP_ARTISTS = "current_user_top_artists"
    # CURRENT_USER_TOP_TRACKS = "current_user_top_tracks"
    # CATEGORIES = "categories"
    # FEATURED_PLAYLISTS = "featured_playlists"
    # NEW_RELEASES = "new_releases"


LIBRARY_MAP = {
    BrowsableMedia.PANDORA_STATIONS.value: {
        "title": "Pandora Stations",
        "image": f"/local/images/{DOMAIN}_medialib_pandora_stations.png",
    },
    BrowsableMedia.SOUNDTOUCH_PRESETS.value: {
        "title": "Presets",
        "image": f"/local/images/{DOMAIN}_medialib_presets.png",
    },
    BrowsableMedia.SOUNDTOUCH_RECENTLY_PLAYED.value: {
        "title": "Recently Played",
        "image": f"/local/images/{DOMAIN}_medialib_recently_played.png",
    },
    # BrowsableMedia.CURRENT_USER_PLAYLISTS.value: "Playlists",
    # BrowsableMedia.CURRENT_USER_FOLLOWED_ARTISTS.value: "Artists",
    # BrowsableMedia.CURRENT_USER_SAVED_ALBUMS.value: "Albums",
    # BrowsableMedia.CURRENT_USER_SAVED_TRACKS.value: "Tracks",
    # BrowsableMedia.CURRENT_USER_SAVED_SHOWS.value: "Podcasts",
    # BrowsableMedia.CURRENT_USER_TOP_ARTISTS.value: "Top Artists",
    # BrowsableMedia.CURRENT_USER_TOP_TRACKS.value: "Top Tracks",
    # BrowsableMedia.CATEGORIES.value: "Categories",
    # BrowsableMedia.FEATURED_PLAYLISTS.value: "Featured Playlists",
    # BrowsableMedia.NEW_RELEASES.value: "New Releases",
}
""" Library index definitions, containing a title and (optional) image to display. """


CONTENT_TYPE_MEDIA_CLASS: dict[str, Any] = {
    BrowsableMedia.LIBRARY_INDEX.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.PANDORA_STATIONS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SOUNDTOUCH_PRESETS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SOUNDTOUCH_RECENTLY_PLAYED.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    # BrowsableMedia.CURRENT_USER_PLAYLISTS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.PLAYLIST,
    # },
    # BrowsableMedia.CURRENT_USER_FOLLOWED_ARTISTS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.ARTIST,
    # },
    # BrowsableMedia.CURRENT_USER_SAVED_ALBUMS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.ALBUM,
    # },
    # BrowsableMedia.CURRENT_USER_SAVED_TRACKS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.TRACK,
    # },
    # BrowsableMedia.CURRENT_USER_SAVED_SHOWS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.PODCAST,
    # },
    # BrowsableMedia.CURRENT_USER_TOP_ARTISTS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.ARTIST,
    # },
    # BrowsableMedia.CURRENT_USER_TOP_TRACKS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.TRACK,
    # },
    # BrowsableMedia.FEATURED_PLAYLISTS.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.PLAYLIST,
    # },
    # BrowsableMedia.CATEGORIES.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.GENRE,
    # },
    # "category_playlists": {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.PLAYLIST,
    # },
    # BrowsableMedia.NEW_RELEASES.value: {
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.ALBUM,
    # },
    # MediaType.PLAYLIST: {
    #     "parent": MediaClass.PLAYLIST,
    #     "children": MediaClass.TRACK,
    # },
    # MediaType.ALBUM: {
    #     "parent": MediaClass.ALBUM, 
    #     "children": MediaClass.TRACK,
    # },
    # MediaType.ARTIST: {
    #     "parent": MediaClass.ARTIST, 
    #     "children": MediaClass.ALBUM,
    # },
    # MediaType.EPISODE: {
    #     "parent": MediaClass.EPISODE, 
    #     "children": None,
    # },
    # MediaType.TRACK: {
    #     "parent": MediaClass.TRACK, 
    #     "children": None,
    # }
}
"""
Dictionary of content types for the various custom root node types and 
Home Assistant base media types.
"""

CONTENT_ITEM_BASE64:str = "ci_base64::"
""" eye-catcher used to denote a serialized ContentItem. """

LOCAL_IMAGE_PREFIX:str = "/local/"
""" Local image prefix value. """

PLAYABLE_MEDIA_TYPES = [
    MediaType.TRACK,
]


class MediaSourceNotFoundError(BrowseError):
    """ Source could not be found selected media type. """


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


async def async_browse_media_library_index(hass:HomeAssistant,
                                           client:SoundTouchClient,
                                           playerName:str,
                                           source:str|None,
                                           media_content_type:str|None,
                                           media_content_id:str|None,
                                           ) -> BrowseMedia:
    """
    Builds a BrowseMedia object for the top level index page, and all of it's
    child nodes.
    
    Args:
        client (SoundTouchClient):
            The SoundTouchClient instance that will make calls to the device
            to retrieve the data for display in the media browser.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        source (str):
            Currently selected source value.
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.
    """
    methodParms:SIMethodParmListContext = None
        
    try:

        # trace.
        methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
        methodParms.AppendKeyValue("playerName", playerName)
        methodParms.AppendKeyValue("source", source)
        methodParms.AppendKeyValue("media_content_type", media_content_type)
        methodParms.AppendKeyValue("media_content_id", media_content_id)
        _logsi.LogMethodParmList(SILevel.Verbose, "'%s': MediaPlayer is browsing for media - top level index" % playerName, methodParms)
        
        # validations.
        if source is None:
            source = "unknownSource"
            
        # set index media class based upon media content type.
        mediaClassMap:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(BrowsableMedia.LIBRARY_INDEX.value, None)
        _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer BrowseMedia mediaClassMap Dictionary for media content type: '%s'" % (playerName, BrowsableMedia.LIBRARY_INDEX.value), mediaClassMap)

        # create the index.
        browseMedia:BrowseMedia = BrowseMedia(
            can_expand=True,
            can_play=False,
            children=[],
            children_media_class=mediaClassMap["parent"],
            media_class=mediaClassMap["parent"],
            media_content_id=BrowsableMedia.LIBRARY_INDEX.value,
            media_content_type=BrowsableMedia.LIBRARY_INDEX.value,
            title="SoundTouchPlus Media Library",
            )

        # add child items to the index.
        for mediaType, mediaAttrs in LIBRARY_MAP.items():
            
            # set child media class based upon media content type.
            mediaClassMapChild:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(mediaType, None)

            # if a LOCAL index image was specified, then ensure it exists.
            # otherwise, default to null.
            image:str = mediaAttrs.get("image", None)
            if image is not None and image.startswith(LOCAL_IMAGE_PREFIX):
                imagePath:str = "%s/www/%s" % (hass.config.config_dir, image[len(LOCAL_IMAGE_PREFIX):])
                if not os.path.exists(imagePath):
                    _logsi.LogVerbose("'%s': MediaPlayer could not find logo image path '%s'; image will be reset to null" % (playerName, imagePath))
                    image = None

            browseMediaChild:BrowseMedia = BrowseMedia(
                can_expand=True,
                can_play=False,
                children=None,
                children_media_class=mediaClassMapChild["children"],
                media_class=mediaClassMapChild["parent"],
                media_content_id=f"{mediaType}",
                media_content_type=f"{mediaType}",
                title=mediaAttrs.get("title", "Unknown"),
                thumbnail=image
                )
            browseMedia.children.append(browseMediaChild)
                
            _logsi.LogObject(SILevel.Verbose, "BrowseMedia Child Object: Type='%s', Id='%s', Title='%s'" % (browseMediaChild.media_content_type, browseMediaChild.media_content_id, browseMediaChild.title), browseMediaChild)


        # add base media library items to the index.
        #_logsi.LogVerbose("'%s': MediaPlayer is adding base media library child items" % playerName)
        media:BrowseMedia = await media_source.async_browse_media(hass, media_content_id)
        mediaChild:BrowseMedia
        for mediaChild in media.children:
            _logsi.LogObject(SILevel.Verbose, "'%s': MediaPlayer is adding base media library child item: '%s'" % (playerName, mediaChild.title), mediaChild)
            browseMedia.children.append(mediaChild)
                
        # trace.
        _logsi.LogObject(SILevel.Verbose, "BrowseMedia Parent Object: Type='%s', Id='%s', Title='%s'" % (browseMedia.media_content_type, browseMedia.media_content_id, browseMedia.title), browseMedia)

        return browseMedia

    except Exception as ex:
            
        # trace.
        _logsi.LogException("'%s': MediaPlayer async_browse_media exception: %s" % (playerName, str(ex)), ex, logToSystemLogger=False)
        raise HomeAssistantError(str(ex)) from ex
        
    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


def browse_media_node(hass:HomeAssistant,
                      client:SoundTouchClient,
                      playerName:str,
                      source:str|None,
                      media_content_type:str|None,
                      media_content_id:str|None,
                      ) -> BrowseMedia:
    """
    Builds a BrowseMedia object for a selected media content type, and all of it's
    child nodes.
    
    Args:
        client (SoundTouchClient):
            The SoundTouchClient instance that will make calls to the device
            to retrieve the data for display in the media browser.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        source (str):
            Currently selected source value.
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.
    """
    methodParms:SIMethodParmListContext = None
        
    try:

        # trace.
        methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
        methodParms.AppendKeyValue("playerName", playerName)
        methodParms.AppendKeyValue("source", source)
        methodParms.AppendKeyValue("media_content_type", media_content_type)
        methodParms.AppendKeyValue("media_content_id", media_content_id)
        _logsi.LogMethodParmList(SILevel.Verbose, "'%s': MediaPlayer is browsing for media - selected node" % playerName, methodParms)
        
        # validations.
        if source is None:
            source = "unknownSource"
            
        title:str = None
        image:str = None
        media:object = None
        items:list = []
        mediaClassChild:str = None
        
        # get child media class value.
        mediaClassMapChild:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(media_content_type, None)
        mediaClassChild = mediaClassMapChild["children"]
        
        # build selection list based upon the browsable media type.
        # - media: will contain the result of the soundtouch api call.
        # - items: will contain the child items to display for the media item.
        # - title: the title to display in the media browser.
        # - image: the image (if any) to display in the media browser (can be none).
        if media_content_type == BrowsableMedia.SOUNDTOUCH_PRESETS:
            _logsi.LogVerbose("'%s': MediaPlayer is querying client device for SoundTouch presets" % playerName)
            media:PresetList = client.GetPresetList(refresh=True, resolveSourceTitles=True)
            items = media.Presets
            title = "SoundTouch Presets"
            image = None  # no parent image
            mediaTypeChild = MediaType.TRACK
            mediaClassMapChild:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(media_content_type, None)
            
        elif media_content_type == BrowsableMedia.SOUNDTOUCH_RECENTLY_PLAYED:
            _logsi.LogVerbose("'%s': MediaPlayer is querying client device for SoundTouch recently played items" % playerName)
            media:RecentList = client.GetRecentList(True, resolveSourceTitles=True)
            items = media.Recents
            title = "SoundTouch Recently Played"
            image = None  # no parent image
            mediaTypeChild = MediaType.TRACK
            mediaClassMapChild:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(media_content_type, None)
            
        elif media_content_type == BrowsableMedia.PANDORA_STATIONS:
            _logsi.LogVerbose("'%s': MediaPlayer is querying client device for Pandora stations" % playerName)
            sourceItems:SourceList = client.GetSourceList(refresh=False)
            sourceItem:SourceItem
            for sourceItem in sourceItems:
                if sourceItem.Source == SoundTouchSources.PANDORA.value:
                    criteria:Navigate = Navigate(sourceItem.Source, sourceItem.SourceAccount)
                    media:NavigateResponse = client.GetMusicServiceStations(criteria)
                    items = media.Items
                    title = "SoundTouch Pandora Stations"
                    mediaTypeChild = MediaType.TRACK
                    mediaClassMapChild:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(media_content_type, None)
                    break
            if media is None:
                raise MediaSourceNotFoundError("'%s': MediaPlayer could not find SoundTouch Source for '%s' content" % (playerName, media_content_type))
            
        # if media was not set then we are done.
        if media is None:
            raise ValueError("'%s': MediaPlayer could not find media items for content type '%s'" % (playerName, media_content_type))

        # set index media class based upon media content type.
        mediaClassMap:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(media_content_type, None)
        _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer BrowseMedia mediaClassMap Dictionary for media content type: '%s'" % (playerName, media_content_type), mediaClassMap)

        # set index flag indicating if index media can be played or not.
        canPlay:bool = media_content_type in PLAYABLE_MEDIA_TYPES
        
        # track and episode media items cannot be expanded (only played);
        # other media types can be expanded to display child items (e.g. Album, Artist, Playlist, etc).
        canExpand = media_content_type not in [
            MediaType.TRACK,
            MediaType.EPISODE,
        ]
        
        # if a LOCAL index image was specified, then ensure it exists.
        # otherwise, default to null.
        if image is not None and image.startswith(LOCAL_IMAGE_PREFIX):
            imagePath:str = "%s/www/%s" % (hass.config.config_dir, image[len(LOCAL_IMAGE_PREFIX):])
            if not os.path.exists(imagePath):
                _logsi.LogVerbose("'%s': MediaPlayer could not find logo image path '%s'; image will be reset to null" % (playerName, imagePath))
                image = None

        # create the index.
        browseMedia:BrowseMedia = BrowseMedia(
            can_expand=canExpand,
            can_play=canPlay,
            children=[],
            children_media_class=mediaClassMap["children"],
            media_class=mediaClassMap["parent"],
            media_content_id=media_content_id,
            media_content_type=media_content_type,
            thumbnail=image,
            title=title,
            )

        # add child items to the index.
        for item in items:
            
            # set child media class based upon media content type.
            mediaClassMapChild:dict[str, Any] = CONTENT_TYPE_MEDIA_CLASS.get(media_content_type, None)

            # set child flag indicating if media can be played or not.
            canPlay:bool = mediaTypeChild in PLAYABLE_MEDIA_TYPES
        
            # track and episode media items cannot be expanded (only played);
            # other media types can be expanded to display child items (e.g. Album, Artist, Playlist, etc).
            canExpand = mediaTypeChild not in [
                MediaType.TRACK,
                MediaType.EPISODE,
            ]

            # serialize content item to a string so we can place it in the media_content_id field.
            # it stinks that we have to do this, but there are no custom fields in the BrowseMedia
            # class that pass through to the UI and back!
            ciSerialized:str = serialize_object(item.ContentItem)

            #_logsi.LogText(SILevel.Verbose, "media_content_id length (pickle) = %d" % len(ciSerialized), ciSerialized)

            browseMediaChild:BrowseMedia = BrowseMedia(
                can_expand=canExpand,
                can_play=canPlay,
                children=None,
                children_media_class=None,
                media_class=mediaClassChild,
                media_content_id=f'{CONTENT_ITEM_BASE64}{ciSerialized}',
                media_content_type=mediaTypeChild,
                thumbnail=item.ContentItem.ContainerArt, # item.ContainerArt,
                title=item.Name,
                )
            browseMedia.children.append(browseMediaChild)
                
            _logsi.LogObject(SILevel.Verbose, "BrowseMedia Child Object: Type='%s', Id='%s', Title='%s'" % (browseMediaChild.media_content_type, browseMediaChild.media_content_id, browseMediaChild.title), browseMediaChild)

        # trace.
        _logsi.LogObject(SILevel.Verbose, "BrowseMedia Parent Object: Type='%s', Id='%s', Title='%s'" % (browseMedia.media_content_type, browseMedia.media_content_id, browseMedia.title), browseMedia)

        return browseMedia

    except Exception as ex:
            
        # trace.
        _logsi.LogException("'%s': MediaPlayer async_browse_media exception: %s" % (playerName, str(ex)), ex, logToSystemLogger=False)
        raise HomeAssistantError(str(ex)) from ex
        
    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


@staticmethod
def serialize_object(obj:object) -> str:
    """
    Serialize an object into a plain text string.
    
    Args:
        obj (object):
            The object to serialize.
            
    Returns:
        A serialized base64 string representation of the object.
    """
    message_bytes = pickle.dumps(obj)
    base64_bytes = base64.b64encode(message_bytes)
    txt = base64_bytes.decode('ascii')
    return txt


def deserialize_object(txt:str) -> object:
    """
    Deserialize an object from a plain text string.
    
    Args:
        txt (str):
            The serialized version of the object in the form of a string.
            
    Returns:
        An object that was deserialized from a base64 string representation.
    """
    base64_bytes = txt.encode('ascii')
    message_bytes = base64.b64decode(base64_bytes)
    obj = pickle.loads(message_bytes)
    return obj

"""Support for SoundTouchPlus media browsing."""
from __future__ import annotations
from asyncio import run_coroutine_threadsafe
import base64
import os
import pickle
import logging
from typing import Any, Tuple

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
from spotifywebapipython import SpotifyClient
from spotifywebapipython.models import (
    Album,
    AlbumPageSaved,
    AlbumPageSimplified,
    AlbumSimplified,
    Artist,
    ArtistPage,
    Category,
    CategoryPage,
    EpisodeSimplified,
    PlayHistoryPage,
    Playlist,
    PlaylistPageSimplified, 
    PlaylistSimplified, 
    Show,
    ShowPageSaved,
    ShowSaved,
    Track,
    TrackPage,
    TrackPageSaved,
    UserProfile
)
from spotifywebapipython.sautils import GetUnixTimestampMSFromUtcNow

from .const import DOMAIN, DOMAIN_SPOTIFYPLUS
from .instancedata_soundtouchplus import InstanceDataSoundTouchPlus
from .stappmessages import STAppMessages

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIColors, SIMethodParmListContext
import logging
_logsi:SISession = SIAuto.Si.GetSession(__name__)
if (_logsi == None):
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


MEDIA_TYPE_SHOW = "show"
""" Spotify Show media type (aka PODCAST in HA) """

MEDIA_TYPE_CATEGORY = "spotify_category"
""" Spotify Show media type (aka PODCAST in HA) """

SPOTIFY_BROWSE_LIMIT = 50
""" Max number of items to return from a Spotify Web API query. """

SPOTIFY_BROWSE_LIMIT_TOTAL = 200
""" Max number of items to return from a SpotifyPlus integration request that supports paging. """

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
    # spotify library types should all start with "spotify_".
    SPOTIFY_LIBRARY_INDEX = "spotify_library_index"
    SPOTIFY_CATEGORY_PLAYLISTS = "spotify_category_playlists"
    SPOTIFY_CATEGORY_PLAYLISTS_MADEFORYOU = "spotify_category_playlists_madeforyou"
    SPOTIFY_CATEGORYS = "spotify_categorys"
    SPOTIFY_FEATURED_PLAYLISTS = "spotify_featured_playlists"
    SPOTIFY_NEW_RELEASES = "spotify_new_releases"
    #SPOTIFY_USER_DAILY_MIXES = "spotify_user_daily_mixes"
    SPOTIFY_USER_FOLLOWED_ARTISTS = "spotify_user_followed_artists"
    SPOTIFY_USER_PLAYLISTS = "spotify_user_playlists"
    SPOTIFY_USER_RECENTLY_PLAYED = "spotify_user_recently_played"
    SPOTIFY_USER_SAVED_ALBUMS = "spotify_user_saved_albums"
    SPOTIFY_USER_SAVED_SHOWS = "spotify_user_saved_shows"
    SPOTIFY_USER_SAVED_TRACKS = "spotify_user_saved_tracks"
    SPOTIFY_USER_TOP_ARTISTS = "spotify_user_top_artists"
    SPOTIFY_USER_TOP_TRACKS = "spotify_user_top_tracks"


LIBRARY_MAP = {
    BrowsableMedia.LIBRARY_INDEX.value: {
        "title": "SoundTouchPlus Media Library",
        "image": None,
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.DIRECTORY,
        "is_index_item": False,
    },
    BrowsableMedia.PANDORA_STATIONS.value: {
        "title": "Pandora Stations",
        "title_node": "SoundTouchPlus Pandora Stations",
        "image": f"/local/images/{DOMAIN}_medialib_pandora_stations.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SOUNDTOUCH_PRESETS.value: {
        "title": "Presets",
        "title_node": "SoundTouchPlus Presets",
        "image": f"/local/images/{DOMAIN}_medialib_presets.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
        "is_index_item": True,
    },
    BrowsableMedia.SOUNDTOUCH_RECENTLY_PLAYED.value: {
        "title": "Recently Played",
        "title_node": "SoundTouchPlus Recently Played",
        "image": f"/local/images/{DOMAIN}_medialib_recently_played.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SPOTIFY_LIBRARY_INDEX.value: {
        "title": "Spotify",
        "title_node": "SoundTouchPlus Spotify Media Library",
        "image": f"/local/images/{DOMAIN}_medialib_spotify.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.DIRECTORY,
        "is_index_item": True,
    },
    # the following are HA media types, and will not be displayed in the library index.
    # they are required for playing base-level types of media for this library index.
    MediaType.PLAYLIST: {
        "parent": MediaClass.PLAYLIST,
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.ALBUM: {
        "parent": MediaClass.ALBUM, 
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.ARTIST: {
        "parent": MediaClass.ARTIST, 
        "children": MediaClass.ALBUM,
        "is_index_item": False,
    },
    MediaType.EPISODE: {
        "parent": MediaClass.EPISODE, 
        "children": None,
        "is_index_item": False,
    },
    MediaType.PODCAST: {
        "parent": MediaClass.PODCAST,
        "children": MediaClass.EPISODE,
        "is_index_item": False,
    },
    MEDIA_TYPE_SHOW: {
        "parent": MediaClass.PODCAST,
        "children": MediaClass.EPISODE,
        "is_index_item": False,
    },
    MediaType.TRACK: {
        "parent": MediaClass.TRACK, 
        "children": None,
        "is_index_item": False,
    }
}
""" 
Library index definitions, containing media attributes that control content display. 
The order listed is how they are displayed in the media browser.
"""


# Spotify Library index definitions, containing media attributes that control content display.
# The order listed is how they are displayed in the media browser.
SPOTIFY_LIBRARY_MAP = {
    BrowsableMedia.SPOTIFY_LIBRARY_INDEX.value: {
        "title": "SoundTouchPlus Spotify Media Library",
        "title_with_name": "SoundTouchPlus Spotify Media Library (%s)",   # used by media_player to add SpotifyPlus entity name suffix
        "image": None,
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.DIRECTORY,
        "is_index_item": False,
    },
    BrowsableMedia.SPOTIFY_USER_PLAYLISTS.value: {
        "title": "Playlists",
        "title_node": "Spotify Playlist Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_playlists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.SPOTIFY_USER_FOLLOWED_ARTISTS.value:  {
        "title": "Artists",
        "title_node": "Spotify Artists Followed",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_artists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ARTIST,
    },
    BrowsableMedia.SPOTIFY_USER_SAVED_ALBUMS.value:  {
        "title": "Albums",
        "title_node": "Spotify Album Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_albums.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ALBUM,
    },
    BrowsableMedia.SPOTIFY_USER_SAVED_TRACKS.value:  {
        "title": "Tracks",
        "title_node": "Spotify Track Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_tracks.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SPOTIFY_USER_SAVED_SHOWS.value:  {
        "title": "Podcasts",
        "title_node": "Spotify Podcast Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_podcasts.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PODCAST,
    },
    BrowsableMedia.SPOTIFY_USER_TOP_ARTISTS.value:  {
        "title": "Top Artists",
        "title_node": "Spotify Top Artists",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_top_artists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ARTIST,
    },
    BrowsableMedia.SPOTIFY_USER_TOP_TRACKS.value:  {
        "title": "Top Tracks",
        "title_node": "Spotify Top Tracks",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_top_tracks.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SPOTIFY_FEATURED_PLAYLISTS.value:  {
        "title": "Featured Playlists",
        "title_node": "Spotify Featured Playlists",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_featured_playlists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.SPOTIFY_NEW_RELEASES.value:  {
        "title": "New Releases",
        "title_node": "Spotify Album New Releases",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_new_releases.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ALBUM,
    },
    BrowsableMedia.SPOTIFY_CATEGORYS.value:  {
        "title": "Categories",
        "title_node": "Spotify Categories ",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_categorys.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.GENRE,
    },
    BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS.value:  {
        "title": "Category Playlists",
        "title_node": "Spotify Category Playlists",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_category_playlists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
        "is_index_item": False,
    },
    BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS_MADEFORYOU.value:  {
        "title": "Made For You",
        "title_node": "Spotify Playlists Made For You",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_category_playlists_madeforyou.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    # BrowsableMedia.SPOTIFY_USER_DAILY_MIXES.value: {
    #     "title": "Daily Mixes",
    #     "title_node": "Spotify Daily Mix Playlists",
    #     "image": f"/local/images/{DOMAIN}_medialib_spotify_daily_mixes.png",
    #     "parent": MediaClass.DIRECTORY,
    #     "children": MediaClass.PLAYLIST,
    # },
    BrowsableMedia.SPOTIFY_USER_RECENTLY_PLAYED.value:  {
        "title": "Recently Played",
        "title_node": "Spotify Recently Played",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_recently_played.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    # the following are HA media types, and will not be displayed in the library index.
    # they are required for playing base-level types of media for this library index.
    MediaType.ALBUM: {
        "parent": MediaClass.ALBUM, 
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.ARTIST: {
        "parent": MediaClass.ARTIST, 
        "children": MediaClass.ALBUM,
        "is_index_item": False,
    },
    MediaType.EPISODE: {
        "parent": MediaClass.EPISODE, 
        "children": None,
        "is_index_item": False,
    },
    MediaType.GENRE: {
        "parent": MediaClass.PLAYLIST,
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.PLAYLIST: {
        "parent": MediaClass.PLAYLIST,
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.PODCAST: {
        "parent": MediaClass.PODCAST, 
        "children": MediaClass.EPISODE,
        "is_index_item": False,
    },
    MEDIA_TYPE_SHOW: {
        "parent": MediaClass.PODCAST, 
        "children": MediaClass.EPISODE,
        "is_index_item": False,
    },
    MediaType.TRACK: {
        "parent": MediaClass.TRACK, 
        "children": None,
        "is_index_item": False,
    }
}
"""
Spotify Library index definitions, containing media attributes that control content display.
The order listed is how they are displayed in the media browser.
"""


CATEGORY_BASE64:str = "category_base64::"
""" Eye-catcher used to denote a serialized ContentItem. """

CONTENT_ITEM_BASE64:str = "ci_base64::"
""" Eye-catcher used to denote a serialized ContentItem. """


LOCAL_IMAGE_PREFIX:str = "/local/"
""" Local image prefix value. """


PLAYABLE_MEDIA_TYPES = [
    MediaType.PLAYLIST,
    MediaType.ALBUM,
    MediaType.ARTIST,
    MediaType.EPISODE,
    MediaType.PODCAST,
    MEDIA_TYPE_SHOW,
    MediaType.TRACK,
]
""" Array of all media types that are playable. """


class MediaSourceNotFoundError(BrowseError):
    """ Source could not be found for selected media type. """


class MissingMediaInformation(BrowseError):
    """ Missing required media information. """


class UnknownMediaType(BrowseError):
    """ Unknown media type. """


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


async def async_browse_media_library_index(hass:HomeAssistant,
                                           data:InstanceDataSoundTouchPlus,
                                           playerName:str,
                                           source:str|None,
                                           libraryMap:dict,
                                           libraryIndex:BrowsableMedia,
                                           media_content_type:str|None,
                                           media_content_id:str|None,
                                           ) -> BrowseMedia:
    """
    Builds a BrowseMedia object for the top level index page, and all of it's
    child nodes.
    
    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        source (str):
            Currently selected source value.
        libraryMap (dict):
            The library map that contains media content attributes for each library index entry.
        libraryIndex (BrowseMedia):
            The library index of media content types.
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
        methodParms.AppendKeyValue("libraryMap", libraryMap)
        methodParms.AppendKeyValue("libraryIndex", libraryIndex)
        methodParms.AppendKeyValue("media_content_type", media_content_type)
        methodParms.AppendKeyValue("media_content_id", media_content_id)
        _logsi.LogMethodParmList(SILevel.Verbose, "'%s': browsing for media - top level index: '%s'" % (playerName, libraryIndex), methodParms)
        
        # validations.
        if source is None:
            source = "unknownSource"
            
        # get parent media atttributes based upon selected media content type.
        parentAttrs:dict[str, Any] = libraryMap.get(libraryIndex.value, None)
        _logsi.LogDictionary(SILevel.Verbose, "'%s': BrowseMedia attributes for parent media content type: '%s'" % (playerName, libraryIndex.value), parentAttrs)

        # create the index.
        browseMedia:BrowseMedia = BrowseMedia(
            can_expand=True,
            can_play=False,
            children=[],
            children_media_class=parentAttrs["children"],
            media_class=parentAttrs["parent"],
            media_content_id=libraryIndex.value,
            media_content_type=libraryIndex.value,
            thumbnail=parentAttrs["image"],
            title=parentAttrs["title"],
            )

        # add child items to the index.
        for mediaType, childAttrs in libraryMap.items():

            # if not an index item then don't bother.
            isIndexItem:bool = childAttrs.get("is_index_item", True)
            if not isIndexItem:
                continue
            
            # trace.
            #_logsi.LogDictionary(SILevel.Verbose, "'%s': BrowseMedia attributes for child media content type: '%s'" % (playerName, mediaType), childAttrs)

            # if a LOCAL index image was specified, then ensure it exists.
            # otherwise, default to null.
            image:str = childAttrs.get("image", None)
            if image is not None and image.startswith(LOCAL_IMAGE_PREFIX):
                imagePath:str = "%s/www/%s" % (hass.config.config_dir, image[len(LOCAL_IMAGE_PREFIX):])
                if not os.path.exists(imagePath):
                    #_logsi.LogVerbose("'%s': could not find logo image path '%s'; image will be reset to null" % (playerName, imagePath))
                    image = None

            browseMediaChild:BrowseMedia = BrowseMedia(
                can_expand=True,
                can_play=False,
                children=None,
                children_media_class=childAttrs["children"],
                media_class=childAttrs["parent"],
                media_content_id=f"{mediaType}",
                media_content_type=f"{mediaType}",
                thumbnail=image,
                title=childAttrs["title"],
                )
            browseMedia.children.append(browseMediaChild)
            _logsi.LogObject(SILevel.Verbose, "'%s': BrowseMedia Child Object: Type='%s', Id='%s', Title='%s'" % (playerName, browseMediaChild.media_content_type, browseMediaChild.media_content_id, browseMediaChild.title), browseMediaChild)

        # add base media library items to the MAIN index.
        if libraryIndex == BrowsableMedia.LIBRARY_INDEX:
            media:BrowseMedia = await media_source.async_browse_media(hass, media_content_id)
            mediaChild:BrowseMedia
            for mediaChild in media.children:
                _logsi.LogObject(SILevel.Verbose, "'%s': adding base media library child item: '%s'" % (playerName, mediaChild.title), mediaChild)
                browseMedia.children.append(mediaChild)
                
        # trace.
        _logsi.LogObject(SILevel.Verbose, "'%s': BrowseMedia Parent Object: Type='%s', Id='%s', Title='%s'" % (playerName, browseMedia.media_content_type, browseMedia.media_content_id, browseMedia.title), browseMedia)

        return browseMedia

    except Exception as ex:
            
        # trace.
        _logsi.LogException("'%s': BrowseMedia async_browse_media_library_index exception: %s" % (playerName, str(ex)), ex, logToSystemLogger=False)
        raise HomeAssistantError(str(ex)) from ex
        
    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


def browse_media_node(hass:HomeAssistant,
                      data:InstanceDataSoundTouchPlus,
                      playerName:str,
                      source:str|None,
                      libraryMap:dict,
                      media_content_type:str|None,
                      media_content_id:str|None,
                      ) -> BrowseMedia:
    """
    Builds a BrowseMedia object for a selected media content type, and all of it's
    child nodes.
    
    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        source (str):
            Currently selected source value.
        libraryMap (dict):
            The library map that contains media content attributes for each library index entry.
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
        methodParms.AppendKeyValue("libraryMap", libraryMap)
        methodParms.AppendKeyValue("media_content_type", media_content_type)
        methodParms.AppendKeyValue("media_content_id", media_content_id)
        _logsi.LogMethodParmList(SILevel.Verbose, "'%s': browsing for media - selected node: '%s'" % (playerName, media_content_type), methodParms)
        
        # validations.
        if source is None:
            source = "unknownSource"
            
        # initialize child item attributes.
        title:str = None
        image:str = None
        media:object = None
        items:list = []
        
        # build selection list based upon the browsable media type.
        # - media: will contain the result of the soundtouch api call.
        # - items: will contain the child items to display for the media item.
        # - title: the title to display in the media browser.
        # - image: the image (if any) to display in the media browser (can be none).
        if media_content_type == BrowsableMedia.SOUNDTOUCH_PRESETS:
            _logsi.LogVerbose("'%s': querying client device for SoundTouch presets" % playerName)
            media:PresetList = data.client.GetPresetList(refresh=True, resolveSourceTitles=True)
            items = media.Presets

        elif media_content_type == BrowsableMedia.SOUNDTOUCH_RECENTLY_PLAYED:
            _logsi.LogVerbose("'%s': querying client device for SoundTouch recently played items" % playerName)
            media:RecentList = data.client.GetRecentList(True, resolveSourceTitles=True)
            items = media.Recents
            
        elif media_content_type == BrowsableMedia.PANDORA_STATIONS:
            _logsi.LogVerbose("'%s': querying client device for Pandora stations" % playerName)
            sourceItems:SourceList = data.client.GetSourceList(refresh=False)
            sourceItem:SourceItem
            for sourceItem in sourceItems:
                if sourceItem.Source == SoundTouchSources.PANDORA.value:
                    criteria:Navigate = Navigate(sourceItem.Source, sourceItem.SourceAccount)
                    media:NavigateResponse = data.client.GetMusicServiceStations(criteria)
                    items = media.Items
                    break
            if media is None:
                raise MediaSourceNotFoundError("'%s': could not find SoundTouch Source for '%s' content" % (playerName, media_content_type))
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_PLAYLISTS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetPlaylistFavorites(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_FOLLOWED_ARTISTS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetArtistsFollowed(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_SAVED_ALBUMS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetAlbumFavorites(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_SAVED_TRACKS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetTrackFavorites(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_SAVED_SHOWS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetShowFavorites(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_RECENTLY_PLAYED:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetPlayerRecentTracks(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_TOP_ARTISTS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetUsersTopArtists(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_USER_TOP_TRACKS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetUsersTopTracks(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_FEATURED_PLAYLISTS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetFeaturedPlaylists(hass, data, playerName, media_content_type, media_content_id)

        elif media_content_type == BrowsableMedia.SPOTIFY_NEW_RELEASES:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetAlbumNewReleases(hass, data, playerName, media_content_type, media_content_id)
            
        elif media_content_type == BrowsableMedia.SPOTIFY_CATEGORYS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetBrowseCategorysList(hass, data, playerName, media_content_type, media_content_id)

        elif media_content_type == BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            
            # was a base64 encoded category object supplied?  if not, then it's a problem! 
            if not media_content_id.startswith(CATEGORY_BASE64):
                raise ValueError("'%s': media content type '%s' is not a serialized Category object!" % (playerName, media_content_type))

            # drop the eye-catcher and deserialize the category object.
            category:Category = Category()
            media_content_id = media_content_id[len(CATEGORY_BASE64):]
            category = deserialize_object(media_content_id)
            _logsi.LogObject(SILevel.Verbose, "'%s': deserialized %s" % (playerName, category.ToString()), category, excludeNonPublic=True)
            media_content_id = category.Uri   # Spotify URI that contains the category id.

            # get the playlists for the category id.
            media, items = _SpotifyPlusGetCategoryPlaylists(hass, data, playerName, media_content_type, media_content_id)
            title = category.Name
            image = category.ImageUrl
                                       
        elif media_content_type == BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS_MADEFORYOU:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media_content_id = 'spotify:category:0JQ5DAt0tbjZptfcdMSKl3'   # special hidden category "Made For You"
            media, items = _SpotifyPlusGetCategoryPlaylists(hass, data, playerName, media_content_type, media_content_id)

        # elif media_content_type == BrowsableMedia.SPOTIFY_USER_DAILY_MIXES:
        #     _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
        #     media, items = _SpotifyPlusSearchPlaylists(hass, data, playerName, media_content_type, media_content_id, data.OptionSpotifyMediaPlayerEntityId, "Daily Mix", 200, True)
            
        elif media_content_type == MediaType.ALBUM:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetAlbum(hass, data, playerName, media_content_type, media_content_id)
            title = media.Name
            image = media.ImageUrl
            
        elif media_content_type == MediaType.ARTIST:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            artist:Artist = _SpotifyPlusGetArtist(hass, data, playerName, media_content_type, media_content_id)  # for cover image
            media, items = _SpotifyPlusGetArtistAlbums(hass, data, playerName, media_content_type, media_content_id)
            title = artist.Name
            image = artist.ImageUrl
            
        elif media_content_type == MediaType.PLAYLIST:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetPlaylist(hass, data, playerName, media_content_type, media_content_id)
            title = media.Name
            image = media.ImageUrl
            
        elif media_content_type == MediaType.PODCAST or media_content_type == MEDIA_TYPE_SHOW:
            _logsi.LogVerbose(STAppMessages.MSG_SPOTIFYPLUS_SERVICE_EXECUTE % (playerName, DOMAIN_SPOTIFYPLUS, media_content_type))
            media, items = _SpotifyPlusGetShow(hass, data, playerName, media_content_type, media_content_id)
            title = media.Name
            image = media.ImageUrl
            
        else:
            raise ValueError("'%s': unrecognized media content type '%s' in browse media node" % (playerName, media_content_type))

        # if media was not set then we are done.
        if media is None:
            raise ValueError("'%s': could not find media items for content type '%s'" % (playerName, media_content_type))

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
                #_logsi.LogVerbose("'%s': could not find logo image path '%s'; image will be reset to null" % (playerName, imagePath))
                image = None

        # get parent media atttributes based upon selected media content type.
        parentAttrs:dict[str, Any] = libraryMap.get(media_content_type, None)
        _logsi.LogDictionary(SILevel.Verbose, "'%s': BrowseMedia attributes for parent media content type: '%s'" % (playerName, media_content_type), parentAttrs)
        
        # get parent attributes that are not set.
        if title is None:
            title = parentAttrs.get("title_node", media_content_id)

        # create the index.
        browseMedia:BrowseMedia = BrowseMedia(
            can_expand=canExpand,
            can_play=canPlay,
            children=[],
            children_media_class=parentAttrs["children"],
            media_class=parentAttrs["parent"],
            media_content_id=media_content_id,
            media_content_type=media_content_type,
            thumbnail=image,
            title=title,
            )

        # add child items to the index.
        for item in items:

            # resolve media content type.
            mediaType:str = parentAttrs["children"]

            # get child media atttributes based upon child item media content type.
            childAttrs:dict[str, Any] = libraryMap.get(mediaType, None)
            #_logsi.LogDictionary(SILevel.Verbose, "'%s': BrowseMedia attributes for child media content type: '%s'" % (playerName, mediaType), childAttrs)

            # set child flag indicating if media can be played or not.
            canPlay:bool = mediaType in PLAYABLE_MEDIA_TYPES
        
            # track and episode media items cannot be expanded (only played);
            # other media types can be expanded to display child items (e.g. Album, Artist, Playlist, etc).
            canExpand = mediaType not in [
                MediaType.TRACK,
                MediaType.EPISODE,
            ]

            # resolve media content id and image to use.
            # Default the value to the media type.
            image:str = None
            mediaId:str = mediaType
            if canPlay:
                
                # if it is playable then serialize the ContentItem and use it instead - we pass the
                # ContentItem to the play_media function so the SoundTouch knows how to play the content.
                mediaId = "%s%s" % (CONTENT_ITEM_BASE64, serialize_object(item.ContentItem))
                image = item.ContentItem.ContainerArt
                
            elif mediaType == MediaType.GENRE:
                
                # if it's GENRE content, then serialize the Category object and use it instead so that
                # we don't have to go get it again - we will deserialize it when the child node is
                # selected, and use it to resolve the category Id, Name, and imageUrl values.
                mediaId = "%s%s" % (CATEGORY_BASE64, serialize_object(item))
                mediaType = BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS.value
                image = item.ImageUrl  # category image.
                
            else:
                
                image = item.ContentItem.ContainerArt
            
            # build the chile node.
            browseMediaChild:BrowseMedia = BrowseMedia(
                can_expand=canExpand,
                can_play=canPlay,
                children=None,
                children_media_class=childAttrs["children"],
                media_class=childAttrs["parent"],
                media_content_id=mediaId,
                media_content_type=mediaType,
                thumbnail=image,
                title=item.Name,
                )
            browseMedia.children.append(browseMediaChild)
            _logsi.LogObject(SILevel.Verbose, "'%s': BrowseMedia Child Object: Type='%s', Id='%s', Title='%s'" % (playerName, browseMediaChild.media_content_type, browseMediaChild.media_content_id, browseMediaChild.title), browseMediaChild)

        # trace.
        _logsi.LogObject(SILevel.Verbose, "'%s': BrowseMedia Parent Object: Type='%s', Id='%s', Title='%s'" % (playerName, browseMedia.media_content_type, browseMedia.media_content_id, browseMedia.title), browseMedia)

        return browseMedia

    except Exception as ex:
            
        # trace.
        _logsi.LogException("'%s': BrowseMedia browse_media_node exception: %s" % (playerName, str(ex)), ex, logToSystemLogger=False)
        raise HomeAssistantError(str(ex)) from ex
        
    finally:

        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


def _GetSpotifySourceItem(playerName:str, 
                          data:InstanceDataSoundTouchPlus,
                          userProfile:UserProfile
                          ) -> SourceItem:
    """
    Returns the Spotify sourceitem from the SoundTouch device source list.
    """
    sourceItem:SourceItem = None
    
    # get the soundtouch source list (from cache).
    sourceItems:SourceList = data.client.GetSourceList(refresh=False)
    
    # get the Spotify source user account item.
    for sourceItem in sourceItems:
        if sourceItem.Source == SoundTouchSources.SPOTIFY.value:
            if sourceItem.SourceAccount != "SpotifyConnectUserName" and sourceItem.SourceAccount != "SpotifyAlexaUserName":
                break
            
    # log a warning message if there is a mismatch between the soundtouch source userid
    # and the spotifyPlus integration userid that obtained the results.
    if sourceItem.SourceAccount != userProfile.Id:
        _logsi.LogVerbose("'%s': SpotifyPlus integration userid ('%s') did not match the SoundTouch Spotify SourceAccount value ('%s') - content may not be playable if it is private" % (playerName, userProfile.Id, sourceItem.SourceAccount))
            
    # return source item to caller.
    return sourceItem


def _SpotifyPlusGetAlbum(hass:HomeAssistant,
                         data:InstanceDataSoundTouchPlus,
                         playerName:str,
                         media_content_type:str|None,
                         media_content_id:str|None,
                         ) -> Tuple[Album, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_album", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `Album` object that contains album information.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_album',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "album_id": SpotifyClient.GetIdFromUri(media_content_id),
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:Album = Album(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Track] = media.Tracks.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Album
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetAlbumFavorites(hass:HomeAssistant,
                                  data:InstanceDataSoundTouchPlus,
                                  playerName:str,
                                  media_content_type:str|None,
                                  media_content_id:str|None,
                                  ) -> Tuple[PlaylistPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_album_favorites", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `AlbumPageSaved` object that contains the results.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_album_favorites',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT,
                "offset": 0
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:AlbumPageSaved = AlbumPageSaved(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Album] = media.GetAlbums()
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Album
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetAlbumNewReleases(hass:HomeAssistant,
                                    data:InstanceDataSoundTouchPlus,
                                    playerName:str,
                                    media_content_type:str|None,
                                    media_content_id:str|None,
                                    ) -> Tuple[AlbumPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_album_new_releases", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `AlbumPageSimplified` object that contains the results.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_album_new_releases',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT,
                "offset": 0,
                "limit_total": SPOTIFY_BROWSE_LIMIT_TOTAL,
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:AlbumPageSimplified = AlbumPageSimplified(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[AlbumSimplified] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Album
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetArtist(hass:HomeAssistant,
                          data:InstanceDataSoundTouchPlus,
                          playerName:str,
                          media_content_type:str|None,
                          media_content_id:str|None,
                          ) -> Artist:
    """
    Calls the spotifyPlus integration service "get_artist", and returns the media result.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        An `Artist` object that contains artist information.  
    """
    
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_artist',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "artist_id": SpotifyClient.GetIdFromUri(media_content_id),
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:Artist = Artist(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, media)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    return media


def _SpotifyPlusGetArtistAlbums(hass:HomeAssistant,
                                data:InstanceDataSoundTouchPlus,
                                playerName:str,
                                media_content_type:str|None,
                                media_content_id:str|None,
                                ) -> Tuple[ArtistPage, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_artist_albums", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `ArtistPage` object that contains artists followed information.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_artist_albums',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "artist_id": SpotifyClient.GetIdFromUri(media_content_id),
                "include_groups": "album",
                "limit": SPOTIFY_BROWSE_LIMIT
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:ArtistPage = ArtistPage(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Artist] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Artist
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetArtistsFollowed(hass:HomeAssistant,
                                   data:InstanceDataSoundTouchPlus,
                                   playerName:str,
                                   media_content_type:str|None,
                                   media_content_id:str|None,
                                   ) -> Tuple[ArtistPage, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_artists_followed", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `ArtistPage` object that contains artists followed information.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_artists_followed',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:ArtistPage = ArtistPage(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Artist] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Artist
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetBrowseCategorysList(hass:HomeAssistant,
                                       data:InstanceDataSoundTouchPlus,
                                       playerName:str,
                                       media_content_type:str|None,
                                       media_content_id:str|None,
                                       ) -> Tuple[CategoryPage, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_browse_categorys", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `CategoryPage` object that contains artists followed information.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_browse_categorys_list',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "refresh": False
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:CategoryPage = CategoryPage(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Category] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # add a "Uri" attribute to each category in the category list.
    # this is so we can process categories just like other index types, as
    # spotify categories are simply playlists of tracks.
    category:Category
    for category in mediaItems:
        if hasattr(category, "Uri"):
            _logsi.LogVerbose("Category Uri's have already been set in the cache; don't need to do it again")
            break
        setattr(category, "Uri", f"spotify:category:{category.Id}")

    # set items list to the media list for child node processing.
    items:list[Category] = mediaItems
    return media, items


def _SpotifyPlusGetCategoryPlaylists(hass:HomeAssistant,
                                     data:InstanceDataSoundTouchPlus,
                                     playerName:str,
                                     media_content_type:str|None,
                                     media_content_id:str|None,
                                     ) -> Tuple[PlaylistPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_category_playlists", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `PlaylistPageSimplified` object that contains artists followed information.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # get category id value.
    categoryId:str = SpotifyClient.GetIdFromUri(media_content_id)

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_category_playlists',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "category_id": categoryId,
                "limit_total": SPOTIFY_BROWSE_LIMIT_TOTAL
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:PlaylistPageSimplified = PlaylistPageSimplified(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[PlaylistSimplified] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Artist
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetFeaturedPlaylists(hass:HomeAssistant,
                                     data:InstanceDataSoundTouchPlus,
                                     playerName:str,
                                     media_content_type:str|None,
                                     media_content_id:str|None,
                                     ) -> Tuple[PlaylistPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_featured_playlists", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `PlaylistPageSimplified` object that contains artists followed information.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_featured_playlists',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT,
                "offset": 0,
                "limit_total": SPOTIFY_BROWSE_LIMIT_TOTAL
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:PlaylistPageSimplified = PlaylistPageSimplified(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[PlaylistSimplified] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Artist
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetPlayerRecentTracks(hass:HomeAssistant,
                                      data:InstanceDataSoundTouchPlus,
                                      playerName:str,
                                      media_content_type:str|None,
                                      media_content_id:str|None,
                                      ) -> Tuple[PlayHistoryPage, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_player_recent_tracks", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `PlayHistoryPage` object that contains the results.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_player_recent_tracks',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT,
                "after": 0          # get last 50 regardless of timeframe
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
               
    # convert results dictionary to managed code instances.
    media:PlayHistoryPage = PlayHistoryPage(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Track] = media.GetTracks()
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Track
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetPlaylist(hass:HomeAssistant,
                            data:InstanceDataSoundTouchPlus,
                            playerName:str,
                            media_content_type:str|None,
                            media_content_id:str|None,
                            ) -> Tuple[Playlist, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_playlist", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `PlaylistPageSimplified` object that contains the results.    
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_playlist',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "playlist_id": SpotifyClient.GetIdFromUri(media_content_id),
                "fields": "description,id,images,name,public,snapshot_id,type,uri,tracks(limit,next,offset,previous,total,items(track(id,name,track_number,type,uri,album(id,images,name,total_tracks,type,uri,artists(id,name,type,uri)))))",
                "additional_types": "episode"
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:Playlist = Playlist(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Track] = media.GetTracks()
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Playlist
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetPlaylistFavorites(hass:HomeAssistant,
                                     data:InstanceDataSoundTouchPlus,
                                     playerName:str,
                                     media_content_type:str|None,
                                     media_content_id:str|None,
                                     ) -> Tuple[PlaylistPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_playlist_favorites", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `PlaylistPageSimplified` object that contains the results.    
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_playlist_favorites',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT,
                "offset": 0
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:PlaylistPageSimplified = PlaylistPageSimplified(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[PlaylistSimplified] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtained the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:PlaylistSimplified
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetShow(hass:HomeAssistant,
                        data:InstanceDataSoundTouchPlus,
                        playerName:str,
                        media_content_type:str|None,
                        media_content_id:str|None,
                        ) -> Tuple[Show, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_show", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `Show` object that contains album information.  
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    
    # was a content item in base64 encoded format supplied?  
    # this can happen for meia content that could be played as well as expanded (e..g playlist, album, etc).
    if media_content_id.startswith(CONTENT_ITEM_BASE64):

        # drop the eye-ctacher prefix before we deserialize.
        media_content_id = media_content_id[len(CONTENT_ITEM_BASE64):]
        contentItem:ContentItem = deserialize_object(media_content_id)
        _logsi.LogObject(SILevel.Verbose, "'%s': ContentItem is deserialized %s" % (playerName, contentItem.ToString()), contentItem)
        media_content_id = contentItem.Location   # Spotify URI

    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_show',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "show_id": SpotifyClient.GetIdFromUri(media_content_id),
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:Show = Show(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[EpisodeSimplified] = media.Episodes.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Album
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetShowFavorites(hass:HomeAssistant,
                                 data:InstanceDataSoundTouchPlus,
                                 playerName:str,
                                 media_content_type:str|None,
                                 media_content_id:str|None,
                                 ) -> Tuple[PlaylistPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_show_favorites", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `ShowPageSaved` object that contains the results.    
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_show_favorites',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT,
                "offset": 0
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:ShowPageSaved = ShowPageSaved(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[ShowSaved] = media.GetShows()
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:ShowSaved
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetTrackFavorites(hass:HomeAssistant,
                                  data:InstanceDataSoundTouchPlus,
                                  playerName:str,
                                  media_content_type:str|None,
                                  media_content_id:str|None,
                                  ) -> Tuple[PlaylistPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_track_favorites", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `TrackPageSaved` object that contains the results.    
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_track_favorites',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit": SPOTIFY_BROWSE_LIMIT,
                "offset": 0
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:TrackPageSaved = TrackPageSaved(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Track] = media.GetTracks()
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Track
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetUsersTopArtists(hass:HomeAssistant,
                                   data:InstanceDataSoundTouchPlus,
                                   playerName:str,
                                   media_content_type:str|None,
                                   media_content_id:str|None,
                                   ) -> Tuple[ArtistPage, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_users_top_artists", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `ArtistPage` object that contains the results.    
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_users_top_artists',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit_total": SPOTIFY_BROWSE_LIMIT_TOTAL,
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:ArtistPage = ArtistPage(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Artist] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Track
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusGetUsersTopTracks(hass:HomeAssistant,
                                  data:InstanceDataSoundTouchPlus,
                                  playerName:str,
                                  media_content_type:str|None,
                                  media_content_id:str|None,
                                  ) -> Tuple[TrackPage, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "get_users_top_tracks", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.

    Returns:
        A tuple of 2 objects:  
        - `TrackPage` object that contains the results.    
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'get_users_top_tracks',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "limit_total": SPOTIFY_BROWSE_LIMIT_TOTAL,
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:TrackPage = TrackPage(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[Track] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:Track
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items


def _SpotifyPlusSearchPlaylists(hass:HomeAssistant,
                                data:InstanceDataSoundTouchPlus,
                                playerName:str,
                                media_content_type:str|None,
                                media_content_id:str|None,
                                criteria:str,
                                limitTotal:int,
                                ) -> Tuple[PlaylistPageSimplified, list[NavigateItem]]:
    """
    Calls the spotifyPlus integration service "search_playlist", and returns the media and items results.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        data (InstanceDataSoundTouchPlus):
            Component instance data that contains the SoundTouchClient instance.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.
        criteria (str):
            Criteria to search for.
        limitTotal (int):
            The maximum number of items to return for the request.  
            If specified, this argument overrides the limit and offset argument values
            and paging is automatically used to retrieve all available items up to the
            maximum number specified.  
            Default: None (disabled)

    Returns:
        A tuple of 2 objects:  
        - `PlaylistPageSimplified` object that contains the results.    
        - list[NavigateItem] list of items that will be loaded to child nodes.   
    """
    # call SpotifyPlus integration service.
    # this returns a dictionary of a partial user profile, as well as the items retrieved.
    result:dict = run_coroutine_threadsafe(
        hass.services.async_call(
            DOMAIN_SPOTIFYPLUS,
            'search_playlists',
            {
                "entity_id": data.OptionSpotifyMediaPlayerEntityId,
                "criteria": criteria,
                "offset": 0,
                "limit_total": limitTotal
            },      
            blocking=True,          # wait for service to complete before returning
            return_response=True    # returns service response data.
        ), hass.loop
    ).result()
    _logsi.LogDictionary(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_DICTIONARY % playerName, result, prettyPrint=True)
            
    # convert results dictionary to managed code instances.
    media:PlaylistPageSimplified = PlaylistPageSimplified(root=result.get("result", None))
    if media is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS_FORMAT_ERROR % (playerName, media_content_type))
    mediaItems:list[PlaylistSimplified] = media.Items
    _logsi.LogArray(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_RESULT_ITEMS % playerName, mediaItems)

    userProfile:UserProfile = UserProfile(root=result.get("user_profile", None))
    if userProfile is None:
        raise MediaSourceNotFoundError(STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE_FORMAT_ERROR % (playerName, media_content_type))
    _logsi.LogObject(SILevel.Verbose, STAppMessages.MSG_SPOTIFYPLUS_USERPROFILE % playerName, userProfile, excludeNonPublic=True)

    result = None

    # verify that the soundtouch Spotify source userid matches the spotifyPlus integration
    # userid that obtatined the results.  if they don't match, then it's a problem because
    # the soundtouch device won't be able to play it!
    spotifySourceItem:SourceItem = _GetSpotifySourceItem(playerName, data, userProfile)

    # build a list of soundtouchapi NavigateItems (which also contain ContentItem) to 
    # use in the child load process.
    items:list[NavigateItem] = []
    item:PlaylistSimplified
    for item in mediaItems:
        ci:ContentItem = ContentItem(spotifySourceItem.Source, "uri", item.Uri, spotifySourceItem.SourceAccount, True, name=item.Name, containerArt=item.ImageUrl)
        navItem:NavigateItem = NavigateItem(ci.Source, ci.SourceAccount, ci.Name, ci.TypeValue, contentItem=ci)
        items.append(navItem)

    return media, items



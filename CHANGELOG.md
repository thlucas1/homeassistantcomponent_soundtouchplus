## Change Log

All notable changes to this project are listed here.  

Change are listed in reverse chronological order (newest to oldest).  

<span class="changelog">

###### [ 1.0.89 ] - 2025/01/23

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.156.
  * Updated underlying `smartinspectPython` package requirement to version 3.0.34.

###### [ 1.0.88 ] - 2025/01/07

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.139.

###### [ 1.0.87 ] - 2025/01/06

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.138.

###### [ 1.0.86 ] - 2025/01/05

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.137.

###### [ 1.0.85 ] - 2025/01/05

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.135.

###### [ 1.0.84 ] - 2025/01/04

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.134.

###### [ 1.0.83 ] - 2025/01/03

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.133.

###### [ 1.0.82 ] - 2025/01/02

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.132.

###### [ 1.0.81 ] - 2025/01/01

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.131.

###### [ 1.0.80 ] - 2024/12/27

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.130.

###### [ 1.0.79 ] - 2024/12/21

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.129.

###### [ 1.0.78 ] - 2024/12/20

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.128.

###### [ 1.0.77 ] - 2024/12/20

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.127.

###### [ 1.0.76 ] - 2024/12/18

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.126.

###### [ 1.0.75 ] - 2024/12/09

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.125.

###### [ 1.0.74 ] - 2024/12/06

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.123.

###### [ 1.0.73 ] - 2024/12/02

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.122.
  * The above `spotifywebapiPython` package will now return an exception due to the functions being deprecated by the Spotify development team.  More information can be found on the [Spotify Developer Forum Blog post](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api) that was conveyed on November 27, 2024.  The following methods will now raise a `SpotifyApiError` exception due to the Spotify development team changes: `GetArtistRelatedArtists`, `GetTrackRecommendations`, `GetTrackAudioFeatures`, `GetFeaturedPlaylists`, `GetCategoryPlaylists`, `GetGenres`.  The following properties were also marked as deprecated for the same reason: `TrackSimplified.PreviewUrl`.
  * Due to the above chnages made by Spotify, any Algorithmic and Spotify-owned editorial playlists are no longer accessible or have more limited functionality.  This means that you can no longer obtain details via the `SpotifyClient.GetPlaylist` and `SpotifyClient.GetPlaylistItems` methods for Spotify-owned / generated content (e.g. "Made For You", etc).  A `404 - Not Found` error will be returned when trying to retrieve information for these playlist types.

###### [ 1.0.72 ] - 2024/11/20

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.121.

###### [ 1.0.71 ] - 2024/11/15

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.119.

###### [ 1.0.70 ] - 2024/11/03

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.114.

###### [ 1.0.69 ] - 2024/10/31

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.113.

###### [ 1.0.68 ] - 2024/10/22

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.112.

###### [ 1.0.67 ] - 2024/10/04

  * Updated service description strings to correct HASSFest validation errors on GitHub.
  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.106.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.68.

###### [ 1.0.66 ] - 2024/09/28

  * Updated `system_health` module to read the contents of the manifest file outside of the event loop.  This was causing `Detected blocking call to open with args ...` exceptions in the system log when gathering integration health details.
  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.101.

###### [ 1.0.65 ] - 2024/09/25

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.99.

###### [ 1.0.64 ] - 2024/09/20

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.97.

###### [ 1.0.63 ] - 2024/09/19

  * Added extra state variable: `stp_nowplaying_image_url`.  Returns the url of the nowplaying image if one is present; otherwise, None.
  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.96.

###### [ 1.0.62 ] - 2024/09/16

  * Added extra state variable: `stp_nowplaying_image_url`.  Returns the url of the nowplaying image if one is present; otherwise, None.
  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.95.

###### [ 1.0.61 ] - 2024/08/21

  * Updated `media_player.sound_mode` property to hold the same value as the `soundtouchplus_sound_mode` attribute.

###### [ 1.0.60 ] - 2024/08/20

  * Updated `_OnSoundTouchUpdateEvent_audiodspcontrols` event processing to method.  The Bose AudioDspControls update event does not contain the supported audio modes in some circumstances. This is causing the SupportedAudioModes property to be set to None, which in turn causes exceptions in the `select_sound_mode` service.  I did not catch this in my testing, as it appears to only happen when the update event occurs which is driven by a change from the device (e.g. by clicking the dialog mode button on the remote).
  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.88.

###### [ 1.0.59 ] - 2024/08/19

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.86.

###### [ 1.0.58 ] - 2024/08/18

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.84.

###### [ 1.0.57 ] - 2024/08/16

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.83.

###### [ 1.0.56 ] - 2024/07/18

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.76.

###### [ 1.0.55 ] - 2024/07/02

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.73.

###### [ 1.0.54 ] - 2024/06/27

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.71.

###### [ 1.0.53 ] - 2024/06/24

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.64.

###### [ 1.0.52 ] - 2024/06/21

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.62.

###### [ 1.0.51 ] - 2024/06/21

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.61.

###### [ 1.0.50 ] - 2024/06/19

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.59.

###### [ 1.0.49 ] - 2024/06/10

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.48.

###### [ 1.0.48 ] - 2024/06/08

  * Fixed a bug that was causing `ValueError: list.remove(x): x not in list` exceptions to be raised whenever the user changed configuration options for a device.  This started appearing with the HA 2024.6.1 release.

###### [ 1.0.47 ] - 2024/06/07

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.46.
  * Added the following requirements to manifest.json so that any dependency `ResolutionImpossible` errors can be quickly identified: 'oauthlib>=3.2.2', 'platformdirs>=4.1.0', 'requests>=2.31.0', 'requests_oauthlib>=1.3.1', 'zeroconf>=0.132.2'.  This bug bit me in the HA 2024.6.1 release when the HA devs upgraded the `requests` dependency to 2.32.3!  The System log was showing that the `spotifywebapiPython` library was the invalid dependency, but it was not - the REAL culprit was the `requests` dependency!

###### [ 1.0.46 ] - 2024/06/07

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.44.

###### [ 1.0.45 ] - 2024/06/06

  * Changed logic to access file system files via a `hass.async_add_executor_job` call.  This fixes the issue of `Detected blocking call to open inside the event loop by custom integration 'X' ...` that was introduced with HA 2024.6 release.

###### [ 1.0.44 ] - 2024/05/21

  * Added extra state variable: `soundtouchplus_websockets_enabled`.  Returns true if websocket support is enabled for the device; otherwise, false if device does not support websockets or if websockets were disabled during device setup.
  * Added extra state variable: `soundtouchplus_polling_enabled`.  Returns true if device polling is enabled; otherwise, false.  Polling can be a temporary condition, in that it will be enabled if websocket support is enabled and the connection is lost and has not been re-established yet.

###### [ 1.0.43 ] - 2024/05/20

  * Added extra state variables related to recently played cache feature: `soundtouchplus_recents_cache_enabled`, `soundtouchplus_recents_cache_max_items`, `soundtouchplus_recents_cache_lastupdated`.
  * Added service `recent_list_cache` to retrieve the recently played items cache from the file system.
  * Added service `remove_preset` to remove the specified preset id.
  * Changed all `media_player.schedule_update_ha_state(force_refresh=True)` calls to `schedule_update_ha_state(force_refresh=False)` to improve performance.  Suggested by @bdraco, along with an explanation of why.  Thanks @bdraco!
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.66.

###### [ 1.0.42 ] - 2024/05/03

  * Changed all `media_player.async_write_ha_state()` calls to `schedule_update_ha_state(force_refresh=True)` calls due to HA 2024.5 release requirements.  This fixes the issue of "Failed to call service X. Detected that custom integration 'Y' calls async_write_ha_state from a thread at Z. Please report it to the author of the 'Y' custom integration.".
  * Added service `get_source_list` to get the current source list configuration of the device.
  * Modified `media_player.service_preset_list` service to update the extra state attribute named `soundtouchplus_presets_lastupdated` to correctly reflect the last update datetime.
  * Modified `media_player.service_recent_list` service to update the extra state attribute named `soundtouchplus_recents_lastupdated` to correctly reflect the last update datetime.
  * Added system health information.
  * Modified strings.json (and translations) to remove a placeholder inside single quotes that was embedded in a service description.  This was causing hass validation step to fail.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.59.
  * Updated Python version from 3.11 to 3.12.3 due to HA 2024.5 release requirements.

###### [ 1.0.41 ] - 2024/04/21

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.43.

###### [ 1.0.40 ] - 2024/04/15

  * Corrected a bug in the underlying `bosesoundtouchapi` that was returning an incorrect image url for currently playing media.  This incorrect value was being used by the `media_player.media_image_url` value, which caused an incorrect image to be displayed for currently playing media in the media player UI.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.58.

###### [ 1.0.39 ] - 2024/04/05

  * Updated Media Browser logic to return an empty `BrowseMedia` object when ignoring Sonos-Card 'favorites' node requests, as a null object was causing numerous `Browse Media should use new BrowseMedia class` log warnings.
  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.42.

###### [ 1.0.38 ] - 2024/04/04

  * Updated Media Browser logic to ignore Sonos-Card 'favorites' node requests, as there is no SoundTouch direct equivalent.
  * Updated `media_player.media_title` attribute to just return the track name (not the `artist - track name`).
  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.41.

###### [ 1.0.37 ] - 2024/03/27

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.40.

###### [ 1.0.36 ] - 2024/03/22

  * Updated `media_player.state` property to return the correct power state when the device has been placed into STANDBY.  This corrects a bug that was introduced in v1.0.28, which set the state to STANDBY instead of OFF.
  * Updated `media_player.media_image_url` to return the content item coverart if present; otherwise, return the nowplaying arturl value.
  * Added new extra state attribute named `soundtouchplus_nowplaying_isadvertisement` - True if the current source is playing an advertisement; otherwise, False.  Note that not all sources support advertisement detection.
  * Added new extra state attribute named `soundtouchplus_nowplaying_isfavorite` - True if the current source content has been marked as a favorite; otherwise, False.  Note that not all sources support favorites.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.57.

###### [ 1.0.35 ] - 2024/03/20

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.37.

###### [ 1.0.34 ] - 2024/03/19

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.36.

###### [ 1.0.33 ] - 2024/03/12

  * Updated TTS force Google Translate support to use a volume level of zero, which causes the announcement to be played at the current volume level of the SoundTouch device.  Prior to the fix, the volume level was set at 30.

###### [ 1.0.32 ] - 2024/03/11

  * Added TTS force Google Translate support, which will force all TTS play media announcement requests to use Google Translate instead of the called service.  This functionality was provided because the SoundTouch device could not play the MP3 file generated by some TTS services due to bitrate limitations.  These includes `tts.speak`, `tts.cloud_say`, etc.

###### [ 1.0.31 ] - 2024/03/05

  * Added service `clear_source_nowplayingstatus` to clear the NowPlayingStatus for a given source.
  * Added service `update_source_nowplayingstatus` to allow updates to the NowPlayingStatus for a given source.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.56.

###### [ 1.0.30 ] - 2024/03/02

  * Updated underlying `spotifywebapiPython` package requirement to version 1.0.33.

###### [ 1.0.29 ] - 2024/02/27

  * Added Spotify music service support.  See the [SoundTouchPlus Wiki](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/Media-Library-Browser) for details on how to customize it.
  * Updated `browse_media.py` to add options for SpotifyPlus integration support.  Also reorganized the library map structure to easily support more music services in the future.

###### [ 1.0.28 ] - 2024/02/14

  * Updated `media_player.py` to properly restart websocket event listener when connectivity to a device is lost.  Prior to this fix, HA would need to be restarted in order to receive status notifications after a device lost connectivity.  It will now gracefully reconnect to the device within 30 seconds.
  * Updated `__init__.py` with proper support for options update processing.
  * Updated all modules with better tracing support.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.55.

###### [ 1.0.27 ] - 2024/02/14

  * Added browse media support that allows the user to play Pandora Stations, SoundTouch Presets, and SoundTouch Recently played items from the media browser.  See the [SoundTouchPlus Wiki](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/Media-Library-Browser) for details on how to customize it.
  * Added Spotify URI support to the stock `play_media` service.
  * Updated `media_player.py` with better tracing support.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.53.

###### [ 1.0.26 ] - 2023/12/29

  * Added "set_repeat()" support, which allows track play to be repeated (one, all, off).
  * Added "set_shuffle()" support, which allows track play to be shuffled (on, off).
  * Added "media_seek()" support, which allows playing track position to be changed, as well as display duration, position, and estimated time remaining values.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.51.

###### [ 1.0.25 ] - 2023/12/27

  * Added source title resolution to the `preset_list` and `recent_list` services, which includes a ui-friendly source title value for preset and recent list items.
  * Added service "Toggle Zone Member" - Toggles the given zone member in the master device's zone.  If the member exists in the zone then it is removed; if the member does not exist in the zone, then it is added.  A new zone is automatically created if necessary.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.48.  This also increases PoolManager sizes and fixes the "Connection pool is full, discarding connection ..." warning messages.

###### [ 1.0.24 ] - 2023/12/26

  * Added `include_empty_slots` argument to the `preset_list` service - True to include ALL preset slots (both empty and set); otherwise, False (default) to only include preset slots that have been set.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.44.

###### [ 1.0.23 ] - 2023/12/20

  * Added configuration options support - source_select processing, to only show sources that the user wants.
  * Added friendlier sound_mode_list display values for devices that support audiodspcontrols (ST-300, etc).
  * Updated code in __init__.py to log an error message (instead of an exception) when a SoundTouchClient instance could not be created.  This is usually caused by a temporary error (e.g. device unplugged, network connectivity, etc), in which case the user will need to manually reload the device when the temporary condition is cleared.  If it's a permanent error (e.g. ip address change), then the user needs to correct the configuration.
  * Updated underlying `bosesoundtouchapi` package requirement to version 1.0.43.

###### [ 1.0.22 ] - 2023/12/17

  *  Added service "Music Service Station List" - Gets a list of your stored stations from the specified music service (e.g. PANDORA, etc).

###### [ 1.0.21 ] - 2023/12/16

  *  Updated underlying `bosesoundtouchapi` package requirement to version 1.0.35.
  *  Updated configuration caching to utilize the `SoundTouchClient` module cache instead of local variables.  It's doing the same thing, without twice the overhead of memory storage.

###### [ 1.0.20 ] - 2023/12/13

  *  Added service "Reboot Device" - Reboots the operating system of the SoundTouch device.
  *  Updated Remote Keypress service to include key_state argument.  This allows presets to be stored (press) or selected for playing (release).
  *  Updated underlying `bosesoundtouchapi` package requirement to version 1.0.31.

###### [ 1.0.19 ] - 2023/12/04

  *  Updated underlying `bosesoundtouchapi` package requirement to version 1.0.22.
  *  Updated `sourcesUpdated` event processing to refresh the source list when the list has changed.

###### [ 1.0.18 ] - 2023/11/29

  *  Updated service "Play Content Item" to make most parameters optional, to support switching to LOCAL source if necessary.
  *  Updated README.md page to reference documentation in the GitHub Wiki pages.
  *  Changed github validation script to run once per month instead of once per day.

###### [ 1.0.17 ] - 2023/11/27

  *  Added service "Play Content Item" to allow media content from sources (e.g. TUNEIN, LOCAL_MUSIC, etc) to be played directly.

###### [ 1.0.16 ] - 2023/11/26

  *  Corrected high cpu rate condition in the underlying `SmartInspectPython` package api.  This was causing the integration to consume 50%+ of the cpu at all times.

###### [ 1.0.15 ] - 2023/11/20

  *  Updated `media_player.source_list` property to include sourceAccount as well as the source in the returned list (e.g. "PRODUCT:TV", etc).

###### [ 1.0.14 ] - 2023/11/15

  *  Added service "Adjust Audio Tone Levels" to allow bass and treble levels to be adjusted for devices that support AudioProductToneControls capability.
  *  Added new extra state attribute named "soundtouchplus_audio_bass_level" to indicate the current bass level.
  *  Added new extra state attribute named "soundtouchplus_audio_treble_level" to indicate the current treble level.
  *  Updated `select_source` method with the ability to select the last source (LASTSOURCE), as well as the last Soundtouch source (LASTSOUNDTOUCHSOURCE).

###### [ 1.0.13 ] - 2023/11/11

  *  Added "select_sound_mode()" support, which allows the device to enable AUDIO_MODE_DIALOG or AUDIO_MODE_NORMAL.  Note that only certain SoundTouch devices support the audiodspcontrols API (e.g. ST-300 does, ST-10 does not).

###### [ 1.0.12 ] - 2023/11/10

  *  Updated "select_source()" method processing to call the "SelectLocalSource()" method if LOCAL is specified for the source value; for some SoundTouch devices, this is the only way that the LOCAL source can be selected.

###### [ 1.0.11 ] - 2023/11/09

  *  Added a new extra state attribute to media_player named "soundtouchplus_source".  This will return a "source:sourceAccount" value if the sourceAccount value is populated; otherwise, it just returns the "source" value.

###### [ 1.0.10 ] - 2023/11/08

  *  Updated initialization method to load the _attr_source_list state property with the list of sources the device supports.  Also added listener to update the source list when it is changed in real-time.

###### [ 1.0.9 ] - 2023/11/06

  *  Allow user to disable websocket notifications if desired when device is added.  This will enable device polling every 10 seconds from Home Assistant UI for status updates.

###### [ 1.0.8 ] - 2023/11/05

  *  Updated config flow to allow configuration key name changes.  Updates were failing due to a configuration key name change.

###### [ 1.0.7 ] - 2023/11/05

  *  Updated config flow to allow entry for websocket port and ping interval values.

###### [ 1.0.6 ] - 2023/11/02

  *  Updated websocket connection event handler to log a debug message instead of an error when a socket connection is opened or closed.

###### [ 1.0.5 ] - 2023/11/01

  *  Updated code to handle device websocket connection errors (e.g. power loss, socket connection errors, etc).  This was causing devices to not respond once the websocket connection was re-established.

###### [ 1.0.4 ] - 2023/10/31

  *  Updated code to handle devices that do not support websocket notifications.  In this case, HA will poll the device every 10 seconds for status updates.

###### [ 1.0.3 ] - 2023/10/30

  *  Added "play_url" service support that allows better support for playing URL media content.

###### [ 1.0.2 ] - 2023/10/30

  *  Removed some HTML formatting from strings.json to be HASSFest validation compliant.

###### [ 1.0.1 ] - 2023/10/30

  *  Corrected a bug in the underlying bosesoundtouchapi which would cause delays in playing url's with no metadata present.

###### [ 1.0.0 ] - 2023/10/29

  *  Version 1 initial release.

</span>
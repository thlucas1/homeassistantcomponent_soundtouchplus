## Change Log

All notable changes to this project are listed here.  

Change are listed in reverse chronological order (newest to oldest).  

<span class="changelog">

###### [ 1.0.20 ] - 2023/12/13

  *  Added service "Reboot Device" - Reboots the operating system of the SoundTouch device.
  *  Updated Remote Keypress service to include key_state argument.  This allows presets to be stored (press) or selected for playing (release).
  *  Updated underlying `bosesoundtouchapi` package requirement to version 1.0.30.

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
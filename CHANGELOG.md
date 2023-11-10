## Change Log

All notable changes to this project are listed here.  

Change are listed in reverse chronological order (newest to oldest).  

<span class="changelog">

###### [ 1.0.12 ] - 2023/11/10

  *  Updated "select_source()" metthod processing to call the "SelectLocalSource()" method if LOCAL is specified for the source value; for some SoundTouch devices, this is the only way that the LOCAL source can be selected.

###### [ 1.0.11 ] - 2023/11/09

  *  Added a new extra state attribut to media_player named "soundtouchplus_source".  This will return a "source:sourceAccount" value if the sourceAccount value is populated; otherwise, it just returns the "source" value.

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
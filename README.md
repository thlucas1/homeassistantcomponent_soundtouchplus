# Bose SoundTouchPlus

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

_Home Assistant Integration to integrate with [soundtouchplus][soundtouchplus]._

**This integration will set up the following platforms.**

Platform | Description
-- | --
`media_player` | Media Player Entity.

## Features

The following Home Assistant media_player Platform services are supplied by this integration.
- BROWSE_MEDIA
- GROUPING
- NEXT_TRACK
- PAUSE
- PLAY
- PLAY_MEDIA **
- PREVIOUS_TRACK
- REPEAT_SET
- SELECT_SOURCE **
- SHUFFLE_SET
- STOP
- TURN_OFF
- TURN_ON
- VOLUME_MUTE
- VOLUME_SET
- VOLUME_STEP

The SELECT_SOURCE supports selecting a Source as well as a SourceAccount value.  This is required functionality for specific Bose SoundTouch devices that require it (e.g. ST300).
For example, to watch TV using the ST300 you must select source="PRODUCT" and sourceAccount="TV".  Your service call would look like this:

[code]
service: media_player.select_source
data:
  source: PRODUCT:TV
target:
  entity_id: media_player.soundtouch_10
[/code]

PLAY_MEDIA also supports playing of both HTTP and HTTPS url's.  If the URL contains ID3 metadata tags, then the Album, Artist, and Song Title are automatically extracted and appear in the NowPlaying status.  Your service call would look like this:

[code]
service: media_player.play_media
data:
  media_content_type: music
  media_content_id: >-
    https://freetestdata.com/wp-content/uploads/2021/09/Free_Test_Data_1MB_MP3.mp3
target:
  entity_id: media_player.soundtouch_10
[/code]

[code]
service: media_player.play_media
data:
  media_content_type: music
  media_content_id: >-
    http://www.hyperion-records.co.uk/audiotest/14%20Clementi%20Piano%20Sonata%20in%20D%20major,%20Op%2025%20No%206%20-%20Movement%202%20Un%20poco%20andante.MP3
target:
  entity_id: media_player.soundtouch_10
[/code]

The following custom services are also supplied by this integration.
- Play Handoff: Handoff playing source from one SoundTouch device to another.
- Play TTS Message: Play Text-To-Speech notification on a SoundTouch device.  Note that this is limited to ST10,20,30 devices, as Bose ST300 does not support notifications (AFAIK).
- Get Preset List: Retrieves the list of presets defined to the device.
- Get Recent List: Retrieves the list of recently played items defined to the device.
- Remote Keypress: Simulates the press and release of a key on the SoundTouch device remote control.
- Snapshot Restore: Restore SoundTouch device settings from a snapshot.
- Snapshot Store: Store SoundTouch device settings to a snapshot.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `soundtouchplus`.
1. Download _all_ the files from the `custom_components/soundtouchplus/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Bose SoundTouchPlus"

## Configuration is done in the UI

<!---->

## Extended Logging Support using SmartInspect

The SmartInspectPython package (installed with this integration) can be used to easily debug the integration.
Note that the standard Home Assistant logger is also supported, but does not provide as much information as the SmartInspect logger.

The following topics and code samples will get you started on how to enable SmartInspect logging support.  
Note that logging support can be turned on and off without changing code or restarting the application.  
Click on the topics below to expand the section and reveal more information.  

<details>
  <summary>Configure Logging Support Settings File</summary>
  <br/>
  Add the following lines to a new file (e.g. "smartinspect.cfg") in the HA `config` directory.  
  You will probably need to change the `host=192.168.1.1` address to your networks equivalent.  This is the location of the SmartInspect Console viewer application (see below for more details on the SI Viewer).

``` ini
; smartinspect.cfg
; SmartInspect Configuration File settings.

; specify SmartInspect properties.
Connections = tcp(host=192.168.1.1,port=4228,timeout=30000,reconnect=true,reconnect.interval=10s,async.enabled=true)
Enabled = True 
Level = Verbose
DefaultLevel = Debug
AppName = Home Assistant VM
        
; set defaults for new sessions
; note that session defaults do not apply to the SiAuto.Main session, since
; this session was already added before a configuration file can be loaded. 
; session defaults only apply to newly added sessions and do not affect existing sessions.
SessionDefaults.Active = True
SessionDefaults.Level = Verbose
SessionDefaults.ColorBG = 0xFFFFFF

; configure some individual session properties.
; note that this does not add the session to the sessionmanager; it simply
; sets the property values IF the session name already exists.
;Session.Main.Active = True
;Session.Main.Level = Verbose
;Session.Main.ColorBG = 0xFFFFFF

; configure SoundTouchPlus sessions.
Session.bosesoundtouchapi.websockets.soundtouchwebsocket.ColorBG = 0xFBD340
Session.custom_components.soundtouchplus.media_player.ColorBG = 0x40A9FB
Session.custom_components.soundtouchplus.config_flow.ColorBG = 0x1AAE54
Session.custom_components.soundtouchplus.ColorBG = 0x1AAE54
```

</details>

<details>
  <summary>SmartInspect Redistributable Console Viewer </summary>
  <br/>
  The SmarrtInspect Redistributable Console Viewer (free) is required to view SmartInspect Log (.sil) formatted log files, as well capture packets via the TcpProtocol or PipeProtocol connections.  The Redistributable Console Viewer can be downloaded from the <a href="https://code-partners.com/offerings/smartinspect/releases/" target="_blank">Code-Partners Software Downloads Page</a>. Note that the "Redistributable Console Viewer" is a free product, while the "SmartInspect Full Setup" is the Professional level viewer that adds a few more bells and whistles for a fee.  Also note that a Console Viewer is NOT required to view plain text (non .sil) formatted log files.
</details>

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[soundtouchplus]: https://github.com/thlucas1/homeassistantcomponent_soundtouchplus
[commits-shield]: https://img.shields.io/github/commit-activity/y/thlucas1/homeassistantcomponent_soundtouchplus.svg?style=for-the-badge
[commits]: https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/commits/main
[license-shield]: https://img.shields.io/github/license/thlucas1/homeassistantcomponent_soundtouchplus.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/thlucas1/homeassistantcomponent_soundtouchplus.svg?style=for-the-badge
[releases]: https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/releases

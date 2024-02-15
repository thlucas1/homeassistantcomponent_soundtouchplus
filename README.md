# Bose SoundTouchPlus

[![GitHub Release][releases-shield]][releases] [![License][license-shield]](LICENSE) [![docs][docs-shield]][docs] [![hacs][hacs-shield]][hacs]

![Project Maintenance][maintenance-shield] [![BuyMeCoffee][buymecoffee-shield]][buymecoffee]

_Home Assistant Integration to integrate with [soundtouchplus][soundtouchplus]._  
Extended support for the Bose SoundTouch line of speaker products for use in Home Assistant.

This integration will set up the following platforms.

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
- PLAY_MEDIA
- PREVIOUS_TRACK
- REPEAT_SET
- SEEK
- SELECT_SOURCE
- SHUFFLE_SET
- STOP
- TURN_OFF
- TURN_ON
- VOLUME_MUTE
- VOLUME_SET
- VOLUME_STEP

The following custom services are also supplied by this integration.
- Play Handoff: Handoff playing source from one SoundTouch device to another.
- Play TTS Message: Play Text-To-Speech notification on a SoundTouch device.  Note that this is limited to ST10,20,30 devices, as Bose ST300 does not support notifications (AFAIK).
- Play URL: Play media content URL on a SoundTouch device.  Note that this is limited to ST10,20,30 devices, as Bose ST300 does not support notifications (AFAIK).
- Get Preset List: Retrieves the list of presets defined to the device.
- Get Recent List: Retrieves the list of recently played items defined to the device.
- Get Music Service Station List: Retrieves a list of stored stations for your music service account (e.g. PANDORA, etc).
- Reboot Device: Reboots the operating system of the SoundTouch device.
- Remote Keypress: Simulates the press and release of a key on the SoundTouch device remote control.
- Snapshot Restore: Restore SoundTouch device settings from a snapshot.
- Snapshot Store: Store SoundTouch device settings to a snapshot.
- Zone Member Toggle: Toggles the given zone member to or from the master device's zone.  A new zone will be created automatically if needed.
- Browse media support that allows the user to play content via the media browser (e.g. Pandora Stations, SoundTouch Presets, and SoundTouch Recently Played).

Check out the [Services Provided wiki](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/Services-Provided) page for detailed explanations and YAML examples of the custom services provided by this integration.

Check out the [Media Player Service Enhancements wiki](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/Media-Player-Service-Enhancements) page for detailed explanations and YAML examples of the media player service enhancements provided by this integration.

## HACS Installation Instructions

- go to HACS main menu.
- click on the 3-dot overflow menu in the upper right, and select `custom repositories` item.
- copy / paste `https://github.com/thlucas1/homeassistantcomponent_soundtouchplus` in the Repository textbox and select `Integration` for the category entry.
- click on `Add` to add the custom repository.
- you can then click on the SoundTouchPlus repository entry (you may need to filter your list first to find the new entry).
- click on `download` to start the download. It will install the soundtouchplus integration to your config/custom_components directory.
- restart HA to start using the component.

## Manual Installation

- Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
- If you do not have a `custom_components` directory (folder) there, you need to create it.
- In the `custom_components` directory (folder) create a new folder called `soundtouchplus`.
- Download _all_ the files from the `custom_components/soundtouchplus/` directory (folder) in this repository.
- Place the files you downloaded in the new directory (folder) you created.
- Restart Home Assistant.
- In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Bose SoundTouchPlus"

## Configuration 

All configuration of the integration is done in the UI.

<!---->

## Advanced Logging Support

The SmartInspectPython package (installed with this integration) can be used to easily debug the integration.
Note that the standard Home Assistant logger is also supported, but does not provide as much information as the SmartInspect logger.

Check out the [SmartInspect Logging Configuration wiki page](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/SmartInspect-Logging-Configuration) for more information on how to configure and enable / disable advanced logging.

## Reporting a Problem

Submit a [Bug Report](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/issues/new?assignees=&labels=Bug&projects=&template=bug.yml) to bring the issue to my attention. I receive a notification when a new issue is opened, and will do my best to address it in a prompt and professional manner.

## Request a New Feature

Do you have an idea for a new feature that could be added to the integration?  Submit a [Feature Request](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/issues/new?assignees=&labels=Feature%2BRequest&projects=&template=feature_request.yml) to get your idea into the queue. I receive a notification when a new request is opened, and will do my best to turn your idea into the latest and greatest feature.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[soundtouchplus]: https://github.com/thlucas1/homeassistantcomponent_soundtouchplus

[releases-shield]: https://img.shields.io/github/release/thlucas1/homeassistantcomponent_soundtouchplus.svg?style=for-the-badge
[releases]: https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/releases
[license-shield]: https://img.shields.io/github/license/thlucas1/homeassistantcomponent_soundtouchplus.svg?style=for-the-badge
[docs]: https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki
[docs-shield]: https://img.shields.io/badge/Docs-Wiki-blue.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[hacs-shield]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge

[maintenance-shield]: https://img.shields.io/badge/maintainer-Todd%20Lucas%20%40thlucas1-blue.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/thlucas1
[buymecoffee-shield]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
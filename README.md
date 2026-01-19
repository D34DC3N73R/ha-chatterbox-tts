# Chatterbox TTS for Home Assistant

A Home Assistant integration for [Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server), a FastAPI-based text-to-speech server that supports voice cloning and multiple predefined voices.

## Features

- 🎙️ **Voice Cloning**: Choose from cloned custom voices available on the Chatterbox-TTS-Server
- 🗣️ **Predefined Voices**: Choose from built-in high-quality voices
- 🔢 **Multi-Entity Support**: Configure multiple TTS entities with different voices from your Chatterbox-TTS-Server
- 🎚️ **Configurable Parameters**:
  - Exaggeration level (0.0 - 2.0) for more expressive speech
  - Speed factor (0.25 - 4.0) to control speech rate (experimental - may cause audio distortions or echoes)
- ⚙️ **Easy Configuration**: Simple UI-based setup through Home Assistant's config flow
- 🏠 **Local Processing**: Works with self-hosted Chatterbox TTS instances for privacy

## Requirements

- Home Assistant 2021.12 or newer
- A running [Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server) instance (local or remote)

## Installation

### HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance
2. Go to HACS → Integrations
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add this repository URL: `https://github.com/D34DC3N73R/ha-chatterbox-tts`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "Chatterbox TTS" in HACS
8. Click "Download" and restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/D34DC3N73R/ha-chatterbox-tts/releases)
2. Extract the files and copy the `custom_components/chatterbox_tts` folder to your Home Assistant's `custom_components` directory
   - If the `custom_components` directory doesn't exist, create it in your Home Assistant configuration directory (where `configuration.yaml` is located)
   - The final path should be: `<config>/custom_components/chatterbox_tts/`
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Chatterbox TTS" and select it
4. Enter your Chatterbox TTS server URL (e.g., `http://localhost:8004` or `http://192.168.1.100:8004`)
5. Choose the voice mode:
   - **Clone Voice**: Use custom voice cloning with reference audio files
   - **Predefined Voice**: Use built-in voices
6. Select a voice from the available options
7. Optionally configure:
   - **Exaggeration** (default: 0.5): Controls expressiveness of the generated speech
   - **Speed Factor** (default: 1.0): Controls speech rate ⚠️ *Experimental - may cause audio distortions or echoes*
8. Click **Submit** to complete the setup

**Note**: You can add the integration multiple times to create separate TTS entities for different voices available on your Chatterbox-TTS-Server. Each entity can be configured with its own voice, exaggeration, and speed settings.

### Changing Voice or Options

You can change the voice or adjust parameters at any time:

1. Go to **Settings** → **Devices & Services**
2. Find the Chatterbox TTS integration
3. Click **Configure**
4. Select a new voice or adjust the exaggeration and speed factor settings
5. Click **Submit**

## Usage

After configuration, a new TTS entity will be created (e.g., `tts.chatterbox_gianna`). You can use it in your automations, scripts, or services. The exaggeration and speed settings you configured will be applied to all TTS calls.

### Service Calls

#### TTS Service Call

```yaml
service: tts.speak
target:
  entity_id: tts.chatterbox_gianna
data:
  media_player_entity_id: media_player.living_room
  message: "Hello, this is a test of the Chatterbox TTS integration!"
```

### Automation Example

```yaml
automation:
  - alias: "Announce when someone arrives home"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: tts.speak
        target:
          entity_id: tts.chatterbox_gianna
        data:
          media_player_entity_id: media_player.living_room
          message: "Welcome home! The front door has been opened."
```

### Script Example

```yaml
script:
  tts_announcement:
    alias: "Make TTS Announcement"
    sequence:
      - service: tts.speak
        target:
          entity_id: tts.chatterbox_gianna
        data:
          media_player_entity_id: "{{ media_player }}"
          message: "{{ message }}"
```

## Troubleshooting

### Integration Fails to Load Voices

- Ensure your Chatterbox-TTS-Server is running and accessible from Home Assistant
- Verify the URL is correct and includes the port number (default: 8004)
- Check that your Chatterbox-TTS-Server has reference audio files (for clone mode) or predefined voices configured

### Audio Not Playing

- Verify your media player is working and accessible
- Check Home Assistant logs for any error messages
- Test your Chatterbox-TTS-Server directly to ensure it's generating audio correctly

### Enable Debug Logging

Add this to your `configuration.yaml` to enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.chatterbox_tts: debug
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Issues

If you encounter any issues, please report them on the [GitHub Issues page](https://github.com/D34DC3N73R/ha-chatterbox-tts/issues).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- Integration developed by [@D34DC3N73R](https://github.com/D34DC3N73R)
- Powered by [Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server)

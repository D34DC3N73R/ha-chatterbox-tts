# Chatterbox TTS for Home Assistant

A Home Assistant integration for [Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server), a FastAPI-based text-to-speech server that supports voice cloning and multiple predefined voices.

## Features

- 🔄 **Model Switching**: Switch between Original, Turbo, and Multilingual Chatterbox models directly from the HA config UI
- 🎙️ **Voice Cloning**: Choose from cloned custom voices available on the Chatterbox-TTS-Server
- 🗣️ **Predefined Voices**: Choose from built-in high-quality voices
- 🔢 **Multi-Entity Support**: Configure multiple TTS entities with different voices from your Chatterbox-TTS-Server
- 🌍 **Multilingual**: Pass a language code when using the Multilingual model (23 languages supported)
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
5. Choose the **Model**:
   - **Original**: High-quality English with emotion exaggeration control
   - **Turbo**: Fastest inference, supports paralinguistic tags like `[laugh]`, `[cough]`, `[chuckle]`
   - **Multilingual**: 23-language support with voice cloning and emotion control
6. Choose the **Voice Mode**:
   - **Clone Voice**: Use custom voice cloning with reference audio files
   - **Predefined Voice**: Use built-in voices
7. Select a voice from the available options
8. Optionally configure:
   - **Exaggeration** (default: 0.5): Controls expressiveness of the generated speech
   - **Speed Factor** (default: 1.0): Controls speech rate ⚠️ *Experimental - may cause audio distortions or echoes*
   - **Language** (Multilingual model only): ISO 639-1 code (e.g., `en`, `fr`, `de`, `ja`, `zh`)
9. Click **Submit** to complete the setup

**Note**: You can add the integration multiple times to create separate TTS entities for different voices available on your Chatterbox-TTS-Server. Each entity can be configured with its own voice, exaggeration, and speed settings.

> ### ⚠️ Important: How Model Switching Works
>
> Chatterbox-TTS-Server can only load **one model at a time** into VRAM. Each TTS entity records which model it was configured with (Original, Turbo, or Multilingual). Before every TTS request, the integration checks what model the server currently has loaded and **automatically hot-swaps if it doesn't match**.
>
> **This means:**
>
> - **If all your entities use the same model** (e.g., all Turbo), the check is a fast no-op and you'll never notice it.
> - **If you have entities configured with different models**, calling one after the other will trigger a model swap. Depending on your GPU, this adds **10–30+ seconds** of latency while weights are unloaded and reloaded. A per-server lock ensures swaps don't race each other — the second call will wait for the first swap to finish.
> - **If the model-info check fails** (e.g., server is slow to respond), the integration proceeds optimistically with whatever model is loaded rather than blocking the TTS call.
> - The server also downloads model weights from Hugging Face on first use of each model type — this is a one-time cost per model.

### Changing Voice, Model, or Options

You can change the voice, model, or adjust parameters at any time:

1. Go to **Settings** → **Devices & Services**
2. Find the Chatterbox TTS integration
3. Click **Configure**
4. Select a new model, voice, or adjust the exaggeration and speed factor settings
5. Click **Submit**

If you changed the model, the server will hot-swap to the new model before saving. This may take a moment.

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

#### Turbo with Paralinguistic Tags

When using the Turbo model, you can include expressive tags directly in your text:

```yaml
service: tts.speak
target:
  entity_id: tts.chatterbox_emily
data:
  media_player_entity_id: media_player.living_room
  message: "Oh wow [laugh] I can't believe that actually worked! [chuckle] Let me try again."
```

Supported tags: `[laugh]`, `[chuckle]`, `[sigh]`, `[gasp]`, `[cough]`, `[clear throat]`, `[sniff]`, `[groan]`, `[shush]`

#### Multilingual with Language Override

When using the Multilingual model, you can override the language per call:

```yaml
service: tts.speak
target:
  entity_id: tts.chatterbox_gianna
data:
  media_player_entity_id: media_player.living_room
  message: "Bonjour, comment ça va?"
  language: fr
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

### Model Switch Failed

- The server must be running and reachable when you change the model in the config UI
- Model hot-swaps can take 10–30+ seconds depending on your GPU — the config flow has a 120-second timeout
- Check the Chatterbox-TTS-Server logs for errors (e.g., out of VRAM, missing model files)
- The server downloads model weights from Hugging Face on first use of each model type — this requires internet access on the server

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

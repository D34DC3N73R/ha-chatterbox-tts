"""TTS platform for Chatterbox."""
from __future__ import annotations

import logging
import aiohttp

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_URL, CONF_VOICE_MODE, CONF_REFERENCE_AUDIO, CONF_EXAGGERATION, CONF_SPEED_FACTOR

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    "en", "en-US", "en-GB", "es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko",
    "ar", "cs", "da", "fi", "el", "hi", "hu", "id", "no", "pl", "ro", "sk", "sv", "tr", "uk",
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Chatterbox TTS entity."""
    async_add_entities([ChatterboxTTSEntity(entry.data, entry.options, entry.entry_id)])

class ChatterboxTTSEntity(TextToSpeechEntity):
    def __init__(self, data: dict, options: dict, entry_id: str):
        self._data = data  # Fixed setup data
        self._options = options or {}
        self._url = data[CONF_URL].rstrip("/")
        raw_voice = data.get(CONF_REFERENCE_AUDIO, "default")
        clean_voice = raw_voice.split(".")[0].replace("-", "_").replace(" ", "_").lower()
        self._attr_unique_id = f"chatterbox_tts_{clean_voice}"
        self._attr_name = f"Chatterbox TTS – {clean_voice.replace('_', ' ').title()}"
        self.entity_id = f"tts.chatterbox_{clean_voice}"

    @property
    def default_language(self) -> str | None:
        return "en-US"

    @property
    def supported_languages(self) -> list[str]:
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        return [CONF_EXAGGERATION, CONF_SPEED_FACTOR]

    @property
    def default_options(self) -> dict:
        return {
            "exaggeration": 0.5,
            "speed_factor": 1.0,
        } | self._options

    async def async_get_tts_audio(
        self,
        message: str,
        language: str | None = None,
        options: dict | None = None,
    ) -> tuple[str, bytes] | tuple[None, None]:
        opts = {**self.default_options, **(options or {})}
        payload = {
            "text": message,
            "voice_mode": self._data.get(CONF_VOICE_MODE, "clone"),
            "output_format": "mp3",
            "split_text": "true",
            "chunk_size": "240",
            "exaggeration": str(opts.get("exaggeration", 0.5)),
            "speed_factor": str(opts.get("speed_factor", 1.0)),
        }
        voice_filename = self._data.get(CONF_REFERENCE_AUDIO)
        if voice_filename:
            if payload["voice_mode"] == "clone":
                payload["reference_audio_filename"] = voice_filename
            else:
                payload["predefined_voice_id"] = voice_filename
        else:
            _LOGGER.error("No voice filename in data - skipping TTS request")
            return None, None

        _LOGGER.debug("Sending payload to Chatterbox: %s", payload)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self._url}/tts", json=payload, timeout=60) as response:
                    if response.status != 200:
                        text = await response.text()
                        _LOGGER.error("Chatterbox TTS error %s: %s", response.status, text)
                        return None, None
                    audio = await response.read()
                    return "mp3", audio
        except Exception as err:
            _LOGGER.exception("Unexpected error in Chatterbox TTS: %s", err)
            return None, None"""

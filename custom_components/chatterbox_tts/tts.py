"""TTS platform for Chatterbox."""
from __future__ import annotations

import asyncio
import logging
import aiohttp

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_VOICE_MODE,
    CONF_REFERENCE_AUDIO,
    CONF_EXAGGERATION,
    CONF_SPEED_FACTOR,
    CONF_MODEL_TYPE,
    CONF_LANGUAGE,
    DEFAULT_MODEL_TYPE,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    "en", "en-US", "en-GB", "es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko",
    "ar", "cs", "da", "fi", "el", "hi", "hu", "id", "no", "pl", "ro", "sk", "sv", "tr", "uk",
    "he", "ms", "sw",
]

# Map server model type strings ("original", "turbo", "multilingual") to config
# selector values used by save_settings
_SERVER_TYPE_TO_SELECTOR = {
    "original": "chatterbox",
    "turbo": "chatterbox-turbo",
    "multilingual": "chatterbox-multilingual",
}

# Timeouts
_API_TIMEOUT = aiohttp.ClientTimeout(total=15)
_MODEL_SWITCH_TIMEOUT = aiohttp.ClientTimeout(total=120)
_TTS_TIMEOUT = aiohttp.ClientTimeout(total=120)


def _get_server_lock(hass: HomeAssistant, server_url: str) -> asyncio.Lock:
    """Get or create a per-server asyncio lock to serialize model switches.

    All entities pointing at the same server URL share one lock so that
    concurrent TTS calls don't race each other through the check-and-swap
    sequence.
    """
    locks: dict[str, asyncio.Lock] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "server_locks", {}
    )
    if server_url not in locks:
        locks[server_url] = asyncio.Lock()
    return locks[server_url]


async def _ensure_model(
    hass: HomeAssistant,
    server_url: str,
    desired_model: str,
) -> bool:
    """Ensure the server is running the desired model, switching if necessary.

    Acquires a per-server lock so only one entity switches at a time.
    Returns True if the server is (now) running the desired model,
    False if the switch failed.
    """
    lock = _get_server_lock(hass, server_url)

    async with lock:
        # Check what the server is currently running
        try:
            async with aiohttp.ClientSession(timeout=_API_TIMEOUT) as session:
                async with session.get(f"{server_url}/api/model-info") as resp:
                    if resp.status == 200:
                        info = await resp.json()
                        current_type = info.get("type")
                        current_selector = _SERVER_TYPE_TO_SELECTOR.get(current_type)
                        if current_selector == desired_model:
                            return True  # Already running the right model
                    else:
                        _LOGGER.warning(
                            "Could not query model info (status %s), proceeding with TTS anyway",
                            resp.status,
                        )
                        return True  # Optimistic — don't block TTS on a failed info check
        except Exception as err:
            _LOGGER.warning(
                "Could not query model info (%s), proceeding with TTS anyway", err
            )
            return True  # Optimistic

        # Need to switch
        _LOGGER.info(
            "Server is running '%s' but entity needs '%s' — hot-swapping model",
            current_selector,
            desired_model,
        )

        try:
            async with aiohttp.ClientSession(timeout=_MODEL_SWITCH_TIMEOUT) as session:
                # Step 1: Save the new model selector
                async with session.post(
                    f"{server_url}/save_settings",
                    json={"model": {"repo_id": desired_model}},
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.error(
                            "Failed to save model setting: %s", await resp.text()
                        )
                        return False

                # Step 2: Hot-swap the engine
                async with session.post(f"{server_url}/restart_server") as resp:
                    if resp.status != 200:
                        _LOGGER.error(
                            "Failed to hot-swap model: %s", await resp.text()
                        )
                        return False

            _LOGGER.info("Model hot-swap to '%s' completed successfully", desired_model)
            return True
        except Exception as err:
            _LOGGER.error("Error during model hot-swap: %s", err)
            return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Chatterbox TTS entity."""
    async_add_entities([ChatterboxTTSEntity(hass, entry.data, entry.options, entry.entry_id)])


class ChatterboxTTSEntity(TextToSpeechEntity):
    def __init__(self, hass: HomeAssistant, data: dict, options: dict, entry_id: str):
        self.hass = hass
        self._data = data  # Fixed setup data
        self._options = options or {}
        self._cfg = {**data, **(options or {})}
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
        return [CONF_EXAGGERATION, CONF_SPEED_FACTOR, CONF_LANGUAGE]

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
        model_type = self._cfg.get(CONF_MODEL_TYPE, DEFAULT_MODEL_TYPE)

        # Ensure the server is running the correct model for this entity
        model_ok = await _ensure_model(self.hass, self._url, model_type)
        if not model_ok:
            _LOGGER.error(
                "Failed to switch server to model '%s' — TTS request aborted",
                model_type,
            )
            return None, None

        opts = {**self.default_options, **(options or {})}
        payload: dict = {
            "text": message,
            "voice_mode": self._cfg.get(CONF_VOICE_MODE, "clone"),
            "output_format": "mp3",
            "split_text": True,
            "chunk_size": 240,
            "exaggeration": float(opts.get("exaggeration", 0.5)),
            "speed_factor": float(opts.get("speed_factor", 1.0)),
        }
        voice_filename = self._cfg.get(CONF_REFERENCE_AUDIO)
        if voice_filename:
            if payload["voice_mode"] == "clone":
                payload["reference_audio_filename"] = voice_filename
            else:
                payload["predefined_voice_id"] = voice_filename
        else:
            _LOGGER.error("No voice filename in data - skipping TTS request")
            return None, None

        # Pass language for multilingual model
        if model_type == "chatterbox-multilingual":
            # Prefer per-call language option, then config language, then HA language
            lang = opts.get(CONF_LANGUAGE) or self._cfg.get(CONF_LANGUAGE) or language or "en"
            # Strip region suffix (e.g. "en-US" -> "en") for the server API
            if lang and "-" in lang:
                lang = lang.split("-")[0]
            payload["language"] = lang

        _LOGGER.debug("Sending payload to Chatterbox: %s", payload)
        try:
            async with aiohttp.ClientSession(timeout=_TTS_TIMEOUT) as session:
                async with session.post(f"{self._url}/tts", json=payload) as response:
                    if response.status != 200:
                        text = await response.text()
                        _LOGGER.error("Chatterbox TTS error %s: %s", response.status, text)
                        return None, None
                    audio = await response.read()
                    return "mp3", audio
        except Exception as err:
            _LOGGER.exception("Unexpected error in Chatterbox TTS: %s", err)
            return None, None

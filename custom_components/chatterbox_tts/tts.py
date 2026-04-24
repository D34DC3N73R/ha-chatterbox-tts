"""TTS platform for Chatterbox."""
from __future__ import annotations

import asyncio
import logging
import re
import aiohttp

from homeassistant.components.tts import TextToSpeechEntity, TTSAudioRequest, TTSAudioResponse
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_VOICE_MODE,
    CONF_REFERENCE_AUDIO,
    CONF_EXAGGERATION,
    CONF_CFG_WEIGHT,
    CONF_SPEED_FACTOR,
    CONF_MODEL_TYPE,
    CONF_LANGUAGE,
    CONF_STREAM,
    CONF_CHUNK_SIZE,
    CONF_TEMPERATURE,
    DEFAULT_MODEL_TYPE,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_TEMPERATURE,
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
        current_type = None
        current_selector = None
        try:
            async with aiohttp.ClientSession(timeout=_API_TIMEOUT) as session:
                async with session.get(f"{server_url}/api/model-info") as resp:
                    if resp.status == 200:
                        info = await resp.json()
                        _LOGGER.debug("model-info response: %s", info)
                        current_type = info.get("type")
                        current_selector = _SERVER_TYPE_TO_SELECTOR.get(current_type)
                        _LOGGER.debug(
                            "model-info: server type=%r → selector=%r, desired=%r",
                            current_type, current_selector, desired_model,
                        )
                        if current_selector == desired_model:
                            _LOGGER.debug("Model already correct (%r), no switch needed", desired_model)
                            return True
                    else:
                        body = await resp.text()
                        _LOGGER.warning(
                            "model-info status %s: %s — proceeding optimistically",
                            resp.status, body,
                        )
                        return True  # Optimistic — don't block TTS on a failed info check
        except Exception as err:
            _LOGGER.warning("Could not query model info (%s), proceeding optimistically", err)
            return True  # Optimistic

        # Need to switch
        _LOGGER.info(
            "Server type=%r (selector=%r) does not match desired=%r — hot-swapping",
            current_type, current_selector, desired_model,
        )
        save_payload = {"model": {"repo_id": desired_model}}
        _LOGGER.debug("save_settings payload: %s", save_payload)

        try:
            async with aiohttp.ClientSession(timeout=_MODEL_SWITCH_TIMEOUT) as session:
                # Step 1: Save the new model selector
                async with session.post(
                    f"{server_url}/save_settings",
                    json=save_payload,
                ) as resp:
                    body = await resp.text()
                    _LOGGER.debug("save_settings status=%s body=%s", resp.status, body)
                    if resp.status != 200:
                        _LOGGER.error("Failed to save model setting (status %s): %s", resp.status, body)
                        return False

                # Step 2: Hot-swap the engine
                async with session.post(f"{server_url}/restart_server") as resp:
                    body = await resp.text()
                    _LOGGER.debug("restart_server status=%s body=%s", resp.status, body)
                    if resp.status != 200:
                        _LOGGER.error("Failed to hot-swap model (status %s): %s", resp.status, body)
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
    _LOGGER.debug(
        "async_setup_entry: entry_id=%s data=%s options=%s",
        entry.entry_id, dict(entry.data), dict(entry.options),
    )
    try:
        entity = ChatterboxTTSEntity(hass, entry.data, entry.options, entry.entry_id, entry.unique_id)
        _LOGGER.debug(
            "Entity created: unique_id=%s entity_id=%s",
            entity._attr_unique_id, entity.entity_id,
        )
        async_add_entities([entity])
    except Exception:
        _LOGGER.exception("Failed to create ChatterboxTTSEntity for entry %s", entry.entry_id)


class ChatterboxTTSEntity(TextToSpeechEntity):
    def __init__(self, hass: HomeAssistant, data: dict, options: dict, entry_id: str, entry_unique_id: str | None = None):
        self.hass = hass
        self._data = data  # Fixed setup data
        self._options = options or {}
        self._cfg = {**data, **(options or {})}
        self._url = data[CONF_URL].rstrip("/")
        raw_voice = data.get(CONF_REFERENCE_AUDIO, "default")
        stem = raw_voice.split(".")[0].lower()
        clean_voice = re.sub(r'[^a-z0-9]+', '_', stem).strip("_") or "default"
        if entry_unique_id:
            # New entries: config flow assigned a human-friendly unique_id like "chatterbox_rogan_2"
            self._attr_unique_id = entry_unique_id
            self._attr_name = f"Chatterbox TTS – {entry_unique_id.removeprefix('chatterbox_').replace('_', ' ').title()}"
            self.entity_id = f"tts.{entry_unique_id}"
            _LOGGER.debug("New entry: unique_id=%s entity_id=%s", self._attr_unique_id, self.entity_id)
        else:
            # Legacy entries: preserve the original unique_id so the entity registry entry is reused
            self._attr_unique_id = f"chatterbox_tts_{clean_voice}"
            self._attr_name = f"Chatterbox TTS – {clean_voice.replace('_', ' ').title()}"
            self.entity_id = f"tts.chatterbox_{clean_voice}"
            _LOGGER.debug("Legacy entry: unique_id=%s entity_id=%s", self._attr_unique_id, self.entity_id)

    @property
    def default_language(self) -> str | None:
        return "en-US"

    @property
    def supported_languages(self) -> list[str]:
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        return [
            CONF_EXAGGERATION,
            CONF_CFG_WEIGHT,
            CONF_SPEED_FACTOR,
            CONF_TEMPERATURE,
            CONF_LANGUAGE,
            CONF_STREAM,
            CONF_CHUNK_SIZE,
        ]

    @property
    def default_options(self) -> dict:
        return {
            CONF_EXAGGERATION: 0.5,
            CONF_CFG_WEIGHT: 0.5,
            CONF_SPEED_FACTOR: 1.0,
            CONF_TEMPERATURE: DEFAULT_TEMPERATURE,
            CONF_STREAM: False,
            CONF_CHUNK_SIZE: DEFAULT_CHUNK_SIZE,
        } | self._options

    async def async_stream_tts_audio(
        self,
        request: TTSAudioRequest,
    ) -> TTSAudioResponse:
        # Consume the async text generator to get the full message string
        message = "".join([chunk async for chunk in request.message_gen])
        language = request.language
        options = request.options
        opts = {**self.default_options, **(options or {})}
        cfg = {**self._cfg, **(options or {})}
        model_type = cfg.get(CONF_MODEL_TYPE, DEFAULT_MODEL_TYPE)
        use_stream = bool(opts.get(CONF_STREAM, False))
        _LOGGER.debug(
            "TTS stream request: entity=%s model_type=%r server_stream=%s",
            self.entity_id, model_type, use_stream,
        )

        model_ok = await _ensure_model(self.hass, self._url, model_type)
        if not model_ok:
            _LOGGER.error(
                "Failed to switch server to model '%s' — TTS stream request aborted",
                model_type,
            )

            async def _empty():
                return
                yield

            return TTSAudioResponse(extension="wav", data_gen=_empty())

        voice_filename = cfg.get(CONF_REFERENCE_AUDIO)
        if not voice_filename:
            _LOGGER.error("No voice filename in data - skipping TTS stream request")

            async def _empty():
                return
                yield

            return TTSAudioResponse(extension="wav", data_gen=_empty())

        voice_mode = cfg.get(CONF_VOICE_MODE, "clone")

        is_turbo = model_type == "chatterbox-turbo"

        payload: dict = {
            "text": message,
            "voice_mode": voice_mode,
            "split_text": True,
            "chunk_size": int(opts.get(CONF_CHUNK_SIZE, DEFAULT_CHUNK_SIZE)),
        }
        if not is_turbo:
            payload["exaggeration"] = float(opts.get(CONF_EXAGGERATION, 0.5))
            payload["cfg_weight"] = float(opts.get(CONF_CFG_WEIGHT, 0.5))
            payload["speed_factor"] = float(opts.get(CONF_SPEED_FACTOR, 1.0))
            payload["temperature"] = float(opts.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE))

        if voice_mode == "clone":
            payload["reference_audio_filename"] = voice_filename
        else:
            payload["predefined_voice_id"] = voice_filename

        if model_type == "chatterbox-multilingual":
            lang = opts.get(CONF_LANGUAGE) or cfg.get(CONF_LANGUAGE) or language or "en"
            if lang and "-" in lang:
                lang = lang.split("-")[0]
            payload["language"] = lang

        url = self._url

        if use_stream:
            payload["output_format"] = "wav"
            payload["stream"] = True
            _LOGGER.debug("Sending payload to Chatterbox (stream): %s", payload)

            async def audio_gen_stream():
                try:
                    async with aiohttp.ClientSession(timeout=_TTS_TIMEOUT) as session:
                        async with session.post(f"{url}/tts", json=payload) as response:
                            if response.status != 200:
                                body = await response.text()
                                _LOGGER.error(
                                    "Chatterbox TTS stream error %s: %s", response.status, body
                                )
                                return
                            first = True
                            async for chunk in response.content.iter_chunked(8192):
                                if first:
                                    first = False
                                    if len(chunk) >= 28:
                                        sample_rate = int.from_bytes(chunk[24:28], "little")
                                        _LOGGER.debug("Stream WAV sample_rate=%d", sample_rate)
                                yield chunk
                except Exception as err:
                    _LOGGER.exception("Error in Chatterbox TTS stream: %s", err)

            return TTSAudioResponse(extension="wav", data_gen=audio_gen_stream())

        else:
            payload["output_format"] = "mp3"
            _LOGGER.debug("Sending payload to Chatterbox (buffered): %s", payload)

            async def audio_gen_buffered():
                try:
                    async with aiohttp.ClientSession(timeout=_TTS_TIMEOUT) as session:
                        async with session.post(f"{url}/tts", json=payload) as response:
                            if response.status != 200:
                                body = await response.text()
                                _LOGGER.error(
                                    "Chatterbox TTS error %s: %s", response.status, body
                                )
                                return
                            yield await response.read()
                except Exception as err:
                    _LOGGER.exception("Unexpected error in Chatterbox TTS: %s", err)

            return TTSAudioResponse(extension="mp3", data_gen=audio_gen_buffered())

"""Config flow for Chatterbox TTS"""
from __future__ import annotations

import logging
import re
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_VOICE_MODE,
    CONF_REFERENCE_AUDIO,
    CONF_EXAGGERATION,
    CONF_SPEED_FACTOR,
    CONF_MODEL_TYPE,
    CONF_LANGUAGE,
    MODEL_TYPES,
    DEFAULT_MODEL_TYPE,
)

_LOGGER = logging.getLogger(__name__)

# Timeout for API calls (seconds)
API_TIMEOUT = aiohttp.ClientTimeout(total=15)
# Model switching can take a while (loading weights into VRAM)
MODEL_SWITCH_TIMEOUT = aiohttp.ClientTimeout(total=120)


async def _fetch_current_model(url: str) -> str | None:
    """Fetch the currently loaded model type from the server."""
    try:
        async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
            async with session.get(f"{url}/api/model-info") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _LOGGER.debug("model-info raw response: %s", data)
                    model_type = data.get("type")
                    _LOGGER.debug("model-info type field: %r", model_type)
                    return model_type  # "original", "turbo", "multilingual"
                else:
                    body = await resp.text()
                    _LOGGER.warning("model-info returned status %s: %s", resp.status, body)
    except Exception as err:
        _LOGGER.debug("Could not fetch model info: %s", err)
    return None


def _server_type_to_config(server_type: str | None) -> str:
    """Map server model type string to config repo_id selector."""
    mapping = {
        "original": "chatterbox",
        "turbo": "chatterbox-turbo",
        "multilingual": "chatterbox-multilingual",
    }
    return mapping.get(server_type, DEFAULT_MODEL_TYPE)


async def _switch_model(url: str, model_type: str) -> bool:
    """Switch the server to a different model via save_settings + restart_server.

    Returns True on success, False on failure.
    """
    save_payload = {"model": {"repo_id": model_type}}
    _LOGGER.debug("Switching model to %r, save_settings payload: %s", model_type, save_payload)
    try:
        async with aiohttp.ClientSession(timeout=MODEL_SWITCH_TIMEOUT) as session:
            # Step 1: Save the new model selector to config.yaml
            async with session.post(
                f"{url}/save_settings",
                json=save_payload,
            ) as resp:
                body = await resp.text()
                _LOGGER.debug("save_settings status=%s body=%s", resp.status, body)
                if resp.status != 200:
                    _LOGGER.error("Failed to save model setting (status %s): %s", resp.status, body)
                    return False

            # Step 2: Hot-swap the engine
            async with session.post(f"{url}/restart_server") as resp:
                body = await resp.text()
                _LOGGER.debug("restart_server status=%s body=%s", resp.status, body)
                if resp.status != 200:
                    _LOGGER.error("Failed to hot-swap model (status %s): %s", resp.status, body)
                    return False

            _LOGGER.info("Successfully switched server model to %s", model_type)
            return True
    except Exception as err:
        _LOGGER.error("Error switching model: %s", err)
        return False


class ChatterboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.data: dict = {}

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            self.data = user_input
            url = user_input[CONF_URL].rstrip("/")
            model_type = user_input.get(CONF_MODEL_TYPE, DEFAULT_MODEL_TYPE)

            # Check what model the server currently has loaded
            current_type = await _fetch_current_model(url)
            current_config = _server_type_to_config(current_type)

            # If the user selected a different model, switch it
            if current_config != model_type:
                success = await _switch_model(url, model_type)
                if not success:
                    errors["base"] = "model_switch_failed"
                    # Fall through to show form again with error

            if not errors:
                return await self.async_step_voice_params()

        # Build model type options from MODEL_TYPES dict
        model_options = [
            selector.SelectOptionDict(value=k, label=v)
            for k, v in MODEL_TYPES.items()
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default="http://localhost:8004"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                ),
                vol.Required(CONF_MODEL_TYPE, default=DEFAULT_MODEL_TYPE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=model_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_VOICE_MODE, default="clone"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="clone", label="Clone Voice"),
                            selector.SelectOptionDict(value="predefined", label="Predefined Voice"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_voice_params(self, user_input=None):
        errors = {}

        if user_input is not None:
            final_data = {**self.data, **user_input}
            _LOGGER.debug("Creating config entry with data: %s", final_data)
            voice = user_input.get(CONF_REFERENCE_AUDIO, "")
            stem = voice.split(".")[0].lower()
            clean_voice = re.sub(r'[^a-z0-9]+', '_', stem).strip("_") or "default"
            existing_ids = {e.unique_id for e in self.hass.config_entries.async_entries(DOMAIN)}
            base = f"chatterbox_{clean_voice}"
            uid, n = base, 2
            while uid in existing_ids:
                uid = f"{base}_{n}"
                n += 1
            _LOGGER.debug("Assigned config entry unique_id=%s", uid)
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured(updates=final_data)
            return self.async_create_entry(title="Chatterbox TTS", data=final_data)

        voice_mode = self.data[CONF_VOICE_MODE]
        url = self.data[CONF_URL].rstrip("/")
        model_type = self.data.get(CONF_MODEL_TYPE, DEFAULT_MODEL_TYPE)

        if voice_mode == "predefined":
            endpoint = "/get_predefined_voices"
            option_builder = lambda v: {"value": v["filename"], "label": v["display_name"]}
        else:
            endpoint = "/get_reference_files"
            option_builder = lambda f: {"value": f, "label": f}

        options = []
        try:
            async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
                async with session.get(f"{url}{endpoint}") as resp:
                    _LOGGER.debug("Voice list %s status=%s", endpoint, resp.status)
                    if resp.status == 200:
                        data = await resp.json()
                        _LOGGER.debug("Voice list raw response: %s", data)
                        options = [option_builder(item) for item in data]
                    else:
                        body = await resp.text()
                        _LOGGER.warning("Voice list %s returned status %s: %s", endpoint, resp.status, body)
                        errors["base"] = "fetch_voices_failed"
        except Exception:
            _LOGGER.exception("Failed to fetch voice list from %s%s", url, endpoint)
            errors["base"] = "fetch_voices_failed"

        if not options:
            _LOGGER.warning("No voices returned; falling back to default Gianna.wav")
            options = [
                {"value": "Gianna.wav", "label": "Gianna"},
            ]

        default_voice = options[0]["value"]

        # Build the schema - add language selector for multilingual model
        fields: dict = {
            vol.Required(CONF_REFERENCE_AUDIO, default=default_voice): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=o["value"], label=o["label"])
                        for o in options
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_EXAGGERATION, default=0.5): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.0, max=2.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_SPEED_FACTOR, default=1.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.25, max=4.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
        }

        if model_type == "chatterbox-multilingual":
            fields[vol.Optional(CONF_LANGUAGE, default="en")] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )

        schema = vol.Schema(fields)

        return self.async_show_form(
            step_id="voice_params",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChatterboxOptionsFlow()


class ChatterboxOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}

        if user_input is not None:
            current = {**self.config_entry.data, **self.config_entry.options}
            url = current[CONF_URL].rstrip("/")
            new_model = user_input.get(CONF_MODEL_TYPE)
            old_model = current.get(CONF_MODEL_TYPE, DEFAULT_MODEL_TYPE)

            # If model type changed, switch it on the server
            if new_model and new_model != old_model:
                success = await _switch_model(url, new_model)
                if not success:
                    errors["base"] = "model_switch_failed"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        voice_mode = current.get(CONF_VOICE_MODE, "clone")
        url = current[CONF_URL].rstrip("/")
        current_model = current.get(CONF_MODEL_TYPE, DEFAULT_MODEL_TYPE)

        if voice_mode == "predefined":
            endpoint = "/get_predefined_voices"
            option_builder = lambda v: {"value": v["filename"], "label": v["display_name"]}
        else:
            endpoint = "/get_reference_files"
            option_builder = lambda f: {"value": f, "label": f}

        options = []
        try:
            async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
                async with session.get(f"{url}{endpoint}") as resp:
                    _LOGGER.debug("Options voice list %s status=%s", endpoint, resp.status)
                    if resp.status == 200:
                        data = await resp.json()
                        _LOGGER.debug("Options voice list raw response: %s", data)
                        options = [option_builder(item) for item in data]
                    else:
                        body = await resp.text()
                        _LOGGER.warning("Options voice list %s returned status %s: %s", endpoint, resp.status, body)
                        errors["base"] = "fetch_voices_failed"
        except Exception:
            _LOGGER.exception("Failed to fetch voice list from %s%s (options flow)", url, endpoint)
            errors["base"] = "fetch_voices_failed"

        if not options:
            _LOGGER.warning("No voices returned in options flow; falling back to default Gianna.wav")
            options = [
                {"value": "Gianna.wav", "label": "Gianna"},
            ]

        default_voice = current.get(CONF_REFERENCE_AUDIO) or options[0]["value"]

        model_options = [
            selector.SelectOptionDict(value=k, label=v)
            for k, v in MODEL_TYPES.items()
        ]

        fields: dict = {
            vol.Required(CONF_MODEL_TYPE, default=current_model): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=model_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_REFERENCE_AUDIO, default=default_voice): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=o["value"], label=o["label"])
                        for o in options
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_EXAGGERATION, default=current.get(CONF_EXAGGERATION, 0.5)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.0, max=2.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_SPEED_FACTOR, default=current.get(CONF_SPEED_FACTOR, 1.0)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.25, max=4.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
        }

        # Add language field for multilingual model
        if current_model == "chatterbox-multilingual":
            fields[vol.Optional(CONF_LANGUAGE, default=current.get(CONF_LANGUAGE, "en"))] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )

        schema = vol.Schema(fields)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

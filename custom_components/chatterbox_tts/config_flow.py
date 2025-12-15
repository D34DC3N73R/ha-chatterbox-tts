"""Config flow for Chatterbox TTS — dropdown for both modes."""
from __future__ import annotations

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
)

class ChatterboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.data: dict = {}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.data = user_input
            return await self.async_step_voice_params()

        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default="http://localhost:8004"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                ),
                vol.Required(CONF_VOICE_MODE, default="clone"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="clone", label="Clone Voice"),
                            selector.SelectOptionDict(value="predefined", label="Predefined voice"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_voice_params(self, user_input=None):
        errors = {}

        if user_input is not None:
            final_data = {**self.data, **user_input}
            self._abort_if_unique_id_configured(updates=final_data)
            return self.async_create_entry(title="Chatterbox TTS", data=final_data)

        voice_mode = self.data[CONF_VOICE_MODE]
        url = self.data[CONF_URL].rstrip("/")

        if voice_mode == "predefined":
            endpoint = "/get_predefined_voices"
            option_builder = lambda v: {"value": v["filename"], "label": v["display_name"]}
        else:
            endpoint = "/get_reference_files"
            option_builder = lambda f: {"value": f, "label": f}

        options = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        options = [option_builder(item) for item in data]
        except Exception:
            errors["base"] = "fetch_voices_failed"

        if not options:
            if voice_mode == "predefined":
                options = [
                    {"value": "Alice.wav", "label": "Alice"},
                    {"value": "Abigail.wav", "label": "Abigail"},
                ]
            else:
                options = [
                    {"value": "Gianna.wav", "label": "Gianna.wav"},
                ]

        # Use dict access for default
        default_voice = self.data.get(CONF_REFERENCE_AUDIO) or options[0]["value"]

        schema = vol.Schema(
            {
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
        )

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
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        voice_mode = current.get(CONF_VOICE_MODE, "clone")
        url = current[CONF_URL].rstrip("/")

        if voice_mode == "predefined":
            endpoint = "/get_predefined_voices"
            option_builder = lambda v: {"value": v["filename"], "label": v["display_name"]}
        else:
            endpoint = "/get_reference_files"
            option_builder = lambda f: {"value": f, "label": f}

        options = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        options = [option_builder(item) for item in data]
        except Exception:
            errors["base"] = "fetch_voices_failed"

        if not options:
            if voice_mode == "predefined":
                options = [
                    {"value": "Alice.wav", "label": "Alice"},
                ]
            else:
                options = [
                    {"value": "Gianna.wav", "label": "Gianna.wav"},
                ]

        default_voice = current.get(CONF_REFERENCE_AUDIO) or options[0]["value"]

        schema = vol.Schema(
            {
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
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

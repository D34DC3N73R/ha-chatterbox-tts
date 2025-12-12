"""Config flow for Chatterbox TTS."""
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
                            selector.SelectOptionDict(value="clone", label="Clone (voice cloning)"),
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

        common_schema = {
            vol.Optional(CONF_EXAGGERATION, default=0.55): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.0, max=2.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_SPEED_FACTOR, default=1.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.25, max=4.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
        }

        if voice_mode == "predefined":
            url = self.data[CONF_URL].rstrip("/")
            options = []

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{url}/get_predefined_voices") as resp:
                        if resp.status == 200:
                            voices = await resp.json()
                            options = [
                                selector.SelectOptionDict(value=v["filename"], label=v["display_name"])
                                for v in voices
                            ]
            except Exception:
                errors["base"] = "fetch_voices_failed"

            if not options:
                options = [
                    selector.SelectOptionDict(value="Alice.wav", label="Alice"),
                    selector.SelectOptionDict(value="Abigail.wav", label="Abigail"),
                ]

            default_voice = self.data.get(CONF_REFERENCE_AUDIO) or options[0]["value"]

            schema = vol.Schema(
                {
                    vol.Required(CONF_REFERENCE_AUDIO, default=default_voice): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                    ),
                    **common_schema,
                }
            )

        else:  # clone
            schema = vol.Schema(
                {
                    vol.Required(CONF_REFERENCE_AUDIO, default=self.data.get(CONF_REFERENCE_AUDIO, "")): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    **common_schema,
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
    """Options flow — no __init__, HA sets self.config_entry automatically."""

    async def async_step_init(self, user_input=None):
        """Single-step options flow."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        voice_mode = current.get(CONF_VOICE_MODE, "clone")

        common_schema = {
            vol.Optional(CONF_EXAGGERATION, default=current.get(CONF_EXAGGERATION, 0.55)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.0, max=2.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_SPEED_FACTOR, default=current.get(CONF_SPEED_FACTOR, 1.0)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.25, max=4.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
        }

        if voice_mode == "predefined":
            url = current[CONF_URL].rstrip("/")
            options = []

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{url}/get_predefined_voices") as resp:
                        if resp.status == 200:
                            voices = await resp.json()
                            options = [
                                selector.SelectOptionDict(value=v["filename"], label=v["display_name"])
                                for v in voices
                            ]
            except Exception:
                errors["base"] = "fetch_voices_failed"

            if not options:
                options = [
                    selector.SelectOptionDict(value="Alice.wav", label="Alice"),
                    selector.SelectOptionDict(value="Abigail.wav", label="Abigail"),
                ]

            default_voice = current.get(CONF_REFERENCE_AUDIO) or options[0]["value"]

            schema = vol.Schema(
                {
                    vol.Required(CONF_REFERENCE_AUDIO, default=default_voice): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                    ),
                    **common_schema,
                }
            )

        else:  # clone
            schema = vol.Schema(
                {
                    vol.Required(CONF_REFERENCE_AUDIO, default=current.get(CONF_REFERENCE_AUDIO, "")): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    **common_schema,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
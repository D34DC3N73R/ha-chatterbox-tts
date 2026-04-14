"""Constants for Chatterbox TTS."""
DOMAIN = "chatterbox_tts"

CONF_URL = "url"
CONF_VOICE_MODE = "voice_mode"
CONF_REFERENCE_AUDIO = "reference_audio_filename"
CONF_EXAGGERATION = "exaggeration"
CONF_SPEED_FACTOR = "speed_factor"
CONF_MODEL_TYPE = "model_type"
CONF_LANGUAGE = "language"

MODEL_TYPES = {
    "chatterbox": "Original (English, emotion control)",
    "chatterbox-turbo": "Turbo (fast, paralinguistic tags)",
    "chatterbox-multilingual": "Multilingual (23 languages)",
}

DEFAULT_MODEL_TYPE = "chatterbox-turbo"
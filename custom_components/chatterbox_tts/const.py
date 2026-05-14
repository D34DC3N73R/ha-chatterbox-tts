"""Constants for Chatterbox TTS."""
DOMAIN = "chatterbox_tts"

CONF_URL = "url"
CONF_VOICE_MODE = "voice_mode"
CONF_REFERENCE_AUDIO = "reference_audio_filename"
CONF_EXAGGERATION = "exaggeration"
CONF_CFG_WEIGHT = "cfg_weight"
CONF_SPEED_FACTOR = "speed_factor"
CONF_MODEL_TYPE = "model_type"
CONF_LANGUAGE = "language"
CONF_STREAM = "stream"
CONF_CHUNK_SIZE = "chunk_size"
CONF_TEMPERATURE = "temperature"

MODEL_TYPES = {
    "chatterbox": "Original (English, emotion control)",
    "chatterbox-turbo": "Turbo (fast, paralinguistic tags)",
    "chatterbox-multilingual": "Multilingual (23 languages)",
}

DEFAULT_MODEL_TYPE = "chatterbox"
DEFAULT_CHUNK_SIZE = 120
DEFAULT_TEMPERATURE = 0.8

CONF_OUTPUT_FORMAT = "output_format"
DEFAULT_OUTPUT_FORMAT = "mp3"
OUTPUT_FORMATS = {
    "mp3":  "MP3 (compressed, smaller)",
    "wav":  "WAV (lossless, larger)",
    "opus": "Opus (compressed, efficient)",
}

from typing import Optional
import logging

from openai import OpenAI

from inq_service_svc import config

_logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def get_openai_model_name() -> str:
    """Return configured OpenAI model name."""
    return config.OPENAI_MODEL_NAME


def get_openai_client() -> OpenAI:
    """Lazily initialize and return a singleton OpenAI client.

    Raises RuntimeError when OPENAI_API_KEY is not configured.
    Any initialization error is logged with exc_info.
    """
    global _client
    if _client is not None:
        return _client
    try:
        api_key = config.OPENAI_API_KEY
        if not api_key:
            # raise then be caught below to ensure logging.error(e, exc_info=True) is executed
            raise RuntimeError("OPENAI_API_KEY is not configured")
        _client = OpenAI(api_key=api_key)
        return _client
    except Exception as e:
        # Required structured error logging with exception info
        logging.error("Failed to initialize OpenAI client: %s", e, exc_info=True)
        logging.error(e, exc_info=True)
        # Re-raise to signal caller
        raise

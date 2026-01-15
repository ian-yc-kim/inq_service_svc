from typing import Any, Optional
import logging

from pydantic import BaseModel

from inq_service_svc.utils.openai_client import (
    get_openai_client,
    get_openai_model_name,
)

_logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = ["Billing", "Technical", "General", "Account"]
ALLOWED_URGENCIES = ["Low", "Medium", "High"]


class ClassificationResult(BaseModel):
    category: str
    urgency: str


DEFAULT_CLASSIFICATION = ClassificationResult(category="General", urgency="Medium")


def _build_prompt(title: str, content: str) -> str:
    # strict instructions: only choose from provided lists and return JSON with category and urgency
    instruction = (
        "You are an assistant that classifies customer inquiries.\n"
        "Respond ONLY with a JSON object containing exactly two keys: category and urgency.\n"
        "category must be one of the following: ['Billing', 'Technical', 'General', 'Account'].\n"
        "urgency must be one of the following: ['Low', 'Medium', 'High'].\n"
        "Do NOT include any additional text, explanation, or fields.\n"
        "Return valid JSON only.\n\n"
        "Inquiry Title: {title}\n"
        "Inquiry Content: {content}\n"
    )
    return instruction.format(title=title, content=content)


def _extract_parsed(response: Any) -> Optional[Any]:
    # Try several common shapes returned by OpenAI parse helper
    try:
        # choices[0].message.parsed is the preferred shape
        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                parsed = getattr(msg, "parsed", None)
                if parsed is not None:
                    return parsed
        # fallback: response.parsed
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return parsed
        # fallback: response itself might be the parsed model or dict
        return response
    except Exception as e:
        _logger.error(e, exc_info=True)
        return None


def classify_inquiry(title: str, content: str) -> ClassificationResult:
    """Classify an inquiry using the configured OpenAI model.

    Returns ClassificationResult. On any error or invalid response, returns DEFAULT_CLASSIFICATION.
    """
    prompt = _build_prompt(title, content)
    try:
        client = get_openai_client()
        model_name = get_openai_model_name()
        # Use parse helper to directly parse into our Pydantic model
        response = client.with_options(max_retries=3).beta.chat.completions.parse(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=ClassificationResult,
        )

        parsed = _extract_parsed(response)
        if parsed is None:
            return DEFAULT_CLASSIFICATION

        # parsed may be a pydantic model instance or a dict-like
        if isinstance(parsed, ClassificationResult):
            result = parsed
        else:
            try:
                # Use pydantic v2 model_validate for dicts
                result = ClassificationResult.model_validate(parsed)  # type: ignore[attr-defined]
            except Exception as e:
                _logger.error(e, exc_info=True)
                return DEFAULT_CLASSIFICATION

        # Validate allowed values strictly
        if (
            not isinstance(result.category, str)
            or not isinstance(result.urgency, str)
            or result.category not in ALLOWED_CATEGORIES
            or result.urgency not in ALLOWED_URGENCIES
        ):
            _logger.warning(
                "OpenAI returned out-of-bound classification: %s",
                result,
            )
            return DEFAULT_CLASSIFICATION

        return result
    except Exception as e:
        logging.error(e, exc_info=True)
        return DEFAULT_CLASSIFICATION

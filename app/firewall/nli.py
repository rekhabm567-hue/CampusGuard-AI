# ============================================================
# NLI ENTAILMENT FUNCTION
# LLM HALLUCINATION FIREWALL
#
# Wraps an NLI cross-encoder as entailment_fn(claim, evidence)
# -> {"entailment": p, "contradiction": p, "neutral": p}.
# Label order is read from the model config, never assumed.
# ============================================================

import logging

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_NLI_MODEL = "cross-encoder/nli-deberta-v3-xsmall"

_CACHE = {}


def _softmax(logits):
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / exp.sum()


def load_nli(model_name=DEFAULT_NLI_MODEL):
    """Return (CrossEncoder, {label_name: index}) or None on failure."""

    if model_name in _CACHE:
        return _CACHE[model_name]

    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name)

        id2label = model.model.config.id2label
        labels = {str(name).lower(): int(idx) for idx, name in id2label.items()}

        missing = {"entailment", "contradiction"} - set(labels)

        if missing:
            raise ValueError(f"Unexpected NLI labels: {id2label}")

        _CACHE[model_name] = (model, labels)

    except Exception as error:
        logger.warning("NLI model %s not available (%s).", model_name, error)
        _CACHE[model_name] = None

    return _CACHE[model_name]


def create_entailment_fn(model_name=DEFAULT_NLI_MODEL):
    """Return an entailment_fn, or None if the model can't load."""

    loaded = load_nli(model_name)

    if loaded is None:
        return None

    model, labels = loaded

    def entailment_fn(claim, evidence_text):
        logits = np.asarray(
            model.predict([(str(evidence_text), str(claim))])[0],
            dtype="float64",
        )
        probs = _softmax(logits)

        return {
            "entailment": float(probs[labels["entailment"]]),
            "contradiction": float(probs[labels["contradiction"]]),
            "neutral": float(probs[labels["neutral"]])
            if "neutral" in labels
            else 0.0,
        }

    return entailment_fn
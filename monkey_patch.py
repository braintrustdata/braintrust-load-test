import braintrust


def _validate_and_sanitize_experiment_log_partial_args(event):
    # Make sure only certain keys are specified.
    forbidden_keys = set(event.keys()) - {
        "input",
        "output",
        "expected",
        "tags",
        "scores",
        "metadata",
        "metrics",
        "dataset_record_id",
        "inputs",
        # MONKEY PATCH ADDED
        "created",
    }
    if forbidden_keys:
        raise ValueError(f"The following keys may are not permitted: {forbidden_keys}")

    scores = event.get("scores")
    if scores:
        for name, score in scores.items():
            if not isinstance(name, str):
                raise ValueError("score names must be strings")

            if score is None:
                continue

            if isinstance(score, bool):
                score = 1 if score else 0
                scores[name] = score

            if not isinstance(score, (int, float)):
                raise ValueError("score values must be numbers")
            if score < 0 or score > 1:
                raise ValueError("score values must be between 0 and 1")

    metadata = event.get("metadata")
    if metadata:
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary")
        for key in metadata.keys():
            if not isinstance(key, str):
                raise ValueError("metadata keys must be strings")

    metrics = event.get("metrics")
    if metrics:
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be a dictionary")
        for key in metrics.keys():
            if not isinstance(key, str):
                raise ValueError("metric keys must be strings")

        for value in metrics.values():
            if not isinstance(value, (int, float)):
                raise ValueError("metric values must be numbers")

    tags = event.get("tags")
    if tags:
        braintrust.logger.validate_tags(tags)

    input = event.get("input")
    inputs = event.get("inputs")
    if input is not None and inputs is not None:
        raise ValueError(
            "Only one of input or inputs (deprecated) can be specified. Prefer input."
        )
    if inputs is not None:
        return dict(
            **{k: v for k, v in event.items() if k not in ["input", "inputs"]},
            input=inputs,
        )
    else:
        return {k: v for k, v in event.items()}


braintrust.logger._validate_and_sanitize_experiment_log_partial_args = (
    _validate_and_sanitize_experiment_log_partial_args
)

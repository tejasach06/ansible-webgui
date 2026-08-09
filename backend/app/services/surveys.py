import re

_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TYPES = {"text", "textarea", "password", "integer", "boolean", "choice"}


def validate_survey_spec(spec: list) -> None:
    if not isinstance(spec, list):
        raise ValueError("survey_not_a_list")
    seen = set()
    for field in spec:
        var = field.get("var") if isinstance(field, dict) else None
        if not var:
            raise ValueError("survey_var_missing")
        if not _VAR_RE.match(var):
            raise ValueError("survey_var_invalid")
        if var in seen:
            raise ValueError("survey_var_duplicate")
        seen.add(var)
        if field.get("type") not in _TYPES:
            raise ValueError("survey_type_invalid")
        if field.get("type") == "choice" and not field.get("choices"):
            raise ValueError("survey_choices_required")


def apply_survey(spec: list, answers: dict) -> tuple[dict, dict]:
    validate_survey_spec(spec)
    answers = answers or {}
    plain_vars = {}
    secret_vars = {}
    for field in spec:
        var = field["var"]
        value = answers.get(var, field.get("default"))
        if field.get("required") and (value is None or value == ""):
            raise ValueError("survey_answer_required")
        if value is None or value == "":
            continue
        kind = field.get("type")
        if kind == "integer":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError("survey_answer_invalid")
            if field.get("min") is not None and value < field["min"]:
                raise ValueError("survey_answer_invalid")
            if field.get("max") is not None and value > field["max"]:
                raise ValueError("survey_answer_invalid")
        elif kind == "boolean":
            value = bool(value)
        elif kind == "choice" and value not in field.get("choices", []):
            raise ValueError("survey_answer_invalid")
        target = secret_vars if kind == "password" else plain_vars
        target[var] = value
    return plain_vars, secret_vars

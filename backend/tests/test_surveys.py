import pytest

from app.services.surveys import apply_survey, validate_survey_spec


def field(var, type="text", **overrides):
    data = {"var": var, "label": var, "type": type, "required": False, "default": "", "choices": [], "min": None, "max": None}
    data.update(overrides)
    return data


def test_validate_survey_spec_rejects_duplicate_vars():
    with pytest.raises(ValueError, match="survey_var_duplicate"):
        validate_survey_spec([field("env"), field("env")])


def test_validate_survey_spec_rejects_invalid_type():
    with pytest.raises(ValueError, match="survey_type_invalid"):
        validate_survey_spec([field("env", "bogus")])


def test_validate_survey_spec_requires_choice_options():
    with pytest.raises(ValueError, match="survey_choices_required"):
        validate_survey_spec([field("env", "choice")])


def test_apply_survey_requires_answer_without_default():
    with pytest.raises(ValueError, match="survey_answer_required"):
        apply_survey([field("env", required=True, default="")], {})


def test_apply_survey_rejects_bad_integer_and_choice():
    with pytest.raises(ValueError, match="survey_answer_invalid"):
        apply_survey([field("count", "integer", min=2, max=4)], {"count": "8"})
    with pytest.raises(ValueError, match="survey_answer_invalid"):
        apply_survey([field("env", "choice", choices=["dev", "prod"])], {"env": "stage"})


def test_apply_survey_coerces_integer_and_routes_password_to_secrets():
    plain, secret = apply_survey([
        field("count", "integer"),
        field("api_token", "password"),
    ], {"count": "3", "api_token": "top-secret", "ignored": "x"})
    assert plain == {"count": 3}
    assert secret == {"api_token": "top-secret"}

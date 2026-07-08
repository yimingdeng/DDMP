import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def test_six_digit_simple_password_is_allowed():
    validate_password("123456")


def test_password_shorter_than_six_is_rejected():
    with pytest.raises(ValidationError):
        validate_password("12345")

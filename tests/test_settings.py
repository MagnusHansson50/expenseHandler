"""core/settings.py: which highest price per item a user may choose."""

import math

import pytest

from core.constants import MAX_PRICE, MAX_PRICE_CEILING, MAX_PRICE_SETTING_MIN
from core.settings import max_price_problem


@pytest.mark.parametrize("value", [MAX_PRICE_SETTING_MIN, MAX_PRICE, 250_000.5, MAX_PRICE_CEILING])
def test_values_in_the_range_are_allowed(value):
    assert max_price_problem(value) is None


@pytest.mark.parametrize("value", [MAX_PRICE_SETTING_MIN - 1, MAX_PRICE_CEILING + 0.01, 0, -100])
def test_values_outside_the_range_say_what_the_range_is(value):
    problem = max_price_problem(value)
    assert problem.key == "max_price_out_of_range"
    assert problem.params == {"min": MAX_PRICE_SETTING_MIN, "max": MAX_PRICE_CEILING}


@pytest.mark.parametrize("value", [None, "50000", True, math.nan, math.inf])
def test_anything_but_a_finite_number_is_refused(value):
    assert max_price_problem(value).key == "max_price_not_a_number"


def test_the_default_lies_within_the_range():
    assert MAX_PRICE_SETTING_MIN <= MAX_PRICE <= MAX_PRICE_CEILING

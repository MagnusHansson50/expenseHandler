"""Rules for a user's own settings, as pure functions.

The only setting so far is the highest price per item ("max amount"): each
user chooses it within MAX_PRICE_SETTING_MIN..MAX_PRICE_CEILING; without a
choice it is MAX_PRICE.
"""

import math

from core.constants import MAX_PRICE_CEILING, MAX_PRICE_SETTING_MIN
from core.receipt import Problem


def max_price_problem(value):
    """Why `value` cannot be a user's highest price per item, as a Problem, or None if it can."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return Problem("max_price_not_a_number", {})
    if not MAX_PRICE_SETTING_MIN <= value <= MAX_PRICE_CEILING:
        return Problem("max_price_out_of_range", {"min": MAX_PRICE_SETTING_MIN, "max": MAX_PRICE_CEILING})
    return None

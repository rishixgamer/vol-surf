from math import erf, erfc, exp, isfinite, log, log1p, pi, sqrt
from typing import Literal

OptionKind = Literal["call", "put"]
_SQRT_2 = sqrt(2.0)
_INV_SQRT_2PI = 1.0 / sqrt(2.0 * pi)


def _finite(value: float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


class _BlackQuote:
    def __init__(self, forward: float, strike: float, discount: float, kind: OptionKind):
        forward = _finite(forward, "forward")
        strike = _finite(strike, "strike")
        discount = _finite(discount, "discount")
        if forward <= 0.0 or strike <= 0.0 or discount <= 0.0:
            raise ValueError("forward, strike, and discount must be positive")
        if kind not in ("call", "put"):
            raise ValueError("kind must be 'call' or 'put'")

        prepaid_forward = forward * discount
        prepaid_strike = strike * discount
        self.small = min(prepaid_forward, prepaid_strike)
        self.large = max(prepaid_forward, prepaid_strike)
        if self.small == 0.0 or not isfinite(self.large):
            raise ValueError("discounted forward and strike must be positive and finite")

        difference = forward - strike
        self.spread = abs(difference) * discount
        self.intrinsic = discount * max(0.0, difference if kind == "call" else -difference)
        self.upper = prepaid_forward if kind == "call" else prepaid_strike

        larger, smaller = max(forward, strike), min(forward, strike)
        if abs(difference) <= smaller:
            self.distance = log1p(abs(difference) / smaller)
        else:
            ratio = larger / smaller
            self.distance = log(ratio) if isfinite(ratio) else log(larger) - log(smaller)

    def price(self, total_vol: float) -> float:
        if total_vol == 0.0:
            return self.intrinsic
        if not isfinite(total_vol):
            return self.upper

        # Price the out-of-the-money leg, then add discounted intrinsic value.
        if self.distance == 0.0 and total_vol >= 1e-5:
            time_value = self.small * erf(total_vol / (2.0 * _SQRT_2))
        else:
            m = -self.distance / total_vol
            a = (m + 0.5 * total_vol) / _SQRT_2
            b = (m - 0.5 * total_vol) / _SQRT_2
            lower_cdf = 0.5 * erfc(-b)
            if total_vol < 1e-5:
                # Integrate the density between close CDF arguments using the
                # midpoint and its second derivative, avoiding CDF subtraction.
                density = _INV_SQRT_2PI * exp(-0.5 * m * m)
                correction = 1.0 + (self.distance**2 - total_vol**2) / 24.0
                time_value = self.small * density * total_vol * correction - self.spread * lower_cdf
            elif abs(a) < 0.5 and abs(b) < 0.5:
                # Differencing erf near zero preserves small near-ATM premiums.
                time_value = self.small * (0.5 * (erf(a) - erf(b))) - self.spread * lower_cdf
            else:
                time_value = self.small * (0.5 * erfc(-a)) - self.large * lower_cdf

        return min(self.upper, self.intrinsic + max(0.0, time_value))


def black_price(
    forward: float,
    strike: float,
    expiry: float,
    volatility: float,
    *,
    discount: float = 1.0,
    kind: OptionKind = "call",
) -> float:
    """Price a European option using Black-76 and a supplied discount factor.

    Expiry is in years and volatility is annualized (0.20 means 20%). Zero
    expiry or zero volatility returns discounted intrinsic value.
    """
    expiry = _finite(expiry, "expiry")
    volatility = _finite(volatility, "volatility")
    if expiry < 0.0 or volatility < 0.0:
        raise ValueError("expiry and volatility must be nonnegative")
    quote = _BlackQuote(forward, strike, discount, kind)
    return quote.price(volatility * sqrt(expiry))


def implied_volatility(
    price: float,
    forward: float,
    strike: float,
    expiry: float,
    *,
    discount: float = 1.0,
    kind: OptionKind = "call",
) -> float:
    """Invert a discounted Black-76 price at a strictly positive expiry.

    The lower price bound implies zero volatility. Values outside the price
    bounds or at the upper bound raise ValueError.
    """
    price = _finite(price, "price")
    expiry = _finite(expiry, "expiry")
    if expiry <= 0.0:
        raise ValueError("expiry must be positive for implied volatility")
    quote = _BlackQuote(forward, strike, discount, kind)
    if price < quote.intrinsic or price >= quote.upper:
        raise ValueError(f"price must be in [{quote.intrinsic}, {quote.upper})")
    if price == quote.intrinsic:
        return 0.0

    # Bracket total volatility so the same solve works at any expiry.
    lower, upper = 0.0, 1.0
    while quote.price(upper) < price:
        lower, upper = upper, 2.0 * upper

    while True:
        middle = lower + 0.5 * (upper - lower)
        middle_price = quote.price(middle)
        if middle_price == price or upper - lower <= 1e-12 * middle:
            return middle / sqrt(expiry)
        if middle == lower or middle == upper:
            nearest = min((lower, upper), key=lambda value: abs(quote.price(value) - price))
            return nearest / sqrt(expiry)
        if middle_price < price:
            lower = middle
        else:
            upper = middle

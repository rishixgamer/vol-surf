from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from math import ulp

from ._black import _finite, black_price, implied_volatility

_PRICE_TOLERANCE = 16 * ulp(1.0)


def _axis(values: Sequence[float], name: str) -> tuple[float, ...]:
    axis = tuple(_finite(value, name) for value in values)
    if not axis or axis[0] <= 0.0 or any(a >= b for a, b in zip(axis, axis[1:])):
        raise ValueError(f"{name} must be nonempty, positive, and strictly increasing")
    return axis


def _grid(
    values: Sequence[Sequence[float]], rows: int, columns: int, name: str
) -> tuple[tuple[float, ...], ...]:
    grid = tuple(tuple(_finite(value, name) for value in row) for row in values)
    if len(grid) != rows or any(len(row) != columns for row in grid):
        raise ValueError(f"{name} must have one row per expiry and one column per strike ratio")
    return grid


def _linear(x: float, left: float, right: float, a: float, b: float) -> float:
    width = right - left
    if x - left <= right - x:
        return a + ((x - left) / width) * (b - a)
    return b + ((right - x) / width) * (a - b)


def _validate_calls(ratios: tuple[float, ...], calls: tuple[tuple[float, ...], ...]) -> None:
    strikes = (0.0, *ratios)
    for index, row in enumerate(calls):
        for strike, price in zip(ratios, row):
            if not max(0.0, 1.0 - strike) <= price < 1.0:
                raise ValueError(f"call price outside its bounds at expiry row {index}")

        prices = (1.0, *row)
        for left, right, a, b in zip(strikes, strikes[1:], prices, prices[1:]):
            if b > a + _PRICE_TOLERANCE or a - b > right - left + _PRICE_TOLERANCE:
                raise ValueError(f"call spread violates price bounds at expiry row {index}")

        for column in range(1, len(strikes) - 1):
            chord = _linear(
                strikes[column], strikes[column - 1], strikes[column + 1],
                prices[column - 1], prices[column + 1],
            )
            if prices[column] > chord + _PRICE_TOLERANCE:
                raise ValueError(f"call prices must be convex in strike at expiry row {index}")

    for index, (earlier, later) in enumerate(zip(calls, calls[1:])):
        if any(b + _PRICE_TOLERANCE < a for a, b in zip(earlier, later)):
            raise ValueError(f"call prices decrease in expiry between rows {index} and {index + 1}")


def _bracket(axis: Sequence[float], point: float, name: str) -> tuple[int, int]:
    if not axis[0] <= point <= axis[-1]:
        raise ValueError(f"{name} is outside the surface grid [{axis[0]}, {axis[-1]}]")
    right = bisect_left(axis, point)
    return (right, right) if axis[right] == point else (right - 1, right)


@dataclass(frozen=True, slots=True)
class VolSurface:
    """Immutable rectangular grid of normalized European call premiums.

    Axes contain positive, strictly increasing expiries in years and strike
    ratios K/F. Each premium is the call price divided by discount times
    forward, with one row per expiry. Queries interpolate only within the grid.
    """

    expiries: Sequence[float]
    strike_ratios: Sequence[float]
    normalized_calls: Sequence[Sequence[float]]

    def __post_init__(self) -> None:
        expiries = _axis(self.expiries, "expiries")
        ratios = _axis(self.strike_ratios, "strike ratios")
        calls = _grid(self.normalized_calls, len(expiries), len(ratios), "normalized calls")
        _validate_calls(ratios, calls)
        object.__setattr__(self, "expiries", expiries)
        object.__setattr__(self, "strike_ratios", ratios)
        object.__setattr__(self, "normalized_calls", calls)

    @classmethod
    def from_volatilities(
        cls,
        expiries: Sequence[float],
        strike_ratios: Sequence[float],
        volatilities: Sequence[Sequence[float]],
    ) -> "VolSurface":
        """Build a surface from annualized Black-76 volatility quotes."""
        times = _axis(expiries, "expiries")
        ratios = _axis(strike_ratios, "strike ratios")
        vols = _grid(volatilities, len(times), len(ratios), "volatilities")
        calls = tuple(
            tuple(black_price(1.0, ratio, expiry, vol) for ratio, vol in zip(ratios, row))
            for expiry, row in zip(times, vols)
        )
        return cls(times, ratios, calls)

    def normalized_call(self, expiry: float, strike_ratio: float) -> float:
        """Return the interpolated call premium divided by discount times forward."""
        expiry = _finite(expiry, "expiry")
        strike_ratio = _finite(strike_ratio, "strike ratio")
        first, last = _bracket(self.expiries, expiry, "expiry")
        left, right = _bracket(self.strike_ratios, strike_ratio, "strike ratio")

        def at_strike(row: Sequence[float]) -> float:
            if left == right:
                return row[left]
            return _linear(
                strike_ratio, self.strike_ratios[left], self.strike_ratios[right],
                row[left], row[right],
            )

        call = at_strike(self.normalized_calls[first])
        if first != last:
            call = _linear(
                expiry, self.expiries[first], self.expiries[last], call,
                at_strike(self.normalized_calls[last]),
            )
        return max(call, 0.0, 1.0 - strike_ratio)

    def implied_volatility(self, expiry: float, strike_ratio: float) -> float:
        """Return the annualized Black-76 volatility at an in-grid point."""
        call = self.normalized_call(expiry, strike_ratio)
        return implied_volatility(call, 1.0, strike_ratio, expiry)

# vol-surf

A Python library for Black-76 pricing and implied volatility for European options.
It interpolates normalized call prices on a strike and expiry grid and checks
strike convexity and calendar spreads under the carry assumptions below.

[Price an option](#price-and-invert-an-option) · [Build a surface](#build-and-query-a-surface) · [Run the tests](#verify-a-checkout)

The `1.0.0rc1` candidate uses Python 3.11 or later and the standard library.

## Install from a checkout

```sh
python -m pip install .
```

## Price and invert an option

```python
from vol_surf import black_price, implied_volatility

premium = black_price(103.0, 97.0, 0.7, 0.31, discount=0.96, kind="put")
iv = implied_volatility(premium, 103.0, 97.0, 0.7, discount=0.96, kind="put")
# premium ≈ 7.287949 and iv ≈ 0.31
```

Supply the forward and strike in the same currency, the time to expiry in years,
and the annualized volatility as a decimal. The discount factor is applied once,
defaults to `1.0`, and may exceed one. `kind` defaults to `"call"`.

Both functions require finite inputs and positive forwards, strikes, and discount
factors whose discounted forward and strike are representable as positive finite
floats. Zero volatility or expiry gives discounted intrinsic value. Implied
volatility requires positive expiry, returns zero at the lower price bound, and
raises `ValueError` below that bound or at and above the upper bound. For calls
the upper bound is discounted forward, and for puts it is discounted strike.
Near either bound, floating-point rounding can erase time value or make multiple
volatilities reprice to the same premium. With extreme inputs, a normal tail can
underflow before the premium is scaled. Prefer an out-of-the-money premium when
inverting a quote with little time value. The formula follows [Black (1976)](https://doi.org/10.1016/0304-405X(76)90024-6).

## Build and query a surface

```python
from vol_surf import VolSurface

surface = VolSurface.from_volatilities(
    expiries=[0.25, 1.0],
    strike_ratios=[0.8, 1.0, 1.2],
    volatilities=[[0.20, 0.20, 0.20], [0.20, 0.20, 0.20]],
)
forward, strike, discount = 110.0, 115.5, 0.98
ratio = strike / forward
call = discount * forward * surface.normalized_call(0.5, ratio)
iv = surface.implied_volatility(0.5, ratio)
```

Use `VolSurface(expiries, strike_ratios, normalized_calls)` for price data. Divide
each discounted call premium by its row's `discount * forward` and express
strikes as `K / F` on a common grid. Supply nonempty, finite, positive, strictly
increasing axes and one row per expiry. The surface copies its input to immutable
tuples and rejects queries outside either axis.

At each expiry, the normalized calls must lie within their price bounds, decrease
or stay flat in strike, and be convex with strike slopes in `[-1, 0]`. The shape
check includes the zero-strike boundary value of one. At fixed `K / F`, call
premiums must be nondecreasing with expiry. Spread, convexity, and calendar
checks allow an absolute premium tolerance of about `3.6e-15` for roundoff.
Nonnegative premiums within that tolerance below intrinsic are set to intrinsic.

Interpolation is piecewise linear in strike ratio and expiry in normalized
premium space, so it preserves these local shape conditions in exact arithmetic
for slices that meet them. Implied volatility is recovered from the resulting
premium. The calendar interpretation assumes the same underlying and a carry
model under which the forward-normalized underlying is a martingale, such as
deterministic rates with proportional dividends. This API provides in-grid
interpolation and validation. Global wing behavior, smooth Greeks, fitting
irregular market quotes, and American exercise are outside its scope. See
[Gatheral and Jacquier, §2](https://arxiv.org/abs/1204.0646) for the calendar and
butterfly conditions.

## Verify a checkout

```sh
python -m pip install .
python -m unittest discover -s tests -v
```

Build and publication criteria are in the [release checklist](https://github.com/rishixgamer/vol-surf/blob/main/RELEASING.md).

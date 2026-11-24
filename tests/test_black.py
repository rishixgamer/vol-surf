import math
import unittest

from vol_surf import black_price, implied_volatility


class BlackTests(unittest.TestCase):
    def test_prices_against_high_precision_black_references(self):
        # Evaluated independently with 100-digit normal CDFs.
        cases = (
            (100, 100, 1, 0.20, 1.00, 7.965567455405796, 7.965567455405796),
            (103, 97, 0.7, 0.31, 0.96, 13.047949151742056, 7.287949151742056),
            (80, 115, 0.25, 0.28, 1.01, 0.020312145201428265, 35.37031214520143),
            (100, 160, 0.1, 0.20, 0.99, 5.532112645802601e-14, 59.400000000000055),
            (1, math.nextafter(1.0, math.inf), 1, 3e-16, 1, 4.002424324140119e-17,
             2.620688481664325e-16),
        )
        for forward, strike, expiry, vol, discount, call, put in cases:
            for kind, expected in (("call", call), ("put", put)):
                with self.subTest(forward=forward, strike=strike, vol=vol, kind=kind):
                    actual = black_price(forward, strike, expiry, vol, discount=discount, kind=kind)
                    self.assertTrue(math.isclose(actual, expected, rel_tol=2e-10), (actual, expected))

    def test_call_put_parity_and_monotonic_volatility(self):
        for strike in (40, 85, 100, 125, 250):
            calls = []
            for vol in (0.0, 0.1, 0.25, 0.75, 2.0):
                call = black_price(100, strike, 1.5, vol, discount=0.94)
                put = black_price(100, strike, 1.5, vol, discount=0.94, kind="put")
                self.assertAlmostEqual(call - put, 0.94 * (100 - strike), places=12)
                calls.append(call)
            self.assertEqual(calls, sorted(calls))

    def test_implied_volatility_round_trips(self):
        cases = (
            (100, 100, 1e-10, 1e-8),
            (1, math.nextafter(1.0, math.inf), 1, 3e-16),
            (100, 160, 0.1, 0.20),
            (100, 70, 0.3, 0.65),
            (100, 125, 3, 0.30),
            (100, 100, 0.1, 12.0),
        )
        for forward, strike, expiry, vol in cases:
            for kind in ("call", "put"):
                with self.subTest(strike=strike, expiry=expiry, vol=vol, kind=kind):
                    options = {"discount": 0.97, "kind": kind}
                    price = black_price(forward, strike, expiry, vol, **options)
                    actual = implied_volatility(price, forward, strike, expiry, **options)
                    if strike == 160 and kind == "put":
                        # The ITM price rounds away a large fraction of its time value.
                        self.assertEqual(black_price(forward, strike, expiry, actual, **options), price)
                    else:
                        self.assertTrue(math.isclose(actual, vol, rel_tol=5e-11), (actual, vol))

    def test_zero_expiry_and_zero_volatility(self):
        for expiry, vol in ((0, 0.2), (1, 0)):
            self.assertEqual(black_price(110, 100, expiry, vol, discount=0.9), 9)
            self.assertEqual(black_price(110, 100, expiry, vol, discount=0.9, kind="put"), 0)
        self.assertEqual(implied_volatility(9, 110, 100, 1, discount=0.9), 0)
        self.assertEqual(implied_volatility(0, 110, 100, 1, discount=0.9, kind="put"), 0)

    def test_price_just_below_upper_bound(self):
        target = math.nextafter(100.0, 0.0)
        vol = implied_volatility(target, 100, 100, 1)
        self.assertTrue(math.isfinite(vol))
        self.assertEqual(black_price(100, 100, 1, vol), target)

    def test_discounted_in_the_money_price_just_below_upper_bound(self):
        forward, strike, discount = 157.7891578116566, 7.532734790777497, 0.7642904730174174
        price = math.nextafter(forward * discount, 0.0)
        for f, k, kind in ((forward, strike, "call"), (strike, forward, "put")):
            with self.subTest(kind=kind):
                iv = implied_volatility(price, f, k, 1, discount=discount, kind=kind)
                self.assertTrue(math.isfinite(iv))
                self.assertEqual(black_price(f, k, 1, iv, discount=discount, kind=kind), price)

    def test_tiny_at_the_money_volatility_with_representable_price(self):
        vol = math.ulp(0.0)
        price = black_price(1e300, 1e300, 1, vol)
        self.assertTrue(math.isclose(price, 1.9710367541991352e-24, rel_tol=1e-14))
        self.assertEqual(implied_volatility(price, 1e300, 1e300, 1), vol)

    def test_invalid_price_or_expiry(self):
        for price in (9.99, 110, 115, math.nan, math.inf):
            with self.subTest(price=price), self.assertRaises(ValueError):
                implied_volatility(price, 110, 100, 1)
        with self.assertRaisesRegex(ValueError, "expiry must be positive"):
            implied_volatility(10, 110, 100, 0)
        with self.assertRaisesRegex(ValueError, "price must be in"):
            implied_volatility(85, 100, 85, 1, kind="put")

    def test_invalid_pricing_inputs(self):
        cases = (
            (0, 100, 1, 0.2), (100, -1, 1, 0.2), (100, 100, -1, 0.2),
            (100, 100, 1, -0.2), (100, math.nan, 1, 0.2), (100, 100, math.inf, 0.2),
            (100, 100, 1, math.inf), (10**400, 100, 1, 0.2),
        )
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                black_price(*args)
        with self.assertRaisesRegex(ValueError, "discounted forward and strike"):
            black_price(1e308, 100, 1, 0.2, discount=2)
        with self.assertRaisesRegex(ValueError, "must be positive"):
            black_price(100, 100, 1, 0.2, discount=0)
        with self.assertRaisesRegex(ValueError, "kind"):
            black_price(100, 100, 1, 0.2, kind="CALL")

import math
import unittest
from dataclasses import FrozenInstanceError

from vol_surf import VolSurface, black_price


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.expiries = [0.25, 0.5, 1.0]
        self.ratios = [0.8, 1.0, 1.2, 1.3]
        self.surface = VolSurface.from_volatilities(self.expiries, self.ratios, [[0.2] * 4] * 3)

    def test_exact_premiums_and_implied_vols_at_all_nodes(self):
        for expiry in self.expiries:
            for ratio in self.ratios:
                with self.subTest(expiry=expiry, ratio=ratio):
                    self.assertEqual(self.surface.normalized_call(expiry, ratio),
                                     black_price(1.0, ratio, expiry, 0.2))
                    self.assertAlmostEqual(self.surface.implied_volatility(expiry, ratio), 0.2, places=10)

    def test_bilinear_premium_and_iv_off_grid(self):
        surface = VolSurface([0.25, 1.25], [0.8, 1.2], [[0.28, 0.03], [0.34, 0.07]])
        expected = 0.75 * (0.75 * 0.28 + 0.25 * 0.03) + 0.25 * (0.75 * 0.34 + 0.25 * 0.07)
        call = surface.normalized_call(0.5, 0.9)
        self.assertAlmostEqual(call, expected, places=15)
        self.assertAlmostEqual(black_price(1.0, 0.9, 0.5, surface.implied_volatility(0.5, 0.9)),
                               expected, places=12)

    def test_interpolation_preserves_local_shape(self):
        # Use a dense grid crossing each original strike and expiry knot.
        times = [0.25 + i * 0.75 / 20 for i in range(21)]
        ratios = [0.8 + i * 0.5 / 20 for i in range(21)]
        calls = [[self.surface.normalized_call(t, k) for k in ratios] for t in times]
        for row in calls:
            slopes = [(b - a) / (r - l) for l, r, a, b in zip(ratios, ratios[1:], row, row[1:])]
            self.assertTrue(all(-1 - 1e-12 <= slope <= 1e-12 for slope in slopes))
            self.assertTrue(all(b >= a - 1e-12 for a, b in zip(slopes, slopes[1:])))
        for earlier, later in zip(calls, calls[1:]):
            self.assertTrue(all(b >= a for a, b in zip(earlier, later)))

    def test_single_node_and_immutable_inputs(self):
        times, ratios, calls = [1.0], [1.0], [[0.0]]
        surface = VolSurface(times, ratios, calls)
        times[0], ratios[0], calls[0][0] = 2.0, 2.0, 0.5
        self.assertEqual(surface.normalized_call(1.0, 1.0), 0)
        self.assertEqual(surface.implied_volatility(1.0, 1.0), 0)
        with self.assertRaises(FrozenInstanceError):
            surface.expiries = [2.0]

    def test_rejects_extrapolation_and_nonfinite_queries(self):
        for expiry, ratio in ((0.24, 1), (1.01, 1), (0.5, 0.79), (0.5, 1.31)):
            with self.subTest(expiry=expiry, ratio=ratio), self.assertRaisesRegex(ValueError, "outside"):
                self.surface.normalized_call(expiry, ratio)
        with self.assertRaisesRegex(ValueError, "finite"):
            self.surface.implied_volatility(0.5, math.nan)

    def test_rejects_bounds_vertical_butterfly_and_calendar_violations(self):
        cases = (
            ([1], [0.8], [[0.1]], "outside its bounds"),
            ([1], [1.0], [[1.0]], "outside its bounds"),
            ([1], [1.0, 1.2], [[0.12, 0.13]], "call spread"),
            ([1], [1.0, 1.2], [[0.3, 0.07]], "call spread"),
            ([1], [1.0, 1.2, 1.4], [[0.3, 0.22, 0.06]], "convex"),
            ([1], [0.9, 1.0], [[0.3, 0.21]], "convex"),
            ([1, 2], [1.0], [[0.2], [0.1]], "decrease in expiry"),
        )
        for times, ratios, prices, message in cases:
            with self.subTest(times=times, ratios=ratios, prices=prices):
                with self.assertRaisesRegex(ValueError, message):
                    VolSurface(times, ratios, prices)

    def test_rejects_bad_axes_and_grid_shape(self):
        cases = (([], [1], []), ([0], [1], [[0.1]]), ([1], [0], [[0.1]]),
                 ([1, 1], [1], [[0.1], [0.2]]), ([1], [1.2, 1], [[0.1, 0.2]]),
                 ([1], [1], [[math.nan]]), ([1, 2], [1], [[0.1]]), ([1], [1, 2], [[0.1]]))
        for times, ratios, prices in cases:
            with self.subTest(times=times, ratios=ratios, prices=prices), self.assertRaises(ValueError):
                VolSurface(times, ratios, prices)
        with self.assertRaisesRegex(ValueError, "volatility must be nonnegative"):
            VolSurface.from_volatilities([1], [1], [[-0.2]])
        with self.assertRaisesRegex(ValueError, "one row per expiry"):
            VolSurface.from_volatilities([1, 2], [1], [[0.2]])

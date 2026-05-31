from __future__ import annotations

import unittest

from src.report import calculate_page_cvr, find_improvement_candidates


class ReportCalculationTests(unittest.TestCase):
    def test_calculate_page_cvr_uses_downloads_over_product_page_views(self) -> None:
        self.assertEqual(calculate_page_cvr(downloads=0, product_page_views=100), 0.0)
        self.assertEqual(calculate_page_cvr(downloads=10, product_page_views=0), 0.0)
        self.assertAlmostEqual(calculate_page_cvr(downloads=12, product_page_views=150), 0.08)

    def test_find_improvement_candidates_filters_and_sorts_by_score(self) -> None:
        current = {
            "low_views": {
                "name": "Low Views",
                "sku": "low_views",
                "product_page_views": 39,
                "downloads": 1,
                "conversion_rate": 0.02,
            },
            "good_cvr": {
                "name": "Good CVR",
                "sku": "good_cvr",
                "product_page_views": 200,
                "downloads": 30,
                "conversion_rate": 0.15,
            },
            "needs_work": {
                "name": "Needs Work",
                "sku": "needs_work",
                "product_page_views": 100,
                "downloads": 3,
                "conversion_rate": 0.03,
            },
            "bigger_opportunity": {
                "name": "Bigger Opportunity",
                "sku": "bigger_opportunity",
                "product_page_views": 300,
                "downloads": 18,
                "conversion_rate": 0.06,
            },
        }

        candidates = find_improvement_candidates(current)

        self.assertEqual([row["sku"] for row in candidates], ["bigger_opportunity", "needs_work"])
        self.assertAlmostEqual(candidates[0]["improvement_score"], 12.0)
        self.assertAlmostEqual(candidates[1]["improvement_score"], 7.0)


if __name__ == "__main__":
    unittest.main()

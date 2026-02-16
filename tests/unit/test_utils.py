from types import SimpleNamespace

from app.models import ItemCategory
from app.utils import compute_category_density


class TestComputeCategoryDensity:
    def test_basic_distribution(self):
        rows = [
            SimpleNamespace(category=ItemCategory.electronics, count=5),
            SimpleNamespace(category=ItemCategory.books, count=3),
            SimpleNamespace(category=ItemCategory.food, count=2),
        ]
        result = compute_category_density(rows)

        assert result.success is True
        assert result.data.total_items == 10
        assert len(result.data.categories) == 3

        elec = next(c for c in result.data.categories if c.category == "electronics")
        assert elec.count == 5
        assert elec.percentage == 50.0

        books = next(c for c in result.data.categories if c.category == "books")
        assert books.count == 3
        assert books.percentage == 30.0

    def test_empty_list(self):
        result = compute_category_density([])

        assert result.success is True
        assert result.data.total_items == 0
        assert result.data.categories == []

    def test_none_category_becomes_uncategorized(self):
        rows = [SimpleNamespace(category=None, count=4)]
        result = compute_category_density(rows)

        assert result.data.categories[0].category == "uncategorized"
        assert result.data.categories[0].percentage == 100.0

    def test_single_category(self):
        rows = [SimpleNamespace(category=ItemCategory.clothing, count=7)]
        result = compute_category_density(rows)

        assert result.data.total_items == 7
        assert len(result.data.categories) == 1
        assert result.data.categories[0].percentage == 100.0

    def test_rounding(self):
        rows = [
            SimpleNamespace(category=ItemCategory.electronics, count=1),
            SimpleNamespace(category=ItemCategory.books, count=2),
        ]
        result = compute_category_density(rows)

        elec = next(c for c in result.data.categories if c.category == "electronics")
        assert elec.percentage == 33.3  # round(1/3 * 100, 1)

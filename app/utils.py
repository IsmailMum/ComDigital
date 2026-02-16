from app.models import (
    CategoryDensityResponse, CategoryDensityData, CategoryDensityItem,
)


def compute_category_density(items) -> CategoryDensityResponse:

    total_items = sum(row.count for row in items)

    categories = [
        CategoryDensityItem(
            category=row.category.value if row.category else "uncategorized",
            count=row.count,
            percentage=round((row.count / total_items) * 100, 1) if total_items > 0 else 0.0,
        )
        for row in items
    ]

    return CategoryDensityResponse(
        success=True,
        data=CategoryDensityData(
            total_items=total_items,
            categories=categories,
        ),
    )

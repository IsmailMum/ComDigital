from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.exception_handlers import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from app.core.exceptions import AppException


@pytest.fixture
def mock_request():
    return MagicMock()


class TestAppExceptionHandler:
    @pytest.mark.asyncio
    async def test_returns_structured_error(self, mock_request):
        exc = AppException(
            status_code=400,
            error="TEST_ERROR",
            message="Something went wrong",
            details={"field": "value"},
        )
        response = await app_exception_handler(mock_request, exc)
        assert response.status_code == 400
        assert response.body is not None

    @pytest.mark.asyncio
    async def test_without_details(self, mock_request):
        exc = AppException(status_code=403, error="FORBIDDEN", message="No access")
        response = await app_exception_handler(mock_request, exc)
        assert response.status_code == 403


class TestHttpExceptionHandler:
    @pytest.mark.asyncio
    async def test_returns_structured_error(self, mock_request):
        exc = HTTPException(status_code=401, detail="Not authenticated")
        response = await http_exception_handler(mock_request, exc)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_handles_empty_detail(self, mock_request):
        exc = HTTPException(status_code=500, detail=None)
        response = await http_exception_handler(mock_request, exc)
        assert response.status_code == 500


class TestGenericExceptionHandler:
    @pytest.mark.asyncio
    async def test_returns_500(self, mock_request):
        exc = RuntimeError("unexpected crash")
        response = await generic_exception_handler(mock_request, exc)
        assert response.status_code == 500

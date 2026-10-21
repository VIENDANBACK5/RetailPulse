"""Warehouse-backed portal API; no sample-data fallback."""
import logging
from datetime import date
from typing import Optional, Literal
from functools import wraps

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from app.services.analytics import Analytics, warehouse_engine

router = APIRouter(prefix="/analytics")
analytics = Analytics(warehouse_engine())


def available(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except SQLAlchemyError:
            logging.exception("Warehouse analytics unavailable")
            raise HTTPException(503, "Chưa đọc được warehouse. Kiểm tra dịch vụ DWH và chạy scripts/prepare_dashboard.py.")
    return wrapped


@router.get("/meta")
@available
def meta():
    return analytics.meta()


@router.get("/sales")
@available
def sales(currency: Literal["GBP", "VND", "USD", "EUR"] = "GBP",
          source: Optional[str] = Query(None, max_length=50),
          branch: Optional[str] = Query(None, max_length=30),
          start: Optional[date] = None, end: Optional[date] = None):
    if start and end and start > end:
        raise HTTPException(422, "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
    return analytics.sales(currency, source, branch, start, end)


@router.get("/inventory")
@available
def inventory(branch: Optional[str] = Query(None, max_length=30),
              health: Optional[Literal["low", "healthy", "offline", "unknown"]] = None,
              search: str = Query("", max_length=100), page: int = Query(1, ge=1),
              page_size: int = Query(20, ge=1, le=100)):
    return analytics.inventory(branch, health, search, page, page_size)


@router.get("/customers")
@available
def customers(cluster: Optional[int] = Query(None, ge=0), search: str = Query("", max_length=100),
              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return analytics.customers(cluster, search, page, page_size)


@router.get("/status")
@available
def status():
    return analytics.status()

"""Same-origin gateway to the read-only Analytics service, not arbitrary URLs."""
import os
from typing import Literal
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix='/api/reports', tags=['Read-only portal reports'])


@router.get('/{endpoint}')
def report(endpoint: Literal['meta', 'sales', 'inventory', 'customers', 'status'], request: Request):
    upstream = os.getenv('REPORTS_API_URL', 'http://127.0.0.1:8001/api/v1/analytics').rstrip('/')
    try:
        response = httpx.get(upstream + '/' + endpoint, params=list(request.query_params.multi_items()), timeout=35)
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, 'Analytics chưa sẵn sàng. Kiểm tra API nguồn và Warehouse trong trạng thái hệ thống.') from exc
    return JSONResponse(data, status_code=response.status_code)

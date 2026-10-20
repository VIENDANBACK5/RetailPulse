@echo off
chcp 65001 > nul
cls
echo ===============================================================================
echo   HOC VIEN CONG NGHE BUU CHINH VIEN THONG (PTIT)
echo   TRIEN KHAI HE THONG DATA WAREHOUSE & DATA MINING VOI DOCKER COMPOSE
echo ===============================================================================
echo.

echo [1/4] Khoi dong cac containers: CSDL Tac nghiep, Data Warehouse va FastAPI App...
docker compose up -d oltp-db dwh-db app
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong the khoi dong Docker. Vui long kiem tra Docker Desktop da bat chua!
    pause
    exit /b %ERRORLEVEL%
)
echo.

echo [2/4] Doi 5 giay de PostgreSQL khoi tao xong co so du lieu...
timeout /t 5 /nobreak > nul

echo.
echo [3/4] Nap du lieu ban dau (Branches, Products, Stock) vao App Container...
docker compose exec app python seed_data.py
echo.

echo [4/4] Chay Duong ong ETL va Khai pha du lieu qua Container Runner...
docker compose run --rm pipeline python src/etl/pipeline.py
docker compose run --rm pipeline python src/mining/pipeline.py --k 4
echo.

echo ===============================================================================
echo   HE THONG DOCKER DA SAN SANG VA HOAT DONG!
echo.
echo   - FastAPI App & Swagger UI : http://localhost:8001/docs
echo   - CSDL Tac nghiep (OLTP)   : localhost:5432 / Database: retail_app_db
echo   - Data Warehouse (DWH)     : localhost:5433 / Database: retail_dwh_db
echo.
echo   * Dashboard: http://localhost:8001/frontend/dashboard.html
echo   * Chuan bi SQL views: docker compose run --rm pipeline python scripts/prepare_dashboard.py
echo.
echo   * Xem them giao dien pgAdmin (tuy chon):
echo     docker compose --profile tools up -d pgadmin
echo     Truy cap: http://localhost:5050 (admin@ptit.edu.vn / admin)
echo ===============================================================================
pause

@echo off
chcp 65001 > nul
cls
echo ===============================================================================
echo   HOC VIEN CONG NGHE BUU CHINH VIEN THONG (PTIT)
echo   BAI TAP LON: KHO DU LIEU VA KHAI PHA DU LIEU
echo   DE TAI: XAY DUNG KHO DU LIEU BAN HANG VA PHAN CUM KHACH HANG (RFM & K-MEANS)
echo ===============================================================================
echo.

set PYTHONPATH=%CD%

echo [1/4] Chuan bi thu muc Data Lake va Du lieu Online Retail II (UCI)...
python src/utils/data_downloader.py
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong the chuan bi du lieu nguon.
    pause
    exit /b %ERRORLEVEL%
)
echo.

echo [2/4] Khoi chay Duong ong ETL Da nguon (File, DB, API)...
python src/etl/pipeline.py --sources uci app api
if %ERRORLEVEL% NEQ 0 (
    echo [CANH BAO] ETL co the dang chay o che do offline/fallback.
)
echo.

echo [3/4] Khoi chay Pipeline Khai pha Du lieu (RFM Extraction + Thuc nghiem K=2..6 + K-Means)...
python src/mining/pipeline.py
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong the thuc thi pipeline khai pha du lieu.
    pause
    exit /b %ERRORLEVEL%
)
echo.

echo [4/4] Kiem thu kich ban Chịu loi Node API chi nhanh...
python scripts/test_fault_node.py
echo.

echo ===============================================================================
echo   HOAN TAT TOAN BO TIEN TRINH THUC THI HE THONG!
echo.
echo   - Mo Swagger API: cd fastapi-base ^&^& uvicorn app.main:app --reload
echo   - Xem Bieu do K-Means: models/elbow_silhouette_evaluation.png
echo   - Ket qua Phan cum: models/customer_segments_*.csv
echo   - Mo file Bao cao Power BI trong thu muc bi/
echo ===============================================================================
pause

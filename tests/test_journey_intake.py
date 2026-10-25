"""Actual HTTP/file intake checks; isolated temp files, no mocked ETL success."""
import hashlib
import io
import json
from pathlib import Path
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import src.web.journey as journey

CSV = b'Invoice,StockCode,Quantity,InvoiceDate,Price,Customer ID,Country\nDJ-TEST,DJ-SKU,2,2011-01-01,5,DJ-CUSTOMER,DEMO\n'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(journey, 'ROOT', tmp_path)
    monkeypatch.setattr(journey, 'RAW', tmp_path/'data_lake/raw')
    app = FastAPI()
    app.include_router(journey.router)
    return TestClient(app), tmp_path


def test_upload_is_real_file_with_preview_checksum_and_unverified_label(client):
    http, root = client
    response = http.post('/api/journey/files?filename=demo.csv', content=CSV)
    assert response.status_code == 201
    result = response.json()
    assert result['provenance'] == 'UNVERIFIED' and result['currency'] == 'GBP'
    assert result['intake_only'] is True
    assert result['checksum'] == hashlib.sha256(CSV).hexdigest()
    path = root/result['file_path']
    assert path.read_bytes() == CSV
    assert result['preview']['rows'][0]['Invoice'] == 'DJ-TEST'
    metadata = json.loads(path.with_suffix('.csv.provenance.json').read_text(encoding='utf-8'))
    assert metadata['checksum'] == result['checksum']
    downloaded = http.get('/api/journey/download', params={'path': result['file_path']})
    assert downloaded.content == CSV


@pytest.mark.parametrize('filename,body,code', [('bad.exe',CSV,415),('empty.csv',b'',422),('wrong.csv',b'a,b\n1,2\n',422)])
def test_invalid_files_not_accepted_as_valid_sources(client, filename, body, code):
    http, root = client
    assert http.post('/api/journey/files', params={'filename':filename}, content=body).status_code == code
    assert not list(root.rglob('source.*'))


def test_file_limit_checked_while_streaming(client, monkeypatch):
    http, root = client
    monkeypatch.setattr(journey, 'MAX_UPLOAD', 10)
    assert http.post('/api/journey/files?filename=large.csv',content=CSV).status_code == 413
    assert not list(root.rglob('source.*'))


def test_same_filename_never_overwrites_original(client):
    http, root = client
    first=http.post('/api/journey/files?filename=demo.csv',content=CSV).json()
    second=http.post('/api/journey/files?filename=demo.csv',content=CSV).json()
    assert first['file_path'] != second['file_path']
    assert (root/first['file_path']).read_bytes() == (root/second['file_path']).read_bytes() == CSV


def test_excel_preview_and_filename_traversal_cannot_escape_raw(client):
    http, root = client
    stream=io.BytesIO()
    pd.read_csv(io.BytesIO(CSV)).to_excel(stream,index=False)
    response=http.post('/api/journey/files',params={'filename':'../../demo.xlsx'},content=stream.getvalue())
    assert response.status_code == 201
    uploaded=response.json()
    assert uploaded['original_filename'] == 'demo.xlsx'
    assert (root/uploaded['file_path']).resolve().is_relative_to((root/'data_lake/raw').resolve())
    assert uploaded['preview']['rows'][0]['StockCode'] == 'DJ-SKU'


def test_raw_download_cannot_escape_root(client):
    http, root = client
    (root/'secret.env').write_text('private',encoding='utf-8')
    assert http.get('/api/journey/download?path=secret.env').status_code == 404
    assert http.get('/api/journey/download?path=../secret.env').status_code == 404

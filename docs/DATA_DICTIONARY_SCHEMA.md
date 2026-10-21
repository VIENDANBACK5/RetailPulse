# Ph? l?c schema th?c t? PostgreSQL

Sinh b?ng SQLAlchemy Inspector ng?y 21/10/2026. ??y l? c?u tr?c DB ?? ch?y, kh?ng ph?i ERD d? ki?n. ??nh ngh?a nghi?p v?, grain v? null semantics xem DATA_DICTIONARY.md.

## dim_date

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| date_key | INTEGER | False | PK  |  |
| full_date | DATE | False |  |  |
| day_of_week | INTEGER | False |  |  |
| day_name | VARCHAR(20) | False |  |  |
| day_of_month | INTEGER | False |  |  |
| month | INTEGER | False |  |  |
| month_name | VARCHAR(20) | False |  |  |
| quarter | INTEGER | False |  |  |
| year | INTEGER | False |  |  |
| is_weekend | BOOLEAN | False |  | false |
| is_holiday | BOOLEAN | False |  | false |

UNIQUE: full_date.

## dim_customer

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| customer_key | INTEGER | False | PK  | nextval('dim_customer_customer_key_seq'::regclass) |
| source_key | INTEGER | False | dim_source.source_key |  |
| customer_code | VARCHAR(100) | False |  |  |
| customer_name | VARCHAR(255) | True |  |  |
| country | VARCHAR(100) | True |  | 'Vietnam'::character varying |

UNIQUE: source_key, customer_code.

## dim_product

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| product_key | INTEGER | False | PK  | nextval('dim_product_product_key_seq'::regclass) |
| source_key | INTEGER | False | dim_source.source_key |  |
| stock_code | VARCHAR(100) | False |  |  |
| description | VARCHAR(255) | False |  |  |
| category | VARCHAR(100) | True |  |  |
| unit_price_base | NUMERIC(20, 4) | True |  | 0.0 |

UNIQUE: source_key, stock_code.

## dim_branch

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| branch_key | INTEGER | False | PK  | nextval('dim_branch_branch_key_seq'::regclass) |
| branch_code | VARCHAR(50) | False |  |  |
| branch_name | VARCHAR(255) | False |  |  |
| location | VARCHAR(255) | True |  |  |

UNIQUE: branch_code.

## dim_source

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| source_key | INTEGER | False | PK  | nextval('dim_source_source_key_seq'::regclass) |
| source_code | VARCHAR(50) | False |  |  |
| source_name | VARCHAR(255) | False |  |  |
| currency | VARCHAR(10) | False |  |  |

UNIQUE: source_code.

## fact_sales

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| sales_key | BIGINT | False | PK  | nextval('fact_sales_sales_key_seq'::regclass) |
| date_key | INTEGER | False | dim_date.date_key |  |
| customer_key | INTEGER | False | dim_customer.customer_key |  |
| product_key | INTEGER | False | dim_product.product_key |  |
| branch_key | INTEGER | False | dim_branch.branch_key |  |
| source_key | INTEGER | False | dim_source.source_key |  |
| invoice_no | VARCHAR(100) | False |  |  |
| quantity | INTEGER | False |  |  |
| unit_price | NUMERIC(20, 4) | False |  |  |
| total_amount | NUMERIC(20, 4) | False |  |  |
| is_cancelled | BOOLEAN | False |  | false |
| record_hash | VARCHAR(64) | False |  |  |
| batch_id | VARCHAR(100) | False |  |  |
| loaded_at | TIMESTAMP | True |  | now() |
| source_record_id | TEXT | True |  |  |
| raw_path | TEXT | True |  |  |
| provenance | TEXT | True |  |  |
| currency | VARCHAR(10) | True |  |  |
| transaction_type | VARCHAR(20) | True |  |  |
| content_hash | VARCHAR(64) | True |  |  |
| run_id | TEXT | True |  |  |
| updated_at | TIMESTAMP | True |  | now() |

UNIQUE: record_hash.

## fact_inventory_snapshot

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| snapshot_key | BIGINT | False | PK  | nextval('fact_inventory_snapshot_snapshot_key_seq'::regclass) |
| date_key | INTEGER | False | dim_date.date_key |  |
| branch_key | INTEGER | False | dim_branch.branch_key |  |
| product_key | INTEGER | False | dim_product.product_key |  |
| source_key | INTEGER | False | dim_source.source_key |  |
| stock_on_hand | INTEGER | True |  |  |
| snapshot_time | TIMESTAMP | True |  |  |
| node_status | VARCHAR(50) | True |  | 'ONLINE'::character varying |
| batch_id | VARCHAR(100) | False |  |  |
| loaded_at | TIMESTAMP | True |  | now() |
| raw_path | TEXT | True |  |  |
| run_id | TEXT | True |  |  |
| snapshot_identity | TEXT | True |  |  |

UNIQUE: date_key, branch_key, product_key, batch_id.

## customer_segment_snapshot

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| segment_key | BIGINT | False | PK  | nextval('customer_segment_snapshot_segment_key_seq'::regclass) |
| analysis_date | DATE | False |  |  |
| customer_key | INTEGER | False | dim_customer.customer_key |  |
| recency | DOUBLE PRECISION | False |  |  |
| frequency | INTEGER | False |  |  |
| monetary | NUMERIC(20, 4) | False |  |  |
| cluster_id | INTEGER | False |  |  |
| cluster_name | VARCHAR(100) | False |  |  |
| model_version | VARCHAR(160) | False |  |  |
| created_at | TIMESTAMP | True |  | now() |
| window_start | DATE | True |  |  |
| window_end | DATE | True |  |  |
| run_id | TEXT | True |  |  |
| source_code | VARCHAR(50) | True |  |  |
| currency | VARCHAR(10) | True |  |  |

UNIQUE: analysis_date, customer_key, model_version.

## source_manifest

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| manifest_id | BIGINT | False | PK  | nextval('source_manifest_manifest_id_seq'::regclass) |
| run_id | TEXT | False |  |  |
| batch_id | TEXT | False |  |  |
| source_code | TEXT | False |  |  |
| status | TEXT | False |  |  |
| provenance | TEXT | False |  |  |
| raw_path | TEXT | True |  |  |
| checksum | TEXT | True |  |  |
| record_count | INTEGER | True |  |  |
| currency | TEXT | True |  |  |
| collected_at | TIMESTAMP | False |  | now() |
| metadata | JSONB | False |  | '{}'::jsonb |


## inventory_source_status

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| id | BIGINT | False | PK  | nextval('inventory_source_status_id_seq'::regclass) |
| run_id | TEXT | False |  |  |
| batch_id | TEXT | False |  |  |
| source_code | TEXT | False |  | 'APP_OPERATIONAL'::text |
| branch_code | TEXT | False |  |  |
| status | TEXT | False |  |  |
| snapshot_time | TIMESTAMP | True |  |  |
| collected_at | TIMESTAMP | False |  | now() |
| error | TEXT | True |  |  |
| raw_path | TEXT | True |  |  |
| item_count | INTEGER | False |  | 0 |


## etl_batch_records

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| batch_id | TEXT | False | PK  |  |
| run_id | TEXT | False |  |  |
| source_key | INTEGER | False | PK dim_source.source_key |  |
| source_record_id | TEXT | False | PK  |  |
| disposition | TEXT | False |  |  |
| raw_path | TEXT | True |  |  |


## etl_rejected_records

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| id | BIGINT | False | PK  | nextval('etl_rejected_records_id_seq'::regclass) |
| batch_id | VARCHAR(100) | False |  |  |
| source_code | VARCHAR(50) | False |  |  |
| raw_data | TEXT | False |  |  |
| rejection_reason | VARCHAR(255) | False |  |  |
| rejected_at | TIMESTAMP | True |  | now() |


## etl_reconciliation_log

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| id | BIGINT | False | PK  | nextval('etl_reconciliation_log_id_seq'::regclass) |
| batch_id | VARCHAR(100) | False |  |  |
| run_date | TIMESTAMP | True |  | now() |
| source_code | VARCHAR(50) | False |  |  |
| source_records_count | INTEGER | False |  |  |
| dwh_records_inserted | INTEGER | False |  |  |
| rejected_records_count | INTEGER | False |  |  |
| source_total_amount | DOUBLE PRECISION | False |  |  |
| dwh_total_amount | DOUBLE PRECISION | False |  |  |
| diff_amount | DOUBLE PRECISION | False |  |  |
| status | VARCHAR(50) | False |  |  |
| notes | TEXT | True |  |  |
| currency | VARCHAR(10) | True |  |  |
| updated_count | INTEGER | True |  | 0 |
| unchanged_count | INTEGER | True |  | 0 |
| target_count | INTEGER | True |  | 0 |
| run_id | TEXT | True |  |  |


## retailpulse_runs

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| run_id | TEXT | False | PK  |  |
| kind | TEXT | False |  |  |
| status | TEXT | False |  |  |
| started_at | TIMESTAMP | True |  |  |
| finished_at | TIMESTAMP | True |  |  |
| payload | JSONB | False |  |  |


## retailpulse_schema_versions

| Column | Type | Nullable | PK / FK | Default |
|---|---|---|---|---|
| version | TEXT | False | PK  |  |
| applied_at | TIMESTAMP | True |  | now() |


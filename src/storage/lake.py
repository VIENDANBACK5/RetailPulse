"""Raw object storage with verified manifests; S3 failures never fall back silently."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


class RawLake:
    def __init__(self, backend=None, base_dir=None, client=None):
        self.backend = backend or os.getenv("LAKE_BACKEND", "local")
        self.base_dir = Path(base_dir or Path(__file__).resolve().parents[2] / "data_lake")
        self.bucket = os.getenv("LAKE_BUCKET", "retailpulse-raw")
        self.client = client
        if self.backend not in ("local", "s3"):
            raise ValueError("LAKE_BACKEND must be local or s3")
        if self.backend == "s3":
            if self.client is None:
                import boto3
                from botocore.config import Config
                self.client = boto3.client(
                    "s3", endpoint_url=os.environ["LAKE_ENDPOINT_URL"],
                    aws_access_key_id=os.environ["LAKE_ACCESS_KEY"],
                    aws_secret_access_key=os.environ["LAKE_SECRET_KEY"],
                    region_name=os.getenv("LAKE_REGION", "us-east-1"),
                    config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                                  connect_timeout=5, read_timeout=30,
                                  retries={"max_attempts": 2}),
                )
            from botocore.exceptions import ClientError
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as error:
                if str(error.response["Error"]["Code"]) not in ("404", "NoSuchBucket"):
                    raise
                self.client.create_bucket(Bucket=self.bucket)

    @staticmethod
    def _key(key):
        path = PurePosixPath(key)
        if not key or path.is_absolute() or ".." in path.parts or "\\" in key:
            raise ValueError("Invalid lake object key")
        return str(path)

    def put(self, key, payload, content_type="application/octet-stream"):
        key = self._key(key)
        if self.backend == "s3":
            self.client.put_object(Bucket=self.bucket, Key=key, Body=payload,
                                   ContentType=content_type,
                                   Metadata={"sha256": hashlib.sha256(payload).hexdigest()})
        else:
            target = self.base_dir / key
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_bytes(payload)
            temporary.replace(target)
        return self.uri(key)

    def get(self, key):
        key = self._key(key)
        if self.backend == "s3":
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            try:
                return response["Body"].read()
            finally:
                response["Body"].close()
        return (self.base_dir / key).read_bytes()

    def uri(self, key):
        return f"s3://{self.bucket}/{key}" if self.backend == "s3" else str(self.base_dir / key)

    def get_optional(self, key):
        """Only a missing object is optional; network/authentication errors propagate."""
        try:
            return self.get(key)
        except FileNotFoundError:
            return None
        except Exception as error:
            from botocore.exceptions import ClientError
            if isinstance(error, ClientError) and str(error.response['Error']['Code']) in ('NoSuchKey', '404'):
                return None
            raise

    @staticmethod
    def raw_prefix(source, batch_id, ingested_at):
        for value in (source, batch_id):
            if not value or '/' in value or '\\' in value or value in ('.', '..'):
                raise ValueError('Invalid raw partition')
        return f'raw/source={source}/ingest_date={ingested_at:%Y-%m-%d}/batch_id={batch_id}'

    def write_raw(self, source, batch_id, filename, payload, *, record_count=None, mode="operational", ingested_at=None, collected_at=None, provenance=None, currency=None, metadata=None):
        # Source and batch are single partition values, never directory paths.
        for value in (source, batch_id, filename):
            if not value or "/" in value or "\\" in value or value in (".", ".."):
                raise ValueError("Invalid raw partition or filename")
        now = ingested_at or datetime.now(timezone.utc)
        prefix = self.raw_prefix(source, batch_id, now)
        key = f"{prefix}/{filename}"
        digest = hashlib.sha256(payload).hexdigest()
        # Same batch may be retried, but its original bytes must be immutable.
        try:
            previous = self.get(key)
        except FileNotFoundError:
            previous = None
        except Exception as error:
            from botocore.exceptions import ClientError
            if not isinstance(error, ClientError) or error.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                raise
            previous = None
        if previous is not None and previous != payload:
            raise ValueError("Raw object already exists with different contents")
        manifest_key = f"{prefix}/manifest.json"
        existing_manifest = self.get_optional(manifest_key)
        if existing_manifest is not None:
            manifest, previous_payload = self.read_raw(manifest_key)
            if previous_payload != payload or manifest['object_key'] != key:
                raise ValueError('Raw object already exists with different contents')
            return manifest_key
        self.put(key, payload)
        manifest = {
            "schema_version": 1, "batch_id": batch_id, "source": source,
            "data_mode": mode, "ingested_at": now.isoformat(), "object_key": key,
            "collected_at": (collected_at or now).isoformat(),
            "sha256": digest, "size_bytes": len(payload), "record_count": record_count,
            "backend": self.backend, "bucket": self.bucket if self.backend == "s3" else None,
            "provenance": provenance or ("DEMO" if source in ("app", "api") else "UNVERIFIED"),
            "currency": currency or ("GBP" if source == "uci" else "VND"),
            "metadata": metadata or {},
        }
        self.put(manifest_key, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"), "application/json")
        return manifest_key

    def read_raw(self, manifest_key):
        manifest = json.loads(self.get(manifest_key))
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported raw manifest schema")
        payload = self.get(manifest["object_key"])
        if len(payload) != manifest["size_bytes"] or hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
            raise ValueError("Raw object checksum/size does not match its manifest")
        return manifest, payload

    def write_run_result(self, batch_id, result):
        self._key(batch_id)
        return self.put(f"runs/{batch_id}.json", json.dumps(result, ensure_ascii=False, indent=2,
                                                          default=str).encode("utf-8"), "application/json")

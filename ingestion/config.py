"""
Configuration management for the ingestion pipeline.

All configuration comes from environment variables so the same code runs
unchanged in local dev, CI, and (later) Airflow/production. Never hardcode
secrets or environment-specific paths in the pipeline code itself -- put
them here, and load them from the environment.

See .env.example for the full list of variables this pipeline expects.
"""

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    requests_per_minute: int
    raw_data_dir: Path
    request_timeout_seconds: int
    max_retries: int
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    s3_bucket_name: str
    s3_raw_prefix: str

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.getenv("BALLDONTLIE_API_KEY")
        if not api_key:
            raise ConfigError(
                "BALLDONTLIE_API_KEY is not set. Copy .env.example to .env, "
                "add your free API key from app.balldontlie.io, and make sure "
                "it's loaded into the environment before running this script."
            )

        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        s3_bucket_name = os.getenv("S3_BUCKET_NAME")

        missing_aws = [
            name
            for name, value in [
                ("AWS_ACCESS_KEY_ID", aws_access_key_id),
                ("AWS_SECRET_ACCESS_KEY", aws_secret_access_key),
                ("S3_BUCKET_NAME", s3_bucket_name),
            ]
            if not value
        ]
        if missing_aws:
            raise ConfigError(
                f"Missing required AWS configuration: {', '.join(missing_aws)}. "
                "Add these to your .env file -- see .env.example for the full list. "
                "Access keys come from IAM > Users > sports-pipeline-app > "
                "Security credentials."
            )

        raw_data_dir = Path(os.getenv("RAW_DATA_DIR", "storage/raw"))

        return cls(
            api_key=api_key,
            base_url=os.getenv("BALLDONTLIE_BASE_URL", "https://api.balldontlie.io/v1"),
            requests_per_minute=int(os.getenv("REQUESTS_PER_MINUTE", "5")),
            raw_data_dir=raw_data_dir,
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            s3_bucket_name=s3_bucket_name,
            s3_raw_prefix=os.getenv("S3_RAW_PREFIX", "raw/"),
        )

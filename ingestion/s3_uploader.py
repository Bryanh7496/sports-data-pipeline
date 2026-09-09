"""
Upload landed raw files to S3.

Kept as its own module rather than folded into fetch_games.py so that
"fetch and validate data" and "land data somewhere" stay separately
testable and separately swappable -- the same separation of concerns
that made it easy to add S3 here without touching the API client at all.
"""

from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ingestion.config import Settings
from ingestion.utils.logger import get_logger

logger = get_logger(__name__)


class S3UploadError(Exception):
    """Raised when a file fails to upload to S3."""


def upload_file(local_path: Path, settings: Settings) -> str:
    """
    Upload a local file to S3 under the configured raw-data prefix,
    preserving the local filename as the S3 object key.

    Returns the full s3:// URI of the uploaded object.
    """
    s3_key = f"{settings.s3_raw_prefix}{local_path.name}"

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )

    try:
        client.upload_file(str(local_path), settings.s3_bucket_name, s3_key)
    except (BotoCoreError, ClientError) as exc:
        raise S3UploadError(
            f"Failed to upload {local_path} to "
            f"s3://{settings.s3_bucket_name}/{s3_key}: {exc}"
        ) from exc

    s3_uri = f"s3://{settings.s3_bucket_name}/{s3_key}"
    logger.info("Uploaded %s to %s", local_path.name, s3_uri)
    return s3_uri

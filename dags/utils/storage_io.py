import io
import os
from typing import List

from utils.storage_paths import build_paths, get_storage_mode

try:
    from google.cloud import storage
except ImportError:
    storage = None


def _split_gcs_uri(uri: str):
    if not uri.startswith("gs://"):
        raise ValueError(f"Not a GCS URI: {uri}")
    no_scheme = uri[5:]
    bucket, _, blob = no_scheme.partition("/")
    return bucket, blob


def _get_gcs_client():
    if storage is None:
        raise ImportError("google-cloud-storage is not installed")
    return storage.Client()


def ensure_dir(path: str):
    mode = get_storage_mode()
    if mode == "local":
        os.makedirs(path, exist_ok=True)
    else:
        # no-op for GCS
        return


def path_exists(path: str) -> bool:
    mode = get_storage_mode()
    if mode == "local":
        return os.path.exists(path)

    bucket_name, blob_prefix = _split_gcs_uri(path)
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)

    # exact blob
    blob = bucket.blob(blob_prefix)
    if blob.exists():
        return True

    # prefix/folder-style existence
    blobs = list(client.list_blobs(bucket_name, prefix=blob_prefix.rstrip("/") + "/", max_results=1))
    return len(blobs) > 0


def list_files(path: str) -> List[str]:
    mode = get_storage_mode()
    if mode == "local":
        if not os.path.exists(path):
            return []
        return os.listdir(path)

    bucket_name, prefix = _split_gcs_uri(path)
    prefix = prefix.rstrip("/") + "/"
    client = _get_gcs_client()

    names = []
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        relative = blob.name[len(prefix):]
        if relative and "/" not in relative:
            names.append(relative)
    return names


def join_path(base: str, filename: str) -> str:
    mode = get_storage_mode()
    if mode == "local":
        return os.path.join(base, filename)
    return base.rstrip("/") + "/" + filename


def copy_file(src: str, dst: str):
    mode = get_storage_mode()
    if mode == "local":
        import shutil
        shutil.copy2(src, dst)
        return

    src_bucket, src_blob = _split_gcs_uri(src)
    dst_bucket, dst_blob = _split_gcs_uri(dst)
    client = _get_gcs_client()

    source_bucket = client.bucket(src_bucket)
    source_blob = source_bucket.blob(src_blob)

    target_bucket = client.bucket(dst_bucket)
    source_bucket.copy_blob(source_blob, target_bucket, dst_blob)


def write_text(path: str, content: str):
    mode = get_storage_mode()
    if mode == "local":
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return

    bucket_name, blob_name = _split_gcs_uri(path)
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_name).upload_from_string(content, content_type="text/plain")


def read_text(path: str) -> str:
    mode = get_storage_mode()
    if mode == "local":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    bucket_name, blob_name = _split_gcs_uri(path)
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    return bucket.blob(blob_name).download_as_text()


def write_bytes(path: str, content: bytes, content_type: str = "application/octet-stream"):
    mode = get_storage_mode()
    if mode == "local":
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return

    bucket_name, blob_name = _split_gcs_uri(path)
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_name).upload_from_string(content, content_type=content_type)


def read_bytes(path: str) -> bytes:
    mode = get_storage_mode()
    if mode == "local":
        with open(path, "rb") as f:
            return f.read()

    bucket_name, blob_name = _split_gcs_uri(path)
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    return bucket.blob(blob_name).download_as_bytes()

def get_size(path: str) -> int:
    mode = get_storage_mode()
    if mode == "local":
        return os.path.getsize(path)

    bucket_name, blob_name = _split_gcs_uri(path)
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.reload()
    return blob.size or 0
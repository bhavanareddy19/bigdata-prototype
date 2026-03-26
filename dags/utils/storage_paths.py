import os
from typing import Dict


def get_storage_mode() -> str:
    return os.getenv("STORAGE_MODE", "local").strip().lower()


def get_data_bucket() -> str:
    return os.getenv("GCS_DATA_BUCKET", "").strip()


def get_prefix(name: str, default: str) -> str:
    return os.getenv(name, default).strip().strip("/")


def get_local_root() -> str:
    return os.getenv("LOCAL_DATA_ROOT", "data").strip()


def build_paths() -> Dict[str, str]:
    mode = get_storage_mode()

    zone_defaults = {
        "landing": "landing",
        "raw": "raw",
        "staging": "staging",
        "processed": "processed",
        "curated": "curated",
        "features": "features",
        "models": "models",
    }

    if mode == "gcs":
        bucket = get_data_bucket()
        if not bucket:
            raise ValueError("GCS_DATA_BUCKET is required when STORAGE_MODE=gcs")

        return {
            "mode": "gcs",
            **{
                key: f"gs://{bucket}/{get_prefix(f'GCS_{key.upper()}_PREFIX', default)}"
                for key, default in zone_defaults.items()
            },
        }

    root = get_local_root()
    return {
        "mode": "local",
        **{key: os.path.join(root, default) for key, default in zone_defaults.items()},
    }
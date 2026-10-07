"""Application configuration, read once from environment variables.

Keeping all config in one pydantic-settings object (rather than scattering os.getenv
calls) makes the knobs discoverable and testable. Every value has a safe default so the
app runs with no configuration at all.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LABELCHECK_", env_file=".env")

    # --- Performance budget (see the 5-second non-negotiable) -------------------------
    # If a single verify exceeds this, we log a warning. Target is ~3 s, hard budget 5 s.
    slow_label_ms: int = 4000

    # Longest edge (px) images are downscaled to before OCR. Larger = slower, not more
    # accurate past a point; 2000 matches the client-side downscale.
    max_image_edge_px: int = 2000

    # --- Batch limits (reject clearly above these) ------------------------------------
    batch_max_images: int = 500
    batch_max_zip_bytes: int = 500 * 1024 * 1024  # 500 MB
    batch_max_image_bytes: int = 20 * 1024 * 1024  # 20 MB
    batch_max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024  # zip-bomb guard: 2 GB
    batch_ttl_seconds: int = 60 * 60  # in-memory job store TTL: 1 hour
    batch_workers: int = 0  # 0 => use CPU count

    # --- Optional cloud vision fallback -----------------------------------------------
    # OFF by default and must stay off for the firewalled target environment. The code
    # path exists only as a documented extension point; it is never called when False.
    cloud_vision_enabled: bool = False

    # --- Static frontend -------------------------------------------------------------
    # Directory of the built React app that FastAPI serves. Empty => API only (dev mode,
    # where Vite serves the frontend and proxies /api here).
    static_dir: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the singleton Settings, parsed from the environment exactly once."""
    return Settings()

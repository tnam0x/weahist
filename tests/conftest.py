import pytest

from weahist.config import Settings


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(cache_dir=tmp_path / "cache", http_max_retries=0)

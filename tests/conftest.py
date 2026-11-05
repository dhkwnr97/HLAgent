from pathlib import Path

import pytest

from hlagent.settings import Settings
from hlagent.storage import Store


@pytest.fixture
def settings(tmp_path):
    jar = Path.home() / ".local/share/hlagent/tools/beagle.27Feb25.75f.jar"
    return Settings(home=tmp_path / "hlagent", beagle_jar=jar if jar.exists() else None).initialize()


@pytest.fixture
def store(settings):
    return Store(settings.db_path)

import pytest

from app import runner


@pytest.fixture(scope="session", autouse=True)
def toolchains():
    runner.warm()

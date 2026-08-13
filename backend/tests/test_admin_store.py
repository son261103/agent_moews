import asyncio

import pytest

from src.api.admin_store import AdminStore, DEFAULT_SKILL


@pytest.fixture
def store(tmp_path):
    s = AdminStore(str(tmp_path / "admin.db"))
    asyncio.run(s.connect())
    yield s
    asyncio.run(s.close())


def test_seed_default_skill_when_empty(store):
    asyncio.run(store.seed_default_skill())
    skills = asyncio.run(store.list_skills())
    assert [s.name for s in skills] == ["code-review"]
    assert skills[0].description == DEFAULT_SKILL[1]
    # second run does not duplicate
    asyncio.run(store.seed_default_skill())
    assert len(asyncio.run(store.list_skills())) == 1


def test_skill_crud(store):
    asyncio.run(store.create_skill("demo", "Demo skill", "# Steps\n1. Do it"))
    skills = asyncio.run(store.list_skills())
    assert [s.name for s in skills] == ["demo"]

    loaded = asyncio.run(store.get_skill("demo"))
    assert loaded is not None and loaded.content == "# Steps\n1. Do it"

    with pytest.raises(ValueError):
        asyncio.run(store.create_skill("demo", "dup", "x"))

    asyncio.run(store.update_skill("demo", "New desc", "# New"))
    assert asyncio.run(store.get_skill("demo")).description == "New desc"

    with pytest.raises(KeyError):
        asyncio.run(store.update_skill("nope", "d", "c"))
    with pytest.raises(KeyError):
        asyncio.run(store.delete_skill("nope"))

    asyncio.run(store.delete_skill("demo"))
    assert asyncio.run(store.get_skill("demo")) is None


def test_openapi_config_roundtrip(store):
    cfg = asyncio.run(store.get_openapi_config())
    assert cfg.spec_content == "" and cfg.enabled is False

    asyncio.run(
        store.save_openapi_config('{"paths": {}}', "http://x", "tok123", True)
    )
    cfg = asyncio.run(store.get_openapi_config())
    assert cfg.spec_content == '{"paths": {}}'
    assert cfg.base_url == "http://x" and cfg.token == "tok123" and cfg.enabled is True

    asyncio.run(store.save_openapi_config("", "", "", False))
    cfg = asyncio.run(store.get_openapi_config())
    assert cfg.enabled is False and cfg.spec_content == ""

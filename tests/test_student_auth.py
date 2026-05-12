"""tests for _device_ctx + _student_auth + /api/student/login endpoint."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# 確保 src/ 在 path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------- _device_ctx --------------------------------------------------


def test_get_active_device_id_default_none(monkeypatch):
    monkeypatch.delenv("VTUBER_BRAIN_DEVICE_ID", raising=False)
    from open_llm_vtuber._device_ctx import get_active_device_id, set_active_device_id
    set_active_device_id(None)
    assert get_active_device_id() is None


def test_get_active_device_id_env_fallback(monkeypatch):
    monkeypatch.setenv("VTUBER_BRAIN_DEVICE_ID", "env-student")
    from open_llm_vtuber._device_ctx import get_active_device_id, set_active_device_id
    set_active_device_id(None)
    assert get_active_device_id() == "env-student"


def test_set_active_device_id_overrides_env(monkeypatch):
    monkeypatch.setenv("VTUBER_BRAIN_DEVICE_ID", "env-student")
    from open_llm_vtuber._device_ctx import get_active_device_id, set_active_device_id
    set_active_device_id("ctx-student")
    assert get_active_device_id() == "ctx-student"


def test_multi_tenant_disables_env_fallback(monkeypatch):
    monkeypatch.setenv("VTUBER_BRAIN_DEVICE_ID", "env-student")
    monkeypatch.setenv("VTUBER_MULTI_TENANT", "true")
    from open_llm_vtuber._device_ctx import get_active_device_id, set_active_device_id
    set_active_device_id(None)
    assert get_active_device_id() is None


def test_extract_device_id_from_ws_query():
    from open_llm_vtuber._device_ctx import extract_device_id_from_ws

    class FakeWS:
        query_params = {"device_id": "from-query"}
        cookies = {}

    assert extract_device_id_from_ws(FakeWS()) == "from-query"


def test_extract_device_id_from_ws_cookie():
    from open_llm_vtuber._device_ctx import extract_device_id_from_ws

    class FakeWS:
        query_params = {}
        cookies = {"device_id": "from-cookie"}

    assert extract_device_id_from_ws(FakeWS()) == "from-cookie"


def test_extract_device_id_from_ws_none():
    from open_llm_vtuber._device_ctx import extract_device_id_from_ws

    class FakeWS:
        query_params = {}
        cookies = {}

    assert extract_device_id_from_ws(FakeWS()) is None


# ---------- _student_auth ------------------------------------------------


@pytest.fixture
def tmpdb(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("METRICS_DB", tmp.name)
    monkeypatch.setenv("ALLOW_STUDENT_AUTOREGISTER", "true")
    yield tmp.name
    os.unlink(tmp.name)


def test_login_autoregister(tmpdb):
    from open_llm_vtuber import _student_auth
    ok, info = _student_auth.login("s100", name="新同學")
    assert ok is True
    assert info["device_id"] == "s100"
    assert info["name"] == "新同學"
    # 第二次登入不再 auto_register
    ok2, info2 = _student_auth.login("s100", name="改名")
    assert ok2 is True
    # 已存在 → 不會覆寫 name
    assert info2["name"] == "新同學"


def test_login_invalid_id(tmpdb):
    from open_llm_vtuber import _student_auth
    ok, info = _student_auth.login("../etc")
    assert ok is False
    assert "device_id" in info["error"]


def test_login_no_autoregister(tmpdb, monkeypatch):
    monkeypatch.setenv("ALLOW_STUDENT_AUTOREGISTER", "false")
    from open_llm_vtuber import _student_auth
    ok, info = _student_auth.login("s999")
    assert ok is False
    assert "找不到" in info["error"]


def test_find_student_returns_none_for_unknown(tmpdb):
    from open_llm_vtuber import _student_auth
    assert _student_auth.find_student("ghost") is None


# ---------- ${VAR:-default} loader --------------------------------------


def test_yaml_env_var_with_default(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_TEST_KEY", raising=False)
    p = tmp_path / "x.yaml"
    p.write_text("api_key: '${MY_TEST_KEY:-fallback123}'\n")
    from open_llm_vtuber.config_manager.utils import read_yaml
    cfg = read_yaml(str(p))
    assert cfg["api_key"] == "fallback123"


def test_yaml_env_var_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "from-env")
    p = tmp_path / "x.yaml"
    p.write_text("api_key: '${MY_TEST_KEY:-fallback123}'\n")
    from open_llm_vtuber.config_manager.utils import read_yaml
    cfg = read_yaml(str(p))
    assert cfg["api_key"] == "from-env"


def test_yaml_env_var_no_default_keeps_raw(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_TEST_KEY", raising=False)
    p = tmp_path / "x.yaml"
    p.write_text("api_key: '${MY_TEST_KEY}'\n")
    from open_llm_vtuber.config_manager.utils import read_yaml
    cfg = read_yaml(str(p))
    assert cfg["api_key"] == "${MY_TEST_KEY}"

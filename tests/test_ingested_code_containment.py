import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tios.security_ops import ContainmentError, containment, run_untrusted_python


def test_macos_sandbox_path_scrubs_credentials_and_denies_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_python = tmp_path / ".venv" / "bin" / "python"
    isolated_python.parent.mkdir(parents=True)
    isolated_python.symlink_to(sys.executable)
    script = tmp_path / "probe.py"
    script.write_text("pass\n")
    sandbox = tmp_path / "sandbox-exec"
    sandbox.write_text("")
    monkeypatch.setenv("TIOS_TEST_SECRET", "must-not-leak")
    monkeypatch.setattr(containment.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(containment, "SANDBOX_EXEC", sandbox)
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="ok\n", stderr=""))
    monkeypatch.setattr(containment.subprocess, "run", run)

    result = run_untrusted_python(script, interpreter=isolated_python, working_dir=tmp_path)

    assert result.returncode == 0
    assert result.network_denied
    command = run.call_args.args[0]
    assert command[:3] == [str(sandbox), "-p", "(version 1)(allow default)(deny network*)"]
    assert "TIOS_TEST_SECRET" not in run.call_args.kwargs["env"]


@pytest.mark.parametrize("system", ["Linux", "Windows", "FreeBSD", "Unknown"])
def test_containment_refuses_execution_without_proven_network_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, system: str
) -> None:
    isolated_python = tmp_path / ".venv" / "bin" / "python"
    isolated_python.parent.mkdir(parents=True)
    isolated_python.symlink_to(sys.executable)
    script = tmp_path / "probe.py"
    script.write_text("raise AssertionError('must not execute')\n")
    run = Mock()
    monkeypatch.setattr(containment.platform, "system", lambda: system)
    monkeypatch.setattr(containment.subprocess, "run", run)

    with pytest.raises(ContainmentError, match="network isolation is unavailable"):
        run_untrusted_python(script, interpreter=isolated_python, working_dir=tmp_path)
    run.assert_not_called()


def test_containment_rejects_in_process_or_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(ContainmentError):
        run_untrusted_python(Path(__file__), interpreter=Path(sys.executable), working_dir=tmp_path)

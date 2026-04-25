import subprocess
from evalops.env import Env


def test_version_command_shell():
    result = subprocess.run(
        ["python", "-m", "evalops", "-v0", "version"], capture_output=True, text=True
    )

    assert result.returncode == 0
    assert result.stdout.strip() == Env.evalops_version
    assert Env.evalops_version and "." in Env.evalops_version
    assert result.stderr == ""


def test_version_return_val():
    from evalops.commands.version import version

    assert version() == Env.evalops_version

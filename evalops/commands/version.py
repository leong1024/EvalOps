"""Show EvalOps version command."""

from ..cli_base import app
from ..env import Env


@app.command(name="version", help="Show EvalOps version.")
def version():
    print(Env.evalops_version)
    return Env.evalops_version

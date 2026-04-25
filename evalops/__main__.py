"""Allow running the package with `python -m evalops`."""

# Use an absolute import (package-qualified) here; otherwise, the Windows build
# produced by PyInstaller fails.
from evalops.entrypoint import main

if __name__ == "__main__":
    main()

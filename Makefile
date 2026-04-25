cs:
	flake8 .
black:
	black .


install:
	pip install -e .

pkg:
	python multi-build.py
build: pkg

clear-dist:
	python -c "import shutil, os; shutil.rmtree('dist', ignore_errors=True); os.makedirs('dist', exist_ok=True)"
clr-dist: clear-dist

windows-build:  # Build Windows executable using PyInstaller to dist/evalops.exe
	pyinstaller evalops.spec

publish:
	python -c "import os,subprocess;t=os.getenv('PYPI_TOKEN');subprocess.run(['python', '-m', 'twine', 'upload', 'dist/*', '-u', '__token__', '-p', t], check=True)"

upload: publish
test:
	pytest --log-cli-level=INFO
tests: test

# Generate CLI reference documentation
# Does not work on Windows due to PYTHONUTF8 env var setting
cli-reference:
	PYTHONUTF8=1 typer evalops.cli utils docs --name evalops --title="<a href=\"../\"><img src=\"../press-kit/logo/evalops-bot-1_64top.png\" align=\"left\" width=64 height=50 title=\"EvalOps: AI Code Reviewer\"></a>EvalOps CLI Reference" --output documentation/command_line_reference.md
cli-ref: cli-reference
cli-doc: cli-reference
cli-docs: cli-reference
#!/usr/bin/env python3
"""
Cross-platform launcher for the ActiSculpt Confocal Viewer.
Creates a local virtual environment, installs requirements, verifies the
Python environment, and starts the Streamlit app.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import venv


MIN_PYTHON = (3, 9)
REQUIRED_MODULES = [
    "streamlit",
    "tifffile",
    "numpy",
    "matplotlib",
    "imageio",
    "PIL",
    "skimage",
]


def venv_python_path(venv_dir: str) -> str:
    if platform.system() == "Windows":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def ensure_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        required = ".".join(str(part) for part in MIN_PYTHON)
        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print(f"✗ Python {required}+ is required. Current version: {current}")
        sys.exit(1)


def ensure_venv(venv_dir: str) -> str:
    python_exe = venv_python_path(venv_dir)

    if not os.path.exists(python_exe):
        print("Creating virtual environment...")
        try:
            venv.create(venv_dir, with_pip=True)
            print(f"✓ Virtual environment created at {venv_dir}")
        except Exception as exc:
            print(f"✗ Error creating virtual environment: {exc}")
            sys.exit(1)
    else:
        print(f"✓ Using existing virtual environment: {venv_dir}")

    if not os.path.exists(python_exe):
        print(f"✗ Virtual environment Python not found at {python_exe}")
        sys.exit(1)

    return python_exe


def run_command(command: list[str], cwd: str) -> None:
    subprocess.run(command, check=True, cwd=cwd)


def install_requirements(python_exe: str, requirements_file: str, script_dir: str) -> None:
    if not os.path.exists(requirements_file):
        print(f"✗ requirements.txt not found at {requirements_file}")
        sys.exit(1)

    print("Upgrading pip...")
    try:
        run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip"], script_dir)
        print("✓ pip upgraded")
    except Exception as exc:
        print(f"✗ Error upgrading pip: {exc}")
        sys.exit(1)

    print("Installing dependencies from requirements.txt...")
    try:
        run_command([python_exe, "-m", "pip", "install", "-r", requirements_file], script_dir)
        print("✓ Dependencies installed")
    except Exception as exc:
        print(f"✗ Error installing dependencies: {exc}")
        sys.exit(1)

    print("Checking installed dependencies...")
    try:
        run_command([python_exe, "-m", "pip", "check"], script_dir)
        print("✓ Dependency check passed")
    except Exception as exc:
        print(f"✗ Dependency check failed: {exc}")
        sys.exit(1)


def verify_required_modules(python_exe: str, script_dir: str) -> None:
    module_probe = "import importlib.util\nmissing = []\nfor name in {modules!r}:\n    if importlib.util.find_spec(name) is None:\n        missing.append(name)\nif missing:\n    raise SystemExit('Missing modules: ' + ', '.join(missing))\n".format(modules=REQUIRED_MODULES)

    try:
        run_command([python_exe, "-c", module_probe], script_dir)
        print("✓ Required modules are available")
    except Exception as exc:
        print(f"✗ Missing required modules: {exc}")
        sys.exit(1)


def main() -> None:
    ensure_python_version()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(script_dir, ".venv")
    requirements_file = os.path.join(script_dir, "requirements.txt")
    app_file = os.path.join(script_dir, "confocal_gui.py")

    python_exe = ensure_venv(venv_dir)
    install_requirements(python_exe, requirements_file, script_dir)
    verify_required_modules(python_exe, script_dir)

    if not os.path.exists(app_file):
        print(f"✗ App file not found at {app_file}")
        sys.exit(1)

    print("Starting Streamlit app...\n")
    print("=" * 60)

    try:
        subprocess.run([python_exe, "-m", "streamlit", "run", app_file], cwd=script_dir)
    except KeyboardInterrupt:
        print("\n\nApp terminated by user.")
        sys.exit(0)
    except Exception as exc:
        print(f"\n✗ Error running Streamlit: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
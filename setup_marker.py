#!/usr/bin/env python3
"""
Setup script for marker-pdf installation.

marker-pdf has heavy ML dependencies (PyTorch, Transformers, etc.) that can be
tricky to install. This script helps automate the process and provides helpful
error messages if something goes wrong.

Usage:
    python setup_marker.py

Options:
    --cpu-only: Install CPU-only version (no CUDA support)
    --check: Only check if marker-pdf is installed, don't install
"""

import argparse
import subprocess
import sys
from pathlib import Path


def print_header(message: str) -> None:
    """Print a formatted header message."""
    print("\n" + "=" * 70)
    print(f"  {message}")
    print("=" * 70 + "\n")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"ℹ️  {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"✓ {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"❌ {message}", file=sys.stderr)


def check_marker_installed() -> bool:
    """
    Check if marker-pdf is already installed.

    Returns:
        bool: True if installed, False otherwise
    """
    try:
        import marker
        print_success("marker-pdf is already installed")
        print_info(f"Location: {Path(marker.__file__).parent}")
        return True
    except ImportError:
        return False


def install_marker(cpu_only: bool = False) -> bool:
    """
    Install marker-pdf and its dependencies.

    Args:
        cpu_only: If True, install CPU-only version (no CUDA)

    Returns:
        bool: True if installation succeeded, False otherwise
    """
    print_header("Installing marker-pdf")

    # Determine installation command
    if cpu_only:
        print_info("Installing CPU-only version (no CUDA support)")
        install_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "marker-pdf",
            "--extra-index-url",
            "https://download.pytorch.org/whl/cpu",
        ]
    else:
        print_info("Installing with CUDA support (if available)")
        install_cmd = [sys.executable, "-m", "pip", "install", "marker-pdf"]

    print_info(f"Running: {' '.join(install_cmd)}")
    print_info("This may take several minutes...")
    print()

    # Run installation
    try:
        result = subprocess.run(
            install_cmd,
            check=True,
            text=True,
            capture_output=False,  # Show output in real-time
        )

        print()
        print_success("marker-pdf installed successfully!")
        return True

    except subprocess.CalledProcessError as e:
        print()
        print_error("Installation failed!")
        print_error(f"Error: {e}")
        return False


def verify_installation() -> bool:
    """
    Verify that marker-pdf is installed and can be imported.

    Returns:
        bool: True if verification succeeded, False otherwise
    """
    print_header("Verifying Installation")

    try:
        print_info("Importing marker...")
        import marker
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered

        print_success("All imports successful!")

        print_info("Checking model initialization...")
        print_info("(First run will download ~2GB of models - this is normal)")
        print()

        # This will trigger model download if needed
        # We don't actually need to use them, just check they initialize
        try:
            model_dict = create_model_dict()
            print()
            print_success("Models initialized successfully!")
            print_info("marker-pdf is ready to use")
            return True
        except Exception as e:
            print()
            print_error(f"Failed to initialize models: {e}")
            print_info("Models will be downloaded on first use")
            return True  # Not a fatal error

    except ImportError as e:
        print_error(f"Import failed: {e}")
        return False
    except Exception as e:
        print_error(f"Verification failed: {e}")
        return False


def print_usage_instructions() -> None:
    """Print instructions on how to use marker-pdf."""
    print_header("Next Steps")

    print("marker-pdf is now ready to use!")
    print()
    print("To start the Lokal-RAG application:")
    print("  python main.py")
    print()
    print("Note: On first run, marker-pdf will download ~2GB of ML models.")
    print("This is a one-time operation and may take a few minutes.")
    print()


def main() -> None:
    """Main entry point for the setup script."""
    parser = argparse.ArgumentParser(
        description="Install marker-pdf for Lokal-RAG application"
    )
    parser.add_argument(
        "--cpu-only",
        action="store_true",
        help="Install CPU-only version (no CUDA support)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check if marker-pdf is installed, don't install",
    )

    args = parser.parse_args()

    print_header("Lokal-RAG: marker-pdf Setup")

    # Check if already installed
    if check_marker_installed():
        if args.check:
            sys.exit(0)

        print_info("marker-pdf is already installed.")
        response = input("Do you want to reinstall? (y/N): ")
        if response.lower() not in ("y", "yes"):
            print_info("Skipping installation")
            sys.exit(0)

    elif args.check:
        print_error("marker-pdf is not installed")
        sys.exit(1)

    # Install marker-pdf
    if not install_marker(cpu_only=args.cpu_only):
        print_error("Installation failed. Please check the error messages above.")
        print()
        print("Common issues:")
        print("  - Insufficient disk space (requires ~5GB)")
        print("  - Network issues (downloads large ML models)")
        print("  - Conflicting package versions")
        print()
        print("Try:")
        print("  - python setup_marker.py --cpu-only  (for CPU-only installation)")
        print("  - pip install marker-pdf  (manual installation)")
        sys.exit(1)

    # Verify installation
    if not verify_installation():
        print_error("Installation verification failed")
        print_info("You may still be able to use marker-pdf, but there might be issues")
        sys.exit(1)

    # Print usage instructions
    print_usage_instructions()


if __name__ == "__main__":
    main()

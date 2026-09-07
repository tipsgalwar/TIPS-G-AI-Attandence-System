"""
TIPS-G ALWAR Student Attendance System — Frontend Entry Point
This is the standalone entry point for the PyQt6 desktop application.
Use this file to run the frontend independently of the backend.

Usage:
    python run_frontend.py

For PyInstaller bundling:
    pyinstaller frontend.spec
"""
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import sys

def main():
    from frontend.main import main as run_qt
    run_qt()

if __name__ == "__main__":
    main()

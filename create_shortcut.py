# -*- coding: utf-8 -*-
"""
TIPS-G ALWAR Student Attendance System - Desktop Shortcut Creator
Run this standalone script to place a TIPS-G launcher shortcut on your Windows Desktop.

Usage:
    python create_shortcut.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from frontend.icon_manager import icon_manager

def main():
    print("=" * 60)
    print("  TIPS-G ALWAR - Desktop Shortcut & Icon Setup Utility")
    print("=" * 60)
    
    status = icon_manager.verify_icon_status()
    print("\n[1] Icon Verification:")
    print(f"    - Found: {status['found']}")
    print(f"    - Path:  {status['path']}")
    print(f"    - Size:  {status['size_bytes']} bytes")
    print(f"    - Valid: {status['is_valid']}")
    
    print("\n[2] Creating Desktop Shortcut...")
    success, message, paths = icon_manager.create_desktop_shortcut()
    
    if success:
        print(f"\n[+] SUCCESS: {message}")
        for p in paths:
            print(f"  -> {p}")
    else:
        print(f"\n[-] FAILED: {message}")
        sys.exit(1)

if __name__ == "__main__":
    main()

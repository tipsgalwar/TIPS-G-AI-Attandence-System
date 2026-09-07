import subprocess

ALLOWED_BSSIDS = [
    "F4-27-56-7C-2D-9F"
]

import subprocess
import re

def get_current_bssid():
    try:
        output = subprocess.check_output(
            "arp -a",
            shell=True
        ).decode(errors="ignore")

        match = re.search(
            r"192\.168\.1\.1\s+([a-fA-F0-9\-]+)",
            output
        )

        if match:
            return match.group(1).upper()

    except Exception as e:
        print(e)

    return None

def is_university_wifi():
    current_bssid = get_current_bssid()
    print(f"Current BSSID: {current_bssid}")
    return current_bssid in ALLOWED_BSSIDS
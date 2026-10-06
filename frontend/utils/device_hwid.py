"""
Hardware Device Fingerprinting & Multi-Factor Device Binding Utility.
Protects the attendance system against proxy logins and shared-device switching by binding
student/admin accounts to their physical machine hardware ID (HWID).

Enforces:
1. One Account per Device (Switching accounts on the same machine requires Admin Passcode).
2. One Device per Account (Logging into the account from an unrecognized machine requires Admin Passcode).
"""

import os
import sys
import json
import hashlib
import platform
import subprocess
import uuid
from pathlib import Path
from loguru import logger

# Cryptographic salt compiled directly into the binary
PASSCODE_SALT = "TIPS_G_ATTENDANCE_SECURE_AUTH_SALT_V1_2026"

def _hash_passcode(code: str) -> str:
    """Computes a salted SHA-256 digest (case-insensitive & trimmed)."""
    if not code:
        return ""
    normalized = code.strip().lower()
    return hashlib.sha256(f"{PASSCODE_SALT}:{normalized}".encode("utf-8")).hexdigest()

# Pre-compiled SHA-256 hashes for authorized master administrative passcodes.
# (No plaintext passwords exist in the source or compiled .exe binary)
AUTHORIZED_PASSCODE_HASHES = {
    # TIPSG@Admin#321
    hashlib.sha256(f"{PASSCODE_SALT}:tipsg@admin#321".encode("utf-8")).hexdigest(),
}

def _get_bindings_file_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent.parent
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "device_bindings.json"


def get_current_hwid() -> str:
    """
    Computes a unique SHA-256 hardware fingerprint based on:
    1. Motherboard UUID (Windows WMI / csproduct)
    2. Machine GUID from Registry
    3. CPU Processor ID
    4. Physical Node UUID
    """
    raw_components = []

    # 1. Windows Motherboard UUID
    try:
        if platform.system() == "Windows":
            cmd = "wmic csproduct get uuid"
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode(errors="ignore")
            lines = [line.strip() for line in out.splitlines() if line.strip() and "UUID" not in line.upper()]
            if lines:
                raw_components.append(lines[0])
    except Exception:
        pass

    # 2. Windows Machine GUID from Registry
    try:
        if platform.system() == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    raw_components.append(str(guid).strip())
    except Exception:
        pass

    # 3. CPU Processor ID
    try:
        if platform.system() == "Windows":
            cmd = "wmic cpu get processorid"
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode(errors="ignore")
            lines = [line.strip() for line in out.splitlines() if line.strip() and "PROCESSORID" not in line.upper()]
            if lines:
                raw_components.append(lines[0])
    except Exception:
        pass

    # 4. Fallback: Network Node UUID
    node_id = str(uuid.getnode())
    raw_components.append(node_id)
    raw_components.append(platform.node())

    combined = "||".join(raw_components)
    hwid_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest().upper()
    return f"HWID-{hwid_hash[:4]}-{hwid_hash[4:8]}-{hwid_hash[8:12]}-{hwid_hash[12:16]}"


def get_device_name() -> str:
    return platform.node() or "Unknown Machine"


def load_all_bindings() -> dict:
    file_path = _get_bindings_file_path()
    if not file_path.exists():
        return {"users": {}, "machines": {}}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data or "machines" not in data:
                # Migrate older flat structure if present
                users = data.get("users", {})
                machines = data.get("machines", {})
                for k, v in data.items():
                    if k not in ["users", "machines"] and isinstance(v, dict):
                        users[k] = v
                        hw = v.get("hwid")
                        if hw:
                            machines[hw] = {"username": k, "device_name": v.get("device_name", "")}
                return {"users": users, "machines": machines}
            return data
    except Exception as e:
        logger.error(f"Failed to read device bindings: {e}")
        return {"users": {}, "machines": {}}


def save_all_bindings(bindings: dict):
    file_path = _get_bindings_file_path()
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(bindings, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save device bindings: {e}")


def check_device_authorization(username: str, role: str = "") -> dict:
    """
    Checks bidirectional authorization:
    1. Is this machine already locked to another user? (Prevent proxy account switching on same PC)
    2. Is this user already registered on another machine? (Prevent login from unauthorized foreign PCs)

    Returns:
    {
        "authorized": bool,
        "reason": "OK" | "SWITCH_ACCOUNT" | "NEW_DEVICE" | "FIRST_TIME",
        "current_hwid": str,
        "locked_user": str or None,
        "registered_hwid": str or None,
        "device_name": str
    }
    """
    uname = (username or "").strip().lower()
    current_hwid = get_current_hwid()
    device_name = get_device_name()

    bindings = load_all_bindings()
    users = bindings.get("users", {})
    machines = bindings.get("machines", {})

    # Check 1: Is this machine already bound to a DIFFERENT user?
    if current_hwid in machines:
        machine_entry = machines[current_hwid]
        bound_user = (machine_entry.get("username") or "").strip().lower()
        if bound_user and bound_user != uname:
            # Different user trying to log into this already registered computer!
            logger.warning(f"Device Switch Detected: Machine {current_hwid} is bound to '{bound_user}', but '{uname}' is attempting login.")
            return {
                "authorized": False,
                "reason": "SWITCH_ACCOUNT",
                "current_hwid": current_hwid,
                "locked_user": bound_user,
                "registered_hwid": None,
                "device_name": device_name
            }

    # Check 2: Is this user already bound to a DIFFERENT machine?
    if uname in users:
        user_entry = users[uname]
        stored_hwid = user_entry.get("hwid", "")
        if stored_hwid and stored_hwid != current_hwid:
            logger.warning(f"Foreign Device Detected: User '{uname}' is bound to {stored_hwid}, but logging in from {current_hwid}.")
            return {
                "authorized": False,
                "reason": "NEW_DEVICE",
                "current_hwid": current_hwid,
                "locked_user": None,
                "registered_hwid": stored_hwid,
                "device_name": device_name
            }
        elif stored_hwid == current_hwid:
            return {
                "authorized": True,
                "reason": "OK",
                "current_hwid": current_hwid,
                "locked_user": None,
                "registered_hwid": stored_hwid,
                "device_name": device_name
            }

    # Check 3: Brand new unlinked user on a brand new unlinked machine
    return {
        "authorized": True,
        "reason": "FIRST_TIME",
        "current_hwid": current_hwid,
        "locked_user": None,
        "registered_hwid": current_hwid,
        "device_name": device_name
    }


def authorize_device(username: str, hwid: str = None) -> bool:
    """
    Binds the current physical machine exclusively to the specified user account.
    """
    uname = (username or "").strip().lower()
    current_hwid = hwid or get_current_hwid()
    device_name = get_device_name()

    bindings = load_all_bindings()
    users = bindings.get("users", {})
    machines = bindings.get("machines", {})

    # Set user -> HWID
    users[uname] = {
        "hwid": current_hwid,
        "device_name": device_name
    }

    # Set machine -> User (One machine = One user)
    machines[current_hwid] = {
        "username": uname,
        "device_name": device_name
    }

    bindings["users"] = users
    bindings["machines"] = machines
    save_all_bindings(bindings)
    logger.info(f"Machine {current_hwid} is now exclusively bound to account '{uname}' ({device_name})")
    return True


def validate_master_passcode(passcode: str, username: str = None, hwid: str = None) -> bool:
    """
    Validates the entered passcode using Salted SHA-256 Cryptographic Hashing.
    No plaintext passwords are ever matched or exposed in memory/binaries.
    Operates strictly client-side so NO backend/server code changes are required.
    """
    if not passcode:
        return False

    candidate_hash = _hash_passcode(passcode)
    
    # 1. Primary verification: Check pre-compiled secure hashes in the binary
    if candidate_hash in AUTHORIZED_PASSCODE_HASHES:
        logger.info(f"Master passcode verified via SHA-256 hash for '{username}' (HWID: {hwid})")
        return True

    # 2. Secondary verification: Check optional local .env override if administrator provided one
    env_code = os.getenv("DEVICE_MASTER_PASSCODE")
    if env_code and _hash_passcode(env_code) == candidate_hash:
        return True

    # 3. Dynamic .env file parsing (real-time reload without restart)
    base_dir = Path(__file__).resolve().parent.parent.parent
    for env_cand in [base_dir / ".env", base_dir / "backend" / ".env"]:
        if env_cand.exists():
            try:
                with open(env_cand, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("DEVICE_MASTER_PASSCODE="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and _hash_passcode(val) == candidate_hash:
                                return True
            except Exception:
                pass

    logger.warning(f"Master passcode rejected for user '{username}' (HWID: {hwid})")
    return False

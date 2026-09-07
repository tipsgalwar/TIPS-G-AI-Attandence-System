# -*- mode: python ; coding: utf-8 -*-
# TIPS-G ALWAR Student Attendance System — PyInstaller Spec
# Embeds TIPS-G-ALWAR.ico directly into the Windows executable PE header.

import os
from pathlib import Path

block_cipher = None
project_root = os.path.abspath(SPECPATH)

import cv2
import mediapipe

added_datas = [
    (os.path.join(project_root, 'storage', 'TIPS-G-ALWAR.ico'), 'storage'),
    (os.path.join(project_root, 'storage', '_TIPS-G ALWAR.png'), 'storage'),
    (os.path.join(project_root, 'models', 'arcface_resnet50.onnx'), 'models'),
    (os.path.join(project_root, 'models', 'face_landmarker.task'), 'models'),
    (os.path.join(project_root, 'config.ini'), '.'),
    (os.path.join(project_root, '.env'), '.'),
    (os.path.join(project_root, '.env_vps'), '.'),
    (os.path.join(project_root, 'config'), 'config'),
]

# Embed OpenCV Haar cascades for face detection in frozen .exe
if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
    cascade_file = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
    if os.path.exists(cascade_file):
        added_datas.append((cv2.data.haarcascades, 'cv2/data'))

# Embed MediaPipe module graphs & data
mediapipe_dir = os.path.dirname(mediapipe.__file__)
if os.path.exists(mediapipe_dir):
    added_datas.append((mediapipe_dir, 'mediapipe'))

# Only include existing data files
datas = [(src, dst) for src, dst in added_datas if os.path.exists(src)]

a = Analysis(
    ['run_frontend.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'frontend',
        'frontend.main',
        'frontend.ui_effects',
        'frontend.icon_manager',
        'frontend.api_client',
        'frontend.onnx_face_service',
        'frontend.utils.wifi_checker',
        'src',
        'src.database',
        'src.database.connection',
        'src.database.models',
        'src.backend',
        'src.backend.services',
        'src.backend.services.auth_service',
        'sqlalchemy',
        'sqlalchemy.orm',
        'sqlalchemy.ext.declarative',
        'sqlalchemy.dialects.postgresql',
        'psycopg2',
        'models',
        'models.download_models',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'cv2',
        'numpy',
        'onnxruntime',
        'mediapipe',
        'requests',
        'websocket',
        'loguru',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'torch', 'tensorflow'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TIPS-G-Attendance',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'storage', 'TIPS-G-ALWAR.ico'),
)

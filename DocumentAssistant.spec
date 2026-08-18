# PyInstaller spec — DocumentAssistant (UI cliente).
# Build : pyinstaller DocumentAssistant.spec --noconfirm  ->  dist/DocumentAssistant.exe
#
# N'embarque QUE l'UI et ses dépendances (PySide6, psycopg, requests).
# Le pipeline (Docling, Anthropic, Exchange) reste sur le serveur : exclu du build.

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# psycopg 3 : la lib native (libpq) vit dans psycopg_binary et doit être collectée.
for paquet in ("psycopg", "psycopg_binary"):
    d, b, h = collect_all(paquet)
    datas += d
    binaries += b
    hiddenimports += h


a = Analysis(
    ["src/document_assisstant/run_client.py"],
    pathex=["src/document_assisstant"],          # racine des imports (config, databases, ui...)
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[                                   # dépendances pipeline : jamais dans l'UI
        "docling", "torch", "torchvision", "transformers",
        "anthropic", "exchangelib", "ollama", "notion_client",
        "matplotlib", "scipy", "sympy", "networkx", "pandas",
        "tkinter",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtQuick3D",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DocumentAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # désactivé : UPX peut corrompre les DLL Qt
    runtime_tmpdir=None,
    console=False,            # application fenêtrée (pas de console noire)
    disable_windowed_traceback=False,
    icon=None,                # mettre "app.ico" ici pour une icône personnalisée
)

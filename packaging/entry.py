"""PyInstaller entry point.

cli.py uses relative imports, so it can't be handed to PyInstaller directly;
this wrapper imports the package the normal way. Build with:

    .venv\Scripts\pyinstaller --onefile --name wwvb-emulator -p src ^
        --collect-all sounddevice --collect-all tzdata ^
        --distpath release\windows packaging\entry.py
"""

from wwvb_emulator.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

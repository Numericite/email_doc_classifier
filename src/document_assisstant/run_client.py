# Point d'entrée de l'application compilée (DocumentAssistant.exe).
# En mode fenêtré, PyInstaller met sys.stdout / sys.stderr à None : on les
# redirige vers le vide pour que les print() de debug ne fassent pas planter l'app.
import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from ui.app import main

if __name__ == "__main__":
    main()

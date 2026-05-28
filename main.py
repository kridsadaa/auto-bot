import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from engine.logger import setup_logger
from gui.main_window import MainWindow


if __name__ == "__main__":
    setup_logger()
    app = MainWindow()
    app.mainloop()

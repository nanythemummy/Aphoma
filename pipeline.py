import tkinter as tk
import logging
from util import util

from UI.BuildFrame import BuildFrame
LOGGER = util.getLogger(__name__)



class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FM/ISAC Photogrammetry Pipeline")
        build = BuildFrame(self)
        build.configure(padding=10)
        build.grid(column=0,row=0, sticky=(tk.N,tk.W,tk.E,tk.S))
        LOGGER.warning("UI Started.")

if __name__=="__main__":
    app= MainApp()
    app.mainloop()

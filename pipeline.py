import tkinter as tk
from tkinter import ttk
import logging
from util import util
import photogrammetryScripts
from UI.BuildFrame import BuildFrame
from UI.WatchFrame import WatchFrame
from UI.SendFrame import SendFrame
from UI.BuildConsole import BuildConsole, TextHanlder
LOGGER = util.getLogger(__name__)



class MainApp(tk.Tk):
    
    def __init__(self):
        super().__init__()
        self.geometry("1000x700")
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self.title("FM/ISAC Photogrammetry Pipeline")
        config = photogrammetryScripts.load_config()
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(column=0,row=0,sticky="NSEW")

        #setup build tab
        self.build = BuildFrame(self.notebook, config)
        self.build.configure(padding=10)
        self.build.grid(column=0,row=0, sticky="NSEW")
        self.notebook.add(self.build, text="Build")
        
        #setup watch tab
        self.watch = WatchFrame(self.notebook,config)
        self.watch.configure(padding=10)
        self.watch.grid(column=0,row=0, sticky="NSEW")
        self.notebook.add(self.watch,text="Watch")

        #setup send tab
        self.sender = SendFrame(self.notebook,config)
        self.sender.configure(padding=10)
        self.sender.grid(column=0,row=0)
        self.notebook.add(self.sender,text="Sender")
        #setup logging console
        self.console = BuildConsole(self)
        textHandler =  TextHanlder(self.console)
        self.console.grid(column=0,row=1,padx=3, pady=3, sticky="NSEW")
        util.addLogHandler(textHandler)
        LOGGER.info("UI Started.")

if __name__=="__main__":
    app= MainApp()
    app.mainloop()

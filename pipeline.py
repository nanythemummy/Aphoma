import tkinter as tk
from tkinter import ttk
from util import util
from util.Configurator import Configurator
import photogrammetryScripts
from UI.BuildFrame import BuildFrame
from UI.WatchFrame import WatchFrame
from UI.SendFrame import SendFrame
from UI.BuildConsole import BuildConsole, TextHanlder
from UI.PipelineConfigFrame import ConfigWindow
import util.PipelineLogging as PipelineLogging

LOGGER = PipelineLogging.getLogger(__name__)



class MainApp(tk.Tk):
    def OpenConfigWindow(self):
        if not self.configWindow:
            self.configWindow = ConfigWindow(self)
            self.configWindow.protocol("WM_DELETE_WINDOW",self.CloseConfigWindow)  

    def CloseConfigWindow(self):
            self.configWindow.destroy()
            self.configWindow=None
            
            
    def __init__(self):
        super().__init__()
        self.configWindow = None
        self.geometry("1000x700")
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self.title("FM/ISAC Photogrammetry Pipeline")
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(column=0,row=0,sticky="NSEW")

        #setup build tab
        self.build = BuildFrame(self.notebook)
        self.build.configure(padding=10)
        self.build.grid(column=0,row=0, sticky="NSEW")
        self.notebook.add(self.build, text="Build")
        
        #setup watch tab
        self.watch = WatchFrame(self.notebook)
        self.watch.configure(padding=10)
        self.watch.grid(column=0,row=0, sticky="NSEW")
        self.notebook.add(self.watch,text="Watch")

        #setup send tab
        self.sender = SendFrame(self.notebook)
        self.sender.configure(padding=10)
        self.sender.grid(column=0,row=0)
        self.notebook.add(self.sender,text="Sender")

        #setup logging console
        self.console = BuildConsole(self)
        textHandler =  TextHanlder(self.console)
        self.console.grid(column=0,row=1,padx=3, pady=3, sticky="NSEW")
        PipelineLogging.addLogHandler(textHandler)

        #setup config panel
        configbutton = tk.Button(self,text="Configure", command = self.OpenConfigWindow)
        configbutton.grid(column=0,row=2, pady=3, sticky="NSEW")
        

if __name__=="__main__":
    app= MainApp()
    app.mainloop()

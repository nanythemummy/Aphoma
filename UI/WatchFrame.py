from tkinter import *
from tkinter import ttk
from tkinter import messagebox, filedialog
from pathlib import Path
from UI.UIconsts import UIConsts
from util.util import MaskingOptions
from util.Configurator import Configurator
from util.InstrumentationStatistics import InstrumentationStatistics
import photogrammetryScripts as phscripts
from UI.PipelineFrame import FormItemsInterface,PipelineFrameBase


class WatchFormItems(FormItemsInterface):

    def __init__(self):
        self.input_dir = StringVar()
        self.masking_option = StringVar()
      

    def validate(self)->dict:
        msg = ""
        valid = False
        inputdir = Path(self.input_dir.get())
        if not self.input_dir.get() or not inputdir.exists() or not inputdir.is_dir():
            msg = "Pick a directory to listen on."
        else:
            valid = True
        return {"valid":valid,"message":msg}
    
class WatchFrame(PipelineFrameBase):
    def update_buttons(self):
        if self.watcher:
            if not self.watcher.stoprequest:
                self.disable_enable_all(False)
                self.watcher = None
            else:
                self.after(5,self.update_buttons)

    def stop_watching(self):
        if not self.state=="stopped":
            self.state = "stopped"
            if self.watcher:
                self.watcher.stoprequest=True
                self.after(5,self.update_buttons)
                
    def task(self,args:WatchFormItems):
        try:
            self.disable_enable_all(True)
            self.state = "running"
            mask_option = UIConsts.MASKOPTIONS[args.masking_option.get()]
            print(mask_option)

            Configurator.getConfig().setProperty("processing","ListenerDefaultMasking", MaskingOptions.numToFriendlyString(mask_option))
            self.watcher = phscripts.Watcher(args.input_dir.get(), False) 
            self.stopbutton.configure(state="normal")
            self.watcher.run()
        except Exception as e:
            messagebox.showerror("Build Exception",e)
            raise e
        finally:
            self.disable_enable_all(False)

    def __init__(self,container):

        super().__init__(container)
        maskoptionvals = [*UIConsts.MASKOPTIONS.keys()]
        self.watcher = None
        self.svars = WatchFormItems()
        ttk.Label(self,text="Listen Directory").grid(column=0,row=1)

        self.svars.input_dir.set(Configurator.getConfig().getProperty("watcher","listen_directory"))
        directory = ttk.Entry(self, width=25, textvariable=self.svars.input_dir)
        directory.grid(column=0,row=2,sticky=("WE"))
        ttk.Button(self,text="Browse",command = lambda:self.svars.input_dir.set(filedialog.askdirectory())).grid(column=1,row=2)
        ttk.Label(self,text="Masking Technique").grid(column=0,row=3)
        maskoption = ttk.Combobox(self,textvariable=self.svars.masking_option, values=maskoptionvals,state='readonly')
        maskoption.current(0)
        maskoption.grid(column=0,row=4)
        self.watchbutton = ttk.Button(self,text="Watch",command=lambda:self.execute(self.svars))
        self.watchbutton.grid(column=0, row=5)
        self.stopbutton = ttk.Button(self,text="Stop",state = "disabled",command=lambda:self.stop_watching())
        self.stopbutton.grid(column=1,row=5)
        self.state  = "stopped"
    
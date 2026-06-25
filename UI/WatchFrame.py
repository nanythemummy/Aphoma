from tkinter import *
from tkinter import ttk
import threading
import shutil
from tkinter import messagebox, filedialog
from pathlib import Path
from UI.UIconsts import UIConsts
from util.util import MaskingOptions, delete_manifests_images
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
    def execute(self,args:FormItemsInterface):
        validate = args.validate()
        if not validate["valid"]:
            messagebox.showerror("Validation Error", validate["message"])
            return
        maskoption = args.masking_option.get()
        mask_option = UIConsts.MASKOPTIONS.get(maskoption,MaskingOptions.NOMASKS)
        Configurator.getConfig().setProperty("processing","ListenerDefaultMasking", MaskingOptions.numToFriendlyString(mask_option))
            #phscripts.Watcher(args.input_dir.get(), False) 
        self.stopbutton.configure(state="normal")
        self.cancel_event.clear()
        try:
            thr = threading.Thread(target=phscripts.startWatcher,args=(args.input_dir.get(),self.cancel_event),daemon=False)
            self.threads.append(thr)
            thr.start()
            self.disable_enable_all(True)
        except Exception as e:
            messagebox.showerror("Build Exception",e)
            self.disable_enable_all(False)
            raise e


    def stop_watching(self):
        self.cancel_event.set()
        while len(self.threads)>0:
            th = self.threads.pop()
            th.join()
        self.disable_enable_all(False)


    def clear_directories(self):
        temp = Configurator.getConfig().getProperty("watcher","temp_scratch")
        listen = Configurator.getConfig().getProperty("watcher","listen_directory")
        proceed= messagebox.askokcancel("Clear Directories?",f"This operation will clear the temp directory {temp} \n and the listen directory {listen}. \n Proceed?")
        if proceed:
            delete_manifests_images(listen)
            if Path(temp).exists():
                shutil.rmtree(temp)
        
    def task(self,args:WatchFormItems):
        try:
            self.schedule_on_main_thread(self.disable_enable_all, True)
            self.cancel_event.clear()
            maskoption = args.masking_option.get()
            mask_option = UIConsts.MASKOPTIONS[maskoption]
            Configurator.getConfig().setProperty("processing","ListenerDefaultMasking", MaskingOptions.numToFriendlyString(mask_option))
            #phscripts.Watcher(args.input_dir.get(), False) 
            self.schedule_on_main_thread(self.stopbutton.configure, state="normal")
            phscripts.startWatcher(args.input_dir.get(),self.cancel_event) 

        except Exception as e:
            self.schedule_on_main_thread(messagebox.showerror, "Build Exception", str(e))
            raise e
        finally:
            self.schedule_on_main_thread(self.disable_enable_all, False)

    def __init__(self,container):

        super().__init__(container)
        maskoptionvals = [*UIConsts.MASKOPTIONS.keys()]
        self.watcher = None
        self.svars = WatchFormItems()
        self.cancel_event = threading.Event()

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
        self.stopbutton = ttk.Button(self,text="Cancel",state = "disabled",command=self.stop_watching)
        self.stopbutton.grid(column=1,row=5)
        self.clearbutton = ttk.Button(self,text="Purge Temp Directories",command=self.clear_directories)
        self.clearbutton.grid(column=3,row=5)
        self.state  = "stopped"
    
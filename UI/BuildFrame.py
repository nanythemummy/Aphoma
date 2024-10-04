
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from pathlib import Path
from UI.UIconsts import UIConsts
from UI.BuildConsole import BuildConsole
import photogrammetryScripts as phscripts
from threading import Thread


class BuildFormItems:

    def __init__(self):
        self.proj_base = StringVar()
        self.image_path = StringVar()
        self.mask_option = StringVar()
        self.proj_name= StringVar()

    def validate(self)->dict:
        msg = ""
        valid = False
        print(self.proj_base.get())
        projpath = Path(self.proj_base.get())
        imagest = Path(self.proj_base.get())
        if not self.proj_base.get() or not projpath.exists() or not projpath.is_dir():
            msg = "Please pick a project directory."
        elif not self.image_path.get() or not imagest.exists() or not imagest.is_dir():
            msg = "Please pick a folder containing images to build."
        elif not self.mask_option.get():
            msg = "Please select a masking option."
        elif not self.proj_name.get():
            msg = "Please name your project."
        else:
            valid = True
        return {"valid":valid,"message":msg}
    
class BuildFrame(ttk.Frame):
   
    def build(self,args:BuildFormItems):
        validate = args.validate()
        if not validate["valid"]:
            messagebox.showerror("Validation Error",validate["message"])
            return
        thread = Thread(target = lambda:self.buildThread(args))
        self.threads.append(thread)

        thread.start()

    def buildThread(self,args:BuildFormItems):
        phscripts.build_model(jobname = args.proj_name.get(),
                            inputdir = args.image_path.get(),
                            outputdir = args.proj_base.get(),
                            config = phscripts.CONFIG,
                            mask_option = UIConsts.MASKOPTIONS[args.mask_option.get()])

    def __init__(self,container):
        super().__init__(container)
        svars = BuildFormItems()
        vals = [*UIConsts.MASKOPTIONS.keys()]
        self.threads = []
        projnameentry = ttk.Entry(self, width=25, textvariable=svars.proj_name)
        projnameentry.grid(column=0,row=2,sticky=(W,E))
        ttk.Label(self,text="Image Folder Path").grid(column=0,row=4)
        ttk.Label(self,textvariable = svars.image_path,borderwidth=1, relief="solid").grid(column=0,row=5)
        ttk.Button(self,text="Browse",command = lambda:svars.image_path.set(filedialog.askdirectory())).grid(column=1,row=5)
        ttk.Label(self,text="Project Base Path").grid(column=0,row=6)
        ttk.Label(self,textvariable = svars.proj_base,borderwidth=1, relief="solid").grid(column=0,row=7)
        ttk.Button(self,text="Browse",command = lambda:svars.proj_base.set(filedialog.askdirectory())).grid(column=1,row=7)
        ttk.Label(self,text="Masking Technique").grid(column=0,row=8)
        maskoption = ttk.Combobox(self,textvariable=svars.mask_option, values=vals,state='readonly')
        maskoption.current(0)
        maskoption.grid(column=0,row=9)
        ttk.Button(self,text="Build",command=lambda:self.build(svars)).grid(column=0, row=10)
        self.console = BuildConsole(self)
        self.console.grid(columnspan=2, row = 11)
        
    
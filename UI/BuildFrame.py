
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from pathlib import Path
from UI.UIconsts import UIConsts
from UI.PipelineFrame import *
import photogrammetryScripts as phscripts
from util import util


class BuildFormItems(FormItemsInterface):

    def __init__(self):
        self.proj_base = StringVar()
        self.image_path = StringVar()
        self.mask_option = StringVar()
        self.proj_name= StringVar()
        self.pal_name = StringVar()
      

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
    
class BuildFrame(PipelineFrameBase):
    
    def task(self,args:BuildFormItems):
        try:
            self.disable_enable_all(True)
            self.config["photogrammetry"]["palette"] = args.pal_name.get()
            phscripts.build_model(jobname = args.proj_name.get(),
                                inputdir = args.image_path.get(),
                                outputdir = args.proj_base.get(),
                                config = self.config,
                                mask_option = UIConsts.MASKOPTIONS[args.mask_option.get()],
                                snapshot=True)

            
            
        except Exception as e:
            messagebox.showerror("Build Exception",e)
            util.getLogger(__name__).error(e)
            raise e
        finally:
            self.disable_enable_all(False)

    def __init__(self,container,config):

        super().__init__(container,config)
        self.svars = BuildFormItems()
        maskoptionvals = [*UIConsts.MASKOPTIONS.keys()]
        palettevals = util.getPaletteOptions()
        projnameentry = ttk.Entry(self, width=25, textvariable=self.svars.proj_name)
        projnameentry.grid(column=0,row=2,sticky=(W,E))
        ttk.Label(self,text="Image Folder Path").grid(column=0,row=4)
        ttk.Label(self,textvariable = self.svars.image_path,borderwidth=1, relief="solid").grid(column=0,row=5)
        ttk.Button(self,text="Browse",command = lambda:self.svars.image_path.set(filedialog.askdirectory())).grid(column=1,row=5)
        ttk.Label(self,text="Project Base Path").grid(column=0,row=6)
        ttk.Label(self,textvariable = self.svars.proj_base,borderwidth=1, relief="solid").grid(column=0,row=7)
        ttk.Button(self,text="Browse",command = lambda:self.svars.proj_base.set(filedialog.askdirectory())).grid(column=1,row=7)
        ttk.Label(self,text="Masking Technique").grid(column=0,row=8)
        ttk.Label(self,text="Palette").grid(column=0,row=10)
        maskoption = ttk.Combobox(self,textvariable=self.svars.mask_option, values=maskoptionvals,state='readonly')
        maskoption.current(0)
        maskoption.grid(column=0,row=9)
        paletteoption = ttk.Combobox(self,textvariable=self.svars.pal_name,values =palettevals,state='readonly')
        paletteoption.current(0)
        paletteoption.grid(column=0,row=11)
        ttk.Button(self,text="Build",command=lambda:self.execute(self.svars)).grid(column=0, row=12)


        
    
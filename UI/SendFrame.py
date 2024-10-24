from tkinter import *
from tkinter import ttk
from tkinter import messagebox, filedialog
from pathlib import Path
import photogrammetryScripts as phscripts
from UI.PipelineFrame import *


class SendFormItems(FormItemsInterface):

    def __init__(self):
        self.projectname = StringVar()
        self.input_dir = StringVar()
        self.should_prune = BooleanVar()
        self.target_dir = StringVar()

    def validate(self)->dict:
        msg = ""
        valid = False
        inputdir = Path(self.input_dir.get())
        if not self.input_dir.get() or not inputdir.exists() or not inputdir.is_dir():
            msg = "Pick a directory to listen on."
        elif not self.projectname.get():
            msg = "Name your project."
        elif not self.target_dir.get():
            msg = "Pick a directory to transfer these files to. It can be a network location."
        else:
            valid = True
        return {"valid":valid,"message":msg}
    
class SendFrame(PipelineFrameBase):
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
                
    def task(self,args:SendFormItems):
        try:
            self.disable_enable_all(True)
            self.state = "running"
            phscripts.PRUNE = args.prune.get()
            self.watcher = phscripts.Watcher(self.config,args.input_dir.get(), True, args.projname) 
            self.watcher.maskmode = 0
            self.stopbutton.configure(state="normal")
            self.watcher.run()
        except Exception as e:
            messagebox.showerror("Build Exception",e)
            raise e
        finally:
            self.disable_enable_all(False)

    def __init__(self,container,config):

        super().__init__(container,config)
        self.watcher = None
        self.svars = SendFormItems()

        ttk.Label(self,text="Project Name").grid(column=0,row=0)
        projectname = ttk.Entry(self, width=25, textvariable=self.svars.projectname)
        projectname.grid(column=0,row=1,sticky=("WE"))

        ttk.Label(self,text="Ortery Temp Directory").grid(column=0,row=2)
        self.svars.input_dir.set(config["watcher"]["listen_and_send"])
        directory = ttk.Entry(self, width=25, textvariable=self.svars.input_dir)
        directory.grid(column=0,row=3,sticky=("WE"))
        ttk.Button(self,text="Browse",command = lambda:self.svars.input_dir.set(filedialog.askdirectory())).grid(column=1,row=3)
       
        ttk.Label(self,text="Network Transfer Directory").grid(column=0,row=4)
        self.svars.target_dir.set(config["watcher"]["networkdrive"])
        transferdir = ttk.Entry(self, width=25, textvariable=self.svars.target_dir)
        transferdir.grid(column=0,row=5,sticky=("WE"))
        ttk.Button(self,text="Browse",command = lambda:self.svars.target_dir.set(filedialog.askdirectory())).grid(column=1,row=5)
 
        ttk.Checkbutton(self, text = "Prune?",variable = self.svars.should_prune, onvalue= True, offvalue=False ).grid(column=0, row=6)


        self.watchbutton = ttk.Button(self,text="Watch",command=lambda:self.execute(self.svars))
        self.watchbutton.grid(column=0, row=7)
        self.stopbutton = ttk.Button(self,text="Stop",state = "disabled",command=self.stop_watching())
        self.stopbutton.grid(column=1,row=7)
        self.state  = "stopped"
    
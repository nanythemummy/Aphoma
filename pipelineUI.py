from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from pathlib import Path
import photogrammetryScripts as phscripts

MASKOPTIONS = {"No Masks":0,
            "Context-Aware Select Droplet":1,
            "Magic Wand Droplet":2,
            "Otsu Thresholding":3,
            "Binary Thresholding":4}

def buildFrameSetup(parent):
    buildframe = ttk.Frame(parent,padding=10,borderwidth=1,relief='solid')
    buildframe.grid(column=0,row=0, sticky=(N,W,E,S))
    projname = StringVar()
    imagepath = StringVar()
    projbase = StringVar()
    maskoption = StringVar()
    vals = [*MASKOPTIONS.keys()]
    projnameentry = ttk.Entry(buildframe, width=25, textvariable=projname)
    projnameentry.grid(column=0,row=2,sticky=(W,E))
    projnameentry = ttk.Entry(buildframe, width=25, textvariable=projname)
    projnameentry.grid(column=0,row=2,sticky=(W,E))
    
    def validate():
        msg = ""
        ret = False
        print(projbase.get())
        projpath = Path(projbase.get())
        imagest = Path(imagepath.get())
        if not projbase.get() or not projpath.exists() or not projpath.is_dir():
            print("wut")
            msg = "Please pick a project directory."
        elif not imagepath.get() or not imagest.exists() or not imagest.is_dir():
            msg = "Please pick a folder containing images to build."
        elif not maskoption.get():
            msg = "Please select a masking option."
        elif not projname.get():
            msg = "Please name your project."
        else:
            ret = True
        if not ret:
            messagebox.showerror("Validation Error",msg)
        return ret

    def build():
        if not validate():
            return
        phscripts.build_model(jobname = projname.get(),
                              inputdir = imagepath.get(),
                              outputdir = projbase.get(),
                              config = phscripts.CONFIG,
                              mask_option = MASKOPTIONS[maskoption.get()])

    ttk.Label(buildframe,text="Image Folder Path").grid(column=0,row=4)
    ttk.Label(buildframe,textvariable = imagepath,borderwidth=1, relief="solid").grid(column=0,row=5)
    ttk.Button(buildframe,text="Browse",command = lambda:imagepath.set(filedialog.askdirectory())).grid(column=1,row=5)
    ttk.Label(buildframe,text="Project Base Path").grid(column=0,row=6)
    ttk.Label(buildframe,textvariable = projbase,borderwidth=1, relief="solid").grid(column=0,row=7)
    ttk.Button(buildframe,text="Browse",command = lambda:projbase.set(filedialog.askdirectory())).grid(column=1,row=7)
    ttk.Label(buildframe,text="Masking Technique").grid(column=0,row=8)
    
    maskoption = ttk.Combobox(buildframe,textvariable=maskoption, values=vals,state='readonly')
    maskoption.current(0)
    maskoption.grid(column=0,row=9)
    ttk.Button(buildframe,text="Build",command=build).grid(column=0, row=10)
    
    
    return buildframe
    
def mainWindowSetup(tkroot):
    frm = ttk.Frame(root,padding=10)
    frm.grid(column=0,row=0, sticky=(N,W,E,S))
    ttk.Label(frm,text="Photogrammetry Asset Pipeline").grid(column=0,row=0)
    _ = buildFrameSetup(frm)
    ttk.Button(frm,text="Quit",command = root.destroy).grid(column=1,row=1)
    return frm


root = Tk()
root.columnconfigure(0,weight=1)
root.rowconfigure(0,weight=1)
root.title("Photogrammetry Asset Pipeline")
frm = mainWindowSetup(root)
root.mainloop()

    
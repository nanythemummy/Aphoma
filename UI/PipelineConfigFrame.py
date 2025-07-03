import tkinter as tk
from tkinter import ttk

from tkinter import messagebox, filedialog
from pathlib import Path
import re
import json
import functools
import photogrammetryScripts as phscripts
from UI.PipelineFrame import *
from util.Configurator import Configurator

class ConfigFormItems(FormItemsInterface):

    def __init__(self):
        config = Configurator.getConfig()
        for section in config.getSections():
            setattr(self,section,{})
            for prop in config.getPropertiesForSection(section):
                val = config.getProperty(section,prop)
                sv = tk.StringVar()
                if isinstance(val,float):
                    t="float"
                elif isinstance(val,int) and type(val)==type(2):   #because bools are a type of int in python.
                    t ="int"
                elif isinstance(val,bool):
                    t= "bool"
                elif isinstance(val,dict):
                    t="dict"
                    val = json.dumps(val)
                elif isinstance(val,list):
                    t="list"
                    val = json.dumps(val)
                elif val and Path(val).exists():
                    t ="path"
                else:
                    t="string"
                sv.set(val)
                getattr(self,section)[prop]=(sv,t) 

    def validate(self)->dict:
        msg = ""
        floatpat  = re.compile(r"^\d+\.\d+$")
        intpat = re.compile(r"^\d+$")
        valid = True
        config = Configurator.getConfig()
        for section in config.getSections():
            props = getattr(self,section)
            for k,v in props.items():
                try:
                    itemval = v[0].get()
                    if v[1]=="string":
                        continue
                    if  itemval:
                        msg = f"Expecting value {k}:{v[0].get()} to be of type {v[1]}"
                        if v[1] == "int":
                            if not re.match(intpat,itemval):
                                valid = False
                        elif v[1]=="float":
                            if not re.match(floatpat,itemval):
                                valid=False
                        elif v[1] =="path":
                            pathitem = Path(itemval)
                            if not pathitem.exists():
                                valid = False
                        elif v[1]=="bool":
                            intitem = int(itemval)
                            valid = intitem==0 or intitem==1
                        elif v[1] == "dict":
                            try:
                                isinstance(json.loads(itemval),dict)
                            except json.decoder.JSONDecodeError:
                                valid = False
                        elif v[1] == "list":
                            try:
                                if not isinstance(json.loads(itemval),list):
                                    valid=False
                            except json.decoder.JSONDecodeError:
                                valid = False
                        if not valid:
                            break
                    else:
                        valid = False
                        msg = "Expecting Value in {k}"
                except Exception as e:
                    raise e
        return {"valid":valid,"message":msg}
    
    
                    

class ConfigWindow(tk.Toplevel):


    def resetConfig(self):
        Configurator.reloadConfigFromFile()

    def castToType(self, prop,t):
        ret = prop
        if  t == "int":
            ret = int(prop)  
        elif t =="float":
            ret = float(prop)
        elif t =="path":
            ret = Path(prop)
        elif t=="bool":
            ret = True if prop=="1" else False
        elif t == "dict" or t=="list":
            ret = json.loads(prop)
        return ret
    
    def setConfigVals(self):
        validate = self.svars.validate()
        if validate["valid"]:
            config = Configurator.getConfig()
            for section in config.getSections():
                sectionconfig = getattr(self.svars,section)
                for prop in config.getPropertiesForSection(section):
                    p = sectionconfig[prop][0].get()
                    t = sectionconfig[prop][1]
                    loaded = self.castToType(p,t)
                    config.setProperty(section,prop,loaded)
        else:
            messagebox.showerror("Validation Error", validate["message"])


    def __init__(self,container):
        def set_path(configname,variablename):
            varname = getattr(self.svars,configname)
            fn = filedialog.askopenfilename()
            varname[variablename][0].set(fn)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * event.delta/120),"units")
        super().__init__(container)

        self.geometry("500x500")
        frame = ttk.Frame(self)
        frame.grid(row=0,column=0,sticky="nsew")

        # Create canvas and scrollbar as children of 'frame'
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Create the interior frame inside the canvas
        interiorframe = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=interiorframe, anchor="nw")
        interiorframe.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Configure grid weights for resizing
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # Place widgets
        canvas.grid(column=0, row=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Bind mousewheel to canvas only
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        rowcounter = 0
        config = Configurator.getConfig()
        self.svars = ConfigFormItems()
        for k in config.getSections():
            ttk.Label(interiorframe, text=k).grid(column=0, row=rowcounter)
            ttk.Separator(interiorframe, orient="horizontal")
            rowcounter += 1
            for a in config.getPropertiesForSection(k):
                ttk.Label(interiorframe, text=a).grid(column=0, row=rowcounter)
                ttk.Entry(interiorframe, textvariable=getattr(self.svars, k)[a][0]).grid(column=1, row=rowcounter)
                if getattr(self.svars, k)[a][1] == "path":
                    ttk.Button(interiorframe, text="Browse",
                                command=functools.partial(set_path, configname=k, variablename=a)).grid(column=2, row=rowcounter)
                rowcounter += 1
        ttk.Button(interiorframe, text="OK", command=lambda: self.setConfigVals()).grid(column=1, row=rowcounter)

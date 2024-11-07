import tkinter as tk
from tkinter import ttk

from tkinter import messagebox, filedialog
from pathlib import Path
import re
import json
import functools
import photogrammetryScripts as phscripts
from UI.PipelineFrame import *

class ConfigFormItems(FormItemsInterface):

    def __init__(self,config):
        for k,v in config.items():
            if isinstance(v,dict):
                setattr(self,k,{})
                for k1,v1 in v.items():
                    val = v1
                    sv = tk.StringVar()
                    t = "string"
                    if isinstance(v1,float):
                        t="float"
                    if isinstance(v1,int):
                        t ="int"
                    elif isinstance(v1,dict):
                        val = json.dumps(v1)
                        t="dict"
                    elif isinstance(v1,list):
                        val = json.dumps(v1)
                        t="list"
                    else:
                        if v1 and Path(v1).exists():
                            t = "path"

                    sv.set(val)
                    getattr(self,k)[k1]=(sv,t) 

    def validate(self)->dict:
        msg = ""
        floatpat  = re.compile(r"^\d+\.\d+$")
        intpat = re.compile(r"^\d+$")
        valid = True
        for attr in dir(self):
            if isinstance(getattr(self,attr),dict):
                for k,v in getattr(self,attr):

                    try:
                        if v[0].get():
                            msg = f"Expecting value {k}:{v[0]} to be of type{v[1]}"
                            if v[1] == "int":
                                if not re.match(intpat,v[0].get()):
                                    valid = False
                            elif v[1]=="float":
                                if not re.match(floatpat,v[0].get()):
                                    valid=False
                            elif v[1] =="path":
                                if not Path(v[0].get()).exists():
                                    valid = False
                            elif v[1] == "dict":
                                try:
                                    isinstance(json.loads(v[0].get),dict)
                                except json.decoder.JSONDecodeError:
                                    valid = False
                            elif v[1] == "list":
                                try:
                                    if not isinstance(json.loads(v[0].get),list):
                                        valid=False
                                except json.decoder.JSONDecodeError:
                                    valid = False
                            if not valid:
                                break
                        else:
                            valid = False
                            msg = "Expecting Value in {k}"
                    except Exception:
                        continue
        return {"valid":valid,"message":msg}
    
                    

class ConfigWindow(tk.Toplevel):


    def resetConfig(self):
        with open("config.json", "r",encoding="utf-8") as f:
            self.config = json.load(f)["config"]
        self.svars = ConfigFormItems(self.config)

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

        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(self,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        interiorframe = ttk.Frame(canvas)
        interiorframe.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        
        self.columnconfigure(0,weight=1)
        self.rowconfigure(0,weight=1)
        frame.columnconfigure(0,weight=1)
        frame.columnconfigure(0,weight=1)

        interiorframe.grid(column=0,row=0,sticky="nsew")
        scrollbar.grid(row=0,column=1,sticky="ns")
        canvas.grid(column=0,row=0,sticky="nsew")
        canvas.bind_all("<MouseWheel>",_on_mousewheel)


        rowcounter = 0
        self.resetConfig()
        for k,v in self.config.items():
            if isinstance(v,dict):
                ttk.Label(interiorframe,text=k).grid(column=0,row=rowcounter)
                ttk.Separator(interiorframe,orient="horizontal")
                rowcounter+=1
                for a in v.keys():
                    ttk.Label(interiorframe,text=a).grid(column=0,row = rowcounter)
                    ttk.Entry(interiorframe,textvariable=getattr(self.svars,k)[a][0]).grid(column=1,row=rowcounter)
                    if getattr(self.svars,k)[a][1]=="path":
                        ttk.Button(interiorframe,text="Browse",
                                   command=functools.partial(set_path,configname=k,variablename=a)).grid(column=2,row=rowcounter)
                    rowcounter+=1
    
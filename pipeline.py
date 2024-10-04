import tkinter as tk
from UI.BuildFrame import BuildFrame



class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FM/ISAC Photogrammetry Pipeline")
        build = BuildFrame(self)
        build.configure(padding=10)
        build.grid(column=0,row=0, sticky=(tk.N,tk.W,tk.E,tk.S))
        

if __name__=="__main__":
    app= MainApp()
    app.mainloop()

from tkinter import END
from tkinter.scrolledtext import ScrolledText
import sys
import os
import threading
import time
import logging



class BuildConsole(ScrolledText):
    
    def __init__(self,parent):
        super().__init__(parent)

class TextHanlder(logging.Handler):
    def __init__(self,text):
        logging.Handler.__init__(self)
        self.text = text
    def emit(self,record):
        msg = self.format(record)
        def append():
            self.text.configure(state="normal")
            self.text.insert(END, msg+'\n')
            self.text.configure(state='disabled')
            self.text.yview(END)
        self.text.after(0,append)
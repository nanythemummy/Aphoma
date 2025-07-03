from tkinter import END
from tkinter.scrolledtext import ScrolledText
import sys
import os
import threading
import time
import logging



class BuildConsole(ScrolledText):
    
    def __init__(self, parent):
        super().__init__(parent)
        # Bind mouse wheel locally to this widget
        self.bind("<Enter>", self._bind_mousewheel)
        self.bind("<Leave>", self._unbind_mousewheel)

    def _on_mousewheel(self, event):
        # For Windows, use event.delta
        self.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _bind_mousewheel(self, event=None):
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.unbind_all("<MouseWheel>")

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
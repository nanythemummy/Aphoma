from tkinter import END
import platform
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
        if platform.system() == 'Darwin':  # macOS
            self.yview_scroll(-1 * event.delta, "units")
        else:
            self.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _bind_mousewheel(self, event=None):
        if platform.system() == 'Darwin':
            self.bind_all("<MouseWheel>", self._on_mousewheel)
            self.bind_all("<Button-4>", lambda e: self.yview_scroll(-1, "units"))
            self.bind_all("<Button-5>", lambda e: self.yview_scroll(1, "units"))
        else:
            self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.unbind_all("<MouseWheel>")
        if platform.system() == 'Darwin':
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")


class TextHandler(logging.Handler):
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
import abc
from tkinter import ttk
from tkinter import messagebox
import threading

class FormItemsInterface(metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return (hasattr(subclass,'validate')and 
                callable(subclass.validate)or 
                NotImplemented)
    @abc.abstractmethod
    def validate(self)->dict:
        raise NotImplementedError


class PipelineFrameBase(ttk.Frame):
    def execute(self,args:FormItemsInterface):
        validate = args.validate()
        if not validate["valid"]:
            messagebox.showerror("Validation Error", validate["message"])
            return
        thr = threading.Thread(target=lambda:self.task(args),daemon=False)
        self.threads.append(thr)
        thr.start()

    def task(self,args:FormItemsInterface):
        #subclasses need to implement this.
        pass

    def schedule_on_main_thread(self, func, *args, **kwargs):
        """Schedule a UI operation to run on the main Tkinter thread."""
        self.after(0, lambda: func(*args, **kwargs))

    def __init__(self,container):
        super().__init__(container)
        self.threads = []

    def disable_enable_all(self,disable=True):
         for child in self.winfo_children():
            if isinstance(child,ttk.Button):
                if not disable:
                    child.configure(state='normal')
                else:
                    if child.cget("text").lower() != "cancel":
                         child.configure(state='disabled')

    def destroy(self):
        super().destroy()
        for t in self.threads:
            t.join()
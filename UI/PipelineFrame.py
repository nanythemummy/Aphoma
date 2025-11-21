import abc
from tkinter import ttk
from tkinter import messagebox
from threading import Thread

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
        thr = Thread(target=lambda:self.task(args),daemon=False)
        self.threads.append(thr)
        thr.start()

    def task(self,args:FormItemsInterface):
        #subclasses need to implement this.
        pass

    def __init__(self,container):
        super().__init__(container)
        self.threads = []

    def disable_enable_all(self,disable=True):
         for child in self.winfo_children():
            if child.widgetName != 'frame':
                if not disable:
                    child.configure(state='normal')
                else:
                    child.configure(state='disabled')
    def destroy(self):
        super().destroy()
        for t in self.threads:
            t.join()
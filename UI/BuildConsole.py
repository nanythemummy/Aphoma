from tkinter import END
from tkinter.scrolledtext import ScrolledText
import sys
import os
import threading
import time

# class COutputGetter(object):
#     #cribbed from https://stackoverflow.com/questions/24277488/in-python-how-to-capture-the-stdout-from-a-c-shared-library-to-a-variable#:~:text=More%20simply,%20the%20Py%20library%20has
#     escape_char='\b'
#     def __init__(self,stream=None,threaded=False,targetwidget = None):
#         self.origstream = stream
#         self.threaded = threaded
#         if self.origstream is None:
#             self.origstream = sys.stdout
#         self.origstreamfile = self.origstream.fileno()
#         self.streamfile = None
#         self.outputmsg = ""
#         self.pipe_out, self.pipe_in = os.pipe()
#         self.targetwidget = targetwidget
    
#     def __enter__(self):
#         self.start()
#         return self
    
#     def __exit__(self,type,value,traceback):
#         self.stop()
    
#     def start(self):
#         #saves off the current file descriptor, in the streamfile class variable and replace it with the pipe_in pipe.
#         self.capturedtext = ""
#         self.streamfile = os.dup(self.origstreamfile)
#         os.dup2(self.pipe_in,self.origstreamfile)
#         if self.threaded:
#             self.workerThread = threading.Thread(target = self.readOutput)
#             self.workerThread.start()
#             time.sleep(0.01)
    
#     def stop(self):
#         self.origstream.flush
#         self.origstream.write(self.escape_char)
#         self.origstream.flush()
#         if self.threaded:
#             self.workerThread.join()
#         else:
#             self.readOutput()
#         os.close(self.pipe_in)
#         os.close(self.pipe_out)
#         os.dup2(self.streamfile,self.origstreamfile)
#         os.close(self.streamfile)

#     def readOutput(self):
#         msg = ""
#         while True:
#             char = os.read(self.pipe_out,1).decode(self.origstream.encoding)
#             if not char or char is self.escape_char:
#                 break
#             msg+=char
#             if "\n" in char:
#                 self.outputmsg+=msg
#                 self.targetwidget.write(msg)
#                 self.origstream.flush()

class BuildConsole(ScrolledText):
    
    def __init__(self,parent):
        super().__init__(parent)
        sys.stdout = self

    def write(self,textstr):
        self.insert(END, textstr)

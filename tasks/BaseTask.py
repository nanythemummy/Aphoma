
from enum import Enum
from util.PipelineLogging import getLogger

class TaskStatus(Enum):
    """Class containing constants for state status."""
    NONE = 0
    SETUP = 1
    RUNNING = 2
    FINISHED = 3

class BaseTask():
    """Generic  base class for states"""

    def __init__(self, name):
        self._shouldFinish = False
        self._status = TaskStatus.NONE
        self._statename = name
        
    def setup(self)->bool:
        self._status = TaskStatus.SETUP
        getLogger(__name__).info("Starting %s",self._statename)
        return True
    def exit(self)->bool:
        self._status = TaskStatus.FINISHED
        getLogger(__name__).info("Exiting %s",self._statename)
        return True
    def execute(self)->bool:
        self._status = TaskStatus.RUNNING
        getLogger(__name__).info("Executing %s",self._statename)
        return True
    def getStatus(self)->int:
        return self._status
    def getName(self)->str:
        return self._statename
    
    

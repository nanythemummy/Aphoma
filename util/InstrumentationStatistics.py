from enum import Enum
from datetime import datetime,timedelta
from util import util
from functools import reduce
from uuid import uuid4

class Statistic_Event_Types(Enum):
    EVENT_CONVERT_PHOTO = 0
    EVENT_BUILD_MASK = 1
    EVENT_BUILD_MODEL = 2
    EVENT_SNAPSHOT = 3
    EVENT_TAKE_PHOTO = 4

    @classmethod
    def getPrettyString(cls, value:int):
        pretty_event_strings = ["Conversion of photos",
                                "Building Masks",
                                "Building Models",
                                "Model Snapshot",
                                "Photography"]
        return pretty_event_strings[value]
    
    @classmethod
    def getIteratable(cls):
        return[cls.EVENT_CONVERT_PHOTO,cls.EVENT_BUILD_MASK,cls.EVENT_BUILD_MODEL,cls.EVENT_SNAPSHOT,cls.EVENT_TAKE_PHOTO]



class Statistics_Timed_Event():
    def __init__(self, type:Statistic_Event_Types):
        self._start =0
        self._end = 0
        self.type = type
        self.id = uuid4()
        self.start()

    def start(self,t:datetime=None):
        if not t:
            self._start = datetime.now()
        else:
            self._start = t
    def end(self,t:datetime=None):
        if t is None:
            self._end = datetime.now()
        else:
            self._end = t
    def isCompleted(self):
        return self._start and self._end
    def getDuration(self):
        return self._end-self._start

class InstrumentationStatistics():

    _STATISTICS = None
    
    def __init__(self):
        self.events={}
        self.completed = {}

    def logReport(self):
        logger = util.getLogger(__name__)
        accumulatedtime = timedelta(0)
        for s in Statistic_Event_Types.getIteratable():
            if s.name in self.completed.keys():
                arrayofevents = self.completed[s.name]
                totaltime = timedelta(0)
                for e in arrayofevents:
                    totaltime += e.getDuration()
                ave = totaltime/len(arrayofevents)
                accumulatedtime += totaltime
                logger.info("Time for %s: %s, on average, %s.",Statistic_Event_Types.getPrettyString(s.value),
                            totaltime,ave)
        logger.info("Total build time: %s",accumulatedtime)

    def timeEventStart(self,type:Statistic_Event_Types,starttime = None): 
        evt = Statistics_Timed_Event(type)
        if starttime:
            if isinstance(starttime,str):
                starttime = datetime.strptime(starttime,"%Y-%m-%d %H:%M:%S.%f")
            if isinstance(starttime,datetime):
                evt.start(starttime)
        self.events[evt.id] = evt
        return evt.id
    
    def timeEventEnd(self,id,endtime=None):
        evt = self.events[id]
        if endtime:
            if isinstance(endtime,str):
                endtime = datetime.strptime(endtime,"%Y-%m-%d %H:%M:%S.%f")
            if isinstance(endtime,datetime):
                evt.end(endtime)
        else:
            evt.end()
        if evt.type.name not in self.completed.keys(): #using the string for the key for readability
            self.completed[evt.type.name] = []
        self.completed[evt.type.name].append(evt)

    
    @staticmethod
    def getStatistics():
        if not InstrumentationStatistics._STATISTICS:
            InstrumentationStatistics._STATISTICS = InstrumentationStatistics()
        return InstrumentationStatistics._STATISTICS
    
    @staticmethod
    def destroyStatistics():
        InstrumentationStatistics._STATISTICS = None
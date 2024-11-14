import json
import re
import logging
from pathlib import Path
from util.PipelineLogging import getLogger


class Configurator():
    _CONFIG = None

    def loadFrom(self,filename:Path):
        with open(self._cfgfile,'r', encoding="utf-8") as f:
            cfg= json.load(f)["config"]
        return cfg

    def __init__(self):
        self._cfgfile = Path(Path(__file__).parent.parent, Path("config.json"))
        self._template = Path(Path(__file__).parent.parent, Path("config_template.json"))
        self._config = self.loadFrom(self._cfgfile)

    def setProperty(self, section, keyname, val):
        try:
            self._config[section][keyname]=val
            getLogger(__name__).info("Set config %s:%s to %s",section,keyname,val)
        except KeyError as ke:
            getLogger(__name__).error(ke)
            raise ke
    def getProperty(self,section,keyname):
        try:
            return self._config[section][keyname]
        except KeyError as ke:
            getLogger(__name__).error(ke)
            return None
    def revertToTemplate(self):
        self._cfgfile = self.loadFrom(self._template)
    
    def saveConfig(self):
        with open(self._cfgfile,'w', encoding="utf-8") as f:
            json.dump(self._config,f)
    
    def getPropertiesForSection(self,sectionname):
        try:
            return self._config[sectionname].keys()
        except KeyError as ke:
            getLogger(__name__).error(ke)
            return []

    def getSections(self):
        return self._config.keys()
               

    @staticmethod 
    def getConfig():
        if Configurator._CONFIG  is None:
            Configurator._CONFIG = Configurator()
        return Configurator._CONFIG

    @staticmethod
    def reloadConfigFromFile():
        Configurator._CONFIG = Configurator()
        return Configurator._CONFIG
    



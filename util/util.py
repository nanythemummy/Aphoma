"""Utility functions, mainly for dealing with configuration."""
from pathlib import Path, PurePath
import json
import logging
import shutil
import os
from datetime import datetime



def getPaletteOptions():
    pals = {}
    with open(PurePath(Path(__file__).parent,"MarkerPalettes.json"), 'r',encoding="utf-8") as f:
        pals = json.load(f)
    return list(pals["palettes"].keys())

def getLogger(name):
    
    if name == "__main__":
        logger = logging.getLogger()
        logging.config.fileConfig('logging.conf')
    else:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
    return logger
def addLogHandler(handler):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger  = logging.getLogger()
    logger.addHandler(handler)
class MaskingOptions:
    """Class containing constants for masking options."""

    NOMASKS = 0
    MASK_CONTEXT_AWARE_DROPLET = 1
    MASK_MAGIC_WAND_DROPLET =2
    MASK_CANNY = 3
    MASK_THRESHOLDING = 4
    FRIENDLY = ["None", "SmartSelectDroplet","FuzzySelectDroplet","Thresholding","EdgeDetection"]
    @staticmethod
    def numToFriendlyString(num:int):
        return MaskingOptions.FRIENDLY[num]
    @staticmethod 
    def friendlyToNum(friendly:str):

        for i,fr in enumerate(MaskingOptions.FRIENDLY):
            if fr is friendly:
                return i
        return 0

        

def copy_file_to_dest(sourcefiles:list,destpath:str, deleteoriginal=False):
    """Moves file from source to destination
    
    Parameters:
    --------------
    * sourcefiles: a list of the files to move. [list of files]
    * destpath: a string path to move them to.
    """
    if not os.path.exists(destpath):
         os.mkdir(destpath)
    for f in sourcefiles:
        try:
            if deleteoriginal:
                shutil.move(f,destpath, shutil.copy)
            else:
                shutil.copy(f,destpath)
        except shutil.Error as e:
            print(e)
            #swallow it and keep the original.
            
def get_camera_lens_profile(cameraprofile,lensprofile):
    """Gets the appropriate model and make information from the config file for ther specified camera profile. May be deprecated now that we are no longer
    doing lens profile corrections as part of the processing.
    
    Parameters:
    -----------------
    cameraprofile: the value of config.json->processing->Camera, that is, the name of the camera profile as defined in util/cameraprofiles.json.
    lensprofile: the value of config.json->processing->Lens, that is, the name of the lens profile as defined in util/cameraprofiles.

    returns: a dictionary containing the make and model of the lens and camera.
    """
    setupinfo = {"lens":None,
                 "camera":None}
    profiles = {}
    with open("util/CameraProfiles.json") as f:
        profiles= json.load(f)
    if cameraprofile in profiles["cameras"].keys():
        setupinfo["camera"] = profiles["cameras"][cameraprofile]
    if lensprofile in profiles["lenses"].keys():
        setupinfo["lens"] = profiles["lenses"][lensprofile]
    return setupinfo

class Statistics():

    _STATISTICS = None

    def __init__(self):
        self.photostart = \
        self.photoend  = \
        self.maskingstart  = \
        self.maskingend= \
        self.modelstart = \
        self.modelend = None
    
    def logReport(self):
        logger = getLogger(__name__)
        if self.photoend and self.photostart:
            phototime = self.photoend-self.photostart
            logger.info("Time to take photos: %s",phototime)

        if self.maskingstart and self.maskingend:
            maskingtime = 0
            if self.maskingend>self.photoend:
                if self.maskingstart<self.photoend:
                    maskingtime = self.maskingend-self.photoend #if masking time and photo time overlaps.
                else:
                    maskingtime = self.maskingend-self.maskingstart
            logger.info("Time to mask not overlapping with photography: %s", maskingtime)
        if self.modelend and self.modelstart:
            modeltime = self.modelend-self.modelstart
            logger.info("Time to build model: %s",modeltime)

    @staticmethod
    def getStatistics():
        if not Statistics._STATISTICS:
            Statistics._STATISTICS = Statistics()
        return Statistics._STATISTICS
    
    @staticmethod
    def destroyStatistics():
        Statistics._STATISTICS = None
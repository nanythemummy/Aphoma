"""Utility functions, mainly for dealing with configuration."""
from os import path
from pathlib import Path, PurePath
import json
import logging
import shutil
import os
from datetime import datetime




def getPaletteOptions():
    pals = {}
    with open(Path(Path(__file__).parent,"MarkerPalettes.json"), 'r',encoding="utf-8") as f:
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


def load_palettes():
    """Loads MarkerPalettes.json and returns a dictionary of different palettes.
    Different marker palettes may be used while doing photo capture in order to perform various calculations at the 
    model building stage. The palette used is specified in config.json->photogrammetry-> palette, which is used as a key to locate
    the specific data needed for each palette. This data is stored in MarkerPalettes.json
    """

    #going to hardcode this path for now. Maybe come back and configure it.
    palette = {}
    with open(path.join("util/MarkerPalettes.json"), encoding = "utf-8") as f:
        palette = json.load(f)
    return palette["palettes"]


def get_export_filename(chunkname:str,config:dict, type:str):
    """Constructs a filename for the export encoding features of the model such as the scale unit and filetype.

    Parameters:
    ------------------
    chunkname: Should be the acession nubmer of the object.
    config: a dictionary of config values, probably under Photogrammetry in config.json"

    returns:string with proposed filename for export file. """
    scaleunit ="mm"
    if config["palette"]:
        palette = load_palettes()[config["palette"]]
        scaleunit = palette["unit"]
    type = type.replace('.','')
    exporttype = type.upper()
    exportname=f"{chunkname}_PhotogrammetryScaledIn{scaleunit}{exporttype}"
    return exportname


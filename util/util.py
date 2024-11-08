"""Utility functions, mainly for dealing with configuration."""

from pathlib import Path, PurePath
import json
import logging.config
import shutil
import os
import re
import argparse
from enum import Enum





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

class MaskingOptions(Enum):
    """Class containing constants for masking options."""
    NOMASKS = 0
    MASK_CONTEXT_AWARE_DROPLET = 1
    MASK_MAGIC_WAND_DROPLET =2
    MASK_CANNY = 3
    MASK_THRESHOLDING = 4
     
    @classmethod 
    def getFriendlyStrings(cls):
        return ["None", "SmartSelectDroplet","FuzzySelectDroplet","EdgeDetection","Thresholding"]
    @classmethod
    def numToFriendlyString(cls, num): 
        if isinstance(num, MaskingOptions):
            num = num.value
        return MaskingOptions.getFriendlyStrings()[num]
    @classmethod 
    def friendlyToEnum(cls, searchstring:str):
        friendly = MaskingOptions.getFriendlyStrings()
        for i,fr in enumerate(friendly):
            if fr is searchstring:
                return MaskingOptions(i)
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


def should_prune(filename: str,config:dict)->bool:
    """Takes a file name and figures out based on the number in it whether the picture should be sent or not and added to the manifest or not. It assumes files are named ending in a number and that
    this is sequential based on when the camera took the picture.
    Parameters
    -----------------
    filename: The filename in question.

    returns: True or false based on whether the file ought to be omitted.
    """
    shouldprune = False
    numinround = config["pics_per_revolution"]
    numcams = len(config["pics_per_cam"].keys())
    basename_with_ext = os.path.split(filename)[1]
    fn = os.path.splitext(basename_with_ext)[0]
    try:
        t = re.match(r"[a-zA-Z]*_*(\d+)$",fn)
        filenum = int(t.group(1)) #ortery counts from zero.
        camnum = int(filenum/numinround)+1
        picinround = filenum%(numinround)+1
        expected = config["pics_per_cam"][str(camnum)]
        print(f"{fn} is pic number {picinround} of camera {camnum}. The expected number in this round is {expected}")
        if expected < numinround:
            invert = False
            if (numinround-expected)/numinround <0.5:
                divisor = round(numinround/(numinround-expected))
            else:
                divisor = round(numinround/expected)
                invert = True
            if (picinround %divisor==0) and invert is False:
                shouldprune=True
            elif (picinround % divisor != 0) and invert is True:
                shouldprune = True
            
    except AttributeError:
        print(f"Filename {fn} were not in format expected: [a-zA-Z]*_*\\d+$.xxx . Forgoing pruning.")
        shouldprune = False

    return shouldprune

def cmd_test_prune(args):

    pat = re.compile(r"[a-zA-Z]*_*(\d+)$")
    def sortonpat(x):
        x = Path(x).stem
        t1= re.match(pat,x)
        g = t1.group(1)
        return int(g)
    cpath = Path(Path(__file__).parent.parent,"config.json")
    config = {}
    prunelist = []
    with open(cpath,"r",encoding = 'utf-8') as f:
        config=json.load(f)["config"]
    paths = list(Path(args.imagedir).glob("*.jpg"))
    paths.sort(key=sortonpat)
    for f in paths:
        if should_prune(f,config["ortery"]):
            print(f"pruning {f}")
        else:
            prunelist.append(f)
    prunelist.sort()
    print(prunelist)
    print(len(prunelist))



if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="buildManifest")
    parser.add_argument("imagedir",help="Directory of images for which to build a manifest")
    args = parser.parse_args()
    cmd_test_prune(args)


def load_palettes():
    """Loads MarkerPalettes.json and returns a dictionary of different palettes.
    Different marker palettes may be used while doing photo capture in order to perform various calculations at the 
    model building stage. The palette used is specified in config.json->photogrammetry-> palette, which is used as a key to locate
    the specific data needed for each palette. This data is stored in MarkerPalettes.json
    """

    #going to hardcode this path for now. Maybe come back and configure it.
    palette = {}
    with open(Path(Path(__file__).parent,"MarkerPalettes.json"), encoding = "utf-8") as f:
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
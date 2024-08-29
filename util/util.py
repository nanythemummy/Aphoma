"""Utility functions, mainly for dealing with configuration."""
from sys import platform
import json
import shutil
import os
class MaskingOptions:
    """Class containing constants for masking options."""
    NOMASKS = 0
    MASK_DROPLET = 1
    MASK_ARBITRARY_HEIGHT = 2

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
            
        
def get_config_for_platform(config):
    """For the operations that shell out to a third party app, the paths may be fundamentally different on Windows/Mac. This function may be
    deprecated now that each computer has its own config.json file.
    
    Anyway, basically, you pass in the config value you want, and this will get the value for the appropriate platform key from the config dictionary
    so I don't have to repeat this block of code everywhere.
    Parameters:
    ----------------
    Config: the subset of the config dictionary with configurations that might vary by platform. For example: config["processing"]["Masking_Droplet"]
    """

    if platform.startswith("linux"):
        return config["Linux"]
    elif platform == "darwin":
        return config["Mac"]
    else:
        return config["Win"]

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


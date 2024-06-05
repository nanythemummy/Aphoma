from sys import platform
import json

def getConfigForPlatform(config):
    #In the json config, differing options for platform should folllow the format:
    #optionname:{
    #platformname:platformval
    #}
    #where possible platforms are Mac, Win, Linux.
    #The dictionary passed in here ought to be "optionname"
    if platform.startswith("linux"):
        return(config["Linux"])
    elif platform == "darwin":
        return(config["Mac"])
    else:
        return(config["Win"])
    
def getCameraLensProfiles(cameraprofile,lensprofile):
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


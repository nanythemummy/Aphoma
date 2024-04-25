import rawpy, subprocess, imageio
from os import path
from sys import platform
from pathlib import Path

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
    
def convertCR2toDNG(input,output,config):
    outputcmd = f"-d \"{output}/\""
    print(outputcmd)
    converterpath = getConfigForPlatform(config["processing"]["DNG Converter"])
    subprocess.run([converterpath,"-d",output,"-c", input])

def convertCR2toTIF(input,output,config):
    fn = Path(input).stem
    with rawpy.imread(input) as raw:
        rgb = raw.postprocess(use_camera_wb=True)
        imageio.imsave(path.join(output,fn+".tif"),rgb)
def getWhiteBalance(rawpath):
    with rawpy.imread(rawpath) as raw:
        return raw.camera_whitebalance


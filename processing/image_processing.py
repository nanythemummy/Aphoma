import rawpy, subprocess, imageio
from os import path
from sys import platform
from pathlib import Path
from util import util


    
def convertCR2toDNG(input,output,config):
    outputcmd = f"-d \"{output}/\""
    print(outputcmd)
    converterpath = util.getConfigForPlatform(config["processing"]["DNG Converter"])
    subprocess.run([converterpath,"-d",output,"-c", input])

def convertCR2toTIF(input,output,config):
    fn = Path(input).stem
    with rawpy.imread(input) as raw:
        rgb = raw.postprocess(use_camera_wb=True)
        imageio.imsave(path.join(output,fn+".tif"),rgb)
def getWhiteBalance(rawpath):
    with rawpy.imread(rawpath) as raw:
        return raw.camera_whitebalance


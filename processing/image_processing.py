import os
import rawpy, subprocess, imageio
import numpy
from sys import platform
from pathlib import Path
from util import util
import cv2
import shutil

def buildMasks( imagefolder, outputpath, config):
    dropletpath = util.getConfigForPlatform(config["Masking_Droplet"])
    dropletoutput = util.getConfigForPlatform(config["Droplet_Output"])
    if not dropletpath:
        print("Cannot build mask with a non-existent droplet. Please specify the droplet path in the config under processing->Masking_Droplet.")
        return
    else:
        print(f" Using Droplet at {dropletpath}")
    maskdir = outputpath
    if not os.path.exists(maskdir):
        os.mkdir(maskdir)
    if not os.path.exists(dropletoutput):
        os.mkdir(dropletoutput)
    #droplet should dump files in c:\tempmask or \tempmask
    subprocess.run([dropletpath,imagefolder],check = False)
    with os.scandir(dropletoutput) as it: #scans through a given directory, returning an interator.
        for f in it:
            if os.path.isfile(f):
                oldpath = f.path
                filename = f.name
                shutil.move(oldpath,os.path.join(maskdir,filename))
    shutil.rmtree(dropletoutput)


def convertCR2toDNG(input,output,config):
    outputcmd = f"-d \"{output}/\""
    converterpath = util.getConfigForPlatform(config["DNG_Converter"])
    subprocess.run([converterpath,"-d",output,"-c", input], check = False)

def convertCR2toTIF(input,output,config):
    fn = Path(input).stem
    with rawpy.imread(input) as raw:
        rgb = raw.postprocess(use_camera_wb=True)
        imageio.imsave(path.join(output,fn+".tif"),rgb)

def convertToJPG(input, output):
    fn = Path(input).stem #get the filename.
    ext = os.path.splitext(input)[1].upper()
    if ext==".TIF":
        try:
            f=cv2.imread(input)
            cv2.imwrite(os.path.join(output,fn+".jpg"),f,[int(cv2.IMWRITE_JPEG_QUALITY),100])
        except Exception as e:
            raise e
    elif ext ==".CR2":
        with rawpy.imread(input) as f:
            processedimage = f.postprocess(use_camera_wb=True)
            imageio.save(os.path.join(output,fn+".jpg"),processedimage)

def getWhiteBalance(rawpath):
    with rawpy.imread(rawpath) as raw:
        return raw.camera_whitebalance
    
def getGrayFromCard(cardpath):
    pass



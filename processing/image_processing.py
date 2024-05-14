import rawpy, subprocess, imageio
import numpy
from os import path
from sys import platform
from pathlib import Path
from util import util

import cv2

    
def convertCR2toDNG(input,output,config):
    outputcmd = f"-d \"{output}/\""
    converterpath = util.getConfigForPlatform(config["DNG_Converter"])
    subprocess.run([converterpath,"-d",output,"-c", input])

def convertCR2toTIF(input,output,config):
    fn = Path(input).stem
    with rawpy.imread(input) as raw:
        rgb = raw.postprocess(use_camera_wb=True)
        imageio.imsave(path.join(output,fn+".tif"),rgb)

def convertToJPG(input, output):
    fn = Path(input).stem #get the filename.
    ext = path.splitext(input)[1].upper()
    if ext==".TIF":
        try:
            f=cv2.imread(input)
            cv2.imwrite(path.join(output,fn+".jpg"),f,[int(cv2.IMWRITE_JPEG_QUALITY),100])
        except Exception as e:
            raise e
    elif ext ==".CR2":
        with rawpy.imread(input) as f:
            processedimage = f.postprocess(use_camera_wb=True)
            imageio.save(path.join(output,fn+".jpg"),processedimage)

def getWhiteBalance(rawpath):
    with rawpy.imread(rawpath) as raw:
        return raw.camera_whitebalance
    
def getGrayFromCard(cardpath):
    card = cv2.imread(cardpath)
    grayboundaries = ([170,170,170],[190,190,190]) #Hardcoded.
    #Colorbalance approach here seems promising.
    #https://pyimagesearch.com/2021/02/15/automatic-color-correction-with-opencv-and-python/

    lower = numpy.array(grayboundaries[0], dtype="uint8")
    upper = numpy.array(grayboundaries[1],dtype="uint8")
    mask = cv2.inRange(card,lower,upper)
    output = cv2.bitwise_and(card,card,mask=mask)
    cv2.imshow("result",output)
    cv2.waitKey(0)
    mean = numpy.mean(mask)



import os
from pathlib import Path
import shutil
import subprocess
import imageio
import rawpy
import lensfunpy
import cv2
from PIL import Image as PILImage
from PIL import ExifTags
from util import util


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

def lensProfileCorrection(filepath,config):
    clprofile = util.getCameraLensProfiles(config["camera"],config["lens"])
    lensdb = lensfunpy.Database()
    #both of these return a list, the first item of which should be our camera. If not, we need to be more specific.
    cam = lensdb.find_cameras(clprofile["camera"]["maker"],clprofile["camera"]["model"])[0]
    lens = lensdb.find_lenses(cam,clprofile["lens"]["maker"],clprofile["lens"]["model"])[0]

def convertCR2toDNG(input,output,config):
    outputcmd = f"-d \"{output}/\""
    converterpath = util.getConfigForPlatform(config["DNG_Converter"])
    subprocess.run([converterpath,"-d",output,"-c", input], check = False)

def getExifData(filename):
    exif = {}
    skiplist=["MakerNote","UserComment"] #These have a bunch of data that needs to be decoded somehow and I can't be stuffed to figure out how to do it.
    with PILImage.open(filename) as pi:
        exif = pi.getexif()
        IFD_CODES = {i.value: i.name for i in ExifTags.IFD}
        for code, val in exif.items():
            if code in IFD_CODES:
                propname = IFD_CODES[code]
                print(propname)
                ifd_data = exif.get_ifd(code)
                for nk,nv in ifd_data.items():
                    nested_tag = ExifTags.GPSTAGS.get(nk,None) or ExifTags.TAGS.get(nk,None) or nk
                    print(nested_tag)
                    if nested_tag in skiplist:
                        continue
                    exif[nested_tag]=nv
            else:
                tagname = ExifTags.TAGS.get(code,code)
                exif[tagname]=val
    

    return exif           


def convertCR2toTIF(input,output,config):
    fn = Path(input).stem
    with rawpy.imread(input) as raw:
        rgb = raw.postprocess(use_camera_wb=True)
        imageio.imsave(os.path.join(output,fn+".tif"),rgb)

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



import os
from pathlib import Path
import shutil
import subprocess
import imageio
import rawpy
import lensfunpy
import numpy
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

def processImage(filepath, output, config):
    #takes a camera raw file, applies lens distortion correction, converts to TIF
    exif = getExifData(filepath)
    tifname = convertCR2toTIF(filepath,output,config)
    outputfile = f"{Path(filepath).stem}_corrected.TIF"
    img = cv2.imread(tifname)
    newimg = lensProfileCorrection(img,config,exif)
    imageio.imwrite(os.path.join(output,outputfile), newimg)


def lensProfileCorrection(tifhandle,config,exif): #pass a camera raw file.
    
    clprofile = util.getCameraLensProfiles(config["Camera"],config["Lens"])
    lensdb = lensfunpy.Database()
    #both of these return a list, the first item of which should be our camera. If not, we need to be more specific.
    cam = lensdb.find_cameras(clprofile["camera"]["maker"],clprofile["camera"]["model"])[0]
    lens = lensdb.find_lenses(cam,clprofile["lens"]["maker"],clprofile["lens"]["model"])[0]
    
    #get data needed for calc from exif data
    focal_length = exif["FocalLength"] if "FocalLength" in exif.keys() else 0
    aperture = exif["FNumber"] if "FNumber" in exif.keys() else 0
    distance = 1.0 #this is usually the distance when I'm photographing small stuff.
    img_width = tifhandle.shape[1]
    img_height = tifhandle.shape[0]
    modifier = lensfunpy.Modifier(lens,cam.crop_factor,img_width,img_height)
    print(f"focal_length = {focal_length}, aperture ={aperture}, distance={distance}, cam:{cam}, lens:{lens}")
    modifier.initialize(focal_length,aperture,distance,pixel_format = tifhandle.dtype.type )
    undist_coords = modifier.apply_geometry_distortion()
    newimg = cv2.remap(tifhandle,undist_coords, None, cv2.INTER_LANCZOS4)
    return newimg
    
    #get information on picture from exif data

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
    outputname = os.path.join(output,fn+".tif")
    with rawpy.imread(input) as raw:
        rgb = raw.postprocess(use_camera_wb=True)
        imageio.imsave(outputname,rgb)
    return outputname

def convertToJPG(input, output):
    fn = Path(input).stem #get the filename.
    ext = os.path.splitext(input)[1].upper()
    outputname = os.path.join(output,fn+".jpg")
    if ext==".TIF":
        try:
            f=cv2.imread(input)
            cv2.imwrite(outputname,f,[int(cv2.IMWRITE_JPEG_QUALITY),100])
        except Exception as e:
            raise e
    elif ext ==".CR2":
        with rawpy.imread(input) as f:
            processedimage = f.postprocess(use_camera_wb=True)
            imageio.save(outputname,processedimage)
    return outputname
def getWhiteBalance(rawpath):
    with rawpy.imread(rawpath) as raw:
        return raw.camera_whitebalance
    
def getGrayFromCard(cardpath):
    pass



import os
from pathlib import Path
import shutil
import subprocess
import imageio
import rawpy
import lensfunpy
import numpy as np
import cv2
from PIL import Image as PILImage
from PIL import ExifTags
from util import util
from processing import processingTools

def findGray(colorcarddatacv2):
    h,w,rgb = colorcarddatacv2.shape
    midpoint = [int(w/2),int(h/2)]
    #there are four squares per row on a color card. 
    halfsquare = int(w/8)
    #our gray square ought to be about a square and a half up and to the right from the centerpoint.
    graycoords = [midpoint[0]+3*halfsquare,midpoint[1]-3*halfsquare]
    print(f"width:{w},height:{h},square dimensions:{halfsquare*2}, gray location:{graycoords}")
    graypoint = colorcarddatacv2[graycoords[0],graycoords[1]]
    print(f"color {graypoint} at coords: {graycoords}")
    return graypoint


def getColorCardFromImage(colorcardimage):
    markerdict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    arucoparams = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(markerdict,arucoparams)
    (corners,ids,rejected) =detector.detectMarkers(colorcardimage)
    ids = ids.flatten()
    print("found markers {ids}")
    try:
        #basically get the index in the ids array of each marker id. The corner coordinates of the marker will have the same index in the 
        #multidimensional "corners" array. Get the outermost coordinate for each item in the array 
        # we will use these to straighten the color card. The order of the ids is arbitrary based on how I made the card.
        idindex = np.squeeze(np.where(ids==2))
        topleft = np.squeeze(corners[idindex])[0]
        print("Got topleft")
        idindex = np.squeeze(np.where(ids==3))
        topright = np.squeeze(corners[idindex])[1]
        print("Got topright")
        idindex = np.squeeze(np.where(ids==0))
        bottomright = np.squeeze(corners[idindex])[2]
        print("Got bottomright")
        idindex = np.squeeze(np.where(ids==1))
        bottomleft = np.squeeze(corners[idindex])[3]
        print("Got bottomleft")
        card = processingTools.perspectiveTransform(colorcardimage,np.array([topleft,topright,bottomright,bottomleft]))
        return card
    except Exception as e:
        print(e)
        print(f"Could not find four markers in the color card iamge. Markers found were: {ids}. Aborting.")
        return None
    
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

def processImage(filepath: str, output: str, config: dict):
    """Runs non-filter corrections on a file format and then exports it as a tiff
    
    Checks to see if a file is a canon RAW file (CR2), and converts the file to tiff. Then, opens the file and with imageio 
    and does lens profile corrections and vignette removal. Eventually this function will also do white balance.
    
    Parameters
    -------------
    filepath : the path to an image file.
    output : the path where you want the new tiff file to be written.
    config : a dictionary of config values. These are found in the config.json file under "processing", which is the dict that gets passed in.

    """
    exif = getExifData(filepath)

    if filepath.upper().endswith(".CR2"):
        filepath = convertCR2toTIF(filepath,output,config)
    img = imageio.imread(filepath)
    newimg = lensProfileCorrection(img,config,exif)
    imageio.imwrite(filepath, newimg)


def lensProfileCorrection(tifhandle,config,exif): #pass a camera raw file.
    #do lens profile correction This code was borrowed from here: https://pypi.org/project/lensfunpy/
    clprofile = util.getCameraLensProfiles(config["Camera"],config["Lens"])
    lensdb = lensfunpy.Database()
    #both of these return a list, the first item of which should be our camera. If not, we need to be more specific.
    cam = lensdb.find_cameras(clprofile["camera"]["maker"],clprofile["camera"]["model"])[0]
    lens = lensdb.find_lenses(cam,clprofile["lens"]["maker"],clprofile["lens"]["model"])[0]
    #get data needed for calc from exif data
    focal_length = exif["FocalLength"] if "FocalLength" in exif.keys() else 0
    aperture = exif["FNumber"] if "FNumber" in exif.keys() else 0
    if focal_length ==0 or aperture ==0:
        print(f"WARNING: Can't do profile corrections, because there is no value for aperture or f-number in the exif data of the photo.")
        return tifhandle
    distance = 1.0 #can't think of a great way to calculate this so I'm going to hardcode it since it's about a meter in person and with the ortery.
    img_width = tifhandle.shape[1]
    img_height = tifhandle.shape[0]
    modifier = lensfunpy.Modifier(lens,cam.crop_factor,img_width,img_height)
    print(f"focal_length = {focal_length}, aperture ={aperture}, distance={distance}, cam:{cam}, lens:{lens}")
    modifier.initialize(focal_length,aperture,distance,pixel_format = tifhandle.dtype.type ) #demo code has this as just dtype, but it has a keyerror exception.
    undist_coords = modifier.apply_geometry_distortion()
    newimg = cv2.remap(tifhandle,undist_coords, None, cv2.INTER_LANCZOS4)
    if not modifier.apply_color_modification(newimg):
        print("WARNING: Failed to remove vignetting.")
    return newimg

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
                ifd_data = exif.get_ifd(code)
                for nk,nv in ifd_data.items():
                    nested_tag = ExifTags.GPSTAGS.get(nk,None) or ExifTags.TAGS.get(nk,None) or nk
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



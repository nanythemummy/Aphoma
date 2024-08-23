"""Utility scripts for doing color correction and other processing operations. The idea is to keep the pixel crunching in this module
and to do the orchestration of the pixel crunching in image_processing.py"""
import argparse
from pathlib import Path
import numpy as np
import cv2

def background_begone_opencv(imagefile:Path):
    pass
#code for perspective transform inspired by Adrian Rosebrock's code here: https://pyimagesearch.com/2014/08/25/4-point-opencv-getperspective-transform-example/
def points_to_clockwise_rectangle(pts):
    """
    Given four points in space, try to figure out which is the top left, and which one is the bottom right etc, then return them in a list where
    they are ordered clockwise.

    Parameters:
    pts: A numpy array of coordinates in 2d space.

    returns: a numpy NDArray.
    """
    #new array of four x,y coordinates, initialized to zero.
    rect = np.zeros((4,2),dtype="float32")
    #np sum will add the x,y vals, ie. Axis 1 of an array of 4 x,y pts.
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2]= pts[np.argmax(s)]
    #there is a chance the middle two points will have the same sum, so we can't figure them this way. 
    #we need to instead figure the biggest distance between points. 
    #I think this makes some assumptions about our rectangle not being too distorted.
    d = np.diff(pts,axis=1)
    rect[1]=pts[np.argmin(d)]
    rect[3]=pts[np.argmax(d)]
    return rect

def perspective_transform(image,pts):
    """Given four points in space, orders them in a clockwise direction and then uses cv2 to do a perspective transform on them into
    a rectangle.
    Parameters:
    -------------------------
    image: a numpy array of pixels.
    pts: an numpy array of points.
    
    returns an array of pixels.
    """
    rect = points_to_clockwise_rectangle(pts)
    (tl, tr, br, bl) = rect #these are the points from the rectangle in order.
    #calculate the new image width which will be the 
    #maximum between the distance between the top points or the distance between the bottom ones.
    #distance = root(a^2+b^2). Honestly, we could just convert these guys into vectors and get the length.
    widthbrbl = np.sqrt((br[0]-bl[0])**2 + (br[1]-bl[1])**2)
    widthtrtl = np.sqrt((tr[0]-tl[0])**2 + (tr[1]-tl[1])**2)
    maxWidth = max(int(widthbrbl),int(widthtrtl))
    #do the same for the height.
    heighttrbr = np.sqrt((tr[0]-br[0])**2 + (tr[1]-br[1])**2)
    heighttlbl = np.sqrt((tl[0]-bl[0])**2 + (tl[1]-bl[1])**2)
    maxHeight = max(int(heighttrbr),int(heighttlbl))
    #construct a new array of pixels of the new dimensions into which the old image will be stretched.
    dst = np.array([
        [0,0],
        [maxWidth-1,0],
        [maxWidth-1,maxHeight-1],
        [0,maxHeight-1]
    ], dtype="float32")
    transformmatrix = cv2.getPerspectiveTransform(rect,dst)
    newpixels = cv2.warpPerspective(image,transformmatrix,(maxWidth,maxHeight))
    return newpixels


def find_gray(colorcarddatacv2):
    """Given an array of pixels corresponding to a color card, find the second gray box from the center.
    This basically just finds the center point and counts two swatches up and over. It doesn't do any sort of special color
    detection stuff.
    
    Parameters:
    ---------------
    colorcarddatacv2 - an array of pixels.
    """

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


def get_color_card_from_image(colorcardimage: str): 
    """
    Detects Aruco markers around a color card in a picture, and does a perspective transform on them so that they form a rectangular image.
    The model for this code is here: https://pyimagesearch.com/2021/02/15/automatic-color-correction-with-opencv-and-python/
    
    Parameters:
    -----------------
    colorcardimage: path to an image with a color card and aruco markers in it.

    returns: a numpy array of pixels (numpy.Matlike) representing the color card.

    """
    markerdict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    arucoparams = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(markerdict,arucoparams)
    corners, ids, rejected = detector.detectMarkers(colorcardimage)
    ids = ids.flatten()
    print("found markers {ids}")
    try:
        #basically get the index in the ids array of each marker id. 
        #The corner coordinates of the marker will have the same index in the 
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
        card = perspective_transform(colorcardimage,np.array([topleft,topright,bottomright,bottomleft]))
        return card
    except Exception as e:
        print(e)
        print(f"Could not find four markers in the color card iamge. Markers found were: {ids}. Aborting.")
        return None
def remove_background_cmd(args):
    if not Path(args.imagepath).is_file():
        print(f"{args.imagepath} doesn't seem to be a real file.")
        return
    

def find_gray_cmd(args):
    if Path(args.colorcardimage).is_file():
        card = get_color_card_from_image(args.colorcardimage)
        rgbgray = find_gray(card)
        print(rgbgray)
    else:
        print(f"{args.colorcardimage} doesn't seem to be a real file.")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(prog="processingTools")
    subparsers = parser.add_subparsers(help="Sub-command help")
    grayparser = subparsers.add_parser("detectGray", help="Detects a color card with aruco markers around it, and finds gray on that color card.")
    bgparser = subparsers.add_parser("removeBackground", help="Uses OpenCV to remove the background of an image.")

    grayparser.add_argument("colorcardimage", help="path to the color card image", type=str)
    grayparser.set_defaults(func=find_gray_cmd)

    bgparser.add_argument("imagepath", help="Path of the image you want to remove the background from.", type=str)
    bgparser.set_defaults(func=remove_background_cmd)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
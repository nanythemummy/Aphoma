import argparse
from pathlib import Path

import cv2
import numpy as np

def thresholdingMask(picpath: Path, maskout: Path, lowerthreshold:int):
    img = cv2.imread(str(picpath))
    #threshold image
    grayscale = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(grayscale,235,lowerthreshold,cv2.THRESH_BINARY)[1]
    mask = 255-mask #invert the colors
    cv2.imwrite(str(maskout),mask)

def edgeDetectionMask(picpath: Path, maskout: Path, threshold1: int, threshold2: int):
    #uses the canny edge detection algorithm to detect edges, then finds the biggest contiguous edge and fills it.
    #if you have issues with this, play with the two threshold values below. They controll the smallest and largest line intensities to be
    #included in the final calculation to find the longest lines. Having a lower threshold will include more details from the picture
    #but may not end up selecting what you want.

    #https://stackoverflow.com/questions/29313667/how-do-i-remove-the-background-from-this-kind-of-image?rq=4

    print(f"Building mask for {picpath} with edge detection. Output at {maskout}")
    img = cv2.imread(str(picpath))

    grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    #edge detection
    print(f"thresholds ={threshold1},{threshold2}")
    edges = cv2.Canny(grayscale,threshold1,threshold2)

    edges = cv2.dilate(edges, None)
    edges = cv2.erode(edges, None)

    #find contours in edges, sort by area
    contoursInfo = []
    contours, _ = cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)

    for c in contours:
        contoursInfo.append((c,cv2.contourArea(c)))
    contoursInfo = sorted(contoursInfo, key=lambda c: c[1], reverse=True)
    max_contour = contoursInfo[0]

    #make an empty mask, draw polygon on it corresponding to the largest contour.
    mask = np.zeros(edges.shape)
    cv2.fillConvexPoly(mask,max_contour[0],(255))
    cv2.imwrite(str(maskout),mask)


if __name__ == "__main__":
    import json

    def load_config_file(configpath):
        """Loads config.json into a dictionary
        
        Parameters:
        ---------------
        configpath: path to config.json
        
        returns: dictionary of key value configurations.
        """
        cfg = {}
        with open(configpath, encoding='utf-8') as f:
            cfg = json.load(f)
        return cfg["config"]
    
    def thresholdSelectCommand(args):
        img = Path(args.imagepath)
        outpath = Path(args.outpath)
        if img.exists and outpath.parent.exists():
            if not args.contextselect:
                thresholdingMask(img, outpath,config["thresholding_lower_gray_threshold"])
            else:
                edgeDetectionMask(img,outpath, 
                                  config["canny_lower_intensity_threshold"],
                                  config["canny_higher_intensity_threshold"])

    config = load_config_file(Path.joinpath(Path(__file__).parent.parent.resolve(),"config.json"))["processing"]
    parser = argparse.ArgumentParser(prog="maskingAlgorithms")
    subparsers = parser.add_subparsers(help="Sub-command help")
    maskTypeParser = subparsers.add_parser("mask", help="algorithm for removing background from an image")
    maskTypeParser.add_argument("--contextselect", action="store_true", help="By default, the background will be removed using grayscale thresholding. With this flag, it will use canny edge detection.")
    maskTypeParser.add_argument("imagepath", help="path to image with a background to remove.", type=str)
    maskTypeParser.add_argument("outpath", help="path to image with a background to remove.", type=str)
    maskTypeParser.set_defaults(func=thresholdSelectCommand)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
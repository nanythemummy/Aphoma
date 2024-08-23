import argparse
from pathlib import Path

import cv2
import numpy as np

def thresholdingMask(picpath: Path, maskout: Path, lowerthreshold:int):
    img = cv2.imread(picpath)
    #threshold image
    grayscale = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(grayscale,235,lowerthreshold,cv2.THRESH_BINARY)[1]
    mask = 255-mask #invert the colors
    cv2.imwrite(maskout,mask)

def contextSelectMask(picpath: Path, maskout: Path):
    #https://stackoverflow.com/questions/29313667/how-do-i-remove-the-background-from-this-kind-of-image?rq=4
    canny_threshold1 = 10
    canny_threshold2 = 200
    
    img = cv2.imread(picpath)
    grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    #edge detection
    edges = cv2.Canny(grayscale,canny_threshold1,canny_threshold2)

    edges = cv2.dilate(edges, None)
    edges = cv2.erode(edges, None)

    #find contours in edges, sort by area
    contoursInfo = []
    contours,hierarchy = cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)

    for c in contours:
        contoursInfo.append((c,cv2.isContourConvex(c),cv2.contourArea(c)))
    contoursInfo = sorted(contoursInfo, key=lambda c: c[2], reverse=True)
    max_contour = contoursInfo[0]

    #make an empty mask, draw polygon on it corresponding to the largest contour.
    mask = np.zeros(edges.shape)
    cv2.fillConvexPoly(mask,max_contour[0],(255))
    cv2.imwrite(maskout,mask)


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
                thresholdingMask(img, outpath,config["FuzzySelectDroplet"]["lower_gray_threshold"])
            else:
                contextSelectMask(img,outpath)

    config = load_config_file(Path.joinpath(Path(__file__).parent.parent.resolve(),"config.json"))["processing"]
    parser = argparse.ArgumentParser(prog="maskingAlgorithms")
    subparsers = parser.add_subparsers(help="Sub-command help")
    fuzzyselectParser = subparsers.add_parser("mask", help="algorithm for removing background from an image")
    fuzzyselectParser.add_argument("--contextselect", action="store_true", help="By default, the background will be removed using grayscale thresholding. With this flag, it will use canny edge detection.")
    fuzzyselectParser.add_argument("imagepath", help="path to image with a background to remove.", type=str)
    fuzzyselectParser.add_argument("outpath", help="path to image with a background to remove.", type=str)
    fuzzyselectParser.set_defaults(func=thresholdSelectCommand)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
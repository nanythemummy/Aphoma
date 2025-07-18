import argparse
from pathlib import Path
import cv2
import numpy as np
from inference_sdk import InferenceHTTPClient

def otsuThresholding(picpath: Path, maskout: Path):
    img = cv2.imread(str(picpath))
    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    _,mask = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)    if np.mean(mask)>127: #ie, its greater than half of 255:
    mask = cv2.bitwise_not(mask)
    cv2.imwrite(str(maskout),mask)



def thresholdingMask(picpath: Path, maskout: Path, lowerthreshold:int):
    img = cv2.imread(str(picpath))
    #threshold image

    grayscale = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    _,mask = cv2.threshold(grayscale,lowerthreshold,255,cv2.THRESH_BINARY)
    cv2.imwrite(str(maskout),cv2.bitwise_not(mask))

def edgeDetectionMask(picpath: Path, maskout: Path, threshold1: int, threshold2: int):
    #uses the canny edge detection algorithm to detect edges, then finds the biggest contiguous edge and fills it.
    #if you have issues with this, play with the two threshold values below. They controll the smallest and largest line intensities to be
    #included in the final calculation to find the longest lines. Having a lower threshold will include more details from the picture
    #but may not end up selecting what you want.

    #https://stackoverflow.com/questions/29313667/how-do-i-remove-the-background-from-this-kind-of-image?rq=4

    print(f"Building mask for {picpath} with edge detection. Output at {maskout}")
    img = cv2.imread(str(picpath))
    h,w,_ = img.shape
    print(f"h:{h},w:{w}")
    grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(grayscale,(25,25),0)
    #edge detection
    print(f"thresholds ={threshold1},{threshold2}")
    edges = cv2.Canny(blur,threshold1,threshold2)


    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
    edges = cv2.morphologyEx(edges,cv2.MORPH_CLOSE,kernel, iterations=5)


    cv2.imshow('With dilation erosion', cv2.resize(edges,(1600,1000 )))
    cv2.waitKey(0)
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
        thresholds = []
        if args.thresholds:
            thresholds = [float(f) for f in str.split(args.thresholds.replace(" ",""),',')] 
        if img.exists and outpath.parent.exists():
            if args.type == "thresholding":
                thresholdingMask(img, outpath,thresholds[0] if len(thresholds)>0 else config["thresholding_lower_gray_threshold"])
            elif args.type == "canny":
                edgeDetectionMask(img,outpath, 
                                  thresholds[0] if len(thresholds)>1 else config["canny_lower_intensity_threshold"],
                                  thresholds[1] if len(thresholds)>1 else config["canny_higher_intensity_threshold"])
            else:
                otsuThresholding(img, outpath)

    config = load_config_file(Path.joinpath(Path(__file__).parent.parent.resolve(),"config.json"))["processing"]
    parser = argparse.ArgumentParser(prog="maskingAlgorithms")
    subparsers = parser.add_subparsers(help="Sub-command help")
    maskTypeParser = subparsers.add_parser("mask", help="algorithm for removing background from an image. default is thresholding, whcih takes a minimum gray value.")
    maskTypeParser.add_argument("type", choices=["otsu","thresholding","canny"], help="By default, the background will be removed using grayscale thresholding. With this flag, it will use canny edge detection. It takes an upper and lower threshold.")
    maskTypeParser.add_argument("imagepath", help="path to image with a background to remove.", type=str)
    maskTypeParser.add_argument("outpath", help="path to image with a background to remove.", type=str)
    maskTypeParser.add_argument("--thresholds", help="Each masking option can take thresholds. Pass these in as a comma seperated list.", type=str)
    maskTypeParser.set_defaults(func=thresholdSelectCommand)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
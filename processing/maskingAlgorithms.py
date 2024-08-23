import argparse
from pathlib import Path

import cv2
import numpy as np

def fuzzySelectMask(picpath: Path, maskout: Path, lowerthreshold:int):
    img = cv2.imread(picpath)
    #threshold image
    grayscale = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(grayscale,235,lowerthreshold,cv2.THRESH_BINARY)[1]
    mask = 255-mask #invert the colors
    cv2.imwrite(maskout,mask)

def contextSelectMask(picpath: Path, maskout: Path):
    pass


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
    
    def fuzzySelectCommand(args):
        img = Path(args.imagepath)
        outpath = Path(args.outpath)
        if img.exists and outpath.parent.exists():
            if not args.contextselect:
                fuzzySelectMask(img, outpath,config["FuzzySelectDroplet"]["lower_gray_threshold"])
            else:
                contextSelectMask(img,outpath)

    config = load_config_file(Path.joinpath(Path(__file__).parent.parent.resolve(),"config.json"))["processing"]
    parser = argparse.ArgumentParser(prog="maskingAlgorithms")
    subparsers = parser.add_subparsers(help="Sub-command help")
    fuzzyselectParser = subparsers.add_parser("mask", help="algorithm for removing background from an image")
    fuzzyselectParser.add_argument("--contextselect", action="store_true", help="By default, the background will be removed using grayscale thresholding. With this flag, it will use canny edge detection.")
    fuzzyselectParser.add_argument("imagepath", help="path to image with a background to remove.", type=str)
    fuzzyselectParser.add_argument("outpath", help="path to image with a background to remove.", type=str)
    fuzzyselectParser.set_defaults(func=fuzzySelectCommand)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
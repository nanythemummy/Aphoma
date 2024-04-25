from processing import image_processing
import os.path
import argparse

def convert_raw_to_format(args):
    inputdir = args.imagedirectory
    outputdir = args.outputdirectory
    if not os.path.exists(outputdir):
        os.mkdir(outputdir)
        print(f"Created directory {outputdir}")
    with os.scandir(inputdir) as it: #scans through a given directory, returning an interator.
        for f in it:
            if os.path.isfile(f):
                if f.name.endswith(".CR2"): #CANON CAMERA!
                    if args.dng:
                        image_processing.convertCR2toDNG(os.path.join(f),outputdir)
                    if args.tif:
                        image_processing.convertCR2toTIF(os.path.join(f),outputdir)


parser = argparse.ArgumentParser(prog="photogrammetryScripts")
subparsers = parser.add_subparsers(help="Sub-command help")
convertprocessor = subparsers.add_parser("convert", help=" Convert a Raw file to another format ")
convertprocessor.add_argument("--dng",help="Converts to dng type", action="store_true")
convertprocessor.add_argument("--tif", help = "Convert to tif type", action="store_true")
convertprocessor.add_argument("imagedirectory", help="Directory of raw files to operate on.")
convertprocessor.add_argument("outputdirectory", help="Directory to put the output processed files.")
convertprocessor.set_defaults(func=convert_raw_to_format)
args = parser.parse_args()
if hasattr(args,"func"):
    args.func(args)
else:  
    parser.print_help()

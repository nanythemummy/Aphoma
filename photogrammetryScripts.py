from processing import image_processing
from transfer import transferscripts
from photogrammetry import MetashapeTools
import os.path, json, argparse

#This script mainly takes input and arguments from the command line and delegates them elsewhere.
#For individual transfer scripts see the transfer module, likewise, see the processing module for processing scripts.

def build_model(args):
    """Wrapper script for using automating the use of agisoft metashape from the command line."""
    job = args.jobname
    photoinput = args.photos
    outputdir = args.outputdirectory
    MetashapeTools.build_basic_model(photoinput,outputdir,job)
def transfer_to_network_folder(args):
    """Wrapper script for running the transfer functions from the command line."""
    inputdir = args.imagedirectory
    jobname = args.jobname
    def getFileCreationTime(item):
        return os.path.getctime(item)
    fs=[os.path.join(inputdir,f) for f in os.listdir(inputdir) if f.endswith("cr2")]
    filestocopy = sorted(fs,key=getFileCreationTime)
    if args.p: #if the pics need to be pruned...
       filestocopy= transferscripts.pruneOrteryPics(filestocopy,config["ortery"])
    transferscripts.transferToNetworkDirectory(jobname, filestocopy,config["transfer"]["networkdrive"])

def convert_raw_to_format(args):
    """wrapper script for using the RAW image conversion fucntions via the command line."""
    inputdir = args.imagedirectory
    outputdir = args.outputdirectory
    if not os.path.exists(outputdir):
        os.mkdir(outputdir)
    with os.scandir(inputdir) as it: #scans through a given directory, returning an interator.
        print(inputdir)
        for f in it:
            if os.path.isfile(f):
                if f.name.upper().endswith(".CR2"): #CANON CAMERA!
                    if args.dng:
                        image_processing.convertCR2toDNG(os.path.join(f),outputdir, config["processing"])
                    if args.tif:
                        image_processing.convertCR2toTIF(os.path.join(f),outputdir, config["processing"])

def load_config():
    """Loads the configuration values in config.json and stores them in a dictionary."""
    with open('config.json') as f:
        return json.load(f)["config"]
   

config = load_config()

parser = argparse.ArgumentParser(prog="photogrammetryScripts")
subparsers = parser.add_subparsers(help="Sub-command help")
convertprocessor = subparsers.add_parser("convert", help=" Convert a Raw file to another format ")
convertprocessor.add_argument("--dng",help="Converts to dng type", action="store_true")
convertprocessor.add_argument("--tif", help = "Convert to tif type", action="store_true")
convertprocessor.add_argument("imagedirectory", help="Directory of raw files to operate on.", type=str)
convertprocessor.add_argument("outputdirectory", help="Directory to put the output processed files.", type=str)
convertprocessor.set_defaults(func=convert_raw_to_format)

transferparser = subparsers.add_parser("transfer", help="transfers files to a network drive from the specified folder.")
transferparser.add_argument("--p", help="Prunes every Nth file from Camera X, as specified in the config.json.",action="store_true")
transferparser.add_argument("jobname", help="The name of this job. This translates into a subfolder on the network drive.")
transferparser.add_argument("imagedirectory", help="Copies images from this directory to the shared network folder as specified in config.json")
transferparser.set_defaults(func=transfer_to_network_folder)

photogrammetryparser = subparsers.add_parser("photogrammetry", help="scripts for turning photographs into 3d models")
photogrammetryparser.add_argument("jobname", help="The name of the project")
photogrammetryparser.add_argument("photos", help="Place where the photos in tiff or jpeg format are stored.")
photogrammetryparser.add_argument("outputdirectory", help="Where the intermediary files for building the model and the ultimate model will be stored.")
photogrammetryparser.set_defaults(func=build_model)

args = parser.parse_args()
if hasattr(args,"func"):
    args.func(args)
else:
    parser.print_help()


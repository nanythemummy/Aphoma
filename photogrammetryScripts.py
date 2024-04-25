from processing import image_processing
from transfer import transferscripts
import os.path, json, argparse

#This script mainly takes input and arguments from the command line and delegate them elsewhere.
#For individual transfer scripts see the transfer module, likewise, see the processing module for processing scripts.


def transfer_to_network_folder(args):
   
    inputdir = args.imagedirectory
    jobname = args.jobname
    print(config)
    transferscripts.transferToNetworkDirectory(jobname, inputdir,config["transfer"]["networkdrive"], args.p)

def convert_raw_to_format(args):
    inputdir = args.imagedirectory
    outputdir = args.outputdirectory
    if not os.path.exists(outputdir):
        os.mkdir(outputdir)
    with os.scandir(inputdir) as it: #scans through a given directory, returning an interator.
        for f in it:
            if os.path.isfile(f):
                if f.name.endswith(".CR2"): #CANON CAMERA!
                    if args.dng:
                        image_processing.convertCR2toDNG(os.path.join(f),outputdir, config["processing"])
                    if args.tif:
                        image_processing.convertCR2toTIF(os.path.join(f),outputdir, config["processing"])

def load_config():
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


args = parser.parse_args()
if hasattr(args,"func"):
    args.func(args)
else:  
    parser.print_help()

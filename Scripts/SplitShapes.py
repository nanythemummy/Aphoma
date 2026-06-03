
from pathlib import Path
import argparse
import sys
parentpath = Path(__file__).parent.parent.absolute()
sys.path.append(str(parentpath))
from photogrammetry.MetashapeTools import splitModelIntoShapes

def split_shapes_cmd(args):
    """Wrapper script for taking a psx file and splitting the model inside into multiple cubic components which are exported as named obj files."""
    print("Got there.")
    inputdir = Path(args.inputdir)
    project = args.projectname
    projdir = Path(inputdir,f"{project}.psx")
    print(f"{projdir}")
    if projdir.exists():
        try:
            splitModelIntoShapes(projdir)
        except ImportError as e:
            print(f"{e.msg}: You should try downloading the metashape python module from Agisoft and installing it. See Readme for more details.")
            raise e
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="SplitShapes")
    parser.add_argument("inputdir",help="Directory of project")
    parser.add_argument("projectname", type=str, help="Name of the psx file.")
    parser.set_defaults(func = split_shapes_cmd)
    args = parser.parse_args()
    if hasattr(args,"func"):
        args.func(args)
    else:
        parser.print_help()
import sys
import argparse
import os
import shutil
from pathlib import Path
from util.PipelineLogging import getLogger as getGlobalLogger
import json, csv, re
if __name__=="__main__":
    parentpath = Path(__file__).parent.parent.absolute()
    sys.path.append(str(parentpath))

#makes a zipfile from a set of files.
def zipTheseFiles(files:list, basedir:Path, zipfilename:str):
    file_existed = False
    try:
        zipdir = os.mkdir(Path(basedir,zipfilename))
        for f in files:
            shutil.copy2(f,Path(zipdir,Path(f).name))
        shutil.make_archive(zipfilename,"zip",zipdir)
    except shutil.Error as e:
        getGlobalLogger(__name__).error(e)
        raise e
    except FileExistsError as e:
        getGlobalLogger(__name__).error(e)
        file_existed=True
        raise e
    finally:
        if not file_existed:
            shutil.rmtree(Path(basedir,zipfilename))
    
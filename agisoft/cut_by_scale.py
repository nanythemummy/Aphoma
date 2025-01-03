# Rotates chunk's bounding box in accordance of coordinate system for active chunk. Bounding box size is kept.
#
# This is python script for Metashape Pro. Scripts repository: https://github.com/agisoft-llc/metashape-scripts

import math
import json
from pathlib import Path

import Metashape

# Checking compatibility
compatible_major_version = "2.1"
found_major_version = ".".join(Metashape.app.version.split('.')[:2])
if found_major_version != compatible_major_version:
    raise Exception("Incompatible Metashape version: {} != {}".format(found_major_version, compatible_major_version))




def cutbyfactor():
    scalefactor = 0.5
    doc = Metashape.app.document
    chunk = doc.chunk
    size = chunk.region.size
    size[1]*=scalefactor
    
    ctr = chunk.transform.matrix.mulp(chunk.region.center)
    ctr[1] = ctr[1]+(-1*ctr[1]/2)
    chunk.region.size = size
    print(f" center{chunk.region.center}")
    chunk.region.center = ctr
    print(f"new center{chunk.region.center}")



label = "Cut By Factor"
Metashape.app.addMenuItem(label, cutbyfactor)
print("To execute this script press {}".format(label))

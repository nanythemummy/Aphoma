# Rotates chunk's bounding box in accordance of coordinate system for active chunk. Bounding box size is kept.
#
# This is python script for Metashape Pro. Scripts repository: https://github.com/agisoft-llc/metashape-scripts

import Metashape
import math

# Checking compatibility
compatible_major_version = "2.1"
found_major_version = ".".join(Metashape.app.version.split('.')[:2])
if found_major_version != compatible_major_version:
    raise Exception("Incompatible Metashape version: {} != {}".format(found_major_version, compatible_major_version))


def print_locations():
    doc = Metashape.app.document
    chunk = doc.chunk
    reg = chunk.region
    print(f"mulp={chunk.transform.matrix.mulp(reg.center)}")
    print(f"transform of chunk.{chunk.transform.matrix}")
    print(f"rotation of region.{reg.rot}")
    print(f"center of region, {reg.center}")
    print(f"dimensions of region. {reg.size}")

label = "Where's the bounding box?"
Metashape.app.addMenuItem(label, print_locations)
print("To execute this script press {}".format(label))

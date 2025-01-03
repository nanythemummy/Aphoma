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

def findAxesFromMarkers(chunk,palette):
    if not chunk.markers:
        print("No marker palette defined or markers detected. Cannot detect orientation from palette.")
        return []
    xaxis = []
    zaxis = []
    markers = chunk.markers
    markers.reverse() #generally higher numbers are on the inside, so search from inside out.
    for m in markers:
        if not m.position==None:
            lookforlabel = (int)(m.label.split()[1]) #get the number of the label to look for it in the list of axes.
            if lookforlabel in palette["axes"]["xpos"] or lookforlabel in palette["axes"]["xneg"]:
                xaxis.append(m.position)
            if lookforlabel in palette["axes"]["zpos"] or lookforlabel in palette["axes"]["zneg"]:
                zaxis.append(m.position)
            if len(xaxis)>=2 and len(zaxis)>=2:
                break
    if len(xaxis)<2 or len(zaxis) <2:
        print("Not enough data to determine x and z axes.")
        return []
    ux = (xaxis[1]-xaxis[0])
    uz = (zaxis[1]-zaxis[0])
    yaxis = Metashape.Vector.cross(uz,ux)
    ux.normalize()
    uz.normalize()
    yaxis.normalize()
    return [ux,yaxis,uz]


def movetozero():

    palette = {
            "type":"12bit",
            "unit":"mm",
            "scalebars":{
                "type":"explicit",
                "bars":[
                {
                "points":[1,2],
                "distance":60,
                "units":"mm"
                },
                {
                "points":[1,3],
                "distance":60.3,
                "units":"mm"
                }
            ]
            },
            "axes":{
                "xpos":[2,3],
                "xneg":[],
                "zpos":[3,1],
                "zneg":[]
            }
        }
    

    doc = Metashape.app.document
    chunk = doc.chunk
    chunk.resetRegion()
    regioncenter = chunk.region.center
    height = chunk.region.size.y
    axes = findAxesFromMarkers(chunk,palette)

    #rotate chunk to new axes.
    print("Setting rotation to align with axes")
    transmat = chunk.transform.matrix
    scale = math.sqrt(transmat[0,0]**2+transmat[0,1]**2 + transmat[0,2]**2) #length of the top row in the matrix, but why?
    scale*=1 #by default agisoft assumes we are using meters while we are measuring in mm in meshlab and gigamesh.
    scalematrix = Metashape.Matrix().Diag([scale,scale,scale,1])
    newaxes = Metashape.Matrix([[axes[0].x,axes[0].y, axes[0].z,0],
                   [axes[1].x,axes[1].y,axes[1].z,0],
                   [axes[2].x, axes[2].y,axes[2].z,0],
                   [0,0,0,1]])


    chunk.transform.matrix=scalematrix*newaxes 

    #moving object to zero
   
    #moving region to zero and aligning it with object rotation.

    vertices = chunk.model.vertices
    step = int(min(1E4, len(vertices)) / 1E4) + 1
    sum = Metashape.Vector([0,0,0])
    N = 0
    for i in range(0, len(vertices), step):
        sum += vertices[i].coord
        N += 1
    avg = sum / N


    s = chunk.transform.matrix.scale()
    T = chunk.transform.matrix
    M = Metashape.Matrix().Diag([s,s,s,1])

    reg = chunk.region
    reg.center = avg
   
    reg.rot = T.rotation()

    origin = (-1) * M.mulp(chunk.region.center)
    chunk.transform.matrix  = Metashape.Matrix().Translation(origin) * (s * Metashape.Matrix().Rotation(T.rotation()))

#resize bounding box
    reg = chunk.region
    

label = "ObjectToZero"
Metashape.app.addMenuItem(label, movetozero)
print("To execute this script press {}".format(label))

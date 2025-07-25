#for low light pictures where markers cannot be detected, this:
#creates a new chunk, 
# copies pictures into it, 
# thresholds pictures to a tunable value, 
# detects 12-bit markers circular markers on those,
# uses the coordinates to place markers on original pictures
# blows away the new chunk.
# blows away the directory the thresholded pics are in.
from pathlib import Path
from os import *
import shutil
import cv2

import Metashape
def checkMarkerLabelExists(chunk, labelname):

    for m in chunk.markers:
        if m.label ==labelname:
            return m
    return None
def sledgeHammerDetector(threshold=25):
    t = int(threshold)
    print(t)
    #make a temp dir.
    doc = Metashape.app.document
    currentworkingdir = Path(doc.path).parent
    photostomunge=[]
    deletetemp = True
    oldchunk = doc.chunk
    tempdir = Path(currentworkingdir,"temp")
    try:
        mkdir(tempdir)
    except FileExistsError:
        deletetemp = False
    #for each pic in the chunk, threshold it and save the new image out to the tempdir.
    for camera in oldchunk.cameras:
        impath = camera.photo.path
        cam = cv2.imread(impath)
        bw = cv2.cvtColor(cam,cv2.COLOR_BGR2GRAY)
        _,mask = cv2.threshold(bw,t,255,cv2.THRESH_BINARY)
        outdir =str(Path(tempdir,Path(impath).name))
        photostomunge.append(outdir)
        cv2.imwrite(str(outdir),mask)

    # add a new temporary chunk, importing the pictures from the temp directory.
    tempchunk = doc.addChunk()
    tempchunk.label = "tempchunk"
    for photo in photostomunge:
        if Path(photo).suffix.upper() ==".JPG":
            tempchunk.addPhotos(photo)

    #detect markers on the new chunk.
    tempchunk.detectMarkers(Metashape.TargetType.CircularTarget12bit,filter_mask=False)
    photostomarkers={}
    if len(tempchunk.markers)>0:
        for m in tempchunk.markers:
            for camera in tempchunk.cameras:
                if camera in m.projections.keys():
                    projection = m.projections[camera]
                    x = projection.coord.x
                    y = projection.coord.y
                    photoname = Path(camera.photo.path).stem
                    if  photoname not in photostomarkers.keys():
                        photostomarkers[photoname] = []
                    photostomarkers[photoname].append({"name":m.label,"x":x,"y":y })
    print(photostomarkers)
    doc.chunk = oldchunk
    for cam in doc.chunk.cameras:
        camname=Path(cam.photo.path).stem
        if camname in photostomarkers.keys():
            newmarkers = photostomarkers[camname]
            for marker in newmarkers:
                mk = checkMarkerLabelExists(oldchunk,marker["name"]) or oldchunk.addMarker()
                mk.label= marker["name"]
                mk.projections[cam]=Metashape.Marker.Projection(Metashape.Vector([marker["x"],marker["y"]]),True)
    doc.remove(tempchunk)
    if(deletetemp):
        shutil.rmtree(tempdir)


label = "Detect Markers with Sledgehammer"

Metashape.app.addMenuItem(label, sledgeHammerDetector)
print("To execute this script press {}".format(label))
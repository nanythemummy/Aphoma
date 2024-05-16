import Metashape
import json
from os import path
targetTypes = {
    "Circular":Metashape.TargetType.CircularTarget,
    "12bit":Metashape.TargetType.CircularTarget12bit,
    "14bit":Metashape.TargetType.CircularTarget14bit,
    "16bit":Metashape.TargetType.CircularTarget16bit,
    "20bit":Metashape.TargetType.CircularTarget20bit,
    "Cross":Metashape.TargetType.CrossTarget
}
def loadPallettes():
    #going to hardcode this for now. Maybe come back and configure it.
    pallettes = {}
    with open (path.join("util/MarkerPallettes.json")) as f:
        pallettes = json.load(f)
    return pallettes["pallettes"]
def setChunkAccuracy(chunk):
     # set accuracy values for markers and scale bars in the chunk
    chunk.tiepoint_accuracy = 0.25 # pixels WHAT ARE THESE MAGIC NUMBERS?
    chunk.marker_projection_accuracy = 0.5 # pixels
    chunk.marker_location_accuracy = Metashape.Vector( (5.0e-5, 5.0e-5, 5.0e-5) ) # meters (= 0.05 mm)

def convertUnitToMeters(unit,val):
    if unit == "cm":
        return val*0.01
    elif unit == "mm":
        return val*0.001
    elif unit == "km":
        return val*100.0
    else:
        return val*1.0
    
def buildScalebarsFromList(chunk,scalebardefinitions):
    setChunkAccuracy(chunk)
    for definition in scalebardefinitions:
        name1=f"target {definition["points"][0]}"
        name2=f"target {definition["points"][1]}"
        marker1=marker2=None
        for marker in chunk.markers:
            if marker.label == name1:
                marker1=marker
            elif marker.label == name2:
                marker2=marker
            if marker1 and marker2:
                break
        if marker1 and marker2:
            #either make a new scalebar or find one that already exists between the two markers and reset the distance between them.
            scalebar = None
            for existingbar in chunk.scalebars:
                if (existingbar.point0==marker1 or existingbar.point0==marker1) and (existingbar.point0==marker2 or existingbar.point1==marker2):
                    scalebar = existingbar
                    break
            if scalebar == None:
                scalebar = chunk.addScalebar(marker1,marker2)
            scalebar.reference.distance = convertUnitToMeters(definition["units"],definition["distance"])
            scalebar.reference.accuracy = 1.0e-5
            scalebar.reference.enabled = True
    chunk.updateTransform()        

def detectMarkers(chunk, type):
    setChunkAccuracy(chunk)
    # remove any existing markers from this chunk
    if len(chunk.markers):
        chunk.remove(chunk.markers)

    print("Detecting and assigning 12-bit targets")
    # detect markers using defaults (12-bit markers, tolerance: 50, filter_mask: False, etc.)
    chunk.detectMarkers(target_type=targetTypes[type], filter_mask=False) 

    # bale if we have no markers
    if len(chunk.markers) ==  0:
        print("- no markers detected")
    else:
        print(f"- found {len(chunk.markers)} markers")
    # update markers
    chunk.refineMarkers()
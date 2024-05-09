# -*- coding: utf-8 -*-
"""
Orient model by detecting markers and 

Required arguments:
- the names of three markers 

Created on Weds April 17 18:24:41 2024
For Metsahape 2.1 Python Library 
@authors: JP Brown 
"""

import Metashape, math, sys

print("orient model in x-z plane")
def get_marker(chunk, name):
    result = next((x for x in chunk.markers if x.label == name), None)
    if(result is None):
        print(f"- could not find '{name}'")
    else:
        print(f"- found '{name}': {result.position}")
    return result 

doc = Metashape.app.document # specifies open document
chunk = doc.chunk # specifies active chunk

"""
if chunk.scale is not None:
    print("- OrientModel should be performed before scaling")
    print("- Model not oriented")
    exit(0)
"""

# target properties: coord (vector)
# TODO: make the names of these three markers arguments - first and second marker should define left-right axis 
m0 = get_marker(chunk, "target 15") 
m1 = get_marker(chunk, "target 50") 
m2 = get_marker(chunk, "target 20") 

# figure out the local x, y, and z unit vectors

x_vector = (m0.position - m1.position)  # the model vector we want oriented parallel with the world's x-axis
dummy_vector = (m0.position - m2.position) # a dummy vector that is oriented in the model's x-z plane 

y_vector = Metashape.Vector.cross(x_vector, dummy_vector).normalized() # the vector we want oriented parallel with the world's y-axis
z_vector = Metashape.Vector.cross(x_vector, y_vector).normalized() # the vector we want oriented parallel with the world's z-axis
x_vector = x_vector.normalized() # normalize the x_vector 

# build a rotation matrix
R = Metashape.Matrix([x_vector, y_vector, z_vector])

# apply the rotation 
chunk.transform.rotation = R

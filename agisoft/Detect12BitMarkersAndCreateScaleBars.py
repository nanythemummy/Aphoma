# -*- coding: utf-8 -*-
"""
Detect markers and set scales.
This process should be classed *after* RefineSparseCloud.py has been called.

Created on Sat Jan 27 15:00:04 2024
For Metsahape 2.1 Python Library 
@authors:  JP Brown

"""
import Metashape, math, sys


#  Holds information on the known distance between points for different scale bars
class ScaleBarInfo:

	# Constructor
	# 	target1_marker_num: number of the first target
	# 	target2_marker_num: number of the second target
	# 	distance_in_meters: the length of the marker in meters
	def __init__(self, target1_marker_num, target2_marker_num, distance_in_meters):
		self.target1_name = "target " + str(target1_marker_num)
		self.target2_name = "target " + str(target2_marker_num)
		self.distance_in_meters = distance_in_meters
	
	# stringify this ScaleBarInfo
	def __str__(self):
		return  f"{self.target1_name}_{self.target2_name}: {self.distance_in_meters}  m"
	
	# return the scale bar's label
	def label(self):
		return  f"{self.target1_name}_{self.target2_name}"
		

# List of known scale bars
class ScaleBarList:

	# Constructor
	# Initializes the known_scale_bars list
	def __init__(self):
		# list of ScaleBarInfo items representing our known scale bars
		self._known_scale_bars = []		
		# make list of known scale distances on our coded scale bars
		self._known_scale_bars.append(ScaleBarInfo(1, 3, 1.000023))
		self._known_scale_bars.append(ScaleBarInfo(4, 6, 0.50013))
		self._known_scale_bars.append(ScaleBarInfo(7, 8, 0.25004))
		self._known_scale_bars.append(ScaleBarInfo(9, 11, 1.000016))
		self._known_scale_bars.append(ScaleBarInfo(12, 14, 0.50000))
		self._known_scale_bars.append(ScaleBarInfo(15, 16, 0.24989))
	
	# return a scale bar (if we know of one) that starts with first_target_label
	# 	first_target_label: the Metashape.marker.label we are trying to match
	#	returns: the matching ScaleBarInfo object, or 'None' if no match is found
	def getScaleBarStartingWith(self, first_target_label):
		# look for first target label (or 'None' if we can't find a match)
		info = next( (x for x in self._known_scale_bars if x.target1_name == first_target_label), None)
		return info
		

# start main program
print("== detecting and assigning 12-bit targets ==")
chunk = Metashape.app.document.chunk

# set accuracy values for markers and scale bars in the chunk
chunk.tiepoint_accuracy = 0.25 # pixels
chunk.marker_projection_accuracy = 0.5 # pixels
chunk.marker_location_accuracy = Metashape.Vector( (5.0e-5, 5.0e-5, 5.0e-5) ) # meters (= 0.05 mm)
chunk.scalebar_accuracy = 1.0e-5  # meters (= .01 mm)

# NB - default CRS is 'Local Coordinates (m)'
#crs = Metashape.CoordinateSystem()
#crs.init(Metashape.CoordinateSystem('LOCAL_CS["Local CS",LOCAL_DATUM["Local Datum",0],UNIT["metre",1]]')

# remove any existing markers from this chunk
if len(chunk.markers):
	chunk.remove(chunk.markers)

# detect markers using defaults (12-bit markers, tolerance: 50, filter_mask: False, etc.)
chunk.detectMarkers() 

# bale if we have no markers
if len(chunk.markers) ==  0:
	print("== no markers detected ==")
	exit(0)
else:
	print("== found markers ==")

# update markers
chunk.refineMarkers()

our_scalebars = ScaleBarList()

# iterate over the markers, looking for known scale bars with matching target names

for count, m1 in enumerate(chunk.markers):
	
	print(f"- {m1}")
	
	# see if we have a known first marker target
	matching_scalebar = our_scalebars.getScaleBarStartingWith(m1.label) 
	
	# if we don't have a scale bar whose first target label == m1.label, continue to the next marker 
	if (matching_scalebar == None):
		continue
		
	# check for second marker target
	m2 = next( (x for x in chunk.markers if x.label == matching_scalebar.target2_name), None)  
	
	# if we can't find the end label for our scale bar, continue to the next marker 
	if (m2 == None):
		continue
	
	print(f"- - found scale bar {matching_scalebar.label}")
	
	# create scale bar
	new_scalebar = chunk.addScalebar(m1, m2)
	new_scalebar.reference.distance = matching_scalebar.distance_in_meters
	new_scalebar.reference.accuracy = 1.0e-5
	new_scalebar.reference.enabled = True

# now we have scale bars, we should be able to rescale the sparse cloud?

chunk.updateTransform()
Metashape.app.update()

# update to set scale
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True, fit_k1=True,
						  fit_k2=True, fit_k3=True, fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True,
						  fit_p4=True, adaptive_fitting=False, tiepoint_covariance=False)

"""
T = chunk.transform.matrix
M = T.scale() * Metashape.Matrix.Rotation(T.rotation())
chunk.transform.matrix = Metashape.Matrix().Translation(M.mulp((-1) * T.mulp(marker.position))) * M
"""




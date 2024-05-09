# -*- coding: utf-8 -*-
"""
Refine the initial sparse cloud by iteratively selecting the weakest points
in a particular category, deleting them, and re-optimzing the sparse cloud.

Created on Mon May 23 10:24:18 2022
For Metsahape 2.1 Python Library 
@authors: Marc Block, JP Brown, Murphy Spence
"""
import Metashape, math, sys

# fraction of least good points to be removed on each iteration on a scale of 0-1
# (here we remove 0.1 which is equivalent to 10% of the total points)
DISCARD_FRACTION = 0.1

# initial setup
doc = Metashape.app.document # specifies open document
chunk = doc.chunk # specifies active chunk

tp = chunk.tie_points # TiePoints in the sparse cloud
ntp_start = len(tp.points) # Initial number of tie points
ntp_remaining = ntp_start # current number of tie points
f = Metashape.TiePoints.Filter() # global filter for TiePoints object
	
print("****Number of starting points:", ntp_start) # prints initial point number in raw sparse cloud

# Put the camera optimization in a block, because it is unwieldy
#    isFinal: boolean value for some of the less important fitting variables (set this value to True on the last optimization) 
def optimize_cameras(isFinal):
	chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=isFinal, fit_b2=isFinal, fit_k1=True,
							  fit_k2=True, fit_k3=True, fit_k4=isFinal, fit_p1=True, fit_p2=True, fit_p3=isFinal,
							  fit_p4=isFinal, adaptive_fitting=False, tiepoint_covariance=False)

# Function to optimize tie points.
#    Filter type: one of the Metashape.TiePoints.Filter criterion values
#    while_value: fraction of the ntp_start points below which we are are not willing to go.
#    desired_value: the criterion threshold (we want to reduce the value for this filter type <= this value)
def optimize_tiepoints(filter_type, while_value, desired_value):
	
	global ntp_remaining
	
	# continue 
	while(ntp_remaining > while_value * ntp_start):
		f.init(tp, filter_type)
		
		values = f.values.copy()
		values.sort(reverse=True)
		
		print("- filter max value:", values[0])
		
		# exit the while loop if the filter value < desired_value
		if values[0] <= desired_value:
			break
		
		thresh = values[int(len(values)*DISCARD_FRACTION)]
		
		f.selectPoints(thresh)
		
		#nselected = len([p for p in tp.points if p.selected])
		tp.removeSelectedPoints()
		
		ntp_remaining = len(tp.points)
		print("- remaining points:", ntp_remaining)
		
		# camera optimization after point deletion
		optimize_cameras(False)

# initial optimization
optimize_cameras(False)

# optimize reconstruction uncertainty 
# - do not continue if we are at 50% or less of the initial tie points.
# - stop if the reconstruction uncertainty value is <= 10
print("- Optimizing reconstruction uncertainty:")
optimize_tiepoints(Metashape.TiePoints.Filter.ReconstructionUncertainty, 0.5, 10)

# optimize the reprojection error
# - do not continue if we are at 25% or less of the initial tie points.
# - stop if the reprojection error is <= 0.3
print("- Optimizing Repeojection Error:")
optimize_tiepoints(Metashape.TiePoints.Filter.ReprojectionError, 0.25, 0.3)

#final optimization
optimize_cameras(True)


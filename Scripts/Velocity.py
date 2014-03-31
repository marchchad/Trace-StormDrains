# Created by: Chad March
# Description: This script calculates velocity of linear storm drain features
# using Manning's Equation and Roughness Coefficients.

# Import arcpy, sys, and math libraries and specific modules from each
import arcpy
import sys, traceback
import math
from math import *

# Define workspace/geoprocessing environment.
workspace = r'C:\SDNTest\SDN_Temp.gdb'
arcpy.env.workspace = workspace

class pathObj:
    """
    pathObj takes in 2 arguments.
    The name of the path object and the row object to be used for calculations
    and updating. If the row object has an 8th field, it'll be updated.
    """
    def __init__(self,path,row):
        self.path = path
        self.material = row[0]
        self.height = row[1]
        self.slope = row[2]
        self.velocity = row[3]
        self.flowTime = row[4]
        self.length = row[5]
        self.oid = row[6]
        if len(row) > 7:
            self.softBtm = row[7]

# Predefined functions

# Calculates velocity based on Manning's coefficient, height, and length of
# line passed in.
def velocity(edge,coef):
    
    # Manning's equation to calculate velocity
    velocity = (1.486/coef)*(((edge.height/12)/4)**(0.667))*(sqrt(edge.slope))
    
    # Time calculated by dividing length with velocity
    time = edge.length/velocity
    
    # populate fields with values
    row[3] = velocity
    row[4] = time
    
    # write values in to feature
    # rows.updateRow(row)
    print "Path: {0} Objectid-{1} has a velocity of {2} and a flow time of {3}.".format(edge.path,edge.oid,edge.velocity,edge.flowTime)

# Error function writes in 0 values to make sure no invalid results are written in
def error(path,oid,varType,var):
    print "Path: {0} Objectid-{1} has an invalid {2} value of {3}.".format(path,oid,varType,var)
    row[3] = 0
    row[4] = 0
    # rows.updateRow(row)

# Function to check the material value to determine which Manning's coefficient value to use
def checks(edge):
    """
    Requires a row object or variable initialized with a custom object representing the required
    slope, height, material, oid, soft bottom, and length attributes of the rows object.
    """

    coef = 0.0
    
    # If an invalid slope value, set to the most common value of 0.03
    if edge.slope <= 0 or edge.slope is None:
        edge.slope = 0.03

    # If an invalid value, set to the most common value of 24.0
    if edge.height <= 0 or edge.height >= 999 or edge.height is None:
        edge.height = 24.0
        
    # All values in materialList use 0.012 according to Manning's Roughness Coefficients
    if edge.material in materialList:
        coef = 0.012
        
    # Materials that are CMP or Cast Iron Pipe use 0.022
    elif edge.material in materialCorrugatedList:
        coef = 0.022
    
    # Plastic pipes have ranges for their roughness coefficient values
    # Use 0.009 for both since that will result in a higher velocity.
    elif edge.material in materialPlasticList:
        coef = 0.009 

    # Earth materials use 0.025
    elif edge.material in materialEarthList:
        coef = 0.025
        
    # 13 is clay pipe and uses 0.01
    elif edge.material == 13:
        coef = 0.01
        
    # 22 is High Density Polyethylene Pipe (corrugated plastic) and uses a range 0.018 - 0.025
    # Use 0.018 since that will result in a higher velocity.
    elif edge.material == 22:
        coef = 0.018
    
    # For open channels with soft bottoms, overwrite coef value.
    if hasattr(edge,'softBtm'):
        if edge.softBtm == 'Y':
            coef = 0.025

    # If material value is in error list, call error function
    if edge.material in materialErrorList:
        error(edge.path,edge.oid,"material",edge.material)
    else:
        velocity(edge,coef)

#Use try statement to contain cursor and processing to catch errors
try:
    # List of material values of various concrete type pipes, brick, and steel
    # that all share the same manning's coefficient.
    # RCP, RCB, RCA, Concrete, Steel, unreinforced concrete, asbestos cement, brick, CIPP, RCC
    materialList = [1,3,5,9,12,14,15,20,21,23]

    # Plastic materials PVC, ABS, Polyethylene liner and Truss Pipe
    materialPlasticList = [2,10,11,16,24]
    
    # Corrugate metal pipes
    materialCorrugatedList = [4,6,8]

    # Earth material codes
    materialEarthList = [7,19]

    # List of invalid materials or None for no value entered.
    materialErrorList = [0,98,99,None]

    # List of fields to be added to feature classes
    newFields = ["Velocity_fps","FlowTime_secs"]
    
    # List of polyline feature classes to calculate values for.
    paths = ['GravityMain','LateralLine','OpenChannel','Culvert']
    
    for path in paths:
        # List fields to see if there is already velocity and flow time fields
        # Fields cannot be added during an edit session.
        fields = [f.name for f in arcpy.ListFields(path)]
        for field in newFields:
            if field not in fields:
                print 'adding {0} to {1}...'.format(field, path)
                arcpy.AddField_management(path,field,'FLOAT')
                
    # Start an edit session. Must provide the worksapce.
    edit = arcpy.da.Editor(workspace)
    
    # Edit session is started without an undo/redo stack for versioned data
    # (for second argument, use False for unversioned data)
    # For fgdbs, use settings below.
    edit.startEditing(False, False)

    # Start an edit operation
    edit.startOperation()

    # Loop through list of paths
    for path in paths:
        # Data Access Update Cursor is only valid in ArcGIS 10.1 and above
        # Much faster cursor than general update cursor
        fields = ["MATERIAL","DIAMETER_HEIGHT","SLOPE","Velocity_fps","FlowTime_secs","SHAPE_Length","OID@"]

        # For channels, append Soft Bottom field. When set to Y, it is an earthen bottom
        # and will override the roughness coefficient of the material.
        if path == 'OpenChannel':
            fields.append("SOFT_BOTTOM")

        with arcpy.da.UpdateCursor(path,fields) as rows:
            for row in rows:
                edge = pathObj(path,row)
                checks(edge)
                rows.updateRow(row)


    # Stop the edit session and save the changes
    edit.stopEditing(True)       
        
# Code that runs when error(s) occurs
except:
    # Stop the edit session and save the changes
    edit.stopEditing(False)
    print '\nStopped editing and no changes were saved...'

    # Get the python traceback object
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]
    
    # Concatenate information together concerning the error into a message string
    pymsg = "\nPYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
    msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages(2) + "\n"
    
    # Print Python error messages for use in Python / Python Window
    print "\n" + pymsg + "\n" + msgs

# Code that executes when script is done.
finally:
    print 'Script Complete...'

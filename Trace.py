# Created by: Chad March
# Description: This script iterates through an input point feature class used
# as 'flags' in a geometric network to trace the linear features of that network,
# totals the flow times of each linear feature, then outputs a merged polyline
# feature class of that traced path labeled with the objectid of the flag used
# as the origin of the trace.
'''
Things to keep in mind:
1. All polylines must be of the same edge type (Complex or Simple)
2. If lines are not split at every junction, the output merged/dissolved line will contain
    entire line selected by trace, even parts that are upstream of the the incoming
    connected line.
3. You cannot be using the output file gdb in any application because an exclusive lock
    will be placed upon it, preventing the output feature classes from being generated
    and causing the script to fail.
'''

# import modules
import arcpy, os, sys, traceback

# Only set an output worksapce if dissolved trace outputs are to be created
output = r'C:\SDNTest\SDN_Trace_Output.gdb'
# output = ''

if len(output) != 0:
    path = output.rsplit('\\',1)[0]
    name = output.rsplit('\\',1)[1]
    # If it already exists, delete it so a fresh one can be made
    if os.path.exists(output):
        print 'Deleting old output fgdb...'
        arcpy.Delete_management(output)
        print 'Old output fgdb deleted...'

    print 'Creating output fgdb...'
    arcpy.CreateFileGDB_management(path,name)
    print 'Output fgdb created at '+output

# Set workspace environments

workspace = r'C:\SDNTest\SDN_Temp.gdb'
arcpy.env.workspace = workspace
arcpy.env.overwriteOutput = True

# Predefined functions 

def createOutput(tracePath,output,mergeList):

    fieldMappings = arcpy.FieldMappings()
    fieldMap = arcpy.FieldMap()
    fieldMap.addInputField(mergeList[0],"FlowTime_secs")
    fieldMappings.addFieldMap(fieldMap)

    print 'merging...'
    arcpy.Merge_management(mergeList,tracePath,fieldMappings)

    # print 'dissolving...'
    arcpy.Dissolve_management(tracePath,tracePath+'_dissolved','#','#','SINGLE_PART','DISSOLVE_LINES')

    print 'deleting temp output...'
    arcpy.Delete_management(tracePath)

def calcFlow(output,path):
    # Local variable to hold total of time in selected feature class
    time = 0.0

    # Boolean operator to return the path variable when true.
    mergePath = True if int(arcpy.GetCount_management(path).getOutput(0)) > 0 else False

    # Begin cursor on selected feature class
    if mergePath == True:
        with arcpy.da.SearchCursor(path,["FlowTime_secs"]) as rows:
            for row in rows:
                # Get value from FlowTime_secs field
                flow = row[0]
                # If value has a value and it is not a space
                if flow != None or flow != ' ':
                    time += flow
                    
    # return the total time for the path and the path
    return [time,mergePath]

try:
    # Name of geometric network
    sdnNet = workspace+'\\SDN\\'+'STORMDRAINNET_NET'

    # Feature class to be used as flags in tracing the geometric network
    flags = 'CatchBasin'
    
    # Add flow time field to catch basins if not already present
    fields = [f.name for f in arcpy.ListFields(flags)]
    
    newField = ['FlowTime']
    for field in newField:
        if field not in fields:
            arcpy.AddField_management(flags,field,'FLOAT')
            print field+' added to '+flags+'...'
    
    # Start an edit session. Must provide the worksapce.
    edit = arcpy.da.Editor(workspace)
    
    # Edit session is started without an undo/redo stack for versioned data
    # (for second argument, use False for unversioned data)
    # For fgdbs, use settings below.
    edit.startEditing(False, False)
    
    # Start an edit operation
    edit.startOperation()

    # Set flow direction of network to follow digitized direction
    flow = 'WITH_DIGITIZED_DIRECTION'
    arcpy.SetFlowDirection_management(sdnNet,flow)
    
    flagFields = ['OID@','FlowTime']
    with arcpy.da.UpdateCursor(flags,flagFields) as rows:
        for row in rows:
            # Create temporary variables for functions
            oid = row[0]
            newNet = 'SDN_Net'+str(oid)
            flag = 'flag'+str(oid)
            exp = '"OBJECTID" = '+str(oid)

            # Create in memory feature layer of one catch basin
            arcpy.MakeFeatureLayer_management(flags,flag,exp)

            # Trace the network downstream
            arcpy.TraceGeometricNetwork_management(sdnNet,newNet,flag,"TRACE_DOWNSTREAM","#","#","#","#","#","NO_TRACE_ENDS","NO_TRACE_INDETERMINATE_FLOW","#","#","AS_IS","#","#","#","AS_IS")
            print newNet
            gMain = "GravityMain"
            latLine = "LateralLine"
            oChann = "OpenChannel"
            culvert = "Culvert"
            pseudoLine = "PseudoLine"

            # Create array of temporary paths for enumeration
            pathList = [gMain,latLine,oChann,culvert]
            
            # Create an empty array to be populated with paths to be merged later
            mergeList = []

            # Create variable for total time
            total = 0.0

            # Enumerate the list and update output variables
            for path in pathList:
                results = calcFlow(output,newNet+"\\"+path)
                total += results[0]
                if results[1] is True:
                    mergeList.append(path)

            print 'total time is '+str(total)
            # Set the FlowTime value to the resulting total time variable
            row[1] = total
            rows.updateRow(row)

            # If there are paths populated in the merge list and
            # there is an output workspace declared, copy out the selected trace results
            if len(output) != 0 and len(mergeList) != 0:
                # Create name for dissolved path output
                tracePath = output+"\\"+"tracePath_"+str(oid)

                # Check to see if there are any pseudo lines selected
                # If so, append to list so the merge and dissolve won't have gaps
                pseudoRecords = int(arcpy.GetCount_management(newNet+'\\'+pseudoLine).getOutput(0))
                if pseudoRecords > 0:
                    mergeList.append(pseudoLine)
                
                # Use the pathList for enumeration and merging
                createOutput(tracePath,output,mergeList)

            # Delete temporary outputs
            delete = [flag,newNet]
            for each in delete:
                arcpy.Delete_management(each)
            
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
    msgs = "\nArcPy ERRORS:\n" + arcpy.GetMessages(2) + "\n"
    
    # Print Python error messages for use in Python / Python Window
    print "\n" + pymsg + "\n" + msgs

# Code that executes when script is done.
finally:
    
    print 'Script Complete...'

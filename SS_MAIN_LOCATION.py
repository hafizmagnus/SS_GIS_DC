# RlVDSyBZT1UgQlVERFkh
# -------------------------------------------------------------------------------
# Name:        Check SS Main Locaiton & Add Loction Code
# Purpose:     Provide GIS Data Managers with a tool to check topology
#
# Author:      Muhammad Hafiz Bin Ishak Magnus
#
# Created:     24/05/2016
# Copyright:   (c) National Parks Board 2016
# Licence:     Enterprise Perpetual
# -------------------------------------------------------------------------------

import base64
import os
import re

import arcpy

__version__ = "1.1"


# geometry correction for area modification
def geo_mod_correction(main_feature, SS_feature):
    SS_MOD_CLIP = "in_memory" + "//" + "SS_CLIPPED"
    arcpy.Clip_analysis(SS_feature, main_feature, SS_MOD_CLIP)
    result = arcpy.GetCount_management(SS_MOD_CLIP)
    count = int(result.getOutput(0))
    if count != 0:
        with arcpy.da.UpdateCursor(main_feature, ["OID@", "SHAPE@", "LOC_CD", "EDIT_TYPE"]) as mod_feats:
            for i_feat in mod_feats:
                if i_feat[3] == "MODIFY":
                    with arcpy.da.SearchCursor(SS_MOD_CLIP, ["OID@", "SHAPE@", "LOC_CD"]) as SS_CURSORS:
                        for SS_i_feat in SS_CURSORS:
                            if i_feat[2] != SS_i_feat[2]:
                                i_feat[1] = i_feat[1].difference(SS_i_feat[1])
                                mod_feats.updateRow(i_feat)
                            else:
                                continue


# ensuring no overlaps with the current EVE layers
def NON_SS_modify(main_feature, EVE_layers):
    arcpy.AddMessage("\nChecking if any overlaps are present..........")
    arcpy.GetMessages(0)
    counter = 0
    for EVE_layer in EVE_layers:
        counter += 1
        output = "in_memory" + "\\" + "MAO"
        arcpy.Clip_analysis(EVE_layer, main_feature, output)
        result = arcpy.GetCount_management(output)
        count = int(result.getOutput(0))

        if count > 0:
            arcpy.AddMessage("Overlaps have been detected with {0}.\n\tStarting clean-up..........".format(EVE_layer))
            with arcpy.da.UpdateCursor(main_feature,["OID@", "SHAPE@", "EDIT_TYPE"]) as mod_cursor:
                for mod_row in mod_cursor:
                    if mod_row[2] == "MODIFY":
                        with arcpy.da.SearchCursor(output, ["OID@", "SHAPE@"]) as EVE_cursor:
                            for EVE_row in EVE_cursor:
                                mod_row[1] = mod_row[1].difference(EVE_row[1])
                                mod_cursor.updateRow(mod_row)
            arcpy.AddMessage("\tClean-up completed for overlaps with {0}.".format(EVE_layer))
            arcpy.GetMessages(0)



#ensuring no overlaps with the current EVE layers
def union_erase(main_feature, EVE_layers):
    arcpy.AddMessage("\nChecking if any overlaps are present..........")
    arcpy.GetMessages(0)
    counter = 0
    for EVE_layer in EVE_layers:
        counter += 1
        output = "in_memory" + "\\" + "MAO"
        output_union = "in_memory" + "\\" + "MAO" + "_Union"
        im_feature_layer = "in_memory" + "\\" + "MAO_FL"
        union_layer = "in_memory" + "\\" + "UNION_LAYER_" + str(counter)
        arcpy.Clip_analysis(EVE_layer, main_feature, output)
        result = arcpy.GetCount_management(output)
        count = int(result.getOutput(0))

        if count > 0:
            arcpy.AddMessage("Overlaps have been detected with {0}.\n\tStarting clean-up..........".format(EVE_layer))
            with arcpy.da.UpdateCursor(main_feature, ["OID@", "SHAPE@", "EDIT_TYPE"]) as new_cursor:
                for new_row in new_cursor:
                    if new_row[2] == "CREATE":
                        with arcpy.da.SearchCursor(output, ["OID@", "SHAPE@"]) as EVE_cursor:
                            for EVE_row in EVE_cursor:
                                new_row[1] = new_row[1].difference(EVE_row[1])
                                new_cursor.updateRow(new_row)
            arcpy.AddMessage("\tClean-up completed for overlaps with {0}.".format(EVE_layer))
            arcpy.GetMessages(0)


#function to populate location codes based on the current layers
def loc_cd_populator(main_feature, SS_EVE_Layer):
    global error_count
    with arcpy.da.UpdateCursor(main_feature, ["EDIT_TYPE", "LOC_TYPE", "SECTION_CODE", "LOC_CD", "LOC_DESC", "OID@", "SHAPE@"]) as lc_cursor:
        f_loc_cd_list = []
        for row in lc_cursor:
            lc_text = None
            lc_number = 1
            f_loc_cd = None
            ss_table_view = "SS_Table"

            arcpy.AddMessage("\nChecking attribute for OBJECTID {0}..........".format(row[5]))
            arcpy.GetMessages(0)

            if row[0] == None:
                arcpy.AddError("\tERROR. OBJECTID {0} does not have an Edit Type.\n".format(row[5]))
                arcpy.GetMessages(2)
                error_count += 1
                continue

            elif row[0] == "CREATE":
                if row[4] == None:
                    arcpy.AddError("\tERROR. OBJECTID {0} does not have a Location Description.\n".format(row[5]))
                    arcpy.GetMessages(2)
                    error_count += 1
                    continue

                elif row[2] == None:
                    arcpy.AddError("\tERROR. OBJECTID {0} does not have a SS Section.\n".format(row[5]))
                    arcpy.GetMessages(2)
                    error_count += 1
                    continue

                elif row[1] == None:
                    arcpy.AddError("\tERROR. OBJECTID {0} does not have a Location Type.\n".format(row[5]))
                    arcpy.GetMessages(2)
                    error_count += 1
                    continue

                else:
                    f_loc_desc = str(row[4]).upper().strip()
                    row[4] = f_loc_desc
                    arcpy.AddMessage("\tAssigning Location Code to OBJECTID {0}".format(row[5]))
                    arcpy.GetMessages(0)
                    lc_text = loc_ty_dict[row[1]] + row[2]
                    layer_att = arcpy.AddFieldDelimiters(SS_EVE_Layer, "LOC_CD")
                    main_sql = layer_att + " LIKE " + " '" + lc_text + "%' "
                    arcpy.MakeFeatureLayer_management(SS_EVE_Layer, ss_table_view, where_clause=main_sql)
                    result = arcpy.GetCount_management(ss_table_view)
                    count = int(result.getOutput(0))
                    if count > 0:
                        with arcpy.da.SearchCursor(SS_EVE_Layer, ["LOC_CD"], where_clause=main_sql) as scursor:
                            for current_lc in scursor:
                                re_list_no = re.findall(("[0-9]+"), current_lc[0])
                                num = int(re_list_no[0])
                                if num > lc_number:
                                    lc_number = num + 1
                        f_loc_cd = lc_text + ((str(lc_number)).zfill(3))
                    else:
                        f_loc_cd = lc_text + ((str(lc_number)).zfill(3))

                    # checking the internal dataset if the location code has been assigned
                    if f_loc_cd not in f_loc_cd_list:
                        f_loc_cd_list.append(f_loc_cd)
                        row[3] = f_loc_cd

                    else:
                        internal_re_list_no = re.findall(("[0-9]+"), f_loc_cd)
                        high_internal_no = int(internal_re_list_no[0]) + 1
                        f_loc_cd = lc_text + ((str(high_internal_no)).zfill(3))
                        f_loc_cd_list.append(f_loc_cd)
                        row[3] = f_loc_cd

                    arcpy.AddMessage("\tOBJECTID {0} assigned Location Code {1}.\n".format(row[5], f_loc_cd))
                    arcpy.GetMessages(0)
                    union_erase(main_location, LIVE_LIST)

            elif row[0] == "MODIFY":

                if row[4] == None:
                    arcpy.AddError("\tERROR. OBJECTID {0} does not have a Location Description.\n".format(row[5]))
                    arcpy.GetMessages(2)
                    error_count += 1
                    continue

                elif row[3] == None:
                    arcpy.AddError("\tERROR. OBJECTID {0} does not have a Location Code.\n".format(row[5]))
                    arcpy.GetMessages(2)
                    error_count += 1
                    continue

                else:
                    f_loc_desc = str(row[4]).upper().strip()
                    row[4] = f_loc_desc
                    arcpy.AddMessage("\tChecking if the Location Code {0} exits.".format(row[3]))
                    arcpy.GetMessages(0)
                    layer_att = arcpy.AddFieldDelimiters(SS_EVE_Layer, "LOC_CD")
                    main_sql = layer_att + " = " + " '" + str(row[3]) + "' "
                    arcpy.MakeFeatureLayer_management(SS_EVE_Layer, ss_table_view, where_clause=main_sql)
                    aresult = arcpy.GetCount_management(ss_table_view)
                    acount = int(aresult.getOutput(0))
                    if acount != 1:
                        arcpy.AddError("\tERROR. The Location Code {0} has NOT been identified for OBJECTID {1}.\n".format(row[3], row[5]))
                        arcpy.GetMessages(2)
                        continue
                    else:
                        arcpy.AddMessage("\tThe Location Code {0} has been identified for OBJECTID {1}.\n".format(row[3], row[5]))
                        arcpy.GetMessages(0)
                        tree_layer_att = arcpy.AddFieldDelimiters(LIVE_SS_TREES, "LOC_CD")
                        tree_main_sql = tree_layer_att + " = " + " '" + str(row[3]) + "' "
                        arcpy.MakeFeatureLayer_management(LIVE_SS_TREES, "SS_TREE_LYR", tree_main_sql)
                        ok_trees = []
                        not_ok_trees = []
                        with arcpy.da.SearchCursor("SS_TREE_LYR", ["SHAPE@", "TREE_ID"]) as tree_cursors:
                            for tree in tree_cursors:
                                if row[6].contains(tree[0]) == True:
                                    ok_trees.append(tree[1])
                                else:
                                    not_ok_trees.append(tree[0])
                        if len(not_ok_trees) != 0:
                            arcpy.AddWarning("WARNING. There are {0} tress in EVE that do not fall within OBJECTID {1}".format(len(not_ok_trees), row[5]))
            lc_cursor.updateRow(row)


#-------------------------------------------------------------------------------


# setting out the enviormental parameters
main_location = arcpy.GetParameterAsText(0)
workspace = os.path.dirname(main_location)
folder = os.path.dirname(workspace)
arcpy.env.workspace = workspace

# allowing for overwrite
arcpy.env.overwriteOutput = True

# creating the location codes logic dictionary
loc_ty_dict = {
    "R": "A",
    "S": "AS",
    "O": "AO",
    "F": "AF",
    "GP": "AGP",
    "D": "AD"
}

# the error counter
error_count = 0

# creating the view only database file connection if it does not exists
con_path = folder + "\\" + "MAVEN_VIEW_TEMP.sde"
u = "U1NfR0lTX1ZJRVc="
p = "U1NnaXNWaWV3QDEyMw=="

if os.path.exists(con_path):
    os.remove(con_path)
arcpy.CreateDatabaseConnection_management(folder, "MAVEN_VIEW_TEMP.sde", "SQL_SERVER", "NPMAVCLUS02\MSSQLSERVER1,60001", "DATABASE_AUTH", base64.b64decode(u), base64.b64decode(p), "SAVE_USERNAME", "Maven")

LIVE_SS = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.STREETSCAPE_LOCATION_BOUNDARY'
LIVE_PK = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.PARK_MAINTENANCE_BOUNDARY'
LIVE_EX = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.EXTERNAL_AGENCY_LOCATION_BOUNDARY'
LIVE_SS_TREES = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.STREETSCAPETREES'
LIVE_SS_SUB = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.STREETSCAPE_SUBLOCATION_BOUNDARY'

LIVE_LIST = [LIVE_EX, LIVE_PK, LIVE_SS]

arcpy.RepairGeometry_management(main_location)

edit = arcpy.da.Editor(workspace)
edit.startEditing(False, False)
edit.startOperation()

loc_cd_populator(main_location, LIVE_SS)

#correction for modification check
MOD_LIVE_LIST = [LIVE_EX, LIVE_PK]
NON_SS_modify(main_location, MOD_LIVE_LIST)
geo_mod_correction(main_location, LIVE_SS)

edit.stopOperation()
edit.stopEditing(True)

if error_count > 0:
    arcpy.AddMessage("{} errors have been detected.\nPlease correct these errors and re-run the tool.".format(error_count))
else:
    arcpy.AddMessage("All digitisations are OK!")

arcpy.GetMessages(0)

os.remove(con_path)

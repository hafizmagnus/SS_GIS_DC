# RlVDSyBZT1UgQlVERFkh
# -------------------------------------------------------------------------------
# Name:        Check SS Sub-location and Add Sub-Location Code
# Purpose:     Provide SS GIS Data Managers with a tool to check topology
#
# Author:      Muhammad Hafiz Bin Ishak Magnus
#
# Created:     08/06/2016
# Copyright:   (c) National Parks Board 2016
# Licence:     Enterprise Perpetual
# -------------------------------------------------------------------------------

import base64
import collections
import os

import arcpy

__version__ = "1.1"

loc_cd_list = []
main_location = None
error_count = 0


# function to get the main location template from just the sub-location
def get_main_location_template(s_template):
    global main_location
    main = None
    fc_list = arcpy.ListFeatureClasses()
    if len(fc_list) > 1:
        for fc in fc_list:
            if fc.startswith("SS_SUB_LOCATION_TEMPLATE"):
                fc_list.remove(fc)
        if len(fc_list) == 1:
            main = fc_list[0]
            main_location = workspace + "\\" + main
        else:
            for i in fc_list:
                if i > main:
                    main = i
                main_location = workspace + "\\" + main


# function to just pull out the location codes from the sublocation template
def location_code_extractor(s_template):
    global loc_cd_list
    with arcpy.da.SearchCursor(s_template, ["LOC_CD"]) as sc:
        for i in sc:
            if i[0] not in loc_cd_list:
                loc_cd_list.append(i[0])


# function to check attribution of the sub-locations
def sub_location_attributes(s_template, m_template_clipped, ss_live, ss_sub_live):
    global error_count
    with arcpy.da.UpdateCursor(s_template, ["OID@", "LOC_CD", "LOC_DESC", "SUB_LOC_DESC", "EDIT_TYPE", "SUB_LOC_CD"]) as scursor:
        for row in scursor:
            if row[1] is None:
                arcpy.AddError("\tERROR. OBJECTID {0} does not have a Location Code.\n".format(row[0]))
                arcpy.GetMessages(2)
                error_count += 1
                continue

            elif row[2] is None:
                arcpy.AddError("\tERROR. OBJECTID {0} does not have a Location Description.\n".format(row[0]))
                arcpy.GetMessages(2)
                error_count += 1
                continue

            elif row[3] is None:
                arcpy.AddError("\tERROR. OBJECTID {0} does not have a Sub-Location Description.\n".format(row[0]))
                arcpy.GetMessages(2)
                error_count += 1
                continue

            elif row[4] is None:
                arcpy.AddError("\tERROR. OBJECTID {0} does not have an Edit Type.\n".format(row[0]))
                arcpy.GetMessages(2)
                error_count += 1
                continue

            elif row[4] == "MODIFY" and row[5] is None:
                arcpy.AddError("\tERROR. OBJECTID {0} is a modification but does not have a Sub-Location Code.\n".format(row[0]))
                arcpy.GetMessages(2)
                error_count += 1
                continue

            else:
                f_loc_desc = str(row[3]).upper().strip()
                row[3] = f_loc_desc
                scursor.updateRow(row)
                main_temp_check(s_template, m_template_clipped)
                live_ss_geo_correction(s_template, ss_live)
                sub_loc_populator(s_template)
                mod_check(s_template, ss_sub_live)
                check_sub_location_count(s_template)


# function to check if sub-location is from a new main location
def main_temp_check(s_template, m_template_clipped):
    global loc_cd_list

    if len(loc_cd_list) == 0:
        return

    elif len(loc_cd_list) == 1:
        layer_attr = arcpy.AddFieldDelimiters(m_template_clipped, "LOC_CD")
        whereClause = layer_attr + " = " + str(loc_cd_list[0])

    elif len(loc_cd_list) > 1:
        layer_attr = arcpy.AddFieldDelimiters(m_template_clipped, "LOC_CD")
        whereClause = layer_attr + " IN " + str(tuple(loc_cd_list))

    if len(whereClause):
        arcpy.MakeFeatureLayer_management(m_template_clipped, "M_FEATS", whereClause)
    else:
        arcpy.MakeFeatureLayer_management(m_template_clipped, "M_FEATS")

    result = arcpy.GetCount_management("M_FEATS")
    count = int(result.getOutput(0))

    if count > 0:
        for location in loc_cd_list:
            new_clause = layer_attr + " = '" + str(location) + "'"
            with arcpy.da.SearchCursor(m_template_clipped, ["OID@", "SHAPE@"], new_clause) as mscursor:
                for mloc in mscursor:
                    if mloc[1].getArea("PLANAR", "SQUAREMETERS") > 0.0:
                        loc_cd_list.remove(location)
                        with arcpy.da.UpdateCursor(s_template, ["EDIT_TYPE", "SHAPE@"], new_clause) as ucursor:
                            for subloc in ucursor:
                                if subloc[0] == "CREATE":
                                    if mloc[1].contains(subloc[1]) is False:
                                        subloc[1] = mloc[1].intersect(subloc[1], 4)
                                    subloc[0] = "NEW FROM MAIN LOC TEMPLATE"
                                    ucursor.updateRow(subloc)
                                elif subloc[0] == "MODIFY":
                                    if mloc[1].contains(subloc[1]) is False:
                                        subloc[1] = mloc[1].intersect(subloc[1], 4)
                                    subloc[0] = "MODIFY FROM MAIN LOC TEMPLATE"
                                    ucursor.updateRow(subloc)


# function to populate the sublocation code for new locations
def sub_loc_populator(s_template):
    arcpy.AddMessage("\nPopulating the sub-location codes for new areas..........")
    arcpy.GetMessages(0)
    for location in loc_cd_list:
        oid_list = []
        shape_xy_list = []
        sorted_xy = []
        new_oid_list = []
        alphabet_list = []
        position = 0
        layer_attr = arcpy.AddFieldDelimiters(s_template, "LOC_CD")
        whereClause = layer_attr + " = " + "'" + str(location) + "'"
        with arcpy.da.UpdateCursor(s_template, ["OID@", "SHAPE@XY", "EDIT_TYPE", "SUB_LOC_CD", "LOC_CD", "SUB_LOC_DESC"], where_clause = whereClause) as sloc_cursor:
            for i in sloc_cursor:
                f_loc_desc = str(i[5]).upper().strip()
                i[5] = f_loc_desc
                if i[2] == "CREATE" or i[2] == "NEW FROM MAIN LOC TEMPLATE":
                    oid_list.append(i[0])
                    shape_xy_list.append(i[1])
                    sorted_xy.append(i[1])
            sorted_xy.sort()
            for xy in sorted_xy:
                new_oid_list.append(oid_list[shape_xy_list.index(xy)])
                alphabet_list.append(chr(position + ord('A')))
                position += 1
            coding_dict = dict(zip(new_oid_list, alphabet_list))
            sloc_cursor.reset()
            for new in sloc_cursor:
                if new[2] == "CREATE" or new[2] == "NEW FROM MAIN LOC TEMPLATE":
                    new[3] = str(new[4]) + str(coding_dict[new[0]])
                    sloc_cursor.updateRow(new)
        arcpy.AddMessage("All sub-locaiton codes for {} have been populated successfully.".format(location))
        arcpy.GetMessages(0)


# funtion to correct the geometry if based on live streetscape managed areas
def live_ss_geo_correction(s_template, ss_live):

    if len(loc_cd_list) == 0:
        return

    elif len(loc_cd_list) == 1:
        layer_attr = arcpy.AddFieldDelimiters(ss_live, "LOC_CD")
        whereClause = layer_attr + " = " + str(loc_cd_list[0])

    elif len(loc_cd_list) > 1:
        layer_attr = arcpy.AddFieldDelimiters(ss_live, "LOC_CD")
        whereClause = layer_attr + " IN " + str(tuple(loc_cd_list))

    arcpy.MakeTableView_management(ss_live, "SS_FEATS", whereClause)
    result = arcpy.GetCount_management("SS_FEATS")
    count = int(result.getOutput(0))
    layer_attr = arcpy.AddFieldDelimiters(ss_live, "LOC_CD")

    if count == 0:
        for loc in loc_cd_list:
            arcpy.AddError("The Location Code {} does not exist in either your SS Main Location Template or the EVE SS Boundary!".format(loc))
            arcpy.GetMessages(2)
            error_count += 1

    else:
         for location in loc_cd_list:
            new_clause = layer_attr + " = '" + str(location) + "'"
            with arcpy.da.SearchCursor(ss_live, ["OID@", "SHAPE@"], new_clause) as sscursor:
                for ssloc in sscursor:
                    if ssloc[1].getArea("PLANAR", "SQUAREMETERS") > 0.0:
                        with arcpy.da.UpdateCursor(s_template, ["EDIT_TYPE", "SHAPE@"], new_clause) as ucursor:
                            for subloc in ucursor:
                                if subloc[0] == "CREATE" or subloc[0] == "MODIFY":
                                    if ssloc[1].contains(subloc[1]) is False:
                                        subloc[1] = ssloc[1].intersect(subloc[1], 4)


# function to check if modified sub location exists
def mod_check(s_template, ss_sub_live):
    global error_count
    s_list = []
    s_mod_list = []
    with arcpy.da.SearchCursor(s_template, ["OID@", "EDIT_TYPE", "SUB_LOC_CD"]) as scursor:
        for row in scursor:
            if row[1] == "MODIFY" and row[2] not in s_mod_list:
                    s_mod_list.append(row[2])

    if len(s_mod_list) == 0:
        return

    elif len(s_mod_list) == 1:
        layer_attr = arcpy.AddFieldDelimiters(ss_sub_live, "SUB_LOC_CD")
        whereClause = layer_attr + " = " + str(s_mod_list[0])

    elif len(s_mod_list) > 1:
        layer_attr = arcpy.AddFieldDelimiters(ss_sub_live, "SUB_LOC_CD")
        whereClause = layer_attr + " IN " + str(tuple(s_mod_list))

    if len(whereClause) == 0:
        arcpy.MakeFeatureLayer_management(ss_sub_live, "SS_SUB_FEATS", whereClause)
    else:
        arcpy.MakeFeatureLayer_management(ss_sub_live, "SS_SUB_FEATS")

    result = arcpy.GetCount_management("SS_SUB_FEATS")
    count = int(result.getOutput(0))

    if len(s_mod_list) == count:
        return

    elif len(s_mod_list) > count:
        with arcpy.da.SearchCursor("SS_SUB_FEATS", ["SUB_LOC_CD"]) as tcursor:
            for i in tcursor:
                if i[0] not in s_list:
                    s_list.append(i[0])

        non_represented = list(set(s_mod_list) - set(s_list))
        for aitem in non_represented:
            arcpy.AddError("You've digitised a sub-location modification, but the sub-location {} was not found".format(aitem))
            arcpy.GetMessages(2)
            error_count += 1


#function to check that no multiple sub-locations exists
def check_sub_location_count(s_template):
    s_loc_list = []
    with arcpy.da.SearchCursor(s_template, ["SUB_LOC_CD"]) as scursor:
        for row in scursor:
            if row[0] != None:
                s_loc_list.append(row[0])
    counter = collections.Counter(s_loc_list)
    for sloc in s_loc_list:
        if counter[sloc] > 1:
            arcpy.AddError("There are {} polygons with the sub-location code {}.\nPlease check your digitisation.".format(counter[sloc], sloc))
            arcpy.GetMessages(2)
            error_count += 1


#-------------------------------------------------------------------------------


#setting out the enviormental parameters
sub_location = arcpy.GetParameterAsText(0)
workspace = os.path.dirname(sub_location)
folder = os.path.dirname(workspace)
arcpy.env.workspace = workspace

#allowing for overwrite
arcpy.env.overwriteOutput = True

#creating the location codes logic dictionary
loc_ty_dict = {
"R":"A",
"S":"AS",
"O":"AO",
"F":"AF",
"GP":"AGP",
"D":"AD"
}

#creating the view only database file connection
con_path = folder + "\\" + "MAVEN_VIEW_TEMP.sde"
u = "U1NfR0lTX1ZJRVc="
p = "U1NnaXNWaWV3QDEyMw=="

if os.path.exists(con_path) == True:
    os.remove(con_path)

arcpy.CreateDatabaseConnection_management(folder, "MAVEN_VIEW_TEMP.sde", "SQL_SERVER", "NPMAVCLUS02\MSSQLSERVER1,60001", "DATABASE_AUTH", base64.b64decode(u), base64.b64decode(p), "SAVE_USERNAME", "Maven")

LIVE_SS = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.STREETSCAPE_LOCATION_BOUNDARY'
LIVE_PK = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.PARK_MAINTENANCE_BOUNDARY'
LIVE_EX = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.EXTERNAL_AGENCY_LOCATION_BOUNDARY'
LIVE_HT = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.HERITAGETREES_MAINTENANCE_BOUNDARY'
LIVE_SS_TREES = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.STREETSCAPETREES'
LIVE_SS_SUB = con_path + '\\' + r'Maven.OPS.EVE_GIS\Maven.OPS.STREETSCAPE_SUBLOCATION_BOUNDARY'

LIVE_LIST = [LIVE_EX, LIVE_HT, LIVE_PK, LIVE_SS]
MOD_LIVE_LIST = [LIVE_EX, LIVE_PK, LIVE_HT]

#fixing all the sub-location feature class geometry errors
arcpy.RepairGeometry_management(sub_location)

#getting the main location feature class
get_main_location_template(sub_location)

#fixing all the main-location feature class geometry errors
arcpy.RepairGeometry_management(main_location)

#params for the resulting clipped areas
s_buffer = "in_memory" + "//" + "S_BUFFER"
m_clip = "in_memory" + "//" + "main_template_CLIPPED"
ss_clip = "in_memory" + "//" + "SS_Areas_CLIPPED"

#generating the clip features
arcpy.Buffer_analysis(sub_location, s_buffer, "100 Meters", dissolve_option = "ALL")
arcpy.Clip_analysis(main_location, s_buffer, m_clip)
arcpy.Clip_analysis(LIVE_SS, s_buffer, ss_clip)

#getting a list of location codes for which new sub-locations are to be created
location_code_extractor(sub_location)

#starting the edit session
edit = arcpy.da.Editor(workspace)
edit.startEditing(False, False)
edit.startOperation()

sub_location_attributes(sub_location, m_clip, ss_clip, LIVE_SS_SUB)

edit.stopOperation()
edit.stopEditing(True)

if error_count > 0:
    arcpy.AddMessage("{} errors have been detected.\nPlease correct these errors and re-run the tool.".format(error_count))
else:
    arcpy.AddMessage("All digitisations are OK!")

arcpy.GetMessages(0)

os.remove(con_path)



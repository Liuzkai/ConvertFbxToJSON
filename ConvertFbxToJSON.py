import sys
from fbx import *
import FbxCommon
import os
import json
import argparse



def main_load_fbx(fbx_file, json_file = None):
    manager, scene = FbxCommon.InitializeSdkObjects()
    if FbxCommon.LoadScene(manager, scene, fbx_file) :
        data = {}
        import_fbx_data(scene, data)

        filename = json_file if len(json_file)>0 else os.path.split(sys.executable)[0] + '\\fbx_data.json'
        write_data(data, filename)

        scene.Destroy(True)


def import_fbx_data(scene, out_data):
    root = scene.GetRootNode()
    import_fbx_global_settings(scene, out_data)
    import_fbx_node(scene, root, out_data)


def import_fbx_global_settings(scene:FbxScene, out_data):
    global_settings:FbxGlobalSettings = scene.GetGlobalSettings()
    global_settings_data = get_properties(global_settings)
    out_data.update({"GlobalSettings": global_settings_data})


def import_fbx_node(scene, node:FbxNode, out_data):
    out_data.update({node.GetName() : get_node_data(node)})
    for i in range(node.GetChildCount()) :
        child = node.GetChild(i)
        import_fbx_node(scene, child, out_data)


def get_node_data(node):
    node_properties = get_properties(node)
    attr_properties = get_properties(node.GetNodeAttribute())
    node_data = {"Name": node.GetName(),
                 "ID": node.GetUniqueID(),
                 "Type": node.GetTypeName(),
                 "Parent": get_parent_id(node),
                 "Properties": node_properties,
                 "Attributes": attr_properties}
    return node_data


def get_properties(node):
    if node is None:
        return []
    node_property = node.GetFirstProperty()
    node_properties = {}
    while node_property.IsValid() :
        node_properties.update(get_property_data(node, node_property))
        node_property = node.GetNextProperty(node_property)

    return node_properties


def get_property_data(node:FbxNode, node_property: FbxProperty):

    out_data = { node_property.GetName().Buffer() : get_property_value(node, node_property)}

    return out_data


def get_property_value(node:FbxNode, node_property: FbxProperty):
    anim_curves = {}
    if get_property_animation_curve(node, node_property, anim_curves):
        return {'Default':get_property_value_internal(node_property) ,'AnimCurves': anim_curves}
    else:
        return get_property_value_internal(node_property)



def get_property_value_internal(node_property: FbxProperty):
    result = None
    if node_property.GetPropertyDataType().GetType() == EFbxType.eFbxDouble4:
        double4 = FbxPropertyDouble4(node_property).Get()
        result = (double4[0], double4[1], double4[2], double4[3])
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxDouble3:
        double3 = FbxPropertyDouble3(node_property).Get()
        result = (double3[0], double3[1], double3[2])
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxDouble2:
        double2 = FbxPropertyDouble2(node_property).Get()
        result = (double2[0], double2[1])
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxDouble:
        result = FbxPropertyDouble1(node_property).Get()
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxInt:
        result = FbxPropertyInteger1(node_property).Get()
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxFloat:
        result = FbxPropertyFloat1(node_property).Get()
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxBool:
        result = FbxPropertyBool1(node_property).Get()
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxString:
        result = FbxPropertyString(node_property).Get().Buffer()
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxEnum:
        result = FbxPropertyEnum(node_property).Get()
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxTime:
        result = FbxPropertyFbxTime(node_property).Get().GetFrameCount()
    elif node_property.GetPropertyDataType().GetType() == EFbxType.eFbxDateTime:
        result = FbxPropertyDateTime(node_property).Get().toString()
    return result


def get_property_animation_curve(node:FbxNode, node_property: FbxProperty, out_anim_curve:dict):
    # out_anim_curve = {}
    scene:FbxScene = node.GetScene()

    for anim_layer in get_animation_layers(scene):
        anim_curve_data = {}
        anim_curve_nodes = node_property.GetCurveNode(anim_layer)

        if anim_curve_nodes is None:
            continue

        channel_count = anim_curve_nodes.GetChannelsCount()
        for c in range(channel_count):
            curve_count = anim_curve_nodes.GetCurveCount(c)
            for cc in range(curve_count):

                anim_curve:FbxAnimCurve = anim_curve_nodes.GetCurve(c,cc) # Consider one animation curve only
                if anim_curve is None:
                    continue

                curve_name = anim_curve_nodes.GetName()
                if channel_count > 1:
                    curve_name += "_{}".format(anim_curve_nodes.GetChannelName(c))
                elif curve_count > 1:
                    curve_name += "_{}".format(cc)
                anim_curve_data.update({ curve_name: get_curve_keys(anim_curve)})

        if len(anim_curve_data) > 0:
            out_anim_curve.update({anim_layer.GetName(): anim_curve_data})

    return len(out_anim_curve) > 0


def get_curve_keys(anim_curve:FbxAnimCurve):
    keys = []
    for i in range(anim_curve.KeyGetCount()):

        key_value = anim_curve.KeyGetValue(i)
        key_time: FbxTime = anim_curve.KeyGetTime(i).GetSecondDouble()
        key_frame: FbxTime = anim_curve.KeyGetTime(i).GetFrameCount()

        key_break = anim_curve.KeyGetBreak(i)
        key_con = anim_curve.KeyGetConstantMode(i).name

        key_intp = anim_curve.KeyGetInterpolation(i).name # eInterpolationConstant, eInterpolationLinear, eInterpolationCubic
        key_tang = anim_curve.KeyGetTangentMode(i).name  # pIncludeOverrides Include override flags: Break, Clamp, Time-Independent.

        key_lder_info: FbxAnimCurveTangentInfo = anim_curve.KeyGetLeftDerivativeInfo(i)
        key_rder_info: FbxAnimCurveTangentInfo = anim_curve.KeyGetRightDerivativeInfo(i)

        key = {"time": key_time,
               "frame": key_frame,
               "value": key_value,

               "break": key_break,
               "con": key_con,

               "intp": key_intp,
               "tang": key_tang,

               "left auto" : key_lder_info.mAuto,
               "right auto" : key_rder_info.mAuto,

               "left slope" : key_lder_info.mDerivative,
               "right slope" : key_rder_info.mDerivative,

               "left weighted": key_lder_info.mWeighted,
               "left weight": key_lder_info.mWeight,
               "right weighted": key_rder_info.mWeighted,
               "right weight" : key_rder_info.mWeight,
               "left has velocity" : key_lder_info.mHasVelocity,
               "left velocity": key_lder_info.mVelocity,
               "right has velocity" : key_rder_info.mHasVelocity,
               "right velocity": key_rder_info.mVelocity,
               }
        keys.append(key)
    return keys


def get_animation_layers(scene:FbxScene):
    anim_layers = []
    if scene is None:
        return anim_layers
    for i in range(scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))):
        anim_stack = scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i)
        if anim_stack :
            for j in range(anim_stack.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimLayer.ClassId))):
                anim_layers.append(anim_stack.GetSrcObject(FbxCriteria.ObjectType(FbxAnimLayer.ClassId), j))
    return anim_layers


def get_parent_id(node):
    parent_node = node.GetParent()
    parent_id = -1
    if parent_node :
        parent_id = parent_node.GetUniqueID()
    return parent_id


def write_data(pdata, file_name):
    jdata = json.dumps(pdata)
    with open(file_name, 'w') as f:
        f.write(jdata)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert Fbx to Json Tool 1.0 @zhongkailiu')
    parser.add_argument('file', type = str,help='Fbx File Path')
    parser.add_argument('json', nargs= '?', default="", type = str,help='Json File Path')
    args = parser.parse_args()

    main_load_fbx(args.file, args.json)

import hou
import json
import os
import math



def import_lights_from_json(json_file):
    data = load_json(json_file)
    subnet = create_hou_subnet(json_file)
    import_lights(subnet, data)


def load_json(filename):
    with open(filename, 'r') as json_file:
        return json.load(json_file)


def import_lights(scene, data):
    for key, item in data.items():
        if type(item) is dict:
            if "Type" in item.keys():
                if item["Type"] == "Light":
                    create_hou_light(scene, item)


def create_hou_subnet(filename):
    subnet =  hou.node('/obj').createNode('subnet', os.path.split(filename)[1])
    subnet.moveToGoodPosition()
    return subnet


def create_hou_light(scene, item):
    new_light = scene.createNode('hlight', item['Name'])
    new_light.moveToGoodPosition()
    set_light_common_attributes(new_light)
    set_light_attributes_from_data(new_light, item)


def set_light_common_attributes(light):
    # add preRotation and postRotation data for convert coord
    temp_g = light.parmTemplateGroup()
    rpre_parm = hou.FloatParmTemplate('rpre', 'Pre Rotate', 3, default_value = [-90.0, 0.0, 0.0])
    rpost_parm = hou.FloatParmTemplate('rpost', 'Post Rotate', 3, default_value = [-90.0,0.0,0.0])
    temp_g.append(rpre_parm)
    temp_g.append(rpost_parm)
    light.setParmTemplateGroup(temp_g)
    # default icon scale
    light.parm('iconscale').set(20)



def set_light_attributes_from_data(light, data):
    # set light type
    light_type = set_light_type(light, data)
    # set light parameters
    set_light_attrbutes(light, data, light_type)



def set_light_attrbutes(light, data, light_type=None):
    pts = data['Properties']
    ats = data['Attributes']
    set_hou_parm(light, 'tx', pts['Lcl Translation'], 0, 1,True)
    set_hou_parm(light, 'ty', pts['Lcl Translation'], 2, 1,True)
    set_hou_parm(light, 'tz', pts['Lcl Translation'], 1, -1.0,True)
    set_hou_parm(light, 'rx', pts['Lcl Rotation'], 0, 1,True)
    set_hou_parm(light, 'ry', pts['Lcl Rotation'], 1, 1,True)
    set_hou_parm(light, 'rz', pts['Lcl Rotation'], 2, 1,True)
    if 'Intensity' in pts.keys():
        set_hou_parm(light, 'light_intensity', pts['Intensity'], 0, 1,False)
    if 'Color.R' in pts.keys():
        set_hou_parm(light, 'light_colorr', pts['Color.R'], 0, 1,False)
    if 'Color.G' in pts.keys():
        set_hou_parm(light, 'light_colorg', pts['Color.G'], 0, 1,False)
    if 'Color.B' in pts.keys():
        set_hou_parm(light, 'light_colorb', pts['Color.B'], 0, 1,False)
    if 'OuterConeAngle' in pts.keys():
        set_hou_parm(light, 'coneangle', pts['OuterConeAngle'], 0, 1, False)



def set_hou_parm(node, parm_name, value, index = 0, factor = 1.0,multi_channels=False ):

    if type(value) is dict:
        # Has Animation
        set_hou_parm_animation(node, parm_name, value, index, factor, multi_channels)
    else:
        # No Animation
        in_value = value[index] if multi_channels else value
        node.parm(parm_name).set(in_value * factor)



def set_hou_parm_animation(node, parm_name, value, index, factor=1.0, multi_channels=False):
    anim_curves = value["AnimCurves"]
    default = value["Default"]
    # set default data
    node.parm(parm_name).set(default[index] * factor if multi_channels else default * factor)

    if 'Base Layer' in anim_curves.keys():
        # TODO : support multi-animation-layers
        base_layer = anim_curves['Base Layer']

        if multi_channels:
            channel_name = ['X', 'Y', 'Z', 'W']
            channel_curve = None
            for k, v in base_layer.items():
                if k.endswith(channel_name[index]):
                    channel_curve = v
                    break
            if channel_curve:
                set_hou_parm_animation_internal(node, parm_name, channel_curve, factor)

        else:
            channel_curve = list(base_layer.values())[0]
            if channel_curve:
                set_hou_parm_animation_internal(node, parm_name, channel_curve, factor)



def set_hou_parm_animation_internal(node, parm_name, keys, factor = 1.0):
    hou_key_frames = []
    counter = 0
    for key in keys:
        new_key = hou.Keyframe()
        new_key.setFrame(key['frame'])
        new_key.setValue(key['value'] * factor)
        set_curve_interpolation(new_key, keys, counter, factor)

        hou_key_frames.append(new_key)
        counter += 1

    node.parm(parm_name).setKeyframes(hou_key_frames)



def set_curve_interpolation(key_node, keys, index, factor):
    ck = keys[index]
    ck_type = intp_type(ck)

    if ck_type == 'constant()':
        key_node.setSlopeAuto(True)

    elif ck_type == 'linear()':
        if index == len(keys) - 1: # end key frame
            if index == 0: # only one key frame
                key_node.setSlopeAuto(True)
            pk = keys[index-1]
            pk_type = intp_type(pk)
            if pk_type == 'bezier()':
                set_slope_and_accel(key_node, keys, index, 'eTangentBreak',factor, True)
                ck_type = 'bezier()'
            else:
                key_node.setSlopeAuto(True)
        else:
            nk = keys[index + 1]
            nk_type = intp_type(nk)
            if nk_type == 'cubic()' or nk_type == 'bezier()':
                # if next point is cubic/bezier, converts this to cubic too
                set_slope_and_accel(key_node, keys, index,'eTangentBreak', factor,  True)
                ck_type = 'bezier()'
            else:
                key_node.setSlopeAuto(True)

    elif ck_type == 'cubic()' or ck_type == 'bezier()':

        if index == 0: # start point
            key_node.setSlope(slope(ck, True) * factor)
            key_node.setAccel(accel(keys, index, True))
        else:
            if index < len(keys) - 1:
                nk = keys[index + 1]
                nk_type = intp_type(nk)
                if nk_type == 'bezier()':
                    # cubic convert to bezier()
                    ck_type = 'bezier()'
            set_slope_and_accel(key_node, keys, index, ck['tang'], factor, True)

    key_node.setExpression(ck_type, hou.exprLanguage.Hscript)



def intp_type(key:dict):
    if 'intp' not in key.keys():
        return 'bezier()'
    if key['intp'] == 'eInterpolationCubic':
        if key['left weighted'] or key['right weighted']:
            return 'bezier()'
        else:
            return 'cubic()'
    elif key['intp'] == 'eInterpolationLinear':
        return 'linear()'
    elif key['intp'] == 'eInterpolationConstant':
        return 'constant()'



def slope(key:dict, right = True):
    return get_float_safely(key, 'right slope', 0.0) if right else get_float_safely(key, 'left slope', 0.0)



def accel(keys:list, index:int, right = True):
    # reference : https://www.sidefx.com/docs/houdini/anim/convert_keys.html
    # TW^2 = W^2*DT^2 * (1 + S^2)

    W = 0.0
    S = slope(keys[index], right)
    DT = 0.0
    if right and index < len(keys)-1 :
        current_time = get_float_safely(keys[index], 'time', 0.0)
        next_time = get_float_safely(keys[index+1], 'time', 0.0)
        W = get_float_safely(keys[index], 'right weight', 0.0)
        DT = current_time - next_time
    elif not right and index >0 :
        current_time = get_float_safely(keys[index], 'time', 0.0)
        previous_time = get_float_safely(keys[index-1], 'time', 0.0)
        W = get_float_safely(keys[index], 'left weight', 0.0)
        DT = current_time - previous_time

    return math.sqrt(W * W * DT * DT * (1 + S*S))



def set_slope_and_accel(key_node, keys:list, index:int, mode:str, factor = 1.0,  set_in = False):
    key = keys[index]
    if mode == 'eTangentAuto':
        key_node.setSlopeAuto(True)
    elif mode == 'eTangentBreak':
        if set_in:
            key_node.setInSlope(slope(key, False) * factor)
            key_node.setInAccel(accel(keys, index, False))
        key_node.setSlope(slope(key, True) * factor)
        key_node.setAccel(accel(keys, index, True))
    elif mode == 'eTangentUser':  # eTangentUser
        if set_in:
            key_node.setInSlope(slope(key, True) * factor)
            key_node.setInAccel(accel(keys, index, True))
        key_node.setSlope(slope(key, True) * factor)
        key_node.setAccel(accel(keys, index, True))



def get_float_safely(data:dict, name:str, default:float = 0.0):
    v = data[name]
    return default if is_NaN(v) else v


def is_NaN(value):
    # Json NaN is always unequals
    return not value == value


def set_light_type(light, data):
    def cast_point_light(hou_light, attributes=None):
        hou_light.parm('light_type').set(0)
        hou_light.parm('coneenable').set(0)
        return 'PointLight'

    def cast_spot_light(hou_light, attributes=None):
        hou_light.parm('light_type').set(0)
        hou_light.parm('coneenable').set(1)
        hou_light.parm('coneangle').set(attributes['OuterAngle']) # override
        return 'SpotLight'

    def cast_distant_light(hou_light, attributes=None):
        hou_light.parm('light_type').set(7)
        hou_light.parm('coneenable').set(0)
        hou_light.parm('light_intensity').set(attributes['Intensity'] * 0.01)  # override
        return 'DistantLight'

    def cast_area_light(hou_light, attributes=None):
        hou_light.parm('light_type').set(2)
        hou_light.parm('coneenable').set(0)
        return 'AreaLight'

    cast_light_type = { 0 : cast_point_light,
                        1 : cast_distant_light,
                        2 : cast_spot_light,
                        3 : cast_area_light,
                        4 : cast_point_light}

    light_type = cast_light_type.get(get_item_attribute(data, 'LightType'))
    return light_type(light, data['Attributes'])




def get_item_property(item, property_name):
    if 'Properties' not in item.keys():
        return []
    properties = item['Properties']
    return properties[property_name] if property_name in properties.keys() else None


def get_item_attribute(item, attribute_name):
    if 'Attributes' not in item.keys():
        return []
    attributes = item['Attributes']
    return attributes[attribute_name] if attribute_name in attributes.keys() else None



if __name__ == '__main__':
    json = 'D:\\Temp\\scenes_with_light.json'
    import_lights_from_json(json)
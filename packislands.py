import bpy
from bpy import context as C, ops as O, data as D
from time import time


kwargs = { # pack_islands operator settings
'rotate' : True,
'margin' : .001}


def core(obj):
    C.scene.objects.active = obj
    O.object.editmode_toggle()
    O.uv.select_all(action='SELECT')
    O.uv.pack_islands(**kwargs)
    O.object.editmode_toggle()


def pack_uvs(input):
    if C.mode != 'OBJECT': #pre-set required mode
        O.object.editmode_toggle()
        
    start = time()
            
    if type(input) is list:
        for obj in input:
            if obj.type == 'MESH':
                if obj.data.uv_textures:
                    core(obj)
        end = abs(round(start - time(), 2))
        print ("Finished in", end, "seconds.")

    elif type(input) is bpy.types.Object:
        if input.type == 'MESH':
                if input.data.uv_textures:
                    core(input)

    for obj in D.objects: # restore selection
        obj.select = False if not obj in selection else True
    C.scene.objects.active = ao

selection, ao = C.selected_objects, C.active_object

pack_uvs(C.selected_objects)

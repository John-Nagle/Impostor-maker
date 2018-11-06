#
#   Impostor maker for Second Life
#
#   Renders selected objects orthographically and puts
#   those images on the faces of the last-selected object.
#
#   John Nagle
#   October, 2018
#   License: GPL 3
#
#   Impostor maker, where the work gets done.
#
import bpy
import bmesh
import mathutils
import math
import tempfile
import os
#
#   Constants
#
DRAWABLE = ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'ARMATURE', 'LATTICE']      # drawable types

NORMALERROR = 0.001                     # allowed difference for two normals being the same
IMPOSTORPREFIX = "IMP-"                 # our textures and materials begin with this

#   Debug settings
DEBUGPRINT = True                       # enable debug print
DEBUGMARKERS = False                    # add marking objects to scene

#   Non-class functions

def matrixlookat(eye, targetpt, up) :
    """
    Generate a LookAt matrix. Rotates to object pointing in dirvec with given up vector.
    
    From https://github.com/mono/opentk/blob/master/Source/OpenTK/Math/Matrix4.cs
    """
    z = eye - targetpt
    x = up.cross(z)
    y = z.cross(x)
    
    x.normalize()
    y.normalize()
    z.normalize()
    
    rot = mathutils.Matrix()
    rot[0][0] = x[0]
    rot[0][1] = y[0]
    rot[0][2] = z[0]
    rot[0][3] = 0
    rot[1][0] = x[1]
    rot[1][1] = y[1]
    rot[1][2] = z[1]
    rot[1][3] = 0
    rot[2][0] = x[2]
    rot[2][1] = y[2]
    rot[2][2] = z[2]
    rot[2][3] = 0
    
    # eye not need to be minus cmp to opentk 
    # perhaps opentk has z inverse axis
    tran = mathutils.Matrix.Translation(eye)
    return tran * rot
    
def addtestpoint(pos) :
    """
    Add visible small test point for debug
    """
    bpy.ops.mesh.primitive_cube_add(location=pos)
    bpy.context.object.name = "Testpt"
    bpy.context.object.scale = (0.1,0.1,0.1)                # apply scale
    
def vecmult(v0, v1) :
    """
    Element by element vector multiply, for scaling
    """
    return mathutils.Vector((v0[0]*v1[0], v0[1]*v1[1], v0[2]*v1[2]))
    
def nextpowerof2(n, maxval) :
    """
    Round up to next power of 2
    """
    x = 1
    while x < n :                       # if not big enough yet
        if x > maxval :
            raise ValueError("Image size %d is too large. Limit %d" % (n,maxval))
        x = x * 2                       # next power of 2
    return x
        
    
def gettestmatl(name, color) :
    """
    Create simple colored material for test objects
    """
    matl = bpy.data.materials.get(name)
    if matl is None:
        # create material
            matl = bpy.data.materials.new(name=name)
            matl.diffuse_color = color
    return matl
        
def setnorender(ob, viz):
    """
    Set rendering invisibility of object and children
    """
    ob.hide_render = viz
    for child in ob.children :
        setvisible(child, viz)
        
def deleteimg(img) :
    """
    Delete image object
    """
    img.user_clear                          # clear this object of users
    ###bpy.context.scene.objects.unlink(obj)   # unlink the object from the scene
    bpy.data.images.remove(img)            # delete the object from the data block

class ImageComposite :
    """
    Image composited from multiple images
    """
    CHANNELS = 4                                    # RGBA
    
    def __init__(self, filepath, width, height) :
        #   RGBA image initialized to black transparent
        name = os.path.splitext(os.path.basename(filepath))[0]          # name without path
        if not name :
            raise ValueError("Invalid file name for composite: \"%s\"" % (filename,))
        if name in bpy.data.images :                                    # release old image because we are changing size
            oldimg = bpy.data.images[name]
            oldimg.user_clear
            bpy.data.images.remove(oldimg)
        bpy.ops.image.new(name=name, width=width, height=height, color=(0.0, 0.0, 0.0, 0.0), alpha=True)  
        self.image = bpy.data.images[name]          # must get by name
        assert self.image, "ImageComposite image not stored properly" 
        print("ImageComposite size: (%d,%d)" % (width,height))      # ***TEMP***
        self.image.filepath = filepath              # will be saved here  
        
    def getimage(self) :
        """
        Return image object
        """
        return self.image
        
    def paste(self, img, x, y) :
        """
        Paste image into indicated position
        """
        (inw, inh) = img.size                       # input size of image
        (outw, outh) = self.image.size              # existing size
        if (inw + x > outw or inh + y > outh or     # will it fit?
            x < 0 or y < 0) :
            raise ValueError("Image paste of (%d,%d) at (%d,%d) into (%d,%d), won't fit." % (inw, inh, x, y, outw, outh))  
        print("Pasting (%d,%d) at (%d,%d) into (%d,%d), input length %d, output length %d." % (inw, inh, x, y, outw, outh, len(img.pixels), len(self.image.pixels)))  # ***TEMP***
        ####for pixel in img.pixels[0:100] :
        ####    print("Pixel: %d" % (pixel,))           # ***TEMP***
        if x == 0 and inw == outw :                 # easy case, full rows
            start = y*outw*ImageComposite.CHANNELS                 # offset into image
            end = start + inw*inh*ImageComposite.ImageComposite.CHANNELS
            print("Paste image to %d:%d length %d" % (start, end, len(img.pixels)))   # ***TEMP***
            self.image.pixels[start:end] = img.pixels[:]      # do paste all at once
        else :                                      # hard case, row by row
            outpos = (x + y*outw) * ImageComposite.CHANNELS        # start here in old image
            stride = outw * ImageComposite.CHANNELS    
            instart = 0  
            for offset in range(0, inh*stride, stride) : # copy by rows
                start = outpos + offset
                end = start + inw*ImageComposite.CHANNELS 
                ####print("Paste row to %d:%d from %d:%d" % (start, end, instart, instart+inw*ImageComposite.CHANNELS))   # ***TEMP***
                self.image.pixels[start : end] = img.pixels[instart : instart+inw*ImageComposite.CHANNELS]
                instart = instart + inw*ImageComposite.CHANNELS 
        
class ImageLayout :
    """
    Very simple image layout planner
    
    Ask for a rectangle, and it fits it in.
    """
    
    def __init__(self, margin, width, height = None) :
        self.width = width
        self.height = height                        # desired height, or none for auto
        self.margin = margin
        self.xpos = 0                               # next starting point, X
        self.ypos = 0                               # next starting point, Y
        self.ymax = 0                               # used this much space
        self.rects = []                             # allocated rectangles
        
    def getrect(self, width, height) :
        """
        Ask for a rectangle, get back starting corner
        """
        if (width > self.width - 2*self.margin) :
            raise ValueError("Image too large to composite into target image")
        #   Try to fit in current row
        if self.xpos + width + 2*self.margin < self.width : # if can fit in this row
            corner = (self.xpos + self.margin, self.ypos + self.margin)
            self.xpos = self.xpos + width + self.margin  # use up space
            self.ymax = max(self.ymax, self.ypos + height + self.margin)
        else :
            #   Must start a new row
            self.ypos = self.ymax
            self.xpos = 0
            corner = (self.xpos + self.margin, self.ypos + self.margin)
            self.xpos = self.xpos + width + self.margin  # use up space
            self.ymax = max(self.ymax, self.ypos + height + self.margin)
        rect = (corner[0], corner[1], corner[0] + width, corner[1] + height)
        self.rects.append(rect)                     # allocated rectangle
        if self.height and self.ypos > self.height :    # if specified size and won't fit
            raise ValueError("Image (%d,%d) will not fit into desired target image size of (%d,%d)" % (width, height, self.width, self.height))
        return rect
            
    def getsize(self) :
        """
        Return final size of image
        """
        if self.height :                                # if caller specified height
            return (self.width, self.height)            # use it
        return (self.width, self.ymax)                  # otherwise report height needed
        
    def getmargin(self) :
        return self.margin
        
    def getrects(self) :
        """
        Return list of rects
        """
        return self.rects       
        
    def dump(self) :
        """
        Debug use
        """
        print("Layout size (%d,%d) Rectangles: " % (self.getsize()))
        for rect in self.rects :
            print("  (%d,%d) - (%d,%d)" % (rect))
        


class ImpostorFace :
    """
    Face of an impostor object.
    
    Contains one or more polygons, all coplanar.
    """        
    def __init__(self, context, target, poly) :
        self.normal = None                  # normal in object coords
        self.vertexids = []                 # vertex indices into 
        self.loopindices = []               # loop index (sequential numbers)
        self.scaledverts = []               # vertices in object frame after scaling
        self.baseedge = None                # (vertID, vertID)
        self.center = None                  # center of face, object coords
        self.facebounds = None              # size bounds of face, world scale
        self.target = target                # the Blender object
        self.poly = poly                    # the Blender face
        rot = (target.matrix_world.to_3x3().normalized()).to_4x4() # rotation only
        trans = mathutils.Matrix.Translation(target.matrix_world.to_translation())
        self.worldtransform = trans * rot   # transform to global coords
        ####self.worldtransform = target.matrix_world  # transform to global coords
        assert target.type == "MESH", "Must be a mesh target"
        me = target.data                    # mesh info
        vertices = me.vertices
        if poly.loop_total < 3 :            # can't compute a normal
            raise RuntimeError("A face of \"%s\" has less than 3 vertices." % (target.name,))
        #   We need a normal for the face. Not a graphics normal, a geometric one based on the vertices.
        #   We also need the base edge for the image and the center of the face.
        baseedgelength = -math.inf          # no base edge length yet
        meloop = me.loops[poly.loop_start : poly.loop_start + poly.loop_total]   # vertices of this loop
        for loop_index in range(len(meloop)) :
            #   Get 3 succesive vertices for 2 edges
            vid0 = meloop[loop_index].vertex_index
            self.loopindices.append(loop_index + poly.loop_start)    # loop index for this vertex
            vid1 = meloop[(loop_index + 1) % poly.loop_total].vertex_index # next, circularly
            vid2 = meloop[(loop_index + 2) % poly.loop_total].vertex_index # next, circularly
            ####print("    Loop index %d: Vertex indices: %d %d %d" % (loop_index, vid0, vid1, vid2))  
            #   Get two successive edges to get a normal for the face              
            v0 = vecmult(target.scale, me.vertices[vid0].co)       # get 3 points, wrapping around
            v1 = vecmult(target.scale, me.vertices[vid1].co)
            v2 = vecmult(target.scale, me.vertices[vid2].co)
            self.vertexids.append(vid0)     # save vertex
            self.scaledverts.append(v0)     # save vertex loc, scaled
            print("    Vertex: %d: (%1.4f,%1.4f,%1.4f)" % (vid0, v0[0],v0[1],v0[2]))
            cross = (v1-v0).cross(v2-v1)    # direction of normal
            #### print("   Cross: " + str(cross))
            if cross.length < NORMALERROR : # collinear edges - cannot compute a normal
                print("  Cross length error: %f" % (cross.length))  # ***TEMP*** this is OK, not an error
                continue                    # skip this edge pair
            cross.normalize()               # normal vector, probably
            if self.normal :
                if abs(self.normal.dot(cross)) < 1.0 - NORMALERROR :
                    print("Dot product of normal %s and edge %s is %1.4f, not zero." % (self.normal, cross, self.normal.dot(cross)))
                    raise RuntimeError("A face of \"%s\" is not flat." % (target.name,))
            else :
                self.normal = cross             # we have a face normal
            #   Find longest edge. This will orient the image.
            edge = v1 - v0                      # element by element multiply
            edgelength = edge.length
            if edgelength > baseedgelength :
                baseedgelength = edgelength     # new winner
                self.baseedge = (v0, v1)        # save longest edge coords
            #   Compute center of face. Just the average of the corners.
            if not self.center :
                self.center = v0
            else :
                self.center = self.center + v0  # sum the vertices
        #   All vertices examined.  
        if not self.normal :
            raise RuntimeError("Unable to compute a normal for a face of \"%s\"." % (target.name,)) # degenerate geometry of some kind  
        ####if poly.normal.dot(self.normal) > 0.0 : # if our normal is backwards
        ####    print("Flipping normal: %s" % ((self.normal),))
        ####    self.normal = -self.normal          # invert ours  
        self.center = self.center / poly.loop_total # average to get center of face         
        print("  Face normal: (%1.4f,%1.4f,%1.4f)" % (self.normal[0],self.normal[1],self.normal[2])) 
        #   Compute bounding box of face.  Use longest edge to orient the bounding box
        #   This will be the area of the image we will take and map onto the face.
        
        faceplanemat = self.getfaceplanetransform()                                 # transform object points onto face plane
        faceplanematinv = faceplanemat.copy()
        faceplanematinv.invert()                                                    # transform face plane back to object points
        ####pts = [faceplanematinv * me.vertices[vid].co for vid in self.vertexids]     # points transformed onto face, now 2D
        pts = [faceplanematinv * vert for vert in self.scaledverts]                 # vertices transformed onto face, now 2D
        for pt in pts :                                                             # all points must be on face plane
            assert abs(pt[2]  < 0.01), "Internal error: Vertex not on face plane"   # point must be on face plane
        minx = min([pt[0] for pt in pts])                                           # size per max excursion in X
        miny = min([pt[1] for pt in pts])                                           # size per max excursion in X
        maxx = max([pt[0] for pt in pts])                                           # size per max excursion in X
        maxy = max([pt[1] for pt in pts])                                           # size per max excursion in X
        #    Compute bounding box in face plane coordinate system
        lowerleft = mathutils.Vector((minx, miny, 0.0))                             # bounding box in face coordinates
        upperright = mathutils.Vector((maxx, maxy, 0.0))
        width = upperright[0] - lowerleft[0]                                        # dimensions for ortho camera
        height = upperright[1] - lowerleft[1]
        self.facebounds = (width, height)

        
        lowerleft = faceplanemat * mathutils.Vector((minx, miny, 0.0))              # we have to transfer these back to obj coords to scale
        upperright = faceplanemat * mathutils.Vector((maxx, maxy, 0.0))
        newcenter = (lowerleft + upperright)*0.5                                    # in object coords
        #   Re-center
        print("Old center: %s  New center: %s" % (str(self.center), str(newcenter)))
        self.center = newcenter                                                     # and use it
        print("Face size, scaled: %f %f" % (self.facebounds))                     # ***TEMP***
        for pt in pts :
            print (pt)                                               ##  ***TEMP***
        
    def getfaceplanetransform(self) :
        """
        Calculate a transform which will transform coordinates of the face into
        local coordinates such that 
        1) X axis is aligned with self.baseedge
        2) Z axis is aligned with normal and +Z is in the normal direction
        3) Origin is at self.center      
        """
        #### print("Base edge" + str(self.baseedge))    # ***TEMP***
        xvec = self.baseedge[1] - self.baseedge[0]                      # +X axis of desired plane, perpendicular to normal
        ### xvec = -xvec # ***TEMP***
        upvec = xvec.cross(self.normal)                                 # up vector
        orientmat = matrixlookat(self.center, self.center - self.normal, upvec)     # rotation to proper orientation 
        return orientmat                                                
                       
    def getcameratransform(self, disttocamera = 5.0) :
        """
        Get camera transform, world coordinates
                """
        xvec = self.baseedge[1] - self.baseedge[0]                      # +X axis of desired plane, perpendicular to normal
        cameranormal = self.normal
        if self.poly.normal.dot(cameranormal) < 0 :
            cameranormal = -cameranormal
        upvec = xvec.cross(self.normal)                                # up vector
        print("Getcameratransform: upvec: %s, normal: %s  camera normal %s" % (upvec, self.normal, cameranormal))
        orientmat = matrixlookat(mathutils.Vector((0,0,0)), -cameranormal, upvec)     # rotation to proper orientation 
        camerapos = self.center + cameranormal*disttocamera              # location of camera, object coords
        posmat = mathutils.Matrix.Translation(camerapos)
        return self.worldtransform * (posmat * orientmat)               # camera in world coordinates
      
    def getcameraorthoscale(self) :
        """
        Get camera orthographic scale.
        (width, height)
        """
        return self.facebounds
        
        
    def getedgeids(self) :
        """
        Return set of edge tuples for this face
        """
        return self.edgeids
        
    def getfacebounds(self) :
        """
        Returns width, for sorting
        """
        return self.facebounds
        
    def setupcamera(self, camera, dist = 5.0, margin = 0.0) :
        """
        Set camera params
        """
        camera.data.ortho_scale = self.getcameraorthoscale()[0] * (1.0+margin)   # width of bounds, plus debug margin if desired
        camera.matrix_world = self.getcameratransform(dist)
        camera.data.type = 'ORTHO'

        
    def rendertofile(self, filename, width, height) :
        """
        Render to file
        
        ***NEEDS MORE PARAMS***
        ***NEED TO SAVE CAMERA PARAMS AND RETURN TO NORMAL OR USE A NEW CAMERA***
        ***NEED TO WORK OUT FILENAME/OBJECT NAME UNIQUENESS ISSUES***
        """
        heightalt = int(math.floor((self.facebounds[1] / self.facebounds[0]) * width))     # user sets width, height is just enough for info
        assert abs(height-heightalt) < 2, "Height estimate is wrong"                    # ***TEMP*** not sure about this
        bpy.context.scene.render.filepath = filename
        bpy.context.scene.render.resolution_x = width
        bpy.context.scene.render.resolution_y = height
        bpy.context.scene.render.pixel_aspect_x = 1.0
        bpy.context.scene.render.pixel_aspect_y = 1.0
        bpy.context.scene.render.resolution_percentage = 100                            # mandatory, or we get undersized output
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'                     # ask for alpha channel
        bpy.context.scene.render.alpha_mode = 'TRANSPARENT'                             # transparent background, Blender renderer
        bpy.context.scene.cycles.film_transparent = True                                # transparent background, Cycles renderer
        bpy.ops.render.render(write_still=True) 
        
    def rendertoimage(self, fd, width, height) :
        """
        Render to new image object
        """
        fd.truncate()                                                                   # clear file before rendering into it
        filename = fd.name
        self.rendertofile(filename, width, height)                                      # render into temp file
        print("Temp file: %s  (%d,%d)" % (filename, width, height))
        ####image = bpy.ops.image.new(name="Face render", width=width, height=height, color=(0.0, 0.0, 0.0, 0.0), alpha=True)   # render result goes here
        ####image.open(fd.name)                                                         # load rendered image
        bpy.data.images.load(filename, check_existing=True)
        imgname = os.path.basename(filename)    # Blender seems to want base name
        image = bpy.data.images[imgname]                                                # image object
        assert image, "No image object found"
        assert image.size[0] == width, "Width different after render. Was %d, should be %d" % (image.size[0], width)
        assert image.size[1] == height, "Height different after render. Was %d, should be %d" % (image.size[1], height)
        image.reload()                  # try to get pixels from render into memory
        assert image.size[0] == width, "Width different after reload. Was %d, should be %d" % (image.size[0], width)
        assert image.size[1] == height, "Height different after reload. Was %d, should be %d" % (image.size[1], height)
        return image
        
    def setuvs(self, target, rect, margin, finalimagesize) :
        """
        Set UVs for this face to map rect inset by margin into the final image
        """
        faceplanemat = self.getfaceplanetransform()                                
        faceplanematinv = faceplanemat.copy()
        faceplanematinv.invert()                                                    # transform object points onto face plane
        insetrect = (rect[0]+margin, rect[1]+margin, rect[2]-margin, rect[3]-margin)# actual area into which face was rendered, not including margin
        me = self.target.data                       # mesh info
        assert me, "Dump - no mesh"
        if not me.uv_layers.active :
            raise RuntimeError("Target object has no UV coordinates yet.")          # need to create these first          
                       
        for vert, vertex_index, loop_index in zip(self.scaledverts, self.vertexids, self.loopindices) :
            pt = faceplanematinv * vert                                             # point in face plane space
            assert abs(pt[2]  < 0.01), "Internal error: Vertex not on face plane"   # point must be on face plane, with Z = 0
            fractpt = ((pt[0] + self.facebounds[0]*0.5) / (self.facebounds[0]),
                       (pt[1] + self.facebounds[1]*0.5) / (self.facebounds[1]))     # point in 0..1 space on face plane
            ####fractpt = (1.0-fractpt[0], fractpt[1])                                  # ***TEMP FIX*** u is backwards
            #   UV points are in 0..1 over entire image space
            uvpt = ((insetrect[0] + fractpt[0] * (insetrect[2]-insetrect[0])) / finalimagesize[0],
                    (insetrect[1] + fractpt[1] * (insetrect[3]-insetrect[1])) / finalimagesize[1])
            print("UV: Vertex (%1.2f,%1.2f) -> face point (%1.2f, %1.2f) -> UV (%1.3f, %1.3f)" % (pt[0], pt[1], fractpt[0], fractpt[1], uvpt[0], uvpt[1]))
            me.uv_layers.active.data[loop_index].uv.x = uvpt[0]         # apply UV indices
            me.uv_layers.active.data[loop_index].uv.y = uvpt[1]
        
                         
                    
    def dump(self) :
        """
        Debug output
        """
        print("Face:  %d vertices, normal (%1.4f,%1.4f,%1.4f), center (%1.4f,%1.4f,%1.4f)" % 
            (len(self.vertexids), self.normal[0], self.normal[1], self.normal[2], self.center[0], self.center[1], self.center[2])) 
        me = self.target.data                       # mesh info
        assert me, "Dump - no mesh"
        for vert_idx, loop_idx in zip(self.poly.vertices, self.poly.loop_indices):
            if me.uv_layers.active :
                uv_coords = me.uv_layers.active.data[loop_idx].uv   
                print("face idx: %i, vert idx: %i, uv: (%f, %f)" % (self.poly.index, vert_idx, uv_coords.x, uv_coords.y))
            else :
                print("face idx: %i, vert idx: %i, uv: None" % (self.poly.index, vert_idx))

    

    
class ImpostorMaker(bpy.types.Operator) :
    """Impostor maker"""                # blender will use this as a tooltip for menu items and buttons.
    #   Class static variables
    bl_idname = "object.impostor_maker" # unique identifier for buttons and menu items to reference.
    bl_label = "Make impostor"          # display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}   # enable undo for the operator.
    
    MAXIMAGEDIM = 1024                  # Second Life texture size limit (no impostor should be this big)
    
    def __init__(self) :
        """ Constructor """
        pass
    
    def execute(self, context):                     # execute() is called by blender when running the operator.
        """
        Target impostor is last selected object.
        Objects to render are all other selected objects.
        If only one object is selected, it is the impostor, 
        and all other visible objects will be rendered.
        """
        if not context.selected_objects :
            self.report({'ERROR_INVALID_INPUT'}, "Nothing selected.")
            return {'CANCELLED'}
        target = context.selected_objects[0]        # target impostor (last selection is first?)
        if target.type != 'MESH' :
            self.report({'ERROR_INVALID_INPUT'}, "Impostor \"%s\"must be a mesh." % (target.name,))
            return {'CANCELLED'}
        sources = context.selected_objects[:-1]     # source objects
        if not sources :                            # if no source objects
            sources = [obj for obj in context.visible_objects if obj != target] # everything but target
        sources = [obj for obj in sources if obj.type in DRAWABLE]  # only drawables
        if not sources :
            self.report({'ERROR_INVALID_INPUT'}, "No drawable objects to draw on the impostor.")
            return {'CANCELLED'}
        status = self.buildimpostor(context, target, sources)   # do the work
        if status :                                 # if trouble
            self.report({'ERROR'}, status)          # report error, but treat as finished - we may have changed some state
        return {'FINISHED'}                         # this lets blender know the operator finished successfully.
                
    def limiteddissolve(self, context, target) :
        """
        Do a limited dissolve on the target object to combine coplanar triangles into big faces.
        """
        BREAKANGLE = math.radians(0.1)              # must be very flat
        bm = bmesh.new()                            # get working mesh
        bm.from_mesh(target.data)                   # load it from target object
        #   Limited dissove with very shallow break angle
        bmesh.ops.dissolve_limit(bm, angle_limit=BREAKANGLE, verts=bm.verts, edges=bm.edges)
        bm.to_mesh(target.data)                     # put back in original object
        target.data.update()                        # and update the target
        bm.clear()                                  # clean up
        bm.free()
        
    def layoutcomposite(self, layout, faces) :
        """
        Decide where to place faces in composite image
        """
        #   Widest faces first
        width = layout.getsize()[0]
        sortedfaces = sorted(faces, key = lambda f : f.getfacebounds()[0], reverse=True)
        widest = sortedfaces[0].getfacebounds()[0]  # width of widest face
        scalefactor = (width - 2*layout.getmargin()) / widest     # pixels per unit
        for face in sortedfaces :
            width = int(math.floor(face.getfacebounds()[0] * scalefactor))   # width in pixels
            height = int(math.floor(face.getfacebounds()[1] * scalefactor))   # height in pixels
            print("Face size in pixels: (%d,%d)" % (width, height)) # ***TEMP***
            layout.getrect(width, height)           # lay out in layout object            
        layout.dump()                               # ***TEMP***
        return sortedfaces
        
    def outputcomposite(self, target, image) :
        """
        Output composite image to Blender material
        """
        material = None                             # no material yet.
        assert not (target.data.materials is None), "Target has no materials list"
        for matl in target.data.materials :
            if matl.name.startswith(IMPOSTORPREFIX) :   # if starts with "IMP", use it
                material = matl                     # keep this one
                break
        if not material :                           # if no existing "IMP" material
            material = bpy.data.materials.new(name=IMPOSTORPREFIX + target.name)  # create it
            material.use_nodes = True
            target.data.materials.append(material)
        if DEBUGPRINT :
            print("Outputting to material \"%s\"." % (material.name,))
        #   We have a material. Now we have to hook the image to it.
        texture = None
        assert not (material.node_tree.nodes is None), "Target has no node list"
        while "Image Texture" in material.node_tree.nodes : # clean out old image textures
            imgnode = material.node_tree.nodes['Image Texture']
            material.node_tree.nodes.remove(imgnode)
            print("Removed old image texture")      # ***TEMP***
        for node in material.node_tree.nodes :      # search for existing node
            if node.type == 'TEX_IMAGE' and node.name.startswith(IMPOSTORPREFIX) :
                texture = node                      # found existing node
        if not texture :                            # if no existing texture node   
            texture = material.node_tree.nodes.new("ShaderNodeTexImage")    # BSDF shader with a texture image option
            imgnode = material.node_tree.nodes['Image Texture']
            assert imgnode, "No image texture node"
            bsdf = material.node_tree.nodes['Diffuse BSDF']
            assert bsdf, "No BSDF node"                 # We just created it, should exist
            material.node_tree.links.new(imgnode.outputs['Color'], bsdf.inputs['Color'])
            #   ***NO ALPHA YET - MAY NEED ANOTHER NODE***
            ####material.node_tree.links.new(imgnode.outputs['Alpha'], bsdf.inputs['Alpha'])
        if texture.image :                          # if there was a previous image, get rid of it
            print("Old image survived removal")     # ***TEMP***
            oldimage = texture.image
            texture.image = None
            material.node_tree.nodes.remove(oldimage)     
        texture.image = image                       # attach new image to texture
        #   Connect up nodes
        
            
        
    def buildcomposite(self, target, filename, faces, width=512, margin=9) :
        """
        Create composite image
        """
        #   Layout phase
        assert len(faces) > 0, "No faces for impostor target"   
        #   Pass 1 - find out how much space we need      
        layout = ImageLayout(margin, width, None)
        self.layoutcomposite(layout, faces)
        #   Pass 2 - layout in actual size image
        layout = ImageLayout(margin, width, nextpowerof2(layout.getsize()[1], self.MAXIMAGEDIM))  # round up to next power of 2
        sortedfaces = self.layoutcomposite(layout, faces)
        #   Rendering phase
        setnorender(target, True)                                           # hide target impostor object during render
        outimg = self.compositefaces(filename, sortedfaces, layout)
        setnorender(target, False)                                          # hide target impostor object during render
        #   UV setup phase
        self.adduvlayer(target, sortedfaces, layout, margin)
        #   Output
        self.outputcomposite(target, outimg)                                # save image in Blender world
        
    def adduvlayer(self, target, faces, layout, margin) :
        """
        Add UV layer and connect to texture
        """
        rects = layout.getrects()
        size = layout.getsize()
        print("Adding UV info.")
        for face, rect in zip(faces, rects) :       # iterate over arrays in sync
            face.setuvs(target, rect, margin, size)         # set UV values for face
            face.dump()
        
    def compositefaces(self, filename, faces, layout) :
        """
        Composite list of faces into an image
        """
        (width, height) = layout.getsize()                              # final image dimensions
        rects = layout.getrects()
        composite = ImageComposite(filename, width, height)
        print("Rendering and pasting...") # ***TEMP***
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.png', prefix='TMP-', delete=True) as fd :       # create temp file for render
            for i in range(len(faces)) :
                print("Pasting face %d" % (i,)) # ***TEMP***
                face = faces[i]
                rect = rects[i]
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                print("Pasting sorted face %d (%1.2f,%1.2f) -> (%d,%d)" % (i,face.getfacebounds()[0], face.getfacebounds()[1],width, height))
                camera = bpy.data.objects['Camera']                         # CHECK - may not always be current camera
                face.setupcamera(camera, 5.0, 0.05)
                img = face.rendertoimage(fd, width, height)
                composite.paste(img, rect[0], rect[1])                      # paste into image
                deleteimg(img)                                              # get rid of just-rendered image
        image = composite.getimage()
        image.save()                 # save image to file
        return image                                                        # return image object
        
    def markimpostor(self, faces) :
        """
        Debug use only. Puts a red plane on each face of the impostor.
        Used to check transforms.
        """
        redmatl = gettestmatl("Red diffuse", (1, 0, 0))
        greenmatl = gettestmatl("Green diffuse", (0, 1, 0))
        for face in faces:
            #   Put plane on face
            pos = face.worldtransform * face.center                 # dummy start pos
            bpy.ops.mesh.primitive_cube_add(location=pos)
            bpy.context.object.data.materials.append(redmatl)
            bpy.context.object.name = "Marker-face"
            xform = face.getfaceplanetransform()                    # get positioning transform
            xformworld = face.worldtransform * xform                # in world space
            bpy.context.object.matrix_world = xformworld            # apply rotation
            bpy.context.object.scale = mathutils.Vector((face.facebounds[0], face.facebounds[1], 0.01))*0.5                  # apply scale
            #   Put normal on face - long thin cube in normal dir
            pos = face.worldtransform * face.center                 # dummy start pos
            bpy.ops.mesh.primitive_cube_add(location=pos)
            bpy.context.object.data.materials.append(greenmatl)
            bpy.context.object.name = "Marker-normal"
            xform = face.getfaceplanetransform()                    # get positioning transform
            xformworld = face.worldtransform * xform                # in world space
            bpy.context.object.matrix_world = xformworld            # apply rotation
            #   ***NEED TO MOVE ORIGIN TO END***
            bpy.context.object.scale = mathutils.Vector((0.01, 0.01, 4.0))*0.5                  # apply scale


                
    def buildimpostor(self, context, target, sources) :
        status = None                                                       # returned status
        try: 
            if DEBUGPRINT :
                print("Target: " + target.name) 
                print("Sources: " + ",".join([obj.name for obj in sources]))  
            #   ***NEED TO TURN OFF RENDERING FOR ANY RENDERABLE OBJECTS NOT ON THE LIST***
            #   Do a limited dissolve on the target object to combine coplanar triangles into big faces. 
            self.limiteddissolve(context, target)     
            ####faces = []
            ####for poly in target.data.polygons:
                ####faces.append(ImpostorFace(context, target, poly))           # build single poly face objects
            #   Make our object for each face
            faces = [ImpostorFace(context, target, poly) for poly in target.data.polygons]  # single poly face objects
            if DEBUGPRINT :
                print("Faces")
                for f in faces :
                    f.dump()
            #   Lay out texture map
            texmapwidth = 256                                               # ***TEMP***
            self.buildcomposite(target, "/tmp/impostortexture.png", faces, texmapwidth)                        # lay out, first try
            if DEBUGMARKERS : 
                self.markimpostor(faces)                                    # Turn on if transform bugs to show faces.
        except (ValueError, RuntimeError) as message :                      # if trouble
            status = str(message)                                           # message for user            
        return status                                                       # done
            


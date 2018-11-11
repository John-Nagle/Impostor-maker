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
CAMERADISTFACTOR = 0.5                  # camera is half the size of the object back from it, times this

#   Level of detail constants for sizing textures.
#   A 1m object in SL goes to Low level of detail in SL at 10 meters.
LLLOWLODDIST = 10                       # LL viewer goes to low LOD at this * facesize
FSLOWLODDIST = 20                       # Firestorm viewer (using this due to market share)
SCREENSIZE = 2000                       # width of screen in pixels
VIEWANGLE = 1.048                       # default view angle, radians
TEXELSPERPIXEL = 1                      # provide this many texels per pixel

SCREENFRACT = (2*math.atan(0.5/FSLOWLODDIST)) / VIEWANGLE # fraction of screen occupied by object at low LOD point
PIXELSNEEDED = SCREENFRACT*TEXELSPERPIXEL*SCREENSIZE # number of pixels needed at this resolution

TEXMAPWIDTH = 512                       # always this wide, height varies
MARGIN = 3                              # space between images


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
    
def counttriangles(obj) :
    """
    Triangle count of object
    """
    return sum([len(face.vertices)-2 for face in obj.data.polygons])   # tris = verts-2
    
class ImageComposite :
    """
    Image composited from multiple images
    """
    CHANNELS = 4                                    # RGBA
    
    def __init__(self, name, width, height) :
        #   RGBA image initialized to black transparent
        ####bpy.ops.image.new(name=name, width=width, height=height, color=(0.0, 0.0, 0.0, 0.0), alpha=True)  
        ####self.image = bpy.data.images[name]          # must get by name
        self.image = bpy.data.images.new(name=name, width=width, height=height, alpha=True) 
        #   Fill with transparent black
        self.image.pixels[:] = [0.0 for n in range(height*width*self.CHANNELS)] # slow. Is there a better way?
        assert self.image, "ImageComposite image not stored properly" 
        print("ImageComposite size: (%d,%d)" % (width,height))      # ***TEMP***
        ####self.image.filepath = filepath              # will be saved here  
        
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
        if DEBUGPRINT :
            print("Pasting (%d,%d) at (%d,%d) into (%d,%d), input length %d, output length %d." % (inw, inh, x, y, outw, outh, len(img.pixels), len(self.image.pixels))) 
        if x == 0 and inw == outw :                 # easy case, full rows
            start = y*outw*ImageComposite.CHANNELS                 # offset into image
            end = start + inw*inh*ImageComposite.ImageComposite.CHANNELS
            #### print("Paste image to %d:%d length %d" % (start, end, len(img.pixels)))   # ***TEMP***
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
        self.center = self.center / poly.loop_total # average to get center of face         
        print("  Face normal: (%1.4f,%1.4f,%1.4f)" % (self.normal[0],self.normal[1],self.normal[2])) 
        #   Compute bounding box of face.  Use longest edge to orient the bounding box
        #   This will be the area of the image we will take and map onto the face.
        
        faceplanemat = self.getfaceplanetransform()                                 # transform object points onto face plane
        faceplanematinv = faceplanemat.copy()
        faceplanematinv.invert()                                                    # transform face plane back to object points
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
        if DEBUGPRINT: 
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
        camera.data.ortho_scale = self.getcameraorthoscale()[0] * (1.0+margin)          # width of bounds, plus debug margin if desired
        camera.matrix_world = self.getcameratransform(dist)
        camera.data.type = 'ORTHO'
        
    def setuplamp(self, lamp, dist) :
        #   Lamp, for diffuse lighting, points in same direction as camera.
        lamp.matrix_world = self.getcameratransform(dist)
        
    def rendertofile(self, filename, width, height) :
        """
        Render to file
        
        ***NEEDS MORE PARAMS***
        ***NEED TO SAVE CAMERA PARAMS AND RETURN TO NORMAL OR USE A NEW CAMERA***
        ***NEED TO WORK OUT FILENAME/OBJECT NAME UNIQUENESS ISSUES***
        """
        heightalt = int(math.floor((self.facebounds[1] / self.facebounds[0]) * width))     # user sets width, height is just enough for info
        assert abs(height-heightalt) < 2, "Height estimate is wrong"                    # ***TEMP*** not sure about this
        scene = bpy.context.scene
        scene.render.filepath = filename
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.pixel_aspect_x = 1.0
        scene.render.pixel_aspect_y = 1.0
        scene.render.resolution_percentage = 100                                        # mandatory, or we get undersized output
        scene.render.image_settings.color_mode = 'RGBA'                                 # ask for alpha channel
        scene.render.alpha_mode = 'TRANSPARENT'                                         # transparent background, Blender renderer
        scene.cycles.film_transparent = True                                            # transparent background, Cycles renderer
        ####renderout = scene.render.render(write_still=True)   # ***TEMP TEST***
        bpy.ops.render.render(write_still=True) 
        
    def rendertoimage(self, fd, width, height) :
        """
        Render to new image object
        """
        fd.truncate()                                                                   # clear file before rendering into it
        filename = fd.name
        self.rendertofile(filename, width, height)                                      # render into temp file
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
            #   UV points are in 0..1 over entire image space
            uvpt = ((insetrect[0] + fractpt[0] * (insetrect[2]-insetrect[0])) / finalimagesize[0],
                    (insetrect[1] + fractpt[1] * (insetrect[3]-insetrect[1])) / finalimagesize[1])
            if DEBUGPRINT :
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
        #   Sanity checks before starting
        if not context.selected_objects :
            self.report({'ERROR_INVALID_INPUT'}, "Nothing selected.")
            return {'CANCELLED'}
        target = context.selected_objects[0]        # target impostor (last selection is first?)
        if target.type != 'MESH' :
            self.report({'ERROR_INVALID_INPUT'}, "Impostor \"%s\" must be a mesh." % (target.name,))
            return {'CANCELLED'}
        if target.scale[0] < 0 or target.scale[1] < 0 or target.scale[2] < 0 :
            self.report({'ERROR_INVALID_INPUT'}, "Impostor \"%s\" has a negative scale:  (%1.2f, %1.2f, %1.2f)." % 
                (target.name, target.scale[0], target.scale[1], target.scale[2]))
            return {'CANCELLED'}
        sources = context.selected_objects[:-1]     # source objects
        if not sources :                            # if no source objects
            sources = [obj for obj in context.visible_objects if obj != target] # everything but target
        sources = [obj for obj in sources if obj.type in DRAWABLE]  # only drawables
        if not sources :
            self.report({'ERROR_INVALID_INPUT'}, "No drawable objects to draw on the impostor.")
            return {'CANCELLED'}            
        if counttriangles(target) > sum(counttriangles(obj) for obj in sources) : 
            self.report({'ERROR_INVALID_INPUT'}, "The impostor \"%s\" has more triangles than the input objects. Selected wrong object?" % (target.name,))
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
        
    def layoutcomposite(self, layout, sortedfaces, scalefactor) :
        """
        Decide where to place faces in composite image
        """
        #   Widest faces first
        width = layout.getsize()[0]
        ####sortedfaces = sorted(faces, key = lambda f : f.getfacebounds()[0], reverse=True)
        ####widest = sortedfaces[0].getfacebounds()[0]  # width of widest face, meters
        ####scalefactor = (width - 2*layout.getmargin()) / widest     # pixels per unit
        for face in sortedfaces :
            width = int(math.floor(face.getfacebounds()[0] * scalefactor))   # width in pixels
            height = int(math.floor(face.getfacebounds()[1] * scalefactor))   # height in pixels
            print("Face size in pixels: (%d,%d)" % (width, height)) # ***TEMP***
            layout.getrect(width, height)           # lay out in layout object            
        layout.dump()                               # ***TEMP***
        
    def calcscalefactor(self, sortedfaces) :
        """
        Calculate scale factor, pixels per meter, to achieve desired texels per pixel
        """
        widest = sortedfaces[0].getfacebounds()[0]  # width of widest face, meters
        if widest <= 0.0 :
            raise ValueError("Faces have zero size.")
        print("Scale factor: %d/%1.2f = %1.2f" % (PIXELSNEEDED, widest, PIXELSNEEDED/widest)) # ***TEMP***
        return PIXELSNEEDED / widest
        
        
    def outputcomposite(self, target, image) :
        """
        Output composite image to Blender material
        """
        material = None                             # no material yet.
        assert not (target.data.materials is None), "Target has no materials list"
        target.data.materials.clear()               # clear out any old materials
        material = bpy.data.materials.new(name=IMPOSTORPREFIX + target.name)  # create fresh material
        material.use_nodes = True
        target.data.materials.append(material)
        if DEBUGPRINT :
            print("Outputting to material \"%s\"." % (material.name,))
        #   We have a material. Now we have to hook the image to it.
        #   Set up nodes to allow viewing the result. This has no effect on the output file.
        texture = material.node_tree.nodes.new(type='ShaderNodeTexImage')    # BSDF shader with a texture image option
        imgnode = material.node_tree.nodes['Image Texture'] # just created by above
        materialoutput = material.node_tree.nodes['Material Output'] # just created by above
        bsdf = material.node_tree.nodes['Diffuse BSDF']
        mixer = material.node_tree.nodes.new(type='ShaderNodeMixShader')  # for applying alpha
        transpnode = material.node_tree.nodes.new(type='ShaderNodeBsdfTransparent')   # just to generate black transparent
        transpnode.inputs[0].default_value = mathutils.Vector((1.0, 1.0, 1.0, 0.0))   # white transparent 
        material.node_tree.links.new(imgnode.outputs['Color'], bsdf.inputs['Color']) # Image color -> BSDF shader
        material.node_tree.links.new(imgnode.outputs['Alpha'], mixer.inputs['Fac']) # Image alpha channel -> Mixer control
        material.node_tree.links.new(transpnode.outputs['BSDF'], mixer.inputs[1]) # Black transparent -> Mixer input 
        material.node_tree.links.new(bsdf.outputs['BSDF'], mixer.inputs[2]) # Shader output -> Mixer input 
        material.node_tree.links.new(mixer.outputs['Shader'], materialoutput.inputs['Surface']) # 
        material.game_settings.alpha_blend = 'CLIP'   # Needed to get alpha control on screen
        if texture.image :                          # previous image should have been deleted above
            raise RuntimeError("Clean up of image from previous run did not work")
        texture.image = image                       # attach new image to texture
        #   Save file in default folder
        ####texture.image.save()                        # save final textured image (WHERE???)
        
            
        
    def buildcomposite(self, target, faces, width, margin) :
        """
        Create composite image
        """
        #   Layout phase
        assert len(faces) > 0, "No faces for impostor target"   
        #   Pass 1 - find out how much space we need
        sortedfaces = sorted(faces, key = lambda f : f.getfacebounds()[0], reverse=True) # widest faces first
        scalefactor = self.calcscalefactor(sortedfaces)
        layout = ImageLayout(margin, width, None)
        self.layoutcomposite(layout, sortedfaces, scalefactor)
        #   Pass 2 - layout in actual size image
        layout = ImageLayout(margin, width, nextpowerof2(layout.getsize()[1], self.MAXIMAGEDIM))  # round up to next power of 2
        self.layoutcomposite(layout, sortedfaces, scalefactor)
        #   Rendering phase
        setnorender(target, True)                                           # hide target impostor object during render
        imgname = IMPOSTORPREFIX + target.name
        outimg = self.compositefaces(imgname, sortedfaces, layout)          # do the real work
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
        me = target.data                                    # mesh info
        assert me, "Dump - no mesh"
        if not me.uv_layers.active :                        # if no UV layer to modify
            me.uv_textures.new()                            # create UV layer
            ####   Don't know how to do this at the data layer. Have to do it with an operator.
            ####oldactive = bpy.context.scene.objects.active
            ####bpy.context.scene.objects.active = target
            ####bpy.ops.mesh.uv_texture_add()
            ####bpy.context.scene.objects.active = oldactive
            ####me.uv_layers.uv_texture_add()                             # add UV layer
        for face, rect in zip(faces, rects) :               # iterate over arrays in sync
            face.setuvs(target, rect, margin, size)         # set UV values for face
            if DEBUGPRINT :
                face.dump()
            
    def addlamp(self, scene, name="Rendering lamp", lamptype='SUN') :
        """
        Create a lamp object and plug it into the scene
        """
        # Create new lamp datablock
        lamp_data = bpy.data.lamps.new(name=name, type=lamptype)
        # Create new object with our lamp datablock
        lamp = bpy.data.objects.new(name=name, object_data=lamp_data)
        # Link lamp object to the scene so it'll appear in this scene
        scene.objects.link(lamp)
        # And finally select it make active
        scene.objects.active = lamp
        return lamp
        
    def compositefaces(self, name, faces, layout) :
        """
        Composite list of faces into an image
        """
        (width, height) = layout.getsize()                                  # final image dimensions
        rects = layout.getrects()
        composite = ImageComposite(name, width, height)
        scene = bpy.context.scene                                           # active scene
        camera = scene.camera                                               # active camera in this scene
        if not camera :                                                     # no camera available, can't render
            raise RuntimeError("No camera in the scene. Please add one.")                   
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.png', prefix='TMP-', delete=True) as fd :       # create temp file for render
            lamp = self.addlamp(scene)                                      # temporary lamp for rendering
            try :
                for i in range(len(faces)) :
                    ####self.report({'INFO'},"Rendering, %d%% done." % (int((100*i)/len(faces)),))    # useless, they all come out at the end
                    face = faces[i]
                    rect = rects[i]
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    cameradist = max(face.getfacebounds()) * CAMERADISTFACTOR * 0.5 # Camera is half the size of the target face back from it.
                    if DEBUGPRINT :
                        print("Calculated camera distance: %1.2f" % (cameradist,))  
                        print("Pasting sorted face %d (%1.2f,%1.2f) -> (%d,%d)" % (i,face.getfacebounds()[0], face.getfacebounds()[1],width, height))
                    face.setupcamera(camera, cameradist, 0.05)              # point camera
                    face.setuplamp(lamp, cameradist)                        # lamp at camera
                    img = face.rendertoimage(fd, width, height)
                    composite.paste(img, rect[0], rect[1])                  # paste into image
                    deleteimg(img)                                          # get rid of just-rendered image
            #   Cleanup for all faces
            finally: 
                scene.objects.unlink(lamp)                                  # remove from scene
            ####bpy.data.lamps.remove(lamp)                                 # remove from lamps
        image = composite.getimage()                                        # composited image
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
                print("Target: %s (%d triangles)" % (target.name, counttriangles(target))) 
                print("Sources: %s (%d triangles) " % (",".join([obj.name for obj in sources]), sum(counttriangles(obj) for obj in sources)))  
            #   ***NEED TO TURN OFF RENDERING FOR ANY RENDERABLE OBJECTS NOT ON THE LIST***
            #   Do a limited dissolve on the target object to combine coplanar triangles into big faces. 
            self.limiteddissolve(context, target)     
            #   Make our object for each face
            faces = [ImpostorFace(context, target, poly) for poly in target.data.polygons]  # single poly face objects
            if DEBUGPRINT :
                print("Faces")
                for f in faces :
                    f.dump()
            #   Do the real work
            self.buildcomposite(target, faces, TEXMAPWIDTH, MARGIN)         # render and composite
            if DEBUGMARKERS : 
                self.markimpostor(faces)                                    # Turn on if transform bugs to show faces.
        except (ValueError, RuntimeError) as message :                      # if trouble
            status = str(message)                                           # message for user            
        return status                                                       # done
            


# Impostor-maker
Blender impostor maker for creating Second Life content

ALPHA - ready for initial test usage

# Installation
(To be provided. For now, download from Github.)

After installation, there should be a "Make Impostor" item in the Object menu.

# Usage instructions

Start with a high-detail 3D model. Build a low-detail model around it.
Try enclosing it with a cube as a first try. This is enough for squared off
buildings. The low-detail model must be one object, and it must be located
in the same place as the high-detail model. It doesn't have to be in the same
layer.

Make sure the high-detail model and low-detail model are both visible. Turn off
rendering for any irrelevant objects in the scene. Select the low-detail model.
(Or select all objects to be used to make the impostor image, *then* the impostor object.)
Click on Object->Make Impostor. Wait while it builds the impostor image.
It takes a few seconds per face of the low-detail model.

The high-detail model is rendered from the viewpoint of each face of the low-detail model,
and that gets pasted on the appropriate face of the low-detail model. Material generation
and UV setup is automatic. The material and image will be named "IMP-<name of object>"

Unlike Blender baking, you do not have to adjust object scales or centers. That's all automatic.
Texture resolution is set to be appropriate for "Low" models in Second Life" 

# Hints

If the output impostor has transparent sections around the outside, the enclosing low-detail model
is oversize. Shrink it into the original model. 

# Limitations and bugs

Currently, the output texture image is always 256 pixels wide, and as high as it has to be to fit all the faces.
Use any image editor to shrink it, if desired.

Blender's display of the impostor in "Rendered" setting does not have proper alpha transparency. "Textured" 
is OK.  This does not affect the generated impostor; it's just a Blender problem.

There is a problem with very narrow faces, under 4 pixels wide, causing the add-on to fail an
assertion check.

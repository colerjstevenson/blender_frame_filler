 ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Stop Motion Fill",
    "author": "Cole Stevenson",
    "version": (1, 0, 0),
    "blender": (4, 1, 0),
    "location": "Output > Stop Motion Fill",
    "description": "at the end of a render on 2s or 3s, will duplicate created images to fill in missing frames",
    "warning": "",
    "category": "Render"}

import bpy
import shutil
import re
import aud, platform, subprocess, os, threading, smtplib, time, traceback, requests, json, urllib, random
from bpy.props import *
from bpy.app.handlers import persistent
from bpy.types import Operator, Panel, PropertyGroup, AddonPreferences

C = bpy.context
D = bpy.data

OS = 'WIN' if platform.system().startswith('Win') else 'LIN' #Determine platform prefix
d = '/' if OS == 'WIN' else '-'                              #platform dependent flag
sound_path = os.path.normpath(os.path.dirname(__file__)+'/sounds/')
poweroff_list = [("NONE", "Do Not Shut Down", ""),
                ("POWER_OFF", "Power Off", ""),
                ("RESTART", "Restart", ""),
                ("SLEEP", "Sleep", "")]


agents = ['Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0',
'Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:42.0) Gecko/20100101 Firefox/42.0',
'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36',
'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36 OPR/38.0.2220.41'
]

@persistent
def fillFramesHook(scene): #Function hooked at render completion event
    global timer
    props = scene.frame_filler
    print("WWWWWWOOOOOOOOO")
    if bpy.context.window_manager.use_frame_filler:
        print("WEEEEEEEE")
        if props.use_filler: frameFiller()
        

def handlerBind(self, context): #callback function bind to use_frame_filler checkbox
	H = bpy.app.handlers.render_complete
	if fillFramesHook not in H: H.append(fillFramesHook) #it binds fillFramesHook to handler




bpy.types.WindowManager.use_frame_filler = BoolProperty(name='Enable', description='Enable Frame Filler', default=False, update=handlerBind)

class fillFramesPROPS(bpy.types.PropertyGroup): #All the properties utilized by addon
    
    # remaining_time : IntProperty()
    # alarm_volume : IntProperty(name='Volume', description='Alarm volume level', default=100, min=1, max=100, step=1, subtype='PERCENTAGE')
    # use_send_email : BoolProperty(name='Send Email', description='Sends an email with notification on render completion', default=False)
    # use_send_telegram : BoolProperty(name='Send Telegram Message', description='Sends a message via Telegram on render completion', default=False)
    # use_send_viber : BoolProperty(name='Send Viber Message', description='Sends a message via Viber on render completion', default=False)
    # use_attach_render : BoolProperty(name='Attach rendered image', description='Attaches rendered image to the notification', default=False)
    use_filler : BoolProperty(name='fillFrames', description='fills frames on for renders not on 1s', default=False)
    use_overwrite : BoolProperty(name='overwrite?', description='overwrite frames if they already exist', default=False)
    

bpy.utils.register_class(fillFramesPROPS)
bpy.types.Scene.frame_filler = PointerProperty(type=fillFramesPROPS)
    

class fillFramesPANEL(bpy.types.Panel):
    bl_description = 'Fills in missing frames for renders not on 1s'
    bl_idname = 'RENDER_PT_frameFill'
    bl_label = 'Frame Filler'
    bl_region_type = 'WINDOW'
    bl_space_type = 'PROPERTIES'
    bl_context = 'output'
    
    @classmethod
    def poll(cls, context):
        return True
    
    def draw(self, context):
        props = context.scene.frame_filler
        prefs = bpy.context.preferences.addons[__name__].preferences
        l = self.layout
        m = l.column()
        m.active = bpy.context.window_manager.use_frame_filler #Check whether addon function is enabled
        c = m.column(align=True)
        c.prop(props, 'use_filler')
        c.prop(props, 'use_overwrite')
        if props.use_filler:
            if bpy.context.scene.render.filepath == '':
                c.label(text='no output destination set', icon='ERROR')
            elif bpy.context.scene.frame_step == 1:
                c.label(text='render is current on 1s, nothing to fill', icon='ERROR')

        c = m.column()
        c.scale_y = 3
        
        
    def draw_header(self, context):
        l = self.layout
        l.prop(context.window_manager, 'use_frame_filler', text='')
        
    
class fillFramesPREF(AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        l = self.layout
        r = l.row(align=True)
        

def frameFiller():
    path = bpy.context.scene.render.filepath
    steps = bpy.context.scene.frame_step
    start = bpy.context.scene.frame_start

    prefs = bpy.context.preferences.addons[__name__].preferences

    if(path == '' or steps == 1):
        print("not valid for run")
        return

    files = getFiles(path)


    for file in files:
        
        for i in range(1, steps):
            groups = re.search(r'(.*)(\d{4,})(\..*)', file)

            frame = int(groups.group(2)) + i

            if((frame - start) % steps != 0):
                dst = groups.group(1) + str(frame).rjust(4, '0') + groups.group(3)
                if not os.path.exists(dst) or bpy.context.scene.frame_filler.use_overwrite:
                    print("creating " + dst)
                    shutil.copy2(file, dst)
    



def getFiles(start_path):

    out = []
    for root, dirs, files in os.walk(start_path):
        for file in files:
            out.append(os.path.join(root, file))
            

    return out




toRegister = (fillFramesPANEL, fillFramesPREF)
    
def register():
    for cls in toRegister:
        bpy.utils.register_class(cls)
    handlerBind(None, C)

def unregister():
    H = bpy.app.handlers.render_complete
    if fillFramesHook in H:
        bpy.app.handlers.render_complete.remove(fillFramesHook)
    for cls in toRegister:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    print("WEEEEEEEEE")
    register()

#-******************************************************************************
#
# Copyright (c) 2013-2014,
#  Sony Pictures Imageworks Inc. and
#  Industrial Light & Magic, a division of Lucasfilm Entertainment Company Ltd.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# *       Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# *       Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
# *       Neither the name of Sony Pictures Imageworks, nor
# Industrial Light & Magic, nor the names of their contributors may be used
# to endorse or promote products derived from this software without specific
# prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#-******************************************************************************

import os
import sys
import math
from functools import wraps

try:
    from PyQt5 import QtWidgets
    from PyQt5 import QtGui
    from PyQt5 import QtCore
    from PyQt5 import QtOpenGL
    from PyQt5.QtCore import pyqtSignal as Signal
except:
    from PySide2 import QtWidgets
    from PySide2 import QtGui
    from PySide2 import QtCore
    from PySide2 import QtOpenGL
    from PySide2.QtCore import Signal as Signal

import numpy
import OpenGL
OpenGL.ERROR_CHECKING = True
import OpenGL.GL
import OpenGL.GLU

# flag opengl errors
import OpenGL.arrays.numpymodule
OpenGL.arrays.numpymodule.NumpyHandler.ERROR_ON_COPY = True

import imath
import alembic

import abcview
import abcview.io
import abcview.gl

# GL drawing mode map
GL_MODE_MAP = {
    abcview.io.Mode.OFF: 0,
    abcview.io.Mode.BOUNDS: 1,
    abcview.io.Mode.FILL: OpenGL.GL.GL_FILL,
    abcview.io.Mode.LINE: OpenGL.GL.GL_LINE,
    abcview.io.Mode.POINT: OpenGL.GL.GL_POINT
}

def update_camera(func):
    """
    GL camera update decorator
    """
    @wraps(func)
    def with_wrapped_func(*args, **kwargs):
        func(*args, **kwargs)
        wid = args[0]
        wid.camera.apply()
        wid.updateGL()
        wid.SIGNAL_CAMERA_UPDATED.emit(wid.camera)
        wid.state.SIGNAL_STATE_CHANGE.emit()
    return with_wrapped_func

def set_diffuse_light():
    """
    Sets up the GL calls for the light that illuminates objects.
    """
    ambient = (0.2, 0.2, 0.2, 1.0)
    diffuse = (0.9, 0.9, 0.9, 1.0)
    position = (90.0, 90.0, 150.0, 0.0)

    front_mat_shininess = (10.0)
    front_mat_specular = (0.3, 0.3, 0.3, 1.0)
    front_mat_diffuse = (1.0, 1.0, 1.0, 1.0)
    back_mat_shininess = (10.0)
    back_mat_specular = (0.2, 0.2, 0.2, 1.0)
    back_mat_diffuse = (0.5, 0.5, 0.5, 1.0)

    lmodel_ambient = (0.2, 0.2, 0.2, 1.0)

    OpenGL.GL.glEnable(OpenGL.GL.GL_LIGHTING)
    OpenGL.GL.glEnable(OpenGL.GL.GL_LIGHT0)
    OpenGL.GL.glShadeModel(OpenGL.GL.GL_SMOOTH)

    OpenGL.GL.glEnable(OpenGL.GL.GL_DEPTH_TEST)
    
    #OpenGL.GL.glLightfv(OpenGL.GL.GL_LIGHT0, GL_AMBIENT, ambient)
    OpenGL.GL.glLightfv(OpenGL.GL.GL_LIGHT0, OpenGL.GL.GL_DIFFUSE, diffuse)

    OpenGL.GL.glMaterialfv(OpenGL.GL.GL_FRONT, OpenGL.GL.GL_SHININESS, front_mat_shininess)
    OpenGL.GL.glMaterialfv(OpenGL.GL.GL_FRONT, OpenGL.GL.GL_SPECULAR, front_mat_specular)
    OpenGL.GL.glMaterialfv(OpenGL.GL.GL_FRONT, OpenGL.GL.GL_DIFFUSE, front_mat_diffuse)
    OpenGL.GL.glMaterialfv(OpenGL.GL.GL_BACK, OpenGL.GL.GL_SHININESS, back_mat_shininess)
    OpenGL.GL.glMaterialfv(OpenGL.GL.GL_BACK, OpenGL.GL.GL_SPECULAR, back_mat_specular)
    OpenGL.GL.glMaterialfv(OpenGL.GL.GL_BACK, OpenGL.GL.GL_DIFFUSE, back_mat_diffuse)

    OpenGL.GL.glLightModelfv(OpenGL.GL.GL_LIGHT_MODEL_AMBIENT, lmodel_ambient)
    
def create_viewer_app(filepath=None):
    """
    Creates a standalone viewer app. ::

        >>> from abcview.widget.viewer_widget import create_viewer_app
        >>> create_viewer_app('file.abc')

    """
    import abcview.app
    app = abcview.app.App(sys.argv)

    # create the viewer widget
    viewer = GLWidget()
    viewer_group = QtGui.QGroupBox()
    viewer_group.setLayout(QtGui.QVBoxLayout())
    viewer_group.layout().setSpacing(0)
    viewer_group.layout().setMargin(0)
    viewer_group.layout().addWidget(viewer)
    viewer_group.setWindowTitle('GLWidget')

    # set default size
    viewer_group.setMinimumSize(QtCore.QSize(100, 100))
    viewer_group.resize(500, 300)

    # display the viewer app
    viewer_group.show()
    viewer_group.raise_()

    # override key press event handler
    viewer_group.keyPressEvent = viewer.keyPressEvent

    def load():
        if filepath and os.path.exists(filepath):
            viewer.add_file(filepath)
    
    app.signal_starting_up.connect(load)
    return app.exec_()

def message(info):
    dialog = QtGui.QMessageBox()
    dialog.setStyleSheet(abcview.style.DIALOG)
    dialog.setText(info)
    dialog.exec_()

class GLSplitter(QtGui.QSplitter):
    def __init__(self, orientation, wipe=False):
        super(GLSplitter, self).__init__(orientation)
        self.wipe = wipe

class GLState(QtCore.QObject):
    """
    Global GL viewer state manager. Manages list of Cameras and Scenes, 
    which can be shared between viewers.
    """
    SECOND = 1000.0

    SIGNAL_STATE_CHANGE = Signal()
    SIGNAL_PLAY_FWD = Signal()
    SIGNAL_PLAY_STOP = Signal()
    SIGNAL_CURRENT_TIME = Signal(float)
    SIGNAL_CURRENT_FRAME = Signal(int)

    def __init__(self, fps=24.0):
        """
        :param fps: play scene at frames per second (fps)
        """
        super(GLState, self).__init__()
        self.timer = QtCore.QTimer(self)
        self.active_viewer = None
        self.frames_per_second = fps
        self.clear()
        
        # for calculating frames per second during playback
        self.fps = 0.0
        self.__fps_timer = QtCore.QTimer(self)
        self.__fps_timer.setInterval(self.SECOND)
        self.__fps_timer.timeout.connect(self._fps_timer_cb)

    def uid(self):
        return id(self)

    def __repr__(self):
        return '<GLState {0}>'.format(self.uid())

    def clear(self):
        """
        Clears the current state.
        """
        abcview.log.debug('[{0}.clear]'.format(self))

        # stores all the GLScene objects
        self.__scenes = []

        # stores all the GLCamera objects
        self.__cameras = {}

        # min/max/current time information
        self.__min = None
        self.__max = None
        self.__time = 0

        # current frame
        self.__frame = 0

        # "is playing" bool toggle
        self.__playing = False

        # frames per second tracker
        self.__fps_counter = 0

        # update all the viewers
        self.SIGNAL_STATE_CHANGE.emit()

    def _get_cameras(self):
        return self.__cameras.values()

    def _set_cameras(self):
        abcview.log.debug('use add_camera()')

    cameras = property(_get_cameras, _set_cameras, doc='cameras')

    def _get_scenes(self):
        return self.__scenes

    def _set_scenes(self):
        abcview.log.debug('use add_scene() to add scenes')

    scenes = property(_get_scenes, _set_scenes, doc='scenes')

    def add_scene(self, scene):
        """
        Adds a scene to the viewer session. 

        :param scene: GLScene object
        """
        abcview.log.debug('[{0}.add_scene] {1}'.format(self, scene))
        if type(scene) == abcview.gl.GLScene:
            if scene not in self.__scenes:
                scene.state = self
                self.__scenes.append(scene)
            else:
                scene.visible = True
            scene.set_time(self.current_time)
        self.SIGNAL_STATE_CHANGE.emit()

    def add_file(self, filepath):
        """
        Generic add file method.

        :param filepath: path to file to add
        """
        abcview.log.debug('[{0}.add_file] {1}'.format(self, filepath))
        self.add_scene(abcview.gl.GLScene(filepath))

    def remove_scene(self, scene):
        """
        Removes a given GLScene object from the master scene.

        :param scene: GLScene to remove.
        """
        abcview.log.debug('[{0}.remove_scene] {1}'.format(self, scene))
        scene.visible = False
        if scene in self.__scenes:
            self.__scenes.remove(scene)
        self.SIGNAL_STATE_CHANGE.emit()

    def add_camera(self, camera):
        """
        Adds a new GLCamera to the state.

        :param camera: GLCamera object
        """
        abcview.log.debug('[{0}.add_camera] {1}'.format(self, camera))
        if camera and camera.name not in self.__cameras.keys():
            self.__cameras[camera.name] = camera
            return True
        return False

    def remove_camera(self, camera):
        """
        Removes a GLCamera object from the state.

        :param camera: GLCamera object
        """
        if type(camera) in [str, unicode]:
            del self.__cameras[camera]
        else:
            del self.__cameras[camera.name]
        self.SIGNAL_STATE_CHANGE.emit()

    def get_camera(self, name):
        """
        Returns a named camera for a given viewer.

        :param camera: GLCamera object
        """
        return self.__cameras.get(name)

    def _get_time(self):
        return self.__time

    def _set_time(self, new_time):
        if new_time is None:
            abcview.log.warn('time is None')
            return
        self.__time = new_time
        self.__frame = new_time * self.frames_per_second
        for scene in self.scenes:
            if scene.visible:
                scene.set_time(new_time)
        self.SIGNAL_CURRENT_TIME.emit(new_time)
        self.SIGNAL_CURRENT_FRAME.emit(int(round(new_time * self.frames_per_second)))

        # update other viewers
        self.SIGNAL_STATE_CHANGE.emit()
        
    current_time = property(_get_time, _set_time, doc='set/get current time')

    def _get_frame(self):
        return self.__frame

    def _set_frame(self, frame):
        if frame > self.frame_range()[1]:
            frame = self.frame_range()[0]
        elif frame < self.frame_range()[0]:
            frame = self.frame_range()[1]
        self.current_time = frame / float(self.frames_per_second)

    current_frame = property(_get_frame, _set_frame, doc='set/get current frame')
   
    def _get_min_time(self):
        return self.__min

    def _set_min_time(self, value):
        self.__min = value
        abcview.log.debug('[{0}._set_min_time] {1}'.format(self, self.__min))

    min_time = property(_get_min_time, _set_min_time, doc='set/get minimum time')

    def _get_max_time(self):
        return self.__max

    def _set_max_time(self, value):
        self.__max = value
        abcview.log.debug('[{0}._set_min_time] {1}'.format(self, self.__max))

    max_time = property(_get_max_time, _set_max_time, doc='set/get maximum time')

    def time_range(self):
        """
        Returns min/max time range in seconds as a tuple.
        """
        if self.__min == None or self.__max == None:
            if self.scenes:
                for scene in self.scenes:
                    if self.__min is None or scene.min_time() < min:
                        self.__min = scene.min_time()
                    if self.__max is None or scene.max_time() > max:
                        self.__max = scene.max_time()
            else:
                self.__min, self.__max = 0, 0
        return (self.__min, self.__max)

    def _get_min_frame(self):
        return self.frame_range()[0]

    def _set_min_frame(self, value):
        if value is None:
            self.min_time = None
        elif self.frames_per_second > 0:
            self.min_time = value / float(self.frames_per_second)

    min_frame = property(_get_min_frame, _set_min_frame, doc='set/get minimum frame')

    def _get_max_frame(self):
        return self.frame_range()[1]

    def _set_max_frame(self, value):
        if value is None:
            self.max_time = None
        elif self.frames_per_second > 0:
            self.max_time = value / float(self.frames_per_second)

    max_frame = property(_get_max_frame, _set_max_frame, doc='set/get maximum frame')

    def frame_range(self):
        """
        Returns min/max frame range as a tuple.
        """
        (min, max) = self.time_range()
        return (min * self.frames_per_second, max * self.frames_per_second)

    def frame_count(self):
        """
        Returns total frame count.
        """
        return len(range(*self.frame_range())) + 1
    
    def is_playing(self):
        """
        Returns True if the playback timer is running.
        """
        return self.__playing

    def play(self):
        """
        Plays loaded scenes by activating timer and setting callback
        """
        self.timer.setInterval(self.SECOND / (float(self.frames_per_second)))
        self.timer.timeout.connect(self._play_fwd_cb)
        self.timer.start()
        self.__fps_timer.start()
        self.SIGNAL_PLAY_FWD.emit()

    def _play_fwd_cb(self):
        """
        Play callback, sets current time for all scenes
        """
        self.__playing = True
        min_time, max_time = self.time_range()
        self.current_time += 1.0 / float(self.frames_per_second)
        if self.current_time > max_time:
            self.current_time = min_time
        self.__fps_counter += 1

    def stop(self):
        """
        Stops scene playback
        """
        self.__playing = False
        self.timer.timeout.disconnect(self._play_fwd_cb)
        self.timer.stop()
        self.__fps_timer.stop()
        self.__fps_counter = 0
        self.fps = 0.0
        self.SIGNAL_PLAY_STOP.emit()

    def _fps_timer_cb(self):
        """
        Frames per second timer callback
        """
        self.fps = (self.__fps_counter / float(self.frames_per_second)) * self.frames_per_second
        self.__fps_counter = 0

class GLWidget(QtOpenGL.QGLWidget):
    """
    AbcView OpenGL Widget.

    Basic usage ::

        >>> create_viewer_app('file.abc')

    or inside a larger Qt application ::

        >>> viewer = GLWidget()
        >>> viewer.add_file('file.abc')
    """

    FONT_NAME = 'Arial'

    #TODO: check if all signals used

    # scene signals
    SIGNAL_SCENE_OPENED = Signal(abcview.gl.GLScene)
    SIGNAL_SCENE_REMOVED = Signal(abcview.gl.GLScene)
    SIGNAL_SCENE_ERROR = Signal(str)
    SIGNAL_SCENE_DRAWN = Signal()

    # camera signals (pass 'object' to support both camera classes)
    SIGNAL_SET_CAMERA = Signal(object)
    SIGNAL_NEW_CAMERA = Signal(object)
    SIGNAL_CAMERA_UPDATED = Signal(object)

    # selection signals
    SIGNAL_SCENE_SELECTED = Signal(abcview.gl.GLScene)
    SIGNAL_OBJECT_SELECTED = Signal(str)
    SIGNAL_CLEAR_SELECTION = Signal()

    # error signals
    SIGNAL_UNDRAWABLE_SCENE = Signal(abcview.gl.GLScene, float)

    def __init__(self, parent=None, state=None):
        """
        :param parent: parent Qt object
        :param state: GLState object (for shared states)
        """
        self.camera = None
        format = QtOpenGL.QGLFormat()
        format.setDirectRendering(True)
        format.setSampleBuffers(True)
        self.state = state or GLState()
        self.state.SIGNAL_STATE_CHANGE.connect(self.handle_state_change)
        super(GLWidget, self).__init__(format, parent)
        self.setAutoBufferSwap(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
      
        # embedded in larger app?
        self._main = parent

        # various matrices and vectors
        self.__bounds_default = imath.Box3d((-5,-5,-5), (5,5,5))
        self.__bounds = None
        self.__radius = 5.0
        self.__last_pok = False
        self.__last_p2d = QtCore.QPoint()
        self.__last_p3d = [1.0, 0.0, 0.0]
        self.__rotating = False
        self.__mode = OpenGL.GL.GL_SELECT

        # viewers must have at least one camera
        self.setup_default_camera()

    def uid(self):
        return id(self)

    def __repr__(self):
        return '<GLWidget {0}>'.format(self.uid())

    def setup_default_camera(self):
        """
        Creates the default interactive camera for this view (and others if the
        state is shared between viewers).
        """
        self.add_camera(abcview.gl.GLCamera(self, name='interactive'))
        self.set_camera('interactive')

    def clear(self):
        """
        Resets this GL viewer widget, clears the shared state
        and creates a new default interactive camera.
        """
        self.state.clear()
        self.setup_default_camera()

    def add_file(self, filepath):
        """
        Loads a given filepath into the GL viewer.

        :param filepath: path to Alembic file.
        """
        self.add_scene(abcview.gl.GLScene(filepath))

    def add_scene(self, scene):
        """
        Adds a scene to the viewer session. 

        :param scene: GLScene object
        """
        abcview.log.debug('[{0}.add_scene] {1}'.format(self, scene))
        self.state.add_scene(scene)
        self.SIGNAL_SCENE_OPENED.emit(scene)
        self.updateGL()

    def remove_scene(self, scene):
        """
        Removes a given GLScene object from the master scene.

        :param scene: GLScene to remove.
        """
        abcview.log.debug('[{0}.remove_scene] {1}'.format(self, scene))
        self.state.remove_scene(scene)
        self.SIGNAL_SCENE_REMOVED.emit(scene)
        self.updateGL()

    def add_camera(self, camera):
        """
        :param camera: GLCamera object
        """
        abcview.log.debug('[{0}.add_camera] {1}'.format(self, camera))
        if self.state.add_camera(camera):
            camera.add_view(self)
            self.SIGNAL_NEW_CAMERA.emit(camera)

    def remove_camera(self, camera):
        """
        :param camera: GLCamera object to remove
        """
        abcview.log.debug('[{0}.remove_camera] {1}'.format(self, camera))
        self.state.remove_camera(camera)
        self.SIGNAL_STATE_CHANGE.emit()

    @update_camera
    def set_camera(self, camera):
        """
        Sets the scene camera from a given camera name string

        :param camera: Name of camera or GLCamera object
        """
        abcview.log.debug('[{0}.set_camera] {1}'.format(self, camera))
        if type(camera) in [str, unicode]:
            if '/' in camera:
                camera = os.path.split('/')[-1]
            elif camera not in [cam.name for cam in self.state.cameras]:
                abcview.log.warn('camera not found: {0}'.format(camera))
                return
            self.camera = self.state.get_camera(camera)
        else:
            self.camera = camera
        self.camera.add_view(self)
        self.resizeGL(self.width(), self.height())
        self.SIGNAL_SET_CAMERA.emit(self.camera)

    def aspect_ratio(self):
        """
        Returns current aspect ration of the viewer.
        """
        return self.width() / float(self.height())
    
    def _get_bounds(self):
        #TODO: ugly code needs refactor
        if self.state.scenes:
            bounds = None
            for scene in self.state.scenes:
                if not scene.loaded or not scene.drawable():
                    continue
                if bounds is None or \
                        scene.bounds(self.state.current_time).max() > bounds.max():
                    bounds = scene.bounds(self.state.current_time)
                    min = bounds.min()
                    max = bounds.max()
                    if scene.properties.get('translate'):
                        max = max * imath.V3d(*scene.translate)
                        min = min * imath.V3d(*scene.translate)
                    if scene.properties.get('scale'):
                        max = max * imath.V3d(*scene.scale)
                        min = min * imath.V3d(*scene.scale)
                    bounds = imath.Box3d(min, max)
            
            if bounds is None:
                return self.__bounds_default
            self.__bounds = bounds
            return self.__bounds
        else:
            return self.__bounds_default

    def _set_bounds(self, bounds):
        self.__bounds = bounds

    bounds = property(_get_bounds, _set_bounds, doc='scene bounding box')

    @update_camera
    def frame(self, bounds=None):
        """
        Frames the viewer's active camera on the bounds of the currently
        loaded and visible scenes.

        :param bounds: imath.Box3d bounds object.
        """
        abcview.log.debug('[{0}.frame] {1}'.format(self, bounds))
        if self.camera.type() == abcview.gl.GLICamera.type():
            message('''Can\'t frame when viewing through ICameras.\nSelect or create a new camera.''')
            return
        if bounds is None:
            bounds = self.bounds
        if self.camera:
            self.camera.frame(bounds)

    def split(self, orientation=QtCore.Qt.Vertical, wipe=False):
        """
        Splist the viewer into two separate widgets according
        to the orientation param. ::

            QGroupBox
                `- QSplitter
                        |- QGroupBox
                        |       `- GLWidget
                        `- QGroupBox
                                `- GLWidget

        """
        if not self.parent():
            return

        item = self.parent().layout().itemAt(0)

        # create the splitter
        splitter = GLSplitter(orientation, wipe)
        self.parent().layout().addWidget(splitter)

        # left/top viewer group
        group1 = QtGui.QGroupBox()
        group1.setLayout(QtGui.QVBoxLayout())
        group1.layout().setSpacing(0)
        group1.layout().setMargin(0)
        group1.layout().addWidget(item.widget())

        # right/bottom viewer group
        group2 = QtGui.QGroupBox()
        group2.setLayout(QtGui.QVBoxLayout())
        group2.layout().setSpacing(0)
        group2.layout().setMargin(0)

        new_viewer = GLWidget(self._main, state=self.state)

        self.camera.add_view(new_viewer)
        group2.layout().addWidget(new_viewer)

        # link the two groups for unsplitting later
        group1.other = group2
        group1.viewer = self
        group2.other = group1
        group2.viewer = new_viewer

        # add the two groups to the splitter
        splitter.addWidget(group1)
        splitter.addWidget(group2)

    def split_vert(self):
        """
        Splits the viewer vertically.
        """
        self.split(QtCore.Qt.Horizontal)

    def split_horz(self):
        """
        Splits the viewer horizontally.
        """
        self.split(QtCore.Qt.Vertical)

    #TODO: support viewer pop-outs, better garbage collection
    def unsplit(self):
        """
        Unsplits and deletes current viewer
        """
        if not self.parent():
            return

        # get the parent splitter object
        splitter = self.parent()
        while splitter and type(splitter) != GLSplitter:
            splitter = splitter.parent()

        # we've reached the top splitter, do nothing
        if splitter is None:
            return

        splitter.parent().layout().removeWidget(splitter)
        splitter.parent().layout().addWidget(self.parent().other)

        # delete this view from all cameras
        for camera in self.state.cameras:
            camera.remove_view(self)

        # reassign the viewer attribute on main
        if self._main:
            self._main.viewer = self.parent().other.viewer

        # cleanup
        del splitter
        del self

    def _paint_normals(self):
        """
        Paints normals for polys and subds.
        """
        OpenGL.GL.glColor3f(1, 1, 1)
        def _draw(obj):
            md = obj.getMetaData()
            if alembic.AbcGeom.IPolyMesh.matches(md) or alembic.AbcGeom.ISubD.matches(md):
                meshObj = alembic.AbcGeom.IPolyMesh(obj.getParent(), obj.getName())
                mesh = meshObj.getSchema()
                
                ts = mesh.getTimeSampling()
                index = ts.getNearIndex(self.state.current_time, mesh.getNumSamples())
                facesProp = mesh.getFaceIndicesProperty()
                pointsProp = mesh.getPositionsProperty()
                normalsProp = mesh.getNormalsParam().getValueProperty()

                for p in [facesProp, pointsProp, normalsProp]:
                    if not p.valid():
                        return

                faces = facesProp.getValue(index)
                points = pointsProp.getValue(index)
                normals = normalsProp.getValue(index)
                xf = abcview.gl.get_final_matrix(meshObj, self.state.current_time)

                for i, fi in enumerate(faces):
                    p = points[fi] * xf
                    n = normals[i]
                    v = p + n
                    OpenGL.GL.glBegin(OpenGL.GL.GL_LINES)
                    OpenGL.GL.glColor3f(0, 1, 0)
                    OpenGL.GL.glVertex3f(p[0], p[1], p[2])
                    OpenGL.GL.glVertex3f(v[0], v[1], v[2])
                    OpenGL.GL.glEnd()
        
            for child in obj.children:
                try:
                    _draw(child)
                except Exception, e:
                    abcview.log.warn('unhandled exception: {0}'.format(e))

        for scene in self.state.scenes:
            _draw(scene.top())

    def _paint_grid(self):
        """
        Paints the grid.
        """
        OpenGL.GL.glDisable(OpenGL.GL.GL_LIGHTING)
        OpenGL.GL.glColor3f(0.5, 0.5, 0.5)
        for x in range(-10, 11):
            if x == 0:
                continue
            OpenGL.GL.glBegin(OpenGL.GL.GL_LINES)
            OpenGL.GL.glVertex3f(x, 0, -10)
            OpenGL.GL.glVertex3f(x, 0, 10)
            OpenGL.GL.glVertex3f(-10, 0, x)
            OpenGL.GL.glVertex3f(10, 0, x)
            OpenGL.GL.glEnd()
        
        OpenGL.GL.glBegin(OpenGL.GL.GL_LINES)
        OpenGL.GL.glVertex3f(0, 0, -10)
        OpenGL.GL.glVertex3f(0, 0, 10)
        OpenGL.GL.glVertex3f(-10, 0, 0)
        OpenGL.GL.glVertex3f(10, 0, 0)
        OpenGL.GL.glEnd()

    def _paint_hud(self):
        """
        Paints the heads-up-display information.
        """
        OpenGL.GL.glColor3f(1, 1, 1)
        def _format(array):
            return ', '.join(['{0:.02f}'.format(f) for f in array])

        OpenGL.GL.glViewport(0, 0, self.width(), self.height())
        
        # draw the camera name
        OpenGL.GL.glColor3f(0.5, 1, 0.5)
        if self.camera.fixed:
            self.renderText(15, 20, '{0} [{1:.02f}]'.format(self.camera.name, self.camera.aspect_ratio))
        else:
            self.renderText(15, 20, str(self.camera.name))

        # draw the camera info
        OpenGL.GL.glColor3f(0.6, 0.6, 0.6)
        font = QtGui.QFont(GLWidget.FONT_NAME, 8)
        self.renderText(15, 35, 'T [{0}]'.format(_format(self.camera.translation), font))
        self.renderText(15, 50, 'R [{0}]'.format(_format(self.camera.rotation), font))
        self.renderText(15, 66, 'S [{0}]'.format(_format(self.camera.scale), font))

        # draw the FPS info
        OpenGL.GL.glColor3f(0.7, 0.7, 0.7)
        font = QtGui.QFont(GLWidget.FONT_NAME, 9)
        self.renderText(self.width()-100,
                        self.height()-10,
                        '{0:.1f} / {1:.1f} FPS'.format(self.state.fps,
                                                       self.state.frames_per_second),
                        font)

        OpenGL.GL.glColor3f(1, 1, 1)

    def _paint_fixed(self):
        """
        Changes the GL viewport according to the camera's aspect ratio.
        """
        # get basic size values for this viewer
        camera_width = self.camera.get_size(self)[0]
        camera_height = self.camera.get_size(self)[1]
        camera_aspect_ratio = camera_width / float(camera_height)
        
        # if fixed, lock the aspect ratio
        if self.camera.fixed:
            camera_aspect_ratio = self.camera.aspect_ratio
            if self.aspect_ratio() > self.camera.aspect_ratio:
                w = int(self.width() / (self.aspect_ratio() / camera_aspect_ratio))
                h = camera_height
            else:
                w = camera_width
                h = int(self.height() * (self.aspect_ratio() / camera_aspect_ratio))
            x = int(abs(w-self.width()) / 2.0)
            y = int(abs(h-self.height()) / 2.0)

        # camera size matches viewer
        else:
            x = y = 0
            w = self.width()
            h = self.height()
        
        # do some GL stuff
        OpenGL.GL.glViewport(x, y, w, h)
        self.makeCurrent()
        OpenGL.GL.glMatrixMode(OpenGL.GL.GL_PROJECTION)
        OpenGL.GL.glLoadIdentity()
        OpenGL.GLU.gluPerspective(self.camera.fovy, camera_aspect_ratio,
                       self.camera.near, self.camera.far)
        OpenGL.GL.glMatrixMode(OpenGL.GL.GL_MODELVIEW)

    def set_camera_clipping_planes(self, near=None, far=None):
        self.camera.set_clipping_planes(self.camera.near, self.camera.far)

    def map_to_sphere(self, v2d):
        v3d = [0.0, 0.0, 0.0]
        if ((v2d.x() >= 0) and (v2d.x() <= self.width()) and
            (v2d.y() >= 0) and (v2d.y() <= self.height())):
            x = float(v2d.x() - 0.5 * self.width())  / self.width()
            y = float(0.5 * self.height() - v2d.y()) / self.height()
            v3d[0] = x
            v3d[1] = y
            z2 = 2.0 * 0.5 * 0.5 - x * x - y * y
            v3d[2] = math.sqrt(max( z2, 0.0 ))
            n = numpy.linalg.norm(v3d)
            v3d = numpy.array(v3d) / float(n)
            return True, v3d
        else:
            return False, v3d

    def handle_state_change(self):
        """
        State change signal handler.
        """
        self.updateGL()

    def handle_set_camera(self, action):
        """
        Sets camera from name derived from the text of a QAction.

        :param action: QAction
        """
        self.set_camera(str(action.text().toAscii()))

    def handle_set_mode(self, mode):
        """
        Set active camera drawing mode.

        :param mode: abcview.io.Mode enum value
        """
        self.setCursor(QtCore.Qt.WaitCursor)
        if self.sender(): # via menu action 
            mode = self.sender().data().toInt()[0]
        if mode not in GL_MODE_MAP.keys():
            raise Exception('Invalid drawing mode: {0}'.format(mode))
        self.camera.mode = mode
        self.setCursor(QtCore.Qt.ArrowCursor)

    def handle_camera_action(self, action):
        """
        New camera menu handler.

        :param action: QAction object
        """
        action_name = str(action.text().toAscii())
        if action_name == 'New':
            text, ok = QtGui.QInputDialog.getText(self,
                                                  'New Camera',
                                                  'Camera Name:',
                                                  QtGui.QLineEdit.Normal)
            if ok and not text.isEmpty():
                name = str(text.toAscii())
                camera = abcview.gl.GLCamera(self, name)
                self.add_camera(camera)
                self.set_camera(name)

    def selection(self, x, y):
        """
        Bounding box selection handler. This handles selecting at the 
        scene level, e.g. GLScenes. Object-level selection is handled
        in the AbcOpenGL lib. 

        :param x: mouse x position
        :param y: mouse y position
        :return: list of GLScene objects
        """
        abcview.log.debug('[{0}.selection] {1} {2} {3}'.format(self, x, y, self.camera))

        self.setDisabled(True)

        #--- begin adjustments for fixed aspect ratio cameras
        #TODO: consolidate this code and same from _paint_fixed()

        # get basic size values for this viewer
        camera_width = self.camera.get_size(self)[0]
        camera_height = self.camera.get_size(self)[1]
        camera_aspect_ratio = camera_width / float(camera_height)
        
        # if fixed, lock the aspect ratio
        if self.camera.fixed:
            camera_aspect_ratio = self.camera.aspect_ratio
            if self.aspect_ratio() > self.camera.aspect_ratio:
                w = int(self.width() / (self.aspect_ratio() / camera_aspect_ratio))
                h = camera_height
            else:
                w = camera_width
                h = int(self.height() * (self.aspect_ratio() / camera_aspect_ratio))
            _x = int(abs(w-self.width()) / 2.0)
            _y = int(abs(h-self.height()) / 2.0)

        # camera size matches viewer
        else:
            _x = _y = 0
            w = self.width()
            h = self.height()
        
        #--- end fixed ratio adjustments

        MaxSize = 512

        #viewport = glGetIntegerv(GL_VIEWPORT)
        viewport = [_x, _y, w, h]
        buffer = OpenGL.GL.glSelectBuffer(MaxSize)

        OpenGL.GL.glRenderMode(OpenGL.GL.GL_SELECT)
        OpenGL.GL.glInitNames()

        # adjust mouse y value
        if self.camera.fixed:
            y = y - (_y * 2)

        OpenGL.GL.glMatrixMode(OpenGL.GL.GL_PROJECTION)
        OpenGL.GL.glPushMatrix()
        OpenGL.GL.glLoadIdentity()
        OpenGL.GLU.gluPickMatrix(x, (viewport[3] - y), 5.0, 5.0, viewport)

        # adjust ratio for fixed cameras
        if self.camera.fixed:
            ratio = self.camera.aspect_ratio
        else:
            ratio = self.aspect_ratio()

        OpenGL.GLU.gluPerspective(self.camera.fovy, camera_aspect_ratio, 
                       self.camera.near, self.camera.far)

        # draw the scenes
        for scene in self.state.scenes:

            # skip non-visible scenes
            if not scene.visible:
                continue

            #TODO: pick on translated scenes
            # push local transforms
            if scene.has_xform_overrides():
                OpenGL.GL.glPushMatrix()
                OpenGL.GL.glTranslatef(*scene.translate)
                OpenGL.GL.glRotatef(*scene.rotate)
                OpenGL.GL.glScalef(*scene.scale)

            # pick anywhere within the scene bounds
            if scene.mode != abcview.io.Mode.OFF:
                mode = OpenGL.GL.GL_POLYGON

            # pick just on the bounding box edges
            else:
                mode = OpenGL.GL.GL_LINES
            
            # draw scene bounds
            scene.draw_bounds(self.state.current_time, mode)

            # pop local transforms
            if scene.has_xform_overrides():
                OpenGL.GL.glPopMatrix()

        #OpenGL.GL.glMatrixMode(OpenGL.GL.GL_PROJECTION)
        OpenGL.GL.glPopMatrix()

        # get the list of gl picks
        hits = OpenGL.GL.glRenderMode(OpenGL.GL.GL_RENDER)

        self.setDisabled(False)

        # return list of picked scenes
        return self.state.scenes[hits[-1].names[-1]] if hits else None

    def isReady(self):
        if not self.isVisible():
            return False
        elif not self.isEnabled():
            return False
        elif not self.isValid():
            return False
        elif self not in self.camera.views:
            return False
        elif not self.state:
            return False
        elif self.isHidden():
            return False
        else:
            return True
        
    ## base class overrides

    def initializeGL(self):
        self.makeCurrent()
        OpenGL.GL.glPointSize(1.0)
        OpenGL.GL.glEnable(OpenGL.GL.GL_AUTO_NORMAL)
        OpenGL.GL.glEnable(OpenGL.GL.GL_COLOR_MATERIAL)
        OpenGL.GL.glEnable(OpenGL.GL.GL_NORMALIZE)
        OpenGL.GL.glDisable(OpenGL.GL.GL_CULL_FACE)
        OpenGL.GL.glShadeModel(OpenGL.GL.GL_SMOOTH)
        OpenGL.GL.OpenGL.GL.glClearColor(0.15, 0.15, 0.15, 0.0)
        set_diffuse_light()

    def paintGL(self):
        """
        OpenGL painting override
        """
        if not self.isReady():
            return
        
        OpenGL.GL.glClear(OpenGL.GL.GL_COLOR_BUFFER_BIT | OpenGL.GL.GL_DEPTH_BUFFER_BIT)

        # update camera
        self.camera.apply()

        # adjusts the camera size
        self._paint_fixed()
        
        # draw the grid lines
        if self.camera.draw_grid:
            self._paint_grid()
        
        # draw geom normals
        if self.camera.draw_normals:
            self._paint_normals()

        # draw each scene
        for scene in self.state.scenes:
           
            if not scene.visible:
                continue

            if not scene.drawable():
                #self.SIGNAL_UNDRAWABLE_SCENE.emit(scene, self.state.current_frame)
                OpenGL.GL.glColor3d(1, 1, 0)
                self.renderText(0, 0, 0, '[Error drawing {0}]'.format(scene.name))
                continue

            # draw mode override
            mode = GL_MODE_MAP.get(scene.properties.get('mode'),
                   GL_MODE_MAP.get(self.camera.mode, OpenGL.GL.GL_LINE)
                   )
            if mode > 1:
                OpenGL.GL.glPolygonMode(OpenGL.GL.GL_FRONT_AND_BACK, mode)
           
            # apply local transforms
            if scene.has_xform_overrides():
                OpenGL.GL.glPushMatrix()
                OpenGL.GL.glTranslatef(*scene.translate)
                OpenGL.GL.glRotatef(*scene.rotate)
                OpenGL.GL.glScalef(*scene.scale)
            
            if scene.selected:
                OpenGL.GL.glColor3d(0.5, 0.5, 0)
            else:
                OpenGL.GL.glColor3f(*scene.color)

            # draw scene bounds
            if self.camera.draw_bounds:
                scene.draw_bounds(self.state.current_time)
            
            # draw scene geom
            if mode != abcview.io.Mode.OFF:
                scene.draw(self.camera.visible, mode == abcview.io.Mode.BOUNDS)
            
            # draw scene labels
            if self.camera.draw_labels:
                c = scene.bounds().center()
                self.renderText(c[0], c[1], c[2], scene.name)

            if scene.has_xform_overrides():
                OpenGL.GL.glPopMatrix()
        
        # draw the heads-up-display
        if self.camera.draw_hud:
            self._paint_hud()
            
    def resizeGL(self, width, height):
        try:
            self.camera.resize()
        except AttributeError, e:
            pass

    @update_camera
    def keyPressEvent(self, event):
        """
        key press event handler
        """
        key = event.key()
        mod = event.modifiers()

        def _set_selected_scene_mode(mode):
            # applies display mode to objects/scenes
            self.setCursor(QtCore.Qt.WaitCursor)
            found = False
            for scene in self.state.scenes:
                if scene.selected:
                    scene.mode = mode
                    found = True
                    if mode != abcview.io.Mode.OFF:
                        scene.load()
            if not found:
                self.handle_set_mode(mode)
            self.state.current_frame = self.state.current_frame
            self.updateGL()
            self.setCursor(QtCore.Qt.ArrowCursor)

        # space bar - playback control
        if key == QtCore.Qt.Key_Space:
            if len(self.state.scenes) == 0 or \
                   self.state.frame_count <= 1:
                return
            if self.state.is_playing():
                self.state.stop()
            else:
                self.state.play()
        
        # 0 - display off
        elif key == QtCore.Qt.Key_0:
            _set_selected_scene_mode(abcview.io.Mode.OFF)

        # 1 - smooth
        elif key == QtCore.Qt.Key_1:
            _set_selected_scene_mode(abcview.io.Mode.FILL)

        # 2 - lines
        elif key == QtCore.Qt.Key_2:
            _set_selected_scene_mode(abcview.io.Mode.LINE)

        # 3 - points
        elif key == QtCore.Qt.Key_3:
            _set_selected_scene_mode(abcview.io.Mode.POINT)

        # 4 - bounds
        elif key == QtCore.Qt.Key_4:
            _set_selected_scene_mode(abcview.io.Mode.BOUNDS)

        # right arroy - increment frame
        elif key == QtCore.Qt.Key_Right:
            self.state.current_frame = self.state.current_frame + 1

        # left arrow - decrement frame
        elif key == QtCore.Qt.Key_Left:
            self.state.current_frame = self.state.current_frame - 1

        # shift+f - toggle fixed aspect ratio
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_A:
            self.camera._set_fixed()
    
        # shift+b - toggle bounding boxes
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_B:
            self.camera._set_draw_bounds()

        # shift+n - toggle draw normals
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_N:
            self.camera._set_draw_normals()

        # shift+g - toggle grid
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_G:
            self.camera._set_draw_grid()

        # shift+h - toggle hud
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_H:
            self.camera._set_draw_hud()

        # shift+l - toggle labels
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_L:
            self.camera._set_draw_labels()

        # shift+v - toggle visibility
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_V:
            self.camera._set_visible()

        # shift+| - split vertically
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_Bar:
            self.split_vert()

        # shift+| - split horizontally
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_Underscore:
            self.split_horz()
        
        # shift+- - unsplit
        elif mod == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_Minus:
            self.unsplit()

        # "f" - frame scene
        elif key == QtCore.Qt.Key_F:
            self.frame()

    def mouseDoubleClickEvent(self, event):
        """
        mouse double-click event handler
        """
        if self.camera.mode == abcview.io.Mode.OFF:
            return

        # get scene selection hits
        hit = None
        for scene in self.state.scenes:
            if scene.mode == abcview.io.Mode.OFF or not scene.visible:
                continue
            x, y = event.pos().x(), event.pos().y()
            camera = self.camera.views[self]
            hit = scene.selection(x, y, camera)

        #HACK: need a better/faster way to find the object
        if hit:
            name = hit.split('/')[-1]
            self.SIGNAL_OBJECT_SELECTED.emit('.*{0}'.format(name))

    def mousePressEvent(self, event):
        """
        mouse press event handler
        """
        #TODO: use weakref for this instead? 
        self.state.active_viewer = self

        # make this viewer the active one
        if self._main:
            self._main.viewer = self

        # process mouse event
        if event.button() == QtCore.Qt.LeftButton and \
           event.modifiers() == QtCore.Qt.NoModifier:
            self.setCursor(QtCore.Qt.ArrowCursor)

            if self.__mode == OpenGL.GL.GL_SELECT:
                for scene in self.state.scenes:
                    scene.selected = False
                self.SIGNAL_CLEAR_SELECTION.emit()
                hit = self.selection(event.pos().x(), event.pos().y())
                if hit:
                    self.SIGNAL_SCENE_SELECTED.emit(hit)
                    hit.selected = True
                self.paintGL()
                return

        # process mouse event
        elif event.button() == QtCore.Qt.RightButton and \
           event.modifiers() == QtCore.Qt.NoModifier:
            self.setCursor(QtCore.Qt.ArrowCursor)
            
            menu = QtGui.QMenu(self)

            # splits
            layout_menu = QtGui.QMenu('Layout', self)
            self.splitHAct = QtGui.QAction(QtGui.QIcon('{0}/split_vert.png'.format(abcview.config.ICON_DIR)),
                                           'Split Vertical ',
                                           self)
            self.splitHAct.setShortcut('Shift+|')
            self.splitHAct.triggered.connect(self.split_vert)
            layout_menu.addAction(self.splitHAct)

            self.splitVAct = QtGui.QAction(QtGui.QIcon('{0}/split_horz.png'.format(abcview.config.ICON_DIR)),
                                           'Split Horizontal ',
                                           self)
            self.splitVAct.setShortcut('Shift+_')
            self.splitVAct.triggered.connect(self.split_horz)
            layout_menu.addAction(self.splitVAct)
            
            self.closeAct = QtGui.QAction('Close ', self)
            self.closeAct.setShortcut('Shift+-')
            self.closeAct.triggered.connect(self.unsplit)
            layout_menu.addAction(self.closeAct)
            
            menu.addMenu(layout_menu)

            # cameras
            camera_menu = QtGui.QMenu('Cameras', self)
            camera_group = QtGui.QActionGroup(camera_menu)
            camera_group_unsaved = QtGui.QActionGroup(camera_menu)
            camera_group.setExclusive(False)
            camera_group_unsaved.setExclusive(True)

            for camera in self.state.cameras:
                camera_action = QtGui.QAction(camera.name, self)
                camera_action.setCheckable(True)
                if camera.name == self.camera.name:
                    camera_action.setChecked(True)
                if camera.name == 'interactive':
                    camera_action.setActionGroup(camera_group_unsaved)
                    camera_action.setToolTip('This camera cannot be saved.')
                else:
                    camera_action.setActionGroup(camera_group)
                camera_menu.addAction(camera_action)
            camera_group.triggered.connect(self.handle_set_camera)
            camera_group_unsaved.triggered.connect(self.handle_set_camera)
            camera_menu.triggered.connect(self.handle_camera_action)
            camera_menu.addSeparator()
            camera_menu.addAction('New')

            menu.addMenu(camera_menu)
          
            options_menu = QtGui.QMenu('Options', self)

            # bounds toggle menu item
            #self.aframeAct = QtGui.QAction("Autoframe", self)
            #self.aframeAct.setCheckable(True)
            #self.aframeAct.setChecked(self.camera.auto_frame)
            #self.connect(self.aframeAct, QtCore.SIGNAL("toggled (bool)"), 
            #        self.camera._set_auto_frame)
            #options_menu.addAction(self.aframeAct)

            # fixed aspect ratio toggle menu item
            self.fixedAct = QtGui.QAction('Fixed Aspect Ratio ', self)
            self.fixedAct.setShortcut('Shift+A')
            self.fixedAct.setCheckable(True)
            self.fixedAct.setChecked(self.camera.fixed)
            self.fixedAct.toggled.connect(self.camera._set_fixed)
            options_menu.addAction(self.fixedAct)

            # heads-up-display menu item
            self.hudAct = QtGui.QAction('Heads-Up-Display ', self)
            self.hudAct.setShortcut('Shift+H')
            self.hudAct.setCheckable(True)
            self.hudAct.setChecked(self.camera.draw_hud)
            self.hudAct.toggled.connect(self.camera._set_draw_hud)
            options_menu.addAction(self.hudAct)

            # labels toggle menu item
            self.labelsAct = QtGui.QAction('Labels ', self)
            self.labelsAct.setShortcut('Shift+L')
            self.labelsAct.setCheckable(True)
            self.labelsAct.setChecked(self.camera.draw_labels)
            self.labelsAct.toggled.connect(self.camera._set_draw_labels)
            options_menu.addAction(self.labelsAct)

            # normals toggle menu item
            self.normalsAct = QtGui.QAction('Normals ', self)
            self.normalsAct.setShortcut('Shift+N')
            self.normalsAct.setCheckable(True)
            self.normalsAct.setChecked(self.camera.draw_normals)
            self.normalsAct.toggled.connect(self.camera._set_draw_normals)
            options_menu.addAction(self.normalsAct)

            # bounds toggle menu item
            self.boundsAct = QtGui.QAction('Scene Bounds ', self)
            self.boundsAct.setShortcut('Shift+B')
            self.boundsAct.setCheckable(True)
            self.boundsAct.setChecked(self.camera.draw_bounds)
            self.boundsAct.toggled.connect(self.camera._set_draw_bounds)
            options_menu.addAction(self.boundsAct)

            # grid toggle menu item
            self.gridAct = QtGui.QAction('Show Grid ', self)
            self.gridAct.setShortcut('Shift+G')
            self.gridAct.setCheckable(True)
            self.gridAct.setChecked(self.camera.draw_grid)
            self.gridAct.toggled.connect(self.camera._set_draw_grid)
            options_menu.addAction(self.gridAct)

            # visibility toggle menu item
            self.visibleAct = QtGui.QAction('Visible Only ', self)
            self.visibleAct.setShortcut('Shift+V')
            self.visibleAct.setCheckable(True)
            self.visibleAct.setChecked(self.camera.visible)
            self.visibleAct.toggled.connect(self.camera._set_visible)
            options_menu.addAction(self.visibleAct)

            # shading toggle menu item
            self.shading_menu = QtGui.QMenu('Shading', self)
            shading_group = QtGui.QActionGroup(self.shading_menu)

            self.offAct = QtGui.QAction('Off', self)
            self.offAct.setShortcut('0')
            self.offAct.setCheckable(True)
            self.offAct.setActionGroup(shading_group)
            self.offAct.setData(abcview.io.Mode.OFF)
            self.offAct.setChecked(self.camera.mode == abcview.io.Mode.OFF)
            self.offAct.toggled.connect(self.handle_set_mode)
            self.shading_menu.addAction(self.offAct)

            self.fillAct = QtGui.QAction('Fill', self)
            self.fillAct.setShortcut('1')
            self.fillAct.setCheckable(True)
            self.fillAct.setActionGroup(shading_group)
            self.fillAct.setData(abcview.io.Mode.FILL)
            self.fillAct.setChecked(self.camera.mode == abcview.io.Mode.FILL)
            self.fillAct.toggled.connect(self.handle_set_mode)
            self.shading_menu.addAction(self.fillAct)
            
            self.lineAct = QtGui.QAction('Line', self)
            self.lineAct.setShortcut('2')
            self.lineAct.setCheckable(True)
            self.lineAct.setActionGroup(shading_group)
            self.lineAct.setData(abcview.io.Mode.LINE)
            self.lineAct.setChecked(self.camera.mode == abcview.io.Mode.LINE)
            self.lineAct.toggled.connect(self.handle_set_mode)
            self.shading_menu.addAction(self.lineAct)

            self.pointAct = QtGui.QAction('Point ', self)
            self.pointAct.setShortcut('3')
            self.pointAct.setCheckable(True)
            self.pointAct.setActionGroup(shading_group)
            self.pointAct.setData(abcview.io.Mode.POINT)
            self.pointAct.setChecked(self.camera.mode == abcview.io.Mode.POINT)
            self.pointAct.toggled.connect(self.handle_set_mode)
            self.shading_menu.addAction(self.pointAct)
            
            self.bboxAct = QtGui.QAction('Bounds ', self)
            self.bboxAct.setShortcut('4')
            self.bboxAct.setCheckable(True)
            self.bboxAct.setActionGroup(shading_group)
            self.bboxAct.setData(abcview.io.Mode.BOUNDS)
            self.bboxAct.setChecked(self.camera.mode == abcview.io.Mode.BOUNDS)
            self.bboxAct.toggled.connect(self.handle_set_mode)
            self.shading_menu.addAction(self.bboxAct)

            options_menu.addMenu(self.shading_menu)

            menu.addMenu(options_menu)
            menu.popup(QtCore.QPoint(event.globalX(), event.globalY()))

        else:
            self.__last_p2d = event.pos()
            self.__last_pok, self.__last_p3d = self.map_to_sphere(self.__last_p2d)
        
    @update_camera
    def mouseMoveEvent(self, event):
        """
        mouse move event handler
        """
        # alt key is required to move the camera
        if not event.modifiers() & QtCore.Qt.AltModifier:
            return
        newPoint2D = event.pos()
        if ((newPoint2D.x() < 0) or (newPoint2D.x() > self.width()) or
            (newPoint2D.y() < 0) or (newPoint2D.y() > self.height())):
            return
        value_y = 0
        newPoint_hitSphere, newPoint3D = self.map_to_sphere(newPoint2D)
        dx = float(newPoint2D.x() - self.__last_p2d.x())
        dy = float(newPoint2D.y() - self.__last_p2d.y())
        w = float(self.width())
        h = float(self.height())
        self.makeCurrent()

        if (((event.buttons() & QtCore.Qt.LeftButton) and (event.buttons() & QtCore.Qt.MidButton))
            or (event.buttons() & QtCore.Qt.LeftButton and event.modifiers() & QtCore.Qt.ControlModifier)
            or (event.buttons() & QtCore.Qt.RightButton and event.modifiers() & QtCore.Qt.AltModifier)):
            self.camera.dolly(dx, dy)
        
        elif (event.buttons() & QtCore.Qt.MidButton
              or (event.buttons() & QtCore.Qt.LeftButton and event.modifiers() & QtCore.Qt.ShiftModifier)):
            self.camera.track(dx, dy)

        elif event.buttons() & QtCore.Qt.LeftButton:
            self.__rotating = True
            self.camera.rotate(dx, dy)
            
        # TODO: replace with global state (with these as attrs)
        self.__last_p2d = newPoint2D
        self.__last_p3d = newPoint3D
        self.__last_pok = newPoint_hitSphere
    
    def mouseReleaseEvent(self, event):
        """
        mouse release event handler
        """
        self.__rotating = False
        self.__last_pok = False
        super(GLWidget, self).mouseReleaseEvent(event)

    @update_camera
    def wheelEvent(self, event):
        """
        mouse wheel event handler
        """
        dx = float(event.delta()) / 10
        self.camera.dolly(dx, 0)
        event.accept()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = None
    create_viewer_app(filepath)

#! /usr/bin/env python
#-******************************************************************************
#
# Copyright (c) 2012-2014,
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
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
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
import time
import logging
import traceback
from functools import wraps
from copy import deepcopy

try:
    from PyQt5 import QtWidgets
    from PyQt5 import QtGui
    from PyQt5 import QtCore
    from PyQt5.QtCore import pyqtSignal as Signal
except:
    from PySide2 import QtWidgets
    from PySide2 import QtGui
    from PySide2 import QtCore
    from PySide2.QtCore import Signal as Signal

import imath
import alembic

import abcview
import abcview.io
import abcview.gl
import abcview.widget.console_widget
import abcview.widget.viewer_widget
import abcview.widget.time_slider
import abcview.widget.tree_widget

__all__ = [
    'create_app',
    'AbcView',
    'io2gl',
    'version_check',
]

def make_dirty(func):
    """make abcview session dirty decorator"""
    @wraps(func)
    def with_wrapped_func(*args, **kwargs):
        return func(*args, **kwargs)
        if args[0].session:
            args[0].session.make_dirty()
    return with_wrapped_func

def make_clean(func):
    """make abcview session clean decorator"""
    @wraps(func)
    def with_wrapped_func(*args, **kwargs):
        return func(*args, **kwargs)
        if args[0].session:
            args[0].session.make_clean()
    return with_wrapped_func

def wait(func):
    """wait/arrow mouse cursor decorator"""
    @wraps(func)
    def with_wrapped_func(*args, **kwargs):
        args[0].setCursor(QtCore.Qt.WaitCursor)
        ret = func(*args, **kwargs)
        args[0].setCursor(QtCore.Qt.ArrowCursor)
        return ret
    return with_wrapped_func

def message(info):
    dialog = QtWidgets.QMessageBox()
    dialog.setStyleSheet(abcview.style.DIALOG)
    dialog.setText(info)
    dialog.exec_()

# global file load counter (for default scene colors)
global COUNT
COUNT = 0

def io2gl(item, viewer=None):
    """
    Recursively recasts an IO-module object to a GL-module object.
    Used for loading session items into the GL viewer.

    :param item: Session, Scene, Camera or ICamera object
    :param viewer: abcview.widget.viewer_widget.GLWidget object
    """
    global COUNT
    COUNT += 1
    if isinstance(item, abcview.io.Session):
        for child in item.walk():
            io2gl(child, viewer)
        return

    elif isinstance(item, abcview.io.Scene):
        if not os.path.isfile(item.filepath):
            abcview.log.warn('file not found {0}'.format(item.filepath))
            return
        item.__class__ = abcview.gl.GLScene
        item.init()

    elif isinstance(item, abcview.io.Camera):
        _translation = item.translation
        _rotation = item.rotation
        _scale = item.scale
        _center = item.center
        _near = item.near
        _far = item.far
        _ratio = item.aspect_ratio
        item.__class__ = abcview.gl.GLCamera
        item.init(viewer,
                  translation=_translation,
                  rotation=_rotation,
                  scale=_scale,
                  center=_center,
                  near=_near,
                  far=_far,
                  aspect_ratio=_ratio,
                 )

    elif isinstance(item, abcview.io.ICamera):
        item.__class__ = abcview.gl.GLICamera
        item.init(viewer)

    else:
        return

class QScriptAction(QtWidgets.QGroupBox):
    def __init__(self, name, filepath, action, doc='', version='', author=''):
        """
        :param name: name of the script
        :param action: QWidgetAction object
        :param doc: doc string
        :param version: version string
        :param author: author string
        """
        super(QScriptAction, self).__init__()
        self.action = action
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setMargin(0)
        self.layout.setSpacing(0)
        self.label = QtWidgets.QPushButton(os.path.basename(name))
        self.button = QtWidgets.QPushButton()
        self.button.setFixedSize(12, 12)
        self.button.setObjectName('edit_button')
        self.button.setIcon(QtGui.QIcon('{0}/edit.png'.format(abcview.config.ICON_DIR)))
        self.button.setIconSize(self.button.size())
        self.button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.button)
        self.name = name
        self.filepath = filepath
        self.setLayout(self.layout)
        self.label.pressed.connect(self.handle_clicked)
        self.button.pressed.connect(self.handle_edit)
        self.setToolTip('{0} {1}\n(author: {2})\n\n{3}'.format(name, version, author, doc))

    def handle_clicked(self):
        """script click handler"""
        self.action.trigger()

    def handle_edit(self):
        """script edit button handler"""
        cmd = ' '.join([abcview.config.SCRIPT_EDITOR, self.filepath])
        abcview.log.debug(cmd)
        os.system(cmd)

class AbcMenuBar(QtWidgets.QMenuBar):
    def __init__(self, parent, main):
        super(AbcMenuBar, self).__init__(parent)
        self.main = main
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.file_menu = QtWidgets.QMenu('File')
        self.widget_menu = QtWidgets.QMenu('Widgets')
        self.script_menu = QtWidgets.QMenu('Scripts')
        self.help_menu = QtWidgets.QMenu('Help')

        self.file_menu.setStyleSheet(abcview.style.MAIN)
        self.widget_menu.setStyleSheet(abcview.style.MAIN)
        self.script_menu.setStyleSheet(abcview.style.MAIN)
        self.help_menu.setStyleSheet(abcview.style.MAIN)

        self.setup_file_menu()
        self.setup_wid_menu()
        self.setup_script_menu()
        self.setup_help_menu()

    def setup_file_menu(self):
        self.file_menu.addAction('New', self.main.handle_new, 'Ctrl+N')
        self.file_menu.addAction('Open', self.main.handle_open, 'Ctrl+O')
        self.file_menu.addAction('Import', self.main.handle_import, 'Ctrl+I')
        self.file_menu.addAction('Reload', self.main.handle_reload, 'Ctrl+R')

        self.file_menu.addSeparator()
        self.file_menu.addAction('Save', self.main.handle_save, 'Ctrl+S')
        self.file_menu.addAction('Save As..', self.main.handle_save_as, 'Ctrl+Shift+S')
        self.file_menu.addSeparator()
        self.file_menu.addAction('Save Layout', self.main.save_settings, 'Ctrl+Alt+S')
        self.file_menu.addAction('Reset Layout', self.main.reset_settings)
        self.file_menu.addAction('Review Mode', self.main.review_settings)
        self.file_menu.addSeparator()
        self.file_menu.addAction('Quit', self.main.close, 'Ctrl+Q')
        self.addMenu(self.file_menu)

    def setup_wid_menu(self):
        self.console_action = QtWidgets.QAction('Console', self)
        self.console_action.setShortcut('Ctrl+Shift+C')
        self.console_action.setCheckable(True)
        self.console_action.setChecked(True)
        self.console_action.toggled.connect(self.handle_show_console)
        self.widget_menu.addAction(self.console_action)

        self.object_action = QtWidgets.QAction('Objects', self)
        self.object_action.setShortcut('Ctrl+Shift+O')
        self.object_action.setCheckable(True)
        self.object_action.setChecked(True)
        self.object_action.toggled.connect(self.handle_show_objects)
        self.widget_menu.addAction(self.object_action)

        self.props_action = QtWidgets.QAction('Properties', self)
        self.props_action.setShortcut('Ctrl+Shift+P')
        self.props_action.setCheckable(True)
        self.props_action.setChecked(True)
        self.props_action.toggled.connect(self.handle_show_props)
        self.widget_menu.addAction(self.props_action)

        self.time_slider_action = QtWidgets.QAction('Timeline', self)
        self.time_slider_action.setShortcut('Ctrl+Shift+T')
        self.time_slider_action.setCheckable(True)
        self.time_slider_action.setChecked(True)
        self.time_slider_action.toggled.connect(self.handle_show_timeline)
        self.widget_menu.addAction(self.time_slider_action)

        self.viewer_action = QtWidgets.QAction('Viewer', self)
        self.viewer_action.setShortcut('Ctrl+Shift+V')
        self.viewer_action.setCheckable(True)
        self.viewer_action.setChecked(True)
        self.viewer_action.toggled.connect(self.handle_show_viewer)
        self.widget_menu.addAction(self.viewer_action)

        self.addMenu(self.widget_menu)

    def setup_script_menu(self):
        self.addMenu(self.script_menu)
        self.handle_refresh_scripts()

    def setup_help_menu(self):
        self.help_menu.addAction('About Alembic', self.handle_about_abc)
        self.help_menu.addAction('About AbcView', self.handle_about_abcview)
        self.addMenu(self.help_menu)

    def handle_refresh_scripts(self):
        self.script_menu.clear()
        self.script_menu.addAction('Refresh', self.handle_refresh_scripts)
        self.script_menu.addSeparator()

        def get_docs(script):
            """
            parses a python file looking for docstring, __name__ and __author__.

            :param script: filepath to .py file
            """
            import ast

            doc = ''
            name = os.path.basename(script)
            version = ''
            author = ''

            try:
                m = ast.parse(''.join(open(script)))
                doc = ast.get_docstring(m)
                assigns = [node for node in m.body if isinstance(node, ast.Assign)]
                names = [a.value.s for a in assigns if getattr(a.targets[0], 'id', None) == '__name__']
                authors = [a.value.s for a in assigns if getattr(a.targets[0],'id', None) == '__author__']
                versions = [a.value.s for a in assigns if getattr(a.targets[0], 'id', None) == '__version__']

                if names:
                    name = names[0]
                else:
                    name = os.path.basename(script)
                if authors:
                    author = authors[0]
                if versions:
                    version = versions[0]

            except Exception, e:
                abcview.log.error(e)

            return doc, name, version, author

        def find_scripts(path):
            """
            walks scripts dir looking for .py files

            :param path: directory containing scripts
            """
            _scripts = {}
            if not path or not os.path.isdir(path):
                return
            for r, d, f in os.walk(path):
                for files in f:
                    name = os.path.basename(files)
                    if name == '__init__.py':
                        continue
                    if files.endswith('.py'):
                        script = os.path.join(r, files)
                        doc, name, version, author = get_docs(script)
                        _scripts[name] = {
                            'name': name,
                            'filepath': script,
                            'doc': doc,
                            'version': version,
                            'author': author
                        }
            return _scripts

        def build_scripts(scripts):
            """
            builds up the script menu from a dict of found scripts
            """
            for name, meta in scripts.items():
                doc = meta.get('doc')
                version = meta.get('version')
                author = meta.get('author')
                filepath = meta.get('filepath')
                script_act = QtWidgets.QWidgetAction(self.script_menu)
                script_act.setDefaultWidget(QScriptAction(name, filepath, script_act, doc, version, author))
                script_act.setData(filepath)
                script_act.triggered.connect(self.handle_run_script)
                self.script_menu.addAction(script_act)

        # built-in scripts that ship with abcview
        scripts = find_scripts(abcview.config.SCRIPT_DIR)

        # user-defined script paths
        for path in abcview.config.USER_SCRIPT_DIR:
            scripts.update(find_scripts(path) or {})

        # build the scripts menu
        build_scripts(scripts)

    def handle_run_script(self):
        script_path = str(self.sender().data().toString())
        self.main.load_script(script_path)

    def handle_show_console(self, toggled):
        self.main.toggle_widget(self.main.console)

    def handle_show_objects(self):
        self.main.toggle_widget(self.main.objects_group)

    def handle_show_props(self):
        self.main.toggle_widget(self.main.properties_splitter)

    def handle_show_timeline(self):
        self.main.toggle_widget(self.main.time_slider_toolbar)

    def handle_show_viewer(self):
        self.main.toggle_widget(self.main.viewer_group)

    def handle_about_abc(self):
        message('Using Alembic {0}'.format(alembic.Abc.GetLibraryVersionShort()))

    def handle_about_abcview(self):
        _v = ' '.join([abcview.config.__prog__, abcview.config.__version__])
        message('\n'.join([_v, abcview.__doc__]))

class FindLineEdit(QtWidgets.QLineEdit):
    """
    Auto-unfocus line editor used for search bar.
    """
    def __init__(self, parent):
        super(FindLineEdit, self).__init__(parent)
        self._parent = parent
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Maximum)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

    def leaveEvent(self, event):
        self._parent.setFocus()
        super(FindLineEdit, self).leaveEvent(event)

class Splash(QtWidgets.QSplashScreen):
    """
    AbcView splash screen.
    """
    def __init__(self, parent):
        super(Splash, self).__init__(parent)
        self._parent = parent
        self.setStyleSheet(abcview.style.SPLASH)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # logo
        self.logo = QtWidgets.QLabel()
        self.logo.setPixmap(QtGui.QPixmap('{0}/logo.png'.format(abcview.config.ICON_DIR)))

        self.resize(600, 350)
        self.move(0, 0)

        # layout
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.setMargin(0)
        layout.addWidget(self.logo)
        self.text = QtWidgets.QLineEdit()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setMinimum(0)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        layout.addWidget(self.text)
        self.setLayout(layout)

    def updateProgress(self, value):
        """
        Updates the splash screen progress bar.

        :param value: new value (must be b/w min and max values)
        """
        self.progress.setValue(value)

    def setMessage(self, message):
        """
        Sets the message to be displayed in the splash screen.

        :param message: message as string
        """
        self.text.setText(message)

## MAIN -----------------------------------------------------------------------
class AbcView(QtWidgets.QMainWindow):
    """
    Main application. The best way to instantiate this class is to use
    the :py:func:`.create_app` function.
    """

    TITLE = ' '.join([abcview.config.__prog__, abcview.config.__version__])

    def __init__(self, filepath=None):
        """
        Creates an instance of the AbcView Main Window.

        :param filepath: file to load (.io or .abc)
        """
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowState(QtCore.Qt.WindowActive)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle(self.TITLE)
        self.setStyle(QtWidgets.QStyleFactory.create('cleanlooks'))
        self.setStyleSheet(abcview.style.MAIN)
        self.setMinimumSize(200, 200)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # deferred load list, files loaded after event loop starts
        self._load_files = []

        # overrides are used for deferring frame range overrides
        self._overrides = {}

        # for storing session data
        self.settings = QtCore.QSettings('Alembic',
                           '-'.join([abcview.config.__prog__, abcview.config.__version__]))
        self.session = abcview.io.Session(filepath)

        # main menu
        self.main_menu = AbcMenuBar(self, main=self)
        self.setMenuBar(self.main_menu)

        self.objects_group = QtWidgets.QGroupBox(self)
        self.objects_group.setLayout(QtWidgets.QVBoxLayout())

        #TODO: refactor these signals
        self.objects_tree = abcview.widget.tree_widget.ObjectTreeWidget(self, main=self)
        self.objects_tree.signal_item_removed.connect(self.handle_item_removed)
        self.objects_tree.SIGNAL_VIEW_CAMERA.connect(self.handle_view_camera)
        self.objects_tree.itemSelectionChanged.connect(self.handle_object_selection)
        self.objects_tree.itemClicked.connect(self.handle_item_selected)

        self.find_line_edit = FindLineEdit(self)
        self.objects_group.layout().setSpacing(0)
        self.objects_group.layout().setMargin(0)
        self.objects_group.layout().addWidget(self.find_line_edit)
        self.objects_group.layout().addWidget(self.objects_tree)

        # tree widgets
        self.properties_tree = abcview.widget.tree_widget.PropertyTreeWidget(self, main=self)
        self.samples_tree = abcview.widget.tree_widget.SampleTreeWidget(self, main=self)
        self.array_tree = abcview.widget.tree_widget.ArrayTreeWidget(self, main=self)

        # console widget
        self.console = abcview.widget.console_widget.AbcConsoleWidget(self)
        self.console.updateNamespace({
            'exit': self.console.exit,
            'find': self.find,
            'app': self,
            'objects': self.objects_tree,
            'properties': self.properties_tree,
            'samples': self.samples_tree,
            'selected': self.get_selected,
            'alembic': alembic,
            'abcview': abcview
            })

        # viewer
        self.viewer = abcview.widget.viewer_widget.GLWidget(self)
        self.viewer_group = QtWidgets.QGroupBox(self)
        self.viewer_group.setLayout(QtWidgets.QVBoxLayout())
        self.viewer_group.layout().setSpacing(0)
        self.viewer_group.layout().setMargin(0)
        self.viewer_group.layout().addWidget(self.viewer)
        self.main_menu.setFocusProxy(self.viewer)

        # viewer/state connections
        self.viewer.SIGNAL_SCENE_ERROR.connect(self.handle_viewer_error)
        self.viewer.SIGNAL_SCENE_OPENED.connect(self.handle_scene_opened)
        self.viewer.SIGNAL_SET_CAMERA.connect(self.handle_set_camera)
        self.viewer.SIGNAL_NEW_CAMERA.connect(self.handle_new_camera)
        self.viewer.state.SIGNAL_CURRENT_FRAME.connect(self.handle_update_frame)
        self.viewer.state.SIGNAL_PLAY_FWD.connect(self.handle_state_play_fwd)
        self.viewer.state.SIGNAL_PLAY_STOP.connect(self.handle_state_play_stop)
        self.viewer.SIGNAL_SCENE_SELECTED.connect(self.handle_scene_selected)
        self.viewer.SIGNAL_OBJECT_SELECTED.connect(self.handle_object_selected)
        self.viewer.SIGNAL_CLEAR_SELECTION.connect(self.objects_tree.clearSelection)
        self.viewer.SIGNAL_UNDRAWABLE_SCENE.connect(self.handle_bad_scene)

        # time slider
        self.time_slider = abcview.widget.time_slider.TimeSlider(self)
        self.time_slider.setFocus(True)
        self.time_slider.SIGNAL_PLAY_FWD.connect(self.handle_play)
        self.time_slider.SIGNAL_PLAY_STOP.connect(self.handle_stop)
        self.time_slider.SIGNAL_FIRST_FRAME_CHANGED.connect(self.handle_first_frame_change)
        self.time_slider.SIGNAL_LAST_FRAME_CHANGED.connect(self.handle_last_frame_change)
        self.time_slider_toolbar = QtWidgets.QToolBar(self)
        self.time_slider_toolbar.setObjectName('time_slider_toolbar')
        self.time_slider_toolbar.addWidget(self.time_slider)
        self.time_slider_toolbar.setMovable(False)
        self.addToolBar(QtCore.Qt.BottomToolBarArea, self.time_slider_toolbar)

        # splitters
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.console_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.objects_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.properties_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.properties_splitter.addWidget(self.properties_tree)
        self.properties_splitter.addWidget(self.samples_tree)
        self.properties_splitter.addWidget(self.array_tree)
        self.objects_splitter.addWidget(self.objects_group)
        self.objects_splitter.addWidget(self.viewer_group)
        self.objects_splitter.addWidget(self.properties_splitter)
        self.main_splitter.addWidget(self.objects_splitter)
        self.console_splitter.addWidget(self.main_splitter)
        self.console_splitter.addWidget(self.console)
        self.setCentralWidget(self.console_splitter)

        # TODO: refactor signals to new signal object method
        self.objects_tree.itemSelectionChanged.connect(self.properties_tree.clear)
        self.properties_tree.itemSelectionChanged.connect(self.samples_tree.clear)
        self.samples_tree.itemSelectionChanged.connect(self.array_tree.clear)
        self.objects_tree.itemLoaded.connect(self.handle_item_loaded)
        self.objects_tree.itemUnloaded.connect(self.handle_item_unloaded)
        self.objects_tree.itemClicked.connect(self.handle_object_clicked)
        self.properties_tree.itemClicked.connect(self.handle_property_clicked)
        self.samples_tree.itemClicked.connect(self.array_tree.show_values)
        self.find_line_edit.returnPressed.connect(self.handle_find)

        # wait for main event loop to start
        QtWidgets.QApplication.instance().SIGNAL_STARTING_UP.connect(self._start)

        # create the splash screen
        self.splash = Splash(self)

        # open a session
        if filepath and filepath.endswith(abcview.io.Session.EXT):
            self.open_file(filepath)

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, id(self))

    @make_clean
    def clear(self):
        """
        Clears session and viewer.
        """
        self.session = abcview.io.Session()
        self.viewer.clear()
        self.objects_tree.clear()
        self.properties_tree.clear()
        self.samples_tree.clear()
        self.array_tree.clear()

    def confirm_close(self, message):
        """
        Window close confirmation.

        :param message: text to display
        """
        msg = QtWidgets.QMessageBox()
        msg.setStyleSheet(abcview.style.DIALOG)
        msg.setText(message)
        msg.setInformativeText('Do you want to save your changes?')
        msg.setStandardButtons(QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
        msg.setDefaultButton(QtWidgets.QMessageBox.Save)
        return msg.exec_()

    ## settings

    def _settings(self, width, height):
        # default position settings
        self.setGeometry(200, 200, width, height)

        # default splitter locations
        self.objects_splitter.setSizes([50, 200, 50])

        # default widgets settings
        self.main_menu.object_action.setChecked(False)
        self.main_menu.props_action.setChecked(False)
        self.main_menu.console_action.setChecked(False)
        self.main_menu.viewer_action.setChecked(True)
        self.main_menu.time_slider_action.setChecked(True)

        # default viewer settings
        self.viewer.resize(self.width(), self.height())
        self.viewer.draw_hud = False

    def reset_settings(self, width=550, height=500):
        """
        Resets the AbcView layout settings to default values.
        """
        self.settings.clear()
        self._settings(width, height)
        self.viewer.camera.draw_grid = True
        self.viewer.camera.draw_hud = False
        self.viewer.camera.draw_normals = False
        self.viewer.camera.fixed = False
        self.viewer.camera.visible = True

    def review_settings(self):
        """
        Loads 'review' display settings. Does not affect saved settings.
        """
        self._settings(1200, 600)
        self.viewer.camera.draw_grid = False
        self.viewer.camera.draw_hud = True
        self.viewer.camera.draw_normals = False
        self.viewer.camera.fixed = True
        self.viewer.camera.visible = True

    def load_settings(self):
        """
        Loads AbcView layout settings from a PyQt settings file.
        """
        geom = self.settings.value('geometry')
        if geom.isNull() or not geom.isValid():
            self.reset_settings()
            return

        # general settings
        self.restoreGeometry(geom.toByteArray())
        self.restoreState(self.settings.value('window_state').toByteArray())

        # layout settings
        self.settings.beginGroup('layout')
        self.main_splitter.restoreState(
                self.settings.value('main_splitter').toByteArray())
        self.objects_splitter.restoreState(
                self.settings.value('objects_splitter').toByteArray())
        self.properties_splitter.restoreState(
                self.settings.value('properties_splitter').toByteArray())
        self.console_splitter.restoreState(
                self.settings.value('console_splitter').toByteArray())
        self.main_menu.object_action.setChecked(not self.settings.value('objects_hidden').toBool())
        self.objects_group.setHidden(self.settings.value('objects_hidden').toBool())
        self.main_menu.props_action.setChecked(not self.settings.value('properties_hidden').toBool())
        self.properties_splitter.setHidden(self.settings.value('properties_hidden').toBool())
        self.main_menu.console_action.setChecked(not self.settings.value('console_hidden').toBool())
        self.console.setHidden(self.settings.value('console_hidden').toBool())
        self.main_menu.time_slider_action.setChecked(not self.settings.value('time_slider_hidden').toBool())
        self.time_slider_toolbar.setHidden(self.settings.value('time_slider_hidden').toBool())
        self.main_menu.viewer_action.setChecked(not self.settings.value('viewer_hidden').toBool())
        self.viewer_group.setHidden(self.settings.value('viewer_hidden').toBool())
        self.settings.endGroup()

        # restore viewer settings
        self.settings.beginGroup('viewer')
        self.viewer.restoreGeometry(self.settings.value('geometry').toByteArray())

        # drawing mode
        mode, found = self.settings.value('draw_mode').toInt()
        if found:
            self.viewer.mode = mode

        self.settings.endGroup()

    def save_settings(self, settings=None):
        """
        Saves layout settings to a PyQt settings file.
        """
        if settings is None:
            settings = self.settings

        # general settings
        settings.setValue('geometry', self.saveGeometry())
        settings.setValue('window_state', self.saveState())

        # layout settings
        settings.beginGroup('layout')
        settings.setValue('main_splitter', self.main_splitter.saveState())
        settings.setValue('objects_splitter', self.objects_splitter.saveState())
        settings.setValue('properties_splitter', self.properties_splitter.saveState())
        settings.setValue('console_splitter', self.console_splitter.saveState())
        settings.setValue('objects_hidden', self.objects_group.isHidden())
        settings.setValue('properties_hidden', self.properties_splitter.isHidden())
        settings.setValue('console_hidden', self.console.isHidden())
        settings.setValue('time_slider_hidden', self.time_slider_toolbar.isHidden())
        settings.setValue('viewer_hidden', self.viewer_group.isHidden())
        settings.endGroup()

        # save viewer settings
        settings.beginGroup('viewer')
        settings.setValue('geometry', self.saveGeometry())

        # save timeslider settings
        settings.endGroup()

    @make_dirty
    def toggle_widget(self, widget):
        """
        Toggles visibilty of given widget.

        :param widget: AbcView widget object.
        """
        if widget.isHidden():
            widget.show()
        else:
            widget.hide()

    def get_selected(self):
        """
        Returns the actively selected AbcView object.
        """
        items = self.objects_tree.selectedItems()
        if not items:
            return
        return items[0].object

    ## file io

    def set_default_mode(self, mode):
        """
        Sets the default display mode that overrides anything in the
        session file(s). Disable by setting mode to None.

        :param mode: alembic.io.Mode value, or None
        """
        abcview.log.debug('[{0}].set_default_mode: {1}'.format(self, mode))
        self._overrides['mode'] = mode

    def set_first_frame(self, frame):
        abcview.log.debug('[{0}.set_first_frame] {1}'.format(self, frame))
        self._overrides['first_frame'] = frame
        self.viewer.state.min_time = frame / self.viewer.state.frames_per_second
        self.time_slider.set_minimum(frame)
        self.time_slider.slider.setMinimum(frame)
        self.viewer.state.min_frame = frame

    def set_last_frame(self, frame):
        abcview.log.debug('[{0}.set_last_frame] {1}'.format(self, frame))
        self._overrides['last_frame'] = frame
        self.viewer.state.max_time = frame / self.viewer.state.frames_per_second
        self.time_slider.set_maximum(frame)
        self.time_slider.slider.setMaximum(frame)
        self.viewer.state.max_frame = frame

    def set_frames_per_second(self, fps=24):
        abcview.log.debug('[{0}.set_frames_per_second] {1}'.format(self, fps))
        self._overrides['frames_per_second'] = fps
        self.session.frames_per_second = fps
        self.viewer.state.frames_per_second = fps

    def set_current_frame(self, frame):
        abcview.log.debug('[{0}.set_current_frame] {1}'.format(self, frame))
        self._overrides['current_frame'] = frame
        self.viewer.state.current_frame = frame
        self.time_slider.set_value(frame)
        self.time_slider.slider.setValue(frame)
        self.viewer.state.current_frame = frame

    def set_load_files(self, filepaths):
        """
        Sets the deferred load list. Loads files after the main window and
        event loop is up and running.

        :param filepath: list of files to load
        :param mode: Override display mode (abcview.io.Mode)
        """
        self._load_files = deepcopy(filepaths)
        #self.setWindowTitle('%s - %s' % (self.TITLE,
        #    ', '.join([os.path.basename(f) for f in filepaths]))
        #)
        self.splash.progress.setMaximum(len(filepaths))

    def set_frames_from_session(self, session):
        """
        Updates the time slider's frame range according to the min/max
        frames of the given session.

        :param session: abcview.gl.GLScene object.
        """
        assert isinstance(session, abcview.io.Session), 'Invalid session'
        self.viewer.state.min_time = session.min_time
        self.viewer.state.max_time = session.max_time
        self.viewer.state.current_time = session.current_time
        self.time_slider.set_minimum(session.min_time * session.frames_per_second)
        self.time_slider.set_maximum(session.max_time * session.frames_per_second)
        self.time_slider.set_value(session.current_time * session.frames_per_second)

    def set_frames_from_scene(self, scene):
        """
        Updates the time slider's frame range according to the min/max
        frames of the given scene.

        :param scene: abcview.gl.GLScene object.
        """
        assert isinstance(scene, abcview.gl.GLScene), 'Invalid scene'
        self.viewer.state.min_time = scene.min_time()
        self.viewer.state.max_time = scene.max_time()
        self.time_slider.set_minimum(scene.min_time() * self.session.frames_per_second)
        self.time_slider.set_maximum(scene.max_time() * self.session.frames_per_second)

    def _start(self):
        """
        This is the startup callback function for when the QApplication starts
        its event loop. This handles deferred file loading.
        """
        abcview.log.debug('[{0}]._start'.format(self))
        self.viewer.setDisabled(True)

        self.splash.setMessage('starting up')
        self._wait()
        start = time.time()
        self.splash.show()

        # build the abcview session
        try:
            self._load()
        except Exception, e:
            traceback.print_exc()
            abcview.log.error(e)

        abcview.log.debug('session loaded in {0:.2fs}'.format(time.time() - start))
        self.splash.close()
        self.time_slider.SIGNAL_FRAME_CHANGED.connect(self.handle_time_slider_change)

        self.viewer.setEnabled(True)

    def _load(self):
        """
        Loads all the files and cameras in the load list, sets display
        overrides and creates tree widget items.
        """
        self.viewer.setDisabled(True)

        # track files that can't be loaded
        _bad_files = []

        # if just one session file, replace current session
        if len(self._load_files) == 1 and self._load_files[0].endswith(abcview.io.Session.EXT):
            self.session = abcview.io.Session(self._load_files[0])

        # otherwise, add each file to current session
        else:
            for filepath in self._load_files:
                if not os.path.isfile(filepath):
                    _bad_files.append(filepath)
                    continue
                try:
                    self.session.add_file(filepath)
                except abcview.io.AbcViewError, e:
                    abcview.log.debug(str(e))
                    _bad_files.append(filepath)

        # display a warning for bad files, bail if all are bad
        if len(_bad_files) > 0:
            message('The follow files could not be loaded:\n{0}'.format('\n'.join(_bad_files)))

            if len(_bad_files) == len(self._load_files):
                self.viewer.setDisabled(False)
                return

        # convert the session items to gl objects
        io2gl(self.session, self.viewer)

        # item color range
        COLORS = abcview.style.gen_colors(COUNT)
        self.splash.progress.setMaximum(COUNT)

        # walk session looking for cameras and load them
        for index, item in enumerate(self.session.walk()):
            self.splash.setMessage('loading {0}'.format(item.name))

            if isinstance(item, (abcview.gl.GLCamera, abcview.gl.GLICamera)):
                self.viewer.add_camera(item)
                if item.loaded:
                    self.viewer.set_camera(item)

            # set display overrides
            else:
                if self._overrides.get('mode') is not None:
                    item.mode = self._overrides.get('mode')

                if not item.properties.get('color', None):
                    item.color = COLORS[index]

        # default frame range
        self.viewer.state.frames_per_second = self.session.frames_per_second
        self.viewer.state.min_frame = 0
        self.viewer.state.max_frame = 100
        self.time_slider.set_minimum(0)
        self.time_slider.set_maximum(100)

        # set the frame range from loaded files
        if len(self._load_files) == 1:
            if self._load_files[0].endswith(abcview.io.Session.EXT):
                self.set_frames_from_session(self.session)
            elif (self._load_files[0].endswith(abcview.io.Scene.EXT) and
                  self._overrides.get('mode') != abcview.io.Mode.OFF):
                self.set_frames_from_scene(self.session.items[0])

        # frame range overrides
        if self._overrides.get('frames_per_second'):
            fps = self._overrides.get('frames_per_second')
            self.viewer.state.frames_per_second = fps
            self.session.frames_per_second = fps
        if self._overrides.get('first_frame'):
            first_frame = self._overrides.get('first_frame')
            self.viewer.state.min_frame = first_frame
            self.time_slider.set_minimum(first_frame)
        if self._overrides.get('last_frame'):
            last_frame = self._overrides.get('last_frame')
            self.viewer.state.max_frame = last_frame
            self.time_slider.set_maximum(last_frame)
        if self._overrides.get('current_frame'):
            curr_frame = int(self._overrides.get('current_frame'))
            self.viewer.state.current_frame = curr_frame
            self.time_slider.set_value(curr_frame)

        # frame boundary adjustments
        if self.viewer.state.current_time < self.viewer.state.min_time:
            self.viewer.state.current_time = self.viewer.state.min_time
        elif self.viewer.state.current_time > self.viewer.state.max_time:
            self.viewer.state.current_time = self.viewer.state.max_time

        # create trees for top-level session items, load items last
        for item in self.session.items:
            tree = None
            if isinstance(item, abcview.io.Session):
                tree = abcview.widget.tree_widget.SessionTreeWidgetItem(self.objects_tree, item)
            elif isinstance(item, abcview.gl.GLScene):
                tree = abcview.widget.tree_widget.SceneTreeWidgetItem(self.objects_tree, item)
            if item.loaded and tree is not None:
                tree.load()
            item.tree = tree

        # frame the viewer if we're just loading one abc file
        if len(self._load_files) == 1 and self._load_files[0].endswith(abcview.io.Scene.EXT):
            self.viewer.frame()

        self.viewer.setDisabled(False)
        self.setWindowTitle('{0}: {1}'.format(self.TITLE, self.session.name))

    def _wait(self):
        """
        Waits for the window to be drawn before proceeding.
        """
        app = QtWidgets.QApplication.instance()
        while QtWidgets.QApplication.instance().startingUp():
            pass
        while not self.isVisible():
            pass

    def open_file(self, filepath):
        """
        File loader

        :param filepath: file path to load, replaces session
        """
        self.set_load_files([filepath])
        self._start()

    def import_file(self, filepath, overrides=None):
        """
        File importer

        :param filepath: file path to import, adds to session
        :param overrides: parameter overrides dict
        """
        self.viewer.setDisabled(True)

        if filepath.endswith(abcview.io.Session.EXT):
            item = abcview.io.Session(filepath)
            num_items = len(item.items)
            io2gl(item, self.viewer)
        elif filepath.endswith(abcview.io.Scene.EXT):
            item = abcview.gl.GLScene(filepath)
            num_items = 1

        # update item from params override
        if overrides:
            item.name = overrides.get('name', item.name)
            item.loaded = overrides.get('loaded', item.loaded)
            item.color = overrides.get('color', item.color)
            item.properties.update(overrides.get('properties'))

        self.session.add_item(item)
        COLORS = abcview.style.gen_colors(num_items)

        if self._overrides.get('mode') is not None:
            item.mode = self._overrides.get('mode')

        if isinstance(item, abcview.io.Session):
            item = abcview.widget.tree_widget.SessionTreeWidgetItem(self.objects_tree, item)
        elif isinstance(item, abcview.gl.GLScene):
            item = abcview.widget.tree_widget.SceneTreeWidgetItem(self.objects_tree, item)
        if item.object.loaded:
            item.load()

        self.viewer.setDisabled(False)

    @make_clean
    def save_session(self, filepath=None):
        """
        Saves the current AbcView session to  a given filepath, or
        to the current filepath if filepath is None.

        :param filepath: save to filepath (passing no args or None
                         overrwrites current session file.
        """
        try:
            self.session.min_time = self.viewer.state.min_time
            self.session.max_time = self.viewer.state.max_time
            self.session.current_time = self.viewer.state.current_time
            self.session.frames_per_second = self.viewer.state.frames_per_second
            self.session.save(filepath)
        except Exception, e:
            traceback.print_exc()
            message('Error saving file:\n\n{0}'.format(str(e)))

    def load_script(self, script):
        """
        Loads and executes a python AbcView script.

        :param script: code or path to file containing python code.
        """
        abcview.log.debug('[{0}.load_script] {1}'.format(self, script))
        if os.path.exists(script):
            self.console.runScript(script)
        else:
            self.console.setCommand(script)
            self.console.runCommand()

    ## event handlers

    def handle_play(self):
        """
        Playback handler, starts playing the viewer.
        """
        self.viewer.state.play()

    def handle_stop(self):
        """
        Viewer playback stop handler, stops the viewer playback.
        """
        self.viewer.state.stop()

    @make_dirty
    def handle_item_removed(self, item=None):
        self.viewer.state.stop()
        if item is None:
            item = self.objects_tree.selectedItems()[0]
        abcview.log.debug('[{0}].handle_item_removed: {1}'.format(self, item))
        self.viewer.remove_scene(item.object)
        self.session.remove_item(item.object)

    def handle_scene_opened(self, scene):
        """
        Scene open signal handler.
        """
        frame_range = self.viewer.state.frame_range()
        self.time_slider.set_minimum(frame_range[0])
        self.time_slider.set_maximum(frame_range[1])

    def handle_viewer_error(self, msg):
        message(msg)

    def handle_time_slider_change(self, frame):
        """
        handles frame changes coming from time slider

        :param frame: frame number
        """
        self.viewer.state.current_frame = frame

    def handle_first_frame_change(self, frame):
        """
        handles first frame change from time slider

        :param frame: frame number
        """
        self.viewer.state.min_frame = frame
        if self.session.frames_per_second > 0:
            self.session.min_time = frame / self.session.frames_per_second

    def handle_last_frame_change(self, frame):
        """
        handles last frame change from time slider

        :param frame: frame number
        """
        self.viewer.state.max_frame = frame
        if self.session.frames_per_second > 0:
            self.session.max_time = frame / self.session.frames_per_second

    def handle_state_play_fwd(self):
        """
        viewer state play foward signal handler
        """
        self.time_slider.playing = True

    def handle_state_play_stop(self):
        """
        viewer state play stop signal handler
        """
        self.time_slider.playing = False

    def handle_update_frame(self, frame):
        """
        handles frame changes coming from viewer
        """
        self.time_slider.set_value(frame)

        # update the samples tree selected item
        if not self.properties_splitter.isHidden() and \
            self.samples_tree.topLevelItemCount() > 0:
            p = self.properties_tree.selected()
            ts = p.getTimeSampling()
            t = self.time_slider.value() \
                    / float(self.viewer.state.frames_per_second)
            index = ts.getNearIndex(t, len(p.samples))
            item = self.samples_tree.topLevelItem(index)
            self.samples_tree.clearSelection()
            self.samples_tree.setItemSelected(item, True)
            self.samples_tree.scrollToItem(item)

    def handle_bad_scene(self, scene, frame):
        """
        Undrawabe scene signal handler.

        :param scene: abcview.gl.GLScene
        """
        scene.tree.set_bad(True)

    @make_dirty
    def handle_new_camera(self, camera):
        """
        handles adding a new camera to the session

        :param camera: abcview.gl.GLCamera
        """
        abcview.log.debug('[{0}.handle_new_camera] {1}'.format(self, camera))
        if camera.name != 'interactive':
            self.session.add_camera(camera)

    @make_dirty
    def handle_set_camera(self, camera):
        """
        handles setting the camera name on the session

        :param camera: abcview.gl.GLCamera
        """
        if camera.name != 'interactive':
            self.session.set_camera(camera)

    @make_dirty
    def handle_view_camera(self, item):
        """
        object tree 'view through selected' menu handler

        :param item: CameraTreeWidgetItem
        """
        icamera = item.camera()
        if icamera.getName() not in [c.name for c in self.viewer.state.cameras]:
            camera = abcview.gl.GLICamera(self.viewer, icamera)
            self.viewer.add_camera(camera)
            self.viewer.set_camera(camera.name)
        else:
            self.viewer.set_camera(icamera.getName())

    def handle_scene_selected(self, scene):
        """
        abcview.widget.viewer_widget.GLWidget scene selected handler.

        :param scene: abcview.gl.GLScene
        """
        abcview.log.debug('[{0}.handle_scene_selected] {1}'.format(self, scene))
        self.objects_tree.clearSelection()
        if scene:
            scene.tree.treeWidget().scrollToItem(scene.tree,
                             QtWidgets.QAbstractItemView.PositionAtCenter)
            scene.tree.treeWidget().setItemSelected(scene.tree, True)
            self.handle_object_clicked(scene.tree)

    @wait
    def handle_object_selected(self, name):
        """
        abcview.widget.viewer_widget.GLWidget object selected handler.

        :param name: name of object
        """
        abcview.log.debug('[{0}.handle_object_selected] {1}'.format(self, name))
        self.objects_tree.find(str(name.toAscii()))

    @wait
    def find(self, name):
        """
        searches for objects in the tree matching name
        """
        self.setFocus()
        self.objects_tree.find(name)

    @wait
    def handle_find(self, text=None):
        """
        handles input from the search box
        """
        if text is None:
            text = self.find_line_edit.text()
        if text:
            self.find(str(text.toAscii()))

    def handle_object_selection(self):
        for scene in self.viewer.state.scenes:
            scene.selected = False
        self.viewer.updateGL()

    def handle_item_selected(self, item):
        """
        item click handler

        :param item: SceneTreeWidgetItem, SessionTreeWidgetItem
        """
        if isinstance(item, abcview.widget.tree_widget.SceneTreeWidgetItem):
            item.object.selected = True
        self.viewer.updateGL()

    @wait
    def handle_item_loaded(self, item):
        """
        load checkbox click handler

        :param item: SceneTreeWidgetItem, SessionTreeWidgetItem
        """
        def load(item):
            if isinstance(item, abcview.widget.tree_widget.SceneTreeWidgetItem):
                self.viewer.add_scene(item.object)
            elif isinstance(item, abcview.widget.tree_widget.SessionTreeWidgetItem):
                for child in item.children():
                    load(child)
        abcview.log.debug('[{0}.handle_item_loaded] {1}'.format(self, item.object))
        self.splash.setMessage('loading {0}'.format(item.object.name))
        self.splash.updateProgress(self.splash.progress.value() + 1)
        load(item)

    @wait
    def handle_item_unloaded(self, item):
        """
        Item unloaded handler.

        :param item: ObjectTreeWidgetItem
        """
        self.viewer.remove_scene(item.object)

    def handle_object_clicked(self, item):
        """
        Object tree item clicked handler.

        :param item: ObjectTreeWidgetItem
        """
        self.samples_tree.clear()
        self.array_tree.clear()
        self.properties_tree.show_properties(item)

    @wait
    def handle_property_clicked(self, item):
        """
        Property tree item clicked handler.

        :param item: PropertyTreeWidgetItem
        """
        self.array_tree.clear()
        self.samples_tree.show_samples(item)

    @wait
    def handle_new(self):
        """
        File->New menu handler
        """
        self.clear()
        self.setWindowTitle(self.TITLE)

    @make_clean
    def handle_open(self):
        """
        File->Open menud handler
        """
        filepath = QtWidgets.QFileDialog.getOpenFileName(self,
                                                     'Open File',
                                                     os.getcwd(),
                                                     ('Alembic Files (*.%s *.{0})'.format((abcview.io.Scene.EXT,
                                                                                           abcview.io.Session.EXT))))
        if filepath:
            self.clear()
            self.set_load_files([str(filepath.toAscii())])
            self._load()

    @make_dirty
    def handle_import(self):
        """
        File->Import menud handler
        """
        filepath = QtWidgets.QFileDialog.getOpenFileName(self, 'Open File',
                    os.getcwd(), ('Alembic Files (*.{0} *.{1})'.format(abcview.io.Scene.EXT,
                                                                       abcview.io.Session.EXT)))
        if filepath:
            self.import_file(str(filepath.toAscii()))

    @make_clean
    def handle_reload(self):
        """
        File->Reload menu handler, reloads session
        """
        self.clear()
        self._load()

    def handle_frame_all(self):
        """
        Frame all.
        """
        abcview.log.debug('[{0}.handle_frame_all]'.format(self))
        self.viewer.frame()

    def handle_frame_scene(self, item):
        """
        Scene level framing handler.

        :param item: SceneTreeWidgetItem
        """
        abcview.log.debug('[{0}.handle_frame_scene] {1}'.format(self, item))
        bounds = item.object.bounds(self.viewer.state.current_time)
        self.viewer.frame(bounds)

    def handle_frame_object(self, item=None):
        """
        Object level framing handler. Called when a user types 'f' while
        the object tree widget has focus.

        :param item: ObjectTreeWidgetItem
        """
        abcview.log.debug('[{0}.handle_frame_object] {1}'.format(self, item))
        if item is None:
            obj = self.objects_tree.selected()
        else:
            obj = item.object
        if obj.getFullName() == '/':
            self.handle_frame_scene()
        md = obj.getMetaData()
        if alembic.AbcGeom.IPolyMesh.matches(md) or \
           alembic.AbcGeom.ISubD.matches(md):
            meshObj = alembic.AbcGeom.IPolyMesh(obj.getParent(), obj.getName())
            mesh = meshObj.getSchema()
            bounds_prop = mesh.getSelfBoundsProperty()
        elif alembic.AbcGeom.IXform.matches(md):
            meshObj = alembic.AbcGeom.IXform(obj.getParent(), obj.getName())
            mesh = meshObj.getSchema()
            bounds_prop = mesh.getChildBoundsProperty()
        else:
            return

        # get the final accumulated xform values
        xf = abcview.gl.get_final_matrix(meshObj)
        #iss = alembic.Abc.ISampleSelector(0)
        if not bounds_prop.valid():
            message('Object has invalid or no bounds set.')
            return

        # get the bounds value from the bounds property
        ts = bounds_prop.getTimeSampling()
        index = ts.getNearIndex(self.viewer.state.current_time,
                        bounds_prop.getNumSamples())
        bounds = bounds_prop.getValue(index) #iss)
        abcview.log.debug('bounds at index {0}: {1}'.format(index, bounds))

        #TODO: apply local transforms when framing
        if 0:
            min = bounds.min()
            max = bounds.max()
            item = self.objects_tree.selectedItems()[0]
            scene = item.scene().object
            if scene.properties.get('translate'):
                max = max * imath.V3d(*scene.translate)
                min = min * imath.V3d(*scene.translate)
            if scene.properties.get('scale'):
                max = max * imath.V3d(*scene.scale)
                min = min * imath.V3d(*scene.scale)
            bounds = imath.Box3d(min, max)

        self.viewer.frame(bounds * xf)

    def handle_save(self):
        if not self.session.filepath:
            self.handle_save_as()
        else:
            self.save_session()

    def handle_save_as(self):
        filepath = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File',
                    os.getcwd(), ('Alembic Files (*.{0})'.format(abcview.io.Session.EXT)))
        if filepath:
            self.save_session(str(filepath.toAscii()))

    ## base class overrides

    def resizeEvent(self, event):
        self.splash.move((event.size().width() / 2.0) - (self.splash.width() / 2.0),
                         (event.size().height() / 2.0) - (self.splash.height() / 2.0))
        super(AbcView, self).resizeEvent(event)

    def keyPressEvent(self, event):
        """
        Handles key press events for the main application. If nothing
        matches, it defers to the viewer.
        """
        if event.key() == QtCore.Qt.Key_F:
            if len(self.objects_tree.selectedItems()) == 0:
                self.handle_frame_all()
            else:
                item = self.objects_tree.selectedItems()[0]
                if isinstance(item, abcview.widget.tree_widget.SceneTreeWidgetItem):
                    self.handle_frame_scene(item)
                elif isinstance(item, abcview.widget.tree_widget.ObjectTreeWidgetItem):
                    self.handle_frame_object(item)
                else:
                    abcview.log.debug('Can\'t frame this object: {0}'.format(item))
        elif event.key() == QtCore.Qt.Key_Space:
            if self.time_slider.playing:
                self.handle_stop()
            else:
                self.handle_play()
        elif event.key() == QtCore.Qt.Key_Backspace:
            item = self.objects_tree.selectedItems()[0]
            self.handle_item_removed(item)
        else:
            self.viewer.keyPressEvent(event)

    def closeEvent(self, event):
        if self.session and self.session.is_dirty():
            resp = self.confirm_close('This session has changed.')
            if resp == QtWidgets.QMessageBox.Cancel:
                event.ignore()
                return
            elif resp == QtWidgets.QMessageBox.Save:
                self.handle_save()
        super(AbcView, self).closeEvent(event)

class App(QtWidgets.QApplication):
    """
    QApplication subclass that emits a 'startup' signal after
    the event loop has started. This may trigger deferred
    file loading, among other things.
    """

    SIGNAL_STARTING_UP = Signal()

    def __init__(self, args):
        super(App, self).__init__(args)
        # trigger the callback after the main event loop starts
        QtCore.QTimer.singleShot(1, self.starting)

    def starting(self):
        """
        Callback function for Timer timeout.
        """
        self.SIGNAL_STARTING_UP.emit()

def version_check():
    """
    Validates that alembic and alembicgl can be imported and
    that they meet the minimum requires versions.

    Current minimum version requirements for Alembic are 1.5.0.

    :return: 1 or 0
    """
    # Alembic minimum version requirement
    MAJOR = 1
    MINOR = 5
    MAINT = 0

    # validate the Alembic version
    version = alembic.Abc.GetLibraryVersionShort()
    major, minor, maint = version.split('.')
    if int(major) >= MAJOR and int(minor) >= MINOR:
        return 1
    else:
        print '{0} {1} requires Alembic {2}.{3}.{4} or greater'.format(abcview.config.__prog__,
                                                                       abcview.config.__version__,
                                                                       MAJOR,
                                                                       MINOR,
                                                                       MAINT)
        return 0

def create_app(files = None,
               first_frame = None,
               last_frame = None,
               current_frame = None,
               fps = None,
               script = None,
               bounds = False,
               mode = None,
               review = False,
               reset = False,
               verbose = False):
    """
    Creates a new instance of an :py:class:`.AbcView` application.

    :param files: list of files to load
    :param first_frame: set first frame
    :param last_frame: set last frame
    :param current_frame: set current frame
    :param fps: frames per second (default 24)
    :param script: python script to load
    :param bounds: force scene bounding box mode
    :param mode: default object draw mode
    :param review: use review settings
    :param reset: reset layout settings
    :param verbose: verbose standard out
    :return: exit code
    """
    assert version_check()

    # create application and widget
    app = App(sys.argv)
    win = AbcView()

    # verbosity
    if verbose:
        abcview.log.setLevel(logging.DEBUG)

    # settings
    if reset:
        win.reset_settings()
    elif review:
        win.review_settings()
    else:
        win.load_settings()

    # show widgets (Qt oddity this is done before event loop)
    win.show()
    win.raise_()

    # force scene bounds
    if bounds:
        win.set_default_mode(abcview.io.Mode.OFF)
        win.viewer.camera.mode = abcview.io.Mode.OFF
        win.viewer.camera.draw_bounds = 1
    elif mode is not None:
        win.set_default_mode(mode)

    # defer file loading until event loop starts
    win.set_load_files(files)

    # set frame range overrides
    if first_frame is not None:
        win.set_first_frame(first_frame)
    if last_frame is not None:
        win.set_last_frame(last_frame)
    if current_frame is not None:
        win.set_current_frame(current_frame)
    if fps:
        win.set_frames_per_second(fps)

    # execute some python
    if script:
        win.load_script(script)

    # start event loop
    return app.exec_()

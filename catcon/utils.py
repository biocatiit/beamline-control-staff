#! /usr/bin/env python
# coding: utf-8
#
#    Project: BioCAT staff beamline control software (CATCON)
#             https://github.com/biocatiit/beamline-control-staff
#
#
#    Principal author:       Jesse Hopkins
#
#    This is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this software.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, unicode_literals
from builtins import object, range, map
from io import open

import os
import time
import sys
import string

import wx
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg

def get_mxdir():
    """Gets the top level install directory for MX."""
    try:
        mxdir = os.environ["MXDIR"]
    except:
        mxdir = "/opt/mx"   # This is the default location.

    return mxdir

def get_mpdir():
    """Construct the name of the Mp modules directory."""
    mxdir = get_mxdir()

    mp_modules_dir = os.path.join(mxdir, "lib", "mp")
    mp_modules_dir = os.path.normpath(mp_modules_dir)

    return mp_modules_dir

def set_mppath():
    """Puts the mp directory in the system path, if it isn't already."""
    os.environ['PATH']

    mp_dir = get_mpdir()

    if mp_dir not in os.environ['PATH']:
        os.environ["PATH"] = mp_dir+os.pathsep+os.environ["PATH"]
    if mp_dir not in sys.path:
        sys.path.append(mp_dir)


def file_follow(the_file, stop_event):
    """
    This function follows a file that is continuously being written to and
    provides a generator that gives each new line written into the file.

    Modified from: http://www.dabeaz.com/generators/follow.py

    :param file the_file: The file object to read lines from.
    :param threading.Event stop_event: A stop event that will end the generator,
        allowing any loops iterating on the generator to exit.
    """
    while True:
        if stop_event.is_set():
            break
        line = the_file.readline()
        if not line:
            time.sleep(0.001)
            continue
        yield line

class CharValidator(wx.Validator):
    ''' Validates data as it is entered into the text controls. '''

    def __init__(self, flag):
        wx.Validator.__init__(self)
        self.flag = flag
        self.Bind(wx.EVT_CHAR, self.OnChar)

        self.fname_chars = string.ascii_letters+string.digits+'_-'

        self.special_keys = [wx.WXK_BACK, wx.WXK_DELETE,
            wx.WXK_TAB, wx.WXK_NUMPAD_TAB, wx.WXK_NUMPAD_ENTER]

    def Clone(self):
        '''Required Validator method'''
        return CharValidator(self.flag)

    def Validate(self, win):
        return True

    def TransferToWindow(self):
        return True

    def TransferFromWindow(self):
        return True

    def OnChar(self, event):
        keycode = int(event.GetKeyCode())
        if keycode < 256 and keycode not in self.special_keys:
            #print keycode
            key = chr(keycode)
            #print key
            if self.flag == 'int' and key not in string.digits:
                return
            elif self.flag == 'float' and key not in string.digits+'.':
                return
            elif self.flag == 'fname' and key not in self.fname_chars:
                return
            elif self.flag == 'float_te' and key not in string.digits+'.\n\r':
                return
            elif self.flag == 'float_neg' and key not in string.digits+'.-':
                return
            elif self.flag == 'float_neg_te' and key not in string.digits+'.-\n\r':
                return
        event.Skip()

class CustomPlotToolbar(NavigationToolbar2WxAgg):
    """
    A custom plot toolbar that displays the cursor position (or other text)
    in addition to the usual controls.
    """
    def __init__(self, canvas):
        """
        Initializes the toolbar.

        :param wx.Window parent: The parent window
        :param matplotlib.Canvas: The canvas associated with the toolbar.
        """
        NavigationToolbar2WxAgg.__init__(self, canvas)

        self.status = wx.StaticText(self, label='')

        self.AddControl(self.status)

    def set_status(self, status):
        """
        Called to set the status text in the toolbar, i.e. the cursor position
        on the plot.
        """
        self.status.SetLabel(status)

def set_best_size(window, shrink=False):

    best_size = window.GetBestSize()
    current_size = window.GetSize()

    client_display = wx.GetClientDisplayRect()

    best_width = min(best_size.GetWidth(), client_display.Width)
    best_height = min(best_size.GetHeight(), client_display.Height)

    if best_size.GetWidth() > current_size.GetWidth():
        best_size.SetWidth(best_width)
    else:
        if not shrink:
            best_size.SetWidth(current_size.GetWidth())
        else:
            best_size.SetWidth(best_width)

    if best_size.GetHeight() > current_size.GetHeight():
        best_size.SetHeight(best_height)
    else:
        if not shrink:
            best_size.SetHeight(current_size.GetHeight())
        else:
            best_size.SetHeight(best_height)

    window.SetSize(best_size)

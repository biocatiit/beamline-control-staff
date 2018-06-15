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

import wx

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
    path = os.environ['PATH']

    mp_dir = get_mpdir()

    if mp_dir not in path:
        os.environ["PATH"] = mp_dir+os.pathsep+os.environ["PATH"]

class FieldValueEntry(wx.TextCtrl):
    """
    Based on the ValueEntry in mpwx, but without callbacks. Meant to work
    when you want to change a field value that doesn't have a getter or setter.
    """
    def __init__( self, parent, record, field, **kwargs):
        self.record = record
        self.field = field

        if 'style' in kwargs:
            style = kwargs['style'] | wx.TE_PROCESS_ENTER
            del kwargs[style]
        else:
            style = wx.TE_PROCESS_ENTER

        wx.TextCtrl.__init__(self, parent, value=self.record.get_field(self.field),
            style=style, **kwargs)

        self.Bind(wx.EVT_TEXT, self.OnText)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)

    def OnText(self, event):
        self.SetBackgroundColour("yellow")

    def OnEnter(self, event):
        value = self.GetValue().strip()

        self.record.set_field(self.field, value)

        self.SetBackgroundColour(wx.NullColour)


def file_follow(thefile, stop_event):
    """Modified from: http://www.dabeaz.com/generators/follow.py"""
    while True:
        if stop_event.is_set():
            break
        line = thefile.readline()
        if not line:
            time.sleep(0.001)
            continue
        yield line

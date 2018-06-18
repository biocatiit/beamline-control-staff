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

import wx

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
import MpWx as mpwx
import MpWxCa as mpwxca


class FuncValueEntry(wx.TextCtrl):
    """
    Based on the ValueEntry in mpwx, but without callbacks. Meant to work
    when the mp record itself has a get/set function, like get/set speed
    for motors.
    """
    def __init__( self, parent, record, getter, setter, **kwargs):

        if 'style' in kwargs:
            style = kwargs['style'] | wx.TE_PROCESS_ENTER
            del kwargs[style]
        else:
            style = wx.TE_PROCESS_ENTER

        wx.TextCtrl.__init__(self, parent, value=getter(), style=style, **kwargs)

        self.record = record
        self.getter = getter
        self.setter = setter

        self.Bind(wx.EVT_TEXT, self.OnText)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)

    def OnText(self, event):
        self.SetBackgroundColour("yellow")

    def OnEnter(self, event):
        value = self.GetValue().strip()

        self.setter(value)

        self.SetBackgroundColour(wx.NullColour)


class CustomEpicsValue(wx.StaticText):

    def __init__(self, parent, pv_name, function, scale, offset, id=-1,
        pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
        name=wx.StaticTextNameStr, base=None):

        wx.StaticText.__init__(self, parent, id=id, label="-----", pos=pos,
            size=size, style=style, name=name )

        if base != 10 and base != 16 and base != 8 and base != None:
            error_message = "Only base 8, 10, and 16 are supported."
            raise ValueError, error_message

        self.base = base
        self.pv = mpca.PV(pv_name)

        mpwxca.EVT_UPDATE(self, self.OnUpdate)

        args = (self.pv, self, scale, offset)

        self.callback = self.pv.add_callback( mpca.DBE_VALUE, function, args )

        try:
            self.pv.caget()
            function(self.callback, args)
        except mp.Not_Found_Error:
            self.SetValue("NOT FOUND")
            self.Enable(False)
            return

        mpca.poll()

        self.SetForegroundColour("blue")

    def OnUpdate(self, event):
        value = event.args

        self.SetLabel(value)
        self.SetSize(self.GetBestSize())

class CustomEpicsValueEntry(wx.TextCtrl):

    def __init__(self, parent, pv_name,function, scale, offset, id=-1,
        pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
        name=wx.TextCtrlNameStr, validator=wx.DefaultValidator):

        # Adding wx.TE_PROCESS_ENTER to the style causes the
        # widget to generate wx.EVT_TEXT_ENTER events when
        # the Enter key is pressed.

        style = style | wx.TE_PROCESS_ENTER

        wx.TextCtrl.__init__(self, parent, id=id, value=wx.EmptyString,
            pos=pos, size=size, style=style, validator=validator)

        self.pv = mpca.PV(pv_name)
        self.scale = scale
        self.offset = offset

        mpwxca.EVT_UPDATE(self, self.OnUpdate)

        args = (self.pv, self, self.scale, self.offset)

        self.callback = self.pv.add_callback(mpca.DBE_VALUE, function, args)

        # Test for the existence of the PV.

        try:
            self.pv.caget()
        except mp.Not_Found_Error:
            self.SetValue("NOT FOUND")
            self.Enable(False)
            return

        # Disable the widget if the PV is read only.

        read_only = False

        if read_only:
            self.Enable(False)

        mpca.poll()

        self.Bind(wx.EVT_TEXT, self.OnText)

        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)

    def OnText(self, event):
        self.SetBackgroundColour("yellow")

    def OnEnter(self, event):
        value = float(self.GetValue().strip())
        value = str((value-self.offset)/self.scale)
        self.pv.caput(value, wait=False)
        self.SetBackgroundColour(wx.NullColour)

    def OnUpdate(self, event):
        value = event.args
        self.SetValue(value)
        self.SetBackgroundColour(wx.NullColour)


def on_epics_limit(callback, args):
    pv, widget = args
    value = pv.get_local()

    if value == 1:
        msg = str("Software limit hit for motor '{}'".format(widget.motor_name))
        wx.CallAfter(wx.MessageBox, msg, 'Error moving motor')

def network_value_callback(nf, widget, args, value):

    scale, offset = args

    if isinstance(value, list):
        if len(value) == 1:
            value = value[0]

    value = value*scale+offset

    if widget.base == 10:
        value = "%d" % value
    elif widget.base == 16 :
        value = "%#x" % value
    elif widget.base == 8 :
        value = "%#o" % value
    else:
        value = str(round(value, 4))

    widget.SetLabel(value)
    widget.SetSize(widget.GetBestSize())
    widget.Refresh()

def epics_value_callback(callback, args):

    pv, widget, scale, offset = args

    value = pv.get_local()

    if isinstance(value, list):
        if len(value) == 1:
            value = value[0]

    value = value*scale+offset

    if isinstance(widget, CustomEpicsValue):
        if widget.base == 10:
            value = "%d" % value
        elif widget.base == 16:
            value = "%#x" % value
        elif widget.base == 8:
            value = "%#o" % value
        else:
            value = str(round(value, 4))
    else:
        value = str(round(value, 4))

    wx.PostEvent(widget, mpwxca.UpdateEvent(value))
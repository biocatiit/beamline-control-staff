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
import MpWx as mpwx
import MpCa as mpca
import MpWxCa as mpwxca


def network_value_callback(nf, widget, args, value):
    """
    This is a callback function that sets the value of an MX network variable.
    It is modified from the one in :mod:`MpWx` to use the local record scale
    and offset.
    """
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

def limit_network_value_callback(nf, widget, args, value):
    """
    This is a callback function that sets the value of an MX network variable.
    It is modified from the one in :mod:`MpWx` to use the local record scale
    and offset.
    """

    local_scale, local_offset, remote_scale, remote_offset = args

    if isinstance(value, list):
        if len(value) == 1:
            value = value[0]

    value = value*remote_scale+remote_offset
    value = value*local_scale+local_offset

    value = str(round(value, 4))

    widget.SetValue(value)
    widget.SetBackgroundColour( wx.NullColour )
    widget.Refresh()


class CustomLimitValueEntry(mpwx.ValueEntry):

    def __init__(self, parent, server_record=None, field_name=None, nf=None,
        function=None, args=None, id=-1, pos=wx.DefaultPosition,
        size=wx.DefaultSize, style=0, name=wx.TextCtrlNameStr,
        validator=wx.DefaultValidator):

        # Adding wx.TE_PROCESS_ENTER to the style causes the
        # widget to generate wx.EVT_TEXT_ENTER events when
        # the Enter key is pressed.

        style = style | wx.TE_PROCESS_ENTER

        super(CustomLimitValueEntry, self).__init__(parent, 
            server_record=server_record, field_name=field_name, nf=nf,
        function=function, args=args, id=id, pos=pos,
        size=size, style=style, name=name,
        validator=validator)

        # Grab scaling values from callback args
        self.local_scale, self.local_offset, self.remote_scale, self.remote_offset = args

    def OnText(self, event):
        self.SetBackgroundColour( "yellow" )

    def OnEnter(self, event):
        print('in onenter')
        value = self.GetValue().strip()

        value = float(value)
        value = (value-self.local_offset)/self.local_scale
        value = (value-self.remote_offset)/self.remote_scale
        value = int(round(value))

        self.nf.put(str(value))

        self.SetBackgroundColour(wx.NullColour)
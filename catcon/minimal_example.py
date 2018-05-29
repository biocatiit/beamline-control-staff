#! /usr/bin/env mpscript

from __future__ import absolute_import, division, print_function, unicode_literals
from builtins import object, range, map
from io import open

import wx

import Mp as mp
import MpWx as mpwx


class MainFrame(wx.Frame):

    def __init__(self, mx_db, *args, **kwargs):
        wx.Frame.__init__(self, None, *args, **kwargs)

        self.mx_db = mx_db
        self.controls = [{'rows':1, 'cols':2, 'title':'test'}, [u'mtr1', u'Motor']]

        self._create_layout()

        self.mx_timer = wx.Timer()
        self.mx_timer.Bind(wx.EVT_TIMER, self._on_mxtimer)

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

        self.mx_timer.Start(100)

    def _create_layout(self):
        test_btn = wx.Button(self, label='Open control')
        test_btn.Bind(wx.EVT_BUTTON, self._on_showctrls)

        top_sizer = wx.BoxSizer()
        top_sizer.Add(test_btn)

        self.SetSizer(top_sizer)

    def _on_mxtimer(self, evt):
        """
        Called on the mx_timer, refreshes mx values in the GUI by calling
        wait_for_messages on the database.
        """
        self.mx_db.wait_for_messages(0.01)

    def _on_closewindow(self, evt):
        self.mx_timer.Stop()
        self.Destroy()

    def _on_showctrls(self, evt):
        self.mx_timer.Stop()
        ctrl_frame = CtrlsFrame(self.controls, self.mx_db, parent=self)
        ctrl_frame.Show()
        self.mx_timer.Start()

    def start_timer(self):
        self.mx_timer.Start()


class CtrlsFrame(wx.Frame):
    def __init__(self, ctrls, mx_db, *args, **kwargs):
        wx.Frame.__init__(self, title=ctrls[0]['title'], *args, **kwargs)

        self._create_layout(ctrls, mx_db)

        self.Fit()
        self.Raise()

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

    def _create_layout(self, ctrls, mx_db):
        settings = ctrls[0]
        ctrls = ctrls[1:]

        grid_sizer = wx.FlexGridSizer(rows=settings['rows'], cols=settings['cols'],
            hgap=2, vgap=2)

        for i in range(settings['cols']):
            grid_sizer.AddGrowableCol(i)

        for ctrl_name, ctrl_type in ctrls:
            ctrl_panel = MotorPanel(ctrl_name, mx_db, self)
            box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='{} Control'.format(ctrl_name)))
            box_sizer.Add(ctrl_panel)
            grid_sizer.Add(box_sizer, flag=wx.EXPAND)

        self.SetSizer(grid_sizer)

    def _on_closewindow(self, evt):
        main_frame = self.GetParent()
        main_frame.mx_timer.Stop()
        wx.CallLater(1000, main_frame.start_timer)
        self.Destroy()


class MotorPanel(wx.Panel):
    """
    .. todo::
        Eventually this should allow viewing (and setting?) of the motor
        settings, ideally through a generic GUI that works for various
        types of devices, not just motors.

    This motor panel supports standard motor controls, such as moving to a fixed
    position, redefining the current position value, and relative moves.
    It is mean to be embedded in a larger application, and can be instanced
    several times, once for each motor. It communicates with the motors by
    calling ``Mp``, the python wrapper for ``MX``.
    """
    def __init__(self, motor_name, mx_database, parent, panel_id=wx.ID_ANY,
        panel_name=''):
        """
        Initializes the custom panel. Important parameters here are the
        ``motor_name``, and the ``mx_database``.

        :param str motor_name: The motor name in the Mx database.

        :param Mp.RecordList mx_database: The database instance from Mp.

        :param wx.Window parent: Parent class for the panel.

        :param int panel_id: wx ID for the panel.

        :param str panel_name: Name for the panel.
        """
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self.mx_database = mx_database
        self.motor_name = motor_name
        self.motor = self.mx_database.get_record(self.motor_name)
        server_record_name = self.motor.get_field("server_record")
        self.server_record = self.mx_database.get_record(server_record_name)
        self.remote_record_name = self.motor.get_field("remote_record_name")

        top_sizer = self._create_layout()

        self.SetSizer(top_sizer)

    def _create_layout(self):
        """
        Creates the layout for the panel.

        :returns: wx Sizer for the panel.
        :rtype: wx.Sizer
        """
        pos_name = "{}.position".format(self.remote_record_name)
        pos = mpwx.Value(self, self.server_record, pos_name)


        status_grid = wx.GridBagSizer(vgap=2, hgap=2)
        status_grid.Add(wx.StaticText(self, label='Motor name:'), (0,0))
        status_grid.Add(wx.StaticText(self, label=self.motor.name), (0,1), span=(1,2), flag=wx.EXPAND)
        status_grid.Add(wx.StaticText(self, label='Current position:'), (1,0))
        status_grid.Add(pos, (1,1), flag=wx.EXPAND)
        status_grid.Add(wx.StaticText(self, label=self.motor.get_field('units')), (1,2))
        status_grid.AddGrowableCol(1)

        status_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Info'),
            wx.VERTICAL)
        status_sizer.Add(status_grid, 1, flag=wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(status_sizer, flag=wx.EXPAND)

        return top_sizer

def main(mx_db, args):
    app = wx.App(0)   #MyApp(redirect = True)
    frame = MainFrame(mx_db, title='BioCAT Staff Controls', name='MainFrame')
    frame.Show()
    app.MainLoop()

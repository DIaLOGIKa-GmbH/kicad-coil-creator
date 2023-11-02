import os
import sys
import time
import tempfile
import logging

import wx # type: ignore
import pcbnew # type: ignore

from .menu import *

# WX GUI form that show coil settings
class CoilGeneratorUI(wx.Frame):
	def __init__(self, pcbnew_frame):
		super(CoilGeneratorUI, self).__init__()

		self.width_label = 120
		self.width_content = 180
		self.padding = 5

		self._init_logger()
		self.logger = logging.getLogger(__name__)
		self.logger.log(logging.DEBUG, "Running Coil Generator")

		self._pcbnew_frame = pcbnew_frame

		wx.Dialog.__init__(
			self,
			None,
			id = wx.ID_ANY,
			title = u"Coil Generator",
			pos = wx.DefaultPosition,
			size = wx.DefaultSize,
			style = wx.DEFAULT_DIALOG_STYLE
		)

		self.sizer_box = wx.BoxSizer(wx.VERTICAL)

		# self.app = wx.PySimpleApp()
		icon = wx.Icon(os.path.join(os.path.dirname(__file__), 'icon.png'))
		self.SetIcon(icon)
		self.SetBackgroundColour(wx.LIGHT_GREY)

		for entry in menu_structure:
			if entry["type"] == "choices":
				self._make_choices(entry["label"], entry["choices"], entry["default"], entry["unit"])
				self.logger.log(logging.DEBUG, "[UI] Adding Choices")

			if entry["type"] == "checkbox":
				self._make_checkbox(entry["label"], entry["default"], entry["unit"])
				self.logger.log(logging.DEBUG, "[UI] Adding Checkbox")

			if entry["type"] == "slider":
				self._make_slider(entry["label"], entry["min"], entry["max"], entry["default"], entry["unit"])
				self.logger.log(logging.DEBUG, "[UI] Adding Slider")

			if entry["type"] == "text":
				self._make_textbox(entry["label"], entry["default"], entry["unit"])
				self.logger.log(logging.DEBUG, "[UI] Adding Textfield")

			self.logger.log(logging.DEBUG, entry)

		elem_button_generate = wx.Button(self, label="Generate Coil")
		elem_button_generate.Bind(wx.EVT_BUTTON, self._on_generate_button_lick)

		self.sizer_box.Add(elem_button_generate, 0, wx.ALL, self.padding)

		self.SetSizer(self.sizer_box)
		self.Layout()
		self.sizer_box.Fit(self)
		self.Centre(wx.BOTH)

	def _make_choices(self, label, choices, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_choices = wx.Choice(self, choices=choices)

		elem_choices.SetSelection(default)

		self._add_content(
			elem_label,
			elem_choices,
			unit
		)

	def _make_checkbox(self, label, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_check = wx.CheckBox(self)

		self._add_content(
			elem_label,
			elem_check,
			unit
		)

	def _make_slider(self, label, min, max, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_slider = wx.Slider(self, value = 50, minValue = min, maxValue = max, style = wx.SL_HORIZONTAL | wx.SL_LABELS)

		self._add_content(
			elem_label,
			elem_slider,
			unit
		)

	def _make_textbox(self, label, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_text = wx.TextCtrl(self)

		elem_text.SetValue(str(default))

		self._add_content(
			elem_label,
			elem_text,
			unit
		)

	def _add_content(self, elem_label, elem_content, unit):
		elem_label.SetMinSize((self.width_label, -1))
		elem_content.SetMinSize((self.width_content, -1))

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(elem_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, self.padding)
		sizer.Add(elem_content, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, self.padding)

		if unit:
			unit_label = wx.StaticText(self, label=unit)

			# decrease the content box size:
			elem_content.SetMinSize((self.width_content - unit_label.GetSize().GetWidth() - 2 * self.padding, -1))

			sizer.Add(unit_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, self.padding)

		self.sizer_box.Add(sizer, 0, wx.ALL, self.padding)

	def _on_generate_button_lick(self, event):
		self.Destroy()

		# todo placeholder		
		path = os.path.dirname(__file__)
		file = os.path.join(path, "COIL_GENERATOR_1.kicad_mod")

		self.logger.log(logging.DEBUG, "reading file...")

		with open(file, "r") as file:
			template = file.read()
		self.logger.log(logging.DEBUG, "read file")

		# copy the generated footprint into clipboard
		clipboard = wx.Clipboard.Get()
		if clipboard.Open():
			self.logger.log(logging.DEBUG, "Adding to clipboard")

			clipboard.SetData(wx.TextDataObject(template))
			clipboard.Close()
		else:                    
			self.logger.log(logging.DEBUG, "Clipboard error")

			return
		
		# paste generated foodprint into the pcbview
		try:
			evt = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
			evt.SetKeyCode(ord('V'))
			evt.SetControlDown(True)
			self.logger.log(logging.INFO, "Using wx.KeyEvent for paste")
	
			wnd = [i for i in self._pcbnew_frame.Children if i.ClassName == 'wxWindow'][0]

			self.logger.log(logging.INFO, "Injecting event: {} into window: {}".format(evt, wnd))
			wx.PostEvent(wnd, evt)
		except:
			# Likely on Linux with old wx python support :(
			self.logger.log(logging.INFO, "Using wx.UIActionSimulator for paste")
			keyinput = wx.UIActionSimulator()
			self._pcbnew_frame.Raise()
			self._pcbnew_frame.SetFocus()
			wx.MilliSleep(100)
			wx.Yield()
			# Press and release CTRL + V
			keyinput.Char(ord("V"), wx.MOD_CONTROL)
			wx.MilliSleep(100)

	def _init_logger(self):
		root = logging.getLogger()
		root.handlers.clear()
		root.setLevel(logging.DEBUG)

		log_path = os.path.dirname(__file__)
		log_file = os.path.join(log_path, "coilgenerator.log")

		handler = logging.FileHandler(log_file)
		handler.setLevel(logging.DEBUG)

		formatter = logging.Formatter(
			"%(asctime)s %(name)s %(lineno)d:%(message)s", datefmt="%m-%d %H:%M:%S"
		)

		handler.setFormatter(formatter)

		root.addHandler(handler)

# use this class to track the last focused page
class FocusTracker(wx.EvtHandler):
	def __init__(self):
		wx.EvtHandler.__init__(self)
		self.prev_focused_window = None

	def OnFocus(self, event):
		self.prev_focused_window = event.GetEventObject()

# Plugin definition
class Plugin(pcbnew.ActionPlugin):
	def __init__(self):
		self.name = "Coil Generator"
		self.category = "Manufacturing"
		self.description = "Toolkit to automatically generate coils for KiCad"
		self.pcbnew_icon_support = hasattr(self, "show_toolbar_button")
		self.show_toolbar_button = True
		self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')
		self.dark_icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')

		self.focus_tracker = FocusTracker()

		# if a window loses focus, this event updates the last focused window
		for window in wx.GetTopLevelWindows():
			window.Bind(wx.EVT_SET_FOCUS, self.focus_tracker.OnFocus)
			
	def Run(self):
		CoilGeneratorUI(self.focus_tracker.prev_focused_window).Show()

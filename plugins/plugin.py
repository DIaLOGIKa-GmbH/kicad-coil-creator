import os
import logging
import json
import math

import wx # type: ignore
import pcbnew # type: ignore

from .lib import menu
from .lib import coilgenerator

# WX GUI form that show coil settings
class CoilGeneratorUI(wx.Frame):
	def __init__(self, pcbnew_frame):
		super(CoilGeneratorUI, self).__init__()

		self.width_label = 120
		self.width_content = 180
		self.padding = 5

		self.board = pcbnew.GetBoard()
		self.path_project = os.path.dirname(self.board.GetFileName())
		self.path_footprint_folder_name = "/pcb_coils/"
		self.path_footprint_folder = self.path_project + self.path_footprint_folder_name
		self.path_fp_lib_table = self.path_project + "/fp-lib-table"

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

		self._prepare_defaults_from_cached_settings(menu.structure)

		for entry in menu.structure:
			if entry["type"] == "choices" or entry["type"] == "choices_from_board":

				# if choice structure values are sourced from board variables, some fields need to be dynamically generated before applying general choice handling
				if entry["type"] == "choices_from_board":
					if entry["choices_source"] == "COPPER_LAYER_COUNT":
						entries_str = [str(e) for e in range(1, pcbnew.GetBoard().GetCopperLayerCount()+1)]
						entries = [e for e in range(1, pcbnew.GetBoard().GetCopperLayerCount()+1)]
						entry["choices"] = entries_str
						entry["choices_data"] = entries

				entry["wx_elem"] = self._make_choices(entry["label"], entry["choices"], entry["default"], entry["unit"])
				self.Bind(wx.EVT_CHOICE, self._on_choice_change, entry["wx_elem"])
				self.logger.log(logging.DEBUG, "[UI] Adding Choices")

			if entry["type"] == "checkbox":
				entry["wx_elem"] = self._make_checkbox(entry["label"], entry["default"], entry["unit"])
				self.Bind(wx.EVT_CHECKBOX, self._on_value_change, entry["wx_elem"])
				self.logger.log(logging.DEBUG, "[UI] Adding Checkbox")

			if entry["type"] == "slider":
				entry["wx_elem"] = self._make_slider(entry["label"], entry["min"], entry["max"], entry["default"], entry["unit"])
				self.Bind(wx.EVT_SCROLL, self._on_value_change, entry["wx_elem"])
				self.logger.log(logging.DEBUG, "[UI] Adding Slider")

			if entry["type"] == "text":
				entry["wx_elem"] = self._make_textbox(entry["label"], entry["default"], entry["unit"])
				self.Bind(wx.EVT_TEXT, self._on_value_change, entry["wx_elem"])
				self.logger.log(logging.DEBUG, "[UI] Adding Textfield")

			self.logger.log(logging.DEBUG, entry)

		self.Bind(wx.EVT_CHAR_HOOK, self._on_key_up)

		self.notes = self._make_label(label="")
		self.notes.SetForegroundColour((255, 0, 0, 255))
		self.logger.log(logging.DEBUG, "[UI] Adding Label")

		self.elem_button_generate = wx.Button(self, label="Generate Coil")
		self.elem_button_generate.Bind(wx.EVT_BUTTON, self._on_generate_button_klick)

		self.elem_button_save = wx.Button(self, label="Save as Project Footprint")
		self.elem_button_save.Bind(wx.EVT_BUTTON, self._on_save_button_klick)


		self.sizer_box.Add(self.elem_button_generate, 0, wx.ALL, self.padding)
		self.sizer_box.Add(self.elem_button_save, 0, wx.ALL, self.padding)

		self.SetSizer(self.sizer_box)
		self.Layout()
		self.sizer_box.Fit(self)
		self.Centre(wx.BOTH)

		self.update_coil_generation_notes()

	def _on_choice_change(self, event):
		identifier = ""

		for entry in menu.structure:
			if entry["wx_elem"] == event.GetEventObject():
				identifier = entry["id"]

		self.update_coil_generation_notes()
		self._update_cached_setting(identifier, event.GetEventObject().GetSelection())

	def _on_value_change(self, event):
		identifier = ""

		for entry in menu.structure:
			if entry["wx_elem"] == event.GetEventObject():
				identifier = entry["id"]

		self.update_coil_generation_notes()
		self._update_cached_setting(identifier, event.GetEventObject().GetValue())

	def _make_choices(self, label, choices, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_choices = wx.Choice(self, choices=choices)

		elem_choices.SetSelection(default)

		self._add_content(
			elem_label,
			elem_choices,
			unit
		)

		return elem_choices

	def _make_checkbox(self, label, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_check = wx.CheckBox(self)

		elem_check.SetValue(default)

		self._add_content(
			elem_label,
			elem_check,
			unit
		)

		return elem_check

	def _make_slider(self, label, min, max, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_slider = wx.Slider(self, value = 50, minValue = min, maxValue = max, style = wx.SL_HORIZONTAL | wx.SL_LABELS)

		elem_slider.SetValue(default)

		self._add_content(
			elem_label,
			elem_slider,
			unit
		)

		return elem_slider

	def _make_label(self, label):
		elem_label = wx.StaticText(self, label=label)
		self.sizer_box.Add(elem_label, 0, wx.ALL, self.padding)

		return elem_label

	def _make_textbox(self, label, default = 0, unit = None):
		elem_label = wx.StaticText(self, label=label)
		elem_text = wx.TextCtrl(self)

		elem_text.SetValue(str(default))

		self._add_content(
			elem_label,
			elem_text,
			unit
		)

		return elem_text

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

	def _parse_data(self, identifier):
		self.logger.log(logging.INFO, "Finding value for: " + identifier)
		for entry in menu.structure:
			if entry["id"] != identifier:
				continue

			self.logger.log(logging.INFO, "Located element, extracting data...")

			val = None

			if entry["type"] == "choices" or entry["type"] == "choices_from_board":
				val = entry["choices_data"][entry["wx_elem"].GetSelection()]
			elif entry["type"] == "checkbox":
				val = entry["wx_elem"].GetValue()
			elif entry["type"] == "slider":
				val = entry["wx_elem"].GetValue()
			elif entry["type"] == "text":
				val = entry["wx_elem"].GetValue()

			self.logger.log(logging.INFO, "Raw data: " + str(val))

			if entry["datatype"] == "float":
				return float(val)
			elif entry["datatype"] == "int":
				return int(val)
			elif entry["datatype"] == "bool":
				return bool(val)
			else:
				return str(val)

	def _update_cached_setting(self, identifier, value):
		cache_file = os.path.join(os.path.dirname(__file__), "dynamic/lastconfig.json")

		with open(cache_file, "r") as file:
			data = json.load(file)

		data[identifier] = value

		with open(cache_file, "w") as file:
			json.dump(data, file, indent=4)

	def _prepare_defaults_from_cached_settings(self, menu_array):
		cache_file = os.path.join(os.path.dirname(__file__), "dynamic/lastconfig.json")

		with open(cache_file, "r") as file:
			data = json.load(file)

		for entry in menu_array:
			try:
				id = entry["id"]
				thisdefault = data[id]
				entry["default"] = thisdefault
			except KeyError:
				continue

	def _handle_coil_generation(self):
		self.Destroy()

		self.logger.log(logging.INFO, "Generating coil ...")
		layer_names = [pcbnew.GetBoard().GetLayerName(x) for x in range(pcbnew.GetBoard().GetCopperLayerCount())]
		# last layer in layer list should always be B.Cu, but if board layer count != max_layer_count, pcbnew reports InX.Cu as last layer name
		layer_names[pcbnew.GetBoard().GetCopperLayerCount() -1] = "B.Cu"

		template = coilgenerator.generate(
			self._parse_data("layer_count"),
			self._parse_data("turn_direction"),
			self._parse_data("turns_count"),
			self._parse_data("trace_width"),
			self._parse_data("trace_spacing"),
			self._parse_data("via_outer"),
			self._parse_data("via_drill"),
			self._parse_data("outer_diameter"),
			self._parse_data("name"),
			layer_names
		)

		self.logger.log(logging.INFO, "Done.")

		return template
	
	def _add_to_fp_lib(self):
		entry = "  (lib (name \"PCB Coils\")"
		entry += "(type \"KiCad\")"
		entry += "(uri \"${KIPRJMOD}" + self.path_footprint_folder_name + "\")"
		entry += "(options \"\")"
		entry += "(descr \"auto-generated coil footprints\"))"

		if os.path.exists(self.path_fp_lib_table):
			# Read the existing content of fp-lib-table
			with open(self.path_fp_lib_table, "r") as file:
				lines = file.readlines()


			# Find the position of the closing bracket
			closing_bracket_index = None
			for i, line in enumerate(lines):
				if line.strip() == ")":
					closing_bracket_index = i

					break

			# Insert the new entry just before the closing bracket
			if closing_bracket_index is not None:
				lines.insert(closing_bracket_index, entry)

			self.logger.log(logging.INFO, "Inserted into footprint library file")
		else:
			lines = [
				"(fp_lib_table\n",
  				"  (version 7)\n",
				entry + "\n",
				")\n"
			]

			self.logger.log(logging.INFO, "Creating new footprint library file")

		# Write the modified content back to the file
		with open(self.path_fp_lib_table, "w") as file:
			file.writelines(lines)
			file.close()

		# reload footprints not really possible?
		pcbnew.Refresh() # Refresh the user interface

	def _on_save_button_klick(self, event):
		template = self. _handle_coil_generation()

		# if the folder does not exist yet, it should be created and added to
		# the project library path
		if not os.path.exists(self.path_footprint_folder):
			os.makedirs(self.path_footprint_folder)

			self._add_to_fp_lib()

			self.logger.log(logging.INFO, "Created new footprint folder, added to project library")
		else:
			self.logger.log(logging.INFO, "Footprint folder already exists")

		with open(self.path_footprint_folder + get_safe_name(self._parse_data("name")) + ".kicad_mod", "w") as file:
			file.write(template)
			file.close()

	def _on_generate_button_klick(self, event):
		template = self. _handle_coil_generation()

		# copy the generated footprint into clipboard
		clipboard = wx.Clipboard.Get()
		if clipboard.Open():
			self.logger.log(logging.DEBUG, "Adding to clipboard")

			clipboard.SetData(wx.TextDataObject(template))
			clipboard.Close()
		else:                    
			self.logger.log(logging.DEBUG, "Clipboard error")

			return
		
		# paste generated footprint into the pcbview
		try:
			evt = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
			evt.SetKeyCode(ord('V'))
			evt.SetControlDown(True)
			self.logger.log(logging.INFO, "Using wx.KeyEvent for paste")
		
			wx.PostEvent(self._pcbnew_frame, evt)
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

	def _on_key_up(self, event):
		key_code = event.GetKeyCode()
		modifiers = event.GetModifiers()

		if key_code == wx.WXK_ESCAPE:
			self.Close()

			return
		elif key_code == key_code == wx.WXK_RETURN and modifiers == wx.MOD_CONTROL:
			self._on_generate_button_klick(event)

			return

		event.Skip()

	def _init_logger(self):
		root = logging.getLogger()
		root.handlers.clear()
		root.setLevel(logging.DEBUG)

		log_file = os.path.join(os.path.dirname(__file__), "dynamic/coilgenerator.log")

		handler = logging.FileHandler(log_file)
		handler.setLevel(logging.DEBUG)

		formatter = logging.Formatter(
			"%(asctime)s %(name)s %(lineno)d:%(message)s", datefmt="%m-%d %H:%M:%S"
		)

		handler.setFormatter(formatter)

		root.addHandler(handler)

	def update_coil_generation_notes(self):
		"""
		Checks if a coil is generatable and places notes on form / generation errors.
		To be called on form value changes
		"""
		try:
			self.elem_button_generate.Enable()
			self.elem_button_save.Enable()

			if self._parse_data("via_outer") < self._parse_data("via_drill"):
				self.notes.SetLabel("WARNING: Via drill is greater than outer diameter")
			elif not self.estimate_is_coil_generatable(
				self._parse_data("outer_diameter"),
				self._parse_data("turns_count"),
				self._parse_data("trace_width"),
				self._parse_data("trace_spacing"),
				self._parse_data("via_outer"),
				self._parse_data("layer_count")
				):
				self.notes.SetLabel("WARNING: This coil MAY not be generatable.")
			else:
				self.notes.SetLabel("")
		except:
			self.notes.SetLabel("One or more entries contain invalid values")
			self.elem_button_generate.Disable()
			self.elem_button_save.Disable()

	def estimate_is_coil_generatable(self, outer_diameter, turns_per_layer, trace_width, trace_spacing, via_diameter, layer_count):
		"""
		Checks if a coil is generatable.
		If this returns true, the coil is likely to be fault free.
		If this return false, the coil is likely to be faulty.
		Checks are ESTIMATES only
		Checks this by checking inner via placement
		Args:
			outer_diameter: Desires outer coil diameter. Coil generation is from outside to inside, so if this is too small, coil wraps may collode
			turns_per_layer: Minimum number of turns per layer: Connecting to vias might introduce up to one more turn
			trace_width: Width of line trace
			trace_spacing: Distance between line traces
			via_diameter: Outer diameter of connecting vias
			layer_count: Number of layers in coil

		Returns:
			Bool: False, if coil is definitely not generatable, True, if coil MAY be generatable
		"""
		(via_inner_diameter, _) = coilgenerator.get_via_radius(outer_diameter, turns_per_layer, trace_width, trace_spacing, via_diameter)

		# if via diameter is negative, then coil spiral traces are overlapping in one layer, even without considering vias
		if via_inner_diameter <= 0:
			return False

		# check if inner vias fit on radius
		(num_vias_inside, _) = coilgenerator.get_num_vias(layer_count)

		circumference = 2 * math.pi * (via_inner_diameter / 2)

		# using trace width as minimum distance between vias, a ROUGH ESTIMATE can be made if the vias fit on the chosen circle
		if circumference - num_vias_inside * (via_diameter + trace_width) < 0:
			return False

		return True

def get_safe_name(name, keepcharacters = (' ','.','_')):
    return "".join(c for c in name if c.isalnum() or c in keepcharacters).rstrip()

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
			
	def Run(self):
		# Assuming the PCBNew window is focused when run function is executed
		# Alternative would be to keep track of last focussed window, which does not seem to work on all systems
		CoilGeneratorUI(wx.Window.FindFocus()).Show()

"""
This script is used to generate pcb coils
Copyright (C) 2022 Colton Baldridge
Copyright (C) 2023 Tim Goll

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import math
from . import generator

TEMPLATE_FILE = "../dynamic/template.kicad_mod"
BREAKOUT_LEN = 0.5  # (mm)

class Connector:
	x: float
	y: float
	angle: float

	def __init__(self, x, y, angle):
		self.x = x
		self.y = y
		self.angle = angle
		self

def generate(layer_count, wrap_clockwise, turns_per_layer, trace_width, trace_spacing, via_diameter, via_drill, outer_diameter, coil_name, layer_names):
	"""
	Generates coils with given parameters. Attempts to place all parts to generate valid coils, though with some parameters, producing a valid coil might not be possible
	Args:
		layer_count: Number of layers in coil
		wrap_clockwise: Clockwise or counter-clockwise coil wrapping
		turns_per_layer: Minimum number of turns per layer: Connecting to vias might introduce up to one more turn
		trace_width: Width of line trace
		trace_spacing: Distance between line traces
		via_diameter: Outer diameter of connecting vias
		via_drill: Diameter of via drill hole
		outer_diameter: Desires outer coil diameter. Coil generation is from outside to inside, so if this is too small, coil wraps may collode
		coil_name: Reference name of coil to put in kicad
		layer_names: Names of Kicad layers to place coil in. Lenght is expected to be >= layer_count
	Returns:
		File: Generated coil in file
	"""
	template_file = os.path.join(os.path.dirname(__file__), TEMPLATE_FILE)

	with open(template_file, "r") as file:
		template = file.read()

	# generate vias and their connectors
	(vias, arc_connectors) = generate_vias(outer_diameter, turns_per_layer, trace_width, trace_spacing, via_diameter, via_drill, layer_count)

	# generate coil spirals and connect them to vias
	(arcs, lines, last_used_radius) = generate_coil_spiral(wrap_clockwise, layer_count, trace_width, trace_spacing, turns_per_layer, outer_diameter, layer_names, arc_connectors)

	# build coil endpoints
	(lines, pads) = generate_pads(lines, last_used_radius, trace_width, via_diameter, wrap_clockwise, layer_count, layer_names[0], layer_names[layer_count -1])

	substitution_dict = {
		"NAME": coil_name,
		"LINES": ''.join(lines),
		"ARCS": ''.join(arcs),
		"VIAS": ''.join(vias),
		"PADS": ''.join(pads),
		"TIMESTAMP1": generator.get_uuid(),
		"TIMESTAMP2": generator.get_uuid(),
		"TIMESTAMP3": generator.get_uuid(),
	}

	return template.format(**substitution_dict)

def generate_coil_spiral(wrap_clockwise, layer_count, trace_width, trace_spacing, turns_per_layer, outer_diameter, layer_names, arc_connectors):
	"""
	Generates coil spirals for a given coil and connects them to vias.
	Args:
		wrap_clockwise: Clockwise or counter-clockwise coil wrapping
		layer_count: Number of layers in coil
		trace_width: Width of line trace
		trace_spacing: Distance between line traces
		turns_per_layer: Minimum number of turns per layer: Connecting to vias might introduce up to one more turn
		outer_diameter: Desires outer coil diameter. Coil generation is from outside to inside, so if this is too small, coil wraps may collode
		layer_names: Names of Kicad layers to place coil in. Lenght is expected to be >= layer_count
		arc_connectors: Via connector points to connect to

	Returns:
		([str], [str], float): (Generated arcs for spirals for PCBNew, Generated connector lines for spirals to vias, last used radius in coil generation)
	"""
	# build out arcs to spec, until # turns is reached
	wrap_direction_multiplier = 1 if wrap_clockwise else -1
	increment = trace_width + trace_spacing
	arcs = []
	lines = []

	start_radius = outer_diameter / 2 - turns_per_layer * trace_width - (turns_per_layer - 1) * trace_spacing
	for layer in range(layer_count):
		current_radius = start_radius

		# for odd layers, the wrap direction needs to be flipped
		inverse_turn_mult = 1
		if layer % 2 != 0:
			inverse_turn_mult = -1

		#generate all full turns for one layer
		for _ in range(turns_per_layer):
			arcs.extend(generator.loop(
					current_radius,
					increment,
					trace_width,
					layer_names[layer],
					wrap_direction_multiplier * inverse_turn_mult
				))
			current_radius += increment

		# connect to vias
		if layer % 2 == 0:
			first_via_inside = False
			second_via_inside = True
		else:
			first_via_inside = True
			second_via_inside = False

		if (wrap_clockwise and layer % 2 == 0) \
			or (not wrap_clockwise and layer % 2 == 1):
			current_clockwise = True
		else:
			current_clockwise = False

		loop_inner_point = generator.P2D(start_radius, 0)
		loop_outer_point = generator.P2D(current_radius, 0)

		# connect up to two vias, or one for first layer
		if layer > 0:
			if first_via_inside:
				loop_end_point = loop_inner_point
				end_point_radius = start_radius
			else:
				loop_end_point = loop_outer_point
				end_point_radius = current_radius

			(arcs, lines) = connect_via(end_point_radius, loop_end_point, increment, layer_names[layer], trace_width, first_via_inside, current_clockwise, arc_connectors[layer -1], arcs, lines)

		if layer < (layer_count -1) or (layer_count % 2 != 0):
			if second_via_inside:
				loop_end_point = loop_inner_point
				end_point_radius = start_radius
			else:
				loop_end_point = loop_outer_point
				end_point_radius = current_radius

			(arcs, lines) = connect_via(end_point_radius, loop_end_point, increment, layer_names[layer], trace_width, second_via_inside, current_clockwise, arc_connectors[layer], arcs, lines)

	return (arcs, lines, current_radius)


def generate_vias(outer_diameter, turns_per_layer, trace_width, trace_spacing, via_diameter, via_drill, layer_count):
	"""
	Generates vias for a given coil.
	Connection has to be done when coil spirals have been generated
	Args:
		outer_diameter: Desired outer coil diameter
		turns_per_layer: Number of spiral turns per coil layer
		trace_width: Width of line trace
		trace_spacing: Distance between line traces
		via_diameter: Outer diameter of connecting vias
		via_drill: Diameter of via drill hole
		layer_count: Number of layers in coil

	Returns:
		([str], [Connector]): (Generated vias for PCBNew, Via positions to be used for easier connecting with coil spiral)
	"""
	(VIA_INSIDE_RADIUS, VIA_OUTSIDE_RADIUS) = get_via_radius(outer_diameter, turns_per_layer, trace_width, trace_spacing, via_diameter)
	arc_connectors = []
	vias = []

	#calculate the number of vias inside and outside of coil and their corresponding degree spacing
	num_vias_inside = 0
	num_vias_outside = 0

	(num_vias_inside, num_vias_outside) = get_num_vias(layer_count)

	degree_steps_inside = 360 / (num_vias_inside)
	degree_steps_outside = 0
	if num_vias_outside != 0:
		degree_steps_outside = 360 / (num_vias_outside)

	for v in range(0, num_vias_inside + num_vias_outside):

		# define if via is placed inside or outside of coil
		via_used_radius = VIA_INSIDE_RADIUS
		if v % 2 != 0:
			via_used_radius = VIA_OUTSIDE_RADIUS

		# set different step width for inside and outside loop
		degree_steps_used = degree_steps_inside
		if v % 2 != 0:
			degree_steps_used = degree_steps_outside

		rotation_degree = (v // 2) * degree_steps_used

		height = math.sin(math.radians(rotation_degree)) * via_used_radius
		width = math.sqrt(via_used_radius**2 - height**2)

		if rotation_degree > 90 and rotation_degree < 270:
			width *= -1

		arc_connectors.append(Connector(width, height, rotation_degree))

		vias.append(
			generator.via(
				generator.P2D(width, height),
				via_diameter,
				via_drill
			)
		)

	return (vias, arc_connectors)

def generate_pads(lines, outer_radius, trace_width, via_diameter, clockwise, layer_count, top_layer_name, bottom_layer_name):
	"""
	Generates and connects pads for a given coil.
	Coils with uneven number of layers will only have one pad, as the other connection is a via on the inside of the coil
	Args:
		lines: previously drawn lines array to manipulate / append
		outer_radius: Desired outer coil radius
		trace_width: Width of line trace
		via_diameter: Outer diameter of connecting vias
		clockwise: Clockwise or counter-clockwise coil wrapping
		layer_count: Number of layers in coil
		top_layer_name: PCBNew name of top coil layer
		bottom_layer_name: PCBNew name of bottom coil layer (not necessarily PCB bottom layer!)

	Returns:
		([str], [str]): (Modified lines array, Generated Pads array)
	"""
	pads = []
	wrap_direction_multiplier = 1 if clockwise else -1

	#calculate pad center points
	top_pad_center_point = generator.P2D(outer_radius + BREAKOUT_LEN + 4 * trace_width, (BREAKOUT_LEN + 0.5 * via_diameter + trace_width) * -wrap_direction_multiplier)
	bottom_pad_center_point = generator.P2D(outer_radius + BREAKOUT_LEN + 4 * trace_width, (BREAKOUT_LEN + 0.5 * via_diameter + trace_width)* wrap_direction_multiplier)

	# draw lines from coil spiral end point to top pad
	lines.append(
		generator.line(
			generator.P2D(outer_radius, 0),
			generator.P2D(outer_radius, top_pad_center_point.y),
			trace_width,
			top_layer_name
		)
	)

	lines.append(
		generator.line(
			generator.P2D(outer_radius, top_pad_center_point.y),
			generator.P2D(top_pad_center_point.x - 3 * trace_width, top_pad_center_point.y),
			trace_width,
			top_layer_name
		)
	)

	# if bottom pad exists, draw lines from spiral end point to bottom pad
	if layer_count > 1 and layer_count % 2 == 0:
		lines.append(
			generator.line(
				generator.P2D(outer_radius, 0),
				generator.P2D(outer_radius, bottom_pad_center_point.y),
				trace_width,
				bottom_layer_name
			)
		)

		lines.append(
			generator.line(
				generator.P2D(outer_radius, bottom_pad_center_point.y),
				generator.P2D(bottom_pad_center_point.x - 3 * trace_width, bottom_pad_center_point.y),
				trace_width,
				bottom_layer_name
			)
		)

	# generate the pads
	# NOTE: there are some oddities in KiCAD here. The pad must be sufficiently far away from the last line such that
	# KiCAD does not display the "Cannot start routing from a graphic" error. It also must be far enough away that the
	# trace does not throw the "The routing start point violates DRC error". I have found that a 0.5mm gap works ok in
	# most scenarios, with a 1.2mm wide pad. Feel free to adjust to your needs, but you've been warned.
	pads.append(
		generator.pad(
			1,
			top_pad_center_point,
			8 * trace_width,
			trace_width,
			top_layer_name
		)
	)

	if layer_count > 1 and layer_count % 2 == 0:
		pads.append(
			generator.pad(
				2,
				bottom_pad_center_point,
				8 * trace_width,
				trace_width,
				bottom_layer_name
			)
		)

	return (lines, pads)

def get_num_vias(layer_count):
	"""
	Calculates number of vias required inside and outside of coil
	Args:
		layer_count: Number of layers in coil

	Returns:
		(float, float): (Via inside of coil, Via outside of coil)
	"""
	#coils with uneven layer count need extra via that allows connection of last endpoint of coil
	num_vias = layer_count - (1- layer_count % 2)
	num_vias_inside = num_vias // 2 + 1
	num_vias_outside = num_vias_inside - 1

	return (num_vias_inside, num_vias_outside)

def get_via_radius(outer_diameter, turns_per_layer, trace_width, trace_spacing, via_diameter):
	"""
	Calculates diameter at which vias need to be placed
	Args:
		outer_diameter: Desired outer coil diameter. Coil generation is from outside to inside, so if this is too small, coil wraps may collide
		turns_per_layer: Minimum number of turns per layer: Connecting to vias might introduce up to one more turn
		trace_width: Width of line trace
		trace_spacing: Distance between line traces
		via_diameter: Outer diameter of connecting vias

	Returns:
		(float, float): (Via inside radius, Via outside radius)
	"""
	VIA_INSIDE_RADIUS = outer_diameter / 2 - turns_per_layer * trace_width - (turns_per_layer -1) * trace_spacing - via_diameter - (trace_width + trace_spacing)
	VIA_OUTSIDE_RADIUS = outer_diameter / 2 + via_diameter + 2 * trace_spacing + trace_width

	return (VIA_INSIDE_RADIUS, VIA_OUTSIDE_RADIUS)


def get_circle_section_centerpoint(point_a, point_b, radius):
	"""
	Takes two points A and B, generates a point central to A and B and places it on a radius from origin
	Args:
		point_a: Reference point A to produce central point from
		point_b: Reference point B to produce central point from
		radius: Desired radius at which to put produced point

	Returns:
		P2D: Generated center point between A and B on radius
	"""
	point_a_red = get_point_radius_reduced(point_a, 1)
	point_b_red = get_point_radius_reduced(point_b, 1)

	x_new = (point_a_red.x + point_b_red.x) / 2
	y_new = (point_a_red.y + point_b_red.y) / 2

	angle_deg = math.atan2(x_new, y_new) * 180 / math.pi
	return get_point_on_circle(angle_deg, radius)

def get_angle_degree_of_point(point):
	"""
	Takes a point, and calculates angle from it, at which it would sit on a generated circle around origin
	Args:
		point: Point of which to get angle around origin circle

	Returns:
		float: Angle in degree of point on origin circle
	"""
	angle_rad = math.atan2(point.x, point.y)
	return angle_rad * 180 / math.pi

def get_point_on_circle(angle_deg, radius):
	"""
	Given an angle and a radius, generates a point on the resulting circle
	Args:
		angle_deg: Angle in degree, at which to position point on circle
		radius: Radius of target circle

	Returns:
		P2D: given point on circle at angle_deg
	"""
	a = math.cos(math.radians(angle_deg)) * radius
	b = math.sin(math.radians(angle_deg)) * radius
	return generator.P2D(b, a)

def get_point_radius_reduced(point, radius):
	"""
	Reduces a point to be on a circle with given radius around the origin
	Args:
		point: Point somewhere outside of circle
		radius: Radius of target circle

	Returns:
		P2D: given point, mapped onto circle with radius
	"""
	hypotenuse = math.sqrt(point.x**2 + point.y**2)
	factor = hypotenuse / radius
	return generator.P2D(point.x / factor, point.y / factor)

def get_point_distance(point_a, point_b):
	"""
	Returns the distance between two points
	Args:
		point_a: Start point
		point_b: End point

	Returns:
		float: Distance between given points
	"""
	return math.sqrt((point_a.x - point_b.x)**2 + (point_a.y - point_b.y)**2)

def get_angle_degree_between(point_a, point_b, clockwise):
	"""
	Returns angle difference between two points on a circle, factoring in traversing direction
	Args:
		point_a: Start point
		point_b: End point
		clockwise: Traversal direction

	Returns:
		float: Angle in degree, between the given points
	"""
	angle_a = get_angle_degree_of_point(point_a)
	if angle_a < 0:
		angle_a = 360 + angle_a
	angle_b = get_angle_degree_of_point(point_b)
	if angle_b < 0:
		angle_b = 360 + angle_b

	result = angle_a - angle_b
	if result < 0:
		result = 360 + result

	if not clockwise:
		result = 360 - result

	if result == 360:
		result = 0

	return result

def is_left_of(point_a, point_b):
	"""
	Checks if point a is left of point b
	Convenience function to be more expressive
	Args:
		point_a: Point A to check if A left of B
		point_b: Point B to check if A left of B
		clockwise: Traversal direction

	Returns:
		float: Angle in degree, between the given points
	"""
	return point_a < point_b

def connect_via(end_point_radius, loop_end_point, loop_increment, layer_name, trace_width, inside, clockwise, arc_connector, arcs, lines):
	"""
	Connects a coil spirals endpoint to a designated via.
	Does so in three steps:
	1) If the distance between the end point and via is >= 180 degree in coil winding direction, produces a half arc.
	2) If the distance is then still greater than 3 * loop_increment, generates a partial arc to fill the gap
	3) Connects the last missing piece via a straight line
	Args:
		end_point_radius: Radius of loop_end_point
		loop_end_point: Edge of coil spiral to connect to via
		loop_increment:
		layer_name: Name of currently modified layer, needed for line generation
		trace_width: Width of the line trace
		inside: Boolean to identify if inside of a coil spiral is to be connected or outside
		clockwise: Boolean to identify if the coil spiral is going clockwise or counter-clockwise (check from outside end point)
		arc_connector: Via to connect to
		arcs: Previously drawn arcs array to manipulate / append
		lines: previously drawn lines array to manipulate / append
	Returns:
		([str], [str]): Modified (arcs array, lines array)
	"""
	MIN_DIRECT_BRIDGE_DISTANCE = (3 * loop_increment)

	# define which endpoint is on outer side of loop and which on inner side
	if inside :
		target_radius_closest_to_via = end_point_radius - loop_increment
	else:
		target_radius_closest_to_via = end_point_radius + loop_increment

	current_closest_to_via_radius = end_point_radius
	current_closest_to_via = loop_end_point

	# define a point close to the via from where to go straight to the via
	nearest_connector_point = get_point_radius_reduced(generator.P2D(arc_connector.x, arc_connector.y), target_radius_closest_to_via)
	# if the via is too far away from one of the loop endpoints, the gap needs to be bridged
	if get_point_distance(current_closest_to_via, generator.P2D(arc_connector.x, arc_connector.y)) >= MIN_DIRECT_BRIDGE_DISTANCE:

		# if more than half a circle is to cover, split the operation in generating half a circle + the rest
		if get_angle_degree_between(current_closest_to_via, nearest_connector_point, (inside == clockwise)) >= 180:
			# radius adaption
			if inside:
				arc_target_radius = target_radius_closest_to_via
				arc_center_radius = arc_target_radius + 0.5 * loop_increment
			else:
				arc_target_radius = target_radius_closest_to_via - loop_increment
				arc_center_radius = arc_target_radius

			# for half circle, opposite point is end point
			opposite_point = get_point_radius_reduced(generator.P2D(-loop_end_point.x, -loop_end_point.y), arc_target_radius)

			center_point = generator.P2D(0, arc_center_radius)
			if inside != clockwise:
				center_point.y = center_point.y * -1

			arcs.extend(generator.arc(
				loop_end_point,
				center_point,
				opposite_point,
				trace_width,
				layer_name,
				not (clockwise == inside)))

			current_closest_to_via = opposite_point
			current_closest_to_via_radius = arc_target_radius

		# if 180 degree arc was not enough, the gap needs to fill with a partial arc
		remaining_angle = get_angle_degree_between(current_closest_to_via, nearest_connector_point,  (inside == clockwise))

		if remaining_angle >= MIN_DIRECT_BRIDGE_DISTANCE:
			arc_center_radius = (target_radius_closest_to_via - current_closest_to_via_radius) / 2 + current_closest_to_via_radius

			arcs.extend(generator.arc(
				current_closest_to_via,
				get_circle_section_centerpoint(current_closest_to_via, nearest_connector_point, arc_center_radius),
				nearest_connector_point,
				trace_width,
				layer_name,
				not (inside == clockwise)))

			current_closest_to_via = nearest_connector_point

	# connecting the last piece to via with direct line
	lines.extend(generator.line(
		current_closest_to_via,
		generator.P2D(arc_connector.x, arc_connector.y),
		trace_width,
		layer_name))

	return (arcs, lines)
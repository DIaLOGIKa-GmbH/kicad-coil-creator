import traceback

try:
	from .plugin import Plugin
	plugin = Plugin()
	plugin.register()
except Exception as e:
	import logging
	logger = logging.getLogger()
	logger.log(logging.INFO, "Exception was thrown while initializing coilgen plugin: " + repr(e))
	logger.log(traceback.format_exc())

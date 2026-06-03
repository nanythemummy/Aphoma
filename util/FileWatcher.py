from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util.util import MaskingOptions, copy_file_to_dest, should_prune, get_export_filename
from util.PipelineLogging import getLogger as getGlobalLogger
from util.Configurator import Configurator
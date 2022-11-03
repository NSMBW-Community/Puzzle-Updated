import os.path

# Everything highly specific to Puzzle is in this section, to make it
# simpler to copypaste this script across all of the NSMBW-related
# projects that use the same technologies (Reggie, Puzzle, BRFNTify,
# etc)

PROJECT_NAME = 'Puzzle'
FULL_PROJECT_NAME = 'Puzzle Tileset Editor'
PROJECT_VERSION = '1.0'

WIN_ICON = None
MAC_ICON = None
MAC_BUNDLE_IDENTIFIER = 'ca.chronometry.puzzle'

SCRIPT_FILE = 'puzzle.py'
DATA_FOLDERS = ['Icons']
DATA_FILES = ['readme.txt', 'license.txt']
EXTRA_IMPORT_PATHS = []

USE_PYQT = True
USE_NSMBLIB = True

EXCLUDE_HASHLIB = True

# macOS only
AUTO_APP_BUNDLE_NAME = SCRIPT_FILE.split('.')[0] + '.app'
FINAL_APP_BUNDLE_NAME = FULL_PROJECT_NAME + '.app'

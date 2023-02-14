#!/usr/bin/env python3

from ctypes import create_string_buffer
import os, os.path
import struct
import sys

try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    QtName = 'PyQt6'
except ImportError:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets
        QtName = 'PyQt5'
    except ImportError:
        raise RuntimeError('Could not find any supported Qt bindings. Please read the readme for more information.')

def pyqtVersionToTuple(v):
    return (v >> 16, (v >> 8) & 0xff, v & 0xff)

Qt = QtCore.Qt
QtCompatVersion = tuple([int(c) for c in QtCore.qVersion().split('.')])
QtBindingsVersion = (QtCore.PYQT_VERSION >> 16,
                     (QtCore.PYQT_VERSION >> 8) & 0xff,
                     QtCore.PYQT_VERSION & 0xff)

import archive
import lz77

try:
    import nsmblib
    HaveNSMBLib = True
except ImportError:
    HaveNSMBLib = False


########################################################
# To Do:
#
#   - Object Editor
#       - Moving objects around
#
#   - Make UI simpler for Pop
#   - fix up conflicts with different types of parameters
#   - C speed saving
#   - quick settings for applying to mulitple slopes
#
########################################################


Tileset = None


def module_path():
    """
    This will get us the program's directory, even if we are frozen
    using PyInstaller
    """

    if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):  # PyInstaller
        if sys.platform == 'darwin':  # macOS
            # sys.executable is /x/y/z/puzzle.app/Contents/MacOS/puzzle
            # We need to return /x/y/z/puzzle.app/Contents/Resources/

            macos = os.path.dirname(sys.executable)
            if os.path.basename(macos) != 'MacOS':
                return None

            return os.path.join(os.path.dirname(macos), 'Resources')

        else:  # Windows, Linux
            return os.path.dirname(sys.executable)

    if __name__ == '__main__':
        return os.path.dirname(os.path.abspath(__file__))

    return None


def setUpDarkMode():
    """Sets up dark mode theming"""
    # Taken from https://gist.github.com/QuantumCD/6245215

    app.setStyle(QtWidgets.QStyleFactory.create('Fusion'))

    darkPalette = QtGui.QPalette()
    darkPalette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(53,53,53))
    darkPalette.setColor(QtGui.QPalette.ColorRole.WindowText, QtCore.Qt.GlobalColor.white)
    darkPalette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(25,25,25))
    darkPalette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(53,53,53))
    darkPalette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtCore.Qt.GlobalColor.white)
    darkPalette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtCore.Qt.GlobalColor.white)
    darkPalette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.white)
    darkPalette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(53,53,53))
    darkPalette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtCore.Qt.GlobalColor.white)
    darkPalette.setColor(QtGui.QPalette.ColorRole.BrightText, QtCore.Qt.GlobalColor.red)
    darkPalette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(42, 130, 218))

    darkPalette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(42, 130, 218))
    darkPalette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtCore.Qt.GlobalColor.black)

    # fix for disabled menu options
    darkPalette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QtGui.QColor(127,127,127))
    darkPalette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Light, QtGui.QColor(53,53,53))

    app.setPalette(darkPalette)

    app.setStyleSheet("""
        QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white }
        #qt_toolbar_ext_button { background-color: #555; border: 1px solid #888; border-radius: 2px }
        #qt_toolbar_ext_button::hover { background-color: #666 }
    """)


#############################################################################################
########################## Tileset Class and Tile/Object Subclasses #########################

class TilesetClass():
    '''Contains Tileset data. Inits itself to a blank tileset.
    Methods: addTile, removeTile, addObject, removeObject, clear'''

    class Tile():
        def __init__(self, image, noalpha, bytelist):
            '''Tile Constructor'''

            self.image = image
            self.noalpha = noalpha
            self.byte0 = bytelist[0]
            self.byte1 = bytelist[1]
            self.byte2 = bytelist[2]
            self.byte3 = bytelist[3]
            self.byte4 = bytelist[4]
            self.byte5 = bytelist[5]
            self.byte6 = bytelist[6]
            self.byte7 = bytelist[7]


    class Object():

        def __init__(self, height, width, uslope, lslope, tilelist):
            '''Tile Constructor'''

            self.height = height
            self.width = width

            self.upperslope = uslope
            self.lowerslope = lslope

            self.tiles = tilelist


    def __init__(self):
        '''Constructor'''

        self.tiles = []
        self.objects = []
        self.unknownFiles = {}

        self.slot = 0


    def addTile(self, image, noalpha, bytelist = (0, 0, 0, 0, 0, 0, 0, 0)):
        '''Adds an tile class to the tile list with the passed image or parameters'''

        self.tiles.append(self.Tile(image, noalpha, bytelist))


    def addObject(self, height = 1, width = 1,  uslope = [0, 0], lslope = [0, 0], tilelist = [[(0, 0, 0)]]):
        '''Adds a new object'''

        global Tileset

        if tilelist == [[(0, 0, 0)]]:
            tilelist = [[(0, 0, Tileset.slot)]]

        self.objects.append(self.Object(height, width, uslope, lslope, tilelist))


    def removeObject(self, index):
        '''Removes an Object by Index number. Don't use this much, because we want objects to preserve their ID.'''

        self.objects.pop(index)


    def clear(self):
        '''Clears the tileset for a new file'''

        self.tiles = []
        self.objects = []
        self.unknownFiles = {}


#############################################################################################
######################### Palette for painting behaviours to tiles ##########################


class paletteWidget(QtWidgets.QWidget):

    def __init__(self, window):
        super().__init__(window)


        # Core Types Radio Buttons and Tooltips
        self.coreType = QtWidgets.QGroupBox()
        self.coreType.setTitle('Core Type:')
        self.coreWidgets = []
        coreLayout = QtWidgets.QVBoxLayout()
        rowA = QtWidgets.QHBoxLayout()
        rowB = QtWidgets.QHBoxLayout()
        rowC = QtWidgets.QHBoxLayout()
        rowD = QtWidgets.QHBoxLayout()
        rowE = QtWidgets.QHBoxLayout()
        rowF = QtWidgets.QHBoxLayout()

        path = 'Icons/'

        self.coreTypes = [['Default', QtGui.QIcon(path + 'Core/Default.png'), 'The standard type for tiles.\n\nAny regular terrain or backgrounds\nshould be of generic type. It has no\n collision properties.'],
                     ['Slope', QtGui.QIcon(path + 'Core/Slope.png'), 'Defines a sloped tile\n\nSloped tiles have sloped collisions,\nwhich Mario can slide on.\n\nNote: Do NOT set slopes to have solid collision.'],
                     ['Reverse Slope', QtGui.QIcon(path + 'Core/RSlope.png'), 'Defines an upside-down slope.\n\nSloped tiles have sloped collisions,\nwhich Mario can slide on.\n\nNote: Do NOT set slopes to have solid collision.'],
                     ['Partial Block', QtGui.QIcon(path + 'Partial/Full.png'), 'Used for blocks with partial collisions.\n\nVery useful for Mini-Mario secret\nareas, but also for providing a more\naccurate collision map for your tiles.'],
                     ['Coin', QtGui.QIcon(path + 'Core/Coin.png'), 'Creates a coin.\n\nCoins have no solid collision,\nand when touched will disappear\nand increment the coin counter.'],
                     ['Explodable Block', QtGui.QIcon(path + 'Core/Explode.png'), 'Specifies blocks which can explode.\n\nThese blocks will shatter into componenent\npieces when hit by a bom-omb or meteor.\nThe pieces themselves may be hardcoded\nand must be included in the tileset.\nBehaviour may be sporadic.'],
                     ['Climable Grid', QtGui.QIcon(path + 'Core/Climb.png'), 'Creates terrain that can be climbed on.\n\nClimable terrain cannot be walked on.\nWhen Mario is overtop of a climable\ntile and the player presses up,\nMario will enter a climbing state.'],
                     ['Spike', QtGui.QIcon(path + 'Core/Spike.png'), 'Dangerous Spikey spikes.\n\nSpike tiles will damage Mario one hit\nwhen they are touched.'],
                     ['Pipe', QtGui.QIcon(path + 'Core/Pipe.png'), "Denotes a pipe tile.\n\nPipe tiles are specified according to\nthe part of the pipe. It's important\nto specify the right parts or\nentrances will not function correctly."],
                     ['Rails', QtGui.QIcon(path + 'Core/Rails.png'), 'Used for all types of rails.\n\nPlease note that Pa3_rail.arc is hardcoded\nto replace rails with 3D models.'],
                     ['Conveyor Belt', QtGui.QIcon(path + 'Core/Conveyor.png'), 'Defines moving tiles.\n\nMoving tiles will move Mario in one\ndirection or another. Parameters are\nlargely unknown at this time.'],
                     ['Question Block', QtGui.QIcon(path + 'Core/Qblock.png'), 'Creates question blocks.']]

        i = 0
        for item in range(len(self.coreTypes)):
            self.coreWidgets.append(QtWidgets.QRadioButton())
            if i == 0:
                self.coreWidgets[item].setText('Default')
            else:
                self.coreWidgets[item].setIcon(self.coreTypes[item][1])
            self.coreWidgets[item].setIconSize(QtCore.QSize(24, 24))
            self.coreWidgets[item].setToolTip(self.coreTypes[item][2])
            self.coreWidgets[item].clicked.connect(self.swapParams)
            if i < 2:
                rowA.addWidget(self.coreWidgets[item])
            elif i < 4:
                rowB.addWidget(self.coreWidgets[item])
            elif i < 6:
                rowC.addWidget(self.coreWidgets[item])
            elif i < 8:
                rowD.addWidget(self.coreWidgets[item])
            elif i < 10:
                rowE.addWidget(self.coreWidgets[item])
            else:
                rowF.addWidget(self.coreWidgets[item])
            i += 1

        coreLayout.addLayout(rowA)
        coreLayout.addLayout(rowB)
        coreLayout.addLayout(rowC)
        coreLayout.addLayout(rowD)
        coreLayout.addLayout(rowE)
        coreLayout.addLayout(rowF)
        self.coreType.setLayout(coreLayout)


        # Properties Buttons. I hope this works well!
        self.propertyGroup = QtWidgets.QGroupBox()
        self.propertyGroup.setTitle('Properties:')
        propertyLayout = QtWidgets.QVBoxLayout()
        self.propertyWidgets = []
        propertyList = [['Solid', QtGui.QIcon(path + 'Prop/Solid.png'), 'Tiles you can walk on.\n\nThe tiles we be a solid basic square\nthrough which Mario can not pass.'],
                        ['Block', QtGui.QIcon(path + 'Prop/Break.png'), 'This denotes breakable tiles such\nas brick blocks. It is likely that these\nare subject to the same issues as\nexplodable blocks. They emit a coin\nwhen hit.'],
                        ['Falling Block', QtGui.QIcon(path + 'Prop/Fall.png'), 'Sets the block to fall after a set period. The\nblock is sadly replaced with a donut lift model.'],
                        ['Ledge', QtGui.QIcon(path + 'Prop/Ledge.png'), 'A ledge tile with unique properties.\n\nLedges can be shimmied along or\nhung from, but not walked along\nas with normal terrain. Must have the\nledge terrain type set as well.'],
                        ['Meltable', QtGui.QIcon(path + 'Prop/Melt.png'), 'Supposedly allows melting the tile?']]

        for item in range(len(propertyList)):
            self.propertyWidgets.append(QtWidgets.QCheckBox(propertyList[item][0]))
            self.propertyWidgets[item].setIcon(propertyList[item][1])
            self.propertyWidgets[item].setIconSize(QtCore.QSize(24, 24))
            self.propertyWidgets[item].setToolTip(propertyList[item][2])
            propertyLayout.addWidget(self.propertyWidgets[item])


        self.PassThrough = QtWidgets.QRadioButton('Pass-Through')
        self.PassDown = QtWidgets.QRadioButton('Pass-Down')
        self.PassNone = QtWidgets.QRadioButton('No Passing')

        self.PassThrough.setIcon(QtGui.QIcon(path + 'Prop/Pup.png'))
        self.PassDown.setIcon(QtGui.QIcon(path + 'Prop/Pdown.png'))
        self.PassNone.setIcon(QtGui.QIcon(path + 'Prop/Pnone.png'))

        self.PassThrough.setIconSize(QtCore.QSize(24, 24))
        self.PassDown.setIconSize(QtCore.QSize(24, 24))
        self.PassNone.setIconSize(QtCore.QSize(24, 24))

        self.PassThrough.setToolTip('Allows Mario to jump through the bottom\nof the tile and land on the top.')
        self.PassDown.setToolTip("Allows Mario to fall through the tile but\nbe able to jump up through it. Doesn't seem to actually do anything, though?")
        self.PassNone.setToolTip('Default setting')

        propertyLayout.addWidget(self.PassNone)
        propertyLayout.addWidget(self.PassThrough)
        propertyLayout.addWidget(self.PassDown)

        self.propertyGroup.setLayout(propertyLayout)



        # Terrain Type ComboBox
        self.terrainType = QtWidgets.QComboBox()
        self.terrainLabel = QtWidgets.QLabel('Terrain Type')

        self.terrainTypes = [['Default', QtGui.QIcon(path + 'Core/Default.png')],
                        ['Ice', QtGui.QIcon(path + 'Terrain/Ice.png')],
                        ['Snow', QtGui.QIcon(path + 'Terrain/Snow.png')],
                        ['Quicksand', QtGui.QIcon(path + 'Terrain/Quicksand.png')],
                        ['Conveyor Belt Right', QtGui.QIcon(path + 'Core/Conveyor.png')],
                        ['Conveyor Belt Left', QtGui.QIcon(path + 'Core/Conveyor.png')],
                        ['Horiz. Climbing Rope', QtGui.QIcon(path + 'Terrain/Rope.png')],
                        ['Anti Wall Jumps', QtGui.QIcon(path + 'Terrain/Spike.png')],
                        ['Ledge', QtGui.QIcon(path + 'Terrain/Ledge.png')],
                        ['Ladder', QtGui.QIcon(path + 'Terrain/Ladder.png')],
                        ['Staircase', QtGui.QIcon(path + 'Terrain/Stairs.png')],
                        ['Carpet', QtGui.QIcon(path + 'Terrain/Carpet.png')],
                        ['Dusty', QtGui.QIcon(path + 'Terrain/Dust.png')],
                        ['Grass', QtGui.QIcon(path + 'Terrain/Grass.png')],
                        ['Muffled', QtGui.QIcon(path + 'Unknown.png')],
                        ['Beach Sand', QtGui.QIcon(path + 'Terrain/Sand.png')]]

        for item in range(len(self.terrainTypes)):
            self.terrainType.addItem(self.terrainTypes[item][1], self.terrainTypes[item][0])
            self.terrainType.setIconSize(QtCore.QSize(24, 24))
        self.terrainType.setToolTip('Set the various types of terrain.'
                                    '<ul>'
                                    '<li><b>Default:</b><br>'
                                    'Terrain with no particular properties.</li>'
                                    '<li><b>Ice:</b><br>'
                                    'Will be slippery.</li>'
                                    '<li><b>Snow:</b><br>'
                                    'Will emit puffs of snow and snow noises.</li>'
                                    '<li><b>Quicksand:</b><br>'
                                    'Will slowly swallow Mario. Required for creating the quicksand effect.</li>'
                                    '<li><b>Conveyor Belt Right:</b><br>'
                                    'Mario moves rightwards.</li>'
                                    '<li><b>Conveyor Belt Left:</b><br>'
                                    'Mario moves leftwards.</li>'
                                    '<li><b>Horiz. Rope:</b><br>'
                                    'Must be solid to function. Mario will move hand-over-hand along the rope.</li>'
                                    '<li><b>Anti Wall Jumps:</b><br>'
                                    'Mario cannot wall-jump off of the tile.</li>'
                                    '<li><b>Ledge:</b><br>'
                                    'Must have ledge property set as well.</li>'
                                    '<li><b>Ladder:</b><br>'
                                    'Acts as a pole. Mario will face right or left as he climbs.</li>'
                                    '<li><b>Staircase:</b><br>'
                                    'Does not allow Mario to slide.</li>'
                                    '<li><b>Carpet:</b><br>'
                                    'Will muffle footstep noises.</li>'
                                    '<li><b>Dusty:</b><br>'
                                    'Will emit puffs of dust.</li>'
                                    '<li><b>Muffled:</b><br>'
                                    'Mostly muffles footstep noises.</li>'
                                    '<li><b>Grass:</b><br>'
                                    'Will emit grass-like footstep noises.</li>'
                                    '<li><b>Beach Sand:</b><br>'
                                    "Will create sand tufts around Mario's feet.</li>"
                                    '</ul>'
                                   )



        # Parameters ComboBox
        self.parameters = QtWidgets.QComboBox()
        self.parameterLabel = QtWidgets.QLabel('Parameters')
        self.parameters.addItem('None')


        GenericParams = [['None', QtGui.QIcon(path + 'Core/Default.png')],
                         ['Beanstalk Stop', QtGui.QIcon(path + '/Generic/Beanstopper.png')],
                         ['Dash Coin', QtGui.QIcon(path + 'Generic/Outline.png')],
                         ['Battle Coin', QtGui.QIcon(path + 'Generic/Outline.png')],
                         ['Red Block Outline A', QtGui.QIcon(path + 'Generic/RedBlock.png')],
                         ['Red Block Outline B', QtGui.QIcon(path + 'Generic/RedBlock.png')],
                         ['Cave Entrance Right', QtGui.QIcon(path + 'Generic/Cave-Right.png')],
                         ['Cave Entrance Left', QtGui.QIcon(path + 'Generic/Cave-Left.png')],
                         ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                         ['Layer 0 Pit', QtGui.QIcon(path + 'Unknown.png')]]

        RailParams = [['None', QtGui.QIcon(path + 'Core/Default.png')],
                      ['Rail: Upslope', QtGui.QIcon(path + '')],
                      ['Rail: Downslope', QtGui.QIcon(path + '')],
                      ['Rail: 90 degree Corner Fill', QtGui.QIcon(path + '')],
                      ['Rail: 90 degree Corner', QtGui.QIcon(path + '')],
                      ['Rail: Horizontal Rail', QtGui.QIcon(path + '')],
                      ['Rail: Vertical Rail', QtGui.QIcon(path + '')],
                      ['Rail: Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Rail: Gentle Upslope 2', QtGui.QIcon(path + '')],
                      ['Rail: Gentle Upslope 1', QtGui.QIcon(path + '')],
                      ['Rail: Gentle Downslope 2', QtGui.QIcon(path + '')],
                      ['Rail: Gentle Downslope 1', QtGui.QIcon(path + '')],
                      ['Rail: Steep Upslope 2', QtGui.QIcon(path + '')],
                      ['Rail: Steep Upslope 1', QtGui.QIcon(path + '')],
                      ['Rail: Steep Downslope 2', QtGui.QIcon(path + '')],
                      ['Rail: Steep Downslope 1', QtGui.QIcon(path + '')],
                      ['Rail: One Panel Circle', QtGui.QIcon(path + '')],
                      ['Rail: 2x2 Circle Upper Right', QtGui.QIcon(path + '')],
                      ['Rail: 2x2 Circle Upper Left', QtGui.QIcon(path + '')],
                      ['Rail: 2x2 Circle Lower Right', QtGui.QIcon(path + '')],
                      ['Rail: 2x2 Circle Lower Left', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Top Left Corner', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Top Left', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Top Right', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Top Right Corner', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Upper Left Side', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Upper Right Side', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Lower Left Side', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Lower Right Side', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Bottom Left Corner', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Bottom Left', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Bottom Right', QtGui.QIcon(path + '')],
                      ['Rail: 4x4 Circle Bottom Right Corner', QtGui.QIcon(path + '')],
                      ['Rail: Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Rail: End Stop', QtGui.QIcon(path + '')]]

        ClimableGridParams = [['None', QtGui.QIcon(path + 'Core/Default.png')],
                             ['Free Move', QtGui.QIcon(path + 'Climb/Center.png')],
                             ['Upper Left Corner', QtGui.QIcon(path + 'Climb/UpperLeft.png')],
                             ['Top', QtGui.QIcon(path + 'Climb/Top.png')],
                             ['Upper Right Corner', QtGui.QIcon(path + 'Climb/UpperRight.png')],
                             ['Left Side', QtGui.QIcon(path + 'Climb/Left.png')],
                             ['Center', QtGui.QIcon(path + 'Climb/Center.png')],
                             ['Right Side', QtGui.QIcon(path + 'Climb/Right.png')],
                             ['Lower Left Corner', QtGui.QIcon(path + 'Climb/LowerLeft.png')],
                             ['Bottom', QtGui.QIcon(path + 'Climb/Bottom.png')],
                             ['Lower Right Corner', QtGui.QIcon(path + 'Climb/LowerRight.png')]]


        CoinParams = [['Generic Coin', QtGui.QIcon(path + 'QBlock/Coin.png')],
                     ['Coin', QtGui.QIcon(path + 'Unknown.png')],
                     ['Nothing', QtGui.QIcon(path + 'Unknown.png')],
                     ['Coin', QtGui.QIcon(path + 'Unknown.png')],
                     ['Pow Block Coin', QtGui.QIcon(path + 'Coin/POW.png')]]

        ExplodableBlockParams = [['None', QtGui.QIcon(path + 'Core/Default.png')],
                                ['Stone Block', QtGui.QIcon(path + 'Explode/Stone.png')],
                                ['Wooden Block', QtGui.QIcon(path + 'Explode/Wooden.png')],
                                ['Red Block', QtGui.QIcon(path + 'Explode/Red.png')],
                                ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                                ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                                ['Unknown', QtGui.QIcon(path + 'Unknown.png')]]

        PipeParams = [['Vert. Top Entrance Left', QtGui.QIcon(path + 'Pipes/')],
                      ['Vert. Top Entrance Right', QtGui.QIcon(path + '')],
                      ['Vert. Bottom Entrance Left', QtGui.QIcon(path + '')],
                      ['Vert. Bottom Entrance Right', QtGui.QIcon(path + '')],
                      ['Vert. Center Left', QtGui.QIcon(path + '')],
                      ['Vert. Center Right', QtGui.QIcon(path + '')],
                      ['Vert. On Top Junction Left', QtGui.QIcon(path + '')],
                      ['Vert. On Top Junction Right', QtGui.QIcon(path + '')],
                      ['Horiz. Left Entrance Top', QtGui.QIcon(path + '')],
                      ['Horiz. Left Entrance Bottom', QtGui.QIcon(path + '')],
                      ['Horiz. Right Entrance Top', QtGui.QIcon(path + '')],
                      ['Horiz. Right Entrance Bottom', QtGui.QIcon(path + '')],
                      ['Horiz. Center Top', QtGui.QIcon(path + '')],
                      ['Horiz. Center Bottom', QtGui.QIcon(path + '')],
                      ['Horiz. On Top Junction Top', QtGui.QIcon(path + '')],
                      ['Horiz. On Top Junction Bottom', QtGui.QIcon(path + '')],
                      ['Vert. Mini Pipe Top', QtGui.QIcon(path + '')],
                      ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Vert. Mini Pipe Bottom', QtGui.QIcon(path + '')],
                      ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Vert. On Top Mini-Junction', QtGui.QIcon(path + '')],
                      ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Horiz. Mini Pipe Left', QtGui.QIcon(path + '')],
                      ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Horiz. Mini Pipe Right', QtGui.QIcon(path + '')],
                      ['Unknown', QtGui.QIcon(path + 'Unknown.png')],
                      ['Vert. Mini Pipe Center', QtGui.QIcon(path + '')],
                      ['Horiz. Mini Pipe Center', QtGui.QIcon(path + '')],
                      ['Horiz. On Top Mini-Junction', QtGui.QIcon(path + '')],
                      ['Block Covered Corner', QtGui.QIcon(path + '')]]

        PartialBlockParams = [['None', QtGui.QIcon(path + 'Core/Default.png')],
                              ['Upper Left', QtGui.QIcon(path + 'Partial/UpLeft.png')],
                              ['Upper Right', QtGui.QIcon(path + 'Partial/UpRight.png')],
                              ['Top Half', QtGui.QIcon(path + 'Partial/TopHalf.png')],
                              ['Lower Left', QtGui.QIcon(path + 'Partial/LowLeft.png')],
                              ['Left Half', QtGui.QIcon(path + 'Partial/LeftHalf.png')],
                              ['Diagonal Downwards', QtGui.QIcon(path + 'Partial/DiagDn.png')],
                              ['Upper Left 3/4', QtGui.QIcon(path + 'Partial/UpLeft3-4.png')],
                              ['Lower Right', QtGui.QIcon(path + 'Partial/LowRight.png')],
                              ['Diagonal Downwards', QtGui.QIcon(path + 'Partial/DiagDn.png')],
                              ['Right Half', QtGui.QIcon(path + 'Partial/RightHalf.png')],
                              ['Upper Right 3/4', QtGui.QIcon(path + 'Partial/UpRig3-4.png')],
                              ['Lower Half', QtGui.QIcon(path + 'Partial/LowHalf.png')],
                              ['Lower Left 3/4', QtGui.QIcon(path + 'Partial/LowLeft3-4.png')],
                              ['Lower Right 3/4', QtGui.QIcon(path + 'Partial/LowRight3-4.png')],
                              ['Full Brick', QtGui.QIcon(path + 'Partial/Full.png')]]

        SlopeParams = [['Steep Upslope', QtGui.QIcon(path + 'Slope/steepslopeleft.png')],
                       ['Steep Downslope', QtGui.QIcon(path + 'Slope/steepsloperight.png')],
                       ['Upslope 1', QtGui.QIcon(path + 'Slope/slopeleft.png')],
                       ['Upslope 2', QtGui.QIcon(path + 'Slope/slope3left.png')],
                       ['Downslope 1', QtGui.QIcon(path + 'Slope/slope3right.png')],
                       ['Downslope 2', QtGui.QIcon(path + 'Slope/sloperight.png')],
                       ['Steep Upslope 1', QtGui.QIcon(path + 'Slope/vsteepup1.png')],
                       ['Steep Upslope 2', QtGui.QIcon(path + 'Slope/vsteepup2.png')],
                       ['Steep Downslope 1', QtGui.QIcon(path + 'Slope/vsteepdown1.png')],
                       ['Steep Downslope 2', QtGui.QIcon(path + 'Slope/vsteepdown2.png')],
                       ['Slope Edge (solid)', QtGui.QIcon(path + 'Slope/edge.png')],
                       ['Gentle Upslope 1', QtGui.QIcon(path + 'Slope/gentleupslope1.png')],
                       ['Gentle Upslope 2', QtGui.QIcon(path + 'Slope/gentleupslope2.png')],
                       ['Gentle Upslope 3', QtGui.QIcon(path + 'Slope/gentleupslope3.png')],
                       ['Gentle Upslope 4', QtGui.QIcon(path + 'Slope/gentleupslope4.png')],
                       ['Gentle Downslope 1', QtGui.QIcon(path + 'Slope/gentledownslope1.png')],
                       ['Gentle Downslope 2', QtGui.QIcon(path + 'Slope/gentledownslope2.png')],
                       ['Gentle Downslope 3', QtGui.QIcon(path + 'Slope/gentledownslope3.png')],
                       ['Gentle Downslope 4', QtGui.QIcon(path + 'Slope/gentledownslope4.png')]]

        ReverseSlopeParams = [['Steep Downslope', QtGui.QIcon(path + 'Slope/Rsteepslopeleft.png')],
                              ['Steep Upslope', QtGui.QIcon(path + 'Slope/Rsteepsloperight.png')],
                              ['Downslope 1', QtGui.QIcon(path + 'Slope/Rslopeleft.png')],
                              ['Downslope 2', QtGui.QIcon(path + 'Slope/Rslope3left.png')],
                              ['Upslope 1', QtGui.QIcon(path + 'Slope/Rslope3right.png')],
                              ['Upslope 2', QtGui.QIcon(path + 'Slope/Rsloperight.png')],
                              ['Steep Downslope 1', QtGui.QIcon(path + 'Slope/Rvsteepdown1.png')],
                              ['Steep Downslope 2', QtGui.QIcon(path + 'Slope/Rvsteepdown2.png')],
                              ['Steep Upslope 1', QtGui.QIcon(path + 'Slope/Rvsteepup1.png')],
                              ['Steep Upslope 2', QtGui.QIcon(path + 'Slope/Rvsteepup2.png')],
                              ['Slope Edge (solid)', QtGui.QIcon(path + 'Slope/edge.png')],
                              ['Gentle Downslope 1', QtGui.QIcon(path + 'Slope/Rgentledownslope1.png')],
                              ['Gentle Downslope 2', QtGui.QIcon(path + 'Slope/Rgentledownslope2.png')],
                              ['Gentle Downslope 3', QtGui.QIcon(path + 'Slope/Rgentledownslope3.png')],
                              ['Gentle Downslope 4', QtGui.QIcon(path + 'Slope/Rgentledownslope4.png')],
                              ['Gentle Upslope 1', QtGui.QIcon(path + 'Slope/Rgentleupslope1.png')],
                              ['Gentle Upslope 2', QtGui.QIcon(path + 'Slope/Rgentleupslope2.png')],
                              ['Gentle Upslope 3', QtGui.QIcon(path + 'Slope/Rgentleupslope3.png')],
                              ['Gentle Upslope 4', QtGui.QIcon(path + 'Slope/Rgentleupslope4.png')]]

        SpikeParams = [['Double Left Spikes', QtGui.QIcon(path + 'Spike/Left.png')],
                       ['Double Right Spikes', QtGui.QIcon(path + 'Spike/Right.png')],
                       ['Double Upwards Spikes', QtGui.QIcon(path + 'Spike/Up.png')],
                       ['Double Downwards Spikes', QtGui.QIcon(path + 'Spike/Down.png')],
                       ['Long Spike Down 1', QtGui.QIcon(path + 'Spike/LongDown1.png')],
                       ['Long Spike Down 2', QtGui.QIcon(path + 'Spike/LongDown2.png')],
                       ['Single Downwards Spike', QtGui.QIcon(path + 'Spike/SingDown.png')],
                       ['Spike Block', QtGui.QIcon(path + 'Unknown.png')]]

        ConveyorBeltParams = [['Slow', QtGui.QIcon(path + 'Unknown.png')],
                              ['Fast', QtGui.QIcon(path + 'Unknown.png')]]

        QBlockParams = [['Fire Flower', QtGui.QIcon(path + 'Qblock/Fire.png')],
                       ['Star', QtGui.QIcon(path + 'Qblock/Star.png')],
                       ['Coin', QtGui.QIcon(path + 'Qblock/Coin.png')],
                       ['Vine', QtGui.QIcon(path + 'Qblock/Vine.png')],
                       ['1-Up', QtGui.QIcon(path + 'Qblock/1up.png')],
                       ['Mini Mushroom', QtGui.QIcon(path + 'Qblock/Mini.png')],
                       ['Propeller Suit', QtGui.QIcon(path + 'Qblock/Prop.png')],
                       ['Penguin Suit', QtGui.QIcon(path + 'Qblock/Peng.png')],
                       ['Ice Flower', QtGui.QIcon(path + 'Qblock/IceF.png')]]


        self.ParameterList = [GenericParams,
                              SlopeParams,
                              ReverseSlopeParams,
                              PartialBlockParams,
                              CoinParams,
                              ExplodableBlockParams,
                              ClimableGridParams,
                              SpikeParams,
                              PipeParams,
                              RailParams,
                              ConveyorBeltParams,
                              QBlockParams]


        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.coreType, 0, 1)
        layout.addWidget(self.propertyGroup, 0, 0, 3, 1)
        layout.addWidget(self.terrainType, 2, 1)
        layout.addWidget(self.parameters, 1, 1)
        self.setLayout(layout)


    def swapParams(self):
        for item in range(12):
            if self.coreWidgets[item].isChecked():
                self.parameters.clear()
                for option in self.ParameterList[item]:
                    self.parameters.addItem(option[1], option[0])



#############################################################################################
######################### InfoBox Custom Widget to display info to ##########################


class InfoBox(QtWidgets.QWidget):
    def __init__(self, window):
        super().__init__(window)

        # InfoBox
        superLayout = QtWidgets.QGridLayout()
        infoLayout = QtWidgets.QFormLayout()

        self.imageBox = QtWidgets.QGroupBox()
        imageLayout = QtWidgets.QHBoxLayout()

        pix = QtGui.QPixmap(24, 24)
        pix.fill(Qt.GlobalColor.transparent)

        self.coreImage = QtWidgets.QLabel()
        self.coreImage.setPixmap(pix)
        self.terrainImage = QtWidgets.QLabel()
        self.terrainImage.setPixmap(pix)
        self.parameterImage = QtWidgets.QLabel()
        self.parameterImage.setPixmap(pix)


        def updateAllTiles():
            for i in range(256):
                window.tileDisplay.update(window.tileDisplay.model().index(i, 0))
        self.collisionOverlay = QtWidgets.QCheckBox('Overlay Collision')
        self.collisionOverlay.clicked.connect(updateAllTiles)


        self.coreInfo = QtWidgets.QLabel()
        self.propertyInfo = QtWidgets.QLabel('             \n\n\n\n\n')
        self.terrainInfo = QtWidgets.QLabel()
        self.paramInfo = QtWidgets.QLabel()

        Font = self.font()
        Font.setPointSize(9)

        self.coreInfo.setFont(Font)
        self.propertyInfo.setFont(Font)
        self.terrainInfo.setFont(Font)
        self.paramInfo.setFont(Font)


        self.LabelB = QtWidgets.QLabel('Properties:')
        self.LabelB.setFont(Font)

        self.hexdata = QtWidgets.QLabel('Hex Data: 0x00 0x00 0x00 0x00\n                0x00 0x00 0x00 0x00')
        self.hexdata.setFont(Font)


        coreLayout = QtWidgets.QVBoxLayout()
        terrLayout = QtWidgets.QVBoxLayout()
        paramLayout = QtWidgets.QVBoxLayout()

        coreLayout.setGeometry(QtCore.QRect(0,0,40,40))
        terrLayout.setGeometry(QtCore.QRect(0,0,40,40))
        paramLayout.setGeometry(QtCore.QRect(0,0,40,40))


        label = QtWidgets.QLabel('Core')
        label.setFont(Font)
        coreLayout.addWidget(label, 0, Qt.AlignmentFlag.AlignCenter)

        label = QtWidgets.QLabel('Terrain')
        label.setFont(Font)
        terrLayout.addWidget(label, 0, Qt.AlignmentFlag.AlignCenter)

        label = QtWidgets.QLabel('Parameters')
        label.setFont(Font)
        paramLayout.addWidget(label, 0, Qt.AlignmentFlag.AlignCenter)

        coreLayout.addWidget(self.coreImage, 0, Qt.AlignmentFlag.AlignCenter)
        terrLayout.addWidget(self.terrainImage, 0, Qt.AlignmentFlag.AlignCenter)
        paramLayout.addWidget(self.parameterImage, 0, Qt.AlignmentFlag.AlignCenter)

        coreLayout.addWidget(self.coreInfo, 0, Qt.AlignmentFlag.AlignCenter)
        terrLayout.addWidget(self.terrainInfo, 0, Qt.AlignmentFlag.AlignCenter)
        paramLayout.addWidget(self.paramInfo, 0, Qt.AlignmentFlag.AlignCenter)

        imageLayout.setContentsMargins(0,4,4,4)
        imageLayout.addLayout(coreLayout)
        imageLayout.addLayout(terrLayout)
        imageLayout.addLayout(paramLayout)

        self.imageBox.setLayout(imageLayout)


        superLayout.addWidget(self.imageBox, 0, 0)
        superLayout.addWidget(self.collisionOverlay, 1, 0)
        infoLayout.addRow(self.LabelB, self.propertyInfo)
        infoLayout.addRow(self.hexdata)
        superLayout.addLayout(infoLayout, 0, 1, 2, 1)
        self.setLayout(superLayout)




#############################################################################################
##################### Object List Widget and Model Setup with Painter #######################


class objectList(QtWidgets.QListView):

    def __init__(self, parent=None):
        super().__init__(parent)


        self.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.setIconSize(QtCore.QSize(96,96))
        self.setGridSize(QtCore.QSize(114,114))
        self.setMovement(QtWidgets.QListView.Movement.Static)
        self.setBackgroundRole(QtGui.QPalette.ColorRole.BrightText)
        self.setWrapping(False)
        self.setMinimumHeight(140)
        self.setMaximumHeight(140)



def SetupObjectModel(self, objects, tiles):
    global Tileset
    self.clear()

    count = 0
    for object in objects:
        tex = QtGui.QPixmap(object.width * 24, object.height * 24)
        tex.fill(Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(tex)

        Xoffset = 0
        Yoffset = 0

        for i in range(len(object.tiles)):
            for tile in object.tiles[i]:
                if (Tileset.slot == 0) or ((tile[2] & 3) != 0):
                    painter.drawImage(Xoffset, Yoffset, tiles[tile[1]].image)
                Xoffset += 24
            Xoffset = 0
            Yoffset += 24

        painter.end()

        item = QtGui.QStandardItem(QtGui.QIcon(tex), 'Object {0}'.format(count))
        item.setEditable(False)
        self.appendRow(item)

        count += 1


#############################################################################################
######################## List Widget with custom painter/MouseEvent #########################


class displayWidget(QtWidgets.QListView):

    mouseMoved = QtCore.pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumWidth(424)
        self.setMaximumWidth(424)
        self.setMinimumHeight(404)
        self.setDragEnabled(True)
        self.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.setIconSize(QtCore.QSize(24,24))
        self.setGridSize(QtCore.QSize(25,25))
        self.setMovement(QtWidgets.QListView.Movement.Static)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(True)
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setBackgroundRole(QtGui.QPalette.ColorRole.BrightText)
        self.setMouseTracking(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setItemDelegate(self.TileItemDelegate())


    def mouseMoveEvent(self, event):
        QtWidgets.QWidget.mouseMoveEvent(self, event)

        self.mouseMoved.emit(event.pos().x(), event.pos().y())



    class TileItemDelegate(QtWidgets.QAbstractItemDelegate):
        """Handles tiles and their rendering"""

        def __init__(self):
            """Initialises the delegate"""
            super().__init__()

        def paint(self, painter, option, index):
            """Paints an object"""

            global Tileset
            p = index.model().data(index, Qt.ItemDataRole.DecorationRole)
            painter.drawPixmap(option.rect.x(), option.rect.y(), p.pixmap(24,24))

            x = option.rect.x()
            y = option.rect.y()


            # Collision Overlays
            info = window.infoDisplay
            curTile = Tileset.tiles[index.row()]

            if info.collisionOverlay.isChecked():
                path = os.path.dirname(os.path.abspath(sys.argv[0])) + '/Icons/'

                # Sets the colour based on terrain type
                if curTile.byte2 & 16:      # Red
                    colour = QtGui.QColor(255, 0, 0, 120)
                elif curTile.byte5 == 1:    # Ice
                    colour = QtGui.QColor(0, 0, 255, 120)
                elif curTile.byte5 == 2:    # Snow
                    colour = QtGui.QColor(0, 0, 255, 120)
                elif curTile.byte5 == 3:    # Quicksand
                    colour = QtGui.QColor(128,64,0, 120)
                elif curTile.byte5 == 4:    # Conveyor
                    colour = QtGui.QColor(128,128,128, 120)
                elif curTile.byte5 == 5:    # Conveyor
                    colour = QtGui.QColor(128,128,128, 120)
                elif curTile.byte5 == 6:    # Rope
                    colour = QtGui.QColor(128,0,255, 120)
                elif curTile.byte5 == 7:    # Half Spike
                    colour = QtGui.QColor(128,0,255, 120)
                elif curTile.byte5 == 8:    # Ledge
                    colour = QtGui.QColor(128,0,255, 120)
                elif curTile.byte5 == 9:    # Ladder
                    colour = QtGui.QColor(128,0,255, 120)
                elif curTile.byte5 == 10:    # Staircase
                    colour = QtGui.QColor(255, 0, 0, 120)
                elif curTile.byte5 == 11:    # Carpet
                    colour = QtGui.QColor(255, 0, 0, 120)
                elif curTile.byte5 == 12:    # Dust
                    colour = QtGui.QColor(128,64,0, 120)
                elif curTile.byte5 == 13:    # Grass
                    colour = QtGui.QColor(0, 255, 0, 120)
                elif curTile.byte5 == 14:    # Unknown
                    colour = QtGui.QColor(255, 0, 0, 120)
                elif curTile.byte5 == 15:    # Beach Sand
                    colour = QtGui.QColor(128, 64, 0, 120)
                else:                       # Brown?
                    colour = QtGui.QColor(64, 30, 0, 120)


                # Sets Brush style for fills
                if curTile.byte2 & 4:        # Climbing Grid
                    style = Qt.BrushStyle.DiagCrossPattern
                elif curTile.byte3 & 16:     # Breakable
                    style = Qt.BrushStyle.VerPattern
                else:
                    style = Qt.BrushStyle.SolidPattern


                brush = QtGui.QBrush(colour, style)
                painter.setBrush(brush)
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)


                # Paints shape based on other junk
                if curTile.byte3 & 32: # Slope
                    if curTile.byte7 == 0:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y)]))
                    elif curTile.byte7 == 1:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 2:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y + 12)]))
                    elif curTile.byte7 == 3:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 24)]))
                    elif curTile.byte7 == 4:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x + 24, y + 24)]))
                    elif curTile.byte7 == 5:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 10:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y)]))
                    elif curTile.byte7 == 11:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 24, y + 18),
                                                            QtCore.QPoint(x + 24, y + 24)]))
                    elif curTile.byte7 == 12:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 18),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 13:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y + 6),
                                                            QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 14:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x, y + 6),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 15:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y + 6),
                                                            QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 16:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 6),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 17:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y + 18),
                                                            QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 18:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 18),
                                                            QtCore.QPoint(x, y + 24)]))

                elif curTile.byte3 & 64: # Reverse Slope
                    if curTile.byte7 == 0:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y)]))
                    elif curTile.byte7 == 1:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y)]))
                    elif curTile.byte7 == 2:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y + 12)]))
                    elif curTile.byte7 == 3:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y)]))
                    elif curTile.byte7 == 4:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12)]))
                    elif curTile.byte7 == 5:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y)]))
                    elif curTile.byte7 == 10:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y)]))
                    elif curTile.byte7 == 11:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 6)]))
                    elif curTile.byte7 == 12:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 6)]))
                    elif curTile.byte7 == 13:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 18),
                                                            QtCore.QPoint(x, y + 12)]))
                    elif curTile.byte7 == 14:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 18)]))
                    elif curTile.byte7 == 15:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 18),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 16:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 18)]))
                    elif curTile.byte7 == 17:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 6),
                                                            QtCore.QPoint(x, y + 12)]))
                    elif curTile.byte7 == 18:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x, y + 6)]))

                elif curTile.byte2 & 8: # Partial
                    if curTile.byte7 == 1:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 12, y + 12),
                                                            QtCore.QPoint(x, y + 12)]))
                    elif curTile.byte7 == 2:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x + 12, y + 12)]))
                    elif curTile.byte7 == 3:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 12)]))
                    elif curTile.byte7 == 4:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x + 12, y + 12),
                                                            QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 5:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 6:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 12)]))
                    elif curTile.byte7 == 7:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x + 12, y + 12),
                                                            QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 8:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 12, y + 12),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 12, y + 24)]))
                    elif curTile.byte7 == 9:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x + 12, y)]))
                    elif curTile.byte7 == 10:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 12, y + 24)]))
                    elif curTile.byte7 == 11:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x + 12, y + 12),
                                                            QtCore.QPoint(x, y + 12)]))
                    elif curTile.byte7 == 12:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 13:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 12, y + 12),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 14:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 12, y + 12),
                                                            QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x, y + 24)]))
                    elif curTile.byte7 == 15:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 24)]))

                elif curTile.byte2 & 0x40: # Solid-on-bottom
                    painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                        QtCore.QPoint(x + 24, y + 24),
                                                        QtCore.QPoint(x + 24, y + 18),
                                                        QtCore.QPoint(x, y + 18)]))

                    painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 15, y),
                                                        QtCore.QPoint(x + 15, y + 12),
                                                        QtCore.QPoint(x + 18, y + 12),
                                                        QtCore.QPoint(x + 12, y + 17),
                                                        QtCore.QPoint(x + 6, y + 12),
                                                        QtCore.QPoint(x + 9, y + 12),
                                                        QtCore.QPoint(x + 9, y)]))

                elif curTile.byte2 & 0x80: # Solid-on-top
                    painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                        QtCore.QPoint(x + 24, y),
                                                        QtCore.QPoint(x + 24, y + 6),
                                                        QtCore.QPoint(x, y + 6)]))

                    painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 15, y + 24),
                                                        QtCore.QPoint(x + 15, y + 12),
                                                        QtCore.QPoint(x + 18, y + 12),
                                                        QtCore.QPoint(x + 12, y + 7),
                                                        QtCore.QPoint(x + 6, y + 12),
                                                        QtCore.QPoint(x + 9, y + 12),
                                                        QtCore.QPoint(x + 9, y + 24)]))

                elif curTile.byte2 & 16: # Spikes
                    if curTile.byte7 == 0:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x, y + 6)]))
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 24, y + 12),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x, y + 18)]))
                    if curTile.byte7 == 1:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x + 24, y + 6)]))
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 12),
                                                            QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 24, y + 18)]))
                    if curTile.byte7 == 2:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y + 24),
                                                            QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x + 6, y)]))
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 12, y + 24),
                                                            QtCore.QPoint(x + 24, y + 24),
                                                            QtCore.QPoint(x + 18, y)]))
                    if curTile.byte7 == 3:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 6, y + 24)]))
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 12, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 18, y + 24)]))
                    if curTile.byte7 == 4:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 18, y + 24),
                                                            QtCore.QPoint(x + 6, y + 24)]))
                    if curTile.byte7 == 5:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x + 6, y),
                                                            QtCore.QPoint(x + 18, y),
                                                            QtCore.QPoint(x + 12, y + 24)]))
                    if curTile.byte7 == 6:
                        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y),
                                                            QtCore.QPoint(x + 24, y),
                                                            QtCore.QPoint(x + 12, y + 24)]))

                elif curTile.byte3 & 2: # Coin
                    if curTile.byte7 == 0:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'Coin/Coin.png'))
                    if curTile.byte7 == 4:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'Coin/POW.png'))

                elif curTile.byte3 & 8: # Exploder
                    if curTile.byte7 == 1:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'Explode/Stone.png'))
                    if curTile.byte7 == 2:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'Explode/Wood.png'))
                    if curTile.byte7 == 3:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'Explode/Red.png'))

                elif curTile.byte1 & 2: # Falling
                    painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'Prop/Fall.png'))

                elif curTile.byte3 & 4: # QBlock
                    if curTile.byte7 == 0:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/FireF.png'))
                    if curTile.byte7 == 1:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/Star.png'))
                    if curTile.byte7 == 2:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/Coin.png'))
                    if curTile.byte7 == 3:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/Vine.png'))
                    if curTile.byte7 == 4:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/1up.png'))
                    if curTile.byte7 == 5:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/Mini.png'))
                    if curTile.byte7 == 6:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/Prop.png'))
                    if curTile.byte7 == 7:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/Peng.png'))
                    if curTile.byte7 == 8:
                        painter.drawPixmap(option.rect, QtGui.QPixmap(path + 'QBlock/IceF.png'))

                elif curTile.byte3 & 1: # Solid
                    painter.drawRect(option.rect)

                else: # No fill
                    pass


            # Highlight stuff.
            colour = option.palette.highlight().color()
            colour.setAlpha(80)

            if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, colour)


        def sizeHint(self, option, index):
            """Returns the size for the object"""
            return QtCore.QSize(24,24)



#############################################################################################
############################ Tile widget for drag n'drop Objects ############################


class tileOverlord(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        # Setup Widgets
        self.tiles = tileWidget()

        self.addObject = QtWidgets.QPushButton('Add')
        self.removeObject = QtWidgets.QPushButton('Remove')

        self.addRow = QtWidgets.QPushButton('+')
        self.removeRow = QtWidgets.QPushButton('-')

        self.addColumn = QtWidgets.QPushButton('+')
        self.removeColumn = QtWidgets.QPushButton('-')

        self.tilingMethod = QtWidgets.QComboBox()
        self.tilesetType = QtWidgets.QLabel('Pa0')

        self.tilingMethod.addItems(['Repeat',
                                    'Stretch Center',
                                    'Stretch X',
                                    'Stretch Y',
                                    'Repeat Bottom',
                                    'Repeat Top',
                                    'Repeat Left',
                                    'Repeat Right',
                                    'Upward slope',
                                    'Downward slope',
                                    'Downward reverse slope',
                                    'Upward reverse slope'])


        # Connections
        self.addObject.released.connect(self.addObj)
        self.removeObject.released.connect(self.removeObj)
        self.addRow.released.connect(self.tiles.addRow)
        self.removeRow.released.connect(self.tiles.removeRow)
        self.addColumn.released.connect(self.tiles.addColumn)
        self.removeColumn.released.connect(self.tiles.removeColumn)

        self.tilingMethod.activated.connect(self.setTiling)


        # Layout
        layout = QtWidgets.QGridLayout()

        layout.addWidget(self.tilesetType, 0, 0, 1, 3)
        layout.addWidget(self.tilingMethod, 0, 3, 1, 3)

        layout.addWidget(self.addObject, 0, 6, 1, 1)
        layout.addWidget(self.removeObject, 0, 7, 1, 1)

        layout.setRowMinimumHeight(1, 40)

        layout.setRowStretch(1, 1)
        layout.setRowStretch(2, 5)
        layout.setRowStretch(5, 5)
        layout.addWidget(self.tiles, 2, 1, 4, 6)

        layout.addWidget(self.addColumn, 3, 7, 1, 1)
        layout.addWidget(self.removeColumn, 4, 7, 1, 1)
        layout.addWidget(self.addRow, 6, 3, 1, 1)
        layout.addWidget(self.removeRow, 6, 4, 1, 1)

        self.setLayout(layout)




    def addObj(self):
        global Tileset

        Tileset.addObject()

        pix = QtGui.QPixmap(24, 24)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pix)
        painter.drawImage(0, 0, Tileset.tiles[0].image)
        painter.end()

        count = len(Tileset.objects)
        window.objmodel.appendRow(QtGui.QStandardItem(QtGui.QIcon(pix), 'Object {0}'.format(count-1)))
        index = window.objectList.currentIndex()
        window.objectList.setCurrentIndex(index)
        self.setObject(index)

        window.objectList.update()
        self.update()


    def removeObj(self):
        global Tileset

        if not Tileset.objects:
            return

        index = window.objectList.currentIndex()

        if index.row() == -1:
            return

        Tileset.removeObject(index.row())
        window.objmodel.removeRow(index.row())

        index = window.objectList.currentIndex()
        if index.row() == -1:
            self.tiles.clear()
        else:
            window.objectList.setCurrentIndex(index)
            self.setObject(index)

        window.objectList.update()
        self.update()


    def setObject(self, index):
        global Tileset
        object = Tileset.objects[index.row()]

        width = len(object.tiles[0])-1
        height = len(object.tiles)-1
        Xuniform = True
        Yuniform = True
        Xstretch = False
        Ystretch = False

        for tile in object.tiles[0]:
            if tile[0] != object.tiles[0][0][0]:
                Xuniform = False

        for tile in object.tiles:
            if tile[0][0] != object.tiles[0][0][0]:
                Yuniform = False

        if object.tiles[0][0][0] == object.tiles[0][width][0] and Xuniform == False:
            Xstretch = True

        if object.tiles[0][0][0] == object.tiles[height][0][0] and Xuniform == False:
            Ystretch = True



        if object.upperslope[0] != 0:
            if object.upperslope[0] == 0x90:
                self.tilingMethod.setCurrentIndex(8)
            elif object.upperslope[0] == 0x91:
                self.tilingMethod.setCurrentIndex(9)
            elif object.upperslope[0] == 0x92:
                self.tilingMethod.setCurrentIndex(10)
            elif object.upperslope[0] == 0x93:
                self.tilingMethod.setCurrentIndex(11)

        else:
            if Xuniform and Yuniform:
                self.tilingMethod.setCurrentIndex(0)
            elif Xstretch and Ystretch:
                self.tilingMethod.setCurrentIndex(1)
            elif Xstretch:
                self.tilingMethod.setCurrentIndex(2)
            elif Ystretch:
                self.tilingMethod.setCurrentIndex(3)
            elif Xuniform and Yuniform == False and object.tiles[0][0][0] == 0:
                self.tilingMethod.setCurrentIndex(4)
            elif Xuniform and Yuniform == False and object.tiles[height][0][0] == 0:
                self.tilingMethod.setCurrentIndex(5)
            elif Xuniform == False and Yuniform and object.tiles[0][0][0] == 0:
                self.tilingMethod.setCurrentIndex(6)
            elif Xuniform == False and Yuniform and object.tiles[0][width][0] == 0:
                self.tilingMethod.setCurrentIndex(7)


        self.tiles.setObject(object)

#        print 'Object {0}, Width: {1} / Height: {2}, Slope {3}/{4}'.format(index.row(), object.width, object.height, object.upperslope, object.lowerslope)
#        for row in object.tiles:
#            print 'Row: {0}'.format(row)
#        print ''

    @QtCore.pyqtSlot(int)
    def setTiling(self, listindex):
        global Tileset

        index = window.objectList.currentIndex()
        object = Tileset.objects[index.row()]


        if listindex == 0: # Repeat
            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()

        if listindex == 1: # Stretch Center

            if object.width < 3 and object.height < 3:
                reply = QtWidgets.QMessageBox.information(self, "Warning", "An object must be at least 3 tiles\nwide and 3 tiles tall to apply stretch center.")
                self.setObject(index)
                return

            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    if crow == 0 and ctile == 0:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    elif crow == 0 and ctile == object.width-1:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    elif crow == object.height-1 and ctile == object.width-1:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    elif crow == object.height-1 and ctile == 0:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    elif crow == 0 or crow == object.height-1:
                        object.tiles[crow][ctile] = (1, tile[1], tile[2])
                    elif ctile == 0 or ctile == object.width-1:
                        object.tiles[crow][ctile] = (2, tile[1], tile[2])
                    else:
                        object.tiles[crow][ctile] = (3, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()

        if listindex == 2: # Stretch X

            if object.width < 3:
                reply = QtWidgets.QMessageBox.information(self, "Warning", "An object must be at least 3 tiles\nwide to apply stretch X.")
                self.setObject(index)
                return

            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    if ctile == 0:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    elif ctile == object.width-1:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    else:
                        object.tiles[crow][ctile] = (1, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()

        if listindex == 3: # Stretch Y

            if object.height < 3:
                reply = QtWidgets.QMessageBox.information(self, "Warning", "An object must be at least 3 tiles\ntall to apply stretch Y.")
                self.setObject(index)
                return

            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    if crow == 0:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    elif crow == object.height-1:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    else:
                        object.tiles[crow][ctile] = (2, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()

        if listindex == 4: # Repeat Bottom

            if object.height < 2:
                reply = QtWidgets.QMessageBox.information(self, "Warning", "An object must be at least 2 tiles\ntall to apply repeat bottom.")
                self.setObject(index)
                return

            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    if crow == object.height-1:
                        object.tiles[crow][ctile] = (2, tile[1], tile[2])
                    else:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()

        if listindex == 5: # Repeat Top

            if object.height < 2:
                reply = QtWidgets.QMessageBox.information(self, "Warning", "An object must be at least 2 tiles\ntall to apply repeat top.")
                self.setObject(index)
                return

            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    if crow == 0:
                        object.tiles[crow][ctile] = (2, tile[1], tile[2])
                    else:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()

        if listindex == 6: # Repeat Left

            if object.width < 2:
                reply = QtWidgets.QMessageBox.information(self, "Warning", "An object must be at least 2 tiles\nwide to apply repeat left.")
                self.setObject(index)
                return

            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    if ctile == 0:
                        object.tiles[crow][ctile] = (1, tile[1], tile[2])
                    else:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()

        if listindex == 7: # Repeat Right

            if object.width < 2:
                reply = QtWidgets.QMessageBox.information(self, "Warning", "An object must be at least 2 tiles\nwide to apply repeat right.")
                self.setObject(index)
                return

            ctile = 0
            crow = 0

            for row in object.tiles:
                for tile in row:
                    if ctile == object.width-1:
                        object.tiles[crow][ctile] = (1, tile[1], tile[2])
                    else:
                        object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0, 0]
            object.lowerslope = [0, 0]
            self.tiles.slope = 0
            self.tiles.update()


        if listindex == 8: # Upward Slope
            ctile = 0
            crow = 0
            for row in object.tiles:
                for tile in row:
                    object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0x90, 1]
            object.lowerslope = [0x84, object.height - 1]
            self.tiles.slope = 1
            self.tiles.update()

        if listindex == 9: # Downward Slope
            ctile = 0
            crow = 0
            for row in object.tiles:
                for tile in row:
                    object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0x91, 1]
            object.lowerslope = [0x84, object.height - 1]
            self.tiles.slope = 1
            self.tiles.update()

        if listindex == 10: # Upward Reverse Slope
            ctile = 0
            crow = 0
            for row in object.tiles:
                for tile in row:
                    object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0x92, object.height - 1]
            object.lowerslope = [0x84, 1]
            self.tiles.slope = 0-(object.height-1)
            self.tiles.update()

        if listindex == 11: # Downward Reverse Slope
            ctile = 0
            crow = 0
            for row in object.tiles:
                for tile in row:
                    object.tiles[crow][ctile] = (0, tile[1], tile[2])
                    ctile += 1
                crow += 1
                ctile = 0

            object.upperslope = [0x93, object.height - 1]
            object.lowerslope = [0x84, 1]
            self.tiles.slope = 0-(object.height-1)
            self.tiles.update()


class tileWidget(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        self.tiles = []

        self.size = [1, 1]
        self.setMinimumSize(24, 24)

        self.slope = 0

        self.highlightedRect = QtCore.QRect()

        self.setAcceptDrops(True)
        self.object = 0


    def clear(self):
        self.tiles = []
        self.size = [1, 1] # [width, height]

        self.slope = 0
        self.highlightedRect = QtCore.QRect()

        self.update()


    def addColumn(self):
        global Tileset

        if self.object >= len(Tileset.objects):
            return

        if self.size[0] >= 24:
            return

        self.size[0] += 1
        self.setMinimumSize(self.size[0]*24, self.size[1]*24)

        img = QtGui.QImage(24, 24, QtGui.QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)

        for y in range(self.size[1]):
            self.tiles.insert(((y+1) * self.size[0]) -1, [self.size[0]-1, y, img])


        curObj = Tileset.objects[self.object]
        curObj.width += 1

        for row in curObj.tiles:
            row.append((0, 0, 0))

        self.update()
        self.updateList()


    def removeColumn(self):
        global Tileset

        if self.size[0] == 1:
            return

        for y in range(self.size[1]):
            self.tiles.pop(((y+1) * self.size[0])-(y+1))

        self.size[0] = self.size[0] - 1
        self.setMinimumSize(self.size[0]*24, self.size[1]*24)


        curObj = Tileset.objects[self.object]
        curObj.width -= 1

        for row in curObj.tiles:
            row.pop()

        self.update()
        self.updateList()


    def addRow(self):
        global Tileset

        if self.object >= len(Tileset.objects):
            return

        if self.size[1] >= 24:
            return

        self.size[1] += 1
        self.setMinimumSize(self.size[0]*24, self.size[1]*24)

        img = QtGui.QImage(24, 24, QtGui.QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)

        for x in range(self.size[0]):
            self.tiles.append([x, self.size[1]-1, img])

        curObj = Tileset.objects[self.object]
        curObj.height += 1

        curObj.tiles.append([])
        for i in range(0, curObj.width):
            curObj.tiles[len(curObj.tiles)-1].append((0, 0, 0))

        self.update()
        self.updateList()


    def removeRow(self):
        global Tileset

        if self.size[1] == 1:
            return

        for x in range(self.size[0]):
            self.tiles.pop()

        self.size[1] -= 1
        self.setMinimumSize(self.size[0]*24, self.size[1]*24)

        curObj = Tileset.objects[self.object]
        curObj.height -= 1

        curObj.tiles.pop()

        self.update()
        self.updateList()


    def setObject(self, object):
        self.clear()

        global Tileset

        self.size = [object.width, object.height]

        if not object.upperslope[1] == 0:
            if object.upperslope[0] & 2:
                self.slope = 0 - object.lowerslope[1]
            else:
                self.slope = object.upperslope[1]

        x = 0
        y = 0
        for row in object.tiles:
            for tile in row:
                if (Tileset.slot == 0) or ((tile[2] & 3) != 0):
                    self.tiles.append([x, y, Tileset.tiles[tile[1]].image])
                else:
                    img = QtGui.QImage(24, 24, QtGui.QImage.Format.Format_ARGB32)
                    img.fill(Qt.GlobalColor.transparent)
                    self.tiles.append([x, y, img])
                x += 1
            y += 1
            x = 0


        self.object = window.objectList.currentIndex().row()
        self.update()
        self.updateList()


    def contextMenuEvent(self, event):

        TileMenu = QtWidgets.QMenu(self)
        self.contX = event.x()
        self.contY = event.y()

        TileMenu.addAction('Set tile...', self.setTile)
        TileMenu.addAction('Set item...', self.setItem)

        TileMenu.exec(event.globalPos())


    def mousePressEvent(self, event):
        global Tileset

        if event.button() == 2:
            return

        if window.tileDisplay.selectedIndexes() == []:
            return

        currentSelected = window.tileDisplay.selectedIndexes()

        ix = 0
        iy = 0
        for modelItem in currentSelected:
            # Update yourself!
            centerPoint = self.contentsRect().center()

            tile = modelItem.row()
            upperLeftX = centerPoint.x() - self.size[0]*12
            upperLeftY = centerPoint.y() - self.size[1]*12

            lowerRightX = centerPoint.x() + self.size[0]*12
            lowerRightY = centerPoint.y() + self.size[1]*12


            x = int((event.pos().x() - upperLeftX)/24 + ix)
            y = int((event.pos().y() - upperLeftY)/24 + iy)

            if event.pos().x() < upperLeftX or event.pos().y() < upperLeftY or event.pos().x() > lowerRightX or event.pos().y() > lowerRightY:
                return

            try:
                self.tiles[(y * self.size[0]) + x][2] = Tileset.tiles[tile].image
                Tileset.objects[self.object].tiles[y][x] = (Tileset.objects[self.object].tiles[y][x][0], tile, Tileset.slot)
            except IndexError:
                pass

            ix += 1
            if self.size[0]-1 < ix:
                ix = 0
                iy += 1
            if iy > self.size[1]-1:
                break


        self.update()

        self.updateList()


    def updateList(self):
        # Update the list >.>
        object = window.objmodel.itemFromIndex(window.objectList.currentIndex())
        if not object: return


        tex = QtGui.QPixmap(self.size[0] * 24, self.size[1] * 24)
        tex.fill(Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(tex)

        Xoffset = 0
        Yoffset = 0

        for tile in self.tiles:
            painter.drawImage(tile[0]*24, tile[1]*24, tile[2])

        painter.end()

        object.setIcon(QtGui.QIcon(tex))

        window.objectList.update()



    def setTile(self):
        global Tileset

        dlg = self.setTileDialog()
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Do stuff
            centerPoint = self.contentsRect().center()

            upperLeftX = centerPoint.x() - self.size[0]*12
            upperLeftY = centerPoint.y() - self.size[1]*12

            tile = dlg.tile.value()
            tileset = dlg.tileset.currentIndex()

            x = int((self.contX - upperLeftX) / 24)
            y = int((self.contY - upperLeftY) / 24)

            if tileset != Tileset.slot:
                tex = QtGui.QImage(self.size[0] * 24, self.size[1] * 24, QtGui.QImage.Format.Format_ARGB32)
                tex.fill(Qt.GlobalColor.transparent)

                self.tiles[(y * self.size[0]) + x][2] = tex

            Tileset.objects[self.object].tiles[y][x] = (Tileset.objects[self.object].tiles[y][x][0], tile, tileset)

            self.update()
            self.updateList()


    class setTileDialog(QtWidgets.QDialog):

        def __init__(self):
            super().__init__()

            self.setWindowTitle('Set tiles')

            self.tileset = QtWidgets.QComboBox()
            self.tileset.addItems(['Pa0', 'Pa1', 'Pa2', 'Pa3'])

            self.tile = QtWidgets.QSpinBox()
            self.tile.setRange(0, 255)

            self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)

            self.layout = QtWidgets.QGridLayout()
            self.layout.addWidget(QtWidgets.QLabel('Tileset:'), 0,0,1,1, Qt.AlignmentFlag.AlignLeft)
            self.layout.addWidget(QtWidgets.QLabel('Tile:'), 0,3,1,1, Qt.AlignmentFlag.AlignLeft)
            self.layout.addWidget(self.tileset, 1, 0, 1, 2)
            self.layout.addWidget(self.tile, 1, 3, 1, 3)
            self.layout.addWidget(self.buttons, 2, 3)
            self.setLayout(self.layout)


    def setItem(self):
        global Tileset

        centerPoint = self.contentsRect().center()

        upperLeftX = centerPoint.x() - self.size[0]*12
        upperLeftY = centerPoint.y() - self.size[1]*12

        x = int((self.contX - upperLeftX) / 24)
        y = int((self.contY - upperLeftY) / 24)

        obj = Tileset.objects[self.object].tiles[y][x]

        dlg = self.setItemDialog(obj[2] >> 2)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Do stuff
            item = dlg.item.currentIndex()

            Tileset.objects[self.object].tiles[y][x] = (obj[0], obj[1], (obj[2] & 3) | (item << 2))

            self.update()
            self.updateList()


    class setItemDialog(QtWidgets.QDialog):

        def __init__(self, initialIndex=0):
            super().__init__()

            self.setWindowTitle('Set item')

            self.item = QtWidgets.QComboBox()
            self.item.addItems([
                'Item specified in tile behavior',
                'Fire Flower',
                'Star',
                'Coin',
                'Vine',
                'Spring',
                'Mini Mushroom',
                'Propeller Mushroom',
                'Penguin Suit',
                'Yoshi',
                'Ice Flower',
                'Unknown (11)',
                'Unknown (12)',
                'Unknown (13)',
                'Unknown (14)'])
            self.item.setCurrentIndex(initialIndex)

            self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)

            self.layout = QtWidgets.QHBoxLayout()
            self.vlayout = QtWidgets.QVBoxLayout()
            self.layout.addWidget(QtWidgets.QLabel('Item:'))
            self.layout.addWidget(self.item)
            self.vlayout.addLayout(self.layout)
            self.vlayout.addWidget(self.buttons)
            self.setLayout(self.vlayout)



    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)

        centerPoint = self.contentsRect().center()
        upperLeftX = centerPoint.x() - self.size[0]*12
        lowerRightX = centerPoint.x() + self.size[0]*12

        upperLeftY = centerPoint.y() - self.size[1]*12
        lowerRightY = centerPoint.y() + self.size[1]*12


        painter.fillRect(upperLeftX, upperLeftY, self.size[0] * 24, self.size[1]*24, QtGui.QColor(205, 205, 255))

        for x, y, pix in self.tiles:
            painter.drawImage(upperLeftX + (x * 24), upperLeftY + (y * 24), pix)

        if not self.slope == 0:
            pen = QtGui.QPen()
#            pen.setStyle(Qt.QDashLine)
            pen.setWidth(1)
            pen.setColor(Qt.GlobalColor.blue)
            painter.setPen(QtGui.QPen(pen))
            painter.drawLine(upperLeftX, upperLeftY + (abs(self.slope) * 24), lowerRightX, upperLeftY + (abs(self.slope) * 24))

            if self.slope > 0:
                main = 'Main'
                sub = 'Sub'
            elif self.slope < 0:
                main = 'Sub'
                sub = 'Main'

            font = painter.font()
            font.setPixelSize(8)
            font.setFamily('Monaco')
            painter.setFont(font)

            painter.drawText(upperLeftX+1, upperLeftY+10, main)
            painter.drawText(upperLeftX+1, upperLeftY + (abs(self.slope) * 24) + 9, sub)

        painter.end()



#############################################################################################
############################ Subclassed one dimension Item Model ############################


class PiecesModel(QtCore.QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.pixmaps = []

    def supportedDragActions(self):
        super().supportedDragActions()
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DecorationRole:
            return QtGui.QIcon(self.pixmaps[index.row()])

        if role == Qt.ItemDataRole.UserRole:
            return self.pixmaps[index.row()]

        return None

    def addPieces(self, pixmap):
        row = len(self.pixmaps)

        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.pixmaps.insert(row, pixmap)
        self.endInsertRows()

    def flags(self,index):
        if index.isValid():
            return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable |
                    Qt.ItemFlag.ItemIsDragEnabled)

    def clear(self):
        row = len(self.pixmaps)

        del self.pixmaps[:]


    def mimeTypes(self):
        return ['image/x-tile-piece']


    def mimeData(self, indexes):
        mimeData = QtCore.QMimeData()
        encodedData = QtCore.QByteArray()

        stream = QtCore.QDataStream(encodedData, QtCore.QIODevice.WriteOnly)

        for index in indexes:
            if index.isValid():
                pixmap = QtGui.QPixmap(self.data(index, Qt.ItemDataRole.UserRole))
                stream << pixmap

        mimeData.setData('image/x-tile-piece', encodedData)
        return mimeData


    def rowCount(self, parent):
        if parent.isValid():
            return 0
        else:
            return len(self.pixmaps)

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction



#############################################################################################
################## Python-based RGB5a3 Decoding code from my BRFNT program ##################


RGB4A3LUT = []
RGB4A3LUT_NoAlpha = []
def PrepareRGB4A3LUTs():
    global RGB4A3LUT, RGB4A3LUT_NoAlpha

    RGB4A3LUT = [None] * 0x10000
    RGB4A3LUT_NoAlpha = [None] * 0x10000
    for LUT, hasA in [(RGB4A3LUT, True), (RGB4A3LUT_NoAlpha, False)]:

        # RGB4A3
        for d in range(0x8000):
            if hasA:
                alpha = d >> 12
                alpha = alpha << 5 | alpha << 2 | alpha >> 1
            else:
                alpha = 0xFF
            red = ((d >> 8) & 0xF) * 17
            green = ((d >> 4) & 0xF) * 17
            blue = (d & 0xF) * 17
            LUT[d] = blue | (green << 8) | (red << 16) | (alpha << 24)

        # RGB555
        for d in range(0x8000):
            red = d >> 10
            red = red << 3 | red >> 2
            green = (d >> 5) & 0x1F
            green = green << 3 | green >> 2
            blue = d & 0x1F
            blue = blue << 3 | blue >> 2
            LUT[d + 0x8000] = blue | (green << 8) | (red << 16) | 0xFF000000

PrepareRGB4A3LUTs()


def RGB4A3Decode(tex, useAlpha=True):
    tx = 0; ty = 0
    iter = tex.__iter__()
    dest = [0] * 262144

    LUT = RGB4A3LUT if useAlpha else RGB4A3LUT_NoAlpha

    # Loop over all texels (of which there are 16384)
    for i in range(16384):
        temp1 = (i // 256) % 8
        if temp1 == 0 or temp1 == 7:
            # Skip every row of texels that is a multiple of 8 or (a
            # multiple of 8) - 1
            # Unrolled loop for performance.
            next(iter); next(iter); next(iter); next(iter)
            next(iter); next(iter); next(iter); next(iter)
            next(iter); next(iter); next(iter); next(iter)
            next(iter); next(iter); next(iter); next(iter)
            next(iter); next(iter); next(iter); next(iter)
            next(iter); next(iter); next(iter); next(iter)
            next(iter); next(iter); next(iter); next(iter)
            next(iter); next(iter); next(iter); next(iter)
        else:
            temp2 = i % 8
            if temp2 == 0 or temp2 == 7:
                # Skip every column of texels that is a multiple of 8
                # or (a multiple of 8) - 1
                # Unrolled loop for performance.
                next(iter); next(iter); next(iter); next(iter)
                next(iter); next(iter); next(iter); next(iter)
                next(iter); next(iter); next(iter); next(iter)
                next(iter); next(iter); next(iter); next(iter)
                next(iter); next(iter); next(iter); next(iter)
                next(iter); next(iter); next(iter); next(iter)
                next(iter); next(iter); next(iter); next(iter)
                next(iter); next(iter); next(iter); next(iter)
            else:
                # Actually render this texel
                for y in range(ty, ty+4):
                    for x in range(tx, tx+4):
                        dest[x + y * 1024] = LUT[next(iter) << 8 | next(iter)]

        # Move on to the next texel
        tx += 4
        if tx >= 1024: tx = 0; ty += 4

    # Convert the list of ARGB color values into a bytes object, and
    # then convert that into a QImage
    return QtGui.QImage(struct.pack('<262144I', *dest), 1024, 256, QtGui.QImage.Format.Format_ARGB32)


def RGB4A3Encode(tex):
    assert len(tex) == (1024 * 256 * 4)

    shorts = []
    colorCache = {}
    for ytile in range(0, 256, 4):
        for xtile in range(0, 1024, 4):
            for ypixel in range(ytile, ytile + 4):
                for xpixel in range(xtile, xtile + 4):

                    pixel = tex[ypixel * 4096 + xpixel * 4 : ypixel * 4096 + (xpixel + 1) * 4]

                    if pixel in colorCache:
                        rgba = colorCache[pixel]

                    else:
                        b, g, r, a = pixel

                        # See encodingTests.py for verification that these
                        # channel conversion formulas are 100% correct

                        # Note: we can't do
                        # if a < 19:
                        #     rgba = 0
                        # for speed, because that causes an issue with
                        # texture filtering that results in graphics
                        # having faint black borders in-game

                        if a < 238:  # RGB4A3
                            a = ((a + 18) << 1) // 73
                            r = (r + 8) // 17
                            g = (g + 8) // 17
                            b = (b + 8) // 17

                            # 0aaarrrrggggbbbb
                            rgba = (a << 12) | (r << 8) | (g << 4) | b

                        else:  # RGB555
                            r = ((r + 4) << 2) // 33
                            g = ((g + 4) << 2) // 33
                            b = ((b + 4) << 2) // 33

                            # 1rrrrrgggggbbbbb
                            rgba = 0x8000 | (r << 10) | (g << 5) | b

                        colorCache[pixel] = rgba

                    shorts.append(rgba)

                    if xtile % 32 == 0 or xtile % 32 == 28:
                        shorts.append(rgba)
                        shorts.append(rgba)
                        shorts.append(rgba)
                        break
                if ytile % 32 == 0 or ytile % 32 == 28:
                    shorts.extend(shorts[-4:])
                    shorts.extend(shorts[-8:])
                    break

    return struct.pack('>262144H', *shorts)


#############################################################################################
######################### Function to fix black borders around tiles ########################


def color_transparent_pixels_around_edges_24_24(data: bytearray) -> None:
    """
    THIS FUNCTION IS AUTO-GENERATED SOURCE CODE!
    See make_color_transparent_pixels_around_edges.py.

    Find fully-transparent pixels that border non-fully-transparent
    pixels, and set their RGB channels to the average of those of their
    neighboring non-fully-transparent pixels. This solves the
    longstanding "black outlines around tile edges" bug.

    "data" should be BGRA8 bytes for an image of size 24x24.
    """
    if len(data) != 0x900:
        raise ValueError(f'expected 0x900 bytes, got {len(data):#x}')

    # Redefine some globals as locals for faster lookups
    sum_loc, len_loc, range_loc = sum, len, range

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Top-left corner

    if not data[0x3]:
        neighbors = []

        # (x + 1, y)
        if data[0x7]:
            neighbors.append(data[0x4 : 0x7])

        # (x + 1, y + 1)
        if data[0x67]:
            neighbors.append(data[0x64 : 0x67])

        # (x, y + 1)
        if data[0x63]:
            neighbors.append(data[0x60 : 0x63])

        if neighbors:
            ln = len_loc(neighbors)
            data[0x0] = sum_loc(n[0] for n in neighbors) // ln
            data[0x1] = sum_loc(n[1] for n in neighbors) // ln
            data[0x2] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Top-right corner

    if not data[0x5f]:
        neighbors = []

        # (x, y + 1)
        if data[0xbf]:
            neighbors.append(data[0xbc : 0xbf])

        # (x - 1, y + 1)
        if data[0xbb]:
            neighbors.append(data[0xb8 : 0xbb])

        # (x - 1, y)
        if data[0x5b]:
            neighbors.append(data[0x58 : 0x5b])

        if neighbors:
            ln = len_loc(neighbors)
            data[0x5c] = sum_loc(n[0] for n in neighbors) // ln
            data[0x5d] = sum_loc(n[1] for n in neighbors) // ln
            data[0x5e] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Bottom-left corner

    if not data[0x8a3]:
        neighbors = []

        # (x, y - 1)
        if data[0x843]:
            neighbors.append(data[0x840 : 0x843])

        # (x + 1, y - 1)
        if data[0x847]:
            neighbors.append(data[0x844 : 0x847])

        # (x + 1, y)
        if data[0x8a7]:
            neighbors.append(data[0x8a4 : 0x8a7])

        if neighbors:
            ln = len_loc(neighbors)
            data[0x8a0] = sum_loc(n[0] for n in neighbors) // ln
            data[0x8a1] = sum_loc(n[1] for n in neighbors) // ln
            data[0x8a2] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Bottom-right corner

    if not data[0x8ff]:
        neighbors = []

        # (x - 1, y)
        if data[0x8fb]:
            neighbors.append(data[0x8f8 : 0x8fb])

        # (x - 1, y - 1)
        if data[0x89b]:
            neighbors.append(data[0x898 : 0x89b])

        # (x, y - 1)
        if data[0x89f]:
            neighbors.append(data[0x89c : 0x89f])

        if neighbors:
            ln = len_loc(neighbors)
            data[0x8fc] = sum_loc(n[0] for n in neighbors) // ln
            data[0x8fd] = sum_loc(n[1] for n in neighbors) // ln
            data[0x8fe] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Top edge, except corners

    for offset in range_loc(0x7, 0x5f, 0x4):
        if not data[offset]:
            neighbors = []

            # (x + 1, y)
            offset += 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x + 1, y + 1)
            offset += 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x, y + 1)
            offset -= 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x - 1, y + 1)
            offset -= 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x - 1, y)
            offset -= 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            if neighbors:
                ln = len_loc(neighbors)
                data[offset + 1] = sum_loc(n[0] for n in neighbors) // ln
                data[offset + 2] = sum_loc(n[1] for n in neighbors) // ln
                data[offset + 3] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Bottom edge, except corners

    for offset in range_loc(0x8a7, 0x8ff, 0x4):
        if not data[offset]:
            neighbors = []

            # (x - 1, y)
            offset -= 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x - 1, y - 1)
            offset -= 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x, y - 1)
            offset += 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x + 1, y - 1)
            offset += 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x + 1, y)
            offset += 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            if neighbors:
                ln = len_loc(neighbors)
                data[offset - 7] = sum_loc(n[0] for n in neighbors) // ln
                data[offset - 6] = sum_loc(n[1] for n in neighbors) // ln
                data[offset - 5] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Left edge, except corners

    for offset in range_loc(0x63, 0x8a3, 0x60):
        if not data[offset]:
            neighbors = []

            # (x, y - 1)
            offset -= 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x + 1, y - 1)
            offset += 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x + 1, y)
            offset += 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x + 1, y + 1)
            offset += 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x, y + 1)
            offset -= 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            if neighbors:
                offset -= 0x63
                ln = len_loc(neighbors)
                data[offset] = sum_loc(n[0] for n in neighbors) // ln
                data[offset + 1] = sum_loc(n[1] for n in neighbors) // ln
                data[offset + 2] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Right edge, except corners

    for offset in range_loc(0xbf, 0x8ff, 0x60):
        if not data[offset]:
            neighbors = []

            # (x, y + 1)
            offset += 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x - 1, y + 1)
            offset -= 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x - 1, y)
            offset -= 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x - 1, y - 1)
            offset -= 0x60
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            # (x, y - 1)
            offset += 0x4
            if data[offset]:
                neighbors.append(data[offset - 3 : offset])

            if neighbors:
                offset += 0x5d
                ln = len_loc(neighbors)
                data[offset] = sum_loc(n[0] for n in neighbors) // ln
                data[offset + 1] = sum_loc(n[1] for n in neighbors) // ln
                data[offset + 2] = sum_loc(n[2] for n in neighbors) // ln

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Main body

    for row_start_offs in range_loc(0x67, 0x8a7, 0x60):
        for offset in range_loc(row_start_offs, row_start_offs + 0x58, 0x4):
            if not data[offset]:  # (fully transparent pixel)
                neighbors = []

                # (x, y - 1)
                offset -= 0x60
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                # (x + 1, y - 1)
                offset += 0x4
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                # (x + 1, y)
                offset += 0x60
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                # (x + 1, y + 1)
                offset += 0x60
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                # (x, y + 1)
                offset -= 0x4
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                # (x - 1, y + 1)
                offset -= 0x4
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                # (x - 1, y)
                offset -= 0x60
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                # (x - 1, y - 1)
                offset -= 0x60
                if data[offset]:
                    neighbors.append(data[offset - 3 : offset])

                if neighbors:
                    offset += 0x61
                    ln = len_loc(neighbors)
                    data[offset] = sum_loc(n[0] for n in neighbors) // ln
                    data[offset + 1] = sum_loc(n[1] for n in neighbors) // ln
                    data[offset + 2] = sum_loc(n[2] for n in neighbors) // ln


#############################################################################################
############ Main Window Class. Takes care of menu functions and widget creation ############


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.alpha = True

        global Tileset
        Tileset = TilesetClass()

        self.name = ''

        self.setupMenus()
        self.setupWidgets()

        self.setuptile()

        self.newTileset()

        self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Fixed))
        self.setWindowTitle("New Tileset")


    def setuptile(self):
        self.tileWidget.tiles.clear()
        self.model.clear()

        if self.alpha == True:
            for tile in Tileset.tiles:
                self.model.addPieces(QtGui.QPixmap.fromImage(tile.image))
        else:
            for tile in Tileset.tiles:
                self.model.addPieces(QtGui.QPixmap.fromImage(tile.noalpha))


    def newTileset(self):
        '''Creates a new, blank tileset'''

        global Tileset
        Tileset.clear()
        Tileset = TilesetClass()

        EmptyImg = QtGui.QImage(24, 24, QtGui.QImage.Format.Format_ARGB32)
        EmptyImg.fill(Qt.GlobalColor.black)

        for i in range(256):
            Tileset.addTile(EmptyImg, EmptyImg)

        self.setuptile()
        self.setWindowTitle('New Tileset')


    def openTileset(self):
        '''Asks the user for a filename, then calls openTilesetFromPath().'''

        defaultPath = settings.value('MostRecentArcPath', '')

        path = QtWidgets.QFileDialog.getOpenFileName(self, "Open NSMBW Tileset", defaultPath,
                    "Tileset Files (*.arc)")[0]

        if path:
            self.openTilesetFromPath(path)
            settings.setValue('MostRecentArcPath', os.path.dirname(path))


    def openTilesetFromPath(self, path):
        '''Opens a Nintendo tileset arc and parses the heck out of it.'''
        self.setWindowTitle(os.path.basename(path))
        Tileset.clear()

        name = path[str(path).rfind('/')+1:-4]

        with open(path,'rb') as file:
            data = file.read()

        arc = archive.U8()
        arc._load(data)

        Image = None
        behaviourdata = None
        objstrings = None
        metadata = None

        for key, value in arc.files:
            if value is None:
                continue
            elif key.startswith('BG_tex/') and key.endswith('_tex.bin.LZ'):
                Image = arc[key]
            elif key.startswith('BG_chk/d_bgchk_') and key.endswith('.bin'):
                behaviourdata = arc[key]
            elif key.startswith('BG_unt/') and key.endswith('_hd.bin'):
                metadata = arc[key]
            elif key.startswith('BG_unt/') and key.endswith('.bin'):
                objstrings = arc[key]
            else:
                Tileset.unknownFiles[key] = arc[key]


        if (Image is None) or (behaviourdata is None) or (objstrings is None) or (metadata is None):
            QtWidgets.QMessageBox.warning(None, 'Error',  'Error - the necessary files were not found.\n\nNot a valid tileset, sadly.')
            return

        # Stolen from Reggie! Loads the Image Data.
        if HaveNSMBLib:
            tiledata = nsmblib.decompress11LZS(Image)
            if hasattr(nsmblib, 'decodeTilesetNoPremultiplication'):
                argbdata = nsmblib.decodeTilesetNoPremultiplication(tiledata)
                tileImage = QtGui.QImage(argbdata, 1024, 256, QtGui.QImage.Format.Format_ARGB32)
            else:
                tileImage = RGB4A3Decode(tiledata)

            if hasattr(nsmblib, 'decodeTilesetNoPremultiplicationNoAlpha'):
                rgbdata = nsmblib.decodeTilesetNoPremultiplicationNoAlpha(tiledata)
                noalphaImage = QtGui.QImage(rgbdata, 1024, 256, QtGui.QImage.Format.Format_ARGB32)
            else:
                noalphaImage = RGB4A3Decode(tiledata, False)
        else:
            lz = lz77.LZS11()
            decomp = lz.Decompress11LZS(Image)
            tileImage = RGB4A3Decode(decomp)
            noalphaImage = RGB4A3Decode(decomp, False)

        # Loads Tile Behaviours

        behaviours = []
        for entry in range(256):
            behaviours.append(struct.unpack_from('>8B', behaviourdata, entry*8))


        # Makes us some nice Tile Classes!
        Xoffset = 4
        Yoffset = 4
        for i in range(256):
            Tileset.addTile(tileImage.copy(Xoffset,Yoffset,24,24), noalphaImage.copy(Xoffset,Yoffset,24,24), behaviours[i])
            Xoffset += 32
            if Xoffset >= 1024:
                Xoffset = 4
                Yoffset += 32


        # Load Objects

        meta = []
        for i in range(len(metadata) // 4):
            meta.append(struct.unpack_from('>H2B', metadata, i * 4))

        tilelist = [[]]
        upperslope = [0, 0]
        lowerslope = [0, 0]
        byte = 0

        for entry in meta:
            offset = entry[0]
            byte = struct.unpack_from('>B', objstrings, offset)[0]
            row = 0

            while byte != 0xFF:

                if byte == 0xFE:
                    tilelist.append([])

                    if (upperslope[0] != 0) and (lowerslope[0] == 0):
                        upperslope[1] = upperslope[1] + 1

                    if lowerslope[0] != 0:
                        lowerslope[1] = lowerslope[1] + 1

                    offset += 1
                    byte = struct.unpack_from('>B', objstrings, offset)[0]

                elif (byte & 0x80):

                    if upperslope[0] == 0:
                        upperslope[0] = byte
                    else:
                        lowerslope[0] = byte

                    offset += 1
                    byte = struct.unpack_from('>B', objstrings, offset)[0]

                else:
                    tilelist[len(tilelist)-1].append(struct.unpack_from('>3B', objstrings, offset))

                    offset += 3
                    byte = struct.unpack_from('>B', objstrings, offset)[0]

            tilelist.pop()

            if (upperslope[0] & 0x80) and (upperslope[0] & 0x2):
                for i in range(lowerslope[1]):
                    pop = tilelist.pop()
                    tilelist.insert(0, pop)

            Tileset.addObject(entry[2], entry[1], upperslope, lowerslope, tilelist)

            tilelist = [[]]
            upperslope = [0, 0]
            lowerslope = [0, 0]

        if Tileset.objects:
            Tileset.slot = Tileset.objects[0].tiles[0][0][2] & 3
        else:
            Tileset.slot = 1
        self.tileWidget.tilesetType.setText('Pa{0}'.format(Tileset.slot))

        self.setuptile()
        SetupObjectModel(self.objmodel, Tileset.objects, Tileset.tiles)

        self.name = path


    def openImage(self):
        '''Opens an Image from png, and creates a new tileset from it.'''

        defaultPath = settings.value('MostRecentImagePath', '')

        path = QtWidgets.QFileDialog.getOpenFileName(self, "Open Image", defaultPath,
                    "Image Files (*.png)")[0]
        if not path: return

        settings.setValue('MostRecentImagePath', os.path.dirname(path))

        tileImage = QtGui.QImage(path)
        if tileImage.isNull():
            QtWidgets.QMessageBox.warning(self, "Open Image",
                    "The image file could not be loaded.",
                    QtWidgets.QMessageBox.StandardButton.Cancel)
            return

        if tileImage.width() != 384 or tileImage.height() != 384:
            QtWidgets.QMessageBox.warning(self, "Open Image",
                    "The image was not the proper dimensions."
                    "Please resize the image to 384x384 pixels.",
                    QtWidgets.QMessageBox.StandardButton.Cancel)
            return

        if tileImage.format() != QtGui.QImage.Format.Format_ARGB32:
            tileImage.convertTo(QtGui.QImage.Format.Format_ARGB32)

        if not hasattr(self, 'extendEdges'):
            self.extendEdges = True
            self.skipExtendEdgesDialog = False
            isFirstTime = True
        else:
            isFirstTime = False

        tileImagesRaw = []
        tileImagesFixed = []
        tileImagesRawNoAlpha = []
        tileImagesFixedNoAlpha = []

        x = 0
        y = 0
        for i in range(256):
            img = tileImage.copy(x*24,y*24,24,24)

            bgra = bytearray(img.bits().asstring(24 * 24 * 4))

            # Skip this if it's not going to be used for anything
            if not self.skipExtendEdgesDialog or not self.extendEdges:
                bgra_bk = bytearray(bgra)

                tileImagesRaw.append(QtGui.QImage(bytes(bgra), 24, 24, QtGui.QImage.Format.Format_ARGB32))
                for offs in range(3, 24 * 24 * 4, 4):
                    bgra[offs] = 0xff
                tileImagesRawNoAlpha.append(QtGui.QImage(bytes(bgra), 24, 24, QtGui.QImage.Format.Format_ARGB32))

                bgra = bgra_bk

            # Ditto
            if not self.skipExtendEdgesDialog or self.extendEdges:
                color_transparent_pixels_around_edges_24_24(bgra)

                tileImagesFixed.append(QtGui.QImage(bytes(bgra), 24, 24, QtGui.QImage.Format.Format_ARGB32))
                for offs in range(3, 24 * 24 * 4, 4):
                    bgra[offs] = 0xff
                tileImagesFixedNoAlpha.append(QtGui.QImage(bytes(bgra), 24, 24, QtGui.QImage.Format.Format_ARGB32))

            x += 1
            if x >= 16:
                y += 1
                x = 0

        # Show dialog if needed
        if not self.skipExtendEdgesDialog:
            fullRaw = QtGui.QImage(384, 384, QtGui.QImage.Format.Format_ARGB32)
            painterRaw = QtGui.QPainter(fullRaw)
            fullFixed = QtGui.QImage(384, 384, QtGui.QImage.Format.Format_ARGB32)
            painterFixed = QtGui.QPainter(fullFixed)

            Xoffset = Yoffset = 0
            for raw, fixed in zip(tileImagesRawNoAlpha, tileImagesFixedNoAlpha):
                painterRaw.drawImage(Xoffset, Yoffset, raw)
                painterFixed.drawImage(Xoffset, Yoffset, fixed)
                Xoffset += 24
                if Xoffset >= 384:
                    Xoffset = 0
                    Yoffset += 24

            del painterRaw, painterFixed

            dlg = self.extendEdgesDialog(fullRaw, fullFixed, self.extendEdges, isFirstTime)

            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                self.extendEdges = dlg.doFix
                self.skipExtendEdgesDialog = dlg.rememberCheckbox.isChecked()
            else:
                return

        # Apply new tile images
        if self.extendEdges:
            for i in range(256):
                Tileset.tiles[i].image = tileImagesFixed[i]
                Tileset.tiles[i].noalpha = tileImagesFixedNoAlpha[i]
        else:
            for i in range(256):
                Tileset.tiles[i].image = tileImagesRaw[i]
                Tileset.tiles[i].noalpha = tileImagesRawNoAlpha[i]

        self.setuptile()


    class extendEdgesDialog(QtWidgets.QDialog):
        class linkedScrollArea(QtWidgets.QScrollArea):
            '''A QScrollArea that synchronizes its scrolling with another one (self.other)'''
            updating = False

            def __init__(self, parent=None):
                super().__init__(parent)
                self.horizontalScrollBar().valueChanged.connect(self.handleHorzScroll)
                self.verticalScrollBar().valueChanged.connect(self.handleVertScroll)

            def handleHorzScroll(self, value):
                if self.updating: return
                self.updating = True
                self.other.horizontalScrollBar().setValue(value)
                self.updating = False

            def handleVertScroll(self, value):
                if self.updating: return
                self.updating = True
                self.other.verticalScrollBar().setValue(value)
                self.updating = False

        def __init__(self, rawImage, fixedImage, defaultFixed, defaultRemember):
            super().__init__()

            self.setWindowTitle('Choose import options')

            self.textLabel = QtWidgets.QLabel(
                "When exporting, many image editing tools set the RGB values for transparent pixels to black or other arbitrary colors, since it's irrelevant in most cases."
                " However, with the Wii's texture filtering, this can result in faint dark outlines around tiles."
                "\n\nPuzzle can try to automatically correct for this, or you can keep the existing colors in your image."
                '\n\nYou should choose "Fix colors of transparent pixels" in most cases unless you know what you\'re doing.')
            self.textLabel.setWordWrap(True)

            SCALE = 5

            self.rawLabel = QtWidgets.QLabel(self)
            self.rawLabel.setPixmap(QtGui.QPixmap.fromImage(rawImage).scaledToWidth(384 * SCALE))
            self.fixedLabel = QtWidgets.QLabel(self)
            self.fixedLabel.setPixmap(QtGui.QPixmap.fromImage(fixedImage).scaledToWidth(384 * SCALE))

            self.rawScrollArea = self.linkedScrollArea(self)
            self.rawScrollArea.setWidget(self.rawLabel)
            self.fixedScrollArea = self.linkedScrollArea(self)
            self.fixedScrollArea.setWidget(self.fixedLabel)
            self.rawScrollArea.other = self.fixedScrollArea
            self.fixedScrollArea.other = self.rawScrollArea

            self.rawTitleLabel = QtWidgets.QLabel('<b>Original image without alpha channel:</b>')
            self.fixedTitleLabel = QtWidgets.QLabel('<b>Fixed image without alpha channel:</b>')

            self.rememberCheckbox = QtWidgets.QCheckBox("Don't ask again for this session")
            self.rememberCheckbox.setChecked(defaultRemember)

            self.buttons = QtWidgets.QDialogButtonBox()
            self.buttons.addButton('Preserve colors of transparent pixels', QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
            self.fixedButton = QtWidgets.QPushButton('Fix colors of transparent pixels', self)
            self.fixedButton.setDefault(True)
            self.buttons.addButton(self.fixedButton, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
            self.buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)
            self.buttons.clicked.connect(self.handleClicked)

            self.layout = QtWidgets.QGridLayout()
            self.layout.addWidget(self.textLabel, 0, 0, 1, 2)
            self.layout.setRowMinimumHeight(1, 32)
            self.layout.addWidget(self.rawTitleLabel, 2, 0, 1, 1, Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.fixedTitleLabel, 2, 1, 1, 1, Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.rawScrollArea, 3, 0)
            self.layout.addWidget(self.fixedScrollArea, 3, 1)
            self.layout.setRowMinimumHeight(4, 32)
            self.layout.addWidget(self.rememberCheckbox, 5, 0, 1, 2, Qt.AlignmentFlag.AlignRight)
            self.layout.addWidget(self.buttons, 6, 0, 1, 2)
            self.setLayout(self.layout)

        def handleClicked(self, button):
            self.doFix = (button is self.fixedButton)


    def saveImage(self):

        defaultPath = settings.value('MostRecentImagePath', '')

        fn = QtWidgets.QFileDialog.getSaveFileName(self, 'Choose a new filename', defaultPath, '.png (*.png)')[0]
        if not fn: return

        settings.setValue('MostRecentImagePath', os.path.dirname(fn))

        tex = QtGui.QImage(384, 384, QtGui.QImage.Format.Format_ARGB32)
        tex.fill(Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(tex)

        Xoffset = 0
        Yoffset = 0

        for tile in Tileset.tiles:
            painter.drawImage(Xoffset, Yoffset, tile.image)
            Xoffset += 24
            if Xoffset >= 384:
                Xoffset = 0
                Yoffset += 24

        painter.end()

        tex.save(fn)


    def saveTileset(self):
        if not self.name:
            self.saveTilesetAs()
            return

        outdata = self.saving(os.path.basename(self.name)[:-4])

        if outdata is not None:
            fn = self.name
            with open(fn, 'wb') as f:
                f.write(outdata)


    def saveTilesetAs(self):

        defaultPath = settings.value('MostRecentArcPath', '')

        fn = QtWidgets.QFileDialog.getSaveFileName(self, 'Choose a new filename', defaultPath, '.arc (*.arc)')[0]
        if not fn: return

        settings.setValue('MostRecentArcPath', os.path.dirname(fn))

        outdata = self.saving(os.path.basename(str(fn))[:-4])

        if outdata is not None:
            self.name = fn
            self.setWindowTitle(os.path.basename(str(fn)))

            with open(fn, 'wb') as f:
                f.write(outdata)


    def saving(self, name):

        # Prepare tiles, objects, object metadata, and textures and stuff into buffers.

        textureBuffer = self.PackTexture()

        if textureBuffer is None:
            # The user canceled the saving process in the "use nsmblib?" dialog
            return None

        tileBuffer = self.PackTiles()
        objectBuffers = self.PackObjects()
        objectBuffer = objectBuffers[0]
        objectMetaBuffer = objectBuffers[1]


        # Make an arc and pack up the files!

        # NOTE: adding the files/folders to the U8 object in
        # alphabetical order is a simple workaround for a wii.py... bug?
        # unintuitive quirk? Whatever. Fixes one of the issues listed
        # in GitHub issue #3 (in the RoadrunnerWMC/Puzzle-Updated repo)

        arcFiles = {}
        arcFiles['BG_tex'] = None
        arcFiles['BG_tex/{0}_tex.bin.LZ'.format(name)] = textureBuffer

        arcFiles['BG_chk'] = None
        arcFiles['BG_chk/d_bgchk_{0}.bin'.format(name)] = tileBuffer

        arcFiles['BG_unt'] = None
        arcFiles['BG_unt/{0}.bin'.format(name)] = objectBuffer
        arcFiles['BG_unt/{0}_hd.bin'.format(name)] = objectMetaBuffer

        arcFiles.update(Tileset.unknownFiles)

        arc = archive.U8()
        for name in sorted(arcFiles):
            arc[name] = arcFiles[name]
        return arc._dump()


    def PackTexture(self):

        tex = bytearray(1024 * 256 * 4)
        stride = 1024 * 4

        for i, tile in enumerate(Tileset.tiles):
            tile_bytes = bytearray(tile.image.bits().asstring(24 * 24 * 4))

            row, col = divmod(i, 32)
            dest_offs = row * 32 * stride + col * (32 * 4)

            for src_y in range(24):
                row = tile_bytes[src_y * (24 * 4) : (src_y + 1) * (24 * 4)]

                # Clamp left/right pixels of the row
                row = row[:4] * 4 + row + row[-4:] * 4

                tex[dest_offs : dest_offs + (32 * 4)] = row
                dest_offs += stride
                if src_y == 0 or src_y == 23:
                    # Clamp top/bottom rows of the tile
                    tex[dest_offs : dest_offs + (32 * 4)] = row
                    dest_offs += stride
                    tex[dest_offs : dest_offs + (32 * 4)] = row
                    dest_offs += stride
                    tex[dest_offs : dest_offs + (32 * 4)] = row
                    dest_offs += stride
                    tex[dest_offs : dest_offs + (32 * 4)] = row
                    dest_offs += stride

        tex = bytes(tex)

        tex = RGB4A3Encode(tex)

        useNSMBLib = HaveNSMBLib and hasattr(nsmblib, 'compress11LZS')

        if useNSMBLib:
            # There are two versions of nsmblib floating around: the original
            # one, where the compression doesn't work correctly, and a fixed one
            # with correct compression.
            # We're going to show a warning to the user if they have the broken one installed.
            # To detect which one it is, we use the following test data:
            COMPRESSION_TEST = b'\0\1\0\0\0\0\0\0\0\1\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'

            # The original broken algorithm compresses that incorrectly.
            # So let's compress it, and then decompress it, and see if we
            # got the right output.
            compressionWorking = (nsmblib.decompress11LZS(nsmblib.compress11LZS(COMPRESSION_TEST)) == COMPRESSION_TEST)

            if not compressionWorking:
                # NSMBLib is available, but only with the broken compression algorithm,
                # so the user can choose whether to use it or not

                items = ['Slow compression, good quality', 'Fast compression, but the image gets damaged']

                item, ok = QtWidgets.QInputDialog.getItem(self, 'Choose compression method',
                    'Two methods of compression are available. Choose<br />'
                    '"fast compression" for rapid testing. Choose "slow<br />'
                    'compression" for releases.<br />'
                    '<br />'
                    'To fix the fast compression, download and install<br />'
                    'NSMBLib-Updated:<br />'
                    '"pip install --force-reinstall --no-cache-dir nsmblib"',
                    items, 0, False)
                if not ok:
                    return None

                if item == "Slow compression, good quality":
                    useNSMBLib = False
                else:
                    useNSMBLib = True

        else:
            # NSMBLib is not available, so we have to use the Python version
            useNSMBLib = False

        if useNSMBLib:
            return nsmblib.compress11LZS(bytes(tex))
        else:
            return lz77.LZS11().Compress11LZS(tex)


    def PackTiles(self):
        offset = 0
        tilespack = struct.Struct('>8B')
        Tilebuffer = create_string_buffer(2048)
        for tile in Tileset.tiles:
            tilespack.pack_into(Tilebuffer, offset, tile.byte0, tile.byte1, tile.byte2, tile.byte3, tile.byte4, tile.byte5, tile.byte6, tile.byte7)
            offset += 8

        return Tilebuffer.raw


    def PackObjects(self):
        objectStrings = []

        o = 0
        for object in Tileset.objects:


            # Slopes
            if object.upperslope[0] != 0:

                # Reverse Slopes
                if object.upperslope[0] & 0x2:
                    a = struct.pack('>B', object.upperslope[0])

                    if object.height == 1:
                        iterationsA = 0
                        iterationsB = 1
                    else:
                        iterationsA = object.upperslope[1]
                        iterationsB = object.lowerslope[1] + object.upperslope[1]

                    for row in range(iterationsA, iterationsB):
                        for tile in object.tiles[row]:
                            a = a + struct.pack('>BBB', tile[0], tile[1], tile[2])
                        a = a + b'\xfe'

                    if object.height > 1:
                        a = a + struct.pack('>B', object.lowerslope[0])

                        for row in range(0, object.upperslope[1]):
                            for tile in object.tiles[row]:
                                a = a + struct.pack('>BBB', tile[0], tile[1], tile[2])
                            a = a + b'\xfe'

                    a = a + b'\xff'

                    objectStrings.append(a)


                # Regular Slopes
                else:
                    a = struct.pack('>B', object.upperslope[0])

                    for row in range(0, object.upperslope[1]):
                        for tile in object.tiles[row]:
                            a = a + struct.pack('>BBB', tile[0], tile[1], tile[2])
                        a = a + b'\xfe'

                    if object.height > 1:
                        a = a + struct.pack('>B', object.lowerslope[0])

                        for row in range(object.upperslope[1], object.height):
                            for tile in object.tiles[row]:
                                a = a + struct.pack('>BBB', tile[0], tile[1], tile[2])
                            a = a + b'\xfe'

                    a = a + b'\xff'

                    objectStrings.append(a)


            # Not slopes!
            else:
                a = b''

                for tilerow in object.tiles:
                    for tile in tilerow:
                        a = a + struct.pack('>BBB', tile[0], tile[1], tile[2])

                    a = a + b'\xfe'

                a = a + b'\xff'

                objectStrings.append(a)

            o += 1

        Objbuffer = b''
        Metabuffer = b''
        i = 0
        for a in objectStrings:
            Metabuffer = Metabuffer + struct.pack('>H2B', len(Objbuffer), Tileset.objects[i].width, Tileset.objects[i].height)
            Objbuffer = Objbuffer + a

            i += 1

        return (Objbuffer, Metabuffer)



    def setupMenus(self):
        fileMenu = self.menuBar().addMenu("&File")

        pixmap = QtGui.QPixmap(60,60)
        pixmap.fill(Qt.GlobalColor.black)
        icon = QtGui.QIcon(pixmap)

        if QtCompatVersion < (6,0,0):
            QAction = QtWidgets.QAction
        else:
            QAction = QtGui.QAction

        def addAction(menu, text, slot, shortcut=None, icon=None):

            if icon is not None:
                act = QAction(icon, text, self)
            else:
                act = QAction(text, self)

            act.triggered.connect(slot)

            if shortcut is not None:
                act.setShortcut(shortcut)

            menu.addAction(act)
            return act

        addAction(fileMenu, "New", self.newTileset, QtGui.QKeySequence.StandardKey.New, icon)
        addAction(fileMenu, "Open...", self.openTileset, QtGui.QKeySequence.StandardKey.Open)
        addAction(fileMenu, "Import Image...", self.openImage, QtGui.QKeySequence('Ctrl+I'))
        addAction(fileMenu, "Export Image...", self.saveImage, QtGui.QKeySequence('Ctrl+E'))
        addAction(fileMenu, "Save", self.saveTileset, QtGui.QKeySequence.StandardKey.Save)
        addAction(fileMenu, "Save as...", self.saveTilesetAs, QtGui.QKeySequence.StandardKey.SaveAs)
        addAction(fileMenu, "Quit", self.close, QtGui.QKeySequence('Ctrl-Q'))

        fileMenu.addSeparator()

        if HaveNSMBLib:
            if hasattr(nsmblib, 'getUpdatedVersion'):
                updatedVersion = nsmblib.getUpdatedVersion()
                updatedVersionStr = '%04d.%02d.%02d.%d' % (updatedVersion // 1000000,
                                                           (updatedVersion // 10000) % 100,
                                                           (updatedVersion // 100) % 100,
                                                           updatedVersion % 100)
                nsmblib_msg = 'Using NSMBLib-Updated %s' % (updatedVersionStr)
            else:
                nsmblib_msg = 'Using NSMBLib %d' % nsmblib.getVersion()
        else:
            nsmblib_msg = 'Not using NSMBLib'

        pyVerAct = fileMenu.addAction('Using Python %d.%d.%d' % sys.version_info[:3])
        pyVerAct.setEnabled(False)
        bindingsVerAct = fileMenu.addAction('Using %s %d.%d.%d' % (QtName, QtBindingsVersion[0], QtBindingsVersion[1], QtBindingsVersion[2]))
        bindingsVerAct.setEnabled(False)
        qtVerAct = fileMenu.addAction('Using Qt %d.%d.%d' % QtCompatVersion)
        qtVerAct.setEnabled(False)
        nsmblibVerAct = fileMenu.addAction(nsmblib_msg)
        nsmblibVerAct.setEnabled(False)

        taskMenu = self.menuBar().addMenu("&Tasks")
        addAction(taskMenu, "Set Tileset Slot...", self.setSlot, QtGui.QKeySequence('Ctrl+T'))
        addAction(taskMenu, "Toggle Alpha", self.toggleAlpha, QtGui.QKeySequence('Ctrl+Shift+A'))
        addAction(taskMenu, "Toggle Dark Mode", self.toggleDarkMode)
        addAction(taskMenu, "Clear Collision Data", self.clearCollisions, QtGui.QKeySequence('Ctrl+Shift+Backspace'))
        addAction(taskMenu, "Clear Object Data", self.clearObjects, QtGui.QKeySequence('Ctrl+Alt+Backspace'))



    def setSlot(self):
        global Tileset

        items = ("Pa0", "Pa1", "Pa2", "Pa3")

        item, ok = QtWidgets.QInputDialog.getItem(self, "Set Tileset Slot",
                "Warning: \n    Setting the tileset slot will override any \n    tiles set to draw from other tilesets.\n\nCurrent slot is Pa%d" % Tileset.slot, items, 0, False)
        if ok and item:
            Tileset.slot = int(item[2])
            self.tileWidget.tilesetType.setText(item)


            cobj = 0
            crow = 0
            ctile = 0
            for object in Tileset.objects:
                for row in object.tiles:
                    for tile in row:
                        if tile != (0,0,0):
                            Tileset.objects[cobj].tiles[crow][ctile] = (tile[0], tile[1], (tile[2] & 0xFC) | int(str(item[2])))
                        if tile == (0,0,0) and ctile == 0:
                            Tileset.objects[cobj].tiles[crow][ctile] = (tile[0], tile[1], (tile[2] & 0xFC) | int(str(item[2])))
                        ctile += 1
                    crow += 1
                    ctile = 0
                cobj += 1
                crow = 0
                ctile = 0


    def toggleAlpha(self):
        # Replace Alpha Image with non-Alpha images in model
        if self.alpha == True:
            self.alpha = False
        else:
            self.alpha = True

        self.setuptile()


    def toggleDarkMode(self):
        global DarkMode
        DarkMode = not DarkMode
        settings.setValue('DarkMode', DarkMode)
        QtWidgets.QMessageBox.information(None, 'Dark Mode', 'This change will take effect when you restart Puzzle.')


    def clearObjects(self):
        '''Clears the object data'''

        Tileset.objects = []

        SetupObjectModel(self.objmodel, Tileset.objects, Tileset.tiles)

        self.objectList.update()
        self.tileWidget.update()


    def clearCollisions(self):
        '''Clears the collisions data'''

        for tile in Tileset.tiles:
            tile.byte0 = 0
            tile.byte1 = 0
            tile.byte2 = 0
            tile.byte3 = 0
            tile.byte4 = 0
            tile.byte5 = 0
            tile.byte6 = 0
            tile.byte7 = 0

        self.updateInfo(0, 0)
        self.tileDisplay.update()


    def setupWidgets(self):
        frame = QtWidgets.QFrame()
        frameLayout = QtWidgets.QGridLayout(frame)

        # Displays the tiles
        self.tileDisplay = displayWidget()

        # Info Box for tile information
        self.infoDisplay = InfoBox(self)

        # Sets up the model for the tile pieces
        self.model = PiecesModel(self)
        self.tileDisplay.setModel(self.model)

        # Object List
        self.objectList = objectList()
        self.objmodel = QtGui.QStandardItemModel()
        SetupObjectModel(self.objmodel, Tileset.objects, Tileset.tiles)
        self.objectList.setModel(self.objmodel)

        # Creates the Tab Widget for behaviours and objects
        self.tabWidget = QtWidgets.QTabWidget()
        self.tileWidget = tileOverlord()
        self.paletteWidget = paletteWidget(self)

        # Second Tab
        self.container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.objectList)
        layout.addWidget(self.tileWidget)
        self.container.setLayout(layout)

        # Sets the Tabs
        self.tabWidget.addTab(self.paletteWidget, 'Behaviours')
        self.tabWidget.addTab(self.container, 'Objects')

        # Connections do things!
        self.tileDisplay.clicked.connect(self.paintFormat)
        self.tileDisplay.mouseMoved.connect(self.updateInfo)
        self.objectList.clicked.connect(self.tileWidget.setObject)

        # Layout
        frameLayout.addWidget(self.infoDisplay, 0, 0, 1, 1)
        frameLayout.addWidget(self.tileDisplay, 1, 0)
        frameLayout.addWidget(self.tabWidget, 0, 1, 2, 1)
        self.setCentralWidget(frame)


    def updateInfo(self, x, y):

        index = [self.tileDisplay.indexAt(QtCore.QPoint(x, y))]
        curTile = Tileset.tiles[index[0].row()]
        info = self.infoDisplay
        palette = self.paletteWidget

        propertyList = []
        propertyText = ''
        coreType = 0

        if curTile.byte3 & 32:
            coreType = 1
        elif curTile.byte3 & 64:
            coreType = 2
        elif curTile.byte2 & 8:
            coreType = 3
        elif curTile.byte3 & 2:
            coreType = 4
        elif curTile.byte3 & 8:
            coreType = 5
        elif curTile.byte2 & 4:
            coreType = 6
        elif curTile.byte2 & 16:
            coreType = 7
        elif curTile.byte1 & 1:
            coreType = 8
        elif 0 > curTile.byte7 > 0x23:
            coretype = 9
        elif curTile.byte5 == 4 or 5:
            coretype = 10
        elif curTile.byte3 & 4:
            coreType = 11

        if curTile.byte3 & 1:
            propertyList.append('Solid')
        if curTile.byte3 & 16:
            propertyList.append('Breakable')
        if curTile.byte2 & 128:
            propertyList.append('Pass-Through')
        if curTile.byte2 & 64:
            propertyList.append('Pass-Down')
        if curTile.byte1 & 2:
            propertyList.append('Falling')
        if curTile.byte1 & 8:
            propertyList.append('Ledge')
        if curTile.byte0 & 2:
            propertyList.append('Meltable')


        if len(propertyList) == 0:
            propertyText = 'None'
        elif len(propertyList) == 1:
            propertyText = propertyList[0]
        else:
            propertyText = propertyList.pop(0)
            for string in propertyList:
                propertyText = propertyText + ', ' + string

        if coreType == 0:
            if curTile.byte7 == 0x23:
                parameter = palette.ParameterList[coreType][1]
            elif curTile.byte7 == 0x28:
                parameter = palette.ParameterList[coreType][2]
            elif curTile.byte7 >= 0x35:
                parameter = palette.ParameterList[coreType][curTile.byte7 - 0x32]
            else:
                parameter = palette.ParameterList[coreType][0]
        else:
            parameter = palette.ParameterList[coreType][curTile.byte7]


        info.coreImage.setPixmap(palette.coreTypes[coreType][1].pixmap(24,24))
        info.terrainImage.setPixmap(palette.terrainTypes[curTile.byte5][1].pixmap(24,24))
        info.parameterImage.setPixmap(parameter[1].pixmap(24,24))

        info.coreInfo.setText(palette.coreTypes[coreType][0])
        info.propertyInfo.setText(propertyText)
        info.terrainInfo.setText(palette.terrainTypes[curTile.byte5][0])
        info.paramInfo.setText(parameter[0])

        info.hexdata.setText('Hex Data: {0} {1} {2} {3}\n                {4} {5} {6} {7}'.format(
                                hex(curTile.byte0), hex(curTile.byte1), hex(curTile.byte2), hex(curTile.byte3),
                                hex(curTile.byte4), hex(curTile.byte5), hex(curTile.byte6), hex(curTile.byte7)))



    def paintFormat(self, index):
        if self.tabWidget.currentIndex() == 1:
            return

        curTile = Tileset.tiles[index.row()]
        palette = self.paletteWidget

        if palette.coreWidgets[8].isChecked() == 1 or palette.propertyWidgets[0].isChecked() == 1:
            solid = 1
        else:
            solid = 0

        if palette.coreWidgets[1].isChecked() == 1 or palette.coreWidgets[2].isChecked() == 1:
            solid = 0


        curTile.byte0 = ((palette.propertyWidgets[4].isChecked() << 1))
        curTile.byte1 = ((palette.coreWidgets[8].isChecked()) +
                        (palette.propertyWidgets[2].isChecked() << 1) +
                        (palette.propertyWidgets[3].isChecked() << 3))
        curTile.byte2 = ((palette.coreWidgets[6].isChecked() << 2) +
                        (palette.coreWidgets[3].isChecked() << 3) +
                        (palette.coreWidgets[7].isChecked() << 4) +
                        (palette.PassDown.isChecked() << 6) +
                        (palette.PassThrough.isChecked() << 7))
        curTile.byte3 = ((solid) +
                        (palette.coreWidgets[4].isChecked() << 1) +
                        (palette.coreWidgets[5].isChecked() << 3) +
                        (palette.propertyWidgets[1].isChecked() << 4) +
                        (palette.coreWidgets[1].isChecked() << 5) +
                        (palette.coreWidgets[2].isChecked() << 6) +
                        (palette.coreWidgets[11].isChecked() << 2))
        curTile.byte4 = 0
        if palette.coreWidgets[2].isChecked():
            curTile.byte5 = 4
        curTile.byte5 = palette.terrainType.currentIndex()

        if palette.coreWidgets[0].isChecked():
            params = palette.parameters.currentIndex()
            if params == 0:
                curTile.byte7 = 0
            elif params == 1:
                curTile.byte7 = 0x23
            elif params == 2:
                curTile.byte7 = 0x28
            elif params >= 3:
                curTile.byte7 = params + 0x32
        else:
            curTile.byte7 = palette.parameters.currentIndex()

        self.updateInfo(0, 0)
        self.tileDisplay.update()



#############################################################################################
####################################### Main Function #######################################


if '-nolib' in sys.argv:
    HaveNSMBLib = False
    sys.argv.remove('-nolib')

if __name__ == '__main__':

    import sys

    # The default high-dpi scaling looks really bad, unfortunately.
    if QtCompatVersion >= (5,14,0):
        QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor)

    app = QtWidgets.QApplication(sys.argv)

    # load the settings
    if os.path.isfile('portable.txt'):
        settings = QtCore.QSettings('settings_Puzzle_%s.ini' % QtName, QtCore.QSettings.IniFormat)
    else:
        settings = QtCore.QSettings('Puzzle', 'Puzzle Tileset Editor (%s)' % QtName)

    if '-clear-settings' in sys.argv:
        settings.clear()

    # note: the str().lower() is for macOS, where bools in settings aren't automatically stringified
    DarkMode = (str(settings.value('DarkMode', 'false')).lower() == 'true')

    if DarkMode:
        setUpDarkMode()

    # go to the script path
    path = module_path()
    if path is not None:
        os.chdir(path)

    window = MainWindow()
    if len(sys.argv) > 1:
        window.openTilesetFromPath(sys.argv[1])
    window.show()
    sys.exit(app.exec())
    app.deleteLater()
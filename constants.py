# -*- coding: utf-8 -*-

from utils import versus_distance

SPEAKER_NAMES = ['FL', 'FR', 'FC', 'BL', 'BR', 'SL', 'SR', 'WL', 'WR', 'TFL', 'TFR', 'TSL', 'TSR', 'TBL', 'TBR']

SPEAKER_PATTERN = f'({"|".join(SPEAKER_NAMES + ["X"])})'
SPEAKER_LIST_PATTERN = r'{speaker_pattern}+(,{speaker_pattern})*'.format(speaker_pattern=SPEAKER_PATTERN)

SPEAKER_DELAYS = { _speaker: 0 for _speaker in SPEAKER_NAMES }

# Each channel, left and right
IR_ORDER = []
# SPL change relative to middle of the head - disable
IR_ROOM_SPL =  {
    sp: {'left': 0.0, 'right': 0.0}
    for sp in SPEAKER_NAMES
}
COLORS = {
    'lightblue': '#7db4db',
    'blue': '#1f77b4',
    'pink': '#dd8081',
    'red': '#d62728',
    'lightpurple': '#ecdef9',
    'purple': '#680fb9',
    'green': '#2ca02c'
}

HESUVI_TRACK_ORDER = ['FL-left', 'FL-right', 'SL-left', 'SL-right', 'BL-left', 'BL-right', 'FC-left', 'FR-right',
                      'FR-left', 'SR-right', 'SR-left', 'BR-right', 'BR-left', 'FC-right', 'WL-left', 'WL-right', 'WR-left', 'WR-right', 'TFL-left', 'TFL-right',
                             'TFR-left', 'TFR-right', 'TSL-left', 'TSL-right', 'TSR-left', 'TSR-right',
                             'TBL-left', 'TBL-right', 'TBR-left', 'TBR-right']

HEXADECAGONAL_TRACK_ORDER = ['FL-left', 'FL-right', 'FR-left', 'FR-right', 'FC-left', 'FC-right', 'LFE-left',
                             'LFE-right', 'BL-left', 'BL-right', 'BR-left', 'BR-right', 'SL-left', 'SL-right',
                             'SR-left', 'SR-right', 'WL-left', 'WL-right', 'WR-left', 'WR-right', 'TFL-left', 'TFL-right',
                             'TFR-left', 'TFR-right', 'TSL-left', 'TSL-right', 'TSR-left', 'TSR-right',
                             'TBL-left', 'TBL-right', 'TBR-left', 'TBR-right']

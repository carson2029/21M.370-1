from scamp import *

import comms, utils, init
from pynput import keyboard
import threading, math, random
from setup import *
import time

debug = False
number_sensors = 6

instr = s.new_midi_part("esp32", 1)

for m in init.initial_params:
    comms.send_osc(*m)

monitor = ""

# -----------------------------
# MIDI handlers: ONLY monitor
# -----------------------------
def handle_note(note, velocity):
    if debug:
        print('note', note, velocity)

def handle_cc(num, val):
    if debug:
        print('cc', num, val)


# -----------------------------
# main loop
# -----------------------------
def mainLoop():
    global index

    instr.play_note(60, 1, 0.1)   # reset the mpr121

    # pads 0,1,2 = arp pads
    arp_patterns = {
        0: [0, 3, 7, 10, 7, 3],   # C minor 7 feel
        1: [0, 3, 7, 12, 7, 3],   # F minor feel
        2: [0, 3, 7, 10, 7, 3],   # G minor 7 feel
    }

    arp_roots = {
        0: 36,
        1: 41,
        2: 43,
    }

    sustain_pitches = {
        3: (48-3)/127,
        4: (60-3)/127,
        5: (67-3)/127,
    }

    # state
    arp_index = {0: 0, 1: 0, 2: 0}
    next_arp_time = {0: 0, 1: 0, 2: 0}
    arp_gate_off = {0: 0, 1: 0, 2: 0}

    sustain_started = {3: False, 4: False, 5: False}

    while True:
        now = time.monotonic()

        # -----------------------------
        # monitoring
        # -----------------------------
        monitor_values = []
        for i in range(number_sensors):
            if monitor == "proximity":
                monitor_values.append(ccs[i+12])
            if monitor == "touch_state":
                monitor_values.append(True if i in active_notes else False)
            if monitor == "touch_cap":
                monitor_values.append(ccs[i])

        if len(monitor_values) > 0:
            print(monitor_values)

        # -----------------------------
        # pads 0,1,2 = looping arps
        # -----------------------------
        for note in [0, 1, 2]:
            if note in active_notes:
                if now >= next_arp_time[note]:
                    interval = arp_patterns[note][arp_index[note]]
                    pitch = (arp_roots[note] + interval - 3) / 127

                    comms.send_osc('voice', note, 'pitch', pitch)
                    comms.send_osc('voice', note, 'vca', 1)
                    comms.send_osc('voice', note, 'trigger', 1)

                    arp_gate_off[note] = now + 0.03
                    next_arp_time[note] = now + 0.16
                    arp_index[note] = (arp_index[note] + 1) % len(arp_patterns[note])
            else:
                arp_index[note] = 0
                comms.send_osc('voice', note, 'trigger', 0)
                comms.send_osc('voice', note, 'vca', 0)

        # turn arp trigger back off shortly after firing
        for note in [0, 1, 2]:
            if arp_gate_off[note] != 0 and now >= arp_gate_off[note]:
                comms.send_osc('voice', note, 'trigger', 0)
                arp_gate_off[note] = 0

        # -----------------------------
        # pads 3,4,5 = sustained notes
        # use touch-cap CC (cc 3,4,5) for volume while touched
        # -----------------------------
        for note in [3, 4, 5]:
            prox = ccs[note + 12]
            vol = max(0, min(1, prox / 127))

            if prox > 5:   # <-- only active when your hand is near
                comms.send_osc('voice', note, 'pitch', sustain_pitches[note])
                comms.send_osc('voice', note, 'vca', vol)
                comms.send_osc('voice', note, 'trigger', 1)
            else:
                comms.send_osc('voice', note, 'vca', 0)
                comms.send_osc('voice', note, 'trigger', 0)

        wait(0.01)


def run_session():
    s.fork(mainLoop)
    s.wait_forever()


comms.handle_cc = handle_cc
comms.handle_note = handle_note
s.register_midi_listener(comms.esp32_midi_port, comms.handle_midi)

run_session()
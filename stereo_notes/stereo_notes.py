import csv
import json
import os
import sys
import time

if len(sys.argv) < 1:
    print "Usage: %s <inputfile>" % sys.argv[0]
    sys.exit(1)

inputFile = sys.argv[1]
inputFilename = inputFile.split('/')[-1].split('.')[0]
instrumentFile = "data/instruments.csv"
instrumentDir = "instruments/"
frequenciesFile = "data/frequencies.json"

writeNotes = True
writeSequence = True

minNoteDuration = 100
pitchNoteThreshold = 10.0
gain = 1.0

notes = []
instruments = []
sequence = []
instrumentTypes = []

def getChords(note):
    chord_map = {
        # Root: [Major third, Minor third, Fifth]
        'C': ['E', 'D#', 'G'],
        'C#': ['F', 'E', 'G#'],
        'D': ['F#', 'F', 'A'],
        'D#': ['G', 'F#', 'A#'],
        'E': ['G#', 'G', 'B'],
        'F': ['A', 'G#', 'C'],
        'F#': ['A#', 'A', 'C#'],
        'G': ['B', 'A#', 'D'],
        'G#': ['C', 'B', 'D#'],
        'A': ['C#', 'C', 'E'],
        'A#': ['D', 'C#', 'F'],
        'B': ['D#', 'D', 'F#']
    }
    return chord_map[note]

def mean(data):
    if iter(data) is data:
        data = list(data)
    n = len(data)
    if n < 1:
        return 0
    else:
        return sum(data)/n

# get pitch data
def getPitchData(pitch):
    global frequencies
    data = frequencies[0]
    for i, f in enumerate(frequencies):
        hz = float(f['hz'])
        prev_hz = 0
        if i > 0:
            prev_hz = float(frequencies[i-1]['hz'])
        if pitch < hz:
            if prev_hz > 0 and abs(prev_hz-pitch) < abs(hz-pitch):
                data = frequencies[i-1]
            else:
                data = f
            break
    return data

# Get frequency table
frequencies = json.load(open(frequenciesFile))

# Read sound data
with open(inputFile, 'rb') as f:
    r = csv.reader(f, delimiter=',')
    for _s,_pitch in r:
        ms = int(round(float(_s) * 1000))
        pitch = float(_pitch)
        mid = 0
        note = '-'
        octave = 0
        if pitch > 0:
            pdata = getPitchData(pitch)
            mid = pdata['midi']
            note = pdata['note']
            octave = pdata['octave']
        notes.append({
            'ms': ms,
            'pitch': pitch,
            'midi': mid,
            'note': note,
            'octave': octave,
            'note_octave': note + str(octave)
        })

# Read instrument data
with open(instrumentFile, 'rb') as f:
    r = csv.reader(f, delimiter=',')
    next(r, None) # remove header
    for file,note,octave,duration,instrumentType,mod,remainder in r:
        instruments.append({
            'index': len(instruments),
            'file': instrumentDir + file,
            'note': note,
            'octave': int(octave),
            'note_octave': note + octave,
            'duration': int(duration),
            'type': instrumentType,
            'mod': int(mod),
            'remainder': int(remainder)
        })
    instruments = sorted(instruments, key=lambda k: k['duration'])
    instrumentTypes = set([i['type'] for i in instruments])

def selectInstrument(step, note, octave, duration, instrumentType):
    global instruments
    if instrumentType=='harmony':
        chords = getChords(note)
        note = chords[-1]
    if instrumentType=='rhythm':
        note = 'any'
        octave = 0
    candidates = [i for i in instruments if i['note']==note and i['type']==instrumentType and i['duration']<duration and step%i['mod']==i['remainder']]
    minOctave = min([i['octave'] for i in candidates])
    maxOctave = max([i['octave'] for i in candidates])
    octave = max([octave, minOctave])
    octave = min([octave, maxOctave])
    matches = [i for i in candidates if i['octave']==octave]
    if instrumentType!='rhythm':
        matches = [matches[-1]]
    return matches

# Add new sequence step
def addToSequence(ms, duration, pitch):
    global sequence
    global minNoteDuration
    global instrumentTypes
    if duration >= minNoteDuration:
        pdata = getPitchData(pitch)
        mid = pdata['midi']
        note = pdata['note']
        octave = pdata['octave']
        i = len(set([step['elapsed_ms'] for step in sequence if step['elapsed_ms'] < ms]))
        for instrumentType in instrumentTypes:
            selectedInstruments = selectInstrument(i, note, octave, duration, instrumentType)
            if len(selectedInstruments) > 0:
                for instrument in selectedInstruments:
                    sequence.append({
                        'elapsed_ms': ms,
                        'duration': duration,
                        'note': note,
                        'octave': octave,
                        'instrument': instrument
                    })

# Build sequence
pitch_queue = []
start_ms = 0
start_pitch = 0
ms = 0
for n in notes:
    ms = n['ms']
    pitch = n['pitch']
    # reached a pause, add previous note queue
    if pitch <= 0 and len(pitch_queue) > 0:
        addToSequence(start_ms, ms-start_ms, mean(pitch_queue))
        pitch_queue = []
    # reached a note threshold, add previous note queue
    elif pitch > 0 and abs(pitch-start_pitch) > pitchNoteThreshold and (ms-start_ms) > minNoteDuration and len(pitch_queue) > 0:
        addToSequence(start_ms, ms-start_ms, mean(pitch_queue))
        pitch_queue = []
    # add pitch to note queue
    elif pitch > 0:
        if len(pitch_queue) <= 0:
            start_ms = ms
            start_pitch = pitch
        pitch_queue.append(pitch)
if len(pitch_queue) > 0:
    addToSequence(start_ms, ms-start_ms, mean(pitch_queue))

# Report on sequence time
total_ms = sequence[-1]['elapsed_ms']
total_seconds = int(1.0*total_ms/1000)
remainding_ms = int(total_ms % 1000)

print('Main sequence time: '+time.strftime('%M:%S', time.gmtime(total_seconds)) + ' (' + str(total_seconds) + '.'+str(remainding_ms)+'s)')

# Sort sequence
sequence = sorted(sequence, key=lambda k: k['elapsed_ms'])

# Add milliseconds to sequence
elapsed = 0
for i, step in enumerate(sequence):
	sequence[i]['ms'] = step['elapsed_ms'] - elapsed
	elapsed = step['elapsed_ms']

# Write notes to file
if writeNotes:
    with open('output/'+inputFilename+'-notes.csv', 'wb') as f:
        w = csv.writer(f)
        for n in notes:
            w.writerow([n['ms'], n['note'], n['octave']])
        print('Successfully wrote '+str(len(notes))+' notes to log file')

# Write sequence to file
if writeSequence:
    # Write human-readable sequence
    with open('output/'+inputFilename+'-sequence-readable.csv', 'wb') as f:
        w = csv.writer(f)
        for s in sequence:
            w.writerow([s['elapsed_ms'], s['duration'], s['note'], s['octave']])
    # Write instruments
    with open('output/ck-instruments.csv', 'wb') as f:
        w = csv.writer(f)
        for i in instruments:
            w.writerow([i['index']])
            w.writerow([i['file']])
        f.seek(-2, os.SEEK_END) # remove newline
        f.truncate()
    # Write machine-readable sequence
    with open('output/ck-sequence.csv', 'wb') as f:
        w = csv.writer(f)
        for s in sequence:
            w.writerow([s['instrument']['index']])
            w.writerow([gain])
            w.writerow([s['ms']])
        f.seek(-2, os.SEEK_END) # remove newline
        f.truncate()
    print('Successfully wrote '+str(len(sequence))+' notes to sequence file')

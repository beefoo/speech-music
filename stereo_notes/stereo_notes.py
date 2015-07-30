from aubio import freqtomidi
import csv
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

writeNotes = True
writeSequence = True

minNoteDuration = 100
pitchNoteThreshold = 10.0
gain = 1.0

minOctave = None
maxOctave = None

notes = []
instruments = []
sequence = []

def mean(data):
    if iter(data) is data:
        data = list(data)
    n = len(data)
    if n < 1:
        return 0
    else:
        return sum(data)/n

# Convert midi to note
def midi2note(midi):
    if type(midi) != int:
        raise TypeError, "an integer is required, got %s" % midi
    midi = min(127, midi)
    midi = max(0, midi)
    midi = int(midi)
    _valid_notenames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = midi / 12 - 1
    return [_valid_notenames[midi % 12], octave]

# Read sound data
with open(inputFile, 'rb') as f:
    r = csv.reader(f, delimiter=',')
    for _s,_pitch in r:
        ms = int(round(float(_s) * 1000))
        pitch = float(_pitch)
        mid = 0
        note = ['-', 0]
        if pitch > 0:
            mid = int(freqtomidi(pitch))
            note = midi2note(mid)
        notes.append({
            'ms': ms,
            'pitch': pitch,
            'midi': mid,
            'note': note[0],
            'octave': note[1],
            'note_octave': note[0] + str(note[1])
        })

# Read instrument data
with open(instrumentFile, 'rb') as f:
    r = csv.reader(f, delimiter=',')
    next(r, None) # remove header
    for file,note,octave,duration in r:
        instruments.append({
            'index': len(instruments),
            'file': instrumentDir + file,
            'note': note,
            'octave': int(octave),
            'note_octave': note + octave,
            'duration': int(duration)
        })
    instruments = sorted(instruments, key=lambda k: k['duration'])
    minOctave = min([i['octave'] for i in instruments])
    maxOctave = max([i['octave'] for i in instruments])

def selectInstrument(note_octave, duration):
    global instruments
    matches = [i for i in instruments if i['note_octave']==note_octave and i['duration'] < duration]
    return matches[-1]

# Add new sequence step
def addToSequence(ms, duration, pitch):
    global sequence
    global minNoteDuration
    global minOctave
    global maxOctave
    if duration >= minNoteDuration:
        mid = int(freqtomidi(pitch))
        note = midi2note(mid)
        octave = note[1]
        note = note[0]
        octave = max([octave, minOctave])
        octave = min([octave, maxOctave])
        note_octave = note + str(octave)
        sequence.append({
            'elapsed_ms': ms,
            'duration': duration,
            'note': note,
            'octave': octave,
            'instrument': selectInstrument(note_octave, duration)
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

total_ms = sequence[-1]['elapsed_ms']
total_seconds = int(1.0*total_ms/1000)
print('Main sequence time: '+time.strftime('%M:%S', time.gmtime(total_seconds)) + ' (' + str(total_seconds) + 's)')

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
    with open('output/'+inputFilename+'-instruments.csv', 'wb') as f:
        w = csv.writer(f)
        for i in instruments:
            w.writerow([i['index']])
            w.writerow([i['file']])
        f.seek(-2, os.SEEK_END) # remove newline
        f.truncate()
    # Write machine-readable sequence
    with open('output/'+inputFilename+'-sequence.csv', 'wb') as f:
        w = csv.writer(f)
        for s in sequence:
            w.writerow([s['instrument']['index']])
            w.writerow([gain])
            w.writerow([s['ms']])
        f.seek(-2, os.SEEK_END) # remove newline
        f.truncate()
    print('Successfully wrote '+str(len(sequence))+' notes to sequence file')

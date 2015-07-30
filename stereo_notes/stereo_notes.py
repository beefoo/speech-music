from aubio import source, pitch, freqtomidi
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

sampleRate = 44100
tolerance = 0.8
downsample = 1
minNoteDuration = 1
gain = 1.0

minOctave = None
maxOctave = None

win_s = 4096 / downsample # fft size
hop_s = 512 / downsample # hop size
s = source(inputFile, sampleRate, hop_s)
sampleRate = s.samplerate

pitch_o = pitch("yin", win_s, hop_s, sampleRate)
pitch_o.set_unit("freq")
pitch_o.set_tolerance(tolerance)

notes = []
instruments = []
sequence = []

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

# Total number of frames read
total_frames = 0
while True:
    samples, read = s()
    pitch = pitch_o(samples)[0]
    #pitch = int(round(pitch))
    confidence = pitch_o.get_confidence()
    ms = int(round(total_frames / float(sampleRate) * 1000))
    mid = 0
    note = ['-', 0]
    if confidence > 0 and pitch > 0:
        mid = int(freqtomidi(pitch))
        note = midi2note(mid)
    notes.append({
        'ms': ms,
        'pitch': pitch,
        'midi': mid,
        'note': note[0],
        'octave': note[1],
        'note_octave': note[0] + str(note[1]),
        'confidence': confidence
    })
    total_frames += read
    if read < hop_s: break

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

def addQueueToSequence(q):
    global minNoteDuration
    global sequence

    n0 = q[0]
    n1 = q[-1]
    queue_duration = n1['ms']-n0['ms']
    if queue_duration >= minNoteDuration and n0['note']!='-':
        sequence.append({
            'ms': n0['ms'],
            'duration': queue_duration,
            'note': n0['note'],
            'octave': n0['octave'],
            'instrument': selectInstrument(n0['note_octave'], queue_duration)
        })

# Build sequence
queue = []
for n in notes:
    if n['octave'] >= minOctave and n['octave'] <= maxOctave:
        if len(queue) < 1 or queue[0]['note_octave']==n['note_octave']:
            queue.append(n)
        elif len(queue) > 0:
            addQueueToSequence(queue)
            queue = [n]
    elif len(queue) > 0:
        addQueueToSequence(queue)
        queue = []
if len(queue) > 0:
    addQueueToSequence(queue)

total_ms = sequence[-1]['ms']
total_seconds = int(1.0*total_ms/1000)
print('Main sequence time: '+time.strftime('%M:%S', time.gmtime(total_seconds)) + ' (' + str(total_seconds) + 's)')

# Write notes to file
if writeNotes:
    with open('output/'+inputFilename+'-notes.csv', 'wb') as f:
        w = csv.writer(f)
        for n in notes:
            w.writerow([n['ms'], n['note'], n['octave'], n['confidence']])
        print('Successfully wrote '+str(len(notes))+' notes to log file')

# Write sequence to file
if writeSequence:
    # Write human-readable sequence
    with open('output/'+inputFilename+'-sequence-readable.csv', 'wb') as f:
        w = csv.writer(f)
        for s in sequence:
            w.writerow([s['ms'], s['duration'], s['note'], s['octave']])
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

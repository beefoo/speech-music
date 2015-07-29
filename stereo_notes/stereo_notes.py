import sys
import csv
from aubio import source, pitch, freqtomidi

if len(sys.argv) < 1:
    print "Usage: %s <inputfile>" % sys.argv[0]
    sys.exit(1)

inputFile = sys.argv[1]
inputFilename = inputFile.split('/')[-1].split('.')[0]

writeNotes = True
writeSequence = True

sampleRate = 44100
tolerance = 0.8
downsample = 1
minOctave = 0
maxOctave = 5
minNoteDuration = 10

win_s = 4096 / downsample # fft size
hop_s = 512 / downsample # hop size
s = source(inputFile, sampleRate, hop_s)
sampleRate = s.samplerate

pitch_o = pitch("yin", win_s, hop_s, sampleRate)
pitch_o.set_unit("freq")
pitch_o.set_tolerance(tolerance)

notes = []
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

def addQueueToSequence(q):
    global sequence
    global minNoteDuration

    n0 = q[0]
    n1 = q[-1]
    queue_duration = n1['ms']-n0['ms']
    if queue_duration >= minNoteDuration and n0['note']!='-':
        sequence.append({
            'ms': n0['ms'],
            'duration': queue_duration,
            'note': n0['note'],
            'octave': n0['octave']
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

# Write notes to file
if writeNotes:
    with open('output/'+inputFilename+'-notes.csv', 'wb') as f:
        w = csv.writer(f)
        for n in notes:
            w.writerow([n['ms'], n['note'], n['octave'], n['confidence']])
        print('Successfully wrote '+str(len(notes))+' notes to log file')

# Write sequence to file
if writeSequence:
    with open('output/'+inputFilename+'-sequence.csv', 'wb') as f:
        w = csv.writer(f)
        for s in sequence:
            w.writerow([s['ms'], s['duration'], s['note'], s['octave']])
        print('Successfully wrote '+str(len(sequence))+' notes to sequence file')

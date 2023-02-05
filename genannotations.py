import sys
import os
import argparse
from musicxml import MusicXML


def filterForAnnotations(sequences, include_notes=False, include_rests=False):
    annotations = list()

    for seq in sequences:
        s = seq.split(' + ')  # Each element is a series of simultaneous tokens

        for elem in s:
            tokens = elem.split(' ')
            t = tokens[0]  # Take first element in chord. They will all have same length anyway

            if 'barline' in t:
                annotations.append(t)
            elif 'note' in t:
                if include_notes:
                    split = t.split('_')
                    time = '_'.join(split[1:len(split) + 1])
                    annotations.append(time)
                else:
                    continue

            elif 'rest' in t:
                if include_rests:
                    split = t.split('-')
                    time = '-'.join(split[1:len(split) + 1])
                    annotations.append(time)
                else:
                    continue
                
            elif 'clef' in t or 'key' in t:
                continue
            elif '+' in t:  # If bar empty
                continue
            else:
                annotations.append(t)

    return annotations


def get_bar_annotations(staves):
    staves_bars = list()
    for stave in staves:
        sequences = [x for x in stave if x != '']
        sequences_annotations = filterForAnnotations(sequences, include_notes=False, include_rests=False)

        # Group all elements in same bars together
        full = list()
        bar = list()
        for s in sequences_annotations:
            if s == 'barline':
                full.append(bar)
                bar = list()
            else:
                bar.append(s)

        staves_bars.append(full)

    # Merge
    merged = list()
    for s in staves_bars:
        for idx, bar in enumerate(s):
            if len(merged) > idx:
                merged[idx] += bar
            else:
                merged.append(bar)

    return merged


def get_first_bar_time(sequence):
    first_bar = [x for x in sequence if x != ''][0]
    first_bar = first_bar.split(' + barline + ')[0]  # Get first bar
    first_bar = filterForAnnotations([first_bar], include_notes=True, include_rests=True)
    
    note_dur_dict = {'half': 1/2,
            'quarter': 1/4,
            'eighth': 1/8,
            'sixteenth': 1/16,
            'thirty_second': 1/32}

    counter = 0
    for t in first_bar:
        dot = True if '.' in t else False
        t = t.replace('.', '')
        if t in note_dur_dict.keys():
            if dot:
                counter += note_dur_dict[t] * 1.5
            else:
                counter += note_dur_dict[t]

    return counter

def calculateAnnotationTimes(staves, sequence):
    # Get time of first bar in top stave
    first_bar_time = get_first_bar_time(staves[0])

    time_sig_dict = {
        'C/': 1,
        '4/8': 4/8,
        '3/8': 3/8,
    }

    add_next = 0
    time_sig = 0
    running_time = 0
    annotation_times = list()
    for idx, bar in enumerate(sequence):
        running_time += time_sig

        running_time += add_next
        add_next = 0

        for elem in bar:
            if 'timeSignature' in elem:
                bar_time_sig_end = elem.split('-')[1]
                time_sig = time_sig_dict[bar_time_sig_end]

                if idx == 0:
                    add_next = first_bar_time - time_sig
            else:
                annotation_times.append((running_time, elem))

    return annotation_times


def gen_annotations(args):
    musicxml_obj = MusicXML(input_file=args.input)

    try:
        sequences = musicxml_obj.get_sequences()
    except UnicodeDecodeError: # Ignore bad MusicXML
        raise Exception('Corrupted file')

    staves = [[x[0] for x in sequences]] + [[x[1] for x in sequences]]

    # Check staves have same length
    if len(staves[0]) * len(staves) != sum([len(s) for s in staves]):
        raise Exception('Decoded staves have different lengths')

    merged = get_bar_annotations(staves)
    if args.verbose:
        print('Merged annotations:\n', merged)

    if args.time:
        merged = calculateAnnotationTimes(staves, merged)
        if args.verbose:
            print('Times:\n', merged)
    
    return merged


if __name__ == '__main__':
    """
    Command line args:

    -input <input directory with MusicXMLS>
    --verbose
    """

    # Parse command line arguments for input/output directories
    parser = argparse.ArgumentParser()
    parser.add_argument('-input', dest='input', type=str, required='-c' not in sys.argv, help='Path to the input directory with MusicXMLs.')
    parser.add_argument('--time', dest='time', action='store_true')
    parser.add_argument('--verbose', dest='verbose', action='store_true')
    args = parser.parse_args()

    gen_annotations(args)
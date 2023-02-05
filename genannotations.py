import sys
import os
import argparse
from musicxml import MusicXML


def filterForAnnotations(sequences):
    annotations = list()

    for seq in sequences:
        s = seq.split(' + ')  # Each element is a series of simultaneous tokens

        for elem in s:
            tokens = elem.split(' ')
            t = tokens[0]  # Take first element in chord. They will all have same length anyway
            t = t.replace('.', '')

            if 'barline' in t:
                annotations.append(t)
            elif 'note' in t:
                continue
                split = t.split('_')
                time = '_'.join(split[1:len(split) + 1])
                annotations.append(time)
            elif 'rest' in t:
                continue
                split = t.split('-')
                time = '-'.join(split[1:len(split) + 1])
                annotations.append(time)
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
        sequences_annotations = filterForAnnotations(sequences)

        # Group all elements in same bars together
        full = list()
        bar = list()
        for s in sequences_annotations[1:]:
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

    merged = [[sequences_annotations[0]]] + merged
    return merged


def calculateAnnotationTimes(sequence):
    time_dict = {
        '4/8': 4/8,
        '3/8': 3/8,
    }

    time_sig = 0
    running_time = 0
    annotation_times = list()
    for bar in sequence:
        running_time += time_sig

        for elem in bar:
            if 'timeSignature' in elem:
                bar_time_sig_end = elem.split('-')[1]
                time_sig = time_dict[bar_time_sig_end]
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
        merged = calculateAnnotationTimes(merged)
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
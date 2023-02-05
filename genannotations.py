import sys
import os
import argparse
from musicxml import MusicXML


def filterForAnnotations(sequences):
    annotations = list()

    for seq in sequences:
        annotations.append("a")
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


def collapseAnnotations(sequence):
    len_dict = {'half': 1/2,
                'quarter': 1/4,
                'eighth': 1/8,
                'sixteenth': 1/16,
                'thirty_second': 1/32}
    counter = 0
    key = None
    for t in sequence:
        if 'time' in t:
            time = t.split('-')[1].split('/')
            time = int(time[0]) / int(time[1])
            print('TIME', time)

        if t in len_dict.keys():
            counter += len_dict[t]

        if t == 'barline':
            print(counter)
            counter = 0

if __name__ == '__main__':

    """
    Command line args:

    -input <input directory with MusicXMLS>
    """

    # Parse command line arguments for input/output directories
    parser = argparse.ArgumentParser()
    parser.add_argument('-input', dest='input', type=str, required='-c' not in sys.argv, help='Path to the input directory with MusicXMLs.')
    args = parser.parse_args()

    # Track all unique tokens
    pitch_tokens = list()
    rhythm_tokens = list()

    # Go through all inputs generating output sequences
    for i, file_name in enumerate(os.listdir(args.input)):

        # Ignore non .musicxml files
        if not file_name.endswith('.musicxml'):
            continue

        # Create a MusicXML object for generating sequences
        input_path = os.path.join(args.input, file_name)
        musicxml_obj = MusicXML(input_file=input_path)

        try:
            # Write sequence
            sequences = musicxml_obj.get_sequences()
            staves = [[x[0] for x in sequences]] + [[x[1] for x in sequences]]
            print(len(staves[0]), len(staves[1]))
            print(staves[0], staves[1])

            # Add new unique tokens to vocab
            sequences = [x for x in staves[0] if x != '']
            sequences_annotations = filterForAnnotations(sequences)
            print(sequences_annotations)
            print(len([0 for x in sequences_annotations if x == 'barline']))

            sequences = [x for x in staves[1] if x != '']
            sequences_annotations = filterForAnnotations(sequences)
            print(sequences_annotations)
            print(len([0 for x in sequences_annotations if x == 'barline']))
        
        except UnicodeDecodeError: # Ignore bad MusicXML
            pass  # TODO nuke bad files
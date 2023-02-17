"""
Contains class that converts MusicXML to a sequence
by parsing it
"""

import sys
import xml.etree.ElementTree as ET 

from .measure import Measure

import functools

class MusicXML():

    def __init__(self, input_file):

        """
        Stores MusicXML file passed in 
        """

        # Input/output file path (.musicxml and .semantic)
        self.input_file = input_file
        
        # Set default values for key, clef, time signature
        self.key = ''
        self.clef = ''
        self.time = ''
        self.beat = 4
        self.beat_type = 4

        # Track whether current page being labeled is polyphonic or not
        self.polyphonic_page = True

        # Read the width and cutoffs for each page of the .musicxml file
        self.get_width()

    def get_width(self):
        """
        Reads width/cutoffs on left/right of XML
        """

        margins = 0

        with open(self.input_file, 'r', errors='ignore') as input_file:
            
            # Check for valid parse tree in .musicxml file
            try:
                tree = ET.parse(input_file)
                root = tree.getroot()
            except:
                return

            # Index in parse tree with information about page width
            defaults_idx = -1

            # Look for "defaults" tag which contains page width information
            for i, child in enumerate(root):
                if child.tag == 'defaults':
                    defaults_idx = i
                    break

            # Check for bad MusicXML
            if defaults_idx == -1:
                print('MusicXML file:', self.input_file,' missing <score-partwise> or <part>')
                return

            # .MusicXML defines margins separately for odd even pages,
            #  assume they are the same
            margin_found = False            

            # Get number of staves in the MusicXML
            for i,e in enumerate(root[defaults_idx]):
                if e.tag == 'page-layout':
                    for c in e:
                        if c.tag == 'page-width':
                            self.width = float(c.text)
                        elif c.tag == 'page-margins' and not margin_found:
                            for k in c:
                                if k.tag == 'left-margin':
                                    margins += float(k.text)
                                elif k.tag == 'right-margin':
                                    margins += float(k.text)
                            margin_found = True

        # Based on width and margins read, set the width per page, for calculating
        # when to proceed to next page (sample) while generating labels
        self.width_cutoff = self.width - margins + 1
                
    def get_sequences(self):

        """
        Parses MusicXML file and returns sequences corresponding
        to the first staff of the first part of the score
        (list of symbols for each page)
        """

        # Stores all symbolic sequences for the .musicxml
        sequences = []

        new_score = True

        with open(self.input_file, 'r') as input_file:

            # Get parse tree
            try:
                tree = ET.parse(input_file)
                root = tree.getroot()
            except:
                return sequences

            # Indexing for part list
            part_list_idx = -1
            part_idx = -1

            # Find <part-list> and <part> element indexes
            for i, child in enumerate(root):
                if child.tag == 'part-list':
                    part_list_idx = i
                elif child.tag == 'part':
                    # Choose 1st part only to generate sequence
                    part_idx = i if part_idx == -1 else part_idx

            # Check for bad MusicXML
            if part_list_idx == -1 or part_idx == -1:
                print('MusicXML file:', self.input_file,' missing <part-list> or <part>')
                return ['']

            # Get number of staves in the MusicXML
            num_staves = 1
            try:
                for e in root[part_idx][0][0]:
                    if e.tag == 'staff-layout':
                        num_staves = int(e.attrib['number'])
            except IndexError:
                return ['']
            staves = ['' for x in range(num_staves)]    # Holds sequence of each staff

            # Read each measure
            r_iter = iter(root[part_idx])
            cur_width = 0.0     # Sum of width of measures currently read
            page_num = 1        # Current page number (for naming)
            new_page = False    # Tracks if just beginning a new page due to "print" element

            # Iterate through all measures 
            for i, measure in enumerate(r_iter):

                # Increment current width by the measure's width
                cur_width += float(measure.attrib['width'])

                # Check if need to create a new page (ie. new sample)
                child_elems = [e for e in measure]
                child_tags = [e.tag for e in child_elems]
                if 'print' in child_tags:
                    print_children = [e.tag for e in list(iter(child_elems[child_tags.index('print')]))]
                    if 'system-layout' in print_children: 
                        new_page = True
                if cur_width > self.width_cutoff or new_page:
                    # Save the current sequence to be saved
                    sequences.append(staves)
                    staves = ['' for x in range(num_staves)]
                    cur_width = int(float(measure.attrib['width']))
                    page_num += 1

                    # Reset polyphonic page and print if necessary
                    if self.polyphonic_page:
                        pass
                        #print(self.input_file.split('\\')[-1].split('.semantic')[0] + '-' + str(page_num-1))
                    self.polyphonic_page = False

                # Gets the symbolic sequence of each staff in measure of first part
                measure_staves, skip = self.read_measure(measure, num_staves, new_page, staves, new_score)
                new_score = False

                # Updates current symbolic sequence of each staff with current measure's symbols
                for j in range(num_staves):
                    staves[j] += measure_staves[j]

                # Skips any measures as needed
                for j in range(skip-1):
                    next(r_iter)

                new_page = False

        # Add any remaining measures to list of sequences
        if cur_width > 0:
            sequences.append(staves)
            staves = ['' for x in range(num_staves)]
            cur_width = int(float(measure.attrib['width']))

        return sequences


    def read_measure(self, measure, num_staves, new_page, cur_staves, new_score):

        """
        Reads a measure and returns a sequence of symbols

        measure: .xml element of the current measure being read
        num_staves: number of staves in the measure
        new_page: indiciates if starting a new page
        cur_staves: rest of sequence so far from previous measures
        new_score: indicates if first measure of the score
        """

        # Create a measure object
        m = Measure(measure, num_staves, self.beat, self.beat_type)

        # Tracking variables for the current sequence of each staff/voices for polyphonic music
        staves = ['' for _ in range(num_staves)]
        skip = 0
        voice_lines = dict()        # Symbolic representations of each voice
        voice_durations = dict()    # Length (in time) of each symbol of each voice

        forward_dur = []    # used for weird use of a 2nd voice
        cur_voice = -1      # tracks current voice

        # Track the clef, key, time signature that each sequence should start with
        start_clef = self.clef
        start_key = self.key
        start_time = self.time

        # Skip percussion/guitar tabs
        if 'percussion' in self.clef or 'TAB' in self.clef:
            return staves, 0

        # Grace note tracking
        is_grace = False
        prev_grace = False
        # Iterate through all elements in measure
        for elem in measure:

            # Stores symbolic sequence representing the current element being read
            cur_elem = ['' for _ in range(num_staves)]

            is_chord = False    # Used for determining to advance (+ symbol)

            if elem.tag == 'attributes':
                # Parse the attributes element
                # (Skip is number of measures to skip for multirest)
                cur_elem, skip, self.beat, self.beat_type = m.parse_attributes(elem)

                # Skip percussion/guitar music
                if 'percussion' in cur_elem[0] or 'TAB' in cur_elem[0] or \
                    'percussion' in cur_elem or 'TAB' in cur_elem:
                    self.clef = 'percussion'
                    return ['' for _ in range(num_staves)], 0

                # Add to all staves
                for i in range(num_staves):
                    if (cur_staves[i] != '' or staves[i] != '') and not is_chord and cur_elem[i] != '':
                        staves[i] += '+ ' + cur_elem[i]
                    else:
                        staves[i] += cur_elem[i]

            elif elem.tag == 'note':

                # Parse note element and get the symbolic representation of it
                cur_elem, is_chord, voice, duration, is_grace, _ = m.parse_note(elem)

                # Check if new voice started
                if cur_voice != voice and cur_voice != -1:

                    # Add any remaining forwards to previous voice
                    if len(forward_dur) != 0 and cur_voice in voice_lines:
                        voice_lines[cur_voice].append('forward')
                        voice_durations[cur_voice].append(forward_dur[-1])
                        del forward_dur[-1]

                cur_voice = voice

                # No print object case, include a duration, but don't generate symbol
                if cur_elem == 'forward':

                    if len(forward_dur) == 1:
                        forward_dur[0] += duration
                    else:
                        forward_dur.append(duration)

                else:
                    # Update voicing stuff (for multi voice aka polyphony)
                    if voice not in voice_lines:
                        voice_lines[voice] = []
                        voice_durations[voice] = []
                        if len(forward_dur) != 0:       # Handle weird case when voice added in middle of a measure
                            voice_lines[voice].append('+ ')
                            voice_lines[voice].append('forward')
                            voice_durations[voice].append(0)
                            voice_durations[voice].append(forward_dur[-1])
                            del forward_dur[-1]
                    
                    # If not a chord, append a '+' and 0 duration for it
                    if ((cur_staves[0] != '' or staves[0] != '') and not is_chord and cur_elem[0] != '') and not is_grace and not prev_grace:
                        voice_lines[voice].append('+ ')
                        voice_durations[voice].append(0)
                        voice_lines[voice].append(cur_elem[0])
                        voice_durations[voice].append(duration)
                    else:
                        # Different behavior if first note of sequence
                        if staves[0] != '':
                            voice_lines[voice].append(cur_elem[0])
                            voice_durations[voice].append(0)
                        else:
                            voice_lines[voice].append('+ ')
                            voice_durations[voice].append(0)
                            voice_lines[voice].append(cur_elem[0])
                            voice_durations[voice].append(duration)

                # Add to stave
                if (cur_staves[voice] != '' or staves[voice] != '') and not is_chord and cur_elem[0] != '':
                    staves[voice] += '+ ' + cur_elem[0]
                else:
                    staves[voice] += cur_elem[0]
                        
            elif elem.tag == 'direction':       # Parse direction element
                cur_elem = m.parse_direction(elem)

            elif elem.tag == 'forward':         # Parse forward element (used for multi voice music)
                forward_dur.append(int(elem[0].text))

            elif elem.tag == 'backup':          # Switching voice indication

                # Add any remaining forwards to previous voice
                if len(forward_dur) != 0 and cur_voice in voice_lines:
                    voice_lines[cur_voice].append('forward')
                    voice_durations[cur_voice].append(forward_dur[-1])
                    del forward_dur[-1]

                if len(forward_dur) != 0:
                    forward_dur = []

                cur_voice = -1

            # Add whatever was read to the staves
            if elem.tag != 'attributes' and elem.tag != 'note':
                for i in range(num_staves):
                    if 'multirest' in cur_elem[0]:
                        pass
                    if cur_elem != 'forward':
                        if (cur_staves[i] != '' or staves[i] != '') and not is_chord and cur_elem[i] != '':
                            staves[i] += ' + ' + cur_elem[i]
                        else:
                            staves[i] += cur_elem[i] 

            # Store current key/time/clef signature if found
            for word in cur_elem[0].split():

                # Check for key
                if 'key' in word:
                    
                    # If not a chord, append a '+' and 0 duration for it
                    if ((cur_staves[0] != '' or staves[0] != '') and not is_chord and cur_elem[0] != '') \
                        and self.key != '':
                        for v in voice_lines.keys():
                            voice_durations[v].append(0)
                            voice_durations[v].append(0)
                            voice_lines[v].append(' + ')
                            voice_lines[v].append(word + ' ')
                            
                    self.key = word
                    start_key = self.key

                # Check for clef
                if 'clef' in word:
                    
                    # If not a chord, append a '+' and 0 duration for it
                    if ((cur_staves[0] != '' or staves[0] != '') and not is_chord and cur_elem[0] != '') \
                        and self.clef != '':
                        for v in voice_lines.keys():
                            voice_durations[v].append(0)
                            voice_durations[v].append(0)
                            voice_lines[v].append(' + ')
                            voice_lines[v].append(word + ' ')
     
                    self.clef = word
                    start_clef = self.clef

                # Check for time signature symbol
                if 'time' in word:
                    
                    # If not a chord, append a '+' and 0 duration for it
                    if ((cur_staves[0] != '' or staves[0] != '') and not is_chord and cur_elem[0] != '') \
                        and self.time != '':
                        for v in voice_lines.keys():
                            voice_durations[v].append(0)
                            voice_durations[v].append(0)
                            voice_lines[v].append(' + ')
                            voice_lines[v].append(word + ' ')
        
                    self.time = word
                    start_time = self.time

            # Skip rest of measure if multirest
            if skip > 0:
                break

            # Update grace note tracking
            prev_grace = is_grace

        # Add measure separator to just one voice
        if len(voice_lines) > 0:
            key = sorted(voice_lines.keys())[0]
            voice_lines[key].append(' + ')
            voice_lines[key].append('barline ')
            voice_durations[key].append(0)
            voice_durations[key].append(0)

        # Add any remaining forwards to last voice if not extra
        if len(forward_dur) != 0 and len(voice_lines) > 0:
            keys = sorted(voice_lines.keys())
            max_sum = sum(voice_durations[keys[0]])

            # Only add if not an extra forward for diff staff possibly
            if (sum(voice_durations[keys[-1]]) + forward_dur[-1]) <= max_sum:
                voice_lines[keys[-1]].append('forward')
                voice_durations[keys[-1]].append(forward_dur[-1])
                del forward_dur[-1]

        # Add measure separator to each staff
        for i in range(num_staves):
            staves[i] = staves[i] + ' + barline '

        return staves, skip

        
    def compare_symbols(self, a, b):

        """
        Given a list of symbols, sort from how they would
        appear on a staff (top to bottom), assume rest/clef is on top
        """

        ret_val = 0

        # Clef case
        if 'clef' in a:
            ret_val = 1
            return ret_val
        if 'clef' in b:
            ret_val = -1
            return ret_val

        # Note case
        if 'note' in a and 'note' in b:
            a_note = self.note_to_num(''.join(a.split('-')[1].split('_')[0][:-1]))
            a_oct = int(a.split('_')[0][-1])
            b_note = self.note_to_num(''.join(b.split('-')[1].split('_')[0][:-1]))
            b_oct = int(b.split('_')[0][-1])
            if a_oct > b_oct:
                ret_val = 1
            elif a_oct == b_oct:
                ret_val = 1 if a_note > b_note else -1
            else:
                ret_val = -1

        # Rest case
        elif 'rest' in a and 'rest' not in b:
            ret_val = 1
        elif 'rest' in a and 'rest' in b:
            ret_val = 0
        else:
            ret_val = -1

        return ret_val

    def note_to_num(self, note):

        """
        Converts note to num for purpose of sorting
        """

        note_dict = {
            'Cb': 0,
            'C': 1,
            'C#': 2,
            'Db': 2,
            'D': 3,
            'D#': 4,
            'Eb': 4,
            'E': 5,
            'E#': 6,
            'Fb': 6,
            'F': 7,
            'F#': 8,
            'Gb': 8,
            'G': 9,
            'G#': 10,
            'Ab': 10,
            'A': 11,
            'A#': 12,
            'Bb': 12,
            'B': 13,
            'B#': 14,
        }

        try:
            return note_dict[note]
        except KeyError:
            try:
                return note_dict[note[:-1]]
            except KeyError:
                print('Error with note dict?',note)
                return 0
import argparse
from operator import itemgetter
from typing import TypeVar, Union, Generic
import fitz
import json
import re

def get_tag(element: str) -> tuple[str, str]:
    """Returns the tag for the element and the remaining text.
    :param element: element to get tag for
    :type element: str
    :rtype: str
    :return: tuple of tag and remaining text
    """
    re_pattern = r'\<.*?\>'
    if "<" in element and ">" in element:
        res = re.findall(re_pattern, element)
        tag: str = str(res[0].replace("<", "").replace(">", ""))
        line: str = re.sub(re_pattern, "", element)
        return (tag, line)
    else:
        return ("", element)


T = TypeVar('T')
class Note(dict, Generic[T]):
    def __init__(self, tag, value):
        self.tag = tag
        self.value = value
        dict.__init__(self, value=self.value, tag=self.tag)

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

    def toJSON(self):
        return json.dumps(self.__dict__, default=lambda o: o.__dict__,
            sort_keys=True, indent=4)

    def __dict__(self):
        return {'note': self.value, 'tag': self.tag}


class Element(dict, Generic[T]):
    """Represents an element in the document.
    :param value: the text of the element
    :type value: str
    :param tag: the tag of the element
    :type tag: str
    :param children: the children of the element
    :type children: list
    :param notes: the notes of the element
    :type notes: list
    """
    def __init__(self, element: str, max_header: int, root_header):
        (tag, line) = get_tag(element)
        self.in_list = False
        self.value: str = line
        self.tag: str = tag
        self.parent: Union['Element[T]', None] = None
        self.children: list['Element[T]'] = []
        self.notes: list[Note] = []
        self.is_header: bool = "h" in tag
        self.header_size: int = int(tag[1:]) if self.is_header else 0
        self.__root_header = root_header
        self.is_root_tag: bool = self.tag == self.__root_header
        self.largest_header = max_header
        self.drop_tag_list = []
        dict.__init__(self, value=self.value, tag=self.tag, notes=self.notes, children=self.children)

    def drop_tags(self, tags):
        self.drop_tag_list = tags

    def set_parent(self, parent: 'Element[T]'):
        self.parent = parent

    def add_child(self, child: 'Element[T]'):
        self.children.append(child)

    def add_header_element(self, element: 'Element[T]'):
        """Adds a child to the element.
        :param element: the raw child to add
        """
        def add_as_child(parent, element):
            element.set_parent(parent)
            parent.add_child(element)
            return element

        if self.parent is None: # if this is the root element
            return add_as_child(self, element)

        if self.header_size < element.header_size: # if the child is a larger header
            return add_as_child(self, element)

        current = self.parent
        while(current.parent is not None and current.header_size < element.header_size): # if the child is a smaller header
            current = current.parent

        if current.header_size == element.header_size and current.parent is not None:
            element.parent = current.parent
            current.parent.add_child(element)
            return

        element.parent = current
        current.children.append(element)



    def is_root_in_list(self):
        return self.get_root().in_list

    def set_root_in_list(self):
        root = self.get_root()
        root.in_list = True

    def get_root(self):
        iter = self
        count = 0
        while iter.parent is not None:
            count += 1
            iter = iter.parent
        return iter

    def add_note(self, note: str, tag: str):
        if any(map(tag.__contains__, self.drop_tag_list)):
            print(f'Dropping:{tag} - {note}')
            return
        self.notes.append(Note(tag, note))

    def include_tag(self):
        if self.tag == 'h1':
            return False
        return 'h' in self.tag or self.is_paragraph()

    def is_paragraph(self):
        if self.is_header:
            return self.header_size > self.largest_header
        return any(map(self.tag.__contains__, ['p', 's']))

    def exclude_tag(self):
        return not self.include_tag()

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

    def toJSON(self):
        return json.dumps(self.__dict__, default=lambda o: o.__dict__,
            sort_keys=True, indent=4)

    def __dict__(self):
        return {
            'value': self.value,
            'tag': self.tag,
            'children': self.children,
            'notes': self.notes
        }

def add_node(json_arrays: list, node: Element):
    if not node.is_root_in_list():
        node.set_root_in_list()
        json_arrays.append(node.get_root())
    return json_arrays

def make_nested_json(elements, max_header=6, root_header="h2", drop_tags=[]) -> tuple[ list[Element], list[Element] ]:
    """Turns an element array into a nested json array with h1 as root"""
    element_list: list[Element] = []
    json_arrays: list[Element] = []
    def keep_going():
        return len(elements) > 0

    def get_next_to_include():
        scan = Element(elements.pop(0), max_header, root_header)
        while(scan.exclude_tag()  and keep_going()):
            raw = elements.pop(0)
            scan = Element(raw, max_header, root_header)
        return scan

    last = None
    while(keep_going()):
        element = get_next_to_include()
        if len(drop_tags) > 0:
            element.drop_tags(drop_tags)
        if element.is_root_tag or last is None:
            json_arrays.append(element)
            last = element
            continue

        if element.is_paragraph():
            last.add_note(element.value, element.tag)
        else:
            element_list.append(element)
            last.add_header_element(element)
            last = element
    return (json_arrays, element_list)


def fonts(doc, granularity=False):
    """Extracts fonts and their usage in PDF documents.
    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param granularity: also use 'font', 'flags' and 'color' to discriminate text
    :type granularity: bool
    :rtype: [(font_size, count), (font_size, count}], dict
    :return: most used fonts sorted by count, font style information
    """
    styles = {}
    font_counts = {}

    for page in doc:
        blocks = page.get_text("dict")["blocks"] # get all text blocks
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # block contains text
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        if granularity:
                            identifier = "{0}_{1}_{2}_{3}".format(s['size'], s['flags'], s['font'], s['color'])
                            styles[identifier] = {'size': s['size'], 'flags': s['flags'], 'font': s['font'],
                                                  'color': s['color']} # store style information
                        else:
                            identifier = "{0}".format(s['size']) # store font size
                            styles[identifier] = {'size': s['size'], 'font': s['font']} # store style information

                        font_counts[identifier] = font_counts.get(identifier, 0) + 1  # count the fonts usage

    font_counts = sorted(font_counts.items(), key=itemgetter(1), reverse=True) # sort by count

    if len(font_counts) < 1: # no fonts found
        raise ValueError("Zero discriminating fonts found!") # check if there are any discriminating fonts

    return font_counts, styles


def font_tags(font_counts, styles):
    """Returns dictionary with font sizes as keys and tags as value.
    :param font_counts: (font_size, count) for all fonts occuring in document
    :type font_counts: list
    :param styles: all styles found in the document
    :type styles: dict
    :rtype: dict
    :return: all element tags based on font-sizes
    """
    p_style = styles[font_counts[0][0]]  # get style for most used font by count (paragraph)
    p_size = p_style['size']  # get the paragraph's size

    # sorting the font sizes high to low, so that we can append the right integer to each tag
    font_sizes = []
    for (font_size, count) in font_counts: # iterate through the font counts
        font_sizes.append(float(font_size)) # append font size to list
    font_sizes.sort(reverse=True) # sort the list in descending order

    # aggregating the tags for each font size
    idx = 0
    size_tag = {}
    for size in font_sizes: # iterate through the font sizes
        idx += 1
        if size == p_size: # if the font size is the same as the paragraph's size
            idx = 0 # reset the index
            size_tag[size] = '<p>' # append paragraph tag
        if size > p_size: # if the font size is bigger than the paragraph's size
            size_tag[size] = '<h{0}>'.format(idx) # append header tag
        elif size < p_size: # if the font size is smaller than the paragraph's size
            size_tag[size] = '<s{0}>'.format(idx) # append subheader tag

    return size_tag #  return header_para


def headers_para(doc, size_tag):
    """Scrapes headers & paragraphs from PDF and return texts with element tags.
    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param size_tag: textual element tags for each size
    :type size_tag: dict
    :rtype: list
    :return: texts with pre-prended element tags
    """
    header_para = []  # list with headers and paragraphs
    first = True  # boolean operator for first header
    previous_s = {}  # previous span

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # this block contains text

                # REMEMBER: multiple fonts and sizes are possible IN one block

                block_string = ""  # text found in block
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        # if the last two characters in bockstring are spaces,
                        # remove one
                        if s['text'].strip():  # removing whitespaces:
                            if first:
                                previous_s = s
                                first = False
                                block_string = size_tag[s['size']] + s['text']
                            else:
                                if s['size'] == previous_s['size']:

                                    if block_string and all((c == "|") for c in block_string):
                                        # block_string only contains pipes
                                        block_string = size_tag[s['size']] + s['text']
                                    if block_string == "":
                                        # new block has started, so append size tag
                                        block_string = size_tag[s['size']] + s['text']
                                    else:  # in the same block, so concatenate strings
                                        block_string += " " + s['text']

                                else:
                                    header_para.append(block_string)
                                    block_string = size_tag[s['size']] + s['text']

                                previous_s = s

                    # new block started, indicating with a pipe
                    # block_string += "|"

                # remove any double spaces
                block_string = block_string.replace("  ", " ")
                # only append if block_string is not empty
                if block_string:
                    header_para.append(block_string)

    return header_para

# when passed an element array, build a dictionary of all the elements
def build_dict(elements):
    """Builds a dictionary of all the elements.
    :param elements: list of elements
    :type elements: list
    :rtype: dict
    :return: dictionary of all the elements
    """
    for element in elements:
        # if the string contains < or >, continue
        if "<" in element or ">" in element:
            res = re.findall(r'\<.*?\>', element)
            if "h" in res[0]:
                print(res)

def reverse_notes(flat):
    for node in flat:
        node.notes.reverse()


def main():
    # use argparse to get the input PDF file
    parser = argparse.ArgumentParser(description='Extract text from PDF')
    parser.add_argument('-i', '--input', help='input file', required=True)
    # use argparse to get the max header size
    parser.add_argument('-m', '--max', help='max header', required=False)

    # use argparse to get the root header size
    parser.add_argument('-r', '--root', help='root header', required=False)

    # add param to enable note reversal
    parser.add_argument('-n', '--reverse', help='reverse notes', required=False)

    # add param to pass csv of tags to drop
    parser.add_argument('-d', '--drop', help='drop tags', required=False)

    args = parser.parse_args()
    input_file = args.input
    output_file = f"output/{(input_file.split('.')[0] + '.json').split('/')[-1]}"

    doc = fitz.open(input_file)

    font_counts, styles = fonts(doc, granularity=False) # get font counts and styles

    size_tag = font_tags(font_counts, styles) # get font tags

    elements = headers_para(doc, size_tag) # get headers and paragraphs

    # get the root header
    root_header = args.root or "h2"

    # get the max header
    max_header = 6 if args.max == None else int(args.max)

    # parse drop tag csv into a list
    drop_tags = args.drop.split(',') if args.drop else []

    (nested, flat)= make_nested_json(elements, max_header, root_header, drop_tags)

    # if note reversal is enabled, reverse the reverse_notes
    if args.reverse:
        print(f'Reversing the notes...')
        reverse_notes(flat)

    # elements = Elements()
    # elements.load_from_list(nested)
    # for element in elements:
    #     print(element.value)

    print(f'Writing to {output_file} [{len(nested)}] elements')
    with open(output_file, 'w') as json_out: # write to json file
        json.dump(nested, json_out, indent=4) # dump the elements to json file


if __name__ == '__main__':
    main()

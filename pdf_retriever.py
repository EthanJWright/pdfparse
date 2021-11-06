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
    def __init__(self, element: str):
        (tag, line) = get_tag(element)
        self.in_list = False
        self.value: str = line
        self.tag: str = tag
        self.parent: Union['Element[T]', None] = None
        self.children: list['Element[T]'] = []
        self.notes: list[str] = []
        self.is_header: bool = "h" in tag
        self.header_size: int = int(tag[1:]) if self.is_header else 0
        self.is_root_tag: bool = self.tag == 'h2'
        self.largest_header = 6
        dict.__init__(self, value=self.value, tag=self.tag, notes=self.notes, children=self.children)

    def set_parent(self, parent: 'Element[T]'):
        self.parent = parent

    def add_child(self, child: 'Element[T]'):
        self.children.append(child)

    def add_header_element(self, element: 'Element[T]'):
        """Adds a child to the element.
        :param element: the raw child to add
        """
        if self.header_size < element.header_size:
            element.parent = self
            self.add_child(element)
            return

        if self.parent is not None and self.parent.header_size <= element.header_size:
            element.set_parent(self.parent)
            self.parent.add_header_element(element)
            return

        if self.header_size < element.header_size:
            self.set_parent(element)
            element.set_parent(self)
            return

        if self.parent is not None:
            return self.parent.add_header_element(element)
        element.set_parent(self)
        self.add_child(element)

    def is_root_in_list(self):
        return self.get_root().in_list

    def set_root_in_list(self):
        root = self.get_root()
        root.in_list = True

    def get_root(self):
        if self.parent is None:
            return self
        else:
            return self.parent.get_root()

    def add_note(self, note: str):
        self.notes.append(note)

    def include_tag(self):
        if self.tag == 'h1':
            return False
        return 'h' in self.tag or self.is_paragraph()

    def is_paragraph(self):
        if self.is_header:
            return self.header_size > self.largest_header
        return 'p' in self.tag or 's' in self.tag

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

def make_nested_json(elements, json_arrays, current):
    """Turns an element array into a nested json array with h1 as root"""
    if len(elements) == 0:
        return add_node(json_arrays, current)

    raw = elements.pop(0)
    element = Element(raw)
    while(element.exclude_tag()  and len(elements) > 0):
        raw = elements.pop(0)
        element = Element(raw)
    new_json = element
    if not current:
        current = new_json

    if element.is_root_tag:
        if len(elements) > 0:
            json_arrays = add_node(json_arrays, current)
        return make_nested_json(elements, json_arrays, new_json)

    if element.is_paragraph():
        current.add_note(element.value)
        return make_nested_json(elements, json_arrays, current)
    else:
        current.add_header_element(element)
        return make_nested_json(elements, json_arrays, element)


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
        blocks = page.getText("dict")["blocks"] # get all text blocks
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
        blocks = page.getText("dict")["blocks"]
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


def main():

    OUTPUT_FILE = './output/blue_alley.json'
    INPUT_FILE = './input/blue_alley.pdf'
    doc = fitz.open(INPUT_FILE)

    font_counts, styles = fonts(doc, granularity=False) # get font counts and styles

    size_tag = font_tags(font_counts, styles) # get font tags

    elements = headers_para(doc, size_tag) # get headers and paragraphs

    nested = make_nested_json(elements, [], {})

    with open(OUTPUT_FILE, 'w') as json_out: # write to json file
        json.dump(nested, json_out, indent=4) # dump the elements to json file


if __name__ == '__main__':
    main()

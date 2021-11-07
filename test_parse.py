import json

def test_get_tag():
    from parse import get_tag
    assert get_tag('<h2>Test H2') == ('h2', 'Test H2')
    assert get_tag('<h3>Test H3') == ('h3', 'Test H3')
    assert get_tag('<p>Test P') == ('p', 'Test P')

def test_make_folder_one_layer_json():
    from parse import make_nested_json
    elements = ['<h2>Waterdeep Dragon Heist', '<h3>Chapter 1', '<p>So start by doing...']
    folders = make_nested_json(elements)
    assert len(folders) == 1
    assert folders[0]['value'] == 'Waterdeep Dragon Heist'
    assert len(folders[0].children) == 1
    assert folders[0].children[0]['value'] == 'Chapter 1'


def test_make_folder_two_layer_json():
    from parse import make_nested_json
    elements = ['<h2>Waterdeep Dragon Heist', '<h3>Chapter 1', '<h3>Chapter 2', '<p>So start by doing...', '<h2>Blue Alley', '<h3>Rewards', '<p>GOLD']
    folders = make_nested_json(elements)
    assert len(folders) == 2
    assert folders[0]['value'] == 'Waterdeep Dragon Heist'
    assert len(folders[0].children) == 2
    assert folders[1]['value'] == 'Blue Alley'


def test_make_folder_ignored_tags():
    from parse import make_nested_json
    elements = ['<h2>Waterdeep Dragon Heist', '<s1>small text','<h3>Chapter 1', '<s2>Other text','<p>So start by doing...']
    folders = make_nested_json(elements)
    assert len(folders) == 1
    assert folders[0]['value'] == 'Waterdeep Dragon Heist'
    assert len(folders[0].children) == 1
    assert folders[0].children[0]['value'] == 'Chapter 1'

def test_element_ordering():
    from parse import make_nested_json
    elements = ['<h2>Waterdeep Dragon Heist', '<h6>some sub section', '<h3>Chapter 1', '<h6>another sub section', '<h3>Chapter 2']
    folders = make_nested_json(elements)
    assert len(folders) == 1
    assert folders[0]['value'] == 'Waterdeep Dragon Heist'
    assert len(folders[0].children) == 3
    assert folders[0].children[1]['value'] == 'Chapter 1'
    assert folders[0].children[2]['value'] == 'Chapter 2'

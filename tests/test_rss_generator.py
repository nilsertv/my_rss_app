import os
import xml.etree.ElementTree as ET
from pathlib import Path
from src.core.rss_generator import RSSGenerator


def test_rss_generator_empty_posts(tmp_path):
    generator = RSSGenerator([])
    out_file = tmp_path / "test_feed.xml"
    generator.save_rss(str(out_file))
    
    assert out_file.exists()
    tree = ET.parse(out_file)
    root = tree.getroot()
    assert root.tag == 'rss'
    channel = root.find('channel')
    assert channel is not None
    assert len(channel.findall('item')) == 0


def test_rss_generator_with_items(tmp_path):
    posts = [
        {
            'title': 'Test Article 1',
            'url': 'https://example.com/1',
            'content': 'Summary content of article 1',
            'section': 'Noticias',
            'image_url': 'https://example.com/img1.jpg'
        },
        {
            'title': 'Test Article 2',
            'url': 'https://example.com/2',
            'content': 'Summary content of article 2',
            'section': 'CienciayTech',
            'image_url': None
        }
    ]
    
    generator = RSSGenerator(posts)
    out_file = tmp_path / "feed.xml"
    generator.save_rss(str(out_file))
    
    assert out_file.exists()
    tree = ET.parse(out_file)
    root = tree.getroot()
    channel = root.find('channel')
    assert channel is not None
    
    items = channel.findall('item')
    assert len(items) == 2
    
    # Verify Item 1
    item1 = items[0]
    assert item1.find('title').text == '#Noticias Test Article 1'
    assert item1.find('link').text == 'https://example.com/1'
    assert item1.find('description').text == 'Summary content of article 1'
    assert item1.find('image').text == 'https://example.com/img1.jpg'
    
    # Verify Item 2 (without image)
    item2 = items[1]
    assert item2.find('title').text == '#CienciayTech Test Article 2'
    assert item2.find('image') is None

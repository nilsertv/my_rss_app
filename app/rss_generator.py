from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
import datetime

class RSSGenerator:
    def __init__(self, posts):
        self.posts = posts

    def generate_rss(self):
        rss = Element('rss')
        rss.set('version', '2.0')
        channel = SubElement(rss, 'channel')

        title = SubElement(channel, 'title')
        title.text = 'Latest Posts and Videos'

        link = SubElement(channel, 'link')
        link.text = 'http://example.com/rss'

        description = SubElement(channel, 'description')
        description.text = 'This RSS feed contains the latest posts and videos.'

        for post in self.posts:
            item = SubElement(channel, 'item')

            title = SubElement(item, 'title')
            title.text = post['title']

            link = SubElement(item, 'link')
            link.text = post['url']

            description = SubElement(item, 'description')
            description.text = post['content']

        return ElementTree(rss)

    def save_rss(self, filename='feed.xml'):
        tree = self.generate_rss()
        tree.write(filename, encoding='utf-8', xml_declaration=True)

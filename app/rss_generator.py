from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
import logging

class RSSGenerator:
    def __init__(self, posts):
        self.posts = posts
        self.logger = logging.getLogger('RSSLogger')

    def generate_rss(self):
        self.logger.info("Generating RSS feed...")
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
            
            section = post.get('section', 'General')
            item_title = SubElement(item, 'title')
            item_title.text = f"#{section} {post.get('title', 'No Title')}"

            item_link = SubElement(item, 'link')
            item_link.text = post.get('url', 'No URL')

            item_description = SubElement(item, 'description')
            item_description.text = post.get('content', 'No Content')

        self.logger.info("RSS feed generated.")
        return ElementTree(rss)

    def save_rss(self, filename='feed.xml'):
        tree = self.generate_rss()
        tree.write(filename, encoding='utf-8', xml_declaration=True)
        self.logger.info(f"RSS feed saved to {filename}")

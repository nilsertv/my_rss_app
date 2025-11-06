from xml.etree.ElementTree import Element, SubElement, ElementTree
import xml.dom.minidom
import logging

class RSSGenerator:
    def __init__(self, posts):
        self.posts = posts
        self.logger = logging.getLogger('RSSLogger')

    def generate_rss(self):
        self.logger.info("Generating RSS feed...")
        rss = Element('rss')
        rss.set('version', '2.0')
        rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
        
        channel = SubElement(rss, 'channel')

        title = SubElement(channel, 'title')
        title.text = 'Latest Posts and Videos'

        link = SubElement(channel, 'link')
        link.text = 'https://my-rss-app.fly.dev/'

        description = SubElement(channel, 'description')
        description.text = 'This RSS feed contains the latest posts and videos from various sources.'

        language = SubElement(channel, 'language')
        language.text = 'es'

        for post in self.posts:
            item = SubElement(channel, 'item')
            
            section = post.get('section', 'General')
            item_title = SubElement(item, 'title')
            item_title.text = f"#{section} {post.get('title', 'No Title')}"

            item_link = SubElement(item, 'link')
            item_link.text = post.get('url', 'No URL')

            item_description = SubElement(item, 'description')
            item_description.text = post.get('content', 'No Content')
            
            # Agregar imagen si disponible
            image_url = post.get('image_url')
            if image_url:
                item_image = SubElement(item, 'image')
                item_image.text = image_url
            
            # Agregar GUID (identificador único)
            item_guid = SubElement(item, 'guid')
            item_guid.set('isPermaLink', 'true')
            item_guid.text = post.get('url', 'No URL')

        self.logger.info("RSS feed generated.")
        return ElementTree(rss)

    def save_rss(self, filename='feed.xml'):
        tree = self.generate_rss()
        root = tree.getroot()
        
        if root is None:
            self.logger.error("Failed to generate RSS tree")
            return
        
        # Convertir a string y formatear con minidom
        from xml.etree.ElementTree import tostring
        xml_string = tostring(root, encoding='unicode')
        
        # Pretty print
        dom = xml.dom.minidom.parseString(xml_string)
        pretty_xml = dom.toprettyxml(indent='  ', encoding='utf-8')
        
        # Escribir al archivo
        with open(filename, 'wb') as f:
            f.write(pretty_xml)
        
        self.logger.info(f"RSS feed saved to {filename}")

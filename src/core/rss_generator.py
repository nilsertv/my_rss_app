from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring
import xml.dom.minidom
import logging
from email.utils import format_datetime
from datetime import datetime, timezone


class RSSGenerator:
    def __init__(
        self,
        posts,
        title: str = 'Latest Posts and Videos',
        description: str = 'This RSS feed contains the latest posts and videos from various sources.',
        feed_url: str = None
    ):
        self.posts = posts
        self.title = title
        self.description = description
        self.feed_url = feed_url
        self.logger = logging.getLogger('RSSLogger')

    def generate_rss(self):
        self.logger.info("Generating RSS feed...")
        rss = Element('rss')
        rss.set('version', '2.0')
        rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')

        channel = SubElement(rss, 'channel')

        title = SubElement(channel, 'title')
        title.text = self.title

        from src.config import APP_URL
        link = SubElement(channel, 'link')
        link.text = self.feed_url or APP_URL

        description = SubElement(channel, 'description')
        description.text = self.description

        language = SubElement(channel, 'language')
        language.text = 'es'

        for post in self.posts:
            item = SubElement(channel, 'item')

            section = post.get('section', 'General')
            item_title = SubElement(item, 'title')
            raw_title = post.get('title', 'No Title')
            item_title.text = raw_title if raw_title.startswith(f"#{section}") else f"#{section} {raw_title}"

            item_link = SubElement(item, 'link')
            item_link.text = post.get('url', 'No URL')

            item_description = SubElement(item, 'description')
            item_description.text = post.get('content', 'No Content')

            category_el = SubElement(item, 'category')
            category_el.text = section

            # Agregar imagen si disponible
            image_url = post.get('image_url')
            if image_url:
                item_image = SubElement(item, 'image')
                item_image.text = image_url

            # Agregar pubDate en formato RFC 2822 para compatibilidad con IFTTT
            ts = post.get('timestamp')
            if ts:
                try:
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    elif isinstance(ts, datetime):
                        dt = ts
                    else:
                        dt = None
                    if dt:
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        pub_date = SubElement(item, 'pubDate')
                        pub_date.text = format_datetime(dt)
                except Exception:
                    pass

            # Agregar GUID (identificador único)
            item_guid = SubElement(item, 'guid')
            item_guid.set('isPermaLink', 'true')
            item_guid.text = post.get('url', 'No URL')

        self.logger.info("RSS feed generated.")
        return ElementTree(rss)

    def to_xml_bytes(self) -> bytes:
        """Retorna el RSS formateado como bytes UTF-8 listo para respuesta HTTP o disco."""
        tree = self.generate_rss()
        root = tree.getroot()
        if root is None:
            return b""
        xml_string = tostring(root, encoding='unicode')
        dom = xml.dom.minidom.parseString(xml_string)
        return dom.toprettyxml(indent='  ', encoding='utf-8')

    def save_rss(self, filename='feed.xml'):
        pretty_xml = self.to_xml_bytes()
        if not pretty_xml:
            self.logger.error("Failed to generate RSS tree")
            return

        with open(filename, 'wb') as f:
            f.write(pretty_xml)

        self.logger.info(f"RSS feed saved to {filename}")

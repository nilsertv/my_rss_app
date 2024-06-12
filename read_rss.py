import xml.etree.ElementTree as ET

def read_rss(filename):
    tree = ET.parse(filename)
    root = tree.getroot()

    channel = root.find('channel')
    if channel is not None:
        title = channel.find('title').text
        link = channel.find('link').text
        description = channel.find('description').text

        print(f"Channel Title: {title}")
        print(f"Channel Link: {link}")
        print(f"Channel Description: {description}")
        print("\nEntries:")

        for item in channel.findall('item'):
            item_title = item.find('title').text
            item_link = item.find('link').text
            item_description = item.find('description').text
            print(f"Title: {item_title}")
            print(f"Link: {item_link}")
            print(f"Description: {item_description}\n")
    else:
        print("No channel found in the RSS feed.")

# Leer el archivo RSS
read_rss('feed.xml')

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class XiechengItem(scrapy.Item):
    # define the fields for your item here like:
    title = scrapy.Field()
    subtitle = scrapy.Field()
    score = scrapy.Field()
    soldCount=scrapy.Field()
    commentCount=scrapy.Field()
    price=scrapy.Field()
    source_url=scrapy.Field()
    pass

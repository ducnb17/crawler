import scrapy


class CrawlerItem(scrapy.Item):
    """Schema dữ liệu cơ bản cho crawler."""

    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    price = scrapy.Field()
    availability = scrapy.Field()
    crawled_at = scrapy.Field()

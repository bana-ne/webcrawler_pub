# webcrawler_pub
Public copy of webcrawler project for an idea a friend had
-------------
# webcrawler
Webcrawler to extract tool information

Current Search Terms are hard coded into scrawler.py: 
"Dremometer", "Dremoplus", "Torcofix"


# TODO:
1. extract csv from 
    * [x] __gedore__
        
        Since 29.01.2021
      
        **columns**|manufacturer|ean-code|articlename_manufacturer|articlenumber_manufacturer|dkm-code|uvp|description|details|product_img_urls|downloaded_imgs
        :--- |:--- |:--- |:--- |:--- |:--- |:--- |:--- |:--- |:--- |:---
        **css class** |- |ean |article-description     |code-number               |article-number|price|description|product-accordion|slider-image| -
        **info**| str "Gedore"|Product Name | EAN code | Article Number | DKM code? --> searchable on Gedore | Price incl. tax; if NA no price specified| Product description in html ul tags | Name (<ean>.csv --> sep='&#x7c;') csv with downloaded product details | the product image urls separated by single space | filename of the downloaded images
    
    * [ ] __hoffmann-group__ -> skip, because information cannot be mapped

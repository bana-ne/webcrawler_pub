# Script to scrape part info from the internet
# Author: Vanessa Schmoll
# Email: schmollv@mytum.de
# Last Modified: December 2020

# import packages
import os
import pandas as pd
import requests
import shutil
from time import sleep
from bs4 import BeautifulSoup
# import selenium to extract all search results = all products
from contextlib import closing
from selenium.webdriver import Firefox
from selenium.common.exceptions import ElementNotInteractableException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_headers import Headers  # for random header generation
from tqdm import tqdm  # for progressbar


# TODO write main.py and only keep processing functions here???

# define functions
def df2str(df: pd.DataFrame,sep: str = "|") -> str:
    return df.to_csv(sep=sep,index=False,index_label=False)


# load data
def load_data(csv_name: str,proj_dir: str = os.getcwd()) -> pd.DataFrame:
    """
    function to load csv data as pandas DataFrame
    :param csv_name: name and extension of the csv file to be loaded
    :param proj_dir: path to csv file
    :return: pandas DataFrame
    """
    csv_path = os.path.join(proj_dir, csv_name)
    return pd.read_csv(csv_path)


# write data
def write_data(df: pd.DataFrame,file_name: str,proj_dir: str = os.getcwd(),sep: str = ",",index: bool = False) -> str:
    """
    function to write text files from pandas DataFrame
    :param index: bool - Whether to print the pandas DataFrame index. Default: False
    :rtype: str
    :param df: pandas DataFrame
    :param file_name: file name to write data to
    :param proj_dir: path to file
    :param sep: separator to be used when writing file
    :return: The filename of the written csv
    """
    # check if outdir exists or create it otherwise
    if not os.path.exists(proj_dir):
        os.makedirs(proj_dir)
    csv_path = os.path.join(proj_dir,file_name)
    df.to_csv(csv_path,sep=sep,index=index)
    return csv_path


# extract images from websites and save to specified location
def save_img_from_url(url: str,outdir: str = "") -> str:
    """
    Function to download images to specified directory.
    :param url:
    :param outdir:
    :return: The filename of the saved image None if file could not be saved.
    """
    filename = os.path.join(outdir,url.split("/")[-1])

    # open url image and return stream content
    r = requests.get(url,stream=True)
    sleep(0.01)
    # check if image was successfully retrieved
    if r.status_code == 200:
        # set decode content value to true, otherwise downloaded file size will be zero
        r. raw.decode_content = True
        # check if outdir exists or create it otherwise
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        # write image to file with shutil
        with open(filename,"wb") as img:
            shutil.copyfileobj(r.raw,img)
        return filename

    else:
        print("[WARNING:] Download for product image at url (" + url + ") failed.")
        return None


def process_gedore(url: str, img_dir: str = None) -> pd.DataFrame:
    """
    Function that extracts Product information from the Gedore website. If img_dir is specified product images will be
    downloaded to that directory keeping the original names.
    :param url: The website from which the data should be extracted. This function was implemented on the gedore website (last checked 28.01.2021) with a list of products (e.g. from a search or product line).
    :param img_dir: The directory in which to download the product images. If None (default) Images will not be downloaded, and the cell
    :return: Pandas data frame with products as rows and [manufacturer,ean-code, articlename_gedore, articlenumber_gedore, dkm, uvp, gedore_img_urls,downloaded_images] as column
    """
    # assign class names to variables
    class_scroll_button = "show-more"
    class_nr_pages = "result-text"  # li
    manufacturer = "Gedore"
    class_product_link = 'teaser-link'
    class_product_description = "description"
    class_product_details = "product-accordion"
    class_product_images = 'slider-image'
    class_ean = "ean"
    pre_ean = "EAN"
    url_domain = "/".join(url.split("/",3)[:3]) if url.startswith("http") else url.split("/")[0]
    #url_page_suffix = "?page={}&pagesize={}"  # if next button pages can be accessed with ?page=x&pagesize=y within url
    url_page_format = "{url}?page={page}&pagesize={pagesize}"
    class_article_name = "article-description"
    class_article_number = "code-number"
    class_dkm_number = "article-number"
    class_uvp = "price"
    content_columns = ["group","info","value"]
    img_final_dir = "img"
    csv_final_dir = "csv"

    def process_product_listing(bs_obj:BeautifulSoup):
        """
        Function to extract relevant information from product search/listing url.
        :param bs_obj: A BeautifulSoup object from the product search/listing url
        :return: A tuple with (article_name_manufacturer,article_number_manufacturer,dkm_number,product_urls)
        """
        article_name = [p.text.strip() for p in bs_obj.find_all('div', {"class": class_article_name})]
        article_number = [p.text.strip() for p in bs_obj.find_all('span', {"class": class_article_number})]
        dkm_nr = [p.text.strip() for p in bs_obj.find_all('span', {"class": class_dkm_number})]  # is this the DKM number???
        product_urls_list = [p["href"] for p in bs_obj.find_all('a', class_=class_product_link, href=True)]
        return (article_name,article_number,dkm_nr,product_urls_list)

    def process_details(bs_prod:BeautifulSoup):
        """
        Extract correct information in dataframe structure from details list on product page
        :param bs_prod: the BeautifulSoup object from a product page
        :return: returns a pandas DataFrame
        """
        html_list = bs_prod.find('div',class_=class_product_details).findChild("ul")
        tables = [header.text.strip() for header in html_list.findChildren("a")]
        contents = []  #[[el.split(": ")] for a in html_list.findChildren("ul",class_="gedore-list") for el in a.text.strip().split("\n")]
        for i,a in enumerate(html_list.findChildren("ul",class_="gedore-list")):
            cur_tab = []
            for el in a.text.strip().split("\n"):
                cur_tab.append([tables[i]]+el.split(": "))
            contents.append(pd.DataFrame(cur_tab,columns=content_columns))
        return pd.concat(contents)

    def process_prod_page(product_url:str):
        """
        Function to extract information from individual product pages
        :rtype: tuple(str,str(html list),str,list(str),list(str))
        :param product_url: The url for the product
        :return: (ean number, uvp, product description, product details, gedore_img_urls,downloaded_images)
        """
        downloaded_images = []
        #details_csv = ""
        cur_bs = BeautifulSoup(requests.get(product_url).content, "lxml")
        sleep(0.01)
        img_urls = [url_domain + i["src"].split("?", 1)[0] for i in cur_bs.find_all("img", class_=class_product_images, src=True)]
        if img_dir:  # if outdir is specified save images to this directory
            for img in img_urls:
                cur_img = save_img_from_url(img,os.path.join(img_dir,img_final_dir))
                if cur_img:
                    downloaded_images.append(cur_img)
                else:
                    print(product_url)

        uvp_prod = cur_bs.find('span', class_=class_uvp)
        uvp_prod = uvp_prod.text.strip() if uvp_prod else "NA"
        ean = cur_bs.find('div', class_=class_ean).text.replace(pre_ean, "").strip()
        description = str(cur_bs.find('div',class_=class_product_description).findChild("ul"))
        details = process_details(cur_bs)
        if img_dir:
            # details_csv = write_data(details,ean+".csv",img_dir,sep="|")
            details = write_data(details,ean+".csv",os.path.join(img_dir,csv_final_dir),sep="|")
        #details = os.linesep.join([details_csv,df2str(details)]).lstrip()
        else:
            details = df2str(details)
        return ean,uvp_prod,description,details,img_urls,downloaded_images

    # get all elements from Gedore search result
    # create BeautifulSoup object from request url
    #bs = BeautifulSoup(requests.get(url).content, "html.parser")
    bs = BeautifulSoup(requests.get(url).content, "lxml")
    # if show more button available click on it until it disappears and all products are displayed
    if bs.find_all('a',class_=class_scroll_button):
        # disable browser view
        options = Options()
        options.add_argument('--headless')
        with closing(Firefox(options=options)) as driver:
            driver.get(url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, class_scroll_button)))
            button = driver.find_element_by_class_name(class_scroll_button)
            clicks = 0
            while True:
                print("\rShow More Products: [{0}] {1} % ".format("#" * clicks + "-" * 25, clicks))
                try:
                    button.click()
                    clicks += 1
                    # sleep for 1 second because for some reason selenium wait did not work...
                    sleep(1)
                except ElementNotInteractableException:
                    break
            # store it to string variable
            page_source = driver.page_source
            bs = BeautifulSoup(page_source, "html.parser")
    # case if next button and not show more
    elif bs.find("li",class_=class_nr_pages):
        """
        # if number of products displayed at once can be selected use max
        button_list = [int(x["value"]) for x in bs.find_all("button", value=True) if x["value"].isdigit()]
        if len(button_list) > 0:
           max_products_on_page = max(button_list)
        
           max_button = bs.find("button", attrs={"value":max_products_on_page})
           # select this button in selenium with
           driver.find_element_by_xpath('//button["value='+max_products_on_page+'"]')
        """
        # use currently selected pagesize
        pagesize = bs.find("li", class_="selected").findChild("button",value=True)["value"]
        page_nr = int(bs.find("li",class_=class_nr_pages).findChild("span").text.split(" von ")[1])
        bs = []
        print("Creating bs objects for product listing ...")
        for page in tqdm(range(1,page_nr+1)):
            page_url = url_page_format.format(url=url.split("?")[0], page=page,pagesize=pagesize)
            bs.append(BeautifulSoup(requests.get(page_url).content,"lxml"))
            sleep(0.01)

    # Extract information from product listing/search
    if type(bs) == list:  # if multiple BeautifulSoup objects in a list within variable bs
        article_name_manufacturer = []
        article_number_manufacturer = []
        dkm_number = []
        product_urls = []
        for bs_cur in bs:
            cur_article_name_manufacturer,cur_article_number_manufacturer,cur_dkm_number,cur_product_urls = process_product_listing(bs_cur)
            article_name_manufacturer += cur_article_name_manufacturer
            article_number_manufacturer += cur_article_number_manufacturer
            dkm_number += cur_dkm_number
            product_urls += cur_product_urls
    else:  # if bs is a BeautifulSoup object
        article_name_manufacturer, article_number_manufacturer, dkm_number, product_urls = process_product_listing(bs)

    # Extract EAN code, product description, details and images from each product url
    print("\nExtracting info from product pages ...")
    ean = []
    uvp = []
    description = []
    details = []
    product_img_urls = []
    downloaded_imgs = []
    for product_url in tqdm(product_urls):
        cur_ean,cur_uvp,cur_description,cur_details,cur_product_img_urls,cur_downloaded_imgs = process_prod_page(product_url)
        ean.append(cur_ean)
        ean.append(cur_uvp)
        description.append(cur_description)
        details.append(cur_details)
        product_img_urls.append(" ".join(cur_product_img_urls))
        downloaded_imgs.append(" ".join(cur_downloaded_imgs))
    # create DataFrame with all information
    gedore_df = pd.DataFrame({"manufacturer":manufacturer,"ean-code":ean,"articlename_manufacturer":article_name_manufacturer,"articlenumber_manufacturer":article_number_manufacturer,"dkm-code":dkm_number,"uvp":uvp,"description":description,"details":details,"product_img_urls":product_img_urls,"downloaded_imgs":downloaded_imgs})
    return gedore_df


def process_tooler(term_url_dict,key="tooler"):
    """
    TODO
    :param term_url_dict:
    :param key:
    :return:
    """
    # assign class names to variables
    class_scroll_button = "div.amscroll-load-button"
    manufacturer = "Gedore"
    class_product_link = "a.product-item-link"
    class_ean = "ean"
    pre_ean = "EAN"
    class_article_name = "article-description"
    class_article_number = "code-number"
    class_dkm_number = "article-number"
    class_uvp = "price"
    # generate fake headers
    headers = Headers().generate()

    # 1. Extract all product links from search results
    # create BeautifulSoup object from request url
    bs = BeautifulSoup(requests.get(term_url_dict[key], headers=headers).content, "lxml")
    # extract all urls from products in search result
    product_urls = [p["href"] for p in bs.select(class_product_link)]
    # if more than one pages go through each page and append the urls to product_urls
    if bs.select(class_scroll_button):
        # disable browser view
        options = Options()
        options.add_argument('--headless')
        with closing(Firefox(options=options)) as driver:
            driver.get(term_url_dict[key])
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, class_scroll_button)))
            driver.find_element_by_id("popin_tc_privacy_button").click()
            clicks = 0
            while True:
                button = driver.find_element_by_css_selector(class_scroll_button)
                driver.execute_script("arguments[0].scrollIntoView();", button)
                button.click()
                # sleep for 1 second because for some reason selenium wait did not work...
                sleep(1)
                # store it to string variable and append articles from current page
                page_source = driver.page_source
                bs = BeautifulSoup(page_source, "html.parser")
                # append product urls for current page
                product_urls += [p["href"] for p in bs.find_all('a', class_=class_product_link, href=True)]
                clicks += 1
                print(clicks)
                if not bs.find_all('button', class_=class_scroll_button):
                    break
    # 2. Go through each product page and extract relevant information
    # 2.1 check wh
    test = pd.read_html(
        "https://www.tooler.de/handwerkzeuge/drehmomentwerkzeuge/drehmomentschluessel/gedore-drehmomentschluessel-6234.html",
        match="Katalogartikelnr.", flavor="lxml", index_col=0)


def process_mercateo(term_url_dict,key="mercateo"):
    """
    TODO
    :param term_url_dict:
    :param key:
    :return:
    """


def process_contorion(term_url_dict,key="contorion"):
    """
    TODO
    :param term_url_dict:
    :param key:
    :return:
    """


def process_eurafco(term_url_dict,key="eurafco"):
    """
    TODO
    :param term_url_dict:
    :param key:
    :return:
    """


# initialize variables TODO use argparse or file to get search terms?
proj_dir = os.getcwd()
search_terms = ["Dremometer", "Dremoplus", "Torcofix"]
manufacturer = "Gedore"
# create list of base urls with place holder @1, @2 to replace search term
base_url_dict = {"gedore": "https://www.gedore.com/de-de/suche?q=@2&category=products",
                 #"hoffmann-group" : "https://www.hoffmann-group.com/DE/de/hom/v2/search?type=product&page=&sort=&tId=170&search=@1+@2",
                 "tooler": "https://www.tooler.de/catalogsearch/result/?limit=120&q=@1+@2",
                 "mercateo": "https://www.mercateo.com/kw/@1(20)@2/@1_@2.html?ViewName=live~secureMode",
                 "contorion": "https://www.contorion.de/search/@1/marke1?q=@2",
                 "eurafco": "https://www.eurafco.com/deu/catalogsearch/result/?cat=0&q=@1+@2",
                 }
"""
gedore_list = []
for term in search_terms:
    # replace manufacturer and search term in url to extract wanted product list from url
    term_url_dict = base_url_dict.copy()
    for key in term_url_dict.keys():
        term_url_dict[key] = term_url_dict[key].replace("@1",manufacturer).replace("@2", term)

        if key == "gedore":
            gedore_df = process_gedore(term_url_dict[key],os.path.join(proj_dir,key))
            print("appending gedore csv for term: " + term)
            gedore_list.append(gedore_df)
       # elif key == "hoffmann-group":
       #     hoffmann_df = process_hoffmann(url,key)
        elif key == "tooler":
            tooler_df = process_tooler(term_url_dict,key)
        elif key == "mercateo":
            mercateo_df = process_mercateo(term_url_dict,key)
        elif key == "contorion":
            contorion_df = process_contorion(term_url_dict,key)
        elif key == "eurafco":
            eurafco_df = process_eurafco(term_url_dict,key)
        else:
            print("[WARNING:] URL key processing not yet defined!\nSkipping key: " + key )

        # TODO merge data frames with outer join and write to csv file

gedore_all = pd.concat(gedore_list)
write_data(gedore_all,"gedore_all.csv",proj_dir=proj_dir,sep=";")
"""
# call function for Drehmomentwerkzeuge TODO do not trash your scripts!

url = "https://www.gedore.com/de-de/produkte/drehmomentwerkzeuge?pagesize=24&page=1"
key = "gedore"
outdir = os.path.relpath(os.path.join(proj_dir,"data",key),proj_dir)
gedore_df = process_gedore(url,outdir)
write_data(gedore_df,"data/gedore_drehmomentwerkzeuge.csv",sep=";")

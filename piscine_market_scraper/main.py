import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import logging
from requests.exceptions import RequestException
import re
import time

# Set up logging to file and console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
file_handler = logging.FileHandler('scraper.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def sanitize_filename(name):
    return re.sub(r'[^\w\s_-]', '', name).strip().replace(' ', '_')

def download_image(url, folder, name, extension=None):
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        if extension:
            img_name = sanitize_filename(name) + extension
        else:
            img_name = sanitize_filename(name) + os.path.splitext(url.split("/")[-1])[1]
        
        img_path = os.path.join(folder, img_name)
        with open(img_path, 'wb') as file:
            file.write(response.content)
        logging.info(f"Downloaded image: {img_name} from {url}")
        return img_name
    except RequestException as e:
        logging.error(f"Failed to download image {url}: {e}")
        raise

def get_subcategories(main_url):
    try:
        logging.info(f"Fetching subcategories from {main_url}")
        response = requests.get(main_url, headers=HEADERS, timeout=10)
        time.sleep(3)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        subcategories = []
        for div in soup.find_all('div', class_='categorie'):
            a_tag = div.find('a')
            name = a_tag.find('h4').text.strip()
            image_url = "https://www.piscine-market.com" + a_tag.find('img')['src']
            logging.info(f"Found subcategory: {name} with image URL: {image_url}")
            subcategories.append({
                'name': name,
                'image': download_image(image_url, 'subcategories_images', name, '.gif'),
                'thumbnail': None,
                'link': "https://www.piscine-market.com" + a_tag['href']
            })
        return subcategories
    except RequestException as e:
        logging.error(f"Failed to get subcategories from {main_url}: {e}")
        raise

def get_subcategory_details(subcategory):
    try:
        url = subcategory['link']
        logging.info(f"Fetching details for subcategory: {subcategory['name']} from {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        time.sleep(3)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        image_div = soup.find('div', class_='row image')
        if image_div:
            img_tag = image_div.find('img')
            if img_tag:
                thumbnail_url = img_tag['src']
                subcategory['thumbnail'] = download_image(thumbnail_url, 'subcategories_thumbnails', 'thumbnail_' + subcategory['name'])
                logging.info(f"Found thumbnail for subcategory: {subcategory['name']} with URL: {thumbnail_url}")
        else:
            logging.warning(f"No thumbnail found for subcategory: {subcategory['name']}")
            subcategory['thumbnail'] = ''
        
        products = []
        for div in soup.find_all('div', class_='col-sm-7 col-xs-12'):
            product_link = div.find('a')['href']
            products.append(product_link)
        logging.info(f"Found {len(products)} products for subcategory: {subcategory['name']}")
        return subcategory, products
    except RequestException as e:
        logging.error(f"Failed to get subcategory details from {url}: {e}")
        raise

def get_product_details(product_link, category_name):
    try:
        url = "https://www.piscine-market.com" + product_link
        logging.info(f"Fetching product details from {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        time.sleep(3)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        name = soup.find('h1', class_='titre-produit').text.strip()
        part_number = soup.find('tr', class_='first').find_all('td')[1].text.strip()
        price = soup.find('span', class_='prix').text.strip().split()[0]
        description = soup.find('div', class_='description')
        if description:
            des = description.find('p')
            if des:
                description = des.text.strip()
            else:
                description = description.find('div').text.strip()
        image_div = soup.find('div', class_='col-sm-5 photos')
        image_name = ''
        if image_div:
            image = image_div.find('img')
            if image:
                image_url = image['src']
                image_name = download_image(image_url, 'product_images', name)
        
        logging.info(f"Product details - Name: {name}, Part Number: {part_number}, Price: {price}, Description: {description}")
        
        return {
            'name': name,
            'part_number': part_number,
            'price': price,
            'description': description,
            'image': image_name if image_name else None,
            'category': category_name
        }
    except RequestException as e:
        logging.error(f"Failed to get product details from {url}: {e}")
        raise

def main():
    try:
        main_url = 'https://www.piscine-market.com/robots-piscine/159/cg'
        subcategories = get_subcategories(main_url)
        
        # Load existing subcategories if any
        if os.path.isfile('subcategories.csv'):
            existing_subcategories = pd.read_csv('subcategories.csv')
            processed_subcategories = existing_subcategories['name'].tolist()
        else:
            processed_subcategories = []

        for subcategory in subcategories:
            if subcategory['name'] in processed_subcategories:
                logging.info(f"Subcategory {subcategory['name']} already processed. Skipping...")
                continue
            
            subcategory, products = get_subcategory_details(subcategory)
            all_products = []
            
            # Load existing products if any
            if os.path.isfile('products.csv'):
                existing_products = pd.read_csv('products.csv')
                processed_products = existing_products[existing_products['category'] == subcategory['name']]['name'].tolist()
            else:
                processed_products = []

            for product_link in products:
                product_details = get_product_details(product_link, subcategory['name'])
                if product_details['name'] in processed_products:
                    logging.info(f"Product {product_details['name']} in subcategory {subcategory['name']} already processed. Skipping...")
                    continue
                all_products.append(product_details)
            
            # Save subcategory to CSV
            subcategories_df = pd.DataFrame([subcategory])
            if not os.path.isfile('subcategories.csv'):
                subcategories_df.to_csv('subcategories.csv', index=False)
            else:
                subcategories_df.to_csv('subcategories.csv', mode='a', header=False, index=False)
            logging.info(f"Saved subcategory {subcategory['name']} to subcategories.csv")

            # Save products to CSV
            products_df = pd.DataFrame(all_products)
            if not os.path.isfile('products.csv'):
                products_df.to_csv('products.csv', index=False)
            else:
                products_df.to_csv('products.csv', mode='a', header=False, index=False)
            logging.info(f"Saved {len(all_products)} products for subcategory {subcategory['name']} to products.csv")
    except RequestException:
        logging.error("Request failed. Stopping the scraper.")
        return

if __name__ == "__main__":
    main()

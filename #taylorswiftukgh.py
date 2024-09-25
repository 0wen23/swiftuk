#taylorswift uk shop
#allmerch / musicshop / erastour / sale scraper / home page
#detects new products, price changes, restocks, and size availability changes on an interval basis


import asyncio
import json
import logging
import re
import aiohttp
from datetime import datetime
from typing import Dict, Tuple, List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from webdriver_manager.chrome import ChromeDriverManager





# Config
DISCORD_BOT_TOKEN = 'DISCORD BOT TOKEN HERE'
CHANNEL_ID = DISCORD CHANNEL ID HERE
#pages, add urls here for new pages
BASE_URL = 'https://storeuk.taylorswift.com/collections/all-merch'
MUSIC_SHOP_URL = 'https://storeuk.taylorswift.com/collections/music-shop'
ERAS_TOUR_URL = 'https://storeuk.taylorswift.com/collections/taylor-swift-the-eras-tour-shop-1'
SALE_URL = 'https://storeuk.taylorswift.com/collections/sale'
HOME_PAGE_URL = 'https://storeuk.taylorswift.com/'
#driver
CHROMEDRIVER_PATH = 'C:\\Users\\??\\Desktop\\chromedriver-win64\\chromedriver.exe'
#files
PRODUCT_DATA_FILE = 'product_data.json'
LAST_CHECK_FILE = 'swift_last_check_timestamp.json'
#time interval for checking
CHECK_INTERVAL = 600  # Check every 10 min (in seconds this section)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')






# Set up Selenium WebDriver
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--window-size=1920x1080")
chrome_options.add_argument("--log-level=3")  # Suppresses console logs
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)





#load and save functions for product data and last check time 
def load_product_data(file_path=PRODUCT_DATA_FILE) -> Dict[str, dict]:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading product data: {e}")
        return {}



#save product data to file 
def save_product_data(data, file_path=PRODUCT_DATA_FILE):
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
    except IOError as e:
        logging.error(f"Error saving product data: {e}")



# load last check time from file 
def load_last_check_time(file_path=LAST_CHECK_FILE) -> str:
    try:
        with open(file_path, 'r') as file:
            return json.load(file).get('last_check', '')
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading last check time: {e}")
        return ''



# save last check time to file 
def save_last_check_time(last_check, file_path=LAST_CHECK_FILE):
    try:
        with open(file_path, 'w') as file:
            json.dump({"last_check": last_check}, file, indent=4)
    except IOError as e:
        logging.error(f"Error saving last check time: {e}")



# extract image url from product card 
def extract_image_url(card):
    img_container = card.find('div', class_='card__image--container')
    if img_container:
        img_element = img_container.find('img', class_='image__responsive')
        if img_element and 'src' in img_element.attrs:
            image_url = img_element['src']
            if not image_url.startswith('http'):
                image_url = f"https:{image_url}"
            return image_url
    return None



# generate product url from title 
def generate_product_url(title: str) -> str:
    url_title = title.lower()
    url_title = re.sub(r'[^a-z0-9\s-]', '', url_title)
    url_title = url_title.replace(' ', '-')
    url_title = re.sub(r'-+', '-', url_title)
    url_title = url_title.strip('-')
    return f"https://storeuk.taylorswift.com/collections/all-merch/products/{url_title}"




# scrape products from url with pagination
def scrape_products(url: str) -> Tuple[List[Dict[str, str]], str]:
    try:
        logging.info(f"Scraping {url}")  # Ensure you see this output
        driver.get(url)
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'card__container'))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        product_cards = soup.find_all('div', class_='card__container')
        
        product_info = []
        for index, card in enumerate(product_cards):
            try:
                title_element = card.find('p', class_='text_display_md')
                title = title_element.get_text(strip=True) if title_element else 'No title available'
                
                price_element = card.find('span', class_='price__current')
                price = price_element.get_text(strip=True) if price_element else 'No price available'
                
                if title != 'No title available':
                    product_url = generate_product_url(title)
                else:
                    continue
                
                image_url = extract_image_url(card)
                
                product_data = {
                    'title': title,
                    'price': price,
                    'image_url': image_url,
                    'product_url': product_url
                }
                product_info.append(product_data)
            except Exception as e:
                logging.error(f"Error extracting product {index + 1}: {e}")
        
        pagination_links = soup.find_all('a', class_='pagination__item')
        next_page_url = None
        
        for link in pagination_links:
            if 'aria-label' in link.attrs and link['aria-label'] == 'Next page':
                next_page_url = link.get('href')
                if next_page_url:
                    if not next_page_url.startswith('http'):
                        next_page_url = f"https://storeuk.taylorswift.com{next_page_url}"
                    break
        
        return product_info, next_page_url
    except Exception as e:
        logging.error(f"Error scraping products from {url}: {e}")
        return [], None





# scrape product details from product url 
async def scrape_product_details(product_url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(product_url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Check if "Add to Cart" button exists to determine if the product is in stock
                add_to_cart_button = soup.find('button', {'name': 'add'})
                in_stock = add_to_cart_button is not None

                sizes_in_stock = {}
                variant_ids = {}
                size_labels = soup.select('label.option--swatch')
                for label in size_labels:
                    size_name = label.get_text(strip=True)
                    is_available = 'line-through' not in label.get('class', [])
                    sizes_in_stock[size_name] = is_available

                    # Extract variant ID from 'for' attribute
                    variant_id = label.get('for').split('-')[-1]
                    variant_ids[size_name] = variant_id

                add_to_cart_links = {
                    size: f"https://storeuk.taylorswift.com/products/{product_url.split('/')[-1]}?variant={variant_id}"
                    for size, variant_id in variant_ids.items()
                }

                return {
                    'in_stock': in_stock,
                    'sizes': sizes_in_stock,
                    'add_to_cart_links': add_to_cart_links
                }
                
        except Exception as e:
            logging.error(f"Error scraping product details from {product_url}: {e}")
            return {'in_stock': False, 'sizes': {}, 'add_to_cart_links': {}}




#monitor products
async def monitor_products(bot):
    old_products = load_product_data()
    last_check = load_last_check_time()

    while True:
        try:
            logging.info("Starting product check...")
            all_products = {}
            notifications_to_send = {}
            
            urls_to_scrape = [BASE_URL, MUSIC_SHOP_URL, ERAS_TOUR_URL, SALE_URL, HOME_PAGE_URL]
            
            for url in urls_to_scrape:
                logging.info(f"Scraping URL: {url}")
                current_page_url = url
                page_counter = 1
                
                while current_page_url:
                    logging.info(f"Checking page {page_counter} of {url}...")
                    current_products, next_page_url = scrape_products(current_page_url)
                    
                    if current_products:
                        logging.info(f"Scraped {len(current_products)} products from {current_page_url}")
                        tasks = [scrape_product_details(product['product_url']) for product in current_products]
                        results = await asyncio.gather(*tasks)
                        
                        for product, details in zip(current_products, results):
                            logging.debug(f"Processing product: {product['title']}")
                            product['in_stock'] = details['in_stock']
                            product['sizes'] = details['sizes']
                            product['add_to_cart_links'] = details['add_to_cart_links']
                            
                            old_product = old_products.get(product['title'])
                            if old_product:
                                status_changes = []
                                if old_product.get('in_stock') != product['in_stock']:
                                    if product['in_stock']:
                                        status_changes.append('restock')
                                    else:
                                        status_changes.append('out_of_stock')
                                if old_product['price'] != product['price']:
                                    status_changes.append('price_change')
                                if old_product['sizes'] != product['sizes']:
                                    status_changes.append('size_change')

                                if status_changes:
                                    notifications_to_send[product['title']] = (product, status_changes)
                                    logging.info(f"Detected changes for {product['title']}: {', '.join(status_changes)}")
                            else:
                                notifications_to_send[product['title']] = (product, ['new'])
                                logging.info(f"New product detected: {product['title']}")
                        
                    if next_page_url:
                        current_page_url = next_page_url
                        page_counter += 1
                        await asyncio.sleep(15)
                    else:
                        logging.info(f"Finished checking all pages for {url}.")
                        break
            
            logging.info("Finished scraping all URLs.")
            
            channel = bot.get_channel(CHANNEL_ID)
            if not channel:
                logging.error(f"Channel with ID {CHANNEL_ID} not found.")
                return

            for title, (product, status_changes) in notifications_to_send.items():
                await send_to_discord(channel, product, status_changes)
                logging.info(f"Notification sent for {title} with changes: {', '.join(status_changes)}")

            save_product_data(all_products)
            old_products = all_products
            save_last_check_time(datetime.utcnow().isoformat())

            logging.info("Product check completed.")

        except Exception as e:
            logging.error(f"Error in monitoring products: {e}")

        await asyncio.sleep(CHECK_INTERVAL)





# send product details to discord 
async def send_to_discord(channel, product, status_changes):
    try:
        embed_color = 0x00ff00
        if 'out_of_stock' in status_changes:
            embed_color = 0xff0000

        status_message = []

        if 'new' in status_changes:
            status_message.append("New Product Added!")
        if 'price_change' in status_changes:
            status_message.append("Price Changed!")
        if 'restock' in status_changes:
            status_message.append("Product Restocked!")
        if 'size_change' in status_changes:
            status_message.append("Size Availability Changed!")
        if 'out_of_stock' in status_changes:
            status_message.append("Product Out of Stock!")

        embed = discord.Embed(
            title=product['title'],
            description=f'Price: {product["price"]}\n[View Product]({product["product_url"]})',
            color=embed_color
        )
        if product['image_url']:
            embed.set_image(url=product['image_url'])

        sizes_available = ", ".join([size for size, available in product.get('sizes', {}).items() if available])
        #sizes_unavailable = ", ".join([size for size, available in product.get('sizes', {}).items() if not available])
        embed.add_field(name="Sizes in Stock", value=sizes_available if sizes_available else "None", inline=False)

        embed.add_field(name="Status", value="\n".join(status_message) if status_message else "No Changes", inline=False)

        add_to_cart_links = "\n".join([f"{size}: [Add to Cart]({link})" for size, link in product.get('add_to_cart_links', {}).items()])
        embed.add_field(name="Add to Cart Links", value=add_to_cart_links if add_to_cart_links else "No Sizes Available", inline=False)

        await channel.send(embed=embed)
        logging.info(f"Message sent to Discord: {', '.join(status_message)} - {product['title']}")

    except discord.DiscordException as e:
        logging.error(f"Error sending message to Discord: {e}")





def main():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logging.info(f'Logged in as {bot.user}')
        await monitor_products(bot)

    bot.run(DISCORD_BOT_TOKEN)

if __name__ == '__main__':
    main()
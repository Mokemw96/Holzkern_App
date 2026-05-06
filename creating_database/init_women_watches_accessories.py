import argparse
import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from sqlmodel import Session, delete

from models import WomenProduct, engine

BASE_URL = 'https://www.world.holzkern.com/en_world/shop/watches/women.html'
HEADERS = {'User-Agent': 'Mozilla/5.0'}
CSV_FILE = Path('women_watches_accessories.csv')
MAX_ITEMS = 100


def clean_text(text: str) -> str:
    if not text:
        return ''
    return ' '.join(text.strip().split())


def parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace(',', '').strip()
    match = re.search(r'[0-9]+(?:\.[0-9]+)?', cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def parse_listing_item(item) -> dict:
    link = item.select_one('a.product.photo.product-item-photo')
    image = item.select_one('img.product-image-photo')
    name_spans = item.select('strong.product.name.product-item-name span')
    if name_spans:
        product_name = ' '.join(clean_text(span.get_text()) for span in name_spans if clean_text(span.get_text()))
    else:
        product_name = clean_text(item.select_one('strong.product.name.product-item-name').get_text()) if item.select_one('strong.product.name.product-item-name') else ''
    price_text = item.select_one('div.price-box span.price')
    return {
        'product_name': product_name,
        'price': parse_price(price_text.get_text() if price_text else ''),
        'product_url': link['href'] if link and link.has_attr('href') else '',
        'image_url': image.get('data-srcset') or image.get('src') if image else '',
    }


def parse_product_page(url: str) -> dict:
    soup = get_soup(url)
    material = None
    color = None
    description = None
    availability = 'Available'

    desc_block = soup.select_one('div.product.attribute.faq-container.description')
    if desc_block:
        description = clean_text(desc_block.get_text())
    else:
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.has_attr('content'):
            description = clean_text(meta_desc['content'])

    for row in soup.select('div.row-spec'):
        header = row.select_one('div.header-spec')
        detail = row.select_one('div.details-spec')
        if not header or not detail:
            continue
        label = clean_text(header.get_text()).lower()
        value = clean_text(detail.get_text())
        if label == 'material' and value:
            material = value
        elif label == 'color' and value:
            color = value
        elif label == 'case' and not material and 'made of' in value.lower():
            material = value.split('made of', 1)[1].strip(' .')
        elif label == 'dial' and not color and value:
            color = value

    if not color:
        alt_image = soup.select_one('img.product-image-photo')
        if alt_image and alt_image.has_attr('alt'):
            alt = clean_text(alt_image['alt'])
            if '(' in alt and ')' in alt:
                color = alt.split('(', 1)[1].split(')', 1)[0]

    return {
        'material': material or '',
        'color': color or '',
        'description': description or '',
        'availability': availability,
    }


def scrape_items() -> list[dict]:
    items = []
    page = 1
    while len(items) < MAX_ITEMS:
        page_url = f'{BASE_URL}?p={page}' if page > 1 else BASE_URL
        print('Scraping', page_url)
        soup = get_soup(page_url)
        product_blocks = soup.select('div.product-item-info.remove-border-product-grid')
        if not product_blocks:
            break
        for product_block in product_blocks:
            if len(items) >= MAX_ITEMS:
                break
            listing = parse_listing_item(product_block)
            if not listing['product_url']:
                continue
            details = parse_product_page(listing['product_url'])
            items.append({
                'product_name': listing['product_name'],
                'category': 'Women Watches',
                'subcategory': 'Watches',
                'material': details['material'],
                'color': details['color'],
                'price': listing['price'],
                'availability': details['availability'],
                'description': details['description'],
                'product_url': listing['product_url'],
                'image_url': listing['image_url'],
            })
            time.sleep(0.2)
        page += 1
        if page > 10:
            break
    return items


def write_csv(rows: list[dict]):
    with CSV_FILE.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'product_name', 'category', 'subcategory', 'material', 'color', 'price', 'availability', 'description', 'product_url', 'image_url'])
        for idx, row in enumerate(rows, start=1):
            writer.writerow([
                idx,
                row['product_name'],
                row['category'],
                row['subcategory'],
                row['material'],
                row['color'],
                row['price'],
                row['availability'],
                row['description'],
                row['product_url'],
                row['image_url'],
            ])


def load_csv_to_db(csv_path: str = str(CSV_FILE), clear_table: bool = False):
    with Session(engine) as session:
        if clear_table:
            session.exec(delete(WomenProduct))
            session.commit()

        products = []
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                price = None
                if row.get('price'):
                    try:
                        price = float(row['price'])
                    except ValueError:
                        price = None

                products.append(WomenProduct(
                    id=int(row['id']) if row.get('id') else None,
                    product_name=row.get('product_name', '').strip(),
                    category=row.get('category', 'Women Watches').strip(),
                    subcategory=row.get('subcategory', '').strip() or None,
                    material=row.get('material', '').strip() or None,
                    color=row.get('color', '').strip() or None,
                    price=price,
                    availability=row.get('availability', '').strip() or None,
                    description=row.get('description', '').strip() or None,
                    product_url=row.get('product_url', '').strip() or None,
                    image_url=row.get('image_url', '').strip() or None,
                ))

        session.add_all(products)
        session.commit()
    print(f'Loaded {len(products)} rows into the women_watches_accessories table.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape or load women watches data')
    parser.add_argument('--scrape', action='store_true', help='Scrape the women watches site and write the CSV')
    parser.add_argument('--load', action='store_true', help='Load the CSV file into the database')
    parser.add_argument('--clear', action='store_true', help='Clear existing table rows before loading')
    parser.add_argument('--csv', default=str(CSV_FILE), help='Path to the CSV file')
    args = parser.parse_args()

    if args.scrape:
        scraped = scrape_items()
        write_csv(scraped)
        print(f'Written {len(scraped)} rows to {args.csv}')

    if args.load:
        load_csv_to_db(csv_path=args.csv, clear_table=args.clear)

    if not args.scrape and not args.load:
        parser.print_help()

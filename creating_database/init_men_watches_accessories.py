import argparse
import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from sqlmodel import Session, delete

from models import MenProduct, engine

BASE_URLS = [
    ('Men Watches', 'Watches', 'https://www.world.holzkern.com/en_world/shop/watches/men.html', 3),
    ('Men Accessories', 'Bracelets', 'https://www.world.holzkern.com/en_world/shop/bracelets/men.html', 1),
    ('Men Accessories', 'Jewelry', 'https://www.world.holzkern.com/en_world/shop/jewelry/men.html', 1),
]
CSV_FILE = Path('men_watches_accessories.csv')
HEADERS = {'User-Agent': 'Mozilla/5.0'}
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
    return float(match.group(0))


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def parse_name(title) -> str:
    if not title:
        return ''
    parts = [clean_text(text) for text in title.stripped_strings]
    return ' '.join(parts)


def parse_listing(item) -> dict:
    link = item.select_one('a.product.photo.product-item-photo')
    title = item.select_one('strong.product.name.product-item-name')
    image = item.select_one('img.product-image-photo')
    price_text = item.select_one('div.price-box span.price')
    return {
        'product_name': parse_name(title),
        'price': parse_price(price_text.get_text() if price_text else ''),
        'product_url': link['href'] if link and link.has_attr('href') else '',
        'image_url': image.get('data-srcset') or image.get('src') if image else '',
    }


def parse_product_page(url: str) -> dict:
    soup = get_soup(url)
    description = ''
    material = ''
    color = ''
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
        img = soup.select_one('img.product-image-photo')
        if img and img.has_attr('alt'):
            alt = clean_text(img['alt'])
            if '(' in alt and ')' in alt:
                color = alt.split('(', 1)[1].split(')', 1)[0]

    return {
        'description': description,
        'material': material,
        'color': color,
        'availability': availability,
    }


def scrape_items() -> list[dict]:
    products = []
    for category, subcategory, base_url, max_pages in BASE_URLS:
        for page in range(1, max_pages + 1):
            url = f'{base_url}?p={page}' if page > 1 else base_url
            print('Scraping', url)
            soup = get_soup(url)
            product_blocks = soup.select('div.product-item-info.remove-border-product-grid')
            if not product_blocks:
                break
            for item in product_blocks:
                if len(products) >= MAX_ITEMS:
                    break
                listing = parse_listing(item)
                if not listing['product_url']:
                    continue
                details = parse_product_page(listing['product_url'])
                products.append({
                    'product_name': listing['product_name'],
                    'category': category,
                    'subcategory': subcategory,
                    'material': details['material'],
                    'color': details['color'],
                    'price': listing['price'],
                    'availability': details['availability'],
                    'description': details['description'],
                    'product_url': listing['product_url'],
                    'image_url': listing['image_url'],
                })
                time.sleep(0.2)
            if len(products) >= MAX_ITEMS:
                break
        if len(products) >= MAX_ITEMS:
            break
    return products


def write_csv(rows: list[dict], csv_path: str = str(CSV_FILE)):
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
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
            session.exec(delete(MenProduct))
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
                products.append(MenProduct(
                    id=int(row['id']) if row.get('id') else None,
                    product_name=row.get('product_name', '').strip(),
                    category=row.get('category', '').strip(),
                    subcategory=row.get('subcategory', '').strip() or None,
                    material=row.get('material', '').strip() or None,
                    color=row.get('color', '').strip() or None,
                    price=price,
                    availability=row.get('availability', '').strip() or None,
                    description=row.get('description', '').strip() or None,
                    product_url=row.get('product_url', '').strip() or None,
                    image_url=row.get('image_url', '').strip() or None,
                ))
        with Session(engine) as session:
            session.add_all(products)
            session.commit()
    print(f'Loaded {len(products)} rows into the men_watches_accessories table.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape or load men watches/accessories data')
    parser.add_argument('--scrape', action='store_true', help='Scrape the men product pages and write the CSV')
    parser.add_argument('--load', action='store_true', help='Load the CSV file into the database')
    parser.add_argument('--clear', action='store_true', help='Clear existing rows in the table before loading')
    parser.add_argument('--csv', default=str(CSV_FILE), help='CSV file path')
    args = parser.parse_args()

    if args.scrape:
        items = scrape_items()
        write_csv(items, csv_path=args.csv)
        print(f'Written {len(items)} rows to {args.csv}')

    if args.load:
        load_csv_to_db(csv_path=args.csv, clear_table=args.clear)

    if not args.scrape and not args.load:
        parser.print_help()

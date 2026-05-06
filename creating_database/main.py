from init_women_watches_accessories import load_csv_to_db as load_women_csv
from init_men_watches_accessories import load_csv_to_db as load_men_csv

if __name__ == '__main__':
    print('Loading women watches and accessories...')
    load_women_csv(clear_table=True)
    print('Loading men watches and accessories...')
    load_men_csv(clear_table=True)
    print('Done! Both datasets loaded into holzkern.db')

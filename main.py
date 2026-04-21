import pandas as pd
import json
from scraper import scrape
from database import init_db, insert_data
from utils import setup


def main():
    setup()

    keyword = "plumbers"
    location = "Houston, TX"

    data = scrape(keyword, location, pages=3)

    df = pd.DataFrame(data).drop_duplicates()

    df.to_csv("output/data.csv", index=False)

    with open("output/data.json", "w") as f:
        json.dump(data, f, indent=4)

    init_db()
    insert_data(data)

    print("Scraping completed successfully. Data saved to CSV, JSON, and SQL database.")


if __name__ == "__main__":
    main()
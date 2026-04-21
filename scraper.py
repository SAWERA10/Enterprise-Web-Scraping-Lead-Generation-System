import logging
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


OUTPUT_DIR = Path("output")
DEBUG_DIR = OUTPUT_DIR / "debug"
LOG_FILE = OUTPUT_DIR / "scraper.log"

SEARCH_URL = "https://www.yellowpages.com/search?search_terms={keyword}&geo_location_terms={location}"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

CARD_SELECTORS = (
    "div.result",
    "div.result-card",
    "li.result",
    "div.organic",
    "div.info",
)

NEXT_SELECTORS = (
    "a.next",
    "a[rel='next']",
    "a[aria-label='Next']",
    "button[aria-label='Next']",
    "a.pagination-next",
)

NAME_SELECTORS = (
    "a.business-name",
    "h2 a",
    "h3 a",
    "a[href*='/mip/']",
)

PHONE_SELECTORS = (
    ".phones",
    ".phone",
    ".contact .phone",
)

ADDRESS_SELECTORS = (
    ".street-address",
    ".adr",
    "address",
    ".address",
)

WEBSITE_SELECTORS = (
    "a.track-visit-website",
    "a[href^='http']",
)

RATING_SELECTORS = (
    ".rating",
    ".stars",
    "[itemprop='ratingValue']",
)

REVIEW_SELECTORS = (
    ".count",
    ".reviews",
    "[itemprop='reviewCount']",
)

BLOCK_MARKERS = (
    "attention required",
    "just a moment",
    "cloudflare",
    "access denied",
    "verify you are human",
    "blocked",
)


def ensure_dirs():
    OUTPUT_DIR.mkdir(exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger():
    logger = logging.getLogger("scraper")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger


def normalize(text):
    return " ".join((text or "").split()).strip().lower()


def human_pause(min_seconds=0.8, max_seconds=1.8):
    time.sleep(random.uniform(min_seconds, max_seconds))


def build_search_url(keyword, location):
    return SEARCH_URL.format(
        keyword=quote_plus(keyword),
        location=quote_plus(location),
    )


def get_driver(headless=False):
    options = uc.ChromeOptions()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1400,1000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=en-US,en")
    options.add_argument(f"--user-agent={USER_AGENT}")

    driver = uc.Chrome(options=options, use_subprocess=True)
    driver.set_page_load_timeout(45)

    try:
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": USER_AGENT})
    except Exception:
        pass

    return driver


def save_debug_artifacts(driver, label):
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    screenshot_path = DEBUG_DIR / f"{label}_{stamp}.png"
    html_path = DEBUG_DIR / f"{label}_{stamp}.html"

    try:
        driver.save_screenshot(str(screenshot_path))
    except Exception:
        pass

    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
    except Exception:
        pass


def is_blocked(driver):
    try:
        title = normalize(driver.title)
    except Exception:
        title = ""

    try:
        body = normalize(driver.find_element(By.TAG_NAME, "body").text)
    except Exception:
        body = ""

    combined = f"{title} {body}"
    return any(marker in combined for marker in BLOCK_MARKERS)


def wait_for_page_ready(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def slow_scroll(driver):
    try:
        total_height = driver.execute_script(
            "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
        )
        step = max(500, total_height // 6)

        for position in range(0, int(total_height), step):
            driver.execute_script(f"window.scrollTo(0, {position});")
            time.sleep(random.uniform(0.15, 0.35))

        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass


def find_cards(driver):
    for selector in CARD_SELECTORS:
        cards = driver.find_elements(By.CSS_SELECTOR, selector)
        if cards:
            return cards
    return []


def wait_for_cards(driver, retries=3, timeout=12):
    for attempt in range(retries):
        try:
            wait_for_page_ready(driver, timeout=timeout)
            human_pause(0.4, 0.9)
            slow_scroll(driver)

            if is_blocked(driver):
                return []

            cards = find_cards(driver)
            if cards:
                return cards

        except TimeoutException:
            pass
        except WebDriverException:
            pass

        time.sleep(1.5 + attempt)

    return []


def text_from_selectors(parent, selectors):
    for selector in selectors:
        try:
            text = parent.find_element(By.CSS_SELECTOR, selector).text.strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def attr_from_selectors(parent, selectors, attr="href"):
    for selector in selectors:
        try:
            value = parent.find_element(By.CSS_SELECTOR, selector).get_attribute(attr)
            if value:
                return value.strip()
        except Exception:
            continue
    return ""


def extract_card(card):
    name = text_from_selectors(card, NAME_SELECTORS)
    if not name:
        return None

    return {
        "name": name,
        "phone": text_from_selectors(card, PHONE_SELECTORS),
        "address": text_from_selectors(card, ADDRESS_SELECTORS),
        "website": attr_from_selectors(card, WEBSITE_SELECTORS),
        "rating": text_from_selectors(card, RATING_SELECTORS),
        "review_count": text_from_selectors(card, REVIEW_SELECTORS),
        "source_url": attr_from_selectors(card, NAME_SELECTORS),
    }


def enrich_detail_page(driver, item):
    source_url = item.get("source_url")
    if not source_url:
        return item

    original_handle = driver.current_window_handle

    try:
        driver.execute_script("window.open(arguments[0], '_blank');", source_url)
        driver.switch_to.window(driver.window_handles[-1])

        wait_for_page_ready(driver, timeout=20)
        human_pause(0.7, 1.4)

        if is_blocked(driver):
            save_debug_artifacts(driver, "blocked_detail")
            return item

        item["phone"] = item["phone"] or text_from_selectors(driver, PHONE_SELECTORS)
        item["address"] = item["address"] or text_from_selectors(driver, ADDRESS_SELECTORS)
        item["website"] = item["website"] or attr_from_selectors(driver, WEBSITE_SELECTORS)
        item["rating"] = item["rating"] or text_from_selectors(driver, RATING_SELECTORS)
        item["review_count"] = item["review_count"] or text_from_selectors(driver, REVIEW_SELECTORS)

        return item

    except Exception:
        return item

    finally:
        try:
            driver.close()
        except Exception:
            pass

        try:
            driver.switch_to.window(original_handle)
        except Exception:
            pass


def go_next_page(driver):
    previous_url = driver.current_url
    cards_before = find_cards(driver)
    first_card = cards_before[0] if cards_before else None

    for selector in NEXT_SELECTORS:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            for button in buttons:
                if button.is_displayed() and button.is_enabled():
                    driver.execute_script("arguments[0].click();", button)

                    try:
                        if first_card is not None:
                            WebDriverWait(driver, 12).until(EC.staleness_of(first_card))
                        else:
                            WebDriverWait(driver, 12).until(lambda d: d.current_url != previous_url)
                    except TimeoutException:
                        pass

                    human_pause(1.0, 2.0)
                    return True
        except Exception:
            continue

    return False


def scrape(keyword, location, pages=3, headless=False, scrape_details=False, max_detail_pages=50):
    ensure_dirs()
    logger = setup_logger()
    driver = get_driver(headless=headless)

    url = build_search_url(keyword, location)
    all_data = []
    seen = set()
    detail_count = 0

    try:
        driver.get(url)
        wait_for_page_ready(driver)

        if is_blocked(driver):
            save_debug_artifacts(driver, "blocked_search")
            logger.warning("Blocked page detected on initial load.")
            print("No listings found or blocked")
            return []

        for page in range(1, pages + 1):
            print(f"Scraping page {page}")

            cards = wait_for_cards(driver)

            if not cards:
                logger.warning("No listings found on page %s", page)
                save_debug_artifacts(driver, f"no_cards_page_{page}")
                print("No listings found or blocked")
                break

            print(f"Found {len(cards)} listings")

            for card in cards:
                try:
                    item = extract_card(card)
                    if not item or not item["name"]:
                        continue

                    dedupe_key = (
                        normalize(item["name"]),
                        normalize(item["phone"]),
                        normalize(item["address"]),
                    )
                    if dedupe_key in seen:
                        continue

                    seen.add(dedupe_key)

                    if scrape_details and detail_count < max_detail_pages and item.get("source_url"):
                        item = enrich_detail_page(driver, item)
                        detail_count += 1

                    all_data.append(item)

                except Exception as exc:
                    logger.warning("Failed to parse card: %s", exc)
                    continue

            if page == pages:
                break

            if not go_next_page(driver):
                break

        print(f"Total collected: {len(all_data)} records")
        logger.info("Scraping completed with %s records", len(all_data))
        return all_data

    except Exception as exc:
        logger.exception("Scraper failed: %s", exc)
        save_debug_artifacts(driver, "scraper_failed")
        return all_data

    finally:
        try:
            driver.quit()
        except Exception:
            pass

 
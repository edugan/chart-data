from bs4 import BeautifulSoup
from datetime import datetime
import requests
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def extract_chart_date(soup):
    """
    Finds the 'Week of <Month> <Day>, <Year>' label on the page and returns
    it as a date object. Used to detect when Billboard has redirected us to
    the nearest available chart instead of the one we actually requested
    (which happens when you request a date before a chart existed).
    """
    span = soup.find("span", string=re.compile(r"Week of", re.I))
    if not span:
        return None
    text = span.get_text(strip=True)
    m = re.search(r"Week of (.+)", text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").date()
    except ValueError:
        return None

def parse_chart_row(row_soup):
    """Parses a single chart row into a dict of attributes."""
    data = {}

    pos_tag = row_soup.find("span", class_="c-label")
    data["current_position"] = int(pos_tag.get_text(strip=True)) if pos_tag and pos_tag.get_text(strip=True).isdigit() else None

    title_tag = row_soup.find("h3", id="title-of-a-story")
    data["title"] = title_tag.get_text(strip=True) if title_tag else None

    artist_container = row_soup.find("span", class_="a-no-trucate")
    if artist_container:
        raw_artist_text = artist_container.get_text(separator=" ", strip=True)
        data["artist_name"] = re.sub(r'\s+', ' ', raw_artist_text)
    else:
        data["artist_name"] = None

    weeks_span = row_soup.find("span", string=re.compile(r"\bWEEKS\b", re.I))
    if weeks_span:
        parent_flex = weeks_span.find_parent("div", class_="lrv-u-flex")
        val_item = parent_flex.find("span", class_="c-label") if parent_flex else None
        val_text = val_item.get_text(strip=True) if val_item else "-"
        data["weeks_on_chart"] = int(val_text) if val_text.isdigit() else 0
    else:
        data["weeks_on_chart"] = 0

    lw_span = row_soup.find("span", string=re.compile(r"\bLW\b", re.I))
    if lw_span:
        parent_flex = lw_span.find_parent("div", class_="lrv-u-flex")
        val_item = parent_flex.find("span", class_="c-label") if parent_flex else None
        val_text = val_item.get_text(strip=True) if val_item else "-"
        if val_text.isdigit():
            data["last_week_position"] = int(val_text)
        else:
            data["last_week_position"] = "NEW" if data["weeks_on_chart"] <= 1 else "RE"
    else:
        data["last_week_position"] = "NEW" if data["weeks_on_chart"] <= 1 else "RE"

    debut_section = row_soup.find("div", class_="o-chart-position-stats__debut")
    if debut_section:
        num_tag = debut_section.find("span", class_="c-label")
        data["debut_position"] = int(num_tag.get_text(strip=True)) if num_tag and num_tag.get_text(strip=True).isdigit() else None
        date_link = debut_section.find("a", class_="c-label__link")
        data["debut_date"] = date_link.get_text(strip=True) if date_link else None
    else:
        data["debut_position"] = None
        data["debut_date"] = None

    awards = []
    awards_section = row_soup.find("div", class_="o-chart-awards")
    if awards_section:
        for item in awards_section.find_all("div", class_="o-chart-awards-list-item"):
            tagline = item.find("p", class_="c-tagline")
            if tagline:
                awards.append(tagline.get_text(strip=True))
    data["awards_vector"] = "|".join(awards)  # stored as string for CSV-friendliness

    return data


def scrape_billboard_chart(chart_name, date_str, max_retries=3, timeout=20):
    """
    Scrapes a Billboard chart for a given date, retrying on transient errors.
    Returns (rows, actual_date) where actual_date is the real chart date
    found on the page — this lets the caller detect when Billboard has
    redirected to a different chart than the one requested.
    """
    url = f"https://www.billboard.com/charts/{chart_name}/{date_str}/"

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Fetching '{chart_name}' for week: {date_str}... (attempt {attempt})")
            response = requests.get(url, headers=HEADERS, timeout=timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                actual_date = extract_chart_date(soup)

                if actual_date and actual_date.isoformat() != date_str:
                    print(f"-> {date_str} redirected to {actual_date.isoformat()} "
                          f"(chart likely didn't exist yet). Skipping.")
                    return [], actual_date
                
                rows = soup.find_all("div", class_="o-chart-results-list-row-container")
                week_data = []
                for row in rows:
                    parsed_row = parse_chart_row(row)
                    parsed_row["chart_date"] = date_str
                    week_data.append(parsed_row)

                # print(f"-> Got {len(week_data)} rows for {date_str}.")
                return week_data, actual_date

            elif response.status_code == 429:
                # Rate limited — wait longer before retrying
                wait = 5 * attempt
                print(f"-> Rate limited (429) for {date_str}. Waiting {wait}s before retry...")
                time.sleep(wait)

            else:
                print(f"-> Failed to fetch {date_str}. Status code: {response.status_code}")
                return [], None  # don't retry on things like 404 — it won't resolve itself

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait = 3 * attempt
            print(f"-> Network error for {date_str} (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                print(f"   Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"-> Giving up on {date_str} after {max_retries} attempts.")
                return [], None

        except Exception as e:
            print(f"-> Unexpected error processing {date_str}: {e}")
            return [], None

    return [], None
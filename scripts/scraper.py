from bs4 import BeautifulSoup
import requests
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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


def scrape_billboard_chart(chart_name, date_str):
    """
    Scrapes a Billboard chart (e.g. 'hot-100', 'billboard-200') for a given
    date ('YYYY-MM-DD') and returns a list of row dicts.
    """
    url = f"https://www.billboard.com/charts/{chart_name}/{date_str}/"

    try:
        print(f"Fetching '{chart_name}' for week: {date_str}...")
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code != 200:
            print(f"-> Failed to fetch {date_str}. Status code: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all("div", class_="o-chart-results-list-row-container")

        week_data = []
        for row in rows:
            parsed_row = parse_chart_row(row)
            parsed_row["chart_date"] = date_str
            week_data.append(parsed_row)

        print(f"-> Got {len(week_data)} rows for {date_str}.")
        return week_data

    except Exception as e:
        print(f"-> Error processing {date_str}: {e}")
        return []
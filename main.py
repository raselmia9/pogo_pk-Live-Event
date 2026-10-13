import json
import cloudscraper
from bs4 import BeautifulSoup

URL = 'https://pogo.pk/'

def scrape_pogo_matches():
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    print(f"Fetching URL: {URL}")
    response = scraper.get(URL)
    
    if response.status_code != 200:
        print(f"Failed to fetch page. Status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    matches_data = []
    status_lines = []

    match_cards = soup.select('div.match-card, div[class*="match"], a[href*="match"]')
    if not match_cards:
        match_cards = soup.select('div.grid > div, div.flex > div')

    # ডট গুলোর জন্য কালার লুপ বা সিলেকশন (লাল, নীল, হলুদ)
    dots = ['🔴', '🔵', '🟡']
    dot_index = 0

    for card in match_cards:
        try:
            team_elements = card.select('.team-name, span, p')
            teams = [t.get_text(strip=True) for t in team_elements if t.get_text(strip=True)]
            
            team_one_title = teams[0] if len(teams) > 0 else "N/A"
            team_two_title = teams[1] if len(teams) > 1 else "N/A"

            logos = card.select('img')
            team_one_logo = logos[0].get('src') or logos[0].get('data-src') if len(logos) > 0 else "N/A"
            team_two_logo = logos[1].get('src') or logos[1].get('data-src') if len(logos) > 1 else "N/A"

            link_tag = card if card.name == 'a' else card.find_parent('a') or card.select_one('a')
            match_link = "N/A"
            if link_tag and link_tag.has_attr('href'):
                href = link_tag['href']
                match_link = f"https://pogo.pk{href}" if href.startswith('/') else href

            if team_one_title != "N/A" or team_two_title != "N/A":
                match_info = {
                    "team_one_title": team_one_title,
                    "team_two_title": team_two_title,
                    "team_one_logo": team_one_logo,
                    "team_two_logo": team_two_logo,
                    "match_link": match_link
                }
                
                if match_info not in matches_data:
                    matches_data.append(match_info)
                    
                    # স্ট্যাটাস টেক্সটের জন্য রঙিন ডট সহ ফরম্যাট (কোনো ডেট/টাইম ছাড়া)
                    current_dot = dots[dot_index % len(dots)]
                    status_line = f"{current_dot} Match: {team_one_title} vs {team_two_title}"
                    status_lines.append(status_line)
                    dot_index += 1

        except Exception as e:
            print(f"Error parsing an item: {e}")

    # ১. JSON ফাইলে ডাটা সেভ করা
    with open('matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)

    # ২. Status টেক্সট ফাইলে স্ট্যাটাস সেভ করা (তারিখ ও সময় ছাড়া)
    with open('status.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(status_lines))
    
    print(f"Successfully scraped {len(matches_data)} matches.")

if __name__ == "__main__":
    scrape_pogo_matches()

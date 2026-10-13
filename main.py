import json
import cloudscraper
from bs4 import BeautifulSoup

URL = 'https://pogo.pk/'

def scrape_pogo_matches():
    # Cloudscraper ইনিশিয়ালাইজ করা (ক্লাউডফ্লেয়ার প্রটেকশন বাইপাস করার জন্য)
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

    # ওয়েবসাইটের ম্যাচ কার্ডের স্ট্রাকচার অনুযায়ী সিলেক্টর (প্রয়োজনীয় সাপেক্ষে সিলেক্টর অ্যাডজাস্ট করা যাবে)
    match_cards = soup.select('div.match-card, div[class*="match"], a[href*="match"]')

    if not match_cards:
        # যদি নির্দিষ্ট ক্লাস না পাওয়া যায়, তবে সেকশন বা জেনেরিক কার্ড ট্র্যাক করার চেষ্টা
        match_cards = soup.select('div.grid > div, div.flex > div')

    for card in match_cards:
        try:
            # টিম টাইটেলসমূহ সংগ্রহ
            team_elements = card.select('.team-name, span, p')
            teams = [t.get_text(strip=True) for t in team_elements if t.get_text(strip=True)]
            
            team_one_title = teams[0] if len(teams) > 0 else "N/A"
            team_two_title = teams[1] if len(teams) > 1 else "N/A"

            # টিম লোগোগুলো সংগ্রহ (img ট্যাগ থেকে)
            logos = card.select('img')
            team_one_logo = logos[0].get('src') or logos[0].get('data-src') if len(logos) > 0 else "N/A"
            team_two_logo = logos[1].get('src') or logos[1].get('data-src') if len(logos) > 1 else "N/A"

            # পরবর্তী পেজের বা ডিটেইলস পেজের লিংক সংগ্রহ
            link_tag = card if card.name == 'a' else card.find_parent('a') or card.select_one('a')
            match_link = "N/A"
            if link_tag and link_tag.has_attr('href'):
                href = link_tag['href']
                match_link = f"https://pogo.pk{href}" if href.startswith('/') else href

            # অপ্রয়োজনীয় বা খালি এন্ট্রি এড়িয়ে চলা
            if team_one_title != "N/A" or team_two_title != "N/A":
                match_info = {
                    "team_one_title": team_one_title,
                    "team_two_title": team_two_title,
                    "team_one_logo": team_one_logo,
                    "team_two_logo": team_two_logo,
                    "match_link": match_link
                }
                # ডুপ্লিকেট এন্ট্রি এড়াতে চেক করা
                if match_info not in matches_data:
                    matches_data.append(match_info)

        except Exception as e:
            print(f"Error parsing an item: {e}")

    # ডাটা JSON ফাইলে সেভ করা
    with open('matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)
    
    print(f"Successfully scraped {len(matches_data)} matches and saved to matches.json.")
    return matches_data

if __name__ == "__main__":
    scrape_pogo_matches()

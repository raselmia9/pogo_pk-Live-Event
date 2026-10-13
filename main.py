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
    
    print(f"Fetching Main URL: {URL}")
    response = scraper.get(URL)
    
    if response.status_code != 200:
        print(f"Failed to fetch page. Status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    matches_data = []
    status_lines = []

    match_cards = []
    potential_cards = soup.find_all(['a', 'div'], class_=lambda x: x and ('match' in x.lower() or 'grid' in x.lower() or 'flex' in x.lower()))
    
    for card in potential_cards:
        imgs = card.find_all('img')
        if len(imgs) >= 2:
            if card not in match_cards:
                match_cards.append(card)

    if not match_cards:
        match_cards = soup.select('a[href*="/stream"], a[href*="match"], div.match-card')

    dots = ['🔴', '🔵', '🟡']
    dot_index = 0

    for card in match_cards:
        try:
            team_elements = card.find_all(['span', 'p', 'div'], class_=lambda x: x and ('team' in x.lower() or 'name' in x.lower()))
            if not team_elements:
                team_elements = card.find_all(['span', 'p'])

            teams = [t.get_text(strip=True) for t in team_elements if t.get_text(strip=True)]
            
            if len(teams) < 2:
                all_texts = [el.get_text(strip=True) for el in card.find_all(text=True) if el.get_text(strip=True)]
                filtered_texts = [t for t in all_texts if not any(w in t.lower() for w in ['live', 'starts', 'am', 'pm', 'epl', 'efl', 'fa cup'])]
                teams = filtered_texts

            team_one_title = teams[0] if len(teams) > 0 else "N/A"
            team_two_title = teams[1] if len(teams) > 1 else ("N/A" if len(teams) > 0 else "N/A")

            logos = card.find_all('img')
            team_one_logo = logos[0].get('src') or logos[0].get('data-src') if len(logos) > 0 else "N/A"
            team_two_logo = logos[1].get('src') or logos[1].get('data-src') if len(logos) > 1 else "N/A"

            link_tag = card if card.name == 'a' else card.find_parent('a') or card.find('a')
            match_link = "N/A"
            if link_tag and link_tag.has_attr('href'):
                href = link_tag['href']
                match_link = f"https://pogo.pk{href}" if href.startswith('/') else href

            # ১. প্রথম কার্ড বা হোমপেজের লিংকযুক্ত এন্ট্রিগুলো ফিল্টার করে বাদ দেওয়া
            if match_link == "https://pogo.pk/" or match_link == "https://pogo.pk" or match_link == "N/A":
                continue

            if team_one_title != "N/A" and team_two_title != "N/A" and team_one_logo != "N/A":
                
                # ২. এখন সংগ্রহ করা ম্যাচ লিংকের মাধ্যমে সরাসরি দ্বিতীয় পেজে (Detail Page) প্রবেশ করা
                print(f"Visiting second page for match: {team_one_title} vs {team_two_title} -> {match_link}")
                sub_response = scraper.get(match_link)
                
                sub_title = "N/A"
                if sub_response.status_code == 200:
                    sub_soup = BeautifulSoup(sub_response.text, 'html.parser')
                    # দ্বিতীয় পেজ থেকে এক্সট্রা ইনফো বা টাইটেল সংগ্রহ করার লজিক (প্রয়োজন অনুযায়ী কাস্টমাইজ করা যাবে)
                    page_title_tag = sub_soup.find('h1') or sub_soup.find('title')
                    if page_title_tag:
                        sub_title = page_title_tag.get_text(strip=True)

                match_info = {
                    "team_one_title": team_one_title,
                    "team_two_title": team_two_title,
                    "team_one_logo": team_one_logo,
                    "team_two_logo": team_two_logo,
                    "match_link": match_link,
                    "second_page_title": sub_title # দ্বিতীয় পেজ থেকে প্রাপ্ত তথ্য
                }
                
                if match_info not in matches_data:
                    matches_data.append(match_info)
                    
                    current_dot = dots[dot_index % len(dots)]
                    status_line = f"{current_dot} Match: {team_one_title} vs {team_two_title}"
                    status_lines.append(status_line)
                    dot_index += 1

        except Exception as e:
            print(f"Error parsing match card: {e}")

    # JSON ফাইলে ডাটা সেভ করা
    with open('matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)

    # Status টেক্সট ফাইলে স্ট্যাটাস সেভ করা
    with open('status.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(status_lines))
    
    print(f"Successfully scraped and processed {len(matches_data)} matches.")

if __name__ == "__main__":
    scrape_pogo_matches()

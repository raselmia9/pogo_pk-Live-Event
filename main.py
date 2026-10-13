import json
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

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

            # হোমপেজ বা লিগ ক্যাটাগরি পেজ (যেমন /leagues/, /nfl-streams ইত্যাদি) ফিল্টার করে বাদ দেওয়া
            if match_link == "https://pogo.pk/" or match_link == "https://pogo.pk" or match_link == "N/A" or "leagues" in match_link:
                continue

            if team_one_title != "N/A" and team_two_title != "N/A" and team_one_logo != "N/A":
                
                # দ্বিতীয় পেজে প্রবেশ করে ম্যাচের শুরুর সময় সংগ্রহ করা
                print(f"Visiting detail page: {match_link}")
                sub_response = scraper.get(match_link)
                
                match_time_bst = "Time TBA"
                if sub_response.status_code == 200:
                    sub_soup = BeautifulSoup(sub_response.text, 'html.parser')
                    
                    # দ্বিতীয় পেজ থেকে টাইম বা ডেট ট্যাগ খুঁজে বের করা (ওয়েবসাইটের স্ট্রাকচার অনুযায়ী ক্লাস বা ট্যাগ অ্যাডজাস্ট করা যেতে পারে)
                    time_tag = sub_soup.find('time') or sub_soup.find(class_=lambda x: x and ('time' in x.lower() or 'date' in x.lower() or 'schedule' in x.lower()))
                    
                    if time_tag:
                        raw_time_str = time_tag.get('datetime') or time_tag.get_text(strip=True)
                        try:
                            # যদি ISO ফরম্যাট বা টাইম স্ট্রিং থাকে তবে সেটিকে বাংলাদেশ টাইমে (UTC+6) কনভার্ট করা
                            # এখানে উদাহরণের জন্য UTC টাইম ধরে BST (+6) করা হলো
                            dt_utc = datetime.fromisoformat(raw_time_str.replace('Z', '+00:00'))
                            bst_timezone = timezone(timedelta(hours=6))
                            dt_bst = dt_utc.astimezone(bst_timezone)
                            match_time_bst = dt_bst.strftime('%I:%M %p, %d %b')
                        except:
                            match_time_bst = raw_time_str # কনভার্ট করা সম্ভব না হলে অরিজিনাল টেক্সট রাখবে

                match_info = {
                    "team_one_title": team_one_title,
                    "team_two_title": team_two_title,
                    "team_one_logo": team_one_logo,
                    "team_two_logo": team_two_logo,
                    "match_link": match_link,
                    "match_time": match_time_bst
                }
                
                if match_info not in matches_data:
                    matches_data.append(match_info)
                    
                    # স্ট্যাটাস টেক্সটের জন্য রঙিন ডট, টিম নাম এবং বাংলাদেশ সময় ফরম্যাট
                    current_dot = dots[dot_index % len(dots)]
                    status_line = f"{current_dot} {team_one_title} vs {team_two_title} | Time: {match_time_bst}"
                    status_lines.append(status_line)
                    dot_index += 1

        except Exception as e:
            print(f"Error parsing match card: {e}")

    # JSON ফাইলে ডাটা সেভ করা
    with open('matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)

    # Status টেক্সট ফাইলে স্ট্যাটাস সেভ করা (কোনো ডেট/টাইম স্ট্যাম্প হেডার ছাড়াই)
    with open('status.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(status_lines))
    
    print(f"Successfully scraped {len(matches_data)} matches.")

if __name__ == "__main__":
    scrape_pogo_matches()

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

URL = 'https://pogo.pk/'

def fetch_match_details(card_info):
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    team_one_title = card_info['team_one_title']
    team_two_title = card_info['team_two_title']
    team_one_logo = card_info['team_one_logo']
    team_two_logo = card_info['team_two_logo']
    match_link = card_info['match_link']

    match_time_bst = "Time TBA"
    stream_links = []

    try:
        print(f"Visiting detail page: {match_link}")
        sub_response = scraper.get(match_link, timeout=10)
        
        if sub_response.status_code == 200:
            sub_soup = BeautifulSoup(sub_response.text, 'html.parser')
            
            # ১. স্ক্রিনশট অনুযায়ী ডেট এবং টাইম সংগ্রহ (যেমন: Oct 13, 2026 at 07:00 PM UTC)
            # সাধারণত এটি ক্যালেন্ডার আইকন বা নির্দিষ্ট টেক্সটের পাশে থাকে
            time_elem = sub_soup.find(string=lambda t: t and ('UTC' in t or 'PM' in t or 'AM' in t) and (',' in t or 'at' in t))
            
            if time_elem:
                raw_time_str = time_elem.strip()
                try:
                    # যেমন: "Oct 13, 2026 at 07:00 PM UTC" ফরম্যাট পার্স করা
                    clean_str = raw_time_str.replace(' at ', ' ')
                    dt_utc = datetime.strptime(clean_str, '%b %d, %Y %I:%M %p UTC')
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                    
                    # বাংলাদেশ টাইমে কনভার্ট করা (UTC+6)
                    bst_timezone = timezone(timedelta(hours=6))
                    dt_bst = dt_utc.astimezone(bst_timezone)
                    match_time_bst = dt_bst.strftime('%I:%M %p, %d %b %Y')
                except Exception as e:
                    match_time_bst = raw_time_str # ফেইল করলে অরিজিনাল টেক্সট রাখবে

            # ২. টেবিল থেকে Watch বাটন বা ৩য় পেজের লিংকগুলো সংগ্রহ করা
            # স্ক্রিনশট অনুযায়ী 'Watch' লেখা বাটন বা সংশ্লিষ্ট টার্গেট লিংকগুলো খুঁজে বের করা
            rows = sub_soup.find_all('tr') or sub_soup.find_all('div', class_=lambda x: x and 'row' in x.lower())
            for row in rows:
                link_tag = row.find('a', string=lambda t: t and 'watch' in t.lower()) or row.find('a', href=True)
                channel_name_elem = row.find(['td', 'span', 'div'], string=lambda t: t and 'link' in t.lower())
                
                channel_name = channel_name_elem.get_text(strip=True) if channel_name_elem else "Channel"
                
                if link_tag and link_tag.has_attr('href'):
                    href = link_tag['href']
                    watch_link = f"https://pogo.pk{href}" if href.startswith('/') else href
                    stream_links.append({
                        "channel": channel_name,
                        "watch_link": watch_link
                    })
            
            # যদি সরাসরি টেবিল রো না মিলে, তবে পেজের সব 'Watch' লিংক ট্র্যাক করা
            if not stream_links:
                all_links = sub_soup.find_all('a', href=True)
                for a in all_links:
                    if 'watch' in a.get_text(strip=True).lower() or 'stream' in a.get_href() if hasattr(a, 'get_href') else '':
                        stream_links.append({
                            "channel": "Watch Link",
                            "watch_link": a['href'] if a['href'].startswith('http') else f"https://pogo.pk{a['href']}"
                        })

    except Exception as e:
        print(f"Error fetching sub-page {match_link}: {e}")

    return {
        "team_one_title": team_one_title,
        "team_two_title": team_two_title,
        "team_one_logo": team_one_logo,
        "team_two_logo": team_two_logo,
        "match_link": match_link,
        "match_time": match_time_bst,
        "stream_links": stream_links
    }

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
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    match_cards_info = []

    match_cards = []
    potential_cards = soup.find_all(['a', 'div'], class_=lambda x: x and ('match' in x.lower() or 'grid' in x.lower() or 'flex' in x.lower()))
    
    for card in potential_cards:
        imgs = card.find_all('img')
        if len(imgs) >= 2:
            if card not in match_cards:
                match_cards.append(card)

    if not match_cards:
        match_cards = soup.select('a[href*="/stream"], a[href*="match"], div.match-card')

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

            if match_link == "https://pogo.pk/" or match_link == "https://pogo.pk" or match_link == "N/A" or "leagues" in match_link:
                continue

            if team_one_title != "N/A" and team_two_title != "N/A" and team_one_logo != "N/A":
                match_cards_info.append({
                    "team_one_title": team_one_title,
                    "team_two_title": team_two_title,
                    "team_one_logo": team_one_logo,
                    "team_two_logo": team_two_logo,
                    "match_link": match_link
                })
        except Exception as e:
            print(f"Error parsing card: {e}")

    # মাল্টিথ্রেডিং (ThreadPoolExecutor) ব্যবহার করে দ্রুত দ্বিতীয় পেজগুলো প্রসেস করা
    matches_data = []
    status_lines = []
    dots = ['🔴', '🔵', '🟡']
    dot_index = 0

    print(f"Processing {len(match_cards_info)} matches using multi-threading...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_match = {executor.submit(fetch_match_details, info): info for info in match_cards_info}
        
        for future in as_completed(future_to_match):
            result = future.result()
            if result:
                matches_data.append(result)
                current_dot = dots[dot_index % len(dots)]
                status_line = f"{current_dot} {result['team_one_title']} vs {result['team_two_title']} | Time: {result['match_time']}"
                status_lines.append(status_line)
                dot_index += 1

    # JSON ফাইলে ডাটা সেভ করা
    with open('matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)

    # Status টেক্সট ফাইলে স্ট্যাটাস সেভ করা (তারিখ ও সময় ছাড়া সুন্দর আউটপুট)
    with open('status.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(status_lines))
    
    print(f"Successfully scraped and processed {len(matches_data)} matches with multi-threading.")

if __name__ == "__main__":
    scrape_pogo_matches()

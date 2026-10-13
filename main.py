import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

URL = 'https://pogo.pk/'

def fetch_stream_data(stream_info):
    m3u8_link = "N/A"
    referer_url = "N/A"
    watch_link = stream_info['watch_link']

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            def handle_request(request):
                nonlocal m3u8_link, referer_url
                url = request.url
                if '.m3u8' in url or 'playlist' in url or 'manifest' in url or 'm3u' in url:
                    if m3u8_link == "N/A":
                        m3u8_link = url
                        headers = request.headers
                        referer_url = headers.get('referer', 'N/A')

            page.on("request", handle_request)

            print(f"Opening stream page: {watch_link}")
            page.goto(watch_link, timeout=30000, wait_until="domcontentloaded")
            
            # ভিডিও প্লেয়ার ট্রিগার হওয়ার জন্য পর্যাপ্ত সময় অপেক্ষা করা
            page.wait_for_timeout(7000)
            browser.close()

    except Exception as e:
        print(f"Error in playwright for {watch_link}: {e}")

    return {
        "channel": stream_info['channel'],
        "watch_link": watch_link,
        "m3u8_link": m3u8_link,
        "referer": referer_url
    }

def fetch_match_details(card_info):
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    
    team_one_title = card_info['team_one_title']
    team_two_title = card_info['team_two_title']
    team_one_logo = card_info['team_one_logo']
    team_two_logo = card_info['team_two_logo']
    match_link = card_info['match_link']

    match_time_bst = "Time TBA"
    stream_links = []

    try:
        sub_response = scraper.get(match_link, timeout=15)
        if sub_response.status_code == 200:
            sub_soup = BeautifulSoup(sub_response.text, 'html.parser')
            
            # ১. ডেট ও টাইম সংগ্রহ এবং বাংলাদেশ টাইমে কনভার্ট
            time_elem = sub_soup.find(string=lambda t: t and ('UTC' in t or 'PM' in t or 'AM' in t) and (',' in t or 'at' in t))
            if time_elem:
                raw_time_str = time_elem.strip()
                try:
                    clean_str = raw_time_str.replace(' at ', ' ')
                    dt_utc = datetime.strptime(clean_str, '%b %d, %Y %I:%M %p UTC')
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                    bst_timezone = timezone(timedelta(hours=6))
                    dt_bst = dt_utc.astimezone(bst_timezone)
                    match_time_bst = dt_bst.strftime('%I:%M %p, %d %b %Y')
                except:
                    match_time_bst = raw_time_str

            # ২. ৩য় পেজের লিংক বা ওয়াচ বাটনগুলোর টেবিল রো পার্স করা
            # টেবিল বা রো কিংবা যেকোনো এঙ্কর ট্যাগ যা ওয়াচ বা চ্যানেল নির্দেশ করে
            for a_tag in sub_soup.find_all('a', href=True):
                href = a_tag['href']
                text = a_tag.get_text(strip=True).lower()
                # যদি লিঙ্কে watch বা stream অথবা কোনো চ্যানেল আইডি থাকে
                if 'watch' in text or 'stream' in href or 'event' in href or 'channel' in href:
                    full_link = f"https://pogo.pk{href}" if href.startswith('/') else href
                    # ডুপ্লিকেট এড়াতে চেক করা
                    if not any(s['watch_link'] == full_link for s in stream_links):
                        stream_links.append({
                            "channel": a_tag.get_text(strip=True) or "Watch Stream",
                            "watch_link": full_link
                        })

    except Exception as e:
        print(f"Error fetching sub-page {match_link}: {e}")

    processed_streams = []
    if stream_links:
        print(f"Processing {len(stream_links)} streams for {team_one_title} vs {team_two_title}...")
        with ThreadPoolExecutor(max_workers=3) as stream_executor:
            future_streams = [stream_executor.submit(fetch_stream_data, stream) for stream in stream_links]
            for future in as_completed(future_streams):
                res = future.result()
                if res:
                    processed_streams.append(res)

    return {
        "team_one_title": team_one_title,
        "team_two_title": team_two_title,
        "team_one_logo": team_one_logo,
        "team_two_logo": team_two_logo,
        "match_link": match_link,
        "match_time": match_time_bst,
        "streams": processed_streams
    }

def scrape_pogo_matches():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    
    response = scraper.get(URL)
    if response.status_code != 200:
        print("Failed to fetch main page.")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    match_cards_info = []

    # মূল ম্যাচ কার্ডগুলো খুঁজে বের করার জন্য ফ্লেক্স/গ্রিড বা লিংকের কার্ড টার্গেট করা
    match_cards = soup.find_all('a', href=lambda x: x and ('event' in x or 'match' in x or 'stream' in x))
    
    # যদি সরাসরি a ট্যাগ না মিলে, তবে div কার্ড চেক করা
    if not match_cards:
        match_cards = soup.select('div.match-card, div.grid > div, div[class*="flex"]')

    for card in match_cards:
        try:
            # টিম নাম বা টাইটেল বের করার জন্য কার্ডের ভেতরে থাকা টেক্সট বা হেডিং টার্গেট করা
            team_texts = []
            # সাধারণত টিমের নামগুলো span বা p ট্যাগের ভেতরে থাকে
            for el in card.find_all(['span', 'p', 'div', 'h3']):
                t = el.get_text(strip=True)
                if t and len(t) > 2 and not any(w in t.lower() for w in ['live', 'starts', 'am', 'pm', 'epl', 'efl', 'watch']):
                    if t not in team_texts:
                        team_texts.append(t)

            # লোগো সংগ্রহ
            logos = card.find_all('img')
            
            # যদি অন্তত দুটি লোগো এবং টিমের নাম পাওয়া যায় তবেই এটি পারফেক্ট ম্যাচ কার্ড
            if len(logos) >= 2 and len(team_texts) >= 2:
                team_one_title = team_texts[0]
                team_two_title = team_texts[1]
                
                team_one_logo = logos[0].get('src') or logos[0].get('data-src') or "N/A"
                team_two_logo = logos[1].get('src') or logos[1].get('data-src') or "N/A"

                link_tag = card if card.name == 'a' else card.find('a') or card.find_parent('a')
                match_link = "N/A"
                if link_tag and link_tag.has_attr('href'):
                    href = link_tag['href']
                    match_link = f"https://pogo.pk{href}" if href.startswith('/') else href

                if match_link not in ["https://pogo.pk/", "https://pogo.pk", "N/A"] and "leagues" not in match_link:
                    match_info = {
                        "team_one_title": team_one_title,
                        "team_two_title": team_two_title,
                        "team_one_logo": team_one_logo,
                        "team_two_logo": team_two_logo,
                        "match_link": match_link
                    }
                    if match_info not in match_cards_info:
                        match_cards_info.append(match_info)
        except Exception as e:
            print(f"Error parsing card: {e}")

    print(f"Found {len(match_cards_info)} valid match cards.")

    matches_data = []
    status_lines = []
    dots = ['🔴', '🔵', '🟡']
    dot_index = 0

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_match_details, info): info for info in match_cards_info}
        for future in as_completed(futures):
            res = future.result()
            if res:
                matches_data.append(res)
                current_dot = dots[dot_index % len(dots)]
                status_lines.append(f"{current_dot} {res['team_one_title']} vs {res['team_two_title']} | Time: {res['match_time']}")
                dot_index += 1

    with open('matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)

    with open('status.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(status_lines))
    
    print("Scraping completed successfully!")

if __name__ == "__main__":
    scrape_pogo_matches()

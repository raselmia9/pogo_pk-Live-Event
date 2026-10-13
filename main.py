import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

URL = 'https://pogo.pk/'

def fetch_stream_data(stream_info):
    """প্লেরাইট ব্যবহার করে ৩য় পেজে ঢুকে .m3u8 লিংক এবং Referer ক্যাচ করার ফাংশন"""
    m3u8_link = "N/A"
    referer_url = "N/A"
    watch_link = stream_info['watch_link']

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # নেটওয়ার্ক রিকোয়েস্ট ইন্টারসেপ্ট করার লজিক
            def handle_request(request):
                nonlocal m3u8_link, referer_url
                url = request.url
                if '.m3u8' in url or 'playlist' in url or 'manifest' in url:
                    if m3u8_link == "N/A":
                        m3u8_link = url
                        headers = request.headers
                        referer_url = headers.get('referer', 'N/A')

            page.on("request", handle_request)

            print(f"Opening stream page with Playwright: {watch_link}")
            page.goto(watch_link, timeout=25000, wait_until="networkidle")
            
            # ভিডিও প্লেয়ার লোড হওয়ার জন্য কয়েক সেকেন্ড অপেক্ষা করা যাতে রিকোয়েস্ট ট্রিগার হয়
            page.wait_for_timeout(5000)
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
        sub_response = scraper.get(match_link, timeout=10)
        if sub_response.status_code == 200:
            sub_soup = BeautifulSoup(sub_response.text, 'html.parser')
            
            # ডেট এবং টাইম সংগ্রহ ও বাংলাদেশ টাইমে কনভার্ট
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

            # ওয়াচ বা ৩য় পেজের লিংকগুলো সংগ্রহ করা
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

    except Exception as e:
        print(f"Error fetching sub-page {match_link}: {e}")

    # মাল্টিথ্রেডিং ব্যবহার করে প্রতিটি স্ট্রিম লিংক থেকে প্লেরাইটের মাধ্যমে m3u8 ও referer সংগ্রহ করা
    processed_streams = []
    if stream_links:
        print(f"Processing {len(stream_links)} streams with Playwright for {team_one_title} vs {team_two_title}...")
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
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    match_cards_info = []

    potential_cards = soup.find_all(['a', 'div'], class_=lambda x: x and ('match' in x.lower() or 'grid' in x.lower() or 'flex' in x.lower()))
    match_cards = []
    for card in potential_cards:
        if len(card.find_all('img')) >= 2 and card not in match_cards:
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
                teams = [t for t in [el.get_text(strip=True) for el in card.find_all(text=True)] if not any(w in t.lower() for w in ['live', 'starts'])]

            team_one_title = teams[0] if len(teams) > 0 else "N/A"
            team_two_title = teams[1] if len(teams) > 1 else "N/A"

            logos = card.find_all('img')
            team_one_logo = logos[0].get('src') or logos[0].get('data-src') if len(logos) > 0 else "N/A"
            team_two_logo = logos[1].get('src') or logos[1].get('data-src') if len(logos) > 1 else "N/A"

            link_tag = card if card.name == 'a' else card.find_parent('a') or card.find('a')
            match_link = f"https://pogo.pk{link_tag['href']}" if link_tag and link_tag.has_attr('href') and link_tag['href'].startswith('/') else link_tag.get('href', 'N/A')

            if match_link in ["https://pogo.pk/", "https://pogo.pk", "N/A"] or "leagues" in match_link:
                continue

            if team_one_title != "N/A" and team_two_title != "N/A":
                match_cards_info.append({
                    "team_one_title": team_one_title,
                    "team_two_title": team_two_title,
                    "team_one_logo": team_one_logo,
                    "team_two_logo": team_two_logo,
                    "match_link": match_link
                })
        except:
            pass

    matches_data = []
    status_lines = []
    dots = ['🔴', '🔵', '🟡']
    dot_index = 0

    # মূল ম্যাচগুলোর ওপর মাল্টিথ্রেডিং চালানো
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

if __name__ == "__main__":
    scrape_pogo_matches()

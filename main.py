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

    # পোগো সাইটের মূল ম্যাচের কার্ডগুলো যে বক্স বা লিঙ্কের ভেতরে থাকে তা নির্দিষ্ট করা
    # সাধারণত প্রতিটি ম্যাচের জন্য আলাদা লিঙ্ক বা কার্ড ব্লক থাকে যেগুলোতে লোগো ও দুটো টিম থাকে
    match_cards = []
    
    # স্ক্রিনশট অনুযায়ী মূল ম্যাচের কার্ডগুলো পেতে যেসব কমন প্যাটার্ন থাকতে পারে:
    # ১. যেসব কার্ডের ভেতর অন্তত দুটি ইমেজ (লোগো) এবং লিঙ্কের উপস্থিতি আছে
    potential_cards = soup.find_all(['a', 'div'], class_=lambda x: x and ('match' in x.lower() or 'grid' in x.lower() or 'flex' in x.lower()))
    
    for card in potential_cards:
        imgs = card.find_all('img')
        # মূল ম্যাচ কার্ডগুলোতে সাধারণত দুটি টিমের লোগো (২টি img) থাকে
        if len(imgs) >= 2:
            if card not in match_cards:
                match_cards.append(card)

    # যদি উপরের ফিল্টারে কার্ড না পাওয়া যায়, তবে সব অ্যাঙ্কর ট্যাগ বা মেইন গ্রিড চেক করা
    if not match_cards:
        match_cards = soup.select('a[href*="/stream"], a[href*="match"], div.match-card')

    dots = ['🔴', '🔵', '🟡']
    dot_index = 0

    for card in match_cards:
        try:
            # কার্ডের ভেতর থেকে টিমের নাম বা টেক্সটগুলো সংগ্রহ
            team_elements = card.find_all(['span', 'p', 'div'], class_=lambda x: x and ('team' in x.lower() or 'name' in x.lower()))
            if not team_elements:
                team_elements = card.find_all(['span', 'p'])

            teams = [t.get_text(strip=True) for t in team_elements if t.get_text(strip=True)]
            
            # যদি সরাসরি টিম নেম ক্লাস না মিলে, তবে ভেতরের টেক্সটগুলো ফিল্টার করা
            if len(teams) < 2:
                all_texts = [el.get_text(strip=True) for el in card.find_all(text=True) if el.get_text(strip=True)]
                # অপ্রয়োজনীয় শব্দ (যেমন Live Now, Starts in ইত্যাদি) বাদ দিয়ে টিমের নাম বের করা
                filtered_texts = [t for t in all_texts if not any(w in t.lower() for w in ['live', 'starts', 'am', 'pm', 'epl', 'efl', 'fa cup'])]
                teams = filtered_texts

            team_one_title = teams[0] if len(teams) > 0 else "N/A"
            team_two_title = teams[1] if len(teams) > 1 else ("N/A" if len(teams) > 0 else "N/A")

            # টিম লোগোগুলো সংগ্রহ (img ট্যাগ থেকে)
            logos = card.find_all('img')
            team_one_logo = logos[0].get('src') or logos[0].get('data-src') if len(logos) > 0 else "N/A"
            team_two_logo = logos[1].get('src') or logos[1].get('data-src') if len(logos) > 1 else "N/A"

            # দ্বিতীয় পেজের বা ম্যাচের ডিটেইলস পেজের লিংক সংগ্রহ
            link_tag = card if card.name == 'a' else card.find_parent('a') or card.find('a')
            match_link = "N/A"
            if link_tag and link_tag.has_attr('href'):
                href = link_tag['href']
                match_link = f"https://pogo.pk{href}" if href.startswith('/') else href

            # লোগো এবং টিম নাম ভ্যালিড হলে তবেই তালিকায় যুক্ত করব (মেনু বা ফুটার আইটেম বাদ দেওয়ার জন্য)
            if team_one_title != "N/A" and team_two_title != "N/A" and team_one_logo != "N/A":
                match_info = {
                    "team_one_title": team_one_title,
                    "team_two_title": team_two_title,
                    "team_one_logo": team_one_logo,
                    "team_two_logo": team_two_logo,
                    "match_link": match_link
                }
                
                if match_info not in matches_data:
                    matches_data.append(match_info)
                    
                    # স্ট্যাটাস টেক্সটের জন্য রঙিন ডট সহ ফরম্যাট (তারিখ বা সময় ছাড়া)
                    current_dot = dots[dot_index % len(dots)]
                    status_line = f"{current_dot} Match: {team_one_title} vs {team_two_title}"
                    status_lines.append(status_line)
                    dot_index += 1

        except Exception as e:
            print(f"Error parsing match card: {e}")

    # ১. JSON ফাইলে মূল ম্যাচের ডাটা সেভ করা
    with open('matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)

    # ২. Status টেক্সট ফাইলে স্ট্যাটাস সেভ করা
    with open('status.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(status_lines))
    
    print(f"Successfully scraped {len(matches_data)} main matches.")

if __name__ == "__main__":
    scrape_pogo_matches()

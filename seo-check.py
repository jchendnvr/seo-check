#!/usr/bin/env python3

## jchendnvr 
##
## ./seo-check file.html
## ./seo-check https://example.com/mypage.html



import os
import sys
import re
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse




def fetch_html(source):
    if source.startswith("http://") or source.startswith("https://"):
        try:
            headers = {
                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            print(headers)
            response = requests.get(source, headers=headers)
            response.raise_for_status()
            response = response
            if response.status_code == 404:
                print(f"❌ Error: Web page not found (404): {source}")
                sys.exit(1)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching URL: {e}")
            sys.exit(1)
    elif os.path.isfile(source):
        try:
            with open(source, "r", encoding="utf-8") as file:
                content = file.read()
                if not content.strip().lower().startswith("<!doctype") and "<html" not in content.lower():
                    print("❌ Error: Files must be HTML.")
                    sys.exit(1)
                return content
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            sys.exit(1)
    else:
        print("❌ Error: Invalid source. Must be a URL or a local HTML file.")
        sys.exit(1)


def extract_keywords(soup):
    meta = soup.find("meta", attrs={"name": "keywords"})
    if not meta or not meta.get("content"):
        return None, []
    keywords = [k.strip().lower() for k in meta["content"].split(",") if k.strip()]
    if not keywords:
        return None, []
    return keywords[0], keywords[1:]


def count_words_from_tags(soup):
    tags = soup.find_all(["p", "li", "td", "th", "blockquote", "cite"])
    text = " ".join(tag.get_text(separator=' ', strip=True) for tag in tags)
    words = re.findall(r"\b\w+\b", text.lower())
    return len(words), words, text


def contains_keywords(text, keywords):
    matches = {}
    for kw in keywords:
        matches[kw] = text.lower().count(kw.lower())
    return matches


def check_meta_tags(soup, primary, secondary):
    findings = []
    robots = soup.find("meta", attrs={"name": "robots"})
    if robots:
        content = robots.get("content", "").lower()
        if "noindex" in content or "none" in content:
            findings.append("**❌❌❌ Page is not indexed due to meta robots tag.\n There is no point is SEO check for non indexed pages**")
            return findings, True
        elif not ("index" in content or "all" in content):
            findings.append("**❌ Meta robots tag is not set to index or all.**")
    else:
        findings.append("**❌ Meta robots tag not found. Proceeding with checks.**")
    
    
    findings.append("**Meta keywords tag not found. Keyword-based checks will be skipped.**") if primary is None else None       
    all_keywords = [primary] + secondary if primary else []
    keyword_display = ", ".join(all_keywords)
    findings.append(f"\n**Meta Keywords:**\n {keyword_display}\n\n\n**---")


    tags_to_check = [
        ("title", soup.title.string if soup.title else None),
        ("twitter:title", soup.find("meta", property="twitter:title")),
        ("og:title", soup.find("meta", property="og:title")),
        ("description", soup.find("meta", attrs={"name": "description"})),
        ("twitter:description", soup.find("meta", property="twitter:description")),
        ("og:description", soup.find("meta", property="og:description"))
    ]

    for name, tag in tags_to_check:
        text = tag.get("content") if hasattr(tag, 'get') else tag
        if text:
            line = f"**{name}**:"
            if primary in text.lower():
                line += " ✅ Primary keyword present."
            else:
                line += " ❌ Primary keyword missing."
            for kw in secondary:
                if kw in text.lower():
                    line += f" ✅ {kw}"
            findings.append(line)
            findings.append(f"**{name} value:** {text.strip()}")
        else:
            findings.append(f"❌ No {name} tag found.")

    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        findings.append(f"✅**Canonical set to**: {canonical['href']}")
    else:
        findings.append("**❌ rel=\"canonical\" not set.**")

    return findings, False


def analyze_body(soup, primary, secondary):
    body = soup.body
    # print(soup.body)
    if not body:
        return ["No <body> found."], 0, 0, 0

    headings = body.find_all(re.compile("^h[1-4]$"))
    heading_texts = [h.get_text(separator=' ', strip=True).lower() for h in headings]

    keyword_headline_coverage = {k: False for k in [primary] + secondary}
    for text in heading_texts:
        for k in keyword_headline_coverage:
            if k in text:
                keyword_headline_coverage[k] = True

    total_words, all_words, full_text = count_words_from_tags(body)

    heading_words = " ".join(heading_texts).split()
    non_heading_words = [w for w in all_words if w not in heading_words]
    non_heading_count = len(non_heading_words)

    keyword_total_count = sum(non_heading_words.count(k.lower()) for k in [primary] + secondary)
    keyword_percentage = (keyword_total_count / non_heading_count) * 100 if non_heading_count else 0

    results = [f"**Total word count:** {total_words}"]
    if total_words < 300:
        results.append("❌ Less than 300 words on page.")

    for k, v in keyword_headline_coverage.items():
        results.append(f"{'✅' if v else '❌'} Keyword '{k}' in headings")

    used_keywords = {k: full_text.lower().count(k.lower()) > 0 for k in [primary] + secondary}
    for k, used in used_keywords.items():
        if not used:
            results.append(f"❌ Keyword '{k}' not found in body text")

    results.append(f"**Keyword usage in non-heading text:** {keyword_percentage:.2f}%")
    if total_words < 1200:
        if keyword_percentage < 1:
            results.append("❌ Keyword density < 1% for <1200 words")
        elif keyword_percentage > 4:
            results.append("❌ Keyword density > 4% for <1200 words")
        else:
            results.append("✅ Keyword density is good!")
    elif total_words >= 1200:
        if keyword_percentage < 0.7:
            results.append("❌ Keyword density < 0.7% for >1200 words")
        elif keyword_percentage > 3:
            results.append("❌ Keyword density > 3% for >1200 words")
        else:
            results.append("✅ Keyword density is good!")
    return results, total_words, non_heading_count, keyword_total_count


def analyze_images(soup, primary, secondary):
    imgs = soup.find_all("img")
    keyword_set = set([primary] + secondary)
    found_keywords = set()
    findings = []

    for img in imgs:
        fname = img.get("src", "").lower()
        alt = img.get("alt", "").lower()
        text = fname + " " + alt
        for kw in keyword_set:
            if kw in text:
                found_keywords.add(kw)

    for kw in keyword_set:
        findings.append(f"{'✅' if kw in found_keywords else '❌'} Keyword '{kw}' in image src/alt")
    return findings


def generate_report(title, meta_results, body_results, image_results):
    return f"""# SEO Report for `{title}`

## Meta Tags
{chr(10).join(meta_results)}

## Body Analysis
{chr(10).join(body_results)}

## Image Analysis
{chr(10).join(image_results)}
"""


def main():
    parser = argparse.ArgumentParser(description="SEO On-Page Analyzer")
    parser.add_argument("source", help="URL or local HTML file path")
    args = parser.parse_args()

    html = fetch_html(args.source)
    soup = BeautifulSoup(html, "html.parser")

    primary, secondary = extract_keywords(soup)
    if not primary:
        print("No primary keyword found in meta keywords.")
        sys.exit(1)

    meta_results, abort = check_meta_tags(soup, primary, secondary)
    if abort:
        print(generate_report(args.source, meta_results, [], []))
        sys.exit(0)

    body_results, total_words, non_heading, keyword_total = analyze_body(soup, primary, secondary)
    image_results = analyze_images(soup, primary, secondary)
    print(generate_report(args.source, meta_results, body_results, image_results))


if __name__ == "__main__":
    main()

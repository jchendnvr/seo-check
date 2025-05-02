#!/usr/bin/env python3

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
            response = requests.get(source)
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
            findings.append("**Page is not indexed due to meta robots tag.**")
            return findings, True
        elif not ("index" in content or "all" in content):
            findings.append("**Meta robots tag is not set to index or all.**")
    else:
        findings.append("**Meta robots tag not found. Proceeding with checks.**")

    if primary is None:
        findings.append("**Meta keywords tag not found. Keyword-based checks will be skipped.**")
        all_keywords = []
    else:
        all_keywords = [primary] + secondary
        keyword_display = ", ".join(all_keywords)
        findings.append(f"**Meta keywords:** {keyword_display}")

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
            if primary:
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
        findings.append(f"**Canonical set to**: {canonical['href']}")
    else:
        findings.append("**❌ rel=\"canonical\" not set.**")

    return findings, False

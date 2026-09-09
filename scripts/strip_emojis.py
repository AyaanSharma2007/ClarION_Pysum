import re
import os
import sys

# Broad emoji regex
emoji_pattern = re.compile(
    r'['
    r'\U0001f600-\U0001f64f'  # emoticons
    r'\U0001f300-\U0001f5ff'  # symbols & pictographs
    r'\U0001f680-\U0001f6ff'  # transport & map symbols
    r'\U0001f1e0-\U0001f1ff'  # flags (iOS)
    r'\u2702-\u27b0'          # Dingbats
    r'\u24c2-\u25B6'
    r'\u23E9-\u23FA'
    r'\u2600-\u26FF'          # Misc symbols
    r'\U0001f900-\U0001f9ff'  # Supplemental Symbols and Pictographs
    r'\u2B50\u2B55\u23F3'
    r'\u2728'                 # sparkles
    r'\u26A0'                 # warning
    r'\u2705'                 # check mark
    r'\U0001F4A1'             # bulb
    r'\U0001F504'             # refresh
    r'\u23F1'                 # stopwatch
    r'\U0001F4CB'             # clipboard
    r'\U0001F4DD'             # memo
    r'\U0001F50D'             # magnifying glass
    r'\U0001F4BE'             # floppy
    r'\U0001F512'             # lock
    r'\U0001F311'             # moon
    r'\U0001F31E'             # sun
    r']+', flags=re.UNICODE)

# Add some specific ones seen like 🔴 ⚠ ✓ ↻ 💡 ⏱ 📋 📝 🔄 ⏳ ↑ 🌙 ☀️ ❌
specific = ["🔴", "⚠", "✓", "↻", "💡", "⏱", "📋", "📝", "🔄", "⏳", "↑", "🌙", "☀️", "❌", "✨", "✅", "⚠️", "💡", "🔍"]

def strip_emojis(text):
    text = emoji_pattern.sub('', text)
    for c in specific:
        text = text.replace(c, '')
    return text

def process_dir(directory):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith('.jsx') or f.endswith('.js'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                new_content = strip_emojis(content)
                if new_content != content:
                    print(f"Stripped emojis from {path}")
                    with open(path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "frontend", "src"))
process_dir(target_dir)

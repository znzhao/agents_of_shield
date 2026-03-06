import requests
from bs4 import BeautifulSoup
import csv
import os
import re
from pathlib import Path
import time
import unicodedata


class TranscriptDownloader:
    """
    A class to download Marvel's Agents of S.H.I.E.L.D. transcripts from marvelsaos.tumblr.com
    and save them as CSV files with character and line columns.
    """
    
    def __init__(self, base_url="https://marvelsaos.tumblr.com", output_folder="data"):
        """
        Initialize the TranscriptDownloader.
        
        Args:
            base_url: The base URL of the transcript website
            output_folder: The root data folder where transcripts will be saved
                           (files go to {output_folder}/SxEyy/transcript.csv)
        """
        self.base_url = base_url
        self.transcript_url = f"{base_url}/transcript"
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True, parents=True)
    
    def get_episode_list(self):
        """
        Get list of all episodes from the main transcript page.
        
        Returns:
            List of dictionaries containing episode information (season, episode, name, url)
        """
        print(f"Fetching episode list from {self.transcript_url}...")
        response = requests.get(self.transcript_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        episodes = []
        # Find all links that match the pattern /transcript/1x01, /transcript/1x02, etc.
        for link in soup.find_all('a', href=re.compile(r'/transcript/\d+x\d+')):
            href = link.get('href')
            title = link.get_text(strip=True)
            
            # Extract season and episode numbers from the href
            match = re.search(r'/transcript/(\d+)x(\d+)', href)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))
                
                # Extract episode name from title (e.g., "1x01 Pilot" -> "Pilot")
                name_match = re.search(r'\d+x\d+\s+(.*)', title)
                ep_name = name_match.group(1) if name_match else "Unknown"
                
                episodes.append({
                    'season': season,
                    'episode': episode,
                    'name': ep_name,
                    'url': f"{self.base_url}{href}"
                })
        
        # Remove duplicates (in case episodes are listed multiple times)
        unique_episodes = []
        seen = set()
        for ep in episodes:
            key = (ep['season'], ep['episode'])
            if key not in seen:
                seen.add(key)
                unique_episodes.append(ep)
        
        # Sort by season and episode
        unique_episodes.sort(key=lambda x: (x['season'], x['episode']))
        
        return unique_episodes
    def download_transcript(self, url):
        """
        Download and parse a single transcript from the given URL using HTML parsing.
        
        Args:
            url: URL of the transcript page
            
        Returns:
            List of dictionaries with 'character' and 'line' keys
        """
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        # Ensure proper encoding detection
        response.encoding = response.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the transcript container
        caption_div = soup.find('div', class_='caption')
        if not caption_div:
            print("  ⚠ Warning: Transcript HTML structure not found")
            return []

        lines = []
        # Each <p> tag is a dialogue line
        for p in caption_div.find_all('p'):
            text = p.get_text(strip=True)
            # Fix encoding issues: if UTF-8 bytes were decoded as Latin-1, fix it
            try:
                # Try to detect and fix mojibake (UTF-8 decoded as Latin-1)
                if '\xc3' in text or '\xc2' in text:
                    text = text.encode('latin-1').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                # If that fails, just use the text as-is
                pass
            # Normalize unicode: convert smart quotes to regular apostrophes
            text = unicodedata.normalize('NFKC', text)
            text = text.replace("\u2019", "'")
            
            # Match "Character: dialogue"
            match = re.match(r'^([A-Z][A-Za-z\s\-\']*?):\s*(.+)$', text)
            if match:
                character = match.group(1).strip()
                dialogue = match.group(2).strip()
                # Filter out very short entries and non-dialogue patterns
                if len(character) > 1 and len(dialogue) > 3:
                    if not any(skip in character for skip in ['\u00A9', '\u2013', '\u2122']):
                        if not re.search(r'(Pilot|Chapter|Episode|Epilogue|Transcript)[A-Z]', character):
                            lines.append({
                                'character': character,
                                'line': dialogue
                            })
        return lines
    
    def save_to_csv(self, lines, season, episode, name):
        """
        Save transcript lines to a CSV file, handling Unicode properly.
        
        Args:
            lines: List of dictionaries with 'character' and 'line' keys
            season: Season number
            episode: Episode number
            name: Episode name
            
        Returns:
            Path to the saved CSV file
        """
        # Save to data/Season_X/SxEyy_Name/transcript.csv
        ep_dir = self.output_folder / f"Season_{season}" / f"S{season}E{episode:02d}_{name.replace('/', '_')}"
        ep_dir.mkdir(parents=True, exist_ok=True)
        filepath = ep_dir / "transcript.csv"

        # change ’ to '

        # Ensure all lines are properly encoded as UTF-8
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['character', 'line'])
            writer.writeheader()
            for line in lines:
                # Handle Unicode normalization for character and line
                character = line['character']
                dialogue = line['line']
                character = character.replace('\u2019', "'")
                dialogue = dialogue.replace('\u2019', "'")
                writer.writerow({
                    'character': character,
                    'line': dialogue
                })

        print(f"  \u2713 Saved: {filepath} ({len(lines)} lines)")
        return filepath
    
    def download_all(self):
        """Download all transcripts from the website."""
        episodes = self.get_episode_list()
        print(f"\nFound {len(episodes)} episodes to download\n")
        
        successful = 0
        failed = 0
        
        for i, ep in enumerate(episodes, 1):
            try:
                print(f"[{i}/{len(episodes)}] Downloading S{ep['season']}E{ep['episode']:02d} - {ep['name']}...")
                lines = self.download_transcript(ep['url'])
                
                if lines:
                    self.save_to_csv(lines, ep['season'], ep['episode'], ep['name'])
                    successful += 1
                else:
                    print(f"  \u26A0 Warning: No dialogue found for this episode")
                    failed += 1
                
                # Be polite and add a small delay between requests
                time.sleep(1)
                
            except Exception as e:
                print(f"  \u2717 Error downloading {ep['name']}: {e}")
                failed += 1
        
        print(f"\n{'='*60}")
        print(f"Download complete!")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Output folder: {self.output_folder.absolute()}")
        print(f"{'='*60}")
    
    def download_single(self, season, episode):
        """
        Download a single episode transcript.
        
        Args:
            season: Season number
            episode: Episode number
        """
        episodes = self.get_episode_list()
        target_ep = next((ep for ep in episodes if ep['season'] == season and ep['episode'] == episode), None)
        
        if not target_ep:
            print(f"Episode S{season}E{episode:02d} not found!")
            return
        
        try:
            print(f"Downloading S{season}E{episode:02d} - {target_ep['name']}...")
            lines = self.download_transcript(target_ep['url'])
            
            if lines:
                self.save_to_csv(lines, season, episode, target_ep['name'])
            else:
                print("Warning: No dialogue found for this episode")
                
        except Exception as e:
            print(f"Error downloading episode: {e}")


if __name__ == "__main__":
    downloader = TranscriptDownloader()
    
    # Download all transcripts
    downloader.download_all()
    
    # Or download a single episode:
    # downloader.download_single(1, 1)  # Season 1, Episode 1

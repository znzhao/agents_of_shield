import re
import cloudscraper
from bs4 import BeautifulSoup
from pathlib import Path
import time
import unicodedata
import random
from transcript_downloader import TranscriptDownloader

class SynopsisDownloader:
    """
    A class to download Marvel's Agents of S.H.I.E.L.D. episode synopses from marvel.fandom.com
    and save them as plain text files.
    """
    
    def __init__(self, base_url="https://marvel.fandom.com", output_folder="data"):
        """
        Initialize the SynopsisDownloader.
        
        Args:
            base_url: The base URL of the Marvel Fandom website
            output_folder: The root data folder where synopses will be saved
                           (files go to {output_folder}/SxEyy/synopsis.txt)
        """
        self.base_url = base_url
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True, parents=True)
        
        # Create a cloudscraper session to bypass CloudFlare
        self.scraper = cloudscraper.create_scraper()
    
    def get_episode_url(self, season, episode):
        """
        Generate the URL for a specific episode's synopsis page.
        
        Args:
            season: Season number
            episode: Episode number
            
        Returns:
            URL string for the episode
        """
        return f"{self.base_url}/wiki/Marvel%27s_Agents_of_S.H.I.E.L.D._Season_{season}_{episode}"
    
    def download_synopsis(self, url):
        """
        Download and parse a single synopsis from the given URL.
        
        Args:
            url: URL of the synopsis page
            
        Returns:
            String containing the synopsis text, or empty string if not found
        """
        print(f"    Requesting: {url}")
        
        try:
            response = self.scraper.get(url, timeout=30)
            print(f"    Status: {response.status_code}")
            response.raise_for_status()
            
        except Exception as e:
            print(f"    Request failed: {e}")
            raise
        
        response.encoding = response.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the Synopsis header
        synopsis_header = None
        for h2 in soup.find_all('h2', class_='marvel_database_header'):
            if 'Synopsis' in h2.get_text():
                synopsis_header = h2
                break
        
        if not synopsis_header:
            print("  [WARN] Synopsis header not found")
            return ""
        
        # Find the synopsis content div right after the header
        content_div = synopsis_header.find_next('div', class_='marvel_database_section')
        if not content_div:
            print("  [WARN] Synopsis content div not found")
            return ""
        
        # Extract all paragraphs and combine them
        paragraphs = content_div.find_all('p')
        synopsis_text = []
        
        for p in paragraphs:
            text = p.get_text(strip=True)
            # Fix encoding issues
            try:
                if 'â€' in text or 'â' in text:
                    text = text.encode('latin-1').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            
            # Normalize unicode
            text = unicodedata.normalize('NFKC', text)
            text = text.replace("\u2019", "'")
            
            if text:
                synopsis_text.append(text)
        
        return '\n\n'.join(synopsis_text)
    
    def save_to_txt(self, synopsis_text, season, episode, name):
        """
        Save synopsis to a text file.
        
        Args:
            synopsis_text: The synopsis text to save
            season: Season number
            episode: Episode number
            name: Episode name
            
        Returns:
            Path to the saved file
        """
        # Save to data/Season_X/SxEyy_Name/synopsis.txt
        ep_dir = self.output_folder / f"Season_{season}" / f"S{season}E{episode:02d}_{name.replace('/', '_')}"
        ep_dir.mkdir(parents=True, exist_ok=True)
        filepath = ep_dir / "synopsis.txt"
        
        # Save as UTF-8 text file
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(synopsis_text)
        
        print(f"  [OK] Saved: {filepath}")
        return filepath
    
    def download_single(self, season, episode, name):
        """
        Download a single episode synopsis.
        
        Args:
            season: Season number
            episode: Episode number
            name: Episode name
        """
        url = self.get_episode_url(season, episode)
        
        try:
            print(f"Downloading S{season}E{episode:02d} - {name}...")
            synopsis = self.download_synopsis(url)
            
            if synopsis:
                self.save_to_txt(synopsis, season, episode, name)
            else:
                print(f"  [WARN] No synopsis found for this episode")
                
        except Exception as e:
            print(f"  [ERROR] Error downloading episode: {e}")
    
    def download_batch(self, episodes):
        """
        Download synopses for a batch of episodes.
        
        Args:
            episodes: List of dictionaries with 'season', 'episode', and 'name' keys
        """
        print(f"\nDownloading {len(episodes)} episode synopses\n")
        
        successful = 0
        failed = 0
        
        for i, ep in enumerate(episodes, 1):
            try:
                print(f"[{i}/{len(episodes)}] Downloading S{ep['season']}E{ep['episode']:02d} - {ep['name']}...")
                synopsis = self.download_synopsis(self.get_episode_url(ep['season'], ep['episode']))
                
                if synopsis:
                    self.save_to_txt(synopsis, ep['season'], ep['episode'], ep['name'])
                    successful += 1
                else:
                    print(f"  [WARN] No synopsis found")
                    failed += 1
                
                # Wait random time between 1-3 seconds to avoid blocking
                if i < len(episodes):
                    wait_time = random.uniform(1, 3)
                    print(f"  Waiting {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                
            except Exception as e:
                print(f"  [ERROR] Error downloading {ep['name']}: {e}")
                failed += 1
        
        print(f"\n{'='*60}")
        print(f"Download complete!")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Output folder: {self.output_folder.absolute()}")
        print(f"{'='*60}")
    
    def download_all(self):
        """
        Download synopses for all episodes using episode list from TranscriptDownloader.
        """
        print("Getting episode list from TranscriptDownloader...")
        transcript_downloader = TranscriptDownloader()
        episodes = transcript_downloader.get_episode_list()
        
        if not episodes:
            print("No episodes found!")
            return
        
        print(f"Found {len(episodes)} episodes\n")
        self.download_batch(episodes)


if __name__ == "__main__":
    downloader = SynopsisDownloader()
    
    # Download all episodes
    downloader.download_all()

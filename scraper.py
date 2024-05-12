from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import time
import os
from dotenv import load_dotenv

class InstagramScraper:
    def __init__(self, username, password, headless=True):
        self.username = username
        self.password = password

        # Configure Chrome options
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--log-level=3")  # Suppress console warnings/errors
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36"
        options.add_argument(f"user-agent={user_agent}")

        # Initialize WebDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    def human_sleep(self, min_seconds, max_seconds):
        """Sleep for a random duration between min and max seconds."""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def login(self):
        """Log in to Instagram with provided credentials."""
        self.driver.get("https://www.instagram.com/accounts/login/")
        self.human_sleep(2, 5)

        # Accept cookies if the popup is visible
        try:
            allow_cookies_button = self.driver.find_element(By.XPATH, '//button[@class="_a9-- _ap36 _a9_0"]')
            allow_cookies_button.click()
            self.human_sleep(1, 2)
            print("Cookies accepted.")
        except Exception:
            print("No cookie consent button found or already accepted.")

        # Find login elements and perform login
        username_field = self.driver.find_element(By.NAME, 'username')
        password_field = self.driver.find_element(By.NAME, 'password')
        login_button = self.driver.find_element(By.XPATH, '//button[@type="submit"]')

        username_field.send_keys(self.username)
        self.human_sleep(1, 3)
        password_field.send_keys(self.password)
        self.human_sleep(1, 3)
        login_button.click()
        self.human_sleep(3, 6)

    def scrape_profile(self, profile_url, post_count):
        """Scrape up to `post_count` posts from a specific profile URL."""
        self.driver.get(profile_url)
        self.human_sleep(3, 6)
        posts = self.driver.find_elements(By.CLASS_NAME, '_aagw')
        for index, post in enumerate(posts):
            if index >= post_count:
                break
            post.click()
            self.human_sleep(2, 4)
            try:
                image = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, '//img[@class="css-9pa8cd efnq0gx0"]'))
                )
                image_url = image.get_attribute('src')
                print(f"Post {index + 1} Image URL: {image_url}")
            except Exception:
                print(f"Post {index + 1} Image URL not found")
            try:
                caption = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, '//h1[@class="_ap3a _aaco _aacu _aacx _aad7 _aade"]'))
                )
                print(f"Post {index + 1} Caption: {caption.text}")
            except Exception:
                print(f"Post {index + 1} Caption not found")
            try:
                close_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//div[@role="button" and contains(@class, "x1i10hfl")]'))
                )
                close_button.click()
                self.human_sleep(2, 4)
            except Exception:
                print(f"Attempt to close Post {index + 1} failed, retrying...")

    def close(self):
        """Quit the WebDriver."""
        self.driver.quit()

def main():
    # Load credentials from environment variables
    load_dotenv()
    username = os.getenv('MY_APP_USERNAME')
    password = os.getenv('MY_APP_PASSWORD')
    post_count = int(os.getenv('MAX_POSTS_PER_PAGE'))

    # Instantiate the scraper in Non-Headless mode (to be less suspicious)
    scraper = InstagramScraper(username, password, False)

    # Log in to Instagram
    scraper.login()

    # Read the list of profile URLs and define the number of posts to scrape
    file_path = 'scrape.txt'
    with open(file_path, 'r') as file:
        profile_urls = [line.strip() for line in file.readlines() if line.strip()]

    # Scrape each profile
    for url in profile_urls:
        print(f"Scraping profile: {url}")
        scraper.scrape_profile(url, post_count)

    # Close the WebDriver
    scraper.close()

if __name__ == "__main__":
    main()



import re
import threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import random
import requests
import json
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from upload import upload_files, stop_event


class InstagramScraper:
    def __init__(self, username, password,element_timeout, headless=True):
        self.username = username
        self.password = password
        self.element_timeout = element_timeout

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

    def scroll_page(self):
        """Scrolls the page up and down randomly to mimic human reading behavior."""
        current_scroll_position, new_position = 0, 0
        scroll_attempts = 0
        while scroll_attempts < 3:
            # Calculate how far to scroll
            max_scroll = int(self.driver.execute_script("return document.body.scrollHeight") / random.uniform(1, 4))
            scroll_distance = random.randint(-max_scroll, max_scroll)
            
            # Scroll the page
            new_position = current_scroll_position + scroll_distance
            if new_position < 0:
                new_position = 0
            elif new_position > self.driver.execute_script("return document.body.scrollHeight"):
                new_position = self.driver.execute_script("return document.body.scrollHeight")
            
            self.driver.execute_script(f"window.scrollTo(0, {new_position});")
            self.human_sleep(1, 1)  # wait for a bit between scrolls

            current_scroll_position = new_position
            scroll_attempts += 1

    def login(self):
        """Log in to Instagram with provided credentials."""
        self.driver.get("https://www.instagram.com/accounts/login/")
        self.human_sleep(2, 3)

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
        self.human_sleep(6, 10)

    def scrape_profile(self, profile_url, max_post_count):
        """Scrape up to `max_post_count` posts from a specific profile URL."""
        profile = urlparse(profile_url).path.strip('/').split('/')[0]
        print(f'Trying to scrape at most {max_post_count} posts for {profile}...')

        self.driver.get(profile_url)
        self.scroll_page() 
        self.human_sleep(3, 6)

        # Get profile follower count
        follower_count_candidates=self.driver.find_elements(By.CLASS_NAME, '_ac2a')
        follower_count = None

        for candidate in follower_count_candidates:
            if candidate.accessible_name:
                follower_count = int(candidate.accessible_name.replace(',', ''))
                

        print(f"{profile} has {follower_count} followers.")

        try:
            # Find first post
            loaded_posts = self.driver.find_elements(By.CLASS_NAME, '_aagw')
            post = loaded_posts[0]
            print('Opening first post...')
            post.click()
            self.human_sleep(1,3)
            
            
            for index in range(max_post_count):
                post_details = {'account': profile}
                post_details['follower_count'] = follower_count #Todo: Conver to int? Currently something like "9.1k"
                isCarousel = False

                try:
                    print('Trying carousel or video post...')
                    current_post = WebDriverWait(self.driver, self.element_timeout).until(
                        EC.presence_of_element_located((By.XPATH, '//article[.//textarea[@placeholder="Add a comment…"]]'))
                    ) 
                except Exception as e:
                    print(f"Carousel post element not found!")
                    try:
                        print('Trying single image post...')
                        current_post = WebDriverWait(self.driver, self.element_timeout).until(
                            EC.presence_of_element_located((By.XPATH, '//a[.//textarea[@placeholder="Add a comment…"]]'))
                        ) 
                    except Exception as e:
                        print(f"Image post element not found!")

                # Check if there is a button with the label "Next" 
                try:
                    if current_post.find_element(By.XPATH, './/button[@aria-label="Next"]'):
                        isCarousel = True
                        print(f"Carousel post found.")
                except Exception as e:
                    print(f"No carousel found.")

                self.scrape_post(current_post, index, isCarousel, post_details)

                try:

                    buttons = self.driver.find_elements(By.CLASS_NAME, "_abl-")
                    for button in buttons:
                        if button.accessible_name == "Next":
                            print("Moving to next post")
                            button.click()
                            break

                    self.human_sleep(1, 2)
                except Exception as e:
                    print(f"Can't move to next post: {e}")
                    break
        except Exception as e:
            print(f"No posts found!: {e}")
        print(f'Done with scraping {profile}.')

    def scrape_post(self, post, index, isCarousel, post_details):
        unique_id = self.driver.current_url.split('/')[-2]
        image_found = False
        image_number = 0

        try: 
            if isCarousel:
                carousel_content = post.find_element(By.TAG_NAME, 'ul')
                scraped_urls = []
                while True: 
                    img_elements = carousel_content.find_elements(By.TAG_NAME, 'img')
                    for image in img_elements:
                        
                        image_url = image.get_attribute('src')
                        if not any(image_url in s for s in scraped_urls) :
                            try:
                                self.scrape_image(image,image_url, post_details, unique_id, image_number)
                                scraped_urls.append(image_url)
                                image_number += 1
                                image_found = True
                            except Exception as e:
                                print(f"Post {index}: Couldn't scrape Image {image_number} in carousel: {str(e)}")
                        
                    try:
                        print('Clicking next')
                        next_button = post.find_element(By.XPATH, './/button[@aria-label="Next"]')
                        next_button.click()
                        self.human_sleep(1,2)  
                    except Exception as e: 
                        print(f'No next button found in carousel!')
                        break       
            else:
                # Only single image
                image = WebDriverWait(post, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'img.x5yr21d.xu96u03.x10l6tqk.x13vifvy.x87ps6o.xh8yej3'))
                )
                image_url = image.get_attribute('src')
                try:
                    self.scrape_image(image, image_url, post_details, unique_id)
                    image_found = True
                except Exception as e:
                    print(f"Post {index}: Couldn't scrape Image: {str(e)}")  
        except Exception as e:
            print(f"Problem with image in srcape post: {e}")


        if image_found:
            # Get Date
            try:
                time_element = WebDriverWait(post, self.element_timeout).until(
                    EC.visibility_of_element_located((By.XPATH, '//time[@class="x1p4m5qa"]'))
                )
                post_time = time_element.get_attribute('datetime')
                post_details['time'] = post_time
                print(f"Post {index} Time: {post_time}")
            except Exception as e:
                print(f"Post {index} Time not found: {str(e)}")
                post_details['time'] = None
            
            # Get Caption
            try:
                caption = WebDriverWait(post, self.element_timeout).until(
                    EC.visibility_of_element_located((By.XPATH, '//h1[@class="_ap3a _aaco _aacu _aacx _aad7 _aade"]'))
                ).text
                post_details['caption'] = caption
                print(f"Post {index} Caption: {caption[:15]}")
            except Exception:
                print(f"Post {index} Caption not found")
                post_details['caption'] = None

            # Get Likes 
            try:
                likes = WebDriverWait(post, self.element_timeout).until(
                    EC.visibility_of_element_located((By.XPATH, "//span[contains(text(), 'likes')]/span[contains(@class, 'xdj266r')]"))
                ).text
                post_details['likes'] = int(likes)
                print(f"Post {index} Likes: {likes}")
            except Exception as e:
                print(f"Post {index} Likes not found!: {e}")
                post_details['likes'] = None

            
            # Get Comments

            target_folder = './scraped data'
            json_filename = f"{unique_id}.json"
            json_file_path = os.path.join(target_folder, json_filename)
            with open(json_file_path, 'w') as json_file:
                json.dump(post_details, json_file)

        


        

    def scrape_image(self, image,image_url,post_details, unique_id, image_number=None):
        image_response = requests.get(image_url)

        alt_attribute = image.get_attribute('alt')
        # Clean up unecessary filler 
        # Regular expression to find "May be" and everything before it
        pattern = r'.*May be'
        # Substitute the pattern with an empty string
        result = re.sub(pattern, '', alt_attribute)
        result.strip()  # Remove leading/trailing whitespaces
    
        if 'picture_contents' in post_details and isinstance(post_details['picture_contents'], list):
            # Append the alt attribute to the list
            post_details['picture_contents'].append(result)
        else:
            # Initialize 'picture_contents' as a list with the alt attribute
            post_details['picture_contents'] = [result]

        if 'source_url' in post_details and isinstance(post_details['source_url'], list):
            # Append the alt attribute to the list
            post_details['source_url'].append(image_url)
        else:
            # Initialize 'picture_contents' as a list with the alt attribute
            post_details['source_url'] = [image_url]
        

        
        if image_number is not None: 
            image_filename = f"{unique_id}_{image_number}.png"
        else:
            image_filename = f"{unique_id}.png"

        target_folder = './scraped data'
        image_file_path = os.path.join(target_folder, image_filename)
        with open(image_file_path, 'wb') as f:
            f.write(image_response.content)

    def close(self):
        """Quit the WebDriver."""
        self.driver.quit()

def main():
    # Load credentials from environment variables
    load_dotenv()
    username = os.getenv('MY_APP_USERNAME')
    password = os.getenv('MY_APP_PASSWORD')
    max_post_count = int(os.getenv('MAX_POSTS_PER_PAGE'))
    element_timeout = int(os.getenv('ELEMENT_TIMEOUT'))

    # Instantiate the scraper in Non-Headless mode (to be less suspicious)
    # Erstelle und starte den Thread
    
  # Wartet, bis der Thread beendet ist
    scraper = InstagramScraper(username, password, element_timeout, False, )


    upload_thread = threading.Thread(target=upload_files)
    upload_thread.start()

    # Log in to Instagram
    scraper.login()

    # Read the list of profile URLs and define the number of posts to scrape
    file_path = 'scrape.txt'
    with open(file_path, 'r') as file:
        profile_urls = [line.strip() for line in file.readlines() if line.strip()]

    # Scrape each profile
    for url in profile_urls:
        print(f"Scraping profile: {url}")
        scraper.scrape_profile(url, max_post_count)

    # Close the WebDriver
    scraper.close()
    stop_event.set()
    upload_thread.join()

if __name__ == "__main__":
    main()
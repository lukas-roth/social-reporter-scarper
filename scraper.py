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
import portalocker
import logging_config


class InstagramScraper:
    def __init__(self, username, password, element_timeout, headless=True):
        self.username = username
        self.password = password
        self.element_timeout = element_timeout
        self.logger = logging_config.get_logger("Scraper")

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
            self.logger.info("Cookies accepted.")  
        except Exception as e:
            self.logger.error(f"No cookie consent button found or already accepted! {e}")  

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

    def scrape_profile(self, profile_url):
        """Scrape up to `max_post_count` posts from a specific profile URL."""
        profile = urlparse(profile_url).path.strip('/').split('/')[0]
        self.logger.info(f'Trying to scrape posts for {profile}.')

        self.driver.get(profile_url)
        self.scroll_page() 
        self.human_sleep(3, 6)

        # Get profile follower count
        follower_count_candidates = self.driver.find_elements(By.CLASS_NAME, '_ac2a')
        follower_count = None

        for candidate in follower_count_candidates:
            if candidate.accessible_name:
                follower_count = int(candidate.accessible_name.replace(',', ''))

        self.logger.info(f"{profile} has {follower_count} followers.")  

        try:
            # Find first post
            loaded_posts = self.driver.find_elements(By.CLASS_NAME, '_aagw')
            post = loaded_posts[0]
            self.logger.info('Opening first post...')
            post.click()
            self.human_sleep(1, 3)
            
            index = 0
            
            #for index in range(max_post_count):
            while True:
                unique_id = self.driver.current_url.split('/')[-2]
                self.logger.debug(f"Found post_id: {unique_id}.")

                is_uploaded = self.is_post_uploaded(unique_id)

                if  is_uploaded and self.is_profile_completed(profile):
                    self.logger.info(f"Already scraped profile {profile}. Now new posts found")
                    return True
                
                if not is_uploaded:  
                    post_details = {'account': profile}
                    post_details['follower_count'] = follower_count 
                    isCarousel = False

                    try:
                        self.logger.debug('Checking if article element is present...')  
                        current_post = WebDriverWait(self.driver, self.element_timeout).until(
                            EC.presence_of_element_located((By.XPATH, '//article[.//textarea[@placeholder="Add a comment…"] or .//span[text()="Comments on this post have been limited."]]'))
                        ) 
                    except Exception as e:
                        self.logger.debug(f"No article element found!")  
                        try:
                            self.logger.debug('Checking if <a> element...')  
                            current_post = WebDriverWait(self.driver, self.element_timeout).until(
                                EC.presence_of_element_located((By.XPATH, '//a[.//textarea[@placeholder="Add a comment…"]]'))
                            ) 
                        except Exception as e:
                            self.logger.debug(f"<a> element not found!")  

                    # Check if there is a button with the label "Next" 
                    if current_post:
                        try:
                            if current_post.find_element(By.XPATH, './/button[@aria-label="Next"]'):
                                isCarousel = True
                                self.logger.debug(f"Carousel post found.")  
                        except Exception as e:
                            self.logger.debug(f"No carousel post found.") 

                        self.scrape_post(current_post, unique_id, index, isCarousel, post_details)
                else:
                    self.logger.debug(f"Already scraped post: {unique_id}.")  
                try:
                    buttons = self.driver.find_elements(By.CLASS_NAME, "_abl-")
                    next_button_found = False
                    for button in buttons:
                        if button.accessible_name == "Next":
                            self.logger.info("Moving to next post.")  
                            index += 1
                            button.click()
                            next_button_found = True
                            break
                    self.human_sleep(1, 2)
                    if not next_button_found:
                        raise Exception("No next button found on profile post")
                except Exception as e:
                    self.logger.debug(f"Can't move to next post!")
                    self.save_completed_profile(profile)  
                    break
        except Exception as e:
            self.logger.debug(f"No posts found for profile {profile}!: {e}")
        self.logger.info(f'Done with scraping {profile}.')
        return True
        
    def scrape_post(self, post, unique_id, index, isCarousel, post_details):
        
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
                                self.scrape_image(image, image_url, post_details, unique_id, image_number)
                                scraped_urls.append(image_url)
                                image_number += 1
                                image_found = True
                            except Exception as e:
                                self.logger.warning(f"Post {index}: Couldn't scrape image {image_number} in carousel! {str(e)}")  
                        
                    try:
                        self.logger.info('Clicking next.')  
                        next_button = post.find_element(By.XPATH, './/button[@aria-label="Next"]')
                        next_button.click()
                        self.human_sleep(1, 2)  
                    except Exception as e: 
                        self.logger.debug(f'No next button found in carousel!')  
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
                    self.logger.warning(f"Couldn't scrape image! {str(e)}")  
        except Exception as e:
            self.logger.debug(f"Problem with image in post {unique_id}! {str(e)}")
            self.mark_post_for_skipping(unique_id)  


        if image_found:
            # Get Date
            try:
                time_element = WebDriverWait(post, self.element_timeout).until(
                    EC.visibility_of_element_located((By.XPATH, '//time[@class="x1p4m5qa"]'))
                )
                post_time = time_element.get_attribute('datetime')
                post_details['time'] = post_time
                self.logger.debug(f"Post {index} Time: {post_time}")  
            except Exception as e:
                self.logger.warning(f"Post {index} Time not found! {str(e)}") 
                post_details['time'] = None
            
            # Get Caption
            try:
                caption = WebDriverWait(post, self.element_timeout).until(
                    EC.visibility_of_element_located((By.XPATH, '//h1[@class="_ap3a _aaco _aacu _aacx _aad7 _aade"]'))
                ).text
                if caption:
                    post_details['caption'] = caption
                else: 
                    post_details['caption'] = ''
                self.logger.debug(f"Post {index} Caption: {caption[:15]}")  
            except Exception as e:
                self.logger.warning(f"Post {index} Caption not found! {str(e)}") 
                post_details['caption'] = None

            # Get Likes 
            try:
                likes = WebDriverWait(post, self.element_timeout).until(
                    EC.visibility_of_element_located((By.XPATH, "//span[contains(text(), 'likes')]/span[contains(@class, 'xdj266r')]"))
                ).text.replace(',', '')
                post_details['likes'] = int(likes)
                self.logger.info(f"Post {index}, Likes: {likes}")  
            except Exception as e:
                self.logger.warning(f"Post {index} Likes not found! {e}")  
                post_details['likes'] = None

            # Get comments
            post_details['comments'] = self.scrape_comments(post, caption)

            target_folder = './scraped data'
            json_filename = f"{unique_id}.json"
            json_file_path = os.path.join(target_folder, json_filename)
            with open(json_file_path, 'w') as json_file:
                json.dump(post_details, json_file)

    def scrape_image(self, image, image_url, post_details, unique_id, image_number=None):
        image_response = requests.get(image_url)

        alt_attribute = image.get_attribute('alt')
        # Clean up unnecessary filler 
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

    def scrape_comments(self, post, caption):
        try:
            # Find the parent div containing the comments
            parent_div = WebDriverWait(post, self.element_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.x9f619.xjbqb8w.x78zum5.x168nmei.x13lgxp2.x5pf9jr.xo71vjh.x1uhb9sk.x1plvlek.xryxfnj.x1c4vz4f.x2lah0s.xdt5ytf.xqjyukv.x1qjc9v5.x1oa3qoh.x1nhvcw1"))
            )
            
            # Find all comment elements within the parent div
            comments_divs = post.find_elements(By.XPATH, ".//li[contains(@class, '_a9zj')]")
            
            comments = []
            for comment_div in comments_divs:

                comment = comment_div.text
                text, likes = self.extract_comment_data(comment)
                comment = {"text": text, "likes": likes}
                if text not in caption:
                    comments.append(comment)
            
            return comments
    
        except Exception as e:
            self.logger.debug(f'An error occured scraping the comments!: {e}')
            return []
    
    def extract_comment_data(self,comment):
        # Regex to extract text content (emoji or text between newlines)
        text_match = re.search(r'\n(.*?)\n', comment)
        comment_text = text_match.group(1) if text_match else ''
        
        # Regex to extract the number of likes
        likes_match = re.search(r'(\d+)\s+likes', comment)
        comment_likes = int(likes_match.group(1)) if likes_match else 2  # Default to 2 if no likes found
        
        return comment_text, comment_likes

    def load_file_data(self, file):
        if os.path.exists(file):
            with open(file, 'r') as f:
                portalocker.lock(f, portalocker.LOCK_SH)  # Shared lock for reading
                try:
                    data = json.load(f)
                    self.logger.debug(f"Loaded {file}: {data}")  
                    return data
                finally:
                    portalocker.unlock(f)
        else:
            self.logger.debug(f"{file} does not exist.")  
        return {}
    
    def mark_post_for_skipping(self, post_id):
        uploaded_posts = self.load_file_data('uploaded_posts.json')
        with open('uploaded_posts.json', 'w+') as f:  # Open file in read/write mode, create if it doesn't exist
            portalocker.lock(f, portalocker.LOCK_EX)  # Exclusive lock for writing
            try:
                uploaded_posts[post_id] = True
                f.seek(0)
                f.truncate()  # Clear the file contents before writing
                json.dump(uploaded_posts, f)
                self.logger.info(f"Post {post_id} marked for skipping.")
            finally:
                portalocker.unlock(f)

    def is_post_uploaded(self, post_id):
        uploaded_posts = self.load_file_data('uploaded_posts.json')
        is_uploaded = uploaded_posts.get(post_id, False)
        self.logger.debug(f"Checking if post {post_id} has been scraped already: {is_uploaded}") 
        return is_uploaded
    
    def is_profile_completed(self, profile):
        uploaded_posts = self.load_file_data('scraped_profiles.json')
        is_completed = uploaded_posts.get(profile, False)
        self.logger.debug(f"Checking if profile {profile} has been scraped already: {is_completed}") 
        return is_completed
    
    def save_completed_profile(self, profile):
        completed_profiles = self.load_file_data('scraped_profiles.json')
        with open('scraped_profiles.json', 'w+') as f:  # Open file in read/write mode, create if it doesn't exist
            portalocker.lock(f, portalocker.LOCK_EX)  # Exclusive lock for writing
            try:
                completed_profiles[profile] = True
                f.seek(0)
                f.truncate()  # Clear the file contents before writing
                json.dump(completed_profiles, f)
                self.logger.debug(f"Post {profile} marked as completed.")
            finally:
                portalocker.unlock(f)


    def close(self):
        """Quit the WebDriver."""
        self.driver.quit()

def main():
    # Load credentials from environment variables
    load_dotenv()
    username = os.getenv('MY_APP_USERNAME')
    password = os.getenv('MY_APP_PASSWORD')
    element_timeout = int(os.getenv('ELEMENT_TIMEOUT'))

    # Instantiate the scraper in Non-Headless mode (to be less suspicious)
    # Erstelle und starte den Thread
    
    # Wartet, bis der Thread beendet ist
    scraper = InstagramScraper(username, password, element_timeout, False)

    upload_thread = threading.Thread(target=upload_files)
    upload_thread.start()

    # Log in to Instagram
    scraper.login()

    # Read the list of profile URLs and define the number of posts to scrape
    file_path = 'scrape.txt'
    with open(file_path, 'r') as file:
        portalocker.lock(file, portalocker.LOCK_SH)  # Acquire a shared lock
        try:
            profile_urls = [line.strip() for line in file.readlines() if line.strip()]
        finally:
            portalocker.unlock(file)  # Ensure the lock is released

    # Scrape each profile
    for url in profile_urls:
        scraper.scrape_profile(url)

    # Close the WebDriver
    scraper.close()
    stop_event.set()
    upload_thread.join()

if __name__ == "__main__":
    main()

import json
import os
import time
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import threading 
import portalocker
import logging_config


stop_event = threading.Event()

def upload_files():

    logger = logging_config.get_logger('Upload')

    logger.info("Upload.py started.")
    
    current_dir = os.getcwd()
    logger.debug(f'Current working directory: {current_dir}')
    
    client_secrets_path = os.path.join(current_dir, 'client_secrets.json')
    logger.debug(f'Path to client_secrets.json: {client_secrets_path}')
    
    # Prüfen, ob die client_secrets.json Datei existiert
    if not os.path.exists(client_secrets_path):
        logger.error(f'client_secrets.json file not found! {client_secrets_path}')
        return
    
    # Google Drive authentifizieren
    gauth = GoogleAuth()
    gauth.settings['client_config_file'] = "client_secrets.json"
    gauth.settings['oauth_scope'] = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file"]
    gauth.LoadClientConfigFile(client_secrets_path)
    gauth.LocalWebserverAuth()  # Erfordert das erste Mal Benutzerauthentifizierung im Webbrowser
    drive = GoogleDrive(gauth)

    # Google Drive Ordner ID von "Postdetails"
    folder_name = 'Social Reporter Data'
    folder_id = None

    # Überprüfen, ob der Ordner "Postdetails" existiert
    file_list = drive.ListFile({'q': "title='{}' and mimeType='application/vnd.google-apps.folder' and trashed=false".format(folder_name)}).GetList()
    if file_list:
        folder_id = file_list[0]['id']
    else:
        # Erstelle den Ordner, falls er nicht existiert
        folder_metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        folder_id = folder['id']
    local_folder = 'scraped data'

    # Call the function to count uploaded files
    uploaded_counts = count_uploaded_files(drive, folder_id)
    logger.info(f"PNG files uploaded: {uploaded_counts['png_count']}")
    logger.info(f"JSON files uploaded: {uploaded_counts['json_count']}")

    upload_manager = UploadManager()


    while not stop_event.is_set() or os.listdir(local_folder):
        for filename in os.listdir(local_folder):
            file_path = os.path.join(local_folder, filename)
            if os.path.isfile(file_path):
                post_id = extract_post_id(filename)
                logger.debug(f"Post_id: {post_id}")  
                if upload_manager.is_post_uploaded(post_id):
                    logger.info(f'{filename} has already been uploaded and will be skipped.') 
                    safe_delete(file_path)
                    continue
                else:
                    try:
                        file_drive = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
                        file_drive.SetContentFile(file_path)
                        file_drive.Upload()
                        del file_drive
                        logger.debug(f'{filename} uploaded.')
                        safe_delete(file_path)
                        
                        # Check if all parts of the post are uploaded
                        post_files = [f for f in os.listdir(local_folder) if f.startswith(post_id)]
                        if not post_files:
                            upload_manager.save_uploaded_post(post_id)
                    except Exception as e:
                        logger.error(f"File could not be uploaded!: {e}")
    logger.info("Upload.py done.")

def safe_delete(file_path, attempts=10, delay=5):
    """Attempt to delete a file with retries and delays between attempts."""
    logger = logging_config.get_logger('Uploader')
    for attempt in range(attempts):
        try:
            os.remove(file_path)
            logger.debug(f'{file_path} has been deleted from the local folder.')
            break
        except Exception as e:
            logger.warning(f"{file_path} could not be deleted!: {e}")
            time.sleep(delay)  # Wait before retrying
    else:
        logger.error(f"Failed to delete {file_path} after {attempts} attempts.")

def extract_post_id(filename):
    return filename.split('.')[0][:11]

def count_uploaded_files(drive, folder_id):
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            file_list = drive.ListFile({'q': query}).GetList()
            
            png_count = sum(1 for file in file_list if file['mimeType'] == 'image/jpeg')
            json_count = sum(1 for file in file_list if file['mimeType'] == 'application/json')
            
            return {'png_count': png_count, 'json_count': json_count}
        except Exception as e:
            logger = logging_config.get_logger('Uploader')
            logger.error(f"An error occurred while counting files: {e}")
            return {'png_count': 0, 'json_count': 0}


class UploadManager:

    def __init__(self):
        current_dir = os.getcwd()
        self.uploaded_posts_file_path = os.path.join(current_dir, 'uploaded_posts.json')
        self.logger = logging_config.get_logger('Uploader')

    def load_uploaded_posts(self):
        if os.path.exists(self.uploaded_posts_file_path):
            with open(self.uploaded_posts_file_path, 'r') as f:
                portalocker.lock(f, portalocker.LOCK_SH)  # Shared lock for reading
                try:
                    data = json.load(f)
                    self.logger.debug(f"Loaded uploaded posts: {data}")
                    return data
                finally:
                    portalocker.unlock(f)
        else:
            self.logger.debug(f"{self.uploaded_posts_file_path} does not exist.")
        return {}

    def is_post_uploaded(self, post_id):
        uploaded_posts = self.load_uploaded_posts()
        is_uploaded = uploaded_posts.get(post_id, False)
        self.logger.debug(f"Checking if post {post_id} is uploaded: {is_uploaded}")
        return is_uploaded

    def save_uploaded_post(self, post_id):
        uploaded_posts = self.load_uploaded_posts()
        with open(self.uploaded_posts_file_path, 'w+') as f:  # Open file in read/write mode, create if it doesn't exist
            portalocker.lock(f, portalocker.LOCK_EX)  # Exclusive lock for writing
            try:
                uploaded_posts[post_id] = True
                f.seek(0)
                f.truncate()  # Clear the file contents before writing
                json.dump(uploaded_posts, f)
                self.logger.info(f"Post {post_id} marked as uploaded.")
            finally:
                portalocker.unlock(f)

    






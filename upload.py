import json
import os
import time
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import threading 
import portalocker


stop_event = threading.Event()

def upload_files():

    print("Upload.py gestartet.")
    
    # Arbeitsverzeichnis überprüfen
    current_dir = os.getcwd()
    print(f'Aktuelles Arbeitsverzeichnis: {current_dir}')
    
    # Absoluten Pfad zur client_secrets.json angeben
    client_secrets_path = os.path.join(current_dir, 'client_secrets.json')
    print(f'Pfad zur client_secrets.json: {client_secrets_path}')
    
    # Prüfen, ob die client_secrets.json Datei existiert
    if not os.path.exists(client_secrets_path):
        print(f'client_secrets.json Datei nicht gefunden: {client_secrets_path}')
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

    upload_manager = UploadManager()

    while not stop_event.is_set() or os.listdir(local_folder):
        for filename in os.listdir(local_folder):
            file_path = os.path.join(local_folder, filename)
            if os.path.isfile(file_path):
                post_id = extract_post_id(filename)
                print(f"Post_id: {post_id}")
                if upload_manager.is_post_uploaded(post_id):
                    print(f'{filename} wurde bereits hochgeladen und wird übersprungen.')
                    safe_delete(file_path)
                    continue
                else:
                    try:
                        file_drive = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
                        file_drive.SetContentFile(file_path)
                        file_drive.Upload()
                        del file_drive
                        print(f'{filename} hochgeladen.')
                        safe_delete(file_path)
                        
                        # Check if all parts of the post are uploaded
                        post_files = [f for f in os.listdir(local_folder) if f.startswith(post_id)]
                        if not post_files:
                            upload_manager.save_uploaded_post(post_id)
                    except Exception as e:
                        print(f"Datei konnte nich hochgeladen werden!: {e}")
    print("Upload.py beendet.")

def safe_delete(file_path, attempts=10, delay=5):
    """Attempt to delete a file with retries and delays between attempts."""
    for attempt in range(attempts):
        try:
            os.remove(file_path)
            print(f'{file_path} wurde aus dem lokalen Ordner gelöscht.')
            break
        except Exception as e:
            print(f"{file_path} konnte nicht gelöscht werden!: {e}")
            time.sleep(delay)  # Wait before retrying
    else:
        print(f"Failed to delete {file_path} after {attempts} attempts.")

def extract_post_id(filename):
    return filename.split('.')[0][:11]


class UploadManager:

    def __init__(self):
        current_dir = os.getcwd()
        self.uploaded_posts_file_path = os.path.join(current_dir, 'uploaded_posts.json')

    def load_uploaded_posts(self):
        if os.path.exists(self.uploaded_posts_file_path):
            with open(self.uploaded_posts_file_path, 'r') as f:
                portalocker.lock(f, portalocker.LOCK_SH)  # Shared lock for reading
                try:
                    data = json.load(f)
                    print(f"Loaded uploaded posts: {data}")
                    return data
                finally:
                    portalocker.unlock(f)
        else:
            print(f"{self.uploaded_posts_file_path} does not exist.")
        return {}

    def is_post_uploaded(self, post_id):
        uploaded_posts = self.load_uploaded_posts()
        is_uploaded = uploaded_posts.get(post_id, False)
        print(f"Checking if post {post_id} is uploaded: {is_uploaded}")
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
                print(f"Post {post_id} marked as uploaded.")
            finally:
                portalocker.unlock(f)





import os
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import threading

def upload_files():
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
    folder_name = 'Postdetails'
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

    # Dateien aus dem lokalen Ordner "example data" hochladen
    local_folder = 'example data'
    for filename in os.listdir(local_folder):
        file_path = os.path.join(local_folder, filename)
        if os.path.isfile(file_path):
            # Überprüfen, ob die Datei bereits im Zielordner existiert
            existing_files = drive.ListFile({'q': "'{}' in parents and title='{}' and trashed=false".format(folder_id, filename)}).GetList()
            if existing_files:
                print(f'{filename} existiert bereits und wird nicht hochgeladen.')
            else:
                file_drive = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
                file_drive.SetContentFile(file_path)
                file_drive.Upload()
                print(f'{filename} hochgeladen.')

# Erstelle und starte den Thread
upload_thread = threading.Thread(target=upload_files)
upload_thread.start()
upload_thread.join()  # Wartet, bis der Thread beendet ist

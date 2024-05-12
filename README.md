# Instagram Scraper für das Projekt Social Reporter


### Setup
1. Clone project. 
2. Requirements installieren (entweder A oder B). 
    - A: [Conda](https://docs.anaconda.com/free/miniconda/index.html) environment erstellen: 
        ```
        conda create --name social-reporter --file conda-requirements.txt
        conda activate social-reporter
        ```
    - B: Oder mit Python virtual environment:
        ```
        python3 -m venv env
        source env/bin/activate
        pip install -r pip-requirements.txt
        ```

4. Instagram Account in .env Datei hinterlegen.
5. URLs der zu scrapenden Accounts in scrape.txt anpassen.
3. Scrape.py ausführen
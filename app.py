from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from db_setup import create_database, create_tables
from generative_text_engine import GenerativeTextEngine
from config import websites_config
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import json
import re
import requests
from pytrends.request import TrendReq
import MySQLdb
import traceback
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import os
import asyncio
from sklearn.feature_extraction.text import TfidfVectorizer
from prompts import Prompts


app = Flask(__name__)



# Load environment variables from the .env file
load_dotenv()

# Flask Secret Key
app.secret_key = os.getenv('SECRET_KEY')

# MySQL Configuration
mysql = MySQL(app)
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')

# API Keys
generative_api_key = os.getenv('GENERATIVE_API_KEY')
scraper_api_key = os.getenv('SCRAPER_API_KEY')

with app.app_context():
    create_database(mysql)
    create_tables(app, mysql)
    
# Set up logging to a file with rotation
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
handler.setFormatter(formatter)
app.logger.addHandler(handler)


def is_article_link(tag, keyword):
    return tag.name == 'a' and tag.get('href', '').startswith(keyword)


# Utility function to calculate relevance based on multiple factors
def calculate_relevance(title, description, query, citation_count=0, publication_date=None, journal_impact=1):
    score = 0
    query_terms = query.split()

    # Boost for keyword matches in title (more weight for title matches)
    for term in query_terms:
        if title and term.lower() in title.lower():
            score += 5  # Higher weight for title match

        if description and term.lower() in description.lower():
            score += 3  # Moderate weight for description match

    # Incorporating citation count (assumes higher citations means higher relevance)
    score += min(citation_count / 100, 5)  # Normalizing citation impact

    # Incorporating publication date (recent papers could be more relevant)
    if publication_date:
        try:
            pub_date = datetime.strptime(publication_date, '%Y-%m-%d')
            days_since_publication = (datetime.now() - pub_date).days
            if days_since_publication < 365:  # Boost for papers published in the last year
                score += 3
            elif days_since_publication < 3 * 365:  # Boost for papers published in the last three years
                score += 1
        except ValueError:
            pass  # Ignore if date format is invalid

    # Adding journal impact (if available) - high-impact journals get a boost
    score += journal_impact * 2

    # Use TF-IDF for more fine-tuned term relevance within the title and description
    tfidf = TfidfVectorizer(stop_words='english')
    text_data = [title, description]
    if any(text_data):
        tfidf_matrix = tfidf.fit_transform(text_data)
        feature_names = tfidf.get_feature_names_out()
        for term in query_terms:
            if term.lower() in feature_names:
                term_index = list(feature_names).index(term.lower())
                # Add TF-IDF score for the term if it's present
                score += tfidf_matrix[0, term_index] * 2  # TF-IDF of title weighted more
                score += tfidf_matrix[1, term_index] if len(text_data) > 1 else 0

    return round(score, 2)  # Return rounded score for better readability

# Function to process data for each site
def process_site_data(site, soup, base_url, qry):
    data = []
    
    if site == 'springer':
        for article in soup.find_all('li', class_='app-card-open'):
            article_tag = article.find('a', class_='app-card-open__link')
            article_url = f"{base_url}{article_tag.get('href')}"
            title = article_tag.text.strip()

            article_response = requests.get(article_url)
            article_soup = BeautifulSoup(article_response.content, 'html.parser')
            abstract_tag = article_soup.find('div', class_='c-article-section__content')
            abstract = abstract_tag.text.strip() if abstract_tag else "No abstract available"
            authors_tags = article_soup.find('ul', class_='c-article-author-list')
            authors = [author.text.strip() for author in authors_tags.find_all('a', {'data-test': 'author-name'})] if authors_tags else []
            date_tag = article_soup.find('time')
            date_text = date_tag.text.strip() if date_tag else "Date not available"
            pdf_link_tag = article_soup.find('a', class_='c-pdf-download__link')
            pdf_link = f"{base_url}{pdf_link_tag.get('href')}" if pdf_link_tag else "No PDF available"
            
            relevance_score = calculate_relevance(title, abstract, qry)

            content = {
                "url": article_url,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "relevance": relevance_score,
                "source": site,
                "date": date_text,
                "pdf_link": pdf_link
            }
            data.append(content)

    elif site == 'mdpi':
        for article in soup.find_all('div', class_='generic-item article-item'):
            article_url_tag = article.find('a', class_='title-link')
            article_url = f"{base_url}{article_url_tag.get('href')}"
            title = article_url_tag.text.strip()
            description_tag = article.find('div', class_='abstract-cropped')
            description_text = description_tag.text.strip() if description_tag else None
            authors_list = [author.text.strip() for author in article.find('div', class_='authors').find_all('span', class_='inlineblock')] if article.find('div', class_='authors') else []
            date_tag = article.find('div', class_='color-grey-dark')
            date_text = date_tag.text.split(";")[-1].strip().split("-")[-1].strip() if date_tag else "Date not available"

            relevance_score = calculate_relevance(title, description_text, qry)

            content = {
                "url": article_url,
                "title": title,
                "description": description_text,
                "authors": authors_list,
                "relevance": relevance_score,
                "source": site,
                "date": date_text
            }
            data.append(content)

    elif site == 'nature':
        for article in soup.find_all('li', class_='app-article-list-row__item'):
            article_tag = article.find('a', class_='c-card__link')
            article_url = f"{base_url}{article_tag.get('href')}"
            title = article_tag.text.strip()
            description_tag = article.find('div', class_='c-card__summary')
            description_text = description_tag.text.strip() if description_tag else "Description not available"
            authors_list = [author.text.strip() for author in article.find_all('span', itemprop='name')]
            date_tag = article.find('time', itemprop='datePublished')
            date_text = date_tag.text.strip() if date_tag else "Date not available"

            relevance_score = calculate_relevance(title, description_text, qry)

            content = {
                "url": article_url,
                "title": title,
                "description": description_text,
                "authors": authors_list,
                "relevance": relevance_score,
                "source": site,
                "date": date_text
            }
            data.append(content)

    elif site == 'omjournal':
        for article in soup.select('tr.GridItem, tr.GridAlternatingItem'):
            link_tag = article.find('a')
            if link_tag:
                article_url = f"{base_url}/{link_tag.get('href')}"
                title = link_tag.text.strip()
                description_text = article.text.strip().replace(title, '').strip()
                authors_list = ["Authors not available"]
                date_match = re.search(r'Volume (\d+), Issue (\d+) (January|February|March|April|May|June|July|August|September|October|November|December) (\d+)', article.text.strip())
                date_text = f"{date_match.group(3)} {date_match.group(2)}, {date_match.group(4)}" if date_match else "Date not available"

                relevance_score = calculate_relevance(title, description_text, qry)

                content = {
                    "url": article_url,
                    "title": title,
                    "description": description_text,
                    "authors": authors_list,
                    "relevance": relevance_score,
                    "source": site,
                    "date": date_text
                }
                data.append(content)

    return data

# Asynchronous function to fetch data from a site
async def fetch_from_site_async(site, qry, headers, retries=3):
    base_url = websites_config[site]['url'].rstrip('/')
    search_path = websites_config[site]['search'].lstrip('/')

    if site == 'springer':
        search_url = f"{base_url}/{search_path}?new-search=true&query={qry}&content-type=article&content-type=research&dateFrom=&dateTo=&sortBy=relevance"
    else:
        search_url = f"{base_url}/{search_path}{qry}"

    clean_url = re.sub(r'(?<!:)//', '/', search_url)

 
    try:
        response = requests.get(clean_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = process_site_data(site, soup, base_url, qry)
        return data
    except Exception as e:
        return {"error": str(e), "site": site}



# Asynchronous function to fetch data from multiple sites in parallel
async def fetch_data_parallel_async(qry, source_filter=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    sources = [site for site in websites_config.keys() if not source_filter or source_filter == 'all' or site == source_filter]

    tasks = [fetch_from_site_async(site, qry, headers) for site in sources]
    results = await asyncio.gather(*tasks)

    # Combine results and filter out any errors or invalid data
    combined_results = []
    for data in results:
        if isinstance(data, list):  # Ensure we only extend with lists of data
            combined_results.extend(data)
        else:
            app.logger.error(f"Invalid data received from site: {data}")

    # Only sort the results that have the 'relevance' key
    combined_results = [result for result in combined_results if isinstance(result, dict) and 'relevance' in result]

    # Sort by relevance in descending order
    combined_results.sort(key=lambda x: x['relevance'], reverse=True)

    return combined_results


# Flask route with asynchronous data fetching
@app.route('/fetch-articles', methods=['GET'])
async def fetch_articles():
    query = request.args.get('q')
    source = request.args.get('source', 'all')
    
    if not query:
        return jsonify({"error": "Query parameter is missing"}), 400

    data = await fetch_data_parallel_async(query, source)
    return jsonify(data)





# Define the login_required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



@app.route('/fetch_paper_by_url', methods=['GET'])
def fetch_paper_by_url():
    # Get the URL from the query parameters
    paper_url = request.args.get('url')

    # Connect to the database (update with your credentials)
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)

    # Query the database to fetch the paper details using the URL
    query = """
        SELECT
            PaperID,
            Title,
            Summary,
            Abstract,
            KeyFindings,
            Methodology,
            Implications,
            Conclusion,
            Insights,
            URL
        FROM
            Papers
        WHERE
            URL = %s;
    """
    cursor.execute(query, (paper_url,))
    paper_details = cursor.fetchone()  # Fetch the paper details

    # Close the database connection
    conn.close()

    # Return the paper details as JSON or an empty response if not found
    if paper_details:
        return jsonify(paper_details)
    else:
        return jsonify({"error": "Paper not found"}), 404


@app.route('/get_details', methods=['GET'])
def get_details():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing URL parameter"}), 400

    # Using Flask-MySQL connection
    cur = mysql.connection.cursor()

    try:
        # Check if the paper is already in the database
        cur.execute("SELECT * FROM paperssummary WHERE URL = %s", (url,))
        result = cur.fetchone()

        if result:
            return jsonify({
                "paperTitle": result[2],
                "summary": json.loads(result[3]) if result[3] else [],
                "abstract": json.loads(result[4]) if result[4] else [],
                "keyFindings": json.loads(result[5]) if result[5] else [],
                "methods": json.loads(result[6]) if result[6] else [],
                "implications": json.loads(result[7]) if result[7] else [],
                "conclusion": json.loads(result[8]) if result[8] else [],
                "insights": json.loads(result[9]) if result[9] else []
            })

        # Fetching the content from the URL using ScraperAPI
        try:
            scraper_api_url = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={url}"
            app.logger.info(f"Making request to ScraperAPI for URL: {url}")
            response = requests.get(scraper_api_url, timeout=20)  # Adding timeout
            app.logger.info(f"ScraperAPI response status: {response.status_code} for URL: {url}")
            response.raise_for_status()
        except requests.Timeout:
            return jsonify({"error": "Request timed out."}), 500
        except requests.RequestException as e:
            return jsonify({"error": "Failed to fetch paper details from the URL."}), 500

        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = [paragraph.text for paragraph in soup.find_all('p')]
        content = '\n'.join(paragraphs).strip()

        if not content:
            content = "This is a placeholder content as the original content was insufficient."

        # Extract the title from the page
        title_tag = soup.find('title')  # Or any other tag containing the title
        paper_title = title_tag.text.strip() if title_tag else "Title not available"

        # Generate prompt using the function from prompts.py
        prompt = Prompts.generate_paper_summary_prompt(paper_title, content)


        # Assuming GenerativeTextEngine is a valid class for generating text
        engine = GenerativeTextEngine(generative_api_key)
        engine.configure()
        summary = engine.generate_content(prompt)
        app.logger.info(f"Generative API response received for URL: {url}")

        # Handle the response from the generative API
        if hasattr(summary, 'parts'):
            combined_text = " ".join([part.text for part in summary.parts if hasattr(part, 'text')])
            if not combined_text.strip():
                return jsonify({"error": "Failed to generate content."}), 500
        else:
            return jsonify({"error": "Unexpected response format."}), 500

        # Clean up the generated text and parse JSON
        clean_text = combined_text.strip().strip('```json').strip('```')

        try:
            paper_data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            return jsonify({"error": "Failed to decode JSON", "response": clean_text}), 500

        user_id = session.get('user_id', 1)  # Default to user 1 if not logged in

        # Save the summary to the database, replacing old data if it exists
        cur.execute(
            """
            REPLACE INTO paperssummary (URL, Title, Summary, Abstract, KeyFindings, Methods, Implications, Conclusion, Insights, DateAdded, UserID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """,
            (
                url,
                paper_data.get("paperTitle", paper_title),  # Ensure the title is the same as extracted
                json.dumps(paper_data.get("summary", [])),
                json.dumps(paper_data.get("abstract", [])),
                json.dumps(paper_data.get("keyFindings", [])),
                json.dumps(paper_data.get("methods", [])),
                json.dumps(paper_data.get("implications", [])),
                json.dumps(paper_data.get("conclusion", [])),
                json.dumps(paper_data.get("insights", [])),
                user_id
            )
        )
        mysql.connection.commit()

        return jsonify(paper_data)

    except MySQLdb.OperationalError as e:
        app.logger.error(f"MySQL Operational Error: {e}", exc_info=True)
        return jsonify({"error": "Database operation failed."}), 500

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request error: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch paper details from the URL."}), 500

    finally:
        cur.close()



@app.route('/summarize-query', methods=['GET'])
def summarize_query():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Query parameter is missing"}), 400

    prompt = Prompts.generate_summary_query_prompt(query)

    engine = GenerativeTextEngine(generative_api_key)
    engine.configure()
    summary_insight = engine.generate_content(prompt).text

    # Clean and format the response
    summary_insight = clean_and_format_summary(summary_insight, query)

    return jsonify({"summary_insight": summary_insight})


def clean_and_format_summary(text, query):
    # Remove "Summary: query" prefix if present
    text = text.replace(f"Summary: {query}", "").strip()
    text = text.replace(f"Summary:", "").strip()

    return text








@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/explore')
@login_required
def explore():
    return render_template('explore.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        app.logger.info(f"Login attempt with email: {email}")

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        user = cur.fetchone()
        cur.close()

        app.logger.info(f"User fetched from database: {user}")

        if user and check_password_hash(user[2], password):
            app.logger.info("Password check passed")
            session['logged_in'] = True
            session['username'] = user[1]
            session['user_id'] = user[0]  # Assuming user[0] is the UserID field
            return redirect(url_for('home'))
        else:
            app.logger.warning("Invalid email or password")
            flash('Invalid email or password!', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.', 'danger')
    return redirect(url_for('login'))

@app.route('/library')
@login_required
def library():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("SELECT Title, URL, Authors, Description, search_query, OriginalURL FROM userlibrary WHERE UserID = %s", [user_id])
    saved_articles = cur.fetchall()
    cur.close()

    # Debugging line to ensure correct data is fetched
    print(saved_articles)
    
    return render_template('library.html', saved_articles=saved_articles)




@app.route('/multiple-papers-summarized')
@login_required
def multiple_papers_summarized():
    selected_urls = request.args.getlist('selectedUrls')  # This will be a list of selected URLs
    papers_data = []
    
    # Loop through each URL and fetch details individually
    for url in selected_urls:
        try:
            # Fetch paper details for each URL
            response = requests.get(f"http://127.0.0.1:5000/get_details?url={url}")
            if response.status_code == 200:
                paper_data = response.json()  # Get the JSON response for each paper
                papers_data.append(paper_data)  # Append to the papers_data list
            else:
                papers_data.append({"error": f"Failed to fetch details for {url}"})
        except Exception as e:
            papers_data.append({"error": f"An error occurred: {str(e)}"})

    # Pass the fetched data to the template
    return render_template('multiple-papers-summarized.html', papers_data=papers_data)


@app.route('/trends')
@login_required
def trends():
    user_id = session.get('user_id')
    time_frame = request.args.get('time_frame', '4')  # Default to 'ALL TIME'
    
    # Fetch user's interests from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT InterestTopic FROM user_interests WHERE UserID = %s", [user_id])
    interests = [row[0] for row in cur.fetchall()]

    # Time frame filtering logic
    if time_frame == '0':  # Today
        time_filter = "DATE(Timestamp) = CURDATE()"
    elif time_frame == '1':  # Last Week
        time_filter = "Timestamp >= CURDATE() - INTERVAL 7 DAY"
    elif time_frame == '2':  # Last Month
        time_filter = "Timestamp >= CURDATE() - INTERVAL 1 MONTH"
    elif time_frame == '3':  # Last Year
        time_filter = "Timestamp >= CURDATE() - INTERVAL 1 YEAR"
    else:  # All Time
        time_filter = "1=1"

    # Fetch top searches based on the time filter
    cur.execute(f"""
        SELECT SearchQuery, COUNT(SearchQuery) as count 
        FROM searchlog 
        WHERE {time_filter}
        GROUP BY SearchQuery 
        ORDER BY count DESC 
        LIMIT 10
    """)
    top_searches = cur.fetchall()

    # Fetch top 3 searches for scorecards
    cur.execute(f"""
        SELECT SearchQuery, COUNT(SearchQuery) as count 
        FROM searchlog 
        WHERE {time_filter}
        GROUP BY SearchQuery 
        ORDER BY count DESC 
        LIMIT 3
    """)
    top_3_searches = cur.fetchall()

    cur.close()

    return render_template('trends.html', top_searches=top_searches, interests=interests, top_3_searches=top_3_searches, time_frame=time_frame)



@app.route('/about-us')
@login_required
def about_us():
    return render_template('aboutus.html')

# Dummy data for demonstration purposes
general_notifications = [
    {"message": "System maintenance scheduled for tomorrow.", "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
    {"message": "New feature added to the platform.", "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
]

interest_notifications = [
    {"message": "New research paper on kidney cancer.", "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
    {"message": "Breast cancer study update.", "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
]

@app.route('/notifications')
@login_required
def notifications():
    UserID = session.get('user_id')  # Assuming user_id is stored in the session

    # Fetch general notifications
    cur = mysql.connection.cursor()
    cur.execute("SELECT message, date FROM notifications WHERE UserID = %s AND is_general = TRUE", [UserID])
    general_notifications = cur.fetchall()

    # Fetch interest-based notifications
    cur.execute("""
        SELECT notifications.message, notifications.date
        FROM notifications
        JOIN interests ON notifications.UserID = interests.UserID
        WHERE notifications.UserID = %s AND notifications.is_general = FALSE
    """, [UserID])
    interest_notifications = cur.fetchall()
    cur.close()

    return render_template('notifications.html', general_notifications=general_notifications, interest_notifications=interest_notifications)




@app.route('/search')
@login_required
def search():
    query = request.args.get('query')
    user_id = session.get('user_id')

    if query:
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO searchlog (UserID, SearchQuery) VALUES (%s, %s)", (user_id, query))
            mysql.connection.commit()
            cur.close()
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error logging search: {str(e)}', 'danger')

    return render_template('search.html', query=query)



@app.route('/paper-summary')
@login_required
def paper_summary():
    return render_template('paper-summary.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_password))
            app.logger.info(f"User {email} signed up successfully")
            mysql.connection.commit()
            user_id = cur.lastrowid
            cur.close()
            session['user_id'] = user_id  # Save user ID in session
            flash('You have successfully registered!', 'success')
            return redirect(url_for('user_preferences'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('signup.html')

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


@app.route('/save_article', methods=['POST'])
@login_required
def save_article():
    data = request.get_json()
    user_id = session.get('user_id')
    title = data.get('title')
    url = data.get('url')  # This will be the URL used for the "Read Full Paper" link
    authors = data.get('authors')
    description = data.get('description')
    search_query = data.get('search_query')
    original_url = data.get('original_url')  # Retrieve the original URL

    if not title or not url or not user_id:
        return jsonify({"error": "Invalid input"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO userlibrary (UserID, Title, URL, Authors, Description, search_query, OriginalURL) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                    (user_id, title, url, authors, description, search_query, original_url))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Article saved successfully"}), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": str(e)}), 500





    

@app.route('/unsave_article', methods=['POST'])
@login_required
def unsave_article():
    data = request.get_json()
    user_id = session.get('user_id')
    url = data.get('url')

    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM userlibrary WHERE UserID = %s AND URL = %s", (user_id, url))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Article removed successfully"}), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    if request.method == 'POST':
        email = request.form['email']
        # Add logic to handle password reset
        flash('Password reset link has been sent to your email.', 'success')
        return redirect(url_for('forget_password'))
    return render_template('forget_password.html')

@app.route('/interests')
@login_required
def interests():
    username = session.get('username', 'Guest')
    user_id = session.get('user_id')  # Assuming user_id is stored in session
    cur = mysql.connection.cursor()
    cur.execute("SELECT UserInterestID, InterestTopic FROM user_interests WHERE UserID = %s", [user_id])
    interests = cur.fetchall()
    cur.close()
    return render_template('intresets.html', username=username, interests=interests)


@app.route('/add_interest', methods=['POST'])
def add_interest():
    data = request.get_json()
    interest_topic = data.get('interestTopic')
    user_id = session.get('user_id')  # Get the user ID from session

    if not interest_topic or not user_id:
        return jsonify({'error': 'Invalid input'}), 400

    try:
        cur = mysql.connection.cursor()
        # Check if the interest already exists for the user
        cur.execute("SELECT * FROM user_interests WHERE UserID = %s AND InterestTopic = %s", (user_id, interest_topic))
        existing_interest = cur.fetchone()
        
        if existing_interest:
            return jsonify({'message': 'Interest already added'}), 400

        # Insert the new interest if it doesn't exist
        cur.execute("INSERT INTO user_interests (UserID, InterestTopic) VALUES (%s, %s)", (user_id, interest_topic))
        mysql.connection.commit()
        cur.close()
        return jsonify({'message': 'Interest added successfully'}), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/delete_interest', methods=['POST'])
def delete_interest():
    data = request.get_json()
    interest_id = data.get('interestID')
    user_id = session.get('user_id')  # Get the user ID from session

    if not interest_id or not user_id:
        return jsonify({'error': 'Invalid input'}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM user_interests WHERE UserInterestID = %s AND UserID = %s", (interest_id, user_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({'message': 'Interest deleted successfully'}), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500









@app.route('/create_alert', methods=['POST'])
def create_alert():
    data = request.get_json()
    print('Received data:', data)  # Debugging line
    alert_topic = data.get('alertTopic')
    user_id = session.get('user_id')  # Get the user ID from session

    if not alert_topic or not user_id:
        print('Invalid input:', alert_topic, user_id)  # Debugging line
        return jsonify({'error': 'Invalid input'}), 400

    try:
        cur = mysql.connection.cursor()
        # Check if the interest already exists for the user
        cur.execute("SELECT * FROM user_interests WHERE UserID = %s AND InterestTopic = %s", (user_id, alert_topic))
        existing_interest = cur.fetchone()
        
        if existing_interest:
            return jsonify({'message': 'Interest already added as alert'}), 400

        # Insert the new interest if it doesn't exist
        cur.execute("INSERT INTO user_interests (UserID, InterestTopic) VALUES (%s, %s)", (user_id, alert_topic))
        mysql.connection.commit()
        cur.close()
        print('Alert created successfully')  # Debugging line
        return jsonify({'message': 'Alert created successfully as interest'}), 200
    except Exception as e:
        mysql.connection.rollback()
        print('Error:', e)  # Debugging line
        return jsonify({'error': str(e)}), 500




@app.route('/user_preferences', methods=['GET', 'POST'])
def user_preferences():
    if request.method == 'POST':
        user_id = session.get('user_id')  # Get the user ID from session
        preference_field = request.form['preference_field']
        research_topics = request.form['research_topics']
        additional_info = request.form['additional_info']
        
        if not user_id:
            flash('User not logged in.', 'danger')
            return redirect(url_for('login'))
        
        try:
            cur = mysql.connection.cursor()
            # Insert the preference field
            cur.execute("INSERT INTO user_interests (UserID, InterestTopic) VALUES (%s, %s)", (user_id, preference_field))
            # Insert each research topic individually if there are multiple topics
            for topic in research_topics.split(','):
                cur.execute("INSERT INTO user_interests (UserID, InterestTopic) VALUES (%s, %s)", (user_id, topic.strip()))
            mysql.connection.commit()
            cur.close()
            flash('Your preferences have been saved!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error saving preferences: {str(e)}', 'danger')
        
        return redirect(url_for('home'))
    
    return render_template('user_preferences.html')




@app.route('/save_search_query', methods=['POST'])
@login_required
def save_search_query():
    data = request.get_json()
    query = data.get('query')
    user_id = session.get('user_id')

    if not query or not user_id:
        return jsonify({"error": "Invalid input"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO searchlog (UserID, SearchQuery) VALUES (%s, %s)", (user_id, query))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Search query saved successfully"}), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": str(e)}), 500





@app.route('/pytrends', methods=['POST'])
def pytrends_test():
    data = request.get_json()
    keyword = data.get('keyword')
    
    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400
    
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload([keyword], cat=0, timeframe='today 5-y', geo='', gprop='')
    interest_over_time_df = pytrends.interest_over_time()
    
    interest_over_time = interest_over_time_df.reset_index().to_dict(orient='records')
    trending_searches_df = pytrends.realtime_trending_searches(pn='US')
    trending_searches = trending_searches_df.head(10).to_dict(orient='records')
    
    return jsonify({"interest_over_time": interest_over_time, "trending_searches": trending_searches})





@app.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        # Add your form processing logic here
        # For example, sending an email with the contact form details
        # You can use Flask-Mail or another email sending service

        flash('Your message has been sent successfully!', 'success')
        return redirect(url_for('contact_us'))
    
    return render_template('contact_us.html')


def generate_summary(texts):
    # Combine the texts
    combined_text = "\n\n".join(texts)

    # Use the prompt function from prompts.py
    prompt = Prompts.generate_paper_comparison_prompt(texts)

    # Make a request to the API
    response = requests.post(
        'https://api.your-gemini-endpoint.com/generate',
        headers={'Authorization': f'Bearer {generative_api_key}'},
        json={'prompt': prompt}
    )

    # Parse the API response
    if response.status_code == 200:
        data = response.json()
        return {
            'overall_summary': data['choices'][0]['text'].strip(),
            'similarities': data['choices'][1]['text'].strip(),
            'differences': data['choices'][2]['text'].strip()
        }
    else:
        return {'error': 'Failed to generate summary'}


@app.route('/summarize_papers', methods=['POST'])
def summarize_papers():
    try:
        data = request.json
        summaries = data['summaries']

        prompt = Prompts.generate_paper_comparison_prompt(summaries)

        engine = GenerativeTextEngine(generative_api_key)
        engine.configure()
        result = engine.generate_content(prompt).text

        return jsonify({"summary": result})
    except Exception as e:
        return jsonify({'error': str(e)})

    

@app.route('/compare_key_findings', methods=['POST'])
def compare_key_findings():
    urls = request.json.get('urls')
    
    if not urls or not isinstance(urls, list) or len(urls) < 2:
        return jsonify({"error": "A list of at least two URLs is required"}), 400

    papers = []
    cursor = mysql.connection.cursor()

    # Fetching key findings for each URL
    for url in urls:
        cursor.execute("SELECT Title, KeyFindings FROM paperssummary WHERE URL = %s", (url,))
        result = cursor.fetchone()

        if result:
            # If the result exists in the database
            papers.append({
                "url": url,
                "title": result[0],
                "keyFindings": json.loads(result[1])
            })
        else:
            # If the paper is not in the database, use ScraperAPI to fetch content
            api_url = f'http://api.scraperapi.com?api_key={scraper_api_key}&url={url}'
            try:
                response = requests.get(api_url)
                response.raise_for_status()
            except requests.RequestException as e:
                return jsonify({"error": f"Failed to fetch the paper details for URL {url}: {str(e)}"}), 500

            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = [paragraph.text for paragraph in soup.find_all('p')]
            content = '\n'.join(paragraphs).strip()

            if not content:
                content = "This is placeholder content as the original content was insufficient."

            # Use the function from prompts.py to generate the summary prompt
            prompt = Prompts.generate_summary_prompt(content)


            engine = GenerativeTextEngine(generative_api_key)
            engine.configure()

            # Generate summary using the generative engine
            summary = engine.generate_content(prompt)

            try:
                # Parsing the generated content as JSON
                paper_data = json.loads(summary.text)
                key_findings = paper_data.get("keyFindings", [])

                user_id = session.get('user_id', None)
                if not user_id:
                    user_id = 1

                # Save paper summary into the database
                cursor.execute(
                    """
                    INSERT INTO paperssummary (URL, Title, Summary, Abstract, KeyFindings, Methods, Implications, Conclusion, Insights, Implementation, DateAdded, UserID)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                    """,
                    (
                        url,
                        paper_data.get("paperTitle", "Unknown Title"),
                        json.dumps(paper_data.get("summary", [])),
                        json.dumps(paper_data.get("abstract", [])),
                        json.dumps(key_findings),
                        json.dumps(paper_data.get("methods", [])),
                        json.dumps(paper_data.get("implications", [])),
                        json.dumps(paper_data.get("conclusion", [])),
                        json.dumps(paper_data.get("insights", [])),
                        json.dumps(paper_data.get("implementation", [])),
                        user_id
                    )
                )
                mysql.connection.commit()

                papers.append({
                    "url": url,
                    "title": paper_data.get("paperTitle"),
                    "keyFindings": key_findings,
                    "implementation": paper_data.get("implementation", [])
                })

            except json.JSONDecodeError as e:
                return jsonify({"error": "Failed to decode JSON", "details": str(e), "response": summary.text}), 500

    cursor.close()

    # Combining key findings from all papers
    combined_key_findings = "\n".join([f"Paper Title: {paper['title']}\nKey Findings:\n" + "\n".join(paper["keyFindings"]) for paper in papers])

    # Generate comparison using the function from prompts.py
    prompt = Prompts.generate_comparison_prompt(combined_key_findings)


    # Generate comparison using the generative engine
    engine = GenerativeTextEngine(generative_api_key)
    engine.configure()

    comparison = engine.generate_content(prompt)

    try:
        # Try to parse the comparison as JSON
        comparison_data = json.loads(comparison.text)
        comparison_text = f'''
        **Summary of Key Findings:**
        {comparison_data.get('KeyFindingsSummary', 'No summary available.')}

        **Comparisons Between Papers:**
        {', '.join(comparison_data.get('KeyComparisons', ['No comparisons available.']))}

        **Insights Gained:**
        {comparison_data.get('Insights', 'No insights available.')}

        **Detailed Comparative Analysis:**
        {comparison_data.get('ComparativeAnalysis', 'No analysis available.')}

        **Real-World Implementations:**
        {', '.join(comparison_data.get('Implementation', ['No implementations available.']))}
        '''

        return jsonify({"comparison": comparison_text})
    
    except json.JSONDecodeError:
        # If JSON decoding fails, manually extract sections from the text
        text = comparison.text.strip()

        # Fallback logic: Extract key sections using manual string processing
        key_findings_summary_start = text.find("Summary of Key Findings")
        key_comparisons_start = text.find("Comparisons Between Papers")
        insights_start = text.find("Insights Gained")
        analysis_start = text.find("Detailed Comparative Analysis")
        implementation_start = text.find("Real-World Implementations")

        key_findings_summary = text[key_findings_summary_start:key_comparisons_start].strip() if key_findings_summary_start != -1 else "No Key Findings Summary available"
        key_comparisons = text[key_comparisons_start:insights_start].strip() if key_comparisons_start != -1 else "No Key Comparisons available"
        insights = text[insights_start:analysis_start].strip() if insights_start != -1 else "No Insights available"
        comparative_analysis = text[analysis_start:implementation_start].strip() if analysis_start != -1 else "No Comparative Analysis available"
        implementation = text[implementation_start:].strip() if implementation_start != -1 else "No Implementation information available"

        # Create a readable output without JSON formatting
        comparison_text = f'''
        **Summary of Key Findings:**
        {key_findings_summary}

        **Comparisons Between Papers:**
        {key_comparisons}

        **Insights Gained:**
        {insights}

        **Detailed Comparative Analysis:**
        {comparative_analysis}

        **Real-World Implementations:**
        {implementation}
        '''

        return jsonify({"comparison": comparison_text})





@app.route('/reload_summary', methods=['POST'])
def reload_summary():
    url = request.json.get('url')  # Get URL from the POST request body
    if not url:
        return jsonify({"error": "Missing URL parameter"}), 400

    # Database connection and cursor initialization
    conn = mysql.connection
    cursor = conn.cursor()  # Removed dictionary=True

    try:
        # Step 1: Delete the existing summary
        cursor.execute("DELETE FROM paperssummary WHERE URL = %s", (url,))
        conn.commit()

        # Step 2: Fetch the content from the URL
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.Timeout:
            return jsonify({"error": "Request timed out."}), 500
        except requests.RequestException as e:
            return jsonify({"error": "Failed to fetch paper details from the URL."}), 500

        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = [paragraph.text for paragraph in soup.find_all('p')]
        content = '\n'.join(paragraphs).strip()
        paper_title = request.json.get('paperTitle', 'Insert title here')  

        if not content:
            content = "This is a placeholder content as the original content was insufficient."

        # Generate reload prompt using prompts.py
        prompt = Prompts.generate_paper_summary_prompt(paper_title, content)



        # Assuming GenerativeTextEngine is a valid class for generating text
        engine = GenerativeTextEngine(generative_api_key)
        engine.configure()
        summary = engine.generate_content(prompt)

        # Step 4: Handle the response from the generative API
        if hasattr(summary, 'parts'):
            combined_text = " ".join([part.text for part in summary.parts if hasattr(part, 'text')])
            if not combined_text.strip():
                return jsonify({"error": "Failed to generate content."}), 500
        else:
            return jsonify({"error": "Unexpected response format."}), 500

        # Clean up the generated text and parse JSON
        clean_text = combined_text.strip().strip('```json').strip('```')

        try:
            paper_data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            return jsonify({"error": "Failed to decode JSON", "response": clean_text}), 500

        user_id = session.get('user_id', 1)  # Default to user 1 if not logged in

        # Step 5: Save the new summary to the database
        cursor.execute(
            """
            REPLACE INTO paperssummary (URL, Title, Summary, Abstract, KeyFindings, Methods, Implications, Conclusion, Insights, DateAdded, UserID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """,
            (
                url,
                paper_data["paperTitle"],
                json.dumps(paper_data.get("summary", [])),
                json.dumps(paper_data.get("abstract", [])),
                json.dumps(paper_data.get("keyFindings", [])),
                json.dumps(paper_data.get("methods", [])),
                json.dumps(paper_data.get("implications", [])),
                json.dumps(paper_data.get("conclusion", [])),
                json.dumps(paper_data.get("insights", [])),
                user_id
            )
        )
        conn.commit()

        return jsonify({"message": "Summary reloaded successfully"}), 200

    except MySQLdb.OperationalError as e:
        app.logger.error(f"MySQL Operational Error: {e}", exc_info=True)
        return jsonify({"error": "Database operation failed."}), 500

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({"error": "An unexpected error occurred."}), 500
    finally:
        cursor.close()

    
if __name__ == '__main__':
    app.run(debug=True)

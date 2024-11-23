from flask_mysqldb import MySQL

def create_database(mysql):
    with mysql.connection.cursor() as cursor:
        # Create the database if it doesn't exist
        cursor.execute("CREATE DATABASE IF NOT EXISTS arqamaic_mueen")
        cursor.execute("USE arqamaic_mueen")
        mysql.connection.commit()


def create_tables(app, mysql):
    with app.app_context():
        create_database(mysql)  # Ensure the database exists before creating tables

        with mysql.connection.cursor() as cursor:
            # Create `users` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                UserID INT AUTO_INCREMENT PRIMARY KEY,
                Username VARCHAR(50),
                Password VARCHAR(255),
                Email VARCHAR(100),
                UserType VARCHAR(50)
            );
            """)

            # Create `userlibrary` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS userlibrary (
                LibraryID INT AUTO_INCREMENT PRIMARY KEY,
                UserID INT,
                Title VARCHAR(255),
                URL VARCHAR(255),
                Authors TEXT,
                Description TEXT,
                SavedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                search_query VARCHAR(255),
                OriginalURL VARCHAR(255),
                FOREIGN KEY (UserID) REFERENCES users(UserID)
            );
            """)

            # Create `searchlog` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS searchlog (
                SearchLogID INT AUTO_INCREMENT PRIMARY KEY,
                UserID INT,
                SearchQuery TEXT,
                Timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                InterestTopic VARCHAR(255),
                SearchCountLog INT,
                FOREIGN KEY (UserID) REFERENCES users(UserID)
            );
            """)

            # Create `paperssummary` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS paperssummary (
                SummaryID INT AUTO_INCREMENT PRIMARY KEY,
                URL VARCHAR(255),
                Title VARCHAR(255),
                Summary TEXT,
                Abstract TEXT,
                KeyFindings TEXT,
                Methods TEXT,
                Implications TEXT,
                Conclusion TEXT,
                Insights TEXT,
                DateAdded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UserID INT,
                FOREIGN KEY (UserID) REFERENCES users(UserID)
            );
            """)

            # Create `notifications` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                UserID INT,
                message TEXT,
                date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_general TINYINT(1),
                FOREIGN KEY (UserID) REFERENCES users(UserID)
            );
            """)

            # Create `user_interests` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_interests (
                UserInterestID INT AUTO_INCREMENT PRIMARY KEY,
                UserID INT,
                InterestTopic VARCHAR(255),
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (UserID) REFERENCES users(UserID)
            );
            """)

            # Create `interestanalysis` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS interestanalysis (
                AnalysisID INT AUTO_INCREMENT PRIMARY KEY,
                UserID INT,
                InterestTopic VARCHAR(255),
                TotalSearchCount INT,
                FOREIGN KEY (UserID) REFERENCES users(UserID)
            );
            """)

            # Create `alerts` table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                AlertID INT AUTO_INCREMENT PRIMARY KEY,
                UserID INT,
                InterestTopic VARCHAR(255),
                NotificationSent TINYINT(1),
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (UserID) REFERENCES users(UserID)
            );
            """)

            mysql.connection.commit()
        print("Database and tables created successfully.")